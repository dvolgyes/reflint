"""Enhanced identifier resolution and lookup strategy."""

import re
from dataclasses import dataclass

from loguru import logger

from ..core.entry import BibTeXEntry
from ..sources.base import LookupResult
from ..sources.registry import DataSourceRegistry
from ..utils.identifiers import IdentifierExtractor


@dataclass
class ResolvedIdentifiers:
    """Container for resolved and prioritized identifiers."""

    primary_doi: str | None = None
    primary_isbn: str | None = None
    arxiv_id: str | None = None
    pmid: str | None = None
    issn: str | None = None

    # Additional identifiers found via Semantic Scholar
    s2_doi: str | None = None
    s2_isbn: str | None = None
    s2_pmid: str | None = None

    # Flags
    is_web_only: bool = False
    skip_semantic_scholar: bool = False


class EnhancedLookupStrategy:
    """Enhanced lookup strategy with intelligent identifier prioritization."""

    # arXiv DOI pattern
    ARXIV_DOI_PATTERN = re.compile(r"10\.48550/arxiv\.", re.IGNORECASE)

    # Patterns for web/online-only sources (skip Semantic Scholar)
    WEB_ONLY_PATTERNS = [
        re.compile(r"@misc\s*{.*url\s*=.*}", re.IGNORECASE | re.DOTALL),
        re.compile(r"howpublished\s*=.*{.*online.*}", re.IGNORECASE),
        re.compile(r"howpublished\s*=.*{.*web.*}", re.IGNORECASE),
        re.compile(r"note\s*=.*{.*web.*}", re.IGNORECASE),
        re.compile(r"note\s*=.*{.*online.*}", re.IGNORECASE),
    ]

    def __init__(self, source_registry: DataSourceRegistry):
        """Initialize enhanced lookup strategy.

        Args:
            source_registry: Registry of available data sources
        """
        self.source_registry = source_registry
        self.extractor = IdentifierExtractor()

    def is_arxiv_doi(self, doi: str) -> bool:
        """Check if DOI is from arXiv (10.48550/arXiv.*)."""
        return bool(self.ARXIV_DOI_PATTERN.match(doi))

    def is_web_only_entry(self, entry: BibTeXEntry) -> bool:
        """Check if entry is web/online only and should skip Semantic Scholar."""
        # Check entry type
        if entry.entry_type.lower() == "misc":
            # Check if it has URL but no DOI/ISBN/PMID
            has_url = entry.has_field("url") and entry.get_field("url")
            has_doi = entry.has_field("doi") and entry.get_field("doi")
            has_isbn = entry.has_field("isbn") and entry.get_field("isbn")
            has_pmid = entry.has_field("pmid") and entry.get_field("pmid")

            if has_url and not (has_doi or has_isbn or has_pmid):
                return True

        # Check for web/online patterns in text
        entry_text = str(entry.to_dict())
        return any(pattern.search(entry_text) for pattern in self.WEB_ONLY_PATTERNS)

    def resolve_identifiers(self, entry: BibTeXEntry) -> ResolvedIdentifiers:
        """Resolve and prioritize identifiers from entry.

        Args:
            entry: BibTeX entry to analyze

        Returns:
            ResolvedIdentifiers with prioritized identifier information
        """
        resolved = ResolvedIdentifiers()

        # Check if this is a web-only entry
        resolved.is_web_only = self.is_web_only_entry(entry)
        resolved.skip_semantic_scholar = resolved.is_web_only

        # Extract all identifiers
        identifiers = self.extractor.extract_from_entry(entry)

        # Categorize and prioritize identifiers
        for identifier in identifiers:
            if identifier.identifier_type == "doi":
                # Prioritize non-arXiv DOIs
                if not self.is_arxiv_doi(identifier.value):
                    if not resolved.primary_doi:
                        resolved.primary_doi = identifier.value
                elif not resolved.arxiv_id:
                    # Extract arXiv ID from arXiv DOI
                    arxiv_match = re.search(
                        r"10\.48550/arxiv\.(.+)", identifier.value, re.IGNORECASE
                    )
                    if arxiv_match:
                        resolved.arxiv_id = arxiv_match.group(1)

            elif identifier.identifier_type == "isbn":
                if not resolved.primary_isbn:
                    resolved.primary_isbn = identifier.value

            elif identifier.identifier_type == "arxiv":
                if not resolved.arxiv_id:
                    resolved.arxiv_id = identifier.value

            elif identifier.identifier_type == "pmid":
                if not resolved.pmid:
                    resolved.pmid = identifier.value

            elif identifier.identifier_type == "issn" and not resolved.issn:
                resolved.issn = identifier.value

        logger.debug(
            f"Resolved identifiers for {entry.key}: DOI={resolved.primary_doi}, "
            f"ISBN={resolved.primary_isbn}, arXiv={resolved.arxiv_id}, "
            f"PMID={resolved.pmid}, web_only={resolved.is_web_only}"
        )

        return resolved

    async def resolve_via_semantic_scholar(
        self, resolved: ResolvedIdentifiers
    ) -> ResolvedIdentifiers:
        """Resolve additional identifiers via Semantic Scholar.

        Args:
            resolved: Current resolved identifiers

        Returns:
            Updated ResolvedIdentifiers with additional information from Semantic Scholar
        """
        if resolved.skip_semantic_scholar:
            logger.debug("Skipping Semantic Scholar lookup for web-only entry")
            return resolved

        # Get Semantic Scholar source
        s2_source = self.source_registry.get_source("semantic_scholar")
        if not s2_source:
            logger.warning("Semantic Scholar source not available")
            return resolved

        # Try different lookup strategies in order of priority
        s2_result = None

        # 1. If we have arXiv ID but no DOI, try to find DOI via arXiv lookup
        if resolved.arxiv_id and not resolved.primary_doi:
            logger.debug(f"Looking up arXiv {resolved.arxiv_id} via Semantic Scholar")
            try:
                s2_result = await s2_source.lookup_by_arxiv(resolved.arxiv_id)
            except Exception as e:
                logger.warning(
                    f"Failed to lookup arXiv {resolved.arxiv_id} via Semantic Scholar: {e}"
                )

        # 2. If we have PMID but no DOI, try to find DOI via PMID lookup
        if resolved.pmid and not resolved.primary_doi and not s2_result:
            logger.debug(f"Looking up PMID {resolved.pmid} via Semantic Scholar")
            try:
                s2_result = await s2_source.lookup_by_pmid(resolved.pmid)
            except Exception as e:
                logger.warning(
                    f"Failed to lookup PMID {resolved.pmid} via Semantic Scholar: {e}"
                )

        # Extract additional identifiers from Semantic Scholar result
        if s2_result and s2_result.entry:
            s2_entry = s2_result.entry

            # Extract DOI (non-arXiv)
            if s2_entry.has_field("doi"):
                s2_doi = s2_entry.get_field("doi")
                if s2_doi and not self.is_arxiv_doi(s2_doi):
                    resolved.s2_doi = s2_doi
                    # Use this as primary DOI if we don't have one
                    if not resolved.primary_doi:
                        resolved.primary_doi = s2_doi
                        logger.info(f"Found DOI via Semantic Scholar: {s2_doi}")

            # Extract ISBN
            if s2_entry.has_field("isbn"):
                s2_isbn = s2_entry.get_field("isbn")
                if s2_isbn:
                    resolved.s2_isbn = s2_isbn
                    if not resolved.primary_isbn:
                        resolved.primary_isbn = s2_isbn
                        logger.info(f"Found ISBN via Semantic Scholar: {s2_isbn}")

            # Extract PMID
            if s2_entry.has_field("pmid"):
                s2_pmid = s2_entry.get_field("pmid")
                if s2_pmid:
                    resolved.s2_pmid = s2_pmid
                    if not resolved.pmid:
                        resolved.pmid = s2_pmid
                        logger.info(f"Found PMID via Semantic Scholar: {s2_pmid}")

            # If we found a DOI and had only arXiv, remove arXiv preference
            if resolved.s2_doi and resolved.arxiv_id and not resolved.primary_doi:
                logger.info(
                    f"Replacing arXiv {resolved.arxiv_id} with DOI {resolved.s2_doi}"
                )
                resolved.arxiv_id = None  # Remove arXiv since we have a proper DOI

        return resolved

    async def get_lookup_results(
        self, resolved: ResolvedIdentifiers, source_filter: list[str] | None = None
    ) -> list[LookupResult]:
        """Get lookup results using prioritized identifiers.

        Args:
            resolved: Resolved identifiers
            source_filter: Optional list of source names to filter by

        Returns:
            List of lookup results from all appropriate sources
        """
        all_results = []

        # Priority order for identifiers
        lookup_sequence = []

        # 1. Primary DOI (highest priority)
        if resolved.primary_doi:
            lookup_sequence.append(("doi", resolved.primary_doi))

        # 2. Primary ISBN
        if resolved.primary_isbn:
            lookup_sequence.append(("isbn", resolved.primary_isbn))

        # 3. PMID
        if resolved.pmid:
            lookup_sequence.append(("pmid", resolved.pmid))

        # 4. arXiv (only if no DOI found)
        if resolved.arxiv_id and not resolved.primary_doi:
            lookup_sequence.append(("arxiv", resolved.arxiv_id))

        # 5. ISSN (lowest priority)
        if resolved.issn:
            lookup_sequence.append(("issn", resolved.issn))

        # For web-only entries, only use specific sources
        if resolved.is_web_only:
            # Skip most sources for web-only entries
            logger.debug("Skipping external lookups for web-only entry")
            return []

        # Perform lookups
        for identifier_type, value in lookup_sequence:
            try:
                logger.debug(f"Looking up {identifier_type}:{value}")
                results = await self.source_registry.lookup_with_fallback(
                    identifier_type, value, preferred_sources=source_filter
                )
                all_results.extend(results)
            except Exception as e:
                logger.warning(f"Lookup failed for {identifier_type}:{value}: {e}")

        return all_results

    def should_enhance_with_crossref(self, resolved: ResolvedIdentifiers) -> bool:
        """Determine if entry should be enhanced with CrossRef.

        Args:
            resolved: Resolved identifiers

        Returns:
            True if CrossRef should be used for enhancement
        """
        # Use CrossRef if we have a DOI and it's not web-only
        return bool(resolved.primary_doi and not resolved.is_web_only)

    def get_enhancement_sources(self, resolved: ResolvedIdentifiers) -> list[str]:
        """Get list of sources to use for enhancement based on identifiers.

        Args:
            resolved: Resolved identifiers

        Returns:
            List of source names to use for enhancement
        """
        sources = []

        if resolved.is_web_only:
            # For web-only entries, minimal enhancement
            return []

        # Always try Semantic Scholar first (unless skipped)
        if not resolved.skip_semantic_scholar:
            sources.append("semantic_scholar")

        # Add CrossRef if we have DOI
        if resolved.primary_doi:
            sources.append("crossref")

        # Add PubMed if we have PMID or it's medical
        if resolved.pmid:
            sources.append("pubmed")

        # Add arXiv if we have arXiv ID
        if resolved.arxiv_id:
            sources.append("arxiv")

        # Add OpenAlex for additional metadata
        if resolved.primary_doi or resolved.pmid:
            sources.append("openalex")

        return sources
