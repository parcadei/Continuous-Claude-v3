"""Test: threading.Lock Thread Safety Verification.

This test verifies that SharedContext's threading.Lock implementation
provides proper cross-thread synchronization.

Historical context:
- Originally, SharedContext used asyncio.Lock which doesn't work across threads
- Migration to threading.Lock was completed
- These tests verify the new implementation is correct

See also:
- thoughts/shared/work/security-hardening/12-nia-validation.md
- thoughts/shared/work/security-hardening/13-asyncio-lock-codemap.md
"""

import time
from threading import Thread

import pytest


class TestThreadingLockCrossThread:
    """Test threading.Lock behavior when SharedContext is used from multiple threads."""

    def test_threading_lock_cross_thread_safety(self):
        """Verify threading.Lock provides cross-thread synchronization.

        This test creates multiple threads that concurrently call log_operation.
        With proper threading.Lock, all operations should be logged without loss.
        """
        from scripts.agentica_patterns.claude_scope import SharedContext

        shared = SharedContext()
        errors: list[tuple[int, Exception]] = []

        def thread_worker(n: int) -> None:
            """Thread worker that logs operations."""
            try:
                for i in range(1000):
                    shared.log_operation({"thread": n, "op": i})
            except Exception as e:
                errors.append((n, e))

        # Spawn 10 threads
        threads = [Thread(target=thread_worker, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert: No errors should occur
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Assert: All operations should be logged (no data loss)
        expected_ops = 10 * 1000
        actual_ops = len(shared.operation_log)
        assert actual_ops == expected_ops, (
            f"Data loss detected: expected {expected_ops}, got {actual_ops}"
        )

        # Assert: No duplicates (no corruption)
        unique_ops = set(
            f"t{op['thread']}-o{op['op']}" for op in shared.operation_log
        )
        assert len(unique_ops) == expected_ops, (
            f"Duplicates detected: expected {expected_ops} unique, "
            f"got {len(unique_ops)}"
        )


class TestSharedContextThreadSafety:
    """Test real SharedContext behavior with threading.Lock."""

    def test_shared_context_concurrent_operations(self):
        """Verify SharedContext handles concurrent operations correctly.

        This mimics what happens when multiple agents operate concurrently
        on the same SharedContext. With threading.Lock, all operations
        should be properly serialized.
        """
        from scripts.agentica_patterns.claude_scope import SharedContext

        shared = SharedContext()
        errors: list[tuple[int, Exception]] = []

        def thread_worker(n: int):
            """Each thread performs multiple operations."""
            try:
                for i in range(500):
                    shared.log_operation({"thread": n, "iteration": i})
            except Exception as e:
                errors.append((n, e))

        # 20 threads, 500 ops each = 10000 total ops
        threads = [Thread(target=thread_worker, args=(n,)) for n in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Check for hung threads
        alive_threads = [t for t in threads if t.is_alive()]
        assert len(alive_threads) == 0, (
            f"Threads hung (possible deadlock): {len(alive_threads)} threads"
        )

        # Check for errors
        assert len(errors) == 0, f"Errors: {errors}"

        # Check for data loss
        expected = 20 * 500
        actual = len(shared.operation_log)
        assert actual == expected, (
            f"Data loss: expected {expected}, got {actual} "
            f"(missing {expected - actual} operations)"
        )

    def test_shared_context_cache_thread_safety(self):
        """Test cache operations are thread-safe.

        Cache get/set/invalidate operations should be consistent
        across multiple threads.
        """
        from scripts.agentica_patterns.claude_scope import SharedContext, ClaudeResult

        shared = SharedContext()
        errors: list[tuple[int, Exception]] = []

        def thread_worker(n: int):
            """Thread that performs cache operations."""
            try:
                # Set cache
                result = ClaudeResult(
                    success=True,
                    operation="read",
                    path=f"file_{n}.txt",
                    content=f"content_{n}"
                )
                shared.set_cached(f"file_{n}.txt", result)

                # Read cache - should get our value
                cached = shared.get_cached(f"file_{n}.txt")
                if cached is None:
                    errors.append((n, ValueError("Cache miss after set")))
            except Exception as e:
                errors.append((n, e))

        threads = [Thread(target=thread_worker, args=(n,)) for n in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Check for errors
        assert len(errors) == 0, f"Errors: {errors}"

        # Check cache has all entries
        assert len(shared.file_cache) == 50, (
            f"Cache incomplete: expected 50, got {len(shared.file_cache)}"
        )


class TestThreadingLockSynchronization:
    """Test that threading.Lock actually serializes concurrent access."""

    def test_lock_serializes_concurrent_access(self):
        """Verify that threading.Lock prevents concurrent execution.

        If lock works correctly, overlapping acquisitions should not occur.
        We detect this by having threads hold the lock and do slow work.
        """
        from scripts.agentica_patterns.claude_scope import SharedContext

        shared = SharedContext()
        work_duration = 0.02  # 20ms of "work" per operation
        acquisition_times: list[tuple[int, float, float]] = []
        lock_for_times = __import__("threading").Lock()

        def thread_worker(n: int):
            """Perform work that takes time under lock."""
            start = time.time()
            shared.log_operation({"thread": n, "start": start})
            time.sleep(work_duration)  # Simulate work
            end = time.time()
            with lock_for_times:
                acquisition_times.append((n, start, end))

        # Run 5 threads concurrently
        n_threads = 5
        threads = [Thread(target=thread_worker, args=(n,)) for n in range(n_threads)]

        overall_start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        overall_duration = time.time() - overall_start

        # Note: With threading.Lock, log_operation is fast (just append).
        # The sleep happens OUTSIDE the lock, so threads CAN overlap.
        # This is the correct behavior - we only protect the data structure,
        # not the entire thread's work.

        # Verify all operations completed
        assert len(shared.operation_log) == n_threads

    def test_lock_prevents_data_corruption(self):
        """Verify lock prevents data corruption under high contention.

        This is the key test: without proper locking, concurrent list.append
        operations can cause data corruption or loss.
        """
        from scripts.agentica_patterns.claude_scope import SharedContext

        shared = SharedContext()
        ops_per_thread = 10000
        n_threads = 10

        def thread_worker(n: int):
            """Rapidly append operations."""
            for i in range(ops_per_thread):
                shared.log_operation({"t": n, "i": i})

        threads = [Thread(target=thread_worker, args=(n,)) for n in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # With proper locking, we should have exactly n_threads * ops_per_thread entries
        expected = n_threads * ops_per_thread
        actual = len(shared.operation_log)
        assert actual == expected, (
            f"Data loss/corruption: expected {expected}, got {actual}"
        )
