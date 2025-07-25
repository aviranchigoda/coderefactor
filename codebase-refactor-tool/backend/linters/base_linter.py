"""
Base linter interface and registry for language-specific linters.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import subprocess
import json
import logging
from pathlib import Path
import tempfile
import os

from ..models.code_entity import LintErrorEntity
from ..models.graph_node import Severity

logger = logging.getLogger(__name__)


class BaseLinter(ABC):
    """Abstract base class for all linters."""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.supported_extensions = []
        self.executable = None
        self.config_file = None
    
    @abstractmethod
    def can_lint(self, file_path: str) -> bool:
        """Check if this linter can handle the file."""
        pass
    
    @abstractmethod
    def lint_file(self, file_path: str) -> List[LintErrorEntity]:
        """
        Lint a single file and return errors.
        
        Args:
            file_path: Path to the file to lint
            
        Returns:
            List of lint errors found
        """
        pass
    
    def lint_directory(self, directory: str, 
                      extensions: Optional[List[str]] = None) -> List[LintErrorEntity]:
        """
        Lint all files in a directory.
        
        Args:
            directory: Directory path
            extensions: File extensions to lint (None = use defaults)
            
        Returns:
            List of all lint errors found
        """
        errors = []
        extensions = extensions or self.supported_extensions
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check extension
                if not any(file_path.endswith(ext) for ext in extensions):
                    continue
                
                # Lint file
                if self.can_lint(file_path):
                    try:
                        file_errors = self.lint_file(file_path)
                        errors.extend(file_errors)
                    except Exception as e:
                        logger.error(f"Error linting {file_path}: {e}")
        
        return errors
    
    def check_executable(self) -> bool:
        """Check if the linter executable is available."""
        if not self.executable:
            return True
        
        try:
            result = subprocess.run(
                [self.executable, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def run_command(self, cmd: List[str], cwd: str = None, 
                   timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a linter command and return the result."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Linter command timed out: {' '.join(cmd)}")
            raise
        except Exception as e:
            logger.error(f"Error running linter command: {e}")
            raise
    
    def map_severity(self, linter_severity: str) -> Severity:
        """Map linter-specific severity to our severity enum."""
        severity_map = {
            'error': Severity.ERROR,
            'warning': Severity.WARNING,
            'info': Severity.INFO,
            'hint': Severity.INFO,
            'note': Severity.INFO,
            'fatal': Severity.ERROR,
            'critical': Severity.ERROR
        }
        
        return severity_map.get(linter_severity.lower(), Severity.WARNING)


class LinterRegistry:
    """Registry for managing multiple linters."""
    
    def __init__(self):
        self.linters: Dict[str, BaseLinter] = {}
        self._initialize_linters()
    
    def _initialize_linters(self):
        """Initialize all available linters."""
        # Import and register linters
        try:
            from .pylint_wrapper import PylintWrapper
            self.register_linter('python', PylintWrapper())
        except ImportError:
            logger.warning("Pylint wrapper not available")
        
        try:
            from .eslint_wrapper import ESLintWrapper
            self.register_linter('javascript', ESLintWrapper())
        except ImportError:
            logger.warning("ESLint wrapper not available")
        
        try:
            from .checkstyle_wrapper import CheckstyleWrapper
            self.register_linter('java', CheckstyleWrapper())
        except ImportError:
            logger.warning("Checkstyle wrapper not available")
    
    def register_linter(self, name: str, linter: BaseLinter):
        """Register a new linter."""
        self.linters[name] = linter
        
        # Check if executable is available
        if not linter.check_executable():
            logger.warning(f"Linter {name} executable not found: {linter.executable}")
        else:
            logger.info(f"Registered linter: {name}")
    
    def get_linter(self, name: str) -> Optional[BaseLinter]:
        """Get a linter by name."""
        return self.linters.get(name)
    
    def get_linter_for_file(self, file_path: str) -> Optional[BaseLinter]:
        """Get appropriate linter for a file."""
        for linter in self.linters.values():
            if linter.can_lint(file_path):
                return linter
        return None
    
    def lint_file(self, file_path: str) -> List[LintErrorEntity]:
        """Lint a file using the appropriate linter."""
        linter = self.get_linter_for_file(file_path)
        if linter:
            return linter.lint_file(file_path)
        return []
    
    def get_available_linters(self) -> List[str]:
        """Get list of available linter names."""
        return list(self.linters.keys())


class ConfigurableLinter(BaseLinter):
    """Base class for linters that support configuration files."""
    
    def __init__(self):
        super().__init__()
        self.default_config = {}
    
    def find_config_file(self, start_path: str) -> Optional[str]:
        """Find configuration file by walking up the directory tree."""
        if not self.config_file:
            return None
        
        path = Path(start_path)
        if path.is_file():
            path = path.parent
        
        while path != path.parent:
            config_path = path / self.config_file
            if config_path.exists():
                return str(config_path)
            path = path.parent
        
        return None
    
    def create_temp_config(self, config: Dict[str, Any]) -> str:
        """Create a temporary configuration file."""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=f'_{self.config_file}',
            delete=False
        ) as f:
            json.dump(config, f, indent=2)
            return f.name
    
    def merge_configs(self, base_config: Dict[str, Any], 
                     override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries."""
        merged = base_config.copy()
        merged.update(override_config)
        return merged


class CompositeLinter(BaseLinter):
    """Linter that combines multiple linters."""
    
    def __init__(self, linters: List[BaseLinter]):
        super().__init__()
        self.linters = linters
        self.supported_extensions = []
        
        # Collect all supported extensions
        for linter in linters:
            self.supported_extensions.extend(linter.supported_extensions)
        
        self.supported_extensions = list(set(self.supported_extensions))
    
    def can_lint(self, file_path: str) -> bool:
        """Check if any sub-linter can handle the file."""
        return any(linter.can_lint(file_path) for linter in self.linters)
    
    def lint_file(self, file_path: str) -> List[LintErrorEntity]:
        """Lint file with all applicable linters."""
        errors = []
        
        for linter in self.linters:
            if linter.can_lint(file_path):
                try:
                    linter_errors = linter.lint_file(file_path)
                    errors.extend(linter_errors)
                except Exception as e:
                    logger.error(f"Error running {linter.name} on {file_path}: {e}")
        
        return errors


# Utility functions
def parse_line_column(text: str) -> tuple:
    """
    Parse line and column from various formats.
    
    Examples:
        "10:5" -> (10, 5)
        "line 10, column 5" -> (10, 5)
        "10" -> (10, None)
    """
    import re
    
    # Try different patterns
    patterns = [
        r'(\d+):(\d+)',  # 10:5
        r'line\s+(\d+),?\s+col(?:umn)?\s+(\d+)',  # line 10, column 5
        r'(\d+),(\d+)',  # 10,5
        r'(\d+)'  # Just line number
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return int(groups[0]), int(groups[1])
            elif len(groups) == 1:
                return int(groups[0]), None
    
    return None, None


def normalize_path(path: str, base_path: str = None) -> str:
    """Normalize file path relative to base path."""
    path = Path(path)
    
    if path.is_absolute():
        if base_path:
            try:
                return str(path.relative_to(base_path))
            except ValueError:
                pass
        return str(path)
    
    if base_path:
        return str(Path(base_path) / path)
    
    return str(path)