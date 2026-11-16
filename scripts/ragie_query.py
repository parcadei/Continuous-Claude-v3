#!/usr/bin/env python3
"""
USAGE: Query Ragie for relevant document chunks.

Examples:
    # Simple query
    uv run python scripts/ragie_query.py --query "What is the Bellman equation?"

    # Query with partition filter
    uv run python scripts/ragie_query.py --query "Kripke semantics" --partition modal-logic

    # Query with more results
    uv run python scripts/ragie_query.py --query "expected utility maximization" --top-k 10

    # Query with rerank for better relevance
    uv run python scripts/ragie_query.py --query "Nash equilibrium" --rerank
"""

import argparse
import json
import os
import sys

import httpx
from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv()


def query_ragie(
    query: str,
    partition: str | None,
    top_k: int,
    rerank: bool,
    api_key: str
) -> dict:
    """Query Ragie for relevant chunks."""
    url = "https://api.ragie.ai/retrievals"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": query,
        "top_k": top_k,
    }
    if partition:
        payload["partition"] = partition
    if rerank:
        payload["rerank"] = True

    response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()


def format_results(results: dict) -> str:
    """Format results for human-readable output."""
    chunks = results.get("scored_chunks", [])
    if not chunks:
        return "No results found."

    output = []
    for i, chunk in enumerate(chunks, 1):
        score = chunk.get("score", 0)
        text = chunk.get("text", "")[:500]  # Truncate for display
        doc_id = chunk.get("document_id", "unknown")
        metadata = chunk.get("metadata", {})

        output.append(f"--- Result {i} (score: {score:.3f}) ---")
        output.append(f"Document: {doc_id}")
        if metadata:
            output.append(f"Metadata: {json.dumps(metadata)}")
        output.append(f"Text: {text}...")
        output.append("")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Query Ragie for document retrieval")
    parser.add_argument("--query", "-q", type=str, required=True, help="Search query")
    parser.add_argument("--partition", "-p", type=str, help="Filter by partition")
    parser.add_argument("--top-k", "-k", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--rerank", action="store_true", help="Enable reranking for better relevance")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    args = parser.parse_args()

    api_key = os.environ.get("RAGIE_API_KEY")
    if not api_key:
        print("Error: RAGIE_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    try:
        results = query_ragie(
            query=args.query,
            partition=args.partition,
            top_k=args.top_k,
            rerank=args.rerank,
            api_key=api_key
        )

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(format_results(results))

    except httpx.HTTPStatusError as e:
        print(f"Error: API request failed: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
