"""
Main CodebaseAnalyzer that orchestrates parsing, graph building, and analysis.
"""

import os
import logging
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path
import fnmatch
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models.code_entity import CodebaseModel, FileEntity, CallRelationship
from ..models.graph_node import Severity
from ..parsers.base_parser import ParserRegistry
from ..graph.neo4j_client import Neo4jClient
from ..core.graph_builder import GraphBuilder
from ..linters.base_linter import LinterRegistry
from ..utils.file_utils import FileScanner
from ..utils.cache import CacheManager

logger = logging.getLogger(__name__)


class CodebaseAnalyzer:
    """Main analyzer that coordinates parsing, linting, and graph building."""
    
    def __init__(self, neo4j_client: Neo4jClient, config: Dict = None):
        self.neo4j_client = neo4j_client
        self.config = config or {}
        
        # Initialize components
        self.parser_registry = ParserRegistry()
        self.linter_registry = LinterRegistry()
        self.graph_builder = GraphBuilder(neo4j_client)
        self.file_scanner = FileScanner()
        self.cache_manager = CacheManager()
        
        # Analysis state
        self.codebase_model = CodebaseModel()
        self.analysis_stats = {
            'files_scanned': 0,
            'files_parsed': 0,
            'files_failed': 0,
            'parse_time': 0,
            'lint_time': 0,
            'graph_time': 0,
            'total_time': 0
        }
        
        # Configuration
        self.max_workers = self.config.get('max_workers', 4)
        self.ignore_patterns = self.config.get('ignore_patterns', self._default_ignore_patterns())
        self.file_extensions = self.config.get('file_extensions', self._default_extensions())
        
    def analyze_codebase(self, root_path: str, options: Dict = None) -> Dict:
        """
        Analyze entire codebase starting from root path.
        
        Args:
            root_path: Root directory of the codebase
            options: Analysis options (e.g., enable_linting, clear_graph)
            
        Returns:
            Analysis results and statistics
        """
        start_time = time.time()
        options = options or {}
        
        logger.info(f"Starting codebase analysis from: {root_path}")
        
        # Reset state
        self.codebase_model = CodebaseModel()
        self.analysis_stats = {
            'files_scanned': 0,
            'files_parsed': 0,
            'files_failed': 0,
            'parse_time': 0,
            'lint_time': 0,
            'graph_time': 0,
            'total_time': 0
        }
        
        try:
            # Step 1: Scan file system
            logger.info("Scanning file system...")
            file_paths = self._scan_files(root_path)
            self.analysis_stats['files_scanned'] = len(file_paths)
            
            # Step 2: Parse files
            logger.info(f"Parsing {len(file_paths)} files...")
            parse_start = time.time()
            self._parse_files(file_paths)
            self.analysis_stats['parse_time'] = time.time() - parse_start
            
            # Step 3: Run linters (optional)
            if options.get('enable_linting', True):
                logger.info("Running linters...")
                lint_start = time.time()
                self._run_linters()
                self.analysis_stats['lint_time'] = time.time() - lint_start
            
            # Step 4: Build graph
            if options.get('clear_graph', False):
                logger.info("Clearing existing graph...")
                self.graph_builder.clear_graph()
            
            logger.info("Building graph...")
            graph_start = time.time()
            success = self.graph_builder.build_graph(self.codebase_model)
            self.analysis_stats['graph_time'] = time.time() - graph_start
            
            if not success:
                logger.error("Failed to build graph")
                return {'error': 'Graph building failed', 'stats': self.analysis_stats}
            
            # Step 5: Post-analysis
            self._analyze_relationships()
            
            self.analysis_stats['total_time'] = time.time() - start_time
            
            # Get final statistics
            codebase_stats = self.codebase_model.get_stats()
            graph_stats = self.neo4j_client.get_database_stats()
            
            return {
                'success': True,
                'stats': {
                    **self.analysis_stats,
                    **codebase_stats,
                    'graph': graph_stats
                }
            }
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {
                'error': str(e),
                'stats': self.analysis_stats
            }
    
    def _scan_files(self, root_path: str) -> List[str]:
        """Scan file system and return list of files to parse."""
        file_paths = []
        
        for root, dirs, files in os.walk(root_path):
            # Remove ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(root, d))]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check if file should be ignored
                if self._should_ignore(file_path):
                    continue
                
                # Check if file has supported extension
                if any(file_path.endswith(ext) for ext in self.file_extensions):
                    file_paths.append(file_path)
        
        return file_paths
    
    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored based on patterns."""
        path_parts = Path(path).parts
        
        for pattern in self.ignore_patterns:
            # Check against full path
            if fnmatch.fnmatch(path, pattern):
                return True
            
            # Check against individual path components
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        
        return False
    
    def _parse_files(self, file_paths: List[str]):
        """Parse files in parallel."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit parsing tasks
            future_to_path = {
                executor.submit(self._parse_single_file, path): path 
                for path in file_paths
            }
            
            # Process results as they complete
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    file_entity = future.result()
                    if file_entity:
                        self.codebase_model.add_file(file_entity)
                        self.analysis_stats['files_parsed'] += 1
                    else:
                        self.analysis_stats['files_failed'] += 1
                except Exception as e:
                    logger.error(f"Failed to parse {path}: {e}")
                    self.analysis_stats['files_failed'] += 1
    
    def _parse_single_file(self, file_path: str) -> Optional[FileEntity]:
        """Parse a single file."""
        # Check cache first
        cached_entity = self.cache_manager.get_cached_parse(file_path)
        if cached_entity:
            logger.debug(f"Using cached parse for {file_path}")
            return cached_entity
        
        # Parse file
        parser = self.parser_registry.get_parser_for_file(file_path)
        if not parser:
            logger.warning(f"No parser for {file_path}")
            return None
        
        try:
            file_entity = parser.parse_file(file_path)
            
            if file_entity:
                # Cache the result
                self.cache_manager.cache_parse(file_path, file_entity)
                
                # Add any parse errors as lint errors
                for error in parser.get_lint_errors():
                    self.codebase_model.add_lint_error(error)
                
                parser.clear_lint_errors()
            
            return file_entity
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None
    
    def _run_linters(self):
        """Run linters on all parsed files."""
        for file_path, file_entity in self.codebase_model.files.items():
            linter = self.linter_registry.get_linter_for_file(file_path)
            if linter:
                try:
                    errors = linter.lint_file(file_path)
                    for error in errors:
                        self.codebase_model.add_lint_error(error)
                except Exception as e:
                    logger.error(f"Linting failed for {file_path}: {e}")
    
    def _analyze_relationships(self):
        """Analyze and resolve call relationships between functions."""
        # This is a simplified version - in practice, you'd need more sophisticated
        # name resolution considering imports, scopes, etc.
        
        logger.info("Analyzing call relationships...")
        
        # Build a map of all functions/methods by name
        name_to_entities = {}
        
        for file_entity in self.codebase_model.files.values():
            # Add standalone functions
            for func in file_entity.functions:
                name = func.name
                if name not in name_to_entities:
                    name_to_entities[name] = []
                name_to_entities[name].append(func)
            
            # Add methods
            for class_entity in file_entity.classes:
                for method in class_entity.methods:
                    # Use qualified name for methods
                    qualified_name = f"{class_entity.name}.{method.name}"
                    if qualified_name not in name_to_entities:
                        name_to_entities[qualified_name] = []
                    name_to_entities[qualified_name].append(method)
                    
                    # Also add unqualified name for local resolution
                    if method.name not in name_to_entities:
                        name_to_entities[method.name] = []
                    name_to_entities[method.name].append(method)
        
        # Analyze calls and create relationships
        for file_entity in self.codebase_model.files.values():
            self._analyze_file_calls(file_entity, name_to_entities)
    
    def _analyze_file_calls(self, file_entity: FileEntity, name_to_entities: Dict):
        """Analyze calls within a specific file."""
        all_functions = []
        
        # Collect all functions and methods in this file
        all_functions.extend(file_entity.functions)
        for class_entity in file_entity.classes:
            all_functions.extend(class_entity.methods)
        
        # Analyze calls for each function
        for func in all_functions:
            for called_name in func.calls:
                # Try to resolve the call
                if called_name in name_to_entities:
                    target_entities = name_to_entities[called_name]
                    
                    # For simplicity, create relationship with first match
                    # In practice, you'd need scope analysis
                    if target_entities:
                        target = target_entities[0]
                        relationship = CallRelationship(
                            caller=func.name,
                            callee=target.name,
                            caller_line=func.location.line_start,
                            call_line=func.location.line_start  # Simplified
                        )
                        self.codebase_model.add_call_relationship(relationship)
    
    def _default_ignore_patterns(self) -> List[str]:
        """Get default ignore patterns."""
        return [
            '.*',           # Hidden files/dirs
            '__pycache__',  # Python cache
            '*.pyc',        # Python bytecode
            '*.pyo',        # Python optimized
            'node_modules', # Node.js
            'dist',         # Distribution
            'build',        # Build output
            '*.egg-info',   # Python eggs
            '.git',         # Git
            '.svn',         # SVN
            '.hg',          # Mercurial
            'venv',         # Virtual env
            'env',          # Environment
            '.env',         # Environment files
            'coverage',     # Coverage reports
            '.coverage',    # Coverage data
            '*.log',        # Log files
            '*.tmp',        # Temporary files
            '*.temp',       # Temporary files
        ]
    
    def _default_extensions(self) -> List[str]:
        """Get default file extensions to parse."""
        return [
            '.py',    # Python
            '.pyw',   # Python Windows
            '.js',    # JavaScript
            '.jsx',   # React JSX
            '.ts',    # TypeScript
            '.tsx',   # TypeScript JSX
            '.java',  # Java
            '.cpp',   # C++
            '.cxx',   # C++
            '.cc',    # C++
            '.c',     # C
            '.h',     # C/C++ header
            '.hpp',   # C++ header
            '.cs',    # C#
            '.go',    # Go
            '.rs',    # Rust
            '.php',   # PHP
            '.rb',    # Ruby
            '.swift', # Swift
            '.kt',    # Kotlin
            '.scala', # Scala
        ]
    
    def get_project_stats(self) -> Dict:
        """Get current project statistics."""
        return {
            'analysis': self.analysis_stats,
            'codebase': self.codebase_model.get_stats(),
            'graph': self.neo4j_client.get_database_stats() if self.neo4j_client.is_connected() else {}
        }
    
    def analyze_single_file(self, file_path: str) -> Optional[FileEntity]:
        """Analyze a single file without affecting the main codebase model."""
        parser = self.parser_registry.get_parser_for_file(file_path)
        if parser:
            return parser.parse_file(file_path)
        return None
    
    def get_file_analysis(self, file_path: str) -> Dict:
        """Get detailed analysis for a specific file."""
        file_entity = self.codebase_model.get_file(file_path)
        if not file_entity:
            return {'error': 'File not found in analysis'}
        
        # Get lint errors for this file
        errors = self.codebase_model.get_errors_for_file(file_path)
        
        return {
            'file': {
                'path': file_entity.file_path,
                'name': file_entity.name,
                'size': file_entity.size,
                'classes': len(file_entity.classes),
                'functions': len(file_entity.functions),
                'imports': len(file_entity.imports)
            },
            'classes': [
                {
                    'name': cls.name,
                    'line_start': cls.location.line_start,
                    'line_end': cls.location.line_end,
                    'methods': len(cls.methods),
                    'base_classes': cls.base_classes
                }
                for cls in file_entity.classes
            ],
            'functions': [
                {
                    'name': func.name,
                    'line_start': func.location.line_start,
                    'line_end': func.location.line_end,
                    'parameters': len(func.parameters),
                    'calls': len(func.calls)
                }
                for func in file_entity.functions
            ],
            'errors': [
                {
                    'line': error.line,
                    'type': error.error_type,
                    'message': error.message,
                    'severity': error.severity.value
                }
                for error in errors
            ]
        }
    
    def clear_analysis(self):
        """Clear all analysis data."""
        self.codebase_model = CodebaseModel()
        self.cache_manager.clear_cache()
        logger.info("Analysis data cleared")