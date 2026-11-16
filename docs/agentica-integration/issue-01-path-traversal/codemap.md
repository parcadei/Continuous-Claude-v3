# Codemap: Path Traversal Vulnerability in AgentHandoff

**Status:** FIXED
**File:** `scripts/agentica/agent_handoff.py`
**Related Tests:** `tests/unit/test_agent_handoff_security.py`

---

## Summary

The path traversal vulnerability described in `comment.md` has been **fully addressed**. The implementation includes:

1. **Input validation helpers** (lines 47-161)
2. **Validated `__init__`** (lines 178-188)
3. **Validated `get_output_dir`** (lines 202-212)
4. **Validated `write_artifact`** (lines 301-312)
5. **Defense-in-depth `cleanup`** (lines 501-515)

---

## Validation Helpers

### `_validate_path_component(component, component_type)` (lines 54-91)

Validates session_id, phase, and similar path components using an allowlist regex:

```python
SAFE_PATH_COMPONENT = re.compile(r'^[a-zA-Z0-9_\-]+$')
```

**Blocks:**
- Empty strings
- Null bytes (`\x00`)
- Traversal patterns (`..`)
- Absolute paths (`/`, `~`)
- Path separators (`/`, `\`)
- Special characters (anything outside alphanumeric, underscore, hyphen)

### `_validate_filename(name)` (lines 94-127)

Validates artifact filenames with extension support:

```python
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$')
```

**Additional restrictions:**
- Hidden files (starting with `.`) blocked
- Only single extension allowed

### `_validate_path_within_base(path, base)` (lines 130-160)

Belt-and-suspenders containment check after path construction:

```python
def _validate_path_within_base(path: Path, base: Path) -> Path:
    resolved = path.resolve()
    base_resolved = base.resolve()

    # Handle macOS case-insensitive filesystem
    if sys.platform == 'darwin':
        resolved_str = str(resolved).lower()
        base_str = str(base_resolved).lower()
    else:
        resolved_str = str(resolved)
        base_str = str(base_resolved)

    if not (resolved_str.startswith(base_str + os.sep) or resolved_str == base_str):
        raise ValueError(f"Path {path} resolves to {resolved} which escapes base directory")

    return resolved
```

---

## Protected Entry Points

### `__init__` (lines 168-188)

```python
def __init__(self, session_id: str, base_dir: Path | None = None):
    # Validate session_id before use
    self.session_id = _validate_path_component(session_id, "session_id")
    self.base_dir = (base_dir or self.BASE_DIR).resolve()

    # Build session directory path
    self.session_dir = self.base_dir / self.session_id

    # Validate the constructed path stays within base_dir
    _validate_path_within_base(self.session_dir, self.base_dir)

    self.session_dir.mkdir(parents=True, exist_ok=True)
```

### `get_output_dir` (lines 190-212)

```python
def get_output_dir(self, phase: str) -> Path:
    # Validate phase before use
    _validate_path_component(phase, "phase")

    output_dir = self.session_dir / phase

    # Belt-and-suspenders: verify path containment
    _validate_path_within_base(output_dir, self.base_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "artifacts").mkdir(exist_ok=True)
    return output_dir
```

### `write_artifact` (lines 287-312)

```python
def write_artifact(self, phase: str, name: str, content: str) -> Path:
    # Validate filename
    _validate_filename(name)

    # get_output_dir validates phase
    output_dir = self.get_output_dir(phase)
    artifact_path = output_dir / "artifacts" / name

    # Belt-and-suspenders: verify final path
    _validate_path_within_base(artifact_path, self.base_dir)

    artifact_path.write_text(content)
    return artifact_path
```

### `cleanup` (lines 492-515)

```python
def cleanup(self) -> None:
    import shutil

    if self.session_dir.exists():
        # Defense in depth: re-validate before destructive operation
        try:
            _validate_path_within_base(self.session_dir, self.base_dir)
        except ValueError as e:
            raise ValueError(
                f"SECURITY: Refusing to delete directory outside base: {self.session_dir}"
            ) from e

        if not self.session_dir.is_dir():
            raise ValueError(f"Expected directory, got file: {self.session_dir}")

        shutil.rmtree(self.session_dir)
```

---

## Test Coverage

**File:** `tests/unit/test_agent_handoff_security.py` (739 lines)

### Test Classes:

| Class | Coverage |
|-------|----------|
| `TestValidatePathComponentHelper` | Valid inputs, empty string, traversal, absolute paths, tilde, separators, null bytes, special chars |
| `TestValidateFilenameHelper` | Valid filenames, empty, traversal, hidden files, separators, null bytes |
| `TestValidatePathWithinBaseHelper` | Valid subpaths, escaped paths, parent traversal |
| `TestSessionIdPathTraversal` | Basic traversal, deep traversal, absolute path, null byte |
| `TestPhasePathTraversal` | get_output_dir, chain_from, read_summary, write_summary, list_artifacts |
| `TestArtifactNameTraversal` | write_artifact, hidden files, read_artifact, null bytes |
| `TestCleanupPathTraversal` | Valid cleanup, escaped session_dir, symlink attack |
| `TestDoubleEncodingAttacks` | Double dots, backslash, mixed separators, URL encoding |
| `TestUnicodeNormalizationAttacks` | Unicode slash variants, Unicode dot variants |
| `TestKnownAttackVectors` | All 4 attack vectors from original plan |
| `TestValidInputsStillWork` | Valid session_id, phases, artifacts, summaries, full workflow |

---

## Existing Security Patterns in Codebase

### `claude_scope.py` - `_canonicalize_path` (lines 54-89)

Similar pattern used for general file operations:

```python
def _canonicalize_path(path: str, project_dir: str | None = None) -> str:
    resolved = os.path.realpath(os.path.expanduser(path))

    if project_dir:
        allowed = os.path.realpath(os.path.expanduser(project_dir))

        if sys.platform == 'darwin':
            resolved_check = resolved.lower()
            allowed_check = allowed.lower()
        else:
            resolved_check = resolved
            allowed_check = allowed

        if not resolved_check.startswith(allowed_check + os.sep) and resolved_check != allowed_check:
            raise ValueError(f"Path '{path}' escapes project directory")

    return resolved
```

**Related test files:**
- `tests/unit/test_security_path.py` - Tests for `_canonicalize_path`
- `tests/unit/test_security_path_traversal.py` - Path traversal tests for `claude_scope`

---

## Defense Strategy

The fix uses **defense-in-depth** with two layers:

1. **Allowlist validation** - Reject bad input early with strict regex
2. **Containment check** - Verify resolved paths stay within base directory

Both layers must pass. Even if an attacker bypasses the allowlist (e.g., through encoding tricks), the containment check will catch paths that escape.

---

## Attack Vectors Blocked

| Attack | How Blocked |
|--------|-------------|
| `../../../etc/passwd` | `..` detected by allowlist |
| `/etc/passwd` | `/` prefix detected by allowlist |
| `~/secret` | `~` prefix detected by allowlist |
| `session\x00evil` | Null byte detected by allowlist |
| `....//etc` | Non-alphanumeric chars rejected by regex |
| `..\\windows` | `\\` separator detected by allowlist |
| Unicode slashes | Non-ASCII rejected by regex |
| Symlink escape | `resolve()` follows symlinks, containment catches escape |

---

## Verification

Run security tests:

```bash
uv run pytest tests/unit/test_agent_handoff_security.py -v
```

All 42 tests should pass.
