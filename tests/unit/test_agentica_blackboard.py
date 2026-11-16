"""
Tests for Blackboard pattern.

Tests TDD-style:
1. Test specialists can read/write to blackboard
2. Test iteration continues until controller approves
3. Test max_iterations stops infinite loops
4. Test state history is preserved
"""

import pytest
from unittest.mock import AsyncMock, patch

from scripts.agentica_patterns.patterns import Blackboard, Specialist, BlackboardState


class TestBlackboard:
    """Tests for the Blackboard pattern."""

    @pytest.fixture
    def mock_spawn(self):
        """Create mock spawn function."""
        with patch("scripts.agentica_patterns.patterns.blackboard.spawn") as mock:
            yield mock

    def test_specialist_can_write_to_blackboard_keys(self):
        """Test that Specialist defines which keys it writes to."""
        spec = Specialist(
            premise="You analyze requirements.",
            writes_to=["requirements"]
        )

        assert spec.premise == "You analyze requirements."
        assert spec.writes_to == ["requirements"]
        assert spec.reads_from == []  # Default empty

    def test_specialist_can_read_from_blackboard_keys(self):
        """Test that Specialist defines which keys it reads from."""
        spec = Specialist(
            premise="You design architecture.",
            writes_to=["architecture"],
            reads_from=["requirements"]
        )

        assert spec.writes_to == ["architecture"]
        assert spec.reads_from == ["requirements"]

    def test_blackboard_state_stores_values(self):
        """Test that BlackboardState can store and retrieve values."""
        state = BlackboardState()
        state["requirements"] = "User auth needed"

        assert state["requirements"] == "User auth needed"

    def test_blackboard_state_tracks_history(self):
        """Test that BlackboardState preserves history of changes."""
        state = BlackboardState()
        state["requirements"] = "Initial"
        state["requirements"] = "Updated"

        # History should have both values
        assert len(state.history) >= 2
        assert any("Initial" in str(h) for h in state.history)

    @pytest.mark.asyncio
    async def test_specialists_write_to_blackboard(self, mock_spawn):
        """Test that specialists can write to the blackboard."""
        # Mock specialist agent that writes to blackboard
        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()

            async def mock_call(return_type, prompt, **kw):
                # Simulate writing to blackboard keys
                return {"requirements": "User needs login system"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze requirements.", writes_to=["requirements"]),
            ],
            controller_premise="You check if design is complete.",
            max_iterations=1
        )

        result = await bb.solve("Build auth system")

        # Blackboard should have the written key
        assert "requirements" in result.state

    @pytest.mark.asyncio
    async def test_iteration_continues_until_controller_approves(self, mock_spawn):
        """Test that solve() iterates until controller says done."""
        iteration_count = {"value": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "check" in premise.lower():
                    # Controller: approve after 2 iterations
                    iteration_count["value"] += 1
                    if iteration_count["value"] >= 2:
                        return {"complete": True}
                    return {"complete": False}
                else:
                    # Specialist
                    return {"output": f"iteration {iteration_count['value']}"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze.", writes_to=["analysis"]),
            ],
            controller_premise="You check if complete.",
            max_iterations=10
        )

        result = await bb.solve("Build something")

        # Should have iterated at least twice
        assert iteration_count["value"] >= 2

    @pytest.mark.asyncio
    async def test_max_iterations_stops_infinite_loops(self, mock_spawn):
        """Test that max_iterations prevents infinite loops."""
        iteration_count = {"value": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                iteration_count["value"] += 1
                if "check" in premise.lower():
                    # Controller never approves
                    return {"complete": False}
                else:
                    return {"output": "some work"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze.", writes_to=["analysis"]),
            ],
            controller_premise="You check if complete.",
            max_iterations=3
        )

        result = await bb.solve("Build something")

        # Should have stopped after max_iterations
        # Each iteration = 1 specialist call + 1 controller call = 2 calls
        # 3 iterations = at most 6 calls (could be less if we stop after controller)
        assert iteration_count["value"] <= 6

    @pytest.mark.asyncio
    async def test_state_history_is_preserved(self, mock_spawn):
        """Test that all state changes are preserved in history."""
        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "check" in premise.lower():
                    return {"complete": True}  # Approve immediately
                else:
                    return {"output": "analyzed"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze.", writes_to=["analysis"]),
            ],
            controller_premise="You check if complete.",
            max_iterations=3
        )

        result = await bb.solve("Build something")

        # History should be non-empty
        assert len(result.state.history) > 0
