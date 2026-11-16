# Database Schema Issue: Stop Hook Query Analysis

## Executive Summary

**CRITICAL MISMATCH FOUND:** The Stop hook's SQL query and the actual coordination.db schema are **incompatible**. The hook will crash at runtime if executed.

**Issue:** The Stop hook queries `completed_tasks` table for a `swarm_id` column that doesn't exist in the actual schema.

---

## Current Schema State

### File: `/scripts/agentica/coordination.py` (Lines 35-90)

The `SCHEMA` constant defines the actual database structure:

#### `completed_tasks` table definition (Lines 50-61):
```sql
CREATE TABLE IF NOT EXISTS completed_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    pattern TEXT,
    input_summary TEXT,
    output_summary TEXT,
    output_type TEXT,
    artifacts TEXT,
    duration_ms INTEGER,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);
```

**Columns present:**
- `id`, `agent_id`, `pattern`, `input_summary`, `output_summary`, `output_type`, `artifacts`, `duration_ms`, `completed_at`

**Critical gap:** NO `swarm_id` column

#### `broadcasts` table definition (Lines 79-90):
```sql
CREATE TABLE IF NOT EXISTS broadcasts (
    id TEXT PRIMARY KEY,
    swarm_id TEXT NOT NULL,
    sender_agent TEXT NOT NULL,
    broadcast_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

**Columns present:** `id`, `swarm_id`, `sender_agent`, `broadcast_type`, `payload`, `created_at` ✓

---

## Stop Hook Implementation Issue

### File: `.claude/hooks/src/stop-swarm-coordinator.ts` (Lines 60-86)

The hook executes this SQL query:

```sql
-- Query 1: This works - broadcasts table HAS swarm_id
SELECT COUNT(DISTINCT sender_agent) as done_count
FROM broadcasts
WHERE swarm_id = ? AND broadcast_type = 'done'

-- Query 2: This FAILS - completed_tasks table DOES NOT have swarm_id
SELECT COUNT(DISTINCT agent_id) as total_count
FROM completed_tasks
WHERE swarm_id = ?
```

**Runtime error:** SQL error: "no such column: swarm_id" in the second query

---

## Test Schema vs Reality

### File: `tests/unit/test_stop_swarm_coordinator.py`

The test file **creates its own schema** (Lines 109-115) that differs from production:

```sql
CREATE TABLE IF NOT EXISTS completed_tasks (
    id TEXT PRIMARY KEY,
    swarm_id TEXT NOT NULL,           -- EXTRA COLUMN (test only)
    agent_id TEXT NOT NULL,
    task_prompt TEXT NOT NULL,        -- Different from production
    completed_at TEXT NOT NULL
);
```

**Why tests pass:**
- Tests create ad-hoc schemas with the `swarm_id` column the Stop hook expects
- Tests don't use `coordination.py`'s real schema
- This creates false confidence that the implementation works

---

## Plan Intent vs Implementation

### Plan: Phase 12.5 (Lines 675-821 in 2025-12-28-user-triggered-agentica.md)

The plan shows the same problem:

**Lines 757-761 in the plan:**
```python
cursor = conn.execute('''
    SELECT COUNT(DISTINCT agent_id) as total_count
    FROM completed_tasks
    WHERE swarm_id = ?
''', (swarm_id,))
```

**The plan copied the flawed query directly into the implementation** without validating against the actual schema.

---

## Root Cause

**Missing integration:** Phase 12.7 (PostToolUse Hook for Task Completion) is supposed to:
1. Track when Task tool completes
2. Record `agent_id` to coordination.db

But there's **no code** that:
- Adds `swarm_id` column to `completed_tasks`
- Inserts `swarm_id` values into `completed_tasks` from the PostToolUse hook

Phase 12.7 is listed as **pending** (not completed), so this integration was never done.

---

## What Should Happen (By Design)

```
User-Triggered Agentica Flow:
├─ User: "launch agentica"
├─ Agents spawn with SWARM_ID environment variable
├─ Phase 12.5 (Stop Hook):
│  ├─ Query broadcasts for agents that broadcast "done"
│  └─ Count total agents (from ???)
└─ Phase 12.7 (PostToolUse Hook - NOT YET IMPLEMENTED):
   ├─ Track Task tool completions
   ├─ Insert into completed_tasks with swarm_id
   └─ Make agents queryable by swarm
```

**The Stop hook assumes Phase 12.7 is done, but it isn't.**

---

## Three Options to Fix

### Option A: Add swarm_id to completed_tasks (Correct)

**Status:** Requires Phase 12.7 implementation

1. **Update schema** in `coordination.py` (Lines 50-61):
   ```sql
   CREATE TABLE IF NOT EXISTS completed_tasks (
       id TEXT PRIMARY KEY,
       swarm_id TEXT,              -- NEW COLUMN (nullable for non-swarm tasks)
       agent_id TEXT NOT NULL,
       pattern TEXT,
       input_summary TEXT,
       output_summary TEXT,
       output_type TEXT,
       artifacts TEXT,
       duration_ms INTEGER,
       completed_at TEXT NOT NULL,
       FOREIGN KEY (agent_id) REFERENCES agents(id)
   );

   CREATE INDEX IF NOT EXISTS idx_tasks_swarm ON completed_tasks(swarm_id);
   ```

2. **Implement Phase 12.7** - PostToolUse Hook:
   - Detect Task tool completion
   - Get `SWARM_ID` from environment
   - Insert into `completed_tasks` with `swarm_id`

3. **Stop hook works as-is** once Phase 12.7 populates the data

**Pros:**
- Matches the plan and design intent
- Allows direct querying of completed tasks by swarm
- Integrates task completion tracking with agent coordination

**Cons:**
- Requires completing Phase 12.7 first
- Requires schema migration for any existing databases

---

### Option B: Query agent_count differently (Temporary Fix)

**Use `agents` table instead of `completed_tasks`:**

```python
# Query 1: done count (broadcasts - WORKS)
SELECT COUNT(DISTINCT sender_agent) as done_count
FROM broadcasts
WHERE swarm_id = ? AND broadcast_type = 'done'

# Query 2: total agents (agents - WORKS if populated)
SELECT COUNT(DISTINCT id) as total_count
FROM agents
WHERE ???  -- How do we know which agents are in the swarm?
```

**Problem:** `agents` table has no `swarm_id` column either!

The `agents` table structure (from `coordination.py` lines 36-48):
```sql
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    premise TEXT,
    model TEXT,
    scope_keys TEXT,
    pattern TEXT,              -- Contains "swarm", not the swarm ID
    parent_agent_id TEXT,
    spawned_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    error_message TEXT
);
```

**No swarm_id field to correlate agents to swarm.**

**Verdict:** Option B doesn't work without adding `swarm_id` to `agents` too.

---

### Option C: Track via environment variables (Workaround)

**Store swarm info in files instead of database:**

```typescript
// In Stop hook:
const swarmInfoPath = join(projectDir, '.claude', 'cache',
                           'agentica-coordination', `swarm-${swarmId}.json`);
const swarmInfo = JSON.parse(readFileSync(swarmInfoPath, 'utf-8'));
const totalAgents = swarmInfo.agents.length;
const doneAgents = swarmInfo.agents.filter(a => a.status === 'done').length;
```

**Pros:**
- No schema changes needed
- Works immediately

**Cons:**
- Defeats purpose of coordination.db
- Race conditions if multiple agents write same file
- Duplicates data (agents table already exists)
- Not idempotent (as per idempotent-redundancy.md rules)

---

## Recommendation

**OPTION A IS CORRECT** - Add `swarm_id` to `completed_tasks` and implement Phase 12.7.

**Rationale:**
1. **Matches the plan** - This is the intended design (lines 823-874 of 2025-12-28-user-triggered-agentica.md)
2. **Proper data model** - `completed_tasks` should track swarms for coordination
3. **Enables future features** - Task completion tracking by swarm enables better agent observability
4. **Follows rules** - Adheres to index-at-creation.md (track at creation time) and idempotent-redundancy.md (no redundant storage)

**Work breakdown:**
1. Update `SCHEMA` in `/scripts/agentica/coordination.py`:
   - Add `swarm_id TEXT` column to `completed_tasks`
   - Add index on `swarm_id`
   - Make `swarm_id` nullable (for non-swarm tasks)

2. Update `CoordinationDB.record_task()` method:
   - Accept optional `swarm_id` parameter
   - Insert `swarm_id` into database

3. Implement Phase 12.7 (PostToolUse Hook):
   - Detect Task tool completions
   - Read `SWARM_ID` environment variable
   - Call `record_task(swarm_id=swarm_id)`

4. Stop hook automatically works once Phase 12.7 populates data

---

## Files Affected

**Schema definition:**
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/coordination.py` (lines 35-90)

**Stop hook implementation:**
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/hooks/src/stop-swarm-coordinator.ts` (lines 77-81)
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/hooks/dist/stop-swarm-coordinator.mjs` (compiled version)

**Test schemas (need updating for consistency):**
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_stop_swarm_coordinator.py` (multiple test fixtures)

**Implementation plan:**
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/thoughts/shared/plans/2025-12-28-user-triggered-agentica.md` (Phase 12.5, 12.7 sections)

---

## Verification Checklist

- [ ] Confirm `completed_tasks` schema currently has no `swarm_id` column
- [ ] Verify Stop hook queries use `WHERE swarm_id = ?` on `completed_tasks`
- [ ] Identify which component should populate `swarm_id` (Phase 12.7)
- [ ] Check if Phase 12.7 implementation is complete
- [ ] Run test to see actual SQL error when executing Stop hook

