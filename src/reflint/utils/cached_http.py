"""Cached HTTP client wrapper with TTL caching for repeated lookups."""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, cast
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

import httpx2 as httpx
from loguru import logger


class HttpResponseCache:
    """Small TTL cache for serialized HTTP responses."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._entries: dict[str, tuple[Any, float | None]] = {}

    def get(self, key: str) -> Any | None:
        """Return cached value if present and not expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None

        value, expires_at = entry
        if expires_at is not None and time.time() >= expires_at:
            self._entries.pop(key, None)
            return None

        return value

    def set(self, key: str, value: Any, expire: float | None = None) -> None:
        """Store value with optional TTL."""
        expires_at = time.time() + expire if expire is not None else None
        self._entries[key] = (value, expires_at)

    def clear(self) -> None:
        """Clear all cached values."""
        self._entries.clear()

    def cull(self) -> int:
        """Remove expired entries and return the number removed."""
        now = time.time()
        expired_keys = [
            key
            for key, (_, expires_at) in self._entries.items()
            if expires_at is not None and now >= expires_at
        ]
        for key in expired_keys:
            self._entries.pop(key, None)
        return len(expired_keys)

    def volume(self) -> int:
        """Approximate cache size in bytes."""
        return sum(len(repr(value)) for value, _ in self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)


_cache: HttpResponseCache | None = None


def get_cache() -> HttpResponseCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        # Create cache directory in user's cache directory
        cache_dir = Path.home() / ".cache" / "reflint" / "http_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        _cache = HttpResponseCache(cache_dir)
        logger.debug(f"Initialized HTTP cache at {cache_dir}")

    return _cache


def generate_cache_key(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    """Generate a cache key from URL, params, and relevant headers.

    Args:
        url: The request URL
        params: Query parameters dict
        headers: Request headers dict

    Returns:
        SHA256 hash of the normalized request components
    """
    # Start with the URL
    key_components = [url]

    # Add sorted parameters
    if params:
        # Convert all values to strings and sort by key
        sorted_params = sorted(
            (str(k), str(v)) for k, v in params.items() if v is not None
        )
        if sorted_params:
            key_components.append(urlencode(sorted_params))

    # Add relevant headers that might affect response content
    if headers:
        # Only include headers that might affect response content
        relevant_headers = {
            "accept",
            "accept-encoding",
            "user-agent",
            "x-api-key",
            "authorization",
            "api_key",
        }
        filtered_headers = {
            k.lower(): v for k, v in headers.items() if k.lower() in relevant_headers
        }
        if filtered_headers:
            sorted_headers = sorted(filtered_headers.items())
            key_components.append(json.dumps(sorted_headers, sort_keys=True))

    # Create key string and hash it
    key_string = "|".join(key_components)
    return hashlib.sha256(key_string.encode()).hexdigest()


async def cached_httpx_get(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = 30.0,
    follow_redirects: bool = True,
    ttl: int = 7 * 24 * 60 * 60,  # 7 days in seconds
    force_refresh: bool = False,
    rate_limit_func: Callable[[], Awaitable[None]] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """Cached HTTP GET request.

    Args:
        url: The URL to request
        params: Query parameters
        headers: Request headers
        timeout: Request timeout in seconds
        follow_redirects: Whether to follow redirects
        ttl: Cache TTL in seconds (default 7 days)
        force_refresh: If True, bypass cache and refresh
        rate_limit_func: Optional async function to call before making HTTP request (only if not cached)
        **kwargs: Additional httpx.get arguments

    Returns:
        httpx.Response object (may be from cache)

    Raises:
        httpx.HTTPError: For HTTP errors
        Exception: For other errors
    """
    cache = get_cache()

    # Generate cache key
    cache_key = generate_cache_key(url, params, headers)

    # Check cache first (unless forcing refresh)
    if not force_refresh:
        try:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                # Reconstruct response from cached data
                cached_response = _deserialize_response(cached_data)
                logger.debug(f"Cache HIT for {url}")
                return cached_response
        except Exception as e:
            logger.warning(f"Cache read error for {url}: {e}")

    # Cache miss or forced refresh - make actual request
    logger.debug(f"Cache MISS for {url} - making HTTP request")

    # Apply rate limiting only for actual HTTP requests (not cached responses)
    if rate_limit_func is not None:
        await rate_limit_func()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url=url,
                params=params,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
                **kwargs,
            )

            # Only cache successful responses (2xx status codes).
            status_code = response.status_code
            if isinstance(status_code, int) and 200 <= status_code < 300:
                try:
                    # Serialize response for caching
                    cached_data = _serialize_response(response)
                    cache.set(cache_key, cached_data, expire=ttl)
                    logger.debug(f"Cached successful response for {url} (TTL: {ttl}s)")
                except Exception as e:
                    logger.warning(f"Cache write error for {url}: {e}")
            else:
                logger.debug(
                    f"Not caching non-2xx response for {url} (status: {status_code})"
                )

            return response

        except Exception as e:
            logger.error(f"HTTP request failed for {url}: {e}")
            raise


def _serialize_response(response: httpx.Response) -> dict[str, Any]:
    """Serialize httpx.Response to a cacheable dict."""
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "content": response.content,
        "url": str(response.url),
        "cached_at": time.time(),
    }


def _deserialize_response(cached_data: dict[str, Any]) -> httpx.Response:
    """Deserialize cached data back to httpx.Response-like object."""

    # Create a mock response object with the essential attributes
    class CachedResponse:
        def __init__(self, data: dict[str, Any]) -> None:
            self.status_code = data["status_code"]
            self.headers = httpx.Headers(data["headers"])
            self.content = data["content"]
            self.url = httpx.URL(data["url"])
            self._cached_at = data.get("cached_at", time.time())

        def json(self) -> Any:
            """Parse JSON content."""
            return json.loads(self.content.decode())

        @property
        def text(self) -> str:
            """Get text content."""
            content = cast(bytes, self.content)
            return content.decode()

        def raise_for_status(self) -> None:
            """Raise exception for bad status codes."""
            if 400 <= self.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"HTTP {self.status_code}", request=None, response=self
                )

    return cast(httpx.Response, CachedResponse(cached_data))


def clear_cache() -> None:
    """Clear the entire HTTP cache."""
    cache = get_cache()
    cache.clear()
    logger.info("HTTP cache cleared")


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    cache = get_cache()
    return {
        "size": len(cache),
        "volume": cache.volume(),
        "directory": str(cache.directory),
    }


def cleanup_expired_cache() -> int:
    """Remove expired cache entries and return count of removed items."""
    cache = get_cache()
    removed_count = 0

    # Note: diskcache automatically handles expiration, but we can force cleanup
    try:
        removed_count = cache.cull()
        logger.debug(f"Cache cleanup removed {removed_count} expired entries")
    except Exception as e:
        logger.warning(f"Cache cleanup error: {e}")

    return removed_count
