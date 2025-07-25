"""
Cache management for parsed code entities.
"""

import os
import json
import pickle
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
from dataclasses import asdict
import tempfile
import shutil

from ..models.code_entity import FileEntity, CodebaseModel

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of parsed code entities to improve performance."""
    
    def __init__(self, cache_dir: Optional[str] = None, 
                 max_cache_size_mb: int = 500,
                 ttl_hours: int = 24):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache storage (default: system temp)
            max_cache_size_mb: Maximum cache size in MB
            ttl_hours: Time to live for cache entries in hours
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "codebase_refactor_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # Convert to bytes
        self.ttl_seconds = ttl_hours * 3600
        
        # In-memory cache for current session
        self.memory_cache: Dict[str, Any] = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
        # Initialize cache index
        self.index_file = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_index()
        
        # Clean up old entries on startup
        self._cleanup_expired()
    
    def get_cached_parse(self, file_path: str) -> Optional[FileEntity]:
        """
        Get cached parse result for a file.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Cached FileEntity or None if not found/invalid
        """
        # Check memory cache first
        cache_key = self._get_cache_key(file_path)
        if cache_key in self.memory_cache:
            self.cache_stats['hits'] += 1
            logger.debug(f"Memory cache hit for {file_path}")
            return self.memory_cache[cache_key]
        
        # Check disk cache
        cache_entry = self.cache_index.get(cache_key)
        if not cache_entry:
            self.cache_stats['misses'] += 1
            return None
        
        # Validate cache entry
        if not self._is_valid_cache_entry(file_path, cache_entry):
            self.cache_stats['misses'] += 1
            self._remove_cache_entry(cache_key)
            return None
        
        # Load from disk
        cached_data = self._load_from_disk(cache_entry['cache_file'])
        if cached_data:
            self.cache_stats['hits'] += 1
            # Add to memory cache
            self.memory_cache[cache_key] = cached_data
            logger.debug(f"Disk cache hit for {file_path}")
            return cached_data
        
        self.cache_stats['misses'] += 1
        return None
    
    def cache_parse(self, file_path: str, file_entity: FileEntity):
        """
        Cache parse result for a file.
        
        Args:
            file_path: Path to the source file
            file_entity: Parsed file entity
        """
        cache_key = self._get_cache_key(file_path)
        
        # Add to memory cache
        self.memory_cache[cache_key] = file_entity
        
        # Save to disk
        cache_file = self._get_cache_file_path(cache_key)
        if self._save_to_disk(file_entity, cache_file):
            # Update index
            self.cache_index[cache_key] = {
                'file_path': file_path,
                'cache_file': str(cache_file),
                'file_hash': self._calculate_file_hash(file_path),
                'file_mtime': os.path.getmtime(file_path),
                'cached_at': time.time(),
                'size': cache_file.stat().st_size
            }
            self._save_index()
            logger.debug(f"Cached parse result for {file_path}")
        
        # Check cache size and evict if necessary
        self._check_cache_size()
    
    def clear_cache(self):
        """Clear all cache entries."""
        logger.info("Clearing cache...")
        
        # Clear memory cache
        self.memory_cache.clear()
        
        # Clear disk cache
        try:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error clearing cache directory: {e}")
        
        # Reset index
        self.cache_index = {}
        self._save_index()
        
        # Reset stats
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
        logger.info("Cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(entry.get('size', 0) for entry in self.cache_index.values())
        
        return {
            **self.cache_stats,
            'memory_entries': len(self.memory_cache),
            'disk_entries': len(self.cache_index),
            'total_size_mb': total_size / (1024 * 1024),
            'hit_rate': self.cache_stats['hits'] / max(1, self.cache_stats['hits'] + self.cache_stats['misses'])
        }
    
    def _get_cache_key(self, file_path: str) -> str:
        """Generate cache key for a file path."""
        return hashlib.md5(file_path.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get cache file path for a cache key."""
        # Use subdirectories to avoid too many files in one directory
        subdir = cache_key[:2]
        return self.cache_dir / subdir / f"{cache_key}.pkl"
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _is_valid_cache_entry(self, file_path: str, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid."""
        try:
            # Check if file still exists
            if not os.path.exists(file_path):
                return False
            
            # Check modification time
            current_mtime = os.path.getmtime(file_path)
            if current_mtime > cache_entry.get('file_mtime', 0):
                return False
            
            # Check content hash (more expensive but accurate)
            current_hash = self._calculate_file_hash(file_path)
            if current_hash != cache_entry.get('file_hash'):
                return False
            
            # Check TTL
            age = time.time() - cache_entry.get('cached_at', 0)
            if age > self.ttl_seconds:
                return False
            
            # Check if cache file exists
            cache_file = Path(cache_entry.get('cache_file', ''))
            if not cache_file.exists():
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error validating cache entry: {e}")
            return False
    
    def _save_to_disk(self, file_entity: FileEntity, cache_file: Path) -> bool:
        """Save file entity to disk."""
        try:
            # Create parent directory
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save as pickle for efficiency
            with open(cache_file, 'wb') as f:
                pickle.dump(file_entity, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving to cache: {e}")
            return False
    
    def _load_from_disk(self, cache_file: str) -> Optional[FileEntity]:
        """Load file entity from disk."""
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.debug(f"Error loading from cache: {e}")
            return None
    
    def _load_index(self) -> Dict[str, Dict]:
        """Load cache index from disk."""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cache index: {e}")
        
        return {}
    
    def _save_index(self):
        """Save cache index to disk."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.cache_index, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")
    
    def _cleanup_expired(self):
        """Remove expired cache entries."""
        logger.debug("Cleaning up expired cache entries...")
        
        expired_keys = []
        current_time = time.time()
        
        for cache_key, entry in self.cache_index.items():
            age = current_time - entry.get('cached_at', 0)
            if age > self.ttl_seconds:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            self._remove_cache_entry(key)
        
        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired cache entries")
            self._save_index()
    
    def _check_cache_size(self):
        """Check cache size and evict if necessary."""
        total_size = sum(entry.get('size', 0) for entry in self.cache_index.values())
        
        if total_size <= self.max_cache_size:
            return
        
        logger.info(f"Cache size ({total_size / 1024 / 1024:.1f}MB) exceeds limit, evicting...")
        
        # Sort by access time (oldest first)
        sorted_entries = sorted(
            self.cache_index.items(),
            key=lambda x: x[1].get('cached_at', 0)
        )
        
        # Evict oldest entries until under limit
        while total_size > self.max_cache_size and sorted_entries:
            cache_key, entry = sorted_entries.pop(0)
            self._remove_cache_entry(cache_key)
            total_size -= entry.get('size', 0)
            self.cache_stats['evictions'] += 1
        
        self._save_index()
    
    def _remove_cache_entry(self, cache_key: str):
        """Remove a cache entry."""
        # Remove from memory cache
        self.memory_cache.pop(cache_key, None)
        
        # Remove from index
        entry = self.cache_index.pop(cache_key, None)
        if not entry:
            return
        
        # Remove cache file
        try:
            cache_file = Path(entry.get('cache_file', ''))
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.debug(f"Error removing cache file: {e}")


class ProjectCache:
    """Higher-level cache for entire project analysis results."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.project_cache_file = cache_manager.cache_dir / "project_cache.json"
    
    def save_project_analysis(self, project_path: str, analysis_results: Dict):
        """Save project analysis results."""
        try:
            cache_data = {
                'project_path': project_path,
                'analysis_results': analysis_results,
                'timestamp': time.time()
            }
            
            with open(self.project_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            logger.info(f"Saved project analysis cache for {project_path}")
            
        except Exception as e:
            logger.error(f"Error saving project cache: {e}")
    
    def load_project_analysis(self, project_path: str) -> Optional[Dict]:
        """Load project analysis results if valid."""
        try:
            if not self.project_cache_file.exists():
                return None
            
            with open(self.project_cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Validate project path
            if cache_data.get('project_path') != project_path:
                return None
            
            # Check age
            age = time.time() - cache_data.get('timestamp', 0)
            if age > 86400:  # 24 hours
                return None
            
            return cache_data.get('analysis_results')
            
        except Exception as e:
            logger.error(f"Error loading project cache: {e}")
            return None