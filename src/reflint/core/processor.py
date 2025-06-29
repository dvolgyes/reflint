"""Main processor for BibTeX file operations."""

from pathlib import Path
from typing import TextIO
import sys

from loguru import logger
import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter

from .entry import BibTeXEntry


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
            with open(file_path, encoding="utf-8") as f:
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
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.to_bibtex())
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            raise

    def save_to_stdout(self) -> None:
        """Save BibTeX entries to stdout."""
        logger.debug("Writing BibTeX to stdout")
        print(self.to_bibtex())

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

        return bibtexparser.dumps(self._database, writer)

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

    def __iter__(self):  # type: ignore[no-untyped-def]
        """Iterate over entries."""
        return iter(self.entries)

    def __getitem__(self, index: int) -> BibTeXEntry:
        """Get entry by index."""
        return self.entries[index]
