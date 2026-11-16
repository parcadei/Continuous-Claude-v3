"""
Tests for Circuit Breaker pattern hook handlers.

Tests the TypeScript handlers via command-line execution:
- onSubagentStart: Inject primary/fallback role context
- onSubagentStop: Track success/failure for circuit state
- onPostToolUse: Detect failures from tool responses
- onStop: Circuit state summary
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


def run_hook(handler_name: str, input_data: dict, env: dict | None = None) -> dict:
    """Run TypeScript hook handler and return parsed output."""
    project_dir = Path(__file__).parent.parent.parent
    hook_path = project_dir / ".claude/hooks/src/patterns/circuit-breaker.ts"

    # Build environment
    test_env = os.environ.copy()
    test_env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    if env:
        test_env.update(env)

    # Execute TypeScript via npx tsx
    cmd = ["npx", "tsx", "-e", f"import {{ {handler_name} }} from '{hook_path}'; {handler_name}({json.dumps(input_data)}).then(r => console.log(JSON.stringify(r)))"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=test_env,
        cwd=str(project_dir / ".claude/hooks")
    )

    if result.returncode != 0:
        raise RuntimeError(f"Hook execution failed: {result.stderr}")

    return json.loads(result.stdout.strip())


class TestOnSubagentStart:
    """Test onSubagentStart handler for circuit breaker pattern."""

    def test_no_cb_id_continues(self):
        """Handler continues when PATTERN_TYPE is not circuit_breaker."""
        input_data = {"session_id": "test-session"}
        output = run_hook("onSubagentStart", input_data, env={})

        assert output["result"] == "continue"
        assert "message" not in output or output["message"] is None or output["message"] == ""

    def test_primary_role_injection(self):
        """Handler injects primary agent context."""
        input_data = {"session_id": "test-session"}
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "primary",
            "CIRCUIT_STATE": "closed"
        }
        output = run_hook("onSubagentStart", input_data, env=env)

        assert output["result"] == "continue"
        assert "PRIMARY" in output["message"]
        assert "closed" in output["message"].lower()

    def test_fallback_role_injection(self):
        """Handler injects fallback agent context."""
        input_data = {"session_id": "test-session"}
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "fallback",
            "CIRCUIT_STATE": "open"
        }
        output = run_hook("onSubagentStart", input_data, env=env)

        assert output["result"] == "continue"
        assert "FALLBACK" in output["message"]
        assert "degraded mode" in output["message"].lower() or "backup" in output["message"].lower()

    def test_half_open_state_warning(self):
        """Handler warns when circuit is in half-open state."""
        input_data = {"session_id": "test-session"}
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "primary",
            "CIRCUIT_STATE": "half_open"
        }
        output = run_hook("onSubagentStart", input_data, env=env)

        assert output["result"] == "continue"
        assert "half_open" in output["message"].lower() or "testing" in output["message"].lower()


class TestOnSubagentStop:
    """Test onSubagentStop handler for circuit breaker pattern."""

    def test_no_cb_id_continues(self):
        """Handler continues when CB_ID not set."""
        input_data = {"session_id": "test-session", "agent_id": "agent-456"}
        output = run_hook("onSubagentStop", input_data, env={})

        assert output["result"] == "continue"

    def test_primary_success_recorded(self):
        """Handler records successful primary execution."""
        input_data = {
            "session_id": "test-session",
            "agent_id": "agent-456",
            "stop_reason": "success"
        }
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "primary"
        }
        output = run_hook("onSubagentStop", input_data, env=env)

        assert output["result"] == "continue"
        # Success should be recorded in DB (verified by integration tests)

    def test_primary_failure_recorded(self):
        """Handler records failed primary execution."""
        input_data = {
            "session_id": "test-session",
            "agent_id": "agent-456",
            "stop_reason": "error"
        }
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "primary"
        }
        output = run_hook("onSubagentStop", input_data, env=env)

        assert output["result"] == "continue"
        # Failure should be recorded in DB

    def test_fallback_execution_tracked(self):
        """Handler tracks fallback agent execution."""
        input_data = {
            "session_id": "test-session",
            "agent_id": "agent-789",
            "stop_reason": "success"
        }
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "fallback"
        }
        output = run_hook("onSubagentStop", input_data, env=env)

        assert output["result"] == "continue"


class TestOnPostToolUse:
    """Test onPostToolUse handler for circuit breaker pattern."""

    def test_no_cb_id_continues(self):
        """Handler continues when CB_ID not set."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Bash",
            "tool_response": {"output": "ok"}
        }
        output = run_hook("onPostToolUse", input_data, env={})

        assert output["result"] == "continue"

    def test_bash_error_detected(self):
        """Handler detects Bash command failures."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Bash",
            "tool_response": {
                "output": "error: command not found",
                "exit_code": 127
            }
        }
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "primary"
        }
        output = run_hook("onPostToolUse", input_data, env=env)

        assert output["result"] == "continue"
        # Failure should be recorded for circuit breaker

    def test_read_missing_file_detected(self):
        """Handler detects Read tool failures (missing files)."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_response": {
                "error": "File not found: /nonexistent.txt"
            }
        }
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "primary"
        }
        output = run_hook("onPostToolUse", input_data, env=env)

        assert output["result"] == "continue"
        # Failure should be recorded

    def test_successful_tool_use_ignored(self):
        """Handler ignores successful tool executions."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Bash",
            "tool_response": {
                "output": "Success",
                "exit_code": 0
            }
        }
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "AGENT_ROLE": "primary"
        }
        output = run_hook("onPostToolUse", input_data, env=env)

        assert output["result"] == "continue"
        assert "message" not in output or not output["message"]


class TestOnStop:
    """Test onStop handler for circuit breaker pattern."""

    def test_no_cb_id_continues(self):
        """Handler continues when CB_ID not set."""
        input_data = {"session_id": "test-session"}
        output = run_hook("onStop", input_data, env={})

        assert output["result"] == "continue"

    def test_closed_circuit_summary(self):
        """Handler provides summary for closed circuit (all healthy)."""
        input_data = {"session_id": "test-session"}
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "CIRCUIT_STATE": "closed"
        }
        output = run_hook("onStop", input_data, env=env)

        assert output["result"] == "continue"
        # Should include circuit state summary

    def test_open_circuit_summary(self):
        """Handler provides summary for open circuit (primary failed)."""
        input_data = {"session_id": "test-session"}
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123",
            "CIRCUIT_STATE": "open"
        }
        output = run_hook("onStop", input_data, env=env)

        assert output["result"] == "continue"
        assert "message" in output
        # Should warn about circuit being open

    def test_prevents_infinite_loop(self):
        """Handler prevents infinite loops by checking stop_hook_active."""
        input_data = {
            "session_id": "test-session",
            "stop_hook_active": True
        }
        env = {
            "PATTERN_TYPE": "circuit_breaker",
            "CB_ID": "cb-123"
        }
        output = run_hook("onStop", input_data, env=env)

        assert output["result"] == "continue"
        assert "message" not in output or not output["message"]


# =============================================================================
# TDD Tests for onPostToolUse - Red Phase
# =============================================================================


class TestOnPostToolUseExports:
    """Test that onPostToolUse is properly exported from the module."""

    def test_exports_on_post_tool_use(self):
        """Module exports onPostToolUse function."""
        project_dir = Path(__file__).parent.parent.parent
        module_path = project_dir / ".claude/hooks/src/patterns/circuit-breaker.ts"

        assert module_path.exists(), (
            f"Circuit breaker module not found: {module_path}"
        )

        content = module_path.read_text()

        # Check for export
        assert "export" in content and "onPostToolUse" in content, (
            "Module must export onPostToolUse function. "
            "Expected: export async function onPostToolUse or export { onPostToolUse }"
        )


class TestOnPostToolUseRecordsSuccess:
    """Test that onPostToolUse records success and resets failure count."""

    def test_records_success_when_tool_succeeds(self):
        """Handler should record success and reset failure count on successful tool."""
        project_dir = Path(__file__).parent.parent.parent

        # Create temp directory with DB that has existing failures
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS circuit_state (
                    id TEXT PRIMARY KEY,
                    cb_id TEXT NOT NULL,
                    state TEXT DEFAULT 'closed',
                    failure_count INTEGER DEFAULT 0,
                    last_failure_at TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # Pre-populate with 2 failures (one more would open circuit)
            cb_id = "cb-success-test"
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO circuit_state (id, cb_id, state, failure_count, created_at) VALUES (?, ?, ?, ?, ?)",
                (cb_id, cb_id, "closed", 2, now)
            )
            conn.commit()
            conn.close()

            # Run handler with successful tool response
            input_data = {
                "session_id": "test-session",
                "tool_name": "Bash",
                "tool_response": {
                    "output": "Success",
                    "exit_code": 0
                }
            }
            env = {
                "CB_ID": cb_id,
                "AGENT_ROLE": "primary",
                "CLAUDE_PROJECT_DIR": tmpdir
            }

            output = run_hook("onPostToolUse", input_data, env=env)

            assert output["result"] == "continue"

            # Verify failure count was reset to 0
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT failure_count, state FROM circuit_state WHERE cb_id = ?",
                (cb_id,)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Circuit state should exist"
            failure_count, state = row

            # TDD EXPECTATION: Success should reset failure count
            assert failure_count == 0, (
                f"Success should reset failure_count to 0. Got: {failure_count}"
            )
            assert state == "closed", (
                f"Circuit should remain closed after success. Got: {state}"
            )


class TestOnPostToolUseRecordsFailure:
    """Test that onPostToolUse properly records failures in database."""

    def test_records_failure_when_tool_fails(self):
        """Handler should increment failure count when tool fails."""
        project_dir = Path(__file__).parent.parent.parent

        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS circuit_state (
                    id TEXT PRIMARY KEY,
                    cb_id TEXT NOT NULL,
                    state TEXT DEFAULT 'closed',
                    failure_count INTEGER DEFAULT 0,
                    last_failure_at TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # Start with 0 failures
            cb_id = "cb-failure-test"
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO circuit_state (id, cb_id, state, failure_count, created_at) VALUES (?, ?, ?, ?, ?)",
                (cb_id, cb_id, "closed", 0, now)
            )
            conn.commit()
            conn.close()

            # Run handler with failed tool response
            input_data = {
                "session_id": "test-session",
                "tool_name": "Bash",
                "tool_response": {
                    "output": "Error: command failed",
                    "exit_code": 1
                }
            }
            env = {
                "CB_ID": cb_id,
                "AGENT_ROLE": "primary",
                "CLAUDE_PROJECT_DIR": tmpdir
            }

            output = run_hook("onPostToolUse", input_data, env=env)

            assert output["result"] == "continue"

            # Verify failure count was incremented
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT failure_count, state, last_failure_at FROM circuit_state WHERE cb_id = ?",
                (cb_id,)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Circuit state should exist"
            failure_count, state, last_failure_at = row

            assert failure_count == 1, (
                f"Failure should increment failure_count to 1. Got: {failure_count}"
            )
            assert state == "closed", (
                f"Circuit should remain closed after 1 failure. Got: {state}"
            )
            assert last_failure_at is not None, (
                "last_failure_at should be set after failure"
            )


class TestOnPostToolUseOpensCircuit:
    """Test that circuit opens after failure threshold."""

    def test_opens_circuit_after_threshold(self):
        """Handler should open circuit after 3 consecutive failures."""
        project_dir = Path(__file__).parent.parent.parent

        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS circuit_state (
                    id TEXT PRIMARY KEY,
                    cb_id TEXT NOT NULL,
                    state TEXT DEFAULT 'closed',
                    failure_count INTEGER DEFAULT 0,
                    last_failure_at TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # Start with 2 failures (threshold is 3)
            cb_id = "cb-threshold-test"
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO circuit_state (id, cb_id, state, failure_count, created_at) VALUES (?, ?, ?, ?, ?)",
                (cb_id, cb_id, "closed", 2, now)
            )
            conn.commit()
            conn.close()

            # Run handler with 3rd failure
            input_data = {
                "session_id": "test-session",
                "tool_name": "Bash",
                "tool_response": {
                    "output": "Error: command failed",
                    "exit_code": 1
                }
            }
            env = {
                "CB_ID": cb_id,
                "AGENT_ROLE": "primary",
                "CLAUDE_PROJECT_DIR": tmpdir
            }

            output = run_hook("onPostToolUse", input_data, env=env)

            assert output["result"] == "continue"

            # Verify circuit is now OPEN
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT failure_count, state FROM circuit_state WHERE cb_id = ?",
                (cb_id,)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Circuit state should exist"
            failure_count, state = row

            assert failure_count == 3, (
                f"failure_count should be 3. Got: {failure_count}"
            )
            assert state == "open", (
                f"Circuit should be OPEN after 3 failures. Got: {state}"
            )

    def test_reopens_circuit_on_half_open_failure(self):
        """Handler should reopen circuit if failure occurs in half_open state."""
        project_dir = Path(__file__).parent.parent.parent

        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS circuit_state (
                    id TEXT PRIMARY KEY,
                    cb_id TEXT NOT NULL,
                    state TEXT DEFAULT 'closed',
                    failure_count INTEGER DEFAULT 0,
                    last_failure_at TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # Start in half_open state (testing recovery)
            cb_id = "cb-halfopen-test"
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO circuit_state (id, cb_id, state, failure_count, created_at) VALUES (?, ?, ?, ?, ?)",
                (cb_id, cb_id, "half_open", 1, now)
            )
            conn.commit()
            conn.close()

            # Run handler with failure during half_open
            input_data = {
                "session_id": "test-session",
                "tool_name": "Bash",
                "tool_response": {
                    "output": "Error: still failing",
                    "exit_code": 1
                }
            }
            env = {
                "CB_ID": cb_id,
                "AGENT_ROLE": "primary",
                "CIRCUIT_STATE": "half_open",
                "CLAUDE_PROJECT_DIR": tmpdir
            }

            output = run_hook("onPostToolUse", input_data, env=env)

            assert output["result"] == "continue"

            # Verify circuit reopened
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT state FROM circuit_state WHERE cb_id = ?",
                (cb_id,)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Circuit state should exist"
            state = row[0]

            assert state == "open", (
                f"Circuit should reopen after failure in half_open state. Got: {state}"
            )


class TestOnPostToolUseInputValidation:
    """Test security validation of input formats."""

    def test_validates_input_format(self):
        """Handler should validate CB_ID format to prevent injection."""
        # Try malicious CB_ID with shell metacharacters
        malicious_ids = [
            "cb; rm -rf /",
            "cb`whoami`",
            "cb$(cat /etc/passwd)",
            "../../../etc/passwd",
            "cb\n--malicious",
        ]

        for malicious_id in malicious_ids:
            input_data = {
                "session_id": "test-session",
                "tool_name": "Bash",
                "tool_response": {
                    "output": "Error",
                    "exit_code": 1
                }
            }
            env = {
                "CB_ID": malicious_id,
                "AGENT_ROLE": "primary"
            }

            # Should not crash, should continue (rejecting invalid ID)
            output = run_hook("onPostToolUse", input_data, env=env)

            assert output["result"] == "continue", (
                f"Should continue (reject) with malicious CB_ID '{malicious_id}'. Got: {output}"
            )

    def test_validates_tool_name_in_response(self):
        """Handler should handle missing or malformed tool_name gracefully."""
        input_data = {
            "session_id": "test-session",
            # tool_name is missing
            "tool_response": {
                "output": "Error",
                "exit_code": 1
            }
        }
        env = {
            "CB_ID": "cb-valid",
            "AGENT_ROLE": "primary"
        }

        # Should not crash
        output = run_hook("onPostToolUse", input_data, env=env)

        assert output["result"] == "continue", (
            f"Should continue when tool_name is missing. Got: {output}"
        )

    def test_validates_tool_response_format(self):
        """Handler should handle missing or malformed tool_response gracefully."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Bash"
            # tool_response is missing
        }
        env = {
            "CB_ID": "cb-valid",
            "AGENT_ROLE": "primary"
        }

        # Should not crash
        output = run_hook("onPostToolUse", input_data, env=env)

        assert output["result"] == "continue", (
            f"Should continue when tool_response is missing. Got: {output}"
        )


class TestOnPostToolUseFallbackRole:
    """Test that fallback agents don't affect circuit state."""

    def test_ignores_fallback_agent_failures(self):
        """Handler should not record failures for fallback agents."""
        project_dir = Path(__file__).parent.parent.parent

        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS circuit_state (
                    id TEXT PRIMARY KEY,
                    cb_id TEXT NOT NULL,
                    state TEXT DEFAULT 'closed',
                    failure_count INTEGER DEFAULT 0,
                    last_failure_at TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # Start with 0 failures
            cb_id = "cb-fallback-test"
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO circuit_state (id, cb_id, state, failure_count, created_at) VALUES (?, ?, ?, ?, ?)",
                (cb_id, cb_id, "open", 3, now)  # Circuit is already open
            )
            conn.commit()
            conn.close()

            # Run handler as FALLBACK with failure
            input_data = {
                "session_id": "test-session",
                "tool_name": "Bash",
                "tool_response": {
                    "output": "Error: fallback also failed",
                    "exit_code": 1
                }
            }
            env = {
                "CB_ID": cb_id,
                "AGENT_ROLE": "fallback",  # This is the key difference
                "CLAUDE_PROJECT_DIR": tmpdir
            }

            output = run_hook("onPostToolUse", input_data, env=env)

            assert output["result"] == "continue"

            # Verify failure count was NOT incremented
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT failure_count FROM circuit_state WHERE cb_id = ?",
                (cb_id,)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Circuit state should exist"
            failure_count = row[0]

            assert failure_count == 3, (
                f"Fallback failures should not affect circuit. Expected 3, got: {failure_count}"
            )
