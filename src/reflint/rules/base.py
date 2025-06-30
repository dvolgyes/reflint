"""Base classes for validation rules."""

from abc import ABC, abstractmethod
from typing import Literal

from ..core.entry import BibTeXEntry
from ..core.validation import RuleViolation


class BaseRule(ABC):
    """Base class for all validation rules."""

    rule_id: str
    severity: Literal["error", "warning", "info"]
    category: str
    description: str

    @abstractmethod
    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate an entry and return any violations found."""
        pass

    def can_fix(self) -> bool:
        """Return True if this rule can automatically fix violations."""
        return False

    def fix(self, entry: BibTeXEntry) -> BibTeXEntry:
        """Fix violations in the entry and return the modified entry."""
        if not self.can_fix():
            raise NotImplementedError(f"Rule {self.rule_id} cannot auto-fix violations")
        return entry

    def __str__(self) -> str:
        """String representation of the rule."""
        return f"{self.rule_id}: {self.description}"


class FieldValidationRule(BaseRule):
    """Base class for rules that validate specific fields."""

    def __init__(self, field_name: str):
        self.field_name = field_name

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate the specific field if it exists."""
        if not entry.has_field(self.field_name):
            return []

        field_value = entry.get_field(self.field_name)
        if field_value is None:
            return []

        return self.validate_field(entry, field_value)

    @abstractmethod
    def validate_field(
        self, entry: BibTeXEntry, field_value: str
    ) -> list[RuleViolation]:
        """Validate the specific field value."""
        pass


class EntryTypeRule(BaseRule):
    """Base class for rules that apply to specific entry types."""

    def __init__(self, entry_types: list[str]):
        self.entry_types = [t.lower() for t in entry_types]

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate only if entry type matches."""
        if entry.entry_type not in self.entry_types:
            return []
        return self.validate_entry_type(entry)

    @abstractmethod
    def validate_entry_type(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate the entry for specific types."""
        pass
