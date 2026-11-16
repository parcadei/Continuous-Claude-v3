#!/usr/bin/env python3
"""Morph Fast Apply - Apply code edits using AI-assisted diff application.

Use Cases:
- Apply targeted code changes without reading entire files
- Add features or fix bugs with minimal context
- Preview changes before applying (dry-run mode)
- 10,500+ tokens/sec edit speed with 98% accuracy

Usage:
  # Add error handling to a file
  uv run python -m runtime.harness scripts/morph_apply.py \
    --file "src/auth.ts" \
    --instruction "I will add null check for user" \
    --code_edit "// ... existing code ...
if (!user) throw new Error('User not found');
// ... existing code ..."

  # Refactor function with context markers
  uv run python -m runtime.harness scripts/morph_apply.py \
    --file "src/utils/logger.ts" \
    --instruction "I will add timestamp to log output" \
    --code_edit "function log(message: string) {
  const timestamp = new Date().toISOString();
  console.log(\`[\${timestamp}] \${message}\`);
  // ... existing code ...
}"

  # Preview changes without applying (dry-run)
  uv run python -m runtime.harness scripts/morph_apply.py \
    --file "src/config.ts" \
    --instruction "I will add new environment variable" \
    --code_edit "export const API_URL = process.env.API_URL || 'http://localhost';
export const NEW_FEATURE_FLAG = process.env.NEW_FEATURE === 'true';
// ... existing code ..." \
    --dry-run

  # Delete code (show context, omit deleted lines)
  uv run python -m runtime.harness scripts/morph_apply.py \
    --file "src/deprecated.ts" \
    --instruction "I will remove old authentication method" \
    --code_edit "// ... existing imports ...
// removed oldAuthMethod function
export function newAuthMethod() {
// ... existing code ..."

Important:
- Use '// ... existing code ...' to represent unchanged code blocks
- Include just enough context to locate edits precisely
- Preserve exact indentation of final code
- Add descriptive hints when helpful: '// ... keep auth logic ...'
- Batch multiple edits to same file in one call

Requires: morph server in mcp_config.json with MORPH_API_KEY
"""

import argparse
import asyncio
import json
import sys


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Apply code edits using Morph Fast Apply API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add error handling
  %(prog)s --file "src/auth.ts" \\
    --instruction "I will add null check" \\
    --code_edit "if (!user) throw new Error('Not found');"

  # Preview changes
  %(prog)s --file "src/auth.ts" \\
    --instruction "Add logging" \\
    --code_edit "console.log('User logged in');" \\
    --dry-run
        """
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Path to file to edit"
    )
    parser.add_argument(
        "--instruction",
        required=True,
        help="Brief first-person description of the change (e.g., 'I will add error handling')"
    )
    parser.add_argument(
        "--code_edit",
        required=True,
        help="Code with '// ... existing code ...' markers to represent unchanged sections"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )

    # Only filter out the script name, not file path arguments
    args_to_parse = sys.argv[1:]
    # Remove script path if passed by harness (first arg ending in .py that looks like a path)
    if args_to_parse and args_to_parse[0].endswith(".py") and "/" in args_to_parse[0]:
        args_to_parse = args_to_parse[1:]
    return parser.parse_args(args_to_parse)


async def main():
    from runtime.mcp_client import call_mcp_tool

    args = parse_args()

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Editing: {args.file}")
    print(f"Instruction: {args.instruction}")
    print()

    # Build parameters
    params = {
        "path": args.file,
        "code_edit": args.code_edit,
        "instruction": args.instruction
    }

    if args.dry_run:
        params["dryRun"] = True

    # Call Morph edit_file tool
    result = await call_mcp_tool("morph__edit_file", params)

    # Print result
    if args.dry_run:
        print("✓ Dry run complete - Changes previewed (not applied)")
    else:
        print("✓ File edited successfully")

    print()
    print(json.dumps(result, indent=2) if isinstance(result, dict) else result)


if __name__ == "__main__":
    asyncio.run(main())
