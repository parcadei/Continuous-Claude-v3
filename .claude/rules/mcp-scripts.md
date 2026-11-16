---
globs: ["scripts/**/*.py"]
---

# MCP Script Rules

When working with files in `scripts/`:

## DO
- Use CLI arguments for all parameters (argparse)
- Include USAGE docstring at top of file
- Use `call_mcp_tool("server__tool", params)` pattern
- Handle errors gracefully with informative messages
- Print results to stdout for Claude to process

## DON'T
- Hardcode parameters in the script
- Edit scripts to change parameters (use CLI args instead)
- Import from servers/ directly (use runtime.mcp_client)

## Tool Naming
Tool IDs use double underscore: `serverName__toolName`

Examples:
- `morph__warpgrep_codebase_search`
- `ast-grep__ast_grep`
- `perplexity__perplexity_ask`

## Testing
Test with: `uv run python -m runtime.harness scripts/<script>.py --help`
