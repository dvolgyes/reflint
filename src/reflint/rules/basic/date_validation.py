"""Date validation rule (D001)."""

import re
from calendar import monthrange
from datetime import datetime
from typing import ClassVar

from ..base import FieldValidationRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation


class DateValidationRule(FieldValidationRule):
    """Rule D001: Advanced date validation with coherence checking."""

    rule_id: ClassVar[str] = "D001"
    severity: ClassVar[str] = "warning"
    category: ClassVar[str] = "content"
    description: ClassVar[str] = "Date fields must be properly formatted and valid with coherence checking"

    def __init__(self) -> None:
        super().__init__("year")  # Primary field to check
        self.current_year = datetime.now().year

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate date-related fields with advanced coherence checking."""
        violations: list[RuleViolation] = []

        # Extract and parse all date fields
        year_value = entry.get_field("year") if entry.has_field("year") else None
        month_value = entry.get_field("month") if entry.has_field("month") else None
        day_value = entry.get_field("day") if entry.has_field("day") else None

        # Parse date components
        year_int = self._parse_year(year_value) if year_value and year_value.strip() else None
        month_int = self._parse_month(month_value) if month_value and month_value.strip() else None
        day_int = self._parse_day(day_value) if day_value and day_value.strip() else None

        # Individual field validation
        if year_value is not None:
            violations.extend(self._validate_year_field(year_value, year_int))

        if month_value is not None:
            violations.extend(self._validate_month_field(month_value, month_int))

        if day_value is not None:
            violations.extend(self._validate_day_field(day_value, day_int))

        # Cross-field coherence validation
        violations.extend(self._validate_date_coherence(year_int, month_int, day_int))

        # Month normalization suggestions
        if month_value and month_int:
            violations.extend(self._suggest_month_normalization(month_value, month_int))

        return violations

    def validate_field(
        self, entry: BibTeXEntry, field_value: str
    ) -> list[RuleViolation]:
        """Required by parent class - delegates to main validate method."""
        return []  # Logic handled in main validate method

    def _parse_year(self, year_str: str) -> int | None:
        """Parse year string to integer."""
        year_clean = year_str.strip("{}").strip()
        if re.match(r"^\d{4}$", year_clean):
            return int(year_clean)
        return None

    def _parse_month(self, month_str: str) -> int | None:
        """Parse month string to integer (1-12)."""
        month_clean = month_str.strip("{}").strip().lower()
        
        # Direct number
        if month_clean.isdigit():
            month_int = int(month_clean)
            return month_int if 1 <= month_int <= 12 else None

        # Month name mapping
        month_map = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        }

        return month_map.get(month_clean)

    def _parse_day(self, day_str: str) -> int | None:
        """Parse day string to integer."""
        day_clean = day_str.strip("{}").strip()
        if re.match(r"^\d{1,2}$", day_clean):
            day_int = int(day_clean)
            return day_int if 1 <= day_int <= 31 else None
        return None

    def _validate_year_field(self, year_str: str, year_int: int | None) -> list[RuleViolation]:
        """Validate year field with advanced range checking."""
        violations: list[RuleViolation] = []

        # Check format
        if year_int is None:
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

        # Advanced year range validation with probability levels
        if year_int > self.current_year:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="error",
                    message=f"Year {year_int} is in the future (current year: {self.current_year})",
                    field="year",
                    suggested_fix=f"Use a year ≤ {self.current_year}",
                )
            )
        elif year_int < 1970:
            severity = "warning" if year_int < 1900 else "info"
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity=severity,
                    message=f"Year {year_int} is quite old (unlikely for modern publications)",
                    field="year",
                )
            )
        elif year_int < 2000:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="info",
                    message=f"Year {year_int} is somewhat old (maybe check if correct)",
                    field="year",
                )
            )

        return violations

    def _validate_month_field(self, month_str: str, month_int: int | None) -> list[RuleViolation]:
        """Validate month field."""
        violations: list[RuleViolation] = []

        if month_int is None:
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

    def _validate_day_field(self, day_str: str, day_int: int | None) -> list[RuleViolation]:
        """Validate day field."""
        violations: list[RuleViolation] = []

        if day_int is None:
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

    def _validate_date_coherence(self, year_int: int | None, month_int: int | None, day_int: int | None) -> list[RuleViolation]:
        """Validate coherence between date fields."""
        violations: list[RuleViolation] = []

        # Only validate coherence if we have valid year, month, and day
        if year_int and month_int and day_int:
            try:
                # Check if day is valid for the specific month/year
                max_day = monthrange(year_int, month_int)[1]
                if day_int > max_day:
                    violations.append(
                        RuleViolation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=f"Day {day_int} is invalid for month {month_int} in year {year_int} (max: {max_day})",
                            field="day",
                            suggested_fix=f"Use day 1-{max_day} for this month/year",
                        )
                    )
                    return violations  # Don't add additional errors for invalid date

                # Check for reasonable date (not too far in the future)
                from datetime import date
                try:
                    entry_date = date(year_int, month_int, day_int)
                    current_date = date.today()
                    
                    if entry_date > current_date:
                        violations.append(
                            RuleViolation(
                                rule_id=self.rule_id,
                                severity="error",
                                message=f"Date {entry_date} is in the future",
                                field="year",
                                suggested_fix="Use a date in the past or present",
                            )
                        )
                except ValueError:
                    # This should already be caught by the max_day check above
                    pass

            except (ValueError, TypeError):
                # If we can't validate, skip coherence check
                pass

        return violations

    def _suggest_month_normalization(self, month_str: str, month_int: int) -> list[RuleViolation]:
        """Suggest month normalization to numeric format."""
        violations: list[RuleViolation] = []
        
        month_clean = month_str.strip("{}").strip()
        
        # If month is already numeric, no suggestion needed
        if month_clean.isdigit():
            return violations
            
        # Suggest numeric format for non-numeric months
        violations.append(
            RuleViolation(
                rule_id=self.rule_id,
                severity="info",
                message=f"Consider normalizing month to numeric format",
                field="month",
                suggested_fix=str(month_int),
            )
        )

        return violations

    def can_fix(self) -> bool:
        """This rule can suggest fixes for month normalization."""
        return True
