"""Write extracted facts to temporal.db.

Phase 3.5 of backfill pipeline.

Writes facts extracted from Braintrust spans to temporal.db with:
- Calibrated confidence scores based on session outcomes
- Content hash deduplication (idempotent writes)
- Turn-level trace snapshots
- WAL mode for concurrency

Schema created:
    temporal_facts - Individual facts with calibrated confidence
    temporal_traces - Turn-level trace snapshots
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from scripts.backfill.outcome_tagger import SessionOutcome
from scripts.backfill.span_parser import SpanFact

# Schema for temporal facts table
TEMPORAL_FACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS temporal_facts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    turn INTEGER,
    confidence REAL DEFAULT 1.0,
    content_hash TEXT UNIQUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_temporal_facts_session ON temporal_facts(session_id);
CREATE INDEX IF NOT EXISTS idx_temporal_facts_hash ON temporal_facts(content_hash);
"""

# Schema for temporal traces table
TEMPORAL_TRACES_SCHEMA = """
CREATE TABLE IF NOT EXISTS temporal_traces (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    fact_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_temporal_traces_session ON temporal_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_temporal_traces_turn ON temporal_traces(session_id, turn);
"""


class TemporalWriter:
    """Write facts to temporal.db with calibration.

    Uses aiosqlite for async SQLite access with WAL mode for concurrency.
    Supports content hash deduplication for idempotent writes.
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize TemporalWriter.

        Args:
            db_path: Path to temporal.db. Defaults to
                .claude/cache/temporal-memory/temporal.db
        """
        self.db_path = db_path or Path(".claude/cache/temporal-memory/temporal.db")
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize database connection and schema.

        Creates the database file and parent directories if they don't exist.
        Enables WAL mode for better concurrency.
        """
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Open connection with WAL mode and busy timeout
        self._conn = await aiosqlite.connect(
            self.db_path,
            timeout=30.0,  # 30 second busy timeout
        )
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for better concurrency
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA busy_timeout=30000")

        # Create schema
        await self._conn.executescript(TEMPORAL_FACTS_SCHEMA)
        await self._conn.executescript(TEMPORAL_TRACES_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def write_facts(
        self,
        session_id: str,
        facts: list[SpanFact],
        outcome: SessionOutcome,
    ) -> int:
        """Write facts with calibrated confidence.

        Args:
            session_id: Root span ID of the session
            facts: List of SpanFact objects to write
            outcome: SessionOutcome with confidence multiplier

        Returns:
            Number of facts written (excluding duplicates)
        """
        if not facts:
            return 0

        if self._conn is None:
            raise RuntimeError("Database connection not initialized. Call connect() first.")

        written_count = 0

        # Write all facts in a single transaction
        async with self._conn.execute("BEGIN"):
            for fact in facts:
                # Compute calibrated confidence
                calibrated_confidence = fact.confidence * outcome.confidence_multiplier

                # Ensure content hash exists
                content_hash = fact.content_hash or self._compute_content_hash(fact)

                # Generate unique ID
                fact_id = str(uuid.uuid4())

                try:
                    await self._conn.execute(
                        """
                        INSERT OR IGNORE INTO temporal_facts
                        (id, session_id, key, value, turn, confidence, content_hash, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fact_id,
                            session_id,
                            fact.key,
                            fact.value,
                            fact.turn,
                            calibrated_confidence,
                            content_hash,
                            datetime.now(UTC).isoformat(),
                        ),
                    )

                    # Check if row was actually inserted (not a duplicate)
                    if self._conn.total_changes > 0:
                        cursor = await self._conn.execute("SELECT changes()")
                        row = await cursor.fetchone()
                        if row and row[0] > 0:
                            written_count += 1

                except aiosqlite.IntegrityError:
                    # Duplicate content_hash - skip silently (idempotent)
                    pass

            await self._conn.commit()

        return written_count

    async def write_traces(
        self,
        session_id: str,
        facts_by_turn: dict[int, list[SpanFact]],
        outcome: SessionOutcome,
    ) -> int:
        """Write turn-level trace snapshots.

        Args:
            session_id: Root span ID of the session
            facts_by_turn: Dictionary mapping turn number to list of facts
            outcome: SessionOutcome with confidence multiplier

        Returns:
            Number of trace entries written
        """
        if not facts_by_turn:
            return 0

        if self._conn is None:
            raise RuntimeError("Database connection not initialized. Call connect() first.")

        written_count = 0

        async with self._conn.execute("BEGIN"):
            for turn, facts in facts_by_turn.items():
                trace_id = str(uuid.uuid4())
                calibrated_confidence = outcome.confidence_multiplier

                await self._conn.execute(
                    """
                    INSERT INTO temporal_traces
                    (id, session_id, turn, fact_count, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trace_id,
                        session_id,
                        turn,
                        len(facts),
                        calibrated_confidence,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                written_count += 1

            await self._conn.commit()

        return written_count

    async def get_facts(self, session_id: str) -> list[dict[str, Any]]:
        """Get all facts for a session.

        Args:
            session_id: Root span ID of the session

        Returns:
            List of fact dictionaries
        """
        if self._conn is None:
            raise RuntimeError("Database connection not initialized. Call connect() first.")

        cursor = await self._conn.execute(
            """
            SELECT id, session_id, key, value, turn, confidence, content_hash, created_at
            FROM temporal_facts
            WHERE session_id = ?
            ORDER BY turn, created_at
            """,
            (session_id,),
        )

        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_traces(self, session_id: str) -> list[dict[str, Any]]:
        """Get all traces for a session.

        Args:
            session_id: Root span ID of the session

        Returns:
            List of trace dictionaries
        """
        if self._conn is None:
            raise RuntimeError("Database connection not initialized. Call connect() first.")

        cursor = await self._conn.execute(
            """
            SELECT id, session_id, turn, fact_count, confidence, created_at
            FROM temporal_traces
            WHERE session_id = ?
            ORDER BY turn
            """,
            (session_id,),
        )

        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    def _compute_content_hash(self, fact: SpanFact) -> str:
        """Compute hash for deduplication (excludes timestamp).

        Hash is based on key:value:turn which allows same facts
        to be deduplicated across multiple processing runs.
        """
        content = f"{fact.key}:{fact.value}:{fact.turn}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
