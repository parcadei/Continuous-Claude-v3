# Phase 14: End-to-End Integration Tests

## Summary

Phase 14 implements comprehensive E2E integration tests for the resource management and orphan detection systems. These tests verify the complete flow from status.sh writing resource data to hooks reading it and taking action.

## Test Files Created

### 1. test_resource_limits_e2e.py (15 tests)

Tests the complete resource management pipeline:

**TestStatusShWritesResourcesJson (4 tests)**
- `test_status_sh_writes_resources_json` - Verifies JSON output format
- `test_max_agents_formula_with_low_ram` - Verifies formula: (RAM - 2GB) / 500MB
- `test_max_agents_formula_with_high_ram` - Verifies maxAgents capped at 20
- `test_context_pct_written_to_separate_file` - Verifies context percentage file

**TestSkillActivationResourceWarnings (4 tests)**
- `test_no_warning_when_below_threshold` - No warning at <80% utilization
- `test_warning_when_near_limit` - WARNING at 80-99% utilization
- `test_critical_when_at_limit` - CRITICAL at 100% utilization
- `test_no_warning_when_resource_file_missing` - Graceful degradation

**TestPreToolUseResourceBlock (5 tests)**
- `test_task_continues_when_below_limit` - Task allowed below limit
- `test_task_blocked_when_at_limit` - Task blocked at limit
- `test_task_blocked_when_over_limit` - Task blocked over limit
- `test_other_tools_not_blocked` - Read/Write tools not affected
- `test_task_continues_when_resource_file_missing` - Graceful degradation

**TestFullResourcePipeline (2 tests)**
- `test_full_flow_status_to_block` - Complete pipeline: status.sh -> JSON -> block
- `test_full_flow_status_to_warning_to_continue` - High utilization warning flow

### 2. test_orphan_detection_e2e.py (20 tests)

Tests the three-tier orphan detection system:

**TestIsUnixOrphan (4 tests)**
- `test_current_process_not_orphan` - Current process is not orphan
- `test_init_process_is_special` - PID 1 handling
- `test_nonexistent_process_not_orphan` - Non-existent process handling
- `test_invalid_pid_not_orphan` - Invalid PID handling

**TestAgentRegistrationWithPid (3 tests)**
- `test_register_agent_with_pid_ppid` - PID/PPID storage
- `test_register_agent_without_pid` - Backwards compatibility
- `test_agent_record_preserves_pid_ppid` - Query retrieval

**TestFindOrphansClassification (5 tests)**
- `test_tier1_unix_orphan_ppid_1` - Tier 1: ppid=1 detection
- `test_tier2_parent_agent_dead` - Tier 2: Dead parent + 30min grace
- `test_tier3_app_orphan_running_24h` - Tier 3: Running >24h
- `test_main_session_not_orphan` - Main sessions excluded
- `test_running_child_with_running_parent_not_orphan` - Active children excluded

**TestCleanupOrphansScript (3 tests)**
- `test_dry_run_lists_orphans` - --dry-run shows but doesn't kill
- `test_tier_filter` - --tier N filters by tier
- `test_no_orphans_message` - "No orphans found" message

**TestWatchAgentsOrphans (3 tests)**
- `test_orphans_flag_shows_orphans` - --orphans displays orphans
- `test_orphans_json_output` - --orphans --json format
- `test_no_orphans_message_watch` - "No orphans" message

**TestFullOrphanPipeline (2 tests)**
- `test_full_orphan_lifecycle` - Register -> detect -> report flow
- `test_multi_tier_detection` - All three tiers detected simultaneously

### 3. test_status_line_e2e.py (15 tests)

Tests the status.sh display output:

**TestStatusLineFormat (2 tests)**
- `test_basic_output_format` - Token count and percentage display
- `test_context_percentage_calculation` - Context window calculation

**TestResourceDisplay (3 tests)**
- `test_no_resource_display_below_50_percent` - Hidden below 50%
- `test_resource_display_at_50_percent` - Visible at 50%+
- `test_resource_display_at_high_utilization` - Visible at 90%

**TestColorCoding (5 tests)**
- `test_green_at_low_context` - Green below 60%
- `test_yellow_at_medium_context` - Yellow at 60-80%
- `test_red_at_high_context` - Red at 80%+
- `test_yellow_agents_at_medium_utilization` - Yellow agent display
- `test_red_agents_at_high_utilization` - Red agent display

**TestStatusLineEdgeCases (5 tests)**
- `test_zero_active_agents` - 0 agents handling
- `test_empty_json_input` - Empty JSON input
- `test_malformed_json_input` - Invalid JSON graceful handling
- `test_very_high_agent_count` - Agent count above max
- `test_writes_correct_json_format` - JSON format validation

## Test Results

```
tests/integration/test_resource_limits_e2e.py    15 passed
tests/integration/test_orphan_detection_e2e.py   20 passed
tests/integration/test_status_line_e2e.py        15 passed
-------------------------------------------------
Total:                                           50 passed
```

## Environment Setup

Tests use:
- `MOCK_FREE_MEM_MB` - Mock free memory for status.sh
- `MOCK_ACTIVE_AGENTS` - Mock active agent count
- `CLAUDE_SESSION_ID` - Session ID for resource file path
- Temporary skill-rules.json for skill-activation tests
- Temporary coordination.db for orphan detection tests

## Key Implementation Notes

1. **TypeScript Compilation Required**: The hooks must be compiled with `npx tsc` before tests run. Tests look for `.js` files first (compiled output), then `.mjs` (legacy).

2. **Session ID Resolution**: The resource-reader.ts uses `CLAUDE_SESSION_ID` environment variable, falling back to `process.ppid`.

3. **skill-rules.json Dependency**: The skill-activation-prompt hook exits early if no skill-rules.json exists. Tests create a minimal one for resource warning tests.

4. **Database Locking**: Tests that mix CoordinationDB usage with raw sqlite3 connections must be careful about database locking. Register all agents via CoordinationDB before opening raw connections.

5. **Cleanup**: Tests use pytest's `tmp_path` fixture and cleanup fixtures to remove temporary files.

## Files Modified

- `.claude/hooks/dist/*.js` - Recompiled TypeScript hooks

## Files Created

- `tests/integration/test_resource_limits_e2e.py`
- `tests/integration/test_orphan_detection_e2e.py`
- `tests/integration/test_status_line_e2e.py`
- `docs/implementation/phase-14-output.md`
