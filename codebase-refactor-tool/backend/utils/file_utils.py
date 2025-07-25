"""
File system utilities for the codebase analyzer.
"""

import os
import fnmatch
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class FileScanner:
    """Utility class for scanning and filtering files in a codebase."""
    
    def __init__(self):
        self.default_ignore_patterns = [
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
            '.DS_Store',    # macOS
            'Thumbs.db',    # Windows
        ]
        
        self.binary_extensions = {
            '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.bin',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
            '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac',
            '.ttf', '.otf', '.woff', '.woff2', '.eot',
            '.db', '.sqlite', '.sqlite3'
        }
    
    def scan_directory(self, root_path: str, 
                      extensions: Optional[List[str]] = None,
                      ignore_patterns: Optional[List[str]] = None,
                      max_file_size: int = 10 * 1024 * 1024) -> List[str]:
        """
        Scan directory for files matching criteria.
        
        Args:
            root_path: Root directory to scan
            extensions: File extensions to include (None = all)
            ignore_patterns: Patterns to ignore (None = use defaults)
            max_file_size: Maximum file size in bytes
            
        Returns:
            List of file paths
        """
        if not os.path.exists(root_path):
            logger.error(f"Path does not exist: {root_path}")
            return []
        
        if not os.path.isdir(root_path):
            logger.error(f"Path is not a directory: {root_path}")
            return []
        
        ignore_patterns = ignore_patterns or self.default_ignore_patterns
        file_paths = []
        
        for root, dirs, files in os.walk(root_path):
            # Filter directories
            dirs[:] = [d for d in dirs if not self._should_ignore(
                os.path.join(root, d), ignore_patterns
            )]
            
            # Filter files
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check ignore patterns
                if self._should_ignore(file_path, ignore_patterns):
                    continue
                
                # Check extensions
                if extensions:
                    if not any(file_path.endswith(ext) for ext in extensions):
                        continue
                
                # Check file size
                try:
                    if os.path.getsize(file_path) > max_file_size:
                        logger.warning(f"Skipping large file: {file_path}")
                        continue
                except OSError:
                    logger.warning(f"Cannot access file: {file_path}")
                    continue
                
                # Check if binary
                if self._is_binary_file(file_path):
                    logger.debug(f"Skipping binary file: {file_path}")
                    continue
                
                file_paths.append(file_path)
        
        return sorted(file_paths)
    
    def _should_ignore(self, path: str, patterns: List[str]) -> bool:
        """Check if path matches any ignore pattern."""
        path_parts = Path(path).parts
        
        for pattern in patterns:
            # Check full path
            if fnmatch.fnmatch(path, pattern):
                return True
            
            # Check individual components
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        
        return False
    
    def _is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary based on extension or content."""
        # Check extension first
        _, ext = os.path.splitext(file_path.lower())
        if ext in self.binary_extensions:
            return True
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and not mime_type.startswith('text/'):
            return True
        
        # Sample file content
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\0' in chunk:  # Null byte indicates binary
                    return True
                
                # Check for high ratio of non-text characters
                text_chars = bytes(range(32, 127)) + b'\n\r\t\b'
                non_text = sum(1 for byte in chunk if byte not in text_chars)
                if non_text / len(chunk) > 0.3:
                    return True
                    
        except Exception:
            return True  # Assume binary if can't read
        
        return False
    
    def get_file_info(self, file_path: str) -> Dict[str, any]:
        """Get detailed information about a file."""
        try:
            stat = os.stat(file_path)
            path_obj = Path(file_path)
            
            return {
                'path': file_path,
                'name': path_obj.name,
                'extension': path_obj.suffix,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'created': stat.st_ctime,
                'is_symlink': path_obj.is_symlink(),
                'readable': os.access(file_path, os.R_OK),
                'writable': os.access(file_path, os.W_OK)
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return None
    
    def calculate_file_hash(self, file_path: str, algorithm: str = 'md5') -> Optional[str]:
        """Calculate hash of file content."""
        try:
            hash_func = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None


def find_project_root(start_path: str) -> Optional[str]:
    """
    Find project root by looking for common markers.
    
    Args:
        start_path: Starting directory or file path
        
    Returns:
        Project root path or None
    """
    markers = [
        '.git', '.svn', '.hg',  # Version control
        'package.json', 'setup.py', 'pyproject.toml',  # Project files
        'requirements.txt', 'Pipfile', 'poetry.lock',  # Python
        'Cargo.toml',  # Rust
        'go.mod',  # Go
        'pom.xml', 'build.gradle',  # Java
        '.project', '.solution'  # IDE files
    ]
    
    path = Path(start_path)
    if path.is_file():
        path = path.parent
    
    while path != path.parent:  # Not reached root
        for marker in markers:
            if (path / marker).exists():
                return str(path)
        path = path.parent
    
    # Default to start path if no marker found
    return str(Path(start_path).parent if Path(start_path).is_file() else start_path)


def get_relative_path(file_path: str, base_path: str) -> str:
    """Get relative path from base path."""
    try:
        return os.path.relpath(file_path, base_path)
    except ValueError:
        # Paths on different drives (Windows)
        return file_path


def ensure_directory(directory: str) -> bool:
    """Ensure directory exists, create if necessary."""
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        return False


def safe_read_file(file_path: str, encoding: str = 'utf-8') -> Optional[str]:
    """Safely read file content with fallback encodings."""
    encodings = [encoding, 'utf-8', 'latin-1', 'cp1252']
    
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None
    
    logger.error(f"Failed to read {file_path} with any encoding")
    return None


def get_file_encoding(file_path: str) -> Optional[str]:
    """Detect file encoding."""
    try:
        import chardet
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read(10000))
            return result['encoding']
    except ImportError:
        logger.warning("chardet not installed, using default encoding")
        return 'utf-8'
    except Exception as e:
        logger.error(f"Error detecting encoding for {file_path}: {e}")
        return None


def batch_process_files(file_paths: List[str], 
                       processor_func,
                       batch_size: int = 100) -> List[any]:
    """Process files in batches."""
    results = []
    
    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i + batch_size]
        batch_results = []
        
        for file_path in batch:
            try:
                result = processor_func(file_path)
                if result is not None:
                    batch_results.append(result)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
        
        results.extend(batch_results)
        logger.info(f"Processed batch {i//batch_size + 1}/{(len(file_paths) + batch_size - 1)//batch_size}")
    
    return results