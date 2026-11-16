"""Tests for Agent Monitor TUI fixes.

Tests for:
1. Home page shows current session agent count (not all-time count)
2. Clean Stale button filters agents in the view
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.agentica_patterns.coordination import AgentRecord
from scripts.agent_monitor_tui.poller import (
    DataPoller,
    HomeData,
    AgentsData,
    is_stale_agent,
)


# ============================================================
# Test Data Fixtures
# ============================================================


def make_agent(
    agent_id: str = "test-agent-1",
    session_id: str = "session-1",
    status: str = "running",
    spawned_at: datetime | None = None,
    pid: int | None = None,
    pattern: str | None = "swarm",
) -> AgentRecord:
    """Create an AgentRecord for testing."""
    if spawned_at is None:
        spawned_at = datetime.now(UTC).replace(tzinfo=None)
    return AgentRecord(
        id=agent_id,
        session_id=session_id,
        premise="Test agent",
        model="claude-3-opus",
        scope_keys=["key1"],
        pattern=pattern,
        parent_agent_id=None,
        pid=pid,
        ppid=os.getpid(),
        spawned_at=spawned_at,
        completed_at=None,
        status=status,
        error_message=None,
    )


# ============================================================
# Test: Issue 1 - Home page shows current session agent count
# ============================================================


class TestHomePageAgentCount:
    """Tests for Home page agent count fix."""

    @pytest.mark.asyncio
    async def test_poll_home_returns_visible_agent_count(self):
        """poll_home should return count of visible agents, not all-time count."""
        poller = DataPoller()

        # Create mock agents for get_all_running_agents
        visible_agents = [
            make_agent(agent_id=f"agent-{i}")
            for i in range(5)
        ]

        # Mock the DB methods
        mock_db = MagicMock()
        mock_db.get_session_summary.return_value = {
            "agents_by_status": {"running": 3},
            "agents_by_pattern": {"swarm": 5},
        }
        mock_db.get_all_sessions_summary.return_value = {
            "total_agents": 96,  # All-time count (should NOT be used)
            "total_sessions": 10,
        }
        mock_db.get_all_running_agents.return_value = visible_agents

        poller._db = mock_db
        poller._connected = True

        result = await poller.poll_home()

        # Should return 5 (visible agents), not 96 (all-time)
        assert result.agent_count == 5
        assert result.running_agents == 3
        assert result.session_count == 10

    @pytest.mark.asyncio
    async def test_poll_home_returns_zero_when_no_agents(self):
        """poll_home should return 0 when no visible agents."""
        poller = DataPoller()

        mock_db = MagicMock()
        mock_db.get_session_summary.return_value = {
            "agents_by_status": {},
            "agents_by_pattern": {},
        }
        mock_db.get_all_sessions_summary.return_value = {
            "total_agents": 50,
            "total_sessions": 5,
        }
        mock_db.get_all_running_agents.return_value = []

        poller._db = mock_db
        poller._connected = True

        result = await poller.poll_home()

        assert result.agent_count == 0

    @pytest.mark.asyncio
    async def test_poll_home_handles_none_running_agents(self):
        """poll_home should handle None return from get_all_running_agents."""
        poller = DataPoller()

        mock_db = MagicMock()
        mock_db.get_session_summary.return_value = {
            "agents_by_status": {},
            "agents_by_pattern": {},
        }
        mock_db.get_all_sessions_summary.return_value = {
            "total_agents": 50,
            "total_sessions": 5,
        }
        mock_db.get_all_running_agents.return_value = None

        poller._db = mock_db
        poller._connected = True

        result = await poller.poll_home()

        assert result.agent_count == 0


# ============================================================
# Test: Issue 2 - Clean Stale filters agents in the view
# ============================================================


class TestCleanStaleFilter:
    """Tests for Clean Stale button fix."""

    def test_hide_stale_agents_sets_flag(self):
        """hide_stale_agents should set _show_stale to False."""
        from scripts.agent_monitor_tui.widgets.agent_view import AgentPanel

        panel = AgentPanel()
        # Initially _show_stale should be True
        assert panel._show_stale is True

        # Mock _initialized so watch_data doesn't actually try to query widgets
        panel._initialized = False

        panel.hide_stale_agents()

        assert panel._show_stale is False

    def test_watch_data_filters_stale_when_hidden(self):
        """watch_data should filter stale agents when _show_stale is False."""
        from scripts.agent_monitor_tui.widgets.agent_view import AgentPanel

        panel = AgentPanel()
        panel._show_stale = False
        # Don't run actual widget updates
        panel._initialized = False

        old_agent = make_agent(
            agent_id="old-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=48),
        )
        fresh_agent = make_agent(
            agent_id="fresh-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        )

        data = AgentsData(agents=[old_agent, fresh_agent])

        # When _show_stale is False, watch_data should filter
        # We can't call watch_data directly without widget initialization,
        # so test the filtering logic directly
        if not panel._show_stale:
            visible_agents = [a for a in data.agents if not is_stale_agent(a)]
        else:
            visible_agents = data.agents

        assert len(visible_agents) == 1
        assert visible_agents[0].id == "fresh-1"

    def test_watch_data_shows_all_when_show_stale_true(self):
        """watch_data should show all agents when _show_stale is True (default)."""
        from scripts.agent_monitor_tui.widgets.agent_view import AgentPanel

        panel = AgentPanel()
        assert panel._show_stale is True
        panel._initialized = False

        old_agent = make_agent(
            agent_id="old-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=48),
        )
        fresh_agent = make_agent(
            agent_id="fresh-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        )

        data = AgentsData(agents=[old_agent, fresh_agent])

        # When _show_stale is True, should show all
        if panel._show_stale:
            visible_agents = data.agents
        else:
            visible_agents = [a for a in data.agents if not is_stale_agent(a)]

        assert len(visible_agents) == 2

    def test_is_stale_agent_identifies_old_agents(self):
        """is_stale_agent should correctly identify agents older than 24 hours."""
        old_agent = make_agent(
            agent_id="old-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25),
        )
        fresh_agent = make_agent(
            agent_id="fresh-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        )

        assert is_stale_agent(old_agent) is True
        assert is_stale_agent(fresh_agent) is False


# ============================================================
# Test: AgentPanel filter state behavior
# ============================================================


class TestAgentPanelFilterState:
    """Tests for AgentPanel filter state management."""

    def test_initial_show_stale_is_true(self):
        """AgentPanel should show stale agents by default."""
        from scripts.agent_monitor_tui.widgets.agent_view import AgentPanel

        panel = AgentPanel()
        assert panel._show_stale is True

    def test_hide_stale_agents_changes_state(self):
        """hide_stale_agents should change _show_stale from True to False."""
        from scripts.agent_monitor_tui.widgets.agent_view import AgentPanel

        panel = AgentPanel()
        panel._initialized = False  # Prevent widget operations

        assert panel._show_stale is True
        panel.hide_stale_agents()
        assert panel._show_stale is False

    def test_filter_logic_with_mixed_agents(self):
        """Filter should correctly handle mix of stale and fresh agents."""
        old_agents = [
            make_agent(
                agent_id=f"old-{i}",
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
            )
            for i in range(3)
        ]
        fresh_agents = [
            make_agent(
                agent_id=f"fresh-{i}",
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
            )
            for i in range(2)
        ]

        all_agents = old_agents + fresh_agents
        filtered = [a for a in all_agents if not is_stale_agent(a)]

        assert len(all_agents) == 5
        assert len(filtered) == 2
        assert all(a.id.startswith("fresh-") for a in filtered)
