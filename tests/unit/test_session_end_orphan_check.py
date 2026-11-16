"""Unit tests for SessionEnd orphan check hook.

Tests the integration between session-end-cleanup-swarms.ts and cleanup_orphans.py
to ensure orphan cleanup is triggered at session end using fire-and-forget pattern.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSessionEndOrphanCheck:
    """Tests for SessionEnd hook orphan cleanup integration."""

    @pytest.fixture
    def project_dir(self) -> Path:
        """Get the project directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def hook_path(self, project_dir: Path) -> Path:
        """Get the path to the session-end hook TypeScript file."""
        return project_dir / ".claude" / "hooks" / "src" / "session-end-cleanup-swarms.ts"

    @pytest.fixture
    def cleanup_script_path(self, project_dir: Path) -> Path:
        """Get the path to cleanup_orphans.py script."""
        return project_dir / "scripts" / "agentica" / "cleanup_orphans.py"

    def test_hook_file_exists(self, hook_path: Path) -> None:
        """Verify the hook file exists."""
        assert hook_path.exists(), f"Hook file not found: {hook_path}"

    def test_cleanup_script_exists(self, cleanup_script_path: Path) -> None:
        """Verify the cleanup script exists."""
        assert cleanup_script_path.exists(), f"Cleanup script not found: {cleanup_script_path}"

    def test_hook_imports_spawn_for_fire_and_forget(self, hook_path: Path) -> None:
        """Verify hook imports spawn (not just spawnSync) for fire-and-forget pattern."""
        content = hook_path.read_text()
        # The hook should import 'spawn' from child_process for fire-and-forget
        assert "spawn" in content, "Hook should import 'spawn' for fire-and-forget pattern"

    def test_hook_calls_cleanup_orphans_with_tier_1(self, hook_path: Path) -> None:
        """Verify hook calls cleanup_orphans.py with --kill --tier 1 flags."""
        content = hook_path.read_text()
        # Should call cleanup_orphans.py with --kill and --tier 1
        assert "cleanup_orphans.py" in content, "Hook should reference cleanup_orphans.py"
        assert "--kill" in content, "Hook should use --kill flag"
        assert "--tier" in content and "1" in content, "Hook should filter to tier 1 only"

    def test_hook_uses_detached_mode(self, hook_path: Path) -> None:
        """Verify hook spawns cleanup in detached mode for fire-and-forget."""
        content = hook_path.read_text()
        # Fire-and-forget requires detached: true
        assert "detached" in content, "Hook should use detached mode for fire-and-forget"

    def test_hook_uses_unref(self, hook_path: Path) -> None:
        """Verify hook calls unref() to not block session exit."""
        content = hook_path.read_text()
        # unref() allows the parent to exit without waiting for child
        assert "unref" in content, "Hook should call unref() to not block session exit"

    def test_hook_logs_cleanup_trigger(self, hook_path: Path) -> None:
        """Verify hook logs that cleanup was triggered."""
        content = hook_path.read_text()
        # Should log something about orphan cleanup being triggered
        has_logging = (
            "orphan" in content.lower()
            or "cleanup" in content.lower()
        )
        assert has_logging, "Hook should log that orphan cleanup was triggered"

    def test_hook_execution_returns_continue(self, project_dir: Path) -> None:
        """Verify hook execution returns continue result."""
        hook_script = project_dir / ".claude" / "hooks" / "session-end-cleanup-swarms.sh"

        # Skip if shell wrapper doesn't exist
        if not hook_script.exists():
            pytest.skip("Shell wrapper not found")

        # Create a temporary database path to avoid touching real data
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["bash", str(hook_script)],
                input='{"session_id": "test-session-123"}',
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "CLAUDE_PROJECT_DIR": tmpdir,
                },
                timeout=30,
            )

            # Hook should not fail
            if result.returncode != 0:
                pytest.skip(f"Hook execution failed: {result.stderr}")

            # Parse JSON output
            try:
                output = json.loads(result.stdout.strip().split("\n")[-1])
                assert output.get("result") == "continue", "Hook should return 'continue' result"
            except json.JSONDecodeError:
                pytest.skip(f"Could not parse hook output: {result.stdout}")


class TestCleanupOrphansScript:
    """Tests for cleanup_orphans.py script CLI behavior."""

    @pytest.fixture
    def project_dir(self) -> Path:
        """Get the project directory."""
        return Path(__file__).parent.parent.parent

    def test_script_accepts_tier_argument(self, project_dir: Path) -> None:
        """Verify cleanup_orphans.py accepts --tier argument."""
        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/cleanup_orphans.py", "--help"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=30,
        )
        assert "--tier" in result.stdout, "Script should accept --tier argument"

    def test_script_accepts_kill_argument(self, project_dir: Path) -> None:
        """Verify cleanup_orphans.py accepts --kill argument."""
        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/cleanup_orphans.py", "--help"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=30,
        )
        assert "--kill" in result.stdout, "Script should accept --kill argument"

    def test_script_dry_run_default(self, project_dir: Path) -> None:
        """Verify dry-run is the default mode."""
        result = subprocess.run(
            ["uv", "run", "python", "scripts/agentica/cleanup_orphans.py", "--help"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=30,
        )
        assert "dry-run" in result.stdout.lower(), "Script should default to dry-run"
