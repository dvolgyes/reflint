"""Content formatting and validation rules."""

from ..registry import register_rule
from .brace_management import AdvancedBraceManagementRule
from .conditional_validation import ConditionalValidationRule
from .journal_issn_validation import JournalIssnValidationRule
from .publication_name_standardization import PublicationNameStandardizationRule


def register_content_rules() -> None:
    """Register all content validation rules."""
    register_rule(AdvancedBraceManagementRule())
    register_rule(ConditionalValidationRule())
    register_rule(JournalIssnValidationRule())
    register_rule(PublicationNameStandardizationRule())


# Register rules when module is imported
register_content_rules()

__all__ = [
    "AdvancedBraceManagementRule",
    "ConditionalValidationRule",
    "JournalIssnValidationRule",
    "PublicationNameStandardizationRule",
]
