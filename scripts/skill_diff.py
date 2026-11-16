"""
Skill Diff Formatter (Phase 1 Tasks 1.7-1.8).

USAGE:
    uv run python scripts/skill_diff.py --before old.md --after new.md [--no-color]

Shows before/after comparison of SKILL.md changes with:
1. Unified diff format
2. ANSI color codes (green for additions, red for removals)
3. Statistics summary
"""

from dataclasses import dataclass
import difflib
import argparse
import sys


# ANSI color codes
GREEN = '\033[32m'
RED = '\033[31m'
CYAN = '\033[36m'
RESET = '\033[0m'
BOLD = '\033[1m'


@dataclass
class DiffStats:
    """Statistics about diff changes."""
    additions: int = 0
    deletions: int = 0

    @classmethod
    def from_diff(cls, diff_text: str) -> 'DiffStats':
        """Parse statistics from diff output."""
        additions = 0
        deletions = 0

        for line in diff_text.split('\n'):
            # Skip diff headers
            if line.startswith('+++') or line.startswith('---'):
                continue
            if line.startswith('@@'):
                continue

            if line.startswith('+'):
                additions += 1
            elif line.startswith('-'):
                deletions += 1

        return cls(additions=additions, deletions=deletions)

    def summary(self) -> str:
        """Return human-readable summary."""
        parts = []
        if self.additions:
            parts.append(f"+{self.additions} additions")
        if self.deletions:
            parts.append(f"-{self.deletions} deletions")
        if not parts:
            return "No changes"
        return ", ".join(parts)


def format_skill_diff(
    before: str,
    after: str,
    colorize: bool = True,
    context_lines: int = 3
) -> str:
    """
    Format a unified diff between two SKILL.md versions.

    Args:
        before: Original SKILL.md content
        after: New SKILL.md content
        colorize: Whether to add ANSI color codes
        context_lines: Number of context lines around changes

    Returns:
        Formatted diff string
    """
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    # Generate unified diff
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile='before',
        tofile='after',
        n=context_lines
    )

    diff_lines = list(diff)

    if not diff_lines:
        return "No changes detected."

    if not colorize:
        return ''.join(diff_lines)

    # Colorize the diff
    colored_lines = []
    for line in diff_lines:
        if line.startswith('+++') or line.startswith('---'):
            colored_lines.append(f"{BOLD}{line}{RESET}")
        elif line.startswith('@@'):
            colored_lines.append(f"{CYAN}{line}{RESET}")
        elif line.startswith('+'):
            colored_lines.append(f"{GREEN}{line}{RESET}")
        elif line.startswith('-'):
            colored_lines.append(f"{RED}{line}{RESET}")
        else:
            colored_lines.append(line)

    return ''.join(colored_lines)


def format_skill_diff_summary(before: str, after: str, colorize: bool = True) -> str:
    """
    Format diff with summary statistics.

    Args:
        before: Original content
        after: New content
        colorize: Whether to add colors

    Returns:
        Diff with stats summary
    """
    diff = format_skill_diff(before, after, colorize=colorize)
    stats = DiffStats.from_diff(format_skill_diff(before, after, colorize=False))

    summary = f"\n{BOLD if colorize else ''}Summary:{RESET if colorize else ''} {stats.summary()}"
    return diff + summary


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Show diff between two SKILL.md versions"
    )
    parser.add_argument(
        '--before', '-b',
        required=True,
        help="Path to original SKILL.md"
    )
    parser.add_argument(
        '--after', '-a',
        required=True,
        help="Path to new SKILL.md"
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help="Disable ANSI color codes"
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help="Include change statistics"
    )

    args = parser.parse_args()

    try:
        with open(args.before, 'r') as f:
            before_content = f.read()
        with open(args.after, 'r') as f:
            after_content = f.read()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    colorize = not args.no_color

    if args.summary:
        output = format_skill_diff_summary(before_content, after_content, colorize=colorize)
    else:
        output = format_skill_diff(before_content, after_content, colorize=colorize)

    print(output)


if __name__ == '__main__':
    main()
