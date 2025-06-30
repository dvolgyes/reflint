"""Unicode to LaTeX character conversion rule."""

import re
from typing import ClassVar

from ...core.validation import RuleViolation
from ..base import BaseRule


class UnicodeLatexConversionRule(BaseRule):
    """Rule for converting Unicode characters to LaTeX equivalents."""

    rule_id: ClassVar[str] = "C002"
    severity: ClassVar[str] = "info"
    category: ClassVar[str] = "content"
    description: ClassVar[str] = "Convert Unicode characters to LaTeX equivalents"

    # Comprehensive Unicode to LaTeX mapping
    UNICODE_TO_LATEX = {
        # Scandinavian characters
        "å": r"{\aa}",
        "Å": r"{\AA}",
        "ä": r'{\"a}',
        "Ä": r'{\"A}',
        "ö": r'{\"o}',
        "Ö": r'{\"O}',
        "æ": r"{\ae}",
        "Æ": r"{\AE}",
        "ø": r"{\o}",
        "Ø": r"{\O}",
        # German characters
        "ü": r'{\"u}',
        "Ü": r'{\"U}',
        "ß": r"{\ss}",
        # French characters
        "à": r"{\`a}",
        "À": r"{\`A}",
        "á": r"{\'a}",
        "Á": r"{\'A}",
        "â": r"{\^a}",
        "Â": r"{\^A}",
        "ã": r"{\~a}",
        "Ã": r"{\~A}",
        "ç": r"{\c c}",
        "Ç": r"{\c C}",
        "è": r"{\`e}",
        "È": r"{\`E}",
        "é": r"{\'e}",
        "É": r"{\'E}",
        "ê": r"{\^e}",
        "Ê": r"{\^E}",
        "ë": r'{\"e}',
        "Ë": r'{\"E}',
        "î": r"{\^i}",
        "Î": r"{\^I}",
        "ï": r'{\"i}',
        "Ï": r'{\"I}',
        "ô": r"{\^o}",
        "Ô": r"{\^O}",
        "ù": r"{\`u}",
        "Ù": r"{\`U}",
        "ú": r"{\'u}",
        "Ú": r"{\'U}",
        "û": r"{\^u}",
        "Û": r"{\^U}",
        "ÿ": r'{\"y}',
        "Ÿ": r'{\"Y}',
        # Spanish characters
        "ñ": r"{\~n}",
        "Ñ": r"{\~N}",
        "í": r"{\'i}",
        "Í": r"{\'I}",
        "ó": r"{\'o}",
        "Ó": r"{\'O}",
        # Eastern European
        "č": r"{\v c}",
        "Č": r"{\v C}",
        "ď": r"{\v d}",
        "Ď": r"{\v D}",
        "ě": r"{\v e}",
        "Ě": r"{\v E}",
        "ň": r"{\v n}",
        "Ň": r"{\v N}",
        "ř": r"{\v r}",
        "Ř": r"{\v R}",
        "š": r"{\v s}",
        "Š": r"{\v S}",
        "ť": r"{\v t}",
        "Ť": r"{\v T}",
        "ů": r"{\r u}",
        "Ů": r"{\r U}",
        "ý": r"{\'y}",
        "Ý": r"{\'Y}",
        "ž": r"{\v z}",
        "Ž": r"{\v Z}",
        # Polish characters
        "ą": r"{\k a}",
        "Ą": r"{\k A}",
        "ć": r"{\'c}",
        "Ć": r"{\'C}",
        "ę": r"{\k e}",
        "Ę": r"{\k E}",
        "ł": r"{\l}",
        "Ł": r"{\L}",
        "ń": r"{\'n}",
        "Ń": r"{\'N}",
        "ś": r"{\'s}",
        "Ś": r"{\'S}",
        "ź": r"{\'z}",
        "Ź": r"{\'Z}",
        "ż": r"{\. z}",
        "Ż": r"{\. Z}",
        # Mathematical symbols
        "α": r"$\alpha$",
        "β": r"$\beta$",
        "γ": r"$\gamma$",
        "δ": r"$\delta$",
        "ε": r"$\epsilon$",
        "ζ": r"$\zeta$",
        "η": r"$\eta$",
        "θ": r"$\theta$",
        "ι": r"$\iota$",
        "κ": r"$\kappa$",
        "λ": r"$\lambda$",
        "μ": r"$\mu$",
        "ν": r"$\nu$",
        "ξ": r"$\xi$",
        "π": r"$\pi$",
        "ρ": r"$\rho$",
        "σ": r"$\sigma$",
        "τ": r"$\tau$",
        "υ": r"$\upsilon$",
        "φ": r"$\phi$",
        "χ": r"$\chi$",
        "ψ": r"$\psi$",
        "ω": r"$\omega$",
        "Α": r"$A$",
        "Β": r"$B$",
        "Γ": r"$\Gamma$",
        "Δ": r"$\Delta$",
        "Ε": r"$E$",
        "Ζ": r"$Z$",
        "Η": r"$H$",
        "Θ": r"$\Theta$",
        "Ι": r"$I$",
        "Κ": r"$K$",
        "Λ": r"$\Lambda$",
        "Μ": r"$M$",
        "Ν": r"$N$",
        "Ξ": r"$\Xi$",
        "Π": r"$\Pi$",
        "Ρ": r"$P$",
        "Σ": r"$\Sigma$",
        "Τ": r"$T$",
        "Υ": r"$\Upsilon$",
        "Φ": r"$\Phi$",
        "Χ": r"$X$",
        "Ψ": r"$\Psi$",
        "Ω": r"$\Omega$",
        # Common symbols
        "°": r"$^\circ$",
        "±": r"$\pm$",
        "²": r"$^2$",
        "³": r"$^3$",
        "µ": r"$\mu$",
        "·": r"$\cdot$",
        "×": r"$\times$",
        "÷": r"$\div$",
        "≈": r"$\approx$",
        "≠": r"$\neq$",
        "≤": r"$\leq$",
        "≥": r"$\geq$",
        "∞": r"$\infty$",
        "∂": r"$\partial$",
        "∇": r"$\nabla$",
        "∑": r"$\sum$",
        "∏": r"$\prod$",
        "∫": r"$\int$",
        "√": r"$\sqrt{}$",
        # Quotation marks
        "\u201c": r"``",  # left double quotation mark
        "\u201d": r"''",  # right double quotation mark
        "\u2018": r"`",   # left single quotation mark
        "\u2019": r"'",   # right single quotation mark
        # En/em dashes
        "\u2013": r"--",  # en dash
        "\u2014": r"---", # em dash
        # Common encoding issues
        "Ã¡": "\u00e1",  # á encoded as UTF-8 then decoded as Latin-1
        "Ã©": "\u00e9",  # é encoded as UTF-8 then decoded as Latin-1
        "Ã­": "\u00ed",  # í encoded as UTF-8 then decoded as Latin-1
        "Ã³": "\u00f3",  # ó encoded as UTF-8 then decoded as Latin-1
        "Ãº": "\u00fa",  # ú encoded as UTF-8 then decoded as Latin-1
        "Ã±": "\u00f1",  # ñ encoded as UTF-8 then decoded as Latin-1
    }

    # Fields that commonly contain Unicode characters
    UNICODE_FIELDS = [
        "title",
        "author",
        "journal",
        "booktitle",
        "publisher",
        "address",
        "note",
        "abstract",
        "keywords",
        "series",
    ]

    def validate(self, entry):
        """Check for Unicode characters that should be converted to LaTeX."""
        violations = []

        for field_name in self.UNICODE_FIELDS:
            if entry.has_field(field_name):
                field_value = entry.get_field(field_name)
                if field_value:
                    converted_value, conversions = self._convert_unicode_to_latex(
                        field_value
                    )

                    if conversions:
                        # Create detailed message about conversions
                        conversion_details = ", ".join(
                            f"'{char}' → '{latex}'" for char, latex in conversions
                        )

                        violations.append(
                            RuleViolation(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Unicode characters found in {field_name}: {conversion_details}",
                                field=field_name,
                                suggested_fix=converted_value,
                            )
                        )

        return violations

    def _convert_unicode_to_latex(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """
        Convert Unicode characters to LaTeX equivalents.

        Returns:
            Tuple of (converted_text, list_of_conversions)
        """
        converted_text = text
        conversions = []

        # Sort by length (longest first) to handle multi-character sequences
        sorted_mappings = sorted(
            self.UNICODE_TO_LATEX.items(), key=lambda x: len(x[0]), reverse=True
        )

        for unicode_char, latex_equiv in sorted_mappings:
            if unicode_char in converted_text:
                conversions.append((unicode_char, latex_equiv))
                converted_text = converted_text.replace(unicode_char, latex_equiv)

        return converted_text, conversions

