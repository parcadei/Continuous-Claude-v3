"""
CLI for temporal memory operations.

USAGE:
    uv run python -m scripts.temporal_memory.cli summarize --session-id abc123
    uv run python -m scripts.temporal_memory.cli record --session-id abc123 --turn 5 --facts '{"key": "value"}'

Commands:
    summarize   Generate temporal summary for a session
    record      Record facts at a specific turn

Examples:
    # Record facts at turn 1
    uv run python -m scripts.temporal_memory.cli record \\
        --session-id "session-abc" \\
        --turn 1 \\
        --facts '{"phase": "testing", "db": "sqlite"}'

    # Get JSON summary
    uv run python -m scripts.temporal_memory.cli summarize \\
        --session-id "session-abc" \\
        --output json

    # Get markdown summary with custom token budget
    uv run python -m scripts.temporal_memory.cli summarize \\
        --session-id "session-abc" \\
        --output markdown \\
        --budget 500
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .store import TemporalMemoryStore
from .summarizer import TemporalSummarizer


async def cmd_summarize(args: argparse.Namespace) -> None:
    """Summarize temporal memory.

    Generates a summary of the temporal memory state for a session,
    including invariants, open questions, transitions, and current state.

    Args:
        args: Parsed command line arguments containing:
            - session_id: Session identifier
            - budget: Token budget for summary
            - output: Output format (json or markdown)
            - db_path: Optional custom database path
    """
    db_path = Path(args.db_path) if args.db_path else None
    store = TemporalMemoryStore(session_id=args.session_id, db_path=db_path)
    await store.connect()

    summarizer = TemporalSummarizer()
    summary = await summarizer.summarize(store, budget_tokens=args.budget)

    if args.output == "json":
        print(json.dumps(summary))
    else:
        print_markdown_summary(summary)


async def cmd_record(args: argparse.Namespace) -> None:
    """Record facts at a turn.

    Stores facts in the temporal memory database for later summarization.
    Facts are associated with a session ID and turn number.

    Args:
        args: Parsed command line arguments containing:
            - session_id: Session identifier
            - turn: Turn number
            - facts: JSON string of facts to record
            - db_path: Optional custom database path
    """
    db_path = Path(args.db_path) if args.db_path else None
    store = TemporalMemoryStore(session_id=args.session_id, db_path=db_path)
    await store.connect()

    try:
        facts = json.loads(args.facts)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "message": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)

    await store.record_with_erotetic(turn=args.turn, facts=facts)

    print(json.dumps({"status": "ok", "turn": args.turn}))


def print_markdown_summary(summary: dict[str, Any]) -> None:
    """Print summary in markdown format.

    Formats the temporal summary as human-readable markdown with sections
    for open questions, invariants, pending goals, and transitions.

    Args:
        summary: Dictionary containing temporal summary data
    """
    print(f"# Temporal Summary (Turn {summary['turn_count']})\n")

    print("## Open Questions")
    open_questions = summary.get("open_questions", [])
    if open_questions:
        for q in open_questions:
            print(f"- {q}")
    else:
        print("- (none)")

    print("\n## Invariants")
    invariants = summary.get("invariants", [])
    if invariants:
        for inv in invariants:
            print(f"- {inv}")
    else:
        print("- (none)")

    print("\n## Pending Goals")
    pending_goals = summary.get("pending_goals", [])
    if pending_goals:
        for g in pending_goals:
            print(f"- [ ] {g}")
    else:
        print("- (none)")

    print("\n## Transitions")
    transitions = summary.get("transitions", [])
    if transitions:
        for t in transitions:
            print(f"- {t}")
    else:
        print("- (none)")

    print(f"\n*Token estimate: {summary.get('token_estimate', 0)}*")


def main() -> None:
    """Main entry point for temporal memory CLI.

    Parses command line arguments and dispatches to the appropriate
    command handler (summarize or record).
    """
    parser = argparse.ArgumentParser(
        description="Temporal Memory CLI - TEL-based memory for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Summarize command
    p_sum = subparsers.add_parser(
        "summarize",
        help="Generate temporal summary for a session",
        description="Summarize the temporal memory state including invariants, "
        "open questions, transitions, and current state.",
    )
    p_sum.add_argument(
        "--session-id",
        required=True,
        help="Session identifier to summarize",
    )
    p_sum.add_argument(
        "--budget",
        type=int,
        default=2000,
        help="Token budget for summary (default: 2000)",
    )
    p_sum.add_argument(
        "--output",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    p_sum.add_argument(
        "--db-path",
        help="Custom database path (default: .claude/cache/temporal-memory/temporal.db)",
    )

    # Record command
    p_rec = subparsers.add_parser(
        "record",
        help="Record facts at a specific turn",
        description="Store facts in the temporal memory database for later summarization.",
    )
    p_rec.add_argument(
        "--session-id",
        required=True,
        help="Session identifier",
    )
    p_rec.add_argument(
        "--turn",
        type=int,
        required=True,
        help="Turn number",
    )
    p_rec.add_argument(
        "--facts",
        required=True,
        help='JSON string of facts to record (e.g., \'{"key": "value"}\')',
    )
    p_rec.add_argument(
        "--db-path",
        help="Custom database path (default: .claude/cache/temporal-memory/temporal.db)",
    )

    args = parser.parse_args()

    if args.command == "summarize":
        asyncio.run(cmd_summarize(args))
    elif args.command == "record":
        asyncio.run(cmd_record(args))


if __name__ == "__main__":
    main()
