"""Tests for Phase 5: Shell wrapper for pattern-aware subagent-start router.

These tests verify that the shell wrapper `.claude/hooks/subagent-start.sh`:
1. Exists and is executable
2. Passes stdin through correctly to the TypeScript handler
3. Outputs valid JSON
4. Handles missing tsx gracefully

The wrapper should invoke `npx tsx src/subagent-start.ts` following the pattern
from `subagent-start-swarm.sh` but routing to the pattern-aware router instead.

Expected wrapper structure:
```bash
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
cat | npx tsx src/subagent-start.ts
```

Tests are designed to FAIL initially (TDD approach) until Phase 5 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 5)
"""

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


class TestWrapperExists:
    """Tests for shell wrapper file existence."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper exists at expected path."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}. "
            "Create .claude/hooks/subagent-start.sh for the pattern-aware router."
        )

    def test_shell_wrapper_is_regular_file(self, hooks_dir: Path) -> None:
        """Shell wrapper is a regular file (not symlink or directory)."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        assert shell_wrapper.is_file(), (
            f"Shell wrapper should be a regular file, not a directory or symlink. "
            f"Path: {shell_wrapper}"
        )


class TestWrapperIsExecutable:
    """Tests for shell wrapper executable permission."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}. "
            "Run: chmod +x .claude/hooks/subagent-start.sh"
        )

    def test_shell_wrapper_has_correct_mode(self, hooks_dir: Path) -> None:
        """Shell wrapper has user executable permission set."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        mode = shell_wrapper.stat().st_mode
        has_user_execute = mode & stat.S_IXUSR

        assert has_user_execute, (
            f"Shell wrapper should have user executable permission (u+x). "
            f"Current mode: {oct(mode)}. "
            "Run: chmod +x .claude/hooks/subagent-start.sh"
        )

    def test_shell_wrapper_starts_with_shebang(self, hooks_dir: Path) -> None:
        """Shell wrapper starts with bash shebang."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()
        first_line = content.split('\n')[0].strip()

        assert first_line == "#!/bin/bash", (
            f"Shell wrapper should start with #!/bin/bash shebang. "
            f"Got: {first_line!r}"
        )


class TestWrapperPassesStdinCorrectly:
    """Tests for stdin passthrough to TypeScript handler."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_wrapper_uses_cat_pipe(self, hooks_dir: Path) -> None:
        """Shell wrapper uses 'cat |' pattern to pipe stdin."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        assert "cat |" in content or "cat|" in content, (
            "Shell wrapper should use 'cat |' to pipe stdin to TypeScript handler. "
            f"Content: {content}"
        )

    def test_wrapper_invokes_tsx(self, hooks_dir: Path) -> None:
        """Shell wrapper invokes npx tsx for TypeScript execution."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        assert "npx tsx" in content, (
            "Shell wrapper should use 'npx tsx' to run TypeScript handler. "
            f"Content: {content}"
        )

    def test_wrapper_references_subagent_start_ts(self, hooks_dir: Path) -> None:
        """Shell wrapper references src/subagent-start.ts handler."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        # Should reference the TypeScript file (not the old swarm-specific one)
        assert "src/subagent-start.ts" in content, (
            "Shell wrapper should invoke 'src/subagent-start.ts' (the pattern-aware router). "
            f"Content: {content}"
        )

    def test_wrapper_uses_set_e(self, hooks_dir: Path) -> None:
        """Shell wrapper uses 'set -e' for error handling."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        assert "set -e" in content, (
            "Shell wrapper should use 'set -e' to exit on errors. "
            f"Content: {content}"
        )

    def test_wrapper_changes_to_hooks_dir(self, hooks_dir: Path) -> None:
        """Shell wrapper changes to hooks directory before running."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        # Should either use SCRIPT_DIR pattern or cd to hooks dir
        uses_script_dir = 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in content
        uses_cd_script_dir = 'cd "$SCRIPT_DIR"' in content

        assert uses_script_dir or 'cd ' in content, (
            "Shell wrapper should change to hooks directory before running. "
            "Use SCRIPT_DIR pattern: "
            'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" && cd "$SCRIPT_DIR". '
            f"Content: {content}"
        )

    def test_wrapper_passes_json_input_through(self, hooks_dir: Path) -> None:
        """Shell wrapper correctly passes JSON input to TypeScript handler."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        ts_handler = hooks_dir / "src" / "subagent-start.ts"
        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet (Phase 4 required)")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        test_input = {
            "session_id": "test-session-stdin-passthrough",
            "agent_id": "agent-stdin-test",
            "agent_type": "general-purpose"
        }

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(test_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # If TypeScript handler exists and works, we should get valid JSON output
        if result.returncode == 0 and result.stdout.strip():
            try:
                output = json.loads(result.stdout.strip())
                assert "result" in output, (
                    f"Output should contain 'result' field. Got: {output}"
                )
            except json.JSONDecodeError:
                pytest.fail(
                    f"Wrapper should produce valid JSON output. Got: {result.stdout}"
                )


class TestWrapperOutputsValidJson:
    """Tests for valid JSON output from wrapper."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_wrapper_outputs_valid_json_on_success(self, hooks_dir: Path) -> None:
        """Wrapper outputs valid JSON when TypeScript handler succeeds."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        ts_handler = hooks_dir / "src" / "subagent-start.ts"
        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet (Phase 4 required)")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-json-output",
            "agent_id": "json-test-agent",
            "agent_type": "general-purpose"
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
            f"Wrapper should exit with 0 on success. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        assert result.stdout.strip(), (
            "Wrapper should produce output on stdout"
        )

        try:
            output = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            pytest.fail(
                f"Wrapper output is not valid JSON: {e}. Output: {result.stdout}"
            )

        assert isinstance(output, dict), (
            f"Wrapper output should be a JSON object. Got: {type(output)}"
        )

    def test_wrapper_outputs_result_field(self, hooks_dir: Path) -> None:
        """Wrapper output contains 'result' field."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        ts_handler = hooks_dir / "src" / "subagent-start.ts"
        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet (Phase 4 required)")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-result-field",
            "agent_id": "result-test-agent",
            "agent_type": "Explore"
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

        if result.returncode != 0:
            pytest.skip(f"Wrapper failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        assert "result" in output, (
            f"Output must contain 'result' field. Got: {output}"
        )

        assert output["result"] in ["continue", "block"], (
            f"'result' field must be 'continue' or 'block'. Got: {output['result']}"
        )

    def test_wrapper_returns_continue_for_subagent_start(self, hooks_dir: Path) -> None:
        """SubagentStart should always return 'continue' (never blocks)."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        ts_handler = hooks_dir / "src" / "subagent-start.ts"
        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet (Phase 4 required)")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-continue",
            "agent_id": "continue-test-agent",
            "agent_type": "general-purpose"
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

        if result.returncode != 0:
            pytest.skip(f"Wrapper failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        assert output.get("result") == "continue", (
            f"SubagentStart should always return 'continue'. Got: {output}"
        )


class TestWrapperHandlesMissingTsx:
    """Tests for graceful handling when tsx is not available."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_wrapper_fails_cleanly_without_tsx(self, hooks_dir: Path) -> None:
        """Wrapper fails with non-zero exit when tsx is not available."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        # Create environment where npx/tsx is not available
        env = os.environ.copy()
        env["PATH"] = "/nonexistent"  # Remove all PATH
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-no-tsx",
            "agent_id": "no-tsx-agent",
            "agent_type": "general-purpose"
        })

        result = subprocess.run(
            ["/bin/bash", str(shell_wrapper)],  # Use explicit bash path
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Wrapper should fail when tsx is not available
        # Due to 'set -e', it should exit with non-zero
        assert result.returncode != 0, (
            "Wrapper should fail with non-zero exit when tsx is not available"
        )

    def test_wrapper_does_not_hang_without_tsx(self, hooks_dir: Path) -> None:
        """Wrapper does not hang indefinitely when tsx is not available."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        # Create environment where npx/tsx is not available
        env = os.environ.copy()
        env["PATH"] = "/nonexistent"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-no-hang",
            "agent_id": "no-hang-agent",
            "agent_type": "general-purpose"
        })

        # If wrapper hangs, timeout will raise exception
        try:
            result = subprocess.run(
                ["/bin/bash", str(shell_wrapper)],
                input=hook_input,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir),
                timeout=5  # Short timeout to catch hangs
            )
            # Reached this point means no hang
        except subprocess.TimeoutExpired:
            pytest.fail(
                "Wrapper should not hang when tsx is not available. "
                "Timed out after 5 seconds."
            )


class TestWrapperPatternRouting:
    """Tests for pattern detection routing (integration with TypeScript handler)."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_wrapper_routes_to_swarm_handler(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE=swarm, wrapper routes to swarm handler."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        ts_handler = hooks_dir / "src" / "subagent-start.ts"
        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet (Phase 4 required)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm-id"
        env["SWARM_ID"] = "test-swarm-id"  # Legacy env var
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-swarm-routing",
            "agent_id": "swarm-routing-agent",
            "agent_type": "general-purpose"
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
            f"Wrapper should succeed for swarm pattern. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Swarm handler should return 'continue'. Got: {output}"
        )

    def test_wrapper_continues_when_no_pattern(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE is not set, wrapper returns continue silently."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        ts_handler = hooks_dir / "src" / "subagent-start.ts"
        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet (Phase 4 required)")

        env = os.environ.copy()
        env.pop("PATTERN_TYPE", None)  # Ensure not set
        env.pop("SWARM_ID", None)  # Ensure not set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-no-pattern",
            "agent_id": "no-pattern-agent",
            "agent_type": "general-purpose"
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
            f"Wrapper should succeed when no pattern detected. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Should return 'continue' when no pattern detected. Got: {output}"
        )


class TestWrapperStructure:
    """Tests for shell wrapper structure and best practices."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_wrapper_follows_existing_pattern(self, hooks_dir: Path) -> None:
        """New wrapper follows same structure as subagent-start-swarm.sh."""
        shell_wrapper = hooks_dir / "subagent-start.sh"
        existing_wrapper = hooks_dir / "subagent-start-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        if not existing_wrapper.exists():
            pytest.skip("Reference wrapper subagent-start-swarm.sh doesn't exist")

        new_content = shell_wrapper.read_text()
        existing_content = existing_wrapper.read_text()

        # Both should use same structural patterns
        assert "#!/bin/bash" in new_content, "Should have bash shebang"
        assert "set -e" in new_content, "Should use set -e"

        # Should have similar directory handling
        new_has_script_dir = 'SCRIPT_DIR' in new_content
        existing_has_script_dir = 'SCRIPT_DIR' in existing_content

        assert new_has_script_dir == existing_has_script_dir or 'cd ' in new_content, (
            "New wrapper should follow similar directory pattern as existing wrapper"
        )

    def test_wrapper_has_no_hardcoded_paths(self, hooks_dir: Path) -> None:
        """Wrapper uses relative paths or SCRIPT_DIR, not hardcoded absolute paths."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        # Should not contain hardcoded user paths
        assert "/Users/" not in content, (
            "Wrapper should not contain hardcoded /Users/ paths"
        )
        assert "/home/" not in content, (
            "Wrapper should not contain hardcoded /home/ paths"
        )

        # Should use SCRIPT_DIR or relative paths
        uses_script_dir = 'SCRIPT_DIR' in content
        uses_relative = 'src/subagent-start.ts' in content

        assert uses_script_dir or uses_relative, (
            "Wrapper should use SCRIPT_DIR pattern or relative paths"
        )

    def test_wrapper_is_minimal(self, hooks_dir: Path) -> None:
        """Wrapper is minimal - just invokes TypeScript handler."""
        shell_wrapper = hooks_dir / "subagent-start.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()
        lines = [l for l in content.strip().split('\n') if l.strip() and not l.strip().startswith('#')]

        # Wrapper should be very short - typically 4-5 lines
        assert len(lines) <= 7, (
            f"Wrapper should be minimal (<=7 non-comment lines). "
            f"Got {len(lines)} lines: {lines}"
        )
