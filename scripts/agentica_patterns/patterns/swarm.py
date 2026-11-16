"""
Swarm Pattern for Agentica.

Spawn multiple agents with different perspectives in parallel, aggregate results.

This pattern sets the following environment variables for pattern-aware hooks:
- PATTERN_TYPE=swarm
- PATTERN_ID=<unique_swarm_id>
- SWARM_ID=<unique_swarm_id>
- AGENT_ROLE=worker (for swarm agents)

See: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 13)
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


class Swarm:
    """
    Swarm pattern: Spawn multiple agents with different perspectives in parallel.

    Each agent attacks the problem from a different angle. Results are aggregated
    using the Aggregator primitive.

    Example:
        swarm = Swarm(
            perspectives=[
                "You are a security expert.",
                "You are a performance expert.",
                "You are a UX expert."
            ]
        )
        result = await swarm.execute("Analyze OAuth implementation")
    """

    def __init__(
        self,
        perspectives: list[str],
        aggregate_mode: AggregateMode = AggregateMode.MERGE,
        aggregation_separator: str = " ",
        fail_fast: bool = False,
        model: str | None = None,
        scope: dict[str, Any] | None = None,
        mcp: str | None = None,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize Swarm pattern.

        Args:
            perspectives: List of agent premises (one per agent)
            aggregate_mode: How to combine results (MERGE, CONCAT, BEST)
            aggregation_separator: Separator for CONCAT mode
            fail_fast: If True, stop on first error. If False, continue with partial results
            model: Model to use for all agents
            scope: Tools/functions available to all agents
            mcp: MCP config path to pass to all agents
            db: Optional coordination database for tracking agents

        Raises:
            ValueError: If perspectives is None or empty
        """
        if perspectives is None:
            raise ValueError("perspectives cannot be None")
        if not perspectives:
            raise ValueError("perspectives cannot be empty")

        self.perspectives = perspectives
        self.fail_fast = fail_fast
        self.model = model
        self.scope = scope or {}
        self.mcp = mcp
        self.db = db

        # Create aggregator
        self.aggregator = Aggregator(
            mode=aggregate_mode,
            separator=aggregation_separator
        )

        # Set default return type based on aggregate mode
        if aggregate_mode == AggregateMode.MERGE:
            self.default_return_type = dict
        elif aggregate_mode == AggregateMode.CONCAT:
            self.default_return_type = str
        else:  # BEST
            self.default_return_type = dict

        # Generate unique swarm ID for this instance
        self.swarm_id = uuid4().hex[:12]

    @contextmanager
    def _pattern_env_context(self):
        """Context manager to set and restore pattern environment variables.

        Sets:
            PATTERN_TYPE=swarm
            PATTERN_ID=<swarm_id>
            SWARM_ID=<swarm_id>
            AGENT_ROLE=worker

        These env vars are read by pattern-aware hooks to route to swarm handlers.
        """
        # Save original values
        original_env = {
            'PATTERN_TYPE': os.environ.get('PATTERN_TYPE'),
            'PATTERN_ID': os.environ.get('PATTERN_ID'),
            'SWARM_ID': os.environ.get('SWARM_ID'),
            'AGENT_ROLE': os.environ.get('AGENT_ROLE'),
        }

        try:
            # Set pattern env vars
            os.environ['PATTERN_TYPE'] = 'swarm'
            os.environ['PATTERN_ID'] = self.swarm_id
            os.environ['SWARM_ID'] = self.swarm_id
            os.environ['AGENT_ROLE'] = 'worker'

            yield
        finally:
            # Restore original values
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    async def execute(
        self,
        query: str,
        return_type: type = None
    ) -> Any:
        """
        Execute swarm on a query.

        Args:
            query: Question or task for the swarm
            return_type: Expected return type for each agent (defaults to aggregate mode default)

        Returns:
            Aggregated results from all agents

        Note:
            Sets PATTERN_TYPE=swarm environment variable during execution
            for pattern-aware hooks to detect and route correctly.
        """
        if return_type is None:
            return_type = self.default_return_type

        # Set pattern env vars during spawn and execution
        with self._pattern_env_context():
            # Spawn agents for each perspective
            agents = []
            for perspective in self.perspectives:
                spawn_kwargs = {"premise": perspective}
                if self.model:
                    spawn_kwargs["model"] = self.model
                if self.scope:
                    spawn_kwargs["scope"] = self.scope
                if self.mcp:
                    spawn_kwargs["mcp"] = self.mcp

                # Use tracked_spawn if db is set
                if self.db:
                    from scripts.agentica_patterns.tracked_agent import tracked_spawn
                    agent = await tracked_spawn(db=self.db, pattern="swarm", **spawn_kwargs)
                else:
                    agent = await spawn(**spawn_kwargs)
                agents.append(agent)

            # Execute all agents in parallel
            from .primitives import gather_fail_fast

            async def call_agent(agent):
                return await agent.call(return_type, query)

            coros = [call_agent(agent) for agent in agents]

            if self.fail_fast:
                try:
                    results = await gather_fail_fast(coros, fail_fast=True)
                except ExceptionGroup as eg:
                    # Re-raise first exception for backward compatibility
                    raise eg.exceptions[0] from eg
            else:
                raw_results = await gather_fail_fast(coros, fail_fast=False)
                # Filter exceptions to None for backward compatibility
                results = [r if not isinstance(r, Exception) else None for r in raw_results]

        # Filter None results (failed agents in non-fail-fast mode)
        results = [r for r in results if r is not None]

        # Aggregate results
        return self.aggregator.aggregate(results)
