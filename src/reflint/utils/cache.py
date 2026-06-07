"""Caching system for API responses and external data."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

from loguru import logger


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    data: Any
    timestamp: float
    source: str
    ttl: int  # Time to live in seconds
    size: int = 0

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.timestamp > self.ttl

    def age(self) -> int:
        """Get age in seconds."""
        return int(time.time() - self.timestamp)


class ResponseCache:
    """SQLite-based cache for API responses."""

    def __init__(
        self, cache_file: Path | None = None, default_ttl: int = 86400
    ) -> None:
        """Initialize cache.

        Args:
            cache_file: Path to SQLite cache file. Defaults to ~/.cache/reflint/responses.db
            default_ttl: Default time-to-live in seconds (24 hours)
        """
        if cache_file is None:
            cache_dir = Path.home() / ".cache" / "reflint"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / "responses.db"

        self.cache_file = cache_file
        self.default_ttl = default_ttl
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.cache_file) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    source TEXT NOT NULL,
                    ttl INTEGER NOT NULL,
                    size INTEGER DEFAULT 0
                )
            """)

            # Create index on timestamp for cleanup
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON cache_entries(timestamp)
            """)

            # Create index on source for statistics
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source ON cache_entries(source)
            """)

            conn.commit()

    def _serialize_data(self, data: Any) -> str:
        """Serialize data to JSON string."""
        try:
            return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize cache data: {e}")
            raise

    def _deserialize_data(self, data_str: str) -> Any:
        """Deserialize JSON string to data."""
        try:
            return json.loads(data_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to deserialize cache data: {e}")
            raise

    def get(self, key: str) -> CacheEntry | None:
        """Get cache entry by key."""
        with sqlite3.connect(self.cache_file) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM cache_entries WHERE key = ?", (key,))
            row = cursor.fetchone()

            if row is None:
                return None

            entry = CacheEntry(
                key=row["key"],
                data=self._deserialize_data(row["data"]),
                timestamp=row["timestamp"],
                source=row["source"],
                ttl=row["ttl"],
                size=row["size"],
            )

            # Check if expired
            if entry.is_expired():
                logger.debug(f"Cache entry {key} expired, removing")
                self.delete(key)
                return None

            logger.debug(f"Cache hit for {key} (age: {entry.age()}s)")
            return entry

    def put(self, key: str, data: Any, source: str, ttl: int | None = None) -> None:
        """Store data in cache."""
        if ttl is None:
            ttl = self.default_ttl

        serialized_data = self._serialize_data(data)
        size = len(serialized_data.encode("utf-8"))

        with sqlite3.connect(self.cache_file) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (key, data, timestamp, source, ttl, size)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (key, serialized_data, time.time(), source, ttl, size),
            )
            conn.commit()

        logger.debug(f"Cached {key} from {source} ({size} bytes, TTL: {ttl}s)")

    def delete(self, key: str) -> bool:
        """Delete cache entry by key."""
        with sqlite3.connect(self.cache_file) as conn:
            cursor = conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

    def clear(self, source: str | None = None) -> int:
        """Clear cache entries.

        Args:
            source: If specified, only clear entries from this source

        Returns:
            Number of entries deleted
        """
        with sqlite3.connect(self.cache_file) as conn:
            if source:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE source = ?", (source,)
                )
            else:
                cursor = conn.execute("DELETE FROM cache_entries")
            conn.commit()

            deleted_count = cursor.rowcount
            logger.info(
                f"Cleared {deleted_count} cache entries"
                + (f" from {source}" if source else "")
            )
            return deleted_count

    def cleanup_expired(self) -> int:
        """Remove expired cache entries."""
        current_time = time.time()

        with sqlite3.connect(self.cache_file) as conn:
            cursor = conn.execute(
                """
                DELETE FROM cache_entries
                WHERE ? - timestamp > ttl
            """,
                (current_time,),
            )
            conn.commit()

            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired cache entries")
            return deleted_count

    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.cache_file) as conn:
            conn.row_factory = sqlite3.Row

            # Overall stats
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_entries,
                    SUM(size) as total_size,
                    AVG(size) as avg_size,
                    MIN(timestamp) as oldest_entry,
                    MAX(timestamp) as newest_entry
                FROM cache_entries
            """)
            overall = cursor.fetchone()

            # Stats by source
            cursor = conn.execute("""
                SELECT
                    source,
                    COUNT(*) as count,
                    SUM(size) as total_size,
                    AVG(size) as avg_size
                FROM cache_entries
                GROUP BY source
                ORDER BY count DESC
            """)
            by_source = cursor.fetchall()

            # Expired entries
            current_time = time.time()
            cursor = conn.execute(
                """
                SELECT COUNT(*) as expired_count
                FROM cache_entries
                WHERE ? - timestamp > ttl
            """,
                (current_time,),
            )
            expired = cursor.fetchone()

            return {
                "total_entries": overall["total_entries"] or 0,
                "total_size_bytes": overall["total_size"] or 0,
                "average_size_bytes": overall["avg_size"] or 0,
                "oldest_entry_age": int(
                    current_time - (overall["oldest_entry"] or current_time)
                ),
                "newest_entry_age": int(
                    current_time - (overall["newest_entry"] or current_time)
                ),
                "expired_entries": expired["expired_count"] or 0,
                "by_source": [dict(row) for row in by_source],
            }

    def get_cache_key(self, source: str, identifier_type: str, value: str) -> str:
        """Generate standardized cache key."""
        return f"{source}:{identifier_type}:{value}"

    def get_search_cache_key(self, source: str, title: str, author: str) -> str:
        """Generate cache key for search queries."""
        query_hash = hash(f"{title}|{author}")
        return f"{source}:search:{query_hash}"


class CachedDataSourceMixin:
    """Mixin to add caching capabilities to data sources."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cache: ResponseCache | None = None
        self._cache_enabled = True

    def set_cache(self, cache: ResponseCache) -> None:
        """Set cache instance."""
        self._cache = cache

    def enable_cache(self, enabled: bool = True) -> None:
        """Enable or disable caching."""
        self._cache_enabled = enabled

    @asynccontextmanager
    async def _cached_request(self, cache_key: str, ttl: int | None = None) -> Any:
        """Context manager for cached requests."""
        if not self._cache_enabled or not self._cache:
            yield None, False
            return

        # Try to get from cache
        cached_entry = self._cache.get(cache_key)
        if cached_entry:
            yield cached_entry.data, True
            return

        # Cache miss - yield None and expect caller to store result
        result_data = None

        class CacheResult:
            def __init__(self, name: str, cache: ResponseCache | None) -> None:
                self.name = name
                self._cache = cache

            def store(self, data: Any) -> None:
                nonlocal result_data
                result_data = data
                if self._cache:
                    self._cache.put(cache_key, data, self.name, ttl)

        cache_result = CacheResult(getattr(self, "name", "unknown"), self._cache)

        yield cache_result, False

    def clear_cache(self) -> int:
        """Clear cache entries for this data source."""
        if self._cache:
            return self._cache.clear(getattr(self, "name", None))
        return 0


# Global cache instance
_global_cache: ResponseCache | None = None


def get_cache() -> ResponseCache:
    """Get global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = ResponseCache()
    return _global_cache


def cleanup_cache() -> int:
    """Cleanup expired entries from global cache."""
    cache = get_cache()
    return cache.cleanup_expired()


def clear_cache(source: str | None = None) -> int:
    """Clear global cache."""
    cache = get_cache()
    return cache.clear(source)


def get_cache_statistics() -> dict[str, Any]:
    """Get global cache statistics."""
    cache = get_cache()
    return cache.get_statistics()
