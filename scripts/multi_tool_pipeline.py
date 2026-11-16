"""
SKILL: Multi-Tool Pipeline

DESCRIPTION: Demonstrates chaining multiple MCP tools in a workflow with CLI arguments

WHEN TO USE:
- Multi-step workflows
- Tool orchestration
- As a template for complex skills

CLI ARGUMENTS:
    --repo-path    Path to git repository (default: ".")
    --max-commits  Maximum commits to analyze (default: 10)

USAGE:
    uv run python -m runtime.harness scripts/multi_tool_pipeline.py \
        --repo-path "." \
        --max-commits 5

REQUIREMENTS:
    MCP server with git capabilities (e.g., mcp-server-git)
"""

import argparse
import asyncio
import sys


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Multi-tool pipeline skill")
    parser.add_argument("--repo-path", default=".", help="Git repository path")
    parser.add_argument("--max-commits", type=int, default=10, help="Max commits to fetch")

    # Filter out script path from sys.argv (harness adds it)
    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    """Main skill workflow - demonstrates tool chaining."""
    from runtime.mcp_client import call_mcp_tool

    args = parse_args()

    print(f"Analyzing repository: {args.repo_path}")

    try:
        # Step 1: Get repository status
        print("\n[1/3] Getting repository status...")
        status = await call_mcp_tool(
            "git__git_status", {"repo_path": args.repo_path}
        )

        # Step 2: Get recent commits
        print(f"[2/3] Fetching last {args.max_commits} commits...")
        commits = await call_mcp_tool(
            "git__git_log", {"repo_path": args.repo_path, "max_count": args.max_commits}
        )

        # Step 3: Get current branch
        print("[3/3] Getting branch information...")
        branches = await call_mcp_tool(
            "git__git_branch", {"repo_path": args.repo_path, "branch_type": "current"}
        )

        # Process results
        result = {
            "status": status,
            "commits": commits,
            "branches": branches,
            "summary": {
                "repo_path": args.repo_path,
                "commits_fetched": args.max_commits,
            },
        }

        print("\n✓ Pipeline complete")
        return result

    except Exception as e:
        print(f"\n✗ Error in pipeline: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    asyncio.run(main())
