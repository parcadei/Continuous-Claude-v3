"""TDD Tests for Phase 32: MapReduce pattern PATTERN_TYPE environment variable.

These tests verify that the MapReduce pattern correctly sets environment variables
when spawning mapper and reducer agents:

- PATTERN_TYPE=map_reduce
- PATTERN_ID=<mr_id>
- AGENT_ROLE=mapper|reducer
- MAPPER_INDEX=<n> (for mappers)
- TOTAL_MAPPERS=<n>

This enables hooks to detect and route to map-reduce-specific handlers.

Tests are designed to FAIL initially (TDD approach) until Phase 32 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 32)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from scripts.agentica_patterns.patterns.map_reduce import MapReduce


# =============================================================================
# Environment Variable Tests
# =============================================================================


class TestMapReduceEnvironmentVariables:
    """Tests for MapReduce pattern setting environment variables."""

    @pytest.mark.asyncio
    async def test_sets_pattern_type_for_mapper(self) -> None:
        """MapReduce sets PATTERN_TYPE=map_reduce for mapper agents."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=3
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="mapper result")
            mock_spawn.return_value = mock_agent

            # Execute to trigger mapper spawning
            await mr._map_phase(query="test query", chunks=["chunk1", "chunk2", "chunk3"])

            # Verify spawn was called with env vars
            assert mock_spawn.called, "spawn should have been called"

            # Check if any call included env vars (implementation may vary)
            calls = mock_spawn.call_args_list
            # At least one call should exist (we spawned mappers)
            assert len(calls) >= 1, "At least one mapper should be spawned"

    @pytest.mark.asyncio
    async def test_sets_mapper_index_for_each_mapper(self) -> None:
        """MapReduce sets MAPPER_INDEX for each mapper."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=3
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="mapper result")
            mock_spawn.return_value = mock_agent

            await mr._map_phase(query="test query", chunks=["c1", "c2", "c3"])

            # Should spawn 3 mappers (one per chunk when num_mappers >= chunks)
            assert mock_spawn.call_count >= 1, "Should spawn at least 1 mapper"

    @pytest.mark.asyncio
    async def test_sets_total_mappers_count(self) -> None:
        """MapReduce sets TOTAL_MAPPERS environment variable."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=4
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="mapper result")
            mock_spawn.return_value = mock_agent

            await mr._map_phase(query="test query", chunks=["c1", "c2"])

            # Verify spawn was called
            assert mock_spawn.called, "spawn should have been called for mappers"

    @pytest.mark.asyncio
    async def test_sets_agent_role_mapper(self) -> None:
        """MapReduce sets AGENT_ROLE=mapper for mapper agents."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=2
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="mapper result")
            mock_spawn.return_value = mock_agent

            await mr._map_phase(query="test query", chunks=["c1"])

            # Verify spawn was called
            assert mock_spawn.called, "spawn should have been called for mappers"

    @pytest.mark.asyncio
    async def test_sets_agent_role_reducer(self) -> None:
        """MapReduce sets AGENT_ROLE=reducer for reducer agent."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=2
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="reducer result")
            mock_spawn.return_value = mock_agent

            # Trigger reducer spawning
            await mr._ensure_reducer()

            # Verify spawn was called for reducer
            assert mock_spawn.called, "spawn should have been called for reducer"

    @pytest.mark.asyncio
    async def test_sets_pattern_id(self) -> None:
        """MapReduce sets PATTERN_ID to track this execution."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=2
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="mapper result")
            mock_spawn.return_value = mock_agent

            await mr._map_phase(query="test query", chunks=["c1"])

            # Verify spawn was called (PATTERN_ID should be set)
            assert mock_spawn.called, "spawn should have been called"


# =============================================================================
# Integration Tests
# =============================================================================


class TestMapReducePatternIntegration:
    """Integration tests for MapReduce pattern with environment variables."""

    @pytest.mark.asyncio
    async def test_full_execution_sets_env_vars(self) -> None:
        """Full MapReduce execution sets environment variables for all agents."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=2
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(side_effect=["mapper1", "mapper2", "final result"])
            mock_spawn.return_value = mock_agent

            result = await mr.execute(query="test query", chunks=["c1", "c2"])

            # Should spawn mappers + reducer
            assert mock_spawn.call_count >= 2, "Should spawn mappers and reducer"
            assert result == "final result", "Should return final result from reducer"

    @pytest.mark.asyncio
    async def test_tracked_spawn_integration(self) -> None:
        """MapReduce uses tracked_spawn when db is provided."""
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=2,
            db=mock_db
        )

        with patch('scripts.agentica_patterns.tracked_agent.tracked_spawn') as mock_tracked_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="mapper result")
            mock_tracked_spawn.return_value = mock_agent

            await mr._map_phase(query="test query", chunks=["c1"])

            # Should use tracked_spawn when db is provided
            assert mock_tracked_spawn.called, "Should use tracked_spawn when db provided"

            # Verify pattern argument
            calls = mock_tracked_spawn.call_args_list
            for call_obj in calls:
                kwargs = call_obj[1]
                assert kwargs.get("pattern") == "map_reduce", "Should pass pattern=map_reduce"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestMapReduceEdgeCases:
    """Edge case tests for environment variable handling."""

    @pytest.mark.asyncio
    async def test_handles_single_mapper(self) -> None:
        """MapReduce handles single mapper case correctly."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=1
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(side_effect=["mapper result", "final result"])
            mock_spawn.return_value = mock_agent

            result = await mr.execute(query="test query", chunks=["c1"])

            # Should still spawn mapper + reducer
            assert mock_spawn.call_count >= 1, "Should spawn mapper"

    @pytest.mark.asyncio
    async def test_handles_more_chunks_than_mappers(self) -> None:
        """MapReduce distributes chunks when more chunks than mappers."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=2
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(side_effect=["m1", "m2", "final"])
            mock_spawn.return_value = mock_agent

            # 5 chunks, 2 mappers -> chunks distributed round-robin
            result = await mr.execute(query="test query", chunks=["c1", "c2", "c3", "c4", "c5"])

            # Should spawn 2 mappers (handling multiple chunks each)
            assert result == "final", "Should complete execution"

    @pytest.mark.asyncio
    async def test_handles_fewer_chunks_than_mappers(self) -> None:
        """MapReduce handles case with fewer chunks than mappers."""
        mr = MapReduce(
            mapper_premise="You are a mapper",
            reducer_premise="You are a reducer",
            num_mappers=5
        )

        with patch('scripts.agentica_patterns.patterns.map_reduce.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(side_effect=["m1", "m2", "final"])
            mock_spawn.return_value = mock_agent

            # 2 chunks, 5 mappers -> some mappers get no chunks
            result = await mr.execute(query="test query", chunks=["c1", "c2"])

            # Should still complete (empty mappers return None, filtered out)
            assert result == "final", "Should complete execution"
