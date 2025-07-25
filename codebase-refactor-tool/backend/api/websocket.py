"""
WebSocket management for real-time communication with the frontend.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types."""
    # Analysis progress
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_PROGRESS = "analysis_progress"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"
    
    # File processing
    FILE_STARTED = "file_started"
    FILE_COMPLETED = "file_completed"
    FILE_FAILED = "file_failed"
    
    # Graph updates
    GRAPH_NODE_ADDED = "graph_node_added"
    GRAPH_EDGE_ADDED = "graph_edge_added"
    GRAPH_UPDATED = "graph_updated"
    
    # Linting
    LINT_STARTED = "lint_started"
    LINT_COMPLETED = "lint_completed"
    LINT_ERROR = "lint_error"
    
    # System status
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    INFO = "info"
    WARNING = "warning"


@dataclass
class WebSocketMessage:
    """Structured WebSocket message."""
    type: MessageType
    data: Dict[str, Any]
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps({
            'type': self.type.value,
            'data': self.data,
            'timestamp': self.timestamp
        })


class ProgressTracker:
    """Tracks and reports progress of long-running operations."""
    
    def __init__(self, total: int, operation: str = "Processing"):
        self.total = total
        self.current = 0
        self.operation = operation
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 1.0  # Update every second
    
    def update(self, increment: int = 1) -> Optional[Dict]:
        """Update progress and return progress data if should notify."""
        self.current += increment
        current_time = time.time()
        
        # Only update if enough time has passed or operation is complete
        if (current_time - self.last_update >= self.update_interval or 
            self.current >= self.total):
            
            self.last_update = current_time
            elapsed = current_time - self.start_time
            percentage = (self.current / self.total) * 100 if self.total > 0 else 0
            rate = self.current / elapsed if elapsed > 0 else 0
            
            eta = (self.total - self.current) / rate if rate > 0 and self.current < self.total else 0
            
            return {
                'operation': self.operation,
                'current': self.current,
                'total': self.total,
                'percentage': round(percentage, 1),
                'elapsed': round(elapsed, 1),
                'rate': round(rate, 1),
                'eta': round(eta, 1),
                'completed': self.current >= self.total
            }
        
        return None


class WebSocketManager:
    """Manages WebSocket connections and broadcasting."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict] = {}
        self.progress_trackers: Dict[str, ProgressTracker] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        async with self._lock:
            self.active_connections[client_id] = websocket
            self.connection_metadata[client_id] = {
                'connected_at': time.time(),
                'subscriptions': set()
            }
        
        logger.info(f"WebSocket client {client_id} connected")
        
        # Send connection confirmation
        await self.send_to_client(client_id, WebSocketMessage(
            type=MessageType.INFO,
            data={'message': 'Connected successfully', 'client_id': client_id}
        ))
    
    async def disconnect(self, client_id: str):
        """Disconnect a WebSocket client."""
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
            if client_id in self.connection_metadata:
                del self.connection_metadata[client_id]
            if client_id in self.progress_trackers:
                del self.progress_trackers[client_id]
        
        logger.info(f"WebSocket client {client_id} disconnected")
    
    async def send_to_client(self, client_id: str, message: WebSocketMessage):
        """Send message to a specific client."""
        if client_id not in self.active_connections:
            logger.warning(f"Attempted to send message to disconnected client: {client_id}")
            return
        
        try:
            websocket = self.active_connections[client_id]
            await websocket.send_text(message.to_json())
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
            await self.disconnect(client_id)
    
    async def broadcast(self, message: WebSocketMessage, exclude: Optional[Set[str]] = None):
        """Broadcast message to all connected clients."""
        exclude = exclude or set()
        disconnected_clients = []
        
        async with self._lock:
            clients = list(self.active_connections.keys())
        
        for client_id in clients:
            if client_id not in exclude:
                try:
                    await self.send_to_client(client_id, message)
                except Exception as e:
                    logger.error(f"Error broadcasting to client {client_id}: {e}")
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
    
    async def send_progress_update(self, client_id: str, tracker_id: str, 
                                 increment: int = 1):
        """Send progress update for a specific tracker."""
        if tracker_id in self.progress_trackers:
            tracker = self.progress_trackers[tracker_id]
            progress_data = tracker.update(increment)
            
            if progress_data:
                message = WebSocketMessage(
                    type=MessageType.ANALYSIS_PROGRESS,
                    data=progress_data
                )
                await self.send_to_client(client_id, message)
                
                # Clean up completed trackers
                if progress_data.get('completed'):
                    del self.progress_trackers[tracker_id]
    
    async def start_progress_tracking(self, client_id: str, tracker_id: str, 
                                    total: int, operation: str = "Processing"):
        """Start tracking progress for an operation."""
        self.progress_trackers[tracker_id] = ProgressTracker(total, operation)
        
        # Send initial progress message
        message = WebSocketMessage(
            type=MessageType.ANALYSIS_STARTED,
            data={
                'tracker_id': tracker_id,
                'operation': operation,
                'total': total
            }
        )
        await self.send_to_client(client_id, message)
    
    async def send_analysis_completed(self, client_id: str, results: Dict):
        """Send analysis completion notification."""
        message = WebSocketMessage(
            type=MessageType.ANALYSIS_COMPLETED,
            data=results
        )
        await self.send_to_client(client_id, message)
    
    async def send_analysis_failed(self, client_id: str, error: str):
        """Send analysis failure notification."""
        message = WebSocketMessage(
            type=MessageType.ANALYSIS_FAILED,
            data={'error': error}
        )
        await self.send_to_client(client_id, message)
    
    async def send_file_processing_update(self, client_id: str, file_path: str, 
                                        status: str, details: Optional[Dict] = None):
        """Send file processing update."""
        message_type = {
            'started': MessageType.FILE_STARTED,
            'completed': MessageType.FILE_COMPLETED,
            'failed': MessageType.FILE_FAILED
        }.get(status, MessageType.INFO)
        
        data = {
            'file_path': file_path,
            'status': status,
            'file_name': Path(file_path).name
        }
        
        if details:
            data.update(details)
        
        message = WebSocketMessage(type=message_type, data=data)
        await self.send_to_client(client_id, message)
    
    async def send_graph_update(self, node_data: Optional[Dict] = None, 
                              edge_data: Optional[Dict] = None):
        """Send graph update to all clients."""
        if node_data:
            message = WebSocketMessage(
                type=MessageType.GRAPH_NODE_ADDED,
                data=node_data
            )
            await self.broadcast(message)
        
        if edge_data:
            message = WebSocketMessage(
                type=MessageType.GRAPH_EDGE_ADDED,
                data=edge_data
            )
            await self.broadcast(message)
    
    async def send_lint_update(self, client_id: str, file_path: str, 
                             errors: List[Dict]):
        """Send linting results update."""
        message = WebSocketMessage(
            type=MessageType.LINT_COMPLETED,
            data={
                'file_path': file_path,
                'errors': errors,
                'error_count': len(errors)
            }
        )
        await self.send_to_client(client_id, message)
    
    async def send_status_update(self, status: str, details: Optional[Dict] = None):
        """Send system status update to all clients."""
        data = {'status': status}
        if details:
            data.update(details)
        
        message = WebSocketMessage(
            type=MessageType.STATUS_UPDATE,
            data=data
        )
        await self.broadcast(message)
    
    async def send_error(self, client_id: str, error: str, details: Optional[Dict] = None):
        """Send error message to specific client."""
        data = {'error': error}
        if details:
            data.update(details)
        
        message = WebSocketMessage(
            type=MessageType.ERROR,
            data=data
        )
        await self.send_to_client(client_id, message)
    
    def get_connection_stats(self) -> Dict:
        """Get statistics about active connections."""
        return {
            'active_connections': len(self.active_connections),
            'active_trackers': len(self.progress_trackers),
            'client_ids': list(self.active_connections.keys())
        }


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint handler."""
    try:
        await websocket_manager.connect(websocket, client_id)
        
        while True:
            try:
                # Listen for incoming messages
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle client messages (subscription management, etc.)
                await handle_client_message(client_id, message)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket_manager.send_error(
                    client_id, 
                    "Invalid JSON message format"
                )
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await websocket_manager.send_error(
                    client_id, 
                    f"Message handling error: {str(e)}"
                )
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    
    finally:
        await websocket_manager.disconnect(client_id)


async def handle_client_message(client_id: str, message: Dict):
    """Handle incoming messages from WebSocket clients."""
    message_type = message.get('type')
    data = message.get('data', {})
    
    if message_type == 'subscribe':
        # Handle subscription to specific events
        subscriptions = data.get('subscriptions', [])
        if client_id in websocket_manager.connection_metadata:
            websocket_manager.connection_metadata[client_id]['subscriptions'].update(subscriptions)
        
        await websocket_manager.send_to_client(
            client_id,
            WebSocketMessage(
                type=MessageType.INFO,
                data={'message': f'Subscribed to: {subscriptions}'}
            )
        )
    
    elif message_type == 'ping':
        # Handle ping/pong for connection keepalive
        await websocket_manager.send_to_client(
            client_id,
            WebSocketMessage(
                type=MessageType.INFO,
                data={'message': 'pong'}
            )
        )
    
    else:
        logger.warning(f"Unknown message type from client {client_id}: {message_type}")