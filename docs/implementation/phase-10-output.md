# Phase 10: Orphan Cleanup Script - Implementation Summary

## Overview

Implemented the orphan cleanup script as specified in the resource-limits-plan.md, using Test-Driven Development (TDD). This phase also required implementing Phase 8 (`OrphanCandidate`, `get_orphan_candidates()`) and Phase 9 (`is_unix_orphan()`) dependencies.

## Files Created/Modified

### New Files

1. **`scripts/agentica/cleanup_orphans.py`**
   - Standalone cleanup script with three-tier orphan detection
   - CLI with `--dry-run` (default), `--kill`, `--tier N`, `--session` flags
   - Uses `find_orphans()` from coordination.py and `is_unix_orphan()` from watch_agents.py
   - Logs actions taken and marks killed agents in database

2. **`tests/unit/test_cleanup_orphans.py`**
   - 22 unit tests covering:
     - OrphanCandidate dataclass
     - Three-tier detection logic
     - is_unix_orphan() function
     - cleanup_orphans() function
     - CLI argument parsing

### Modified Files

1. **`scripts/agentica/coordination.py`**
   - Added `ppid` column to agents table schema
   - Added migration for existing databases
   - Added `OrphanCandidate` dataclass
   - Added `find_orphans()` / `get_orphan_candidates()` method
   - Updated `register_agent()` to accept `ppid` parameter
   - Updated `AgentRecord` dataclass with `ppid` field
   - Updated `_row_to_agent()` to handle `ppid`

2. **`scripts/agentica/watch_agents.py`**
   - `is_unix_orphan()` function already existed (Phase 9 was pre-implemented)

## Three-Tier Orphan Detection

| Tier | Condition | Action | Grace Period |
|------|-----------|--------|--------------|
| 1 | `ppid = 1` (Unix orphan) | Kill immediately | None |
| 2 | Parent agent not running | Kill after grace | 30 minutes |
| 3 | Running > 24h | Kill after timeout | 24 hours |

### Safety Features

- Main sessions excluded (parent_agent_id IS NULL AND ppid != 1)
- Completed agents excluded
- Dry-run mode enabled by default
- Tier 1 requires runtime verification via `is_unix_orphan()`

## Test Results

```
22 passed in 0.16s
```

All tests pass, covering:
- Dataclass field validation
- Three-tier detection logic
- Grace period handling
- Main session exclusion
- CLI argument parsing
- Kill mode with mocked signals
- Error handling (ProcessLookupError, PermissionError)

## Usage

```bash
# Dry-run (default) - report orphans without killing
uv run python scripts/agentica/cleanup_orphans.py --dry-run

# Kill only Tier 1 Unix orphans (safest)
uv run python scripts/agentica/cleanup_orphans.py --kill --tier 1

# Kill all orphans
uv run python scripts/agentica/cleanup_orphans.py --kill

# Filter by tier
uv run python scripts/agentica/cleanup_orphans.py --tier 2
```

## Example Output

```
============================================================
Orphan Agent Cleanup
============================================================
Mode: DRY-RUN
------------------------------------------------------------
[DRY-RUN] Tier 1: agent-abc123 - ppid=1 (parent process died)
[DRY-RUN] Tier 2: agent-def456 - Parent agent completed/failed (30min grace expired)
------------------------------------------------------------
Dry run complete. 2 orphan(s) would be cleaned up.
Run with --kill to actually terminate orphan processes.
============================================================
```

## Database Schema Changes

Added `ppid` column:

```sql
ALTER TABLE agents ADD COLUMN ppid INTEGER;
```

Migration is idempotent - safe to run multiple times.

## Integration Points

- Called from SessionEnd hook (Phase 11) to auto-clean Tier 1 orphans
- Can be run manually for maintenance
- Supports `--orphans` flag in watch_agents.py (Phase 12)

## TDD Process Followed

1. Wrote failing tests first (22 tests)
2. Confirmed tests failed due to missing imports
3. Implemented OrphanCandidate dataclass
4. Implemented get_orphan_candidates() method
5. Verified is_unix_orphan() already existed
6. Created cleanup_orphans.py script
7. Fixed one test mock issue
8. All 22 tests pass

## Risks Mitigated

- **False positives**: Grace periods prevent premature kills
- **Main session safety**: Explicit exclusion in SQL queries
- **Permission errors**: Handled gracefully, logged
- **Process already dead**: Returns False, marks agent as killed
