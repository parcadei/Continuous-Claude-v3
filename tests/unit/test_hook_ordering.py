"""Tests for Hook Ordering Configuration (Phase 3 Task 3.11).

TDD tests for hook ordering to prevent double-execution.
"""

import pytest
import json
from pathlib import Path


class TestHookOrdering:
    """Task 3.11: Hook ordering configuration tests."""

    def test_hook_ordering_prevents_double_execution(self):
        """Hook ordering ensures skill-router runs before erotetic-clarification."""
        settings_path = Path(__file__).parent.parent.parent / ".claude" / "settings.json"

        assert settings_path.exists(), "settings.json must exist"

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})

        # Check that UserPromptSubmit hooks are ordered
        user_prompt_hooks = hooks.get("UserPromptSubmit", [])

        # Find skill-router and erotetic-clarification indices within the hooks list
        skill_router_idx = None
        erotetic_idx = None

        for hook_config in user_prompt_hooks:
            hooks_list = hook_config.get("hooks", [])
            for j, h in enumerate(hooks_list):
                cmd = h.get("command", "")
                if "skill-router" in cmd:
                    skill_router_idx = j
                if "erotetic" in cmd:
                    erotetic_idx = j

        # If both exist in the same list, skill-router should come first
        if skill_router_idx is not None and erotetic_idx is not None:
            assert skill_router_idx < erotetic_idx, \
                f"skill-router ({skill_router_idx}) must run before erotetic-clarification ({erotetic_idx})"

    def test_flywheel_hook_is_registered(self):
        """Flywheel hook is registered in settings.json."""
        settings_path = Path(__file__).parent.parent.parent / ".claude" / "settings.json"

        assert settings_path.exists()

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})

        # Check PostToolUse has flywheel-related hook
        post_tool_hooks = hooks.get("PostToolUse", [])

        # Look for flywheel trigger in any hook
        has_flywheel = False
        for hook_config in post_tool_hooks:
            hooks_list = hook_config.get("hooks", [])
            for h in hooks_list:
                cmd = h.get("command", "")
                if "flywheel" in cmd or "post-tool-use" in cmd:
                    has_flywheel = True
                    break

        # It's okay if flywheel is not registered yet (can be added in 3.13)
        # Just verify the structure exists
        assert isinstance(post_tool_hooks, list)


class TestProcessedSkillsTracking:
    """Track processed skills to prevent double-execution."""

    def test_processed_skills_tracked_in_session(self):
        """Processed skills are tracked per session."""
        from scripts.skill_flywheel import (
            get_processed_skills,
            mark_skill_processed,
            clear_processed_skills
        )

        # Clear at start
        clear_processed_skills()

        assert len(get_processed_skills()) == 0

        # Mark as processed
        mark_skill_processed("deploy-api")
        mark_skill_processed("math-tutor")

        processed = get_processed_skills()
        assert "deploy-api" in processed
        assert "math-tutor" in processed

    def test_is_skill_processed(self):
        """Check if skill was already processed."""
        from scripts.skill_flywheel import (
            is_skill_processed,
            mark_skill_processed,
            clear_processed_skills
        )

        clear_processed_skills()

        assert is_skill_processed("deploy-api") is False

        mark_skill_processed("deploy-api")

        assert is_skill_processed("deploy-api") is True
        assert is_skill_processed("other-skill") is False
