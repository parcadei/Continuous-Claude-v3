"""
Unit tests for Hierarchical pattern handlers.

Tests the TypeScript handlers:
- onSubagentStart: Inject subtask context for specialists
- onSubagentStop: Notify coordinator of specialist completion
- onPreToolUse: Scope broadcasts to hierarchy level
- onStop: Synthesis verification

Environment Variables:
- PATTERN_TYPE=hierarchical
- HIERARCHY_ID=<id>
- AGENT_ROLE=coordinator|specialist
- COORDINATOR_ID=<id> (for specialists)
- HIERARCHY_LEVEL=<n>
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class TestHierarchicalHandlers:
    """Test Hierarchical pattern TypeScript handlers."""

    @staticmethod
    def get_hooks_dir() -> Path:
        """Get absolute path to .claude/hooks directory."""
        project_dir = Path(__file__).parent.parent.parent
        return project_dir / ".claude" / "hooks"

    @staticmethod
    def setup_test_db() -> tuple[str, str]:
        """Create temporary database for testing.

        Returns:
            Tuple of (db_path, project_dir)
        """
        # Create temp directory structure matching expected layout
        temp_dir = tempfile.mkdtemp()
        cache_dir = os.path.join(temp_dir, ".claude", "cache", "agentica-coordination")
        os.makedirs(cache_dir, exist_ok=True)

        db_path = os.path.join(cache_dir, "coordination.db")

        # Create hierarchy_agents table
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hierarchy_agents (
                id TEXT PRIMARY KEY,
                hierarchy_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,
                coordinator_id TEXT,
                level INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hierarchy_agents
                ON hierarchy_agents(hierarchy_id, status)
        """)
        conn.commit()
        conn.close()

        return db_path, temp_dir

    def test_onsubagentstart_coordinator(self):
        """Test SubagentStart handler for coordinator role."""
        hooks_dir = self.get_hooks_dir()

        # Prepare input
        hook_input = {
            "session_id": "test-session-123",
            "agent_id": "coordinator-agent-456"
        }

        # Set environment variables
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "hierarchical"
        env["HIERARCHY_ID"] = "hierarchy-abc123"
        env["AGENT_ROLE"] = "coordinator"
        env["HIERARCHY_LEVEL"] = "0"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Run hook
        result = subprocess.run(
            ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            env=env
        )

        # Should succeed
        assert result.returncode == 0, f"stderr: {result.stderr}"

        # Parse output
        output = json.loads(result.stdout)
        assert output["result"] == "continue"
        assert "message" in output
        assert "coordinator" in output["message"].lower()
        assert "decompose" in output["message"].lower() or "subtask" in output["message"].lower()

    def test_onsubagentstart_specialist(self):
        """Test SubagentStart handler for specialist role."""
        hooks_dir = self.get_hooks_dir()

        # Prepare input
        hook_input = {
            "session_id": "test-session-123",
            "agent_id": "specialist-agent-789"
        }

        # Set environment variables
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "hierarchical"
        env["HIERARCHY_ID"] = "hierarchy-abc123"
        env["AGENT_ROLE"] = "specialist"
        env["COORDINATOR_ID"] = "coordinator-agent-456"
        env["HIERARCHY_LEVEL"] = "1"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Run hook
        result = subprocess.run(
            ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            env=env
        )

        # Should succeed
        assert result.returncode == 0, f"stderr: {result.stderr}"

        # Parse output
        output = json.loads(result.stdout)
        assert output["result"] == "continue"
        assert "message" in output
        assert "specialist" in output["message"].lower()

    def test_onsubagentstart_no_hierarchy_id(self):
        """Test SubagentStart with no HIERARCHY_ID (not in a hierarchy)."""
        hooks_dir = self.get_hooks_dir()

        hook_input = {"session_id": "test-session-123"}

        env = os.environ.copy()
        # No PATTERN_TYPE or HIERARCHY_ID
        env.pop("PATTERN_TYPE", None)
        env.pop("HIERARCHY_ID", None)
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            env=env
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["result"] == "continue"
        # Should continue silently (no message)
        assert "message" not in output or output["message"] == ""

    def test_onsubagentstopcomplete_specialist(self):
        """Test SubagentStop handler when specialist completes."""
        hooks_dir = self.get_hooks_dir()
        db_path, temp_dir = self.setup_test_db()

        try:
            # Set up database with coordinator and one specialist
            conn = sqlite3.connect(db_path)
            hierarchy_id = "hierarchy-abc123"
            coordinator_id = "coordinator-agent-456"
            specialist_id = "specialist-agent-789"

            # Insert coordinator
            conn.execute(
                """INSERT INTO hierarchy_agents
                   (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (coordinator_id, hierarchy_id, coordinator_id, "coordinator", None, 0, "active")
            )
            conn.commit()
            conn.close()

            # Don't pre-insert specialist - let the hook do it

            # Prepare input (specialist completing)
            hook_input = {
                "session_id": "test-session-123",
                "agent_id": specialist_id
            }

            # Set environment variables
            env = os.environ.copy()
            env["PATTERN_TYPE"] = "hierarchical"
            env["HIERARCHY_ID"] = hierarchy_id
            env["AGENT_ROLE"] = "specialist"
            env["COORDINATOR_ID"] = coordinator_id
            env["HIERARCHY_LEVEL"] = "1"
            env["STOP_HOOK"] = "true"  # Signal this is a SubagentStop call
            env["CLAUDE_PROJECT_DIR"] = temp_dir

            # Run hook
            result = subprocess.run(
                ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
                cwd=str(hooks_dir),
                env=env
            )

            # Should succeed
            assert result.returncode == 0, f"stderr: {result.stderr}"

            # Parse output
            output = json.loads(result.stdout)
            assert output["result"] == "continue"

            # Verify database was updated
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT status FROM hierarchy_agents WHERE agent_id = ?",
                (specialist_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "completed"
            conn.close()

        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def test_onstop_waiting_for_specialists(self):
        """Test Stop handler when not all specialists are complete."""
        hooks_dir = self.get_hooks_dir()
        db_path, temp_dir = self.setup_test_db()

        try:
            # Set up database with coordinator and two specialists, one incomplete
            conn = sqlite3.connect(db_path)
            hierarchy_id = "hierarchy-abc123"
            coordinator_id = "coordinator-agent-456"

            # Insert coordinator
            conn.execute(
                """INSERT INTO hierarchy_agents
                   (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (coordinator_id, hierarchy_id, coordinator_id, "coordinator", None, 0, "active")
            )

            # Insert completed specialist
            conn.execute(
                """INSERT INTO hierarchy_agents
                   (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                ("specialist-1", hierarchy_id, "specialist-1", "specialist", coordinator_id, 1, "completed")
            )

            # Insert active specialist (not completed)
            conn.execute(
                """INSERT INTO hierarchy_agents
                   (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                ("specialist-2", hierarchy_id, "specialist-2", "specialist", coordinator_id, 1, "active")
            )
            conn.commit()
            conn.close()

            # Prepare input
            hook_input = {"session_id": "test-session-123"}

            # Set environment variables
            env = os.environ.copy()
            env["PATTERN_TYPE"] = "hierarchical"
            env["HIERARCHY_ID"] = hierarchy_id
            env["AGENT_ROLE"] = "coordinator"
            env["HIERARCHY_LEVEL"] = "0"
            env["CLAUDE_PROJECT_DIR"] = temp_dir

            # Run hook
            result = subprocess.run(
                ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
                cwd=str(hooks_dir),
                env=env
            )

            # Should succeed
            assert result.returncode == 0, f"stderr: {result.stderr}"

            # Parse output
            output = json.loads(result.stdout)
            # Should block because not all specialists are done
            assert output["result"] == "block"
            assert "waiting" in output["message"].lower() or "specialist" in output["message"].lower()

        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def test_onstop_all_specialists_complete(self):
        """Test Stop handler when all specialists are complete."""
        hooks_dir = self.get_hooks_dir()
        db_path, temp_dir = self.setup_test_db()

        try:
            # Set up database with coordinator and two completed specialists
            conn = sqlite3.connect(db_path)
            hierarchy_id = "hierarchy-abc123"
            coordinator_id = "coordinator-agent-456"

            # Insert coordinator
            conn.execute(
                """INSERT INTO hierarchy_agents
                   (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (coordinator_id, hierarchy_id, coordinator_id, "coordinator", None, 0, "active")
            )

            # Insert two completed specialists
            for i in [1, 2]:
                conn.execute(
                    """INSERT INTO hierarchy_agents
                       (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (f"specialist-{i}", hierarchy_id, f"specialist-{i}", "specialist", coordinator_id, 1, "completed")
                )
            conn.commit()
            conn.close()

            # Prepare input
            hook_input = {"session_id": "test-session-123"}

            # Set environment variables
            env = os.environ.copy()
            env["PATTERN_TYPE"] = "hierarchical"
            env["HIERARCHY_ID"] = hierarchy_id
            env["AGENT_ROLE"] = "coordinator"
            env["HIERARCHY_LEVEL"] = "0"
            env["CLAUDE_PROJECT_DIR"] = temp_dir

            # Run hook
            result = subprocess.run(
                ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
                cwd=str(hooks_dir),
                env=env
            )

            # Should succeed
            assert result.returncode == 0, f"stderr: {result.stderr}"

            # Parse output
            output = json.loads(result.stdout)
            # Should continue because all specialists are done
            assert output["result"] == "continue"
            assert "message" in output
            assert "specialist" in output["message"].lower() or "synthesis" in output["message"].lower()

        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


# =============================================================================
# onPostToolUse Handler Tests (TDD Red Phase)
# =============================================================================


class TestOnPostToolUseHandler:
    """Tests for onPostToolUse handler - tracks coordinator Task spawns.

    These tests verify that when a coordinator spawns specialists via Task tool,
    the handler records them in the hierarchy_agents table for tracking.

    TDD Status: RED - Tests should FAIL until onPostToolUse is implemented.
    """

    @staticmethod
    def get_hooks_dir() -> Path:
        """Get absolute path to .claude/hooks directory."""
        project_dir = Path(__file__).parent.parent.parent
        return project_dir / ".claude" / "hooks"

    @staticmethod
    def setup_test_db() -> tuple[str, str]:
        """Create temporary database for testing.

        Returns:
            Tuple of (db_path, project_dir)
        """
        temp_dir = tempfile.mkdtemp()
        cache_dir = os.path.join(temp_dir, ".claude", "cache", "agentica-coordination")
        os.makedirs(cache_dir, exist_ok=True)

        db_path = os.path.join(cache_dir, "coordination.db")

        # Create hierarchy_agents table
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hierarchy_agents (
                id TEXT PRIMARY KEY,
                hierarchy_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,
                coordinator_id TEXT,
                level INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hierarchy_agents
                ON hierarchy_agents(hierarchy_id, status)
        """)
        conn.commit()
        conn.close()

        return db_path, temp_dir

    def test_exports_on_post_tool_use(self):
        """Module exports onPostToolUse function."""
        hooks_dir = self.get_hooks_dir()
        hierarchical_path = hooks_dir / "src" / "patterns" / "hierarchical.ts"

        assert hierarchical_path.exists(), f"hierarchical.ts not found at {hierarchical_path}"

        content = hierarchical_path.read_text()
        assert "export" in content and "onPostToolUse" in content, (
            "Module must export onPostToolUse function. "
            "Expected: export async function onPostToolUse or export { onPostToolUse }"
        )

    def test_notifies_coordinator_of_task_spawn(self):
        """onPostToolUse records specialist spawn when coordinator uses Task tool.

        When a coordinator spawns a specialist via Task tool, the handler should:
        1. Record the spawned agent in hierarchy_agents table
        2. Set role='specialist', status='active'
        3. Link to coordinator via coordinator_id
        """
        hooks_dir = self.get_hooks_dir()
        db_path, temp_dir = self.setup_test_db()

        try:
            hierarchy_id = "hierarchy-posttool-123"
            coordinator_id = "coordinator-abc"
            spawned_specialist_id = "specialist-spawned-789"

            # Insert coordinator first
            conn = sqlite3.connect(db_path)
            conn.execute(
                """INSERT INTO hierarchy_agents
                   (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (coordinator_id, hierarchy_id, coordinator_id, "coordinator", None, 0, "active")
            )
            conn.commit()
            conn.close()

            # Prepare hook input - coordinator spawns a specialist via Task
            hook_input = {
                "session_id": "test-session-123",
                "tool_name": "Task",
                "tool_input": {
                    "prompt": "Analyze the authentication module",
                    "description": "Specialist task for auth analysis"
                },
                "tool_response": {
                    "task_id": spawned_specialist_id,
                    "agent_id": spawned_specialist_id,
                    "status": "started"
                }
            }

            env = os.environ.copy()
            env["PATTERN_TYPE"] = "hierarchical"
            env["HIERARCHY_ID"] = hierarchy_id
            env["AGENT_ROLE"] = "coordinator"
            env["AGENT_ID"] = coordinator_id
            env["HIERARCHY_LEVEL"] = "0"
            env["POST_TOOL_USE_HOOK"] = "true"  # Signal for test harness
            env["CLAUDE_PROJECT_DIR"] = temp_dir

            # Run hook via test harness
            result = subprocess.run(
                ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
                cwd=str(hooks_dir),
                env=env
            )

            assert result.returncode == 0, f"Handler failed: {result.stderr}"

            output = json.loads(result.stdout)
            assert output["result"] == "continue"

            # CRITICAL: Verify specialist was recorded in database
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                """SELECT agent_id, role, coordinator_id, status, level
                   FROM hierarchy_agents
                   WHERE hierarchy_id = ? AND agent_id = ?""",
                (hierarchy_id, spawned_specialist_id)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, (
                f"onPostToolUse should record spawned specialist in database. "
                f"No record found for agent_id={spawned_specialist_id}"
            )

            agent_id, role, coord_id, status, level = row
            assert role == "specialist", f"Spawned agent should have role='specialist', got '{role}'"
            assert coord_id == coordinator_id, f"Spawned agent should link to coordinator, got '{coord_id}'"
            assert status == "active", f"Spawned agent should have status='active', got '{status}'"
            assert level == 1, f"Specialist should be level 1, got {level}"

        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def test_ignores_non_task_tools(self):
        """onPostToolUse only tracks Task tool, ignores others like Bash, Read, etc."""
        hooks_dir = self.get_hooks_dir()
        db_path, temp_dir = self.setup_test_db()

        try:
            hierarchy_id = "hierarchy-ignore-123"
            coordinator_id = "coordinator-xyz"

            # Insert coordinator
            conn = sqlite3.connect(db_path)
            conn.execute(
                """INSERT INTO hierarchy_agents
                   (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (coordinator_id, hierarchy_id, coordinator_id, "coordinator", None, 0, "active")
            )
            conn.commit()
            initial_count = conn.execute("SELECT COUNT(*) FROM hierarchy_agents").fetchone()[0]
            conn.close()

            # Prepare hook input - Bash tool (not Task)
            hook_input = {
                "session_id": "test-session-123",
                "tool_name": "Bash",
                "tool_input": {"command": "ls -la"},
                "tool_response": {"output": "file1.txt\nfile2.txt"}
            }

            env = os.environ.copy()
            env["PATTERN_TYPE"] = "hierarchical"
            env["HIERARCHY_ID"] = hierarchy_id
            env["AGENT_ROLE"] = "coordinator"
            env["AGENT_ID"] = coordinator_id
            env["HIERARCHY_LEVEL"] = "0"
            env["POST_TOOL_USE_HOOK"] = "true"
            env["CLAUDE_PROJECT_DIR"] = temp_dir

            result = subprocess.run(
                ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
                cwd=str(hooks_dir),
                env=env
            )

            assert result.returncode == 0, f"Handler failed: {result.stderr}"

            output = json.loads(result.stdout)
            assert output["result"] == "continue", (
                f"Should return 'continue' for non-Task tools. Got: {output}"
            )

            # Verify no new records were added
            conn = sqlite3.connect(db_path)
            final_count = conn.execute("SELECT COUNT(*) FROM hierarchy_agents").fetchone()[0]
            conn.close()

            assert final_count == initial_count, (
                f"Should not create new records for Bash tool. "
                f"Before: {initial_count}, After: {final_count}"
            )

        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def test_validates_input_format(self):
        """onPostToolUse validates input and handles malformed data gracefully."""
        hooks_dir = self.get_hooks_dir()
        db_path, temp_dir = self.setup_test_db()

        try:
            hierarchy_id = "hierarchy-valid-123"

            # Test: Malicious agent_id in tool_response (SQL injection attempt)
            hook_input = {
                "session_id": "test-session-123",
                "tool_name": "Task",
                "tool_input": {"prompt": "Do something"},
                "tool_response": {
                    "task_id": "'; DROP TABLE hierarchy_agents; --",
                    "agent_id": "'; DROP TABLE hierarchy_agents; --"
                }
            }

            env = os.environ.copy()
            env["PATTERN_TYPE"] = "hierarchical"
            env["HIERARCHY_ID"] = hierarchy_id
            env["AGENT_ROLE"] = "coordinator"
            env["HIERARCHY_LEVEL"] = "0"
            env["POST_TOOL_USE_HOOK"] = "true"
            env["CLAUDE_PROJECT_DIR"] = temp_dir

            result = subprocess.run(
                ["npx", "tsx", "src/patterns/hierarchical-test-harness.ts"],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
                cwd=str(hooks_dir),
                env=env
            )

            # Should not crash
            assert result.returncode == 0, f"Handler crashed on malicious input: {result.stderr}"

            output = json.loads(result.stdout)
            assert output["result"] == "continue", (
                f"Should continue (reject) with malicious agent_id. Got: {output}"
            )

            # Verify table still exists and wasn't dropped
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='hierarchy_agents'"
            )
            table_exists = cursor.fetchone() is not None
            conn.close()

            assert table_exists, "SQL injection should not have dropped the table"

        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
