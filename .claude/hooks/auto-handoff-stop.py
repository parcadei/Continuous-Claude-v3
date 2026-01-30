#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Stop hook: Block when context is too high and suggest handoff.

Reads context percentage from the temp file written by status.py.
This ensures 1:1 match with status line display.
"""
import json
import os
import sys
import tempfile
from pathlib import Path


CONTEXT_THRESHOLD = 85   # Block at 85%+


def get_session_id(data: dict) -> str:
    """Get session ID from Claude Code input, matching status.py logic."""
    session_id = data.get("session_id", "")
    if session_id:
        return session_id[:8]  # First 8 chars for filename
    return os.environ.get("CLAUDE_SESSION_ID", str(os.getppid()))


def read_context_pct_from_file(data: dict) -> int | None:
    """Read context percentage from temp file written by status.py.

    Returns None if file doesn't exist or can't be read.
    """
    session_id = get_session_id(data)
    tmp_dir = Path(tempfile.gettempdir())
    tmp_file = tmp_dir / f"claude-context-pct-{session_id}.txt"

    try:
        if tmp_file.exists():
            return int(tmp_file.read_text().strip())
    except (ValueError, OSError):
        pass
    return None


def main():
    data = json.load(sys.stdin)

    # Avoid recursion if stop hook triggers itself
    if data.get('stop_hook_active'):
        print('{}')
        sys.exit(0)

    # Read from temp file (written by status.py) for consistency
    pct = read_context_pct_from_file(data)

    # If temp file unavailable, don't block (status line is source of truth)
    if pct is None:
        print('{}')
        sys.exit(0)

    if pct >= CONTEXT_THRESHOLD:
        print(json.dumps({
            "decision": "block",
            "reason": f"Context at {pct}%. Run: /create_handoff"
        }))
    else:
        print('{}')


if __name__ == "__main__":
    main()
