# Phase 4 Implementation Output: TypeScript Resource Reader

**Date:** 2025-12-28
**Plan Reference:** `docs/handoffs/resource-limits-plan.md` (Phase 4)

## Summary

Successfully implemented Phase 4 using TDD. Created `resource-reader.ts` - a TypeScript utility that reads the resources JSON file written by `status.sh` (Phase 3) and provides typed access to resource state for downstream hooks.

## Tests Written

**File:** `tests/unit/test_resource_reader.py`

| Test Class | Test Name | Description |
|------------|-----------|-------------|
| `TestResourceReaderFileExists` | `test_resource_reader_ts_exists` | Verifies resource-reader.ts exists in shared directory |
| `TestResourceStateInterface` | `test_exports_resource_state_interface` | Verifies ResourceState interface is exported and usable |
| `TestReadResourceState` | `test_exports_read_resource_state_function` | Verifies readResourceState function is exported |
| `TestReadResourceState` | `test_returns_null_when_file_missing` | Verifies null return when file doesn't exist |
| `TestReadResourceState` | `test_returns_resource_state_when_file_exists` | Verifies correct JSON parsing |
| `TestReadResourceState` | `test_returns_null_on_corrupt_json` | Verifies graceful handling of corrupt JSON |
| `TestReadResourceState` | `test_returns_defaults_on_missing_fields` | Verifies missing fields get default values |
| `TestGetSessionId` | `test_exports_get_session_id_function` | Verifies getSessionId function is exported |
| `TestGetSessionId` | `test_returns_claude_session_id_when_set` | Verifies CLAUDE_SESSION_ID env var is used |
| `TestGetSessionId` | `test_returns_string` | Verifies getSessionId always returns a string |
| `TestDefaultResourceState` | `test_exports_default_resource_state` | Verifies DEFAULT_RESOURCE_STATE is exported |
| `TestDefaultResourceState` | `test_default_values_are_sensible` | Verifies default values are reasonable |
| `TestResourceFilePath` | `test_exports_get_resource_file_path` | Verifies getResourceFilePath function is exported |
| `TestResourceFilePath` | `test_returns_correct_path_format` | Verifies correct path format is returned |
| `TestFileContentAnalysis` | `test_exports_resource_state_interface_in_file` | Verifies interface export in source |
| `TestFileContentAnalysis` | `test_uses_fs_module` | Verifies fs module is imported |
| `TestFileContentAnalysis` | `test_has_freememmb_field` | Verifies freeMemMB field exists |
| `TestFileContentAnalysis` | `test_has_activeagents_field` | Verifies activeAgents field exists |
| `TestFileContentAnalysis` | `test_has_maxagents_field` | Verifies maxAgents field exists |
| `TestFileContentAnalysis` | `test_has_contextpct_field` | Verifies contextPct field exists |

## Implementation

### Created `.claude/hooks/src/shared/resource-reader.ts`

```typescript
/**
 * Resource State Reader Utility
 *
 * Reads resource state JSON from /tmp/claude-resources-{sessionId}.json.
 * This file is written by status.sh (Phase 3) and contains:
 * - freeMemMB: Available RAM in MB
 * - activeAgents: Number of currently running agents
 * - maxAgents: Maximum agents allowed based on RAM
 * - contextPct: Current context usage percentage
 */

import { readFileSync, existsSync } from 'fs';

export interface ResourceState {
  /** Free RAM in MB */
  freeMemMB: number;
  /** Number of currently running agents */
  activeAgents: number;
  /** Maximum agents allowed based on available RAM */
  maxAgents: number;
  /** Current context usage percentage (0-100) */
  contextPct: number;
}

export const DEFAULT_RESOURCE_STATE: ResourceState = {
  freeMemMB: 4096,
  activeAgents: 0,
  maxAgents: 10,
  contextPct: 0,
};

export function getSessionId(): string {
  return process.env.CLAUDE_SESSION_ID || String(process.ppid || process.pid);
}

export function getResourceFilePath(sessionId: string): string {
  return `/tmp/claude-resources-${sessionId}.json`;
}

export function readResourceState(): ResourceState | null {
  const sessionId = getSessionId();
  const resourceFile = getResourceFilePath(sessionId);

  if (!existsSync(resourceFile)) {
    return null;
  }

  try {
    const content = readFileSync(resourceFile, 'utf-8');
    const data = JSON.parse(content);

    return {
      freeMemMB: typeof data.freeMemMB === 'number' ? data.freeMemMB : DEFAULT_RESOURCE_STATE.freeMemMB,
      activeAgents: typeof data.activeAgents === 'number' ? data.activeAgents : DEFAULT_RESOURCE_STATE.activeAgents,
      maxAgents: typeof data.maxAgents === 'number' ? data.maxAgents : DEFAULT_RESOURCE_STATE.maxAgents,
      contextPct: typeof data.contextPct === 'number' ? data.contextPct : DEFAULT_RESOURCE_STATE.contextPct,
    };
  } catch {
    return null;
  }
}
```

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-9.0.2, pluggy-1.6.0
collected 20 items

tests/unit/test_resource_reader.py::TestResourceReaderFileExists::test_resource_reader_ts_exists PASSED
tests/unit/test_resource_reader.py::TestResourceStateInterface::test_exports_resource_state_interface PASSED
tests/unit/test_resource_reader.py::TestReadResourceState::test_exports_read_resource_state_function PASSED
tests/unit/test_resource_reader.py::TestReadResourceState::test_returns_null_when_file_missing PASSED
tests/unit/test_resource_reader.py::TestReadResourceState::test_returns_resource_state_when_file_exists PASSED
tests/unit/test_resource_reader.py::TestReadResourceState::test_returns_null_on_corrupt_json PASSED
tests/unit/test_resource_reader.py::TestReadResourceState::test_returns_defaults_on_missing_fields PASSED
tests/unit/test_resource_reader.py::TestGetSessionId::test_exports_get_session_id_function PASSED
tests/unit/test_resource_reader.py::TestGetSessionId::test_returns_claude_session_id_when_set PASSED
tests/unit/test_resource_reader.py::TestGetSessionId::test_returns_string PASSED
tests/unit/test_resource_reader.py::TestDefaultResourceState::test_exports_default_resource_state PASSED
tests/unit/test_resource_reader.py::TestDefaultResourceState::test_default_values_are_sensible PASSED
tests/unit/test_resource_reader.py::TestResourceFilePath::test_exports_get_resource_file_path PASSED
tests/unit/test_resource_reader.py::TestResourceFilePath::test_returns_correct_path_format PASSED
tests/unit/test_resource_reader.py::TestFileContentAnalysis::test_exports_resource_state_interface_in_file PASSED
tests/unit/test_resource_reader.py::TestFileContentAnalysis::test_uses_fs_module PASSED
tests/unit/test_resource_reader.py::TestFileContentAnalysis::test_has_freememmb_field PASSED
tests/unit/test_resource_reader.py::TestFileContentAnalysis::test_has_activeagents_field PASSED
tests/unit/test_resource_reader.py::TestFileContentAnalysis::test_has_maxagents_field PASSED
tests/unit/test_resource_reader.py::TestFileContentAnalysis::test_has_contextpct_field PASSED

============================== 20 passed in 13.10s ==============================
```

## TypeScript Check Results

```
$ npx tsc --noEmit
(no errors)
```

## Usage Example

```typescript
import { readResourceState } from './shared/resource-reader.js';

const state = readResourceState();
if (state) {
  console.log(`Agents: ${state.activeAgents}/${state.maxAgents}`);
  console.log(`Free RAM: ${Math.round(state.freeMemMB / 1024)}GB`);
  console.log(`Context: ${state.contextPct}%`);

  if (state.activeAgents >= state.maxAgents) {
    console.log('LIMIT REACHED: Cannot spawn more agents');
  }
}
```

## Files Created/Modified

| File | Action |
|------|--------|
| `tests/unit/test_resource_reader.py` | Created (20 tests) |
| `.claude/hooks/src/shared/resource-reader.ts` | Created |
| `docs/implementation/phase-4-output.md` | Created (this file) |

## Key Design Decisions

1. **Returns null for missing/corrupt files**: Rather than throwing errors, the function returns null when the resource file doesn't exist or contains invalid JSON. This allows consuming code to handle missing state gracefully.

2. **Default values for missing fields**: When the JSON file exists but is missing some fields, we merge with sensible defaults rather than returning null. This handles partial data from older versions of status.sh.

3. **Session ID fallback chain**: Uses `CLAUDE_SESSION_ID` if set, otherwise falls back to `process.ppid || process.pid`. This matches the behavior of status.sh which uses `${CLAUDE_SESSION_ID:-$PPID}`.

4. **Pure TypeScript with fs module**: Uses Node.js fs module directly for file operations, avoiding external dependencies. The implementation is synchronous since it reads a small local file.

## Issues Encountered

None. Implementation proceeded smoothly following TDD approach.

## Next Steps

Phase 5 and 6 can now use this utility:
- Phase 5: Add soft limit advisory to `skill-activation-prompt.ts`
  ```typescript
  import { readResourceState } from './shared/resource-reader.js';
  const resources = readResourceState();
  // Inject warning when approaching limits
  ```
- Phase 6: Add hard limit block to `pre-tool-use.ts`
  ```typescript
  import { readResourceState } from './shared/resource-reader.js';
  const state = readResourceState();
  if (state && state.activeAgents >= state.maxAgents) {
    return { result: 'block', reason: 'Resource limit reached' };
  }
  ```
