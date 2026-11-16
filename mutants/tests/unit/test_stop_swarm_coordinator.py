"""Tests for Stop hook swarm coordinator (Phase 12.5).

These tests verify that the Stop hook correctly:
1. Blocks the Stop event until all agents in a swarm have completed
2. Checks stop_hook_active to prevent infinite loops
3. Queries broadcasts table ONLY for "done" count vs total agents
   - Done = COUNT(DISTINCT sender_agent) WHERE broadcast_type = 'done'
   - Total = COUNT(DISTINCT sender_agent) from all broadcasts
4. Returns block when not all done, continue when all done
5. Handles missing DB and errors gracefully

Note: Uses broadcasts table only (no completed_tasks dependency).

See plan: thoughts/shared/plans/2025-12-28-user-triggered-agentica.md (Phase 12.5)
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestStopHookFiles:
    """Tests for Stop hook file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Verify stop-swarm-coordinator.sh shell wrapper exists."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}"
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Verify shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}"
        )

    def test_typescript_handler_exists(self, hooks_dir: Path) -> None:
        """Verify stop-swarm-coordinator.ts TypeScript handler exists."""
        ts_handler = hooks_dir / "src" / "stop-swarm-coordinator.ts"

        assert ts_handler.exists(), (
            f"TypeScript handler not found: {ts_handler}"
        )

    def test_shell_wrapper_calls_typescript(self, hooks_dir: Path) -> None:
        """Verify shell wrapper invokes TypeScript via npx tsx."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        content = shell_wrapper.read_text()

        # Should call npx tsx with the TypeScript file
        assert "npx tsx" in content or "node dist/" in content, (
            "Shell wrapper should invoke TypeScript via 'npx tsx' or compiled JS"
        )
        assert "stop-swarm-coordinator" in content, (
            "Shell wrapper should reference stop-swarm-coordinator handler"
        )


class TestStopHookBlocksWhenAgentsPending:
    """Tests for Stop hook blocking when not all agents have completed."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_partial_swarm(self) -> Path:
        """Create project with swarm where not all agents are done.

        Uses broadcasts-only schema:
        - 3 agents have broadcast (registered in swarm)
        - Only 1 agent has broadcast "done"
        - Hook should block waiting for 2 more agents
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

            swarm_id = "test-swarm-partial"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # All 3 agents broadcast "started" to register in the swarm
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # Only agent-1 has broadcast "done"
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("bc1", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "Agent 1 done"}), now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_stop_hook_blocks_when_agents_pending(
        self,
        hooks_dir: Path,
        project_with_partial_swarm: tuple[Path, str]
    ) -> None:
        """Stop hook blocks when agents haven't all broadcast done."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_partial_swarm

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-123",
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

        # Should block because not all agents are done
        assert output.get("result") == "block", (
            f"Hook should block when agents pending. Got: {output}"
        )

        # Message should indicate waiting
        message = output.get("message", "")
        assert "waiting" in message.lower() or "agent" in message.lower(), (
            f"Block message should indicate waiting. Got: {message}"
        )


class TestStopHookContinuesWhenAllDone:
    """Tests for Stop hook allowing stop when all agents complete."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_complete_swarm(self) -> Path:
        """Create project with swarm where all agents are done.

        Uses broadcasts-only schema:
        - 3 agents have broadcast (registered in swarm)
        - All 3 agents have broadcast "done"
        - Hook should allow stop (continue)
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
            """)

            swarm_id = "test-swarm-complete"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # ALL 3 agents have broadcast "done" (they are also registered by this)
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"bc{i}", swarm_id, agent, "done",
                     json.dumps({"summary": f"{agent} done"}), now)
                )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_stop_hook_continues_when_all_done(
        self,
        hooks_dir: Path,
        project_with_complete_swarm: tuple[Path, str]
    ) -> None:
        """Stop hook allows stop when all agents broadcast done."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_complete_swarm

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-456",
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

        # Should continue because all agents are done
        assert output.get("result") == "continue", (
            f"Hook should continue when all done. Got: {output}"
        )


class TestStopHookActiveLoop:
    """Tests for stop_hook_active infinite loop prevention."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_pending_swarm(self) -> Path:
        """Create project with swarm where agents are pending (would normally block).

        Uses broadcasts-only schema:
        - 3 agents have broadcast (registered in swarm)
        - Only 1 agent has broadcast "done"
        - Hook WOULD block, but stop_hook_active=true should bypass
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
            """)

            swarm_id = "test-swarm-loop"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # All 3 agents broadcast "started" to register in the swarm
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # Only agent-1 has broadcast "done"
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("bc1", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "Agent 1 done"}), now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_stop_hook_active_prevents_loop(
        self,
        hooks_dir: Path,
        project_with_pending_swarm: tuple[Path, str]
    ) -> None:
        """When stop_hook_active=true, hook returns continue immediately."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_pending_swarm

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        # Signal that we're already in a stop hook (prevent infinite loop)
        hook_input = json.dumps({
            "session_id": "test-session-loop",
            "stop_hook_active": True,  # Key flag!
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

        # Should continue immediately to prevent infinite loop
        # Even though there are pending agents
        assert output.get("result") == "continue", (
            f"Hook must continue when stop_hook_active=true to prevent loops. Got: {output}"
        )


class TestNoSwarmIdContinues:
    """Tests for Stop hook behavior when not in a swarm."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_no_swarm_id_continues(self, hooks_dir: Path) -> None:
        """When SWARM_ID not set, hook returns continue."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env.pop("SWARM_ID", None)  # Ensure SWARM_ID is NOT set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

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

        # Should continue because not in a swarm
        assert output.get("result") == "continue", (
            f"Hook should continue when SWARM_ID not set. Got: {output}"
        )

    def test_empty_swarm_id_continues(self, hooks_dir: Path) -> None:
        """When SWARM_ID is empty string, hook returns continue."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = ""  # Empty string
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-empty-swarm",
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


class TestMissingDbContinues:
    """Tests for graceful degradation when DB is missing."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_missing_db_continues(self, hooks_dir: Path) -> None:
        """When DB doesn't exist, hook returns continue gracefully."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # No database created - directory is empty
            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm-no-db"
            env["CLAUDE_PROJECT_DIR"] = tmpdir  # No .claude/cache here

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

            # Should complete successfully despite missing DB
            assert result.returncode == 0, f"Hook failed: {result.stderr}"

            output = json.loads(result.stdout.strip())

            # Should continue gracefully
            assert output.get("result") == "continue", (
                f"Hook should continue when DB missing. Got: {output}"
            )

    def test_missing_cache_dir_continues(self, hooks_dir: Path) -> None:
        """When .claude/cache directory doesn't exist, hook returns continue."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

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


class TestErrorHandlingGraceful:
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

    def test_error_handling_graceful(
        self,
        hooks_dir: Path,
        project_with_corrupted_db: Path
    ) -> None:
        """Errors don't crash the hook, return continue."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        env = os.environ.copy()
        env["SWARM_ID"] = "test-swarm-error"
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

    def test_invalid_json_input_graceful(self, hooks_dir: Path) -> None:
        """Hook handles invalid JSON input gracefully."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

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

        # Even with invalid input, hook should not crash catastrophically
        # It can return non-zero, but output should still be valid JSON
        # with result: 'continue' for graceful degradation
        if result.returncode == 0:
            output = json.loads(result.stdout.strip())
            # If it succeeded, should continue
            assert output.get("result") in ["continue", "block"], (
                f"Hook output should have valid result. Got: {output}"
            )


class TestSettingsJsonRegistration:
    """Tests for Stop hook registration in settings.json."""

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

    def test_stop_hook_registered(self, settings_path: Path) -> None:
        """Verify Stop hook for swarm coordination is registered."""
        if not settings_path.exists():
            pytest.skip("settings.json doesn't exist yet")

        with open(settings_path) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        stop_hooks = hooks.get("Stop", [])

        # Find our swarm coordinator hook
        swarm_hook_found = False
        for hook_config in stop_hooks:
            hook_list = hook_config.get("hooks", [])
            for hook in hook_list:
                command = hook.get("command", "")
                if "stop-swarm-coordinator" in command:
                    swarm_hook_found = True
                    break

        assert swarm_hook_found, (
            "Stop hook for swarm coordination must be registered in settings.json. "
            f"Current Stop hooks: {stop_hooks}"
        )


class TestSwarmCompletionCounting:
    """Tests for accurate counting of completed agents."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_duplicate_dones(self) -> Path:
        """Create project where same agent broadcasts done multiple times.

        Uses broadcasts-only schema:
        - 2 agents have broadcast (registered in swarm)
        - Agent-1 broadcasts "done" twice (should count as 1 distinct)
        - Agent-2 has broadcast "started" but NOT "done"
        - Hook should block waiting for 1 agent
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
            """)

            swarm_id = "test-swarm-dups"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # Both agents broadcast "started" to register in the swarm
            for i, agent in enumerate(["agent-1", "agent-2"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # Agent-1 broadcasts done TWICE (should count as 1 distinct)
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("bc1", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "Agent 1 first done"}), now)
            )
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("bc2", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "Agent 1 second done"}), now)
            )

            # Agent-2 has NOT broadcast "done" yet

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_duplicate_done_counted_once(
        self,
        hooks_dir: Path,
        project_with_duplicate_dones: tuple[Path, str]
    ) -> None:
        """Same agent broadcasting done multiple times counts as one."""
        shell_wrapper = hooks_dir / "stop-swarm-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")

        project_dir, swarm_id = project_with_duplicate_dones

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-dups",
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

        # Should block because agent-2 is not done
        # Even though there are 2 "done" broadcasts, only 1 DISTINCT agent
        assert output.get("result") == "block", (
            f"Hook should block when counting distinct agents. Got: {output}"
        )

        # Message should indicate waiting for 1 agent
        message = output.get("message", "")
        assert "1" in message or "one" in message.lower(), (
            f"Should be waiting for 1 agent. Got: {message}"
        )
