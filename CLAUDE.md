# CLAUDE.md - Claude Code Operational Guide

**Terminology:**
- **Skills** = Claude Code native format (.claude/skills/ with SKILL.md) - Auto-discovered
- **Scripts** = CLI-based Python workflows (./scripts/) - Agent-agnostic

**Dual-Mode MCP pattern**: Reusable scripts (PREFERRED, 99.6% reduction) with CLI arguments, OR direct script writing (98.7% reduction) for novel tasks. Progressive disclosure via filesystem. Multi-transport support (stdio + SSE + HTTP).

## Execution Modes

### PRIMARY: Scripts-Based Execution (>2 tools, complex logic)

**When to use:**
- Multi-step research workflows
- Cross-validation needed
- Data processing pipelines
- Chaining multiple MCP servers
- 99.6% token reduction, 96% time reduction

**Pattern:**
1. `ls scripts/` - Discover available scripts
2. `cat scripts/{script}.py` - Read script docstring and CLI arguments
3. Execute with args (DO NOT edit file):
   ```bash
   # Example: Web scraping
   uv run python -m runtime.harness scripts/firecrawl_scrape.py \
       --url "https://example.com"

   # Example: Multi-tool pipeline
   uv run python -m runtime.harness scripts/multi_tool_pipeline.py \
       --repo-path "." \
       --max-commits 5
   ```

**Example Scripts:**

Reusable CLI workflows (./scripts/):
- `firecrawl_scrape.py` - Web scraping pattern (`--url`)
- `multi_tool_pipeline.py` - Multi-tool chaining pattern (`--repo-path`, `--max-commits`)

**Note:** These are **templates** - use as examples to create custom scripts for your specific MCP servers and use cases.

**Claude Code Users:** These scripts are also available as native Skills in `.claude/skills/` (SKILL.md format, auto-discovered).

### ALTERNATIVE: Direct Script Writing (1 tool, simple fetch)

**When to use:**
- Single tool call
- Straightforward data retrieval
- Novel workflows not covered by existing scripts
- Prototyping new patterns

**Pattern:** (existing documentation)
1. Explore `servers/` to discover tools
2. Write Python script using tool imports
3. Execute: `uv run python -m runtime.harness workspace/script.py`

## MCP Server Configuration

The runtime checks for config in this order:
1. `.mcp.json` (Claude Code project convention)
2. `mcp_config.json` (visible example, tracked in repo)

**Environment variables:** Add API keys to `.env` (copy from `.env.example`). The config uses `${VAR}` placeholders.

## Commands
- `uv run mcp-generate` - Gen Python wrappers from `.mcp.json` or `mcp_config.json`
- `uv run mcp-discover` - Gen Pydantic types from actual API responses (see `discovery_config.json`)
- `uv run mcp-exec <script.py>` - Run script w/ MCP
- `uv run mcp-exec <script> --args` - Run script with CLI arguments
- Example scripts: `workspace/example_progressive_disclosure.py`, `tests/integration/test_*.py`
- User scripts go in: `workspace/` (gitignored)

## Core Files
- `src/runtime/mcp_client.py` - `McpClientManager`: lazy loading, `initialize()` loads config only, `call_tool()` connects on-demand, tool format `"serverName__toolName"`, singleton via `get_mcp_client_manager()`
- `src/runtime/harness.py` - Exec harness: asyncio, MCP init, signal handlers, cleanup
- `src/runtime/generate_wrappers.py` - Auto-gen: connects all servers (stdio/SSE/HTTP), introspects schemas, generates `servers/<server>/<tool>.py` + `__init__.py`
- `src/runtime/discover_schemas.py` - Schema discovery: calls safe read-only tools, generates `servers/<server>/discovered_types.py` from real responses
- `src/runtime/normalize_fields.py` - Field normalization: auto-converts inconsistent API field casing (e.g., ADO: `system.parent` → `System.Parent`)

## Structure
`servers/` (gitignored, regen w/ `uv run mcp-generate`):
```
servers/<serverName>/<toolName>.py         # Pydantic models, async wrapper
servers/<serverName>/__init__.py           # Barrel exports
servers/<serverName>/discovered_types.py   # Optional: Pydantic types from actual API responses
```

`scripts/` (CLI-based parameter templates - edit logic freely):
```
scripts/<script_name>.py                    # Workflow with argparse, USAGE docstring
scripts/README.md                           # Scripts documentation
scripts/SCRIPTS.md                          # Complete framework guide
```

`mcp_config.json` format (multi-transport):
```json
{
  "mcpServers": {
    "name_stdio": {
      "type": "stdio",
      "command": "command",
      "args": ["arg1"],
      "env": {}
    },
    "name_sse": {
      "type": "sse",
      "url": "https://...",
      "headers": {"Authorization": "Bearer ..."}
    },
    "name_http": {
      "type": "http",
      "url": "https://...",
      "headers": {"x-api-key": "..."}
    }
  }
}
```

`discovery_config.json` format (optional, for schema discovery):
```json
{"servers": {"name": {"safeTools": {"tool_name": {"param1": "value"}}}}}
```

## Workflow

### Scripts-Based (PREFERRED)
1. Discover: `ls scripts/` → see available script templates
2. Read: `cat scripts/firecrawl_scrape.py` → see CLI arguments and USAGE
3. Execute: `uv run python -m runtime.harness scripts/firecrawl_scrape.py --url "https://example.com"`
4. Change parameters via CLI args - edit scripts freely to fix bugs or improve logic
5. Create your own scripts for your specific workflows using the template

### Script-Based (ALTERNATIVE)
1. Add server: edit `mcp_config.json` or `.mcp.json` → specify type (stdio/sse/http)
2. Generate wrappers: `uv run mcp-generate` → auto-detect transports
3. Import in script: `from servers.name import tool_name`
4. Execute: `uv run mcp-exec workspace/script.py` (auto-connect on first call)

Optional schema discovery: copy `discovery_config.example.json` → edit w/ safe read-only tools + real params → `uv run mcp-discover` → `from servers.name.discovered_types import ToolNameResult`

Script pattern (`workspace/` for user scripts, `tests/` for examples):
```python
from servers.name import tool_name
from servers.name.discovered_types import ToolNameResult  # optional

result = await tool_name(params)  # Pydantic model
# Use defensive coding: result.field or fallback
# Return data - LLM can process/summarize in follow-up interactions
# Not all processing needs to happen in-script
```

## Key Details
- **Scripts pattern** - Change parameters via CLI args, edit scripts freely to fix bugs or improve logic
- **Skills (Claude Code)** - Native SKILL.md format in .claude/skills/ (auto-discovered by Claude Code)
- Tool ID: `"serverName__toolName"` (double underscore)
- Progressive disclosure:
  - Scripts with CLI args: 110 tokens, 99.6% reduction (PREFERRED)
  - Writing scripts from scratch: 2K tokens, 98.7% reduction (ALTERNATIVE)
  - Claude Code Skills: Wrapper for script discovery (auto-discovered)
- Multi-transport: stdio (subprocess), SSE (events), HTTP (streamable)
- **Processing flexibility**: Scripts can return raw data for LLM to process, pre-process for efficiency, or reshape for chaining tool calls - choose based on use case
- Type gen: Pydantic models for all schemas, handles primitives, unions, nested objects, required/optional, docstrings
- Schema discovery: only use safe read-only tools (never mutations), types are hints (fields marked Optional), still use defensive coding
- Field normalization: auto-applied per server (e.g., ADO normalizes all fields to PascalCase for consistency)
- Python: asyncio for concurrency, Pydantic for validation, mypy for type safety

## Troubleshooting
- "No config file found": create `.mcp.json` or ensure `mcp_config.json` exists
- "MCP server not configured": check config file keys and ensure `.env` has required API keys
- "Connection closed": verify server command with `which <command>`
- Missing wrappers: `uv run mcp-generate`
- Import errors: ensure `src/` in sys.path (harness handles this)
- Type checking: `uv run mypy src/` for validation
- Script --help: `python scripts/{script}.py --help` shows CLI arguments

## Refs
- [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [MCP spec](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
