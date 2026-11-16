"""Tests for three-tier orphan detection in CoordinationDB.

Phase 8: Dynamic Resource Limits & Orphan Detection

Tier 1: Unix orphan (pid's ppid=1) - requires external check via is_unix_orphan()
Tier 2: Parent agent dead (parent status != 'running')
Tier 3: App orphan (no 'done' broadcast, older than 24h threshold)
"""

import pytest
from datetime import datetime, timedelta, UTC
from pathlib import Path


class TestOrphanCandidate:
    """Test OrphanCandidate dataclass."""

    def test_import_orphan_candidate(self):
        """OrphanCandidate should be importable from coordination module."""
        from scripts.agentica.coordination import OrphanCandidate

        candidate = OrphanCandidate(
            agent_id="test-agent",
            ppid=1234,  # Parent process ID for orphan detection
            parent_agent_id="parent-1",
            spawned_at=datetime.now(UTC).replace(tzinfo=None),
            tier=1,
            reason="Test reason",
        )

        assert candidate.agent_id == "test-agent"
        assert candidate.ppid == 1234
        assert candidate.tier == 1


class TestFindOrphans:
    """Test find_orphans() method for three-tier orphan detection."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database with ppid support."""
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_find_orphans_returns_list(self, db):
        """find_orphans() should return a list."""
        orphans = db.find_orphans()
        assert isinstance(orphans, list)

    def test_tier1_unix_orphan_detection(self, db):
        """Tier 1: Agents whose process's ppid=1 should be detected as Unix orphans.

        Note: Tier 1 detection requires an external is_unix_orphan(pid) check
        to verify the process's actual parent. This test verifies the dataclass
        can represent tier 1 orphans correctly.
        """
        from scripts.agentica.coordination import OrphanCandidate

        # Tier 1 orphans are detected externally via is_unix_orphan(pid)
        # The find_orphans() method focuses on tier 2 and tier 3 detection
        # which can be done purely from database state.
        #
        # For unit testing, we verify the dataclass works correctly
        candidate = OrphanCandidate(
            agent_id="unix-orphan",
            ppid=1,  # Unix orphan indicator - parent is init/launchd
            parent_agent_id="dead-parent",
            spawned_at=datetime.now(UTC).replace(tzinfo=None),
            tier=1,
            reason="ppid=1 (parent process died)",
        )

        assert candidate.tier == 1
        assert candidate.ppid == 1
        assert "ppid=1" in candidate.reason.lower()

    def test_tier2_parent_agent_dead(self, db):
        """Tier 2: Agents whose parent agent is no longer running.

        Grace period of 30 minutes before being flagged.
        """
        from scripts.agentica.coordination import OrphanCandidate

        # Register parent agent and mark it completed
        db.register_agent(agent_id="parent-agent", premise="Parent")
        db.complete_agent(agent_id="parent-agent", status="completed")

        # Register child agent (spawned 35 minutes ago to exceed grace period)
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=35)
        with db._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pid, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "child-orphan",
                    db.session_id,
                    "Child of dead parent",
                    9999,
                    "parent-agent",
                    old_time.isoformat(),
                    "running",
                )
            )

        orphans = db.find_orphans()

        tier2_orphans = [o for o in orphans if o.tier == 2]
        assert len(tier2_orphans) == 1
        assert tier2_orphans[0].agent_id == "child-orphan"
        assert tier2_orphans[0].parent_agent_id == "parent-agent"
        assert "parent" in tier2_orphans[0].reason.lower()

    def test_tier2_within_grace_period_not_flagged(self, db):
        """Tier 2: Agents within 30-minute grace period should NOT be flagged."""
        # Register parent agent and mark it completed
        db.register_agent(agent_id="parent-agent", premise="Parent")
        db.complete_agent(agent_id="parent-agent", status="completed")

        # Register child agent (spawned 10 minutes ago - within grace period)
        recent_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)
        with db._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pid, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "recent-child",
                    db.session_id,
                    "Recent child",
                    9999,
                    "parent-agent",
                    recent_time.isoformat(),
                    "running",
                )
            )

        orphans = db.find_orphans()

        tier2_orphans = [o for o in orphans if o.tier == 2]
        assert len(tier2_orphans) == 0

    def test_tier3_app_orphan_running_too_long(self, db):
        """Tier 3: Agents running > 24 hours without completion.

        These are "app orphans" - technically valid but likely stuck.
        """
        from scripts.agentica.coordination import OrphanCandidate

        # Register parent (still running)
        db.register_agent(agent_id="parent-agent", premise="Parent still running")

        # Register child agent spawned 25 hours ago
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
        with db._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pid, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ancient-agent",
                    db.session_id,
                    "Very old agent",
                    9999,
                    "parent-agent",
                    old_time.isoformat(),
                    "running",
                )
            )

        orphans = db.find_orphans()

        tier3_orphans = [o for o in orphans if o.tier == 3]
        assert len(tier3_orphans) == 1
        assert tier3_orphans[0].agent_id == "ancient-agent"
        assert "24h" in tier3_orphans[0].reason.lower() or ">24" in tier3_orphans[0].reason

    def test_tier3_recent_agent_not_flagged(self, db):
        """Tier 3: Recently spawned agents should NOT be flagged."""
        db.register_agent(agent_id="parent-agent", premise="Parent")
        db.register_agent(
            agent_id="recent-agent",
            premise="Recent agent",
            parent_agent_id="parent-agent",
        )

        orphans = db.find_orphans()

        tier3_orphans = [o for o in orphans if o.tier == 3]
        assert len(tier3_orphans) == 0

    def test_main_sessions_not_flagged(self, db):
        """Main sessions (parent_agent_id IS NULL) should NOT be flagged as orphans.

        CRITICAL: We must not accidentally kill main sessions.
        """
        # Register a "main" agent with no parent
        db.register_agent(
            agent_id="main-session",
            premise="Main session agent",
            parent_agent_id=None,  # No parent = main session
        )

        orphans = db.find_orphans()

        # Main session should never appear in orphan list
        assert not any(o.agent_id == "main-session" for o in orphans)

    def test_completed_agents_not_flagged(self, db):
        """Completed agents should NOT be flagged as orphans."""
        db.register_agent(
            agent_id="completed-agent",
            premise="Already done",
            pid=1234,
            parent_agent_id="some-parent",
        )
        db.complete_agent("completed-agent", status="completed")

        orphans = db.find_orphans()

        assert not any(o.agent_id == "completed-agent" for o in orphans)

    def test_orphan_detection_across_sessions(self, tmp_path):
        """find_orphans() should detect tier 2/3 orphans across ALL sessions."""
        from scripts.agentica.coordination import CoordinationDB

        db1 = CoordinationDB(db_path=tmp_path / "test.db", session_id="session-1")
        db2 = CoordinationDB(db_path=tmp_path / "test.db", session_id="session-2")

        # Register parent and complete it
        db1.register_agent(agent_id="parent-1", premise="Parent")
        db1.complete_agent("parent-1", status="completed")

        db2.register_agent(agent_id="parent-2", premise="Parent")
        db2.complete_agent("parent-2", status="completed")

        # Register tier 2 orphan in session 1 (35 min old)
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=35)
        with db1._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pid, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("orphan-s1", "session-1", "Orphan 1", 1111, "parent-1", old_time.isoformat(), "running")
            )
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pid, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("orphan-s2", "session-2", "Orphan 2", 2222, "parent-2", old_time.isoformat(), "running")
            )

        # Query from any db instance should find both
        orphans = db1.find_orphans()

        orphan_ids = [o.agent_id for o in orphans]
        assert "orphan-s1" in orphan_ids
        assert "orphan-s2" in orphan_ids


class TestRegisterAgentWithPid:
    """Test that register_agent accepts pid parameter."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_register_agent_with_pid(self, db):
        """register_agent should accept and store pid."""
        import os

        record = db.register_agent(
            agent_id="agent-with-pid",
            premise="Agent with process ID",
            pid=os.getpid(),  # Current PID
        )

        assert record.pid == os.getpid()

    def test_register_agent_pid_default_none(self, db):
        """register_agent should default pid to None if not provided."""
        record = db.register_agent(
            agent_id="agent-no-pid",
            premise="Agent without pid",
        )

        assert record.pid is None
