"""Dependency-Aware Parallel Implementation Swarm.

Executes tasks in parallel while respecting dependencies.
Uses CoordinationDB for tracking and resume capability.

Example:
    db = CoordinationDB()
    swarm = DependencySwarm(db=db)

    swarm.add_task("models", "Implement data models", file_path="src/models.py")
    swarm.add_task("api", "Implement API", file_path="src/api.py", depends_on=["models"])
    swarm.add_task("tests", "Write tests", depends_on=["api"])

    results = await swarm.execute()
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from scripts.agentica_patterns.tracked_agent import tracked_spawn

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


@dataclass
class TaskNode:
    """A task in the dependency graph."""
    id: str
    name: str
    premise: str
    file_path: str | None = None
    depends_on: list[str] = field(default_factory=list)
    skills: list[str] | None = None
    rules: list[str] | None = None
    bundle: str | None = None
    status: str = "pending"
    result: Any = None
    error: str | None = None


class TaskGraph:
    """Build and validate a dependency graph.

    Usage:
        graph = TaskGraph(db)
        a_id = graph.add_task("models", "Implement data models")
        b_id = graph.add_task("api", "Implement API", depends_on=[a_id])

        graph.validate()  # Raises ValueError if cycles or invalid refs
        ready = graph.get_ready_tasks()
        # Returns tasks with all dependencies completed
    """

    def __init__(self, db: "CoordinationDB"):
        self.db = db
        self.nodes: dict[str, TaskNode] = {}

    def add_task(
        self,
        name: str,
        premise: str,
        file_path: str | None = None,
        depends_on: list[str] | None = None,
        skills: list[str] | None = None,
        rules: list[str] | None = None,
        bundle: str | None = None,
    ) -> str:
        """Add task to graph. Returns task_id."""
        from uuid import uuid4
        task_id = uuid4().hex[:8]
        node = TaskNode(
            id=task_id,
            name=name,
            premise=premise,
            file_path=file_path,
            depends_on=depends_on or [],
            skills=skills,
            rules=rules,
            bundle=bundle,
        )
        self.nodes[task_id] = node
        return task_id

    def validate(self) -> None:
        """Validate the graph for cycles and invalid references.

        Uses Kahn's algorithm for cycle detection.

        Raises:
            ValueError: If cycles are detected or dependencies reference unknown tasks.
        """
        self._check_unknown_dependencies()
        self._detect_cycles()

    def _check_unknown_dependencies(self) -> None:
        """Check for references to non-existent task IDs.

        Raises:
            ValueError: If any dependency references an unknown task.
        """
        for task_id, node in self.nodes.items():
            for dep_id in node.depends_on:
                if dep_id not in self.nodes:
                    raise ValueError(
                        f"Unknown dependency: Task '{node.name}' ({task_id}) "
                        f"depends on non-existent task ID '{dep_id}'"
                    )

    def _detect_cycles(self) -> None:
        """Detect cycles using Kahn's algorithm.

        Raises:
            ValueError: If a cycle is detected in the dependency graph.
        """
        # Count in-degrees (number of dependencies for each task)
        in_degree: dict[str, int] = {}
        for task_id, node in self.nodes.items():
            in_degree[task_id] = len(node.depends_on)

        # Queue of tasks with no dependencies (in-degree 0)
        queue: deque[str] = deque(
            task_id for task_id, degree in in_degree.items() if degree == 0
        )

        # Process tasks in topological order
        processed_count = 0
        while queue:
            current = queue.popleft()
            processed_count += 1

            # Find tasks that depend on current and reduce their in-degree
            for task_id, node in self.nodes.items():
                if current in node.depends_on:
                    in_degree[task_id] -= 1
                    if in_degree[task_id] == 0:
                        queue.append(task_id)

        # If we couldn't process all tasks, there's a cycle
        if processed_count != len(self.nodes):
            cycle_tasks = [
                self.nodes[tid].name
                for tid, degree in in_degree.items()
                if degree > 0
            ]
            raise ValueError(
                f"Cycle detected in task dependencies. "
                f"Tasks involved: {', '.join(cycle_tasks)}"
            )

    def get_ready_tasks(self) -> list[str]:
        """Get pending tasks with all dependencies completed."""
        ready = []
        for task_id, node in self.nodes.items():
            if node.status != "pending":
                continue

            # Check if all dependencies are completed (with safe lookup)
            all_deps_completed = all(
                self.nodes.get(dep_id, TaskNode(id="", name="", premise="")).status == "completed"
                for dep_id in node.depends_on
            )

            if all_deps_completed:
                ready.append(task_id)

        return ready


class DependencySwarm:
    """Execute tasks in parallel while respecting dependencies."""

    def __init__(
        self,
        db: "CoordinationDB",
        model: str = "anthropic:claude-sonnet-4",
        scope: dict[str, Any] | None = None,
        mcp: str | None = None,
        fail_fast: bool = True,
        max_parallel: int | None = None,
        skills: list[str] | None = None,
        rules: list[str] | None = None,
        bundle: str | None = None,
        use_claude_scope: bool = False,
    ):
        """Initialize DependencySwarm.

        Args:
            db: CoordinationDB for tracking agents and tasks
            model: Model to use for all agents
            scope: Tools/functions available to all agents
            mcp: MCP config path for all agents
            fail_fast: If True, stop on first error. If False, continue with partial results
            max_parallel: Maximum number of tasks to execute in parallel (None = unlimited)
            skills: Default skills to inject into all tasks
            rules: Default rules to inject into all tasks
            bundle: Default bundle to use for all tasks (implementation, research)
            use_claude_scope: If True and no scope provided, create claude_scope with
                              read_file, write_file, bash, etc. functions
        """
        self.db = db
        self.model = model
        # Create claude_scope if requested and no scope provided
        if scope is None and use_claude_scope:
            from scripts.agentica_patterns.claude_scope import create_claude_scope
            self.scope = create_claude_scope()
        else:
            self.scope = scope or {}
        self.mcp = mcp
        self.fail_fast = fail_fast
        self.max_parallel = max_parallel
        self.default_skills = skills
        self.default_rules = rules
        self.default_bundle = bundle
        self.graph = TaskGraph(db)

    def add_task(
        self,
        name: str,
        premise: str,
        file_path: str | None = None,
        depends_on: list[str] | None = None,
        skills: list[str] | None = None,
        rules: list[str] | None = None,
        bundle: str | None = None,
    ) -> str:
        """Add a task to the graph. Returns task_id.

        Args:
            name: Task name (used as key in results dict)
            premise: Agent premise/instructions for this task
            file_path: Optional file path to implement
            depends_on: List of task IDs that must complete before this task
            skills: Skills to inject (overrides swarm defaults)
            rules: Rules to inject (overrides swarm defaults)
            bundle: Bundle to use (overrides swarm defaults)

        Returns:
            Task ID (8-character UUID)
        """
        return self.graph.add_task(
            name, premise, file_path, depends_on,
            skills, rules, bundle
        )

    def _build_dependency_context(self, task_id: str) -> str:
        """Build context from completed dependencies.

        Args:
            task_id: Task ID to build context for

        Returns:
            String containing dependency results to prepend to premise
        """
        node = self.graph.nodes[task_id]
        premise = node.premise

        # First, inject skills/rules/bundle
        premise = self._inject_skills_for_task(task_id, premise)

        # Then add dependency context if needed
        if not node.depends_on:
            return premise

        # Collect results from completed dependencies
        dep_contexts = []
        for dep_id in node.depends_on:
            dep_node = self.graph.nodes.get(dep_id)
            if dep_node and dep_node.status == "completed":
                dep_contexts.append(
                    f"[Dependency '{dep_node.name}' completed with result: {dep_node.result}]"
                )

        if not dep_contexts:
            return premise

        # Prepend dependency context to premise (which already has skills injected)
        context_header = "\n".join(dep_contexts)
        return f"{context_header}\n\n{premise}"

    def _inject_skills_for_task(self, task_id: str, premise: str) -> str:
        """Inject skills/rules/bundle into task premise.

        Args:
            task_id: Task ID
            premise: Original premise

        Returns:
            Premise with skills/rules injected
        """
        from scripts.agentica_patterns.skill_injection import inject_skills

        node = self.graph.nodes[task_id]

        # Use task-specific skills/rules/bundle, or fall back to swarm defaults
        skills = node.skills if node.skills is not None else self.default_skills
        rules = node.rules if node.rules is not None else self.default_rules
        bundle = node.bundle if node.bundle is not None else self.default_bundle

        return inject_skills(
            premise,
            skills=skills,
            rules=rules,
            bundle=bundle
        )

    async def execute(self) -> dict[str, Any]:
        """Execute the task graph.

        Returns:
            Dictionary mapping task name -> result for completed tasks

        Raises:
            ValueError: If graph validation fails (cycles, invalid refs)
        """
        # Validate graph before execution
        self.graph.validate()

        results = {}

        while True:
            # Get tasks ready to execute
            ready = self.graph.get_ready_tasks()

            if not ready:
                # No more tasks ready - either done or stuck on unmet deps
                break

            # Execute ready tasks in parallel
            await self._execute_phase(ready)

        # Collect results
        for task_id, node in self.graph.nodes.items():
            if node.status == "completed":
                results[node.name] = node.result

        return results

    async def _execute_phase(self, task_ids: list[str]) -> None:
        """Execute all tasks in a phase in parallel.

        Args:
            task_ids: List of task IDs to execute
        """
        # Apply max_parallel limit if set
        if self.max_parallel:
            # Execute in batches
            for i in range(0, len(task_ids), self.max_parallel):
                batch = task_ids[i:i + self.max_parallel]
                await self._execute_batch(batch)
        else:
            # Execute all in parallel
            await self._execute_batch(task_ids)

    async def _execute_batch(self, task_ids: list[str]) -> None:
        """Execute a batch of tasks in parallel.

        Args:
            task_ids: List of task IDs to execute
        """
        if self.fail_fast:
            # Use gather with default behavior - raises on first error
            await asyncio.gather(*[self._execute_task(tid) for tid in task_ids])
        else:
            # Use gather with return_exceptions to continue on errors
            results = await asyncio.gather(
                *[self._execute_task(tid) for tid in task_ids],
                return_exceptions=True
            )
            # Process exceptions
            for task_id, result in zip(task_ids, results):
                if isinstance(result, Exception):
                    # Mark as failed
                    self.graph.nodes[task_id].status = "failed"
                    self.graph.nodes[task_id].error = str(result)

    async def _execute_task(self, task_id: str) -> Any:
        """Execute a single task with a tracked agent.

        Args:
            task_id: Task ID to execute

        Returns:
            Task result

        Raises:
            Exception: If task execution fails and fail_fast is True
        """
        node = self.graph.nodes[task_id]
        agent = None

        try:
            # Build premise with dependency context
            premise_with_context = self._build_dependency_context(task_id)

            # Spawn agent for this task
            agent = await tracked_spawn(
                db=self.db,
                premise=premise_with_context,
                model=self.model,
                scope=self.scope,
                mcp=self.mcp,
                pattern="dependency_swarm",
            )

            # Execute the task
            result = await agent.call(str, premise_with_context)

            # Mark as completed
            node.status = "completed"
            node.result = result

            return result

        except Exception as e:
            # Mark as failed
            node.status = "failed"
            node.error = str(e)
            raise

        finally:
            # Always close the agent
            if agent is not None:
                await agent.close()
