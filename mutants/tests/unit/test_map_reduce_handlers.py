"""TDD Tests for Phase 31: patterns/map-reduce.ts unified module.

These tests verify that the unified map-reduce pattern handlers correctly:
1. onSubagentStart - injects mapper index and chunk context
2. onSubagentStop - tracks mapper completion, triggers reducer
3. onPreToolUse - injects chunk context to mappers
4. onStop - triggers reducer when all mappers done

The unified module implements MapReduce pattern coordination:
- Mapper registration (assign index, track chunks)
- Reducer triggering (when all mappers complete)
- Chunk context injection (what data each mapper processes)
- Progress tracking (mappers completed/pending)

Module path: .claude/hooks/src/patterns/map-reduce.ts

Tests are designed to FAIL initially (TDD approach) until Phase 31 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 31)
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
def map_reduce_module_path(hooks_dir: Path) -> Path:
    """Path to the unified map-reduce module."""
    return hooks_dir / "src" / "patterns" / "map-reduce.ts"


@pytest.fixture
def project_with_db() -> Generator[tuple[Path, str], None, None]:
    """Create project with coordination DB for map-reduce pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS mr_mappers (
                id TEXT PRIMARY KEY,
                mr_id TEXT NOT NULL,
                mapper_index INTEGER NOT NULL,
                agent_id TEXT,
                status TEXT DEFAULT 'pending',
                output TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mr_mappers
                ON mr_mappers(mr_id, status);
        """)
        conn.commit()
        conn.close()

        mr_id = "test-mr-unified"
        yield Path(tmpdir), mr_id


@pytest.fixture
def project_with_active_mappers() -> Generator[tuple[Path, str], None, None]:
    """Create project with active mappers (some completed)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS mr_mappers (
                id TEXT PRIMARY KEY,
                mr_id TEXT NOT NULL,
                mapper_index INTEGER NOT NULL,
                agent_id TEXT,
                status TEXT DEFAULT 'pending',
                output TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mr_mappers
                ON mr_mappers(mr_id, status);
        """)

        mr_id = "test-mr-active"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # 4 mappers total, 2 completed
        for i in range(4):
            mapper_id = f"mapper-{i}"
            status = "completed" if i < 2 else "pending"
            output = f"output-{i}" if i < 2 else None

            conn.execute(
                "INSERT INTO mr_mappers VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"mr-{i}", mr_id, i, mapper_id, status, output, now)
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), mr_id


@pytest.fixture
def project_with_all_mappers_done() -> Generator[tuple[Path, str], None, None]:
    """Create project with all mappers completed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS mr_mappers (
                id TEXT PRIMARY KEY,
                mr_id TEXT NOT NULL,
                mapper_index INTEGER NOT NULL,
                agent_id TEXT,
                status TEXT DEFAULT 'pending',
                output TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mr_mappers
                ON mr_mappers(mr_id, status);
        """)

        mr_id = "test-mr-complete"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # All 3 mappers completed
        for i in range(3):
            mapper_id = f"mapper-{i}"
            conn.execute(
                "INSERT INTO mr_mappers VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"mr-{i}", mr_id, i, mapper_id, "completed", f"result-{i}", now)
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), mr_id


# =============================================================================
# Module Existence Tests
# =============================================================================


class TestMapReduceModuleExists:
    """Tests for unified map-reduce module file existence."""

    def test_map_reduce_module_exists(self, map_reduce_module_path: Path) -> None:
        """Unified map-reduce.ts module exists at expected path."""
        assert map_reduce_module_path.exists(), (
            f"Unified map-reduce module not found: {map_reduce_module_path}. "
            "Create .claude/hooks/src/patterns/map-reduce.ts"
        )

    def test_patterns_directory_exists(self, hooks_dir: Path) -> None:
        """Patterns directory exists at expected path."""
        patterns_dir = hooks_dir / "src" / "patterns"
        assert patterns_dir.exists(), (
            f"Patterns directory not found: {patterns_dir}. "
            "Create .claude/hooks/src/patterns/"
        )


class TestMapReduceModuleExports:
    """Tests for map-reduce module exports."""

    def test_exports_on_subagent_start(self, map_reduce_module_path: Path) -> None:
        """Module exports onSubagentStart function."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        content = map_reduce_module_path.read_text()
        assert "export" in content and "onSubagentStart" in content, (
            "Module must export onSubagentStart function. "
            "Expected: export function onSubagentStart or export { onSubagentStart }"
        )

    def test_exports_on_subagent_stop(self, map_reduce_module_path: Path) -> None:
        """Module exports onSubagentStop function."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        content = map_reduce_module_path.read_text()
        assert "export" in content and "onSubagentStop" in content, (
            "Module must export onSubagentStop function. "
            "Expected: export function onSubagentStop or export { onSubagentStop }"
        )

    def test_exports_on_pre_tool_use(self, map_reduce_module_path: Path) -> None:
        """Module exports onPreToolUse function."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        content = map_reduce_module_path.read_text()
        assert "export" in content and "onPreToolUse" in content, (
            "Module must export onPreToolUse function. "
            "Expected: export function onPreToolUse or export { onPreToolUse }"
        )

    def test_exports_on_stop(self, map_reduce_module_path: Path) -> None:
        """Module exports onStop function."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        content = map_reduce_module_path.read_text()
        assert "export" in content and "onStop" in content, (
            "Module must export onStop function. "
            "Expected: export function onStop or export { onStop }"
        )


# =============================================================================
# onSubagentStart Handler Tests
# =============================================================================


class TestOnSubagentStartHandler:
    """Tests for onSubagentStart handler - registers mapper."""

    def test_injects_mapper_context(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onSubagentStart injects mapper index context message."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_db

        test_script = """
import { onSubagentStart } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'mapper-0',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "0"
        env["TOTAL_MAPPERS"] = "4"
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
            f"onSubagentStart should return 'continue'. Got: {output}"
        )

        # Should have mapper context message
        message = output.get("message", "")
        assert message, (
            "onSubagentStart should inject mapper context. "
            f"Got empty message. Output: {output}"
        )
        message_lower = message.lower()
        assert "mapper" in message_lower or "chunk" in message_lower or "index" in message_lower, (
            f"Message should mention mapper/chunk/index. Got: {message}"
        )

    def test_includes_mapper_index(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onSubagentStart includes mapper index in context."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_db

        test_script = """
import { onSubagentStart } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'mapper-2',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "2"
        env["TOTAL_MAPPERS"] = "4"
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

        # Should mention mapper index
        assert "2" in message or "mapper" in message.lower(), (
            f"Message should include mapper index. Got: {message}"
        )

    def test_handles_reducer_role(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onSubagentStart handles reducer role differently."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_db

        test_script = """
import { onSubagentStart } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'reducer-1',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "reducer"
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
            f"Should continue for reducer. Got: {output}"
        )

    def test_handles_missing_mr_id(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path
    ) -> None:
        """onSubagentStart handles missing MR_ID gracefully."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/map-reduce.ts';

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
        env.pop("MR_ID", None)  # No MR_ID
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
            f"Should continue when MR_ID not set. Got: {output}"
        )


# =============================================================================
# onSubagentStop Handler Tests
# =============================================================================


class TestOnSubagentStopHandler:
    """Tests for onSubagentStop handler - tracks mapper completion."""

    def test_records_mapper_completion(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onSubagentStop marks mapper as completed in database."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_db
        mapper_id = "mapper-completed"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/map-reduce.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{mapper_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "0"
        env["TOTAL_MAPPERS"] = "3"
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

        # Verify mapper completion was recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM mr_mappers WHERE mr_id = ? AND agent_id = ? AND status = 'completed'",
            (mr_id, mapper_id)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onSubagentStop should mark mapper as completed. Found {len(rows)} rows."
        )

    def test_triggers_reducer_when_all_done(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_active_mappers: tuple[Path, str]
    ) -> None:
        """onSubagentStop triggers reducer when last mapper completes."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_active_mappers

        # Complete the remaining 2 mappers (mapper-2, mapper-3)
        for i in range(2, 4):
            mapper_id = f"mapper-{i}"
            test_script = f"""
import {{ onSubagentStop }} from './patterns/map-reduce.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{mapper_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
            env = os.environ.copy()
            env["MR_ID"] = mr_id
            env["AGENT_ROLE"] = "mapper"
            env["MAPPER_INDEX"] = str(i)
            env["TOTAL_MAPPERS"] = "4"
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

            # On the last mapper, should inject reducer trigger message
            if i == 3:
                output = json.loads(result.stdout.strip())
                message = output.get("message", "")
                # Message is optional but if present should mention reduce phase
                if message:
                    message_lower = message.lower()
                    assert "reduce" in message_lower or "complete" in message_lower or "all" in message_lower, (
                        f"Reducer trigger message should mention reduce/complete. Got: {message}"
                    )

    def test_no_reducer_when_mappers_pending(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_active_mappers: tuple[Path, str]
    ) -> None:
        """onSubagentStop does not trigger reducer when mappers pending."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_active_mappers
        # Only 2 of 4 mappers done. Complete mapper-2 (still 1 pending)
        mapper_id = "mapper-2"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/map-reduce.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{mapper_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "2"
        env["TOTAL_MAPPERS"] = "4"
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

        # Should not trigger reducer
        if message:
            message_lower = message.lower()
            assert "reduce" not in message_lower or "pending" in message_lower, (
                f"Should not trigger reducer when mappers pending. Got: {message}"
            )


# =============================================================================
# onPreToolUse Handler Tests
# =============================================================================


class TestOnPreToolUseHandler:
    """Tests for onPreToolUse handler - injects chunk context."""

    def test_continues_normally(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path
    ) -> None:
        """onPreToolUse continues normally (no blocking needed)."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        test_script = """
import { onPreToolUse } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Read',
    tool_input: { file_path: '/some/file.txt' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["MR_ID"] = "test-mr"
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "0"
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
            f"Should continue. Got: {output}"
        )


# =============================================================================
# onStop Handler Tests
# =============================================================================


class TestOnStopHandler:
    """Tests for onStop handler - reducer trigger."""

    def test_blocks_when_mappers_pending(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_active_mappers: tuple[Path, str]
    ) -> None:
        """onStop blocks when some mappers haven't completed."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_active_mappers

        test_script = """
import { onStop } from './patterns/map-reduce.ts';

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
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "reducer"
        env["TOTAL_MAPPERS"] = "4"
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
            f"onStop should block when mappers pending. Got: {output}"
        )

        message = output.get("message", "")
        assert "wait" in message.lower() or "mapper" in message.lower() or "pending" in message.lower(), (
            f"Block message should mention waiting for mappers. Got: {message}"
        )

    def test_provides_results_when_all_done(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_all_mappers_done: tuple[Path, str]
    ) -> None:
        """onStop provides mapper results when all mappers completed."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_all_mappers_done

        test_script = """
import { onStop } from './patterns/map-reduce.ts';

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
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "reducer"
        env["TOTAL_MAPPERS"] = "3"
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
            f"onStop should continue when all mappers done. Got: {output}"
        )

        message = output.get("message", "")
        assert message, "Should provide mapper results summary"
        message_lower = message.lower()
        assert "mapper" in message_lower or "result" in message_lower or "reduce" in message_lower, (
            f"Message should mention mapper results. Got: {message}"
        )

    def test_prevents_infinite_loop(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_active_mappers: tuple[Path, str]
    ) -> None:
        """onStop continues when stop_hook_active is true (prevents loop)."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_active_mappers

        test_script = """
import { onStop } from './patterns/map-reduce.ts';

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
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "reducer"
        env["TOTAL_MAPPERS"] = "4"
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

    def test_continues_when_not_reducer(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path
    ) -> None:
        """onStop continues when not in a reducer role."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        test_script = """
import { onStop } from './patterns/map-reduce.ts';

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
        env.pop("MR_ID", None)  # No MR_ID
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
            f"onStop should continue when no MR_ID. Got: {output}"
        )


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurityValidation:
    """Tests for security validation in map-reduce handlers."""

    def test_validates_mr_id_format(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path
    ) -> None:
        """Handlers reject malicious MR_ID values."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/map-reduce.ts';

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
        env["MR_ID"] = "test; rm -rf /"  # Should be rejected
        env["AGENT_ROLE"] = "mapper"
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
            f"Should continue (reject) with invalid MR_ID. Got: {output}"
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_handles_missing_db_gracefully(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path
    ) -> None:
        """Handlers continue when database doesn't exist."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_script = """
import { onSubagentStop } from './patterns/map-reduce.ts';

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
            env["MR_ID"] = "test-mr"
            env["AGENT_ROLE"] = "mapper"
            env["MAPPER_INDEX"] = "0"
            env["TOTAL_MAPPERS"] = "3"
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


# =============================================================================
# onPostToolUse Handler Tests (TDD - Red Phase)
# =============================================================================


class TestOnPostToolUseHandler:
    """Tests for onPostToolUse handler - tracks mapper outputs.

    TDD Red Phase: These tests are designed to FAIL initially.
    The current onPostToolUse is a no-op that just returns 'continue'.

    Implementation should:
    1. Track Write tool outputs from mappers
    2. Store output in mr_mappers table
    3. Signal when all mappers have completed
    """

    def test_exports_on_post_tool_use(self, map_reduce_module_path: Path) -> None:
        """Module exports onPostToolUse function."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        content = map_reduce_module_path.read_text()
        assert "export" in content and "onPostToolUse" in content, (
            "Module must export onPostToolUse function. "
            "Expected: export function onPostToolUse or export { onPostToolUse }"
        )

    def test_records_mapper_output(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse records mapper output when Write tool completes."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_db
        mapper_id = "mapper-output-test"
        output_content = "Mapper 0 results: found 42 items"

        test_script = f"""
import {{ onPostToolUse }} from './patterns/map-reduce.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/tmp/mapper-0-output.txt',
        content: '{output_content}'
    }},
    tool_response: {{ success: true }}
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "0"
        env["TOTAL_MAPPERS"] = "3"
        env["AGENT_ID"] = mapper_id
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

        # Verify mapper output was recorded in database
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM mr_mappers WHERE mr_id = ? AND mapper_index = ?",
            (mr_id, 0)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onPostToolUse should record mapper output. Found {len(rows)} rows."
        )

        # Check that output was stored
        row = dict(rows[0])
        assert row.get("output") is not None, (
            f"Mapper output should be recorded. Got row: {row}"
        )

    def test_tracks_write_outputs_only(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse only tracks Write tool, not other tools."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_db

        test_script = """
import { onPostToolUse } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',  // Not Write
    tool_input: { command: 'ls' },
    tool_response: { output: 'file1.txt' }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "0"
        env["TOTAL_MAPPERS"] = "3"
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

        # Verify no mapper output was recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM mr_mappers WHERE mr_id = ? AND output IS NOT NULL",
            (mr_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"Should not record output for Bash tool. Found {count} outputs."
        )

    def test_triggers_reducer_when_all_mappers_done(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_active_mappers: tuple[Path, str]
    ) -> None:
        """onPostToolUse signals reducer when last mapper writes output."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_active_mappers

        # First, complete mapper-2 and mapper-3 outputs
        # (mapper-0 and mapper-1 are already completed in fixture)
        for i in range(2, 4):
            mapper_id = f"mapper-{i}"
            test_script = f"""
import {{ onPostToolUse }} from './patterns/map-reduce.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/tmp/mapper-{i}-output.txt',
        content: 'Mapper {i} results'
    }},
    tool_response: {{ success: true }}
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""
            env = os.environ.copy()
            env["MR_ID"] = mr_id
            env["AGENT_ROLE"] = "mapper"
            env["MAPPER_INDEX"] = str(i)
            env["TOTAL_MAPPERS"] = "4"
            env["AGENT_ID"] = mapper_id
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

            # On the last mapper, should inject reducer trigger message
            if i == 3:
                output = json.loads(result.stdout.strip())
                message = output.get("message", "")
                # Message should mention reduce phase or all mappers complete
                assert message, (
                    "onPostToolUse should signal when last mapper writes output. "
                    f"Got empty message. Output: {output}"
                )
                message_lower = message.lower()
                assert "reduce" in message_lower or "complete" in message_lower or "all" in message_lower, (
                    f"Should signal reducer when last mapper outputs. Got: {message}"
                )

    def test_validates_input_format(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse validates input format for security."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_db

        # Test with malformed tool_input
        test_script = """
import { onPostToolUse } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: null,  // Invalid - should be object
    tool_response: { success: true }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "0"
        env["TOTAL_MAPPERS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0, f"Handler crashed on invalid input: {result.stderr}"

        output = json.loads(result.stdout.strip())
        assert output.get("result") == "continue", (
            f"Should continue (gracefully handle) invalid input. Got: {output}"
        )

    def test_ignores_reducer_role(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse ignores Write from reducer (only tracks mappers)."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, mr_id = project_with_db

        test_script = """
import { onPostToolUse } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {
        file_path: '/tmp/reducer-output.txt',
        content: 'Final aggregated results'
    },
    tool_response: { success: true }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["MR_ID"] = mr_id
        env["AGENT_ROLE"] = "reducer"  # Not a mapper
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
            f"Should continue for reducer Write. Got: {output}"
        )

        # Verify no mapper output was recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM mr_mappers WHERE mr_id = ? AND output IS NOT NULL",
            (mr_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"Should not record output for reducer. Found {count} outputs."
        )

    def test_handles_missing_mr_id(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path
    ) -> None:
        """onPostToolUse handles missing MR_ID gracefully."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        test_script = """
import { onPostToolUse } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {
        file_path: '/tmp/output.txt',
        content: 'Some content'
    },
    tool_response: { success: true }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env.pop("MR_ID", None)  # No MR_ID
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
            f"Should continue when MR_ID not set. Got: {output}"
        )

    def test_validates_mr_id_security(
        self,
        hooks_dir: Path,
        map_reduce_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPostToolUse rejects malicious MR_ID values."""
        if not map_reduce_module_path.exists():
            pytest.skip("MapReduce module doesn't exist yet")

        project_dir, _ = project_with_db

        test_script = """
import { onPostToolUse } from './patterns/map-reduce.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {
        file_path: '/tmp/output.txt',
        content: 'Some content'
    },
    tool_response: { success: true }
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["MR_ID"] = "test$(whoami)"  # Shell injection attempt
        env["AGENT_ROLE"] = "mapper"
        env["MAPPER_INDEX"] = "0"
        env["TOTAL_MAPPERS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

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
            f"Should continue (reject) with invalid MR_ID. Got: {output}"
        )
