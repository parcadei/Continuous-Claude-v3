# Gap Analysis Summary

**Generated:** 2025-12-29
**Analyst:** Gap Analysis Agent (Claude Opus 4.5)
**Sources:** Mutation analysis + Asyncio research + SQLite WAL research + Connection pool research

---

## P0 - Critical Gaps (Production Risk)

These gaps could cause production outages or deadlocks.

### Gap 1: Lock Not Released on Exception/Cancellation

- **Source:**
  - Mutations: `test_pattern_concurrency.py` - "No exception path testing for lock release" (P0)
  - Mutations: `test_span_processor_async_lock.py` - "No test for lock held during exception"
  - Asyncio research: Pattern 5 - "Task Cancellation Without Cleanup"
- **Issue:** If an exception is raised or task is cancelled while holding `asyncio.Lock`, the lock may not be released. This causes deadlock for all subsequent coroutines waiting on that lock.
- **Files affected:**
  - `scripts/agentica/span_processor.py` - `add_summary()`, `get_reference_context()`
  - `scripts/agentica/patterns/circuit_breaker.py` - `_record_failure()`, `_record_success()`
  - `scripts/agentica/patterns/blackboard.py` - `update_item()`, `get_item()`
- **Test needed:**
  - `test_lock_released_on_exception`
  - `test_lock_released_on_task_cancellation`

---

### Gap 2: Mock-Only Integration Tests (No Real Database)

- **Source:**
  - Mutations: All 5 files - "Mock-only tests - no real integration" (P0)
  - SQLite WAL research: Edge Case 4 - "async/await and Thread-Local Storage"
  - Connection pool research: Pattern 3 - "Connection Leak Prevention"
- **Issue:** All concurrency tests use mocked databases. Mocks pass but production could fail due to real locking behavior, thread affinity, and connection lifecycle issues.
- **Files affected:**
  - `tests/unit/test_sqlite_busy_timeout.py` - Verifies string presence, not actual timeout behavior
  - `tests/unit/test_postgres_pool_timeout.py` - All tests mock asyncpg
  - `tests/unit/test_embedding_client_reuse.py` - Mocks httpx.AsyncClient
- **Test needed:**
  - `test_sqlite_concurrent_writes_integration` (real SQLite file, multi-process)
  - `test_postgres_pool_exhaustion_integration` (real PostgreSQL container)
  - `test_embedding_concurrent_requests_integration` (real HTTP server)

---

### Gap 3: Check-Then-Act Race in Lazy Initialization

- **Source:**
  - Asyncio research: Pattern 2 - "Check-Then-Act Race (Lazy Initialization)"
  - Mutations: `test_pattern_concurrency.py` - "Timing-dependent tests"
- **Issue:** Hierarchical pattern's `_ensure_coordinator()` and `_ensure_specialist()` have lazy initialization without locks. Two concurrent calls both see `None`, both spawn agents.
- **Files affected:**
  - `scripts/agentica/patterns/hierarchical.py:204-223` - `_ensure_coordinator()`
  - `scripts/agentica/patterns/hierarchical.py:227-247` - `_ensure_specialist()`
- **Test needed:**
  - `test_ensure_coordinator_concurrent_init`
  - `test_ensure_specialist_concurrent_init`

---

## P1 - High Gaps (Data Risk)

These gaps could cause data corruption or inconsistent state.

### Gap 4: GIL-Masked Races in Blackboard Tests

- **Source:**
  - Mutations: `test_pattern_concurrency.py` - "GIL-masked races" (P1)
  - Asyncio research: Pattern 4 - "Missing asyncio.Lock for Concurrent State Mutations"
- **Issue:** Tests pass in CPython due to GIL atomicity, but would fail in PyPy or if operations become non-atomic. The read-modify-write pattern in increment tests is not thread-safe across async yield points.
- **Files affected:**
  - `scripts/agentica/patterns/blackboard.py` - `update_item()` for increment operations
  - `tests/unit/test_pattern_concurrency.py:255-257` - Tests simple dict writes
- **Test needed:**
  - `test_blackboard_read_modify_write_race`
  - `test_blackboard_increment_with_yield_points`

---

### Gap 5: SQLite busy_timeout Semantic Check (Substring Only)

- **Source:**
  - Mutations: `test_sqlite_busy_timeout.py` - "Substring checks instead of semantic" (P1)
  - SQLite WAL research: Edge Case 2 - "busy_timeout vs busy_handler Incompatibility"
- **Issue:** Tests check for string `"busy_timeout"` in file content. A comment like `# TODO: fix busy_timeout` would pass the test. Also, if code uses `sqlite3.connect(timeout=5)` (wrong parameter), it might pass.
- **Files affected:**
  - `tests/unit/test_sqlite_busy_timeout.py:76` - `assert "busy_timeout" in content`
  - `tests/unit/test_sqlite_busy_timeout.py:94` - `assert "journal_mode" in content and "WAL" in content`
- **Test needed:**
  - `test_busy_timeout_pragma_executed` (verify actual PRAGMA execution, not string presence)
  - `test_busy_timeout_behavior_under_contention`

---

### Gap 6: Lock Scope Not Verified (Premature Release)

- **Source:**
  - Mutations: `test_span_processor_async_lock.py` - "Lock scope not verified" (P1)
  - Mutations: "asyncio.Lock created but not used in critical section" surviving mutation
- **Issue:** Tests verify `isinstance(ctx._lock, asyncio.Lock)` but don't verify the lock is actually held during the critical section. Lock could exist but be released before write completes.
- **Files affected:**
  - `scripts/agentica/span_processor.py` - All locked methods
  - `tests/unit/test_span_processor_async_lock.py:38-45` - Type check only
- **Test needed:**
  - `test_lock_held_for_entire_operation` (instrument lock to verify timing)
  - `test_concurrent_writes_interleaved` (verify data integrity, not just count)

---

### Gap 7: Negative/Zero Value Handling for Timeouts

- **Source:**
  - Mutations: `test_sqlite_busy_timeout.py` - "No test for busy_timeout=0"
  - Mutations: `test_postgres_pool_timeout.py` - "No test for negative timeout values" (P1)
- **Issue:** What happens with `busy_timeout=0` (disables timeout), `busy_timeout=-1` (undefined), `acquire_timeout=-1` (undefined asyncpg behavior)? No tests verify rejection or safe handling.
- **Files affected:**
  - `scripts/agentica/postgres_pool.py:_get_pool_config()` - No validation
  - All SQLite connection code - No validation
- **Test needed:**
  - `test_busy_timeout_zero_rejected_or_handled`
  - `test_acquire_timeout_negative_rejected`
  - `test_pool_size_zero_rejected`

---

### Gap 8: SQLITE_LOCKED Not Handled (Different from SQLITE_BUSY)

- **Source:**
  - SQLite WAL research: Edge Case 3 - "SQLITE_BUSY vs SQLITE_LOCKED"
  - Mutations: "No actual behavioral verification"
- **Issue:** `busy_timeout` only handles `SQLITE_BUSY` (cross-connection), not `SQLITE_LOCKED` (same-connection table lock). Code iterating while modifying would fail immediately.
- **Files affected:**
  - `scripts/artifact_index.py:479-494` - FTS5 rebuild during iteration could hit this
  - All SQLite code lacking `SQLITE_LOCKED` handling
- **Test needed:**
  - `test_sqlite_locked_during_iteration`
  - `test_sqlite_locked_retry_logic`

---

## P2 - Medium Gaps (Edge Cases)

These are edge cases that could cause issues under specific conditions.

### Gap 9: Client Cleanup on Exception Path

- **Source:**
  - Mutations: `test_embedding_client_reuse.py` - "Client cleanup on exception" (P2)
  - Asyncio research: Pattern 5 - "Task Cancellation Without Cleanup"
- **Issue:** If `embed()` raises an exception, is the client still usable? No test verifies the client can be reused after error recovery.
- **Files affected:**
  - `scripts/agentica/embedding_service.py` - `OpenAIEmbeddingProvider`, `VoyageEmbeddingProvider`
- **Test needed:**
  - `test_client_usable_after_exception`
  - `test_concurrent_close_calls`

---

### Gap 10: Task Cancellation During Lock Acquisition

- **Source:**
  - Mutations: `test_pattern_concurrency.py` - "No cancellation tests" (P2)
  - Asyncio research: Pattern 5 - "Task Cancellation Without Cleanup"
- **Issue:** What if a task is cancelled while waiting to acquire a lock? The `asyncio.Lock.acquire()` can be cancelled, but cleanup depends on correct exception handling.
- **Files affected:**
  - All pattern files using `async with self._lock:`
  - `scripts/agentica/span_processor.py`
- **Test needed:**
  - `test_cancel_while_waiting_for_lock`
  - `test_lock_state_after_cancel`

---

### Gap 11: Arbitrary Timeout Values in Tests (Flaky CI)

- **Source:**
  - Mutations: `test_span_processor_async_lock.py` - "Arbitrary timeout values" (P2)
- **Issue:** Test at line 151 uses `timeout=5.0` which is arbitrary. Slow CI could timeout on valid code, fast machines might not expose real deadlocks.
- **Files affected:**
  - `tests/unit/test_span_processor_async_lock.py:151`
  - Various tests with hardcoded timeouts
- **Test needed:**
  - `test_deadlock_detection_with_configurable_timeout`
  - Consider using `pytest-timeout` with CI-appropriate values

---

### Gap 12: WAL Checkpoint Starvation

- **Source:**
  - SQLite WAL research: Edge Case 1 - "WAL Checkpoint Starvation"
  - Mutations: `test_sqlite_busy_timeout.py` - "No test for WAL checkpoint behavior"
- **Issue:** Long-running operations or connection pooling can prevent WAL checkpointing, causing unbounded WAL file growth and performance degradation.
- **Files affected:**
  - `scripts/artifact_index.py` - Bulk indexing keeps connection open
  - Any code that holds connections for extended periods
- **Test needed:**
  - `test_wal_checkpoint_during_bulk_operations`
  - `test_wal_file_size_bounded`

---

### Gap 13: Connection Leak Detection in SQLite

- **Source:**
  - SQLite WAL research: Edge Case 6 - "Connection Leaks in Exception Paths"
  - Mutations: `test_postgres_pool_timeout.py` - "No test for connection leak detection"
- **Issue:** Some SQLite code uses raw connections without context managers. Exception paths could leak connections.
- **Files affected:**
  - `scripts/artifact_index.py:465` - `conn = init_db(...)` without try/finally
  - `scripts/artifact_query.py:324, 259` - Same pattern
  - `scripts/artifact_mark.py:71` - Same pattern
- **Test needed:**
  - `test_connection_closed_on_exception`
  - `test_connection_count_stable_under_errors`

---

### Gap 14: Pool Exhaustion Recovery

- **Source:**
  - Mutations: `test_postgres_pool_timeout.py` - "No pool exhaustion recovery test" (P3)
  - Connection pool research: Pattern 1 - "Pool Exhaustion Under Load"
- **Issue:** After a `TimeoutError` from pool exhaustion, is the pool still usable? No test verifies recovery.
- **Files affected:**
  - `scripts/agentica/postgres_pool.py`
- **Test needed:**
  - `test_pool_usable_after_timeout`
  - `test_pool_connections_released_after_timeout`

---

### Gap 15: FTS5 Rebuild Coordination

- **Source:**
  - SQLite WAL research: Edge Case 7 - "FTS5 Rebuild During Concurrent Access"
- **Issue:** FTS5 rebuild/optimize requires exclusive access. Running during concurrent queries can fail or block. The 5000ms `busy_timeout` may be insufficient for large rebuilds.
- **Files affected:**
  - `scripts/artifact_index.py:479-494` - FTS5 rebuild at end of bulk indexing
- **Test needed:**
  - `test_fts5_rebuild_with_concurrent_queries`
  - `test_busy_timeout_sufficient_for_rebuild`

---

## Test Plan

### Immediate (P0) - Must Fix Before Release

| Test Name | Gap | File to Test | Priority |
|-----------|-----|--------------|----------|
| `test_lock_released_on_exception` | Gap 1 | `span_processor.py`, `circuit_breaker.py` | P0 |
| `test_lock_released_on_task_cancellation` | Gap 1 | `span_processor.py`, `patterns/*.py` | P0 |
| `test_sqlite_concurrent_writes_integration` | Gap 2 | `memory_service.py`, `session_tree.py` | P0 |
| `test_postgres_pool_exhaustion_integration` | Gap 2 | `postgres_pool.py` | P0 |
| `test_ensure_coordinator_concurrent_init` | Gap 3 | `hierarchical.py` | P0 |
| `test_ensure_specialist_concurrent_init` | Gap 3 | `hierarchical.py` | P0 |

### Short-term (P1) - Next Sprint

| Test Name | Gap | File to Test | Priority |
|-----------|-----|--------------|----------|
| `test_blackboard_read_modify_write_race` | Gap 4 | `blackboard.py` | P1 |
| `test_busy_timeout_pragma_executed` | Gap 5 | All SQLite code | P1 |
| `test_lock_held_for_entire_operation` | Gap 6 | `span_processor.py` | P1 |
| `test_acquire_timeout_negative_rejected` | Gap 7 | `postgres_pool.py` | P1 |
| `test_busy_timeout_zero_rejected_or_handled` | Gap 7 | SQLite code | P1 |
| `test_sqlite_locked_during_iteration` | Gap 8 | `artifact_index.py` | P1 |

### Medium-term (P2) - Backlog

| Test Name | Gap | File to Test | Priority |
|-----------|-----|--------------|----------|
| `test_client_usable_after_exception` | Gap 9 | `embedding_service.py` | P2 |
| `test_cancel_while_waiting_for_lock` | Gap 10 | All pattern files | P2 |
| `test_deadlock_detection_configurable_timeout` | Gap 11 | Test infrastructure | P2 |
| `test_wal_checkpoint_during_bulk_operations` | Gap 12 | `artifact_index.py` | P2 |
| `test_connection_closed_on_exception` | Gap 13 | SQLite scripts | P2 |
| `test_pool_usable_after_timeout` | Gap 14 | `postgres_pool.py` | P2 |
| `test_fts5_rebuild_with_concurrent_queries` | Gap 15 | `artifact_index.py` | P2 |

---

## Cross-Reference Matrix

| Gap | Mutation Source | Research Source | Implementation File | Test File |
|-----|----------------|-----------------|---------------------|-----------|
| Gap 1 | pattern_concurrency P0 | asyncio Pattern 5 | span_processor.py | test_span_processor_async_lock.py |
| Gap 2 | All files P0 | sqlite Edge 4, pool Pattern 3 | All | All concurrency tests |
| Gap 3 | pattern_concurrency timing | asyncio Pattern 2 | hierarchical.py | (missing) |
| Gap 4 | pattern_concurrency GIL | asyncio Pattern 4 | blackboard.py | test_pattern_concurrency.py |
| Gap 5 | sqlite_busy_timeout P1 | sqlite Edge 2 | db_connection.py | test_sqlite_busy_timeout.py |
| Gap 6 | span_processor P1 | asyncio Pattern 1 | span_processor.py | test_span_processor_async_lock.py |
| Gap 7 | postgres_pool P1, sqlite | - | postgres_pool.py | test_postgres_pool_timeout.py |
| Gap 8 | - | sqlite Edge 3 | artifact_index.py | (missing) |
| Gap 9 | embedding_client P2 | asyncio Pattern 5 | embedding_service.py | test_embedding_client_reuse.py |
| Gap 10 | pattern_concurrency P2 | asyncio Pattern 5 | patterns/*.py | (missing) |
| Gap 11 | span_processor P2 | - | tests | test_span_processor_async_lock.py |
| Gap 12 | sqlite_busy_timeout WAL | sqlite Edge 1 | artifact_index.py | (missing) |
| Gap 13 | - | sqlite Edge 6 | artifact scripts | (missing) |
| Gap 14 | postgres_pool P3 | pool Pattern 1 | postgres_pool.py | test_postgres_pool_timeout.py |
| Gap 15 | - | sqlite Edge 7 | artifact_index.py | (missing) |

---

## Summary Statistics

| Priority | Count | Production Risk |
|----------|-------|-----------------|
| P0 | 3 gaps | Could cause production outage or deadlock |
| P1 | 5 gaps | Could cause data corruption or inconsistent state |
| P2 | 7 gaps | Edge cases that could cause issues under specific conditions |

**Total gaps identified:** 15

**Gaps with no existing tests:** 6 (Gaps 3, 8, 10, 12, 13, 15)

**Gaps with weak existing tests:** 9 (Gaps 1, 2, 4, 5, 6, 7, 9, 11, 14)
