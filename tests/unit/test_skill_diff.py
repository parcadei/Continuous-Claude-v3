"""Tests for skill diff formatter (Phase 1 Tasks 1.7-1.8).

This module tests the skill_diff.py that:
1. Shows before/after comparison of SKILL.md changes
2. Adds ANSI color codes for terminal display

TDD approach: tests are written FIRST, then implementation.
"""

import pytest


# =============================================================================
# Task 1.7: Diff Formatter
# =============================================================================


class TestDiffFormatter:
    """Tests for diff formatting functionality."""

    def test_format_skill_diff_shows_changes(self) -> None:
        """Task 1.7: format_skill_diff() should show before/after comparison."""
        from scripts.skill_diff import format_skill_diff

        before = """---
name: deploy-api
description: Deploy API
---

# Deploy API
"""

        after = """---
name: deploy-api
description: Deploy API
parameters:
  hosting:
    type: enum
    values: [aws, gcp, vercel]
---

# Deploy API
"""

        diff = format_skill_diff(before, after)

        # Diff should contain line markers
        assert "+" in diff, "Diff should show additions with +"
        assert "parameters" in diff, "Diff should show added parameters"
        assert "hosting" in diff, "Diff should show specific parameter"

    def test_format_skill_diff_no_changes(self) -> None:
        """format_skill_diff() should handle identical content."""
        from scripts.skill_diff import format_skill_diff

        content = """---
name: test-skill
description: A test skill
---
"""

        diff = format_skill_diff(content, content)
        # Should not crash, may return empty or "no changes" message
        assert diff is not None

    def test_format_skill_diff_removal(self) -> None:
        """format_skill_diff() should show removals."""
        from scripts.skill_diff import format_skill_diff

        before = """---
name: test-skill
description: A test skill
old_field: to_remove
---
"""

        after = """---
name: test-skill
description: A test skill
---
"""

        diff = format_skill_diff(before, after)
        assert "-" in diff, "Diff should show removals with -"
        assert "old_field" in diff, "Diff should show removed field"

    def test_format_skill_diff_modification(self) -> None:
        """format_skill_diff() should show modifications."""
        from scripts.skill_diff import format_skill_diff

        before = """---
name: test-skill
description: Old description
---
"""

        after = """---
name: test-skill
description: New description
---
"""

        diff = format_skill_diff(before, after)
        assert "-" in diff, "Diff should show removal"
        assert "+" in diff, "Diff should show addition"
        assert "Old description" in diff or "old" in diff.lower()
        assert "New description" in diff or "new" in diff.lower()


# =============================================================================
# Task 1.8: Diff Colorization
# =============================================================================


class TestDiffColorization:
    """Tests for ANSI color code formatting."""

    def test_format_skill_diff_colors(self) -> None:
        """Task 1.8: Diff should include ANSI color codes."""
        from scripts.skill_diff import format_skill_diff

        before = """---
name: test-skill
description: Test
---
"""

        after = """---
name: test-skill
description: Test
new_field: value
---
"""

        diff = format_skill_diff(before, after, colorize=True)

        # ANSI escape codes for colors
        GREEN = '\033[32m'
        RED = '\033[31m'
        RESET = '\033[0m'

        # Should have color codes
        has_colors = GREEN in diff or RED in diff or '\033[' in diff
        assert has_colors, (
            f"Colored diff should contain ANSI codes. Got: {repr(diff)}"
        )

    def test_format_skill_diff_no_color_option(self) -> None:
        """format_skill_diff() should support no-color option."""
        from scripts.skill_diff import format_skill_diff

        before = "---\nname: a\n---"
        after = "---\nname: b\n---"

        diff = format_skill_diff(before, after, colorize=False)

        # Should NOT have ANSI codes when colorize=False
        assert '\033[' not in diff, (
            "Non-colored diff should not contain ANSI codes"
        )

    def test_format_skill_diff_green_for_additions(self) -> None:
        """Additions should be colored green."""
        from scripts.skill_diff import format_skill_diff

        before = "---\nname: test\n---"
        after = "---\nname: test\nadded: value\n---"

        diff = format_skill_diff(before, after, colorize=True)

        GREEN = '\033[32m'
        # The addition should be preceded by green
        assert GREEN in diff, "Additions should be colored green"

    def test_format_skill_diff_red_for_removals(self) -> None:
        """Removals should be colored red."""
        from scripts.skill_diff import format_skill_diff

        before = "---\nname: test\nremoved: value\n---"
        after = "---\nname: test\n---"

        diff = format_skill_diff(before, after, colorize=True)

        RED = '\033[31m'
        # The removal should be preceded by red
        assert RED in diff, "Removals should be colored red"


# =============================================================================
# DiffResult Tests
# =============================================================================


class TestDiffResult:
    """Tests for DiffResult structure."""

    def test_diff_result_line_count(self) -> None:
        """DiffResult should track line counts."""
        from scripts.skill_diff import format_skill_diff, DiffStats

        before = "---\nname: a\nold: x\n---"
        after = "---\nname: a\nnew: y\nadded: z\n---"

        # Use colorize=False for stats counting
        diff = format_skill_diff(before, after, colorize=False)
        stats = DiffStats.from_diff(diff)

        assert stats.additions > 0, "Should count additions"
        assert stats.deletions > 0, "Should count deletions"

    def test_diff_stats_summary(self) -> None:
        """DiffStats should provide summary string."""
        from scripts.skill_diff import DiffStats

        stats = DiffStats(additions=3, deletions=1)
        summary = stats.summary()

        assert "3" in summary, "Summary should show additions count"
        assert "1" in summary, "Summary should show deletions count"
