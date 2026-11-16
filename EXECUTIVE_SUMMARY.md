# Executive Summary: Database Schema Issue

## The Issue (One Sentence)

The Stop hook will crash with "no such column: swarm_id" because the `completed_tasks` table in the actual database schema doesn't have a `swarm_id` column, but the Stop hook queries for it.

---

## Root Cause

**Phase 12.7 (PostToolUse Hook for Task Completion) is not yet implemented.**

The architecture assumes:
1. Phase 12.7 populates `completed_tasks.swarm_id` when tasks complete
2. Stop hook reads `completed_tasks.swarm_id` to count total agents
3. Stop hook reads broadcasts for agents that broadcast "done"
4. Stop hook blocks until all agents complete

But Phase 12.7 hasn't been built, so `completed_tasks.swarm_id` never exists.

---

## Current State

### What Exists
- `broadcasts` table: Has `swarm_id` column ✓
- `agents` table: No `swarm_id` column
- `completed_tasks` table: **No `swarm_id` column** ✗
- Stop hook: Already implemented, queries for `swarm_id` ✓

### What's Missing
- Phase 12.7 PostToolUse hook: Not implemented ✗
- `completed_tasks.swarm_id` column: Not defined ✗
- CoordinationDB.record_task(swarm_id=...) parameter: Not added ✗

---

## Why Tests Pass (False Confidence)

The test file (`tests/unit/test_stop_swarm_coordinator.py`) creates **its own ad-hoc schema** that includes `swarm_id` in `completed_tasks`. This is different from the production schema in `coordination.py`, so tests pass but production code will crash.

---

## The Fix

### Option A (Correct) - Add swarm_id to completed_tasks

**Work:**
1. Update SCHEMA in `scripts/agentica/coordination.py`:
   - Add `swarm_id TEXT` column to `completed_tasks` table
   - Add `CREATE INDEX idx_tasks_swarm ON completed_tasks(swarm_id)`

2. Update `CoordinationDB.record_task()`:
   - Accept `swarm_id` parameter
   - Insert it into database

3. Implement Phase 12.7:
   - Create PostToolUse hook
   - Detect Task tool completions
   - Read `SWARM_ID` environment variable
   - Call `record_task(swarm_id=swarm_id)`

**Result:** Stop hook queries will work correctly

**Files affected:**
- `/scripts/agentica/coordination.py` (schema + method signature)
- `.claude/hooks/src/post-task-complete.ts` (new file - Phase 12.7)

### Option B (Workaround) - Query broadcasts instead

**Won't work:** The broadcasts table doesn't know how many total agents exist, only how many have broadcast "done". There's no way to know the denominator.

### Option C (Hack) - Store swarm info in files

**Wrong approach:** 
- Defeats purpose of coordination.db
- Not idempotent (violates project rules)
- Creates race conditions

---

## Files to Review

**Schema definition:**
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/coordination.py` (lines 35-90)

**Stop hook (will crash):**
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/hooks/src/stop-swarm-coordinator.ts` (lines 77-81)

**Plan (Phase 12.7 pending):**
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/thoughts/shared/plans/2025-12-28-user-triggered-agentica.md` (lines 823-874)

**Test schema (doesn't match production):**
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_stop_swarm_coordinator.py` (lines 109-115)

---

## Recommendation

**Implement Option A** - add `swarm_id` to `completed_tasks` and implement Phase 12.7.

This is the intended design per the plan and maintains data consistency in coordination.db.

**Effort:** ~1-2 hours
- Schema update: 10 minutes
- CoordinationDB update: 15 minutes  
- Phase 12.7 implementation: 30-45 minutes
- Testing: 15 minutes

**Risk:** Low - isolated changes to schema and one new hook

---

## Next Steps

1. Verify analysis is correct with architecture team
2. Decide: implement Option A now or defer Phase 12.7?
3. If proceeding, create implementation plan for Phase 12.7
4. Update tests to match production schema (or leave as-is for phase completion verification)

