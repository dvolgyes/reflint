"""URL validation rule (U001)."""

import re
from urllib.parse import urlparse, ParseResult

from ..base import FieldValidationRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation


class URLValidationRule(FieldValidationRule):
    """Rule U001: Validate URL format and accessibility."""

    rule_id = "U001"
    severity = "warning"
    category = "content"
    description = "URLs should be properly formatted and use secure protocols"

    def __init__(self) -> None:
        super().__init__("url")

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate URL fields in the entry."""
        violations: list[RuleViolation] = []

        # Check main URL field
        if entry.has_field("url"):
            url_value = entry.get_field("url")
            if url_value:
                violations.extend(self.validate_field(entry, url_value))

        # Check DOI field for URL-like content
        if entry.has_field("doi"):
            doi_value = entry.get_field("doi")
            if doi_value and self._looks_like_url(doi_value):
                violations.extend(self._validate_doi_url(doi_value))

        # Check note field for URLs
        if entry.has_field("note"):
            note_value = entry.get_field("note")
            if note_value:
                violations.extend(self._validate_urls_in_text(note_value, "note"))

        return violations

    def validate_field(
        self, entry: BibTeXEntry, field_value: str
    ) -> list[RuleViolation]:
        """Validate URL field value."""
        violations: list[RuleViolation] = []

        # Remove common BibTeX formatting
        url_clean = field_value.strip("{}").strip()

        # Basic URL format validation
        violations.extend(self._validate_url_format(url_clean))

        return violations

    def _validate_url_format(self, url: str) -> list[RuleViolation]:
        """Validate URL format and structure."""
        violations: list[RuleViolation] = []

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="error",
                    message=f"Invalid URL format: '{url}'",
                    field="url",
                )
            )
            return violations

        # Check for scheme
        if not parsed.scheme:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="error",
                    message=f"URL missing protocol (http:// or https://): '{url}'",
                    field="url",
                    suggested_fix=f"https://{url}",
                )
            )
            return violations

        # Check for secure protocol
        if parsed.scheme.lower() == "http":
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="info",
                    message="Consider using HTTPS instead of HTTP for better security",
                    field="url",
                    suggested_fix=url.replace("http://", "https://", 1),
                )
            )
        elif parsed.scheme.lower() not in ["http", "https", "ftp", "ftps"]:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=f"Unusual URL scheme: '{parsed.scheme}'",
                    field="url",
                )
            )

        # Check for netloc (domain)
        if not parsed.netloc:
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="error",
                    message=f"URL missing domain: '{url}'",
                    field="url",
                )
            )

        # Check for suspicious URLs
        violations.extend(self._check_suspicious_urls(url, parsed))

        return violations

    def _check_suspicious_urls(
        self, url: str, parsed: ParseResult
    ) -> list[RuleViolation]:
        """Check for suspicious or problematic URLs."""
        violations: list[RuleViolation] = []

        # Check for URL shorteners
        shorteners = [
            "bit.ly",
            "tinyurl.com",
            "t.co",
            "goo.gl",
            "ow.ly",
            "short.link",
            "tiny.cc",
            "is.gd",
            "buff.ly",
        ]

        if any(shortener in parsed.netloc.lower() for shortener in shorteners):
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="warning",
                    message="URL shortener detected - consider using the full URL",
                    field="url",
                )
            )

        # Check for localhost/development URLs
        if parsed.netloc.lower() in [
            "localhost",
            "127.0.0.1",
        ] or parsed.netloc.startswith("192.168."):
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="error",
                    message="Local/development URL should not be used in published bibliography",
                    field="url",
                )
            )

        # Check for temporary file sharing services
        temp_services = [
            "wetransfer.com",
            "sendspace.com",
            "mediafire.com",
            "dropbox.com/s/",
        ]
        if any(service in url.lower() for service in temp_services):
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="warning",
                    message="Temporary file sharing URL may become invalid",
                    field="url",
                )
            )

        return violations

    def _validate_doi_url(self, doi_value: str) -> list[RuleViolation]:
        """Validate DOI field that looks like a URL."""
        violations: list[RuleViolation] = []

        if doi_value.startswith("http"):
            violations.append(
                RuleViolation(
                    rule_id=self.rule_id,
                    severity="info",
                    message="DOI field contains URL - consider extracting just the DOI identifier",
                    field="doi",
                    suggested_fix=self._extract_doi_from_url(doi_value),
                )
            )

        return violations

    def _extract_doi_from_url(self, url: str) -> str:
        """Extract DOI from URL."""
        # Common DOI URL patterns
        doi_match = re.search(r"doi\.org/(10\.\d+/.+)", url)
        if doi_match:
            return doi_match.group(1)

        dx_doi_match = re.search(r"dx\.doi\.org/(10\.\d+/.+)", url)
        if dx_doi_match:
            return dx_doi_match.group(1)

        return url  # Return original if can't extract

    def _validate_urls_in_text(self, text: str, field_name: str) -> list[RuleViolation]:
        """Find and validate URLs within text fields."""
        violations: list[RuleViolation] = []

        # Simple URL detection pattern
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?]'
        urls = re.findall(url_pattern, text)

        for url in urls:
            violations.extend(self._validate_url_format(url))
            # Change field reference to the actual field
            for violation in violations[-len(self._validate_url_format(url)) :]:
                violation.field = field_name

        return violations

    def _looks_like_url(self, text: str) -> bool:
        """Check if text looks like a URL."""
        return text.startswith(("http://", "https://", "ftp://", "ftps://"))

    def can_fix(self) -> bool:
        """This rule can fix some URL issues."""
        return True

    def fix(self, entry: BibTeXEntry) -> BibTeXEntry:
        """Fix URL formatting issues."""
        # Fix URL field
        if entry.has_field("url"):
            url_value = entry.get_field("url")
            if url_value:
                fixed_url = self._fix_url(url_value)
                if fixed_url != url_value:
                    entry.set_field("url", fixed_url)

        # Fix DOI field if it contains URL
        if entry.has_field("doi"):
            doi_value = entry.get_field("doi")
            if doi_value and self._looks_like_url(doi_value):
                extracted_doi = self._extract_doi_from_url(doi_value)
                if extracted_doi != doi_value:
                    entry.set_field("doi", extracted_doi)

        return entry

    def _fix_url(self, url: str) -> str:
        """Fix common URL issues."""
        url_clean = url.strip("{}").strip()

        # Add protocol if missing
        if not url_clean.startswith(("http://", "https://", "ftp://", "ftps://")):
            url_clean = f"https://{url_clean}"

        return url_clean
