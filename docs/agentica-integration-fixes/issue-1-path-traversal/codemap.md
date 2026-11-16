# Path Traversal Security Codemap

## Issue Summary

`AgentHandoff` in `scripts/agentica/agent_handoff.py` lacks path validation, allowing attackers to:
1. Create directories outside the allowed base via `get_output_dir("../../../etc")`
2. Delete arbitrary directories via `cleanup()` with `shutil.rmtree()`

---

## 1. Vulnerable File: `agent_handoff.py`

**Location:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/agent_handoff.py`

### Class Structure

```python
class AgentHandoff:
    BASE_DIR = Path(".claude/cache/agents")  # L47

    def __init__(self, session_id: str, base_dir: Path | None = None):  # L49
        self.session_id = session_id       # UNTRUSTED INPUT - no validation
        self.base_dir = base_dir or self.BASE_DIR
        self.session_dir = self.base_dir / session_id  # Path join with untrusted input
        self.session_dir.mkdir(parents=True, exist_ok=True)  # Creates arbitrary dirs
```

### Vulnerable Methods

#### `get_output_dir(phase: str)` - L61-73

```python
def get_output_dir(self, phase: str) -> Path:
    output_dir = self.session_dir / phase  # No validation on `phase`
    output_dir.mkdir(parents=True, exist_ok=True)  # Creates arbitrary directories
    (output_dir / "artifacts").mkdir(exist_ok=True)
    return output_dir
```

**Attack Vector:**
```python
handoff = AgentHandoff(session_id="task-123")
handoff.get_output_dir("../../../tmp/malicious")  # Creates /tmp/malicious/artifacts
```

#### `chain_from(upstream_phase: str)` - L75-84

```python
def chain_from(self, upstream_phase: str) -> Path:
    return self.session_dir / upstream_phase  # No validation
```

**Attack Vector:**
```python
handoff.chain_from("../../../etc")  # Returns path to /etc
```

#### `write_summary(phase: str, ...)` - L86-111

```python
def write_summary(self, phase: str, summary: str, metadata: dict[str, Any] | None = None) -> Path:
    output_dir = self.get_output_dir(phase)  # Inherits vulnerability
    summary_path = output_dir / "summary.md"
    summary_path.write_text(content)  # Writes to arbitrary location
    return summary_path
```

#### `write_artifact(phase: str, name: str, ...)` - L127-141

```python
def write_artifact(self, phase: str, name: str, content: str) -> Path:
    output_dir = self.get_output_dir(phase)
    artifact_path = output_dir / "artifacts" / name  # `name` also unvalidated
    artifact_path.write_text(content)  # Double traversal possible
    return artifact_path
```

**Attack Vector:**
```python
handoff.write_artifact("research", "../../.bashrc", "malicious content")
```

#### `cleanup()` - L300-305 (CRITICAL)

```python
def cleanup(self) -> None:
    import shutil
    if self.session_dir.exists():
        shutil.rmtree(self.session_dir)  # Deletes arbitrary directory tree
```

**Attack Vector:**
```python
handoff = AgentHandoff(session_id="../../../home/user")
handoff.cleanup()  # Deletes /home/user recursively
```

---

## 2. Existing Path Validation Pattern: `_canonicalize_path`

**Location:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/claude_scope.py` (L54-88)

### Implementation

```python
def _canonicalize_path(path: str, project_dir: str | None = None) -> str:
    """Canonicalize path and validate it's within allowed scope.

    Args:
        path: User-provided path (may contain ../ or symlinks)
        project_dir: If set, paths must resolve within this directory

    Returns:
        Canonicalized absolute path

    Raises:
        ValueError: If path escapes project_dir bounds
    """
    # Expand ~ and resolve symlinks/..
    resolved = os.path.realpath(os.path.expanduser(path))

    if project_dir:
        allowed = os.path.realpath(os.path.expanduser(project_dir))

        # On macOS (case-insensitive), normalize case for comparison
        if sys.platform == 'darwin':
            resolved_check = resolved.lower()
            allowed_check = allowed.lower()
        else:
            resolved_check = resolved
            allowed_check = allowed

        # Ensure resolved path starts with allowed directory
        if not resolved_check.startswith(allowed_check + os.sep) and resolved_check != allowed_check:
            raise ValueError(
                f"Path '{path}' resolves to '{resolved}' which escapes "
                f"project directory '{allowed}'"
            )

    return resolved
```

### Key Features

1. **Symlink resolution**: Uses `os.path.realpath()` to follow symlinks
2. **Tilde expansion**: Handles `~/` paths
3. **Parent traversal**: Resolves `../` sequences
4. **Case sensitivity**: Handles macOS case-insensitive filesystems
5. **Bounds checking**: Validates path stays within `project_dir`

---

## 3. Usage Pattern in `unified_scope.py`

**Location:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/unified_scope.py` (L71-82)

```python
def read_file(path: str) -> dict[str, Any]:
    """Read a file using Claude CLI with shared cache."""
    # Validate path first
    try:
        path = _canonicalize_path(path, project_dir)
    except ValueError as e:
        return {
            "success": False,
            "path": path,
            "content": None,
            "error": str(e),
        }
    # ... proceed with validated path
```

---

## 4. Existing Security Tests

### Test File 1: `test_security_path.py`

**Location:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_security_path.py`

Key test classes:
- `TestCanonicalizePathHelper` - Tests `_canonicalize_path()` directly
- `TestReadFilePathValidation` - Tests path validation in `create_claude_scope()`
- `TestWriteFilePathValidation` - Tests write operations
- `TestEditFilePathValidation` - Tests edit operations
- `TestSharedContextPathValidation` - Tests shared context wiring
- `TestUnifiedScopePathValidation` - Tests unified scope wiring
- `TestPathSecurityEdgeCases` - Edge cases (empty, null bytes, unicode)

### Test File 2: `test_security_path_traversal.py`

**Location:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_security_path_traversal.py`

Key tests:
- `test_path_traversal_blocked` - Blocks `../../../etc/passwd`
- `test_symlink_traversal_blocked` - Blocks symlinks escaping project
- `test_nested_symlinks_blocked` - Blocks symlink chains
- `test_double_dot_in_middle_blocked` - Blocks `subdir/../../etc`
- `test_absolute_path_outside_project_blocked` - Blocks `/etc/passwd`

---

## 5. Recommended Fix

### Step 1: Add `_validate_phase` helper

```python
def _validate_phase(phase: str, base_dir: Path) -> Path:
    """Validate phase name and return safe path.

    Raises:
        ValueError: If phase contains path traversal or escapes base_dir
    """
    # Block obvious traversal patterns
    if ".." in phase or phase.startswith("/") or phase.startswith("~"):
        raise ValueError(f"Invalid phase name: {phase}")

    # Build candidate path
    candidate = (base_dir / phase).resolve()

    # Ensure it's within base_dir
    base_resolved = base_dir.resolve()
    if not str(candidate).startswith(str(base_resolved) + os.sep):
        raise ValueError(f"Phase '{phase}' escapes base directory")

    return candidate
```

### Step 2: Apply to all methods

- `__init__`: Validate `session_id`
- `get_output_dir`: Validate `phase`
- `chain_from`: Validate `upstream_phase`
- `write_artifact`: Validate both `phase` and `name`
- `cleanup`: Ensure `session_dir` is within `base_dir` before rmtree

### Step 3: Add tests in `test_agent_handoff_security.py`

Test vectors:
- `session_id="../../../etc"`
- `phase="../../tmp"`
- `name="../../.bashrc"`
- Symlink attacks on session_dir
- cleanup() on traversed path

---

## 6. Files to Modify

| File | Change |
|------|--------|
| `scripts/agentica/agent_handoff.py` | Add `_validate_phase()`, apply to all methods |
| `tests/unit/test_agent_handoff_security.py` | New file with security tests |

---

## 7. Cross-References

- `_canonicalize_path` defined in: `scripts/agentica/claude_scope.py:54`
- Used in `unified_scope.py:75` for file operations
- Test patterns in: `tests/unit/test_security_path*.py`
