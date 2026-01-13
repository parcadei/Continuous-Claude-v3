#!/usr/bin/env python3
"""Semantic recall of session learnings from archival_memory.

Searches the archival_memory table for session_learning entries
using vector similarity search.

USAGE:
    # Simple search (top 5 results, local embeddings)
    uv run python scripts/recall_learnings.py --query "authentication patterns"

    # More results
    uv run python scripts/recall_learnings.py --query "database schema" --k 10

    # Voyage embeddings (higher quality, requires VOYAGE_API_KEY)
    uv run python scripts/recall_learnings.py --query "errors" --provider voyage

Workflow:
    Query -> Embed (Local/Voyage) -> Vector Search (pgvector) -> Return

Environment:
    VOYAGE_API_KEY - For Voyage embeddings (optional)
    PostgreSQL with pgvector extension
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env files
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)
load_dotenv()

# Add project root to path for imports (opc/)
project_dir = os.environ.get("CLAUDE_PROJECT_DIR", str(Path(__file__).parent.parent.parent))
sys.path.insert(0, project_dir)


def format_result_preview(content: str, max_length: int = 200) -> str:
    """Format content for display, truncating if needed.

    Args:
        content: Full content string
        max_length: Maximum characters before truncation

    Returns:
        Content string, truncated with ... if over max_length
    """
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def get_backend() -> str:
    """Determine which backend to use (sqlite or postgres)."""
    # Check explicit env var first
    backend = os.environ.get("AGENTICA_MEMORY_BACKEND", "").lower()
    if backend in ("sqlite", "postgres"):
        return backend

    # Check if DATABASE_URL or CONTINUOUS_CLAUDE_DB_URL is set
    if os.environ.get("DATABASE_URL") or os.environ.get("CONTINUOUS_CLAUDE_DB_URL"):
        return "postgres"

    # Default to sqlite for simplicity
    return "sqlite"


async def search_learnings_text_only_postgres(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Fast text-only search for PostgreSQL using full-text search.

    Uses tsvector/tsquery with GIN index. Automatic stopword handling.
    Falls back to ILIKE if tsquery fails (e.g., all stopwords).
    """
    from scripts.core.db.postgres_pool import get_pool

    pool = await get_pool()

    async with pool.acquire() as conn:
        # Try full-text search using plainto_tsquery (flexible OR semantics)
        # Strip meta-words and normalize for better matching
        meta_words = {'help', 'want', 'need', 'show', 'tell', 'find', 'look', 'please', 'with', 'for'}
        clean_query = query.lower().replace('-', ' ')  # "multi-terminal" -> "multi terminal"
        clean_query = ' '.join(w for w in clean_query.split() if w not in meta_words)
        if not clean_query.strip():
            clean_query = query  # Fallback to original if all stripped

        # Build OR-based query: "session affinity terminal" -> 'session' | 'affinity' | 'terminal'
        # This matches documents containing ANY of the terms, ranked by how many match
        import re
        words = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in clean_query.split()]
        words = [w for w in words if len(w) > 2]
        if not words:
            words = clean_query.split()[:1] or [query.split()[0]]
        or_query = ' | '.join(words)

        rows = await conn.fetch(
            """
            SELECT
                id,
                session_id,
                content,
                metadata,
                created_at,
                ts_rank(to_tsvector('english', content), to_tsquery('english', $1)) as similarity
            FROM archival_memory
            WHERE metadata->>'type' = 'session_learning'
                AND to_tsvector('english', content) @@ to_tsquery('english', $1)
            ORDER BY similarity DESC, created_at DESC
            LIMIT $2
            """,
            or_query,
            k,
        )

        # Fallback to ILIKE if no FTS results (query was all stopwords)
        if not rows:
            # Extract first word for simple substring match
            first_word = query.split()[0] if query.split() else query
            search_pattern = f"%{first_word}%"
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    session_id,
                    content,
                    metadata,
                    created_at,
                    0.1 as similarity
                FROM archival_memory
                WHERE metadata->>'type' = 'session_learning'
                    AND content ILIKE $3
                ORDER BY created_at DESC
                LIMIT $2
                """,
                first_word,
                k,
                search_pattern,
            )

    results = []
    for row in rows:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        results.append({
            "id": str(row["id"]),
            "session_id": row["session_id"],
            "content": row["content"],
            "metadata": metadata,
            "created_at": row["created_at"],
            "similarity": float(row["similarity"]),  # Use actual ts_rank score
        })

    return results


async def search_learnings_sqlite(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Search learnings using SQLite FTS5 (BM25 ranking).

    Cross-session search - finds learnings from ALL sessions.

    Args:
        query: Search query
        k: Number of results to return

    Returns:
        List of matching learnings with BM25 scores
    """
    import sqlite3
    import re

    # Global SQLite path
    db_path = Path.home() / ".claude" / "cache" / "memory.db"

    if not db_path.exists():
        return []

    # Prepare FTS query (OR-join words for broader matching)
    words = re.findall(r"\w+", query.lower())
    fts_query = " OR ".join(words) if words else query

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.execute(
            """
            SELECT
                a.id,
                a.session_id,
                a.content,
                a.metadata_json,
                a.created_at,
                bm25(archival_fts) as rank
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
            # BM25 returns negative scores (lower = better)
            # Normalize to 0.0-1.0 range
            raw_rank = row["rank"] if row["rank"] else 0
            normalized_score = min(1.0, max(0.0, -raw_rank / 25.0))

            metadata = {}
            if row["metadata_json"]:
                try:
                    metadata = json.loads(row["metadata_json"])
                except json.JSONDecodeError:
                    pass

            results.append({
                "id": row["id"] or "",
                "session_id": row["session_id"] or "unknown",
                "content": row["content"] or "",
                "metadata": metadata,
                "created_at": datetime.fromtimestamp(row["created_at"]) if row["created_at"] else None,
                "similarity": normalized_score,
            })

        return results
    finally:
        conn.close()


async def search_learnings_auto_rerank(
    query: str,
    k: int = 5,
    provider: str = "local",
    auto_rerank: bool = True,
    reranker: str = "Qwen/Qwen3-Reranker-0.6B",
    confidence_gap_threshold: float = 0.10,
    high_confidence_threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """Hybrid search with automatic reranking based on confidence.

    Two-stage retrieval that conditionally uses the reranker:
    - Skip rerank if top result has high confidence (>0.85)
    - Skip rerank if top-3 scores are well-separated (clear winner)
    - Rerank if confidence gap between top results is small (uncertain)

    This balances quality and speed: ~50% of queries skip reranking.

    Args:
        query: Search query
        k: Number of results to return
        provider: Embedding provider for initial retrieval
        auto_rerank: Enable automatic reranking (default True)
        reranker: Reranker model name
        confidence_gap_threshold: Gap below which to rerank (default 0.10)
        high_confidence_threshold: Score above which to skip rerank (default 0.85)

    Returns:
        List of learnings with reranker scores
    """
    import re

    from scripts.core.db.embedding_service import EmbeddingService, RerankerProvider
    from scripts.core.db.postgres_pool import get_pool, init_pgvector

    pool = await get_pool()

    # Generate query embedding
    embedder = EmbeddingService(provider=provider)
    try:
        query_embedding = await embedder.embed(query)
    finally:
        await embedder.aclose()

    # Fetch more candidates for analysis
    initial_k = 20

    async with pool.acquire() as conn:
        await init_pgvector(conn)

        rows = await conn.fetch(
            """
            SELECT
                id,
                session_id,
                content,
                metadata,
                created_at,
                1 - (embedding <=> $1::vector) as similarity
            FROM archival_memory
            WHERE metadata->>'type' = 'session_learning'
                AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            str(query_embedding),
            initial_k,
        )

    if not rows:
        return []

    # Build results list
    results = []
    for row in rows:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        results.append({
            "id": str(row["id"]),
            "session_id": row["session_id"],
            "content": row["content"],
            "metadata": metadata,
            "created_at": row["created_at"],
            "vector_score": float(row["similarity"]),
            "similarity": float(row["similarity"]),
        })

    # Analyze confidence to decide on reranking
    should_rerank = False
    rerank_reason = ""

    if auto_rerank and len(results) >= 3:
        top_score = results[0]["vector_score"]
        second_score = results[1]["vector_score"]
        third_score = results[2]["vector_score"]

        # Skip reranking if high confidence
        if top_score >= high_confidence_threshold:
            rerank_reason = f"high confidence ({top_score:.2f})"
            should_rerank = False

        # Check confidence gap (top - second)
        gap = top_score - second_score

        # Skip reranking if clear winner
        if gap >= confidence_gap_threshold + 0.15:
            rerank_reason = f"clear winner (gap: {gap:.2f})"
            should_rerank = False

        # Rerank if close race
        elif gap < confidence_gap_threshold:
            should_rerank = True
            rerank_reason = f"close race (gap: {gap:.2f})"

        # Rerank if top-3 are all close
        elif (top_score - third_score) < (confidence_gap_threshold * 2):
            should_rerank = True
            rerank_reason = f"crowded top (top-3 span: {top_score - third_score:.2f})"

        # Check query complexity indicators
        comparison_words = {" vs ", " vs", "and", "or", "compare", "difference", "better"}
        query_lower = query.lower()
        if any(word in query_lower for word in comparison_words):
            should_rerank = True
            rerank_reason = f"comparison query"

    # Conditional reranking
    if should_rerank and auto_rerank:
        reranker_provider = RerankerProvider(model=reranker)
        try:
            documents = [r["content"][:2000] for r in results]
            rerank_scores = await reranker_provider.rerank(query, documents)

            # Combine scores (70% rerank, 30% vector for final ranking)
            for i, result in enumerate(results):
                result["rerank_score"] = rerank_scores[i]
                result["similarity"] = (result["vector_score"] * 0.3 + rerank_scores[i] * 0.7)

            # Sort by combined score
            results.sort(key=lambda x: x["similarity"], reverse=True)
            rerank_reason += f" -> reranked"

        finally:
            del reranker_provider

    # Return top k results
    return results[:k]


async def search_learnings_hybrid_rrf(
    query: str,
    k: int = 5,
    provider: str = "local",
    rrf_k: int = 60,
    similarity_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """Hybrid RRF search combining text and vector rankings.

    Uses Reciprocal Rank Fusion:
        score = 1/(k + rank_fts) + 1/(k + rank_vector)

    Args:
        query: Search query
        k: Number of results
        provider: Embedding provider
        rrf_k: RRF constant (default 60)
        similarity_threshold: Minimum RRF score to include

    Returns:
        List of learnings with RRF scores
    """
    from scripts.core.db.embedding_service import EmbeddingService
    from scripts.core.db.postgres_pool import get_pool, init_pgvector

    pool = await get_pool()

    # Generate query embedding
    embedder = EmbeddingService(provider=provider)
    try:
        query_embedding = await embedder.embed(query)
    finally:
        await embedder.aclose()

    async with pool.acquire() as conn:
        await init_pgvector(conn)

        # RRF query across all sessions for learnings
        rows = await conn.fetch(
            """
            WITH fts_ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank(
                            to_tsvector('english', content),
                            plainto_tsquery('english', $1)
                        ) DESC
                    ) as fts_rank
                FROM archival_memory
                WHERE metadata->>'type' = 'session_learning'
                AND to_tsvector('english', content) @@ plainto_tsquery('english', $1)
            ),
            vector_ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (ORDER BY embedding <=> $2::vector) as vec_rank
                FROM archival_memory
                WHERE metadata->>'type' = 'session_learning'
                AND embedding IS NOT NULL
            ),
            combined AS (
                SELECT
                    COALESCE(f.id, v.id) as id,
                    COALESCE(1.0 / ($3 + f.fts_rank), 0) +
                    COALESCE(1.0 / ($3 + v.vec_rank), 0) as rrf_score,
                    f.fts_rank,
                    v.vec_rank
                FROM fts_ranked f
                FULL OUTER JOIN vector_ranked v ON f.id = v.id
            )
            SELECT
                a.id,
                a.session_id,
                a.content,
                a.metadata,
                a.created_at,
                c.rrf_score,
                c.fts_rank,
                c.vec_rank
            FROM combined c
            JOIN archival_memory a ON a.id = c.id
            ORDER BY c.rrf_score DESC
            LIMIT $4
            """,
            query,
            str(query_embedding),
            rrf_k,
            k * 2,  # Fetch more to allow filtering
        )

    results = []
    for row in rows:
        rrf_score = float(row["rrf_score"])

        if similarity_threshold > 0 and rrf_score < similarity_threshold:
            continue

        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        results.append({
            "id": str(row["id"]),
            "session_id": row["session_id"],
            "content": row["content"],
            "metadata": metadata,
            "created_at": row["created_at"],
            "similarity": rrf_score,  # Use RRF score as similarity for consistency
            "fts_rank": row["fts_rank"],
            "vec_rank": row["vec_rank"],
        })

        if len(results) >= k:
            break

    return results


async def search_learnings_postgres(
    query: str,
    k: int = 5,
    provider: str = "local",
    text_fallback: bool = True,
    similarity_threshold: float = 0.0,
    recency_weight: float = 0.0,
) -> list[dict[str, Any]]:
    """Search learnings using PostgreSQL (vector similarity or text fallback).

    Args:
        query: Search query for semantic matching
        k: Number of results to return
        provider: Embedding provider ("local" or "voyage")
        text_fallback: If True, use text search when no embeddings exist
        similarity_threshold: Minimum similarity score (0.0-1.0) to include results
        recency_weight: Weight for recency boost (0.0-1.0). 0=no boost, 0.3=30% recency

    Returns:
        List of matching learnings with similarity scores
    """
    from scripts.core.db.embedding_service import EmbeddingService
    from scripts.core.db.postgres_pool import get_pool

    pool = await get_pool()

    # First check if any learnings have embeddings
    async with pool.acquire() as conn:
        count_row = await conn.fetchrow(
            """
            SELECT COUNT(*) as cnt FROM archival_memory
            WHERE metadata->>'type' = 'session_learning'
                AND embedding IS NOT NULL
            """
        )
        has_embeddings = count_row["cnt"] > 0

    if has_embeddings:
        # Vector similarity search
        embedder = EmbeddingService(provider=provider)
        try:
            query_embedding = await embedder.embed(query)
        finally:
            await embedder.aclose()

        async with pool.acquire() as conn:
            from scripts.core.db.postgres_pool import init_pgvector
            await init_pgvector(conn)

            if recency_weight > 0:
                # Combined score: (1-recency_weight)*similarity + recency_weight*recency
                # Recency is normalized: 1.0 for newest, 0.0 for 30 days old or older
                rows = await conn.fetch(
                    """
                    WITH scored AS (
                        SELECT
                            id,
                            session_id,
                            content,
                            metadata,
                            created_at,
                            1 - (embedding <=> $1::vector) as similarity,
                            GREATEST(0, 1.0 - EXTRACT(EPOCH FROM NOW() - created_at) / (30 * 86400)) as recency
                        FROM archival_memory
                        WHERE metadata->>'type' = 'session_learning'
                            AND embedding IS NOT NULL
                    )
                    SELECT
                        id, session_id, content, metadata, created_at, similarity, recency,
                        (1.0 - $3::float) * similarity + $3::float * recency as combined_score
                    FROM scored
                    ORDER BY combined_score DESC
                    LIMIT $2
                    """,
                    str(query_embedding),
                    k,
                    recency_weight,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT
                        id,
                        session_id,
                        content,
                        metadata,
                        created_at,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM archival_memory
                    WHERE metadata->>'type' = 'session_learning'
                        AND embedding IS NOT NULL
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                    """,
                    str(query_embedding),
                    k,
                )
    elif text_fallback:
        # Fallback to text search (ILIKE) when no embeddings
        search_pattern = f"%{query}%"
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    session_id,
                    content,
                    metadata,
                    created_at,
                    0.5 as similarity
                FROM archival_memory
                WHERE metadata->>'type' = 'session_learning'
                    AND content ILIKE $3
                ORDER BY created_at DESC
                LIMIT $2
                """,
                query,
                k,
                search_pattern,
            )
    else:
        return []

    results = []
    for row in rows:
        row_dict = dict(row)  # Convert Record to dict for easier access

        # Use combined_score if available (recency boost), otherwise similarity
        if "combined_score" in row_dict:
            score = float(row_dict["combined_score"]) if row_dict["combined_score"] else 0.0
        else:
            score = float(row_dict["similarity"]) if row_dict["similarity"] else 0.0

        # Skip results below threshold (only for vector search, not text fallback)
        if similarity_threshold > 0 and score < similarity_threshold:
            continue

        metadata = row_dict["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        result = {
            "id": str(row_dict["id"]),
            "session_id": row_dict["session_id"],
            "content": row_dict["content"],
            "metadata": metadata,
            "created_at": row_dict["created_at"],
            "similarity": score,
        }

        # Include raw similarity and recency if available
        if "recency" in row_dict:
            result["raw_similarity"] = float(row_dict["similarity"]) if row_dict["similarity"] else 0.0
            result["recency"] = float(row_dict["recency"]) if row_dict["recency"] else 0.0

        results.append(result)

    return results


async def search_learnings(
    query: str,
    k: int = 5,
    provider: str = "local",
    text_fallback: bool = True,
    similarity_threshold: float = 0.2,
    recency_weight: float = 0.0,
) -> list[dict[str, Any]]:
    """Search archival_memory for session learnings.

    Automatically selects SQLite (BM25) or PostgreSQL (vector) based on environment.

    Args:
        query: Search query for semantic matching
        k: Number of results to return
        provider: Embedding provider ("local" or "voyage") - PostgreSQL only
        text_fallback: If True, use text search when no embeddings exist
        similarity_threshold: Minimum similarity score (default 0.2 filters garbage)
        recency_weight: Weight for recency boost (0.0-1.0). 0=no boost, 0.3=30% recency

    Returns:
        List of matching learnings with similarity scores
    """
    if not query.strip():
        return []

    backend = get_backend()

    if backend == "sqlite":
        return await search_learnings_sqlite(query, k)
    else:
        return await search_learnings_postgres(query, k, provider, text_fallback, similarity_threshold, recency_weight)


async def main() -> int:
    """Run semantic recall on session learnings."""
    parser = argparse.ArgumentParser(
        description="Semantic recall of session learnings from archival_memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--query",
        "-q",
        required=True,
        help="Search query for semantic matching",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)",
    )
    parser.add_argument(
        "--provider",
        choices=["local", "voyage"],
        default="local",
        help="Embedding provider (default: local)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for programmatic use)",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Use text search only (faster, no embeddings)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.2,
        help="Minimum similarity threshold (default: 0.2, filters low-quality results)",
    )
    parser.add_argument(
        "--vector-only",
        action="store_true",
        help="Use vector-only search (disables hybrid RRF, enables recency)",
    )
    parser.add_argument(
        "--recency",
        "-r",
        type=float,
        default=0.1,
        help="Recency weight for vector-only mode (0.0-1.0, default: 0.1)",
    )
    parser.add_argument(
        "--auto-rerank",
        action="store_true",
        default=True,
        help="Auto-rerank based on confidence (default: enabled)",
    )
    parser.add_argument(
        "--no-auto-rerank",
        action="store_false",
        dest="auto_rerank",
        help="Disable auto-reranking (always skip reranker)",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Force reranking (override auto-decision)",
    )

    args = parser.parse_args()

    # JSON mode: suppress human-readable output
    if not args.json:
        print(f'Recalling learnings for: "{args.query}"')
        print(f"Provider: {args.provider}")
        if args.auto_rerank:
            print("Mode: Auto-rerank (skips reranker when confident)")
        print()

    try:
        backend = get_backend()

        if backend == "sqlite":
            # SQLite only supports text search (no pgvector)
            if not args.text_only and not args.json:
                print("  (SQLite backend - using text search)")
            results = await search_learnings_sqlite(args.query, args.k)
        elif args.text_only:
            # Fast text-only search (no embeddings)
            results = await search_learnings_text_only_postgres(args.query, args.k)
        elif args.vector_only:
            # Vector-only search with recency boost
            results = await search_learnings(
                query=args.query,
                k=args.k,
                provider=args.provider,
                similarity_threshold=args.threshold,
                recency_weight=args.recency,
            )
        elif args.rerank:
            # Force reranking (bypass auto-decision)
            results = await search_learnings_auto_rerank(
                query=args.query,
                k=args.k,
                provider=args.provider,
                auto_rerank=True,
                high_confidence_threshold=0.0,  # Force rerank
                confidence_gap_threshold=999.0,  # Force rerank
            )
        else:
            # Default: Auto-rerank based on confidence
            results = await search_learnings_auto_rerank(
                query=args.query,
                k=args.k,
                provider=args.provider,
                auto_rerank=args.auto_rerank,
            )
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e), "results": []}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    # JSON output mode
    if args.json:
        json_results = []
        for result in results:
            created_at = result["created_at"]
            if isinstance(created_at, datetime):
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

    # Human-readable output
    if not results:
        print("No matching learnings found.")
        return 0

    print(f"Found {len(results)} matching learnings:")
    print()

    for i, result in enumerate(results, 1):
        similarity = result["similarity"]
        content_preview = format_result_preview(result["content"], max_length=300)
        session_id = result["session_id"]
        created_at = result["created_at"]

        # Format timestamp
        if isinstance(created_at, datetime):
            created_str = created_at.strftime("%Y-%m-%d %H:%M")
        else:
            created_str = str(created_at)[:16]

        print(f"{i}. [{similarity:.3f}] Session: {session_id} ({created_str})")
        print(f"   {content_preview}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
