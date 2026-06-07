"""Smart field dependencies for conditional validation."""

from typing import Any, ClassVar

from ..base import BaseRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation


class ConditionalValidationRule(BaseRule):
    """Rule that modifies validation behavior based on field dependencies."""

    rule_id = "C001"
    severity = "info"
    category = "dependencies"
    description = "Apply conditional validation logic based on field presence"

    # Define field dependency rules
    DEPENDENCY_RULES: ClassVar[dict[str, dict[str, Any]]] = {
        # Skip ISSN validation if arXiv ID is present
        "issn": {
            "skip_if_present": ["arxivid", "eprint"],
            "reason": "ISSN not applicable for arXiv preprints",
        },
        # Skip URL validation if DOI is present
        "url": {
            "skip_if_present": ["doi"],
            "reason": "DOI provides more reliable access than URL",
        },
        # Skip publisher validation for preprints
        "publisher": {
            "skip_if_present": ["arxivid", "eprint"],
            "reason": "Publisher not applicable for preprints",
        },
        # Skip pages validation for preprints
        "pages": {
            "skip_if_present": ["arxivid", "eprint"],
            "reason": "Page numbers not applicable for preprints",
        },
        # Skip journal validation for conference papers
        "journal": {
            "skip_if_present": ["booktitle"],
            "reason": "Conference papers use booktitle, not journal",
        },
        # Skip booktitle validation for journal papers
        "booktitle": {
            "skip_if_present": ["journal"],
            "reason": "Journal papers use journal, not booktitle",
        },
        # Skip volume/number for books
        "volume": {
            "skip_if_present_and_type": [("isbn", "book"), ("isbn", "incollection")],
            "reason": "Volume numbers typically not used for books",
        },
        "number": {
            "skip_if_present_and_type": [("isbn", "book"), ("isbn", "incollection")],
            "reason": "Issue numbers typically not used for books",
        },
    }

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Check for field dependencies and suggest conditional validation logic."""
        violations = []

        for field_name, rule_config in self.DEPENDENCY_RULES.items():
            if entry.has_field(field_name):
                # Check simple field presence dependencies
                if "skip_if_present" in rule_config:
                    for dependency_field in rule_config["skip_if_present"]:
                        if entry.has_field(dependency_field):
                            violation = RuleViolation(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Field '{field_name}' may be unnecessary due to '{dependency_field}' presence",
                                field=field_name,
                                suggested_fix=f"Consider removing '{field_name}' field: {rule_config['reason']}",
                            )
                            violations.append(violation)
                            break  # Only report one dependency per field

                # Check field presence + entry type dependencies
                if "skip_if_present_and_type" in rule_config:
                    for dependency_field, required_type in rule_config[
                        "skip_if_present_and_type"
                    ]:
                        if (
                            entry.has_field(dependency_field)
                            and entry.entry_type == required_type
                        ):
                            violation = RuleViolation(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Field '{field_name}' may be unnecessary for {required_type} with '{dependency_field}'",
                                field=field_name,
                                suggested_fix=f"Consider removing '{field_name}' field: {rule_config['reason']}",
                            )
                            violations.append(violation)
                            break

        # Check for missing expected dependencies
        violations.extend(self._check_missing_dependencies(entry))

        return violations

    def _check_missing_dependencies(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Check for cases where expected dependencies are missing."""
        violations = []

        # Conference papers should have booktitle or journal
        if (
            entry.entry_type in ["inproceedings", "conference"]
            and not entry.has_field("booktitle")
            and not entry.has_field("journal")
        ):
            violation = RuleViolation(
                rule_id=self.rule_id,
                severity="warning",
                message="Conference paper missing both 'booktitle' and 'journal' fields",
                suggested_fix="Add 'booktitle' field for conference proceedings",
            )
            violations.append(violation)

        # Journal articles should have journal
        if (
            entry.entry_type == "article"
            and not entry.has_field("journal")
            and not entry.has_field("arxivid")
            and not entry.has_field("eprint")
        ):
            violation = RuleViolation(
                rule_id=self.rule_id,
                severity="warning",
                message="Article missing 'journal' field and not identified as preprint",
                suggested_fix="Add 'journal' field or arXiv identifier",
            )
            violations.append(violation)

        # Books should have publisher or URL/DOI
        if (
            entry.entry_type in ["book", "proceedings"]
            and not entry.has_field("publisher")
            and not entry.has_field("url")
            and not entry.has_field("doi")
        ):
            violation = RuleViolation(
                rule_id=self.rule_id,
                severity="warning",
                message="Book/proceedings missing publisher and access information",
                suggested_fix="Add 'publisher' field or URL/DOI for access",
            )
            violations.append(violation)

        return violations

    def can_fix(self) -> bool:
        """This rule provides suggestions but doesn't auto-fix."""
        return False

    @staticmethod
    def should_skip_validation(entry: BibTeXEntry, field_name: str) -> tuple[bool, str]:
        """
        Check if validation should be skipped for a field based on dependencies.

        Args:
            entry: The BibTeX entry to check
            field_name: The field to check for skip conditions

        Returns:
            Tuple of (should_skip, reason)
        """
        rule = ConditionalValidationRule()

        if field_name not in rule.DEPENDENCY_RULES:
            return False, ""

        rule_config = rule.DEPENDENCY_RULES[field_name]

        # Check simple field presence dependencies
        if "skip_if_present" in rule_config:
            for dependency_field in rule_config["skip_if_present"]:
                if entry.has_field(dependency_field):
                    return True, rule_config["reason"]

        # Check field presence + entry type dependencies
        if "skip_if_present_and_type" in rule_config:
            for dependency_field, required_type in rule_config[
                "skip_if_present_and_type"
            ]:
                if (
                    entry.has_field(dependency_field)
                    and entry.entry_type == required_type
                ):
                    return True, rule_config["reason"]

        return False, ""
