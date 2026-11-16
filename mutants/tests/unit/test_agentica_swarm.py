"""Tests for Agentica Swarm pattern (TDD - tests written first).

The Swarm pattern:
- Spawns multiple agents in parallel to attack a problem from different angles
- Each agent gets a different premise/perspective
- Results are aggregated using the Aggregator primitive
- Uses asyncio.gather() for parallel execution
- Default aggregation mode: MERGE

Reference: scripts/agentica/PATTERNS.md - Pattern #2
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scripts.agentica.patterns import Swarm, AggregateMode

# Check if agentica is available for integration tests
try:
    from agentica import spawn
    HAS_AGENTICA = True
except ImportError:
    HAS_AGENTICA = False


class TestSwarmParallelExecution:
    """Test that swarm runs agents in parallel."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_AGENTICA, reason="agentica not installed")
    async def test_swarm_parallel_execution(self):
        """3 agents run in parallel, results aggregated."""
        # Create swarm with 3 different perspectives
        swarm = Swarm(
            perspectives=[
                "You are a security expert. Focus on security implications.",
                "You are a performance engineer. Focus on scalability.",
                "You are a UX designer. Focus on user experience."
            ]
        )

        # Ask the swarm to analyze a feature
        result = await swarm.execute("Analyze implementing OAuth login")

        # Should return aggregated insights from all 3 agents
        assert result is not None
        assert isinstance(result, dict)  # MERGE mode returns dict by default

    @pytest.mark.asyncio
    async def test_swarm_uses_asyncio_gather(self):
        """Swarm should use asyncio.gather for parallel execution."""
        swarm = Swarm(
            perspectives=[
                "Perspective A",
                "Perspective B",
                "Perspective C"
            ]
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            # Mock spawn to return mock agents
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(side_effect=[
                {"insight": "A"},
                {"insight": "B"},
                {"insight": "C"}
            ])
            mock_spawn.return_value = mock_agent

            result = await swarm.execute("Test query")

            # Verify all 3 agents were spawned (for parallel execution)
            assert mock_spawn.call_count == 3
            assert result is not None

    @pytest.mark.asyncio
    async def test_swarm_spawns_correct_number_of_agents(self):
        """Swarm should spawn one agent per perspective."""
        perspectives = [
            "Expert 1",
            "Expert 2",
            "Expert 3",
            "Expert 4",
            "Expert 5"
        ]
        swarm = Swarm(perspectives=perspectives)

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            # Mock spawn to return fake agents
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"result": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Test query")

            # Should spawn exactly 5 agents (one per perspective)
            assert mock_spawn.call_count == 5


class TestSwarmPremises:
    """Test that each agent gets a different premise."""

    @pytest.mark.asyncio
    async def test_swarm_with_different_premises(self):
        """Each agent gets different premise/angle."""
        perspectives = [
            "You are optimistic. Focus on benefits.",
            "You are pessimistic. Focus on risks.",
            "You are pragmatic. Focus on implementation."
        ]
        swarm = Swarm(perspectives=perspectives)

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"insight": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Evaluate new feature")

            # Verify each spawn call got a different premise
            calls = mock_spawn.call_args_list
            assert len(calls) == 3

            # Extract premises from spawn calls
            premises = [call.kwargs.get('premise') or call.args[0] for call in calls]
            assert perspectives[0] in premises[0]
            assert perspectives[1] in premises[1]
            assert perspectives[2] in premises[2]

    @pytest.mark.asyncio
    async def test_swarm_custom_model_propagates(self):
        """Custom model setting should propagate to all spawned agents."""
        swarm = Swarm(
            perspectives=["Expert A", "Expert B"],
            model="anthropic:claude-opus-4.5"
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"result": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Test")

            # Both agents should use the custom model
            for call in mock_spawn.call_args_list:
                assert call.kwargs.get('model') == "anthropic:claude-opus-4.5"


class TestSwarmAggregation:
    """Test aggregation of results from swarm agents."""

    @pytest.mark.asyncio
    async def test_swarm_aggregation_mode_merge_default(self):
        """Swarm uses MERGE mode by default."""
        swarm = Swarm(perspectives=["A", "B", "C"])

        # Default aggregator should be MERGE mode
        assert swarm.aggregator.mode == AggregateMode.MERGE

    @pytest.mark.asyncio
    async def test_swarm_custom_aggregator_concat(self):
        """Can override aggregation mode to CONCAT."""
        swarm = Swarm(
            perspectives=["A", "B"],
            aggregate_mode=AggregateMode.CONCAT
        )

        assert swarm.aggregator.mode == AggregateMode.CONCAT

    @pytest.mark.asyncio
    async def test_swarm_custom_aggregator_best(self):
        """Can override aggregation mode to BEST."""
        swarm = Swarm(
            perspectives=["A", "B"],
            aggregate_mode=AggregateMode.BEST
        )

        assert swarm.aggregator.mode == AggregateMode.BEST

    @pytest.mark.asyncio
    async def test_swarm_aggregates_results(self):
        """Swarm should aggregate all agent results."""
        swarm = Swarm(
            perspectives=["A", "B", "C"],
            aggregate_mode=AggregateMode.MERGE
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            # Mock agents to return different results
            mock_agents = []
            for i, result in enumerate([
                {"key1": "value1"},
                {"key2": "value2"},
                {"key3": "value3"}
            ]):
                agent = AsyncMock()
                agent.call = AsyncMock(return_value=result)
                mock_agents.append(agent)

            mock_spawn.side_effect = mock_agents

            result = await swarm.execute("Test query")

            # MERGE mode should combine all dicts
            assert result == {"key1": "value1", "key2": "value2", "key3": "value3"}


class TestSwarmErrorHandling:
    """Test error handling in swarm execution."""

    @pytest.mark.asyncio
    async def test_swarm_handles_agent_failure(self):
        """If one agent fails, others continue and partial results returned."""
        swarm = Swarm(
            perspectives=["A", "B", "C"],
            fail_fast=False  # Don't stop on first error
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            # First agent succeeds, second fails, third succeeds
            agent1 = AsyncMock()
            agent1.call = AsyncMock(return_value={"result": "A"})

            agent2 = AsyncMock()
            agent2.call = AsyncMock(side_effect=Exception("Agent B failed"))

            agent3 = AsyncMock()
            agent3.call = AsyncMock(return_value={"result": "C"})

            mock_spawn.side_effect = [agent1, agent2, agent3]

            result = await swarm.execute("Test query")

            # Should aggregate results from agents that succeeded
            # (exact behavior depends on implementation - could filter None or raise)
            # Test documents expected behavior: continue on failure
            assert result is not None

    @pytest.mark.asyncio
    async def test_swarm_fail_fast_mode(self):
        """In fail_fast mode, first error should stop execution."""
        swarm = Swarm(
            perspectives=["A", "B", "C"],
            fail_fast=True
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            agent1 = AsyncMock()
            agent1.call = AsyncMock(return_value={"result": "A"})

            agent2 = AsyncMock()
            agent2.call = AsyncMock(side_effect=ValueError("Agent B failed"))

            agent3 = AsyncMock()
            agent3.call = AsyncMock(return_value={"result": "C"})

            mock_spawn.side_effect = [agent1, agent2, agent3]

            # Should raise the error from agent2
            with pytest.raises(ValueError, match="Agent B failed"):
                await swarm.execute("Test query")

    @pytest.mark.asyncio
    async def test_swarm_empty_perspectives_raises(self):
        """No perspectives specified raises ValueError."""
        with pytest.raises(ValueError, match="perspectives.*empty"):
            Swarm(perspectives=[])

    @pytest.mark.asyncio
    async def test_swarm_none_perspectives_raises(self):
        """None as perspectives raises ValueError."""
        with pytest.raises(ValueError, match="perspectives"):
            Swarm(perspectives=None)

    @pytest.mark.asyncio
    async def test_swarm_single_perspective_allowed(self):
        """Single perspective is allowed (degenerates to single agent)."""
        swarm = Swarm(perspectives=["Single expert"])

        # Should not raise
        assert len(swarm.perspectives) == 1


class TestSwarmReturnTypes:
    """Test return type handling in swarm."""

    @pytest.mark.asyncio
    async def test_swarm_respects_return_type(self):
        """Swarm should pass return type to agent.call()."""
        swarm = Swarm(perspectives=["A", "B"])

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"key": "value"})
            mock_spawn.return_value = mock_agent

            # Execute with explicit return type
            result = await swarm.execute("Test", return_type=dict)

            # Verify agents were called with the return type
            for call in mock_agent.call.call_args_list:
                # First arg should be return type (dict in this case)
                assert call.args[0] == dict

    @pytest.mark.asyncio
    async def test_swarm_default_return_type(self):
        """Default return type should be str or dict based on aggregate mode."""
        swarm_merge = Swarm(
            perspectives=["A", "B"],
            aggregate_mode=AggregateMode.MERGE
        )

        swarm_concat = Swarm(
            perspectives=["A", "B"],
            aggregate_mode=AggregateMode.CONCAT
        )

        # MERGE mode → dict return type default
        # CONCAT mode → str return type default
        # (test documents the expected contract)
        assert swarm_merge.default_return_type == dict
        assert swarm_concat.default_return_type == str


class TestSwarmScope:
    """Test tool/scope passing to swarm agents."""

    @pytest.mark.asyncio
    async def test_swarm_with_shared_scope(self):
        """Tools/scope should be available to all swarm agents."""
        def shared_tool(x: str) -> str:
            return f"Processed: {x}"

        swarm = Swarm(
            perspectives=["A", "B"],
            scope={"process": shared_tool}
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"result": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Test")

            # All spawned agents should receive the scope
            for call in mock_spawn.call_args_list:
                assert "scope" in call.kwargs
                assert "process" in call.kwargs["scope"]


class TestSwarmEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_swarm_with_duplicate_perspectives(self):
        """Duplicate perspectives are allowed (different agent instances)."""
        swarm = Swarm(
            perspectives=[
                "Same perspective",
                "Same perspective",
                "Same perspective"
            ]
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"result": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Test")

            # Should spawn 3 separate agents even with same premise
            assert mock_spawn.call_count == 3

    @pytest.mark.asyncio
    async def test_swarm_preserves_execution_order(self):
        """Results should be aggregated in perspective order."""
        swarm = Swarm(
            perspectives=["First", "Second", "Third"],
            aggregate_mode=AggregateMode.MERGE
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            # Return results in order
            agents = []
            for i in range(3):
                agent = AsyncMock()
                agent.call = AsyncMock(return_value={f"key{i}": f"value{i}"})
                agents.append(agent)

            mock_spawn.side_effect = agents

            result = await swarm.execute("Test")

            # Keys should appear in order (if MERGE preserves order)
            # This documents expected behavior
            assert list(result.keys()) == ["key0", "key1", "key2"]

    @pytest.mark.asyncio
    async def test_swarm_with_mcp_config(self):
        """Swarm can pass MCP config to all agents."""
        swarm = Swarm(
            perspectives=["A", "B"],
            mcp="path/to/mcp_config.json"
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"result": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Test")

            # All spawned agents should receive MCP config
            for call in mock_spawn.call_args_list:
                assert call.kwargs.get('mcp') == "path/to/mcp_config.json"


class TestSwarmTaskGroupBehavior:
    """Test TaskGroup-based fail-fast behavior (Python 3.11+)."""

    @pytest.mark.asyncio
    async def test_fail_fast_cancels_remaining(self):
        """Fail-fast mode should cancel slow agents on first failure.

        Pattern: Fail-fast cancellation via TaskGroup
        Expected: First failure cancels remaining agent tasks
        """
        import asyncio
        executed = []

        swarm = Swarm(
            perspectives=["Fast", "Slow"],
            fail_fast=True
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            call_count = [0]

            async def create_agent(**kwargs):
                agent = AsyncMock()
                premise = kwargs.get('premise', '')
                idx = call_count[0]
                call_count[0] += 1

                async def call_impl(return_type, query):
                    if 'Fast' in premise:
                        executed.append("fast")
                        raise ValueError("Fast failed")
                    await asyncio.sleep(1)
                    executed.append("slow")
                    return {"result": "slow"}

                agent.call = call_impl
                return agent

            mock_spawn.side_effect = create_agent

            with pytest.raises(ValueError, match="Fast failed"):
                await swarm.execute("Test")

            # Slow agent should have been cancelled
            assert "slow" not in executed

    @pytest.mark.asyncio
    async def test_non_fail_fast_executes_all(self):
        """Non-fail-fast mode should let all agents complete.

        Pattern: Partial results mode uses gather with return_exceptions
        Expected: All agents execute even when some fail
        """
        executed = []

        swarm = Swarm(
            perspectives=["A", "B", "C"],
            fail_fast=False
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            idx = [0]

            async def create_agent(**kwargs):
                agent = AsyncMock()
                i = idx[0]
                idx[0] += 1

                async def call_impl(return_type, query):
                    executed.append(f"agent_{i}")
                    if i == 1:
                        raise ValueError(f"Agent {i} failed")
                    return {"result": f"agent_{i}"}

                agent.call = call_impl
                return agent

            mock_spawn.side_effect = create_agent

            result = await swarm.execute("Test")

            # All three should have executed
            assert len(executed) == 3
            # Result should have 2 successful results merged
            assert result is not None

    @pytest.mark.asyncio
    async def test_swarm_non_fail_fast_collects_exceptions(self):
        """Non-fail-fast mode should collect exceptions, not raise on first.

        Pattern: Bug fix for return_exceptions=False issue
        Expected: All agents complete, failures filtered to None
        """
        swarm = Swarm(
            perspectives=["A", "B", "C"],
            fail_fast=False
        )

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            # All three agents fail with different exceptions
            agents = []
            for i, exc in enumerate([
                ValueError("A failed"),
                TypeError("B failed"),
                RuntimeError("C failed")
            ]):
                agent = AsyncMock()
                agent.call = AsyncMock(side_effect=exc)
                agents.append(agent)

            mock_spawn.side_effect = agents

            # Should NOT raise - aggregator handles empty list
            try:
                result = await swarm.execute("Test query")
                # If aggregator raises on empty list, that's expected
                # The key is we don't raise A failed, B failed, or C failed
                assert True
            except ValueError as e:
                # Aggregator may raise for empty results
                assert "empty" in str(e).lower() or "results" in str(e).lower()
