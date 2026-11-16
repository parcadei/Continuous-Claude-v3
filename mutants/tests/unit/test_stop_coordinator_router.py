"""Tests for Stop coordinator router (Phases 10-11 of pattern-aware hooks).

These tests verify that the stop-coordinator.ts router correctly:
1. Reads stdin JSON input
2. Detects pattern via PATTERN_TYPE env var
3. Dispatches to appropriate pattern handler
4. For swarm: blocks until all agents done
5. For jury: tallies votes and returns verdict
6. For pipeline: synthesizes pipeline output
7. Handles unknown patterns gracefully
8. Handles missing DB and errors gracefully

Plan reference: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 10-11)

Tests are designed to FAIL initially (TDD approach) until Phases 10-11 are implemented.

Router location: .claude/hooks/src/stop-coordinator.ts
Shell wrapper: .claude/hooks/stop-coordinator.sh
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
        ts_router = hooks_dir / "src" / "stop-coordinator.ts"

        assert ts_router.exists(), (
            f"TypeScript router not found: {ts_router}. "
            "Create .claude/hooks/src/stop-coordinator.ts as part of Phase 10."
        )

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper exists at expected path (Phase 11)."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}. "
            "Create .claude/hooks/stop-coordinator.sh as part of Phase 11."
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}. "
            "Run: chmod +x .claude/hooks/stop-coordinator.sh"
        )


class TestSwarmCoordinatorBlocking:
    """Tests for swarm coordinator blocking until all agents done."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_partial_swarm(self) -> tuple[Path, str]:
        """Create project with swarm where not all agents are done."""
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

            swarm_id = "test-swarm-partial-coord"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # 3 agents started
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            # Only agent-1 done
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("done1", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "agent-1 completed"}), now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_blocks_when_agents_pending(
        self,
        hooks_dir: Path,
        project_with_partial_swarm: tuple[Path, str]
    ) -> None:
        """Coordinator blocks when not all agents have broadcast done."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        project_dir, swarm_id = project_with_partial_swarm

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = swarm_id
        env["SWARM_ID"] = swarm_id
        env["AGENT_ROLE"] = "coordinator"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-coord-block",
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

        # Should block because not all agents are done
        assert output.get("result") == "block", (
            f"Coordinator should block when agents pending. Got: {output}"
        )

        # Message should indicate waiting
        message = output.get("message", "")
        assert "waiting" in message.lower() or "agent" in message.lower() or "pending" in message.lower(), (
            f"Block message should indicate waiting. Got: {message}"
        )

    @pytest.fixture
    def project_with_complete_swarm(self) -> tuple[Path, str]:
        """Create project with swarm where all agents are done."""
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

            swarm_id = "test-swarm-complete-coord"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # All 3 agents done
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"done{i}", swarm_id, agent, "done",
                     json.dumps({"summary": f"{agent} completed"}), now)
                )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_continues_when_all_done(
        self,
        hooks_dir: Path,
        project_with_complete_swarm: tuple[Path, str]
    ) -> None:
        """Coordinator continues when all agents have broadcast done."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        project_dir, swarm_id = project_with_complete_swarm

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = swarm_id
        env["SWARM_ID"] = swarm_id
        env["AGENT_ROLE"] = "coordinator"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-coord-continue",
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

        # Should continue because all agents are done
        assert output.get("result") == "continue", (
            f"Coordinator should continue when all done. Got: {output}"
        )


class TestJuryVoteTallying:
    """Tests for jury vote tallying."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_jury_votes(self) -> tuple[Path, str, dict]:
        """Create project with jury votes."""
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
                    ON jury_votes(jury_id);
            """)

            jury_id = "test-jury-tally"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # 3 jurors voted: 2 approve, 1 reject
            votes = [
                ("juror-0", "approve", "Code looks good"),
                ("juror-1", "approve", "Tests pass"),
                ("juror-2", "reject", "Need more tests"),
            ]

            for juror_id, vote, reasoning in votes:
                conn.execute(
                    "INSERT INTO jury_votes VALUES (?, ?, ?, ?, ?, ?)",
                    (f"vote-{juror_id}", jury_id, juror_id, vote, reasoning, now)
                )

            conn.commit()
            conn.close()

            expected_verdict = {
                "approve": 2,
                "reject": 1,
                "result": "approve",  # Majority
            }

            yield Path(tmpdir), jury_id, expected_verdict

    def test_tallies_jury_votes(
        self,
        hooks_dir: Path,
        project_with_jury_votes: tuple[Path, str, dict]
    ) -> None:
        """Coordinator tallies jury votes and returns verdict."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        project_dir, jury_id, expected_verdict = project_with_jury_votes

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = jury_id
        env["JURY_ID"] = jury_id
        env["AGENT_ROLE"] = "coordinator"
        env["TOTAL_JURORS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-jury-tally",
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

        # Should continue with verdict
        assert output.get("result") == "continue", (
            f"Jury coordinator should continue with verdict. Got: {output}"
        )

        # Message should contain verdict summary
        message = output.get("message", "")
        assert message, "Jury coordinator should return verdict message"

        message_lower = message.lower()
        assert any(keyword in message_lower for keyword in ["verdict", "vote", "approve", "reject"]), (
            f"Verdict message should contain voting info. Got: {message}"
        )

    @pytest.fixture
    def project_with_incomplete_jury(self) -> tuple[Path, str]:
        """Create project with incomplete jury votes."""
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
            """)

            jury_id = "test-jury-incomplete"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # Only 1 of 3 jurors voted
            conn.execute(
                "INSERT INTO jury_votes VALUES (?, ?, ?, ?, ?, ?)",
                ("vote-juror-0", jury_id, "juror-0", "approve", "LGTM", now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), jury_id

    def test_blocks_when_votes_incomplete(
        self,
        hooks_dir: Path,
        project_with_incomplete_jury: tuple[Path, str]
    ) -> None:
        """Coordinator blocks when not all jurors have voted."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        project_dir, jury_id = project_with_incomplete_jury

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = jury_id
        env["JURY_ID"] = jury_id
        env["AGENT_ROLE"] = "coordinator"
        env["TOTAL_JURORS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-jury-incomplete",
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

        # Should block waiting for more votes
        assert output.get("result") == "block", (
            f"Jury coordinator should block when votes incomplete. Got: {output}"
        )

        message = output.get("message", "")
        assert "wait" in message.lower() or "vote" in message.lower() or "juror" in message.lower(), (
            f"Block message should indicate waiting for votes. Got: {message}"
        )


class TestPipelineOutputSynthesis:
    """Tests for pipeline output synthesis."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_pipeline_stages(self) -> tuple[Path, str]:
        """Create project with completed pipeline stages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pipeline_stages (
                    id TEXT PRIMARY KEY,
                    pipeline_id TEXT NOT NULL,
                    stage_index INTEGER NOT NULL,
                    stage_name TEXT,
                    status TEXT NOT NULL,
                    output TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_pipeline_stages
                    ON pipeline_stages(pipeline_id, stage_index);
            """)

            pipeline_id = "test-pipeline-synth"
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

            # 3-stage pipeline, all complete
            stages = [
                (0, "analyze", "completed", {"findings": ["bug1", "bug2"]}),
                (1, "fix", "completed", {"fixes": ["fix1", "fix2"]}),
                (2, "verify", "completed", {"passed": True}),
            ]

            for stage_index, stage_name, status, output in stages:
                conn.execute(
                    "INSERT INTO pipeline_stages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"stage-{stage_index}", pipeline_id, stage_index, stage_name,
                     status, json.dumps(output), now, now)
                )

            conn.commit()
            conn.close()

            yield Path(tmpdir), pipeline_id

    def test_synthesizes_pipeline_output(
        self,
        hooks_dir: Path,
        project_with_pipeline_stages: tuple[Path, str]
    ) -> None:
        """Coordinator synthesizes pipeline output."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        project_dir, pipeline_id = project_with_pipeline_stages

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "pipeline"
        env["PATTERN_ID"] = pipeline_id
        env["AGENT_ROLE"] = "coordinator"
        env["PIPELINE_TOTAL_STAGES"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": "test-session-pipeline-synth",
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

        # Should continue with synthesis
        assert output.get("result") == "continue", (
            f"Pipeline coordinator should continue with synthesis. Got: {output}"
        )

        # Message should contain pipeline summary
        message = output.get("message", "")
        assert message, "Pipeline coordinator should return synthesis message"

        message_lower = message.lower()
        assert any(keyword in message_lower for keyword in ["pipeline", "stage", "complete", "output"]), (
            f"Synthesis message should mention pipeline info. Got: {message}"
        )


class TestUnknownPatternHandling:
    """Tests for handling unknown patterns."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_unknown_pattern_continues(self, hooks_dir: Path) -> None:
        """Unknown pattern type returns continue."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "unknown_pattern_xyz"
        env["PATTERN_ID"] = "test-unknown"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-unknown",
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

        # Should continue for unknown patterns
        assert output.get("result") == "continue", (
            f"Unknown pattern should continue. Got: {output}"
        )

    def test_no_pattern_continues(self, hooks_dir: Path) -> None:
        """No pattern type returns continue."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        env = os.environ.copy()
        env.pop("PATTERN_TYPE", None)
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-no-pattern",
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

        # Should continue when no pattern
        assert output.get("result") == "continue", (
            f"No pattern should continue. Got: {output}"
        )


class TestStopHookActiveLoop:
    """Tests for stop_hook_active infinite loop prevention."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_pending_swarm(self) -> tuple[Path, str]:
        """Create project with swarm that would normally block."""
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

            # 3 agents started, only 1 done (would normally block)
            for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
                conn.execute(
                    "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                    (f"start{i}", swarm_id, agent, "started",
                     json.dumps({"task": f"Task for {agent}"}), now)
                )

            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                ("done1", swarm_id, "agent-1", "done",
                 json.dumps({"summary": "agent-1 completed"}), now)
            )

            conn.commit()
            conn.close()

            yield Path(tmpdir), swarm_id

    def test_stop_hook_active_prevents_loop(
        self,
        hooks_dir: Path,
        project_with_pending_swarm: tuple[Path, str]
    ) -> None:
        """When stop_hook_active=true, coordinator returns continue immediately."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        project_dir, swarm_id = project_with_pending_swarm

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = swarm_id
        env["SWARM_ID"] = swarm_id
        env["AGENT_ROLE"] = "coordinator"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        # Key flag to prevent infinite loop
        hook_input = json.dumps({
            "session_id": "test-session-loop",
            "stop_hook_active": True,
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

        # Should continue immediately to prevent infinite loop
        assert output.get("result") == "continue", (
            f"Coordinator must continue when stop_hook_active=true to prevent loops. Got: {output}"
        )


class TestMissingDbHandling:
    """Tests for graceful handling when DB is missing."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_missing_db_continues(self, hooks_dir: Path) -> None:
        """When DB doesn't exist, coordinator returns continue gracefully."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        with tempfile.TemporaryDirectory() as tmpdir:
            # No database created
            env = os.environ.copy()
            env["PATTERN_TYPE"] = "swarm"
            env["PATTERN_ID"] = "test-swarm-no-db"
            env["SWARM_ID"] = "test-swarm-no-db"
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

            assert result.returncode == 0, f"Router failed: {result.stderr}"

            output = json.loads(result.stdout.strip())

            # Should continue gracefully
            assert output.get("result") == "continue", (
                f"Coordinator should continue when DB missing. Got: {output}"
            )

    def test_corrupted_db_continues(self, hooks_dir: Path) -> None:
        """When DB is corrupted, coordinator returns continue gracefully."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            # Create corrupted database
            db_path = db_dir / "coordination.db"
            db_path.write_text("This is not a valid SQLite database!")

            env = os.environ.copy()
            env["PATTERN_TYPE"] = "swarm"
            env["PATTERN_ID"] = "test-swarm-corrupt"
            env["SWARM_ID"] = "test-swarm-corrupt"
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            hook_input = json.dumps({
                "session_id": "test-session-corrupt",
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

            # Should not crash
            assert result.returncode == 0, (
                f"Router should not crash on corrupted DB. "
                f"Exit code: {result.returncode}, stderr: {result.stderr}"
            )

            output = json.loads(result.stdout.strip())

            # Should continue gracefully
            assert output.get("result") == "continue", (
                f"Coordinator should continue on error. Got: {output}"
            )


class TestInvalidInputHandling:
    """Tests for graceful handling of invalid input."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_invalid_json_graceful(self, hooks_dir: Path) -> None:
        """Router handles invalid JSON input gracefully."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm"
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Invalid JSON
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

        # Should handle gracefully
        assert result.returncode == 0, (
            f"Router should not crash on invalid JSON. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

        if result.stdout.strip():
            output = json.loads(result.stdout.strip())
            assert output.get("result") in ["continue", "block"], (
                f"Output should have valid result. Got: {output}"
            )

    def test_empty_input_graceful(self, hooks_dir: Path) -> None:
        """Router handles empty input gracefully."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = "test-jury"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input="",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Should not hang (timeout would catch this)
        assert result.returncode == 0, (
            f"Router should not crash on empty input. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )


class TestRouterOutputFormat:
    """Tests for correct output format from router."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_output_is_valid_json(self, hooks_dir: Path) -> None:
        """Router output is always valid JSON."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "test-swarm"
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-output",
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
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "pipeline"
        env["PATTERN_ID"] = "test-pipeline"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        hook_input = json.dumps({
            "session_id": "test-session-result",
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


class TestPatternTypeDetection:
    """Tests for PATTERN_TYPE environment variable detection."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.mark.parametrize("pattern_type", [
        "swarm",
        "jury",
        "pipeline",
        "generator_critic",
        "hierarchical",
        "map_reduce",
    ])
    def test_pattern_type_detection(self, hooks_dir: Path, pattern_type: str) -> None:
        """Router correctly detects PATTERN_TYPE."""
        shell_wrapper = hooks_dir / "stop-coordinator.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 11)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = pattern_type
        env["PATTERN_ID"] = f"test-{pattern_type}-coord-123"
        env["AGENT_ROLE"] = "coordinator"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        # Add pattern-specific env vars
        if pattern_type == "swarm":
            env["SWARM_ID"] = env["PATTERN_ID"]
        elif pattern_type == "jury":
            env["JURY_ID"] = env["PATTERN_ID"]
            env["TOTAL_JURORS"] = "3"
        elif pattern_type == "pipeline":
            env["PIPELINE_TOTAL_STAGES"] = "3"

        hook_input = json.dumps({
            "session_id": f"test-session-{pattern_type}-coord",
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
        assert output.get("result") in ["continue", "block"], (
            f"Handler for {pattern_type} should return valid result. Got: {output}"
        )
