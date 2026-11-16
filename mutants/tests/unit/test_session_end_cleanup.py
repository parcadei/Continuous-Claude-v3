"""Tests for SessionEnd Cleanup Hook (Phase 19.5).

These tests verify that the SessionEnd cleanup hook correctly:
1. Shell wrapper and TypeScript handler exist
2. Creates orphaned_agents table if not exists
3. Marks agents without 'done' broadcast as orphaned
4. Does NOT mark completed agents (those with 'done' broadcast)
5. Orphaning is session-specific (tracks session_id)
6. Graceful handling when no swarm, DB missing, etc.
7. Always returns continue (never blocks)
8. Is registered in settings.json

SessionEnd input structure:
```typescript
interface SessionEndInput {
    session_id: string;
}
```

Tests are designed to FAIL initially (TDD approach) until Phase 19.5 is implemented.

See plan: thoughts/shared/plans/2025-12-28-user-triggered-agentica.md (Phase 19.5)
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestSessionEndHookFiles:
    """Tests for SessionEnd cleanup hook file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper exists at expected path."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}. "
            "Create .claude/hooks/session-end-cleanup-swarms.sh"
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}. "
            "Run: chmod +x .claude/hooks/session-end-cleanup-swarms.sh"
        )

    def test_typescript_handler_exists(self, hooks_dir: Path) -> None:
        """TypeScript handler exists at expected path."""
        ts_handler = hooks_dir / "src" / "session-end-cleanup-swarms.ts"

        assert ts_handler.exists(), (
            f"TypeScript handler not found: {ts_handler}. "
            "Create .claude/hooks/src/session-end-cleanup-swarms.ts"
        )

    def test_shell_wrapper_invokes_typescript(self, hooks_dir: Path) -> None:
        """Shell wrapper invokes TypeScript via npx tsx or compiled JS."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        # Should call npx tsx with the TypeScript file or node with compiled JS
        has_tsx = "npx tsx" in content
        has_node = "node dist/" in content
        has_reference = "session-end-cleanup-swarms" in content

        assert has_tsx or has_node, (
            "Shell wrapper should invoke TypeScript via 'npx tsx' or compiled JS via 'node dist/'. "
            f"Content: {content}"
        )
        assert has_reference, (
            "Shell wrapper should reference session-end-cleanup-swarms handler. "
            f"Content: {content}"
        )


class TestCreatesOrphanedAgentsTable:
    """Tests for creating orphaned_agents table if not exists."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_db_no_orphan_table(self) -> tuple[Path, str]:
        """Create project with DB but without orphaned_agents table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            # Create only broadcasts and completed_tasks tables (no orphaned_agents)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    sender_agent TEXT NOT NULL,
                    broadcast_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_broadcasts_swarm
                    ON broadcasts(swarm_id, created_at);

                CREATE TABLE IF NOT EXISTS completed_tasks (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );
            """)

            swarm_id = "test-swarm-orphan-table"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # Add an incomplete agent (started task but no 'done' broadcast)
            conn.execute(
                "INSERT INTO completed_tasks VALUES (?, ?, ?)",
                (swarm_id, "incomplete-agent", now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_creates_orphaned_agents_table(
        self,
        hooks_dir: Path,
        project_with_db_no_orphan_table: tuple[Path, str]
    ) -> None:
        """Hook creates orphaned_agents table if not exists."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_db_no_orphan_table

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-create-table",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Verify orphaned_agents table now exists
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orphaned_agents'"
        )
        tables = cursor.fetchall()
        conn.close()

        assert len(tables) == 1, (
            "Hook should create orphaned_agents table. "
            f"Tables found: {tables}"
        )


class TestMarksIncompleteAgentsOrphaned:
    """Tests for marking agents without 'done' broadcast as orphaned."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_incomplete_agents(self) -> tuple[Path, str]:
        """Create project with swarm where agents started but didn't finish.

        - 3 agents registered in completed_tasks (Task tool completed)
        - Only 1 agent broadcast 'done'
        - 2 agents should be marked orphaned
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    sender_agent TEXT NOT NULL,
                    broadcast_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_broadcasts_swarm
                    ON broadcasts(swarm_id, created_at);

                CREATE TABLE IF NOT EXISTS completed_tasks (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );
            """)

            swarm_id = "test-swarm-incomplete"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # 3 agents completed tasks
            for agent in ["agent-1", "agent-2", "agent-3"]:
                conn.execute(
                    "INSERT INTO completed_tasks VALUES (?, ?, ?)",
                    (swarm_id, agent, now)
                )

            # Only agent-1 broadcast 'done'
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("done1", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "Agent 1 completed"}), now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_marks_incomplete_agents_orphaned(
        self,
        hooks_dir: Path,
        project_with_incomplete_agents: tuple[Path, str]
    ) -> None:
        """Agents without 'done' broadcast are marked orphaned."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_incomplete_agents
        session_id = "test-session-orphan"

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Verify orphaned agents in database
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM orphaned_agents WHERE swarm_id = ?",
            (swarm_id,)
        )
        orphaned = cursor.fetchall()
        conn.close()

        orphaned_agents = {row["agent_id"] for row in orphaned}

        # agent-2 and agent-3 should be orphaned (no 'done' broadcast)
        assert "agent-2" in orphaned_agents, (
            f"agent-2 should be marked orphaned. Found: {orphaned_agents}"
        )
        assert "agent-3" in orphaned_agents, (
            f"agent-3 should be marked orphaned. Found: {orphaned_agents}"
        )
        assert len(orphaned_agents) >= 2, (
            f"Expected at least 2 orphaned agents, found {len(orphaned_agents)}"
        )

    def test_orphaned_record_has_session_id(
        self,
        hooks_dir: Path,
        project_with_incomplete_agents: tuple[Path, str]
    ) -> None:
        """Orphaned agent records include the session_id."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_incomplete_agents
        session_id = "test-session-id-tracking"

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Verify session_id is recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM orphaned_agents WHERE session_id = ?",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"Should have orphaned agents with session_id {session_id}. "
            f"Found {len(rows)} rows."
        )

        for row in rows:
            assert row["session_id"] == session_id, (
                f"session_id mismatch. Expected: {session_id}, Got: {row['session_id']}"
            )


class TestDoesntMarkCompletedAgents:
    """Tests for NOT marking completed agents as orphaned."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_all_completed(self) -> tuple[Path, str]:
        """Create project with swarm where all agents completed successfully.

        - 3 agents registered in completed_tasks
        - All 3 agents broadcast 'done'
        - None should be marked orphaned
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    sender_agent TEXT NOT NULL,
                    broadcast_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_broadcasts_swarm
                    ON broadcasts(swarm_id, created_at);

                CREATE TABLE IF NOT EXISTS completed_tasks (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );

                CREATE TABLE IF NOT EXISTS orphaned_agents (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    orphaned_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );
            """)

            swarm_id = "test-swarm-all-done"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # All 3 agents completed tasks AND broadcast 'done'
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO completed_tasks VALUES (?, ?, ?)",
                    (swarm_id, agent, now)
                )
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"done{i}", swarm_id, agent, "done",
                     json.dumps({"summary": f"{agent} completed"}), now)
                )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_doesnt_mark_completed_agents(
        self,
        hooks_dir: Path,
        project_with_all_completed: tuple[Path, str]
    ) -> None:
        """Agents that broadcast 'done' are NOT marked orphaned."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_all_completed

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-all-done",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Verify NO agents are orphaned
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM orphaned_agents WHERE swarm_id = ?",
            (swarm_id,)
        )
        orphaned = cursor.fetchall()
        conn.close()

        assert len(orphaned) == 0, (
            f"No agents should be orphaned when all broadcast 'done'. "
            f"Found orphaned: {[row['agent_id'] for row in orphaned]}"
        )


class TestOrphaningIsSessionSpecific:
    """Tests for session-specific orphaning behavior."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_multiple_sessions(self) -> tuple[Path, str, str]:
        """Create project with agents from different sessions.

        - swarm-A has incomplete agent from session-1
        - swarm-B has incomplete agent from session-2
        - Hook run with session-1 should only track session-1's orphans
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    sender_agent TEXT NOT NULL,
                    broadcast_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS completed_tasks (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );
            """)

            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # swarm-A with incomplete agent
            conn.execute(
                "INSERT INTO completed_tasks VALUES (?, ?, ?)",
                ("swarm-A", "agent-A1", now)
            )

            # swarm-B with incomplete agent
            conn.execute(
                "INSERT INTO completed_tasks VALUES (?, ?, ?)",
                ("swarm-B", "agent-B1", now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), "swarm-A", "swarm-B"

    def test_orphaning_is_session_specific(
        self,
        hooks_dir: Path,
        project_with_multiple_sessions: tuple[Path, str, str]
    ) -> None:
        """Only orphans agents from current session context."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_a, swarm_b = project_with_multiple_sessions
        session_id = "session-specific-test"

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # All orphaned agents should have this session_id
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM orphaned_agents WHERE session_id = ?",
            (session_id,)
        )
        orphaned = cursor.fetchall()
        conn.close()

        # Verify all orphaned records have the correct session_id
        for row in orphaned:
            assert row["session_id"] == session_id, (
                f"All orphaned records should have session_id={session_id}. "
                f"Got: {row['session_id']}"
            )


class TestNoSwarmContinues:
    """Tests for behavior when no swarm data exists."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_empty_db(self) -> Path:
        """Create project with empty database (no swarm data)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    sender_agent TEXT NOT NULL,
                    broadcast_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS completed_tasks (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );
            """)
            conn.commit()
            conn.close()

            yield Path(tmpdir)

    def test_no_swarm_continues(
        self,
        hooks_dir: Path,
        project_with_empty_db: Path
    ) -> None:
        """When no swarm data exists, hook continues gracefully."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_with_empty_db)

        hook_input = json.dumps({
            "session_id": "test-session-no-swarm",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should continue when no swarm data. Got: {output}"
        )


class TestMissingDbContinues:
    """Tests for graceful handling when DB is missing."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_missing_db_continues(self, hooks_dir: Path) -> None:
        """When DB doesn't exist, hook returns continue gracefully."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # No database created - directory is empty
            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            hook_input = json.dumps({
                "session_id": "test-session-no-db",
            })

            result = subprocess.run(
                [str(shell_wrapper)],
                input=hook_input,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir),
                timeout=30
            )

            assert result.returncode == 0, f"Hook failed: {result.stderr}"

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Hook should continue when DB missing. Got: {output}"
            )

    def test_missing_cache_dir_continues(self, hooks_dir: Path) -> None:
        """When .claude/cache directory doesn't exist, hook returns continue."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude but NOT cache subdirectory
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()

            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            hook_input = json.dumps({
                "session_id": "test-session-no-cache",
            })

            result = subprocess.run(
                [str(shell_wrapper)],
                input=hook_input,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir),
                timeout=30
            )

            assert result.returncode == 0, f"Hook failed: {result.stderr}"

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Hook should continue when cache dir missing. Got: {output}"
            )


class TestAlwaysReturnsContinue:
    """Tests to ensure SessionEnd cleanup hook never blocks."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_swarm(self) -> tuple[Path, str]:
        """Create project with broadcasts table for a swarm."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    sender_agent TEXT NOT NULL,
                    broadcast_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS completed_tasks (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );
            """)

            swarm_id = "test-swarm-never-block"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # Add incomplete agents
            for agent in ["agent-1", "agent-2"]:
                conn.execute(
                    "INSERT INTO completed_tasks VALUES (?, ?, ?)",
                    (swarm_id, agent, now)
                )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_always_returns_continue(
        self,
        hooks_dir: Path,
        project_with_swarm: tuple[Path, str]
    ) -> None:
        """SessionEnd cleanup hook should always return continue (never block)."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_swarm

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-never-block",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())

        # SessionEnd cleanup should NEVER block - it's for cleanup only
        assert output.get("result") == "continue", (
            f"SessionEnd cleanup hook should always return 'continue', never 'block'. "
            f"Got: {output}"
        )


class TestCorruptedDbContinues:
    """Tests for graceful handling of corrupted database."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_corrupted_db(self) -> Path:
        """Create project with corrupted database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            # Create a file that's not a valid SQLite database
            db_path = db_dir / "coordination.db"
            db_path.write_text("This is not a valid SQLite database!")

            yield Path(tmpdir)

    def test_corrupted_db_continues(
        self,
        hooks_dir: Path,
        project_with_corrupted_db: Path
    ) -> None:
        """Errors don't crash the hook, return continue."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_with_corrupted_db)

        hook_input = json.dumps({
            "session_id": "test-session-error",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Hook should NOT crash
        assert result.returncode == 0, (
            f"Hook should not crash on error. Exit code: {result.returncode}, "
            f"stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())

        # Should continue gracefully on error
        assert output.get("result") == "continue", (
            f"Hook should continue on error. Got: {output}"
        )


class TestSettingsJsonRegistration:
    """Tests for SessionEnd hook registration in settings.json."""

    @pytest.fixture
    def settings_path(self) -> Path:
        """Path to settings.json."""
        return Path(__file__).parents[2] / ".claude" / "settings.json"

    def test_settings_json_exists(self, settings_path: Path) -> None:
        """Verify settings.json exists."""
        assert settings_path.exists(), f"settings.json not found: {settings_path}"

    def test_settings_json_valid(self, settings_path: Path) -> None:
        """Verify settings.json is valid JSON."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            try:
                json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"settings.json is not valid JSON: {e}")

    def test_hook_registered(self, settings_path: Path) -> None:
        """SessionEnd cleanup hook for swarms is registered in settings.json."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        session_end_hooks = hooks.get("SessionEnd", [])

        # Find our cleanup hook
        cleanup_hook_found = False
        for hook_config in session_end_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "session-end-cleanup-swarms" in command:
                    cleanup_hook_found = True
                    break

        assert cleanup_hook_found, (
            "SessionEnd cleanup hook for swarms must be registered in settings.json. "
            "Expected hooks.SessionEnd to contain command with 'session-end-cleanup-swarms'. "
            f"Current SessionEnd hooks: {session_end_hooks}"
        )

    def test_hook_uses_project_dir(self, settings_path: Path) -> None:
        """SessionEnd hook command uses $CLAUDE_PROJECT_DIR."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        session_end_hooks = hooks.get("SessionEnd", [])

        # Find our cleanup hook and check path
        for hook_config in session_end_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "session-end-cleanup-swarms" in command:
                    assert "$CLAUDE_PROJECT_DIR" in command, (
                        "Hook command should use $CLAUDE_PROJECT_DIR for project-local hooks. "
                        f"Got: {command}"
                    )
                    return

        pytest.skip("SessionEnd cleanup hook not found")


class TestOrphanedAtTimestamp:
    """Tests for orphaned_at timestamp in orphaned records."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_incomplete_agent(self) -> tuple[Path, str]:
        """Create project with an incomplete agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    sender_agent TEXT NOT NULL,
                    broadcast_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS completed_tasks (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );
            """)

            swarm_id = "test-swarm-timestamp"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # Add incomplete agent
            conn.execute(
                "INSERT INTO completed_tasks VALUES (?, ?, ?)",
                (swarm_id, "timestamp-agent", now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_orphaned_at_timestamp_set(
        self,
        hooks_dir: Path,
        project_with_incomplete_agent: tuple[Path, str]
    ) -> None:
        """Orphaned records have orphaned_at timestamp."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_incomplete_agent

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-timestamp",
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Verify orphaned_at is set
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM orphaned_agents WHERE agent_id = ?",
            ("timestamp-agent",)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, "Should have orphaned agent record"

        row = rows[0]
        assert row["orphaned_at"] is not None, (
            "Orphaned record should have orphaned_at timestamp"
        )

        # Verify it's a valid ISO format timestamp
        try:
            datetime.fromisoformat(row["orphaned_at"])
        except ValueError:
            pytest.fail(f"orphaned_at should be ISO format. Got: {row['orphaned_at']}")


class TestErrorHandling:
    """Tests for graceful error handling."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_invalid_json_input_graceful(self, hooks_dir: Path) -> None:
        """Hook handles invalid JSON input gracefully."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Send invalid JSON
        invalid_input = "{ not valid json }"

        result = subprocess.run(
            [str(shell_wrapper)],
            input=invalid_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Hook should either handle gracefully or fail with clear error
        # If it returns 0, output should be valid JSON
        if result.returncode == 0:
            try:
                output = json.loads(result.stdout.strip())
                assert output.get("result") in ["continue", "block"], (
                    f"Hook output should have valid result. Got: {output}"
                )
            except json.JSONDecodeError:
                pytest.fail(
                    f"Hook returned 0 but output is not valid JSON: {result.stdout}"
                )

    def test_missing_session_id_graceful(self, hooks_dir: Path) -> None:
        """Hook handles missing session_id gracefully."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            # Input without session_id
            hook_input = json.dumps({
                # Note: no session_id field!
            })

            result = subprocess.run(
                [str(shell_wrapper)],
                input=hook_input,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir),
                timeout=30
            )

            # Hook should NOT crash
            assert result.returncode == 0, (
                f"Hook should not crash when session_id missing. "
                f"Exit code: {result.returncode}, stderr: {result.stderr}"
            )

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Hook should continue when session_id missing. Got: {output}"
            )


class TestIdempotentOrphaning:
    """Tests for idempotent orphaning (INSERT OR IGNORE)."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_already_orphaned(self) -> tuple[Path, str]:
        """Create project where agent is already marked orphaned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    sender_agent TEXT NOT NULL,
                    broadcast_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS completed_tasks (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );

                CREATE TABLE IF NOT EXISTS orphaned_agents (
                    swarm_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    orphaned_at TEXT NOT NULL,
                    PRIMARY KEY (swarm_id, agent_id)
                );
            """)

            swarm_id = "test-swarm-idempotent"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # Add incomplete agent
            conn.execute(
                "INSERT INTO completed_tasks VALUES (?, ?, ?)",
                (swarm_id, "already-orphaned", now)
            )

            # Pre-mark as orphaned (from previous session end)
            conn.execute(
                "INSERT INTO orphaned_agents VALUES (?, ?, ?, ?)",
                (swarm_id, "already-orphaned", "old-session", now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_idempotent_orphaning(
        self,
        hooks_dir: Path,
        project_with_already_orphaned: tuple[Path, str]
    ) -> None:
        """Running cleanup twice doesn't duplicate orphaned records."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_already_orphaned

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "new-session",
        })

        # Run hook (should be idempotent)
        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Verify only one orphaned record exists (not duplicated)
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM orphaned_agents WHERE swarm_id = ? AND agent_id = ?",
            (swarm_id, "already-orphaned")
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 1, (
            f"Should have exactly one orphaned record (idempotent). "
            f"Found {len(rows)} rows."
        )

        # Original session_id should be preserved (INSERT OR IGNORE)
        assert rows[0]["session_id"] == "old-session", (
            f"Original session_id should be preserved. Got: {rows[0]['session_id']}"
        )
