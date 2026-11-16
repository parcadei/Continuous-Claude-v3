# Phase 9: Add Unix ppid Check to watch_agents.py

**Completed:** 2025-12-28
**Status:** All tests passing (13/13)

## Implementation Summary

Added `is_unix_orphan(pid: int) -> bool` function to `scripts/agentica/watch_agents.py` that detects true Unix orphans by checking if a process's parent is init/launchd (PID 1).

## TDD Process

### 1. Wrote Failing Tests First

Created `tests/unit/test_unix_orphan_check.py` with 13 tests covering:

| Test | Description |
|------|-------------|
| `test_current_process_is_not_orphan` | Running process has living parent |
| `test_nonexistent_pid_returns_false` | Non-existent PIDs handled gracefully |
| `test_init_process_has_ppid_zero` | PID 1 has ppid=0, not orphan |
| `test_negative_pid_returns_false` | Negative PIDs handled gracefully |
| `test_zero_pid_returns_false` | PID 0 handled gracefully |
| `test_returns_true_when_ppid_is_one` | Core functionality (mocked) |
| `test_returns_false_when_ppid_is_not_one` | Normal process (mocked) |
| `test_handles_timeout_gracefully` | Timeout returns False |
| `test_handles_invalid_output_gracefully` | Non-numeric output returns False |
| `test_handles_empty_output_gracefully` | Empty output returns False |
| `test_ps_command_format_macos_linux_compatible` | Verifies command format |
| `test_real_parent_process_check` | Integration test with real ps |
| `test_ps_format_works_on_platform` | Platform-specific integration test |

### 2. Confirmed Tests Failed

Initial run showed 11 failures (ImportError: `is_unix_orphan` not found) and 2 passing integration tests (which test `ps` directly).

### 3. Implemented Function

```python
def is_unix_orphan(pid: int) -> bool:
    """Check if a process is a Unix orphan (ppid == 1).

    A Unix orphan is a process whose parent has died and has been
    adopted by init/launchd (PID 1). This is used for orphan detection
    in the three-tier orphan classification system.

    Args:
        pid: The process ID to check.

    Returns:
        True if the process exists and its parent is init/launchd (PID 1).
        False if process doesn't exist, has a living parent, or on any error.
    """
    if pid <= 0:
        return False

    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "ppid="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                ppid = int(output)
                return ppid == 1
        return False  # Process doesn't exist or ps failed
    except (subprocess.TimeoutExpired, ValueError):
        return False
```

### 4. Confirmed All Tests Pass

```
============================= test session starts ==============================
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_current_process_is_not_orphan PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_nonexistent_pid_returns_false PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_init_process_has_ppid_zero PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_negative_pid_returns_false PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_zero_pid_returns_false PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_returns_true_when_ppid_is_one PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_returns_false_when_ppid_is_not_one PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_handles_timeout_gracefully PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_handles_invalid_output_gracefully PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_handles_empty_output_gracefully PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphan::test_ps_command_format_macos_linux_compatible PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphanIntegration::test_real_parent_process_check PASSED
tests/unit/test_unix_orphan_check.py::TestIsUnixOrphanIntegration::test_ps_format_works_on_platform PASSED
============================== 13 passed in 0.07s ==============================
```

## Files Changed

| File | Action |
|------|--------|
| `scripts/agentica/watch_agents.py` | Added `is_unix_orphan()` function |
| `tests/unit/test_unix_orphan_check.py` | Created (new file) |

## Cross-Platform Compatibility

The `ps -p <pid> -o ppid=` command format works on:
- macOS (Darwin)
- Linux (tested via integration test)

The `=` suffix suppresses the header line, returning only the numeric ppid.

## Usage

```python
from scripts.agentica.watch_agents import is_unix_orphan

# Check if a process is a true Unix orphan
if is_unix_orphan(some_pid):
    print("Process has been adopted by init - safe to terminate")
```

## Next Steps

This function is consumed by:
- Phase 10: `cleanup_orphans.py` script for orphan cleanup
- Phase 8: `CoordinationDB.get_orphan_candidates()` for tier-1 orphan detection
