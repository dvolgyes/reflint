"""Date validation rule (D001)."""

import re
from calendar import monthrange

from ..base import FieldValidationRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation


class DateValidationRule(FieldValidationRule):
    """Rule D001: Validate date fields (year, month, day)."""

    rule_id = "D001"
    severity = "warning"
    category = "content"
    description = "Date fields must be properly formatted and valid"

    def __init__(self) -> None:
        super().__init__("year")  # Primary field to check

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate date-related fields."""
        violations: list[RuleViolation] = []

        # Validate year field
        if entry.has_field("year"):
            year_value = entry.get_field("year")
            if year_value:
                violations.extend(self._validate_year(year_value))

        # Validate month field
        if entry.has_field("month"):
            month_value = entry.get_field("month")
            if month_value:
                violations.extend(self._validate_month(month_value))

        # Validate day field (less common)
        if entry.has_field("day"):
            day_value = entry.get_field("day")
            year_value = entry.get_field("year")
            month_value = entry.get_field("month")
            if day_value:
                violations.extend(
                    self._validate_day(day_value, year_value, month_value)
                )

        return violations

    def validate_field(
        self, entry: BibTeXEntry, field_value: str
    ) -> list[RuleViolation]:
        """Required by parent class - delegates to main validate method."""
        return []  # Logic handled in main validate method

    def _validate_year(self, year_str: str) -> list[RuleViolation]:
        """Validate year field."""
        violations: list[RuleViolation] = []

        # Remove common BibTeX formatting
        year_clean = year_str.strip("{}").strip()

        # Check for 4-digit year
        if not re.match(r"^\d{4}$", year_clean):
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=f"Year should be a 4-digit number, got: '{year_str}'",
                    field="year",
                    suggested_fix="Use format: YYYY (e.g., 2023)",
                )
            )
            return violations

        # Validate reasonable year range
        year_int = int(year_clean)
        current_year = 2024  # Could be dynamic
        if year_int < 1000 or year_int > current_year + 10:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="info",
                    message=f"Year {year_int} seems unusual (outside 1000-{current_year + 10})",
                    field="year",
                )
            )

        return violations

    def _validate_month(self, month_str: str) -> list[RuleViolation]:
        """Validate month field."""
        violations: list[RuleViolation] = []

        # Remove common BibTeX formatting
        month_clean = month_str.strip("{}").strip().lower()

        # Valid month representations
        valid_months = {
            # Full names
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
            # Short forms
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
            # Numbers
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
            "07",
            "08",
            "09",
        }

        if month_clean not in valid_months:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=f"Invalid month format: '{month_str}'",
                    field="month",
                    suggested_fix="Use full month name (January) or number (1-12)",
                )
            )

        return violations

    def _validate_day(
        self, day_str: str, year_str: str | None, month_str: str | None
    ) -> list[RuleViolation]:
        """Validate day field."""
        violations: list[RuleViolation] = []

        # Remove common BibTeX formatting
        day_clean = day_str.strip("{}").strip()

        # Check for numeric day
        if not re.match(r"^\d{1,2}$", day_clean):
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=f"Day should be a number (1-31), got: '{day_str}'",
                    field="day",
                    suggested_fix="Use numeric day (1-31)",
                )
            )
            return violations

        day_int = int(day_clean)

        # Basic range check
        if day_int < 1 or day_int > 31:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=f"Day must be between 1-31, got: {day_int}",
                    field="day",
                )
            )
            return violations

        # More detailed validation if year and month are available
        if year_str and month_str:
            try:
                year_clean = year_str.strip("{}").strip()
                month_clean = month_str.strip("{}").strip()

                if re.match(r"^\d{4}$", year_clean):
                    year_int = int(year_clean)
                    month_int = self._month_to_int(month_clean)

                    if month_int and 1 <= month_int <= 12:
                        # Check if day is valid for the specific month/year
                        max_day = monthrange(year_int, month_int)[1]
                        if day_int > max_day:
                            violations.append(
                                RuleViolation(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=f"Day {day_int} is invalid for {month_clean} {year_int} (max: {max_day})",
                                    field="day",
                                )
                            )
            except (ValueError, TypeError):
                # If we can't parse year/month, skip detailed validation
                pass

        return violations

    def _month_to_int(self, month_str: str) -> int | None:
        """Convert month string to integer."""
        month_lower = month_str.lower()

        # Direct number
        if month_lower.isdigit():
            month_int = int(month_lower)
            return month_int if 1 <= month_int <= 12 else None

        # Month name mapping
        month_map = {
            "january": 1,
            "jan": 1,
            "february": 2,
            "feb": 2,
            "march": 3,
            "mar": 3,
            "april": 4,
            "apr": 4,
            "may": 5,
            "june": 6,
            "jun": 6,
            "july": 7,
            "jul": 7,
            "august": 8,
            "aug": 8,
            "september": 9,
            "sep": 9,
            "october": 10,
            "oct": 10,
            "november": 11,
            "nov": 11,
            "december": 12,
            "dec": 12,
        }

        return month_map.get(month_lower)

    def can_fix(self) -> bool:
        """This rule cannot automatically fix date issues."""
        return False
