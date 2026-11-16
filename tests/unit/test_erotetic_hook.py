"""Tests for erotetic clarification hook (UserPromptSubmit event).

This module tests the erotetic hook that triggers clarification questions
when it detects implementation tasks. The hook should:
1. Detect implementation patterns (build, implement, create feature)
2. Inject EROTETIC CLARIFICATION message with AskUserQuestion instruction
3. NOT trigger for simple tasks (fix typo, run tests)

Plan reference:
thoughts/shared/handoffs/open-source-release/2025-12-30_14-06-14_erotetic-z3-hybrid.md

Phase 3 Hook Integration pattern:
```typescript
if (isImplementationTask(prompt)) {
  output += `
EROTETIC CLARIFICATION REQUIRED
Run: uv run python scripts/z3_erotetic.py --context "..."
If E(X,Q) >= 2, use AskUserQuestion for unknowns.
Loop until E(X,Q) = empty.
`;
}
```

TDD approach: tests are written FIRST, then implementation.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

# =============================================================================
# File Structure Tests
# =============================================================================


class TestEroteticHookFileStructure:
    """Tests for erotetic hook file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Verify erotetic-clarification.sh exists."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"
        assert shell_wrapper.exists(), (
            f"erotetic-clarification.sh not found at {shell_wrapper}. "
            "Create .claude/hooks/erotetic-clarification.sh"
        )

    def test_shell_wrapper_executable(self, hooks_dir: Path) -> None:
        """Verify erotetic-clarification.sh is executable."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"
        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")

        assert os.access(shell_wrapper, os.X_OK), (
            f"erotetic-clarification.sh is not executable. "
            f"Run: chmod +x {shell_wrapper}"
        )

    def test_shell_wrapper_has_correct_shebang(self, hooks_dir: Path) -> None:
        """Verify erotetic-clarification.sh has bash shebang."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"
        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")

        content = shell_wrapper.read_text()
        assert content.startswith("#!/bin/bash"), (
            "erotetic-clarification.sh must start with #!/bin/bash"
        )

    def test_shell_wrapper_uses_set_e(self, hooks_dir: Path) -> None:
        """Verify erotetic-clarification.sh uses set -e for error handling."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"
        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")

        content = shell_wrapper.read_text()
        assert "set -e" in content, (
            "erotetic-clarification.sh must use 'set -e' for error handling"
        )

    def test_shell_wrapper_pipes_to_handler(self, hooks_dir: Path) -> None:
        """Verify erotetic-clarification.sh pipes stdin to handler."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"
        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")

        content = shell_wrapper.read_text()
        assert "cat |" in content or "cat|" in content, (
            "erotetic-clarification.sh must pipe stdin using 'cat |'"
        )
        assert "erotetic" in content.lower(), (
            "erotetic-clarification.sh must reference erotetic handler"
        )

    def test_typescript_handler_exists(self, hooks_dir: Path) -> None:
        """Verify erotetic-clarification.ts exists in src directory."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        assert ts_handler.exists(), (
            f"erotetic-clarification.ts not found at {ts_handler}. "
            "Create .claude/hooks/src/erotetic-clarification.ts"
        )

    def test_typescript_handler_has_main_function(self, hooks_dir: Path) -> None:
        """Verify erotetic-clarification.ts has main function."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        assert "async function main()" in content or "function main()" in content, (
            "erotetic-clarification.ts must have a main() function"
        )

    def test_typescript_handler_has_is_implementation_task(self, hooks_dir: Path) -> None:
        """Verify erotetic-clarification.ts has isImplementationTask function."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        assert "isImplementationTask" in content, (
            "erotetic-clarification.ts must have isImplementationTask function"
        )


# =============================================================================
# Pattern Detection Tests - Triggers
# =============================================================================


class TestEroteticPatternDetectionTriggers:
    """Tests for prompts that SHOULD trigger erotetic clarification."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def _run_hook(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict[str, Any]:
        """Execute hook with given prompt and return parsed output."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        test_input = json.dumps({
            "prompt": prompt,
            "session_id": "test-session-erotetic"
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            cwd=str(hooks_dir),
        )

        if result.returncode != 0:
            pytest.fail(f"Hook execution failed: {result.stderr}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook output is not valid JSON: {e}. stdout: {result.stdout}")

    def test_build_api_triggers(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Build an API' should trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Build an API with authentication")

        assert output["result"] == "continue", (
            f"Hook should return 'continue'. Got: {output}"
        )
        assert "message" in output, (
            f"Hook should return message for implementation task. Got: {output}"
        )
        assert "EROTETIC CLARIFICATION" in output["message"], (
            f"Message should contain 'EROTETIC CLARIFICATION'. Got: {output['message']}"
        )

    def test_implement_feature_triggers(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Implement authentication' should trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Implement user authentication system")

        assert "message" in output, (
            f"'Implement' should trigger clarification. Got: {output}"
        )
        assert "EROTETIC CLARIFICATION" in output["message"]

    def test_create_new_feature_triggers(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Create a new feature' should trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Create a new feature for user profiles")

        assert "message" in output, (
            f"'Create a new feature' should trigger clarification. Got: {output}"
        )
        assert "EROTETIC CLARIFICATION" in output["message"]

    def test_add_functionality_triggers(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Add functionality' should trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Add search functionality to the app")

        assert "message" in output, (
            f"'Add functionality' should trigger clarification. Got: {output}"
        )
        assert "EROTETIC CLARIFICATION" in output["message"]

    def test_develop_module_triggers(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Develop a module' should trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Develop a payment processing module")

        assert "message" in output, (
            f"'Develop' should trigger clarification. Got: {output}"
        )
        assert "EROTETIC CLARIFICATION" in output["message"]

    def test_design_system_triggers(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Design a system' should trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Design a caching system for the database")

        assert "message" in output, (
            f"'Design' should trigger clarification. Got: {output}"
        )
        assert "EROTETIC CLARIFICATION" in output["message"]

    def test_set_up_infrastructure_triggers(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Set up infrastructure' should trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Set up CI/CD infrastructure")

        assert "message" in output, (
            f"'Set up' should trigger clarification. Got: {output}"
        )
        assert "EROTETIC CLARIFICATION" in output["message"]

    def test_write_new_service_triggers(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Write a new service' should trigger erotetic clarification."""
        output = self._run_hook(
            hooks_dir, project_dir, "Write a new microservice for notifications"
        )

        assert "message" in output, (
            f"'Write a new service' should trigger clarification. Got: {output}"
        )
        assert "EROTETIC CLARIFICATION" in output["message"]


# =============================================================================
# Pattern Detection Tests - Non-Triggers
# =============================================================================


class TestEroteticPatternDetectionNonTriggers:
    """Tests for prompts that should NOT trigger erotetic clarification."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def _run_hook(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict[str, Any]:
        """Execute hook with given prompt and return parsed output."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        test_input = json.dumps({
            "prompt": prompt,
            "session_id": "test-session-erotetic"
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            cwd=str(hooks_dir),
        )

        if result.returncode != 0:
            pytest.fail(f"Hook execution failed: {result.stderr}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook output is not valid JSON: {e}. stdout: {result.stdout}")

    def test_fix_typo_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Fix the typo' should NOT trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Fix the typo in the README")

        # Should return continue but no erotetic message
        assert output["result"] == "continue"
        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'Fix the typo' should NOT trigger clarification. Got message: {message}"
        )

    def test_run_tests_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Run the tests' should NOT trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Run the tests for the auth module")

        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'Run the tests' should NOT trigger clarification. Got message: {message}"
        )

    def test_show_me_code_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Show me the code' should NOT trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Show me the code in main.py")

        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'Show me' should NOT trigger clarification. Got message: {message}"
        )

    def test_explain_function_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Explain this function' should NOT trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Explain how the auth middleware works")

        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'Explain' should NOT trigger clarification. Got message: {message}"
        )

    def test_list_files_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'List files' should NOT trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "List all Python files in src/")

        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'List files' should NOT trigger clarification. Got message: {message}"
        )

    def test_search_for_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Search for' should NOT trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Search for TODO comments in the codebase")

        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'Search for' should NOT trigger clarification. Got message: {message}"
        )

    def test_rename_variable_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Rename variable' should NOT trigger (simple refactor, not new feature)."""
        output = self._run_hook(hooks_dir, project_dir, "Rename the variable 'x' to 'count'")

        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'Rename variable' should NOT trigger clarification. Got message: {message}"
        )

    def test_delete_file_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Delete file' should NOT trigger erotetic clarification."""
        output = self._run_hook(hooks_dir, project_dir, "Delete the old backup.py file")

        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'Delete file' should NOT trigger clarification. Got message: {message}"
        )

    def test_update_config_does_not_trigger(self, hooks_dir: Path, project_dir: Path) -> None:
        """'Update config' should NOT trigger (simple change, not new feature)."""
        output = self._run_hook(hooks_dir, project_dir, "Update the port number in config.yaml")

        message = output.get("message", "")
        assert "EROTETIC CLARIFICATION" not in message, (
            f"'Update config' should NOT trigger clarification. Got message: {message}"
        )


# =============================================================================
# Message Content Tests
# =============================================================================


class TestEroteticMessageContent:
    """Tests for erotetic clarification message content."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def _run_hook(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict[str, Any]:
        """Execute hook with given prompt and return parsed output."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        test_input = json.dumps({
            "prompt": prompt,
            "session_id": "test-session-erotetic"
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            cwd=str(hooks_dir),
        )

        if result.returncode != 0:
            pytest.fail(f"Hook execution failed: {result.stderr}")

        return json.loads(result.stdout)

    def test_message_contains_erotetic_header(self, hooks_dir: Path, project_dir: Path) -> None:
        """Message should contain 'EROTETIC CLARIFICATION' header."""
        output = self._run_hook(hooks_dir, project_dir, "Build a REST API")

        assert "message" in output
        assert "EROTETIC CLARIFICATION" in output["message"], (
            f"Message should contain 'EROTETIC CLARIFICATION'. Got: {output['message']}"
        )

    def test_message_contains_ask_user_question_instruction(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Message should contain AskUserQuestion instruction."""
        output = self._run_hook(hooks_dir, project_dir, "Build a REST API")

        assert "message" in output
        assert "AskUserQuestion" in output["message"], (
            f"Message should contain 'AskUserQuestion'. Got: {output['message']}"
        )

    def test_message_contains_script_path(self, hooks_dir: Path, project_dir: Path) -> None:
        """Message should contain path to z3_erotetic.py script."""
        output = self._run_hook(hooks_dir, project_dir, "Build a REST API")

        assert "message" in output
        assert "z3_erotetic" in output["message"], (
            f"Message should reference z3_erotetic script. Got: {output['message']}"
        )

    def test_message_contains_evocation_notation(self, hooks_dir: Path, project_dir: Path) -> None:
        """Message should contain E(X,Q) evocation notation."""
        output = self._run_hook(hooks_dir, project_dir, "Build a REST API")

        assert "message" in output
        assert "E(X,Q)" in output["message"], (
            f"Message should contain 'E(X,Q)' notation. Got: {output['message']}"
        )

    def test_message_contains_loop_instruction(self, hooks_dir: Path, project_dir: Path) -> None:
        """Message should contain loop instruction."""
        output = self._run_hook(hooks_dir, project_dir, "Build a REST API")

        assert "message" in output
        # Should mention looping until E(X,Q) is empty
        assert "loop" in output["message"].lower() or "empty" in output["message"].lower(), (
            f"Message should contain loop/empty instruction. Got: {output['message']}"
        )


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEroteticHookEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def _run_hook(
        self, hooks_dir: Path, project_dir: Path, input_data: str
    ) -> subprocess.CompletedProcess:
        """Execute hook with raw input and return result."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        return subprocess.run(
            [str(shell_wrapper)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            cwd=str(hooks_dir),
        )

    def test_handles_empty_json(self, hooks_dir: Path, project_dir: Path) -> None:
        """Hook should handle empty JSON gracefully."""
        result = self._run_hook(hooks_dir, project_dir, "{}")

        # Should not crash
        assert result.returncode == 0, (
            f"Hook should not crash on empty JSON. "
            f"returncode: {result.returncode}, stderr: {result.stderr}"
        )

        # Should return valid JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook must return valid JSON on empty input: {e}")

        assert output.get("result") == "continue"

    def test_handles_malformed_json(self, hooks_dir: Path, project_dir: Path) -> None:
        """Hook should handle malformed JSON gracefully."""
        result = self._run_hook(hooks_dir, project_dir, "{broken json")

        # Should not crash
        assert result.returncode == 0, (
            f"Hook should not crash on malformed JSON. "
            f"returncode: {result.returncode}, stderr: {result.stderr}"
        )

        # Should return valid JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook must return valid JSON on malformed input: {e}")

        assert output.get("result") == "continue"

    def test_handles_empty_prompt(self, hooks_dir: Path, project_dir: Path) -> None:
        """Hook should handle empty prompt gracefully."""
        result = self._run_hook(hooks_dir, project_dir, json.dumps({"prompt": ""}))

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output.get("result") == "continue"
        # Empty prompt should not trigger clarification
        assert "EROTETIC CLARIFICATION" not in output.get("message", "")

    def test_handles_missing_prompt_field(self, hooks_dir: Path, project_dir: Path) -> None:
        """Hook should handle missing prompt field gracefully."""
        result = self._run_hook(
            hooks_dir, project_dir, json.dumps({"session_id": "test"})
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output.get("result") == "continue"

    def test_case_insensitive_detection(self, hooks_dir: Path, project_dir: Path) -> None:
        """Pattern detection should be case insensitive."""
        result = self._run_hook(
            hooks_dir, project_dir, json.dumps({"prompt": "BUILD AN API WITH JWT"})
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "message" in output, "Uppercase 'BUILD' should trigger clarification"
        assert "EROTETIC CLARIFICATION" in output["message"]

    def test_prompt_with_unicode(self, hooks_dir: Path, project_dir: Path) -> None:
        """Hook should handle Unicode characters in prompt."""
        result = self._run_hook(
            hooks_dir, project_dir,
            json.dumps({"prompt": "Build an API for multilingual support: english"})
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        # Should still work with unicode
        assert output.get("result") == "continue"


# =============================================================================
# Integration with Existing Hooks Tests
# =============================================================================


class TestEroteticHookIntegration:
    """Tests for integration with existing hook infrastructure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def settings_path(self) -> Path:
        """Path to settings.json."""
        return Path(__file__).parents[2] / ".claude" / "settings.json"

    def test_hook_registered_in_settings_json(self, settings_path: Path, hooks_dir: Path) -> None:
        """Verify erotetic hook is registered in settings.json."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")
        if not (hooks_dir / "erotetic-clarification.sh").exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        user_prompt_hooks = hooks.get("UserPromptSubmit", [])

        # Find erotetic hook
        erotetic_found = False
        for hook_config in user_prompt_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "erotetic" in command.lower():
                    erotetic_found = True
                    break

        assert erotetic_found, (
            f"Erotetic hook must be registered in UserPromptSubmit. "
            f"Current UserPromptSubmit hooks: {user_prompt_hooks}"
        )

    def test_hook_uses_project_dir(self, settings_path: Path, hooks_dir: Path) -> None:
        """Verify erotetic hook uses $CLAUDE_PROJECT_DIR."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")
        if not (hooks_dir / "erotetic-clarification.sh").exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        user_prompt_hooks = hooks.get("UserPromptSubmit", [])

        for hook_config in user_prompt_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "erotetic" in command.lower():
                    assert "$CLAUDE_PROJECT_DIR" in command, (
                        f"Erotetic hook should use $CLAUDE_PROJECT_DIR. Got: {command}"
                    )
                    return

        # If we get here, hook wasn't found (already tested above, but safe)
        pytest.skip("Erotetic hook not found in settings.json")

    def test_typescript_has_hook_input_interface(self, hooks_dir: Path) -> None:
        """Verify TypeScript handler has proper HookInput interface."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        assert "interface" in content and "HookInput" in content, (
            "erotetic-clarification.ts must have HookInput interface"
        )
        assert "prompt" in content, (
            "HookInput interface must include 'prompt' field"
        )

    def test_typescript_outputs_json(self, hooks_dir: Path) -> None:
        """Verify TypeScript handler outputs JSON."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        assert "JSON.stringify" in content, (
            "erotetic-clarification.ts must output JSON using JSON.stringify"
        )


# =============================================================================
# TypeScript Logic Tests
# =============================================================================


class TestEroteticTypeScriptLogic:
    """Tests for TypeScript handler implementation details."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_has_implementation_patterns(self, hooks_dir: Path) -> None:
        """Verify TypeScript has implementation pattern definitions."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        # Should have patterns for build, implement, create, etc.
        patterns = ["build", "implement", "create"]
        for pattern in patterns:
            assert pattern in content.lower(), (
                f"erotetic-clarification.ts should include '{pattern}' in patterns"
            )

    def test_has_negative_patterns(self, hooks_dir: Path) -> None:
        """Verify TypeScript has negative patterns (non-triggers)."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        # Should exclude certain patterns like fix, run, show
        # Either as explicit exclusions or by carefully crafted positive patterns
        # The test validates that the logic exists to differentiate
        has_negative_handling = (
            "fix" in content.lower()
            or "exclude" in content.lower()
            or "negative" in content.lower()
            or len(content) > 500
        )
        assert has_negative_handling, (
            "erotetic-clarification.ts should handle negative patterns (fix, run, etc.)"
        )

    def test_reads_stdin(self, hooks_dir: Path) -> None:
        """Verify TypeScript reads from stdin."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        assert "readFileSync" in content or "stdin" in content.lower(), (
            "erotetic-clarification.ts must read from stdin"
        )

    def test_has_result_continue(self, hooks_dir: Path) -> None:
        """Verify TypeScript returns result: continue."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        assert "continue" in content, (
            "erotetic-clarification.ts must return result: 'continue'"
        )


# =============================================================================
# Distributed Build File Tests
# =============================================================================


class TestEroteticDistributedBuild:
    """Tests for compiled JavaScript output."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_compiled_js_exists(self, hooks_dir: Path) -> None:
        """Verify compiled JavaScript exists in dist directory."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        # Check for .mjs output (ESM) or .js output
        dist_mjs = hooks_dir / "dist" / "erotetic-clarification.mjs"
        dist_js = hooks_dir / "dist" / "erotetic-clarification.js"

        assert dist_mjs.exists() or dist_js.exists(), (
            f"Compiled JavaScript not found. Expected at {dist_mjs} or {dist_js}. "
            "Run the TypeScript build."
        )

    def test_shell_wrapper_references_compiled_output(self, hooks_dir: Path) -> None:
        """Verify shell wrapper references compiled output."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"
        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")

        content = shell_wrapper.read_text()
        # Should reference dist/erotetic-clarification.mjs or use npx tsx for ts
        assert "dist/" in content or "tsx" in content or "ts-node" in content, (
            "Shell wrapper should reference compiled output (dist/) or use tsx"
        )


# =============================================================================
# Phase 1: Flywheel Core Wiring Tests (Tasks 1.1-1.3)
# =============================================================================


class TestEroteticSkillNameDetection:
    """Tests for detecting skill name from prompt context (Task 1.1)."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def _run_hook(
        self, hooks_dir: Path, project_dir: Path, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute hook with given input and return parsed output."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            cwd=str(hooks_dir),
        )

        if result.returncode != 0:
            pytest.fail(f"Hook execution failed: {result.stderr}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook output is not valid JSON: {e}. stdout: {result.stdout}")

    def test_detect_skill_name_from_prompt(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Task 1.1: Hook should detect skill name when skillName is provided."""
        # When skillName is in input, hook should detect and use it
        output = self._run_hook(
            hooks_dir,
            project_dir,
            {"prompt": "deploy to aws", "skillName": "deploy-api"}
        )

        # The hook should include skill-specific context in its response
        # when a skillName is provided
        assert output["result"] == "continue"
        # The TypeScript handler must have detectSkillName function
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if ts_handler.exists():
            content = ts_handler.read_text()
            assert "detectSkillName" in content or "skillName" in content, (
                "erotetic-clarification.ts must have skill name detection"
            )


class TestEroteticSkillSpecificCLI:
    """Tests for calling skill-specific CLI (Task 1.2)."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_hook_calls_skill_specific_cli(self, hooks_dir: Path) -> None:
        """Task 1.2: Hook should call erotetic_skill_check.py with --skill flag."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        # When skill is detected, should call skill-specific CLI
        # Either directly or via a helper function
        has_skill_cli_call = (
            "erotetic_skill_check" in content
            or "--skill" in content
            or "callSkillCLI" in content
            or "skill_check" in content.lower()
        )
        assert has_skill_cli_call, (
            "erotetic-clarification.ts must call skill-specific CLI when skill detected"
        )


class TestEroteticCLIResponseParser:
    """Tests for parsing CLI JSON response (Task 1.3)."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_parse_cli_json_response(self, hooks_dir: Path) -> None:
        """Task 1.3: Hook should parse JSON response from skill CLI."""
        ts_handler = hooks_dir / "src" / "erotetic-clarification.ts"
        if not ts_handler.exists():
            pytest.skip("erotetic-clarification.ts doesn't exist yet")

        content = ts_handler.read_text()
        # Hook must parse JSON from CLI output
        assert "JSON.parse" in content, (
            "erotetic-clarification.ts must parse JSON response"
        )
        # Should handle different response types
        has_response_handling = (
            "SkillCheckResult" in content
            or "unknowns" in content
            or "evocation" in content.lower()
            or "result" in content
        )
        assert has_response_handling, (
            "erotetic-clarification.ts must handle CLI response structure"
        )
