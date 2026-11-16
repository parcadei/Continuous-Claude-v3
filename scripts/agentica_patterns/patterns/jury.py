"""
Jury Pattern for Agentica.

N independent agents vote on a question via Consensus mechanism.

This pattern sets the following environment variables for pattern-aware hooks:
- PATTERN_TYPE=jury
- PATTERN_ID=<unique_jury_id>
- JURY_ID=<unique_jury_id>
- AGENT_ROLE=juror
- JUROR_INDEX=<n> (0-indexed)
- TOTAL_JURORS=<n>

See: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 16)
"""

import asyncio
import os
from collections.abc import Callable
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
    Consensus,
    ConsensusMode,
)

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


class Jury:
    """
    Jury pattern: N independent agents vote on a question via Consensus.

    All jurors evaluate independently and vote. Consensus mechanism
    determines the final verdict (majority, unanimous, threshold).

    Example:
        jury = Jury(
            num_jurors=5,
            consensus_mode=ConsensusMode.MAJORITY
        )
        verdict = await jury.decide(bool, "Is this code safe?")
    """

    def __init__(
        self,
        num_jurors: int,
        consensus_mode: ConsensusMode,
        threshold: float | None = None,
        weights: list[float] | None = None,
        premise: str | None = None,
        premises: list[str] | None = None,
        model: str | None = None,
        scope: dict[str, Any] | None = None,
        key: Callable[[Any], Any] | None = None,
        allow_partial: bool = False,
        min_jurors: int | None = None,
        debug: bool = False,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize Jury.

        Args:
            num_jurors: Number of jurors to spawn
            consensus_mode: Voting mode (MAJORITY, UNANIMOUS, THRESHOLD)
            threshold: Required agreement percentage for THRESHOLD mode
            weights: Optional weights for each juror
            premise: Single premise for all jurors (mutually exclusive with premises)
            premises: Different premise per juror (mutually exclusive with premise)
            model: Model to use for all jurors
            scope: Tools available to all jurors
            key: Function to extract decision from structured votes
            allow_partial: Continue with partial votes if some jurors fail
            min_jurors: Minimum successful jurors required (only with allow_partial)
            debug: Track individual votes for debugging
            db: Optional coordination database for tracking agents

        Raises:
            ValueError: Invalid configuration
        """
        # Validation
        if num_jurors < 1:
            raise ValueError("num_jurors must be at least 1")

        if weights and len(weights) != num_jurors:
            raise ValueError("weights must be same length as num_jurors")

        if premises and len(premises) != num_jurors:
            raise ValueError("premises must be same length as num_jurors")

        if consensus_mode == ConsensusMode.THRESHOLD and threshold is None:
            raise ValueError("threshold parameter required for THRESHOLD mode")

        if threshold is not None and not (0 <= threshold <= 1):
            raise ValueError("threshold must be between 0 and 1")

        self.num_jurors = num_jurors
        self.consensus_mode = consensus_mode
        self.threshold = threshold
        self.weights = weights
        self.premise = premise
        self.premises = premises
        self.model = model
        self.scope = scope or {}
        self.key = key
        self.allow_partial = allow_partial
        self.min_jurors = min_jurors or num_jurors
        self.debug = debug
        self.db = db

        # Create consensus mechanism
        self.consensus = Consensus(mode=consensus_mode, threshold=threshold)

        # Debug: track last votes
        if debug:
            self.last_votes = []

        # Generate unique jury ID for each decide() call
        self.jury_id: str | None = None

    def _get_juror_premise(self, index: int) -> str:
        """Get premise for juror at given index."""
        if self.premises:
            return self.premises[index]
        if self.premise:
            return self.premise
        return "You are an expert evaluator. Provide your honest assessment."

    def _build_spawn_kwargs(self, premise: str) -> dict[str, Any]:
        """Build spawn kwargs for a juror."""
        kwargs: dict[str, Any] = {"premise": premise}
        if self.model:
            kwargs["model"] = self.model
        if self.scope:
            kwargs["scope"] = self.scope
        return kwargs

    @contextmanager
    def _pattern_env_context(self, juror_index: int):
        """Context manager to set and restore pattern environment variables.

        Sets:
            PATTERN_TYPE=jury
            PATTERN_ID=<jury_id>
            JURY_ID=<jury_id>
            AGENT_ROLE=juror
            JUROR_INDEX=<n> (0-indexed)
            TOTAL_JURORS=<n>

        These env vars are read by pattern-aware hooks to route to jury handlers.
        """
        # Save original values
        original_env = {
            'PATTERN_TYPE': os.environ.get('PATTERN_TYPE'),
            'PATTERN_ID': os.environ.get('PATTERN_ID'),
            'JURY_ID': os.environ.get('JURY_ID'),
            'AGENT_ROLE': os.environ.get('AGENT_ROLE'),
            'JUROR_INDEX': os.environ.get('JUROR_INDEX'),
            'TOTAL_JURORS': os.environ.get('TOTAL_JURORS'),
        }

        try:
            # Set pattern env vars
            os.environ['PATTERN_TYPE'] = 'jury'
            os.environ['PATTERN_ID'] = self.jury_id or ''
            os.environ['JURY_ID'] = self.jury_id or ''
            os.environ['AGENT_ROLE'] = 'juror'
            os.environ['JUROR_INDEX'] = str(juror_index)
            os.environ['TOTAL_JURORS'] = str(self.num_jurors)

            yield
        finally:
            # Restore original values
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    async def _spawn_jurors(self) -> list:
        """Spawn all jurors with pattern environment variables set."""
        jurors = []
        for i in range(self.num_jurors):
            premise = self._get_juror_premise(i)
            spawn_kwargs = self._build_spawn_kwargs(premise)

            # Set pattern env vars for this juror
            with self._pattern_env_context(juror_index=i):
                # Use tracked_spawn if db is set
                if self.db:
                    from scripts.agentica_patterns.tracked_agent import tracked_spawn
                    juror = await tracked_spawn(db=self.db, pattern="jury", **spawn_kwargs)
                else:
                    juror = await spawn(**spawn_kwargs)
                jurors.append(juror)
        return jurors

    async def _collect_votes(
        self, jurors: list, return_type: type, question: str
    ) -> list[Any]:
        """Collect votes from jurors, handling failures if allow_partial."""
        from .primitives import gather_fail_fast

        async def get_vote(juror):
            return await juror.call(return_type, question)

        coros = [get_vote(juror) for juror in jurors]

        if self.allow_partial:
            # Partial mode: collect all results including exceptions
            results = await gather_fail_fast(coros, fail_fast=False)
            votes = [v for v in results if not isinstance(v, Exception)]
            if len(votes) < self.min_jurors:
                raise ValueError(
                    f"Not enough successful jurors: {len(votes)} < {self.min_jurors}"
                )
            return votes
        else:
            # Strict mode: fail-fast via TaskGroup
            try:
                return await gather_fail_fast(coros, fail_fast=True)
            except ExceptionGroup as eg:
                # Re-raise first exception for backward compatibility
                raise eg.exceptions[0] from eg

    async def decide(self, return_type: type, question: str) -> Any:
        """
        Jury decides on a question.

        Args:
            return_type: Expected return type for votes
            question: Question for jurors to decide

        Returns:
            Consensus verdict from jurors

        Raises:
            ConsensusNotReached: If consensus cannot be reached

        Note:
            Sets PATTERN_TYPE=jury environment variable during execution
            for pattern-aware hooks to detect and route correctly.
        """
        # Generate a new jury ID for this decision
        self.jury_id = uuid4().hex[:12]

        jurors = await self._spawn_jurors()
        votes = await self._collect_votes(jurors, return_type, question)

        if self.debug:
            self.last_votes = votes

        return self.consensus.decide(votes=votes, weights=self.weights, key=self.key)
