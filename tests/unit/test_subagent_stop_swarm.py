"""Tests for SubagentStop hook for auto-completion (Phase 18.5).

These tests verify that the SubagentStop hook correctly:
1. Shell wrapper and TypeScript handler exist
2. Auto-broadcasts "done" message when agent stops
3. Persists "done" broadcast to the broadcasts table
4. Checks if all agents in swarm have completed
5. Injects synthesis context when all agents done
6. No synthesis message when agents still pending
7. Continues silently when SWARM_ID is not set
8. Handles missing DB and corrupted DB gracefully
9. Is registered in settings.json

SubagentStop input structure:
```typescript
interface SubagentStopInput {
    session_id: string;
    agent_id: string;
    agent_type: string;
}
```

Tests are designed to FAIL initially (TDD approach) until Phase 18.5 is implemented.

See plan: thoughts/shared/plans/2025-12-28-user-triggered-agentica.md (Phase 18.5)
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestSubagentStopHookFiles:
    """Tests for SubagentStop hook file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper exists at expected path."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}. "
            "Create .claude/hooks/subagent-stop-swarm.sh"
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}. "
            "Run: chmod +x .claude/hooks/subagent-stop-swarm.sh"
        )

    def test_typescript_handler_exists(self, hooks_dir: Path) -> None:
        """TypeScript handler exists at expected path."""
        ts_handler = hooks_dir / "src" / "subagent-stop-swarm.ts"

        assert ts_handler.exists(), (
            f"TypeScript handler not found: {ts_handler}. "
            "Create .claude/hooks/src/subagent-stop-swarm.ts"
        )

    def test_shell_wrapper_invokes_typescript(self, hooks_dir: Path) -> None:
        """Shell wrapper invokes TypeScript via npx tsx or compiled JS."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        # Should call npx tsx with the TypeScript file or node with compiled JS
        has_tsx = "npx tsx" in content
        has_node = "node dist/" in content
        has_reference = "subagent-stop-swarm" in content

        assert has_tsx or has_node, (
            "Shell wrapper should invoke TypeScript via 'npx tsx' or compiled JS via 'node dist/'. "
            f"Content: {content}"
        )
        assert has_reference, (
            "Shell wrapper should reference subagent-stop-swarm handler. "
            f"Content: {content}"
        )


class TestAutoBroadcastsDone:
    """Tests for auto-broadcasting 'done' message when agent stops."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_empty_swarm(self) -> tuple[Path, str]:
        """Create project with empty broadcasts table for a swarm."""
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
            conn.commit()
            conn.close()

            swarm_id = "test-swarm-auto-done"
            yield Path(tmpdir), swarm_id

    def test_auto_broadcasts_done(
        self,
        hooks_dir: Path,
        project_with_empty_swarm: tuple[Path, str]
    ) -> None:
        """Hook creates 'done' broadcast when agent stops."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_empty_swarm
        agent_id = "stopping-agent-123"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-done",
            "agent_id": agent_id,
            "agent_type": "general-purpose",
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

        # Verify broadcast was created in the database
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM broadcasts WHERE swarm_id = ? AND sender_agent = ? AND broadcast_type = 'done'",
            (swarm_id, agent_id)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"Hook should create 'done' broadcast for agent {agent_id}. "
            f"Found {len(rows)} rows."
        )

    def test_done_broadcast_in_db(
        self,
        hooks_dir: Path,
        project_with_empty_swarm: tuple[Path, str]
    ) -> None:
        """Done broadcast persisted to broadcasts table with correct fields."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_empty_swarm
        agent_id = "db-test-agent-456"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-db",
            "agent_id": agent_id,
            "agent_type": "Explore",
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

        # Check database contents
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM broadcasts WHERE swarm_id = ? AND broadcast_type = 'done'",
            (swarm_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, "Should have at least one 'done' broadcast"

        row = rows[0]
        assert row["swarm_id"] == swarm_id, f"swarm_id mismatch: {row['swarm_id']}"
        assert row["sender_agent"] == agent_id, f"sender_agent mismatch: {row['sender_agent']}"
        assert row["broadcast_type"] == "done", f"broadcast_type mismatch: {row['broadcast_type']}"
        assert row["id"] is not None, "Broadcast should have an id"
        assert row["created_at"] is not None, "Broadcast should have created_at"

        # Payload should be valid JSON
        payload = json.loads(row["payload"])
        assert isinstance(payload, dict), f"Payload should be dict, got {type(payload)}"


class TestSwarmCompletionCheck:
    """Tests for checking if all agents in swarm have completed."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_partial_swarm(self) -> tuple[Path, str]:
        """Create project with swarm where some agents have already completed.

        - 3 agents have broadcast (registered in swarm via 'started')
        - 2 agents already broadcast 'done'
        - The stopping agent (agent-3) will be the last one
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
            """)

            swarm_id = "test-swarm-synthesis"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # All 3 agents started (registered in swarm)
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # Agent-1 and Agent-2 already done
            for i, agent in enumerate(["agent-1", "agent-2"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"done{i}", swarm_id, agent, "done",
                     json.dumps({"summary": f"{agent} completed"}), now)
                )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_injects_synthesis_context_when_all_done(
        self,
        hooks_dir: Path,
        project_with_partial_swarm: tuple[Path, str]
    ) -> None:
        """When all agents done, injects synthesis message."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_partial_swarm
        # agent-3 is the last agent stopping
        agent_id = "agent-3"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-synthesis",
            "agent_id": agent_id,
            "agent_type": "general-purpose",
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

        # When all agents complete, should have synthesis message
        message = output.get("message", "")
        assert message, (
            "Hook should inject synthesis context when all agents complete. "
            f"Got empty message. Output: {output}"
        )

        # Message should mention synthesis or completion
        message_lower = message.lower()
        assert "synth" in message_lower or "complete" in message_lower or "all" in message_lower, (
            f"Synthesis message should mention synthesis/complete/all. Got: {message}"
        )

    @pytest.fixture
    def project_with_pending_agents(self) -> tuple[Path, str]:
        """Create project with swarm where some agents are still pending.

        - 3 agents have broadcast 'started' (registered in swarm)
        - Only 1 agent has broadcast 'done'
        - The stopping agent (agent-2) is NOT the last one (agent-3 still pending)
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
            """)

            swarm_id = "test-swarm-pending"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # All 3 agents started
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # Only agent-1 has broadcast 'done'
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("done1", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "agent-1 completed"}), now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_no_synthesis_when_agents_pending(
        self,
        hooks_dir: Path,
        project_with_pending_agents: tuple[Path, str]
    ) -> None:
        """When agents still pending, no synthesis message."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_pending_agents
        # agent-2 is stopping, but agent-3 is still pending
        agent_id = "agent-2"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-pending",
            "agent_id": agent_id,
            "agent_type": "general-purpose",
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

        # When agents still pending, should NOT have synthesis message
        message = output.get("message", "")

        # Message should be empty or not mention synthesis
        if message:
            message_lower = message.lower()
            assert "synth" not in message_lower and "all" not in message_lower, (
                f"Should not inject synthesis when agents pending. Got: {message}"
            )


class TestNoSwarmIdContinues:
    """Tests for behavior when SWARM_ID is not set."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_no_swarm_id_continues(self, hooks_dir: Path) -> None:
        """When SWARM_ID not set, continues without broadcasting."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env.pop("SWARM_ID", None)  # Ensure SWARM_ID is NOT set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-no-swarm",
            "agent_id": "orphan-agent-123",
            "agent_type": "general-purpose",
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
            f"Hook should return 'continue' when no SWARM_ID. Got: {output}"
        )

        # No message should be injected (or minimal)
        message = output.get("message", "")
        assert "swarm" not in message.lower(), (
            f"Hook should not mention swarm when SWARM_ID not set. Got message: {message}"
        )

    def test_empty_swarm_id_continues(self, hooks_dir: Path) -> None:
        """When SWARM_ID is empty string, continues without broadcasting."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = ""  # Empty string
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-empty-swarm",
            "agent_id": "agent-empty-swarm",
            "agent_type": "Explore",
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
            f"Hook should return 'continue' when SWARM_ID is empty. Got: {output}"
        )


class TestMissingDbContinues:
    """Tests for graceful degradation when DB is missing."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_missing_db_continues(self, hooks_dir: Path) -> None:
        """When DB doesn't exist, hook returns continue gracefully."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # No database created - directory is empty
            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm-no-db"
            env["CLAUDE_PROJECT_DIR"] = tmpdir  # No .claude/cache here

            hook_input = json.dumps({
                "session_id": "test-session-no-db",
                "agent_id": "agent-no-db",
                "agent_type": "general-purpose",
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

            # Should continue gracefully
            assert output.get("result") == "continue", (
                f"Hook should continue when DB missing. Got: {output}"
            )

    def test_missing_cache_dir_continues(self, hooks_dir: Path) -> None:
        """When .claude/cache directory doesn't exist, hook returns continue."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude but NOT cache subdirectory
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()

            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm-no-cache"
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            hook_input = json.dumps({
                "session_id": "test-session-no-cache",
                "agent_id": "agent-no-cache",
                "agent_type": "general-purpose",
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
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = "test-swarm-error"
        env["CLAUDE_PROJECT_DIR"] = str(project_with_corrupted_db)

        hook_input = json.dumps({
            "session_id": "test-session-error",
            "agent_id": "agent-error",
            "agent_type": "general-purpose",
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
    """Tests for SubagentStop hook registration in settings.json."""

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
        """SubagentStop hook for swarm is registered in settings.json."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        subagent_stop_hooks = hooks.get("SubagentStop", [])

        # Find our swarm hook
        swarm_hook_found = False
        for hook_config in subagent_stop_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "subagent-stop-swarm" in command:
                    swarm_hook_found = True
                    break

        assert swarm_hook_found, (
            "SubagentStop hook for swarm coordination must be registered in settings.json. "
            "Expected hooks.SubagentStop to contain command with 'subagent-stop-swarm'. "
            f"Current SubagentStop hooks: {subagent_stop_hooks}"
        )

    def test_hook_uses_project_dir(self, settings_path: Path) -> None:
        """SubagentStop hook command uses $CLAUDE_PROJECT_DIR."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        subagent_stop_hooks = hooks.get("SubagentStop", [])

        # Find our swarm hook and check path
        for hook_config in subagent_stop_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "subagent-stop-swarm" in command:
                    assert "$CLAUDE_PROJECT_DIR" in command, (
                        "Hook command should use $CLAUDE_PROJECT_DIR for project-local hooks. "
                        f"Got: {command}"
                    )
                    return

        pytest.skip("SubagentStop swarm hook not found")


class TestDoneBroadcastAutoPayload:
    """Tests for the auto-generated 'done' broadcast payload."""

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
                CREATE INDEX IF NOT EXISTS idx_broadcasts_swarm
                    ON broadcasts(swarm_id, created_at);
            """)
            conn.commit()
            conn.close()

            swarm_id = "test-swarm-payload"
            yield Path(tmpdir), swarm_id

    def test_done_payload_has_auto_flag(
        self,
        hooks_dir: Path,
        project_with_swarm: tuple[Path, str]
    ) -> None:
        """Auto-generated done broadcast payload has 'auto': true flag."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_swarm
        agent_id = "auto-payload-agent"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-payload",
            "agent_id": agent_id,
            "agent_type": "general-purpose",
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

        # Check the payload in the database
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT payload FROM broadcasts WHERE swarm_id = ? AND sender_agent = ? AND broadcast_type = 'done'",
            (swarm_id, agent_id)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, "Should have at least one 'done' broadcast"

        payload = json.loads(rows[0]["payload"])
        assert payload.get("auto") is True, (
            f"Auto-generated done broadcast should have 'auto': true. Got: {payload}"
        )


class TestDistinctAgentCounting:
    """Tests for counting distinct agents (not duplicate broadcasts)."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_duplicate_dones(self) -> tuple[Path, str]:
        """Create project where one agent has multiple 'done' broadcasts.

        - 2 agents in swarm
        - agent-1 has broadcast 'done' twice (duplicates)
        - agent-2 (stopping) should trigger synthesis (all done)
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
            """)

            swarm_id = "test-swarm-dups"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # Both agents started
            for i, agent in enumerate(["agent-1", "agent-2"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # Agent-1 broadcasts done TWICE (duplicates)
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("done1a", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "first done"}), now)
            )
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("done1b", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "second done"}), now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_counts_distinct_agents_not_broadcasts(
        self,
        hooks_dir: Path,
        project_with_duplicate_dones: tuple[Path, str]
    ) -> None:
        """Counts distinct sender_agent, not total 'done' broadcasts."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_duplicate_dones
        # agent-2 is stopping - should complete the swarm
        agent_id = "agent-2"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-dups",
            "agent_id": agent_id,
            "agent_type": "general-purpose",
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

        # Should trigger synthesis because:
        # - agent-1 done (counts as 1, not 2)
        # - agent-2 done (just broadcast by this hook)
        # Total: 2 done out of 2 agents = all done
        message = output.get("message", "")
        assert message, (
            "Hook should inject synthesis context when all agents complete. "
            "Got empty message (duplicate broadcasts may have caused overcounting)."
        )


class TestErrorHandling:
    """Tests for graceful error handling."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_invalid_json_input_graceful(self, hooks_dir: Path) -> None:
        """Hook handles invalid JSON input gracefully."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = "test-swarm"
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

    def test_missing_agent_id_graceful(self, hooks_dir: Path) -> None:
        """Hook handles missing agent_id gracefully (older Claude Code versions)."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create DB so hook can attempt to write
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
            conn.commit()
            conn.close()

            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm-missing-id"
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            # Input without agent_id (older Claude Code version)
            hook_input = json.dumps({
                "session_id": "test-session-old-version",
                # Note: no agent_id field!
                "agent_type": "general-purpose",
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
                f"Hook should not crash when agent_id missing. "
                f"Exit code: {result.returncode}, stderr: {result.stderr}"
            )

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Hook should continue when agent_id missing. Got: {output}"
            )


class TestAlwaysReturnsContinue:
    """Tests to ensure SubagentStop hook never blocks."""

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
            """)
            conn.commit()
            conn.close()

            swarm_id = "test-swarm-never-block"
            yield Path(tmpdir), swarm_id

    def test_always_returns_continue(
        self,
        hooks_dir: Path,
        project_with_swarm: tuple[Path, str]
    ) -> None:
        """SubagentStop hook should always return continue (never block)."""
        shell_wrapper = hooks_dir / "subagent-stop-swarm.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_swarm
        agent_id = "never-block-agent"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-never-block",
            "agent_id": agent_id,
            "agent_type": "general-purpose",
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

        # SubagentStop should NEVER block - it's for recording completion
        assert output.get("result") == "continue", (
            f"SubagentStop hook should always return 'continue', never 'block'. "
            f"Got: {output}"
        )
