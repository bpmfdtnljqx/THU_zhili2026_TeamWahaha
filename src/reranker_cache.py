"""
reranker_cache.py
------------------
Memory-based LRU cache with TTL for DeepSeekReranker results.

Features:
- Cache key = hash(query + sorted candidate IDs)
- TTL-based expiration (default 30 min)
- LRU eviction (max 1000 entries)
- Thread-safe via dict copy-on-read
- Hit/miss logging
"""

import hashlib
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from logger import get_logger

_log = get_logger("cache", enabled=os.getenv("LYRA_CACHE_DEBUG", "0") == "1")


class RerankerCache:
    """Thread-safe LRU cache with TTL for reranker results."""

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 1800,  # 30 minutes default
    ):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._store: Dict[str, Tuple[float, Any]] = {}  # key -> (expiry, value)
        self._access_times: Dict[str, float] = {}  # key -> last access timestamp
        self._lock = threading.Lock()

        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(query: str, candidate_ids: List[str]) -> str:
        """Derive a deterministic cache key from query + sorted candidate IDs."""
        raw = query + "|" + ",".join(sorted(candidate_ids))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[List[Dict]]:
        """Return cached result or None if missing/expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None

            expiry, value = entry
            if time.time() > expiry:
                del self._store[key]
                self._access_times.pop(key, None)
                self.misses += 1
                return None

            # Bump access time for LRU
            self._access_times[key] = time.time()
            self.hits += 1

            # Return a shallow copy so callers can't mutate cached data
            return list(value)

    def set(self, key: str, value: List[Dict]) -> None:
        """Store a result with TTL; evict LRU entries if at capacity."""
        with self._lock:
            expiry = time.time() + self._ttl
            self._store[key] = (expiry, value)
            self._access_times[key] = time.time()

            # LRU eviction
            while len(self._store) > self._max_size:
                # Find least-recently-used key
                lru_key = min(self._access_times, key=self._access_times.get)
                del self._store[lru_key]
                del self._access_times[lru_key]

    @property
    def stats(self) -> Dict[str, int]:
        """Return hit/miss/size stats for logging."""
        with self._lock:
            return {
                "size": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "max_size": self._max_size,
                "ttl_s": self._ttl,
            }

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()
            self._access_times.clear()
            # Don't reset counters — they're cumulative for the session
