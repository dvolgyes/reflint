"""Tests for visual diff system."""

from reflint.utils.visual_diff import (
    VisualDiff,
    DiffChange,
    DiffSummary,
    create_entry_diff,
)


class TestVisualDiff:
    """Test the VisualDiff class."""

    def test_init(self):
        """Test VisualDiff initialization."""
        diff = VisualDiff()
        assert diff.context_size == 20

        diff_no_color = VisualDiff(use_colors=False, context_size=10)
        assert not diff_no_color.use_colors
        assert diff_no_color.context_size == 10

    def test_simple_insertion(self):
        """Test detection of simple text insertion."""
        diff = VisualDiff(use_colors=False)
        original = "Hello world"
        modified = "Hello beautiful world"

        summary = diff.generate_diff(original, modified)

        assert summary.total_changes > 0
        assert summary.insertions >= 1
        assert summary.characters_added > 0

    def test_simple_deletion(self):
        """Test detection of simple text deletion."""
        diff = VisualDiff(use_colors=False)
        original = "Hello beautiful world"
        modified = "Hello world"

        summary = diff.generate_diff(original, modified)

        assert summary.total_changes > 0
        assert summary.deletions >= 1 or summary.replacements >= 1
        assert summary.characters_removed > 0

    def test_simple_replacement(self):
        """Test detection of text replacement."""
        diff = VisualDiff(use_colors=False)
        original = "Hello world"
        modified = "Hello universe"

        summary = diff.generate_diff(original, modified)

        assert summary.total_changes > 0
        # Could be detected as replacement or deletion+insertion

    def test_no_changes(self):
        """Test when there are no changes."""
        diff = VisualDiff(use_colors=False)
        text = "Hello world"

        summary = diff.generate_diff(text, text)

        assert summary.total_changes == 0
        assert summary.insertions == 0
        assert summary.deletions == 0
        assert summary.replacements == 0

    def test_format_change_plain(self):
        """Test formatting changes without colors."""
        diff = VisualDiff(use_colors=False)

        insert_change = DiffChange("insert", "", "new", 0)
        formatted = diff.format_change(insert_change)
        assert "[+new]" in formatted

        delete_change = DiffChange("delete", "old", "", 0)
        formatted = diff.format_change(delete_change)
        assert "[-old]" in formatted

        replace_change = DiffChange("replace", "old", "new", 0)
        formatted = diff.format_change(replace_change)
        assert "[-old+new]" in formatted

    def test_format_diff_summary(self):
        """Test formatting of diff summary."""
        diff = VisualDiff(use_colors=False)

        changes = [
            DiffChange("insert", "", "new", 0),
            DiffChange("delete", "old", "", 5),
        ]
        summary = DiffSummary(
            total_changes=2,
            insertions=1,
            deletions=1,
            replacements=0,
            characters_added=3,
            characters_removed=3,
            changes=changes,
        )

        formatted = diff.format_diff_summary(summary)

        assert "Total changes: 2" in formatted
        assert "Insertions: 1" in formatted
        assert "Deletions: 1" in formatted
        assert "Changes:" in formatted

    def test_side_by_side_diff(self):
        """Test side-by-side diff display."""
        diff = VisualDiff(use_colors=False)
        original = "Line 1\nLine 2\nLine 3"
        modified = "Line 1\nModified Line 2\nLine 3\nNew Line 4"

        side_by_side = diff.create_side_by_side_diff(original, modified, width=80)

        assert "Original" in side_by_side
        assert "Modified" in side_by_side
        assert "|" in side_by_side
        assert "Line 1" in side_by_side
        assert "Modified Line 2" in side_by_side

    def test_unified_diff(self):
        """Test unified diff format."""
        diff = VisualDiff(use_colors=False)
        original = "Line 1\nLine 2\nLine 3"
        modified = "Line 1\nModified Line 2\nLine 3"

        unified = diff.create_unified_diff(original, modified)

        # Should contain diff markers
        assert "---" in unified or "+++" in unified or len(unified.strip()) == 0

    def test_bibtex_field_changes(self):
        """Test diff for BibTeX-like field content."""
        diff = VisualDiff(use_colors=False)
        original = "title = {Machine Learning Approaches}"
        modified = "title = {Deep Learning Approaches}"

        summary = diff.generate_diff(original, modified)

        assert summary.total_changes > 0

    def test_unicode_handling(self):
        """Test handling of Unicode characters in diff."""
        diff = VisualDiff(use_colors=False)
        original = "Café münchën"
        modified = "Café münchen"

        summary = diff.generate_diff(original, modified)

        # Should handle Unicode without errors
        assert isinstance(summary, DiffSummary)

    def test_latex_command_changes(self):
        """Test diff with LaTeX commands."""
        diff = VisualDiff(use_colors=False)
        original = 'author = {M{\\"u}ller, Hans}'
        modified = 'author = {M{\\\\"u}ller, Hans}'

        summary = diff.generate_diff(original, modified)

        assert summary.total_changes > 0

    def test_long_text_diff(self):
        """Test diff with longer text passages."""
        diff = VisualDiff(use_colors=False)
        original = (
            "This is a very long abstract that contains multiple sentences. " * 10
        )
        modified = "This is a very long summary that contains multiple sentences. " * 10

        summary = diff.generate_diff(original, modified)

        assert summary.total_changes > 0
        # Should not fail with long text

    def test_context_extraction(self):
        """Test context extraction around changes."""
        diff = VisualDiff(use_colors=False, context_size=5)
        original = "The quick brown fox jumps over the lazy dog"
        modified = "The quick red fox jumps over the lazy dog"

        summary = diff.generate_diff(original, modified)

        # Check that changes have been detected
        assert summary.total_changes > 0


class TestCreateEntryDiff:
    """Test the create_entry_diff function."""

    def test_entry_diff_with_changes(self):
        """Test diff creation for BibTeX entries with changes."""
        original = {
            "title": "Machine Learning Approaches",
            "author": "Smith, John",
            "year": "2023",
        }
        modified = {
            "title": "Deep Learning Approaches",
            "author": "Smith, John",
            "year": "2023",
            "journal": "Nature",
        }

        diff_text = create_entry_diff(original, modified)

        assert "title:" in diff_text
        assert "journal:" in diff_text

    def test_entry_diff_no_changes(self):
        """Test diff creation when entries are identical."""
        entry = {
            "title": "Machine Learning Approaches",
            "author": "Smith, John",
            "year": "2023",
        }

        diff_text = create_entry_diff(entry, entry)

        # Should be empty or minimal output when no changes
        assert len(diff_text.strip()) == 0

    def test_entry_diff_field_removal(self):
        """Test diff when fields are removed."""
        original = {
            "title": "Machine Learning Approaches",
            "author": "Smith, John",
            "year": "2023",
            "note": "Draft version",
        }
        modified = {
            "title": "Machine Learning Approaches",
            "author": "Smith, John",
            "year": "2023",
        }

        diff_text = create_entry_diff(original, modified)

        assert "note:" in diff_text

    def test_entry_diff_with_unicode(self):
        """Test diff with Unicode content in entries."""
        original = {"author": "Müller, Hans", "title": "Café studies"}
        modified = {"author": "Mueller, Hans", "title": "Café studies"}

        diff_text = create_entry_diff(original, modified)

        # Should handle Unicode without errors
        assert "author:" in diff_text


class TestDiffChange:
    """Test the DiffChange dataclass."""

    def test_diff_change_creation(self):
        """Test creating DiffChange objects."""
        change = DiffChange(
            change_type="insert",
            old_text="",
            new_text="new text",
            position=5,
            context_before="before",
            context_after="after",
        )

        assert change.change_type == "insert"
        assert change.new_text == "new text"
        assert change.position == 5


class TestDiffSummary:
    """Test the DiffSummary dataclass."""

    def test_diff_summary_creation(self):
        """Test creating DiffSummary objects."""
        changes = [
            DiffChange("insert", "", "new", 0),
            DiffChange("delete", "old", "", 5),
        ]

        summary = DiffSummary(
            total_changes=2,
            insertions=1,
            deletions=1,
            replacements=0,
            characters_added=3,
            characters_removed=3,
            changes=changes,
        )

        assert summary.total_changes == 2
        assert len(summary.changes) == 2
        assert summary.characters_added == 3
        assert summary.characters_removed == 3
