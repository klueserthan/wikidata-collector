import time
import hashlib
import threading
from typing import Dict, Any, Optional, Tuple
from collections import OrderedDict


class TTLCache:
    """Thread-safe in-memory cache with TTL (Time-To-Live) support."""
    
    def __init__(self, ttl_seconds: int = 300, max_size: int = 10000):
        """
        Initialize TTL cache.
        
        Args:
            ttl_seconds: Time to live in seconds (default: 300 = 5 minutes)
            max_size: Maximum number of entries (default: 10000)
        """
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
    
    def _generate_key(self, query: str) -> str:
        """Generate cache key from query string."""
        return hashlib.md5(query.encode()).hexdigest()
    
    def get(self, query: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            key = self._generate_key(query)
            if key not in self._cache:
                return None
            
            timestamp, value = self._cache[key]
            current_time = time.time()
            
            # Check if expired
            if current_time - timestamp > self.ttl:
                # Remove expired entry
                del self._cache[key]
                return None
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            return value
    
    def set(self, query: str, value: Any):
        """Store value in cache with current timestamp."""
        with self._lock:
            key = self._generate_key(query)
            current_time = time.time()
            
            # If key exists, update it
            if key in self._cache:
                self._cache[key] = (current_time, value)
                self._cache.move_to_end(key)
                return
            
            # Remove oldest if at max size
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            # Add new entry
            self._cache[key] = (current_time, value)
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)
    
    def cleanup_expired(self):
        """Remove all expired entries (useful for periodic cleanup)."""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (timestamp, _) in self._cache.items()
                if current_time - timestamp > self.ttl
            ]
            for key in expired_keys:
                del self._cache[key]

