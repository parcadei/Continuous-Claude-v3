"""Coordination database for multi-agent observability.

Provides SQLite-backed tracking of:
- Running agents (spawned via tracked_spawn)
- Completed tasks with outputs
- Artifacts produced during execution

Schema is designed for:
- Fast insertions (agents spawn frequently)
- Efficient queries by session, pattern, status
- Low overhead (<1ms for typical operations)
"""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


def _get_db_path() -> Path:
    """Get coordination database path."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    db_dir = Path(project_dir) / ".claude" / "cache" / "agentica-coordination"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "coordination.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    premise TEXT,
    model TEXT,
    scope_keys TEXT,  -- JSON array of scope function names
    pattern TEXT,     -- swarm, hierarchical, jury, etc.
    parent_agent_id TEXT,  -- For hierarchical patterns
    pid INTEGER,      -- Process ID for orphan detection
    ppid INTEGER,     -- Parent process ID for Unix orphan detection
    spawned_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',  -- running, completed, failed
    error_message TEXT,
    source TEXT       -- 'cli' (Task tool), 'agentica' (server), or NULL
);

CREATE TABLE IF NOT EXISTS completed_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    pattern TEXT,
    input_summary TEXT,  -- Truncated input for display
    output_summary TEXT, -- Truncated output for display
    output_type TEXT,    -- Type of output (str, dict, HandoffState, etc.)
    artifacts TEXT,      -- JSON dict of artifacts
    duration_ms INTEGER,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value_type TEXT,  -- str, dict, list, etc.
    value TEXT,       -- JSON-serialized value
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES completed_tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_agents_session ON agents(session_id);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_pattern ON agents(pattern);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON completed_tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id);

CREATE TABLE IF NOT EXISTS broadcasts (
    id TEXT PRIMARY KEY,
    swarm_id TEXT NOT NULL,
    sender_agent TEXT NOT NULL,
    broadcast_type TEXT NOT NULL,  -- finding, question, blocker, done, abort
    payload TEXT NOT NULL,  -- JSON serialized
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_broadcasts_swarm
    ON broadcasts(swarm_id, created_at);
"""


class BroadcastType(str, Enum):
    """Type of broadcast message for swarm coordination."""
    FINDING = "finding"      # Discovered something useful
    QUESTION = "question"    # Asking other agents
    BLOCKER = "blocker"      # Stuck, need help
    DONE = "done"            # Agent completed its work
    ABORT = "abort"          # Critical failure, abort swarm

    def __str__(self) -> str:
        """Return the enum value as string.

        Required for SQLite storage - allows BroadcastType to be used directly
        in SQL INSERT without explicit .value access, and for consistent
        string representation in logs and error messages.
        """
        return self.value


@dataclass
class BroadcastRecord:
    """Record of a broadcast message in a swarm."""
    id: str
    swarm_id: str
    sender_agent: str
    broadcast_type: BroadcastType
    payload: dict[str, Any]
    created_at: datetime


@dataclass
class AgentRecord:
    """Record of a spawned agent."""
    id: str
    session_id: str
    premise: str | None
    model: str | None
    scope_keys: list[str]
    pattern: str | None
    parent_agent_id: str | None
    pid: int | None
    ppid: int | None
    spawned_at: datetime
    completed_at: datetime | None
    status: str
    error_message: str | None
    source: str | None = None  # 'cli' (Task tool), 'agentica', or None


@dataclass
class OrphanCandidate:
    """Candidate orphan agent for cleanup.

    Tiers:
        1: ppid == 1 (true Unix orphan) -> safe to kill immediately
        2: parent_agent_id exists but parent status != 'running' -> kill after 30min
        3: Running > 24h with no recent activity -> kill after timeout
    """
    agent_id: str
    ppid: int | None
    parent_agent_id: str | None
    spawned_at: datetime
    tier: int  # 1=Unix orphan, 2=parent dead, 3=app orphan
    reason: str


@dataclass
class TaskRecord:
    """Record of a completed task."""
    id: str
    agent_id: str
    pattern: str | None
    input_summary: str
    output_summary: str
    output_type: str
    artifacts: dict[str, Any]
    duration_ms: int
    completed_at: datetime


class CoordinationDB:
    """SQLite database for agent coordination tracking.

    Thread-safe via new connection per operation.
    Suitable for multi-agent concurrent access.
    """

    def __init__(self, db_path: Path | None = None, session_id: str | None = None):
        """Initialize coordination database.

        Args:
            db_path: Optional custom database path (default: project cache)
            session_id: Session identifier for agent isolation (default: generated)
        """
        self.db_path = db_path or _get_db_path()
        self.session_id = session_id or uuid4().hex[:8]
        self._init_schema()

    @contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema and run migrations."""
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)
            self._run_migrations(conn)

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Run database migrations for schema updates.

        Migrations are idempotent - safe to run multiple times.
        """
        # Migration: Add pid column to agents table (Phase 7)
        cursor = conn.execute("PRAGMA table_info(agents)")
        columns = {row[1] for row in cursor.fetchall()}

        if "pid" not in columns:
            conn.execute("ALTER TABLE agents ADD COLUMN pid INTEGER")

        if "ppid" not in columns:
            conn.execute("ALTER TABLE agents ADD COLUMN ppid INTEGER")

        if "source" not in columns:
            conn.execute("ALTER TABLE agents ADD COLUMN source TEXT")

    def register_agent(
        self,
        agent_id: str,
        premise: str | None = None,
        model: str | None = None,
        scope_keys: list[str] | None = None,
        pattern: str | None = None,
        parent_agent_id: str | None = None,
        pid: int | None = None,
        ppid: int | None = None,
        source: str | None = None,
    ) -> AgentRecord:
        """Register a spawned agent.

        Args:
            agent_id: Unique identifier for the agent
            premise: Agent's system prompt or premise
            model: Model name (e.g., claude-sonnet)
            scope_keys: List of scope function names
            pattern: Coordination pattern (swarm, hierarchical, etc.)
            parent_agent_id: ID of parent agent (for hierarchical patterns)
            pid: Process ID for orphan detection
            ppid: Parent process ID for Unix orphan detection
            source: Where agent was spawned from ('cli' or 'agentica')
        """
        now = datetime.now(UTC).replace(tzinfo=None)

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, model, scope_keys, pattern,
                 parent_agent_id, pid, ppid, spawned_at, status, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    self.session_id,
                    premise,
                    model,
                    json.dumps(scope_keys or []),
                    pattern,
                    parent_agent_id,
                    pid,
                    ppid,
                    now.isoformat(),
                    "running",
                    source,
                )
            )

        return AgentRecord(
            id=agent_id,
            session_id=self.session_id,
            premise=premise,
            model=model,
            scope_keys=scope_keys or [],
            pattern=pattern,
            parent_agent_id=parent_agent_id,
            pid=pid,
            ppid=ppid,
            spawned_at=now,
            completed_at=None,
            status="running",
            error_message=None,
            source=source,
        )

    def complete_agent(
        self,
        agent_id: str,
        status: str = "completed",
        error_message: str | None = None,
    ) -> None:
        """Mark agent as completed or failed."""
        now = datetime.now(UTC).replace(tzinfo=None)

        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE agents
                SET completed_at = ?, status = ?, error_message = ?
                WHERE id = ?
                """,
                (now.isoformat(), status, error_message, agent_id)
            )

    def record_task(
        self,
        agent_id: str,
        input_text: str,
        output: Any,
        duration_ms: int,
        pattern: str | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> TaskRecord:
        """Record a completed task."""
        task_id = uuid4().hex[:8]
        now = datetime.now(UTC).replace(tzinfo=None)

        # Truncate input/output for storage
        input_summary = input_text[:500] if input_text else ""
        output_summary = str(output)[:500] if output else ""
        output_type = type(output).__name__

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO completed_tasks
                (id, agent_id, pattern, input_summary, output_summary,
                 output_type, artifacts, duration_ms, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    agent_id,
                    pattern,
                    input_summary,
                    output_summary,
                    output_type,
                    json.dumps(artifacts or {}),
                    duration_ms,
                    now.isoformat(),
                )
            )

            # Store artifacts as separate rows for querying
            if artifacts:
                for key, value in artifacts.items():
                    artifact_id = uuid4().hex[:8]
                    conn.execute(
                        """
                        INSERT INTO artifacts
                        (id, task_id, key, value_type, value, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            artifact_id,
                            task_id,
                            key,
                            type(value).__name__,
                            json.dumps(value, default=str),
                            now.isoformat(),
                        )
                    )

        return TaskRecord(
            id=task_id,
            agent_id=agent_id,
            pattern=pattern,
            input_summary=input_summary,
            output_summary=output_summary,
            output_type=output_type,
            artifacts=artifacts or {},
            duration_ms=duration_ms,
            completed_at=now,
        )

    def get_running_agents(self, pattern: str | None = None) -> list[AgentRecord]:
        """Get all running agents, optionally filtered by pattern."""
        with self._get_conn() as conn:
            if pattern:
                rows = conn.execute(
                    """
                    SELECT * FROM agents
                    WHERE session_id = ? AND status = 'running' AND pattern = ?
                    ORDER BY spawned_at DESC
                    """,
                    (self.session_id, pattern)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM agents
                    WHERE session_id = ? AND status = 'running'
                    ORDER BY spawned_at DESC
                    """,
                    (self.session_id,)
                ).fetchall()

        return [self._row_to_agent(row) for row in rows]

    def get_all_running_agents(self, pattern: str | None = None) -> list[AgentRecord]:
        """Get all running agents across ALL sessions, optionally filtered by pattern."""
        with self._get_conn() as conn:
            if pattern:
                rows = conn.execute(
                    """
                    SELECT * FROM agents
                    WHERE status = 'running' AND pattern = ?
                    ORDER BY session_id, spawned_at DESC
                    """,
                    (pattern,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM agents
                    WHERE status = 'running'
                    ORDER BY session_id, spawned_at DESC
                    """
                ).fetchall()

        return [self._row_to_agent(row) for row in rows]

    def get_global_running_count(self) -> int:
        """Count ALL running agents across all sessions.

        Returns:
            Total count of agents with status='running' across all sessions.
        """
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM agents WHERE status = 'running'"
            ).fetchone()[0]

    def get_all_sessions(self) -> list[str]:
        """Get list of all unique session IDs."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT session_id FROM agents ORDER BY session_id"
            ).fetchall()
        return [row[0] for row in rows]

    def get_all_sessions_summary(self) -> dict[str, Any]:
        """Get summary statistics across all sessions."""
        with self._get_conn() as conn:
            # Total agents
            total_agents = conn.execute(
                "SELECT COUNT(*) FROM agents"
            ).fetchone()[0]

            # Agents by session
            session_counts = dict(conn.execute(
                """
                SELECT session_id, COUNT(*) as count
                FROM agents
                GROUP BY session_id
                """
            ).fetchall())

            # Total unique sessions
            total_sessions = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM agents"
            ).fetchone()[0]

        return {
            "total_agents": total_agents,
            "agents_by_session": session_counts,
            "total_sessions": total_sessions,
        }

    def get_completed_tasks(
        self,
        agent_id: str | None = None,
        limit: int = 20
    ) -> list[TaskRecord]:
        """Get completed tasks, optionally filtered by agent."""
        with self._get_conn() as conn:
            if agent_id:
                rows = conn.execute(
                    """
                    SELECT * FROM completed_tasks
                    WHERE agent_id = ?
                    ORDER BY completed_at DESC
                    LIMIT ?
                    """,
                    (agent_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT ct.* FROM completed_tasks ct
                    JOIN agents a ON ct.agent_id = a.id
                    WHERE a.session_id = ?
                    ORDER BY ct.completed_at DESC
                    LIMIT ?
                    """,
                    (self.session_id, limit)
                ).fetchall()

        return [self._row_to_task(row) for row in rows]

    def get_session_summary(self) -> dict[str, Any]:
        """Get summary statistics for current session."""
        with self._get_conn() as conn:
            status_counts = dict(conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM agents
                WHERE session_id = ?
                GROUP BY status
                """,
                (self.session_id,)
            ).fetchall())

            pattern_counts = dict(conn.execute(
                """
                SELECT pattern, COUNT(*) as count
                FROM agents
                WHERE session_id = ? AND pattern IS NOT NULL
                GROUP BY pattern
                """,
                (self.session_id,)
            ).fetchall())

            task_count = conn.execute(
                """
                SELECT COUNT(*) FROM completed_tasks ct
                JOIN agents a ON ct.agent_id = a.id
                WHERE a.session_id = ?
                """,
                (self.session_id,)
            ).fetchone()[0]

        return {
            "session_id": self.session_id,
            "agents_by_status": status_counts,
            "agents_by_pattern": pattern_counts,
            "total_tasks": task_count,
        }

    def find_orphans(self) -> list[OrphanCandidate]:
        """Find potential orphan agents using three-tier detection.

        Tier 1: ppid == 1 (true Unix orphan) -> safe to kill immediately
        Tier 2: parent_agent_id exists but parent status != 'running' -> kill after 30min
        Tier 3: Running > 24h with no recent activity -> kill after timeout

        EXCLUDES main sessions (parent_agent_id IS NULL AND ppid != 1) to prevent
        accidentally killing the main orchestrating session.

        Returns:
            List of OrphanCandidate with tier classification and reason.
        """
        candidates: list[OrphanCandidate] = []
        now = datetime.now(UTC).replace(tzinfo=None)
        grace_30min = now - timedelta(minutes=30)
        grace_24h = now - timedelta(hours=24)

        with self._get_conn() as conn:
            # Tier 1: True Unix orphans (ppid == 1)
            rows = conn.execute(
                """
                SELECT id, ppid, parent_agent_id, spawned_at
                FROM agents
                WHERE status = 'running' AND ppid = 1
                """
            ).fetchall()
            for row in rows:
                candidates.append(OrphanCandidate(
                    agent_id=row["id"],
                    ppid=row["ppid"],
                    parent_agent_id=row["parent_agent_id"],
                    spawned_at=datetime.fromisoformat(row["spawned_at"]),
                    tier=1,
                    reason="ppid=1 (parent process died)",
                ))

            # Tier 2: Parent agent dead (status != 'running'), child > 30min old
            # Must have parent_agent_id (excludes main sessions)
            rows = conn.execute(
                """
                SELECT a.id, a.ppid, a.parent_agent_id, a.spawned_at
                FROM agents a
                JOIN agents p ON a.parent_agent_id = p.id
                WHERE a.status = 'running'
                  AND p.status != 'running'
                  AND a.spawned_at < ?
                """,
                (grace_30min.isoformat(),)
            ).fetchall()

            for row in rows:
                candidates.append(OrphanCandidate(
                    agent_id=row["id"],
                    ppid=row["ppid"],
                    parent_agent_id=row["parent_agent_id"],
                    spawned_at=datetime.fromisoformat(row["spawned_at"]),
                    tier=2,
                    reason="Parent agent completed/failed (30min grace expired)",
                ))

            # Tier 3: App orphans - running > 24h with parent_agent_id set
            # Must have parent_agent_id (excludes main sessions)
            rows = conn.execute(
                """
                SELECT id, ppid, parent_agent_id, spawned_at
                FROM agents
                WHERE status = 'running'
                  AND parent_agent_id IS NOT NULL
                  AND spawned_at < ?
                """,
                (grace_24h.isoformat(),)
            ).fetchall()

            for row in rows:
                # Avoid duplicate if already classified as tier 1 or tier 2
                agent_id = row["id"]
                if not any(c.agent_id == agent_id for c in candidates):
                    candidates.append(OrphanCandidate(
                        agent_id=agent_id,
                        ppid=row["ppid"],
                        parent_agent_id=row["parent_agent_id"],
                        spawned_at=datetime.fromisoformat(row["spawned_at"]),
                        tier=3,
                        reason="Running >24h without completion",
                    ))

        return candidates

    # Alias for plan consistency
    get_orphan_candidates = find_orphans

    def _row_to_agent(self, row: sqlite3.Row) -> AgentRecord:
        """Convert database row to AgentRecord."""
        return AgentRecord(
            id=row["id"],
            session_id=row["session_id"],
            premise=row["premise"],
            model=row["model"],
            scope_keys=json.loads(row["scope_keys"]) if row["scope_keys"] else [],
            pattern=row["pattern"],
            parent_agent_id=row["parent_agent_id"],
            pid=row["pid"],
            ppid=row["ppid"] if "ppid" in row.keys() else None,
            spawned_at=datetime.fromisoformat(row["spawned_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
            status=row["status"],
            error_message=row["error_message"],
            source=row["source"] if "source" in row.keys() else None,
        )

    def _row_to_task(self, row: sqlite3.Row) -> TaskRecord:
        """Convert database row to TaskRecord."""
        return TaskRecord(
            id=row["id"],
            agent_id=row["agent_id"],
            pattern=row["pattern"],
            input_summary=row["input_summary"],
            output_summary=row["output_summary"],
            output_type=row["output_type"],
            artifacts=json.loads(row["artifacts"]) if row["artifacts"] else {},
            duration_ms=row["duration_ms"],
            completed_at=datetime.fromisoformat(row["completed_at"]),
        )

    def create_broadcast(
        self,
        swarm_id: str,
        sender_agent: str,
        broadcast_type: BroadcastType,
        payload: dict[str, Any],
    ) -> BroadcastRecord:
        """Create a broadcast message for swarm coordination.

        Args:
            swarm_id: Identifier for the swarm
            sender_agent: Identifier of the sending agent
            broadcast_type: Type of broadcast (finding, question, blocker, done, abort)
            payload: JSON-serializable payload data

        Returns:
            BroadcastRecord with the created broadcast details
        """
        broadcast_id = uuid4().hex[:12]
        now = datetime.now(UTC).replace(tzinfo=None)

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO broadcasts
                (id, swarm_id, sender_agent, broadcast_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    broadcast_id,
                    swarm_id,
                    sender_agent,
                    broadcast_type.value,
                    json.dumps(payload),
                    now.isoformat(),
                )
            )

        return BroadcastRecord(
            id=broadcast_id,
            swarm_id=swarm_id,
            sender_agent=sender_agent,
            broadcast_type=broadcast_type,
            payload=payload,
            created_at=now,
        )

    def get_broadcasts(
        self,
        swarm_id: str,
        since: datetime | None = None,
        exclude_sender: str | None = None,
        broadcast_types: list[BroadcastType] | None = None,
    ) -> list[BroadcastRecord]:
        """Get broadcasts for a swarm, optionally filtered.

        Args:
            swarm_id: Identifier for the swarm
            since: Only return broadcasts created after this time
            exclude_sender: Exclude broadcasts from this sender
            broadcast_types: Only return broadcasts of these types

        Returns:
            List of BroadcastRecord objects, ordered by created_at ASC
        """
        query = "SELECT * FROM broadcasts WHERE swarm_id = ?"
        params: list[Any] = [swarm_id]

        if since:
            query += " AND created_at > ?"
            params.append(since.isoformat())

        if exclude_sender:
            query += " AND sender_agent != ?"
            params.append(exclude_sender)

        if broadcast_types:
            placeholders = ",".join("?" * len(broadcast_types))
            query += f" AND broadcast_type IN ({placeholders})"
            params.extend([bt.value for bt in broadcast_types])

        query += " ORDER BY created_at ASC"

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_broadcast(row) for row in rows]

    def _row_to_broadcast(self, row: sqlite3.Row) -> BroadcastRecord:
        """Convert database row to BroadcastRecord."""
        try:
            payload = json.loads(row["payload"]) if row["payload"] else {}
        except json.JSONDecodeError:
            payload = {}

        return BroadcastRecord(
            id=row["id"],
            swarm_id=row["swarm_id"],
            sender_agent=row["sender_agent"],
            broadcast_type=BroadcastType(row["broadcast_type"]),
            payload=payload,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
