#!/usr/bin/env python3
"""
Recall Learnings with Structured Logging

Example integration showing:
- Query execution timing
- Cache behavior (hit/miss)
- Backend fallback detection
- Embedding generation metrics
- Search result scoring

Run with:
    uv run python scripts/core/recall_learnings_logged.py --query "authentication patterns"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from scripts.core.logging_config import (
    get_logger,
    setup_logging,
    generate_correlation_id,
    get_correlation_logger,
)

# Load .env
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)
load_dotenv()

project_dir = os.environ.get("CLAUDE_PROJECT_DIR", str(Path(__file__).parent.parent.parent))
sys.path.insert(0, project_dir)


# =============================================================================
# Logger Setup
# =============================================================================

logger = get_logger("recall_learnings", "recall_learnings")


# =============================================================================
# Logging Wrappers
# =============================================================================

def log_query_received(query: str, k: int, provider: str) -> str:
    """Log query reception with correlation ID."""
    correlation_id = generate_correlation_id()
    logger.info(
        "Query received",
        trace_id=correlation_id,
        operation="query_received",
        query_preview=query[:100],
        k=k,
        provider=provider,
    )
    return correlation_id


def log_cache_behavior(
    cache_hit: bool,
    query_hash: str,
    correlation_id: str,
) -> None:
    """Log cache behavior (hit or miss)."""
    logger.debug(
        f"Cache {'hit' if cache_hit else 'miss'}",
        trace_id=correlation_id,
        operation="cache_check",
        cache_hit=cache_hit,
        query_hash=query_hash,
    )


def log_embedding_generation(
    provider: str,
    correlation_id: str,
    duration_ms: float,
) -> None:
    """Log embedding generation timing."""
    logger.debug(
        "Embedding generated",
        trace_id=correlation_id,
        operation="embedding_generation",
        provider=provider,
        duration_ms=round(duration_ms, 2),
    )


def log_backend_selection(backend: str, correlation_id: str) -> None:
    """Log which backend was selected."""
    logger.info(
        "Backend selected",
        trace_id=correlation_id,
        operation="backend_selection",
        backend=backend,
    )


def log_fallback_triggered(
    from_backend: str,
    to_backend: str,
    reason: str,
    correlation_id: str,
) -> None:
    """Log when fallback to alternate backend occurs."""
    logger.warning(
        "Backend fallback triggered",
        trace_id=correlation_id,
        operation="backend_fallback",
        from_backend=from_backend,
        to_backend=to_backend,
        reason=reason,
    )


def log_search_execution(
    backend: str,
    correlation_id: str,
    duration_ms: float,
    result_count: int,
) -> None:
    """Log search execution completion."""
    logger.info(
        "Search completed",
        trace_id=correlation_id,
        operation="search_execution",
        backend=backend,
        duration_ms=round(duration_ms, 2),
        result_count=result_count,
    )


def log_result_scoring(
    result_id: str,
    similarity: float,
    rank: int,
    correlation_id: str,
) -> None:
    """Log individual result scoring details."""
    logger.debug(
        "Result scored",
        trace_id=correlation_id,
        operation="result_scoring",
        result_id=result_id,
        similarity=round(similarity, 4),
        rank=rank,
    )


def log_search_complete(
    correlation_id: str,
    total_results: int,
    total_duration_ms: float,
    has_results: bool,
) -> None:
    """Log search completion summary."""
    logger.info(
        "Search complete",
        trace_id=correlation_id,
        operation="search_complete",
        total_results=total_results,
        total_duration_ms=round(total_duration_ms, 2),
        has_results=has_results,
    )


def log_error(
    error_type: str,
    error_message: str,
    correlation_id: str,
    operation: str = "unknown",
) -> None:
    """Log error with context."""
    logger.error(
        f"Error during {operation}",
        trace_id=correlation_id,
        operation=operation,
        error_type=error_type,
        error_message=error_message,
    )


# =============================================================================
# Backend Selection with Logging
# =============================================================================

def get_backend() -> str:
    """Determine which backend to use with logging."""
    backend = os.environ.get("AGENTICA_MEMORY_BACKEND", "").lower()
    if backend in ("sqlite", "postgres"):
        log_backend_selection(backend, generate_correlation_id())
        return backend

    if os.environ.get("DATABASE_URL") or os.environ.get("CONTINUOUS_CLAUDE_DB_URL"):
        log_backend_selection("postgres", generate_correlation_id())
        return "postgres"

    log_backend_selection("sqlite", generate_correlation_id())
    return "sqlite"


# =============================================================================
# Search Functions with Logging
# =============================================================================

async def search_learnings_sqlite(
    query: str,
    k: int = 5,
    correlation_id: str = "",
) -> list[dict[str, Any]]:
    """Search SQLite with comprehensive logging."""
    import sqlite3

    start_time = datetime.now(timezone.utc).timestamp()
    db_path = Path.home() / ".claude" / "cache" / "memory.db"

    logger.debug(
        "SQLite search started",
        trace_id=correlation_id,
        operation="sqlite_search",
        db_path=str(db_path),
    )

    if not db_path.exists():
        logger.warning(
            "SQLite database not found",
            trace_id=correlation_id,
            operation="sqlite_search",
            db_path=str(db_path),
        )
        return []

    # Prepare FTS query
    words = re.findall(r"\w+", query.lower())
    fts_query = " OR ".join(words) if words else query

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.execute(
            """
            SELECT a.id, a.session_id, a.content, a.metadata_json,
                   a.created_at, bm25(archival_fts) as rank
            FROM archival_memory a
            JOIN archival_fts f ON a.rowid = f.rowid
            WHERE archival_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, k),
        )
        rows = cursor.fetchall()

        results = []
        for row in rows:
            raw_rank = row["rank"] if row["rank"] else 0
            normalized_score = min(1.0, max(0.0, -raw_rank / 25.0))

            metadata = {}
            if row["metadata_json"]:
                try:
                    metadata = json.loads(row["metadata_json"])
                except json.JSONDecodeError as e:
                    log_error(
                        "JSONDecodeError",
                        str(e),
                        correlation_id,
                        "metadata_parsing",
                    )

            results.append({
                "id": row["id"] or "",
                "session_id": row["session_id"] or "unknown",
                "content": row["content"] or "",
                "metadata": metadata,
                "created_at": datetime.fromtimestamp(row["created_at"]) if row["created_at"] else None,
                "similarity": normalized_score,
            })

            log_result_scoring(
                results[-1]["id"],
                normalized_score,
                len(results),
                correlation_id,
            )

        duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
        log_search_execution("sqlite", correlation_id, duration_ms, len(results))

        return results

    finally:
        conn.close()


async def search_learnings_postgres(
    query: str,
    k: int = 5,
    provider: str = "local",
    correlation_id: str = "",
) -> list[dict[str, Any]]:
    """Search PostgreSQL with comprehensive logging."""
    from scripts.core.db.embedding_service import EmbeddingService
    from scripts.core.db.postgres_pool import get_pool

    start_time = datetime.now(timezone.utc).timestamp()

    # Check for embeddings
    pool = await get_pool()
    async with pool.acquire() as conn:
        count_row = await conn.fetchrow("""
            SELECT COUNT(*) as cnt FROM archival_memory
            WHERE metadata->>'type' = 'session_learning' AND embedding IS NOT NULL
        """)
        has_embeddings = count_row["cnt"] > 0

    logger.debug(
        "PostgreSQL embedding check",
        trace_id=correlation_id,
        operation="postgres_embedding_check",
        has_embeddings=has_embeddings,
    )

    if not has_embeddings:
        log_fallback_triggered(
            "postgres_vector",
            "postgres_text",
            "no_embeddings_found",
            correlation_id,
        )
        return await search_learnings_text_only_postgres(query, k, correlation_id)

    # Generate embedding
    embed_start = datetime.now(timezone.utc).timestamp()
    embedder = EmbeddingService(provider=provider)
    try:
        query_embedding = await embedder.embed(query)
    finally:
        await embedder.aclose()

    embed_duration_ms = (datetime.now(timezone.utc).timestamp() - embed_start) * 1000
    log_embedding_generation(provider, correlation_id, embed_duration_ms)

    # Vector search
    async with pool.acquire() as conn:
        from scripts.core.db.postgres_pool import init_pgvector
        await init_pgvector(conn)

        rows = await conn.fetch(
            """
            SELECT id, session_id, content, metadata, created_at,
                   1 - (embedding <=> $1::vector) as similarity
            FROM archival_memory
            WHERE metadata->>'type' = 'session_learning' AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            str(query_embedding),
            k,
        )

    results = []
    for row in rows:
        similarity = float(row["similarity"]) if row["similarity"] else 0.0

        metadata = row["metadata"]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                log_error("JSONDecodeError", str(e), correlation_id, "metadata_parsing")

        results.append({
            "id": str(row["id"]),
            "session_id": row["session_id"],
            "content": row["content"],
            "metadata": metadata,
            "created_at": row["created_at"],
            "similarity": similarity,
        })

        log_result_scoring(results[-1]["id"], similarity, len(results), correlation_id)

    duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
    log_search_execution("postgres_vector", correlation_id, duration_ms, len(results))

    return results


async def search_learnings_text_only_postgres(
    query: str,
    k: int = 5,
    correlation_id: str = "",
) -> list[dict[str, Any]]:
    """Text-only PostgreSQL search with logging."""
    from scripts.core.db.postgres_pool import get_pool

    start_time = datetime.now(timezone.utc).timestamp()

    # Prepare query
    meta_words = {'help', 'want', 'need', 'show', 'tell', 'find', 'look', 'please', 'with', 'for'}
    clean_query = query.lower().replace('-', ' ')
    clean_query = ' '.join(w for w in clean_query.split() if w not in meta_words)

    words = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in clean_query.split()]
    words = [w for w in words if len(w) > 2]
    or_query = ' | '.join(words) if words else query

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, session_id, content, metadata, created_at,
                   ts_rank(to_tsvector('english', content),
                           to_tsquery('english', $1)) as similarity
            FROM archival_memory
            WHERE metadata->>'type' = 'session_learning'
                AND to_tsvector('english', content) @@ to_tsquery('english', $1)
            ORDER BY similarity DESC, created_at DESC
            LIMIT $2
            """,
            or_query,
            k,
        )

    if not rows:
        first_word = query.split()[0] if query.split() else query
        rows = await conn.fetch(
            """
            SELECT id, session_id, content, metadata, created_at, 0.1 as similarity
            FROM archival_memory
            WHERE metadata->>'type' = 'session_learning'
                AND content ILIKE '%' || $1 || '%'
            ORDER BY created_at DESC
            LIMIT $2
            """,
            first_word,
            k,
        )

    results = []
    for row in rows:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                log_error("JSONDecodeError", str(e), correlation_id, "metadata_parsing")

        results.append({
            "id": str(row["id"]),
            "session_id": row["session_id"],
            "content": row["content"],
            "metadata": metadata,
            "created_at": row["created_at"],
            "similarity": float(row["similarity"]),
        })

        log_result_scoring(results[-1]["id"], results[-1]["similarity"], len(results), correlation_id)

    duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
    log_search_execution("postgres_text", correlation_id, duration_ms, len(results))

    return results


async def search_learnings(
    query: str,
    k: int = 5,
    provider: str = "local",
    correlation_id: str = "",
) -> list[dict[str, Any]]:
    """Main search entry with logging."""
    if not query.strip():
        return []

    backend = get_backend()

    try:
        if backend == "sqlite":
            return await search_learnings_sqlite(query, k, correlation_id)
        else:
            return await search_learnings_postgres(query, k, provider, correlation_id)
    except Exception as e:
        log_error(
            type(e).__name__,
            str(e),
            correlation_id,
            "search_learnings",
        )
        raise


# =============================================================================
# Main Entry
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Recall learnings with structured logging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--query", "-q", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--provider", choices=["local", "voyage"], default="local")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Initialize logging
    setup_logging(script_name="recall_learnings", log_level="INFO")

    if not args.json:
        print(f'Recalling learnings for: "{args.query}"')
        print(f"Provider: {args.provider}")
        print()

    # Log query received
    correlation_id = log_query_received(args.query, args.k, args.provider)

    start_time = datetime.now(timezone.utc).timestamp()

    try:
        results = await search_learnings(
            query=args.query,
            k=args.k,
            provider=args.provider,
            correlation_id=correlation_id,
        )
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e), "results": []}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    total_duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000

    log_search_complete(
        correlation_id,
        len(results),
        total_duration_ms,
        len(results) > 0,
    )

    if args.json:
        json_results = []
        for result in results:
            created_at = result["created_at"]
            if hasattr(created_at, "isoformat"):
                created_str = created_at.isoformat()
            else:
                created_str = str(created_at)

            json_results.append({
                "score": result["similarity"],
                "session_id": result["session_id"],
                "content": result["content"],
                "created_at": created_str,
            })
        print(json.dumps({"results": json_results}))
        return 0

    if not results:
        print("No matching learnings found.")
        return 0

    print(f"Found {len(results)} matching learnings:")
    print()

    for i, result in enumerate(results, 1):
        content_preview = result["content"][:300] + "..." if len(result["content"]) > 300 else result["content"]
        print(f"{i}. [{result['similarity']:.3f}] Session: {result['session_id']}")
        print(f"   {content_preview}")
        print()

    return 0


if __name__ == "__main__":
    setup_logging(script_name="recall_learnings", log_level="INFO")
    sys.exit(asyncio.run(main()))
