#!/usr/bin/env python3
"""
USAGE: Process a single math textbook from Ragie and extract techniques by topic.

    uv run python scripts/process_math_book.py --book-id <ID> --book-name <NAME>

Arguments:
    --book-id       Ragie document ID (required)
    --book-name     Human-readable book name (required)
    --output-dir    Output directory (default: thoughts/shared/books)
    --topics        Comma-separated topic categories to query (default: all)

Example:
    uv run python scripts/process_math_book.py \
        --book-id "06bf70b1-c44d-4bbc-a553-37031f70f36f" \
        --book-name "Linear Algebra (Hoffman-Kunze)"
"""

import argparse
import httpx
import os
import json
import sys
from pathlib import Path

# Topic categories and their subtopics for extraction
TOPICS = {
    "real-analysis": [
        "limits and continuity",
        "convergence of sequences and series",
        "differentiation techniques",
        "integration techniques",
        "metric spaces",
    ],
    "linear-algebra": [
        "matrices and determinants",
        "eigenvalues and eigenvectors",
        "vector spaces and subspaces",
        "linear transformations",
        "inner product spaces",
    ],
    "probability": [
        "probability distributions",
        "expectation and variance",
        "conditional probability and Bayes theorem",
        "random variables",
        "limit theorems",
    ],
    "complex-analysis": [
        "analytic functions",
        "contour integration",
        "residue theorem",
        "conformal mappings",
        "power series",
    ],
    "topology": [
        "topological spaces",
        "continuity and homeomorphisms",
        "compactness",
        "connectedness",
        "fundamental group",
    ],
    "differential-equations": [
        "first order ODEs",
        "linear ODEs",
        "systems of equations",
        "boundary value problems",
        "stability analysis",
    ],
    "abstract-algebra": [
        "groups and homomorphisms",
        "rings and ideals",
        "fields and extensions",
        "modules",
        "Galois theory",
    ],
    "number-theory": [
        "divisibility and primes",
        "congruences",
        "quadratic reciprocity",
        "algebraic integers",
        "analytic number theory",
    ],
    "numerical-analysis": [
        "root finding methods",
        "interpolation",
        "numerical integration",
        "numerical linear algebra",
        "error analysis",
    ],
    "optimization": [
        "convex optimization",
        "gradient methods",
        "constrained optimization",
        "linear programming",
        "duality theory",
    ],
    "information-theory": [
        "entropy and information",
        "channel capacity",
        "source coding",
        "rate distortion",
        "network information theory",
    ],
    "category-theory": [
        "categories and functors",
        "natural transformations",
        "limits and colimits",
        "adjunctions",
        "monads",
    ],
}


def get_api_key() -> str:
    """Get Ragie API key from environment or .env file."""
    api_key = os.environ.get("RAGIE_API_KEY")
    if not api_key:
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.startswith("RAGIE_API_KEY="):
                        api_key = line.strip().split("=", 1)[1].strip('"\'')
                        break
    if not api_key:
        raise ValueError("RAGIE_API_KEY not found in environment or .env file")
    return api_key


def query_book_for_topic(
    api_key: str, book_id: str, topic: str, category: str
) -> list[dict]:
    """Query a specific book for a topic and return relevant chunks."""
    url = "https://api.ragie.ai/retrievals"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Note: partition must be in payload, not header
    payload = {
        "query": f"Key techniques, theorems, proofs, and problem-solving strategies for {topic} in {category}. Include worked examples and important lemmas.",
        "partition": "math-textbooks",
        "filter": {"document_id": {"$eq": book_id}},
        "top_k": 8,
        "rerank": True,
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
        return response.json().get("scored_chunks", [])
    except httpx.HTTPError as e:
        print(f"  Warning: Query failed for {category}/{topic}: {e}", file=sys.stderr)
        return []


def process_book(
    book_id: str,
    book_name: str,
    output_dir: str,
    topic_filter: list[str] | None = None,
) -> dict:
    """Process a book and extract techniques for all relevant topics."""
    api_key = get_api_key()

    results = {
        "book_id": book_id,
        "book_name": book_name,
        "topics": {},
        "summary": {"total_topics_queried": 0, "topics_with_results": 0},
    }

    categories_to_process = topic_filter if topic_filter else list(TOPICS.keys())

    for category in categories_to_process:
        if category not in TOPICS:
            print(f"  Skipping unknown category: {category}", file=sys.stderr)
            continue

        subtopics = TOPICS[category]
        for topic in subtopics:
            results["summary"]["total_topics_queried"] += 1
            print(f"  Querying: {category}/{topic}...")

            chunks = query_book_for_topic(api_key, book_id, topic, category)

            if chunks:
                results["summary"]["topics_with_results"] += 1
                key = f"{category}/{topic}"
                results["topics"][key] = []

                for chunk in chunks[:5]:  # Keep top 5 chunks per topic
                    text = chunk.get("text", "")
                    # Truncate very long chunks but keep enough context
                    if len(text) > 1500:
                        text = text[:1500] + "..."

                    results["topics"][key].append(
                        {
                            "score": round(chunk.get("score", 0), 4),
                            "text": text,
                        }
                    )

    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Use first 8 chars of ID for filename
    output_file = output_path / f"{book_id[:8]}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Process a math textbook and extract techniques by topic"
    )
    parser.add_argument("--book-id", required=True, help="Ragie document ID")
    parser.add_argument("--book-name", required=True, help="Human-readable book name")
    parser.add_argument(
        "--output-dir",
        default="thoughts/shared/books",
        help="Output directory for results",
    )
    parser.add_argument(
        "--topics",
        type=str,
        default=None,
        help="Comma-separated list of topic categories to query (default: all)",
    )
    args = parser.parse_args()

    topic_filter = None
    if args.topics:
        topic_filter = [t.strip() for t in args.topics.split(",")]

    print(f"Processing: {args.book_name}")
    print(f"Book ID: {args.book_id}")
    print(f"Output: {args.output_dir}")
    if topic_filter:
        print(f"Topics: {', '.join(topic_filter)}")
    print()

    results = process_book(
        args.book_id, args.book_name, args.output_dir, topic_filter
    )

    print()
    print(f"Complete!")
    print(f"  Topics queried: {results['summary']['total_topics_queried']}")
    print(f"  Topics with results: {results['summary']['topics_with_results']}")
    print(f"  Output saved to: {args.output_dir}/{args.book_id[:8]}.json")


if __name__ == "__main__":
    main()
