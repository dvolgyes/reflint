"""Tests for journal-ISSN validation rule."""

from src.reflint.rules.content.journal_issn_validation import JournalIssnValidationRule
from src.reflint.core.entry import BibTeXEntry


class TestJournalIssnValidationRule:
    """Test cases for journal-ISSN validation rule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = JournalIssnValidationRule()

    def test_valid_journal_issn_pair(self):
        """Test validation passes for valid journal-ISSN pairs."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "journal": "Nature",
                "issn": "0028-0836",
            }
        )

        results = self.rule.validate(entry)

        # Should not have any error-level issues
        errors = [r for r in results if r.severity == "error"]
        assert len(errors) == 0

    def test_journal_name_standardization(self):
        """Test journal name standardization suggestions."""
        entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "article", "journal": "IEEE TPAMI"}
        )

        results = self.rule.validate(entry)

        # Should suggest standardization
        standardization_results = [r for r in results if "standardized" in r.message]
        assert len(standardization_results) == 1
        assert (
            "IEEE Transactions on Pattern Analysis and Machine Intelligence"
            in standardization_results[0].message
        )

    def test_abbreviation_expansion(self):
        """Test common abbreviation expansion."""
        test_cases = [
            (
                "IEEE Trans. Pattern Anal. Mach. Intell.",
                "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            ),
            ("Nat. Mach. Intell.", "Nature Machine Intelligence"),
            ("ACM Trans. Graph.", "ACM Transactions on Graphics"),
            ("Sci. Adv.", "Science Advances"),
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

    def test_invalid_issn_format(self):
        """Test detection of invalid ISSN formats."""
        invalid_issns = [
            "1234567",  # Too short
            "1234-567",  # Wrong format
            "12345678",  # No hyphen
            "1234-56789",  # Too long
            "abcd-1234",  # Non-numeric characters
        ]

        for invalid_issn in invalid_issns:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "journal": "Test Journal",
                    "issn": invalid_issn,
                }
            )

            results = self.rule.validate(entry)
            format_errors = [r for r in results if "Invalid ISSN format" in r.message]

            assert len(format_errors) == 1
            assert format_errors[0].severity == "warning"

    def test_valid_issn_formats(self):
        """Test validation passes for valid ISSN formats."""
        valid_issns = [
            "0028-0836",  # Nature
            "2375-2548",  # Science Advances
            "1234-567X",  # Valid with X check digit
        ]

        for valid_issn in valid_issns:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "journal": "Test Journal",
                    "issn": valid_issn,
                }
            )

            results = self.rule.validate(entry)
            format_errors = [r for r in results if "Invalid ISSN format" in r.message]

            assert len(format_errors) == 0

    def test_issn_checksum_validation(self):
        """Test ISSN check digit validation."""
        # Valid ISSNs (real examples)
        valid_issns = [
            "0028-0836",  # Nature
            "0036-8075",  # Science
            "2375-2548",  # Science Advances
        ]

        for valid_issn in valid_issns:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "journal": "Test Journal",
                    "issn": valid_issn,
                }
            )

            results = self.rule.validate(entry)
            checksum_errors = [
                r for r in results if "check digit validation failed" in r.message
            ]

            assert len(checksum_errors) == 0

    def test_cross_validation_mismatch(self):
        """Test cross-validation detects journal-ISSN mismatches."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "journal": "Nature",
                "issn": "0036-8075",  # Science ISSN, not Nature
            }
        )

        results = self.rule.validate(entry)
        mismatch_errors = [r for r in results if "belongs to" in r.message]

        assert len(mismatch_errors) == 1
        assert mismatch_errors[0].severity == "error"
        assert "Science" in mismatch_errors[0].message

    def test_missing_issn_suggestion(self):
        """Test suggestion of missing ISSN for known journals."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article", "journal": "Nature"})

        results = self.rule.validate(entry)
        missing_issn = [r for r in results if "Missing ISSN" in r.message]

        assert len(missing_issn) == 1
        assert missing_issn[0].severity == "info"
        assert (
            "0028-0836" in missing_issn[0].suggested_fix
            or "1476-4687" in missing_issn[0].suggested_fix
        )

    def test_no_journal_field(self):
        """Test rule handles missing journal field gracefully."""
        entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "article", "title": "Test Article"}
        )

        results = self.rule.validate(entry)

        # Should return empty results for entries without journal field
        assert len(results) == 0

    def test_case_insensitive_matching(self):
        """Test case-insensitive journal name matching."""
        entry = BibTeXEntry(
            {"ID": "test", "ENTRYTYPE": "article", "journal": "ieee tpami"}
        )

        results = self.rule.validate(entry)
        standardization_results = [r for r in results if "standardized" in r.message]

        assert len(standardization_results) == 1
        assert (
            "IEEE Transactions on Pattern Analysis and Machine Intelligence"
            in standardization_results[0].message
        )

    def test_multiple_known_issns(self):
        """Test handling of journals with multiple known ISSNs."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "journal": "Nature",
                "issn": "1476-4687",  # Online ISSN for Nature
            }
        )

        results = self.rule.validate(entry)

        # Should not report cross-validation error for valid alternative ISSN
        mismatch_errors = [
            r for r in results if "does not match known ISSNs" in r.message
        ]
        assert len(mismatch_errors) == 0

    def test_generic_abbreviation_expansion(self):
        """Test generic abbreviation expansion rules."""
        test_cases = [
            ("Proc. Something", "Proceedings of Something"),
            ("J. Something", "Journal of Something"),
            ("Trans. Something", "Transactions on Something"),
            ("Int. Something", "International Something"),
        ]

        for abbrev, expected in test_cases:
            normalized = self.rule._normalize_journal_name(abbrev)
            assert normalized == expected

    def test_issn_format_cleaning(self):
        """Test ISSN format cleaning and validation."""
        test_cases = [
            ("0028-0836", True),  # Standard format
            ("0028 0836", False),  # Space instead of hyphen
            ("ISSN 0028-0836", True),  # With prefix - should be cleaned and valid
            ("0028-0836.", False),  # With period
        ]

        for issn_input, should_be_valid in test_cases:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "journal": "Test Journal",
                    "issn": issn_input,
                }
            )

            results = self.rule.validate(entry)
            format_errors = [r for r in results if "Invalid ISSN format" in r.message]

            if should_be_valid:
                assert len(format_errors) == 0, (
                    f"Expected no format errors for '{issn_input}', got: {[r.message for r in format_errors]}"
                )
            else:
                assert len(format_errors) == 1, (
                    f"Expected 1 format error for '{issn_input}', got: {len(format_errors)} errors: {[r.message for r in format_errors]}"
                )

    def test_rule_metadata(self):
        """Test rule metadata."""
        assert self.rule.rule_id == "B002"
        assert self.rule.severity == "warning"
        assert self.rule.category == "content"
        assert "journal" in self.rule.description.lower()
        assert "issn" in self.rule.description.lower()

    def test_issn_checksum_algorithm(self):
        """Test ISSN checksum validation algorithm directly."""
        # Test known valid ISSNs
        valid_tests = [
            "0028-0836",  # Nature
            "2375-2548",  # Science Advances
            "0378-2166",  # Journal of Pragmatics (ends with X)
        ]

        for issn in valid_tests:
            assert self.rule._validate_issn_checksum(issn)

        # Test invalid checksums
        invalid_tests = [
            "0028-0837",  # Wrong check digit
            "2375-2549",  # Wrong check digit
        ]

        for issn in invalid_tests:
            assert not self.rule._validate_issn_checksum(issn)

    def test_unknown_journal_no_false_positives(self):
        """Test that unknown journals don't generate false positive suggestions."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "journal": "Obscure Unknown Journal",
                "issn": "1234-5678",
            }
        )

        results = self.rule.validate(entry)

        # Should only validate ISSN format, not generate cross-validation errors
        cross_validation_errors = [
            r for r in results if "does not match known ISSNs" in r.message
        ]
        assert len(cross_validation_errors) == 0
