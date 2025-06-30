"""Journal-ISSN validation with cross-validation and standardization."""

import re

from ..base import BaseRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation
from ...sources.reliability import get_reliability_registry


class JournalIssnValidationRule(BaseRule):
    """Validates journal names against ISSN records with cross-validation."""

    rule_id = "B002"
    severity = "warning"
    category = "content"
    description = (
        "Validates journal names against ISSN records and suggests standardizations"
    )

    def __init__(self):
        super().__init__()
        self.reliability_registry = get_reliability_registry()

        # Common journal name standardizations
        self.journal_normalizations = {
            # IEEE Publications
            "IEEE Trans. Pattern Anal. Mach. Intell.": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "IEEE Trans. Pattern Analysis and Machine Intelligence": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "IEEE TPAMI": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "TPAMI": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            # Nature Publications
            "Nat. Mach. Intell.": "Nature Machine Intelligence",
            "Nature Machine Intel.": "Nature Machine Intelligence",
            "Nat Machine Intelligence": "Nature Machine Intelligence",
            # ACM Publications
            "ACM Trans. Graph.": "ACM Transactions on Graphics",
            "ACM TOG": "ACM Transactions on Graphics",
            "ACM Trans. Graphics": "ACM Transactions on Graphics",
            # Science Publications
            "Science Advances": "Science Advances",
            "Sci. Adv.": "Science Advances",
            "Science Adv": "Science Advances",
            # Other common abbreviations
            "J. Mach. Learn. Res.": "Journal of Machine Learning Research",
            "JMLR": "Journal of Machine Learning Research",
            "Proc. Natl. Acad. Sci.": "Proceedings of the National Academy of Sciences",
            "PNAS": "Proceedings of the National Academy of Sciences",
        }

        # Known journal-ISSN mappings for validation
        self.known_issn_mappings = {
            "Nature": ["0028-0836", "1476-4687"],  # Print and online ISSN
            "Science": ["0036-8075", "1095-9203"],
            "Nature Machine Intelligence": ["2522-5839"],
            "IEEE Transactions on Pattern Analysis and Machine Intelligence": [
                "0162-8828",
                "1939-3539",
            ],
            "Journal of Machine Learning Research": ["1532-4435", "1533-7928"],
            "Proceedings of the National Academy of Sciences": [
                "0027-8424",
                "1091-6490",
            ],
            "Science Advances": ["2375-2548"],
            "ACM Transactions on Graphics": ["0730-0301", "1557-7368"],
        }

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate journal-ISSN consistency and suggest improvements."""
        results = []

        journal = entry.get_field("journal")
        issn = entry.get_field("issn")

        if not journal:
            return results

        # Normalize journal name
        normalized_journal = self._normalize_journal_name(journal)

        # Check if journal name should be standardized
        if normalized_journal != journal:
            results.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="info",
                    message=f"Journal name can be standardized: '{journal}' → '{normalized_journal}'",
                    field="journal",
                    suggested_fix=f"Consider using standard form: {normalized_journal}",
                )
            )

        # Validate ISSN format if present
        if issn:
            issn_validation = self._validate_issn_format(issn)
            if issn_validation:
                results.append(issn_validation)

        # Cross-validate journal and ISSN
        cross_validation = self._cross_validate_journal_issn(normalized_journal, issn)
        if cross_validation:
            results.extend(cross_validation)

        # Suggest missing ISSN if we know it
        if not issn:
            known_issns = self._get_known_issns(normalized_journal)
            if known_issns:
                results.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        severity="info",
                        message=f"Missing ISSN for journal '{normalized_journal}'",
                        field="issn",
                        suggested_fix=f"Consider adding ISSN: {known_issns[0]} (print) or {known_issns[-1]} (online)"
                        if len(known_issns) > 1
                        else f"Consider adding ISSN: {known_issns[0]}",
                    )
                )

        return results

    def _normalize_journal_name(self, journal: str) -> str:
        """Normalize journal name using known standardizations."""
        if not journal:
            return journal

        # Check exact matches first
        if journal in self.journal_normalizations:
            return self.journal_normalizations[journal]

        # Check case-insensitive matches
        journal_lower = journal.lower()
        for abbrev, full_name in self.journal_normalizations.items():
            if journal_lower == abbrev.lower():
                return full_name

        # Apply common normalizations
        normalized = journal.strip()

        # Expand common abbreviations
        normalized = re.sub(r"\bProc\.\s*", "Proceedings of ", normalized)
        normalized = re.sub(r"\bJ\.\s*", "Journal of ", normalized)
        normalized = re.sub(r"\bTrans\.\s*", "Transactions on ", normalized)
        normalized = re.sub(r"\bConf\.\s*", "Conference on ", normalized)
        normalized = re.sub(r"\bInt\.\s*", "International ", normalized)
        normalized = re.sub(r"\bNat\.\s*", "Nature ", normalized)
        normalized = re.sub(r"\bSci\.\s*", "Science ", normalized)

        # Fix spacing issues
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip()

        return normalized

    def _validate_issn_format(self, issn: str) -> RuleViolation | None:
        """Validate ISSN format."""
        if not issn:
            return None

        # Strip whitespace and convert to uppercase
        clean_issn = issn.strip().upper()

        # Remove common prefixes like "ISSN "
        if clean_issn.startswith("ISSN "):
            clean_issn = clean_issn[5:]

        # ISSN format: NNNN-NNNX where X can be a digit or X
        issn_pattern = r"^\d{4}-\d{3}[\dX]$"

        if not re.match(issn_pattern, clean_issn):
            return RuleViolation(
                rule_id=self.rule_id,
                severity="warning",
                message=f"Invalid ISSN format: '{issn}'",
                field="issn",
                suggested_fix="ISSN should be in format NNNN-NNNN (8 digits with hyphen after 4th digit)",
            )

        # Validate ISSN check digit
        if not self._validate_issn_checksum(clean_issn):
            return RuleViolation(
                rule_id=self.rule_id,
                severity="warning",
                message=f"ISSN check digit validation failed: '{clean_issn}'",
                field="issn",
                suggested_fix="Verify ISSN is correct - check digit does not match",
            )

        return None

    def _validate_issn_checksum(self, issn: str) -> bool:
        """Validate ISSN check digit using modulo 11 algorithm."""
        if len(issn) != 9 or issn[4] != "-":
            return False

        # Extract digits (replace X with 10 for calculation)
        digits = issn.replace("-", "")
        if len(digits) != 8:
            return False

        try:
            checksum = 0
            for i, char in enumerate(digits[:7]):
                checksum += int(char) * (8 - i)

            remainder = checksum % 11
            expected_check = 11 - remainder if remainder != 0 else 0

            actual_check = 10 if digits[7] == "X" else int(digits[7])

            return expected_check == actual_check
        except (ValueError, IndexError):
            return False

    def _cross_validate_journal_issn(
        self, journal: str, issn: str | None
    ) -> list[RuleViolation]:
        """Cross-validate journal name against ISSN."""
        results = []

        if not issn:
            return results

        # Clean ISSN for comparison
        clean_issn = issn.strip().upper()
        if clean_issn.startswith("ISSN "):
            clean_issn = clean_issn[5:]

        # Check against known mappings
        known_issns = self._get_known_issns(journal)
        if known_issns and clean_issn not in known_issns:
            results.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=f"ISSN '{clean_issn}' does not match known ISSNs for journal '{journal}'",
                    field="issn",
                    suggested_fix=f"Expected ISSN for '{journal}': {' or '.join(known_issns)}",
                )
            )

        # Check for common mismatches
        mismatch = self._detect_common_mismatches(journal, clean_issn)
        if mismatch:
            results.append(mismatch)

        return results

    def _get_known_issns(self, journal: str) -> list[str]:
        """Get known ISSNs for a journal."""
        return self.known_issn_mappings.get(journal, [])

    def _detect_common_mismatches(
        self, journal: str, issn: str
    ) -> RuleViolation | None:
        """Detect common journal-ISSN mismatches."""
        # Check if ISSN belongs to a different well-known journal
        for known_journal, known_issns in self.known_issn_mappings.items():
            if issn in known_issns and known_journal.lower() != journal.lower():
                return RuleViolation(
                    rule_id=self.rule_id,
                    severity="error",
                    message=f"ISSN '{issn}' belongs to '{known_journal}', not '{journal}'",
                    field="issn",
                    suggested_fix=f"Check journal name - ISSN '{issn}' is for '{known_journal}'",
                )

        return None
