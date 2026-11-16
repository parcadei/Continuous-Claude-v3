# Architecture Evolution

**Document Version:** 1.0
**Last Updated:** 2025-12-27
**Branch:** feature/agentica-integration

---

## Executive Summary

This document traces the architectural evolution of Continuous Claude from a stateless CLI tool to a persistent multi-agent system with shared state. The journey represents four major versions:

1. **v1: Stateless Claude Code** - Baseline (context window only)
2. **v2: Continuity System** - File-based state preservation
3. **v3: Agentica Runtime** - Failed approaches to agent execution
4. **v4: Server + REPL Architecture** - Current working solution

**Key Pivot:** The shift from trying to run agents as external processes (v3) to embedding them in a persistent Python runtime with shared scope (v4).

---

## Version Timeline

```
v1 (Baseline)          v2 (Continuity)        v3 (Failed)           v4 (Current)
────────────────────   ──────────────────     ─────────────────     ──────────────────
Context Only           + Ledger/Hooks         + Direct Execution    + Claude Proxy
No Persistence         + Handoffs             ✗ Stateless           + REPL Server
Agent Task tool        + Artifact Index       ✗ MCP Bridge          + Shared Scope
                       + Session State        ✗ No State Sharing    + Memory Layer
                                                                    + PostgreSQL Backend
│                      │                      │                     │
├─ Claude Code CLI     ├─ Ledger Files        ├─ uv run script.py   ├─ FastAPI Proxy
├─ Agent as Task       ├─ SessionStart Hook   ├─ MCP server wrapper ├─ Persistent Process
└─ Compaction Lossy    ├─ PostToolUse Index   └─ Lost Python objs   ├─ shared_scope dict
                       └─ PreCompact Block                          ├─ Memory Protocol
                                                                     └─ RRF Search

2024 Q4                2025 Q1                2025-12-25             2025-12-26/27
```

---

## v1: Stateless Claude Code (Baseline)

### What It Was

Claude Code as a CLI tool with:
- Full context window for each conversation
- Agent Task tool for spawning sub-conversations
- No persistence beyond session lifetime
- Compaction when context fills up

### Architecture

```
┌─────────────────────────────────────────┐
│         Claude Code Session             │
├─────────────────────────────────────────┤
│                                         │
│  User Prompt → LLM → Tool Use          │
│      ↓          ↑        ↓              │
│  Context    Memory    Execute           │
│  (200K)     (None)    (Transient)       │
│                                         │
└─────────────────────────────────────────┘
           │
           ▼
    Context Full (>200K)
           │
           ▼
    ┌──────────────┐
    │  Compaction  │ ← Lossy summarization
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │ Lost Details │
    └──────────────┘
```

### Limitations

1. **Context Degradation** - Each compaction lost details
2. **No Memory** - Forgot everything on `/clear`
3. **Agent Isolation** - Task agents couldn't share state
4. **Single Session** - No continuity across days

### What Worked

- Fast iteration (no setup)
- Native tool access (Read, Write, Edit, Bash)
- Agent Task tool for complex work

---

## v2: Continuity System

### What We Added

File-based state preservation through:
- **Continuity Ledger** - Session state that survives `/clear`
- **Hooks System** - Lifecycle interception (SessionStart, PreCompact, PostToolUse)
- **Handoffs** - End-of-session transfer documents
- **Artifact Index** - SQLite FTS5 for searchable handoffs

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Claude Code Session                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   User Prompt → LLM → Tool Use → PostToolUse Hook           │
│        ↓         ↑       ↓            ↓                      │
│   Context    Ledger   Execute    Index Handoff              │
│   (Fresh)    (Loaded) (Tracked)  (SQLite FTS5)              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
         │                                │
         ▼                                ▼
  ┌─────────────┐                  ┌──────────────────┐
  │   /clear    │                  │  Create Handoff  │
  └─────────────┘                  └──────────────────┘
         │                                │
         ▼                                ▼
  ┌─────────────┐                  ┌──────────────────┐
  │SessionStart │                  │ thoughts/shared/ │
  │Load Ledger  │                  │  handoffs/*.md   │
  └─────────────┘                  └──────────────────┘
         │                                │
         └────────────────────────────────┘
                      │
                      ▼
            Fresh Context + State
```

### Key Insight

**File-based state survives compaction.**

Hooks intercept lifecycle events to:
- Load ledger at `SessionStart`
- Index handoffs at `PostToolUse` (Write)
- Block manual compaction at `PreCompact`
- Create auto-handoff before compaction

### Test Results

```bash
# SessionStart Hook
✓ Loads most recent ledger
✓ Surfaces unmarked handoffs
✓ Injects learnings (48h window)

# PostToolUse Hook
✓ Indexes handoffs immediately on Write
✓ Links to Braintrust trace IDs
✓ Enables fast FTS5 search

# PreCompact Hook
✓ Auto-handoff on compaction
✓ Blocks manual compact
✓ Prompts ledger update
```

### What Still Failed

**Agent state sharing** - Agents spawned via Task tool still couldn't share Python objects or maintain conversation history across turns.

```python
# v2 limitation
agent = Task(subagent_type="research", run_in_background=False)
# Agent runs → Creates handoff → Returns summary
# Next agent has NO access to previous agent's runtime state
```

---

## v3: Agentica Runtime (Failed Approaches)

### Timeline: December 25, 2025

**Goal:** Enable Python agents with persistent state and tool access.

### Attempt 1: Direct Script Execution

#### What We Tried

```bash
uv run python scripts/agentica/braintrust_agent.py
```

Run Agentica agents as standalone scripts, expecting Claude Code tools to "just work."

#### Architecture

```
┌──────────────────────┐
│   Claude Code CLI    │
│   Spawns Process     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  uv run script.py    │
│                      │
│  agent = spawn(...)  │
│  result = call(...)  │
│                      │
│  ✗ No Claude tools   │
│  ✗ Stateless         │
└──────────────────────┘
```

#### What Failed

1. **No Tool Access** - Scripts ran in isolated Python process
2. **Stateless** - Each execution started fresh
3. **Lost Scope** - Python objects didn't persist between runs

#### Why It Failed

```python
# This doesn't work:
agent = await spawn(premise="You are helpful")
result = await agent.call(str, "Read file.py")
# Agent has no access to Claude Code's Read tool
```

### Attempt 2: MCP Bridge Pattern

#### What We Tried

Wrap Claude Code tools as MCP server → Generate wrappers → Import in agents.

```
scripts/agentica/agent.py
    ↓ import
servers/claude_tools/read_file.py  ← Generated wrapper
    ↓ RPC
MCP Server (claude_tools)
    ↓ subprocess
claude -p "Read file.py"
```

#### Architecture

```
┌───────────────────────────────────────────────────┐
│              Agentica Agent Script                │
├───────────────────────────────────────────────────┤
│                                                   │
│  from servers.claude_tools import read_file      │
│                                                   │
│  agent = await spawn(                             │
│      premise="...",                               │
│      scope={"read_file": read_file}               │
│  )                                                │
│                                                   │
└─────────────────────┬─────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────┐
│            MCP Server (claude_tools)              │
├───────────────────────────────────────────────────┤
│                                                   │
│  async def read_file(path: str):                  │
│      result = subprocess.run(["claude", "-p", ...])│
│      return result.stdout                         │
│                                                   │
└───────────────────────────────────────────────────┘
```

#### What Failed

1. **Complex Plumbing** - MCP server → config → wrappers → imports
2. **Latency** - Each tool call spawned subprocess (500ms+ overhead)
3. **No State Sharing** - Each agent in separate process

#### Test Results

```bash
# Performance
Direct Claude Code: ~50ms/tool
MCP Bridge: ~550ms/tool (10x slower)

# State Sharing
Agent A sets context → Agent B has NO access
```

### Attempt 3: Agentica Server Wrapper

#### What We Tried

Build wrapper on official `agentica-server` to add:
- State persistence to `.claude/cache/agentica-state/`
- Braintrust logging
- Session management

#### Architecture

```
┌─────────────────────────────────────────┐
│       Custom Wrapper Service            │
│  ┌───────────────────────────┐          │
│  │  Session Management       │          │
│  │  State Persistence        │          │
│  │  Braintrust Integration   │          │
│  └────────────┬──────────────┘          │
│               ▼                          │
│  ┌───────────────────────────┐          │
│  │   agentica-server (Rust)  │          │
│  │   WebSocket + Sandbox     │          │
│  └───────────────────────────┘          │
└─────────────────────────────────────────┘
```

#### What Failed

**SDK Limitation Discovery:**

```python
# Cannot do this (deltas not injectable):
agent = restore_from_disk("agent_state.json")

# SDK only supports:
agent = await spawn(premise="...", scope={...})  # Fresh agent
```

1. **Deltas NOT Injectable** - Can't hydrate conversation history
2. **Scope NOT Serializable** - Can't persist callables across restarts
3. **WebSocket Ephemeral** - No reconnection to existing agents

#### Key Learning

> "Wrapper can only save metadata, not actual state"

---

## v4: Server + REPL Architecture (Current)

### Timeline: December 26-27, 2025

### The Breakthrough

**Stop trying to run agents externally. Embed them in a persistent process.**

### Solution Components

1. **Claude Proxy** - OpenAI-compatible endpoint routing to Claude CLI
2. **Persistent REPL Server** - Long-running Python process
3. **Shared Scope** - Dict persisting across agent calls
4. **Memory Layer** - SQLite/PostgreSQL backends with Protocol abstraction

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Your Python Script                                 │
│  (DependencySwarm, Hierarchical, Pipeline, Swarm patterns)                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ S_M_BASE_URL=http://localhost:2345
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Agentica Server (Rust WebSocket)                       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ INFERENCE_ENDPOINT_URL=http://localhost:8080
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Claude Proxy (FastAPI Server)                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  POST /v1/chat/completions (OpenAI-compatible)                       │   │
│  │  - Formats messages                                                  │   │
│  │  - Injects REPL_BASELINE system prompt                              │   │
│  │  - Returns SSE stream or JSON response                              │   │
│  └────────────────────────────────┬─────────────────────────────────────┘   │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │ subprocess
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Claude CLI (claude -p)                                 │
│  --allowedTools Read Write Edit Bash Grep Glob                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                          Claude API ($0 via subscription)
```

### Shared Scope Pattern

**The 10x Insight:**

```python
# scripts/agentica/claude_scope.py
def create_claude_scope() -> dict[str, Any]:
    """Create scope with Claude CLI functions."""
    file_cache: dict[str, ClaudeResult] = {}  # Closure over cache

    def read_file(path: str) -> dict[str, Any]:
        if path in file_cache:
            return {"content": file_cache[path].content, "cached": True}

        # Call Claude CLI subprocess
        response = _call_claude_cli(f"Read {path}", ["Read"])
        file_cache[path] = ClaudeResult(content=response)
        return {"content": response, "cached": False}

    def write_file(path: str, content: str) -> dict[str, Any]:
        _call_claude_cli(f"Write {content} to {path}", ["Write"])
        file_cache.pop(path, None)  # Invalidate cache
        return {"success": True}

    return {
        "read_file": read_file,
        "write_file": write_file,
        "edit_file": edit_file,
        "bash": bash,
        "grep": grep,
        "glob": glob,
    }

# Agent uses scope functions
agent = await spawn(
    premise="You are a coder",
    scope=create_claude_scope()
)

# Turn 1: Agent calls read_file() → subprocess → cached
# Turn 2: Agent references cached result (no subprocess!)
```

**Why this works:**

1. **Closure Captures State** - `file_cache` persists across calls
2. **RPC Pattern** - Scope function → subprocess → result
3. **Proxy Reference** - Agent stores lightweight ref, not serialized content
4. **Shared Across Agents** - Multiple agents can share same scope

### Memory Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MemoryService (Protocol)                     │
│  - Core Memory: Key-value for current facts                      │
│  - Archival Memory: FTS5/pgvector searchable storage            │
│  - Recall: Cross-source query combining both                    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────┐       ┌──────────────────────┐
│  MemoryServiceSQLite │       │  MemoryServicePG     │
│  • SQLite + FTS5     │       │  • PostgreSQL        │
│  • Quick start       │       │  • pgvector          │
│  • Single agent      │       │  • RRF search        │
│  • File-based        │       │  • Multi-agent       │
└──────────────────────┘       └──────────────────────┘
```

**Protocol-based abstraction:**

```python
# scripts/agentica/memory_protocol.py
class MemoryService(Protocol):
    async def set_core(self, key: str, value: str) -> None: ...
    async def get_core(self, key: str) -> str | None: ...
    async def store(self, content: str, metadata: dict) -> str: ...
    async def search(self, query: str, limit: int) -> list[ArchivalFact]: ...
    async def recall(self, query: str, limit: int) -> list[str]: ...

# Factory creates backend based on environment
memory = create_memory_service(
    session_id="abc123",
    backend="postgres"  # or "sqlite"
)
```

### Unified Scope Integration

**Memory + Tasks + Custom Tools:**

```python
# scripts/agentica/unified_scope.py
scope = create_unified_scope(
    session_id="research-session",
    backend="postgres",
    extra_scope={"web_search": search_fn}
)

agent = await spawn(
    premise="""You are a research assistant.

    Available functions:
    - remember(key, value): Store facts
    - recall(query): Retrieve facts
    - create_task(description): Create task
    - complete_task(task_id): Mark done
    - web_search(query): Search the web
    """,
    scope=scope
)
```

**Scope contents:**

```python
{
    # Memory functions
    "remember": closure over MemoryService.set_core,
    "recall": closure over MemoryService.recall,
    "search_memory": closure over MemoryService.search,
    "store_fact": closure over MemoryService.store,

    # Task functions
    "create_task": closure over BeadsTaskGraph.create,
    "complete_task": closure over BeadsTaskGraph.complete,
    "get_ready_tasks": closure over BeadsTaskGraph.get_ready,

    # Custom tools
    "web_search": search_fn,

    # Direct service access (advanced)
    "_memory_service": memory,
    "_task_graph": tasks,
}
```

### Multi-Agent Patterns

**12 implemented patterns:**

```python
# scripts/agentica/patterns.py
patterns = {
    "hierarchical": HierarchicalOrchestrator,
    "swarm": SwarmCoordinator,
    "pipeline": PipelineCoordinator,
    "generator_critic": GeneratorCriticCoordinator,
    "map_reduce": MapReduceCoordinator,
    "jury": JuryCoordinator,
    "adversarial": AdversarialCoordinator,
    "chain_of_responsibility": ChainOfResponsibilityCoordinator,
    "blackboard": BlackboardCoordinator,
    "circuit_breaker": CircuitBreakerCoordinator,
    "event_driven": EventDrivenCoordinator,
    "consensus": ConsensusCoordinator,
}
```

**Example - Hierarchical with Memory:**

```python
from scripts.agentica.patterns import HierarchicalOrchestrator
from scripts.agentica.unified_scope import create_unified_scope

async def main():
    scope = create_unified_scope(session_id="project-x")

    orchestrator = HierarchicalOrchestrator(scope=scope)

    result = await orchestrator.execute(
        task="Build authentication system",
        specialists=["architect", "implementer", "tester"]
    )

    # Specialists share memory via unified scope
    # Tasks tracked in BeadsTaskGraph
    # Results aggregated by orchestrator

asyncio.run(main())
```

---

## Key Pivot Points

### Decision 1: Clear, Don't Compact (v2)

**Before:**
```
Work → Context Full → Compact → Lost Details
```

**After:**
```
Work → Save Ledger → /clear → Fresh Context + State
```

**Why:** File-based state is lossless, compaction is lossy.

### Decision 2: Protocol Over ABC (v4)

**Before:**
```python
class MemoryBackend(ABC):
    @abstractmethod
    async def store(self): ...
```

**After:**
```python
class MemoryService(Protocol):
    async def store(self): ...  # Structural typing
```

**Why:** No inheritance required, easier testing, more flexible.

### Decision 3: Closure Over Classes (v4)

**Before:**
```python
class ReadFileTool:
    def __init__(self, cache):
        self.cache = cache

    def __call__(self, path):
        return self.cache.get(path)
```

**After:**
```python
def create_scope():
    cache = {}

    def read_file(path):
        return cache.get(path)

    return {"read_file": read_file}
```

**Why:** Simpler, serialization-friendly, scope pattern idiomatic.

### Decision 4: Subprocess Pattern (v4)

**Before:**
```
Agent → MCP Server → Subprocess → Claude CLI
```

**After:**
```
Agent → Scope Function → Subprocess → Claude CLI
```

**Why:** One fewer layer, same latency, simpler debugging.

### Decision 5: Instructions > Personas (v4)

**Research Finding:**

```python
# WEAK (verbose persona)
premise = "You are a world-renowned security expert with 20 years..."

# STRONG (clear instructions)
premise = """You are a security agent.

DO:
- Scan for SQL injection vulnerabilities
- Check authentication logic
- Validate input sanitization

DON'T:
- Modify production code
- Skip test coverage
- Assume inputs are safe
"""
```

**Source:** Letta research, mutation testing validation (4x effectiveness improvement).

---

## Test Coverage Evolution

### v2 (Continuity System)

```bash
tests/unit/test_continuity.py          # 8 tests
tests/unit/test_artifact_index.py      # 12 tests
tests/unit/test_hooks.py               # 6 tests
```

### v4 (Agentica Integration)

```bash
# Core Services
tests/unit/test_memory_service.py         # 27 tests (SQLite)
tests/unit/test_memory_service_pg.py      # 27 tests (PostgreSQL)
tests/unit/test_agent_scope.py            # 11 tests
tests/unit/test_claude_scope.py           # 15 tests

# Patterns
tests/unit/test_agentica_hierarchical.py  # 10 tests
tests/unit/test_agentica_swarm.py         # 8 tests
tests/unit/test_agentica_pipeline.py      # 7 tests
tests/unit/test_agentica_jury.py          # 6 tests
# ... (12 pattern test files)

# Bug Hunting
tests/unit/test_async_memory_races.py     # 12 tests
tests/unit/test_async_pool_bugs.py        # 15 tests
tests/unit/test_async_sqlite_bugs.py      # 13 tests
tests/unit/test_async_embedding_bugs.py   # 10 tests

# Integration
tests/integration/test_claude_scope_e2e.py  # 8 tests
tests/integration/test_memory_e2e.py        # 6 tests
tests/integration/test_postgres_setup.py    # 5 tests

Total: ~200 tests
```

---

## Performance Metrics

### Context Token Savings

```
v1 (Baseline): All state in context
- Multi-turn conversation: 50K+ tokens
- Context compaction at 200K
- Degradation after 3 compactions

v2 (Continuity): File-based state
- Ledger overhead: ~500 tokens (SessionStart)
- Handoff overhead: ~1K tokens (first load)
- 95% reduction in repeated context

v4 (Agentica): Shared scope + memory
- Scope overhead: ~200 tokens (function signatures)
- Memory overhead: 0 tokens (runtime only)
- 99%+ reduction vs embedding full state in prompts
```

### Agent Execution Speed

```
v3 (MCP Bridge):
- Tool call latency: ~550ms (subprocess overhead)
- Agent spawn: ~2s (process startup)

v4 (Shared Scope):
- Tool call latency: ~50ms (cached) / ~500ms (subprocess)
- Agent spawn: ~100ms (reuse persistent process)
- 5-10x faster for multi-turn conversations
```

### Memory Backend Performance

```
SQLite (MemoryServiceSQLite):
- Store: ~10ms
- Search (FTS5): ~20ms
- Recall: ~30ms

PostgreSQL (MemoryServicePG):
- Store: ~15ms (with embedding)
- Vector search (pgvector): ~50ms
- RRF search: ~80ms (hybrid BM25 + vector)
```

---

## Deployment Configurations

### Local Development (SQLite)

```bash
# .env
MEMORY_BACKEND=sqlite

# Auto-creates: .claude/cache/agentica-memory/memory.db
```

**Pros:**
- Zero setup
- File-based, portable
- Fast for single-agent workflows

**Cons:**
- No concurrent writes
- Limited vector search (FTS5 only)

### Production (PostgreSQL)

```bash
# .env
MEMORY_BACKEND=postgres
POSTGRES_URL=postgresql://user:pass@localhost:5432/db

# Migrations
uv run python scripts/migrate_sqlite_to_postgres.py
```

**Pros:**
- Concurrent multi-agent support
- pgvector for semantic search
- RRF (BM25 + vector) hybrid search
- Connection pooling (asyncpg)

**Cons:**
- Requires PostgreSQL server
- More complex setup

---

## Lessons Learned

### 1. State Location Matters

| Approach | State Lives In | Survives Restart? | Shareable? |
|----------|---------------|-------------------|------------|
| LLM Context | Prompt | No | No |
| File System | Disk | Yes | No (locked) |
| Python Runtime | Memory | No | Yes (shared scope) |
| Database | PostgreSQL | Yes | Yes (concurrent) |

**v4 combines all four:**
- LLM context for reasoning
- File system for ledgers/handoffs
- Python runtime for hot state (scope, cache)
- Database for searchable long-term memory

### 2. Progressive Disclosure Works

```
v1: All tools in context (20K tokens)
v2: Skills reference files (500 tokens)
v3: MCP wrapper scripts (2K tokens)
v4: Scope function signatures (200 tokens)
```

**99% token reduction** from v1 to v4.

### 3. Hydration is a Trap

**Don't try to serialize/deserialize agent state.**

```python
# This doesn't work (v3 mistake):
state = agent.serialize()
disk.write(state)
# Later...
agent = restore_from_disk(state)  # Deltas not injectable

# This works (v4 pattern):
scope = create_scope()  # Fresh scope
agent = spawn(premise="...", scope=scope)  # New agent
# State lives in scope (shared across agents)
```

### 4. Personas Are Overrated

**Research finding (mutation testing + Nia validation):**

```python
# Weak (1x effectiveness):
premise = "You are a world-renowned expert with decades of experience..."

# Strong (4x effectiveness):
premise = """
DO:
- Check for SQL injection
- Validate inputs
- Write tests

DON'T:
- Skip validation
- Trust user input
- Modify production
"""
```

**Instructions > Personas** for agent reliability.

### 5. Protocol > ABC for Backends

**Structural typing allows:**
- Duck typing (no inheritance)
- Easier testing (mock anything matching protocol)
- Gradual typing (can add fields without breaking)

```python
# Protocol
class MemoryService(Protocol):
    async def store(self): ...

# Implementation 1: SQLite
class MemoryServiceSQLite:
    async def store(self): ...  # Matches protocol

# Implementation 2: PostgreSQL
class MemoryServicePG:
    async def store(self): ...  # Matches protocol

# No inheritance required!
```

---

## Future Architecture Considerations

### Agent-to-Agent Handoff Protocol

**Current (v4):** Agents share scope, no direct communication.

**Future:** Structured handoff messages.

```python
class AgentHandoff(Protocol):
    async def handoff_to(self, agent_id: str, context: dict) -> None: ...
    async def receive_handoff(self, from_agent: str, context: dict) -> None: ...
```

### Memory Backfill from Braintrust

**Current (v4):** Manual memory updates.

**In Progress:** Auto-backfill from Braintrust traces.

```python
# scripts/agentica/memory_backfill.py
backfiller = MemoryBackfillService(
    memory=memory,
    span_processor=SpanProcessor()
)

# Extract decisions from traces → store in memory
await backfiller.backfill_from_session(session_id="abc123")
```

### Distributed Multi-Agent Systems

**Current (v4):** Single Python process.

**Future:** Distributed agents via message queue.

```
Agent 1 (Host A) → RabbitMQ → Agent 2 (Host B)
                  ↓
            Shared PostgreSQL
```

### Agent Observability Dashboard

**Current (v4):** Braintrust traces (external).

**Future:** Real-time agent dashboard.

```
┌─────────────────────────────────────────┐
│         Agent Activity Dashboard         │
├─────────────────────────────────────────┤
│  Active Agents: 12                      │
│  Memory Usage: 45MB                     │
│  Tasks Pending: 3                       │
│  Last Decision: 2s ago                  │
│                                         │
│  [Agent Tree View]                      │
│  [Memory Heat Map]                      │
│  [Task Dependency Graph]                │
└─────────────────────────────────────────┘
```

---

## Conclusion

The evolution from v1 to v4 represents a fundamental shift in architecture:

**v1 → v2:** File-based state preservation (lossless continuity)
**v2 → v3:** Failed attempts at external agent execution (learned what NOT to do)
**v3 → v4:** Persistent runtime with shared scope (breakthrough)

**The Core Insight:**

> "Stop trying to serialize agent state. Instead, give agents a shared scope that persists in a long-running process."

This architecture enables:
- **$0 LLM costs** (Claude CLI proxy)
- **Persistent state** (shared scope + memory layer)
- **Multi-agent coordination** (12 patterns)
- **PostgreSQL scalability** (concurrent multi-agent)
- **99% token reduction** (progressive disclosure)

**Current Status:** Production-ready with 200+ tests, 12 multi-agent patterns, and dual backend support (SQLite/PostgreSQL).

---

## References

### Key Files

```
# Architecture
docs/AGENTICA_INTEGRATION_JOURNEY.md   # Detailed journey
docs/memory-backend.md                 # Backend abstraction
docs/braintrust-memory-backfill.md     # Backfill design

# Core Implementation
scripts/agentica/claude_proxy.py       # OpenAI-compatible proxy
scripts/agentica/claude_scope.py       # Scope functions
scripts/agentica/unified_scope.py      # Memory + Tasks + Tools
scripts/agentica/memory_protocol.py    # Protocol definition
scripts/agentica/memory_service.py     # SQLite backend
scripts/agentica/memory_service_pg.py  # PostgreSQL backend
scripts/agentica/patterns.py           # 12 multi-agent patterns

# Tests
tests/unit/test_claude_scope.py        # Scope tests
tests/integration/test_claude_scope_e2e.py  # E2E tests
tests/unit/test_memory_service*.py     # Backend tests
```

### Related Documentation

- [README.md](../../README.md) - Project overview
- [CLAUDE.md](../../CLAUDE.md) - Operational guide
- [Continuity Ledger](../../thoughts/ledgers/CONTINUITY_CLAUDE-open-source-release.md) - Current session state
- [Agentica SDK Skill](../../.claude/skills/agentica-sdk/SKILL.md) - SDK reference

---

**Document Status:** Complete
**Next Update:** After PostgreSQL production deployment
