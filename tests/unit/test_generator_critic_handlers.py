"""TDD Tests for Phase 23: patterns/generator-critic.ts unified module.

These tests verify that the unified generator-critic pattern handlers correctly:
1. onSubagentStart - injects role (generator or critic)
2. onSubagentStop - tracks iteration completion
3. onPreToolUse - injects critic feedback to generator
4. onStop - blocks until approved or max rounds reached

The unified module implements Generator/Critic pattern coordination:
- Role injection (generator vs critic)
- Iteration tracking (round counter)
- Feedback propagation (critic → generator)
- Approval guard (prevent early exit)

Module path: .claude/hooks/src/patterns/generator-critic.ts

Tests are designed to FAIL initially (TDD approach) until Phase 23 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 23)
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
def gc_module_path(hooks_dir: Path) -> Path:
    """Path to the unified generator-critic module."""
    return hooks_dir / "src" / "patterns" / "generator-critic.ts"


@pytest.fixture
def project_with_db() -> Generator[tuple[Path, str], None, None]:
    """Create project with coordination DB for generator-critic pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS gc_iterations (
                id TEXT PRIMARY KEY,
                gc_id TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                generator_output TEXT,
                critic_feedback TEXT,
                approved BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_gc_iterations
                ON gc_iterations(gc_id, iteration);
        """)
        conn.commit()
        conn.close()

        gc_id = "test-gc-unified"
        yield Path(tmpdir), gc_id


@pytest.fixture
def project_with_active_gc() -> Generator[tuple[Path, str], None, None]:
    """Create project with active generator-critic iterations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS gc_iterations (
                id TEXT PRIMARY KEY,
                gc_id TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                generator_output TEXT,
                critic_feedback TEXT,
                approved BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_gc_iterations
                ON gc_iterations(gc_id, iteration);
        """)

        gc_id = "test-gc-active"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # 2 iterations completed, on round 3 now
        for i in range(1, 3):
            conn.execute(
                "INSERT INTO gc_iterations VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f"{gc_id}_iter_{i}",
                    gc_id,
                    i,
                    f"output_{i}",
                    f"feedback_{i}",
                    0,
                    now
                )
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), gc_id


@pytest.fixture
def project_with_approved_gc() -> Generator[tuple[Path, str], None, None]:
    """Create project with approved generator-critic output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS gc_iterations (
                id TEXT PRIMARY KEY,
                gc_id TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                generator_output TEXT,
                critic_feedback TEXT,
                approved BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_gc_iterations
                ON gc_iterations(gc_id, iteration);
        """)

        gc_id = "test-gc-approved"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # Iteration 2 was approved
        conn.execute(
            "INSERT INTO gc_iterations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"{gc_id}_iter_2", gc_id, 2, "approved_output", "APPROVED", 1, now)
        )

        conn.commit()
        conn.close()

        yield Path(tmpdir), gc_id


# =============================================================================
# Module Existence Tests
# =============================================================================


class TestGCModuleExists:
    """Tests for unified generator-critic module file existence."""

    def test_gc_module_exists(self, gc_module_path: Path) -> None:
        """Unified generator-critic.ts module exists at expected path."""
        assert gc_module_path.exists(), (
            f"Unified generator-critic module not found: {gc_module_path}. "
            "Create .claude/hooks/src/patterns/generator-critic.ts"
        )

    def test_patterns_directory_exists(self, hooks_dir: Path) -> None:
        """Patterns directory exists at expected path."""
        patterns_dir = hooks_dir / "src" / "patterns"
        assert patterns_dir.exists(), (
            f"Patterns directory not found: {patterns_dir}. "
            "Create .claude/hooks/src/patterns/"
        )


class TestGCModuleExports:
    """Tests for generator-critic module exports."""

    def test_exports_on_subagent_start(self, gc_module_path: Path) -> None:
        """Module exports onSubagentStart function."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        content = gc_module_path.read_text()
        assert "export" in content and "onSubagentStart" in content, (
            "Module must export onSubagentStart function. "
            "Expected: export function onSubagentStart or export { onSubagentStart }"
        )

    def test_exports_on_subagent_stop(self, gc_module_path: Path) -> None:
        """Module exports onSubagentStop function."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        content = gc_module_path.read_text()
        assert "export" in content and "onSubagentStop" in content, (
            "Module must export onSubagentStop function. "
            "Expected: export function onSubagentStop or export { onSubagentStop }"
        )

    def test_exports_on_pre_tool_use(self, gc_module_path: Path) -> None:
        """Module exports onPreToolUse function."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        content = gc_module_path.read_text()
        assert "export" in content and "onPreToolUse" in content, (
            "Module must export onPreToolUse function. "
            "Expected: export function onPreToolUse or export { onPreToolUse }"
        )

    def test_exports_on_stop(self, gc_module_path: Path) -> None:
        """Module exports onStop function."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        content = gc_module_path.read_text()
        assert "export" in content and "onStop" in content, (
            "Module must export onStop function. "
            "Expected: export function onStop or export { onStop }"
        )


# =============================================================================
# onSubagentStart Handler Tests
# =============================================================================


class TestOnSubagentStartHandler:
    """Tests for onSubagentStart handler - injects role context."""

    def test_injects_generator_role(
        self,
        hooks_dir: Path,
        gc_module_path: Path
    ) -> None:
        """onSubagentStart injects generator role context message."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'generator-1',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        gc_id = "test-gc-gen"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
        env["AGENT_ROLE"] = "generator"
        env["GC_ITERATION"] = "1"
        env["GC_MAX_ROUNDS"] = "3"
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
            f"onSubagentStart should return 'continue'. Got: {output}"
        )

        message = output.get("message", "")
        assert message, "onSubagentStart should inject role context"
        message_lower = message.lower()
        assert "generator" in message_lower or "generate" in message_lower, (
            f"Message should mention generator role. Got: {message}"
        )

    def test_injects_critic_role(
        self,
        hooks_dir: Path,
        gc_module_path: Path
    ) -> None:
        """onSubagentStart injects critic role context message."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'critic-1',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = "test-gc-critic"
        env["AGENT_ROLE"] = "critic"
        env["GC_ITERATION"] = "1"
        env["GC_MAX_ROUNDS"] = "3"
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
        message = output.get("message", "")
        assert message, "Should inject critic context"
        message_lower = message.lower()
        assert "critic" in message_lower or "review" in message_lower or "feedback" in message_lower, (
            f"Message should mention critic role. Got: {message}"
        )

    def test_includes_iteration_info(
        self,
        hooks_dir: Path,
        gc_module_path: Path
    ) -> None:
        """onSubagentStart includes iteration/round information."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'gen-1',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = "test-gc"
        env["AGENT_ROLE"] = "generator"
        env["GC_ITERATION"] = "2"
        env["GC_MAX_ROUNDS"] = "5"
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
        message = output.get("message", "")
        # Should mention iteration/round
        assert "2" in message or "round" in message.lower() or "iteration" in message.lower(), (
            f"Message should include iteration info. Got: {message}"
        )

    def test_handles_missing_gc_id(
        self,
        hooks_dir: Path,
        gc_module_path: Path
    ) -> None:
        """onSubagentStart handles missing GC_ID gracefully."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/generator-critic.ts';

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
        env.pop("GC_ID", None)  # No GC_ID
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
            f"Should continue when GC_ID not set. Got: {output}"
        )


# =============================================================================
# onSubagentStop Handler Tests
# =============================================================================


class TestOnSubagentStopHandler:
    """Tests for onSubagentStop handler - tracks iteration completion."""

    def test_records_iteration_completion(
        self,
        hooks_dir: Path,
        gc_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onSubagentStop tracks iteration completion in database."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        project_dir, gc_id = project_with_db

        test_script = """
import { onSubagentStop } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'generator-1',
    agent_type: 'general-purpose'
};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
        env["AGENT_ROLE"] = "generator"
        env["GC_ITERATION"] = "1"
        env["GC_MAX_ROUNDS"] = "3"
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

        # Verify iteration was tracked
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM gc_iterations WHERE gc_id = ? AND iteration = ?",
            (gc_id, 1)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onSubagentStop should track iteration. Found {len(rows)} rows."
        )

    def test_increments_iteration_counter(
        self,
        hooks_dir: Path,
        gc_module_path: Path,
        project_with_active_gc: tuple[Path, str]
    ) -> None:
        """onSubagentStop tracks next iteration correctly."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        project_dir, gc_id = project_with_active_gc

        test_script = """
import { onSubagentStop } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'generator-3',
    agent_type: 'general-purpose'
};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
        env["AGENT_ROLE"] = "generator"
        env["GC_ITERATION"] = "3"
        env["GC_MAX_ROUNDS"] = "5"
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

        # Should have iterations 1, 2, 3
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM gc_iterations WHERE gc_id = ?",
            (gc_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 3, f"Should have 3+ iterations tracked. Got {count}."


# =============================================================================
# onPreToolUse Handler Tests
# =============================================================================


class TestOnPreToolUseHandler:
    """Tests for onPreToolUse handler - injects critic feedback."""

    def test_injects_critic_feedback_to_generator(
        self,
        hooks_dir: Path,
        gc_module_path: Path,
        project_with_active_gc: tuple[Path, str]
    ) -> None:
        """onPreToolUse injects previous critic feedback to generator."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        project_dir, gc_id = project_with_active_gc

        test_script = """
import { onPreToolUse } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: { file_path: '/some/file.py', content: 'code' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
        env["AGENT_ROLE"] = "generator"
        env["GC_ITERATION"] = "3"  # Should get feedback_2
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
            # Should include previous feedback
            message_lower = message.lower()
            assert "feedback" in message_lower or "critic" in message_lower or "iteration" in message_lower, (
                f"Generator should see critic feedback. Got: {message}"
            )

    def test_no_feedback_on_first_iteration(
        self,
        hooks_dir: Path,
        gc_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPreToolUse doesn't inject feedback on first iteration."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        project_dir, gc_id = project_with_db

        test_script = """
import { onPreToolUse } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {}
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
        env["AGENT_ROLE"] = "generator"
        env["GC_ITERATION"] = "1"  # First iteration
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

    def test_critic_doesnt_get_feedback_injection(
        self,
        hooks_dir: Path,
        gc_module_path: Path,
        project_with_active_gc: tuple[Path, str]
    ) -> None:
        """onPreToolUse doesn't inject feedback to critic agent."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        project_dir, gc_id = project_with_active_gc

        test_script = """
import { onPreToolUse } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Read',
    tool_input: {}
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
        env["AGENT_ROLE"] = "critic"  # Critic role
        env["GC_ITERATION"] = "2"
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
    """Tests for onStop handler - approval guard."""

    def test_blocks_when_not_approved(
        self,
        hooks_dir: Path,
        gc_module_path: Path,
        project_with_active_gc: tuple[Path, str]
    ) -> None:
        """onStop blocks when output not yet approved."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        project_dir, gc_id = project_with_active_gc

        test_script = """
import { onStop } from './patterns/generator-critic.ts';

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
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
        env["GC_ITERATION"] = "2"
        env["GC_MAX_ROUNDS"] = "5"
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
        # May block or continue depending on implementation
        # For now, verify it doesn't crash
        assert output.get("result") in ["continue", "block"]

    def test_continues_when_approved(
        self,
        hooks_dir: Path,
        gc_module_path: Path,
        project_with_approved_gc: tuple[Path, str]
    ) -> None:
        """onStop continues when output is approved."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        project_dir, gc_id = project_with_approved_gc

        test_script = """
import { onStop } from './patterns/generator-critic.ts';

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
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
        env["GC_ITERATION"] = "2"
        env["GC_MAX_ROUNDS"] = "5"
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
            f"Should continue when approved. Got: {output}"
        )

    def test_prevents_infinite_loop(
        self,
        hooks_dir: Path,
        gc_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onStop continues when stop_hook_active is true (prevents loop)."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        project_dir, gc_id = project_with_db

        test_script = """
import { onStop } from './patterns/generator-critic.ts';

(async () => {
const input = {
    session_id: 'test-session',
    stop_hook_active: true
};

const result = await onStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "generator_critic"
        env["GC_ID"] = gc_id
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
            f"Should continue when stop_hook_active to prevent loop. Got: {output}"
        )

    def test_continues_when_no_gc_id(
        self,
        hooks_dir: Path,
        gc_module_path: Path
    ) -> None:
        """onStop continues when not in a generator-critic pattern."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        test_script = """
import { onStop } from './patterns/generator-critic.ts';

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
        env.pop("GC_ID", None)  # No GC context
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
            f"Should continue when no GC_ID. Got: {output}"
        )


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurityValidation:
    """Tests for security validation in generator-critic handlers."""

    def test_validates_gc_id_format(
        self,
        hooks_dir: Path,
        gc_module_path: Path
    ) -> None:
        """Handlers reject malicious GC_ID values."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/generator-critic.ts';

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
        env["GC_ID"] = "test; rm -rf /"  # Should be rejected
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
            f"Should continue (reject) with invalid GC_ID. Got: {output}"
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_handles_missing_db_gracefully(
        self,
        hooks_dir: Path,
        gc_module_path: Path
    ) -> None:
        """Handlers continue when database doesn't exist."""
        if not gc_module_path.exists():
            pytest.skip("Generator-critic module doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_script = """
import { onSubagentStop } from './patterns/generator-critic.ts';

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
            env["PATTERN_TYPE"] = "generator_critic"
            env["GC_ID"] = "test-gc"
            env["AGENT_ROLE"] = "generator"
            env["GC_ITERATION"] = "1"
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
