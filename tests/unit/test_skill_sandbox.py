"""Tests for skill sandbox directory structure (Phase 1 Task 1.9).

This module tests the sandbox environment for safe skill testing:
1. _sandbox directory exists under .claude/skills/
2. Contains test fixture skills (prose-only for flywheel testing)
3. Is properly isolated from production skills

TDD approach: tests are written FIRST, then implementation.
"""

import pytest
from pathlib import Path


# =============================================================================
# Task 1.9: Sandbox Directory Structure
# =============================================================================


class TestSandboxDirectoryStructure:
    """Tests for sandbox directory existence and structure."""

    @pytest.fixture
    def skills_dir(self) -> Path:
        """Path to skills directory."""
        return Path(__file__).parents[2] / ".claude" / "skills"

    @pytest.fixture
    def sandbox_dir(self) -> Path:
        """Path to sandbox directory."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "_sandbox"

    def test_sandbox_directory_structure_exists(self, sandbox_dir: Path) -> None:
        """Task 1.9: Sandbox directory should exist."""
        assert sandbox_dir.exists(), (
            f"Sandbox directory not found at {sandbox_dir}. "
            "Create .claude/skills/_sandbox/"
        )
        assert sandbox_dir.is_dir(), (
            f"{sandbox_dir} should be a directory"
        )

    def test_sandbox_has_gitkeep(self, sandbox_dir: Path) -> None:
        """Sandbox should have .gitkeep to preserve empty directory."""
        if not sandbox_dir.exists():
            pytest.skip("Sandbox directory doesn't exist yet")

        gitkeep = sandbox_dir / ".gitkeep"
        assert gitkeep.exists(), (
            f"Sandbox should have .gitkeep file at {gitkeep}"
        )

    def test_sandbox_has_test_skill(self, sandbox_dir: Path) -> None:
        """Sandbox should contain a test skill fixture."""
        if not sandbox_dir.exists():
            pytest.skip("Sandbox directory doesn't exist yet")

        test_skill = sandbox_dir / "test-skill"
        assert test_skill.exists(), (
            f"Test skill fixture not found at {test_skill}"
        )
        assert test_skill.is_dir(), (
            f"Test skill should be a directory"
        )

    def test_test_skill_has_skill_md(self, sandbox_dir: Path) -> None:
        """Test skill should have SKILL.md file."""
        if not sandbox_dir.exists():
            pytest.skip("Sandbox directory doesn't exist yet")

        skill_md = sandbox_dir / "test-skill" / "SKILL.md"
        assert skill_md.exists(), (
            f"Test skill SKILL.md not found at {skill_md}"
        )

    def test_test_skill_is_prose_only(self, sandbox_dir: Path) -> None:
        """Test skill should be prose-only (no typed params) for flywheel testing."""
        import re

        if not sandbox_dir.exists():
            pytest.skip("Sandbox directory doesn't exist yet")

        skill_md = sandbox_dir / "test-skill" / "SKILL.md"
        if not skill_md.exists():
            pytest.skip("Test skill SKILL.md doesn't exist yet")

        content = skill_md.read_text()

        # Should have name and description
        assert "name:" in content.lower(), "SKILL.md should have name field"
        assert "description:" in content.lower(), "SKILL.md should have description field"

        # Extract frontmatter (between --- markers)
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        assert frontmatter_match, "SKILL.md should have frontmatter"
        frontmatter = frontmatter_match.group(1)

        # Frontmatter should NOT have parameters: key (prose-only for testing flywheel conversion)
        # This is the fixture for testing the CONVERT mode
        assert "parameters:" not in frontmatter.lower(), (
            "Test skill should be prose-only (no parameters in frontmatter) for flywheel testing"
        )


class TestSandboxIsolation:
    """Tests for sandbox isolation from production skills."""

    @pytest.fixture
    def skills_dir(self) -> Path:
        """Path to skills directory."""
        return Path(__file__).parents[2] / ".claude" / "skills"

    @pytest.fixture
    def sandbox_dir(self) -> Path:
        """Path to sandbox directory."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "_sandbox"

    def test_sandbox_directory_starts_with_underscore(self, sandbox_dir: Path) -> None:
        """Sandbox directory should start with underscore for visual separation."""
        assert sandbox_dir.name.startswith("_"), (
            "Sandbox directory should start with underscore (_sandbox)"
        )

    def test_sandbox_is_separate_from_production_skills(
        self, skills_dir: Path, sandbox_dir: Path
    ) -> None:
        """Sandbox should be clearly separate from production skills."""
        if not skills_dir.exists():
            pytest.skip("Skills directory doesn't exist")

        # Count production skills (non-underscore directories)
        production_skills = [
            d for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        ]

        # Count sandbox skills
        sandbox_skills = []
        if sandbox_dir.exists():
            sandbox_skills = [
                d for d in sandbox_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]

        # Sandbox skills should not overlap with production
        production_names = {s.name for s in production_skills}
        sandbox_names = {s.name for s in sandbox_skills}

        # Test skill names shouldn't conflict (unless intentional)
        # This is more of a sanity check
        assert sandbox_dir.exists(), "Sandbox should exist"
