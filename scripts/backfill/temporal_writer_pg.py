"""Write extracted facts to PostgreSQL.

Phase 3.2 of PostgreSQL migration - PostgreSQL version of TemporalWriter.

Writes facts extracted from Braintrust spans to PostgreSQL with:
- Calibrated confidence scores based on session outcomes
- Content hash deduplication (idempotent writes via ON CONFLICT DO NOTHING)
- Turn-level trace snapshots
- Connection pooling via postgres_pool.py
- Vector embeddings for semantic search (Phase 3.6)

Schema (created by Phase 3.1):
    temporal_facts - Individual facts with calibrated confidence
    temporal_traces - Turn-level trace snapshots
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Union

import numpy as np

from scripts.agentica_patterns.postgres_pool import (
    get_connection,
    get_transaction,
    init_pgvector,
)
from scripts.backfill.outcome_tagger import SessionOutcome
from scripts.backfill.span_parser import SpanFact

# Target embedding dimension for pgvector column
# Voyage voyage-3 outputs 1024 dimensions, matching our schema
TARGET_EMBEDDING_DIM = 1024


class TemporalWriterPG:
    """Write facts to PostgreSQL with calibration.

    Uses asyncpg connection pool for true async/await.
    Supports content hash deduplication for idempotent writes.
    """

    def __init__(self) -> None:
        """Initialize TemporalWriterPG.

        Uses the global connection pool from postgres_pool.py.
        No explicit connection management needed.
        """
        pass

    async def connect(self) -> None:
        """Initialize connection (no-op when using pool).

        The connection pool is initialized lazily on first use.
        This method exists for API compatibility with SQLite version.
        """
        # Pool is initialized lazily by get_connection()
        pass

    async def close(self) -> None:
        """Close connection (no-op when using pool).

        The connection pool manages connection lifecycle.
        This method exists for API compatibility with SQLite version.
        """
        # Pool manages connection lifecycle
        pass

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

        written_count = 0

        # Write all facts in a single transaction
        async with get_transaction() as conn:
            for fact in facts:
                # Compute calibrated confidence
                calibrated_confidence = fact.confidence * outcome.confidence_multiplier

                # Ensure content hash exists
                content_hash = fact.content_hash or self._compute_content_hash(fact)

                # Generate unique ID
                fact_id = str(uuid.uuid4())

                # INSERT ... ON CONFLICT DO NOTHING for deduplication
                # PostgreSQL uses $1, $2, $3 placeholders
                # Use NOW() for timestamp (let PG handle it)
                result = await conn.execute(
                    """
                    INSERT INTO temporal_facts
                    (id, session_id, key, value, turn, confidence, content_hash, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    ON CONFLICT (content_hash) DO NOTHING
                    """,
                    fact_id,
                    session_id,
                    fact.key,
                    fact.value,
                    fact.turn,
                    calibrated_confidence,
                    content_hash,
                )

                # Check if row was inserted (not a duplicate)
                # asyncpg returns "INSERT 0 1" on success, "INSERT 0 0" on conflict
                if result and result.endswith("1"):
                    written_count += 1

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

        written_count = 0

        async with get_transaction() as conn:
            for turn, facts in facts_by_turn.items():
                trace_id = str(uuid.uuid4())
                calibrated_confidence = outcome.confidence_multiplier

                await conn.execute(
                    """
                    INSERT INTO temporal_traces
                    (id, session_id, turn, fact_count, confidence, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    """,
                    trace_id,
                    session_id,
                    turn,
                    len(facts),
                    calibrated_confidence,
                )
                written_count += 1

        return written_count

    async def get_facts(self, session_id: str) -> list[dict[str, Any]]:
        """Get all facts for a session.

        Args:
            session_id: Root span ID of the session

        Returns:
            List of fact dictionaries
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, session_id, key, value, turn, confidence, content_hash, created_at
                FROM temporal_facts
                WHERE session_id = $1
                ORDER BY turn, created_at
                """,
                session_id,
            )

        return [dict(row) for row in rows]

    async def get_traces(self, session_id: str) -> list[dict[str, Any]]:
        """Get all traces for a session.

        Args:
            session_id: Root span ID of the session

        Returns:
            List of trace dictionaries
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, session_id, turn, fact_count, confidence, created_at
                FROM temporal_traces
                WHERE session_id = $1
                ORDER BY turn
                """,
                session_id,
            )

        return [dict(row) for row in rows]

    def _compute_content_hash(self, fact: SpanFact) -> str:
        """Compute hash for deduplication (excludes timestamp).

        Hash is based on key:value:turn which allows same facts
        to be deduplicated across multiple processing runs.
        """
        content = f"{fact.key}:{fact.value}:{fact.turn}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _pad_embedding(
        self, embedding: list[float], target_dim: int = TARGET_EMBEDDING_DIM
    ) -> list[float]:
        """Pad or truncate embedding to target dimension.

        Following the Letta pattern for pgvector compatibility.

        Args:
            embedding: Original embedding
            target_dim: Target dimension (default 4096)

        Returns:
            Padded/truncated embedding as list
        """
        vec = np.array(embedding)
        if len(vec) >= target_dim:
            return vec[:target_dim].tolist()
        return np.pad(vec, (0, target_dim - len(vec)), mode="constant").tolist()

    async def write_facts_with_embeddings(
        self,
        session_id: str,
        turn: int,
        facts: list[SpanFact],
        outcome: SessionOutcome,
        embedding_fn: Union[
            Callable[[str], list[float]],
            Callable[[str], Awaitable[list[float]]],
            None,
        ] = None,
    ) -> int:
        """Write facts with optional vector embeddings.

        This method extends write_facts() by generating and storing
        vector embeddings for semantic similarity search.

        Args:
            session_id: Root span ID of the session
            turn: Turn number for these facts
            facts: List of SpanFact objects to write
            outcome: SessionOutcome with confidence multiplier
            embedding_fn: Optional function to generate embeddings.
                         If None, facts are written without embeddings.
                         Function signature: (text: str) -> list[float]
                         Can be sync or async.

        Returns:
            Number of facts written (excluding duplicates)
        """
        if not facts:
            return 0

        written_count = 0

        async with get_transaction() as conn:
            # Initialize pgvector if we have embeddings
            if embedding_fn is not None:
                await init_pgvector(conn)

            for fact in facts:
                # Compute calibrated confidence
                calibrated_confidence = fact.confidence * outcome.confidence_multiplier

                # Ensure content hash exists
                content_hash = fact.content_hash or self._compute_content_hash(fact)

                # Generate unique ID
                fact_id = str(uuid.uuid4())

                # Generate embedding if function provided
                embedding = None
                if embedding_fn is not None:
                    # Combine key and value for embedding text
                    embed_text = f"{fact.key}: {fact.value}"
                    # Handle both sync and async embedding functions
                    result = embedding_fn(embed_text)
                    if inspect.iscoroutine(result):
                        raw_embedding = await result
                    else:
                        raw_embedding = result
                    embedding = self._pad_embedding(raw_embedding)

                if embedding is not None:
                    # INSERT with embedding
                    result = await conn.execute(
                        """
                        INSERT INTO temporal_facts
                        (id, session_id, key, value, turn, confidence, content_hash, embedding, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector, NOW())
                        ON CONFLICT (content_hash) DO NOTHING
                        """,
                        fact_id,
                        session_id,
                        fact.key,
                        fact.value,
                        turn,
                        calibrated_confidence,
                        content_hash,
                        embedding,
                    )
                else:
                    # INSERT without embedding (NULL)
                    result = await conn.execute(
                        """
                        INSERT INTO temporal_facts
                        (id, session_id, key, value, turn, confidence, content_hash, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                        ON CONFLICT (content_hash) DO NOTHING
                        """,
                        fact_id,
                        session_id,
                        fact.key,
                        fact.value,
                        turn,
                        calibrated_confidence,
                        content_hash,
                    )

                # Check if row was inserted (not a duplicate)
                if result and result.endswith("1"):
                    written_count += 1

        return written_count
