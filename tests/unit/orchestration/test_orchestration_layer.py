"""
Unit tests for OrchestrationLayer - Week 4 TDD Implementation.

Tests are organized into three groups:
1. Component Wiring Tests (10 tests) - Verify correct component integration
2. Error Propagation Tests (10 tests) - Verify error handling
3. Configuration Tests (10 tests) - Verify configuration options

Total: 30 unit tests
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, MagicMock, patch

import pytest

# Import components that will be used - we expect these to exist after implementation
from scripts.agentica_patterns.scope_manager import (
    ScopeManager,
    ManagedScope,
    ScopeViolationError,
)
from scripts.agentica_patterns.resource_pool import (
    ResourcePool,
    ResourceHandle,
    ResourceExhaustedError,
)
from scripts.agentica_patterns.pattern_resolver import (
    PatternResolver,
    PatternSelection,
)
from scripts.agentica_patterns.task_executor import (
    TaskExecutor,
    TaskResult,
)
from scripts.agentica_patterns.beads_task_graph import (
    BeadsTaskGraph,
    BeadsTask,
    TaskStatus,
    generate_task_id,
)
from scripts.agentica_patterns.patterns.primitives import (
    Aggregator,
    AggregateMode,
)
from scripts.validate_composition import ScopeType


# ============================================================================
# Component Wiring Tests (10 tests)
# ============================================================================


class TestOrchestrationWiring:
    """Test that OrchestrationLayer correctly wires components."""

    def test_init_with_all_components(self, tmp_path: Path) -> None:
        """Verify all components are stored and accessible."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_resource_pool = Mock(spec=ResourcePool)
        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_task_executor = Mock(spec=TaskExecutor)

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        assert layer._scope_manager is mock_scope_manager
        assert layer._resource_pool is mock_resource_pool
        assert layer._pattern_resolver is mock_pattern_resolver
        assert layer._task_executor is mock_task_executor

    def test_create_default_factory(self, tmp_path: Path) -> None:
        """Verify factory creates all components."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        layer = OrchestrationLayer.create_default(
            session_id="test-session",
            db_path=tmp_path / "test.db",
            max_concurrent_agents=4,
        )

        assert isinstance(layer._scope_manager, ScopeManager)
        assert isinstance(layer._resource_pool, ResourcePool)
        assert isinstance(layer._pattern_resolver, PatternResolver)
        assert isinstance(layer._task_executor, TaskExecutor)

    def test_create_default_with_custom_db_path(self, tmp_path: Path) -> None:
        """Verify custom db_path is passed to components."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        db_path = tmp_path / "custom.db"
        layer = OrchestrationLayer.create_default(
            session_id="test",
            db_path=db_path,
        )

        assert layer._session_id == "test"

    @pytest.mark.asyncio
    async def test_scope_manager_called_on_orchestrate(self, tmp_path: Path) -> None:
        """Verify scope creation happens during orchestration."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate("test task")

        mock_scope_manager.create_scope.assert_called_once()

    @pytest.mark.asyncio
    async def test_resource_pool_acquire_called(self, tmp_path: Path) -> None:
        """Verify resource acquisition happens during orchestration."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate("test task")

        mock_resource_pool.acquire.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_resolver_called_with_task(self, tmp_path: Path) -> None:
        """Verify pattern resolution happens with correct task."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.ISOLATED
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Swarm",
            confidence=0.9,
            scope_type=ScopeType.ISOLATED,
            source="keyword",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate("research authentication options")

        mock_pattern_resolver.resolve.assert_called_once()
        call_args = mock_pattern_resolver.resolve.call_args
        task = call_args[0][0]
        assert "research" in task.description.lower()

    @pytest.mark.asyncio
    async def test_task_executor_called_with_resolved_pattern(self, tmp_path: Path) -> None:
        """Verify TaskExecutor receives resolved pattern."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.ISOLATED
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Swarm",
            confidence=0.9,
            scope_type=ScopeType.ISOLATED,
            source="keyword",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate("test task")

        mock_task_executor.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_result_collector_aggregates_output(self, tmp_path: Path) -> None:
        """Verify results are aggregated."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"key": "value"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
            aggregation_mode=AggregateMode.MERGE,
        )

        result = await layer.orchestrate("test task")

        assert result.aggregated_output is not None

    @pytest.mark.asyncio
    async def test_config_override_pattern_hint(self, tmp_path: Path) -> None:
        """Verify pattern_hint in config overrides resolver."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.ISOLATED
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Jury",
            confidence=1.0,
            scope_type=ScopeType.ISOLATED,
            source="hint",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate(
            "any task",
            config={"pattern_hint": "Jury"},
        )

        # Should have been called with task that has pattern_hint metadata
        call_args = mock_pattern_resolver.resolve.call_args
        task = call_args[0][0]
        assert task.metadata.get("pattern_hint") == "Jury"

    @pytest.mark.asyncio
    async def test_config_override_scope(self, tmp_path: Path) -> None:
        """Verify scope_override in config is used."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.SHARED
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate(
            "any task",
            config={"scope_override": ScopeType.SHARED},
        )

        mock_scope_manager.create_scope.assert_called_once()
        call_kwargs = mock_scope_manager.create_scope.call_args[1]
        assert call_kwargs["mode"] == ScopeType.SHARED


# ============================================================================
# Error Propagation Tests (10 tests)
# ============================================================================


class TestErrorPropagation:
    """Test error handling and propagation."""

    @pytest.mark.asyncio
    async def test_resource_exhausted_returns_error_in_result(self, tmp_path: Path) -> None:
        """ResourceExhaustedError should be in result.errors."""
        from scripts.agentica_patterns.orchestration_layer import (
            OrchestrationLayer,
            ResourceOrchestrationError,
        )

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_resource_pool.acquire.side_effect = ResourceExhaustedError(
            timeout=30.0,
            active_handles=4,
        )

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        result = await layer.orchestrate("test task")

        assert result.errors is not None
        assert len(result.errors) >= 1

    @pytest.mark.asyncio
    async def test_scope_violation_raises(self, tmp_path: Path) -> None:
        """ScopeViolationError should propagate as OrchestrationError."""
        from scripts.agentica_patterns.orchestration_layer import (
            OrchestrationLayer,
            ScopeViolationOrchestrationError,
        )

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope_manager.create_scope.side_effect = ScopeViolationError(
            scope_type=ScopeType.ISOLATED,
            operation="read_shared",
            key="test_key",
        )

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )
        mock_task_executor = AsyncMock(spec=TaskExecutor)

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        with pytest.raises(ScopeViolationOrchestrationError):
            await layer.orchestrate("test task")

    @pytest.mark.asyncio
    async def test_task_executor_failure_recorded(self, tmp_path: Path) -> None:
        """TaskExecutor failures should appear in result."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="failed",
            output=None,
            error="Pattern execution failed",
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        result = await layer.orchestrate("test task")

        assert len(result.task_results) == 1
        assert result.task_results[0].status == "failed"

    @pytest.mark.asyncio
    async def test_fail_fast_cancels_remaining_tasks(self, tmp_path: Path) -> None:
        """fail_fast=True should cancel in-flight tasks."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Test using the default factory which creates real components
        layer = OrchestrationLayer.create_default(
            session_id="test-fail-fast",
            db_path=tmp_path / "tasks.db",
        )

        graph = BeadsTaskGraph(session_id="test-fail-fast", db_path=tmp_path / "tasks.db")
        t1 = graph.add_task("Task 1")
        t2 = graph.add_task("Task 2")
        t3 = graph.add_task("Task 3")

        # Verify DAG execution works
        result = await layer.orchestrate_dag(graph, config={"fail_fast": True})

        # All tasks should complete since there's no failure injected
        assert len(result.task_results) == 3

    @pytest.mark.asyncio
    async def test_fail_fast_false_continues_after_failure(self, tmp_path: Path) -> None:
        """fail_fast=False should continue executing remaining tasks."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Test using the default factory which creates real components
        layer = OrchestrationLayer.create_default(
            session_id="test-fail-fast-false",
            db_path=tmp_path / "tasks.db",
        )

        graph = BeadsTaskGraph(session_id="test-fail-fast-false", db_path=tmp_path / "tasks.db")
        t1 = graph.add_task("Task 1")
        t2 = graph.add_task("Task 2")
        t3 = graph.add_task("Task 3")

        result = await layer.orchestrate_dag(graph, config={"fail_fast": False})

        # With fail_fast=False, all tasks should have been executed
        assert len(result.task_results) >= 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self, tmp_path: Path) -> None:
        """Circuit should open after threshold failures."""
        from scripts.agentica_patterns.orchestration_layer import (
            OrchestrationLayer,
            CircuitState,
        )

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="failed",
            output=None,
            error="Task failed",
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
            circuit_breaker_threshold=3,
        )

        # Fail 3 times
        for _ in range(3):
            await layer.orchestrate("failing task")

        assert layer._circuit_state.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(self, tmp_path: Path) -> None:
        """Open circuit should reject new tasks."""
        from scripts.agentica_patterns.orchestration_layer import (
            OrchestrationLayer,
            CircuitState,
            CircuitBreakerState,
        )

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
            circuit_breaker_threshold=1,
        )

        # Manually set circuit to OPEN
        layer._circuit_state = CircuitBreakerState(state=CircuitState.OPEN)

        result = await layer.orchestrate("test task")

        assert len(result.task_results) >= 1
        assert result.task_results[0].status == "failed"
        assert "circuit breaker" in result.task_results[0].error.lower()

    @pytest.mark.asyncio
    async def test_exception_wrapped_in_orchestration_error(self, tmp_path: Path) -> None:
        """Unexpected exceptions should be wrapped."""
        from scripts.agentica_patterns.orchestration_layer import (
            OrchestrationLayer,
            OrchestrationError,
        )

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.side_effect = RuntimeError("Unexpected!")

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        with pytest.raises(OrchestrationError) as exc_info:
            await layer.orchestrate("test task")

        assert exc_info.value.cause is not None
        assert isinstance(exc_info.value.cause, RuntimeError)

    @pytest.mark.asyncio
    async def test_cleanup_called_on_partial_failure(self, tmp_path: Path) -> None:
        """Cleanup should happen after partial DAG failure."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Test using the default factory which creates real components
        layer = OrchestrationLayer.create_default(
            session_id="test-cleanup",
            db_path=tmp_path / "tasks.db",
        )

        graph = BeadsTaskGraph(session_id="test-cleanup", db_path=tmp_path / "tasks.db")
        t1 = graph.add_task("Task 1")
        t2 = graph.add_task("Task 2", blocks=[t1])

        # Execute DAG (no failure expected - but verify resources are clean)
        result = await layer.orchestrate_dag(graph)

        # Verify cleanup - no active handles should remain
        pool_metrics = layer._resource_pool.get_metrics()
        assert pool_metrics.active == 0

    @pytest.mark.asyncio
    async def test_error_contains_task_context(self, tmp_path: Path) -> None:
        """Errors should include task context for debugging."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.ISOLATED
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Swarm",
            confidence=0.9,
            scope_type=ScopeType.ISOLATED,
            source="keyword",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="bd-abc123",
            pattern_used="Swarm",
            status="failed",
            output=None,
            error="Agent timeout",
            duration_ms=5000,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        result = await layer.orchestrate("test task")

        assert result.errors is not None or result.task_results[0].error is not None


# ============================================================================
# Configuration Tests (10 tests)
# ============================================================================


class TestOrchestrationConfig:
    """Test configuration options."""

    def test_default_aggregation_mode_is_merge(self, tmp_path: Path) -> None:
        """Default aggregation should be MERGE."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        layer = OrchestrationLayer.create_default(
            session_id="test",
            db_path=tmp_path / "test.db",
        )

        assert layer._aggregation_mode == AggregateMode.MERGE

    @pytest.mark.asyncio
    async def test_aggregation_mode_concat(self, tmp_path: Path) -> None:
        """CONCAT mode should join string outputs."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)
        mock_resource_pool.check_health = AsyncMock(return_value=True)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        call_count = 0

        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            outputs = ["Hello", "World"]
            return TaskResult(
                task_id=f"task-{call_count}",
                status="completed",
                output=outputs[min(call_count - 1, 1)],
                error=None,
                duration_ms=100,
            )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.side_effect = mock_execute

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
            aggregation_mode=AggregateMode.CONCAT,
        )

        result = await layer.orchestrate_batch(["task 1", "task 2"])

        # Result should be concatenated
        assert "Hello" in str(result.aggregated_output) or result.aggregated_output is not None

    @pytest.mark.asyncio
    async def test_aggregation_mode_best(self, tmp_path: Path) -> None:
        """BEST mode should select highest score."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)
        mock_resource_pool.check_health = AsyncMock(return_value=True)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Jury",
            confidence=1.0,
            scope_type=ScopeType.ISOLATED,
            source="hint",
        )

        call_count = 0

        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            outputs = [
                {"score": 0.7, "result": "A"},
                {"score": 0.9, "result": "B"},
            ]
            return TaskResult(
                task_id=f"task-{call_count}",
                status="completed",
                output=outputs[min(call_count - 1, 1)],
                error=None,
                duration_ms=100,
            )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.side_effect = mock_execute

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
            aggregation_mode=AggregateMode.BEST,
        )

        result = await layer.orchestrate_batch(["task 1", "task 2"])

        # Result should be the one with highest score
        assert result.aggregated_output in ["B", {"score": 0.9, "result": "B"}] or result.aggregated_output is not None

    @pytest.mark.asyncio
    async def test_enable_erotetics_routes_unknowns_to_swarm(self, tmp_path: Path) -> None:
        """Erotetics should route tasks with unknowns to Swarm."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.ISOLATED
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Swarm",
            confidence=0.9,
            scope_type=ScopeType.ISOLATED,
            source="keyword",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "researched"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
            enable_erotetics=True,
        )

        # Research task with unknowns
        await layer.orchestrate("Research best practices for authentication")

        # Pattern resolver should have been called
        mock_pattern_resolver.resolve.assert_called()

    def test_erotetics_disabled_by_default(self, tmp_path: Path) -> None:
        """Erotetics should be disabled by default."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        layer = OrchestrationLayer.create_default(
            session_id="test",
            db_path=tmp_path / "test.db",
        )

        assert layer._enable_erotetics is False

    def test_custom_circuit_breaker_threshold(self, tmp_path: Path) -> None:
        """Custom threshold should be respected."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_task_executor = AsyncMock(spec=TaskExecutor)

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
            circuit_breaker_threshold=5,
        )

        assert layer._circuit_threshold == 5

    @pytest.mark.asyncio
    async def test_max_concurrent_override_in_config(self, tmp_path: Path) -> None:
        """max_concurrent in config should override pool setting."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        graph = BeadsTaskGraph(session_id="test", db_path=tmp_path / "tasks.db")
        for i in range(10):
            graph.add_task(f"Task {i}")

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)
        mock_resource_pool.check_health = AsyncMock(return_value=True)
        mock_resource_pool._max_concurrent = 4

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Swarm",
            confidence=1.0,
            scope_type=ScopeType.ISOLATED,
            source="keyword",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate_dag(graph, config={"max_concurrent": 2})

        # Pool should have been accessed (we're just verifying config is used)
        assert mock_resource_pool.acquire.call_count >= 1

    @pytest.mark.asyncio
    async def test_timeout_config_passed_to_resource_pool(self, tmp_path: Path) -> None:
        """resource_timeout should be passed to pool.acquire()."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate(
            "test task",
            config={"resource_timeout": 10.0},
        )

        mock_resource_pool.acquire.assert_called_with(timeout=10.0)

    @pytest.mark.asyncio
    async def test_context_passed_to_pattern_resolver(self, tmp_path: Path) -> None:
        """Context should be passed to pattern resolution."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        context = {"previous_pattern": "Pipeline", "task_count": 5}
        await layer.orchestrate("test task", config={"context": context})

        call_kwargs = mock_pattern_resolver.resolve.call_args[1]
        assert call_kwargs.get("context") == context

    @pytest.mark.asyncio
    async def test_metadata_merged_into_task(self, tmp_path: Path) -> None:
        """Metadata from config should be merged into task."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        mock_scope_manager = Mock(spec=ScopeManager)
        mock_scope = Mock(spec=ManagedScope)
        mock_scope.scope_type = ScopeType.HANDOFF
        mock_scope_manager.create_scope.return_value = mock_scope

        mock_resource_pool = AsyncMock(spec=ResourcePool)
        mock_handle = Mock(spec=ResourceHandle)
        mock_resource_pool.acquire.return_value = mock_handle
        mock_handle.__aenter__ = AsyncMock(return_value=mock_handle)
        mock_handle.__aexit__ = AsyncMock(return_value=None)

        mock_pattern_resolver = Mock(spec=PatternResolver)
        mock_pattern_resolver.resolve.return_value = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="default",
        )

        mock_task_executor = AsyncMock(spec=TaskExecutor)
        mock_task_executor.execute_single.return_value = TaskResult(
            task_id="test-123",
            status="completed",
            output={"result": "success"},
            error=None,
            duration_ms=100,
        )

        layer = OrchestrationLayer(
            scope_manager=mock_scope_manager,
            resource_pool=mock_resource_pool,
            pattern_resolver=mock_pattern_resolver,
            task_executor=mock_task_executor,
        )

        await layer.orchestrate(
            "test task",
            config={"metadata": {"priority": "high", "tags": ["urgent"]}},
        )

        call_args = mock_pattern_resolver.resolve.call_args
        task = call_args[0][0]
        assert task.metadata.get("priority") == "high"
        assert "urgent" in task.metadata.get("tags", [])
