"""Semantic Scholar API integration for academic paper metadata."""

import asyncio
import time
from typing import Any, cast
from urllib.parse import quote

import httpx2 as httpx
from loguru import logger

from .base import (
    BaseDataSource,
    LookupResult,
    SourceMetadata,
    SourceConfidence,
    DataSourceError,
)
from ..core.entry import BibTeXEntry
from ..utils.cached_http import cached_httpx_get


class SemanticScholarSource(BaseDataSource):
    """Semantic Scholar data source for academic paper metadata."""

    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        super().__init__(
            name="semantic_scholar",
            base_url="https://api.semanticscholar.org/graph/v1",
            confidence=SourceConfidence.HIGH,
        )
        self.api_key = api_key
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None

        # Fields to request from S2 API
        self.paper_fields = [
            "paperId",
            "corpusId",
            "title",
            "abstract",
            "venue",
            "year",
            "authors",
            "externalIds",
            "journal",
            "publicationTypes",
            "publicationDate",
            "citationCount",
            "referenceCount",
            "fieldsOfStudy",
            "s2FieldsOfStudy",
        ]

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                headers=self._get_headers(), timeout=self.timeout, follow_redirects=True
            )
        return self._session

    def _get_headers(self) -> dict[str, str]:
        """Build request headers for Semantic Scholar."""
        headers = {"User-Agent": "ReflInt/1.0 (https://github.com/reflint/reflint)"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def _cached_get_with_retry(
        self, url: str, params: dict[str, Any], max_retries: int = 3
    ) -> httpx.Response:
        """GET with bounded retry for Semantic Scholar rate limiting."""
        retry_count = 0
        while retry_count <= max_retries:
            try:
                return await cached_httpx_get(
                    url=url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=float(self.timeout),
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 429:
                    raise
                retry_count += 1
                if retry_count > max_retries:
                    raise
                await asyncio.sleep(min(retry_count * 2, 60))

        raise DataSourceError("Semantic Scholar retry loop exhausted unexpectedly")

    async def lookup_by_doi(self, doi: str) -> LookupResult:
        """Look up entry by DOI."""
        return await self._lookup_by_identifier("DOI", doi)

    async def lookup_by_arxiv(self, arxiv_id: str) -> LookupResult:
        """Look up entry by arXiv ID."""
        return await self._lookup_by_identifier("ArXiv", arxiv_id)

    async def lookup_by_pmid(self, pmid: str) -> LookupResult:
        """Look up entry by PMID."""
        return await self._lookup_by_identifier("PubMed", pmid)

    async def _lookup_by_identifier(self, id_type: str, value: str) -> LookupResult:
        """Look up entry by identifier type."""
        start_time = time.time()

        # Clean identifier
        clean_value = value.strip()
        if id_type == "DOI":
            clean_value = clean_value.replace("https://doi.org/", "").replace(
                "http://dx.doi.org/", ""
            )

        url = f"{self.base_url}/paper/{id_type}:{quote(clean_value)}"
        params = {"fields": ",".join(self.paper_fields)}

        try:
            response = await self._cached_get_with_retry(url, params)
            lookup_time = time.time() - start_time

            if response.status_code == 404:
                return LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=lookup_time,
                        confidence=self.confidence,
                        api_response_size=len(response.content),
                        error=f"{id_type} not found",
                    ),
                )

            response.raise_for_status()
            data = cast("dict[str, Any]", response.json())

            entry = self._convert_to_bibtex(data)

            return LookupResult(
                entry=entry,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=lookup_time,
                    confidence=self.confidence,
                    api_response_size=len(response.content),
                ),
                raw_data=data,
            )

        except httpx.HTTPStatusError as e:
            lookup_time = time.time() - start_time
            if e.response.status_code == 429:
                logger.warning("Semantic Scholar rate limit exceeded")
                return LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=lookup_time,
                        confidence=self.confidence,
                        rate_limited=True,
                        error="Rate limited",
                    ),
                )
            raise DataSourceError(f"Semantic Scholar API error: {e}")

        except Exception as e:
            lookup_time = time.time() - start_time
            raise DataSourceError(f"Semantic Scholar lookup failed: {e}")

    async def lookup_by_title_author(
        self, title: str, author: str
    ) -> list[LookupResult]:
        """Look up entries by title and author."""
        start_time = time.time()
        # Build query
        query_parts = []
        if title:
            query_parts.append(title.strip())
        if author:
            query_parts.append(author.strip())

        query = " ".join(query_parts)
        url = f"{self.base_url}/paper/search"
        params = {"query": query, "limit": "5", "fields": ",".join(self.paper_fields)}

        try:
            response = await self._cached_get_with_retry(url, params)
            lookup_time = time.time() - start_time
            response.raise_for_status()

            data = cast("dict[str, Any]", response.json())
            papers = data.get("data", [])

            results = []
            for paper in papers:
                entry = self._convert_to_bibtex(paper)
                if entry:
                    results.append(
                        LookupResult(
                            entry=entry,
                            metadata=SourceMetadata(
                                source_name=self.name,
                                lookup_time=lookup_time
                                / len(papers),  # Distribute time
                                confidence=self.confidence
                                * 0.9,  # Slightly lower for search
                                api_response_size=len(response.content) // len(papers),
                            ),
                            raw_data=paper,
                        )
                    )

            return results

        except Exception as e:
            raise DataSourceError(f"Semantic Scholar title/author search failed: {e}")

    def _convert_to_bibtex(self, paper: dict[str, Any]) -> BibTeXEntry | None:
        """Convert Semantic Scholar paper data to BibTeX entry."""
        if not paper:
            return None

        # Determine entry type
        entry_type = self._determine_entry_type(paper)

        # Create entry dict
        entry_data = {"ID": self._generate_key(paper), "ENTRYTYPE": entry_type}

        # Add identifiers
        external_ids = paper.get("externalIds", {})
        if external_ids:
            if external_ids.get("DOI"):
                entry_data["doi"] = external_ids["DOI"]
            if external_ids.get("ArXiv"):
                entry_data["eprint"] = external_ids["ArXiv"]
                entry_data["archivePrefix"] = "arXiv"
            if external_ids.get("PubMed"):
                entry_data["note"] = f"PMID: {external_ids['PubMed']}"

        # Add title
        title = paper.get("title")
        if title:
            entry_data["title"] = title

        # Add authors
        authors = self._extract_authors(paper)
        if authors:
            entry_data["author"] = authors

        # Add venue/journal
        venue = self._extract_venue(paper, entry_type)
        if venue:
            if entry_type == "article":
                entry_data["journal"] = venue
            elif entry_type == "inproceedings":
                entry_data["booktitle"] = venue
            else:
                entry_data["journal"] = venue

        # Add year
        year = paper.get("year")
        if year:
            entry_data["year"] = str(year)

        # Add abstract
        abstract = paper.get("abstract")
        if abstract:
            entry_data["abstract"] = abstract

        # Add citation count as note
        citation_count = paper.get("citationCount")
        if citation_count is not None:
            note_parts = []
            if entry_data.get("note"):
                note_parts.append(entry_data["note"])
            note_parts.append(f"Citations: {citation_count}")
            entry_data["note"] = "; ".join(note_parts)

        # Add URL using DOI if available, otherwise S2 URL
        if external_ids and external_ids.get("DOI"):
            entry_data["url"] = f"https://doi.org/{external_ids['DOI']}"
        elif paper.get("paperId"):
            entry_data["url"] = (
                f"https://www.semanticscholar.org/paper/{paper['paperId']}"
            )

        # Add fields of study as keywords
        fields = self._extract_fields_of_study(paper)
        if fields:
            entry_data["keywords"] = fields

        return BibTeXEntry(entry_data)

    def _determine_entry_type(self, paper: dict[str, Any]) -> str:
        """Determine BibTeX entry type from Semantic Scholar data."""
        publication_types = paper.get("publicationTypes", [])
        venue = paper.get("venue", "").lower()
        journal_info = paper.get("journal", {})

        # Check publication types
        if "JournalArticle" in publication_types:
            return "article"
        if "Conference" in publication_types or "ConferencePaper" in publication_types:
            return "inproceedings"
        if "Book" in publication_types:
            return "book"
        if "BookSection" in publication_types:
            return "inbook"
        if "Thesis" in publication_types:
            return "phdthesis"
        if "Review" in publication_types:
            return "article"

        # Check venue information
        if journal_info or "journal" in venue:
            return "article"
        if any(
            conf_word in venue
            for conf_word in ["conference", "workshop", "symposium", "proceedings"]
        ):
            return "inproceedings"

        # Check for arXiv preprints
        external_ids = paper.get("externalIds", {})
        if external_ids.get("ArXiv") and not external_ids.get("DOI"):
            return "misc"  # Preprint

        return "misc"  # Default

    def _extract_authors(self, paper: dict[str, Any]) -> str | None:
        """Extract authors from Semantic Scholar data."""
        authors = paper.get("authors", [])
        if not authors:
            return None

        author_strings = []
        for author in authors:
            name = author.get("name", "")
            if name:
                author_strings.append(name)

        return " and ".join(author_strings) if author_strings else None

    def _extract_venue(self, paper: dict[str, Any], entry_type: str) -> str | None:
        """Extract venue information."""
        # First try the venue field
        venue = paper.get("venue")
        if venue:
            return str(venue)

        # Try journal information
        journal = paper.get("journal", {})
        if journal:
            journal_name = journal.get("name")
            if journal_name:
                return str(journal_name)

        return None

    def _extract_fields_of_study(self, paper: dict[str, Any]) -> str | None:
        """Extract fields of study as keywords."""
        # Try S2 fields first (more detailed)
        s2_fields = paper.get("s2FieldsOfStudy", [])
        if s2_fields:
            field_names = [
                field.get("category", "")
                for field in s2_fields
                if field.get("category")
            ]
            if field_names:
                return ", ".join(field_names)

        # Fall back to regular fields
        fields = paper.get("fieldsOfStudy", [])
        if fields:
            return ", ".join(fields)

        return None

    def _generate_key(self, paper: dict[str, Any]) -> str:
        """Generate BibTeX key from paper data."""
        # Get first author's last name
        authors = paper.get("authors", [])
        author_key = ""
        if authors and len(authors) > 0:
            name = authors[0].get("name", "")
            if name:
                # Try to extract last name (assume last word)
                name_parts = name.split()
                if name_parts:
                    author_key = name_parts[-1].replace(" ", "").lower()

        if not author_key:
            author_key = "unknown"

        # Get year
        year = paper.get("year")
        year_key = str(year) if year else "unknown"

        # Get first word of title
        title = paper.get("title", "")
        title_key = ""
        if title:
            words = title.split()
            if words:
                title_key = words[0].lower().replace(":", "").replace(",", "")

        if not title_key:
            title_key = "unknown"

        return f"{author_key}{year_key}{title_key}"

    def can_lookup_identifier(self, identifier_type: str) -> bool:
        """Check if this source can look up a specific identifier type."""
        return identifier_type in ["doi", "arxiv", "pmid"]

    def get_supported_identifiers(self) -> list[str]:
        """Get list of supported identifier types."""
        return ["doi", "arxiv", "pmid"]

    def get_reliability_score(self, field_name: str) -> float:
        """Get reliability score for a specific field."""
        # Semantic Scholar reliability by field
        field_reliability = {
            "title": 0.95,
            "author": 0.90,
            "abstract": 0.95,  # S2 is very good for abstracts
            "year": 0.85,
            "venue": 0.80,
            "journal": 0.80,
            "doi": 0.95,
            "keywords": 0.90,  # Good for fields of study
            "url": 0.90,
        }

        return field_reliability.get(field_name, self.confidence)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.aclose()
            self._session = None
