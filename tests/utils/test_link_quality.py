"""Tests for link quality management system."""

from unittest.mock import AsyncMock, patch

import pytest

from reflint.utils.link_quality import (
    ArchiveResult,
    LinkQualityManager,
    LinkStatus,
    URLShortenerDetector,
    check_entry_link_quality,
)


class TestLinkStatus:
    """Test the LinkStatus dataclass."""

    def test_link_status_creation(self):
        """Test creating LinkStatus objects."""
        status = LinkStatus(
            url="https://example.com",
            is_accessible=True,
            status_code=200,
            redirect_url=None,
            error_message=None,
            response_time=0.5,
            archived_url=None,
            last_checked=1234567890.0,
        )

        assert status.url == "https://example.com"
        assert status.is_accessible
        assert status.status_code == 200
        assert not status.is_redirect
        assert not status.is_dead

    def test_is_redirect_property(self):
        """Test the is_redirect property."""
        # No redirect
        status = LinkStatus(
            url="https://example.com",
            is_accessible=True,
            status_code=200,
            redirect_url=None,
            error_message=None,
            response_time=0.5,
            archived_url=None,
            last_checked=1234567890.0,
        )
        assert not status.is_redirect

        # Same URL redirect
        status.redirect_url = "https://example.com"
        assert not status.is_redirect

        # Different URL redirect
        status.redirect_url = "https://different.com"
        assert status.is_redirect

    def test_is_dead_property(self):
        """Test the is_dead property."""
        # Accessible URL
        status = LinkStatus(
            url="https://example.com",
            is_accessible=True,
            status_code=200,
            redirect_url=None,
            error_message=None,
            response_time=0.5,
            archived_url=None,
            last_checked=1234567890.0,
        )
        assert not status.is_dead

        # Dead URL
        status.is_accessible = False
        status.status_code = 404
        assert status.is_dead

        # Rate limited (not considered dead)
        status.status_code = 429
        assert not status.is_dead

        # Temporarily unavailable (not considered dead)
        status.status_code = 503
        assert not status.is_dead


class TestArchiveResult:
    """Test the ArchiveResult dataclass."""

    def test_archive_result_creation(self):
        """Test creating ArchiveResult objects."""
        result = ArchiveResult(
            original_url="https://example.com",
            archived_url="https://web.archive.org/web/20230101000000/https://example.com",
            archive_date="20230101000000",
            is_available=True,
            snapshot_count=5,
        )

        assert result.original_url == "https://example.com"
        assert result.is_available
        assert result.snapshot_count == 5


class TestLinkQualityManager:
    """Test the LinkQualityManager class."""

    def test_init(self):
        """Test LinkQualityManager initialization."""
        manager = LinkQualityManager()
        assert manager.timeout == 10.0
        assert manager.max_retries == 2
        assert isinstance(manager._cache, dict)
        assert isinstance(manager._archive_cache, dict)

        manager_custom = LinkQualityManager(timeout=5.0, max_retries=1)
        assert manager_custom.timeout == 5.0
        assert manager_custom.max_retries == 1

    @pytest.mark.asyncio
    async def test_check_url_status_success(self):
        """Test successful URL status checking."""
        manager = LinkQualityManager()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.history = []
            mock_response.url = "https://example.com"

            mock_client.return_value.__aenter__.return_value.head.return_value = (
                mock_response
            )

            status = await manager.check_url_status("https://example.com")

            assert status.is_accessible
            assert status.status_code == 200
            assert not status.is_redirect

    @pytest.mark.asyncio
    async def test_check_url_status_redirect(self):
        """Test URL status checking with redirect."""
        manager = LinkQualityManager()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock redirect response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.history = [AsyncMock()]  # Has redirect history
            mock_response.url = "https://redirected.com"

            mock_client.return_value.__aenter__.return_value.head.return_value = (
                mock_response
            )

            status = await manager.check_url_status("https://example.com")

            assert status.is_accessible
            assert status.redirect_url == "https://redirected.com"
            assert status.is_redirect

    @pytest.mark.asyncio
    async def test_check_url_status_error(self):
        """Test URL status checking with error."""
        manager = LinkQualityManager()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock error response
            mock_client.return_value.__aenter__.return_value.head.side_effect = (
                Exception("Network error")
            )

            status = await manager.check_url_status("https://example.com")

            assert not status.is_accessible
            assert "Network error" in status.error_message

    @pytest.mark.asyncio
    async def test_check_multiple_urls(self):
        """Test checking multiple URLs concurrently."""
        manager = LinkQualityManager()

        with patch.object(manager, "check_url_status") as mock_check:
            # Mock status for each URL
            mock_check.side_effect = [
                LinkStatus(
                    "https://example1.com",
                    True,
                    200,
                    None,
                    None,
                    0.1,
                    None,
                    1234567890.0,
                ),
                LinkStatus(
                    "https://example2.com",
                    False,
                    404,
                    None,
                    "Not found",
                    0.2,
                    None,
                    1234567890.0,
                ),
            ]

            urls = ["https://example1.com", "https://example2.com"]
            results = await manager.check_multiple_urls(urls)

            assert len(results) == 2
            assert results["https://example1.com"].is_accessible
            assert not results["https://example2.com"].is_accessible

    @pytest.mark.asyncio
    async def test_find_archive_url_success(self):
        """Test successful archive URL lookup."""
        manager = LinkQualityManager()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock archive API response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                ["timestamp", "original", "mimetype", "statuscode", "digest", "length"],
                [
                    "20230101000000",
                    "https://example.com",
                    "text/html",
                    "200",
                    "abc123",
                    "1000",
                ],
            ]

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await manager.find_archive_url("https://example.com")

            assert result.is_available
            assert "web.archive.org" in result.archived_url
            assert result.archive_date == "20230101000000"
            assert result.snapshot_count == 1

    @pytest.mark.asyncio
    async def test_find_archive_url_not_found(self):
        """Test archive URL lookup when not found."""
        manager = LinkQualityManager()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock empty archive response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                ["timestamp", "original", "mimetype", "statuscode", "digest", "length"]
            ]

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await manager.find_archive_url("https://example.com")

            assert not result.is_available
            assert result.archived_url is None

    @pytest.mark.asyncio
    async def test_suggest_https_upgrade(self):
        """Test HTTPS upgrade suggestion."""
        manager = LinkQualityManager()

        with patch.object(manager, "check_url_status") as mock_check:
            # Mock successful HTTPS check
            mock_check.return_value = LinkStatus(
                "https://example.com", True, 200, None, None, 0.1, None, 1234567890.0
            )

            https_url = await manager.suggest_https_upgrade("http://example.com")

            assert https_url == "https://example.com"

    @pytest.mark.asyncio
    async def test_suggest_https_upgrade_not_available(self):
        """Test HTTPS upgrade when not available."""
        manager = LinkQualityManager()

        with patch.object(manager, "check_url_status") as mock_check:
            # Mock failed HTTPS check
            mock_check.return_value = LinkStatus(
                "https://example.com",
                False,
                404,
                None,
                "Not found",
                0.1,
                None,
                1234567890.0,
            )

            https_url = await manager.suggest_https_upgrade("http://example.com")

            assert https_url is None

    @pytest.mark.asyncio
    async def test_resolve_redirect_chain(self):
        """Test resolving redirect chains."""
        manager = LinkQualityManager()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock redirect chain
            responses = [
                AsyncMock(status_code=301, headers={"location": "https://step1.com"}),
                AsyncMock(status_code=302, headers={"location": "https://final.com"}),
                AsyncMock(status_code=200, headers={}),
            ]

            mock_client.return_value.__aenter__.return_value.head.side_effect = (
                responses
            )

            chain = await manager.resolve_redirect_chain("https://start.com")

            assert len(chain) >= 1
            assert chain[0] == "https://start.com"

    def test_extract_urls_from_entry(self):
        """Test URL extraction from BibTeX entries."""
        manager = LinkQualityManager()

        entry = {
            "title": "Test Paper",
            "url": "https://example.com/paper.pdf",
            "note": "Available at https://arxiv.org/abs/1234.5678",
            "howpublished": "\\url{https://preprint.com/123}",
            "author": "Smith, John",
        }

        urls = manager.extract_urls_from_entry(entry)

        assert "https://example.com/paper.pdf" in urls
        assert "https://arxiv.org/abs/1234.5678" in urls
        assert "https://preprint.com/123" in urls

    @pytest.mark.asyncio
    async def test_enhance_entry_urls(self):
        """Test URL enhancement in BibTeX entries."""
        manager = LinkQualityManager()

        entry = {"title": "Test Paper", "url": "http://example.com/paper.pdf"}

        with patch.object(manager, "check_multiple_urls") as mock_check:
            # Mock HTTPS upgrade available
            mock_check.return_value = {
                "http://example.com/paper.pdf": LinkStatus(
                    "http://example.com/paper.pdf",
                    True,
                    200,
                    None,
                    None,
                    0.1,
                    None,
                    1234567890.0,
                )
            }

            with patch.object(manager, "suggest_https_upgrade") as mock_https:
                mock_https.return_value = "https://example.com/paper.pdf"

                enhanced = await manager.enhance_entry_urls(entry)

                assert enhanced["url"] == "https://example.com/paper.pdf"

    def test_get_dead_link_report(self):
        """Test dead link report generation."""
        manager = LinkQualityManager()

        urls = ["https://dead.com", "https://redirect.com", "http://upgrade.com"]
        status_map = {
            "https://dead.com": LinkStatus(
                "https://dead.com",
                False,
                404,
                None,
                "Not found",
                None,
                None,
                1234567890.0,
            ),
            "https://redirect.com": LinkStatus(
                "https://redirect.com",
                True,
                200,
                "https://new.com",
                None,
                0.1,
                None,
                1234567890.0,
            ),
            "http://upgrade.com": LinkStatus(
                "http://upgrade.com", True, 200, None, None, 0.1, None, 1234567890.0
            ),
        }

        report = manager.get_dead_link_report(urls, status_map)

        assert report["total_urls"] == 3
        assert report["dead_count"] == 1
        assert report["redirect_count"] == 1
        assert report["https_candidate_count"] == 1


class TestURLShortenerDetector:
    """Test the URLShortenerDetector class."""

    def test_is_shortened_url(self):
        """Test shortened URL detection."""
        assert URLShortenerDetector.is_shortened_url("https://bit.ly/abc123")
        assert URLShortenerDetector.is_shortened_url("http://tinyurl.com/xyz")
        assert URLShortenerDetector.is_shortened_url("https://goo.gl/maps")
        assert URLShortenerDetector.is_shortened_url("https://t.co/abcdef")

        assert not URLShortenerDetector.is_shortened_url("https://example.com")
        assert not URLShortenerDetector.is_shortened_url("https://github.com/user/repo")

    @pytest.mark.asyncio
    async def test_resolve_shortened_url(self):
        """Test shortened URL resolution."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.url = "https://final-destination.com"

            mock_client.return_value.__aenter__.return_value.head.return_value = (
                mock_response
            )

            resolved = await URLShortenerDetector.resolve_shortened_url(
                "https://bit.ly/abc123"
            )

            assert resolved == "https://final-destination.com"

    @pytest.mark.asyncio
    async def test_resolve_non_shortened_url(self):
        """Test resolving non-shortened URLs (returns original)."""
        url = "https://example.com/full-url"
        resolved = await URLShortenerDetector.resolve_shortened_url(url)

        assert resolved == url


class TestCheckEntryLinkQuality:
    """Test the check_entry_link_quality function."""

    @pytest.mark.asyncio
    async def test_check_entry_no_urls(self):
        """Test checking entry with no URLs."""
        entry = {"title": "Test Paper", "author": "Smith, John", "year": "2023"}

        result = await check_entry_link_quality(entry)

        assert result["enhanced_entry"] == entry
        assert result["link_report"]["total_urls"] == 0

    @pytest.mark.asyncio
    async def test_check_entry_with_urls(self):
        """Test checking entry with URLs."""
        entry = {"title": "Test Paper", "url": "https://example.com"}

        with patch(
            "reflint.utils.link_quality.LinkQualityManager"
        ) as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager

            mock_manager.extract_urls_from_entry.return_value = ["https://example.com"]
            mock_manager.check_multiple_urls.return_value = {
                "https://example.com": LinkStatus(
                    "https://example.com",
                    True,
                    200,
                    None,
                    None,
                    0.1,
                    None,
                    1234567890.0,
                )
            }
            mock_manager.enhance_entry_urls.return_value = entry
            mock_manager.get_dead_link_report.return_value = {
                "total_urls": 1,
                "dead_links": [],
                "redirected_links": [],
                "https_candidates": [],
                "dead_count": 0,
                "redirect_count": 0,
                "https_candidate_count": 0,
            }

            result = await check_entry_link_quality(entry)

            assert result["enhanced_entry"] == entry
            assert result["link_report"]["total_urls"] == 1
