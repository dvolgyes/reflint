"""OpenAlex API integration for comprehensive academic metadata.

This module provides integration with the OpenAlex API for fetching metadata
about academic publications from a comprehensive open database.
"""

import re
import time
from typing import Any
from urllib.parse import quote

import httpx
from loguru import logger

from ..utils.cached_http import cached_httpx_get
from .base import (
    BaseDataSource,
    LookupResult,
    SourceMetadata,
    SourceConfidence,
)
from ..core.entry import BibTeXEntry


class OpenAlexSource(BaseDataSource):
    """Source for OpenAlex academic metadata."""

    def __init__(self, email: str | None = None) -> None:
        """Initialize OpenAlex source.

        Args:
            email: Email for polite crawling identification (recommended for better performance)
        """
        super().__init__(
            name="openalex",
            base_url="https://api.openalex.org",
            confidence=SourceConfidence.HIGH,  # Comprehensive open database
        )
        self.email = email

        # OpenAlex rate limit: 100,000 requests per day, recommend 10 requests/second
        self.rate_limit = 10
        self.last_request_time = 0.0

    async def lookup_by_doi(self, doi: str) -> LookupResult:
        """Look up entry by DOI."""
        start_time = time.time()

        # Clean DOI
        clean_doi = self._clean_doi(doi)
        if not clean_doi:
            return LookupResult(
                entry=None,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=time.time() - start_time,
                    confidence=self.confidence,
                    error=f"Invalid DOI format: {doi}",
                ),
            )

        logger.debug(f"Looking up DOI: {clean_doi}")

        try:
            headers = {"User-Agent": "ReflInt/1.0 (OpenAlex integration)"}
            if self.email:
                headers["User-Agent"] += f" (mailto:{self.email})"

            # Search by DOI
            url = f"{self.base_url}/works"
            params = {"filter": f"doi:{clean_doi}", "per-page": 1}

            response = await cached_httpx_get(
                url=url,
                params=params,
                headers=headers,
                timeout=30.0,
                rate_limit_func=self._rate_limit
            )
            response.raise_for_status()

            data = response.json()
            works = data.get("results", [])

            if not works:
                return LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        error=f"No OpenAlex entry found for DOI: {clean_doi}",
                    ),
                )

            entry = self._parse_work(works[0])

            return LookupResult(
                    entry=entry,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        api_response_size=len(response.text),
                    ),
                    raw_data={"response_json": data},
                )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching DOI {clean_doi}: {e}")
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
            logger.error(f"Error fetching DOI {clean_doi}: {e}")
            return LookupResult(
                entry=None,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=time.time() - start_time,
                    confidence=self.confidence,
                    error=f"Unexpected error: {e}",
                ),
            )

    async def lookup_by_title_author(
        self, title: str, author: str
    ) -> list[LookupResult]:
        """Look up entries by title and author."""
        start_time = time.time()

        # Build search query
        filters = []
        if title:
            # Use title search
            filters.append(f"title.search:{quote(title)}")
        if author:
            # Use author search
            filters.append(f"author.search:{quote(author)}")

        if not filters:
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

        try:
            headers = {"User-Agent": "ReflInt/1.0 (OpenAlex integration)"}
            if self.email:
                headers["User-Agent"] += f" (mailto:{self.email})"

            url = f"{self.base_url}/works"
            params = {
                "filter": ",".join(filters),
                "per-page": 5,
                "sort": "relevance_score:desc",
            }

            response = await cached_httpx_get(
                url=url,
                params=params,
                headers=headers,
                timeout=30.0,
                rate_limit_func=self._rate_limit
            )
            response.raise_for_status()

            data = response.json()
            works = data.get("results", [])

            if not works:
                return [
                    LookupResult(
                        entry=None,
                        metadata=SourceMetadata(
                            source_name=self.name,
                            lookup_time=time.time() - start_time,
                            confidence=self.confidence,
                            error="No matching entries found",
                        ),
                    )
                ]

            results = []
            for work in works:
                entry = self._parse_work(work)
                if entry:
                    results.append(
                            LookupResult(
                                entry=entry,
                                metadata=SourceMetadata(
                                    source_name=self.name,
                                    lookup_time=time.time() - start_time,
                                    confidence=self.confidence,
                                    api_response_size=len(response.text),
                                ),
                                raw_data={"work_data": work},
                            )
                        )

            return results

        except httpx.HTTPError as e:
            logger.error(f"HTTP error searching OpenAlex: {e}")
            return [
                LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        error=f"HTTP error: {e}",
                    ),
                )
            ]
        except Exception as e:
            logger.error(f"Error searching OpenAlex: {e}")
            return [
                LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        error=f"Unexpected error: {e}",
                    ),
                )
            ]

    def can_lookup_identifier(self, identifier_type: str) -> bool:
        """Check if this source can look up a specific identifier type."""
        return identifier_type.lower() in ["doi", "pmid"]

    async def lookup_by_pmid(self, pmid: str) -> LookupResult:
        """Look up entry by PubMed ID."""
        start_time = time.time()

        # Clean PMID
        clean_pmid = self._clean_pmid(pmid)
        if not clean_pmid:
            return LookupResult(
                entry=None,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=time.time() - start_time,
                    confidence=self.confidence,
                    error=f"Invalid PMID format: {pmid}",
                ),
            )

        logger.debug(f"Looking up PMID: {clean_pmid}")

        try:
            headers = {"User-Agent": "ReflInt/1.0 (OpenAlex integration)"}
            if self.email:
                headers["User-Agent"] += f" (mailto:{self.email})"

            # Search by PMID
            url = f"{self.base_url}/works"
            params = {"filter": f"ids.pmid:{clean_pmid}", "per-page": 1}

            response = await cached_httpx_get(
                url=url,
                params=params,
                headers=headers,
                timeout=30.0,
                rate_limit_func=self._rate_limit
            )
            response.raise_for_status()

            data = response.json()
            works = data.get("results", [])

            if not works:
                return LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        error=f"No OpenAlex entry found for PMID: {clean_pmid}",
                    ),
                )

            entry = self._parse_work(works[0])

            return LookupResult(
                    entry=entry,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        api_response_size=len(response.text),
                    ),
                    raw_data={"response_json": data},
                )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching PMID {clean_pmid}: {e}")
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
            logger.error(f"Error fetching PMID {clean_pmid}: {e}")
            return LookupResult(
                entry=None,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=time.time() - start_time,
                    confidence=self.confidence,
                    error=f"Unexpected error: {e}",
                ),
            )

    async def lookup_journal_issn(self, journal_name: str) -> dict[str, str] | None:
        """Look up ISSN information for a journal by name.
        
        Args:
            journal_name: Name of the journal to search for
            
        Returns:
            Dictionary with ISSN information or None if not found
            Format: {"issn_l": "xxxx-xxxx", "issn": ["xxxx-xxxx", "yyyy-yyyy"], "display_name": "Journal Name"}
        """
        start_time = time.time()
        
        if not journal_name or not journal_name.strip():
            logger.debug("Empty journal name provided")
            return None
            
        journal_name = journal_name.strip()
        logger.debug(f"Looking up ISSN for journal: {journal_name}")

        try:
            headers = {"User-Agent": "ReflInt/1.0 (OpenAlex integration)"}
            if self.email:
                headers["User-Agent"] += f" (mailto:{self.email})"

            # Use autocomplete endpoint first (faster and more accurate for name matching)
            autocomplete_url = f"{self.base_url}/autocomplete/sources"
            params = {"q": journal_name}

            response = await cached_httpx_get(
                url=autocomplete_url,
                params=params,
                headers=headers,
                timeout=30.0,
                rate_limit_func=self._rate_limit
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            
            if results:
                # Take the first (most relevant) result
                source = results[0]
                
                # Extract ISSN information
                issn_info = {
                    "display_name": source.get("display_name", ""),
                    "issn_l": source.get("external_id"),  # This is ISSN-L in autocomplete
                    "issn": [],
                    "openalex_id": source.get("id", "")
                }
                
                # If we have an OpenAlex ID, get full source details for complete ISSN array
                if issn_info["openalex_id"]:
                    source_id = issn_info["openalex_id"].split("/")[-1]  # Extract ID from URL
                    full_source = await self._get_full_source_details(source_id)
                    if full_source:
                        issn_info["issn"] = full_source.get("issn", [])
                        if not issn_info["issn_l"]:
                            issn_info["issn_l"] = full_source.get("issn_l")
                
                logger.debug(f"Found ISSN info for '{journal_name}': {issn_info}")
                return issn_info
            
            # Fallback to search endpoint if autocomplete doesn't find anything
            search_url = f"{self.base_url}/sources"
            params = {"search": journal_name, "per-page": 5}
            
            response = await cached_httpx_get(
                url=search_url,
                params=params,
                headers=headers,
                timeout=30.0,
                rate_limit_func=self._rate_limit
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            
            if results:
                # Take the first (most relevant) result
                source = results[0]
                issn_info = {
                    "display_name": source.get("display_name", ""),
                    "issn_l": source.get("issn_l"),
                    "issn": source.get("issn", []),
                    "openalex_id": source.get("id", "")
                }
                
                logger.debug(f"Found ISSN info via search for '{journal_name}': {issn_info}")
                return issn_info
            
            logger.debug(f"No ISSN found for journal: {journal_name}")
            return None

        except httpx.HTTPError as e:
            logger.error(f"HTTP error looking up journal '{journal_name}': {e}")
            return None
        except Exception as e:
            logger.error(f"Error looking up journal '{journal_name}': {e}")
            return None

    async def _get_full_source_details(self, source_id: str) -> dict | None:
        """Get full source details by OpenAlex ID."""
        try:
            headers = {"User-Agent": "ReflInt/1.0 (OpenAlex integration)"}
            if self.email:
                headers["User-Agent"] += f" (mailto:{self.email})"

            url = f"{self.base_url}/sources/{source_id}"
            
            response = await cached_httpx_get(
                url=url,
                headers=headers,
                timeout=30.0,
                rate_limit_func=self._rate_limit
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.debug(f"Error getting full source details for {source_id}: {e}")
            return None

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self.last_request_time > 0:
            time_since_last = time.time() - self.last_request_time
            min_interval = 1.0 / self.rate_limit

            if time_since_last < min_interval:
                import asyncio

                sleep_time = min_interval - time_since_last
                await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    def _clean_doi(self, doi: str) -> str | None:
        """Clean and validate DOI."""
        # Remove common prefixes
        doi = re.sub(
            r"^(doi:|DOI:|https?://doi\.org/|https?://dx\.doi\.org/)",
            "",
            doi,
            flags=re.IGNORECASE,
        )

        # Basic DOI format validation
        if re.match(r"^10\.\d{4,}/\S+$", doi):
            return doi

        return None

    def _clean_pmid(self, pmid: str) -> str | None:
        """Clean and validate PMID."""
        # Remove common prefixes
        pmid = re.sub(r"^(pmid:|PMID:)", "", pmid, flags=re.IGNORECASE)

        # Check if it's a valid number
        if re.match(r"^\d+$", pmid.strip()):
            return pmid.strip()

        return None

    def _parse_work(self, work: dict) -> BibTeXEntry | None:
        """Parse OpenAlex work data to BibTeX entry."""
        try:
            # Extract basic metadata
            title = work.get("title", "")
            if not title:
                return None

            # Authors
            authors = self._extract_authors(work)

            # Publication info
            publication_info = self._extract_publication_info(work)

            # Publication date
            pub_date = self._extract_publication_date(work)

            # Abstract (inverted abstract format)
            abstract = self._extract_abstract(work)

            # Identifiers
            identifiers = self._extract_identifiers(work)

            # Topics/keywords
            topics = self._extract_topics(work)

            # Determine entry type
            entry_type = self._determine_entry_type(work)

            # Build BibTeX entry
            entry_data = {
                "ID": self._generate_entry_key(authors, pub_date.get("year"), title),
                "ENTRYTYPE": entry_type,
                "title": self._clean_title(title),
                "author": self._format_authors(authors),
            }

            # Add publication information
            if publication_info.get("venue"):
                if entry_type == "article":
                    entry_data["journal"] = publication_info["venue"]
                elif entry_type == "inproceedings":
                    entry_data["booktitle"] = publication_info["venue"]
                else:
                    entry_data["journal"] = publication_info["venue"]

            if publication_info.get("publisher"):
                entry_data["publisher"] = publication_info["publisher"]
            if publication_info.get("volume"):
                entry_data["volume"] = publication_info["volume"]
            if publication_info.get("issue"):
                entry_data["number"] = publication_info["issue"]
            if publication_info.get("pages"):
                entry_data["pages"] = publication_info["pages"]
            if publication_info.get("issn"):
                entry_data["issn"] = publication_info["issn"]

            # Add publication date
            if pub_date.get("year"):
                entry_data["year"] = str(pub_date["year"])
            if pub_date.get("month"):
                entry_data["month"] = str(pub_date["month"])

            # Add optional fields
            if abstract:
                entry_data["abstract"] = abstract
            if identifiers.get("doi"):
                entry_data["doi"] = identifiers["doi"]
            if identifiers.get("pmid"):
                entry_data["pmid"] = identifiers["pmid"]
            if topics:
                entry_data["keywords"] = "; ".join(topics[:8])  # Limit to 8 topics

            # Add citation count if available
            cited_by_count = work.get("cited_by_count")
            if cited_by_count and cited_by_count > 0:
                entry_data["note"] = f"Cited by {cited_by_count} papers"

            # Add OpenAlex URL
            openalex_id = work.get("id", "").replace("https://openalex.org/", "")
            if openalex_id:
                entry_data["url"] = f"https://openalex.org/{openalex_id}"

            return BibTeXEntry(entry_data)

        except Exception as e:
            logger.error(f"Error parsing OpenAlex work: {e}")
            return None

    def _safe_get(self, obj, key: str, default=None):
        """Safely get a value from an object that might be a dict or string."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default

    def _extract_authors(self, work: dict) -> list[str]:
        """Extract author list from work."""
        authors = []
        authorships = work.get("authorships", [])

        for authorship in authorships:
            author = self._safe_get(authorship, "author", {})
            display_name = self._safe_get(author, "display_name")

            if display_name:
                authors.append(display_name.strip())

        return authors

    def _extract_publication_info(self, work: dict) -> dict[str, str]:
        """Extract publication venue information."""
        pub_info = {}

        # Primary location (journal/venue)
        primary_location = work.get("primary_location", {})
        if primary_location:
            source = self._safe_get(primary_location, "source", {})
            if source:
                display_name = self._safe_get(source, "display_name")
                if display_name:
                    pub_info["venue"] = display_name

                issn_l = self._safe_get(source, "issn_l")
                if issn_l:
                    pub_info["issn"] = issn_l

                # Publisher
                host_org = self._safe_get(source, "host_organization")
                if host_org:
                    pub_info["publisher"] = self._safe_get(host_org, "display_name", "")

        # Biblio information
        biblio = work.get("biblio", {})
        if biblio:
            volume = self._safe_get(biblio, "volume")
            if volume:
                pub_info["volume"] = volume

            issue = self._safe_get(biblio, "issue")
            if issue:
                pub_info["issue"] = issue

            first_page = self._safe_get(biblio, "first_page")
            last_page = self._safe_get(biblio, "last_page")
            if first_page and last_page:
                pub_info["pages"] = f"{first_page}--{last_page}"
            elif first_page:
                pub_info["pages"] = first_page

        return pub_info

    def _extract_publication_date(self, work: dict) -> dict[str, int]:
        """Extract publication date."""
        pub_date = {}

        publication_date = work.get("publication_date")
        if publication_date:
            try:
                # Parse ISO date format (YYYY-MM-DD)
                parts = publication_date.split("-")
                if len(parts) >= 1:
                    pub_date["year"] = int(parts[0])
                if len(parts) >= 2:
                    pub_date["month"] = int(parts[1])
            except (ValueError, TypeError):
                pass

        # Fallback to publication year
        if not pub_date.get("year"):
            publication_year = work.get("publication_year")
            if publication_year:
                pub_date["year"] = publication_year

        return pub_date

    def _extract_abstract(self, work: dict) -> str:
        """Extract abstract from inverted abstract format."""
        abstract_inverted_index = work.get("abstract_inverted_index")
        if not abstract_inverted_index:
            return ""

        try:
            # Reconstruct abstract from inverted index
            word_positions = []
            for word, positions in abstract_inverted_index.items():
                for pos in positions:
                    word_positions.append((pos, word))

            # Sort by position and join
            word_positions.sort(key=lambda x: x[0])
            abstract = " ".join([word for _, word in word_positions])

            return abstract.strip()

        except Exception as e:
            logger.warning(f"Error reconstructing abstract: {e}")
            return ""

    def _extract_identifiers(self, work: dict) -> dict[str, str]:
        """Extract DOI, PMID, and other identifiers."""
        identifiers = {}

        # DOI
        doi = work.get("doi")
        if doi:
            # Remove URL prefix if present
            doi = doi.replace("https://doi.org/", "")
            identifiers["doi"] = doi

        # IDs section
        ids = work.get("ids", {})
        if ids:
            pmid = self._safe_get(ids, "pmid")
            if pmid:
                # Extract PMID number from URL
                pmid = pmid.replace("https://pubmed.ncbi.nlm.nih.gov/", "").rstrip("/")
                identifiers["pmid"] = pmid

        return identifiers

    def _extract_topics(self, work: dict) -> list[str]:
        """Extract research topics/keywords."""
        topics = []

        # Primary topic
        primary_topic = work.get("primary_topic")
        if primary_topic:
            display_name = self._safe_get(primary_topic, "display_name")
            if display_name:
                topics.append(display_name)

        # Additional topics
        work_topics = work.get("topics", [])
        for topic in work_topics:
            display_name = self._safe_get(topic, "display_name")
            if display_name and display_name not in topics:
                topics.append(display_name)

        return topics

    def _determine_entry_type(self, work: dict) -> str:
        """Determine appropriate BibTeX entry type."""
        work_type = work.get("type", "").lower()

        # Map OpenAlex types to BibTeX types
        type_mapping = {
            "journal-article": "article",
            "proceedings-article": "inproceedings",
            "book-chapter": "incollection",
            "book": "book",
            "dataset": "misc",
            "dissertation": "phdthesis",
            "preprint": "article",
            "report": "techreport",
            "review": "article",
            "letter": "article",
            "editorial": "article",
        }

        return type_mapping.get(work_type, "article")

    def _clean_title(self, title: str) -> str:
        """Clean and format title."""
        if not title:
            return ""

        # Remove extra whitespace
        title = re.sub(r"\s+", " ", title.strip())

        return title

    def _format_authors(self, authors: list[str]) -> str:
        """Format author list for BibTeX."""
        if not authors:
            return ""

        return " and ".join(authors)

    def _generate_entry_key(
        self, authors: list[str], year: int | None, title: str
    ) -> str:
        """Generate BibTeX entry key."""
        # Use first author's last name
        author_key = "openalex"
        if authors:
            first_author = authors[0]
            # Extract last name (last word)
            parts = first_author.split()
            if parts:
                last_name = parts[-1]
                # Clean last name
                author_key = re.sub(r"[^a-zA-Z0-9]", "", last_name.lower())

        year_key = str(year) if year else "unknown"

        # Add a short title word if possible
        title_words = re.findall(r"\b[a-zA-Z]{4,}\b", title.lower())
        title_key = title_words[0] if title_words else "work"

        return f"{author_key}{year_key}{title_key}"

    def get_supported_identifiers(self) -> list[str]:
        """Get list of supported identifier types."""
        return ["doi", "pmid"]

    def get_source_info(self) -> dict[str, Any]:
        """Get information about this source."""
        return {
            "name": self.name,
            "description": "OpenAlex comprehensive open academic database",
            "confidence": self.confidence,
            "supported_identifiers": self.get_supported_identifiers(),
            "rate_limit": f"{self.rate_limit} requests/second (100,000/day)",
            "coverage": "All academic disciplines with institutional and funding data",
            "url": "https://openalex.org",
        }
