"""Tests for settings.json hook configuration (Phase 12 of pattern-aware hooks).

These tests verify that the settings.json correctly:
1. Registers the new unified routers
2. Removes or deprecates old swarm-specific hooks
3. Configures hook matchers correctly
4. Uses correct hook paths with $CLAUDE_PROJECT_DIR
5. Maintains backward compatibility during transition

Plan reference: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 12)

Tests are designed to FAIL initially (TDD approach) until Phase 12 is implemented.

Settings location: .claude/settings.json
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest


class TestSettingsJsonStructure:
    """Tests for settings.json file structure."""

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
                settings = json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"settings.json is not valid JSON: {e}")

        # Basic structure check
        assert isinstance(settings, dict), "settings.json should be a dict"

    def test_settings_has_hooks_section(self, settings_path: Path) -> None:
        """Verify settings.json has hooks section."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        assert "hooks" in settings, "settings.json must have 'hooks' section"
        assert isinstance(settings["hooks"], dict), "hooks section must be a dict"


class TestUnifiedRoutersRegistered:
    """Tests for unified router registration in settings.json."""

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

    def test_subagent_start_router_registered(self, settings: dict) -> None:
        """Unified subagent-start router is registered."""
        hooks = settings.get("hooks", {})
        subagent_start_hooks = hooks.get("SubagentStart", [])

        # Find unified router (NOT swarm-specific)
        unified_router_found = False
        for hook_config in subagent_start_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                # Look for unified router (subagent-start.sh without -swarm suffix)
                if "subagent-start.sh" in command and "-swarm" not in command:
                    unified_router_found = True
                    break

        assert unified_router_found, (
            "Unified SubagentStart router (subagent-start.sh) must be registered. "
            f"Current SubagentStart hooks: {subagent_start_hooks}"
        )

    def test_subagent_stop_router_registered(self, settings: dict) -> None:
        """Unified subagent-stop router is registered."""
        hooks = settings.get("hooks", {})
        subagent_stop_hooks = hooks.get("SubagentStop", [])

        # Find unified router (NOT swarm-specific)
        unified_router_found = False
        for hook_config in subagent_stop_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                # Look for unified router (subagent-stop.sh without -swarm suffix)
                if "subagent-stop.sh" in command and "-swarm" not in command:
                    unified_router_found = True
                    break

        assert unified_router_found, (
            "Unified SubagentStop router (subagent-stop.sh) must be registered. "
            f"Current SubagentStop hooks: {subagent_stop_hooks}"
        )

    def test_pre_tool_use_router_registered(self, settings: dict) -> None:
        """Unified pre-tool-use router is registered."""
        hooks = settings.get("hooks", {})
        pre_tool_use_hooks = hooks.get("PreToolUse", [])

        # Find unified router (NOT broadcast-specific)
        unified_router_found = False
        for hook_config in pre_tool_use_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                # Look for unified router (pre-tool-use.sh without -broadcast suffix)
                if "pre-tool-use.sh" in command and "-broadcast" not in command:
                    unified_router_found = True
                    break

        assert unified_router_found, (
            "Unified PreToolUse router (pre-tool-use.sh) must be registered. "
            f"Current PreToolUse hooks: {pre_tool_use_hooks}"
        )

    def test_stop_coordinator_router_registered(self, settings: dict) -> None:
        """Unified stop-coordinator router is registered."""
        hooks = settings.get("hooks", {})
        stop_hooks = hooks.get("Stop", [])

        # Find unified router (NOT swarm-specific)
        unified_router_found = False
        for hook_config in stop_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                # Look for unified router (stop-coordinator.sh without -swarm suffix)
                if "stop-coordinator.sh" in command and "-swarm" not in command:
                    unified_router_found = True
                    break

        assert unified_router_found, (
            "Unified Stop coordinator router (stop-coordinator.sh) must be registered. "
            f"Current Stop hooks: {stop_hooks}"
        )


class TestOldSwarmHooksDeprecated:
    """Tests for old swarm-specific hooks being removed or deprecated."""

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

    def test_subagent_start_swarm_deprecated(self, settings: dict) -> None:
        """Old subagent-start-swarm.sh should be removed or replaced."""
        hooks = settings.get("hooks", {})
        subagent_start_hooks = hooks.get("SubagentStart", [])

        # Check if old swarm-specific hook is still present
        swarm_specific_found = False
        unified_found = False

        for hook_config in subagent_start_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "subagent-start-swarm" in command:
                    swarm_specific_found = True
                if "subagent-start.sh" in command and "-swarm" not in command:
                    unified_found = True

        # Either unified is present (replacing old), or both are gone
        if swarm_specific_found:
            assert unified_found, (
                "If old subagent-start-swarm.sh is present, unified router must also be registered. "
                "Expected to migrate to unified router during Phase 12."
            )

    def test_subagent_stop_swarm_deprecated(self, settings: dict) -> None:
        """Old subagent-stop-swarm.sh should be removed or replaced."""
        hooks = settings.get("hooks", {})
        subagent_stop_hooks = hooks.get("SubagentStop", [])

        swarm_specific_found = False
        unified_found = False

        for hook_config in subagent_stop_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "subagent-stop-swarm" in command:
                    swarm_specific_found = True
                if "subagent-stop.sh" in command and "-swarm" not in command:
                    unified_found = True

        if swarm_specific_found:
            assert unified_found, (
                "If old subagent-stop-swarm.sh is present, unified router must also be registered. "
                "Expected to migrate to unified router during Phase 12."
            )

    def test_pre_tool_use_broadcast_deprecated(self, settings: dict) -> None:
        """Old pre-tool-use-broadcast.sh should be removed or replaced."""
        hooks = settings.get("hooks", {})
        pre_tool_use_hooks = hooks.get("PreToolUse", [])

        broadcast_specific_found = False
        unified_found = False

        for hook_config in pre_tool_use_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "pre-tool-use-broadcast" in command:
                    broadcast_specific_found = True
                if "pre-tool-use.sh" in command and "-broadcast" not in command:
                    unified_found = True

        if broadcast_specific_found:
            assert unified_found, (
                "If old pre-tool-use-broadcast.sh is present, unified router must also be registered. "
                "Expected to migrate to unified router during Phase 12."
            )

    def test_stop_swarm_coordinator_deprecated(self, settings: dict) -> None:
        """Old stop-swarm-coordinator.sh should be removed or replaced."""
        hooks = settings.get("hooks", {})
        stop_hooks = hooks.get("Stop", [])

        swarm_specific_found = False
        unified_found = False

        for hook_config in stop_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "stop-swarm-coordinator" in command:
                    swarm_specific_found = True
                if "stop-coordinator.sh" in command and "-swarm" not in command:
                    unified_found = True

        if swarm_specific_found:
            assert unified_found, (
                "If old stop-swarm-coordinator.sh is present, unified router must also be registered. "
                "Expected to migrate to unified router during Phase 12."
            )


class TestHookPathsCorrect:
    """Tests for correct hook path configuration."""

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

    def test_uses_claude_project_dir(self, settings: dict) -> None:
        """Verify project-local hooks use $CLAUDE_PROJECT_DIR."""
        hooks = settings.get("hooks", {})

        # Collect all commands
        all_commands = []
        for event_type, hook_configs in hooks.items():
            if isinstance(hook_configs, list):
                for hook_config in hook_configs:
                    hook_list = hook_config.get("hooks", [])
                    for hook in hook_list:
                        command = hook.get("command", "")
                        all_commands.append((event_type, command))

        # Check project-local hooks - use .sh suffix to avoid matching global hooks
        # e.g., "subagent-stop.sh" is project-local, but "subagent-stop-continuity.sh" is global
        project_local_hooks = [
            "subagent-start.sh",
            "subagent-stop.sh",
            "pre-tool-use.sh",
            "stop-coordinator.sh",
            "post-task-complete.sh",
            "session-end-cleanup-swarms.sh",
        ]

        for event_type, command in all_commands:
            for hook_name in project_local_hooks:
                # Use exact match at end of path to avoid substring false positives
                if command.endswith(hook_name):
                    assert "$CLAUDE_PROJECT_DIR" in command, (
                        f"Project-local hook '{hook_name}' should use $CLAUDE_PROJECT_DIR. "
                        f"Got: {command}"
                    )

    def test_global_hooks_use_home(self, settings: dict) -> None:
        """Verify global hooks use $HOME."""
        hooks = settings.get("hooks", {})

        global_hooks = [
            "braintrust-tracing",
            "session-start-continuity",
            "skill-activation-prompt",
            "pre-compact-continuity",
            "session-end-cleanup",
            "session-outcome",
            "handoff-index",
            "post-tool-use-tracker",
            "typescript-preflight",
            "subagent-stop-continuity",
        ]

        for event_type, hook_configs in hooks.items():
            if isinstance(hook_configs, list):
                for hook_config in hook_configs:
                    hook_list = hook_config.get("hooks", [])
                    for hook in hook_list:
                        command = hook.get("command", "")
                        for hook_name in global_hooks:
                            if hook_name in command and "$CLAUDE_PROJECT_DIR" not in command:
                                # Should use $HOME for global hooks
                                assert "$HOME" in command or "~" in command, (
                                    f"Global hook '{hook_name}' should use $HOME. "
                                    f"Got: {command}"
                                )


class TestMatchersConfigured:
    """Tests for hook matcher configuration."""

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

    def test_post_tool_use_has_matchers(self, settings: dict) -> None:
        """Verify PostToolUse hooks have appropriate matchers."""
        hooks = settings.get("hooks", {})
        post_tool_use_hooks = hooks.get("PostToolUse", [])

        # PostToolUse should have different matchers for different tools
        matchers_found = set()
        for hook_config in post_tool_use_hooks:
            matcher = hook_config.get("matcher", "")
            if matcher:
                matchers_found.add(matcher)

        # Should have at least Task matcher
        assert any("Task" in m for m in matchers_found), (
            f"PostToolUse should have Task matcher. Found: {matchers_found}"
        )

    def test_session_start_has_matcher(self, settings: dict) -> None:
        """Verify SessionStart continuity hook has resume/compact matcher."""
        hooks = settings.get("hooks", {})
        session_start_hooks = hooks.get("SessionStart", [])

        resume_matcher_found = False
        for hook_config in session_start_hooks:
            matcher = hook_config.get("matcher", "")
            hooks_list = hook_config.get("hooks", [])
            for hook in hooks_list:
                command = hook.get("command", "")
                if "session-start-continuity" in command:
                    # This hook should have resume/compact matcher
                    if "resume" in matcher or "compact" in matcher:
                        resume_matcher_found = True

        assert resume_matcher_found, (
            "SessionStart continuity hook should have resume|compact matcher. "
            f"SessionStart hooks: {session_start_hooks}"
        )


class TestHookTypeCorrect:
    """Tests for hook type configuration."""

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

    def test_all_hooks_have_type_command(self, settings: dict) -> None:
        """Verify all hooks have type: command."""
        hooks = settings.get("hooks", {})

        for event_type, hook_configs in hooks.items():
            if isinstance(hook_configs, list):
                for hook_config in hook_configs:
                    hook_list = hook_config.get("hooks", [])
                    for hook in hook_list:
                        hook_type = hook.get("type", "")
                        assert hook_type == "command", (
                            f"Hook must have type: command. "
                            f"Event: {event_type}, Hook: {hook}"
                        )


class TestHookEventsCovered:
    """Tests for all required hook events being configured."""

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

    def test_subagent_start_event_exists(self, settings: dict) -> None:
        """Verify SubagentStart event is configured."""
        hooks = settings.get("hooks", {})
        assert "SubagentStart" in hooks, "SubagentStart event must be configured"
        assert len(hooks["SubagentStart"]) > 0, "SubagentStart must have at least one hook"

    def test_subagent_stop_event_exists(self, settings: dict) -> None:
        """Verify SubagentStop event is configured."""
        hooks = settings.get("hooks", {})
        assert "SubagentStop" in hooks, "SubagentStop event must be configured"
        assert len(hooks["SubagentStop"]) > 0, "SubagentStop must have at least one hook"

    def test_pre_tool_use_event_exists(self, settings: dict) -> None:
        """Verify PreToolUse event is configured."""
        hooks = settings.get("hooks", {})
        assert "PreToolUse" in hooks, "PreToolUse event must be configured"
        assert len(hooks["PreToolUse"]) > 0, "PreToolUse must have at least one hook"

    def test_stop_event_exists(self, settings: dict) -> None:
        """Verify Stop event is configured."""
        hooks = settings.get("hooks", {})
        assert "Stop" in hooks, "Stop event must be configured"
        assert len(hooks["Stop"]) > 0, "Stop must have at least one hook"

    def test_post_tool_use_event_exists(self, settings: dict) -> None:
        """Verify PostToolUse event is configured."""
        hooks = settings.get("hooks", {})
        assert "PostToolUse" in hooks, "PostToolUse event must be configured"
        assert len(hooks["PostToolUse"]) > 0, "PostToolUse must have at least one hook"

    def test_session_start_event_exists(self, settings: dict) -> None:
        """Verify SessionStart event is configured."""
        hooks = settings.get("hooks", {})
        assert "SessionStart" in hooks, "SessionStart event must be configured"
        assert len(hooks["SessionStart"]) > 0, "SessionStart must have at least one hook"

    def test_session_end_event_exists(self, settings: dict) -> None:
        """Verify SessionEnd event is configured."""
        hooks = settings.get("hooks", {})
        assert "SessionEnd" in hooks, "SessionEnd event must be configured"
        assert len(hooks["SessionEnd"]) > 0, "SessionEnd must have at least one hook"


class TestUnifiedRouterFiles:
    """Tests for unified router file existence."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_subagent_start_router_files(self, hooks_dir: Path) -> None:
        """Verify subagent-start unified router files exist."""
        ts_router = hooks_dir / "src" / "subagent-start.ts"
        sh_wrapper = hooks_dir / "subagent-start.sh"

        assert ts_router.exists(), (
            f"TypeScript router not found: {ts_router}. "
            "Create .claude/hooks/src/subagent-start.ts"
        )
        assert sh_wrapper.exists(), (
            f"Shell wrapper not found: {sh_wrapper}. "
            "Create .claude/hooks/subagent-start.sh"
        )

    def test_subagent_stop_router_files(self, hooks_dir: Path) -> None:
        """Verify subagent-stop unified router files exist."""
        ts_router = hooks_dir / "src" / "subagent-stop.ts"
        sh_wrapper = hooks_dir / "subagent-stop.sh"

        assert ts_router.exists(), (
            f"TypeScript router not found: {ts_router}. "
            "Create .claude/hooks/src/subagent-stop.ts"
        )
        assert sh_wrapper.exists(), (
            f"Shell wrapper not found: {sh_wrapper}. "
            "Create .claude/hooks/subagent-stop.sh"
        )

    def test_pre_tool_use_router_files(self, hooks_dir: Path) -> None:
        """Verify pre-tool-use unified router files exist."""
        ts_router = hooks_dir / "src" / "pre-tool-use.ts"
        sh_wrapper = hooks_dir / "pre-tool-use.sh"

        assert ts_router.exists(), (
            f"TypeScript router not found: {ts_router}. "
            "Create .claude/hooks/src/pre-tool-use.ts"
        )
        assert sh_wrapper.exists(), (
            f"Shell wrapper not found: {sh_wrapper}. "
            "Create .claude/hooks/pre-tool-use.sh"
        )

    def test_stop_coordinator_router_files(self, hooks_dir: Path) -> None:
        """Verify stop-coordinator unified router files exist."""
        ts_router = hooks_dir / "src" / "stop-coordinator.ts"
        sh_wrapper = hooks_dir / "stop-coordinator.sh"

        assert ts_router.exists(), (
            f"TypeScript router not found: {ts_router}. "
            "Create .claude/hooks/src/stop-coordinator.ts"
        )
        assert sh_wrapper.exists(), (
            f"Shell wrapper not found: {sh_wrapper}. "
            "Create .claude/hooks/stop-coordinator.sh"
        )


class TestSharedModulesExist:
    """Tests for shared module files."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_pattern_router_module(self, hooks_dir: Path) -> None:
        """Verify shared/pattern-router.ts exists (Phase 1 dependency)."""
        pattern_router = hooks_dir / "src" / "shared" / "pattern-router.ts"

        assert pattern_router.exists(), (
            f"Pattern router module not found: {pattern_router}. "
            "Create .claude/hooks/src/shared/pattern-router.ts (Phase 1)"
        )

    def test_db_utils_module(self, hooks_dir: Path) -> None:
        """Verify shared/db-utils.ts exists (Phase 2 dependency)."""
        db_utils = hooks_dir / "src" / "shared" / "db-utils.ts"

        assert db_utils.exists(), (
            f"DB utils module not found: {db_utils}. "
            "Create .claude/hooks/src/shared/db-utils.ts (Phase 2)"
        )


class TestPatternHandlersExist:
    """Tests for pattern handler files."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_swarm_pattern_handler(self, hooks_dir: Path) -> None:
        """Verify patterns/swarm.ts exists (Phase 3 dependency)."""
        swarm_pattern = hooks_dir / "src" / "patterns" / "swarm.ts"

        assert swarm_pattern.exists(), (
            f"Swarm pattern handler not found: {swarm_pattern}. "
            "Create .claude/hooks/src/patterns/swarm.ts (Phase 3)"
        )

    def test_jury_pattern_handler(self, hooks_dir: Path) -> None:
        """Verify patterns/jury.ts exists (Phase 15 dependency)."""
        jury_pattern = hooks_dir / "src" / "patterns" / "jury.ts"

        # This is a future phase, so skip if not implemented yet
        if not jury_pattern.exists():
            pytest.skip("Jury pattern handler not implemented yet (Phase 15)")

        assert jury_pattern.exists(), (
            f"Jury pattern handler not found: {jury_pattern}. "
            "Create .claude/hooks/src/patterns/jury.ts (Phase 15)"
        )

    def test_pipeline_pattern_handler(self, hooks_dir: Path) -> None:
        """Verify patterns/pipeline.ts exists (Phase 19 dependency)."""
        pipeline_pattern = hooks_dir / "src" / "patterns" / "pipeline.ts"

        # This is a future phase, so skip if not implemented yet
        if not pipeline_pattern.exists():
            pytest.skip("Pipeline pattern handler not implemented yet (Phase 19)")

        assert pipeline_pattern.exists(), (
            f"Pipeline pattern handler not found: {pipeline_pattern}. "
            "Create .claude/hooks/src/patterns/pipeline.ts (Phase 19)"
        )
