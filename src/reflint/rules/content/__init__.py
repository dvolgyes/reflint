"""Content formatting and validation rules."""

from ..registry import register_rule
from .brace_management import AdvancedBraceManagementRule
from .conditional_validation import ConditionalValidationRule
from .journal_issn_validation import JournalIssnValidationRule
from .publication_name_standardization import PublicationNameStandardizationRule
from .unicode_latex_conversion import UnicodeLatexConversionRule, create_unicode_rule


def register_content_rules() -> None:
    """Register all content validation rules."""
    register_rule(AdvancedBraceManagementRule())
    register_rule(ConditionalValidationRule())
    register_rule(JournalIssnValidationRule())
    register_rule(PublicationNameStandardizationRule())
    register_rule(create_unicode_rule())


# Register rules when module is imported
register_content_rules()

__all__ = [
    "AdvancedBraceManagementRule",
    "ConditionalValidationRule",
    "JournalIssnValidationRule",
    "PublicationNameStandardizationRule",
    "UnicodeLatexConversionRule",
    "create_unicode_rule",
]
