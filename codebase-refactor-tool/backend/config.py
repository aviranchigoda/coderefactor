"""
Configuration management for the backend server.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Neo4jConfig:
    """Neo4j database configuration."""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    encrypted: bool = False
    trust: str = "TRUST_ALL_CERTIFICATES"


@dataclass
class ServerConfig:
    """Server configuration."""
    host: str = "127.0.0.1"
    port: int = 5000
    cors_origins: list = None
    debug: bool = False
    reload: bool = False
    workers: int = 1
    
    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["http://localhost:3000", "file://"]


@dataclass
class AnalyzerConfig:
    """Code analyzer configuration."""
    max_workers: int = 4
    max_file_size_mb: int = 10
    cache_enabled: bool = True
    cache_dir: Optional[str] = None
    cache_ttl_hours: int = 24
    ignore_patterns: list = None
    file_extensions: list = None
    
    def __post_init__(self):
        if self.ignore_patterns is None:
            self.ignore_patterns = [
                '.*', '__pycache__', '*.pyc', 'node_modules',
                'dist', 'build', '.git', 'venv', 'env'
            ]
        
        if self.file_extensions is None:
            self.file_extensions = [
                '.py', '.js', '.jsx', '.ts', '.tsx', '.java',
                '.cpp', '.c', '.h', '.cs', '.go', '.rs'
            ]


@dataclass 
class LinterConfig:
    """Linter configuration."""
    enabled: bool = True
    pylint_enabled: bool = True
    eslint_enabled: bool = True
    timeout_seconds: int = 30
    max_errors: int = 100


@dataclass
class RefactoringConfig:
    """Refactoring configuration."""
    max_context_size: int = 10000
    default_prune_depth: int = 3
    enable_auto_save: bool = False
    backup_enabled: bool = True
    backup_dir: Optional[str] = None


class Config:
    """Main configuration class."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_file: Path to configuration file (JSON)
        """
        self.config_file = config_file or self._find_config_file()
        
        # Load base configuration
        self._load_defaults()
        
        # Load from file if exists
        if self.config_file and os.path.exists(self.config_file):
            self._load_from_file(self.config_file)
        
        # Override with environment variables
        self._load_from_env()
        
        # Validate configuration
        self._validate()
    
    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations."""
        search_paths = [
            Path.cwd() / "config.json",
            Path.cwd() / "backend" / "config.json",
            Path.home() / ".codebase_refactor" / "config.json",
            Path("/etc/codebase_refactor/config.json")
        ]
        
        for path in search_paths:
            if path.exists():
                logger.info(f"Found config file: {path}")
                return str(path)
        
        return None
    
    def _load_defaults(self):
        """Load default configuration."""
        self.neo4j = Neo4jConfig()
        self.server = ServerConfig()
        self.analyzer = AnalyzerConfig()
        self.linter = LinterConfig()
        self.refactoring = RefactoringConfig()
        
        # Additional settings
        self.app_name = "Codebase Refactor Tool"
        self.version = "1.0.0"
        self.log_level = "INFO"
        self.log_dir = None
        self.data_dir = str(Path.home() / ".codebase_refactor" / "data")
    
    def _load_from_file(self, config_file: str):
        """Load configuration from JSON file."""
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
            
            # Update Neo4j config
            if 'neo4j' in data:
                self.neo4j = Neo4jConfig(**data['neo4j'])
            
            # Update server config
            if 'server' in data:
                self.server = ServerConfig(**data['server'])
            
            # Update analyzer config
            if 'analyzer' in data:
                self.analyzer = AnalyzerConfig(**data['analyzer'])
            
            # Update linter config
            if 'linter' in data:
                self.linter = LinterConfig(**data['linter'])
            
            # Update refactoring config
            if 'refactoring' in data:
                self.refactoring = RefactoringConfig(**data['refactoring'])
            
            # Update other settings
            self.app_name = data.get('app_name', self.app_name)
            self.version = data.get('version', self.version)
            self.log_level = data.get('log_level', self.log_level)
            self.log_dir = data.get('log_dir', self.log_dir)
            self.data_dir = data.get('data_dir', self.data_dir)
            
            logger.info(f"Loaded configuration from {config_file}")
            
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        # Neo4j settings
        if os.getenv('NEO4J_URI'):
            self.neo4j.uri = os.getenv('NEO4J_URI')
        if os.getenv('NEO4J_USERNAME'):
            self.neo4j.username = os.getenv('NEO4J_USERNAME')
        if os.getenv('NEO4J_PASSWORD'):
            self.neo4j.password = os.getenv('NEO4J_PASSWORD')
        if os.getenv('NEO4J_DATABASE'):
            self.neo4j.database = os.getenv('NEO4J_DATABASE')
        
        # Server settings
        if os.getenv('SERVER_HOST'):
            self.server.host = os.getenv('SERVER_HOST')
        if os.getenv('SERVER_PORT'):
            self.server.port = int(os.getenv('SERVER_PORT'))
        if os.getenv('DEBUG'):
            self.server.debug = os.getenv('DEBUG').lower() == 'true'
        
        # Analyzer settings
        if os.getenv('MAX_WORKERS'):
            self.analyzer.max_workers = int(os.getenv('MAX_WORKERS'))
        if os.getenv('CACHE_DIR'):
            self.analyzer.cache_dir = os.getenv('CACHE_DIR')
        
        # Other settings
        if os.getenv('LOG_LEVEL'):
            self.log_level = os.getenv('LOG_LEVEL')
        if os.getenv('LOG_DIR'):
            self.log_dir = os.getenv('LOG_DIR')
        if os.getenv('DATA_DIR'):
            self.data_dir = os.getenv('DATA_DIR')
    
    def _validate(self):
        """Validate configuration."""
        # Check Neo4j password
        if not self.neo4j.password:
            logger.warning("Neo4j password not set - using environment variable or config file")
        
        # Ensure directories exist
        if self.log_dir:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        
        # Set cache directory if not specified
        if not self.analyzer.cache_dir:
            self.analyzer.cache_dir = os.path.join(self.data_dir, "cache")
        
        # Set backup directory if not specified
        if not self.refactoring.backup_dir:
            self.refactoring.backup_dir = os.path.join(self.data_dir, "backups")
    
    def save(self, config_file: Optional[str] = None):
        """Save configuration to file."""
        config_file = config_file or self.config_file
        if not config_file:
            config_file = "config.json"
        
        data = {
            'app_name': self.app_name,
            'version': self.version,
            'log_level': self.log_level,
            'log_dir': self.log_dir,
            'data_dir': self.data_dir,
            'neo4j': asdict(self.neo4j),
            'server': asdict(self.server),
            'analyzer': asdict(self.analyzer),
            'linter': asdict(self.linter),
            'refactoring': asdict(self.refactoring)
        }
        
        try:
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved configuration to {config_file}")
        except Exception as e:
            logger.error(f"Error saving config file: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'app_name': self.app_name,
            'version': self.version,
            'log_level': self.log_level,
            'log_dir': self.log_dir,
            'data_dir': self.data_dir,
            'neo4j': asdict(self.neo4j),
            'server': asdict(self.server),
            'analyzer': asdict(self.analyzer),
            'linter': asdict(self.linter),
            'refactoring': asdict(self.refactoring)
        }
    
    # Convenience properties
    @property
    def neo4j_uri(self) -> str:
        return self.neo4j.uri
    
    @property
    def neo4j_username(self) -> str:
        return self.neo4j.username
    
    @property
    def neo4j_password(self) -> str:
        return self.neo4j.password
    
    @property
    def server_host(self) -> str:
        return self.server.host
    
    @property
    def server_port(self) -> int:
        return self.server.port
    
    @property
    def debug(self) -> bool:
        return self.server.debug
    
    @property
    def analyzer_config(self) -> Dict[str, Any]:
        return asdict(self.analyzer)