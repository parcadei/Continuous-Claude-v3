"""Memory Service with Core, Archival, and Recall memory (async).

Inspired by Letta/MemGPT memory architecture:
- Core Memory: Persistent in-context blocks (current facts)
- Archival Memory: FTS5 searchable long-term storage
- Recall Memory: Cross-source query combining all sources

Usage:
    memory = MemoryService(session_id="abc123")
    await memory.connect()

    # Core memory (in-context)
    await memory.set_core("persona", "You are a helpful assistant")
    await memory.set_core("task", "Build a REST API")

    # Archival memory (searchable)
    await memory.store("User prefers Python over JavaScript")
    await memory.store("Project uses PostgreSQL database")

    # Recall (cross-source query)
    result = await memory.recall("What database does the project use?")

    # Generate context for prompt
    context = await memory.to_context()

    await memory.close()
"""

import json
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import aiosqlite


def generate_memory_id() -> str:
    """Generate a UUID-based memory ID."""
    return f"mem-{uuid4().hex[:12]}"


@dataclass
class ArchivalFact:
    """A fact stored in archival memory."""

    id: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime


class MemoryService:
    """Memory service with Core, Archival, and Recall memory types.

    Architecture:
    - Core Memory: Key-value store for current session facts
    - Archival Memory: FTS5-indexed long-term storage
    - Recall Memory: Query interface combining all sources
    """

    def __init__(
        self,
        session_id: str = "default",
        db_path: Optional[Path] = None,
    ):
        """Initialize memory service.

        Args:
            session_id: Session identifier for isolation
            db_path: Optional custom database path
        """
        self.session_id = session_id

        if db_path is None:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            cache_dir = Path(project_dir) / ".claude" / "cache" / "agentica-memory"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = cache_dir / "memory.db"

        self._db_path = db_path
        self._connected = False

    @asynccontextmanager
    async def _get_conn(self):
        """Get async database connection with WAL mode and busy timeout.

        Concurrency: Uses WAL mode for better concurrent read performance
        and busy_timeout to handle lock contention gracefully.
        """
        conn = await aiosqlite.connect(str(self._db_path))
        conn.row_factory = aiosqlite.Row
        # Enable WAL mode for better concurrency (readers don't block writers)
        await conn.execute("PRAGMA journal_mode=WAL")
        # Set busy timeout to 30 seconds to handle lock contention
        # This prevents "database is locked" errors under concurrent access
        await conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
            await conn.commit()
        finally:
            await conn.close()

    async def connect(self) -> None:
        """Initialize backend connection and schema.

        Idempotent - safe to call multiple times.
        """
        if self._connected:
            return
        await self._init_schema()
        self._connected = True

    async def close(self) -> None:
        """Close backend connection.

        Idempotent - safe to call multiple times.
        """
        self._connected = False

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        async with self._get_conn() as conn:
            await conn.executescript("""
                -- Core memory (key-value)
                CREATE TABLE IF NOT EXISTS core_memory (
                    session_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (session_id, key)
                );

                -- Archival memory
                CREATE TABLE IF NOT EXISTS archival_memory (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at REAL NOT NULL
                );

                -- FTS5 virtual table for archival search
                CREATE VIRTUAL TABLE IF NOT EXISTS archival_fts USING fts5(
                    content,
                    content='archival_memory',
                    content_rowid='rowid',
                    tokenize='porter'
                );

                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS archival_ai AFTER INSERT ON archival_memory BEGIN
                    INSERT INTO archival_fts(rowid, content) VALUES (new.rowid, new.content);
                END;

                CREATE TRIGGER IF NOT EXISTS archival_ad AFTER DELETE ON archival_memory BEGIN
                    INSERT INTO archival_fts(archival_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                END;

                CREATE TRIGGER IF NOT EXISTS archival_au AFTER UPDATE ON archival_memory BEGIN
                    INSERT INTO archival_fts(archival_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                    INSERT INTO archival_fts(rowid, content) VALUES (new.rowid, new.content);
                END;

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_core_session ON core_memory(session_id);
                CREATE INDEX IF NOT EXISTS idx_archival_session ON archival_memory(session_id);
            """)

    # ==================== Core Memory ====================

    async def set_core(self, key: str, value: str) -> None:
        """Set a core memory block.

        Args:
            key: Block key (e.g., "persona", "task", "context")
            value: Block content
        """
        now = datetime.now(timezone.utc).timestamp()
        async with self._get_conn() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO core_memory (session_id, key, value, updated_at)
                VALUES (?, ?, ?, ?)
            """,
                (self.session_id, key, value, now),
            )

    async def get_core(self, key: str) -> Optional[str]:
        """Get a core memory block.

        Args:
            key: Block key

        Returns:
            Block content or None if not found
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT value FROM core_memory WHERE session_id = ? AND key = ?",
                (self.session_id, key),
            )
            row = await cursor.fetchone()
            return row["value"] if row else None

    async def list_core_keys(self) -> list[str]:
        """List all core memory block keys.

        Returns:
            List of keys
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT key FROM core_memory WHERE session_id = ? ORDER BY key",
                (self.session_id,),
            )
            rows = await cursor.fetchall()
            return [row["key"] for row in rows]

    async def delete_core(self, key: str) -> None:
        """Delete a core memory block.

        Args:
            key: Block key to delete
        """
        async with self._get_conn() as conn:
            await conn.execute(
                "DELETE FROM core_memory WHERE session_id = ? AND key = ?",
                (self.session_id, key),
            )

    async def get_all_core(self) -> dict[str, str]:
        """Get all core memory blocks.

        Returns:
            Dict of key -> value
        """
        async with self._get_conn() as conn:
            cursor = await conn.execute(
                "SELECT key, value FROM core_memory WHERE session_id = ? ORDER BY key",
                (self.session_id,),
            )
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}

    # ==================== Archival Memory ====================

    async def store(
        self,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        embedding: Optional[list[float]] = None,
    ) -> str:
        """Store a fact in archival memory.

        Args:
            content: Fact content
            metadata: Optional metadata dict
            embedding: Optional embedding vector (not used in SQLite)

        Returns:
            Memory ID
        """
        memory_id = generate_memory_id()
        now = datetime.now(timezone.utc).timestamp()

        async with self._get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO archival_memory (id, session_id, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    memory_id,
                    self.session_id,
                    content,
                    json.dumps(metadata) if metadata else None,
                    now,
                ),
            )

        return memory_id

    def _prepare_fts_query(self, query: str) -> str:
        """Prepare a query string for FTS5 MATCH.

        Converts natural language query to FTS5 OR query format.
        Each word becomes a term, joined with OR for broader matching.

        Args:
            query: Natural language query string

        Returns:
            FTS5-compatible query string
        """
        # Extract alphanumeric words
        words = re.findall(r'\w+', query.lower())
        if not words:
            return query
        # Join with OR for broader matching - any term can match
        return " OR ".join(words)

    async def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.0
    ) -> list[dict[str, Any]]:
        """Search archival memory with FTS5.

        Args:
            query: Search query
            limit: Max results to return
            threshold: Minimum relevance threshold (0.0-1.0). BM25 scores are
                      normalized to this range. Higher values return fewer,
                      more relevant results. Default 0.0 returns all matches.

        Returns:
            List of matching facts with BM25 ranking, filtered by threshold

        Note:
            BM25 scores are negative (lower = better match). We normalize them
            to 0.0-1.0 range where 1.0 is best match for threshold filtering.
        """
        fts_query = self._prepare_fts_query(query)

        async with self._get_conn() as conn:
            # Use FTS5 match with BM25 ranking
            cursor = await conn.execute(
                """
                SELECT
                    a.id,
                    a.content,
                    a.metadata_json,
                    a.created_at,
                    bm25(archival_fts) as rank
                FROM archival_memory a
                JOIN archival_fts f ON a.rowid = f.rowid
                WHERE a.session_id = ?
                AND archival_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """,
                (self.session_id, fts_query, limit),
            )
            rows = await cursor.fetchall()

            results = []
            for row in rows:
                # BM25 returns negative scores (lower = better)
                # Normalize to 0.0-1.0 range where 1.0 = best match
                # Typical BM25 scores range from -25 (best) to 0 (worst)
                raw_rank = row["rank"]
                # Normalize: -25 -> 1.0, 0 -> 0.0
                normalized_score = min(1.0, max(0.0, -raw_rank / 25.0))

                # Filter by threshold
                if normalized_score >= threshold:
                    results.append({
                        "id": row["id"],
                        "content": row["content"],
                        "metadata": json.loads(row["metadata_json"])
                        if row["metadata_json"]
                        else {},
                        "created_at": datetime.fromtimestamp(row["created_at"], tz=timezone.utc),
                        "rank": row["rank"],
                        "score": normalized_score,  # Add normalized score
                    })

            return results

    async def delete_archival(self, memory_id: str) -> None:
        """Delete a fact from archival memory.

        Args:
            memory_id: Memory ID to delete
        """
        async with self._get_conn() as conn:
            await conn.execute(
                "DELETE FROM archival_memory WHERE id = ? AND session_id = ?",
                (memory_id, self.session_id),
            )

    # ==================== Recall Memory ====================

    async def recall(self, query: str, include_core: bool = True, limit: int = 5) -> str:
        """Recall information from all memory sources.

        Args:
            query: Natural language query
            include_core: Whether to include core memory
            limit: Max archival results

        Returns:
            Combined recall result as string
        """
        parts = []

        # Check core memory first (exact key match or substring)
        if include_core:
            core = await self.get_all_core()
            for key, value in core.items():
                if query.lower() in key.lower() or key.lower() in query.lower():
                    parts.append(f"[Core/{key}]: {value}")

        # Search archival memory
        archival_results = await self.search(query, limit=limit)
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

        async with self._get_conn() as conn:
            cursor = await conn.execute(
                """
                SELECT content FROM archival_memory
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (self.session_id, max_archival),
            )
            rows = await cursor.fetchall()

            if rows:
                for row in rows:
                    lines.append(f"- {row['content']}")
            else:
                lines.append("(empty)")

        return "\n".join(lines)
