#!/usr/bin/env python3
"""
Qlty Code Quality Check via MCP.

USAGE:
    # Check changed files (default)
    uv run python -m runtime.harness scripts/qlty_check.py

    # Check all files
    uv run python -m runtime.harness scripts/qlty_check.py --all

    # Check with auto-fix
    uv run python -m runtime.harness scripts/qlty_check.py --fix

    # Check specific paths
    uv run python -m runtime.harness scripts/qlty_check.py --paths src/ tests/

    # Get metrics instead
    uv run python -m runtime.harness scripts/qlty_check.py --metrics

    # Find code smells
    uv run python -m runtime.harness scripts/qlty_check.py --smells

    # Initialize qlty in a repo
    uv run python -m runtime.harness scripts/qlty_check.py --init --cwd /path/to/repo
"""

import argparse
import asyncio
import json
import sys


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run qlty code quality checks via MCP")

    # Mode selection
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", default=True,
                      help="Run linters (default)")
    mode.add_argument("--metrics", action="store_true",
                      help="Calculate code metrics instead of linting")
    mode.add_argument("--smells", action="store_true",
                      help="Find code smells instead of linting")
    mode.add_argument("--fmt", action="store_true",
                      help="Format files instead of linting")
    mode.add_argument("--init", action="store_true",
                      help="Initialize qlty in repository")
    mode.add_argument("--plugins", action="store_true",
                      help="List available plugins")

    # Common options
    parser.add_argument("--all", action="store_true",
                        help="Process all files, not just changed")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix issues where possible (for --check)")
    parser.add_argument("--level", choices=["note", "low", "medium", "high"],
                        default="low", help="Minimum issue level (for --check)")
    parser.add_argument("--paths", nargs="+",
                        help="Specific files or directories to process")
    parser.add_argument("--cwd", help="Working directory (must have .qlty/qlty.toml)")
    parser.add_argument("--text", action="store_true",
                        help="Output as text instead of JSON")
    parser.add_argument("--sort", choices=["complexity", "duplication", "maintainability"],
                        help="Sort metrics by (for --metrics)")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


def filter_none(d: dict) -> dict:
    """Remove keys with None values from dict."""
    return {k: v for k, v in d.items() if v is not None}


async def main():
    from runtime.mcp_client import call_mcp_tool

    args = parse_args()
    json_output = not args.text

    if args.init:
        print("Initializing qlty...")
        result = await call_mcp_tool("qlty__qlty_init", filter_none({
            "yes": True,
            "cwd": args.cwd,
        }))
        print(result)
        return

    if args.plugins:
        print("Listing qlty plugins...")
        result = await call_mcp_tool("qlty__qlty_plugins_list", filter_none({
            "cwd": args.cwd,
        }))
        print(result)
        return

    if args.fmt:
        print("Formatting files...")
        result = await call_mcp_tool("qlty__qlty_fmt", filter_none({
            "all": args.all,
            "paths": args.paths or [],
            "cwd": args.cwd,
        }))
        print(result)
        return

    if args.metrics:
        print("Calculating metrics...")
        result = await call_mcp_tool("qlty__qlty_metrics", filter_none({
            "all": args.all,
            "paths": args.paths or [],
            "sort": args.sort,
            "json_output": json_output,
            "cwd": args.cwd,
        }))
        if json_output and isinstance(result, str):
            try:
                parsed = json.loads(result)
                print(json.dumps(parsed, indent=2))
            except json.JSONDecodeError:
                print(result)
        else:
            print(result)
        return

    if args.smells:
        print("Finding code smells...")
        result = await call_mcp_tool("qlty__qlty_smells", filter_none({
            "all": args.all,
            "paths": args.paths or [],
            "json_output": json_output,
            "cwd": args.cwd,
        }))
        if json_output and isinstance(result, str):
            try:
                parsed = json.loads(result)
                print(json.dumps(parsed, indent=2))
            except json.JSONDecodeError:
                print(result)
        else:
            print(result)
        return

    # Default: check
    mode_desc = "with auto-fix" if args.fix else "for issues"
    scope = "all files" if args.all else "changed files"
    print(f"Checking {scope} {mode_desc}...")

    result = await call_mcp_tool("qlty__qlty_check", filter_none({
        "all": args.all,
        "fix": args.fix,
        "level": args.level,
        "paths": args.paths or [],
        "json_output": json_output,
        "cwd": args.cwd,
    }))

    if json_output and isinstance(result, str):
        try:
            parsed = json.loads(result)
            issues = parsed.get("issues", [])
            print(f"\n{'='*60}")
            print(f"Found {len(issues)} issue(s)")
            print(f"{'='*60}")
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print(result)
    else:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
