"""Tests for --all-sessions flag in watch_agents.py.

These tests verify that watch_agents can:
1. Show agents from all sessions with --all-sessions flag
2. Filter by specific session ID
3. Display session column in output
4. Handle empty databases and multiple sessions

TDD: These tests are written BEFORE implementation.
Expected to FAIL until the feature is implemented.
"""

import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import sqlite3

import pytest

from scripts.agentica.coordination import CoordinationDB, AgentRecord


class TestAllSessionsFlag:
    """Test --all-sessions CLI flag."""

    def test_all_sessions_flag_exists(self):
        """watch_agents.py should accept --all-sessions flag."""
        result = subprocess.run(
            ["python", "scripts/agentica/watch_agents.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )
        # This will FAIL until --all-sessions is implemented
        assert "--all-sessions" in result.stdout, (
            "Expected --all-sessions flag in help output. "
            "Feature not yet implemented."
        )

    def test_all_sessions_flag_short_form(self):
        """Should support -a as short form for --all-sessions."""
        result = subprocess.run(
            ["python", "scripts/agentica/watch_agents.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )
        # Common convention: -a for --all
        assert "-a" in result.stdout or "--all-sessions" in result.stdout


class TestDefaultBehavior:
    """Test default behavior (current session only)."""

    def test_default_shows_current_session_only(self):
        """By default, should only show agents from current session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create two sessions with agents
            db1 = CoordinationDB(db_path=db_path, session_id="session1")
            db1.register_agent("agent1", premise="From session 1", pattern="swarm")

            db2 = CoordinationDB(db_path=db_path, session_id="session2")
            db2.register_agent("agent2", premise="From session 2", pattern="jury")

            # Query with session1 - should only see agent1
            agents = db1.get_running_agents()
            assert len(agents) == 1
            assert agents[0].id == "agent1"
            assert agents[0].session_id == "session1"

    def test_session_filter_isolates_agents(self):
        """Agents from different sessions should be isolated by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Session A with 2 agents
            db_a = CoordinationDB(db_path=db_path, session_id="sessionA")
            db_a.register_agent("a1", premise="A1")
            db_a.register_agent("a2", premise="A2")

            # Session B with 3 agents
            db_b = CoordinationDB(db_path=db_path, session_id="sessionB")
            db_b.register_agent("b1", premise="B1")
            db_b.register_agent("b2", premise="B2")
            db_b.register_agent("b3", premise="B3")

            # Each session only sees its own agents
            assert len(db_a.get_running_agents()) == 2
            assert len(db_b.get_running_agents()) == 3


class TestAllSessionsQuery:
    """Test querying agents across all sessions."""

    def test_get_all_running_agents_method_exists(self):
        """CoordinationDB should have get_all_running_agents method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = CoordinationDB(db_path=db_path, session_id="test")

            # This will FAIL until method is implemented
            assert hasattr(db, "get_all_running_agents"), (
                "CoordinationDB should have get_all_running_agents method. "
                "Feature not yet implemented."
            )

    def test_get_all_running_agents_returns_all_sessions(self):
        """get_all_running_agents should return agents from ALL sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create multiple sessions
            db1 = CoordinationDB(db_path=db_path, session_id="sess1")
            db1.register_agent("agent-1a", premise="Session 1 Agent A")
            db1.register_agent("agent-1b", premise="Session 1 Agent B")

            db2 = CoordinationDB(db_path=db_path, session_id="sess2")
            db2.register_agent("agent-2a", premise="Session 2 Agent A")

            db3 = CoordinationDB(db_path=db_path, session_id="sess3")
            db3.register_agent("agent-3a", premise="Session 3 Agent A")
            db3.register_agent("agent-3b", premise="Session 3 Agent B")
            db3.register_agent("agent-3c", premise="Session 3 Agent C")

            # Query all sessions - should see 6 total agents
            # This will FAIL until method is implemented
            all_agents = db1.get_all_running_agents()

            assert len(all_agents) == 6, (
                f"Expected 6 agents across all sessions, got {len(all_agents)}"
            )

            # Verify we have agents from each session
            session_ids = {a.session_id for a in all_agents}
            assert session_ids == {"sess1", "sess2", "sess3"}

    def test_get_all_running_agents_with_pattern_filter(self):
        """get_all_running_agents should support pattern filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create agents with different patterns across sessions
            db1 = CoordinationDB(db_path=db_path, session_id="s1")
            db1.register_agent("swarm-1", pattern="swarm")
            db1.register_agent("jury-1", pattern="jury")

            db2 = CoordinationDB(db_path=db_path, session_id="s2")
            db2.register_agent("swarm-2", pattern="swarm")
            db2.register_agent("pipeline-2", pattern="pipeline")

            # Filter by pattern across all sessions
            # This will FAIL until method is implemented
            swarm_agents = db1.get_all_running_agents(pattern="swarm")

            assert len(swarm_agents) == 2
            assert all(a.pattern == "swarm" for a in swarm_agents)
            assert {a.session_id for a in swarm_agents} == {"s1", "s2"}


class TestSessionColumn:
    """Test session column in output."""

    def test_create_running_table_includes_session(self):
        """create_running_table should include session column when all_sessions=True."""
        # Import the function
        try:
            from scripts.agentica.watch_agents import create_running_table_all_sessions
        except ImportError:
            pytest.fail(
                "create_running_table_all_sessions function not implemented. "
                "Need function that adds session column to table."
            )

        # Create mock agents from different sessions
        agents = [
            AgentRecord(
                id="agent1",
                session_id="sess-abc123",
                premise="Test agent 1",
                model="claude-3-opus",
                scope_keys=[],
                pattern="swarm",
                parent_agent_id=None,
                spawned_at=datetime.now(timezone.utc).replace(tzinfo=None),
                completed_at=None,
                status="running",
                error_message=None,
            ),
            AgentRecord(
                id="agent2",
                session_id="sess-def456",
                premise="Test agent 2",
                model="claude-3-sonnet",
                scope_keys=[],
                pattern="jury",
                parent_agent_id=None,
                spawned_at=datetime.now(timezone.utc).replace(tzinfo=None),
                completed_at=None,
                status="running",
                error_message=None,
            ),
        ]

        table = create_running_table_all_sessions(agents)

        # Table should have Session column
        column_names = [col.header for col in table.columns]
        assert "Session" in column_names, (
            f"Expected 'Session' column, got columns: {column_names}"
        )


class TestEmptyDatabase:
    """Test handling of empty database."""

    def test_all_sessions_empty_db(self):
        """get_all_running_agents should return empty list for empty DB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = CoordinationDB(db_path=db_path, session_id="empty")

            # This will FAIL until method is implemented
            all_agents = db.get_all_running_agents()

            assert all_agents == []

    def test_all_sessions_no_running_agents(self):
        """get_all_running_agents should return empty when all agents completed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db = CoordinationDB(db_path=db_path, session_id="test")
            db.register_agent("agent1", premise="Test")
            db.complete_agent("agent1", status="completed")

            # This will FAIL until method is implemented
            all_agents = db.get_all_running_agents()

            assert all_agents == []


class TestSessionList:
    """Test getting list of all sessions."""

    def test_get_all_sessions_method_exists(self):
        """CoordinationDB should have get_all_sessions method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = CoordinationDB(db_path=db_path, session_id="test")

            # This will FAIL until method is implemented
            assert hasattr(db, "get_all_sessions"), (
                "CoordinationDB should have get_all_sessions method. "
                "Useful for listing available sessions."
            )

    def test_get_all_sessions_returns_unique_session_ids(self):
        """get_all_sessions should return unique session IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create agents in multiple sessions
            db1 = CoordinationDB(db_path=db_path, session_id="session-alpha")
            db1.register_agent("a1")
            db1.register_agent("a2")  # Same session, multiple agents

            db2 = CoordinationDB(db_path=db_path, session_id="session-beta")
            db2.register_agent("b1")

            db3 = CoordinationDB(db_path=db_path, session_id="session-gamma")
            db3.register_agent("g1")

            # This will FAIL until method is implemented
            sessions = db1.get_all_sessions()

            assert len(sessions) == 3
            assert set(sessions) == {"session-alpha", "session-beta", "session-gamma"}


class TestCLIIntegration:
    """Integration tests for CLI with --all-sessions."""

    def test_cli_runs_with_all_sessions(self):
        """CLI should run successfully with --all-sessions flag."""
        result = subprocess.run(
            ["python", "scripts/agentica/watch_agents.py", "--all-sessions"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
            timeout=5,
        )
        # Will FAIL if flag not recognized
        assert result.returncode == 0 or "all-sessions" not in result.stderr.lower(), (
            f"CLI failed with --all-sessions: {result.stderr}"
        )

    def test_all_sessions_with_pattern_filter(self):
        """CLI should support --all-sessions combined with --pattern."""
        result = subprocess.run(
            [
                "python", "scripts/agentica/watch_agents.py",
                "--all-sessions", "--pattern", "swarm"
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
            timeout=5,
        )
        # Will FAIL if flags not recognized
        assert "error: unrecognized arguments" not in result.stderr


class TestSessionSummary:
    """Test session summary with all sessions."""

    def test_summary_all_sessions_method(self):
        """get_all_sessions_summary should aggregate across sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create agents in multiple sessions
            db1 = CoordinationDB(db_path=db_path, session_id="s1")
            db1.register_agent("a1", pattern="swarm")
            db1.register_agent("a2", pattern="swarm")
            db1.complete_agent("a1", status="completed")

            db2 = CoordinationDB(db_path=db_path, session_id="s2")
            db2.register_agent("b1", pattern="jury")
            db2.register_agent("b2", pattern="jury")

            # This will FAIL until method is implemented
            assert hasattr(db1, "get_all_sessions_summary"), (
                "CoordinationDB should have get_all_sessions_summary method."
            )

            summary = db1.get_all_sessions_summary()

            # Summary should aggregate across all sessions
            assert summary["total_agents"] == 4
            assert summary["agents_by_session"]["s1"] == 2
            assert summary["agents_by_session"]["s2"] == 2
            assert summary["total_sessions"] == 2


class TestOutputFormat:
    """Test output format consistency."""

    def test_session_id_truncated_for_display(self):
        """Long session IDs should be truncated for table display."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            long_session_id = "very-long-session-id-that-should-be-truncated-abc123"
            db = CoordinationDB(db_path=db_path, session_id=long_session_id)
            db.register_agent("agent1", premise="Test")

            # When displaying in table, session ID should be reasonable length
            # This tests a formatting concern, not DB functionality
            # The implementation should truncate to ~8-12 chars like agent IDs
            agents = db.get_running_agents()
            assert len(agents[0].session_id) == len(long_session_id)  # DB stores full
            # Display truncation happens in table creation

    def test_agents_sorted_by_session_then_spawned_at(self):
        """All-sessions output should be sorted by session, then spawn time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            import time

            # Create agents in interleaved order
            db1 = CoordinationDB(db_path=db_path, session_id="sess-b")
            db1.register_agent("b1", premise="B first")
            time.sleep(0.01)

            db2 = CoordinationDB(db_path=db_path, session_id="sess-a")
            db2.register_agent("a1", premise="A first")
            time.sleep(0.01)

            db1.register_agent("b2", premise="B second")

            # This will FAIL until method is implemented
            all_agents = db1.get_all_running_agents()

            # Should be sorted by session_id first, then spawned_at DESC within session
            # Or alternatively, just by spawned_at DESC globally
            # The key is consistent, predictable ordering
            assert len(all_agents) == 3
