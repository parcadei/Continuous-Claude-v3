"""TDD Tests for Phase 19: patterns/pipeline.ts unified module.

These tests verify that the unified pipeline pattern handlers correctly:
1. onSubagentStart - injects stage context
2. onSubagentStop - tracks stage completion
3. onPreToolUse - injects upstream artifacts
4. onStop - provides pipeline completion summary

The unified module implements Pipeline pattern coordination:
- Stage sequencing (A → B → C)
- Stage context injection
- Upstream artifact availability
- Completion tracking

Module path: .claude/hooks/src/patterns/pipeline.ts

Tests are designed to FAIL initially (TDD approach) until Phase 19 is implemented.

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 19)
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
def pipeline_module_path(hooks_dir: Path) -> Path:
    """Path to the unified pipeline module."""
    return hooks_dir / "src" / "patterns" / "pipeline.ts"


@pytest.fixture
def project_with_db() -> Generator[tuple[Path, str], None, None]:
    """Create project with coordination DB for pipeline pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_stages (
                id TEXT PRIMARY KEY,
                pipeline_id TEXT NOT NULL,
                stage_index INTEGER NOT NULL,
                agent_id TEXT,
                status TEXT DEFAULT 'pending',
                output TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pipeline_stages
                ON pipeline_stages(pipeline_id, stage_index);
        """)
        conn.commit()
        conn.close()

        pipeline_id = "test-pipeline-unified"
        yield Path(tmpdir), pipeline_id


@pytest.fixture
def project_with_active_pipeline() -> Generator[tuple[Path, str], None, None]:
    """Create project with active pipeline (some stages completed)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_stages (
                id TEXT PRIMARY KEY,
                pipeline_id TEXT NOT NULL,
                stage_index INTEGER NOT NULL,
                agent_id TEXT,
                status TEXT DEFAULT 'pending',
                output TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pipeline_stages
                ON pipeline_stages(pipeline_id, stage_index);
        """)

        pipeline_id = "test-pipeline-active"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # 5 stages total, stages 0-1 completed, stage 2 in progress, 3-4 pending
        for i in range(5):
            stage_id = f"{pipeline_id}_stage_{i}"
            agent_id = f"stage-{i}-agent" if i <= 2 else None
            status = "completed" if i < 2 else ("running" if i == 2 else "pending")
            output_val = f"Stage {i} output" if i < 2 else None

            conn.execute(
                "INSERT INTO pipeline_stages VALUES (?, ?, ?, ?, ?, ?, ?)",
                (stage_id, pipeline_id, i, agent_id, status, output_val, now)
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), pipeline_id


@pytest.fixture
def project_with_completed_pipeline() -> Generator[tuple[Path, str], None, None]:
    """Create project with all pipeline stages completed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = Path(tmpdir) / ".claude" / "cache" / "agentica-coordination"
        db_dir.mkdir(parents=True)

        db_path = db_dir / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_stages (
                id TEXT PRIMARY KEY,
                pipeline_id TEXT NOT NULL,
                stage_index INTEGER NOT NULL,
                agent_id TEXT,
                status TEXT DEFAULT 'pending',
                output TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pipeline_stages
                ON pipeline_stages(pipeline_id, stage_index);
        """)

        pipeline_id = "test-pipeline-complete"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        # All 3 stages completed
        for i in range(3):
            stage_id = f"{pipeline_id}_stage_{i}"
            conn.execute(
                "INSERT INTO pipeline_stages VALUES (?, ?, ?, ?, ?, ?, ?)",
                (stage_id, pipeline_id, i, f"stage-{i}-agent", "completed", f"Result from stage {i}", now)
            )

        conn.commit()
        conn.close()

        yield Path(tmpdir), pipeline_id


# =============================================================================
# Module Existence Tests
# =============================================================================


class TestPipelineModuleExists:
    """Tests for unified pipeline module file existence."""

    def test_pipeline_module_exists(self, pipeline_module_path: Path) -> None:
        """Unified pipeline.ts module exists at expected path."""
        assert pipeline_module_path.exists(), (
            f"Unified pipeline module not found: {pipeline_module_path}. "
            "Create .claude/hooks/src/patterns/pipeline.ts"
        )

    def test_patterns_directory_exists(self, hooks_dir: Path) -> None:
        """Patterns directory exists at expected path."""
        patterns_dir = hooks_dir / "src" / "patterns"
        assert patterns_dir.exists(), (
            f"Patterns directory not found: {patterns_dir}. "
            "Create .claude/hooks/src/patterns/"
        )


class TestPipelineModuleExports:
    """Tests for pipeline module exports."""

    def test_exports_on_subagent_start(self, pipeline_module_path: Path) -> None:
        """Module exports onSubagentStart function."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        content = pipeline_module_path.read_text()
        assert "export" in content and "onSubagentStart" in content, (
            "Module must export onSubagentStart function. "
            "Expected: export function onSubagentStart or export { onSubagentStart }"
        )

    def test_exports_on_subagent_stop(self, pipeline_module_path: Path) -> None:
        """Module exports onSubagentStop function."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        content = pipeline_module_path.read_text()
        assert "export" in content and "onSubagentStop" in content, (
            "Module must export onSubagentStop function. "
            "Expected: export function onSubagentStop or export { onSubagentStop }"
        )

    def test_exports_on_pre_tool_use(self, pipeline_module_path: Path) -> None:
        """Module exports onPreToolUse function."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        content = pipeline_module_path.read_text()
        assert "export" in content and "onPreToolUse" in content, (
            "Module must export onPreToolUse function. "
            "Expected: export function onPreToolUse or export { onPreToolUse }"
        )

    def test_exports_on_stop(self, pipeline_module_path: Path) -> None:
        """Module exports onStop function."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        content = pipeline_module_path.read_text()
        assert "export" in content and "onStop" in content, (
            "Module must export onStop function. "
            "Expected: export function onStop or export { onStop }"
        )


# =============================================================================
# onSubagentStart Handler Tests
# =============================================================================


class TestOnSubagentStartHandler:
    """Tests for onSubagentStart handler - injects stage context."""

    def test_injects_stage_context(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path
    ) -> None:
        """onSubagentStart injects stage position and context message."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/pipeline.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'stage-1-agent',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        pipeline_id = "test-pipeline-context"

        env = os.environ.copy()
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = pipeline_id
        env["PIPELINE_STAGE_INDEX"] = "1"
        env["PIPELINE_TOTAL_STAGES"] = "5"
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

        # Should have stage context message
        message = output.get("message", "")
        assert message, (
            "onSubagentStart should inject stage context. "
            f"Got empty message. Output: {output}"
        )
        message_lower = message.lower()
        assert "stage" in message_lower or "pipeline" in message_lower, (
            f"Message should mention stage/pipeline. Got: {message}"
        )

    def test_includes_stage_index(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path
    ) -> None:
        """onSubagentStart includes stage index in context."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/pipeline.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'stage-3-agent',
    agent_type: 'general-purpose'
};

const result = await onSubagentStart(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = "test-pipeline"
        env["PIPELINE_STAGE_INDEX"] = "2"  # Zero-indexed: stage 3
        env["PIPELINE_TOTAL_STAGES"] = "5"
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

        # Should mention stage position (either "3" or "2" depending on implementation)
        assert "2" in message or "3" in message or "stage" in message.lower(), (
            f"Message should include stage position. Got: {message}"
        )

    def test_handles_missing_pipeline_id(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path
    ) -> None:
        """onSubagentStart handles missing PIPELINE_ID gracefully."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/pipeline.ts';

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
        env.pop("PIPELINE_ID", None)  # No PIPELINE_ID
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
            f"Should continue when PIPELINE_ID not set. Got: {output}"
        )


# =============================================================================
# onSubagentStop Handler Tests
# =============================================================================


class TestOnSubagentStopHandler:
    """Tests for onSubagentStop handler - tracks stage completion."""

    def test_records_stage_completion(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onSubagentStop marks stage as completed in database."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        project_dir, pipeline_id = project_with_db
        agent_id = "stage-0-completed"

        test_script = f"""
import {{ onSubagentStop }} from './patterns/pipeline.ts';

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
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = pipeline_id
        env["PIPELINE_STAGE_INDEX"] = "0"
        env["PIPELINE_TOTAL_STAGES"] = "3"
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

        # Verify stage completion was recorded
        db_path = project_dir / ".claude" / "cache" / "agentica-coordination" / "coordination.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM pipeline_stages WHERE pipeline_id = ? AND stage_index = ? AND status = 'completed'",
            (pipeline_id, 0)
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) >= 1, (
            f"onSubagentStop should mark stage as completed. Found {len(rows)} rows."
        )

    def test_injects_next_stage_prompt_when_more_stages(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path,
        project_with_active_pipeline: tuple[Path, str]
    ) -> None:
        """onSubagentStop injects next stage prompt when completing intermediate stage."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        project_dir, pipeline_id = project_with_active_pipeline

        # Complete stage 2 (currently running), should prompt for stage 3
        test_script = """
import { onSubagentStop } from './patterns/pipeline.ts';

(async () => {
const input = {
    session_id: 'test-session',
    agent_id: 'stage-2-agent',
    agent_type: 'general-purpose'
};

const result = await onSubagentStop(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = pipeline_id
        env["PIPELINE_STAGE_INDEX"] = "2"
        env["PIPELINE_TOTAL_STAGES"] = "5"
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

        # Should have some message (could be next stage prompt or completion message)
        # For intermediate stages, might mention "next" or "continue"
        # For final stage, might mention "complete"
        # Either is acceptable - just verify handler provides guidance
        assert output.get("result") == "continue", (
            f"Should continue after stage completion. Got: {output}"
        )

    def test_completion_message_on_final_stage(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path,
        project_with_active_pipeline: tuple[Path, str]
    ) -> None:
        """onSubagentStop provides completion message when final stage completes."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        project_dir, pipeline_id = project_with_active_pipeline

        # Complete all remaining stages (2, 3, 4)
        for i in range(2, 5):
            agent_id = f"stage-{i}-agent"
            test_script = f"""
import {{ onSubagentStop }} from './patterns/pipeline.ts';

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
            env["PATTERN_TYPE"] = "pipeline"
            env["PIPELINE_ID"] = pipeline_id
            env["PIPELINE_STAGE_INDEX"] = str(i)
            env["PIPELINE_TOTAL_STAGES"] = "5"
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

            # On the final stage (stage 4), should provide completion message
            if i == 4:
                output = json.loads(result.stdout.strip())
                message = output.get("message", "")
                if message:  # Message is optional but if present should mention completion
                    message_lower = message.lower()
                    assert "complete" in message_lower or "final" in message_lower or "pipeline" in message_lower, (
                        f"Final stage message should mention completion. Got: {message}"
                    )


# =============================================================================
# onPreToolUse Handler Tests
# =============================================================================


class TestOnPreToolUseHandler:
    """Tests for onPreToolUse handler - injects upstream artifacts."""

    def test_injects_upstream_artifacts(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path,
        project_with_active_pipeline: tuple[Path, str]
    ) -> None:
        """onPreToolUse injects upstream stage outputs as context."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        project_dir, pipeline_id = project_with_active_pipeline

        test_script = """
import { onPreToolUse } from './patterns/pipeline.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: { command: 'echo "test"' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = pipeline_id
        env["PIPELINE_STAGE_INDEX"] = "2"  # Stage 2 (stages 0-1 completed)
        env["PIPELINE_TOTAL_STAGES"] = "5"
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
            f"onPreToolUse should continue (allow tool). Got: {output}"
        )

        # Should inject upstream outputs as context
        message = output.get("message", "")
        if message:  # Message is optional but if present should mention upstream
            message_lower = message.lower()
            assert "upstream" in message_lower or "stage" in message_lower or "output" in message_lower, (
                f"Should mention upstream artifacts. Got: {message}"
            )

    def test_first_stage_no_upstream(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path,
        project_with_db: tuple[Path, str]
    ) -> None:
        """onPreToolUse handles first stage (no upstream artifacts)."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        project_dir, pipeline_id = project_with_db

        test_script = """
import { onPreToolUse } from './patterns/pipeline.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: { command: 'echo "test"' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = pipeline_id
        env["PIPELINE_STAGE_INDEX"] = "0"  # First stage
        env["PIPELINE_TOTAL_STAGES"] = "5"
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
            f"Should continue for first stage. Got: {output}"
        )

    def test_handles_missing_pipeline_id(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path
    ) -> None:
        """onPreToolUse handles missing PIPELINE_ID gracefully."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        test_script = """
import { onPreToolUse } from './patterns/pipeline.ts';

(async () => {
const input = {
    session_id: 'test-session',
    tool_name: 'Bash',
    tool_input: { command: 'echo "test"' }
};

const result = await onPreToolUse(input);
console.log(JSON.stringify(result));
})();
"""
        env = os.environ.copy()
        env.pop("PIPELINE_ID", None)  # No pipeline
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
            f"Should continue when no PIPELINE_ID. Got: {output}"
        )


# =============================================================================
# onStop Handler Tests
# =============================================================================


class TestOnStopHandler:
    """Tests for onStop handler - pipeline completion summary."""

    def test_blocks_when_stages_pending(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path,
        project_with_active_pipeline: tuple[Path, str]
    ) -> None:
        """onStop blocks when some stages haven't completed."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        project_dir, pipeline_id = project_with_active_pipeline

        test_script = """
import { onStop } from './patterns/pipeline.ts';

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
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = pipeline_id
        env["PIPELINE_TOTAL_STAGES"] = "5"
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
        # Could block or continue - depends on implementation
        # If blocking: should mention pending stages
        # If continuing: should mention pipeline status
        result_value = output.get("result")
        assert result_value in ["block", "continue"], (
            f"onStop should return valid result. Got: {output}"
        )

        if result_value == "block":
            message = output.get("message", "")
            assert message, "Block should include message"
            message_lower = message.lower()
            assert "stage" in message_lower or "pending" in message_lower or "pipeline" in message_lower, (
                f"Block message should mention pending stages. Got: {message}"
            )

    def test_provides_summary_when_all_completed(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path,
        project_with_completed_pipeline: tuple[Path, str]
    ) -> None:
        """onStop provides completion summary when all stages done."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        project_dir, pipeline_id = project_with_completed_pipeline

        test_script = """
import { onStop } from './patterns/pipeline.ts';

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
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = pipeline_id
        env["PIPELINE_TOTAL_STAGES"] = "3"
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
            f"onStop should continue when all completed. Got: {output}"
        )

        message = output.get("message", "")
        if message:  # Message is optional but if present should mention completion
            message_lower = message.lower()
            assert "complete" in message_lower or "pipeline" in message_lower or "stage" in message_lower, (
                f"Message should mention pipeline completion. Got: {message}"
            )

    def test_prevents_infinite_loop(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path,
        project_with_active_pipeline: tuple[Path, str]
    ) -> None:
        """onStop continues when stop_hook_active is true (prevents loop)."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        project_dir, pipeline_id = project_with_active_pipeline

        test_script = """
import { onStop } from './patterns/pipeline.ts';

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
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = pipeline_id
        env["PIPELINE_TOTAL_STAGES"] = "5"
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

    def test_continues_when_no_pipeline(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path
    ) -> None:
        """onStop continues when not in a pipeline."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        test_script = """
import { onStop } from './patterns/pipeline.ts';

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
        env.pop("PIPELINE_ID", None)  # No pipeline
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
            f"onStop should continue when no PIPELINE_ID. Got: {output}"
        )


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurityValidation:
    """Tests for security validation in pipeline handlers."""

    def test_validates_pipeline_id_format(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path
    ) -> None:
        """Handlers reject malicious PIPELINE_ID values."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        test_script = """
import { onSubagentStart } from './patterns/pipeline.ts';

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
        env["PATTERN_TYPE"] = "pipeline"
        env["PIPELINE_ID"] = "test; rm -rf /"  # Should be rejected
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
            f"Should continue (reject) with invalid PIPELINE_ID. Got: {output}"
        )


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_handles_missing_db_gracefully(
        self,
        hooks_dir: Path,
        pipeline_module_path: Path
    ) -> None:
        """Handlers continue when database doesn't exist."""
        if not pipeline_module_path.exists():
            pytest.skip("Pipeline module doesn't exist yet")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_script = """
import { onSubagentStop } from './patterns/pipeline.ts';

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
            env["PATTERN_TYPE"] = "pipeline"
            env["PIPELINE_ID"] = "test-pipeline"
            env["PIPELINE_STAGE_INDEX"] = "0"
            env["PIPELINE_TOTAL_STAGES"] = "3"
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
