"""Tests for advanced date validation rule."""

from src.reflint.rules.basic.date_validation import DateValidationRule
from src.reflint.core.entry import BibTeXEntry


class TestAdvancedDateValidationRule:
    """Test cases for advanced date validation rule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = DateValidationRule()

    def test_valid_dates(self):
        """Test entries with valid dates."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "2023",
                "month": "6",
                "day": "15",
            }
        )

        results = self.rule.validate(entry)
        # Should have no violations - all fields are valid and month is already numeric
        assert len(results) == 0

    def test_year_range_validation(self):
        """Test year range validation with different probability levels."""
        test_cases = [
            ("2030", "error", "future"),  # Future year
            ("1850", "warning", "quite old"),  # Very old
            ("1950", "info", "quite old"),  # Old but not ancient
            ("1990", "info", "somewhat old"),  # Somewhat old
            ("2010", 0, None),  # Good range (no violations except normalization)
        ]

        for year, expected_severity, expected_message_part in test_cases:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "year": year,
                    "month": "january",
                }
            )

            results = self.rule.validate(entry)
            
            if expected_severity == 0:
                # Should only have month normalization suggestion
                year_violations = [r for r in results if r.field == "year"]
                assert len(year_violations) == 0
            else:
                year_violations = [r for r in results if r.field == "year"]
                assert len(year_violations) == 1
                assert year_violations[0].severity == expected_severity
                assert expected_message_part in year_violations[0].message

    def test_invalid_year_format(self):
        """Test invalid year formats."""
        test_cases = [
            "23",  # Too short
            "202x",  # Non-numeric
            "two thousand twenty three",  # Text
            "",  # Empty
        ]

        for invalid_year in test_cases:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "year": invalid_year,
                }
            )

            results = self.rule.validate(entry)
            year_violations = [r for r in results if r.field == "year"]
            assert len(year_violations) == 1
            assert "4-digit number" in year_violations[0].message

    def test_month_validation(self):
        """Test month field validation."""
        valid_months = [
            "1", "01", "12",  # Numeric
            "January", "Feb", "march",  # Name variants
            "JAN", "feb", "DEC",  # Case variants
        ]

        for month in valid_months:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "year": "2023",
                    "month": month,
                }
            )

            results = self.rule.validate(entry)
            month_violations = [r for r in results if r.field == "month" and r.severity != "info"]
            assert len(month_violations) == 0

    def test_invalid_month_format(self):
        """Test invalid month formats."""
        invalid_months = [
            "13",  # Invalid number
            "0",   # Invalid number
            "Janurary",  # Misspelled
            "Month1",  # Invalid format
        ]

        for invalid_month in invalid_months:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "year": "2023",
                    "month": invalid_month,
                }
            )

            results = self.rule.validate(entry)
            month_violations = [r for r in results if r.field == "month" and r.severity != "info"]
            assert len(month_violations) == 1
            assert "Invalid month format" in month_violations[0].message

    def test_day_validation(self):
        """Test day field validation."""
        valid_days = ["1", "15", "31"]
        
        for day in valid_days:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "year": "2023",
                    "month": "1",
                    "day": day,
                }
            )

            results = self.rule.validate(entry)
            day_violations = [r for r in results if r.field == "day"]
            assert len(day_violations) == 0

    def test_invalid_day_format(self):
        """Test invalid day formats."""
        invalid_days = [
            "32",  # Too high
            "0",   # Too low
            "day1",  # Invalid format
            "first",  # Text
        ]

        for invalid_day in invalid_days:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    "year": "2023",
                    "month": "1",
                    "day": invalid_day,
                }
            )

            results = self.rule.validate(entry)
            day_violations = [r for r in results if r.field == "day"]
            assert len(day_violations) == 1

    def test_date_coherence_validation(self):
        """Test coherence validation between date fields."""
        # Test leap year
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "2024",  # Leap year
                "month": "2",
                "day": "29",  # Valid in leap year
            }
        )

        results = self.rule.validate(entry)
        day_violations = [r for r in results if r.field == "day"]
        assert len(day_violations) == 0

        # Test non-leap year
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "2023",  # Non-leap year
                "month": "2",
                "day": "29",  # Invalid in non-leap year
            }
        )

        results = self.rule.validate(entry)
        day_violations = [r for r in results if r.field == "day"]
        assert len(day_violations) == 1
        assert "invalid for month 2 in year 2023" in day_violations[0].message

    def test_february_edge_cases(self):
        """Test February date edge cases."""
        # February 30th (always invalid)
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "2023",
                "month": "2",
                "day": "30",
            }
        )

        results = self.rule.validate(entry)
        day_violations = [r for r in results if r.field == "day"]
        assert len(day_violations) == 1
        assert "max: 28" in day_violations[0].message

    def test_month_normalization_suggestions(self):
        """Test month normalization suggestions."""
        # Test that numeric months don't get normalization suggestions
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "2023",
                "month": "6",
            }
        )

        results = self.rule.validate(entry)
        normalization_suggestions = [r for r in results if "normalizing month" in r.message]
        assert len(normalization_suggestions) == 0

        # Test that named months get normalization suggestions
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "2023",
                "month": "June",
            }
        )

        results = self.rule.validate(entry)
        normalization_suggestions = [r for r in results if "normalizing month" in r.message]
        assert len(normalization_suggestions) == 1
        assert normalization_suggestions[0].suggested_fix == "6"

    def test_future_date_detection(self):
        """Test detection of future dates."""
        # Create a future date
        import datetime
        future_year = datetime.datetime.now().year + 1
        
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": str(future_year),
                "month": "6",
                "day": "15",
            }
        )

        results = self.rule.validate(entry)
        future_violations = [r for r in results if "future" in r.message]
        assert len(future_violations) >= 1  # Could be both year and full date

    def test_bibtex_formatting_handling(self):
        """Test handling of BibTeX formatting like braces."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "{2023}",
                "month": "{June}",
                "day": "{15}",
            }
        )

        results = self.rule.validate(entry)
        
        # Should parse correctly despite braces
        year_violations = [r for r in results if r.field == "year" and r.severity != "info"]
        assert len(year_violations) == 0
        
        month_violations = [r for r in results if r.field == "month" and r.severity != "info"]
        assert len(month_violations) == 0
        
        day_violations = [r for r in results if r.field == "day"]
        assert len(day_violations) == 0

    def test_mixed_field_scenarios(self):
        """Test scenarios with various combinations of date fields."""
        # Only year
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "2023",
            }
        )

        results = self.rule.validate(entry)
        # Should not have coherence violations with only year
        coherence_violations = [r for r in results if "invalid for month" in r.message]
        assert len(coherence_violations) == 0

        # Year and month only
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "year": "2023",
                "month": "February",
            }
        )

        results = self.rule.validate(entry)
        # Should not have day-related coherence violations
        day_coherence_violations = [r for r in results if r.field == "day"]
        assert len(day_coherence_violations) == 0

    def test_rule_metadata(self):
        """Test rule metadata."""
        assert self.rule.rule_id == "D001"
        assert self.rule.severity == "warning"
        assert self.rule.category == "content"
        assert "coherence checking" in self.rule.description.lower()
        assert self.rule.can_fix() is True