# Code Locations: Schema Issue References

## Schema Definition
**File:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/coordination.py`

**Lines 35-90:** SCHEMA constant
```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    premise TEXT,
    model TEXT,
    scope_keys TEXT,
    pattern TEXT,
    parent_agent_id TEXT,
    spawned_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    error_message TEXT
);

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
**Issue:** `completed_tasks` has no `swarm_id` column

**Lines 273-289:** `record_task()` method
```python
def record_task(
    self,
    agent_id: str,
    input_text: str,
    output: Any,
    duration_ms: int,
    pattern: str | None = None,
    artifacts: dict[str, Any] | None = None,
) -> TaskRecord:
```
**Issue:** Doesn't accept `swarm_id` parameter

---

## Stop Hook Implementation
**File:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/hooks/src/stop-swarm-coordinator.ts`

**Lines 77-81:** The failing SQL query
```typescript
cursor = conn.execute('''
    SELECT COUNT(DISTINCT agent_id) as total_count
    FROM completed_tasks
    WHERE swarm_id = ?
''', (swarm_id,))
```
**Issue:** `completed_tasks.swarm_id` doesn't exist

**Lines 68-73:** This query works
```typescript
cursor = conn.execute('''
    SELECT COUNT(DISTINCT sender_agent) as done_count
    FROM broadcasts
    WHERE swarm_id = ? AND broadcast_type = 'done'
''', (swarm_id,))
```
**Status:** OK - broadcasts table has `swarm_id`

---

## Test Schema (False Confidence)
**File:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_stop_swarm_coordinator.py`

**Lines 109-115:** Test creates different schema
```python
CREATE TABLE IF NOT EXISTS completed_tasks (
    id TEXT PRIMARY KEY,
    swarm_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    task_prompt TEXT NOT NULL,
    completed_at TEXT NOT NULL
);
```
**Issue:** Test schema doesn't match production schema
- Includes `swarm_id` (production doesn't)
- Uses `task_prompt` (production uses different fields)

**Line 124-125:** Test inserts with swarm_id
```python
conn.execute(
    "INSERT INTO completed_tasks VALUES (?, ?, ?, ?, ?)",
    (uuid4().hex[:12], swarm_id, agent, f"Task for {agent}", now)
)
```

---

## Plan Documentation
**File:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/thoughts/shared/plans/2025-12-28-user-triggered-agentica.md`

**Lines 675-821:** Phase 12.5 - Stop Hook for Swarm Completion
- Describes stop hook behavior
- Contains the problematic SQL query (lines 757-761)

**Lines 823-874:** Phase 12.7 - PostToolUse Hook for Task Completion
- Status: PENDING
- Supposed to populate `completed_tasks.swarm_id`
- **NOT YET IMPLEMENTED**

**Lines 1-100:** Architecture diagram
- Shows flow of swarm coordination
- Implies swarm_id tracking throughout

---

## Architecture Files

**broadcasts table** (working):
- File: `scripts/agentica/coordination.py` lines 79-90
- Has `swarm_id` column
- Has methods: `create_broadcast()`, `get_broadcasts()`
- Status: ✓ Fully implemented

**agents table** (partial):
- File: `scripts/agentica/coordination.py` lines 36-48
- Missing `swarm_id` column
- Has `pattern` (which contains swarm name, not ID)
- Status: Can register agents but no swarm linkage

**completed_tasks table** (broken):
- File: `scripts/agentica/coordination.py` lines 50-61
- Missing `swarm_id` column
- Has `record_task()` method but can't record swarm ID
- Status: Incomplete - can't track tasks by swarm

---

## CoordinationDB Methods
**File:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/coordination.py`

**Lines 186-231:** `register_agent()` - No swarm_id
**Lines 233-250:** `complete_agent()` - No swarm_id
**Lines 252-321:** `record_task()` - No swarm_id parameter
**Lines 323-345:** `get_running_agents()` - Can't filter by swarm_id
**Lines 347-376:** `get_completed_tasks()` - Can't filter by swarm_id
**Lines 378-415:** `get_session_summary()` - No swarm breakdown
**Lines 449-494:** `create_broadcast()` - ✓ Has swarm_id
**Lines 496-535:** `get_broadcasts()` - ✓ Can filter by swarm_id

---

## What Needs to Be Changed

### 1. Schema (coordination.py)
- Add `swarm_id TEXT` column to `completed_tasks` table
- Add `CREATE INDEX idx_tasks_swarm ON completed_tasks(swarm_id)`
- Make `swarm_id` nullable (for non-swarm tasks)

### 2. CoordinationDB (coordination.py)
- Update `record_task()` signature to accept `swarm_id` parameter
- Update `INSERT INTO completed_tasks` to include swarm_id
- Update `get_completed_tasks()` to accept swarm_id filter

### 3. Phase 12.7 Implementation
- Create `.claude/hooks/post-task-complete.ts`
- Detect Task tool completions
- Read `SWARM_ID` environment variable
- Call `record_task(swarm_id=swarm_id)`

### 4. Tests (coordination.py)
- Don't change test schemas
- Tests will automatically pass once production schema is fixed

---

## Verification Steps

1. **Confirm the issue:**
   ```bash
   grep -n "WHERE swarm_id = ?" .claude/hooks/src/stop-swarm-coordinator.ts
   # Should show line 80 in completed_tasks query
   ```

2. **Check schema:**
   ```bash
   grep -A 10 "CREATE TABLE IF NOT EXISTS completed_tasks" scripts/agentica/coordination.py
   # Should NOT show swarm_id column
   ```

3. **Check broadcasts table:**
   ```bash
   grep -A 10 "CREATE TABLE IF NOT EXISTS broadcasts" scripts/agentica/coordination.py
   # Should show swarm_id column exists
   ```

4. **Verify test mismatch:**
   ```bash
   grep -A 5 "CREATE TABLE IF NOT EXISTS completed_tasks" tests/unit/test_stop_swarm_coordinator.py
   # Should show swarm_id in test (different from production)
   ```

