#!/usr/bin/env python3
"""CLI entry point for the Native REPL Research Coordinator.

This module provides the command-line interface for running research
using the Native REPL approach (Approach 3).

Usage:
    uv run python -m scripts.agentica.native_repl.cli --topic "Python async patterns"

    # With options
    uv run python -m scripts.agentica.native_repl.cli \
        --topic "MCP server patterns" \
        --depth deep \
        --max-sections 7 \
        --output research.md \
        --track

Functions:
    parse_args: Parse command-line arguments
    main: Async main entry point
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .coordinator import ResearchCoordinator
from .models import ResearchDocument


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Native REPL Research Coordinator (Approach 3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic research
  %(prog)s --topic "Python async patterns" --output research.md

  # Deep research with more sections
  %(prog)s --topic "AI observability" --depth deep --max-sections 7

  # With tracking enabled
  %(prog)s --topic "MCP architecture" --track --output research.md

  # JSON output
  %(prog)s --topic "API design" --format json --output research.json
        """,
    )

    parser.add_argument("--topic", "-t", required=True, help="Research topic to investigate")
    parser.add_argument(
        "--depth",
        "-d",
        choices=["standard", "deep"],
        default="standard",
        help="Research depth (default: standard)",
    )
    parser.add_argument(
        "--max-sections",
        "-m",
        type=int,
        default=5,
        help="Maximum sections to create (default: 5)",
    )
    parser.add_argument(
        "--model", help="Model to use for Agentica agents (e.g., anthropic:claude-sonnet-4)"
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("--track", action="store_true", help="Enable CoordinationDB tracking")

    return parser.parse_args()


def setup_tracking() -> object | None:
    """Setup CoordinationDB if available.

    Returns:
        CoordinationDB instance or None
    """
    try:
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB()
        print(f"[Tracking] Session: {db.session_id}", file=sys.stderr)
        return db
    except ImportError:
        print("[Warning] CoordinationDB not available, tracking disabled", file=sys.stderr)
        return None


def format_output(document: ResearchDocument, output_format: str) -> str:
    """Format the research document for output.

    Args:
        document: The research document to format
        output_format: Either "markdown" or "json"

    Returns:
        Formatted string
    """
    if output_format == "json":
        return json.dumps(document.to_dict(), indent=2, default=str)
    return document.to_markdown()


def print_tracking_summary(db: object) -> None:
    """Print tracking summary if available.

    Args:
        db: CoordinationDB instance
    """
    try:
        summary = db.get_session_summary()  # type: ignore[attr-defined]
        print("\n=== Tracking Summary ===", file=sys.stderr)
        print(f"Agents: {summary.get('agents_by_status', {})}", file=sys.stderr)
        print(f"Patterns: {summary.get('agents_by_pattern', {})}", file=sys.stderr)
    except (AttributeError, TypeError):
        # DB object doesn't have get_session_summary or returned invalid type
        print("[Tracking] Summary unavailable", file=sys.stderr)


async def run_research(args: argparse.Namespace) -> None:
    """Run the research workflow.

    Args:
        args: Parsed command-line arguments
    """
    # Setup tracking if requested
    db = None
    if args.track:
        db = setup_tracking()

    # Create coordinator
    coordinator = ResearchCoordinator(
        topic=args.topic,
        depth=args.depth,
        max_sections=args.max_sections,
        model=args.model,
        db=db,
    )

    # Print header
    print("=== Native REPL Research Coordinator ===", file=sys.stderr)
    print(f"Topic: {args.topic}", file=sys.stderr)
    print(f"Depth: {args.depth}, Max sections: {args.max_sections}", file=sys.stderr)
    print("", file=sys.stderr)

    # Execute research
    print("[Coordinator] Starting research...", file=sys.stderr)
    document = await coordinator.research()

    # Format output
    output = format_output(document, args.format)

    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output)
        print(f"[Output] Research saved to: {args.output}", file=sys.stderr)
    else:
        print(output)

    # Print tracking summary if enabled
    if db:
        print_tracking_summary(db)


async def main() -> None:
    """Main entry point for CLI."""
    args = parse_args()
    await run_research(args)


if __name__ == "__main__":
    asyncio.run(main())
