#!/usr/bin/env python3
"""
RepoPrompt Async Operations via tmux

USAGE:
    # Start context builder (async)
    uv run python -m runtime.harness scripts/repoprompt_async.py \
        --action start --task "understand the auth system"

    # Check if done
    uv run python -m runtime.harness scripts/repoprompt_async.py \
        --action status

    # Get result when done
    uv run python -m runtime.harness scripts/repoprompt_async.py \
        --action result

    # Run any rp-cli command async
    uv run python -m runtime.harness scripts/repoprompt_async.py \
        --action start --command "workspace switch MyProject && builder 'task'"

    # Switch workspace first, then build context
    uv run python -m runtime.harness scripts/repoprompt_async.py \
        --action start --workspace "mcp-code-execution" --task "explore MCP patterns"

    # Kill running session
    uv run python -m runtime.harness scripts/repoprompt_async.py \
        --action kill
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

SESSION_NAME = "rp-async"

# Use project-local cache dir (gitignored)
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
CACHE_DIR = Path(PROJECT_DIR) / ".claude" / "cache" / "rp"
OUTPUT_FILE = CACHE_DIR / "async_result.md"


def run_cmd(cmd: str) -> tuple[int, str]:
    """Run shell command and return exit code + output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def session_exists() -> bool:
    """Check if tmux session exists."""
    code, _ = run_cmd(f"tmux has-session -t {SESSION_NAME} 2>/dev/null")
    return code == 0


def start_async(command: str) -> None:
    """Start rp-cli command in tmux session."""
    if session_exists():
        print(f"Session '{SESSION_NAME}' already running. Kill it first with --action kill")
        sys.exit(1)

    # Ensure cache dir exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Clear previous output
    OUTPUT_FILE.unlink(missing_ok=True)

    # Start tmux session with command
    full_cmd = f'tmux new-session -d -s {SESSION_NAME} "{command} > {OUTPUT_FILE} 2>&1"'
    code, output = run_cmd(full_cmd)

    if code == 0:
        print(f"Started async operation in tmux session '{SESSION_NAME}'")
        print(f"Output will be saved to: {OUTPUT_FILE}")
        print(f"\nCheck status: --action status")
        print(f"Get result:   --action result")
    else:
        print(f"Failed to start: {output}")
        sys.exit(1)


def check_status() -> None:
    """Check if async operation is still running."""
    if session_exists():
        print("Status: RUNNING")
        print(f"Session: {SESSION_NAME}")

        # Show partial output if available
        if Path(OUTPUT_FILE).exists():
            content = Path(OUTPUT_FILE).read_text()
            lines = content.strip().split('\n')
            if lines and lines[0]:
                print(f"\nPartial output ({len(lines)} lines so far):")
                print('\n'.join(lines[:10]))
                if len(lines) > 10:
                    print(f"... ({len(lines) - 10} more lines)")
    else:
        print("Status: DONE (or not started)")
        if Path(OUTPUT_FILE).exists():
            print(f"Result available at: {OUTPUT_FILE}")
        else:
            print("No result file found. Run --action start first.")


def get_result(cleanup: bool = True) -> None:
    """Get result of completed async operation."""
    if session_exists():
        print("Operation still running. Wait for completion or use --action kill")
        sys.exit(1)

    if not Path(OUTPUT_FILE).exists():
        print("No result file found. Run --action start first.")
        sys.exit(1)

    content = Path(OUTPUT_FILE).read_text()
    print(content)

    # Cleanup after successful retrieval
    if cleanup:
        Path(OUTPUT_FILE).unlink(missing_ok=True)
        # Kill any zombie session just in case
        run_cmd(f"tmux kill-session -t {SESSION_NAME} 2>/dev/null")


def kill_session() -> None:
    """Kill running tmux session."""
    if session_exists():
        run_cmd(f"tmux kill-session -t {SESSION_NAME}")
        print(f"Killed session '{SESSION_NAME}'")
    else:
        print("No session running")


def main():
    parser = argparse.ArgumentParser(description="RepoPrompt async operations via tmux")
    parser.add_argument("--action", required=True,
                       choices=["start", "status", "result", "kill"],
                       help="Action to perform")
    parser.add_argument("--task", help="Task description for context_builder")
    parser.add_argument("--command", help="Raw rp-cli command to run")
    parser.add_argument("--workspace", help="Workspace to switch to before running")
    parser.add_argument("--timeout", type=int, default=300,
                       help="Max wait time in seconds for 'result' action (default: 300)")
    parser.add_argument("--no-cleanup", action="store_true",
                       help="Don't delete output file after reading result")

    args = parser.parse_args()

    if args.action == "start":
        if args.command:
            # Raw command mode
            cmd = f"rp-cli -e '{args.command}'"
        elif args.task:
            # Context builder mode
            if args.workspace:
                cmd = f"rp-cli -e 'workspace switch \"{args.workspace}\" && builder \"{args.task}\"'"
            else:
                cmd = f"rp-cli -e 'builder \"{args.task}\"'"
        else:
            print("Error: --task or --command required for start action")
            sys.exit(1)

        start_async(cmd)

    elif args.action == "status":
        check_status()

    elif args.action == "result":
        get_result(cleanup=not args.no_cleanup)

    elif args.action == "kill":
        kill_session()


if __name__ == "__main__":
    main()
