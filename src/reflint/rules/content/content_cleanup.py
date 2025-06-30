"""Content cleanup and text sanitization rule."""

import re
from typing import ClassVar

from ...core.validation import RuleViolation
from ..base import BaseRule


class ContentCleanupRule(BaseRule):
    """Rule for cleaning up and sanitizing text content in BibTeX fields."""

    rule_id: ClassVar[str] = "C003"
    severity: ClassVar[str] = "info"
    category: ClassVar[str] = "content"
    description: ClassVar[str] = "Clean up and sanitize text content"

    # Fields that should be cleaned up
    CLEANUP_FIELDS = [
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
        "ID",  # Entry ID needs special handling
    ]

    def validate(self, entry):
        """Check for content that needs cleanup."""
        violations = []

        for field_name in self.CLEANUP_FIELDS:
            # Special handling for ID field since it's uppercase
            if field_name == "ID":
                if "ID" in entry._entry:
                    field_value = entry._entry["ID"]
                    # Handle empty strings too
                    if field_value is not None:
                        cleaned_value, cleanup_details = self._sanitize_entry_id(field_value)
                        if cleanup_details:
                            cleanup_description = ", ".join(cleanup_details)
                            violations.append(
                                RuleViolation(
                                    rule_id=self.rule_id,
                                    severity=self.severity,
                                    message=f"Content cleanup needed in {field_name}: {cleanup_description}",
                                    field=field_name,
                                    suggested_fix=cleaned_value,
                                )
                            )
            elif entry.has_field(field_name):
                field_value = entry.get_field(field_name)
                if field_value:
                    cleaned_value, cleanup_details = self._cleanup_text_content(field_value)

                    if cleanup_details:
                        # Create detailed message about cleanup operations
                        cleanup_description = ", ".join(cleanup_details)

                        violations.append(
                            RuleViolation(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Content cleanup needed in {field_name}: {cleanup_description}",
                                field=field_name,
                                suggested_fix=cleaned_value,
                            )
                        )

        return violations

    def _cleanup_text_content(self, text: str) -> tuple[str, list[str]]:
        """
        Clean up text content with various sanitization operations.
        
        Returns:
            Tuple of (cleaned_text, list_of_cleanup_operations)
        """
        cleaned_text = text
        cleanup_operations = []

        # Remove XML tags
        xml_pattern = re.compile(r'<[^>]+>')
        if xml_pattern.search(cleaned_text):
            cleaned_text = xml_pattern.sub('', cleaned_text)
            cleanup_operations.append("removed XML tags")

        # Remove HTML entities
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&nbsp;': ' ',
            '&#8217;': "'",  # Right single quotation mark
            '&#8220;': '"',  # Left double quotation mark
            '&#8221;': '"',  # Right double quotation mark
            '&#8211;': '–',  # En dash
            '&#8212;': '—',  # Em dash
        }
        
        original_text = cleaned_text
        for entity, replacement in html_entities.items():
            if entity in cleaned_text:
                cleaned_text = cleaned_text.replace(entity, replacement)
        
        if original_text != cleaned_text:
            cleanup_operations.append("converted HTML entities")

        # Normalize whitespace (multiple spaces to single space)
        original_text = cleaned_text
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        if original_text != cleaned_text:
            cleanup_operations.append("normalized whitespace")

        # Remove leading/trailing whitespace
        original_text = cleaned_text
        cleaned_text = cleaned_text.strip()
        if original_text != cleaned_text:
            cleanup_operations.append("trimmed whitespace")

        # Remove zero-width characters and other invisible Unicode
        invisible_chars = [
            '\u200b',  # Zero-width space
            '\u200c',  # Zero-width non-joiner
            '\u200d',  # Zero-width joiner
            '\u2060',  # Word joiner
            '\ufeff',  # Byte order mark
            '\u00ad',  # Soft hyphen
        ]
        
        original_text = cleaned_text
        for char in invisible_chars:
            if char in cleaned_text:
                cleaned_text = cleaned_text.replace(char, '')
        
        if original_text != cleaned_text:
            cleanup_operations.append("removed invisible characters")

        # Fix common encoding issues (order matters - longer/specific fixes first)
        encoding_fixes = [
            ('FranÃ§ois', 'François'),  # More specific fix
            ('MÃ¼ller', 'Müller'),  # More specific fix
            ('MarÃ­a', 'María'),  # More specific fix
            ('MarÃa', 'María'),  # After invisible char removal (soft hyphen gone)
            ('Ã¡', 'á'),  # á encoded as UTF-8 then decoded as Latin-1
            ('Ã©', 'é'),  # é encoded as UTF-8 then decoded as Latin-1
            ('Ã­', 'í'),  # í encoded as UTF-8 then decoded as Latin-1
            ('Ã³', 'ó'),  # ó encoded as UTF-8 then decoded as Latin-1
            ('Ãº', 'ú'),  # ú encoded as UTF-8 then decoded as Latin-1
            ('Ã±', 'ñ'),  # ñ encoded as UTF-8 then decoded as Latin-1
            ('Ã¤', 'ä'),  # ä encoded as UTF-8 then decoded as Latin-1
            ('Ã¶', 'ö'),  # ö encoded as UTF-8 then decoded as Latin-1
            ('Ã¼', 'ü'),  # ü encoded as UTF-8 then decoded as Latin-1
            ('ÃŸ', 'ß'),  # ß encoded as UTF-8 then decoded as Latin-1
        ]
        
        original_text = cleaned_text
        for broken, fixed in encoding_fixes:
            if broken in cleaned_text:
                cleaned_text = cleaned_text.replace(broken, fixed)
        
        if original_text != cleaned_text:
            cleanup_operations.append("fixed encoding issues")

        # Remove or fix special character patterns
        # Remove standalone backslashes that aren't part of LaTeX commands
        original_text = cleaned_text
        # Only remove backslashes not followed by a letter (LaTeX commands)
        cleaned_text = re.sub(r'\\(?![a-zA-Z])', '', cleaned_text)
        if original_text != cleaned_text:
            cleanup_operations.append("removed stray backslashes")

        # Fix multiple punctuation marks
        original_text = cleaned_text
        cleaned_text = re.sub(r'[.]{3,}', '...', cleaned_text)  # Multiple dots to ellipsis
        cleaned_text = re.sub(r'[!]{2,}', '!', cleaned_text)     # Multiple exclamations
        cleaned_text = re.sub(r'[?]{2,}', '?', cleaned_text)     # Multiple questions
        if original_text != cleaned_text:
            cleanup_operations.append("fixed punctuation patterns")

        return cleaned_text, cleanup_operations

    def _sanitize_entry_id(self, entry_id: str) -> tuple[str, list[str]]:
        """
        Sanitize entry ID by removing problematic characters.
        
        Returns:
            Tuple of (sanitized_id, list_of_cleanup_operations)
        """
        original_id = entry_id
        sanitized_id = entry_id
        cleanup_operations = []

        # Remove problematic characters from entry ID  
        # Keep only alphanumeric, underscore, hyphen, colon, period
        cleaned_id = re.sub(r'[^a-zA-Z0-9_:.-]', '', sanitized_id)
        if cleaned_id != sanitized_id:
            sanitized_id = cleaned_id
            cleanup_operations.append("removed invalid ID characters")

        # Ensure ID doesn't start with a number (BibTeX requirement)
        if sanitized_id and sanitized_id[0].isdigit():
            sanitized_id = 'entry_' + sanitized_id
            cleanup_operations.append("added prefix to numeric ID")

        # Ensure ID is not empty
        if not sanitized_id:
            sanitized_id = 'entry_unknown'
            cleanup_operations.append("replaced empty ID")

        # Limit ID length to reasonable bounds
        if len(sanitized_id) > 100:
            sanitized_id = sanitized_id[:100]
            cleanup_operations.append("truncated long ID")

        return sanitized_id, cleanup_operations