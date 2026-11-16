# Agentica Infrastructure Documentation

## Overview

Agentica is a multi-agent orchestration framework that enables spawning, coordinating, and tracking multiple AI agents working together on complex tasks. It provides:

1. **Claude Proxy Server** - An OpenAI-compatible API that routes LLM calls through Claude Code CLI
2. **Scope System** - Provides agents with file operations, memory, and task management capabilities
3. **Native REPL** - A harness for executing agents with Claude Code as the underlying engine
4. **Coordination Database** - SQLite-backed tracking for multi-agent observability
5. **Multi-Agent Patterns** - Support for hierarchical, swarm, pipeline, and other orchestration patterns

The core problem Agentica solves is **coordinating multiple AI agents** to work on complex tasks that benefit from parallelization, specialization, or different perspectives. Rather than having a single agent tackle everything sequentially, Agentica enables patterns like:

- Research swarms that explore a topic from multiple angles simultaneously
- Hierarchical teams with coordinators delegating to specialists
- Generator-critic loops for iterative refinement
- Jury voting for high-stakes decisions

---

## Architecture

### High-Level Component Diagram

```
+-------------------+     +--------------------+     +------------------+
|   User/Client     |     |   Claude Proxy     |     |  Claude Code CLI |
|   (OpenAI API)    | --> |   (FastAPI)        | --> |  (Subprocess)    |
+-------------------+     +--------------------+     +------------------+
                                   |
                                   v
                          +------------------+
                          |   Scope System   |
                          | - File Ops       |
                          | - Memory         |
                          | - Tasks          |
                          +------------------+
                                   |
                                   v
                          +------------------+
                          | Coordination DB  |
                          |   (SQLite)       |
                          +------------------+
```

### Key Files

| File | Purpose |
|------|---------|
| `scripts/agentica/claude_proxy.py` | OpenAI-compatible API server routing through Claude CLI |
| `scripts/agentica/claude_scope.py` | File operation scope functions for agents |
| `scripts/agentica/unified_scope.py` | Combined scope: files + memory + tasks |
| `scripts/agentica/native_repl/run_claude.py` | Async wrapper for Claude Code CLI subprocess |
| `scripts/agentica/native_repl/coordinator.py` | Research coordinator orchestrating multi-agent workflows |
| `scripts/agentica/native_repl/tools.py` | Tool wrappers for research operations |
| `scripts/agentica/coordination.py` | SQLite database for agent tracking |
| `scripts/agentica/tracked_agent.py` | Agent wrapper with automatic observability |
| `scripts/agentica/memory_service.py` | Core + Archival memory with FTS5 search |

---

## Claude Proxy

The Claude Proxy (`scripts/agentica/claude_proxy.py`) provides an **OpenAI-compatible API** that routes requests through the Claude Code CLI instead of direct API calls. This enables:

- Using Claude Code's native tools (Read, Write, Edit, Bash) through an API
- Streaming responses via Server-Sent Events (SSE)
- Integration with frameworks expecting OpenAI-style endpoints

### Starting the Server

```bash
# Start with defaults (localhost:8080)
uv run python scripts/agentica/claude_proxy.py

# Custom host/port
uv run python scripts/agentica/claude_proxy.py --host 0.0.0.0 --port 9000
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/v1/chat/completions` | OpenAI-compatible chat completions |

### Example Request

```bash
# Non-streaming
curl -X POST http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "claude-3-5-sonnet", "messages": [{"role": "user", "content": "Hello"}]}'

# Streaming (SSE)
curl -X POST http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "claude-3-5-sonnet", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

### REPL Baseline System Prompt

The proxy injects a comprehensive system prompt that instructs agents to use specific scope functions:

```python
REPL_BASELINE = """
You are an implementation agent running in Claude Code CLI with Python REPL.

## AVAILABLE SCOPE FUNCTIONS (USE THESE!)

You have these Python functions available in your scope. Call them directly:

```python
# Read a file - returns dict with 'success', 'content', 'path'
result = read_file("/path/to/file.txt")

# Write a file - returns dict with 'success', 'path'
result = write_file("/path/to/file.txt", "file content here")

# Edit a file (find and replace) - returns dict with 'success', 'path'
result = edit_file("/path/to/file.txt", "old text", "new text")

# Run bash command - returns dict with 'success', 'output', 'command'
result = bash("ls -la")

# Search for pattern - returns dict with 'success', 'matches'
result = grep("pattern", "/path/to/search")

# Find files by glob - returns dict with 'success', 'files'
result = glob("**/*.py")
```
...
"""
```

### How Requests are Processed

1. System messages are extracted and combined with the REPL baseline
2. User/assistant messages are formatted as a prompt
3. The prompt is sent to `claude -p` subprocess with allowed tools
4. Response is returned in OpenAI-compatible format

```python
async def call_claude_cli(prompt: str, system_prompt: str) -> str:
    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--append-system-prompt", system_prompt,
            "--allowedTools", "Read", "Write", "Edit", "Bash",
        ],
        capture_output=True,
        text=True,
        timeout=900,  # 15 minute timeout per task
    )
    return result.stdout.strip()
```

---

## Native REPL

The Native REPL (`scripts/agentica/native_repl/`) provides an async wrapper for Claude Code CLI that agents can use to execute tasks.

### Architecture

```
Agentica Agent --> REPL --> run_claude() --> subprocess --> Claude Code CLI
```

### Key Function: `run_claude()`

Located in `scripts/agentica/native_repl/run_claude.py`:

```python
async def run_claude(
    task: str,
    tools: list[str] | None = None,
    max_turns: int = 0,  # 0 = unlimited turns
    system_prompt: str | None = None,
    model: str | None = None,
    timeout: int = 1800,  # 30 min timeout
    modular: bool = False,  # Inject MODULAR_SYSTEM_PROMPT
    validate: bool = False,  # Run qlty check --fix after
) -> dict[str, Any]:
    """Execute Claude Code CLI and return parsed result."""
```

### Usage Example

```python
from scripts.agentica.native_repl.run_claude import run_claude

# Basic task
result = await run_claude(
    task="Read pyproject.toml and extract the project name",
    tools=["Read"],
    max_turns=3
)

# Modular implementation with validation
result = await run_claude(
    task="Implement user authentication",
    modular=True,
    validate=True,
    max_turns=15
)
```

### Convenience Wrappers

The module provides high-level wrappers for common operations:

```python
# Read a file
content = await read_file("pyproject.toml")

# Write a file
await write_file("hello.py", "print('hello world')")

# Edit a file
await edit_file("config.py", "DEBUG = True", "DEBUG = False")

# Run bash command
output = await run_bash("git status")

# Search codebase
results = await search_codebase("def run_claude", "scripts/")
```

### Research Tools

The `tools.py` module provides specialized research functions:

```python
from scripts.agentica.native_repl.tools import (
    web_research,
    codebase_research,
    docs_research,
    comprehensive_research,
    get_tool_scope,
)

# Web research
results = await web_research("Python async patterns 2025")

# Codebase analysis
results = await codebase_research("async spawn patterns", "scripts/")

# Documentation fetch
docs = await docs_research("https://docs.python.org/3/library/asyncio.html", "gather")

# Comprehensive multi-tool research
findings = await comprehensive_research("MCP server patterns", depth="deep")

# Get all tools as scope dict for agent spawning
scope = get_tool_scope()
```

---

## Scope System

The scope system provides agents with callable functions for file operations, memory, and task management. Two main scope factories exist:

### 1. Claude Scope (`claude_scope.py`)

Provides file operations via Claude CLI:

```python
from scripts.agentica.claude_scope import create_claude_scope

scope = create_claude_scope(
    cache_reads=True,       # Cache file reads
    project_dir="/my/project"  # Required for path validation
)

# Available functions:
scope["read_file"]("path/to/file.py")
scope["write_file"]("path/to/file.py", "content")
scope["edit_file"]("path/to/file.py", "old", "new")
scope["bash"]("ls -la")
scope["grep"]("pattern", "/search/path")
scope["glob"]("**/*.py")

# Swarm coordination functions:
scope["broadcast_finding"]("Found important insight", metadata={})
scope["broadcast_blocker"]("Stuck on dependency issue")
scope["broadcast_done"]("Completed analysis", artifacts={})
```

### 2. Unified Scope (`unified_scope.py`)

Combines file ops + memory + tasks:

```python
from scripts.agentica.unified_scope import create_unified_scope

scope = create_unified_scope(
    session_id="abc123",
    db_path=Path("/tmp/test.db"),  # Optional
    enable_memory=True,
    enable_tasks=True,
    project_dir="/my/project",
)

# File operations (same as claude_scope)
scope["read_file"]("path/to/file.py")
scope["write_file"]("path/to/file.py", "content")

# Memory operations
scope["remember"]("key", "value")      # Store in core memory
scope["recall"]("query")               # Query all memory sources
scope["search_memory"]("query")        # FTS5 search archival memory
scope["store_fact"]("Important fact")  # Store in archival memory

# Task operations
scope["create_task"]("Build the API", blocks=["design"])
scope["complete_task"](task_id)
scope["get_ready_tasks"]()             # Tasks with no pending blockers
scope["get_all_tasks"]()
```

### SharedContext for Multi-Agent Coordination

When multiple agents need to share file cache and operation logs:

```python
from scripts.agentica.claude_scope import SharedContext, create_claude_scope_with_shared

shared = SharedContext()

# Create scopes for multiple agents sharing same context
scope_a = create_claude_scope_with_shared(shared, project_dir="/project")
scope_b = create_claude_scope_with_shared(shared, project_dir="/project")

# Agent A reads a file
scope_a["read_file"]("config.py")

# Agent B gets cached result (no duplicate CLI call)
scope_b["read_file"]("config.py")  # Returns cached content
```

### Path Security

The scope system includes path validation to prevent directory traversal attacks:

```python
def _canonicalize_path(path: str, project_dir: str | None = None) -> str:
    """Canonicalize path and validate it's within allowed scope."""
    resolved = os.path.realpath(os.path.expanduser(path))

    if project_dir:
        allowed = os.path.realpath(os.path.expanduser(project_dir))
        if not resolved.startswith(allowed + os.sep):
            raise ValueError(f"Path '{path}' escapes project directory")

    return resolved
```

---

## Memory Service

The memory service (`scripts/agentica/memory_service.py`) implements a Letta/MemGPT-inspired memory architecture:

### Memory Types

| Type | Description | Storage |
|------|-------------|---------|
| **Core Memory** | Key-value pairs for current session facts | SQLite table |
| **Archival Memory** | Long-term searchable storage with FTS5 | SQLite + FTS5 virtual table |
| **Recall Memory** | Cross-source query combining all sources | Query interface |

### Usage

```python
from scripts.agentica.memory_service import MemoryService

memory = MemoryService(session_id="abc123")
await memory.connect()

# Core memory (in-context key-value)
await memory.set_core("persona", "You are a helpful assistant")
await memory.set_core("task", "Build a REST API")
value = await memory.get_core("persona")

# Archival memory (searchable long-term)
mem_id = await memory.store("User prefers Python over JavaScript")
await memory.store("Project uses PostgreSQL database")

# Search archival with FTS5
results = await memory.search("database", limit=10)

# Recall (cross-source query)
result = await memory.recall("What database does the project use?")

# Generate context for prompt injection
context = await memory.to_context()

await memory.close()
```

### FTS5 Search

The archival memory uses SQLite FTS5 for full-text search with BM25 ranking:

```python
async def search(self, query: str, limit: int = 10) -> list[dict]:
    """Search archival memory with FTS5 and BM25 ranking."""
    fts_query = self._prepare_fts_query(query)  # Converts to OR-joined terms

    cursor = await conn.execute("""
        SELECT a.*, bm25(archival_fts) as rank
        FROM archival_memory a
        JOIN archival_fts f ON a.rowid = f.rowid
        WHERE a.session_id = ? AND archival_fts MATCH ?
        ORDER BY rank LIMIT ?
    """, (self.session_id, fts_query, limit))
```

---

## Coordination Database

The coordination database (`scripts/agentica/coordination.py`) provides SQLite-backed tracking for multi-agent observability.

### Schema

```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    premise TEXT,
    model TEXT,
    scope_keys TEXT,  -- JSON array
    pattern TEXT,     -- swarm, hierarchical, jury, etc.
    parent_agent_id TEXT,
    spawned_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',  -- running, completed, failed
    error_message TEXT
);

CREATE TABLE completed_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    pattern TEXT,
    input_summary TEXT,
    output_summary TEXT,
    output_type TEXT,
    artifacts TEXT,  -- JSON dict
    duration_ms INTEGER,
    completed_at TEXT NOT NULL
);

CREATE TABLE broadcasts (
    id TEXT PRIMARY KEY,
    swarm_id TEXT NOT NULL,
    sender_agent TEXT NOT NULL,
    broadcast_type TEXT NOT NULL,  -- finding, question, blocker, done, abort
    payload TEXT NOT NULL,  -- JSON
    created_at TEXT NOT NULL
);
```

### Usage

```python
from scripts.agentica.coordination import CoordinationDB

db = CoordinationDB(session_id="my-session")

# Register an agent
agent_record = db.register_agent(
    agent_id="agent-123",
    premise="You are a code analyst",
    pattern="swarm",
)

# Record a completed task
task_record = db.record_task(
    agent_id="agent-123",
    input_text="Analyze the authentication module",
    output="Found 3 security issues...",
    duration_ms=5000,
    artifacts={"issues": ["issue1", "issue2"]},
)

# Mark agent as completed
db.complete_agent(agent_id="agent-123", status="completed")

# Query running agents
running = db.get_running_agents(pattern="swarm")

# Get session summary
summary = db.get_session_summary()
```

### Broadcast Types

For swarm coordination, agents can broadcast messages:

```python
from scripts.agentica.coordination import BroadcastType

class BroadcastType(str, Enum):
    FINDING = "finding"      # Discovered something useful
    QUESTION = "question"    # Asking other agents
    BLOCKER = "blocker"      # Stuck, need help
    DONE = "done"            # Agent completed its work
    ABORT = "abort"          # Critical failure, abort swarm
```

---

## Tracked Agents

The `TrackedAgent` wrapper (`scripts/agentica/tracked_agent.py`) automatically tracks agent lifecycle:

```python
from scripts.agentica.tracked_agent import tracked_spawn

# Drop-in replacement for agentica.spawn()
agent = await tracked_spawn(
    db=coordination_db,
    premise="You are a code analyst",
    pattern="hierarchical",
    scope=my_scope,
)

# Calls are automatically tracked with timing
result = await agent.call(str, "Analyze this code")

# Completion is tracked when agent closes
await agent.close()
```

### What Gets Tracked

- Agent registration at spawn time
- Task completion with duration and output
- Agent completion/failure status
- Artifacts produced during execution

---

## Multi-Agent Patterns

Agentica supports multiple orchestration patterns (see `scripts/agentica/PATTERNS.md`):

### Hierarchical (Coordinator --> Specialists --> Grunts)

```python
# Coordinator spawns specialists for different areas
coordinator = await tracked_spawn(db=db, pattern="hierarchical", ...)
specialist_a = await tracked_spawn(db=db, pattern="hierarchical", parent_agent_id=coordinator.agent_id, ...)
```

### Swarm (Parallel Attack)

```python
# Multiple agents research from different angles simultaneously
agents = await asyncio.gather(*[
    tracked_spawn(db=db, pattern="swarm", premise=f"Research angle: {angle}")
    for angle in ["web", "codebase", "docs"]
])
```

### Research Coordinator Example

The `ResearchCoordinator` class demonstrates hierarchical multi-agent research:

```python
from scripts.agentica.native_repl.coordinator import ResearchCoordinator

coordinator = ResearchCoordinator(
    topic="Python async patterns",
    depth="deep",
    max_sections=5,
)

# Execute full research workflow
document = await coordinator.research()
print(document.to_markdown())
```

The workflow:
1. **Decompose**: Break topic into research sections
2. **Research sections**: Parallel specialist agents investigate each section
3. **Synthesize**: Combine findings into final document

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_PROJECT_DIR` | Project root directory | Current working directory |

### Database Paths

By default, databases are created under:
```
{CLAUDE_PROJECT_DIR}/.claude/cache/agentica-coordination/coordination.db
{CLAUDE_PROJECT_DIR}/.claude/cache/agentica-memory/memory.db
```

### Custom Database Paths

```python
# Coordination DB
db = CoordinationDB(db_path=Path("/custom/path/coordination.db"))

# Memory Service
memory = MemoryService(session_id="abc", db_path=Path("/custom/path/memory.db"))

# Unified Scope
scope = create_unified_scope(session_id="abc", db_path=Path("/custom/path"))
```

---

## Code Examples

### Basic Agent Spawning with Tracking

```python
import asyncio
from scripts.agentica.coordination import CoordinationDB
from scripts.agentica.tracked_agent import tracked_spawn
from scripts.agentica.unified_scope import create_unified_scope

async def main():
    # Initialize coordination database
    db = CoordinationDB(session_id="example-session")

    # Create unified scope with all capabilities
    scope = create_unified_scope(
        session_id="example-session",
        enable_memory=True,
        enable_tasks=True,
        project_dir="/path/to/project",
    )

    # Spawn tracked agent
    agent = await tracked_spawn(
        db=db,
        premise="You are a Python code analyst",
        pattern="solo",
        scope=scope,
    )

    # Execute task
    result = await agent.call(str, "Analyze the auth module and list security concerns")
    print(f"Result: {result}")

    # Close agent (marks as completed in DB)
    await agent.close()

    # View session summary
    summary = db.get_session_summary()
    print(f"Session summary: {summary}")

asyncio.run(main())
```

### Multi-Agent Research Swarm

```python
import asyncio
from scripts.agentica.native_repl.tools import get_tool_scope
from scripts.agentica.tracked_agent import tracked_spawn
from scripts.agentica.coordination import CoordinationDB

async def research_swarm(topic: str, angles: list[str]):
    db = CoordinationDB(session_id="research-swarm")
    base_scope = get_tool_scope()

    async def research_angle(angle: str):
        scope = dict(base_scope)
        scope["results"] = {}  # Mutable for scope persistence

        agent = await tracked_spawn(
            db=db,
            premise=f"Research {topic} from {angle} perspective",
            pattern="swarm",
            scope=scope,
        )

        await agent.call(str, f"""
            Research '{topic}' focusing on {angle}.
            Store findings in results['findings'] as a dict.
        """)

        await agent.close()
        return scope.get("results", {}).get("findings", {})

    # Run all angles in parallel
    findings = await asyncio.gather(*[
        research_angle(angle) for angle in angles
    ])

    return findings

# Usage
results = asyncio.run(research_swarm(
    topic="MCP server patterns",
    angles=["web", "codebase", "docs"]
))
```

### Using Claude Proxy with External Client

```python
import httpx

async def query_claude_proxy():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8080/v1/chat/completions",
            json={
                "model": "claude-proxy",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Read pyproject.toml and summarize it"}
                ],
                "stream": False
            }
        )
        return response.json()
```

---

## Testing

### Running Tests

```bash
# Unit tests
uv run pytest tests/unit/test_claude_scope.py -v
uv run pytest tests/unit/test_unified_scope.py -v
uv run pytest tests/unit/test_coordination.py -v

# Integration tests (require Claude CLI)
uv run pytest tests/integration/test_agentica_server_integration.py -v
```

### Mocking Claude CLI

For testing without actual Claude CLI:

```python
from unittest.mock import patch

def test_read_file():
    with patch('scripts.agentica.unified_scope._call_claude_cli') as mock:
        mock.return_value = "file contents here"

        scope = create_unified_scope(session_id="test")
        result = scope["read_file"]("/path/to/file.py")

        assert result["success"] is True
        assert result["content"] == "file contents here"
```

---

## Troubleshooting

### Claude CLI Not Found

```
FileNotFoundError: Claude Code CLI not found in PATH
```

**Solution**: Install Claude Code CLI from https://code.claude.com/download

### Path Escapes Project Directory

```
ValueError: Path '/etc/passwd' resolves to '/etc/passwd' which escapes project directory
```

**Solution**: Ensure you're accessing files within the configured `project_dir`

### Database Locked

```
sqlite3.OperationalError: database is locked
```

**Solution**: The coordination database uses new connections per operation for thread safety. If you see this, check for long-running transactions or increase timeout.

### Agent Not Tracking

If agents aren't appearing in the coordination database:

1. Check that you're using `tracked_spawn()` instead of `spawn()`
2. Verify the `db` parameter is passed
3. Confirm the database path is writable

---

## Further Reading

- [PATTERNS.md](../../scripts/agentica/PATTERNS.md) - Multi-agent orchestration patterns
- [Native REPL RESEARCH.md](../../scripts/agentica/native_repl/RESEARCH.md) - Architecture decisions
- [Memory Backend Documentation](../memory-backend.md) - Detailed memory service docs
