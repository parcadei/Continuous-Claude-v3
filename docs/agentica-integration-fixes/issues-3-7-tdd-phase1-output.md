# TDD Phase 1: Current Test State for Issues 3-7

Generated: 2025-12-29

## Summary

All affected tests currently **PASS**, which means the issues are about test quality, not test failures. The fixes will strengthen assertions and remove dead code without changing pass/fail status.

## Issue 3: Unused asyncio.Lock() (test_unified_scope_e2e.py:583)

**File:** `tests/integration/test_unified_scope_e2e.py`
**Location:** Line 583

**Current state:** Line exists as documented:
```
583:        lock = asyncio.Lock()
```

**Test class:** `TestE2EConcurrentAgents`
**Test status:** Tests FAIL but for unrelated reasons (database locking issues, not the unused variable)

```
tests/integration/test_unified_scope_e2e.py::TestE2EConcurrentAgents::test_e2e_concurrent_agents FAILED
  - Concurrent write success rate 54.0% below threshold 80%
  - Root cause: "database is locked" errors

tests/integration/test_unified_scope_e2e.py::TestE2EConcurrentAgents::test_e2e_concurrent_task_creation FAILED
  - Root cause: asyncio.run() called from running event loop
```

**Action:** Remove unused `lock = asyncio.Lock()` line (dead code removal).

---

## Issue 4: Weak Assertion (test_crud_patterns_batch2.py:148)

**File:** `tests/unit/test_crud_patterns_batch2.py`
**Location:** Line 148

**Current state:** Line exists as documented:
```
148:        assert "combined" in result.lower() or result is not None
```

**Test class:** `TestMapReducePatternBatch2`
**Test status:** All 5 tests PASS

```
tests/unit/test_crud_patterns_batch2.py::TestMapReducePatternBatch2::test_map_phase_spawns_correct_number_of_mappers PASSED
tests/unit/test_crud_patterns_batch2.py::TestMapReducePatternBatch2::test_chunks_distributed_to_mappers_correctly PASSED
tests/unit/test_crud_patterns_batch2.py::TestMapReducePatternBatch2::test_reducer_receives_all_mapper_outputs PASSED
tests/unit/test_crud_patterns_batch2.py::TestMapReducePatternBatch2::test_handles_mapper_failure_with_fail_fast_false PASSED
tests/unit/test_crud_patterns_batch2.py::TestMapReducePatternBatch2::test_mapper_prompt_contains_chunk_data PASSED
```

**Problem:** The assertion `"combined" in result.lower() or result is not None` always passes because `result is not None` is always true after `await mr.execute()`.

**Action:** Split into two assertions to actually verify the "combined" content.

---

## Issue 5: Unused mock_spawn Fixture (test_crud_patterns_batch2.py:522-543)

**File:** `tests/unit/test_crud_patterns_batch2.py`
**Test:** `TestChainOfResponsibilityPatternBatch2::test_raises_error_when_no_handler_matches`

**Test status:** PASS

```
tests/unit/test_crud_patterns_batch2.py::TestChainOfResponsibilityPatternBatch2::test_raises_error_when_no_handler_matches PASSED
```

**Problem:** The `mock_spawn` fixture is used for test isolation but never verified. When no handler matches, no spawn should occur.

**Action:** Add `mock_spawn.assert_not_called()` to verify expected behavior.

---

## Issue 6: Weak Prompt Assertion (test_crud_patterns_batch2.py:780-786)

**File:** `tests/unit/test_crud_patterns_batch2.py`
**Test class:** `TestBlackboardPatternBatch2`

**Test status:** All 5 tests PASS

```
tests/unit/test_crud_patterns_batch2.py::TestBlackboardPatternBatch2::test_specialists_write_to_blackboard_state PASSED
tests/unit/test_crud_patterns_batch2.py::TestBlackboardPatternBatch2::test_iteration_continues_until_controller_approves PASSED
tests/unit/test_crud_patterns_batch2.py::TestBlackboardPatternBatch2::test_max_iterations_prevents_infinite_loop PASSED
tests/unit/test_crud_patterns_batch2.py::TestBlackboardPatternBatch2::test_state_history_preserved_across_iterations PASSED
tests/unit/test_crud_patterns_batch2.py::TestBlackboardPatternBatch2::test_specialist_prompt_contains_readable_keys PASSED
```

**Problem:** The test uses `if captured_prompts:` which silently passes if no prompts are captured, potentially hiding bugs.

**Action:** Change to `assert captured_prompts` and verify content includes "requirements".

---

## Issue 7: Unused Variable result_b (test_unified_scope.py:124)

**File:** `tests/unit/test_unified_scope.py`
**Location:** Line 124

**Current state:** Lines exist as documented:
```
124:        result_b = scope_b["recall"]("secret_key")
132:        result_b_fresh = scope_b_fresh["recall"]("secret_key")
133:        assert "secret_value_a" not in result_b_fresh, "Session B should not see A's memory"
```

**Test class:** `TestUnifiedScopeSessionIsolation`
**Test status:** Both tests PASS

```
tests/unit/test_unified_scope.py::TestUnifiedScopeSessionIsolation::test_memory_isolation_between_sessions PASSED
tests/unit/test_unified_scope.py::TestUnifiedScopeSessionIsolation::test_task_isolation_between_sessions PASSED
```

**Problem:** `result_b` is computed but never asserted. Only `result_b_fresh` is verified.

**Action:** Add assertion `assert "secret_value_a" not in result_b` after line 124.

---

## Next Steps

1. Apply fixes in order (Issue 3, 7, 5, 4, 6) as specified in the plan
2. Re-run tests after each fix to verify continued pass status
3. For Issues 4 and 6, may need to adjust assertions if mock responses differ

## Note: Unrelated Test Failures

The `TestE2EConcurrentAgents` tests fail due to SQLite concurrency issues ("database is locked"), not related to the unused lock variable. This is a separate issue from the test quality fixes.
