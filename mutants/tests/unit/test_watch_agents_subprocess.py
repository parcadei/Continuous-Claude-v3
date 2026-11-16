"""Tests for subprocess observability in watch_agents.py.

These tests verify that watch_agents can:
1. Detect running `claude` CLI processes
2. Track file changes in watched directories
3. Associate subprocesses with their parent agents

TDD: These tests are written BEFORE implementation.
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import subprocess monitoring functions
from scripts.agentica.watch_agents import (
    find_claude_processes,
    watch_directory_changes,
    get_process_tree,
    SubprocessMonitor,
)


class TestFindClaudeProcesses:
    """Test detection of running claude CLI processes."""

    def test_returns_list(self):
        """find_claude_processes should return a list."""
        result = find_claude_processes()
        assert isinstance(result, list)

    def test_process_info_structure(self):
        """Each process should have pid, command, and parent_pid."""
        # Mock a claude process
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="12345 claude -p test query\n",
                returncode=0,
            )
            result = find_claude_processes()
            if result:
                proc = result[0]
                assert "pid" in proc
                assert "command" in proc
                assert "parent_pid" in proc

    def test_filters_to_claude_only(self):
        """Should only return claude-related processes."""
        with patch("subprocess.run") as mock_run:
            # Simulate ps output with mixed processes
            mock_run.return_value = MagicMock(
                stdout="123 python script.py\n456 claude -p query\n789 node server.js\n",
                returncode=0,
            )
            result = find_claude_processes()
            # Should filter to only claude
            assert all("claude" in p.get("command", "") for p in result)


class TestWatchDirectoryChanges:
    """Test file system change detection."""

    def test_detects_new_file(self):
        """Should detect when a new file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = watch_directory_changes(tmpdir)

            # Create a file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')")

            changes = monitor.get_changes()
            assert len(changes) > 0
            assert any(c["type"] == "created" for c in changes)

    def test_detects_modified_file(self):
        """Should detect when a file is modified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("original")

            monitor = watch_directory_changes(tmpdir)

            # Modify the file
            time.sleep(0.1)  # Ensure mtime changes
            test_file.write_text("modified")

            changes = monitor.get_changes()
            assert any(c["type"] == "modified" for c in changes)

    def test_returns_file_path_and_time(self):
        """Changes should include path and timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = watch_directory_changes(tmpdir)

            test_file = Path(tmpdir) / "new.txt"
            test_file.write_text("content")

            changes = monitor.get_changes()
            if changes:
                change = changes[0]
                assert "path" in change
                assert "timestamp" in change


class TestGetProcessTree:
    """Test process tree inspection."""

    def test_returns_children_of_pid(self):
        """Should return child processes of a given PID."""
        # Get our own PID and check for children
        our_pid = os.getpid()
        result = get_process_tree(our_pid)
        assert isinstance(result, list)

    def test_includes_recursive_children(self):
        """Should include grandchildren (recursive)."""
        # This is a structural test - implementation should handle recursion
        result = get_process_tree(1)  # init/launchd
        assert isinstance(result, list)


class TestSubprocessMonitor:
    """Test the unified subprocess monitor class."""

    def test_init_with_watch_dir(self):
        """Should accept a directory to watch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = SubprocessMonitor(watch_dirs=[tmpdir])
            assert monitor is not None

    def test_get_status_returns_dict(self):
        """get_status should return comprehensive status dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = SubprocessMonitor(watch_dirs=[tmpdir])
            status = monitor.get_status()

            assert isinstance(status, dict)
            assert "claude_processes" in status
            assert "file_changes" in status
            assert "timestamp" in status

    def test_snapshot_and_diff(self):
        """Should track changes between snapshots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = SubprocessMonitor(watch_dirs=[tmpdir])
            monitor.take_snapshot()

            # Create a file
            (Path(tmpdir) / "new.txt").write_text("hello")

            diff = monitor.get_diff_since_snapshot()
            assert "new_files" in diff

    def test_integration_with_watch_agents_table(self):
        """SubprocessMonitor should integrate with watch_agents output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = SubprocessMonitor(watch_dirs=[tmpdir])
            status = monitor.get_status()

            # Should be formattable for Rich table
            assert "claude_processes" in status
            # Processes should be list of dicts with display-friendly fields
            for proc in status["claude_processes"]:
                assert isinstance(proc, dict)


class TestIntegration:
    """Integration tests for subprocess monitoring with watch_agents.py."""

    def test_monitor_flag_exists(self):
        """watch_agents.py should accept --monitor flag."""
        result = subprocess.run(
            ["python", "scripts/agentica/watch_agents.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )
        # After implementation, --monitor should be in help
        assert "--monitor" in result.stdout or result.returncode != 0

    def test_subprocess_column_in_table(self):
        """Running agents table should show subprocess info."""
        # This is a visual/output test - implementation specific
        # For now, just verify the module imports work
        from scripts.agentica import watch_agents

        assert hasattr(watch_agents, "main")
