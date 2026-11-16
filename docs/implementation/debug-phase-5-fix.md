# Debug Fix: Phase 5 Code Duplication

**Date:** 2025-12-28
**Issue:** Code duplication in `skill-activation-prompt.ts`
**Status:** FIXED

---

## Problem

Phase 5 (`skill-activation-prompt.ts`) defined its own `ResourceState` interface and `readResourceState()` function instead of importing from the shared module created in Phase 4.

### Evidence of Duplication

**Before fix - skill-activation-prompt.ts (lines 9-38):**
```typescript
// DUPLICATE - should import from shared/resource-reader.ts
interface ResourceState {
    freeMemMB: number;
    activeAgents: number;
    maxAgents: number;
    contextPct?: number;  // Note: optional here, required in shared module
}

function readResourceState(): ResourceState | null {
    const sessionId = process.env.CLAUDE_SESSION_ID || process.env.CLAUDE_PPID || 'default';
    const resourceFile = `/tmp/claude-resources-${sessionId}.json`;
    // ... duplicate implementation
}
```

**Canonical version - shared/resource-reader.ts:**
```typescript
export interface ResourceState {
  freeMemMB: number;
  activeAgents: number;
  maxAgents: number;
  contextPct: number;  // Required, not optional
}

export function readResourceState(): ResourceState | null {
  const sessionId = getSessionId();
  const resourceFile = getResourceFilePath(sessionId);
  // ... with proper default handling
}
```

### Issues with Duplication

1. **DRY Violation:** Same logic in two places
2. **Inconsistency Risk:** Phase 5's `contextPct` was optional (`?`), but Phase 4's was required
3. **Session ID Fallback:** Phase 5 used `'default'` as fallback, Phase 4 used `process.ppid`
4. **Maintenance Burden:** Changes need to be made in two places

---

## Fix Applied

### Change Summary

1. **Removed** duplicate `ResourceState` interface (lines 9-14)
2. **Removed** duplicate `readResourceState()` function (lines 20-38)
3. **Added** import from shared module:
   ```typescript
   import { readResourceState, ResourceState } from './shared/resource-reader.js';
   ```

### Files Modified

| File | Change |
|------|--------|
| `.claude/hooks/src/skill-activation-prompt.ts` | Replaced 30 lines of duplicate code with 1-line import |

### Lines Removed

- Lines 9-14: `interface ResourceState { ... }`
- Lines 20-38: `function readResourceState(): ResourceState | null { ... }`

### Import Added

```typescript
// Import shared resource reader (Phase 4 module)
import { readResourceState, ResourceState } from './shared/resource-reader.js';
```

---

## Verification Steps

1. **TypeScript Compilation:**
   ```bash
   cd .claude/hooks && npx tsc --noEmit
   ```
   Expected: No type errors

2. **Existing Tests:**
   ```bash
   uv run pytest tests/unit/test_soft_limit_advisory.py -v
   ```
   Expected: All 16 tests pass

3. **Manual Test:**
   ```bash
   echo '{"prompt":"test"}' | CLAUDE_PROJECT_DIR="$(pwd)" npx tsx .claude/hooks/src/skill-activation-prompt.ts
   ```
   Expected: No errors (may exit silently if no skill-rules.json found)

---

## Consistency Now Achieved

| Aspect | Before Fix | After Fix |
|--------|------------|-----------|
| ResourceState source | 2 copies | 1 (shared module) |
| contextPct type | Optional in Phase 5 | Required (from shared) |
| Session ID fallback | `'default'` in Phase 5 | `process.ppid` (from shared) |
| readResourceState | 2 implementations | 1 (shared module) |

---

## Related Files

- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/hooks/src/skill-activation-prompt.ts` - Fixed file
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/hooks/src/shared/resource-reader.ts` - Canonical shared module
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/hooks/src/pre-tool-use.ts` - Reference for correct import pattern
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/docs/implementation/review-phases-4-6.md` - Original issue documentation

---

## Prevention

To prevent similar issues in future phases:

1. **Import Check:** Before defining new interfaces/functions, search for existing shared modules
2. **Shared Module Convention:** All reusable code goes in `src/shared/`
3. **Jury Review:** The Jury pattern correctly identified this issue - continue using for code reviews
