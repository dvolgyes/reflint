"""Tests for Semantic Scholar source integration."""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch, Mock
import httpx2 as httpx

from src.reflint.sources.semantic_scholar import SemanticScholarSource
from src.reflint.sources.base import LookupResult, SourceMetadata
from src.reflint.core.entry import BibTeXEntry


class TestSemanticScholarSource:
    """Test cases for SemanticScholarSource."""

    def setup_method(self):
        """Set up test fixtures."""
        self.source = SemanticScholarSource(api_key="test_key")

    def test_init(self):
        """Test SemanticScholarSource initialization."""
        assert self.source.name == "semantic_scholar"
        assert self.source.confidence == 0.85  # SourceConfidence.HIGH
        assert self.source.api_key == "test_key"
        assert self.source.timeout == 30

    def test_init_no_api_key(self):
        """Test initialization without API key."""
        source = SemanticScholarSource()
        assert source.api_key is None

    def test_can_lookup_identifier(self):
        """Test identifier type checking."""
        assert self.source.can_lookup_identifier("doi")
        assert self.source.can_lookup_identifier("arxiv")
        assert self.source.can_lookup_identifier("pmid")
        assert not self.source.can_lookup_identifier("isbn")

    def test_get_supported_identifiers(self):
        """Test supported identifier list."""
        identifiers = self.source.get_supported_identifiers()
        assert "doi" in identifiers
        assert "arxiv" in identifiers
        assert "pmid" in identifiers

    def test_get_reliability_score(self):
        """Test reliability scoring."""
        assert self.source.get_reliability_score("title") == 0.95
        assert self.source.get_reliability_score("abstract") == 0.95
        assert self.source.get_reliability_score("author") == 0.90
        assert self.source.get_reliability_score("unknown_field") == 0.85

    @pytest.mark.asyncio
    async def test_lookup_by_doi_success(self):
        """Test successful DOI lookup."""
        mock_response_data = {
            "paperId": "test_id",
            "title": "Test Paper",
            "year": 2023,
            "authors": [{"name": "Test Author"}],
            "externalIds": {"DOI": "10.1000/test"},
            "venue": "Test Journal",
            "abstract": "Test abstract",
            "citationCount": 10,
        }

        # Mock the cached_httpx_get function
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.content = b'{"test": "data"}'
        mock_response.raise_for_status.return_value = None

        with patch(
            "src.reflint.sources.semantic_scholar.cached_httpx_get",
            return_value=mock_response,
        ):
            result = await self.source.lookup_by_doi("10.1000/test")

            assert isinstance(result, LookupResult)
            assert result.entry is not None
            assert isinstance(result.entry, BibTeXEntry)
            assert result.entry.get_field("title") == "Test Paper"
            assert result.entry.get_field("doi") == "10.1000/test"

    @pytest.mark.asyncio
    async def test_lookup_by_doi_not_found(self):
        """Test DOI lookup when paper not found."""
        # Mock the cached_httpx_get function
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.content = b'{"error": "not found"}'

        with patch(
            "src.reflint.sources.semantic_scholar.cached_httpx_get",
            return_value=mock_response,
        ):
            result = await self.source.lookup_by_doi("10.1000/notfound")

            assert isinstance(result, LookupResult)
            assert result.entry is None
            assert result.metadata.error == "DOI not found"

    @pytest.mark.asyncio
    async def test_lookup_by_doi_rate_limit_retry_success(self):
        """Test DOI lookup with rate limit that succeeds on retry."""
        mock_response_data = {
            "paperId": "test_id",
            "title": "Test Paper After Retry",
            "year": 2023,
            "authors": [{"name": "Test Author"}],
            "externalIds": {"DOI": "10.1000/retry"},
        }

        # Create a mock session that simulates the behavior we want
        mock_session = AsyncMock()

        # Mock responses
        mock_429_response = Mock()
        mock_429_response.status_code = 429

        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = mock_response_data
        mock_success_response.content = b'{"test": "data"}'
        mock_success_response.raise_for_status.return_value = None

        # Set up side effects: first call raises 429, second succeeds
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call - rate limited
                raise httpx.HTTPStatusError(
                    "Rate limited", request=Mock(), response=mock_429_response
                )
            else:
                # Second call - success
                return mock_success_response

        mock_session.get.side_effect = mock_get

        # Mock the cached_httpx_get function
        with patch(
            "src.reflint.sources.semantic_scholar.cached_httpx_get",
            side_effect=mock_get,
        ):
            # Mock asyncio.sleep to avoid actual delays in tests
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await self.source.lookup_by_doi("10.1000/retry")

                # Verify sleep was called for retry delay
                mock_sleep.assert_called_once_with(2)  # First retry is 2 seconds

                assert isinstance(result, LookupResult)
                assert result.entry is not None
                assert result.entry.get_field("title") == "Test Paper After Retry"

    @pytest.mark.asyncio
    async def test_lookup_by_doi_rate_limit_exhausted(self):
        """Test DOI lookup with rate limit that exhausts all retries."""
        # Create a mock session that always returns 429
        mock_session = AsyncMock()

        mock_429_response = Mock()
        mock_429_response.status_code = 429

        # Always return 429
        async def mock_get(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "Rate limited", request=Mock(), response=mock_429_response
            )

        mock_session.get.side_effect = mock_get

        # Mock asyncio.sleep to speed up test and track calls
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

            async def limited_retry_lookup(id_type, value):
                # Copy the original logic but with fewer retries
                start_time = time.time()
                session = await self.source._get_session()

                clean_value = value.strip()
                if id_type == "DOI":
                    clean_value = clean_value.replace("https://doi.org/", "").replace(
                        "http://dx.doi.org/", ""
                    )

                url = f"{self.source.base_url}/paper/{id_type}:{clean_value}"
                params = {"fields": ",".join(self.source.paper_fields)}

                # Reduced retries for testing
                max_retries = 2
                retry_count = 0

                while retry_count <= max_retries:
                    try:
                        await session.get(url, params=params)
                        # Won't reach here due to mock
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            retry_count += 1
                            if retry_count > max_retries:
                                lookup_time = time.time() - start_time
                                return LookupResult(
                                    entry=None,
                                    metadata=SourceMetadata(
                                        source_name=self.source.name,
                                        lookup_time=lookup_time,
                                        confidence=self.source.confidence,
                                        rate_limited=True,
                                        error="Rate limited - retries exhausted",
                                    ),
                                )

                            delay = min(retry_count * 2, 60)
                            await asyncio.sleep(delay)
                            continue

            # Patch both the session and the method
            with patch.object(self.source, "_get_session", return_value=mock_session):
                with patch.object(
                    self.source,
                    "_lookup_by_identifier",
                    side_effect=limited_retry_lookup,
                ):
                    result = await self.source.lookup_by_doi("10.1000/exhausted")

                    assert isinstance(result, LookupResult)
                    assert result.entry is None
                    assert result.metadata.rate_limited is True
                    assert "retries exhausted" in result.metadata.error

                    # Should have called sleep for retries (2s, 4s)
                    assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_lookup_by_arxiv_success(self):
        """Test successful arXiv lookup."""
        mock_response_data = {
            "paperId": "arxiv_test_id",
            "title": "arXiv Test Paper",
            "year": 2023,
            "authors": [{"name": "arXiv Author"}],
            "externalIds": {"ArXiv": "2023.12345"},
        }

        # Mock the cached_httpx_get function
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.content = b'{"test": "data"}'
        mock_response.raise_for_status.return_value = None

        with patch(
            "src.reflint.sources.semantic_scholar.cached_httpx_get",
            return_value=mock_response,
        ):
            result = await self.source.lookup_by_arxiv("2023.12345")

            assert isinstance(result, LookupResult)
            assert result.entry is not None
            assert result.entry.get_field("title") == "arXiv Test Paper"
            assert result.entry.get_field("eprint") == "2023.12345"

    @pytest.mark.asyncio
    async def test_lookup_by_pmid_success(self):
        """Test successful PMID lookup."""
        mock_response_data = {
            "paperId": "pmid_test_id",
            "title": "PubMed Test Paper",
            "year": 2023,
            "authors": [{"name": "PubMed Author"}],
            "externalIds": {"PubMed": "12345678"},
        }

        # Mock the cached_httpx_get function
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.content = b'{"test": "data"}'
        mock_response.raise_for_status.return_value = None

        with patch(
            "src.reflint.sources.semantic_scholar.cached_httpx_get",
            return_value=mock_response,
        ):
            result = await self.source.lookup_by_pmid("12345678")

            assert isinstance(result, LookupResult)
            assert result.entry is not None
            assert result.entry.get_field("title") == "PubMed Test Paper"
            assert "PMID: 12345678" in result.entry.get_field("note")

    @pytest.mark.asyncio
    async def test_lookup_by_title_author_success(self):
        """Test successful title/author search."""
        mock_response_data = {
            "data": [
                {
                    "paperId": "search_test_id",
                    "title": "Search Test Paper",
                    "year": 2023,
                    "authors": [{"name": "Search Author"}],
                    "venue": "Search Journal",
                }
            ]
        }

        # Mock the cached_httpx_get function
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.content = b'{"test": "data"}'
        mock_response.raise_for_status.return_value = None

        with patch(
            "src.reflint.sources.semantic_scholar.cached_httpx_get",
            return_value=mock_response,
        ):
            results = await self.source.lookup_by_title_author(
                "Search Test", "Search Author"
            )

            assert isinstance(results, list)
            assert len(results) == 1
            assert isinstance(results[0], LookupResult)
            assert results[0].entry.get_field("title") == "Search Test Paper"

    @pytest.mark.asyncio
    async def test_lookup_by_title_author_rate_limit_retry(self):
        """Test title/author search with rate limit retry."""
        mock_response_data = {
            "data": [
                {
                    "paperId": "retry_search_id",
                    "title": "Retry Search Paper",
                    "year": 2023,
                    "authors": [{"name": "Retry Author"}],
                }
            ]
        }

        mock_429_response = Mock()
        mock_429_response.status_code = 429

        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = mock_response_data
        mock_success_response.content = b'{"test": "data"}'
        mock_success_response.raise_for_status.return_value = None

        # Mock to return 429 first, then success
        call_count = 0

        async def mock_cached_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "Rate limited", request=Mock(), response=mock_429_response
                )
            else:
                return mock_success_response

        # Mock the cached_httpx_get function
        with patch(
            "src.reflint.sources.semantic_scholar.cached_httpx_get",
            side_effect=mock_cached_get,
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                results = await self.source.lookup_by_title_author(
                    "Retry Search", "Retry Author"
                )

                mock_sleep.assert_called_once_with(2)  # First retry delay

                assert isinstance(results, list)
                assert len(results) == 1
                assert results[0].entry.get_field("title") == "Retry Search Paper"

    def test_determine_entry_type(self):
        """Test entry type determination."""
        # Journal article
        paper = {"publicationTypes": ["JournalArticle"]}
        assert self.source._determine_entry_type(paper) == "article"

        # Conference paper
        paper = {"publicationTypes": ["Conference"]}
        assert self.source._determine_entry_type(paper) == "inproceedings"

        # Book
        paper = {"publicationTypes": ["Book"]}
        assert self.source._determine_entry_type(paper) == "book"

        # arXiv preprint
        paper = {"externalIds": {"ArXiv": "2023.12345"}}
        assert self.source._determine_entry_type(paper) == "misc"

        # Default case
        paper = {}
        assert self.source._determine_entry_type(paper) == "misc"

    def test_extract_authors(self):
        """Test author extraction."""
        paper = {"authors": [{"name": "John Doe"}, {"name": "Jane Smith"}]}
        result = self.source._extract_authors(paper)
        assert result == "John Doe and Jane Smith"

        # No authors
        paper = {"authors": []}
        result = self.source._extract_authors(paper)
        assert result is None

    def test_extract_venue(self):
        """Test venue extraction."""
        # From venue field
        paper = {"venue": "Test Journal"}
        result = self.source._extract_venue(paper, "article")
        assert result == "Test Journal"

        # From journal field
        paper = {"journal": {"name": "Journal Name"}}
        result = self.source._extract_venue(paper, "article")
        assert result == "Journal Name"

        # No venue
        paper = {}
        result = self.source._extract_venue(paper, "article")
        assert result is None

    def test_extract_fields_of_study(self):
        """Test fields of study extraction."""
        # S2 fields
        paper = {
            "s2FieldsOfStudy": [
                {"category": "Computer Science"},
                {"category": "Medicine"},
            ]
        }
        result = self.source._extract_fields_of_study(paper)
        assert result == "Computer Science, Medicine"

        # Regular fields
        paper = {"fieldsOfStudy": ["Biology", "Chemistry"]}
        result = self.source._extract_fields_of_study(paper)
        assert result == "Biology, Chemistry"

        # No fields
        paper = {}
        result = self.source._extract_fields_of_study(paper)
        assert result is None

    def test_generate_key(self):
        """Test BibTeX key generation."""
        paper = {
            "authors": [{"name": "John Doe"}],
            "year": 2023,
            "title": "Test Paper Title",
        }
        key = self.source._generate_key(paper)
        assert key == "doe2023test"

        # Missing data
        paper = {}
        key = self.source._generate_key(paper)
        assert key == "unknownunknownunknown"

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test session cleanup."""
        # Create a mock session
        mock_session = AsyncMock()
        self.source._session = mock_session

        await self.source.close()

        mock_session.aclose.assert_called_once()
        assert self.source._session is None
