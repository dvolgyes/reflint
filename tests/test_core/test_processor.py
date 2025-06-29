"""Tests for BibTeX processor."""

from pathlib import Path

from reflint.core.processor import BibTeXProcessor


def test_load_from_string():
    """Test loading BibTeX from string."""
    bibtex_content = """
    @article{test2023,
      title={Test Title},
      author={Test Author},
      journal={Test Journal},
      year={2023}
    }
    """

    processor = BibTeXProcessor()
    processor.load_from_string(bibtex_content)

    assert len(processor) == 1
    entry = processor[0]
    assert entry.key == "test2023"
    assert entry.entry_type == "article"
    assert entry.get_field("title") == "Test Title"


def test_load_from_file():
    """Test loading BibTeX from file."""
    # Use the sample file we created
    sample_file = Path(__file__).parent.parent / "fixtures" / "bibtex" / "sample.bib"

    processor = BibTeXProcessor()
    processor.load_from_file(sample_file)

    assert len(processor) == 2

    # Check first entry
    entry1 = processor.get_entry_by_key("sample2023")
    assert entry1 is not None
    assert entry1.entry_type == "article"
    assert entry1.get_field("title") == "A Sample Article"

    # Check second entry
    entry2 = processor.get_entry_by_key("testbook2022")
    assert entry2 is not None
    assert entry2.entry_type == "book"
    assert entry2.get_field("title") == "Test Book Title"


def test_entry_types():
    """Test getting entry types."""
    bibtex_content = """
    @article{art1, title={Title1}, year={2023}}
    @book{book1, title={Title2}, year={2022}}
    @article{art2, title={Title3}, year={2021}}
    """

    processor = BibTeXProcessor()
    processor.load_from_string(bibtex_content)

    types = processor.get_entry_types()
    assert "article" in types
    assert "book" in types
    assert len(types) == 2


def test_filter_by_type():
    """Test filtering entries by type."""
    bibtex_content = """
    @article{art1, title={Title1}, year={2023}}
    @book{book1, title={Title2}, year={2022}}
    @article{art2, title={Title3}, year={2021}}
    """

    processor = BibTeXProcessor()
    processor.load_from_string(bibtex_content)

    articles = processor.filter_entries_by_type("article")
    assert len(articles) == 2

    books = processor.filter_entries_by_type("book")
    assert len(books) == 1
