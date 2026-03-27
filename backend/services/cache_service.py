"""
GEOAI-OPT-02: In-memory TTL cache for spatial queries.
"""
import hashlib
import time
import threading
from typing import Dict, Tuple, Any, Optional, Union


class SpatialCache:
    """Thread-safe in-memory cache with TTL expiration."""

    def __init__(self, default_ttl: int = 60):
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._default_ttl = default_ttl
        self._lock = threading.Lock()

    @staticmethod
    def _hash_key(sql: str) -> str:
        return hashlib.md5((sql + "_v2").encode()).hexdigest()

    def get(self, sql: str):
        """Return cached result or None if miss/expired."""
        key = self._hash_key(sql)
        with self._lock:
            if key in self._store:
                expires_at, value = self._store[key]
                if time.time() < expires_at:
                    return value
                else:
                    del self._store[key]
        return None

    def set(self, sql: str, value, ttl: Optional[int] = None):
        """Store a result with TTL."""
        key = self._hash_key(sql)
        expires_at = time.time() + (ttl or self._default_ttl)
        with self._lock:
            self._store[key] = (expires_at, value)

    def invalidate(self, sql: Optional[str] = None):
        """Invalidate one key or clear entire cache."""
        with self._lock:
            if sql:
                key = self._hash_key(sql)
                self._store.pop(key, None)
            else:
                self._store.clear()

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            now = time.time()
            total = len(self._store)
            active = sum(1 for exp, _ in self._store.values() if now < exp)
            return {"total_keys": total, "active_keys": active}


# Singleton instances
query_cache = SpatialCache(default_ttl=300)        # 5 mins
basemap_cache = SpatialCache(default_ttl=1800)     # 30 mins
llm_cache = SpatialCache(default_ttl=120)          # 2 mins
summary_cache = SpatialCache(default_ttl=600)      # 10 mins
