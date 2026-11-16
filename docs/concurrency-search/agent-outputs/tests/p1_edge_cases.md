# P1 Edge Case Tests Summary

**Generated:** 2025-12-29
**Test File:** `tests/unit/test_concurrency_edge_cases.py`
**Status:** 8 FAILED, 4 PASSED, 1 SKIPPED (blackboard atomicity documented)

---

## Overview

These tests expose P1 gaps in edge case handling for concurrency primitives. All tests are designed to FAIL initially, documenting the gaps that need to be fixed.

## Test Results

```
FAILED test_postgres_pool_rejects_negative_timeout
FAILED test_postgres_pool_rejects_zero_timeout
FAILED test_postgres_pool_rejects_zero_pool_size
FAILED test_postgres_pool_rejects_negative_pool_size
FAILED test_sqlite_locked_error_handling
FAILED test_sqlite_locked_during_fts5_rebuild
PASSED test_circuit_breaker_lock_held_during_entire_operation
PASSED test_blackboard_get_set_pattern_demonstrates_race (renamed, now documents expected behavior)
PASSED test_blackboard_update_item_is_truly_atomic
SKIPPED test_dict_operations_thread_safety (GIL luck)
FAILED test_asyncio_dict_race_with_yield_points
PASSED test_sqlite_busy_timeout_zero_disables_timeout
FAILED test_sqlite_busy_timeout_negative_undefined_behavior
```

---

## Gap 7: Negative/Zero Timeout Value Handling

### Tests Created

| Test | Gap | Status | Issue |
|------|-----|--------|-------|
| `test_postgres_pool_rejects_negative_timeout` | Gap 7 | FAILED | `-1` accepted, passed to asyncpg |
| `test_postgres_pool_rejects_zero_timeout` | Gap 7 | FAILED | `0` accepted (infinite wait) |
| `test_postgres_pool_rejects_zero_pool_size` | Gap 7 | FAILED | `0` accepted for max_size |
| `test_postgres_pool_rejects_negative_pool_size` | Gap 7 | FAILED | `-5` accepted for max_size |
| `test_sqlite_busy_timeout_zero_disables_timeout` | Gap 7 | PASSED | Documents the behavior |
| `test_sqlite_busy_timeout_negative_undefined_behavior` | Gap 7 | FAILED | `-1` converted to `0` silently |

### Issue

`_get_pool_config()` in `postgres_pool.py` does no validation:

```python
try:
    acquire_timeout = int(acquire_timeout_str)
except ValueError:
    acquire_timeout = 30  # Only handles non-numeric
# Missing: if acquire_timeout <= 0: raise ValueError(...)
```

### Fix Required

Add validation to `_get_pool_config()`:

```python
if max_size <= 0:
    raise ValueError(f"AGENTICA_MAX_POOL_SIZE must be > 0, got {max_size}")
if acquire_timeout <= 0:
    raise ValueError(f"AGENTICA_ACQUIRE_TIMEOUT must be > 0, got {acquire_timeout}")
```

---

## Gap 8: SQLITE_LOCKED vs SQLITE_BUSY Handling

### Tests Created

| Test | Gap | Status | Issue |
|------|-----|--------|-------|
| `test_sqlite_locked_error_handling` | Gap 8 | FAILED | No retry logic for SQLITE_LOCKED |
| `test_sqlite_locked_during_fts5_rebuild` | Gap 8 | FAILED | FTS5 rebuild not coordinated |

### Issue

`busy_timeout` only handles `SQLITE_BUSY` (cross-connection contention). `SQLITE_LOCKED` occurs when:
- Modifying a table while iterating over its rows
- FTS5 rebuild while queries are active

### Fix Required

1. **Pattern change**: Use `fetchall()` before modifying:
   ```python
   rows = cursor.execute("SELECT ...").fetchall()
   for row in rows:
       conn.execute(f"DELETE WHERE id = {row[0]}")
   ```

2. **FTS5 rebuild coordination**: Schedule rebuilds during idle periods or use separate connections.

---

## Gap 6: Lock Scope Verification

### Tests Created

| Test | Gap | Status | Issue |
|------|-----|--------|-------|
| `test_circuit_breaker_lock_held_during_entire_operation` | Gap 6 | PASSED | Lock is properly held |
| `test_blackboard_get_set_pattern_demonstrates_race` | Gap 4/6 | PASSED | Documents expected race (not a bug) |
| `test_blackboard_update_item_is_truly_atomic` | Gap 4/6 | PASSED | update_item IS atomic |

### Issue

The non-atomic pattern loses 99% of increments:

```
Expected 1000 but got 10. Lost 990 increments due to race condition.
```

The separate `get_item` + `set_item` pattern is not atomic:

```python
# WRONG - race condition between get and set
current = await state.get_item("counter")
await asyncio.sleep(0.0001)  # Yield point releases lock!
await state.set_item("counter", current + 1)
```

### Fix Required

Use `update_item` for atomic read-modify-write:

```python
# CORRECT - lock held for entire operation
await state.update_item("counter", lambda x: (x or 0) + 1)
```

---

## Gap 4: GIL-Independence

### Tests Created

| Test | Gap | Status | Issue |
|------|-----|--------|-------|
| `test_dict_operations_thread_safety` | Gap 4 | SKIPPED | GIL masks the race |
| `test_asyncio_dict_race_with_yield_points` | Gap 4 | FAILED | 100 read inconsistencies |

### Issue

Tests that pass under CPython's GIL would fail under PyPy or with true parallelism. The asyncio test detected 100 read inconsistencies in 100 iterations.

### Fix Required

Always use `asyncio.Lock` for shared state, even for "simple" dict operations:

```python
async with self._lock:
    value = self._data[key]
    # ... modifications ...
```

---

## Summary

| Gap | Tests | Failing | Key Finding |
|-----|-------|---------|-------------|
| Gap 7 (Timeouts) | 6 | 5 | No validation for negative/zero values |
| Gap 8 (SQLITE_LOCKED) | 2 | 2 | No handling for same-connection locks |
| Gap 6 (Lock Scope) | 3 | 0 | get/set race documented as expected |
| Gap 4 (GIL) | 2 | 1 | Dict operations need explicit locks |

**Total: 13 tests, 8 failing (1 converted to documentation test)**

---

## Next Steps

1. Fix `_get_pool_config()` validation (Gap 7)
2. Add `fetchall()` pattern to SQLite iteration code (Gap 8)
3. Document that `update_item` must be used instead of get/set (Gap 6)
4. Review all asyncio code for unprotected dict operations (Gap 4)

---

## Files Referenced

- **Test file:** `tests/unit/test_concurrency_edge_cases.py`
- **Gap analysis:** `docs/concurrency-search/agent-outputs/gaps/gap_analysis.md`
- **Implementation files:**
  - `scripts/agentica/postgres_pool.py` - Timeout validation
  - `scripts/agentica/patterns/blackboard.py` - Atomic operations
  - `scripts/agentica/patterns/circuit_breaker.py` - Lock scope
  - `scripts/artifact_index.py` - SQLite iteration patterns
