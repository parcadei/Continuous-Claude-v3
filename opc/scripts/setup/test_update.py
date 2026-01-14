#!/usr/bin/env python3
"""Tests for update.py wizard.

USAGE:
    pytest opc/scripts/setup/test_update.py -v
"""

import tempfile
from pathlib import Path

import pytest


def test_compare_directories_detects_tldr_stats():
    """Test that compare_directories detects tldr_stats.py in scripts/ directory."""
    from .update import compare_directories

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create source structure (repo)
        source = tmp / "source" / "scripts"
        source.mkdir(parents=True)
        (source / "tldr_stats.py").write_text("# tldr stats script\n")
        (source / "other_script.py").write_text("# other script\n")
        (source / "readme.txt").write_text("readme")  # Should be ignored

        # Create installed structure (empty)
        installed = tmp / "installed" / "scripts"
        installed.mkdir(parents=True)

        # Run comparison
        result = compare_directories(source.parent / "scripts", installed, {".py"})

        # Verify both .py files are detected as new
        assert len(result["new"]) == 2
        assert "tldr_stats.py" in result["new"]
        assert "other_script.py" in result["new"]
        assert "readme.txt" not in result["new"]  # Wrong extension
        assert len(result["updated"]) == 0
        assert len(result["unchanged"]) == 0


def test_compare_directories_detects_updates():
    """Test that compare_directories detects when tldr_stats.py is updated."""
    from .update import compare_directories

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create source structure (repo) with new version
        source = tmp / "source" / "scripts"
        source.mkdir(parents=True)
        (source / "tldr_stats.py").write_text("# tldr stats script v2\n")

        # Create installed structure with old version
        installed = tmp / "installed" / "scripts"
        installed.mkdir(parents=True)
        (installed / "tldr_stats.py").write_text("# tldr stats script v1\n")

        # Run comparison
        result = compare_directories(source.parent / "scripts", installed, {".py"})

        # Verify file is detected as updated
        assert len(result["new"]) == 0
        assert len(result["updated"]) == 1
        assert "tldr_stats.py" in result["updated"]
        assert len(result["unchanged"]) == 0


def test_compare_directories_detects_unchanged():
    """Test that compare_directories correctly identifies unchanged files."""
    from .update import compare_directories

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create source structure
        source = tmp / "source" / "scripts"
        source.mkdir(parents=True)
        content = "# tldr stats script\nprint('hello')\n"
        (source / "tldr_stats.py").write_text(content)

        # Create installed structure with identical content
        installed = tmp / "installed" / "scripts"
        installed.mkdir(parents=True)
        (installed / "tldr_stats.py").write_text(content)

        # Run comparison
        result = compare_directories(source.parent / "scripts", installed, {".py"})

        # Verify file is unchanged
        assert len(result["new"]) == 0
        assert len(result["updated"]) == 0
        assert len(result["unchanged"]) == 1
        assert "tldr_stats.py" in result["unchanged"]


def test_tldr_stats_skill_references_global_path():
    """Test that tldr-stats skill references the correct global path."""
    skill_path = (
        Path(__file__).parent.parent.parent.parent
        / ".claude"
        / "skills"
        / "tldr-stats"
        / "SKILL.md"
    )

    if not skill_path.exists():
        pytest.skip(f"Skill file not found at {skill_path}")

    content = skill_path.read_text()

    # Verify it references the global path
    assert (
        "~/.claude/scripts/tldr_stats.py" in content
    ), "Skill should reference global path ~/.claude/scripts/tldr_stats.py"

    # Verify it doesn't reference the old project-specific path
    assert (
        "$CLAUDE_PROJECT_DIR/.claude/scripts/tldr_stats.py" not in content
    ), "Skill should not reference old project-specific path"


def test_update_wizard_includes_scripts_directory():
    """Test that update.py checks list includes scripts directory."""

    # Read the update.py source to verify checks configuration
    update_py = Path(__file__).parent / "update.py"
    content = update_py.read_text()

    # Verify scripts directory is in the checks list
    assert (
        '("scripts"' in content
    ), "update.py should include scripts directory in checks"

    # Verify the comment explains it's for top-level scripts
    assert (
        "Top-level scripts" in content or "tldr_stats" in content
    ), "update.py should document why scripts directory is included"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
