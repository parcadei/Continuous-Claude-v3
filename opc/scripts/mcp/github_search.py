#!/usr/bin/env python3
"""GitHub Search via MCP - Search code, repos, issues, PRs."""

import argparse
import asyncio
import json
import sys


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Search GitHub via MCP")
    parser.add_argument(
        "--type", choices=["code", "repos", "issues", "prs"], default="code", help="Search type"
    )
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--owner", help="Repository owner filter")
    parser.add_argument("--repo", help="Repository name filter")
    parser.add_argument("--limit", type=int, default=10, help="Max results")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    from runtime.mcp_client import call_mcp_tool

    args = parse_args()

    print(f"Searching GitHub {args.type}: {args.query}")

    # Map type to GitHub MCP tool
    tool_map = {
        "code": "github__search_code",
        "repos": "github__search_repositories",
        "issues": "github__search_issues",
        "prs": "github__search_pull_requests",
    }

    tool_name = tool_map[args.type]
    params = {"q": args.query, "perPage": args.limit}

    if args.owner:
        params["owner"] = args.owner
    if args.repo:
        params["repo"] = args.repo

    result = await call_mcp_tool(tool_name, params)

    print("✓ Found results")
    print(json.dumps(result, indent=2) if isinstance(result, dict) else result)


if __name__ == "__main__":
    asyncio.run(main())
