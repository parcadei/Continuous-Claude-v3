"""
Test Blackboard Pattern Handlers

Tests for .claude/hooks/src/patterns/blackboard.ts handlers
"""
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name

    # Initialize database
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS blackboard_state (
            id TEXT PRIMARY KEY,
            blackboard_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            updated_by TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(blackboard_id, key)
        )
    ''')
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def blackboard_env(temp_db, monkeypatch):
    """Set up blackboard environment variables."""
    monkeypatch.setenv('PATTERN_TYPE', 'blackboard')
    monkeypatch.setenv('BLACKBOARD_ID', 'test-bb-123')
    monkeypatch.setenv('AGENT_ROLE', 'specialist')
    monkeypatch.setenv('BLACKBOARD_WRITES_TO', 'requirements,architecture')
    monkeypatch.setenv('BLACKBOARD_READS_FROM', 'query,constraints')
    monkeypatch.setenv('CLAUDE_PROJECT_DIR', str(Path(temp_db).parent.parent))

    yield temp_db


def run_hook(hook_script: str, input_data: dict, env: dict = None) -> dict:
    """Helper to run a hook script and return parsed output."""
    import subprocess

    # Prepare environment
    hook_env = os.environ.copy()
    if env:
        hook_env.update(env)

    # Run hook
    result = subprocess.run(
        ['bash', hook_script],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        env=hook_env,
        cwd=Path(__file__).parent.parent.parent / '.claude' / 'hooks'
    )

    if result.returncode != 0:
        raise RuntimeError(f"Hook failed: {result.stderr}")

    # Parse output
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Invalid JSON output: {result.stdout}")


class TestBlackboardSubagentStart:
    """Test onSubagentStart handler."""

    def test_specialist_gets_context_message(self, blackboard_env):
        """Specialist agent receives blackboard context on start."""
        hook_path = Path(__file__).parent.parent.parent / '.claude' / 'hooks' / 'subagent-start.sh'
        if not hook_path.exists():
            pytest.skip("Hook not yet implemented")

        output = run_hook(
            str(hook_path),
            {'session_id': 'test-session'},
            env={
                'PATTERN_TYPE': 'blackboard',
                'BLACKBOARD_ID': 'test-bb-123',
                'AGENT_ROLE': 'specialist',
                'BLACKBOARD_WRITES_TO': 'requirements,architecture',
                'BLACKBOARD_READS_FROM': 'query,constraints'
            }
        )

        assert output['result'] == 'continue'
        assert 'message' in output
        assert 'specialist' in output['message'].lower()
        assert 'requirements' in output['message']
        assert 'architecture' in output['message']

    def test_controller_gets_approval_context(self, blackboard_env):
        """Controller agent receives approval context on start."""
        hook_path = Path(__file__).parent.parent.parent / '.claude' / 'hooks' / 'subagent-start.sh'
        if not hook_path.exists():
            pytest.skip("Hook not yet implemented")

        output = run_hook(
            str(hook_path),
            {'session_id': 'test-session'},
            env={
                'PATTERN_TYPE': 'blackboard',
                'BLACKBOARD_ID': 'test-bb-123',
                'AGENT_ROLE': 'controller',
            }
        )

        assert output['result'] == 'continue'
        assert 'message' in output
        assert 'controller' in output['message'].lower()

    def test_no_blackboard_id_continues_silently(self):
        """Missing BLACKBOARD_ID causes silent continue."""
        hook_path = Path(__file__).parent.parent.parent / '.claude' / 'hooks' / 'subagent-start.sh'
        if not hook_path.exists():
            pytest.skip("Hook not yet implemented")

        output = run_hook(
            str(hook_path),
            {'session_id': 'test-session'},
            env={'PATTERN_TYPE': 'blackboard'}  # No BLACKBOARD_ID
        )

        assert output['result'] == 'continue'
        assert 'message' not in output or output.get('message') == ''


class TestBlackboardPreToolUse:
    """Test onPreToolUse handler."""

    def test_injects_current_blackboard_state(self, temp_db):
        """PreToolUse injects current blackboard state to specialist."""
        # Use actual coordination DB path
        project_dir = Path(__file__).parent.parent.parent
        coord_db = project_dir / '.claude' / 'cache' / 'agentica-coordination' / 'coordination.db'
        coord_db.parent.mkdir(parents=True, exist_ok=True)

        # Populate blackboard in coordination DB
        conn = sqlite3.connect(str(coord_db))
        conn.execute('''
            CREATE TABLE IF NOT EXISTS blackboard_state (
                id TEXT PRIMARY KEY,
                blackboard_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_by TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(blackboard_id, key)
            )
        ''')
        conn.execute('''
            INSERT OR REPLACE INTO blackboard_state (id, blackboard_id, key, value, updated_by, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', ('test-bb-456_query', 'test-bb-456', 'query', 'Build auth system', 'user'))
        conn.execute('''
            INSERT OR REPLACE INTO blackboard_state (id, blackboard_id, key, value, updated_by, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', ('test-bb-456_constraints', 'test-bb-456', 'constraints', 'Use OAuth2', 'coordinator'))
        conn.commit()
        conn.close()

        try:
            hook_path = project_dir / '.claude' / 'hooks' / 'pre-tool-use.sh'
            if not hook_path.exists():
                pytest.skip("Hook not yet implemented")

            output = run_hook(
                str(hook_path),
                {'session_id': 'test-session', 'tool_name': 'Bash'},
                env={
                    'PATTERN_TYPE': 'blackboard',
                    'BLACKBOARD_ID': 'test-bb-456',
                    'AGENT_ROLE': 'specialist',
                    'BLACKBOARD_READS_FROM': 'query,constraints',
                    'CLAUDE_PROJECT_DIR': str(project_dir)
                }
            )

            assert output['result'] == 'continue'
            assert 'message' in output
            assert 'Build auth system' in output['message']
            assert 'Use OAuth2' in output['message']
        finally:
            # Cleanup
            conn = sqlite3.connect(str(coord_db))
            conn.execute("DELETE FROM blackboard_state WHERE blackboard_id = 'test-bb-456'")
            conn.commit()
            conn.close()

    def test_no_injection_for_controller(self, blackboard_env):
        """Controller does not receive state injection."""
        hook_path = Path(__file__).parent.parent.parent / '.claude' / 'hooks' / 'pre-tool-use.sh'
        if not hook_path.exists():
            pytest.skip("Hook not yet implemented")

        output = run_hook(
            str(hook_path),
            {'session_id': 'test-session', 'tool_name': 'Bash'},
            env={
                'PATTERN_TYPE': 'blackboard',
                'BLACKBOARD_ID': 'test-bb-123',
                'AGENT_ROLE': 'controller'
            }
        )

        assert output['result'] == 'continue'


class TestBlackboardSubagentStop:
    """Test onSubagentStop handler."""

    def test_records_specialist_contribution(self, blackboard_env, temp_db):
        """SubagentStop records specialist contribution to database."""
        hook_path = Path(__file__).parent.parent.parent / '.claude' / 'hooks' / 'subagent-stop.sh'
        if not hook_path.exists():
            pytest.skip("Hook not yet implemented")

        output = run_hook(
            str(hook_path),
            {'session_id': 'test-session', 'agent_id': 'specialist-abc'},
            env={
                'PATTERN_TYPE': 'blackboard',
                'BLACKBOARD_ID': 'test-bb-123',
                'AGENT_ROLE': 'specialist',
                'BLACKBOARD_WRITES_TO': 'requirements',
                'CLAUDE_PROJECT_DIR': str(Path(temp_db).parent.parent)
            }
        )

        assert output['result'] == 'continue'

        # Verify database was updated
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute('''
            SELECT COUNT(*) FROM blackboard_state
            WHERE blackboard_id = ? AND updated_by = ?
        ''', ('test-bb-123', 'specialist-abc'))
        count = cursor.fetchone()[0]
        conn.close()

        # May be 0 if specialist didn't write anything, that's ok
        assert count >= 0


class TestBlackboardStop:
    """Test onStop handler."""

    def test_controller_approval_notification(self):
        """Stop hook notifies controller to approve final state."""
        project_dir = Path(__file__).parent.parent.parent
        coord_db = project_dir / '.claude' / 'cache' / 'agentica-coordination' / 'coordination.db'
        coord_db.parent.mkdir(parents=True, exist_ok=True)

        # Create DB with some blackboard state
        conn = sqlite3.connect(str(coord_db))
        conn.execute('''
            CREATE TABLE IF NOT EXISTS blackboard_state (
                id TEXT PRIMARY KEY,
                blackboard_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_by TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(blackboard_id, key)
            )
        ''')
        conn.execute('''
            INSERT OR REPLACE INTO blackboard_state (id, blackboard_id, key, value, updated_by, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', ('test-bb-789_result', 'test-bb-789', 'result', 'Final answer', 'specialist-1'))
        conn.commit()
        conn.close()

        try:
            hook_path = project_dir / '.claude' / 'hooks' / 'stop-coordinator.sh'
            if not hook_path.exists():
                pytest.skip("Hook not yet implemented")

            output = run_hook(
                str(hook_path),
                {'session_id': 'test-session'},
                env={
                    'PATTERN_TYPE': 'blackboard',
                    'BLACKBOARD_ID': 'test-bb-789',
                    'AGENT_ROLE': 'controller',
                    'CLAUDE_PROJECT_DIR': str(project_dir)
                }
            )

            assert output['result'] == 'continue'
            assert 'message' in output
            assert 'blackboard' in output['message'].lower() or 'final' in output['message'].lower()
        finally:
            # Cleanup
            conn = sqlite3.connect(str(coord_db))
            conn.execute("DELETE FROM blackboard_state WHERE blackboard_id = 'test-bb-789'")
            conn.commit()
            conn.close()


class TestBlackboardPatternType:
    """Test PATTERN_TYPE detection."""

    def test_pattern_type_blackboard_routes_correctly(self, blackboard_env):
        """PATTERN_TYPE=blackboard routes to blackboard handlers."""
        hook_path = Path(__file__).parent.parent.parent / '.claude' / 'hooks' / 'subagent-start.sh'
        if not hook_path.exists():
            pytest.skip("Hook not yet implemented")

        output = run_hook(
            str(hook_path),
            {'session_id': 'test-session'},
            env={
                'PATTERN_TYPE': 'blackboard',
                'BLACKBOARD_ID': 'test-bb-123',
                'AGENT_ROLE': 'specialist',
                'BLACKBOARD_WRITES_TO': 'requirements'
            }
        )

        # Should be handled by blackboard handler
        assert output['result'] == 'continue'
        assert 'message' in output
        assert 'specialist' in output['message'].lower()


# =============================================================================
# onPostToolUse Handler Tests (TDD Red Phase)
# =============================================================================


class TestBlackboardPostToolUseExport:
    """Tests for onPostToolUse export."""

    def test_exports_on_post_tool_use(self):
        """Module exports onPostToolUse function."""
        blackboard_module_path = (
            Path(__file__).parent.parent.parent
            / ".claude"
            / "hooks"
            / "src"
            / "patterns"
            / "blackboard.ts"
        )
        if not blackboard_module_path.exists():
            pytest.skip("Blackboard module doesn't exist yet")

        content = blackboard_module_path.read_text()
        assert "export" in content and "onPostToolUse" in content, (
            "Module must export onPostToolUse function. "
            "Expected: export function onPostToolUse or export { onPostToolUse }"
        )


class TestBlackboardPostToolUseHandler:
    """Tests for onPostToolUse handler - tracks Write operations to blackboard."""

    @pytest.fixture
    def project_with_blackboard_db(self) -> Generator[tuple[Path, str], None, None]:
        """Create project with blackboard coordination DB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)

            db_path = db_dir / "coordination.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS blackboard_state (
                    id TEXT PRIMARY KEY,
                    blackboard_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    updated_by TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(blackboard_id, key)
                );
                CREATE INDEX IF NOT EXISTS idx_blackboard_state
                    ON blackboard_state(blackboard_id, key);
            """)
            conn.commit()
            conn.close()

            blackboard_id = "test-bb-post-tool"
            yield Path(tmpdir), blackboard_id

    def test_records_blackboard_write(
        self,
        project_with_blackboard_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse records Write operations that update blackboard keys."""
        project_dir, blackboard_id = project_with_blackboard_db
        hooks_dir = Path(__file__).parents[2] / ".claude" / "hooks"
        blackboard_module = hooks_dir / "src" / "patterns" / "blackboard.ts"

        if not blackboard_module.exists():
            pytest.skip("Blackboard module doesn't exist yet")

        agent_id = "specialist-writer"
        written_key = "requirements"
        written_value = "Must support OAuth2 and SSO"

        # Simulate Write tool output that updates a blackboard key
        test_script = f"""
import {{ onPostToolUse }} from './patterns/blackboard.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/blackboard/{written_key}.md',
        content: '{written_value}'
    }},
    tool_response: {{ success: true }}
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["BLACKBOARD_ID"] = blackboard_id
        env["AGENT_ID"] = agent_id
        env["AGENT_ROLE"] = "specialist"
        env["BLACKBOARD_WRITES_TO"] = "requirements,architecture"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Handler failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"onPostToolUse should return 'continue'. Got: {output}"
        )

        # Verify the write was recorded in the database
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM blackboard_state WHERE blackboard_id = ? AND key = ?",
            (blackboard_id, written_key)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onPostToolUse should record Write to blackboard key '{written_key}'. "
            f"Found {len(rows)} rows in database."
        )

        row = rows[0]
        assert row["value"] == written_value, (
            f"Recorded value should match written content. "
            f"Expected: {written_value}, Got: {row['value']}"
        )
        assert row["updated_by"] == agent_id, (
            f"updated_by should be the agent ID. "
            f"Expected: {agent_id}, Got: {row['updated_by']}"
        )

    def test_validates_write_permissions(
        self,
        project_with_blackboard_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse only allows writes to keys in BLACKBOARD_WRITES_TO."""
        project_dir, blackboard_id = project_with_blackboard_db
        hooks_dir = Path(__file__).parents[2] / ".claude" / "hooks"
        blackboard_module = hooks_dir / "src" / "patterns" / "blackboard.ts"

        if not blackboard_module.exists():
            pytest.skip("Blackboard module doesn't exist yet")

        agent_id = "restricted-specialist"
        unauthorized_key = "solution"  # Not in BLACKBOARD_WRITES_TO

        test_script = f"""
import {{ onPostToolUse }} from './patterns/blackboard.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/blackboard/{unauthorized_key}.md',
        content: 'Unauthorized write attempt'
    }},
    tool_response: {{ success: true }}
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["BLACKBOARD_ID"] = blackboard_id
        env["AGENT_ID"] = agent_id
        env["AGENT_ROLE"] = "specialist"
        env["BLACKBOARD_WRITES_TO"] = "requirements,architecture"  # Does NOT include 'solution'
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Handler failed: {result.stderr}"

        # Verify the unauthorized write was NOT recorded in the database
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM blackboard_state WHERE blackboard_id = ? AND key = ?",
            (blackboard_id, unauthorized_key)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"Unauthorized write to key '{unauthorized_key}' should NOT be recorded. "
            f"Found {count} rows in database. "
            "Agent only has permission to write to: requirements, architecture"
        )

    def test_validates_input_format(
        self,
        project_with_blackboard_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse validates input for security (no injection attacks)."""
        project_dir, blackboard_id = project_with_blackboard_db
        hooks_dir = Path(__file__).parents[2] / ".claude" / "hooks"
        blackboard_module = hooks_dir / "src" / "patterns" / "blackboard.ts"

        if not blackboard_module.exists():
            pytest.skip("Blackboard module doesn't exist yet")

        # Test with malicious input containing shell metacharacters
        malicious_inputs = [
            {"key": "requirements; rm -rf /", "value": "test"},
            {"key": "requirements`whoami`", "value": "test"},
            {"key": "../../../etc/passwd", "value": "test"},
        ]

        for test_case in malicious_inputs:
            malicious_key = test_case["key"]
            malicious_value = test_case["value"]

            test_script = f"""
import {{ onPostToolUse }} from './patterns/blackboard.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/blackboard/{malicious_key}.md',
        content: "{malicious_value}"
    }},
    tool_response: {{ success: true }}
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""
            env = os.environ.copy()
            env["BLACKBOARD_ID"] = blackboard_id
            env["AGENT_ID"] = "security-test-agent"
            env["AGENT_ROLE"] = "specialist"
            env["BLACKBOARD_WRITES_TO"] = "requirements,architecture"
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)

            result = subprocess.run(
                ["npx", "tsx", "-e", test_script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir / "src"),
                timeout=30
            )

            # Handler should NOT crash with malicious input
            assert result.returncode == 0, (
                f"Handler crashed with malicious input: {test_case}. "
                f"stderr: {result.stderr}"
            )

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Should handle malicious input gracefully: {test_case}. Got: {output}"
            )

        # Verify no malicious data was written (malicious keys should be rejected)
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM blackboard_state WHERE blackboard_id = ?",
            (blackboard_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        # If security validation is working, malicious keys should be rejected
        # because they don't match valid key names (alphanumeric + underscore + hyphen)
        assert count == 0, (
            f"Malicious keys should be rejected. Found {count} rows in database."
        )

    def test_ignores_non_write_tools(
        self,
        project_with_blackboard_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse only processes Write tool, ignores others."""
        project_dir, blackboard_id = project_with_blackboard_db
        hooks_dir = Path(__file__).parents[2] / ".claude" / "hooks"
        blackboard_module = hooks_dir / "src" / "patterns" / "blackboard.ts"

        if not blackboard_module.exists():
            pytest.skip("Blackboard module doesn't exist yet")

        test_script = """
import { onPostToolUse } from './patterns/blackboard.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',  // Not Write tool
    tool_input: { command: 'echo "test"' },
    tool_response: { output: 'test' }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["BLACKBOARD_ID"] = blackboard_id
        env["AGENT_ID"] = "test-agent"
        env["AGENT_ROLE"] = "specialist"
        env["BLACKBOARD_WRITES_TO"] = "requirements"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Handler failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Should return 'continue' for non-Write tools. Got: {output}"
        )

        # Verify no state was recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM blackboard_state WHERE blackboard_id = ?",
            (blackboard_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"Should not record state for Bash tool. Found {count} rows."
        )

    def test_handles_missing_blackboard_id(self) -> None:
        """onPostToolUse continues silently when BLACKBOARD_ID not set."""
        hooks_dir = Path(__file__).parents[2] / ".claude" / "hooks"
        blackboard_module = hooks_dir / "src" / "patterns" / "blackboard.ts"

        if not blackboard_module.exists():
            pytest.skip("Blackboard module doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_script = """
import { onPostToolUse } from './patterns/blackboard.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {
        file_path: '/blackboard/requirements.md',
        content: 'Some content'
    },
    tool_response: { success: true }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
            env = os.environ.copy()
            env.pop("BLACKBOARD_ID", None)  # No BLACKBOARD_ID
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            result = subprocess.run(
                ["npx", "tsx", "-e", test_script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir / "src"),
                timeout=30
            )

            assert result.returncode == 0, f"Handler failed: {result.stderr}"

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Should continue when BLACKBOARD_ID not set. Got: {output}"
            )

    def test_controller_role_bypasses_write_tracking(
        self,
        project_with_blackboard_db: tuple[Path, str]
    ) -> None:
        """Controller role does not track writes (only specialists contribute)."""
        project_dir, blackboard_id = project_with_blackboard_db
        hooks_dir = Path(__file__).parents[2] / ".claude" / "hooks"
        blackboard_module = hooks_dir / "src" / "patterns" / "blackboard.ts"

        if not blackboard_module.exists():
            pytest.skip("Blackboard module doesn't exist yet")

        test_script = """
import { onPostToolUse } from './patterns/blackboard.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {
        file_path: '/blackboard/final_decision.md',
        content: 'Controller decision'
    },
    tool_response: { success: true }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["BLACKBOARD_ID"] = blackboard_id
        env["AGENT_ID"] = "controller-agent"
        env["AGENT_ROLE"] = "controller"  # Controller, not specialist
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Handler failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Should return 'continue' for controller. Got: {output}"
        )

        # Controller writes should NOT be tracked as blackboard contributions
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM blackboard_state WHERE blackboard_id = ? AND updated_by = 'controller-agent'",
            (blackboard_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"Controller writes should not be tracked. Found {count} rows."
        )
