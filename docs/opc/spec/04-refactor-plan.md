# Refactor Plan: Claude Continuity Kit v3

## CRITICAL UPDATE: Use `claude -p` Instead of Task Tool

The refactor will use `claude -p "query"` via Bash instead of Task tool for agent spawning:

```bash
# Spawn parallel agents (true process isolation)
claude -p "As security expert: $QUERY" --output-format json > /tmp/swarm-1.json &
claude -p "As performance expert: $QUERY" --output-format json > /tmp/swarm-2.json &
wait

# Agents write to PostgreSQL CoordinationDB during execution
# Main reads DB for status, not output files (avoids context pollution)
```

**Why `claude -p` over Task tool:**
| Aspect | Task Tool | `claude -p` via Bash |
|--------|-----------|---------------------|
| Process isolation | Subagent context | Completely separate process |
| Context pollution | Summary returned | Zero - stdout only |
| Parallel execution | Limited | True parallel with `&` |
| Control over flags | Subagent type only | Full (`--allowedTools`, `--output-format json`) |
| Monitoring | TaskOutput (floods context) | `ps`, process ID, CoordinationDB |

**Pattern Implementation with `claude -p`:**
| Pattern | Implementation |
|---------|---------------|
| Swarm | N parallel `claude -p &` processes |
| Jury | N parallel + vote aggregation from output files |
| Pipeline | Sequential `claude -p` calls, pass output as input |
| MapReduce | N mappers parallel, then reducer sequential |
| Hierarchical | Coordinator spawns specialists via `claude -p` |

---

## Executive Summary

This refactor removes the Agentica SDK dependency and replaces it with headless Claude Code agents via `claude -p`. The 11 multi-agent patterns (Swarm, Hierarchical, etc.) will be adapted to spawn Claude Code subagents instead of Agentica agents. CoordinationDB moves to PostgreSQL. Memory system (Core/Archival/Recall) is retained and simplified. Skills and hooks are cleaned up to remove Agentica references.

---

## Agent Routing

> Reference: [00-architecture-decisions.md](./00-architecture-decisions.md) - Agent Roster & Routing Engine

### Routing Engine

**Approach**: Keyword matching + LLM classification fallback

1. **First**: Try keyword match (instant, covers 80% of cases)
2. **Fallback**: LLM classifies (handles edge cases, ~500ms)
3. **NOT erotetic**: Erotetic is for parameter extraction, not routing

### Agent Roster (18 Agents)

| Domain | Agents |
|--------|--------|
| Implement | Kraken, Spark |
| Document | Scribe |
| Debug | Sleuth, Aegis, Profiler |
| Validate | Arbiter, Atlas |
| Research | Oracle, Scout, Pathfinder |
| Plan | Architect, Phoenix |
| Review | Sentinel, Warden |
| Session | Chronicler |
| Deploy | Herald |
| Orchestrate | Maestro |

**Lead agents (can spawn):** Kraken, Architect, Phoenix, Herald, Maestro
**Workers (leaf nodes):** All others - cannot spawn agents

---

## Session Isolation

> Reference: [00-architecture-decisions.md](./00-architecture-decisions.md) - Session Isolation

```python
MAX_AGENTS_PER_SESSION = 4
```

Each session gets an isolated agent pool. No cross-session resource contention.

### Depth Limits

| Depth | Who Can Spawn | Rule |
|-------|---------------|------|
| 0 | Main session | Spawns leads or workers |
| 1 | Leads | Can spawn workers |
| 2 | Leads | Can spawn workers (last level for leads) |
| 3+ | Nobody | Hard reject |

### Explicit Identity

> Reference: [00-architecture-decisions.md](./00-architecture-decisions.md) - Session Identity

**session_id MUST be passed through spawn calls** - never rely on "latest" or "current".

```bash
# CORRECT - explicit identity
claude -p "$PROMPT" --session-id "$SESSION_ID"

# WRONG - race condition
claude -p "$PROMPT"  # Which session?
```

---

## File Inventory

### scripts/agentica_patterns/ (Main Module)

| File | LOC | Status | Action |
|------|-----|--------|--------|
| `__init__.py` | 231 | MODIFY | Remove agentica imports, update exports |
| `patterns.py` | 1986 | MODIFY | Replace `spawn()` with Task tool wrapper |
| `primitives.py` | 565 | KEEP | No agentica deps - Consensus, Aggregator, HandoffState |
| `coordination.py` | 779 | MIGRATE | Move to PostgreSQL (keep SQLite fallback) |
| `task_executor.py` | 711 | MODIFY | Already uses patterns, update spawn calls |
| `claude_proxy.py` | 572 | MODIFY | Update REPL_BASELINE, remove agentica imports |
| `claude_scope.py` | 825 | KEEP | Creates scope for CLI tools - no agentica |
| `memory_service.py` | 459 | KEEP | SQLite-based, no agentica deps |
| `memory_service_pg.py` | 1181 | KEEP | PostgreSQL + pgvector backend (primary) |
| `memory_factory.py` | 548 | MODIFY | Update to prefer PostgreSQL |
| `memory_protocol.py` | 654 | KEEP | Protocol definitions only |
| `tracked_agent.py` | ~200 | MODIFY | Replace agentica spawn with Task tool |
| `websocket_multiplex.py` | 746 | DELETE | Agentica server WebSocket support |
| `postgres_pool.py` | 102 | KEEP | PostgreSQL connection pool |
| `embedding_service.py` | 657 | KEEP | Embedding provider abstraction |
| `beads_task_graph.py` | ~350 | KEEP | DAG task graph - no agentica |
| `resource_pool.py` | ~250 | KEEP | Concurrency control - no agentica |
| `pattern_resolver.py` | 501 | MODIFY | Pattern selection logic - update spawn refs |
| `pattern_inference.py` | 557 | KEEP | LLM-based pattern inference |
| `unified_scope.py` | 970 | KEEP | Tool scope management |
| `unified_gate.py` | 469 | KEEP | Resource gating |
| `dynamic_resources.py` | 657 | KEEP | Dynamic resource management |
| `orchestration_layer.py` | 758 | MODIFY | Update pattern execution |
| `span_processor.py` | 980 | KEEP | Braintrust tracing |
| `session_tree.py` | 504 | KEEP | Session hierarchy tracking |
| `handoff_atom.py` | 548 | KEEP | Atomic handoff operations |
| `agent_handoff.py` | 529 | KEEP | Agent-to-agent handoff logic |
| `agent_scope.py` | ~200 | KEEP | Agent scope management |
| `scope_manager.py` | ~300 | KEEP | Scope lifecycle management |
| `blackboard.py` | ~400 | MODIFY | Update spawn calls |
| `blackboard_research.py` | ~250 | MODIFY | Update spawn calls |
| `reranker.py` | ~350 | KEEP | Result reranking |
| `erotetic_verifier.py` | ~300 | MODIFY | Uses agentica spawn |
| `safe_regex.py` | ~300 | KEEP | Regex utilities |
| `skill_*.py` (6 files) | ~2000 | KEEP | Skill management (no agentica) |
| `watch_agents.py` | 906 | MODIFY | Update agent monitoring |
| `cleanup_orphans.py` | ~200 | KEEP | Orphan cleanup |
| `memory_backfill.py` | 2014 | KEEP | Memory migration utilities |
| `test_*.py` (4 files) | ~500 | DELETE | Agentica-specific tests |
| `*_researcher.py` | ~200 | DELETE | Agentica-specific researchers |
| `run_hierarchical_swarm.py` | ~250 | DELETE | Agentica-specific runner |
| `build_*.py` | ~500 | DELETE | Agentica build scripts |
| `dependency_swarm.py` | ~400 | DELETE | Agentica-specific swarm |
| `research_client.py` | ~350 | DELETE | Agentica research client |
| `refactor_patterns_modular.py` | 493 | DELETE | Completed refactor script |

### scripts/agentica_patterns/patterns/ (Modular Patterns)

| File | Status | Action |
|------|--------|--------|
| `__init__.py` | MODIFY | Update imports |
| `swarm.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `pipeline.py` | KEEP | Uses HandoffState, no spawn |
| `hierarchical.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `jury.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `generator_critic.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `circuit_breaker.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `adversarial.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `chain_of_responsibility.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `map_reduce.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `blackboard.py` | MODIFY | Replace spawn() with task_tool_spawn() |
| `event_driven.py` | MODIFY | Replace spawn() with task_tool_spawn() |

### scripts/agentica_patterns/native_repl/ (Native REPL Experiments)

| File | Status | Action |
|------|--------|--------|
| All files | DELETE | Entire subdirectory - Agentica-specific REPL implementation |

### scripts/agentica_patterns/baseline/ (Baseline Experiments)

| File | Status | Action |
|------|--------|--------|
| All files | DELETE | Entire subdirectory - Agentica comparison baselines |

### .claude/hooks/

| File | Status | Action |
|------|--------|--------|
| `session-start-continuity.sh` | KEEP | Core continuity hook |
| `session-end-cleanup.sh` | KEEP | Cleanup hook |
| `session-end-cleanup-swarms.sh` | MODIFY | Update swarm cleanup for Task tool |
| `pre-compact-continuity.sh` | KEEP | Continuity before compaction |
| `post-tool-use-tracker.sh` | KEEP | Tool tracking |
| `post-tool-use.sh` | KEEP | General post-tool hook |
| `pre-tool-use.sh` | KEEP | General pre-tool hook |
| `pre-tool-use-broadcast.sh` | MODIFY | Update broadcast mechanism |
| `skill-router.sh` | KEEP | Skill routing |
| `skill-activation-prompt.sh` | KEEP | Skill activation |
| `handoff-index.sh` | KEEP | Handoff indexing |
| `session-outcome.sh` | KEEP | Session outcome tracking |
| `subagent-start.sh` | MODIFY | Update for Task tool agents |
| `subagent-stop.sh` | MODIFY | Update for Task tool agents |
| `subagent-start-swarm.sh` | MODIFY | Update for Task tool swarms |
| `subagent-stop-swarm.sh` | MODIFY | Update for Task tool swarms |
| `subagent-stop-continuity.sh` | KEEP | Continuity on stop |
| `stop-coordinator.sh` | MODIFY | Update coordinator logic |
| `stop-swarm-coordinator.sh` | MODIFY | Update swarm coordinator |
| `blackboard-poll.sh` | MODIFY | Update blackboard polling |
| `task-router.sh` | KEEP | Task routing |
| `post-task-complete.sh` | KEEP | Task completion hook |
| `resource-gate.sh` | KEEP | Resource gating |
| `composition-gate.sh` | KEEP | Composition gating |
| `erotetic-clarification.sh` | KEEP | Clarification hook |
| `compiler-in-the-loop*.sh` | KEEP | Compiler hooks |
| `failure-detection.sh` | KEEP | Failure detection |
| `import-error-detector.sh` | KEEP | Import error detection |
| `build.sh` | KEEP | Build hook |

### .claude/skills/agentica-*/

| Skill | Status | Action |
|-------|--------|--------|
| `agentica-sdk/SKILL.md` | DELETE | Documents Agentica SDK |
| `agentica-spawn/SKILL.md` | DELETE | Documents Agentica spawn patterns |
| `agentica-server/SKILL.md` | DELETE | Documents Agentica server |
| `agentica-infrastructure/SKILL.md` | DELETE | Documents Agentica infrastructure |
| `agentica-claude-proxy/SKILL.md` | MODIFY | Update to Task tool patterns |
| `agentica-prompts/SKILL.md` | KEEP | Prompt patterns still valid |

---

## Pattern Migration

| Pattern | Task-Compatible? | Changes Needed |
|---------|-----------------|----------------|
| **Swarm** | YES | Replace `spawn()` with `Task(description=premise, prompt=query)` |
| **Pipeline** | YES | Already uses HandoffState, no spawn |
| **Hierarchical** | YES | Replace `spawn()` for coordinator + specialists |
| **Jury** | YES | Replace `spawn()` for juror agents |
| **GeneratorCritic** | YES | Replace `spawn()` for generator + critic |
| **CircuitBreaker** | YES | Replace `spawn()` for primary + fallback |
| **Adversarial** | YES | Replace `spawn()` for advocate + adversary + judge |
| **ChainOfResponsibility** | YES | Replace `spawn()` for handlers |
| **MapReduce** | YES | Replace `spawn()` for mappers + reducer |
| **Blackboard** | YES | Replace `spawn()` for specialists + controller |
| **EventDriven** | YES | Replace `spawn()` for subscribers |

### Extended HandoffState

> Reference: [00-architecture-decisions.md](./00-architecture-decisions.md) - Handoff Format

The HandoffState dataclass is extended with 5 new fields for v3:

```python
@dataclass
class HandoffState:
    context: str
    next_instruction: str
    artifacts: dict[str, Any]
    metadata: dict[str, Any]
    # NEW FIELDS (v3):
    resolved: list[str]              # Decided propositions
    unknowns: list[str]              # E(X,Q) open questions
    decision_matrix: list[Decision]  # Options with risk/value
    diff: dict[str, str]             # Files created/modified
    spawn_next: str | None           # Agent to hand off to
```

**YAML Frontmatter in Handoffs:**

```yaml
resolved:
  - framework: FastAPI
  - database: PostgreSQL
unknowns:
  - auth_method
  - caching_strategy
decision_matrix:
  - action: add_caching
    options:
      redis: {risk: 0.1, value: 0.9}
      memory: {risk: 0.05, value: 0.6}
diff:
  created: [src/api/routes.py]
  modified: [pyproject.toml]
spawn_next: sentinel
```

### Task Tool Wrapper

Create a `task_tool_spawn()` function that wraps Claude Code's Task tool.

**CRITICAL:** Must set AGENT_ID and SESSION_ID environment variables for coordination.

```python
async def task_tool_spawn(
    premise: str,
    prompt: str,
    scope: dict[str, Any] | None = None,
    model: str | None = None,
    db: CoordinationDB | None = None,
    session_id: str | None = None,  # REQUIRED for coordination
) -> TaskResult:
    """
    Spawn a Claude Code subagent via Task tool.

    Maps Agentica concepts to Task tool:
    - premise -> description (background context)
    - prompt -> prompt (the actual task)
    - scope -> allowedTools (filtered tool list)
    - model -> (not supported, uses default)
    """
    # Generate agent ID for tracking
    agent_id = generate_uuid()

    # Session ID MUST be passed explicitly
    if not session_id:
        session_id = os.environ.get('SESSION_ID')
        if not session_id:
            raise ValueError("session_id required - never rely on 'latest'")

    # Build description from premise
    description = f"You are: {premise}"

    # Build allowed tools from scope
    allowed_tools = ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
    if scope:
        # Add custom tool names
        allowed_tools.extend(scope.keys())

    # Set environment variables for coordination
    env = {
        **os.environ,
        'AGENT_ID': agent_id,
        'SESSION_ID': session_id,
    }

    # Execute via Task tool
    result = await execute_task(
        description=description,
        prompt=prompt,
        allowed_tools=allowed_tools,
        env=env,
    )

    # Track in coordination DB
    if db:
        db.register_agent(
            agent_id=result.task_id,
            premise=premise,
            source="cli",
        )

    return result
```

---

## Database Migration

### CoordinationDB: SQLite to PostgreSQL

**Current State:**
- `coordination.py` uses SQLite with sync operations
- Schema: agents, completed_tasks, artifacts, broadcasts tables

**Migration Steps:**

1. Create `coordination_pg.py` with async PostgreSQL implementation
2. Reuse `postgres_pool.py` for connection management
3. Keep SQLite as fallback for local development
4. Add migration script for existing data

**PostgreSQL Schema:**

```sql
-- Agents table with UUID primary key
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    premise TEXT,
    model TEXT,
    scope_keys JSONB DEFAULT '[]',
    pattern TEXT,
    parent_agent_id UUID REFERENCES agents(id),
    pid INTEGER,
    ppid INTEGER,
    spawned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running',
    error_message TEXT,
    source TEXT  -- 'cli' (Task tool) or NULL
);

CREATE INDEX idx_agents_session ON agents(session_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_pattern ON agents(pattern);

-- Broadcasts for swarm coordination
CREATE TABLE broadcasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    swarm_id TEXT NOT NULL,
    sender_agent UUID NOT NULL,
    broadcast_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_broadcasts_swarm ON broadcasts(swarm_id, created_at);
```

---

## Memory System

### Three-Layer Architecture (KEEP)

1. **Core Memory** - Key-value blocks per session
2. **Archival Memory** - FTS5/GIN indexed long-term storage
3. **Recall Memory** - Cross-source query interface

### Components

| Component | Status | Notes |
|-----------|--------|-------|
| `MemoryService` | KEEP | SQLite implementation (fallback) |
| `MemoryServicePG` | KEEP | PostgreSQL + pgvector (primary) |
| `EmbeddingProvider` | KEEP | Protocol for embeddings |
| `memory_factory.py` | MODIFY | Default to PostgreSQL |

### PostgreSQL Memory Schema (already exists)

```sql
-- Core memory
CREATE TABLE core_memory (
    session_id TEXT NOT NULL,
    agent_id TEXT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (session_id, COALESCE(agent_id, ''), key)
);

-- Archival memory with vector search
CREATE TABLE archival_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    agent_id TEXT,
    content TEXT NOT NULL,
    metadata_json JSONB,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_archival_session ON archival_memory(session_id);
CREATE INDEX idx_archival_embedding ON archival_memory USING ivfflat (embedding vector_cosine_ops);
```

---

## Deletion List

### Safe to Delete Immediately

```
scripts/agentica_patterns/native_repl/           # Entire directory
scripts/agentica_patterns/baseline/              # Entire directory
scripts/agentica_patterns/websocket_multiplex.py # Agentica WebSocket
scripts/agentica_patterns/dependency_swarm.py    # Agentica-specific
scripts/agentica_patterns/research_client.py     # Agentica client
scripts/agentica_patterns/run_hierarchical_swarm.py  # Agentica runner
scripts/agentica_patterns/build_remaining_patterns.py
scripts/agentica_patterns/build_research_coordinator.py
scripts/agentica_patterns/refactor_patterns_modular.py
scripts/agentica_patterns/test_cross_agent.py
scripts/agentica_patterns/test_cross_agent_simple.py
scripts/agentica_patterns/test_persistence.py
scripts/agentica_patterns/mutation_bug_researcher.py
scripts/agentica_patterns/patterns.py.backup
scripts/agentica_patterns/safe_regex.py.bak
scripts/agentica_patterns/examples/              # Example scripts

.claude/skills/agentica-sdk/
.claude/skills/agentica-spawn/
.claude/skills/agentica-server/
.claude/skills/agentica-infrastructure/
```

**Total: ~25 files/directories**

---

## Modification List

### High Priority (Core Pattern Changes)

1. **`patterns.py`** - Replace all `spawn()` calls with `task_tool_spawn()`
   - 22 occurrences of spawn across 11 patterns
   - Each pattern class needs _ensure_* methods updated

2. **`tracked_agent.py`** - Rewrite `tracked_spawn()` to use Task tool
   - Single function, currently wraps agentica spawn
   - Update to call Task tool with tracking

3. **`claude_proxy.py`** - Remove agentica imports, update REPL_BASELINE
   - Remove WebSocket/session registry code
   - Keep OpenAI-compatible API for other uses

4. **`pattern_resolver.py`** - Update pattern instantiation
   - Remove agentica-specific kwargs

### Medium Priority (Pattern Modules)

Each file in `patterns/` needs:
- Remove `from agentica import spawn`
- Add `from scripts.agentica_patterns.task_tool import task_tool_spawn`
- Replace all spawn() calls

Files: `swarm.py`, `hierarchical.py`, `jury.py`, `generator_critic.py`,
       `circuit_breaker.py`, `adversarial.py`, `chain_of_responsibility.py`,
       `map_reduce.py`, `blackboard.py`, `event_driven.py`

### Low Priority (Hooks & Skills)

1. **Swarm hooks** - Update for Task tool subagent model
2. **Subagent hooks** - Update start/stop for Task tool
3. **agentica-claude-proxy skill** - Rewrite for Task tool

---

## New Components

### 1. Task Tool Wrapper (`task_tool.py`)

```python
"""
Task tool wrapper for pattern execution.

Provides task_tool_spawn() as drop-in replacement for agentica spawn().
"""

from dataclasses import dataclass
from typing import Any

@dataclass
class TaskAgent:
    """Wrapper around Task tool result."""
    task_id: str
    description: str

    async def call(self, return_type: type, prompt: str, **kwargs) -> Any:
        """Execute a call to this agent."""
        # Use Task tool to send follow-up
        ...

async def task_tool_spawn(
    premise: str,
    scope: dict[str, Any] | None = None,
    model: str | None = None,  # Ignored for Task tool
    system: str | None = None,
    db: "CoordinationDB | None" = None,
) -> TaskAgent:
    """
    Spawn a Claude Code subagent via Task tool.

    Maps Agentica API to Task tool:
    - premise -> description
    - scope -> allowedTools
    - Returns TaskAgent for chained calls
    """
    ...
```

### 2. PostgreSQL Coordination (`coordination_pg.py`)

Async version of CoordinationDB using asyncpg.

### 3. Pattern Base Class (`patterns/_base.py`)

Abstract base class for patterns with common spawn logic.

---

## Verification Plan

### Phase 1: Unit Tests

```bash
# Run pattern tests (should fail initially)
uv run pytest tests/unit/test_patterns*.py -v

# Run primitives tests (should pass - no changes)
uv run pytest tests/unit/test_primitives.py -v

# Run memory tests
uv run pytest tests/unit/test_memory*.py -v
```

### Phase 2: Integration Tests

```bash
# Test Task tool wrapper
uv run pytest tests/integration/test_task_tool_spawn.py -v

# Test pattern execution with Task tool
uv run pytest tests/integration/test_patterns_task_tool.py -v

# Test CoordinationDB PostgreSQL
uv run pytest tests/integration/test_coordination_pg.py -v
```

### Phase 3: End-to-End Tests

```bash
# Run a Swarm pattern with real Task tool
uv run python scripts/test_swarm_e2e.py

# Run a Hierarchical pattern
uv run python scripts/test_hierarchical_e2e.py

# Verify hooks fire correctly
echo '{"type": "start"}' | .claude/hooks/subagent-start.sh
```

### Phase 4: Manual Verification

1. Start a Claude Code session
2. Run: `/research some topic`
3. Verify subagents spawn via Task tool
4. Check CoordinationDB for agent records
5. Verify memory persistence works

---

## Migration Order

### Week 1: Foundation

1. Create `task_tool.py` wrapper
2. Create `coordination_pg.py`
3. Delete safe-to-delete files
4. Update `__init__.py` exports

### Week 2: Pattern Migration

1. Update `patterns.py` (main file)
2. Update each pattern module
3. Update `tracked_agent.py`
4. Run unit tests

### Week 3: Integration

1. Update hooks for Task tool
2. Update/delete Agentica skills
3. Update orchestration layer
4. Run integration tests

### Week 4: Verification & Cleanup

1. End-to-end testing
2. Fix any remaining issues
3. Update documentation
4. Final cleanup

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Task tool API changes | Low | High | Abstract behind wrapper |
| Pattern behavior differs | Medium | Medium | Comprehensive tests |
| Performance regression | Low | Medium | Benchmark before/after |
| Memory migration issues | Low | High | Keep SQLite fallback |
| Hook compatibility | Medium | Low | Incremental updates |

---

## Success Criteria

1. All 11 patterns work with Task tool
2. No `agentica` imports remain in codebase
3. CoordinationDB works with PostgreSQL
4. Memory system unchanged (three-layer)
5. All existing hooks function correctly
6. Unit tests pass (>90% coverage)
7. Integration tests pass
8. E2E patterns execute successfully
