"""Visual diff system for character-level change visualization.

This module provides tools for visualizing changes between original and modified
BibTeX entries with color-coded diffs and alignment algorithms.
"""

from dataclasses import dataclass
from typing import Any

try:
    from colorama import Fore, Style, init as colorama_init

    COLORAMA_AVAILABLE = True
    colorama_init(autoreset=True)
except ImportError:
    COLORAMA_AVAILABLE = False

    # Fallback for when colorama is not available
    class _ForeStub:
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        RESET = ""

    class _StyleStub:
        RESET_ALL = ""
        BRIGHT = ""

    Fore = _ForeStub()
    Style = _StyleStub()

try:
    import nwalign3

    NWALIGN_AVAILABLE = True
except ImportError:
    NWALIGN_AVAILABLE = False


@dataclass
class DiffChange:
    """Represents a single change in a diff."""

    change_type: str  # 'insert', 'delete', 'replace', 'equal'
    old_text: str
    new_text: str
    position: int
    context_before: str = ""
    context_after: str = ""


@dataclass
class DiffSummary:
    """Summary statistics for a diff operation."""

    total_changes: int
    insertions: int
    deletions: int
    replacements: int
    characters_added: int
    characters_removed: int
    changes: list[DiffChange]


class VisualDiff:
    """Visual diff system with color-coded output and alignment algorithms."""

    def __init__(self, use_colors: bool = True, context_size: int = 20):
        """Initialize the visual diff system.

        Args:
            use_colors: Whether to use color output (requires colorama)
            context_size: Number of characters to show around changes for context
        """
        self.use_colors = use_colors and COLORAMA_AVAILABLE
        self.context_size = context_size

    def generate_diff(self, original: str, modified: str) -> DiffSummary:
        """Generate a detailed diff between original and modified text.

        Args:
            original: Original text
            modified: Modified text

        Returns:
            DiffSummary with change details and statistics
        """
        if NWALIGN_AVAILABLE:
            return self._generate_nwalign_diff(original, modified)
        else:
            return self._generate_simple_diff(original, modified)

    def _generate_nwalign_diff(self, original: str, modified: str) -> DiffSummary:
        """Generate diff using nwalign3 for precise alignment."""
        # Use global alignment for character-level comparison
        alignment = nwalign3.global_align(
            original, modified, gap_open=-2, gap_extend=-1, matrix="match"
        )

        aligned_orig, aligned_mod = alignment[:2]
        changes = []
        insertions = deletions = replacements = 0
        chars_added = chars_removed = 0

        i = 0
        while i < len(aligned_orig):
            if aligned_orig[i] == aligned_mod[i]:
                # No change
                i += 1
                continue

            # Find the extent of this change
            start = i
            while i < len(aligned_orig) and aligned_orig[i] != aligned_mod[i]:
                i += 1

            old_text = aligned_orig[start:i].replace("-", "")
            new_text = aligned_mod[start:i].replace("-", "")

            # Determine change type
            if not old_text and new_text:
                change_type = "insert"
                insertions += 1
                chars_added += len(new_text)
            elif old_text and not new_text:
                change_type = "delete"
                deletions += 1
                chars_removed += len(old_text)
            else:
                change_type = "replace"
                replacements += 1
                chars_added += len(new_text)
                chars_removed += len(old_text)

            # Get context
            context_start = max(0, start - self.context_size)
            context_end = min(len(aligned_orig), i + self.context_size)
            context_before = aligned_orig[context_start:start].replace("-", "")
            context_after = aligned_orig[i:context_end].replace("-", "")

            changes.append(
                DiffChange(
                    change_type=change_type,
                    old_text=old_text,
                    new_text=new_text,
                    position=start,
                    context_before=context_before,
                    context_after=context_after,
                )
            )

        return DiffSummary(
            total_changes=len(changes),
            insertions=insertions,
            deletions=deletions,
            replacements=replacements,
            characters_added=chars_added,
            characters_removed=chars_removed,
            changes=changes,
        )

    def _generate_simple_diff(self, original: str, modified: str) -> DiffSummary:
        """Generate diff using simple character comparison (fallback)."""
        import difflib

        # Use difflib for basic character-level diff
        diff = list(difflib.ndiff(original, modified))
        changes = []
        insertions = deletions = replacements = 0
        chars_added = chars_removed = 0

        i = 0
        while i < len(diff):
            line = diff[i]
            if line.startswith("  "):  # No change
                i += 1
                continue

            # Collect consecutive changes
            old_chars = []
            new_chars = []
            start_pos = i

            while i < len(diff) and not diff[i].startswith("  "):
                if diff[i].startswith("- "):
                    old_chars.append(diff[i][2:])
                elif diff[i].startswith("+ "):
                    new_chars.append(diff[i][2:])
                i += 1

            old_text = "".join(old_chars)
            new_text = "".join(new_chars)

            # Determine change type
            if not old_text and new_text:
                change_type = "insert"
                insertions += 1
                chars_added += len(new_text)
            elif old_text and not new_text:
                change_type = "delete"
                deletions += 1
                chars_removed += len(old_text)
            else:
                change_type = "replace"
                replacements += 1
                chars_added += len(new_text)
                chars_removed += len(old_text)

            changes.append(
                DiffChange(
                    change_type=change_type,
                    old_text=old_text,
                    new_text=new_text,
                    position=start_pos,
                    context_before="",  # Simple diff doesn't provide easy context
                    context_after="",
                )
            )

        return DiffSummary(
            total_changes=len(changes),
            insertions=insertions,
            deletions=deletions,
            replacements=replacements,
            characters_added=chars_added,
            characters_removed=chars_removed,
            changes=changes,
        )

    def format_change(self, change: DiffChange) -> str:
        """Format a single change with color coding.

        Args:
            change: The change to format

        Returns:
            Formatted string representation of the change
        """
        if not self.use_colors:
            return self._format_change_plain(change)

        if change.change_type == "insert":
            return f"{Fore.GREEN}+{change.new_text}{Style.RESET_ALL}"
        elif change.change_type == "delete":
            return f"{Fore.RED}-{change.old_text}{Style.RESET_ALL}"
        elif change.change_type == "replace":
            return f"{Fore.RED}-{change.old_text}{Style.RESET_ALL}{Fore.GREEN}+{change.new_text}{Style.RESET_ALL}"
        else:  # equal
            return change.old_text

    def _format_change_plain(self, change: DiffChange) -> str:
        """Format a change without colors for plain text output."""
        if change.change_type == "insert":
            return f"[+{change.new_text}]"
        elif change.change_type == "delete":
            return f"[-{change.old_text}]"
        elif change.change_type == "replace":
            return f"[-{change.old_text}+{change.new_text}]"
        else:  # equal
            return change.old_text

    def format_diff_summary(self, summary: DiffSummary) -> str:
        """Format a complete diff summary with statistics.

        Args:
            summary: The diff summary to format

        Returns:
            Formatted string with change summary and statistics
        """
        lines = []

        # Header with statistics
        if self.use_colors:
            lines.append(f"{Style.BRIGHT}Diff Summary:{Style.RESET_ALL}")
            lines.append(
                f"  Total changes: {Fore.BLUE}{summary.total_changes}{Style.RESET_ALL}"
            )
            lines.append(
                f"  Insertions: {Fore.GREEN}{summary.insertions} (+{summary.characters_added} chars){Style.RESET_ALL}"
            )
            lines.append(
                f"  Deletions: {Fore.RED}{summary.deletions} (-{summary.characters_removed} chars){Style.RESET_ALL}"
            )
            lines.append(
                f"  Replacements: {Fore.YELLOW}{summary.replacements}{Style.RESET_ALL}"
            )
        else:
            lines.append("Diff Summary:")
            lines.append(f"  Total changes: {summary.total_changes}")
            lines.append(
                f"  Insertions: {summary.insertions} (+{summary.characters_added} chars)"
            )
            lines.append(
                f"  Deletions: {summary.deletions} (-{summary.characters_removed} chars)"
            )
            lines.append(f"  Replacements: {summary.replacements}")

        if summary.changes:
            lines.append("")
            if self.use_colors:
                lines.append(f"{Style.BRIGHT}Changes:{Style.RESET_ALL}")
            else:
                lines.append("Changes:")

            for i, change in enumerate(
                summary.changes[:10]
            ):  # Limit to first 10 changes
                change_str = self.format_change(change)
                lines.append(f"  {i + 1:2d}. {change_str}")

            if len(summary.changes) > 10:
                lines.append(f"  ... and {len(summary.changes) - 10} more changes")

        return "\n".join(lines)

    def create_side_by_side_diff(
        self, original: str, modified: str, width: int = 80
    ) -> str:
        """Create a side-by-side comparison of original and modified text.

        Args:
            original: Original text
            modified: Modified text
            width: Total width for the display

        Returns:
            Side-by-side formatted diff
        """
        col_width = (width - 3) // 2  # Account for separator
        lines = []

        # Split into lines for comparison
        orig_lines = original.split("\n")
        mod_lines = modified.split("\n")
        max_lines = max(len(orig_lines), len(mod_lines))

        # Header
        if self.use_colors:
            header = f"{Style.BRIGHT}{'Original':<{col_width}} | {'Modified':<{col_width}}{Style.RESET_ALL}"
        else:
            header = f"{'Original':<{col_width}} | {'Modified':<{col_width}}"
        lines.append(header)
        lines.append("-" * width)

        for i in range(max_lines):
            orig_line = orig_lines[i] if i < len(orig_lines) else ""
            mod_line = mod_lines[i] if i < len(mod_lines) else ""

            # Truncate or pad lines to fit columns
            orig_display = (
                (orig_line[: col_width - 1] + "…")
                if len(orig_line) >= col_width
                else orig_line.ljust(col_width)
            )
            mod_display = (
                (mod_line[: col_width - 1] + "…")
                if len(mod_line) >= col_width
                else mod_line.ljust(col_width)
            )

            # Color coding for different lines
            if orig_line != mod_line:
                if self.use_colors:
                    if orig_line and not mod_line:  # Deleted line
                        orig_display = f"{Fore.RED}{orig_display}{Style.RESET_ALL}"
                        mod_display = f"{' ':<{col_width}}"
                    elif not orig_line and mod_line:  # Added line
                        orig_display = f"{' ':<{col_width}}"
                        mod_display = f"{Fore.GREEN}{mod_display}{Style.RESET_ALL}"
                    else:  # Modified line
                        orig_display = f"{Fore.YELLOW}{orig_display}{Style.RESET_ALL}"
                        mod_display = f"{Fore.YELLOW}{mod_display}{Style.RESET_ALL}"
                else:
                    if orig_line and not mod_line:
                        orig_display = f"[-] {orig_display[4:]}"
                    elif not orig_line and mod_line:
                        mod_display = f"[+] {mod_display[4:]}"
                    else:
                        orig_display = f"[~] {orig_display[4:]}"
                        mod_display = f"[~] {mod_display[4:]}"

            lines.append(f"{orig_display} | {mod_display}")

        return "\n".join(lines)

    def create_unified_diff(
        self,
        original: str,
        modified: str,
        original_name: str = "original",
        modified_name: str = "modified",
    ) -> str:
        """Create a unified diff format output.

        Args:
            original: Original text
            modified: Modified text
            original_name: Name for the original version
            modified_name: Name for the modified version

        Returns:
            Unified diff format string
        """
        import difflib

        orig_lines = original.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                mod_lines,
                fromfile=original_name,
                tofile=modified_name,
                lineterm="",
            )
        )

        if not self.use_colors:
            return "".join(diff_lines)

        # Add color coding to unified diff
        colored_lines = []
        for line in diff_lines:
            if line.startswith("+++") or line.startswith("---"):
                colored_lines.append(f"{Style.BRIGHT}{line}{Style.RESET_ALL}")
            elif line.startswith("@@"):
                colored_lines.append(f"{Fore.BLUE}{line}{Style.RESET_ALL}")
            elif line.startswith("+"):
                colored_lines.append(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
            elif line.startswith("-"):
                colored_lines.append(f"{Fore.RED}{line}{Style.RESET_ALL}")
            else:
                colored_lines.append(line)

        return "\n".join(colored_lines)


def create_entry_diff(
    original_entry: dict[str, Any], modified_entry: dict[str, Any]
) -> str:
    """Create a visual diff for BibTeX entry changes.

    Args:
        original_entry: Original BibTeX entry
        modified_entry: Modified BibTeX entry

    Returns:
        Formatted diff showing field-by-field changes
    """
    differ = VisualDiff()
    lines = []

    # Get all fields from both entries
    all_fields = set(original_entry.keys()) | set(modified_entry.keys())

    for field in sorted(all_fields):
        orig_value = str(original_entry.get(field, ""))
        mod_value = str(modified_entry.get(field, ""))

        if orig_value != mod_value:
            summary = differ.generate_diff(orig_value, mod_value)
            if summary.total_changes > 0:
                if differ.use_colors:
                    lines.append(f"{Style.BRIGHT}{field}:{Style.RESET_ALL}")
                else:
                    lines.append(f"{field}:")
                lines.append(differ.format_diff_summary(summary))
                lines.append("")

    return "\n".join(lines)
