"""Tests for SubagentStart hook (Phases 18-19).

These tests verify that the SubagentStart hook correctly:
1. Shell wrapper and TypeScript handler exist
2. Logs agent joining swarm when SWARM_ID is set
3. Continues silently when SWARM_ID is not set
4. Handles missing agent_id gracefully
5. Works with various agent_types
6. Is registered in settings.json

Note: Claude Code v2.0.43+ provides agent_id field in SubagentStart/SubagentStop.

SubagentStart input structure:
```typescript
interface SubagentStartInput {
    session_id: string;
    agent_id: string;    // New in v2.0.43
    agent_type: string;  // e.g., "general-purpose", "Explore"
}
```

Tests are designed to FAIL initially (TDD approach) until Phases 18-19 are implemented.

See plan: thoughts/shared/plans/2025-12-28-user-triggered-agentica.md (Phase 18-19)
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestSubagentStartHookFiles:
    """Tests for SubagentStart hook file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper exists at expected path."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}. "
            "Create .claude/hooks/subagent-start-swarm.sh"
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}. "
            "Run: chmod +x .claude/hooks/subagent-start-swarm.sh"
        )

    def test_typescript_handler_exists(self, hooks_dir: Path) -> None:
        """TypeScript handler exists at expected path."""
        ts_handler = hooks_dir / "src" / "subagent-start-swarm.ts"

        assert ts_handler.exists(), (
            f"TypeScript handler not found: {ts_handler}. "
            "Create .claude/hooks/src/subagent-start-swarm.ts"
        )

    def test_shell_wrapper_invokes_typescript(self, hooks_dir: Path) -> None:
        """Shell wrapper invokes TypeScript via npx tsx or compiled JS."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        # Should call npx tsx with the TypeScript file or node with compiled JS
        has_tsx = "npx tsx" in content
        has_node = "node dist/" in content
        has_reference = "subagent-start-swarm" in content

        assert has_tsx or has_node, (
            "Shell wrapper should invoke TypeScript via 'npx tsx' or compiled JS via 'node dist/'. "
            f"Content: {content}"
        )
        assert has_reference, (
            "Shell wrapper should reference subagent-start-swarm handler. "
            f"Content: {content}"
        )


class TestLogsAgentJoiningSwarm:
    """Tests for swarm awareness - logging when agent joins."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_logs_agent_joining_swarm(self, hooks_dir: Path) -> None:
        """When SWARM_ID is set, logs agent joining to stderr."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-abc123"
        agent_id = "subagent-xyz789"
        agent_type = "general-purpose"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-123",
            "agent_id": agent_id,
            "agent_type": agent_type,
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

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Output should be valid JSON with result: 'continue'
        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should return 'continue'. Got: {output}"
        )

        # Stderr should contain logging about agent joining
        stderr = result.stderr.lower()
        assert "subagent" in stderr or "agent" in stderr or "swarm" in stderr, (
            f"Hook should log agent joining swarm to stderr. Got stderr: {result.stderr}"
        )

    def test_logs_contain_agent_id(self, hooks_dir: Path) -> None:
        """Log message includes the agent_id."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-log"
        agent_id = "my-unique-agent-id-12345"
        agent_type = "Explore"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-456",
            "agent_id": agent_id,
            "agent_type": agent_type,
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

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Stderr should contain the agent_id
        assert agent_id in result.stderr, (
            f"Hook should log agent_id '{agent_id}' to stderr. Got: {result.stderr}"
        )

    def test_logs_contain_swarm_id(self, hooks_dir: Path) -> None:
        """Log message includes the SWARM_ID."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "unique-swarm-id-67890"
        agent_id = "agent-for-swarm-test"
        agent_type = "general-purpose"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-789",
            "agent_id": agent_id,
            "agent_type": agent_type,
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

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Stderr should contain the swarm_id
        assert swarm_id in result.stderr, (
            f"Hook should log swarm_id '{swarm_id}' to stderr. Got: {result.stderr}"
        )


class TestNoSwarmIdContinuesSilently:
    """Tests for behavior when SWARM_ID is not set."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_no_swarm_id_continues_silently(self, hooks_dir: Path) -> None:
        """When SWARM_ID not set, continues without logging."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env.pop("SWARM_ID", None)  # Ensure SWARM_ID is NOT set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-no-swarm",
            "agent_id": "orphan-agent-123",
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

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should return 'continue' when no SWARM_ID. Got: {output}"
        )

        # No message should be injected (or minimal)
        message = output.get("message", "")
        assert "swarm" not in message.lower(), (
            f"Hook should not mention swarm when SWARM_ID not set. Got message: {message}"
        )

    def test_empty_swarm_id_continues_silently(self, hooks_dir: Path) -> None:
        """When SWARM_ID is empty string, continues without logging."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = ""  # Empty string
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-empty-swarm",
            "agent_id": "agent-empty-swarm",
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

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should return 'continue' when SWARM_ID is empty. Got: {output}"
        )


class TestHandlesMissingAgentId:
    """Tests for handling missing agent_id gracefully."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_handles_missing_agent_id(self, hooks_dir: Path) -> None:
        """Handles missing agent_id gracefully (older Claude Code versions)."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-missing-id"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Input without agent_id (older Claude Code version)
        hook_input = json.dumps({
            "session_id": "test-session-old-version",
            # Note: no agent_id field!
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

        # Hook should NOT crash
        assert result.returncode == 0, (
            f"Hook should not crash when agent_id missing. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should continue when agent_id missing. Got: {output}"
        )

    def test_handles_null_agent_id(self, hooks_dir: Path) -> None:
        """Handles null agent_id gracefully."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-null-id"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Input with null agent_id
        hook_input = json.dumps({
            "session_id": "test-session-null",
            "agent_id": None,  # Explicitly null
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
            f"Hook should not crash when agent_id is null. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should continue when agent_id is null. Got: {output}"
        )


class TestHandlesAllAgentTypes:
    """Tests for handling various agent_types."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.mark.parametrize("agent_type", [
        "general-purpose",
        "Explore",
        "CodeEdit",
        "Search",
        "custom-type",
        "",  # Empty string
    ])
    def test_handles_various_agent_types(
        self,
        hooks_dir: Path,
        agent_type: str
    ) -> None:
        """Works with various agent_types."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-types"
        agent_id = f"agent-{agent_type or 'empty'}-123"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-types",
            "agent_id": agent_id,
            "agent_type": agent_type,
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
            f"Hook failed for agent_type '{agent_type}': {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should continue for agent_type '{agent_type}'. Got: {output}"
        )

    def test_handles_missing_agent_type(self, hooks_dir: Path) -> None:
        """Works when agent_type is missing."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-no-type"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Input without agent_type
        hook_input = json.dumps({
            "session_id": "test-session-no-type",
            "agent_id": "agent-no-type",
            # Note: no agent_type field!
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
            f"Hook should not crash when agent_type missing. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should continue when agent_type missing. Got: {output}"
        )


class TestSettingsJsonRegistration:
    """Tests for SubagentStart hook registration in settings.json."""

    @pytest.fixture
    def settings_path(self) -> Path:
        """Path to settings.json."""
        return Path(__file__).parents[2] / ".claude" / "settings.json"

    def test_settings_json_exists(self, settings_path: Path) -> None:
        """Verify settings.json exists."""
        assert settings_path.exists(), f"settings.json not found: {settings_path}"

    def test_settings_json_valid(self, settings_path: Path) -> None:
        """Verify settings.json is valid JSON."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            try:
                json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"settings.json is not valid JSON: {e}")

    def test_subagent_start_hook_registered(self, settings_path: Path) -> None:
        """SubagentStart hook for swarm is registered in settings.json."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        subagent_start_hooks = hooks.get("SubagentStart", [])

        # Find our swarm hook
        swarm_hook_found = False
        for hook_config in subagent_start_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "subagent-start-swarm" in command:
                    swarm_hook_found = True
                    break

        assert swarm_hook_found, (
            "SubagentStart hook for swarm coordination must be registered in settings.json. "
            "Expected hooks.SubagentStart to contain command with 'subagent-start-swarm'. "
            f"Current SubagentStart hooks: {subagent_start_hooks}"
        )

    def test_subagent_start_hook_uses_project_dir(self, settings_path: Path) -> None:
        """SubagentStart hook command uses $CLAUDE_PROJECT_DIR."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        subagent_start_hooks = hooks.get("SubagentStart", [])

        # Find our swarm hook and check path
        for hook_config in subagent_start_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "subagent-start-swarm" in command:
                    assert "$CLAUDE_PROJECT_DIR" in command, (
                        "Hook command should use $CLAUDE_PROJECT_DIR for project-local hooks. "
                        f"Got: {command}"
                    )
                    return

        pytest.skip("SubagentStart swarm hook not found")


class TestErrorHandling:
    """Tests for graceful error handling."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_invalid_json_input_graceful(self, hooks_dir: Path) -> None:
        """Hook handles invalid JSON input gracefully."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Send invalid JSON
        invalid_input = "{ not valid json }"

        result = subprocess.run(
            [str(shell_wrapper)],
            input=invalid_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Hook should either handle gracefully or fail with clear error
        # If it returns 0, output should be valid JSON
        if result.returncode == 0:
            try:
                output = json.loads(result.stdout.strip())
                assert output.get("result") in ["continue", "block"], (
                    f"Hook output should have valid result. Got: {output}"
                )
            except json.JSONDecodeError:
                pytest.fail(
                    f"Hook returned 0 but output is not valid JSON: {result.stdout}"
                )

    def test_empty_input_graceful(self, hooks_dir: Path) -> None:
        """Hook handles empty input gracefully."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = "test-swarm"
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

        # Hook should not hang indefinitely (timeout would catch this)
        # If it returns 0, output should be valid JSON
        if result.returncode == 0 and result.stdout.strip():
            try:
                output = json.loads(result.stdout.strip())
                assert output.get("result") in ["continue", "block"], (
                    f"Hook output should have valid result. Got: {output}"
                )
            except json.JSONDecodeError:
                pass  # Empty output is acceptable for error case


class TestContextInjection:
    """Tests for SWARM_ID context propagation/injection."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_can_inject_swarm_context_message(self, hooks_dir: Path) -> None:
        """Hook CAN inject a message with swarm context (optional feature)."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-context"
        agent_id = "context-agent-123"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-context",
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

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())

        # Hook may optionally include a message with swarm context
        # This is an optional feature - if message exists, it should be useful
        message = output.get("message", "")
        if message:
            # If there's a message, it should provide useful context
            assert len(message) > 0, "If message provided, it should not be empty"

    def test_always_returns_continue(self, hooks_dir: Path) -> None:
        """SubagentStart hook should always return continue (never block)."""
        shell_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-continue"
        agent_id = "continue-agent-123"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-continue",
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

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())

        # SubagentStart should NEVER block - it's just for logging/context
        assert output.get("result") == "continue", (
            f"SubagentStart hook should always return 'continue', never 'block'. "
            f"Got: {output}"
        )
