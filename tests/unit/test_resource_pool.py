"""
Unit tests for ResourcePool.

Tests resource pooling and concurrency control for the Orchestration Layer.
TDD: These tests are written BEFORE implementation and should FAIL initially.

Test coverage:
- ResourceHandle context manager protocol
- ResourceMetrics dataclass
- ResourceExhaustedError exception
- ResourcePool.acquire() with timeout
- ResourcePool.release() with idempotency
- ResourcePool.check_health() status
- ResourcePool.get_metrics() reporting
- Concurrent acquire/release thread safety
"""

import asyncio
import pytest
from datetime import datetime
from uuid import uuid4

# Import will fail until implementation exists - this is expected for TDD
from scripts.agentica_patterns.resource_pool import (
    ResourcePool,
    ResourceHandle,
    ResourceMetrics,
    ResourceExhaustedError,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def pool() -> ResourcePool:
    """Create ResourcePool with default settings for testing."""
    return ResourcePool(max_concurrent_agents=4, acquire_timeout=30.0)


@pytest.fixture
def small_pool() -> ResourcePool:
    """Create small ResourcePool for timeout/saturation tests."""
    return ResourcePool(max_concurrent_agents=2, acquire_timeout=0.1)


# ============================================================================
# TestResourceHandle
# ============================================================================


class TestResourceHandle:
    """Tests for ResourceHandle context manager."""

    @pytest.mark.asyncio
    async def test_resource_handle_context_manager(self, pool: ResourcePool):
        """Handle auto-releases on async with exit."""
        # Acquire via context manager
        async with await pool.acquire() as handle:
            assert isinstance(handle, ResourceHandle)
            assert handle.resource_id is not None
            assert isinstance(handle.acquired_at, datetime)
            # Inside context: handle is active
            metrics = pool.get_metrics()
            assert metrics.active == 1

        # Outside context: handle is released
        metrics = pool.get_metrics()
        assert metrics.active == 0

    @pytest.mark.asyncio
    async def test_handle_has_pool_reference(self, pool: ResourcePool):
        """Handle has back-reference to owning pool."""
        handle = await pool.acquire()
        try:
            assert handle.pool is pool
        finally:
            await pool.release(handle)

    @pytest.mark.asyncio
    async def test_handle_acquired_at_is_recent(self, pool: ResourcePool):
        """Handle acquired_at timestamp is recent."""
        before = datetime.now()
        handle = await pool.acquire()
        after = datetime.now()

        try:
            assert before <= handle.acquired_at <= after
        finally:
            await pool.release(handle)

    @pytest.mark.asyncio
    async def test_handle_resource_id_unique(self, pool: ResourcePool):
        """Each handle has unique resource_id."""
        handle1 = await pool.acquire()
        handle2 = await pool.acquire()

        try:
            assert handle1.resource_id != handle2.resource_id
        finally:
            await pool.release(handle1)
            await pool.release(handle2)

    @pytest.mark.asyncio
    async def test_context_manager_releases_on_exception(self, pool: ResourcePool):
        """Handle releases even when exception occurs inside context."""
        with pytest.raises(ValueError):
            async with await pool.acquire() as handle:
                raise ValueError("Test exception")

        # Handle should still be released
        metrics = pool.get_metrics()
        assert metrics.active == 0
        assert metrics.total_releases == 1


# ============================================================================
# TestResourceMetrics
# ============================================================================


class TestResourceMetrics:
    """Tests for ResourceMetrics dataclass."""

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, pool: ResourcePool):
        """Metrics accurately track acquisitions and releases."""
        initial = pool.get_metrics()
        assert initial.max_concurrent == 4
        assert initial.active == 0
        assert initial.total_acquisitions == 0
        assert initial.total_releases == 0
        assert initial.denied_due_to_timeout == 0

        # Acquire one
        handle1 = await pool.acquire()
        metrics1 = pool.get_metrics()
        assert metrics1.active == 1
        assert metrics1.total_acquisitions == 1
        assert metrics1.total_releases == 0

        # Acquire another
        handle2 = await pool.acquire()
        metrics2 = pool.get_metrics()
        assert metrics2.active == 2
        assert metrics2.total_acquisitions == 2

        # Release one
        await pool.release(handle1)
        metrics3 = pool.get_metrics()
        assert metrics3.active == 1
        assert metrics3.total_releases == 1

        # Release another
        await pool.release(handle2)
        metrics4 = pool.get_metrics()
        assert metrics4.active == 0
        assert metrics4.total_releases == 2

    @pytest.mark.asyncio
    async def test_metrics_denied_count(self, small_pool: ResourcePool):
        """denied_due_to_timeout increments on timeout."""
        # Saturate pool
        handle1 = await small_pool.acquire()
        handle2 = await small_pool.acquire()

        # Try to acquire with timeout - should fail
        with pytest.raises(ResourceExhaustedError):
            await small_pool.acquire(timeout=0.05)

        metrics = small_pool.get_metrics()
        assert metrics.denied_due_to_timeout == 1

        # Cleanup
        await small_pool.release(handle1)
        await small_pool.release(handle2)

    def test_metrics_is_dataclass(self):
        """ResourceMetrics is a proper dataclass."""
        metrics = ResourceMetrics(
            max_concurrent=4,
            active=2,
            total_acquisitions=10,
            total_releases=8,
            denied_due_to_timeout=1,
        )

        assert metrics.max_concurrent == 4
        assert metrics.active == 2
        assert metrics.total_acquisitions == 10
        assert metrics.total_releases == 8
        assert metrics.denied_due_to_timeout == 1


# ============================================================================
# TestResourceExhaustedError
# ============================================================================


class TestResourceExhaustedError:
    """Tests for ResourceExhaustedError exception."""

    def test_attributes_accessible(self):
        """Error has correct timeout and active_handles attributes."""
        error = ResourceExhaustedError(timeout=30.0, active_handles=4)

        assert error.timeout == 30.0
        assert error.active_handles == 4

    def test_string_representation(self):
        """Error message includes timeout and active handles."""
        error = ResourceExhaustedError(timeout=5.0, active_handles=3)

        msg = str(error)
        assert "5.0" in msg or "5" in msg
        assert "3" in msg
        assert "timeout" in msg.lower() or "exhausted" in msg.lower()

    def test_is_exception_subclass(self):
        """ResourceExhaustedError is a proper Exception."""
        error = ResourceExhaustedError(timeout=1.0, active_handles=0)
        assert isinstance(error, Exception)

        # Can be raised and caught
        with pytest.raises(ResourceExhaustedError) as exc_info:
            raise error
        assert exc_info.value.timeout == 1.0


# ============================================================================
# TestResourcePoolAcquire
# ============================================================================


class TestResourcePoolAcquire:
    """Tests for ResourcePool.acquire()."""

    @pytest.mark.asyncio
    async def test_acquire_respects_limit(self, pool: ResourcePool):
        """Never exceeds max_concurrent_agents."""
        handles = []

        # Acquire up to limit
        for _ in range(4):
            handle = await pool.acquire()
            handles.append(handle)

        metrics = pool.get_metrics()
        assert metrics.active == 4
        assert metrics.active <= metrics.max_concurrent

        # Cleanup
        for handle in handles:
            await pool.release(handle)

    @pytest.mark.asyncio
    async def test_acquire_timeout_raises(self, small_pool: ResourcePool):
        """ResourceExhaustedError raised on timeout."""
        # Saturate pool
        handles = []
        for _ in range(2):
            handles.append(await small_pool.acquire())

        # Next acquire should timeout
        with pytest.raises(ResourceExhaustedError) as exc_info:
            await small_pool.acquire(timeout=0.05)

        assert exc_info.value.timeout == 0.05
        assert exc_info.value.active_handles == 2

        # Cleanup
        for handle in handles:
            await small_pool.release(handle)

    @pytest.mark.asyncio
    async def test_acquire_uses_default_timeout(self, small_pool: ResourcePool):
        """acquire() uses default timeout when none specified."""
        # Saturate pool
        handles = []
        for _ in range(2):
            handles.append(await small_pool.acquire())

        # Next acquire should timeout using default (0.1s)
        start = datetime.now()
        with pytest.raises(ResourceExhaustedError):
            await small_pool.acquire()  # Uses default timeout
        elapsed = (datetime.now() - start).total_seconds()

        # Should have waited approximately the default timeout
        assert elapsed >= 0.05  # At least some waiting
        assert elapsed < 1.0    # Not too long

        # Cleanup
        for handle in handles:
            await small_pool.release(handle)

    @pytest.mark.asyncio
    async def test_acquire_custom_timeout_overrides_default(self, pool: ResourcePool):
        """Custom timeout overrides default timeout."""
        # Saturate pool
        handles = []
        for _ in range(4):
            handles.append(await pool.acquire())

        # Custom short timeout
        start = datetime.now()
        with pytest.raises(ResourceExhaustedError):
            await pool.acquire(timeout=0.05)
        elapsed = (datetime.now() - start).total_seconds()

        assert elapsed < 0.5  # Should be quick due to custom timeout

        # Cleanup
        for handle in handles:
            await pool.release(handle)


# ============================================================================
# TestResourcePoolRelease
# ============================================================================


class TestResourcePoolRelease:
    """Tests for ResourcePool.release()."""

    @pytest.mark.asyncio
    async def test_release_frees_slot(self, small_pool: ResourcePool):
        """Released slot is available for next acquire."""
        # Saturate pool
        handle1 = await small_pool.acquire()
        handle2 = await small_pool.acquire()

        # Release one
        await small_pool.release(handle1)

        # Should now be able to acquire
        handle3 = await small_pool.acquire(timeout=0.1)
        assert handle3 is not None

        # Cleanup
        await small_pool.release(handle2)
        await small_pool.release(handle3)

    @pytest.mark.asyncio
    async def test_double_release_safe(self, pool: ResourcePool):
        """Double release is idempotent and safe."""
        handle = await pool.acquire()

        # First release
        await pool.release(handle)
        metrics1 = pool.get_metrics()
        assert metrics1.total_releases == 1
        assert metrics1.active == 0

        # Second release - should be no-op
        await pool.release(handle)
        metrics2 = pool.get_metrics()
        assert metrics2.total_releases == 1  # Still 1, not 2
        assert metrics2.active == 0

    @pytest.mark.asyncio
    async def test_release_decrements_active(self, pool: ResourcePool):
        """Release decrements active count."""
        handle = await pool.acquire()
        assert pool.get_metrics().active == 1

        await pool.release(handle)
        assert pool.get_metrics().active == 0


# ============================================================================
# TestResourcePoolHealthCheck
# ============================================================================


class TestResourcePoolHealthCheck:
    """Tests for ResourcePool.check_health()."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, pool: ResourcePool):
        """Returns True when pool has available capacity."""
        assert await pool.check_health() is True

        # Acquire some but not all
        handle = await pool.acquire()
        assert await pool.check_health() is True

        await pool.release(handle)

    @pytest.mark.asyncio
    async def test_health_check_saturated(self, small_pool: ResourcePool):
        """Returns False when pool is at capacity."""
        # Saturate pool
        handles = []
        for _ in range(2):
            handles.append(await small_pool.acquire())

        assert await small_pool.check_health() is False

        # Cleanup
        for handle in handles:
            await small_pool.release(handle)

    @pytest.mark.asyncio
    async def test_health_check_recovers_after_release(self, small_pool: ResourcePool):
        """Health check returns True after releasing from saturated state."""
        # Saturate
        handles = []
        for _ in range(2):
            handles.append(await small_pool.acquire())

        assert await small_pool.check_health() is False

        # Release one
        await small_pool.release(handles.pop())

        assert await small_pool.check_health() is True

        # Cleanup
        for handle in handles:
            await small_pool.release(handle)


# ============================================================================
# TestConcurrency
# ============================================================================


class TestConcurrency:
    """Thread safety tests for concurrent acquire/release."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_release(self, pool: ResourcePool):
        """Concurrent acquire/release operations don't corrupt state."""
        num_tasks = 20
        iterations_per_task = 50
        errors: list[Exception] = []

        async def worker(task_id: int) -> None:
            """Worker that acquires and releases multiple times."""
            for i in range(iterations_per_task):
                try:
                    async with await pool.acquire(timeout=5.0) as handle:
                        # Small delay to increase chance of race conditions
                        if i % 10 == 0:
                            await asyncio.sleep(0.001)
                        # Verify handle is valid
                        assert handle.resource_id is not None
                except ResourceExhaustedError:
                    # This is acceptable under high contention
                    pass
                except Exception as e:
                    errors.append(e)

        # Run workers concurrently
        tasks = [asyncio.create_task(worker(i)) for i in range(num_tasks)]
        await asyncio.gather(*tasks)

        # Verify no errors and clean state
        assert len(errors) == 0, f"Concurrency errors: {errors}"

        # All handles should be released
        metrics = pool.get_metrics()
        assert metrics.active == 0
        assert metrics.total_acquisitions == metrics.total_releases

    @pytest.mark.asyncio
    async def test_concurrent_acquire_respects_limit(self, small_pool: ResourcePool):
        """Even under concurrent load, never exceeds limit."""
        max_observed = 0
        max_lock = asyncio.Lock()

        async def observer() -> None:
            """Monitor pool state during test."""
            nonlocal max_observed
            for _ in range(100):
                metrics = small_pool.get_metrics()
                async with max_lock:
                    if metrics.active > max_observed:
                        max_observed = metrics.active
                await asyncio.sleep(0.001)

        async def worker() -> None:
            """Worker that acquires and holds briefly."""
            for _ in range(10):
                try:
                    async with await small_pool.acquire(timeout=0.5) as handle:
                        await asyncio.sleep(0.005)
                except ResourceExhaustedError:
                    pass

        # Run observer and workers
        observer_task = asyncio.create_task(observer())
        worker_tasks = [asyncio.create_task(worker()) for _ in range(10)]

        await asyncio.gather(observer_task, *worker_tasks)

        # Max observed should never exceed limit
        assert max_observed <= 2, f"Exceeded limit: observed {max_observed} active"

    @pytest.mark.asyncio
    async def test_concurrent_metrics_consistency(self, pool: ResourcePool):
        """Metrics remain consistent under concurrent access."""
        errors: list[str] = []

        async def worker(task_id: int) -> None:
            for _ in range(20):
                async with await pool.acquire(timeout=5.0):
                    metrics = pool.get_metrics()
                    # Invariant: active should be positive when we hold a handle
                    if metrics.active < 1:
                        errors.append(f"Task {task_id}: active={metrics.active} while holding handle")
                    # Invariant: active should never exceed max
                    if metrics.active > metrics.max_concurrent:
                        errors.append(f"Task {task_id}: active={metrics.active} > max={metrics.max_concurrent}")
                    await asyncio.sleep(0.001)

        tasks = [asyncio.create_task(worker(i)) for i in range(8)]
        await asyncio.gather(*tasks)

        assert len(errors) == 0, f"Metrics inconsistencies: {errors}"

        # Final state should be clean
        final_metrics = pool.get_metrics()
        assert final_metrics.active == 0
        # acquisitions - releases = active (which is 0)
        assert final_metrics.total_acquisitions == final_metrics.total_releases


# ============================================================================
# TestEdgeCases
# ============================================================================


class TestEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_zero_timeout_fails_immediately(self, small_pool: ResourcePool):
        """Zero timeout fails immediately when pool is saturated."""
        # Saturate
        handles = [await small_pool.acquire() for _ in range(2)]

        start = datetime.now()
        with pytest.raises(ResourceExhaustedError):
            await small_pool.acquire(timeout=0.0)
        elapsed = (datetime.now() - start).total_seconds()

        # Should be nearly instant
        assert elapsed < 0.1

        # Cleanup
        for handle in handles:
            await small_pool.release(handle)

    @pytest.mark.asyncio
    async def test_single_slot_pool(self):
        """Pool with max_concurrent=1 works correctly."""
        single_pool = ResourcePool(max_concurrent_agents=1, acquire_timeout=0.1)

        # First acquire succeeds
        handle = await single_pool.acquire()
        assert single_pool.get_metrics().active == 1

        # Second acquire times out
        with pytest.raises(ResourceExhaustedError):
            await single_pool.acquire(timeout=0.05)

        # Release allows next acquire
        await single_pool.release(handle)
        handle2 = await single_pool.acquire()
        assert single_pool.get_metrics().active == 1

        await single_pool.release(handle2)

    @pytest.mark.asyncio
    async def test_many_sequential_acquire_release(self, pool: ResourcePool):
        """Many sequential acquire/release cycles work correctly."""
        for i in range(100):
            handle = await pool.acquire()
            await pool.release(handle)

        metrics = pool.get_metrics()
        assert metrics.total_acquisitions == 100
        assert metrics.total_releases == 100
        assert metrics.active == 0

    @pytest.mark.asyncio
    async def test_release_wrong_pool_handle(self):
        """Releasing handle from different pool is safe (no-op or error)."""
        pool1 = ResourcePool(max_concurrent_agents=2)
        pool2 = ResourcePool(max_concurrent_agents=2)

        handle1 = await pool1.acquire()

        # Try to release handle1 via pool2 - should be no-op since resource_id won't match
        await pool2.release(handle1)

        # pool1 should still have the handle active
        assert pool1.get_metrics().active == 1

        # Proper cleanup
        await pool1.release(handle1)
        assert pool1.get_metrics().active == 0
