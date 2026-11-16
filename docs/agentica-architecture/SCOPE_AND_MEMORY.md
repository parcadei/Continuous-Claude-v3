# Agentica Scope and Memory Architecture

## Quick Answer

**Q: How do Agentica agents access scope and memory?**

**A:** Scope is passed explicitly to `spawn()`. Agents get whatever you give them. Patterns are primitives that accept scope and distribute it to child agents.

```python
scope = {
    "run_claude": run_claude,
    "read_file": read_file,
    "remember": memory.store,
    "recall": memory.query,
}

pattern = Hierarchical(coordinator_scope=scope, specialist_scope=scope)
await pattern.execute("Do complex task")
# All agents have full scope access
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AGENTICA + CLAUDE PROXY STACK                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Your Python Code                                                       │
│       │                                                                  │
│       │ spawn(premise="...", scope={...})                               │
│       ▼                                                                  │
│   Agentica Server (Rust, WASM sandbox)                                  │
│       │                                                                  │
│       │ INFERENCE_ENDPOINT_URL=http://localhost:8080                    │
│       ▼                                                                  │
│   Claude Proxy (FastAPI)  ◀── scripts/agentica/claude_proxy.py          │
│       │                       Exposes Claude CLI as OpenAI API          │
│       │                                                                  │
│       │ subprocess.run(["claude", "-p", ...])                           │
│       ▼                                                                  │
│   Claude CLI               ◀── Has Read, Write, Edit, Bash, Task        │
│       │                       This is the agent's "brain"               │
│       ▼                                                                  │
│   Claude API ($0 via subscription)                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## How Agents Access Tools

Agents run in a WASM sandbox. They write Python code that calls **scope functions**:

```python
# Agent writes this code in WASM sandbox:
content = await read_file("pyproject.toml")
await remember("config", content)
```

This triggers RPC calls to your Python runtime, which executes the scope functions.

### Scope Functions → Claude CLI Tools

| Scope Function | Implementation | Claude Tool Used |
|----------------|----------------|------------------|
| `read_file(path)` | `run_claude(..., tools=["Read"])` | Read |
| `write_file(path, content)` | `run_claude(..., tools=["Write"])` | Write |
| `run_bash(cmd)` | `run_claude(..., tools=["Bash"])` | Bash |
| `run_claude(task, tools)` | Direct subprocess | Any specified |
| `remember(key, value)` | `memory.store(session_id, k, v)` | N/A (direct DB) |
| `recall(query)` | `memory.query(session_id, q)` | N/A (direct DB) |

---

## Patterns as Primitives

Patterns (hierarchical, swarm, pipeline, etc.) are **primitives that accept scope**:

```python
class Hierarchical:
    def __init__(
        self,
        coordinator_premise: str,
        coordinator_scope: dict = None,  # ← You pass this
        specialist_scope: dict = None,   # ← And this
        ...
    ):
        self.coordinator_scope = coordinator_scope
        self.specialist_scope = specialist_scope
```

When the pattern spawns agents, it passes your scope:

```python
async def _ensure_coordinator(self):
    spawn_kwargs = {"premise": self.coordinator_premise}
    if self.coordinator_scope:
        spawn_kwargs["scope"] = self.coordinator_scope  # ← Your scope
    self.coordinator = await spawn(**spawn_kwargs)
```

### This Makes Patterns Extendable

You can give agents **any capabilities** by passing them in scope:

```python
# Minimal scope (file ops only)
minimal_scope = {
    "read_file": read_file,
}

# Full scope (files + memory + custom tools)
full_scope = {
    "run_claude": run_claude,
    "read_file": read_file,
    "write_file": write_file,
    "run_bash": run_bash,
    "remember": memory.store,
    "recall": memory.query,
    "search_memory": memory.search,
    "create_task": task_graph.create,
    "my_custom_tool": my_function,
}

# Different agents can get different capabilities
pattern = Hierarchical(
    coordinator_scope=full_scope,    # Coordinator gets everything
    specialist_scope=minimal_scope,  # Specialists get read-only
)
```

---

## Memory Sharing

### Via session_id

Agents share memory when they use the same `session_id`:

```python
# Create memory service with session_id
memory = MemoryService(session_id="task-123", db_path="/tmp/agents.db")

# Create scope with memory functions
scope = {
    "remember": lambda k, v: memory.store(k, v),
    "recall": lambda q: memory.query(q),
}

# All agents using this scope share the same memory
coordinator = await spawn(premise="Coordinate", scope=scope)
specialist_a = await spawn(premise="Research", scope=scope)
specialist_b = await spawn(premise="Analyze", scope=scope)

# Agent A stores:
await remember("finding", "important data")

# Agent B can recall:
result = await recall("finding")  # Returns "important data"
```

### Memory Isolation

Different `session_id` = isolated memory:

```python
memory_team_a = MemoryService(session_id="team-a")
memory_team_b = MemoryService(session_id="team-b")

# Team A and Team B have separate memory spaces
```

---

## Three-Layer Memory Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MEMORY LAYERS (when PostgreSQL is live)             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Layer 1: Core Memory (SQLite/PostgreSQL)                              │
│   ├── remember(key, value) - Key-value storage                          │
│   └── recall(key) - Direct retrieval                                    │
│                                                                          │
│   Layer 2: Archival Memory (PGVector)                                   │
│   ├── store_fact(content) - Embedding + storage                         │
│   └── search_memory(query) - Semantic search                            │
│                                                                          │
│   Layer 3: Unified Recall                                               │
│   └── recall(query) - Searches both layers, ranks results               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Current status:**
- SQLite backend: Working
- PostgreSQL backend: Code exists, not deployed
- PGVector: Code exists, not deployed

---

## What's Missing (To Wire Memory)

### Current State

```python
# run_claude.py provides these scope functions:
scope = {
    "run_claude": run_claude,
    "read_file": read_file,
    "write_file": write_file,
    "run_bash": run_bash,
}
# No memory functions!
```

### What Needs to Happen

```python
# Add memory to scope:
from scripts.agentica.memory_service import MemoryService

def create_full_scope(session_id: str):
    memory = MemoryService(session_id=session_id)

    return {
        # File operations (existing)
        "run_claude": run_claude,
        "read_file": read_file,
        "write_file": write_file,
        "run_bash": run_bash,

        # Memory operations (TO ADD)
        "remember": memory.store,
        "recall": memory.query,
        "search_memory": memory.search,
        "list_memories": memory.list_keys,
    }
```

Then pass to patterns:

```python
scope = create_full_scope(session_id="my-task")

pattern = Hierarchical(
    coordinator_scope=scope,
    specialist_scope=scope,
)
```

---

## Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Claude Proxy | Working | Exposes Claude CLI as API |
| Agentica spawn() | Working | Creates agents in WASM sandbox |
| Scope passing | Working | Explicit via `spawn(..., scope=scope)` |
| Patterns as primitives | Working | Accept and distribute scope |
| File ops in scope | Working | `run_claude.py` wrappers |
| Memory in scope | **Not wired** | `MemoryService` exists, needs integration |
| PostgreSQL backend | Not deployed | Code ready |
| PGVector backend | Not deployed | Code ready |

**Bottom line:** The architecture is extensible. Patterns accept scope, agents get what you pass. Memory just needs to be wired into scope, then all agents can use it.

---

## Quick Start

```python
from agentica import spawn
from scripts.agentica.patterns.hierarchical import Hierarchical
from scripts.agentica.memory_service import MemoryService
from scripts.agentica.native_repl.run_claude import run_claude, read_file, write_file

# 1. Create memory service
memory = MemoryService(session_id="my-session")

# 2. Build full scope
scope = {
    "run_claude": run_claude,
    "read_file": read_file,
    "write_file": write_file,
    "remember": memory.store,
    "recall": memory.query,
}

# 3. Use with pattern
pattern = Hierarchical(
    coordinator_premise="You are a coordinator...",
    coordinator_scope=scope,
    specialist_scope=scope,
)

# 4. Execute - all agents have full access
result = await pattern.execute("Analyze the codebase and remember key findings")
```

---

## See Also

- `scripts/agentica/claude_proxy.py` - Claude CLI as OpenAI API
- `scripts/agentica/native_repl/run_claude.py` - Scope function wrappers
- `scripts/agentica/memory_service.py` - Memory implementation
- `scripts/agentica/patterns/` - Pattern primitives
