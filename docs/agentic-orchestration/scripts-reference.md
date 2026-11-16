# Agentic Orchestration Scripts Reference

This document provides a comprehensive reference for all scripts involved in agentic orchestration, including validation, resource tracking, pattern implementation, and testing.

---

## Table of Contents

1. [Core Validation Scripts](#core-validation-scripts)
   - [validate_composition.py](#validate_compositionpy)
2. [Resource Tracking Scripts](#resource-tracking-scripts)
   - [status.sh](#statussh)
   - [get-resources.sh](#get-resourcessh)
3. [Pattern Implementation Scripts](#pattern-implementation-scripts)
   - [patterns.py](#patternspy)
   - [unified_scope.py](#unified_scopepy)
   - [coordination.py](#coordinationpy)
4. [Testing Scripts](#testing-scripts)
   - [test_validate_composition.py](#test_validate_compositionpy)

---

## Core Validation Scripts

### validate_composition.py

**Purpose:** Validates pattern compositions against the formal algebra defined in pattern-algebra.md

**Location:** `scripts/validate_composition.py`

**Usage:**

```bash
# Basic validation
uv run python scripts/validate_composition.py "Pipeline ;[handoff] Jury"

# Show detailed validation trace
uv run python scripts/validate_composition.py --explain "Swarm |[shared] Blackboard"

# Suggest valid compositions between two patterns
uv run python scripts/validate_composition.py --suggest Pipeline Jury

# List all available patterns
uv run python scripts/validate_composition.py --list-patterns

# Output as JSON
uv run python scripts/validate_composition.py --json "Pipeline ;[handoff] Jury"

# Validate structure AND check resource availability
uv run python scripts/validate_composition.py --check-resources "Swarm(10) |[iso] Jury"
```

**CLI Arguments:**

| Flag | Description | Default |
|------|-------------|---------|
| `expression` | Composition to validate (e.g., `"Pipeline ;[handoff] Jury"`) | Required (unless using --list-patterns or --suggest) |
| `--explain` | Show detailed validation trace with scope checks | False |
| `--suggest PATTERN_A PATTERN_B` | Suggest valid compositions between two patterns | - |
| `--list-patterns` | List all patterns and their scope requirements | False |
| `--json` | Output result as JSON | False |
| `--check-resources` | Validate structure AND check resource availability | False |

**Composition Syntax:**

```
Pattern1 <operator>[<scope>] Pattern2
```

**Operators:**
- `;` - Sequential composition (A then B)
- `|` - Parallel composition (A and B concurrently)
- `+` - Choice (A or B)

**Scopes:**
- `iso` - Isolated (no shared state)
- `shared` - Shared context enabled
- `fed` - Federated (cross-agent queries, read-only)
- `handoff` - Sequential state transfer at boundaries

**Key Functions:**

| Function | Description |
|----------|-------------|
| `can_compose(pattern_a, pattern_b, scope, operator)` | Main validation - checks ScopeCompatible, NoDeadlock, TerminationGuarantee, ResourceSafe |
| `parse_composition(expr)` | Parse composition expression into tuples of (pattern_a, operator, scope, pattern_b) |
| `suggest_compositions(pattern_a, pattern_b)` | Return list of valid composition strings between two patterns |
| `scope_compatible(pattern_a, pattern_b, scope)` | Check if both patterns support the given scope |
| `no_deadlock(pattern_a, pattern_b, operator, scope)` | Check for potential deadlock conditions |
| `termination_guarantee(pattern_a, pattern_b, operator)` | Check if composition guarantees termination |
| `resource_safe(pattern_a, pattern_b, operator, scope)` | Check for resource conflicts |
| `check_resources(composition)` | Validate resource availability for composition |
| `count_agents_in_composition(composition)` | Count total agents needed for a composition |
| `suggest_cheaper_composition(composition, max_agents)` | Suggest cheaper alternative if resources insufficient |

**What It Checks (from pattern-algebra.md Section 6):**

1. **ScopeCompatible** - Both patterns must support the specified scope
2. **NoDeadlock** - Detects potential deadlock conditions (e.g., Blackboard with isolated scope in parallel)
3. **TerminationGuarantee** - Warns if patterns have conditional termination
4. **ResourceSafe** - Detects resource conflicts (e.g., two patterns writing to shared state)

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | Composition is valid (and resources available if --check-resources) |
| 1 | Composition is invalid OR resources unavailable |

**Pattern Definitions (14 patterns):**

| Pattern | Supported Scopes | Termination | Primary Op | Agent Count |
|---------|------------------|-------------|------------|-------------|
| Pipeline | handoff | guaranteed | sequential | 1 |
| Swarm | iso, shared | guaranteed | parallel | 5 (default) |
| Jury | iso | guaranteed | parallel | 3 |
| Hierarchical | shared, fed | guaranteed | parallel | 4 |
| Blackboard | shared | conditional | parallel | 3 |
| MapReduce | iso, handoff | guaranteed | parallel | 4 |
| GeneratorCritic | handoff | conditional | sequential | 2 |
| CircuitBreaker | iso, handoff | guaranteed | choice | 1 |
| ChainOfResponsibility | handoff | guaranteed | choice | 2 |
| EventDriven | shared, fed | conditional | sequential | 2 |
| Consensus | shared | conditional | parallel | 3 |
| Aggregator | handoff | guaranteed | sequential | 1 |
| Adversarial | iso, handoff | guaranteed | parallel | 3 |
| Broadcast | shared | guaranteed | parallel | 2 |

**Example:**

```bash
$ uv run python scripts/validate_composition.py --check-resources "Swarm(10) |[iso] Jury"
x STRUCTURAL: Valid composition

x RESOURCES: Need 13 agents, only 6 available (RAM: 4GB free)

  Suggested fallback: Swarm(3) |[iso] Jury
  -> Needs 6 agents, fits within available capacity
```

**Dependencies:**
- Reads from: `/tmp/claude-resources-*.json` (written by status.sh)
- References: `docs/agentic-orchestration/pattern-algebra.md`

---

## Resource Tracking Scripts

### status.sh

**Purpose:** StatusLine generation and resource tracking for Claude Code sessions

**Location:** `.claude/scripts/status.sh`

**Usage:**

```bash
# Called automatically by Claude Code StatusLine hook
# Receives JSON input via stdin with context window info

# Manual test:
echo '{"context_window": {"current_usage": {"input_tokens": 50000}, "context_window_size": 200000}}' | bash .claude/scripts/status.sh
```

**Output Format:**

```
Normal:   145K 72% | main U:6 | ✓ Last done → Current focus
Warning:  145K 72% | main U:6 | RAM:4G Ag:5/8 | ✓ Last → Now
Critical: ⚠ 160K 80% | main U:6 | Current focus
```

**What It Writes:**

| File | Content | Purpose |
|------|---------|---------|
| `/tmp/claude-context-pct-${session_id}.txt` | Context percentage (e.g., `72`) | For hooks to check context usage |
| `/tmp/claude-resources-${session_id}.json` | `{"freeMemMB": N, "activeAgents": N, "maxAgents": N, "contextPct": N}` | For validate_composition.py resource checks |

**Formula for max_agents:**

```bash
# (freeRAM - 2GB safety margin) / 500MB per agent
safety_mb=2048
per_agent_mb=500
max_agents=$(( (free_mem - safety_mb) / per_agent_mb ))

# Clamped to [1, 20]
```

**Key Sections:**

1. **Token Calculation:**
   ```bash
   total_tokens = input_tokens + cache_read + cache_creation + 45000 (system overhead)
   context_pct = total_tokens * 100 / context_size
   ```

2. **Resource Calculation:**
   - Calls `get-resources.sh` for RAM info
   - Queries `CoordinationDB.get_global_running_count()` for active agents
   - Writes combined JSON for downstream hooks

3. **Git Status:**
   - Branch name (truncated to 12 chars)
   - Staged (S), Unstaged (U), Added (A) file counts

4. **Continuity:**
   - Reads from `CONTINUITY_CLAUDE-*.md` ledger files
   - Extracts "Done:" and "Now:" items

**Color Coding:**

| Condition | Color | Display |
|-----------|-------|---------|
| Context < 60% | Green | Normal display |
| Context 60-79% | Yellow | Warning display |
| Context >= 80% | Red | Critical: ⚠ prefix |
| Agent utilization >= 80% | Red | RAM and agent counts |
| Agent utilization 50-79% | Yellow | RAM and agent counts |
| Agent utilization < 50% | Hidden | Not displayed |

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `CLAUDE_PROJECT_DIR` | Project root directory |
| `CLAUDE_SESSION_ID` | Session ID (falls back to `$PPID`) |
| `MOCK_FREE_MEM_MB` | Override free memory for testing |
| `MOCK_ACTIVE_AGENTS` | Override active agent count for testing |

**Dependencies:**
- Reads from: `get-resources.sh`, `CONTINUITY_CLAUDE-*.md`
- Queries: `scripts/agentica_patterns/coordination.py` via `uv run python`
- Writes to: `/tmp/claude-context-pct-*.txt`, `/tmp/claude-resources-*.json`

---

### get-resources.sh

**Purpose:** Cross-platform RAM detection utility for resource management

**Location:** `.claude/scripts/get-resources.sh`

**Usage:**

```bash
# Returns JSON with memory info
bash .claude/scripts/get-resources.sh
# Output: {"freeMemMB": 8192, "totalMemMB": 16384}
```

**Output Format:**

```json
{"freeMemMB": N, "totalMemMB": N}
```

**Platform Handling:**

**macOS:**
```bash
# Uses vm_stat for accurate free memory calculation
# free_pages + inactive_pages + speculative_pages (all reclaimable)
page_size=4096
available_pages=$((free_pages + inactive_pages + speculative_pages))
free_mb=$((available_pages * page_size / 1024 / 1024))
total_mb=$(($(sysctl -n hw.memsize) / 1024 / 1024))
```

**Linux:**
```bash
# Uses /proc/meminfo
# MemAvailable (preferred) or MemFree + Buffers + Cached (fallback)
free_mb=$(grep MemAvailable /proc/meminfo | awk '{print int($2/1024)}')
total_mb=$(grep MemTotal /proc/meminfo | awk '{print int($2/1024)}')
```

**Fallback Values:**
```bash
# If detection fails
free_mb=4096   # 4GB
total_mb=16384 # 16GB
```

**Dependencies:**
- None (standalone utility)

---

## Pattern Implementation Scripts

### patterns.py

**Purpose:** Implements 11 core multi-agent coordination patterns for Agentica

**Location:** `scripts/agentica_patterns/patterns.py`

**Patterns Implemented:**

| Pattern | Class | Description | Supported Scopes |
|---------|-------|-------------|------------------|
| Swarm | `Swarm` | Parallel agents with different perspectives, aggregated results | iso, shared |
| Pipeline | `Pipeline` | Sequential stages passing HandoffState | handoff |
| Hierarchical | `Hierarchical` | Coordinator decomposes tasks for specialists | shared, fed |
| Jury | `Jury` | N independent agents voting via Consensus | iso |
| GeneratorCritic | `GeneratorCritic` | Iterative refinement loop | handoff |
| CircuitBreaker | `CircuitBreaker` | Failure detection with fallback routing | iso, handoff |
| Adversarial | `Adversarial` | Opposing agents debate to stress-test ideas | iso, handoff |
| ChainOfResponsibility | `ChainOfResponsibility` | Route request to first handler that can handle it | handoff |
| MapReduce | `MapReduce` | Fan out to mappers, combine with reducer | iso, handoff |
| Blackboard | `Blackboard` | Specialists contribute to shared state, controller decides completion | shared |
| EventDriven | `EventDriven` | Agents react to events published on a bus | shared, fed |

**Usage Examples:**

```python
from scripts.agentica_patterns.patterns import Swarm, Pipeline, Hierarchical, Jury

# Swarm: Multiple perspectives
swarm = Swarm(
    perspectives=["Security expert", "Performance expert", "UX expert"],
    aggregate_mode=AggregateMode.MERGE
)
result = await swarm.execute("Analyze OAuth implementation")

# Pipeline: Sequential stages
pipeline = Pipeline(stages=[fetch_stage, transform_stage, validate_stage])
result = await pipeline.run(initial_state)

# Hierarchical: Coordinator + specialists
hierarchical = Hierarchical(
    coordinator_premise="You break tasks into subtasks.",
    specialist_premises={"researcher": "You research.", "analyst": "You analyze."}
)
result = await hierarchical.execute("Research and analyze topic X")

# Jury: Voting consensus
jury = Jury(num_jurors=5, consensus_mode=ConsensusMode.MAJORITY)
verdict = await jury.decide(bool, "Is this code safe?")
```

**Key Classes:**

| Class | Key Methods | Description |
|-------|-------------|-------------|
| `Swarm` | `execute(query, return_type)` | Spawn parallel agents, aggregate results |
| `Pipeline` | `run(initial_state)` | Execute sequential stages |
| `Hierarchical` | `execute(task)` | Decompose, delegate, synthesize |
| `Jury` | `decide(return_type, question)` | Collect votes, reach consensus |
| `GeneratorCritic` | `run(task)` | Iterative generate/critique loop |
| `CircuitBreaker` | `execute(query)` | Try primary, fallback on failure |
| `Adversarial` | `debate(question)`, `resolve(question)` | Advocate vs adversary debate |
| `ChainOfResponsibility` | `process(query)` | Route to first matching handler |
| `MapReduce` | `execute(query, chunks)` | Map in parallel, reduce to single result |
| `Blackboard` | `solve(query)` | Specialists contribute to shared state |
| `EventDriven` | `publish(event)` | Dispatch event to matching subscribers |

**CoordinationDB Integration:**

All patterns support optional `db: CoordinationDB` parameter for agent tracking:

```python
from scripts.agentica_patterns.coordination import CoordinationDB

db = CoordinationDB()
swarm = Swarm(perspectives=[...], db=db)

# Agents are automatically registered and tracked
await swarm.execute("...")

# Query running agents
running = db.get_running_agents(pattern="swarm")
```

**Dependencies:**
- `scripts/agentica_patterns/primitives.py` - HandoffState, Aggregator, Consensus
- `scripts/agentica_patterns/tracked_agent.py` - tracked_spawn for CoordinationDB integration
- `agentica` package (optional) - spawn function

---

### unified_scope.py

**Purpose:** Creates unified scope combining Claude file ops, memory, and task operations

**Location:** `scripts/agentica_patterns/unified_scope.py`

**Usage:**

```python
from scripts.agentica_patterns.unified_scope import create_unified_scope, SharedContext

# Basic usage
scope = create_unified_scope(session_id="abc123")
agent = await spawn(premise="...", scope=scope)

# With shared context for multi-agent file cache
shared = SharedContext()
scope = create_unified_scope(session_id="abc123", shared_context=shared)

# With custom database path
scope = create_unified_scope(
    session_id="abc123",
    db_path=Path("/tmp/test.db"),
    enable_memory=True,
    enable_tasks=True
)
```

**Key Functions:**

| Function | Description |
|----------|-------------|
| `create_unified_scope(session_id, ...)` | Main factory - creates scope dict with file/memory/task ops |
| `_create_file_ops(cache_manager, project_dir)` | Create file operations with pluggable cache manager |
| `_create_file_ops_with_shared(shared, ...)` | File ops with SharedContext for multi-agent |
| `_create_file_ops_default(...)` | File ops with LocalCacheManager for single-agent |

**Scope Functions Provided:**

| Category | Functions |
|----------|-----------|
| **File Operations** | `read_file(path)`, `write_file(path, content)`, `edit_file(path, old, new)`, `bash(cmd, args)`, `grep(pattern, path)`, `glob(pattern)` |
| **Memory Operations** | `remember(key, value)`, `recall(query)`, `search_memory(query, limit)`, `store_fact(content)` |
| **Task Operations** | `create_task(desc, blocks)`, `complete_task(task_id)`, `get_ready_tasks()`, `get_all_tasks()` |
| **Debug** | `debug_get_cache()`, `debug_get_operation_log()`, `debug_clear_cache()` |

**Classes:**

| Class | Description |
|-------|-------------|
| `CacheManager` | Protocol for cache/log operations |
| `LocalCacheManager` | Cache manager with local dict storage (not thread-safe, lower overhead) |
| `SharedContext` | Thread-safe cache for multi-agent use (from claude_scope.py) |

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | str | Session identifier for memory/task isolation |
| `db_path` | Path | Custom database path (default: project cache) |
| `enable_memory` | bool | Include memory functions (default: True) |
| `enable_tasks` | bool | Include task functions (default: True) |
| `shared_context` | SharedContext | For multi-agent file cache sharing |
| `extra_scope` | dict | Additional scope items (cannot override built-ins) |
| `project_dir` | str | For path validation |

**Dependencies:**
- `scripts/agentica_patterns/beads_task_graph.py` - BeadsTaskGraph
- `scripts/agentica_patterns/claude_scope.py` - SharedContext, ClaudeResult
- `scripts/agentica_patterns/memory_service.py` - MemoryService

---

### coordination.py

**Purpose:** SQLite-backed coordination database for multi-agent observability

**Location:** `scripts/agentica_patterns/coordination.py`

**Usage:**

```python
from scripts.agentica_patterns.coordination import CoordinationDB, BroadcastType

# Initialize database
db = CoordinationDB(session_id="my-session")

# Register an agent
agent = db.register_agent(
    agent_id="agent-001",
    premise="You are an expert.",
    pattern="swarm",
    parent_agent_id="parent-001",
    pid=12345,
    ppid=1234
)

# Mark agent complete
db.complete_agent("agent-001", status="completed")

# Get running agents
running = db.get_running_agents(pattern="swarm")

# Get global running count (across ALL sessions)
count = db.get_global_running_count()

# Record a task
task = db.record_task(
    agent_id="agent-001",
    input_text="Analyze code",
    output="Analysis complete",
    duration_ms=1500,
    pattern="swarm"
)

# Find orphan agents
orphans = db.find_orphans()

# Broadcast coordination
db.create_broadcast(
    swarm_id="swarm-001",
    sender_agent="agent-001",
    broadcast_type=BroadcastType.FINDING,
    payload={"key": "value"}
)

broadcasts = db.get_broadcasts(swarm_id="swarm-001", since=datetime.now() - timedelta(minutes=5))
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `register_agent(agent_id, ...)` | Register a spawned agent |
| `complete_agent(agent_id, status, error_message)` | Mark agent as completed or failed |
| `record_task(agent_id, input_text, output, ...)` | Record a completed task |
| `get_running_agents(pattern)` | Get running agents for current session |
| `get_all_running_agents(pattern)` | Get running agents across ALL sessions |
| `get_global_running_count()` | Count ALL running agents (for status.sh) |
| `get_all_sessions()` | Get list of all unique session IDs |
| `get_all_sessions_summary()` | Get summary statistics across all sessions |
| `get_completed_tasks(agent_id, limit)` | Get completed tasks |
| `get_session_summary()` | Get summary for current session |
| `find_orphans()` / `get_orphan_candidates()` | Find potential orphan agents |
| `create_broadcast(swarm_id, sender, type, payload)` | Create broadcast message |
| `get_broadcasts(swarm_id, since, exclude_sender, types)` | Get broadcasts for a swarm |

**Database Schema:**

```sql
-- Agents table
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    premise TEXT,
    model TEXT,
    scope_keys TEXT,      -- JSON array
    pattern TEXT,         -- swarm, hierarchical, jury, etc.
    parent_agent_id TEXT, -- For hierarchical patterns
    pid INTEGER,          -- Process ID for orphan detection
    ppid INTEGER,         -- Parent process ID
    spawned_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',  -- running, completed, failed
    error_message TEXT
);

-- Completed tasks table
CREATE TABLE completed_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    pattern TEXT,
    input_summary TEXT,   -- Truncated to 500 chars
    output_summary TEXT,  -- Truncated to 500 chars
    output_type TEXT,
    artifacts TEXT,       -- JSON dict
    duration_ms INTEGER,
    completed_at TEXT NOT NULL
);

-- Broadcasts table (for swarm coordination)
CREATE TABLE broadcasts (
    id TEXT PRIMARY KEY,
    swarm_id TEXT NOT NULL,
    sender_agent TEXT NOT NULL,
    broadcast_type TEXT NOT NULL,  -- finding, question, blocker, done, abort
    payload TEXT NOT NULL,         -- JSON
    created_at TEXT NOT NULL
);
```

**Orphan Detection Tiers:**

| Tier | Condition | Action |
|------|-----------|--------|
| 1 | `ppid == 1` (Unix orphan) | Safe to kill immediately |
| 2 | Parent agent completed/failed, child > 30min old | Kill after grace period |
| 3 | Running > 24h with parent_agent_id set | Kill after timeout |

**BroadcastType Enum:**

| Type | Description |
|------|-------------|
| `FINDING` | Discovered something useful |
| `QUESTION` | Asking other agents |
| `BLOCKER` | Stuck, need help |
| `DONE` | Agent completed its work |
| `ABORT` | Critical failure, abort swarm |

**Database Location:**
```
$CLAUDE_PROJECT_DIR/.claude/cache/agentica-coordination/coordination.db
```

**Dependencies:**
- None (standalone SQLite-backed module)

---

## Testing Scripts

### test_validate_composition.py

**Purpose:** Comprehensive adversarial test suite for validate_composition.py with 123 tests

**Location:** `tests/unit/test_validate_composition.py`

**Usage:**

```bash
# Run all tests
uv run pytest tests/unit/test_validate_composition.py -v

# Run specific test category
uv run pytest tests/unit/test_validate_composition.py::TestValidCompositions -v
uv run pytest tests/unit/test_validate_composition.py::TestAdversarialParsing -v

# Run with coverage
uv run pytest tests/unit/test_validate_composition.py --cov=scripts.validate_composition
```

**Test Categories:**

| Category | Class | Tests | Description |
|----------|-------|-------|-------------|
| 1 | `TestValidCompositions` | ~15 | Valid compositions that should pass |
| 2 | `TestInvalidCompositions` | ~10 | Invalid compositions with specific errors |
| 3 | `TestEdgeCases` | ~12 | Unknown patterns, malformed expressions |
| 4 | `TestDeadlockDetection` | ~5 | Deadlock detection logic |
| 5 | `TestTerminationWarnings` | ~8 | Termination guarantee warnings |
| 6 | `TestSuggestionEngine` | ~7 | Composition suggestion engine |
| 7 | `TestAdversarialParsing` | ~45 | Malicious inputs handling |
| 8 | `TestCompositionChains` | ~3 | Multi-pattern chains |
| 9 | `TestResourceSafety` | ~4 | Resource conflict detection |
| 10 | `TestValidationResultStructure` | ~4 | ValidationResult dataclass |
| 11 | `TestScopeCompatibility` | ~4 | Direct scope_compatible tests |
| 12 | `TestPatternCoverage` | ~2 | Ensure all patterns work |
| 13 | `TestRegressionCases` | ~3 | Previously found bugs |
| 14 | `TestPropertyBased` | ~5 | Hypothesis property tests (optional) |
| 15 | `TestIntegration` | ~3 | Integration-like tests |

**Adversarial Inputs Tested:**

```python
[
    # SQL injection
    "Pipeline'; DROP TABLE patterns; --",
    # Path traversal
    "../../../etc/passwd",
    # Buffer overflow
    "A" * 100000,
    # Null bytes
    "\x00\x01\x02",
    # Unicode attacks
    "\u202EPipeline",  # Right-to-left override
    # Shell injection
    "Pipeline$(whoami)",
    # Format strings
    "%s%s%s%s%s",
    # And ~35 more...
]
```

**Key Test Fixtures:**

```python
@pytest.mark.parametrize(
    "pattern_a,pattern_b,scope,operator",
    [
        ("Pipeline", "Aggregator", ScopeType.HANDOFF, Operator.SEQUENTIAL),
        ("Swarm", "Jury", ScopeType.ISOLATED, Operator.PARALLEL),
        # ... many more
    ],
)
def test_valid_compositions(self, pattern_a, pattern_b, scope, operator):
    result = can_compose(pattern_a, pattern_b, scope, operator)
    assert result.valid
```

**Property-Based Tests (requires hypothesis):**

```python
@given(st.sampled_from(list(PATTERNS.keys())), st.sampled_from(list(PATTERNS.keys())))
def test_suggest_never_crashes(self, pattern_a, pattern_b):
    suggestions = suggest_compositions(pattern_a, pattern_b)
    assert isinstance(suggestions, list)
```

**Dependencies:**
- pytest
- hypothesis (optional, for property-based tests)
- `scripts/validate_composition.py`

---

## Quick Reference: Script Interactions

```
┌─────────────────────────────────────────────────────────────────────┐
│                         StatusLine Display                           │
│                                                                       │
│   145K 72% | main U:6 | RAM:4G Ag:5/8 | ✓ Last → Current             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────┐    ┌─────────────────────┐
│    status.sh        │───▶│  get-resources.sh   │
│                     │    │                     │
│ - Token counting    │    │ - macOS: vm_stat    │
│ - Git status        │    │ - Linux: /proc      │
│ - Continuity ledger │    │                     │
│ - Agent counting    │    │ Output: JSON        │
└─────────────────────┘    └─────────────────────┘
         │                            │
         │                            │
         ▼                            ▼
┌─────────────────────┐    ┌─────────────────────┐
│ coordination.py     │    │ /tmp/claude-        │
│                     │    │ resources-*.json    │
│ - SQLite DB         │    │                     │
│ - Agent tracking    │    │ {freeMemMB,         │
│ - Orphan detection  │    │  activeAgents,      │
│ - Broadcasts        │    │  maxAgents,         │
│                     │    │  contextPct}        │
└─────────────────────┘    └─────────────────────┘
         │                            │
         │                            │
         └────────────┬───────────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │validate_composition │
           │                     │
           │ - Parse expressions │
           │ - Check validity    │
           │ - Resource limits   │
           │ - Suggest fallbacks │
           └─────────────────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │    patterns.py      │
           │                     │
           │ - 11 pattern impl   │
           │ - Agent spawning    │
           │ - Result aggregation│
           └─────────────────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │  unified_scope.py   │
           │                     │
           │ - File operations   │
           │ - Memory operations │
           │ - Task operations   │
           └─────────────────────┘
```

---

## Common Patterns

### Validating Before Spawning

```bash
# Check if composition is valid AND resources available
if uv run python scripts/validate_composition.py --check-resources "Swarm(5) |[iso] Jury"; then
    echo "OK to spawn"
else
    echo "Cannot spawn - check resources or use suggested fallback"
fi
```

### Getting Resource State

```bash
# Get current resource state
cat /tmp/claude-resources-*.json | jq .
# {"freeMemMB": 8192, "activeAgents": 3, "maxAgents": 12, "contextPct": 45}
```

### Tracking Agent Lifecycle

```python
from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.patterns import Swarm

db = CoordinationDB()
swarm = Swarm(perspectives=[...], db=db)

# Before execution
print(f"Running agents: {db.get_global_running_count()}")

# Execute
await swarm.execute("...")

# After execution
summary = db.get_session_summary()
print(f"Session: {summary}")
```
