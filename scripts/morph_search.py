#!/usr/bin/env python3
"""Morph Codebase Search - Fast codebase search via WarpGrep.

Use Cases:
- Search codebase 20x faster than traditional grep
- Find code patterns, function definitions, usages
- Edit files programmatically

Usage:
  # Search for a pattern in codebase
  uv run python -m runtime.harness scripts/morph_search.py \
    --search "authentication" --path "."

  # Search with regex pattern
  uv run python -m runtime.harness scripts/morph_search.py \
    --search "def.*login" --path "./src"

  # Edit a file
  uv run python -m runtime.harness scripts/morph_search.py \
    --edit "/path/to/file.py" --content "new content"

Requires: morph server in mcp_config.json with MORPH_API_KEY
"""

import argparse
import asyncio
import json
import sys


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Codebase search via Morph/WarpGrep")

    # Search mode
    parser.add_argument("--search", help="Search query/pattern")
    parser.add_argument("--path", default=".", help="Directory to search (default: .)")

    # Edit mode
    parser.add_argument("--edit", help="File path to edit")
    parser.add_argument("--content", help="New content for file (use with --edit)")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    from runtime.mcp_client import call_mcp_tool

    args = parse_args()

    if args.edit:
        if not args.content:
            print("Error: --content required when using --edit")
            return

        print(f"Editing: {args.edit}")
        result = await call_mcp_tool("morph__edit_file", {
            "path": args.edit,
            "code_edit": args.content,
            "instruction": "Apply the provided edit"
        })
        print(f"✓ File edited")
        print(json.dumps(result, indent=2) if isinstance(result, dict) else result)

    elif args.search:
        print(f"Searching: {args.search} in {args.path}")
        result = await call_mcp_tool("morph__warpgrep_codebase_search", {
            "search_string": args.search,
            "repo_path": args.path
        })
        print(f"✓ Search complete")
        print(json.dumps(result, indent=2) if isinstance(result, dict) else result)

    else:
        print("Error: Either --search or --edit is required")
        print("\nExamples:")
        print("  --search 'authentication' --path './src'")
        print("  --edit '/path/to/file.py' --content 'new content'")


if __name__ == "__main__":
    asyncio.run(main())
