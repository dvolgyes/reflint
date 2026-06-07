"""ISSN lookup utility for journal name resolution.

This module provides functionality to look up ISSN information for journals
based on their names using various academic databases.
"""

from typing import Any
from loguru import logger

from ..sources.openalex import OpenAlexSource
from ..sources.crossref import CrossRefSource


class ISSNLookupService:
    """Service for looking up ISSN information based on journal names."""

    def __init__(self, email: str | None = None):
        """Initialize ISSN lookup service.

        Args:
            email: Email for polite crawling identification
        """
        self.openalex = OpenAlexSource(email=email)
        self.crossref = CrossRefSource()

    async def lookup_issn_by_journal_name(
        self, journal_name: str
    ) -> dict[str, Any] | None:
        """Look up ISSN information for a journal by name.

        Args:
            journal_name: Name of the journal to search for

        Returns:
            Dictionary with ISSN information including:
            - issn_l: Linking ISSN (canonical)
            - issn: List of all ISSNs (electronic and print)
            - eissn: Electronic ISSN (preferred)
            - pissn: Print ISSN
            - display_name: Official journal name
            - source: Which database provided the information
        """
        if not journal_name or not journal_name.strip():
            return None

        journal_name = journal_name.strip()
        logger.debug(f"Looking up ISSN for journal: {journal_name}")

        # Try OpenAlex first (has comprehensive ISSN coverage)
        try:
            openalex_result = await self.openalex.lookup_journal_issn(journal_name)
            if openalex_result and (
                openalex_result.get("issn_l") or openalex_result.get("issn")
            ):
                result = self._process_openalex_result(openalex_result)
                if result:
                    logger.debug(
                        f"Found ISSN via OpenAlex for '{journal_name}': {result}"
                    )
                    return result
        except Exception as e:
            logger.debug(f"OpenAlex ISSN lookup failed for '{journal_name}': {e}")

        # TODO: Could add CrossRef journal search as fallback if needed
        # CrossRef doesn't have a direct journal name search, but could search for recent papers

        logger.debug(f"No ISSN found for journal: {journal_name}")
        return None

    def _process_openalex_result(
        self, openalex_result: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Process OpenAlex result into standardized format."""
        if not openalex_result:
            return None

        issn_list = openalex_result.get("issn", [])
        issn_l = openalex_result.get("issn_l")

        if not issn_l and not issn_list:
            return None

        # Separate electronic and print ISSNs
        # Electronic ISSNs typically have higher numeric values
        eissn = None
        pissn = None

        if issn_list:
            if len(issn_list) == 1:
                # If only one ISSN, assume it's the electronic one (more common now)
                eissn = issn_list[0]
            else:
                # Sort to prefer electronic ISSN (higher values)
                sorted_issns = sorted(issn_list, reverse=True)
                eissn = sorted_issns[0]
                pissn = sorted_issns[-1] if len(sorted_issns) > 1 else None

        return {
            "issn_l": issn_l,
            "issn": issn_list,
            "eissn": eissn,
            "pissn": pissn,
            "display_name": openalex_result.get("display_name", ""),
            "source": "openalex",
        }

    async def close(self) -> None:
        """Close any open connections."""
        if hasattr(self.openalex, "close"):
            await self.openalex.close()
        if hasattr(self.crossref, "close"):
            await self.crossref.close()


async def lookup_journal_issn(
    journal_name: str, email: str | None = None
) -> dict[str, Any] | None:
    """Convenience function to look up ISSN for a journal name.

    Args:
        journal_name: Name of the journal
        email: Optional email for polite crawling

    Returns:
        ISSN information dictionary or None if not found
    """
    service = ISSNLookupService(email=email)
    try:
        return await service.lookup_issn_by_journal_name(journal_name)
    finally:
        await service.close()
