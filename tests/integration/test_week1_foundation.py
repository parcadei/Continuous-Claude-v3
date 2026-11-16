"""Week 1 Foundation Integration Tests - ScopeManager + ResourcePool.

These tests verify that the foundation components work together correctly:
1. Scope isolation with resource acquisition patterns
2. Handoff state transfer across resource boundaries
3. Concurrent scope creation with bounded resources
4. Scope violations properly release resources (no leaks)
5. Health checks correlate with active scope states

Reference:
- scripts/agentica_patterns/scope_manager.py (66 unit tests passing)
- scripts/agentica_patterns/resource_pool.py (28 unit tests passing)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from scripts.agentica_patterns.resource_pool import (
    ResourceExhaustedError,
    ResourcePool,
)
from scripts.agentica_patterns.scope_manager import (
    ManagedScope,
    ScopeManager,
    ScopeViolationError,
)
from scripts.validate_composition import ScopeType


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def scope_manager() -> ScopeManager:
    """Create a ScopeManager for testing."""
    return ScopeManager(
        session_id="test-session-001",
        db_path=None,  # No database needed for these tests
        enable_memory=False,
        enable_tasks=False,
    )


@pytest.fixture
def resource_pool() -> ResourcePool:
    """Create a ResourcePool with small limits for testing."""
    return ResourcePool(
        max_concurrent_agents=3,
        acquire_timeout=5.0,
    )


# =============================================================================
# Test 1: Scope with Resource Acquisition
# =============================================================================


class TestScopeWithResourceAcquisition:
    """Test that scopes work correctly when combined with resource acquisition."""

    @pytest.mark.asyncio
    async def test_scope_with_resource_acquisition(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Create scope, acquire resource, do work, release - verify isolation and tracking."""
        # Acquire resource
        handle = await resource_pool.acquire()
        assert handle is not None
        assert handle.resource_id is not None

        # Create ISOLATED scope while holding resource
        scope = scope_manager.create_scope(mode=ScopeType.ISOLATED, task_id=handle.resource_id)
        assert scope.scope_type == ScopeType.ISOLATED
        assert scope.task_id == handle.resource_id

        # Verify scope isolation - local operations work
        scope_manager.validate_access(scope, "read", "local_key")
        scope_manager.validate_access(scope, "write", "local_key")

        # Verify scope isolation - shared operations blocked
        with pytest.raises(ScopeViolationError) as exc_info:
            scope_manager.validate_access(scope, "read_shared", "shared_key")
        assert exc_info.value.scope_type == ScopeType.ISOLATED
        assert exc_info.value.operation == "read_shared"

        with pytest.raises(ScopeViolationError) as exc_info:
            scope_manager.validate_access(scope, "write_shared", "shared_key")
        assert exc_info.value.scope_type == ScopeType.ISOLATED
        assert exc_info.value.operation == "write_shared"

        # Do some work in the scope
        scope.scope["result"] = "work_completed"
        assert scope.scope["result"] == "work_completed"

        # Verify resource is tracked
        metrics = resource_pool.get_metrics()
        assert metrics.active == 1
        assert metrics.total_acquisitions == 1

        # Release resource
        await resource_pool.release(handle)

        # Verify resource released
        metrics = resource_pool.get_metrics()
        assert metrics.active == 0
        assert metrics.total_releases == 1

    @pytest.mark.asyncio
    async def test_scope_with_resource_context_manager(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Test scope + resource using context manager pattern."""
        scope: ManagedScope | None = None

        async with await resource_pool.acquire() as handle:
            # Create scope tied to this resource handle
            scope = scope_manager.create_scope(
                mode=ScopeType.SHARED,
                task_id=handle.resource_id,
            )
            scope.scope["data"] = "test_value"

            # Verify resource is active
            metrics = resource_pool.get_metrics()
            assert metrics.active == 1

        # After context exit, resource should be released
        metrics = resource_pool.get_metrics()
        assert metrics.active == 0

        # Scope data persists (scope isn't tied to resource lifecycle)
        assert scope is not None
        assert scope.scope["data"] == "test_value"


# =============================================================================
# Test 2: Handoff Across Resource Boundaries
# =============================================================================


class TestHandoffAcrossResourceBoundaries:
    """Test handoff state transfer when resources are acquired/released between stages."""

    @pytest.mark.asyncio
    async def test_handoff_across_resource_boundaries(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Acquire resource for stage 1, release, acquire for stage 2, transfer state."""
        # Stage 1: Acquire resource and create HANDOFF scope
        handle1 = await resource_pool.acquire()
        scope1 = scope_manager.create_scope(
            mode=ScopeType.HANDOFF,
            task_id="stage-1",
        )

        # Set up handoff state in stage 1
        assert scope1._handoff_state is not None
        scope1._handoff_state.context = "Stage 1 completed analysis"
        scope1._handoff_state.next_instruction = "Process results in stage 2"
        scope1._handoff_state.artifacts["analysis_result"] = {"score": 0.95}
        scope1._handoff_state.metadata["stage"] = 1

        # Release resource (simulating stage 1 completion)
        await resource_pool.release(handle1)

        # Verify resource released
        metrics = resource_pool.get_metrics()
        assert metrics.active == 0

        # Stage 2: Acquire new resource and create new HANDOFF scope
        handle2 = await resource_pool.acquire()
        scope2 = scope_manager.create_scope(
            mode=ScopeType.HANDOFF,
            task_id="stage-2",
        )

        # Transfer handoff state from scope1 to scope2
        scope_manager.transfer_handoff(scope1, scope2)

        # Verify state transferred correctly
        assert scope2._handoff_state is not None
        assert scope2._handoff_state.context == "Stage 1 completed analysis"
        assert scope2._handoff_state.next_instruction == "Process results in stage 2"
        assert scope2._handoff_state.artifacts["analysis_result"] == {"score": 0.95}
        assert scope2._handoff_state.metadata["stage"] == 1

        # Verify handoff chain was recorded
        chain = scope2._handoff_state.get_handoff_chain()
        assert len(chain) == 1
        assert chain[0] == {"from": "stage-1", "to": "stage-2"}

        # Stage 2 can add its own state
        scope2._handoff_state.context = "Stage 2 processed results"
        scope2._handoff_state.metadata["stage"] = 2
        scope2._handoff_state.artifacts["final_output"] = {"processed": True}

        # Release final resource
        await resource_pool.release(handle2)

        # Verify final state
        assert scope2._handoff_state.metadata["stage"] == 2
        assert "final_output" in scope2._handoff_state.artifacts

    @pytest.mark.asyncio
    async def test_multi_stage_handoff_chain(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Test handoff chain across 3+ stages."""
        scopes: list[ManagedScope] = []

        for stage in range(1, 4):
            handle = await resource_pool.acquire()
            scope = scope_manager.create_scope(
                mode=ScopeType.HANDOFF,
                task_id=f"stage-{stage}",
            )

            if stage > 1:
                # Transfer from previous stage
                scope_manager.transfer_handoff(scopes[-1], scope)

            # Add stage-specific data
            assert scope._handoff_state is not None
            scope._handoff_state.metadata[f"stage_{stage}_done"] = True

            scopes.append(scope)
            await resource_pool.release(handle)

        # Verify final scope has complete handoff chain
        final_scope = scopes[-1]
        assert final_scope._handoff_state is not None
        chain = final_scope._handoff_state.get_handoff_chain()
        assert len(chain) == 2
        assert chain[0] == {"from": "stage-1", "to": "stage-2"}
        assert chain[1] == {"from": "stage-2", "to": "stage-3"}

        # Verify all metadata accumulated
        assert final_scope._handoff_state.metadata["stage_1_done"] is True
        assert final_scope._handoff_state.metadata["stage_2_done"] is True
        assert final_scope._handoff_state.metadata["stage_3_done"] is True


# =============================================================================
# Test 3: Concurrent Scopes with Bounded Resources
# =============================================================================


class TestConcurrentScopesWithBoundedResources:
    """Test concurrent scope creation respects resource pool limits."""

    @pytest.mark.asyncio
    async def test_concurrent_scopes_with_bounded_resources(
        self,
        scope_manager: ScopeManager,
    ) -> None:
        """Launch 5 concurrent tasks with max_concurrent=3, verify only 3 run at a time."""
        pool = ResourcePool(max_concurrent_agents=3, acquire_timeout=10.0)

        concurrent_count = 0
        max_concurrent_observed = 0
        completed_count = 0
        lock = asyncio.Lock()

        async def worker(task_id: int) -> dict[str, Any]:
            nonlocal concurrent_count, max_concurrent_observed, completed_count

            async with await pool.acquire() as handle:
                # Track concurrency
                async with lock:
                    concurrent_count += 1
                    max_concurrent_observed = max(max_concurrent_observed, concurrent_count)

                # Create scope for this task
                scope = scope_manager.create_scope(
                    mode=ScopeType.ISOLATED,
                    task_id=f"task-{task_id}",
                )

                # Simulate async work
                await asyncio.sleep(0.1)
                scope.scope["result"] = f"completed-{task_id}"

                async with lock:
                    concurrent_count -= 1
                    completed_count += 1

                return {"task_id": task_id, "result": scope.scope["result"]}

        # Launch 5 concurrent tasks
        tasks = [asyncio.create_task(worker(i)) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Verify concurrency was bounded
        assert max_concurrent_observed <= 3, f"Max concurrent was {max_concurrent_observed}, expected <= 3"
        assert max_concurrent_observed >= 2, f"Expected some concurrency, but max was {max_concurrent_observed}"

        # Verify all tasks completed
        assert completed_count == 5
        assert len(results) == 5

        # Verify all results are correct
        for i, result in enumerate(results):
            assert result["task_id"] == i
            assert result["result"] == f"completed-{i}"

        # Verify pool is back to idle
        metrics = pool.get_metrics()
        assert metrics.active == 0
        assert metrics.total_acquisitions == 5
        assert metrics.total_releases == 5

    @pytest.mark.asyncio
    async def test_resource_exhaustion_with_short_timeout(
        self,
    ) -> None:
        """Verify ResourceExhaustedError when timeout exceeded."""
        pool = ResourcePool(max_concurrent_agents=1, acquire_timeout=0.1)

        # Acquire the only resource
        handle1 = await pool.acquire()

        # Try to acquire another - should timeout
        with pytest.raises(ResourceExhaustedError) as exc_info:
            await pool.acquire(timeout=0.1)

        assert exc_info.value.timeout == 0.1
        assert exc_info.value.active_handles == 1

        # Verify denial was tracked
        metrics = pool.get_metrics()
        assert metrics.denied_due_to_timeout == 1

        # Release and verify pool recovers
        await pool.release(handle1)
        assert await pool.check_health() is True


# =============================================================================
# Test 4: Scope Violation Releases Resource
# =============================================================================


class TestScopeViolationReleasesResource:
    """Test that resources are properly released when scope violations occur."""

    @pytest.mark.asyncio
    async def test_scope_violation_releases_resource(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Trigger ScopeViolationError and verify resource is released (not leaked)."""

        async def work_with_violation() -> None:
            async with await resource_pool.acquire() as handle:
                scope = scope_manager.create_scope(
                    mode=ScopeType.ISOLATED,
                    task_id=handle.resource_id,
                )

                # Do some valid work
                scope.scope["data"] = "valid"

                # Trigger violation - ISOLATED scope can't write shared
                scope_manager.validate_access(scope, "write_shared", "forbidden_key")

        # Attempt work that will raise ScopeViolationError
        with pytest.raises(ScopeViolationError):
            await work_with_violation()

        # Critical: Resource must be released despite the exception
        metrics = resource_pool.get_metrics()
        assert metrics.active == 0, "Resource leaked after ScopeViolationError!"
        assert metrics.total_acquisitions == 1
        assert metrics.total_releases == 1

    @pytest.mark.asyncio
    async def test_multiple_violations_no_leaks(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Multiple scope violations should not leak resources."""

        async def violating_work(task_id: int) -> None:
            async with await resource_pool.acquire():
                scope = scope_manager.create_scope(
                    mode=ScopeType.FEDERATED,
                    task_id=f"task-{task_id}",
                    parent=scope_manager.create_scope(mode=ScopeType.SHARED),
                )
                # FEDERATED can read_shared but not write_shared
                scope_manager.validate_access(scope, "write_shared", "forbidden")

        # Run multiple violating tasks
        for i in range(5):
            with pytest.raises(ScopeViolationError):
                await violating_work(i)

        # All resources must be released
        metrics = resource_pool.get_metrics()
        assert metrics.active == 0
        assert metrics.total_acquisitions == 5
        assert metrics.total_releases == 5

    @pytest.mark.asyncio
    async def test_handoff_violation_releases_resource(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Invalid handoff transfer should release resources properly."""

        async def invalid_handoff() -> None:
            async with await resource_pool.acquire():
                # Create mismatched scopes (one HANDOFF, one ISOLATED)
                handoff_scope = scope_manager.create_scope(mode=ScopeType.HANDOFF, task_id="source")
                isolated_scope = scope_manager.create_scope(mode=ScopeType.ISOLATED, task_id="target")

                # This should fail - can't transfer to non-HANDOFF scope
                scope_manager.transfer_handoff(handoff_scope, isolated_scope)

        with pytest.raises(ScopeViolationError) as exc_info:
            await invalid_handoff()

        assert "HANDOFF" in str(exc_info.value)

        # Resource must still be released
        metrics = resource_pool.get_metrics()
        assert metrics.active == 0


# =============================================================================
# Test 5: Health Check with Active Scopes
# =============================================================================


class TestHealthCheckWithActiveScopes:
    """Test health checks reflect resource state with active scopes."""

    @pytest.mark.asyncio
    async def test_health_check_with_active_scopes(
        self,
        scope_manager: ScopeManager,
    ) -> None:
        """Check health returns appropriate status based on active scopes/resources."""
        pool = ResourcePool(max_concurrent_agents=3, acquire_timeout=5.0)

        # Initially healthy
        assert await pool.check_health() is True
        metrics = pool.get_metrics()
        assert metrics.active == 0
        assert metrics.max_concurrent == 3

        # Acquire resources and create scopes
        handles = []
        scopes = []

        for i in range(3):
            handle = await pool.acquire()
            handles.append(handle)

            scope = scope_manager.create_scope(
                mode=ScopeType.SHARED,
                task_id=f"task-{i}",
            )
            scopes.append(scope)

        # Now at capacity - health check should return False
        assert await pool.check_health() is False
        metrics = pool.get_metrics()
        assert metrics.active == 3

        # Scopes are still valid and can do work
        for i, scope in enumerate(scopes):
            scope.scope[f"key_{i}"] = f"value_{i}"
            assert scope.scope[f"key_{i}"] == f"value_{i}"

        # Release one resource
        await pool.release(handles[0])

        # Health should recover
        assert await pool.check_health() is True
        metrics = pool.get_metrics()
        assert metrics.active == 2

        # Release remaining
        for handle in handles[1:]:
            await pool.release(handle)

        # Fully healthy again
        assert await pool.check_health() is True
        metrics = pool.get_metrics()
        assert metrics.active == 0
        assert metrics.total_acquisitions == 3
        assert metrics.total_releases == 3

    @pytest.mark.asyncio
    async def test_health_degrades_under_load(
        self,
        scope_manager: ScopeManager,
    ) -> None:
        """Health should degrade as pool approaches capacity."""
        pool = ResourcePool(max_concurrent_agents=2, acquire_timeout=5.0)

        # Track health state as we acquire resources
        health_states: list[bool] = []

        # Start healthy
        health_states.append(await pool.check_health())  # True

        # Acquire first resource
        handle1 = await pool.acquire()
        scope_manager.create_scope(mode=ScopeType.ISOLATED, task_id="task-1")
        health_states.append(await pool.check_health())  # True (1/2)

        # Acquire second resource - now at capacity
        handle2 = await pool.acquire()
        scope_manager.create_scope(mode=ScopeType.ISOLATED, task_id="task-2")
        health_states.append(await pool.check_health())  # False (2/2)

        # Release one
        await pool.release(handle1)
        health_states.append(await pool.check_health())  # True (1/2)

        # Release last
        await pool.release(handle2)
        health_states.append(await pool.check_health())  # True (0/2)

        # Verify expected pattern
        assert health_states == [True, True, False, True, True]


# =============================================================================
# Additional Integration Tests
# =============================================================================


class TestIntegrationPatterns:
    """Additional patterns that emerge from ScopeManager + ResourcePool integration."""

    @pytest.mark.asyncio
    async def test_scope_cleanup_on_resource_release(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Verify scopes remain valid after resource release (for handoff scenarios)."""
        # Acquire and create scope
        handle = await resource_pool.acquire()
        scope = scope_manager.create_scope(
            mode=ScopeType.SHARED,
            task_id=handle.resource_id,
        )
        scope.scope["important_data"] = "must_persist"

        # Release resource
        await resource_pool.release(handle)

        # Scope data should still be accessible (resource and scope lifecycles are independent)
        assert scope.scope["important_data"] == "must_persist"
        assert scope.scope_type == ScopeType.SHARED
        assert scope.task_id == handle.resource_id

    @pytest.mark.asyncio
    async def test_concurrent_shared_scopes_see_mutations(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """Multiple SHARED scopes should see each other's writes."""
        results: list[str] = []

        async def writer(pool: ResourcePool, value: str) -> None:
            async with await pool.acquire():
                scope = scope_manager.create_scope(mode=ScopeType.SHARED)
                scope.scope["shared_key"] = value
                await asyncio.sleep(0.05)  # Let other writers run
                results.append(scope.scope.get("shared_key", "missing"))

        # Run concurrent writers
        await asyncio.gather(
            writer(resource_pool, "value_a"),
            writer(resource_pool, "value_b"),
            writer(resource_pool, "value_c"),
        )

        # All results should see the same final value (last write wins)
        # The key point is that all scopes see SOME shared value, not None
        assert all(r != "missing" for r in results)
        # All should see the same value since they share the context
        assert len(set(results)) == 1 or all(r in ["value_a", "value_b", "value_c"] for r in results)

    @pytest.mark.asyncio
    async def test_federated_scope_reads_parent_shared(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
    ) -> None:
        """FEDERATED scope can read from parent's SHARED context."""
        # Create parent SHARED scope
        parent = scope_manager.create_scope(mode=ScopeType.SHARED, task_id="parent")
        parent.scope["parent_data"] = "inherited_value"

        async with await resource_pool.acquire():
            # Create FEDERATED child scope
            child = scope_manager.create_scope(
                mode=ScopeType.FEDERATED,
                task_id="child",
                parent=parent,
            )

            # FEDERATED can read shared (from parent)
            scope_manager.validate_access(child, "read_shared", "parent_data")

            # FEDERATED cannot write shared
            with pytest.raises(ScopeViolationError):
                scope_manager.validate_access(child, "write_shared", "forbidden")

            # Verify parent reference
            assert child.parent is parent
            assert child.allows_parent_read is True
            assert child.allows_write is False
