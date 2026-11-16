"""Tests for PreToolUse broadcast hook (Phases 10-12).

These tests verify that the PreToolUse hook correctly:
1. Continues without action when SWARM_ID is not set
2. Injects broadcast context when SWARM_ID is set and broadcasts exist
3. Handles missing database gracefully
4. Excludes own broadcasts (exclude_sender)
5. Formats broadcast context correctly

Tests are designed to FAIL initially (TDD approach) until Phases 10-12 are implemented.
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest


class TestPreToolUseHookFiles:
    """Tests for PreToolUse hook file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Verify pre-tool-use-broadcast.sh shell wrapper exists."""
        shell_wrapper = hooks_dir / "pre-tool-use-broadcast.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}"
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Verify shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "pre-tool-use-broadcast.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        # Check if file has executable bit
        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}"
        )

    def test_typescript_handler_exists(self, hooks_dir: Path) -> None:
        """Verify pre-tool-use-broadcast.ts TypeScript handler exists."""
        ts_handler = hooks_dir / "src" / "pre-tool-use-broadcast.ts"

        assert ts_handler.exists(), (
            f"TypeScript handler not found: {ts_handler}"
        )

    def test_shell_wrapper_calls_compiled_js(self, hooks_dir: Path) -> None:
        """Verify shell wrapper invokes compiled JavaScript via node."""
        shell_wrapper = hooks_dir / "pre-tool-use-broadcast.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        assert "node dist/pre-tool-use-broadcast.mjs" in content, (
            "Shell wrapper should invoke compiled JS via 'node dist/pre-tool-use-broadcast.mjs'"
        )


class TestPreToolUseHookBehavior:
    """Tests for PreToolUse hook behavior with mocked environment."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create a temporary coordination database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "coordination.db"
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
            yield db_path

    def test_hook_continues_without_swarm_id(self, hooks_dir: Path) -> None:
        """When SWARM_ID not set, hook returns continue."""
        shell_wrapper = hooks_dir / "pre-tool-use-broadcast.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        # Create input JSON
        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/path"}
        })

        # Run hook without SWARM_ID
        env = os.environ.copy()
        env.pop("SWARM_ID", None)  # Ensure not set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Should complete successfully
        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Parse output
        output = json.loads(result.stdout.strip())

        assert output.get("result") == "continue", (
            "Hook should return 'continue' when SWARM_ID not set"
        )
        # Should NOT have a message when no broadcasts
        assert output.get("message") is None or output.get("message") == "", (
            "Hook should not inject message when SWARM_ID not set"
        )

    def test_hook_handles_missing_db(self, hooks_dir: Path) -> None:
        """When coordination.db doesn't exist, hook continues gracefully."""
        shell_wrapper = hooks_dir / "pre-tool-use-broadcast.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up environment with non-existent DB path
            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm-123"
            env["AGENT_ID"] = "agent-1"
            env["CLAUDE_PROJECT_DIR"] = tmpdir  # No .claude/cache here

            hook_input = json.dumps({
                "session_id": "test-session",
                "tool_name": "Read",
                "tool_input": {}
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
                "Hook should return 'continue' when DB missing"
            )


class TestPreToolUseBroadcastInjection:
    """Tests for broadcast context injection behavior."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_db(self) -> Path:
        """Create a temporary project with coordination database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude/cache/agentica-coordination directory
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

    def test_hook_injects_broadcasts_when_swarm_id_set(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """When SWARM_ID set and broadcasts exist, hook injects context."""
        shell_wrapper = hooks_dir / "pre-tool-use-broadcast.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-abc"

        # Insert a broadcast into the database
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        conn.execute(
            """
            INSERT INTO broadcasts (id, swarm_id, sender_agent, broadcast_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "bc1",
                swarm_id,
                "other-agent",
                "finding",
                json.dumps({"finding": "Important discovery"}),
                now
            )
        )
        conn.commit()
        conn.close()

        # Set up environment
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["AGENT_ID"] = "current-agent"
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {}
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
        assert output.get("result") == "continue"

        # Should have injected broadcast context
        message = output.get("message", "")
        assert message, "Hook should inject message when broadcasts exist"
        assert "SWARM BROADCASTS" in message or "other-agent" in message, (
            f"Message should contain broadcast info. Got: {message}"
        )

    def test_hook_excludes_own_broadcasts(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Hook excludes broadcasts from current agent (exclude_sender)."""
        shell_wrapper = hooks_dir / "pre-tool-use-broadcast.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "test-swarm-xyz"
        current_agent = "agent-self"

        # Insert broadcasts - one from self, one from other
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # Own broadcast (should be excluded)
        conn.execute(
            """
            INSERT INTO broadcasts (id, swarm_id, sender_agent, broadcast_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("bc-self", swarm_id, current_agent, "finding",
             json.dumps({"finding": "My own finding"}), now)
        )

        # Other agent's broadcast (should be included)
        conn.execute(
            """
            INSERT INTO broadcasts (id, swarm_id, sender_agent, broadcast_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("bc-other", swarm_id, "other-agent", "finding",
             json.dumps({"finding": "Other agent finding"}), now)
        )
        conn.commit()
        conn.close()

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["AGENT_ID"] = current_agent
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {}
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
        message = output.get("message", "")

        # Should include other agent's broadcast
        assert "other-agent" in message or "Other agent finding" in message, (
            f"Should include other agent's broadcast. Got: {message}"
        )

        # Should NOT include own broadcast
        assert "My own finding" not in message, (
            f"Should exclude own broadcasts. Got: {message}"
        )


class TestPreToolUseBroadcastFormatting:
    """Tests for broadcast context formatting."""

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

    def test_hook_formats_broadcast_context(
        self,
        hooks_dir: Path,
        project_with_db: Path
    ) -> None:
        """Broadcast context is formatted correctly for injection."""
        shell_wrapper = hooks_dir / "pre-tool-use-broadcast.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        swarm_id = "format-test-swarm"

        # Insert multiple broadcasts with different types
        db_path = (
            project_with_db / ".claude" / "cache" /
            "agentica-coordination" / "coordination.db"
        )
        conn = sqlite3.connect(str(db_path))
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        conn.execute(
            "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
            ("bc1", swarm_id, "researcher", "finding",
             json.dumps({"finding": "Found security vulnerability"}), now)
        )
        conn.execute(
            "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
            ("bc2", swarm_id, "analyst", "blocker",
             json.dumps({"blocker": "Need API access", "severity": "high"}), now)
        )
        conn.commit()
        conn.close()

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["AGENT_ID"] = "current-agent"
        env["CLAUDE_PROJECT_DIR"] = str(project_with_db)

        hook_input = json.dumps({
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {}
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
        message = output.get("message", "")

        # Check formatting includes key elements
        assert "FINDING" in message.upper() or "finding" in message.lower(), (
            f"Message should indicate broadcast type. Got: {message}"
        )
        assert "researcher" in message or "analyst" in message, (
            f"Message should include sender. Got: {message}"
        )


class TestSettingsJsonRegistration:
    """Tests for PreToolUse hook registration in settings.json (Phase 12)."""

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

    def test_pre_tool_use_hook_registered(self, settings_path: Path) -> None:
        """Verify PreToolUse hook for broadcasts is registered."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        pre_tool_use = hooks.get("PreToolUse", [])

        # Find our broadcast hook
        broadcast_hook_found = False
        for hook_config in pre_tool_use:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "pre-tool-use-broadcast" in command:
                    broadcast_hook_found = True
                    break

        assert broadcast_hook_found, (
            "PreToolUse hook for broadcasts must be registered in settings.json. "
            f"Current PreToolUse hooks: {pre_tool_use}"
        )
