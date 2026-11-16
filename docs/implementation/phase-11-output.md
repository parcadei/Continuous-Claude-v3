# Phase 11: Add Orphan Check to SessionEnd Hook

**Completed:** 2025-12-28

## Summary

Implemented orphan cleanup trigger in the SessionEnd hook using a fire-and-forget pattern. At the end of each main session, the hook spawns `cleanup_orphans.py --kill --tier 1` to clean up true Unix orphans (processes whose parent has died, ppid=1).

## TDD Process

### 1. Failing Tests Created

Created `tests/unit/test_session_end_orphan_check.py` with 11 tests covering:
- Hook file existence
- Cleanup script existence
- Fire-and-forget pattern (spawn import, detached mode, unref())
- Cleanup script invocation with `--kill --tier 1` flags
- Logging of cleanup trigger
- Hook execution returns `continue`
- CLI argument acceptance for cleanup script

### 2. Tests Initially Failed

Three tests failed as expected:
- `test_hook_calls_cleanup_orphans_with_tier_1` - No reference to cleanup_orphans.py
- `test_hook_uses_detached_mode` - No detached spawning
- `test_hook_uses_unref` - No unref() call

### 3. Implementation

Modified `.claude/hooks/src/session-end-cleanup-swarms.ts`:

1. **Added spawn import:**
   ```typescript
   import { spawn, spawnSync } from 'child_process';
   ```

2. **Added fire-and-forget orphan cleanup:**
   ```typescript
   const cleanupScript = join(projectDir, 'scripts', 'agentica', 'cleanup_orphans.py');
   if (existsSync(cleanupScript)) {
       const orphanCleanup = spawn('uv', [
           'run', 'python', cleanupScript,
           '--kill', '--tier', '1'
       ], {
           detached: true,
           stdio: 'ignore',
           cwd: projectDir,
       });
       orphanCleanup.unref();
       console.error('SessionEnd: Triggered tier-1 orphan cleanup (fire-and-forget)');
   }
   ```

### 4. All Tests Pass

```
============================== 11 passed in 0.36s ==============================
```

## Key Design Decisions

### Fire-and-Forget Pattern
- **`detached: true`**: Child process runs independently of parent
- **`stdio: 'ignore'`**: No pipe connections to block on
- **`.unref()`**: Parent process can exit without waiting for child

### Tier 1 Only
Only cleans up true Unix orphans (ppid=1) at session end because:
- These are definitively orphaned (parent process died)
- Safe to kill immediately without grace period
- Tier 2/3 require longer grace periods handled elsewhere

### Error Handling
- Cleanup is best-effort, wrapped in try/catch
- Session end never blocked by cleanup failures
- Errors logged to stderr for debugging

## Files Modified

| File | Change |
|------|--------|
| `.claude/hooks/src/session-end-cleanup-swarms.ts` | Added fire-and-forget orphan cleanup spawn |

## Files Created

| File | Purpose |
|------|---------|
| `tests/unit/test_session_end_orphan_check.py` | Unit tests for SessionEnd orphan check |

## Test Command

```bash
uv run pytest tests/unit/test_session_end_orphan_check.py -v
```

## Integration Points

- **Depends on:** Phase 10 (`cleanup_orphans.py` script)
- **Triggered by:** Claude Code SessionEnd hook
- **Affects:** Orphaned agent processes with ppid=1

## Next Steps

- Phase 12: Add `--orphans` flag to `watch_agents.py` for visibility
- Phase 13: Add agent count to status line
- Phase 14: Integration test suite
