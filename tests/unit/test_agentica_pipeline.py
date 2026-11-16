"""
TDD Tests for Pipeline Pattern

Tests written BEFORE implementation to drive design.
Expected to FAIL until scripts/agentica/patterns.py implements Pipeline.

Pipeline Pattern:
- Executes stages sequentially A → B → C
- Passes HandoffState between stages
- Each stage receives previous stage's output
- Returns final stage's output
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scripts.agentica_patterns.primitives import HandoffState


class TestPipeline:
    """Test sequential pipeline execution pattern."""

    @pytest.mark.asyncio
    async def test_pipeline_sequential_execution(self):
        """Stages A→B→C execute in order and pass HandoffState."""
        from scripts.agentica_patterns.patterns import Pipeline

        # Track execution order
        execution_order = []

        async def stage_a(state: HandoffState) -> HandoffState:
            execution_order.append("A")
            state.add_artifact("stage_a_output", "result_a")
            state.update_instruction("Processed by A, now go to B")
            return state

        async def stage_b(state: HandoffState) -> HandoffState:
            execution_order.append("B")
            assert "stage_a_output" in state.artifacts
            state.add_artifact("stage_b_output", "result_b")
            state.update_instruction("Processed by B, now go to C")
            return state

        async def stage_c(state: HandoffState) -> HandoffState:
            execution_order.append("C")
            assert "stage_a_output" in state.artifacts
            assert "stage_b_output" in state.artifacts
            state.add_artifact("stage_c_output", "result_c")
            state.update_instruction("Pipeline complete")
            return state

        # Create pipeline with three stages
        pipeline = Pipeline(stages=[stage_a, stage_b, stage_c])

        # Initial state
        initial_state = HandoffState(
            context="Pipeline test",
            next_instruction="Start pipeline"
        )

        # Execute pipeline
        final_state = await pipeline.run(initial_state)

        # Verify execution order
        assert execution_order == ["A", "B", "C"]

        # Verify all artifacts preserved
        assert final_state.artifacts["stage_a_output"] == "result_a"
        assert final_state.artifacts["stage_b_output"] == "result_b"
        assert final_state.artifacts["stage_c_output"] == "result_c"

        # Verify final instruction
        assert final_state.next_instruction == "Pipeline complete"

    @pytest.mark.asyncio
    async def test_pipeline_handoff_state_passed(self):
        """Each stage receives previous output via HandoffState."""
        from scripts.agentica_patterns.patterns import Pipeline

        async def stage_1(state: HandoffState) -> HandoffState:
            # First stage modifies state
            state.add_artifact("data", [1, 2, 3])
            state.metadata["processed_by"] = "stage_1"
            return state

        async def stage_2(state: HandoffState) -> HandoffState:
            # Second stage receives the modified state
            assert "data" in state.artifacts
            assert state.artifacts["data"] == [1, 2, 3]
            assert state.metadata["processed_by"] == "stage_1"

            # Modify further
            state.artifacts["data"].append(4)
            state.metadata["processed_by"] = "stage_2"
            return state

        async def stage_3(state: HandoffState) -> HandoffState:
            # Third stage sees all previous modifications
            assert state.artifacts["data"] == [1, 2, 3, 4]
            assert state.metadata["processed_by"] == "stage_2"

            state.metadata["processed_by"] = "stage_3"
            return state

        pipeline = Pipeline(stages=[stage_1, stage_2, stage_3])

        initial = HandoffState(
            context="Test handoff",
            next_instruction="Start"
        )

        result = await pipeline.run(initial)

        # Final state has all accumulated changes
        assert result.artifacts["data"] == [1, 2, 3, 4]
        assert result.metadata["processed_by"] == "stage_3"

    @pytest.mark.asyncio
    async def test_pipeline_artifacts_accumulate(self):
        """Artifacts from each stage are preserved and accumulate."""
        from scripts.agentica_patterns.patterns import Pipeline

        async def fetch_stage(state: HandoffState) -> HandoffState:
            state.add_artifact("raw_data", {"users": [1, 2, 3]})
            return state

        async def transform_stage(state: HandoffState) -> HandoffState:
            raw = state.artifacts["raw_data"]
            state.add_artifact("transformed", {"count": len(raw["users"])})
            return state

        async def enrich_stage(state: HandoffState) -> HandoffState:
            state.add_artifact("enriched", {"total": 100})
            return state

        pipeline = Pipeline(stages=[fetch_stage, transform_stage, enrich_stage])

        initial = HandoffState(
            context="Data pipeline",
            next_instruction="Fetch data"
        )

        result = await pipeline.run(initial)

        # All artifacts from all stages preserved
        assert "raw_data" in result.artifacts
        assert "transformed" in result.artifacts
        assert "enriched" in result.artifacts
        assert result.artifacts["raw_data"]["users"] == [1, 2, 3]
        assert result.artifacts["transformed"]["count"] == 3
        assert result.artifacts["enriched"]["total"] == 100

    @pytest.mark.asyncio
    async def test_pipeline_single_stage(self):
        """Single stage pipeline works correctly."""
        from scripts.agentica_patterns.patterns import Pipeline

        async def only_stage(state: HandoffState) -> HandoffState:
            state.add_artifact("result", "done")
            return state

        pipeline = Pipeline(stages=[only_stage])

        initial = HandoffState(
            context="Single stage test",
            next_instruction="Process"
        )

        result = await pipeline.run(initial)

        assert result.artifacts["result"] == "done"

    @pytest.mark.asyncio
    async def test_pipeline_stage_failure_stops(self):
        """If a stage fails, pipeline stops and propagates error."""
        from scripts.agentica_patterns.patterns import Pipeline

        async def stage_1(state: HandoffState) -> HandoffState:
            state.add_artifact("stage_1", "ok")
            return state

        async def failing_stage(state: HandoffState) -> HandoffState:
            raise ValueError("Stage 2 failed")

        async def stage_3(state: HandoffState) -> HandoffState:
            # This should not execute
            state.add_artifact("stage_3", "should not see this")
            return state

        pipeline = Pipeline(stages=[stage_1, failing_stage, stage_3])

        initial = HandoffState(
            context="Failure test",
            next_instruction="Start"
        )

        # Pipeline should propagate the error
        with pytest.raises(ValueError, match="Stage 2 failed"):
            await pipeline.run(initial)

    @pytest.mark.asyncio
    async def test_pipeline_empty_stages_raises(self):
        """No stages raises ValueError."""
        from scripts.agentica_patterns.patterns import Pipeline

        with pytest.raises(ValueError, match="at least one stage"):
            Pipeline(stages=[])

    @pytest.mark.asyncio
    async def test_pipeline_with_spawn_agents(self):
        """Pipeline can use spawn() agents as stages."""
        from scripts.agentica_patterns.patterns import Pipeline

        # Mock spawn to return mock agents
        mock_agent_a = AsyncMock()
        mock_agent_b = AsyncMock()

        # Stage A modifies state
        async def mock_a_call(return_type, prompt, **kwargs):
            state = kwargs.get("state")
            state.add_artifact("analyzed", True)
            return state

        # Stage B receives state from A
        async def mock_b_call(return_type, prompt, **kwargs):
            state = kwargs.get("state")
            assert state.artifacts["analyzed"] is True
            state.add_artifact("summarized", "Complete")
            return state

        mock_agent_a.call = mock_a_call
        mock_agent_b.call = mock_b_call

        async def stage_with_agent_a(state: HandoffState) -> HandoffState:
            result = await mock_agent_a.call(
                HandoffState,
                f"Analyze: {state.next_instruction}",
                state=state
            )
            return result

        async def stage_with_agent_b(state: HandoffState) -> HandoffState:
            result = await mock_agent_b.call(
                HandoffState,
                f"Summarize: {state.next_instruction}",
                state=state
            )
            return result

        pipeline = Pipeline(stages=[stage_with_agent_a, stage_with_agent_b])

        initial = HandoffState(
            context="Agent pipeline test",
            next_instruction="Process data"
        )

        result = await pipeline.run(initial)

        # Both agents processed the state
        assert result.artifacts["analyzed"] is True
        assert result.artifacts["summarized"] == "Complete"

    @pytest.mark.asyncio
    async def test_pipeline_records_handoff_chain(self):
        """Pipeline records handoffs in state's handoff chain."""
        from scripts.agentica_patterns.patterns import Pipeline

        async def stage_a(state: HandoffState) -> HandoffState:
            state.record_handoff(from_agent="pipeline_start", to_agent="stage_a")
            return state

        async def stage_b(state: HandoffState) -> HandoffState:
            state.record_handoff(from_agent="stage_a", to_agent="stage_b")
            return state

        async def stage_c(state: HandoffState) -> HandoffState:
            state.record_handoff(from_agent="stage_b", to_agent="stage_c")
            return state

        pipeline = Pipeline(stages=[stage_a, stage_b, stage_c])

        initial = HandoffState(
            context="Handoff tracking test",
            next_instruction="Track handoffs"
        )

        result = await pipeline.run(initial)

        chain = result.get_handoff_chain()
        assert len(chain) == 3
        assert chain[0] == {"from": "pipeline_start", "to": "stage_a"}
        assert chain[1] == {"from": "stage_a", "to": "stage_b"}
        assert chain[2] == {"from": "stage_b", "to": "stage_c"}

    @pytest.mark.asyncio
    async def test_pipeline_context_updates(self):
        """Pipeline allows stages to update context for next stage."""
        from scripts.agentica_patterns.patterns import Pipeline

        async def stage_1(state: HandoffState) -> HandoffState:
            state.context = "Stage 1 context: data fetched"
            state.update_instruction("Transform the data")
            return state

        async def stage_2(state: HandoffState) -> HandoffState:
            assert "data fetched" in state.context
            assert state.next_instruction == "Transform the data"
            state.context = "Stage 2 context: data transformed"
            state.update_instruction("Validate results")
            return state

        async def stage_3(state: HandoffState) -> HandoffState:
            assert "data transformed" in state.context
            assert state.next_instruction == "Validate results"
            state.context = "Stage 3 context: validation complete"
            return state

        pipeline = Pipeline(stages=[stage_1, stage_2, stage_3])

        initial = HandoffState(
            context="Initial context",
            next_instruction="Start processing"
        )

        result = await pipeline.run(initial)

        assert result.context == "Stage 3 context: validation complete"
