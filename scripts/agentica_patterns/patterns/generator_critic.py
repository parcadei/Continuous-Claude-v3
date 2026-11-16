"""
GeneratorCritic Pattern for Agentica.

Iterative refinement loop with generator and critic agents.
"""

import os
from collections.abc import Callable
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

from .primitives import HandoffState

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


class GeneratorCritic:
    """
    GeneratorCritic pattern: Iterative refinement loop.

    Flow:
    1. Generator creates initial solution
    2. Critic evaluates and provides feedback
    3. Generator refines based on feedback
    4. Repeat until critic approves or max_rounds reached

    Example:
        gc = GeneratorCritic(
            generator_premise="You generate Python code.",
            critic_premise="You review Python code for correctness."
        )
        result = await gc.run("Create a function to parse JSON")
    """

    def __init__(
        self,
        generator_premise: str,
        critic_premise: str,
        max_rounds: int = 3,
        generator_scope: dict[str, Any] | None = None,
        critic_scope: dict[str, Any] | None = None,
        generator_model: str | None = None,
        critic_model: str | None = None,
        is_approved: Callable[[HandoffState], bool] | None = None,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize GeneratorCritic.

        Args:
            generator_premise: Premise for generator agent
            critic_premise: Premise for critic agent
            max_rounds: Maximum iteration rounds
            generator_scope: Tools for generator
            critic_scope: Tools for critic
            generator_model: Model for generator
            critic_model: Model for critic
            is_approved: Custom function to check if state is approved
            db: Optional coordination database for tracking agents
        """
        if max_rounds <= 0:
            raise ValueError("max_rounds must be positive")

        self.generator_premise = generator_premise
        self.critic_premise = critic_premise
        self.max_rounds = max_rounds
        self.generator_scope = generator_scope or {}
        self.critic_scope = critic_scope or {}
        self.generator_model = generator_model
        self.critic_model = critic_model
        self.db = db

        # Default approval check
        if is_approved:
            self.is_approved = is_approved
        else:
            self.is_approved = lambda state: "APPROVED" in state.next_instruction

        # Agents spawned lazily
        self.generator = None
        self.critic = None

        # Track GC ID for pattern-aware hooks
        self.gc_id: str | None = None

    async def _ensure_generator(self, iteration: int):
        """Lazy spawn generator with pattern env vars."""
        if self.generator is None:
            # Set pattern-aware environment variables
            os.environ["PATTERN_TYPE"] = "generator_critic"
            os.environ["PATTERN_ID"] = self.gc_id or ""
            os.environ["GC_ID"] = self.gc_id or ""
            os.environ["AGENT_ROLE"] = "generator"
            os.environ["GC_ITERATION"] = str(iteration)
            os.environ["GC_MAX_ROUNDS"] = str(self.max_rounds)

            spawn_kwargs = {"premise": self.generator_premise}
            if self.generator_scope:
                spawn_kwargs["scope"] = self.generator_scope
            if self.generator_model:
                spawn_kwargs["model"] = self.generator_model

            # Use tracked_spawn if db is set
            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.generator = await tracked_spawn(db=self.db, pattern="generator_critic", **spawn_kwargs)
            else:
                self.generator = await spawn(**spawn_kwargs)

    async def _ensure_critic(self, iteration: int):
        """Lazy spawn critic with pattern env vars."""
        if self.critic is None:
            # Set pattern-aware environment variables
            os.environ["PATTERN_TYPE"] = "generator_critic"
            os.environ["PATTERN_ID"] = self.gc_id or ""
            os.environ["GC_ID"] = self.gc_id or ""
            os.environ["AGENT_ROLE"] = "critic"
            os.environ["GC_ITERATION"] = str(iteration)
            os.environ["GC_MAX_ROUNDS"] = str(self.max_rounds)

            spawn_kwargs = {"premise": self.critic_premise}
            if self.critic_scope:
                spawn_kwargs["scope"] = self.critic_scope
            if self.critic_model:
                spawn_kwargs["model"] = self.critic_model

            # Use tracked_spawn if db is set
            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.critic = await tracked_spawn(db=self.db, pattern="generator_critic", **spawn_kwargs)
            else:
                self.critic = await spawn(**spawn_kwargs)

    async def run(self, task: str) -> HandoffState:
        """
        Run generator/critic loop.

        Args:
            task: Task for generator to complete

        Returns:
            Final HandoffState (approved or max rounds reached)
        """
        # Generate unique ID for this execution
        self.gc_id = str(uuid4())

        # Save original env vars for cleanup
        original_env = {
            "PATTERN_TYPE": os.environ.get("PATTERN_TYPE"),
            "PATTERN_ID": os.environ.get("PATTERN_ID"),
            "GC_ID": os.environ.get("GC_ID"),
            "AGENT_ROLE": os.environ.get("AGENT_ROLE"),
            "GC_ITERATION": os.environ.get("GC_ITERATION"),
            "GC_MAX_ROUNDS": os.environ.get("GC_MAX_ROUNDS"),
        }

        try:
            # Initialize state
            state = HandoffState(
                context=f"Task: {task}",
                next_instruction="Generate initial solution"
            )

            for iteration in range(1, self.max_rounds + 1):
                # Update iteration in env
                os.environ["GC_ITERATION"] = str(iteration)

                # Ensure generator spawned with current iteration
                await self._ensure_generator(iteration)

                # Generator produces/refines solution
                feedback = state.artifacts.get('feedback', '')
                if feedback:
                    feedback_text = f"Feedback from previous round: {feedback}"
                else:
                    feedback_text = "First attempt."
                prompt = f"""
                {state.context}

                Task: {task}

                {feedback_text}

                Generate your solution. Return HandoffState with artifacts.
                """

                state = await self.generator.call(HandoffState, prompt, state=state)

                # Ensure critic spawned with current iteration
                await self._ensure_critic(iteration)

                # Critic evaluates
                critique_prompt = f"""
                Review this solution:

                Task: {task}

                Solution artifacts: {state.artifacts}

                Provide feedback. If approved, set next_instruction to "APPROVED".
                Otherwise, provide constructive feedback in artifacts['feedback'].
                """

                state = await self.critic.call(HandoffState, critique_prompt, state=state)

                # Check if approved
                if self.is_approved(state):
                    break

            return state
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
