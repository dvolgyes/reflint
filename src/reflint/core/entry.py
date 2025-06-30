"""BibTeX entry wrapper with enhanced functionality."""

from typing import Any


class BibTeXEntry:
    """Wrapper for bibtex entry with enhanced functionality."""

    def __init__(self, entry_dict: dict[str, Any]) -> None:
        """Initialize with a bibtexparser entry dictionary."""
        self._entry = entry_dict
        self._metadata: dict[str, Any] = {}

    @property
    def key(self) -> str:
        """Get the entry key."""
        return self._entry.get("ID", "")

    @property
    def entry_type(self) -> str:
        """Get the entry type (article, book, etc.)."""
        return self._entry.get("ENTRYTYPE", "").lower()

    @property
    def fields(self) -> dict[str, str]:
        """Get all fields as a dictionary."""
        # Return all fields except ID and ENTRYTYPE
        return {k: v for k, v in self._entry.items() if k not in ["ID", "ENTRYTYPE"]}

    def get_field(self, field_name: str) -> str | None:
        """Get a specific field value."""
        return self._entry.get(field_name.lower())

    def set_field(self, field_name: str, value: str) -> None:
        """Set a field value."""
        self._entry[field_name.lower()] = value

    def has_field(self, field_name: str) -> bool:
        """Check if entry has a specific field."""
        return field_name.lower() in self._entry

    def get_metadata(self, key: str) -> Any:
        """Get metadata value."""
        return self._metadata.get(key)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self._metadata[key] = value

    def to_bibtex(self) -> str:
        """Convert to BibTeX string representation."""
        import bibtexparser
        from bibtexparser.bibdatabase import BibDatabase

        db = BibDatabase()
        db.entries = [self._entry]
        return bibtexparser.dumps(db)

    def __str__(self) -> str:
        """String representation."""
        return f"BibTeXEntry({self.key}, {self.entry_type})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"BibTeXEntry(key='{self.key}', type='{self.entry_type}', fields={len(self.fields)})"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return dict(self._entry)

    def get_all_fields(self) -> list[str]:
        """Get list of all field names."""
        return [k for k in self._entry.keys() if k not in ["ID", "ENTRYTYPE"]]
