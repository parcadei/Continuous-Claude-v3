"""BeadsTaskGraph - Hash-based task graph with blocked cache.

Inspired by Beads (https://github.com/steveyegge/beads):
- Hash-based IDs: bd-{sha256(uuid4)[:6]} for collision-free multi-agent creation
- 6 dependency types: blocks, conditional-blocks, waits-for, parent-child, related, discovered-from
- Blocked cache: Pre-computed view of ready tasks (O(1) lookup)
- Wisps: Ephemeral tasks for agent-internal state (never shared)

Usage:
    graph = BeadsTaskGraph(session_id="abc123")

    # Create tasks with dependencies
    task_a = graph.add_task("Research API options")
    task_b = graph.add_task("Design schema", blocks=[task_a])
    task_c = graph.add_task("Implement endpoints", blocks=[task_b])

    # Get ready tasks (O(1) via blocked cache)
    ready = graph.get_ready_tasks()  # Returns [task_a]

    # Complete and check again
    graph.complete_task(task_a)
    ready = graph.get_ready_tasks()  # Returns [task_b]
"""

import hashlib
import json
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


DependencyType = Literal[
    "blocks",
    "conditional_blocks",
    "waits_for",
    "parent_child",
    "related",
    "discovered_from",
]


def generate_task_id() -> str:
    """Generate hash-based task ID."""
    raw = uuid4().hex
    hash_bytes = hashlib.sha256(raw.encode()).hexdigest()[:6]
    return f"bd-{hash_bytes}"


def generate_wisp_id() -> str:
    """Generate wisp ID."""
    raw = uuid4().hex
    hash_bytes = hashlib.sha256(raw.encode()).hexdigest()[:6]
    return f"wp-{hash_bytes}"


@dataclass
class BeadsTask:
    """A task in the Beads task graph."""
    id: str
    description: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    is_wisp: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class BeadsTaskGraph:
    """Hash-based task graph with blocked cache.

    Key features:
    - Hash-based IDs prevent collisions in multi-agent creation
    - 6 dependency types for rich task relationships
    - Blocked cache provides O(1) ready task queries
    - Wisps are ephemeral and excluded from shared views
    """

    def __init__(
        self,
        session_id: str = "default",
        db_path: Optional[Path] = None,
    ):
        self.session_id = session_id

        if db_path is None:
            import os
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            cache_dir = Path(project_dir) / ".claude" / "cache" / "agentica-tasks"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = cache_dir / "tasks.db"

        self._db_path = db_path
        self._blocked_cache: set[str] = set()  # Task IDs that are blocked
        self._init_schema()
        self._rebuild_blocked_cache()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    is_wisp BOOLEAN DEFAULT FALSE,
                    metadata_json TEXT,
                    created_at REAL NOT NULL,
                    completed_at REAL
                );

                CREATE TABLE IF NOT EXISTS dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    from_task TEXT NOT NULL,
                    to_task TEXT NOT NULL,
                    dep_type TEXT NOT NULL,
                    UNIQUE(from_task, to_task, dep_type),
                    FOREIGN KEY (from_task) REFERENCES tasks(id),
                    FOREIGN KEY (to_task) REFERENCES tasks(id)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(session_id, status);
                CREATE INDEX IF NOT EXISTS idx_deps_from ON dependencies(from_task);
                CREATE INDEX IF NOT EXISTS idx_deps_to ON dependencies(to_task);
            """)

    def add_task(
        self,
        description: str,
        blocks: Optional[list[str]] = None,
        conditional_blocks: Optional[list[str]] = None,
        waits_for: Optional[list[str]] = None,
        parent: Optional[str] = None,
        related: Optional[list[str]] = None,
        discovered_from: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Add a task to the graph.

        Args:
            description: Task description
            blocks: Tasks that must complete before this one
            conditional_blocks: Tasks that block this one only if they fail
            waits_for: Tasks this one waits for (can proceed if they fail)
            parent: Parent task (this is a subtask)
            related: Related tasks (informational)
            discovered_from: Task this was discovered from
            metadata: Optional metadata dict

        Returns:
            Task ID
        """
        task_id = generate_task_id()
        now = datetime.now(timezone.utc).timestamp()

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO tasks (id, session_id, description, status, is_wisp, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                self.session_id,
                description,
                TaskStatus.PENDING.value,
                False,
                json.dumps(metadata) if metadata else None,
                now,
            ))

            # Add dependencies
            deps_to_add = []
            if blocks:
                deps_to_add.extend((b, task_id, "blocks") for b in blocks)
            if conditional_blocks:
                deps_to_add.extend((b, task_id, "conditional_blocks") for b in conditional_blocks)
            if waits_for:
                deps_to_add.extend((w, task_id, "waits_for") for w in waits_for)
            if parent:
                deps_to_add.append((parent, task_id, "parent_child"))
            if related:
                deps_to_add.extend((r, task_id, "related") for r in related)
            if discovered_from:
                deps_to_add.append((discovered_from, task_id, "discovered_from"))

            for from_task, to_task, dep_type in deps_to_add:
                conn.execute("""
                    INSERT INTO dependencies (session_id, from_task, to_task, dep_type)
                    VALUES (?, ?, ?, ?)
                """, (self.session_id, from_task, to_task, dep_type))

        self._rebuild_blocked_cache()
        return task_id

    def add_wisp(self, description: str) -> str:
        """Add an ephemeral wisp task."""
        wisp_id = generate_wisp_id()
        now = datetime.now(timezone.utc).timestamp()

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO tasks (id, session_id, description, status, is_wisp, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (wisp_id, self.session_id, description, TaskStatus.PENDING.value, True, now))

        return wisp_id

    def add_dependency(self, from_task: str, dep_type: DependencyType, to_task: str) -> None:
        """Add a dependency between tasks.

        Args:
            from_task: Source task ID
            dep_type: Type of dependency
            to_task: Target task ID

        Raises:
            ValueError: If adding this dependency would create a cycle
        """
        # Check for cycles before adding
        if self._would_create_cycle(from_task, to_task):
            raise ValueError(f"Adding dependency {from_task} -> {to_task} would create a cycle")

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO dependencies (session_id, from_task, to_task, dep_type)
                VALUES (?, ?, ?, ?)
            """, (self.session_id, from_task, to_task, dep_type))

        self._rebuild_blocked_cache()

    def _would_create_cycle(self, from_task: str, to_task: str) -> bool:
        """Check if adding edge from_task -> to_task would create a cycle."""
        # If to_task can reach from_task, adding from_task -> to_task creates cycle
        visited = set()
        stack = [to_task]

        with self._get_conn() as conn:
            while stack:
                current = stack.pop()
                if current == from_task:
                    return True
                if current in visited:
                    continue
                visited.add(current)

                # Get all tasks that current depends on (blocking deps)
                rows = conn.execute("""
                    SELECT from_task FROM dependencies
                    WHERE session_id = ? AND to_task = ? AND dep_type IN ('blocks', 'waits_for')
                """, (self.session_id, current)).fetchall()

                for row in rows:
                    stack.append(row["from_task"])

        return False

    def complete_task(self, task_id: str) -> None:
        """Mark a task as completed."""
        now = datetime.now(timezone.utc).timestamp()

        with self._get_conn() as conn:
            conn.execute("""
                UPDATE tasks SET status = ?, completed_at = ?
                WHERE id = ? AND session_id = ?
            """, (TaskStatus.COMPLETED.value, now, task_id, self.session_id))

        self._rebuild_blocked_cache()

    def mark_in_progress(self, task_id: str) -> None:
        """Mark a task as in-progress."""
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE tasks SET status = ?
                WHERE id = ? AND session_id = ?
            """, (TaskStatus.IN_PROGRESS.value, task_id, self.session_id))

    def fail_task(self, task_id: str) -> None:
        """Mark a task as failed."""
        now = datetime.now(timezone.utc).timestamp()

        with self._get_conn() as conn:
            conn.execute("""
                UPDATE tasks SET status = ?, completed_at = ?
                WHERE id = ? AND session_id = ?
            """, (TaskStatus.FAILED.value, now, task_id, self.session_id))

        self._rebuild_blocked_cache()

    def get_task(self, task_id: str) -> Optional[BeadsTask]:
        """Get a single task by ID.

        Args:
            task_id: Task ID to lookup

        Returns:
            BeadsTask if found, None otherwise
        """
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT * FROM tasks
                WHERE id = ? AND session_id = ?
            """, (task_id, self.session_id)).fetchone()

            if row is None:
                return None

            return BeadsTask(
                id=row["id"],
                description=row["description"],
                status=TaskStatus(row["status"]),
                created_at=datetime.fromtimestamp(row["created_at"], tz=timezone.utc),
                completed_at=datetime.fromtimestamp(row["completed_at"], tz=timezone.utc) if row["completed_at"] else None,
                is_wisp=bool(row["is_wisp"]),
                metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            )

    def get_dependencies(self, task_id: str) -> dict[str, Any]:
        """Get all dependencies for a task."""
        result: dict[str, Any] = {
            "blocks": [],
            "conditional_blocks": [],
            "waits_for": [],
            "parent": None,
            "related": [],
            "discovered_from": None,
        }

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT from_task, dep_type FROM dependencies
                WHERE session_id = ? AND to_task = ?
            """, (self.session_id, task_id)).fetchall()

            for row in rows:
                dep_type = row["dep_type"]
                from_task = row["from_task"]

                if dep_type == "parent_child":
                    result["parent"] = from_task
                elif dep_type == "discovered_from":
                    result["discovered_from"] = from_task
                elif dep_type in result:
                    result[dep_type].append(from_task)

        return result

    def get_children(self, task_id: str) -> list[str]:
        """Get child tasks of a parent task."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT to_task FROM dependencies
                WHERE session_id = ? AND from_task = ? AND dep_type = 'parent_child'
            """, (self.session_id, task_id)).fetchall()
            return [row["to_task"] for row in rows]

    def get_ready_tasks(self) -> list[str]:
        """Get all tasks that are ready to execute (O(1) via blocked cache)."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT id FROM tasks
                WHERE session_id = ? AND status = 'pending' AND is_wisp = FALSE
            """, (self.session_id,)).fetchall()

            return [row["id"] for row in rows if row["id"] not in self._blocked_cache]

    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get all non-wisp tasks."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM tasks
                WHERE session_id = ? AND is_wisp = FALSE
                ORDER BY created_at ASC
            """, (self.session_id,)).fetchall()

            return [
                {
                    "id": row["id"],
                    "description": row["description"],
                    "status": row["status"],
                    "created_at": datetime.fromtimestamp(row["created_at"], tz=timezone.utc),
                    "completed_at": datetime.fromtimestamp(row["completed_at"], tz=timezone.utc) if row["completed_at"] else None,
                    "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
                }
                for row in rows
            ]

    def _rebuild_blocked_cache(self) -> None:
        """Rebuild the blocked cache."""
        self._blocked_cache.clear()

        with self._get_conn() as conn:
            # Get all pending tasks
            pending = conn.execute("""
                SELECT id FROM tasks
                WHERE session_id = ? AND status = 'pending' AND is_wisp = FALSE
            """, (self.session_id,)).fetchall()
            pending_ids = {row["id"] for row in pending}

            # Get all incomplete blockers for each pending task
            for task_id in pending_ids:
                rows = conn.execute("""
                    SELECT d.from_task, t.status
                    FROM dependencies d
                    JOIN tasks t ON d.from_task = t.id
                    WHERE d.session_id = ? AND d.to_task = ? AND d.dep_type = 'blocks'
                """, (self.session_id, task_id)).fetchall()

                for row in rows:
                    if row["status"] != TaskStatus.COMPLETED.value:
                        self._blocked_cache.add(task_id)
                        break
