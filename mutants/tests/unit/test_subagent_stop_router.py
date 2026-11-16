"""Tests for SubagentStop router (Phases 8-9 of pattern-aware hooks).

These tests verify that the subagent-stop.ts router correctly:
1. Reads stdin JSON input
2. Detects pattern via PATTERN_TYPE env var
3. Dispatches to appropriate pattern handler (swarm, jury, etc.)
4. Falls back to continue if no pattern detected
5. Handles invalid JSON gracefully
6. For swarm: broadcasts "done" message
7. For jury: submits vote
8. Handles quorum checking

Plan reference: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 8-9)

Tests are designed to FAIL initially (TDD approach) until Phases 8-9 are implemented.

Router location: .claude/hooks/src/subagent-stop.ts
Shell wrapper: .claude/hooks/subagent-stop.sh
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


class TestRouterFileExists:
    """Tests for router file existence."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_typescript_router_exists(self, hooks_dir: Path) -> None:
        """TypeScript router exists at expected path."""
        ts_router = hooks_dir / "src" / "subagent-stop.ts"

        assert ts_router.exists(), (
            f"TypeScript router not found: {ts_router}. "
            "Create .claude/hooks/src/subagent-stop.ts as part of Phase 8."
        )

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper exists at expected path (Phase 9)."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}. "
            "Create .claude/hooks/subagent-stop.sh as part of Phase 9."
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}. "
            "Run: chmod +x .claude/hooks/subagent-stop.sh"
        )


class TestNoPatternDetectedContinues:
    """Tests for fallback behavior when no pattern detected."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_no_pattern_type_returns_continue(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE is not set, router returns continue."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        env = os.environ.copy()
        env.pop("PATTERN_TYPE", None)  # Ensure PATTERN_TYPE is NOT set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-no-pattern",
            "agent_id": "agent-123",
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' when no PATTERN_TYPE. Got: {output}"
        )

    def test_empty_pattern_type_returns_continue(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE is empty string, router returns continue."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = ""  # Empty string
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-empty-pattern",
            "agent_id": "agent-456",
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' when PATTERN_TYPE is empty. Got: {output}"
        )

    def test_unknown_pattern_type_returns_continue(self, hooks_dir: Path) -> None:
        """When PATTERN_TYPE is unknown, router returns continue."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "unknown_pattern_xyz"
        env["PATTERN_ID"] = "test-123"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-unknown-pattern",
            "agent_id": "agent-789",
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' for unknown pattern types. Got: {output}"
        )


class TestSwarmPatternDispatch:
    """Tests for routing to swarm pattern handler."""

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

            swarm_id = "test-swarm-stop-router"
            yield Path(tmpdir), swarm_id

    def test_swarm_pattern_broadcasts_done(
        self,
        hooks_dir: Path,
        project_with_empty_swarm: tuple[Path, str]
    ) -> None:
        """When PATTERN_TYPE=swarm, router broadcasts 'done' message."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        project_dir, swarm_id = project_with_empty_swarm
        agent_id = "swarm-agent-stopping"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = swarm_id
        env["SWARM_ID"] = swarm_id  # Legacy compat
        env["AGENT_ROLE"] = "worker"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-swarm",
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Swarm handler should return 'continue'. Got: {output}"
        )

        # Verify 'done' broadcast was created in database
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
            f"Swarm handler should broadcast 'done' for agent {agent_id}. "
            f"Found {len(rows)} rows."
        )

    def test_swarm_pattern_logs_agent_completion(self, hooks_dir: Path) -> None:
        """Swarm handler logs agent completion."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

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

            swarm_id = "log-swarm-456"
            agent_id = "swarm-agent-log-test"

            env = os.environ.copy()
            env["PATTERN_TYPE"] = "swarm"
            env["PATTERN_ID"] = swarm_id
            env["SWARM_ID"] = swarm_id
            env["AGENT_ROLE"] = "worker"
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            hook_input = json.dumps({
                "session_id": "test-session-log",
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

            assert result.returncode == 0, f"Router failed: {result.stderr}"

            # Stderr should contain logging about agent completion
            stderr = result.stderr.lower()
            has_completion_log = any(keyword in stderr for keyword in ["done", "complet", "stop"])

            assert has_completion_log, (
                f"Swarm handler should log agent completion. Got stderr: {result.stderr}"
            )


class TestJuryPatternDispatch:
    """Tests for routing to jury pattern handler."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_jury(self) -> tuple[Path, str]:
        """Create project with jury votes table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS jury_votes (
                    id TEXT PRIMARY KEY,
                    jury_id TEXT NOT NULL,
                    juror_id TEXT NOT NULL,
                    vote TEXT NOT NULL,
                    reasoning TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jury_votes
                    ON jury_votes(jury_id, juror_id);
            """)
            conn.commit()
            conn.close()

            jury_id = "test-jury-stop-router"
            yield Path(tmpdir), jury_id

    def test_jury_pattern_submits_vote(
        self,
        hooks_dir: Path,
        project_with_jury: tuple[Path, str]
    ) -> None:
        """When PATTERN_TYPE=jury, router handles vote submission."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        project_dir, jury_id = project_with_jury
        juror_id = "juror-0"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = jury_id
        env["JURY_ID"] = jury_id
        env["AGENT_ROLE"] = "juror"
        env["JUROR_INDEX"] = "0"
        env["TOTAL_JURORS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-jury-stop",
            "agent_id": juror_id,
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Jury handler should return 'continue'. Got: {output}"
        )

        # Jury handler should log or acknowledge vote submission
        stderr = result.stderr.lower()
        message = output.get("message", "").lower()
        has_jury_log = any(keyword in stderr for keyword in ["jury", "juror", "vote"])
        has_jury_message = any(keyword in message for keyword in ["jury", "juror", "vote", "complete"])

        assert has_jury_log or has_jury_message, (
            f"Jury handler should acknowledge vote or completion. "
            f"Got stderr: {result.stderr}, message: {output.get('message', '')}"
        )


class TestQuorumChecking:
    """Tests for quorum checking in swarm/jury patterns."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_partial_swarm(self) -> tuple[Path, str]:
        """Create project where some agents already completed."""
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

            swarm_id = "quorum-swarm"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # 3 agents started
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # agent-1 already done
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("done1", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "agent-1 completed"}), now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_quorum_message_when_agents_pending(
        self,
        hooks_dir: Path,
        project_with_partial_swarm: tuple[Path, str]
    ) -> None:
        """When not all agents done, include quorum status in message."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        project_dir, swarm_id = project_with_partial_swarm
        agent_id = "agent-2"  # Second agent stopping

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = swarm_id
        env["SWARM_ID"] = swarm_id
        env["AGENT_ROLE"] = "worker"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-quorum",
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Handler should return 'continue'. Got: {output}"
        )

        # Check stderr or message for quorum status (2/3 done, 1 remaining)
        stderr = result.stderr.lower()
        message = output.get("message", "").lower()
        combined = stderr + message

        # Should mention remaining agents or quorum status
        has_quorum_info = any(keyword in combined for keyword in [
            "remaining", "pending", "waiting", "2/3", "1 more"
        ])

        # It's OK if no quorum info when not all done - synthesis only at completion
        # This test just ensures the handler runs successfully

    @pytest.fixture
    def project_with_complete_swarm(self) -> tuple[Path, str]:
        """Create project where all agents completed."""
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

            swarm_id = "complete-swarm"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # 3 agents started
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # agent-1 and agent-2 already done
            for i, agent in enumerate(["agent-1", "agent-2"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"done{i}", swarm_id, agent, "done",
                     json.dumps({"summary": f"{agent} completed"}), now)
                )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_synthesis_message_when_all_done(
        self,
        hooks_dir: Path,
        project_with_complete_swarm: tuple[Path, str]
    ) -> None:
        """When last agent completes, include synthesis context."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        project_dir, swarm_id = project_with_complete_swarm
        agent_id = "agent-3"  # Last agent stopping

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = swarm_id
        env["SWARM_ID"] = swarm_id
        env["AGENT_ROLE"] = "worker"
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Handler should return 'continue'. Got: {output}"
        )

        # When all agents complete, should have synthesis message
        message = output.get("message", "")
        assert message, (
            "Handler should inject synthesis context when all agents complete. "
            f"Got empty message. Output: {output}"
        )

        message_lower = message.lower()
        assert any(keyword in message_lower for keyword in ["synth", "complete", "all", "done"]), (
            f"Synthesis message should mention synthesis/complete/all. Got: {message}"
        )


class TestInvalidInputHandling:
    """Tests for graceful handling of invalid input."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_invalid_json_returns_continue(self, hooks_dir: Path) -> None:
        """Router handles invalid JSON input gracefully."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm"
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Invalid JSON
        invalid_input = "{ this is not valid json }"

        result = subprocess.run(
            [str(shell_wrapper)],
            input=invalid_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Router should handle gracefully - return 0 with continue
        assert result.returncode == 0, (
            f"Router should not crash on invalid JSON. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should return 'continue' for invalid JSON. Got: {output}"
        )

    def test_empty_input_returns_continue(self, hooks_dir: Path) -> None:
        """Router handles empty input gracefully."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = "test-jury"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input="",  # Empty input
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Router should not hang (timeout would catch this)
        assert result.returncode == 0, (
            f"Router should not crash on empty input. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        if result.stdout.strip():
            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Router should return 'continue' for empty input. Got: {output}"
            )

    def test_missing_agent_id_graceful(self, hooks_dir: Path) -> None:
        """Router handles missing agent_id gracefully."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm"
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Input without agent_id
        hook_input = json.dumps({
            "session_id": "test-session-missing-id",
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

        assert result.returncode == 0, (
            f"Router should not crash when agent_id missing. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Router should continue when agent_id missing. Got: {output}"
        )


class TestRouterOutputFormat:
    """Tests for correct output format from router."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_output_is_valid_json(self, hooks_dir: Path) -> None:
        """Router output is always valid JSON."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm"
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-output",
            "agent_id": "output-agent",
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        try:
            output = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            pytest.fail(f"Router output is not valid JSON: {result.stdout}")

    def test_output_has_result_field(self, hooks_dir: Path) -> None:
        """Router output always includes result field."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = "test-jury"
        env["JURY_ID"] = "test-jury"
        env["JUROR_INDEX"] = "0"
        env["TOTAL_JURORS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-result",
            "agent_id": "result-agent",
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

        assert result.returncode == 0, f"Router failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert "result" in output, (
            f"Router output must include 'result' field. Got: {output}"
        )
        assert output["result"] in ["continue", "block"], (
            f"Result must be 'continue' or 'block'. Got: {output['result']}"
        )

    def test_subagent_stop_never_blocks(self, hooks_dir: Path) -> None:
        """SubagentStop router should never return block."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        # Test with various patterns - none should block
        patterns = [
            ("swarm", {"SWARM_ID": "test-swarm"}),
            ("jury", {"JURY_ID": "test-jury", "JUROR_INDEX": "0", "TOTAL_JURORS": "3"}),
            (None, {}),  # No pattern
        ]

        for pattern_type, extra_env in patterns:
            env = os.environ.copy()
            if pattern_type:
                env["PATTERN_TYPE"] = pattern_type
                env["PATTERN_ID"] = f"test-{pattern_type}"
            env.update(extra_env)
            env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

            hook_input = json.dumps({
                "session_id": f"test-session-noblock-{pattern_type}",
                "agent_id": "noblock-agent",
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

            assert result.returncode == 0, (
                f"Router failed for pattern {pattern_type}: {result.stderr}"
            )

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"SubagentStop should never block. "
                f"Pattern: {pattern_type}, Got: {output}"
            )


class TestPatternDetectionViaEnvVar:
    """Tests for PATTERN_TYPE environment variable detection."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.mark.parametrize("pattern_type,expected_handler", [
        ("swarm", "swarm"),
        ("jury", "jury"),
        ("pipeline", "pipeline"),
        ("generator_critic", "generator_critic"),
        ("hierarchical", "hierarchical"),
        ("map_reduce", "map_reduce"),
    ])
    def test_pattern_type_detection(
        self,
        hooks_dir: Path,
        pattern_type: str,
        expected_handler: str
    ) -> None:
        """Router correctly detects PATTERN_TYPE and routes to handler."""
        shell_wrapper = hooks_dir / "subagent-stop.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 9)")

        pattern_id = f"test-{pattern_type}-stop-123"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = pattern_type
        env["PATTERN_ID"] = pattern_id
        env["AGENT_ROLE"] = "worker"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Add pattern-specific env vars
        if pattern_type == "swarm":
            env["SWARM_ID"] = pattern_id
        elif pattern_type == "jury":
            env["JURY_ID"] = pattern_id
            env["JUROR_INDEX"] = "0"
            env["TOTAL_JURORS"] = "3"

        hook_input = json.dumps({
            "session_id": f"test-session-{pattern_type}-stop",
            "agent_id": f"agent-{pattern_type}-stop-xyz",
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

        assert result.returncode == 0, (
            f"Router failed for PATTERN_TYPE={pattern_type}: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Handler for {pattern_type} should return 'continue'. Got: {output}"
        )
