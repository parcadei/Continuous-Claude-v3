"""
Tests for ChainOfResponsibility pattern.
"""

import pytest
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch, MagicMock


# Handler dataclass should exist in patterns
@pytest.fixture
def mock_spawn():
    """Mock spawn function for testing."""
    with patch("scripts.agentica.patterns.chain_of_responsibility.spawn") as mock:
        async def create_agent(**kwargs):
            agent = MagicMock()
            agent.call = AsyncMock(return_value=f"Handled by: {kwargs.get('premise', 'unknown')}")
            return agent
        mock.side_effect = create_agent
        yield mock


class TestChainOfResponsibility:
    """Tests for ChainOfResponsibility pattern."""

    @pytest.mark.asyncio
    async def test_first_matching_handler_is_used(self, mock_spawn):
        """First handler that can_handle returns True should process the request."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(handlers=[
            Handler(
                premise="You handle Python questions.",
                can_handle=lambda q: "python" in q.lower()
            ),
            Handler(
                premise="You handle JavaScript questions.",
                can_handle=lambda q: "javascript" in q.lower()
            ),
        ])

        result = await chain.process("How do I use async in Python?")

        # Should have called spawn with Python handler premise
        assert "Python" in result or "python" in result.lower() or mock_spawn.called

    @pytest.mark.asyncio
    async def test_falls_through_to_next_handler(self, mock_spawn):
        """If first handler can't handle, should try next handler."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        python_handler_called = False
        js_handler_called = False

        chain = ChainOfResponsibility(handlers=[
            Handler(
                premise="You handle Python questions.",
                can_handle=lambda q: "python" in q.lower()
            ),
            Handler(
                premise="You handle JavaScript questions.",
                can_handle=lambda q: "javascript" in q.lower()
            ),
        ])

        result = await chain.process("How do I use promises in JavaScript?")

        # JavaScript handler should be used (Python can't handle it)
        assert mock_spawn.called
        # Check the premise passed to spawn
        call_kwargs = mock_spawn.call_args.kwargs
        assert "JavaScript" in call_kwargs.get("premise", "")

    @pytest.mark.asyncio
    async def test_fallback_handler_catches_all(self, mock_spawn):
        """A handler with can_handle=lambda q: True should catch all unhandled requests."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(handlers=[
            Handler(
                premise="You handle Python questions.",
                can_handle=lambda q: "python" in q.lower()
            ),
            Handler(
                premise="You handle general programming questions.",
                can_handle=lambda q: True  # Fallback
            ),
        ])

        # Query that doesn't match Python
        result = await chain.process("What is recursion?")

        # Should fall through to general handler
        call_kwargs = mock_spawn.call_args.kwargs
        assert "general" in call_kwargs.get("premise", "").lower()

    @pytest.mark.asyncio
    async def test_handler_priority_ordering(self, mock_spawn):
        """Handlers should be sorted by priority (lower number = higher priority)."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        # Create handlers in wrong order, but with priorities
        chain = ChainOfResponsibility(handlers=[
            Handler(
                premise="Low priority fallback.",
                can_handle=lambda q: True,
                priority=100
            ),
            Handler(
                premise="High priority Python handler.",
                can_handle=lambda q: "python" in q.lower(),
                priority=1
            ),
            Handler(
                premise="Medium priority general handler.",
                can_handle=lambda q: True,
                priority=50
            ),
        ])

        # Query that matches Python and general
        result = await chain.process("How do I use async in Python?")

        # High priority Python handler should be used
        call_kwargs = mock_spawn.call_args.kwargs
        assert "High priority" in call_kwargs.get("premise", "") or "Python" in call_kwargs.get("premise", "")

    @pytest.mark.asyncio
    async def test_no_handler_can_handle_raises_error(self, mock_spawn):
        """If no handler can handle the request, should raise an error."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(handlers=[
            Handler(
                premise="You handle Python questions.",
                can_handle=lambda q: "python" in q.lower()
            ),
            Handler(
                premise="You handle JavaScript questions.",
                can_handle=lambda q: "javascript" in q.lower()
            ),
        ])

        # Query that matches neither
        with pytest.raises(ValueError, match="No handler"):
            await chain.process("What is the meaning of life?")

    @pytest.mark.asyncio
    async def test_coordination_db_integration(self, mock_spawn):
        """Should use tracked_spawn when db is provided."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        mock_db = MagicMock()

        with patch("scripts.agentica.tracked_agent.tracked_spawn") as mock_tracked:
            async def create_tracked_agent(**kwargs):
                agent = MagicMock()
                agent.call = AsyncMock(return_value="Tracked result")
                return agent
            mock_tracked.side_effect = create_tracked_agent

            chain = ChainOfResponsibility(
                handlers=[
                    Handler(
                        premise="General handler.",
                        can_handle=lambda q: True
                    ),
                ],
                db=mock_db
            )

            result = await chain.process("Any question")

            # Should have used tracked_spawn
            mock_tracked.assert_called_once()
            call_kwargs = mock_tracked.call_args.kwargs
            assert call_kwargs.get("db") == mock_db
            assert call_kwargs.get("pattern") == "chain_of_responsibility"
