"""Tests for content cleanup rule."""

from src.reflint.rules.content.content_cleanup import ContentCleanupRule
from src.reflint.core.entry import BibTeXEntry


class TestContentCleanupRule:
    """Test cases for content cleanup rule."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule = ContentCleanupRule()

    def test_xml_tag_removal(self):
        """Test removal of XML tags."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "A study of <em>machine learning</em> and <strong>AI</strong>",
                "abstract": "This paper discusses <i>deep learning</i> approaches.",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2  # title and abstract

        title_result = next(r for r in results if r.field == "title")
        assert "A study of machine learning and AI" in title_result.suggested_fix
        assert "removed XML tags" in title_result.message

        abstract_result = next(r for r in results if r.field == "abstract")
        assert (
            "This paper discusses deep learning approaches."
            in abstract_result.suggested_fix
        )

    def test_html_entity_conversion(self):
        """Test conversion of HTML entities."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Research &amp; Development in AI &quot;Systems&quot;",
                "author": "Smith &amp; Jones",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        title_result = next(r for r in results if r.field == "title")
        assert 'Research & Development in AI "Systems"' in title_result.suggested_fix
        assert "converted HTML entities" in title_result.message

        author_result = next(r for r in results if r.field == "author")
        assert "Smith & Jones" in author_result.suggested_fix

    def test_whitespace_normalization(self):
        """Test normalization of whitespace."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "A   study    with   multiple     spaces",
                "journal": "  Journal  with  tabs\t\tand  spaces  ",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        title_result = next(r for r in results if r.field == "title")
        assert "A study with multiple spaces" in title_result.suggested_fix
        assert "normalized whitespace" in title_result.message

        journal_result = next(r for r in results if r.field == "journal")
        assert "Journal with tabs and spaces" in journal_result.suggested_fix
        assert "trimmed whitespace" in journal_result.message

    def test_invisible_character_removal(self):
        """Test removal of invisible Unicode characters."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Title\u200bwith\u200czero\u200dwidth\u2060chars\ufeff",
                "author": "Author\u00adwith\u200bsoft\u200chyphen",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        title_result = next(r for r in results if r.field == "title")
        assert "Titlewithzerowidthchars" in title_result.suggested_fix
        assert "removed invisible characters" in title_result.message

        author_result = next(r for r in results if r.field == "author")
        assert "Authorwithsofthyphen" in author_result.suggested_fix

    def test_encoding_issue_fixes(self):
        """Test fixing of common encoding issues."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "José María investigación with Ã±",
                "author": "François Müller becomes FranÃ§ois MÃ¼ller",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        title_result = next(r for r in results if r.field == "title")
        assert "José María investigación with ñ" in title_result.suggested_fix
        assert "fixed encoding issues" in title_result.message

        author_result = next(r for r in results if r.field == "author")
        assert "François Müller becomes François Müller" in author_result.suggested_fix

    def test_stray_backslash_removal(self):
        """Test removal of stray backslashes."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Title with \\ stray backslashes \\ but keep \\textbf{bold}",
                "abstract": "Abstract with \\alpha math and \\ random backslash",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        title_result = next(r for r in results if r.field == "title")
        assert (
            "Title with  stray backslashes  but keep \\textbf{bold}"
            in title_result.suggested_fix
        )
        assert "removed stray backslashes" in title_result.message

        abstract_result = next(r for r in results if r.field == "abstract")
        assert (
            "Abstract with \\alpha math and  random backslash"
            in abstract_result.suggested_fix
        )

    def test_punctuation_pattern_fixes(self):
        """Test fixing of punctuation patterns."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "Title with......multiple dots!!!!",
                "abstract": "What about this????",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        title_result = next(r for r in results if r.field == "title")
        assert "Title with...multiple dots!" in title_result.suggested_fix
        assert "fixed punctuation patterns" in title_result.message

        abstract_result = next(r for r in results if r.field == "abstract")
        assert "What about this?" in abstract_result.suggested_fix

    def test_entry_id_sanitization(self):
        """Test entry ID sanitization."""
        # Test various problematic IDs
        test_cases = [
            ("123invalid", "entry_123invalid", "added prefix to numeric ID"),
            ("valid@#$%id", "validid", "removed invalid ID characters"),
            ("", "entry_unknown", "replaced empty ID"),
            ("a" * 150, "a" * 100, "truncated long ID"),
            ("valid-id_123", "valid-id_123", None),  # Should not need cleanup
        ]

        for original_id, expected_id, expected_message in test_cases:
            entry = BibTeXEntry(
                {
                    "ID": original_id,
                    "ENTRYTYPE": "article",
                    "title": "Test Title",
                }
            )

            results = self.rule.validate(entry)

            if expected_message:
                # Should have ID violation
                id_results = [r for r in results if r.field == "ID"]
                assert len(id_results) == 1
                assert expected_id in id_results[0].suggested_fix
                assert expected_message in id_results[0].message
            else:
                # Should not have ID violation
                id_results = [r for r in results if r.field == "ID"]
                assert len(id_results) == 0

    def test_multiple_cleanup_operations(self):
        """Test combining multiple cleanup operations."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "  <b>Title</b> with &amp;   multiple   issues\u200b....  ",
                "author": "AuthorÃ© with\u200c issues\\",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 2

        title_result = next(r for r in results if r.field == "title")
        suggested = title_result.suggested_fix
        assert "Title with & multiple issues..." in suggested

        # Check that multiple operations are listed
        message = title_result.message
        assert "removed XML tags" in message
        assert "converted HTML entities" in message
        assert "normalized whitespace" in message
        assert "removed invisible characters" in message
        assert "trimmed whitespace" in message
        assert "fixed punctuation patterns" in message

        author_result = next(r for r in results if r.field == "author")
        assert "Authoré with issues" in author_result.suggested_fix

    def test_no_cleanup_needed(self):
        """Test entries that don't need cleanup."""
        entry = BibTeXEntry(
            {
                "ID": "clean_entry_123",
                "ENTRYTYPE": "article",
                "title": "Clean Title with No Issues",
                "author": "John Smith and Jane Doe",
                "journal": "Clean Journal Name",
            }
        )

        results = self.rule.validate(entry)

        assert len(results) == 0

    def test_field_coverage(self):
        """Test that all relevant fields are checked for cleanup."""
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
                    field_name: "Text   with   cleanup  needed  ",
                }
            )

            results = self.rule.validate(entry)
            assert len(results) == 1
            assert results[0].field == field_name
            assert "normalized whitespace" in results[0].message

    def test_empty_and_none_fields(self):
        """Test handling of empty and None field values."""
        entry = BibTeXEntry(
            {
                "ID": "test",
                "ENTRYTYPE": "article",
                "title": "",
                "author": None,
                "journal": "Normal Journal",
            }
        )

        results = self.rule.validate(entry)

        # Should not crash and should not report issues for empty/None fields
        assert len(results) == 0

    def test_rule_metadata(self):
        """Test rule metadata."""
        assert self.rule.rule_id == "C003"
        assert self.rule.severity == "info"
        assert self.rule.category == "content"
        assert "clean" in self.rule.description.lower()

    def test_complex_mixed_content(self):
        """Test complex content with multiple types of issues."""
        entry = BibTeXEntry(
            {
                "ID": "123complex@test",
                "ENTRYTYPE": "article",
                "title": "<i>Analysis</i> of AI &amp; Machine Learning........with\u200b issues",
                "abstract": "  This  research  examines   <em>deep</em>   learning  methods  &quot;specifically&quot;  ",
                "author": "José MarÃ­a Smith &amp; Jane\u200c Doe\\",
            }
        )

        results = self.rule.validate(entry)

        # Should have violations for ID, title, abstract, and author
        assert len(results) == 4

        # Check ID sanitization
        id_result = next(r for r in results if r.field == "ID")
        assert "entry_123complextest" in id_result.suggested_fix
        assert "added prefix to numeric ID" in id_result.message
        assert "removed invalid ID characters" in id_result.message

        # Check title cleanup
        title_result = next(r for r in results if r.field == "title")
        assert (
            "Analysis of AI & Machine Learning...with issues"
            in title_result.suggested_fix
        )

        # Check abstract cleanup
        abstract_result = next(r for r in results if r.field == "abstract")
        assert (
            'This research examines deep learning methods "specifically"'
            in abstract_result.suggested_fix
        )

        # Check author cleanup
        author_result = next(r for r in results if r.field == "author")
        # Note: MarÃ­a -> María encoding fix should happen
        assert "José María Smith & Jane Doe" in author_result.suggested_fix
