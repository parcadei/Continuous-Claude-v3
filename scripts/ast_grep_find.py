#!/usr/bin/env python3
"""AST-Grep Find via MCP - AST-based code search and refactoring.

Use Cases:
- Find code patterns that understand syntax (not just text)
- Refactor code across files with structural awareness
- Search for function calls, class definitions, imports, etc.

Usage:
  # Search for a pattern
  uv run python -m runtime.harness scripts/ast_grep_find.py \
    --pattern "console.log($$$)" --language javascript

  # Search in specific directory
  uv run python -m runtime.harness scripts/ast_grep_find.py \
    --pattern "async def $FUNC($$$)" --language python --path "./src"

  # Refactor/replace pattern
  uv run python -m runtime.harness scripts/ast_grep_find.py \
    --pattern "console.log($MSG)" --replace "logger.info($MSG)" \
    --language javascript

  # Dry run refactoring (preview changes)
  uv run python -m runtime.harness scripts/ast_grep_find.py \
    --pattern "print($X)" --replace "logger.info($X)" \
    --language python --dry-run

Pattern syntax:
  $NAME  - Match single node (variable, expression)
  $$$    - Match multiple nodes (arguments, statements)
  $_     - Match any single node (wildcard)

Supported languages: javascript, typescript, python, go, rust, java, c, cpp, etc.

Requires: ast-grep server in mcp_config.json
"""

import argparse
import asyncio
import json
import sys


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="AST code search via ast-grep MCP")
    parser.add_argument("--pattern", required=True, help="AST pattern to search")
    parser.add_argument("--language", default="python",
                        help="Language (javascript, typescript, python, go, etc.)")
    parser.add_argument("--path", default=".", help="Directory to search")
    parser.add_argument("--glob", help="File glob pattern (e.g., '**/*.py')")
    parser.add_argument("--replace", help="Replacement pattern for refactoring")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--context", type=int, default=2, help="Lines of context (default: 2)")
    parser.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    from runtime.mcp_client import call_mcp_tool

    args = parse_args()

    params = {
        "pattern": args.pattern,
        "path": args.path,
        "language": args.language,
        "context": args.context
    }

    if args.glob:
        params["glob"] = args.glob

    if args.replace:
        params["replacement"] = args.replace
        params["dry_run"] = args.dry_run
        mode = "Refactoring (dry-run)" if args.dry_run else "Refactoring"
        print(f"{mode}: {args.pattern} -> {args.replace}")
    else:
        print(f"Searching: {args.pattern} (language: {args.language})")

    result = await call_mcp_tool("ast-grep__ast_grep", params)

    print(f"\n✓ Complete\n")

    if isinstance(result, str):
        # ast-grep returns plain text output
        if result.strip():
            lines = result.strip().split('\n')
            for i, line in enumerate(lines[:args.limit], 1):
                print(f"{i}. {line}")
        else:
            print("No matches found")
    elif isinstance(result, dict):
        # Pretty print matches if dict format
        if "matches" in result:
            for i, match in enumerate(result["matches"][:args.limit], 1):
                file_path = match.get("file", match.get("path", "unknown"))
                line_num = match.get("line", match.get("start_line", "?"))
                text = match.get("text", match.get("matched", ""))
                print(f"{i}. {file_path}:{line_num}")
                if text:
                    print(f"   {text[:200]}")
        else:
            print(json.dumps(result, indent=2))
    else:
        print(result if result else "No matches found")


if __name__ == "__main__":
    asyncio.run(main())
