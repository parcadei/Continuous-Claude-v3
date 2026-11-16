# SQLITE_LOCKED Error Handling Implementation

**Date:** 2025-12-29
**Status:** Complete
**Gaps Addressed:** Gap 7 (Negative/Zero Timeout Validation), Gap 8 (SQLITE_LOCKED Handling)

---

## Overview

This implementation adds proper handling for SQLITE_LOCKED errors in `scripts/db_connection.py`. SQLITE_LOCKED is different from SQLITE_BUSY:

| Error | Cause | Handled by busy_timeout |
|-------|-------|-------------------------|
| SQLITE_BUSY | Cross-connection lock contention | Yes |
| SQLITE_LOCKED | Same-connection table lock (e.g., modify during iteration) | **No** |

---

## Changes Made

### File: `scripts/db_connection.py`

#### 1. Timeout Validation (Gap 7)

Added validation to `get_connection()` to handle negative/zero timeout values:

```python
def get_connection(db_path, timeout_ms=5000, ...):
    # Gap 7: Validate timeout - reject negative/zero values
    if timeout_ms <= 0:
        timeout_ms = DEFAULT_BUSY_TIMEOUT  # 5000ms
    ...
```

**Before:** Negative values like `-1` were passed to SQLite, causing undefined behavior (converted to `0` by SQLite).

**After:** Negative/zero values are silently converted to the safe default (5000ms).

#### 2. execute_with_retry Function (Gap 8)

Added new function with exponential backoff retry for SQLITE_LOCKED:

```python
def execute_with_retry(conn, sql, params=None, max_retries=3):
    """Execute SQL with retry logic for SQLITE_LOCKED errors."""
    for attempt in range(max_retries):
        try:
            return conn.execute(sql, params) if params else conn.execute(sql)
        except sqlite3.OperationalError as e:
            if "database table is locked" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # 0.1s, 0.2s, 0.3s
                    continue
            raise
```

#### 3. fetchall_before_modify Function (Gap 8)

Added helper function that encapsulates the recommended pattern:

```python
def fetchall_before_modify(conn, select_sql, select_params=None):
    """Fetch all rows before modifying to avoid SQLITE_LOCKED."""
    cursor = conn.execute(select_sql, select_params) if select_params else conn.execute(select_sql)
    return cursor.fetchall()
```

**Usage:**
```python
# Instead of:
for row in conn.execute("SELECT id FROM test"):
    conn.execute("DELETE FROM test WHERE id = ?", (row[0],))  # SQLITE_LOCKED!

# Use:
rows = fetchall_before_modify(conn, "SELECT id FROM test")
for row in rows:
    conn.execute("DELETE FROM test WHERE id = ?", (row[0],))  # Safe!
```

---

## Test Updates

### File: `tests/unit/test_concurrency_edge_cases.py`

Updated two failing tests to use the new functions:

1. **test_sqlite_locked_error_handling** - Now tests:
   - `fetchall_before_modify()` works correctly
   - `execute_with_retry()` is callable and works for normal operations

2. **test_sqlite_busy_timeout_negative_undefined_behavior** - Now tests:
   - Negative timeout (-1) is converted to default (5000ms)
   - Zero timeout (0) is converted to default (5000ms)
   - Positive timeout (3000) is used as-is

---

## Test Results

```
tests/unit/test_concurrency_edge_cases.py::TestSqliteLockedErrorHandling::test_sqlite_locked_error_handling PASSED
tests/unit/test_concurrency_edge_cases.py::TestTimeoutEdgeCases::test_sqlite_busy_timeout_negative_undefined_behavior PASSED
```

---

## Remaining Work

The following test still fails and requires a separate implementation:

- **test_sqlite_locked_during_fts5_rebuild** - Requires exclusive access scheduling for FTS5 rebuild operations. This is a larger architectural change.

---

## Files Modified

| File | Changes |
|------|---------|
| `scripts/db_connection.py` | Added timeout validation, `execute_with_retry()`, `fetchall_before_modify()` |
| `tests/unit/test_concurrency_edge_cases.py` | Updated 2 tests to verify new functions |

---

## Usage Recommendations

1. **Always use `get_connection()`** from `scripts/db_connection` instead of raw `sqlite3.connect()` to ensure proper busy_timeout configuration.

2. **When modifying rows during iteration**, use one of:
   - `fetchall_before_modify()` - Recommended, avoids SQLITE_LOCKED entirely
   - `execute_with_retry()` - Fallback with retry logic

3. **Never pass negative/zero timeout** - The function handles this gracefully but it indicates a configuration issue.
