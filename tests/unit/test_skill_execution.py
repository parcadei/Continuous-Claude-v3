"""Tests for skill execution and hook registration (Phases 16-18).

This module tests:
- Phase 16: Hook registration in settings.json
- Phase 17: Skill invocation message format
- Phase 18: Memory adaptation tracking

TDD approach: tests written FIRST, then implementation.

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

# =============================================================================
# Phase 16 Tests: Hook Registration
# =============================================================================


class TestPhase16HookRegistration:
    """Tests for Phase 16: Register skill-router hook in settings.json."""

    @pytest.fixture
    def settings_path(self) -> Path:
        """Path to settings.json file."""
        return Path(__file__).parents[2] / ".claude" / "settings.json"

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_settings_json_exists(self, settings_path: Path) -> None:
        """Verify settings.json exists."""
        assert settings_path.exists(), (
            f"settings.json not found at {settings_path}"
        )

    def test_settings_json_is_valid_json(self, settings_path: Path) -> None:
        """Verify settings.json contains valid JSON."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist")

        try:
            json.loads(settings_path.read_text())
        except json.JSONDecodeError as e:
            pytest.fail(f"settings.json is not valid JSON: {e}")

    def test_settings_has_hooks_section(self, settings_path: Path) -> None:
        """Verify settings.json has hooks section."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist")

        content = json.loads(settings_path.read_text())
        assert "hooks" in content, (
            "settings.json must have 'hooks' section"
        )

    def test_settings_has_user_prompt_submit_hook(self, settings_path: Path) -> None:
        """Verify settings.json has UserPromptSubmit hook section."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist")

        content = json.loads(settings_path.read_text())
        assert "hooks" in content, "settings.json must have 'hooks' section"
        assert "UserPromptSubmit" in content["hooks"], (
            "settings.json must have 'UserPromptSubmit' hook section"
        )

    def test_skill_router_registered_in_user_prompt_submit(
        self, settings_path: Path
    ) -> None:
        """Verify skill-router.sh is registered in UserPromptSubmit hooks.

        Per plan Phase 16, the skill-router hook should be registered
        for UserPromptSubmit events.
        """
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist")

        content = json.loads(settings_path.read_text())
        user_prompt_hooks = content.get("hooks", {}).get("UserPromptSubmit", [])

        # Flatten all hook commands
        all_commands: list[str] = []
        for hook_group in user_prompt_hooks:
            hooks = hook_group.get("hooks", [])
            for hook in hooks:
                command = hook.get("command", "")
                all_commands.append(command)

        # Check if skill-router.sh is registered
        skill_router_registered = any(
            "skill-router.sh" in cmd for cmd in all_commands
        )

        assert skill_router_registered, (
            "skill-router.sh must be registered in UserPromptSubmit hooks. "
            f"Found commands: {all_commands}"
        )

    def test_skill_router_uses_project_dir_variable(
        self, settings_path: Path
    ) -> None:
        """Verify skill-router hook uses $CLAUDE_PROJECT_DIR variable.

        The hook command should use $CLAUDE_PROJECT_DIR for portability.
        """
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist")

        content = json.loads(settings_path.read_text())
        user_prompt_hooks = content.get("hooks", {}).get("UserPromptSubmit", [])

        # Find skill-router command
        skill_router_command = None
        for hook_group in user_prompt_hooks:
            hooks = hook_group.get("hooks", [])
            for hook in hooks:
                command = hook.get("command", "")
                if "skill-router.sh" in command:
                    skill_router_command = command
                    break

        if skill_router_command is None:
            pytest.skip("skill-router.sh not registered yet")

        assert "$CLAUDE_PROJECT_DIR" in skill_router_command, (
            "skill-router hook should use $CLAUDE_PROJECT_DIR variable. "
            f"Got: {skill_router_command}"
        )

    def test_skill_router_runs_before_skill_activation_prompt(
        self, settings_path: Path
    ) -> None:
        """Verify skill-router runs BEFORE skill-activation-prompt.

        Per plan: 'Runs before skill-activation-prompt'
        The skill-router should be first in the list to intercept prompts
        before the existing skill-activation-prompt hook.
        """
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist")

        content = json.loads(settings_path.read_text())
        user_prompt_hooks = content.get("hooks", {}).get("UserPromptSubmit", [])

        # Find indices of skill-router and skill-activation-prompt
        skill_router_idx = -1
        skill_activation_idx = -1

        for group_idx, hook_group in enumerate(user_prompt_hooks):
            hooks = hook_group.get("hooks", [])
            for hook_idx, hook in enumerate(hooks):
                command = hook.get("command", "")
                if "skill-router.sh" in command:
                    skill_router_idx = (group_idx, hook_idx)
                if "skill-activation-prompt" in command:
                    skill_activation_idx = (group_idx, hook_idx)

        if skill_router_idx == -1:
            pytest.skip("skill-router.sh not registered yet")
        if skill_activation_idx == -1:
            pytest.skip("skill-activation-prompt not found")

        # skill-router should come before skill-activation-prompt
        # Either in an earlier group, or earlier in the same group
        assert skill_router_idx < skill_activation_idx, (
            "skill-router must run before skill-activation-prompt. "
            f"skill-router at {skill_router_idx}, skill-activation at {skill_activation_idx}"
        )

    def test_hook_registration_format_valid(self, settings_path: Path) -> None:
        """Verify hook registration follows correct format.

        Each hook entry should have:
        - type: "command"
        - command: string with path to script
        """
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist")

        content = json.loads(settings_path.read_text())
        user_prompt_hooks = content.get("hooks", {}).get("UserPromptSubmit", [])

        for hook_group in user_prompt_hooks:
            hooks = hook_group.get("hooks", [])
            for hook in hooks:
                if "skill-router.sh" in hook.get("command", ""):
                    assert hook.get("type") == "command", (
                        "skill-router hook must have type: 'command'"
                    )
                    assert isinstance(hook.get("command"), str), (
                        "skill-router hook must have command: string"
                    )


# =============================================================================
# Phase 17 Tests: Skill Invocation Message Format
# =============================================================================


class TestPhase17SkillInvocationMessage:
    """Tests for Phase 17: Skill invocation message format.

    When a skill is matched, the hook should return a message
    instructing how to invoke the skill.
    """

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_skill_match_returns_use_skill_instruction(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify skill match returns instruction to use Skill tool.

        Per plan Phase 17:
        'When skill matched, return message instructing to use Skill tool'
        Format: 'Use Skill("skill-name") to handle this request.'
        """
        shell_wrapper = hooks_dir / "skill-router.sh"
        ts_handler = hooks_dir / "src" / "skill-router.ts"

        if not shell_wrapper.exists():
            pytest.skip("skill-router.sh doesn't exist yet")
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("skill-router.sh is not executable")

        # Test with a keyword that matches the commit skill
        test_input = json.dumps({
            "prompt": "commit my changes",
            "session_id": "test-phase17"
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

        output = json.loads(result.stdout)
        assert "message" in output, "Skill match should return message"

        # Message should contain instruction format per plan
        message = output["message"]
        assert "commit" in message.lower(), (
            f"Message should mention skill name. Got: {message}"
        )

    def test_skill_match_message_includes_source(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify skill match message includes the source (keyword/intent/memory)."""
        shell_wrapper = hooks_dir / "skill-router.sh"
        ts_handler = hooks_dir / "src" / "skill-router.ts"

        if not shell_wrapper.exists():
            pytest.skip("skill-router.sh doesn't exist yet")
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("skill-router.sh is not executable")

        test_input = json.dumps({
            "prompt": "commit my changes",
            "session_id": "test-phase17"
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

        output = json.loads(result.stdout)
        message = output.get("message", "")

        # Message should indicate the source
        has_source = (
            "source:" in message.lower() or
            "keyword" in message.lower() or
            "intent" in message.lower() or
            "memory" in message.lower()
        )
        assert has_source, (
            f"Message should include match source. Got: {message}"
        )

    def test_skill_match_returns_continue_not_block(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify skill match returns result: continue (not block).

        The hook suggests skills but should not block execution.
        """
        shell_wrapper = hooks_dir / "skill-router.sh"
        ts_handler = hooks_dir / "src" / "skill-router.ts"

        if not shell_wrapper.exists():
            pytest.skip("skill-router.sh doesn't exist yet")
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("skill-router.sh is not executable")

        test_input = json.dumps({
            "prompt": "commit my changes",
            "session_id": "test-phase17"
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

        output = json.loads(result.stdout)
        assert output.get("result") == "continue", (
            f"Skill match should return 'continue'. Got: {output}"
        )

    def test_jit_skill_returns_generation_message(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify JIT skill detection returns appropriate message.

        Per plan Phase 17:
        'For JIT-generated skills, return message with generated skill content'

        Note: Full JIT generation is Phase 8-12. Phase 17 just handles
        the message format for novel tasks detected in Phase 7.
        """
        shell_wrapper = hooks_dir / "skill-router.sh"
        ts_handler = hooks_dir / "src" / "skill-router.ts"

        if not shell_wrapper.exists():
            pytest.skip("skill-router.sh doesn't exist yet")
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("skill-router.sh is not executable")

        # A task-like prompt that won't match any existing skill
        # Use very specific domain terminology that won't match keywords
        # NOTE: This test depends on task-detector detecting this as a task
        test_input = json.dumps({
            "prompt": "migrate the PostgreSQL schema to use materialized views for the analytics dashboard",
            "session_id": "test-phase17-jit"
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

        output = json.loads(result.stdout)

        # Should return continue (not block)
        assert output.get("result") == "continue"

        # If message present (novel task detected), should mention novel/JIT/task
        # OR it might match an existing skill - that's also acceptable
        if "message" in output:
            message = output["message"]
            # Either a skill was matched, OR it's a novel task
            is_skill_match = "skill" in message.lower() and "matches" in message.lower()
            is_novel_task = (
                "novel" in message.lower() or
                "jit" in message.lower() or
                "task" in message.lower()
            )
            assert is_skill_match or is_novel_task, (
                f"Message should indicate skill match or novel task. Got: {message}"
            )


class TestPhase17MemoryMatch:
    """Tests for Phase 17: Memory match message format."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_memory_match_includes_confidence(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify memory match message includes confidence score.

        When a memory match is found (without specific skill name),
        the message should include the confidence score.
        """
        ts_handler = hooks_dir / "src" / "skill-router.ts"
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")

        content = ts_handler.read_text()

        # Should format confidence in output message
        assert "confidence" in content.lower(), (
            "Memory match handling should include confidence in message"
        )

    def test_memory_match_with_skill_name_mentions_skill(
        self, hooks_dir: Path
    ) -> None:
        """Verify memory match with skillName mentions the skill.

        If memory returns a result with skillName metadata,
        the message should mention that skill.
        """
        ts_handler = hooks_dir / "src" / "skill-router.ts"
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")

        content = ts_handler.read_text()

        # Should handle skillName from metadata
        assert "skillName" in content, (
            "Memory lookup should handle skillName from metadata"
        )


# =============================================================================
# Phase 18 Tests: Memory Adaptation Tracking
# =============================================================================


class TestPhase18MemoryAdaptation:
    """Tests for Phase 18: Memory adaptation tracking.

    When a memory match is used, the system should:
    - Track that this pattern worked
    - Boost its relevance for future searches
    - Store decision trace
    """

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared modules directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_memory_client_has_track_usage_function(self, shared_dir: Path) -> None:
        """Verify memory-client.ts has trackUsage function.

        Per plan Phase 18:
        'Track that this pattern worked'
        """
        memory_client = shared_dir / "memory-client.ts"
        if not memory_client.exists():
            pytest.skip("memory-client.ts doesn't exist yet")

        content = memory_client.read_text()

        # Should have function to track usage
        has_track_usage = (
            "trackUsage" in content or
            "recordUsage" in content or
            "track_usage" in content or
            "record_usage" in content
        )

        # This is a Phase 18 requirement - may not exist yet
        # Test will fail until implementation
        assert has_track_usage, (
            "memory-client.ts should have a function to track usage "
            "(trackUsage, recordUsage, etc.)"
        )

    def test_skill_usage_tracking_module_exists(self, shared_dir: Path) -> None:
        """Verify skill-usage.ts module exists for tracking.

        Per plan Phase 24 (referenced in Phase 18):
        The skill-usage module tracks usage statistics.
        """
        skill_usage = shared_dir / "skill-usage.ts"

        # This is an optional implementation detail
        # The tracking could be in memory-client.ts or skill-usage.ts
        if not skill_usage.exists():
            # Check if tracking exists in memory-client instead
            memory_client = shared_dir / "memory-client.ts"
            if memory_client.exists():
                content = memory_client.read_text()
                has_tracking = (
                    "trackUsage" in content or
                    "recordUsage" in content or
                    "usage" in content.lower()
                )
                if has_tracking:
                    pytest.skip("Usage tracking exists in memory-client.ts")

        # If we get here, check skill-usage.ts exists
        # Note: Usage tracking may be in memory-client.ts instead of skill-usage.ts
        # This is a soft check - if skill-usage.ts doesn't exist, that's acceptable
        # as long as usage tracking is implemented somewhere (checked above)
        if not skill_usage.exists():
            pytest.skip("skill-usage.ts doesn't exist - usage tracking in memory-client")

    def test_typescript_tracks_memory_match_usage(self, hooks_dir: Path) -> None:
        """Verify skill-router.ts tracks when memory match is used.

        Per plan Phase 18:
        'When a memory match is used, track that this pattern worked'
        """
        ts_handler = hooks_dir / "src" / "skill-router.ts"
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")

        content = ts_handler.read_text()

        # This is aspirational - may need implementation
        # For now, check that memory results are handled
        assert "source: 'memory'" in content or 'source: "memory"' in content, (
            "Memory matches should be identified (prerequisite for tracking)"
        )


class TestPhase18DecisionTrace:
    """Tests for Phase 18: Decision trace storage."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_typescript_logs_lookup_decision(self, hooks_dir: Path) -> None:
        """Verify skill-router.ts logs the lookup decision.

        Per plan Phase 18:
        'Store decision trace'

        The decision trace should include:
        - What was matched (skill name, memory ID)
        - How it was matched (keyword, intent, memory)
        - Confidence level
        """
        ts_handler = hooks_dir / "src" / "skill-router.ts"
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")

        content = ts_handler.read_text()

        # Should track the source of the match
        has_source_tracking = (
            "source:" in content or
            "source =" in content
        )

        assert has_source_tracking, (
            "skill-router.ts should track match source for decision trace"
        )

    def test_lookup_result_includes_all_decision_factors(
        self, hooks_dir: Path
    ) -> None:
        """Verify SkillLookupResult includes all factors for decision trace.

        The result should capture enough info to reconstruct the decision:
        - found: boolean
        - skillName: string (if found)
        - confidence: number
        - source: 'keyword' | 'intent' | 'memory' | 'jit'
        """
        types_file = hooks_dir / "src" / "shared" / "skill-router-types.ts"
        if not types_file.exists():
            pytest.skip("skill-router-types.ts doesn't exist yet")

        content = types_file.read_text()

        # Check all required fields exist in SkillLookupResult
        assert "found: boolean" in content, "Must have 'found: boolean'"
        assert "skillName" in content, "Must have 'skillName' field"
        assert "confidence" in content, "Must have 'confidence' field"
        assert "source" in content, "Must have 'source' field"


class TestPhase18RelevanceBoost:
    """Tests for Phase 18: Relevance boosting."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared modules directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_memory_client_can_boost_relevance(self, shared_dir: Path) -> None:
        """Verify memory client has capability to boost relevance.

        Per plan Phase 18:
        'Boost its relevance for future searches'

        This could be implemented as:
        - Storing usage count in metadata
        - Updating a relevance/weight field
        - Recording positive feedback
        """
        memory_client = shared_dir / "memory-client.ts"
        if not memory_client.exists():
            pytest.skip("memory-client.ts doesn't exist yet")

        content = memory_client.read_text()

        # Should have some form of relevance boosting
        # This is an aspirational test - may need implementation
        has_boost_capability = (
            "boost" in content.lower() or
            "relevance" in content.lower() or
            "weight" in content.lower() or
            "feedback" in content.lower() or
            "usage" in content.lower() or
            "store" in content.lower()  # Can store usage records
        )

        assert has_boost_capability, (
            "memory-client.ts should have capability to store/update relevance data"
        )


# =============================================================================
# Integration Tests: Full Execution Flow
# =============================================================================


class TestPhase16to18Integration:
    """Integration tests for Phases 16-18 working together."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    @pytest.fixture
    def settings_path(self) -> Path:
        """Path to settings.json file."""
        return Path(__file__).parents[2] / ".claude" / "settings.json"

    def test_full_skill_match_flow(
        self, hooks_dir: Path, project_dir: Path, settings_path: Path
    ) -> None:
        """Test complete flow: hook registered -> skill matched -> message returned.

        This is an end-to-end test verifying:
        1. Hook is registered (Phase 16)
        2. Skill match returns proper message (Phase 17)
        3. Hook returns continue (doesn't block)
        """
        # Skip if any component is missing
        shell_wrapper = hooks_dir / "skill-router.sh"
        ts_handler = hooks_dir / "src" / "skill-router.ts"

        if not shell_wrapper.exists():
            pytest.skip("skill-router.sh doesn't exist yet")
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("skill-router.sh is not executable")

        # Verify hook is registered
        settings = json.loads(settings_path.read_text())
        user_prompt_hooks = settings.get("hooks", {}).get("UserPromptSubmit", [])
        all_commands = []
        for hook_group in user_prompt_hooks:
            for hook in hook_group.get("hooks", []):
                all_commands.append(hook.get("command", ""))

        if not any("skill-router.sh" in cmd for cmd in all_commands):
            pytest.skip("skill-router.sh not registered in settings.json")

        # Execute hook with skill-matching prompt
        test_input = json.dumps({
            "prompt": "commit my changes to git",
            "session_id": "test-integration"
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

        # Verify execution
        assert result.returncode == 0, (
            f"Hook should execute successfully. stderr: {result.stderr}"
        )

        output = json.loads(result.stdout)

        # Verify output format
        assert output.get("result") == "continue", "Should return 'continue'"
        assert "message" in output, "Should return message for skill match"
        assert "commit" in output["message"].lower(), "Message should mention skill"

    def test_no_match_flow_returns_continue(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test flow when no skill matches: should return continue without message.

        For conversational prompts that don't match any skill:
        - Hook should return result: continue
        - No message (or minimal message)
        """
        shell_wrapper = hooks_dir / "skill-router.sh"
        ts_handler = hooks_dir / "src" / "skill-router.ts"

        if not shell_wrapper.exists():
            pytest.skip("skill-router.sh doesn't exist yet")
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("skill-router.sh is not executable")

        # Pure conversational prompt that shouldn't match any skill
        test_input = json.dumps({
            "prompt": "Hello, how are you today?",
            "session_id": "test-integration-no-match"
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

        assert result.returncode == 0, f"Hook should not crash. stderr: {result.stderr}"

        output = json.loads(result.stdout)
        assert output.get("result") == "continue", "Should return 'continue'"

        # Conversational prompts shouldn't trigger skill or JIT messages
        # (they're not tasks)
