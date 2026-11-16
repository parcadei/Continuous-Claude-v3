---
root_span_id: f728943a-4c7a-40b7-aec7-b27be4282d16
turn_span_id: 8e088335-9715-4e54-b9c2-1009b7a2917a
session_id: f728943a-4c7a-40b7-aec7-b27be4282d16
---

# Implementation Plan: Dynamic Resource Limits & Orphan Detection

Generated: 2025-12-28

## Goal

Prevent OOM conditions from uncontrolled agent spawning by implementing dynamic resource limits based on available RAM, and clean up orphaned agent processes using a three-tier detection system that distinguishes true Unix orphans from app-level orphans.

## Architecture Overview

```
                    +-------------------+
                    |    status.sh      |  <-- Calculates RAM + agent count
                    +-------------------+
                            |
                            v
                    /tmp/claude-resources-{session}.json
                            |
                            v
        +-------------------------------------------+
        |           skill-activation-prompt.ts       |  <-- Soft limit: advisory
        +-------------------------------------------+
                            |
                            v
        +-------------------------------------------+
        |              pre-tool-use.ts               |  <-- Hard limit: blocks Task
        +-------------------------------------------+
                            |
                            v
        +-------------------------------------------+
        |              watch_agents.py               |  <-- Orphan detection
        +-------------------------------------------+
```

---

## Phase 1: Add RAM Query Utility

**Action:** Create a shell function that outputs available RAM in MB using `os.freemem()` equivalent.

**Files:**
- Create: `.claude/scripts/get-resources.sh`

**Input:** None (reads system state)

**Output:** JSON with `freeMemMB`, `totalMemMB` to stdout

**Test:**
```bash
bash .claude/scripts/get-resources.sh
# Expected: {"freeMemMB": 8192, "totalMemMB": 32768}
```

**Implementation:**
```bash
#!/bin/bash
# Cross-platform RAM detection
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS: use vm_stat
    free_pages=$(vm_stat | grep "Pages free" | awk '{print $3}' | tr -d '.')
    page_size=4096
    free_mb=$((free_pages * page_size / 1024 / 1024))
    total_mb=$(($(sysctl -n hw.memsize) / 1024 / 1024))
else
    # Linux: use /proc/meminfo
    free_mb=$(grep MemAvailable /proc/meminfo | awk '{print int($2/1024)}')
    total_mb=$(grep MemTotal /proc/meminfo | awk '{print int($2/1024)}')
fi
echo "{\"freeMemMB\": $free_mb, \"totalMemMB\": $total_mb}"
```

---

## Phase 2: Add Agent Count Query

**Action:** Add method to `coordination.py` to count running agents across all sessions.

**Files:**
- Modify: `scripts/agentica/coordination.py`

**Input:** None

**Output:** `get_global_running_count() -> int`

**Test:**
```bash
uv run python -c "from scripts.agentica.coordination import CoordinationDB; print(CoordinationDB().get_global_running_count())"
```

**Implementation:**
```python
def get_global_running_count(self) -> int:
    """Count ALL running agents across all sessions."""
    with self._get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM agents WHERE status = 'running'"
        ).fetchone()[0]
```

---

## Phase 3: Extend status.sh to Output Resources JSON

**Action:** Add RAM and agent count to status.sh output, writing to `/tmp/claude-resources-{sessionId}.json`.

**Files:**
- Modify: `.claude/scripts/status.sh`

**Input:** Existing JSON from Claude Code

**Output:** Writes `/tmp/claude-resources-{sessionId}.json` with `freeMemMB`, `activeAgents`, `maxAgents`

**Test:**
```bash
echo '{}' | bash .claude/scripts/status.sh
cat /tmp/claude-resources-*.json
# Expected: {"freeMemMB": 8000, "activeAgents": 2, "maxAgents": 12, "contextPct": 45}
```

**Implementation additions:**
```bash
# After existing context calculation, add:
source "$HOME/.claude/scripts/get-resources.sh" 2>/dev/null || true
resources=$(bash "$HOME/.claude/scripts/get-resources.sh" 2>/dev/null)
free_mem=$(echo "$resources" | jq -r '.freeMemMB // 4096')

# Calculate max agents: (freeRAM - 2GB safety) / 500MB per agent
safety_mb=2048
per_agent_mb=500
max_agents=$(( (free_mem - safety_mb) / per_agent_mb ))
[[ "$max_agents" -lt 1 ]] && max_agents=1
[[ "$max_agents" -gt 20 ]] && max_agents=20  # Cap at 20

# Get active agent count via Python
active_agents=$(uv run python -c "
from scripts.agentica.coordination import CoordinationDB
print(CoordinationDB().get_global_running_count())
" 2>/dev/null || echo "0")

# Write resources JSON
echo "{\"freeMemMB\": $free_mem, \"activeAgents\": $active_agents, \"maxAgents\": $max_agents, \"contextPct\": $context_pct}" > "/tmp/claude-resources-${session_id}.json"
```

---

## Phase 4: Create TypeScript Resource Reader

**Action:** Create shared utility to read resources JSON from temp file.

**Files:**
- Create: `.claude/hooks/src/shared/resource-limits.ts`

**Input:** Session ID from environment

**Output:** `{ freeMemMB, activeAgents, maxAgents, contextPct, recommendation }`

**Test:**
```bash
echo '{"freeMemMB": 8000, "activeAgents": 2, "maxAgents": 12}' > /tmp/claude-resources-test.json
CLAUDE_SESSION_ID=test npx tsx -e "
import { getResourceStatus } from './.claude/hooks/src/shared/resource-limits.js';
console.log(getResourceStatus());
"
```

**Implementation:**
```typescript
import { readFileSync, existsSync } from 'fs';

export interface ResourceStatus {
  freeMemMB: number;
  activeAgents: number;
  maxAgents: number;
  contextPct: number;
  recommendation: string;
}

export function getResourceStatus(): ResourceStatus | null {
  const sessionId = process.env.CLAUDE_SESSION_ID || process.env.CLAUDE_PPID || 'default';
  const resourceFile = `/tmp/claude-resources-${sessionId}.json`;

  if (!existsSync(resourceFile)) {
    return null;
  }

  try {
    const data = JSON.parse(readFileSync(resourceFile, 'utf-8'));
    const remaining = data.maxAgents - data.activeAgents;

    let recommendation: string;
    if (remaining <= 0) {
      recommendation = 'LIMIT REACHED: Do not spawn more agents';
    } else if (remaining <= 2) {
      recommendation = `Caution: Only ${remaining} agent slot(s) remaining`;
    } else {
      recommendation = `OK: ${remaining} agent slots available`;
    }

    return {
      freeMemMB: data.freeMemMB,
      activeAgents: data.activeAgents,
      maxAgents: data.maxAgents,
      contextPct: data.contextPct || 0,
      recommendation
    };
  } catch {
    return null;
  }
}

export function isAtLimit(): boolean {
  const status = getResourceStatus();
  return status ? status.activeAgents >= status.maxAgents : false;
}
```

---

## Phase 5: Add Soft Limit Advisory to UserPromptSubmit

**Action:** Extend `skill-activation-prompt.ts` to inject RAM/agent advisory when approaching limits.

**Files:**
- Modify: `.claude/hooks/src/skill-activation-prompt.ts`

**Input:** Reads `/tmp/claude-resources-{sessionId}.json`

**Output:** Injects system message: "RAM: 4GB | Agents: 3/8 | Recommend: max 2 more"

**Test:**
```bash
echo '{"freeMemMB": 4000, "activeAgents": 6, "maxAgents": 8}' > /tmp/claude-resources-test.json
echo '{"prompt": "spawn more agents"}' | CLAUDE_SESSION_ID=test npx tsx .claude/hooks/src/skill-activation-prompt.ts
```

**Implementation additions:**
```typescript
import { getResourceStatus } from './shared/resource-limits.js';

// After existing context warnings, add:
const resources = getResourceStatus();
if (resources) {
  const remaining = resources.maxAgents - resources.activeAgents;
  let resourceWarning = '';

  if (remaining <= 0) {
    resourceWarning = '\n' +
      '='.repeat(50) + '\n' +
      'RESOURCE LIMIT: Agents ' + resources.activeAgents + '/' + resources.maxAgents + '\n' +
      'RAM: ' + Math.round(resources.freeMemMB / 1024) + 'GB free\n' +
      'Do NOT spawn new agents until existing ones complete.\n' +
      '='.repeat(50) + '\n';
  } else if (remaining <= 2) {
    resourceWarning = '\nResource Status: Agents ' + resources.activeAgents + '/' +
      resources.maxAgents + ' | RAM: ' + Math.round(resources.freeMemMB / 1024) +
      'GB | Recommend: max ' + remaining + ' more\n';
  }

  if (resourceWarning) {
    console.log(resourceWarning);
  }
}
```

---

## Phase 6: Add Hard Limit Block to PreToolUse

**Action:** Block Task tool if `activeAgents >= maxAgents`.

**Files:**
- Modify: `.claude/hooks/src/pre-tool-use.ts`

**Input:** Tool name from PreToolUse input

**Output:** `{ result: 'block', reason: '...' }` when over limit

**Test:**
```bash
echo '{"freeMemMB": 2000, "activeAgents": 4, "maxAgents": 4}' > /tmp/claude-resources-test.json
echo '{"tool_name": "Task", "tool_input": {}}' | CLAUDE_SESSION_ID=test npx tsx .claude/hooks/src/pre-tool-use.ts
# Expected: {"result": "block", "reason": "Resource limit reached..."}
```

**Implementation additions:**
```typescript
import { isAtLimit, getResourceStatus } from './shared/resource-limits.js';

// At top of main(), before pattern routing:
if (input.tool_name === 'Task') {
  if (isAtLimit()) {
    const status = getResourceStatus();
    console.log(JSON.stringify({
      result: 'block',
      reason: `Resource limit reached: ${status?.activeAgents}/${status?.maxAgents} agents running. ` +
        `Wait for existing agents to complete or terminate idle ones.`
    }));
    return;
  }
}
```

---

## Phase 7: Add ppid Column to Agents Table

**Action:** Store parent process ID when registering agents for Unix orphan detection.

**Files:**
- Modify: `scripts/agentica/coordination.py`

**Input:** `os.getppid()` at registration time

**Output:** New column `ppid INTEGER` in agents table

**Test:**
```bash
uv run python -c "
from scripts.agentica.coordination import CoordinationDB
import os
db = CoordinationDB()
# Check schema has ppid column
"
```

**Implementation:**
```python
# Add to SCHEMA:
# ppid INTEGER,  -- Parent process ID for orphan detection

# Modify register_agent to include:
import os
ppid = os.getppid()
# Add ppid to INSERT statement
```

---

## Phase 8: Add Orphan Detection Query

**Action:** Add method to find potential orphans using three-tier rules.

**Files:**
- Modify: `scripts/agentica/coordination.py`

**Input:** None

**Output:** `get_orphan_candidates() -> list[OrphanCandidate]` with tier classification

**Test:**
```bash
uv run python -c "
from scripts.agentica.coordination import CoordinationDB
db = CoordinationDB()
orphans = db.get_orphan_candidates()
print(f'Found {len(orphans)} orphan candidates')
"
```

**Implementation:**
```python
@dataclass
class OrphanCandidate:
    agent_id: str
    ppid: int | None
    parent_agent_id: str | None
    spawned_at: datetime
    tier: int  # 1=Unix orphan, 2=parent dead, 3=app orphan
    reason: str

def get_orphan_candidates(self) -> list[OrphanCandidate]:
    """Find potential orphan agents using three-tier detection.

    Tier 1: ppid == 1 (true Unix orphan) -> safe to kill immediately
    Tier 2: parent_agent_id exists but parent status != 'running' -> kill after 30min
    Tier 3: Running > 24h with no recent activity -> kill after timeout

    EXCLUDES main sessions (parent_agent_id IS NULL AND ppid != 1)
    """
    candidates = []
    now = datetime.now(UTC).replace(tzinfo=None)

    with self._get_conn() as conn:
        # Tier 1: True Unix orphans (ppid == 1)
        rows = conn.execute('''
            SELECT id, ppid, parent_agent_id, spawned_at
            FROM agents
            WHERE status = 'running' AND ppid = 1
        ''').fetchall()
        for row in rows:
            candidates.append(OrphanCandidate(
                agent_id=row['id'],
                ppid=row['ppid'],
                parent_agent_id=row['parent_agent_id'],
                spawned_at=datetime.fromisoformat(row['spawned_at']),
                tier=1,
                reason='ppid=1 (parent process died)'
            ))

        # Tier 2: Parent agent dead (status != 'running')
        rows = conn.execute('''
            SELECT a.id, a.ppid, a.parent_agent_id, a.spawned_at
            FROM agents a
            JOIN agents p ON a.parent_agent_id = p.id
            WHERE a.status = 'running'
              AND p.status != 'running'
              AND a.spawned_at < ?
        ''', ((now - timedelta(minutes=30)).isoformat(),)).fetchall()
        for row in rows:
            candidates.append(OrphanCandidate(
                agent_id=row['id'],
                ppid=row['ppid'],
                parent_agent_id=row['parent_agent_id'],
                spawned_at=datetime.fromisoformat(row['spawned_at']),
                tier=2,
                reason='Parent agent completed/failed (30min grace expired)'
            ))

        # Tier 3: App orphans (running > 24h)
        rows = conn.execute('''
            SELECT id, ppid, parent_agent_id, spawned_at
            FROM agents
            WHERE status = 'running'
              AND parent_agent_id IS NOT NULL
              AND spawned_at < ?
        ''', ((now - timedelta(hours=24)).isoformat(),)).fetchall()
        for row in rows:
            candidates.append(OrphanCandidate(
                agent_id=row['id'],
                ppid=row['ppid'],
                parent_agent_id=row['parent_agent_id'],
                spawned_at=datetime.fromisoformat(row['spawned_at']),
                tier=3,
                reason='Running >24h without completion'
            ))

    return candidates
```

---

## Phase 9: Add Unix ppid Check to watch_agents.py

**Action:** Add function to check if a PID's parent is actually PID 1 (init/launchd).

**Files:**
- Modify: `scripts/agentica/watch_agents.py`

**Input:** PID to check

**Output:** `is_unix_orphan(pid: int) -> bool`

**Test:**
```bash
uv run python -c "
from scripts.agentica.watch_agents import is_unix_orphan
# Current process should NOT be orphan
import os
print(f'Current process orphan: {is_unix_orphan(os.getpid())}')
"
```

**Implementation:**
```python
def is_unix_orphan(pid: int) -> bool:
    """Check if a process is a Unix orphan (ppid == 1).

    Returns True if the process exists and its parent is init/launchd (PID 1).
    Returns False if process doesn't exist or has a living parent.
    """
    try:
        result = subprocess.run(
            ['ps', '-p', str(pid), '-o', 'ppid='],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            ppid = int(result.stdout.strip())
            return ppid == 1
        return False  # Process doesn't exist
    except (subprocess.TimeoutExpired, ValueError):
        return False
```

---

## Phase 10: Create Orphan Cleanup Script

**Action:** Create standalone script that finds and kills orphaned processes.

**Files:**
- Create: `scripts/agentica/cleanup_orphans.py`

**Input:** `--dry-run` flag (default: dry run), `--tier N` to limit to specific tier

**Output:** Prints orphans found, kills them if not dry-run

**Test:**
```bash
uv run python scripts/agentica/cleanup_orphans.py --dry-run
uv run python scripts/agentica/cleanup_orphans.py --tier 1  # Only kill Unix orphans
```

**Implementation:**
```python
#!/usr/bin/env python3
"""Orphan agent cleanup with three-tier detection.

USAGE:
    uv run python scripts/agentica/cleanup_orphans.py --dry-run
    uv run python scripts/agentica/cleanup_orphans.py --tier 1
    uv run python scripts/agentica/cleanup_orphans.py --kill
"""
import argparse
import os
import signal
from scripts.agentica.coordination import CoordinationDB
from scripts.agentica.watch_agents import is_unix_orphan

def kill_process(pid: int) -> bool:
    """Attempt to kill a process. Returns True if successful."""
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False  # Already dead
    except PermissionError:
        return False

def main():
    parser = argparse.ArgumentParser(description="Clean up orphaned agents")
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--kill', action='store_true', help='Actually kill processes')
    parser.add_argument('--tier', type=int, choices=[1, 2, 3], help='Only process specific tier')
    args = parser.parse_args()

    if args.kill:
        args.dry_run = False

    db = CoordinationDB()
    candidates = db.get_orphan_candidates()

    if args.tier:
        candidates = [c for c in candidates if c.tier == args.tier]

    for c in candidates:
        prefix = '[DRY-RUN] ' if args.dry_run else ''
        print(f'{prefix}Tier {c.tier}: {c.agent_id} - {c.reason}')

        if not args.dry_run and c.ppid:
            # Verify it's still an orphan before killing
            if c.tier == 1 and is_unix_orphan(c.ppid):
                if kill_process(c.ppid):
                    db.complete_agent(c.agent_id, status='killed',
                                     error_message=f'Orphan cleanup: {c.reason}')
                    print(f'  Killed PID {c.ppid}')

if __name__ == '__main__':
    main()
```

---

## Phase 11: Add Orphan Check to SessionEnd Hook

**Action:** Run orphan cleanup at end of each main session.

**Files:**
- Modify: `.claude/hooks/src/session-end-cleanup-swarms.ts` (or create new handler)

**Input:** SessionEnd event

**Output:** Logs orphan count, optionally cleans tier-1 orphans

**Test:**
```bash
echo '{}' | npx tsx .claude/hooks/src/session-end-cleanup-swarms.ts
# Should log: "Orphan check: 0 tier-1, 0 tier-2, 0 tier-3"
```

**Implementation:**
```typescript
// Add to session-end handler:
import { spawnSync } from 'child_process';

// Run orphan detection (dry-run by default)
const result = spawnSync('uv', [
  'run', 'python', 'scripts/agentica/cleanup_orphans.py',
  '--dry-run'
], { encoding: 'utf-8', timeout: 10000 });

if (result.stdout) {
  console.error(`Orphan check: ${result.stdout.trim()}`);
}

// Auto-kill tier-1 orphans (safest)
spawnSync('uv', [
  'run', 'python', 'scripts/agentica/cleanup_orphans.py',
  '--kill', '--tier', '1'
], { encoding: 'utf-8', timeout: 10000 });
```

---

## Phase 12: Add --orphans Flag to watch_agents.py

**Action:** Add command to display orphan candidates in watch_agents.py.

**Files:**
- Modify: `scripts/agentica/watch_agents.py`

**Input:** `--orphans` flag

**Output:** Table showing orphan candidates with tier, reason, age

**Test:**
```bash
uv run python scripts/agentica/watch_agents.py --orphans
```

**Implementation:**
```python
# Add to argparse:
parser.add_argument('--orphans', '-o', action='store_true', help='Show orphan candidates')

# Add handler:
if args.orphans:
    candidates = db.get_orphan_candidates()
    if RICH_AVAILABLE:
        table = Table(title="Orphan Candidates")
        table.add_column("Tier", style="red")
        table.add_column("Agent ID", style="cyan")
        table.add_column("Age", style="magenta")
        table.add_column("Reason", style="white")

        for c in candidates:
            age = format_elapsed(c.spawned_at)
            table.add_row(str(c.tier), c.agent_id, age, c.reason)

        console.print(table)
    else:
        for c in candidates:
            print(f"Tier {c.tier}: {c.agent_id} - {c.reason}")
```

---

## Phase 13: Add Status Line Resource Display

**Action:** Show agent count in status line when near limit.

**Files:**
- Modify: `.claude/scripts/status.sh`

**Input:** Existing status line data

**Output:** Adds "Agents: 5/8" to status line when > 50% utilized

**Test:**
```bash
echo '{}' | bash .claude/scripts/status.sh
# Expected: "145K 72% | main U:6 | Agents: 5/8 | Current focus"
```

**Implementation:**
```bash
# After git_info calculation, before output:
agent_display=""
if [[ -f "/tmp/claude-resources-${session_id}.json" ]]; then
    active=$(jq -r '.activeAgents // 0' "/tmp/claude-resources-${session_id}.json" 2>/dev/null)
    max=$(jq -r '.maxAgents // 10' "/tmp/claude-resources-${session_id}.json" 2>/dev/null)
    if [[ "$active" -gt 0 ]]; then
        utilization=$((active * 100 / max))
        if [[ "$utilization" -ge 75 ]]; then
            agent_display="\033[31mAgents: $active/$max\033[0m"  # Red
        elif [[ "$utilization" -ge 50 ]]; then
            agent_display="\033[33mAgents: $active/$max\033[0m"  # Yellow
        fi
    fi
fi

# Include in output
[[ -n "$agent_display" ]] && output="$output | $agent_display"
```

---

## Phase 14: Integration Test Suite

**Action:** Create integration tests for resource limits and orphan detection.

**Files:**
- Create: `tests/integration/test_resource_limits.py`

**Input:** None (uses test fixtures)

**Output:** pytest results

**Test:**
```bash
uv run pytest tests/integration/test_resource_limits.py -v
```

**Implementation:**
```python
"""Integration tests for resource limits and orphan detection."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
import pytest
from scripts.agentica.coordination import CoordinationDB

class TestResourceLimits:
    def test_status_sh_writes_resources_json(self):
        """status.sh should write resources JSON to /tmp."""
        session_id = f"test-{os.getpid()}"
        result = subprocess.run(
            ['bash', '.claude/scripts/status.sh'],
            input='{}',
            capture_output=True,
            text=True,
            env={**os.environ, 'CLAUDE_SESSION_ID': session_id}
        )

        resource_file = Path(f'/tmp/claude-resources-{session_id}.json')
        assert resource_file.exists()

        data = json.loads(resource_file.read_text())
        assert 'freeMemMB' in data
        assert 'activeAgents' in data
        assert 'maxAgents' in data
        assert data['maxAgents'] >= 1

    def test_max_agents_formula(self):
        """Max agents should scale with available RAM."""
        # Formula: (freeRAM - 2GB) / 500MB
        # 10GB free -> (10240 - 2048) / 500 = 16 agents
        # 4GB free -> (4096 - 2048) / 500 = 4 agents
        pass  # Implement based on get-resources.sh

class TestOrphanDetection:
    def test_orphan_candidates_excludes_main_sessions(self):
        """Main sessions (parent_agent_id IS NULL) should not be flagged."""
        db = CoordinationDB(session_id=f"test-{os.getpid()}")
        # Register a "main" agent (no parent)
        db.register_agent("main-test", premise="Main session")

        orphans = db.get_orphan_candidates()
        assert not any(o.agent_id == "main-test" for o in orphans)
```

---

## Testing Strategy

### Unit Tests
- `test_resource_limits.py`: Formula calculations, JSON parsing
- `test_orphan_detection.py`: Three-tier classification, edge cases

### Integration Tests
- End-to-end status.sh -> JSON -> hook injection
- PreToolUse blocking when at limit
- Orphan cleanup script with --dry-run

### Manual Verification
1. Start multiple Claude sessions, verify agent count in status line
2. Spawn agents until limit reached, verify block message
3. Kill a parent process, verify child detected as orphan
4. Run cleanup script, verify only appropriate orphans killed

---

## Risks & Considerations

1. **Race conditions**: Multiple sessions may read/write agent counts simultaneously
   - Mitigation: Use SQLite transactions, accept eventual consistency

2. **False positive orphans**: Process may be slow to start, not actually orphaned
   - Mitigation: Grace periods (30min for tier-2, 24h for tier-3)

3. **Main session misidentification**: Could incorrectly flag main sessions as orphans
   - Mitigation: Explicit `parent_agent_id IS NULL` exclusion

4. **Resource detection latency**: StatusLine runs frequently but agent spawn is async
   - Mitigation: Soft limits give advisory before hard block kicks in

5. **Cross-platform compatibility**: RAM detection differs macOS vs Linux
   - Mitigation: Platform-specific commands in get-resources.sh

---

## Estimated Complexity

| Phase | Effort | Risk |
|-------|--------|------|
| 1-4   | Low    | Low  | Infrastructure setup
| 5-6   | Medium | Low  | Hook modifications
| 7-9   | Medium | Medium | Database schema + Unix detection
| 10-11 | Medium | Medium | Cleanup automation
| 12-14 | Low    | Low  | UI/UX + tests

**Total estimate:** 4-6 hours for full implementation

---

## References

- Code map: `docs/handoffs/resource-limits-codemap.md`
- Existing hooks: `.claude/hooks/src/`
- Coordination DB: `scripts/agentica/coordination.py`
- Watch agents: `scripts/agentica/watch_agents.py`
