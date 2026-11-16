"""Tests for threading.Lock migration from asyncio.Lock.

These tests implement TDD Phase 1 (Red): they MUST FAIL with the current
asyncio.Lock implementation and PASS after migration to threading.Lock.

The core issue: asyncio.Lock provides NO cross-thread synchronization when
threads create their own event loops. This is a fundamental design flaw for
shared state accessed from multiple threads.

Test Strategy:
1. Type assertions - verify lock type is threading.Lock
2. API assertions - verify methods are synchronous (not coroutines)
3. Behavioral assertions - verify actual cross-thread synchronization works
"""

import asyncio
import inspect
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest


class TestSharedContextLockType:
    """Tests that SharedContext uses threading.Lock instead of asyncio.Lock."""

    def test_shared_context_uses_threading_lock(self) -> None:
        """Assert SharedContext._lock is threading.Lock, not asyncio.Lock.

        EXPECTED: FAIL with current implementation (uses asyncio.Lock)
        EXPECTED: PASS after migration to threading.Lock
        """
        from scripts.agentica.claude_scope import SharedContext

        ctx = SharedContext()

        # The lock should be threading.Lock (or threading.RLock)
        # NOT asyncio.Lock
        assert isinstance(ctx._lock, (threading.Lock, type(threading.Lock()))), (
            f"SharedContext._lock should be threading.Lock, got {type(ctx._lock)}"
        )

        # Explicitly verify it's NOT asyncio.Lock
        assert not isinstance(ctx._lock, asyncio.Lock), (
            "SharedContext._lock should NOT be asyncio.Lock"
        )

    def test_shared_context_methods_are_sync(self) -> None:
        """Assert SharedContext methods are NOT coroutines (no async).

        After migration, methods should be synchronous since they only
        need to acquire a threading.Lock (which doesn't require await).

        EXPECTED: FAIL with current implementation (methods are async)
        EXPECTED: PASS after migration to sync methods
        """
        from scripts.agentica.claude_scope import SharedContext

        ctx = SharedContext()

        # These methods should NOT be coroutine functions after migration
        methods_to_check = ['get_cached', 'set_cached', 'invalidate', 'log_operation']

        for method_name in methods_to_check:
            method = getattr(ctx, method_name)
            assert not asyncio.iscoroutinefunction(method), (
                f"SharedContext.{method_name} should be synchronous, not async"
            )


class TestSpanProcessingContextLockType:
    """Tests that SpanProcessingContext uses threading.Lock instead of asyncio.Lock."""

    def test_span_processing_context_uses_threading_lock(self) -> None:
        """Assert SpanProcessingContext._lock is threading.Lock, not asyncio.Lock.

        EXPECTED: FAIL with current implementation (uses asyncio.Lock)
        EXPECTED: PASS after migration to threading.Lock
        """
        from scripts.agentica.span_processor import SpanProcessingContext

        ctx = SpanProcessingContext()

        # The lock should be threading.Lock (or threading.RLock)
        # NOT asyncio.Lock
        assert isinstance(ctx._lock, (threading.Lock, type(threading.Lock()))), (
            f"SpanProcessingContext._lock should be threading.Lock, got {type(ctx._lock)}"
        )

        # Explicitly verify it's NOT asyncio.Lock
        assert not isinstance(ctx._lock, asyncio.Lock), (
            "SpanProcessingContext._lock should NOT be asyncio.Lock"
        )

    def test_span_processing_context_methods_are_sync(self) -> None:
        """Assert SpanProcessingContext methods are NOT coroutines.

        After migration, methods should be synchronous since they only
        need to acquire a threading.Lock (which doesn't require await).

        EXPECTED: FAIL with current implementation (methods are async)
        EXPECTED: PASS after migration to sync methods
        """
        from scripts.agentica.span_processor import SpanProcessingContext

        ctx = SpanProcessingContext()

        # These methods should NOT be coroutine functions after migration
        methods_to_check = ['add_summary', 'get_reference_context']

        for method_name in methods_to_check:
            method = getattr(ctx, method_name)
            assert not asyncio.iscoroutinefunction(method), (
                f"SpanProcessingContext.{method_name} should be synchronous, not async"
            )


class TestCrossThreadSynchronization:
    """Tests that verify actual cross-thread synchronization behavior.

    These tests demonstrate the REAL problem: asyncio.Lock does NOT
    synchronize across threads because each thread creates its own event loop.
    """

    def test_shared_context_cross_thread_synchronization(self) -> None:
        """Verify lock prevents simultaneous access across threads.

        This test creates multiple threads that all try to modify SharedContext
        simultaneously. With proper threading.Lock, operations should be atomic.
        With asyncio.Lock, there's no cross-thread synchronization.

        EXPECTED: FAIL with asyncio.Lock (race conditions cause inconsistent state)
        EXPECTED: PASS with threading.Lock (operations are properly serialized)
        """
        from scripts.agentica.claude_scope import SharedContext

        ctx = SharedContext()

        # Track the order of operations for verification
        operation_order: list[str] = []
        operation_lock = threading.Lock()  # For tracking, not for the SUT

        # Sentinel to detect race conditions
        race_detected = threading.Event()

        def worker(worker_id: int, iterations: int = 100) -> None:
            """Worker that performs cache operations."""
            for i in range(iterations):
                key = f"worker_{worker_id}_key_{i}"
                value: Any = {"worker": worker_id, "iteration": i}

                # Try to set and immediately get - should be consistent
                # With threading.Lock this is atomic
                # With asyncio.Lock each thread has its own event loop
                if asyncio.iscoroutinefunction(ctx.set_cached):
                    # Current (buggy) async implementation
                    asyncio.run(ctx.set_cached(key, value))
                    result = asyncio.run(ctx.get_cached(key))
                else:
                    # Expected (fixed) sync implementation
                    ctx.set_cached(key, value)
                    result = ctx.get_cached(key)

                # Verify what we wrote is what we read
                if result != value:
                    race_detected.set()

                with operation_lock:
                    operation_order.append(f"w{worker_id}:i{i}")

        # Create multiple threads
        threads = []
        for worker_id in range(4):
            t = threading.Thread(target=worker, args=(worker_id, 50))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # With threading.Lock, no races should occur
        assert not race_detected.is_set(), (
            "Race condition detected: cached values were inconsistent"
        )

        # Verify all operations completed
        assert len(operation_order) == 4 * 50, (
            f"Expected 200 operations, got {len(operation_order)}"
        )

    def test_span_processing_context_cross_thread_synchronization(self) -> None:
        """Verify SpanProcessingContext lock prevents simultaneous access.

        EXPECTED: FAIL with asyncio.Lock (race conditions)
        EXPECTED: PASS with threading.Lock (proper synchronization)
        """
        from scripts.agentica.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()

        # Track for race detection
        race_detected = threading.Event()

        def worker(worker_id: int, iterations: int = 50) -> None:
            """Worker that adds span summaries."""
            for i in range(iterations):
                summary = SpanSummary(
                    span_id=f"span_{worker_id}_{i}",
                    turn_number=i,
                    summary=f"Summary from worker {worker_id}, iteration {i}",
                    key_entities=[f"entity_{worker_id}"],
                    references=[],
                    span_type="test",
                    content_hash=f"hash_{worker_id}_{i}",
                )

                if asyncio.iscoroutinefunction(ctx.add_summary):
                    # Current (buggy) async implementation
                    asyncio.run(ctx.add_summary(summary))
                else:
                    # Expected (fixed) sync implementation
                    ctx.add_summary(summary)

                # Verify it was stored
                if asyncio.iscoroutinefunction(ctx.get_reference_context):
                    _ = asyncio.run(ctx.get_reference_context(summary.span_id))
                else:
                    _ = ctx.get_reference_context(summary.span_id)

        # Create multiple threads
        threads = []
        for worker_id in range(4):
            t = threading.Thread(target=worker, args=(worker_id, 50))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify all summaries were stored (no lost updates)
        expected_count = 4 * 50  # 4 workers * 50 iterations
        actual_count = len(ctx.span_summaries)

        assert actual_count == expected_count, (
            f"Expected {expected_count} summaries, got {actual_count}. "
            "Lost updates indicate race condition."
        )


class TestLockBehaviorUnderContention:
    """Tests that verify lock behavior under high contention scenarios."""

    def test_increment_counter_atomicity(self) -> None:
        """Classic thread-safety test: concurrent counter increments.

        This is a simplified test that demonstrates the core issue.
        A counter should be incremented exactly N*M times when N threads
        each increment M times.

        With asyncio.Lock: each thread's asyncio.run() creates its own loop,
        so the lock doesn't synchronize across threads.

        With threading.Lock: proper synchronization.
        """
        from scripts.agentica.claude_scope import SharedContext

        ctx = SharedContext()

        # Use the operation_log as a counter proxy
        num_threads = 10
        increments_per_thread = 100

        def increment_worker() -> None:
            for _ in range(increments_per_thread):
                op = {"type": "increment", "timestamp": time.time()}
                if asyncio.iscoroutinefunction(ctx.log_operation):
                    asyncio.run(ctx.log_operation(op))
                else:
                    ctx.log_operation(op)

        threads = [
            threading.Thread(target=increment_worker)
            for _ in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = num_threads * increments_per_thread
        actual = len(ctx.operation_log)

        assert actual == expected, (
            f"Expected {expected} operations, got {actual}. "
            f"Lost {expected - actual} operations due to race conditions."
        )
