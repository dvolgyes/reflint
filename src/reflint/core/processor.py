"""Main processor for BibTeX file operations."""

from pathlib import Path
from typing import Any, TextIO, cast
from collections.abc import Iterator
import sys

from loguru import logger
import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter

from .entry import BibTeXEntry
from .validation import ValidationResult
from ..rules import get_registry


class BibTeXProcessor:
    """Main processor for BibTeX file operations."""

    def __init__(self) -> None:
        """Initialize the processor."""
        self.entries: list[BibTeXEntry] = []
        self._database: BibDatabase | None = None

    def load_from_file(self, file_path: Path) -> None:
        """Load BibTeX entries from a file."""
        logger.info(f"Loading BibTeX file: {file_path}")

        try:
            with file_path.open(encoding="utf-8") as f:
                self._load_from_stream(f)
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    def load_from_string(self, bibtex_content: str) -> None:
        """Load BibTeX entries from a string."""
        logger.debug("Loading BibTeX from string")

        try:
            self._database = bibtexparser.loads(bibtex_content)
            self.entries = [BibTeXEntry(entry) for entry in self._database.entries]
            logger.info(f"Loaded {len(self.entries)} entries")
        except Exception as e:
            logger.error(f"Error parsing BibTeX content: {e}")
            raise

    def load_from_stdin(self) -> None:
        """Load BibTeX entries from stdin."""
        logger.info("Loading BibTeX from stdin")
        self._load_from_stream(sys.stdin)

    def _load_from_stream(self, stream: TextIO) -> None:
        """Load BibTeX entries from a text stream."""
        content = stream.read()
        self.load_from_string(content)

    def save_to_file(self, file_path: Path) -> None:
        """Save BibTeX entries to a file."""
        logger.info(f"Saving BibTeX file: {file_path}")

        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(self.to_bibtex())
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            raise

    def save_to_stdout(self) -> None:
        """Save BibTeX entries to stdout."""
        logger.debug("Writing BibTeX to stdout")
        sys.stdout.write(f"{self.to_bibtex()}\n")

    def to_bibtex(self) -> str:
        """Convert all entries to BibTeX string."""
        if not self._database:
            self._database = BibDatabase()

        # Update database with current entries
        self._database.entries = [entry._entry for entry in self.entries]

        # Use custom writer for better formatting
        writer = BibTexWriter()
        writer.indent = "  "
        writer.align_values = True

        return cast("str", bibtexparser.dumps(self._database, writer))

    def get_entry_by_key(self, key: str) -> BibTeXEntry | None:
        """Get an entry by its key."""
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None

    def add_entry(self, entry: BibTeXEntry) -> None:
        """Add a new entry."""
        self.entries.append(entry)
        if self._database:
            self._database.entries.append(entry._entry)

    def remove_entry(self, key: str) -> bool:
        """Remove an entry by key. Returns True if removed, False if not found."""
        for i, entry in enumerate(self.entries):
            if entry.key == key:
                del self.entries[i]
                if self._database:
                    # Remove from database as well
                    self._database.entries = [
                        e for e in self._database.entries if e.get("ID") != key
                    ]
                return True
        return False

    def get_entry_count(self) -> int:
        """Get the number of entries."""
        return len(self.entries)

    def get_entry_types(self) -> list[str]:
        """Get list of unique entry types."""
        return list({entry.entry_type for entry in self.entries})

    def filter_entries_by_type(self, entry_type: str) -> list[BibTeXEntry]:
        """Filter entries by type."""
        return [
            entry for entry in self.entries if entry.entry_type == entry_type.lower()
        ]

    def __len__(self) -> int:
        """Return number of entries."""
        return len(self.entries)

    def __iter__(self) -> Iterator[BibTeXEntry]:
        """Iterate over entries."""
        return iter(self.entries)

    def __getitem__(self, index: int) -> BibTeXEntry:
        """Get entry by index."""
        return self.entries[index]

    def validate_entries(
        self, rule_filter: list[str] | None = None
    ) -> list[ValidationResult]:
        """Validate all entries using registered rules."""
        logger.info(f"Validating {len(self.entries)} entries")

        registry = get_registry()
        results: list[ValidationResult] = []

        for entry in self.entries:
            result = registry.validate_entry(entry, rule_filter)
            results.append(result)

            # Log validation summary
            if result.has_errors:
                logger.warning(f"Entry '{entry.key}': {result.error_count} errors")
            elif result.has_warnings:
                logger.info(f"Entry '{entry.key}': {result.warning_count} warnings")

        # Log overall summary
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)
        total_info = sum(r.info_count for r in results)

        logger.info(
            f"Validation complete: {total_errors} errors, {total_warnings} warnings, {total_info} info"
        )

        return results

    def get_validation_summary(self, results: list[ValidationResult]) -> dict[str, Any]:
        """Get summary statistics from validation results."""
        return {
            "total_entries": len(results),
            "entries_with_errors": sum(1 for r in results if r.has_errors),
            "entries_with_warnings": sum(1 for r in results if r.has_warnings),
            "total_errors": sum(r.error_count for r in results),
            "total_warnings": sum(r.warning_count for r in results),
            "total_info": sum(r.info_count for r in results),
        }
