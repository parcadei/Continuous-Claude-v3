# SQLite busy_timeout Tests

## Test File

`tests/unit/test_sqlite_busy_timeout.py`

## Issue Reference

**STARVATION_FINDINGS.md Finding 3**: SQLite Database Lock Without Busy Timeout

- **Risk Level**: HIGH
- **Pattern**: Direct SQLite connections do not set `PRAGMA busy_timeout`, causing indefinite blocks when multiple writers contend.

## Test Summary

| Status | Count |
|--------|-------|
| FAILED | 10    |
| PASSED | 4     |
| SKIPPED | 1    |

## Test Details

### TestBusyTimeoutConfiguration (3 tests - ALL FAILING)

| Test Name | What It Verifies | Current Status |
|-----------|------------------|----------------|
| `test_db_utils_sets_busy_timeout` | db-utils.ts embedded Python must set `PRAGMA busy_timeout` | FAILED |
| `test_db_utils_enables_wal_mode` | db-utils.ts embedded Python must enable WAL mode | FAILED |
| `test_busy_timeout_value_is_reasonable` | busy_timeout value is between 1000-10000ms | FAILED |

### TestWALModeConfiguration (5 tests - ALL FAILING)

| Test Name | What It Verifies | Current Status |
|-----------|------------------|----------------|
| `test_artifact_index_enables_wal_mode` | artifact_index.py must enable WAL mode | FAILED |
| `test_artifact_index_sets_busy_timeout` | artifact_index.py must set busy_timeout | FAILED |
| `test_artifact_query_sets_busy_timeout` | artifact_query.py must set busy_timeout | FAILED |
| `test_artifact_mark_sets_busy_timeout` | artifact_mark.py must set busy_timeout | FAILED |
| `test_braintrust_analyze_sets_busy_timeout` | braintrust_analyze.py must set busy_timeout | FAILED |

### TestConcurrentWriteTimeout (2 tests - PASSING)

| Test Name | What It Verifies | Current Status |
|-----------|------------------|----------------|
| `test_concurrent_writes_timeout_without_busy_timeout` | Demonstrates blocking behavior without busy_timeout | PASSED |
| `test_concurrent_writes_succeed_with_proper_timeout` | Shows concurrent writes succeed with busy_timeout | PASSED |

### TestHookPythonScriptsTimeout (2 tests - ALL FAILING)

| Test Name | What It Verifies | Current Status |
|-----------|------------------|----------------|
| `test_all_python_scripts_have_busy_timeout` | All embedded Python in hooks/*.js sets busy_timeout | FAILED |
| `test_db_utils_js_sets_busy_timeout` | shared/db-utils.js embedded Python sets busy_timeout | FAILED |

### TestConnectionFactoryPattern (1 test - SKIPPED)

| Test Name | What It Verifies | Current Status |
|-----------|------------------|----------------|
| `test_connection_factory_exists` | Suggests centralized connection factory pattern | SKIPPED |

### TestTimeoutErrorHandling (2 tests - PASSING)

| Test Name | What It Verifies | Current Status |
|-----------|------------------|----------------|
| `test_timeout_raises_operational_error` | busy_timeout expiry raises OperationalError | PASSED |
| `test_retry_logic_after_timeout` | Retry logic works after timeout | PASSED |

## Current Failure Output

```
FAILED tests/unit/test_sqlite_busy_timeout.py::TestBusyTimeoutConfiguration::test_db_utils_sets_busy_timeout
  - db-utils.ts must set PRAGMA busy_timeout in Python scripts.
    Expected: conn.execute('PRAGMA busy_timeout = 5000')
    This prevents indefinite blocking when multiple writers contend.

FAILED tests/unit/test_sqlite_busy_timeout.py::TestBusyTimeoutConfiguration::test_db_utils_enables_wal_mode
  - db-utils.ts must enable WAL mode in Python scripts.
    Expected: conn.execute('PRAGMA journal_mode = WAL')

FAILED tests/unit/test_sqlite_busy_timeout.py::TestWALModeConfiguration::test_artifact_index_sets_busy_timeout
  - artifact_index.py must set PRAGMA busy_timeout.
    Expected: conn.execute('PRAGMA busy_timeout = 5000')
    Location: init_db() function after sqlite3.connect()

FAILED tests/unit/test_sqlite_busy_timeout.py::TestHookPythonScriptsTimeout::test_all_python_scripts_have_busy_timeout
  - The following hook files contain sqlite3.connect() without busy_timeout:
    - pre-tool-use-broadcast.js
    - pre-tool-use.js
    - session-start-continuity.js
    - stop-coordinator.js
    - (and others)
```

## Implementation Required

To make these tests pass, the following changes are needed:

### 1. Update `.claude/hooks/src/shared/db-utils.ts`

In the embedded Python script within `getActiveAgentCount()`:

```python
# After: conn = sqlite3.connect(db_path)
# Add:
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")
```

### 2. Update `scripts/artifact_index.py`

In the `init_db()` function:

```python
def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize database with schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout = 5000")  # Add this
    conn.execute("PRAGMA journal_mode = WAL")   # Add this
    # ... rest of function
```

### 3. Update `scripts/artifact_query.py`

After each `sqlite3.connect()` call (lines 259, 322):

```python
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA busy_timeout = 5000")
```

### 4. Update `scripts/artifact_mark.py`

After the `sqlite3.connect()` call (line 71):

```python
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA busy_timeout = 5000")
```

### 5. Update `scripts/braintrust_analyze.py`

After the `sqlite3.connect()` call (line 904):

```python
conn = sqlite3.connect(db)
conn.execute("PRAGMA busy_timeout = 5000")
```

### 6. Update all hook TypeScript files with embedded Python

Files in `.claude/hooks/src/` that contain embedded Python with `sqlite3.connect()`:

- `pre-tool-use-broadcast.ts`
- `pre-tool-use.ts`
- `session-start-continuity.ts`
- `stop-coordinator.ts`
- (others as identified by the test)

After adding the changes, rebuild hooks:
```bash
cd .claude/hooks && npm run build
```

## Recommended Pattern: Connection Factory

Consider creating a shared connection factory to enforce consistent configuration:

```python
# scripts/db_connection.py
import sqlite3

def get_connection(db_path: str, timeout_ms: int = 5000) -> sqlite3.Connection:
    """Get SQLite connection with proper concurrency configuration."""
    conn = sqlite3.connect(db_path)
    conn.execute(f"PRAGMA busy_timeout = {timeout_ms}")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
```

Then use it everywhere instead of direct `sqlite3.connect()` calls.

## Run Tests

```bash
uv run pytest tests/unit/test_sqlite_busy_timeout.py -v
```
