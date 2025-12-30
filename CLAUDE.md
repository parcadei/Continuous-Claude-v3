# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Session continuity, token-efficient MCP execution, and agentic workflows for Claude Code. Implements "clear, don't compact" - save state to ledger, wipe context, resume fresh.

## Commands

### Development
```bash
uv sync                                    # Install dependencies
uv run pytest                              # Run all tests
uv run pytest tests/unit/                  # Run unit tests only
uv run pytest tests/unit/test_mcp_client.py::test_tool_call  # Single test
uv run pytest -k "artifact"                # Tests matching pattern
uv run mypy src/                           # Type checking
```

### MCP Runtime
```bash
uv run mcp-generate                        # Generate Python wrappers from config
uv run mcp-discover                        # Generate Pydantic types from API responses
uv run mcp-exec scripts/<name>.py          # Run script with MCP context

# Example: Run script with arguments
uv run python -m runtime.harness scripts/morph_search.py --query "pattern" --path "."
```

### Code Quality
```bash
qlty check --fix                           # Lint and auto-fix
qlty fmt                                   # Format code
```

## Architecture

### Core Pattern: Scripts over Direct Execution
Scripts (`scripts/`) execute MCP tools with 99.6% token reduction vs loading full schemas. Always prefer scripts over direct tool calls.

```
User Request → Script (argparse CLI) → MCP Tool → Result
                    ↓
              runtime.harness (asyncio, cleanup, signal handlers)
                    ↓
              mcp_client.py (lazy connection, tool format: "server__tool")
```

### Continuity System
```
SessionStart Hook → Load ledger + handoff into context
       ↓
Working (PreToolUse validates, PostToolUse indexes)
       ↓
PreCompact → Auto-handoff to thoughts/shared/handoffs/
       ↓
/clear → Fresh context with ledger loaded
```

**Key files:**
- Ledgers: `thoughts/ledgers/CONTINUITY_CLAUDE-*.md`
- Handoffs: `thoughts/shared/handoffs/<session>/*.md`
- Artifact Index: `.claude/cache/artifact-index/context.db` (SQLite+FTS5)

### Runtime Core (`src/runtime/`)
- `mcp_client.py` - McpClientManager: lazy loading, singleton, tool format `"server__tool"`
- `harness.py` - Execution wrapper: asyncio, MCP init, signal handlers
- `generate_wrappers.py` - Generates `servers/<name>/<tool>.py` from MCP schemas

### Hooks (`.claude/hooks/`)
Shell wrappers calling bundled TypeScript. Pattern: `*.sh` → `node dist/*.mjs`
- `session-start-continuity.sh` - Loads ledger on resume/clear
- `pre-compact-continuity.sh` - Auto-generates handoff before compaction
- `typescript-preflight.sh` - Type-checks before Edit/Write on .ts files

### MCP Config
Checks `.mcp.json` first, then `mcp_config.json`. Use `${VAR}` placeholders for API keys from `.env`.

```json
{
  "mcpServers": {
    "name": {
      "type": "stdio|sse|http",
      "command": "...",
      "env": {"KEY": "${API_KEY}"}
    }
  }
}
```

## Key Scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `artifact_index.py` | Index handoffs/plans to SQLite |
| `artifact_query.py` | Search artifact database |
| `braintrust_analyze.py` | Session tracing analysis |
| `morph_search.py` | Fast code search (20x grep) |
| `ast_grep_find.py` | AST-based structural search |

## Testing

Tests use pytest-asyncio with `asyncio_mode = "auto"`. Integration tests require MCP servers configured.

```bash
# Run with verbose output
uv run pytest -v tests/unit/test_mcp_client.py

# Run integration tests (needs config)
uv run pytest tests/integration/
```
