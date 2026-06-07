"""arXiv API integration for academic preprint metadata retrieval.

This module provides integration with the arXiv API for fetching metadata
about academic preprints in physics, mathematics, computer science, and other fields.
"""

import re
import time
from typing import Any
import xml.etree.ElementTree as ET

import httpx2 as httpx
from loguru import logger

from .base import (
    BaseDataSource,
    LookupResult,
    SourceMetadata,
    SourceConfidence,
)
from ..core.entry import BibTeXEntry


class ArxivSource(BaseDataSource):
    """Source for arXiv preprint metadata."""

    def __init__(self, email: str | None = None) -> None:
        """Initialize arXiv source.

        Args:
            email: Optional email for polite crawling identification
        """
        super().__init__(
            name="arxiv",
            base_url="http://export.arxiv.org/api/query",
            confidence=SourceConfidence.MEDIUM,  # Secondary tier - preprints, not peer-reviewed
        )
        self.email = email

        # arXiv namespace for XML parsing
        self.namespace = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

    async def lookup_by_doi(self, doi: str) -> LookupResult:
        """Look up entry by DOI (not supported by arXiv)."""
        return LookupResult(
            entry=None,
            metadata=SourceMetadata(
                source_name=self.name,
                lookup_time=0.0,
                confidence=self.confidence,
                error="arXiv does not support DOI lookup",
            ),
        )

    async def lookup_by_title_author(
        self, title: str, author: str
    ) -> list[LookupResult]:
        """Look up entries by title and author."""
        start_time = time.time()

        # Build search query
        query_parts = []
        if title:
            query_parts.append(f'ti:"{title}"')
        if author:
            query_parts.append(f'au:"{author}"')

        if not query_parts:
            return [
                LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        error="Both title and author are required",
                    ),
                )
            ]

        query = " AND ".join(query_parts)
        entries = await self.search(query, max_results=5)

        results = []
        for entry in entries:
            results.append(
                LookupResult(
                    entry=entry,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                    ),
                )
            )

        return results

    def can_lookup_identifier(self, identifier_type: str) -> bool:
        """Check if this source can look up a specific identifier type."""
        return identifier_type.lower() == "arxiv"

    async def lookup_by_arxiv(self, arxiv_id: str) -> LookupResult:
        """Look up entry by arXiv identifier."""
        start_time = time.time()

        # Normalize arXiv ID format
        normalized_id = self._normalize_arxiv_id(arxiv_id)
        if not normalized_id:
            return LookupResult(
                entry=None,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=time.time() - start_time,
                    confidence=self.confidence,
                    error=f"Invalid arXiv ID format: {arxiv_id}",
                ),
            )

        logger.debug(f"Looking up arXiv ID: {normalized_id}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {"id_list": normalized_id, "max_results": 1}

                headers = {}
                if self.email:
                    headers["User-Agent"] = f"ReflInt/1.0 ({self.email})"

                response = await client.get(
                    self.base_url, params=params, headers=headers
                )
                response.raise_for_status()

                entry = self._parse_arxiv_response(response.text, normalized_id)

                return LookupResult(
                    entry=entry,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        api_response_size=len(response.text),
                    ),
                    raw_data={"response_text": response.text},
                )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching arXiv {normalized_id}: {e}")
            return LookupResult(
                entry=None,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=time.time() - start_time,
                    confidence=self.confidence,
                    error=f"HTTP error: {e}",
                ),
            )
        except Exception as e:
            logger.error(f"Error fetching arXiv {normalized_id}: {e}")
            return LookupResult(
                entry=None,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=time.time() - start_time,
                    confidence=self.confidence,
                    error=f"Unexpected error: {e}",
                ),
            )

    async def search(self, query: str, max_results: int = 10) -> list[BibTeXEntry]:
        """Search arXiv by query string.

        Args:
            query: Search query (title, author, abstract, etc.)
            max_results: Maximum number of results to return

        Returns:
            List of BibTeXEntry objects
        """
        logger.debug(f"Searching arXiv for: {query}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {
                    "search_query": query,
                    "max_results": max_results,
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                }

                headers = {}
                if self.email:
                    headers["User-Agent"] = f"ReflInt/1.0 ({self.email})"

                response = await client.get(
                    self.base_url, params=params, headers=headers
                )
                response.raise_for_status()

                return self._parse_arxiv_feed(response.text)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error searching arXiv: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching arXiv: {e}")
            return []

    def _normalize_arxiv_id(self, arxiv_id: str) -> str | None:
        """Normalize arXiv ID to canonical format.

        Args:
            arxiv_id: Raw arXiv identifier

        Returns:
            Normalized arXiv ID or None if invalid
        """
        # Remove common prefixes
        arxiv_id = re.sub(r"^(arxiv:|arXiv:)", "", arxiv_id, flags=re.IGNORECASE)

        # New format: YYMM.NNNN[vN]
        new_format = re.match(r"^(\d{4}\.\d{4,5})(v\d+)?$", arxiv_id)
        if new_format:
            return new_format.group(1)  # Return without version

        # Old format: subject-class/YYMMnnn
        old_format = re.match(r"^([a-z-]+)(\.[A-Z]{2})?/(\d{7})$", arxiv_id)
        if old_format:
            return arxiv_id

        return None

    def _parse_arxiv_response(
        self, xml_content: str, requested_id: str
    ) -> BibTeXEntry | None:
        """Parse arXiv API XML response for a single paper.

        Args:
            xml_content: XML response from arXiv API
            requested_id: The arXiv ID that was requested

        Returns:
            BibTeXEntry if found, None otherwise
        """
        try:
            root = ET.fromstring(xml_content)
            entries = root.findall(".//atom:entry", self.namespace)

            if not entries:
                logger.debug(f"No arXiv entry found for ID: {requested_id}")
                return None

            # Take the first entry
            return self._parse_arxiv_entry(entries[0])

        except ET.ParseError as e:
            logger.error(f"Error parsing arXiv XML response: {e}")
            return None

    def _parse_arxiv_feed(self, xml_content: str) -> list[BibTeXEntry]:
        """Parse arXiv API XML feed for multiple papers.

        Args:
            xml_content: XML response from arXiv API

        Returns:
            List of BibTeXEntry objects
        """
        entries = []
        try:
            root = ET.fromstring(xml_content)
            xml_entries = root.findall(".//atom:entry", self.namespace)

            for xml_entry in xml_entries:
                entry = self._parse_arxiv_entry(xml_entry)
                if entry:
                    entries.append(entry)

        except ET.ParseError as e:
            logger.error(f"Error parsing arXiv XML feed: {e}")

        return entries

    def _parse_arxiv_entry(self, xml_entry: ET.Element) -> BibTeXEntry | None:
        """Parse a single arXiv entry from XML.

        Args:
            xml_entry: XML element representing one arXiv entry

        Returns:
            BibTeXEntry or None if parsing fails
        """
        try:
            # Extract basic metadata
            arxiv_id = self._extract_arxiv_id(xml_entry)
            if not arxiv_id:
                return None

            title = self._extract_text(xml_entry, ".//atom:title")
            summary = self._extract_text(xml_entry, ".//atom:summary")
            published = self._extract_text(xml_entry, ".//atom:published")

            # Extract authors
            authors = self._extract_authors(xml_entry)

            # Extract categories (subjects)
            categories = self._extract_categories(xml_entry)

            # Extract DOI if present
            doi = self._extract_doi(xml_entry)

            # Parse publication date
            year = self._extract_year(published)

            # Build BibTeX entry
            entry_data = {
                "ID": self._generate_entry_key(authors, year, title),
                "ENTRYTYPE": "article",  # Default to article type
                "title": self._clean_title(title),
                "author": self._format_authors(authors),
                "year": str(year) if year else "",
                "eprint": arxiv_id,
                "archiveprefix": "arXiv",
                "primaryclass": categories[0] if categories else "",
            }

            # Add optional fields
            if summary:
                entry_data["abstract"] = self._clean_abstract(summary)
            if doi:
                entry_data["doi"] = doi
            if len(categories) > 1:
                entry_data["note"] = f"arXiv subjects: {', '.join(categories)}"

            # Add arXiv URL
            entry_data["url"] = f"https://arxiv.org/abs/{arxiv_id}"

            return BibTeXEntry(entry_data)

        except Exception as e:
            logger.error(f"Error parsing arXiv entry: {e}")
            return None

    def _extract_arxiv_id(self, entry: ET.Element) -> str | None:
        """Extract arXiv ID from entry."""
        arxiv_id_elem = entry.find(".//arxiv:id", self.namespace)
        if arxiv_id_elem is not None and arxiv_id_elem.text:
            return arxiv_id_elem.text.strip()

        # Fallback: extract from atom:id URL
        id_elem = entry.find(".//atom:id", self.namespace)
        if id_elem is not None and id_elem.text:
            match = re.search(r"/abs/(.+)$", id_elem.text)
            if match:
                return match.group(1)

        return None

    def _extract_text(self, entry: ET.Element, xpath: str) -> str:
        """Extract text content from XML element."""
        elem = entry.find(xpath, self.namespace)
        return elem.text.strip() if elem is not None and elem.text else ""

    def _extract_authors(self, entry: ET.Element) -> list[str]:
        """Extract author list from entry."""
        authors = []
        author_elems = entry.findall(".//atom:author", self.namespace)

        for author_elem in author_elems:
            name_elem = author_elem.find(".//atom:name", self.namespace)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text.strip())

        return authors

    def _extract_categories(self, entry: ET.Element) -> list[str]:
        """Extract subject categories from entry."""
        categories = []
        category_elems = entry.findall(".//atom:category", self.namespace)

        for cat_elem in category_elems:
            term = cat_elem.get("term")
            if term:
                categories.append(term)

        return categories

    def _extract_doi(self, entry: ET.Element) -> str | None:
        """Extract DOI if present in entry."""
        doi_elem = entry.find(".//arxiv:doi", self.namespace)
        if doi_elem is not None and doi_elem.text:
            return doi_elem.text.strip()
        return None

    def _extract_year(self, date_str: str) -> int | None:
        """Extract year from date string."""
        if not date_str:
            return None

        match = re.match(r"^(\d{4})", date_str)
        if match:
            return int(match.group(1))
        return None

    def _clean_title(self, title: str) -> str:
        """Clean and format title."""
        if not title:
            return ""

        # Remove extra whitespace and normalize
        title = re.sub(r"\s+", " ", title.strip())

        # arXiv titles sometimes have newlines
        return title.replace("\n", " ")

    def _clean_abstract(self, abstract: str) -> str:
        """Clean and format abstract."""
        if not abstract:
            return ""

        # Remove extra whitespace and normalize
        abstract = re.sub(r"\s+", " ", abstract.strip())

        # Remove newlines but preserve paragraph breaks
        abstract = re.sub(r"\n\s*\n", "\n\n", abstract)
        return abstract.replace("\n", " ")

    def _format_authors(self, authors: list[str]) -> str:
        """Format author list for BibTeX."""
        if not authors:
            return ""

        # arXiv author names are typically in "First Last" format
        formatted_authors = []
        for author in authors:
            # Split name and reformat if needed
            parts = author.strip().split()
            if len(parts) >= 2:
                # Keep as "First Last" format for arXiv
                formatted_authors.append(author.strip())
            else:
                formatted_authors.append(author.strip())

        return " and ".join(formatted_authors)

    def _generate_entry_key(
        self, authors: list[str], year: int | None, title: str
    ) -> str:
        """Generate BibTeX entry key."""
        # Use first author's last name
        author_key = "arxiv"
        if authors:
            first_author = authors[0]
            parts = first_author.split()
            if parts:
                author_key = parts[-1].lower()  # Last name
                # Remove non-alphanumeric characters
                author_key = re.sub(r"[^a-z0-9]", "", author_key)

        year_key = str(year) if year else "unknown"

        # Add a short title word if possible
        title_words = re.findall(r"\b[a-zA-Z]{4,}\b", title.lower())
        title_key = title_words[0] if title_words else "paper"

        return f"{author_key}{year_key}{title_key}"

    def get_supported_identifiers(self) -> list[str]:
        """Get list of supported identifier types."""
        return ["arxiv"]

    def get_source_info(self) -> dict[str, Any]:
        """Get information about this source."""
        return {
            "name": self.name,
            "description": "arXiv preprint repository",
            "confidence": self.confidence,
            "supported_identifiers": self.get_supported_identifiers(),
            "rate_limit": "3 requests/second (recommended)",
            "coverage": "Physics, Mathematics, Computer Science, Quantitative Biology, Statistics",
            "url": "https://arxiv.org",
        }
