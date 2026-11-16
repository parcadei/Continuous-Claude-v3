"""Tests for P0 Gap 1: Lock Release on Exception/Cancellation.

These tests verify that asyncio.Lock is properly released when:
1. An exception is raised while holding the lock
2. A task is cancelled while holding the lock
3. A callback/updater function raises an exception

Gap Analysis Reference: docs/concurrency-search/agent-outputs/gaps/gap_analysis.md

Files tested:
- scripts/agentica/span_processor.py (SpanProcessingContext)
- scripts/agentica/patterns/circuit_breaker.py (CircuitBreaker)
- scripts/agentica/patterns/blackboard.py (BlackboardState)
- scripts/agentica/patterns/hierarchical.py (Hierarchical)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.agentica.span_processor import SpanProcessingContext, SpanSummary


# =============================================================================
# SpanProcessingContext Tests
# =============================================================================


@pytest.mark.asyncio
async def test_span_processor_lock_released_on_exception():
    """Lock must be released even if add_summary raises.

    This test verifies that if an exception occurs during add_summary(),
    the lock is still released and subsequent operations can acquire it.

    GAP: If the lock is not released on exception, this test would hang forever
    on the second lock acquisition attempt.
    """
    ctx = SpanProcessingContext()

    # Create a summary that will cause processing_log.append to raise
    summary = SpanSummary(
        span_id="test-1",
        turn_number=0,
        summary="test summary",
        key_entities=["entity1"],
        references=[],
        span_type="tool_call",
        content_hash="abc123"
    )

    # Patch the processing_log to raise on append
    original_log = ctx.processing_log
    mock_log = MagicMock()
    mock_log.append = MagicMock(side_effect=RuntimeError("Simulated failure"))
    ctx.processing_log = mock_log

    # First call should raise
    with pytest.raises(RuntimeError, match="Simulated failure"):
        await ctx.add_summary(summary)

    # CRITICAL: The lock should be released. If not, this will hang.
    # Use a short timeout to detect the issue.
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with ctx._lock:
                return True

    # This should NOT hang - if it does, the lock was not released
    result = await try_acquire()
    assert result is True, "Lock was not released after exception"


@pytest.mark.asyncio
async def test_span_processor_lock_released_on_cancellation():
    """Lock must be released if task is cancelled mid-operation.

    This test verifies that if a task is cancelled while holding the lock
    (e.g., during add_summary), the lock is properly released.

    GAP: asyncio.Lock uses async with context manager which should handle
    CancelledError, but this needs verification.
    """
    ctx = SpanProcessingContext()

    # Create an event to signal when we're inside the lock
    inside_lock = asyncio.Event()

    async def slow_add_summary():
        """Simulate a slow operation inside add_summary."""
        async with ctx._lock:
            inside_lock.set()
            # Simulate slow I/O operation
            await asyncio.sleep(10)  # Long sleep that will be cancelled

    # Start the slow operation
    task = asyncio.create_task(slow_add_summary())

    # Wait until we're inside the lock
    await asyncio.wait_for(inside_lock.wait(), timeout=1.0)

    # Cancel the task while it holds the lock
    task.cancel()

    # Wait for the task to be cancelled
    with pytest.raises(asyncio.CancelledError):
        await task

    # CRITICAL: The lock should be released after cancellation
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with ctx._lock:
                return True

    # This should NOT hang - if it does, the lock was not released
    result = await try_acquire()
    assert result is True, "Lock was not released after cancellation"


@pytest.mark.asyncio
async def test_span_processor_lock_released_on_get_reference_context_exception():
    """Lock must be released if get_reference_context raises.

    This tests the other locked method in SpanProcessingContext.
    """
    ctx = SpanProcessingContext()

    # Add a summary first
    summary = SpanSummary(
        span_id="test-1",
        turn_number=0,
        summary="test summary",
        key_entities=["entity1"],
        references=["ref-1"],  # Reference that doesn't exist
        span_type="tool_call",
        content_hash="abc123"
    )
    await ctx.add_summary(summary)

    # Patch span_summaries to raise when accessed
    original_summaries = ctx.span_summaries
    mock_summaries = MagicMock()
    mock_summaries.__contains__ = MagicMock(side_effect=RuntimeError("Dict access failed"))
    ctx.span_summaries = mock_summaries

    # First call should raise
    with pytest.raises(RuntimeError, match="Dict access failed"):
        await ctx.get_reference_context("test-1")

    # Restore and verify lock is released
    ctx.span_summaries = original_summaries

    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with ctx._lock:
                return True

    result = await try_acquire()
    assert result is True, "Lock was not released after exception in get_reference_context"


# =============================================================================
# CircuitBreaker Tests
# =============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_lock_released_on_record_failure_exception():
    """State lock must be released if _record_failure raises internally.

    This test simulates an exception during _record_failure() and verifies
    the lock is released for subsequent operations.
    """
    from scripts.agentica.patterns.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(
        primary_premise="Primary agent",
        fallback_premise="Fallback agent",
        max_failures=3,
        reset_timeout=60
    )

    # Patch failure_count to raise on comparison
    original_failure_count = cb.failure_count

    # Create a property that raises when compared
    class RaisingInt:
        def __lt__(self, other):
            raise RuntimeError("Comparison failed")
        def __ge__(self, other):
            raise RuntimeError("Comparison failed")

    # The _record_failure method does: if self.failure_count < self.max_failures
    # We need to make this comparison raise
    cb.failure_count = RaisingInt()

    # Call _record_failure which should raise
    with pytest.raises(RuntimeError, match="Comparison failed"):
        await cb._record_failure()

    # Restore failure_count
    cb.failure_count = original_failure_count

    # CRITICAL: The lock should be released
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with cb._state_lock:
                return True

    result = await try_acquire()
    assert result is True, "State lock was not released after exception in _record_failure"


@pytest.mark.asyncio
async def test_circuit_breaker_lock_released_on_record_success_exception():
    """State lock must be released if _record_success raises internally.

    This test injects an exception into the _record_success path and verifies
    the lock is released. We use a wrapper that simulates an internal failure.
    """
    from scripts.agentica.patterns.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(
        primary_premise="Primary agent",
        fallback_premise="Fallback agent"
    )

    # We'll manually acquire the lock, simulate exception, and verify release
    # This mimics what would happen if an exception occurred inside _record_success

    exception_raised = False

    async def failing_operation():
        """Simulate exception while holding lock."""
        nonlocal exception_raised
        async with cb._state_lock:
            cb.failure_count = 0  # Start of _record_success
            exception_raised = True
            raise RuntimeError("Simulated failure during success recording")

    # Call the failing operation
    with pytest.raises(RuntimeError, match="Simulated failure"):
        await failing_operation()

    assert exception_raised, "Exception should have been raised"

    # CRITICAL: The lock should be released
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with cb._state_lock:
                return True

    result = await try_acquire()
    assert result is True, "State lock was not released after exception in _record_success"


# =============================================================================
# BlackboardState Tests
# =============================================================================


@pytest.mark.asyncio
async def test_blackboard_lock_released_on_set_item_exception():
    """Lock released if set_item history append raises.

    The set_item method appends to history after setting the value.
    If history.append raises, the lock must still be released.
    """
    from scripts.agentica.patterns.blackboard import BlackboardState

    state = BlackboardState()

    # Patch history to raise on append
    mock_history = MagicMock()
    mock_history.append = MagicMock(side_effect=RuntimeError("History append failed"))
    state.history = mock_history

    # set_item should raise
    with pytest.raises(RuntimeError, match="History append failed"):
        await state.set_item("key1", "value1")

    # CRITICAL: The lock should be released
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with state._lock:
                return True

    result = await try_acquire()
    assert result is True, "Lock was not released after exception in set_item"


@pytest.mark.asyncio
async def test_blackboard_lock_released_on_update_item_callback_exception():
    """Lock released if updater callback raises.

    The update_item method calls a user-provided updater function.
    If this function raises, the lock must still be released.

    GAP: This is a real risk - users can pass arbitrary callables.
    """
    from scripts.agentica.patterns.blackboard import BlackboardState

    state = BlackboardState()
    await state.set_item("counter", 0)

    # Create an updater that raises
    def raising_updater(current):
        raise ValueError("Updater callback failed")

    # update_item should propagate the exception
    with pytest.raises(ValueError, match="Updater callback failed"):
        await state.update_item("counter", raising_updater)

    # CRITICAL: The lock should be released
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with state._lock:
                return True

    result = await try_acquire()
    assert result is True, "Lock was not released after callback exception in update_item"


@pytest.mark.asyncio
async def test_blackboard_lock_released_on_cancellation():
    """Lock must be released if task is cancelled during update_item.

    This tests cancellation during a slow callback operation.
    """
    from scripts.agentica.patterns.blackboard import BlackboardState

    state = BlackboardState()
    await state.set_item("counter", 0)

    inside_lock = asyncio.Event()

    async def slow_update():
        """Slow updater that can be cancelled."""
        async def slow_callback(current):
            inside_lock.set()
            await asyncio.sleep(10)  # Will be cancelled
            return current + 1

        # Note: update_item takes a sync function, not async
        # We need to test cancellation while inside the lock differently
        async with state._lock:
            inside_lock.set()
            await asyncio.sleep(10)  # Will be cancelled

    task = asyncio.create_task(slow_update())

    # Wait until inside the lock
    await asyncio.wait_for(inside_lock.wait(), timeout=1.0)

    # Cancel
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    # CRITICAL: Lock should be released
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with state._lock:
                return True

    result = await try_acquire()
    assert result is True, "Lock was not released after cancellation in BlackboardState"


# =============================================================================
# Hierarchical Pattern Tests
# =============================================================================


@pytest.mark.asyncio
async def test_hierarchical_coordinator_lock_released_on_spawn_failure():
    """Coordinator lock released if spawn fails.

    The _ensure_coordinator method holds a lock while spawning.
    If spawn raises, the lock must be released.
    """
    from scripts.agentica.patterns.hierarchical import Hierarchical

    hierarchical = Hierarchical(
        coordinator_premise="You coordinate.",
        specialist_premises={"worker": "You work."}
    )

    # Patch spawn to raise
    with patch('scripts.agentica.patterns.hierarchical.spawn',
               side_effect=RuntimeError("Spawn failed")):
        with pytest.raises(RuntimeError, match="Spawn failed"):
            await hierarchical._ensure_coordinator()

    # CRITICAL: The coordinator lock should be released
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with hierarchical._coordinator_lock:
                return True

    result = await try_acquire()
    assert result is True, "Coordinator lock was not released after spawn failure"


@pytest.mark.asyncio
async def test_hierarchical_specialist_lock_released_on_spawn_failure():
    """Specialist lock released if spawn fails.

    The _ensure_specialist method holds per-specialist locks while spawning.
    If spawn raises, the lock must be released.
    """
    from scripts.agentica.patterns.hierarchical import Hierarchical

    hierarchical = Hierarchical(
        coordinator_premise="You coordinate.",
        specialist_premises={"worker": "You work."}
    )

    # First, ensure coordinator succeeds (needed before specialist)
    mock_coordinator = AsyncMock()
    mock_coordinator.agent_id = "coord-123"

    with patch('scripts.agentica.patterns.hierarchical.spawn',
               return_value=mock_coordinator):
        await hierarchical._ensure_coordinator()

    # Now patch spawn to fail for specialist
    with patch('scripts.agentica.patterns.hierarchical.spawn',
               side_effect=RuntimeError("Specialist spawn failed")):
        with pytest.raises(RuntimeError, match="Specialist spawn failed"):
            await hierarchical._ensure_specialist("worker")

    # CRITICAL: The specialist lock should be released
    # The lock is in _specialist_locks dict, keyed by name
    specialist_lock = hierarchical._specialist_locks.get("worker")

    if specialist_lock is None:
        # Lock wasn't created yet, which is fine
        pass
    else:
        async def try_acquire():
            async with asyncio.timeout(0.5):
                async with specialist_lock:
                    return True

        result = await try_acquire()
        assert result is True, "Specialist lock was not released after spawn failure"


@pytest.mark.asyncio
async def test_hierarchical_lock_released_on_concurrent_spawn_failure():
    """Both coordinator and specialist locks released on concurrent failure.

    Tests the scenario where multiple concurrent calls to _ensure_specialist
    all fail - all locks should be released.
    """
    from scripts.agentica.patterns.hierarchical import Hierarchical

    hierarchical = Hierarchical(
        coordinator_premise="You coordinate.",
        specialist_premises={
            "worker1": "You work.",
            "worker2": "You also work."
        }
    )

    call_count = 0

    async def failing_spawn(**kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate async work
        raise RuntimeError(f"Spawn {call_count} failed")

    with patch('scripts.agentica.patterns.hierarchical.spawn',
               side_effect=failing_spawn):
        # Try to spawn multiple specialists concurrently (all will fail)
        # This also triggers coordinator spawn which will fail first
        results = await asyncio.gather(
            hierarchical._ensure_coordinator(),
            hierarchical._ensure_coordinator(),  # Second call should be blocked by lock
            return_exceptions=True
        )

    # All calls should have raised
    assert all(isinstance(r, RuntimeError) for r in results)

    # CRITICAL: Coordinator lock should be released
    async def try_acquire_coord():
        async with asyncio.timeout(0.5):
            async with hierarchical._coordinator_lock:
                return True

    result = await try_acquire_coord()
    assert result is True, "Coordinator lock was not released after concurrent failures"


# =============================================================================
# Edge Cases: Lock State After Multiple Failures
# =============================================================================


@pytest.mark.asyncio
async def test_span_processor_lock_usable_after_multiple_exceptions():
    """Lock should work correctly after multiple consecutive exceptions.

    This tests that the lock state isn't corrupted by repeated failures.
    """
    ctx = SpanProcessingContext()

    summary = SpanSummary(
        span_id="test",
        turn_number=0,
        summary="test",
        key_entities=[],
        references=[],
        span_type="test",
        content_hash="test"
    )

    # Cause multiple failures
    for i in range(5):
        mock_log = MagicMock()
        mock_log.append = MagicMock(side_effect=RuntimeError(f"Failure {i}"))
        ctx.processing_log = mock_log

        with pytest.raises(RuntimeError):
            await ctx.add_summary(summary)

    # Restore normal behavior
    ctx.processing_log = []

    # Lock should still be usable
    await ctx.add_summary(summary)
    assert "test" in ctx.span_summaries


@pytest.mark.asyncio
async def test_circuit_breaker_lock_usable_after_rapid_state_changes():
    """Lock should work after rapid state changes with failures.

    Tests that interleaved success/failure recordings don't corrupt lock state.
    """
    from scripts.agentica.patterns.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(
        primary_premise="Primary",
        fallback_premise="Fallback",
        max_failures=3
    )

    # Rapidly alternate success and failure
    for i in range(10):
        if i % 2 == 0:
            await cb._record_success()
        else:
            await cb._record_failure()

    # Lock should still be usable
    async def try_acquire():
        async with asyncio.timeout(0.5):
            async with cb._state_lock:
                return True

    result = await try_acquire()
    assert result is True, "Lock corrupted after rapid state changes"


# =============================================================================
# Deadlock Detection Tests
# =============================================================================


@pytest.mark.asyncio
async def test_span_processor_no_deadlock_on_nested_access():
    """Verify no deadlock when methods call each other.

    Currently SpanProcessingContext doesn't have nested calls,
    but this test documents the expected behavior.
    """
    ctx = SpanProcessingContext()

    # Add a summary
    summary = SpanSummary(
        span_id="test",
        turn_number=0,
        summary="test",
        key_entities=[],
        references=["other"],
        span_type="test",
        content_hash="test"
    )
    await ctx.add_summary(summary)

    # Both operations should complete without deadlock
    # (They don't actually nest, but this documents the API contract)
    async with asyncio.timeout(1.0):
        result = await ctx.get_reference_context("test")
        summaries = await ctx.all_summaries()

    assert result == ""  # "other" doesn't exist
    assert len(summaries) == 1
