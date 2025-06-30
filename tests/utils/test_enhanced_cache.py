"""Tests for enhanced caching system."""

import tempfile
import time
from pathlib import Path

import pytest

from reflint.utils.enhanced_cache import (
    CacheConfig,
    CacheEntry,
    CacheStats,
    EnhancedCache,
    RequestDeduplicator,
    cached,
    deduplicated,
    get_cache,
    get_deduplicator,
)


class TestCacheStats:
    """Test the CacheStats dataclass."""

    def test_cache_stats_init(self):
        """Test CacheStats initialization."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 1.0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats()
        stats.hits = 7
        stats.misses = 3
        stats.total_requests = 10

        assert abs(stats.hit_rate - 0.7) < 1e-10
        assert abs(stats.miss_rate - 0.3) < 1e-10

    def test_zero_requests(self):
        """Test stats with zero requests."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 1.0


class TestCacheConfig:
    """Test the CacheConfig dataclass."""

    def test_cache_config_init(self):
        """Test CacheConfig initialization."""
        config = CacheConfig()
        assert config.default_ttl == 3600.0
        assert config.max_size == 1000
        assert config.eviction_policy == "lru"
        assert "crossref" in config.source_ttls

    def test_get_ttl_for_source(self):
        """Test TTL retrieval for different sources."""
        config = CacheConfig()

        assert config.get_ttl_for_source("crossref") == 86400.0
        assert config.get_ttl_for_source("arxiv") == 7200.0
        assert config.get_ttl_for_source("unknown_source") == 3600.0

    def test_custom_source_ttls(self):
        """Test custom source TTLs."""
        custom_ttls = {"custom_source": 1234.0}
        config = CacheConfig(source_ttls=custom_ttls)

        assert config.get_ttl_for_source("custom_source") == 1234.0
        assert config.get_ttl_for_source("crossref") == 3600.0  # Falls back to default


class TestCacheEntry:
    """Test the CacheEntry dataclass."""

    def test_cache_entry_init(self):
        """Test CacheEntry initialization."""
        entry = CacheEntry(
            key="test_key", value="test_value", timestamp=1234567890.0, ttl=3600.0
        )

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.ttl == 3600.0

    def test_is_expired(self):
        """Test expiration checking."""
        # Not expired
        entry = CacheEntry(key="test", value="value", timestamp=time.time(), ttl=3600.0)
        assert not entry.is_expired

        # Expired
        old_entry = CacheEntry(
            key="test",
            value="value",
            timestamp=time.time() - 7200.0,  # 2 hours ago
            ttl=3600.0,  # 1 hour TTL
        )
        assert old_entry.is_expired

    def test_age_property(self):
        """Test age calculation."""
        past_time = time.time() - 100.0
        entry = CacheEntry(key="test", value="value", timestamp=past_time, ttl=3600.0)

        assert entry.age >= 100.0

    def test_touch_method(self):
        """Test access tracking."""
        entry = CacheEntry(key="test", value="value", timestamp=time.time(), ttl=3600.0)

        initial_count = entry.access_count
        initial_access = entry.last_access

        time.sleep(0.01)  # Small delay
        entry.touch()

        assert entry.access_count == initial_count + 1
        assert entry.last_access > initial_access


class TestEnhancedCache:
    """Test the EnhancedCache class."""

    def test_init(self):
        """Test EnhancedCache initialization."""
        cache = EnhancedCache()
        assert isinstance(cache.config, CacheConfig)
        assert isinstance(cache.stats, CacheStats)

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = CacheConfig(default_ttl=1800.0, max_size=500)
        cache = EnhancedCache(config=config)
        assert cache.config.default_ttl == 1800.0
        assert cache.config.max_size == 500

    def test_generate_key(self):
        """Test cache key generation."""
        cache = EnhancedCache()

        # String key
        key1 = cache._generate_key("test_string")
        key2 = cache._generate_key("test_string")
        assert key1 == key2

        # Dict key
        dict_data = {"field": "value", "number": 123}
        key3 = cache._generate_key(dict_data)
        key4 = cache._generate_key({"number": 123, "field": "value"})  # Different order
        assert key3 == key4  # Should be same due to sort_keys=True

        # With source
        key5 = cache._generate_key("test", "source1")
        key6 = cache._generate_key("test", "source2")
        assert key5 != key6

    def test_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = EnhancedCache()

        # Set and get
        cache.set("test_key", "test_value")
        result = cache.get("test_key")
        assert result == "test_value"

        # Stats should be updated
        assert cache.stats.sets == 1
        assert cache.stats.hits == 1
        assert cache.stats.total_requests == 1

    def test_get_nonexistent(self):
        """Test getting non-existent key."""
        cache = EnhancedCache()
        result = cache.get("nonexistent")
        assert result is None
        assert cache.stats.misses == 1

    def test_ttl_expiration(self):
        """Test TTL-based expiration."""
        cache = EnhancedCache()

        # Set with short TTL
        cache.set("short_ttl", "value", ttl=0.1)

        # Should be available immediately
        assert cache.get("short_ttl") == "value"

        # Wait for expiration
        time.sleep(0.2)

        # Should be expired
        assert cache.get("short_ttl") is None

    def test_source_based_ttl(self):
        """Test source-based TTL selection."""
        cache = EnhancedCache()

        # Set with source
        cache.set("arxiv_data", "value", source="arxiv")

        # Check that the entry has the correct TTL
        key = cache._generate_key("arxiv_data", "arxiv")
        entry = cache._memory_cache[key]
        assert entry.ttl == cache.config.get_ttl_for_source("arxiv")

    def test_delete(self):
        """Test cache deletion."""
        cache = EnhancedCache()

        cache.set("to_delete", "value")
        assert cache.get("to_delete") == "value"

        deleted = cache.delete("to_delete")
        assert deleted
        assert cache.get("to_delete") is None
        assert cache.stats.deletes == 1

    def test_delete_nonexistent(self):
        """Test deleting non-existent key."""
        cache = EnhancedCache()
        deleted = cache.delete("nonexistent")
        assert not deleted

    def test_clear_all(self):
        """Test clearing all cache entries."""
        cache = EnhancedCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2", source="test")

        count = cache.clear()
        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_clear_by_source(self):
        """Test clearing entries by source."""
        cache = EnhancedCache()

        cache.set("key1", "value1", source="source1")
        cache.set("key2", "value2", source="source2")
        cache.set("key3", "value3")  # No source

        count = cache.clear(source="source1")
        assert count == 1
        assert cache.get("key1", "source1") is None
        assert cache.get("key2", "source2") == "value2"
        assert cache.get("key3") == "value3"

    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache = EnhancedCache()

        # Add entries with different TTLs
        cache.set("short", "value1", ttl=0.1)
        cache.set("long", "value2", ttl=10.0)

        # Wait for short TTL to expire
        time.sleep(0.2)

        # Cleanup
        count = cache.cleanup_expired()
        assert count == 1
        assert cache.get("short") is None
        assert cache.get("long") == "value2"

    def test_eviction_lru(self):
        """Test LRU eviction policy."""
        config = CacheConfig(max_size=2, eviction_policy="lru")
        cache = EnhancedCache(config=config, enable_disk_cache=False)

        # Fill cache
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Access key1 to make it more recently used
        cache.get("key1")

        # Add third item, should evict key2 (least recently used)
        cache.set("key3", "value3")

        assert cache.get("key1") == "value1"  # Should still be there
        assert cache.get("key2") is None  # Should be evicted
        assert cache.get("key3") == "value3"  # Should be there

    def test_get_cache_info(self):
        """Test cache information retrieval."""
        cache = EnhancedCache()

        cache.set("test", "value")
        cache.get("test")
        cache.get("nonexistent")

        info = cache.get_cache_info()

        assert "config" in info
        assert "stats" in info
        assert "size" in info
        assert info["stats"]["hits"] == 1
        assert info["stats"]["misses"] == 1
        assert info["size"]["memory_entries"] == 1

    @pytest.mark.skipif(
        not hasattr(tempfile, "TemporaryDirectory"),
        reason="TemporaryDirectory not available",
    )
    def test_disk_cache_integration(self):
        """Test disk cache integration if available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache = EnhancedCache(cache_dir=cache_dir, enable_disk_cache=True)

            # This test will pass regardless of whether diskcache is available
            # If diskcache is not available, disk cache will be None
            cache.set("test", "value")
            result = cache.get("test")
            assert result == "value"


class TestRequestDeduplicator:
    """Test the RequestDeduplicator class."""

    def test_init(self):
        """Test RequestDeduplicator initialization."""
        dedup = RequestDeduplicator()
        assert dedup.get_pending_count() == 0

    def test_duplicate_detection(self):
        """Test duplicate request detection."""
        dedup = RequestDeduplicator()

        assert not dedup.is_duplicate("request1")

        dedup.add_pending("request1")
        assert dedup.is_duplicate("request1")
        assert not dedup.is_duplicate("request2")

    def test_complete_request(self):
        """Test request completion."""
        dedup = RequestDeduplicator()

        dedup.add_pending("request1")
        assert dedup.get_pending_count() == 1

        dedup.complete_request("request1")
        assert dedup.get_pending_count() == 0
        assert not dedup.is_duplicate("request1")

    def test_clear_pending(self):
        """Test clearing all pending requests."""
        dedup = RequestDeduplicator()

        dedup.add_pending("request1")
        dedup.add_pending("request2")
        assert dedup.get_pending_count() == 2

        dedup.clear_pending()
        assert dedup.get_pending_count() == 0


class TestCachedDecorator:
    """Test the @cached decorator."""

    def test_cached_decorator(self):
        """Test basic caching decorator functionality."""
        call_count = 0

        @cached()
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute function
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment

        # Different argument should execute function
        result3 = expensive_function(6)
        assert result3 == 12
        assert call_count == 2

    def test_cached_with_source(self):
        """Test caching decorator with source."""

        @cached(source="test_source")
        def test_function(x):
            return x + 1

        result = test_function(5)
        assert result == 6

        # Function should be cached
        result2 = test_function(5)
        assert result2 == 6

    def test_cached_with_ttl(self):
        """Test caching decorator with custom TTL."""
        call_count = 0

        @cached(ttl=0.1)
        def short_ttl_function(x):
            nonlocal call_count
            call_count += 1
            return x * 3

        # First call
        result1 = short_ttl_function(2)
        assert result1 == 6
        assert call_count == 1

        # Wait for TTL to expire
        time.sleep(0.2)

        # Should execute function again
        result2 = short_ttl_function(2)
        assert result2 == 6
        assert call_count == 2


class TestDeduplicatedDecorator:
    """Test the @deduplicated decorator."""

    def test_deduplicated_decorator(self):
        """Test basic deduplication decorator functionality."""
        call_count = 0

        @deduplicated
        def test_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should work
        result1 = test_function(5)
        assert result1 == 10
        assert call_count == 1

        # Clear pending to allow next call
        get_deduplicator().clear_pending()

        # Second call should work after clearing
        result2 = test_function(5)
        assert result2 == 10
        assert call_count == 2


class TestGlobalInstances:
    """Test global cache and deduplicator instances."""

    def test_get_cache(self):
        """Test global cache instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2  # Should be the same instance

    def test_get_deduplicator(self):
        """Test global deduplicator instance."""
        dedup1 = get_deduplicator()
        dedup2 = get_deduplicator()
        assert dedup1 is dedup2  # Should be the same instance
