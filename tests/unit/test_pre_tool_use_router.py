"""Tests for PreToolUse router (Phase 6 of pattern-aware hooks plan).

The PreToolUse router:
1. Detects pattern via PATTERN_TYPE environment variable
2. Routes to pattern-specific handlers:
   - Swarm: injects broadcasts (existing pre-tool-use-broadcast.ts logic)
   - Jury: enforces vote isolation (blocks cross-juror data access)
   - Pipeline: injects upstream artifacts
3. Returns 'continue' when no pattern is detected
4. Handles missing handlers gracefully

Tests are designed to FAIL initially (TDD approach) until Phase 6 is implemented.

Expected file: .claude/hooks/src/pre-tool-use.ts
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestPreToolUseRouterFileStructure:
    """Tests for pre-tool-use router file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_router_typescript_exists(self, hooks_dir: Path) -> None:
        """Verify pre-tool-use.ts router exists."""
        router_ts = hooks_dir / "src" / "pre-tool-use.ts"

        assert router_ts.exists(), (
            f"Router TypeScript not found: {router_ts}. "
            "Phase 6 requires creating .claude/hooks/src/pre-tool-use.ts"
        )

    def test_router_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Verify pre-tool-use.sh shell wrapper exists."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        assert shell_wrapper.exists(), (
            f"Shell wrapper not found: {shell_wrapper}. "
            "Phase 7 requires creating .claude/hooks/pre-tool-use.sh"
        )

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Verify shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        assert os.access(shell_wrapper, os.X_OK), (
            f"Shell wrapper must be executable: {shell_wrapper}"
        )

    def test_shell_wrapper_calls_typescript(self, hooks_dir: Path) -> None:
        """Verify shell wrapper invokes TypeScript via npx tsx."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        content = shell_wrapper.read_text()

        # Should invoke the TS handler via npx tsx or compiled JS
        assert (
            "npx tsx" in content or
            "node dist/pre-tool-use.mjs" in content or
            "pre-tool-use.ts" in content
        ), (
            "Shell wrapper should invoke pre-tool-use.ts via npx tsx "
            "or compiled JavaScript"
        )


class TestPreToolUseRouterPatternDetection:
    """Tests for pattern detection and routing logic."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def base_hook_input(self) -> dict:
        """Base hook input for PreToolUse events."""
        return {
            "session_id": "test-session-123",
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"}
        }

    def _run_hook(
        self,
        hooks_dir: Path,
        hook_input: dict,
        env_vars: dict
    ) -> tuple[int, dict]:
        """Run the pre-tool-use hook and return (returncode, output)."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        env = os.environ.copy()
        env.update(env_vars)
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        if result.returncode != 0:
            return result.returncode, {}

        try:
            output = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            output = {"raw_stdout": result.stdout, "raw_stderr": result.stderr}

        return result.returncode, output

    def test_router_continues_when_no_pattern(
        self,
        hooks_dir: Path,
        base_hook_input: dict
    ) -> None:
        """When PATTERN_TYPE not set, router returns continue with no message."""
        env = {
            # No PATTERN_TYPE set
        }
        # Ensure PATTERN_TYPE is not inherited from environment
        env_clean = os.environ.copy()
        env_clean.pop("PATTERN_TYPE", None)
        env_clean.pop("SWARM_ID", None)
        env_clean.pop("JURY_ID", None)
        env_clean.pop("PIPELINE_ID", None)
        env_clean["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        shell_wrapper = hooks_dir / "pre-tool-use.sh"
        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(base_hook_input),
            capture_output=True,
            text=True,
            env=env_clean,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            "Router should return 'continue' when no pattern detected"
        )
        # Should NOT have a message when no pattern
        assert output.get("message") is None or output.get("message") == "", (
            "Router should not inject message when no pattern detected"
        )

    def test_router_detects_swarm_pattern(
        self,
        hooks_dir: Path,
        base_hook_input: dict
    ) -> None:
        """When PATTERN_TYPE=swarm, router should route to swarm handler."""
        returncode, output = self._run_hook(
            hooks_dir,
            base_hook_input,
            env_vars={
                "PATTERN_TYPE": "swarm",
                "PATTERN_ID": "test-swarm-001",
                "SWARM_ID": "test-swarm-001",  # Legacy compat
                "AGENT_ID": "agent-1",
                "AGENT_ROLE": "researcher"
            }
        )

        assert returncode == 0, f"Hook failed with return code {returncode}"
        assert output.get("result") == "continue", (
            "Swarm handler should return 'continue' (broadcasts injected via message)"
        )

    def test_router_detects_jury_pattern(
        self,
        hooks_dir: Path,
        base_hook_input: dict
    ) -> None:
        """When PATTERN_TYPE=jury, router should route to jury handler."""
        returncode, output = self._run_hook(
            hooks_dir,
            base_hook_input,
            env_vars={
                "PATTERN_TYPE": "jury",
                "PATTERN_ID": "test-jury-001",
                "JURY_ID": "test-jury-001",
                "AGENT_ROLE": "juror",
                "JUROR_INDEX": "0",
                "TOTAL_JURORS": "3"
            }
        )

        assert returncode == 0, f"Hook failed with return code {returncode}"
        # Jury handler enforces isolation - may continue or block depending on tool
        assert output.get("result") in ["continue", "block"], (
            "Jury handler should return 'continue' or 'block'"
        )

    def test_router_detects_pipeline_pattern(
        self,
        hooks_dir: Path,
        base_hook_input: dict
    ) -> None:
        """When PATTERN_TYPE=pipeline, router should route to pipeline handler."""
        returncode, output = self._run_hook(
            hooks_dir,
            base_hook_input,
            env_vars={
                "PATTERN_TYPE": "pipeline",
                "PATTERN_ID": "test-pipeline-001",
                "AGENT_ROLE": "stage",
                "PIPELINE_STAGE_INDEX": "1",
                "PIPELINE_TOTAL_STAGES": "3"
            }
        )

        assert returncode == 0, f"Hook failed with return code {returncode}"
        assert output.get("result") == "continue", (
            "Pipeline handler should return 'continue' (artifacts injected via message)"
        )


class TestSwarmHandlerBroadcastInjection:
    """Tests for swarm handler broadcast injection (routed via pre-tool-use.ts)."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_broadcasts(self) -> Path:
        """Create a temporary project with coordination database and broadcasts."""
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

            # Insert test broadcast
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "bc-001",
                    "router-test-swarm",
                    "other-agent",
                    "finding",
                    json.dumps({"finding": "Important discovery from router test"}),
                    now
                )
            )
            conn.commit()
            conn.close()

            yield Path(tmpdir)

    def test_swarm_handler_injects_broadcasts(
        self,
        hooks_dir: Path,
        project_with_broadcasts: Path
    ) -> None:
        """Router routes to swarm handler which injects broadcast context."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        hook_input = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.txt"}
        }

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "router-test-swarm"
        env["SWARM_ID"] = "router-test-swarm"
        env["AGENT_ID"] = "current-agent"
        env["AGENT_ROLE"] = "researcher"
        env["CLAUDE_PROJECT_DIR"] = str(project_with_broadcasts)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(hook_input),
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
        assert message, (
            "Swarm handler should inject broadcast message when broadcasts exist"
        )
        assert "other-agent" in message or "Important discovery" in message, (
            f"Message should contain broadcast info. Got: {message}"
        )


class TestJuryHandlerVoteIsolation:
    """Tests for jury handler vote isolation enforcement."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_jury_handler_allows_non_cross_juror_operations(
        self,
        hooks_dir: Path
    ) -> None:
        """Jury handler allows normal operations that don't violate isolation."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        # Normal file read - should be allowed
        hook_input = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/code.py"}
        }

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = "test-jury"
        env["JURY_ID"] = "test-jury"
        env["AGENT_ROLE"] = "juror"
        env["JUROR_INDEX"] = "0"
        env["TOTAL_JURORS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            "Jury handler should allow normal operations"
        )

    def test_jury_handler_blocks_cross_juror_access_in_strict_mode(
        self,
        hooks_dir: Path
    ) -> None:
        """Jury handler blocks cross-juror data access when JURY_ISOLATION=strict."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        # Attempt to read another juror's output file
        hook_input = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/jury-test-jury/juror-1-output.json"}
        }

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "jury"
        env["PATTERN_ID"] = "test-jury"
        env["JURY_ID"] = "test-jury"
        env["AGENT_ROLE"] = "juror"
        env["JUROR_INDEX"] = "0"  # This is juror 0
        env["TOTAL_JURORS"] = "3"
        env["JURY_ISOLATION"] = "strict"  # Enable strict isolation
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        # Should block cross-juror access
        assert output.get("result") == "block", (
            "Jury handler should block cross-juror data access in strict mode. "
            f"Got: {output}"
        )
        # Should explain why blocked
        assert "isolation" in output.get("reason", "").lower() or \
               "juror" in output.get("reason", "").lower(), (
            f"Block reason should mention isolation. Got: {output.get('reason')}"
        )


class TestPipelineHandlerArtifactInjection:
    """Tests for pipeline handler upstream artifact injection."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_with_pipeline_state(self) -> Path:
        """Create a temporary project with pipeline state database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude/cache/agentica-coordination directory
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))

            # Create pipeline artifacts table
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pipeline_artifacts (
                    id TEXT PRIMARY KEY,
                    pipeline_id TEXT NOT NULL,
                    stage_index INTEGER NOT NULL,
                    artifact_type TEXT NOT NULL,
                    artifact_path TEXT,
                    artifact_content TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pipeline_artifacts
                    ON pipeline_artifacts(pipeline_id, stage_index);
            """)

            # Insert upstream stage artifact
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            conn.execute(
                "INSERT INTO pipeline_artifacts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "art-001",
                    "test-pipeline",
                    0,  # Stage 0 (upstream)
                    "output",
                    None,
                    json.dumps({"result": "Stage 0 completed successfully"}),
                    now
                )
            )
            conn.commit()
            conn.close()

            yield Path(tmpdir)

    def test_pipeline_handler_injects_upstream_artifacts(
        self,
        hooks_dir: Path,
        project_with_pipeline_state: Path
    ) -> None:
        """Pipeline handler injects upstream stage artifacts."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        hook_input = {
            "session_id": "test-session",
            "tool_name": "Bash",
            "tool_input": {"command": "echo process"}
        }

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "pipeline"
        env["PATTERN_ID"] = "test-pipeline"
        env["AGENT_ROLE"] = "stage"
        env["PIPELINE_STAGE_INDEX"] = "1"  # Stage 1, so stage 0 is upstream
        env["PIPELINE_TOTAL_STAGES"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_with_pipeline_state)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue"

        # Should have injected upstream artifact context
        message = output.get("message", "")
        assert message, (
            "Pipeline handler should inject upstream artifact context"
        )
        assert "Stage 0" in message or "upstream" in message.lower(), (
            f"Message should reference upstream stage. Got: {message}"
        )


class TestRouterHandlerGracefulDegradation:
    """Tests for router handling missing handlers gracefully."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_router_continues_for_unknown_pattern(
        self,
        hooks_dir: Path
    ) -> None:
        """Router returns continue for unknown PATTERN_TYPE values."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        hook_input = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.txt"}
        }

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "nonexistent_pattern"
        env["PATTERN_ID"] = "test-123"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Should not crash, should continue
        assert result.returncode == 0, (
            f"Router should not crash on unknown pattern. Stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            "Router should return 'continue' for unknown patterns"
        )

    def test_router_continues_on_handler_error(
        self,
        hooks_dir: Path
    ) -> None:
        """Router returns continue if pattern handler throws an error."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        # Use swarm pattern with invalid SWARM_ID format to potentially trigger errors
        hook_input = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.txt"}
        }

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        # Invalid SWARM_ID with special characters - should be handled gracefully
        env["SWARM_ID"] = "'; DROP TABLE broadcasts; --"
        env["PATTERN_ID"] = "test-123"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Should handle gracefully, not crash
        assert result.returncode == 0, (
            f"Router should handle errors gracefully. Stderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            "Router should return 'continue' when handler fails gracefully"
        )

    def test_router_handles_malformed_input(
        self,
        hooks_dir: Path
    ) -> None:
        """Router handles malformed JSON input gracefully."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input="{ invalid json",  # Malformed JSON
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Should either:
        # 1. Return continue (graceful degradation), or
        # 2. Exit with error but not crash the hook system
        # The key is it should be predictable behavior
        if result.returncode == 0:
            try:
                output = json.loads(result.stdout.strip())
                assert output.get("result") == "continue", (
                    "On malformed input, should return continue"
                )
            except json.JSONDecodeError:
                # If output is not JSON, that's also acceptable as error handling
                pass
        # Non-zero returncode is also acceptable - just not hanging/crashing


class TestRouterEnvironmentVariableContract:
    """Tests verifying the router respects the environment variable contract."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_router_reads_pattern_type_from_env(
        self,
        hooks_dir: Path
    ) -> None:
        """Router correctly reads PATTERN_TYPE environment variable."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        # Test each valid pattern type
        for pattern_type in ["swarm", "jury", "pipeline", "generator_critic",
                             "hierarchical", "map_reduce", "blackboard",
                             "circuit_breaker", "chain_of_responsibility",
                             "adversarial", "event_driven"]:

            hook_input = {
                "session_id": "test-session",
                "tool_name": "Read",
                "tool_input": {}
            }

            env = os.environ.copy()
            env["PATTERN_TYPE"] = pattern_type
            env["PATTERN_ID"] = f"test-{pattern_type}-001"
            env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

            result = subprocess.run(
                [str(shell_wrapper)],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir),
                timeout=30
            )

            # Should not crash for any valid pattern type
            assert result.returncode == 0, (
                f"Router should handle PATTERN_TYPE={pattern_type}. "
                f"Stderr: {result.stderr}"
            )

    def test_router_uses_pattern_id_for_context(
        self,
        hooks_dir: Path
    ) -> None:
        """Router uses PATTERN_ID for pattern-specific context lookup."""
        shell_wrapper = hooks_dir / "pre-tool-use.sh"

        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet (Phase 7)")

        hook_input = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {}
        }

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["PATTERN_ID"] = "unique-pattern-id-12345"
        env["SWARM_ID"] = "unique-pattern-id-12345"  # Legacy compat
        env["AGENT_ID"] = "agent-001"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            [str(shell_wrapper)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # The output should be based on PATTERN_ID context
        output = json.loads(result.stdout.strip())
        assert output.get("result") in ["continue", "block"], (
            "Router should process request using PATTERN_ID context"
        )
