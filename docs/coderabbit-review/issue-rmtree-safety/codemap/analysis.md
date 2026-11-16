# Codemap Analysis: cleanup() Safety in agent_handoff.py

## Summary

The `cleanup()` method at lines 492-515 uses `shutil.rmtree()` for session directory deletion. Defense-in-depth validation is present, re-validating paths before the destructive operation despite earlier validation in `__init__`.

## Key Files

- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/agent_handoff.py` - Main implementation

## 1. cleanup() Method (Lines 492-515)

```python
def cleanup(self) -> None:
    """Remove all handoff data for this session.

    Raises:
        ValueError: If session directory escapes base directory (should never happen
                    if session_id was validated in __init__, but defense-in-depth)
    """
    import shutil

    if self.session_dir.exists():
        # Defense in depth: re-validate before destructive operation
        try:
            _validate_path_within_base(self.session_dir, self.base_dir)
        except ValueError as e:
            # Log this as a security event - should never happen with validated session_id
            raise ValueError(
                f"SECURITY: Refusing to delete directory outside base: {self.session_dir}. "
                f"Original error: {e}"
            ) from e

        if not self.session_dir.is_dir():
            raise ValueError(f"Expected directory, got file: {self.session_dir}")

        shutil.rmtree(self.session_dir)
```

**Safety Measures:**
1. Re-validates `session_dir` against `base_dir` before deletion
2. Checks that target is actually a directory (not file)
3. Raises `ValueError` with "SECURITY" prefix for audit trails

## 2. session_dir Construction (Lines 168-188)

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

**Path Construction Flow:**
1. `session_id` validated via `_validate_path_component()` (lines 54-91)
2. `base_dir` resolved to absolute path
3. `session_dir = base_dir / session_id` (simple join)
4. Final path validated via `_validate_path_within_base()` (lines 130-160)

## 3. Validation Methods

### _validate_path_component() (Lines 54-91)
```python
SAFE_PATH_COMPONENT = re.compile(r'^[a-zA-Z0-9_\-]+$')

def _validate_path_component(component: str, component_type: str = "path component") -> str:
    # Blocks:
    # - Empty strings
    # - Null bytes (\x00)
    # - ".." traversal
    # - Absolute paths (/, ~)
    # - Path separators (/, \)
    # - Characters not matching [a-zA-Z0-9_-]
```

### _validate_filename() (Lines 94-127)
```python
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$')

def _validate_filename(name: str) -> str:
    # Same as above, plus:
    # - Blocks hidden files (starting with .)
    # - Allows single extension (.ext)
```

### _validate_path_within_base() (Lines 130-160)
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

    # Check containment (must be base + separator or equal to base)
    if not (resolved_str.startswith(base_str + os.sep) or resolved_str == base_str):
        raise ValueError(f"Path {path} resolves to {resolved} which escapes base directory {base_resolved}")

    return resolved
```

## 4. Callers of cleanup()

### Production Code
- **None in production** - `cleanup()` is not called by any production code path

### Test Code
| File | Line | Purpose |
|------|------|---------|
| `tests/unit/test_agent_handoff_security.py` | 446 | Normal cleanup test |
| `tests/unit/test_agent_handoff_security.py` | 468 | Test escaped session_dir rejection |
| `tests/unit/test_agent_handoff_security.py` | 503 | Test symlink attack rejection |
| `tests/unit/test_agent_handoff_security.py` | 737 | Integration workflow test |

## 5. Attack Vector Analysis

### Blocked Attack: Path Traversal via session_id
```python
# Blocked at __init__ by _validate_path_component()
AgentHandoff("../../../home/user")  # ValueError: Path traversal
```

### Blocked Attack: Runtime session_dir Mutation
```python
# If attacker mutates session_dir after construction:
handoff = AgentHandoff("valid-session")
handoff.session_dir = Path("/etc")  # Bypass __init__ validation
handoff.cleanup()  # BLOCKED by re-validation in cleanup()
```

### Blocked Attack: Symlink Injection
```python
# If session_dir is a symlink to /etc:
# cleanup() calls resolve() which follows symlinks
# _validate_path_within_base() checks resolved path
# Raises ValueError if resolved path escapes base_dir
```

## 6. Security Assessment

| Check | Status | Implementation |
|-------|--------|----------------|
| Input validation | PASS | Allowlist regex at entry point |
| Path containment | PASS | resolve() + prefix check |
| Defense-in-depth | PASS | Re-validates in cleanup() |
| Symlink handling | PASS | resolve() follows symlinks before check |
| Case sensitivity | PASS | macOS lowercase comparison |
| Directory check | PASS | is_dir() before rmtree() |

## 7. Recommendations

1. **Consider logging** - The "SECURITY" prefix in the error message is good for grep-ability, but actual logging would help incident response

2. **Symlink test coverage** - Existing test at line 503 covers this, but could be more explicit about cross-platform behavior

3. **No production callers** - cleanup() is never called in production. If it were, consider:
   - Adding rate limiting
   - Requiring explicit confirmation for large directories
   - Async deletion with audit trail

## Code Signatures

```python
# Validation functions (module-level)
def _validate_path_component(component: str, component_type: str = "path component") -> str
def _validate_filename(name: str) -> str
def _validate_path_within_base(path: Path, base: Path) -> Path

# Class methods
class AgentHandoff:
    BASE_DIR = Path(".claude/cache/agents")

    def __init__(self, session_id: str, base_dir: Path | None = None)
    def cleanup(self) -> None
```
