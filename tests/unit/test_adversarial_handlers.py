"""TDD Tests for Phase 47: patterns/adversarial.ts unified module.

These tests verify that the unified adversarial pattern handlers correctly:
1. onSubagentStart - injects role context (advocate/adversary/judge)
2. onSubagentStop - tracks round completion
3. onPreToolUse - injects opponent's last argument as context
4. onPostToolUse - logs debate turn to database
5. onStop - captures verdict when debate completes

The unified module implements Adversarial pattern coordination:
- Role injection (advocate, adversary, judge)
- Round tracking (debate iterations)
- Argument injection (opponent's position)
- Debate history logging
- Verdict capture

Module path: .claude/hooks/src/patterns/adversarial.ts

Tests are designed to FAIL initially (TDD approach) until Phase 47 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 47)
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
def adversarial_module_path(hooks_dir: Path) -> Path:
    """Path to the unified adversarial module."""
    return hooks_dir / "src" / "patterns" / "adversarial.ts"


@pytest.fixture
def project_with_db() -> Generator[tuple[Path, str], None, None]:
    """Create project with coordination DB for adversarial pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS adversarial_rounds (
                id TEXT PRIMARY KEY,
                adv_id TEXT NOT NULL,
                round INTEGER NOT NULL,
                advocate_argument TEXT,
                adversary_argument TEXT,
                judge_verdict TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_adversarial_rounds
                ON adversarial_rounds(adv_id, round);
        """)
        conn.commit()
        conn.close()

        adv_id = "test-adversarial-unified"
        yield Path(tmpdir), adv_id


@pytest.fixture
def project_with_active_debate() -> Generator[tuple[Path, str], None, None]:
    """Create project with active debate (some rounds completed)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS adversarial_rounds (
                id TEXT PRIMARY KEY,
                adv_id TEXT NOT NULL,
                round INTEGER NOT NULL,
                advocate_argument TEXT,
                adversary_argument TEXT,
                judge_verdict TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_adversarial_rounds
                ON adversarial_rounds(adv_id, round);
        """)

        adv_id = "test-adversarial-active"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # 2 rounds completed out of 3 max
        # Use the same ID format as the implementation: {adv_id}_round_{round_num}
        for round_num in range(1, 3):
            conn.execute(
                """INSERT INTO adversarial_rounds
                   (id, adv_id, round, advocate_argument, adversary_argument, judge_verdict, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"{adv_id}_round_{round_num}",
                    adv_id,
                    round_num,
                    f"Advocate argument round {round_num}",
                    f"Adversary argument round {round_num}",
                    None,
                    now,
                ),
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), adv_id


@pytest.fixture
def project_with_complete_debate() -> Generator[tuple[Path, str], None, None]:
    """Create project with complete debate (all rounds done)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS adversarial_rounds (
                id TEXT PRIMARY KEY,
                adv_id TEXT NOT NULL,
                round INTEGER NOT NULL,
                advocate_argument TEXT,
                adversary_argument TEXT,
                judge_verdict TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_adversarial_rounds
                ON adversarial_rounds(adv_id, round);
        """)

        adv_id = "test-adversarial-complete"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # All 3 rounds completed
        # Use the same ID format as the implementation: {adv_id}_round_{round_num}
        for round_num in range(1, 4):
            conn.execute(
                """INSERT INTO adversarial_rounds
                   (id, adv_id, round, advocate_argument, adversary_argument, judge_verdict, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"{adv_id}_round_{round_num}",
                    adv_id,
                    round_num,
                    f"Advocate argument round {round_num}",
                    f"Adversary argument round {round_num}",
                    None,
                    now,
                ),
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), adv_id


# =============================================================================
# Test onSubagentStart Handler
# =============================================================================


class TestAdversarialOnSubagentStart:
    """Tests for onSubagentStart handler in adversarial pattern."""

    def test_module_exists(self, adversarial_module_path: Path):
        """Adversarial module file should exist."""
        assert adversarial_module_path.exists(), (
            f"Expected adversarial module at {adversarial_module_path}"
        )

    def test_advocate_role_injection(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onSubagentStart should inject advocate role context."""
        project_dir, adv_id = project_with_db

        test_script = f"""
import {{ onSubagentStart }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: 'advocate-agent',
}};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "adversarial"
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "1"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())

        assert output["result"] == "continue"
        assert "message" in output
        assert "advocate" in output["message"].lower()
        assert "round 1" in output["message"].lower()

    def test_adversary_role_injection(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onSubagentStart should inject adversary role context."""
        project_dir, adv_id = project_with_db

        test_script = f"""
import {{ onSubagentStart }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: 'adversary-agent',
}};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "adversarial"
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "adversary"
        env["ADVERSARIAL_ROUND"] = "1"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())

        assert output["result"] == "continue"
        assert "message" in output
        assert "adversary" in output["message"].lower()

    def test_judge_role_injection(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onSubagentStart should inject judge role context."""
        project_dir, adv_id = project_with_db

        test_script = f"""
import {{ onSubagentStart }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: 'judge-agent',
}};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "adversarial"
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "judge"
        env["ADVERSARIAL_ROUND"] = "3"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())

        assert output["result"] == "continue"
        assert "message" in output
        assert "judge" in output["message"].lower()

    def test_no_adv_id_continues_silently(self, hooks_dir: Path):
        """onSubagentStart should continue silently if no ADV_ID is set."""
        test_script = """
import { onSubagentStart } from './patterns/adversarial.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'some-agent',
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""

        env = os.environ.copy()
        # Remove ADV_ID if present
        env.pop("ADV_ID", None)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["result"] == "continue"
        assert "message" not in output or output.get("message") == ""


# =============================================================================
# Test onSubagentStop Handler
# =============================================================================


class TestAdversarialOnSubagentStop:
    """Tests for onSubagentStop handler in adversarial pattern."""

    def test_tracks_round_completion(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onSubagentStop should track when a round completes."""
        project_dir, adv_id = project_with_db

        test_script = f"""
import {{ onSubagentStop }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: 'advocate-agent',
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "adversarial"
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "1"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["result"] == "continue"

    def test_prompts_next_round(
        self, hooks_dir: Path, project_with_active_debate: tuple[Path, str]
    ):
        """onSubagentStop should prompt for next round when not at max."""
        project_dir, adv_id = project_with_active_debate

        test_script = f"""
import {{ onSubagentStop }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    agent_id: 'adversary-agent',
}};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "adversarial"
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "adversary"
        env["ADVERSARIAL_ROUND"] = "2"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["result"] == "continue"


# =============================================================================
# Test onPreToolUse Handler
# =============================================================================


class TestAdversarialOnPreToolUse:
    """Tests for onPreToolUse handler in adversarial pattern."""

    def test_injects_opponent_argument(
        self, hooks_dir: Path, project_with_active_debate: tuple[Path, str]
    ):
        """onPreToolUse should inject opponent's last argument for advocate."""
        project_dir, adv_id = project_with_active_debate

        test_script = f"""
import {{ onPreToolUse }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{ file_path: '/tmp/test.txt', content: 'test' }},
}};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "adversarial"
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "3"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["result"] == "continue"
        # May include opponent's argument in message


# =============================================================================
# Test onPostToolUse Handler
# =============================================================================


class TestAdversarialOnPostToolUse:
    """Tests for onPostToolUse handler in adversarial pattern."""

    def test_logs_debate_turn(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onPostToolUse should log debate turns to database."""
        project_dir, adv_id = project_with_db

        argument_content = "My argument is..."
        test_script = f"""
import {{ onPostToolUse }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{ file_path: '/tmp/argument.txt', content: '{argument_content}' }},
    tool_response: 'success'
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "1"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
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
        output = json.loads(result.stdout)
        assert output["result"] == "continue"


# =============================================================================
# Test onStop Handler
# =============================================================================


class TestAdversarialOnStop:
    """Tests for onStop handler in adversarial pattern."""

    def test_captures_verdict(
        self, hooks_dir: Path, project_with_complete_debate: tuple[Path, str]
    ):
        """onStop should capture final verdict when all rounds complete."""
        project_dir, adv_id = project_with_complete_debate

        test_script = f"""
import {{ onStop }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    stop_hook_active: false,
}};

const result = await onStop(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "adversarial"
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "judge"
        env["ADVERSARIAL_ROUND"] = "3"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["result"] == "continue"

    def test_prevents_infinite_loop(self, hooks_dir: Path):
        """onStop should prevent infinite loops with stop_hook_active flag."""
        test_script = """
import { onStop } from './patterns/adversarial.ts';

(async () => {
const input = {
    session_id: 'test-session',
    stop_hook_active: true,
};

const result = await onStop(input);
console.log(JSON.stringify(result));
})();
"""

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "adversarial"
        env["ADV_ID"] = "test-adv"
        env["AGENT_ROLE"] = "judge"

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            env=env,
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["result"] == "continue"


# =============================================================================
# Test Module Exports
# =============================================================================


class TestAdversarialModuleExports:
    """Tests that adversarial module exports all required handlers."""

    def test_exports_all_handlers(self, hooks_dir: Path):
        """Adversarial module should export all required handlers."""
        test_script = """
import * as adversarial from './patterns/adversarial.ts';
const exports = Object.keys(adversarial);
console.log(JSON.stringify(exports));
"""

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Import failed: {result.stderr}"
        exports = json.loads(result.stdout.strip())

        required_exports = [
            "onSubagentStart",
            "onSubagentStop",
            "onPreToolUse",
            "onPostToolUse",
            "onStop",
        ]

        for export in required_exports:
            assert export in exports, f"Missing export: {export}"


# =============================================================================
# Test onPostToolUse Handler - Exports
# =============================================================================


class TestAdversarialOnPostToolUseExports:
    """Tests for onPostToolUse handler exports."""

    def test_exports_on_post_tool_use(self, adversarial_module_path: Path):
        """Module exports onPostToolUse function."""
        if not adversarial_module_path.exists():
            pytest.skip("Adversarial module doesn't exist yet")

        content = adversarial_module_path.read_text()
        assert "export" in content and "onPostToolUse" in content, (
            "Module must export onPostToolUse function. "
            "Expected: export async function onPostToolUse or export { onPostToolUse }"
        )

    def test_on_post_tool_use_is_async_function(self, hooks_dir: Path):
        """onPostToolUse should be an async function."""
        test_script = """
import { onPostToolUse } from './patterns/adversarial.ts';
console.log(JSON.stringify({isAsync: onPostToolUse.constructor.name === 'AsyncFunction'}));
"""
        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Failed to check export: {result.stderr}"
        output = json.loads(result.stdout)
        assert output.get("isAsync") is True, (
            "onPostToolUse should be an async function"
        )


# =============================================================================
# Test onPostToolUse Handler - Debate Turn Recording
# =============================================================================


class TestAdversarialOnPostToolUseDebateTurns:
    """Tests for onPostToolUse handler - recording debate turns."""

    def test_records_advocate_debate_turn(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onPostToolUse records advocate argument when Write tool used."""
        project_dir, adv_id = project_with_db

        argument_content = "The evidence clearly supports our position because..."

        # Escape single quotes for JavaScript
        escaped_content = argument_content.replace("'", "\\'")
        test_script = f"""
import {{ onPostToolUse }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/tmp/advocate_argument.md',
        content: '{escaped_content}'
    }},
    tool_response: 'File written successfully'
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "1"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["result"] == "continue"

        # Verify debate turn was recorded in DB
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM adversarial_rounds WHERE adv_id = ? AND round = ?",
            (adv_id, 1)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onPostToolUse should record debate turn. Found {len(rows)} rows."
        )
        row = dict(rows[0])
        assert row["advocate_argument"] == argument_content, (
            f"Advocate argument not recorded correctly. Got: {row['advocate_argument']}"
        )

    def test_records_adversary_debate_turn(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onPostToolUse records adversary argument when Write tool used."""
        project_dir, adv_id = project_with_db

        argument_content = "I counter that the evidence is flawed because..."

        escaped_content = argument_content.replace("'", "\\'")
        test_script = f"""
import {{ onPostToolUse }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/tmp/adversary_argument.md',
        content: '{escaped_content}'
    }},
    tool_response: 'File written successfully'
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "adversary"
        env["ADVERSARIAL_ROUND"] = "2"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["result"] == "continue"

        # Verify adversary turn was recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM adversarial_rounds WHERE adv_id = ? AND round = ?",
            (adv_id, 2)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, "Adversary argument should be recorded"
        row = dict(rows[0])
        assert row["adversary_argument"] == argument_content, (
            f"Adversary argument not recorded correctly. Got: {row['adversary_argument']}"
        )


# =============================================================================
# Test onPostToolUse Handler - Judge Verdict Capture
# =============================================================================


class TestAdversarialOnPostToolUseJudgeVerdict:
    """Tests for onPostToolUse handler - capturing judge verdict."""

    def test_captures_judge_verdict(
        self, hooks_dir: Path, project_with_complete_debate: tuple[Path, str]
    ):
        """onPostToolUse captures judge verdict on final round."""
        project_dir, adv_id = project_with_complete_debate

        verdict_content = "After reviewing both positions, I rule in favor of the advocate."

        escaped_content = verdict_content.replace("'", "\\'")
        test_script = f"""
import {{ onPostToolUse }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/tmp/verdict.md',
        content: '{escaped_content}'
    }},
    tool_response: 'File written successfully'
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "judge"
        env["ADVERSARIAL_ROUND"] = "3"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["result"] == "continue"

        # Verify judge verdict was recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM adversarial_rounds WHERE adv_id = ? AND round = ?",
            (adv_id, 3)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, "Judge verdict should be recorded"
        row = dict(rows[0])
        assert row["judge_verdict"] == verdict_content, (
            f"Judge verdict not recorded correctly. Got: {row['judge_verdict']}"
        )

    def test_updates_existing_round_with_verdict(
        self, hooks_dir: Path, project_with_active_debate: tuple[Path, str]
    ):
        """onPostToolUse updates existing round record with judge verdict."""
        project_dir, adv_id = project_with_active_debate

        verdict_content = "The adversary made more compelling arguments."

        escaped_content = verdict_content.replace("'", "\\'")
        test_script = f"""
import {{ onPostToolUse }} from './patterns/adversarial.ts';

(async () => {{
const input = {{
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: {{
        file_path: '/tmp/verdict.md',
        content: '{escaped_content}'
    }},
    tool_response: 'File written successfully'
}};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
}})();
"""

        env = os.environ.copy()
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "judge"
        env["ADVERSARIAL_ROUND"] = "2"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Verify existing round was updated (not a new row)
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM adversarial_rounds WHERE adv_id = ? AND round = ?",
            (adv_id, 2)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 1, f"Should have exactly 1 row for round 2. Found {len(rows)}."
        row = dict(rows[0])
        # Original advocate/adversary should still be there
        assert row["advocate_argument"] is not None, "Advocate argument should be preserved"
        assert row["adversary_argument"] is not None, "Adversary argument should be preserved"
        assert row["judge_verdict"] == verdict_content, "Judge verdict should be added"


# =============================================================================
# Test onPostToolUse Handler - Input Validation
# =============================================================================


class TestAdversarialOnPostToolUseInputValidation:
    """Tests for onPostToolUse handler - input validation and security."""

    def test_validates_adv_id_format(self, hooks_dir: Path):
        """onPostToolUse rejects malicious ADV_ID values."""
        test_script = """
import { onPostToolUse } from './patterns/adversarial.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: { file_path: '/tmp/test.md', content: 'test' },
    tool_response: 'success'
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""

        env = os.environ.copy()
        # Try malicious ADV_ID with SQL injection attempt
        env["ADV_ID"] = "test'; DROP TABLE adversarial_rounds; --"
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "1"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"

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

        output = json.loads(result.stdout)
        assert output.get("result") == "continue", (
            f"Should continue (reject) with invalid ADV_ID. Got: {output}"
        )

    def test_validates_input_has_required_fields(self, hooks_dir: Path):
        """onPostToolUse handles missing tool_input gracefully."""
        test_script = """
import { onPostToolUse } from './patterns/adversarial.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    // Missing tool_input
    tool_response: 'success'
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""

        env = os.environ.copy()
        env["ADV_ID"] = "valid-adv-id"
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "1"

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

        output = json.loads(result.stdout)
        assert output.get("result") == "continue", (
            f"Should continue when tool_input missing. Got: {output}"
        )

    def test_only_tracks_write_tool(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onPostToolUse only tracks Write tool, ignores other tools."""
        project_dir, adv_id = project_with_db

        test_script = """
import { onPostToolUse } from './patterns/adversarial.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',  // Not Write
    tool_input: { command: "echo 'argument'" },
    tool_response: 'argument'
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""

        env = os.environ.copy()
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "1"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
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
        output = json.loads(result.stdout)
        assert output["result"] == "continue"

        # Verify no record was created
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM adversarial_rounds WHERE adv_id = ?",
            (adv_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, (
            f"Should not record debate turn for Bash tool. Found {count} rows."
        )

    def test_continues_silently_without_adv_id(self, hooks_dir: Path):
        """onPostToolUse continues silently when not in adversarial debate."""
        test_script = """
import { onPostToolUse } from './patterns/adversarial.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: { file_path: '/tmp/test.md', content: 'test' },
    tool_response: 'success'
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""

        # No ADV_ID set - not in adversarial debate
        env = {k: v for k, v in os.environ.items() if k != "ADV_ID"}

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Handler failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["result"] == "continue"
        assert "message" not in output or output.get("message") == "", (
            "Should not inject message when not in adversarial debate"
        )


# =============================================================================
# Test onPostToolUse Handler - Error Handling
# =============================================================================


class TestAdversarialOnPostToolUseErrorHandling:
    """Tests for onPostToolUse handler - error handling."""

    def test_handles_missing_db_gracefully(self, hooks_dir: Path):
        """onPostToolUse continues when database doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No database created
            test_script = """
import { onPostToolUse } from './patterns/adversarial.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: { file_path: '/tmp/test.md', content: 'test' },
    tool_response: 'success'
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""

            env = os.environ.copy()
            env["ADV_ID"] = "test-adv"
            env["AGENT_ROLE"] = "advocate"
            env["ADVERSARIAL_ROUND"] = "1"
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

            output = json.loads(result.stdout)
            assert output.get("result") == "continue", (
                f"Should continue when DB missing. Got: {output}"
            )

    def test_handles_empty_content_gracefully(
        self, hooks_dir: Path, project_with_db: tuple[Path, str]
    ):
        """onPostToolUse handles empty content in tool_input."""
        project_dir, adv_id = project_with_db

        test_script = """
import { onPostToolUse } from './patterns/adversarial.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Write',
    tool_input: { file_path: '/tmp/empty.md', content: '' },  // Empty content
    tool_response: 'success'
};

const result = await onPostToolUse(input);
console.log(JSON.stringify(result));
})();
"""

        env = os.environ.copy()
        env["ADV_ID"] = adv_id
        env["AGENT_ROLE"] = "advocate"
        env["ADVERSARIAL_ROUND"] = "1"
        env["ADVERSARIAL_MAX_ROUNDS"] = "3"
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir / "src"),
            timeout=30
        )

        assert result.returncode == 0, f"Handler crashed: {result.stderr}"

        output = json.loads(result.stdout)
        assert output.get("result") == "continue", (
            f"Should continue with empty content. Got: {output}"
        )
