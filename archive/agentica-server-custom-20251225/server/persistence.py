"""State persistence for Agentica agents.

State is persisted to:
    .claude/cache/agentica-state/{agent_type}.json

Each state file contains:
    - timestamp: last update time
    - agent_type: the agent type identifier
    - query_count: total queries processed
    - state: the actual agent state dict

Note: This is a stub for Phase 1. Full implementation in Phase 2.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Default threshold for state flushing (1MB)
STATE_SIZE_THRESHOLD = 1024 * 1024


def _get_state_dir() -> Path:
    """Get the state directory path."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    state_dir = Path(project_dir) / ".claude" / "cache" / "agentica-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _get_state_path(agent_type: str) -> Path:
    """Get the state file path for an agent type."""
    return _get_state_dir() / f"{agent_type}.json"


def save_state(agent_type: str, state: dict[str, Any]) -> None:
    """Save agent state to disk.

    Args:
        agent_type: The agent type identifier
        state: The state dict to persist
    """
    path = _get_state_path(agent_type)

    # Load existing metadata if available
    existing = {}
    if path.exists():
        try:
            with open(path) as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            pass

    # Update query count
    query_count = existing.get("query_count", 0) + 1

    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent_type": agent_type,
        "query_count": query_count,
        "state": state,
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_state(agent_type: str) -> Optional[dict[str, Any]]:
    """Load agent state from disk.

    Args:
        agent_type: The agent type identifier

    Returns:
        The state dict, or None if no state file exists
    """
    path = _get_state_path(agent_type)

    if not path.exists():
        return None

    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("state", {})
    except json.JSONDecodeError:
        return None


def get_state_size(agent_type: str) -> int:
    """Get the size of the state file in bytes.

    Args:
        agent_type: The agent type identifier

    Returns:
        Size in bytes, or 0 if no file
    """
    path = _get_state_path(agent_type)
    if not path.exists():
        return 0
    return path.stat().st_size


def should_flush(agent_type: str, threshold: int = STATE_SIZE_THRESHOLD) -> bool:
    """Check if state should be flushed due to size.

    Args:
        agent_type: The agent type identifier
        threshold: Size threshold in bytes (default 1MB)

    Returns:
        True if state exceeds threshold
    """
    return get_state_size(agent_type) > threshold


def flush_state(agent_type: str) -> None:
    """Flush large state, preserving essential data.

    This reduces the state size by:
    - Keeping only the last N findings
    - Summarizing query history count
    - Keeping source URLs but not full content

    Args:
        agent_type: The agent type identifier
    """
    state = load_state(agent_type)
    if not state:
        return

    flushed = {}

    # Preserve last 5 findings
    if "findings" in state:
        findings = state["findings"]
        if isinstance(findings, list):
            flushed["findings"] = findings[-5:]
            flushed["findings_count"] = len(findings)

    # Preserve query count summary
    if "query_history" in state:
        history = state["query_history"]
        if isinstance(history, list):
            flushed["query_count"] = len(history)
            flushed["last_query"] = history[-1] if history else None

    # Preserve source URLs only (no content)
    if "sources" in state:
        sources = state["sources"]
        if isinstance(sources, dict):
            flushed["sources"] = {k: v[:100] if isinstance(v, str) else v
                                   for k, v in list(sources.items())[:20]}

    # Preserve any custom fields not in the flush list
    preserve_fields = {"current_focus", "research_topic", "summary"}
    for field in preserve_fields:
        if field in state:
            flushed[field] = state[field]

    # Add flush marker
    flushed["_flushed_at"] = datetime.utcnow().isoformat()

    save_state(agent_type, flushed)
