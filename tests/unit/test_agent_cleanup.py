"""Tests for agent/swarm cleanup functionality in Agent Monitor TUI.

Tests:
1. Stale detection (>24h old agents)
2. SIGTERM sending (mocked)
3. Clean stale filtering
4. Kill agent with PID validation
"""

from __future__ import annotations

import os
import signal
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, patch

import pytest

from scripts.agentica_patterns.coordination import AgentRecord


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
        ppid=os.getpid(),  # Use current process as parent
        spawned_at=spawned_at,
        completed_at=None,
        status=status,
        error_message=None,
    )


# ============================================================
# Test: is_stale_agent()
# ============================================================


class TestIsStaleAgent:
    """Tests for stale agent detection."""

    def test_agent_younger_than_24h_is_not_stale(self):
        """Agent spawned less than 24 hours ago should not be stale."""
        from scripts.agent_monitor_tui.poller import is_stale_agent

        agent = make_agent(
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=23)
        )
        assert is_stale_agent(agent) is False

    def test_agent_older_than_24h_is_stale(self):
        """Agent spawned more than 24 hours ago should be stale."""
        from scripts.agent_monitor_tui.poller import is_stale_agent

        agent = make_agent(
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
        )
        assert is_stale_agent(agent) is True

    def test_agent_exactly_24h_is_stale(self):
        """Agent spawned exactly 24 hours ago should be stale (edge case)."""
        from scripts.agent_monitor_tui.poller import is_stale_agent

        agent = make_agent(
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
        )
        assert is_stale_agent(agent) is True

    def test_stale_threshold_can_be_customized(self):
        """Stale threshold can be customized via parameter."""
        from scripts.agent_monitor_tui.poller import is_stale_agent

        agent = make_agent(
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        )
        # Default 24h: not stale
        assert is_stale_agent(agent) is False
        # Custom 1h threshold: stale
        assert is_stale_agent(agent, threshold_hours=1) is True


# ============================================================
# Test: filter_stale_agents()
# ============================================================


class TestFilterStaleAgents:
    """Tests for filtering out stale agents from a list."""

    def test_filters_out_stale_agents(self):
        """Stale agents should be removed from the list."""
        from scripts.agent_monitor_tui.poller import filter_stale_agents

        old_agent = make_agent(
            agent_id="old-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=48),
        )
        fresh_agent = make_agent(
            agent_id="fresh-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        )

        result = filter_stale_agents([old_agent, fresh_agent])
        assert len(result) == 1
        assert result[0].id == "fresh-1"

    def test_empty_list_returns_empty(self):
        """Empty input returns empty output."""
        from scripts.agent_monitor_tui.poller import filter_stale_agents

        result = filter_stale_agents([])
        assert result == []

    def test_all_stale_returns_empty(self):
        """If all agents are stale, return empty list."""
        from scripts.agent_monitor_tui.poller import filter_stale_agents

        old_agents = [
            make_agent(
                agent_id=f"old-{i}",
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=3),
            )
            for i in range(3)
        ]
        result = filter_stale_agents(old_agents)
        assert result == []

    def test_all_fresh_returns_all(self):
        """If no agents are stale, return all."""
        from scripts.agent_monitor_tui.poller import filter_stale_agents

        fresh_agents = [
            make_agent(
                agent_id=f"fresh-{i}",
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
            )
            for i in range(3)
        ]
        result = filter_stale_agents(fresh_agents)
        assert len(result) == 3


# ============================================================
# Test: kill_agent()
# ============================================================


class TestKillAgent:
    """Tests for killing an agent by PID."""

    def test_kill_agent_sends_sigterm(self):
        """kill_agent should send SIGTERM to the specified PID."""
        from scripts.agent_monitor_tui.poller import kill_agent

        with patch("os.kill") as mock_kill:
            result = kill_agent(12345)
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)
            assert result.success is True
            assert result.pid == 12345

    def test_kill_agent_handles_no_such_process(self):
        """kill_agent should handle OSError (process not found) gracefully."""
        from scripts.agent_monitor_tui.poller import kill_agent

        with patch("os.kill") as mock_kill:
            mock_kill.side_effect = OSError("No such process")
            result = kill_agent(99999)
            assert result.success is False
            assert "No such process" in result.error

    def test_kill_agent_handles_permission_error(self):
        """kill_agent should handle PermissionError gracefully."""
        from scripts.agent_monitor_tui.poller import kill_agent

        with patch("os.kill") as mock_kill:
            mock_kill.side_effect = PermissionError("Operation not permitted")
            result = kill_agent(1)  # PID 1 = init, typically protected
            assert result.success is False
            assert "not permitted" in result.error.lower()

    def test_kill_agent_rejects_invalid_pid(self):
        """kill_agent should reject invalid PIDs."""
        from scripts.agent_monitor_tui.poller import kill_agent

        # Negative PID
        result = kill_agent(-1)
        assert result.success is False
        assert "Invalid PID" in result.error

        # Zero PID
        result = kill_agent(0)
        assert result.success is False
        assert "Invalid PID" in result.error

    def test_kill_agent_rejects_none_pid(self):
        """kill_agent should reject None as PID."""
        from scripts.agent_monitor_tui.poller import kill_agent

        result = kill_agent(None)  # type: ignore
        assert result.success is False
        assert "Invalid PID" in result.error


# ============================================================
# Test: KillResult dataclass
# ============================================================


class TestKillResult:
    """Tests for KillResult dataclass."""

    def test_kill_result_success(self):
        """KillResult should represent successful kill."""
        from scripts.agent_monitor_tui.poller import KillResult

        result = KillResult(success=True, pid=12345, error=None)
        assert result.success is True
        assert result.pid == 12345
        assert result.error is None

    def test_kill_result_failure(self):
        """KillResult should represent failed kill."""
        from scripts.agent_monitor_tui.poller import KillResult

        result = KillResult(success=False, pid=12345, error="No such process")
        assert result.success is False
        assert result.pid == 12345
        assert "No such process" in result.error


# ============================================================
# Test: DataPoller.clean_stale_agents()
# ============================================================


class TestDataPollerCleanStale:
    """Tests for DataPoller.clean_stale_agents() method."""

    @pytest.mark.asyncio
    async def test_clean_stale_returns_fresh_agents_only(self):
        """clean_stale_agents should return only non-stale agents."""
        from scripts.agent_monitor_tui.poller import DataPoller, AgentsData

        poller = DataPoller()

        old_agent = make_agent(
            agent_id="old-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=48),
        )
        fresh_agent = make_agent(
            agent_id="fresh-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        )

        data = AgentsData(agents=[old_agent, fresh_agent])
        result = poller.clean_stale_agents(data)

        assert len(result.agents) == 1
        assert result.agents[0].id == "fresh-1"

    @pytest.mark.asyncio
    async def test_clean_stale_preserves_other_data_fields(self):
        """clean_stale_agents should preserve orphans, by_pattern, by_status."""
        from scripts.agent_monitor_tui.poller import DataPoller, AgentsData
        from scripts.agentica_patterns.coordination import OrphanCandidate

        poller = DataPoller()

        agent = make_agent(
            spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        )
        orphan = OrphanCandidate(
            agent_id="orphan-1",
            ppid=1,
            parent_agent_id=None,
            spawned_at=datetime.now(UTC).replace(tzinfo=None),
            tier=1,
            reason="test orphan",
        )

        data = AgentsData(
            agents=[agent],
            orphans=[orphan],
            by_pattern={"swarm": 1},
            by_status={"running": 1},
        )
        result = poller.clean_stale_agents(data)

        assert len(result.orphans) == 1
        assert result.by_pattern == {"swarm": 1}
        assert result.by_status == {"running": 1}


# ============================================================
# Test: DataPoller.kill_agent()
# ============================================================


class TestDataPollerKillAgent:
    """Tests for DataPoller.kill_agent() method."""

    @pytest.mark.asyncio
    async def test_kill_agent_via_poller(self):
        """DataPoller.kill_agent should delegate to kill_agent function."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch("scripts.agent_monitor_tui.poller.kill_agent") as mock_kill:
            from scripts.agent_monitor_tui.poller import KillResult
            mock_kill.return_value = KillResult(success=True, pid=12345, error=None)

            result = await poller.kill_agent_async(12345)
            mock_kill.assert_called_once_with(12345)
            assert result.success is True


# ============================================================
# Test: Integration with AgentRecord.pid
# ============================================================


class TestAgentKillIntegration:
    """Integration tests for killing agents from AgentRecord."""

    def test_agent_with_pid_can_be_killed(self):
        """Agent with valid PID should be killable (mocked)."""
        from scripts.agent_monitor_tui.poller import kill_agent

        agent = make_agent(pid=12345)

        with patch("os.kill") as mock_kill:
            result = kill_agent(agent.pid)
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)
            assert result.success is True

    def test_agent_without_pid_cannot_be_killed(self):
        """Agent without PID should return error."""
        from scripts.agent_monitor_tui.poller import kill_agent

        agent = make_agent(pid=None)

        result = kill_agent(agent.pid)
        assert result.success is False
        assert "Invalid PID" in result.error
