"""
Blackboard Pattern: Multiple specialists contribute to shared state.

A controller agent monitors the blackboard state and decides when
the solution is complete. Specialists read relevant keys from the
blackboard, process information, and write their contributions back.
"""

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

# Import spawn from agentica if available, otherwise use a stub for testing
try:
    from agentica import spawn
except ImportError:
    # Stub for testing - tests will mock this
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - use mocking in tests")

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


@dataclass
class Specialist:
    """
    A specialist agent that contributes to the blackboard.

    Attributes:
        premise: The premise/role for this specialist agent
        writes_to: List of blackboard keys this specialist writes to
        reads_from: List of blackboard keys this specialist reads from
    """
    premise: str
    writes_to: list[str] = field(default_factory=list)
    reads_from: list[str] = field(default_factory=list)


class BlackboardState:
    """
    Thread-safe blackboard state storage.

    Provides dict-like access to state values while tracking history
    of all changes for debugging and auditing. Includes async methods
    for thread-safe read-modify-write operations.

    WARNING: Separate get_item() + set_item() calls are NOT atomic!
    For read-modify-write operations, use update_item() instead:

        # WRONG - Race condition:
        val = await state.get_item("counter")
        await state.set_item("counter", val + 1)

        # RIGHT - Atomic:
        await state.update_item("counter", lambda x: (x or 0) + 1)

    The get/set pattern loses ~99% of concurrent increments due to
    race conditions at yield points. See test_blackboard_atomic_read_modify_write
    for a demonstration of this race condition.

    Example:
        state = BlackboardState()
        state["requirements"] = "User auth needed"
        state["architecture"] = "Microservices"
        print(state.history)  # Shows all changes

        # For atomic read-modify-write, use update_item:
        await state.update_item("counter", lambda x: (x or 0) + 1)
    """

    def __init__(self):
        """Initialize empty blackboard state."""
        self._data: dict[str, Any] = {}
        self.history: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    def __getitem__(self, key: str) -> Any:
        """Get a value from the blackboard."""
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a value on the blackboard and record in history."""
        self._data[key] = value
        self.history.append({
            "action": "set",
            "key": key,
            "value": value
        })

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the blackboard."""
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value with a default."""
        return self._data.get(key, default)

    async def get_item(self, key: str, default: Any = None) -> Any:
        """Get a value with lock protection for atomic operations."""
        async with self._lock:
            return self._data.get(key, default)

    async def set_item(self, key: str, value: Any) -> None:
        """Set a value with lock protection for atomic operations."""
        async with self._lock:
            self._data[key] = value
            self.history.append({
                "action": "set",
                "key": key,
                "value": value
            })

    async def update_item(self, key: str, updater) -> Any:
        """
        Atomically read, modify, and write a value.

        Args:
            key: The key to update
            updater: A callable that takes current value and returns new value

        Returns:
            The new value after update

        Example:
            # Atomic increment
            await state.update_item("counter", lambda x: (x or 0) + 1)
        """
        async with self._lock:
            current = self._data.get(key)
            new_value = updater(current)
            self._data[key] = new_value
            self.history.append({
                "action": "set",
                "key": key,
                "value": new_value
            })
            return new_value

    def keys(self):
        """Return all keys in the blackboard."""
        return self._data.keys()

    def items(self):
        """Return all items in the blackboard."""
        return self._data.items()

    def to_dict(self) -> dict[str, Any]:
        """Return a copy of the blackboard data."""
        return dict(self._data)


@dataclass
class BlackboardResult:
    """Result from Blackboard.solve()."""
    state: BlackboardState
    iterations: int
    completed: bool


class Blackboard:
    """
    Blackboard pattern: Multiple specialists contribute to shared state.

    A controller agent monitors the blackboard state and decides when
    the solution is complete. Specialists read relevant keys from the
    blackboard, process information, and write their contributions back.

    Flow:
    1. Initialize blackboard with query
    2. Each iteration:
       a. Run each specialist (they read/write to blackboard)
       b. Ask controller if solution is complete
    3. Return when controller approves or max_iterations reached

    Example:
        bb = Blackboard(
            specialists=[
                Specialist(
                    premise="You analyze requirements.",
                    writes_to=["requirements"]
                ),
                Specialist(
                    premise="You design architecture.",
                    writes_to=["architecture"],
                    reads_from=["requirements"]
                ),
                Specialist(
                    premise="You write implementation plan.",
                    writes_to=["plan"],
                    reads_from=["architecture"]
                ),
            ],
            controller_premise="You check if the design is complete.",
            max_iterations=5
        )
        result = await bb.solve("Build a user authentication system")
    """

    def __init__(
        self,
        specialists: list[Specialist],
        controller_premise: str,
        max_iterations: int = 5,
        controller_model: str | None = None,
        specialist_model: str | None = None,
        controller_scope: dict[str, Any] | None = None,
        specialist_scope: dict[str, Any] | None = None,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize Blackboard pattern.

        Args:
            specialists: List of Specialist definitions
            controller_premise: Premise for the controller agent
            max_iterations: Maximum iterations before stopping
            controller_model: Model for controller agent
            specialist_model: Model for specialist agents
            controller_scope: Tools for controller agent
            specialist_scope: Tools for specialist agents
            db: Optional coordination database for tracking agents

        Raises:
            ValueError: If specialists is empty
        """
        if not specialists:
            raise ValueError("specialists cannot be empty")

        self.specialists = specialists
        self.controller_premise = controller_premise
        self.max_iterations = max_iterations
        self.controller_model = controller_model
        self.specialist_model = specialist_model
        self.controller_scope = controller_scope or {}
        self.specialist_scope = specialist_scope or {}
        self.db = db

        # Agents spawned lazily
        self.controller_agent = None
        self.specialist_agents: dict[int, Any] = {}

        # Generate unique blackboard ID
        import uuid
        self.blackboard_id = str(uuid.uuid4())

    async def _ensure_controller(self):
        """Lazy spawn controller agent."""
        if self.controller_agent is None:
            spawn_kwargs = {"premise": self.controller_premise}
            if self.controller_scope:
                spawn_kwargs["scope"] = self.controller_scope
            if self.controller_model:
                spawn_kwargs["model"] = self.controller_model

            # Set environment variables for hooks
            spawn_kwargs["env"] = {
                "PATTERN_TYPE": "blackboard",
                "BLACKBOARD_ID": self.blackboard_id,
                "AGENT_ROLE": "controller"
            }

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.controller_agent = await tracked_spawn(
                    db=self.db, pattern="blackboard", **spawn_kwargs
                )
            else:
                self.controller_agent = await spawn(**spawn_kwargs)

    async def _ensure_specialist(self, index: int):
        """Lazy spawn specialist agent by index."""
        if index not in self.specialist_agents:
            specialist = self.specialists[index]
            spawn_kwargs = {"premise": specialist.premise}
            if self.specialist_scope:
                spawn_kwargs["scope"] = self.specialist_scope
            if self.specialist_model:
                spawn_kwargs["model"] = self.specialist_model

            # Set environment variables for hooks
            spawn_kwargs["env"] = {
                "PATTERN_TYPE": "blackboard",
                "BLACKBOARD_ID": self.blackboard_id,
                "AGENT_ROLE": "specialist",
                "BLACKBOARD_WRITES_TO": ",".join(specialist.writes_to),
                "BLACKBOARD_READS_FROM": ",".join(specialist.reads_from)
            }

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.specialist_agents[index] = await tracked_spawn(
                    db=self.db, pattern="blackboard", **spawn_kwargs
                )
            else:
                self.specialist_agents[index] = await spawn(**spawn_kwargs)

    async def _run_specialist(
        self, index: int, query: str, state: BlackboardState
    ) -> dict[str, Any]:
        """
        Run a single specialist and get their contribution.

        Returns:
            Dict of key-value pairs to write to blackboard
        """
        await self._ensure_specialist(index)
        specialist = self.specialists[index]
        agent = self.specialist_agents[index]

        # Build context from keys the specialist reads
        read_context = ""
        if specialist.reads_from:
            for key in specialist.reads_from:
                if key in state:
                    read_context += f"\n{key}: {state[key]}"

        prompt = f"""
        Task: {query}

        You are responsible for: {specialist.writes_to}
        {f"Based on: {read_context}" if read_context else ""}

        Current blackboard state: {state.to_dict()}

        Provide your contribution as a dict with keys: {specialist.writes_to}
        """

        result = await agent.call(dict, prompt)
        return result if isinstance(result, dict) else {}

    async def _check_completion(
        self, query: str, state: BlackboardState
    ) -> dict[str, Any]:
        """
        Ask controller if the solution is complete.

        Returns:
            Dict with 'complete' key (bool) and optional feedback
        """
        await self._ensure_controller()

        prompt = f"""
        Task: {query}

        Current blackboard state: {state.to_dict()}

        Is the solution complete and coherent?
        Return a dict with:
        - 'complete': True if done, False if more work needed
        - 'feedback': Optional guidance for next iteration
        """

        result = await self.controller_agent.call(dict, prompt)
        return result if isinstance(result, dict) else {"complete": False}

    async def solve(self, query: str) -> BlackboardResult:
        """
        Solve a problem using the blackboard pattern.

        Args:
            query: The problem/task to solve

        Returns:
            BlackboardResult with final state, iterations, and completion status
        """
        state = BlackboardState()
        state["query"] = query

        for iteration in range(1, self.max_iterations + 1):
            # Run each specialist
            for i, specialist in enumerate(self.specialists):
                contribution = await self._run_specialist(i, query, state)

                # Write specialist's contributions to blackboard
                for key in specialist.writes_to:
                    if key in contribution:
                        state[key] = contribution[key]

            # Check if controller approves
            completion = await self._check_completion(query, state)

            if completion.get("complete", False):
                return BlackboardResult(
                    state=state,
                    iterations=iteration,
                    completed=True
                )

        # Max iterations reached
        return BlackboardResult(
            state=state,
            iterations=self.max_iterations,
            completed=False
        )
