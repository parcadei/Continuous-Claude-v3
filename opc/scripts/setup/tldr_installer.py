#!/usr/bin/env python3
"""tldr-code installation and management module.

Provides functions for:
- Installing llm-tldr from PyPI
- Creating system-wide symlink at /usr/local/bin/tldr
- Verifying installation
- Checking for updates
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Optional

# Configuration paths
HOME = Path(os.environ.get("HOME", str(Path.home())))
TLDR_BIN = HOME / ".venv" / "bin" / "tldr"
LLM_TLDR_BIN = HOME / ".venv" / "bin" / "llm-tldr"
SYMLINK = Path("/usr/local/bin/tldr")


def run_uv_pip_install(packages: list[str] = None, verbose: bool = False) -> bool:
    """Install packages using uv pip.

    Args:
        packages: List of packages to install. Defaults to ['llm-tldr'].
        verbose: Whether to print verbose output.

    Returns:
        True if installation succeeded, False otherwise.
    """
    if packages is None:
        packages = ["llm-tldr"]

    cmd = ["uv", "pip", "install"] + packages

    try:
        result = subprocess.run(
            cmd,
            capture_output=not verbose,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        if verbose:
            print(f"Installation failed: {e.stderr}")
        return False


def ensure_tldr_symlink(
    tldr_bin: Optional[Path] = None, symlink_path: Optional[Path] = None, verbose: bool = False
) -> bool:
    """Ensure tldr symlink exists at /usr/local/bin/tldr.

    Args:
        tldr_bin: Path to tldr binary. Defaults to ~/.venv/bin/tldr.
        symlink_path: Path for symlink. Defaults to /usr/local/bin/tldr.
        verbose: Print verbose output.

    Returns:
        True if symlink exists and works, False otherwise.
    """
    if tldr_bin is None:
        tldr_bin = TLDR_BIN
    if symlink_path is None:
        symlink_path = SYMLINK

    # Check if tldr binary exists
    if not tldr_bin.exists():
        if verbose:
            print(f"tldr binary not found at {tldr_bin}")
        return False

    try:
        # Check if symlink already exists
        if symlink_path.exists():
            if symlink_path.is_symlink():
                current_target = os.readlink(str(symlink_path))
                if Path(current_target).resolve() == tldr_bin.resolve():
                    # Already points to correct target
                    if verbose:
                        print(f"Symlink already correct at {symlink_path}")
                    return True
                else:
                    # Wrong target - remove for recreation
                    if verbose:
                        print(f"Removing incorrect symlink at {symlink_path}")
                    symlink_path.unlink()
            else:
                # Not a symlink - this is an error
                if verbose:
                    print(f"{symlink_path} exists but is not a symlink")
                return False

        # Create symlink using sudo
        if verbose:
            print(f"Creating symlink: {symlink_path} -> {tldr_bin}")

        subprocess.run(
            ["sudo", "ln", "-sf", str(tldr_bin), str(symlink_path)],
            check=True,
            capture_output=True,
        )

        # Verify the symlink works
        if symlink_path.exists():
            try:
                result = subprocess.run(
                    [str(symlink_path), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and "Token-efficient code analysis" in result.stdout:
                    if verbose:
                        print("Symlink verification successful")
                    return True
                else:
                    if verbose:
                        print(f"Symlink verification failed: {result.stderr}")
                    return False
            except (subprocess.TimeoutExpired, Exception) as e:
                if verbose:
                    print(f"Symlink verification error: {e}")
                return False
        else:
            if verbose:
                print("Symlink was not created")
            return False

    except PermissionError as e:
        if verbose:
            print(f"Permission denied: {e}")
        return False
    except subprocess.CalledProcessError as e:
        if verbose:
            print(f"Failed to create symlink: {e.stderr}")
        return False
    except Exception as e:
        if verbose:
            print(f"Unexpected error: {e}")
        return False


def install_tldr_code(
    verbose: bool = False,
    tldr_bin: Optional[Path] = None,
    symlink_path: Optional[Path] = None,
) -> bool:
    """Install tldr-code from PyPI and create system symlink.

    Args:
        verbose: Print verbose output.
        tldr_bin: Path to tldr binary.
        symlink_path: Path for symlink.

    Returns:
        True if installation succeeded, False otherwise.
    """
    if tldr_bin is None:
        tldr_bin = LLM_TLDR_BIN

    if verbose:
        print("Installing llm-tldr from PyPI...")

    # Check if already installed
    if tldr_bin.exists():
        if verbose:
            print(f"llm-tldr already installed at {tldr_bin}")
    else:
        # Install from PyPI
        if not run_uv_pip_install(verbose=verbose):
            if verbose:
                print("Failed to install llm-tldr")
            return False

    # Create symlink
    return ensure_tldr_symlink(tldr_bin=tldr_bin, symlink_path=symlink_path, verbose=verbose)


def check_tldr_update(
    tldr_bin: Optional[Path] = None, symlink_path: Optional[Path] = None
) -> bool:
    """Check if tldr is installed and up to date.

    Args:
        tldr_bin: Path to local tldr binary.
        symlink_path: Path to system symlink.

    Returns:
        True if tldr is installed and working, False otherwise.
    """
    if tldr_bin is None:
        tldr_bin = TLDR_BIN
    if symlink_path is None:
        symlink_path = SYMLINK

    # Check local installation
    if tldr_bin.exists():
        try:
            result = subprocess.run(
                [str(tldr_bin), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Check system-wide installation
    if symlink_path.exists():
        try:
            result = subprocess.run(
                [str(symlink_path), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return False


def uninstall_tldr_code(
    verbose: bool = False,
    tldr_bin: Optional[Path] = None,
    symlink_path: Optional[Path] = None,
) -> bool:
    """Uninstall tldr-code by removing symlink.

    Note: This only removes the symlink, not the pip package.

    Args:
        verbose: Print verbose output.
        tldr_bin: Path to tldr binary.
        symlink_path: Path to system symlink.

    Returns:
        True if symlink was removed or didn't exist, False on error.
    """
    if symlink_path is None:
        symlink_path = SYMLINK

    if not symlink_path.exists():
        if verbose:
            print(f"Symlink not found at {symlink_path}")
        return True

    if not symlink_path.is_symlink():
        if verbose:
            print(f"{symlink_path} is not a symlink, cannot remove")
        return False

    try:
        if verbose:
            print(f"Removing symlink at {symlink_path}")
        subprocess.run(
            ["sudo", "rm", str(symlink_path)],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        if verbose:
            print(f"Failed to remove symlink: {e.stderr}")
        return False
    except PermissionError as e:
        if verbose:
            print(f"Permission denied: {e}")
        return False
