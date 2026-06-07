"""Validation result classes and utilities."""

from typing import Any, Literal
from dataclasses import dataclass


@dataclass
class RuleViolation:
    """Represents a rule violation found during validation."""

    rule_id: str
    severity: Literal["error", "warning", "info"]
    message: str
    field: str | None = None
    suggested_fix: str | None = None

    def __str__(self) -> str:
        """String representation of the violation."""
        field_info = f" in field '{self.field}'" if self.field else ""
        return f"[{self.severity.upper()}] {self.rule_id}: {self.message}{field_info}"


@dataclass
class ValidationResult:
    """Container for validation results and metadata."""

    entry_key: str
    violations: list[RuleViolation]
    metadata: dict[str, Any]

    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level violations."""
        return any(v.severity == "error" for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warning-level violations."""
        return any(v.severity == "warning" for v in self.violations)

    @property
    def error_count(self) -> int:
        """Count of error-level violations."""
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count of warning-level violations."""
        return sum(1 for v in self.violations if v.severity == "warning")

    @property
    def info_count(self) -> int:
        """Count of info-level violations."""
        return sum(1 for v in self.violations if v.severity == "info")

    def get_violations_by_severity(
        self, severity: Literal["error", "warning", "info"]
    ) -> list[RuleViolation]:
        """Get violations filtered by severity level."""
        return [v for v in self.violations if v.severity == severity]

    def __str__(self) -> str:
        """String representation of validation result."""
        summary = f"ValidationResult for '{self.entry_key}': "
        summary += f"{self.error_count} errors, {self.warning_count} warnings, {self.info_count} info"
        return summary
