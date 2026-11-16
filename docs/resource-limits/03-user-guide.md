# User Guide: Resource Limits & Orphan Management

This guide covers how to use the resource management system to monitor agents, understand warnings, and clean up orphaned processes.

## Quick Start

### What You'll See

When resources are constrained, the status line shows additional information:

```
95.0K 47% | main U:3 | RAM:4G Ag:3/8 | Current focus
                       ^^^^^^^^^^^^
                       Resource indicator (only shown when utilization >= 50%)
```

**Format breakdown:**
- `RAM:4G` - Available RAM in gigabytes
- `Ag:3/8` - Active agents / Maximum allowed agents

### Color Coding

The resource indicator is color-coded based on agent utilization:

| Utilization | Color  | Status |
|-------------|--------|--------|
| 50-79%      | Yellow | Warning - approaching limit |
| 80%+        | Red    | Critical - near or at limit |

When utilization is below 50%, no resource indicator is displayed.

---

## Warning Messages

The system provides two levels of warnings via the `UserPromptSubmit` hook.

### Soft Warning (80% utilization)

When `activeAgents >= maxAgents * 0.8`:

```
RESOURCE WARNING: 8/10 agents running (80%)
Consider completing existing tasks before spawning more.
```

This warning is informational and does not block any operations. It appears in the hook output to remind you that resources are running low.

### Critical Warning (100% utilization)

When `activeAgents >= maxAgents`:

```
RESOURCE CRITICAL: 10/10 agents running (100%)
Task tool will be blocked until agents complete.
```

At this level, the `PreToolUse` hook actively blocks the `Task` tool, preventing new agent spawns.

---

## Managing Agents

### Check Active Agents

View currently running agents across all sessions:

```bash
# One-shot view
uv run python scripts/agentica/watch_agents.py

# Real-time monitoring (updates every 0.5s)
uv run python scripts/agentica/watch_agents.py --watch

# With subprocess monitoring (shows Claude CLI processes)
uv run python scripts/agentica/watch_agents.py --watch --monitor

# Filter by pattern type
uv run python scripts/agentica/watch_agents.py --pattern swarm
```

### View All Sessions

To see agents from all sessions (not just the current one):

```bash
uv run python scripts/agentica/watch_agents.py --all-sessions
```

### Get Session Summary

```bash
uv run python scripts/agentica/watch_agents.py --summary
```

Output:
```
Session: abc123def456
By Status: {'running': 3, 'completed': 12, 'failed': 1}
By Pattern: {'swarm': 8, 'hierarchical': 4, 'pipeline': 4}
Tasks: 16
```

---

## Orphan Detection

Orphan agents are processes that should no longer be running but haven't properly terminated.

### Three-Tier Detection System

| Tier | Description | Detection Criteria | Grace Period |
|------|-------------|-------------------|--------------|
| 1 | Unix orphan | `ppid = 1` (parent died, adopted by init) | Immediate |
| 2 | Parent agent dead | Parent agent status != 'running' | 30 minutes |
| 3 | Long-running | Running > 24 hours | 24 hours |

### Check for Orphans

View potential orphan candidates:

```bash
# Table view (requires rich library)
uv run python scripts/agentica/watch_agents.py --orphans

# JSON output (for scripting)
uv run python scripts/agentica/watch_agents.py --orphans --json
```

Example output:
```
Orphan Candidates
+------+------------------+-------+----------------------------------------+
| Tier | Agent ID         | Age   | Reason                                 |
+------+------------------+-------+----------------------------------------+
| 1    | abc123def456     | 2h 5m | ppid=1 (parent process died)           |
| 2    | xyz789abc012     | 45m   | Parent agent completed/failed (30min   |
|      |                  |       | grace expired)                         |
| 3    | mno345pqr678     | 25h   | Running >24h without completion        |
+------+------------------+-------+----------------------------------------+
```

---

## Cleaning Up Orphans

### Dry Run (Default - Safe Preview)

Always run a dry run first to see what would be cleaned up:

```bash
uv run python scripts/agentica/cleanup_orphans.py
# or explicitly:
uv run python scripts/agentica/cleanup_orphans.py --dry-run
```

Output:
```
============================================================
Orphan Agent Cleanup
============================================================
Mode: DRY-RUN
------------------------------------------------------------
Found 2 orphan candidate(s):

[DRY-RUN] Tier 1: abc123def456 - ppid=1 (parent process died)
[DRY-RUN] Tier 2: xyz789abc012 - Parent agent completed/failed (30min grace expired)
------------------------------------------------------------
Dry run complete. 2 orphan(s) would be cleaned up.
Run with --kill to actually terminate orphan processes.
============================================================
```

### Actually Kill Orphans

```bash
# Kill all detected orphans
uv run python scripts/agentica/cleanup_orphans.py --kill

# Kill only Tier 1 orphans (safest - true Unix orphans)
uv run python scripts/agentica/cleanup_orphans.py --kill --tier 1

# Kill only Tier 2 orphans (parent agent dead)
uv run python scripts/agentica/cleanup_orphans.py --kill --tier 2

# Kill only Tier 3 orphans (long-running)
uv run python scripts/agentica/cleanup_orphans.py --kill --tier 3
```

**Recommendation:** Start with `--tier 1` which is the safest. Tier 1 orphans have definitely lost their parent process and can be safely terminated.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_SESSION_ID` | `$PPID` | Session identifier for resource files |
| `MOCK_FREE_MEM_MB` | (system) | Override detected free RAM (testing only) |
| `MOCK_ACTIVE_AGENTS` | (db) | Override active agent count (testing only) |

### Resource Calculation Formula

Maximum agents are calculated based on available RAM:

```
maxAgents = (freeRAM_MB - 2048) / 500
```

**Constraints:**
- Minimum: 1 agent
- Maximum: 20 agents (hard cap)

**Examples:**
| Free RAM | Calculation | Max Agents |
|----------|-------------|------------|
| 3 GB     | (3072 - 2048) / 500 = 2 | 2 |
| 8 GB     | (8192 - 2048) / 500 = 12 | 12 |
| 16 GB    | (16384 - 2048) / 500 = 28 | 20 (capped) |

### Resource File Location

Resources are written to:
```
/tmp/claude-resources-{sessionId}.json
```

Example content:
```json
{
  "freeMemMB": 8192,
  "activeAgents": 3,
  "maxAgents": 12,
  "contextPct": 45
}
```

---

## Troubleshooting

### "Task tool blocked" but I want to spawn more agents

This happens when `activeAgents >= maxAgents`. Options:

1. **Wait for agents to complete** - Check progress with:
   ```bash
   uv run python scripts/agentica/watch_agents.py --watch
   ```

2. **Clean up orphans** - Some agents may be stuck:
   ```bash
   uv run python scripts/agentica/cleanup_orphans.py --kill --tier 1
   ```

3. **Free up RAM** - Close other applications to increase `maxAgents`

### Resource warnings not appearing

Check if the resource file is being written:
```bash
cat /tmp/claude-resources-*.json
```

If missing, verify `status.sh` is running. The status script is triggered by the `StatusLine` hook.

### Orphans not being detected

Orphan detection requires:
1. The agent was registered with `coordination.py`
2. Enough time has passed (grace periods apply to Tier 2 and 3)

Check the coordination database:
```bash
uv run python -c "
from scripts.agentica.coordination import CoordinationDB
db = CoordinationDB()
print(f'Running agents: {db.get_global_running_count()}')
print(f'Orphan candidates: {len(db.get_orphan_candidates())}')
"
```

### Wrong agent count displayed

The agent count queries the coordination database. Verify it's accessible:
```bash
# Check database path
uv run python -c "
from scripts.agentica.coordination import CoordinationDB
db = CoordinationDB()
print(f'DB path: {db.db_path}')
"
```

### Status line not showing resource indicator

The resource indicator only appears when:
1. At least 1 agent is running (`activeAgents > 0`)
2. Utilization is >= 50% (`activeAgents / maxAgents >= 0.5`)

Check current utilization:
```bash
cat /tmp/claude-resources-*.json | jq '(.activeAgents / .maxAgents * 100) | round'
```

---

## Command Reference

### watch_agents.py

```bash
# Basic usage
uv run python scripts/agentica/watch_agents.py [OPTIONS]

Options:
  --watch, -w           Real-time monitoring mode
  --completed, -c       Show completed tasks
  --summary, -s         Show session summary
  --pattern, -p TYPE    Filter by pattern type
  --session ID          Specify session ID
  --all-sessions, -a    Show agents from all sessions
  --monitor, -m         Enable subprocess monitoring
  --watch-dir PATH      Directory to watch for file changes
  --logs, -l            Enable log tailing for agent messages
  --logs-dir PATH       Directory containing agent log files (default: ./logs)
  --orphans, -o         Show orphan candidates
  --json, -j            Output in JSON format
```

### cleanup_orphans.py

```bash
# Basic usage
uv run python scripts/agentica/cleanup_orphans.py [OPTIONS]

Options:
  --dry-run             Report orphans without killing (default: True)
  --kill                Actually terminate orphan processes
  --tier {1,2,3}        Only process orphans of this tier
  --session ID          Session ID for the coordination database
```

---

## Integration with Hooks

The resource management system integrates with Claude Code hooks:

1. **StatusLine** (`status.sh`) - Writes resource JSON to `/tmp`
2. **UserPromptSubmit** (`skill-activation-prompt.ts`) - Displays soft warnings
3. **PreToolUse** (`pre-tool-use.ts`) - Blocks Task when at limit
4. **SessionEnd** (`session-end-cleanup-swarms.ts`) - Auto-cleans Tier 1 orphans

### Manual Hook Testing

Test the resource reading:
```bash
echo '{"freeMemMB": 4000, "activeAgents": 8, "maxAgents": 10}' > /tmp/claude-resources-test.json
CLAUDE_SESSION_ID=test npx tsx .claude/hooks/src/shared/resource-reader.ts
```

Test the hard limit block:
```bash
echo '{"tool_name": "Task", "tool_input": {}}' | \
  CLAUDE_SESSION_ID=test npx tsx .claude/hooks/src/pre-tool-use.ts
```

---

## Related Documentation

- [Architecture Overview](./01-architecture.md) - System design and data flow
- [Code Reference](./02-code-reference.md) - Implementation details
- [Plan Document](../handoffs/resource-limits-plan.md) - Original implementation plan
