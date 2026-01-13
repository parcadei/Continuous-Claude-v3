# CLAUDE.md

This is the **OPC (Open Protocol Claude)** v3 project - a continuity kit for multi-agent Claude sessions with MCP (Model Context Protocol) execution support.

## Quick Start

```bash
# Run the setup wizard (recommended first step)
cd opc && uv run python -m scripts.setup.wizard

# Start Docker services (PostgreSQL + Redis + PgBouncer)
cd opc && docker compose up -d

# Run a script with MCP tools available
cd opc && uv run python -m runtime.harness /path/to/script.py

# Search past learnings
cd opc && uv run python scripts/core/recall_learnings.py --query "hooks patterns"

# Store a new learning
cd opc && uv run python scripts/core/store_learning.py --session-id "session123" \
    --type WORKING_SOLUTION --content "Hook pattern works well" \
    --context "hook development" --tags "hooks,patterns" --confidence high
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        OPC v3 Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │   Harness   │───>│  MCP Client     │───>│ MCP Servers     │  │
│  │  (entry)    │    │  Manager        │    │ (stdio/sse/http)│  │
│  └─────────────┘    └─────────────────┘    └─────────────────┘  │
│         │                   │                      │             │
│         v                   v                      v             │
│  ┌─────────────┐    ┌─────────────────┐                          │
│  │  Scripts    │    │  Memory System  │    ┌─────────────────┐  │
│  │  (runtime/) │    │  (postgresql+   │    │  Coordination   │  │
│  │             │    │   pgvector)     │───>│  (agents,       │  │
│  │             │    │                 │    │   blackboard)   │  │
│  └─────────────┘    └─────────────────┘    └─────────────────┘  │
│                            │                                    │
│                            v                                    │
│                     ┌─────────────┐                             │
│                     │   Redis     │                             │
│                     │ (hot cache) │                             │
│                     └─────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

## Key Modules

### Runtime (`opc/src/runtime/`)

| File | Purpose |
|------|---------|
| `harness.py` | Main entry point - executes scripts with MCP tools |
| `mcp_client.py` | MCP client manager - connects to servers, caches tools |
| `config.py` | Pydantic models for MCP server configuration |

### Scripts (`opc/scripts/core/`)

| File | Purpose |
|------|---------|
| `recall_learnings.py` | Semantic search over past session learnings |
| `store_learning.py` | Store new learnings with embeddings |
| `db/embedding_service.py` | Generate embeddings (local or Voyage) |
| `db/postgres_pool.py` | PostgreSQL connection pooling |
| `db/memory_factory.py` | Memory backend abstraction |

### Setup (`opc/scripts/setup/`)

| File | Purpose |
|------|---------|
| `wizard.py` | Interactive setup - prereqs, DB, API keys |

## MCP Execution Flow

1. **Entry**: `cd opc && python -m runtime.harness <script.py>`
2. **Init**: Load `.env`, parse args, validate script exists
3. **MCP Connect**: Initialize `McpClientManager`, connect to servers from config
4. **Execute**: `runpy.run_path()` injects MCP tools into script's namespace
5. **Cleanup**: Close all MCP connections on exit

### MCP Transport Types

```python
# stdio (process-based)
{"type": "stdio", "command": "python", "args": ["-m", "server"]}

# SSE (Server-Sent Events)
{"type": "sse", "url": "http://localhost:8080/sse", "headers": {"Auth": "Bearer ..."}}

# Streamable HTTP
{"type": "http", "url": "http://localhost:8080/mcp", "headers": {...}}
```

## Memory & Continuity System

### Storage Backends

| Backend | Use When |
|---------|----------|
| **PostgreSQL + pgvector** | Production - semantic search, cross-session |
| **SQLite FTS5** | Development - no DB required |

### Key Tables

```sql
-- Session learnings (semantic search with embeddings)
CREATE TABLE archival_memory (
    id UUID PRIMARY KEY,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1024),  -- Qwen3-Embedding-0.6B (1024 dim)
    metadata JSONB,
    created_at TIMESTAMPTZ
);

-- Agent tracking for multi-agent sessions
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT UNIQUE NOT NULL,
    parent_agent_id UUID REFERENCES agents(id),
    status TEXT DEFAULT 'running',
    ...
);

-- Inter-agent messaging (blackboard pattern)
CREATE TABLE blackboard (
    id UUID PRIMARY KEY,
    swarm_id TEXT NOT NULL,
    sender_agent TEXT NOT NULL,
    message_type TEXT CHECK (message_type IN ('request', 'response', 'status', 'directive', 'checkpoint')),
    payload JSONB NOT NULL,
    ...
);
```

### Learning Storage

```bash
# Store with type, context, tags
cd opc && uv run python scripts/core/store_learning.py \
    --session-id "session123" \
    --type WORKING_SOLUTION \
    --content "Hook pattern X works for Y" \
    --context "hook development" \
    --tags "hooks,patterns" \
    --confidence high
```

### Learning Recall

```bash
# Semantic search (hybrid RRF + optional reranking)
cd opc && uv run python scripts/core/recall_learnings.py --query "authentication patterns"

# Text-only (fast, no embeddings)
cd opc && uv run python scripts/core/recall_learnings.py --query "hooks" --text-only

# Vector-only with recency boost
cd opc && uv run python scripts/core/recall_learnings.py --query "hooks" --vector-only --recency 0.3
```

## Docker Services

```bash
cd opc && docker compose up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5432 | Primary database (coordination, memory) |
| PgBouncer | 6432 | Connection pooling |
| Redis | 6379 | Hot cache, blackboard pub/sub |

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://opc:opc_dev_password@localhost:5432/opc

# Embeddings (optional)
VOYAGE_API_KEY=...

# Memory backend (auto-detected from DATABASE_URL)
AGENTICA_MEMORY_BACKEND=postgres  # or sqlite
```

## Development Commands

```bash
# Install dependencies (run from opc directory)
cd opc && uv sync

# Run a script with MCP tools
cd opc && uv run python -m runtime.harness /path/to/script.py

# Search memories
cd opc && PYTHONPATH=. uv run python scripts/core/recall_learnings.py -q "pattern"

# Store a learning
cd opc && PYTHONPATH=. uv run python scripts/core/store_learning.py --session-id "test" --type CODEBASE_PATTERN --content "..." --context "..."

# Run tests
cd opc && uv run pytest

# Type checking
cd opc && uv run pyright opc/src/runtime/

# Linting
cd opc && uv run ruff check opc/src/runtime/
```

## Testing Patterns

Tests are in `tests/` with integration and unit tests:

```bash
# Run all tests
cd opc && uv run pytest

# Run specific test file
cd opc && uv run pytest tests/test_database.py

# Run a single test
cd opc && uv run pytest tests/test_database.py::TestDatabase::test_connection

# Run with verbose output
cd opc && uv run pytest -v
```

## Key Configuration Files

| File | Purpose |
|------|---------|
| `opc/pyproject.toml` | Python dependencies, scripts, and tools (mypy, ruff, pytest) |
| `opc/init-db.sql` | PostgreSQL schema for sessions, file_claims, archival_memory, handoffs |
| `opc/docker-compose.yml` | PostgreSQL (5432), PgBouncer (6432), Redis (6379) |

## Settings Safety Rule

**CRITICAL:** Never commit `~/.claude/settings.json` to git.

### Why This Matters

The `settings.json` file contains sensitive configuration:
- API keys and tokens for MCP servers
- Authentication credentials
- Environment-specific settings

### Template vs User Settings

| File | Contains | Safe to Commit? |
|------|----------|-----------------|
| `~/.claude/settings.json` | User's actual API keys, tokens, secrets | **NEVER** |
| `settings.json.bak` | Template (hooks only, no secrets) | **YES** |

### How Updates Work

When running the updater (`cd opc && uv run python -m scripts.setup.update`):

1. Reads `settings.json.bak` (template - hooks only, no secrets)
2. Merges it into the user's existing `~/.claude/settings.json`
3. Preserves user-specific fields:
   - `env` - user's environment variables
   - `attribution` - user's attribution settings
   - `mcpServers` - user's MCP server configurations
   - Any user-added customizations

This ensures users get hook updates without losing their secrets, MCP servers, or environment settings.

### Git Ignore Protection

The project's `.gitignore` should already include:
```
~/.claude/settings.json
.claude/settings.json
```

If you see settings.json in git status, remove it and verify `.gitignore` coverage.

## File Organization

```
opc/
├── src/
│   └── runtime/          # Core execution engine
│       ├── harness.py    # Entry point
│       ├── mcp_client.py # MCP connection management
│       ├── config.py     # Configuration models
│       └── ...
├── scripts/
│   ├── core/            # Memory/continuity scripts
│   │   ├── recall_learnings.py
│   │   ├── store_learning.py
│   │   └── db/
│   │       ├── embedding_service.py
│   │       ├── postgres_pool.py
│   │       └── memory_factory.py
│   └── setup/
│       └── wizard.py    # Setup wizard
├── tests/               # Integration and unit tests
├── pyproject.toml       # Dependencies
└── docker-compose.yml   # PostgreSQL + Redis + PgBouncer
```

## Key Dependencies

- **mcp**: Model Context Protocol SDK
- **pydantic**: Configuration validation
- **pgvector**: Vector similarity search (optional, for production semantic search)
- **redis**: Hot cache, pub/sub
- **aiofiles**: Async file I/O
- **rich**: Terminal output formatting (optional, for enhanced CLI output)

## TLDR-Code: Token-Efficient Code Analysis

The project includes **tldr-code** (llm-tldr) for token-efficient code analysis with **95% token savings** vs raw file reads.

### Installation (Automatic)

TLDR-Code is automatically installed when running:
```bash
cd opc && uv run python -m scripts.setup.update  # Full update
```

This installs llm-tldr and attempts to create a symlink at `/usr/local/bin/tldr` pointing to `~/.venv/bin/tldr`, making it available in Claude Code's subprocess PATH.

### Manual Installation (if symlink fails)

```bash
# Install the package
uv pip install llm-tldr

# Create the symlink (requires sudo)
sudo ln -sf ~/.venv/bin/tldr /usr/local/bin/tldr

# Or run the setup script
bash opc/scripts/setup/install_tldr_code.sh
```

### Usage in Claude Code

```bash
# File tree
tldr tree src/

# Code structure (functions, classes, imports)
tldr structure . --lang python

# Reverse call graph (who calls a function)
tldr impact function_name .

# LLM-ready context (follows call graph)
tldr context main --project . --depth 2

# Control flow graph
tldr cfg src/file.py function_name

# Data flow graph
tldr dfg src/file.py function_name

# Find dead code
tldr dead src/

# Detect architecture layers
tldr arch src/

# Type check + lint
tldr diagnostics src/

# Find affected tests
tldr change-impact --git
```

### The 5-Layer Stack

```
Layer 1: AST         ~500 tokens   Function signatures, imports
Layer 2: Call Graph  +440 tokens   What calls what (cross-file)
Layer 3: CFG         +110 tokens   Complexity, branches, loops
Layer 4: DFG         +130 tokens   Variable definitions/uses
Layer 5: PDG         +150 tokens   Dependencies, slicing
───────────────────────────────────────────────────────────────
Total:              ~1,200 tokens  vs 23,000 raw = 95% savings
```

### Verification & Testing

Verify tldr-code is working:
```bash
# Check package is installed
uv pip show llm-tldr

# Verify symlink exists
ls -la /usr/local/bin/tldr

# Test it's the correct binary
tldr --help | grep "Token-efficient"

# Test code analysis works
tldr structure . --lang python | head -20
```

Run installation tests:
```bash
cd opc && uv run pytest tests/test_tldr_installation.py -v
```

Troubleshooting:
- If symlink fails: `sudo ln -sf ~/.venv/bin/tldr /usr/local/bin/tldr`
- If wrong tldr: Ensure `uv pip install llm-tldr` not `tldr` (man-page)

## Common Issues

### MCP Connection Failures

```bash
# Check server config in mcp_servers.json
# Ensure command/args are valid for stdio transport
```

### Memory Search Returns Nothing

```bash
# Verify PostgreSQL is running
docker ps | grep postgres

# Check DATABASE_URL is set
echo $DATABASE_URL
```

### Import Errors

```bash
# Ensure PYTHONPATH includes project root
cd opc && PYTHONPATH=. uv run python scripts/core/recall_learnings.py ...
```
