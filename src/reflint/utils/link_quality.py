"""Link quality management and dead link detection system.

This module provides tools for checking URL health, detecting dead links,
integrating with Internet Archive, and managing link quality.
"""

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger


@dataclass
class LinkStatus:
    """Represents the status of a URL."""

    url: str
    is_accessible: bool
    status_code: int | None
    redirect_url: str | None
    error_message: str | None
    response_time: float | None
    archived_url: str | None
    last_checked: float

    @property
    def is_redirect(self) -> bool:
        """Check if the URL redirects to another location."""
        return self.redirect_url is not None and self.redirect_url != self.url

    @property
    def is_dead(self) -> bool:
        """Check if the URL is considered dead."""
        return not self.is_accessible and self.status_code not in [
            429,
            503,
        ]  # Rate limiting/temp unavailable


@dataclass
class ArchiveResult:
    """Represents the result of an Internet Archive lookup."""

    original_url: str
    archived_url: str | None
    archive_date: str | None
    is_available: bool
    snapshot_count: int


class LinkQualityManager:
    """Manages link quality checking and enhancement."""

    def __init__(self, timeout: float = 10.0, max_retries: int = 2):
        """Initialize the link quality manager.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._cache: dict[str, LinkStatus] = {}
        self._archive_cache: dict[str, ArchiveResult] = {}

        # User agent that's commonly accepted
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ReflInt/1.0; +https://github.com/dvolgyes/reflint)"
        }

    async def check_url_status(self, url: str, use_cache: bool = True) -> LinkStatus:
        """Check the status of a single URL.

        Args:
            url: URL to check
            use_cache: Whether to use cached results

        Returns:
            LinkStatus object with check results
        """
        # Check cache first
        if use_cache and url in self._cache:
            cached = self._cache[url]
            # Use cache if checked within last hour
            if time.time() - cached.last_checked < 3600:
                return cached

        logger.debug(f"Checking URL status: {url}")

        start_time = time.time()
        status = LinkStatus(
            url=url,
            is_accessible=False,
            status_code=None,
            redirect_url=None,
            error_message=None,
            response_time=None,
            archived_url=None,
            last_checked=time.time(),
        )

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, headers=self.headers, follow_redirects=True
            ) as client:
                for attempt in range(self.max_retries + 1):
                    try:
                        response = await client.head(url)

                        status.status_code = response.status_code
                        status.response_time = time.time() - start_time
                        status.is_accessible = response.status_code < 400

                        # Check for redirects
                        if response.history:
                            status.redirect_url = str(response.url)

                        break

                    except httpx.TimeoutException:
                        if attempt == self.max_retries:
                            status.error_message = "Timeout"
                        else:
                            await asyncio.sleep(1)  # Brief delay before retry

                    except httpx.RequestError as e:
                        if attempt == self.max_retries:
                            status.error_message = f"Request error: {str(e)}"
                        else:
                            await asyncio.sleep(1)

        except Exception as e:
            status.error_message = f"Unexpected error: {str(e)}"
            logger.warning(f"Error checking URL {url}: {e}")

        # Cache the result
        self._cache[url] = status
        return status

    async def check_multiple_urls(
        self, urls: list[str], concurrent_limit: int = 10
    ) -> dict[str, LinkStatus]:
        """Check multiple URLs concurrently.

        Args:
            urls: List of URLs to check
            concurrent_limit: Maximum number of concurrent requests

        Returns:
            Dictionary mapping URLs to their LinkStatus
        """
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def check_with_semaphore(url: str) -> tuple[str, LinkStatus]:
            async with semaphore:
                status = await self.check_url_status(url)
                return url, status

        tasks = [check_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        status_map = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in concurrent URL check: {result}")
                continue
            url, status = result
            status_map[url] = status

        return status_map

    async def find_archive_url(self, url: str, use_cache: bool = True) -> ArchiveResult:
        """Find an archived version of a URL using Internet Archive.

        Args:
            url: Original URL to find in archives
            use_cache: Whether to use cached results

        Returns:
            ArchiveResult with archive information
        """
        if use_cache and url in self._archive_cache:
            return self._archive_cache[url]

        logger.debug(f"Looking up archive for URL: {url}")

        result = ArchiveResult(
            original_url=url,
            archived_url=None,
            archive_date=None,
            is_available=False,
            snapshot_count=0,
        )

        try:
            # Use Wayback Machine CDX API
            cdx_url = "http://web.archive.org/cdx/search/cdx"
            params = {
                "url": url,
                "output": "json",
                "limit": "5",  # Get recent snapshots
                "sort": "timestamp",
                "order": "desc",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(cdx_url, params=params)

                if response.status_code == 200:
                    data = response.json()

                    if len(data) > 1:  # First row is headers
                        # Get the most recent snapshot
                        snapshot = data[1]
                        timestamp = snapshot[1]
                        original = snapshot[2]

                        # Format archive URL
                        result.archived_url = (
                            f"https://web.archive.org/web/{timestamp}/{original}"
                        )
                        result.archive_date = timestamp
                        result.is_available = True
                        result.snapshot_count = len(data) - 1

        except Exception as e:
            logger.debug(f"Archive lookup failed for {url}: {e}")

        # Cache the result
        self._archive_cache[url] = result
        return result

    async def suggest_https_upgrade(self, url: str) -> str | None:
        """Suggest HTTPS upgrade for HTTP URLs if available.

        Args:
            url: Original URL

        Returns:
            HTTPS URL if upgrade is available, None otherwise
        """
        if not url.startswith("http://"):
            return None

        https_url = url.replace("http://", "https://", 1)
        status = await self.check_url_status(https_url)

        if status.is_accessible:
            return https_url

        return None

    async def resolve_redirect_chain(
        self, url: str, max_redirects: int = 10
    ) -> list[str]:
        """Resolve the complete redirect chain for a URL.

        Args:
            url: Starting URL
            max_redirects: Maximum number of redirects to follow

        Returns:
            List of URLs in the redirect chain
        """
        chain = [url]
        current_url = url

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, headers=self.headers, follow_redirects=False
            ) as client:
                for _ in range(max_redirects):
                    response = await client.head(current_url)

                    if response.status_code in [301, 302, 303, 307, 308]:
                        location = response.headers.get("location")
                        if location:
                            # Handle relative redirects
                            next_url = urljoin(current_url, location)
                            if next_url in chain:  # Avoid infinite loops
                                break
                            chain.append(next_url)
                            current_url = next_url
                        else:
                            break
                    else:
                        break

        except Exception as e:
            logger.debug(f"Error resolving redirect chain for {url}: {e}")

        return chain

    def extract_urls_from_entry(self, entry: dict[str, Any]) -> list[str]:
        """Extract all URLs from a BibTeX entry.

        Args:
            entry: BibTeX entry dictionary

        Returns:
            List of URLs found in the entry
        """
        urls = []
        url_pattern = re.compile(
            r"https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*)?(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?",
            re.IGNORECASE,
        )

        # Check common URL fields
        url_fields = ["url", "howpublished", "note", "eprint"]

        for field in url_fields:
            if field in entry:
                value = str(entry[field])
                found_urls = url_pattern.findall(value)
                urls.extend(found_urls)

        # Also check other fields for embedded URLs
        for field, value in entry.items():
            if field not in url_fields:
                value_str = str(value)
                found_urls = url_pattern.findall(value_str)
                urls.extend(found_urls)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    async def enhance_entry_urls(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Enhance URLs in a BibTeX entry.

        Args:
            entry: BibTeX entry to enhance

        Returns:
            Enhanced entry with improved URLs
        """
        enhanced_entry = entry.copy()
        urls = self.extract_urls_from_entry(entry)

        if not urls:
            return enhanced_entry

        # Check all URLs
        status_map = await self.check_multiple_urls(urls)

        for original_url in urls:
            status = status_map.get(original_url)
            if not status:
                continue

            replacement_url = None

            # If URL is dead, try to find an archive
            if status.is_dead:
                archive_result = await self.find_archive_url(original_url)
                if archive_result.is_available:
                    replacement_url = archive_result.archived_url
                    logger.info(
                        f"Replaced dead URL with archive: {original_url} -> {replacement_url}"
                    )

            # If URL redirects, consider using the final destination
            elif status.is_redirect and status.redirect_url:
                # Only replace if the redirect is to a different domain or significantly different path
                original_parsed = urlparse(original_url)
                redirect_parsed = urlparse(status.redirect_url)

                if (
                    original_parsed.netloc != redirect_parsed.netloc
                    or len(status.redirect_url) < len(original_url) * 0.8
                ):
                    replacement_url = status.redirect_url
                    logger.info(
                        f"Replaced redirected URL: {original_url} -> {replacement_url}"
                    )

            # Try HTTPS upgrade for HTTP URLs
            elif original_url.startswith("http://"):
                https_url = await self.suggest_https_upgrade(original_url)
                if https_url:
                    replacement_url = https_url
                    logger.info(
                        f"Upgraded to HTTPS: {original_url} -> {replacement_url}"
                    )

            # Apply replacement if we found a better URL
            if replacement_url:
                for field, value in enhanced_entry.items():
                    if isinstance(value, str) and original_url in value:
                        enhanced_entry[field] = value.replace(
                            original_url, replacement_url
                        )

        return enhanced_entry

    def get_dead_link_report(
        self, urls: list[str], status_map: dict[str, LinkStatus]
    ) -> dict[str, Any]:
        """Generate a report of dead links and suggestions.

        Args:
            urls: List of URLs that were checked
            status_map: Mapping of URLs to their status

        Returns:
            Report dictionary with dead link analysis
        """
        dead_links = []
        redirected_links = []
        https_candidates = []

        for url in urls:
            status = status_map.get(url)
            if not status:
                continue

            if status.is_dead:
                dead_links.append(
                    {
                        "url": url,
                        "status_code": status.status_code,
                        "error": status.error_message,
                    }
                )

            elif status.is_redirect:
                redirected_links.append(
                    {
                        "url": url,
                        "redirect_to": status.redirect_url,
                        "status_code": status.status_code,
                    }
                )

            elif url.startswith("http://"):
                https_candidates.append(url)

        return {
            "total_urls": len(urls),
            "dead_links": dead_links,
            "redirected_links": redirected_links,
            "https_candidates": https_candidates,
            "dead_count": len(dead_links),
            "redirect_count": len(redirected_links),
            "https_candidate_count": len(https_candidates),
        }


class URLShortenerDetector:
    """Detects and resolves URL shorteners."""

    SHORTENER_DOMAINS = {
        "bit.ly",
        "tinyurl.com",
        "goo.gl",
        "t.co",
        "ow.ly",
        "is.gd",
        "buff.ly",
        "adf.ly",
        "bc.vc",
        "cli.re",
        "short.link",
        "tiny.cc",
        "rb.gy",
        "cutt.ly",
        "rebrand.ly",
        "bl.ink",
        "switchy.io",
    }

    @classmethod
    def is_shortened_url(cls, url: str) -> bool:
        """Check if a URL appears to be from a URL shortener.

        Args:
            url: URL to check

        Returns:
            True if the URL appears to be shortened
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]

        return domain in cls.SHORTENER_DOMAINS

    @classmethod
    async def resolve_shortened_url(cls, url: str, timeout: float = 10.0) -> str | None:
        """Resolve a shortened URL to its final destination.

        Args:
            url: Shortened URL
            timeout: Request timeout

        Returns:
            Final URL or None if resolution failed
        """
        if not cls.is_shortened_url(url):
            return url

        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                response = await client.head(url)
                return str(response.url)
        except Exception:
            return None


async def check_entry_link_quality(entry: dict[str, Any]) -> dict[str, Any]:
    """Convenience function to check and enhance URLs in a BibTeX entry.

    Args:
        entry: BibTeX entry to check

    Returns:
        Dictionary with enhanced entry and link quality report
    """
    manager = LinkQualityManager()

    # Extract URLs
    urls = manager.extract_urls_from_entry(entry)

    if not urls:
        return {
            "enhanced_entry": entry,
            "link_report": {
                "total_urls": 0,
                "dead_links": [],
                "redirected_links": [],
                "https_candidates": [],
                "dead_count": 0,
                "redirect_count": 0,
                "https_candidate_count": 0,
            },
        }

    # Check URL status
    status_map = await manager.check_multiple_urls(urls)

    # Enhance the entry
    enhanced_entry = await manager.enhance_entry_urls(entry)

    # Generate report
    report = manager.get_dead_link_report(urls, status_map)

    return {"enhanced_entry": enhanced_entry, "link_report": report}
