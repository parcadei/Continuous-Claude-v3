"""Tests for failure-detection hook (Phases 12-14, 17-18, 20).

This hook detects Bash/Task tool failures and suggests Nia documentation search
to help resolve errors.

TDD approach: These tests are written BEFORE implementation.
Expected to FAIL initially until:
1. .claude/hooks/src/failure-detection.ts exists
2. .claude/hooks/failure-detection.sh shell wrapper exists
3. Hook is registered in .claude/settings.json under PostToolUse
4. TypeScript compiles successfully

Hook behavior:
- Detects Bash failures: non-zero exit_code
- Detects Task failures: error keywords in output
- Outputs Nia docs search command with error + goal + context
"""

import json
import subprocess
import os
from pathlib import Path
from typing import Any

import pytest


class TestFailureDetectionHookFilesExist:
    """Tests for hook file existence."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_typescript_file_exists(self, hooks_dir: Path) -> None:
        """Verify .claude/hooks/src/failure-detection.ts exists."""
        ts_file = hooks_dir / "src" / "failure-detection.ts"
        assert ts_file.exists(), (
            f"TypeScript file not found: {ts_file}. "
            "Create .claude/hooks/src/failure-detection.ts"
        )

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Verify .claude/hooks/failure-detection.sh shell wrapper exists."""
        sh_file = hooks_dir / "failure-detection.sh"
        assert sh_file.exists(), (
            f"Shell wrapper not found: {sh_file}. "
            "Create .claude/hooks/failure-detection.sh"
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Verify shell wrapper has execute permission."""
        sh_file = hooks_dir / "failure-detection.sh"
        if not sh_file.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        assert os.access(sh_file, os.X_OK), (
            f"Shell wrapper is not executable: {sh_file}. "
            "Run: chmod +x .claude/hooks/failure-detection.sh"
        )

    def test_compiled_js_exists(self, hooks_dir: Path) -> None:
        """Verify compiled .mjs file exists in dist/."""
        mjs_file = hooks_dir / "dist" / "failure-detection.mjs"
        assert mjs_file.exists(), (
            f"Compiled JavaScript not found: {mjs_file}. "
            "Run: cd .claude/hooks && npm run build"
        )


class TestFailureDetectionHookRegistration:
    """Tests for hook registration in settings.json."""

    @pytest.fixture
    def settings_path(self) -> Path:
        """Path to settings.json."""
        return Path(__file__).parents[2] / ".claude" / "settings.json"

    @pytest.fixture
    def settings(self, settings_path: Path) -> dict:
        """Load settings.json."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")
        with open(settings_path) as f:
            return json.load(f)

    def test_hook_registered_in_post_tool_use(self, settings: dict) -> None:
        """Verify failure-detection hook is registered under PostToolUse."""
        hooks = settings.get("hooks", {})
        post_tool_use_hooks = hooks.get("PostToolUse", [])

        failure_detection_found = False
        for hook_config in post_tool_use_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "failure-detection.sh" in command:
                    failure_detection_found = True
                    break

        assert failure_detection_found, (
            "failure-detection hook must be registered in PostToolUse. "
            f"Current PostToolUse hooks: {post_tool_use_hooks}"
        )

    def test_hook_has_bash_task_matcher(self, settings: dict) -> None:
        """Verify hook has matcher for Bash and Task tools."""
        hooks = settings.get("hooks", {})
        post_tool_use_hooks = hooks.get("PostToolUse", [])

        matcher_found = False
        for hook_config in post_tool_use_hooks:
            hook_list = hook_config.get("hooks", [])
            matcher = hook_config.get("matcher", "")

            for hook in hook_list:
                command = hook.get("command", "")
                if "failure-detection.sh" in command:
                    # Check matcher includes Bash and Task
                    if "Bash" in matcher and "Task" in matcher:
                        matcher_found = True
                    elif matcher == "Bash|Task" or matcher == "Task|Bash":
                        matcher_found = True
                    break

        assert matcher_found, (
            "failure-detection hook must have matcher for 'Bash|Task'. "
            f"Current PostToolUse hooks: {post_tool_use_hooks}"
        )

    def test_hook_uses_project_dir(self, settings: dict) -> None:
        """Verify hook uses $CLAUDE_PROJECT_DIR."""
        hooks = settings.get("hooks", {})
        post_tool_use_hooks = hooks.get("PostToolUse", [])

        for hook_config in post_tool_use_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "failure-detection.sh" in command:
                    assert "$CLAUDE_PROJECT_DIR" in command, (
                        f"Hook should use $CLAUDE_PROJECT_DIR. Got: {command}"
                    )
                    return

        pytest.fail("failure-detection hook not found in settings.json")


class TestFailureDetectionTypeScriptStructure:
    """Tests for TypeScript file structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def ts_content(self, hooks_dir: Path) -> str:
        """Read TypeScript file content."""
        ts_file = hooks_dir / "src" / "failure-detection.ts"
        if not ts_file.exists():
            pytest.skip("TypeScript file doesn't exist yet")
        return ts_file.read_text()

    def test_has_main_function(self, ts_content: str) -> None:
        """Verify TypeScript has main function."""
        assert "async function main" in ts_content or "function main" in ts_content, (
            "TypeScript must have a main function"
        )

    def test_reads_stdin(self, ts_content: str) -> None:
        """Verify TypeScript reads from stdin."""
        assert "readFileSync(0" in ts_content or "process.stdin" in ts_content, (
            "TypeScript must read from stdin"
        )

    def test_has_post_tool_use_input_type(self, ts_content: str) -> None:
        """Verify TypeScript has PostToolUseInput interface or import."""
        has_interface = "interface PostToolUseInput" in ts_content
        has_import = "PostToolUseInput" in ts_content and "import" in ts_content
        assert has_interface or has_import, (
            "TypeScript must define or import PostToolUseInput interface"
        )

    def test_outputs_json(self, ts_content: str) -> None:
        """Verify TypeScript outputs JSON."""
        assert "JSON.stringify" in ts_content, (
            "TypeScript must output JSON via JSON.stringify"
        )

    def test_detects_exit_code(self, ts_content: str) -> None:
        """Verify TypeScript checks for non-zero exit_code."""
        assert "exit_code" in ts_content or "exitCode" in ts_content, (
            "TypeScript must check exit_code for Bash failures"
        )

    def test_has_error_patterns(self, ts_content: str) -> None:
        """Verify TypeScript has error detection patterns."""
        # Should detect error keywords for Task failures
        error_patterns = ["error", "Error", "failed", "Failed", "exception", "Exception"]
        has_pattern = any(p in ts_content for p in error_patterns)
        assert has_pattern, (
            "TypeScript must have error detection patterns for Task failures"
        )

    def test_includes_nia_command(self, ts_content: str) -> None:
        """Verify TypeScript includes Nia docs search command."""
        assert "nia_docs.py" in ts_content or "nia-docs" in ts_content, (
            "TypeScript must include Nia docs search command"
        )

    def test_includes_universal_search(self, ts_content: str) -> None:
        """Verify TypeScript uses universal search mode."""
        assert "universal" in ts_content, (
            "TypeScript must use 'search universal' mode for Nia"
        )


class TestFailureDetectionShellWrapperStructure:
    """Tests for shell wrapper structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def sh_content(self, hooks_dir: Path) -> str:
        """Read shell wrapper content."""
        sh_file = hooks_dir / "failure-detection.sh"
        if not sh_file.exists():
            pytest.skip("Shell wrapper doesn't exist yet")
        return sh_file.read_text()

    def test_has_shebang(self, sh_content: str) -> None:
        """Verify shell wrapper has shebang."""
        assert sh_content.startswith("#!/bin/bash"), (
            "Shell wrapper must start with #!/bin/bash"
        )

    def test_has_set_e(self, sh_content: str) -> None:
        """Verify shell wrapper has set -e."""
        assert "set -e" in sh_content, (
            "Shell wrapper must have 'set -e' for error handling"
        )

    def test_changes_to_hooks_dir(self, sh_content: str) -> None:
        """Verify shell wrapper changes to hooks directory."""
        assert 'cd "$CLAUDE_PROJECT_DIR/.claude/hooks"' in sh_content, (
            "Shell wrapper must cd to $CLAUDE_PROJECT_DIR/.claude/hooks"
        )

    def test_pipes_to_node(self, sh_content: str) -> None:
        """Verify shell wrapper pipes stdin to node."""
        has_node = "node dist/failure-detection.mjs" in sh_content
        has_cat_pipe = "cat |" in sh_content or "cat|" in sh_content
        assert has_node and has_cat_pipe, (
            "Shell wrapper must pipe stdin to node: cat | node dist/failure-detection.mjs"
        )


class TestFailureDetectionBehavior:
    """Tests for hook behavior using subprocess execution."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project directory."""
        return Path(__file__).parents[2]

    def _run_hook(self, hooks_dir: Path, project_dir: Path, input_data: dict) -> dict:
        """Run the hook with given input and return parsed output."""
        sh_file = hooks_dir / "failure-detection.sh"
        if not sh_file.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        mjs_file = hooks_dir / "dist" / "failure-detection.mjs"
        if not mjs_file.exists():
            pytest.skip("Compiled JS doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["bash", str(sh_file)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
        )

        if result.returncode != 0:
            pytest.fail(f"Hook failed: {result.stderr}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {result.stdout}")

    def test_detects_bash_failure_nonzero_exit(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Hook detects Bash failure from non-zero exit code."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Bash",
            "tool_input": {"command": "python test.py"},
            "tool_response": {
                "stdout": "",
                "stderr": "ImportError: No module named 'missing_module'",
                "exit_code": 1,
            },
        }

        output = self._run_hook(hooks_dir, project_dir, input_data)

        assert output["result"] == "continue", "Hook should not block"
        assert "message" in output, "Hook should return message on failure"
        assert "nia_docs.py" in output["message"], (
            "Message should include Nia docs command"
        )

    def test_detects_task_failure_error_keyword(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Hook detects Task failure from error keywords in output."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "implement feature"},
            "tool_response": "Error: Failed to complete task due to missing dependency",
        }

        output = self._run_hook(hooks_dir, project_dir, input_data)

        assert output["result"] == "continue", "Hook should not block"
        assert "message" in output, "Hook should return message on failure"

    def test_no_message_on_success(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Hook returns no message on successful command."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": {
                "stdout": "hello",
                "stderr": "",
                "exit_code": 0,
            },
        }

        output = self._run_hook(hooks_dir, project_dir, input_data)

        assert output["result"] == "continue", "Hook should continue"
        # No message expected on success
        assert "message" not in output or not output.get("message"), (
            "Hook should not return message on success"
        )

    def test_ignores_other_tools(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Hook ignores tools other than Bash/Task."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/path"},
            "tool_response": "file contents",
        }

        output = self._run_hook(hooks_dir, project_dir, input_data)

        assert output["result"] == "continue", "Hook should continue"
        assert "message" not in output or not output.get("message"), (
            "Hook should not return message for other tools"
        )

    def test_message_includes_error_context(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Hook message includes error context for Nia search."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Bash",
            "tool_input": {"command": "python -c 'import agentica'"},
            "tool_response": {
                "stdout": "",
                "stderr": "ModuleNotFoundError: No module named 'agentica'",
                "exit_code": 1,
            },
        }

        output = self._run_hook(hooks_dir, project_dir, input_data)

        assert "message" in output, "Hook should return message"
        message = output["message"]

        # Should include the error message in Nia query
        assert "ModuleNotFoundError" in message or "agentica" in message, (
            "Message should include error context for search"
        )

        # Should include universal search
        assert "universal" in message, (
            "Message should use 'search universal' mode"
        )

    def test_handles_malformed_input(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Hook handles malformed input gracefully."""
        sh_file = hooks_dir / "failure-detection.sh"
        if not sh_file.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        mjs_file = hooks_dir / "dist" / "failure-detection.mjs"
        if not mjs_file.exists():
            pytest.skip("Compiled JS doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        # Send invalid JSON
        result = subprocess.run(
            ["bash", str(sh_file)],
            input="not valid json",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
        )

        # Should not crash
        assert result.returncode == 0, "Hook should not crash on bad input"

        # Should return valid JSON
        try:
            output = json.loads(result.stdout)
            assert output["result"] == "continue", "Should continue on bad input"
        except json.JSONDecodeError:
            pytest.fail(f"Hook should output valid JSON: {result.stdout}")


class TestNiaQueryFormat:
    """Tests for Nia query format in failure messages."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def ts_content(self, hooks_dir: Path) -> str:
        """Read TypeScript file content."""
        ts_file = hooks_dir / "src" / "failure-detection.ts"
        if not ts_file.exists():
            pytest.skip("TypeScript file doesn't exist yet")
        return ts_file.read_text()

    def test_uses_runtime_harness(self, ts_content: str) -> None:
        """Verify Nia command uses runtime.harness."""
        assert "runtime.harness" in ts_content, (
            "Nia command should use 'uv run python -m runtime.harness'"
        )

    def test_uses_correct_script_path(self, ts_content: str) -> None:
        """Verify Nia command uses correct script path."""
        assert "scripts/nia_docs.py" in ts_content, (
            "Nia command should use 'scripts/nia_docs.py'"
        )

    def test_includes_limit_parameter(self, ts_content: str) -> None:
        """Verify Nia command includes --limit parameter."""
        assert "--limit" in ts_content, (
            "Nia command should include --limit parameter"
        )
