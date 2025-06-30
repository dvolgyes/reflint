"""Tests for caching system."""

import tempfile
import time
from pathlib import Path


from reflint.utils.cache import ResponseCache, CacheEntry


class TestResponseCache:
    """Test the response cache system."""

    def test_cache_basic_operations(self):
        """Test basic cache operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.db"
            cache = ResponseCache(cache_file, default_ttl=60)

            # Test put and get
            test_data = {"key": "value", "number": 42}
            cache.put("test_key", test_data, "test_source")

            entry = cache.get("test_key")
            assert entry is not None
            assert entry.data == test_data
            assert entry.source == "test_source"
            assert not entry.is_expired()

    def test_cache_expiration(self):
        """Test cache entry expiration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.db"
            cache = ResponseCache(cache_file, default_ttl=1)  # 1 second TTL

            # Add entry with short TTL
            cache.put("test_key", {"data": "test"}, "test_source", ttl=1)

            # Should be available immediately
            entry = cache.get("test_key")
            assert entry is not None

            # Wait for expiration
            time.sleep(1.1)

            # Should be expired and removed
            entry = cache.get("test_key")
            assert entry is None

    def test_cache_statistics(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.db"
            cache = ResponseCache(cache_file)

            # Add some test data
            cache.put("key1", {"data": "test1"}, "source1")
            cache.put("key2", {"data": "test2"}, "source1")
            cache.put("key3", {"data": "test3"}, "source2")

            stats = cache.get_statistics()

            assert stats["total_entries"] == 3
            assert stats["by_source"][0]["source"] in ["source1", "source2"]
            assert stats["total_size_bytes"] > 0

    def test_cache_cleanup(self):
        """Test cleanup of expired entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.db"
            cache = ResponseCache(cache_file)

            # Add entries with different TTLs
            cache.put("short_ttl", {"data": "short"}, "test_source", ttl=1)
            cache.put("long_ttl", {"data": "long"}, "test_source", ttl=3600)

            # Wait for short TTL to expire
            time.sleep(1.1)

            # Cleanup expired entries
            deleted = cache.cleanup_expired()
            assert deleted == 1

            # Long TTL entry should still be there
            entry = cache.get("long_ttl")
            assert entry is not None

    def test_cache_clear(self):
        """Test cache clearing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.db"
            cache = ResponseCache(cache_file)

            # Add test data from different sources
            cache.put("key1", {"data": "test1"}, "source1")
            cache.put("key2", {"data": "test2"}, "source2")

            # Clear specific source
            deleted = cache.clear("source1")
            assert deleted == 1

            # Check that only source1 was cleared
            assert cache.get("key1") is None
            assert cache.get("key2") is not None

            # Clear all
            deleted = cache.clear()
            assert deleted == 1
            assert cache.get("key2") is None

    def test_cache_key_generation(self):
        """Test cache key generation."""
        cache = ResponseCache()

        # Test identifier cache key
        key = cache.get_cache_key("crossref", "doi", "10.1234/test")
        assert key == "crossref:doi:10.1234/test"

        # Test search cache key
        key = cache.get_search_cache_key(
            "semantic_scholar", "Test Title", "Test Author"
        )
        assert key.startswith("semantic_scholar:search:")
        assert len(key) > 30  # Should include hash

    def test_serialization(self):
        """Test data serialization and deserialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.db"
            cache = ResponseCache(cache_file)

            # Test complex data structure
            complex_data = {
                "string": "test",
                "number": 42,
                "list": [1, 2, 3],
                "nested": {"inner": "value"},
                "unicode": "tëst",
            }

            cache.put("complex_key", complex_data, "test_source")
            entry = cache.get("complex_key")

            assert entry is not None
            assert entry.data == complex_data

    def test_cache_entry_properties(self):
        """Test cache entry properties and methods."""
        # Create cache entry
        entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            timestamp=time.time() - 30,  # 30 seconds ago
            source="test_source",
            ttl=60,  # 60 second TTL
            size=100,
        )

        # Test properties
        assert not entry.is_expired()
        assert entry.age() >= 30

        # Test expired entry
        expired_entry = CacheEntry(
            key="expired_key",
            data={"test": "data"},
            timestamp=time.time() - 120,  # 2 minutes ago
            source="test_source",
            ttl=60,  # 1 minute TTL
        )

        assert expired_entry.is_expired()
        assert expired_entry.age() >= 120
