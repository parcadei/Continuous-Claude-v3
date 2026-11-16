# Path Traversal Prevention Research Findings

**Date:** 2025-12-29
**Issue:** CodeRabbit path traversal in artifact names
**File:** `scripts/agentica/agent_handoff.py`

## Executive Summary

The codebase already has comprehensive path traversal protection implemented. This document summarizes best practices and confirms the current implementation aligns with OWASP recommendations.

## OWASP Recommendations

### CWE-22: Improper Limitation of Pathname to Restricted Directory

**Core Defense Strategy (Defense in Depth):**

1. **Input Validation (Allowlist)** - Validate input against strict patterns
2. **Canonicalization** - Resolve paths to absolute form before validation
3. **Containment Check** - Verify resolved path stays within allowed directory

### Key OWASP Guidelines

| Technique | Description | Current Implementation |
|-----------|-------------|------------------------|
| Allowlist validation | Only permit known-safe characters | `SAFE_PATH_COMPONENT` regex: `^[a-zA-Z0-9_\-]+$` |
| Reject `..` sequences | Block parent directory references | Explicit check: `if '..' in component` |
| Reject path separators | Block `/` and `\` in components | Explicit check in `_validate_path_component` |
| Canonicalize paths | Use `realpath()` or `resolve()` | `Path.resolve()` in `_validate_path_within_base` |
| Containment validation | Verify path stays in base directory | `startswith(base_str + os.sep)` check |
| Block null bytes | Prevent null byte injection | `if '\x00' in component` check |

## Python pathlib Best Practices

### Path.resolve() vs os.path.realpath()

| Method | Behavior | Recommendation |
|--------|----------|----------------|
| `Path.resolve()` | Resolves symlinks, makes absolute | Preferred for modern Python |
| `os.path.realpath()` | Resolves symlinks, makes absolute | Equivalent, legacy API |
| `Path.absolute()` | Makes absolute, does NOT resolve symlinks | Avoid for security |
| `os.path.abspath()` | Makes absolute, does NOT resolve symlinks | Avoid for security |

**Current implementation correctly uses `Path.resolve()`** which resolves symlinks and makes paths absolute.

### Recommended Validation Pattern

```python
def validate_safe_path(user_input: str, base_dir: Path) -> Path:
    """Secure path validation pattern."""
    # 1. Reject obviously malicious input early
    if not user_input:
        raise ValueError("Empty path")
    if '\x00' in user_input:
        raise ValueError("Null byte in path")
    if '..' in user_input:
        raise ValueError("Parent traversal not allowed")
    if user_input.startswith(('/', '~')):
        raise ValueError("Absolute paths not allowed")
    if '/' in user_input or '\\' in user_input:
        raise ValueError("Path separators not allowed")

    # 2. Validate against allowlist
    if not re.match(r'^[a-zA-Z0-9_\-]+$', user_input):
        raise ValueError("Invalid characters")

    # 3. Construct and resolve path
    candidate = base_dir / user_input
    resolved = candidate.resolve()
    base_resolved = base_dir.resolve()

    # 4. Containment check (with platform awareness)
    if not str(resolved).startswith(str(base_resolved) + os.sep):
        raise ValueError(f"Path escapes base directory")

    return resolved
```

## Common Path Traversal Bypass Techniques

The current implementation defends against all known bypass techniques:

| Attack Vector | Defense in Current Code |
|---------------|-------------------------|
| Basic `../` | Explicit `..` check |
| Double encoding `%2e%2e%2f` | Allowlist regex blocks `%` |
| Null byte injection `file\x00.txt` | Explicit null byte check |
| Unicode normalization (fullwidth slash) | Allowlist blocks non-ASCII |
| Mixed separators `..\/..` | Blocks both `/` and `\` |
| URL encoding | Allowlist blocks `%` character |
| Overlong UTF-8 | Allowlist blocks non-ASCII |
| Symlink attacks | `resolve()` follows symlinks, containment check validates |
| Case sensitivity bypass | macOS handling with `lower()` comparison |

## Current Implementation Analysis

The implementation in `agent_handoff.py` follows a defense-in-depth approach:

### Layer 1: Input Validation (`_validate_path_component`)
- Rejects empty strings
- Blocks null bytes
- Blocks `..` sequences
- Blocks absolute paths (`/` or `~` prefix)
- Blocks path separators (`/` and `\`)
- Allowlist regex `^[a-zA-Z0-9_\-]+$`

### Layer 2: Filename Validation (`_validate_filename`)
- All checks from Layer 1
- Blocks hidden files (`.` prefix)
- Allows single extension via `^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$`

### Layer 3: Path Containment (`_validate_path_within_base`)
- Resolves both candidate and base paths
- Handles macOS case-insensitive filesystem
- Verifies containment with separator-aware check

### Layer 4: Defense at Call Sites
- `session_id` validated in `__init__`
- `phase` validated in `get_output_dir`, `chain_from`, etc.
- `name` validated in `write_artifact`, `read_artifact`
- `cleanup()` validates `session_dir` before `rmtree`

## Test Coverage Analysis

The test file `tests/unit/test_agent_handoff_security.py` provides comprehensive coverage:

| Test Category | Coverage |
|---------------|----------|
| Helper function validation | `TestValidatePathComponentHelper`, `TestValidateFilenameHelper`, `TestValidatePathWithinBaseHelper` |
| Session ID attacks | `TestSessionIdPathTraversal` |
| Phase parameter attacks | `TestPhasePathTraversal` |
| Artifact name attacks | `TestArtifactNameTraversal` |
| Cleanup security | `TestCleanupPathTraversal` |
| Encoding attacks | `TestDoubleEncodingAttacks` |
| Unicode attacks | `TestUnicodeNormalizationAttacks` |
| Known attack vectors | `TestKnownAttackVectors` |
| Regression tests | `TestValidInputsStillWork` |

## Recommended Additional Test Cases

Consider adding these edge cases:

```python
def test_very_long_path_component():
    """Prevent DoS via extremely long path components."""
    long_name = "a" * 10000
    with pytest.raises(ValueError):
        _validate_path_component(long_name, "session_id")

def test_reserved_names_windows():
    """Block Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)."""
    reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
    for name in reserved:
        with pytest.raises(ValueError):
            _validate_path_component(name, "filename")

def test_trailing_dots_spaces():
    """Block trailing dots/spaces (Windows truncates these)."""
    with pytest.raises(ValueError):
        _validate_filename("file.txt.")
    with pytest.raises(ValueError):
        _validate_filename("file.txt ")
```

## CodeRabbit Recommendation vs Current Implementation

| CodeRabbit Suggestion | Current Implementation | Status |
|-----------------------|------------------------|--------|
| Reject `/` and `\` | `_validate_path_component` and `_validate_filename` | Implemented |
| Reject `.` prefix | `_validate_filename` blocks hidden files | Implemented |
| Use `os.path.basename` | Allowlist approach is more secure | Better approach |
| Compare resolved paths | `_validate_path_within_base` | Implemented |
| Create artifacts dir | `get_output_dir` creates directories | Implemented |
| Raise ValueError | All validation functions raise ValueError | Implemented |

## Conclusion

The current implementation in `agent_handoff.py` already addresses the CodeRabbit security finding with a comprehensive defense-in-depth approach that exceeds the basic recommendations. The implementation:

1. Uses allowlist validation (more secure than blocklist)
2. Applies validation at multiple layers
3. Handles platform-specific edge cases (macOS case sensitivity)
4. Has comprehensive test coverage
5. Protects against known bypass techniques

No additional code changes are required. The CodeRabbit finding appears to be based on an earlier version of the code before security fixes were applied.

## References

- OWASP Path Traversal: https://owasp.org/www-community/attacks/Path_Traversal
- CWE-22: https://cwe.mitre.org/data/definitions/22.html
- Python pathlib documentation: https://docs.python.org/3/library/pathlib.html
- Python os.path documentation: https://docs.python.org/3/library/os.path.html
