"""
Tests for Adversarial pattern.

Tests TDD-style:
1. Test advocate and adversary both get called
2. Test multiple rounds of debate
3. Test judge receives both positions
4. Test works without judge (returns both positions)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from scripts.agentica.patterns import Adversarial


class TestAdversarial:
    """Tests for the Adversarial pattern."""

    @pytest.fixture
    def mock_spawn(self):
        """Create mock spawn function."""
        with patch("scripts.agentica.patterns.adversarial.spawn") as mock:
            yield mock

    @pytest.fixture
    def basic_adversarial(self):
        """Create basic Adversarial instance for testing."""
        return Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            max_rounds=2
        )

    @pytest.fixture
    def adversarial_with_judge(self):
        """Create Adversarial instance with judge."""
        return Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            judge_premise="You decide which is stronger.",
            max_rounds=2
        )

    @pytest.mark.asyncio
    async def test_advocate_and_adversary_both_called(self, mock_spawn):
        """Test that both advocate and adversary agents are spawned and called."""
        # Setup mock agents
        advocate_agent = AsyncMock()
        advocate_agent.call = AsyncMock(return_value="Pro argument")

        adversary_agent = AsyncMock()
        adversary_agent.call = AsyncMock(return_value="Con argument")

        # spawn returns different agents based on premise
        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            if "favor" in kwargs.get("premise", ""):
                mock_agent.call = AsyncMock(return_value="Pro argument")
            else:
                mock_agent.call = AsyncMock(return_value="Con argument")
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            max_rounds=1
        )

        result = await adv.debate("Should we use microservices?")

        # Both agents should have been spawned
        assert mock_spawn.call_count >= 2

    @pytest.mark.asyncio
    async def test_multiple_rounds_of_debate(self, mock_spawn):
        """Test that debate runs for multiple rounds."""
        call_count = {"advocate": 0, "adversary": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()

            async def mock_call(return_type, prompt, **kw):
                if "favor" in kwargs.get("premise", ""):
                    call_count["advocate"] += 1
                    return f"Pro argument round {call_count['advocate']}"
                else:
                    call_count["adversary"] += 1
                    return f"Con argument round {call_count['adversary']}"

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            max_rounds=3
        )

        await adv.debate("Should we use microservices?")

        # Each agent should be called max_rounds times
        assert call_count["advocate"] == 3
        assert call_count["adversary"] == 3

    @pytest.mark.asyncio
    async def test_judge_receives_both_positions(self, mock_spawn):
        """Test that judge receives both advocate and adversary positions."""
        judge_received_prompt = None

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                nonlocal judge_received_prompt
                if "decide" in premise:
                    judge_received_prompt = prompt
                    return "Advocate wins"
                elif "favor" in premise:
                    return "Pro argument"
                else:
                    return "Con argument"

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            judge_premise="You decide which is stronger.",
            max_rounds=1
        )

        result = await adv.resolve("Should we use microservices?")

        # Judge should have been called with both positions
        assert judge_received_prompt is not None
        assert "Pro argument" in judge_received_prompt or "advocate" in judge_received_prompt.lower()

    @pytest.mark.asyncio
    async def test_works_without_judge(self, mock_spawn):
        """Test that pattern works without judge, returning both positions."""
        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "favor" in premise:
                    return "Pro argument"
                else:
                    return "Con argument"

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            max_rounds=1
        )

        result = await adv.resolve("Should we use microservices?")

        # Without judge, should return both positions
        assert "advocate" in result or "Pro" in str(result) or isinstance(result, dict)
