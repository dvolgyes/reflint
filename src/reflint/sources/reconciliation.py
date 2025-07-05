"""Multi-source data reconciliation and conflict resolution."""

from dataclasses import dataclass
from typing import Any
from enum import Enum

from loguru import logger

from .base import LookupResult
from ..core.entry import BibTeXEntry
from ..utils.issn_lookup import ISSNLookupService


class ConflictStrategy(Enum):
    """Strategies for resolving data conflicts."""

    HIGHEST_CONFIDENCE = "highest_confidence"
    MOST_COMPLETE = "most_complete"
    LONGEST_VALUE = "longest_value"
    MANUAL_REVIEW = "manual_review"
    SOURCE_PRIORITY = "source_priority"


@dataclass
class FieldConflict:
    """Represents a conflict between field values from different sources."""

    field_name: str
    values: dict[str, Any]  # source_name -> value
    confidences: dict[str, float]  # source_name -> confidence
    selected_value: Any | None = None
    selected_source: str | None = None
    strategy_used: ConflictStrategy | None = None
    requires_manual_review: bool = False


@dataclass
class ReconciledEntry:
    """Result of multi-source data reconciliation."""

    entry: BibTeXEntry
    conflicts: list[FieldConflict]
    sources_used: list[str]
    confidence_score: float
    completeness_score: float
    manual_review_required: bool = False


class DataReconciler:
    """Reconcile data from multiple sources into a unified entry."""

    def __init__(self, source_priorities: dict[str, int] | None = None, email: str | None = None) -> None:
        """Initialize reconciler.

        Args:
            source_priorities: Dictionary mapping source names to priority values (higher = more trusted)
            email: Email for ISSN lookup service (optional)
        """
        self.source_priorities = source_priorities or {
            "crossref": 10,
            "semantic_scholar": 8,
            "pubmed": 9,
            "arxiv": 6,
            "openalex": 7,
        }
        
        # ISSN lookup service for journal name resolution
        self.email = email
        self._issn_service = None

        # Field-specific conflict resolution strategies
        self.field_strategies = {
            "doi": ConflictStrategy.HIGHEST_CONFIDENCE,
            "title": ConflictStrategy.LONGEST_VALUE,
            "author": ConflictStrategy.MOST_COMPLETE,
            "journal": ConflictStrategy.SOURCE_PRIORITY,
            "year": ConflictStrategy.HIGHEST_CONFIDENCE,
            "volume": ConflictStrategy.HIGHEST_CONFIDENCE,
            "number": ConflictStrategy.HIGHEST_CONFIDENCE,
            "pages": ConflictStrategy.LONGEST_VALUE,
            "publisher": ConflictStrategy.SOURCE_PRIORITY,
            "abstract": ConflictStrategy.LONGEST_VALUE,
            "keywords": ConflictStrategy.MOST_COMPLETE,
            "url": ConflictStrategy.SOURCE_PRIORITY,
            "issn": ConflictStrategy.HIGHEST_CONFIDENCE,
            "eissn": ConflictStrategy.HIGHEST_CONFIDENCE,
            "isbn": ConflictStrategy.HIGHEST_CONFIDENCE,
        }

        # Fields that should trigger manual review if they conflict
        self.manual_review_fields = {"doi", "title", "author", "year"}

    def reconcile(
        self,
        lookup_results: list[LookupResult],
        original_entry: BibTeXEntry | None = None,
        add_abstract: bool = False,
        add_note: bool = False,
        add_eprint: bool = False,
        add_pmid: bool = False,
        add_keywords: bool = False,
    ) -> ReconciledEntry:
        """Reconcile multiple lookup results into a single entry."""
        if not lookup_results:
            if original_entry:
                return ReconciledEntry(
                    entry=original_entry,
                    conflicts=[],
                    sources_used=[],
                    confidence_score=0.5,
                    completeness_score=self._calculate_completeness(original_entry),
                )
            else:
                raise ValueError("No lookup results or original entry provided")

        # Filter out empty results
        valid_results = [r for r in lookup_results if r.entry is not None]
        if not valid_results:
            if original_entry:
                return ReconciledEntry(
                    entry=original_entry,
                    conflicts=[],
                    sources_used=[],
                    confidence_score=0.5,
                    completeness_score=self._calculate_completeness(original_entry),
                )
            else:
                raise ValueError("No valid lookup results")

        logger.debug(f"Reconciling data from {len(valid_results)} sources")

        # Start with original entry if available (to preserve key), otherwise use highest-confidence entry
        if original_entry:
            reconciled_entry = BibTeXEntry(original_entry.to_dict())
        else:
            base_result = max(valid_results, key=lambda r: r.metadata.confidence)
            if base_result.entry is None:
                raise ValueError("Base result entry is None")
            reconciled_entry = BibTeXEntry(base_result.entry.to_dict())

        # Collect all field values from all sources
        field_values: dict[str, dict[str, tuple[Any, float]]] = (
            self._collect_field_values(valid_results, original_entry, add_abstract, add_note, add_eprint, add_pmid, add_keywords)
        )

        # Resolve conflicts for each field
        conflicts = []
        sources_used = set()

        for field_name, source_values in field_values.items():
            # Skip ID field to preserve original entry key
            if field_name == "ID":
                continue
                
            if len(source_values) <= 1:
                # No conflict - use the single value
                if source_values:
                    source, (value, confidence) = next(iter(source_values.items()))
                    reconciled_entry.set_field(field_name, value)
                    sources_used.add(source)
                continue

            # Resolve conflict
            conflict = self._resolve_field_conflict(field_name, source_values)
            conflicts.append(conflict)

            if conflict.selected_value is not None:
                reconciled_entry.set_field(field_name, conflict.selected_value)
                if conflict.selected_source:
                    sources_used.add(conflict.selected_source)

        # Calculate overall scores
        confidence_score = self._calculate_confidence_score(valid_results, conflicts)
        completeness_score = self._calculate_completeness(reconciled_entry)

        # Check if manual review is required
        manual_review_required = any(
            conflict.requires_manual_review
            or conflict.field_name in self.manual_review_fields
            for conflict in conflicts
        )

        return ReconciledEntry(
            entry=reconciled_entry,
            conflicts=conflicts,
            sources_used=list(sources_used),
            confidence_score=confidence_score,
            completeness_score=completeness_score,
            manual_review_required=manual_review_required,
        )
    
    async def reconcile_with_issn_lookup(
        self,
        lookup_results: list[LookupResult],
        original_entry: BibTeXEntry | None = None,
        add_abstract: bool = False,
        add_note: bool = False,
        add_eprint: bool = False,
        add_pmid: bool = False,
        add_keywords: bool = False,
    ) -> ReconciledEntry:
        """Reconcile with additional ISSN lookup for journal names."""
        # First do regular reconciliation
        reconciled = self.reconcile(
            lookup_results, original_entry, add_abstract, add_note, add_eprint, add_pmid, add_keywords
        )
        
        # Check if we need ISSN lookup
        entry = reconciled.entry
        needs_issn_lookup = (
            entry.has_field("journal") and 
            not entry.has_field("issn") and 
            not entry.has_field("eissn")
        )
        
        if needs_issn_lookup:
            journal_name = entry.get_field("journal")
            if journal_name:
                logger.debug(f"Looking up ISSN for journal: {journal_name}")
                issn_info = await self._lookup_journal_issn(journal_name)
                
                if issn_info:
                    logger.debug(f"Found ISSN info: {issn_info}")
                    
                    # Add ISSN information to the entry
                    if issn_info.get("eissn"):
                        entry.set_field("issn", issn_info["eissn"])  # Prefer electronic ISSN
                        logger.debug(f"Added electronic ISSN: {issn_info['eissn']}")
                    elif issn_info.get("issn_l"):
                        entry.set_field("issn", issn_info["issn_l"])
                        logger.debug(f"Added ISSN-L: {issn_info['issn_l']}")
                    elif issn_info.get("issn") and issn_info["issn"]:
                        # Take the first/preferred ISSN from the list
                        entry.set_field("issn", issn_info["issn"][0])
                        logger.debug(f"Added ISSN: {issn_info['issn'][0]}")
                    
                    # Update sources used and recalculate completeness
                    reconciled.sources_used.append("issn_lookup")
                    reconciled.completeness_score = self._calculate_completeness(entry)
        
        return reconciled
    
    async def _lookup_journal_issn(self, journal_name: str) -> dict[str, Any] | None:
        """Look up ISSN for a journal name."""
        if not self._issn_service:
            self._issn_service = ISSNLookupService(email=self.email)
        
        try:
            return await self._issn_service.lookup_issn_by_journal_name(journal_name)
        except Exception as e:
            logger.debug(f"ISSN lookup failed for '{journal_name}': {e}")
            return None
    
    async def close(self):
        """Close ISSN lookup service if open."""
        if self._issn_service:
            await self._issn_service.close()
            self._issn_service = None

    def _collect_field_values(
        self, 
        results: list[LookupResult], 
        original_entry: BibTeXEntry | None, 
        add_abstract: bool = False,
        add_note: bool = False,
        add_eprint: bool = False,
        add_pmid: bool = False,
        add_keywords: bool = False
    ) -> dict[str, dict[str, tuple[Any, float]]]:
        """Collect field values from all sources."""
        field_values: dict[str, dict[str, tuple[Any, float]]] = {}
        
        def should_skip_field(field_name: str, entry_type: str = "") -> bool:
            """Check if a field should be skipped based on user preferences and entry type."""
            # Skip fields based on user preferences
            if field_name == "abstract" and not add_abstract:
                return True
            if field_name == "note" and not add_note:
                return True
            if field_name == "eprint" and not add_eprint:
                return True
            if field_name == "pmid" and not add_pmid:
                return True
            if field_name == "keywords" and not add_keywords:
                return True
            
            # Always skip ID field to preserve original entry key
            if field_name == "ID":
                return True
            
            # Entry type-specific field validation
            # Never add journal field for proceedings or book chapters
            if field_name == "journal" and entry_type.lower() in ["inproceedings", "inbook"]:
                logger.debug(f"Skipping journal field for {entry_type} entry")
                return True
            
            # Never add booktitle field for journal articles
            if field_name == "booktitle" and entry_type.lower() == "article":
                logger.debug(f"Skipping booktitle field for {entry_type} entry")
                return True
            
            return False

        # Determine target entry type (prefer original entry type)
        target_entry_type = ""
        if original_entry:
            target_entry_type = original_entry.entry_type
        elif results and results[0].entry:
            target_entry_type = results[0].entry.entry_type

        # Add original entry values if provided
        if original_entry:
            for field_name in original_entry.get_all_fields():
                # Skip fields based on user preferences and entry type
                if should_skip_field(field_name, target_entry_type):
                    continue
                    
                value = original_entry.get_field(field_name)
                if value:
                    if field_name not in field_values:
                        field_values[field_name] = {}
                    field_values[field_name]["original"] = (
                        value,
                        0.6,
                    )  # Medium confidence for original

        # Add values from lookup results
        for result in results:
            if not result.entry:
                continue

            source_name = result.metadata.source_name
            base_confidence = result.metadata.confidence

            for field_name in result.entry.get_all_fields():
                # Skip fields based on user preferences and entry type
                if should_skip_field(field_name, target_entry_type):
                    continue
                    
                value = result.entry.get_field(field_name)
                if value:
                    # Get source-specific field confidence
                    if hasattr(result, "source") and hasattr(
                        result.source, "get_reliability_score"
                    ):
                        field_confidence = result.source.get_reliability_score(
                            field_name
                        )
                    else:
                        field_confidence = base_confidence

                    if field_name not in field_values:
                        field_values[field_name] = {}

                    field_values[field_name][source_name] = (value, field_confidence)

        return field_values

    def _resolve_issn_conflict(
        self, field_name: str, source_values: dict[str, tuple[Any, float]]
    ) -> FieldConflict:
        """Special handling for ISSN conflicts - prefer electronic over print."""
        values = {source: value for source, (value, conf) in source_values.items()}
        confidences = {source: conf for source, (value, conf) in source_values.items()}
        
        conflict = FieldConflict(
            field_name=field_name,
            values=values,
            confidences=confidences,
            strategy_used=ConflictStrategy.HIGHEST_CONFIDENCE,
        )
        
        # Check if we have both ISSN and EISSN, prefer EISSN
        eissn_sources = [s for s in source_values.keys() if "eissn" in s.lower()]
        issn_sources = [s for s in source_values.keys() if s not in eissn_sources]
        
        if eissn_sources:
            # Prefer electronic ISSN
            best_source = max(eissn_sources, key=lambda x: confidences[x])
            conflict.selected_value = values[best_source]
            conflict.selected_source = best_source
            logger.debug(f"Selected electronic ISSN {conflict.selected_value} from {best_source}")
        else:
            # Fall back to highest confidence among print ISSNs
            best_source = max(confidences.keys(), key=lambda x: confidences[x])
            conflict.selected_value = values[best_source]
            conflict.selected_source = best_source
        
        return conflict
    
    def _resolve_field_conflict(
        self, field_name: str, source_values: dict[str, tuple[Any, float]]
    ) -> FieldConflict:
        """Resolve conflict for a specific field."""
        # Special handling for ISSN fields
        if field_name in ["issn", "eissn"]:
            return self._resolve_issn_conflict(field_name, source_values)
        
        strategy = self.field_strategies.get(
            field_name, ConflictStrategy.HIGHEST_CONFIDENCE
        )

        values = {source: value for source, (value, conf) in source_values.items()}
        confidences = {source: conf for source, (value, conf) in source_values.items()}

        conflict = FieldConflict(
            field_name=field_name,
            values=values,
            confidences=confidences,
            strategy_used=strategy,
        )

        # Apply conflict resolution strategy
        if strategy == ConflictStrategy.HIGHEST_CONFIDENCE:
            best_source = max(confidences.keys(), key=lambda x: confidences[x])
            conflict.selected_value = values[best_source]
            conflict.selected_source = best_source

        elif strategy == ConflictStrategy.MOST_COMPLETE:
            # Select the most complete/detailed value
            best_source = max(values.keys(), key=lambda s: len(str(values[s])))
            conflict.selected_value = values[best_source]
            conflict.selected_source = best_source

        elif strategy == ConflictStrategy.LONGEST_VALUE:
            # Select the longest value
            best_source = max(values.keys(), key=lambda s: len(str(values[s])))
            conflict.selected_value = values[best_source]
            conflict.selected_source = best_source

        elif strategy == ConflictStrategy.SOURCE_PRIORITY:
            # Select based on source priority
            prioritized_sources = sorted(
                values.keys(),
                key=lambda s: self.source_priorities.get(s, 0),
                reverse=True,
            )
            if prioritized_sources:
                best_source = prioritized_sources[0]
                conflict.selected_value = values[best_source]
                conflict.selected_source = best_source

        elif strategy == ConflictStrategy.MANUAL_REVIEW:
            conflict.requires_manual_review = True
            # For now, select highest confidence
            best_source = max(confidences.keys(), key=lambda x: confidences[x])
            conflict.selected_value = values[best_source]
            conflict.selected_source = best_source

        # Check if values are substantially different (require manual review)
        if field_name in self.manual_review_fields:
            unique_values = {str(v).lower().strip() for v in values.values()}
            if len(unique_values) > 1:
                conflict.requires_manual_review = True

        logger.debug(
            f"Resolved conflict for {field_name}: {conflict.selected_source} -> {conflict.selected_value}"
        )
        return conflict

    def _calculate_confidence_score(
        self, results: list[LookupResult], conflicts: list[FieldConflict]
    ) -> float:
        """Calculate overall confidence score for reconciled entry."""
        if not results:
            return 0.0

        # Base confidence from best source
        # Handle both SourceConfidence enum and float values
        confidences = []
        for r in results:
            if hasattr(r.metadata.confidence, 'value'):
                # SourceConfidence enum
                confidences.append(r.metadata.confidence.value)
            else:
                # Already a float
                confidences.append(r.metadata.confidence)
        base_confidence = max(confidences)

        # Penalty for conflicts
        conflict_penalty = len(conflicts) * 0.05  # 5% penalty per conflict

        # Bonus for multiple sources agreeing
        agreement_bonus = min(len(results) * 0.02, 0.1)  # 2% per source, max 10%

        final_confidence = base_confidence - conflict_penalty + agreement_bonus
        return max(0.0, min(1.0, final_confidence))

    def _calculate_completeness(self, entry: BibTeXEntry) -> float:
        """Calculate completeness score for an entry."""
        # Define important fields by entry type
        important_fields = {
            "article": ["title", "author", "journal", "year", "doi"],
            "inproceedings": ["title", "author", "booktitle", "year", "doi"],
            "book": ["title", "author", "publisher", "year", "isbn"],
            "misc": ["title", "author", "year", "url"],
        }

        entry_type = entry.entry_type
        required_fields = important_fields.get(entry_type, important_fields["misc"])

        present_fields = sum(
            1
            for field in required_fields
            if entry.has_field(field) and entry.get_field(field)
        )
        completeness = present_fields / len(required_fields)

        # Bonus for additional useful fields
        bonus_fields = [
            "abstract",
            "keywords",
            "volume",
            "number",
            "pages",
            "publisher",
            "issn",
        ]
        bonus_count = sum(
            1
            for field in bonus_fields
            if entry.has_field(field) and entry.get_field(field)
        )
        bonus = min(bonus_count * 0.05, 0.2)  # 5% per bonus field, max 20%

        return min(1.0, completeness + bonus)

    def get_reconciliation_summary(self, reconciled: ReconciledEntry) -> dict:
        """Get a summary of the reconciliation process."""
        return {
            "sources_used": reconciled.sources_used,
            "num_conflicts": len(reconciled.conflicts),
            "confidence_score": reconciled.confidence_score,
            "completeness_score": reconciled.completeness_score,
            "manual_review_required": reconciled.manual_review_required,
            "conflicts": [
                {
                    "field": c.field_name,
                    "num_sources": len(c.values),
                    "selected_source": c.selected_source,
                    "strategy": c.strategy_used.value if c.strategy_used else None,
                    "requires_manual_review": c.requires_manual_review,
                }
                for c in reconciled.conflicts
            ],
        }
