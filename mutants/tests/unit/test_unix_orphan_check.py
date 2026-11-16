#!/usr/bin/env python3
"""Unit tests for is_unix_orphan function in watch_agents.py.

Tests the Unix ppid check functionality that determines if a process
has been adopted by init/launchd (ppid == 1), indicating it's a true
Unix orphan.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add project root for imports
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class TestIsUnixOrphan:
    """Tests for the is_unix_orphan function."""

    def test_current_process_is_not_orphan(self):
        """The current Python process should not be an orphan."""
        from scripts.agentica.watch_agents import is_unix_orphan

        # Current process has a parent (the shell or test runner)
        result = is_unix_orphan(os.getpid())
        assert result is False, "Current process should not be an orphan"

    def test_nonexistent_pid_returns_false(self):
        """A PID that doesn't exist should return False."""
        from scripts.agentica.watch_agents import is_unix_orphan

        # Use a very high PID that's unlikely to exist
        # On most systems, max PID is around 32768 or 4194304
        nonexistent_pid = 9999999
        result = is_unix_orphan(nonexistent_pid)
        assert result is False, "Nonexistent PID should return False"

    def test_init_process_has_ppid_zero(self):
        """PID 1 (init/launchd) itself has ppid 0, not an orphan by our logic."""
        from scripts.agentica.watch_agents import is_unix_orphan

        # PID 1 is the init process, its ppid is 0
        # This should return False (ppid != 1)
        result = is_unix_orphan(1)
        assert result is False, "Init process (PID 1) should not be flagged as orphan"

    def test_negative_pid_returns_false(self):
        """Negative PIDs should return False gracefully."""
        from scripts.agentica.watch_agents import is_unix_orphan

        result = is_unix_orphan(-1)
        assert result is False, "Negative PID should return False"

    def test_zero_pid_returns_false(self):
        """PID 0 should return False."""
        from scripts.agentica.watch_agents import is_unix_orphan

        result = is_unix_orphan(0)
        assert result is False, "PID 0 should return False"

    def test_returns_true_when_ppid_is_one(self):
        """When ps reports ppid=1, function should return True."""
        from scripts.agentica.watch_agents import is_unix_orphan

        # Mock subprocess.run to simulate a process with ppid=1
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "    1\n"  # ppid with leading whitespace

        with mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            result = is_unix_orphan(12345)

            # Verify ps was called with correct arguments
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == ["ps", "-p", "12345", "-o", "ppid="]

            assert result is True, "Process with ppid=1 should be detected as orphan"

    def test_returns_false_when_ppid_is_not_one(self):
        """When ps reports ppid != 1, function should return False."""
        from scripts.agentica.watch_agents import is_unix_orphan

        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  5678\n"  # Some other ppid

        with mock.patch("subprocess.run", return_value=mock_result):
            result = is_unix_orphan(12345)
            assert result is False, "Process with ppid!=1 should not be an orphan"

    def test_handles_timeout_gracefully(self):
        """Timeout during ps call should return False."""
        from scripts.agentica.watch_agents import is_unix_orphan

        with mock.patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ps", timeout=5)
        ):
            result = is_unix_orphan(12345)
            assert result is False, "Timeout should return False"

    def test_handles_invalid_output_gracefully(self):
        """Invalid output (non-numeric) should return False."""
        from scripts.agentica.watch_agents import is_unix_orphan

        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid\n"

        with mock.patch("subprocess.run", return_value=mock_result):
            result = is_unix_orphan(12345)
            assert result is False, "Invalid output should return False"

    def test_handles_empty_output_gracefully(self):
        """Empty output should return False."""
        from scripts.agentica.watch_agents import is_unix_orphan

        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with mock.patch("subprocess.run", return_value=mock_result):
            result = is_unix_orphan(12345)
            assert result is False, "Empty output should return False"

    def test_ps_command_format_macos_linux_compatible(self):
        """Verify the ps command format works on both macOS and Linux."""
        from scripts.agentica.watch_agents import is_unix_orphan

        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  1234\n"

        with mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            is_unix_orphan(9999)

            # Verify command format: ps -p <pid> -o ppid=
            # This format works on both macOS and Linux
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "ps"
            assert "-p" in call_args
            assert "-o" in call_args
            assert "ppid=" in call_args  # = suppresses header


class TestIsUnixOrphanIntegration:
    """Integration tests that use real system calls."""

    def test_real_parent_process_check(self):
        """Verify we can get ppid of current process using ps."""
        # Run actual ps command to verify it works on this system
        result = subprocess.run(
            ["ps", "-p", str(os.getpid()), "-o", "ppid="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, "ps command should succeed"

        ppid = int(result.stdout.strip())
        assert ppid > 0, "Current process should have a positive ppid"
        assert ppid != 1, "Test runner process should not be an orphan"

    @pytest.mark.skipif(
        sys.platform not in ("darwin", "linux"),
        reason="Only runs on macOS or Linux"
    )
    def test_ps_format_works_on_platform(self):
        """Verify ps -o ppid= format works on current platform."""
        result = subprocess.run(
            ["ps", "-p", "1", "-o", "ppid="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # PID 1 exists on all Unix systems
        assert result.returncode == 0, "ps should find PID 1"

        ppid = int(result.stdout.strip())
        # Init's ppid is 0
        assert ppid == 0, "Init process should have ppid=0"
