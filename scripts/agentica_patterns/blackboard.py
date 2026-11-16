"""Blackboard communication protocol for multi-agent coordination.

Architecture:
- HOT tier: JSON file cache, last N entries, fast polling
- COLD tier: PostgreSQL, full history, semantic search

Temporal layers:
- PAST: Query database for who did what
- PRESENT: PreToolUse hook polls cache → injects as system reminder
- FUTURE: Push to queue, next poll picks it up
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, UTC
from enum import Enum
from pathlib import Path
from typing import Any

# Cache configuration
BLACKBOARD_CACHE_DIR = Path(os.environ.get("BLACKBOARD_CACHE_DIR", "/tmp/claude-blackboard"))
MAX_HOT_ENTRIES = int(os.environ.get("BLACKBOARD_HOT_SIZE", "20"))


class MessageType(str, Enum):
    """Types of blackboard messages."""

    TASK = "task"  # Task assignment
    RESULT = "result"  # Task completion
    QUERY = "query"  # Question to other agents
    RESPONSE = "response"  # Answer to query
    STATUS = "status"  # Progress update
    ARTIFACT = "artifact"  # File/resource created
    ERROR = "error"  # Failure notification


class EntryPriority(str, Enum):
    """Priority levels for message ordering."""

    CRITICAL = "critical"  # Must see immediately
    HIGH = "high"  # Important
    NORMAL = "normal"  # Standard
    LOW = "low"  # Background info


class ScopeLevel(str, Enum):
    """Scope levels for blackboard entries.

    Maps to 3-layer memory model:
    - AGENT: Layer 1 - Individual agent's task queue (private)
    - SHARED: Layer 2 - Swarm/pattern blackboard (visible to pattern)
    - TEMPORAL: Layer 3 - Global history (cross-pattern, PostgreSQL)
    """

    AGENT = "agent"  # Private to one agent
    SHARED = "shared"  # Visible to all agents in pattern/swarm
    TEMPORAL = "temporal"  # Global, persisted, queryable history


@dataclass
class SharedContextEntry:
    """A single entry on the blackboard.

    Hybrid format: structured JSON + optional formal logic + prose fallback.

    Example:
        {
            "id": "abc123",
            "project_id": "my-project",
            "type": "task",
            "from_agent": "coordinator",
            "to_agent": "implementer",
            "formal": "∃ f ∈ File(hello.py) : write(f, 'print(\"hello\")')",
            "prose": "Create hello.py that prints hello world",
            "data": {"file": "hello.py", "content": "print('hello world')"},
            "artifacts": [],
            "priority": "normal",
            "timestamp": "2025-12-30T22:30:00Z",
            "parent_id": null,
            "ttl_seconds": 3600
        }
    """

    # Identity
    id: str
    project_id: str

    # Routing (required fields)
    type: MessageType
    from_agent: str

    # Optional routing
    to_agent: str | None = None  # None = broadcast
    pattern_id: str | None = None  # Which pattern/swarm (for SHARED scope)

    # Scope (which layer this entry belongs to)
    scope: ScopeLevel = ScopeLevel.SHARED  # Default to swarm-visible

    # Content (hybrid format)
    formal: str | None = None  # Formal logic notation
    prose: str | None = None  # Natural language fallback
    data: dict[str, Any] = field(default_factory=dict)  # Structured payload

    # References
    artifacts: list[str] = field(default_factory=list)  # File paths
    parent_id: str | None = None  # For threading

    # Metadata
    priority: EntryPriority = EntryPriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    ttl_seconds: int | None = None  # Auto-expire after N seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["type"] = self.type.value
        d["priority"] = self.priority.value
        d["scope"] = self.scope.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SharedContextEntry:
        """Create from dictionary."""
        data = data.copy()
        data["type"] = MessageType(data["type"])
        data["priority"] = EntryPriority(data.get("priority", "normal"))
        data["scope"] = ScopeLevel(data.get("scope", "shared"))
        return cls(**data)

    def to_system_reminder(self) -> str:
        """Format as system reminder for hook injection.

        Compact format to minimize token usage.
        """
        parts = [f"[{self.type.value.upper()}]"]

        if self.from_agent:
            parts.append(f"from:{self.from_agent}")
        if self.to_agent:
            parts.append(f"to:{self.to_agent}")

        # Prefer formal, fall back to prose
        if self.formal:
            parts.append(f"| {self.formal}")
        elif self.prose:
            parts.append(f"| {self.prose}")

        # Add structured data if present
        if self.data:
            # Compact JSON
            parts.append(f"| data={json.dumps(self.data, separators=(',', ':'))}")

        if self.artifacts:
            parts.append(f"| files={','.join(self.artifacts)}")

        return " ".join(parts)


class BlackboardCache:
    """Hot tier: JSON file cache for fast polling."""

    def __init__(self, project_id: str, cache_dir: Path = BLACKBOARD_CACHE_DIR):
        """Initialize cache for a project.

        Args:
            project_id: Project identifier
            cache_dir: Directory for cache files
        """
        self.project_id = project_id
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / f"{project_id}.json"

    def _load(self) -> list[dict[str, Any]]:
        """Load entries from cache file."""
        if not self.cache_file.exists():
            return []
        try:
            with open(self.cache_file) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, entries: list[dict[str, Any]]) -> None:
        """Save entries to cache file."""
        # Atomic write
        tmp_file = self.cache_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            json.dump(entries, f, indent=2)
        tmp_file.rename(self.cache_file)

    def push(self, entry: SharedContextEntry) -> None:
        """Add entry to cache (FIFO with max size)."""
        entries = self._load()
        entries.append(entry.to_dict())

        # Enforce max size (keep most recent)
        if len(entries) > MAX_HOT_ENTRIES:
            entries = entries[-MAX_HOT_ENTRIES:]

        self._save(entries)

    def poll(
        self,
        agent_id: str | None = None,
        pattern_id: str | None = None,
        since_timestamp: str | None = None,
        types: list[MessageType] | None = None,
        scope: ScopeLevel | None = None,
    ) -> list[SharedContextEntry]:
        """Poll cache for relevant entries.

        Args:
            agent_id: Filter to entries addressed to this agent (or broadcasts)
            pattern_id: Filter to entries for this pattern/swarm
            since_timestamp: Only entries after this ISO timestamp
            types: Filter to these message types
            scope: Filter to this scope level

        Returns:
            List of matching entries, oldest first
        """
        entries = self._load()
        result = []

        # Filter expired entries
        now = time.time()
        valid_entries = []
        for e in entries:
            if e.get("ttl_seconds"):
                entry_time = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                age = now - entry_time.timestamp()
                if age > e["ttl_seconds"]:
                    continue  # Expired
            valid_entries.append(e)

        for e in valid_entries:
            # Filter by scope
            if scope and e.get("scope", "shared") != scope.value:
                continue

            # Filter by pattern (for SHARED scope)
            if pattern_id:
                entry_pattern = e.get("pattern_id")
                if entry_pattern and entry_pattern != pattern_id:
                    continue

            # Filter by agent
            if agent_id:
                entry_scope = ScopeLevel(e.get("scope", "shared"))
                to_agent = e.get("to_agent")

                # AGENT scope: only if from/to this agent
                if entry_scope == ScopeLevel.AGENT:
                    if e.get("from_agent") != agent_id and to_agent != agent_id:
                        continue
                # SHARED/TEMPORAL: only if broadcast or addressed to this agent
                elif to_agent and to_agent != agent_id:
                    continue

            # Filter by timestamp
            if since_timestamp and e["timestamp"] <= since_timestamp:
                continue

            # Filter by type
            if types and e["type"] not in [t.value for t in types]:
                continue

            result.append(SharedContextEntry.from_dict(e))

        return result

    def clear(self) -> None:
        """Clear all entries from cache."""
        self.cache_file.unlink(missing_ok=True)

    def get_summary(self, max_entries: int = 5) -> str:
        """Get compact summary for context injection.

        Returns:
            Formatted string suitable for system reminder
        """
        entries = self.poll()
        if not entries:
            return ""

        # Take most recent, prioritize by priority
        recent = sorted(
            entries,
            key=lambda e: (
                0 if e.priority == EntryPriority.CRITICAL else
                1 if e.priority == EntryPriority.HIGH else
                2 if e.priority == EntryPriority.NORMAL else 3,
                e.timestamp,
            ),
        )[:max_entries]

        lines = ["<blackboard>"]
        for entry in recent:
            lines.append(entry.to_system_reminder())
        lines.append("</blackboard>")

        return "\n".join(lines)


# Convenience functions for common operations


def create_task(
    project_id: str,
    from_agent: str,
    to_agent: str | None,
    description: str,
    data: dict[str, Any] | None = None,
    formal: str | None = None,
    priority: EntryPriority = EntryPriority.NORMAL,
) -> SharedContextEntry:
    """Create a task assignment entry."""
    import uuid

    return SharedContextEntry(
        id=str(uuid.uuid4())[:8],
        project_id=project_id,
        type=MessageType.TASK,
        from_agent=from_agent,
        to_agent=to_agent,
        formal=formal,
        prose=description,
        data=data or {},
        priority=priority,
    )


def create_result(
    project_id: str,
    from_agent: str,
    task_id: str,
    success: bool,
    summary: str,
    artifacts: list[str] | None = None,
) -> SharedContextEntry:
    """Create a task result entry."""
    import uuid

    return SharedContextEntry(
        id=str(uuid.uuid4())[:8],
        project_id=project_id,
        type=MessageType.RESULT,
        from_agent=from_agent,
        parent_id=task_id,
        prose=summary,
        data={"success": success},
        artifacts=artifacts or [],
    )


def create_status(
    project_id: str,
    from_agent: str,
    status: str,
    progress: float | None = None,
) -> SharedContextEntry:
    """Create a status update entry."""
    import uuid

    data: dict[str, Any] = {}
    if progress is not None:
        data["progress"] = progress

    return SharedContextEntry(
        id=str(uuid.uuid4())[:8],
        project_id=project_id,
        type=MessageType.STATUS,
        from_agent=from_agent,
        prose=status,
        data=data,
        priority=EntryPriority.LOW,
        ttl_seconds=300,  # Status updates expire after 5 minutes
    )


# Test function
def _test_hello_world():
    """Test the blackboard with a hello world task."""
    cache = BlackboardCache("test-project")
    cache.clear()

    # Coordinator assigns task
    task = create_task(
        project_id="test-project",
        from_agent="coordinator",
        to_agent="implementer",
        description="Create hello.py that prints hello world",
        formal="∃ f ∈ File(hello.py) : write(f, 'print(\"hello world\")')",
        data={"file": "hello.py", "content": "print('hello world')"},
    )
    cache.push(task)

    # Implementer polls and sees task
    entries = cache.poll(agent_id="implementer")
    assert len(entries) == 1
    assert entries[0].type == MessageType.TASK

    # Check system reminder format
    reminder = entries[0].to_system_reminder()
    assert "[TASK]" in reminder
    assert "coordinator" in reminder
    assert "hello.py" in reminder

    # Implementer reports result
    result = create_result(
        project_id="test-project",
        from_agent="implementer",
        task_id=task.id,
        success=True,
        summary="Created hello.py with print statement",
        artifacts=["hello.py"],
    )
    cache.push(result)

    # Get summary
    summary = cache.get_summary()
    assert "<blackboard>" in summary
    assert "[RESULT]" in summary

    print("✓ Hello world test passed")
    print(f"\nTask reminder:\n{task.to_system_reminder()}")
    print(f"\nResult reminder:\n{result.to_system_reminder()}")
    print(f"\nFull summary:\n{summary}")

    return True


if __name__ == "__main__":
    _test_hello_world()
