"""Fuzzy matching algorithms for paper identification and metadata reconciliation."""

import re
from dataclasses import dataclass
from typing import Any
from difflib import SequenceMatcher

from ..core.entry import BibTeXEntry
from .base import LookupResult


@dataclass
class SimilarityScore:
    """Detailed similarity score breakdown."""

    overall: float
    title_similarity: float
    author_similarity: float
    year_similarity: float
    venue_similarity: float

    # Component weights used in calculation
    weights: dict[str, float]

    # Detailed breakdown for debugging
    details: dict[str, Any]


class FuzzyMatcher:
    """Advanced fuzzy matching for bibliographic entries."""

    def __init__(self):
        # Default weights for similarity components
        self.default_weights = {
            "title": 0.40,
            "author": 0.30,
            "year": 0.15,
            "venue": 0.15,
        }

        # Thresholds for automatic matching
        self.high_confidence_threshold = 0.90
        self.medium_confidence_threshold = 0.75
        self.low_confidence_threshold = 0.60

    def calculate_similarity(
        self,
        entry1: BibTeXEntry,
        entry2: BibTeXEntry,
        weights: dict[str, float] | None = None,
    ) -> SimilarityScore:
        """Calculate comprehensive similarity score between two entries."""

        if weights is None:
            weights = self.default_weights.copy()

        # Calculate individual component similarities
        title_sim = self._calculate_title_similarity(entry1, entry2)
        author_sim = self._calculate_author_similarity(entry1, entry2)
        year_sim = self._calculate_year_similarity(entry1, entry2)
        venue_sim = self._calculate_venue_similarity(entry1, entry2)

        # Calculate weighted overall similarity
        overall_sim = (
            title_sim * weights.get("title", 0.40)
            + author_sim * weights.get("author", 0.30)
            + year_sim * weights.get("year", 0.15)
            + venue_sim * weights.get("venue", 0.15)
        )

        # Collect details for debugging
        details = {
            "entry1_key": entry1.key,
            "entry2_key": entry2.key,
            "title1": entry1.get_field("title"),
            "title2": entry2.get_field("title"),
            "author1": entry1.get_field("author"),
            "author2": entry2.get_field("author"),
            "year1": entry1.get_field("year"),
            "year2": entry2.get_field("year"),
            "venue1": self._get_venue_field(entry1),
            "venue2": self._get_venue_field(entry2),
        }

        return SimilarityScore(
            overall=overall_sim,
            title_similarity=title_sim,
            author_similarity=author_sim,
            year_similarity=year_sim,
            venue_similarity=venue_sim,
            weights=weights,
            details=details,
        )

    def _calculate_title_similarity(
        self, entry1: BibTeXEntry, entry2: BibTeXEntry
    ) -> float:
        """Calculate title similarity with text normalization."""
        title1 = entry1.get_field("title")
        title2 = entry2.get_field("title")

        if not title1 or not title2:
            return 0.0

        # Normalize titles
        norm_title1 = self._normalize_title(title1)
        norm_title2 = self._normalize_title(title2)

        if not norm_title1 or not norm_title2:
            return 0.0

        # Calculate sequence similarity
        similarity = SequenceMatcher(None, norm_title1, norm_title2).ratio()

        # Boost similarity for exact substring matches
        if norm_title1 in norm_title2 or norm_title2 in norm_title1:
            similarity = max(similarity, 0.85)

        # Check for key word overlap
        words1 = set(norm_title1.split())
        words2 = set(norm_title2.split())

        if words1 and words2:
            word_overlap = len(words1 & words2) / len(words1 | words2)
            # Combine sequence similarity with word overlap
            similarity = 0.7 * similarity + 0.3 * word_overlap

        return min(similarity, 1.0)

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        if not title:
            return ""

        # Convert to lowercase
        normalized = title.lower()

        # Remove common punctuation and special characters
        normalized = re.sub(r"[^\w\s]", " ", normalized)

        # Remove common stop words at the beginning
        stop_words = ["a", "an", "the", "on", "of", "in", "for", "to", "with"]
        words = normalized.split()
        while words and words[0] in stop_words:
            words.pop(0)

        # Remove extra whitespace
        normalized = " ".join(words)

        return normalized.strip()

    def _calculate_author_similarity(
        self, entry1: BibTeXEntry, entry2: BibTeXEntry
    ) -> float:
        """Calculate author similarity with name normalization."""
        authors1 = entry1.get_field("author")
        authors2 = entry2.get_field("author")

        if not authors1 or not authors2:
            return 0.0

        # Parse author lists
        author_list1 = self._parse_authors(authors1)
        author_list2 = self._parse_authors(authors2)

        if not author_list1 or not author_list2:
            return 0.0

        # Calculate author overlap using normalized names
        norm_authors1 = [self._normalize_author_name(name) for name in author_list1]
        norm_authors2 = [self._normalize_author_name(name) for name in author_list2]

        # Remove empty normalized names
        norm_authors1 = [name for name in norm_authors1 if name]
        norm_authors2 = [name for name in norm_authors2 if name]

        if not norm_authors1 or not norm_authors2:
            return 0.0

        # Calculate Jaccard similarity
        set1 = set(norm_authors1)
        set2 = set(norm_authors2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        jaccard_sim = intersection / union

        # Also check for partial name matches (e.g., "J. Smith" vs "John Smith")
        partial_matches = 0
        for author1 in norm_authors1:
            for author2 in norm_authors2:
                if self._authors_partially_match(author1, author2):
                    partial_matches += 1
                    break

        partial_sim = partial_matches / max(len(norm_authors1), len(norm_authors2))

        # Combine Jaccard and partial matching
        return max(jaccard_sim, partial_sim * 0.8)

    def _parse_authors(self, author_string: str) -> list[str]:
        """Parse author string into individual names."""
        if not author_string:
            return []

        # Split by "and" (BibTeX convention)
        authors = re.split(r"\s+and\s+", author_string, flags=re.IGNORECASE)

        # Clean up each author name
        cleaned_authors = []
        for author in authors:
            cleaned = author.strip()
            if cleaned:
                cleaned_authors.append(cleaned)

        return cleaned_authors

    def _normalize_author_name(self, name: str) -> str:
        """Normalize author name for comparison."""
        if not name:
            return ""

        # Remove extra whitespace and punctuation, including hyphens
        normalized = re.sub(r"[^\w\s]", " ", name)
        normalized = " ".join(normalized.split())

        # Convert to lowercase
        normalized = normalized.lower()

        return normalized

    def _authors_partially_match(self, name1: str, name2: str) -> bool:
        """Check if two author names partially match."""
        if not name1 or not name2:
            return False

        # Split into components
        parts1 = name1.split()
        parts2 = name2.split()

        # Check for last name match (assumes last word is last name)
        if parts1 and parts2 and parts1[-1] == parts2[-1]:
            # Check for first initial match
            if len(parts1) > 1 and len(parts2) > 1:
                first1 = parts1[0]
                first2 = parts2[0]

                # Check if one is an initial of the other
                if (len(first1) == 1 and first2.startswith(first1)) or (
                    len(first2) == 1 and first1.startswith(first2)
                ):
                    return True

                # Check if first names match exactly
                if first1 == first2:
                    return True

        return False

    def _calculate_year_similarity(
        self, entry1: BibTeXEntry, entry2: BibTeXEntry
    ) -> float:
        """Calculate year similarity."""
        year1 = entry1.get_field("year")
        year2 = entry2.get_field("year")

        if not year1 or not year2:
            return 0.5  # Neutral score when one is missing

        try:
            y1 = int(year1)
            y2 = int(year2)

            if y1 == y2:
                return 1.0
            elif abs(y1 - y2) == 1:
                return 0.8  # Off by one year (common in publication lag)
            elif abs(y1 - y2) <= 2:
                return 0.6  # Close but not exact
            else:
                return 0.0  # Too far apart

        except ValueError:
            # Non-numeric years, fall back to string comparison
            return 1.0 if year1.strip() == year2.strip() else 0.0

    def _calculate_venue_similarity(
        self, entry1: BibTeXEntry, entry2: BibTeXEntry
    ) -> float:
        """Calculate venue similarity (journal, booktitle, etc.)."""
        venue1 = self._get_venue_field(entry1)
        venue2 = self._get_venue_field(entry2)

        if not venue1 or not venue2:
            return 0.5  # Neutral score when one is missing

        # Normalize venue names
        norm_venue1 = self._normalize_venue(venue1)
        norm_venue2 = self._normalize_venue(venue2)

        if not norm_venue1 or not norm_venue2:
            return 0.5

        # Calculate string similarity
        similarity = SequenceMatcher(None, norm_venue1, norm_venue2).ratio()

        # Check for acronym matches on both original and normalized strings
        if self._venues_match_acronym(venue1, venue2) or self._venues_match_acronym(
            norm_venue1, norm_venue2
        ):
            similarity = max(similarity, 0.85)

        return similarity

    def _get_venue_field(self, entry: BibTeXEntry) -> str | None:
        """Get the appropriate venue field for an entry."""
        # Try different venue fields in order of preference
        venue_fields = ["journal", "booktitle", "series", "publisher"]

        for field in venue_fields:
            value = entry.get_field(field)
            if value:
                return value

        return None

    def _normalize_venue(self, venue: str) -> str:
        """Normalize venue name for comparison."""
        if not venue:
            return ""

        # Convert to lowercase
        normalized = venue.lower()

        # Remove common words and abbreviations
        remove_patterns = [
            r"\bproceedings\s+of\s+the\b",
            r"\bproceedings\s+of\b",
            r"\binternational\b",
            r"\bconference\s+on\b",
            r"\bjournal\s+of\b",
            r"\btransactions\s+on\b",
            r"\bannual\b",
            r"\bieee\b",
            r"\bacm\b",
        ]

        for pattern in remove_patterns:
            normalized = re.sub(pattern, "", normalized)

        # Remove punctuation and extra whitespace
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = " ".join(normalized.split())

        return normalized.strip()

    def _venues_match_acronym(self, venue1: str, venue2: str) -> bool:
        """Check if venues match by acronym."""
        # Simple heuristic: if one is much shorter, check if it could be an acronym

        short_venue = venue1 if len(venue1) < len(venue2) else venue2
        long_venue = venue2 if len(venue1) < len(venue2) else venue1

        if len(short_venue) <= 10 and len(long_venue) > len(short_venue) * 2:
            # Extract first letters of significant words from long venue
            words = [
                word for word in long_venue.split() if len(word) > 2
            ]  # Skip short words
            if len(words) >= len(short_venue):
                acronym = "".join(word[0] for word in words)
                if acronym.upper() == short_venue.upper():
                    return True

                # Also try with all words (including short ones)
                all_words = long_venue.split()
                if len(all_words) >= len(short_venue):
                    full_acronym = "".join(word[0] for word in all_words)
                    if full_acronym.upper() == short_venue.upper():
                        return True

        return False

    def find_best_matches(
        self,
        target_entry: BibTeXEntry,
        candidate_results: list[LookupResult],
        max_results: int = 5,
    ) -> list[tuple[LookupResult, SimilarityScore]]:
        """Find best matching results for a target entry."""

        matches = []

        for result in candidate_results:
            if result.entry:
                similarity = self.calculate_similarity(target_entry, result.entry)
                matches.append((result, similarity))

        # Sort by overall similarity (descending)
        matches.sort(key=lambda x: x[1].overall, reverse=True)

        return matches[:max_results]

    def is_high_confidence_match(self, similarity: SimilarityScore) -> bool:
        """Check if similarity indicates high confidence match."""
        return similarity.overall >= self.high_confidence_threshold

    def is_probable_match(self, similarity: SimilarityScore) -> bool:
        """Check if similarity indicates probable match."""
        return similarity.overall >= self.medium_confidence_threshold

    def is_possible_match(self, similarity: SimilarityScore) -> bool:
        """Check if similarity indicates possible match."""
        return similarity.overall >= self.low_confidence_threshold

    def get_match_confidence_level(self, similarity: SimilarityScore) -> str:
        """Get human-readable confidence level."""
        if self.is_high_confidence_match(similarity):
            return "high"
        elif self.is_probable_match(similarity):
            return "medium"
        elif self.is_possible_match(similarity):
            return "low"
        else:
            return "very_low"


# Global matcher instance
_global_fuzzy_matcher = FuzzyMatcher()


def get_fuzzy_matcher() -> FuzzyMatcher:
    """Get the global fuzzy matcher instance."""
    return _global_fuzzy_matcher
