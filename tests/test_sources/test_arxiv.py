"""Tests for arXiv source integration."""

import pytest
from unittest.mock import AsyncMock, patch

from src.reflint.sources.arxiv import ArxivSource
from src.reflint.sources.base import LookupResult
from src.reflint.core.entry import BibTeXEntry


class TestArxivSource:
    """Test cases for ArxivSource."""

    def setup_method(self):
        """Set up test fixtures."""
        self.source = ArxivSource(email="test@example.com")

    def test_init(self):
        """Test ArxivSource initialization."""
        assert self.source.name == "arxiv"
        assert self.source.confidence == 0.70  # SourceConfidence.MEDIUM
        assert self.source.email == "test@example.com"
        assert "arxiv" in self.source.get_supported_identifiers()

    def test_normalize_arxiv_id_new_format(self):
        """Test normalization of new format arXiv IDs."""
        # Test new format (YYMM.NNNN)
        assert self.source._normalize_arxiv_id("2301.12345") == "2301.12345"
        assert self.source._normalize_arxiv_id("2301.12345v1") == "2301.12345"
        assert self.source._normalize_arxiv_id("arxiv:2301.12345") == "2301.12345"
        assert self.source._normalize_arxiv_id("arXiv:2301.12345v2") == "2301.12345"

    def test_normalize_arxiv_id_old_format(self):
        """Test normalization of old format arXiv IDs."""
        # Test old format (subject-class/YYMMnnn)
        assert self.source._normalize_arxiv_id("cs.AI/0601001") == "cs.AI/0601001"
        assert self.source._normalize_arxiv_id("math-ph/0601001") == "math-ph/0601001"
        assert self.source._normalize_arxiv_id("arxiv:cs.AI/0601001") == "cs.AI/0601001"

    def test_normalize_arxiv_id_invalid(self):
        """Test normalization of invalid arXiv IDs."""
        assert self.source._normalize_arxiv_id("invalid") is None
        assert self.source._normalize_arxiv_id("123.456") is None
        assert self.source._normalize_arxiv_id("cs/123") is None
        assert self.source._normalize_arxiv_id("") is None

    def test_extract_year(self):
        """Test year extraction from date strings."""
        assert self.source._extract_year("2023-01-15T10:30:00Z") == 2023
        assert self.source._extract_year("2020-12-31") == 2020
        assert self.source._extract_year("invalid") is None
        assert self.source._extract_year("") is None

    def test_clean_title(self):
        """Test title cleaning and formatting."""
        assert (
            self.source._clean_title("  Quantum Computing  \n  Review  ")
            == "Quantum Computing Review"
        )
        assert (
            self.source._clean_title("Title\nwith\nnewlines") == "Title with newlines"
        )
        assert self.source._clean_title("") == ""

    def test_clean_abstract(self):
        """Test abstract cleaning and formatting."""
        abstract = "This is\n\na paper about\nquantum computing.\n\nIt's great."
        expected = "This is a paper about quantum computing. It's great."
        assert self.source._clean_abstract(abstract) == expected

    def test_format_authors(self):
        """Test author formatting for BibTeX."""
        authors = ["John Doe", "Jane Smith", "Bob Wilson"]
        expected = "John Doe and Jane Smith and Bob Wilson"
        assert self.source._format_authors(authors) == expected

        assert self.source._format_authors([]) == ""
        assert self.source._format_authors(["SingleAuthor"]) == "SingleAuthor"

    def test_generate_entry_key(self):
        """Test BibTeX entry key generation."""
        authors = ["John Doe", "Jane Smith"]
        year = 2023
        title = "Quantum Computing and Machine Learning"

        key = self.source._generate_entry_key(authors, year, title)
        assert "doe" in key.lower()
        assert "2023" in key
        assert "quantum" in key.lower()

    def test_generate_entry_key_no_author(self):
        """Test entry key generation with no authors."""
        key = self.source._generate_entry_key([], 2023, "Quantum Computing")
        assert "arxiv" in key.lower()
        assert "2023" in key
        assert "quantum" in key.lower()

    def test_can_lookup_identifier(self):
        """Test identifier type checking."""
        assert self.source.can_lookup_identifier("arxiv")
        assert not self.source.can_lookup_identifier("doi")
        assert not self.source.can_lookup_identifier("pmid")

    @pytest.mark.asyncio
    async def test_lookup_by_doi_not_supported(self):
        """Test DOI lookup (not supported)."""
        result = await self.source.lookup_by_doi("10.1000/123")
        assert isinstance(result, LookupResult)
        assert result.entry is None
        assert "not support DOI" in result.metadata.error

    @pytest.mark.asyncio
    async def test_lookup_by_arxiv_invalid_id(self):
        """Test lookup with invalid arXiv ID."""
        result = await self.source.lookup_by_arxiv("invalid")
        assert isinstance(result, LookupResult)
        assert result.entry is None
        assert "Invalid arXiv ID" in result.metadata.error

    @pytest.mark.asyncio
    async def test_lookup_by_arxiv_success(self):
        """Test successful lookup by arXiv ID."""
        mock_response = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>Quantum Computing Applications</title>
    <summary>This paper discusses quantum computing applications in machine learning.</summary>
    <published>2023-01-15T10:30:00Z</published>
    <updated>2023-01-16T10:30:00Z</updated>
    <author>
      <name>John Doe</name>
    </author>
    <author>
      <name>Jane Smith</name>
    </author>
    <category term="quant-ph"/>
    <category term="cs.LG"/>
    <arxiv:id>2301.12345</arxiv:id>
    <arxiv:doi>10.1000/123</arxiv:doi>
  </entry>
</feed>"""

        with patch("httpx2.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.text = mock_response
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response_obj
            )

            result = await self.source.lookup_by_arxiv("2301.12345")

            assert isinstance(result, LookupResult)
            assert result.entry is not None
            assert isinstance(result.entry, BibTeXEntry)
            assert result.entry.get_field("title") == "Quantum Computing Applications"
            assert result.entry.get_field("author") == "John Doe and Jane Smith"
            assert result.entry.get_field("year") == "2023"
            assert result.entry.get_field("eprint") == "2301.12345"
            assert result.entry.get_field("archiveprefix") == "arXiv"
            assert result.entry.get_field("primaryclass") == "quant-ph"
            assert result.entry.get_field("doi") == "10.1000/123"
            assert "arxiv.org" in result.entry.get_field("url")
            assert result.metadata.source_name == "arxiv"

    @pytest.mark.asyncio
    async def test_lookup_by_arxiv_http_error(self):
        """Test lookup with HTTP error."""
        with patch("httpx2.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                Exception("HTTP Error")
            )

            result = await self.source.lookup_by_arxiv("2301.12345")
            assert isinstance(result, LookupResult)
            assert result.entry is None
            assert "error" in result.metadata.error.lower()

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful search."""
        mock_response = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>Quantum Computing</title>
    <summary>A paper about quantum computing.</summary>
    <published>2023-01-15T10:30:00Z</published>
    <author>
      <name>John Doe</name>
    </author>
    <category term="quant-ph"/>
    <arxiv:id>2301.12345</arxiv:id>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2301.67890v1</id>
    <title>Machine Learning</title>
    <summary>A paper about machine learning.</summary>
    <published>2023-01-16T10:30:00Z</published>
    <author>
      <name>Jane Smith</name>
    </author>
    <category term="cs.LG"/>
    <arxiv:id>2301.67890</arxiv:id>
  </entry>
</feed>"""

        with patch("httpx2.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.text = mock_response
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response_obj
            )

            results = await self.source.search("quantum computing", max_results=5)

            assert len(results) == 2
            assert all(isinstance(entry, BibTeXEntry) for entry in results)

            # Check first result
            assert results[0].get_field("title") == "Quantum Computing"
            assert results[0].get_field("author") == "John Doe"
            assert results[0].get_field("eprint") == "2301.12345"

            # Check second result
            assert results[1].get_field("title") == "Machine Learning"
            assert results[1].get_field("author") == "Jane Smith"
            assert results[1].get_field("eprint") == "2301.67890"

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        """Test search with HTTP error."""
        with patch("httpx2.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                Exception("HTTP Error")
            )

            results = await self.source.search("quantum", max_results=5)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test search with no results."""
        mock_response = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
</feed>"""

        with patch("httpx2.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.text = mock_response
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response_obj
            )

            results = await self.source.search("nonexistent query", max_results=5)
            assert results == []

    def test_parse_arxiv_entry_minimal(self):
        """Test parsing arXiv entry with minimal data."""
        xml_content = """<entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <id>http://arxiv.org/abs/2301.12345v1</id>
  <title>Test Paper</title>
  <published>2023-01-15T10:30:00Z</published>
  <author>
    <name>Test Author</name>
  </author>
  <category term="cs.AI"/>
  <arxiv:id>2301.12345</arxiv:id>
</entry>"""

        import xml.etree.ElementTree as ET

        entry_elem = ET.fromstring(xml_content)

        result = self.source._parse_arxiv_entry(entry_elem)

        assert result is not None
        assert result.get_field("title") == "Test Paper"
        assert result.get_field("author") == "Test Author"
        assert result.get_field("year") == "2023"
        assert result.get_field("eprint") == "2301.12345"
        assert result.get_field("primaryclass") == "cs.AI"

    @pytest.mark.asyncio
    async def test_lookup_by_title_author(self):
        """Test lookup by title and author."""
        mock_response = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>Quantum Computing</title>
    <summary>A paper about quantum computing.</summary>
    <published>2023-01-15T10:30:00Z</published>
    <author>
      <name>John Doe</name>
    </author>
    <category term="quant-ph"/>
    <arxiv:id>2301.12345</arxiv:id>
  </entry>
</feed>"""

        with patch("httpx2.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.text = mock_response
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response_obj
            )

            results = await self.source.lookup_by_title_author(
                "Quantum Computing", "John Doe"
            )

            assert len(results) == 1
            assert isinstance(results[0], LookupResult)
            assert results[0].entry is not None
            assert results[0].entry.get_field("title") == "Quantum Computing"

    def test_get_source_info(self):
        """Test source information retrieval."""
        info = self.source.get_source_info()

        assert info["name"] == "arxiv"
        assert info["confidence"] == 0.70  # SourceConfidence.MEDIUM
        assert "arxiv" in info["supported_identifiers"]
        assert "Physics" in info["coverage"]
        assert "arxiv.org" in info["url"]
