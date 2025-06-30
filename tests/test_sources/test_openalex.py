"""Tests for OpenAlex source integration."""

import pytest
from unittest.mock import AsyncMock, patch

from src.reflint.sources.openalex import OpenAlexSource
from src.reflint.sources.base import LookupResult
from src.reflint.core.entry import BibTeXEntry


class TestOpenAlexSource:
    """Test cases for OpenAlexSource."""

    def setup_method(self):
        """Set up test fixtures."""
        self.source = OpenAlexSource(email="test@example.com")

    def test_init(self):
        """Test OpenAlexSource initialization."""
        assert self.source.name == "openalex"
        assert self.source.confidence == 0.85  # SourceConfidence.HIGH
        assert self.source.email == "test@example.com"
        assert self.source.rate_limit == 10

    def test_can_lookup_identifier(self):
        """Test identifier type checking."""
        assert self.source.can_lookup_identifier("doi")
        assert self.source.can_lookup_identifier("pmid")
        assert not self.source.can_lookup_identifier("arxiv")

    def test_clean_doi(self):
        """Test DOI cleaning and validation."""
        assert self.source._clean_doi("10.1000/123") == "10.1000/123"
        assert self.source._clean_doi("doi:10.1000/123") == "10.1000/123"
        assert self.source._clean_doi("https://doi.org/10.1000/123") == "10.1000/123"
        assert self.source._clean_doi("https://dx.doi.org/10.1000/123") == "10.1000/123"
        assert self.source._clean_doi("invalid") is None
        assert self.source._clean_doi("10.123") is None  # Too short

    def test_clean_pmid(self):
        """Test PMID cleaning and validation."""
        assert self.source._clean_pmid("12345678") == "12345678"
        assert self.source._clean_pmid("pmid:12345678") == "12345678"
        assert self.source._clean_pmid("PMID:12345678") == "12345678"
        assert self.source._clean_pmid("  12345678  ") == "12345678"
        assert self.source._clean_pmid("invalid") is None
        assert self.source._clean_pmid("123abc") is None

    def test_clean_title(self):
        """Test title cleaning."""
        assert (
            self.source._clean_title("A Study of   Research") == "A Study of Research"
        )
        assert self.source._clean_title("  Title  ") == "Title"
        assert self.source._clean_title("") == ""

    def test_format_authors(self):
        """Test author formatting."""
        authors = ["John Smith", "Jane Doe", "Bob Wilson"]
        expected = "John Smith and Jane Doe and Bob Wilson"
        assert self.source._format_authors(authors) == expected
        assert self.source._format_authors([]) == ""

    def test_generate_entry_key(self):
        """Test BibTeX entry key generation."""
        authors = ["John Smith", "Jane Doe"]
        year = 2023
        title = "Machine Learning Research"

        key = self.source._generate_entry_key(authors, year, title)
        assert "smith" in key.lower()
        assert "2023" in key
        assert "machine" in key.lower()

    def test_determine_entry_type(self):
        """Test BibTeX entry type determination."""
        assert (
            self.source._determine_entry_type({"type": "journal-article"}) == "article"
        )
        assert (
            self.source._determine_entry_type({"type": "proceedings-article"})
            == "inproceedings"
        )
        assert self.source._determine_entry_type({"type": "book"}) == "book"
        assert (
            self.source._determine_entry_type({"type": "book-chapter"})
            == "incollection"
        )
        assert (
            self.source._determine_entry_type({"type": "unknown"}) == "article"
        )  # default

    def test_extract_abstract_inverted(self):
        """Test abstract extraction from inverted index."""
        work = {
            "abstract_inverted_index": {
                "This": [0],
                "is": [1],
                "a": [2],
                "test": [3],
                "abstract": [4],
            }
        }

        abstract = self.source._extract_abstract(work)
        assert abstract == "This is a test abstract"

    def test_extract_abstract_empty(self):
        """Test abstract extraction with no data."""
        assert self.source._extract_abstract({}) == ""
        assert self.source._extract_abstract({"abstract_inverted_index": {}}) == ""

    def test_extract_identifiers(self):
        """Test identifier extraction."""
        work = {
            "doi": "https://doi.org/10.1000/123",
            "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/12345678/"},
        }

        identifiers = self.source._extract_identifiers(work)
        assert identifiers["doi"] == "10.1000/123"
        assert identifiers["pmid"] == "12345678"

    def test_extract_publication_date(self):
        """Test publication date extraction."""
        work = {"publication_date": "2023-03-15"}

        date = self.source._extract_publication_date(work)
        assert date["year"] == 2023
        assert date["month"] == 3

    def test_extract_publication_date_year_only(self):
        """Test publication date extraction with year only."""
        work = {"publication_year": 2023}

        date = self.source._extract_publication_date(work)
        assert date["year"] == 2023
        assert "month" not in date

    @pytest.mark.asyncio
    async def test_lookup_by_doi_invalid(self):
        """Test lookup with invalid DOI."""
        result = await self.source.lookup_by_doi("invalid")
        assert isinstance(result, LookupResult)
        assert result.entry is None
        assert "Invalid DOI" in result.metadata.error

    @pytest.mark.asyncio
    async def test_lookup_by_pmid_invalid(self):
        """Test lookup with invalid PMID."""
        result = await self.source.lookup_by_pmid("invalid")
        assert isinstance(result, LookupResult)
        assert result.entry is None
        assert "Invalid PMID" in result.metadata.error

    @pytest.mark.asyncio
    async def test_lookup_by_doi_success(self):
        """Test successful DOI lookup."""
        mock_response_json = {
            "results": [
                {
                    "id": "https://openalex.org/W12345",
                    "title": "Machine Learning in Healthcare",
                    "doi": "https://doi.org/10.1000/123",
                    "publication_date": "2023-03-15",
                    "authorships": [
                        {"author": {"display_name": "John Smith"}},
                        {"author": {"display_name": "Jane Doe"}},
                    ],
                    "primary_location": {
                        "source": {
                            "display_name": "Nature Medicine",
                            "issn_l": "1078-8956",
                            "host_organization": {
                                "display_name": "Nature Publishing Group"
                            },
                        }
                    },
                    "biblio": {
                        "volume": "29",
                        "issue": "3",
                        "first_page": "123",
                        "last_page": "130",
                    },
                    "type": "journal-article",
                    "cited_by_count": 42,
                    "abstract_inverted_index": {
                        "This": [0],
                        "paper": [1],
                        "discusses": [2],
                        "ML": [3],
                    },
                    "primary_topic": {"display_name": "Machine Learning"},
                    "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/87654321/"},
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            # Create proper mock response
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_response_json)
            mock_response.text = str(mock_response_json)
            mock_response.raise_for_status = AsyncMock()

            # Configure the client mock properly
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get = AsyncMock(return_value=mock_response)

            with patch.object(self.source, "_rate_limit", new_callable=AsyncMock):
                result = await self.source.lookup_by_doi("10.1000/123")

            assert isinstance(result, LookupResult)
            assert result.entry is not None
            assert isinstance(result.entry, BibTeXEntry)
            assert result.entry.get_field("title") == "Machine Learning in Healthcare"
            assert result.entry.get_field("author") == "John Smith and Jane Doe"
            assert result.entry.get_field("journal") == "Nature Medicine"
            assert result.entry.get_field("year") == "2023"
            assert result.entry.get_field("month") == "3"
            assert result.entry.get_field("volume") == "29"
            assert result.entry.get_field("number") == "3"
            assert result.entry.get_field("pages") == "123--130"
            assert result.entry.get_field("doi") == "10.1000/123"
            assert result.entry.get_field("pmid") == "87654321"
            assert result.entry.get_field("issn") == "1078-8956"
            assert result.entry.get_field("publisher") == "Nature Publishing Group"
            assert result.entry.get_field("abstract") == "This paper discusses ML"
            assert result.entry.get_field("keywords") == "Machine Learning"
            assert "Cited by 42" in result.entry.get_field("note")
            assert "openalex.org/W12345" in result.entry.get_field("url")

    @pytest.mark.asyncio
    async def test_lookup_by_doi_not_found(self):
        """Test DOI lookup when no results found."""
        mock_response = {"results": []}

        with patch("httpx.AsyncClient") as mock_client:
            # Create proper mock response
            mock_response_obj = AsyncMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock()

            # Configure the client mock properly
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get = AsyncMock(return_value=mock_response_obj)

            with patch.object(self.source, "_rate_limit", new_callable=AsyncMock):
                result = await self.source.lookup_by_doi("10.1000/123")

            assert isinstance(result, LookupResult)
            assert result.entry is None
            assert "No OpenAlex entry found" in result.metadata.error

    @pytest.mark.asyncio
    async def test_lookup_by_doi_http_error(self):
        """Test DOI lookup with HTTP error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                Exception("HTTP Error")
            )

            with patch.object(self.source, "_rate_limit", return_value=None):
                result = await self.source.lookup_by_doi("10.1000/123")

            assert isinstance(result, LookupResult)
            assert result.entry is None
            assert "error" in result.metadata.error.lower()

    @pytest.mark.asyncio
    async def test_lookup_by_pmid_success(self):
        """Test successful PMID lookup."""
        mock_response = {
            "results": [
                {
                    "id": "https://openalex.org/W12345",
                    "title": "Medical Research Study",
                    "publication_date": "2023-01-01",
                    "authorships": [{"author": {"display_name": "Dr. Smith"}}],
                    "primary_location": {"source": {"display_name": "NEJM"}},
                    "type": "journal-article",
                    "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/12345678/"},
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.text = str(mock_response)
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response_obj
            )

            with patch.object(self.source, "_rate_limit", return_value=None):
                result = await self.source.lookup_by_pmid("12345678")

            assert isinstance(result, LookupResult)
            assert result.entry is not None
            assert result.entry.get_field("title") == "Medical Research Study"
            assert result.entry.get_field("pmid") == "12345678"

    @pytest.mark.asyncio
    async def test_lookup_by_title_author(self):
        """Test lookup by title and author."""
        mock_response = {
            "results": [
                {
                    "id": "https://openalex.org/W12345",
                    "title": "AI Research",
                    "publication_date": "2023-01-01",
                    "authorships": [{"author": {"display_name": "John Smith"}}],
                    "primary_location": {"source": {"display_name": "AI Journal"}},
                    "type": "journal-article",
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.text = str(mock_response)
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response_obj
            )

            with patch.object(self.source, "_rate_limit", return_value=None):
                results = await self.source.lookup_by_title_author(
                    "AI Research", "John Smith"
                )

            assert len(results) == 1
            assert isinstance(results[0], LookupResult)
            assert results[0].entry is not None
            assert results[0].entry.get_field("title") == "AI Research"

    @pytest.mark.asyncio
    async def test_lookup_by_title_author_no_params(self):
        """Test lookup with missing title and author."""
        results = await self.source.lookup_by_title_author("", "")

        assert len(results) == 1
        assert isinstance(results[0], LookupResult)
        assert results[0].entry is None
        assert "required" in results[0].metadata.error

    def test_parse_work_minimal(self):
        """Test work parsing with minimal data."""
        work = {
            "title": "Test Paper",
            "authorships": [{"author": {"display_name": "Test Author"}}],
            "publication_year": 2023,
            "type": "journal-article",
        }

        result = self.source._parse_work(work)

        assert result is not None
        assert result.get_field("title") == "Test Paper"
        assert result.get_field("author") == "Test Author"
        assert result.get_field("year") == "2023"
        assert result.entry_type == "article"

    def test_parse_work_no_title(self):
        """Test work parsing with no title."""
        work = {"authorships": [{"author": {"display_name": "Test Author"}}]}

        result = self.source._parse_work(work)
        assert result is None

    def test_get_source_info(self):
        """Test source information retrieval."""
        info = self.source.get_source_info()

        assert info["name"] == "openalex"
        assert info["confidence"] == 0.85
        assert "doi" in info["supported_identifiers"]
        assert "pmid" in info["supported_identifiers"]
        assert "All academic disciplines" in info["coverage"]
        assert "openalex.org" in info["url"]
        assert "10 requests/second" in info["rate_limit"]
