"""
Unit tests for Chain of Responsibility pattern PATTERN_TYPE environment variable.

Tests that the Chain of Responsibility pattern sets the correct environment variables
when spawning handler agents.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scripts.agentica_patterns.patterns.chain_of_responsibility import ChainOfResponsibility, Handler


class TestChainOfResponsibilityPatternType:
    """Tests for PATTERN_TYPE environment variable in Chain of Responsibility pattern."""

    @pytest.mark.asyncio
    async def test_sets_pattern_type_env_var(self):
        """Should set PATTERN_TYPE=chain_of_responsibility when spawning handlers."""
        # Create a simple handler
        handler = Handler(
            premise="Test handler",
            can_handle=lambda q: True,
            priority=0
        )

        chain = ChainOfResponsibility(handlers=[handler])

        # Mock spawn to capture environment variables
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="handled")

        with patch("scripts.agentica_patterns.patterns.chain_of_responsibility.spawn") as mock_spawn:
            mock_spawn.return_value = mock_agent

            result = await chain.process("test query")

            # Verify spawn was called
            mock_spawn.assert_called_once()
            spawn_kwargs = mock_spawn.call_args[1]

            # Check environment variables are set
            assert "env" in spawn_kwargs
            env = spawn_kwargs["env"]
            assert env["PATTERN_TYPE"] == "chain_of_responsibility"
            assert "COR_ID" in env  # Chain of Responsibility ID
            assert "HANDLER_PRIORITY" in env
            assert env["HANDLER_PRIORITY"] == "0"
            assert env["AGENT_ROLE"] == "handler"

    @pytest.mark.asyncio
    async def test_sets_handler_priority_correctly(self):
        """Should set HANDLER_PRIORITY based on handler's priority."""
        handlers = [
            Handler(premise="High priority", can_handle=lambda q: "urgent" in q, priority=0),
            Handler(premise="Medium priority", can_handle=lambda q: "normal" in q, priority=1),
            Handler(premise="Low priority", can_handle=lambda q: True, priority=2),
        ]

        chain = ChainOfResponsibility(handlers=handlers)

        # Mock spawn
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="handled")

        # Test medium priority handler
        with patch("scripts.agentica_patterns.patterns.chain_of_responsibility.spawn") as mock_spawn:
            mock_spawn.return_value = mock_agent

            result = await chain.process("normal query")

            spawn_kwargs = mock_spawn.call_args[1]
            assert spawn_kwargs["env"]["HANDLER_PRIORITY"] == "1"

    @pytest.mark.asyncio
    async def test_sets_chain_length(self):
        """Should set CHAIN_LENGTH to total number of handlers."""
        handlers = [
            Handler(premise="Handler 1", can_handle=lambda q: False, priority=0),
            Handler(premise="Handler 2", can_handle=lambda q: False, priority=1),
            Handler(premise="Handler 3", can_handle=lambda q: True, priority=2),
        ]

        chain = ChainOfResponsibility(handlers=handlers)

        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="handled")

        with patch("scripts.agentica_patterns.patterns.chain_of_responsibility.spawn") as mock_spawn:
            mock_spawn.return_value = mock_agent

            result = await chain.process("test query")

            spawn_kwargs = mock_spawn.call_args[1]
            assert spawn_kwargs["env"]["CHAIN_LENGTH"] == "3"

    @pytest.mark.asyncio
    async def test_unique_cor_id_per_chain(self):
        """Each chain execution should have a unique COR_ID."""
        handler = Handler(premise="Test", can_handle=lambda q: True, priority=0)
        chain = ChainOfResponsibility(handlers=[handler])

        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="handled")

        cor_ids = []

        with patch("scripts.agentica_patterns.patterns.chain_of_responsibility.spawn") as mock_spawn:
            mock_spawn.return_value = mock_agent

            # Execute chain twice
            await chain.process("query 1")
            cor_ids.append(mock_spawn.call_args[1]["env"]["COR_ID"])

            await chain.process("query 2")
            cor_ids.append(mock_spawn.call_args[1]["env"]["COR_ID"])

        # IDs should be different
        assert cor_ids[0] != cor_ids[1]
        # Both should be valid IDs (alphanumeric with hyphens)
        for cor_id in cor_ids:
            assert cor_id.replace("-", "").replace("_", "").isalnum()

    @pytest.mark.asyncio
    async def test_pattern_id_matches_cor_id(self):
        """PATTERN_ID should match COR_ID for consistency."""
        handler = Handler(premise="Test", can_handle=lambda q: True, priority=0)
        chain = ChainOfResponsibility(handlers=[handler])

        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="handled")

        with patch("scripts.agentica_patterns.patterns.chain_of_responsibility.spawn") as mock_spawn:
            mock_spawn.return_value = mock_agent

            await chain.process("test query")

            spawn_kwargs = mock_spawn.call_args[1]
            env = spawn_kwargs["env"]
            assert env["PATTERN_ID"] == env["COR_ID"]

    @pytest.mark.asyncio
    async def test_uses_tracked_spawn_when_db_provided(self):
        """Should use tracked_spawn instead of spawn when db is provided."""
        handler = Handler(premise="Test", can_handle=lambda q: True, priority=0)

        # Mock database
        mock_db = MagicMock()

        chain = ChainOfResponsibility(handlers=[handler], db=mock_db)

        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="handled")

        # Mock the tracked_spawn import that happens at runtime
        with patch("scripts.agentica_patterns.tracked_agent.tracked_spawn") as mock_tracked_spawn:
            mock_tracked_spawn.return_value = mock_agent

            result = await chain.process("test query")

            # Should call tracked_spawn, not spawn
            mock_tracked_spawn.assert_called_once()
            spawn_kwargs = mock_tracked_spawn.call_args[1]

            # Should pass pattern type to tracked_spawn
            assert spawn_kwargs["pattern"] == "chain_of_responsibility"
            assert spawn_kwargs["db"] == mock_db

            # Should still set environment variables
            assert "env" in spawn_kwargs
            assert spawn_kwargs["env"]["PATTERN_TYPE"] == "chain_of_responsibility"
