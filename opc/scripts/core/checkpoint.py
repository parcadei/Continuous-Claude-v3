#!/usr/bin/env python3
"""Checkpoint management for session continuity and crash recovery.

Store and retrieve checkpoints in PostgreSQL for resumable workflows.
Checkpoints track phase progress, context usage, and modified files.

Usage:
    # Create a checkpoint
    uv run python scripts/core/checkpoint.py create \
        --session-id "abc123" \
        --phase "implementation" \
        --context-usage 0.45 \
        --files "src/foo.py,src/bar.py" \
        --unknowns "Need to clarify API format"

    # Get latest checkpoint
    uv run python scripts/core/checkpoint.py get \
        --session-id "abc123"

    # List recent checkpoints
    uv run python scripts/core/checkpoint.py list \
        --session-id "abc123" \
        --limit 5

    # Cleanup old checkpoints
    uv run python scripts/core/checkpoint.py cleanup \
        --session-id "abc123" \
        --keep 3

Environment:
    DATABASE_URL: PostgreSQL connection string
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load global ~/.claude/.env first, then local .env
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)
load_dotenv()

# Add project to path
project_dir = os.environ.get("CLAUDE_PROJECT_DIR", str(Path(__file__).parent.parent.parent))
sys.path.insert(0, project_dir)


async def create_checkpoint(
    session_id: str,
    phase: str,
    agent_id: str | None = None,
    context_usage: float | None = None,
    files_modified: list[str] | None = None,
    unknowns: list[str] | None = None,
    handoff_path: str | None = None,
) -> str:
    """Create a new checkpoint."""
    from scripts.core.db.memory_service_pg import MemoryServicePG

    memory = MemoryServicePG(session_id=session_id, agent_id=agent_id)
    await memory.connect()

    try:
        checkpoint_id = await memory.create_checkpoint(
            phase=phase,
            context_usage=context_usage,
            files_modified=files_modified,
            unknowns=unknowns,
            handoff_path=handoff_path,
        )
        return checkpoint_id
    finally:
        await memory.close()


async def get_latest_checkpoint(
    session_id: str,
    agent_id: str | None = None,
) -> dict | None:
    """Get the most recent checkpoint."""
    from scripts.core.db.memory_service_pg import MemoryServicePG

    memory = MemoryServicePG(session_id=session_id, agent_id=agent_id)
    await memory.connect()

    try:
        return await memory.get_latest_checkpoint()
    finally:
        await memory.close()


async def list_checkpoints(
    session_id: str,
    agent_id: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """List recent checkpoints."""
    from scripts.core.db.memory_service_pg import MemoryServicePG

    memory = MemoryServicePG(session_id=session_id, agent_id=agent_id)
    await memory.connect()

    try:
        return await memory.get_checkpoints(limit=limit)
    finally:
        await memory.close()


async def cleanup_checkpoints(
    session_id: str,
    agent_id: str | None = None,
    keep_count: int = 5,
) -> int:
    """Cleanup old checkpoints, keeping only recent ones."""
    from scripts.core.db.memory_service_pg import MemoryServicePG

    memory = MemoryServicePG(session_id=session_id, agent_id=agent_id)
    await memory.connect()

    try:
        return await memory.cleanup_old_checkpoints(keep_count=keep_count)
    finally:
        await memory.close()


def format_checkpoint(cp: dict, verbose: bool = False) -> str:
    """Format a checkpoint for display."""
    created = cp.get("created_at")
    if isinstance(created, datetime):
        created_str = created.strftime("%Y-%m-%d %H:%M:%S")
    else:
        created_str = str(created) if created else "unknown"

    context = cp.get("context_usage")
    context_str = f"{context:.0%}" if context is not None else "N/A"

    files = cp.get("files_modified", [])
    files_str = f"{len(files)} files" if files else "no files"

    line = f"[{created_str}] {cp.get('phase', 'unknown')} | context: {context_str} | {files_str}"

    if verbose:
        line += f"\n  ID: {cp.get('id')}"
        line += f"\n  Agent: {cp.get('agent_id')}"
        if files:
            line += f"\n  Files: {', '.join(files)}"
        unknowns = cp.get("unknowns", [])
        if unknowns:
            line += f"\n  Unknowns: {', '.join(unknowns)}"
        if cp.get("handoff_path"):
            line += f"\n  Handoff: {cp.get('handoff_path')}"

    return line


def main():
    parser = argparse.ArgumentParser(
        description="Checkpoint management for session continuity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new checkpoint")
    create_parser.add_argument("--session-id", required=True, help="Session identifier")
    create_parser.add_argument("--phase", required=True, help="Current work phase")
    create_parser.add_argument("--agent-id", help="Optional agent identifier")
    create_parser.add_argument("--context-usage", type=float, help="Context usage (0.0-1.0)")
    create_parser.add_argument("--files", help="Comma-separated list of modified files (deprecated)")
    create_parser.add_argument("--files-json", help="JSON array of modified files")
    create_parser.add_argument("--unknowns", help="Comma-separated list of unknowns (deprecated)")
    create_parser.add_argument("--unknowns-json", help="JSON array of unknowns/questions")
    create_parser.add_argument("--handoff-path", help="Path to associated handoff file")

    # Get command
    get_parser = subparsers.add_parser("get", help="Get latest checkpoint")
    get_parser.add_argument("--session-id", required=True, help="Session identifier")
    get_parser.add_argument("--agent-id", help="Optional agent identifier")
    get_parser.add_argument("--json", action="store_true", help="Output as JSON")
    get_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # List command
    list_parser = subparsers.add_parser("list", help="List recent checkpoints")
    list_parser.add_argument("--session-id", required=True, help="Session identifier")
    list_parser.add_argument("--agent-id", help="Optional agent identifier")
    list_parser.add_argument("--limit", type=int, default=10, help="Max checkpoints to show")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old checkpoints")
    cleanup_parser.add_argument("--session-id", required=True, help="Session identifier")
    cleanup_parser.add_argument("--agent-id", help="Optional agent identifier")
    cleanup_parser.add_argument("--keep", type=int, default=5, help="Number to keep")

    args = parser.parse_args()

    if args.command == "create":
        # Prefer JSON args (safe for special chars) over comma-separated (deprecated)
        files = None
        if args.files_json:
            try:
                files = json.loads(args.files_json)
                if not isinstance(files, list):
                    print("Error: --files-json must be a JSON array", file=sys.stderr)
                    sys.exit(1)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in --files-json: {e}", file=sys.stderr)
                sys.exit(1)
        elif args.files:
            files = [f.strip() for f in args.files.split(",") if f.strip()]

        unknowns = None
        if args.unknowns_json:
            try:
                unknowns = json.loads(args.unknowns_json)
                if not isinstance(unknowns, list):
                    print("Error: --unknowns-json must be a JSON array", file=sys.stderr)
                    sys.exit(1)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in --unknowns-json: {e}", file=sys.stderr)
                sys.exit(1)
        elif args.unknowns:
            unknowns = [u.strip() for u in args.unknowns.split(",") if u.strip()]

        checkpoint_id = asyncio.run(
            create_checkpoint(
                session_id=args.session_id,
                phase=args.phase,
                agent_id=args.agent_id,
                context_usage=args.context_usage,
                files_modified=files,
                unknowns=unknowns,
                handoff_path=args.handoff_path,
            )
        )
        print(f"Created checkpoint: {checkpoint_id}")

    elif args.command == "get":
        cp = asyncio.run(
            get_latest_checkpoint(
                session_id=args.session_id,
                agent_id=args.agent_id,
            )
        )
        if cp is None:
            print("No checkpoint found")
            sys.exit(1)

        if args.json:
            # Convert datetime to string for JSON
            if isinstance(cp.get("created_at"), datetime):
                cp["created_at"] = cp["created_at"].isoformat()
            print(json.dumps(cp, indent=2))
        else:
            print(format_checkpoint(cp, verbose=args.verbose))

    elif args.command == "list":
        checkpoints = asyncio.run(
            list_checkpoints(
                session_id=args.session_id,
                agent_id=args.agent_id,
                limit=args.limit,
            )
        )
        if not checkpoints:
            print("No checkpoints found")
            sys.exit(0)

        if args.json:
            for cp in checkpoints:
                if isinstance(cp.get("created_at"), datetime):
                    cp["created_at"] = cp["created_at"].isoformat()
            print(json.dumps(checkpoints, indent=2))
        else:
            for cp in checkpoints:
                print(format_checkpoint(cp, verbose=args.verbose))

    elif args.command == "cleanup":
        deleted = asyncio.run(
            cleanup_checkpoints(
                session_id=args.session_id,
                agent_id=args.agent_id,
                keep_count=args.keep,
            )
        )
        print(f"Deleted {deleted} old checkpoints")


if __name__ == "__main__":
    main()
