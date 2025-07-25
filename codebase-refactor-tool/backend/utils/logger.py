"""
Logging configuration for the codebase refactor tool.
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def __init__(self, fmt=None, datefmt=None, use_colors=True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record):
        if self.use_colors and record.levelname in self.COLORS:
            # Add color to level name
            levelname = record.levelname
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
            formatted = super().format(record)
            record.levelname = levelname  # Restore original
            return formatted
        else:
            return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_obj = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'msecs', 'levelname', 
                          'levelno', 'pathname', 'filename', 'module', 'funcName',
                          'lineno', 'exc_info', 'exc_text', 'stack_info', 'message']:
                log_obj[key] = value
        
        return json.dumps(log_obj)


def setup_logging(name: Optional[str] = None, 
                 level: str = 'INFO',
                 log_file: Optional[str] = None,
                 log_dir: Optional[str] = None,
                 console: bool = True,
                 json_format: bool = False,
                 max_bytes: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5) -> logging.Logger:
    """
    Setup logging configuration.
    
    Args:
        name: Logger name (None for root logger)
        level: Logging level
        log_file: Log file name
        log_dir: Directory for log files
        console: Enable console output
        json_format: Use JSON format for logs
        max_bytes: Max size for log rotation
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        if json_format:
            console_formatter = JSONFormatter()
        else:
            console_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            console_formatter = ColoredFormatter(console_format)
        
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file or log_dir:
        if not log_file:
            log_file = f"codebase_refactor_{datetime.now().strftime('%Y%m%d')}.log"
        
        if log_dir:
            log_path = Path(log_dir) / log_file
            log_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            log_path = Path(log_file)
        
        # Use rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        
        if json_format:
            file_formatter = JSONFormatter()
        else:
            file_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            file_formatter = logging.Formatter(file_format)
        
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class LogContext:
    """Context manager for temporary logging configuration."""
    
    def __init__(self, logger: logging.Logger, 
                 level: Optional[str] = None,
                 extra: Optional[Dict[str, Any]] = None):
        self.logger = logger
        self.new_level = getattr(logging, level.upper()) if level else None
        self.extra = extra or {}
        self.old_level = None
        self.adapter = None
    
    def __enter__(self):
        if self.new_level:
            self.old_level = self.logger.level
            self.logger.setLevel(self.new_level)
        
        if self.extra:
            self.adapter = logging.LoggerAdapter(self.logger, self.extra)
            return self.adapter
        
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_level is not None:
            self.logger.setLevel(self.old_level)


def log_function_call(logger: logging.Logger):
    """Decorator to log function calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__} returned {result}")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
                raise
        return wrapper
    return decorator


def log_execution_time(logger: logging.Logger):
    """Decorator to log execution time."""
    import time
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"{func.__name__} completed in {elapsed:.2f} seconds")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"{func.__name__} failed after {elapsed:.2f} seconds: {e}")
                raise
        return wrapper
    return decorator


class ProgressLogger:
    """Helper for logging progress of long-running operations."""
    
    def __init__(self, logger: logging.Logger, 
                 total: int, 
                 message: str = "Processing",
                 log_interval: int = 10):
        self.logger = logger
        self.total = total
        self.message = message
        self.log_interval = log_interval
        self.current = 0
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"{self.message} started - {self.total} items to process")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            self.logger.info(
                f"{self.message} completed - {self.current}/{self.total} items "
                f"in {elapsed:.1f} seconds"
            )
    
    def update(self, count: int = 1):
        """Update progress."""
        self.current += count
        
        if self.current % self.log_interval == 0 or self.current == self.total:
            percentage = (self.current / self.total) * 100
            elapsed = (datetime.now() - self.start_time).total_seconds()
            rate = self.current / elapsed if elapsed > 0 else 0
            
            self.logger.info(
                f"{self.message} progress: {self.current}/{self.total} "
                f"({percentage:.1f}%) - {rate:.1f} items/sec"
            )


# Configure root logger on import
def configure_root_logger():
    """Configure the root logger with sensible defaults."""
    root_logger = logging.getLogger()
    
    # Only configure if no handlers exist
    if not root_logger.handlers:
        # Set root level from environment or default
        level = os.environ.get('LOG_LEVEL', 'INFO')
        root_logger.setLevel(getattr(logging, level.upper()))
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # Use colored formatter for console
        console_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        console_formatter = ColoredFormatter(console_format)
        console_handler.setFormatter(console_formatter)
        
        root_logger.addHandler(console_handler)
        
        # Add file handler if log directory is specified
        log_dir = os.environ.get('LOG_DIR')
        if log_dir:
            log_file = f"codebase_refactor_{datetime.now().strftime('%Y%m%d')}.log"
            log_path = Path(log_dir) / log_file
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            file_handler.setLevel(logging.DEBUG)
            
            file_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            file_formatter = logging.Formatter(file_format)
            file_handler.setFormatter(file_formatter)
            
            root_logger.addHandler(file_handler)
    
    # Suppress noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('neo4j').setLevel(logging.WARNING)


# Configure on import
configure_root_logger()