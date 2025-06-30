"""Rule registration and management system."""

from loguru import logger

from .base import BaseRule
from ..core.entry import BibTeXEntry
from ..core.validation import ValidationResult, RuleViolation


class RuleRegistry:
    """Registry for validation rules with automatic discovery."""

    def __init__(self) -> None:
        self._rules: dict[str, BaseRule] = {}
        self._rules_by_category: dict[str, list[BaseRule]] = {}

    def register_rule(self, rule: BaseRule) -> None:
        """Register a validation rule."""
        if rule.rule_id in self._rules:
            logger.warning(f"Rule {rule.rule_id} already registered, overwriting")

        self._rules[rule.rule_id] = rule

        # Add to category grouping
        if rule.category not in self._rules_by_category:
            self._rules_by_category[rule.category] = []
        self._rules_by_category[rule.category].append(rule)

        logger.debug(f"Registered rule {rule.rule_id} in category {rule.category}")

    def get_rule(self, rule_id: str) -> BaseRule | None:
        """Get a rule by its ID."""
        return self._rules.get(rule_id)

    def get_rules_by_category(self, category: str) -> list[BaseRule]:
        """Get all rules in a specific category."""
        return self._rules_by_category.get(category, [])

    def get_all_rules(self) -> list[BaseRule]:
        """Get all registered rules."""
        return list(self._rules.values())

    def get_rule_ids(self) -> list[str]:
        """Get all rule IDs."""
        return list(self._rules.keys())

    def validate_entry(
        self, entry: BibTeXEntry, rule_filter: list[str] | None = None
    ) -> ValidationResult:
        """Validate an entry against all or filtered rules."""
        violations: list[RuleViolation] = []

        # Determine which rules to run
        all_rules = list(self._rules.values())
        if rule_filter:
            rules_to_run = [r for r in all_rules if r.rule_id in rule_filter]
        else:
            rules_to_run = all_rules

        # Run validation rules
        for rule in rules_to_run:
            try:
                rule_violations = rule.validate(entry)
                violations.extend(rule_violations)
                logger.debug(
                    f"Rule {rule.rule_id} found {len(rule_violations)} violations"
                )
            except Exception as e:
                logger.error(f"Error running rule {rule.rule_id}: {e}")
                # Add error as a violation
                violations.append(
                    RuleViolation(
                        rule_id=rule.rule_id,
                        severity="error",
                        message=f"Rule execution failed: {e}",
                    )
                )

        return ValidationResult(
            entry_key=entry.key,
            violations=violations,
            metadata={"rules_run": [r.rule_id for r in rules_to_run]},
        )

    def get_statistics(self) -> dict:
        """Get statistics about registered rules."""
        stats = {
            "total_rules": len(self._rules),
            "categories": list(self._rules_by_category.keys()),
            "rules_by_category": {
                cat: len(rules) for cat, rules in self._rules_by_category.items()
            },
            "fixable_rules": sum(1 for rule in self._rules.values() if rule.can_fix()),
        }
        return stats


# Global registry instance
_global_registry = RuleRegistry()


def get_registry() -> RuleRegistry:
    """Get the global rule registry."""
    return _global_registry


def register_rule(rule: BaseRule) -> None:
    """Register a rule with the global registry."""
    _global_registry.register_rule(rule)
