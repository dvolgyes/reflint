"""Tests for identifier extraction utilities."""

from reflint.core.entry import BibTeXEntry
from reflint.utils.identifiers import IdentifierExtractor


class TestIdentifierExtractor:
    """Test the identifier extraction system."""

    def test_extract_doi_from_text(self):
        """Test DOI extraction from text."""
        extractor = IdentifierExtractor()

        # Standard DOI
        doi = extractor.extract_doi("10.1234/example.doi")
        assert doi == "10.1234/example.doi"

        # DOI in URL
        doi = extractor.extract_doi("https://doi.org/10.1234/example.doi")
        assert doi == "10.1234/example.doi"

        # DOI in dx.doi.org URL
        doi = extractor.extract_doi("http://dx.doi.org/10.1234/example.doi")
        assert doi == "10.1234/example.doi"

        # No DOI
        doi = extractor.extract_doi("no doi here")
        assert doi is None

    def test_extract_arxiv_from_text(self):
        """Test arXiv ID extraction from text."""
        extractor = IdentifierExtractor()

        # Standard arXiv ID
        arxiv_id = extractor.extract_arxiv("arXiv:2023.12345")
        assert arxiv_id == "2023.12345"

        # arXiv ID without prefix
        arxiv_id = extractor.extract_arxiv("2023.12345v1")
        assert arxiv_id == "2023.12345v1"

        # arXiv URL
        arxiv_id = extractor.extract_arxiv("https://arxiv.org/abs/2023.12345")
        assert arxiv_id == "2023.12345"

        # No arXiv ID
        arxiv_id = extractor.extract_arxiv("no arxiv here")
        assert arxiv_id is None

    def test_extract_pmid_from_text(self):
        """Test PMID extraction from text."""
        extractor = IdentifierExtractor()

        # Standard PMID
        pmid = extractor.extract_pmid("PMID: 12345678")
        assert pmid == "12345678"

        # PMID without colon
        pmid = extractor.extract_pmid("PMID 12345678")
        assert pmid == "12345678"

        # PMID URL
        pmid = extractor.extract_pmid("https://pubmed.ncbi.nlm.nih.gov/12345678/")
        assert pmid == "12345678"

        # No PMID
        pmid = extractor.extract_pmid("no pmid here")
        assert pmid is None

    def test_validate_issn(self):
        """Test ISSN validation."""
        # Valid ISSN
        assert IdentifierExtractor.validate_issn("0028-0836")  # Nature (valid)
        assert IdentifierExtractor.validate_issn("1144-875X")  # Valid ISSN with X

        # Invalid ISSN
        assert not IdentifierExtractor.validate_issn("1234-5678")  # Wrong checksum
        assert not IdentifierExtractor.validate_issn("invalid")

    def test_validate_isbn(self):
        """Test ISBN validation."""
        # Valid ISBN-10
        assert IdentifierExtractor.validate_isbn("0306406152")

        # Valid ISBN-13
        assert IdentifierExtractor.validate_isbn("9780306406157")

        # Invalid ISBN
        assert not IdentifierExtractor.validate_isbn("1234567890")  # Wrong checksum
        assert not IdentifierExtractor.validate_isbn("invalid")

    def test_extract_from_entry(self):
        """Test identifier extraction from BibTeX entry."""
        extractor = IdentifierExtractor()

        entry_dict = {
            "ID": "test_entry",
            "ENTRYTYPE": "article",
            "doi": "10.1234/example.doi",
            "url": "https://arxiv.org/abs/2023.12345",
            "note": "PMID: 12345678",
            "eprint": "2023.12345",
            "issn": "1234-567X",
        }
        entry = BibTeXEntry(entry_dict)

        identifiers = extractor.extract_from_entry(entry)

        # Should extract DOI, arXiv (from URL and eprint), PMID, and ISSN
        assert len(identifiers) >= 4

        # Check specific identifiers
        doi_ids = [i for i in identifiers if i.identifier_type == "doi"]
        assert len(doi_ids) == 1
        assert doi_ids[0].value == "10.1234/example.doi"

        arxiv_ids = [i for i in identifiers if i.identifier_type == "arxiv"]
        assert len(arxiv_ids) >= 1
        assert any(i.value == "2023.12345" for i in arxiv_ids)

    def test_get_canonical_url(self):
        """Test canonical URL generation."""
        extractor = IdentifierExtractor()

        # DOI URL
        url = extractor.get_canonical_url("doi", "10.1234/example.doi")
        assert url == "https://doi.org/10.1234/example.doi"

        # arXiv URL
        url = extractor.get_canonical_url("arxiv", "2023.12345")
        assert url == "https://arxiv.org/abs/2023.12345"

        # PMID URL
        url = extractor.get_canonical_url("pmid", "12345678")
        assert url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"

        # Unsupported type
        url = extractor.get_canonical_url("unknown", "12345")
        assert url is None
