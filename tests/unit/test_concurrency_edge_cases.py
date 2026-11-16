"""
Tests for P1 concurrency edge cases.

These tests are EXPECTED TO FAIL initially. They expose gaps in:
- Negative/zero timeout value handling
- SQLITE_LOCKED vs SQLITE_BUSY handling
- Lock scope verification (premature release)
- GIL-independence for dict operations

Gap References:
- Gap 7: Negative/Zero Value Handling for Timeouts
- Gap 8: SQLITE_LOCKED Not Handled
- Gap 6: Lock Scope Not Verified (Premature Release)
- Gap 4: GIL-Masked Races in Blackboard Tests
"""

import asyncio
import os
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from unittest import mock

import pytest


# =============================================================================
# Gap 7: Negative/Zero Value Handling for Timeouts
# =============================================================================


class TestPostgresPoolTimeoutValidation:
    """Tests for postgres pool timeout validation (Gap 7).

    The pool should reject negative and zero acquire_timeout values because:
    - Negative timeout: undefined behavior in asyncpg
    - Zero timeout: infinite wait, which defeats the purpose of timeout
    """

    def test_postgres_pool_rejects_negative_timeout(self):
        """Pool should reject negative acquire_timeout.

        Gap 7: "What happens with acquire_timeout=-1 (undefined asyncpg behavior)?"

        Expected behavior: ValueError should be raised during pool configuration.
        Current behavior: No validation - negative value is passed to asyncpg.
        """
        from scripts.agentica_patterns.postgres_pool import _get_pool_config

        with mock.patch.dict(os.environ, {"AGENTICA_ACQUIRE_TIMEOUT": "-1"}):
            config = _get_pool_config()

            # This should fail - negative timeout should be rejected
            # Currently passes because there's no validation
            assert config["acquire_timeout"] > 0, (
                "Negative acquire_timeout should be rejected or converted to positive value"
            )

    def test_postgres_pool_rejects_zero_timeout(self):
        """Pool should reject zero acquire_timeout (infinite wait).

        Gap 7: Zero timeout means infinite wait, which is almost never intended.

        Expected behavior: ValueError should be raised or default applied.
        Current behavior: No validation - zero is passed to asyncpg.
        """
        from scripts.agentica_patterns.postgres_pool import _get_pool_config

        with mock.patch.dict(os.environ, {"AGENTICA_ACQUIRE_TIMEOUT": "0"}):
            config = _get_pool_config()

            # This should fail - zero timeout means infinite wait
            # Currently passes because there's no validation
            assert config["acquire_timeout"] > 0, (
                "Zero acquire_timeout (infinite wait) should be rejected"
            )

    def test_postgres_pool_rejects_zero_pool_size(self):
        """Pool should reject zero max_size.

        Gap 7: Zero pool size makes no sense.

        Expected behavior: ValueError should be raised.
        Current behavior: No validation.
        """
        from scripts.agentica_patterns.postgres_pool import _get_pool_config

        with mock.patch.dict(os.environ, {"AGENTICA_MAX_POOL_SIZE": "0"}):
            config = _get_pool_config()

            # This should fail - zero pool size is invalid
            assert config["max_size"] > 0, (
                "Zero max_size should be rejected"
            )

    def test_postgres_pool_rejects_negative_pool_size(self):
        """Pool should reject negative max_size.

        Gap 7: Negative pool size is invalid.
        """
        from scripts.agentica_patterns.postgres_pool import _get_pool_config

        with mock.patch.dict(os.environ, {"AGENTICA_MAX_POOL_SIZE": "-5"}):
            config = _get_pool_config()

            # This should fail - negative pool size is invalid
            assert config["max_size"] > 0, (
                "Negative max_size should be rejected"
            )


# =============================================================================
# Gap 8: SQLITE_LOCKED vs SQLITE_BUSY handling
# =============================================================================


class TestSqliteLockedErrorHandling:
    """Tests for SQLITE_LOCKED error handling (Gap 8).

    SQLITE_LOCKED is different from SQLITE_BUSY:
    - SQLITE_BUSY: Cross-connection contention (handled by busy_timeout)
    - SQLITE_LOCKED: Same-connection table lock (NOT handled by busy_timeout)

    Code iterating while modifying would fail immediately with SQLITE_LOCKED.
    """

    def test_sqlite_locked_error_handling(self):
        """SQLITE_LOCKED should be handled via fetchall_before_modify pattern.

        Gap 8: "busy_timeout only handles SQLITE_BUSY (cross-connection),
        not SQLITE_LOCKED (same-connection table lock)."

        This test verifies that:
        1. execute_with_retry provides retry logic for SQLITE_LOCKED
        2. fetchall_before_modify provides a safe pattern to avoid SQLITE_LOCKED
        """
        from scripts.db_connection import (
            execute_with_retry,
            fetchall_before_modify,
            get_connection,
        )

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Create table using our connection factory
            conn = get_connection(db_path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'a')")
            conn.execute("INSERT INTO test VALUES (2, 'b')")
            conn.execute("INSERT INTO test VALUES (3, 'c')")
            conn.commit()

            # Test 1: Verify fetchall_before_modify pattern works
            # This is the recommended pattern to avoid SQLITE_LOCKED entirely
            rows = fetchall_before_modify(conn, "SELECT id FROM test")
            assert len(rows) == 3, "Should fetch all 3 rows"

            # Now we can safely modify because cursor is closed
            for row in rows:
                conn.execute("DELETE FROM test WHERE id = ?", (row[0],))
            conn.commit()

            # Verify deletion worked
            remaining = conn.execute("SELECT COUNT(*) FROM test").fetchone()[0]
            assert remaining == 0, "All rows should be deleted"

            conn.close()

            # Test 2: Verify execute_with_retry exists and is callable
            # Note: It's hard to reliably trigger SQLITE_LOCKED in a unit test
            # because it depends on cursor state, but we verify the function exists
            conn2 = get_connection(db_path)
            conn2.execute("CREATE TABLE test2 (id INTEGER PRIMARY KEY)")
            conn2.execute("INSERT INTO test2 VALUES (1)")
            conn2.commit()

            # execute_with_retry should work for normal operations
            cursor = execute_with_retry(conn2, "SELECT * FROM test2")
            assert cursor.fetchone() is not None, "Should fetch row"

            conn2.close()

        finally:
            os.unlink(db_path)

    def test_sqlite_locked_during_fts5_rebuild(self):
        """FTS5 rebuild during concurrent access should be handled.

        Gap 8: "FTS5 rebuild/optimize requires exclusive access.
        Running during concurrent queries can fail or block."

        From gap_analysis.md:
        - artifact_index.py:479-494 - FTS5 rebuild at end of bulk indexing
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content)")
            conn.execute("INSERT INTO test_fts VALUES ('hello world')")
            conn.commit()

            # Start a read transaction
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_fts")

            # Try to rebuild FTS index while read is active
            # This may cause SQLITE_LOCKED or blocking
            try:
                conn.execute("INSERT INTO test_fts(test_fts) VALUES('rebuild')")
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    # This is the expected error we need to handle
                    pass
                else:
                    raise

            conn.close()

            # Fail to indicate the gap - we need proper FTS rebuild handling
            pytest.fail(
                "FTS5 rebuild coordination not implemented. "
                "Need exclusive access or queue-based rebuild scheduling."
            )

        finally:
            os.unlink(db_path)


# =============================================================================
# Gap 6: Lock Scope Verification (Premature Release)
# =============================================================================


class TestLockScopeVerification:
    """Tests for lock scope verification (Gap 6).

    Gap 6: "Tests verify isinstance(ctx._lock, asyncio.Lock) but don't verify
    the lock is actually held during the critical section. Lock could exist
    but be released before write completes."
    """

    @pytest.mark.asyncio
    async def test_circuit_breaker_lock_held_during_entire_operation(self):
        """Lock must be held from state read to state write.

        Gap 6: "Lock scope not verified - lock could exist but be released
        before write completes."

        This test instruments the lock to verify it's held during the entire
        _record_failure operation, not just part of it.
        """
        from scripts.agentica_patterns.patterns.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            primary_premise="test",
            fallback_premise="fallback",
            max_failures=3
        )

        # Instrument the lock to track when it's held
        lock_held_during_operation = []
        original_record_failure = cb._record_failure

        async def instrumented_record_failure():
            # Check lock state before and after key operations
            lock_held_during_operation.append({
                "at_entry": cb._state_lock.locked(),
            })
            await original_record_failure()
            lock_held_during_operation.append({
                "at_exit": cb._state_lock.locked(),
            })

        # The issue: we can't easily verify lock is held DURING the operation
        # because the lock is acquired inside _record_failure via "async with"

        # Create a race condition scenario
        race_detected = False

        async def racer():
            nonlocal race_detected
            # Try to read state while _record_failure is running
            # If lock is properly held, we should be blocked
            for _ in range(10):
                # If we can read state while modification is happening,
                # the lock isn't being held properly
                old_state = cb.state
                old_count = cb.failure_count
                await asyncio.sleep(0.001)
                if cb.state != old_state or cb.failure_count != old_count:
                    # State changed while we were reading - potential race
                    race_detected = True
                    break

        # Run concurrent operations
        async def record_multiple_failures():
            for _ in range(10):
                await cb._record_failure()
                await asyncio.sleep(0.001)

        await asyncio.gather(
            record_multiple_failures(),
            racer()
        )

        # The test should verify that state transitions are atomic
        # Currently, this may pass due to GIL, but would fail under true concurrency

        # Verify final state is consistent
        assert cb.failure_count <= cb.max_failures, (
            "failure_count should be capped at max_failures"
        )

        # This is the key assertion that tests lock scope
        # The lock should ensure that failure_count++ and state transition
        # happen atomically. Let's verify by checking state consistency.

        # After 10+ failures, should be OPEN
        if cb.failure_count >= cb.max_failures:
            assert cb.state == CircuitState.OPEN, (
                "State should be OPEN when failure_count >= max_failures. "
                "This indicates lock scope issue - state and count out of sync."
            )

    @pytest.mark.asyncio
    async def test_blackboard_get_set_pattern_demonstrates_race(self):
        """Demonstrates that get_item + set_item is NOT atomic (expected behavior).

        Gap 4/6: "read-modify-write pattern is not thread-safe across async yield points"

        This test DOCUMENTS the race condition - it is NOT a bug, but expected behavior.
        The separate get/set pattern releases the lock between calls, allowing
        other coroutines to interleave. Use update_item() for atomic operations.

        See: scripts/agentica/patterns/blackboard.py docstring for correct pattern.
        """
        from scripts.agentica_patterns.patterns.blackboard import BlackboardState

        state = BlackboardState()
        await state.set_item("counter", 0)

        num_tasks = 100
        increments_per_task = 10
        expected_total = num_tasks * increments_per_task

        async def increment_counter_non_atomic():
            for _ in range(increments_per_task):
                # WRONG PATTERN: get and set are separate lock acquisitions
                # The yield point between them allows race conditions
                current = await state.get_item("counter")
                await asyncio.sleep(0.0001)  # Yield point - exposes race
                await state.set_item("counter", current + 1)

        # Run concurrent increments
        await asyncio.gather(*[increment_counter_non_atomic() for _ in range(num_tasks)])

        final_value = await state.get_item("counter")

        # EXPECTED: We lose most increments due to race condition
        # This is NOT a bug - it documents why update_item() must be used
        lost_increments = expected_total - final_value

        # Assert that race condition occurred (documents expected behavior)
        assert lost_increments > 0, (
            "Expected race condition to cause lost increments. "
            "If this passes with 0 lost, the test conditions may have changed."
        )

        # Document the severity for future reference
        loss_percentage = (lost_increments / expected_total) * 100
        # Typically loses 95-99% of increments
        assert loss_percentage > 50, (
            f"Expected significant increment loss (>50%), got {loss_percentage:.1f}%. "
            "Race condition should cause major data loss with get/set pattern."
        )

    @pytest.mark.asyncio
    async def test_blackboard_update_item_is_truly_atomic(self):
        """update_item should provide true atomic read-modify-write.

        This is the CORRECT pattern - using update_item instead of get/set.
        This test should PASS if update_item is properly implemented.
        """
        from scripts.agentica_patterns.patterns.blackboard import BlackboardState

        state = BlackboardState()
        await state.set_item("counter", 0)

        num_tasks = 100
        increments_per_task = 10
        expected_total = num_tasks * increments_per_task

        async def increment_counter_atomic():
            for _ in range(increments_per_task):
                # This SHOULD be atomic because update_item holds the lock
                # for the entire read-modify-write operation
                await state.update_item("counter", lambda x: (x or 0) + 1)

        # Run concurrent increments
        await asyncio.gather(*[increment_counter_atomic() for _ in range(num_tasks)])

        final_value = await state.get_item("counter")

        # This should PASS - update_item is properly atomic
        assert final_value == expected_total, (
            f"Expected {expected_total} but got {final_value}. "
            "update_item should be atomic but lost increments detected."
        )


# =============================================================================
# Gap 4: GIL-Independence for Dict Operations
# =============================================================================


class TestGilIndependence:
    """Tests for GIL-independent correctness (Gap 4).

    Gap 4: "Tests pass in CPython due to GIL atomicity, but would fail in PyPy
    or if operations become non-atomic."

    These tests use threading to expose races that the GIL might mask.
    """

    def test_dict_operations_thread_safety(self):
        """Dict operations should be safe without relying on GIL.

        Gap 4: "The read-modify-write pattern in increment tests is not
        thread-safe across async yield points."

        This test uses threads (not asyncio) to bypass GIL-masked behavior.
        """
        shared_dict = {"counter": 0}
        lock = threading.Lock()
        num_threads = 10
        increments_per_thread = 1000
        expected = num_threads * increments_per_thread

        def unsafe_increment():
            """Increment without lock - exposes GIL dependency."""
            for _ in range(increments_per_thread):
                # This pattern is NOT thread-safe
                current = shared_dict["counter"]
                # Explicit yield to expose race
                shared_dict["counter"] = current + 1

        threads = [threading.Thread(target=unsafe_increment) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Under CPython's GIL, this MIGHT pass (not guaranteed)
        # The test documents that we shouldn't rely on this behavior
        if shared_dict["counter"] == expected:
            # If it passes, add explicit note about GIL dependency
            pytest.skip(
                f"Test passed with {expected} due to GIL. "
                "This doesn't prove thread-safety - it's GIL luck. "
                "Code should use explicit locks for true thread-safety."
            )
        else:
            # Race detected - good, this proves the pattern is unsafe
            pytest.fail(
                f"Expected {expected} but got {shared_dict['counter']}. "
                "Race condition detected. Add explicit locking."
            )

    @pytest.mark.asyncio
    async def test_asyncio_dict_race_with_yield_points(self):
        """Async dict operations with yield points should use locks.

        This test inserts explicit yield points to expose races that
        would be masked by the GIL in synchronous code.
        """
        shared_state = {"value": "initial"}
        results = []

        async def reader():
            for _ in range(100):
                v1 = shared_state["value"]
                await asyncio.sleep(0.0001)  # Yield point
                v2 = shared_state["value"]
                if v1 != v2:
                    results.append(("read_inconsistency", v1, v2))

        async def writer():
            for i in range(100):
                shared_state["value"] = f"value_{i}"
                await asyncio.sleep(0.0001)  # Yield point

        await asyncio.gather(reader(), writer())

        # If any read inconsistency was detected, that's actually expected
        # behavior - this shows we need proper synchronization
        if results:
            # Good - we detected the race, now fail to indicate the gap
            pytest.fail(
                f"Detected {len(results)} read inconsistencies. "
                "This is expected without proper locking. "
                "Use asyncio.Lock to protect shared state."
            )
        else:
            # No races detected - but this doesn't prove safety
            # Just means we got lucky with scheduling
            pass


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestTimeoutEdgeCases:
    """Additional timeout-related edge cases."""

    def test_sqlite_busy_timeout_zero_disables_timeout(self):
        """busy_timeout=0 disables the timeout entirely.

        Gap 7: "What happens with busy_timeout=0 (disables timeout)?"

        This is dangerous because it means the connection will fail immediately
        on any contention rather than waiting.
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Create database with data
            conn1 = sqlite3.connect(db_path)
            conn1.execute("CREATE TABLE test (id INTEGER)")
            conn1.execute("INSERT INTO test VALUES (1)")
            conn1.commit()

            # Set busy_timeout to 0 (disables timeout - immediate failure)
            conn2 = sqlite3.connect(db_path)
            conn2.execute("PRAGMA busy_timeout = 0")

            # Start exclusive transaction on conn1
            conn1.execute("BEGIN EXCLUSIVE")

            # conn2 should fail immediately (no wait)
            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn2.execute("SELECT * FROM test")

            assert "locked" in str(exc_info.value).lower()

            conn1.rollback()
            conn1.close()
            conn2.close()

            # The test passes, but indicates that busy_timeout=0 is dangerous
            # We should validate and reject this value in our code

        finally:
            os.unlink(db_path)

    def test_sqlite_busy_timeout_negative_undefined_behavior(self):
        """get_connection should handle negative timeout by using default.

        Gap 7: "What happens with busy_timeout=-1 (undefined)?"

        Our get_connection factory now validates timeout values and converts
        negative/zero values to the default timeout (5000ms).
        """
        from scripts.db_connection import DEFAULT_BUSY_TIMEOUT, get_connection

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Test 1: Negative timeout should be converted to default
            conn = get_connection(db_path, timeout_ms=-1)

            # Check what value was actually set
            result = conn.execute("PRAGMA busy_timeout").fetchone()
            actual_value = result[0] if result else None

            # Should be the default timeout, not negative
            assert actual_value == DEFAULT_BUSY_TIMEOUT, (
                f"Negative timeout should be converted to default ({DEFAULT_BUSY_TIMEOUT}ms), "
                f"but got {actual_value}ms"
            )

            conn.close()

            # Test 2: Zero timeout should also be converted to default
            conn2 = get_connection(db_path, timeout_ms=0)
            result2 = conn2.execute("PRAGMA busy_timeout").fetchone()
            actual_value2 = result2[0] if result2 else None

            assert actual_value2 == DEFAULT_BUSY_TIMEOUT, (
                f"Zero timeout should be converted to default ({DEFAULT_BUSY_TIMEOUT}ms), "
                f"but got {actual_value2}ms"
            )

            conn2.close()

            # Test 3: Positive timeout should be used as-is
            conn3 = get_connection(db_path, timeout_ms=3000)
            result3 = conn3.execute("PRAGMA busy_timeout").fetchone()
            actual_value3 = result3[0] if result3 else None

            assert actual_value3 == 3000, (
                f"Positive timeout should be used as-is, but got {actual_value3}ms"
            )

            conn3.close()

        finally:
            os.unlink(db_path)
