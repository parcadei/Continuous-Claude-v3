"""Tests for Agentica Coordination Database."""

import pytest
from pathlib import Path


class TestCoordinationDB:
    """Test CoordinationDB core functionality."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_register_agent(self, db):
        """Should register agent with all fields."""
        record = db.register_agent(
            agent_id="agent-1",
            premise="You are a test agent",
            model="claude-sonnet",
            scope_keys=["func1", "func2"],
            pattern="swarm",
        )

        assert record.id == "agent-1"
        assert record.session_id == "test-session"
        assert record.premise == "You are a test agent"
        assert record.status == "running"

    def test_complete_agent(self, db):
        """Should mark agent as completed."""
        db.register_agent(agent_id="agent-1")
        db.complete_agent(agent_id="agent-1", status="completed")

        agents = db.get_running_agents()
        assert len(agents) == 0

    def test_record_task(self, db):
        """Should record completed task."""
        db.register_agent(agent_id="agent-1", pattern="jury")

        task = db.record_task(
            agent_id="agent-1",
            input_text="Is this code safe?",
            output=True,
            duration_ms=1500,
            pattern="jury",
            artifacts={"votes": [True, True, False]}
        )

        assert task.agent_id == "agent-1"
        assert task.duration_ms == 1500

    def test_session_isolation(self, tmp_path):
        """Different sessions should not see each other's agents."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        db1 = CoordinationDB(db_path=tmp_path / "test.db", session_id="session-1")
        db2 = CoordinationDB(db_path=tmp_path / "test.db", session_id="session-2")

        db1.register_agent(agent_id="agent-1")
        db2.register_agent(agent_id="agent-2")

        assert len(db1.get_running_agents()) == 1
        assert db1.get_running_agents()[0].id == "agent-1"
