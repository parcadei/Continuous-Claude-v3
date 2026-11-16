"""
TaskExecutor - DAG execution engine with resource control and failure handling.

Coordinates task execution using:
- BeadsTaskGraph for dependency ordering
- ResourcePool for concurrency control
- PatternResolver for pattern selection (optional)

Usage:
    executor = TaskExecutor(
        graph=graph,
        pool=ResourcePool(max_concurrent_agents=4),
        fail_fast=True
    )
    result = await executor.execute()
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from scripts.agentica_patterns.beads_task_graph import (
    BeadsTask,
    BeadsTaskGraph,
    TaskStatus,
)
from scripts.agentica_patterns.resource_pool import (
    ResourceExhaustedError,
    ResourceHandle,
    ResourcePool,
)

# Import pattern classes for execution
from scripts.agentica_patterns.patterns import (
    Swarm,
    Hierarchical,
    Pipeline,
    Jury,
    GeneratorCritic,
    MapReduce,
    CircuitBreaker,
    Adversarial,
    Blackboard,
    ChainOfResponsibility,
    EventDriven,
)

# Import scope creator for Claude CLI tools
from scripts.agentica_patterns.claude_scope import create_claude_scope

if TYPE_CHECKING:
    from scripts.agentica_patterns.pattern_resolver import PatternResolver

# Pattern name -> class mapping
PATTERN_CLASSES: dict[str, type] = {
    "Swarm": Swarm,
    "Hierarchical": Hierarchical,
    "Pipeline": Pipeline,
    "Jury": Jury,
    "GeneratorCritic": GeneratorCritic,
    "Generator_Critic": GeneratorCritic,
    "MapReduce": MapReduce,
    "Map_Reduce": MapReduce,
    "CircuitBreaker": CircuitBreaker,
    "Circuit_Breaker": CircuitBreaker,
    "Adversarial": Adversarial,
    "Blackboard": Blackboard,
    "ChainOfResponsibility": ChainOfResponsibility,
    "Chain_Of_Responsibility": ChainOfResponsibility,
    "EventDriven": EventDriven,
    "Event_Driven": EventDriven,
}


# ============================================================================
# Enums
# ============================================================================


class ExecutionMode(Enum):
    """Execution modes for TaskExecutor."""
    BOUNDED = "bounded"      # Respects max_concurrent, default
    UNBOUNDED = "unbounded"  # No concurrency limit (testing only)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class TaskResult:
    """Result of a single task execution."""
    task_id: str
    status: str  # "completed", "failed", "skipped"
    output: Any
    error: str | None
    duration_ms: int
    pattern_used: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def succeeded(self) -> bool:
        """True if task completed successfully."""
        return self.status == "completed"


@dataclass
class ExecutionResult:
    """Result of DAG execution."""
    completed: list[TaskResult] = field(default_factory=list)
    failed: list[TaskResult] = field(default_factory=list)
    skipped: list[TaskResult] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    total_duration_ms: int = 0

    @property
    def success(self) -> bool:
        """True if all tasks completed without failure."""
        return len(self.failed) == 0 and len(self.pending) == 0

    @property
    def progress(self) -> float:
        """Completion percentage (0.0 to 1.0)."""
        total = len(self.completed) + len(self.failed) + len(self.skipped) + len(self.pending)
        if total == 0:
            return 1.0
        done = len(self.completed) + len(self.failed) + len(self.skipped)
        return done / total


# ============================================================================
# TaskExecutor
# ============================================================================


class TaskExecutor:
    """DAG execution engine with resource control and failure handling.

    Coordinates task execution using:
    - BeadsTaskGraph for dependency ordering
    - ResourcePool for concurrency control
    - PatternResolver for pattern selection (optional)

    Usage:
        executor = TaskExecutor(
            graph=graph,
            pool=ResourcePool(max_concurrent_agents=4),
            fail_fast=True
        )
        result = await executor.execute()
    """

    def __init__(
        self,
        graph: BeadsTaskGraph,
        pool: ResourcePool,
        resolver: PatternResolver | None = None,
        fail_fast: bool = True,
        task_timeout: float = 300.0,  # 5 minutes per task
        poll_interval: float = 0.01,   # Ready task check interval
    ):
        """Initialize TaskExecutor.

        Args:
            graph: BeadsTaskGraph to execute
            pool: ResourcePool for concurrency control
            resolver: Optional PatternResolver for pattern selection
            fail_fast: If True, stop on first failure
            task_timeout: Timeout per task in seconds
            poll_interval: Interval for checking ready tasks
        """
        self._graph = graph
        self._pool = pool
        self._resolver = resolver
        self._fail_fast = fail_fast
        self._task_timeout = task_timeout
        self._poll_interval = poll_interval

        # Task handler for custom execution
        self._task_handler: Callable[[BeadsTask], Awaitable[Any]] | None = None

        # Execution state
        self._completed: list[TaskResult] = []
        self._failed: list[TaskResult] = []
        self._skipped: list[TaskResult] = []
        self._in_progress: dict[str, asyncio.Task] = {}
        self._start_time: datetime | None = None

    def set_task_handler(
        self,
        handler: Callable[[BeadsTask], Awaitable[Any]]
    ) -> None:
        """Set custom task handler for task execution.

        Default handler is a no-op. Set this to wire in actual
        agent execution, pattern dispatch, etc.

        Args:
            handler: Async callable that takes BeadsTask, returns result
        """
        self._task_handler = handler

    def get_progress(self) -> float:
        """Get current execution progress (0.0 to 1.0)."""
        all_tasks = self._graph.get_all_tasks()
        total = len(all_tasks)

        if total == 0:
            return 1.0

        done = 0
        for task in all_tasks:
            status = task["status"]
            if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
                done += 1

        # Also count in-progress and accumulated results
        done += len(self._completed) + len(self._failed) + len(self._skipped)

        # Count unique done tasks from DB
        done_from_db = sum(
            1 for t in all_tasks
            if t["status"] in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value)
        )

        return min(1.0, done_from_db / total) if total > 0 else 1.0

    async def execute(self) -> ExecutionResult:
        """Execute all tasks in the DAG.

        Executes ready tasks concurrently (bounded by ResourcePool),
        respecting dependencies. Stops early if fail_fast=True and
        a task fails.

        Returns:
            ExecutionResult with completed/failed/pending tasks
        """
        self._start_time = datetime.now()
        self._completed = []
        self._failed = []
        self._skipped = []
        self._in_progress = {}

        try:
            await self._execute_loop()
        except Exception:
            # Unexpected error - still return partial results
            pass

        # Calculate total duration
        total_ms = int((datetime.now() - self._start_time).total_seconds() * 1000)

        # Get any remaining pending tasks
        pending_ids = self._get_pending_task_ids()

        return ExecutionResult(
            completed=self._completed,
            failed=self._failed,
            skipped=self._skipped,
            pending=pending_ids,
            total_duration_ms=total_ms,
        )

    async def _execute_loop(self) -> None:
        """Main execution loop."""
        while True:
            # 1. Check termination conditions
            if self._is_complete():
                break

            # 2. Check fail_fast
            if self._fail_fast and len(self._failed) > 0:
                # Skip remaining pending tasks
                await self._skip_remaining_tasks()
                break

            # 3. Get ready tasks (O(1) via blocked cache)
            ready_task_ids = self._graph.get_ready_tasks()

            # 4. Filter out already in-progress tasks
            ready_task_ids = [t for t in ready_task_ids if t not in self._in_progress]

            # 5. Filter out already completed/failed tasks
            completed_ids = {r.task_id for r in self._completed}
            failed_ids = {r.task_id for r in self._failed}
            ready_task_ids = [
                t for t in ready_task_ids
                if t not in completed_ids and t not in failed_ids
            ]

            if not ready_task_ids and not self._in_progress:
                # No ready tasks and nothing in progress - complete or stuck
                break

            # 6. Launch new tasks up to pool capacity
            for task_id in ready_task_ids:
                # Check pool health before attempting acquire
                if not await self._pool.check_health():
                    break  # Pool saturated, wait for completions

                try:
                    # Acquire resource with short timeout
                    handle = await self._pool.acquire(timeout=0.1)

                    # Get task from graph
                    task = self._graph.get_task(task_id)
                    if task is None:
                        await self._pool.release(handle)
                        continue

                    # Mark as in-progress in graph
                    self._graph.mark_in_progress(task_id)

                    # Launch task with resource handle
                    async_task = asyncio.create_task(
                        self._execute_with_resource(task, handle)
                    )
                    self._in_progress[task_id] = async_task

                except ResourceExhaustedError:
                    # Pool busy, try again next iteration
                    break

            # 7. Wait for any task to complete
            if self._in_progress:
                done, _ = await asyncio.wait(
                    self._in_progress.values(),
                    timeout=self._poll_interval,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Process completed tasks
                for async_task in done:
                    try:
                        result = async_task.result()
                        task_id = result.task_id

                        # Remove from in-progress
                        if task_id in self._in_progress:
                            del self._in_progress[task_id]

                        # Update graph and results
                        if result.succeeded:
                            self._graph.complete_task(task_id)
                            self._completed.append(result)
                        else:
                            self._graph.fail_task(task_id)
                            self._failed.append(result)

                    except Exception as e:
                        # Task raised exception unexpectedly
                        # Find and remove from in-progress
                        for tid, t in list(self._in_progress.items()):
                            if t is async_task:
                                del self._in_progress[tid]
                                self._failed.append(TaskResult(
                                    task_id=tid,
                                    status="failed",
                                    output=None,
                                    error=str(e),
                                    duration_ms=0,
                                ))
                                self._graph.fail_task(tid)
                                break
            else:
                # No tasks in progress, short sleep to avoid busy loop
                await asyncio.sleep(self._poll_interval)

    async def _execute_with_resource(
        self,
        task: BeadsTask,
        handle: ResourceHandle,
    ) -> TaskResult:
        """Execute task with automatic resource release."""
        start_time = datetime.now()

        try:
            async with handle:  # Auto-release on exit
                # Apply timeout
                result = await asyncio.wait_for(
                    self._execute_task_impl(task),
                    timeout=self._task_timeout,
                )

                end_time = datetime.now()
                return TaskResult(
                    task_id=task.id,
                    status="completed",
                    output=result,
                    error=None,
                    duration_ms=int((end_time - start_time).total_seconds() * 1000),
                    started_at=start_time,
                    completed_at=end_time,
                )

        except TimeoutError:
            return TaskResult(
                task_id=task.id,
                status="failed",
                output=None,
                error=f"Task timed out after {self._task_timeout}s",
                duration_ms=int(self._task_timeout * 1000),
                started_at=start_time,
            )

        except asyncio.CancelledError:
            return TaskResult(
                task_id=task.id,
                status="failed",
                output=None,
                error="Task was cancelled",
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                started_at=start_time,
            )

        except Exception as e:
            end_time = datetime.now()
            return TaskResult(
                task_id=task.id,
                status="failed",
                output=None,
                error=str(e),
                duration_ms=int((end_time - start_time).total_seconds() * 1000),
                started_at=start_time,
                completed_at=end_time,
            )

    async def _execute_task_impl(self, task: BeadsTask) -> Any:
        """Execute task using handler or pattern resolver."""
        # 1. If custom handler is set, use it
        if self._task_handler is not None:
            return await self._task_handler(task)

        # 2. If resolver is set, resolve pattern and execute via pattern class
        if self._resolver is not None:
            selection = self._resolver.resolve(task)
            pattern_name = selection.pattern

            # Get the pattern class
            pattern_class = PATTERN_CLASSES.get(pattern_name)
            if pattern_class is None:
                # Unknown pattern - fall back to returning selection info
                return {
                    "task_id": task.id,
                    "pattern": pattern_name,
                    "error": f"Unknown pattern: {pattern_name}",
                }

            # Instantiate and execute the pattern
            try:
                # Build pattern-specific config from task metadata
                metadata = getattr(task, 'metadata', {}) or {}

                # Create Universal Scope with Claude CLI tools (Read, Write, Bash, etc)
                import os
                project_dir = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
                scope = create_claude_scope(project_dir=project_dir)

                if pattern_name == "Swarm":
                    # Swarm needs perspectives - generate from task or use defaults
                    perspectives = metadata.get("perspectives", [
                        "You are an implementation expert. Focus on code correctness.",
                        "You are a testing expert. Focus on test coverage.",
                        "You are a documentation expert. Focus on clarity.",
                    ])
                    pattern = pattern_class(perspectives=perspectives, scope=scope)
                    result = await pattern.execute(task.description)

                elif pattern_name == "Hierarchical":
                    # Hierarchical needs coordinator + specialist premises
                    pattern = pattern_class(
                        coordinator_premise=metadata.get(
                            "coordinator_premise",
                            "You coordinate task execution. Delegate to specialists."
                        ),
                        specialist_premises=metadata.get("specialist_premises", [
                            "You implement code changes.",
                            "You write tests.",
                        ]),
                        scope=scope,
                    )
                    result = await pattern.execute(task.description)

                elif pattern_name in ("Pipeline", "Jury", "MapReduce"):
                    # These patterns need minimal config but still get scope
                    pattern = pattern_class(scope=scope) if 'scope' in pattern_class.__init__.__code__.co_varnames else pattern_class()
                    result = await pattern.execute(task.description)

                else:
                    # Generic execution for other patterns
                    try:
                        pattern = pattern_class(scope=scope)
                    except TypeError:
                        pattern = pattern_class()
                    if hasattr(pattern, 'execute'):
                        result = await pattern.execute(task.description)
                    else:
                        result = {"error": f"Pattern {pattern_name} has no execute method"}

                return {
                    "task_id": task.id,
                    "pattern": pattern_name,
                    "result": result,
                }

            except Exception as e:
                return {
                    "task_id": task.id,
                    "pattern": pattern_name,
                    "error": str(e),
                }

        # 3. Default: return task description as output (for testing)
        return {"task_id": task.id, "description": task.description}

    def _is_complete(self) -> bool:
        """Check if all tasks are done."""
        all_tasks = self._graph.get_all_tasks()
        if not all_tasks:
            return True

        for task in all_tasks:
            status = task["status"]
            if status not in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
                # Check if task is pending and blocked by a failed task
                if status == TaskStatus.PENDING.value:
                    deps = self._graph.get_dependencies(task["id"])
                    blockers = deps.get("blocks", [])

                    # Check if any blocker failed
                    blocked_by_failure = False
                    for blocker_id in blockers:
                        blocker = self._graph.get_task(blocker_id)
                        if blocker and blocker.status == TaskStatus.FAILED:
                            blocked_by_failure = True
                            break

                    if blocked_by_failure and not self._fail_fast:
                        # This task is blocked by failure but we're not fail_fast
                        # Mark it as skipped
                        continue

                return False

        return True

    async def _skip_remaining_tasks(self) -> None:
        """Skip all remaining pending tasks."""
        all_tasks = self._graph.get_all_tasks()
        completed_ids = {r.task_id for r in self._completed}
        failed_ids = {r.task_id for r in self._failed}
        in_progress_ids = set(self._in_progress.keys())

        for task in all_tasks:
            task_id = task["id"]
            if (
                task_id not in completed_ids
                and task_id not in failed_ids
                and task_id not in in_progress_ids
            ):
                if task["status"] in (TaskStatus.PENDING.value, TaskStatus.BLOCKED.value):
                    self._skipped.append(
                        TaskResult(
                            task_id=task_id,
                            status="skipped",
                            output=None,
                            error="Skipped due to fail_fast",
                            duration_ms=0,
                        )
                    )

    def _get_pending_task_ids(self) -> list[str]:
        """Get IDs of tasks that are still pending."""
        all_tasks = self._graph.get_all_tasks()
        completed_ids = {r.task_id for r in self._completed}
        failed_ids = {r.task_id for r in self._failed}
        skipped_ids = {r.task_id for r in self._skipped}

        pending = []
        for task in all_tasks:
            task_id = task["id"]
            if (
                task_id not in completed_ids
                and task_id not in failed_ids
                and task_id not in skipped_ids
            ):
                if task["status"] not in (
                    TaskStatus.COMPLETED.value,
                    TaskStatus.FAILED.value,
                ):
                    pending.append(task_id)

        return pending

    async def execute_single(
        self,
        task: BeadsTask,
        context: dict[str, Any] | None = None,
    ) -> TaskResult:
        """Execute a single task.

        Lower-level method for executing one task with optional context.
        Does not acquire resources - caller must manage pool.

        Args:
            task: Task to execute
            context: Optional execution context

        Returns:
            TaskResult with execution outcome
        """
        start_time = datetime.now()

        try:
            result = await asyncio.wait_for(
                self._execute_task_impl(task),
                timeout=self._task_timeout,
            )

            end_time = datetime.now()
            return TaskResult(
                task_id=task.id,
                status="completed",
                output=result,
                error=None,
                duration_ms=int((end_time - start_time).total_seconds() * 1000),
                started_at=start_time,
                completed_at=end_time,
            )

        except TimeoutError:
            return TaskResult(
                task_id=task.id,
                status="failed",
                output=None,
                error=f"Task timed out after {self._task_timeout}s",
                duration_ms=int(self._task_timeout * 1000),
                started_at=start_time,
            )

        except Exception as e:
            end_time = datetime.now()
            return TaskResult(
                task_id=task.id,
                status="failed",
                output=None,
                error=str(e),
                duration_ms=int((end_time - start_time).total_seconds() * 1000),
                started_at=start_time,
                completed_at=end_time,
            )

    async def resume(
        self,
        from_task_id: str | None = None,
    ) -> ExecutionResult:
        """Resume execution from a checkpoint.

        Continues DAG execution from the specified task or from
        the first pending task if no ID provided.

        Args:
            from_task_id: Optional task ID to resume from

        Returns:
            ExecutionResult with execution outcome
        """
        # Reset local state but preserve graph state
        self._start_time = datetime.now()
        self._completed = []
        self._failed = []
        self._skipped = []
        self._in_progress = {}

        # If from_task_id specified, ensure it's ready to execute
        if from_task_id is not None:
            task = self._graph.get_task(from_task_id)
            if task is None:
                raise ValueError(f"Task {from_task_id} not found")

            # If task is completed, start from next
            if task.status == TaskStatus.COMPLETED:
                # Just run execute which will pick up remaining tasks
                pass

        # Run the normal execution loop
        try:
            await self._execute_loop()
        except Exception:
            pass

        # Calculate total duration
        total_ms = int((datetime.now() - self._start_time).total_seconds() * 1000)

        # Get any remaining pending tasks
        pending_ids = self._get_pending_task_ids()

        return ExecutionResult(
            completed=self._completed,
            failed=self._failed,
            skipped=self._skipped,
            pending=pending_ids,
            total_duration_ms=total_ms,
        )
