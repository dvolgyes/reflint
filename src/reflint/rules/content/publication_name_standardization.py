"""Publication name standardization with fuzzy matching."""

import re

from ..base import BaseRule
from ...core.entry import BibTeXEntry
from ...core.validation import RuleViolation
from ...sources.fuzzy_matching import get_fuzzy_matcher


class PublicationNameStandardizationRule(BaseRule):
    """Standardizes publication names using fuzzy matching and known mappings."""

    rule_id = "B003"
    severity = "info"
    category = "content"
    description = (
        "Standardizes publication names using fuzzy matching and known venue mappings"
    )

    def __init__(self):
        super().__init__()
        self.fuzzy_matcher = get_fuzzy_matcher()

        # Comprehensive venue standardization mappings
        self.venue_standardizations = {
            # Major Computer Science Conferences
            "ICML": "International Conference on Machine Learning",
            "International Conference on Machine Learning": "International Conference on Machine Learning",
            "Proc. of ICML": "International Conference on Machine Learning",
            "Proceedings of ICML": "International Conference on Machine Learning",
            "Proceedings of the International Conference on Machine Learning": "International Conference on Machine Learning",
            "NIPS": "Advances in Neural Information Processing Systems",
            "NeurIPS": "Advances in Neural Information Processing Systems",
            "Advances in Neural Information Processing Systems": "Advances in Neural Information Processing Systems",
            "Neural Information Processing Systems": "Advances in Neural Information Processing Systems",
            "Proc. of NIPS": "Advances in Neural Information Processing Systems",
            "ICLR": "International Conference on Learning Representations",
            "International Conference on Learning Representations": "International Conference on Learning Representations",
            "Proc. of ICLR": "International Conference on Learning Representations",
            "CVPR": "IEEE Conference on Computer Vision and Pattern Recognition",
            "IEEE CVPR": "IEEE Conference on Computer Vision and Pattern Recognition",
            "Computer Vision and Pattern Recognition": "IEEE Conference on Computer Vision and Pattern Recognition",
            "IEEE Conference on Computer Vision and Pattern Recognition": "IEEE Conference on Computer Vision and Pattern Recognition",
            "Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition": "IEEE Conference on Computer Vision and Pattern Recognition",
            "ICCV": "IEEE International Conference on Computer Vision",
            "International Conference on Computer Vision": "IEEE International Conference on Computer Vision",
            "IEEE International Conference on Computer Vision": "IEEE International Conference on Computer Vision",
            "Proceedings of the IEEE International Conference on Computer Vision": "IEEE International Conference on Computer Vision",
            "ECCV": "European Conference on Computer Vision",
            "European Conference on Computer Vision": "European Conference on Computer Vision",
            "Proc. of ECCV": "European Conference on Computer Vision",
            "SIGCOMM": "ACM SIGCOMM Conference",
            "ACM SIGCOMM": "ACM SIGCOMM Conference",
            "ACM SIGCOMM Conference": "ACM SIGCOMM Conference",
            "Proceedings of ACM SIGCOMM": "ACM SIGCOMM Conference",
            "CHI": "ACM Conference on Human Factors in Computing Systems",
            "ACM CHI": "ACM Conference on Human Factors in Computing Systems",
            "ACM Conference on Human Factors in Computing Systems": "ACM Conference on Human Factors in Computing Systems",
            "Proceedings of the ACM Conference on Human Factors in Computing Systems": "ACM Conference on Human Factors in Computing Systems",
            # Major Journals
            "Nature": "Nature",
            "Science": "Science",
            "Cell": "Cell",
            "The Lancet": "The Lancet",
            "Lancet": "The Lancet",
            "NEJM": "New England Journal of Medicine",
            "New England Journal of Medicine": "New England Journal of Medicine",
            "N. Engl. J. Med.": "New England Journal of Medicine",
            # IEEE Journals
            "IEEE Trans. Pattern Anal. Mach. Intell.": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "IEEE TPAMI": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "TPAMI": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "IEEE Transactions on Pattern Analysis and Machine Intelligence": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "IEEE Trans. Neural Netw.": "IEEE Transactions on Neural Networks and Learning Systems",
            "IEEE Trans. Neural Networks": "IEEE Transactions on Neural Networks and Learning Systems",
            "IEEE Trans. Neural Netw. Learn. Syst.": "IEEE Transactions on Neural Networks and Learning Systems",
            "IEEE Transactions on Neural Networks and Learning Systems": "IEEE Transactions on Neural Networks and Learning Systems",
            "IEEE Trans. Image Process.": "IEEE Transactions on Image Processing",
            "IEEE TIP": "IEEE Transactions on Image Processing",
            "IEEE Transactions on Image Processing": "IEEE Transactions on Image Processing",
            "IEEE Trans. Comput.": "IEEE Transactions on Computers",
            "IEEE Transactions on Computers": "IEEE Transactions on Computers",
            # ACM Journals
            "ACM Trans. Graph.": "ACM Transactions on Graphics",
            "ACM TOG": "ACM Transactions on Graphics",
            "ACM Transactions on Graphics": "ACM Transactions on Graphics",
            "Transactions on Graphics": "ACM Transactions on Graphics",
            "ACM Trans. Comput. Syst.": "ACM Transactions on Computer Systems",
            "ACM TOCS": "ACM Transactions on Computer Systems",
            "ACM Transactions on Computer Systems": "ACM Transactions on Computer Systems",
            "ACM Comput. Surv.": "ACM Computing Surveys",
            "ACM Computing Surveys": "ACM Computing Surveys",
            "Computing Surveys": "ACM Computing Surveys",
            # Other Tech Journals
            "J. Mach. Learn. Res.": "Journal of Machine Learning Research",
            "JMLR": "Journal of Machine Learning Research",
            "Journal of Machine Learning Research": "Journal of Machine Learning Research",
            "J. Am. Chem. Soc.": "Journal of the American Chemical Society",
            "JACS": "Journal of the American Chemical Society",
            "Journal of the American Chemical Society": "Journal of the American Chemical Society",
            "Proc. Natl. Acad. Sci.": "Proceedings of the National Academy of Sciences",
            "PNAS": "Proceedings of the National Academy of Sciences",
            "Proceedings of the National Academy of Sciences": "Proceedings of the National Academy of Sciences",
            "Proc. Natl. Acad. Sci. USA": "Proceedings of the National Academy of Sciences",
            # Nature Family
            "Nat. Mach. Intell.": "Nature Machine Intelligence",
            "Nature Machine Intelligence": "Nature Machine Intelligence",
            "Nature Machine Intel.": "Nature Machine Intelligence",
            "Nat. Methods": "Nature Methods",
            "Nature Methods": "Nature Methods",
            "Nat. Commun.": "Nature Communications",
            "Nature Communications": "Nature Communications",
            "Nature Comm.": "Nature Communications",
            "Nat. Neurosci.": "Nature Neuroscience",
            "Nature Neuroscience": "Nature Neuroscience",
            # Science Family
            "Science Advances": "Science Advances",
            "Sci. Adv.": "Science Advances",
            "Science Adv": "Science Advances",
            "Science Robotics": "Science Robotics",
            "Sci. Robot.": "Science Robotics",
            # Springer Journals
            "Mach. Learn.": "Machine Learning",
            "Machine Learning": "Machine Learning",
            "Artif. Intell.": "Artificial Intelligence",
            "Artificial Intelligence": "Artificial Intelligence",
            # Elsevier Journals
            "Comput. Vis. Image Underst.": "Computer Vision and Image Understanding",
            "Computer Vision and Image Understanding": "Computer Vision and Image Understanding",
            "CVIU": "Computer Vision and Image Understanding",
            "Pattern Recognit.": "Pattern Recognition",
            "Pattern Recognition": "Pattern Recognition",
            "Neural Netw.": "Neural Networks",
            "Neural Networks": "Neural Networks",
        }

        # Common abbreviation patterns (simpler set to avoid conflicts)
        self.abbreviation_patterns = [
            # Specific organization patterns first
            (r"\bIEEE\s+Trans\.?\s+on\s+", "IEEE Transactions on "),
            (r"\bIEEE\s+Trans\.?\s+", "IEEE Transactions on "),
            (r"\bACM\s+Trans\.?\s+on\s+", "ACM Transactions on "),
            (r"\bACM\s+Trans\.?\s+", "ACM Transactions on "),
            # General patterns
            (r"\bProc\.?\s+of\s+", "Proceedings of "),
            (r"\bInt\.?\s+", "International "),
            (r"\bJ\.?\s+", "Journal of "),
            (r"\bConf\.?\s+", "Conference "),
        ]

    def validate(self, entry: BibTeXEntry) -> list[RuleViolation]:
        """Validate and suggest standardizations for publication names."""
        results = []

        # Check different venue fields
        venue_fields = ["journal", "booktitle", "series", "publisher"]

        for field in venue_fields:
            venue = entry.get_field(field)
            if venue:
                standardization = self._get_standardized_venue(venue)
                if standardization != venue:
                    results.append(
                        RuleViolation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=f"Publication name can be standardized: '{venue}' → '{standardization}'",
                            field=field,
                            suggested_fix=f"Use standardized form: {standardization}",
                        )
                    )

                # Check for fuzzy matches if no exact standardization
                if standardization == venue:
                    fuzzy_suggestion = self._find_fuzzy_standardization(venue)
                    if fuzzy_suggestion and fuzzy_suggestion != venue:
                        results.append(
                            RuleViolation(
                                rule_id=self.rule_id,
                                severity="info",
                                message=f"Similar publication name found: '{venue}' → '{fuzzy_suggestion}' (confidence based)",
                                field=field,
                                suggested_fix=f"Consider using: {fuzzy_suggestion}",
                            )
                        )

        return results

    def _get_standardized_venue(self, venue: str) -> str:
        """Get standardized venue name from known mappings."""
        if not venue:
            return venue

        # Check exact matches first
        if venue in self.venue_standardizations:
            return self.venue_standardizations[venue]

        # Check case-insensitive matches
        venue_lower = venue.lower()
        for abbrev, full_name in self.venue_standardizations.items():
            if venue_lower == abbrev.lower():
                return full_name

        # Apply common abbreviation expansions (simple approach - no iteration)
        standardized = venue.strip()

        # Apply patterns in specific order to avoid conflicts
        for pattern, replacement in self.abbreviation_patterns:
            standardized = re.sub(
                pattern, replacement, standardized, flags=re.IGNORECASE
            )

        # Clean up spacing
        standardized = re.sub(r"\s+", " ", standardized).strip()

        return standardized

    def _find_fuzzy_standardization(self, venue: str) -> str | None:
        """Find fuzzy matches for venue standardization."""
        if not venue or len(venue) < 5:  # Skip very short names
            return None

        best_match = None
        best_similarity = 0.80  # Minimum similarity threshold

        # Compare against all standardized venue names
        for standard_venue in set(self.venue_standardizations.values()):
            similarity = self._calculate_venue_similarity(venue, standard_venue)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = standard_venue

        return best_match

    def _calculate_venue_similarity(self, venue1: str, venue2: str) -> float:
        """Calculate similarity between two venue names."""
        # Use the fuzzy matcher's venue similarity logic
        from difflib import SequenceMatcher

        # Normalize both venues
        norm1 = self._normalize_venue_for_comparison(venue1)
        norm2 = self._normalize_venue_for_comparison(venue2)

        if not norm1 or not norm2:
            return 0.0

        # Calculate string similarity
        similarity = SequenceMatcher(None, norm1, norm2).ratio()

        # Check for acronym matches
        if self._venues_match_acronym(venue1, venue2):
            similarity = max(similarity, 0.85)

        # Word overlap bonus
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if words1 and words2:
            word_overlap = len(words1 & words2) / len(words1 | words2)
            similarity = 0.7 * similarity + 0.3 * word_overlap

        return min(similarity, 1.0)

    def _normalize_venue_for_comparison(self, venue: str) -> str:
        """Normalize venue name for comparison."""
        if not venue:
            return ""

        # Convert to lowercase
        normalized = venue.lower()

        # Remove common patterns that add noise
        remove_patterns = [
            r"\bproceedings\s+of\s+the\b",
            r"\bproceedings\s+of\b",
            r"\bproceedings\b",
            r"\bproc\.?\s*of\s+the\b",
            r"\bproc\.?\s*of\b",
            r"\bproc\.?\b",
            r"\binternational\b",
            r"\bint\.?\b",
            r"\bconference\s+on\b",
            r"\bconf\.?\s+on\b",
            r"\bconf\.?\b",
            r"\bjournal\s+of\b",
            r"\bj\.?\s+of\b",
            r"\bj\.?\b",
            r"\btransactions\s+on\b",
            r"\btrans\.?\s+on\b",
            r"\btrans\.?\b",
            r"\bannual\b",
            r"\bieee\b",
            r"\bacm\b",
            r"\bthe\b",
            r"\band\b",
            r"\bof\b",
            r"\bin\b",
            r"\bfor\b",
            r"\bon\b",
        ]

        for pattern in remove_patterns:
            normalized = re.sub(pattern, " ", normalized)

        # Remove punctuation and extra whitespace
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)

        return normalized.strip()

    def _venues_match_acronym(self, venue1: str, venue2: str) -> bool:
        """Check if venues match by acronym."""
        short_venue = venue1 if len(venue1) < len(venue2) else venue2
        long_venue = venue2 if len(venue1) < len(venue2) else venue1

        if len(short_venue) <= 10 and len(long_venue) > len(short_venue) * 1.5:
            # Clean and normalize both venues for comparison
            clean_short = re.sub(r"[^\w]", "", short_venue.upper())
            clean_long = long_venue.upper()

            # Remove common stop words from long venue for acronym extraction
            stop_words = {
                "THE",
                "OF",
                "ON",
                "IN",
                "FOR",
                "AND",
                "TO",
                "WITH",
                "A",
                "AN",
            }
            words = [
                word
                for word in clean_long.split()
                if word not in stop_words and len(word) > 0
            ]

            # Try different acronym strategies
            if len(words) >= len(clean_short):
                # Strategy 1: First letter of each significant word
                acronym = "".join(word[0] for word in words if len(word) > 1)
                if acronym == clean_short:
                    return True

                # Strategy 2: First letter of all words (including short ones)
                all_words = clean_long.split()
                full_acronym = "".join(
                    word[0] for word in all_words if word not in stop_words
                )
                if full_acronym == clean_short:
                    return True

                # Strategy 3: Check if short venue appears at word boundaries
                pattern = r"\b" + re.escape(clean_short) + r"\b"
                if re.search(pattern, clean_long):
                    return True

        return False
