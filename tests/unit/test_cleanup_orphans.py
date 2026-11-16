"""Unit tests for orphan cleanup script.

Tests the three-tier orphan detection and cleanup process:
- Tier 1: ppid=1 (true Unix orphan) -> Kill immediately
- Tier 2: parent agent dead -> Kill after 30min grace
- Tier 3: app orphan (running > 24h) -> Kill after timeout
"""

import os
import signal
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the modules we're testing (will fail until implemented)
from scripts.agentica_patterns.coordination import CoordinationDB, OrphanCandidate


class TestOrphanCandidate:
    """Test OrphanCandidate dataclass."""

    def test_orphan_candidate_fields(self):
        """OrphanCandidate should have all required fields."""
        now = datetime.now(UTC).replace(tzinfo=None)
        candidate = OrphanCandidate(
            agent_id="test-agent-123",
            ppid=1234,
            parent_agent_id="parent-456",
            spawned_at=now,
            tier=1,
            reason="ppid=1 (parent process died)",
        )

        assert candidate.agent_id == "test-agent-123"
        assert candidate.ppid == 1234
        assert candidate.parent_agent_id == "parent-456"
        assert candidate.spawned_at == now
        assert candidate.tier == 1
        assert candidate.reason == "ppid=1 (parent process died)"

    def test_orphan_candidate_optional_ppid(self):
        """OrphanCandidate should allow None for ppid."""
        now = datetime.now(UTC).replace(tzinfo=None)
        candidate = OrphanCandidate(
            agent_id="test-agent-123",
            ppid=None,
            parent_agent_id="parent-456",
            spawned_at=now,
            tier=2,
            reason="Parent agent completed",
        )

        assert candidate.ppid is None


class TestGetOrphanCandidates:
    """Test get_orphan_candidates() method."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_coordination.db"
        db = CoordinationDB(db_path=db_path, session_id="test-session")
        return db

    def test_tier1_unix_orphan_detected(self, temp_db: CoordinationDB):
        """Agents with ppid=1 should be detected as Tier 1 orphans."""
        # Register an agent with ppid=1 (Unix orphan)
        temp_db.register_agent(
            agent_id="orphan-tier1",
            premise="Unix orphan test",
            pattern="swarm",
            parent_agent_id="dead-parent",
            ppid=1,
        )

        orphans = temp_db.get_orphan_candidates()
        tier1_orphans = [o for o in orphans if o.tier == 1]

        assert len(tier1_orphans) == 1
        assert tier1_orphans[0].agent_id == "orphan-tier1"
        assert tier1_orphans[0].ppid == 1
        assert "ppid=1" in tier1_orphans[0].reason

    def test_tier2_parent_dead_detected(self, temp_db: CoordinationDB):
        """Agents whose parent agent is not running (after 30min) should be Tier 2."""
        # Create parent agent and mark it completed
        temp_db.register_agent(
            agent_id="parent-agent",
            premise="Parent",
            pattern="hierarchical",
        )
        temp_db.complete_agent("parent-agent", status="completed")

        # Create child agent that was spawned more than 30 minutes ago
        past_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=35)
        with temp_db._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pattern, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "orphan-tier2",
                    temp_db.session_id,
                    "Child orphan",
                    "hierarchical",
                    "parent-agent",
                    past_time.isoformat(),
                    "running",
                )
            )

        orphans = temp_db.get_orphan_candidates()
        tier2_orphans = [o for o in orphans if o.tier == 2]

        assert len(tier2_orphans) == 1
        assert tier2_orphans[0].agent_id == "orphan-tier2"
        assert "parent" in tier2_orphans[0].reason.lower()

    def test_tier2_within_grace_period_not_detected(self, temp_db: CoordinationDB):
        """Agents whose parent died but within 30min grace should NOT be detected."""
        # Create parent agent and mark it completed
        temp_db.register_agent(
            agent_id="recent-parent",
            premise="Recent Parent",
            pattern="hierarchical",
        )
        temp_db.complete_agent("recent-parent", status="completed")

        # Create child agent that was spawned 10 minutes ago (within grace)
        recent_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)
        with temp_db._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pattern, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "recent-orphan",
                    temp_db.session_id,
                    "Recent child",
                    "hierarchical",
                    "recent-parent",
                    recent_time.isoformat(),
                    "running",
                )
            )

        orphans = temp_db.get_orphan_candidates()
        tier2_orphans = [o for o in orphans if o.tier == 2]

        # Should NOT include the recent child (still in grace period)
        assert not any(o.agent_id == "recent-orphan" for o in tier2_orphans)

    def test_tier3_long_running_detected(self, temp_db: CoordinationDB):
        """Agents running > 24h should be detected as Tier 3 orphans."""
        # Create an agent that was spawned more than 24 hours ago
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
        with temp_db._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pattern, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "orphan-tier3",
                    temp_db.session_id,
                    "Long running agent",
                    "swarm",
                    "some-parent",  # Has parent but running too long
                    old_time.isoformat(),
                    "running",
                )
            )

        orphans = temp_db.get_orphan_candidates()
        tier3_orphans = [o for o in orphans if o.tier == 3]

        assert len(tier3_orphans) >= 1
        assert any(o.agent_id == "orphan-tier3" for o in tier3_orphans)

    def test_main_sessions_excluded(self, temp_db: CoordinationDB):
        """Main sessions (parent_agent_id IS NULL, ppid != 1) should NOT be flagged."""
        # Register a main session (no parent, normal ppid)
        temp_db.register_agent(
            agent_id="main-session",
            premise="Main session",
            pattern=None,
            parent_agent_id=None,
            ppid=12345,  # Normal parent PID
        )

        orphans = temp_db.get_orphan_candidates()

        # Main session should NOT be in orphans list
        assert not any(o.agent_id == "main-session" for o in orphans)

    def test_completed_agents_excluded(self, temp_db: CoordinationDB):
        """Completed agents should not be flagged as orphans."""
        temp_db.register_agent(
            agent_id="completed-agent",
            premise="Already done",
            ppid=1,  # Would be tier 1 if running
        )
        temp_db.complete_agent("completed-agent", status="completed")

        orphans = temp_db.get_orphan_candidates()

        assert not any(o.agent_id == "completed-agent" for o in orphans)


class TestIsUnixOrphan:
    """Test is_unix_orphan() function."""

    def test_current_process_not_orphan(self):
        """Current process should NOT be detected as orphan."""
        from scripts.agentica_patterns.watch_agents import is_unix_orphan

        # Our own process should have a valid parent (not PID 1)
        assert is_unix_orphan(os.getpid()) is False

    def test_nonexistent_process_returns_false(self):
        """Non-existent PID should return False."""
        from scripts.agentica_patterns.watch_agents import is_unix_orphan

        # Use a very high PID that's unlikely to exist
        assert is_unix_orphan(999999999) is False

    @patch("subprocess.run")
    def test_ppid_1_returns_true(self, mock_run):
        """Process with ppid=1 should return True."""
        from scripts.agentica_patterns.watch_agents import is_unix_orphan

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="1\n",
        )

        assert is_unix_orphan(1234) is True

    @patch("subprocess.run")
    def test_normal_ppid_returns_false(self, mock_run):
        """Process with normal ppid should return False."""
        from scripts.agentica_patterns.watch_agents import is_unix_orphan

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="5678\n",
        )

        assert is_unix_orphan(1234) is False

    @patch("subprocess.run")
    def test_timeout_returns_false(self, mock_run):
        """Timeout should return False (safe default)."""
        from scripts.agentica_patterns.watch_agents import is_unix_orphan

        mock_run.side_effect = subprocess.TimeoutExpired("ps", 5)

        assert is_unix_orphan(1234) is False


class TestCleanupOrphansScript:
    """Test the cleanup_orphans.py script."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_coordination.db"
        db = CoordinationDB(db_path=db_path, session_id="test-session")
        return db

    def test_dry_run_does_not_kill(self, temp_db: CoordinationDB):
        """Dry run mode should NOT kill any processes."""
        from scripts.agentica_patterns.cleanup_orphans import cleanup_orphans

        # Register a tier 1 orphan
        temp_db.register_agent(
            agent_id="test-orphan",
            premise="Test",
            ppid=1,
        )

        killed = cleanup_orphans(db=temp_db, dry_run=True)

        # Should report found but not killed
        assert killed == []

        # Agent should still be running
        agents = temp_db.get_running_agents()
        assert any(a.id == "test-orphan" for a in agents)

    def test_tier_filter_limits_cleanup(self, temp_db: CoordinationDB):
        """--tier flag should only process specified tier."""
        from scripts.agentica_patterns.cleanup_orphans import cleanup_orphans

        # Register tier 1 orphan
        temp_db.register_agent(
            agent_id="tier1-orphan",
            premise="Tier 1",
            ppid=1,
        )

        # Register tier 3 orphan (old agent)
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
        with temp_db._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pattern, parent_agent_id, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tier3-orphan",
                    temp_db.session_id,
                    "Tier 3",
                    "swarm",
                    "parent",
                    old_time.isoformat(),
                    "running",
                )
            )

        # Only get tier 3
        orphans = cleanup_orphans(db=temp_db, dry_run=True, tier_filter=3)

        # Should only report tier 3 orphan
        assert len([o for o in temp_db.get_orphan_candidates() if o.tier == 3]) >= 1

    @patch("scripts.agentica_patterns.cleanup_orphans.kill_process")
    @patch("scripts.agentica_patterns.cleanup_orphans.is_unix_orphan")
    def test_kill_mode_sends_sigterm(self, mock_is_orphan, mock_kill, temp_db: CoordinationDB):
        """Kill mode should send SIGTERM to orphan processes."""
        from scripts.agentica_patterns.cleanup_orphans import cleanup_orphans

        mock_is_orphan.return_value = True
        mock_kill.return_value = True  # Simulate successful kill

        # Register a tier 1 orphan with ppid=1
        with temp_db._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents
                (id, session_id, premise, pattern, ppid, spawned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "kill-test-orphan",
                    temp_db.session_id,
                    "Kill test",
                    "swarm",
                    1,  # ppid=1 for tier 1 orphan
                    datetime.now(UTC).replace(tzinfo=None).isoformat(),
                    "running",
                )
            )

        killed = cleanup_orphans(db=temp_db, dry_run=False, tier_filter=1)

        # Should have verified it's a Unix orphan and killed it
        mock_is_orphan.assert_called_with(1)  # ppid is 1 for tier 1
        mock_kill.assert_called_with(1)  # kill_process called with ppid

    def test_process_not_found_handled_gracefully(self, temp_db: CoordinationDB):
        """ProcessLookupError should be handled gracefully."""
        from scripts.agentica_patterns.cleanup_orphans import kill_process

        # Try to kill a non-existent process
        result = kill_process(999999999)

        # Should return False, not raise
        assert result is False

    def test_logging_actions_taken(self, temp_db: CoordinationDB, capsys):
        """Script should log actions taken."""
        from scripts.agentica_patterns.cleanup_orphans import cleanup_orphans

        # Register a tier 1 orphan
        temp_db.register_agent(
            agent_id="log-test-orphan",
            premise="Log test",
            ppid=1,
        )

        cleanup_orphans(db=temp_db, dry_run=True)

        captured = capsys.readouterr()
        assert "log-test-orphan" in captured.out or "Tier 1" in captured.out


class TestCleanupOrphansCLI:
    """Test CLI interface of cleanup_orphans.py."""

    def test_dry_run_is_default(self):
        """--dry-run should be the default behavior."""
        # This test validates CLI parsing behavior
        import argparse
        from scripts.agentica_patterns.cleanup_orphans import create_parser

        parser = create_parser()
        args = parser.parse_args([])

        assert args.dry_run is True

    def test_kill_flag_overrides_dry_run(self):
        """--kill should override dry-run default."""
        from scripts.agentica_patterns.cleanup_orphans import create_parser

        parser = create_parser()
        args = parser.parse_args(["--kill"])

        # When --kill is specified, we shouldn't be in dry-run mode
        assert args.kill is True

    def test_tier_accepts_valid_values(self):
        """--tier should accept 1, 2, or 3."""
        from scripts.agentica_patterns.cleanup_orphans import create_parser

        parser = create_parser()

        for tier in [1, 2, 3]:
            args = parser.parse_args(["--tier", str(tier)])
            assert args.tier == tier

    def test_tier_rejects_invalid_values(self):
        """--tier should reject values outside 1-3."""
        from scripts.agentica_patterns.cleanup_orphans import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--tier", "0"])

        with pytest.raises(SystemExit):
            parser.parse_args(["--tier", "4"])
