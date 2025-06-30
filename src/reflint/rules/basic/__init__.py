"""Basic validation rules."""

from ..registry import register_rule
from .mandatory_fields import MandatoryFieldsRule
from .date_validation import DateValidationRule
from .page_formatting import PageFormattingRule
from .url_validation import URLValidationRule
from .math_mode_validation import MathModeValidationRule


# Auto-register all basic rules
def register_basic_rules() -> None:
    """Register all basic validation rules."""
    register_rule(MandatoryFieldsRule())
    register_rule(DateValidationRule())
    register_rule(PageFormattingRule())
    register_rule(URLValidationRule())
    register_rule(MathModeValidationRule())


# Register rules when module is imported
register_basic_rules()
