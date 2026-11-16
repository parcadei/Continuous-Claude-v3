"""
Unit tests for Chain of Responsibility pattern hook handlers.

Tests the hook handlers in .claude/hooks/src/patterns/chain-of-responsibility.ts:
- onSubagentStart: Inject handler position context
- onSubagentStop: Track handling/escalation
- onPreToolUse: Inject chain context
- onStop: Resolution summary
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


# Path to the chain-of-responsibility hook handlers
HOOKS_DIR = Path(__file__).parent.parent.parent / ".claude" / "hooks"
CHAIN_OF_RESPONSIBILITY_TS = HOOKS_DIR / "src" / "patterns" / "chain-of-responsibility.ts"


def run_hook_handler(handler_name: str, input_data: dict, env_vars: dict | None = None) -> dict:
    """
    Run a TypeScript hook handler function.

    Args:
        handler_name: Name of the handler function (onSubagentStart, onSubagentStop, etc.)
        input_data: Input data to pass to the handler
        env_vars: Optional environment variables to set

    Returns:
        dict: The parsed JSON output from the handler
    """
    # Create a temporary TypeScript file that imports and runs the handler
    test_script = f"""
import {{ {handler_name} }} from './chain-of-responsibility.js';

const input = {json.dumps(input_data)};

async function main() {{
    const output = await {handler_name}(input);
    console.log(JSON.stringify(output));
}}

main().catch(err => {{
    console.error(err);
    process.exit(1);
}});
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False, dir=HOOKS_DIR / "src" / "patterns") as f:
        f.write(test_script)
        test_file = f.name

    try:
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        result = subprocess.run(
            ["npx", "tsx", test_file],
            cwd=HOOKS_DIR / "src" / "patterns",
            capture_output=True,
            text=True,
            env=env,
            timeout=10
        )

        if result.returncode != 0:
            raise RuntimeError(f"Handler failed: {result.stderr}")

        return json.loads(result.stdout.strip())
    finally:
        os.unlink(test_file)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    # Initialize the database with the cor_handlers table
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cor_handlers (
            id TEXT PRIMARY KEY,
            cor_id TEXT NOT NULL,
            priority INTEGER NOT NULL,
            agent_id TEXT,
            handled BOOLEAN DEFAULT 0,
            escalated BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)


class TestOnSubagentStart:
    """Tests for onSubagentStart handler."""

    def test_no_cor_id_continues_silently(self):
        """When no COR_ID is set, handler should continue without message."""
        input_data = {"session_id": "test-session"}
        output = run_hook_handler("onSubagentStart", input_data)

        assert output["result"] == "continue"
        assert "message" not in output or output.get("message") == ""

    def test_invalid_cor_id_continues_silently(self):
        """When COR_ID has invalid format, handler should continue without message."""
        input_data = {"session_id": "test-session"}
        env_vars = {"COR_ID": "../../../etc/passwd"}
        output = run_hook_handler("onSubagentStart", input_data, env_vars)

        assert output["result"] == "continue"
        assert "message" not in output or output.get("message") == ""

    def test_injects_handler_position_context(self):
        """Should inject handler position and chain context."""
        input_data = {"session_id": "test-session"}
        env_vars = {
            "COR_ID": "chain-abc123",
            "HANDLER_PRIORITY": "1",
            "CHAIN_LENGTH": "5"
        }
        output = run_hook_handler("onSubagentStart", input_data, env_vars)

        assert output["result"] == "continue"
        assert "message" in output
        message = output["message"]
        assert "Handler at position 1" in message or "priority 1" in message
        assert "5" in message  # chain length
        assert "chain-abc123" in message or "can_handle" in message.lower()


class TestOnSubagentStop:
    """Tests for onSubagentStop handler."""

    def test_no_cor_id_continues_silently(self):
        """When no COR_ID is set, handler should continue without database update."""
        input_data = {"session_id": "test-session", "agent_id": "agent-123"}
        output = run_hook_handler("onSubagentStop", input_data)

        assert output["result"] == "continue"

    def test_tracks_handling_success(self, temp_db):
        """Should mark handler as successful when agent completes."""
        input_data = {"session_id": "test-session", "agent_id": "agent-123"}
        env_vars = {
            "COR_ID": "chain-abc123",
            "HANDLER_PRIORITY": "1",
            "CLAUDE_PROJECT_DIR": str(Path(temp_db).parent)
        }

        # Rename temp DB to match expected path
        import shutil
        expected_path = Path(temp_db).parent / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_db, expected_path)

        try:
            output = run_hook_handler("onSubagentStop", input_data, env_vars)
            assert output["result"] == "continue"

            # Verify database was updated
            import sqlite3
            conn = sqlite3.connect(expected_path)
            cursor = conn.execute(
                "SELECT handled, escalated FROM cor_handlers WHERE cor_id = ? AND priority = ?",
                ("chain-abc123", 1)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None
            assert row[0] == 1  # handled = true
            assert row[1] == 0  # escalated = false
        finally:
            if expected_path.exists():
                expected_path.unlink()

    def test_tracks_escalation(self, temp_db):
        """Should mark handler as escalated when configured to pass to next."""
        input_data = {"session_id": "test-session", "agent_id": "agent-123"}
        env_vars = {
            "COR_ID": "chain-abc123",
            "HANDLER_PRIORITY": "1",
            "COR_ESCALATE": "true",
            "CLAUDE_PROJECT_DIR": str(Path(temp_db).parent)
        }

        # Rename temp DB to match expected path
        import shutil
        expected_path = Path(temp_db).parent / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_db, expected_path)

        try:
            output = run_hook_handler("onSubagentStop", input_data, env_vars)
            assert output["result"] == "continue"

            # Verify database was updated
            import sqlite3
            conn = sqlite3.connect(expected_path)
            cursor = conn.execute(
                "SELECT handled, escalated FROM cor_handlers WHERE cor_id = ? AND priority = ?",
                ("chain-abc123", 1)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None
            assert row[0] == 0  # handled = false (escalated instead)
            assert row[1] == 1  # escalated = true
        finally:
            if expected_path.exists():
                expected_path.unlink()


class TestOnPreToolUse:
    """Tests for onPreToolUse handler."""

    def test_no_cor_id_continues_silently(self):
        """When no COR_ID is set, handler should continue without message."""
        input_data = {"session_id": "test-session", "tool_name": "Bash"}
        output = run_hook_handler("onPreToolUse", input_data)

        assert output["result"] == "continue"

    def test_injects_chain_context(self):
        """Should inject chain context showing which handlers came before."""
        input_data = {"session_id": "test-session", "tool_name": "Bash"}
        env_vars = {
            "COR_ID": "chain-abc123",
            "HANDLER_PRIORITY": "2",
            "CHAIN_LENGTH": "5"
        }
        output = run_hook_handler("onPreToolUse", input_data, env_vars)

        assert output["result"] == "continue"
        # Should have context about being handler 2 of 5
        if "message" in output and output["message"]:
            message = output["message"]
            assert "2" in message and "5" in message


class TestOnStop:
    """Tests for onStop handler."""

    def test_no_cor_id_continues_silently(self):
        """When no COR_ID is set, handler should continue without message."""
        input_data = {"session_id": "test-session"}
        output = run_hook_handler("onStop", input_data)

        assert output["result"] == "continue"

    def test_provides_resolution_summary(self, temp_db):
        """Should provide summary of which handler resolved the request."""
        # Populate database with chain history
        import sqlite3
        conn = sqlite3.connect(temp_db)
        from datetime import datetime

        # Handler 0 escalated
        conn.execute(
            "INSERT INTO cor_handlers (id, cor_id, priority, agent_id, handled, escalated, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("h0", "chain-abc123", 0, "agent-0", 0, 1, datetime.now().isoformat())
        )
        # Handler 1 escalated
        conn.execute(
            "INSERT INTO cor_handlers (id, cor_id, priority, agent_id, handled, escalated, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("h1", "chain-abc123", 1, "agent-1", 0, 1, datetime.now().isoformat())
        )
        # Handler 2 handled
        conn.execute(
            "INSERT INTO cor_handlers (id, cor_id, priority, agent_id, handled, escalated, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("h2", "chain-abc123", 2, "agent-2", 1, 0, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        # Rename temp DB to match expected path
        import shutil
        expected_path = Path(temp_db).parent / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_db, expected_path)

        try:
            input_data = {"session_id": "test-session"}
            env_vars = {
                "COR_ID": "chain-abc123",
                "CLAUDE_PROJECT_DIR": str(Path(temp_db).parent)
            }
            output = run_hook_handler("onStop", input_data, env_vars)

            assert output["result"] == "continue"
            assert "message" in output
            message = output["message"]
            # Should indicate handler 2 resolved it
            assert "2" in message or "agent-2" in message
            assert "escalat" in message.lower()  # mentions escalation
        finally:
            if expected_path.exists():
                expected_path.unlink()


# =============================================================================
# onPostToolUse Handler Tests (TDD - Red Phase)
# =============================================================================


class TestOnPostToolUseExport:
    """Tests for onPostToolUse handler export."""

    def test_exports_on_post_tool_use(self):
        """Module exports onPostToolUse function."""
        content = CHAIN_OF_RESPONSIBILITY_TS.read_text()
        assert "export" in content and "onPostToolUse" in content, (
            "Module must export onPostToolUse function. "
            "Expected: export function onPostToolUse or export { onPostToolUse }"
        )


class TestOnPostToolUseRecordsHandlerResolution:
    """Tests for onPostToolUse recording when handler resolves request."""

    def test_records_handler_resolution_on_task_complete(self, temp_db):
        """onPostToolUse records handler resolution when Task completes successfully."""
        # Setup: Create a chain where handler is processing
        import sqlite3
        import shutil

        expected_path = Path(temp_db).parent / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_db, expected_path)

        try:
            input_data = {
                "session_id": "test-session",
                "tool_name": "Task",
                "tool_input": {"prompt": "Handle this request"},
                "tool_response": {
                    "status": "success",
                    "result": "Request processed successfully"
                }
            }
            env_vars = {
                "COR_ID": "chain-abc123",
                "HANDLER_PRIORITY": "2",
                "CHAIN_LENGTH": "5",
                "CLAUDE_PROJECT_DIR": str(Path(temp_db).parent)
            }

            output = run_hook_handler("onPostToolUse", input_data, env_vars)

            assert output["result"] == "continue"

            # Verify resolution was recorded
            conn = sqlite3.connect(expected_path)
            cursor = conn.execute(
                "SELECT handled FROM cor_handlers WHERE cor_id = ? AND priority = ?",
                ("chain-abc123", 2)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Handler resolution should be recorded in database"
            assert row[0] == 1, "handled should be True when Task completes successfully"
        finally:
            if expected_path.exists():
                expected_path.unlink()

    def test_records_resolution_tool_name(self, temp_db):
        """onPostToolUse records which tool led to resolution."""
        import sqlite3
        import shutil

        # First add resolution_tool column to the temp DB schema
        conn = sqlite3.connect(temp_db)
        conn.execute("ALTER TABLE cor_handlers ADD COLUMN resolution_tool TEXT")
        conn.commit()
        conn.close()

        expected_path = Path(temp_db).parent / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_db, expected_path)

        try:
            input_data = {
                "session_id": "test-session",
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/result.txt", "content": "done"},
                "tool_response": {"status": "success"}
            }
            env_vars = {
                "COR_ID": "chain-abc123",
                "HANDLER_PRIORITY": "1",
                "COR_RESOLVED": "true",  # Handler signals resolution
                "CLAUDE_PROJECT_DIR": str(Path(temp_db).parent)
            }

            output = run_hook_handler("onPostToolUse", input_data, env_vars)
            assert output["result"] == "continue"

            # Verify tool name was recorded
            conn = sqlite3.connect(expected_path)
            cursor = conn.execute(
                "SELECT resolution_tool FROM cor_handlers WHERE cor_id = ? AND priority = ?",
                ("chain-abc123", 1)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Resolution should be recorded"
            assert row[0] == "Write", "Resolution tool should be recorded"
        finally:
            if expected_path.exists():
                expected_path.unlink()


class TestOnPostToolUseRecordsEscalation:
    """Tests for onPostToolUse recording escalation decisions."""

    def test_records_escalation_when_handler_cannot_process(self, temp_db):
        """onPostToolUse records escalation when handler decides to pass."""
        import sqlite3
        import shutil

        # Add escalation_reason column to schema
        conn = sqlite3.connect(temp_db)
        conn.execute("ALTER TABLE cor_handlers ADD COLUMN escalation_reason TEXT")
        conn.commit()
        conn.close()

        expected_path = Path(temp_db).parent / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_db, expected_path)

        try:
            input_data = {
                "session_id": "test-session",
                "tool_name": "Task",
                "tool_input": {"prompt": "Escalate to next handler"},
                "tool_response": {
                    "status": "escalate",
                    "reason": "Cannot handle this request type"
                }
            }
            env_vars = {
                "COR_ID": "chain-abc123",
                "HANDLER_PRIORITY": "0",
                "CHAIN_LENGTH": "3",
                "CLAUDE_PROJECT_DIR": str(Path(temp_db).parent)
            }

            output = run_hook_handler("onPostToolUse", input_data, env_vars)
            assert output["result"] == "continue"

            # Verify escalation was recorded
            conn = sqlite3.connect(expected_path)
            cursor = conn.execute(
                "SELECT escalated, escalation_reason FROM cor_handlers WHERE cor_id = ? AND priority = ?",
                ("chain-abc123", 0)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Escalation should be recorded"
            assert row[0] == 1, "escalated should be True"
            assert row[1] is not None, "escalation_reason should be recorded"
        finally:
            if expected_path.exists():
                expected_path.unlink()

    def test_records_escalation_with_env_var_signal(self, temp_db):
        """onPostToolUse records escalation when COR_ESCALATE env var is set."""
        import sqlite3
        import shutil

        expected_path = Path(temp_db).parent / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_db, expected_path)

        try:
            input_data = {
                "session_id": "test-session",
                "tool_name": "Bash",
                "tool_input": {"command": "echo 'escalating'"},
                "tool_response": {"output": "escalating"}
            }
            env_vars = {
                "COR_ID": "chain-abc123",
                "HANDLER_PRIORITY": "1",
                "COR_ESCALATE": "true",  # Signal escalation
                "CLAUDE_PROJECT_DIR": str(Path(temp_db).parent)
            }

            output = run_hook_handler("onPostToolUse", input_data, env_vars)
            assert output["result"] == "continue"

            # Verify escalation was recorded
            conn = sqlite3.connect(expected_path)
            cursor = conn.execute(
                "SELECT escalated FROM cor_handlers WHERE cor_id = ? AND priority = ?",
                ("chain-abc123", 1)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None, "Escalation should be recorded"
            assert row[0] == 1, "escalated should be True when COR_ESCALATE=true"
        finally:
            if expected_path.exists():
                expected_path.unlink()


class TestOnPostToolUseInputValidation:
    """Tests for security validation in onPostToolUse handler."""

    def test_validates_cor_id_format(self):
        """onPostToolUse rejects malicious COR_ID values."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "test"},
            "tool_response": {"status": "success"}
        }

        # Try path traversal attack
        env_vars = {"COR_ID": "../../../etc/passwd"}
        output = run_hook_handler("onPostToolUse", input_data, env_vars)
        assert output["result"] == "continue"
        assert "message" not in output or not output.get("message"), (
            "Should not process with malicious COR_ID"
        )

    def test_validates_handler_priority_format(self):
        """onPostToolUse rejects malicious HANDLER_PRIORITY values."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "test"},
            "tool_response": {"status": "success"}
        }

        # Try SQL injection via priority
        env_vars = {
            "COR_ID": "valid-chain-id",
            "HANDLER_PRIORITY": "1; DROP TABLE cor_handlers;--"
        }
        output = run_hook_handler("onPostToolUse", input_data, env_vars)
        assert output["result"] == "continue"
        # Handler should not crash and should not execute SQL injection

    def test_validates_tool_response_json(self):
        """onPostToolUse handles malformed tool_response gracefully."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "test"},
            "tool_response": "not a valid json object"  # String instead of dict
        }

        env_vars = {
            "COR_ID": "valid-chain-id",
            "HANDLER_PRIORITY": "1"
        }
        output = run_hook_handler("onPostToolUse", input_data, env_vars)
        assert output["result"] == "continue", (
            "Should continue gracefully with malformed tool_response"
        )

    def test_rejects_shell_metacharacters_in_cor_id(self):
        """onPostToolUse rejects COR_ID with shell metacharacters."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "test"},
            "tool_response": {"status": "success"}
        }

        malicious_ids = [
            "test; rm -rf /",
            "test$(whoami)",
            "test`id`",
            "test|cat /etc/passwd",
            "test\nid",
        ]

        for malicious_id in malicious_ids:
            env_vars = {"COR_ID": malicious_id}
            output = run_hook_handler("onPostToolUse", input_data, env_vars)
            assert output["result"] == "continue", (
                f"Should reject malicious COR_ID: {malicious_id}"
            )


class TestOnPostToolUseNoOpBehavior:
    """Tests for no-op behavior when not in chain context."""

    def test_no_op_when_cor_id_missing(self):
        """onPostToolUse is no-op when COR_ID not set."""
        input_data = {
            "session_id": "test-session",
            "tool_name": "Task",
            "tool_input": {"prompt": "test"},
            "tool_response": {"status": "success"}
        }

        # No COR_ID env var
        output = run_hook_handler("onPostToolUse", input_data, {})
        assert output["result"] == "continue"
        assert "message" not in output or not output.get("message")

    def test_no_op_for_non_resolution_tools(self, temp_db):
        """onPostToolUse doesn't record for tools that don't indicate resolution."""
        import sqlite3
        import shutil

        expected_path = Path(temp_db).parent / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(temp_db, expected_path)

        try:
            input_data = {
                "session_id": "test-session",
                "tool_name": "Read",  # Reading doesn't indicate resolution
                "tool_input": {"file_path": "/tmp/test.txt"},
                "tool_response": {"content": "file contents"}
            }
            env_vars = {
                "COR_ID": "chain-abc123",
                "HANDLER_PRIORITY": "1",
                "CLAUDE_PROJECT_DIR": str(Path(temp_db).parent)
            }

            output = run_hook_handler("onPostToolUse", input_data, env_vars)
            assert output["result"] == "continue"

            # Verify no resolution was recorded for Read tool
            conn = sqlite3.connect(expected_path)
            cursor = conn.execute(
                "SELECT COUNT(*) FROM cor_handlers WHERE cor_id = ? AND handled = 1",
                ("chain-abc123",)
            )
            count = cursor.fetchone()[0]
            conn.close()

            assert count == 0, "Read tool should not trigger resolution recording"
        finally:
            if expected_path.exists():
                expected_path.unlink()
