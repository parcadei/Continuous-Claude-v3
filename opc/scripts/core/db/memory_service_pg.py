"""Memory Service with PostgreSQL + pgvector backend.

Async rewrite of memory_service.py with:
- Core Memory: Key-value blocks per session/agent
- Archival Memory: Long-term storage with FTS + vector search
- Recall Memory: Cross-source query combining all sources

Scoping model (R-Flow):
- session_id: Claude Code session
- agent_id: Optional agent identifier within session

Usage:
    memory = MemoryServicePG(session_id="abc123")
    await memory.connect()

    # Core memory
    await memory.set_core("persona", "You are a helpful assistant")

    # Archival memory
    await memory.store("User prefers Python")

    # Recall (cross-source query)
    result = await memory.recall("What language?")

    await memory.close()
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

import asyncpg
import numpy as np

from .postgres_pool import get_connection, get_pool, get_transaction, init_pgvector


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...

    @property
    def dimension(self) -> int:
        """Embedding dimension."""
        ...


def generate_memory_id() -> str:
    """Generate a UUID for memory ID.

    Returns a proper UUID string for PostgreSQL UUID column.
    """
    return str(uuid4())


@dataclass
class ArchivalFact:
    """A fact stored in archival memory."""

    id: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime
    similarity: float | None = None  # For vector search results


class MemoryServicePG:
    """Async memory service with PostgreSQL + pgvector backend.

    Scoping model (R-Flow):
    - session_id: Claude Code session
    - agent_id: Optional agent within session

    Architecture:
    - Core Memory: Key-value blocks (fast reads, concurrent writes)
    - Archival Memory: Long-term with FTS + vector search
    - Recall Memory: Query interface combining all sources
    """

    def __init__(
        self,
        session_id: str = "default",
        agent_id: str | None = None,
    ):
        """Initialize memory service.

        Args:
            session_id: Session identifier for isolation
            agent_id: Optional agent identifier for agent-specific memory
        """
        self.session_id = session_id
        self.agent_id = agent_id
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Initialize connection pool."""
        self._pool = await get_pool()

    async def close(self) -> None:
        """Release connection (pool stays open for other services)."""
        # Pool is shared, don't close it here
        pass

    # ==================== Core Memory ====================

    async def set_core(self, key: str, value: str) -> None:
        """Set a core memory block.

        Args:
            key: Block key (e.g., "persona", "task", "context")
            value: Block content
        """
        async with get_transaction() as conn:
            # Use DELETE + INSERT to handle NULL agent_id properly
            # PostgreSQL's ON CONFLICT doesn't work well with NULL values
            # Transaction wrapper ensures atomicity on concurrent writes
            await conn.execute(
                """
                DELETE FROM core_memory
                WHERE session_id = $1 AND agent_id IS NOT DISTINCT FROM $2 AND key = $3
            """,
                self.session_id,
                self.agent_id,
                key,
            )
            await conn.execute(
                """
                INSERT INTO core_memory (session_id, agent_id, key, value, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
            """,
                self.session_id,
                self.agent_id,
                key,
                value,
            )

    async def get_core(self, key: str) -> str | None:
        """Get a core memory block.

        Args:
            key: Block key

        Returns:
            Block content or None if not found
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT value FROM core_memory
                WHERE session_id = $1 AND agent_id IS NOT DISTINCT FROM $2 AND key = $3
            """,
                self.session_id,
                self.agent_id,
                key,
            )
            return row["value"] if row else None

    async def list_core_keys(self) -> list[str]:
        """List all core memory block keys.

        Returns:
            List of keys
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT key FROM core_memory
                WHERE session_id = $1 AND agent_id IS NOT DISTINCT FROM $2
                ORDER BY key
            """,
                self.session_id,
                self.agent_id,
            )
            return [row["key"] for row in rows]

    async def delete_core(self, key: str) -> None:
        """Delete a core memory block.

        Args:
            key: Block key to delete
        """
        async with get_connection() as conn:
            await conn.execute(
                """
                DELETE FROM core_memory
                WHERE session_id = $1 AND agent_id IS NOT DISTINCT FROM $2 AND key = $3
            """,
                self.session_id,
                self.agent_id,
                key,
            )

    async def get_all_core(self) -> dict[str, str]:
        """Get all core memory blocks.

        Returns:
            Dict of key -> value
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT key, value FROM core_memory
                WHERE session_id = $1 AND agent_id IS NOT DISTINCT FROM $2
                ORDER BY key
            """,
                self.session_id,
                self.agent_id,
            )
            return {row["key"]: row["value"] for row in rows}

    # ==================== Block-Based Core Memory ====================

    async def set_block(self, block: Block) -> None:
        """Set a Block in core memory.

        Stores the block's value under its label, with limit in metadata.
        This provides Letta-compatible block storage in core memory.

        Args:
            block: Block instance to store

        Note:
            Import Block lazily to avoid circular imports.
        """

        # Store as JSON with limit and metadata preserved
        block_data = json.dumps(
            {
                "value": block.value,
                "limit": block.limit,
                "metadata": block.metadata,
            }
        )
        await self.set_core(block.label, block_data)

    async def get_block(self, label: str) -> Block | None:
        """Get a Block from core memory.

        Retrieves block data stored via set_block() and reconstructs
        the Block instance with preserved limit and metadata.

        Args:
            label: Block label to retrieve

        Returns:
            Block instance or None if not found
        """
        from .memory_block import Block

        raw = await self.get_core(label)
        if raw is None:
            return None

        try:
            # Parse JSON block data
            data = json.loads(raw)
            return Block(
                label=label,
                value=data.get("value", ""),
                limit=data.get("limit", 5000),
                metadata=data.get("metadata", {}),
            )
        except (json.JSONDecodeError, TypeError):
            # Fall back to treating raw value as plain string (backward compat)
            return Block(label=label, value=raw)

    async def get_all_blocks(self) -> dict[str, Block]:
        """Get all Blocks from core memory.

        Returns:
            Dict mapping label to Block instance
        """
        from .memory_block import Block

        all_core = await self.get_all_core()
        blocks = {}

        for label, raw in all_core.items():
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and "value" in data:
                    blocks[label] = Block(
                        label=label,
                        value=data.get("value", ""),
                        limit=data.get("limit", 5000),
                        metadata=data.get("metadata", {}),
                    )
                else:
                    # Plain string value
                    blocks[label] = Block(label=label, value=raw)
            except (json.JSONDecodeError, TypeError):
                # Plain string value
                blocks[label] = Block(label=label, value=raw)

        return blocks

    # ==================== Archival Memory ====================

    async def store(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Store a fact in archival memory.

        Args:
            content: Fact content
            metadata: Optional metadata dict
            embedding: Optional pre-computed embedding (normalized to 1024 dims)
            tags: Optional list of tags for categorization

        Returns:
            Memory ID
        """
        memory_id = generate_memory_id()

        # Normalize embedding to 1024 dims if provided
        # Treat empty list as no embedding
        padded_embedding = None
        if embedding is not None and len(embedding) > 0:
            padded_embedding = self._pad_embedding(embedding)

        async with get_transaction() as conn:
            if padded_embedding is not None:
                # Register vector type for this connection
                await init_pgvector(conn)

                await conn.execute(
                    """
                    INSERT INTO archival_memory
                        (id, session_id, agent_id, content, metadata, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    memory_id,
                    self.session_id,
                    self.agent_id,
                    content,
                    json.dumps(metadata or {}),
                    padded_embedding,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO archival_memory
                        (id, session_id, agent_id, content, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                """,
                    memory_id,
                    self.session_id,
                    self.agent_id,
                    content,
                    json.dumps(metadata or {}),
                )

            # Store tags if provided (deduplicated via set)
            if tags:
                unique_tags = set(tags)
                for tag in unique_tags:
                    await conn.execute(
                        """
                        INSERT INTO memory_tags (memory_id, tag, session_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (memory_id, tag) DO NOTHING
                        """,
                        memory_id,
                        tag,
                        self.session_id,
                    )

        return memory_id

    def _pad_embedding(self, embedding: list[float], target_dim: int = 1024) -> list[float]:
        """Pad or truncate embedding to target dimension.

        Args:
            embedding: Original embedding
            target_dim: Target dimension (default 1024 to match bge-large-en-v1.5)

        Returns:
            Padded/truncated embedding as list
        """
        vec = np.array(embedding)
        if len(vec) >= target_dim:
            return vec[:target_dim].tolist()
        return np.pad(vec, (0, target_dim - len(vec)), mode="constant").tolist()

    async def search_text(
        self,
        query: str,
        limit: int = 10,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Search archival memory with full-text search.

        Args:
            query: Search query
            limit: Max results to return
            start_date: Optional start of date range (inclusive)
            end_date: Optional end of date range (inclusive)

        Returns:
            List of matching facts with ranking
        """
        async with get_connection() as conn:
            # Build query dynamically based on date filters
            conditions = [
                "session_id = $1",
                "agent_id IS NOT DISTINCT FROM $2",
                "to_tsvector('english', content) @@ plainto_tsquery('english', $3)",
            ]
            params: list[Any] = [self.session_id, self.agent_id, query]
            param_idx = 4

            if start_date is not None:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(start_date)
                param_idx += 1

            if end_date is not None:
                conditions.append(f"created_at <= ${param_idx}")
                params.append(end_date)
                param_idx += 1

            params.append(limit)

            where_clause = " AND ".join(conditions)
            sql = f"""
                SELECT
                    id,
                    content,
                    metadata,
                    created_at,
                    ts_rank(
                        to_tsvector('english', content),
                        plainto_tsquery('english', $3)
                    ) as rank
                FROM archival_memory
                WHERE {where_clause}
                ORDER BY rank DESC
                LIMIT ${param_idx}
            """

            rows = await conn.fetch(sql, *params)

            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "rank": row["rank"],
                }
                for row in rows
            ]

    async def search_vector(
        self,
        query_embedding: list[float],
        limit: int = 10,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Search archival memory with vector similarity.

        Args:
            query_embedding: Query embedding (normalized to 1024 dims)
            limit: Max results to return
            start_date: Optional start of date range (inclusive)
            end_date: Optional end of date range (inclusive)

        Returns:
            List of matching facts with cosine similarity score
        """
        padded_query = self._pad_embedding(query_embedding)

        async with get_connection() as conn:
            await init_pgvector(conn)

            # Build query dynamically based on date filters
            conditions = [
                "session_id = $1",
                "agent_id IS NOT DISTINCT FROM $2",
                "embedding IS NOT NULL",
            ]
            params: list[Any] = [self.session_id, self.agent_id, padded_query]
            param_idx = 4

            if start_date is not None:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(start_date)
                param_idx += 1

            if end_date is not None:
                conditions.append(f"created_at <= ${param_idx}")
                params.append(end_date)
                param_idx += 1

            params.append(limit)

            where_clause = " AND ".join(conditions)
            sql = f"""
                SELECT
                    id,
                    content,
                    metadata,
                    created_at,
                    1 - (embedding <=> $3::vector) as similarity
                FROM archival_memory
                WHERE {where_clause}
                ORDER BY embedding <=> $3::vector
                LIMIT ${param_idx}
            """

            rows = await conn.fetch(sql, *params)

            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "similarity": row["similarity"],
                }
                for row in rows
            ]

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search archival memory with FTS (backward compatible).

        Alias for search_text() to match original API.
        """
        return await self.search_text(query, limit)

    async def search_vector_with_threshold(
        self,
        query_embedding: list[float],
        threshold: float = 0.0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search archival memory with vector similarity and threshold filter.

        Args:
            query_embedding: Query embedding (will be padded to 4096)
            threshold: Minimum similarity threshold (0.0 to 1.0)
            limit: Max results to return

        Returns:
            List of matching facts with cosine similarity score >= threshold
        """
        padded_query = self._pad_embedding(query_embedding)

        async with get_connection() as conn:
            await init_pgvector(conn)

            rows = await conn.fetch(
                """
                SELECT
                    id,
                    content,
                    metadata,
                    created_at,
                    1 - (embedding <=> $3::vector) as similarity
                FROM archival_memory
                WHERE session_id = $1
                AND agent_id IS NOT DISTINCT FROM $2
                AND embedding IS NOT NULL
                AND (1 - (embedding <=> $3::vector)) >= $4
                ORDER BY embedding <=> $3::vector
                LIMIT $5
            """,
                self.session_id,
                self.agent_id,
                padded_query,
                threshold,
                limit,
            )

            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "similarity": row["similarity"],
                }
                for row in rows
            ]

    async def search_vector_with_filter(
        self,
        query_embedding: list[float],
        metadata_filter: dict[str, Any],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search archival memory with vector similarity and metadata filter.

        Args:
            query_embedding: Query embedding (will be padded to 4096)
            metadata_filter: Dict of key-value pairs to filter by (exact match)
            limit: Max results to return

        Returns:
            List of matching facts filtered by metadata with cosine similarity score
        """
        padded_query = self._pad_embedding(query_embedding)

        async with get_connection() as conn:
            await init_pgvector(conn)

            # Build JSONB containment query for metadata filter
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    content,
                    metadata,
                    created_at,
                    1 - (embedding <=> $3::vector) as similarity
                FROM archival_memory
                WHERE session_id = $1
                AND agent_id IS NOT DISTINCT FROM $2
                AND embedding IS NOT NULL
                AND metadata @> $4::jsonb
                ORDER BY embedding <=> $3::vector
                LIMIT $5
            """,
                self.session_id,
                self.agent_id,
                padded_query,
                json.dumps(metadata_filter),
                limit,
            )

            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "similarity": row["similarity"],
                }
                for row in rows
            ]

    async def search_hybrid(
        self,
        text_query: str,
        query_embedding: list[float],
        limit: int = 10,
        text_weight: float = 0.3,
        vector_weight: float = 0.7,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining full-text search and vector similarity.

        Uses a weighted combination of FTS rank and vector similarity.

        Args:
            text_query: Text query for FTS
            query_embedding: Query embedding for vector search
            limit: Max results to return
            text_weight: Weight for text search score (default 0.3)
            vector_weight: Weight for vector similarity (default 0.7)
            start_date: Optional start of date range (inclusive)
            end_date: Optional end of date range (inclusive)

        Returns:
            List of matching facts with combined score
        """
        padded_query = self._pad_embedding(query_embedding)

        async with get_connection() as conn:
            await init_pgvector(conn)

            # Build query dynamically based on date filters
            conditions = [
                "session_id = $1",
                "agent_id IS NOT DISTINCT FROM $2",
                "(to_tsvector('english', content) @@ plainto_tsquery('english', $3) OR embedding IS NOT NULL)",
            ]
            # Base params: session_id, agent_id, text_query, embedding, text_weight, vector_weight
            params: list[Any] = [
                self.session_id,
                self.agent_id,
                text_query,
                padded_query,
                text_weight,
                vector_weight,
            ]
            param_idx = 7

            if start_date is not None:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(start_date)
                param_idx += 1

            if end_date is not None:
                conditions.append(f"created_at <= ${param_idx}")
                params.append(end_date)
                param_idx += 1

            params.append(limit)

            where_clause = " AND ".join(conditions)
            sql = f"""
                SELECT
                    id,
                    content,
                    metadata,
                    created_at,
                    ts_rank(
                        to_tsvector('english', content),
                        plainto_tsquery('english', $3)
                    ) as text_rank,
                    CASE
                        WHEN embedding IS NOT NULL
                        THEN 1 - (embedding <=> $4::vector)
                        ELSE 0
                    END as similarity,
                    (
                        $5 * COALESCE(ts_rank(
                            to_tsvector('english', content),
                            plainto_tsquery('english', $3)
                        ), 0) +
                        $6 * CASE
                            WHEN embedding IS NOT NULL
                            THEN 1 - (embedding <=> $4::vector)
                            ELSE 0
                        END
                    ) as combined_score
                FROM archival_memory
                WHERE {where_clause}
                ORDER BY combined_score DESC
                LIMIT ${param_idx}
            """

            rows = await conn.fetch(sql, *params)

            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "text_rank": row["text_rank"],
                    "similarity": row["similarity"],
                    "combined_score": row["combined_score"],
                }
                for row in rows
            ]

    async def search_hybrid_rrf(
        self,
        text_query: str,
        query_embedding: list[float],
        limit: int = 10,
        k: int = 60,
    ) -> list[dict[str, Any]]:
        """Hybrid search using Reciprocal Rank Fusion.

        RRF combines rankings from FTS and vector search using:
        score = 1/(k + rank_fts) + 1/(k + rank_vector)

        This approach is more robust than weighted combination because:
        - It's rank-based, not score-based (solves normalization issues)
        - Less sensitive to weight tuning
        - Works well when one modality has no results

        Args:
            text_query: Text query for FTS
            query_embedding: Query embedding for vector search
            limit: Max results to return
            k: RRF constant (default 60, higher = more weight to lower ranks)

        Returns:
            List of matching facts with RRF score
        """
        padded_query = self._pad_embedding(query_embedding)

        async with get_connection() as conn:
            await init_pgvector(conn)

            # RRF query using CTEs for separate rankings
            rows = await conn.fetch(
                """
                WITH fts_ranked AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            ORDER BY ts_rank(
                                to_tsvector('english', content),
                                plainto_tsquery('english', $3)
                            ) DESC
                        ) as fts_rank
                    FROM archival_memory
                    WHERE session_id = $1
                    AND agent_id IS NOT DISTINCT FROM $2
                    AND to_tsvector('english', content) @@ plainto_tsquery('english', $3)
                ),
                vector_ranked AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (ORDER BY embedding <=> $4::vector) as vec_rank
                    FROM archival_memory
                    WHERE session_id = $1
                    AND agent_id IS NOT DISTINCT FROM $2
                    AND embedding IS NOT NULL
                ),
                combined AS (
                    SELECT
                        COALESCE(f.id, v.id) as id,
                        COALESCE(1.0 / ($5 + f.fts_rank), 0) +
                        COALESCE(1.0 / ($5 + v.vec_rank), 0) as rrf_score
                    FROM fts_ranked f
                    FULL OUTER JOIN vector_ranked v ON f.id = v.id
                )
                SELECT
                    a.id,
                    a.content,
                    a.metadata,
                    a.created_at,
                    c.rrf_score
                FROM combined c
                JOIN archival_memory a ON a.id = c.id
                ORDER BY c.rrf_score DESC
                LIMIT $6
            """,
                self.session_id,
                self.agent_id,
                text_query,
                padded_query,
                k,
                limit,
            )

            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "rrf_score": float(row["rrf_score"]),
                }
                for row in rows
            ]

    def _cosine_similarity(self, v1: list[float], v2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            v1: First vector
            v2: Second vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        import math
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 * norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    async def search_learnings_mmr(
        self,
        query: str,
        query_embedding: list[float],
        limit: int = 5,
        lambda_param: float = 0.5,
        similarity_threshold: float = 0.0,
        k: int = 60,
    ) -> list[dict[str, Any]]:
        """Search archival memory using Maximal Marginal Relevance (MMR).

        The MMR algorithm selects results that are both relevant AND diverse.
        This prevents returning redundant/similar results that cluster together
        in the embedding space.

        Algorithm (Greedy Iterative Selection):
        1. Fetch candidates using hybrid FTS + vector search (k candidates)
        2. For each iteration:
           a. Calculate MMR score for all unselected candidates
           b. Select candidate with highest MMR score
           c. Update diversity scores based on newly selected item
           d. Repeat until 'limit' items selected or candidates exhausted

        MMR Score Formula:
            MMR = lambda_param * relevance - (1 - lambda_param) * diversity

        Where:
            - relevance: Cosine similarity to query embedding (0-1)
            - diversity: Maximum cosine similarity to already-selected items (0-1)

        Args:
            query: Text query for full-text search (FTS)
            query_embedding: Query embedding vector for similarity search
            limit: Maximum number of results to return (default: 5)
            lambda_param: Trade-off parameter controlling relevance vs diversity:
                - 1.0 = pure relevance ranking (similar to RRF)
                - 0.5 = balanced trade-off (recommended starting point)
                - 0.0 = pure diversity ranking
            similarity_threshold: Minimum MMR score threshold (0.0-1.0).
                Items with MMR below this are excluded from results.
            k: Number of initial candidates to retrieve before MMR filtering.
                Should be larger than 'limit' to allow diversity selection.
                Typical values: 2-3x the desired limit (default: 60)

        Returns:
            List of matching facts, each containing:
            - id: Memory UUID
            - content: Stored text content
            - metadata: Associated metadata dictionary
            - created_at: Timestamp of storage
            - mmr_score: Final MMR score used for ranking
            - relevance: Cosine similarity to query
            - diversity: Diversity penalty from selected items

        Example:
            >>> results = await memory.search_learnings_mmr(
            ...     query="error handling patterns",
            ...     query_embedding=await memory.embed("error handling"),
            ...     limit=5,
            ...     lambda_param=0.5,
            ...     similarity_threshold=0.1
            ... )
            >>> for r in results:
            ...     print(f"{r['content']}: MMR={r['mmr_score']:.3f}")

        Note:
            Higher lambda values favor topically similar results.
            Lower lambda values favor semantically diverse results.
            For exploratory queries, use lower lambda (0.3-0.4).
            For precise lookups, use higher lambda (0.6-0.8).
        """
        padded_query = self._pad_embedding(query_embedding)

        # Get more candidates than needed for diversity filtering
        num_candidates = limit * 2

        async with get_connection() as conn:
            await init_pgvector(conn)

            # Fetch candidates with both FTS and vector scores
            rows = await conn.fetch(
                """
                WITH fts_ranked AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            ORDER BY ts_rank(
                                to_tsvector('english', content),
                                plainto_tsquery('english', $4)
                            ) DESC
                        ) as fts_rank
                    FROM archival_memory
                    WHERE session_id IS NOT DISTINCT FROM $1
                    AND agent_id IS NOT DISTINCT FROM $2
                    AND to_tsvector('english', content) @@ plainto_tsquery('english', $4)
                ),
                vector_ranked AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (ORDER BY embedding <=> $5::vector) as vec_rank,
                        embedding
                    FROM archival_memory
                    WHERE session_id IS NOT DISTINCT FROM $1
                    AND agent_id IS NOT DISTINCT FROM $2
                    AND embedding IS NOT NULL
                ),
                combined AS (
                    SELECT
                        COALESCE(f.id, v.id) as id,
                        1 - (v.embedding <=> $5::vector) as relevance,
                        v.embedding
                    FROM vector_ranked v
                    LEFT JOIN fts_ranked f ON f.id = v.id
                    UNION
                    SELECT
                        f.id,
                        1 - (v.embedding <=> $5::vector) as relevance,
                        v.embedding
                    FROM fts_ranked f
                    LEFT JOIN vector_ranked v ON v.id = f.id
                    WHERE f.id NOT IN (SELECT id FROM vector_ranked)
                )
                SELECT
                    a.id,
                    a.content,
                    a.metadata,
                    a.created_at,
                    c.relevance,
                    c.embedding
                FROM combined c
                JOIN archival_memory a ON a.id = c.id
                ORDER BY c.relevance DESC
                LIMIT $6
            """,
                self.session_id,
                self.agent_id,
                k,
                query,
                padded_query,
                num_candidates,
            )

            if not rows:
                return []

            # Build candidate list with embeddings
            candidates = []
            for row in rows:
                embedding_bytes = row["embedding"]
                # Convert bytes to list of floats if stored as bytes
                if isinstance(embedding_bytes, bytes):
                    import struct
                    embedding = list(struct.unpack(f"{1024}f", embedding_bytes))
                elif embedding_bytes:
                    embedding = list(embedding_bytes)
                else:
                    embedding = []

                candidates.append({
                    "id": str(row["id"]),
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "relevance": float(row["relevance"]),
                    "embedding": embedding,
                })

        if not candidates:
            return []

        # MMR selection
        selected = []
        selected_embeddings = []

        for item in candidates:
            if len(selected) >= limit:
                break

            relevance = item.get("relevance", 0)

            # Calculate diversity (max similarity to already selected)
            diversity = 0.0
            if selected_embeddings:
                similarities = [
                    self._cosine_similarity(item["embedding"], sel_emb)
                    for sel_emb in selected_embeddings
                ]
                diversity = max(similarities) if similarities else 0

            # MMR score: balance relevance vs diversity
            mmr_score = lambda_param * relevance - (1 - lambda_param) * diversity

            item["mmr_score"] = mmr_score
            item["diversity"] = diversity

            if mmr_score >= similarity_threshold:
                selected.append(item)
                selected_embeddings.append(item["embedding"])

            # Remove embedding from final output to reduce size
            if "embedding" in item:
                del item["embedding"]

        return selected

    async def store_with_embedding(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        embedder: EmbeddingProvider | None = None,
    ) -> str:
        """Store a fact with auto-generated embedding.

        Args:
            content: Fact content
            metadata: Optional metadata dict
            embedder: Optional embedding provider (if None, stores without embedding)

        Returns:
            Memory ID
        """
        embedding = None

        if embedder is not None:
            embedding = await embedder.embed(content)

        return await self.store(content, metadata, embedding)

    async def delete_archival(self, memory_id: str) -> None:
        """Delete a fact from archival memory.

        Args:
            memory_id: Memory ID to delete

        Note:
            Tags are automatically deleted via CASCADE.
        """
        async with get_connection() as conn:
            await conn.execute(
                """
                DELETE FROM archival_memory
                WHERE id = $1 AND session_id = $2 AND agent_id IS NOT DISTINCT FROM $3
            """,
                memory_id,
                self.session_id,
                self.agent_id,
            )

    # ==================== Tag Operations ====================

    async def get_tags(self, memory_id: str) -> list[str]:
        """Get all tags for a memory ID.

        Args:
            memory_id: Memory ID to get tags for

        Returns:
            List of tag strings
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT tag FROM memory_tags
                WHERE memory_id = $1 AND session_id = $2
                ORDER BY tag
                """,
                memory_id,
                self.session_id,
            )
            return [row["tag"] for row in rows]

    async def add_tag(self, memory_id: str, tag: str) -> None:
        """Add a tag to an existing memory.

        Args:
            memory_id: Memory ID to tag
            tag: Tag to add
        """
        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO memory_tags (memory_id, tag, session_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (memory_id, tag) DO NOTHING
                """,
                memory_id,
                tag,
                self.session_id,
            )

    async def remove_tag(self, memory_id: str, tag: str) -> None:
        """Remove a tag from a memory.

        Args:
            memory_id: Memory ID to untag
            tag: Tag to remove
        """
        async with get_connection() as conn:
            await conn.execute(
                """
                DELETE FROM memory_tags
                WHERE memory_id = $1 AND tag = $2 AND session_id = $3
                """,
                memory_id,
                tag,
                self.session_id,
            )

    async def get_all_session_tags(self) -> list[str]:
        """Get all unique tags used in this session.

        Returns:
            List of unique tag strings
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT tag FROM memory_tags
                WHERE session_id = $1
                ORDER BY tag
                """,
                self.session_id,
            )
            return [row["tag"] for row in rows]

    async def search_with_tags(
        self,
        query: str,
        tags: list[str] | None = None,
        tag_match_mode: str = "any",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search archival memory with optional tag filtering.

        Args:
            query: FTS query string
            tags: Optional list of tags to filter by
            tag_match_mode: "any" for OR matching, "all" for AND matching
            limit: Maximum results to return

        Returns:
            List of matching facts with scores
        """
        async with get_connection() as conn:
            # If no tags specified, return all FTS matches
            if not tags:
                rows = await conn.fetch(
                    """
                    SELECT
                        a.id,
                        a.content,
                        a.metadata,
                        a.created_at,
                        ts_rank(
                            to_tsvector('english', a.content),
                            plainto_tsquery('english', $3)
                        ) as score
                    FROM archival_memory a
                    WHERE a.session_id = $1
                    AND a.agent_id IS NOT DISTINCT FROM $2
                    AND to_tsvector('english', a.content) @@ plainto_tsquery('english', $3)
                    ORDER BY score DESC
                    LIMIT $4
                    """,
                    self.session_id,
                    self.agent_id,
                    query,
                    limit,
                )
            elif tag_match_mode == "all":
                # Must have ALL specified tags
                rows = await conn.fetch(
                    """
                    SELECT
                        a.id,
                        a.content,
                        a.metadata,
                        a.created_at,
                        ts_rank(
                            to_tsvector('english', a.content),
                            plainto_tsquery('english', $3)
                        ) as score
                    FROM archival_memory a
                    WHERE a.session_id = $1
                    AND a.agent_id IS NOT DISTINCT FROM $2
                    AND to_tsvector('english', a.content) @@ plainto_tsquery('english', $3)
                    AND a.id IN (
                        SELECT memory_id FROM memory_tags
                        WHERE session_id = $1 AND tag = ANY($4)
                        GROUP BY memory_id
                        HAVING COUNT(DISTINCT tag) = $5
                    )
                    ORDER BY score DESC
                    LIMIT $6
                    """,
                    self.session_id,
                    self.agent_id,
                    query,
                    tags,
                    len(tags),
                    limit,
                )
            else:
                # "any" mode: must have ANY of specified tags (OR)
                rows = await conn.fetch(
                    """
                    SELECT
                        a.id,
                        a.content,
                        a.metadata,
                        a.created_at,
                        ts_rank(
                            to_tsvector('english', a.content),
                            plainto_tsquery('english', $3)
                        ) as score
                    FROM archival_memory a
                    WHERE a.session_id = $1
                    AND a.agent_id IS NOT DISTINCT FROM $2
                    AND to_tsvector('english', a.content) @@ plainto_tsquery('english', $3)
                    AND a.id IN (
                        SELECT memory_id FROM memory_tags
                        WHERE session_id = $1 AND tag = ANY($4)
                    )
                    ORDER BY score DESC
                    LIMIT $5
                    """,
                    self.session_id,
                    self.agent_id,
                    query,
                    tags,
                    limit,
                )

            return [
                {
                    "id": str(row["id"]),
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                    "score": float(row["score"]),
                }
                for row in rows
            ]

    # ==================== Recall Memory ====================

    async def recall(
        self,
        query: str,
        include_core: bool = True,
        limit: int = 5,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> str:
        """Recall information from all memory sources.

        Args:
            query: Natural language query
            include_core: Whether to include core memory
            limit: Max archival results
            start_date: Optional start of date range (inclusive)
            end_date: Optional end of date range (inclusive)

        Returns:
            Combined recall result as string
        """
        parts = []

        # Check core memory first (key match)
        if include_core:
            core = await self.get_all_core()
            for key, value in core.items():
                if query.lower() in key.lower() or key.lower() in query.lower():
                    parts.append(f"[Core/{key}]: {value}")

        # Search archival memory with date filtering
        archival_results = await self.search_text(
            query, limit=limit, start_date=start_date, end_date=end_date
        )
        for result in archival_results:
            parts.append(f"[Archival]: {result['content']}")

        if not parts:
            return "No relevant memories found."

        return "\n".join(parts)

    async def to_context(self, max_archival: int = 10) -> str:
        """Generate context string for prompt injection.

        Args:
            max_archival: Max recent archival facts to include

        Returns:
            Formatted context string
        """
        lines = ["## Core Memory"]

        core = await self.get_all_core()
        if core:
            for key, value in core.items():
                lines.append(f"**{key}:** {value}")
        else:
            lines.append("(empty)")

        lines.append("")
        lines.append("## Recent Archival Memory")

        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT content FROM archival_memory
                WHERE session_id = $1 AND agent_id IS NOT DISTINCT FROM $2
                ORDER BY created_at DESC
                LIMIT $3
            """,
                self.session_id,
                self.agent_id,
                max_archival,
            )

            if rows:
                for row in rows:
                    lines.append(f"- {row['content']}")
            else:
                lines.append("(empty)")

        return "\n".join(lines)
