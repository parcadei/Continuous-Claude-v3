"""Tests for Phase 6: Hard Limit Block in PreToolUse hook.

These tests verify that pre-tool-use.ts:
1. Blocks Task tool when activeAgents >= maxAgents
2. Returns continue for Task when under limit
3. Does NOT block non-Task tools even when at limit
4. Reads resource state from /tmp/claude-resources-{session}.json

Tests are designed to FAIL initially (TDD approach) until Phase 6 is implemented.

See plan: docs/handoffs/resource-limits-plan.md (Phase 6)
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest


class TestHardLimitBlocksTask:
    """Tests for PreToolUse blocking Task when at resource limit."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def unique_session_id(self) -> str:
        """Generate unique session ID for test isolation."""
        return f"test-hardlimit-{os.getpid()}-{id(self)}"

    @pytest.fixture
    def cleanup_temp_files(self, unique_session_id: str):
        """Clean up temp files after test."""
        yield
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        if resource_file.exists():
            resource_file.unlink()

    def _write_resources_json(
        self,
        session_id: str,
        free_mem_mb: int = 8000,
        active_agents: int = 0,
        max_agents: int = 12,
        context_pct: int = 50
    ) -> Path:
        """Write resources JSON file for test."""
        resource_file = Path(f"/tmp/claude-resources-{session_id}.json")
        data = {
            "freeMemMB": free_mem_mb,
            "activeAgents": active_agents,
            "maxAgents": max_agents,
            "contextPct": context_pct
        }
        resource_file.write_text(json.dumps(data))
        return resource_file

    def _run_pre_tool_use(
        self,
        hooks_dir: Path,
        session_id: str,
        tool_name: str,
        tool_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run pre-tool-use.ts and return parsed output."""
        pre_tool_use_script = hooks_dir / "pre-tool-use.sh"

        if not pre_tool_use_script.exists():
            pytest.skip("pre-tool-use.sh doesn't exist")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        input_json = json.dumps({
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_input": tool_input or {}
        })

        result = subprocess.run(
            ["bash", str(pre_tool_use_script)],
            input=input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            cwd=str(hooks_dir.parent.parent)
        )

        # Parse output - should be JSON
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            pytest.fail(
                f"pre-tool-use.sh output is not valid JSON. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )

    def test_pre_tool_use_hook_exists(self, hooks_dir: Path) -> None:
        """PreToolUse hook exists at expected path."""
        pre_tool_use_script = hooks_dir / "pre-tool-use.sh"

        assert pre_tool_use_script.exists(), (
            f"pre-tool-use.sh not found: {pre_tool_use_script}. "
            "Expected at .claude/hooks/pre-tool-use.sh"
        )

    def test_blocks_task_when_at_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """PreToolUse blocks Task tool when activeAgents >= maxAgents."""
        # Set up: at limit (4 agents, max 4)
        self._write_resources_json(
            unique_session_id,
            free_mem_mb=4000,
            active_agents=4,
            max_agents=4
        )

        result = self._run_pre_tool_use(
            hooks_dir,
            unique_session_id,
            tool_name="Task",
            tool_input={"description": "spawn an agent"}
        )

        assert result.get("result") == "block", (
            f"Task should be blocked when activeAgents >= maxAgents. "
            f"Got result: {result}"
        )

        assert "reason" in result, (
            f"Block result should include reason. Got: {result}"
        )

    def test_blocks_task_when_over_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """PreToolUse blocks Task tool when activeAgents > maxAgents."""
        # Set up: over limit (5 agents, max 4)
        self._write_resources_json(
            unique_session_id,
            free_mem_mb=4000,
            active_agents=5,
            max_agents=4
        )

        result = self._run_pre_tool_use(
            hooks_dir,
            unique_session_id,
            tool_name="Task",
            tool_input={"description": "spawn an agent"}
        )

        assert result.get("result") == "block", (
            f"Task should be blocked when activeAgents > maxAgents. "
            f"Got result: {result}"
        )

    def test_continues_task_when_under_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """PreToolUse allows Task tool when activeAgents < maxAgents."""
        # Set up: under limit (2 agents, max 12)
        self._write_resources_json(
            unique_session_id,
            free_mem_mb=8000,
            active_agents=2,
            max_agents=12
        )

        result = self._run_pre_tool_use(
            hooks_dir,
            unique_session_id,
            tool_name="Task",
            tool_input={"description": "spawn an agent"}
        )

        assert result.get("result") == "continue", (
            f"Task should continue when activeAgents < maxAgents. "
            f"Got result: {result}"
        )

    def test_continues_task_when_no_resources_file(
        self, hooks_dir: Path, unique_session_id: str
    ) -> None:
        """PreToolUse allows Task when resources file doesn't exist."""
        # No resources file = graceful degradation, allow Task
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        if resource_file.exists():
            resource_file.unlink()

        result = self._run_pre_tool_use(
            hooks_dir,
            unique_session_id,
            tool_name="Task",
            tool_input={"description": "spawn an agent"}
        )

        assert result.get("result") == "continue", (
            f"Task should continue when resources file missing (graceful degradation). "
            f"Got result: {result}"
        )


class TestNonTaskToolsNotBlocked:
    """Tests that non-Task tools are not blocked by resource limits."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def unique_session_id(self) -> str:
        """Generate unique session ID for test isolation."""
        return f"test-nontask-{os.getpid()}-{id(self)}"

    @pytest.fixture
    def cleanup_temp_files(self, unique_session_id: str):
        """Clean up temp files after test."""
        yield
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        if resource_file.exists():
            resource_file.unlink()

    def _write_resources_json(
        self,
        session_id: str,
        active_agents: int = 10,
        max_agents: int = 5  # Over limit
    ) -> Path:
        """Write resources JSON file with agents at/over limit."""
        resource_file = Path(f"/tmp/claude-resources-{session_id}.json")
        data = {
            "freeMemMB": 2000,
            "activeAgents": active_agents,
            "maxAgents": max_agents,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(data))
        return resource_file

    def _run_pre_tool_use(
        self,
        hooks_dir: Path,
        session_id: str,
        tool_name: str
    ) -> dict[str, Any]:
        """Run pre-tool-use.ts and return parsed output."""
        pre_tool_use_script = hooks_dir / "pre-tool-use.sh"

        if not pre_tool_use_script.exists():
            pytest.skip("pre-tool-use.sh doesn't exist")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        input_json = json.dumps({
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_input": {}
        })

        result = subprocess.run(
            ["bash", str(pre_tool_use_script)],
            input=input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            cwd=str(hooks_dir.parent.parent)
        )

        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            pytest.fail(
                f"pre-tool-use.sh output is not valid JSON. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )

    @pytest.mark.parametrize("tool_name", [
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Glob",
        "Grep",
        "LSP",
        "WebFetch"
    ])
    def test_non_task_tools_not_blocked_at_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files, tool_name: str
    ) -> None:
        """Non-Task tools should not be blocked even when at agent limit."""
        # Set up: at limit
        self._write_resources_json(
            unique_session_id,
            active_agents=5,
            max_agents=5
        )

        result = self._run_pre_tool_use(
            hooks_dir,
            unique_session_id,
            tool_name=tool_name
        )

        assert result.get("result") == "continue", (
            f"{tool_name} should not be blocked by agent limits. "
            f"Got result: {result}"
        )


class TestBlockReasonMessage:
    """Tests for the block reason message format."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def unique_session_id(self) -> str:
        """Generate unique session ID for test isolation."""
        return f"test-reason-{os.getpid()}-{id(self)}"

    @pytest.fixture
    def cleanup_temp_files(self, unique_session_id: str):
        """Clean up temp files after test."""
        yield
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        if resource_file.exists():
            resource_file.unlink()

    def _write_resources_json(
        self,
        session_id: str,
        active_agents: int = 8,
        max_agents: int = 8
    ) -> Path:
        """Write resources JSON file."""
        resource_file = Path(f"/tmp/claude-resources-{session_id}.json")
        data = {
            "freeMemMB": 4000,
            "activeAgents": active_agents,
            "maxAgents": max_agents,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(data))
        return resource_file

    def _run_pre_tool_use(
        self,
        hooks_dir: Path,
        session_id: str,
        tool_name: str
    ) -> dict[str, Any]:
        """Run pre-tool-use.ts and return parsed output."""
        pre_tool_use_script = hooks_dir / "pre-tool-use.sh"

        if not pre_tool_use_script.exists():
            pytest.skip("pre-tool-use.sh doesn't exist")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        input_json = json.dumps({
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_input": {}
        })

        result = subprocess.run(
            ["bash", str(pre_tool_use_script)],
            input=input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            cwd=str(hooks_dir.parent.parent)
        )

        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            pytest.fail(
                f"pre-tool-use.sh output is not valid JSON. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )

    def test_block_reason_includes_agent_counts(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """Block reason should include current/max agent counts."""
        self._write_resources_json(
            unique_session_id,
            active_agents=8,
            max_agents=8
        )

        result = self._run_pre_tool_use(
            hooks_dir,
            unique_session_id,
            tool_name="Task"
        )

        reason = result.get("reason", "")

        # Check that reason includes the counts
        assert "8" in reason, (
            f"Block reason should include agent counts. Got: {reason}"
        )

    def test_block_reason_suggests_waiting(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """Block reason should suggest waiting for agents to complete."""
        self._write_resources_json(
            unique_session_id,
            active_agents=8,
            max_agents=8
        )

        result = self._run_pre_tool_use(
            hooks_dir,
            unique_session_id,
            tool_name="Task"
        )

        reason = result.get("reason", "").lower()

        # Should mention waiting or completion
        assert any(word in reason for word in ["wait", "complete", "limit", "reached"]), (
            f"Block reason should suggest waiting. Got: {reason}"
        )
