# Mutation Analysis

Analysis of concurrency test files to identify weak assertions, surviving mutations, and missing edge cases.

**Analyzed Files:**
- tests/unit/test_sqlite_busy_timeout.py
- tests/unit/test_embedding_client_reuse.py
- tests/unit/test_pattern_concurrency.py
- tests/unit/test_postgres_pool_timeout.py
- tests/unit/test_span_processor_async_lock.py

---

## test_sqlite_busy_timeout.py

### Surviving Mutations (would NOT be caught)

1. **Mutation: Set busy_timeout=0 instead of 5000**
   - Test `test_busy_timeout_value_is_reasonable` only checks range `1000 <= timeout <= 10000`
   - A value of 0 would pass validation (regex captures it) but the assertion `1000 <= 0` would fail
   - However, if code had `busy_timeout = 1000` (minimum), tests pass but this might be too aggressive
   - **Status**: Would be caught, but minimum 1000ms may be too short for production loads

2. **Mutation: Remove WAL mode entirely from implementation**
   - Test `test_db_utils_enables_wal_mode` checks for presence of both `"journal_mode"` AND `"WAL"` in content
   - If implementation uses `PRAGMA journal_mode = DELETE` instead, test would fail
   - **Status**: Properly caught

3. **Mutation: Set busy_timeout via connection parameter instead of PRAGMA**
   - Tests check for string `"busy_timeout"` in file content, not execution behavior
   - If someone writes `conn = sqlite3.connect(db_path, timeout=5)` (wrong approach - this is lock timeout, not busy timeout), tests might pass due to false substring match
   - **Status**: WEAK - tests check string presence, not semantic correctness

### Weak Assertions

- **Line 76**: `assert "busy_timeout" in content` - Only checks substring presence
  - Doesn't verify correct PRAGMA syntax
  - Doesn't verify timeout is actually set after connect()
  - Doesn't verify timeout applies to the right connection

- **Line 94**: `assert "journal_mode" in content and "WAL" in content`
  - Doesn't verify WAL is actually enabled (could be in a comment)
  - Doesn't verify correct PRAGMA syntax

- **Line 120**: `assert 1000 <= timeout_ms <= 10000`
  - Arbitrary bounds - no justification for why 10000ms max
  - Doesn't consider connection vs statement timeouts

### Missing Edge Cases

1. **No test for busy_timeout=0 behavior**
   - What happens if someone explicitly sets `busy_timeout = 0`?
   - This disables the timeout entirely (immediate failure on lock)

2. **No test for negative timeout values**
   - What if `busy_timeout = -1` is set?
   - SQLite behavior is undefined/implementation-specific

3. **No test for WAL mode persistence**
   - WAL mode persists across connections, but tests don't verify this

4. **No test for WAL checkpoint behavior**
   - Long-running connections without checkpoints can cause WAL file growth

5. **No test for read-only connections**
   - Different timeout behavior may apply to read-only opens

6. **No integration test for actual concurrent write behavior**
   - Tests mock or simulate, but don't test with real multi-process contention

### HIGH Risk Gaps

- **Substring-only checks**: Tests verify string presence but not semantic correctness. A developer could add `# TODO: busy_timeout` and tests would pass.
- **No actual behavioral verification**: Tests don't verify that the timeout actually works at runtime.

---

## test_embedding_client_reuse.py

### Surviving Mutations (would NOT be caught)

1. **Mutation: Client reused but not closed on exception**
   - Tests verify `client_init_count == 1` but don't verify client is closed on provider cleanup
   - `test_openai_provider_has_close_method` only checks method existence, not that it actually closes the client
   - **Status**: WEAK - existence check, not behavior check

2. **Mutation: Client reused but timeout set to 0**
   - No test verifies actual timeout value on the persistent client
   - `test_client_has_reasonable_timeout` checks for `_client` attribute but uses `pytest.fail` if missing, not actual timeout verification
   - **Status**: WEAK - test fails if `_client` missing but doesn't verify timeout

3. **Mutation: Client created per-thread instead of truly shared**
   - Tests use `asyncio.gather` which runs in single thread
   - If implementation uses `threading.local()` storage, tests would pass but multi-threaded scenarios would leak
   - **Status**: WEAK - no multi-thread test

### Weak Assertions

- **Line 63**: `assert client_init_count == 1`
  - Tests mock, not real httpx.AsyncClient
  - Doesn't verify same instance ID is reused (could be 1 new instance each time if GC happens)

- **Line 163-167**: `has_close = hasattr(provider, "close") or hasattr(provider, "aclose")`
  - Only checks method exists, not that it actually closes the client
  - Doesn't verify cleanup happens on exception paths

- **Line 336-342**: Timeout test
  - Falls back to `pytest.fail` if `_client` doesn't exist
  - If `_client` exists but has wrong timeout, no assertion verifies correct value

### Missing Edge Cases

1. **No test for client closed then embed() called**
   - What happens if `close()` is called then `embed()` is called?
   - Should raise error or reinitialize client?

2. **No test for client reuse across process boundary**
   - httpx.AsyncClient is not pickle-able
   - Multiprocessing scenarios would fail

3. **No test for SSL/TLS certificate validation**
   - Persistent client should have proper cert validation
   - Mutation could disable verification

4. **No test for connection pool exhaustion recovery**
   - What happens when httpx's internal pool is exhausted?
   - Does client recover or need recreation?

5. **No test for async context manager usage pattern**
   - `test_provider_supports_async_context_manager` checks protocol existence
   - No test that `__aexit__` actually closes the client

6. **No test for concurrent close() calls**
   - What if two tasks call `close()` simultaneously?
   - Double-close could raise or corrupt state

### HIGH Risk Gaps

- **Mock-only testing**: All tests use mocked AsyncClient. No real HTTP calls verified.
- **Cleanup on exception not tested**: If `embed()` raises, is client still usable?
- **No rate limiting / backoff verification**: Persistent client should have retry config.

---

## test_pattern_concurrency.py

### Surviving Mutations (would NOT be caught)

1. **Mutation: Lock acquired but never released on exception**
   - Tests verify operation succeeds but don't verify lock is released on failure path
   - If `_record_failure()` acquires lock and throws, tests would pass but lock would be held
   - **Status**: WEAK - no exception path testing

2. **Mutation: Lock released before operation complete**
   - Premature release would cause race but tests might pass due to timing
   - Tests rely on `asyncio.sleep()` for interleaving which is non-deterministic
   - **Status**: WEAK - timing-dependent tests

3. **Mutation: asyncio.Lock replaced with threading.Lock**
   - Tests don't verify lock type, only behavior
   - threading.Lock in async code would cause deadlocks but tests might pass due to short duration
   - **Status**: WEAK - behavior tests, not type verification

4. **Mutation: Blackboard update_item() doesn't use lock**
   - Test at line 298 verifies final value equals num_increments
   - In CPython, simple dict ops might be atomic due to GIL, causing test to pass
   - **Status**: WEAK - GIL masks race condition

### Weak Assertions

- **Line 104-105**: `assert 0 <= circuit_breaker.failure_count <= circuit_breaker.max_failures`
  - Allows failure_count to be 0 after concurrent failures
  - Should verify failure_count > 0 after failures

- **Line 162**: `assert circuit_breaker.failure_count > 0, "No failures were recorded"`
  - Only checks > 0, not that all failures were recorded
  - With 10 concurrent failures, should have failure_count >= something (depends on max_failures)

- **Line 213**: `assert true_count > 0, "At least one call should try primary"`
  - Doesn't verify EXACTLY one transitions to HALF_OPEN
  - Multiple transitions would indicate race condition

- **Line 255-257**: Blackboard key count
  - Tests simple dict writes which are GIL-atomic in CPython
  - Doesn't test read-modify-write which is the actual race

### Missing Edge Cases

1. **No test for lock timeout scenarios**
   - What if asyncio.Lock.acquire() times out?
   - No test for lock contention at scale

2. **No test for deadlock detection**
   - Multiple locks acquired in different orders could deadlock
   - No test verifies lock ordering

3. **No test for reentrant lock attempts**
   - asyncio.Lock is not reentrant
   - Recursive call paths could deadlock

4. **No test for cancelled tasks with held locks**
   - If task is cancelled while holding lock, is it released?

5. **No test for mixed sync/async access**
   - What if sync code tries to access locked state?

6. **No test for state corruption on partial failure**
   - If failure_count increments but state transition fails, state is inconsistent

### HIGH Risk Gaps

- **GIL-masked races**: Tests pass in CPython but would fail in PyPy or other implementations.
- **Timing-dependent**: Tests use `asyncio.sleep()` for interleaving which is non-deterministic.
- **No cancellation tests**: Asyncio cancellation is common and lock release must be verified.

---

## test_postgres_pool_timeout.py

### Surviving Mutations (would NOT be caught)

1. **Mutation: acquire_timeout set to 0**
   - Test at line 54 checks `call_kwargs["acquire_timeout"] == 30`
   - Value 0 would fail this test
   - **Status**: Properly caught

2. **Mutation: acquire_timeout set to negative value**
   - No test for negative timeout handling
   - asyncpg behavior with negative timeout is undefined
   - **Status**: NOT caught - no negative value test

3. **Mutation: Pool created without min_size**
   - Tests verify max_size but `min_size` assertion at line 256 has weak condition `>= 2`
   - If min_size removed entirely, test uses default of 2 which passes
   - **Status**: WEAK - assertion uses default fallback

4. **Mutation: Different acquire_timeout per code path**
   - Tests verify get_pool and get_pool_with_retry separately
   - If one path missed timeout, respective test would catch it
   - **Status**: Properly caught

### Weak Assertions

- **Line 50-51**: `assert "acquire_timeout" in call_kwargs`
  - Verifies presence but doesn't verify correct handling of the timeout
  - Doesn't verify TimeoutError is properly raised and handled

- **Line 102-105**:
  ```python
  with pytest.raises(TimeoutError):
      async with get_connection():
          ...
  ```
  - Tests that mock raises TimeoutError, not that real pool does
  - No test for actual pool exhaustion behavior

- **Line 133**: `assert call_kwargs.get("max_size") == 10`
  - Uses `.get()` with implicit None default
  - If max_size key missing, assertion fails with `None == 10`
  - **Status**: OK but error message would be confusing

- **Line 256-262**: min_size scaling
  - `assert call_kwargs.get("min_size", 2) >= 2`
  - Uses default of 2 in assertion, masking missing min_size
  - Inner assertion only runs if max_size >= 50

### Missing Edge Cases

1. **No test for negative pool sizes**
   - What if AGENTICA_MAX_POOL_SIZE="-5"?

2. **No test for pool size = 0**
   - What if AGENTICA_MAX_POOL_SIZE="0"?

3. **No test for pool exhaustion recovery**
   - After TimeoutError, is pool still usable?

4. **No test for connection leak detection**
   - If connection not returned to pool, does timeout eventually fire?

5. **No test for pool closure behavior**
   - What happens to pending acquires when pool.close() is called?

6. **No test for statement_timeout vs acquire_timeout**
   - These are different timeouts with different purposes

7. **No integration test with real PostgreSQL**
   - All tests mock asyncpg

### HIGH Risk Gaps

- **Mock-only**: No real asyncpg/PostgreSQL integration tests.
- **No negative value handling**: Negative timeouts could cause undefined behavior.
- **Connection leak not tested**: Pool exhaustion test simulates but doesn't verify actual leak detection.

---

## test_span_processor_async_lock.py

### Surviving Mutations (would NOT be caught)

1. **Mutation: asyncio.Lock created but not used in critical section**
   - Tests verify `isinstance(ctx._lock, asyncio.Lock)` at line 44
   - If lock exists but `add_summary` doesn't acquire it, test passes
   - **Status**: WEAK - type check but no usage verification

2. **Mutation: Lock acquired but released too early**
   - Tests verify method is async (line 58) but don't verify lock held for duration
   - Releasing lock before write completes would pass these tests
   - **Status**: NOT caught - no lock scope verification

3. **Mutation: asyncio.Lock replaced with asyncio.RLock**
   - `isinstance(ctx._lock, asyncio.Lock)` would fail for RLock
   - But RLock might be valid choice for reentrant patterns
   - **Status**: Would fail even if valid design choice

4. **Mutation: Timeout of 5s is too short / too long**
   - Line 151: `timeout=5.0` is arbitrary
   - Slow CI could timeout, fast machine might not expose real deadlock
   - **Status**: WEAK - arbitrary timeout value

### Weak Assertions

- **Line 38-45**: Lock type check
  ```python
  assert not isinstance(ctx._lock, (threading.Lock, type(threading.Lock())))
  assert isinstance(ctx._lock, asyncio.Lock)
  ```
  - Checks type but not usage
  - Lock could exist but never be acquired

- **Line 58-60**: Method signature check
  ```python
  assert inspect.iscoroutinefunction(SpanProcessingContext.add_summary)
  ```
  - Checks method is async but not that it awaits the lock

- **Line 116**: `assert asyncio.iscoroutine(result)`
  - Verifies return type but not behavior

- **Line 158**: `assert len(ctx.span_summaries) == 10`
  - Only verifies count, not data integrity
  - Concurrent writes could corrupt individual entries

### Missing Edge Cases

1. **No test for lock held during exception**
   - If add_summary raises after acquiring lock, is it released?

2. **No test for concurrent read/write**
   - Tests have concurrent writes (add_summary) and concurrent reads (get_reference_context)
   - No test for mixed read/write contention

3. **No test for lock fairness**
   - asyncio.Lock is not guaranteed to be fair
   - Writers could starve readers or vice versa

4. **No test for cancellation**
   - What if task is cancelled while waiting for lock?

5. **No test for reference_graph consistency**
   - Tests check span_summaries count but not reference_graph integrity

6. **No test for memory growth**
   - Large number of summaries could exhaust memory
   - No test for cleanup/eviction

### HIGH Risk Gaps

- **No lock scope verification**: Tests verify lock exists and is correct type, but don't verify it's held for the right duration.
- **Timeout-based deadlock detection is flaky**: 5 second timeout could pass in CI but hide real deadlocks.
- **No exception handling tests**: Lock release on exception path is critical but untested.

---

## Priority Summary: HIGH Risk Gaps Across All Files

| Priority | Gap | Files Affected | Production Risk |
|----------|-----|----------------|-----------------|
| **P0** | Mock-only tests - no real integration | All files | Mocks pass, production fails |
| **P0** | No exception path testing for lock release | patterns, span_processor | Deadlocks on exception |
| **P1** | GIL-masked races in Blackboard tests | pattern_concurrency | Works in CPython, fails in PyPy |
| **P1** | No negative value handling | sqlite_busy_timeout, postgres_pool | Undefined behavior |
| **P1** | Substring checks instead of semantic | sqlite_busy_timeout | False positives |
| **P1** | Lock scope not verified | span_processor | Premature release causes race |
| **P2** | Client cleanup on exception | embedding_client_reuse | Connection leaks |
| **P2** | Arbitrary timeout values in tests | span_processor | Flaky CI |
| **P2** | No cancellation tests | pattern_concurrency | Lock held on cancel |
| **P3** | No pool exhaustion recovery test | postgres_pool | Pool stuck after timeout |
| **P3** | WAL checkpoint not tested | sqlite_busy_timeout | WAL file growth |

## Recommended Test Improvements

### Immediate (P0)

1. Add integration tests with real databases (SQLite file, PostgreSQL container)
2. Add exception path tests that verify locks are released when code throws
3. Verify lock is actually acquired, not just that it exists

### Short-term (P1)

1. Add negative value handling tests for all timeout/size configurations
2. Replace substring checks with AST-based or regex-based semantic checks
3. Add lock scope verification (instrument lock to verify acquire/release timing)

### Medium-term (P2)

1. Add cancellation tests for all async operations
2. Test client cleanup on exception for httpx providers
3. Replace arbitrary timeout values with configurable bounds

### Long-term (P3)

1. Add stress tests for pool exhaustion and recovery
2. Add WAL checkpoint behavior tests
3. Add memory growth tests for long-running scenarios
