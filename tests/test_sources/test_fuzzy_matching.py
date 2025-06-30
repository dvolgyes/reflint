"""Tests for fuzzy matching algorithms."""

from src.reflint.sources.fuzzy_matching import (
    FuzzyMatcher,
    SimilarityScore,
    get_fuzzy_matcher,
)
from src.reflint.sources.base import LookupResult, SourceMetadata
from src.reflint.core.entry import BibTeXEntry


class TestFuzzyMatcher:
    """Test cases for fuzzy matching algorithms."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = FuzzyMatcher()

    def test_identical_entries(self):
        """Test that identical entries have maximum similarity."""
        entry1 = BibTeXEntry(
            {
                "ID": "test1",
                "ENTRYTYPE": "article",
                "title": "Deep Learning for Computer Vision",
                "author": "John Smith and Jane Doe",
                "year": "2023",
                "journal": "Nature",
            }
        )

        entry2 = BibTeXEntry(
            {
                "ID": "test2",
                "ENTRYTYPE": "article",
                "title": "Deep Learning for Computer Vision",
                "author": "John Smith and Jane Doe",
                "year": "2023",
                "journal": "Nature",
            }
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.overall >= 0.95
        assert similarity.title_similarity >= 0.95
        assert similarity.author_similarity >= 0.95
        assert similarity.year_similarity == 1.0
        assert similarity.venue_similarity >= 0.95

    def test_title_similarity_normalization(self):
        """Test title similarity with normalization."""
        entry1 = BibTeXEntry(
            {
                "ID": "test1",
                "ENTRYTYPE": "article",
                "title": "Deep Learning for Computer Vision: A Survey",
            }
        )

        entry2 = BibTeXEntry(
            {
                "ID": "test2",
                "ENTRYTYPE": "article",
                "title": "deep learning for computer vision, a survey",
            }
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.title_similarity >= 0.90

    def test_title_similarity_partial_match(self):
        """Test title similarity with partial matches."""
        entry1 = BibTeXEntry(
            {
                "ID": "test1",
                "ENTRYTYPE": "article",
                "title": "Deep Learning for Computer Vision",
            }
        )

        entry2 = BibTeXEntry(
            {
                "ID": "test2",
                "ENTRYTYPE": "article",
                "title": "Deep Learning Approaches in Computer Vision Applications",
            }
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert 0.60 <= similarity.title_similarity <= 0.90

    def test_author_similarity_exact_match(self):
        """Test author similarity with exact matches."""
        entry1 = BibTeXEntry(
            {"ID": "test1", "ENTRYTYPE": "article", "author": "John Smith and Jane Doe"}
        )

        entry2 = BibTeXEntry(
            {"ID": "test2", "ENTRYTYPE": "article", "author": "John Smith and Jane Doe"}
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.author_similarity >= 0.95

    def test_author_similarity_partial_match(self):
        """Test author similarity with partial name matches."""
        entry1 = BibTeXEntry(
            {"ID": "test1", "ENTRYTYPE": "article", "author": "John Smith and Jane Doe"}
        )

        entry2 = BibTeXEntry(
            {"ID": "test2", "ENTRYTYPE": "article", "author": "J. Smith and J. Doe"}
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.author_similarity >= 0.60

    def test_author_similarity_order_independence(self):
        """Test that author order doesn't significantly affect similarity."""
        entry1 = BibTeXEntry(
            {
                "ID": "test1",
                "ENTRYTYPE": "article",
                "author": "John Smith and Jane Doe and Bob Johnson",
            }
        )

        entry2 = BibTeXEntry(
            {
                "ID": "test2",
                "ENTRYTYPE": "article",
                "author": "Jane Doe and Bob Johnson and John Smith",
            }
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.author_similarity >= 0.95

    def test_year_similarity_exact_match(self):
        """Test year similarity with exact matches."""
        entry1 = BibTeXEntry({"ID": "test1", "ENTRYTYPE": "article", "year": "2023"})

        entry2 = BibTeXEntry({"ID": "test2", "ENTRYTYPE": "article", "year": "2023"})

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.year_similarity == 1.0

    def test_year_similarity_close_years(self):
        """Test year similarity with close years."""
        entry1 = BibTeXEntry({"ID": "test1", "ENTRYTYPE": "article", "year": "2023"})

        entry2 = BibTeXEntry({"ID": "test2", "ENTRYTYPE": "article", "year": "2024"})

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.year_similarity == 0.8  # Off by one year

    def test_year_similarity_distant_years(self):
        """Test year similarity with distant years."""
        entry1 = BibTeXEntry({"ID": "test1", "ENTRYTYPE": "article", "year": "2023"})

        entry2 = BibTeXEntry({"ID": "test2", "ENTRYTYPE": "article", "year": "2010"})

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.year_similarity == 0.0

    def test_venue_similarity_journal(self):
        """Test venue similarity for journals."""
        entry1 = BibTeXEntry(
            {
                "ID": "test1",
                "ENTRYTYPE": "article",
                "journal": "Nature Machine Intelligence",
            }
        )

        entry2 = BibTeXEntry(
            {
                "ID": "test2",
                "ENTRYTYPE": "article",
                "journal": "Nature Machine Intelligence",
            }
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.venue_similarity >= 0.95

    def test_venue_similarity_conference(self):
        """Test venue similarity for conferences."""
        entry1 = BibTeXEntry(
            {
                "ID": "test1",
                "ENTRYTYPE": "inproceedings",
                "booktitle": "International Conference on Machine Learning",
            }
        )

        entry2 = BibTeXEntry(
            {"ID": "test2", "ENTRYTYPE": "inproceedings", "booktitle": "ICML"}
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        # Should detect acronym match
        assert similarity.venue_similarity >= 0.80

    def test_venue_similarity_normalization(self):
        """Test venue similarity with normalization."""
        entry1 = BibTeXEntry(
            {
                "ID": "test1",
                "ENTRYTYPE": "article",
                "journal": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            }
        )

        entry2 = BibTeXEntry(
            {
                "ID": "test2",
                "ENTRYTYPE": "article",
                "journal": "Transactions on Pattern Analysis and Machine Intelligence",
            }
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        assert similarity.venue_similarity >= 0.85

    def test_missing_fields_handling(self):
        """Test handling of missing fields."""
        entry1 = BibTeXEntry(
            {"ID": "test1", "ENTRYTYPE": "article", "title": "Test Title"}
        )

        entry2 = BibTeXEntry(
            {
                "ID": "test2",
                "ENTRYTYPE": "article",
                "title": "Test Title",
                "author": "John Smith",
                "year": "2023",
                "journal": "Nature",
            }
        )

        similarity = self.matcher.calculate_similarity(entry1, entry2)

        # Should still have reasonable overall similarity due to title match
        assert 0.30 <= similarity.overall <= 0.60
        assert similarity.title_similarity >= 0.95
        assert similarity.author_similarity == 0.0  # Missing in entry1
        assert similarity.year_similarity == 0.5  # Neutral score for missing
        assert similarity.venue_similarity == 0.5  # Neutral score for missing

    def test_custom_weights(self):
        """Test similarity calculation with custom weights."""
        entry1 = BibTeXEntry(
            {
                "ID": "test1",
                "ENTRYTYPE": "article",
                "title": "Test Title",
                "author": "John Smith",
            }
        )

        entry2 = BibTeXEntry(
            {
                "ID": "test2",
                "ENTRYTYPE": "article",
                "title": "Different Title",
                "author": "John Smith",
            }
        )

        # Weight authors more heavily than title
        custom_weights = {"title": 0.20, "author": 0.60, "year": 0.10, "venue": 0.10}

        similarity = self.matcher.calculate_similarity(
            entry1, entry2, weights=custom_weights
        )

        # Should have higher overall similarity due to author weight
        assert similarity.overall >= 0.50
        assert similarity.weights == custom_weights

    def test_find_best_matches(self):
        """Test finding best matches from candidate results."""
        target_entry = BibTeXEntry(
            {
                "ID": "target",
                "ENTRYTYPE": "article",
                "title": "Deep Learning for Computer Vision",
                "author": "John Smith",
                "year": "2023",
            }
        )

        # Create candidate results with varying similarity
        candidates = []

        # High similarity candidate
        high_sim_entry = BibTeXEntry(
            {
                "ID": "high",
                "ENTRYTYPE": "article",
                "title": "Deep Learning for Computer Vision",
                "author": "John Smith",
                "year": "2023",
            }
        )
        candidates.append(
            LookupResult(high_sim_entry, SourceMetadata("test_source", 0.5, 0.9))
        )

        # Medium similarity candidate
        med_sim_entry = BibTeXEntry(
            {
                "ID": "medium",
                "ENTRYTYPE": "article",
                "title": "Deep Learning Approaches",
                "author": "J. Smith",
                "year": "2023",
            }
        )
        candidates.append(
            LookupResult(med_sim_entry, SourceMetadata("test_source", 0.5, 0.9))
        )

        # Low similarity candidate
        low_sim_entry = BibTeXEntry(
            {
                "ID": "low",
                "ENTRYTYPE": "article",
                "title": "Quantum Computing",
                "author": "Jane Doe",
                "year": "2020",
            }
        )
        candidates.append(
            LookupResult(low_sim_entry, SourceMetadata("test_source", 0.5, 0.9))
        )

        matches = self.matcher.find_best_matches(
            target_entry, candidates, max_results=3
        )

        assert len(matches) == 3

        # Results should be sorted by similarity (descending)
        assert matches[0][1].overall >= matches[1][1].overall >= matches[2][1].overall

        # First match should be the high similarity one
        assert matches[0][0].entry.key == "high"
        assert matches[0][1].overall >= 0.90

    def test_confidence_levels(self):
        """Test confidence level classification."""
        # High confidence
        high_sim = SimilarityScore(
            overall=0.95,
            title_similarity=0.95,
            author_similarity=0.90,
            year_similarity=1.0,
            venue_similarity=0.90,
            weights={},
            details={},
        )

        assert self.matcher.is_high_confidence_match(high_sim)
        assert self.matcher.get_match_confidence_level(high_sim) == "high"

        # Medium confidence
        med_sim = SimilarityScore(
            overall=0.80,
            title_similarity=0.80,
            author_similarity=0.75,
            year_similarity=1.0,
            venue_similarity=0.70,
            weights={},
            details={},
        )

        assert self.matcher.is_probable_match(med_sim)
        assert not self.matcher.is_high_confidence_match(med_sim)
        assert self.matcher.get_match_confidence_level(med_sim) == "medium"

        # Low confidence
        low_sim = SimilarityScore(
            overall=0.65,
            title_similarity=0.60,
            author_similarity=0.50,
            year_similarity=0.8,
            venue_similarity=0.70,
            weights={},
            details={},
        )

        assert self.matcher.is_possible_match(low_sim)
        assert not self.matcher.is_probable_match(low_sim)
        assert self.matcher.get_match_confidence_level(low_sim) == "low"

        # Very low confidence
        very_low_sim = SimilarityScore(
            overall=0.30,
            title_similarity=0.30,
            author_similarity=0.20,
            year_similarity=0.0,
            venue_similarity=0.40,
            weights={},
            details={},
        )

        assert not self.matcher.is_possible_match(very_low_sim)
        assert self.matcher.get_match_confidence_level(very_low_sim) == "very_low"

    def test_normalize_title(self):
        """Test title normalization."""
        test_cases = [
            ("The Quick Brown Fox", "quick brown fox"),
            ("A Study on Machine Learning", "study on machine learning"),
            (
                "Deep Learning: Methods and Applications",
                "deep learning methods and applications",
            ),
            ("On the Theory of Everything", "theory of everything"),
        ]

        for input_title, expected in test_cases:
            normalized = self.matcher._normalize_title(input_title)
            assert normalized == expected

    def test_parse_authors(self):
        """Test author parsing."""
        test_cases = [
            ("John Smith and Jane Doe", ["John Smith", "Jane Doe"]),
            ("Smith, John and Doe, Jane", ["Smith, John", "Doe, Jane"]),
            ("John Smith", ["John Smith"]),
            (
                "A. Smith and B. Johnson and C. Williams",
                ["A. Smith", "B. Johnson", "C. Williams"],
            ),
        ]

        for input_authors, expected in test_cases:
            parsed = self.matcher._parse_authors(input_authors)
            assert parsed == expected

    def test_normalize_author_name(self):
        """Test author name normalization."""
        test_cases = [
            ("John Smith", "john smith"),
            ("Smith, John", "smith john"),
            ("J. Smith", "j smith"),
            ("Jean-Claude Van Damme", "jean claude van damme"),
        ]

        for input_name, expected in test_cases:
            normalized = self.matcher._normalize_author_name(input_name)
            assert normalized == expected

    def test_authors_partially_match(self):
        """Test partial author matching."""
        test_cases = [
            ("john smith", "j smith", True),
            ("jane doe", "j doe", True),
            ("john smith", "jane smith", False),
            ("a smith", "andrew smith", True),  # First name initial match
            ("smith", "j smith", False),  # Need both first and last
        ]

        for name1, name2, expected in test_cases:
            result = self.matcher._authors_partially_match(name1, name2)
            assert result == expected

    def test_global_matcher_singleton(self):
        """Test that global matcher returns the same instance."""
        matcher1 = get_fuzzy_matcher()
        matcher2 = get_fuzzy_matcher()

        assert matcher1 is matcher2
        assert isinstance(matcher1, FuzzyMatcher)

    def test_similarity_score_dataclass(self):
        """Test SimilarityScore dataclass functionality."""
        score = SimilarityScore(
            overall=0.85,
            title_similarity=0.90,
            author_similarity=0.80,
            year_similarity=1.0,
            venue_similarity=0.70,
            weights={"title": 0.4, "author": 0.3, "year": 0.15, "venue": 0.15},
            details={"test": "data"},
        )

        assert score.overall == 0.85
        assert score.title_similarity == 0.90
        assert score.author_similarity == 0.80
        assert score.year_similarity == 1.0
        assert score.venue_similarity == 0.70
        assert score.weights["title"] == 0.4
        assert score.details["test"] == "data"
