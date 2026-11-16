"""Embed existing temporal facts in PostgreSQL.

USAGE:
    # Embed using local sentence-transformers (no API costs)
    uv run python scripts/embed_temporal_facts.py --provider=local --batch-size=32

    # Embed using Voyage AI (requires VOYAGE_API_KEY)
    uv run python scripts/embed_temporal_facts.py --provider=voyage --batch-size=32

    # Embed code with voyage-code-3 model
    uv run python scripts/embed_temporal_facts.py --provider=voyage --model=voyage-code-3

    # Dry run - show what would be embedded without making changes
    uv run python scripts/embed_temporal_facts.py --provider=local --dry-run

Purpose:
    Embed the existing facts in PostgreSQL that don't have embeddings yet.
    Uses EmbeddingService for batch embedding and pads/truncates to 4096 dimensions
    for pgvector compatibility.

Requirements:
    - PostgreSQL with pgvector extension
    - For local: sentence-transformers package
    - For voyage: VOYAGE_API_KEY environment variable
"""
from __future__ import annotations

import argparse
import asyncio
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
from scripts.agentica_patterns.postgres_pool import (
    get_connection,
    get_transaction,
    init_pgvector,
)

# Target embedding dimension for pgvector column
TARGET_EMBEDDING_DIM = 1024


def _pad_embedding(embedding: list[float], target_dim: int = TARGET_EMBEDDING_DIM) -> list[float]:
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


def chunks(lst: list[Any], n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def get_facts_without_embeddings() -> list[dict[str, Any]]:
    """Query facts where embedding IS NULL."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, key, value FROM temporal_facts
            WHERE embedding IS NULL
            ORDER BY created_at
            """
        )
        return [dict(row) for row in rows]


async def update_fact_embedding(fact_id: str, embedding: list[float]) -> None:
    """Update a single fact with its embedding."""
    async with get_connection() as conn:
        await init_pgvector(conn)
        await conn.execute(
            """
            UPDATE temporal_facts
            SET embedding = $1::vector
            WHERE id = $2
            """,
            embedding,
            fact_id,
        )


async def update_facts_batch(fact_ids: list[str], embeddings: list[list[float]]) -> int:
    """Update multiple facts with embeddings in a single transaction."""
    async with get_transaction() as conn:
        await init_pgvector(conn)
        for fact_id, embedding in zip(fact_ids, embeddings):
            await conn.execute(
                """
                UPDATE temporal_facts
                SET embedding = $1::vector
                WHERE id = $2
                """,
                embedding,
                fact_id,
            )
    return len(fact_ids)


async def embed_facts(
    provider: str = "local",
    model: str | None = None,
    batch_size: int = 32,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Embed existing facts in PostgreSQL.

    Args:
        provider: Embedding provider ("local" or "voyage")
        model: Model name (e.g., "voyage-code-3", "voyage-3-large", "all-mpnet-base-v2")
        batch_size: Number of facts to embed per batch
        dry_run: If True, only show what would be done

    Returns:
        Summary statistics
    """
    # Get facts without embeddings
    facts = await get_facts_without_embeddings()
    total_facts = len(facts)

    if total_facts == 0:
        print("No facts without embeddings found.")
        return {"total": 0, "embedded": 0, "provider": provider}

    print(f"Found {total_facts} facts without embeddings")

    if dry_run:
        model_info = f" ({model})" if model else ""
        print(f"[DRY RUN] Would embed {total_facts} facts using {provider}{model_info}")
        for i, fact in enumerate(facts[:5], 1):
            print(f"  {i}. {fact['key']}: {fact['value'][:50]}...")
        if total_facts > 5:
            print(f"  ... and {total_facts - 5} more")
        return {"total": total_facts, "embedded": 0, "provider": provider, "model": model, "dry_run": True}

    # Initialize embedding service
    model_info = f" ({model})" if model else ""
    print(f"Initializing {provider}{model_info} embedding service...")
    async with EmbeddingService(provider=provider, model=model) as embedder:
        embedded_count = 0

        # Process in batches
        batch_num = 0
        for batch in chunks(facts, batch_size):
            batch_num += 1
            batch_ids = [f["id"] for f in batch]
            texts = [f"{f['key']}: {f['value']}" for f in batch]

            # Generate embeddings
            embeddings = await embedder.embed_batch(texts)

            # Pad embeddings to target dimension
            padded_embeddings = [_pad_embedding(emb) for emb in embeddings]

            # Update facts with embeddings
            updated = await update_facts_batch(batch_ids, padded_embeddings)
            embedded_count += updated

            # Progress
            progress = (embedded_count / total_facts) * 100
            print(f"  Batch {batch_num}: {embedded_count}/{total_facts} ({progress:.1f}%)")

    print(f"\nCompleted: {embedded_count}/{total_facts} facts embedded")
    return {
        "total": total_facts,
        "embedded": embedded_count,
        "provider": provider,
        "model": model,
        "batch_size": batch_size,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Embed existing temporal facts in PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Embed using local sentence-transformers
    uv run python scripts/embed_temporal_facts.py --provider=local

    # Embed using Voyage AI (default voyage-3)
    uv run python scripts/embed_temporal_facts.py --provider=voyage

    # Embed code with voyage-code-3 model
    uv run python scripts/embed_temporal_facts.py --provider=voyage --model=voyage-code-3

    # Embed with voyage-3-large for higher quality
    uv run python scripts/embed_temporal_facts.py --provider=voyage --model=voyage-3-large

    # Dry run
    uv run python scripts/embed_temporal_facts.py --dry-run
        """,
    )
    parser.add_argument(
        "--provider",
        choices=["local", "voyage"],
        default="local",
        help="Embedding provider (default: local)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name. Voyage: voyage-3, voyage-code-3, voyage-3-large, voyage-3-lite. Local: all-MiniLM-L6-v2, all-mpnet-base-v2",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Number of facts to embed per batch (default: 32)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    try:
        result = asyncio.run(
            embed_facts(
                provider=args.provider,
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
