# Path Traversal Prevention Best Practices for Python

## Executive Summary

Path traversal (also known as directory traversal or dot-dot-slash attacks) allows attackers to access files and directories outside the intended scope. This document covers Python-specific prevention patterns for the path traversal vulnerability identified in `scripts/agentica/agent_handoff.py`.

## Research Sources

- OWASP Path Traversal Prevention Cheat Sheet
- Python `pathlib` and `os.path` documentation
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory
- Python Security Best Practices (PEP 506, secure coding guidelines)

---

## Key Findings

### 1. The Canonical Path Validation Pattern

The gold standard for path traversal prevention in Python:

```python
from pathlib import Path

def safe_path(base_dir: Path, user_input: str) -> Path:
    """Safely resolve a user-provided path within a base directory.

    Args:
        base_dir: The allowed root directory (must be absolute)
        user_input: User-provided path component (potentially malicious)

    Returns:
        Resolved absolute path guaranteed to be within base_dir

    Raises:
        ValueError: If the resolved path escapes base_dir
    """
    # Ensure base is absolute and resolved
    base = base_dir.resolve()

    # Join and resolve the full path (resolves .., symlinks, etc.)
    full_path = (base / user_input).resolve()

    # Verify the resolved path is still within base
    if not full_path.is_relative_to(base):
        raise ValueError(f"Path traversal attempt: {user_input}")

    return full_path
```

**Why this works:**
- `Path.resolve()` canonicalizes the path, resolving `..`, `.`, and symlinks
- `is_relative_to()` (Python 3.9+) verifies containment after resolution
- Works regardless of how the traversal is encoded or obfuscated

### 2. Alternative for Python < 3.9

```python
import os
from pathlib import Path

def safe_path_legacy(base_dir: Path, user_input: str) -> Path:
    """Path validation for Python < 3.9."""
    base = str(base_dir.resolve())
    full_path = (base_dir / user_input).resolve()

    # Use os.path.commonpath for containment check
    try:
        common = os.path.commonpath([base, str(full_path)])
        if common != base:
            raise ValueError(f"Path traversal attempt: {user_input}")
    except ValueError:
        # commonpath raises if paths are on different drives (Windows)
        raise ValueError(f"Path traversal attempt: {user_input}")

    return full_path
```

### 3. Input Validation Layer (Defense in Depth)

Even with canonical path validation, add input validation:

```python
import re

# Allowlist pattern for safe filenames
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
SAFE_PATH_COMPONENT = re.compile(r'^[a-zA-Z0-9_\-]+$')

def validate_artifact_name(name: str) -> str:
    """Validate artifact name before path construction.

    Raises:
        ValueError: If name contains unsafe characters
    """
    if not name:
        raise ValueError("Artifact name cannot be empty")

    if not SAFE_FILENAME.match(name):
        raise ValueError(f"Invalid artifact name: {name}")

    # Explicit dangerous pattern rejection
    if '..' in name or name.startswith('.'):
        raise ValueError(f"Invalid artifact name: {name}")

    return name

def validate_session_id(session_id: str) -> str:
    """Validate session ID format."""
    if not session_id:
        raise ValueError("Session ID cannot be empty")

    if not SAFE_PATH_COMPONENT.match(session_id):
        raise ValueError(f"Invalid session ID: {session_id}")

    return session_id
```

### 4. shutil.rmtree Security Considerations

`shutil.rmtree()` is particularly dangerous with unvalidated paths:

```python
import shutil
from pathlib import Path

def safe_cleanup(base_dir: Path, session_id: str) -> None:
    """Safely clean up a session directory.

    CRITICAL: Validates path before deletion to prevent
    arbitrary directory deletion attacks.
    """
    # Validate session_id first
    session_id = validate_session_id(session_id)

    # Use safe path resolution
    session_dir = safe_path(base_dir, session_id)

    # Additional safety: verify we're still in expected location
    expected_parent = base_dir.resolve()
    if session_dir.parent != expected_parent:
        raise ValueError(f"Unexpected directory structure: {session_dir}")

    # Only delete if directory exists and is a directory
    if session_dir.exists():
        if not session_dir.is_dir():
            raise ValueError(f"Expected directory, got file: {session_dir}")
        shutil.rmtree(session_dir)
```

**Additional rmtree protections:**
- Never call `rmtree` on user-controlled paths without validation
- Consider using `rmtree(path, ignore_errors=False)` to catch permission issues
- Log deletions for audit trail
- Consider "soft delete" (rename to `.deleted-{timestamp}`) for critical data

### 5. OWASP Recommended Defense Layers

From OWASP Path Traversal Prevention:

1. **Validate input** - Allowlist acceptable characters
2. **Canonicalize** - Resolve to absolute path before comparison
3. **Verify containment** - Ensure path stays within allowed directory
4. **Use safe APIs** - Prefer `pathlib` over string concatenation
5. **Least privilege** - Run with minimal filesystem permissions

### 6. Common Attack Vectors to Block

```python
# All of these should be blocked:
TRAVERSAL_PATTERNS = [
    "../",           # Basic traversal
    "..\\",          # Windows variant
    "....//",        # Double encoding
    "%2e%2e%2f",     # URL encoding
    "%2e%2e/",       # Partial URL encoding
    "..%252f",       # Double URL encoding
    "..%c0%af",      # Overlong UTF-8
    "..%c1%9c",      # Overlong UTF-8 variant
]
```

The canonical path validation (using `resolve()` + `is_relative_to()`) handles ALL of these automatically because it operates on the resolved path, not the raw input.

---

## Recommended Fix for agent_handoff.py

Based on the issue in `scripts/agentica/agent_handoff.py`:

```python
from pathlib import Path
import re
import shutil

# Validation patterns
SAFE_PATH_COMPONENT = re.compile(r'^[a-zA-Z0-9_\-]+$')
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-\.]+$')

class AgentHandoff:
    def __init__(self, base_dir: Path, session_id: str):
        # Validate session_id at construction time
        if not SAFE_PATH_COMPONENT.match(session_id):
            raise ValueError(f"Invalid session_id: {session_id}")

        self.base_dir = base_dir.resolve()
        self.session_id = session_id
        self.session_dir = self._safe_path(session_id)

    def _safe_path(self, *components: str) -> Path:
        """Safely join path components within base_dir."""
        path = self.base_dir
        for component in components:
            path = path / component

        resolved = path.resolve()

        if not resolved.is_relative_to(self.base_dir):
            raise ValueError(f"Path traversal attempt: {components}")

        return resolved

    def get_output_dir(self, phase: str) -> Path:
        """Get validated output directory for a phase."""
        if not SAFE_PATH_COMPONENT.match(phase):
            raise ValueError(f"Invalid phase name: {phase}")
        return self._safe_path(self.session_id, phase)

    def write_artifact(self, phase: str, name: str, content: str) -> Path:
        """Write artifact with full path validation."""
        # Validate name
        if not SAFE_FILENAME.match(name):
            raise ValueError(f"Invalid artifact name: {name}")

        # Get safe output directory
        output_dir = self.get_output_dir(phase)
        artifacts_dir = output_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Final path validation
        artifact_path = self._safe_path(
            self.session_id, phase, "artifacts", name
        )

        artifact_path.write_text(content)
        return artifact_path

    def cleanup(self) -> None:
        """Safely remove session directory."""
        # session_dir was validated at construction
        if self.session_dir.exists():
            if not self.session_dir.is_dir():
                raise ValueError(f"Expected directory: {self.session_dir}")

            # Extra paranoia: re-verify containment
            if not self.session_dir.is_relative_to(self.base_dir):
                raise ValueError("Session directory escaped base")

            shutil.rmtree(self.session_dir)
```

---

## Testing Path Traversal Prevention

```python
import pytest
from pathlib import Path

def test_path_traversal_blocked():
    """Verify path traversal attempts are blocked."""
    base = Path("/tmp/test_base")
    handoff = AgentHandoff(base, "valid_session")

    # These should all raise ValueError
    traversal_attempts = [
        ("../etc", "passwd"),
        ("valid", "../../../etc/passwd"),
        ("valid", "..\\..\\windows\\system32"),
        ("valid", "name\x00.txt"),  # Null byte injection
        ("valid", "....//....//etc/passwd"),
    ]

    for phase, name in traversal_attempts:
        with pytest.raises(ValueError):
            handoff.write_artifact(phase, name, "content")

def test_safe_paths_allowed():
    """Verify legitimate paths work."""
    base = Path("/tmp/test_base")
    handoff = AgentHandoff(base, "valid_session")

    # These should work
    safe_cases = [
        ("phase1", "artifact.json"),
        ("phase-2", "file_name.txt"),
        ("PHASE_3", "data.md"),
    ]

    for phase, name in safe_cases:
        path = handoff.write_artifact(phase, name, "content")
        assert path.is_relative_to(base)
```

---

## References

1. **OWASP Path Traversal**: https://owasp.org/www-community/attacks/Path_Traversal
2. **CWE-22**: https://cwe.mitre.org/data/definitions/22.html
3. **Python pathlib**: https://docs.python.org/3/library/pathlib.html
4. **Python Security**: https://python-security.readthedocs.io/

---

## Summary

| Technique | Purpose | Python API |
|-----------|---------|------------|
| Canonicalization | Resolve `..`, symlinks | `Path.resolve()` |
| Containment check | Verify within base | `Path.is_relative_to()` (3.9+) |
| Input validation | Block dangerous chars | Regex allowlist |
| Safe construction | Avoid string concat | `Path / component` |
| Validate at boundary | Early rejection | Constructor validation |

**Key principle**: Always validate paths AFTER resolving them to their canonical form, never trust raw user input.
