"""Tests for Skill Flywheel Orchestrator (Phase 2 Tasks 2.1-2.11).

TDD approach: Tests written FIRST, then implementation.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import pytest


# =============================================================================
# Task 2.1: Flywheel Returns Result
# =============================================================================


@pytest.mark.asyncio
async def test_flywheel_returns_result():
    """Task 2.1: Flywheel orchestrator returns a FlywheelResult."""
    from scripts.skill_flywheel import run_flywheel, FlywheelResult

    # Create a minimal prose-only skill fixture
    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp) / "test-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: A test skill for the flywheel
---

# Test Skill

This skill deploys to AWS or GCP.
""")

        result = await run_flywheel(str(skill_path), prompt="Deploy to AWS")

        assert isinstance(result, FlywheelResult)
        assert hasattr(result, 'success')
        assert hasattr(result, 'converted')
        assert hasattr(result, 'diff')


# =============================================================================
# Task 2.2: Detect Typed Params True
# =============================================================================


def test_detect_typed_params_true():
    """Task 2.2: Detect when skill HAS typed params."""
    from scripts.skill_flywheel import _detect_typed_params

    content_with_params = """---
name: deploy-api
description: Deploy API to cloud
parameters:
  hosting:
    type: enum
    values: [aws, gcp, azure]
---

# Deploy API
"""
    assert _detect_typed_params(content_with_params) is True


# =============================================================================
# Task 2.3: Detect Typed Params False
# =============================================================================


def test_detect_typed_params_false():
    """Task 2.3: Detect when skill has NO typed params (prose-only)."""
    from scripts.skill_flywheel import _detect_typed_params

    prose_only_content = """---
name: deploy-api
description: Deploy API to cloud
---

# Deploy API

This skill deploys to AWS, GCP, or Azure.
"""
    assert _detect_typed_params(prose_only_content) is False


def test_detect_typed_params_empty_params():
    """Task 2.3b: Empty parameters: {} counts as no typed params."""
    from scripts.skill_flywheel import _detect_typed_params

    content = """---
name: test
description: Test
parameters: {}
---
"""
    assert _detect_typed_params(content) is False


# =============================================================================
# Task 2.4: Flywheel Triggers Convert
# =============================================================================


@pytest.mark.asyncio
async def test_flywheel_triggers_convert():
    """Task 2.4: Flywheel calls convert_skill() when no typed params."""
    from scripts.skill_flywheel import run_flywheel

    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp) / "prose-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("""---
name: prose-skill
description: A prose-only skill
---

# Prose Skill

Deploy to AWS or GCP with JWT authentication.
""")

        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert:
            # Mock convert_skill to return a valid result
            mock_result = MagicMock()
            mock_result.schema = {
                "name": "prose-skill",
                "description": "A prose-only skill",
                "parameters": {"hosting": {"type": "enum"}}
            }
            mock_result.yaml_content = "---\nname: prose-skill\ndescription: A prose-only skill\n---"
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = True
            mock_result.parity_result.coverage_score = 0.9
            mock_convert.return_value = mock_result

            result = await run_flywheel(str(skill_path), prompt="Deploy to AWS")

            mock_convert.assert_called_once()


# =============================================================================
# Task 2.5: Flywheel Verifies Structure
# =============================================================================


@pytest.mark.asyncio
async def test_flywheel_verifies_structure():
    """Task 2.5: Flywheel calls verify_yaml_structure() on converted result."""
    from scripts.skill_flywheel import run_flywheel
    import scripts.skill_flywheel as flywheel_module

    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp) / "test-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: Test
---

Deploy to AWS.
""")

        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert, \
             patch.object(flywheel_module, 'verify_yaml_structure') as mock_verify:

            mock_result = MagicMock()
            mock_result.yaml_content = "---\nname: test\ndescription: Test\n---"
            mock_result.schema = {"name": "test", "description": "Test"}
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = True
            mock_result.parity_result.coverage_score = 0.85
            mock_convert.return_value = mock_result

            mock_verify.return_value = MagicMock(is_valid=True, errors=[])

            result = await run_flywheel(str(skill_path), prompt="Deploy")

            mock_verify.assert_called()


# =============================================================================
# Task 2.6: Parity Threshold Configurable
# =============================================================================


def test_parity_threshold_configurable():
    """Task 2.6: PARITY_THRESHOLD can be set via env var."""
    from scripts.skill_flywheel import get_parity_threshold

    # Default
    assert get_parity_threshold() == 0.8

    # Env var override
    with patch.dict(os.environ, {"PARITY_THRESHOLD": "0.7"}):
        assert get_parity_threshold() == 0.7

    with patch.dict(os.environ, {"PARITY_THRESHOLD": "0.95"}):
        assert get_parity_threshold() == 0.95


def test_parity_threshold_invalid_env():
    """Task 2.6b: Invalid env var falls back to default."""
    from scripts.skill_flywheel import get_parity_threshold

    with patch.dict(os.environ, {"PARITY_THRESHOLD": "invalid"}):
        assert get_parity_threshold() == 0.8


# =============================================================================
# Task 2.7: Flywheel Verifies Parity
# =============================================================================


@pytest.mark.asyncio
async def test_flywheel_verifies_parity():
    """Task 2.7: Flywheel checks parity score against threshold."""
    from scripts.skill_flywheel import run_flywheel

    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp) / "test-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: Test
---

Deploy to AWS.
""")

        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert, \
             patch('scripts.skill_validator.verify_yaml_structure') as mock_verify:

            # Parity below threshold
            mock_result = MagicMock()
            mock_result.yaml_content = "---\nname: test\ndescription: Test\n---"
            mock_result.schema = {"name": "test", "description": "Test"}
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = False  # Below threshold
            mock_result.parity_result.coverage_score = 0.5
            mock_convert.return_value = mock_result

            mock_verify.return_value = MagicMock(is_valid=True, errors=[])

            result = await run_flywheel(str(skill_path), prompt="Deploy")

            # Should not persist when parity fails
            assert result.success is False
            assert "parity" in result.reason.lower() or "coverage" in result.reason.lower()


# =============================================================================
# Task 2.8: Flywheel Generates Diff
# =============================================================================


@pytest.mark.asyncio
async def test_flywheel_generates_diff():
    """Task 2.8: Flywheel calls format_skill_diff() before persist."""
    from scripts.skill_flywheel import run_flywheel
    import scripts.skill_flywheel as flywheel_module

    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp) / "test-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        original_content = """---
name: test-skill
description: Test
---

Deploy to AWS.
"""
        skill_md.write_text(original_content)

        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert, \
             patch.object(flywheel_module, 'verify_yaml_structure') as mock_verify, \
             patch.object(flywheel_module, 'format_skill_diff') as mock_diff:

            mock_result = MagicMock()
            mock_result.yaml_content = "---\nname: test\ndescription: Test\nparameters:\n  hosting:\n    type: enum\n---"
            mock_result.schema = {"name": "test", "parameters": {"hosting": {}}}
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = True
            mock_result.parity_result.coverage_score = 0.9
            mock_convert.return_value = mock_result

            mock_verify.return_value = MagicMock(is_valid=True, errors=[])
            mock_diff.return_value = "+parameters:\n+  hosting:"

            result = await run_flywheel(str(skill_path), prompt="Deploy")

            mock_diff.assert_called()
            assert result.diff is not None


# =============================================================================
# Task 2.9: Write SKILL.md Atomically
# =============================================================================


@pytest.mark.asyncio
async def test_flywheel_writes_atomically():
    """Task 2.9: Flywheel uses atomic write (write-then-rename) with backup."""
    from scripts.skill_flywheel import run_flywheel

    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp) / "test-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        original_content = """---
name: test-skill
description: Test
---

Deploy to AWS.
"""
        skill_md.write_text(original_content)

        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert, \
             patch('scripts.skill_validator.verify_yaml_structure') as mock_verify:

            mock_result = MagicMock()
            mock_result.yaml_content = "---\nname: test-skill\ndescription: Test\nparameters:\n  hosting:\n    type: enum\n---\n"
            mock_result.schema = {"name": "test-skill", "parameters": {"hosting": {}}}
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = True
            mock_result.parity_result.coverage_score = 0.9
            mock_convert.return_value = mock_result

            mock_verify.return_value = MagicMock(is_valid=True, errors=[])

            result = await run_flywheel(str(skill_path), prompt="Deploy", persist=True)

            # Check backup file exists
            backup_path = skill_path / "SKILL.md.bak"
            assert backup_path.exists(), "Backup file should be created"
            assert backup_path.read_text() == original_content

            # Check new content written
            assert "parameters" in skill_md.read_text()


# =============================================================================
# Task 2.10: Verify Persisted File is Valid YAML
# =============================================================================


@pytest.mark.asyncio
async def test_flywheel_verifies_persisted_yaml():
    """Task 2.10: After write, re-read and verify file is valid YAML."""
    from scripts.skill_flywheel import run_flywheel, FlywheelResult
    import scripts.skill_flywheel as flywheel_module

    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp) / "test-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: Test
---

Deploy to AWS.
""")

        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert, \
             patch.object(flywheel_module, 'verify_yaml_structure') as mock_verify:

            mock_result = MagicMock()
            mock_result.yaml_content = "---\nname: test-skill\ndescription: Test\nparameters:\n  hosting:\n    type: enum\n---\n"
            mock_result.schema = {"name": "test-skill", "parameters": {"hosting": {}}}
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = True
            mock_result.parity_result.coverage_score = 0.9
            mock_convert.return_value = mock_result

            # First call for converted content, second for persisted verification
            mock_verify.return_value = MagicMock(is_valid=True, errors=[])

            result = await run_flywheel(str(skill_path), prompt="Deploy", persist=True)

            # verify_yaml_structure should be called twice:
            # 1. On converted content (before persist)
            # 2. On persisted file (after write)
            assert mock_verify.call_count >= 2


# =============================================================================
# Task 2.11: Update Skill Registry After Persist
# =============================================================================


@pytest.mark.asyncio
async def test_flywheel_updates_registry():
    """Task 2.11: Update skill registry/index after successful persist."""
    from scripts.skill_flywheel import run_flywheel
    import scripts.skill_flywheel as flywheel_module

    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp) / "test-skill"
        skill_path.mkdir()
        skill_md = skill_path / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: Test
---

Deploy to AWS.
""")

        with patch('scripts.skill_generator_v2.convert_skill') as mock_convert, \
             patch('scripts.skill_validator.verify_yaml_structure') as mock_verify, \
             patch.object(flywheel_module, '_update_skill_registry') as mock_registry:

            mock_result = MagicMock()
            mock_result.yaml_content = "---\nname: test-skill\ndescription: Test\n---\n"
            mock_result.schema = {"name": "test-skill"}
            mock_result.parity_result = MagicMock()
            mock_result.parity_result.is_valid = True
            mock_result.parity_result.coverage_score = 0.9
            mock_convert.return_value = mock_result

            mock_verify.return_value = MagicMock(is_valid=True, errors=[])

            result = await run_flywheel(str(skill_path), prompt="Deploy", persist=True)

            mock_registry.assert_called_once()


# =============================================================================
# Task 3.12: Flywheel Trigger Conditions
# =============================================================================


def test_should_trigger_flywheel_prose_only():
    """Task 3.12: Flywheel should trigger for prose-only skills."""
    from scripts.skill_flywheel import should_trigger_flywheel, clear_processed_skills

    clear_processed_skills()

    content = """---
name: test-skill
description: A test skill
---

Deploy to AWS or GCP.
"""
    skill_id = "test-skill"
    prompt = "deploy to aws"

    result = should_trigger_flywheel(skill_id, content, prompt)

    assert result is True, "Should trigger for prose-only skill"


def test_should_not_trigger_flywheel_typed_params():
    """Task 3.12: Flywheel should NOT trigger for typed skills."""
    from scripts.skill_flywheel import should_trigger_flywheel, clear_processed_skills

    clear_processed_skills()

    content = """---
name: test-skill
description: A test skill
parameters:
  hosting:
    type: enum
    values: [aws, gcp]
---

Deploy to AWS or GCP.
"""
    skill_id = "test-skill"
    prompt = "deploy to aws"

    result = should_trigger_flywheel(skill_id, content, prompt)

    assert result is False, "Should NOT trigger for skill with typed params"


def test_should_not_trigger_flywheel_already_processed():
    """Task 3.12: Flywheel should NOT trigger if skill already processed this session."""
    from scripts.skill_flywheel import (
        should_trigger_flywheel,
        mark_skill_processed,
        clear_processed_skills
    )

    clear_processed_skills()

    content = """---
name: test-skill
description: A test skill
---

Deploy to AWS or GCP.
"""
    skill_id = "test-skill"
    prompt = "deploy to aws"

    # First time should trigger
    assert should_trigger_flywheel(skill_id, content, prompt) is True

    # Mark as processed
    mark_skill_processed(skill_id)

    # Second time should NOT trigger
    assert should_trigger_flywheel(skill_id, content, prompt) is False


def test_flywheel_trigger_conditions_empty_prompt():
    """Task 3.12: Flywheel should NOT trigger with empty prompt."""
    from scripts.skill_flywheel import should_trigger_flywheel, clear_processed_skills

    clear_processed_skills()

    content = """---
name: test-skill
description: A test skill
---

Deploy to AWS or GCP.
"""
    skill_id = "test-skill"
    prompt = ""

    result = should_trigger_flywheel(skill_id, content, prompt)

    assert result is False, "Should NOT trigger with empty prompt"
