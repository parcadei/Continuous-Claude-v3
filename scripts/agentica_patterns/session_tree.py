"""Tree-based session management with branching.

Enables exploring alternative conversation paths while preserving full history.
No summary chaining - branches are full copies with UUID-linked entries.

Usage:
    tree = SessionTree(session_id="abc123")

    # Add messages to current branch
    tree.add_message("user", "Hello")
    tree.add_message("assistant", "Hi there!")

    # Fork to explore alternative
    branch_id = tree.fork("experiment-async", "Testing async approach")

    # Switch between branches
    tree.switch(branch_id)
    tree.switch("main")

    # Get messages for current branch (walks tree to root)
    messages = tree.get_branch_messages()
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4


def generate_entry_id() -> str:
    """Generate a UUID-based entry ID."""
    return f"se-{uuid4().hex[:12]}"


@dataclass
class SessionEntry:
    """An entry in the session tree."""

    id: str
    session_id: str
    type: Literal["session", "message", "branch", "model_change"]
    parent_id: Optional[str]
    timestamp: datetime

    # Message-specific
    role: Optional[str] = None
    content: Optional[str] = None
    usage: Optional[dict[str, Any]] = None

    # Branch-specific
    branch_name: Optional[str] = None
    branch_description: Optional[str] = None


@dataclass
class Branch:
    """A branch in the session tree."""

    id: str
    session_id: str
    name: str
    description: Optional[str]
    parent_branch_id: Optional[str]
    created_at: datetime
    is_active: bool = False


class SessionTree:
    """Tree-based session manager with branching and navigation.

    Key operations:
    - add_message(): Add message to current branch
    - fork(): Create a branch from current position
    - switch(): Navigate to a different branch
    - get_branch_messages(): Get all messages in current branch's lineage
    """

    def __init__(
        self,
        session_id: str,
        db_path: Optional[Path] = None,
    ):
        """Initialize session tree.

        Args:
            session_id: Session identifier (from CoordinationDB)
            db_path: Optional custom database path
        """
        self.session_id = session_id

        # Default path in cache directory (shared with MemoryService)
        if db_path is None:
            import os

            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            cache_dir = Path(project_dir) / ".claude" / "cache" / "agentica-memory"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = cache_dir / "memory.db"

        self._db_path = db_path
        self._current_branch_id: Optional[str] = None
        self._init_schema()
        self._ensure_main_branch()

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
        """Initialize session tree schema."""
        schema_path = Path(__file__).parent / "session_tree_schema.sql"
        if schema_path.exists():
            with self._get_conn() as conn:
                conn.executescript(schema_path.read_text())
        else:
            # Inline schema if file not found
            with self._get_conn() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS session_entries (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        branch_id TEXT,
                        type TEXT NOT NULL,
                        parent_id TEXT,
                        timestamp REAL NOT NULL,
                        role TEXT,
                        content TEXT,
                        usage_json TEXT,
                        branch_name TEXT,
                        branch_description TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_se_session ON session_entries(session_id);
                    CREATE INDEX IF NOT EXISTS idx_se_parent ON session_entries(parent_id);
                    CREATE INDEX IF NOT EXISTS idx_se_branch ON session_entries(branch_id);

                    CREATE TABLE IF NOT EXISTS branches (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        parent_branch_id TEXT,
                        fork_point_id TEXT,
                        created_at REAL NOT NULL,
                        is_active BOOLEAN DEFAULT FALSE
                    );
                    CREATE INDEX IF NOT EXISTS idx_br_session ON branches(session_id);
                """
                )

    def _ensure_main_branch(self):
        """Ensure main branch exists for this session."""
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM branches WHERE session_id = ? AND name = 'main'",
                (self.session_id,),
            ).fetchone()

            if not existing:
                # Create main branch
                branch_id = generate_entry_id()
                now = datetime.now(timezone.utc).timestamp()

                conn.execute(
                    """
                    INSERT INTO branches (id, session_id, name, description, parent_branch_id, fork_point_id, created_at, is_active)
                    VALUES (?, ?, 'main', 'Main conversation branch', NULL, NULL, ?, TRUE)
                """,
                    (branch_id, self.session_id, now),
                )

                # Create root session entry
                conn.execute(
                    """
                    INSERT INTO session_entries (id, session_id, branch_id, type, parent_id, timestamp, branch_name)
                    VALUES (?, ?, ?, 'session', NULL, ?, 'main')
                """,
                    (branch_id, self.session_id, branch_id, now),
                )

                self._current_branch_id = branch_id
            else:
                self._current_branch_id = existing["id"]
                # Mark as active
                conn.execute(
                    "UPDATE branches SET is_active = FALSE WHERE session_id = ?",
                    (self.session_id,),
                )
                conn.execute(
                    "UPDATE branches SET is_active = TRUE WHERE id = ?",
                    (self._current_branch_id,),
                )

    @property
    def current_branch_id(self) -> str:
        """Get current branch ID."""
        if self._current_branch_id is None:
            raise RuntimeError("Branch ID not initialized")
        return self._current_branch_id

    @property
    def current_branch_name(self) -> str:
        """Get current branch name."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT name FROM branches WHERE id = ?", (self._current_branch_id,)
            ).fetchone()
            return row["name"] if row else "main"

    def add_message(
        self,
        role: str,
        content: str,
        usage: Optional[dict[str, Any]] = None,
    ) -> str:
        """Add a message to the current branch.

        Args:
            role: Message role (user, assistant, toolResult)
            content: Message content
            usage: Optional token usage stats

        Returns:
            Entry ID of the new message
        """
        entry_id = generate_entry_id()
        now = datetime.now(timezone.utc).timestamp()

        # Find current tip (most recent entry in this branch)
        parent_id = self._get_current_tip()

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO session_entries (id, session_id, branch_id, type, parent_id, timestamp, role, content, usage_json)
                VALUES (?, ?, ?, 'message', ?, ?, ?, ?, ?)
            """,
                (
                    entry_id,
                    self.session_id,
                    self._current_branch_id,
                    parent_id,
                    now,
                    role,
                    content,
                    json.dumps(usage) if usage else None,
                ),
            )

        return entry_id

    def fork(
        self,
        branch_name: str,
        description: str = "",
    ) -> str:
        """Create a new branch from the current position.

        Args:
            branch_name: Human-readable branch name
            description: Why this branch was created

        Returns:
            Branch ID for switching
        """
        branch_id = generate_entry_id()
        now = datetime.now(timezone.utc).timestamp()
        parent_tip = self._get_current_tip()

        with self._get_conn() as conn:
            # Create branch record - store the fork point
            conn.execute(
                """
                INSERT INTO branches (id, session_id, name, description, parent_branch_id, fork_point_id, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)
            """,
                (
                    branch_id,
                    self.session_id,
                    branch_name,
                    description,
                    self._current_branch_id,
                    parent_tip,  # Store the fork point
                    now,
                ),
            )

            # Create branch entry in tree - belongs to the NEW branch
            conn.execute(
                """
                INSERT INTO session_entries (id, session_id, branch_id, type, parent_id, timestamp, branch_name, branch_description)
                VALUES (?, ?, ?, 'branch', ?, ?, ?, ?)
            """,
                (
                    branch_id,
                    self.session_id,
                    branch_id,  # The branch entry belongs to the new branch
                    parent_tip,
                    now,
                    branch_name,
                    description,
                ),
            )

        # Switch to new branch
        self.switch(branch_id)

        return branch_id

    def switch(self, branch_id_or_name: str) -> None:
        """Switch to a different branch.

        Args:
            branch_id_or_name: Branch ID or name to switch to
        """
        with self._get_conn() as conn:
            # Try by ID first, then by name
            row = conn.execute(
                "SELECT id FROM branches WHERE session_id = ? AND (id = ? OR name = ?)",
                (self.session_id, branch_id_or_name, branch_id_or_name),
            ).fetchone()

            if not row:
                raise ValueError(f"Branch '{branch_id_or_name}' not found")

            # Update active status
            conn.execute(
                "UPDATE branches SET is_active = FALSE WHERE session_id = ?",
                (self.session_id,),
            )
            conn.execute(
                "UPDATE branches SET is_active = TRUE WHERE id = ?",
                (row["id"],),
            )

            self._current_branch_id = row["id"]

    def list_branches(self) -> list[Branch]:
        """List all branches for this session.

        Returns:
            List of Branch objects
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM branches
                WHERE session_id = ?
                ORDER BY created_at ASC
            """,
                (self.session_id,),
            ).fetchall()

        return [
            Branch(
                id=row["id"],
                session_id=row["session_id"],
                name=row["name"],
                description=row["description"],
                parent_branch_id=row["parent_branch_id"],
                created_at=datetime.fromtimestamp(row["created_at"], tz=timezone.utc),
                is_active=bool(row["is_active"]),
            )
            for row in rows
        ]

    def get_branch_messages(
        self, branch_id: Optional[str] = None
    ) -> list[SessionEntry]:
        """Get all messages in a branch's lineage.

        Walks up the tree from branch tip to root, collecting messages.

        Args:
            branch_id: Branch to get messages for (default: current branch)

        Returns:
            List of SessionEntry objects (oldest to newest)
        """
        target_branch = branch_id or self._current_branch_id
        messages = []

        with self._get_conn() as conn:
            # Find tip of target branch - only entries that belong to this branch
            tip_id = self._get_branch_tip(conn, target_branch)

            # Walk up the tree
            current_id = tip_id
            while current_id:
                row = conn.execute(
                    "SELECT * FROM session_entries WHERE id = ?",
                    (current_id,),
                ).fetchone()

                if not row:
                    break

                if row["type"] == "message":
                    messages.append(
                        SessionEntry(
                            id=row["id"],
                            session_id=row["session_id"],
                            type=row["type"],
                            parent_id=row["parent_id"],
                            timestamp=datetime.fromtimestamp(
                                row["timestamp"], tz=timezone.utc
                            ),
                            role=row["role"],
                            content=row["content"],
                            usage=json.loads(row["usage_json"])
                            if row["usage_json"]
                            else None,
                        )
                    )

                current_id = row["parent_id"]

        return list(reversed(messages))

    def get_message_count(self, branch_id: Optional[str] = None) -> int:
        """Get count of messages in a branch's lineage."""
        return len(self.get_branch_messages(branch_id))

    def _get_current_tip(self) -> str:
        """Get the ID of the most recent entry in current branch."""
        with self._get_conn() as conn:
            return self._get_branch_tip(conn, self._current_branch_id)

    def _get_branch_tip(self, conn: sqlite3.Connection, branch_id: str) -> str:
        """Get the tip (most recent entry) of a branch.

        The tip is the most recent entry that:
        1. Belongs to this branch (branch_id matches), OR
        2. Is an ancestor that this branch inherits from

        We find the most recent entry belonging to this branch,
        or if none, use the fork point.
        """
        # First, check if there are any entries that belong directly to this branch
        row = conn.execute(
            """
            SELECT id FROM session_entries
            WHERE session_id = ? AND branch_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            (self.session_id, branch_id),
        ).fetchone()

        if row:
            return row["id"]

        # No entries in this branch yet, use the fork point from the branch record
        branch_row = conn.execute(
            "SELECT fork_point_id FROM branches WHERE id = ?",
            (branch_id,),
        ).fetchone()

        if branch_row and branch_row["fork_point_id"]:
            return branch_row["fork_point_id"]

        # Fallback to branch_id itself (for main branch root)
        return branch_id

    def to_context(self, max_messages: int = 50) -> str:
        """Generate context string for prompt injection.

        Args:
            max_messages: Maximum messages to include

        Returns:
            Formatted context string
        """
        messages = self.get_branch_messages()[-max_messages:]
        branches = self.list_branches()

        lines = [
            f"## Session Branch: {self.current_branch_name}",
            f"Branch ID: {self._current_branch_id}",
            f"Total Branches: {len(branches)}",
            "",
        ]

        if len(branches) > 1:
            lines.append("Available Branches:")
            for b in branches:
                marker = " (active)" if b.is_active else ""
                lines.append(f"- {b.name}{marker}")
            lines.append("")

        lines.append(f"Recent Messages: {len(messages)}")

        return "\n".join(lines)
