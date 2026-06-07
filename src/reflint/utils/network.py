"""Network utilities for URL validation and link checking."""

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse
from enum import Enum

import httpx2 as httpx
from loguru import logger

if TYPE_CHECKING:
    from ..core.entry import BibTeXEntry


class LinkStatus(Enum):
    """Status of URL accessibility check."""

    ACCESSIBLE = "accessible"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    TIMEOUT = "timeout"
    REDIRECT = "redirect"
    SSL_ERROR = "ssl_error"
    CONNECTION_ERROR = "connection_error"
    INVALID_URL = "invalid_url"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class LinkCheckResult:
    """Result of URL accessibility check."""

    url: str
    status: LinkStatus
    status_code: int | None = None
    final_url: str | None = None
    response_time: float | None = None
    error_message: str | None = None
    content_type: str | None = None
    content_length: int | None = None
    last_checked: float = 0.0

    def __post_init__(self) -> None:
        if self.last_checked == 0.0:
            self.last_checked = time.time()

    def is_accessible(self) -> bool:
        """Check if URL is accessible."""
        return self.status == LinkStatus.ACCESSIBLE

    def needs_attention(self) -> bool:
        """Check if URL needs attention (broken, redirected, etc.)."""
        return self.status in [
            LinkStatus.NOT_FOUND,
            LinkStatus.FORBIDDEN,
            LinkStatus.SSL_ERROR,
            LinkStatus.CONNECTION_ERROR,
            LinkStatus.INVALID_URL,
            LinkStatus.UNKNOWN_ERROR,
        ]


class URLAnalyzer:
    """Analyze and validate URLs in bibliographic entries."""

    def __init__(self, timeout: int = 10, max_redirects: int = 5) -> None:
        self.timeout = timeout
        self.max_redirects = max_redirects
        self._session: httpx.AsyncClient | None = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=self.max_redirects,
                headers={
                    "User-Agent": "ReflInt/1.0 Link Checker (https://github.com/reflint/reflint)"
                },
            )
        return self._session

    async def check_url(self, url: str) -> LinkCheckResult:
        """Check URL accessibility and status."""
        start_time = time.time()

        # Basic URL validation
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return LinkCheckResult(
                    url=url,
                    status=LinkStatus.INVALID_URL,
                    error_message="Invalid URL format",
                )
        except Exception as e:
            return LinkCheckResult(
                url=url,
                status=LinkStatus.INVALID_URL,
                error_message=f"URL parsing error: {e}",
            )

        session = await self._get_session()

        try:
            # Use HEAD request first for efficiency
            response = await session.head(url)
            response_time = time.time() - start_time

            # Determine status
            if response.status_code == 200:
                status = LinkStatus.ACCESSIBLE
            elif response.status_code == 404:
                status = LinkStatus.NOT_FOUND
            elif response.status_code in [401, 403]:
                status = LinkStatus.FORBIDDEN
            elif 300 <= response.status_code < 400:
                status = LinkStatus.REDIRECT
            else:
                status = LinkStatus.UNKNOWN_ERROR

            return LinkCheckResult(
                url=url,
                status=status,
                status_code=response.status_code,
                final_url=str(response.url) if response.url != url else None,
                response_time=response_time,
                content_type=response.headers.get("content-type"),
                content_length=int(response.headers.get("content-length", 0)) or None,
            )

        except httpx.TimeoutException:
            response_time = time.time() - start_time
            return LinkCheckResult(
                url=url,
                status=LinkStatus.TIMEOUT,
                response_time=response_time,
                error_message="Request timeout",
            )

        except httpx.ConnectError as e:
            response_time = time.time() - start_time
            return LinkCheckResult(
                url=url,
                status=LinkStatus.CONNECTION_ERROR,
                response_time=response_time,
                error_message=f"Connection error: {e}",
            )

        except (httpx.ConnectError, Exception) as e:
            # Handle SSL/TLS errors as part of connection errors
            if "ssl" in str(e).lower() or "tls" in str(e).lower():
                response_time = time.time() - start_time
                return LinkCheckResult(
                    url=url,
                    status=LinkStatus.SSL_ERROR,
                    response_time=response_time,
                    error_message=f"SSL/TLS error: {e}",
                )
            raise  # Re-raise if not SSL/TLS related

        except Exception as e:
            response_time = time.time() - start_time
            return LinkCheckResult(
                url=url,
                status=LinkStatus.SSL_ERROR,
                response_time=response_time,
                error_message=f"SSL/TLS error: {e}",
            )

        except Exception as e:
            response_time = time.time() - start_time
            return LinkCheckResult(
                url=url,
                status=LinkStatus.UNKNOWN_ERROR,
                response_time=response_time,
                error_message=f"Unexpected error: {e}",
            )

    async def check_urls_batch(
        self, urls: list[str], max_concurrent: int = 10
    ) -> dict[str, LinkCheckResult]:
        """Check multiple URLs concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_with_semaphore(url: str) -> tuple[str, LinkCheckResult]:
            async with semaphore:
                result = await self.check_url(url)
                return url, result

        logger.info(
            f"Checking {len(urls)} URLs with max {max_concurrent} concurrent requests"
        )

        tasks = [check_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        url_results = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in batch URL check: {result}")
                continue

            if isinstance(result, tuple) and len(result) == 2:
                url, check_result = result
                url_results[url] = check_result

        return url_results

    def analyze_url_quality(self, url: str) -> dict[str, Any]:
        """Analyze URL quality and provide recommendations."""
        parsed = urlparse(url)
        issues = []
        recommendations = []
        score = 1.0  # Perfect score

        # Check protocol
        if parsed.scheme == "http":
            issues.append("Uses insecure HTTP protocol")
            recommendations.append("Consider using HTTPS if available")
            score -= 0.2
        elif not parsed.scheme:
            issues.append("Missing protocol")
            recommendations.append("Add https:// or http:// protocol")
            score -= 0.5

        # Check for suspicious domains
        suspicious_domains = [
            "bit.ly",
            "tinyurl.com",
            "t.co",
            "goo.gl",
            "ow.ly",
            "short.link",
            "tiny.cc",
            "is.gd",
            "buff.ly",
        ]

        if any(domain in parsed.netloc.lower() for domain in suspicious_domains):
            issues.append("URL shortener detected")
            recommendations.append("Use the full URL instead of shortened version")
            score -= 0.3

        # Check for localhost/development URLs
        if parsed.netloc.lower() in [
            "localhost",
            "127.0.0.1",
        ] or parsed.netloc.startswith("192.168."):
            issues.append("Local/development URL")
            recommendations.append("Replace with public URL for publication")
            score -= 0.8

        # Check for temporary file services
        temp_services = [
            "wetransfer.com",
            "sendspace.com",
            "mediafire.com",
            "dropbox.com/s/",
        ]
        if any(service in url.lower() for service in temp_services):
            issues.append("Temporary file sharing service")
            recommendations.append("Consider using persistent hosting")
            score -= 0.4

        # Check URL length
        if len(url) > 200:
            issues.append("Very long URL")
            recommendations.append("Consider using a more concise URL")
            score -= 0.1

        # Check for common tracking parameters
        tracking_params = ["utm_", "fbclid", "gclid", "ref=", "source="]
        if any(param in url.lower() for param in tracking_params):
            issues.append("Contains tracking parameters")
            recommendations.append("Remove tracking parameters for cleaner URL")
            score -= 0.1

        return {
            "score": max(0.0, score),
            "issues": issues,
            "recommendations": recommendations,
            "domain": parsed.netloc,
            "protocol": parsed.scheme,
            "is_academic": self._is_academic_domain(parsed.netloc),
        }

    def _is_academic_domain(self, domain: str) -> bool:
        """Check if domain is from an academic institution."""
        academic_indicators = [
            ".edu",
            ".ac.",
            ".university",
            ".edu.",
            "scholar.google",
            "arxiv.org",
            "doi.org",
            "ncbi.nlm.nih.gov",
            "ieee.org",
            "acm.org",
            "springer.com",
            "elsevier.com",
            "wiley.com",
            "nature.com",
            "science.org",
            "pnas.org",
        ]

        domain_lower = domain.lower()
        return any(indicator in domain_lower for indicator in academic_indicators)

    def get_canonical_url(self, url: str) -> str:
        """Get canonical form of URL."""
        parsed = urlparse(url)

        # Add protocol if missing
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)

        # Remove common tracking parameters
        tracking_params = [
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "ref",
            "source",
            "campaign",
        ]

        # Parse query parameters and filter out tracking
        if parsed.query:
            from urllib.parse import parse_qs, urlencode

            params = parse_qs(parsed.query)
            clean_params = {k: v for k, v in params.items() if k not in tracking_params}
            clean_query = urlencode(clean_params, doseq=True)

            # Reconstruct URL
            from urllib.parse import urlunparse

            url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    clean_query,
                    parsed.fragment,
                )
            )

        return url

    async def suggest_wayback_url(self, url: str) -> str | None:
        """Suggest Wayback Machine URL for dead links."""
        try:
            wayback_api = f"http://archive.org/wayback/available?url={url}"
            session = await self._get_session()

            response = await session.get(wayback_api)
            if response.status_code == 200:
                data = cast("dict[str, Any]", response.json())
                archived = data.get("archived_snapshots", {}).get("closest")
                if archived and archived.get("available"):
                    archive_url = archived.get("url")
                    return str(archive_url) if archive_url else None

        except Exception as e:
            logger.debug(f"Error checking Wayback Machine: {e}")

        return None

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.aclose()
            self._session = None


class LinkChecker:
    """High-level interface for checking links in bibliographic entries."""

    def __init__(self, cache_results: bool = True) -> None:
        self.analyzer = URLAnalyzer()
        self.cache_results = cache_results
        self._cache: dict[str, LinkCheckResult] = {}

    async def check_entry_urls(
        self, entry: "BibTeXEntry"
    ) -> dict[str, LinkCheckResult]:
        """Check all URLs in a bibliographic entry."""
        urls = []

        # Check main URL field
        if entry.has_field("url"):
            url = entry.get_field("url")
            if url:
                urls.append(url.strip("{}"))

        # Check DOI URL
        if entry.has_field("doi"):
            doi = entry.get_field("doi")
            if doi and not doi.startswith("http"):
                urls.append(f"https://doi.org/{doi}")

        if not urls:
            return {}

        # Check cached results first
        results = {}
        urls_to_check = []

        for url in urls:
            if self.cache_results and url in self._cache:
                cached_result = self._cache[url]
                # Use cached result if less than 1 hour old
                if time.time() - cached_result.last_checked < 3600:
                    results[url] = cached_result
                    continue

            urls_to_check.append(url)

        # Check remaining URLs
        if urls_to_check:
            new_results = await self.analyzer.check_urls_batch(urls_to_check)
            results.update(new_results)

            # Update cache
            if self.cache_results:
                self._cache.update(new_results)

        return results

    async def get_broken_links_report(
        self, entries: list["BibTeXEntry"]
    ) -> dict[str, Any]:
        """Generate report of broken links across all entries."""
        all_results = {}
        broken_links = []

        for entry in entries:
            entry_results = await self.check_entry_urls(entry)
            all_results[entry.key] = entry_results

            for url, result in entry_results.items():
                if result.needs_attention():
                    broken_links.append(
                        {
                            "entry_key": entry.key,
                            "url": url,
                            "status": result.status.value,
                            "error": result.error_message,
                        }
                    )

        return {
            "total_urls_checked": sum(len(results) for results in all_results.values()),
            "broken_links_count": len(broken_links),
            "broken_links": broken_links,
            "all_results": all_results,
        }

    async def close(self) -> None:
        """Close underlying analyzer."""
        await self.analyzer.close()
