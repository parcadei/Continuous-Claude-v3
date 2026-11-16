"""Tests for Agent PID Tracking (Phase 7).

TDD tests for adding pid column to agents table:
1. Schema includes pid column
2. register_agent accepts optional pid parameter
3. AgentRecord includes pid field
4. Migration adds pid column to existing databases
"""

import os
import sqlite3
import pytest
from pathlib import Path


class TestAgentPidTracking:
    """Test pid column in agents table."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_schema_includes_pid_column(self, db):
        """Schema should include pid INTEGER column."""
        with db._get_conn() as conn:
            cursor = conn.execute("PRAGMA table_info(agents)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "pid" in columns, "Schema should include 'pid' column"
        assert columns["pid"] == "INTEGER", "pid column should be INTEGER type"

    def test_register_agent_without_pid(self, db):
        """register_agent should work without pid (backward compatible)."""
        record = db.register_agent(
            agent_id="agent-1",
            premise="Test agent",
        )

        assert record.id == "agent-1"
        assert record.pid is None  # Should have pid attribute, default None

    def test_register_agent_with_pid(self, db):
        """register_agent should accept and store pid."""
        current_pid = os.getpid()

        record = db.register_agent(
            agent_id="agent-2",
            premise="Test agent with PID",
            pid=current_pid,
        )

        assert record.id == "agent-2"
        assert record.pid == current_pid

    def test_pid_persisted_to_database(self, db):
        """pid should be stored in database."""
        test_pid = 12345

        db.register_agent(
            agent_id="agent-3",
            premise="Test persistence",
            pid=test_pid,
        )

        # Query directly to verify storage
        with db._get_conn() as conn:
            row = conn.execute(
                "SELECT pid FROM agents WHERE id = ?",
                ("agent-3",)
            ).fetchone()

        assert row is not None
        assert row[0] == test_pid

    def test_pid_returned_in_get_running_agents(self, db):
        """get_running_agents should return agents with pid field."""
        test_pid = 54321

        db.register_agent(
            agent_id="agent-4",
            premise="Test retrieval",
            pid=test_pid,
        )

        agents = db.get_running_agents()
        assert len(agents) == 1
        assert agents[0].pid == test_pid

    def test_pid_returned_in_get_all_running_agents(self, db):
        """get_all_running_agents should return agents with pid field."""
        test_pid = 99999

        db.register_agent(
            agent_id="agent-5",
            premise="Test global retrieval",
            pid=test_pid,
        )

        agents = db.get_all_running_agents()
        assert len(agents) >= 1
        matching = [a for a in agents if a.id == "agent-5"]
        assert len(matching) == 1
        assert matching[0].pid == test_pid


class TestPidColumnMigration:
    """Test migration for adding pid column to existing databases."""

    def test_migration_adds_pid_to_existing_db(self, tmp_path):
        """Migration should add pid column to databases without it."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        db_path = tmp_path / "legacy.db"

        # Create a "legacy" database without pid column
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE agents (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                premise TEXT,
                model TEXT,
                scope_keys TEXT,
                pattern TEXT,
                parent_agent_id TEXT,
                spawned_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT DEFAULT 'running',
                error_message TEXT
            );

            INSERT INTO agents (id, session_id, spawned_at, status)
            VALUES ('old-agent', 'old-session', '2025-01-01T00:00:00', 'running');
        """)
        conn.commit()
        conn.close()

        # Verify pid column doesn't exist yet
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA table_info(agents)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "pid" not in columns, "Test setup: pid should not exist in legacy DB"

        # Now initialize CoordinationDB - should run migration
        db = CoordinationDB(db_path=db_path, session_id="new-session")

        # Verify pid column now exists
        with db._get_conn() as conn:
            cursor = conn.execute("PRAGMA table_info(agents)")
            columns = {row[1] for row in cursor.fetchall()}

        assert "pid" in columns, "Migration should add pid column"

        # Verify existing data is preserved
        with db._get_conn() as conn:
            row = conn.execute(
                "SELECT id, session_id FROM agents WHERE id = ?",
                ("old-agent",)
            ).fetchone()

        assert row is not None
        assert row[0] == "old-agent"
        assert row[1] == "old-session"

    def test_migration_idempotent(self, tmp_path):
        """Running migration multiple times should be safe."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        db_path = tmp_path / "idempotent.db"

        # Create DB multiple times
        db1 = CoordinationDB(db_path=db_path, session_id="session-1")
        db1.register_agent(agent_id="agent-1", pid=111)

        db2 = CoordinationDB(db_path=db_path, session_id="session-2")
        db2.register_agent(agent_id="agent-2", pid=222)

        db3 = CoordinationDB(db_path=db_path, session_id="session-3")

        # Verify both agents still exist with correct pids
        with db3._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, pid FROM agents ORDER BY id"
            ).fetchall()

        assert len(rows) == 2
        assert rows[0][0] == "agent-1"
        assert rows[0][1] == 111
        assert rows[1][0] == "agent-2"
        assert rows[1][1] == 222
