"""
Hierarchical Pattern

Coordinator decomposes tasks for specialist agents.

This pattern sets the following environment variables for pattern-aware hooks:
- PATTERN_TYPE=hierarchical
- PATTERN_ID=<unique_hierarchy_id>
- HIERARCHY_ID=<unique_hierarchy_id>
- AGENT_ROLE=coordinator|specialist
- COORDINATOR_ID=<coordinator_id> (for specialists)
- HIERARCHY_LEVEL=<n> (0 = coordinator, 1+ = specialist)

See: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 28)
"""

import asyncio
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

# Import spawn from agentica if available, otherwise use a stub for testing
try:
    from agentica import spawn
except ImportError:
    # Stub for testing - tests will mock this
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - use mocking in tests")

from .primitives import (
    AggregateMode,
    Aggregator,
)

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


class Hierarchical:
    """
    Hierarchical pattern: Coordinator decomposes tasks for specialist agents.

    Flow:
    1. Coordinator decomposes task into subtasks
    2. Specialists execute subtasks (in parallel when independent)
    3. Results are aggregated
    4. Coordinator synthesizes final answer

    Example:
        hierarchical = Hierarchical(
            coordinator_premise="You break tasks into subtasks.",
            specialist_premises={
                "researcher": "You research topics.",
                "analyst": "You analyze data."
            }
        )
        result = await hierarchical.execute("Research and analyze topic X")
    """

    def __init__(
        self,
        coordinator_premise: str,
        specialist_premises: dict[str, str],
        coordinator_scope: dict[str, Any] | None = None,
        specialist_scope: dict[str, Any] | None = None,
        coordinator_model: str | None = None,
        specialist_model: str | None = None,
        aggregation_mode: AggregateMode = AggregateMode.CONCAT,
        aggregation_separator: str = "\n\n",
        aggregator: Aggregator | None = None,
        fail_fast: bool = False,
        return_type: type = str,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize Hierarchical coordinator.

        Args:
            coordinator_premise: Premise for coordinator agent
            specialist_premises: Dict mapping specialist name → premise
            coordinator_scope: Tools for coordinator
            specialist_scope: Tools for specialists
            coordinator_model: Model for coordinator
            specialist_model: Model for specialists
            aggregation_mode: How to aggregate specialist results
            aggregation_separator: Separator for aggregation
            aggregator: Custom Aggregator instance (overrides mode/separator)
            fail_fast: Stop on first specialist failure
            return_type: Expected return type for final result
            db: Optional coordination database for tracking agents
        """
        self.coordinator_premise = coordinator_premise
        self.specialist_premises = specialist_premises
        self.coordinator_scope = coordinator_scope or {}
        self.specialist_scope = specialist_scope or {}
        self.coordinator_model = coordinator_model
        self.specialist_model = specialist_model
        self.fail_fast = fail_fast
        self.return_type = return_type
        self.db = db

        # Generate unique hierarchy ID for this execution
        self.hierarchy_id = uuid4().hex[:12]
        self.coordinator_id: str | None = None

        # Coordinator and specialists will be spawned on demand
        self.coordinator = None
        self.specialists: dict[str, Any] = {}

        # Locks for thread-safe lazy initialization
        self._coordinator_lock = asyncio.Lock()
        self._specialist_locks: dict[str, asyncio.Lock] = {}

        # Setup aggregator
        if aggregator:
            self.aggregator = aggregator
        else:
            self.aggregator = Aggregator(
                mode=aggregation_mode,
                separator=aggregation_separator
            )

    @contextmanager
    def _coordinator_env_context(self):
        """Context manager to set coordinator environment variables.

        Sets:
            PATTERN_TYPE=hierarchical
            PATTERN_ID=<hierarchy_id>
            HIERARCHY_ID=<hierarchy_id>
            AGENT_ROLE=coordinator
            HIERARCHY_LEVEL=0

        These env vars are read by pattern-aware hooks to route to hierarchical handlers.
        """
        # Save original values
        original_env = {
            'PATTERN_TYPE': os.environ.get('PATTERN_TYPE'),
            'PATTERN_ID': os.environ.get('PATTERN_ID'),
            'HIERARCHY_ID': os.environ.get('HIERARCHY_ID'),
            'AGENT_ROLE': os.environ.get('AGENT_ROLE'),
            'HIERARCHY_LEVEL': os.environ.get('HIERARCHY_LEVEL'),
        }

        try:
            # Set pattern env vars for coordinator
            os.environ['PATTERN_TYPE'] = 'hierarchical'
            os.environ['PATTERN_ID'] = self.hierarchy_id
            os.environ['HIERARCHY_ID'] = self.hierarchy_id
            os.environ['AGENT_ROLE'] = 'coordinator'
            os.environ['HIERARCHY_LEVEL'] = '0'

            yield
        finally:
            # Restore original values
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @contextmanager
    def _specialist_env_context(self, specialist_name: str):
        """Context manager to set specialist environment variables.

        Sets:
            PATTERN_TYPE=hierarchical
            PATTERN_ID=<hierarchy_id>
            HIERARCHY_ID=<hierarchy_id>
            AGENT_ROLE=specialist
            COORDINATOR_ID=<coordinator_id>
            HIERARCHY_LEVEL=1

        These env vars are read by pattern-aware hooks to route to hierarchical handlers.
        """
        # Save original values
        original_env = {
            'PATTERN_TYPE': os.environ.get('PATTERN_TYPE'),
            'PATTERN_ID': os.environ.get('PATTERN_ID'),
            'HIERARCHY_ID': os.environ.get('HIERARCHY_ID'),
            'AGENT_ROLE': os.environ.get('AGENT_ROLE'),
            'COORDINATOR_ID': os.environ.get('COORDINATOR_ID'),
            'HIERARCHY_LEVEL': os.environ.get('HIERARCHY_LEVEL'),
        }

        try:
            # Set pattern env vars for specialist
            os.environ['PATTERN_TYPE'] = 'hierarchical'
            os.environ['PATTERN_ID'] = self.hierarchy_id
            os.environ['HIERARCHY_ID'] = self.hierarchy_id
            os.environ['AGENT_ROLE'] = 'specialist'
            os.environ['COORDINATOR_ID'] = self.coordinator_id or ''
            os.environ['HIERARCHY_LEVEL'] = '1'

            yield
        finally:
            # Restore original values
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    async def _ensure_coordinator(self):
        """Lazy spawn coordinator with lock protection."""
        async with self._coordinator_lock:
            if self.coordinator is None:
                spawn_kwargs = {"premise": self.coordinator_premise}
                if self.coordinator_scope:
                    spawn_kwargs["scope"] = self.coordinator_scope
                if self.coordinator_model:
                    spawn_kwargs["model"] = self.coordinator_model

                # Use tracked_spawn if db is set
                with self._coordinator_env_context():
                    if self.db:
                        from scripts.agentica_patterns.tracked_agent import tracked_spawn
                        self.coordinator = await tracked_spawn(
                            db=self.db, pattern="hierarchical", **spawn_kwargs
                        )
                    else:
                        self.coordinator = await spawn(**spawn_kwargs)

                # Store coordinator ID for specialists to reference
                if hasattr(self.coordinator, 'agent_id'):
                    self.coordinator_id = self.coordinator.agent_id
                else:
                    self.coordinator_id = 'coordinator'

    async def _ensure_specialist(self, name: str):
        """Lazy spawn specialist by name with lock protection."""
        # Ensure coordinator exists first so we have coordinator_id
        # This must be outside the specialist lock to avoid deadlock
        await self._ensure_coordinator()

        # Get or create lock for this specialist name
        if name not in self._specialist_locks:
            self._specialist_locks[name] = asyncio.Lock()

        async with self._specialist_locks[name]:
            if name not in self.specialists:
                if name not in self.specialist_premises:
                    raise ValueError(f"Unknown specialist: {name}")

                premise = self.specialist_premises[name]
                spawn_kwargs = {"premise": premise}
                if self.specialist_scope:
                    spawn_kwargs["scope"] = self.specialist_scope
                if self.specialist_model:
                    spawn_kwargs["model"] = self.specialist_model

                # Use tracked_spawn if db is set
                with self._specialist_env_context(name):
                    if self.db:
                        from scripts.agentica_patterns.tracked_agent import tracked_spawn
                        self.specialists[name] = await tracked_spawn(
                            db=self.db, pattern="hierarchical", **spawn_kwargs
                        )
                    else:
                        self.specialists[name] = await spawn(**spawn_kwargs)

    async def _decompose_task(self, task: str) -> list[dict[str, str]]:
        """
        Coordinator decomposes task into subtasks.

        Returns:
            List of dicts with keys: specialist, task
        """
        await self._ensure_coordinator()

        prompt = f"""
        Decompose this task into subtasks for specialists.

        Task: {task}

        Available specialists: {', '.join(self.specialist_premises.keys())}

        Return a list of dicts with keys: specialist, task
        Example: [{{"specialist": "researcher", "task": "Find papers"}}, ...]

        If the task is simple enough to answer directly, return an empty list.
        """

        subtasks = await self.coordinator.call(list, prompt)
        return subtasks

    async def _execute_subtasks(self, subtasks: list[dict[str, str]]) -> list[Any]:
        """
        Execute subtasks in parallel.

        Returns:
            List of results from specialists
        """
        from .primitives import gather_fail_fast

        async def execute_subtask(subtask: dict[str, str]):
            specialist_name = subtask["specialist"]
            task = subtask["task"]

            await self._ensure_specialist(specialist_name)
            specialist = self.specialists[specialist_name]
            return await specialist.call(str, task)

        coros = [execute_subtask(st) for st in subtasks]

        if self.fail_fast:
            try:
                results = await gather_fail_fast(coros, fail_fast=True)
            except ExceptionGroup as eg:
                raise eg.exceptions[0] from eg
        else:
            raw = await gather_fail_fast(coros, fail_fast=False)
            results = [r if not isinstance(r, Exception) else None for r in raw]

        return list(results)

    def _aggregate_results(self, results: list[Any]) -> Any:
        """Aggregate specialist results."""
        # Filter None values (failed specialists in non-fail-fast mode)
        filtered_results = [r for r in results if r is not None]
        if not filtered_results:
            return ""
        return self.aggregator.aggregate(filtered_results)

    async def _synthesize(self, task: str, aggregated_results: Any) -> Any:
        """
        Coordinator synthesizes final answer from aggregated results.

        Returns:
            Final synthesized result
        """
        await self._ensure_coordinator()

        prompt = f"""
        Synthesize a final answer based on specialist results.

        Original task: {task}

        Specialist results:
        {aggregated_results}

        Provide a comprehensive final answer.
        """

        return await self.coordinator.call(self.return_type, prompt)

    async def execute(self, task: str) -> Any:
        """
        Execute hierarchical pattern on a task.

        Args:
            task: Task to decompose and execute

        Returns:
            Synthesized final result
        """
        # 1. Decompose
        subtasks = await self._decompose_task(task)

        # 2. If no subtasks (simple task), coordinator answers directly
        if not subtasks:
            await self._ensure_coordinator()
            return await self.coordinator.call(self.return_type, task)

        # 3. Execute specialists
        results = await self._execute_subtasks(subtasks)

        # 4. Aggregate
        aggregated = self._aggregate_results(results)

        # 5. Synthesize
        final_result = await self._synthesize(task, aggregated)

        return final_result
