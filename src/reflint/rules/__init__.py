"""Validation rules for BibTeX entries."""

from .registry import get_registry, register_rule
from .base import BaseRule, FieldValidationRule, EntryTypeRule

# Import basic rules to trigger auto-registration
from . import basic  # noqa: F401
from . import content  # noqa: F401

__all__ = [
    "BaseRule",
    "EntryTypeRule",
    "FieldValidationRule",
    "get_registry",
    "register_rule",
]
