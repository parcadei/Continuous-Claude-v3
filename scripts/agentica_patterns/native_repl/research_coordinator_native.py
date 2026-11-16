#!/usr/bin/env python3
"""Hierarchical Research Coordinator - Native REPL Implementation.

This is the main entry point for running research using the Native REPL approach.
It provides a CLI interface to the ResearchCoordinator for conducting multi-agent
research on any topic.

Architecture:
    ResearchCoordinator (orchestrator)
        └── decompose() → splits topic into ResearchSections
        └── research_sections() → parallel specialist research
        └── synthesize() → aggregates findings into ResearchDocument

Usage:
    # Basic research
    python -m scripts.agentica.native_repl.research_coordinator_native "Python async patterns"

    # Deep research with more sections
    python -m scripts.agentica.native_repl.research_coordinator_native \\
        --topic "MCP server development" \\
        --depth deep \\
        --max-sections 5

    # Output as JSON
    python -m scripts.agentica.native_repl.research_coordinator_native \\
        --topic "Agentica SDK usage" \\
        --output json

Components (all in scripts/agentica/native_repl/):
    - models.py: Data classes (ResearchSection, ResearchFindings, ResearchDocument)
    - coordinator.py: ResearchCoordinator class
    - json_utils.py: JSON parsing utilities
    - tools.py: Claude Code CLI tool wrappers
    - run_claude.py: Async wrapper for Claude Code CLI

References:
    - Plan: thoughts/shared/plans/2025-12-25-hierarchical-research.md
    - Tests: tests/unit/test_research_coordinator_native.py
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Re-export core components for convenience
from .coordinator import ResearchCoordinator
from .json_utils import parse_json_dict, parse_json_list
from .models import ResearchDocument, ResearchFindings, ResearchSection
from .run_claude import (
    ClaudeExecutionError,
    ClaudeParseError,
    read_file,
    run_bash,
    run_claude,
    search_codebase,
    write_file,
)
from .tools import (
    codebase_research,
    comprehensive_research,
    docs_research,
    get_tool_scope,
    web_research,
)

__all__ = [
    # Core classes
    "ResearchCoordinator",
    "ResearchSection",
    "ResearchFindings",
    "ResearchDocument",
    # JSON utilities
    "parse_json_list",
    "parse_json_dict",
    # Claude Code wrappers
    "run_claude",
    "read_file",
    "write_file",
    "search_codebase",
    "run_bash",
    # Research tools
    "web_research",
    "codebase_research",
    "docs_research",
    "comprehensive_research",
    "get_tool_scope",
    # Exceptions
    "ClaudeExecutionError",
    "ClaudeParseError",
]


async def run_research(
    topic: str,
    depth: str = "standard",
    max_sections: int = 5,
    model: Optional[str] = None,
    output_format: str = "markdown",
    output_file: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> ResearchDocument:
    """Run the full research workflow.

    Args:
        topic: Research topic to investigate
        depth: Research depth ("standard" or "deep")
        max_sections: Maximum number of sections to decompose into
        model: Optional model override (e.g., "sonnet", "opus")
        output_format: Output format ("markdown" or "json")
        output_file: Optional file path to write results to
        db_path: Optional CoordinationDB path for tracking

    Returns:
        ResearchDocument with all findings

    Example:
        >>> doc = await run_research("Python async patterns", depth="deep")
        >>> print(doc.to_markdown())
    """
    # Optional CoordinationDB for tracking
    db = None
    if db_path:
        from scripts.agentica_patterns.coordination import CoordinationDB
        db = CoordinationDB(db_path=db_path)

    # Create coordinator
    coordinator = ResearchCoordinator(
        topic=topic,
        depth=depth,
        max_sections=max_sections,
        model=model,
        db=db,
    )

    # Run research
    print(f"[Coordinator] Starting research on: {topic}", file=sys.stderr)
    print(f"[Coordinator] Depth: {depth}, Max sections: {max_sections}", file=sys.stderr)

    document = await coordinator.research()

    # Format output
    if output_format == "json":
        output = json.dumps(document.to_dict(), indent=2)
    else:
        output = document.to_markdown()

    # Write to file if specified
    if output_file:
        output_file.write_text(output)
        print(f"[Coordinator] Wrote results to: {output_file}", file=sys.stderr)

    return document


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser.

    Returns:
        Configured argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Hierarchical Research Coordinator - Native REPL Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic research
    %(prog)s "Python async patterns"

    # Deep research with custom settings
    %(prog)s --topic "MCP servers" --depth deep --max-sections 5

    # JSON output to file
    %(prog)s --topic "Agentica SDK" --output json --output-file research.json
        """,
    )

    parser.add_argument(
        "topic",
        nargs="?",
        help="Research topic (can also use --topic)",
    )

    parser.add_argument(
        "-t", "--topic",
        dest="topic_flag",
        help="Research topic (alternative to positional argument)",
    )

    parser.add_argument(
        "-d", "--depth",
        choices=["standard", "deep"],
        default="standard",
        help="Research depth (default: standard)",
    )

    parser.add_argument(
        "-m", "--max-sections",
        type=int,
        default=5,
        help="Maximum sections to decompose into (default: 5)",
    )

    parser.add_argument(
        "--model",
        help="Model override (e.g., 'sonnet', 'opus')",
    )

    parser.add_argument(
        "-o", "--output",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )

    parser.add_argument(
        "-f", "--output-file",
        type=Path,
        help="Write output to file",
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to CoordinationDB for tracking",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    return parser


async def main_async(args: argparse.Namespace) -> int:
    """Async main entry point.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Determine topic from positional or flag argument
    topic = args.topic or args.topic_flag
    if not topic:
        print("Error: Topic is required", file=sys.stderr)
        return 1

    try:
        document = await run_research(
            topic=topic,
            depth=args.depth,
            max_sections=args.max_sections,
            model=args.model,
            output_format=args.output,
            output_file=args.output_file,
            db_path=args.db_path,
        )

        # Print output to stdout
        if args.output == "json":
            print(json.dumps(document.to_dict(), indent=2))
        else:
            print(document.to_markdown())

        return 0

    except ClaudeExecutionError as e:
        print(f"Error: Claude Code execution failed: {e}", file=sys.stderr)
        return 1
    except ClaudeParseError as e:
        print(f"Error: Failed to parse Claude output: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
