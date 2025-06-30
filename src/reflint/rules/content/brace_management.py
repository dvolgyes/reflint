"""Advanced brace management for BibTeX entries."""

import re

from ..base import BaseRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation


class AdvancedBraceManagementRule(BaseRule):
    """Rule for advanced brace management with smart protected words."""

    rule_id = "B001"
    severity = "warning"
    category = "formatting"
    description = "Manage braces for protected words and consolidate unnecessary braces"

    # Domain-specific protected words that should be braced
    PROTECTED_WORDS = {
        # General technical terms
        "IEEE",
        "ACM",
        "API",
        "GPU",
        "CPU",
        "AI",
        "ML",
        "IoT",
        "3D",
        "2D",
        "4D",
        "HTTP",
        "HTTPS",
        "URL",
        "URI",
        "HTML",
        "CSS",
        "JSON",
        "XML",
        "PDF",
        "USB",
        "WiFi",
        "Bluetooth",
        "GPS",
        "GPS",
        "RFID",
        "NFC",
        # Computer Science
        "TCP",
        "UDP",
        "IP",
        "DNS",
        "SQL",
        "NoSQL",
        "REST",
        "SOAP",
        "GraphQL",
        "CUDA",
        "OpenGL",
        "DirectX",
        "WebGL",
        "OpenCL",
        "SIMD",
        "RISC",
        "CISC",
        "FPGA",
        "ASIC",
        "SoC",
        "PCIe",
        "RAM",
        "ROM",
        "SSD",
        "HDD",
        # Physics
        "QED",
        "QCD",
        "CERN",
        "LHC",
        "NASA",
        "ESA",
        "LIGO",
        "CMB",
        "UV",
        "IR",
        "EM",
        "RF",
        "GHz",
        "MHz",
        "THz",
        "keV",
        "MeV",
        "GeV",
        "TeV",
        # Biology/Medicine
        "DNA",
        "RNA",
        "PCR",
        "ELISA",
        "MRI",
        "CT",
        "PET",
        "fMRI",
        "COVID",
        "HIV",
        "AIDS",
        "WHO",
        "FDA",
        "NIH",
        "CDC",
        # Chemistry
        "NMR",
        "MS",
        "HPLC",
        "GC",
        "IR",
        "UV",
        "XRD",
        "TEM",
        "SEM",
        "pH",
        "pKa",
        "FTIR",
        "ESI",
        "MALDI",
        # Mathematics
        "PDF",
        "CDF",
        "FFT",
        "DFT",
        "PCA",
        "SVD",
        "GMM",
        "HMM",
        "MCMC",
        "EM",
        "MAP",
        "MLE",
        "AIC",
        "BIC",
    }

    def __init__(self):
        # Compile regex patterns for efficiency
        self._consolidation_pattern = re.compile(
            r"\{([A-Z])\}\{([A-Z])\}\{([A-Z])\}(?:\{([A-Z])\})?(?:\{([A-Z])\})?"
        )
        self._single_brace_pattern = re.compile(r"\{([A-Z]+)\}")
        self._protected_word_pattern = re.compile(
            r"\b(" + "|".join(self.PROTECTED_WORDS) + r")\b"
        )
        self._outer_brace_pattern = re.compile(r"^\{(.+)\}$")

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate brace usage in title, booktitle, and journal fields."""
        violations = []

        # Fields that commonly need brace protection
        fields_to_check = ["title", "booktitle", "journal", "series"]

        for field_name in fields_to_check:
            if entry.has_field(field_name):
                field_value = entry.get_field(field_name)
                if field_value:
                    violations.extend(
                        self._check_brace_issues(entry, field_name, field_value)
                    )

        return violations

    def _check_brace_issues(
        self, entry: BibTeXEntry, field_name: str, field_value: str
    ) -> list[RuleViolation]:
        """Check for various brace-related issues in a field."""
        violations = []

        # Check for brace consolidation opportunities
        consolidation_matches = list(self._consolidation_pattern.finditer(field_value))
        for match in consolidation_matches:
            groups = [g for g in match.groups() if g is not None]
            consolidated = "".join(groups)
            if consolidated in self.PROTECTED_WORDS:
                violation = RuleViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=f"Braces can be consolidated: {match.group()} → {{{consolidated}}}",
                    field=field_name,
                    suggested_fix=f"Replace {match.group()} with {{{consolidated}}}",
                )
                violations.append(violation)

        # Check for unprotected words that should be braced
        unprotected_matches = list(self._protected_word_pattern.finditer(field_value))
        for match in unprotected_matches:
            word = match.group(1)
            # Check if it's already properly braced
            start, end = match.span()
            if (start == 0 or field_value[start - 1] != "{") and (
                end == len(field_value) or field_value[end] != "}"
            ):
                violation = RuleViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=f"Protected word '{word}' should be braced",
                    field=field_name,
                    suggested_fix=f"Replace {word} with {{{word}}}",
                )
                violations.append(violation)

        # Check for unnecessary outer braces
        outer_match = self._outer_brace_pattern.match(field_value.strip())
        if outer_match:
            inner_content = outer_match.group(1)
            # Only suggest removal if inner content doesn't contain unprotected braces
            if not self._has_unprotected_content(inner_content):
                violation = RuleViolation(
                    rule_id=self.rule_id,
                    severity="info",
                    message="Unnecessary outer braces detected",
                    field=field_name,
                    suggested_fix=f"Remove outer braces: {inner_content}",
                )
                violations.append(violation)

        return violations

    def _has_unprotected_content(self, content: str) -> bool:
        """Check if content has elements that need protection."""
        # Check for protected words
        if self._protected_word_pattern.search(content):
            return True

        # Check for mixed case that might need protection
        if re.search(r"[a-z][A-Z]|[A-Z][a-z][A-Z]", content):
            return True

        # Check for nested braces
        if "{" in content and "}" in content:
            return True

        return False

    def can_fix(self) -> bool:
        """This rule can automatically fix brace issues."""
        return True

    def fix(self, entry: BibTeXEntry) -> BibTeXEntry:
        """Fix brace issues in the entry."""
        fields_to_fix = ["title", "booktitle", "journal", "series"]

        for field_name in fields_to_fix:
            if entry.has_field(field_name):
                field_value = entry.get_field(field_name)
                if field_value:
                    fixed_value = self._fix_braces(field_value)
                    if fixed_value != field_value:
                        entry.set_field(field_name, fixed_value)

        return entry

    def _fix_braces(self, text: str) -> str:
        """Fix brace issues in text."""
        # Step 1: Consolidate consecutive single-letter braces for known protected words
        text = self._consolidation_pattern.sub(self._consolidate_braces, text)

        # Step 2: Add braces to unprotected words
        text = self._protected_word_pattern.sub(self._protect_word, text)

        # Step 3: Remove unnecessary outer braces (conservative approach)
        text = self._remove_unnecessary_outer_braces(text)

        return text

    def _consolidate_braces(self, match) -> str:
        """Consolidate consecutive single-letter braces."""
        groups = [g for g in match.groups() if g is not None]
        consolidated = "".join(groups)
        if consolidated in self.PROTECTED_WORDS:
            return f"{{{consolidated}}}"
        return match.group(0)  # No change if not a known protected word

    def _protect_word(self, match) -> str:
        """Protect a word with braces if not already protected."""
        word = match.group(1)
        start, end = match.span()
        full_text = match.string

        # Check if already braced
        if (
            start > 0
            and full_text[start - 1] == "{"
            and end < len(full_text)
            and full_text[end] == "}"
        ):
            return word  # Already protected

        return f"{{{word}}}"

    def _remove_unnecessary_outer_braces(self, text: str) -> str:
        """Remove unnecessary outer braces conservatively."""
        text = text.strip()
        outer_match = self._outer_brace_pattern.match(text)

        if outer_match:
            inner_content = outer_match.group(1)
            # Only remove if we're confident it's safe
            if not self._has_unprotected_content(inner_content):
                # Additional safety check: ensure balanced braces inside
                if self._has_balanced_braces(inner_content):
                    return inner_content

        return text

    def _has_balanced_braces(self, text: str) -> bool:
        """Check if braces are balanced in the text."""
        count = 0
        for char in text:
            if char == "{":
                count += 1
            elif char == "}":
                count -= 1
                if count < 0:
                    return False
        return count == 0
