"""Mandatory fields validation rule (F001)."""

from ..base import BaseRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation


# Entry type requirements based on BibTeX standards
MANDATORY_FIELDS: dict[str, list[str | list[str]]] = {
    "article": ["author", "title", "journal", "year"],
    "book": [["author", "editor"], "title", "publisher", "year"],
    "booklet": ["title"],
    "inbook": [
        ["author", "editor"],
        "title",
        ["chapter", "pages"],
        "publisher",
        "year",
    ],
    "incollection": ["author", "title", "booktitle", "publisher", "year"],
    "inproceedings": ["author", "title", "booktitle", "year"],
    "conference": ["author", "title", "booktitle", "year"],  # Alias for inproceedings
    "manual": ["title"],
    "mastersthesis": ["author", "title", "school", "year"],
    "misc": [],  # No mandatory fields for misc
    "phdthesis": ["author", "title", "school", "year"],
    "proceedings": ["title", "year"],
    "techreport": ["author", "title", "institution", "year"],
    "unpublished": ["author", "title", "note"],
}


class MandatoryFieldsRule(BaseRule):
    """Rule F001: Check for mandatory fields based on entry type."""

    rule_id = "F001"
    severity = "error"
    category = "structure"
    description = "Entry must have all mandatory fields for its type"

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate that entry has all mandatory fields."""
        violations: list[RuleViolation] = []
        entry_type = entry.entry_type

        if entry_type not in MANDATORY_FIELDS:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=f"Unknown entry type '{entry_type}' - cannot validate mandatory fields",
                )
            )
            return violations

        required_fields = MANDATORY_FIELDS[entry_type]

        for field_requirement in required_fields:
            if isinstance(field_requirement, list):
                # Alternative fields - at least one must be present
                has_alternative = any(
                    entry.has_field(field) for field in field_requirement
                )
                if not has_alternative:
                    field_names = " or ".join(f"'{f}'" for f in field_requirement)
                    violations.append(
                        RuleViolation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=f"Missing required field: {field_names}",
                            suggested_fix=f"Add one of: {field_names}",
                        )
                    )
            else:
                # Single required field
                if not entry.has_field(field_requirement):
                    violations.append(
                        RuleViolation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=f"Missing required field: '{field_requirement}'",
                            field=field_requirement,
                            suggested_fix=f"Add '{field_requirement}' field",
                        )
                    )

        return violations

    def can_fix(self) -> bool:
        """This rule cannot automatically fix missing fields."""
        return False
