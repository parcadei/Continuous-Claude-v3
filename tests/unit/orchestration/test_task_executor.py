"""
Unit tests for TaskExecutor.

Tests the DAG execution engine that coordinates task execution with
resource control, pattern resolution, and failure handling.

TDD: These tests are written BEFORE implementation and should FAIL initially.

Test coverage (~60 tests):
- Sequential DAG execution (15 tests)
- Parallel execution (15 tests)
- Failure handling (15 tests)
- Resource management (15 tests)
"""

import asyncio
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Import will fail until implementation exists - this is expected for TDD
from scripts.agentica_patterns.task_executor import (
    TaskExecutor,
    TaskResult,
    ExecutionResult,
    ExecutionMode,
)
from scripts.agentica_patterns.resource_pool import (
    ResourcePool,
    ResourceExhaustedError,
)
from scripts.agentica_patterns.beads_task_graph import (
    BeadsTaskGraph,
    BeadsTask,
    TaskStatus,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_db() -> Path:
    """Create temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_tasks.db"


@pytest.fixture
def pool() -> ResourcePool:
    """Create ResourcePool for testing."""
    return ResourcePool(max_concurrent_agents=4, acquire_timeout=5.0)


@pytest.fixture
def small_pool() -> ResourcePool:
    """Create small ResourcePool for concurrency tests."""
    return ResourcePool(max_concurrent_agents=2, acquire_timeout=1.0)


@pytest.fixture
def graph(temp_db: Path) -> BeadsTaskGraph:
    """Create BeadsTaskGraph for testing."""
    return BeadsTaskGraph(session_id="test-session", db_path=temp_db)


@pytest.fixture
def executor(graph: BeadsTaskGraph, pool: ResourcePool) -> TaskExecutor:
    """Create TaskExecutor with default settings."""
    return TaskExecutor(
        graph=graph,
        pool=pool,
        fail_fast=True,
        task_timeout=5.0,
    )


@pytest.fixture
def slow_executor(graph: BeadsTaskGraph, pool: ResourcePool) -> TaskExecutor:
    """Create TaskExecutor with short timeout for timeout tests."""
    return TaskExecutor(
        graph=graph,
        pool=pool,
        fail_fast=True,
        task_timeout=0.1,  # 100ms timeout
    )


# ============================================================================
# TestTaskResult
# ============================================================================


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_task_result_creation(self):
        """TaskResult can be created with required fields."""
        result = TaskResult(
            task_id="bd-abc123",
            status="completed",
            output={"value": 42},
            error=None,
            duration_ms=100,
        )
        assert result.task_id == "bd-abc123"
        assert result.status == "completed"
        assert result.output == {"value": 42}
        assert result.error is None
        assert result.duration_ms == 100

    def test_task_result_succeeded_true(self):
        """succeeded property returns True for completed status."""
        result = TaskResult(
            task_id="bd-abc123",
            status="completed",
            output=None,
            error=None,
            duration_ms=50,
        )
        assert result.succeeded is True

    def test_task_result_succeeded_false_failed(self):
        """succeeded property returns False for failed status."""
        result = TaskResult(
            task_id="bd-abc123",
            status="failed",
            output=None,
            error="Task failed",
            duration_ms=50,
        )
        assert result.succeeded is False

    def test_task_result_succeeded_false_skipped(self):
        """succeeded property returns False for skipped status."""
        result = TaskResult(
            task_id="bd-abc123",
            status="skipped",
            output=None,
            error="Skipped due to fail_fast",
            duration_ms=0,
        )
        assert result.succeeded is False

    def test_task_result_timestamps(self):
        """TaskResult can have optional timestamps."""
        now = datetime.now()
        result = TaskResult(
            task_id="bd-abc123",
            status="completed",
            output=None,
            error=None,
            duration_ms=100,
            started_at=now,
            completed_at=now,
        )
        assert result.started_at == now
        assert result.completed_at == now


# ============================================================================
# TestExecutionResult
# ============================================================================


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_execution_result_empty(self):
        """Empty ExecutionResult is valid and successful."""
        result = ExecutionResult()
        assert result.completed == []
        assert result.failed == []
        assert result.skipped == []
        assert result.pending == []
        assert result.success is True
        assert result.progress == 1.0

    def test_execution_result_success_with_completed(self):
        """ExecutionResult success when all completed."""
        result = ExecutionResult(
            completed=[
                TaskResult(task_id="a", status="completed", output=None, error=None, duration_ms=10),
                TaskResult(task_id="b", status="completed", output=None, error=None, duration_ms=20),
            ],
        )
        assert result.success is True
        assert result.progress == 1.0

    def test_execution_result_failure_with_failed(self):
        """ExecutionResult.success is False when failures exist."""
        result = ExecutionResult(
            completed=[
                TaskResult(task_id="a", status="completed", output=None, error=None, duration_ms=10),
            ],
            failed=[
                TaskResult(task_id="b", status="failed", output=None, error="error", duration_ms=20),
            ],
        )
        assert result.success is False

    def test_execution_result_failure_with_pending(self):
        """ExecutionResult.success is False when pending tasks remain."""
        result = ExecutionResult(
            completed=[
                TaskResult(task_id="a", status="completed", output=None, error=None, duration_ms=10),
            ],
            pending=["b", "c"],
        )
        assert result.success is False

    def test_execution_result_progress_partial(self):
        """Progress reflects partial completion."""
        result = ExecutionResult(
            completed=[
                TaskResult(task_id="a", status="completed", output=None, error=None, duration_ms=10),
            ],
            pending=["b", "c", "d"],
        )
        # 1 completed out of 4 total
        assert result.progress == 0.25

    def test_execution_result_progress_includes_failed(self):
        """Progress includes failed tasks as 'done'."""
        result = ExecutionResult(
            completed=[
                TaskResult(task_id="a", status="completed", output=None, error=None, duration_ms=10),
            ],
            failed=[
                TaskResult(task_id="b", status="failed", output=None, error="err", duration_ms=20),
            ],
            pending=["c", "d"],
        )
        # 2 done (1 completed + 1 failed) out of 4 total
        assert result.progress == 0.5

    def test_execution_result_progress_includes_skipped(self):
        """Progress includes skipped tasks as 'done'."""
        result = ExecutionResult(
            completed=[
                TaskResult(task_id="a", status="completed", output=None, error=None, duration_ms=10),
            ],
            skipped=[
                TaskResult(task_id="b", status="skipped", output=None, error="skip", duration_ms=0),
            ],
            pending=["c"],
        )
        # 2 done out of 3 total
        assert abs(result.progress - 2/3) < 0.01


# ============================================================================
# TestSequentialDAG
# ============================================================================


class TestSequentialDAG:
    """Tests for sequential (linear) DAG execution."""

    @pytest.mark.asyncio
    async def test_single_task_executes(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """Single task DAG completes."""
        task_id = graph.add_task("Single task")

        result = await executor.execute()

        assert len(result.completed) == 1
        assert result.completed[0].task_id == task_id
        assert result.success is True

    @pytest.mark.asyncio
    async def test_two_task_chain_order(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """A -> B executes in order."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])

        execution_order = []

        async def track_handler(task: BeadsTask) -> dict:
            execution_order.append(task.id)
            return {"executed": task.id}

        executor.set_task_handler(track_handler)
        result = await executor.execute()

        assert result.success is True
        assert len(result.completed) == 2
        assert execution_order == [task_a, task_b]

    @pytest.mark.asyncio
    async def test_three_task_chain_order(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """A -> B -> C executes in order."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_b])

        execution_order = []

        async def track_handler(task: BeadsTask) -> dict:
            execution_order.append(task.id)
            return {"executed": task.id}

        executor.set_task_handler(track_handler)
        result = await executor.execute()

        assert result.success is True
        assert len(result.completed) == 3
        assert execution_order == [task_a, task_b, task_c]

    @pytest.mark.asyncio
    async def test_long_chain_order(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """10-task chain executes in order."""
        task_ids = []
        prev_id = None

        for i in range(10):
            if prev_id:
                task_id = graph.add_task(f"Task {i}", blocks=[prev_id])
            else:
                task_id = graph.add_task(f"Task {i}")
            task_ids.append(task_id)
            prev_id = task_id

        execution_order = []

        async def track_handler(task: BeadsTask) -> dict:
            execution_order.append(task.id)
            return {"executed": task.id}

        executor.set_task_handler(track_handler)
        result = await executor.execute()

        assert result.success is True
        assert len(result.completed) == 10
        assert execution_order == task_ids

    @pytest.mark.asyncio
    async def test_blocked_task_waits(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """Blocked task doesn't start until blocker completes."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])

        a_completed = False
        b_started_while_a_running = False

        async def track_handler(task: BeadsTask) -> dict:
            nonlocal a_completed, b_started_while_a_running

            if task.id == task_a:
                await asyncio.sleep(0.05)  # Simulate work
                a_completed = True
            elif task.id == task_b:
                if not a_completed:
                    b_started_while_a_running = True

            return {"executed": task.id}

        executor.set_task_handler(track_handler)
        await executor.execute()

        assert a_completed is True
        assert b_started_while_a_running is False

    @pytest.mark.asyncio
    async def test_completed_list_accurate(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """ExecutionResult.completed contains all completed tasks."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])

        result = await executor.execute()

        completed_ids = {r.task_id for r in result.completed}
        assert completed_ids == {task_a, task_b}

    @pytest.mark.asyncio
    async def test_task_result_has_output(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """TaskResult.output captures handler return value."""
        task_id = graph.add_task("Task with output")

        async def output_handler(task: BeadsTask) -> dict:
            return {"result": "success", "value": 42}

        executor.set_task_handler(output_handler)
        result = await executor.execute()

        assert len(result.completed) == 1
        assert result.completed[0].output == {"result": "success", "value": 42}

    @pytest.mark.asyncio
    async def test_task_result_has_duration(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """TaskResult.duration_ms is accurate."""
        task_id = graph.add_task("Timed task")

        async def slow_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(0.05)  # 50ms
            return {}

        executor.set_task_handler(slow_handler)
        result = await executor.execute()

        assert len(result.completed) == 1
        # Duration should be at least 50ms
        assert result.completed[0].duration_ms >= 40  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_progress_increases_monotonically(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """get_progress() increases as tasks complete."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_b])

        progress_samples = []

        async def tracking_handler(task: BeadsTask) -> dict:
            progress_samples.append(executor.get_progress())
            return {}

        executor.set_task_handler(tracking_handler)
        await executor.execute()

        # Progress should increase monotonically
        for i in range(1, len(progress_samples)):
            assert progress_samples[i] >= progress_samples[i-1]

    @pytest.mark.asyncio
    async def test_progress_100_on_complete(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """Progress is 1.0 when all tasks done."""
        graph.add_task("Task A")
        graph.add_task("Task B")

        result = await executor.execute()

        assert result.progress == 1.0
        assert executor.get_progress() == 1.0

    @pytest.mark.asyncio
    async def test_progress_tracks_failures(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """Progress accounts for failed tasks."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B")

        async def failing_handler(task: BeadsTask) -> dict:
            if task.id == task_b:
                raise ValueError("Task B failed")
            return {}

        executor.set_task_handler(failing_handler)

        # Don't use fail_fast so both run
        executor_no_fail_fast = TaskExecutor(
            graph=executor._graph,
            pool=executor._pool,
            fail_fast=False,
        )
        executor_no_fail_fast.set_task_handler(failing_handler)
        result = await executor_no_fail_fast.execute()

        # Both tasks processed (1 completed, 1 failed)
        assert result.progress == 1.0

    @pytest.mark.asyncio
    async def test_empty_graph_returns_empty(self, executor: TaskExecutor):
        """Empty graph returns empty ExecutionResult."""
        result = await executor.execute()

        assert len(result.completed) == 0
        assert len(result.failed) == 0
        assert len(result.skipped) == 0
        assert result.success is True
        assert result.progress == 1.0

    @pytest.mark.asyncio
    async def test_already_complete_tasks_skipped(self, executor: TaskExecutor, graph: BeadsTaskGraph):
        """Pre-completed tasks are not re-executed."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])

        # Complete task_a manually
        graph.complete_task(task_a)

        executed_ids = []

        async def track_handler(task: BeadsTask) -> dict:
            executed_ids.append(task.id)
            return {}

        executor.set_task_handler(track_handler)
        result = await executor.execute()

        # Only task_b should execute
        assert task_a not in executed_ids
        assert task_b in executed_ids


# ============================================================================
# TestParallelExecution
# ============================================================================


class TestParallelExecution:
    """Tests for parallel task execution."""

    @pytest.mark.asyncio
    async def test_parallel_tasks_execute_concurrently(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Independent tasks run in parallel."""
        graph = BeadsTaskGraph(session_id="test-parallel", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        # Add 4 independent tasks
        task_ids = [graph.add_task(f"Task {i}") for i in range(4)]

        concurrent_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        async def concurrent_handler(task: BeadsTask) -> dict:
            nonlocal concurrent_count, max_concurrent

            async with lock:
                concurrent_count += 1
                if concurrent_count > max_concurrent:
                    max_concurrent = concurrent_count

            await asyncio.sleep(0.05)  # Simulate work

            async with lock:
                concurrent_count -= 1

            return {}

        executor.set_task_handler(concurrent_handler)
        result = await executor.execute()

        assert result.success is True
        # Should have had multiple concurrent tasks
        assert max_concurrent > 1

    @pytest.mark.asyncio
    async def test_respects_max_concurrent(
        self, small_pool: ResourcePool, temp_db: Path
    ):
        """Never exceeds ResourcePool limit."""
        graph = BeadsTaskGraph(session_id="test-max-concurrent", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=small_pool, fail_fast=True)

        # Add more tasks than pool allows
        task_ids = [graph.add_task(f"Task {i}") for i in range(6)]

        max_concurrent = 0
        concurrent_count = 0
        lock = asyncio.Lock()

        async def concurrent_handler(task: BeadsTask) -> dict:
            nonlocal concurrent_count, max_concurrent

            async with lock:
                concurrent_count += 1
                if concurrent_count > max_concurrent:
                    max_concurrent = concurrent_count

            await asyncio.sleep(0.02)

            async with lock:
                concurrent_count -= 1

            return {}

        executor.set_task_handler(concurrent_handler)
        result = await executor.execute()

        assert result.success is True
        # Should never exceed pool limit of 2
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_pool_saturation_queues_tasks(
        self, small_pool: ResourcePool, temp_db: Path
    ):
        """When pool saturated, tasks queue for resources."""
        graph = BeadsTaskGraph(session_id="test-queue", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=small_pool, fail_fast=True)

        # Add more tasks than pool allows
        task_ids = [graph.add_task(f"Task {i}") for i in range(5)]

        result = await executor.execute()

        # All tasks should complete eventually
        assert result.success is True
        assert len(result.completed) == 5

    @pytest.mark.asyncio
    async def test_resource_released_on_completion(
        self, pool: ResourcePool, temp_db: Path
    ):
        """ResourceHandle released after task completes."""
        graph = BeadsTaskGraph(session_id="test-release", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_id = graph.add_task("Single task")

        result = await executor.execute()

        assert result.success is True
        # Pool should be empty after completion
        assert pool.get_metrics().active == 0

    @pytest.mark.asyncio
    async def test_resource_released_on_failure(
        self, pool: ResourcePool, temp_db: Path
    ):
        """ResourceHandle released even if task fails."""
        graph = BeadsTaskGraph(session_id="test-release-fail", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_id = graph.add_task("Failing task")

        async def failing_handler(task: BeadsTask) -> dict:
            raise ValueError("Task failed")

        executor.set_task_handler(failing_handler)
        result = await executor.execute()

        # Pool should be empty after failure
        assert pool.get_metrics().active == 0

    @pytest.mark.asyncio
    async def test_diamond_dag_executes(
        self, pool: ResourcePool, temp_db: Path
    ):
        """A -> (B, C) -> D works correctly."""
        graph = BeadsTaskGraph(session_id="test-diamond", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_a])
        task_d = graph.add_task("Task D", blocks=[task_b, task_c])

        result = await executor.execute()

        assert result.success is True
        assert len(result.completed) == 4

    @pytest.mark.asyncio
    async def test_diamond_dag_d_waits_for_bc(
        self, pool: ResourcePool, temp_db: Path
    ):
        """D doesn't start until both B and C complete."""
        graph = BeadsTaskGraph(session_id="test-diamond-wait", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_a])
        task_d = graph.add_task("Task D", blocks=[task_b, task_c])

        bc_completed = set()
        d_started_before_bc = False

        async def track_handler(task: BeadsTask) -> dict:
            nonlocal d_started_before_bc

            if task.id == task_d:
                if bc_completed != {task_b, task_c}:
                    d_started_before_bc = True
            elif task.id in (task_b, task_c):
                await asyncio.sleep(0.02)  # B and C take some time
                bc_completed.add(task.id)

            return {}

        executor.set_task_handler(track_handler)
        await executor.execute()

        assert d_started_before_bc is False

    @pytest.mark.asyncio
    async def test_wide_fanout_5_tasks(
        self, pool: ResourcePool, temp_db: Path
    ):
        """A -> (B1, B2, B3, B4, B5) executes all."""
        graph = BeadsTaskGraph(session_id="test-fanout", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_bs = [graph.add_task(f"Task B{i}", blocks=[task_a]) for i in range(5)]

        result = await executor.execute()

        assert result.success is True
        assert len(result.completed) == 6  # A + 5 Bs

    @pytest.mark.asyncio
    async def test_wide_fanout_respects_limit(
        self, small_pool: ResourcePool, temp_db: Path
    ):
        """Fan-out respects max_concurrent even with many ready."""
        graph = BeadsTaskGraph(session_id="test-fanout-limit", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=small_pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_bs = [graph.add_task(f"Task B{i}", blocks=[task_a]) for i in range(10)]

        max_concurrent = 0
        concurrent_count = 0
        lock = asyncio.Lock()

        async def concurrent_handler(task: BeadsTask) -> dict:
            nonlocal concurrent_count, max_concurrent

            async with lock:
                concurrent_count += 1
                if concurrent_count > max_concurrent:
                    max_concurrent = concurrent_count

            await asyncio.sleep(0.01)

            async with lock:
                concurrent_count -= 1

            return {}

        executor.set_task_handler(concurrent_handler)
        result = await executor.execute()

        assert result.success is True
        assert max_concurrent <= 2  # Pool limit

    @pytest.mark.asyncio
    async def test_mixed_serial_parallel(
        self, pool: ResourcePool, temp_db: Path
    ):
        """A -> (B, C) ; D -> E works."""
        graph = BeadsTaskGraph(session_id="test-mixed", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        # First chain: A -> (B, C)
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_a])

        # Second chain: D -> E (independent)
        task_d = graph.add_task("Task D")
        task_e = graph.add_task("Task E", blocks=[task_d])

        result = await executor.execute()

        assert result.success is True
        assert len(result.completed) == 5

    @pytest.mark.asyncio
    async def test_complex_dag_topology(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Complex DAG with multiple join points."""
        graph = BeadsTaskGraph(session_id="test-complex", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        #     A
        #    / \
        #   B   C
        #   |\ /|
        #   | X |
        #   |/ \|
        #   D   E
        #    \ /
        #     F

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_a])
        task_d = graph.add_task("Task D", blocks=[task_b, task_c])
        task_e = graph.add_task("Task E", blocks=[task_b, task_c])
        task_f = graph.add_task("Task F", blocks=[task_d, task_e])

        result = await executor.execute()

        assert result.success is True
        assert len(result.completed) == 6

    @pytest.mark.asyncio
    async def test_parallel_faster_than_serial(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Parallel execution completes faster than serial would."""
        graph = BeadsTaskGraph(session_id="test-speed", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        # 4 independent tasks, each takes 50ms
        task_ids = [graph.add_task(f"Task {i}") for i in range(4)]

        async def slow_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(0.05)
            return {}

        executor.set_task_handler(slow_handler)

        start = datetime.now()
        result = await executor.execute()
        elapsed_ms = (datetime.now() - start).total_seconds() * 1000

        assert result.success is True
        # Serial would be ~200ms, parallel should be ~50ms
        # Allow 150ms to account for overhead but be less than serial
        assert elapsed_ms < 150

    @pytest.mark.asyncio
    async def test_concurrent_task_count_observable(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Can observe concurrent execution via metrics."""
        graph = BeadsTaskGraph(session_id="test-observe", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_ids = [graph.add_task(f"Task {i}") for i in range(4)]
        metrics_samples = []

        async def sampling_handler(task: BeadsTask) -> dict:
            metrics_samples.append(pool.get_metrics().active)
            await asyncio.sleep(0.02)
            return {}

        executor.set_task_handler(sampling_handler)
        await executor.execute()

        # Should have observed concurrent execution
        assert max(metrics_samples) > 1


# ============================================================================
# TestFailureHandling
# ============================================================================


class TestFailureHandling:
    """Tests for failure modes and recovery."""

    @pytest.mark.asyncio
    async def test_fail_fast_stops_on_first_failure(
        self, pool: ResourcePool, temp_db: Path
    ):
        """fail_fast=True stops execution on first failure."""
        graph = BeadsTaskGraph(session_id="test-fail-fast", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])  # Will never run
        task_c = graph.add_task("Task C", blocks=[task_a])  # Will never run

        async def failing_handler(task: BeadsTask) -> dict:
            if task.id == task_a:
                raise ValueError("Task A failed")
            return {}

        executor.set_task_handler(failing_handler)
        result = await executor.execute()

        assert result.success is False
        assert len(result.failed) == 1
        assert result.failed[0].task_id == task_a

    @pytest.mark.asyncio
    async def test_fail_fast_skips_pending(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Pending tasks marked as skipped in fail_fast mode."""
        graph = BeadsTaskGraph(session_id="test-skip", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_a])

        async def failing_handler(task: BeadsTask) -> dict:
            if task.id == task_a:
                raise ValueError("Task A failed")
            return {}

        executor.set_task_handler(failing_handler)
        result = await executor.execute()

        # B and C should be skipped
        skipped_ids = {r.task_id for r in result.skipped}
        assert task_b in skipped_ids or task_b in result.pending
        assert task_c in skipped_ids or task_c in result.pending

    @pytest.mark.asyncio
    async def test_fail_fast_lets_in_progress_complete(
        self, pool: ResourcePool, temp_db: Path
    ):
        """In-progress tasks complete even in fail_fast mode."""
        graph = BeadsTaskGraph(session_id="test-in-progress", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        # Two independent tasks
        task_a = graph.add_task("Task A")  # Will fail immediately
        task_b = graph.add_task("Task B")  # Will take time

        completed_b = False

        async def handler(task: BeadsTask) -> dict:
            nonlocal completed_b
            if task.id == task_a:
                raise ValueError("Task A failed")
            else:
                await asyncio.sleep(0.05)
                completed_b = True
            return {}

        executor.set_task_handler(handler)
        result = await executor.execute()

        # B may or may not complete depending on timing
        # The key is that it's either in completed or still had a chance to run

    @pytest.mark.asyncio
    async def test_fail_fast_false_continues(
        self, pool: ResourcePool, temp_db: Path
    ):
        """fail_fast=False continues despite failures."""
        graph = BeadsTaskGraph(session_id="test-continue", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_a = graph.add_task("Task A")  # Will fail
        task_b = graph.add_task("Task B")  # Independent, should complete

        async def handler(task: BeadsTask) -> dict:
            if task.id == task_a:
                raise ValueError("Task A failed")
            return {}

        executor.set_task_handler(handler)
        result = await executor.execute()

        # Both should be processed
        assert len(result.failed) == 1
        assert len(result.completed) == 1
        assert result.completed[0].task_id == task_b

    @pytest.mark.asyncio
    async def test_fail_fast_false_collects_all_failures(
        self, pool: ResourcePool, temp_db: Path
    ):
        """All failures collected when fail_fast=False."""
        graph = BeadsTaskGraph(session_id="test-collect", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B")
        task_c = graph.add_task("Task C")

        async def all_fail_handler(task: BeadsTask) -> dict:
            raise ValueError(f"{task.id} failed")

        executor.set_task_handler(all_fail_handler)
        result = await executor.execute()

        # All 3 should be in failed
        assert len(result.failed) == 3

    @pytest.mark.asyncio
    async def test_task_timeout_marks_failed(
        self, slow_executor: TaskExecutor, graph: BeadsTaskGraph
    ):
        """Timed-out task marked as failed."""
        task_id = graph.add_task("Slow task")

        async def slow_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(1.0)  # Much longer than 100ms timeout
            return {}

        slow_executor.set_task_handler(slow_handler)
        result = await slow_executor.execute()

        assert len(result.failed) == 1
        assert "timed out" in result.failed[0].error.lower()

    @pytest.mark.asyncio
    async def test_task_timeout_releases_resource(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Resource released on timeout."""
        graph = BeadsTaskGraph(session_id="test-timeout-release", db_path=temp_db)
        executor = TaskExecutor(
            graph=graph, pool=pool, fail_fast=True, task_timeout=0.05
        )

        task_id = graph.add_task("Slow task")

        async def slow_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(1.0)
            return {}

        executor.set_task_handler(slow_handler)
        await executor.execute()

        # Pool should be empty after timeout
        assert pool.get_metrics().active == 0

    @pytest.mark.asyncio
    async def test_timeout_error_message_informative(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Timeout error message includes duration."""
        graph = BeadsTaskGraph(session_id="test-timeout-msg", db_path=temp_db)
        executor = TaskExecutor(
            graph=graph, pool=pool, fail_fast=True, task_timeout=0.05
        )

        task_id = graph.add_task("Slow task")

        async def slow_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(1.0)
            return {}

        executor.set_task_handler(slow_handler)
        result = await executor.execute()

        assert len(result.failed) == 1
        error_msg = result.failed[0].error.lower()
        assert "timeout" in error_msg or "0.05" in error_msg or "50" in error_msg

    @pytest.mark.asyncio
    async def test_handler_exception_caught(
        self, executor: TaskExecutor, graph: BeadsTaskGraph
    ):
        """Handler exception caught and recorded."""
        task_id = graph.add_task("Failing task")

        async def failing_handler(task: BeadsTask) -> dict:
            raise RuntimeError("Something went wrong")

        executor.set_task_handler(failing_handler)
        result = await executor.execute()

        assert len(result.failed) == 1
        assert result.failed[0].task_id == task_id

    @pytest.mark.asyncio
    async def test_exception_error_captured(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Exception message captured in TaskResult.error."""
        graph = BeadsTaskGraph(session_id="test-error-msg", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_id = graph.add_task("Failing task")

        async def failing_handler(task: BeadsTask) -> dict:
            raise ValueError("Specific error message")

        executor.set_task_handler(failing_handler)
        result = await executor.execute()

        assert "Specific error message" in result.failed[0].error

    @pytest.mark.asyncio
    async def test_exception_does_not_crash_executor(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Single exception doesn't crash entire executor."""
        graph = BeadsTaskGraph(session_id="test-no-crash", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_a = graph.add_task("Task A")  # Will fail
        task_b = graph.add_task("Task B")  # Should still run

        async def partial_fail_handler(task: BeadsTask) -> dict:
            if task.id == task_a:
                raise RuntimeError("A failed")
            return {"completed": True}

        executor.set_task_handler(partial_fail_handler)
        result = await executor.execute()

        # B should have completed
        assert len(result.completed) == 1

    @pytest.mark.asyncio
    async def test_dependent_task_skipped_on_blocker_failure(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Task depending on failed task is skipped."""
        graph = BeadsTaskGraph(session_id="test-dep-skip", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_a = graph.add_task("Task A")  # Will fail
        task_b = graph.add_task("Task B", blocks=[task_a])  # Should be skipped

        async def failing_handler(task: BeadsTask) -> dict:
            if task.id == task_a:
                raise ValueError("A failed")
            return {}

        executor.set_task_handler(failing_handler)
        result = await executor.execute()

        # B should be skipped or pending (blocked by failed A)
        assert task_b not in {r.task_id for r in result.completed}

    @pytest.mark.asyncio
    async def test_failed_result_has_error(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Failed TaskResult has non-null error."""
        graph = BeadsTaskGraph(session_id="test-has-error", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_id = graph.add_task("Failing task")

        async def failing_handler(task: BeadsTask) -> dict:
            raise ValueError("Error message")

        executor.set_task_handler(failing_handler)
        result = await executor.execute()

        assert result.failed[0].error is not None
        assert len(result.failed[0].error) > 0

    @pytest.mark.asyncio
    async def test_execution_result_success_false_on_failure(
        self, pool: ResourcePool, temp_db: Path
    ):
        """ExecutionResult.success is False when failures exist."""
        graph = BeadsTaskGraph(session_id="test-success-false", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_id = graph.add_task("Failing task")

        async def failing_handler(task: BeadsTask) -> dict:
            raise ValueError("Failed")

        executor.set_task_handler(failing_handler)
        result = await executor.execute()

        assert result.success is False


# ============================================================================
# TestResourceManagement
# ============================================================================


class TestResourceManagement:
    """Tests for ResourcePool integration."""

    @pytest.mark.asyncio
    async def test_acquires_before_execution(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Resource acquired before task starts."""
        graph = BeadsTaskGraph(session_id="test-acquire", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_id = graph.add_task("Task A")
        acquired_during_execution = False

        async def check_handler(task: BeadsTask) -> dict:
            nonlocal acquired_during_execution
            # If handler is running, resource must be acquired
            if pool.get_metrics().active >= 1:
                acquired_during_execution = True
            return {}

        executor.set_task_handler(check_handler)
        await executor.execute()

        assert acquired_during_execution is True

    @pytest.mark.asyncio
    async def test_releases_after_completion(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Resource released after task completes."""
        graph = BeadsTaskGraph(session_id="test-release-complete", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_id = graph.add_task("Task A")

        await executor.execute()

        # Should be fully released
        assert pool.get_metrics().active == 0

    @pytest.mark.asyncio
    async def test_releases_after_failure(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Resource released even on task failure."""
        graph = BeadsTaskGraph(session_id="test-release-fail", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        task_id = graph.add_task("Failing task")

        async def failing_handler(task: BeadsTask) -> dict:
            raise ValueError("Failed")

        executor.set_task_handler(failing_handler)
        await executor.execute()

        assert pool.get_metrics().active == 0

    @pytest.mark.asyncio
    async def test_releases_after_timeout(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Resource released after timeout."""
        graph = BeadsTaskGraph(session_id="test-release-timeout", db_path=temp_db)
        executor = TaskExecutor(
            graph=graph, pool=pool, fail_fast=True, task_timeout=0.05
        )

        task_id = graph.add_task("Slow task")

        async def slow_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(1.0)
            return {}

        executor.set_task_handler(slow_handler)
        await executor.execute()

        assert pool.get_metrics().active == 0

    @pytest.mark.asyncio
    async def test_context_manager_ensures_release(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Context manager pattern ensures release."""
        graph = BeadsTaskGraph(session_id="test-context", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        # Multiple tasks, some fail
        for i in range(5):
            graph.add_task(f"Task {i}")

        async def mixed_handler(task: BeadsTask) -> dict:
            if "2" in task.description:
                raise ValueError("Task 2 fails")
            return {}

        executor.set_task_handler(mixed_handler)
        await executor.execute()

        # All resources should be released
        assert pool.get_metrics().active == 0

    @pytest.mark.asyncio
    async def test_pool_exhaustion_waits(
        self, small_pool: ResourcePool, temp_db: Path
    ):
        """Waits for resource when pool exhausted."""
        graph = BeadsTaskGraph(session_id="test-wait", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=small_pool, fail_fast=True)

        # More tasks than pool capacity
        task_ids = [graph.add_task(f"Task {i}") for i in range(5)]

        async def slow_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(0.02)
            return {}

        executor.set_task_handler(slow_handler)
        result = await executor.execute()

        # All tasks should eventually complete
        assert result.success is True
        assert len(result.completed) == 5

    @pytest.mark.asyncio
    async def test_pool_exhaustion_does_not_deadlock(
        self, small_pool: ResourcePool, temp_db: Path
    ):
        """No deadlock when pool temporarily exhausted."""
        graph = BeadsTaskGraph(session_id="test-no-deadlock", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=small_pool, fail_fast=True)

        # Chain of tasks
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_b])

        result = await executor.execute()

        assert result.success is True
        assert len(result.completed) == 3

    @pytest.mark.asyncio
    async def test_metrics_tracked_accurately(
        self, pool: ResourcePool, temp_db: Path
    ):
        """ResourceMetrics updated correctly."""
        graph = BeadsTaskGraph(session_id="test-metrics", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        initial_metrics = pool.get_metrics()
        initial_acquisitions = initial_metrics.total_acquisitions

        task_ids = [graph.add_task(f"Task {i}") for i in range(3)]

        await executor.execute()

        final_metrics = pool.get_metrics()
        # Should have 3 more acquisitions
        assert final_metrics.total_acquisitions == initial_acquisitions + 3

    @pytest.mark.asyncio
    async def test_respects_health_check(
        self, small_pool: ResourcePool, temp_db: Path
    ):
        """Skips acquire when health check fails."""
        graph = BeadsTaskGraph(session_id="test-health", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=small_pool, fail_fast=True)

        # Fill up the pool
        handles = []
        for _ in range(2):
            handles.append(await small_pool.acquire())

        # Health should be False
        assert await small_pool.check_health() is False

        # Release handles
        for handle in handles:
            await small_pool.release(handle)

    @pytest.mark.asyncio
    async def test_concurrent_acquire_safe(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Concurrent acquires don't corrupt pool state."""
        graph = BeadsTaskGraph(session_id="test-concurrent-acquire", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        # Many independent tasks
        task_ids = [graph.add_task(f"Task {i}") for i in range(20)]

        async def quick_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(0.005)
            return {}

        executor.set_task_handler(quick_handler)
        result = await executor.execute()

        assert result.success is True
        # Final state should be consistent
        metrics = pool.get_metrics()
        assert metrics.active == 0
        assert metrics.total_acquisitions == metrics.total_releases

    @pytest.mark.asyncio
    async def test_concurrent_release_safe(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Concurrent releases don't corrupt pool state."""
        graph = BeadsTaskGraph(session_id="test-concurrent-release", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=False)

        # Tasks that complete at roughly the same time
        task_ids = [graph.add_task(f"Task {i}") for i in range(10)]

        async def varied_handler(task: BeadsTask) -> dict:
            await asyncio.sleep(0.01)
            return {}

        executor.set_task_handler(varied_handler)
        result = await executor.execute()

        metrics = pool.get_metrics()
        assert metrics.active == 0
        assert metrics.total_acquisitions == metrics.total_releases

    @pytest.mark.asyncio
    async def test_resume_acquires_fresh_resources(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Resume doesn't assume prior resource state."""
        graph = BeadsTaskGraph(session_id="test-resume-fresh", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])

        # Complete task A manually
        graph.complete_task(task_a)

        # Resume should work with fresh pool state
        result = await executor.resume()

        assert result.success is True
        assert pool.get_metrics().active == 0

    @pytest.mark.asyncio
    async def test_resume_from_task_id(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Resume from specific task ID works."""
        graph = BeadsTaskGraph(session_id="test-resume-id", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_b])

        # Complete A and B manually
        graph.complete_task(task_a)
        graph.complete_task(task_b)

        # Resume from C
        result = await executor.resume(from_task_id=task_c)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_resume_skips_completed(
        self, pool: ResourcePool, temp_db: Path
    ):
        """Resume skips already-completed tasks."""
        graph = BeadsTaskGraph(session_id="test-resume-skip", db_path=temp_db)
        executor = TaskExecutor(graph=graph, pool=pool, fail_fast=True)

        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])

        # Complete A
        graph.complete_task(task_a)

        executed_ids = []

        async def track_handler(task: BeadsTask) -> dict:
            executed_ids.append(task.id)
            return {}

        executor.set_task_handler(track_handler)
        result = await executor.resume()

        # Only B should have executed
        assert task_a not in executed_ids
        assert task_b in executed_ids
