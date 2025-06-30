"""Tests for PubMed source integration."""

import pytest
from unittest.mock import AsyncMock, patch

from src.reflint.sources.pubmed import PubMedSource
from src.reflint.sources.base import LookupResult
from src.reflint.core.entry import BibTeXEntry


class TestPubMedSource:
    """Test cases for PubMedSource."""

    def setup_method(self):
        """Set up test fixtures."""
        self.source = PubMedSource(email="test@example.com", api_key="test_key")

    def test_init(self):
        """Test PubMedSource initialization."""
        assert self.source.name == "pubmed"
        assert self.source.confidence == 0.95  # SourceConfidence.VERY_HIGH
        assert self.source.email == "test@example.com"
        assert self.source.api_key == "test_key"
        assert self.source.rate_limit == 10  # With API key

    def test_init_no_api_key(self):
        """Test initialization without API key."""
        source = PubMedSource(email="test@example.com")
        assert source.rate_limit == 3  # Without API key

    def test_can_lookup_identifier(self):
        """Test identifier type checking."""
        assert self.source.can_lookup_identifier("pmid")
        assert self.source.can_lookup_identifier("doi")
        assert not self.source.can_lookup_identifier("arxiv")

    def test_clean_pmid(self):
        """Test PMID cleaning and validation."""
        assert self.source._clean_pmid("12345678") == "12345678"
        assert self.source._clean_pmid("pmid:12345678") == "12345678"
        assert self.source._clean_pmid("PMID:12345678") == "12345678"
        assert self.source._clean_pmid("  12345678  ") == "12345678"
        assert self.source._clean_pmid("invalid") is None
        assert self.source._clean_pmid("123abc") is None

    def test_month_name_to_number(self):
        """Test month name to number conversion."""
        assert self.source._month_name_to_number("January") == 1
        assert self.source._month_name_to_number("jan") == 1
        assert self.source._month_name_to_number("JAN") == 1
        assert self.source._month_name_to_number("December") == 12
        assert self.source._month_name_to_number("dec") == 12
        assert self.source._month_name_to_number("invalid") is None

    def test_clean_title(self):
        """Test title cleaning."""
        assert self.source._clean_title("A Study of Cancer.") == "A Study of Cancer"
        assert self.source._clean_title("  Multiple   Spaces  ") == "Multiple Spaces"
        assert self.source._clean_title("") == ""

    def test_format_authors(self):
        """Test author formatting."""
        authors = ["Smith, John", "Doe, Jane", "Wilson, Bob"]
        expected = "Smith, John and Doe, Jane and Wilson, Bob"
        assert self.source._format_authors(authors) == expected
        assert self.source._format_authors([]) == ""

    def test_generate_entry_key(self):
        """Test BibTeX entry key generation."""
        authors = ["Smith, John A", "Doe, Jane"]
        year = 2023
        title = "Cancer Research Study"

        key = self.source._generate_entry_key(authors, year, title)
        assert "smith" in key.lower()
        assert "2023" in key
        assert "cancer" in key.lower()

    def test_generate_entry_key_no_author(self):
        """Test entry key generation with no authors."""
        key = self.source._generate_entry_key([], 2023, "Cancer Research")
        assert "pubmed" in key.lower()
        assert "2023" in key
        assert "cancer" in key.lower()

    def test_parse_search_results(self):
        """Test parsing of search results XML."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
  <IdList>
    <Id>12345678</Id>
    <Id>87654321</Id>
  </IdList>
</eSearchResult>"""

        pmids = self.source._parse_search_results(xml_content)
        assert pmids == ["12345678", "87654321"]

    def test_parse_search_results_empty(self):
        """Test parsing empty search results."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
  <IdList>
  </IdList>
</eSearchResult>"""

        pmids = self.source._parse_search_results(xml_content)
        assert pmids == []

    @pytest.mark.asyncio
    async def test_lookup_by_pmid_invalid(self):
        """Test lookup with invalid PMID."""
        result = await self.source.lookup_by_pmid("invalid")
        assert isinstance(result, LookupResult)
        assert result.entry is None
        assert "Invalid PMID" in result.metadata.error

    @pytest.mark.asyncio
    async def test_lookup_by_pmid_success(self):
        """Test successful PMID lookup."""
        mock_response = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>Cancer Research Study in Oncology.</ArticleTitle>
        <AuthorList>
          <Author>
            <LastName>Smith</LastName>
            <ForeName>John A</ForeName>
            <Initials>JA</Initials>
          </Author>
          <Author>
            <LastName>Doe</LastName>
            <ForeName>Jane</ForeName>
            <Initials>J</Initials>
          </Author>
        </AuthorList>
        <Journal>
          <Title>Journal of Cancer Research</Title>
          <ISSN>1234-5678</ISSN>
          <JournalIssue>
            <Volume>45</Volume>
            <Issue>3</Issue>
            <PubDate>
              <Year>2023</Year>
              <Month>Mar</Month>
            </PubDate>
          </JournalIssue>
        </Journal>
        <Pagination>
          <MedlinePgn>123-130</MedlinePgn>
        </Pagination>
        <Abstract>
          <AbstractText>This study investigates cancer mechanisms.</AbstractText>
        </Abstract>
        <ArticleIdList>
          <ArticleId IdType="doi">10.1000/123</ArticleId>
          <ArticleId IdType="pmc">PMC1234567</ArticleId>
        </ArticleIdList>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""

        with patch("httpx.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.text = mock_response
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response_obj
            )

            # Mock the rate limiting
            with patch.object(self.source, "_rate_limit", return_value=None):
                result = await self.source.lookup_by_pmid("12345678")

            assert isinstance(result, LookupResult)
            assert result.entry is not None
            assert isinstance(result.entry, BibTeXEntry)
            assert (
                result.entry.get_field("title") == "Cancer Research Study in Oncology"
            )
            assert result.entry.get_field("author") == "Smith, John A and Doe, Jane"
            assert result.entry.get_field("journal") == "Journal of Cancer Research"
            assert result.entry.get_field("year") == "2023"
            assert result.entry.get_field("volume") == "45"
            assert result.entry.get_field("number") == "3"
            assert result.entry.get_field("pages") == "123-130"
            assert result.entry.get_field("pmid") == "12345678"
            assert result.entry.get_field("doi") == "10.1000/123"
            assert result.entry.get_field("pmc") == "PMC1234567"
            assert result.entry.get_field("issn") == "1234-5678"
            assert "cancer mechanisms" in result.entry.get_field("abstract")
            assert "pubmed.ncbi.nlm.nih.gov" in result.entry.get_field("url")

    @pytest.mark.asyncio
    async def test_lookup_by_pmid_http_error(self):
        """Test PMID lookup with HTTP error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                Exception("HTTP Error")
            )

            with patch.object(self.source, "_rate_limit", return_value=None):
                result = await self.source.lookup_by_pmid("12345678")

            assert isinstance(result, LookupResult)
            assert result.entry is None
            assert "error" in result.metadata.error.lower()

    @pytest.mark.asyncio
    async def test_lookup_by_doi(self):
        """Test DOI lookup (searches then fetches)."""
        # Mock search results
        search_response = """<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
  <IdList>
    <Id>12345678</Id>
  </IdList>
</eSearchResult>"""

        # Mock fetch response
        fetch_response = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>Test Article.</ArticleTitle>
        <AuthorList>
          <Author>
            <LastName>Test</LastName>
            <ForeName>Author</ForeName>
          </Author>
        </AuthorList>
        <Journal>
          <Title>Test Journal</Title>
          <JournalIssue>
            <PubDate>
              <Year>2023</Year>
            </PubDate>
          </JournalIssue>
        </Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value

            # First call returns search results, second call returns article details
            responses = [
                AsyncMock(text=search_response, raise_for_status=lambda: None),
                AsyncMock(text=fetch_response, raise_for_status=lambda: None),
            ]
            mock_client_instance.get.side_effect = responses

            with patch.object(self.source, "_rate_limit", return_value=None):
                result = await self.source.lookup_by_doi("10.1000/123")

            assert isinstance(result, LookupResult)
            assert result.entry is not None
            assert result.entry.get_field("title") == "Test Article"

    @pytest.mark.asyncio
    async def test_lookup_by_doi_not_found(self):
        """Test DOI lookup when no results found."""
        search_response = """<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
  <IdList>
  </IdList>
</eSearchResult>"""

        with patch("httpx.AsyncClient") as mock_client:
            mock_response_obj = AsyncMock()
            mock_response_obj.text = search_response
            mock_response_obj.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response_obj
            )

            with patch.object(self.source, "_rate_limit", return_value=None):
                result = await self.source.lookup_by_doi("10.1000/123")

            assert isinstance(result, LookupResult)
            assert result.entry is None
            assert "No PubMed entry found" in result.metadata.error

    @pytest.mark.asyncio
    async def test_lookup_by_title_author(self):
        """Test lookup by title and author."""
        # Mock search results
        search_response = """<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
  <IdList>
    <Id>12345678</Id>
  </IdList>
</eSearchResult>"""

        # Mock fetch response
        fetch_response = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>Cancer Research.</ArticleTitle>
        <AuthorList>
          <Author>
            <LastName>Smith</LastName>
            <ForeName>John</ForeName>
          </Author>
        </AuthorList>
        <Journal>
          <Title>Test Journal</Title>
          <JournalIssue>
            <PubDate>
              <Year>2023</Year>
            </PubDate>
          </JournalIssue>
        </Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value

            responses = [
                AsyncMock(text=search_response, raise_for_status=lambda: None),
                AsyncMock(text=fetch_response, raise_for_status=lambda: None),
            ]
            mock_client_instance.get.side_effect = responses

            with patch.object(self.source, "_rate_limit", return_value=None):
                results = await self.source.lookup_by_title_author(
                    "Cancer Research", "John Smith"
                )

            assert len(results) == 1
            assert isinstance(results[0], LookupResult)
            assert results[0].entry is not None
            assert results[0].entry.get_field("title") == "Cancer Research"

    @pytest.mark.asyncio
    async def test_lookup_by_title_author_no_params(self):
        """Test lookup with missing title and author."""
        results = await self.source.lookup_by_title_author("", "")

        assert len(results) == 1
        assert isinstance(results[0], LookupResult)
        assert results[0].entry is None
        assert "required" in results[0].metadata.error

    def test_extract_article_metadata_minimal(self):
        """Test metadata extraction with minimal article data."""
        xml_content = """<PubmedArticle>
  <MedlineCitation>
    <Article>
      <ArticleTitle>Minimal Article</ArticleTitle>
      <AuthorList>
        <Author>
          <LastName>Test</LastName>
          <ForeName>Author</ForeName>
        </Author>
      </AuthorList>
      <Journal>
        <Title>Test Journal</Title>
        <JournalIssue>
          <PubDate>
            <Year>2023</Year>
          </PubDate>
        </JournalIssue>
      </Journal>
    </Article>
  </MedlineCitation>
</PubmedArticle>"""

        import xml.etree.ElementTree as ET

        article_elem = ET.fromstring(xml_content)

        result = self.source._extract_article_metadata(article_elem, "12345678")

        assert result is not None
        assert result.get_field("title") == "Minimal Article"
        assert result.get_field("author") == "Test, Author"
        assert result.get_field("year") == "2023"
        assert result.get_field("pmid") == "12345678"

    def test_get_source_info(self):
        """Test source information retrieval."""
        info = self.source.get_source_info()

        assert info["name"] == "pubmed"
        assert info["confidence"] == 0.95
        assert "pmid" in info["supported_identifiers"]
        assert "doi" in info["supported_identifiers"]
        assert "Medical" in info["coverage"]
        assert "pubmed.ncbi.nlm.nih.gov" in info["url"]
        assert "10 requests/second" in info["rate_limit"]
