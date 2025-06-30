"""Tests for data source registry."""

import pytest
from unittest.mock import AsyncMock

from reflint.sources.base import (
    BaseDataSource,
    LookupResult,
    SourceMetadata,
    SourceConfidence,
)
from reflint.sources.registry import DataSourceRegistry
from reflint.core.entry import BibTeXEntry


class MockDataSource(BaseDataSource):
    """Mock data source for testing."""

    def __init__(self, name: str, supported_ids: list[str]) -> None:
        super().__init__(name, "https://api.example.com", SourceConfidence.HIGH)
        self.supported_ids = supported_ids
        self.lookup_doi = AsyncMock(return_value=self._create_mock_result())
        self.lookup_by_title_author = AsyncMock(
            return_value=[self._create_mock_result()]
        )

    def _create_mock_result(self) -> LookupResult:
        """Create a mock lookup result."""
        entry_dict = {
            "ID": "mock_entry",
            "ENTRYTYPE": "article",
            "title": "Mock Title",
            "author": "Mock Author",
        }
        entry = BibTeXEntry(entry_dict)

        metadata = SourceMetadata(
            source_name=self.name, lookup_time=0.1, confidence=self.confidence
        )

        return LookupResult(entry=entry, metadata=metadata)

    async def lookup_by_doi(self, doi: str) -> LookupResult:
        return await self.lookup_doi(doi)

    async def lookup_by_title_author(
        self, title: str, author: str
    ) -> list[LookupResult]:
        return await self.lookup_by_title_author(title, author)

    def can_lookup_identifier(self, identifier_type: str) -> bool:
        return identifier_type in self.supported_ids

    def get_supported_identifiers(self) -> list[str]:
        return self.supported_ids


class TestDataSourceRegistry:
    """Test the data source registry."""

    def test_register_source(self):
        """Test source registration."""
        registry = DataSourceRegistry()
        source = MockDataSource("test_source", ["doi", "arxiv"])

        registry.register_source(source)

        assert "test_source" in registry.get_source_names()
        assert registry.get_source("test_source") == source

    def test_get_sources_for_identifier(self):
        """Test getting sources by identifier type."""
        registry = DataSourceRegistry()

        source1 = MockDataSource("source1", ["doi", "arxiv"])
        source2 = MockDataSource("source2", ["doi", "pmid"])

        registry.register_source(source1)
        registry.register_source(source2)

        # DOI sources (both)
        doi_sources = registry.get_sources_for_identifier("doi")
        assert len(doi_sources) == 2

        # arXiv sources (only source1)
        arxiv_sources = registry.get_sources_for_identifier("arxiv")
        assert len(arxiv_sources) == 1
        assert arxiv_sources[0] == source1

        # Unsupported identifier
        unsupported_sources = registry.get_sources_for_identifier("isbn")
        assert len(unsupported_sources) == 0

    @pytest.mark.asyncio
    async def test_lookup_with_fallback(self):
        """Test lookup with fallback across sources."""
        registry = DataSourceRegistry()

        source1 = MockDataSource("source1", ["doi"])
        source2 = MockDataSource("source2", ["doi"])

        registry.register_source(source1)
        registry.register_source(source2)

        # Both sources should be called
        results = await registry.lookup_with_fallback("doi", "10.1234/test")

        assert len(results) == 2  # One result from each source
        source1.lookup_doi.assert_called_once_with("10.1234/test")
        source2.lookup_doi.assert_called_once_with("10.1234/test")

    def test_get_statistics(self):
        """Test registry statistics."""
        registry = DataSourceRegistry()

        source1 = MockDataSource("source1", ["doi", "arxiv"])
        source2 = MockDataSource("source2", ["doi", "pmid"])

        registry.register_source(source1)
        registry.register_source(source2)

        stats = registry.get_statistics()

        assert stats["total_sources"] == 2
        assert stats["sources_by_identifier"]["doi"] == 2
        assert stats["sources_by_identifier"]["arxiv"] == 1
        assert stats["sources_by_identifier"]["pmid"] == 1
        assert len(stats["source_details"]) == 2
