"""Page formatting validation rule (P001)."""

import re

from ..base import FieldValidationRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation


class PageFormattingRule(FieldValidationRule):
    """Rule P001: Validate page range formatting."""

    rule_id = "P001"
    severity = "warning"
    category = "formatting"
    description = "Page ranges should use en-dash (--) and be properly formatted"

    def __init__(self) -> None:
        super().__init__("pages")

    def validate_field(
        self, entry: BibTeXEntry, field_value: str
    ) -> list[RuleViolation]:
        """Validate page field formatting."""
        violations: list[RuleViolation] = []

        # Remove common BibTeX formatting
        pages_clean = field_value.strip("{}").strip()

        # Check for page ranges
        if self._is_page_range(pages_clean):
            violations.extend(self._validate_page_range(pages_clean))
        else:
            violations.extend(self._validate_single_page(pages_clean))

        return violations

    def _is_page_range(self, pages: str) -> bool:
        """Check if pages field contains a range."""
        # Look for common range indicators
        range_patterns = [r"-+", r"–", r"—", r"to", r"through"]
        for pattern in range_patterns:
            if re.search(pattern, pages, re.IGNORECASE):
                return True
        return False

    def _validate_page_range(self, pages: str) -> list[RuleViolation]:
        """Validate page range formatting."""
        violations: list[RuleViolation] = []

        # Check for proper en-dash usage
        if "--" not in pages:
            if "-" in pages and not re.search(r"[–—]", pages):
                # Single hyphen used instead of en-dash
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        message="Page ranges should use en-dash (--) not hyphen (-)",
                        field="pages",
                        suggested_fix=pages.replace("-", "--"),
                    )
                )
            elif "to" in pages.lower() or "through" in pages.lower():
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        severity="info",
                        message="Consider using en-dash (--) instead of 'to' for page ranges",
                        field="pages",
                    )
                )

        # Extract page numbers for validation
        page_match = re.search(r"(\d+)\s*--\s*(\d+)", pages)
        if page_match:
            start_page = int(page_match.group(1))
            end_page = int(page_match.group(2))

            if start_page >= end_page:
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        severity="error",
                        message=f"Start page ({start_page}) should be less than end page ({end_page})",
                        field="pages",
                    )
                )

            # Check for excessive page range (might indicate error)
            if end_page - start_page > 1000:
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        severity="warning",
                        message=f"Very large page range ({end_page - start_page + 1} pages) - please verify",
                        field="pages",
                    )
                )

        return violations

    def _validate_single_page(self, pages: str) -> list[RuleViolation]:
        """Validate single page formatting."""
        violations: list[RuleViolation] = []

        # Check if it's a valid page number or range
        if not re.match(r"^[\d\s,\-–—]+$", pages):
            # Contains non-numeric characters (excluding common separators)
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="info",
                    message=f"Pages field contains non-standard characters: '{pages}'",
                    field="pages",
                )
            )

        # Check for multiple single pages (should probably be a range)
        comma_separated = pages.split(",")
        if len(comma_separated) > 3:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="info",
                    message="Multiple comma-separated pages - consider using a range if consecutive",
                    field="pages",
                )
            )

        return violations

    def can_fix(self) -> bool:
        """This rule can fix some page formatting issues."""
        return True

    def fix(self, entry: BibTeXEntry) -> BibTeXEntry:
        """Fix page formatting issues."""
        if not entry.has_field("pages"):
            return entry

        pages_value = entry.get_field("pages")
        if not pages_value:
            return entry

        # Fix single hyphen to en-dash
        fixed_pages = pages_value.replace(" - ", " -- ").replace("-", "--")

        # Remove multiple consecutive dashes
        fixed_pages = re.sub(r"--+", "--", fixed_pages)

        # Clean up spacing around en-dashes
        fixed_pages = re.sub(r"\s*--\s*", "--", fixed_pages)

        if fixed_pages != pages_value:
            entry.set_field("pages", fixed_pages)

        return entry
