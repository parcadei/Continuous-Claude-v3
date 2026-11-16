# Architecture: Dynamic Resource Limits & Orphan Detection

## System Overview

The Dynamic Resource Limits and Orphan Detection system provides intelligent agent lifecycle management for Claude Code's multi-agent orchestration patterns. It operates at three levels: preventing overload before it happens (PreToolUse hard limits), warning operators as resources deplete (UserPromptSubmit soft advisories), and cleaning up abandoned agents post-session (SessionEnd cleanup and orphan detection).

The architecture builds on Claude Code's hook system, combining TypeScript hooks for fast in-process decisions with Python coordination infrastructure for persistent state tracking. Resource state flows from a shell-based StatusLine through temp files, consumed by TypeScript hooks at prompt and tool boundaries. Agent lifecycle data persists in SQLite, enabling cross-session visibility and three-tier orphan classification.

This design prioritizes fail-open semantics: if any component fails (missing database, corrupt temp file, hook error), the system defaults to allowing operations rather than blocking. This ensures developer productivity isn't interrupted by infrastructure failures while still providing protection when the system is healthy.

## Component Diagram

```
                          ┌─────────────────────────────────────────────────────────────────────┐
                          │                       Claude Code CLI                                │
                          ├─────────────────────────────────────────────────────────────────────┤
                          │                                                                     │
                          │  ┌─────────────────────────────────────────────────────────────┐   │
                          │  │                    StatusLine (status.sh)                    │   │
                          │  │  Writes: /tmp/claude-resources-{sessionId}.json              │   │
                          │  │  Fields: freeMemMB, activeAgents, maxAgents, contextPct      │   │
                          │  └─────────────────────────────────────────────────────────────┘   │
                          │                              │                                      │
                          │                              ▼                                      │
┌─────────────────────────┴──────────────────────────────────────────────────────────────────────┴┐
│                                         Hooks Layer                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  ┌──────────────────────────┐  ┌───────────────────────────┐  ┌────────────────────────────┐   │
│  │      PreToolUse          │  │    UserPromptSubmit       │  │      SessionEnd            │   │
│  │    (Hard Limit Block)    │  │    (Soft Advisory)        │  │    (Cleanup/Orphan)        │   │
│  ├──────────────────────────┤  ├───────────────────────────┤  ├────────────────────────────┤   │
│  │ pre-tool-use.ts          │  │ skill-activation-prompt.ts│  │ session-end-cleanup.ts     │   │
│  │                          │  │                           │  │ session-end-cleanup-       │   │
│  │ On tool_name="Task":     │  │ Reads:                    │  │   swarms.ts                │   │
│  │ 1. Read resource state   │  │ - Resource state JSON     │  │                            │   │
│  │ 2. Check activeAgents    │  │ - Context % temp file     │  │ Triggers:                  │   │
│  │    >= maxAgents          │  │                           │  │ - braintrust_analyze.py    │   │
│  │ 3. If true: BLOCK        │  │ Emits warnings:           │  │   --learn                  │   │
│  │ 4. Else: CONTINUE        │  │ - 80%+: WARNING           │  │                            │   │
│  │                          │  │ - 100%: CRITICAL          │  │ Cleans:                    │   │
│  └──────────────────────────┘  └───────────────────────────┘  │ - Stale agent cache        │   │
│              │                             │                   │ - Updates ledger timestamp │   │
│              │                             │                   └────────────────────────────┘   │
│              │                             │                              │                      │
│              ▼                             ▼                              ▼                      │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           Shared TypeScript Modules                                       │   │
│  ├──────────────────────────────────────────────────────────────────────────────────────────┤   │
│  │  shared/resource-reader.ts     shared/resource-utils.ts     shared/db-utils.ts           │   │
│  │  ┌────────────────────┐       ┌────────────────────┐       ┌────────────────────┐        │   │
│  │  │ readResourceState()│       │ getSystemResources()│       │ getDbPath()        │        │   │
│  │  │ getSessionId()     │       │ - freeRAM          │       │ getActiveAgentCount│        │   │
│  │  │ ResourceState:     │       │ - totalRAM         │       │ queryDb()          │        │   │
│  │  │  - freeMemMB       │       │ - cpuCores         │       │ runPythonQuery()   │        │   │
│  │  │  - activeAgents    │       │ - loadAvg          │       │                    │        │   │
│  │  │  - maxAgents       │       │                    │       │                    │        │   │
│  │  │  - contextPct      │       │ (Node.js os module)│       │ (Python subprocess)│        │   │
│  │  └────────────────────┘       └────────────────────┘       └────────────────────┘        │   │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                   SubagentStart / SubagentStop                                   │
│  ┌────────────────────────────────────────────────────────────────────────────────────────┐     │
│  │  subagent-start.ts                          subagent-stop.ts                            │     │
│  │  - Registers agent in CoordinationDB        - Marks agent completed/failed             │     │
│  │  - Records pid/ppid for orphan detection    - Updates status, error_message            │     │
│  │  - Sets pattern, parent_agent_id            - Calculates duration_ms                   │     │
│  └────────────────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                Python Coordination Layer                                          │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                            coordination.py - CoordinationDB                                │  │
│  ├───────────────────────────────────────────────────────────────────────────────────────────┤  │
│  │  SQLite: .claude/cache/agentica-coordination/coordination.db                              │  │
│  │                                                                                           │  │
│  │  Tables:                      Methods:                                                    │  │
│  │  ┌─────────────────┐          ┌────────────────────────────────────────┐                 │  │
│  │  │ agents          │          │ register_agent(agent_id, pid, ppid,    │                 │  │
│  │  │ - id            │          │   pattern, parent_agent_id, ...)       │                 │  │
│  │  │ - session_id    │          │ complete_agent(agent_id, status, err)  │                 │  │
│  │  │ - pattern       │          │ get_running_agents(pattern)            │                 │  │
│  │  │ - parent_agent_id│         │ get_all_running_agents(pattern)        │                 │  │
│  │  │ - pid, ppid     │          │ get_global_running_count()             │                 │  │
│  │  │ - spawned_at    │          │ find_orphans() -> OrphanCandidate[]    │                 │  │
│  │  │ - status        │          └────────────────────────────────────────┘                 │  │
│  │  └─────────────────┘                                                                      │  │
│  │  ┌─────────────────┐          OrphanCandidate dataclass:                                 │  │
│  │  │ broadcasts      │          - agent_id, ppid, parent_agent_id                          │  │
│  │  │ - swarm_id      │          - spawned_at, tier (1/2/3), reason                         │  │
│  │  │ - sender_agent  │                                                                      │  │
│  │  │ - broadcast_type│                                                                      │  │
│  │  │ - payload       │                                                                      │  │
│  │  └─────────────────┘                                                                      │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                  │
│  ┌───────────────────────────────────────┐  ┌───────────────────────────────────────────────┐  │
│  │ watch_agents.py                        │  │ cleanup_orphans.py                            │  │
│  ├───────────────────────────────────────┤  ├───────────────────────────────────────────────┤  │
│  │ Real-time agent monitoring:            │  │ Three-tier orphan cleanup:                    │  │
│  │ - Rich table/progress visualization    │  │                                               │  │
│  │ - Pattern-aware visualizers:           │  │ Tier 1: ppid=1 (Unix orphan)                  │  │
│  │   ParallelVisualizer (swarm/jury)      │  │   -> Kill immediately                         │  │
│  │   SequentialVisualizer (pipeline)      │  │                                               │  │
│  │   HierarchicalVisualizer (tree)        │  │ Tier 2: parent_agent dead + 30min old         │  │
│  │ - is_unix_orphan(pid) detection        │  │   -> Kill after grace period                  │  │
│  │ - find_claude_processes()              │  │                                               │  │
│  │ - Log tailing (agent-*.log)            │  │ Tier 3: Running >24h                          │  │
│  │ - --all-sessions cross-session view    │  │   -> Kill after timeout                       │  │
│  └───────────────────────────────────────┘  │                                               │  │
│                                              │ CLI: --dry-run (default), --kill, --tier N   │  │
│                                              └───────────────────────────────────────────────┘  │
│                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Resource State Flow

```
┌─────────────────┐    writes     ┌────────────────────────────────────────┐
│   status.sh     │ ────────────► │ /tmp/claude-resources-{sessionId}.json │
│  (StatusLine)   │               │                                        │
│                 │               │ {                                      │
│ Runs on each    │               │   "freeMemMB": 8192,                   │
│ prompt display  │               │   "activeAgents": 3,                   │
└─────────────────┘               │   "maxAgents": 10,                     │
                                  │   "contextPct": 45                     │
                                  │ }                                      │
                                  └────────────────────────────────────────┘
                                               │
                    ┌──────────────────────────┴──────────────────────────┐
                    │                                                      │
                    ▼                                                      ▼
        ┌───────────────────────┐                          ┌────────────────────────────┐
        │ PreToolUse Hook       │                          │ UserPromptSubmit Hook      │
        │ (pre-tool-use.ts)     │                          │ (skill-activation-prompt)  │
        │                       │                          │                            │
        │ if tool_name=="Task": │                          │ Check utilization:         │
        │   state = read()      │                          │   80%+ -> WARNING          │
        │   if active >= max:   │                          │  100%  -> CRITICAL         │
        │     return {          │                          │                            │
        │       result: "block",│                          │ Add to system message      │
        │       reason: "..."   │                          └────────────────────────────┘
        │     }                 │
        └───────────────────────┘
```

### Agent Lifecycle Flow

```
┌─────────────────┐   SubagentStart    ┌─────────────────────────────────────┐
│   Task tool     │ ─────────────────► │ CoordinationDB.register_agent()     │
│   invocation    │                    │                                     │
│                 │                    │ INSERT INTO agents (                │
│                 │                    │   id, session_id, pattern,          │
│                 │                    │   parent_agent_id, pid, ppid,       │
└─────────────────┘                    │   spawned_at, status='running'      │
                                       │ )                                   │
                                       └─────────────────────────────────────┘
                                                         │
                                                         │ Agent executes...
                                                         │
                                                         ▼
┌─────────────────┐   SubagentStop     ┌─────────────────────────────────────┐
│ Agent completes │ ─────────────────► │ CoordinationDB.complete_agent()     │
│ or fails        │                    │                                     │
│                 │                    │ UPDATE agents SET                   │
│                 │                    │   status = 'completed'/'failed',    │
└─────────────────┘                    │   completed_at = NOW(),             │
                                       │   error_message = ...               │
                                       └─────────────────────────────────────┘
```

### Orphan Detection Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          find_orphans() Query                               │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Tier 1 (Unix Orphan):                                                     │
│  SELECT * FROM agents WHERE status='running' AND ppid=1                    │
│  Reason: Parent process died, init adopted child                           │
│  Action: Kill immediately                                                  │
│                                                                            │
│  Tier 2 (Parent Agent Dead):                                               │
│  SELECT a.* FROM agents a                                                  │
│  JOIN agents p ON a.parent_agent_id = p.id                                 │
│  WHERE a.status='running' AND p.status != 'running'                        │
│    AND a.spawned_at < (NOW - 30 minutes)                                   │
│  Reason: Parent agent completed/failed, child still running                │
│  Action: Kill after 30min grace period                                     │
│                                                                            │
│  Tier 3 (App Orphan):                                                      │
│  SELECT * FROM agents                                                      │
│  WHERE status='running' AND parent_agent_id IS NOT NULL                    │
│    AND spawned_at < (NOW - 24 hours)                                       │
│  Reason: Running too long without completion                               │
│  Action: Kill after 24h timeout                                            │
│                                                                            │
│  EXCLUSION: Agents with parent_agent_id IS NULL AND ppid != 1              │
│  (Main sessions are never considered orphans)                              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## Code Map

### TypeScript Hooks (`.claude/hooks/src/`)

| File | Purpose | Key Exports |
|------|---------|-------------|
| `pre-tool-use.ts` | Hard limit enforcement on Task tool | Pattern router, resource check, blocks when at limit |
| `skill-activation-prompt.ts` | Soft advisory on user prompts | Resource warnings (80%/100%), context warnings |
| `session-end-cleanup.ts` | Session cleanup, learnings extraction | Ledger update, cache cleanup, braintrust trigger |
| `session-end-cleanup-swarms.ts` | Swarm-specific cleanup | Broadcasts cleanup, swarm state finalization |
| `subagent-start.ts` | Agent registration | Records pid/ppid, pattern, parent_agent_id |
| `subagent-stop.ts` | Agent completion | Updates status, calculates duration |

### Shared Modules (`.claude/hooks/src/shared/`)

| File | Purpose | Key Exports |
|------|---------|-------------|
| `resource-reader.ts` | Resource state JSON reader | `readResourceState()`, `ResourceState`, `DEFAULT_RESOURCE_STATE` |
| `resource-utils.ts` | System resource queries | `getSystemResources()`, `SystemResources` |
| `db-utils.ts` | SQLite query utilities | `getDbPath()`, `getActiveAgentCount()`, `runPythonQuery()` |
| `types.ts` | Shared type definitions | `PreToolUseInput`, `HookOutput`, `QueryResult` |
| `pattern-router.ts` | Pattern detection | `detectPattern()`, `isValidId()`, `SAFE_ID_PATTERN` |

### Python Scripts (`scripts/agentica/`)

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `coordination.py` | SQLite coordination database | `CoordinationDB`, `AgentRecord`, `OrphanCandidate`, `BroadcastRecord` |
| `watch_agents.py` | Real-time agent monitoring | `is_unix_orphan()`, `SubprocessMonitor`, pattern-aware visualizers |
| `cleanup_orphans.py` | Orphan agent cleanup CLI | `cleanup_orphans()`, `kill_process()`, three-tier detection |

## File Index

| Path | Purpose |
|------|---------|
| `.claude/settings.json` | Hook registration, matchers, timeouts |
| `.claude/hooks/pre-tool-use.sh` | Shell wrapper for pre-tool-use.ts |
| `.claude/hooks/src/pre-tool-use.ts` | Hard limit enforcement (Phase 6) |
| `.claude/hooks/src/skill-activation-prompt.ts` | Soft limit advisory (Phase 5) |
| `.claude/hooks/src/session-end-cleanup.ts` | Session cleanup triggers |
| `.claude/hooks/src/shared/resource-reader.ts` | Resource state JSON reader (Phase 4) |
| `.claude/hooks/src/shared/resource-utils.ts` | System resource queries (Phase 1) |
| `.claude/hooks/src/shared/db-utils.ts` | Database utilities (Phase 2) |
| `.claude/hooks/src/shared/types.ts` | Shared TypeScript types |
| `.claude/hooks/src/subagent-start.ts` | Agent registration hook |
| `.claude/hooks/src/subagent-stop.ts` | Agent completion hook |
| `scripts/agentica/coordination.py` | CoordinationDB class (Phase 7) |
| `scripts/agentica/watch_agents.py` | Agent monitoring CLI (Phase 8) |
| `scripts/agentica/cleanup_orphans.py` | Orphan cleanup CLI (Phase 9) |
| `/tmp/claude-resources-{sessionId}.json` | Runtime resource state (Phase 3) |
| `.claude/cache/agentica-coordination/coordination.db` | SQLite coordination database |

## Key Interfaces

### ResourceState (TypeScript)

```typescript
interface ResourceState {
  freeMemMB: number;      // Available RAM in MB
  activeAgents: number;   // Currently running agents
  maxAgents: number;      // Maximum allowed agents
  contextPct: number;     // Context window usage (0-100)
}
```

### OrphanCandidate (Python)

```python
@dataclass
class OrphanCandidate:
    agent_id: str
    ppid: int | None
    parent_agent_id: str | None
    spawned_at: datetime
    tier: int           # 1=Unix orphan, 2=parent dead, 3=app orphan
    reason: str
```

### HookOutput (TypeScript)

```typescript
interface HookOutput {
  result: 'continue' | 'block';
  message?: string;      // System message to inject
  reason?: string;       // Reason for blocking
}
```

## Design Principles

1. **Fail-Open**: All components default to allowing operations on error
2. **No Hot-Path LLMs**: Resource checks use file/database reads, not AI
3. **Explicit Identity**: Session IDs passed explicitly, never "most recent"
4. **Tiered Severity**: Warnings escalate (70% -> 80% -> 100%) before blocks
5. **Cross-Session Visibility**: Coordination DB tracks all sessions
6. **Graceful Degradation**: Missing files/tables return safe defaults
