# Agentic Orchestration Architecture

This document describes the architecture of the agentic orchestration stack, including component interactions, data flows, and design rationale.

---

## 1. System Overview

The orchestration stack consists of three primary subsystems that work together to validate and resource-check multi-agent compositions before launch.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC ORCHESTRATION STACK                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐       │
│  │   Pattern        │    │   Resource       │    │   Coordination   │       │
│  │   Algebra        │    │   Tracking       │    │   Database       │       │
│  │                  │    │                  │    │                  │       │
│  │  pattern-        │    │  status.sh       │    │  coordination.py │       │
│  │  algebra.md      │    │  get-resources   │    │  SQLite/Postgres │       │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘       │
│           │                       │                       │                  │
│           │    ┌──────────────────┴───────────────────────┘                  │
│           │    │                                                             │
│           ▼    ▼                                                             │
│           ┌─────────────────────────────────────────────┐                    │
│           │          validate_composition.py             │                    │
│           │                                              │                    │
│           │  1. Structural validation (algebra rules)    │                    │
│           │  2. Resource validation (capacity check)     │                    │
│           │  3. Fallback suggestions (if over capacity)  │                    │
│           └──────────────────────────────────────────────┘                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Subsystem Responsibilities

| Subsystem | Purpose | Key Files |
|-----------|---------|-----------|
| **Pattern Algebra** | Formal rules for composition validity | `pattern-algebra.md`, `validate_composition.py` |
| **Resource Tracking** | Real-time RAM and agent monitoring | `status.sh`, `get-resources.sh` |
| **Coordination DB** | Persistent agent state across sessions | `coordination.py` |

---

## 2. Data Flow Diagram

The following diagram shows how data flows through the system during a composition validation request.

```
                                                     ┌─────────────────────┐
                                                     │                     │
                                                     │   CoordinationDB    │
                                                     │   (coordination.py) │
                                                     │                     │
                                                     │   Tables:           │
                                                     │   - agents          │
                                                     │   - completed_tasks │
                                                     │   - artifacts       │
                                                     │   - broadcasts      │
                                                     │                     │
                                                     └──────────┬──────────┘
                                                                │
                                                    get_global_running_count()
                                                                │
┌─────────────────┐         ┌─────────────────┐                 ▼
│                 │         │                 │    ┌────────────────────────┐
│  get-resources  │────────▶│    status.sh    │───▶│  /tmp/claude-         │
│  .sh            │  JSON   │                 │    │  resources-{pid}.json │
│                 │         │  Runs every     │    │                        │
│  Cross-platform │         │  StatusLine     │    │  {                     │
│  RAM detection  │         │  hook invocation│    │    "freeMemMB": 8192,  │
│                 │         │                 │    │    "activeAgents": 2,  │
└─────────────────┘         └─────────────────┘    │    "maxAgents": 12,    │
                                                   │    "contextPct": 45    │
                                                   │  }                     │
                                                   └───────────┬────────────┘
                                                               │
                                                   glob("/tmp/claude-resources-*.json")
                                                               │
                                                               ▼
                                               ┌───────────────────────────────┐
                                               │    validate_composition.py     │
                                               │                                │
                                               │  Reads latest resource file    │
                                               │  Counts agents in composition  │
                                               │  Compares needed vs available  │
                                               └───────────────────────────────┘
```

### Data Flow Steps

1. **StatusLine hook runs** (every prompt via Claude Code hooks)
2. **get-resources.sh** detects cross-platform RAM availability
3. **status.sh** queries CoordinationDB for active agent count
4. **status.sh** writes JSON to `/tmp/claude-resources-{session_id}.json`
5. **validate_composition.py** reads latest resource file (on demand)
6. **validate_composition.py** compares composition requirements against available capacity

---

## 3. Validation Pipeline

When an LLM proposes a pattern composition, it passes through two validation stages.

```
LLM proposes composition: "Swarm(5) |[iso] Jury"
                  │
                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         STAGE 1: STRUCTURAL CHECK                       │
│                                                                         │
│  ┌─────────────────────┐                                               │
│  │ ScopeCompatible()   │                                               │
│  │                     │──── ✗ → Error: "Jury requires [iso] scope"    │
│  │ Both patterns must  │                                               │
│  │ support the scope   │                                               │
│  └──────────┬──────────┘                                               │
│             │ ✓                                                         │
│             ▼                                                           │
│  ┌─────────────────────┐                                               │
│  │ NoDeadlock()        │                                               │
│  │                     │──── ✗ → Error: "Blackboard needs [shared]"    │
│  │ Check for circular  │                                               │
│  │ wait conditions     │                                               │
│  └──────────┬──────────┘                                               │
│             │ ✓                                                         │
│             ▼                                                           │
│  ┌─────────────────────┐                                               │
│  │ TerminationGuarantee│                                               │
│  │                     │──── ⚠ → Warning: "Conditional termination"    │
│  │ Will composition    │                                               │
│  │ eventually finish?  │                                               │
│  └──────────┬──────────┘                                               │
│             │ ✓                                                         │
│             ▼                                                           │
│  ┌─────────────────────┐                                               │
│  │ ResourceSafe()      │                                               │
│  │                     │──── ✗ → Error: "Both write to shared state"   │
│  │ No conflicting      │                                               │
│  │ resource access     │                                               │
│  └──────────┬──────────┘                                               │
│             │ ✓                                                         │
└─────────────┴──────────────────────────────────────────────────────────┘
              │
              ▼ VALID
┌────────────────────────────────────────────────────────────────────────┐
│                         STAGE 2: RESOURCE CHECK                         │
│                                                                         │
│  ┌─────────────────────┐                                               │
│  │ Count agents needed │                                               │
│  │                     │                                               │
│  │ Swarm(5) = 5 agents │                                               │
│  │ Jury     = 3 agents │                                               │
│  │ Total    = 8 agents │                                               │
│  └──────────┬──────────┘                                               │
│             │                                                           │
│             ▼                                                           │
│  ┌─────────────────────┐                                               │
│  │ Read resource file  │                                               │
│  │                     │                                               │
│  │ maxAgents: 12       │                                               │
│  │ activeAgents: 5     │                                               │
│  │ available: 7        │                                               │
│  └──────────┬──────────┘                                               │
│             │                                                           │
│             ▼                                                           │
│  ┌─────────────────────────────────────────────────┐                   │
│  │ needed (8) > available (7)?                      │                   │
│  │                                                  │                   │
│  │ YES → Suggest fallback: "Swarm(3) |[iso] Jury"  │                   │
│  │       (3 + 3 = 6 agents, fits within 7)         │                   │
│  │                                                  │                   │
│  │ NO  → Proceed with launch                        │                   │
│  └──────────────────────────────────────────────────┘                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Validation Functions

| Function | Purpose | Located In |
|----------|---------|------------|
| `ScopeCompatible()` | Check both patterns support the scope type | `validate_composition.py` |
| `NoDeadlock()` | Detect circular wait conditions | `validate_composition.py` |
| `TerminationGuarantee()` | Verify composition will eventually finish | `validate_composition.py` |
| `ResourceSafe()` | Check for conflicting resource access | `validate_composition.py` |
| `check_resources()` | Compare agents needed vs available | `validate_composition.py` |

---

## 4. Separation of Concerns

The system deliberately separates **tracking** from **validation**.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   TRACKING (status.sh)              VALIDATION (validate_composition.py) │
│   ────────────────────              ─────────────────────────────────────│
│                                                                          │
│   • Runs every prompt               • Runs on demand                     │
│   • Writes state to /tmp            • Reads state from /tmp              │
│   • Must be fast (<100ms)           • Can be slower (user waits)         │
│   • No user interaction             • Provides feedback to user          │
│   • Side-effect: updates file       • Pure function: file → result       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why This Split?

1. **Performance**: status.sh runs on every prompt. It must be fast (<100ms).
   Validation only runs when the user requests a composition check.

2. **Coupling**: Tracking has no knowledge of pattern algebra.
   It just reports facts: RAM, agent count, context usage.
   Validation interprets those facts against composition requirements.

3. **Testability**: Each component can be tested independently.
   Mock the resource file to test validation without running status.sh.

4. **Extensibility**: New resource types (GPU, network) can be added to tracking
   without changing the validation logic structure.

---

## 5. Pattern Composition Rules

This table shows which scopes are valid for each pattern. Compositions must use
a scope that both patterns support.

```
┌─────────────────────┬─────────────────────────────────────────────────────┐
│     Pattern         │                  Valid Scopes                        │
│                     │   iso    shared    fed    handoff                    │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Pipeline            │    -       -        -        ●     (sequential only) │
│ Swarm               │    ●       ●        -        -     (parallel, any)   │
│ Jury                │    ●       -        -        -     (must be isolated)│
│ Hierarchical        │    -       ●        ●        -     (coordinator sees)│
│ Blackboard          │    -       ●        -        -     (shared board)    │
│ MapReduce           │    ●       -        -        ●     (parallel map)    │
│ GeneratorCritic     │    -       -        -        ●     (iterative loop)  │
│ CircuitBreaker      │    ●       -        -        ●     (fallback routing)│
│ ChainOfResponsibility│   -       -        -        ●     (cascade)         │
│ EventDriven         │    -       ●        ●        -     (shared bus)      │
│ Consensus           │    -       ●        -        -     (agreement)       │
│ Aggregator          │    -       -        -        ●     (collect results) │
│ Adversarial         │    ●       -        -        ●     (debate + judge)  │
│ Broadcast           │    -       ●        -        -     (one-to-many)     │
└─────────────────────┴─────────────────────────────────────────────────────┘

Legend:
  ●  = Scope supported
  -  = Scope not supported (composition with this scope will fail validation)
```

### Scope Definitions

| Scope | Abbreviation | Meaning |
|-------|--------------|---------|
| **Isolated** | `iso` | No shared state between agents. Each runs independently. |
| **Shared** | `shared` | All agents see the same mutable state. Requires synchronization. |
| **Federated** | `fed` | Cross-agent queries allowed (read-only). No writes. |
| **Handoff** | `handoff` | State transferred at boundaries. Sequential ownership. |

---

## 6. Resource Formula

The system calculates maximum concurrent agents from available RAM.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RESOURCE FORMULA                                 │
│                                                                          │
│   max_agents = (free_ram_mb - 2048) / 500                               │
│                                                                          │
│   Where:                                                                 │
│     free_ram_mb  = Available RAM in megabytes (from get-resources.sh)   │
│     2048         = Safety buffer (2GB reserved for system + Claude)      │
│     500          = Memory per agent (estimated 500MB per Claude process) │
│                                                                          │
│   Clamped to range [1, 20]                                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Example Calculations

| System RAM | Free RAM | Safety Buffer | Per Agent | Max Agents |
|------------|----------|---------------|-----------|------------|
| 8 GB       | 4 GB     | 2 GB          | 500 MB    | 4          |
| 16 GB      | 10 GB    | 2 GB          | 500 MB    | 16         |
| 32 GB      | 20 GB    | 2 GB          | 500 MB    | 20 (capped)|
| 4 GB       | 2 GB     | 2 GB          | 500 MB    | 1 (minimum)|

### Why These Constants?

- **2GB Safety Buffer**: Claude Code itself, the shell, and background processes
  need RAM. Leaving 2GB ensures the system remains responsive.

- **500MB Per Agent**: Based on empirical measurements of Claude subprocess memory
  usage. Each agent spawns a claude CLI process with its own context window.

- **Max 20 Agents**: Practical limit for coordination overhead. Beyond 20 agents,
  synchronization and context management become bottlenecks.

---

## 7. File Locations

```
.claude/
├── scripts/
│   ├── status.sh                  # StatusLine hook - writes resource state
│   └── get-resources.sh           # Cross-platform RAM detection utility
│
├── cache/
│   └── agentica-coordination/
│       └── coordination.db        # SQLite database for agent tracking
│
└── hooks/
    └── ...                        # Hook registrations (settings.json)

scripts/
├── validate_composition.py        # Main validation CLI
├── validate_resources.py          # Resource-only validation (subset)
│
└── agentica_patterns/
    ├── coordination.py            # CoordinationDB class
    ├── patterns.py                # Pattern implementations (Swarm, Jury, etc.)
    ├── unified_scope.py           # Scope management (file + memory + task ops)
    ├── primitives.py              # HandoffState, Aggregator, Consensus
    └── ...                        # Additional pattern support

docs/agentic-orchestration/
├── README.md                      # Overview and quick start
├── pattern-algebra.md             # Formal specification (technical)
├── pattern-algebra-for-humans.md  # Layman's explanation
├── architecture.md                # This document
└── scripts-reference.md           # Script documentation

/tmp/
└── claude-resources-{session_id}.json   # Runtime resource state (ephemeral)
```

### Key Paths

| Path | Purpose | Lifetime |
|------|---------|----------|
| `/tmp/claude-resources-*.json` | Runtime resource state | Session (cleared on reboot) |
| `.claude/cache/agentica-coordination/coordination.db` | Agent history | Persistent |
| `scripts/validate_composition.py` | Validation entry point | Static |
| `.claude/scripts/status.sh` | StatusLine hook | Static |

---

## 8. Component Interactions

### Sequence: User Requests Composition Validation

```
User                   Claude Code              status.sh          validate_composition.py
  │                         │                       │                        │
  │  "validate Swarm(5) → Jury"                     │                        │
  ├────────────────────────▶│                       │                        │
  │                         │                       │                        │
  │                         │ (StatusLine runs)     │                        │
  │                         ├──────────────────────▶│                        │
  │                         │                       │                        │
  │                         │  get_global_running_count()                    │
  │                         │                       ├────────────────────────┤
  │                         │                       │         (reads DB)     │
  │                         │                       │◀───────────────────────┤
  │                         │                       │                        │
  │                         │  write /tmp/claude-resources-*.json            │
  │                         │◀──────────────────────│                        │
  │                         │                       │                        │
  │                         │ invoke validation script                       │
  │                         ├───────────────────────────────────────────────▶│
  │                         │                                                │
  │                         │                   read /tmp/claude-resources-*.json
  │                         │                                                │
  │                         │                   parse "Swarm(5) → Jury"      │
  │                         │                   check structural validity    │
  │                         │                   check resource availability  │
  │                         │                                                │
  │                         │◀───────────────────────────────────────────────┤
  │                         │  ValidationResult { valid: true/false, ... }   │
  │                         │                                                │
  │◀────────────────────────│                                                │
  │  "Valid composition,                                                     │
  │   8 agents needed,                                                       │
  │   7 available"                                                           │
```

### Sequence: Agent Registration and Orphan Detection

```
spawn()                 CoordinationDB              find_orphans()
   │                         │                           │
   │  register_agent()       │                           │
   ├────────────────────────▶│                           │
   │                         │                           │
   │                         │  INSERT INTO agents       │
   │                         │  (id, session_id, pid,    │
   │                         │   ppid, pattern, ...)     │
   │                         │                           │
   │◀────────────────────────│                           │
   │  AgentRecord            │                           │
   │                         │                           │
   │       ... time passes, session ends ...             │
   │                         │                           │
   │                         │  SessionEnd hook triggers │
   │                         │◀──────────────────────────┤
   │                         │                           │
   │                         │  find_orphans()           │
   │                         │                           │
   │                         │  Tier 1: ppid == 1        │
   │                         │  Tier 2: parent completed │
   │                         │  Tier 3: running > 24h    │
   │                         │                           │
   │                         ├──────────────────────────▶│
   │                         │  OrphanCandidate[]        │
```

---

## 9. Design Decisions

### Why SQLite for CoordinationDB?

- **Concurrency**: SQLite handles concurrent readers and serialized writers.
  Multiple agents can query the DB; writes are rare (spawn/complete events).

- **Simplicity**: No separate database server to manage. DB file lives in project.

- **Portability**: Works on macOS, Linux, Windows without additional dependencies.

- **Migration Path**: Schema includes migrations for forward compatibility.
  PostgreSQL support available via `memory_service_pg.py` for production deployments.

### Why /tmp for Resource State?

- **Ephemeral**: Resource state is session-scoped. No need to persist across reboots.

- **Cross-Process**: status.sh (bash) writes; validate_composition.py (Python) reads.
  File system is the universal IPC mechanism.

- **Per-Session**: Using `{session_id}` in filename prevents conflicts when
  multiple Claude Code instances run simultaneously.

### Why Two-Stage Validation?

- **Fail Fast**: Structural errors are caught before resource checking.
  No point checking resources for an invalid composition.

- **Clear Errors**: Users see exactly what failed: "scope incompatible" vs
  "insufficient agents." Different remediation for each.

- **Composability**: Structural validation is pure (no side effects).
  Resource checking reads external state. Keeping them separate makes testing easier.

---

## 10. Extension Points

### Adding a New Pattern

1. Add pattern definition to `PATTERNS` dict in `validate_composition.py`
2. Add agent count to `PATTERN_AGENT_COUNTS` dict
3. Implement pattern class in `scripts/agentica_patterns/patterns.py`
4. Update pattern algebra doc if new scope requirements

### Adding a New Resource Type

1. Extend `get-resources.sh` to detect the resource (e.g., GPU memory)
2. Update status.sh to include in JSON output
3. Extend `ResourceCheckResult` in `validate_composition.py`
4. Add resource calculation formula

### Adding a New Scope Type

1. Add to `ScopeType` enum in `validate_composition.py`
2. Update `PATTERNS` dict with which patterns support it
3. Add scope semantics to pattern-algebra.md
4. Update composition table in this document

---

## 11. Related Documents

| Document | Description |
|----------|-------------|
| [pattern-algebra.md](pattern-algebra.md) | Formal mathematical specification |
| [pattern-algebra-for-humans.md](pattern-algebra-for-humans.md) | Accessible explanation |
| [README.md](README.md) | Quick start and overview |
| [scripts-reference.md](scripts-reference.md) | Detailed script documentation |
