# Path Traversal Prevention Best Practices for Python

**Research Date:** 2025-12-29
**Context:** Security hardening for `scripts/agentica/agent_handoff.py`

## Executive Summary

Path traversal attacks allow attackers to access files outside intended directories by manipulating path parameters with sequences like `../`. In Python, defense requires a layered approach: input validation (allowlists), path resolution with `pathlib`, containment verification, and defense-in-depth before dangerous operations.

## Key Security Recommendations

### 1. Input Validation: Use Allowlist Patterns

**Best Practice:** Validate all path components against a strict allowlist regex BEFORE use.

```python
import re

# Allowlist: only alphanumeric, underscore, hyphen
SAFE_PATH_COMPONENT = re.compile(r'^[a-zA-Z0-9_\-]+$')

# Filenames can have a single extension
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$')

def _validate_path_component(component: str, component_type: str = "path component") -> str:
    """Validate a path component to prevent traversal attacks."""
    if not component:
        raise ValueError(f"Empty {component_type} not allowed")

    # Block null bytes (C-string terminator attacks)
    if '\x00' in component:
        raise ValueError(f"Null byte in {component_type} not allowed")

    # Block traversal patterns explicitly
    if '..' in component:
        raise ValueError(f"Path traversal in {component_type}: {component!r}")

    # Block absolute paths
    if component.startswith('/') or component.startswith('~'):
        raise ValueError(f"Absolute path in {component_type} not allowed: {component!r}")

    # Block path separators
    if '/' in component or '\\' in component:
        raise ValueError(f"Path separator in {component_type} not allowed: {component!r}")

    # Validate against allowlist
    if not SAFE_PATH_COMPONENT.match(component):
        raise ValueError(
            f"Invalid {component_type}: {component!r}. "
            f"Only alphanumeric, underscore, and hyphen allowed."
        )

    return component
```

**Why allowlist over blocklist:**
- Blocklists are incomplete (new attack vectors emerge)
- Allowlists define exactly what's permitted
- OWASP recommends allowlist validation for path components

### 2. Path Resolution and Containment Verification

**Best Practice:** After constructing a path, resolve it and verify it stays within the allowed base directory.

```python
import os
import sys
from pathlib import Path

def _validate_path_within_base(path: Path, base: Path) -> Path:
    """Validate that a resolved path stays within the base directory."""
    resolved = path.resolve()
    base_resolved = base.resolve()

    # Handle case-insensitive filesystems (macOS, Windows)
    if sys.platform == 'darwin':
        resolved_str = str(resolved).lower()
        base_str = str(base_resolved).lower()
    else:
        resolved_str = str(resolved)
        base_str = str(base_resolved)

    # Check containment with proper separator handling
    if not (resolved_str.startswith(base_str + os.sep) or resolved_str == base_str):
        raise ValueError(
            f"Path {path} resolves to {resolved} which escapes base directory {base_resolved}"
        )

    return resolved
```

**Key points:**
- Use `Path.resolve()` to canonicalize paths (follows symlinks, normalizes `.` and `..`)
- String prefix comparison catches symlink attacks
- Add `os.sep` to prevent false positives (e.g., `/base-evil` vs `/base`)
- Handle case-insensitive filesystems explicitly

### 3. Avoiding `is_relative_to()` Pitfalls

Python 3.9+ provides `Path.is_relative_to()`, but it has limitations:

```python
# CAUTION: is_relative_to() does NOT resolve symlinks
path = Path("/base/../etc/passwd")
path.is_relative_to("/base")  # Returns False, but...

# The RESOLVED path matters
path.resolve().is_relative_to(Path("/base").resolve())  # Correct check
```

**Recommended pattern:**

```python
def safe_is_within(path: Path, base: Path) -> bool:
    """Check if path is within base, resolving symlinks."""
    try:
        resolved_path = path.resolve()
        resolved_base = base.resolve()
        resolved_path.relative_to(resolved_base)
        return True
    except ValueError:
        return False
```

### 4. Safe `shutil.rmtree()` Usage

**Critical:** `shutil.rmtree()` recursively deletes directories. ALWAYS validate before calling.

```python
import shutil

def safe_cleanup(session_dir: Path, base_dir: Path) -> None:
    """Safely remove a session directory with validation."""
    if not session_dir.exists():
        return

    # Defense-in-depth: re-validate before destructive operation
    try:
        _validate_path_within_base(session_dir, base_dir)
    except ValueError as e:
        raise ValueError(
            f"SECURITY: Refusing to delete directory outside base: {session_dir}. "
            f"Original error: {e}"
        ) from e

    # Verify it's actually a directory
    if not session_dir.is_dir():
        raise ValueError(f"Expected directory, got file: {session_dir}")

    shutil.rmtree(session_dir)
```

**Why defense-in-depth matters:**
- Session directory could be corrupted/manipulated after initial validation
- Symlinks could be created between validation and deletion
- Explicit re-validation catches programming errors

### 5. Filename Validation

For artifact/file names within allowed directories:

```python
def _validate_filename(name: str) -> str:
    """Validate a filename for artifact storage."""
    if not name:
        raise ValueError("Empty filename not allowed")

    if '\x00' in name:
        raise ValueError("Null byte in filename not allowed")

    if '..' in name:
        raise ValueError(f"Path traversal in filename: {name!r}")

    if '/' in name or '\\' in name:
        raise ValueError(f"Path separator in filename not allowed: {name!r}")

    # Block hidden files (common attack vector for dotfiles like .bashrc)
    if name.startswith('.'):
        raise ValueError(f"Hidden files not allowed: {name!r}")

    # Validate against allowlist
    if not SAFE_FILENAME.match(name):
        raise ValueError(
            f"Invalid filename: {name!r}. "
            f"Only alphanumeric, underscore, hyphen, and single extension allowed."
        )

    return name
```

### 6. Belt-and-Suspenders Validation Pattern

Apply validation at multiple layers:

```python
class AgentHandoff:
    def __init__(self, session_id: str, base_dir: Path | None = None):
        # Layer 1: Validate input
        self.session_id = _validate_path_component(session_id, "session_id")
        self.base_dir = (base_dir or self.BASE_DIR).resolve()

        # Layer 2: Build path
        self.session_dir = self.base_dir / self.session_id

        # Layer 3: Validate constructed path
        _validate_path_within_base(self.session_dir, self.base_dir)

        self.session_dir.mkdir(parents=True, exist_ok=True)

    def get_output_dir(self, phase: str) -> Path:
        # Layer 1: Validate input
        _validate_path_component(phase, "phase")

        # Layer 2: Build path
        output_dir = self.session_dir / phase

        # Layer 3: Belt-and-suspenders containment check
        _validate_path_within_base(output_dir, self.base_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
```

## Attack Vectors to Test

| Attack Vector | Example | Defense |
|--------------|---------|---------|
| Basic traversal | `../../../etc/passwd` | Allowlist regex blocks `/` |
| Null byte injection | `session\x00../evil` | Explicit null byte check |
| Absolute path | `/etc/passwd` | Block leading `/` |
| Home expansion | `~/secret` | Block leading `~` |
| Windows backslash | `..\..\etc` | Block `\\` |
| Double encoding | `....//etc` | Allowlist regex blocks `.` and `/` |
| Unicode slashes | `session\u2215secret` | Allowlist rejects non-ASCII |
| Symlink attack | Symlink to external target | `resolve()` follows symlinks, containment check catches escape |
| Hidden files | `.bashrc` | Block leading `.` in filenames |

## OWASP References

1. **Path Traversal (CWE-22)**: https://owasp.org/www-community/attacks/Path_Traversal
2. **Input Validation Cheat Sheet**: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
3. **File Upload Cheat Sheet**: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

## Implementation Checklist

- [x] Input validation with allowlist regex for path components
- [x] Null byte rejection
- [x] Absolute path rejection
- [x] Path separator rejection
- [x] Traversal pattern (`..`) rejection
- [x] Path resolution with `Path.resolve()`
- [x] Containment verification against base directory
- [x] Case-insensitive filesystem handling (macOS)
- [x] Defense-in-depth before `shutil.rmtree()`
- [x] Filename validation with hidden file blocking
- [x] Belt-and-suspenders validation at multiple layers

## Current Implementation Status

The `scripts/agentica/agent_handoff.py` file already implements these best practices:

1. **`_validate_path_component()`** - Lines 54-91: Validates session_id, phase parameters
2. **`_validate_filename()`** - Lines 94-127: Validates artifact names
3. **`_validate_path_within_base()`** - Lines 130-160: Containment verification
4. **Defense-in-depth in `cleanup()`** - Lines 492-515: Re-validates before `shutil.rmtree()`

Comprehensive tests exist in `tests/unit/test_agent_handoff_security.py`.

## Sources

- OWASP Path Traversal Prevention
- Python `pathlib` documentation
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory
- Analysis of existing implementation in `agent_handoff.py`
