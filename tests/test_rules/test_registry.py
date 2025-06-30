"""Tests for rule registry system."""

from reflint.core.entry import BibTeXEntry
from reflint.core.validation import RuleViolation
from reflint.rules.base import BaseRule
from reflint.rules.registry import RuleRegistry


class MockRule(BaseRule):
    """Mock rule for testing."""

    rule_id = "TEST001"
    severity = "warning"
    category = "test"
    description = "Mock test rule"

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Always return one test violation."""
        return [
            RuleViolation(
                rule_id=self.rule_id, severity=self.severity, message="Test violation"
            )
        ]


class TestRuleRegistry:
    """Test the rule registry system."""

    def test_register_rule(self):
        """Test rule registration."""
        registry = RuleRegistry()
        rule = MockRule()

        registry.register_rule(rule)

        assert rule.rule_id in registry.get_rule_ids()
        assert registry.get_rule(rule.rule_id) == rule

    def test_get_rules_by_category(self):
        """Test getting rules by category."""
        registry = RuleRegistry()
        rule = MockRule()

        registry.register_rule(rule)

        rules_in_category = registry.get_rules_by_category("test")
        assert len(rules_in_category) == 1
        assert rules_in_category[0] == rule

    def test_validate_entry(self):
        """Test entry validation."""
        registry = RuleRegistry()
        rule = MockRule()
        registry.register_rule(rule)

        # Create test entry
        entry_dict = {"ID": "test_entry", "ENTRYTYPE": "article", "title": "Test Title"}
        entry = BibTeXEntry(entry_dict)

        result = registry.validate_entry(entry)

        assert result.entry_key == "test_entry"
        assert len(result.violations) == 1
        assert result.violations[0].rule_id == "TEST001"

    def test_rule_filter(self):
        """Test rule filtering during validation."""
        registry = RuleRegistry()
        rule1 = MockRule()
        rule1.rule_id = "TEST001"
        rule2 = MockRule()
        rule2.rule_id = "TEST002"

        registry.register_rule(rule1)
        registry.register_rule(rule2)

        # Create test entry
        entry_dict = {"ID": "test_entry", "ENTRYTYPE": "article", "title": "Test Title"}
        entry = BibTeXEntry(entry_dict)

        # Test with filter
        result = registry.validate_entry(entry, rule_filter=["TEST001"])

        assert len(result.violations) == 1
        assert result.violations[0].rule_id == "TEST001"

    def test_get_statistics(self):
        """Test registry statistics."""
        registry = RuleRegistry()
        rule = MockRule()
        registry.register_rule(rule)

        stats = registry.get_statistics()

        assert stats["total_rules"] == 1
        assert "test" in stats["categories"]
        assert stats["rules_by_category"]["test"] == 1
        assert stats["fixable_rules"] == 0  # MockRule cannot fix
