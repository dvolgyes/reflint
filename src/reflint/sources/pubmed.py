"""PubMed/NCBI E-utilities API integration for medical literature metadata.

This module provides integration with the PubMed E-utilities API for fetching metadata
about medical and biomedical literature.
"""

import asyncio
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


class PubMedSource(BaseDataSource):
    """Source for PubMed medical literature metadata."""

    def __init__(self, email: str | None = None, api_key: str | None = None) -> None:
        """Initialize PubMed source.

        Args:
            email: Email for polite crawling identification (recommended)
            api_key: Optional API key for higher rate limits
        """
        super().__init__(
            name="pubmed",
            base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
            confidence=SourceConfidence.VERY_HIGH,  # Authoritative medical source
        )
        self.email = email
        self.api_key = api_key

        # Rate limiting: 3 requests/second without API key, 10/second with key
        self.rate_limit = 10 if api_key else 3
        self.last_request_time = 0.0

    async def lookup_by_doi(self, doi: str) -> LookupResult:
        """Look up entry by DOI using PubMed."""
        start_time = time.time()

        # PubMed doesn't directly support DOI lookup, but we can search
        search_query = f'"{doi}"[AID]'

        try:
            # First, search for the DOI
            pmids = await self._search_pubmed(search_query, max_results=1)

            if not pmids:
                return LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        error=f"No PubMed entry found for DOI: {doi}",
                    ),
                )

            # Fetch details for the found PMID
            return await self.lookup_by_pmid(pmids[0])

        except Exception as e:
            logger.error(f"Error looking up DOI {doi} in PubMed: {e}")
            return LookupResult(
                entry=None,
                metadata=SourceMetadata(
                    source_name=self.name,
                    lookup_time=time.time() - start_time,
                    confidence=self.confidence,
                    error=f"Error during DOI lookup: {e}",
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
            # Use title field search
            query_parts.append(f'"{title}"[Title]')
        if author:
            # Use author field search
            query_parts.append(f'"{author}"[Author]')

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

        search_query = " AND ".join(query_parts)

        try:
            # Search PubMed
            pmids = await self._search_pubmed(search_query, max_results=5)

            if not pmids:
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

            # Fetch details for found PMIDs
            results = []
            for pmid in pmids:
                result = await self.lookup_by_pmid(pmid)
                if result.entry:
                    results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error searching PubMed: {e}")
            return [
                LookupResult(
                    entry=None,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        error=f"Search error: {e}",
                    ),
                )
            ]

    def can_lookup_identifier(self, identifier_type: str) -> bool:
        """Check if this source can look up a specific identifier type."""
        return identifier_type.lower() in ["pmid", "doi"]

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
            await self._rate_limit()

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Use EFetch to get detailed article information
                params = {
                    "db": "pubmed",
                    "id": clean_pmid,
                    "rettype": "abstract",
                    "retmode": "xml",
                }

                if self.email:
                    params["email"] = self.email
                if self.api_key:
                    params["api_key"] = self.api_key

                headers = {"User-Agent": "ReflInt/1.0 (PubMed integration)"}

                response = await client.get(
                    f"{self.base_url}/efetch.fcgi", params=params, headers=headers
                )
                response.raise_for_status()

                entry = self._parse_pubmed_xml(response.text, clean_pmid)

                return LookupResult(
                    entry=entry,
                    metadata=SourceMetadata(
                        source_name=self.name,
                        lookup_time=time.time() - start_time,
                        confidence=self.confidence,
                        api_response_size=len(response.text),
                    ),
                    raw_data={"response_xml": response.text},
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

    async def _search_pubmed(self, query: str, max_results: int = 10) -> list[str]:
        """Search PubMed and return list of PMIDs."""
        await self._rate_limit()

        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "rettype": "uilist",
                "retmode": "xml",
            }

            if self.email:
                params["email"] = self.email
            if self.api_key:
                params["api_key"] = self.api_key

            headers = {"User-Agent": "ReflInt/1.0 (PubMed integration)"}

            response = await client.get(
                f"{self.base_url}/esearch.fcgi", params=params, headers=headers
            )
            response.raise_for_status()

            return self._parse_search_results(response.text)

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self.last_request_time > 0:
            time_since_last = time.time() - self.last_request_time
            min_interval = 1.0 / self.rate_limit

            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    def _clean_pmid(self, pmid: str) -> str | None:
        """Clean and validate PMID."""
        # Remove common prefixes
        pmid = re.sub(r"^(pmid:|PMID:)", "", pmid, flags=re.IGNORECASE)

        # Check if it's a valid number
        if re.match(r"^\d+$", pmid.strip()):
            return pmid.strip()

        return None

    def _parse_search_results(self, xml_content: str) -> list[str]:
        """Parse search results XML to extract PMIDs."""
        try:
            root = ET.fromstring(xml_content)
            pmids = []

            for id_elem in root.findall(".//Id"):
                if id_elem.text:
                    pmids.append(id_elem.text.strip())

            return pmids

        except ET.ParseError as e:
            logger.error(f"Error parsing PubMed search results: {e}")
            return []

    def _parse_pubmed_xml(self, xml_content: str, pmid: str) -> BibTeXEntry | None:
        """Parse PubMed XML response to extract metadata."""
        try:
            root = ET.fromstring(xml_content)
            articles = root.findall(".//PubmedArticle")

            if not articles:
                logger.debug(f"No article found for PMID: {pmid}")
                return None

            # Process the first article
            article = articles[0]
            return self._extract_article_metadata(article, pmid)

        except ET.ParseError as e:
            logger.error(f"Error parsing PubMed XML: {e}")
            return None

    def _extract_article_metadata(
        self, article: ET.Element, pmid: str
    ) -> BibTeXEntry | None:
        """Extract metadata from a PubmedArticle element."""
        try:
            # Extract basic information
            medline_citation = article.find(".//MedlineCitation")
            if medline_citation is None:
                return None

            # Article details
            article_elem = medline_citation.find(".//Article")
            if article_elem is None:
                return None

            # Title
            title_elem = article_elem.find(".//ArticleTitle")
            title = (
                title_elem.text.strip()
                if title_elem is not None and title_elem.text
                else ""
            )

            # Authors
            authors = self._extract_authors(article_elem)

            # Journal information
            journal_info = self._extract_journal_info(article_elem)

            # Publication date
            pub_date = self._extract_publication_date(article_elem)

            # Abstract
            abstract = self._extract_abstract(article_elem)

            # DOI and other identifiers
            identifiers = self._extract_identifiers(article_elem)

            # MeSH terms
            mesh_terms = self._extract_mesh_terms(medline_citation)

            # Build BibTeX entry
            entry_data = {
                "ID": self._generate_entry_key(authors, pub_date.get("year"), title),
                "ENTRYTYPE": "article",
                "title": self._clean_title(title),
                "author": self._format_authors(authors),
                "pmid": pmid,
            }

            # Add journal information
            if journal_info.get("title"):
                entry_data["journal"] = journal_info["title"]
            if journal_info.get("volume"):
                entry_data["volume"] = journal_info["volume"]
            if journal_info.get("issue"):
                entry_data["number"] = journal_info["issue"]
            if journal_info.get("pages"):
                entry_data["pages"] = journal_info["pages"]
            if journal_info.get("issn"):
                entry_data["issn"] = journal_info["issn"]

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
            if identifiers.get("pmc"):
                entry_data["pmc"] = identifiers["pmc"]
            if mesh_terms:
                entry_data["keywords"] = "; ".join(mesh_terms[:10])  # Limit to 10 terms

            # Add PubMed URL
            entry_data["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            return BibTeXEntry(entry_data)

        except Exception as e:
            logger.error(f"Error extracting article metadata: {e}")
            return None

    def _extract_authors(self, article: ET.Element) -> list[str]:
        """Extract author list from article."""
        authors = []
        author_list = article.find(".//AuthorList")

        if author_list is not None:
            for author in author_list.findall(".//Author"):
                last_name = author.find(".//LastName")
                first_name = author.find(".//ForeName")
                initials = author.find(".//Initials")

                if last_name is not None and last_name.text:
                    author_name = last_name.text.strip()

                    # Add first name or initials
                    if first_name is not None and first_name.text:
                        author_name += f", {first_name.text.strip()}"
                    elif initials is not None and initials.text:
                        author_name += f", {initials.text.strip()}"

                    authors.append(author_name)

        return authors

    def _extract_journal_info(self, article: ET.Element) -> dict[str, str]:
        """Extract journal information."""
        journal_info = {}
        journal = article.find(".//Journal")

        if journal is not None:
            # Journal title
            title_elem = journal.find(".//Title")
            if title_elem is not None and title_elem.text:
                journal_info["title"] = title_elem.text.strip()

            # ISSN
            issn_elem = journal.find(".//ISSN")
            if issn_elem is not None and issn_elem.text:
                journal_info["issn"] = issn_elem.text.strip()

            # Volume, issue, pages
            journal_issue = journal.find(".//JournalIssue")
            if journal_issue is not None:
                volume_elem = journal_issue.find(".//Volume")
                if volume_elem is not None and volume_elem.text:
                    journal_info["volume"] = volume_elem.text.strip()

                issue_elem = journal_issue.find(".//Issue")
                if issue_elem is not None and issue_elem.text:
                    journal_info["issue"] = issue_elem.text.strip()

        # Pagination
        pagination = article.find(".//Pagination")
        if pagination is not None:
            medline_pgn = pagination.find(".//MedlinePgn")
            if medline_pgn is not None and medline_pgn.text:
                journal_info["pages"] = medline_pgn.text.strip()

        return journal_info

    def _extract_publication_date(self, article: ET.Element) -> dict[str, int]:
        """Extract publication date."""
        pub_date = {}

        # Try ArticleDate first (electronic publication)
        article_date = article.find(".//ArticleDate")
        if article_date is None:
            # Fall back to Journal issue date
            journal_issue = article.find(".//JournalIssue")
            if journal_issue is not None:
                article_date = journal_issue.find(".//PubDate")

        if article_date is not None:
            year_elem = article_date.find(".//Year")
            if year_elem is not None and year_elem.text:
                year_text = year_elem.text.strip()
                if year_text.isdigit():
                    pub_date["year"] = int(year_elem.text.strip())

            month_elem = article_date.find(".//Month")
            if month_elem is not None and month_elem.text:
                month_text = month_elem.text.strip()
                month_num = self._month_name_to_number(month_text)
                if month_num:
                    pub_date["month"] = month_num

        return pub_date

    def _extract_abstract(self, article: ET.Element) -> str:
        """Extract abstract text."""
        abstract_elem = article.find(".//Abstract")
        if abstract_elem is None:
            return ""

        # Collect all abstract text elements
        abstract_parts = []
        for abstract_text in abstract_elem.findall(".//AbstractText"):
            if abstract_text.text:
                abstract_parts.append(abstract_text.text.strip())

        return " ".join(abstract_parts)

    def _extract_identifiers(self, article: ET.Element) -> dict[str, str]:
        """Extract DOI, PMC, and other identifiers."""
        identifiers = {}

        # Look for ArticleIdList
        id_list = article.find(".//ArticleIdList")
        if id_list is not None:
            for article_id in id_list.findall(".//ArticleId"):
                id_type = article_id.get("IdType", "").lower()
                id_value = article_id.text

                if id_value and id_type in ["doi", "pmc"]:
                    identifiers[id_type] = id_value.strip()

        return identifiers

    def _extract_mesh_terms(self, medline_citation: ET.Element) -> list[str]:
        """Extract MeSH (Medical Subject Headings) terms."""
        mesh_terms = []
        mesh_heading_list = medline_citation.find(".//MeshHeadingList")

        if mesh_heading_list is not None:
            for mesh_heading in mesh_heading_list.findall(".//MeshHeading"):
                descriptor = mesh_heading.find(".//DescriptorName")
                if descriptor is not None and descriptor.text:
                    mesh_terms.append(descriptor.text.strip())

        return mesh_terms

    def _month_name_to_number(self, month_name: str) -> int | None:
        """Convert month name to number."""
        month_map = {
            "jan": 1,
            "january": 1,
            "feb": 2,
            "february": 2,
            "mar": 3,
            "march": 3,
            "apr": 4,
            "april": 4,
            "may": 5,
            "jun": 6,
            "june": 6,
            "jul": 7,
            "july": 7,
            "aug": 8,
            "august": 8,
            "sep": 9,
            "september": 9,
            "oct": 10,
            "october": 10,
            "nov": 11,
            "november": 11,
            "dec": 12,
            "december": 12,
        }

        normalized = month_name.lower().strip()
        return month_map.get(normalized)

    def _clean_title(self, title: str) -> str:
        """Clean and format title."""
        if not title:
            return ""

        # Remove extra whitespace
        title = re.sub(r"\s+", " ", title.strip())

        # Remove trailing periods (common in PubMed)
        return title.rstrip(".")

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
        author_key = "pubmed"
        if authors:
            first_author = authors[0]
            # Extract last name (should be first part before comma)
            if "," in first_author:
                last_name = first_author.split(",")[0].strip()
            else:
                # Fallback: use last word
                parts = first_author.split()
                last_name = parts[-1] if parts else first_author

            # Clean last name
            author_key = re.sub(r"[^a-zA-Z0-9]", "", last_name.lower())

        year_key = str(year) if year else "unknown"

        # Add a short title word if possible
        title_words = re.findall(r"\b[a-zA-Z]{4,}\b", title.lower())
        title_key = title_words[0] if title_words else "article"

        return f"{author_key}{year_key}{title_key}"

    def get_supported_identifiers(self) -> list[str]:
        """Get list of supported identifier types."""
        return ["pmid", "doi"]

    def get_source_info(self) -> dict[str, Any]:
        """Get information about this source."""
        return {
            "name": self.name,
            "description": "PubMed/NCBI medical literature database",
            "confidence": self.confidence,
            "supported_identifiers": self.get_supported_identifiers(),
            "rate_limit": f"{self.rate_limit} requests/second",
            "coverage": "Medical, biomedical, and life sciences literature",
            "url": "https://pubmed.ncbi.nlm.nih.gov",
        }
