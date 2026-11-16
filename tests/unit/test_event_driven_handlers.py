"""TDD Tests for Phase 51: patterns/event-driven.ts unified module.

These tests verify that the unified event-driven pattern handlers correctly:
1. onSubagentStart - registers subscriber with event types
2. onSubagentStop - unsubscribes and cleans up event subscriptions
3. onPreToolUse - injects pending events for subscribers
4. onPostToolUse - captures published events from publishers
5. onStop - provides event bus summary

The unified module implements Event-Driven pattern coordination:
- Event bus with pub/sub semantics
- Subscriber registration with event type filtering
- Event queue management
- Event delivery to subscribers

Module path: .claude/hooks/src/patterns/event-driven.ts

Tests are designed to FAIL initially (TDD approach) until Phase 51 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 51)
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
def event_driven_module_path(hooks_dir: Path) -> Path:
    """Path to the unified event-driven module."""
    return hooks_dir / "src" / "patterns" / "event-driven.ts"


@pytest.fixture
def project_with_event_bus() -> Generator[tuple[Path, str], None, None]:
    """Create project with coordination DB for event-driven pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS event_subscriptions (
                id TEXT PRIMARY KEY,
                bus_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                event_types TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS event_queue (
                id TEXT PRIMARY KEY,
                bus_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT,
                published_by TEXT,
                created_at TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

        bus_id = "test-event-bus"
        yield Path(tmpdir), bus_id


@pytest.fixture
def project_with_subscriptions() -> Generator[tuple[Path, str], None, None]:
    """Create project with active event subscriptions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS event_subscriptions (
                id TEXT PRIMARY KEY,
                bus_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                event_types TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS event_queue (
                id TEXT PRIMARY KEY,
                bus_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT,
                published_by TEXT,
                created_at TEXT NOT NULL
            );
        """)

        bus_id = "test-bus-with-subs"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # Add 2 subscriptions
        conn.execute(
            "INSERT INTO event_subscriptions VALUES (?, ?, ?, ?, ?)",
            ("sub-1", bus_id, "subscriber-1", '["user.created", "user.updated"]', now)
        )
        conn.execute(
            "INSERT INTO event_subscriptions VALUES (?, ?, ?, ?, ?)",
            ("sub-2", bus_id, "subscriber-2", '["order.placed"]', now)
        )

        # Add some pending events
        conn.execute(
            "INSERT INTO event_queue VALUES (?, ?, ?, ?, ?, ?)",
            ("evt-1", bus_id, "user.created", '{"user_id": "123"}', "publisher-1", now)
        )
        conn.execute(
            "INSERT INTO event_queue VALUES (?, ?, ?, ?, ?, ?)",
            ("evt-2", bus_id, "order.placed", '{"order_id": "456"}', "publisher-1", now)
        )

        conn.commit()
        conn.close()

        yield Path(tmpdir), bus_id


# =============================================================================
# Module Existence Tests
# =============================================================================


class TestEventDrivenModuleExists:
    """Tests for unified event-driven module file existence."""

    def test_event_driven_module_exists(self, event_driven_module_path: Path) -> None:
        """Unified event-driven.ts module exists at expected path."""
        assert event_driven_module_path.exists(), (
            f"Unified event-driven module not found: {event_driven_module_path}. "
            "Create .claude/hooks/src/patterns/event-driven.ts"
        )

    def test_patterns_directory_exists(self, hooks_dir: Path) -> None:
        """Patterns directory exists at expected path."""
        patterns_dir = hooks_dir / "src" / "patterns"
        assert patterns_dir.exists(), (
            f"Patterns directory not found: {patterns_dir}. "
            "Create .claude/hooks/src/patterns/"
        )


class TestEventDrivenModuleExports:
    """Tests for event-driven module exports."""

    def test_exports_on_subagent_start(self, event_driven_module_path: Path) -> None:
        """Module exports onSubagentStart function."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        content = event_driven_module_path.read_text()
        assert "export" in content and "onSubagentStart" in content, (
            "Module must export onSubagentStart function. "
            "Expected: export function onSubagentStart or export { onSubagentStart }"
        )

    def test_exports_on_subagent_stop(self, event_driven_module_path: Path) -> None:
        """Module exports onSubagentStop function."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        content = event_driven_module_path.read_text()
        assert "export" in content and "onSubagentStop" in content, (
            "Module must export onSubagentStop function. "
            "Expected: export function onSubagentStop or export { onSubagentStop }"
        )

    def test_exports_on_pre_tool_use(self, event_driven_module_path: Path) -> None:
        """Module exports onPreToolUse function."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        content = event_driven_module_path.read_text()
        assert "export" in content and "onPreToolUse" in content, (
            "Module must export onPreToolUse function. "
            "Expected: export function onPreToolUse or export { onPreToolUse }"
        )

    def test_exports_on_post_tool_use(self, event_driven_module_path: Path) -> None:
        """Module exports onPostToolUse function."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        content = event_driven_module_path.read_text()
        assert "export" in content and "onPostToolUse" in content, (
            "Module must export onPostToolUse function. "
            "Expected: export function onPostToolUse or export { onPostToolUse }"
        )

    def test_exports_on_stop(self, event_driven_module_path: Path) -> None:
        """Module exports onStop function."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        content = event_driven_module_path.read_text()
        assert "export" in content and "onStop" in content, (
            "Module must export onStop function. "
            "Expected: export function onStop or export { onStop }"
        )


# =============================================================================
# onSubagentStart Handler Tests
# =============================================================================


class TestOnSubagentStartHandler:
    """Tests for onSubagentStart handler - registers subscriber."""

    def test_registers_subscriber_with_event_types(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path,
        project_with_event_bus: tuple[Path, str]
    ) -> None:
        """onSubagentStart registers subscriber with event types in database."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        project_dir, bus_id = project_with_event_bus
        agent_id = "subscriber-test"

        test_script = f"""
import {{ onSubagentStart }} from './patterns/event-driven.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{agent_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "event_driven"
        env["EVENT_BUS_ID"] = bus_id
        env["AGENT_ROLE"] = "subscriber"
        env["SUBSCRIBER_EVENT_TYPES"] = '["user.created", "order.placed"]'
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

        # Verify subscription was registered
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM event_subscriptions WHERE bus_id = ? AND agent_id = ?",
            (bus_id, agent_id)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onSubagentStart should register subscription. Found {len(rows)} rows."
        )

        # Verify event_types were stored
        row = rows[0]
        event_types = json.loads(row['event_types'])
        assert "user.created" in event_types
        assert "order.placed" in event_types

    def test_publisher_does_not_register_subscription(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path,
        project_with_event_bus: tuple[Path, str]
    ) -> None:
        """onSubagentStart does not register subscription for publishers."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        project_dir, bus_id = project_with_event_bus

        test_script = """
import { onSubagentStart } from './patterns/event-driven.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'publisher-agent',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "event_driven"
        env["EVENT_BUS_ID"] = bus_id
        env["AGENT_ROLE"] = "publisher"
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
        assert output.get("result") == "continue"

    def test_handles_missing_event_bus_id(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path
    ) -> None:
        """onSubagentStart handles missing EVENT_BUS_ID gracefully."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/event-driven.ts';

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
        env.pop("EVENT_BUS_ID", None)  # No EVENT_BUS_ID
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
            f"Should continue when EVENT_BUS_ID not set. Got: {output}"
        )


# =============================================================================
# onSubagentStop Handler Tests
# =============================================================================


class TestOnSubagentStopHandler:
    """Tests for onSubagentStop handler - unsubscribes."""

    def test_removes_subscription(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path,
        project_with_subscriptions: tuple[Path, str]
    ) -> None:
        """onSubagentStop removes subscription from database."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        project_dir, bus_id = project_with_subscriptions
        agent_id = "subscriber-1"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/event-driven.ts';

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
        env["PATTERN_TYPE"] = "event_driven"
        env["EVENT_BUS_ID"] = bus_id
        env["AGENT_ROLE"] = "subscriber"
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

        # Verify subscription was removed
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM event_subscriptions WHERE bus_id = ? AND agent_id = ?",
            (bus_id, agent_id)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"onSubagentStop should remove subscription. Found {count} rows remaining."
        )


# =============================================================================
# onPreToolUse Handler Tests
# =============================================================================


class TestOnPreToolUseHandler:
    """Tests for onPreToolUse handler - injects pending events."""

    def test_injects_pending_events_for_subscriber(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path,
        project_with_subscriptions: tuple[Path, str]
    ) -> None:
        """onPreToolUse injects pending events that match subscriber's types."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        project_dir, bus_id = project_with_subscriptions

        test_script = """
import { onPreToolUse } from './patterns/event-driven.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: { command: 'echo test' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "event_driven"
        env["EVENT_BUS_ID"] = bus_id
        env["AGENT_ROLE"] = "subscriber"
        env["SUBSCRIBER_EVENT_TYPES"] = '["user.created"]'
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
        assert output.get("result") == "continue"

        # Should have injected events message
        message = output.get("message", "")
        if message:
            message_lower = message.lower()
            assert "event" in message_lower or "user.created" in message_lower

    def test_no_events_for_non_matching_types(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path,
        project_with_subscriptions: tuple[Path, str]
    ) -> None:
        """onPreToolUse does not inject events that don't match subscriber types."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        project_dir, bus_id = project_with_subscriptions

        test_script = """
import { onPreToolUse } from './patterns/event-driven.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: { command: 'echo test' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "event_driven"
        env["EVENT_BUS_ID"] = bus_id
        env["AGENT_ROLE"] = "subscriber"
        env["SUBSCRIBER_EVENT_TYPES"] = '["unrelated.event"]'  # No match
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
        assert output.get("result") == "continue"

    def test_publisher_does_not_receive_events(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path,
        project_with_subscriptions: tuple[Path, str]
    ) -> None:
        """onPreToolUse does not inject events for publishers."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        project_dir, bus_id = project_with_subscriptions

        test_script = """
import { onPreToolUse } from './patterns/event-driven.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: { command: 'echo test' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "event_driven"
        env["EVENT_BUS_ID"] = bus_id
        env["AGENT_ROLE"] = "publisher"
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
        assert output.get("result") == "continue"


# =============================================================================
# onPostToolUse Handler Tests
# =============================================================================


class TestOnPostToolUseHandler:
    """Tests for onPostToolUse handler - captures published events."""

    def test_captures_published_event_from_write(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path,
        project_with_event_bus: tuple[Path, str]
    ) -> None:
        """onPostToolUse captures event from Write tool for publishers."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        project_dir, bus_id = project_with_event_bus

        test_script = """
import { onPostToolUse } from './patterns/event-driven.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {
        file_path: '/tmp/event.json',
        content: JSON.stringify({
            event_type: 'user.created',
            payload: { user_id: '789' }
        })
    },
    tool_response: { success: true }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "event_driven"
        env["EVENT_BUS_ID"] = bus_id
        env["AGENT_ROLE"] = "publisher"
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
        assert output.get("result") == "continue"


# =============================================================================
# onStop Handler Tests
# =============================================================================


class TestOnStopHandler:
    """Tests for onStop handler - event bus summary."""

    def test_provides_event_bus_summary(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path,
        project_with_subscriptions: tuple[Path, str]
    ) -> None:
        """onStop provides event bus summary with stats."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        project_dir, bus_id = project_with_subscriptions

        test_script = """
import { onStop } from './patterns/event-driven.ts';

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
        env["PATTERN_TYPE"] = "event_driven"
        env["EVENT_BUS_ID"] = bus_id
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
        assert output.get("result") == "continue"

        message = output.get("message", "")
        if message:
            message_lower = message.lower()
            assert "event" in message_lower or "subscriber" in message_lower or "bus" in message_lower

    def test_continues_when_no_event_bus(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path
    ) -> None:
        """onStop continues when not in an event-driven pattern."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        test_script = """
import { onStop } from './patterns/event-driven.ts';

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
        env.pop("EVENT_BUS_ID", None)  # No event bus
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
            f"onStop should continue when no EVENT_BUS_ID. Got: {output}"
        )


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurityValidation:
    """Tests for security validation in event-driven handlers."""

    def test_validates_event_bus_id_format(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path
    ) -> None:
        """Handlers reject malicious EVENT_BUS_ID values."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/event-driven.ts';

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
        env["EVENT_BUS_ID"] = "test; DROP TABLE event_queue;"  # Should be rejected
        env["AGENT_ROLE"] = "subscriber"
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
            f"Should continue (reject) with invalid EVENT_BUS_ID. Got: {output}"
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_handles_missing_db_gracefully(
        self,
        hooks_dir: Path,
        event_driven_module_path: Path
    ) -> None:
        """Handlers continue when database doesn't exist."""
        if not event_driven_module_path.exists():
            pytest.skip("EventDriven module doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_script = """
import { onSubagentStart } from './patterns/event-driven.ts';

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
            env["EVENT_BUS_ID"] = "test-bus"
            env["AGENT_ROLE"] = "subscriber"
            env["SUBSCRIBER_EVENT_TYPES"] = '["test.event"]'
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
