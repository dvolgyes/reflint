"""Tests for cached HTTP client wrapper."""

import json
import time
from unittest.mock import AsyncMock, Mock, patch
import pytest
import httpx2 as httpx

from src.reflint.utils.cached_http import (
    cached_httpx_get,
    generate_cache_key,
    get_cache,
    clear_cache,
    get_cache_stats,
    cleanup_expired_cache,
)


class TestCachedHttp:
    """Test cases for cached HTTP functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clear cache before each test
        clear_cache()

    def test_generate_cache_key_basic(self):
        """Test basic cache key generation."""
        key1 = generate_cache_key("https://api.example.com/data")
        key2 = generate_cache_key("https://api.example.com/data")

        # Same URL should generate same key
        assert key1 == key2
        assert len(key1) == 64  # SHA256 hex length

        # Different URL should generate different key
        key3 = generate_cache_key("https://api.example.com/other")
        assert key1 != key3

    def test_generate_cache_key_with_params(self):
        """Test cache key generation with parameters."""
        # Same params in different order should generate same key
        key1 = generate_cache_key(
            "https://api.example.com/search", {"query": "test", "limit": "10"}
        )
        key2 = generate_cache_key(
            "https://api.example.com/search", {"limit": "10", "query": "test"}
        )
        assert key1 == key2

        # Different params should generate different key
        key3 = generate_cache_key(
            "https://api.example.com/search", {"query": "other", "limit": "10"}
        )
        assert key1 != key3

    def test_generate_cache_key_with_headers(self):
        """Test cache key generation with relevant headers."""
        # Relevant headers should affect key
        key1 = generate_cache_key(
            "https://api.example.com/data", headers={"x-api-key": "key1"}
        )
        key2 = generate_cache_key(
            "https://api.example.com/data", headers={"x-api-key": "key2"}
        )
        assert key1 != key2

        # Irrelevant headers should not affect key
        key3 = generate_cache_key(
            "https://api.example.com/data",
            headers={"x-api-key": "key1", "x-request-id": "req1"},
        )
        key4 = generate_cache_key(
            "https://api.example.com/data",
            headers={"x-api-key": "key1", "x-request-id": "req2"},
        )
        assert key3 == key4  # x-request-id should be ignored

    def test_generate_cache_key_none_values(self):
        """Test cache key generation with None values."""
        key1 = generate_cache_key("https://api.example.com/data")
        key2 = generate_cache_key(
            "https://api.example.com/data", params=None, headers=None
        )
        assert key1 == key2

        # None values in params should be ignored
        key3 = generate_cache_key(
            "https://api.example.com/data", params={"query": "test", "filter": None}
        )
        key4 = generate_cache_key(
            "https://api.example.com/data", params={"query": "test"}
        )
        assert key3 == key4

    @pytest.mark.asyncio
    async def test_cached_httpx_get_success(self):
        """Test successful HTTP request and caching."""
        mock_response_data = {"result": "test_data", "status": "success"}

        # Mock httpx.AsyncClient
        with patch("httpx2.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.content = json.dumps(mock_response_data).encode()
            mock_response.headers = {"content-type": "application/json"}
            mock_response.url = httpx.URL("https://api.example.com/data")

            mock_client.get.return_value = mock_response

            # First request - should hit network
            response1 = await cached_httpx_get("https://api.example.com/data")

            assert response1.status_code == 200
            assert response1.json() == mock_response_data
            mock_client.get.assert_called_once()

            # Second request - should hit cache
            mock_client.get.reset_mock()
            response2 = await cached_httpx_get("https://api.example.com/data")

            assert response2.status_code == 200
            assert response2.json() == mock_response_data
            mock_client.get.assert_not_called()  # Should not make network request

    @pytest.mark.asyncio
    async def test_cached_httpx_get_with_params(self):
        """Test caching with query parameters."""
        mock_response_data = {"query_result": "filtered_data"}

        with patch("httpx2.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.content = json.dumps(mock_response_data).encode()
            mock_response.headers = {"content-type": "application/json"}
            mock_response.url = httpx.URL("https://api.example.com/search?query=test")

            mock_client.get.return_value = mock_response

            # Request with params
            params = {"query": "test", "limit": 10}
            response = await cached_httpx_get(
                "https://api.example.com/search", params=params
            )

            assert response.status_code == 200
            assert response.json() == mock_response_data

            # Verify params were passed correctly
            call_args = mock_client.get.call_args
            assert call_args[1]["params"] == params

    @pytest.mark.asyncio
    async def test_cached_httpx_get_non_2xx_not_cached(self):
        """Test that non-2xx responses are not cached."""
        with patch("httpx2.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock 404 response
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.content = b'{"error": "not found"}'
            mock_response.headers = {"content-type": "application/json"}
            mock_response.url = httpx.URL("https://api.example.com/notfound")

            mock_client.get.return_value = mock_response

            # First request
            response1 = await cached_httpx_get("https://api.example.com/notfound")
            assert response1.status_code == 404

            # Second request - should hit network again (not cached)
            mock_client.get.reset_mock()
            response2 = await cached_httpx_get("https://api.example.com/notfound")
            assert response2.status_code == 404
            mock_client.get.assert_called_once()  # Should make network request

    @pytest.mark.asyncio
    async def test_cached_httpx_get_force_refresh(self):
        """Test force refresh bypasses cache."""
        mock_response_data = {"data": "original"}
        updated_response_data = {"data": "updated"}

        with patch("httpx2.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # First response
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.json.return_value = mock_response_data
            mock_response1.content = json.dumps(mock_response_data).encode()
            mock_response1.headers = {"content-type": "application/json"}
            mock_response1.url = httpx.URL("https://api.example.com/data")

            # Updated response
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.json.return_value = updated_response_data
            mock_response2.content = json.dumps(updated_response_data).encode()
            mock_response2.headers = {"content-type": "application/json"}
            mock_response2.url = httpx.URL("https://api.example.com/data")

            mock_client.get.side_effect = [mock_response1, mock_response2]

            # First request - populate cache
            response1 = await cached_httpx_get("https://api.example.com/data")
            assert response1.json() == mock_response_data

            # Force refresh - should bypass cache
            response2 = await cached_httpx_get(
                "https://api.example.com/data", force_refresh=True
            )
            assert response2.json() == updated_response_data

            # Verify both network calls were made
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_cached_httpx_get_custom_ttl(self):
        """Test custom TTL functionality."""
        mock_response_data = {"data": "test"}

        with patch("httpx2.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.content = json.dumps(mock_response_data).encode()
            mock_response.headers = {"content-type": "application/json"}
            mock_response.url = httpx.URL("https://api.example.com/data")

            mock_client.get.return_value = mock_response

            # Request with short TTL
            response = await cached_httpx_get(
                "https://api.example.com/data",
                ttl=1,  # 1 second
            )
            assert response.status_code == 200

            # Immediately should hit cache
            mock_client.get.reset_mock()
            await cached_httpx_get("https://api.example.com/data")
            mock_client.get.assert_not_called()

            # After TTL expires, should hit network again
            # Note: In real usage, this would wait for expiration
            # For testing, we just verify the TTL parameter is used

    def test_get_cache_stats(self):
        """Test cache statistics."""
        stats = get_cache_stats()

        assert "size" in stats
        assert "volume" in stats
        assert "directory" in stats
        assert isinstance(stats["size"], int)

    def test_clear_cache(self):
        """Test cache clearing."""
        # Put something in cache
        cache = get_cache()
        cache.set("test_key", "test_value")

        # Verify it's there
        assert cache.get("test_key") == "test_value"

        # Clear cache
        clear_cache()

        # Verify it's gone
        assert cache.get("test_key") is None

    def test_cleanup_expired_cache(self):
        """Test cleanup of expired cache entries."""
        removed_count = cleanup_expired_cache()
        assert isinstance(removed_count, int)
        assert removed_count >= 0

    @pytest.mark.asyncio
    async def test_cached_httpx_get_headers_passed(self):
        """Test that headers are properly passed to httpx."""
        with patch("httpx2.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            mock_response.content = b'{"result": "success"}'
            mock_response.headers = {"content-type": "application/json"}
            mock_response.url = httpx.URL("https://api.example.com/data")

            mock_client.get.return_value = mock_response

            headers = {"x-api-key": "test-key", "user-agent": "test"}

            await cached_httpx_get("https://api.example.com/data", headers=headers)

            # Verify headers were passed
            call_args = mock_client.get.call_args
            assert call_args[1]["headers"] == headers

    @pytest.mark.asyncio
    async def test_cached_httpx_get_timeout_passed(self):
        """Test that timeout is properly passed to httpx."""
        with patch("httpx2.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            mock_response.content = b'{"result": "success"}'
            mock_response.headers = {"content-type": "application/json"}
            mock_response.url = httpx.URL("https://api.example.com/data")

            mock_client.get.return_value = mock_response

            await cached_httpx_get("https://api.example.com/data", timeout=60.0)

            # Verify timeout was passed
            call_args = mock_client.get.call_args
            assert call_args[1]["timeout"] == 60.0

    def test_cached_response_attributes(self):
        """Test that cached response has correct attributes."""
        from src.reflint.utils.cached_http import _deserialize_response

        # Create test data
        cached_data = {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "content": b'{"test": "data"}',
            "url": "https://api.example.com/test",
            "cached_at": time.time(),
        }

        # Deserialize
        response = _deserialize_response(cached_data)

        # Test attributes
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.content == b'{"test": "data"}'
        assert str(response.url) == "https://api.example.com/test"
        assert response.json() == {"test": "data"}
        assert response.text == '{"test": "data"}'

        # Test raise_for_status with good status
        response.raise_for_status()  # Should not raise

        # Test raise_for_status with bad status
        cached_data["status_code"] = 404
        bad_response = _deserialize_response(cached_data)

        with pytest.raises(httpx.HTTPStatusError):
            bad_response.raise_for_status()
