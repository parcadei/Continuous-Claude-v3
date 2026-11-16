#!/usr/bin/env python3
"""
OEIS Sequence Lookup Script

Search and retrieve sequences from the On-Line Encyclopedia of Integer Sequences.

USAGE:
    # Search by sequence terms
    uv run python scripts/oeis_lookup.py search "1,1,2,3,5,8,13"

    # Search by keyword
    uv run python scripts/oeis_lookup.py search "prime numbers"

    # Get specific sequence by A-number
    uv run python scripts/oeis_lookup.py get A000045

    # Search with max results
    uv run python scripts/oeis_lookup.py search "fibonacci" --max-results 3

API Reference:
    Base URL: https://oeis.org/search
    Documentation: https://oeis.org/wiki/Lookup
"""

import argparse
import json
import re
import sys
from typing import Any

import requests

# OEIS API base URL
OEIS_BASE_URL = "https://oeis.org/search"

# Timeout for API requests (seconds)
REQUEST_TIMEOUT = 30


def search_oeis(query: str, max_results: int = 10) -> dict[str, Any]:
    """
    Search OEIS for sequences matching the query.

    Args:
        query: Search query (sequence terms, keywords, or A-number)
        max_results: Maximum number of results to return

    Returns:
        Dictionary with 'results' list or 'error' message
    """
    try:
        response = requests.get(
            OEIS_BASE_URL,
            params={"q": query, "fmt": "json"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            return {"error": f"API error: HTTP {response.status_code}"}

        data = response.json()

        # OEIS API returns either:
        # - A list of sequences directly (real API)
        # - A dict with "results" key (as per some docs)
        if isinstance(data, list):
            raw_results = data
        elif isinstance(data, dict):
            raw_results = data.get("results") or []
        else:
            raw_results = []

        # Parse and format results
        results = []
        for seq in raw_results[:max_results]:
            results.append(_format_sequence(seq))

        return {
            "query": query,
            "count": len(results),
            "results": results,
        }

    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON response: {str(e)}"}


def get_sequence(a_number: str) -> dict[str, Any]:
    """
    Get a specific sequence by its A-number.

    Args:
        a_number: OEIS A-number (e.g., "A000045" for Fibonacci)

    Returns:
        Dictionary with sequence data or 'error' message
    """
    # Validate A-number format
    normalized = a_number.upper().strip()

    # Must start with A followed by digits
    if not re.match(r"^A\d+$", normalized):
        return {"error": f"Invalid A-number format: '{a_number}'. Expected format: A000045"}

    try:
        response = requests.get(
            OEIS_BASE_URL,
            params={"q": normalized, "fmt": "json"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            return {"error": f"API error: HTTP {response.status_code}"}

        data = response.json()

        # OEIS API returns either:
        # - A list of sequences directly (real API)
        # - A dict with "results" key (as per some docs)
        if isinstance(data, list):
            raw_results = data
        elif isinstance(data, dict):
            raw_results = data.get("results") or []
        else:
            raw_results = []

        if not raw_results:
            return {"error": f"Sequence not found: {normalized}"}

        # Return the first (and should be only) result
        seq = raw_results[0]
        result = _format_sequence(seq)

        # Ensure the ID matches what was requested
        result["id"] = normalized

        return result

    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON response: {str(e)}"}


def _format_sequence(seq: dict) -> dict[str, Any]:
    """
    Format a raw OEIS sequence result into a standardized structure.

    Args:
        seq: Raw sequence data from OEIS API

    Returns:
        Formatted sequence dictionary
    """
    # Format A-number with leading zeros (e.g., A000045)
    a_number = f"A{seq.get('number', 0):06d}"

    return {
        "id": a_number,
        "name": seq.get("name", ""),
        "data": seq.get("data", ""),
        "keywords": seq.get("keyword", "").split(",") if seq.get("keyword") else [],
        "formulas": seq.get("formula", []) or [],
        "author": seq.get("author", ""),
        "offset": seq.get("offset", ""),
        "references": seq.get("references", 0),
    }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="OEIS Sequence Lookup - Search and retrieve integer sequences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Search by sequence terms
    python scripts/oeis_lookup.py search "1,1,2,3,5,8,13"

    # Search by keyword
    python scripts/oeis_lookup.py search "prime numbers"

    # Get Fibonacci sequence
    python scripts/oeis_lookup.py get A000045
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Search subcommand
    search_parser = subparsers.add_parser(
        "search", help="Search for sequences by terms or keywords"
    )
    search_parser.add_argument(
        "query", type=str, help="Search query (sequence terms, keywords, or A-number)"
    )
    search_parser.add_argument(
        "--max-results",
        "-n",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)",
    )

    # Get subcommand
    get_parser = subparsers.add_parser("get", help="Get a specific sequence by A-number")
    get_parser.add_argument(
        "a_number", type=str, help="OEIS A-number (e.g., A000045 for Fibonacci)"
    )

    args = parser.parse_args()

    if args.command == "search":
        result = search_oeis(args.query, max_results=args.max_results)
    elif args.command == "get":
        result = get_sequence(args.a_number)
    else:
        parser.print_help()
        sys.exit(1)

    # Output as JSON
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
