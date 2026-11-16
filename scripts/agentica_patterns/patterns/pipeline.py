"""
Agentica Pipeline Pattern - Sequential Stage Execution.

Each stage receives the output of the previous stage via HandoffState.
Stages execute sequentially: A → B → C.

This pattern sets the following environment variables for pattern-aware hooks:
- PATTERN_TYPE=pipeline
- PATTERN_ID=<unique_pipeline_id>
- PIPELINE_ID=<unique_pipeline_id>
- AGENT_ROLE=stage
- PIPELINE_STAGE_INDEX=<n> (0-indexed)
- PIPELINE_TOTAL_STAGES=<n>

See: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 20)
"""

import os
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from uuid import uuid4

from .primitives import HandoffState


class Pipeline:
    """
    Pipeline pattern: Sequential stage execution with HandoffState.

    Each stage receives the output of the previous stage via HandoffState.
    Stages execute sequentially: A → B → C.

    Example:
        async def fetch(state: HandoffState) -> HandoffState:
            state.add_artifact("data", fetch_data())
            return state

        async def transform(state: HandoffState) -> HandoffState:
            data = state.artifacts["data"]
            state.add_artifact("transformed", transform(data))
            return state

        pipeline = Pipeline(stages=[fetch, transform])
        result = await pipeline.run(initial_state)
    """

    def __init__(self, stages: list[Callable[[HandoffState], Awaitable[HandoffState]]]):
        """
        Initialize Pipeline.

        Args:
            stages: List of async functions that take and return HandoffState

        Raises:
            ValueError: If stages is empty
        """
        if not stages:
            raise ValueError("Pipeline requires at least one stage")

        self.stages = stages
        self.pipeline_id: str | None = None

    @contextmanager
    def _pattern_env_context(self, stage_index: int):
        """Context manager to set and restore pattern environment variables.

        Sets:
            PATTERN_TYPE=pipeline
            PATTERN_ID=<pipeline_id>
            PIPELINE_ID=<pipeline_id>
            AGENT_ROLE=stage
            PIPELINE_STAGE_INDEX=<n> (0-indexed)
            PIPELINE_TOTAL_STAGES=<n>

        These env vars are read by pattern-aware hooks to route to pipeline handlers.
        """
        # Save original values
        original_env = {
            'PATTERN_TYPE': os.environ.get('PATTERN_TYPE'),
            'PATTERN_ID': os.environ.get('PATTERN_ID'),
            'PIPELINE_ID': os.environ.get('PIPELINE_ID'),
            'AGENT_ROLE': os.environ.get('AGENT_ROLE'),
            'PIPELINE_STAGE_INDEX': os.environ.get('PIPELINE_STAGE_INDEX'),
            'PIPELINE_TOTAL_STAGES': os.environ.get('PIPELINE_TOTAL_STAGES'),
        }

        try:
            # Set pattern env vars
            os.environ['PATTERN_TYPE'] = 'pipeline'
            os.environ['PATTERN_ID'] = self.pipeline_id or ''
            os.environ['PIPELINE_ID'] = self.pipeline_id or ''
            os.environ['AGENT_ROLE'] = 'stage'
            os.environ['PIPELINE_STAGE_INDEX'] = str(stage_index)
            os.environ['PIPELINE_TOTAL_STAGES'] = str(len(self.stages))

            yield

        finally:
            # Restore original values
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    async def run(self, initial_state: HandoffState) -> HandoffState:
        """
        Run the pipeline.

        Args:
            initial_state: Starting state for the pipeline

        Returns:
            Final state after all stages

        Note:
            Sets PATTERN_TYPE=pipeline environment variable during execution
            for pattern-aware hooks to detect and route correctly.
        """
        # Generate a new pipeline ID for this execution
        self.pipeline_id = uuid4().hex[:12]

        state = initial_state

        # Execute stages sequentially with pattern environment variables
        for stage_index, stage in enumerate(self.stages):
            with self._pattern_env_context(stage_index):
                state = await stage(state)

        return state
