"""Enhanced caching and performance features for ReflInt.

This module provides intelligent caching with source-specific TTL,
cache warming, request deduplication, and performance monitoring.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any
from collections.abc import Callable

try:
    import diskcache as dc

    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False
    dc = None

from loguru import logger


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    total_requests: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""

    default_ttl: float = 3600.0  # 1 hour default
    max_size: int = 1000  # Maximum number of entries
    eviction_policy: str = "lru"  # LRU, LFU, or FIFO
    source_ttls: dict[str, float] = field(
        default_factory=lambda: {
            "crossref": 86400.0,  # 24 hours - stable DOI metadata
            "pubmed": 43200.0,  # 12 hours - medical literature
            "arxiv": 7200.0,  # 2 hours - preprints change frequently
            "semantic_scholar": 21600.0,  # 6 hours - AI-enhanced data
            "openalex": 21600.0,  # 6 hours - academic graph data
            "dblp": 86400.0,  # 24 hours - stable CS literature
            "google_scholar": 3600.0,  # 1 hour - web scraping results
            "url_check": 1800.0,  # 30 minutes - URL status
            "fuzzy_match": 86400.0,  # 24 hours - similarity calculations
            "brace_fix": 604800.0,  # 1 week - text processing results
            "unicode_convert": 604800.0,  # 1 week - character conversion
        }
    )

    def get_ttl_for_source(self, source: str) -> float:
        """Get TTL for a specific data source."""
        return self.source_ttls.get(source, self.default_ttl)


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata."""

    key: str
    value: Any
    timestamp: float
    ttl: float
    source: str | None = None
    access_count: int = 0
    last_access: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.timestamp > self.ttl

    @property
    def age(self) -> float:
        """Get the age of the cache entry in seconds."""
        return time.time() - self.timestamp

    def touch(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_access = time.time()


class EnhancedCache:
    """Enhanced cache with intelligent TTL and performance monitoring."""

    def __init__(
        self,
        config: CacheConfig | None = None,
        cache_dir: Path | None = None,
        enable_disk_cache: bool = True,
    ):
        """Initialize the enhanced cache.

        Args:
            config: Cache configuration
            cache_dir: Directory for disk cache (if using diskcache)
            enable_disk_cache: Whether to use persistent disk cache
        """
        self.config = config or CacheConfig()
        self.stats = CacheStats()
        self._memory_cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._pending_requests: dict[str, Any] = {}  # For deduplication

        # Initialize disk cache if available and requested
        self._disk_cache = None
        if enable_disk_cache and DISKCACHE_AVAILABLE:
            cache_path = cache_dir or Path.home() / ".reflint" / "cache"
            cache_path.mkdir(parents=True, exist_ok=True)
            try:
                self._disk_cache = dc.Cache(
                    str(cache_path), size_limit=100 * 1024 * 1024
                )  # 100MB
                logger.debug(f"Disk cache initialized at: {cache_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize disk cache: {e}")

    def _generate_key(self, key_data: Any, source: str | None = None) -> str:
        """Generate a cache key from arbitrary data.

        Args:
            key_data: Data to generate key from
            source: Source identifier to include in key

        Returns:
            SHA256 hash key
        """
        # Convert data to JSON string for consistent hashing
        if isinstance(key_data, (dict, list)):
            key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        else:
            key_str = str(key_data)

        # Include source in key if provided
        if source:
            key_str = f"{source}:{key_str}"

        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def get(self, key_data: Any, source: str | None = None) -> Any | None:
        """Get value from cache.

        Args:
            key_data: Data to generate cache key from
            source: Source identifier

        Returns:
            Cached value or None if not found/expired
        """
        key = self._generate_key(key_data, source)

        with self._lock:
            self.stats.total_requests += 1

            # Check memory cache first
            entry = self._memory_cache.get(key)
            if entry and not entry.is_expired:
                entry.touch()
                self.stats.hits += 1
                logger.debug(f"Cache hit (memory): {key[:16]}...")
                return entry.value

            # Remove expired entry from memory
            if entry and entry.is_expired:
                del self._memory_cache[key]
                self.stats.evictions += 1

            # Check disk cache if available
            if self._disk_cache:
                try:
                    disk_entry_data = self._disk_cache.get(key)
                    if disk_entry_data:
                        # Reconstruct cache entry
                        disk_entry = CacheEntry(**disk_entry_data)
                        if not disk_entry.is_expired:
                            disk_entry.touch()
                            # Promote to memory cache
                            self._memory_cache[key] = disk_entry
                            self._evict_if_needed()
                            self.stats.hits += 1
                            logger.debug(f"Cache hit (disk): {key[:16]}...")
                            return disk_entry.value
                        # Remove expired entry from disk
                        self._disk_cache.delete(key)
                        self.stats.evictions += 1
                except Exception as e:
                    logger.debug(f"Disk cache read error: {e}")

            self.stats.misses += 1
            logger.debug(f"Cache miss: {key[:16]}...")
            return None

    def set(
        self,
        key_data: Any,
        value: Any,
        source: str | None = None,
        ttl: float | None = None,
    ) -> None:
        """Set value in cache.

        Args:
            key_data: Data to generate cache key from
            value: Value to cache
            source: Source identifier (affects TTL)
            ttl: Custom TTL, overrides source-based TTL
        """
        key = self._generate_key(key_data, source)

        # Determine TTL
        if ttl is not None:
            effective_ttl = ttl
        elif source:
            effective_ttl = self.config.get_ttl_for_source(source)
        else:
            effective_ttl = self.config.default_ttl

        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            ttl=effective_ttl,
            source=source,
        )

        with self._lock:
            # Store in memory cache
            self._memory_cache[key] = entry
            self._evict_if_needed()

            # Store in disk cache if available
            if self._disk_cache:
                try:
                    # Convert entry to dict for serialization
                    entry_data = {
                        "key": entry.key,
                        "value": entry.value,
                        "timestamp": entry.timestamp,
                        "ttl": entry.ttl,
                        "source": entry.source,
                        "access_count": entry.access_count,
                        "last_access": entry.last_access,
                    }
                    self._disk_cache.set(key, entry_data, expire=effective_ttl)
                except Exception as e:
                    logger.debug(f"Disk cache write error: {e}")

            self.stats.sets += 1
            logger.debug(f"Cache set: {key[:16]}... (TTL: {effective_ttl}s)")

    def delete(self, key_data: Any, source: str | None = None) -> bool:
        """Delete value from cache.

        Args:
            key_data: Data to generate cache key from
            source: Source identifier

        Returns:
            True if entry was deleted, False if not found
        """
        key = self._generate_key(key_data, source)

        with self._lock:
            deleted = False

            # Delete from memory cache
            if key in self._memory_cache:
                del self._memory_cache[key]
                deleted = True

            # Delete from disk cache
            if self._disk_cache:
                try:
                    if self._disk_cache.delete(key):
                        deleted = True
                except Exception as e:
                    logger.debug(f"Disk cache delete error: {e}")

            if deleted:
                self.stats.deletes += 1
                logger.debug(f"Cache delete: {key[:16]}...")

            return deleted

    def _evict_if_needed(self) -> None:
        """Evict entries if cache is over size limit."""
        if len(self._memory_cache) <= self.config.max_size:
            return

        # Determine eviction strategy
        if self.config.eviction_policy == "lru":
            # Evict least recently used
            to_evict = min(self._memory_cache.values(), key=lambda e: e.last_access)
        elif self.config.eviction_policy == "lfu":
            # Evict least frequently used
            to_evict = min(self._memory_cache.values(), key=lambda e: e.access_count)
        else:  # FIFO
            # Evict oldest entry
            to_evict = min(self._memory_cache.values(), key=lambda e: e.timestamp)

        del self._memory_cache[to_evict.key]
        self.stats.evictions += 1
        logger.debug(
            f"Cache eviction ({self.config.eviction_policy}): {to_evict.key[:16]}..."
        )

    def clear(self, source: str | None = None) -> int:
        """Clear cache entries.

        Args:
            source: If provided, only clear entries from this source

        Returns:
            Number of entries cleared
        """
        with self._lock:
            if source is None:
                # Clear all entries
                count = len(self._memory_cache)
                self._memory_cache.clear()

                if self._disk_cache:
                    try:
                        self._disk_cache.clear()
                    except Exception as e:
                        logger.debug(f"Disk cache clear error: {e}")

                logger.info(f"Cache cleared: {count} entries")
                return count
            # Clear entries from specific source
            to_remove = [
                key
                for key, entry in self._memory_cache.items()
                if entry.source == source
            ]

            for key in to_remove:
                del self._memory_cache[key]

            # For disk cache, we'd need to iterate through all entries
            # which is expensive, so we skip source-specific clearing for disk

            logger.info(
                f"Cache cleared for source '{source}': {len(to_remove)} entries"
            )
            return len(to_remove)

    def cleanup_expired(self) -> int:
        """Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._memory_cache.items() if entry.is_expired
            ]

            for key in expired_keys:
                del self._memory_cache[key]

            # For disk cache, expired entries are automatically handled
            # by the underlying diskcache library

            self.stats.evictions += len(expired_keys)

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

            return len(expired_keys)

    def get_cache_info(self) -> dict[str, Any]:
        """Get cache information and statistics.

        Returns:
            Dictionary with cache stats and configuration
        """
        with self._lock:
            memory_size = len(self._memory_cache)
            disk_size = 0

            if self._disk_cache:
                try:
                    disk_size = len(self._disk_cache)
                except Exception:
                    disk_size = -1  # Error getting size

            return {
                "config": {
                    "default_ttl": self.config.default_ttl,
                    "max_size": self.config.max_size,
                    "eviction_policy": self.config.eviction_policy,
                    "source_ttls": self.config.source_ttls,
                },
                "stats": {
                    "hits": self.stats.hits,
                    "misses": self.stats.misses,
                    "hit_rate": self.stats.hit_rate,
                    "miss_rate": self.stats.miss_rate,
                    "sets": self.stats.sets,
                    "deletes": self.stats.deletes,
                    "evictions": self.stats.evictions,
                    "total_requests": self.stats.total_requests,
                },
                "size": {
                    "memory_entries": memory_size,
                    "disk_entries": disk_size,
                    "disk_cache_available": self._disk_cache is not None,
                },
            }


class RequestDeduplicator:
    """Prevents duplicate requests within a session."""

    def __init__(self) -> None:
        """Initialize the request deduplicator."""
        self._pending: dict[str, Any] = {}
        self._lock = Lock()

    def is_duplicate(self, request_key: str) -> bool:
        """Check if a request is already pending.

        Args:
            request_key: Unique identifier for the request

        Returns:
            True if request is already pending
        """
        with self._lock:
            return request_key in self._pending

    def add_pending(self, request_key: str, placeholder: Any = None) -> None:
        """Mark a request as pending.

        Args:
            request_key: Unique identifier for the request
            placeholder: Optional placeholder value
        """
        with self._lock:
            self._pending[request_key] = placeholder

    def complete_request(self, request_key: str, result: Any = None) -> None:
        """Mark a request as completed.

        Args:
            request_key: Unique identifier for the request
            result: Optional result value
        """
        with self._lock:
            self._pending.pop(request_key, None)

    def get_pending_count(self) -> int:
        """Get the number of pending requests.

        Returns:
            Number of currently pending requests
        """
        with self._lock:
            return len(self._pending)

    def clear_pending(self) -> None:
        """Clear all pending requests."""
        with self._lock:
            self._pending.clear()


# Global cache instance
_global_cache: EnhancedCache | None = None
_global_deduplicator: RequestDeduplicator | None = None


def get_cache() -> EnhancedCache:
    """Get the global cache instance.

    Returns:
        Global EnhancedCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = EnhancedCache()
    return _global_cache


def get_deduplicator() -> RequestDeduplicator:
    """Get the global request deduplicator.

    Returns:
        Global RequestDeduplicator instance
    """
    global _global_deduplicator
    if _global_deduplicator is None:
        _global_deduplicator = RequestDeduplicator()
    return _global_deduplicator


def cached(
    source: str | None = None, ttl: float | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for caching function results.

    Args:
        source: Source identifier for TTL determination
        ttl: Custom TTL, overrides source-based TTL

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = get_cache()

            # Generate cache key from function name and arguments
            key_data = {"function": func.__name__, "args": args, "kwargs": kwargs}

            # Try to get from cache
            result = cache.get(key_data, source)
            if result is not None:
                return result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(key_data, result, source, ttl)
            return result

        return wrapper

    return decorator


def deduplicated(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for preventing duplicate requests.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function that prevents duplicates
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        deduplicator = get_deduplicator()

        # Generate request key
        key_data = {"function": func.__name__, "args": args, "kwargs": kwargs}
        request_key = json.dumps(key_data, sort_keys=True, default=str)

        # Check if request is already pending
        if deduplicator.is_duplicate(request_key):
            logger.debug(f"Duplicate request detected for {func.__name__}")
            return None  # or raise exception, depending on needs

        try:
            deduplicator.add_pending(request_key)
            return func(*args, **kwargs)
        finally:
            deduplicator.complete_request(request_key)

    return wrapper
