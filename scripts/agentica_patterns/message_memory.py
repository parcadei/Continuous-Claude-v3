"""Message Memory Service for conversation search (Phase 3.6).

Stores and searches conversation messages for recall.
Implements Letta's conversation_search pattern.

Features:
- Store messages with role (user/assistant/tool)
- Full-text search with PostgreSQL tsvector
- Role-based filtering
- Temporal filtering (start_date, end_date)
- Pagination (limit, offset)
- Session isolation

Usage:
    service = MessageMemoryService(session_id="abc123")

    # Store messages
    await service.store_message("Hello!", role="user")
    await service.store_message("Hi there!", role="assistant")

    # Search conversations
    results = await service.conversation_search("hello", limit=10)

    # Filter by role
    results = await service.conversation_search("hello", roles=["user"])

    # Get recent messages for context
    recent = await service.get_recent_messages(limit=20)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from .postgres_pool import get_connection


@dataclass
class Message:
    """A conversation message."""

    id: str
    content: str
    role: str  # "user" | "assistant" | "tool"
    created_at: datetime
    agent_id: str | None = None


class MessageMemoryService:
    """Service for storing and searching conversation messages.

    Scoping model:
    - session_id: Claude Code session (required)
    - agent_id: Optional agent identifier within session
    """

    def __init__(self, session_id: str, agent_id: str | None = None):
        """Initialize message memory service.

        Args:
            session_id: Session identifier for isolation
            agent_id: Optional agent identifier
        """
        self.session_id = session_id
        self.agent_id = agent_id

    async def store_message(
        self,
        content: str,
        role: Literal["user", "assistant", "tool"],
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store a conversation message.

        Args:
            content: Message content
            role: Message role ("user", "assistant", or "tool")
            embedding: Optional embedding vector (will be stored as-is)
            metadata: Optional metadata dict

        Returns:
            Message ID (UUID string)

        Raises:
            ValueError/PostgresError: If role is invalid
        """
        async with get_connection() as conn:
            if embedding is not None:
                from .postgres_pool import init_pgvector

                await init_pgvector(conn)

                msg_id = await conn.fetchval(
                    """
                    INSERT INTO memory_messages
                        (session_id, agent_id, content, role, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    self.session_id,
                    self.agent_id,
                    content,
                    role,
                    embedding,
                    json.dumps(metadata or {}),
                )
            else:
                msg_id = await conn.fetchval(
                    """
                    INSERT INTO memory_messages
                        (session_id, agent_id, content, role, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    self.session_id,
                    self.agent_id,
                    content,
                    role,
                    json.dumps(metadata or {}),
                )

            return str(msg_id)

    async def conversation_search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        roles: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        search_mode: Literal["fts", "vector", "hybrid"] = "hybrid",
    ) -> list[dict[str, Any]]:
        """Search conversation history.

        Args:
            query: Search query for full-text search
            limit: Maximum results to return (default: 10)
            offset: Number of results to skip for pagination (default: 0)
            roles: Optional list of roles to filter by (e.g., ["user", "assistant"])
            start_date: Optional start of date range (inclusive)
            end_date: Optional end of date range (inclusive)
            search_mode: Search mode - "fts", "vector", or "hybrid" (default: "hybrid")

        Returns:
            List of dicts with keys: id, content, role, created_at, score
        """
        async with get_connection() as conn:
            # Build dynamic WHERE clause
            conditions = ["session_id = $1"]
            params: list[Any] = [self.session_id]
            param_idx = 2

            if roles:
                conditions.append(f"role = ANY(${param_idx})")
                params.append(roles)
                param_idx += 1

            if start_date:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(start_date)
                param_idx += 1

            if end_date:
                conditions.append(f"created_at <= ${param_idx}")
                params.append(end_date)
                param_idx += 1

            where_clause = " AND ".join(conditions)

            # FTS query with ranking
            # Note: search_mode="hybrid" and "vector" currently fall back to FTS
            # Vector search requires embedding the query first (future enhancement)
            query_param_idx = param_idx
            params.append(query)
            param_idx += 1

            limit_param_idx = param_idx
            params.append(limit)
            param_idx += 1

            offset_param_idx = param_idx
            params.append(offset)

            sql = f"""
                SELECT
                    id,
                    content,
                    role,
                    created_at,
                    ts_rank(
                        to_tsvector('english', content),
                        plainto_tsquery('english', ${query_param_idx})
                    ) as score
                FROM memory_messages
                WHERE {where_clause}
                  AND to_tsvector('english', content) @@ plainto_tsquery('english', ${query_param_idx})
                ORDER BY score DESC, created_at DESC
                LIMIT ${limit_param_idx}
                OFFSET ${offset_param_idx}
            """

            rows = await conn.fetch(sql, *params)

            return [
                {
                    "id": str(row["id"]),
                    "content": row["content"],
                    "role": row["role"],
                    "created_at": row["created_at"].isoformat(),
                    "score": float(row["score"]),
                }
                for row in rows
            ]

    async def get_recent_messages(
        self,
        limit: int = 20,
        role: str | None = None,
    ) -> list[Message]:
        """Get recent messages for context.

        Args:
            limit: Maximum messages to return (default: 20)
            role: Optional role filter ("user", "assistant", "tool")

        Returns:
            List of Message objects, most recent first
        """
        async with get_connection() as conn:
            conditions = ["session_id = $1"]
            params: list[Any] = [self.session_id]

            if role:
                conditions.append("role = $2")
                params.append(role)

            where_clause = " AND ".join(conditions)
            limit_idx = len(params) + 1
            params.append(limit)

            sql = f"""
                SELECT id, content, role, agent_id, created_at
                FROM memory_messages
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${limit_idx}
            """

            rows = await conn.fetch(sql, *params)

            return [
                Message(
                    id=str(row["id"]),
                    content=row["content"],
                    role=row["role"],
                    agent_id=row["agent_id"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    async def search_hybrid(
        self,
        text_query: str,
        query_embedding: list[float],
        limit: int = 10,
        offset: int = 0,
        roles: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        text_weight: float = 0.3,
        vector_weight: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining FTS and vector similarity.

        Uses weighted combination of text rank and cosine similarity.

        Args:
            text_query: Text query for FTS
            query_embedding: Query embedding for vector search
            limit: Maximum results
            offset: Pagination offset
            roles: Optional role filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            text_weight: Weight for text score (default: 0.3)
            vector_weight: Weight for vector similarity (default: 0.7)

        Returns:
            List of results with combined score
        """
        from .postgres_pool import init_pgvector

        async with get_connection() as conn:
            await init_pgvector(conn)

            # Build dynamic WHERE clause
            conditions = ["session_id = $1"]
            params: list[Any] = [self.session_id]
            param_idx = 2

            if roles:
                conditions.append(f"role = ANY(${param_idx})")
                params.append(roles)
                param_idx += 1

            if start_date:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(start_date)
                param_idx += 1

            if end_date:
                conditions.append(f"created_at <= ${param_idx}")
                params.append(end_date)
                param_idx += 1

            where_clause = " AND ".join(conditions)

            # Add remaining parameters
            text_query_idx = param_idx
            params.append(text_query)
            param_idx += 1

            embedding_idx = param_idx
            params.append(query_embedding)
            param_idx += 1

            text_weight_idx = param_idx
            params.append(text_weight)
            param_idx += 1

            vector_weight_idx = param_idx
            params.append(vector_weight)
            param_idx += 1

            limit_idx = param_idx
            params.append(limit)
            param_idx += 1

            offset_idx = param_idx
            params.append(offset)

            sql = f"""
                SELECT
                    id,
                    content,
                    role,
                    created_at,
                    ts_rank(
                        to_tsvector('english', content),
                        plainto_tsquery('english', ${text_query_idx})
                    ) as text_rank,
                    CASE
                        WHEN embedding IS NOT NULL
                        THEN 1 - (embedding <=> ${embedding_idx}::vector)
                        ELSE 0
                    END as similarity,
                    (
                        ${text_weight_idx} * COALESCE(ts_rank(
                            to_tsvector('english', content),
                            plainto_tsquery('english', ${text_query_idx})
                        ), 0) +
                        ${vector_weight_idx} * CASE
                            WHEN embedding IS NOT NULL
                            THEN 1 - (embedding <=> ${embedding_idx}::vector)
                            ELSE 0
                        END
                    ) as combined_score
                FROM memory_messages
                WHERE {where_clause}
                AND (
                    to_tsvector('english', content) @@ plainto_tsquery('english', ${text_query_idx})
                    OR embedding IS NOT NULL
                )
                ORDER BY combined_score DESC, created_at DESC
                LIMIT ${limit_idx}
                OFFSET ${offset_idx}
            """

            rows = await conn.fetch(sql, *params)

            return [
                {
                    "id": str(row["id"]),
                    "content": row["content"],
                    "role": row["role"],
                    "created_at": row["created_at"].isoformat(),
                    "text_rank": float(row["text_rank"]) if row["text_rank"] else 0.0,
                    "similarity": float(row["similarity"]) if row["similarity"] else 0.0,
                    "combined_score": float(row["combined_score"]),
                }
                for row in rows
            ]

    async def delete_message(self, message_id: str) -> None:
        """Delete a message by ID.

        Args:
            message_id: Message UUID to delete
        """
        async with get_connection() as conn:
            await conn.execute(
                """
                DELETE FROM memory_messages
                WHERE id = $1 AND session_id = $2
                """,
                message_id,
                self.session_id,
            )

    async def get_message_count(self) -> int:
        """Get total message count for this session.

        Returns:
            Number of messages in session
        """
        async with get_connection() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM memory_messages
                WHERE session_id = $1
                """,
                self.session_id,
            )
            return count or 0
