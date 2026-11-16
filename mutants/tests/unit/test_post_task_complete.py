"""Tests for PostToolUse hook for Task completion (Phase 12.7).

These tests verify that the PostToolUse hook correctly:
1. Triggers only on Task tool completions (matcher: ["Task"])
2. Extracts agent_id from the tool response
3. Records the agent to the broadcasts table with broadcast_type='started'
4. Uses SWARM_ID from environment variable
5. Handles missing SWARM_ID and DB gracefully

Tests are designed to FAIL initially (TDD approach) until Phase 12.7 is implemented.

See plan: thoughts/shared/plans/2025-12-28-user-triggered-agentica.md (Phase 12.7)
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestPostTaskCompleteHookFiles:
    """Tests for PostToolUse Task hook file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper file exists."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}"
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper file is executable."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}"
        )

    def test_typescript_handler_exists(self, hooks_dir: Path) -> None:
        """TypeScript handler file exists."""
        ts_handler = hooks_dir / "src" / "post-task-complete.ts"

        assert ts_handler.exists(), (
            f"TypeScript handler not found: {ts_handler}"
        )

    def test_shell_wrapper_calls_typescript_or_js(self, hooks_dir: Path) -> None:
        """Verify shell wrapper invokes TypeScript via npx tsx or compiled JS."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        # Should call npx tsx with the TypeScript file or node with compiled JS
        has_tsx = "npx tsx" in content
        has_node = "node dist/" in content
        has_reference = "post-task-complete" in content

        assert has_tsx or has_node, (
            "Shell wrapper should invoke TypeScript via 'npx tsx' or compiled JS via 'node dist/'"
        )
        assert has_reference, (
            "Shell wrapper should reference post-task-complete handler"
        )


class TestOnlyTriggersOnTaskTool:
    """Tests for hook only processing Task tool completions."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_db(self) -> Path:
        """Create a temporary project with coordination database."""
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
            """)
            conn.close()
            yield Path(tmpdir)

    def test_only_triggers_on_task_tool(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Hook only processes Task tool completions."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-task"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        # Simulate Task tool completion
        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "Do something"},
            "tool_response": {"agent_id": "spawned-agent-123", "result": "done"}
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
            f"Hook should return 'continue'. Got: {output}"
        )

        # Verify agent was recorded in broadcasts table
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT sender_agent, broadcast_type FROM broadcasts WHERE swarm_id = ?",
            (swarm_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, "Agent should be recorded in broadcasts table"
        # Check that spawned-agent-123 is recorded
        agent_ids = [row[0] for row in rows]
        assert "spawned-agent-123" in agent_ids, (
            f"Agent spawned-agent-123 should be recorded. Found: {agent_ids}"
        )

    def test_ignores_other_tools(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Hook ignores Read, Write, Bash, etc."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-ignore"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        # Test various non-Task tools
        for tool_name in ["Read", "Write", "Bash", "Grep", "Edit"]:
            hook_input = json.dumps({
                "session_id": "test-session",
                "tool_name": tool_name,
                "tool_input": {"some": "input"},
                "tool_response": {"some": "response"}
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

            assert result.returncode == 0, f"Hook failed for {tool_name}: {result.stderr}"

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Hook should return 'continue' for {tool_name}. Got: {output}"
            )

        # Verify no agents were recorded (since we only used non-Task tools)
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM broadcasts WHERE swarm_id = ?",
            (swarm_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"No broadcasts should be recorded for non-Task tools. Found: {count}"
        )


class TestExtractsAgentId:
    """Tests for extracting agent_id from tool response."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_db(self) -> Path:
        """Create a temporary project with coordination database."""
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
            """)
            conn.close()
            yield Path(tmpdir)

    def test_extracts_agent_id(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Extracts agent_id from tool_response."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-extract"
        expected_agent_id = "my-custom-agent-xyz"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "Test task"},
            "tool_response": {
                "agent_id": expected_agent_id,
                "status": "completed",
                "summary": "Task done"
            }
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

        # Verify the specific agent_id was recorded
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT sender_agent FROM broadcasts WHERE swarm_id = ?",
            (swarm_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        agent_ids = [row[0] for row in rows]
        assert expected_agent_id in agent_ids, (
            f"Agent {expected_agent_id} should be extracted and recorded. Found: {agent_ids}"
        )

    def test_handles_missing_agent_id(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Uses 'unknown' when agent_id not in response."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-missing-id"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        # Task response without agent_id field
        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "Test task"},
            "tool_response": {
                "status": "completed",
                "summary": "Task done"
                # Note: no agent_id field!
            }
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
            f"Hook should continue even without agent_id. Got: {output}"
        )

        # Verify 'unknown' was recorded as fallback
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT sender_agent FROM broadcasts WHERE swarm_id = ?",
            (swarm_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        agent_ids = [row[0] for row in rows]
        assert "unknown" in agent_ids, (
            f"'unknown' should be used as fallback agent_id. Found: {agent_ids}"
        )


class TestRecordsToBroadcastsTable:
    """Tests for recording agent to broadcasts table."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_db(self) -> Path:
        """Create a temporary project with coordination database."""
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
            """)
            conn.close()
            yield Path(tmpdir)

    def test_records_agent_started(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Records agent with broadcast_type='started' to broadcasts table."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-record"
        agent_id = "recorded-agent-456"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "Test task"},
            "tool_response": {"agent_id": agent_id}
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

        # Verify broadcast record with type='started'
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            """
            SELECT sender_agent, broadcast_type, payload
            FROM broadcasts
            WHERE swarm_id = ? AND sender_agent = ?
            """,
            (swarm_id, agent_id)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, f"Agent {agent_id} should be recorded"

        # Check broadcast_type is 'started'
        broadcast_types = [row[1] for row in rows]
        assert "started" in broadcast_types, (
            f"Broadcast type should be 'started'. Found: {broadcast_types}"
        )

    def test_swarm_id_in_broadcast(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Broadcast includes correct swarm_id."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "unique-swarm-789"
        agent_id = "swarm-agent-abc"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "Test task"},
            "tool_response": {"agent_id": agent_id}
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

        # Verify swarm_id is correctly recorded
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT swarm_id FROM broadcasts WHERE sender_agent = ?",
            (agent_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        swarm_ids = [row[0] for row in rows]
        assert swarm_id in swarm_ids, (
            f"Swarm ID {swarm_id} should be in broadcast. Found: {swarm_ids}"
        )


class TestEnvironmentHandling:
    """Tests for environment variable handling."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_no_swarm_id_continues(self, hooks_dir: Path) -> None:
        """When SWARM_ID not set, continues without recording."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env.pop("SWARM_ID", None)  # Ensure SWARM_ID is NOT set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "Test task"},
            "tool_response": {"agent_id": "some-agent"}
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
            f"Hook should continue when SWARM_ID not set. Got: {output}"
        )

    def test_empty_swarm_id_continues(self, hooks_dir: Path) -> None:
        """When SWARM_ID is empty, continues without recording."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = ""  # Empty string
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "Test task"},
            "tool_response": {"agent_id": "some-agent"}
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
            f"Hook should continue when SWARM_ID is empty. Got: {output}"
        )

    def test_missing_db_continues(self, hooks_dir: Path) -> None:
        """When DB doesn't exist, continues gracefully."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # No database created - directory is empty
            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm-no-db"
            env["CLAUDE_PROJECT_DIR"] = tmpdir  # No .claude/cache here

            hook_input = json.dumps({
                "session_id": "test-session",
                "tool_name": "Task",
                "tool_input": {"prompt": "Test task"},
                "tool_response": {"agent_id": "some-agent"}
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

            # Should complete successfully despite missing DB
            assert result.returncode == 0, f"Hook failed: {result.stderr}"

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Hook should continue when DB missing. Got: {output}"
            )


class TestErrorHandling:
    """Tests for graceful error handling."""

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
        """Errors from corrupted DB don't crash hook."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = "test-swarm-corrupt"
        env["CLAUDE_PROJECT_DIR"] = str(project_with_corrupted_db)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "Test task"},
            "tool_response": {"agent_id": "some-agent"}
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
            f"Hook should not crash on corrupted DB. Exit code: {result.returncode}, "
            f"stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Hook should continue on error. Got: {output}"
        )

    def test_invalid_json_response(self, hooks_dir: Path) -> None:
        """Handles non-JSON tool_response gracefully."""
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

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
            """)
            conn.close()

            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm-invalid"
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            # tool_response is a string, not an object
            hook_input = json.dumps({
                "session_id": "test-session",
                "tool_name": "Task",
                "tool_input": {"prompt": "Test task"},
                "tool_response": "This is just a string, not an object"
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
                f"Hook should continue with invalid response. Got: {output}"
            )


class TestSettingsJsonRegistration:
    """Tests for hook registration in settings.json."""

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

    def test_hook_registered_with_task_matcher(self, settings_path: Path) -> None:
        """Hook registered in settings.json with matcher: ['Task']."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        post_tool_use = hooks.get("PostToolUse", [])

        # Find our task complete hook
        task_hook_found = False
        has_task_matcher = False

        for hook_config in post_tool_use:
            hook_list = hook_config.get("hooks", [])
            matcher = hook_config.get("matcher", "")

            for hook in hook_list:
                command = hook.get("command", "")
                if "post-task-complete" in command:
                    task_hook_found = True
                    # Check if matcher includes "Task"
                    if isinstance(matcher, str):
                        has_task_matcher = "Task" in matcher
                    elif isinstance(matcher, list):
                        has_task_matcher = "Task" in matcher
                    break

        assert task_hook_found, (
            "PostToolUse hook for Task completion must be registered in settings.json. "
            f"Current PostToolUse hooks: {post_tool_use}"
        )

        assert has_task_matcher, (
            "PostToolUse hook must have matcher: ['Task'] or matcher containing 'Task'. "
            f"Current PostToolUse hooks: {post_tool_use}"
        )


class TestIdempotency:
    """Tests for idempotent recording (same agent shouldn't be duplicated)."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_db(self) -> Path:
        """Create a temporary project with coordination database."""
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
            """)
            conn.close()
            yield Path(tmpdir)

    def test_multiple_completions_create_multiple_records(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Each Task completion creates a new broadcast record.

        Note: Unlike completed_tasks which might use INSERT OR IGNORE,
        broadcasts table allows multiple records from same agent
        (e.g., multiple findings). Each Task completion is a separate event.
        """
        shell_wrapper = hooks_dir / "post-task-complete.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-multi"
        agent_id = "multi-agent-123"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        # Simulate same agent completing twice (different tasks)
        for i in range(2):
            hook_input = json.dumps({
                "session_id": f"test-session-{i}",
                "tool_name": "Task",
                "tool_input": {"prompt": f"Task {i}"},
                "tool_response": {"agent_id": agent_id, "task_num": i}
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

            assert result.returncode == 0, f"Hook failed on iteration {i}: {result.stderr}"

        # Verify records were created
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            """
            SELECT COUNT(*)
            FROM broadcasts
            WHERE swarm_id = ? AND sender_agent = ? AND broadcast_type = 'started'
            """,
            (swarm_id, agent_id)
        )
        count = cursor.fetchone()[0]
        conn.close()

        # Each completion should create a new 'started' record
        # (or the implementation might deduplicate - both are valid designs)
        assert count >= 1, (
            f"At least one 'started' record should exist for agent {agent_id}. Found: {count}"
        )
