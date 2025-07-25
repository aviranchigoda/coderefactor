"""
Python AST parser for extracting code structure.
"""

import ast
import os
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path
import logging

from ..models.code_entity import (
    FileEntity, ClassEntity, FunctionEntity, MethodEntity,
    Parameter, CodeLocation, CallRelationship
)
from .base_parser import BaseParser

logger = logging.getLogger(__name__)


class PythonParser(BaseParser):
    """Parser for Python source files using the built-in AST module."""
    
    def __init__(self):
        super().__init__()
        self.current_class = None
        self.current_function = None
        self.call_stack = []
        self.imports = {}  # Maps imported names to their modules
        
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the file."""
        return file_path.endswith(('.py', '.pyw'))
    
    def parse_file(self, file_path: str) -> Optional[FileEntity]:
        """Parse a Python file and extract its structure."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Create file entity
            file_entity = FileEntity(file_path, file_size)
            
            # Parse the AST
            tree = ast.parse(content, filename=file_path)
            
            # Visit all nodes
            visitor = PythonASTVisitor(file_entity, content)
            visitor.visit(tree)
            
            # Extract imports
            file_entity.imports = visitor.imports
            
            logger.info(f"Successfully parsed Python file: {file_path}")
            return file_entity
            
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            # Still create a file entity but mark it as having errors
            file_entity = FileEntity(file_path, 0)
            return file_entity
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None


class PythonASTVisitor(ast.NodeVisitor):
    """AST visitor that extracts code entities from Python AST."""
    
    def __init__(self, file_entity: FileEntity, source_code: str):
        self.file_entity = file_entity
        self.source_lines = source_code.splitlines()
        self.current_class = None
        self.current_function = None
        self.imports = []
        self.name_to_module = {}  # For resolving function calls
        self.call_relationships = []
        
    def visit_Import(self, node: ast.Import):
        """Handle import statements."""
        for alias in node.names:
            import_name = alias.name
            as_name = alias.asname or alias.name
            self.imports.append(import_name)
            self.name_to_module[as_name] = import_name
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Handle from ... import statements."""
        module = node.module or ''
        level = '.' * node.level + module
        
        for alias in node.names:
            if alias.name == '*':
                self.imports.append(f"from {level} import *")
            else:
                import_name = f"{level}.{alias.name}"
                as_name = alias.asname or alias.name
                self.imports.append(f"from {level} import {alias.name}")
                self.name_to_module[as_name] = import_name
        
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition."""
        # Extract class information
        location = CodeLocation(
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            column_start=node.col_offset,
            column_end=node.end_col_offset
        )
        
        class_entity = ClassEntity(
            name=node.name,
            location=location,
            file_path=self.file_entity.file_path
        )
        
        # Extract base classes
        for base in node.bases:
            base_name = self._get_name_from_node(base)
            if base_name:
                class_entity.base_classes.append(base_name)
        
        # Extract decorators
        for decorator in node.decorator_list:
            decorator_name = self._get_name_from_node(decorator)
            if decorator_name:
                class_entity.decorators.append(decorator_name)
        
        # Extract docstring
        class_entity.docstring = ast.get_docstring(node)
        
        # Add to file
        self.file_entity.add_class(class_entity)
        
        # Visit class body
        old_class = self.current_class
        self.current_class = class_entity
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition."""
        self._visit_function_def(node, is_async=False)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition."""
        self._visit_function_def(node, is_async=True)
    
    def _visit_function_def(self, node, is_async: bool):
        """Common logic for function and async function definitions."""
        location = CodeLocation(
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            column_start=node.col_offset,
            column_end=node.end_col_offset
        )
        
        # Extract parameters
        parameters = self._extract_parameters(node.args)
        
        # Extract return type annotation
        return_type = None
        if node.returns:
            return_type = self._get_annotation_string(node.returns)
        
        # Determine if it's a method or function
        if self.current_class:
            # It's a method
            method_entity = MethodEntity(
                name=node.name,
                location=location,
                file_path=self.file_entity.file_path,
                class_name=self.current_class.name,
                parameters=parameters,
                return_type=return_type,
                is_async=is_async
            )
            
            # Check for special method types
            if node.decorator_list:
                decorator_names = [self._get_name_from_node(d) for d in node.decorator_list]
                method_entity.is_static = 'staticmethod' in decorator_names
                method_entity.is_classmethod = 'classmethod' in decorator_names
                method_entity.is_property = 'property' in decorator_names
                method_entity.decorators = [d for d in decorator_names if d]
            
            # Determine visibility
            if node.name.startswith('__') and not node.name.endswith('__'):
                method_entity.visibility = 'private'
            elif node.name.startswith('_'):
                method_entity.visibility = 'protected'
            
            method_entity.docstring = ast.get_docstring(node)
            self.current_class.add_method(method_entity)
            
            # Track current function for call analysis
            old_function = self.current_function
            self.current_function = method_entity
            self.generic_visit(node)
            self.current_function = old_function
            
        else:
            # It's a standalone function
            function_entity = FunctionEntity(
                name=node.name,
                location=location,
                file_path=self.file_entity.file_path,
                parameters=parameters,
                return_type=return_type,
                is_async=is_async
            )
            
            # Extract decorators
            for decorator in node.decorator_list:
                decorator_name = self._get_name_from_node(decorator)
                if decorator_name:
                    function_entity.decorators.append(decorator_name)
            
            function_entity.docstring = ast.get_docstring(node)
            self.file_entity.add_function(function_entity)
            
            # Track current function for call analysis
            old_function = self.current_function
            self.current_function = function_entity
            self.generic_visit(node)
            self.current_function = old_function
    
    def visit_Call(self, node: ast.Call):
        """Visit function/method calls to track relationships."""
        if self.current_function:
            call_name = self._get_call_name(node.func)
            if call_name:
                self.current_function.add_call(call_name)
                
                # Create call relationship
                relationship = CallRelationship(
                    caller=self.current_function.name,
                    callee=call_name,
                    caller_line=self.current_function.location.line_start,
                    call_line=node.lineno
                )
                self.call_relationships.append(relationship)
        
        self.generic_visit(node)
    
    def _extract_parameters(self, args: ast.arguments) -> List[Parameter]:
        """Extract parameters from function arguments."""
        parameters = []
        
        # Regular arguments
        defaults_start = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            param = Parameter(name=arg.arg)
            
            # Type annotation
            if arg.annotation:
                param.type_annotation = self._get_annotation_string(arg.annotation)
            
            # Default value
            if i >= defaults_start:
                default_idx = i - defaults_start
                param.default_value = self._get_default_string(args.defaults[default_idx])
            
            parameters.append(param)
        
        # *args
        if args.vararg:
            param = Parameter(name=f"*{args.vararg.arg}")
            if args.vararg.annotation:
                param.type_annotation = self._get_annotation_string(args.vararg.annotation)
            parameters.append(param)
        
        # **kwargs
        if args.kwarg:
            param = Parameter(name=f"**{args.kwarg.arg}")
            if args.kwarg.annotation:
                param.type_annotation = self._get_annotation_string(args.kwarg.annotation)
            parameters.append(param)
        
        return parameters
    
    def _get_name_from_node(self, node: ast.AST) -> Optional[str]:
        """Extract name from various AST node types."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._get_name_from_node(node.value)
            if base:
                return f"{base}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_name_from_node(node.func)
        elif isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        elif isinstance(node, ast.Constant):  # Python >= 3.8
            return str(node.value)
        return None
    
    def _get_call_name(self, node: ast.AST) -> Optional[str]:
        """Extract the name of a called function/method."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # For method calls like obj.method()
            return node.attr
        return None
    
    def _get_annotation_string(self, node: ast.AST) -> str:
        """Convert type annotation to string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Str):  # Python < 3.8
            return repr(node.s)
        elif isinstance(node, ast.Subscript):
            base = self._get_annotation_string(node.value)
            if isinstance(node.slice, ast.Index):  # Python < 3.9
                index = self._get_annotation_string(node.slice.value)
            else:  # Python >= 3.9
                index = self._get_annotation_string(node.slice)
            return f"{base}[{index}]"
        elif isinstance(node, ast.Tuple):
            elements = [self._get_annotation_string(e) for e in node.elts]
            return f"({', '.join(elements)})"
        elif isinstance(node, ast.List):
            elements = [self._get_annotation_string(e) for e in node.elts]
            return f"[{', '.join(elements)}]"
        elif isinstance(node, ast.Attribute):
            base = self._get_annotation_string(node.value)
            return f"{base}.{node.attr}"
        else:
            # Fallback to ast.unparse if available (Python 3.9+)
            try:
                return ast.unparse(node)
            except AttributeError:
                return str(node.__class__.__name__)
    
    def _get_default_string(self, node: ast.AST) -> str:
        """Convert default value to string."""
        if isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            # Handle negative numbers
            if isinstance(node.operand, ast.Constant):
                return f"-{node.operand.value}"
        else:
            # Fallback to ast.unparse if available
            try:
                return ast.unparse(node)
            except AttributeError:
                return "..."


# Export the parser
parser = PythonParser()