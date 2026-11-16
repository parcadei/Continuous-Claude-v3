"""Tests for Flywheel CLI (Phase 3 Task 3.10).

TDD tests for CLI entry point.
"""

import pytest
import subprocess
import sys
from pathlib import Path


class TestFlywheelCli:
    """Task 3.10: Flywheel CLI entry point tests."""

    def test_flywheel_cli_accepts_skill_parameter(self):
        """CLI accepts --skill parameter."""
        result = subprocess.run(
            [sys.executable, "scripts/run_flywheel.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )

        assert result.returncode == 0
        assert "--skill" in result.stdout

    def test_flywheel_cli_accepts_prompt_parameter(self):
        """CLI accepts --prompt parameter."""
        result = subprocess.run(
            [sys.executable, "scripts/run_flywheel.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )

        assert "--prompt" in result.stdout

    def test_flywheel_cli_has_dry_run_mode(self):
        """CLI has --dry-run mode for testing without persistence."""
        result = subprocess.run(
            [sys.executable, "scripts/run_flywheel.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )

        assert "--dry-run" in result.stdout or "--persist" in result.stdout

    def test_flywheel_cli_requires_skill(self):
        """CLI requires --skill argument."""
        result = subprocess.run(
            [sys.executable, "scripts/run_flywheel.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )

        # Should fail without required argument
        assert result.returncode != 0 or "required" in result.stderr.lower()

    def test_flywheel_cli_runs_on_sandbox_skill(self, tmp_path: Path):
        """CLI runs successfully on a sandbox skill."""
        # Create test skill
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: Test skill for CLI
parameters:
  hosting:
    type: enum
    values: [aws, gcp]
---

# Test Skill

Deploy things.
""")

        result = subprocess.run(
            [
                sys.executable, "scripts/run_flywheel.py",
                "--skill", str(skill_dir),
                "--prompt", "deploy to aws",
                "--dry-run"
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )

        # Should succeed (skill already has params, so no conversion needed)
        assert result.returncode == 0
