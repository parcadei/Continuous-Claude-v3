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

    @staticmethod
    def _safe_json_loads(value: str | list | dict | None, default: Any) -> Any:
        """Safely parse JSON with fallback to default.

        Handles both string JSON and already-decoded objects (asyncpg auto-decodes
        JSON columns to Python types in some configurations).

        Args:
            value: JSON string, already-decoded list/dict, or None
            default: Value to return if parsing fails or value is empty

        Returns:
            Parsed JSON or default value
        """
        if value is None:
            return default
        # If asyncpg already decoded JSON to Python type, return as-is
        if isinstance(value, (list, dict)):
            return value
        # Empty string check
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

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

    # ==================== Checkpoint Operations ====================

    async def create_checkpoint(
        self,
        phase: str,
        context_usage: float | None = None,
        files_modified: list[str] | None = None,
        unknowns: list[str] | None = None,
        handoff_path: str | None = None,
    ) -> str:
        """Create a checkpoint for crash recovery and session continuity.

        Args:
            phase: Current work phase (e.g., "planning", "implementation", "testing")
            context_usage: Optional context usage percentage (0.0 to 1.0)
            files_modified: Optional list of files modified in this phase
            unknowns: Optional list of unresolved questions/issues
            handoff_path: Optional path to associated handoff file

        Returns:
            Checkpoint ID
        """
        checkpoint_id = generate_memory_id()
        agent_id = self.agent_id or "main"

        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO checkpoints
                    (id, agent_id, session_id, phase, context_usage,
                     files_modified, unknowns, handoff_path)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                checkpoint_id,
                agent_id,
                self.session_id,
                phase,
                context_usage,
                json.dumps(files_modified or []),
                json.dumps(unknowns or []),
                handoff_path,
            )

        return checkpoint_id

    async def get_latest_checkpoint(self) -> dict[str, Any] | None:
        """Get the most recent checkpoint for this agent/session.

        Returns:
            Checkpoint dict or None if no checkpoints exist
        """
        agent_id = self.agent_id or "main"

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, agent_id, session_id, phase, context_usage,
                       files_modified, unknowns, handoff_path, created_at
                FROM checkpoints
                WHERE agent_id = $1 AND session_id = $2
                ORDER BY created_at DESC
                LIMIT 1
                """,
                agent_id,
                self.session_id,
            )

            if row is None:
                return None

            return {
                "id": str(row["id"]),
                "agent_id": row["agent_id"],
                "session_id": row["session_id"],
                "phase": row["phase"],
                "context_usage": row["context_usage"],
                "files_modified": self._safe_json_loads(row["files_modified"], []),
                "unknowns": self._safe_json_loads(row["unknowns"], []),
                "handoff_path": row["handoff_path"],
                "created_at": row["created_at"],
            }

    async def get_checkpoints(
        self,
        limit: int = 10,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get checkpoints for this agent/session.

        Args:
            limit: Maximum number of checkpoints to return
            since: Optional datetime to filter checkpoints after

        Returns:
            List of checkpoint dicts, most recent first
        """
        agent_id = self.agent_id or "main"

        async with get_connection() as conn:
            if since is not None:
                rows = await conn.fetch(
                    """
                    SELECT id, agent_id, session_id, phase, context_usage,
                           files_modified, unknowns, handoff_path, created_at
                    FROM checkpoints
                    WHERE agent_id = $1 AND session_id = $2 AND created_at >= $3
                    ORDER BY created_at DESC
                    LIMIT $4
                    """,
                    agent_id,
                    self.session_id,
                    since,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, agent_id, session_id, phase, context_usage,
                           files_modified, unknowns, handoff_path, created_at
                    FROM checkpoints
                    WHERE agent_id = $1 AND session_id = $2
                    ORDER BY created_at DESC
                    LIMIT $3
                    """,
                    agent_id,
                    self.session_id,
                    limit,
                )

            return [
                {
                    "id": str(row["id"]),
                    "agent_id": row["agent_id"],
                    "session_id": row["session_id"],
                    "phase": row["phase"],
                    "context_usage": row["context_usage"],
                    "files_modified": self._safe_json_loads(row["files_modified"], []),
                    "unknowns": self._safe_json_loads(row["unknowns"], []),
                    "handoff_path": row["handoff_path"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint ID to delete

        Returns:
            True if deleted, False if not found

        Note:
            Filters by agent_id and session_id for consistency with
            get_latest_checkpoint and get_checkpoints.
        """
        agent_id = self.agent_id or "main"

        async with get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM checkpoints
                WHERE id = $1 AND agent_id = $2 AND session_id = $3
                """,
                checkpoint_id,
                agent_id,
                self.session_id,
            )
            return result == "DELETE 1"

    async def cleanup_old_checkpoints(
        self,
        keep_count: int = 5,
    ) -> int:
        """Delete old checkpoints, keeping only the most recent ones.

        Args:
            keep_count: Number of recent checkpoints to keep per agent

        Returns:
            Number of checkpoints deleted
        """
        agent_id = self.agent_id or "main"

        async with get_transaction() as conn:
            # Get IDs to keep
            keep_rows = await conn.fetch(
                """
                SELECT id FROM checkpoints
                WHERE agent_id = $1 AND session_id = $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                agent_id,
                self.session_id,
                keep_count,
            )
            keep_ids = [str(row["id"]) for row in keep_rows]

            if not keep_ids:
                return 0

            # Delete all others
            result = await conn.execute(
                """
                DELETE FROM checkpoints
                WHERE agent_id = $1 AND session_id = $2
                AND id != ALL($3::uuid[])
                """,
                agent_id,
                self.session_id,
                keep_ids,
            )

            # Parse "DELETE N" to get count
            if result and result.startswith("DELETE "):
                return int(result.split()[1])
            return 0

    # ==================== Agent Operations ====================

    async def register_agent(
        self,
        agent_id: str,
        premise: str | None = None,
        pattern: str | None = None,
        role: str | None = None,
        parent_agent_id: str | None = None,
        depth_level: int = 1,
        pid: int | None = None,
        swarm_id: str | None = None,
    ) -> str:
        """Register a new agent in the agents table.

        Args:
            agent_id: Unique agent identifier (e.g., "kraken-abc123")
            premise: Task description/goal for this agent
            pattern: Multi-agent pattern (e.g., "map-reduce", "pipeline")
            role: Role within pattern (e.g., "mapper", "reducer")
            parent_agent_id: UUID of parent agent if spawned by another agent
            depth_level: Nesting depth (1 = top-level)
            pid: Process ID if running as subprocess
            swarm_id: Optional swarm grouping for batch operations

        Returns:
            UUID of the registered agent
        """
        db_id = generate_memory_id()

        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO agents
                    (id, session_id, agent_id, premise, pattern, role,
                     parent_agent_id, depth_level, pid, swarm_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                db_id,
                self.session_id,
                agent_id,
                premise,
                pattern,
                role,
                parent_agent_id,
                depth_level,
                pid,
                swarm_id or self.session_id,
            )

        return db_id

    async def update_agent_status(
        self,
        agent_id: str,
        status: str,
        error_message: str | None = None,
        result_summary: str | None = None,
    ) -> bool:
        """Update agent status.

        Args:
            agent_id: The agent_id (not UUID)
            status: New status ('running', 'completed', 'failed', 'orphaned', 'killed')
            error_message: Optional error message for failed status
            result_summary: Optional result summary for completed status

        Returns:
            True if updated, False if agent not found
        """
        async with get_transaction() as conn:
            if status in ('completed', 'failed'):
                result = await conn.execute(
                    """
                    UPDATE agents
                    SET status = $1, error_message = $2, result_summary = $3,
                        completed_at = NOW()
                    WHERE agent_id = $4 AND session_id = $5
                    """,
                    status,
                    error_message,
                    result_summary,
                    agent_id,
                    self.session_id,
                )
            else:
                result = await conn.execute(
                    """
                    UPDATE agents
                    SET status = $1
                    WHERE agent_id = $2 AND session_id = $3
                    """,
                    status,
                    agent_id,
                    self.session_id,
                )
            return result == "UPDATE 1"

    async def update_agent_observability(
        self,
        agent_id: str,
        current_todos: list[dict] | None = None,
        last_tool: str | None = None,
        context_usage: float | None = None,
    ) -> bool:
        """Update agent observability fields for TUI/HUD.

        Args:
            agent_id: The agent_id (not UUID)
            current_todos: Current todo list as JSON
            last_tool: Name of last tool used
            context_usage: Current context usage (0.0 to 1.0)

        Returns:
            True if updated, False if agent not found
        """
        updates = []
        params: list[Any] = []
        param_idx = 1

        if current_todos is not None:
            updates.append(f"current_todos = ${param_idx}")
            params.append(json.dumps(current_todos))
            param_idx += 1

        if last_tool is not None:
            updates.append(f"last_tool = ${param_idx}, last_tool_at = NOW()")
            params.append(last_tool)
            param_idx += 1

        if context_usage is not None:
            updates.append(f"context_usage = ${param_idx}")
            params.append(context_usage)
            param_idx += 1

        if not updates:
            return False

        params.extend([agent_id, self.session_id])

        async with get_connection() as conn:
            result = await conn.execute(
                f"""
                UPDATE agents
                SET {', '.join(updates)}
                WHERE agent_id = ${param_idx} AND session_id = ${param_idx + 1}
                """,
                *params,
            )
            return result == "UPDATE 1"

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent by agent_id.

        Args:
            agent_id: The agent_id (not UUID)

        Returns:
            Agent dict or None if not found
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, session_id, agent_id, parent_agent_id, premise,
                       pattern, role, depth_level, pid, swarm_id, status,
                       spawned_at, completed_at, error_message, result_summary,
                       current_todos, last_tool, last_tool_at, handoff_to,
                       context_usage
                FROM agents
                WHERE agent_id = $1 AND session_id = $2
                """,
                agent_id,
                self.session_id,
            )

            if row is None:
                return None

            return self._row_to_agent_dict(row)

    async def get_session_agents(
        self,
        status: str | None = None,
        pattern: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all agents for this session.

        Args:
            status: Optional filter by status
            pattern: Optional filter by pattern

        Returns:
            List of agent dicts
        """
        conditions = ["session_id = $1"]
        params: list[Any] = [self.session_id]
        param_idx = 2

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if pattern:
            conditions.append(f"pattern = ${param_idx}")
            params.append(pattern)

        async with get_connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, session_id, agent_id, parent_agent_id, premise,
                       pattern, role, depth_level, pid, swarm_id, status,
                       spawned_at, completed_at, error_message, result_summary,
                       current_todos, last_tool, last_tool_at, handoff_to,
                       context_usage
                FROM agents
                WHERE {' AND '.join(conditions)}
                ORDER BY spawned_at DESC
                """,
                *params,
            )

            return [self._row_to_agent_dict(row) for row in rows]

    async def get_running_agents(self) -> list[dict[str, Any]]:
        """Get all currently running agents in this session."""
        return await self.get_session_agents(status='running')

    async def kill_swarm(self, swarm_id: str) -> int:
        """Mark all agents in a swarm as killed.

        Args:
            swarm_id: Swarm identifier

        Returns:
            Number of agents killed
        """
        async with get_transaction() as conn:
            result = await conn.execute(
                """
                UPDATE agents
                SET status = 'killed', completed_at = NOW()
                WHERE swarm_id = $1 AND session_id = $2 AND status = 'running'
                """,
                swarm_id,
                self.session_id,
            )
            if result and result.startswith("UPDATE "):
                return int(result.split()[1])
            return 0

    def _row_to_agent_dict(self, row) -> dict[str, Any]:
        """Convert a database row to agent dict."""
        return {
            "id": str(row["id"]),
            "session_id": row["session_id"],
            "agent_id": row["agent_id"],
            "parent_agent_id": str(row["parent_agent_id"]) if row["parent_agent_id"] else None,
            "premise": row["premise"],
            "pattern": row["pattern"],
            "role": row["role"],
            "depth_level": row["depth_level"],
            "pid": row["pid"],
            "swarm_id": row["swarm_id"],
            "status": row["status"],
            "spawned_at": row["spawned_at"],
            "completed_at": row["completed_at"],
            "error_message": row["error_message"],
            "result_summary": row["result_summary"],
            "current_todos": row["current_todos"] if isinstance(row["current_todos"], list) else (json.loads(row["current_todos"]) if row["current_todos"] else []),
            "last_tool": row["last_tool"],
            "last_tool_at": row["last_tool_at"],
            "handoff_to": str(row["handoff_to"]) if row["handoff_to"] else None,
            "context_usage": row["context_usage"],
        }

    # ==================== Blackboard Operations ====================

    async def post_message(
        self,
        swarm_id: str,
        sender_agent: str,
        message_type: str,
        payload: dict[str, Any],
        target_agent: str | None = None,
        priority: str = "normal",
    ) -> str:
        """Post a message to the blackboard.

        Args:
            swarm_id: Swarm identifier for message routing
            sender_agent: Agent ID of the sender
            message_type: One of 'request', 'response', 'status', 'directive', 'checkpoint'
            payload: Message content as dict
            target_agent: Specific recipient (None = broadcast)
            priority: Message priority ('low', 'normal', 'high', 'critical')

        Returns:
            Message UUID
        """
        message_id = generate_memory_id()

        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO blackboard
                    (id, swarm_id, sender_agent, message_type, target_agent,
                     priority, payload)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                message_id,
                swarm_id,
                sender_agent,
                message_type,
                target_agent,
                priority,
                json.dumps(payload),
            )

        return message_id

    async def read_messages(
        self,
        swarm_id: str,
        reader_agent: str,
        unread_only: bool = True,
        message_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Read messages from the blackboard.

        Args:
            swarm_id: Swarm to read from
            reader_agent: Agent ID of the reader (for tracking read status)
            unread_only: Only return messages not yet read by this agent
            message_types: Optional filter by message types
            limit: Max messages to return

        Returns:
            List of message dicts
        """
        conditions = ["swarm_id = $1", "archived_at IS NULL"]
        params: list[Any] = [swarm_id]
        param_idx = 2

        # Filter for messages targeted to this agent or broadcasts
        conditions.append(f"(target_agent IS NULL OR target_agent = ${param_idx})")
        params.append(reader_agent)
        param_idx += 1

        if unread_only:
            conditions.append(f"NOT (read_by ? ${param_idx})")
            params.append(reader_agent)
            param_idx += 1

        if message_types:
            conditions.append(f"message_type = ANY(${param_idx})")
            params.append(message_types)
            param_idx += 1

        params.append(limit)

        async with get_connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, swarm_id, sender_agent, message_type, target_agent,
                       priority, payload, created_at, read_by
                FROM blackboard
                WHERE {' AND '.join(conditions)}
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    created_at ASC
                LIMIT ${param_idx}
                """,
                *params,
            )

            return [
                {
                    "id": str(row["id"]),
                    "swarm_id": row["swarm_id"],
                    "sender_agent": row["sender_agent"],
                    "message_type": row["message_type"],
                    "target_agent": row["target_agent"],
                    "priority": row["priority"],
                    "payload": row["payload"] if isinstance(row["payload"], dict) else (json.loads(row["payload"]) if row["payload"] else {}),
                    "created_at": row["created_at"],
                    "read_by": row["read_by"] if isinstance(row["read_by"], list) else (json.loads(row["read_by"]) if row["read_by"] else []),
                }
                for row in rows
            ]

    async def mark_messages_read(
        self,
        message_ids: list[str],
        reader_agent: str,
    ) -> int:
        """Mark messages as read by an agent.

        Args:
            message_ids: List of message UUIDs
            reader_agent: Agent ID that read the messages

        Returns:
            Number of messages marked as read
        """
        if not message_ids:
            return 0

        # Use transaction with row locking to prevent race condition
        # where concurrent calls could add duplicate entries to read_by
        async with get_transaction() as conn:
            result = await conn.execute(
                """
                UPDATE blackboard
                SET read_by = read_by || to_jsonb($1::text)
                WHERE id IN (
                    SELECT id FROM blackboard
                    WHERE id = ANY($2::uuid[])
                    AND NOT (read_by ? $1)
                    FOR UPDATE SKIP LOCKED
                )
                """,
                reader_agent,
                message_ids,
            )
            if result and result.startswith("UPDATE "):
                return int(result.split()[1])
            return 0

    async def archive_old_messages(
        self,
        swarm_id: str,
        older_than_hours: int = 24,
    ) -> int:
        """Archive old messages from a swarm.

        Args:
            swarm_id: Swarm to clean up
            older_than_hours: Archive messages older than this

        Returns:
            Number of messages archived
        """
        async with get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE blackboard
                SET archived_at = NOW()
                WHERE swarm_id = $1
                AND archived_at IS NULL
                AND created_at < NOW() - INTERVAL '1 hour' * $2
                """,
                swarm_id,
                older_than_hours,
            )
            if result and result.startswith("UPDATE "):
                return int(result.split()[1])
            return 0

    # ==================== Agent Logs Operations ====================

    async def log(
        self,
        level: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Write a log entry from this agent.

        Args:
            level: Log level ('debug', 'info', 'warn', 'error')
            message: Log message
            metadata: Optional additional metadata

        Returns:
            Log entry UUID
        """
        log_id = generate_memory_id()
        agent_id = self.agent_id or "main"

        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO agent_logs
                    (id, agent_id, session_id, level, message, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                log_id,
                agent_id,
                self.session_id,
                level,
                message,
                json.dumps(metadata or {}),
            )

        return log_id

    async def get_logs(
        self,
        level: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get log entries for this session.

        Args:
            level: Optional filter by level
            agent_id: Optional filter by specific agent
            limit: Max entries to return

        Returns:
            List of log entry dicts
        """
        conditions = ["session_id = $1"]
        params: list[Any] = [self.session_id]
        param_idx = 2

        if level:
            conditions.append(f"level = ${param_idx}")
            params.append(level)
            param_idx += 1

        if agent_id:
            conditions.append(f"agent_id = ${param_idx}")
            params.append(agent_id)
            param_idx += 1

        params.append(limit)

        async with get_connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, agent_id, session_id, level, message, metadata, created_at
                FROM agent_logs
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ${param_idx}
                """,
                *params,
            )

            return [
                {
                    "id": str(row["id"]),
                    "agent_id": row["agent_id"],
                    "session_id": row["session_id"],
                    "level": row["level"],
                    "message": row["message"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    async def get_errors(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent error logs for this session."""
        return await self.get_logs(level='error', limit=limit)

    # ==================== Temporal Facts Operations ====================

    async def store_fact(
        self,
        fact_type: str,
        content: str,
        confidence: float = 1.0,
        source_turn: int | None = None,
        expires_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> str:
        """Store a temporal fact with optional expiration.

        Args:
            fact_type: Type of fact ('observation', 'decision', 'learning', 'preference')
            content: Fact content
            confidence: Confidence level (0.0 to 1.0)
            source_turn: Turn number where fact was created
            expires_at: Optional expiration time
            metadata: Optional additional metadata
            embedding: Optional pre-computed embedding (1536 dims for ada-002)

        Returns:
            Fact UUID
        """
        fact_id = generate_memory_id()

        async with get_transaction() as conn:
            if embedding and len(embedding) > 0:
                await init_pgvector(conn)
                await conn.execute(
                    """
                    INSERT INTO temporal_facts
                        (id, session_id, fact_type, content, confidence,
                         source_turn, expires_at, metadata, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    fact_id,
                    self.session_id,
                    fact_type,
                    content,
                    confidence,
                    source_turn,
                    expires_at,
                    json.dumps(metadata or {}),
                    embedding,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO temporal_facts
                        (id, session_id, fact_type, content, confidence,
                         source_turn, expires_at, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    fact_id,
                    self.session_id,
                    fact_type,
                    content,
                    confidence,
                    source_turn,
                    expires_at,
                    json.dumps(metadata or {}),
                )

        return fact_id

    async def get_active_facts(
        self,
        fact_type: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get active (non-expired) facts.

        Args:
            fact_type: Optional filter by type
            min_confidence: Minimum confidence threshold
            limit: Max facts to return

        Returns:
            List of fact dicts
        """
        conditions = [
            "session_id = $1",
            "(expires_at IS NULL OR expires_at > NOW())",
            "confidence >= $2",
        ]
        params: list[Any] = [self.session_id, min_confidence]
        param_idx = 3

        if fact_type:
            conditions.append(f"fact_type = ${param_idx}")
            params.append(fact_type)
            param_idx += 1

        params.append(limit)

        async with get_connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, session_id, fact_type, content, confidence,
                       source_turn, created_at, expires_at, metadata
                FROM temporal_facts
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ${param_idx}
                """,
                *params,
            )

            return [
                {
                    "id": str(row["id"]),
                    "session_id": row["session_id"],
                    "fact_type": row["fact_type"],
                    "content": row["content"],
                    "confidence": row["confidence"],
                    "source_turn": row["source_turn"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                }
                for row in rows
            ]

    async def expire_old_facts(self) -> int:
        """Remove expired facts from this session.

        Returns:
            Number of facts deleted
        """
        async with get_transaction() as conn:
            result = await conn.execute(
                """
                DELETE FROM temporal_facts
                WHERE session_id = $1
                AND expires_at IS NOT NULL
                AND expires_at < NOW()
                """,
                self.session_id,
            )
            if result and result.startswith("DELETE "):
                return int(result.split()[1])
            return 0

    # ==================== User Preferences Operations ====================

    async def record_preference(
        self,
        user_id: str,
        proposition: str,
        choice: str,
        context: str | None = None,
    ) -> None:
        """Record or update a user preference.

        Uses upsert to increment count if preference already exists.

        Args:
            user_id: User identifier
            proposition: The proposition/question
            choice: The user's choice
            context: Optional context for this preference
        """
        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO user_preferences
                    (user_id, proposition, choice, context, count, last_used)
                VALUES ($1, $2, $3, $4, 1, NOW())
                ON CONFLICT (user_id, proposition, choice)
                DO UPDATE SET
                    count = user_preferences.count + 1,
                    last_used = NOW(),
                    context = COALESCE(EXCLUDED.context, user_preferences.context)
                """,
                user_id,
                proposition,
                choice,
                context,
            )

    async def get_preferences(
        self,
        user_id: str,
        proposition: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get user preferences.

        Args:
            user_id: User identifier
            proposition: Optional filter by proposition

        Returns:
            List of preference dicts sorted by count (most chosen first)
        """
        conditions = ["user_id = $1"]
        params: list[Any] = [user_id]
        param_idx = 2

        if proposition:
            conditions.append(f"proposition = ${param_idx}")
            params.append(proposition)

        async with get_connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, user_id, proposition, choice, context, count, last_used
                FROM user_preferences
                WHERE {' AND '.join(conditions)}
                ORDER BY count DESC, last_used DESC
                """,
                *params,
            )

            return [
                {
                    "id": str(row["id"]),
                    "user_id": row["user_id"],
                    "proposition": row["proposition"],
                    "choice": row["choice"],
                    "context": row["context"],
                    "count": row["count"],
                    "last_used": row["last_used"],
                }
                for row in rows
            ]

    async def get_preferred_choice(
        self,
        user_id: str,
        proposition: str,
    ) -> str | None:
        """Get the most preferred choice for a proposition.

        Args:
            user_id: User identifier
            proposition: The proposition to query

        Returns:
            Most chosen option or None if no preferences
        """
        prefs = await self.get_preferences(user_id, proposition)
        return prefs[0]["choice"] if prefs else None

    # ==================== Sandbox Computations Operations ====================

    async def set_shared(
        self,
        key: str,
        value: Any,
        computed_by: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        """Set a shared computation result.

        Args:
            key: Unique key for this computation
            value: Result value (will be JSON serialized)
            computed_by: Agent ID that computed this value
            expires_at: Optional expiration time
        """
        agent_id = computed_by or self.agent_id or "main"

        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO sandbox_computations
                    (session_id, key, value, computed_by, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (session_id, key)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    computed_by = EXCLUDED.computed_by,
                    created_at = NOW(),
                    expires_at = EXCLUDED.expires_at
                """,
                self.session_id,
                key,
                json.dumps(value),
                agent_id,
                expires_at,
            )

    async def get_shared(self, key: str) -> Any | None:
        """Get a shared computation result.

        Args:
            key: Key to retrieve

        Returns:
            Value or None if not found/expired
        """
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT value FROM sandbox_computations
                WHERE session_id = $1 AND key = $2
                AND (expires_at IS NULL OR expires_at > NOW())
                """,
                self.session_id,
                key,
            )
            if row:
                return json.loads(row["value"])
            return None

    async def delete_shared(self, key: str) -> bool:
        """Delete a shared computation.

        Args:
            key: Key to delete

        Returns:
            True if deleted, False if not found
        """
        async with get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM sandbox_computations
                WHERE session_id = $1 AND key = $2
                """,
                self.session_id,
                key,
            )
            return result == "DELETE 1"

    async def list_shared(self) -> list[dict[str, Any]]:
        """List all shared computations for this session.

        Returns:
            List of computation dicts
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT key, value, computed_by, created_at, expires_at
                FROM sandbox_computations
                WHERE session_id = $1
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY created_at DESC
                """,
                self.session_id,
            )

            return [
                {
                    "key": row["key"],
                    "value": json.loads(row["value"]) if row["value"] else None,
                    "computed_by": row["computed_by"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                }
                for row in rows
            ]

    # ==================== Spawn Queue Operations ====================

    async def request_spawn(
        self,
        requester_agent: str,
        target_agent_type: str,
        payload: dict[str, Any],
        depth_level: int = 1,
        priority: str = "normal",
        depends_on: list[str] | None = None,
    ) -> str:
        """Request a new agent spawn.

        Args:
            requester_agent: Agent ID requesting the spawn
            target_agent_type: Type of agent to spawn (e.g., 'kraken', 'scout')
            payload: Task description and context
            depth_level: Nesting depth
            priority: Spawn priority ('low', 'normal', 'high', 'critical')
            depends_on: List of spawn request UUIDs this depends on

        Returns:
            Spawn request UUID
        """
        request_id = generate_memory_id()
        deps = depends_on or []
        blocked_count = len(deps)

        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO spawn_queue
                    (id, requester_agent, target_agent_type, depth_level,
                     priority, payload, depends_on, blocked_by_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                request_id,
                requester_agent,
                target_agent_type,
                depth_level,
                priority,
                json.dumps(payload),
                deps,
                blocked_count,
            )

        return request_id

    async def get_ready_spawns(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get spawn requests ready to execute (no blockers).

        Uses the partial index for O(1) lookup.

        Args:
            limit: Max requests to return

        Returns:
            List of ready spawn request dicts
        """
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, requester_agent, target_agent_type, depth_level,
                       priority, status, payload, created_at, depends_on
                FROM spawn_queue
                WHERE status = 'pending' AND blocked_by_count = 0
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    created_at ASC
                LIMIT $1
                """,
                limit,
            )

            return [
                {
                    "id": str(row["id"]),
                    "requester_agent": row["requester_agent"],
                    "target_agent_type": row["target_agent_type"],
                    "depth_level": row["depth_level"],
                    "priority": row["priority"],
                    "status": row["status"],
                    "payload": json.loads(row["payload"]) if row["payload"] else {},
                    "created_at": row["created_at"],
                    "depends_on": row["depends_on"] or [],
                }
                for row in rows
            ]

    async def approve_spawn(
        self,
        request_id: str,
        spawned_agent_id: str | None = None,
    ) -> bool:
        """Approve and optionally mark a spawn request as spawned.

        Also decrements blocked_by_count for dependent requests (Kahn's algorithm).

        Args:
            request_id: Spawn request UUID
            spawned_agent_id: UUID of the spawned agent (if already spawned)

        Returns:
            True if approved, False if not found
        """
        new_status = 'spawned' if spawned_agent_id else 'approved'

        async with get_transaction() as conn:
            # Update the request
            result = await conn.execute(
                """
                UPDATE spawn_queue
                SET status = $1, processed_at = NOW(), spawned_agent_id = $2
                WHERE id = $3 AND status = 'pending'
                """,
                new_status,
                spawned_agent_id,
                request_id,
            )

            if result != "UPDATE 1":
                return False

            # Decrement blocked_by_count for requests depending on this one
            await conn.execute(
                """
                UPDATE spawn_queue
                SET blocked_by_count = blocked_by_count - 1
                WHERE $1 = ANY(depends_on)
                AND status = 'pending'
                """,
                request_id,
            )

            return True

    async def reject_spawn(
        self,
        request_id: str,
    ) -> bool:
        """Reject a spawn request.

        Also decrements blocked_by_count for dependent requests to prevent deadlock.

        Args:
            request_id: Spawn request UUID

        Returns:
            True if rejected, False if not found
        """
        async with get_transaction() as conn:
            # Update the request status
            result = await conn.execute(
                """
                UPDATE spawn_queue
                SET status = 'rejected', processed_at = NOW()
                WHERE id = $1 AND status = 'pending'
                """,
                request_id,
            )

            if result != "UPDATE 1":
                return False

            # Decrement blocked_by_count for requests depending on this one
            # (same as approve_spawn - prevents deadlock from stuck dependents)
            await conn.execute(
                """
                UPDATE spawn_queue
                SET blocked_by_count = blocked_by_count - 1
                WHERE $1 = ANY(depends_on)
                AND status = 'pending'
                """,
                request_id,
            )

            return True

    async def get_spawn_queue(
        self,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get spawn queue entries.

        Args:
            status: Optional filter by status

        Returns:
            List of spawn request dicts
        """
        conditions = []
        params: list[Any] = []
        param_idx = 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with get_connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, requester_agent, target_agent_type, depth_level,
                       priority, status, payload, created_at, processed_at,
                       spawned_agent_id, depends_on, blocked_by_count
                FROM spawn_queue
                {where_clause}
                ORDER BY created_at DESC
                """,
                *params,
            )

            return [
                {
                    "id": str(row["id"]),
                    "requester_agent": row["requester_agent"],
                    "target_agent_type": row["target_agent_type"],
                    "depth_level": row["depth_level"],
                    "priority": row["priority"],
                    "status": row["status"],
                    "payload": json.loads(row["payload"]) if row["payload"] else {},
                    "created_at": row["created_at"],
                    "processed_at": row["processed_at"],
                    "spawned_agent_id": str(row["spawned_agent_id"]) if row["spawned_agent_id"] else None,
                    "depends_on": row["depends_on"] or [],
                    "blocked_by_count": row["blocked_by_count"],
                }
                for row in rows
            ]
