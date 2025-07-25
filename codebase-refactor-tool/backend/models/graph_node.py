"""
Graph node models for Neo4j database operations.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum


class NodeType(Enum):
    FILE = "File"
    CLASS = "Class"
    METHOD = "Method"
    FUNCTION = "Function"
    LINT_ERROR = "LintError"


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class GraphNode:
    """Base class for all graph nodes."""
    node_type: NodeType
    properties: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary for Neo4j operations."""
        return {
            "type": self.node_type.value,
            **self.properties
        }


@dataclass
class FileNode(GraphNode):
    """Represents a file in the codebase."""
    path: str
    name: str
    extension: str
    size: int
    
    def __init__(self, path: str, name: str, extension: str, size: int):
        self.path = path
        self.name = name
        self.extension = extension
        self.size = size
        super().__init__(
            node_type=NodeType.FILE,
            properties={
                "path": path,
                "name": name,
                "extension": extension,
                "size": size
            }
        )


@dataclass
class ClassNode(GraphNode):
    """Represents a class definition."""
    name: str
    line_start: int
    line_end: int
    
    def __init__(self, name: str, line_start: int, line_end: int):
        self.name = name
        self.line_start = line_start
        self.line_end = line_end
        super().__init__(
            node_type=NodeType.CLASS,
            properties={
                "name": name,
                "line_start": line_start,
                "line_end": line_end
            }
        )


@dataclass
class MethodNode(GraphNode):
    """Represents a method definition."""
    name: str
    parameters: List[str]
    return_type: Optional[str]
    line_start: int
    line_end: int
    
    def __init__(self, name: str, parameters: List[str], return_type: Optional[str], 
                 line_start: int, line_end: int):
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.line_start = line_start
        self.line_end = line_end
        super().__init__(
            node_type=NodeType.METHOD,
            properties={
                "name": name,
                "parameters": parameters,
                "return_type": return_type,
                "line_start": line_start,
                "line_end": line_end
            }
        )


@dataclass
class FunctionNode(GraphNode):
    """Represents a function definition."""
    name: str
    parameters: List[str]
    return_type: Optional[str]
    line_start: int
    line_end: int
    
    def __init__(self, name: str, parameters: List[str], return_type: Optional[str],
                 line_start: int, line_end: int):
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.line_start = line_start
        self.line_end = line_end
        super().__init__(
            node_type=NodeType.FUNCTION,
            properties={
                "name": name,
                "parameters": parameters,
                "return_type": return_type,
                "line_start": line_start,
                "line_end": line_end
            }
        )


@dataclass
class LintErrorNode(GraphNode):
    """Represents a linting error."""
    type: str
    message: str
    severity: Severity
    line: int
    
    def __init__(self, type: str, message: str, severity: Severity, line: int):
        self.type = type
        self.message = message
        self.severity = severity
        self.line = line
        super().__init__(
            node_type=NodeType.LINT_ERROR,
            properties={
                "type": type,
                "message": message,
                "severity": severity.value,
                "line": line
            }
        )


class RelationshipType(Enum):
    CONTAINS = "CONTAINS"
    HAS_METHOD = "HAS_METHOD"
    CALLS = "CALLS"
    HAS_ERROR = "HAS_ERROR"


@dataclass
class GraphRelationship:
    """Represents a relationship between two nodes."""
    source_node: GraphNode
    target_node: GraphNode
    relationship_type: RelationshipType
    properties: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary for Neo4j operations."""
        result = {
            "type": self.relationship_type.value,
            "source": self.source_node.to_dict(),
            "target": self.target_node.to_dict()
        }
        if self.properties:
            result["properties"] = self.properties
        return result


def create_file_node(path: str, name: str, extension: str, size: int) -> FileNode:
    """Factory function to create a FileNode."""
    return FileNode(path, name, extension, size)


def create_class_node(name: str, line_start: int, line_end: int) -> ClassNode:
    """Factory function to create a ClassNode."""
    return ClassNode(name, line_start, line_end)


def create_method_node(name: str, parameters: List[str], return_type: Optional[str],
                      line_start: int, line_end: int) -> MethodNode:
    """Factory function to create a MethodNode."""
    return MethodNode(name, parameters, return_type, line_start, line_end)


def create_function_node(name: str, parameters: List[str], return_type: Optional[str],
                        line_start: int, line_end: int) -> FunctionNode:
    """Factory function to create a FunctionNode."""
    return FunctionNode(name, parameters, return_type, line_start, line_end)


def create_lint_error_node(type: str, message: str, severity: Severity, line: int) -> LintErrorNode:
    """Factory function to create a LintErrorNode."""
    return LintErrorNode(type, message, severity, line)


def create_relationship(source: GraphNode, target: GraphNode, 
                       rel_type: RelationshipType, 
                       properties: Optional[Dict[str, Any]] = None) -> GraphRelationship:
    """Factory function to create a GraphRelationship."""
    return GraphRelationship(source, target, rel_type, properties)