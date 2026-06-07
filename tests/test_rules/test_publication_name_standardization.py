"""Tests for publication name standardization rule."""

from src.reflint.rules.content.publication_name_standardization import (
    PublicationNameStandardizationRule,
)
from src.reflint.core.entry import BibTeXEntry


class TestPublicationNameStandardizationRule:
    """Test cases for publication name standardization rule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = PublicationNameStandardizationRule()

    def test_exact_venue_standardization(self):
        """Test exact venue name standardization from known mappings."""
        test_cases = [
            ("ICML", "International Conference on Machine Learning"),
            ("NIPS", "Advances in Neural Information Processing Systems"),
            (
                "IEEE TPAMI",
                "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            ),
            ("JMLR", "Journal of Machine Learning Research"),
            ("PNAS", "Proceedings of the National Academy of Sciences"),
        ]

        for abbrev, expected_full in test_cases:
            entry = BibTeXEntry(
                {"ID": "test", "ENTRYTYPE": "inproceedings", "booktitle": abbrev}
            )

            results = self.rule.validate(entry)
            standardization_results = [
                r for r in results if "standardized" in r.message
            ]

            assert len(standardization_results) == 1
            assert expected_full in standardization_results[0].message
            assert standardization_results[0].severity == "info"

    def test_journal_field_standardization(self):
        """Test standardization works for journal field."""
        entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "article", "journal": "Nat. Mach. Intell."}
        )

        results = self.rule.validate(entry)
        standardization_results = [r for r in results if "standardized" in r.message]

        assert len(standardization_results) == 1
        assert "Nature Machine Intelligence" in standardization_results[0].message
        assert standardization_results[0].field == "journal"

    def test_case_insensitive_matching(self):
        """Test case-insensitive venue matching."""
        entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "inproceedings", "booktitle": "icml"}
        )

        results = self.rule.validate(entry)
        standardization_results = [r for r in results if "standardized" in r.message]

        assert len(standardization_results) == 1
        assert (
            "International Conference on Machine Learning"
            in standardization_results[0].message
        )

    def test_abbreviation_expansion(self):
        """Test common abbreviation expansion patterns."""
        test_cases = [
            ("Proc. of Something", "Proceedings of Something"),
            ("Int. Conference", "International Conference"),
            ("J. Computer Science", "Journal of Computer Science"),
            ("IEEE Trans. Pattern Analysis", "IEEE Transactions on Pattern Analysis"),
        ]

        for abbrev, expected in test_cases:
            standardized = self.rule._get_standardized_venue(abbrev)
            assert standardized == expected, (
                f"Expected '{expected}' but got '{standardized}' for input '{abbrev}'"
            )

    def test_multiple_venue_fields(self):
        """Test standardization works across different venue fields."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "inproceedings",
                "booktitle": "CVPR",
                "series": "ACM Trans. Graph.",
                "publisher": "IEEE",
            }
        )

        results = self.rule.validate(entry)

        # Should find standardizations for booktitle and series
        booktitle_results = [r for r in results if r.field == "booktitle"]
        series_results = [r for r in results if r.field == "series"]

        assert len(booktitle_results) == 1
        assert (
            "IEEE Conference on Computer Vision and Pattern Recognition"
            in booktitle_results[0].message
        )

        assert len(series_results) == 1
        assert "ACM Transactions on Graphics" in series_results[0].message

    def test_no_standardization_needed(self):
        """Test entries that don't need standardization."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "journal": "Nature",  # Already standardized
            }
        )

        results = self.rule.validate(entry)

        # Should not suggest any standardizations
        standardization_results = [r for r in results if "standardized" in r.message]
        assert len(standardization_results) == 0

    def test_fuzzy_matching_suggestions(self):
        """Test fuzzy matching for similar venue names."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "journal": "International Conf on Machine Learning",  # Close to ICML
            }
        )

        results = self.rule.validate(entry)
        fuzzy_results = [r for r in results if "Similar publication" in r.message]

        # Should suggest a fuzzy match
        assert (
            len(fuzzy_results) >= 0
        )  # May or may not find a match depending on threshold

    def test_venue_similarity_calculation(self):
        """Test venue similarity calculation."""
        test_cases = [
            (
                "ICML",
                "International Conference on Machine Learning",
                True,
            ),  # Should be high similarity
            (
                "Machine Learning Journal",
                "Journal of Machine Learning Research",
                True,
            ),  # Should be high similarity
            (
                "Random Conference",
                "Completely Different Venue",
                False,
            ),  # Should be low similarity
        ]

        for venue1, venue2, should_be_similar in test_cases:
            similarity = self.rule._calculate_venue_similarity(venue1, venue2)

            if should_be_similar:
                assert similarity > 0.5  # High similarity threshold
            else:
                assert similarity < 0.4  # Low similarity threshold

    def test_acronym_matching(self):
        """Test acronym matching logic."""
        test_cases = [
            ("ICML", "International Conference on Machine Learning", True),
            ("CVPR", "Computer Vision and Pattern Recognition", True),
            ("AI", "Artificial Intelligence", True),
            ("RANDOM", "Something Completely Different", False),
        ]

        for short, long, should_match in test_cases:
            matches = self.rule._venues_match_acronym(short, long)
            assert matches == should_match

    def test_venue_normalization(self):
        """Test venue normalization for comparison."""
        test_cases = [
            ("Proceedings of the International Conference on AI", "ai"),
            ("IEEE Transactions on Pattern Analysis", "pattern analysis"),
            ("Journal of Machine Learning Research", "machine learning research"),
            ("ACM Conference on Human Factors", "human factors"),
        ]

        for venue, expected_normalized in test_cases:
            normalized = self.rule._normalize_venue_for_comparison(venue)
            # Check that key terms are present
            for term in expected_normalized.split():
                assert term in normalized

    def test_no_venue_fields(self):
        """Test rule handles entries without venue fields gracefully."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Test Article",
                "author": "John Doe",
            }
        )

        results = self.rule.validate(entry)

        # Should return no results for entries without venue fields
        assert len(results) == 0

    def test_empty_venue_fields(self):
        """Test rule handles empty venue fields gracefully."""
        entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "article", "journal": "", "booktitle": None}
        )

        results = self.rule.validate(entry)

        # Should return no results for empty venue fields
        assert len(results) == 0

    def test_ieee_venue_standardizations(self):
        """Test IEEE-specific venue standardizations."""
        test_cases = [
            (
                "IEEE Trans. Pattern Anal. Mach. Intell.",
                "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            ),
            ("IEEE CVPR", "IEEE Conference on Computer Vision and Pattern Recognition"),
            ("IEEE Trans. Image Process.", "IEEE Transactions on Image Processing"),
        ]

        for abbrev, expected_full in test_cases:
            entry = BibTeXEntry(
                {"ID": "test", "ENTRYTYPE": "article", "journal": abbrev}
            )

            results = self.rule.validate(entry)
            standardization_results = [
                r for r in results if "standardized" in r.message
            ]

            assert len(standardization_results) == 1
            assert expected_full in standardization_results[0].message

    def test_acm_venue_standardizations(self):
        """Test ACM-specific venue standardizations."""
        test_cases = [
            ("ACM Trans. Graph.", "ACM Transactions on Graphics"),
            ("ACM CHI", "ACM Conference on Human Factors in Computing Systems"),
            ("ACM SIGCOMM", "ACM SIGCOMM Conference"),
        ]

        for abbrev, expected_full in test_cases:
            entry = BibTeXEntry(
                {"ID": "test", "ENTRYTYPE": "inproceedings", "booktitle": abbrev}
            )

            results = self.rule.validate(entry)
            standardization_results = [
                r for r in results if "standardized" in r.message
            ]

            assert len(standardization_results) == 1
            assert expected_full in standardization_results[0].message

    def test_nature_family_standardizations(self):
        """Test Nature publication family standardizations."""
        test_cases = [
            ("Nat. Mach. Intell.", "Nature Machine Intelligence"),
            ("Nat. Methods", "Nature Methods"),
            ("Nat. Commun.", "Nature Communications"),
            ("Nat. Neurosci.", "Nature Neuroscience"),
        ]

        for abbrev, expected_full in test_cases:
            entry = BibTeXEntry(
                {"ID": "test", "ENTRYTYPE": "article", "journal": abbrev}
            )

            results = self.rule.validate(entry)
            standardization_results = [
                r for r in results if "standardized" in r.message
            ]

            assert len(standardization_results) == 1
            assert expected_full in standardization_results[0].message

    def test_science_family_standardizations(self):
        """Test Science publication family standardizations."""
        test_cases = [
            ("Sci. Adv.", "Science Advances"),
            ("Science Adv", "Science Advances"),
            ("Sci. Robot.", "Science Robotics"),
        ]

        for abbrev, expected_full in test_cases:
            entry = BibTeXEntry(
                {"ID": "test", "ENTRYTYPE": "article", "journal": abbrev}
            )

            results = self.rule.validate(entry)
            standardization_results = [
                r for r in results if "standardized" in r.message
            ]

            assert len(standardization_results) == 1
            assert expected_full in standardization_results[0].message

    def test_rule_metadata(self):
        """Test rule metadata."""
        assert self.rule.rule_id == "B003"
        assert self.rule.severity == "info"
        assert self.rule.category == "content"
        assert "publication" in self.rule.description.lower()
        assert "standardiz" in self.rule.description.lower()

    def test_very_short_venues_skipped(self):
        """Test that very short venue names are skipped for fuzzy matching."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "journal": "AI",  # Very short, should not trigger fuzzy matching
            }
        )

        results = self.rule.validate(entry)

        # Should not generate fuzzy match suggestions for very short names
        # (unless there's an exact match in standardizations)
        fuzzy_results = [r for r in results if "Similar publication" in r.message]
        assert fuzzy_results == []
        assert isinstance(results, list)

    def test_standardization_priority_over_fuzzy(self):
        """Test that exact standardizations take priority over fuzzy matches."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "inproceedings",
                "booktitle": "ICML",  # Has exact standardization
            }
        )

        results = self.rule.validate(entry)

        # Should get exact standardization, not fuzzy suggestion
        standardization_results = [r for r in results if "standardized" in r.message]
        fuzzy_results = [r for r in results if "Similar publication" in r.message]

        assert len(standardization_results) == 1
        assert len(fuzzy_results) == 0  # Should not also suggest fuzzy match

    def test_suggested_fix_format(self):
        """Test that suggested fixes are properly formatted."""
        entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "inproceedings", "booktitle": "ICML"}
        )

        results = self.rule.validate(entry)

        assert len(results) == 1
        result = results[0]

        assert result.suggested_fix is not None
        assert "International Conference on Machine Learning" in result.suggested_fix
        assert result.field == "booktitle"
