# Agentica + Claude Code Integration Journey

> **"Wait, it's all Claude?"**
>
> ```
> Claude Code (main) → Claude Code (subprocess) → Claude Proxy → Claude CLI → Claude API
> ```
>
> **"Always has been."** 🔫🧑‍🚀
>
> *[Astronaut meme insert here]*

---

**Timeline:** December 25-27, 2025
**Branch:** `feature/agentica-integration`
**Status:** Working integration with 12 multi-agent patterns

## The Goal

Create Python agents that can use Claude Code's full toolset (Read, Write, Edit, Bash, Grep, Glob) while maintaining:
- Stateful context across agent calls
- Multi-agent coordination patterns
- $0 LLM costs by routing through existing Claude subscription

**Key Question:** "What is Claude Code for vs what are Agentica agents for?"
- **Claude Code:** Interface layer, human interaction, native tools
- **Agentica:** State persistence, specialized workers, multi-agent orchestration

---

## Approach 1: Basic Agentica PoC (Braintrust Agent)

**Handoff:** `2025-12-25_20-54-52_agentica-integration-poc.md`

### What We Tried
Wrap existing Braintrust analysis functions as Agentica scope functions:

```python
from agentica import spawn

agent = await spawn(
    premise="You are a Braintrust analyst...",
    scope={"list_sessions": list_sessions, "analyze_session": analyze_session}
)
result = await agent.call(str, "List recent sessions")
```

### What Worked
- TDD approach caught design issues early
- Agent orchestration via Task tool preserved main context
- `redirect_stdout` + `StringIO` cleanly wrapped print-based functions

### What Failed
- Functions returned markdown strings, agent expected structured data
- Session IDs were truncated (used `[:8]...`), agent couldn't use them for drill-down
- Raw `agent.call()` without understanding Agentica's execution model

### Key Learning: State Location
| Approach | State Lives In |
|----------|---------------|
| Claude Code agents | LLM context (fills up, compacts) |
| Agentica agents | Python runtime (persists) |

> "They don't expand context window - they move state OUT of it"

---

## Approach 2: Agentica Server with REST Wrapper

**Handoffs:** `2025-12-25_21-58-54_agentica-server-architecture.md`, `2025-12-25_22-49-20_agentica-wrapper-architecture.md`

### What We Tried
Build a wrapper layer on top of official agentica-server to add:
- State persistence to `.claude/cache/agentica-state/`
- Braintrust logging via AgentListener pattern
- Session management for multi-turn conversations

### What Worked
- Discovered official `agentica-server` and `agentica-python-sdk` repos
- Understood SDK architecture: WebSocket sessions, OpenRouter routing, WASM sandbox
- Identified `S_M_BASE_URL` for SDK connection to self-hosted server

### What Failed
**Critical Blockers (SDK Limitations):**
1. **Deltas NOT injectable** - Cannot push conversation history into new agents
2. **Scope functions NOT serializable** - Can't persist callables across restarts
3. **WebSocket sessions ephemeral** - No reconnection to existing agents

This meant our wrapper would only save metadata, not actual conversation state.

### Key Learning: Hydration is Impossible
```python
# Cannot do this:
agent = restore_from_disk("agent_state.json")  # Deltas can't be injected

# Must create fresh agent each time:
agent = await spawn(premise="...", scope={...})  # New agent, no memory
```

---

## Approach 3: Claude Proxy ($0 LLM Costs)

**Handoffs:** `2025-12-25_23-46-04_agentica-state-layer-architecture.md`, `2025-12-26_00-08-00_claude-proxy-integration.md`

### What We Tried
Instead of paying for OpenRouter, route LLM calls through Claude CLI:

```
agentica-server
    | INFERENCE_ENDPOINT_URL=localhost:8080
    v
Claude Proxy (FastAPI)
    | subprocess
    v
claude -p "prompt" --allowedTools Read Write Edit Bash
    |
    v
Claude API ($0 via subscription)
```

### Implementation
```python
# scripts/agentica/claude_proxy.py
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    prompt = format_messages(request.messages)
    response = await call_claude_cli(prompt, REPL_BASELINE)
    return ChatCompletionResponse(...)
```

### What Worked
- OpenAI-compatible API endpoint with SSE streaming
- `S_M_BASE_URL` bypass eliminates API key requirement for local testing
- Rust nightly build for agentica-server (`edition2024` feature)

### What Failed
- Initial port conflict (8080 used by Docker)
- Wrong env var name (`AGENTICA_SERVER_URL` vs `S_M_BASE_URL`)
- Edition2024 Cargo feature required nightly Rust

### Architecture Established
```
Your Code (DependencySwarm, Hierarchical, etc.)
    | S_M_BASE_URL=http://localhost:2345
    v
Agentica Server (agentica-server)
    | INFERENCE_ENDPOINT_URL=http://localhost:8080
    v
Claude Proxy (claude_proxy.py)
    | --allowedTools Read Write Edit Bash
    v
Claude CLI (claude -p)
```

---

## Approach 4: Claude Scope Integration (Current Working Solution)

**Handoffs:** `2025-12-27_03-51-31_agentica-scope-integration-design.md`, `2025-12-27_04-45-56_claude-scope-implementation.md`

### The Breakthrough

Agentica's scope functions provide the key insight:
1. Agent writes Python code in sandbox
2. Code calls function in scope -> RPC to YOUR runtime
3. Return value stored as **proxy** (lightweight ref, not serialized)
4. Persists in agent scope for future turns

**10x Pattern: Claude CLI as Scope Functions**

```python
async def read_file(path: str) -> dict:
    result = await run_claude(f"Read {path}", tools=["Read"])
    return {"content": result, "path": path}

# Agent calls read_file() -> RPC -> Claude CLI -> result in scope
# Next turn: agent references scope["content"] (no re-read!)
```

### Implementation

**`scripts/agentica/claude_scope.py`:**
```python
def create_claude_scope(cache_reads: bool = True) -> dict[str, Any]:
    """Create scope with Claude CLI functions."""
    file_cache: dict[str, ClaudeResult] = {}

    def read_file(path: str) -> dict[str, Any]:
        if cache_reads and path in file_cache:
            return {"success": True, "content": cached.content, "cached": True}

        response = _call_claude_cli(f"Read {path}", ["Read"])
        file_cache[path] = result
        return {"success": True, "content": response, "cached": False}

    def write_file(path: str, content: str) -> dict[str, Any]:
        response = _call_claude_cli(f"Write to {path}", ["Write"])
        file_cache.pop(path, None)  # Invalidate cache
        return {"success": True, "path": path}

    return {
        "read_file": read_file,
        "write_file": write_file,
        "edit_file": edit_file,
        "bash": bash,
        "grep": grep,
        "glob": glob_search,
    }
```

**Multi-Agent Coordination via SharedContext:**
```python
@dataclass
class SharedContext:
    file_cache: dict[str, ClaudeResult] = field(default_factory=dict)
    operation_log: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get_cached(self, path: str) -> ClaudeResult | None:
        with self._lock:
            return self.file_cache.get(path)

# Multiple agents share cache
shared = SharedContext()
agent_a = await spawn(scope=create_claude_scope_with_shared(shared))
agent_b = await spawn(scope=create_claude_scope_with_shared(shared))
# Both see each other's cached reads!
```

### DependencySwarm Integration

```python
class DependencySwarm:
    def __init__(self, ..., use_claude_scope: bool = False):
        if scope is None and use_claude_scope:
            from scripts.agentica.claude_scope import create_claude_scope
            self.scope = create_claude_scope()
```

---

## The Memory Layer (Built in Parallel)

While developing the Claude Scope integration, we built a parallel memory subsystem inspired by **Letta/MemGPT** architecture. This provides agents with persistent, searchable memory that survives session boundaries.

### Three-Tier Architecture

| Tier | Purpose | Access Pattern |
|------|---------|---------------|
| **Core Memory** | Hot key-value pairs for current session | `memory.set_core("persona", "...")` |
| **Archival Memory** | Long-term FTS-indexed storage | `memory.store("User prefers Python")` |
| **Recall Memory** | Unified query across all sources | `memory.recall("What language?")` |

The architecture mirrors MemGPT's insight: keep frequently-accessed facts in "hot" storage (Core), archive everything else for search (Archival), and provide a unified interface (Recall) that queries both.

### Storage Backends

| Environment | Backend | Features |
|-------------|---------|----------|
| **Development** | SQLite + FTS5 | Zero config, WAL mode, portable |
| **Production** | PostgreSQL + pgvector | Vector similarity, concurrent writes, scalable |

The `MemoryService` (SQLite) and `MemoryServicePG` (PostgreSQL) share identical APIs, enabling local dev with SQLite and production deployment with Postgres.

### Embedding Service

Pluggable embedding providers for vector search:

```python
# OpenAI (1536 dim)
embedder = EmbeddingService(provider="openai")

# Voyage AI (1024 dim, code-optimized)
embedder = EmbeddingService(provider="voyage", model="voyage-code-3")

# Mock (testing, no API calls)
embedder = EmbeddingService(provider="mock")
```

Features:
- Content-based caching (avoids duplicate API calls)
- Batch processing for efficiency
- Retry logic with exponential backoff

### Scope Injection

Memory functions integrate directly into agent scope:

```python
scope = create_agent_scope(session_id="abc123")
# Agent now has access to:
# - remember(key, value)     -> Core memory
# - recall(query)            -> Unified search
# - search_memory(query)     -> Archival FTS
# - store_fact(content)      -> Archival storage
```

This enables agents to persist knowledge across turns without consuming LLM context.

### Hybrid Search (RRF)

The PostgreSQL backend supports **Reciprocal Rank Fusion** combining FTS + vector search:

```python
# Hybrid search with RRF
results = await memory.search_hybrid_rrf(
    query="authentication patterns",
    limit=10,
    k=60  # RRF constant
)
```

RRF formula: `score = 1/(k + fts_rank) + 1/(k + vec_rank)`

This ensures keyword matches and semantic similarity both contribute to relevance.

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `scripts/agentica/memory_service.py` | 396 | SQLite backend (Core + Archival + Recall) |
| `scripts/agentica/memory_service_pg.py` | 808 | PostgreSQL + pgvector backend |
| `scripts/agentica/embedding_service.py` | 603 | OpenAI, Voyage AI, Mock providers |
| `scripts/agentica/agent_scope.py` | 102 | Scope injection for agents |

---

## Architecture Diagram

```
                    +------------------------+
                    |     User Script        |
                    | (DependencySwarm, etc) |
                    +------------------------+
                              |
        +---------------------+---------------------+
        |                                           |
        | S_M_BASE_URL                              | (optional)
        v                                           v
+------------------------+              +------------------------+
|   Agentica Server      |              |    Memory Layer        |
|   (localhost:2345)     |              +------------------------+
|  - WASM Sandbox        |              |  create_agent_scope()  |
|  - Session Manager     |              |  - remember()          |
+------------------------+              |  - recall()            |
        |                               |  - store_fact()        |
        | INFERENCE_ENDPOINT_URL        +------------------------+
        v                                           |
+------------------------+              +-----------+-----------+
|    Claude Proxy        |              |                       |
|   (localhost:8080)     |              v                       v
|  - OpenAI-compatible   |      +------------+         +----------------+
|  - SSE streaming       |      |  SQLite    |         |  PostgreSQL    |
+------------------------+      |  + FTS5    |         |  + pgvector    |
        |                       |  (dev)     |         |  (prod)        |
        | subprocess            +------------+         +----------------+
        v                               |                       |
+------------------------+              v                       v
|     Claude CLI         |      +------------+         +----------------+
|   (claude -p)          |      | Embedding  |<------->| Vector Search  |
|  --allowedTools:       |      | Service    |         | Hybrid RRF     |
|   Read, Write, Edit,   |      | OpenAI/    |         +----------------+
|   Bash                 |      | VoyageAI   |
+------------------------+      +------------+
        |
        v
+------------------------+
|     Claude API         |
| ($0 via subscription)  |
+------------------------+
```

**Memory Layer Integration:** Agents can optionally use the memory layer for persistent storage. Memory functions are injected into agent scope via `create_agent_scope()`, enabling `remember()`, `recall()`, and `search_memory()` calls that persist across sessions.

### Scope Function Flow
```
Agent REPL writes Python:
    content = read_file("/path/to/file.py")
          |
          | RPC to Python runtime
          v
    def read_file(path):
        result = subprocess.run(["claude", "-p", f"Read {path}", ...])
        file_cache[path] = result  # Cached for next turn
        return {"content": result, ...}
          |
          | Returns proxy to agent scope
          v
    Agent scope: {"content": "file contents..."}
          |
          | Next turn references directly
          v
    # No re-read needed!
```

---

## Test Results Summary

### Unit Tests
| Component | Tests | Passing | Time |
|-----------|-------|---------|------|
| claude_scope.py | 27 | 27 | 0.62s |
| Agentica patterns | 191 | 174 | 1.51s |
| **Total** | **218** | **201** | **~2s** |

### E2E Integration Tests
| Test | Status | Time |
|------|--------|------|
| Smoke test (simple query) | PASS | 54s |
| Basic scope persistence | PASS | 288s |
| File read/write cycle | PASS | ~120s |
| Path fidelity check | FAIL* | - |
| Complex multi-step | FAIL* | - |

*Failures due to agent hallucination (not scope bugs)

### Key Test Scenarios Verified
1. **Scope function calling** - Agent correctly uses `read_file()`, `write_file()`, etc.
2. **Cache persistence** - Second read returns cached result
3. **Cache invalidation** - Write/edit invalidates cache for that path
4. **SharedContext** - Multiple agents see same cache
5. **DependencySwarm integration** - `use_claude_scope=True` works

---

## Critical Learnings

### 1. LLM Instruction Ambiguity
The biggest challenge was getting Claude to use the right tools:

**Problem:** Agent tried to call `view_file()` (doesn't exist) instead of `read_file()`

**Solution:** Emphatic REPL_BASELINE prompt with examples:
```python
REPL_BASELINE = """
## AVAILABLE SCOPE FUNCTIONS (USE THESE!)

```python
result = read_file("/path/to/file.txt")  # Returns dict
result = write_file("/path/to/file.txt", "content")
```

**IMPORTANT:** Do NOT use:
- `view_file()` - DOES NOT EXIST
- `await` anything - these are sync functions

## PATH FIDELITY REQUIREMENT
**YOU MUST USE THE EXACT FILE PATHS PROVIDED IN THE TASK.**
"""
```

### 2. Scope Key Naming
Agentica doesn't allow scope keys starting with underscore:
```python
# FAILS: ValueError: Global scope key _get_cache cannot start with underscore
scope = {"_get_cache": get_cache}

# WORKS: Use debug_ prefix
scope = {"debug_get_cache": get_cache}
```

### 3. State Persistence Architecture
```
Durable State (Ledgers, Handoffs)     <- Single source of truth
    - Survives: process exit, /clear, weeks later
    - Human-readable, version-controlled
    | hydrates on start
    v persists on change
Working Memory (Agentica Runtime)     <- Fast operations
    - Objects by reference (not in LLM context)
    - Accumulates across agent calls
    - Volatile: gone when process exits
```

### 4. "Write Code" > "Do Task"
Three-approach evaluation showed:
| Metric | Task Agent | DependencySwarm | Native REPL |
|--------|-----------|-----------------|-------------|
| Implementation LOC | 794 | 879 | 299 |
| Test passing | 4% | 97.6% | 100% |

The constraint of "write Python that uses scope functions" forces explicit reasoning and smaller output.

### 5. Claude IS the Router
Don't build separate routing infrastructure:
```python
# WRONG: Add routing layer
router = await spawn("Select pattern based on task...")
pattern = await router.call(str, task_description)

# RIGHT: Pattern selection in Claude's reasoning
# Give Claude a "pattern vocabulary" via rules
# Pattern: agent-orchestration.md Pattern Selection Guide
```

---

## What Failed and Why

### 1. Wrapper Architecture (SDK Hydration)
**Tried:** Build REST wrapper to persist/restore agent state
**Failed:** Agentica SDK doesn't support injecting conversation deltas into new agents
**Root cause:** `Agent.__init__()` doesn't accept prior deltas, `gen.deltas` not exposed

### 2. Cross-Process State Persistence
**Tried:** Have agent in Process A query agent in Process B
**Failed:** Each `spawn()` creates NEW agent with fresh state
**Workaround:** Use SharedContext pattern within single process

### 3. Dict Return Types
**Tried:** `agent.call(dict[str, Any], "Get structured data")`
**Failed:** "Arbitrary is Coming Soon to agentica"
**Workaround:** Use `str` return type, parse JSON manually

### 4. `--allowed-tools` Flag Parsing
**Tried:** `claude -p "task" --allowed-tools Read Write`
**Failed:** Variadic flag consumed "task" as a tool name
**Fix:** Add `--` separator: `claude -p "task" -- --allowed-tools Read Write`

### 5. Agent Path Hallucination
**Tried:** "Create file at /tmp/workspace/test.py"
**Failed:** Agent created `/tmp/workspace/greet.py` instead
**Mitigation:** Added PATH FIDELITY REQUIREMENT section to REPL_BASELINE

---

## The 12 Patterns

All patterns implemented in `scripts/agentica/patterns.py`:

| Pattern | Description | Use Case |
|---------|-------------|----------|
| **Swarm** | Parallel attack from different angles | Research, exploration |
| **Pipeline** | A -> B -> C sequential | Linear workflows |
| **Hierarchical** | Coordinator -> Specialists -> Grunts | Complex decomposition |
| **Jury** | N agents vote independently | High-stakes decisions |
| **GeneratorCritic** | Propose -> Critique -> Refine | Code review, writing |
| **DependencySwarm** | Parallel with dependencies | Build systems, task graphs |
| **Circuit Breaker** | Primary -> Fallback on failure | Resilient pipelines |
| **Map/Reduce** | Fan out -> Aggregate | Batch processing |
| **Adversarial** | Red vs Blue -> Judge | Security review |
| **Chain of Responsibility** | Escalation tiers | Capability matching |
| **Blackboard** | Shared state, all read/write | Collaborative solving |
| **Event-Driven** | Subscribe/React | Monitoring, async |

### Pattern + Claude Scope Integration

```python
from scripts.agentica.dependency_swarm import DependencySwarm
from scripts.agentica.coordination import CoordinationDB

db = CoordinationDB()
swarm = DependencySwarm(
    db=db,
    use_claude_scope=True,  # Enables read_file, write_file, bash, etc.
)

swarm.add_task("models", "Implement data models", file_path="src/models.py")
swarm.add_task("api", "Implement API", depends_on=["models"])
swarm.add_task("tests", "Write tests", depends_on=["api"])

results = await swarm.execute()
```

---

## Future Work

### 1. DSPy/GEPA Prompt Optimization
Current REPL_BASELINE is ~500 tokens. Could reduce with:
- Automated prompt tuning based on success metrics
- Few-shot compression
- Structured output schemas

### 2. Structured Tool Calling
Replace free-form REPL code with structured function calls:
```python
# Current: Agent writes Python code
result = read_file("/path/to/file.py")

# Future: Agent calls tool directly with schema
# Tool: read_file(path: str) -> FileContent
```

### 3. SQLite Concurrency for Multi-Agent
Current SharedContext uses threading.Lock. For true parallelism:
- SQLite WAL mode for concurrent reads
- Postgres for multi-process agents
- Research: SQLite sharding patterns

### 4. Braintrust Observability
- Token usage tracking (Claude CLI doesn't expose counts)
- Parent-child linking across agent sessions
- Pattern performance metrics

### 5. Level 2 CLI Wrapper
```bash
# Future pattern runner
uv run python scripts/agentica/run_pattern.py \
  --pattern dependency_swarm \
  --agents agents.yaml \
  --task "implement auth system"
```

---

## Quick Start

### Server Stack
```bash
# Terminal 1: Claude proxy
uv run python scripts/agentica/claude_proxy.py --port 8080

# Terminal 2: Agentica server (requires Rust nightly)
cd workspace/agentica-research/agentica-server
INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions \
uv run agentica-server --port 2345
```

### Run Tests
```bash
# Unit tests
uv run pytest tests/unit/test_claude_scope.py -v

# Pattern tests
uv run pytest tests/unit/test_agentica_*.py -v

# E2E (requires servers running)
S_M_BASE_URL=http://localhost:2345 \
uv run pytest tests/integration/test_claude_scope_e2e.py -v -s
```

### Use DependencySwarm
```python
from scripts.agentica.dependency_swarm import DependencySwarm
from scripts.agentica.coordination import CoordinationDB

db = CoordinationDB()
swarm = DependencySwarm(db=db, use_claude_scope=True)

# Add tasks with dependencies
models_id = swarm.add_task("models", "Create User model")
api_id = swarm.add_task("api", "Create REST endpoints", depends_on=[models_id])

# Execute (respects dependency order)
results = await swarm.execute()
```

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/agentica/claude_proxy.py` | OpenAI-compatible proxy to Claude CLI |
| `scripts/agentica/claude_scope.py` | Scope functions for Agentica agents |
| `scripts/agentica/dependency_swarm.py` | DAG-based parallel task execution |
| `scripts/agentica/patterns.py` | 12 multi-agent coordination patterns |
| `scripts/agentica/PATTERNS.md` | Pattern reference documentation |
| `tests/unit/test_claude_scope.py` | 27 unit tests for scope functions |
| `.claude/rules/agent-orchestration.md` | Pattern Selection Guide |
| `.claude/skills/agentica-sdk/SKILL.md` | Agentica SDK reference |

---

## Session References

Handoffs documenting this journey (in `thoughts/shared/handoffs/open-source-release/`):

1. `2025-12-25_20-54-52_agentica-integration-poc.md` - Initial PoC
2. `2025-12-25_21-58-54_agentica-server-architecture.md` - Server design
3. `2025-12-25_22-49-20_agentica-wrapper-architecture.md` - Wrapper approach
4. `2025-12-25_23-46-04_agentica-state-layer-architecture.md` - State layer pivot
5. `2025-12-26_00-08-00_claude-proxy-integration.md` - Proxy implementation
6. `2025-12-26_01-00-18_agentica-state-persistence-testing.md` - State testing
7. `2025-12-26_03-07-12_multi-agent-patterns-router-decision.md` - Router decision
8. `2025-12-26_04-29-15_agentica-multi-agent-patterns.md` - TDD patterns
9. `2025-12-26_14-54-29_repl-prompt-engineering.md` - REPL prompt fix
10. `2025-12-26_18-10-24_agentica-eval-three-approaches.md` - Three approaches
11. `2025-12-26_19-45-37_native-repl-validated.md` - Native REPL validation
12. `2025-12-27_00-16-59_three-approaches-eval-complete.md` - Eval complete
13. `2025-12-27_03-51-31_agentica-scope-integration-design.md` - Scope design
14. `2025-12-27_04-45-56_claude-scope-implementation.md` - Implementation

---

## Session Updates

### 2025-12-27

#### Prompt Engineering Breakthrough
- **Problem:** LLMs conflate "read file at X" with file creation (~35% failure rate)
- **Solution:** Use "RETRIEVE contents of:" instead of "Read", added explicit READ vs WRITE section to REPL_BASELINE
- **Result:** E2E tests now pass reliably (was 3/5, now 5/5)
- **New skill:** `.claude/skills/agentica-prompts/SKILL.md` - prompt patterns for agent reliability

#### Memory Layer Discovery
- Found existing Letta/MemGPT-style memory system built in parallel
- **Three-tier architecture:** Core (hot key-value), Archival (FTS-indexed), Recall (unified query)
- **Backends:** SQLite (dev) + PostgreSQL/pgvector (prod)
- ~2000 lines across `memory_service.py`, `memory_service_pg.py`, `embedding_service.py`
- Not yet wired to `claude_scope` (next integration step)

#### Pattern-Aware Watcher
- Extended `watch_agents.py` with log tailing and pattern-aware visualization
- Three visualizer types: `ParallelVisualizer`, `SequentialVisualizer`, `HierarchicalVisualizer`
- Real-time message table showing agent I/O

#### Key Insight
> "Claude all the way down" - every layer uses Claude, making this a novel self-referential architecture

---

## Observability (Already Done)

### Two Logging Layers
1. **Agentica Level**: `./logs/agent-{id}.log` - Per-agent chat history, XML format
2. **Braintrust Level**: Every Claude CLI subprocess = Braintrust session trace

Both are automatic - no additional work needed.

### Polish Status

| Item | Status | Notes |
|------|--------|-------|
| Observability/Logging | Already done | Two layers active |
| Error handling | Future | Retry logic, graceful degradation |
| Config (hardcoded ports) | Future | Move 8080/2345 to env/config |
| Startup script | Future | 3 terminals -> single command |
| User-facing docs | Future | Tutorials, examples |
| Memory <-> claude_scope wiring | Next step | Merge agent_scope into claude_scope |
| API key fallback | Optional | Strategy pattern for CLI->API switch |
| SQLite scaling | Known | Postgres ready for production |

### Crossed Off (Not Needed)
- ~~Observability~~ - Already have 2 logging layers
- ~~LLM flakiness mitigation~~ - Solved with RETRIEVE prompts
