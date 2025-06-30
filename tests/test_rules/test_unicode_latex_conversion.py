"""Tests for Unicode to LaTeX conversion rule."""

from src.reflint.rules.content.unicode_latex_conversion import (
    UnicodeLatexConversionRule,
    QuoteStyle,
    create_unicode_rule,
)
from src.reflint.core.entry import BibTeXEntry


class TestUnicodeLatexConversionRule:
    """Test cases for Unicode to LaTeX conversion rule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = UnicodeLatexConversionRule()  # Default quote style

    def test_scandinavian_characters(self):
        """Test conversion of Scandinavian characters."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Årsrapport från Björn Åkesson",
                "author": "Øivind Sørensen and Åse Hägg",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2  # title and author fields

        # Check title conversion
        title_result = next(r for r in results if r.field == "title")
        assert (
            r"{\AA}rsrapport fr{\aa}n Bj{\"o}rn {\AA}kesson"
            in title_result.suggested_fix
        )

        # Check author conversion
        author_result = next(r for r in results if r.field == "author")
        assert (
            r"{\O}ivind S{\o}rensen and {\AA}se H{\"a}gg" in author_result.suggested_fix
        )

    def test_german_characters(self):
        """Test conversion of German characters."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Über die Größe der Lösung",
                "author": "Müller, Günther",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        # Check title conversion
        title_result = next(r for r in results if r.field == "title")
        assert (
            r"{\"U}ber die Gr{\"o}{\ss}e der L{\"o}sung" in title_result.suggested_fix
        )

        # Check author conversion
        author_result = next(r for r in results if r.field == "author")
        assert r"M{\"u}ller, G{\"u}nther" in author_result.suggested_fix

    def test_french_characters(self):
        """Test conversion of French characters."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Étude théorique des phénomènes électriques",
                "author": "François Lefèvre",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        # Check title conversion
        title_result = next(r for r in results if r.field == "title")
        expected_title = (
            r"{\'E}tude th{\'e}orique des ph{\'e}nom{\`e}nes {\'e}lectriques"
        )
        assert expected_title in title_result.suggested_fix

        # Check author conversion
        author_result = next(r for r in results if r.field == "author")
        assert r"Fran{\c c}ois Lef{\`e}vre" in author_result.suggested_fix

    def test_spanish_characters(self):
        """Test conversion of Spanish characters."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Investigación sobre la comunicación",
                "author": "José María Peña",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        # Check title conversion
        title_result = next(r for r in results if r.field == "title")
        assert (
            r"Investigaci{\'o}n sobre la comunicaci{\'o}n" in title_result.suggested_fix
        )

        # Check author conversion
        author_result = next(r for r in results if r.field == "author")
        assert r"Jos{\'e} Mar{\'i}a Pe{\~n}a" in author_result.suggested_fix

    def test_mathematical_symbols(self):
        """Test conversion of mathematical symbols."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Analysis of α-particles and β-decay using μ-detectors",
                "abstract": "Temperature increased by 25° with ± 2° uncertainty",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        # Check title conversion
        title_result = next(r for r in results if r.field == "title")
        expected = (
            r"Analysis of $\alpha$-particles and $\beta$-decay using $\mu$-detectors"
        )
        assert expected in title_result.suggested_fix

        # Check abstract conversion
        abstract_result = next(r for r in results if r.field == "abstract")
        expected_abstract = (
            r"Temperature increased by 25$^\circ$ with $\pm$ 2$^\circ$ uncertainty"
        )
        assert expected_abstract in abstract_result.suggested_fix

    def test_quotation_marks(self):
        """Test conversion of smart quotes."""
        # Use Unicode escape sequences for smart quotes
        title_text = "\u201cSmart\u201d quotes and \u2018single\u2019 quotes"
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": title_text,
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 1

        result = results[0]
        assert "``Smart'' quotes and `single' quotes" in result.suggested_fix

    def test_dashes(self):
        """Test conversion of en-dash and em-dash."""
        # Use Unicode escape sequences for dashes
        title_text = (
            "Pages 100\u2013110 \u2014 A comprehensive study"  # en-dash and em-dash
        )
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": title_text,
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 1

        result = results[0]
        assert "Pages 100--110 --- A comprehensive study" in result.suggested_fix

    def test_eastern_european_characters(self):
        """Test conversion of Eastern European characters."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Studie o možnostech českého výzkumu",
                "author": "Václav Novák and Petr Dvořák",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        # Check title conversion
        title_result = next(r for r in results if r.field == "title")
        expected = r"Studie o mo{\v z}nostech {\v c}esk{\'e}ho v{\'y}zkumu"
        assert expected in title_result.suggested_fix

        # Check author conversion
        author_result = next(r for r in results if r.field == "author")
        expected_author = r"V{\'a}clav Nov{\'a}k and Petr Dvo{\v r}{\'a}k"
        assert expected_author in author_result.suggested_fix

    def test_polish_characters(self):
        """Test conversion of Polish characters."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Badania nad wpływem środowiska",
                "author": "Paweł Kowalski and Łukasz Zieliński",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        # Check title conversion
        title_result = next(r for r in results if r.field == "title")
        expected = r"Badania nad wp{\l}ywem {\'s}rodowiska"
        assert expected in title_result.suggested_fix

        # Check author conversion
        author_result = next(r for r in results if r.field == "author")
        expected_author = r"Pawe{\l} Kowalski and {\L}ukasz Zieli{\'n}ski"
        assert expected_author in author_result.suggested_fix

    def test_no_unicode_characters(self):
        """Test that entries without Unicode characters are not flagged."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Standard ASCII Title",
                "author": "John Smith and Jane Doe",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 0

    def test_mixed_characters(self):
        """Test conversion with mixed character types."""
        # Use Unicode escape sequences for problematic characters
        title_text = (
            "Über α-radiation at 25° in \u201cmodern\u201d physics \u2014 a review"
        )
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": title_text,
                "author": "François Müller and José Åkesson",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        # Check title has multiple conversions
        title_result = next(r for r in results if r.field == "title")
        suggested = title_result.suggested_fix
        assert r"{\"U}ber" in suggested  # German
        assert r"$\alpha$" in suggested  # Greek
        assert r"$^\circ$" in suggested  # Degree symbol
        assert r"``modern" "" in suggested  # Smart quotes
        assert r"---" in suggested  # Em dash

        # Check author has multiple conversions
        author_result = next(r for r in results if r.field == "author")
        suggested_author = author_result.suggested_fix
        assert r"Fran{\c c}ois" in suggested_author  # French
        assert r"M{\"u}ller" in suggested_author  # German
        assert r"Jos{\'e}" in suggested_author  # Spanish
        assert r"{\AA}kesson" in suggested_author  # Scandinavian

    def test_conversion_details_in_message(self):
        """Test that conversion details are included in the message."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Résumé of Müller's work",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 1

        result = results[0]
        assert "é" in result.message
        assert r"{\'e}" in result.message
        assert "ü" in result.message
        assert r"{\"u}" in result.message

    def test_field_coverage(self):
        """Test that all relevant fields are checked for Unicode."""
        fields_to_test = [
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

        for field_name in fields_to_test:
            entry = BibTeXEntry(
                {
                    "ID": "test",
                    "ENTRYTYPE": "article",
                    field_name: "Text with ñ character",
                }
            )

            results = self.rule.validate(entry)
            assert len(results) == 1
            assert results[0].field == field_name

    def test_rule_metadata(self):
        """Test rule metadata."""
        assert self.rule.rule_id == "C002"
        assert self.rule.severity == "info"
        assert self.rule.category == "content"
        assert "unicode" in self.rule.description.lower()
        assert "latex" in self.rule.description.lower()

    def test_complex_mathematical_expressions(self):
        """Test conversion of complex mathematical expressions."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Study of Ω-baryon decay: α→β+γ with σ≈2.5×10⁻³",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 1

        result = results[0]
        suggested = result.suggested_fix
        assert r"$\Omega$" in suggested
        assert r"$\alpha$" in suggested
        assert r"$\beta$" in suggested
        assert r"$\gamma$" in suggested
        assert r"$\sigma$" in suggested
        assert r"$\approx$" in suggested
        assert r"$\times$" in suggested

    def test_empty_and_none_fields(self):
        """Test handling of empty and None field values."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "",
                "author": None,
                "journal": "Normal Journal Name",
            }
        )

        results = self.rule.validate(entry)

        # Should not crash and should not report issues for empty/None fields
        assert len(results) == 0

    def test_long_character_sequences_first(self):
        """Test that longer character sequences are processed before shorter ones."""
        # This tests the sorting by length in conversion
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Text with Ã¡ sequence",  # Multi-byte encoding issue
            }
        )

        results = self.rule.validate(entry)

        # Should handle the multi-character sequence properly
        assert len(results) == 1
        # The Ã¡ should be converted to á first, then á to LaTeX
        assert r"{\'a}" in results[0].suggested_fix

    def test_configurable_quote_styles(self):
        """Test different quote conversion styles."""
        # Test text with both double and single quotes
        title_text = "\u201cDouble\u201d quotes and \u2018single\u2019 quotes"
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": title_text,
            }
        )

        # Test LaTeX traditional style (default)
        rule_traditional = UnicodeLatexConversionRule(QuoteStyle.LATEX_TRADITIONAL)
        results = rule_traditional.validate(entry)
        assert len(results) == 1
        assert "``Double'' quotes and `single' quotes" in results[0].suggested_fix

        # Test LaTeX csquotes style
        rule_csquotes = UnicodeLatexConversionRule(QuoteStyle.LATEX_CSQUOTES)
        results = rule_csquotes.validate(entry)
        assert len(results) == 1
        suggested = results[0].suggested_fix
        assert r"\enquote{Double} quotes and \enquote*{single} quotes" in suggested

        # Test Unicode preserve style
        rule_preserve = UnicodeLatexConversionRule(QuoteStyle.UNICODE_PRESERVE)
        results = rule_preserve.validate(entry)
        assert len(results) == 0  # No conversion needed, quotes preserved

        # Test ASCII straight style
        rule_ascii = UnicodeLatexConversionRule(QuoteStyle.ASCII_STRAIGHT)
        results = rule_ascii.validate(entry)
        assert len(results) == 1
        assert '"Double" quotes and \'single\' quotes' in results[0].suggested_fix

    def test_create_unicode_rule_factory(self):
        """Test the factory function for creating rules with different styles."""
        # Test default style
        rule_default = create_unicode_rule()
        assert rule_default.quote_style == QuoteStyle.LATEX_TRADITIONAL

        # Test explicit styles
        rule_csquotes = create_unicode_rule("latex-csquotes")
        assert rule_csquotes.quote_style == QuoteStyle.LATEX_CSQUOTES

        rule_preserve = create_unicode_rule("unicode-preserve")
        assert rule_preserve.quote_style == QuoteStyle.UNICODE_PRESERVE

        rule_ascii = create_unicode_rule("ascii-straight")
        assert rule_ascii.quote_style == QuoteStyle.ASCII_STRAIGHT

        # Test invalid style
        try:
            create_unicode_rule("invalid-style")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown quote style" in str(e)

    def test_quote_style_integration(self):
        """Test that quote styles work correctly in mixed content."""
        title_text = "Study of \u201cmodern\u201d methods using α-particles"
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": title_text,
            }
        )

        # Traditional LaTeX style
        rule_traditional = create_unicode_rule("latex-traditional")
        results = rule_traditional.validate(entry)
        assert len(results) == 1
        suggested = results[0].suggested_fix
        assert "``modern''" in suggested
        assert r"$\alpha$" in suggested

        # csquotes style
        rule_csquotes = create_unicode_rule("latex-csquotes")
        results = rule_csquotes.validate(entry)
        assert len(results) == 1
        suggested = results[0].suggested_fix
        assert r"\enquote{modern}" in suggested
        assert r"$\alpha$" in suggested

    def test_quote_conversion_message_details(self):
        """Test that quote conversion details are shown in messages."""
        title_text = "\u201cTest\u201d with \u2018quotes\u2019"
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": title_text,
            }
        )

        # Traditional style
        rule = create_unicode_rule("latex-traditional")
        results = rule.validate(entry)
        assert len(results) == 1
        message = results[0].message

        # Check that conversion details are in the message
        assert "\u201c" in message  # Original Unicode char
        assert "``" in message     # LaTeX equivalent
        assert "\u201d" in message  # Original Unicode char
        assert "''" in message     # LaTeX equivalent
        assert "\u2018" in message  # Original Unicode char
        assert "`" in message      # LaTeX equivalent
        assert "\u2019" in message  # Original Unicode char
        assert "'" in message      # LaTeX equivalent
