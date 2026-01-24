---
name: knowledge-tree
description: Query and update project knowledge tree for navigation
triggers: ["/knowledge-tree", "project structure", "where to add", "project goals"]
allowed-tools: [Bash, Read]
---

# Knowledge Tree

Navigate and query the project's knowledge tree - a persistent map of what the project is about, how it's structured, and what you're working on.

## When to Use

- Find where to add new code (`/knowledge-tree query "where to add API endpoint"`)
- Understand project structure (`/knowledge-tree structure`)
- Check current goals (`/knowledge-tree goals`)
- Describe the project (`/knowledge-tree describe`)
- Refresh the tree after major changes (`/knowledge-tree refresh`)

## Quick Reference

```bash
# Generate or update the knowledge tree
uv run python ~/.claude/scripts/core/core/knowledge_tree.py --project .

# Query the tree
uv run python ~/.claude/scripts/core/core/query_tree.py --project . --query "where to add tests"

# Show current goals
uv run python ~/.claude/scripts/core/core/query_tree.py --project . --goals

# Show project description
uv run python ~/.claude/scripts/core/core/query_tree.py --project . --describe

# Show structure
uv run python ~/.claude/scripts/core/core/query_tree.py --project . --structure

# JSON output for processing
uv run python ~/.claude/scripts/core/core/query_tree.py --project . --query "auth" --json
```

## Tree Location

- Tree file: `{project}/.claude/knowledge-tree.json`
- ROADMAP file: `{project}/ROADMAP.md` (goals source)

## Common Queries

| Query | Purpose |
|-------|---------|
| `where to add API endpoint` | Find route/controller locations |
| `where to add test` | Find test directories |
| `where to add component` | Find UI component locations |
| `how does auth work` | Find authentication component |
| `what is this project` | Get project description |
| `current goal` | Show current focus from ROADMAP |

## Daemon

The tree daemon continuously updates the knowledge tree when files change:

```bash
# Start daemon in background
uv run python ~/.claude/scripts/core/core/tree_daemon.py --project . --background

# Check daemon status
uv run python ~/.claude/scripts/core/core/tree_daemon.py --project . --status

# Stop daemon
uv run python ~/.claude/scripts/core/core/tree_daemon.py --project . --stop
```

## ROADMAP.md Format

The planning hook automatically maintains ROADMAP.md:

```markdown
# Project Roadmap

## Current Focus
**Feature name**
- Description of what's being worked on
- Started: 2026-01-24

## Completed
- [x] Previous feature (2026-01-20)

## Planned
- [ ] Next feature (high priority)

## Recent Planning Sessions
### 2026-01-24: Session title
- Decision made
- Approach chosen
```

## Tree Schema

```json
{
  "version": "1.0",
  "project": {
    "name": "project-name",
    "description": "What the project does",
    "type": "web-app|cli|library",
    "stack": ["typescript", "react"]
  },
  "structure": {
    "root": "/path/to/project",
    "directories": {
      "src/": { "purpose": "Source code", "key_files": [...] }
    }
  },
  "components": [
    { "name": "Auth", "type": "feature", "files": [...] }
  ],
  "navigation": {
    "common_tasks": { "add_api_endpoint": ["routes/", "controllers/"] },
    "entry_points": { "main": "src/index.ts" }
  },
  "goals": {
    "source": "ROADMAP.md",
    "current": { "title": "...", "description": "..." },
    "completed": [...],
    "planned": [...]
  }
}
```

## Workflow

1. **Initial setup**: Run `knowledge_tree.py --project .` to generate tree
2. **Start daemon**: Optionally run daemon for auto-updates
3. **Query as needed**: Use `query_tree.py` to find locations
4. **Goals sync**: Planning hook updates ROADMAP.md on plan acceptance

## Limitations

- Tree focuses on structure, not code semantics
- Daemon requires watchdog package (`pip install watchdog`)
- Goals extraction depends on ROADMAP.md format
