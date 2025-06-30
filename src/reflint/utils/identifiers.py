"""Identifier extraction and validation utilities."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..core.entry import BibTeXEntry


@dataclass
class ExtractedIdentifier:
    """Container for extracted identifier information."""

    identifier_type: str
    value: str
    source_field: str
    confidence: float = 1.0


class IdentifierExtractor:
    """Extract and validate academic identifiers from BibTeX entries."""

    # DOI patterns
    DOI_PATTERN = re.compile(r"10\.\d{4,6}/[^\s\"'&<>\t\n\r\f\v]+", re.IGNORECASE)
    DOI_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:dx\.)?doi\.org/(10\.\d{4,6}/[^\s\"'&<>\t\n\r\f\v]+)",
        re.IGNORECASE,
    )

    # arXiv patterns
    ARXIV_PATTERN = re.compile(r"(?:arXiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
    ARXIV_URL_PATTERN = re.compile(
        r"(?:https?://)?arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE
    )

    # PMID patterns
    PMID_PATTERN = re.compile(r"(?:PMID:?\s*)?(\d{8})", re.IGNORECASE)
    PMID_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?ncbi\.nlm\.nih\.gov/pubmed/(\d+)", re.IGNORECASE
    )

    # ISSN patterns
    ISSN_PATTERN = re.compile(r"(\d{4}-\d{3}[\dX])", re.IGNORECASE)

    # ISBN patterns
    ISBN_PATTERN = re.compile(
        r"(?:ISBN[-:\s]?)?((?:\d{9}[\dX])|(?:\d{13}))", re.IGNORECASE
    )

    def extract_from_entry(self, entry: "BibTeXEntry") -> list[ExtractedIdentifier]:
        """Extract all identifiers from a BibTeX entry."""
        identifiers: list[ExtractedIdentifier] = []

        # Check DOI field
        if entry.has_field("doi"):
            doi_value = entry.get_field("doi")
            if doi_value:
                doi_id = self.extract_doi(doi_value)
                if doi_id:
                    identifiers.append(ExtractedIdentifier("doi", doi_id, "doi"))

        # Check URL field for identifiers
        if entry.has_field("url"):
            url_value = entry.get_field("url")
            if url_value:
                url_identifiers = self.extract_from_url(url_value)
                for id_info in url_identifiers:
                    id_info.source_field = "url"
                    identifiers.append(id_info)

        # Check note field
        if entry.has_field("note"):
            note_value = entry.get_field("note")
            if note_value:
                note_identifiers = self.extract_from_text(note_value)
                for id_info in note_identifiers:
                    id_info.source_field = "note"
                    identifiers.append(id_info)

        # Check eprint field for arXiv
        if entry.has_field("eprint"):
            eprint_value = entry.get_field("eprint")
            if eprint_value:
                arxiv_id = self.extract_arxiv(eprint_value)
                if arxiv_id:
                    identifiers.append(ExtractedIdentifier("arxiv", arxiv_id, "eprint"))

        # Check ISSN field
        if entry.has_field("issn"):
            issn_value = entry.get_field("issn")
            if issn_value:
                issn_id = self.extract_issn(issn_value)
                if issn_id:
                    identifiers.append(ExtractedIdentifier("issn", issn_id, "issn"))

        # Check ISBN field
        if entry.has_field("isbn"):
            isbn_value = entry.get_field("isbn")
            if isbn_value:
                isbn_id = self.extract_isbn(isbn_value)
                if isbn_id:
                    identifiers.append(ExtractedIdentifier("isbn", isbn_id, "isbn"))

        logger.debug(f"Extracted {len(identifiers)} identifiers from entry {entry.key}")
        return identifiers

    def extract_doi(self, text: str) -> str | None:
        """Extract DOI from text."""
        # First try to extract from DOI URL
        url_match = self.DOI_URL_PATTERN.search(text)
        if url_match:
            return url_match.group(1)

        # Then try direct DOI pattern
        match = self.DOI_PATTERN.search(text)
        if match:
            return match.group(0)

        return None

    def extract_arxiv(self, text: str) -> str | None:
        """Extract arXiv ID from text."""
        # First try URL pattern
        url_match = self.ARXIV_URL_PATTERN.search(text)
        if url_match:
            return url_match.group(1)

        # Then try direct pattern
        match = self.ARXIV_PATTERN.search(text)
        if match:
            return match.group(1)

        return None

    def extract_pmid(self, text: str) -> str | None:
        """Extract PMID from text."""
        # First try URL pattern
        url_match = self.PMID_URL_PATTERN.search(text)
        if url_match:
            return url_match.group(1)

        # Then try direct pattern
        match = self.PMID_PATTERN.search(text)
        if match:
            return match.group(1)

        return None

    def extract_issn(self, text: str) -> str | None:
        """Extract ISSN from text."""
        match = self.ISSN_PATTERN.search(text)
        if match:
            issn = match.group(1)
            # Validate ISSN checksum
            if self.validate_issn(issn):
                return issn

        return None

    def extract_isbn(self, text: str) -> str | None:
        """Extract ISBN from text."""
        match = self.ISBN_PATTERN.search(text)
        if match:
            isbn = match.group(1)
            # Validate ISBN checksum
            if self.validate_isbn(isbn):
                return isbn

        return None

    def extract_from_url(self, url: str) -> list[ExtractedIdentifier]:
        """Extract identifiers from URL."""
        identifiers: list[ExtractedIdentifier] = []

        # DOI from URL
        doi = self.extract_doi(url)
        if doi:
            identifiers.append(ExtractedIdentifier("doi", doi, "url"))

        # arXiv from URL
        arxiv = self.extract_arxiv(url)
        if arxiv:
            identifiers.append(ExtractedIdentifier("arxiv", arxiv, "url"))

        # PMID from URL
        pmid = self.extract_pmid(url)
        if pmid:
            identifiers.append(ExtractedIdentifier("pmid", pmid, "url"))

        return identifiers

    def extract_from_text(self, text: str) -> list[ExtractedIdentifier]:
        """Extract identifiers from free text."""
        identifiers: list[ExtractedIdentifier] = []

        # DOI in text
        doi = self.extract_doi(text)
        if doi:
            identifiers.append(ExtractedIdentifier("doi", doi, "text", 0.8))

        # arXiv in text
        arxiv = self.extract_arxiv(text)
        if arxiv:
            identifiers.append(ExtractedIdentifier("arxiv", arxiv, "text", 0.8))

        # PMID in text
        pmid = self.extract_pmid(text)
        if pmid:
            identifiers.append(ExtractedIdentifier("pmid", pmid, "text", 0.8))

        return identifiers

    @staticmethod
    def validate_issn(issn: str) -> bool:
        """Validate ISSN checksum."""
        if len(issn) != 9 or issn[4] != "-":
            return False

        digits = issn.replace("-", "")
        if len(digits) != 8:
            return False

        # Calculate checksum
        checksum = 0
        for i, char in enumerate(digits[:7]):
            if not char.isdigit():
                return False
            checksum += int(char) * (8 - i)

        remainder = checksum % 11
        if remainder == 0:
            expected = "0"
        elif remainder == 1:
            expected = "X"
        else:
            expected = str(11 - remainder)

        return digits[7].upper() == expected

    @staticmethod
    def validate_isbn(isbn: str) -> bool:
        """Validate ISBN checksum."""
        digits = "".join(c for c in isbn if c.isdigit() or c.upper() == "X")

        if len(digits) == 10:
            # ISBN-10
            checksum = 0
            for i, char in enumerate(digits[:9]):
                checksum += int(char) * (10 - i)

            check_digit = (11 - (checksum % 11)) % 11
            expected = "X" if check_digit == 10 else str(check_digit)
            return digits[9].upper() == expected

        elif len(digits) == 13:
            # ISBN-13
            checksum = 0
            for i, char in enumerate(digits[:12]):
                weight = 1 if i % 2 == 0 else 3
                checksum += int(char) * weight

            check_digit = (10 - (checksum % 10)) % 10
            return int(digits[12]) == check_digit

        return False

    def get_canonical_url(self, identifier_type: str, value: str) -> str | None:
        """Get canonical URL for an identifier."""
        if identifier_type == "doi":
            return f"https://doi.org/{value}"
        elif identifier_type == "arxiv":
            return f"https://arxiv.org/abs/{value}"
        elif identifier_type == "pmid":
            return f"https://pubmed.ncbi.nlm.nih.gov/{value}/"

        return None
