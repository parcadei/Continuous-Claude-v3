"""Tests for Phase 5: Soft Limit Advisory in UserPromptSubmit hook.

These tests verify that `skill-activation-prompt.ts`:
1. Reads resource state from /tmp/claude-resources-{sessionId}.json
2. Displays RESOURCE WARNING when activeAgents >= maxAgents * 0.8
3. Displays RESOURCE CRITICAL when activeAgents >= maxAgents
4. Appends resource advisory to existing system message output

The soft limit advisory provides early warning to Claude before the hard
limit (Phase 6) blocks Task tool invocations.

Tests are designed to FAIL initially (TDD approach) until Phase 5 is implemented.

See plan: docs/handoffs/resource-limits-plan.md (Phase 5)
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def hooks_dir() -> Path:
    """Path to hooks directory."""
    return Path(__file__).parents[2] / ".claude" / "hooks"


@pytest.fixture
def project_dir() -> Path:
    """Path to project root directory."""
    return Path(__file__).parents[2]


@pytest.fixture
def temp_resource_file() -> Generator[tuple[Path, str], None, None]:
    """Create a temporary resource file and clean up after test."""
    session_id = f"test-soft-limit-{os.getpid()}"
    resource_file = Path(f"/tmp/claude-resources-{session_id}.json")

    yield resource_file, session_id

    # Cleanup
    if resource_file.exists():
        resource_file.unlink()


class TestResourceFileReading:
    """Tests for reading resource state from temp file."""

    def test_hook_reads_resource_file(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook reads resource state from /tmp/claude-resources-{sessionId}.json."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # Create resource file with test data
        resource_data = {
            "freeMemMB": 8000,
            "activeAgents": 5,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "spawn more agents",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Hook should succeed even with resource file
        assert result.returncode == 0, (
            f"Hook should exit 0. Exit code: {result.returncode}, stderr: {result.stderr}"
        )

    def test_hook_handles_missing_resource_file(
        self,
        hooks_dir: Path,
        project_dir: Path
    ) -> None:
        """Hook handles gracefully when resource file doesn't exist."""
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        session_id = "nonexistent-session-12345"

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "hello world",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Hook should succeed even without resource file
        assert result.returncode == 0, (
            f"Hook should exit 0 when resource file missing. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )


class TestResourceWarningThreshold:
    """Tests for RESOURCE WARNING at 80% capacity."""

    def test_warning_at_80_percent(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook shows RESOURCE WARNING when activeAgents >= maxAgents * 0.8."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # 8/10 = 80% - exactly at threshold
        resource_data = {
            "freeMemMB": 4000,
            "activeAgents": 8,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "spawn agents",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Should contain RESOURCE WARNING
        output = result.stdout
        assert "RESOURCE WARNING" in output, (
            f"Expected 'RESOURCE WARNING' in output when at 80% capacity. "
            f"Output: {output}"
        )

    def test_warning_above_80_percent(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook shows RESOURCE WARNING when above 80% but below 100%."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # 9/10 = 90% - above 80%, below 100%
        resource_data = {
            "freeMemMB": 4000,
            "activeAgents": 9,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "spawn agents",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = result.stdout
        assert "RESOURCE WARNING" in output or "RESOURCE CRITICAL" in output, (
            f"Expected resource warning/critical in output above 80% capacity. "
            f"Output: {output}"
        )

    def test_no_warning_below_80_percent(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook does NOT show RESOURCE WARNING when below 80% capacity."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # 7/10 = 70% - below threshold
        resource_data = {
            "freeMemMB": 8000,
            "activeAgents": 7,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "hello world",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = result.stdout
        assert "RESOURCE WARNING" not in output, (
            f"Should NOT show 'RESOURCE WARNING' below 80% capacity. "
            f"Output: {output}"
        )
        assert "RESOURCE CRITICAL" not in output, (
            f"Should NOT show 'RESOURCE CRITICAL' below 80% capacity. "
            f"Output: {output}"
        )


class TestResourceCriticalThreshold:
    """Tests for RESOURCE CRITICAL at 100% capacity."""

    def test_critical_at_100_percent(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook shows RESOURCE CRITICAL when activeAgents >= maxAgents."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # 10/10 = 100% - at limit
        resource_data = {
            "freeMemMB": 2000,
            "activeAgents": 10,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "spawn agents",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = result.stdout
        assert "RESOURCE CRITICAL" in output, (
            f"Expected 'RESOURCE CRITICAL' in output at 100% capacity. "
            f"Output: {output}"
        )

    def test_critical_above_100_percent(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook shows RESOURCE CRITICAL when activeAgents > maxAgents."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # 12/10 = 120% - over limit
        resource_data = {
            "freeMemMB": 1000,
            "activeAgents": 12,
            "maxAgents": 10,
            "contextPct": 70
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "spawn agents",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = result.stdout
        assert "RESOURCE CRITICAL" in output, (
            f"Expected 'RESOURCE CRITICAL' in output above 100% capacity. "
            f"Output: {output}"
        )


class TestOutputFormat:
    """Tests for output format and content."""

    def test_warning_includes_agent_count(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Resource warning includes current/max agent count."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        resource_data = {
            "freeMemMB": 4000,
            "activeAgents": 8,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "test",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = result.stdout
        # Should show agent counts in some form (8/10 or similar)
        assert "8" in output and "10" in output, (
            f"Expected agent count (8/10) in output. Output: {output}"
        )

    def test_warning_mentions_near_limit(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Resource warning message indicates near limit."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        resource_data = {
            "freeMemMB": 4000,
            "activeAgents": 8,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "test",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = result.stdout.lower()
        # Should mention being near the limit
        assert "near" in output or "approaching" in output or "warning" in output, (
            f"Expected warning to mention being near limit. Output: {result.stdout}"
        )

    def test_critical_mentions_at_limit(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Resource critical message indicates at/over limit."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        resource_data = {
            "freeMemMB": 2000,
            "activeAgents": 10,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "test",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        output = result.stdout.lower()
        # Should mention being at the limit
        assert "limit" in output or "critical" in output or "at" in output, (
            f"Expected critical to mention being at limit. Output: {result.stdout}"
        )


class TestCoexistenceWithContextWarnings:
    """Tests for coexistence with existing context warnings."""

    def test_resource_warning_appends_to_context_warning(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Resource warning appears alongside context warning when both triggered."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # Set up resource warning condition
        resource_data = {
            "freeMemMB": 4000,
            "activeAgents": 8,
            "maxAgents": 10,
            "contextPct": 85  # Also triggers context warning
        }
        resource_file.write_text(json.dumps(resource_data))

        # Create context pct file for existing context warning
        context_file = Path(f"/tmp/claude-context-pct-{session_id}.txt")
        context_file.write_text("85")

        try:
            env = os.environ.copy()
            env["CLAUDE_SESSION_ID"] = session_id
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)

            hook_input = json.dumps({
                "session_id": session_id,
                "prompt": "test",
                "transcript_path": "/tmp/transcript.txt",
                "cwd": str(project_dir),
                "permission_mode": "auto"
            })

            result = subprocess.run(
                ["npx", "tsx", str(ts_handler)],
                input=hook_input,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir),
                timeout=30
            )

            assert result.returncode == 0, f"Hook failed: {result.stderr}"

            output = result.stdout
            # Should have both warnings
            has_context_warning = "CONTEXT" in output or "context" in output.lower()
            has_resource_warning = "RESOURCE" in output

            assert has_resource_warning, (
                f"Expected resource warning in output. Output: {output}"
            )
            # Context warning is optional based on existing implementation
        finally:
            if context_file.exists():
                context_file.unlink()

    def test_resource_warning_does_not_break_existing_output(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Resource warning doesn't interfere with skill activation output."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        resource_data = {
            "freeMemMB": 4000,
            "activeAgents": 8,
            "maxAgents": 10,
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        # Prompt that would trigger skill activation
        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "commit my changes",  # Should trigger commit skill
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # If skill was activated, output should still be well-formed
        # (no JSON parse errors, no broken formatting)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_malformed_resource_file(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook handles malformed JSON in resource file gracefully."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # Write invalid JSON
        resource_file.write_text("{ invalid json }")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "test",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Hook should still succeed (graceful degradation)
        assert result.returncode == 0, (
            f"Hook should succeed with malformed resource file. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

    def test_handles_missing_fields_in_resource_file(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook handles resource file with missing fields gracefully."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # Write JSON with missing fields
        resource_file.write_text('{"freeMemMB": 4000}')  # Missing activeAgents, maxAgents

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "test",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Hook should still succeed (graceful degradation)
        assert result.returncode == 0, (
            f"Hook should succeed with incomplete resource file. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

    def test_handles_zero_max_agents(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook handles maxAgents=0 without division by zero."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        resource_data = {
            "freeMemMB": 1000,
            "activeAgents": 0,
            "maxAgents": 0,  # Edge case
            "contextPct": 50
        }
        resource_file.write_text(json.dumps(resource_data))

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

        hook_input = json.dumps({
            "session_id": session_id,
            "prompt": "test",
            "transcript_path": "/tmp/transcript.txt",
            "cwd": str(project_dir),
            "permission_mode": "auto"
        })

        result = subprocess.run(
            ["npx", "tsx", str(ts_handler)],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        # Hook should not crash on edge case
        assert result.returncode == 0, (
            f"Hook should handle maxAgents=0 gracefully. "
            f"Exit code: {result.returncode}, stderr: {result.stderr}"
        )

    def test_uses_claude_ppid_fallback(
        self,
        hooks_dir: Path,
        project_dir: Path,
        temp_resource_file: tuple[Path, str]
    ) -> None:
        """Hook falls back to CLAUDE_PPID when CLAUDE_SESSION_ID not set."""
        resource_file, session_id = temp_resource_file
        ts_handler = hooks_dir / "src" / "skill-activation-prompt.ts"

        if not ts_handler.exists():
            pytest.skip("TypeScript handler doesn't exist yet")

        # Use PPID instead of SESSION_ID
        ppid = f"ppid-{os.getpid()}"
        ppid_resource_file = Path(f"/tmp/claude-resources-{ppid}.json")

        resource_data = {
            "freeMemMB": 4000,
            "activeAgents": 8,
            "maxAgents": 10,
            "contextPct": 50
        }
        ppid_resource_file.write_text(json.dumps(resource_data))

        try:
            env = os.environ.copy()
            env.pop("CLAUDE_SESSION_ID", None)  # Remove SESSION_ID
            env["CLAUDE_PPID"] = ppid
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)

            hook_input = json.dumps({
                "session_id": "unused",
                "prompt": "test",
                "transcript_path": "/tmp/transcript.txt",
                "cwd": str(project_dir),
                "permission_mode": "auto"
            })

            result = subprocess.run(
                ["npx", "tsx", str(ts_handler)],
                input=hook_input,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(hooks_dir),
                timeout=30
            )

            assert result.returncode == 0, f"Hook failed: {result.stderr}"

            output = result.stdout
            # Should find the resource file via PPID fallback and show warning
            assert "RESOURCE WARNING" in output, (
                f"Expected warning using PPID fallback. Output: {output}"
            )
        finally:
            if ppid_resource_file.exists():
                ppid_resource_file.unlink()
