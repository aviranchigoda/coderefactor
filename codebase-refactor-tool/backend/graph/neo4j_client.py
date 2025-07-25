"""
Neo4j database client for managing graph operations.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from contextlib import contextmanager
import os

try:
    from neo4j import GraphDatabase, Driver, Session, Result
    from neo4j.exceptions import ServiceUnavailable, AuthError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    Driver = Session = Result = None


logger = logging.getLogger(__name__)


class Neo4jClient:
    """Client for managing Neo4j database connections and operations."""
    
    def __init__(self, uri: str = None, username: str = None, password: str = None):
        """
        Initialize Neo4j client.
        
        Args:
            uri: Neo4j database URI (defaults to bolt://localhost:7687)
            username: Database username (defaults to neo4j)
            password: Database password (required)
        """
        if not NEO4J_AVAILABLE:
            raise ImportError("neo4j package is not installed. Install with: pip install neo4j")
        
        self.uri = uri or os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.username = username or os.getenv('NEO4J_USERNAME', 'neo4j')
        self.password = password or os.getenv('NEO4J_PASSWORD')
        
        if not self.password:
            raise ValueError("Neo4j password must be provided via parameter or NEO4J_PASSWORD environment variable")
        
        self.driver: Optional[Driver] = None
        self.connected = False
    
    def connect(self) -> bool:
        """
        Establish connection to Neo4j database.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            
            # Test the connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            self.connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")
            return True
            
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Neo4j: {e}")
            return False
    
    def disconnect(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()
            self.connected = False
            logger.info("Disconnected from Neo4j")
    
    def is_connected(self) -> bool:
        """Check if client is connected to database."""
        return self.connected and self.driver is not None
    
    @contextmanager
    def session(self):
        """Context manager for database sessions."""
        if not self.is_connected():
            if not self.connect():
                raise RuntimeError("Failed to connect to Neo4j database")
        
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def run_query(self, query: str, parameters: Dict[str, Any] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a Cypher query.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records as dictionaries, or None if error
        """
        try:
            with self.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
                
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            logger.debug(f"Query: {query}")
            logger.debug(f"Parameters: {parameters}")
            return None
    
    def run_query_single(self, query: str, parameters: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return a single result.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            Single result record as dictionary, or None if no results or error
        """
        results = self.run_query(query, parameters)
        if results and len(results) > 0:
            return results[0]
        return None
    
    def run_transaction(self, queries: List[tuple]) -> bool:
        """
        Execute multiple queries in a transaction.
        
        Args:
            queries: List of (query, parameters) tuples
            
        Returns:
            bool: True if all queries succeeded, False otherwise
        """
        try:
            with self.session() as session:
                with session.begin_transaction() as tx:
                    for query, parameters in queries:
                        tx.run(query, parameters or {})
                    tx.commit()
                return True
                
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            return False
    
    def create_constraints(self):
        """Create recommended constraints and indexes for performance."""
        constraints = [
            # Unique constraints
            "CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT class_name_line_unique IF NOT EXISTS FOR (c:Class) REQUIRE (c.name, c.line_start) IS UNIQUE",
            "CREATE CONSTRAINT method_name_line_unique IF NOT EXISTS FOR (m:Method) REQUIRE (m.name, m.line_start) IS UNIQUE",
            "CREATE CONSTRAINT function_name_line_unique IF NOT EXISTS FOR (f:Function) REQUIRE (f.name, f.line_start) IS UNIQUE",
            
            # Indexes for performance
            "CREATE INDEX file_name_index IF NOT EXISTS FOR (f:File) ON (f.name)",
            "CREATE INDEX class_name_index IF NOT EXISTS FOR (c:Class) ON (c.name)",
            "CREATE INDEX method_name_index IF NOT EXISTS FOR (m:Method) ON (m.name)",
            "CREATE INDEX function_name_index IF NOT EXISTS FOR (f:Function) ON (f.name)",
            "CREATE INDEX lint_error_line_index IF NOT EXISTS FOR (e:LintError) ON (e.line)",
            "CREATE INDEX lint_error_severity_index IF NOT EXISTS FOR (e:LintError) ON (e.severity)"
        ]
        
        for constraint in constraints:
            try:
                self.run_query(constraint)
                logger.debug(f"Created constraint/index: {constraint}")
            except Exception as e:
                logger.warning(f"Failed to create constraint/index: {e}")
    
    def clear_database(self) -> bool:
        """
        Clear all data from the database.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.run_query("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, int]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with node and relationship counts
        """
        try:
            # Count nodes by type
            node_counts = {}
            node_types = ['File', 'Class', 'Method', 'Function', 'LintError']
            
            for node_type in node_types:
                result = self.run_query_single(f"MATCH (n:{node_type}) RETURN count(n) as count")
                node_counts[node_type.lower()] = result['count'] if result else 0
            
            # Count relationships by type
            rel_counts = {}
            rel_types = ['CONTAINS', 'HAS_METHOD', 'CALLS', 'HAS_ERROR']
            
            for rel_type in rel_types:
                result = self.run_query_single(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
                rel_counts[rel_type.lower()] = result['count'] if result else 0
            
            return {
                'nodes': node_counts,
                'relationships': rel_counts,
                'total_nodes': sum(node_counts.values()),
                'total_relationships': sum(rel_counts.values())
            }
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
    
    def health_check(self) -> Dict[str, Union[bool, str]]:
        """
        Perform a health check on the database connection.
        
        Returns:
            Dictionary with health status information
        """
        try:
            if not self.is_connected():
                return {
                    'healthy': False,
                    'message': 'Not connected to database'
                }
            
            # Test basic query
            result = self.run_query_single("RETURN 1 as test")
            if result and result.get('test') == 1:
                return {
                    'healthy': True,
                    'message': 'Database connection healthy',
                    'uri': self.uri
                }
            else:
                return {
                    'healthy': False,
                    'message': 'Database query test failed'
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Health check failed: {str(e)}'
            }
    
    def __enter__(self):
        """Context manager entry."""
        if not self.connect():
            raise RuntimeError("Failed to connect to Neo4j database")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


# Factory function for creating Neo4j client
def create_neo4j_client(uri: str = None, username: str = None, password: str = None) -> Neo4jClient:
    """
    Factory function to create a Neo4j client.
    
    Args:
        uri: Neo4j database URI
        username: Database username
        password: Database password
        
    Returns:
        Configured Neo4jClient instance
    """
    return Neo4jClient(uri, username, password)