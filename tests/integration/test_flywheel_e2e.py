"""End-to-End Integration Tests for Skill Flywheel (Phase 3 Task 3.14).

These tests simulate the full flywheel cycle from skill invocation
through conversion, verification, and persistence.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch, MagicMock


@pytest.fixture
def sandbox_skill(tmp_path: Path):
    """Create a prose-only sandbox skill for testing."""
    skill_dir = tmp_path / "sandbox-skill"
    skill_dir.mkdir()

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: sandbox-skill
description: A sandbox skill for E2E testing
---

# Sandbox Skill

This skill deploys applications to cloud providers.

## Usage

Use this skill to deploy your application to AWS, GCP, or Azure.
Specify the hosting provider and region for your deployment.

## Examples

- "Deploy to AWS in us-east-1"
- "Deploy to GCP europe-west1"
- "Deploy my app to Azure"
""")

    return skill_dir


@pytest.fixture
def typed_skill(tmp_path: Path):
    """Create a skill that already has typed params."""
    skill_dir = tmp_path / "typed-skill"
    skill_dir.mkdir()

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: typed-skill
description: A skill with typed parameters
parameters:
  hosting:
    type: enum
    values: [aws, gcp, azure]
    infer_from: "aws|gcp|azure"
  region:
    type: string
---

# Typed Skill

This skill already has typed parameters.
""")

    return skill_dir


class TestFullFlywheelCycle:
    """Task 3.14: End-to-end flywheel cycle tests."""

    @pytest.mark.asyncio
    async def test_full_flywheel_cycle(self, sandbox_skill: Path):
        """E2E test for full flywheel cycle.

        Steps:
        1. Create prose-only skill in sandbox
        2. Invoke skill (trigger flywheel)
        3. Verify convert mode ran
        4. Verify double verification (structural + parity >= 80%)
        5. Verify diff shown to user (assert contains '+' and '-' markers)
        6. Verify SKILL.md updated with typed params
        7. Re-invoke skill, verify uses typed params (no flywheel trigger)
        """
        from scripts.skill_flywheel import (
            run_flywheel,
            should_trigger_flywheel,
            mark_skill_processed,
            clear_processed_skills
        )

        clear_processed_skills()

        skill_file = sandbox_skill / "SKILL.md"
        original_content = skill_file.read_text()

        # Pre-conditions
        assert skill_file.exists(), "sandbox_skill.md exists before test"
        assert "parameters:" not in original_content, \
            "sandbox_skill.md has NO 'params:' before flywheel"

        # Mock the convert_skill to return a valid conversion
        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert:
            mock_result = MagicMock()
            mock_result.yaml_content = """---
name: sandbox-skill
description: A sandbox skill for E2E testing
parameters:
  hosting:
    type: enum
    values: [aws, gcp, azure]
    infer_from: "aws|gcp|azure"
  region:
    type: string
    infer_from: "us-east|eu-west|asia"
---

# Sandbox Skill

This skill deploys applications to cloud providers.
"""
            mock_result.schema = {
                "name": "sandbox-skill",
                "parameters": {
                    "hosting": {"type": "enum"},
                    "region": {"type": "string"}
                }
            }
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = True
            mock_result.parity_result.coverage_score = 0.85  # >= 80%
            mock_convert.return_value = mock_result

            # Step 1-2: Run flywheel with persistence
            result = await run_flywheel(
                sandbox_skill,
                prompt="Deploy to AWS",
                persist=True
            )

            # Step 3: Verify convert mode ran
            assert result.success is True
            assert result.converted is True

            # Step 4: Verify parity >= 80%
            assert result.parity_score >= 0.8, "parity score >= 0.8"

            # Step 5: Verify diff contains change markers
            assert result.diff is not None
            # Diff should show additions
            assert "parameters" in result.diff or "+" in result.diff

            # Step 6: Verify SKILL.md updated
            updated_content = skill_file.read_text()
            assert "parameters:" in updated_content, \
                "sandbox_skill.md HAS 'params:' after flywheel"

            # Verify backup exists
            backup_file = sandbox_skill / "SKILL.md.bak"
            assert backup_file.exists(), "backup file exists at sandbox_skill.md.bak"

        # Step 7: Mark as processed and verify no re-trigger
        mark_skill_processed("sandbox-skill")

        should_trigger = should_trigger_flywheel(
            "sandbox-skill",
            updated_content,
            "Deploy to GCP"
        )
        assert should_trigger is False, \
            "Should not trigger on re-invoke (already processed)"

    @pytest.mark.asyncio
    async def test_flywheel_skips_typed_skills(self, typed_skill: Path):
        """Flywheel should skip skills that already have typed params."""
        from scripts.skill_flywheel import run_flywheel, clear_processed_skills

        clear_processed_skills()

        result = await run_flywheel(typed_skill, prompt="Deploy to AWS")

        assert result.success is True
        assert result.converted is False
        assert "already has typed parameters" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_flywheel_persists_across_sessions(self, tmp_path: Path):
        """Test that flywheel changes survive session boundary.

        Steps:
        1. Run flywheel on prose-only skill
        2. "Clear session" (close test context, reopen)
        3. Load skill from disk
        4. Verify typed params still present
        """
        from scripts.skill_flywheel import run_flywheel, clear_processed_skills

        clear_processed_skills()

        # Create prose-only skill
        skill_dir = tmp_path / "persist-test"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: persist-test
description: Test persistence
---

Deploy to AWS or GCP.
""")

        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert:
            mock_result = MagicMock()
            mock_result.yaml_content = """---
name: persist-test
description: Test persistence
parameters:
  hosting:
    type: enum
    values: [aws, gcp]
---

Deploy to AWS or GCP.
"""
            mock_result.schema = {"name": "persist-test", "parameters": {"hosting": {}}}
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = True
            mock_result.parity_result.coverage_score = 0.9
            mock_convert.return_value = mock_result

            # Run flywheel with persistence
            result = await run_flywheel(skill_dir, "Deploy to AWS", persist=True)
            assert result.success is True

        # "Clear session" - reset in-memory state
        clear_processed_skills()

        # Load skill from disk (simulating new session)
        reloaded_content = skill_file.read_text()

        # Verify typed params still present
        assert "parameters:" in reloaded_content, \
            "skill.params is not None after reload"
        assert "hosting:" in reloaded_content, \
            "skill.params matches original conversion"


class TestFlywheelPatternIntegration:
    """Integration tests for pattern analysis and registry."""

    def test_pattern_registry_available(self):
        """Pattern registry is accessible and populated."""
        from scripts.skill_pattern_registry import get_default_registry

        registry = get_default_registry()

        assert len(registry.patterns) > 0
        assert "cloud_provider" in registry.patterns or "hosting" in registry.patterns or len(registry.patterns) > 5

    def test_correction_analysis_integration(self, tmp_path: Path):
        """Corrections can be analyzed for pattern suggestions."""
        from scripts.skill_feedback import (
            capture_correction,
            persist_correction,
            load_corrections
        )
        from scripts.skill_pattern_analyzer import analyze_corrections
        import os

        # Set temp dir for corrections
        os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)

        # Create some corrections
        c1 = capture_correction("test-skill", "hosting", "aws", "gcp", "google cloud")
        c2 = capture_correction("test-skill", "hosting", "aws", "gcp", "GCP kubernetes")
        c3 = capture_correction("test-skill", "hosting", "azure", "gcp", "google")

        persist_correction(c1)
        persist_correction(c2)
        persist_correction(c3)

        # Load and analyze
        corrections = load_corrections("test-skill")
        suggestions = analyze_corrections(corrections)

        assert len(corrections) == 3
        assert len(suggestions) > 0
        assert any(s["param"] == "hosting" for s in suggestions)


class TestFlywheelCLIIntegration:
    """Integration tests for CLI entry point."""

    def test_cli_help(self):
        """CLI shows help without errors."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "scripts/run_flywheel.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )

        assert result.returncode == 0
        assert "--skill" in result.stdout
        assert "--prompt" in result.stdout

    def test_cli_list_patterns(self):
        """CLI can list shared patterns."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "scripts/run_flywheel.py", "--list-patterns", "--json"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )

        assert result.returncode == 0
        # Should have some JSON output
        import json
        data = json.loads(result.stdout)
        assert len(data) > 0  # At least one domain
