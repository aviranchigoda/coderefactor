"""
Main backend server for the Codebase Refactor Tool.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio
from contextlib import asynccontextmanager

# FastAPI and related imports
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our modules
from config import Config
from core.analyzer import CodebaseAnalyzer
from graph.neo4j_client import create_neo4j_client
from api.routes import setup_routes
from api.websocket import WebSocketManager
from utils.logger import setup_logging

# Setup logging
logger = setup_logging(__name__)

# Global instances
neo4j_client = None
analyzer = None
websocket_manager = WebSocketManager()
config = Config()


# Pydantic models for requests
class ProjectScanRequest(BaseModel):
    path: str
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class FileAnalysisRequest(BaseModel):
    file_path: str


class RefactoringRequest(BaseModel):
    node_id: str
    refactor_type: str
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global neo4j_client, analyzer
    
    logger.info("Starting Codebase Refactor Tool Backend...")
    
    # Initialize Neo4j client
    try:
        neo4j_client = create_neo4j_client(
            uri=config.neo4j_uri,
            username=config.neo4j_username,
            password=config.neo4j_password
        )
        
        if not neo4j_client.connect():
            logger.error("Failed to connect to Neo4j")
            raise RuntimeError("Neo4j connection failed")
        
        # Create constraints and indexes
        neo4j_client.create_constraints()
        
        # Initialize analyzer
        analyzer = CodebaseAnalyzer(neo4j_client, config.analyzer_config)
        
        logger.info("Backend initialization complete")
        
    except Exception as e:
        logger.error(f"Failed to initialize backend: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down backend...")
    if neo4j_client:
        neo4j_client.disconnect()
    logger.info("Backend shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Codebase Refactor Tool API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "file://"],  # Electron app origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Check backend health status."""
    neo4j_health = neo4j_client.health_check() if neo4j_client else {"healthy": False}
    
    return {
        "status": "healthy" if neo4j_health.get("healthy") else "unhealthy",
        "neo4j": neo4j_health,
        "analyzer": analyzer is not None
    }


# Project management endpoints
@app.post("/api/project/scan")
async def scan_project(request: ProjectScanRequest):
    """Scan and analyze a project."""
    try:
        if not analyzer:
            raise HTTPException(status_code=503, detail="Analyzer not initialized")
        
        # Start analysis in background and report progress via WebSocket
        async def run_analysis():
            try:
                # Send initial status
                await websocket_manager.broadcast({
                    "type": "analysis_started",
                    "data": {"path": request.path}
                })
                
                # Run analysis (this is blocking, so we might want to use ThreadPoolExecutor)
                result = analyzer.analyze_codebase(request.path, request.options)
                
                # Send completion status
                await websocket_manager.broadcast({
                    "type": "analysis_completed",
                    "data": result
                })
                
                return result
                
            except Exception as e:
                await websocket_manager.broadcast({
                    "type": "analysis_error",
                    "data": {"error": str(e)}
                })
                raise
        
        # Start analysis task
        asyncio.create_task(run_analysis())
        
        return {"status": "started", "path": request.path}
        
    except Exception as e:
        logger.error(f"Project scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/project/info")
async def get_project_info():
    """Get current project information."""
    try:
        if not analyzer:
            raise HTTPException(status_code=503, detail="Analyzer not initialized")
        
        return analyzer.get_project_stats()
        
    except Exception as e:
        logger.error(f"Failed to get project info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Graph endpoints
@app.get("/api/graph")
async def get_graph_data():
    """Get graph data for visualization."""
    try:
        if not neo4j_client:
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        
        # Query for all nodes and relationships
        nodes_query = """
        MATCH (n)
        RETURN n, labels(n) as labels
        LIMIT 1000
        """
        
        relationships_query = """
        MATCH (n)-[r]->(m)
        RETURN n, r, m, type(r) as type
        LIMIT 2000
        """
        
        nodes = neo4j_client.run_query(nodes_query)
        relationships = neo4j_client.run_query(relationships_query)
        
        # Format for frontend
        graph_data = {
            "nodes": [],
            "links": []
        }
        
        # Process nodes
        node_map = {}
        for record in nodes or []:
            node = record['n']
            node_id = str(node.id)
            node_map[node_id] = {
                "id": node_id,
                "type": record['labels'][0] if record['labels'] else 'Unknown',
                "properties": dict(node)
            }
            graph_data["nodes"].append(node_map[node_id])
        
        # Process relationships
        for record in relationships or []:
            source_id = str(record['n'].id)
            target_id = str(record['m'].id)
            
            if source_id in node_map and target_id in node_map:
                graph_data["links"].append({
                    "source": source_id,
                    "target": target_id,
                    "type": record['type']
                })
        
        return graph_data
        
    except Exception as e:
        logger.error(f"Failed to get graph data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/stats")
async def get_graph_stats():
    """Get graph statistics."""
    try:
        if not neo4j_client:
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        
        return neo4j_client.get_database_stats()
        
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/graph/clear")
async def clear_graph():
    """Clear the graph database."""
    try:
        if not neo4j_client:
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        
        success = neo4j_client.clear_database()
        
        if analyzer:
            analyzer.clear_analysis()
        
        return {"success": success}
        
    except Exception as e:
        logger.error(f"Failed to clear graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# File analysis endpoints
@app.post("/api/analysis/file")
async def analyze_file(request: FileAnalysisRequest):
    """Analyze a specific file."""
    try:
        if not analyzer:
            raise HTTPException(status_code=503, detail="Analyzer not initialized")
        
        result = analyzer.get_file_analysis(request.file_path)
        return result
        
    except Exception as e:
        logger.error(f"File analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for real-time updates."""
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_json()
            
            # Handle different message types
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "subscribe":
                # Handle subscription to specific events
                pass
                
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        websocket_manager.disconnect(websocket)


# Refactoring endpoints (placeholder)
@app.post("/api/refactoring/candidates")
async def find_refactoring_candidates(pattern: Dict[str, Any]):
    """Find refactoring candidates based on pattern."""
    # TODO: Implement refactoring candidate search
    return {"candidates": []}


@app.post("/api/refactoring/preview")
async def preview_refactoring(request: RefactoringRequest):
    """Preview refactoring changes."""
    # TODO: Implement refactoring preview
    return {"preview": "Not implemented"}


@app.post("/api/refactoring/apply")
async def apply_refactoring(request: RefactoringRequest):
    """Apply refactoring to code."""
    # TODO: Implement refactoring application
    return {"status": "Not implemented"}


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"error": "Endpoint not found", "path": str(request.url)}


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return {"error": "Internal server error"}


def main():
    """Run the backend server."""
    # Configure uvicorn logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Run server
    uvicorn.run(
        "main:app",
        host=config.server_host,
        port=config.server_port,
        reload=config.debug,
        log_config=log_config
    )


if __name__ == "__main__":
    main()