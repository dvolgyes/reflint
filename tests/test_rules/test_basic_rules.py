"""Tests for basic validation rules."""

from reflint.core.entry import BibTeXEntry
from reflint.rules.basic.mandatory_fields import MandatoryFieldsRule
from reflint.rules.basic.date_validation import DateValidationRule
from reflint.rules.basic.page_formatting import PageFormattingRule
from reflint.rules.basic.url_validation import URLValidationRule


class TestMandatoryFieldsRule:
    """Test the mandatory fields rule."""

    def test_valid_article(self):
        """Test valid article entry."""
        rule = MandatoryFieldsRule()
        entry_dict = {
            "ID": "test_article",
            "ENTRYTYPE": "article",
            "author": "John Doe",
            "title": "Test Article",
            "journal": "Test Journal",
            "year": "2023",
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 0

    def test_missing_required_field(self):
        """Test article missing required field."""
        rule = MandatoryFieldsRule()
        entry_dict = {
            "ID": "test_article",
            "ENTRYTYPE": "article",
            "author": "John Doe",
            "title": "Test Article",
            # Missing journal and year
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 2  # Missing journal and year
        assert any(v.message.endswith("'journal'") for v in violations)
        assert any(v.message.endswith("'year'") for v in violations)

    def test_alternative_fields(self):
        """Test entry with alternative required fields."""
        rule = MandatoryFieldsRule()
        entry_dict = {
            "ID": "test_book",
            "ENTRYTYPE": "book",
            "editor": "Jane Smith",  # Alternative to author
            "title": "Test Book",
            "publisher": "Test Publisher",
            "year": "2023",
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 0


class TestDateValidationRule:
    """Test the date validation rule."""

    def test_valid_year(self):
        """Test valid year format."""
        rule = DateValidationRule()
        entry_dict = {"ID": "test_entry", "ENTRYTYPE": "article", "year": "2023"}
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 0

    def test_invalid_year_format(self):
        """Test invalid year format."""
        rule = DateValidationRule()
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "year": "23",  # Invalid 2-digit year
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 1
        assert "4-digit number" in violations[0].message

    def test_valid_month(self):
        """Test valid month formats."""
        rule = DateValidationRule()
        for month in ["January", "jan", "1", "01"]:
            entry_dict = {"ID": "test_entry", "ENTRYTYPE": "article", "month": month}
            entry = BibTeXEntry(entry_dict)

            violations = rule.validate(entry)
            assert len(violations) == 0, f"Month '{month}' should be valid"

    def test_invalid_month(self):
        """Test invalid month format."""
        rule = DateValidationRule()
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "month": "invalid_month",
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 1
        assert "Invalid month format" in violations[0].message


class TestPageFormattingRule:
    """Test the page formatting rule."""

    def test_valid_page_range(self):
        """Test valid page range with en-dash."""
        rule = PageFormattingRule()
        entry_dict = {"ID": "test_entry", "ENTRYTYPE": "article", "pages": "123--456"}
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 0

    def test_hyphen_instead_of_endash(self):
        """Test page range with hyphen instead of en-dash."""
        rule = PageFormattingRule()
        entry_dict = {"ID": "test_entry", "ENTRYTYPE": "article", "pages": "123-456"}
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 1
        assert "en-dash (--)" in violations[0].message

    def test_invalid_page_range(self):
        """Test invalid page range (start > end)."""
        rule = PageFormattingRule()
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "pages": "456--123",  # Invalid range
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 1
        assert "should be less than" in violations[0].message

    def test_fix_page_formatting(self):
        """Test automatic fix of page formatting."""
        rule = PageFormattingRule()
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "pages": "123-456",  # Will be fixed to 123--456
        }
        entry = BibTeXEntry(entry_dict)

        fixed_entry = rule.fix(entry)
        assert fixed_entry.get_field("pages") == "123--456"


class TestURLValidationRule:
    """Test the URL validation rule."""

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        rule = URLValidationRule()
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "misc",
            "url": "https://example.com",
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 0

    def test_http_url_warning(self):
        """Test HTTP URL generates info warning."""
        rule = URLValidationRule()
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "misc",
            "url": "http://example.com",
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 1
        assert violations[0].severity == "info"
        assert "HTTPS" in violations[0].message

    def test_missing_protocol(self):
        """Test URL missing protocol."""
        rule = URLValidationRule()
        entry_dict = {"ID": "test_entry", "ENTRYTYPE": "misc", "url": "example.com"}
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 1
        assert "missing protocol" in violations[0].message

    def test_url_shortener_warning(self):
        """Test URL shortener warning."""
        rule = URLValidationRule()
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "misc",
            "url": "https://bit.ly/abc123",
        }
        entry = BibTeXEntry(entry_dict)

        violations = rule.validate(entry)
        assert len(violations) == 1
        assert "shortener" in violations[0].message

    def test_fix_url_missing_protocol(self):
        """Test automatic fix of URL missing protocol."""
        rule = URLValidationRule()
        entry_dict = {"ID": "test_entry", "ENTRYTYPE": "misc", "url": "example.com"}
        entry = BibTeXEntry(entry_dict)

        fixed_entry = rule.fix(entry)
        assert fixed_entry.get_field("url") == "https://example.com"
