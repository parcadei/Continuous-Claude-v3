"""TDD Tests for Phase 20: PATTERN_TYPE=pipeline in patterns/pipeline.py.

These tests verify that the Pipeline pattern sets environment variables correctly
when spawning stage agents.

Expected environment variables:
- PATTERN_TYPE=pipeline
- PIPELINE_ID=<unique_id>
- AGENT_ROLE=stage
- PIPELINE_STAGE_INDEX=<n> (0-indexed)
- PIPELINE_TOTAL_STAGES=<n>

Module path: scripts/agentica/patterns/pipeline.py

Tests are designed to FAIL initially (TDD approach) until Phase 20 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 20)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parents[2]
sys.path.insert(0, str(project_root))

from scripts.agentica_patterns.patterns.pipeline import Pipeline
from scripts.agentica_patterns.patterns.primitives import HandoffState


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = AsyncMock()
    agent.run = AsyncMock(return_value=HandoffState())
    return agent


@pytest.fixture
def pipeline_stages():
    """Create mock pipeline stages."""
    async def stage1(state: HandoffState) -> HandoffState:
        state.artifacts["stage1_output"] = "data from stage 1"
        return state

    async def stage2(state: HandoffState) -> HandoffState:
        state.artifacts["stage2_output"] = "data from stage 2"
        return state

    async def stage3(state: HandoffState) -> HandoffState:
        state.artifacts["stage3_output"] = "data from stage 3"
        return state

    return [stage1, stage2, stage3]


# =============================================================================
# Environment Variable Tests
# =============================================================================


class TestPipelineEnvironmentVariables:
    """Tests for environment variable setting in Pipeline pattern."""

    @pytest.mark.asyncio
    async def test_sets_pattern_type(self, pipeline_stages):
        """Pipeline sets PATTERN_TYPE=pipeline when executing stages."""
        pipeline = Pipeline(stages=pipeline_stages)
        initial_state = HandoffState(context="test", next_instruction="test")

        # Capture env vars during stage execution
        captured_envs = []

        async def capture_env_stage(state: HandoffState) -> HandoffState:
            """Capture environment variables during execution."""
            import os
            captured_envs.append({
                "PATTERN_TYPE": os.environ.get("PATTERN_TYPE"),
                "PIPELINE_ID": os.environ.get("PIPELINE_ID"),
                "AGENT_ROLE": os.environ.get("AGENT_ROLE"),
            })
            return state

        # Replace first stage with capturing stage
        test_pipeline = Pipeline(stages=[capture_env_stage])
        await test_pipeline.run(initial_state)

        # Verify PATTERN_TYPE was set
        assert len(captured_envs) > 0, "Should have captured env vars"
        env = captured_envs[0]
        assert env.get("PATTERN_TYPE") == "pipeline", (
            "Pipeline should set PATTERN_TYPE=pipeline during stage execution. "
            f"Got env: {env}"
        )

    @pytest.mark.asyncio
    async def test_sets_pipeline_id(self, pipeline_stages):
        """Pipeline sets unique PIPELINE_ID for each execution."""
        pipeline = Pipeline(stages=pipeline_stages)
        initial_state = HandoffState(context="test", next_instruction="test")

        # Capture env vars during stage execution
        captured_envs = []

        async def capture_env_stage(state: HandoffState) -> HandoffState:
            """Capture environment variables during execution."""
            import os
            captured_envs.append(os.environ.get("PIPELINE_ID"))
            return state

        test_pipeline = Pipeline(stages=[capture_env_stage])
        await test_pipeline.run(initial_state)

        assert len(captured_envs) > 0, "Should have captured env vars"
        pipeline_id = captured_envs[0]
        assert pipeline_id, "Pipeline should set PIPELINE_ID"
        assert len(pipeline_id) > 0, "PIPELINE_ID should be non-empty"

    @pytest.mark.asyncio
    async def test_sets_stage_index(self, pipeline_stages):
        """Pipeline sets PIPELINE_STAGE_INDEX for each stage."""
        # Capture env vars during each stage execution
        captured_indices = []

        async def capture_stage_0(state: HandoffState) -> HandoffState:
            import os
            captured_indices.append(os.environ.get("PIPELINE_STAGE_INDEX"))
            return state

        async def capture_stage_1(state: HandoffState) -> HandoffState:
            import os
            captured_indices.append(os.environ.get("PIPELINE_STAGE_INDEX"))
            return state

        async def capture_stage_2(state: HandoffState) -> HandoffState:
            import os
            captured_indices.append(os.environ.get("PIPELINE_STAGE_INDEX"))
            return state

        test_pipeline = Pipeline(stages=[capture_stage_0, capture_stage_1, capture_stage_2])
        initial_state = HandoffState(context="test", next_instruction="test")
        await test_pipeline.run(initial_state)

        # Verify stage indices are correct
        assert len(captured_indices) == 3, "Should have captured 3 stage indices"
        assert captured_indices[0] == "0", f"Stage 0 should have index '0', got {captured_indices[0]}"
        assert captured_indices[1] == "1", f"Stage 1 should have index '1', got {captured_indices[1]}"
        assert captured_indices[2] == "2", f"Stage 2 should have index '2', got {captured_indices[2]}"

    @pytest.mark.asyncio
    async def test_sets_total_stages(self, pipeline_stages):
        """Pipeline sets PIPELINE_TOTAL_STAGES."""
        captured_total = []

        async def capture_env_stage(state: HandoffState) -> HandoffState:
            import os
            captured_total.append(os.environ.get("PIPELINE_TOTAL_STAGES"))
            return state

        test_pipeline = Pipeline(stages=[capture_env_stage] * 3)
        initial_state = HandoffState(context="test", next_instruction="test")
        await test_pipeline.run(initial_state)

        assert len(captured_total) > 0, "Should have captured total stages"
        total_stages = captured_total[0]
        assert total_stages == "3", f"PIPELINE_TOTAL_STAGES should be '3', got {total_stages}"

    @pytest.mark.asyncio
    async def test_sets_agent_role(self, pipeline_stages):
        """Pipeline sets AGENT_ROLE=stage."""
        captured_role = []

        async def capture_env_stage(state: HandoffState) -> HandoffState:
            import os
            captured_role.append(os.environ.get("AGENT_ROLE"))
            return state

        test_pipeline = Pipeline(stages=[capture_env_stage])
        initial_state = HandoffState(context="test", next_instruction="test")
        await test_pipeline.run(initial_state)

        assert len(captured_role) > 0, "Should have captured agent role"
        agent_role = captured_role[0]
        assert agent_role == "stage", f"AGENT_ROLE should be 'stage', got {agent_role}"


# =============================================================================
# Integration Tests
# =============================================================================


class TestPipelineIntegration:
    """Integration tests for Pipeline pattern with environment variables."""

    @pytest.mark.asyncio
    async def test_pipeline_runs_without_env_vars(self, pipeline_stages):
        """Pipeline runs successfully without environment variable support (baseline)."""
        # This test ensures existing functionality isn't broken
        pipeline = Pipeline(stages=pipeline_stages)
        initial_state = HandoffState(context="test", next_instruction="test")

        result = await pipeline.run(initial_state)

        assert isinstance(result, HandoffState), "Pipeline should return HandoffState"
        # Verify stages executed
        assert "stage1_output" in result.artifacts
        assert "stage2_output" in result.artifacts
        assert "stage3_output" in result.artifacts

    @pytest.mark.asyncio
    async def test_pipeline_id_consistent_across_stages(self, pipeline_stages):
        """PIPELINE_ID remains consistent across all stages in one execution."""
        captured_ids = []

        async def capture_stage_0(state: HandoffState) -> HandoffState:
            import os
            captured_ids.append(os.environ.get("PIPELINE_ID"))
            return state

        async def capture_stage_1(state: HandoffState) -> HandoffState:
            import os
            captured_ids.append(os.environ.get("PIPELINE_ID"))
            return state

        async def capture_stage_2(state: HandoffState) -> HandoffState:
            import os
            captured_ids.append(os.environ.get("PIPELINE_ID"))
            return state

        test_pipeline = Pipeline(stages=[capture_stage_0, capture_stage_1, capture_stage_2])
        initial_state = HandoffState(context="test", next_instruction="test")
        await test_pipeline.run(initial_state)

        # All PIPELINE_IDs should be the same
        assert len(captured_ids) == 3, "Should have captured 3 pipeline IDs"
        assert len(set(captured_ids)) == 1, (
            f"PIPELINE_ID should be consistent across all stages. Got IDs: {captured_ids}"
        )

    @pytest.mark.asyncio
    async def test_stage_indices_sequential(self, pipeline_stages):
        """PIPELINE_STAGE_INDEX values are sequential (0, 1, 2, ...)."""
        captured_indices = []

        async def capture_stage_0(state: HandoffState) -> HandoffState:
            import os
            captured_indices.append(int(os.environ.get("PIPELINE_STAGE_INDEX", -1)))
            return state

        async def capture_stage_1(state: HandoffState) -> HandoffState:
            import os
            captured_indices.append(int(os.environ.get("PIPELINE_STAGE_INDEX", -1)))
            return state

        async def capture_stage_2(state: HandoffState) -> HandoffState:
            import os
            captured_indices.append(int(os.environ.get("PIPELINE_STAGE_INDEX", -1)))
            return state

        test_pipeline = Pipeline(stages=[capture_stage_0, capture_stage_1, capture_stage_2])
        initial_state = HandoffState(context="test", next_instruction="test")
        await test_pipeline.run(initial_state)

        # Should be [0, 1, 2]
        expected = [0, 1, 2]
        assert captured_indices == expected, (
            f"Stage indices should be sequential {expected}. Got: {captured_indices}"
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestPipelineErrorHandling:
    """Tests for error handling with environment variables."""

    @pytest.mark.asyncio
    async def test_handles_empty_stages_list(self):
        """Pipeline raises ValueError for empty stages list (existing behavior)."""
        with pytest.raises(ValueError, match="at least one stage"):
            Pipeline(stages=[])

    @pytest.mark.asyncio
    async def test_env_vars_not_leaked_between_pipelines(self, pipeline_stages):
        """Environment variables don't leak between separate pipeline executions."""
        captured_id1 = []
        captured_id2 = []

        async def capture_stage1(state: HandoffState) -> HandoffState:
            import os
            captured_id1.append(os.environ.get("PIPELINE_ID"))
            return state

        async def capture_stage2(state: HandoffState) -> HandoffState:
            import os
            captured_id2.append(os.environ.get("PIPELINE_ID"))
            return state

        # Run first pipeline
        pipeline1 = Pipeline(stages=[capture_stage1])
        initial_state = HandoffState(context="test", next_instruction="test")
        await pipeline1.run(initial_state)

        # Run second pipeline
        pipeline2 = Pipeline(stages=[capture_stage2])
        await pipeline2.run(initial_state)

        # IDs should be different (new execution = new ID)
        assert len(captured_id1) > 0 and len(captured_id2) > 0
        pipeline1_id = captured_id1[0]
        pipeline2_id = captured_id2[0]
        assert pipeline1_id != pipeline2_id, (
            f"Each pipeline execution should have unique PIPELINE_ID. "
            f"Got same ID: {pipeline1_id}"
        )
