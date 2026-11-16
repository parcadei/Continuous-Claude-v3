"""E2E Integration Tests for Orphan Detection.

Tests the complete orphan detection and cleanup pipeline:
1. Register agents with pid/ppid in coordination DB
2. Run find_orphans() and verify classification
3. Run cleanup_orphans.py --dry-run and verify output
4. Verify watch_agents.py --orphans shows results

Phase 14 of resource-limits-plan.md
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

# Add project root to path for imports
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.agentica.coordination import CoordinationDB, OrphanCandidate
from scripts.agentica.watch_agents import is_unix_orphan


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def project_dir() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database directory."""
    db_dir = tmp_path / ".claude" / "cache" / "agentica-coordination"
    db_dir.mkdir(parents=True)
    return db_dir / "coordination.db"


@pytest.fixture
def db(temp_db_path: Path) -> CoordinationDB:
    """Create a CoordinationDB with a temp database."""
    session_id = f"test-{uuid4().hex[:8]}"
    return CoordinationDB(db_path=temp_db_path, session_id=session_id)


# ============================================================================
# Test: is_unix_orphan function
# ============================================================================


class TestIsUnixOrphan:
    """Test the is_unix_orphan helper function."""

    def test_current_process_not_orphan(self):
        """Current process should NOT be an orphan."""
        assert is_unix_orphan(os.getpid()) is False

    def test_init_process_is_special(self):
        """PID 1 itself should not be considered an orphan."""
        # PID 1 doesn't have ppid=1, it's init/launchd itself
        # is_unix_orphan checks if the PROCESS's parent is 1
        result = is_unix_orphan(1)
        # PID 1's parent is typically 0, not 1
        assert result is False

    def test_nonexistent_process_not_orphan(self):
        """Non-existent process should return False."""
        # Use a very high PID that's unlikely to exist
        assert is_unix_orphan(999999999) is False

    def test_invalid_pid_not_orphan(self):
        """Invalid PIDs should return False."""
        assert is_unix_orphan(0) is False
        assert is_unix_orphan(-1) is False


# ============================================================================
# Test: Register agents with pid/ppid
# ============================================================================


class TestAgentRegistrationWithPid:
    """Test that agents can be registered with pid/ppid for orphan detection."""

    def test_register_agent_with_pid_ppid(self, db: CoordinationDB):
        """Agents can be registered with pid and ppid."""
        current_pid = os.getpid()
        current_ppid = os.getppid()

        record = db.register_agent(
            agent_id="test-agent-1",
            premise="Test agent",
            pid=current_pid,
            ppid=current_ppid,
        )

        assert record.pid == current_pid
        assert record.ppid == current_ppid
        assert record.status == "running"

    def test_register_agent_without_pid(self, db: CoordinationDB):
        """Agents can be registered without pid (backwards compatible)."""
        record = db.register_agent(
            agent_id="test-agent-2",
            premise="Test agent without PID",
        )

        assert record.pid is None
        assert record.ppid is None
        assert record.status == "running"

    def test_agent_record_preserves_pid_ppid(self, db: CoordinationDB):
        """PID and PPID are preserved when querying agents."""
        db.register_agent(
            agent_id="test-agent-3",
            premise="Test",
            pid=12345,
            ppid=12344,
        )

        agents = db.get_running_agents()
        agent = next(a for a in agents if a.id == "test-agent-3")

        assert agent.pid == 12345
        assert agent.ppid == 12344


# ============================================================================
# Test: find_orphans() three-tier classification
# ============================================================================


class TestFindOrphansClassification:
    """Test the three-tier orphan classification system."""

    def test_tier1_unix_orphan_ppid_1(self, db: CoordinationDB):
        """Tier 1: Agent with ppid=1 is classified as Unix orphan."""
        db.register_agent(
            agent_id="orphan-tier1",
            premise="Unix orphan simulation",
            pid=99999,
            ppid=1,  # ppid=1 means parent died
            parent_agent_id=None,  # Main session
        )

        orphans = db.find_orphans()

        tier1 = [o for o in orphans if o.tier == 1]
        assert len(tier1) >= 1
        assert any(o.agent_id == "orphan-tier1" for o in tier1)
        assert tier1[0].reason == "ppid=1 (parent process died)"

    def test_tier2_parent_agent_dead(self, db: CoordinationDB, temp_db_path: Path):
        """Tier 2: Agent whose parent agent is dead (30min grace expired)."""
        # Register parent agent and mark as completed
        db.register_agent(
            agent_id="parent-agent",
            premise="Parent",
            pattern="hierarchical",
        )
        db.complete_agent("parent-agent", status="completed")

        # Register child agent with old spawn time (>30min)
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        old_time = (datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=45)).isoformat()
        conn.execute("""
            INSERT INTO agents (id, session_id, premise, parent_agent_id, spawned_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("orphan-tier2", db.session_id, "Child orphan", "parent-agent", old_time, "running"))
        conn.commit()
        conn.close()

        orphans = db.find_orphans()

        tier2 = [o for o in orphans if o.tier == 2]
        assert len(tier2) >= 1
        assert any(o.agent_id == "orphan-tier2" for o in tier2)

    def test_tier3_app_orphan_running_24h(self, db: CoordinationDB, temp_db_path: Path):
        """Tier 3: Agent running >24h with parent is classified as app orphan."""
        # Register a parent agent (running)
        db.register_agent(
            agent_id="long-running-parent",
            premise="Long running parent",
        )

        # Register child agent with very old spawn time (>24h)
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        old_time = (datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)).isoformat()
        conn.execute("""
            INSERT INTO agents (id, session_id, premise, parent_agent_id, spawned_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("orphan-tier3", db.session_id, "Long running child", "long-running-parent", old_time, "running"))
        conn.commit()
        conn.close()

        orphans = db.find_orphans()

        tier3 = [o for o in orphans if o.tier == 3]
        assert len(tier3) >= 1
        assert any(o.agent_id == "orphan-tier3" for o in tier3)

    def test_main_session_not_orphan(self, db: CoordinationDB):
        """Main sessions (parent_agent_id IS NULL, ppid != 1) should NOT be orphans."""
        # Register main session agent (no parent)
        db.register_agent(
            agent_id="main-session",
            premise="Main session - should not be orphan",
            pid=os.getpid(),
            ppid=os.getppid(),  # Not 1
            parent_agent_id=None,  # No parent - this is a main session
        )

        orphans = db.find_orphans()

        # Main session should NOT appear in orphans
        main_in_orphans = any(o.agent_id == "main-session" for o in orphans)
        assert not main_in_orphans, "Main session was incorrectly classified as orphan"

    def test_running_child_with_running_parent_not_orphan(self, db: CoordinationDB):
        """Child agent with running parent should NOT be classified as orphan."""
        # Register parent (running)
        db.register_agent(
            agent_id="active-parent",
            premise="Active parent",
        )

        # Register child (running, with parent_agent_id)
        db.register_agent(
            agent_id="active-child",
            premise="Active child",
            parent_agent_id="active-parent",
        )

        orphans = db.find_orphans()

        # Neither should be orphans
        assert not any(o.agent_id == "active-parent" for o in orphans)
        assert not any(o.agent_id == "active-child" for o in orphans)


# ============================================================================
# Test: cleanup_orphans.py --dry-run
# ============================================================================


class TestCleanupOrphansScript:
    """Test the cleanup_orphans.py CLI script."""

    def test_dry_run_lists_orphans(self, project_dir: Path, temp_db_path: Path):
        """cleanup_orphans.py --dry-run should list orphans without killing."""
        # Create a DB with an orphan
        db = CoordinationDB(db_path=temp_db_path, session_id="test")
        db.register_agent(
            agent_id="orphan-for-cleanup",
            premise="Orphan for cleanup test",
            ppid=1,  # Tier 1 orphan
        )

        # Run cleanup script in dry-run mode
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db_path.parent.parent.parent.parent)

        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/cleanup_orphans.py", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=30
        )

        # Should show the orphan
        assert "orphan-for-cleanup" in result.stdout or "Tier 1" in result.stdout
        assert "DRY-RUN" in result.stdout

        # Agent should still be running (not killed)
        agents = db.get_running_agents()
        assert any(a.id == "orphan-for-cleanup" for a in agents)

    def test_tier_filter(self, project_dir: Path, temp_db_path: Path):
        """cleanup_orphans.py --tier 1 should only show tier 1 orphans."""
        db = CoordinationDB(db_path=temp_db_path, session_id="test")

        # Create tier 1 orphan
        db.register_agent(agent_id="tier1-orphan", premise="Tier 1", ppid=1)

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db_path.parent.parent.parent.parent)

        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/cleanup_orphans.py",
             "--dry-run", "--tier", "1"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=30
        )

        assert "Tier 1" in result.stdout or "tier1-orphan" in result.stdout

    def test_no_orphans_message(self, project_dir: Path, temp_db_path: Path):
        """cleanup_orphans.py should report when no orphans found."""
        # Create DB with no orphans
        db = CoordinationDB(db_path=temp_db_path, session_id="test")
        db.register_agent(
            agent_id="healthy-agent",
            premise="Healthy agent",
            ppid=os.getppid(),  # Not 1
            parent_agent_id=None,  # Main session
        )

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db_path.parent.parent.parent.parent)

        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/cleanup_orphans.py", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=30
        )

        assert "No orphan" in result.stdout or "0 orphan" in result.stdout


# ============================================================================
# Test: watch_agents.py --orphans
# ============================================================================


class TestWatchAgentsOrphans:
    """Test the watch_agents.py --orphans flag."""

    def test_orphans_flag_shows_orphans(self, project_dir: Path, temp_db_path: Path):
        """watch_agents.py --orphans should display orphan candidates."""
        db = CoordinationDB(db_path=temp_db_path, session_id="test")
        db.register_agent(
            agent_id="watch-test-orphan",
            premise="Orphan for watch test",
            ppid=1,
        )

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db_path.parent.parent.parent.parent)

        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/watch_agents.py", "--orphans"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=30
        )

        # Should show the orphan
        assert "watch-test-orphan" in result.stdout or "Tier 1" in result.stdout

    def test_orphans_json_output(self, project_dir: Path, temp_db_path: Path):
        """watch_agents.py --orphans --json should output JSON format."""
        db = CoordinationDB(db_path=temp_db_path, session_id="test")
        db.register_agent(
            agent_id="json-orphan",
            premise="Orphan for JSON test",
            ppid=1,
        )

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db_path.parent.parent.parent.parent)

        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/watch_agents.py",
             "--orphans", "--json"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=30
        )

        # Should be valid JSON
        try:
            data = json.loads(result.stdout)
            assert isinstance(data, list)
            # Should have our orphan
            assert any(o.get("agent_id") == "json-orphan" for o in data)
            # Should have tier field
            assert all("tier" in o for o in data)
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {result.stdout}")

    def test_no_orphans_message_watch(self, project_dir: Path, temp_db_path: Path):
        """watch_agents.py --orphans should report when no orphans."""
        db = CoordinationDB(db_path=temp_db_path, session_id="test")
        # Register non-orphan agent
        db.register_agent(
            agent_id="non-orphan",
            premise="Not an orphan",
            ppid=os.getppid(),
            parent_agent_id=None,
        )

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db_path.parent.parent.parent.parent)

        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/watch_agents.py", "--orphans"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=30
        )

        assert "No orphan" in result.stdout or "found" in result.stdout.lower()


# ============================================================================
# Test: Full Orphan Detection Pipeline
# ============================================================================


class TestFullOrphanPipeline:
    """Test the complete orphan detection and cleanup pipeline."""

    def test_full_orphan_lifecycle(self, project_dir: Path, temp_db_path: Path):
        """Test full lifecycle: register -> detect -> report -> (mock) cleanup."""
        db = CoordinationDB(db_path=temp_db_path, session_id="test")

        # Step 1: Register a parent agent
        db.register_agent(
            agent_id="lifecycle-parent",
            premise="Parent that will complete",
            pattern="hierarchical",
        )

        # Step 2: Register child agents
        db.register_agent(
            agent_id="lifecycle-child-1",
            premise="Child 1",
            parent_agent_id="lifecycle-parent",
        )
        db.register_agent(
            agent_id="lifecycle-child-2",
            premise="Child 2",
            parent_agent_id="lifecycle-parent",
        )

        # Step 3: Complete parent (children now potential orphans)
        db.complete_agent("lifecycle-parent", status="completed")

        # Step 4: Find orphans - children won't be orphans yet (30min grace)
        orphans = db.find_orphans()
        # At this point, children are NOT orphans (need 30min grace)
        assert not any(o.agent_id in ("lifecycle-child-1", "lifecycle-child-2") for o in orphans)

        # Step 5: Simulate time passing by backdating spawn time
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        old_time = (datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=45)).isoformat()
        conn.execute(
            "UPDATE agents SET spawned_at = ? WHERE id IN (?, ?)",
            (old_time, "lifecycle-child-1", "lifecycle-child-2")
        )
        conn.commit()
        conn.close()

        # Step 6: Now find orphans - children should be tier 2
        orphans = db.find_orphans()
        tier2 = [o for o in orphans if o.tier == 2]
        assert len(tier2) >= 2

        # Step 7: Verify cleanup script would find them
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db_path.parent.parent.parent.parent)

        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/cleanup_orphans.py",
             "--dry-run", "--tier", "2"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=30
        )

        assert "lifecycle-child-1" in result.stdout or "Tier 2" in result.stdout

    def test_multi_tier_detection(self, project_dir: Path, temp_db_path: Path):
        """Test that all three tiers are detected simultaneously."""
        db = CoordinationDB(db_path=temp_db_path, session_id="test")

        # Tier 1: Unix orphan
        db.register_agent(
            agent_id="multi-tier1",
            premise="Tier 1 Unix orphan",
            ppid=1,
        )

        # Setup for Tier 2: Complete parent, backdate child
        db.register_agent(
            agent_id="multi-parent",
            premise="Parent",
        )
        db.complete_agent("multi-parent")

        # Tier 3: Long running with living parent - register parent first
        db.register_agent(agent_id="multi-tier3-parent", premise="Living parent")

        # Now use raw SQL to backdate agents for tier 2 and 3 testing
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        old_time_30m = (datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=45)).isoformat()
        old_time_24h = (datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)).isoformat()

        # Tier 2 child (parent is dead)
        conn.execute("""
            INSERT INTO agents (id, session_id, premise, parent_agent_id, spawned_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("multi-tier2", db.session_id, "Tier 2 orphan", "multi-parent", old_time_30m, "running"))

        # Tier 3 child (parent alive but running >24h)
        conn.execute("""
            INSERT INTO agents (id, session_id, premise, parent_agent_id, spawned_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("multi-tier3", db.session_id, "Tier 3 orphan", "multi-tier3-parent", old_time_24h, "running"))

        conn.commit()
        conn.close()

        # Verify all tiers detected
        orphans = db.find_orphans()

        tier1 = [o for o in orphans if o.tier == 1]
        tier2 = [o for o in orphans if o.tier == 2]
        tier3 = [o for o in orphans if o.tier == 3]

        assert len(tier1) >= 1, "Should have tier 1 orphan"
        assert len(tier2) >= 1, "Should have tier 2 orphan"
        assert len(tier3) >= 1, "Should have tier 3 orphan"
