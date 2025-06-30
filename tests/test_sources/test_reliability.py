"""Tests for source reliability hierarchy system."""

from src.reflint.sources.reliability import (
    SourceReliabilityRegistry,
    SourceReliabilityProfile,
    SourceTier,
    get_reliability_registry,
)
from src.reflint.sources.base import LookupResult, SourceMetadata
from src.reflint.core.entry import BibTeXEntry


class TestSourceReliabilityRegistry:
    """Test cases for source reliability registry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = SourceReliabilityRegistry()

    def test_default_profiles_loaded(self):
        """Test that default source profiles are loaded."""
        # Check that major sources are registered
        major_sources = [
            "crossref",
            "pubmed",
            "semantic_scholar",
            "openalex",
            "dblp",
            "arxiv",
            "google_scholar",
        ]

        for source in major_sources:
            profile = self.registry.get_profile(source)
            assert profile is not None
            assert profile.source_name == source

    def test_crossref_primary_tier(self):
        """Test that CrossRef is classified as primary tier."""
        crossref_profile = self.registry.get_profile("crossref")

        assert crossref_profile is not None
        assert crossref_profile.tier == SourceTier.PRIMARY
        assert crossref_profile.overall_confidence >= 0.90
        assert "doi" in crossref_profile.identifier_support
        assert crossref_profile.field_reliability["doi"] >= 0.95

    def test_google_scholar_secondary_tier(self):
        """Test that Google Scholar is classified as secondary tier."""
        scholar_profile = self.registry.get_profile("google_scholar")

        assert scholar_profile is not None
        assert scholar_profile.tier == SourceTier.SECONDARY
        assert scholar_profile.overall_confidence < 0.90
        assert "web_scraping_basis" in scholar_profile.limitations

    def test_get_sources_by_tier(self):
        """Test getting sources by reliability tier."""
        primary_sources = self.registry.get_sources_by_tier(SourceTier.PRIMARY)
        secondary_sources = self.registry.get_sources_by_tier(SourceTier.SECONDARY)

        assert len(primary_sources) > 0
        assert len(secondary_sources) > 0

        # Check that all primary sources have high confidence
        for profile in primary_sources:
            assert profile.overall_confidence >= 0.85

    def test_get_best_sources_for_field(self):
        """Test getting best sources for specific fields."""
        # Test DOI field - CrossRef should be top
        doi_sources = self.registry.get_best_sources_for_field("doi", limit=3)

        assert len(doi_sources) > 0
        source_names = [name for name, score in doi_sources]
        assert "crossref" in source_names

        # Check scores are sorted in descending order
        scores = [score for name, score in doi_sources]
        assert scores == sorted(scores, reverse=True)

    def test_calculate_weighted_confidence(self):
        """Test weighted confidence calculation from multiple sources."""
        # Create mock lookup results
        crossref_entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "article", "title": "Test Title"}
        )
        crossref_metadata = SourceMetadata(
            source_name="crossref", lookup_time=0.5, confidence=0.95
        )
        crossref_result = LookupResult(crossref_entry, crossref_metadata)

        scholar_entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "article", "title": "Test Title"}
        )
        scholar_metadata = SourceMetadata(
            source_name="google_scholar", lookup_time=1.0, confidence=0.70
        )
        scholar_result = LookupResult(scholar_entry, scholar_metadata)

        results = [crossref_result, scholar_result]

        # Calculate weighted confidence for title field
        confidence = self.registry.calculate_weighted_confidence(results, "title")

        assert 0.0 < confidence < 1.0
        # Confidence should be reasonable (incorporating all reliability factors)
        assert confidence > 0.50

    def test_recommend_lookup_strategy(self):
        """Test lookup strategy recommendation."""
        # Test with DOI identifier
        doi_strategy = self.registry.recommend_lookup_strategy({"doi": "10.1000/123"})

        assert "crossref" in doi_strategy
        assert "semantic_scholar" in doi_strategy

        # Test with arXiv identifier
        arxiv_strategy = self.registry.recommend_lookup_strategy(
            {"arxiv": "2023.12345"}
        )

        assert "arxiv" in arxiv_strategy
        assert "semantic_scholar" in arxiv_strategy

        # Test with medical domain
        medical_strategy = self.registry.recommend_lookup_strategy(
            {"pmid": "12345"}, domains=["medicine"]
        )

        assert "pubmed" in medical_strategy

    def test_merge_field_values(self):
        """Test merging field values from multiple sources."""
        # Create entries with same title but different sources
        crossref_entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "article", "title": "Reliable Title"}
        )
        crossref_metadata = SourceMetadata(
            source_name="crossref", lookup_time=0.5, confidence=0.95
        )
        crossref_result = LookupResult(crossref_entry, crossref_metadata)

        # Google Scholar with slightly different title
        scholar_entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Reliable Title",  # Same title
            }
        )
        scholar_metadata = SourceMetadata(
            source_name="google_scholar", lookup_time=1.0, confidence=0.70
        )
        scholar_result = LookupResult(scholar_entry, scholar_metadata)

        results = [crossref_result, scholar_result]

        best_title, confidence = self.registry.merge_field_values(results, "title")

        assert best_title == "Reliable Title"
        assert confidence > 0.0

    def test_get_source_statistics(self):
        """Test getting source statistics."""
        stats = self.registry.get_source_statistics()

        assert "total_sources" in stats
        assert "by_tier" in stats
        assert "domain_coverage" in stats
        assert "identifier_support" in stats
        assert "average_confidence" in stats

        assert stats["total_sources"] > 0
        assert stats["average_confidence"] > 0.0

        # Check tier distribution
        assert SourceTier.PRIMARY.value in stats["by_tier"]
        assert SourceTier.SECONDARY.value in stats["by_tier"]

        # Check domain coverage
        assert "computer_science" in stats["domain_coverage"]
        assert "medicine" in stats["domain_coverage"]

        # Check identifier support
        assert "doi" in stats["identifier_support"]
        assert "crossref" in stats["identifier_support"]["doi"]

    def test_custom_profile_registration(self):
        """Test registering custom reliability profiles."""
        custom_profile = SourceReliabilityProfile(
            source_name="test_source",
            tier=SourceTier.TERTIARY,
            overall_confidence=0.60,
            field_reliability={"title": 0.80, "author": 0.70},
            primary_domains=["test_domain"],
            identifier_support=["test_id"],
            data_freshness=0.50,
            completeness_score=0.60,
            strengths=["test_strength"],
            limitations=["test_limitation"],
        )

        self.registry.register_profile(custom_profile)

        retrieved_profile = self.registry.get_profile("test_source")
        assert retrieved_profile is not None
        assert retrieved_profile.source_name == "test_source"
        assert retrieved_profile.tier == SourceTier.TERTIARY
        assert retrieved_profile.overall_confidence == 0.60

    def test_domain_specific_recommendations(self):
        """Test domain-specific source recommendations."""
        # Computer science should recommend DBLP
        cs_strategy = self.registry.recommend_lookup_strategy(
            {}, domains=["computer_science"]
        )
        assert "dblp" in cs_strategy

        # Medical domain should recommend PubMed
        med_strategy = self.registry.recommend_lookup_strategy({}, domains=["medicine"])
        assert "pubmed" in med_strategy

    def test_global_registry_singleton(self):
        """Test that global registry returns the same instance."""
        registry1 = get_reliability_registry()
        registry2 = get_reliability_registry()

        assert registry1 is registry2
        assert "crossref" in [p.source_name for p in registry1._profiles.values()]

    def test_field_reliability_inheritance(self):
        """Test that field reliability falls back to overall confidence."""
        profile = self.registry.get_profile("crossref")

        # Test existing field
        doi_reliability = profile.field_reliability.get("doi")
        assert doi_reliability is not None
        assert doi_reliability > 0.90

        # Test non-existent field should use overall confidence
        best_sources = self.registry.get_best_sources_for_field("nonexistent_field")
        assert len(best_sources) > 0
