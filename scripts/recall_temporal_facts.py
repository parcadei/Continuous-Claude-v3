#!/usr/bin/env python3
"""Semantic recall of temporal facts from PostgreSQL memory.

USAGE:
    # Simple vector search (top 5)
    uv run python scripts/recall_temporal_facts.py --query "authentication implementation"

    # More results
    uv run python scripts/recall_temporal_facts.py --query "database schema" --k 10

    # With reranking for higher precision
    uv run python scripts/recall_temporal_facts.py --query "auth" --rerank

    # Local embeddings (no API key)
    uv run python scripts/recall_temporal_facts.py --query "errors" --provider local

    # Local reranking (no API key)
    uv run python scripts/recall_temporal_facts.py --query "auth" --rerank --rerank-provider local

    # Specific session
    uv run python scripts/recall_temporal_facts.py --query "test" --session-id abc123

Workflow:
    Query -> Embed (Voyage/Local) -> Vector Search (pgvector) -> Rerank (Cohere/Local) -> Return

Environment:
    VOYAGE_API_KEY - For Voyage embeddings (default provider)
    COHERE_API_KEY - For Cohere reranking (default reranker)
    DATABASE_URL - PostgreSQL connection string
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env files (global first, then local)
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)
load_dotenv()  # Local .env

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


async def main() -> int:
    """Run semantic recall on temporal facts."""
    parser = argparse.ArgumentParser(
        description="Semantic recall of temporal facts from PostgreSQL memory",
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
        "--rerank",
        action="store_true",
        help="Enable reranking for higher precision",
    )
    parser.add_argument(
        "--provider",
        choices=["voyage", "local"],
        default="voyage",
        help="Embedding provider (default: voyage)",
    )
    parser.add_argument(
        "--rerank-provider",
        choices=["cohere", "local"],
        default="cohere",
        help="Reranker provider when --rerank is set (default: cohere)",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Session ID to search (default: from CLAUDE_SESSION_ID or 'default')",
    )
    parser.add_argument(
        "--all-sessions",
        action="store_true",
        help="Search across all sessions (ignore session_id filter)",
    )

    args = parser.parse_args()

    # Get session ID (None means cross-session search)
    if args.all_sessions:
        session_id = None
    else:
        session_id = args.session_id or os.environ.get("CLAUDE_SESSION_ID", "default")

    # Import after arg parsing to avoid slow imports on --help
    from scripts.agentica_patterns.embedding_service import EmbeddingService
    from scripts.agentica_patterns.reranker import get_reranker
    from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

    # Initialize embedding service
    try:
        if args.provider == "voyage":
            embedder = EmbeddingService(provider="voyage")
        else:
            embedder = EmbeddingService(provider="local")
    except ValueError as e:
        print(f"Error initializing embedding provider: {e}", file=sys.stderr)
        if args.provider == "voyage":
            print("Hint: Set VOYAGE_API_KEY environment variable", file=sys.stderr)
        return 1

    # Initialize temporal store
    store = TemporalMemoryStorePG(session_id=session_id)

    try:
        await store.connect()

        # Generate query embedding
        print(f"Recalling facts for: \"{args.query}\"")
        print(f"Session: {session_id}")
        print(f"Provider: {args.provider}", end="")
        if args.rerank:
            print(f", Rerank: {args.rerank_provider}")
        else:
            print()
        print()

        query_embedding = await embedder.embed(args.query)

        # Search for similar facts
        # Fetch more if reranking to give reranker good candidates
        search_k = args.k * 3 if args.rerank else args.k
        results = await store.search_similar(
            query_embedding=query_embedding,
            limit=search_k,
        )

        if not results:
            print("No matching facts found.")
            return 0

        # Optionally rerank
        if args.rerank and len(results) > 0:
            try:
                reranker = get_reranker(args.rerank_provider)
            except (ValueError, ImportError) as e:
                print(f"Error initializing reranker: {e}", file=sys.stderr)
                if args.rerank_provider == "cohere":
                    print("Hint: Set COHERE_API_KEY environment variable", file=sys.stderr)
                return 1

            # Prepare documents for reranking
            documents = [f"{r['key']}: {r['value']}" for r in results]

            # Rerank
            ranked = await reranker.rerank(
                query=args.query,
                documents=documents,
                top_k=args.k,
            )

            # Map back to original results with rerank scores
            final_results = []
            for ranked_doc in ranked:
                original_idx = ranked_doc.original_rank
                result = results[original_idx].copy()
                result["rerank_score"] = ranked_doc.score
                final_results.append(result)

            results = final_results
        else:
            # Just take top k
            results = results[: args.k]

        # Display results
        print(f"Found {len(results)} matching facts:")
        print()

        for i, result in enumerate(results, 1):
            if "rerank_score" in result:
                score = result["rerank_score"]
                print(f"{i}. [{score:.2f}] {result['key']}: {result['value']}")
            else:
                score = result.get("similarity", 0.0)
                print(f"{i}. [{score:.2f}] {result['key']}: {result['value']}")

            confidence = result.get("confidence", 1.0)
            similarity = result.get("similarity", 0.0)
            print(f"   Confidence: {confidence:.2f}, Similarity: {similarity:.2f}")
            print()

        return 0

    finally:
        await embedder.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
