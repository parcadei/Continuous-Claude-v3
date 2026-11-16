#!/usr/bin/env python3
"""
USAGE: aggregate_book_extractions.py --output PATH [--input-dir DIR] [--dry-run]

Aggregate book extraction JSON files into a unified searchable topic index.

This script:
1. Loads all book JSON files from the input directory
2. Builds a unified topic index mapping topics to book references
3. Cross-references topics to find books covering the same subject
4. Exports the aggregated index as JSON

Examples:
    # Aggregate books from default directory
    uv run python scripts/aggregate_book_extractions.py --output unified_index.json

    # Use custom input directory
    uv run python scripts/aggregate_book_extractions.py --input-dir ./my_books --output index.json

    # Preview without writing (dry run)
    uv run python scripts/aggregate_book_extractions.py --output index.json --dry-run

Book JSON structure (input):
{
    "book_id": "uuid",
    "book_name": "Book Title",
    "topics": {
        "category/topic": [
            {"score": 0.85, "text": "extracted text..."}
        ]
    }
}

Topic Index structure (output):
{
    "metadata": {
        "total_books": 3,
        "total_topics": 10,
        "generated_at": "2025-01-01T00:00:00"
    },
    "topics": {
        "category/topic": [
            {
                "book_id": "uuid",
                "book_name": "Book Title",
                "extractions": [{"score": 0.85, "text": "..."}]
            }
        ]
    }
}
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_book_json(path: Path) -> dict[str, Any]:
    """
    Load a single book JSON file.

    Args:
        path: Path to the book JSON file

    Returns:
        Dictionary with book_id, book_name, and topics

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    if not path.exists():
        raise FileNotFoundError(f"Book file not found: {path}")

    content = path.read_text()
    return json.loads(content)


def aggregate_multiple_books(directory: Path) -> list[dict[str, Any]]:
    """
    Load all book JSON files from a directory.

    Args:
        directory: Path to directory containing book JSON files

    Returns:
        List of book dictionaries
    """
    books: list[dict[str, Any]] = []

    if not directory.exists():
        return books

    for file_path in directory.iterdir():
        if file_path.suffix.lower() == ".json":
            try:
                book = load_book_json(file_path)
                books.append(book)
            except (json.JSONDecodeError, FileNotFoundError):
                # Skip invalid files
                continue

    return books


def build_topic_index(books: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """
    Build a unified topic index from multiple books.

    The index maps each topic to a list of book references that cover it.

    Args:
        books: List of book dictionaries

    Returns:
        Dictionary mapping topic names to lists of book references.
        Each reference contains:
        - book_id: UUID of the book
        - book_name: Human-readable book title
        - extractions: List of {score, text} from this book for this topic
    """
    topic_index: dict[str, list[dict[str, Any]]] = {}

    for book in books:
        book_id = book.get("book_id", "")
        book_name = book.get("book_name", "")
        topics = book.get("topics", {})

        for topic_name, extractions in topics.items():
            if topic_name not in topic_index:
                topic_index[topic_name] = []

            # Add this book's extractions for this topic
            book_ref = {
                "book_id": book_id,
                "book_name": book_name,
                "extractions": extractions,
            }
            topic_index[topic_name].append(book_ref)

    return topic_index


def cross_reference_topics(
    topic_index: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """
    Enrich the topic index with cross-reference information.

    Adds scoring metadata to help identify the best sources for each topic.

    Args:
        topic_index: Output from build_topic_index

    Returns:
        Enriched topic index where each book reference includes:
        - book_id: UUID of the book
        - book_name: Human-readable book title
        - max_score: Highest extraction score for this topic in this book
        - extractions: List of {score, text} extractions
    """
    cross_ref: dict[str, list[dict[str, Any]]] = {}

    for topic_name, book_refs in topic_index.items():
        enriched_refs: list[dict[str, Any]] = []

        for ref in book_refs:
            extractions = ref.get("extractions", [])

            # Calculate max score for ranking
            scores = [ext.get("score", 0) for ext in extractions if "score" in ext]
            max_score = max(scores) if scores else 0.0

            enriched_ref = {
                "book_id": ref.get("book_id", ""),
                "book_name": ref.get("book_name", ""),
                "max_score": max_score,
                "extractions": extractions,
            }
            enriched_refs.append(enriched_ref)

        # Sort by max_score descending (best sources first)
        enriched_refs.sort(key=lambda x: x.get("max_score", 0), reverse=True)
        cross_ref[topic_name] = enriched_refs

    return cross_ref


def export_unified_index(
    topic_index: dict[str, list[dict[str, Any]]],
    output_path: Path,
    dry_run: bool = False,
) -> None:
    """
    Export the topic index to a JSON file.

    Args:
        topic_index: The topic index to export
        output_path: Path for the output JSON file
        dry_run: If True, don't write the file (for preview)
    """
    if dry_run:
        return

    # Count unique books across all topics
    all_book_ids: set[str] = set()
    for refs in topic_index.values():
        for ref in refs:
            if "book_id" in ref:
                all_book_ids.add(ref["book_id"])

    output_data = {
        "metadata": {
            "total_books": len(all_book_ids),
            "total_topics": len(topic_index),
            "generated_at": datetime.now().isoformat(),
        },
        "topics": topic_index,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_data, indent=2))


def main() -> None:
    """CLI entrypoint for aggregating book extractions."""
    parser = argparse.ArgumentParser(
        description="Aggregate book extraction JSON files into a unified topic index.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --output unified_index.json
    %(prog)s --input-dir ./books --output index.json
    %(prog)s --output index.json --dry-run
        """,
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("thoughts/shared/books"),
        help="Directory containing book JSON files (default: thoughts/shared/books)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for the unified index JSON",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without writing output file",
    )

    args = parser.parse_args()

    # Load all books
    books = aggregate_multiple_books(args.input_dir)

    # Build topic index
    topic_index = build_topic_index(books)

    # Enrich with cross-references
    cross_ref_index = cross_reference_topics(topic_index)

    # Print summary
    print(f"Loaded {len(books)} books")
    print(f"Found {len(topic_index)} unique topics")

    # Find shared topics (covered by multiple books)
    shared_topics = [t for t, refs in cross_ref_index.items() if len(refs) > 1]
    print(f"Found {len(shared_topics)} topics shared across multiple books")

    if args.dry_run:
        print(f"\n[DRY RUN] Would write index to: {args.output}")
    else:
        # Export
        export_unified_index(cross_ref_index, args.output, dry_run=args.dry_run)
        print(f"\nWrote unified index to: {args.output}")


if __name__ == "__main__":
    main()
