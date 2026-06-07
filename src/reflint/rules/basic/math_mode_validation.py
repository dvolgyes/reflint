"""Math mode validation rule (M001).

This rule validates LaTeX math mode syntax, checking for unmatched delimiters,
improper nesting, and potential issues with $ signs in mathematical expressions.
"""

import re
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, cast

from ..base import BaseRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation


@dataclass
class MathModeIssue:
    """Represents a math mode validation issue."""

    issue_type: str
    position: int
    context: str
    suggestion: str
    delimiter: str = ""


class MathModeValidator:
    """Validates LaTeX math mode syntax."""

    # Math mode delimiters and their properties
    MATH_DELIMITERS: ClassVar[dict[str, dict[str, Any]]] = {
        "$": {"type": "inline", "paired": True, "display": False},
        "$$": {"type": "display", "paired": True, "display": True},
        "\\(": {"type": "inline", "paired": True, "display": False, "close": "\\)"},
        "\\)": {
            "type": "inline_close",
            "paired": True,
            "display": False,
            "open": "\\(",
        },
        "\\[": {"type": "display", "paired": True, "display": True, "close": "\\]"},
        "\\]": {
            "type": "display_close",
            "paired": True,
            "display": True,
            "open": "\\[",
        },
        "\\begin{equation}": {
            "type": "environment",
            "paired": True,
            "display": True,
            "close": "\\end{equation}",
        },
        "\\end{equation}": {
            "type": "environment_close",
            "paired": True,
            "display": True,
            "open": "\\begin{equation}",
        },
        "\\begin{align}": {
            "type": "environment",
            "paired": True,
            "display": True,
            "close": "\\end{align}",
        },
        "\\end{align}": {
            "type": "environment_close",
            "paired": True,
            "display": True,
            "open": "\\begin{align}",
        },
        "\\begin{eqnarray}": {
            "type": "environment",
            "paired": True,
            "display": True,
            "close": "\\end{eqnarray}",
        },
        "\\end{eqnarray}": {
            "type": "environment_close",
            "paired": True,
            "display": True,
            "open": "\\begin{eqnarray}",
        },
    }

    # Math environments that need special handling
    MATH_ENVIRONMENTS = [
        "equation",
        "equation*",
        "align",
        "align*",
        "eqnarray",
        "eqnarray*",
        "gather",
        "gather*",
        "multline",
        "multline*",
        "split",
        "cases",
        "matrix",
        "pmatrix",
        "bmatrix",
        "vmatrix",
        "Vmatrix",
    ]

    # Pattern to find potential math delimiters
    DELIMITER_PATTERN = re.compile(
        r"(\$\$?|\\[\(\)\[\]]|\\begin\{(?:"
        + "|".join(MATH_ENVIRONMENTS)
        + r")\*?\}|\\end\{(?:"
        + "|".join(MATH_ENVIRONMENTS)
        + r")\*?\})",
        re.IGNORECASE,
    )

    # Pattern for escaped delimiters that should be ignored
    ESCAPED_PATTERN = re.compile(r"\\[\$\(\)\[\]]")

    def __init__(self) -> None:
        """Initialize the math mode validator."""
        pass

    def validate_math_mode(self, text: str) -> list[MathModeIssue]:
        """Validate math mode syntax in text.

        Args:
            text: Text to validate

        Returns:
            List of math mode issues found
        """
        issues = []

        # Find all potential math delimiters
        delimiters = list(self.DELIMITER_PATTERN.finditer(text))

        # Check for unmatched delimiters
        issues.extend(self._check_unmatched_delimiters(text, delimiters))

        # Check for improper nesting
        issues.extend(self._check_improper_nesting(text, delimiters))

        # Check for common issues
        issues.extend(self._check_common_issues(text))

        return issues

    def _check_unmatched_delimiters(
        self, text: str, delimiters: list[re.Match[str]]
    ) -> list[MathModeIssue]:
        """Check for unmatched math delimiters.

        Args:
            text: Original text
            delimiters: List of delimiter matches

        Returns:
            List of issues found
        """
        issues = []
        stack: list[dict[str, str | int]] = []

        for match in delimiters:
            delimiter = match.group(1)
            position = match.start()

            # Skip escaped delimiters
            if position > 0 and text[position - 1] == "\\" and delimiter in "$()[]":
                continue

            delimiter_info = self.MATH_DELIMITERS.get(delimiter, {})

            if delimiter == "$":
                # Single $ can be opening or closing
                if stack and stack[-1]["delimiter"] == "$":
                    # Closing $
                    stack.pop()
                else:
                    # Opening $
                    stack.append(
                        {"delimiter": delimiter, "position": position, "type": "inline"}
                    )

            elif delimiter == "$$":
                # $$ is always paired
                if stack and stack[-1]["delimiter"] == "$$":
                    # Closing $$
                    stack.pop()
                else:
                    # Opening $$
                    stack.append(
                        {
                            "delimiter": delimiter,
                            "position": position,
                            "type": "display",
                        }
                    )

            elif delimiter_info.get("type", "").endswith("_close"):
                # Closing delimiter
                expected_open = delimiter_info.get("open", "")
                if stack and stack[-1]["delimiter"] == expected_open:
                    stack.pop()
                else:
                    # Unmatched closing delimiter
                    context = self._get_context(text, position, 20)
                    issues.append(
                        MathModeIssue(
                            issue_type="unmatched_closing",
                            position=position,
                            context=context,
                            suggestion=f"Unmatched closing delimiter '{delimiter}'. Check for corresponding opening delimiter.",
                            delimiter=delimiter,
                        )
                    )

            else:
                # Opening delimiter
                stack.append(
                    {
                        "delimiter": delimiter,
                        "position": position,
                        "type": delimiter_info.get("type", "unknown"),
                    }
                )

        # Check for unclosed delimiters
        for unclosed in stack:
            position = cast(int, unclosed["position"])
            delimiter = cast(str, unclosed["delimiter"])
            context = self._get_context(text, position, 20)
            issues.append(
                MathModeIssue(
                    issue_type="unmatched_opening",
                    position=position,
                    context=context,
                    suggestion=f"Unclosed math delimiter '{delimiter}'. Add corresponding closing delimiter.",
                    delimiter=delimiter,
                )
            )

        return issues

    def _check_improper_nesting(
        self, text: str, delimiters: list[re.Match[str]]
    ) -> list[MathModeIssue]:
        """Check for improper nesting of math delimiters.

        Args:
            text: Original text
            delimiters: List of delimiter matches

        Returns:
            List of nesting issues
        """
        issues = []
        stack: list[dict[str, str | int]] = []

        for match in delimiters:
            delimiter = match.group(1)
            position = match.start()

            delimiter_info = self.MATH_DELIMITERS.get(delimiter, {})

            # Check for nested inline math
            if delimiter == "$":
                # For single $, we need to check if we're opening or closing
                is_opening = not (stack and stack[-1]["delimiter"] == "$")

                if (
                    is_opening
                    and stack
                    and any(item["type"] in ["inline", "display"] for item in stack)
                ):
                    context = self._get_context(text, position, 20)
                    issues.append(
                        MathModeIssue(
                            issue_type="nested_math",
                            position=position,
                            context=context,
                            suggestion="Nested math mode detected. Consider using \\text{} for text within math.",
                            delimiter=delimiter,
                        )
                    )

            # Update stack for tracking
            if delimiter == "$":
                if stack and stack[-1]["delimiter"] == "$":
                    stack.pop()
                else:
                    stack.append(
                        {"delimiter": delimiter, "type": "inline", "position": position}
                    )
            elif not delimiter_info.get("type", "").endswith("_close"):
                stack.append(
                    {
                        "delimiter": delimiter,
                        "type": delimiter_info.get("type", "unknown"),
                        "position": position,
                    }
                )
            else:
                if stack:
                    stack.pop()

        return issues

    def _check_common_issues(self, text: str) -> list[MathModeIssue]:
        """Check for common math mode issues.

        Args:
            text: Text to check

        Returns:
            List of common issues found
        """
        issues = []

        # Check for potential unescaped dollar signs in text
        dollar_pattern = re.compile(r"(?<!\\)\$(?!\$)")
        for match in dollar_pattern.finditer(text):
            position = match.start()

            # Get surrounding context to check if this might be currency
            context = self._get_context(text, position, 10)

            # Simple heuristic: if followed by digits, might be currency
            if re.search(r"\$\d", context):
                issues.append(
                    MathModeIssue(
                        issue_type="potential_currency",
                        position=position,
                        context=context,
                        suggestion="Potential currency symbol. If not math mode, escape with \\$.",
                        delimiter="$",
                    )
                )

        # Check for double dollars in inappropriate contexts
        double_dollar_pattern = re.compile(r"\$\$(?=\s*[a-zA-Z])")
        for match in double_dollar_pattern.finditer(text):
            position = match.start()
            context = self._get_context(text, position, 20)
            issues.append(
                MathModeIssue(
                    issue_type="display_math_inline",
                    position=position,
                    context=context,
                    suggestion="Display math ($$) should typically be on its own line.",
                    delimiter="$$",
                )
            )

        # Check for common LaTeX math command issues
        issues.extend(self._check_math_commands(text))

        return issues

    def _check_math_commands(self, text: str) -> list[MathModeIssue]:
        """Check for issues with math commands.

        Args:
            text: Text to check

        Returns:
            List of math command issues
        """
        issues = []

        # Check for math commands outside math mode (simplified check)
        math_commands = [
            r"\\alpha",
            r"\\beta",
            r"\\gamma",
            r"\\delta",
            r"\\epsilon",
            r"\\theta",
            r"\\lambda",
            r"\\mu",
            r"\\pi",
            r"\\sigma",
            r"\\phi",
            r"\\omega",
            r"\\sum",
            r"\\int",
            r"\\frac",
            r"\\sqrt",
            r"\\infty",
            r"\\partial",
            r"\\nabla",
            r"\\cdot",
            r"\\times",
            r"\\div",
        ]

        for command in math_commands:
            pattern = re.compile(command + r"\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                position = match.start()

                # Check if we're likely in math mode (simplified check)
                before_text = text[:position]

                # Count math delimiters before this position
                math_open = len(re.findall(r"(?<!\\)\$", before_text)) % 2
                in_math_env = bool(
                    re.search(r"\\begin\{(?:equation|align|eqnarray)", before_text)
                    and not re.search(
                        r"\\end\{(?:equation|align|eqnarray)", before_text
                    )
                )

                if not math_open and not in_math_env:
                    context = self._get_context(text, position, 15)
                    issues.append(
                        MathModeIssue(
                            issue_type="math_command_outside_math",
                            position=position,
                            context=context,
                            suggestion=f"Math command '{match.group()}' appears outside math mode. Wrap in $ $ or proper math environment.",
                            delimiter="",
                        )
                    )

        return issues

    def _get_context(self, text: str, position: int, radius: int = 20) -> str:
        """Get context around a position in text.

        Args:
            text: Full text
            position: Position of interest
            radius: Number of characters to include on each side

        Returns:
            Context string
        """
        start = max(0, position - radius)
        end = min(len(text), position + radius)

        context = text[start:end]

        # Mark the position of interest
        mark_pos = position - start
        if 0 <= mark_pos < len(context):
            context = context[:mark_pos] + "►" + context[mark_pos:]

        return context.strip()


class MathModeValidationRule(BaseRule):
    """Rule M001: Validates LaTeX math mode syntax."""

    rule_id: ClassVar[str] = "M001"
    severity: ClassVar[Literal["error", "warning", "info"]] = "warning"
    category: ClassVar[str] = "basic"
    description: ClassVar[str] = (
        "Validates LaTeX math mode syntax and checks for unmatched delimiters"
    )

    def __init__(self) -> None:
        """Initialize the math mode validation rule."""
        self.validator = MathModeValidator()

    def applies_to_field(self, field: str) -> bool:
        """Check if this rule applies to a specific field.

        Args:
            field: Field name to check

        Returns:
            True if rule applies to this field
        """
        # Apply to fields that commonly contain LaTeX math
        math_fields = {
            "title",
            "booktitle",
            "journal",
            "abstract",
            "note",
            "description",
            "keywords",
            "subtitle",
        }
        return field.lower() in math_fields

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate an entry for math mode issues.

        Args:
            entry: BibTeX entry to validate

        Returns:
            List of rule violations
        """
        violations = []

        for field_name in entry.get_all_fields():
            if not self.applies_to_field(field_name):
                continue

            field_value = entry.get_field(field_name)
            if not field_value or not isinstance(field_value, str):
                continue

            # Skip empty or very short values
            if len(field_value.strip()) < 2:
                continue

            # Check for math mode issues
            issues = self.validator.validate_math_mode(field_value)

            for issue in issues:
                # Determine severity based on issue type
                severity = self.severity
                if issue.issue_type in ["unmatched_opening", "unmatched_closing"]:
                    severity = "error"
                elif issue.issue_type == "nested_math":
                    severity = "warning"
                else:
                    severity = "info"

                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        field=field_name,
                        severity=severity,
                        message=issue.suggestion,
                        suggested_fix=None,  # Math issues typically need manual review
                    )
                )

        return violations

    def can_fix(self) -> bool:
        """Check if this rule can automatically fix violations."""
        # Only very safe fixes like currency escaping
        return True

    def fix(self, entry: BibTeXEntry) -> BibTeXEntry:
        """Attempt to fix math mode issues.

        Note: Math mode issues typically require manual review and cannot be
        automatically fixed safely. This method provides suggestions only.

        Args:
            entry: BibTeX entry to fix

        Returns:
            Entry with potential fixes (mostly unchanged for math issues)
        """
        # Math mode issues are complex and typically require manual review
        # We only attempt very safe fixes

        fixed_entry = BibTeXEntry(entry.to_dict())

        # Get violations to know what to fix
        violations = self.validate(entry)

        for violation in violations:
            field_name = violation.field
            if not field_name or not fixed_entry.has_field(field_name):
                continue

            field_value = str(fixed_entry.get_field(field_name))

            # Only attempt safe fixes for obvious currency cases
            # Check if the message mentions currency
            if "currency" in violation.message.lower():
                # Escape obvious currency symbols
                fixed_value = re.sub(r"(?<!\\)\$(\d)", r"\\$\1", field_value)
                fixed_entry.set_field(field_name, fixed_value)

        return fixed_entry
