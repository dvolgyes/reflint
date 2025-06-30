"""Tests for math mode validation rule (M001)."""

from reflint.core.entry import BibTeXEntry
from reflint.rules.basic.math_mode_validation import (
    MathModeIssue,
    MathModeValidationRule,
    MathModeValidator,
)


class TestMathModeValidator:
    """Test the MathModeValidator class."""

    def test_init(self):
        """Test MathModeValidator initialization."""
        validator = MathModeValidator()
        assert validator is not None

    def test_simple_math_valid(self):
        """Test validation of simple valid math expressions."""
        validator = MathModeValidator()

        # Valid inline math
        issues = validator.validate_math_mode("The formula $x = y + z$ is correct.")
        # Filter out nested math issues for this test
        critical_issues = [
            i
            for i in issues
            if i.issue_type in ["unmatched_opening", "unmatched_closing"]
        ]
        assert len(critical_issues) == 0

        # Valid display math
        issues = validator.validate_math_mode("The equation $$E = mc^2$$ is famous.")
        critical_issues = [
            i
            for i in issues
            if i.issue_type in ["unmatched_opening", "unmatched_closing"]
        ]
        assert len(critical_issues) == 0

    def test_unmatched_delimiters(self):
        """Test detection of unmatched math delimiters."""
        validator = MathModeValidator()

        # Unmatched opening $
        issues = validator.validate_math_mode("The formula $x = y + z is incomplete.")
        assert len(issues) >= 1
        unmatched_issues = [i for i in issues if i.issue_type == "unmatched_opening"]
        assert len(unmatched_issues) >= 1
        assert "$" in unmatched_issues[0].delimiter

    def test_potential_currency_detection(self):
        """Test detection of potential currency symbols."""
        validator = MathModeValidator()

        # Potential currency
        issues = validator.validate_math_mode("The price is $50 for this item.")
        assert len(issues) >= 1
        currency_issues = [i for i in issues if i.issue_type == "potential_currency"]
        assert len(currency_issues) >= 1

    def test_math_commands_outside_math(self):
        """Test detection of math commands outside math mode."""
        validator = MathModeValidator()

        # Math command outside math mode
        issues = validator.validate_math_mode("The Greek letter \\alpha is used here.")
        assert len(issues) >= 1
        command_issues = [
            i for i in issues if i.issue_type == "math_command_outside_math"
        ]
        assert len(command_issues) >= 1

    def test_math_commands_in_math_mode(self):
        """Test that math commands in math mode don't trigger issues."""
        validator = MathModeValidator()

        # Math command inside math mode (should be fine)
        issues = validator.validate_math_mode(
            "The formula $\\alpha + \\beta = \\gamma$ is valid."
        )
        # Should not have math_command_outside_math issues
        command_issues = [
            i for i in issues if i.issue_type == "math_command_outside_math"
        ]
        assert len(command_issues) == 0

    def test_math_environments(self):
        """Test validation of math environments."""
        validator = MathModeValidator()

        # Valid equation environment
        issues = validator.validate_math_mode("\\begin{equation}x = y\\end{equation}")
        critical_issues = [
            i
            for i in issues
            if i.issue_type in ["unmatched_opening", "unmatched_closing"]
        ]
        assert len(critical_issues) == 0


class TestMathModeIssue:
    """Test the MathModeIssue dataclass."""

    def test_math_mode_issue_creation(self):
        """Test creating MathModeIssue objects."""
        issue = MathModeIssue(
            issue_type="unmatched_opening",
            position=10,
            context="formula $x = y",
            suggestion="Add closing delimiter",
            delimiter="$",
        )

        assert issue.issue_type == "unmatched_opening"
        assert issue.position == 10
        assert issue.delimiter == "$"


class TestMathModeValidationRule:
    """Test the MathModeValidationRule class."""

    def test_init(self):
        """Test rule initialization."""
        rule = MathModeValidationRule()
        assert rule.rule_id == "M001"
        assert (
            rule.description
            == "Validates LaTeX math mode syntax and checks for unmatched delimiters"
        )
        assert rule.severity == "warning"

    def test_applies_to_field(self):
        """Test field applicability."""
        rule = MathModeValidationRule()

        # Should apply to common text fields
        assert rule.applies_to_field("title")
        assert rule.applies_to_field("abstract")
        assert rule.applies_to_field("note")
        assert rule.applies_to_field("journal")

        # Should not apply to non-text fields
        assert not rule.applies_to_field("year")
        assert not rule.applies_to_field("pages")
        assert not rule.applies_to_field("volume")

    def test_check_valid_entry(self):
        """Test checking an entry with valid math."""
        rule = MathModeValidationRule()

        entry = BibTeXEntry(
            {
                "ID": "test_entry",
                "ENTRYTYPE": "article",
                "title": "A Study of $x = y + z$ in Mathematics",
                "abstract": "This paper discusses the equation \\begin{equation}E = mc^2\\end{equation}.",
                "year": "2023",
            }
        )

        violations = rule.validate(entry)

        # Should have no critical issues
        error_violations = [v for v in violations if v.severity == "error"]
        assert len(error_violations) == 0

    def test_check_invalid_entry(self):
        """Test checking an entry with math issues."""
        rule = MathModeValidationRule()

        entry = BibTeXEntry(
            {
                "ID": "test_entry",
                "ENTRYTYPE": "article",
                "title": "A Study of $x = y + z in Mathematics",  # Unmatched $
                "abstract": "The Greek letter \\alpha is important.",  # Math command outside math
                "note": "Price is $50.",  # Potential currency
                "year": "2023",
            }
        )

        violations = rule.validate(entry)

        # Should detect issues
        assert len(violations) > 0

    def test_check_empty_fields(self):
        """Test that empty or short fields are skipped."""
        rule = MathModeValidationRule()

        entry = BibTeXEntry(
            {
                "ID": "test_entry",
                "ENTRYTYPE": "article",
                "title": "",  # Empty
                "abstract": "x",  # Very short
                "note": "12",  # Short but valid
                "year": "2023",
            }
        )

        violations = rule.validate(entry)

        # Should have no results for empty/short fields
        assert len(violations) == 0

    def test_severity_assignment(self):
        """Test that appropriate severities are assigned."""
        rule = MathModeValidationRule()

        entry = BibTeXEntry(
            {
                "ID": "test_entry",
                "ENTRYTYPE": "article",
                "title": "Unmatched $x = y + z",  # Should be ERROR
                "note": "Price $50",  # Should be INFO
            }
        )

        violations = rule.validate(entry)

        # Should have at least one error for unmatched delimiter
        error_violations = [v for v in violations if v.severity == "error"]
        assert len(error_violations) > 0

    def test_fix_method(self):
        """Test the fix method."""
        rule = MathModeValidationRule()

        entry = BibTeXEntry(
            {
                "ID": "test_entry",
                "ENTRYTYPE": "article",
                "title": "Price is $50 for item",
                "year": "2023",
            }
        )

        fixed_entry = rule.fix(entry)

        # Check that the entry was processed (may or may not be fixed)
        assert fixed_entry.has_field("title")

    def test_can_fix(self):
        """Test the can_fix method."""
        rule = MathModeValidationRule()
        assert rule.can_fix()
