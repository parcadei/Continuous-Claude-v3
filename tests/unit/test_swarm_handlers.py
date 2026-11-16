"""TDD Tests for Phase 3: patterns/swarm.ts unified module.

These tests verify that the unified swarm pattern handlers correctly:
1. onSubagentStart - logs agent joining swarm
2. onSubagentStop - broadcasts "done" message
3. onPreToolUse - injects broadcasts into context
4. onPostToolUse - tracks Task completions
5. onStop - blocks coordinator until all agents done

The unified module extracts logic from:
- subagent-start-swarm.ts
- subagent-stop-swarm.ts
- pre-tool-use-broadcast.ts
- post-task-complete.ts
- stop-swarm-coordinator.ts

Module path: .claude/hooks/src/patterns/swarm.ts

Tests are designed to FAIL initially (TDD approach) until Phase 3 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 3)
"""

import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def hooks_dir() -> Path:
    """Path to hooks directory."""
    return Path(__file__).parents[2] / ".claude" / "hooks"


@pytest.fixture
def swarm_module_path(hooks_dir: Path) -> Path:
    """Path to the unified swarm module."""
    return hooks_dir / "src" / "patterns" / "swarm.ts"


@pytest.fixture
def project_with_db() -> Generator[tuple[Path, str], None, None]:
    """Create project with coordination DB."""
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

        swarm_id = "test-swarm-unified"
        yield Path(tmpdir), swarm_id


@pytest.fixture
def project_with_active_swarm() -> Generator[tuple[Path, str], None, None]:
    """Create project with swarm that has broadcasts from other agents."""
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

        swarm_id = "test-swarm-active"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # Add broadcasts from other agents
        conn.execute(
            "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
            ("bc1", swarm_id, "agent-1", "finding",
             json.dumps({"content": "Found something important"}), now)
        )
        conn.execute(
            "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
            ("bc2", swarm_id, "agent-2", "progress",
             json.dumps({"status": "50% complete"}), now)
        )
        conn.commit()
        conn.close()

        yield Path(tmpdir), swarm_id


@pytest.fixture
def project_with_partial_completion() -> Generator[tuple[Path, str], None, None]:
    """Create project with swarm where some agents are done."""
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

        # 3 agents started
        for i, agent in enumerate(["agent-1", "agent-2", "agent-3"]):
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                (f"start{i}", swarm_id, agent, "started",
                 json.dumps({"task": f"Task for {agent}"}), now)
            )

        # Only agent-1 is done
        conn.execute(
            "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
            ("done1", swarm_id, "agent-1", "done",
             json.dumps({"summary": "Agent 1 completed"}), now)
        )

        conn.commit()
        conn.close()

        yield Path(tmpdir), swarm_id


@pytest.fixture
def project_with_all_done() -> Generator[tuple[Path, str], None, None]:
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
            CREATE INDEX IF NOT EXISTS idx_broadcasts_swarm
                ON broadcasts(swarm_id, created_at);
        """)

        swarm_id = "test-swarm-complete"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # 2 agents, both done
        for i, agent in enumerate(["agent-1", "agent-2"]):
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


# =============================================================================
# Module Existence Tests
# =============================================================================


class TestSwarmModuleExists:
    """Tests for unified swarm module file existence."""

    def test_swarm_module_exists(self, swarm_module_path: Path) -> None:
        """Unified swarm.ts module exists at expected path."""
        assert swarm_module_path.exists(), (
            f"Unified swarm module not found: {swarm_module_path}. "
            "Create .claude/hooks/src/patterns/swarm.ts"
        )

    def test_patterns_directory_exists(self, hooks_dir: Path) -> None:
        """Patterns directory exists at expected path."""
        patterns_dir = hooks_dir / "src" / "patterns"
        assert patterns_dir.exists(), (
            f"Patterns directory not found: {patterns_dir}. "
            "Create .claude/hooks/src/patterns/"
        )


class TestSwarmModuleExports:
    """Tests for swarm module exports."""

    def test_exports_on_subagent_start(self, swarm_module_path: Path) -> None:
        """Module exports onSubagentStart function."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        content = swarm_module_path.read_text()
        assert "export" in content and "onSubagentStart" in content, (
            "Module must export onSubagentStart function. "
            "Expected: export function onSubagentStart or export { onSubagentStart }"
        )

    def test_exports_on_subagent_stop(self, swarm_module_path: Path) -> None:
        """Module exports onSubagentStop function."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        content = swarm_module_path.read_text()
        assert "export" in content and "onSubagentStop" in content, (
            "Module must export onSubagentStop function. "
            "Expected: export function onSubagentStop or export { onSubagentStop }"
        )

    def test_exports_on_pre_tool_use(self, swarm_module_path: Path) -> None:
        """Module exports onPreToolUse function."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        content = swarm_module_path.read_text()
        assert "export" in content and "onPreToolUse" in content, (
            "Module must export onPreToolUse function. "
            "Expected: export function onPreToolUse or export { onPreToolUse }"
        )

    def test_exports_on_post_tool_use(self, swarm_module_path: Path) -> None:
        """Module exports onPostToolUse function."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        content = swarm_module_path.read_text()
        assert "export" in content and "onPostToolUse" in content, (
            "Module must export onPostToolUse function. "
            "Expected: export function onPostToolUse or export { onPostToolUse }"
        )

    def test_exports_on_stop(self, swarm_module_path: Path) -> None:
        """Module exports onStop function."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        content = swarm_module_path.read_text()
        assert "export" in content and "onStop" in content, (
            "Module must export onStop function. "
            "Expected: export function onStop or export { onStop }"
        )


# =============================================================================
# onSubagentStart Handler Tests
# =============================================================================


class TestOnSubagentStartHandler:
    """Tests for onSubagentStart handler - logs agent joining swarm."""

    def test_logs_agent_joining_swarm(
        self,
        hooks_dir: Path,
        swarm_module_path: Path
    ) -> None:
        """onSubagentStart logs agent joining to stderr."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        # Create a test script that imports and runs onSubagentStart
        test_script = """
import { onSubagentStart } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'test-agent-123',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        swarm_id = "test-swarm-log"
        agent_id = "test-agent-123"

        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Handler failed: {result.stderr}"

        # Check stderr for agent joining log
        stderr = result.stderr.lower()
        assert agent_id.lower() in stderr or "agent" in stderr, (
            f"onSubagentStart should log agent joining to stderr. Got: {result.stderr}"
        )

        # Check stdout for valid result
        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"onSubagentStart should return 'continue'. Got: {output}"
        )

    def test_returns_continue_always(
        self,
        hooks_dir: Path,
        swarm_module_path: Path
    ) -> None:
        """onSubagentStart always returns 'continue' (never blocks)."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'test-agent',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = "test-swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

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
            "onSubagentStart should NEVER block, always return 'continue'. "
            f"Got: {output}"
        )

    def test_handles_missing_swarm_id(
        self,
        hooks_dir: Path,
        swarm_module_path: Path
    ) -> None:
        """onSubagentStart handles missing SWARM_ID gracefully."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'test-agent',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env.pop("SWARM_ID", None)  # No SWARM_ID
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

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
            f"Should continue when SWARM_ID not set. Got: {output}"
        )


# =============================================================================
# onSubagentStop Handler Tests
# =============================================================================


class TestOnSubagentStopHandler:
    """Tests for onSubagentStop handler - broadcasts 'done' message."""

    def test_broadcasts_done_message(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onSubagentStop creates 'done' broadcast in database."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_db
        agent_id = "stopping-agent-123"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/swarm.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{agent_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
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

        # Verify broadcast was created
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
            f"onSubagentStop should create 'done' broadcast. Found {len(rows)} rows."
        )

    def test_done_broadcast_has_auto_flag(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """Auto-generated done broadcast has 'auto': true in payload."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_db
        agent_id = "auto-flag-agent"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/swarm.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{agent_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
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

        # Verify payload has auto flag
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT payload FROM broadcasts WHERE swarm_id = ? AND sender_agent = ? AND broadcast_type = 'done'",
            (swarm_id, agent_id)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, "Should have done broadcast"
        payload = json.loads(rows[0]["payload"])
        assert payload.get("auto") is True, (
            f"Done broadcast should have 'auto': true. Got: {payload}"
        )

    def test_injects_synthesis_when_all_done(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_partial_completion: tuple[Path, str]
    ) -> None:
        """onSubagentStop injects synthesis message when last agent completes."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_partial_completion

        # Agent-2 and Agent-3 need to complete. Let's complete agent-2 first,
        # then complete agent-3 to trigger synthesis
        for agent_id in ["agent-2", "agent-3"]:
            test_script = f"""
import {{ onSubagentStop }} from './patterns/swarm.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{agent_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
            env = os.environ.copy()
            env["SWARM_ID"] = swarm_id
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

            if agent_id == "agent-3":  # Last agent
                output = json.loads(result.stdout.strip())
                message = output.get("message", "")
                assert message, (
                    "onSubagentStop should inject synthesis message when all agents complete. "
                    f"Got empty message. Output: {output}"
                )
                message_lower = message.lower()
                assert "synth" in message_lower or "complete" in message_lower or "all" in message_lower, (
                    f"Synthesis message should mention synthesis/complete/all. Got: {message}"
                )

    def test_no_synthesis_when_agents_pending(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_partial_completion: tuple[Path, str]
    ) -> None:
        """onSubagentStop does not inject synthesis when agents still pending."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_partial_completion
        # Only agent-1 is done. Agent-2 stopping means agent-3 still pending.
        agent_id = "agent-2"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/swarm.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{agent_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
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
        message = output.get("message", "")

        if message:
            message_lower = message.lower()
            assert "synth" not in message_lower and "all" not in message_lower, (
                f"Should not inject synthesis when agents pending. Got: {message}"
            )


# =============================================================================
# onPreToolUse Handler Tests
# =============================================================================


class TestOnPreToolUseHandler:
    """Tests for onPreToolUse handler - injects broadcasts into context."""

    def test_injects_broadcasts_from_other_agents(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_active_swarm: tuple[Path, str]
    ) -> None:
        """onPreToolUse injects recent broadcasts from other agents."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_active_swarm
        my_agent_id = "agent-3"  # Different from agents in fixture

        test_script = f"""
import {{ onPreToolUse }} from './patterns/swarm.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: {{ command: 'ls' }}
}};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["AGENT_ID"] = my_agent_id
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
            f"onPreToolUse should return 'continue'. Got: {output}"
        )

        # Should have message with broadcasts
        message = output.get("message", "")
        assert message, (
            "onPreToolUse should inject broadcasts from other agents. "
            f"Got empty message. Output: {output}"
        )
        assert "broadcast" in message.lower() or "swarm" in message.lower(), (
            f"Message should contain broadcast context. Got: {message}"
        )

    def test_excludes_own_broadcasts(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_active_swarm: tuple[Path, str]
    ) -> None:
        """onPreToolUse excludes the current agent's own broadcasts."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_active_swarm
        # Use agent-1 which has broadcasts in the fixture
        my_agent_id = "agent-1"

        test_script = f"""
import {{ onPreToolUse }} from './patterns/swarm.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: {{ command: 'ls' }}
}};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["AGENT_ID"] = my_agent_id
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
        message = output.get("message", "")

        # Message should not include agent-1's own broadcasts
        # (The fixture has agent-1 broadcasting "finding")
        # Only agent-2's broadcasts should appear
        if message:
            assert "agent-2" in message.lower() or "progress" in message.lower(), (
                f"Should include other agents' broadcasts. Got: {message}"
            )

    def test_returns_continue_when_no_broadcasts(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPreToolUse returns continue without message when no broadcasts."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_db  # Empty DB

        test_script = """
import { onPreToolUse } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: { command: 'ls' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
        env["AGENT_ID"] = "lonely-agent"
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
            f"Should return 'continue' when no broadcasts. Got: {output}"
        )


# =============================================================================
# onPostToolUse Handler Tests
# =============================================================================


class TestOnPostToolUseHandler:
    """Tests for onPostToolUse handler - tracks Task completions."""

    def test_records_task_spawn_in_db(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse records 'started' broadcast when Task tool spawns agent."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_db
        spawned_agent_id = "spawned-agent-456"

        test_script = f"""
import {{ onPostToolUse }} from './patterns/swarm.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Task',
    tool_input: {{ prompt: 'Do something' }},
    tool_response: {{ agent_id: '{spawned_agent_id}' }}
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
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

        # Verify 'started' broadcast was created
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM broadcasts WHERE swarm_id = ? AND sender_agent = ? AND broadcast_type = 'started'",
            (swarm_id, spawned_agent_id)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onPostToolUse should record 'started' broadcast for spawned agent. "
            f"Found {len(rows)} rows."
        )

    def test_ignores_non_task_tools(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse only tracks Task tool, ignores others."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_db

        test_script = """
import { onPostToolUse } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',  // Not Task
    tool_input: { command: 'ls' },
    tool_response: { output: 'file1.txt' }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
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
            f"Should return 'continue' for non-Task tools. Got: {output}"
        )

        # Verify no broadcast was created
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM broadcasts WHERE swarm_id = ?", (swarm_id,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"Should not create broadcast for Bash tool. Found {count} broadcasts."
        )


# =============================================================================
# onStop Handler Tests
# =============================================================================


class TestOnStopHandler:
    """Tests for onStop handler - blocks coordinator until all done."""

    def test_blocks_when_agents_pending(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_partial_completion: tuple[Path, str]
    ) -> None:
        """onStop blocks when some agents haven't completed."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_partial_completion

        test_script = """
import { onStop } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    stop_hook_active: false
};

const result = await onStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
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
        assert output.get("result") == "block", (
            f"onStop should block when agents pending. Got: {output}"
        )

        # Should have message about waiting
        message = output.get("message", "")
        assert "wait" in message.lower() or "agent" in message.lower(), (
            f"Block message should mention waiting for agents. Got: {message}"
        )

    def test_continues_when_all_done(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_all_done: tuple[Path, str]
    ) -> None:
        """onStop continues when all agents have completed."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_all_done

        test_script = """
import { onStop } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    stop_hook_active: false
};

const result = await onStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
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
            f"onStop should continue when all agents done. Got: {output}"
        )

    def test_prevents_infinite_loop(
        self,
        hooks_dir: Path,
        swarm_module_path: Path,
        project_with_partial_completion: tuple[Path, str]
    ) -> None:
        """onStop continues when stop_hook_active is true (prevents loop)."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        project_dir, swarm_id = project_with_partial_completion

        test_script = """
import { onStop } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    stop_hook_active: true  // Already in stop hook
};

const result = await onStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = swarm_id
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
            f"onStop should continue when stop_hook_active to prevent loop. Got: {output}"
        )

    def test_continues_when_no_swarm(
        self,
        hooks_dir: Path,
        swarm_module_path: Path
    ) -> None:
        """onStop continues when not in a swarm."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        test_script = """
import { onStop } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    stop_hook_active: false
};

const result = await onStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env.pop("SWARM_ID", None)  # No swarm
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

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
            f"onStop should continue when no SWARM_ID. Got: {output}"
        )


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurityValidation:
    """Tests for security validation in swarm handlers."""

    def test_validates_swarm_id_format(
        self,
        hooks_dir: Path,
        swarm_module_path: Path
    ) -> None:
        """Handlers reject malicious SWARM_ID values."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'test-agent',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        # Try malicious SWARM_ID with shell metacharacters
        env = os.environ.copy()
        env["SWARM_ID"] = "test; rm -rf /"  # Should be rejected
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        # Should not crash, should continue (rejecting invalid ID)
        assert result.returncode == 0, f"Handler crashed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Should continue (reject) with invalid SWARM_ID. Got: {output}"
        )

    def test_validates_agent_id_format(
        self,
        hooks_dir: Path,
        swarm_module_path: Path
    ) -> None:
        """Handlers reject malicious agent_id values."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        test_script = """
import { onSubagentStop } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'test`whoami`agent',  // Shell injection attempt
    agent_type: 'general-purpose'
};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["SWARM_ID"] = "valid-swarm-id"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0, f"Handler crashed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Should continue (reject) with invalid agent_id. Got: {output}"
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_handles_missing_db_gracefully(
        self,
        hooks_dir: Path,
        swarm_module_path: Path
    ) -> None:
        """Handlers continue when database doesn't exist."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # No database created
            test_script = """
import { onSubagentStop } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'test-agent',
    agent_type: 'general-purpose'
};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
})();
"""
            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm"
            env["CLAUDE_PROJECT_DIR"] = tmpdir  # No .claude/cache

            result = subprocess.run(
                ["npx", "tsx", "-e", test_script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir / "src"),
                timeout=30
            )

            assert result.returncode == 0, f"Handler crashed: {result.stderr}"

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Should continue when DB missing. Got: {output}"
            )

    def test_handles_corrupted_db_gracefully(
        self,
        hooks_dir: Path,
        swarm_module_path: Path
    ) -> None:
        """Handlers continue when database is corrupted."""
        if not swarm_module_path.exists():
            pytest.skip("Swarm module doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create corrupted DB
            db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
            db_dir.mkdir(parents=True)
            db_path = db_dir / "coordination.db"
            db_path.write_text("Not a valid SQLite database!")

            test_script = """
import { onPreToolUse } from './patterns/swarm.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: { command: 'ls' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
            env = os.environ.copy()
            env["SWARM_ID"] = "test-swarm"
            env["AGENT_ID"] = "test-agent"
            env["CLAUDE_PROJECT_DIR"] = tmpdir

            result = subprocess.run(
                ["npx", "tsx", "-e", test_script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir / "src"),
                timeout=30
            )

            assert result.returncode == 0, f"Handler crashed: {result.stderr}"

            output = json.loads(result.stdout.strip())
            assert output.get("result") == "continue", (
                f"Should continue when DB corrupted. Got: {output}"
            )
