"""
Base parser interface for all language parsers.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

from ..models.code_entity import FileEntity, LintErrorEntity
from ..models.graph_node import Severity

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Abstract base class for all language parsers."""
    
    def __init__(self):
        self.supported_extensions = []
        self.lint_errors = []
        
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """
        Check if this parser can handle the given file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if this parser can handle the file
        """
        pass
    
    @abstractmethod
    def parse_file(self, file_path: str) -> Optional[FileEntity]:
        """
        Parse a file and extract its code structure.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            FileEntity containing the parsed structure, or None on error
        """
        pass
    
    def extract_imports(self, file_entity: FileEntity) -> List[str]:
        """
        Extract import statements from the file.
        
        Args:
            file_entity: The parsed file entity
            
        Returns:
            List of import statements
        """
        return file_entity.imports
    
    def add_lint_error(self, file_path: str, line: int, column: int, 
                      error_type: str, message: str, severity: Severity):
        """
        Add a lint error found during parsing.
        
        Args:
            file_path: Path to the file
            line: Line number of the error
            column: Column number of the error
            error_type: Type of error (e.g., "SyntaxError")
            message: Error message
            severity: Severity level
        """
        error = LintErrorEntity(
            file_path=file_path,
            line=line,
            column=column,
            error_type=error_type,
            message=message,
            severity=severity
        )
        self.lint_errors.append(error)
    
    def get_lint_errors(self) -> List[LintErrorEntity]:
        """Get all lint errors found during parsing."""
        return self.lint_errors
    
    def clear_lint_errors(self):
        """Clear the lint errors list."""
        self.lint_errors.clear()
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic file information.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file information
        """
        path = Path(file_path)
        return {
            'name': path.name,
            'extension': path.suffix,
            'size': path.stat().st_size if path.exists() else 0,
            'path': str(path.absolute())
        }


class ParserRegistry:
    """Registry for managing multiple language parsers."""
    
    def __init__(self):
        self.parsers: List[BaseParser] = []
        self._initialize_parsers()
    
    def _initialize_parsers(self):
        """Initialize all available parsers."""
        # Import and register parsers
        try:
            from .python_parser import parser as python_parser
            self.register_parser(python_parser)
        except ImportError:
            logger.warning("Python parser not available")
        
        try:
            from .javascript_parser import parser as javascript_parser
            self.register_parser(javascript_parser)
        except ImportError:
            logger.warning("JavaScript parser not available")
        
        try:
            from .java_parser import parser as java_parser
            self.register_parser(java_parser)
        except ImportError:
            logger.warning("Java parser not available")
        
        try:
            from .cpp_parser import parser as cpp_parser
            self.register_parser(cpp_parser)
        except ImportError:
            logger.warning("C++ parser not available")
        
        try:
            from .csharp_parser import parser as csharp_parser
            self.register_parser(csharp_parser)
        except ImportError:
            logger.warning("C# parser not available")
    
    def register_parser(self, parser: BaseParser):
        """Register a new parser."""
        self.parsers.append(parser)
        logger.info(f"Registered parser: {parser.__class__.__name__}")
    
    def get_parser_for_file(self, file_path: str) -> Optional[BaseParser]:
        """
        Get the appropriate parser for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Appropriate parser or None if no parser can handle the file
        """
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser
        return None
    
    def parse_file(self, file_path: str) -> Optional[FileEntity]:
        """
        Parse a file using the appropriate parser.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Parsed FileEntity or None on error
        """
        parser = self.get_parser_for_file(file_path)
        if parser:
            logger.info(f"Parsing {file_path} with {parser.__class__.__name__}")
            return parser.parse_file(file_path)
        else:
            logger.warning(f"No parser available for {file_path}")
            return None
    
    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        extensions = set()
        for parser in self.parsers:
            extensions.update(parser.supported_extensions)
        return sorted(list(extensions))


# Global parser registry
registry = ParserRegistry()