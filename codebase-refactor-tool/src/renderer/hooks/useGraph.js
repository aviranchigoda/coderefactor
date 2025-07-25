import { useState, useEffect, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { setGraphData, setGraphLoading, setGraphError } from '../store/actions/graphActions';

const useGraph = () => {
  const dispatch = useDispatch();
  const { graphData, loading, error } = useSelector(state => state.graph);
  const [isConnected, setIsConnected] = useState(false);

  // Fetch graph data from backend
  const fetchGraphData = useCallback(async () => {
    dispatch(setGraphLoading(true));
    dispatch(setGraphError(null));

    try {
      const response = await window.electronAPI.getGraph();
      
      if (response.error) {
        throw new Error(response.error);
      }

      // Transform data if needed
      const transformedData = {
        nodes: response.nodes || [],
        links: response.links || []
      };

      dispatch(setGraphData(transformedData));
    } catch (err) {
      console.error('Error fetching graph data:', err);
      dispatch(setGraphError(err.message || 'Failed to fetch graph data'));
    } finally {
      dispatch(setGraphLoading(false));
    }
  }, [dispatch]);

  // Get graph statistics
  const getGraphStats = useCallback(async () => {
    try {
      const stats = await window.electronAPI.getGraphStats();
      return stats;
    } catch (err) {
      console.error('Error fetching graph stats:', err);
      return null;
    }
  }, []);

  // Clear graph
  const clearGraph = useCallback(async () => {
    try {
      const response = await window.electronAPI.clearGraph();
      if (response.success) {
        dispatch(setGraphData({ nodes: [], links: [] }));
        return true;
      }
      return false;
    } catch (err) {
      console.error('Error clearing graph:', err);
      return false;
    }
  }, [dispatch]);

  // Refresh graph
  const refreshGraph = useCallback(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  // Prune tree to specific depth from a node
  const pruneTree = useCallback(async (nodeId, depth = 3) => {
    dispatch(setGraphLoading(true));
    
    try {
      const response = await window.electronAPI.pruneTree(nodeId, depth);
      
      if (response.error) {
        throw new Error(response.error);
      }

      dispatch(setGraphData(response));
      return response;
    } catch (err) {
      console.error('Error pruning tree:', err);
      dispatch(setGraphError(err.message));
      return null;
    } finally {
      dispatch(setGraphLoading(false));
    }
  }, [dispatch]);

  // Get subgraph for a specific node
  const getSubgraph = useCallback(async (nodeId, options = {}) => {
    try {
      const response = await window.electronAPI.getSubgraph(nodeId, options);
      
      if (response.error) {
        throw new Error(response.error);
      }

      return response;
    } catch (err) {
      console.error('Error getting subgraph:', err);
      return null;
    }
  }, []);

  // Find paths between nodes
  const findPaths = useCallback(async (sourceId, targetId, maxLength = 5) => {
    try {
      const response = await window.electronAPI.findPaths(sourceId, targetId, maxLength);
      
      if (response.error) {
        throw new Error(response.error);
      }

      return response.paths || [];
    } catch (err) {
      console.error('Error finding paths:', err);
      return [];
    }
  }, []);

  // Search nodes by name or property
  const searchNodes = useCallback(async (query, filters = {}) => {
    try {
      const response = await window.electronAPI.searchNodes(query, filters);
      
      if (response.error) {
        throw new Error(response.error);
      }

      return response.nodes || [];
    } catch (err) {
      console.error('Error searching nodes:', err);
      return [];
    }
  }, []);

  // Get node details with relationships
  const getNodeDetails = useCallback(async (nodeId) => {
    try {
      const response = await window.electronAPI.getNodeDetails(nodeId);
      
      if (response.error) {
        throw new Error(response.error);
      }

      return response;
    } catch (err) {
      console.error('Error getting node details:', err);
      return null;
    }
  }, []);

  // Export graph data
  const exportGraph = useCallback(async (format = 'json') => {
    try {
      const response = await window.electronAPI.exportGraph(format);
      
      if (response.error) {
        throw new Error(response.error);
      }

      return response;
    } catch (err) {
      console.error('Error exporting graph:', err);
      return null;
    }
  }, []);

  // WebSocket connection for real-time updates
  useEffect(() => {
    let ws = null;

    const connectWebSocket = () => {
      try {
        ws = new WebSocket('ws://localhost:5000/ws');

        ws.onopen = () => {
          console.log('WebSocket connected');
          setIsConnected(true);
          
          // Subscribe to graph updates
          ws.send(JSON.stringify({
            type: 'subscribe',
            topic: 'graph'
          }));
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            
            switch (message.type) {
              case 'graph_updated':
                // Refresh graph data
                fetchGraphData();
                break;
                
              case 'node_added':
                // Add node to existing graph
                dispatch({
                  type: 'ADD_GRAPH_NODE',
                  payload: message.data
                });
                break;
                
              case 'node_removed':
                // Remove node from graph
                dispatch({
                  type: 'REMOVE_GRAPH_NODE',
                  payload: message.data.nodeId
                });
                break;
                
              case 'link_added':
                // Add link to graph
                dispatch({
                  type: 'ADD_GRAPH_LINK',
                  payload: message.data
                });
                break;
                
              case 'link_removed':
                // Remove link from graph
                dispatch({
                  type: 'REMOVE_GRAPH_LINK',
                  payload: message.data
                });
                break;
                
              default:
                break;
            }
          } catch (err) {
            console.error('Error handling WebSocket message:', err);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          setIsConnected(false);
        };

        ws.onclose = () => {
          console.log('WebSocket disconnected');
          setIsConnected(false);
          
          // Attempt to reconnect after 5 seconds
          setTimeout(connectWebSocket, 5000);
        };
      } catch (err) {
        console.error('Failed to connect WebSocket:', err);
        setIsConnected(false);
      }
    };

    // Connect on mount
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [dispatch, fetchGraphData]);

  // Initial data fetch
  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  return {
    graphData,
    loading,
    error,
    isConnected,
    refreshGraph,
    clearGraph,
    pruneTree,
    getSubgraph,
    findPaths,
    searchNodes,
    getNodeDetails,
    exportGraph,
    getGraphStats
  };
};

export default useGraph;