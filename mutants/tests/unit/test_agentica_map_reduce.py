"""
Tests for MapReduce pattern.

TDD: Write tests first, watch them fail, implement minimally.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestMapReducePattern:
    """Tests for the MapReduce pattern."""

    @pytest.fixture
    def mock_spawn(self):
        """Create a mock spawn function that returns mock agents."""
        async def _spawn(**kwargs):
            agent = MagicMock()
            agent.call = AsyncMock()
            # Store premise for inspection
            agent._premise = kwargs.get("premise", "")
            return agent
        return _spawn

    @pytest.mark.asyncio
    async def test_map_phase_distributes_work_correctly(self, mock_spawn):
        """Test that map phase spawns N mappers and gives each a chunk."""
        from scripts.agentica.patterns import MapReduce

        with patch("scripts.agentica.patterns.map_reduce.spawn", mock_spawn):
            mr = MapReduce(
                mapper_premise="You analyze one section.",
                reducer_premise="You combine results.",
                num_mappers=3
            )

            chunks = ["chunk1", "chunk2", "chunk3"]

            # Mock mapper results
            mapper_results = ["result1", "result2", "result3"]

            with patch.object(mr, '_map_phase', new_callable=AsyncMock) as mock_map:
                mock_map.return_value = mapper_results
                with patch.object(mr, '_reduce_phase', new_callable=AsyncMock) as mock_reduce:
                    mock_reduce.return_value = "combined"

                    result = await mr.execute("Analyze this", chunks=chunks)

                    # Map phase should be called with chunks
                    mock_map.assert_called_once()
                    call_args = mock_map.call_args
                    assert call_args[1]["chunks"] == chunks

    @pytest.mark.asyncio
    async def test_reduce_phase_receives_all_mapper_outputs(self, mock_spawn):
        """Test that reducer receives all mapper outputs."""
        from scripts.agentica.patterns import MapReduce

        with patch("scripts.agentica.patterns.map_reduce.spawn", mock_spawn):
            mr = MapReduce(
                mapper_premise="You analyze one section.",
                reducer_premise="You combine results.",
                num_mappers=3
            )

            # Set up mappers to return specific results
            mapper_results = ["analysis1", "analysis2", "analysis3"]

            with patch.object(mr, '_map_phase', new_callable=AsyncMock) as mock_map:
                mock_map.return_value = mapper_results
                with patch.object(mr, '_reduce_phase', new_callable=AsyncMock) as mock_reduce:
                    mock_reduce.return_value = "combined"

                    await mr.execute("Analyze this", chunks=["a", "b", "c"])

                    # Reduce should receive all mapper outputs
                    mock_reduce.assert_called_once()
                    call_args = mock_reduce.call_args
                    assert call_args[1]["mapper_outputs"] == mapper_results

    @pytest.mark.asyncio
    async def test_handles_mapper_failures_gracefully(self, mock_spawn):
        """Test that MapReduce continues when some mappers fail."""
        from scripts.agentica.patterns import MapReduce

        call_count = 0

        async def failing_spawn(**kwargs):
            nonlocal call_count
            agent = MagicMock()
            call_count += 1
            if call_count == 2:
                # Second mapper fails
                agent.call = AsyncMock(side_effect=Exception("Mapper failed"))
            else:
                agent.call = AsyncMock(return_value=f"result{call_count}")
            agent._premise = kwargs.get("premise", "")
            return agent

        with patch("scripts.agentica.patterns.map_reduce.spawn", failing_spawn):
            mr = MapReduce(
                mapper_premise="You analyze one section.",
                reducer_premise="You combine results.",
                num_mappers=3,
                fail_fast=False  # Continue on failure
            )

            # We need to set up the reducer to handle partial results
            reducer_agent = MagicMock()
            reducer_agent.call = AsyncMock(return_value="combined from partial")

            # Run with actual implementation (once we build it)
            # For now, this test will fail since MapReduce doesn't exist
            chunks = ["chunk1", "chunk2", "chunk3"]

            # The test expects that with 3 mappers, 1 failing,
            # we still get results from 2 mappers passed to reducer
            result = await mr.execute("Analyze this", chunks=chunks)

            # Should not raise, should return something
            assert result is not None

    @pytest.mark.asyncio
    async def test_with_different_numbers_of_mappers(self, mock_spawn):
        """Test MapReduce with different numbers of mappers."""
        from scripts.agentica.patterns import MapReduce

        for num_mappers in [1, 2, 5]:
            spawn_count = 0

            async def counting_spawn(**kwargs):
                nonlocal spawn_count
                spawn_count += 1
                agent = MagicMock()
                agent.call = AsyncMock(return_value=f"result{spawn_count}")
                agent._premise = kwargs.get("premise", "")
                return agent

            with patch("scripts.agentica.patterns.map_reduce.spawn", counting_spawn):
                spawn_count = 0  # Reset
                mr = MapReduce(
                    mapper_premise="You analyze one section.",
                    reducer_premise="You combine results.",
                    num_mappers=num_mappers
                )

                chunks = [f"chunk{i}" for i in range(num_mappers)]
                result = await mr.execute("Analyze this", chunks=chunks)

                # Should have spawned num_mappers + 1 (for reducer)
                assert spawn_count == num_mappers + 1

    @pytest.mark.asyncio
    async def test_mapreduce_init_validates_parameters(self):
        """Test that MapReduce validates init parameters."""
        from scripts.agentica.patterns import MapReduce

        # num_mappers must be positive
        with pytest.raises(ValueError, match="num_mappers must be at least 1"):
            MapReduce(
                mapper_premise="mapper",
                reducer_premise="reducer",
                num_mappers=0
            )

    @pytest.mark.asyncio
    async def test_execute_with_more_chunks_than_mappers(self, mock_spawn):
        """Test that chunks are distributed when there are more chunks than mappers."""
        from scripts.agentica.patterns import MapReduce

        with patch("scripts.agentica.patterns.map_reduce.spawn", mock_spawn):
            mr = MapReduce(
                mapper_premise="You analyze one section.",
                reducer_premise="You combine results.",
                num_mappers=2
            )

            # More chunks than mappers
            chunks = ["chunk1", "chunk2", "chunk3", "chunk4"]

            # Should still work, distributing chunks across mappers
            result = await mr.execute("Analyze this", chunks=chunks)
            assert result is not None

    @pytest.mark.asyncio
    async def test_coordination_db_integration(self, mock_spawn):
        """Test that MapReduce integrates with CoordinationDB for tracking."""
        from scripts.agentica.patterns import MapReduce
        from scripts.agentica.coordination import CoordinationDB

        mock_db = MagicMock(spec=CoordinationDB)

        with patch("scripts.agentica.patterns.map_reduce.spawn", mock_spawn):
            with patch("scripts.agentica.tracked_agent.tracked_spawn", mock_spawn) as mock_tracked:
                mr = MapReduce(
                    mapper_premise="You analyze one section.",
                    reducer_premise="You combine results.",
                    num_mappers=2,
                    db=mock_db
                )

                chunks = ["chunk1", "chunk2"]
                result = await mr.execute("Analyze this", chunks=chunks)

                # tracked_spawn should have been called (or spawn if no db)
                # The actual check depends on implementation
                assert result is not None


class TestMapReduceTaskGroupBehavior:
    """Test TaskGroup-based fail-fast behavior in map phase (Python 3.11+)."""

    @pytest.mark.asyncio
    async def test_fail_fast_cancels_mappers(self):
        """Fail-fast mode should cancel slow mappers on first failure.

        Pattern: Fail-fast cancellation via TaskGroup
        Expected: First mapper failure cancels remaining mapper tasks
        """
        from scripts.agentica.patterns import MapReduce

        executed = []
        call_count = [0]

        async def create_agent(**kwargs):
            agent = MagicMock()
            role = kwargs.get('env', {}).get('AGENT_ROLE', 'unknown')
            idx = call_count[0]
            call_count[0] += 1

            async def call_impl(return_type, prompt):
                if role == 'mapper':
                    if idx == 0:
                        executed.append("fast_mapper")
                        raise ValueError("Mapper 0 failed")
                    await asyncio.sleep(1)
                    executed.append("slow_mapper")
                    return "slow result"
                # Reducer
                return "reduced"

            agent.call = call_impl
            agent._premise = kwargs.get('premise', '')
            return agent

        with patch("scripts.agentica.patterns.map_reduce.spawn", create_agent):
            mr = MapReduce(
                mapper_premise="Map",
                reducer_premise="Reduce",
                num_mappers=2,
                fail_fast=True
            )

            with pytest.raises(ValueError, match="Mapper 0 failed"):
                await mr.execute("Test", chunks=["a", "b"])

            # Slow mapper should have been cancelled
            assert "slow_mapper" not in executed
