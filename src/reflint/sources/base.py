"""Base classes for external data sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from enum import Enum

from ..core.entry import BibTeXEntry


class DataSourceError(Exception):
    """Base exception for data source errors."""

    pass


class SourceConfidence(Enum):
    """Confidence levels for data source reliability."""

    VERY_HIGH = 0.95
    HIGH = 0.85
    MEDIUM = 0.70
    LOW = 0.50
    VERY_LOW = 0.30


@dataclass
class SourceMetadata:
    """Metadata about a data source lookup result."""

    source_name: str
    lookup_time: float
    confidence: float
    api_response_size: int = 0
    cached: bool = False
    rate_limited: bool = False
    error: str | None = None


@dataclass
class LookupResult:
    """Result from a data source lookup."""

    entry: BibTeXEntry | None
    metadata: SourceMetadata
    raw_data: dict | None = None


class BaseDataSource(ABC):
    """Abstract base class for external data sources."""

    def __init__(
        self,
        name: str,
        base_url: str,
        confidence: SourceConfidence = SourceConfidence.MEDIUM,
    ) -> None:
        self.name = name
        self.base_url = base_url
        self.confidence = confidence.value
        self._rate_limiter: Any | None = None

    @abstractmethod
    async def lookup_by_doi(self, doi: str) -> LookupResult:
        """Look up entry by DOI."""
        pass

    @abstractmethod
    async def lookup_by_title_author(
        self, title: str, author: str
    ) -> list[LookupResult]:
        """Look up entries by title and author."""
        pass

    @abstractmethod
    def can_lookup_identifier(self, identifier_type: str) -> bool:
        """Check if this source can look up a specific identifier type."""
        pass

    async def lookup_by_identifier(
        self, identifier_type: str, value: str
    ) -> LookupResult:
        """Look up entry by generic identifier."""
        if identifier_type == "doi":
            return await self.lookup_by_doi(value)
        elif identifier_type == "arxiv":
            return await self.lookup_by_arxiv(value)
        elif identifier_type == "pmid":
            return await self.lookup_by_pmid(value)
        else:
            raise DataSourceError(f"Unsupported identifier type: {identifier_type}")

    async def lookup_by_arxiv(self, arxiv_id: str) -> LookupResult:
        """Look up entry by arXiv ID. Default implementation raises error."""
        raise DataSourceError(f"{self.name} does not support arXiv lookup")

    async def lookup_by_pmid(self, pmid: str) -> LookupResult:
        """Look up entry by PMID. Default implementation raises error."""
        raise DataSourceError(f"{self.name} does not support PMID lookup")

    def get_reliability_score(self, field_name: str) -> float:
        """Get reliability score for a specific field."""
        # Default implementation returns base confidence
        # Subclasses can override for field-specific reliability
        return self.confidence

    def set_rate_limiter(self, rate_limiter: Any) -> None:
        """Set rate limiter for API calls."""
        self._rate_limiter = rate_limiter

    @abstractmethod
    def get_supported_identifiers(self) -> list[str]:
        """Get list of supported identifier types."""
        pass

    def __str__(self) -> str:
        return f"{self.name} (confidence: {self.confidence:.2f})"
