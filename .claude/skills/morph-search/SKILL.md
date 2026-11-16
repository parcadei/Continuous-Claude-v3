---
name: morph-search
description: Fast codebase search via WarpGrep (20x faster than grep)
allowed-tools: [Bash, Read]
---

# Morph Codebase Search

Fast, AI-powered codebase search using WarpGrep. 20x faster than traditional grep.

## When to Use

- Search codebase for patterns, function names, variables
- Find code across large codebases quickly
- Edit files programmatically

## Usage

### Search for code patterns
```bash
uv run python -m runtime.harness scripts/morph_search.py \
    --search "authentication" --path "."
```

### Search with regex
```bash
uv run python -m runtime.harness scripts/morph_search.py \
    --search "def.*login" --path "./src"
```

### Edit a file
```bash
uv run python -m runtime.harness scripts/morph_search.py \
    --edit "/path/to/file.py" --content "new content"
```

## Parameters

| Parameter | Description |
|-----------|-------------|
| `--search` | Search query/pattern |
| `--path` | Directory to search (default: `.`) |
| `--edit` | File path to edit |
| `--content` | New content for file (use with `--edit`) |

## Examples

```bash
# Find all async functions
uv run python -m runtime.harness scripts/morph_search.py \
    --search "async def" --path "./src"

# Search for imports
uv run python -m runtime.harness scripts/morph_search.py \
    --search "from fastapi import" --path "."
```

## vs ast-grep

| Tool | Best For |
|------|----------|
| **morph/warpgrep** | Fast text/regex search (20x faster) |
| **ast-grep** | Structural code search (understands syntax) |

## MCP Server Required

Requires `morph` server in mcp_config.json with `MORPH_API_KEY`.
