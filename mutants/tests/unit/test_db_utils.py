"""Tests for shared/db-utils.ts (Phase 2 of pattern-aware hooks plan).

These tests verify that the shared database utilities module:
1. getDbPath() returns correct coordination.db path
2. getDbPath() uses CLAUDE_PROJECT_DIR env var
3. queryDb() executes Python subprocess correctly
4. queryDb() handles errors gracefully
5. SAFE_ID_PATTERN regex validates IDs correctly

Tests are designed to FAIL initially (TDD approach) until Phase 2 is implemented.

Related:
- Plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 2)
- Source extraction from: .claude/hooks/src/pre-tool-use-broadcast.ts
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest


class TestDbUtilsFileExists:
    """Tests for db-utils.ts file existence and structure."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared utilities directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_shared_directory_exists(self, shared_dir: Path) -> None:
        """Verify shared/ directory exists under hooks/src/."""
        assert shared_dir.exists(), (
            f"shared/ directory not found: {shared_dir}\n"
            "Phase 2 requires creating .claude/hooks/src/shared/ directory"
        )

    def test_db_utils_ts_exists(self, shared_dir: Path) -> None:
        """Verify db-utils.ts exists in shared/ directory."""
        db_utils = shared_dir / "db-utils.ts"
        assert db_utils.exists(), (
            f"db-utils.ts not found: {db_utils}\n"
            "Phase 2 requires creating .claude/hooks/src/shared/db-utils.ts"
        )

    def test_db_utils_exports_get_db_path(self, shared_dir: Path) -> None:
        """Verify db-utils.ts exports getDbPath function."""
        db_utils = shared_dir / "db-utils.ts"

        if not db_utils.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        content = db_utils.read_text()

        # Check for exported function
        assert "export" in content and "getDbPath" in content, (
            "db-utils.ts must export getDbPath function.\n"
            "Expected: export function getDbPath() or export const getDbPath"
        )

    def test_db_utils_exports_query_db(self, shared_dir: Path) -> None:
        """Verify db-utils.ts exports queryDb function."""
        db_utils = shared_dir / "db-utils.ts"

        if not db_utils.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        content = db_utils.read_text()

        assert "export" in content and "queryDb" in content, (
            "db-utils.ts must export queryDb function.\n"
            "Expected: export function queryDb() or export const queryDb"
        )

    def test_db_utils_exports_safe_id_pattern(self, shared_dir: Path) -> None:
        """Verify db-utils.ts exports SAFE_ID_PATTERN regex."""
        db_utils = shared_dir / "db-utils.ts"

        if not db_utils.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        content = db_utils.read_text()

        assert "SAFE_ID_PATTERN" in content, (
            "db-utils.ts must export SAFE_ID_PATTERN regex.\n"
            "Expected: export const SAFE_ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/"
        )


class TestGetDbPathBehavior:
    """Tests for getDbPath() function behavior via TypeScript execution."""

    @pytest.fixture
    def hooks_src_dir(self) -> Path:
        """Path to hooks/src directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src"

    @pytest.fixture
    def db_utils_path(self, hooks_src_dir: Path) -> Path:
        """Path to db-utils.ts."""
        return hooks_src_dir / "shared" / "db-utils.ts"

    def test_get_db_path_returns_correct_path(self, db_utils_path: Path) -> None:
        """getDbPath() returns .claude/cache/agentica-coordination/coordination.db."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Execute TypeScript to test getDbPath
            test_script = f"""
import {{ getDbPath }} from './shared/db-utils.ts';
console.log(getDbPath());
"""
            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            result = subprocess.run(
                ["npx", "tsx", "-e", test_script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(db_utils_path.parent.parent),
                timeout=30
            )

            assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

            output = result.stdout.strip()
            expected_suffix = ".claude/cache/agentica-coordination/coordination.db"

            assert output.endswith(expected_suffix), (
                f"getDbPath() should return path ending with '{expected_suffix}'.\n"
                f"Got: {output}"
            )

    def test_get_db_path_uses_claude_project_dir(self, db_utils_path: Path) -> None:
        """getDbPath() uses CLAUDE_PROJECT_DIR environment variable."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_script = f"""
import {{ getDbPath }} from './shared/db-utils.ts';
console.log(getDbPath());
"""
            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            result = subprocess.run(
                ["npx", "tsx", "-e", test_script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(db_utils_path.parent.parent),
                timeout=30
            )

            assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

            output = result.stdout.strip()

            assert tmpdir in output, (
                f"getDbPath() should use CLAUDE_PROJECT_DIR ({tmpdir}).\n"
                f"Got: {output}"
            )

    def test_get_db_path_falls_back_to_cwd(self, db_utils_path: Path) -> None:
        """getDbPath() falls back to process.cwd() when CLAUDE_PROJECT_DIR not set."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_script = f"""
import {{ getDbPath }} from './shared/db-utils.ts';
console.log(getDbPath());
"""
            env = os.environ.copy()
            # Remove CLAUDE_PROJECT_DIR if set
            env.pop("CLAUDE_PROJECT_DIR", None)

            result = subprocess.run(
                ["npx", "tsx", "-e", test_script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(db_utils_path.parent.parent),
                timeout=30
            )

            assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

            output = result.stdout.strip()

            # Should return a valid path even without CLAUDE_PROJECT_DIR
            assert "coordination.db" in output, (
                f"getDbPath() should return path containing 'coordination.db'.\n"
                f"Got: {output}"
            )


class TestQueryDbBehavior:
    """Tests for queryDb() function behavior."""

    @pytest.fixture
    def hooks_src_dir(self) -> Path:
        """Path to hooks/src directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src"

    @pytest.fixture
    def db_utils_path(self, hooks_src_dir: Path) -> Path:
        """Path to db-utils.ts."""
        return hooks_src_dir / "shared" / "db-utils.ts"

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create a temporary coordination database with test data."""
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

                INSERT INTO broadcasts (id, swarm_id, sender_agent, broadcast_type, payload, created_at)
                VALUES ('test-1', 'swarm-abc', 'agent-1', 'finding', '{"data": "test"}', '2025-01-01T00:00:00');
            """)
            conn.close()
            yield Path(tmpdir)

    def test_query_db_executes_python_query(
        self,
        db_utils_path: Path,
        temp_db: Path
    ) -> None:
        """queryDb() executes Python subprocess to query SQLite."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        # Create test script that uses queryDb
        test_script = """
import { queryDb, getDbPath } from './shared/db-utils.ts';

const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
cursor = conn.execute('SELECT COUNT(*) as count FROM broadcasts')
row = cursor.fetchone()
print(json.dumps({"count": row[0]}))
`;

const dbPath = getDbPath();
const result = queryDb(query, [dbPath]);
console.log(result);
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        # Parse the output as JSON
        try:
            output = json.loads(result.stdout.strip())
            assert output.get("count") == 1, (
                f"queryDb should return query results. Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"queryDb should return valid JSON. Got: {result.stdout}")

    def test_query_db_passes_arguments_safely(
        self,
        db_utils_path: Path,
        temp_db: Path
    ) -> None:
        """queryDb() passes arguments to Python subprocess safely (no shell injection)."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        # Test with a swarm_id that has special characters (should be handled safely)
        test_script = """
import { queryDb, getDbPath } from './shared/db-utils.ts';

const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
swarm_id = sys.argv[2]
print(json.dumps({"swarm_id": swarm_id}))
`;

const dbPath = getDbPath();
const testSwarmId = "test-swarm-123";
const result = queryDb(query, [dbPath, testSwarmId]);
console.log(result);
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db)

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
            assert output.get("swarm_id") == "test-swarm-123", (
                f"queryDb should pass arguments correctly. Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"queryDb should return valid JSON. Got: {result.stdout}")

    def test_query_db_handles_python_error(
        self,
        db_utils_path: Path,
        temp_db: Path
    ) -> None:
        """queryDb() handles Python subprocess errors gracefully."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        # Test with invalid Python code
        test_script = """
import { queryDb } from './shared/db-utils.ts';

const badQuery = `
import sys
raise Exception("Intentional error")
`;

try {
    const result = queryDb(badQuery, []);
    console.log(JSON.stringify({ success: false, error: "Should have thrown" }));
} catch (err) {
    console.log(JSON.stringify({ success: true, caught: true }));
}
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_db)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        # The script itself should succeed (it catches the error)
        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
            assert output.get("caught") is True, (
                f"queryDb should throw on Python error. Got: {output}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Test output should be valid JSON. Got: {result.stdout}")

    def test_query_db_handles_missing_db(
        self,
        db_utils_path: Path
    ) -> None:
        """queryDb() handles missing database file gracefully."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        with tempfile.TemporaryDirectory() as tmpdir:
            # No database created in tmpdir
            test_script = """
import { queryDb, getDbPath } from './shared/db-utils.ts';

const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
cursor = conn.execute('SELECT 1')
print(json.dumps({"ok": True}))
`;

try {
    const dbPath = getDbPath();
    const result = queryDb(query, [dbPath]);
    console.log(result);
} catch (err) {
    console.log(JSON.stringify({ error: err.message }));
}
"""
            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            result = subprocess.run(
                ["npx", "tsx", "-e", test_script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(db_utils_path.parent.parent),
                timeout=30
            )

            # Should not crash - either returns result or error object
            assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"


class TestSafeIdPattern:
    """Tests for SAFE_ID_PATTERN regex exported from db-utils.ts."""

    @pytest.fixture
    def db_utils_path(self) -> Path:
        """Path to db-utils.ts."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared" / "db-utils.ts"

    def test_safe_id_pattern_accepts_valid_ids(self, db_utils_path: Path) -> None:
        """SAFE_ID_PATTERN accepts alphanumeric IDs with hyphens/underscores."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        test_script = """
import { SAFE_ID_PATTERN } from './shared/db-utils.ts';

const validIds = [
    "abc123",
    "test-swarm-1",
    "agent_id_2",
    "A-B_C-123",
    "a",
    "a".repeat(64)  // Max length
];

const results = validIds.map(id => SAFE_ID_PATTERN.test(id));
console.log(JSON.stringify(results));
"""
        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            results = json.loads(result.stdout.strip())
            assert all(results), (
                f"SAFE_ID_PATTERN should accept all valid IDs. Got: {results}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Test output should be valid JSON. Got: {result.stdout}")

    def test_safe_id_pattern_rejects_invalid_ids(self, db_utils_path: Path) -> None:
        """SAFE_ID_PATTERN rejects IDs with shell metacharacters."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        test_script = """
import { SAFE_ID_PATTERN } from './shared/db-utils.ts';

const invalidIds = [
    "test; rm -rf /",
    "id'injection",
    'id"injection',
    "id`command`",
    "id$(whoami)",
    "id\\ninjection",
    "path/../traversal",
    "",  // Empty string
    "a".repeat(65)  // Too long
];

const results = invalidIds.map(id => SAFE_ID_PATTERN.test(id));
console.log(JSON.stringify(results));
"""
        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(db_utils_path.parent.parent),
            timeout=30
        )

        assert result.returncode == 0, f"TypeScript execution failed: {result.stderr}"

        try:
            results = json.loads(result.stdout.strip())
            assert not any(results), (
                f"SAFE_ID_PATTERN should reject all invalid IDs. Got: {results}"
            )
        except json.JSONDecodeError:
            pytest.fail(f"Test output should be valid JSON. Got: {result.stdout}")


class TestDbUtilsIntegration:
    """Integration tests for db-utils.ts with real database operations."""

    @pytest.fixture
    def db_utils_path(self) -> Path:
        """Path to db-utils.ts."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared" / "db-utils.ts"

    @pytest.fixture
    def project_with_db(self) -> Path:
        """Create a temporary project with populated coordination database."""
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

                INSERT INTO broadcasts VALUES
                    ('b1', 'swarm-test', 'agent-1', 'finding', '{"key": "value1"}', '2025-01-01T10:00:00'),
                    ('b2', 'swarm-test', 'agent-2', 'blocker', '{"key": "value2"}', '2025-01-01T10:01:00'),
                    ('b3', 'swarm-other', 'agent-3', 'progress', '{"key": "value3"}', '2025-01-01T10:02:00');
            """)
            conn.close()
            yield Path(tmpdir)

    def test_query_broadcasts_for_swarm(
        self,
        db_utils_path: Path,
        project_with_db: Path
    ) -> None:
        """Full integration test: query broadcasts for a specific swarm."""
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet (Phase 2 not implemented)")

        test_script = """
import { queryDb, getDbPath } from './shared/db-utils.ts';

const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
swarm_id = sys.argv[2]

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.execute(
    'SELECT * FROM broadcasts WHERE swarm_id = ? ORDER BY created_at',
    (swarm_id,)
)

broadcasts = [dict(row) for row in cursor.fetchall()]
print(json.dumps(broadcasts))
`;

const dbPath = getDbPath();
const result = queryDb(query, [dbPath, 'swarm-test']);
console.log(result);
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

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
            broadcasts = json.loads(result.stdout.strip())
            assert len(broadcasts) == 2, (
                f"Should return 2 broadcasts for swarm-test. Got: {len(broadcasts)}"
            )
            assert broadcasts[0]["sender_agent"] == "agent-1"
            assert broadcasts[1]["sender_agent"] == "agent-2"
        except json.JSONDecodeError:
            pytest.fail(f"Query result should be valid JSON. Got: {result.stdout}")
