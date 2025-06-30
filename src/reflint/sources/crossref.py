"""CrossRef API integration for bibliographic metadata."""

import time
from urllib.parse import quote

import httpx
from loguru import logger

from .base import (
    BaseDataSource,
    LookupResult,
    SourceMetadata,
    SourceConfidence,
    DataSourceError,
)
from ..core.entry import BibTeXEntry


class CrossRefSource(BaseDataSource):
    """CrossRef data source for bibliographic metadata lookup."""

    def __init__(self, email: str | None = None, timeout: int = 30) -> None:
        super().__init__(
            name="crossref",
            base_url="https://api.crossref.org",
            confidence=SourceConfidence.VERY_HIGH,
        )
        self.email = email
        self.timeout = timeout
        self._session: httpx.AsyncClient | None = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None:
            headers = {"User-Agent": "ReflInt/1.0 (https://github.com/reflint/reflint)"}
            if self.email:
                headers["User-Agent"] += f" (mailto:{self.email})"

            self._session = httpx.AsyncClient(
                headers=headers, timeout=self.timeout, follow_redirects=True
            )
        return self._session

    async def lookup_by_doi(self, doi: str) -> LookupResult:
        """Look up entry by DOI."""
        start_time = time.time()
        session = await self._get_session()

        # Clean DOI
        clean_doi = (
            doi.strip()
            .replace("https://doi.org/", "")
            .replace("http://dx.doi.org/", "")
        )
        url = f"{self.base_url}/works/{quote(clean_doi)}"

        try:
            response = await session.get(url)
            lookup_time = time.time() - start_time

            if response.status_code == 404:
                return LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=lookup_time,
                        confidence=self.confidence,
                        api_response_size=len(response.content),
                        error="DOI not found",
                    ),
                )

            response.raise_for_status()
            data = response.json()

            # Extract work data
            work = data.get("message", {})
            entry = self._convert_to_bibtex(work, clean_doi)

            return LookupResult(
                entry=entry,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=lookup_time,
                    confidence=self.confidence,
                    api_response_size=len(response.content),
                ),
                raw_data=work,
            )

        except httpx.HTTPStatusError as e:
            lookup_time = time.time() - start_time
            if e.response.status_code == 429:
                logger.warning("CrossRef rate limit exceeded")
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
            else:
                raise DataSourceError(f"CrossRef API error: {e}")

        except Exception as e:
            lookup_time = time.time() - start_time
            raise DataSourceError(f"CrossRef lookup failed: {e}")

    async def lookup_by_title_author(
        self, title: str, author: str
    ) -> list[LookupResult]:
        """Look up entries by title and author."""
        start_time = time.time()
        session = await self._get_session()

        # Build query
        query_parts = []
        if title:
            query_parts.append(f'title:"{title.strip()}"')
        if author:
            query_parts.append(f'author:"{author.strip()}"')

        query = " AND ".join(query_parts)
        url = f"{self.base_url}/works"
        params = {
            "query": query,
            "rows": "5",  # Limit results
            "sort": "relevance",
        }

        try:
            response = await session.get(url, params=params)
            lookup_time = time.time() - start_time
            response.raise_for_status()

            data = response.json()
            items = data.get("message", {}).get("items", [])

            results = []
            for item in items:
                doi = item.get("DOI", "")
                entry = self._convert_to_bibtex(item, doi)
                if entry:
                    results.append(
                        LookupResult(
                            entry=entry,
                            metadata=SourceMetadata(
                                source_name=self.name,
                                lookup_time=lookup_time / len(items),  # Distribute time
                                confidence=self.confidence
                                * 0.9,  # Slightly lower for search
                                api_response_size=len(response.content) // len(items),
                            ),
                            raw_data=item,
                        )
                    )

            return results

        except Exception as e:
            raise DataSourceError(f"CrossRef title/author search failed: {e}")

    def _convert_to_bibtex(self, work: dict, doi: str) -> BibTeXEntry | None:
        """Convert CrossRef work data to BibTeX entry."""
        if not work:
            return None

        # Determine entry type
        entry_type = self._determine_entry_type(work)

        # Create entry dict
        entry_data = {"ID": self._generate_key(work), "ENTRYTYPE": entry_type}

        # Add DOI
        if doi:
            entry_data["doi"] = doi

        # Add title
        title = self._extract_title(work)
        if title:
            entry_data["title"] = title

        # Add authors
        authors = self._extract_authors(work)
        if authors:
            entry_data["author"] = authors

        # Add journal/venue
        venue = self._extract_venue(work, entry_type)
        if venue:
            if entry_type == "article":
                entry_data["journal"] = venue
            elif entry_type == "inproceedings":
                entry_data["booktitle"] = venue
            elif entry_type == "book":
                entry_data["publisher"] = venue

        # Add year
        year = self._extract_year(work)
        if year:
            entry_data["year"] = year

        # Add volume/number/pages
        volume = work.get("volume")
        if volume:
            entry_data["volume"] = volume

        issue = work.get("issue")
        if issue:
            entry_data["number"] = issue

        pages = self._extract_pages(work)
        if pages:
            entry_data["pages"] = pages

        # Add publisher
        publisher = self._extract_publisher(work)
        if publisher and entry_type in ["book", "inbook", "incollection"]:
            entry_data["publisher"] = publisher

        # Add ISSN
        issn = self._extract_issn(work)
        if issn:
            entry_data["issn"] = issn

        # Add URL (canonical DOI URL)
        if doi:
            entry_data["url"] = f"https://doi.org/{doi}"

        return BibTeXEntry(entry_data)

    def _determine_entry_type(self, work: dict) -> str:
        """Determine BibTeX entry type from CrossRef data."""
        type_mapping = {
            "journal-article": "article",
            "book-chapter": "inbook",
            "book": "book",
            "proceedings-article": "inproceedings",
            "dissertation": "phdthesis",
            "report": "techreport",
            "reference-entry": "inbook",
            "monograph": "book",
        }

        crossref_type = work.get("type", "")
        return type_mapping.get(crossref_type, "misc")

    def _extract_title(self, work: dict) -> str | None:
        """Extract title from CrossRef data."""
        titles = work.get("title", [])
        if titles and isinstance(titles, list) and len(titles) > 0:
            return titles[0]
        return None

    def _extract_authors(self, work: dict) -> str | None:
        """Extract authors from CrossRef data."""
        authors = work.get("author", [])
        if not authors:
            return None

        author_strings = []
        for author in authors:
            given = author.get("given", "")
            family = author.get("family", "")

            if family:
                if given:
                    author_strings.append(f"{given} {family}")
                else:
                    author_strings.append(family)

        return " and ".join(author_strings) if author_strings else None

    def _extract_venue(self, work: dict, entry_type: str) -> str | None:
        """Extract venue information."""
        container_title = work.get("container-title", [])
        if (
            container_title
            and isinstance(container_title, list)
            and len(container_title) > 0
        ):
            return container_title[0]

        # Fallback to publisher for books
        if entry_type in ["book", "inbook"]:
            publisher = work.get("publisher")
            if publisher:
                return publisher

        return None

    def _extract_year(self, work: dict) -> str | None:
        """Extract publication year."""
        # Try published date first
        published = work.get("published", {})
        if published:
            date_parts = published.get("date-parts", [])
            if date_parts and len(date_parts) > 0 and len(date_parts[0]) > 0:
                return str(date_parts[0][0])

        # Try created date
        created = work.get("created", {})
        if created:
            date_parts = created.get("date-parts", [])
            if date_parts and len(date_parts) > 0 and len(date_parts[0]) > 0:
                return str(date_parts[0][0])

        return None

    def _extract_pages(self, work: dict) -> str | None:
        """Extract page information."""
        page = work.get("page")
        if page:
            # Convert hyphens to en-dashes
            return page.replace("-", "--")
        return None

    def _extract_publisher(self, work: dict) -> str | None:
        """Extract publisher information."""
        return work.get("publisher")

    def _extract_issn(self, work: dict) -> str | None:
        """Extract ISSN."""
        issns = work.get("ISSN", [])
        if issns and isinstance(issns, list) and len(issns) > 0:
            return issns[0]
        return None

    def _generate_key(self, work: dict) -> str:
        """Generate BibTeX key from work data."""
        # Get first author's last name
        authors = work.get("author", [])
        author_key = ""
        if authors and len(authors) > 0:
            family = authors[0].get("family", "")
            if family:
                author_key = family.replace(" ", "").lower()

        if not author_key:
            author_key = "unknown"

        # Get year
        year = self._extract_year(work)
        year_key = year if year else "unknown"

        # Get first word of title
        title = self._extract_title(work)
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
        return identifier_type == "doi"

    def get_supported_identifiers(self) -> list[str]:
        """Get list of supported identifier types."""
        return ["doi"]

    def get_reliability_score(self, field_name: str) -> float:
        """Get reliability score for a specific field."""
        # CrossRef is very reliable for most fields
        field_reliability = {
            "doi": 0.99,
            "title": 0.95,
            "author": 0.90,
            "journal": 0.95,
            "year": 0.95,
            "volume": 0.90,
            "number": 0.90,
            "pages": 0.85,
            "publisher": 0.90,
            "issn": 0.95,
        }

        return field_reliability.get(field_name, self.confidence)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.aclose()
            self._session = None
