# Architecture

System design and component overview for the Claude Continuity Kit.

---

## High-Level Overview

```
+-----------------------------------------------------------------------+
|                        CLAUDE CODE SESSION                            |
|                                                                       |
|  +-----------+    +-----------+    +-----------+    +-----------+    |
|  |SessionStart|-->|  Working  |-->| PreCompact|-->| SessionEnd|     |
|  +-----------+    +-----------+    +-----------+    +-----------+    |
|       |                |                |                |            |
|       v                v                v                v            |
|  Load Ledger      PreToolUse       Auto-Handoff     Mark Outcome     |
|  Load Handoff     PostToolUse      Block Manual     Extract Learns   |
|  Show Learnings   UserPrompt                        Cleanup          |
+-----------------------------------------------------------------------+
        |                |                |                |
        v                v                v                v
+-----------------------------------------------------------------------+
|                           DATA LAYER                                  |
|                                                                       |
|  thoughts/                 .claude/cache/              .git/claude/  |
|  +-- ledgers/              +-- artifact-index/         +-- commits/  |
|  |   +-- CONTINUITY_*.md       +-- context.db              +-- <hash>/
|  +-- shared/               +-- learnings/                      +-- reasoning.md
|      +-- handoffs/             +-- <date>_<session>.md              |
|      +-- plans/            +-- braintrust_sessions/                  |
+-----------------------------------------------------------------------+
        |                                        |
        v                                        v
+-----------------------------+    +-----------------------------+
|         SKILLS              |    |          AGENTS             |
|                             |    |                             |
|  continuity_ledger          |    |  plan-agent                 |
|  create_handoff             |    |  validate-agent             |
|  resume_handoff             |    |  implement_plan             |
|  commit                     |    |  research-agent             |
|  tdd-workflow               |    |  debug-agent                |
|  hook-developer             |    |  rp-explorer                |
+-----------------------------+    +-----------------------------+
        |                                        |
        +-------------------+--------------------+
                            v
+-----------------------------------------------------------------------+
|                    SCRIPTS (MCP Execution)                            |
|                                                                       |
|  Artifact Index      Braintrust         MCP Tools                    |
|  +---------------+   +---------------+   +---------------+           |
|  | artifact_*    |   | braintrust_   |   | perplexity_   |           |
|  |               |   |   analyze     |   | nia_docs      |           |
|  |               |   |               |   | firecrawl_    |           |
|  +---------------+   +---------------+   | morph_search  |           |
|                                          | ast_grep_find |           |
|  Executed via: uv run python -m runtime.harness scripts/<script>.py  |
+-----------------------------------------------------------------------+
        |
        v
+-----------------------------------------------------------------------+
|                      PATTERN ENGINE                                   |
|                                                                       |
|  +--------+  +--------+  +--------+  +--------+  +--------+          |
|  | Swarm  |  |Pipeline|  | Jury   |  |Hierar- |  |Gen/    |          |
|  |        |  |        |  |        |  |chical  |  |Critic  |          |
|  +--------+  +--------+  +--------+  +--------+  +--------+          |
|  +--------+  +--------+  +--------+  +--------+  +--------+          |
|  |Circuit |  |  Map/  |  |Black-  |  |Advers- |  | Event  |          |
|  |Breaker |  | Reduce |  | board  |  | arial  |  | Driven |          |
|  +--------+  +--------+  +--------+  +--------+  +--------+          |
|  +--------+                                                          |
|  |Chain of|                                                          |
|  |Respons.|    Primitives: Consensus, Aggregator, HandoffState       |
|  +--------+                                                          |
+-----------------------------------------------------------------------+
        |
        v
+-----------------------------------------------------------------------+
|                      MEMORY & COORDINATION                            |
|                                                                       |
|  +------------------+    +------------------+    +------------------+ |
|  | MemoryService    |    | MemoryServicePG  |    | CoordinationDB   | |
|  | (SQLite + FTS5)  |    | (PostgreSQL +    |    | (SQLite)         | |
|  |                  |    |  pgvector)       |    |                  | |
|  | Core Memory      |    | Vector Search    |    | Agent Tracking   | |
|  | Archival Memory  |    | Semantic Recall  |    | Task Completion  | |
|  | Recall Memory    |    |                  |    | Broadcasts       | |
|  +------------------+    +------------------+    +------------------+ |
+-----------------------------------------------------------------------+
```

---

## Core Components

### 1. Pattern Engine

**Location:** `scripts/agentica/patterns/`

**Purpose:** Multi-agent orchestration with 11 coordination patterns.

The Pattern Engine provides battle-tested patterns for coordinating multiple AI agents. Each pattern encapsulates a specific coordination strategy optimized for different task characteristics.

**Key Files:**
- `primitives.py` - Base building blocks (Consensus, Aggregator, HandoffState)
- `swarm.py` - Parallel agents with diverse perspectives
- `hierarchical.py` - Coordinator decomposes, specialists execute
- `jury.py` - Multiple agents vote, consensus decides
- `pipeline.py` - Sequential stage execution with handoff state
- `generator_critic.py` - Iterative propose/critique refinement
- `circuit_breaker.py` - Primary with fallback on failure
- `map_reduce.py` - Fan out to workers, aggregate results
- `chain_of_responsibility.py` - Escalating handler chain
- `adversarial.py` - Red team vs Blue team with judge
- `event_driven.py` - Publish/subscribe event dispatch
- `blackboard.py` - Shared state collaborative solving

**Architecture:**
```
Pattern Classes
       |
       +-- use --> Primitives (Consensus, Aggregator, HandoffState)
       |
       +-- spawn --> Agentica Agents (via spawn())
       |
       +-- track --> CoordinationDB (agent/task records)
```

**Pattern Selection:** Claude acts as the router, selecting patterns based on task keywords:
- "research", "investigate" -> Swarm
- "implement", "build" -> Hierarchical
- "review", "feedback" -> Generator/Critic
- "is correct", high-stakes -> Jury
- Linear workflow -> Pipeline

---

### 2. Hook System

**Location:** `.claude/hooks/`

**Purpose:** Claude Code lifecycle integration for state preservation.

Hooks intercept Claude Code events and automate continuity operations. They follow a shell-wrapper to TypeScript pattern for type safety and debugging.

**Hook Events:**
| Event | When | Purpose |
|-------|------|---------|
| SessionStart | New session, /clear, compact | Load ledger + handoff into context |
| PreToolUse | Before tool execution | TypeScript preflight, validation |
| PostToolUse | After Edit/Write/Bash | Index handoffs, track changes |
| PreCompact | Before compaction | Auto-handoff, block manual compact |
| UserPromptSubmit | Before processing message | Skill suggestions, context warnings |
| SubagentStart/Stop | Agent lifecycle | Track agent spawning/completion |
| SessionEnd | Session closes | Mark outcome, extract learnings, cleanup |
| Stop | Agent finishes turn | Finalize traces |

**Key Files:**
- `src/*.ts` - TypeScript handlers (type-safe logic)
- `dist/*.mjs` - Bundled JavaScript (no runtime deps)
- `*.sh` - Shell wrappers (entry points)
- `shared/` - Shared utilities and types

**Pattern:**
```bash
# Shell wrapper (entry point)
#!/bin/bash
set -e
cd "$CLAUDE_PROJECT_DIR/.claude/hooks"
cat | node dist/session-start-continuity.mjs
```

```typescript
// TypeScript handler (logic)
interface HookInput {
  source: 'startup' | 'resume' | 'clear' | 'compact';
  session_id: string;
}

async function main() {
  const input: HookInput = JSON.parse(await readStdin());
  // Process input
  const output = { result: 'continue', message: 'State loaded' };
  console.log(JSON.stringify(output));
}
```

---

### 3. Memory Backend

**Location:** `scripts/agentica/memory_*.py`

**Purpose:** Persistent agent memory with semantic search.

Inspired by Letta/MemGPT architecture, the memory system provides three memory tiers:

**Memory Tiers:**
```
+------------------+     +------------------+     +------------------+
|   Core Memory    |     | Archival Memory  |     |  Recall Memory   |
|                  |     |                  |     |                  |
| Key-value store  |     | FTS5 searchable  |     | Cross-source     |
| Current facts    |     | Long-term facts  |     | Query interface  |
| In-context       |     | Persistent       |     | Combines all     |
+------------------+     +------------------+     +------------------+
```

**Key Files:**
- `memory_service.py` - SQLite + FTS5 backend
- `memory_service_pg.py` - PostgreSQL + pgvector backend
- `embedding_service.py` - Multi-provider embedding generation
- `memory_protocol.py` - Protocol for backend implementations

**Usage:**
```python
memory = MemoryService(session_id="abc123")
await memory.connect()

# Core memory (in-context)
await memory.set_core("task", "Build REST API")

# Archival memory (searchable)
await memory.store("User prefers Python")

# Recall (cross-source)
result = await memory.recall("What language?")
```

---

### 4. MCP Integration

**Location:** `src/runtime/`

**Purpose:** Token-efficient tool execution via scripts.

The MCP runtime implements Anthropic's Code Execution pattern for 99.6% token reduction. Instead of loading tool schemas into context, tools are executed via Python scripts.

**Key Files:**
- `mcp_client.py` - Lazy-loading client manager with state machine
- `harness.py` - Script execution entry point
- `config.py` - Configuration parsing (Pydantic models)
- `generate_wrappers.py` - Auto-generate Python wrappers from MCP schemas

**State Machine:**
```
UNINITIALIZED --> initialize() --> INITIALIZED --> call_tool() --> CONNECTED
      ^                                                              |
      +----------------------- cleanup() ---------------------------+
```

**Pattern:**
```python
# Script (99.6% token reduction)
from runtime.mcp_client import call_mcp_tool

result = await call_mcp_tool("morph__warpgrep", {"query": "pattern"})
print(result)
```

```bash
# Execution
uv run python -m runtime.harness scripts/morph_search.py --query "pattern"
```

---

### 5. Coordination Database

**Location:** `scripts/agentica/coordination.py`

**Purpose:** Multi-agent observability and state tracking.

SQLite-backed tracking for running agents, completed tasks, and swarm broadcasts.

**Schema:**
```sql
-- Running/completed agents
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    premise TEXT,
    pattern TEXT,        -- swarm, hierarchical, jury, etc.
    parent_agent_id TEXT,
    status TEXT,         -- running, completed, failed
    spawned_at TEXT,
    completed_at TEXT
);

-- Task completion records
CREATE TABLE completed_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    input_summary TEXT,
    output_summary TEXT,
    artifacts TEXT,      -- JSON
    duration_ms INTEGER
);

-- Swarm broadcast messages
CREATE TABLE broadcasts (
    id TEXT PRIMARY KEY,
    swarm_id TEXT,
    sender_agent TEXT,
    broadcast_type TEXT, -- finding, question, blocker, done, abort
    payload TEXT         -- JSON
);
```

**Broadcast Types:**
- `FINDING` - Agent discovered something useful
- `QUESTION` - Agent asking others for help
- `BLOCKER` - Agent is stuck
- `DONE` - Agent completed work
- `ABORT` - Critical failure, abort swarm

---

## Data Flow

### Session Lifecycle

```
1. SESSION START
   +--------------------+
   | SessionStart Hook  |
   +--------------------+
            |
            v
   +--------------------+
   | Load Ledger        |  thoughts/ledgers/CONTINUITY_CLAUDE-*.md
   | Load Handoff       |  thoughts/shared/handoffs/<session>/*.md
   | Surface Learnings  |  .claude/cache/learnings/<48h>
   +--------------------+
            |
            v
   Context primed with state

2. WORKING
   +--------------------+
   | PreToolUse Hook    |  TypeScript preflight for .ts files
   +--------------------+
            |
   +--------------------+
   | Tool Execution     |  Edit, Write, Bash, etc.
   +--------------------+
            |
   +--------------------+
   | PostToolUse Hook   |  Index handoffs, track changes
   +--------------------+
            |
   +--------------------+
   | UserPromptSubmit   |  Skill hints, context warnings
   +--------------------+

3. PRE-COMPACT (if context fills)
   +--------------------+
   | PreCompact Hook    |
   +--------------------+
            |
            v
   +--------------------+
   | Auto-Handoff       |  Parse transcript, generate handoff
   | Block Manual       |  Prompt for /continuity_ledger
   +--------------------+

4. SESSION END
   +--------------------+
   | SessionEnd Hook    |
   +--------------------+
            |
            v
   +--------------------+
   | Mark Outcome       |  SUCCEEDED, PARTIAL, FAILED
   | Extract Learnings  |  What Worked/Failed/Patterns
   | Cleanup            |  Temp files, state
   +--------------------+
```

### Agent Orchestration Flow

```
User Request: "Research and implement authentication"

1. PLAN PHASE (plan-agent)
   +--------------------+
   | Spawn plan-agent   |  Uses MCP tools for research
   +--------------------+
            |
            v
   +--------------------+
   | Research           |  Perplexity, NIA, Morph
   | Design             |  Create implementation plan
   | Write plan         |  thoughts/shared/plans/*.md
   +--------------------+

2. VALIDATE PHASE (validate-agent)
   +--------------------+
   | Spawn validate     |  RAG-judge + WebSearch
   +--------------------+
            |
            v
   +--------------------+
   | Check precedent    |  Artifact Index queries
   | Verify practices   |  Web search for best practices
   | Flag issues        |  Validation report
   +--------------------+

3. IMPLEMENT PHASE (implement_plan)
   +--------------------+
   | Select Pattern     |  Hierarchical for complex impl
   +--------------------+
            |
            v
   +--------------------+     +--------------------+
   | Coordinator        | --> | Specialist 1       |
   | Decomposes task    |     | Auth module        |
   +--------------------+     +--------------------+
                                       |
            +--------------------+     |
            | Specialist 2       | <---+
            | Tests              |
            +--------------------+
                    |
                    v
   +--------------------+
   | Handoffs           |  thoughts/shared/handoffs/session/
   +--------------------+
```

---

## Database Schema

### Coordination DB (SQLite)

**Location:** `.claude/cache/agentica-coordination/coordination.db`

```
+-------------+        +------------------+        +-------------+
|   agents    |        | completed_tasks  |        | broadcasts  |
+-------------+        +------------------+        +-------------+
| id (PK)     |<----+  | id (PK)          |  +---->| id (PK)     |
| session_id  |     |  | agent_id (FK)    |--+     | swarm_id    |
| premise     |     +--| pattern          |        | sender_agent|
| model       |        | input_summary    |        | broadcast_  |
| pattern     |        | output_summary   |        |   type      |
| parent_id   |        | artifacts (JSON) |        | payload     |
| status      |        | duration_ms      |        | created_at  |
| spawned_at  |        | completed_at     |        +-------------+
| completed_at|        +------------------+
+-------------+
      |
      |        +-------------+
      +------->| artifacts   |
               +-------------+
               | id (PK)     |
               | task_id(FK) |
               | key         |
               | value_type  |
               | value       |
               +-------------+
```

### Memory DB (SQLite + FTS5)

**Location:** `.claude/cache/memory/memory.db`

```
+-----------------+        +---------------------+
|   core_memory   |        | archival_memory_fts |
+-----------------+        +---------------------+
| session_id (PK) |        | id (PK)             |
| key (PK)        |        | session_id          |
| value           |        | content             |  <-- FTS5 indexed
| updated_at      |        | metadata (JSON)     |
+-----------------+        | created_at          |
                           +---------------------+
```

### Memory DB (PostgreSQL + pgvector)

**Location:** Configurable via `PG_*` env vars

```
+--------------------+        +--------------------+
| archival_facts     |        | core_memory        |
+--------------------+        +--------------------+
| id (PK)            |        | session_id (PK)    |
| session_id         |        | key (PK)           |
| content            |        | value              |
| embedding (vector) |  <-- pgvector               | updated_at         |
| metadata (jsonb)   |        +--------------------+
| created_at         |
+--------------------+
        |
        +-- GIN index on embedding for similarity search
```

### Artifact Index (SQLite + FTS5)

**Location:** `.claude/cache/artifact-index/context.db`

```
+------------------+        +------------------+
| artifacts        |        | artifacts_fts    |
+------------------+        +------------------+
| id (PK)          |        | id               |
| type             |        | content          |  <-- FTS5 indexed
| path             |        | summary          |
| session_id       |        +------------------+
| root_span_id     |
| turn_span_id     |
| content          |
| summary          |
| outcome          |  <-- SUCCEEDED, PARTIAL, FAILED
| created_at       |
+------------------+
```

---

## Design Decisions

### Why "Clear, Don't Compact"

**Problem:** Compaction is lossy. Each compaction produces a summary of a summary, degrading signal.

**Solution:** Save state to files (ledgers, handoffs), wipe context, resume fresh.

**Benefits:**
- Ledgers are lossless - you control what's preserved
- Fresh context = full signal
- Agents spawn with clean context, not degraded summaries

### Why Shell Wrapper -> TypeScript Pattern

**Problem:** Hooks need type safety for complex logic but must be invokable by Claude Code.

**Solution:** Shell scripts as entry points, TypeScript for logic, pre-bundled to avoid runtime deps.

**Benefits:**
- Type safety catches errors at build time
- No runtime dependencies (bundled JS)
- Easy to test (`echo '{}' | ./hook.sh`)
- Works across platforms

### Why Protocol Over ABC for Backends

**Problem:** Abstract base classes create rigid inheritance hierarchies.

**Solution:** Duck typing via protocols - any class with matching methods works.

**Benefits:**
- Easier to test (mock without inheritance)
- Easier to extend (no base class coupling)
- Third-party integrations (Redis, S3, etc.)
- Faster prototyping

### Why File-Based Checkboxes Over TodoWrite

**Problem:** TodoWrite survives compaction but context around todos degrades.

**Solution:** Track progress with checkboxes in ledger files.

**Benefits:**
- File content never degrades (full fidelity)
- Human-readable without tools
- Visible in git diffs
- Persistent across sessions

### Why Scripts Over Loaded Tool Schemas

**Problem:** Loading MCP tool schemas into context consumes tokens (150K+ for full registry).

**Solution:** Execute tools via Python scripts - only script content in context.

**Benefits:**
- 99.6% token reduction (110 tokens vs 30K)
- Progressive disclosure (read script on demand)
- CLI arguments for parameters
- Reusable across sessions

---

## Extension Points

### Adding a New Pattern

1. **Create pattern file:**
   ```python
   # scripts/agentica/patterns/my_pattern.py
   from .primitives import HandoffState, Aggregator

   class MyPattern:
       def __init__(self, config: dict):
           self.config = config

       async def execute(self, task: str) -> HandoffState:
           # Pattern logic
           pass
   ```

2. **Export from `__init__.py`:**
   ```python
   # scripts/agentica/patterns/__init__.py
   from .my_pattern import MyPattern
   ```

3. **Add tests:**
   ```python
   # tests/unit/test_agentica_my_pattern.py
   async def test_my_pattern_creation():
       pattern = MyPattern(config={})
       assert pattern is not None
   ```

4. **Document in PATTERNS.md**

### Adding a New Hook

1. **Create TypeScript handler:**
   ```typescript
   // .claude/hooks/src/my-hook.ts
   interface MyHookInput {
     // Event-specific fields
   }

   async function main() {
     const input: MyHookInput = JSON.parse(await readStdin());
     const output = { result: 'continue' };
     console.log(JSON.stringify(output));
   }
   ```

2. **Create shell wrapper:**
   ```bash
   #!/bin/bash
   # .claude/hooks/my-hook.sh
   set -e
   cd "$CLAUDE_PROJECT_DIR/.claude/hooks"
   cat | node dist/my-hook.mjs
   ```

3. **Build:**
   ```bash
   cd .claude/hooks && ./build.sh
   ```

4. **Register in settings.json:**
   ```json
   {
     "hooks": {
       "EventType": [{
         "matcher": "pattern",
         "hooks": [{
           "type": "command",
           "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/my-hook.sh"
         }]
       }]
     }
   }
   ```

5. **Test manually:**
   ```bash
   echo '{"source": "test"}' | .claude/hooks/my-hook.sh
   ```

### Adding a New Memory Backend

1. **Implement the protocol:**
   ```python
   # scripts/agentica/memory_my_backend.py
   class MyBackend:
       async def connect(self) -> None: ...
       async def close(self) -> None: ...
       async def set_core(self, key: str, value: str) -> None: ...
       async def get_core(self, key: str) -> str | None: ...
       async def store(self, content: str, metadata: dict) -> str: ...
       async def recall(self, query: str, limit: int = 5) -> list: ...
   ```

2. **Add to factory:**
   ```python
   # scripts/agentica/memory_factory.py
   def create_memory_backend(backend_type: str) -> MemoryBackend:
       if backend_type == "my_backend":
           return MyBackend()
   ```

3. **Add tests:**
   ```python
   # tests/unit/test_memory_my_backend.py
   async def test_my_backend_store_recall():
       backend = MyBackend()
       await backend.connect()
       await backend.store("fact", {})
       results = await backend.recall("fact")
       assert len(results) > 0
   ```

---

## Related Documentation

- [PATTERNS.md](./architecture/PATTERNS.md) - Detailed pattern reference
- [LESSONS_LEARNED.md](./architecture/LESSONS_LEARNED.md) - Design rationale and insights
- [README.md](../README.md) - Quick start and overview
- [QUICKSTART.md](./guides/QUICKSTART.md) - 5-minute setup guide
