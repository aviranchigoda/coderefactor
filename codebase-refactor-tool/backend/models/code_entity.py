"""
Code entity models that represent parsed code structures.
These models bridge the gap between AST parsing and graph nodes.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from pathlib import Path
from .graph_node import FileNode, ClassNode, MethodNode, FunctionNode, LintErrorNode, Severity


@dataclass
class CodeLocation:
    """Represents a location in source code."""
    line_start: int
    line_end: int
    column_start: Optional[int] = None
    column_end: Optional[int] = None


@dataclass
class Parameter:
    """Represents a function/method parameter."""
    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None


@dataclass
class CodeEntity:
    """Base class for all code entities."""
    name: str
    location: CodeLocation
    file_path: str
    
    def get_unique_id(self) -> str:
        """Generate a unique identifier for this entity."""
        return f"{self.file_path}:{self.name}:{self.location.line_start}"


@dataclass
class FileEntity(CodeEntity):
    """Represents a source code file."""
    extension: str
    size: int
    classes: List['ClassEntity'] = field(default_factory=list)
    functions: List['FunctionEntity'] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    
    def __init__(self, file_path: str, size: int):
        path_obj = Path(file_path)
        super().__init__(
            name=path_obj.name,
            location=CodeLocation(1, 1),  # Files span entire content
            file_path=file_path
        )
        self.extension = path_obj.suffix
        self.size = size
        self.classes = []
        self.functions = []
        self.imports = []
    
    def add_class(self, class_entity: 'ClassEntity'):
        """Add a class to this file."""
        self.classes.append(class_entity)
    
    def add_function(self, function_entity: 'FunctionEntity'):
        """Add a function to this file."""
        self.functions.append(function_entity)
    
    def to_graph_node(self) -> FileNode:
        """Convert to graph node."""
        return FileNode(
            path=self.file_path,
            name=self.name,
            extension=self.extension,
            size=self.size
        )


@dataclass
class ClassEntity(CodeEntity):
    """Represents a class definition."""
    methods: List['MethodEntity'] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    
    def add_method(self, method_entity: 'MethodEntity'):
        """Add a method to this class."""
        self.methods.append(method_entity)
    
    def to_graph_node(self) -> ClassNode:
        """Convert to graph node."""
        return ClassNode(
            name=self.name,
            line_start=self.location.line_start,
            line_end=self.location.line_end
        )


@dataclass
class FunctionEntity(CodeEntity):
    """Represents a function definition."""
    parameters: List[Parameter] = field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    calls: Set[str] = field(default_factory=set)
    is_async: bool = False
    
    def add_call(self, called_function: str):
        """Add a function call."""
        self.calls.add(called_function)
    
    def get_parameter_names(self) -> List[str]:
        """Get list of parameter names."""
        return [param.name for param in self.parameters]
    
    def to_graph_node(self) -> FunctionNode:
        """Convert to graph node."""
        return FunctionNode(
            name=self.name,
            parameters=self.get_parameter_names(),
            return_type=self.return_type,
            line_start=self.location.line_start,
            line_end=self.location.line_end
        )


@dataclass
class MethodEntity(FunctionEntity):
    """Represents a method definition (function within a class)."""
    class_name: str
    is_static: bool = False
    is_classmethod: bool = False
    is_property: bool = False
    visibility: str = "public"  # public, private, protected
    
    def to_graph_node(self) -> MethodNode:
        """Convert to graph node."""
        return MethodNode(
            name=self.name,
            parameters=self.get_parameter_names(),
            return_type=self.return_type,
            line_start=self.location.line_start,
            line_end=self.location.line_end
        )


@dataclass
class LintErrorEntity:
    """Represents a linting error."""
    file_path: str
    line: int
    column: Optional[int]
    error_type: str
    message: str
    severity: Severity
    rule_id: Optional[str] = None
    
    def to_graph_node(self) -> LintErrorNode:
        """Convert to graph node."""
        return LintErrorNode(
            type=self.error_type,
            message=self.message,
            severity=self.severity,
            line=self.line
        )


@dataclass
class CallRelationship:
    """Represents a call relationship between functions/methods."""
    caller: str  # Function/method name that makes the call
    callee: str  # Function/method name that is called
    caller_line: int
    call_line: int


@dataclass
class CodebaseModel:
    """Represents the entire codebase structure."""
    files: Dict[str, FileEntity] = field(default_factory=dict)
    lint_errors: List[LintErrorEntity] = field(default_factory=list)
    call_relationships: List[CallRelationship] = field(default_factory=list)
    
    def add_file(self, file_entity: FileEntity):
        """Add a file to the codebase."""
        self.files[file_entity.file_path] = file_entity
    
    def add_lint_error(self, error: LintErrorEntity):
        """Add a lint error to the codebase."""
        self.lint_errors.append(error)
    
    def add_call_relationship(self, relationship: CallRelationship):
        """Add a call relationship."""
        self.call_relationships.append(relationship)
    
    def get_file(self, file_path: str) -> Optional[FileEntity]:
        """Get a file by path."""
        return self.files.get(file_path)
    
    def get_all_classes(self) -> List[ClassEntity]:
        """Get all classes across all files."""
        classes = []
        for file_entity in self.files.values():
            classes.extend(file_entity.classes)
        return classes
    
    def get_all_functions(self) -> List[FunctionEntity]:
        """Get all functions across all files."""
        functions = []
        for file_entity in self.files.values():
            functions.extend(file_entity.functions)
            for class_entity in file_entity.classes:
                functions.extend(class_entity.methods)
        return functions
    
    def get_errors_for_file(self, file_path: str) -> List[LintErrorEntity]:
        """Get all lint errors for a specific file."""
        return [error for error in self.lint_errors if error.file_path == file_path]
    
    def get_stats(self) -> Dict[str, int]:
        """Get codebase statistics."""
        total_classes = len(self.get_all_classes())
        total_functions = len(self.get_all_functions())
        total_errors = len(self.lint_errors)
        
        return {
            "files": len(self.files),
            "classes": total_classes,
            "functions": total_functions,
            "errors": total_errors,
            "calls": len(self.call_relationships)
        }