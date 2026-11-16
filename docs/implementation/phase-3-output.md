# Phase 3 Implementation Output: Extend status.sh

**Date:** 2025-12-28
**Plan Reference:** `docs/handoffs/resource-limits-plan.md` (Phase 3)

## Summary

Successfully implemented Phase 3 using TDD. The `status.sh` script now outputs a resources JSON file to `/tmp/claude-resources-{session_id}.json` containing RAM availability, active agent count, and calculated max agents limit.

## Tests Written

**File:** `tests/unit/test_status_resources.py`

| Test Class | Test Name | Description |
|------------|-----------|-------------|
| `TestStatusShWritesResourcesJson` | `test_status_sh_exists` | Verifies status.sh exists |
| `TestStatusShWritesResourcesJson` | `test_status_sh_creates_resources_json` | Verifies resources JSON file is created |
| `TestStatusShWritesResourcesJson` | `test_resources_json_is_valid_json` | Verifies output is valid JSON |
| `TestResourcesJsonContainsRequiredFields` | `test_resources_contains_free_mem_mb` | Verifies freeMemMB field exists and is positive |
| `TestResourcesJsonContainsRequiredFields` | `test_resources_contains_active_agents` | Verifies activeAgents field exists and is non-negative |
| `TestResourcesJsonContainsRequiredFields` | `test_resources_contains_max_agents` | Verifies maxAgents field exists and >= 1 |
| `TestResourcesJsonContainsRequiredFields` | `test_resources_contains_context_pct` | Verifies contextPct field exists and is 0-100 |
| `TestMaxAgentsCalculation` | `test_max_agents_follows_formula` | Verifies (freeMemMB - 2048) / 500 formula |
| `TestMaxAgentsCalculation` | `test_max_agents_minimum_is_1` | Verifies floor of 1 |
| `TestMaxAgentsCalculation` | `test_max_agents_maximum_is_20` | Verifies ceiling of 20 |
| `TestGetResourcesShScript` | `test_get_resources_sh_exists` | Verifies helper script exists |
| `TestGetResourcesShScript` | `test_get_resources_sh_is_executable` | Verifies executable permissions |
| `TestGetResourcesShScript` | `test_get_resources_sh_outputs_json` | Verifies JSON output with freeMemMB/totalMemMB |
| `TestGetResourcesShScript` | `test_get_resources_sh_returns_positive_values` | Verifies positive memory values |
| `TestCoordinationDBGlobalRunningCount` | `test_coordination_db_has_global_running_count` | Verifies method exists |
| `TestCoordinationDBGlobalRunningCount` | `test_global_running_count_returns_int` | Verifies returns integer |
| `TestCoordinationDBGlobalRunningCount` | `test_global_running_count_includes_all_sessions` | Verifies counts across all sessions |
| `TestCoordinationDBGlobalRunningCount` | `test_global_running_count_excludes_completed` | Verifies excludes completed agents |

## Implementation Changes

### 1. Created `.claude/scripts/get-resources.sh` (Phase 1 prerequisite)

```diff
+ #!/bin/bash
+ # Cross-platform RAM detection utility
+ # Outputs JSON: {"freeMemMB": N, "totalMemMB": N}
+
+ if [[ "$OSTYPE" == "darwin"* ]]; then
+     # macOS: use vm_stat for free memory
+     page_size=4096
+     free_pages=$(vm_stat | grep "Pages free" | awk '{print $3}' | tr -d '.')
+     inactive_pages=$(vm_stat | grep "Pages inactive" | awk '{print $3}' | tr -d '.')
+     speculative_pages=$(vm_stat | grep "Pages speculative" | awk '{print $3}' | tr -d '.')
+     available_pages=$((free_pages + inactive_pages + speculative_pages))
+     free_mb=$((available_pages * page_size / 1024 / 1024))
+     total_mb=$(($(sysctl -n hw.memsize) / 1024 / 1024))
+ else
+     # Linux: use /proc/meminfo
+     free_mb=$(grep MemAvailable /proc/meminfo | awk '{print int($2/1024)}')
+     total_mb=$(grep MemTotal /proc/meminfo | awk '{print int($2/1024)}')
+ fi
+
+ echo "{\"freeMemMB\": $free_mb, \"totalMemMB\": $total_mb}"
```

### 2. Added `get_global_running_count()` to `scripts/agentica/coordination.py` (Phase 2 prerequisite)

```diff
+     def get_global_running_count(self) -> int:
+         """Count ALL running agents across all sessions.
+
+         Returns:
+             Total count of agents with status='running' across all sessions.
+         """
+         with self._get_conn() as conn:
+             return conn.execute(
+                 "SELECT COUNT(*) FROM agents WHERE status = 'running'"
+             ).fetchone()[0]
```

### 3. Extended `.claude/scripts/status.sh` (Phase 3)

```diff
  # Write for hooks (per-session to avoid multi-instance conflicts)
  session_id="${CLAUDE_SESSION_ID:-$PPID}"
  echo "$context_pct" > "/tmp/claude-context-pct-${session_id}.txt"

+ # ─────────────────────────────────────────────────────────────────
+ # RESOURCES - RAM and agent limits for resource management hooks
+ # ─────────────────────────────────────────────────────────────────
+ script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
+
+ # Get system memory info
+ resources=$(bash "$script_dir/get-resources.sh" 2>/dev/null || echo '{"freeMemMB": 4096}')
+ free_mem=$(echo "$resources" | jq -r '.freeMemMB // 4096')
+
+ # Calculate max agents: (freeRAM - 2GB safety) / 500MB per agent
+ safety_mb=2048
+ per_agent_mb=500
+ max_agents=$(( (free_mem - safety_mb) / per_agent_mb ))
+ [[ "$max_agents" -lt 1 ]] && max_agents=1
+ [[ "$max_agents" -gt 20 ]] && max_agents=20
+
+ # Get active agent count via Python coordination DB
+ active_agents=$(uv run python -c "
+ from scripts.agentica.coordination import CoordinationDB
+ print(CoordinationDB().get_global_running_count())
+ " 2>/dev/null || echo "0")
+
+ # Write resources JSON for downstream hooks
+ echo "{\"freeMemMB\": $free_mem, \"activeAgents\": $active_agents, \"maxAgents\": $max_agents, \"contextPct\": $context_pct}" > "/tmp/claude-resources-${session_id}.json"
```

## Test Results

```
============================= test session starts ==============================
collected 18 items

tests/unit/test_status_resources.py::TestStatusShWritesResourcesJson::test_status_sh_exists PASSED
tests/unit/test_status_resources.py::TestStatusShWritesResourcesJson::test_status_sh_creates_resources_json PASSED
tests/unit/test_status_resources.py::TestStatusShWritesResourcesJson::test_resources_json_is_valid_json PASSED
tests/unit/test_status_resources.py::TestResourcesJsonContainsRequiredFields::test_resources_contains_free_mem_mb PASSED
tests/unit/test_status_resources.py::TestResourcesJsonContainsRequiredFields::test_resources_contains_active_agents PASSED
tests/unit/test_status_resources.py::TestResourcesJsonContainsRequiredFields::test_resources_contains_max_agents PASSED
tests/unit/test_status_resources.py::TestResourcesJsonContainsRequiredFields::test_resources_contains_context_pct PASSED
tests/unit/test_status_resources.py::TestMaxAgentsCalculation::test_max_agents_follows_formula PASSED
tests/unit/test_status_resources.py::TestMaxAgentsCalculation::test_max_agents_minimum_is_1 PASSED
tests/unit/test_status_resources.py::TestMaxAgentsCalculation::test_max_agents_maximum_is_20 PASSED
tests/unit/test_status_resources.py::TestGetResourcesShScript::test_get_resources_sh_exists PASSED
tests/unit/test_status_resources.py::TestGetResourcesShScript::test_get_resources_sh_is_executable PASSED
tests/unit/test_status_resources.py::TestGetResourcesShScript::test_get_resources_sh_outputs_json PASSED
tests/unit/test_status_resources.py::TestGetResourcesShScript::test_get_resources_sh_returns_positive_values PASSED
tests/unit/test_status_resources.py::TestCoordinationDBGlobalRunningCount::test_coordination_db_has_global_running_count PASSED
tests/unit/test_status_resources.py::TestCoordinationDBGlobalRunningCount::test_global_running_count_returns_int PASSED
tests/unit/test_status_resources.py::TestCoordinationDBGlobalRunningCount::test_global_running_count_includes_all_sessions PASSED
tests/unit/test_status_resources.py::TestCoordinationDBGlobalRunningCount::test_global_running_count_excludes_completed PASSED

============================== 18 passed in 1.49s ==============================
```

## Shellcheck Results

```
In .claude/scripts/status.sh line 87:
ledger=$(ls -t "$project_dir"/CONTINUITY_CLAUDE-*.md 2>/dev/null | head -1)
         ^-- SC2012 (info): Use find instead of ls to better handle non-alphanumeric filenames.
```

**Note:** This is an info-level warning in pre-existing code (not introduced by Phase 3 changes). The new resource-related code passes shellcheck without any warnings.

## Output File Example

After running `status.sh`, the file `/tmp/claude-resources-{session_id}.json` contains:

```json
{"freeMemMB": 21165, "activeAgents": 0, "maxAgents": 20, "contextPct": 55}
```

## Files Created/Modified

| File | Action |
|------|--------|
| `tests/unit/test_status_resources.py` | Created (18 tests) |
| `.claude/scripts/get-resources.sh` | Created (Phase 1 prerequisite) |
| `scripts/agentica/coordination.py` | Modified (added `get_global_running_count`) |
| `.claude/scripts/status.sh` | Modified (added resources section) |
| `docs/implementation/phase-3-output.md` | Created (this file) |

## Issues Encountered

None. Implementation proceeded smoothly following TDD approach.

## Next Steps

Phase 4 and beyond can now build on this foundation:
- Phase 4: Create TypeScript resource reader utility
- Phase 5: Add soft limit advisory to `skill-activation-prompt.ts`
- Phase 6: Add hard limit block to `pre-tool-use.ts`
