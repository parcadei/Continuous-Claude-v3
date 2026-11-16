# SQLite WAL Edge Cases

Generated: 2025-12-29

## Executive Summary

This report documents SQLite WAL mode edge cases and concurrency issues based on authoritative documentation. The codebase has partial mitigation for these issues through `busy_timeout` configuration, but several edge cases remain unaddressed, particularly around checkpoint starvation, connection pooling in async contexts, and the interaction between `busy_timeout` and `busy_handler`.

## Research Question

What are the known edge cases and bugs with SQLite WAL mode, busy_timeout, concurrent writes, and connection pooling, and how does our implementation handle them?

---

## Key Findings

### Edge Case 1: WAL Checkpoint Starvation

**Source:** SQLite Documentation - https://www.sqlite.org/wal.html#ckpt

**Description:**
WAL mode defers writing changes to the main database file until a checkpoint occurs. Checkpoints happen automatically when the WAL file reaches 1000 pages (default ~4MB), but they require exclusive access. If readers or writers constantly hold connections, the checkpoint can never complete.

**Conditions:**
- Long-running read transactions prevent checkpointing
- High write frequency without closing connections
- Connection pooling that keeps connections open indefinitely

**Symptoms:**
- WAL file grows unboundedly
- Performance degrades as WAL grows (readers must scan larger WAL)
- Disk space exhaustion

**Our Exposure:**
- `scripts/agentica/memory_service.py`: Uses `async with self._get_conn()` which opens/closes connections per operation - GOOD
- `scripts/agentica/session_tree.py`: Uses `with self._get_conn()` context manager that closes after each operation - GOOD
- `scripts/artifact_index.py`: Opens connection at start, closes at end - MODERATE RISK during bulk indexing
- `scripts/artifact_query.py`: Opens connection, runs queries, closes - GOOD for short queries

**Mitigation Status:** Partially mitigated by connection lifecycle patterns, but no explicit checkpoint management.

---

### Edge Case 2: busy_timeout vs busy_handler Incompatibility

**Source:** SQLite Documentation - https://www.sqlite.org/c3ref/busy_handler.html

**Description:**
`busy_timeout` and `busy_handler` are mutually exclusive. Setting one clears the other. The Python sqlite3 module sets `busy_timeout` via `PRAGMA busy_timeout`, but if any code installs a custom `busy_handler`, the timeout is silently disabled.

**Conditions:**
- Using third-party SQLite extensions that install busy handlers
- Using connection hooks that modify busy behavior
- Mixing different SQLite wrapper libraries

**Symptoms:**
- Timeout stops working
- Operations block indefinitely
- No error or warning is raised

**Our Exposure:**
- `scripts/db_connection.py:54`: Sets `PRAGMA busy_timeout = 5000`
- `scripts/artifact_index.py:46-47`: Also sets `PRAGMA busy_timeout = 5000`
- `scripts/artifact_query.py:260-261, 325-326`: Sets timeout in two places
- `scripts/artifact_mark.py:72-73`: Sets timeout
- No code installs custom busy handlers - SAFE currently

**Mitigation Status:** Not explicitly protected against. If future code adds a busy_handler, it will silently break timeout.

---

### Edge Case 3: SQLITE_BUSY vs SQLITE_LOCKED

**Source:** SQLite Documentation - https://www.sqlite.org/rescode.html#busy

**Description:**
`SQLITE_BUSY` (error code 5) occurs when a connection cannot proceed due to another connection's lock. `SQLITE_LOCKED` (error code 6) occurs due to a conflict within the same connection (e.g., trying to modify a table while iterating over it). `busy_timeout` ONLY handles `SQLITE_BUSY`, not `SQLITE_LOCKED`.

**Conditions:**
- Iterating a cursor while trying to write to the same table
- Using `sqlite3.Row` row factory with certain operations
- Nested transactions within the same connection

**Symptoms:**
- `database table is locked` error despite busy_timeout
- No retry, immediate failure

**Our Exposure:**
- All code uses single-statement patterns - LOW RISK
- `scripts/artifact_index.py`: Bulk insert with iteration - could theoretically hit this
- `scripts/agentica/memory_service.py`: Uses row factory but separate queries - SAFE

**Mitigation Status:** Not explicitly handled. Could add try/except for SQLITE_LOCKED with retry logic.

---

### Edge Case 4: async/await and Thread-Local Storage

**Source:** Python sqlite3 and aiosqlite documentation

**Description:**
SQLite connections are NOT thread-safe. Python's `sqlite3` module uses thread-local storage for connection state. When using `aiosqlite` in async contexts, connections may be accessed from different threads in the thread pool, leading to undefined behavior if not properly isolated.

**Conditions:**
- Using `aiosqlite.connect()` with `check_same_thread=False`
- Sharing connections across asyncio tasks
- Using thread pool executors with SQLite

**Symptoms:**
- `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`
- Corrupted data
- Deadlocks

**Our Exposure:**
- `scripts/agentica/memory_service.py:91-98`: Creates new connection per operation via `_get_conn()` context manager - GOOD
- `scripts/agentica/session_tree.py:109-118`: Same pattern with sync sqlite3 - GOOD
- Both use context managers that open/close connections - SAFE

**Mitigation Status:** Properly handled by creating fresh connections per operation.

---

### Edge Case 5: WAL Mode Persistence Across Connections

**Source:** SQLite Documentation - https://www.sqlite.org/pragma.html#pragma_journal_mode

**Description:**
Once a database is set to WAL mode, it PERSISTS across connections and even across process restarts. Setting `PRAGMA journal_mode = WAL` on an already-WAL database is a no-op but harmless. However, switching FROM WAL to another mode requires exclusive lock and may fail.

**Conditions:**
- First connection sets WAL mode, subsequent connections inherit it
- Attempting to change journal mode while other connections are open

**Symptoms:**
- Unexpected WAL behavior if assuming DELETE mode
- Failure to switch modes

**Our Exposure:**
- `scripts/db_connection.py:57-58`: Sets WAL mode on every connection - harmless, just a no-op
- `scripts/artifact_index.py:48`: Same pattern
- `scripts/agentica/memory_service.py:93`: Same pattern
- `scripts/agentica/session_tree.py:113`: Same pattern

**Mitigation Status:** Not an issue, but redundant PRAGMA calls could be optimized.

---

### Edge Case 6: Connection Leaks in Exception Paths

**Source:** General best practice, Python sqlite3 documentation

**Description:**
If a connection is opened but not properly closed due to an exception, it remains open and holds locks. In WAL mode, this can prevent checkpointing and cause lock contention.

**Conditions:**
- Exceptions thrown after `connect()` but before `close()`
- Missing `try/finally` or context manager patterns
- Daemon processes that crash without cleanup

**Symptoms:**
- `database is locked` errors on subsequent connections
- WAL file not checkpointing
- File descriptors leaking

**Our Exposure:**
- `scripts/db_connection.py`: Returns raw connection, caller must close - MODERATE RISK
- `scripts/artifact_index.py:465`: `conn = init_db(...)`, closes at end but no try/finally - RISK
- `scripts/artifact_query.py:324, 259`: `conn = sqlite3.connect(...)`, closes at end - RISK
- `scripts/artifact_mark.py:71`: Same pattern - RISK
- `scripts/agentica/memory_service.py`: Uses `async with` context manager - GOOD
- `scripts/agentica/session_tree.py`: Uses `with` context manager - GOOD

**Mitigation Status:** Inconsistent. Some files use context managers, others rely on explicit close().

---

### Edge Case 7: FTS5 Rebuild During Concurrent Access

**Source:** SQLite FTS5 Documentation - https://www.sqlite.org/fts5.html

**Description:**
FTS5 `rebuild` and `optimize` commands require exclusive access. Running them while other connections are reading/writing can fail or cause blocking.

**Conditions:**
- Bulk indexing with FTS5 rebuild at the end
- Concurrent read queries during optimization
- Long-running index rebuilds

**Symptoms:**
- SQLITE_BUSY during rebuild
- Blocked readers/writers
- Timeouts if busy_timeout is too short for rebuild duration

**Our Exposure:**
- `scripts/artifact_index.py:479-494`: Runs FTS5 rebuild and optimize at end of bulk indexing
- If a query runs concurrently, it could block or fail

**Mitigation Status:** Not explicitly handled. The 5000ms busy_timeout may be insufficient for large rebuilds.

---

### Edge Case 8: Synchronous Pragma in WAL Mode

**Source:** SQLite Documentation - https://www.sqlite.org/pragma.html#pragma_synchronous

**Description:**
In WAL mode, `PRAGMA synchronous = NORMAL` is recommended instead of `FULL`. However, if power loss occurs between a commit and the next checkpoint, data can be lost. Setting `synchronous = FULL` in WAL mode ensures durability but reduces performance.

**Conditions:**
- Power failure after commit but before checkpoint
- Using default `synchronous = FULL` unnecessarily

**Symptoms:**
- Data loss on power failure (with NORMAL)
- Performance degradation (with FULL)

**Our Exposure:**
- No code sets `synchronous` pragma - uses SQLite default (FULL for safety)
- Not a bug, but could optimize for performance if durability is acceptable

**Mitigation Status:** Using safe defaults. No action needed unless performance is critical.

---

## Codebase Analysis

### Files Reviewed

| File | SQLite Usage Pattern | Risk Level |
|------|---------------------|------------|
| `scripts/db_connection.py` | Factory, returns raw conn | Medium - caller must close |
| `scripts/artifact_index.py` | Bulk insert, FTS5 rebuild | Medium - long-running, no context manager |
| `scripts/artifact_query.py` | Read queries | Low - short operations |
| `scripts/artifact_mark.py` | Single update | Low - short operation |
| `scripts/agentica/memory_service.py` | Async context manager | Low - proper isolation |
| `scripts/agentica/session_tree.py` | Sync context manager | Low - proper isolation |

### Current Mitigations

1. **busy_timeout = 5000ms**: Consistently applied across all connection code
2. **WAL mode**: Enabled everywhere for better concurrency
3. **Context managers**: Used in agentica scripts for connection lifecycle
4. **Per-operation connections**: agentica scripts create fresh connections

### Gaps Identified

1. **No checkpoint management**: Could lead to WAL growth
2. **Inconsistent connection lifecycle**: Some scripts use raw connections without context managers
3. **No SQLITE_LOCKED handling**: Only SQLITE_BUSY is retried
4. **No busy_handler protection**: Future code could silently break timeout
5. **FTS5 rebuild during concurrent access**: No coordination for bulk operations

---

## Sources

1. SQLite WAL Mode Documentation: https://www.sqlite.org/wal.html
2. SQLite busy_handler Reference: https://www.sqlite.org/c3ref/busy_handler.html
3. SQLite Result Codes: https://www.sqlite.org/rescode.html
4. SQLite FTS5 Documentation: https://www.sqlite.org/fts5.html
5. SQLite PRAGMA Reference: https://www.sqlite.org/pragma.html
6. Python sqlite3 Module Documentation: https://docs.python.org/3/library/sqlite3.html
7. aiosqlite Documentation: https://aiosqlite.omnilib.dev/

---

## Recommendations

1. **Add explicit checkpoint control**: Consider `PRAGMA wal_checkpoint(TRUNCATE)` after bulk operations
2. **Standardize connection patterns**: Use context managers everywhere
3. **Add SQLITE_LOCKED retry logic**: For robustness in edge cases
4. **Document busy_handler restriction**: Prevent future code from breaking timeout
5. **Coordinate FTS5 rebuilds**: Add locking or scheduling for maintenance operations

---

## Open Questions

1. Should we use connection pooling for performance, or is per-operation connection acceptable?
2. What is the acceptable WAL file size before we should force checkpoint?
3. Do we need SQLITE_LOCKED handling given our current usage patterns?
4. Should we add explicit `synchronous = NORMAL` for performance in WAL mode?
