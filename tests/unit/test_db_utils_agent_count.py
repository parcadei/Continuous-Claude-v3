"""Tests for getActiveAgentCount() in shared/db-utils.ts (Phase 2 of resource-limits plan).

These tests verify that the getActiveAgentCount function:
1. Returns count of agents with status='running'
2. Returns 0 when database doesn't exist
3. Returns 0 when agents table is empty
4. Correctly counts only running agents (not completed/failed)

Tests are designed to FAIL initially (TDD approach) until Phase 2 is implemented.

Related:
- Plan: docs/handoffs/resource-limits-plan.md (Phase 2)
- Implementation: .claude/hooks/src/shared/db-utils.ts
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest


class TestGetActiveAgentCountExists:
    """Tests for getActiveAgentCount function existence."""

    @pytest.fixture
    def db_utils_path(self) -> Path:
        """Path to db-utils.ts."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared" / "db-utils.ts"

    def test_db_utils_exports_get_active_agent_count(self, db_utils_path: Path) -> None:
        """Verify db-utils.ts exports getActiveAgentCount function."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet")

        content = db_utils_path.read_text()

        assert "export" in content and "getActiveAgentCount" in content, (
            "db-utils.ts must export getActiveAgentCount function.\n"
            "Expected: export function getActiveAgentCount() or export async function getActiveAgentCount()"
        )


class TestGetActiveAgentCountBehavior:
    """Tests for getActiveAgentCount() function behavior via TypeScript execution."""

    @pytest.fixture
    def hooks_src_dir(self) -> Path:
        """Path to hooks/src directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src"

    @pytest.fixture
    def db_utils_path(self, hooks_src_dir: Path) -> Path:
        """Path to db-utils.ts."""
        return hooks_src_dir / "shared" / "db-utils.ts"

    @pytest.fixture
    def temp_project_no_db(self) -> Generator[Path, None, None]:
        """Create a temporary project directory without a coordination database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def temp_project_empty_db(self) -> Generator[Path, None, None]:
        """Create a temporary project with an empty coordination database (no agents)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    premise TEXT,
                    role TEXT,
                    pattern TEXT,
                    swarm_id TEXT,
                    parent_agent_id TEXT,
                    spawned_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT DEFAULT 'running',
                    error_message TEXT
                );
            """)
            conn.close()
            yield Path(tmpdir)

    @pytest.fixture
    def temp_project_with_agents(self) -> Generator[Path, None, None]:
        """Create a temporary project with agents in various states."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    premise TEXT,
                    role TEXT,
                    pattern TEXT,
                    swarm_id TEXT,
                    parent_agent_id TEXT,
                    spawned_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT DEFAULT 'running',
                    error_message TEXT
                );

                -- 3 running agents
                INSERT INTO agents (id, session_id, premise, spawned_at, status)
                VALUES
                    ('agent-1', 'session-1', 'Test agent 1', '2025-01-01T10:00:00', 'running'),
                    ('agent-2', 'session-1', 'Test agent 2', '2025-01-01T10:01:00', 'running'),
                    ('agent-3', 'session-2', 'Test agent 3', '2025-01-01T10:02:00', 'running');

                -- 2 completed agents (should not be counted)
                INSERT INTO agents (id, session_id, premise, spawned_at, completed_at, status)
                VALUES
                    ('agent-4', 'session-1', 'Completed agent', '2025-01-01T09:00:00', '2025-01-01T09:30:00', 'completed'),
                    ('agent-5', 'session-2', 'Failed agent', '2025-01-01T09:00:00', '2025-01-01T09:15:00', 'failed');
            """)
            conn.close()
            yield Path(tmpdir)

    def test_returns_zero_when_db_does_not_exist(
        self,
        db_utils_path: Path,
        temp_project_no_db: Path
    ) -> None:
        """getActiveAgentCount() returns 0 when coordination database doesn't exist."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        test_script = """
import { getActiveAgentCount } from './shared/db-utils.ts';

const count = getActiveAgentCount();
console.log(JSON.stringify({ count }));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_project_no_db)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
            assert output.get("count") == 0, (
                f"getActiveAgentCount() should return 0 when DB doesn't exist. Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Output should be valid JSON. Got: {result.stdout}")

    def test_returns_zero_when_agents_table_empty(
        self,
        db_utils_path: Path,
        temp_project_empty_db: Path
    ) -> None:
        """getActiveAgentCount() returns 0 when agents table is empty."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        test_script = """
import { getActiveAgentCount } from './shared/db-utils.ts';

const count = getActiveAgentCount();
console.log(JSON.stringify({ count }));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_project_empty_db)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
            assert output.get("count") == 0, (
                f"getActiveAgentCount() should return 0 when agents table is empty. Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Output should be valid JSON. Got: {result.stdout}")

    def test_returns_count_of_running_agents(
        self,
        db_utils_path: Path,
        temp_project_with_agents: Path
    ) -> None:
        """getActiveAgentCount() returns count of agents with status='running'."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        test_script = """
import { getActiveAgentCount } from './shared/db-utils.ts';

const count = getActiveAgentCount();
console.log(JSON.stringify({ count }));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_project_with_agents)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
            assert output.get("count") == 3, (
                f"getActiveAgentCount() should return 3 (only running agents). Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Output should be valid JSON. Got: {result.stdout}")

    def test_does_not_count_completed_or_failed_agents(
        self,
        db_utils_path: Path,
        temp_project_with_agents: Path
    ) -> None:
        """getActiveAgentCount() excludes completed and failed agents from count."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        # Add another running agent to verify count changes
        db_path = temp_project_with_agents / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT INTO agents (id, session_id, premise, spawned_at, status)
            VALUES ('agent-6', 'session-3', 'New running agent', '2025-01-01T11:00:00', 'running')
        """)
        conn.commit()
        conn.close()

        test_script = """
import { getActiveAgentCount } from './shared/db-utils.ts';

const count = getActiveAgentCount();
console.log(JSON.stringify({ count }));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_project_with_agents)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
            # Should be 4 now (3 original + 1 new)
            assert output.get("count") == 4, (
                f"getActiveAgentCount() should return 4 after adding one more running agent. Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Output should be valid JSON. Got: {result.stdout}")


class TestGetActiveAgentCountErrorHandling:
    """Tests for getActiveAgentCount() error handling."""

    @pytest.fixture
    def hooks_src_dir(self) -> Path:
        """Path to hooks/src directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src"

    @pytest.fixture
    def db_utils_path(self, hooks_src_dir: Path) -> Path:
        """Path to db-utils.ts."""
        return hooks_src_dir / "shared" / "db-utils.ts"

    @pytest.fixture
    def temp_project_corrupt_db(self) -> Generator[Path, None, None]:
        """Create a temporary project with a corrupt/invalid database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            # Write invalid data to the db file
            db_path = db_dir / "coordination.db"
            db_path.write_text("this is not a valid sqlite database")
            yield Path(tmpdir)

    def test_returns_zero_on_db_error(
        self,
        db_utils_path: Path,
        temp_project_corrupt_db: Path
    ) -> None:
        """getActiveAgentCount() returns 0 when database query fails."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        test_script = """
import { getActiveAgentCount } from './shared/db-utils.ts';

const count = getActiveAgentCount();
console.log(JSON.stringify({ count }));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_project_corrupt_db)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
            assert output.get("count") == 0, (
                f"getActiveAgentCount() should return 0 on DB error. Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Output should be valid JSON. Got: {result.stdout}")

    @pytest.fixture
    def temp_project_missing_table(self) -> Generator[Path, None, None]:
        """Create a temporary project with a database that doesn't have agents table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            # Create a different table, not agents
            conn.execute("CREATE TABLE other_table (id TEXT PRIMARY KEY)")
            conn.close()
            yield Path(tmpdir)

    def test_returns_zero_when_agents_table_missing(
        self,
        db_utils_path: Path,
        temp_project_missing_table: Path
    ) -> None:
        """getActiveAgentCount() returns 0 when agents table doesn't exist."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        test_script = """
import { getActiveAgentCount } from './shared/db-utils.ts';

const count = getActiveAgentCount();
console.log(JSON.stringify({ count }));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_project_missing_table)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
            assert output.get("count") == 0, (
                f"getActiveAgentCount() should return 0 when agents table missing. Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Output should be valid JSON. Got: {result.stdout}")
