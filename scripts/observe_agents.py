#!/usr/bin/env python3
"""
Observe running agents - query memory, blackboard, tasks, and outputs.

USAGE:
    # Query PostgreSQL memory tables
    uv run python scripts/observe_agents.py --what memory --query "API"
    uv run python scripts/observe_agents.py --what memory --session-id abc123

    # Read blackboard HOT tier
    uv run python scripts/observe_agents.py --what blackboard

    # Query task graph
    uv run python scripts/observe_agents.py --what tasks
    uv run python scripts/observe_agents.py --what tasks --session-id abc123

    # List agent output files
    uv run python scripts/observe_agents.py --what outputs

    # Combined observation of all sources
    uv run python scripts/observe_agents.py --what all
    uv run python scripts/observe_agents.py --what all --session-id abc123 --query "error"

    # Output as JSON
    uv run python scripts/observe_agents.py --what all --json

This script provides unified observation of agent activity across:
1. PostgreSQL (archival_memory table) - persistent memory storage
2. Blackboard HOT tier (JSON files) - inter-agent communication
3. Task graph (SQLite) - task coordination state
4. Agent outputs (markdown files) - agent work products
"""

import argparse
import asyncio
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

# PostgreSQL connection
POSTGRES_URL = os.environ.get(
    "AGENTICA_POSTGRES_URL",
    "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
)

# Paths - use project-relative paths
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    "/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
))
BLACKBOARD_DIR = Path("/tmp/claude-blackboard")
TASKS_DB = PROJECT_DIR / ".claude" / "cache" / "agentica-coordination" / "tasks.db"
AGENTS_DIR = PROJECT_DIR / ".claude" / "cache" / "agents"


async def query_memory(
    query: str | None = None,
    session_id: str | None = None,
    limit: int = 20
) -> list[dict]:
    """Query PostgreSQL memory tables.

    Args:
        query: Text search query (searches content with ILIKE)
        session_id: Filter by session ID
        limit: Maximum number of results

    Returns:
        List of memory records as dictionaries
    """
    try:
        import asyncpg
    except ImportError:
        print("Warning: asyncpg not installed, skipping memory query")
        return []

    try:
        conn = await asyncpg.connect(POSTGRES_URL)
        try:
            sql = """
                SELECT id, session_id, agent_id, content, created_at
                FROM archival_memory
                WHERE ($1::text IS NULL OR content ILIKE '%' || $1 || '%')
                AND ($2::text IS NULL OR session_id = $2)
                ORDER BY created_at DESC
                LIMIT $3
            """
            rows = await conn.fetch(sql, query, session_id, limit)
            return [dict(r) for r in rows]
        finally:
            await conn.close()
    except Exception as e:
        print(f"Warning: Memory query failed: {e}")
        return []


def read_blackboard() -> dict[str, Any]:
    """Read all blackboard HOT tier JSON files.

    Returns:
        Dictionary mapping board names to their contents
    """
    results: dict[str, Any] = {}

    if not BLACKBOARD_DIR.exists():
        return results

    for f in BLACKBOARD_DIR.glob("*.json"):
        try:
            results[f.stem] = json.loads(f.read_text())
        except json.JSONDecodeError:
            results[f.stem] = {"error": "Invalid JSON"}
        except Exception as e:
            results[f.stem] = {"error": str(e)}

    return results


def query_task_graph(session_id: str | None = None) -> list[dict]:
    """Query task graph SQLite database.

    Args:
        session_id: Filter by session ID

    Returns:
        List of task records as dictionaries
    """
    if not TASKS_DB.exists():
        return []

    try:
        conn = sqlite3.connect(TASKS_DB)
        conn.row_factory = sqlite3.Row
        try:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE session_id = ? ORDER BY created_at DESC LIMIT 50",
                    (session_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            # Table doesn't exist
            return []
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: Task graph query failed: {e}")
        return []


def list_agent_outputs() -> list[dict]:
    """List agent output files.

    Returns:
        List of file metadata dictionaries, sorted by modification time (newest first)
    """
    results: list[dict] = []

    if not AGENTS_DIR.exists():
        return results

    for agent_dir in AGENTS_DIR.iterdir():
        if agent_dir.is_dir():
            for f in agent_dir.glob("*.md"):
                try:
                    stat = f.stat()
                    results.append({
                        "agent": agent_dir.name,
                        "file": f.name,
                        "path": str(f),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "size": stat.st_size,
                    })
                except Exception as e:
                    results.append({
                        "agent": agent_dir.name,
                        "file": f.name,
                        "path": str(f),
                        "error": str(e),
                    })

    return sorted(results, key=lambda x: x.get("modified", ""), reverse=True)


async def observe_all(
    query: str | None = None,
    session_id: str | None = None
) -> dict[str, Any]:
    """Combined observation of all sources.

    Args:
        query: Text search query for memory
        session_id: Filter by session ID for memory and tasks

    Returns:
        Dictionary with all observation results and metadata
    """
    memory = await query_memory(query, session_id)
    blackboard = read_blackboard()
    tasks = query_task_graph(session_id)
    outputs = list_agent_outputs()

    return {
        "timestamp": datetime.now().isoformat(),
        "filters": {
            "query": query,
            "session_id": session_id,
        },
        "memory": {"count": len(memory), "items": memory},
        "blackboard": {"count": len(blackboard), "boards": blackboard},
        "tasks": {"count": len(tasks), "items": tasks},
        "outputs": {"count": len(outputs), "items": outputs},
    }


def format_memory_output(items: list[dict]) -> str:
    """Format memory items for human-readable output."""
    if not items:
        return "No memory records found."

    lines = ["=== Memory Records ===", ""]
    for item in items:
        lines.append(f"ID: {item.get('id', 'unknown')}")
        lines.append(f"Session: {item.get('session_id', 'unknown')}")
        lines.append(f"Agent: {item.get('agent_id', 'unknown')}")
        lines.append(f"Created: {item.get('created_at', 'unknown')}")
        content = item.get('content', '')
        # Truncate long content
        if len(content) > 200:
            content = content[:200] + "..."
        lines.append(f"Content: {content}")
        lines.append("-" * 40)
    return "\n".join(lines)


def format_blackboard_output(boards: dict[str, Any]) -> str:
    """Format blackboard contents for human-readable output."""
    if not boards:
        return "No blackboard files found."

    lines = ["=== Blackboard HOT Tier ===", ""]
    for name, content in boards.items():
        lines.append(f"Board: {name}")
        if isinstance(content, dict) and "error" in content:
            lines.append(f"  Error: {content['error']}")
        else:
            # Show summary of content
            if isinstance(content, dict):
                lines.append(f"  Keys: {list(content.keys())}")
            elif isinstance(content, list):
                lines.append(f"  Items: {len(content)}")
            else:
                lines.append(f"  Type: {type(content).__name__}")
        lines.append("-" * 40)
    return "\n".join(lines)


def format_tasks_output(items: list[dict]) -> str:
    """Format task items for human-readable output."""
    if not items:
        return "No tasks found."

    lines = ["=== Task Graph ===", ""]
    for item in items:
        lines.append(f"ID: {item.get('id', 'unknown')}")
        lines.append(f"Session: {item.get('session_id', 'unknown')}")
        lines.append(f"Status: {item.get('status', 'unknown')}")
        lines.append(f"Created: {item.get('created_at', 'unknown')}")
        lines.append("-" * 40)
    return "\n".join(lines)


def format_outputs_output(items: list[dict]) -> str:
    """Format output files for human-readable output."""
    if not items:
        return "No agent output files found."

    lines = ["=== Agent Outputs ===", ""]
    for item in items:
        lines.append(f"Agent: {item.get('agent', 'unknown')}")
        lines.append(f"File: {item.get('file', 'unknown')}")
        lines.append(f"Path: {item.get('path', 'unknown')}")
        lines.append(f"Modified: {item.get('modified', 'unknown')}")
        size = item.get('size', 0)
        if size > 1024:
            lines.append(f"Size: {size / 1024:.1f} KB")
        else:
            lines.append(f"Size: {size} bytes")
        lines.append("-" * 40)
    return "\n".join(lines)


def format_all_output(result: dict[str, Any]) -> str:
    """Format combined observation for human-readable output."""
    lines = [
        "=" * 60,
        "AGENT OBSERVATION REPORT",
        f"Timestamp: {result['timestamp']}",
        f"Filters: query={result['filters']['query']}, session_id={result['filters']['session_id']}",
        "=" * 60,
        "",
        f"Memory Records: {result['memory']['count']}",
        f"Blackboard Boards: {result['blackboard']['count']}",
        f"Tasks: {result['tasks']['count']}",
        f"Output Files: {result['outputs']['count']}",
        "",
    ]

    if result['memory']['items']:
        lines.append(format_memory_output(result['memory']['items']))
        lines.append("")

    if result['blackboard']['boards']:
        lines.append(format_blackboard_output(result['blackboard']['boards']))
        lines.append("")

    if result['tasks']['items']:
        lines.append(format_tasks_output(result['tasks']['items']))
        lines.append("")

    if result['outputs']['items']:
        lines.append(format_outputs_output(result['outputs']['items']))

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(
        description="Observe running agents - query memory, blackboard, tasks, and outputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query memory for API-related content
  %(prog)s --what memory --query "API"

  # Read all blackboard files
  %(prog)s --what blackboard

  # List tasks for a specific session
  %(prog)s --what tasks --session-id abc123

  # Combined observation with JSON output
  %(prog)s --what all --json
        """
    )
    parser.add_argument(
        "--what",
        choices=["memory", "blackboard", "tasks", "outputs", "all"],
        required=True,
        help="What to observe: memory (PostgreSQL), blackboard (JSON files), tasks (SQLite), outputs (markdown files), or all"
    )
    parser.add_argument(
        "--query", "-q",
        help="Search query for memory content (uses ILIKE pattern matching)"
    )
    parser.add_argument(
        "--session-id", "-s",
        help="Filter by session ID (for memory and tasks)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (default: human-readable format)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit number of results (for memory queries, default: 20)"
    )

    args = parser.parse_args()

    if args.what == "memory":
        result = await query_memory(args.query, args.session_id, args.limit)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(format_memory_output(result))

    elif args.what == "blackboard":
        result = read_blackboard()
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(format_blackboard_output(result))

    elif args.what == "tasks":
        result = query_task_graph(args.session_id)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(format_tasks_output(result))

    elif args.what == "outputs":
        result = list_agent_outputs()
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(format_outputs_output(result))

    elif args.what == "all":
        result = await observe_all(args.query, args.session_id)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(format_all_output(result))


if __name__ == "__main__":
    asyncio.run(main())
