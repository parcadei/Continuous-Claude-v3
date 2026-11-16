"""Integration tests for script harness."""

import subprocess
import sys
from pathlib import Path

# Determine the correct Python executable for subprocess tests
# Priority: .venv/bin/python > sys.executable
venv_python = Path.cwd() / ".venv" / "bin" / "python"
if venv_python.exists():
    PYTHON_EXECUTABLE = str(venv_python)
else:
    PYTHON_EXECUTABLE = sys.executable


def test_harness_simple_script():
    """Test harness executes simple script successfully."""
    # Create test script
    test_script = Path("workspace/test_harness_simple.py")
    test_script.parent.mkdir(exist_ok=True)
    test_script.write_text(
        """
print("Test output")
"""
    )

    # Run harness
    result = subprocess.run(
        [PYTHON_EXECUTABLE, "-m", "runtime.harness", str(test_script)],
        capture_output=True,
        text=True,
    )

    # Verify success
    assert result.returncode == 0
    assert "Test output" in result.stdout


def test_harness_script_with_mcp():
    """Test harness executes script that uses MCP tools."""
    # Create test script
    test_script = Path("workspace/test_harness_mcp.py")
    test_script.write_text(
        """
import asyncio
from runtime.mcp_client import call_mcp_tool

async def main():
    # Harness already initialized the manager, so just call the tool
    result = await call_mcp_tool("git__git_status", {"repo_path": "."})
    print(f"Git status result: {result is not None}")

asyncio.run(main())
"""
    )

    # Run harness
    result = subprocess.run(
        [PYTHON_EXECUTABLE, "-m", "runtime.harness", str(test_script)],
        capture_output=True,
        text=True,
    )

    # Verify success
    assert result.returncode == 0
    assert "Git status result: True" in result.stdout


def test_harness_script_error():
    """Test harness handles script errors."""
    # Create failing script
    test_script = Path("workspace/test_harness_error.py")
    test_script.write_text(
        """
raise Exception("Test error")
"""
    )

    # Run harness
    result = subprocess.run(
        [PYTHON_EXECUTABLE, "-m", "runtime.harness", str(test_script)],
        capture_output=True,
        text=True,
    )

    # Verify error handling
    assert result.returncode == 1
    assert "Test error" in result.stderr or "Test error" in result.stdout


def test_harness_script_not_found():
    """Test harness handles missing script."""
    # Run harness with non-existent script
    result = subprocess.run(
        [PYTHON_EXECUTABLE, "-m", "runtime.harness", "workspace/nonexistent.py"],
        capture_output=True,
        text=True,
    )

    # Verify error
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()
