"""
Adversarial Pattern for Agentica.

Agents take opposing positions to stress-test ideas through structured debate.
"""

import os
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

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


class Adversarial:
    """
    Adversarial pattern: Agents take opposing positions to stress-test ideas.

    Flow:
    1. Advocate presents argument in favor
    2. Adversary critiques and attacks
    3. Iterate for max_rounds
    4. Optional judge decides which position is stronger

    Example:
        adv = Adversarial(
            advocate_premise="You argue in favor of this architectural decision.",
            adversary_premise="You find flaws in architectural decisions.",
            judge_premise="You decide which position is stronger.",
            max_rounds=3
        )
        result = await adv.debate("Should we use microservices or monolith?")
    """

    def __init__(
        self,
        advocate_premise: str,
        adversary_premise: str,
        judge_premise: str | None = None,
        max_rounds: int = 3,
        advocate_model: str | None = None,
        adversary_model: str | None = None,
        judge_model: str | None = None,
        advocate_scope: dict[str, Any] | None = None,
        adversary_scope: dict[str, Any] | None = None,
        judge_scope: dict[str, Any] | None = None,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize Adversarial pattern.

        Args:
            advocate_premise: Premise for the advocate agent (argues in favor)
            adversary_premise: Premise for the adversary agent (attacks/critiques)
            judge_premise: Optional premise for judge agent (decides winner)
            max_rounds: Maximum debate rounds
            advocate_model: Model for advocate agent
            adversary_model: Model for adversary agent
            judge_model: Model for judge agent
            advocate_scope: Tools for advocate agent
            adversary_scope: Tools for adversary agent
            judge_scope: Tools for judge agent
            db: Optional coordination database for tracking agents
        """
        self.advocate_premise = advocate_premise
        self.adversary_premise = adversary_premise
        self.judge_premise = judge_premise

        # Validate max_rounds
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        self.max_rounds = max_rounds
        self.advocate_model = advocate_model
        self.adversary_model = adversary_model
        self.judge_model = judge_model
        self.advocate_scope = advocate_scope or {}
        self.adversary_scope = adversary_scope or {}
        self.judge_scope = judge_scope or {}
        self.db = db

        # Agents spawned lazily
        self.advocate = None
        self.adversary = None
        self.judge = None

        # Track debate history
        self.debate_history: list[dict[str, str]] = []

        # Adversarial ID (generated per debate execution)
        self.adv_id: str | None = None

    async def _ensure_advocate(self, round_num: int):
        """Lazy spawn advocate agent with pattern env vars."""
        if self.advocate is None:
            # Set pattern-aware environment variables
            os.environ["PATTERN_TYPE"] = "adversarial"
            os.environ["PATTERN_ID"] = self.adv_id or ""
            os.environ["ADV_ID"] = self.adv_id or ""
            os.environ["AGENT_ROLE"] = "advocate"
            os.environ["ADVERSARIAL_ROUND"] = str(round_num)
            os.environ["ADVERSARIAL_MAX_ROUNDS"] = str(self.max_rounds)

            spawn_kwargs = {"premise": self.advocate_premise}
            if self.advocate_scope:
                spawn_kwargs["scope"] = self.advocate_scope
            if self.advocate_model:
                spawn_kwargs["model"] = self.advocate_model

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.advocate = await tracked_spawn(
                    db=self.db, pattern="adversarial", **spawn_kwargs
                )
            else:
                self.advocate = await spawn(**spawn_kwargs)

    async def _ensure_adversary(self, round_num: int):
        """Lazy spawn adversary agent with pattern env vars."""
        if self.adversary is None:
            # Set pattern-aware environment variables
            os.environ["PATTERN_TYPE"] = "adversarial"
            os.environ["PATTERN_ID"] = self.adv_id or ""
            os.environ["ADV_ID"] = self.adv_id or ""
            os.environ["AGENT_ROLE"] = "adversary"
            os.environ["ADVERSARIAL_ROUND"] = str(round_num)
            os.environ["ADVERSARIAL_MAX_ROUNDS"] = str(self.max_rounds)

            spawn_kwargs = {"premise": self.adversary_premise}
            if self.adversary_scope:
                spawn_kwargs["scope"] = self.adversary_scope
            if self.adversary_model:
                spawn_kwargs["model"] = self.adversary_model

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.adversary = await tracked_spawn(
                    db=self.db, pattern="adversarial", **spawn_kwargs
                )
            else:
                self.adversary = await spawn(**spawn_kwargs)

    async def _ensure_judge(self):
        """Lazy spawn judge agent with pattern env vars."""
        if self.judge is None and self.judge_premise:
            # Set pattern-aware environment variables
            os.environ["PATTERN_TYPE"] = "adversarial"
            os.environ["PATTERN_ID"] = self.adv_id or ""
            os.environ["ADV_ID"] = self.adv_id or ""
            os.environ["AGENT_ROLE"] = "judge"
            os.environ["ADVERSARIAL_ROUND"] = str(self.max_rounds)
            os.environ["ADVERSARIAL_MAX_ROUNDS"] = str(self.max_rounds)

            spawn_kwargs = {"premise": self.judge_premise}
            if self.judge_scope:
                spawn_kwargs["scope"] = self.judge_scope
            if self.judge_model:
                spawn_kwargs["model"] = self.judge_model

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.judge = await tracked_spawn(
                    db=self.db, pattern="adversarial", **spawn_kwargs
                )
            else:
                self.judge = await spawn(**spawn_kwargs)

    async def debate(self, question: str) -> dict[str, Any]:
        """
        Run adversarial debate on a question.

        Args:
            question: The question or topic to debate

        Returns:
            Dict with debate history and final positions
        """
        # Generate unique ID for this debate execution
        self.adv_id = str(uuid4())

        # Reset agents for fresh debate
        self.advocate = None
        self.adversary = None

        # Save original env vars for cleanup
        original_env = {
            "PATTERN_TYPE": os.environ.get("PATTERN_TYPE"),
            "PATTERN_ID": os.environ.get("PATTERN_ID"),
            "ADV_ID": os.environ.get("ADV_ID"),
            "AGENT_ROLE": os.environ.get("AGENT_ROLE"),
            "ADVERSARIAL_ROUND": os.environ.get("ADVERSARIAL_ROUND"),
            "ADVERSARIAL_MAX_ROUNDS": os.environ.get("ADVERSARIAL_MAX_ROUNDS"),
        }

        try:
            self.debate_history = []
            advocate_position = ""
            adversary_position = ""

            for round_num in range(1, self.max_rounds + 1):
                # Update round number in env
                os.environ["ADVERSARIAL_ROUND"] = str(round_num)

                # Ensure advocate spawned with current round
                await self._ensure_advocate(round_num)
                # Ensure adversary spawned with current round
                await self._ensure_adversary(round_num)

                # Advocate presents/refines argument
                if round_num == 1:
                    advocate_prompt = f"""
                    Question: {question}

                    Present your argument in favor. Be persuasive and thorough.
                    """
                else:
                    advocate_prompt = f"""
                    Question: {question}

                    Your previous argument: {advocate_position}

                    Adversary's critique: {adversary_position}

                    Refine and strengthen your argument, addressing the critique.
                    """

                advocate_position = await self.advocate.call(str, advocate_prompt)
                self.debate_history.append({
                    "round": round_num,
                    "role": "advocate",
                    "content": advocate_position
                })

                # Adversary critiques
                adversary_prompt = f"""
                Question: {question}

                Advocate's argument: {advocate_position}

                Critique this argument. Find flaws, weaknesses, and counterarguments.
                """

                adversary_position = await self.adversary.call(str, adversary_prompt)
                self.debate_history.append({
                    "round": round_num,
                    "role": "adversary",
                    "content": adversary_position
                })

            # All rounds completed, return final results
            result = {
                "question": question,
                "advocate_final": advocate_position,
                "adversary_final": adversary_position,
                "history": self.debate_history
            }
            return result
        finally:
            # Restore original env vars
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    async def resolve(self, question: str) -> dict[str, Any] | str:
        """
        Run debate and resolve with judge (if available).

        Args:
            question: The question or topic to debate

        Returns:
            Judge's verdict if judge exists, otherwise both final positions
        """
        debate_result = await self.debate(question)

        if self.judge_premise:
            await self._ensure_judge()

            judge_prompt = f"""
            You are judging a debate on: {question}

            ADVOCATE'S POSITION:
            {debate_result['advocate_final']}

            ADVERSARY'S POSITION:
            {debate_result['adversary_final']}

            Evaluate both positions and decide which is stronger.
            Provide your verdict with reasoning.
            """

            verdict = await self.judge.call(str, judge_prompt)
            return {
                "question": question,
                "advocate_final": debate_result["advocate_final"],
                "adversary_final": debate_result["adversary_final"],
                "verdict": verdict,
                "history": debate_result["history"]
            }

        # No judge - return both positions
        return debate_result
