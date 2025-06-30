"""Tests for content validation rules."""

from src.reflint.core.entry import BibTeXEntry
from src.reflint.rules.content.brace_management import AdvancedBraceManagementRule
from src.reflint.rules.content.conditional_validation import ConditionalValidationRule


class TestAdvancedBraceManagementRule:
    """Test cases for advanced brace management rule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = AdvancedBraceManagementRule()

    def test_consolidate_consecutive_braces(self):
        """Test consolidation of consecutive single-letter braces."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "Study of {I}{E}{E}{E} Standards")

        violations = self.rule.validate(entry)
        assert len(violations) == 1
        assert "IEEE" in violations[0].message
        assert "{IEEE}" in violations[0].suggested_fix

    def test_protect_unbraced_words(self):
        """Test protection of unbraced protected words."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "Deep Learning with GPU Acceleration")

        violations = self.rule.validate(entry)
        assert len(violations) == 1
        assert "GPU" in violations[0].message
        assert "{GPU}" in violations[0].suggested_fix

    def test_already_protected_words(self):
        """Test that already protected words don't trigger violations."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "Deep Learning with {GPU} Acceleration")

        violations = self.rule.validate(entry)
        assert len(violations) == 0

    def test_remove_unnecessary_outer_braces(self):
        """Test removal of unnecessary outer braces."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "{Simple Title Without Special Terms}")

        violations = self.rule.validate(entry)
        assert len(violations) == 1
        assert "outer braces" in violations[0].message

    def test_keep_necessary_outer_braces(self):
        """Test that necessary outer braces are preserved."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "{GPU-Based Machine Learning}")

        violations = self.rule.validate(entry)
        # Should suggest protecting GPU but not removing outer braces
        gpu_violations = [
            v for v in violations if "GPU" in v.message and "outer" not in v.message
        ]
        outer_violations = [v for v in violations if "outer" in v.message]

        assert len(gpu_violations) == 0  # Already protected by outer braces
        assert (
            len(outer_violations) == 0
        )  # Should keep outer braces due to protected content

    def test_multiple_protected_words(self):
        """Test handling of multiple protected words."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "AI and ML for IoT Applications")

        violations = self.rule.validate(entry)
        assert len(violations) == 3  # AI, ML, IoT

        protected_words = {v.suggested_fix.split()[-1] for v in violations}
        assert "{AI}" in protected_words
        assert "{ML}" in protected_words
        assert "{IoT}" in protected_words

    def test_fix_method(self):
        """Test the automatic fix functionality."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "Study of {I}{E}{E}{E} and GPU Computing")

        fixed_entry = self.rule.fix(entry)
        fixed_title = fixed_entry.get_field("title")

        assert "{IEEE}" in fixed_title
        assert "{GPU}" in fixed_title
        assert "{I}{E}{E}{E}" not in fixed_title

    def test_different_field_types(self):
        """Test rule works on different field types."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "GPU Computing")
        entry.set_field("booktitle", "IEEE Conference")
        entry.set_field("journal", "ACM Transactions")

        violations = self.rule.validate(entry)

        # Should find violations in all three fields
        fields_with_violations = {v.field for v in violations}
        assert "title" in fields_with_violations
        assert "booktitle" in fields_with_violations
        assert "journal" in fields_with_violations

    def test_domain_specific_words(self):
        """Test various domain-specific protected words."""
        test_cases = [
            ("Physics paper about {Q}{E}{D}", "QED"),
            ("Biology study using PCR", "PCR"),
            ("Chemistry analysis with NMR", "NMR"),
            ("Math paper on FFT", "FFT"),
        ]

        for title, expected_word in test_cases:
            entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
            entry.set_field("title", title)

            violations = self.rule.validate(entry)
            violation_texts = [v.message for v in violations]

            # Should find the unprotected word
            assert any(expected_word in text for text in violation_texts)

    def test_balanced_braces_check(self):
        """Test balanced braces detection."""
        # This tests the internal method through the fix method
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "{Title with {nested} braces}")

        violations = self.rule.validate(entry)
        # Should not suggest removing outer braces due to nested content
        outer_violations = [v for v in violations if "outer" in v.message]
        assert len(outer_violations) == 0

    def test_case_sensitivity(self):
        """Test that rule is case-sensitive for protected words."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "gpu computing and ieee standards")  # lowercase

        violations = self.rule.validate(entry)
        # Should not protect lowercase versions
        assert len(violations) == 0


class TestConditionalValidationRule:
    """Test cases for conditional validation rule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = ConditionalValidationRule()

    def test_skip_issn_for_arxiv(self):
        """Test that ISSN validation is suggested to skip for arXiv papers."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("issn", "1234-5678")
        entry.set_field("arxivid", "2023.12345")

        violations = self.rule.validate(entry)
        issn_violations = [v for v in violations if v.field == "issn"]

        assert len(issn_violations) == 1
        assert "unnecessary" in issn_violations[0].message
        assert "arxivid" in issn_violations[0].message

    def test_skip_url_for_doi(self):
        """Test that URL validation is suggested to skip when DOI is present."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("url", "http://example.com")
        entry.set_field("doi", "10.1000/123456")

        violations = self.rule.validate(entry)
        url_violations = [v for v in violations if v.field == "url"]

        assert len(url_violations) == 1
        assert "unnecessary" in url_violations[0].message
        assert "doi" in url_violations[0].message

    def test_skip_publisher_for_preprints(self):
        """Test that publisher validation is suggested to skip for preprints."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("publisher", "IEEE")
        entry.set_field("eprint", "2023.12345")

        violations = self.rule.validate(entry)
        publisher_violations = [v for v in violations if v.field == "publisher"]

        assert len(publisher_violations) == 1
        assert "unnecessary" in publisher_violations[0].message
        assert "eprint" in publisher_violations[0].message

    def test_journal_booktitle_conflict(self):
        """Test detection of journal/booktitle field conflicts."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("journal", "Nature")
        entry.set_field("booktitle", "Some Conference")

        violations = self.rule.validate(entry)
        booktitle_violations = [v for v in violations if v.field == "booktitle"]

        assert len(booktitle_violations) == 1
        assert "unnecessary" in booktitle_violations[0].message

    def test_missing_conference_venue(self):
        """Test detection of missing venue for conference papers."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "inproceedings"})
        entry.set_field("title", "A Conference Paper")
        entry.set_field("author", "John Doe")

        violations = self.rule.validate(entry)
        venue_violations = [
            v for v in violations if "booktitle" in v.message and "journal" in v.message
        ]

        assert len(venue_violations) == 1
        assert all(v.severity == "warning" for v in venue_violations)

    def test_missing_journal_for_article(self):
        """Test detection of missing journal for articles."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "A Journal Article")
        entry.set_field("author", "Jane Doe")

        violations = self.rule.validate(entry)
        journal_violations = [
            v for v in violations if "journal" in v.message and "Article" in v.message
        ]

        assert len(journal_violations) == 1
        assert journal_violations[0].severity == "warning"

    def test_arxiv_article_no_journal_warning(self):
        """Test that arXiv articles don't trigger missing journal warning."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("title", "A Preprint")
        entry.set_field("author", "Jane Doe")
        entry.set_field("arxivid", "2023.12345")

        violations = self.rule.validate(entry)
        journal_violations = [
            v for v in violations if "journal" in v.message and "Article" in v.message
        ]

        assert len(journal_violations) == 0

    def test_missing_publisher_for_book(self):
        """Test detection of missing publisher for books."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "book"})
        entry.set_field("title", "A Book")
        entry.set_field("author", "Author Name")

        violations = self.rule.validate(entry)
        publisher_violations = [v for v in violations if "publisher" in v.message]

        assert len(publisher_violations) == 1
        assert publisher_violations[0].severity == "warning"

    def test_book_with_doi_no_publisher_warning(self):
        """Test that books with DOI don't trigger missing publisher warning."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "book"})
        entry.set_field("title", "A Book")
        entry.set_field("author", "Author Name")
        entry.set_field("doi", "10.1000/123456")

        violations = self.rule.validate(entry)
        publisher_violations = [v for v in violations if "publisher" in v.message]

        assert len(publisher_violations) == 0

    def test_should_skip_validation_static_method(self):
        """Test the static should_skip_validation method."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "article"})
        entry.set_field("doi", "10.1000/123456")

        should_skip, reason = ConditionalValidationRule.should_skip_validation(
            entry, "url"
        )

        assert should_skip is True
        assert "DOI" in reason

        # Test field that shouldn't be skipped
        should_skip, reason = ConditionalValidationRule.should_skip_validation(
            entry, "title"
        )

        assert should_skip is False
        assert reason == ""

    def test_volume_number_skip_for_books(self):
        """Test that volume/number validation is suggested to skip for books with ISBN."""
        entry = BibTeXEntry({"ID": "test", "ENTRYTYPE": "book"})
        entry.set_field("volume", "1")
        entry.set_field("number", "2")
        entry.set_field("isbn", "978-0123456789")

        violations = self.rule.validate(entry)
        volume_violations = [v for v in violations if v.field == "volume"]
        number_violations = [v for v in violations if v.field == "number"]

        assert len(volume_violations) == 1
        assert len(number_violations) == 1
        assert "book" in volume_violations[0].message
        assert "book" in number_violations[0].message
