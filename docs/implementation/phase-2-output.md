# Phase 2: Agent Count Query - Implementation Summary

**Date:** 2025-12-28
**Plan:** `docs/handoffs/resource-limits-plan.md` (Phase 2)

## Tests Written

**File:** `tests/unit/test_db_utils_agent_count.py`

**Test Classes and Methods:**

1. `TestGetActiveAgentCountExists`
   - `test_db_utils_exports_get_active_agent_count` - Verifies function export exists

2. `TestGetActiveAgentCountBehavior`
   - `test_returns_zero_when_db_does_not_exist` - Returns 0 when no coordination DB
   - `test_returns_zero_when_agents_table_empty` - Returns 0 when agents table has no rows
   - `test_returns_count_of_running_agents` - Returns correct count of running agents
   - `test_does_not_count_completed_or_failed_agents` - Excludes completed/failed agents from count

3. `TestGetActiveAgentCountErrorHandling`
   - `test_returns_zero_on_db_error` - Returns 0 when database is corrupt
   - `test_returns_zero_when_agents_table_missing` - Returns 0 when agents table missing

## Implementation

**File:** `.claude/hooks/src/shared/db-utils.ts`

**Function Added:** `getActiveAgentCount(): number`

**Implementation Details:**
- Uses `runPythonQuery()` pattern from existing db-utils.ts
- Query: `SELECT COUNT(*) FROM agents WHERE status = 'running'`
- Returns 0 on any error (DB missing, corrupt, table missing, query failure)
- Checks file existence with `existsSync()` before attempting query
- Python script checks if agents table exists before querying

**Code Location:** Lines 93-155 of db-utils.ts

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-9.0.2, pluggy-1.6.0
tests/unit/test_db_utils_agent_count.py::TestGetActiveAgentCountExists::test_db_utils_exports_get_active_agent_count PASSED [ 14%]
tests/unit/test_db_utils_agent_count.py::TestGetActiveAgentCountBehavior::test_returns_zero_when_db_does_not_exist PASSED [ 28%]
tests/unit/test_db_utils_agent_count.py::TestGetActiveAgentCountBehavior::test_returns_zero_when_agents_table_empty PASSED [ 42%]
tests/unit/test_db_utils_agent_count.py::TestGetActiveAgentCountBehavior::test_returns_count_of_running_agents PASSED [ 57%]
tests/unit/test_db_utils_agent_count.py::TestGetActiveAgentCountBehavior::test_does_not_count_completed_or_failed_agents PASSED [ 71%]
tests/unit/test_db_utils_agent_count.py::TestGetActiveAgentCountErrorHandling::test_returns_zero_on_db_error PASSED [ 85%]
tests/unit/test_db_utils_agent_count.py::TestGetActiveAgentCountErrorHandling::test_returns_zero_when_agents_table_missing PASSED [100%]

============================== 7 passed in 6.15s ===============================
```

## QLTY Results

```bash
npx tsc --noEmit
# Exit code: 0 (no errors)
```

TypeScript compilation passes with no type errors.

## Issues Encountered

None. Implementation was straightforward using the existing `runPythonQuery()` pattern.

## Files Modified

1. `.claude/hooks/src/shared/db-utils.ts` - Added `getActiveAgentCount()` function
2. `tests/unit/test_db_utils_agent_count.py` - New test file (created)
3. `docs/implementation/phase-2-output.md` - This summary (created)

## Usage Example

```typescript
import { getActiveAgentCount } from './shared/db-utils.ts';

const count = getActiveAgentCount();
console.log(`Active agents: ${count}`);
// Output: Active agents: 3
```

## Next Steps

Phase 3 of resource-limits-plan.md: Extend status.sh to output resources JSON including RAM and agent count to `/tmp/claude-resources-{sessionId}.json`.
