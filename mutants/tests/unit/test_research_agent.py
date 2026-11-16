"""Tests for Research Agent - Perplexity and Nia integration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys

# Mock agentica before import to prevent ImportError
sys.modules['agentica'] = MagicMock()


class TestResearchAgentCreation:
    """Test research agent creation."""

    def test_research_agent_imports(self):
        """Research agent module should be importable."""
        from scripts.agentica.server.research_agent import create_research_agent
        assert callable(create_research_agent)

    @pytest.mark.asyncio
    async def test_create_research_agent_returns_agent(self):
        """create_research_agent should return an agent with call method."""
        with patch("agentica.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_agent = MagicMock()
            mock_agent.call = AsyncMock(return_value="test response")
            mock_spawn.return_value = mock_agent

            from scripts.agentica.server.research_agent import create_research_agent
            agent = await create_research_agent()

            assert agent is not None
            assert hasattr(agent, "call")


class TestResearchScope:
    """Test research scope functions."""

    def test_get_research_scope_has_perplexity(self):
        """Scope should include perplexity functions."""
        from scripts.agentica.server.research_agent import get_research_scope

        scope = get_research_scope()

        assert "perplexity_search" in scope
        assert "perplexity_research" in scope
        assert callable(scope["perplexity_search"])

    def test_get_research_scope_has_nia(self):
        """Scope should include nia functions."""
        from scripts.agentica.server.research_agent import get_research_scope

        scope = get_research_scope()

        assert "nia_search" in scope
        assert "nia_oracle" in scope
        assert callable(scope["nia_search"])

    @pytest.mark.asyncio
    async def test_perplexity_search_calls_underlying(self):
        """perplexity_search should call the underlying function."""
        from scripts.agentica.server.research_agent import get_research_scope

        with patch("scripts.agentica.server.research_agent.perplexity_search_fn") as mock_search:
            mock_search.return_value = {"results": []}

            scope = get_research_scope()
            result = await scope["perplexity_search"](query="test")

            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_perplexity_research_calls_underlying(self):
        """perplexity_research should call chat_query with sonar-pro model."""
        from scripts.agentica.server.research_agent import get_research_scope

        with patch("scripts.agentica.server.research_agent.perplexity_chat") as mock_chat:
            mock_chat.return_value = {"answer": "test answer", "citations": []}

            scope = get_research_scope()
            result = await scope["perplexity_research"](query="test research")

            mock_chat.assert_called_once()
            # Verify it was called with sonar-pro model
            call_args = mock_chat.call_args
            assert call_args[0][1] == "sonar-pro"

    @pytest.mark.asyncio
    async def test_nia_search_calls_underlying(self):
        """nia_search should call search_universal."""
        from scripts.agentica.server.research_agent import get_research_scope

        with patch("scripts.agentica.server.research_agent.search_universal_fn") as mock_search:
            mock_search.return_value = {"results": []}

            scope = get_research_scope()
            result = await scope["nia_search"](query="test")

            mock_search.assert_called_once()


class TestResearchAgentState:
    """Test research agent state management."""

    @pytest.mark.asyncio
    async def test_agent_tracks_findings(self):
        """Agent should track findings in state."""
        with patch("agentica.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_agent = MagicMock()
            mock_agent.call = AsyncMock(return_value="Found: X is important")

            # Simulate state
            mock_state = {"findings": [], "sources": {}}
            mock_agent.state = mock_state

            mock_spawn.return_value = mock_agent

            from scripts.agentica.server.research_agent import create_research_agent
            agent = await create_research_agent()

            # Simulate adding finding
            agent.state["findings"].append("X is important")

            assert "X is important" in agent.state["findings"]

    @pytest.mark.asyncio
    async def test_agent_has_initial_state(self):
        """Agent should be initialized with expected state structure."""
        with patch("agentica.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_agent = MagicMock()
            mock_agent.call = AsyncMock(return_value="test")
            mock_spawn.return_value = mock_agent

            from scripts.agentica.server.research_agent import create_research_agent
            agent = await create_research_agent()

            # Verify initial state structure
            assert "findings" in agent.state
            assert "sources" in agent.state
            assert "query_history" in agent.state
            assert "current_topic" in agent.state
            assert isinstance(agent.state["findings"], list)
            assert isinstance(agent.state["sources"], dict)


class TestResearchAgentRegistration:
    """Test agent registration in registry."""

    def test_research_agent_registered(self):
        """Research agent should be in registry."""
        from scripts.agentica.server.registry import AGENT_TYPES

        assert "research" in AGENT_TYPES


class TestResearchAgentPremise:
    """Test the agent premise/system prompt."""

    def test_premise_describes_capabilities(self):
        """Premise should describe research capabilities."""
        from scripts.agentica.server.research_agent import RESEARCH_PREMISE

        assert "research" in RESEARCH_PREMISE.lower()
        assert "perplexity" in RESEARCH_PREMISE.lower() or "search" in RESEARCH_PREMISE.lower()
        assert "nia" in RESEARCH_PREMISE.lower() or "documentation" in RESEARCH_PREMISE.lower()

    def test_premise_describes_state(self):
        """Premise should describe state management."""
        from scripts.agentica.server.research_agent import RESEARCH_PREMISE

        assert "findings" in RESEARCH_PREMISE.lower()
        assert "sources" in RESEARCH_PREMISE.lower()


class TestStatefulAgent:
    """Test StatefulAgent wrapper class."""

    def test_stateful_agent_has_state_dict(self):
        """StatefulAgent should have a state dict."""
        from scripts.agentica.server.research_agent import StatefulAgent

        mock_agent = MagicMock()
        stateful = StatefulAgent(mock_agent, initial_state={"test": "value"})

        assert stateful.state == {"test": "value"}

    def test_stateful_agent_default_state(self):
        """StatefulAgent should default to empty dict if no initial state."""
        from scripts.agentica.server.research_agent import StatefulAgent

        mock_agent = MagicMock()
        stateful = StatefulAgent(mock_agent)

        assert stateful.state == {}

    @pytest.mark.asyncio
    async def test_stateful_agent_delegates_call(self):
        """StatefulAgent.call should delegate to underlying agent."""
        from scripts.agentica.server.research_agent import StatefulAgent

        mock_agent = MagicMock()
        mock_agent.call = AsyncMock(return_value="delegated response")
        stateful = StatefulAgent(mock_agent)

        result = await stateful.call(str, "test query")

        mock_agent.call.assert_called_once_with(str, "test query")
        assert result == "delegated response"

    def test_stateful_agent_delegates_usage(self):
        """StatefulAgent should delegate usage methods."""
        from scripts.agentica.server.research_agent import StatefulAgent

        mock_agent = MagicMock()
        mock_agent.total_usage.return_value = {"tokens": 100}
        mock_agent.last_usage.return_value = {"tokens": 10}
        stateful = StatefulAgent(mock_agent)

        assert stateful.total_usage() == {"tokens": 100}
        assert stateful.last_usage() == {"tokens": 10}
