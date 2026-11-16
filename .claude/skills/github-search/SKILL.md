---
name: github-search
description: Search GitHub code, repositories, issues, and PRs via MCP
allowed-tools: [Bash, Read]
---

# GitHub Search Skill

## When to Use

- Search code across repositories
- Find issues or PRs
- Look up repository information

## Instructions

```bash
uv run python -m runtime.harness scripts/github_search.py \
    --type "code" \
    --query "your search query"
```

### Parameters

- `--type`: Search type - `code`, `repos`, `issues`, `prs`
- `--query`: Search query (supports GitHub search syntax)
- `--owner`: (optional) Filter by repo owner
- `--repo`: (optional) Filter by repo name

### Examples

```bash
# Search code
uv run python -m runtime.harness scripts/github_search.py \
    --type "code" \
    --query "authentication language:python"

# Search issues
uv run python -m runtime.harness scripts/github_search.py \
    --type "issues" \
    --query "bug label:critical" \
    --owner "anthropics"
```

## MCP Server Required

Requires `github` server in mcp_config.json with GITHUB_PERSONAL_ACCESS_TOKEN.
