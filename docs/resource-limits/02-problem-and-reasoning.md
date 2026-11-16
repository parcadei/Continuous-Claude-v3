# Problem Statement & Design Reasoning

This document explains why the Resource Limits and Orphan Detection system was built and the rationale behind key design decisions.

---

## The Problems

### 1. Unbounded Process Spawning

When Claude Code spawns sub-agents via the `Task` tool, each agent runs as a separate process consuming significant resources:

- **Memory consumption**: Each Claude Code instance consumes 400-600MB of RAM
- **Unbounded spawning**: Without limits, a hierarchical pattern could spawn 20+ agents
- **OOM risk**: On a 16GB laptop, spawning 30 agents exhausts available memory
- **System instability**: Memory pressure causes swapping, degrading performance for all processes

The core issue is that the `Task` tool has no awareness of system resources. Users on machines with 128GB RAM can safely run many agents, while users on 8GB machines can only run a few. A fixed limit would be either too restrictive or too permissive.

### 2. Orphaned Processes

Agent processes can become orphaned in several ways:

| Scenario | Cause | Result |
|----------|-------|--------|
| User presses Ctrl+C | Graceful interrupt | Parent may not clean up children |
| User runs `kill -9` | Force kill | No cleanup hooks run at all |
| Parent crashes | Unexpected error | Children continue running indefinitely |
| Network timeout | Claude API issue | Agent hangs, never completes |
| User closes terminal | Session ends | Background processes persist |

Orphaned processes:
- Continue consuming RAM (500MB each)
- Hold database locks (SQLite coordination DB)
- Appear in `watch_agents.py` as "running" indefinitely
- Accumulate over time, degrading system performance

The challenge is distinguishing between:
1. Legitimately long-running agents
2. Truly orphaned processes that should be killed
3. Main sessions that should never be killed

### 3. No Visibility

Before this system, users had no way to see:

- How many agents were currently running
- How much RAM was available for new agents
- Which agents might be orphaned
- Whether they were approaching resource limits

This led to:
- Accidentally spawning too many agents
- OOM errors with no warning
- Orphaned processes going unnoticed
- Manual investigation needed to debug resource issues

---

## Design Decisions

### Why Dynamic Limits (Not Static)

**Problem**: A static limit (e.g., "max 10 agents") fails on diverse hardware.

**Solution**: Calculate limits dynamically from available RAM using a formula:

```
maxAgents = (freeRAM - safetyBuffer) / perAgentMB
         = (freeRAM - 2GB) / 500MB
```

| Machine | Free RAM | Safety Buffer | Per Agent | Max Agents |
|---------|----------|---------------|-----------|------------|
| 8GB laptop | 6GB | 2GB | 500MB | 8 |
| 16GB desktop | 12GB | 2GB | 500MB | 20 (capped) |
| 128GB server | 100GB | 2GB | 500MB | 20 (capped) |

**Rationale**:
- **2GB safety buffer**: Leaves room for OS, Claude Code main process, and other apps
- **500MB per agent**: Conservative estimate based on observed Claude Code memory usage
- **20 agent cap**: Prevents excessive parallelism regardless of RAM (diminishing returns)
- **1 agent minimum**: Always allow at least one agent even on constrained systems

**Why not use process memory limits (ulimit)?**
Process-level limits would kill agents without warning. Our approach warns first (soft limit) and only blocks at the threshold (hard limit).

### Why Three-Tier Orphan Detection

Different orphan scenarios require different handling:

| Tier | Condition | Grace Period | Rationale |
|------|-----------|--------------|-----------|
| **1** | `ppid=1` (Unix orphan) | None | Parent definitely dead; process reparented to init |
| **2** | Parent agent status != 'running' | 30 minutes | Parent completed/failed; child may still be finishing work |
| **3** | No done broadcast in 24h | 24 hours | Could be legitimately long-running; give ample time |

**Tier 1 - Unix Orphans (Immediate)**

When a Unix process's parent dies, the kernel reparents it to PID 1 (init or launchd). This is unambiguous: the parent is definitely gone. These are safe to kill immediately.

```sql
SELECT * FROM agents WHERE status = 'running' AND ppid = 1
```

**Tier 2 - Application Orphans (30 min grace)**

When a parent agent completes or fails in our coordination DB, child agents should ideally complete shortly after. The 30-minute grace period handles:
- Slow network responses finishing
- Final artifact writes completing
- Graceful shutdown sequences

```sql
SELECT a.* FROM agents a
JOIN agents p ON a.parent_agent_id = p.id
WHERE a.status = 'running' AND p.status != 'running'
  AND a.spawned_at < datetime('now', '-30 minutes')
```

**Tier 3 - Stale Agents (24h timeout)**

Some agents may simply hang without crashing. The 24-hour timeout is conservative because:
- Legitimate research swarms can run for hours
- Large codebase analysis takes time
- False positives (killing working agents) are worse than delayed cleanup

```sql
SELECT * FROM agents
WHERE status = 'running' AND parent_agent_id IS NOT NULL
  AND spawned_at < datetime('now', '-24 hours')
```

### Why Soft + Hard Limits

**Soft Limit (Advisory in UserPromptSubmit)**

The skill-activation-prompt hook injects warnings into Claude's context when approaching limits:

```
RESOURCE WARNING: Near limit (6/8 agents)
Only 2 agent slot(s) remaining. Limit spawning.
```

This allows Claude to:
- Self-regulate spawning behavior
- Prioritize completing existing work
- Inform the user proactively

**Hard Limit (Block in PreToolUse)**

The pre-tool-use hook blocks `Task` tool calls when at the limit:

```json
{
  "result": "block",
  "reason": "Agent limit reached: 8/8 agents running. Wait for existing agents to complete."
}
```

This prevents:
- Ignoring soft warnings
- Racing to spawn before the warning is processed
- OOM conditions even if Claude ignores advice

**Why both?**

1. **Soft-only fails**: Claude might spawn 3 agents in parallel before processing the warning
2. **Hard-only fails**: No opportunity for graceful degradation or user awareness
3. **Both together**: Claude gets fair warning, hard limit is safety net

### Why Main Sessions Are Excluded

The orphan detection explicitly excludes main sessions via `parent_agent_id IS NULL`:

```sql
-- Tier 2 and 3 queries include:
WHERE parent_agent_id IS NOT NULL
```

**Rationale**:

Main sessions are started directly by the user and should only be terminated by the user. Even if a main session has been "running" for 48 hours, it may be:
- A long-running development session with the user at lunch
- Paused waiting for user input
- Legitimately working on a complex task

Killing a main session would lose:
- Unsaved work context
- Conversation history
- Any artifacts not yet written to disk

Sub-agents spawned from main sessions ARE included in orphan detection because they're expected to complete autonomously.

---

## Trade-offs Considered

### Alternative 1: Process Groups (Rejected)

**Idea**: Use Unix process groups so killing the parent kills all children.

**Why rejected**:
- Claude Code doesn't spawn agents in dedicated process groups
- Would require modifying Claude Code internals
- Doesn't handle graceful shutdown (all-or-nothing)
- Can't distinguish wanted from unwanted children

### Alternative 2: Fixed Time Limits (Rejected)

**Idea**: Kill any agent running longer than N hours.

**Why rejected**:
- No one-size-fits-all timeout
- Research tasks legitimately take hours
- Would kill working agents during complex analysis
- Three-tier system is more nuanced

### Alternative 3: Memory-Based Killing (Rejected)

**Idea**: Kill agents when memory pressure is detected.

**Why rejected**:
- Reactive instead of proactive
- Which agent to kill? (fairness problem)
- System may already be degraded by the time we detect pressure
- Prevention (limits) is better than cure (killing)

### Alternative 4: User Confirmation for Each Kill (Rejected)

**Idea**: Prompt user before killing each orphan.

**Why rejected**:
- SessionEnd hooks can't prompt users
- Orphan cleanup runs automatically
- Tier-1 orphans are unambiguous; confirmation adds friction
- Users can run `--dry-run` to preview before `--kill`

### Alternative 5: Centralized Daemon (Rejected)

**Idea**: Run a background daemon to monitor and kill orphans.

**Why rejected**:
- Adds deployment complexity
- Daemon itself could become orphaned
- Hooks are already running; leverage them
- Daemon would need DB access, creating concurrency issues

---

## Summary

The Resource Limits and Orphan Detection system balances:

| Goal | How Achieved |
|------|--------------|
| Prevent OOM | Dynamic limits based on available RAM |
| Respect hardware diversity | Formula scales from 8GB to 128GB machines |
| Clean up dead processes | Three-tier orphan detection with appropriate grace periods |
| Preserve user control | Main sessions never auto-killed |
| Provide visibility | Status line shows agent count; `--orphans` flag lists candidates |
| Allow graceful degradation | Soft warnings before hard blocks |

The design prioritizes **safety** (never OOM, never kill main sessions) over **convenience** (might be overly conservative on high-RAM machines, 24h is a long timeout for tier-3 orphans).
