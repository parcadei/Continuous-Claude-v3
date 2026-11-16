"""Temporal Memory Store - PostgreSQL-backed temporal fact storage.

Phase 3.3 of PostgreSQL migration - PostgreSQL version of TemporalMemoryStore.

Stores temporal facts that evolve over turns in a Claude Code session with:
- Turn tracking (turn_established, turn_last_changed)
- Change tracking (change_count)
- Temporal trace snapshots with JSONB
- Erotetic (E(X,Q)) integration
- Inertia rule for belief persistence

Uses asyncpg connection pool for true async/await.
Schema created by Phase 3.1 (docker/init.sql).

Key differences from SQLite version:
- Uses asyncpg instead of aiosqlite
- Uses pool connection management from postgres_pool.py
- Uses IS NOT DISTINCT FROM for NULL comparisons
- Uses JSONB instead of TEXT for JSON columns
- Uses TIMESTAMPTZ for timestamps
- DELETE + INSERT pattern for upserts (unique constraint on session_id+key)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

from scripts.agentica_patterns.postgres_pool import (
    get_connection,
    get_transaction,
    init_pgvector,
)
from scripts.temporal_memory.inertia import (
    RevisionEvent,
    RevisionPriority,
    resolve_conflict,
)
from scripts.z3_erotetic import check_evocation


class TemporalMemoryStorePG:
    """Store for temporal facts with PostgreSQL backend.

    This class manages a PostgreSQL database for storing temporal facts that
    evolve over turns in a Claude Code session. It tracks:
    - Facts with their values and when they were established/changed
    - Temporal trace snapshots for each turn

    Attributes:
        session_id: Unique identifier for this session
        _connected: Whether the store has been connected
        _current_turn: Current turn number (starts at 0)

    Example:
        >>> store = TemporalMemoryStorePG(session_id="abc123")
        >>> await store.connect()
        >>> # Now ready to store/retrieve temporal facts
    """

    def __init__(self, session_id: str):
        """Initialize the temporal memory store.

        Args:
            session_id: Unique identifier for this session
        """
        self.session_id = session_id
        self._connected = False
        self._current_turn = 0

    async def connect(self) -> None:
        """Initialize connection and restore state.

        This method is idempotent - calling it multiple times has no effect
        after the first successful connection. After connecting, restores
        the current turn from the database to maintain continuity.

        Note: Tables should already exist (created by Phase 3.1 init.sql).
        """
        if self._connected:
            return
        await self._restore_current_turn()
        self._connected = True

    async def _restore_current_turn(self) -> None:
        """Restore _current_turn from the database.

        Queries the temporal_traces table for the maximum turn number
        for this session and sets _current_turn accordingly.
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT MAX(turn) as max_turn FROM temporal_traces
                WHERE session_id = $1
                """,
                self.session_id,
            )
            if row and row["max_turn"] is not None:
                self._current_turn = row["max_turn"]

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
        trace_id = str(uuid.uuid4())

        async with get_transaction() as conn:
            # Store trace snapshot
            await conn.execute(
                """
                INSERT INTO temporal_traces
                (id, session_id, turn, facts_json, erotetic_json, created_at)
                VALUES ($1, $2, $3, $4, NULL, NOW())
                """,
                trace_id,
                self.session_id,
                turn,
                json.dumps(facts),
            )

            # Update temporal_facts
            for key, value in facts.items():
                # Convert value to string for storage (matching SQLite behavior)
                # None becomes "None" string (DB has NOT NULL constraint on value)
                str_value = str(value)

                # Check if fact already exists
                row = await conn.fetchrow(
                    """
                    SELECT id, value, change_count FROM temporal_facts
                    WHERE session_id = $1 AND key = $2
                    """,
                    self.session_id,
                    key,
                )

                if row:
                    # Update existing fact - check if value changed
                    # Use IS NOT DISTINCT FROM for NULL-safe comparison
                    old_value = row["value"]
                    if old_value != str_value:
                        await conn.execute(
                            """
                            UPDATE temporal_facts
                            SET value = $1, turn_last_changed = $2, change_count = change_count + 1
                            WHERE session_id = $3 AND key = $4
                            """,
                            str_value,
                            turn,
                            self.session_id,
                            key,
                        )
                else:
                    # Insert new fact
                    fact_id = str(uuid.uuid4())
                    await conn.execute(
                        """
                        INSERT INTO temporal_facts
                        (id, session_id, key, value, turn_established, turn_last_changed, change_count, created_at)
                        VALUES ($1, $2, $3, $4, $5, $5, 0, NOW())
                        """,
                        fact_id,
                        self.session_id,
                        key,
                        str_value,
                        turn,
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
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT turn, facts_json, erotetic_json
                FROM temporal_traces
                WHERE session_id = $1
                ORDER BY turn
                """,
                self.session_id,
            )
            result = []
            for row in rows:
                facts_json = row["facts_json"]
                erotetic_json = row["erotetic_json"]

                # Handle JSONB - asyncpg returns dict directly for JSONB
                if isinstance(facts_json, str):
                    facts = json.loads(facts_json)
                else:
                    facts = facts_json

                if erotetic_json is not None:
                    if isinstance(erotetic_json, str):
                        erotetic = json.loads(erotetic_json)
                    else:
                        erotetic = erotetic_json
                else:
                    erotetic = None

                result.append({
                    "turn": row["turn"],
                    "facts": facts,
                    "erotetic": erotetic,
                })
            return result

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
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT key, value FROM temporal_facts
                WHERE session_id = $1
                """,
                self.session_id,
            )
            result = {}
            for row in rows:
                value = row["value"]
                # Convert "None" string back to None if needed
                if value == "None":
                    result[row["key"]] = None
                else:
                    result[row["key"]] = value
            return result

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
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT key, value FROM temporal_facts
                WHERE session_id = $1 AND change_count = 0
                """,
                self.session_id,
            )
            result = {}
            for row in rows:
                value = row["value"]
                if value == "None":
                    result[row["key"]] = None
                else:
                    result[row["key"]] = value
            return result

    async def record_with_erotetic(
        self, turn: int, facts: dict[str, Any]
    ) -> dict[str, Any]:
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

        async with get_connection() as conn:
            await conn.execute(
                """
                UPDATE temporal_traces SET erotetic_json = $1
                WHERE session_id = $2 AND turn = $3
                """,
                json.dumps(evocation),
                self.session_id,
                turn,
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
        async with get_connection() as conn:
            if turn is None:
                row = await conn.fetchrow(
                    """
                    SELECT erotetic_json FROM temporal_traces
                    WHERE session_id = $1
                    ORDER BY turn DESC
                    LIMIT 1
                    """,
                    self.session_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT erotetic_json FROM temporal_traces
                    WHERE session_id = $1 AND turn = $2
                    """,
                    self.session_id,
                    turn,
                )

            if row and row["erotetic_json"]:
                erotetic_json = row["erotetic_json"]
                # Handle JSONB - asyncpg returns dict directly for JSONB
                if isinstance(erotetic_json, str):
                    erotetic = json.loads(erotetic_json)
                else:
                    erotetic = erotetic_json
                return erotetic.get("unknowns", [])
            return []

    async def advance_turn(
        self,
        updates: dict[str, Any],
        priority: RevisionPriority = RevisionPriority.RECENT_OBSERVATION,
    ) -> list[RevisionEvent]:
        """Advance to next turn with updates.

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
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT change_count FROM temporal_facts
                WHERE session_id = $1 AND key = $2
                """,
                self.session_id,
                key,
            )
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
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT confidence FROM temporal_facts
                WHERE session_id = $1 AND key = $2
                """,
                self.session_id,
                key,
            )
            return row["confidence"] if row else 1.0

    def _pad_embedding(
        self, embedding: list[float], target_dim: int = 1024
    ) -> list[float]:
        """Pad or truncate embedding to target dimension.

        Using native Voyage dimension (1024) for pgvector compatibility.

        Args:
            embedding: Original embedding
            target_dim: Target dimension (default 1024)

        Returns:
            Padded/truncated embedding as list
        """
        vec = np.array(embedding)
        if len(vec) >= target_dim:
            return vec[:target_dim].tolist()
        return np.pad(vec, (0, target_dim - len(vec)), mode="constant").tolist()

    async def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search facts by vector similarity using pgvector.

        Uses cosine similarity (1 - cosine distance) for ranking.
        Only returns facts that have embeddings (non-NULL).
        Results are scoped to the current session.

        Args:
            query_embedding: Query embedding (will be padded to 1024 if needed)
            limit: Maximum number of results to return

        Returns:
            List of matching facts with similarity scores, ordered by
            descending similarity. Each dict contains:
            - key: Fact key
            - value: Fact value
            - confidence: Calibrated confidence score
            - similarity: Cosine similarity (0.0 to 1.0)

        Example:
            >>> results = await store.search_similar(
            ...     query_embedding=[0.1] * 128,
            ...     limit=5
            ... )
            >>> for r in results:
            ...     print(f"{r['key']}: {r['similarity']:.3f}")
        """
        # Pad query embedding to target dimension
        padded_query = self._pad_embedding(query_embedding)

        async with get_connection() as conn:
            # Initialize pgvector for this connection
            await init_pgvector(conn)

            # Support cross-session search when session_id is None
            if self.session_id is None:
                rows = await conn.fetch(
                    """
                    SELECT
                        key,
                        value,
                        confidence,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM temporal_facts
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                    """,
                    padded_query,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT
                        key,
                        value,
                        confidence,
                        1 - (embedding <=> $2::vector) as similarity
                    FROM temporal_facts
                    WHERE session_id = $1
                    AND embedding IS NOT NULL
                    ORDER BY embedding <=> $2::vector
                    LIMIT $3
                    """,
                    self.session_id,
                    padded_query,
                    limit,
                )

            return [
                {
                    "key": row["key"],
                    "value": row["value"],
                    "confidence": row["confidence"],
                    "similarity": row["similarity"],
                }
                for row in rows
            ]
