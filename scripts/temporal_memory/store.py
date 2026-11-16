"""Temporal Memory Store - SQLite-backed temporal fact storage."""
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import aiosqlite

from scripts.temporal_memory.inertia import (
    RevisionEvent,
    RevisionPriority,
    resolve_conflict,
)
from scripts.z3_erotetic import check_evocation


class TemporalMemoryStore:
    """Store for temporal facts and trace data.

    This class manages a SQLite database for storing temporal facts that
    evolve over turns in a Claude Code session. It tracks:
    - Facts with their values and when they were established/changed
    - Temporal trace snapshots for each turn

    Attributes:
        session_id: Unique identifier for this session
        _db_path: Path to the SQLite database file
        _connected: Whether the store has been connected
        _current_turn: Current turn number (starts at 0)

    Example:
        >>> store = TemporalMemoryStore(session_id="abc123")
        >>> await store.connect()
        >>> # Now ready to store/retrieve temporal facts
    """

    def __init__(self, session_id: str, db_path: Optional[Path] = None):
        """Initialize the temporal memory store.

        Args:
            session_id: Unique identifier for this session
            db_path: Path to SQLite database (default: .claude/cache/temporal-memory/temporal.db)
        """
        self.session_id = session_id
        if db_path is None:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            cache_dir = Path(project_dir) / ".claude" / "cache" / "temporal-memory"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = cache_dir / "temporal.db"
        self._db_path = db_path
        self._connected = False
        self._current_turn = 0

    @asynccontextmanager
    async def _get_conn(self):
        """Get a database connection with WAL mode enabled.

        Yields:
            An aiosqlite connection configured with WAL mode and row factory.
        """
        conn = await aiosqlite.connect(str(self._db_path))
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
            await conn.commit()
        finally:
            await conn.close()

    async def connect(self) -> None:
        """Initialize connection and create schema if needed.

        This method is idempotent - calling it multiple times has no effect
        after the first successful connection. After connecting, restores
        the current turn from the database to maintain continuity.
        """
        if self._connected:
            return
        await self._init_schema()
        await self._restore_current_turn()
        self._connected = True

    async def _restore_current_turn(self) -> None:
        """Restore _current_turn from the database.

        Queries the temporal_trace table for the maximum turn number
        for this session and sets _current_turn accordingly.
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT MAX(turn) as max_turn FROM temporal_trace WHERE session_id = ?",
                (self.session_id,)
            )
            row = await cursor.fetchone()
            if row and row["max_turn"] is not None:
                self._current_turn = row["max_turn"]

    async def _init_schema(self) -> None:
        """Create database tables and indexes.

        Creates the following tables:
        - temporal_facts: Stores facts with temporal metadata
        - temporal_trace: Stores turn-by-turn snapshots

        Also creates indexes for efficient session-based queries.
        """
        async with self._get_conn() as conn:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS temporal_facts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    turn_established INTEGER NOT NULL,
                    turn_last_changed INTEGER NOT NULL,
                    change_count INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 1.0,
                    created_at REAL NOT NULL,
                    UNIQUE(session_id, key)
                );

                CREATE TABLE IF NOT EXISTS temporal_trace (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    facts_json TEXT NOT NULL,
                    erotetic_json TEXT,
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_temporal_facts_session
                    ON temporal_facts(session_id, turn_established);
                CREATE INDEX IF NOT EXISTS idx_temporal_trace_session
                    ON temporal_trace(session_id, turn);
            """)

    async def record(self, turn: int, facts: dict[str, Any]) -> None:
        """Record facts at a turn.

        This method stores facts in both the trace table (for historical
        playback) and the facts table (for current state tracking). It
        automatically tracks when facts change.

        Args:
            turn: Turn number for this recording
            facts: Dictionary of key-value facts to record

        Example:
            >>> await store.record(turn=1, facts={"phase": "testing"})
            >>> await store.record(turn=2, facts={"phase": "done"})
            >>> # change_count for "phase" is now 1
        """
        self._current_turn = max(self._current_turn, turn)
        now = datetime.now(timezone.utc).timestamp()
        trace_id = f"trace-{uuid4().hex[:12]}"

        async with self._get_conn() as conn:
            # Store trace snapshot
            await conn.execute(
                """INSERT INTO temporal_trace (id, session_id, turn, facts_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (trace_id, self.session_id, turn, json.dumps(facts), now)
            )

            # Update temporal_facts
            for key, value in facts.items():
                existing = await conn.execute(
                    "SELECT * FROM temporal_facts WHERE session_id = ? AND key = ?",
                    (self.session_id, key)
                )
                row = await existing.fetchone()

                if row:
                    # Update existing fact
                    if str(row["value"]) != str(value):
                        await conn.execute(
                            """UPDATE temporal_facts
                               SET value = ?, turn_last_changed = ?, change_count = change_count + 1
                               WHERE session_id = ? AND key = ?""",
                            (str(value), turn, self.session_id, key)
                        )
                else:
                    # Insert new fact
                    fact_id = f"fact-{uuid4().hex[:12]}"
                    await conn.execute(
                        """INSERT INTO temporal_facts
                           (id, session_id, key, value, turn_established, turn_last_changed, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (fact_id, self.session_id, key, str(value), turn, turn, now)
                    )

    async def get_trace(self) -> list[dict[str, Any]]:
        """Get full temporal trace ordered by turn.

        Returns a list of trace entries, each containing the turn number,
        facts recorded at that turn, and any erotetic (question) data.

        Returns:
            List of trace entries ordered by turn number.

        Example:
            >>> trace = await store.get_trace()
            >>> for entry in trace:
            ...     print(f"Turn {entry['turn']}: {entry['facts']}")
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT turn, facts_json, erotetic_json FROM temporal_trace WHERE session_id = ? ORDER BY turn",
                (self.session_id,)
            )
            rows = await cursor.fetchall()
            return [
                {
                    "turn": row["turn"],
                    "facts": json.loads(row["facts_json"]),
                    "erotetic": json.loads(row["erotetic_json"]) if row["erotetic_json"] else None
                }
                for row in rows
            ]

    async def get_current_state(self) -> dict[str, Any]:
        """Get current values of all facts.

        Returns the latest value for each fact key, regardless of when
        it was last changed.

        Returns:
            Dictionary mapping fact keys to their current values.

        Example:
            >>> await store.record(turn=1, facts={"a": "1", "b": "2"})
            >>> await store.record(turn=2, facts={"a": "updated"})
            >>> state = await store.get_current_state()
            >>> state == {"a": "updated", "b": "2"}
            True
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT key, value FROM temporal_facts WHERE session_id = ?",
                (self.session_id,)
            )
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}

    async def get_invariants(self) -> dict[str, Any]:
        """Get facts that never changed (change_count == 0).

        Invariants are facts that were established once and never modified.
        These represent stable aspects of the session state.

        Returns:
            Dictionary mapping invariant fact keys to their values.

        Example:
            >>> await store.record(turn=1, facts={"db_type": "sqlite", "phase": "init"})
            >>> await store.record(turn=2, facts={"phase": "running"})
            >>> invariants = await store.get_invariants()
            >>> "db_type" in invariants  # Never changed
            True
            >>> "phase" in invariants  # Changed once
            False
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT key, value FROM temporal_facts WHERE session_id = ? AND change_count = 0",
                (self.session_id,)
            )
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}

    async def record_with_erotetic(self, turn: int, facts: dict[str, Any]) -> dict[str, Any]:
        """Record facts and compute E(X,Q) evocation.

        This method extends record() by also computing the erotetic evocation,
        which identifies which propositions are UNKNOWN (not entailed by context).

        Args:
            turn: Turn number
            facts: Dictionary of key-value facts

        Returns:
            Evocation result: {"isEmpty": bool, "unknowns": list, "count": int}

        Example:
            >>> result = await store.record_with_erotetic(
            ...     turn=1,
            ...     facts={"db": "postgres", "auth": "UNKNOWN"}
            ... )
            >>> result["isEmpty"]
            False
            >>> result["unknowns"]
            ["auth"]
        """
        await self.record(turn, facts)
        evocation = check_evocation(facts)

        async with self._get_conn() as conn:
            await conn.execute(
                """UPDATE temporal_trace SET erotetic_json = ?
                   WHERE session_id = ? AND turn = ?""",
                (json.dumps(evocation), self.session_id, turn)
            )

        return evocation

    async def get_open_questions(self, turn: Optional[int] = None) -> list[str]:
        """Get E(X,Q) unknowns at a turn.

        Returns the list of proposition names that were marked as UNKNOWN
        at the specified turn (or the latest turn if not specified).

        Args:
            turn: Specific turn number, or None for latest

        Returns:
            List of unknown proposition names

        Example:
            >>> await store.record_with_erotetic(turn=1, facts={"db": "UNKNOWN"})
            >>> await store.get_open_questions()
            ["db"]
            >>> await store.record_with_erotetic(turn=2, facts={"db": "postgres"})
            >>> await store.get_open_questions()
            []
        """
        async with self._get_conn() as conn:
            if turn is None:
                cursor = await conn.execute(
                    """SELECT erotetic_json FROM temporal_trace
                       WHERE session_id = ? ORDER BY turn DESC LIMIT 1""",
                    (self.session_id,)
                )
            else:
                cursor = await conn.execute(
                    """SELECT erotetic_json FROM temporal_trace
                       WHERE session_id = ? AND turn = ?""",
                    (self.session_id, turn)
                )
            row = await cursor.fetchone()
            if row and row["erotetic_json"]:
                erotetic = json.loads(row["erotetic_json"])
                return erotetic.get("unknowns", [])
            return []

    async def advance_turn(
        self,
        updates: dict[str, Any],
        priority: RevisionPriority = RevisionPriority.RECENT_OBSERVATION,
    ) -> list[RevisionEvent]:
        """
        Advance to next turn with updates.

        Applies inertia rule: persisted facts + updates.
        Returns any revision events (conflicts resolved).

        This method implements the TEL inertia rule:
            holds(P, T+1) :- holds(P, T), not -holds(P, T+1)

        Facts persist unless explicitly updated. When updating an existing
        fact, the priority hierarchy determines which value wins:
            EXPLICIT_NEGATION > RECENT_OBSERVATION > INVARIANT > HISTORICAL

        Args:
            updates: Dictionary of key-value pairs to update
            priority: Priority level for the updates (default: RECENT_OBSERVATION)

        Returns:
            List of RevisionEvent objects for any conflicts that were resolved

        Example:
            >>> await store.record(turn=1, facts={"db": "sqlite", "phase": "planning"})
            >>> revisions = await store.advance_turn(updates={"phase": "testing"})
            >>> # db persists via inertia, phase is updated
            >>> state = await store.get_current_state()
            >>> state == {"db": "sqlite", "phase": "testing"}
            True
        """
        self._current_turn += 1
        current = await self.get_current_state()
        revisions: list[RevisionEvent] = []

        for key, new_value in updates.items():
            if key in current:
                old_value = current[key]
                old_priority = await self._get_fact_priority(key)
                old_confidence = await self._get_fact_confidence(key)

                winner, event = resolve_conflict(
                    key,
                    old_value,
                    old_priority,
                    old_confidence,
                    new_value,
                    priority,
                    self._current_turn,
                )

                if event:
                    revisions.append(event)
                current[key] = winner
            else:
                current[key] = new_value

        await self.record(self._current_turn, current)
        return revisions

    async def _get_fact_priority(self, key: str) -> RevisionPriority:
        """Get the priority level of an existing fact.

        Facts with change_count == 0 are considered INVARIANT.
        Facts that have been changed are considered HISTORICAL.

        Args:
            key: The fact key to look up

        Returns:
            RevisionPriority for the fact
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT change_count FROM temporal_facts WHERE session_id = ? AND key = ?",
                (self.session_id, key),
            )
            row = await cursor.fetchone()
            if row and row["change_count"] == 0:
                return RevisionPriority.INVARIANT
            return RevisionPriority.HISTORICAL

    async def _get_fact_confidence(self, key: str) -> float:
        """Get the confidence level of an existing fact.

        Args:
            key: The fact key to look up

        Returns:
            Confidence value (default 1.0 if not found)
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT confidence FROM temporal_facts WHERE session_id = ? AND key = ?",
                (self.session_id, key),
            )
            row = await cursor.fetchone()
            return row["confidence"] if row else 1.0
