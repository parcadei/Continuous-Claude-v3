"""PostToolUse Flywheel Integration (Phase 3 Task 3.13).

USAGE:
    This module provides functions for the PostToolUse hook to trigger
    the flywheel on skill executions.

    from scripts.post_tool_use_flywheel import (
        should_process_for_flywheel,
        extract_skill_id,
        process_skill_for_flywheel,
        create_hook_response
    )

    # In hook handler:
    if should_process_for_flywheel(hook_input):
        skill_id = extract_skill_id(hook_input)
        result = await process_skill_for_flywheel(hook_input)
        return create_hook_response(result.success, result.reason)

The flywheel is triggered when:
1. Tool is "Skill"
2. Skill is prose-only (no typed params)
3. Not already processed this session
"""

import os
from pathlib import Path
from typing import Any

from scripts.skill_flywheel import (
    run_flywheel,
    should_trigger_flywheel,
    mark_skill_processed,
    FlywheelResult
)


def should_process_for_flywheel(hook_input: dict[str, Any]) -> bool:
    """Determine if this tool use should trigger flywheel processing.

    Task 3.13: Only process Skill tool executions.

    Args:
        hook_input: PostToolUse hook input dict

    Returns:
        True if this is a Skill tool execution
    """
    tool_name = hook_input.get("tool_name", "")
    return tool_name == "Skill"


def extract_skill_id(hook_input: dict[str, Any]) -> str | None:
    """Extract skill ID from Skill tool input.

    Args:
        hook_input: PostToolUse hook input dict

    Returns:
        Skill ID or None if not found
    """
    tool_input = hook_input.get("tool_input", {})
    return tool_input.get("skill")


def get_skill_path(skill_id: str) -> Path | None:
    """Get path to skill directory.

    Searches in:
    1. $CLAUDE_PROJECT_DIR/.claude/skills/{skill_id}/
    2. ~/.claude/skills/{skill_id}/

    Args:
        skill_id: Skill identifier

    Returns:
        Path to skill directory or None
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")

    # Check project skills first
    project_skill = Path(project_dir) / ".claude" / "skills" / skill_id
    if project_skill.exists() and (project_skill / "SKILL.md").exists():
        return project_skill

    # Check user skills
    home = Path.home()
    user_skill = home / ".claude" / "skills" / skill_id
    if user_skill.exists() and (user_skill / "SKILL.md").exists():
        return user_skill

    return None


async def process_skill_for_flywheel(
    hook_input: dict[str, Any]
) -> FlywheelResult | None:
    """Process a Skill tool execution through the flywheel.

    Task 3.13: Main integration point.

    Args:
        hook_input: PostToolUse hook input dict

    Returns:
        FlywheelResult if processed, None if skipped
    """
    skill_id = extract_skill_id(hook_input)
    if not skill_id:
        return None

    skill_path = get_skill_path(skill_id)
    if not skill_path:
        return None

    # Read skill content
    skill_file = skill_path / "SKILL.md"
    content = skill_file.read_text()

    # Extract prompt from args (if provided)
    tool_input = hook_input.get("tool_input", {})
    args = tool_input.get("args", "")

    # Parse --prompt from args
    prompt = ""
    if "--prompt" in args:
        # Simple extraction
        import re
        match = re.search(r"--prompt\s+['\"]?([^'\"]+)['\"]?", args)
        if match:
            prompt = match.group(1)

    # Check trigger conditions
    if not should_trigger_flywheel(skill_id, content, prompt):
        return None

    # Run flywheel (without persistence by default - controlled by config)
    persist = os.environ.get("FLYWHEEL_AUTO_PERSIST", "false").lower() == "true"
    result = await run_flywheel(skill_path, prompt, persist=persist)

    # Mark as processed to prevent double-execution
    if result.success:
        mark_skill_processed(skill_id)

    return result


def create_hook_response(
    success: bool,
    message: str = ""
) -> dict[str, Any]:
    """Create standard hook response.

    Args:
        success: Whether processing was successful
        message: Optional message for system prompt

    Returns:
        Hook response dict
    """
    response: dict[str, Any] = {
        "result": "continue"  # Always continue, flywheel is advisory
    }

    if message:
        response["message"] = message

    return response
