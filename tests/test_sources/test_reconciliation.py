"""Tests for data reconciliation system."""

from reflint.sources.base import LookupResult, SourceMetadata
from reflint.sources.reconciliation import DataReconciler
from reflint.core.entry import BibTeXEntry


class TestDataReconciler:
    """Test the data reconciliation system."""

    def test_reconcile_single_source(self):
        """Test reconciliation with single source."""
        reconciler = DataReconciler()

        # Create lookup result
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "title": "Test Title",
            "author": "Test Author",
            "journal": "Test Journal",
            "year": "2023",
        }
        entry = BibTeXEntry(entry_dict)

        metadata = SourceMetadata(
            source_name="test_source", lookup_time=0.1, confidence=0.9
        )

        result = LookupResult(entry=entry, metadata=metadata)

        # Reconcile
        reconciled = reconciler.reconcile([result])

        assert reconciled.entry.get_field("title") == "Test Title"
        assert len(reconciled.conflicts) == 0
        assert "test_source" in reconciled.sources_used
        assert reconciled.confidence_score > 0.8

    def test_reconcile_with_conflicts(self):
        """Test reconciliation with conflicting data."""
        reconciler = DataReconciler()

        # Create first source result
        entry1_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "title": "Short Title",
            "author": "Test Author",
            "year": "2023",
        }
        entry1 = BibTeXEntry(entry1_dict)
        metadata1 = SourceMetadata("source1", 0.1, 0.8)
        result1 = LookupResult(entry=entry1, metadata=metadata1)

        # Create second source result with conflicts
        entry2_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "title": "A Much Longer and More Detailed Title",
            "author": "Test Author",
            "year": "2024",  # Conflict!
        }
        entry2 = BibTeXEntry(entry2_dict)
        metadata2 = SourceMetadata("source2", 0.1, 0.9)
        result2 = LookupResult(entry=entry2, metadata=metadata2)

        # Reconcile
        reconciled = reconciler.reconcile([result1, result2])

        # Should have conflicts
        assert len(reconciled.conflicts) > 0

        # Title should use longer value (LONGEST_VALUE strategy)
        assert (
            reconciled.entry.get_field("title")
            == "A Much Longer and More Detailed Title"
        )

        # Year should use higher confidence source (HIGHEST_CONFIDENCE strategy)
        assert (
            reconciled.entry.get_field("year") == "2024"
        )  # source2 has higher confidence

    def test_reconcile_with_original_entry(self):
        """Test reconciliation including original entry."""
        reconciler = DataReconciler()

        # Original entry
        original_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "title": "Original Title",
            "author": "Original Author",
            "note": "Original note",
        }
        original = BibTeXEntry(original_dict)

        # External source result
        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "title": "Enhanced Title",
            "author": "Enhanced Author",
            "journal": "New Journal",  # New field
            "doi": "10.1234/test",  # New field
        }
        entry = BibTeXEntry(entry_dict)
        metadata = SourceMetadata("external_source", 0.1, 0.9)
        result = LookupResult(entry=entry, metadata=metadata)

        # Reconcile
        reconciled = reconciler.reconcile([result], original)

        # Should keep original note (not in external data)
        assert reconciled.entry.get_field("note") == "Original note"

        # Should use enhanced data for higher confidence fields
        assert reconciled.entry.get_field("journal") == "New Journal"
        assert reconciled.entry.get_field("doi") == "10.1234/test"

    def test_field_conflict_resolution_strategies(self):
        """Test different conflict resolution strategies."""
        reconciler = DataReconciler()

        # Test HIGHEST_CONFIDENCE strategy
        source_values = {
            "source1": ("value1", 0.7),
            "source2": ("value2", 0.9),
            "source3": ("value3", 0.6),
        }

        conflict = reconciler._resolve_field_conflict("test_field", source_values)
        # Should select source2 (highest confidence)
        assert conflict.selected_value == "value2"
        assert conflict.selected_source == "source2"

    def test_completeness_calculation(self):
        """Test completeness score calculation."""
        reconciler = DataReconciler()

        # Article with all important fields
        complete_entry = BibTeXEntry(
            {
                "ID": "complete",
                "ENTRYTYPE": "article",
                "title": "Title",
                "author": "Author",
                "journal": "Journal",
                "year": "2023",
                "doi": "10.1234/test",
            }
        )

        completeness = reconciler._calculate_completeness(complete_entry)
        assert completeness == 1.0  # Perfect score

        # Article missing some fields
        incomplete_entry = BibTeXEntry(
            {
                "ID": "incomplete",
                "ENTRYTYPE": "article",
                "title": "Title",
                "author": "Author",
                # Missing journal, year, doi
            }
        )

        completeness = reconciler._calculate_completeness(incomplete_entry)
        assert completeness < 0.5  # Low score

    def test_manual_review_detection(self):
        """Test manual review requirement detection."""
        reconciler = DataReconciler()

        # Create conflicting entries for critical fields
        entry1_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "title": "Different Title",
            "author": "Author One",
        }
        entry1 = BibTeXEntry(entry1_dict)
        metadata1 = SourceMetadata("source1", 0.1, 0.8)
        result1 = LookupResult(entry=entry1, metadata=metadata1)

        entry2_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "title": "Completely Different Title",
            "author": "Author Two",
        }
        entry2 = BibTeXEntry(entry2_dict)
        metadata2 = SourceMetadata("source2", 0.1, 0.8)
        result2 = LookupResult(entry=entry2, metadata=metadata2)

        # Reconcile
        reconciled = reconciler.reconcile([result1, result2])

        # Should require manual review due to title/author conflicts
        assert reconciled.manual_review_required

    def test_get_reconciliation_summary(self):
        """Test reconciliation summary generation."""
        reconciler = DataReconciler()

        # Create simple reconciliation
        entry_dict = {"ID": "test_entry", "ENTRYTYPE": "article", "title": "Test Title"}
        entry = BibTeXEntry(entry_dict)
        metadata = SourceMetadata("test_source", 0.1, 0.9)
        result = LookupResult(entry=entry, metadata=metadata)

        reconciled = reconciler.reconcile([result])
        summary = reconciler.get_reconciliation_summary(reconciled)

        assert "sources_used" in summary
        assert "num_conflicts" in summary
        assert "confidence_score" in summary
        assert "completeness_score" in summary
        assert summary["num_conflicts"] == 0
