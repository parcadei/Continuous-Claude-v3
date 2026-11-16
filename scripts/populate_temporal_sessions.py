"""Populate temporal_sessions from handoffs with embeddings.

USAGE:
    # Populate from handoffs (no embedding yet)
    uv run python scripts/populate_temporal_sessions.py

    # Populate with voyage-code-3 embeddings
    uv run python scripts/populate_temporal_sessions.py --embed --model=voyage-code-3

    # Dry run
    uv run python scripts/populate_temporal_sessions.py --embed --dry-run

Purpose:
    Migrates handoffs from SQLite (context.db) to PostgreSQL (temporal_sessions)
    with optional embedding generation for session-level semantic search.

Rate Limits (Voyage):
    - 3M TPM (tokens per minute)
    - 2K RPM (requests per minute)
    - Script uses batch size 32 to stay within limits
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

# Load .env files (global first, then local)
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)
load_dotenv()  # Local .env

from scripts.agentica_patterns.embedding_service import EmbeddingService
from scripts.agentica_patterns.postgres_pool import get_connection, get_transaction

# Target embedding dimension for pgvector (1024 = native Voyage dimension)
TARGET_EMBEDDING_DIM = 1024


def _pad_embedding(embedding, target_dim: int = TARGET_EMBEDDING_DIM) -> str:
    """Pad embedding to target dimension and convert to pgvector string format.

    Handles various input formats:
    - list[float]: Standard embedding list
    - np.ndarray: NumPy array (1D or 2D)
    - list[list[float]]: Batch of 1 (unwraps)
    - str: JSON-encoded embedding (parses)
    """
    import json

    # Handle string input (JSON-encoded embedding)
    if isinstance(embedding, str):
        try:
            embedding = json.loads(embedding)
        except json.JSONDecodeError:
            raise ValueError(f"Cannot parse embedding string: {embedding[:100]}...")

    # Handle numpy array
    if isinstance(embedding, np.ndarray):
        if embedding.ndim == 0:
            raise ValueError(f"Got 0-dimensional array, expected 1D: {embedding}")
        embedding = embedding.flatten().tolist()

    # Handle nested list (batch of 1)
    if isinstance(embedding, list) and len(embedding) > 0:
        if isinstance(embedding[0], list):
            embedding = embedding[0]
        elif isinstance(embedding[0], np.ndarray):
            embedding = embedding[0].tolist()

    # Validate we have a list of numbers
    if not isinstance(embedding, list):
        raise ValueError(f"Expected list, got {type(embedding)}: {str(embedding)[:100]}")
    if len(embedding) == 0:
        raise ValueError("Empty embedding")
    if not isinstance(embedding[0], (int, float)):
        raise ValueError(f"Expected numeric values, got {type(embedding[0])}: {embedding[0]}")

    # Convert to numpy for padding/truncation
    vec = np.array(embedding, dtype=np.float64)

    if len(vec) >= target_dim:
        padded = vec[:target_dim]
    else:
        padded = np.pad(vec, (0, target_dim - len(vec)), mode="constant")

    # pgvector expects string format: '[0.1,0.2,...]'
    return '[' + ','.join(str(x) for x in padded.tolist()) + ']'


def get_handoffs_from_sqlite(context_db_path: Path) -> list[dict[str, Any]]:
    """Read handoffs with session_id from SQLite context.db."""
    conn = sqlite3.connect(context_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT
            session_id,
            session_name,
            task_summary,
            key_decisions,
            what_worked,
            what_failed,
            outcome,
            root_span_id
        FROM handoffs
        WHERE session_id IS NOT NULL AND session_id != ''
        ORDER BY created_at
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def _merge_text_fields(values: list[str | None], separator: str = "\n---\n") -> str | None:
    """Merge multiple text field values, filtering out empty ones."""
    non_empty = [v.strip() for v in values if v and v.strip()]
    return separator.join(non_empty) if non_empty else None


def aggregate_handoffs_by_session(handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate multiple handoffs per session_id into single merged records.

    Multiple handoffs can share the same session_id (one session creates multiple
    handoffs). This function merges them:
    - Text fields (summary, key_decisions, etc.): Concatenate all non-empty values
    - outcome: Use the most recent non-null value
    - root_span_id: Use first non-null value
    - session_name: Use first non-null value

    Args:
        handoffs: List of handoff dicts, ordered by created_at

    Returns:
        List of merged handoff dicts, one per unique session_id
    """
    from collections import defaultdict

    # Group by session_id (preserving order from created_at)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for h in handoffs:
        groups[h['session_id']].append(h)

    merged_sessions = []
    for session_id, group in groups.items():
        # Collect all values for text fields
        summaries = [h.get('task_summary') for h in group]
        key_decisions_list = [h.get('key_decisions') for h in group]
        what_worked_list = [h.get('what_worked') for h in group]
        what_failed_list = [h.get('what_failed') for h in group]

        # For outcome and root_span_id, use first/last non-null
        # outcome: most recent (last in list since ordered by created_at)
        outcome = None
        for h in reversed(group):
            if h.get('outcome'):
                outcome = h['outcome']
                break

        # root_span_id: first non-null
        root_span_id = None
        for h in group:
            if h.get('root_span_id'):
                root_span_id = h['root_span_id']
                break

        # session_name: first non-null
        session_name = None
        for h in group:
            if h.get('session_name'):
                session_name = h['session_name']
                break

        merged_sessions.append({
            'session_id': session_id,
            'session_name': session_name,
            'task_summary': _merge_text_fields(summaries),
            'key_decisions': _merge_text_fields(key_decisions_list),
            'what_worked': _merge_text_fields(what_worked_list),
            'what_failed': _merge_text_fields(what_failed_list),
            'outcome': outcome,
            'root_span_id': root_span_id,
            '_handoff_count': len(group),  # For debugging/logging
        })

    return merged_sessions


def build_composite_text(handoff: dict[str, Any]) -> str:
    """Build composite text for embedding from handoff fields."""
    parts = []

    if handoff.get('task_summary'):
        parts.append(f"Summary: {handoff['task_summary']}")

    if handoff.get('key_decisions'):
        parts.append(f"Decisions: {handoff['key_decisions']}")

    if handoff.get('what_worked'):
        parts.append(f"What worked: {handoff['what_worked']}")

    if handoff.get('what_failed'):
        parts.append(f"What failed: {handoff['what_failed']}")

    return "\n\n".join(parts) if parts else ""


async def get_existing_session_ids() -> set[str]:
    """Get session_ids already in temporal_sessions."""
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT session_id FROM temporal_sessions")
        return {row['session_id'] for row in rows}


async def insert_session(
    session_id: str,
    session_name: str | None,
    summary: str | None,
    key_decisions: str | None,
    what_worked: str | None,
    what_failed: str | None,
    outcome: str | None,
    root_span_id: str | None,
    embedding_str: str | None = None,
) -> None:
    """Insert a session into temporal_sessions."""
    async with get_transaction() as conn:
        if embedding_str:
            await conn.execute("""
                INSERT INTO temporal_sessions (
                    session_id, session_name, summary, key_decisions,
                    what_worked, what_failed, outcome, root_span_id, embedding
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector)
                ON CONFLICT (session_id) DO UPDATE SET
                    session_name = EXCLUDED.session_name,
                    summary = EXCLUDED.summary,
                    key_decisions = EXCLUDED.key_decisions,
                    what_worked = EXCLUDED.what_worked,
                    what_failed = EXCLUDED.what_failed,
                    outcome = EXCLUDED.outcome,
                    root_span_id = EXCLUDED.root_span_id,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
            """,
                session_id, session_name, summary, key_decisions,
                what_worked, what_failed, outcome, root_span_id, embedding_str
            )
        else:
            await conn.execute("""
                INSERT INTO temporal_sessions (
                    session_id, session_name, summary, key_decisions,
                    what_worked, what_failed, outcome, root_span_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (session_id) DO UPDATE SET
                    session_name = EXCLUDED.session_name,
                    summary = EXCLUDED.summary,
                    key_decisions = EXCLUDED.key_decisions,
                    what_worked = EXCLUDED.what_worked,
                    what_failed = EXCLUDED.what_failed,
                    outcome = EXCLUDED.outcome,
                    root_span_id = EXCLUDED.root_span_id,
                    updated_at = NOW()
            """,
                session_id, session_name, summary, key_decisions,
                what_worked, what_failed, outcome, root_span_id
            )


async def populate_sessions(
    context_db_path: Path,
    embed: bool = False,
    model: str = "voyage-code-3",
    batch_size: int = 32,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Populate temporal_sessions from handoffs.

    Args:
        context_db_path: Path to SQLite context.db
        embed: Whether to generate embeddings
        model: Embedding model name
        batch_size: Batch size for embedding API calls
        dry_run: If True, don't write to database

    Returns:
        Summary statistics
    """
    # Read handoffs from SQLite
    raw_handoffs = get_handoffs_from_sqlite(context_db_path)
    raw_total = len(raw_handoffs)

    if raw_total == 0:
        print("No handoffs with session_id found.")
        return {"total": 0, "inserted": 0}

    print(f"Found {raw_total} handoffs with session_id")

    # Aggregate handoffs by session_id (multiple handoffs can share same session)
    sessions = aggregate_handoffs_by_session(raw_handoffs)
    total = len(sessions)

    # Count sessions with multiple handoffs
    multi_handoff_count = sum(1 for s in sessions if s.get('_handoff_count', 1) > 1)
    if multi_handoff_count > 0:
        print(f"  Aggregated into {total} unique sessions ({multi_handoff_count} have multiple handoffs)")
    else:
        print(f"  {total} unique sessions (1:1 mapping)")

    # Get existing sessions to check for updates
    existing = await get_existing_session_ids()
    new_count = sum(1 for s in sessions if s['session_id'] not in existing)
    update_count = total - new_count

    print(f"  New sessions: {new_count}")
    print(f"  Updates: {update_count}")

    if dry_run:
        print(f"\n[DRY RUN] Would insert/update {total} sessions")
        for s in sessions[:5]:
            text = build_composite_text(s)
            handoff_info = f" ({s.get('_handoff_count', 1)} handoffs)" if s.get('_handoff_count', 1) > 1 else ""
            print(f"  - {s['session_id'][:8]}...{handoff_info} ({len(text)} chars)")
        if total > 5:
            print(f"  ... and {total - 5} more")
        return {"total": total, "raw_handoffs": raw_total, "inserted": 0, "dry_run": True}

    # Initialize embedding service if needed
    embedder = None
    if embed:
        print(f"\nInitializing embedding service ({model})...")
        embedder = EmbeddingService(provider="voyage", model=model)

    inserted = 0
    embedded = 0

    try:
        # Process aggregated sessions
        for i, session in enumerate(sessions):
            embedding_str = None

            if embedder:
                # Build composite text and embed
                text = build_composite_text(session)
                if text:
                    embedding = await embedder.embed(text)
                    embedding_str = _pad_embedding(embedding)
                    embedded += 1

            await insert_session(
                session_id=session['session_id'],
                session_name=session.get('session_name'),
                summary=session.get('task_summary'),
                key_decisions=session.get('key_decisions'),
                what_worked=session.get('what_worked'),
                what_failed=session.get('what_failed'),
                outcome=session.get('outcome'),
                root_span_id=session.get('root_span_id'),
                embedding_str=embedding_str,
            )
            inserted += 1

            # Progress
            if (i + 1) % 10 == 0 or i == total - 1:
                pct = ((i + 1) / total) * 100
                embed_info = f", {embedded} embedded" if embed else ""
                print(f"  Progress: {i + 1}/{total} ({pct:.1f}%){embed_info}")

    finally:
        if embedder:
            await embedder.aclose()

    print(f"\nCompleted: {inserted} sessions inserted/updated")
    if embed:
        print(f"  Embedded: {embedded}")

    return {
        "total": total,
        "raw_handoffs": raw_total,
        "inserted": inserted,
        "embedded": embedded if embed else 0,
        "model": model if embed else None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Populate temporal_sessions from handoffs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Populate without embedding
    uv run python scripts/populate_temporal_sessions.py

    # Populate with voyage-code-3 embeddings
    uv run python scripts/populate_temporal_sessions.py --embed --model=voyage-code-3

    # Dry run
    uv run python scripts/populate_temporal_sessions.py --embed --dry-run

Rate Limits:
    Voyage: 3M TPM, 2K RPM
    Batch size 32 stays well within limits.
        """,
    )
    parser.add_argument(
        "--context-db",
        type=Path,
        default=Path(".claude/cache/artifact-index/context.db"),
        help="Path to SQLite context.db (default: .claude/cache/artifact-index/context.db)",
    )
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Generate embeddings for sessions",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="voyage-code-3",
        help="Embedding model (default: voyage-code-3)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding (default: 32)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    if not args.context_db.exists():
        print(f"Error: context.db not found at {args.context_db}")
        sys.exit(1)

    try:
        result = asyncio.run(
            populate_sessions(
                context_db_path=args.context_db,
                embed=args.embed,
                model=args.model,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )
        )
        print(f"\nResult: {result}")
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
