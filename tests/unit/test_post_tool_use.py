"""Tests for PostToolUse Hook Flywheel Integration (Phase 3 Task 3.13).

TDD tests for wiring flywheel to post-tool-use hook.
"""

import pytest
from pathlib import Path
import json
from unittest.mock import patch, MagicMock, AsyncMock


class TestPostToolUseFlywheel:
    """Task 3.13: PostToolUse hook triggers flywheel."""

    def test_post_tool_use_detects_skill_execution(self):
        """PostToolUse hook detects when Skill tool was used."""
        from scripts.post_tool_use_flywheel import should_process_for_flywheel

        # Skill tool input
        hook_input = {
            "tool_name": "Skill",
            "tool_input": {
                "skill": "deploy-api",
                "args": "--prompt 'deploy to aws'"
            },
            "tool_output": {
                "content": "Skill executed successfully"
            }
        }

        result = should_process_for_flywheel(hook_input)

        assert result is True

    def test_post_tool_use_ignores_non_skill_tools(self):
        """PostToolUse hook ignores non-Skill tools."""
        from scripts.post_tool_use_flywheel import should_process_for_flywheel

        # Bash tool input
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_output": {"content": "file1\nfile2"}
        }

        result = should_process_for_flywheel(hook_input)

        assert result is False

    def test_post_tool_use_extracts_skill_id(self):
        """PostToolUse hook extracts skill ID from Skill tool input."""
        from scripts.post_tool_use_flywheel import extract_skill_id

        hook_input = {
            "tool_name": "Skill",
            "tool_input": {
                "skill": "deploy-api",
                "args": "--prompt 'deploy to aws'"
            }
        }

        skill_id = extract_skill_id(hook_input)

        assert skill_id == "deploy-api"

    @pytest.mark.asyncio
    async def test_post_tool_use_triggers_flywheel(self, tmp_path: Path):
        """PostToolUse hook triggers flywheel for prose-only skills."""
        from scripts.post_tool_use_flywheel import process_skill_for_flywheel

        # Create test skill
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: Test skill
---

Deploy to AWS or GCP.
""")

        hook_input = {
            "tool_name": "Skill",
            "tool_input": {
                "skill": "test-skill",
                "args": "--prompt 'deploy to aws'"
            }
        }

        with patch('scripts.post_tool_use_flywheel.get_skill_path') as mock_path, \
             patch('scripts.post_tool_use_flywheel.run_flywheel') as mock_flywheel:

            mock_path.return_value = skill_dir
            mock_flywheel.return_value = MagicMock(
                success=True,
                converted=True,
                diff="+parameters:"
            )

            result = await process_skill_for_flywheel(hook_input)

            mock_flywheel.assert_called_once()
            assert result is not None

    def test_post_tool_use_hook_returns_continue(self):
        """PostToolUse hook returns 'continue' result."""
        from scripts.post_tool_use_flywheel import create_hook_response

        result = create_hook_response(
            success=True,
            message="Flywheel processed skill"
        )

        assert result["result"] == "continue"
        assert "message" in result
