# Phase 8: Three-Tier Orphan Detection Query

## Summary

Implemented `find_orphans()` method in `CoordinationDB` with three-tier orphan detection to identify agents that should be cleaned up.

## Implementation Details

### OrphanCandidate Dataclass

Added new dataclass to represent potential orphan agents:

```python
@dataclass
class OrphanCandidate:
    """Candidate orphan agent for cleanup.

    Tiers:
        1: ppid == 1 (true Unix orphan) -> safe to kill immediately
        2: parent_agent_id exists but parent status != 'running' -> kill after 30min
        3: Running > 24h with no recent activity -> kill after timeout
    """
    agent_id: str
    ppid: int | None
    parent_agent_id: str | None
    spawned_at: datetime
    tier: int  # 1=Unix orphan, 2=parent dead, 3=app orphan
    reason: str
```

### find_orphans() Method

Added method to `CoordinationDB` that detects orphans using three tiers:

**Tier 1: Unix Orphans (ppid=1)**
- Processes whose parent died and were adopted by init/launchd
- Detected by checking `ppid = 1` in database
- Safe to kill immediately

**Tier 2: Parent Agent Dead**
- Agents whose parent agent has status != 'running'
- 30-minute grace period before flagging
- Uses JOIN to check parent agent status

**Tier 3: App Orphans**
- Agents running > 24 hours without completion
- Must have `parent_agent_id` set (excludes main sessions)
- Avoids duplicates with tier 1/2

### Safety: Main Session Protection

Critical safety feature: main sessions (where `parent_agent_id IS NULL`) are NEVER flagged as orphans. This prevents accidentally killing the main orchestrating session.

## Files Modified

- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/coordination.py`
  - Added `OrphanCandidate` dataclass
  - Added `find_orphans()` method
  - Added `get_orphan_candidates` alias for plan consistency
  - Schema already includes `ppid` column (from Phase 7)

## Files Created

- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_orphan_detection.py`
  - 12 unit tests covering all tiers and edge cases

## Test Results

```
tests/unit/test_orphan_detection.py::TestOrphanCandidate::test_import_orphan_candidate PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_find_orphans_returns_list PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_tier1_unix_orphan_detection PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_tier2_parent_agent_dead PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_tier2_within_grace_period_not_flagged PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_tier3_app_orphan_running_too_long PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_tier3_recent_agent_not_flagged PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_main_sessions_not_flagged PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_completed_agents_not_flagged PASSED
tests/unit/test_orphan_detection.py::TestFindOrphans::test_orphan_detection_across_sessions PASSED
tests/unit/test_orphan_detection.py::TestRegisterAgentWithPid::test_register_agent_with_pid PASSED
tests/unit/test_orphan_detection.py::TestRegisterAgentWithPid::test_register_agent_pid_default_none PASSED

12 passed in 0.08s
```

## Usage Example

```python
from scripts.agentica.coordination import CoordinationDB

db = CoordinationDB()
orphans = db.find_orphans()

for orphan in orphans:
    print(f"Tier {orphan.tier}: {orphan.agent_id} - {orphan.reason}")

    if orphan.tier == 1:
        # Unix orphan - safe to kill immediately
        pass
    elif orphan.tier == 2:
        # Parent dead - kill after verifying 30min grace
        pass
    elif orphan.tier == 3:
        # App orphan - kill after verifying > 24h
        pass
```

## TDD Process Followed

1. **Red**: Wrote 12 failing tests first
2. **Green**: Implemented `OrphanCandidate` and `find_orphans()` to make tests pass
3. **Refactor**: Added alias `get_orphan_candidates` for plan consistency

## Next Steps

- Phase 9: Add `is_unix_orphan(pid)` function to `watch_agents.py` for external process verification
- Phase 10: Create orphan cleanup script with `--dry-run` and `--tier` flags
