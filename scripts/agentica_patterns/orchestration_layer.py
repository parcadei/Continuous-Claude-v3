"""
OrchestrationLayer - Week 4 Integration Layer

Wires together all Week 1-3 components:
- ScopeManager (Week 1): Scope isolation and enforcement
- ResourcePool (Week 1): Concurrency control and resource management
- PatternResolver (Week 2): Pattern selection and routing
- TaskExecutor (Week 3): DAG execution with failure handling

Provides:
- orchestrate(): Single task orchestration
- orchestrate_dag(): DAG-based execution
- orchestrate_batch(): Batch task execution
- resume_dag(): Resume from checkpoint

Usage:
    layer = OrchestrationLayer.create_default(
        session_id="my-session",
        db_path=Path("./tasks.db"),
        max_concurrent_agents=4,
    )

    result = await layer.orchestrate("Research authentication options")
    print(result.aggregated_output)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TYPE_CHECKING

from scripts.agentica_patterns.beads_task_graph import (
    BeadsTaskGraph,
    BeadsTask,
    TaskStatus,
    generate_task_id,
)
from scripts.agentica_patterns.resource_pool import (
    ResourcePool,
    ResourceHandle,
    ResourceExhaustedError,
)
from scripts.agentica_patterns.scope_manager import (
    ScopeManager,
    ManagedScope,
    ScopeViolationError,
)
from scripts.agentica_patterns.pattern_resolver import (
    PatternResolver,
    PatternSelection,
)
from scripts.agentica_patterns.task_executor import (
    TaskExecutor,
    TaskResult,
    ExecutionResult,
)
from scripts.agentica_patterns.patterns.primitives import (
    Aggregator,
    AggregateMode,
    HandoffState,
)
from scripts.validate_composition import ScopeType
from scripts.validate_resources import (
    get_system_resources,
    validate_resources,
    SystemResources,
    ResourceRequirements,
)
from scripts.resource_profiler import ResourceProfiler


# ============================================================================
# Enums and Error Classes
# ============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerState:
    """State for circuit breaker pattern."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None


class OrchestrationError(Exception):
    """Base error for orchestration failures."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause
        self.task_id: str | None = None
        self.pattern: str | None = None


class ResourceOrchestrationError(OrchestrationError):
    """Error related to resource exhaustion."""
    pass


class ScopeViolationOrchestrationError(OrchestrationError):
    """Error when scope rules are violated."""
    pass


# ============================================================================
# Result Types
# ============================================================================


@dataclass
class OrchestrationResult:
    """Result of orchestration operation."""
    success: bool
    session_id: str
    task_results: list[TaskResult] = field(default_factory=list)
    aggregated_output: Any = None
    errors: list[str] = field(default_factory=list)
    total_duration_ms: int = 0
    pattern_used: str | None = None
    final_handoff: dict[str, Any] | HandoffState | None = None


# ============================================================================
# OrchestrationLayer
# ============================================================================


class OrchestrationLayer:
    """
    Integration layer that wires together all Week 1-3 components.

    Provides unified interface for:
    - Single task orchestration with automatic pattern selection
    - DAG-based execution with dependency resolution
    - Batch task execution with aggregation
    - Resume from checkpoint for long-running workflows

    Thread-safe and supports concurrent orchestration sessions.
    """

    def __init__(
        self,
        scope_manager: ScopeManager,
        resource_pool: ResourcePool,
        pattern_resolver: PatternResolver,
        task_executor: TaskExecutor,
        aggregation_mode: AggregateMode = AggregateMode.MERGE,
        circuit_breaker_threshold: int = 5,
        enable_erotetics: bool = False,
        session_id: str = "default",
        profiler: ResourceProfiler | None = None,
    ):
        """Initialize OrchestrationLayer with required components.

        Args:
            scope_manager: ScopeManager for scope enforcement
            resource_pool: ResourcePool for concurrency control
            pattern_resolver: PatternResolver for pattern selection
            task_executor: TaskExecutor for task execution
            aggregation_mode: Mode for aggregating results
            circuit_breaker_threshold: Failures before circuit opens
            enable_erotetics: Enable erotetic question routing
            session_id: Session identifier
            profiler: Optional ResourceProfiler for memory tracking
        """
        self._scope_manager = scope_manager
        self._resource_pool = resource_pool
        self._pattern_resolver = pattern_resolver
        self._task_executor = task_executor
        self._aggregation_mode = aggregation_mode
        self._circuit_threshold = circuit_breaker_threshold
        self._enable_erotetics = enable_erotetics
        self._session_id = session_id

        # Resource profiler for adaptive memory estimation
        self._profiler = profiler or ResourceProfiler()

        # Circuit breaker state
        self._circuit_state = CircuitBreakerState()

        # Progress tracking
        self._total_tasks = 0
        self._completed_tasks = 0

        # Active memory polling tasks
        self._polling_tasks: dict[str, asyncio.Task[None]] = {}

        # Aggregator for result combination
        self._aggregator = Aggregator(
            mode=aggregation_mode,
            deduplicate=True,
        )

    @classmethod
    def create_default(
        cls,
        session_id: str = "default",
        db_path: Path | None = None,
        max_concurrent_agents: int = 4,
        aggregation_mode: AggregateMode = AggregateMode.MERGE,
        circuit_breaker_threshold: int = 5,
        enable_erotetics: bool = False,
    ) -> "OrchestrationLayer":
        """Factory method to create OrchestrationLayer with default components.

        Args:
            session_id: Session identifier
            db_path: Path for task graph database
            max_concurrent_agents: Max concurrent agent slots
            aggregation_mode: Mode for aggregating results
            circuit_breaker_threshold: Failures before circuit opens
            enable_erotetics: Enable erotetic question routing

        Returns:
            Configured OrchestrationLayer instance
        """
        # Create components
        scope_manager = ScopeManager(session_id=session_id)
        resource_pool = ResourcePool(
            max_concurrent_agents=max_concurrent_agents,
            acquire_timeout=30.0,
        )

        # Create task graph for internal use
        graph = BeadsTaskGraph(
            session_id=session_id,
            db_path=db_path,
        )

        pattern_resolver = PatternResolver()

        task_executor = TaskExecutor(
            graph=graph,
            pool=resource_pool,
            resolver=pattern_resolver,
        )

        return cls(
            scope_manager=scope_manager,
            resource_pool=resource_pool,
            pattern_resolver=pattern_resolver,
            task_executor=task_executor,
            aggregation_mode=aggregation_mode,
            circuit_breaker_threshold=circuit_breaker_threshold,
            enable_erotetics=enable_erotetics,
            session_id=session_id,
        )

    # ========================================================================
    # Core Orchestration Methods
    # ========================================================================

    async def orchestrate(
        self,
        task_description: str,
        config: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Orchestrate a single task.

        Args:
            task_description: Natural language task description
            config: Optional configuration overrides

        Returns:
            OrchestrationResult with execution outcome

        Raises:
            ScopeViolationOrchestrationError: If scope rules violated
            OrchestrationError: On unexpected errors
        """
        config = config or {}
        start_time = datetime.now(timezone.utc)

        # Check circuit breaker
        if self._circuit_state.state == CircuitState.OPEN:
            return OrchestrationResult(
                success=False,
                session_id=self._session_id,
                task_results=[TaskResult(
                    task_id="circuit-breaker",
                    status="failed",
                    output=None,
                    error="Circuit breaker is OPEN - requests are being rejected",
                    duration_ms=0,
                )],
                errors=["Circuit breaker is OPEN"],
            )

        # Validate resources before proceeding
        model = config.get("model", "sonnet")
        can_proceed, resource_error = self._validate_resources_for_task(model)
        if not can_proceed:
            return OrchestrationResult(
                success=False,
                session_id=self._session_id,
                task_results=[TaskResult(
                    task_id="resource-validation",
                    status="failed",
                    output=None,
                    error=resource_error or "Insufficient resources",
                    duration_ms=0,
                )],
                errors=[resource_error or "Insufficient resources"],
            )

        try:
            # 1. Create scope
            scope_override = config.get("scope_override")
            scope = self._scope_manager.create_scope(
                mode=scope_override or ScopeType.HANDOFF,
            )

            # 2. Create task with metadata
            metadata = config.get("metadata", {})
            if config.get("pattern_hint"):
                metadata["pattern_hint"] = config["pattern_hint"]

            task = BeadsTask(
                id=generate_task_id(),
                description=task_description,
                status=TaskStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                metadata=metadata,
            )

            # 3. Check for strict scope validation
            if config.get("strict_scope_check"):
                pattern_hint = metadata.get("pattern_hint")
                if pattern_hint and scope_override:
                    self._validate_pattern_scope(pattern_hint, scope_override)

            # 4. Resolve pattern
            context = config.get("context", {})
            selection = self._pattern_resolver.resolve(task, context=context)

            # 5. Acquire resource
            timeout = config.get("resource_timeout", 30.0)
            handle = await self._resource_pool.acquire(timeout=timeout)

            try:
                async with handle:
                    # 6. Execute task
                    task_timeout = config.get("task_timeout", 300.0)
                    result = await asyncio.wait_for(
                        self._task_executor.execute_single(task),
                        timeout=task_timeout,
                    )

            except asyncio.TimeoutError:
                result = TaskResult(
                    task_id=task.id,
                    status="failed",
                    output=None,
                    error="Task timed out",
                    duration_ms=int(task_timeout * 1000),
                )

            # Update circuit breaker
            if result.status == "completed":
                self._circuit_state.failure_count = 0
                self._circuit_state.last_success_time = datetime.now(timezone.utc)
            else:
                self._circuit_state.failure_count += 1
                self._circuit_state.last_failure_time = datetime.now(timezone.utc)

                if self._circuit_state.failure_count >= self._circuit_threshold:
                    self._circuit_state.state = CircuitState.OPEN

            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Build result
            errors = []
            if result.error:
                errors.append(result.error)

            return OrchestrationResult(
                success=result.status == "completed",
                session_id=self._session_id,
                task_results=[result],
                aggregated_output=result.output,
                errors=errors,
                total_duration_ms=duration_ms,
                pattern_used=selection.pattern,
            )

        except ScopeViolationError as e:
            raise ScopeViolationOrchestrationError(str(e), cause=e)

        except ResourceExhaustedError as e:
            return OrchestrationResult(
                success=False,
                session_id=self._session_id,
                errors=[str(e)],
            )

        except Exception as e:
            raise OrchestrationError(str(e), cause=e)

    async def orchestrate_dag(
        self,
        graph: BeadsTaskGraph,
        config: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Execute a DAG of tasks.

        Args:
            graph: BeadsTaskGraph with tasks and dependencies
            config: Optional configuration overrides

        Returns:
            OrchestrationResult with execution outcome
        """
        config = config or {}
        start_time = datetime.now(timezone.utc)
        fail_fast = config.get("fail_fast", True)

        all_tasks = graph.get_all_tasks()
        self._total_tasks = len(all_tasks)
        self._completed_tasks = 0

        if self._total_tasks == 0:
            return OrchestrationResult(
                success=True,
                session_id=self._session_id,
                task_results=[],
                total_duration_ms=0,
            )

        # Create scope
        scope = self._scope_manager.create_scope(
            mode=config.get("scope_override", ScopeType.HANDOFF),
        )

        # Create executor for this graph
        executor = TaskExecutor(
            graph=graph,
            pool=self._resource_pool,
            resolver=self._pattern_resolver,
            fail_fast=fail_fast,
        )

        # Set task handler
        async def task_handler(task: BeadsTask) -> Any:
            selection = self._pattern_resolver.resolve(task)
            return {
                "task_id": task.id,
                "pattern": selection.pattern,
                "result": f"Executed {task.description}",
            }

        executor.set_task_handler(task_handler)

        try:
            exec_result = await executor.execute()

            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Aggregate outputs
            completed_outputs = [r.output for r in exec_result.completed if r.output]
            aggregated = None
            if completed_outputs:
                try:
                    aggregated = self._aggregator.aggregate(completed_outputs)
                except Exception:
                    aggregated = completed_outputs

            # Build handoff state
            final_handoff = None
            if config.get("initial_handoff"):
                final_handoff = config["initial_handoff"]
                if isinstance(final_handoff, dict):
                    final_handoff["completed_tasks"] = len(exec_result.completed)

            return OrchestrationResult(
                success=exec_result.success,
                session_id=self._session_id,
                task_results=exec_result.completed + exec_result.failed + exec_result.skipped,
                aggregated_output=aggregated,
                errors=[r.error for r in exec_result.failed if r.error],
                total_duration_ms=duration_ms,
                final_handoff=final_handoff,
            )

        except Exception as e:
            # Cleanup on failure
            await self._resource_pool.force_release_all()
            raise OrchestrationError(str(e), cause=e)

    async def orchestrate_batch(
        self,
        task_descriptions: list[str],
        config: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Execute a batch of independent tasks.

        Args:
            task_descriptions: List of task descriptions
            config: Optional configuration overrides

        Returns:
            OrchestrationResult with aggregated output
        """
        config = config or {}
        start_time = datetime.now(timezone.utc)

        results: list[TaskResult] = []
        outputs: list[Any] = []

        for desc in task_descriptions:
            result = await self.orchestrate(desc, config)
            results.extend(result.task_results)
            if result.aggregated_output:
                outputs.append(result.aggregated_output)

        # Aggregate all outputs
        aggregated = None
        if outputs:
            try:
                aggregated = self._aggregator.aggregate(outputs)
            except Exception:
                aggregated = outputs

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return OrchestrationResult(
            success=all(r.status == "completed" for r in results),
            session_id=self._session_id,
            task_results=results,
            aggregated_output=aggregated,
            errors=[r.error for r in results if r.error],
            total_duration_ms=duration_ms,
        )

    async def resume_dag(
        self,
        graph: BeadsTaskGraph,
        from_task_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Resume DAG execution from a checkpoint.

        Args:
            graph: BeadsTaskGraph with partially completed tasks
            from_task_id: Optional task ID to resume from
            config: Optional configuration overrides

        Returns:
            OrchestrationResult with remaining task execution
        """
        config = config or {}
        start_time = datetime.now(timezone.utc)

        # Create executor
        executor = TaskExecutor(
            graph=graph,
            pool=self._resource_pool,
            resolver=self._pattern_resolver,
            fail_fast=config.get("fail_fast", True),
        )

        # Set handler
        async def task_handler(task: BeadsTask) -> Any:
            selection = self._pattern_resolver.resolve(task)
            return {
                "task_id": task.id,
                "pattern": selection.pattern,
                "result": f"Resumed {task.description}",
            }

        executor.set_task_handler(task_handler)

        # Resume execution
        exec_result = await executor.resume(from_task_id=from_task_id)

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return OrchestrationResult(
            success=exec_result.success,
            session_id=self._session_id,
            task_results=exec_result.completed + exec_result.failed,
            aggregated_output=[r.output for r in exec_result.completed],
            errors=[r.error for r in exec_result.failed if r.error],
            total_duration_ms=duration_ms,
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def get_progress(self) -> float:
        """Get current execution progress (0.0 to 1.0)."""
        if self._total_tasks == 0:
            return 1.0
        return self._completed_tasks / self._total_tasks

    def _validate_pattern_scope(self, pattern: str, scope: ScopeType) -> None:
        """Validate pattern is compatible with scope.

        Raises:
            ScopeViolationError: If pattern incompatible with scope
        """
        from scripts.validate_composition import PATTERNS

        pattern_info = PATTERNS.get(pattern)
        if pattern_info:
            valid_scopes = pattern_info.get("scopes", [])
            if scope not in valid_scopes:
                valid_str = ", ".join(s.value for s in valid_scopes)
                raise ScopeViolationError(
                    scope_type=scope,
                    operation="pattern_execution",
                    key=f"{pattern} requires [{valid_str}], got [{scope.value}]",
                )

    async def _execute_task(self, task: BeadsTask) -> dict[str, Any]:
        """Execute a single task (internal helper).

        This method can be mocked for testing.
        """
        selection = self._pattern_resolver.resolve(task)
        result = await self._task_executor.execute_single(task)
        return result.output or {"task_id": task.id, "pattern": selection.pattern}

    # ========================================================================
    # Resource Profiling Methods
    # ========================================================================

    def _validate_resources_for_task(
        self,
        model: str = "sonnet",
    ) -> tuple[bool, str | None]:
        """Validate that sufficient resources are available for task execution.

        Args:
            model: Model name for memory estimation

        Returns:
            Tuple of (can_proceed, error_message)
        """
        try:
            resources = get_system_resources()
            required_mb = self._profiler.get_estimate(model)

            if required_mb > resources.available_memory_mb:
                return (
                    False,
                    f"Insufficient memory: need {required_mb}MB, "
                    f"have {resources.available_memory_mb}MB",
                )

            return (True, None)
        except Exception as e:
            # Log but don't block on validation errors
            return (True, None)

    async def _poll_memory(
        self,
        task_id: str,
        model: str,
        interval_seconds: float = 5.0,
    ) -> None:
        """Poll memory usage during task execution.

        Args:
            task_id: Task identifier for recording
            model: Model name for categorization
            interval_seconds: Polling interval in seconds
        """
        try:
            while True:
                mem_mb = self._get_current_memory_mb()
                self._profiler.record(task_id, model, mem_mb)
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            # Expected when task completes
            pass

    def _get_current_memory_mb(self) -> int:
        """Get current process memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return int(process.memory_info().rss / (1024 * 1024))
        except Exception:
            return 0

    def _calculate_max_concurrent(self, model: str = "sonnet") -> int:
        """Calculate maximum concurrent agents based on available resources.

        Args:
            model: Model name for memory estimation

        Returns:
            Maximum number of concurrent agents
        """
        try:
            resources = get_system_resources()
            per_agent_mb = self._profiler.get_estimate(model)

            if per_agent_mb <= 0:
                return 1

            max_agents = resources.available_memory_mb // per_agent_mb
            return max(1, max_agents)
        except Exception:
            return 1

    async def _monitored_execute(
        self,
        task: BeadsTask,
        model: str = "sonnet",
    ) -> TaskResult:
        """Execute a task with memory monitoring.

        Args:
            task: Task to execute
            model: Model name for profiling

        Returns:
            TaskResult from execution
        """
        # Start memory polling
        poll_task = asyncio.create_task(
            self._poll_memory(task.id, model)
        )
        self._polling_tasks[task.id] = poll_task

        try:
            result = await self._task_executor.execute_single(task)
            return result
        finally:
            # Stop polling
            poll_task.cancel()
            try:
                await poll_task
            except asyncio.CancelledError:
                pass
            self._polling_tasks.pop(task.id, None)
