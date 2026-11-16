"""Tests for SubagentStart router (Phase 4 of pattern-aware hooks).

These tests verify that the subagent-start.ts router correctly:
1. Reads stdin JSON input
2. Detects pattern via PATTERN_TYPE env var
3. Dispatches to appropriate pattern handler (swarm, jury, etc.)
4. Falls back to continue if no pattern detected
5. Handles invalid JSON gracefully

Plan reference: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 4)

Tests are designed to FAIL initially (TDD approach) until Phase 4 is implemented.

Router location: .claude/hooks/src/subagent-start.ts
Shell wrapper: .claude/hooks/subagent-start.sh (Phase 5)
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest


class TestRouterFileExists:
    """Tests for router file existence."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_typescript_router_exists(self, hooks_dir: Path) -> None:
        """TypeScript router exists at expected path."""
        ts_router = hooks_dir / "src" / "subagent-start.ts"

        assert ts_router.exists(), (
            f"TypeScript router not found: {ts_router}. "
            "Create .claude/hooks/src/subagent-start.ts as part of Phase 4."
        )

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper exists at expected path (Phase 5)."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}. "
            "Create .claude/hooks/subagent-start.sh as part of Phase 5."
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}. "
            "Run: chmod +x .claude/hooks/subagent-start.sh"
        )


class TestNoPatternDetectedContinues:
    """Tests for fallback behavior when no pattern detected."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_no_pattern_type_returns_continue(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE is not set, router returns continue."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        env = os.environ.copy()
        env.pop("PATTERN_TYPE", None)  # Ensure PATTERN_TYPE is NOT set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-no-pattern",
            "agent_id": "agent-123",
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' when no PATTERN_TYPE. Got: {output}"
        )

    def test_empty_pattern_type_returns_continue(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE is empty string, router returns continue."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = ""  # Empty string
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-empty-pattern",
            "agent_id": "agent-456",
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' when PATTERN_TYPE is empty. Got: {output}"
        )

    def test_unknown_pattern_type_returns_continue(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE is unknown, router returns continue."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "unknown_pattern_xyz"
        env["PATTERN_ID"] = "test-123"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-unknown-pattern",
            "agent_id": "agent-789",
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' for unknown pattern types. Got: {output}"
        )


class TestSwarmPatternDispatch:
    """Tests for routing to swarm pattern handler."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_swarm_pattern_dispatches_to_handler(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE=swarm, router dispatches to swarm handler."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        swarm_id = "test-swarm-abc123"
        agent_id = "swarm-agent-xyz"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = swarm_id
        env["SWARM_ID"] = swarm_id  # Legacy compat
        env["AGENT_ROLE"] = "worker"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-swarm",
            "agent_id": agent_id,
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Swarm handler should return 'continue'. Got: {output}"
        )

        # Verify swarm handler was invoked via stderr logging
        stderr = result.stderr.lower()
        assert any(keyword in stderr for keyword in ["swarm", "agent", "joining"]), (
            f"Swarm handler should log agent joining. Got stderr: {result.stderr}"
        )

    def test_swarm_pattern_logs_swarm_id(self, hooks_dir: Path) -> None:
        """Swarm handler logs the SWARM_ID/PATTERN_ID."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        swarm_id = "unique-swarm-id-98765"
        agent_id = "test-agent-swarm"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = swarm_id
        env["SWARM_ID"] = swarm_id
        env["AGENT_ROLE"] = "worker"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-swarm-log",
            "agent_id": agent_id,
            "agent_type": "Explore",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        # Stderr should contain the swarm_id
        assert swarm_id in result.stderr, (
            f"Swarm handler should log swarm_id '{swarm_id}'. Got: {result.stderr}"
        )


class TestJuryPatternDispatch:
    """Tests for routing to jury pattern handler."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_jury_pattern_dispatches_to_handler(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE=jury, router dispatches to jury handler."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        jury_id = "test-jury-verdict123"
        agent_id = "juror-agent-1"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = jury_id
        env["JURY_ID"] = jury_id
        env["AGENT_ROLE"] = "juror"
        env["JUROR_INDEX"] = "0"
        env["TOTAL_JURORS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-jury",
            "agent_id": agent_id,
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Jury handler should return 'continue'. Got: {output}"
        )

        # Verify jury handler was invoked - should have isolation context
        stderr = result.stderr.lower()
        has_jury_log = any(keyword in stderr for keyword in ["jury", "juror", "isolation"])

        # OR there could be a message in the output for jury isolation context
        message = output.get("message", "").lower()
        has_jury_message = any(keyword in message for keyword in ["jury", "juror", "isolation", "vote"])

        assert has_jury_log or has_jury_message, (
            f"Jury handler should log or inject jury context. "
            f"Got stderr: {result.stderr}, message: {output.get('message', '')}"
        )

    def test_jury_pattern_injects_isolation_context(self, hooks_dir: Path) -> None:
        """Jury handler injects isolation context message."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        jury_id = "isolation-jury-456"
        juror_index = "1"
        total_jurors = "5"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = jury_id
        env["JURY_ID"] = jury_id
        env["AGENT_ROLE"] = "juror"
        env["JUROR_INDEX"] = juror_index
        env["TOTAL_JURORS"] = total_jurors
        env["JURY_ISOLATION"] = "strict"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-jury-isolation",
            "agent_id": "isolated-juror-2",
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())

        # Jury handler should inject a message with isolation context
        message = output.get("message", "")
        assert message, (
            f"Jury handler should inject isolation context message. Got: {output}"
        )

        # Message should contain juror-related context
        message_lower = message.lower()
        assert any(keyword in message_lower for keyword in ["juror", "jury", "vote", "isolation", "independent"]), (
            f"Jury isolation message should mention juror/jury/vote context. Got: {message}"
        )


class TestInvalidJsonHandling:
    """Tests for graceful handling of invalid JSON input."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_invalid_json_returns_continue(self, hooks_dir: Path) -> None:
        """Router handles invalid JSON input gracefully."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm"
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Invalid JSON
        invalid_input = "{ this is not valid json }"

        result = subprocess.run(
            [str(shell_wrapper)],
            input=invalid_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Router should handle gracefully - return 0 with continue
        assert result.returncode == 0, (
            f"Router should not crash on invalid JSON. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' for invalid JSON. Got: {output}"
        )

    def test_empty_input_returns_continue(self, hooks_dir: Path) -> None:
        """Router handles empty input gracefully."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = "test-jury"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input="",  # Empty input
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Router should not hang (timeout would catch this)
        assert result.returncode == 0, (
            f"Router should not crash on empty input. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        if result.stdout.strip():
            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Router should return 'continue' for empty input. Got: {output}"
            )

    def test_partial_json_returns_continue(self, hooks_dir: Path) -> None:
        """Router handles partial/truncated JSON input gracefully."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Truncated JSON
        partial_json = '{"session_id": "test", "agent_id":'

        result = subprocess.run(
            [str(shell_wrapper)],
            input=partial_json,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"Router should not crash on partial JSON. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' for partial JSON. Got: {output}"
        )


class TestPatternDetectionViaEnvVar:
    """Tests for PATTERN_TYPE environment variable detection."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.mark.parametrize("pattern_type,expected_handler", [
        ("swarm", "swarm"),
        ("jury", "jury"),
        ("pipeline", "pipeline"),
        ("generator_critic", "generator_critic"),
        ("hierarchical", "hierarchical"),
        ("map_reduce", "map_reduce"),
    ])
    def test_pattern_type_detection(
        self,
        hooks_dir: Path,
        pattern_type: str,
        expected_handler: str
    ) -> None:
        """Router correctly detects PATTERN_TYPE and routes to handler."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        pattern_id = f"test-{pattern_type}-123"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = pattern_type
        env["PATTERN_ID"] = pattern_id
        env["AGENT_ROLE"] = "worker"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Add pattern-specific env vars
        if pattern_type == "swarm":
            env["SWARM_ID"] = pattern_id
        elif pattern_type == "jury":
            env["JURY_ID"] = pattern_id
            env["JUROR_INDEX"] = "0"
            env["TOTAL_JURORS"] = "3"

        hook_input = json.dumps({
            "session_id": f"test-session-{pattern_type}",
            "agent_id": f"agent-{pattern_type}-xyz",
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"Router failed for PATTERN_TYPE={pattern_type}: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Handler for {pattern_type} should return 'continue'. Got: {output}"
        )


class TestRouterOutputFormat:
    """Tests for correct output format from router."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_output_is_valid_json(self, hooks_dir: Path) -> None:
        """Router output is always valid JSON."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm"
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-output",
            "agent_id": "output-agent",
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            pytest.fail(f"Router output is not valid JSON: {result.stdout}")

    def test_output_has_result_field(self, hooks_dir: Path) -> None:
        """Router output always includes result field."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = "test-jury"
        env["JURY_ID"] = "test-jury"
        env["JUROR_INDEX"] = "0"
        env["TOTAL_JURORS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-result",
            "agent_id": "result-agent",
            "agent_type": "general-purpose",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert "result" in output, (
            f"Router output must include 'result' field. Got: {output}"
        )
        assert output["result"] in ["continue", "block"], (
            f"Result must be 'continue' or 'block'. Got: {output['result']}"
        )

    def test_subagent_start_never_blocks(self, hooks_dir: Path) -> None:
        """SubagentStart router should never return block."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 5)")

        # Test with various patterns - none should block
        patterns = [
            ("swarm", {"SWARM_ID": "test-swarm"}),
            ("jury", {"JURY_ID": "test-jury", "JUROR_INDEX": "0", "TOTAL_JURORS": "3"}),
            (None, {}),  # No pattern
        ]

        for pattern_type, extra_env in patterns:
            env = os.environ.copy()
            if pattern_type:
                env["PATTERN_TYPE"] = pattern_type
                env["PATTERN_ID"] = f"test-{pattern_type}"
            env.update(extra_env)
            env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

            hook_input = json.dumps({
                "session_id": f"test-session-noblock-{pattern_type}",
                "agent_id": "noblock-agent",
                "agent_type": "general-purpose",
            })

            result = subprocess.run(
                [str(shell_wrapper)],
                input=hook_input,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir),
                timeout=30
            )

            assert result.returncode == 0, (
                f"Router failed for pattern {pattern_type}: {result.stderr}"
            )

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"SubagentStart should never block. "
                f"Pattern: {pattern_type}, Got: {output}"
            )


class TestPatternRouterImport:
    """Tests for shared pattern-router module usage."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_pattern_router_module_exists(self, hooks_dir: Path) -> None:
        """Shared pattern-router.ts module exists (Phase 1 dependency)."""
        pattern_router = hooks_dir / "src" / "shared" / "pattern-router.ts"

        assert pattern_router.exists(), (
            f"Pattern router module not found: {pattern_router}. "
            "Create .claude/hooks/src/shared/pattern-router.ts as part of Phase 1."
        )

    def test_db_utils_module_exists(self, hooks_dir: Path) -> None:
        """Shared db-utils.ts module exists (Phase 2 dependency)."""
        db_utils = hooks_dir / "src" / "shared" / "db-utils.ts"

        assert db_utils.exists(), (
            f"DB utils module not found: {db_utils}. "
            "Create .claude/hooks/src/shared/db-utils.ts as part of Phase 2."
        )

    def test_swarm_pattern_module_exists(self, hooks_dir: Path) -> None:
        """Swarm pattern module exists (Phase 3 dependency)."""
        swarm_pattern = hooks_dir / "src" / "patterns" / "swarm.ts"

        assert swarm_pattern.exists(), (
            f"Swarm pattern module not found: {swarm_pattern}. "
            "Create .claude/hooks/src/patterns/swarm.ts as part of Phase 3."
        )
