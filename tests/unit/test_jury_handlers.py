"""TDD Tests for Phase 15: patterns/jury.ts unified module.

These tests verify that the unified jury pattern handlers correctly:
1. onSubagentStart - injects juror isolation context
2. onSubagentStop - tracks vote completion
3. onPreToolUse - blocks cross-juror data access if JURY_ISOLATION=strict
4. onStop - provides verdict summary when all jurors complete

The unified module implements Jury pattern coordination:
- Juror isolation (prevent cross-contamination)
- Vote tracking (count completed votes)
- Verdict aggregation context
- Consensus enforcement

Module path: .claude/hooks/src/patterns/jury.ts

Tests are designed to FAIL initially (TDD approach) until Phase 15 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 15)
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
def jury_module_path(hooks_dir: Path) -> Path:
    """Path to the unified jury module."""
    return hooks_dir / "src" / "patterns" / "jury.ts"


@pytest.fixture
def project_with_db() -> Generator[tuple[Path, str], None, None]:
    """Create project with coordination DB for jury pattern."""
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
                vote TEXT,
                created_at TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_jury_votes
                ON jury_votes(jury_id, completed);
        """)
        conn.commit()
        conn.close()

        jury_id = "test-jury-unified"
        yield Path(tmpdir), jury_id


@pytest.fixture
def project_with_active_jury() -> Generator[tuple[Path, str], None, None]:
    """Create project with active jury (some jurors completed)."""
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
                vote TEXT,
                created_at TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_jury_votes
                ON jury_votes(jury_id, completed);
        """)

        jury_id = "test-jury-active"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # 5 jurors total, 2 completed
        for i in range(5):
            juror_id = f"juror-{i+1}"
            completed = 1 if i < 2 else 0
            vote_value = f"vote-{i+1}" if completed else None

            conn.execute(
                "INSERT INTO jury_votes VALUES (?, ?, ?, ?, ?, ?)",
                (f"vote-{i}", jury_id, juror_id, vote_value, now, completed)
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), jury_id


@pytest.fixture
def project_with_all_votes() -> Generator[tuple[Path, str], None, None]:
    """Create project with all jurors completed."""
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
                vote TEXT,
                created_at TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_jury_votes
                ON jury_votes(jury_id, completed);
        """)

        jury_id = "test-jury-complete"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # All 3 jurors completed
        for i in range(3):
            juror_id = f"juror-{i+1}"
            conn.execute(
                "INSERT INTO jury_votes VALUES (?, ?, ?, ?, ?, ?)",
                (f"vote-{i}", jury_id, juror_id, f"yes" if i < 2 else "no", now, 1)
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), jury_id


# =============================================================================
# Module Existence Tests
# =============================================================================


class TestJuryModuleExists:
    """Tests for unified jury module file existence."""

    def test_jury_module_exists(self, jury_module_path: Path) -> None:
        """Unified jury.ts module exists at expected path."""
        assert jury_module_path.exists(), (
            f"Unified jury module not found: {jury_module_path}. "
            "Create .claude/hooks/src/patterns/jury.ts"
        )

    def test_patterns_directory_exists(self, hooks_dir: Path) -> None:
        """Patterns directory exists at expected path."""
        patterns_dir = hooks_dir / "src" / "patterns"
        assert patterns_dir.exists(), (
            f"Patterns directory not found: {patterns_dir}. "
            "Create .claude/hooks/src/patterns/"
        )


class TestJuryModuleExports:
    """Tests for jury module exports."""

    def test_exports_on_subagent_start(self, jury_module_path: Path) -> None:
        """Module exports onSubagentStart function."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        content = jury_module_path.read_text()
        assert "export" in content and "onSubagentStart" in content, (
            "Module must export onSubagentStart function. "
            "Expected: export function onSubagentStart or export { onSubagentStart }"
        )

    def test_exports_on_subagent_stop(self, jury_module_path: Path) -> None:
        """Module exports onSubagentStop function."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        content = jury_module_path.read_text()
        assert "export" in content and "onSubagentStop" in content, (
            "Module must export onSubagentStop function. "
            "Expected: export function onSubagentStop or export { onSubagentStop }"
        )

    def test_exports_on_pre_tool_use(self, jury_module_path: Path) -> None:
        """Module exports onPreToolUse function."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        content = jury_module_path.read_text()
        assert "export" in content and "onPreToolUse" in content, (
            "Module must export onPreToolUse function. "
            "Expected: export function onPreToolUse or export { onPreToolUse }"
        )

    def test_exports_on_stop(self, jury_module_path: Path) -> None:
        """Module exports onStop function."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        content = jury_module_path.read_text()
        assert "export" in content and "onStop" in content, (
            "Module must export onStop function. "
            "Expected: export function onStop or export { onStop }"
        )


# =============================================================================
# onSubagentStart Handler Tests
# =============================================================================


class TestOnSubagentStartHandler:
    """Tests for onSubagentStart handler - injects juror isolation context."""

    def test_injects_isolation_context(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """onSubagentStart injects juror isolation context message."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/jury.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'juror-1',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        jury_id = "test-jury-isolation"

        env = os.environ.copy()
        env["JURY_ID"] = jury_id
        env["JUROR_INDEX"] = "0"
        env["TOTAL_JURORS"] = "5"
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

        # Should have isolation message
        message = output.get("message", "")
        assert message, (
            "onSubagentStart should inject isolation context. "
            f"Got empty message. Output: {output}"
        )
        message_lower = message.lower()
        assert "juror" in message_lower or "isolation" in message_lower or "independent" in message_lower, (
            f"Message should mention juror isolation. Got: {message}"
        )

    def test_includes_juror_index(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """onSubagentStart includes juror index in context."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/jury.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'juror-3',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["JURY_ID"] = "test-jury"
        env["JUROR_INDEX"] = "2"  # Zero-indexed: juror 3
        env["TOTAL_JURORS"] = "5"
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

        # Should mention juror position (either "3" or "2" depending on implementation)
        assert "2" in message or "3" in message or "juror" in message.lower(), (
            f"Message should include juror position. Got: {message}"
        )

    def test_handles_missing_jury_id(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """onSubagentStart handles missing JURY_ID gracefully."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/jury.ts';

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
        env.pop("JURY_ID", None)  # No JURY_ID
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
            f"Should continue when JURY_ID not set. Got: {output}"
        )


# =============================================================================
# onSubagentStop Handler Tests
# =============================================================================


class TestOnSubagentStopHandler:
    """Tests for onSubagentStop handler - tracks vote completion."""

    def test_records_vote_completion(
        self,
        hooks_dir: Path,
        jury_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onSubagentStop marks juror as completed in database."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        project_dir, jury_id = project_with_db
        juror_id = "juror-completed"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/jury.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{juror_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["JURY_ID"] = jury_id
        env["JUROR_INDEX"] = "0"
        env["TOTAL_JURORS"] = "3"
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

        # Verify vote completion was recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM jury_votes WHERE jury_id = ? AND juror_id = ? AND completed = 1",
            (jury_id, juror_id)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onSubagentStop should mark juror as completed. Found {len(rows)} rows."
        )

    def test_injects_verdict_prompt_when_all_done(
        self,
        hooks_dir: Path,
        jury_module_path: Path,
        project_with_active_jury: tuple[Path, str]
    ) -> None:
        """onSubagentStop injects verdict prompt when last juror completes."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        project_dir, jury_id = project_with_active_jury

        # Complete the remaining 3 jurors (juror-3, juror-4, juror-5)
        # Indices 2, 3, 4 correspond to juror-3, juror-4, juror-5
        for i in range(2, 5):
            juror_id = f"juror-{i+1}"
            test_script = f"""
import {{ onSubagentStop }} from './patterns/jury.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{juror_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
            env = os.environ.copy()
            env["JURY_ID"] = jury_id
            env["JUROR_INDEX"] = str(i)
            env["TOTAL_JURORS"] = "5"
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

            # On the last juror (juror-5), should inject verdict message
            if i == 4:
                output = json.loads(result.stdout.strip())
                message = output.get("message", "")
                assert message, (
                    "onSubagentStop should inject verdict message when all jurors complete. "
                    f"Got empty message. Output: {output}"
                )
                message_lower = message.lower()
                assert "verdict" in message_lower or "consensus" in message_lower or "all" in message_lower, (
                    f"Verdict message should mention consensus/verdict. Got: {message}"
                )

    def test_no_verdict_when_jurors_pending(
        self,
        hooks_dir: Path,
        jury_module_path: Path,
        project_with_active_jury: tuple[Path, str]
    ) -> None:
        """onSubagentStop does not inject verdict when jurors still pending."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        project_dir, jury_id = project_with_active_jury
        # Only 2 of 5 jurors done. Complete juror-3 (still 2 pending)
        juror_id = "juror-3"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/jury.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: '{juror_id}',
    agent_type: 'general-purpose'
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""
        env = os.environ.copy()
        env["JURY_ID"] = jury_id
        env["JUROR_INDEX"] = "2"
        env["TOTAL_JURORS"] = "5"
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
            assert "verdict" not in message_lower and "all" not in message_lower, (
                f"Should not inject verdict when jurors pending. Got: {message}"
            )


# =============================================================================
# onPreToolUse Handler Tests
# =============================================================================


class TestOnPreToolUseHandler:
    """Tests for onPreToolUse handler - blocks cross-juror data access."""

    def test_allows_tools_when_no_isolation(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """onPreToolUse allows all tools when JURY_ISOLATION not set."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        test_script = """
import { onPreToolUse } from './patterns/jury.ts';

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
        env["JURY_ID"] = "test-jury"
        env.pop("JURY_ISOLATION", None)  # No isolation mode set
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
            f"Should continue (allow) when no isolation set. Got: {output}"
        )

    def test_blocks_read_when_strict_isolation(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """onPreToolUse blocks Read tool when JURY_ISOLATION=strict."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        test_script = """
import { onPreToolUse } from './patterns/jury.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Read',
    tool_input: { file_path: '/shared/jury-notes.txt' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["JURY_ID"] = "test-jury-strict"
        env["JURY_ISOLATION"] = "strict"
        env["JUROR_INDEX"] = "0"
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
        assert output.get("result") == "block", (
            f"Should block Read when JURY_ISOLATION=strict. Got: {output}"
        )

        message = output.get("message", "")
        assert "isolation" in message.lower() or "independent" in message.lower(), (
            f"Block message should mention isolation. Got: {message}"
        )

    def test_allows_safe_tools_in_strict_mode(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """onPreToolUse allows safe tools even in strict isolation."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        test_script = """
import { onPreToolUse } from './patterns/jury.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',  // Safe tool
    tool_input: { command: 'echo "test"' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["JURY_ID"] = "test-jury-strict"
        env["JURY_ISOLATION"] = "strict"
        env["JUROR_INDEX"] = "0"
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
            f"Should allow safe tools in strict mode. Got: {output}"
        )


# =============================================================================
# onStop Handler Tests
# =============================================================================


class TestOnStopHandler:
    """Tests for onStop handler - verdict summary."""

    def test_blocks_when_votes_pending(
        self,
        hooks_dir: Path,
        jury_module_path: Path,
        project_with_active_jury: tuple[Path, str]
    ) -> None:
        """onStop blocks when some jurors haven't voted."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        project_dir, jury_id = project_with_active_jury

        test_script = """
import { onStop } from './patterns/jury.ts';

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
        env["JURY_ID"] = jury_id
        env["TOTAL_JURORS"] = "5"
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
            f"onStop should block when votes pending. Got: {output}"
        )

        message = output.get("message", "")
        assert "wait" in message.lower() or "juror" in message.lower() or "vote" in message.lower(), (
            f"Block message should mention waiting for votes. Got: {message}"
        )

    def test_provides_verdict_when_all_voted(
        self,
        hooks_dir: Path,
        jury_module_path: Path,
        project_with_all_votes: tuple[Path, str]
    ) -> None:
        """onStop provides verdict summary when all jurors voted."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        project_dir, jury_id = project_with_all_votes

        test_script = """
import { onStop } from './patterns/jury.ts';

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
        env["JURY_ID"] = jury_id
        env["TOTAL_JURORS"] = "3"
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
            f"onStop should continue when all voted. Got: {output}"
        )

        message = output.get("message", "")
        assert message, "Should provide verdict summary"
        message_lower = message.lower()
        assert "verdict" in message_lower or "vote" in message_lower or "consensus" in message_lower, (
            f"Message should mention verdict/votes. Got: {message}"
        )

    def test_prevents_infinite_loop(
        self,
        hooks_dir: Path,
        jury_module_path: Path,
        project_with_active_jury: tuple[Path, str]
    ) -> None:
        """onStop continues when stop_hook_active is true (prevents loop)."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        project_dir, jury_id = project_with_active_jury

        test_script = """
import { onStop } from './patterns/jury.ts';

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
        env["JURY_ID"] = jury_id
        env["TOTAL_JURORS"] = "5"
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

    def test_continues_when_no_jury(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """onStop continues when not in a jury."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        test_script = """
import { onStop } from './patterns/jury.ts';

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
        env.pop("JURY_ID", None)  # No jury
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
            f"onStop should continue when no JURY_ID. Got: {output}"
        )


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurityValidation:
    """Tests for security validation in jury handlers."""

    def test_validates_jury_id_format(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """Handlers reject malicious JURY_ID values."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/jury.ts';

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
        env["JURY_ID"] = "test; rm -rf /"  # Should be rejected
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
            f"Should continue (reject) with invalid JURY_ID. Got: {output}"
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_handles_missing_db_gracefully(
        self,
        hooks_dir: Path,
        jury_module_path: Path
    ) -> None:
        """Handlers continue when database doesn't exist."""
        if not jury_module_path.exists():
            pytest.skip("Jury module doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_script = """
import { onSubagentStop } from './patterns/jury.ts';

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
            env["JURY_ID"] = "test-jury"
            env["JUROR_INDEX"] = "0"
            env["TOTAL_JURORS"] = "3"
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
