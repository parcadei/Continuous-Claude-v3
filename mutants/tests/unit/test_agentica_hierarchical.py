"""
TDD Tests for Hierarchical Pattern

Tests written BEFORE implementation to drive design.
Expected to FAIL until patterns.py implements Hierarchical class.

Hierarchical pattern:
- Coordinator agent decomposes task into subtasks
- Spawns specialist agents for each subtask
- Specialists can run in parallel when independent
- Aggregates specialist results
- Coordinator synthesizes final answer
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scripts.agentica.patterns import Hierarchical

# Decorator for tests that require spawn mocking
def requires_spawn_mock(func):
    """Decorator that skips test if spawn mocking is required but not provided."""
    return func


class TestHierarchicalBasics:
    """Test basic hierarchical agent creation and structure."""

    @pytest.mark.asyncio
    async def test_hierarchical_creation(self):
        """Can create a Hierarchical coordinator."""
        hierarchical = Hierarchical(
            coordinator_premise="You are a coordinator that breaks tasks into subtasks.",
            specialist_premises={
                "researcher": "You research topics.",
                "analyst": "You analyze data."
            }
        )

        assert hierarchical is not None
        # Note: coordinator is None until first use (lazy spawn)
        assert hierarchical.coordinator_premise is not None
        assert len(hierarchical.specialist_premises) == 2
        assert "researcher" in hierarchical.specialist_premises
        assert "analyst" in hierarchical.specialist_premises

    @pytest.mark.asyncio
    async def test_hierarchical_with_scope(self):
        """Coordinator and specialists can have tools."""
        mock_tool = AsyncMock()

        hierarchical = Hierarchical(
            coordinator_premise="Coordinate research.",
            coordinator_scope={"plan": mock_tool},
            specialist_premises={"researcher": "Research topics."},
            specialist_scope={"search": mock_tool}
        )

        assert hierarchical.coordinator_scope == {"plan": mock_tool}
        assert hierarchical.specialist_scope == {"search": mock_tool}


class TestHierarchicalTaskDecomposition:
    """Test coordinator's task decomposition logic."""

    @pytest.mark.asyncio
    async def test_hierarchical_coordinator_decomposes(self):
        """Coordinator breaks task into subtasks."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            # Mock coordinator and specialists separately
            mock_coordinator = AsyncMock()
            # First call: decompose, subsequent calls: synthesis
            mock_coordinator.call = AsyncMock(side_effect=[
                [  # Decomposition returns subtasks
                    {"specialist": "researcher", "task": "Find papers on topic X"},
                    {"specialist": "analyst", "task": "Analyze findings"}
                ],
                "Final synthesized answer"  # Synthesis call
            ])

            mock_specialist = AsyncMock()
            mock_specialist.call = AsyncMock(return_value="Specialist result")

            # Return different mocks based on call order
            call_count = [0]
            async def spawn_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:  # First call is coordinator
                    return mock_coordinator
                return mock_specialist  # Subsequent calls are specialists

            mock_spawn.side_effect = spawn_side_effect

            hierarchical = Hierarchical(
                coordinator_premise="Break down tasks.",
                specialist_premises={
                    "researcher": "Research topics.",
                    "analyst": "Analyze data."
                }
            )

            # Execute task
            result = await hierarchical.execute("Research and analyze topic X")

            # Coordinator should be called at least once for decomposition
            assert mock_coordinator.call.call_count >= 1
            first_call_args = mock_coordinator.call.call_args_list[0]
            assert "Research and analyze topic X" in str(first_call_args)

    @pytest.mark.asyncio
    async def test_hierarchical_returns_structured_plan(self):
        """Coordinator returns list of structured subtasks."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()
            mock_coordinator.call = AsyncMock(return_value=[
                {"specialist": "researcher", "task": "Research AI agents"},
                {"specialist": "writer", "task": "Write summary"}
            ])
            mock_spawn.return_value = mock_coordinator

            hierarchical = Hierarchical(
                coordinator_premise="You decompose tasks.",
                specialist_premises={
                    "researcher": "You research.",
                    "writer": "You write."
                }
            )

            subtasks = await hierarchical._decompose_task("Write report on AI agents")

            assert isinstance(subtasks, list)
            assert len(subtasks) == 2
            assert subtasks[0]["specialist"] == "researcher"
            assert subtasks[1]["specialist"] == "writer"


class TestHierarchicalSpecialistExecution:
    """Test specialist agent execution."""

    @pytest.mark.asyncio
    async def test_hierarchical_specialists_execute(self):
        """Specialist agents receive and execute their subtasks."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            # Mock coordinator
            mock_coordinator = AsyncMock()
            mock_coordinator.agent_id = "coordinator-123"
            mock_coordinator.call = AsyncMock(return_value=[])  # For decomposition

            # Mock specialists
            mock_researcher = AsyncMock()
            mock_researcher.call = AsyncMock(return_value="Research findings")

            mock_analyst = AsyncMock()
            mock_analyst.call = AsyncMock(return_value="Analysis results")

            # Setup spawn to return coordinator first, then specialists
            async def spawn_side_effect(premise, **kwargs):
                if "coordinate" in premise.lower():
                    return mock_coordinator
                elif "researcher" in premise.lower() or "research" in premise.lower():
                    return mock_researcher
                elif "analyst" in premise.lower() or "analyze" in premise.lower():
                    return mock_analyst
                return AsyncMock()

            mock_spawn.side_effect = spawn_side_effect

            hierarchical = Hierarchical(
                coordinator_premise="Coordinate work.",
                specialist_premises={
                    "researcher": "You research.",
                    "analyst": "You analyze."
                }
            )

            # Execute subtasks
            subtasks = [
                {"specialist": "researcher", "task": "Find data"},
                {"specialist": "analyst", "task": "Analyze data"}
            ]

            results = await hierarchical._execute_subtasks(subtasks)

            assert len(results) == 2
            assert results[0] == "Research findings"
            assert results[1] == "Analysis results"

    @pytest.mark.asyncio
    async def test_hierarchical_specialist_not_found_raises(self):
        """Raises error if subtask references unknown specialist."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            # Mock coordinator properly
            mock_coordinator = AsyncMock()
            mock_coordinator.agent_id = "coordinator-123"

            async def spawn_side_effect(premise, **kwargs):
                if "coordinate" in premise.lower():
                    return mock_coordinator
                return AsyncMock()

            mock_spawn.side_effect = spawn_side_effect

            hierarchical = Hierarchical(
                coordinator_premise="Coordinate.",
                specialist_premises={"researcher": "Research."},
                fail_fast=True  # Ensure errors propagate
            )

            subtasks = [
                {"specialist": "unknown_specialist", "task": "Do something"}
            ]

            with pytest.raises(ValueError, match="unknown_specialist"):
                await hierarchical._execute_subtasks(subtasks)


class TestHierarchicalAggregation:
    """Test aggregation of specialist results."""

    @pytest.mark.asyncio
    async def test_hierarchical_results_aggregated(self):
        """Specialist results are combined using Aggregator."""
        from scripts.agentica.patterns.primitives import Aggregator, AggregateMode

        hierarchical = Hierarchical(
            coordinator_premise="Coordinate.",
            specialist_premises={"worker": "Work."},
            aggregation_mode=AggregateMode.CONCAT,
            aggregation_separator="\n\n"
        )

        results = [
            "Result from specialist 1",
            "Result from specialist 2",
            "Result from specialist 3"
        ]

        aggregated = hierarchical._aggregate_results(results)

        assert "Result from specialist 1" in aggregated
        assert "Result from specialist 2" in aggregated
        assert "Result from specialist 3" in aggregated
        assert "\n\n" in aggregated

    @pytest.mark.asyncio
    async def test_hierarchical_custom_aggregator(self):
        """Can provide custom Aggregator instance."""
        from scripts.agentica.patterns.primitives import Aggregator, AggregateMode

        custom_aggregator = Aggregator(
            mode=AggregateMode.MERGE,
            deduplicate=True
        )

        hierarchical = Hierarchical(
            coordinator_premise="Coordinate.",
            specialist_premises={"worker": "Work."},
            aggregator=custom_aggregator
        )

        assert hierarchical.aggregator is custom_aggregator


class TestHierarchicalSynthesis:
    """Test coordinator's final synthesis."""

    @pytest.mark.asyncio
    async def test_hierarchical_coordinator_synthesizes(self):
        """Coordinator produces final answer from aggregated results."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()

            # First call: decompose task
            # Second call: synthesize results
            mock_coordinator.call = AsyncMock(side_effect=[
                [{"specialist": "worker", "task": "Do work"}],  # Decompose
                "Final synthesized answer"  # Synthesize
            ])

            mock_specialist = AsyncMock()
            mock_specialist.call = AsyncMock(return_value="Specialist result")

            def spawn_side_effect(premise, **kwargs):
                if "coordinator" in premise.lower():
                    return mock_coordinator
                return mock_specialist

            mock_spawn.side_effect = spawn_side_effect

            hierarchical = Hierarchical(
                coordinator_premise="You are a coordinator.",
                specialist_premises={"worker": "You work."}
            )

            result = await hierarchical.execute("Complete this task")

            # Coordinator should be called twice
            assert mock_coordinator.call.call_count == 2

            # Second call should be for synthesis
            second_call_args = mock_coordinator.call.call_args_list[1]
            assert "synthesize" in str(second_call_args).lower() or "combine" in str(second_call_args).lower()

            assert result == "Final synthesized answer"


class TestHierarchicalParallelism:
    """Test parallel execution of specialists."""

    @pytest.mark.asyncio
    async def test_hierarchical_parallel_specialists(self):
        """Specialists run in parallel when possible."""
        import asyncio

        execution_order = []

        async def slow_specialist_1(return_type, task):
            execution_order.append("start_1")
            await asyncio.sleep(0.1)
            execution_order.append("end_1")
            return "Result 1"

        async def slow_specialist_2(return_type, task):
            execution_order.append("start_2")
            await asyncio.sleep(0.1)
            execution_order.append("end_2")
            return "Result 2"

        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            # Mock coordinator
            mock_coordinator = AsyncMock()
            mock_coordinator.agent_id = "coordinator-123"

            mock_spec_1 = AsyncMock()
            mock_spec_1.call = slow_specialist_1

            mock_spec_2 = AsyncMock()
            mock_spec_2.call = slow_specialist_2

            # Return coordinator first, then specialists
            async def spawn_side_effect(premise, **kwargs):
                if "coordinate" in premise.lower():
                    return mock_coordinator
                elif "spec1" in premise.lower() or "specialist 1" in premise.lower():
                    return mock_spec_1
                elif "spec2" in premise.lower() or "specialist 2" in premise.lower():
                    return mock_spec_2
                return AsyncMock()

            mock_spawn.side_effect = spawn_side_effect

            hierarchical = Hierarchical(
                coordinator_premise="Coordinate.",
                specialist_premises={
                    "spec1": "Specialist 1.",
                    "spec2": "Specialist 2."
                }
            )

            subtasks = [
                {"specialist": "spec1", "task": "Task 1"},
                {"specialist": "spec2", "task": "Task 2"}
            ]

            # Should run in parallel
            results = await hierarchical._execute_subtasks(subtasks)

            # Both should start before either finishes (parallel execution)
            assert execution_order.index("start_1") < execution_order.index("end_1")
            assert execution_order.index("start_2") < execution_order.index("end_2")

            # At least one should start before the other ends
            assert (
                execution_order.index("start_2") < execution_order.index("end_1") or
                execution_order.index("start_1") < execution_order.index("end_2")
            )

    @pytest.mark.asyncio
    async def test_hierarchical_parallel_execution_faster(self):
        """Parallel execution is faster than sequential."""
        import asyncio
        import time

        async def slow_task(duration):
            await asyncio.sleep(duration)
            return f"Done after {duration}s"

        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            mock_specialists = []
            for i in range(3):
                mock_spec = AsyncMock()
                mock_spec.call = AsyncMock(side_effect=lambda task, i=i: slow_task(0.1))
                mock_specialists.append(mock_spec)

            mock_spawn.side_effect = mock_specialists

            hierarchical = Hierarchical(
                coordinator_premise="Coordinate.",
                specialist_premises={
                    "spec1": "Spec 1.",
                    "spec2": "Spec 2.",
                    "spec3": "Spec 3."
                }
            )

            subtasks = [
                {"specialist": "spec1", "task": "Task 1"},
                {"specialist": "spec2", "task": "Task 2"},
                {"specialist": "spec3", "task": "Task 3"}
            ]

            start = time.time()
            await hierarchical._execute_subtasks(subtasks)
            duration = time.time() - start

            # Should be ~0.1s (parallel), not ~0.3s (sequential)
            # Allow some overhead
            assert duration < 0.25, f"Expected parallel execution (~0.1s), got {duration:.2f}s"


class TestHierarchicalEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_hierarchical_no_specialists_needed(self):
        """Coordinator can answer directly if task is simple."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            mock_coordinator = AsyncMock()

            # Coordinator decides no specialists needed
            mock_coordinator.call = AsyncMock(side_effect=[
                [],  # Empty subtasks list (no decomposition needed)
                "Direct answer from coordinator"  # Direct response
            ])

            mock_spawn.return_value = mock_coordinator

            hierarchical = Hierarchical(
                coordinator_premise="Answer directly if simple.",
                specialist_premises={"worker": "Work on complex tasks."}
            )

            result = await hierarchical.execute("What is 2+2?")

            # Should get direct answer without specialist involvement
            assert result == "Direct answer from coordinator"

    @pytest.mark.asyncio
    async def test_hierarchical_single_specialist(self):
        """Works correctly with only one specialist."""
        hierarchical = Hierarchical(
            coordinator_premise="Coordinate.",
            specialist_premises={"only_specialist": "Do everything."}
        )

        # specialists dict is empty until spawned (lazy loading)
        assert len(hierarchical.specialist_premises) == 1

        # Should still work end-to-end
        # (will fail until implemented)

    @pytest.mark.asyncio
    async def test_hierarchical_empty_result_handling(self):
        """Handles case where specialist returns empty result."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            # Mock coordinator
            mock_coordinator = AsyncMock()
            mock_coordinator.agent_id = "coordinator-123"

            mock_specialist = AsyncMock()
            mock_specialist.call = AsyncMock(return_value="")

            async def spawn_side_effect(premise, **kwargs):
                if "coordinate" in premise.lower():
                    return mock_coordinator
                return mock_specialist

            mock_spawn.side_effect = spawn_side_effect

            hierarchical = Hierarchical(
                coordinator_premise="Coordinate.",
                specialist_premises={"worker": "Work."}
            )

            subtasks = [{"specialist": "worker", "task": "Do something"}]

            results = await hierarchical._execute_subtasks(subtasks)

            # Empty result should be preserved
            assert results[0] == ""

    @pytest.mark.asyncio
    async def test_hierarchical_specialist_error_handling(self):
        """Handles errors from specialist agents gracefully."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            # Mock coordinator
            mock_coordinator = AsyncMock()
            mock_coordinator.agent_id = "coordinator-123"

            mock_specialist = AsyncMock()
            mock_specialist.call = AsyncMock(side_effect=Exception("Specialist failed"))

            async def spawn_side_effect(premise, **kwargs):
                if "coordinate" in premise.lower():
                    return mock_coordinator
                return mock_specialist

            mock_spawn.side_effect = spawn_side_effect

            hierarchical = Hierarchical(
                coordinator_premise="Coordinate.",
                specialist_premises={"worker": "Work."},
                fail_fast=True
            )

            subtasks = [{"specialist": "worker", "task": "Do something"}]

            # Should propagate error when fail_fast=True
            with pytest.raises(Exception, match="Specialist failed"):
                await hierarchical._execute_subtasks(subtasks)

    @pytest.mark.asyncio
    async def test_hierarchical_partial_failure_continue(self):
        """Can continue with partial results if fail_fast=False."""
        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn:
            # Mock coordinator
            mock_coordinator = AsyncMock()
            mock_coordinator.agent_id = "coordinator-123"

            mock_success = AsyncMock()
            mock_success.call = AsyncMock(return_value="Success")

            mock_failure = AsyncMock()
            mock_failure.call = AsyncMock(side_effect=Exception("Failed"))

            async def spawn_side_effect(premise, **kwargs):
                if "coordinate" in premise.lower():
                    return mock_coordinator
                elif "spec 2" in premise.lower():
                    return mock_failure
                else:
                    return mock_success

            mock_spawn.side_effect = spawn_side_effect

            hierarchical = Hierarchical(
                coordinator_premise="Coordinate.",
                specialist_premises={
                    "spec1": "Spec 1.",
                    "spec2": "Spec 2.",
                    "spec3": "Spec 3."
                },
                fail_fast=False
            )

            subtasks = [
                {"specialist": "spec1", "task": "Task 1"},
                {"specialist": "spec2", "task": "Task 2"},
                {"specialist": "spec3", "task": "Task 3"}
            ]

            results = await hierarchical._execute_subtasks(subtasks)

            # Should get results from successful specialists
            # Failed specialist should return None or error marker
            assert results[0] == "Success"
            assert results[2] == "Success"
            # results[1] should indicate failure somehow


class TestHierarchicalConfiguration:
    """Test configuration options."""

    @pytest.mark.asyncio
    async def test_hierarchical_with_model_selection(self):
        """Can specify different models for coordinator and specialists."""
        hierarchical = Hierarchical(
            coordinator_premise="Coordinate with advanced model.",
            coordinator_model="anthropic:claude-opus-4.5",
            specialist_premises={"worker": "Work with fast model."},
            specialist_model="openai:gpt-4o"
        )

        assert hierarchical.coordinator_model == "anthropic:claude-opus-4.5"
        assert hierarchical.specialist_model == "openai:gpt-4o"

    @pytest.mark.asyncio
    async def test_hierarchical_return_type_specification(self):
        """Can specify return type for final result."""
        hierarchical = Hierarchical(
            coordinator_premise="Coordinate.",
            specialist_premises={"worker": "Work."},
            return_type=dict
        )

        # Final synthesis should use specified return type
        assert hierarchical.return_type == dict


class TestHierarchicalTaskGroupBehavior:
    """Test TaskGroup-based fail-fast behavior in subtask execution (Python 3.11+)."""

    @pytest.mark.asyncio
    async def test_fail_fast_cancels_specialists(self):
        """Fail-fast mode should cancel slow specialists on first failure.

        Pattern: Fail-fast cancellation via TaskGroup
        Expected: First specialist failure cancels remaining specialist tasks
        """
        import asyncio
        from scripts.agentica.patterns import Hierarchical

        executed = []
        spawn_count = [0]

        async def create_agent(**kwargs):
            agent = AsyncMock()
            premise = kwargs.get('premise', '')
            idx = spawn_count[0]
            spawn_count[0] += 1

            # Required by Hierarchical for coordinator_id
            agent.agent_id = f"agent_{idx}"

            async def call_impl(return_type, prompt):
                # Coordinator returns subtasks
                if "Coordinate" in premise:
                    return [
                        {"specialist": "fast", "task": "Do fast"},
                        {"specialist": "slow", "task": "Do slow"}
                    ]
                # Fast specialist fails
                if "Fast" in premise:
                    executed.append("fast")
                    raise ValueError("Fast failed")
                # Slow specialist
                await asyncio.sleep(1)
                executed.append("slow")
                return "slow result"

            agent.call = call_impl
            return agent

        with patch("scripts.agentica.patterns.hierarchical.spawn", create_agent):
            h = Hierarchical(
                coordinator_premise="Coordinate.",
                specialist_premises={"fast": "Fast work", "slow": "Slow work"},
                fail_fast=True
            )

            with pytest.raises(ValueError, match="Fast failed"):
                await h.execute("Test task")

            # Slow specialist should have been cancelled
            assert "slow" not in executed
