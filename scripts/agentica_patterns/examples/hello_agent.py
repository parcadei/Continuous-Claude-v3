#!/usr/bin/env python3
"""Simple hello agent to test subprocess monitoring.

USAGE:
    # Terminal 1: Watch subprocesses
    uv run python scripts/agentica/watch_agents.py --monitor --watch

    # Terminal 2: Run this agent
    uv run python scripts/agentica/examples/hello_agent.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))

from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.tracked_agent import tracked_spawn


async def main():
    """Run a simple hello agent."""
    db = CoordinationDB()
    print(f"Session: {db.session_id}")

    agent = await tracked_spawn(
        db=db,
        premise="You are a friendly agent that says hello.",
        model="anthropic:claude-sonnet-4-20250514",
        pattern="hello_test",
    )

    result = await agent.call(str, "Say hello and tell me the current time.")
    print(f"Agent response: {result}")

    summary = db.get_session_summary()
    print(f"Agents spawned: {sum(summary['agents_by_status'].values())}")


if __name__ == "__main__":
    asyncio.run(main())
