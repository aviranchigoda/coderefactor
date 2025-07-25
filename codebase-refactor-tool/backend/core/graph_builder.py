"""
Graph builder for constructing Neo4j graph from code entities.
"""

from typing import List, Dict, Optional, Set
import logging
from ..models.code_entity import (
    CodebaseModel, FileEntity, ClassEntity, FunctionEntity, 
    MethodEntity, LintErrorEntity, CallRelationship
)
from ..models.graph_node import (
    GraphNode, GraphRelationship, RelationshipType,
    create_file_node, create_class_node, create_method_node,
    create_function_node, create_lint_error_node, create_relationship
)
from ..graph.neo4j_client import Neo4jClient
from ..graph import queries


logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds and manages the Neo4j graph representation of the codebase."""
    
    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
        self.created_nodes: Dict[str, GraphNode] = {}
        self.created_relationships: List[GraphRelationship] = []
    
    def build_graph(self, codebase_model: CodebaseModel) -> bool:
        """
        Build the complete graph from a codebase model.
        
        Args:
            codebase_model: The parsed codebase structure
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Starting graph construction")
            
            # Clear existing graph (optional - for development)
            # self.clear_graph()
            
            # Create file nodes and their contents
            self._create_file_nodes(codebase_model)
            
            # Create class nodes and relationships
            self._create_class_nodes(codebase_model)
            
            # Create function/method nodes and relationships
            self._create_function_nodes(codebase_model)
            
            # Create lint error nodes and relationships
            self._create_lint_error_nodes(codebase_model)
            
            # Create call relationships
            self._create_call_relationships(codebase_model)
            
            logger.info(f"Graph construction completed. Created {len(self.created_nodes)} nodes")
            return True
            
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            return False
    
    def _create_file_nodes(self, codebase_model: CodebaseModel):
        """Create file nodes in the graph."""
        for file_path, file_entity in codebase_model.files.items():
            file_node = file_entity.to_graph_node()
            
            # Create file node in Neo4j
            result = self.neo4j_client.run_query(
                queries.CREATE_FILE_NODE,
                file_node.properties
            )
            
            if result:
                self.created_nodes[file_entity.get_unique_id()] = file_node
                logger.debug(f"Created file node: {file_path}")
    
    def _create_class_nodes(self, codebase_model: CodebaseModel):
        """Create class nodes and their relationships to files."""
        for file_entity in codebase_model.files.values():
            for class_entity in file_entity.classes:
                class_node = class_entity.to_graph_node()
                
                # Create class node
                result = self.neo4j_client.run_query(
                    queries.CREATE_CLASS_NODE,
                    class_node.properties
                )
                
                if result:
                    self.created_nodes[class_entity.get_unique_id()] = class_node
                    
                    # Create file-contains-class relationship
                    self.neo4j_client.run_query(
                        queries.CREATE_FILE_CONTAINS_CLASS,
                        {
                            "file_path": file_entity.file_path,
                            "class_name": class_entity.name,
                            "line_start": class_entity.location.line_start
                        }
                    )
                    
                    logger.debug(f"Created class node: {class_entity.name}")
    
    def _create_function_nodes(self, codebase_model: CodebaseModel):
        """Create function and method nodes with their relationships."""
        for file_entity in codebase_model.files.values():
            # Create standalone functions
            for function_entity in file_entity.functions:
                self._create_function_node(function_entity, file_entity.file_path)
            
            # Create methods within classes
            for class_entity in file_entity.classes:
                for method_entity in class_entity.methods:
                    self._create_method_node(method_entity, class_entity)
    
    def _create_function_node(self, function_entity: FunctionEntity, file_path: str):
        """Create a function node and its file relationship."""
        function_node = function_entity.to_graph_node()
        
        # Create function node
        result = self.neo4j_client.run_query(
            queries.CREATE_FUNCTION_NODE,
            function_node.properties
        )
        
        if result:
            self.created_nodes[function_entity.get_unique_id()] = function_node
            
            # Create file-contains-function relationship
            self.neo4j_client.run_query(
                queries.CREATE_FILE_CONTAINS_FUNCTION,
                {
                    "file_path": file_path,
                    "function_name": function_entity.name,
                    "line_start": function_entity.location.line_start
                }
            )
            
            logger.debug(f"Created function node: {function_entity.name}")
    
    def _create_method_node(self, method_entity: MethodEntity, class_entity: ClassEntity):
        """Create a method node and its class relationship."""
        method_node = method_entity.to_graph_node()
        
        # Create method node
        result = self.neo4j_client.run_query(
            queries.CREATE_METHOD_NODE,
            method_node.properties
        )
        
        if result:
            self.created_nodes[method_entity.get_unique_id()] = method_node
            
            # Create class-has-method relationship
            self.neo4j_client.run_query(
                queries.CREATE_CLASS_HAS_METHOD,
                {
                    "class_name": class_entity.name,
                    "class_line_start": class_entity.location.line_start,
                    "method_name": method_entity.name,
                    "method_line_start": method_entity.location.line_start
                }
            )
            
            logger.debug(f"Created method node: {method_entity.name}")
    
    def _create_lint_error_nodes(self, codebase_model: CodebaseModel):
        """Create lint error nodes and their relationships."""
        for error_entity in codebase_model.lint_errors:
            error_node = error_entity.to_graph_node()
            
            # Create lint error node
            result = self.neo4j_client.run_query(
                queries.CREATE_LINT_ERROR_NODE,
                error_node.properties
            )
            
            if result:
                # Try to link error to method or function
                self._link_error_to_code_entity(error_entity, codebase_model)
                
                logger.debug(f"Created lint error node: {error_entity.error_type}")
    
    def _link_error_to_code_entity(self, error_entity: LintErrorEntity, codebase_model: CodebaseModel):
        """Link a lint error to the appropriate method or function."""
        file_entity = codebase_model.get_file(error_entity.file_path)
        if not file_entity:
            return
        
        # Find the method or function that contains this error line
        target_entity = self._find_containing_entity(error_entity.line, file_entity)
        
        if target_entity:
            if isinstance(target_entity, MethodEntity):
                self.neo4j_client.run_query(
                    queries.CREATE_METHOD_HAS_ERROR,
                    {
                        "method_name": target_entity.name,
                        "method_line_start": target_entity.location.line_start,
                        "error_line": error_entity.line,
                        "error_type": error_entity.error_type,
                        "error_message": error_entity.message
                    }
                )
            elif isinstance(target_entity, FunctionEntity):
                self.neo4j_client.run_query(
                    queries.CREATE_FUNCTION_HAS_ERROR,
                    {
                        "function_name": target_entity.name,
                        "function_line_start": target_entity.location.line_start,
                        "error_line": error_entity.line,
                        "error_type": error_entity.error_type,
                        "error_message": error_entity.message
                    }
                )
    
    def _find_containing_entity(self, line: int, file_entity: FileEntity) -> Optional[FunctionEntity]:
        """Find the function or method that contains the given line number."""
        # Check functions first
        for function_entity in file_entity.functions:
            if (function_entity.location.line_start <= line <= function_entity.location.line_end):
                return function_entity
        
        # Check methods in classes
        for class_entity in file_entity.classes:
            for method_entity in class_entity.methods:
                if (method_entity.location.line_start <= line <= method_entity.location.line_end):
                    return method_entity
        
        return None
    
    def _create_call_relationships(self, codebase_model: CodebaseModel):
        """Create call relationships between functions and methods."""
        for relationship in codebase_model.call_relationships:
            # Find caller and callee entities
            caller_entity = self._find_entity_by_name(relationship.caller, codebase_model)
            callee_entity = self._find_entity_by_name(relationship.callee, codebase_model)
            
            if caller_entity and callee_entity:
                self._create_call_relationship(caller_entity, callee_entity)
    
    def _find_entity_by_name(self, name: str, codebase_model: CodebaseModel) -> Optional[FunctionEntity]:
        """Find a function or method by name."""
        # This is a simplified implementation - in practice, you'd need more sophisticated matching
        for file_entity in codebase_model.files.values():
            # Check functions
            for function_entity in file_entity.functions:
                if function_entity.name == name:
                    return function_entity
            
            # Check methods
            for class_entity in file_entity.classes:
                for method_entity in class_entity.methods:
                    if method_entity.name == name:
                        return method_entity
        
        return None
    
    def _create_call_relationship(self, caller: FunctionEntity, callee: FunctionEntity):
        """Create a call relationship between two entities."""
        if isinstance(caller, MethodEntity) and isinstance(callee, MethodEntity):
            query = queries.CREATE_METHOD_CALLS_METHOD
        elif isinstance(caller, MethodEntity) and isinstance(callee, FunctionEntity):
            query = queries.CREATE_METHOD_CALLS_FUNCTION
        elif isinstance(caller, FunctionEntity) and isinstance(callee, MethodEntity):
            query = queries.CREATE_FUNCTION_CALLS_METHOD
        else:  # Both are functions
            query = queries.CREATE_FUNCTION_CALLS_FUNCTION
        
        self.neo4j_client.run_query(
            query,
            {
                "caller_name": caller.name,
                "caller_line_start": caller.location.line_start,
                "callee_name": callee.name,
                "callee_line_start": callee.location.line_start
            }
        )
    
    def clear_graph(self):
        """Clear all nodes from the graph."""
        self.neo4j_client.run_query(queries.DELETE_ALL_NODES)
        self.created_nodes.clear()
        self.created_relationships.clear()
        logger.info("Graph cleared")
    
    def get_graph_stats(self) -> Dict[str, int]:
        """Get statistics about the created graph."""
        return {
            "nodes": len(self.created_nodes),
            "relationships": len(self.created_relationships)
        }