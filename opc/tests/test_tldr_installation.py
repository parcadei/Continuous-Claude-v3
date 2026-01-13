#!/usr/bin/env python3
"""Tests for tldr-code installation and symlink management."""

import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Fixtures for tldr installation testing
# =============================================================================


@pytest.fixture
def mock_venv_bin(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a mock venv bin directory with tldr script."""
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)

    # Create a mock tldr script that outputs expected help text
    tldr_script = venv_bin / "tldr"
    tldr_script.write_text("#!/bin/bash\necho 'Token-efficient code analysis'\n")
    tldr_script.chmod(tldr_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Create llm-tldr as well
    llm_tldr = venv_bin / "llm-tldr"
    llm_tldr.write_text("#!/bin/bash\necho 'Token-efficient code analysis'\n")
    llm_tldr.chmod(llm_tldr.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    yield venv_bin


@pytest.fixture
def mock_tldr_executable(mock_venv_bin: Path) -> Generator[Path, None, None]:
    """Create a mock llm-tldr executable that outputs expected help text."""
    tldr_path = mock_venv_bin / "llm-tldr"
    tldr_path.write_text(
        """#!/bin/bash
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Token-efficient code analysis"
    exit 0
fi
echo "Token-efficient code analysis"
exit 0
"""
    )
    tldr_path.chmod(tldr_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return tldr_path


@pytest.fixture
def mock_usr_local_bin(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a mock /usr/local/bin directory."""
    usr_local_bin = tmp_path / "usr" / "local" / "bin"
    usr_local_bin.mkdir(parents=True)
    return usr_local_bin


@pytest.fixture
def sudo_mock() -> Generator[MagicMock, None, None]:
    """Mock sudo command."""
    mock = MagicMock()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = b""
    mock_result.stderr = b""
    mock.run.return_value = mock_result
    yield mock


def create_symlink_runner(tmp_path: Path):
    """Create a subprocess.run mock that actually creates symlinks."""

    def mock_run(cmd, capture_output=False, text=False, **kwargs):
        result = MagicMock()
        result.returncode = 0
        # Return bytes by default (capture_output=True)
        result.stdout = b"Token-efficient code analysis"
        result.stderr = b""

        # Handle text mode
        if text:
            result.stdout = "Token-efficient code analysis"
            result.stderr = ""

        # Check if this is a symlink creation command
        if isinstance(cmd, list) and len(cmd) >= 3:
            if cmd[0] == "sudo" and cmd[1] == "ln":
                # sudo ln -sf source target
                target = Path(cmd[-1])
                source = Path(cmd[-2])
                try:
                    if target.is_symlink() or target.exists():
                        target.unlink()
                    target.symlink_to(source)
                except OSError as e:
                    result.returncode = 1
                    result.stderr = f"Could not create symlink: {e}".encode() if not text else str(e)

            # Check if this is a verification command (tldr --help)
            elif "--help" in str(cmd) or (len(cmd) > 0 and "tldr" in str(cmd[0])):
                result.returncode = 0
                result.stdout = b"Token-efficient code analysis"
                if text:
                    result.stdout = "Token-efficient code analysis"

            # Check if this is a rm command (uninstall)
            elif len(cmd) >= 2 and cmd[0] == "sudo" and cmd[1] == "rm":
                target = Path(cmd[-1])
                try:
                    if target.exists() or target.is_symlink():
                        target.unlink()
                except OSError as e:
                    result.returncode = 1
                    result.stderr = f"Could not remove symlink: {e}".encode() if not text else str(e)

        return result

    return mock_run


# =============================================================================
# Tests for ensure_tldr_symlink function
# =============================================================================


class TestEnsureTldrSymlink:
    """Tests for the ensure_tldr_symlink function."""

    def test_symlink_created_successfully(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test symlink is created when it doesn't exist."""
        from scripts.setup import tldr_installer

        # Set up paths
        venv_tldr = mock_venv_bin / "tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", create_symlink_runner(mock_usr_local_bin)):
            # Run the function
            result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Verify symlink was created
            assert result is True
            assert target_symlink.exists()
            assert target_symlink.is_symlink()

    def test_symlink_already_exists_correct(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test when symlink already points to correct target."""
        from scripts.setup import tldr_installer

        # Set up paths
        venv_tldr = mock_venv_bin / "tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        # Create existing correct symlink
        target_symlink.symlink_to(venv_tldr)

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""

            # Only count ln calls (symlink creation)
            if isinstance(cmd, list) and len(cmd) >= 2 and cmd[1] == "ln":
                call_count += 1

            # Handle verification
            if "--help" in str(cmd):
                result.stdout = b"Token-efficient code analysis"

            return result

        with patch.object(subprocess, "run", mock_run):
            # Run the function
            result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Should return True and not call ln
            assert result is True
            # subprocess.run should not be called for symlink creation
            assert call_count == 0

    def test_symlink_already_exists_incorrect(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test when symlink exists but points to wrong target."""
        from scripts.setup import tldr_installer

        # Set up paths
        venv_tldr = mock_venv_bin / "tldr"
        wrong_target = mock_usr_local_bin / "wrong_tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        # Create wrong symlink
        target_symlink.symlink_to(wrong_target)

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", create_symlink_runner(mock_usr_local_bin)):
            # Run the function
            result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Should still return True (replaced the symlink)
            assert result is True

    def test_symlink_permission_denied(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test when can't write to /usr/local/bin."""
        from scripts.setup import tldr_installer

        # Set up paths
        venv_tldr = mock_venv_bin / "tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        # Make subprocess.run fail with permission error
        mock_run = MagicMock()
        mock_run.side_effect = PermissionError("Permission denied")

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", mock_run):
            # Run the function
            result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Should return False on permission error
            assert result is False

    def test_symlink_tldr_not_found(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test when llm-tldr is not installed."""
        from scripts.setup import tldr_installer

        # Set up paths - tldr doesn't exist
        venv_tldr = mock_venv_bin / "nonexistent_tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", MagicMock()):
            # Run the function
            result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Should return False when tldr binary not found
            assert result is False

    def test_symlink_verification_fails(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test when symlink is created but binary doesn't work."""
        from scripts.setup import tldr_installer

        # Set up paths
        venv_tldr = mock_venv_bin / "tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        # Make the verification fail (non-zero exit code)
        def mock_run_func(cmd, **kwargs):
            result = MagicMock()
            if "--help" in str(cmd):
                result.returncode = 1
                result.stdout = "error"
                result.stderr = b"Command failed"
            else:
                # Create symlink
                if isinstance(cmd, list) and len(cmd) >= 3 and cmd[1] == "ln":
                    target = Path(cmd[-1])
                    source = Path(cmd[-2])
                    if target.is_symlink() or target.exists():
                        target.unlink()
                    target.symlink_to(source)
                result.returncode = 0
            return result

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", mock_run_func):
            # Run the function
            result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Should return False when verification fails
            assert result is False


# =============================================================================
# Tests for install_tldr_code function
# =============================================================================


class TestInstallTldrCode:
    """Tests for the install_tldr_code function."""

    def test_install_tldr_code_first_time(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test fresh installation of tldr-code."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", create_symlink_runner(mock_usr_local_bin)):
            result = tldr_installer.install_tldr_code(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            assert result is True
            # Symlink should be created
            assert target_symlink.exists()

    def test_install_tldr_code_already_installed(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test when tldr-code is already installed."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        # Create existing symlink
        target_symlink.symlink_to(venv_tldr)

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            if isinstance(cmd, list) and len(cmd) >= 2 and cmd[1] == "ln":
                call_count += 1
            if "--help" in str(cmd):
                result.stdout = b"Token-efficient code analysis"
            return result

        with patch.object(subprocess, "run", mock_run):
            result = tldr_installer.install_tldr_code(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Should return True without creating new symlink
            assert result is True
            # ln should not be called since symlink already exists and is correct
            assert call_count == 0

    def test_install_tldr_code_verbose_output(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        """Test verbose flag produces output."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", create_symlink_runner(mock_usr_local_bin)):
            result = tldr_installer.install_tldr_code(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=True
            )

            assert result is True
            captured = capsys.readouterr()
            # Should have some output about installation
            assert "llm-tldr" in captured.out or "tldr" in captured.out


# =============================================================================
# Tests for check_tldr_update function
# =============================================================================


class TestCheckTldrUpdate:
    """Tests for the check_tldr_update function."""

    def test_check_tldr_update_dev_install(
        self,
        mock_venv_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test checking update when installed in dev mode."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"

        # Mock subprocess.run to return success
        mock_run = MagicMock()
        mock_run.return_value = MagicMock(returncode=0, stdout="Token-efficient code analysis", stderr="")

        with patch.object(subprocess, "run", mock_run):
            result = tldr_installer.check_tldr_update(tldr_bin=venv_tldr)

            assert result is True

    def test_check_tldr_update_pypi_install(
        self,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test checking update when installed from PyPI."""
        from scripts.setup import tldr_installer

        # Create mock system-wide tldr
        system_tldr = mock_usr_local_bin / "tldr"
        system_tldr.write_text("#!/bin/bash\necho 'tldr'\n")
        system_tldr.chmod(0o755)

        # Mock subprocess.run to return success
        mock_run = MagicMock()
        mock_run.return_value = MagicMock(returncode=0, stdout="Token-efficient code analysis", stderr="")

        with patch.object(subprocess, "run", mock_run):
            result = tldr_installer.check_tldr_update(symlink_path=system_tldr)

            assert result is True

    def test_check_tldr_update_not_installed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test when tldr is not installed anywhere."""
        from scripts.setup import tldr_installer

        # Set paths to non-existent locations
        non_existent_venv = tmp_path / ".venv" / "bin" / "tldr"
        non_existent_sys = tmp_path / "usr" / "local" / "bin" / "tldr"

        # Mock subprocess to fail
        mock_run = MagicMock()
        mock_run.side_effect = FileNotFoundError("Command not found")

        with patch.object(subprocess, "run", mock_run):
            result = tldr_installer.check_tldr_update(
                tldr_bin=non_existent_venv, symlink_path=non_existent_sys
            )

            assert result is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestTldrInstallationIntegration:
    """Integration tests for tldr-code installation flow."""

    def test_full_installation_flow(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test complete installation flow from install to verification."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", create_symlink_runner(mock_usr_local_bin)):
            # Step 1: Install tldr-code
            install_result = tldr_installer.install_tldr_code(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )
            assert install_result is True

            # Step 2: Verify installation
            verify_result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )
            assert verify_result is True

            # Step 3: Check update (should show up to date)
            update_check = tldr_installer.check_tldr_update(
                tldr_bin=venv_tldr, symlink_path=target_symlink
            )
            assert update_check is True

    def test_installation_with_broken_symlink(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test recovery from a broken symlink."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        # Create broken symlink
        broken_target = mock_usr_local_bin / "broken_tldr"
        target_symlink.symlink_to(broken_target)

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", create_symlink_runner(mock_usr_local_bin)):
            # Attempt installation (should fix broken symlink)
            result = tldr_installer.install_tldr_code(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            assert result is True
            # Symlink should now point to correct target
            assert target_symlink.exists()
            assert target_symlink.is_symlink()
            # Verify the symlink target is correct
            assert str(target_symlink.resolve()) == str(venv_tldr)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestTldrInstallationEdgeCases:
    """Edge case tests for tldr-code installation."""

    def test_handles_missing_venv_directory(
        self,
        tmp_path: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test handling when .venv directory doesn't exist."""
        from scripts.setup import tldr_installer

        # Non-existent venv
        venv_bin = tmp_path / ".venv" / "bin"
        venv_tldr = venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", MagicMock()):
            result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Should return False when venv doesn't exist
            assert result is False

    def test_handles_corrupted_symlink(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test handling of dangling/broken symlink."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        # Create dangling symlink
        dangling = mock_usr_local_bin / "dangling"
        target_symlink.symlink_to(dangling)

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", create_symlink_runner(mock_usr_local_bin)):
            result = tldr_installer.ensure_tldr_symlink(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=False
            )

            # Should replace the dangling symlink
            assert result is True
            # Symlink should now point to valid target
            assert target_symlink.exists()

    def test_verbose_mode_produces_messages(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        """Test that verbose mode outputs progress messages."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        monkeypatch.setenv("HOME", str(mock_usr_local_bin.parent.parent.parent))

        with patch.object(subprocess, "run", create_symlink_runner(mock_usr_local_bin)):
            # Run with verbose=True
            tldr_installer.install_tldr_code(
                tldr_bin=venv_tldr, symlink_path=target_symlink, verbose=True
            )

            # Check output was produced
            captured = capsys.readouterr()
            assert len(captured.out) > 0 or len(captured.err) > 0

    def test_uninstall_removes_symlink(
        self,
        mock_venv_bin: Path,
        mock_usr_local_bin: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test uninstall function removes symlink correctly."""
        from scripts.setup import tldr_installer

        venv_tldr = mock_venv_bin / "llm-tldr"
        target_symlink = mock_usr_local_bin / "tldr"

        # Create symlink first
        target_symlink.symlink_to(venv_tldr)
        assert target_symlink.exists()

        # Mock subprocess for sudo rm
        def mock_rm(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""

            # Handle rm command
            if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "sudo" and cmd[1] == "rm":
                target = Path(cmd[-1])
                if target.exists() or target.is_symlink():
                    target.unlink()

            return result

        with patch.object(subprocess, "run", mock_rm):
            result = tldr_installer.uninstall_tldr_code(
                symlink_path=target_symlink, verbose=False
            )

            assert result is True
            assert not target_symlink.exists()
