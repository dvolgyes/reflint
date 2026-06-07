"""Source reliability hierarchy and weighted confidence scoring system."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .base import LookupResult


class SourceTier(Enum):
    """Source reliability tiers."""

    PRIMARY = "primary"  # 0.90+ reliability
    SECONDARY = "secondary"  # 0.70-0.89 reliability
    TERTIARY = "tertiary"  # 0.50-0.69 reliability


@dataclass
class SourceReliabilityProfile:
    """Detailed reliability profile for a data source."""

    source_name: str
    tier: SourceTier
    overall_confidence: float

    # Field-specific reliability scores
    field_reliability: dict[str, float]

    # Coverage and specialization
    primary_domains: list[str]  # e.g., ["computer_science", "physics"]
    identifier_support: list[str]  # e.g., ["doi", "arxiv", "pmid"]

    # Quality indicators
    data_freshness: float  # How up-to-date the data typically is (0-1)
    completeness_score: float  # How complete the records are (0-1)

    # Special characteristics
    strengths: list[str]  # e.g., ["comprehensive_coverage", "fast_updates"]
    limitations: list[str]  # e.g., ["limited_historical_data", "english_bias"]


class SourceReliabilityRegistry:
    """Registry of source reliability profiles and hierarchy management."""

    def __init__(self) -> None:
        self._profiles: dict[str, SourceReliabilityProfile] = {}
        self._initialize_default_profiles()

    def _initialize_default_profiles(self) -> None:
        """Initialize default reliability profiles for known sources."""

        # CrossRef - Primary tier, DOI authority
        self.register_profile(
            SourceReliabilityProfile(
                source_name="crossref",
                tier=SourceTier.PRIMARY,
                overall_confidence=0.95,
                field_reliability={
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
                    "url": 0.98,  # DOI-based URLs are highly reliable
                },
                primary_domains=["all"],
                identifier_support=["doi"],
                data_freshness=0.95,
                completeness_score=0.85,
                strengths=[
                    "authoritative_doi_registry",
                    "comprehensive_publisher_coverage",
                    "excellent_metadata_quality",
                    "real_time_updates",
                ],
                limitations=["limited_to_published_works", "minimal_abstract_coverage"],
            )
        )

        # PubMed/NCBI - Primary tier for medical literature
        self.register_profile(
            SourceReliabilityProfile(
                source_name="pubmed",
                tier=SourceTier.PRIMARY,
                overall_confidence=0.92,
                field_reliability={
                    "title": 0.95,
                    "author": 0.92,
                    "abstract": 0.95,
                    "journal": 0.95,
                    "year": 0.95,
                    "volume": 0.90,
                    "number": 0.90,
                    "pages": 0.88,
                    "doi": 0.95,
                    "pmid": 0.99,
                    "issn": 0.92,
                    "keywords": 0.90,  # MeSH terms
                },
                primary_domains=["medicine", "biology", "life_sciences"],
                identifier_support=["pmid", "doi", "pmc"],
                data_freshness=0.90,
                completeness_score=0.90,
                strengths=[
                    "medical_literature_authority",
                    "excellent_abstracts",
                    "mesh_terminology",
                    "comprehensive_indexing",
                ],
                limitations=[
                    "limited_to_biomedical_fields",
                    "slower_preprint_coverage",
                ],
            )
        )

        # Semantic Scholar - Primary tier, AI-enhanced
        self.register_profile(
            SourceReliabilityProfile(
                source_name="semantic_scholar",
                tier=SourceTier.PRIMARY,
                overall_confidence=0.90,
                field_reliability={
                    "title": 0.95,
                    "author": 0.90,
                    "abstract": 0.95,
                    "year": 0.85,
                    "venue": 0.80,
                    "journal": 0.80,
                    "doi": 0.95,
                    "keywords": 0.90,
                    "url": 0.90,
                    "citation_count": 0.95,
                    "reference_count": 0.90,
                },
                primary_domains=["computer_science", "ai", "machine_learning"],
                identifier_support=["doi", "arxiv", "pmid"],
                data_freshness=0.85,
                completeness_score=0.80,
                strengths=[
                    "ai_enhanced_extraction",
                    "excellent_abstracts",
                    "citation_analysis",
                    "broad_coverage",
                    "good_preprint_support",
                ],
                limitations=["variable_venue_quality", "cs_bias_in_coverage"],
            )
        )

        # OpenAlex - Primary tier, open academic graph
        self.register_profile(
            SourceReliabilityProfile(
                source_name="openalex",
                tier=SourceTier.PRIMARY,
                overall_confidence=0.88,
                field_reliability={
                    "title": 0.90,
                    "author": 0.88,
                    "journal": 0.85,
                    "year": 0.90,
                    "doi": 0.95,
                    "issn": 0.88,
                    "venue": 0.85,
                    "institution": 0.90,
                    "funder": 0.85,
                },
                primary_domains=["all"],
                identifier_support=["doi", "pmid", "mag_id"],
                data_freshness=0.80,
                completeness_score=0.85,
                strengths=[
                    "comprehensive_coverage",
                    "institutional_affiliations",
                    "funding_information",
                    "open_access",
                ],
                limitations=["newer_service", "variable_historical_coverage"],
            )
        )

        # DBLP - Primary tier for computer science
        self.register_profile(
            SourceReliabilityProfile(
                source_name="dblp",
                tier=SourceTier.PRIMARY,
                overall_confidence=0.85,
                field_reliability={
                    "title": 0.95,
                    "author": 0.95,
                    "booktitle": 0.90,
                    "journal": 0.90,
                    "year": 0.95,
                    "volume": 0.85,
                    "number": 0.85,
                    "pages": 0.80,
                    "publisher": 0.85,
                    "venue": 0.90,
                },
                primary_domains=["computer_science"],
                identifier_support=["dblp_key"],
                data_freshness=0.90,
                completeness_score=0.80,
                strengths=[
                    "cs_literature_authority",
                    "excellent_venue_data",
                    "consistent_author_names",
                    "conference_proceedings",
                ],
                limitations=[
                    "cs_only_coverage",
                    "limited_abstracts",
                    "no_doi_coverage",
                ],
            )
        )

        # arXiv API - Secondary tier, preprint repository
        self.register_profile(
            SourceReliabilityProfile(
                source_name="arxiv",
                tier=SourceTier.SECONDARY,
                overall_confidence=0.80,
                field_reliability={
                    "title": 0.95,
                    "author": 0.90,
                    "abstract": 0.95,
                    "year": 0.90,
                    "arxiv_id": 0.99,
                    "category": 0.90,
                    "submission_date": 0.95,
                    "update_date": 0.95,
                },
                primary_domains=[
                    "physics",
                    "mathematics",
                    "computer_science",
                    "statistics",
                ],
                identifier_support=["arxiv"],
                data_freshness=0.95,
                completeness_score=0.70,
                strengths=[
                    "preprint_authority",
                    "rapid_availability",
                    "excellent_abstracts",
                    "version_tracking",
                ],
                limitations=[
                    "preprint_quality_varies",
                    "no_peer_review",
                    "limited_metadata",
                ],
            )
        )

        # Google Scholar - Secondary tier, broad coverage with limitations
        self.register_profile(
            SourceReliabilityProfile(
                source_name="google_scholar",
                tier=SourceTier.SECONDARY,
                overall_confidence=0.70,
                field_reliability={
                    "title": 0.85,
                    "author": 0.80,
                    "venue": 0.70,
                    "year": 0.80,
                    "citation_count": 0.85,
                    "pdf_availability": 0.90,
                },
                primary_domains=["all"],
                identifier_support=["scholar_id"],
                data_freshness=0.75,
                completeness_score=0.95,
                strengths=[
                    "broadest_coverage",
                    "includes_theses",
                    "citation_tracking",
                    "pdf_access",
                ],
                limitations=[
                    "web_scraping_basis",
                    "inconsistent_metadata",
                    "duplicate_detection_issues",
                    "rate_limiting",
                ],
            )
        )

    def register_profile(self, profile: SourceReliabilityProfile) -> None:
        """Register a source reliability profile."""
        self._profiles[profile.source_name] = profile

    def get_profile(self, source_name: str) -> SourceReliabilityProfile | None:
        """Get reliability profile for a source."""
        return self._profiles.get(source_name)

    def get_sources_by_tier(self, tier: SourceTier) -> list[SourceReliabilityProfile]:
        """Get all sources in a specific reliability tier."""
        return [p for p in self._profiles.values() if p.tier == tier]

    def get_best_sources_for_field(
        self, field_name: str, limit: int = 3
    ) -> list[tuple[str, float]]:
        """Get the best sources for a specific field, ranked by reliability."""
        field_scores = []

        for profile in self._profiles.values():
            score = profile.field_reliability.get(
                field_name, profile.overall_confidence * 0.8
            )
            field_scores.append((profile.source_name, score))

        # Sort by score (descending) and return top N
        field_scores.sort(key=lambda x: x[1], reverse=True)
        return field_scores[:limit]

    def calculate_weighted_confidence(
        self, results: list[LookupResult], field_name: str
    ) -> float:
        """Calculate weighted confidence score from multiple source results."""
        if not results:
            return 0.0

        total_weight = 0.0
        weighted_confidence_sum = 0.0

        for result in results:
            if result.entry and result.entry.has_field(field_name):
                profile = self.get_profile(result.metadata.source_name)
                if profile:
                    # Get field-specific reliability
                    field_reliability = profile.field_reliability.get(
                        field_name, profile.overall_confidence * 0.8
                    )

                    # Calculate base confidence incorporating all factors
                    base_confidence = (
                        field_reliability
                        * result.metadata.confidence
                        * profile.data_freshness
                        * profile.completeness_score
                    )

                    # Use field reliability as the weight
                    weight = field_reliability

                    weighted_confidence_sum += base_confidence * weight
                    total_weight += weight

        return weighted_confidence_sum / total_weight if total_weight > 0 else 0.0

    def recommend_lookup_strategy(
        self, identifiers: dict[str, str], domains: list[str] | None = None
    ) -> list[str]:
        """Recommend optimal lookup strategy based on available identifiers and domains."""
        strategy = []

        # Primary sources based on identifiers
        if "doi" in identifiers:
            strategy.extend(["crossref", "semantic_scholar"])

        if "pmid" in identifiers:
            strategy.extend(["pubmed", "semantic_scholar"])

        if "arxiv" in identifiers:
            strategy.extend(["arxiv", "semantic_scholar"])

        # Domain-specific recommendations
        if domains:
            for domain in domains:
                if (
                    domain in ["medicine", "biology", "life_sciences"]
                    and "pubmed" not in strategy
                ):
                    strategy.append("pubmed")
                elif domain == "computer_science" and "dblp" not in strategy:
                    strategy.append("dblp")

        # Add general high-reliability sources if not already included
        if "semantic_scholar" not in strategy:
            strategy.append("semantic_scholar")

        if "openalex" not in strategy:
            strategy.append("openalex")

        # Fallback to Google Scholar for broad coverage
        if "google_scholar" not in strategy:
            strategy.append("google_scholar")

        return strategy

    def merge_field_values(
        self, results: list[LookupResult], field_name: str
    ) -> tuple[str | None, float]:
        """
        Merge field values from multiple sources using reliability weighting.

        Returns:
            Tuple of (best_value, confidence_score)
        """
        if not results:
            return None, 0.0

        # Collect all values with their confidence scores
        value_scores: dict[str, float] = {}

        for result in results:
            if result.entry and result.entry.has_field(field_name):
                value = result.entry.get_field(field_name)
                if value:
                    profile = self.get_profile(result.metadata.source_name)
                    if profile:
                        field_reliability = profile.field_reliability.get(
                            field_name, profile.overall_confidence * 0.8
                        )

                        # Calculate total confidence for this value
                        confidence = (
                            field_reliability
                            * result.metadata.confidence
                            * profile.data_freshness
                            * profile.completeness_score
                        )

                        # Accumulate confidence for identical values
                        if value in value_scores:
                            value_scores[value] += confidence
                        else:
                            value_scores[value] = confidence

        if not value_scores:
            return None, 0.0

        # Return value with highest accumulated confidence
        best_value = max(value_scores.items(), key=lambda x: x[1])
        return best_value[0], best_value[1]

    def get_source_statistics(self) -> dict[str, Any]:
        """Get statistics about registered sources."""
        stats: dict[str, Any] = {
            "total_sources": len(self._profiles),
            "by_tier": {
                tier.value: len(self.get_sources_by_tier(tier)) for tier in SourceTier
            },
            "domain_coverage": {},
            "identifier_support": {},
            "average_confidence": sum(
                p.overall_confidence for p in self._profiles.values()
            )
            / len(self._profiles),
        }

        # Analyze domain coverage
        all_domains = set()
        for profile in self._profiles.values():
            all_domains.update(profile.primary_domains)

        for domain in all_domains:
            stats["domain_coverage"][domain] = [
                p.source_name
                for p in self._profiles.values()
                if domain in p.primary_domains or "all" in p.primary_domains
            ]

        # Analyze identifier support
        all_identifiers = set()
        for profile in self._profiles.values():
            all_identifiers.update(profile.identifier_support)

        for identifier in all_identifiers:
            stats["identifier_support"][identifier] = [
                p.source_name
                for p in self._profiles.values()
                if identifier in p.identifier_support
            ]

        return stats


# Global registry instance
_global_reliability_registry = SourceReliabilityRegistry()


def get_reliability_registry() -> SourceReliabilityRegistry:
    """Get the global source reliability registry."""
    return _global_reliability_registry
