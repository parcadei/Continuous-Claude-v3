# Phase 5: Soft Limit Advisory - Implementation Output

**Completed:** 2025-12-28
**Plan Reference:** `docs/handoffs/resource-limits-plan.md` (Phase 5)

## Summary

Implemented soft limit advisory in the `skill-activation-prompt.ts` hook (UserPromptSubmit event). The hook now reads resource state from `/tmp/claude-resources-{sessionId}.json` and displays warnings when approaching or at agent limits.

## Changes Made

### Modified Files

**`.claude/hooks/src/skill-activation-prompt.ts`**
- Added `ResourceState` interface defining the expected JSON structure:
  - `freeMemMB: number`
  - `activeAgents: number`
  - `maxAgents: number`
  - `contextPct?: number`
- Added `readResourceState()` function to read and parse the resource file
- Added resource advisory logic after existing context warning section:
  - **RESOURCE CRITICAL** when `activeAgents >= maxAgents` (100%+)
  - **RESOURCE WARNING** when `activeAgents >= maxAgents * 0.8` (80-99%)

### New Test File

**`tests/unit/test_soft_limit_advisory.py`**
- 16 test cases covering:
  - Resource file reading
  - Warning threshold at 80%
  - Critical threshold at 100%
  - Output format validation
  - Coexistence with context warnings
  - Edge cases (malformed JSON, missing fields, maxAgents=0, PPID fallback)

## Implementation Details

### Resource File Location

The hook reads from `/tmp/claude-resources-{sessionId}.json` where `sessionId` is determined by:
1. `CLAUDE_SESSION_ID` environment variable (preferred)
2. `CLAUDE_PPID` environment variable (fallback)
3. `'default'` (last resort)

### Warning Thresholds

| Utilization | Alert Level | Message |
|-------------|-------------|---------|
| 80-99% | WARNING | "RESOURCE WARNING: Near limit (X/Y agents)" |
| 100%+ | CRITICAL | "RESOURCE CRITICAL: At limit (X/Y agents)" |
| <80% | None | No resource message |

### Output Format

**CRITICAL (at limit):**
```
==================================================
RESOURCE CRITICAL: At limit (10/10 agents)
Do NOT spawn new agents until existing ones complete.
==================================================
```

**WARNING (near limit):**
```
RESOURCE WARNING: Near limit (8/10 agents)
Only 2 agent slot(s) remaining. Limit spawning.
```

## Test Results

```
============================= 16 passed in 15.65s ==============================
```

All tests pass, including:
- File reading and parsing
- Threshold calculations
- Edge case handling
- Environment variable fallback

## TypeScript Validation

```bash
$ cd .claude/hooks && npx tsc --noEmit
# No errors
```

## Dependencies

This phase depends on:
- **Phase 3** (status.sh): Writes `/tmp/claude-resources-{sessionId}.json`

This phase is consumed by:
- **Phase 6** (pre-tool-use.ts): Hard limit that blocks Task tool

## Notes

1. The `readResourceState()` function is defined inline in `skill-activation-prompt.ts` rather than imported from a shared module. This is intentional to keep the hook self-contained and avoid import complexity during tsx execution.

2. Edge case handling:
   - If resource file is missing: no warning (graceful degradation)
   - If JSON is malformed: no warning (graceful degradation)
   - If `maxAgents` is 0 or missing: no warning (prevents division by zero)
   - If `activeAgents` or `maxAgents` are not numbers: no warning

3. The resource advisory appears **after** the context warning (if any), maintaining the existing output ordering.

## Next Steps

Phase 6: Add hard limit block to PreToolUse hook that prevents Task tool invocation when at limit.
