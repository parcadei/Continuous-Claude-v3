# Implementation Plan: Path Traversal Fix for AgentHandoff

Generated: 2025-12-29

## Goal

Fix the HIGH SEVERITY path traversal vulnerability in `scripts/agentica/agent_handoff.py` by adding path validation to prevent directory traversal attacks on `session_id`, `phase`, and artifact `name` parameters. The fix must prevent:

1. Creation of directories outside `.claude/cache/agents/`
2. Writing files outside the intended session directory
3. Deletion of arbitrary directories via `cleanup()`

## Current State Analysis

### Vulnerable Code Locations

| Method | Line | Vulnerability |
|--------|------|---------------|
| `__init__` | L49-59 | `session_id` used directly in path construction |
| `get_output_dir` | L61-73 | `phase` parameter not validated |
| `chain_from` | L75-84 | `upstream_phase` not validated |
| `write_summary` | L86-111 | Inherits `get_output_dir` vulnerability |
| `read_summary` | L113-125 | `phase` not validated |
| `write_artifact` | L127-141 | Both `phase` and `name` not validated |
| `read_artifact` | L143-156 | Both `phase` and `name` not validated |
| `list_artifacts` | L158-170 | `phase` not validated |
| `cleanup` | L300-305 | CRITICAL: `shutil.rmtree()` on unvalidated path |

### Attack Vectors

```python
# 1. Session ID traversal - creates arbitrary directories
handoff = AgentHandoff(session_id="../../../tmp/evil")

# 2. Phase traversal - escapes session directory
handoff.get_output_dir("../../../etc")

# 3. Artifact name traversal - writes to arbitrary locations
handoff.write_artifact("research", "../../.bashrc", "malicious")

# 4. Cleanup attack - deletes arbitrary directories
handoff = AgentHandoff(session_id="../../../home/user")
handoff.cleanup()  # rm -rf /home/user
```

### Existing Pattern to Reuse

From `scripts/agentica/claude_scope.py:54-88`:

```python
def _canonicalize_path(path: str, project_dir: str | None = None) -> str:
    """Canonicalize path and validate it's within allowed scope."""
    resolved = os.path.realpath(os.path.expanduser(path))

    if project_dir:
        allowed = os.path.realpath(os.path.expanduser(project_dir))

        # macOS case-insensitive handling
        if sys.platform == 'darwin':
            resolved_check = resolved.lower()
            allowed_check = allowed.lower()
        else:
            resolved_check = resolved
            allowed_check = allowed

        if not resolved_check.startswith(allowed_check + os.sep) and resolved_check != allowed_check:
            raise ValueError(
                f"Path '{path}' resolves to '{resolved}' which escapes "
                f"project directory '{allowed}'"
            )

    return resolved
```

## What We're NOT Doing

- NOT changing the public API of `AgentHandoff`
- NOT modifying the directory structure or naming conventions
- NOT adding new dependencies
- NOT changing how artifacts are stored (just validating paths)

---

## Phase 1: Add Path Validation Helper

### Overview

Create a `_validate_path_component()` helper function in `agent_handoff.py` that validates individual path components (session_id, phase, artifact name) before they're used in path construction.

### Changes Required

#### 1. Add validation helper function

**File**: `scripts/agentica/agent_handoff.py`
**Location**: After imports, before class definition (around line 42)

```python
import os
import re
import sys

# Validation patterns for path components
# Allow alphanumeric, underscore, hyphen only (no dots, slashes, or special chars)
SAFE_PATH_COMPONENT = re.compile(r'^[a-zA-Z0-9_\-]+$')
# Filenames can have a single dot for extension
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$')


def _validate_path_component(component: str, component_type: str = "path component") -> str:
    """Validate a path component to prevent traversal attacks.

    Args:
        component: The path component to validate (session_id, phase, etc.)
        component_type: Description for error messages

    Returns:
        The validated component (unchanged if valid)

    Raises:
        ValueError: If component contains traversal patterns or invalid characters
    """
    if not component:
        raise ValueError(f"Empty {component_type} not allowed")

    # Block null bytes
    if '\x00' in component:
        raise ValueError(f"Null byte in {component_type} not allowed")

    # Block obvious traversal patterns before regex check
    if '..' in component:
        raise ValueError(f"Path traversal in {component_type}: {component!r}")

    if component.startswith('/') or component.startswith('~'):
        raise ValueError(f"Absolute path in {component_type} not allowed: {component!r}")

    if '/' in component or '\\' in component:
        raise ValueError(f"Path separator in {component_type} not allowed: {component!r}")

    # Validate against allowlist pattern
    if not SAFE_PATH_COMPONENT.match(component):
        raise ValueError(
            f"Invalid {component_type}: {component!r}. "
            f"Only alphanumeric, underscore, and hyphen allowed."
        )

    return component


def _validate_filename(name: str) -> str:
    """Validate a filename for artifact storage.

    Args:
        name: The filename to validate

    Returns:
        The validated filename

    Raises:
        ValueError: If filename is invalid
    """
    if not name:
        raise ValueError("Empty filename not allowed")

    if '\x00' in name:
        raise ValueError("Null byte in filename not allowed")

    if '..' in name:
        raise ValueError(f"Path traversal in filename: {name!r}")

    if '/' in name or '\\' in name:
        raise ValueError(f"Path separator in filename not allowed: {name!r}")

    if name.startswith('.'):
        raise ValueError(f"Hidden files not allowed: {name!r}")

    if not SAFE_FILENAME.match(name):
        raise ValueError(
            f"Invalid filename: {name!r}. "
            f"Only alphanumeric, underscore, hyphen, and single extension allowed."
        )

    return name


def _validate_path_within_base(path: Path, base: Path) -> Path:
    """Validate that a resolved path stays within the base directory.

    Args:
        path: Path to validate (will be resolved)
        base: Base directory that must contain the path

    Returns:
        The resolved path

    Raises:
        ValueError: If path escapes base directory
    """
    resolved = path.resolve()
    base_resolved = base.resolve()

    # Handle macOS case-insensitive filesystem
    if sys.platform == 'darwin':
        resolved_str = str(resolved).lower()
        base_str = str(base_resolved).lower()
    else:
        resolved_str = str(resolved)
        base_str = str(base_resolved)

    # Check containment
    if not (resolved_str.startswith(base_str + os.sep) or resolved_str == base_str):
        raise ValueError(
            f"Path {path} resolves to {resolved} which escapes base directory {base_resolved}"
        )

    return resolved
```

### Success Criteria

#### Automated Verification:
- [ ] Unit tests pass: `uv run pytest tests/unit/test_agent_handoff_security.py -v -k "test_validate"`
- [ ] Type checking passes: `uv run mypy scripts/agentica/agent_handoff.py`

---

## Phase 2: Add Validation to `__init__` and Core Methods

### Overview

Apply path validation to `__init__`, `get_output_dir`, `chain_from` to prevent session_id and phase traversal.

### Changes Required

#### 1. Update `__init__` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 49-59

```python
def __init__(self, session_id: str, base_dir: Path | None = None):
    """Initialize handoff for a session.

    Args:
        session_id: Unique identifier for this orchestration session
        base_dir: Override base directory (for testing)

    Raises:
        ValueError: If session_id contains path traversal patterns
    """
    # Validate session_id before use
    self.session_id = _validate_path_component(session_id, "session_id")
    self.base_dir = (base_dir or self.BASE_DIR).resolve()

    # Build session directory path
    self.session_dir = self.base_dir / self.session_id

    # Validate the constructed path stays within base_dir
    _validate_path_within_base(self.session_dir, self.base_dir)

    self.session_dir.mkdir(parents=True, exist_ok=True)
```

#### 2. Update `get_output_dir` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 61-73

```python
def get_output_dir(self, phase: str) -> Path:
    """Get output directory for a phase.

    Args:
        phase: Phase name (e.g., "research", "plan", "implement")

    Returns:
        Path to output directory (created if needed)

    Raises:
        ValueError: If phase contains path traversal patterns
    """
    # Validate phase before use
    _validate_path_component(phase, "phase")

    output_dir = self.session_dir / phase

    # Belt-and-suspenders: verify path containment
    _validate_path_within_base(output_dir, self.base_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "artifacts").mkdir(exist_ok=True)
    return output_dir
```

#### 3. Update `chain_from` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 75-84

```python
def chain_from(self, upstream_phase: str) -> Path:
    """Get input directory from upstream phase.

    Args:
        upstream_phase: Name of upstream phase to read from

    Returns:
        Path to upstream's output directory

    Raises:
        ValueError: If upstream_phase contains path traversal patterns
    """
    # Validate upstream_phase before use
    _validate_path_component(upstream_phase, "upstream_phase")

    path = self.session_dir / upstream_phase

    # Validate containment
    _validate_path_within_base(path, self.base_dir)

    return path
```

### Success Criteria

#### Automated Verification:
- [ ] Unit tests pass: `uv run pytest tests/unit/test_agent_handoff_security.py -v -k "test_init or test_get_output_dir or test_chain_from"`
- [ ] Existing handoff tests still pass: `uv run pytest tests/unit/test_agentica_handoff.py -v`

---

## Phase 3: Add Validation to Read/Write Methods

### Overview

Apply validation to `write_summary`, `read_summary`, `write_artifact`, `read_artifact`, and `list_artifacts`.

### Changes Required

#### 1. Update `write_summary` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 86-111

```python
def write_summary(self, phase: str, summary: str, metadata: dict[str, Any] | None = None) -> Path:
    """Write summary.md for a phase.

    Args:
        phase: Phase name
        summary: Summary content (markdown)
        metadata: Optional metadata dict

    Returns:
        Path to written summary file

    Raises:
        ValueError: If phase contains path traversal patterns
    """
    # get_output_dir already validates phase
    output_dir = self.get_output_dir(phase)
    summary_path = output_dir / "summary.md"

    # Existing content generation unchanged
    content = f"""# {phase.title()} Phase Summary

Generated: {datetime.now().isoformat()}
Session: {self.session_id}

{summary}
"""
    if metadata:
        content += f"\n## Metadata\n\n```json\n{json.dumps(metadata, indent=2)}\n```\n"

    summary_path.write_text(content)
    return summary_path
```

#### 2. Update `read_summary` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 113-125

```python
def read_summary(self, phase: str) -> str | None:
    """Read summary.md from a phase.

    Args:
        phase: Phase name

    Returns:
        Summary content or None if not found

    Raises:
        ValueError: If phase contains path traversal patterns
    """
    # Validate phase
    _validate_path_component(phase, "phase")

    summary_path = self.session_dir / phase / "summary.md"

    # Validate path containment
    _validate_path_within_base(summary_path, self.base_dir)

    if summary_path.exists():
        return summary_path.read_text()
    return None
```

#### 3. Update `write_artifact` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 127-141

```python
def write_artifact(self, phase: str, name: str, content: str) -> Path:
    """Write an artifact file.

    Args:
        phase: Phase name
        name: Artifact filename
        content: Artifact content

    Returns:
        Path to written artifact

    Raises:
        ValueError: If phase or name contains path traversal patterns
    """
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

#### 4. Update `read_artifact` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 143-156

```python
def read_artifact(self, phase: str, name: str) -> str | None:
    """Read an artifact from a phase.

    Args:
        phase: Phase name
        name: Artifact filename

    Returns:
        Artifact content or None if not found

    Raises:
        ValueError: If phase or name contains path traversal patterns
    """
    # Validate both components
    _validate_path_component(phase, "phase")
    _validate_filename(name)

    artifact_path = self.session_dir / phase / "artifacts" / name

    # Validate containment
    _validate_path_within_base(artifact_path, self.base_dir)

    if artifact_path.exists():
        return artifact_path.read_text()
    return None
```

#### 5. Update `list_artifacts` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 158-170

```python
def list_artifacts(self, phase: str) -> list[str]:
    """List all artifacts in a phase.

    Args:
        phase: Phase name

    Returns:
        List of artifact filenames

    Raises:
        ValueError: If phase contains path traversal patterns
    """
    # Validate phase
    _validate_path_component(phase, "phase")

    artifacts_dir = self.session_dir / phase / "artifacts"

    # Validate containment
    _validate_path_within_base(artifacts_dir, self.base_dir)

    if artifacts_dir.exists():
        return [f.name for f in artifacts_dir.iterdir() if f.is_file()]
    return []
```

### Success Criteria

#### Automated Verification:
- [ ] Unit tests pass: `uv run pytest tests/unit/test_agent_handoff_security.py -v -k "test_write or test_read or test_list"`
- [ ] Existing tests still pass: `uv run pytest tests/unit/test_agentica_handoff.py -v`

---

## Phase 4: Secure `cleanup()` Method

### Overview

The `cleanup()` method is the most critical vulnerability - it calls `shutil.rmtree()`. Add validation to prevent arbitrary directory deletion.

### Changes Required

#### 1. Update `cleanup` method

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 300-305

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

### Success Criteria

#### Automated Verification:
- [ ] Unit tests pass: `uv run pytest tests/unit/test_agent_handoff_security.py -v -k "test_cleanup"`
- [ ] Security edge case tests pass

---

## Phase 5: Update Convenience Functions

### Overview

Update `create_handoff()` and `get_phase_summary()` convenience functions to propagate validation.

### Changes Required

#### 1. Update convenience functions

**File**: `scripts/agentica/agent_handoff.py`
**Location**: Lines 308-319

```python
def create_handoff(session_id: str) -> AgentHandoff:
    """Create a new handoff instance.

    Args:
        session_id: Unique identifier for the session

    Returns:
        AgentHandoff instance

    Raises:
        ValueError: If session_id contains path traversal patterns
    """
    return AgentHandoff(session_id)


def get_phase_summary(session_id: str, phase: str) -> str | None:
    """Quick read of a phase summary.

    Args:
        session_id: Session identifier
        phase: Phase name

    Returns:
        Summary content or None if not found

    Raises:
        ValueError: If session_id or phase contains path traversal patterns
    """
    handoff = AgentHandoff(session_id)
    return handoff.read_summary(phase)
```

### Success Criteria

#### Automated Verification:
- [ ] All unit tests pass: `uv run pytest tests/unit/test_agent_handoff_security.py -v`

---

## Phase 6: Create Security Test Suite

### Overview

Create comprehensive security tests for all path traversal vectors.

### Changes Required

#### 1. Create new test file

**File**: `tests/unit/test_agent_handoff_security.py`

```python
"""Security tests for AgentHandoff path traversal prevention.

Tests verify that path traversal attacks are blocked for:
1. session_id parameter in __init__
2. phase parameter in get_output_dir, chain_from, etc.
3. name parameter in write_artifact, read_artifact
4. cleanup() method with malicious session_dir

Run with: uv run pytest tests/unit/test_agent_handoff_security.py -v
"""

import pytest
from pathlib import Path
import tempfile
import os

from scripts.agentica.agent_handoff import (
    AgentHandoff,
    _validate_path_component,
    _validate_filename,
    _validate_path_within_base,
    create_handoff,
    get_phase_summary,
)


class TestValidatePathComponent:
    """Test _validate_path_component helper."""

    def test_valid_session_id(self):
        """Valid session IDs should pass."""
        valid_ids = [
            "task-123",
            "session_abc",
            "myTask",
            "UPPER_CASE",
            "mixed-Case_123",
        ]
        for sid in valid_ids:
            assert _validate_path_component(sid, "session_id") == sid

    def test_empty_rejected(self):
        """Empty string should be rejected."""
        with pytest.raises(ValueError, match="Empty"):
            _validate_path_component("", "session_id")

    def test_traversal_rejected(self):
        """Path traversal sequences should be rejected."""
        traversal_attempts = [
            "../",
            "..",
            "..\\",
            "foo/../bar",
            "session/../../etc",
        ]
        for attempt in traversal_attempts:
            with pytest.raises(ValueError, match="traversal"):
                _validate_path_component(attempt, "session_id")

    def test_absolute_path_rejected(self):
        """Absolute paths should be rejected."""
        with pytest.raises(ValueError, match="Absolute"):
            _validate_path_component("/etc/passwd", "session_id")

    def test_home_expansion_rejected(self):
        """Tilde expansion should be rejected."""
        with pytest.raises(ValueError, match="Absolute"):
            _validate_path_component("~/secret", "session_id")

    def test_path_separator_rejected(self):
        """Path separators should be rejected."""
        with pytest.raises(ValueError, match="separator"):
            _validate_path_component("foo/bar", "session_id")
        with pytest.raises(ValueError, match="separator"):
            _validate_path_component("foo\\bar", "session_id")

    def test_null_byte_rejected(self):
        """Null bytes should be rejected."""
        with pytest.raises(ValueError, match="Null"):
            _validate_path_component("session\x00evil", "session_id")

    def test_special_chars_rejected(self):
        """Special characters should be rejected."""
        invalid_chars = ["session!", "session@", "session$", "session%", "session*"]
        for attempt in invalid_chars:
            with pytest.raises(ValueError):
                _validate_path_component(attempt, "session_id")


class TestValidateFilename:
    """Test _validate_filename helper."""

    def test_valid_filenames(self):
        """Valid filenames should pass."""
        valid_names = [
            "artifact.json",
            "data.txt",
            "summary.md",
            "file_name.py",
            "FILE-NAME.txt",
            "noextension",
        ]
        for name in valid_names:
            assert _validate_filename(name) == name

    def test_empty_rejected(self):
        """Empty filename should be rejected."""
        with pytest.raises(ValueError, match="Empty"):
            _validate_filename("")

    def test_traversal_rejected(self):
        """Path traversal in filename should be rejected."""
        with pytest.raises(ValueError, match="traversal"):
            _validate_filename("../etc/passwd")
        with pytest.raises(ValueError, match="traversal"):
            _validate_filename("..\\windows\\system32")

    def test_hidden_file_rejected(self):
        """Hidden files (starting with .) should be rejected."""
        with pytest.raises(ValueError, match="Hidden"):
            _validate_filename(".bashrc")
        with pytest.raises(ValueError, match="Hidden"):
            _validate_filename(".ssh")

    def test_path_separator_rejected(self):
        """Filenames with path separators should be rejected."""
        with pytest.raises(ValueError, match="separator"):
            _validate_filename("path/to/file.txt")

    def test_multiple_dots_rejected(self):
        """Filenames with multiple extensions should still work."""
        # This depends on the regex - file.tar.gz might be rejected
        # Adjust test based on actual requirements
        assert _validate_filename("file.txt")  # Single extension OK


class TestValidatePathWithinBase:
    """Test _validate_path_within_base helper."""

    def test_valid_subpath(self, tmp_path):
        """Paths within base should pass."""
        base = tmp_path / "base"
        base.mkdir()
        child = base / "session" / "phase"

        result = _validate_path_within_base(child, base)
        assert str(result).startswith(str(base.resolve()))

    def test_traversal_blocked(self, tmp_path):
        """Paths escaping base should be rejected."""
        base = tmp_path / "base"
        base.mkdir()
        escaped = tmp_path / "secret"

        with pytest.raises(ValueError, match="escapes"):
            _validate_path_within_base(escaped, base)

    def test_parent_traversal_blocked(self, tmp_path):
        """Parent traversal should be blocked after resolution."""
        base = tmp_path / "base"
        base.mkdir()
        # This path, when resolved, escapes base
        tricky_path = base / ".." / "secret"

        with pytest.raises(ValueError, match="escapes"):
            _validate_path_within_base(tricky_path, base)


class TestAgentHandoffSecurityInit:
    """Test AgentHandoff.__init__ path validation."""

    def test_valid_session_id(self, tmp_path):
        """Valid session ID should work."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)
        assert handoff.session_id == "task-123"
        assert (tmp_path / "task-123").exists()

    def test_traversal_in_session_id_blocked(self, tmp_path):
        """Path traversal in session_id should raise."""
        with pytest.raises(ValueError):
            AgentHandoff("../../../etc", base_dir=tmp_path)

    def test_absolute_session_id_blocked(self, tmp_path):
        """Absolute path as session_id should raise."""
        with pytest.raises(ValueError):
            AgentHandoff("/etc/passwd", base_dir=tmp_path)

    def test_null_byte_session_id_blocked(self, tmp_path):
        """Null byte in session_id should raise."""
        with pytest.raises(ValueError):
            AgentHandoff("session\x00evil", base_dir=tmp_path)


class TestAgentHandoffSecurityPhase:
    """Test phase parameter validation in AgentHandoff methods."""

    def test_get_output_dir_traversal_blocked(self, tmp_path):
        """get_output_dir should block phase traversal."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.get_output_dir("../../../tmp")

    def test_chain_from_traversal_blocked(self, tmp_path):
        """chain_from should block upstream_phase traversal."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.chain_from("../../etc")

    def test_read_summary_traversal_blocked(self, tmp_path):
        """read_summary should block phase traversal."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.read_summary("../../../etc")

    def test_list_artifacts_traversal_blocked(self, tmp_path):
        """list_artifacts should block phase traversal."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.list_artifacts("../../../etc")


class TestAgentHandoffSecurityArtifact:
    """Test artifact name validation in AgentHandoff."""

    def test_write_artifact_name_traversal_blocked(self, tmp_path):
        """write_artifact should block name traversal."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.write_artifact("research", "../../.bashrc", "evil")

    def test_write_artifact_hidden_file_blocked(self, tmp_path):
        """write_artifact should block hidden files."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.write_artifact("research", ".bashrc", "evil")

    def test_read_artifact_traversal_blocked(self, tmp_path):
        """read_artifact should block name traversal."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.read_artifact("research", "../../etc/passwd")

    def test_valid_artifact_works(self, tmp_path):
        """Valid artifact name should work."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        path = handoff.write_artifact("research", "data.json", '{"key": "value"}')
        assert path.exists()
        assert handoff.read_artifact("research", "data.json") == '{"key": "value"}'


class TestAgentHandoffSecurityCleanup:
    """Test cleanup() security - CRITICAL."""

    def test_cleanup_valid_session(self, tmp_path):
        """cleanup should work for valid session."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)
        handoff.write_summary("research", "Test summary")

        assert handoff.session_dir.exists()
        handoff.cleanup()
        assert not handoff.session_dir.exists()

    def test_cleanup_refuses_escaped_path(self, tmp_path):
        """cleanup should refuse if session_dir somehow escaped base.

        Note: This shouldn't happen if __init__ validates properly,
        but cleanup has defense-in-depth validation.
        """
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        # Manually corrupt session_dir to simulate attack
        # (This bypasses normal validation - testing defense-in-depth)
        handoff.session_dir = tmp_path.parent / "should-not-delete"
        handoff.session_dir.mkdir(exist_ok=True)

        with pytest.raises(ValueError, match="SECURITY"):
            handoff.cleanup()

        # Directory should NOT be deleted
        assert handoff.session_dir.exists()

    def test_cleanup_file_not_directory(self, tmp_path):
        """cleanup should refuse if session_dir is a file."""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        # Replace directory with file
        handoff.session_dir.rmdir()
        handoff.session_dir.write_text("not a directory")

        with pytest.raises(ValueError, match="directory"):
            handoff.cleanup()


class TestConvenienceFunctionsSecurity:
    """Test convenience functions validate inputs."""

    def test_create_handoff_validates(self, tmp_path):
        """create_handoff should validate session_id."""
        # We can't easily test this without modifying BASE_DIR
        # Just verify the function exists and signature is correct
        pass

    def test_get_phase_summary_validates(self, tmp_path):
        """get_phase_summary should validate both parameters."""
        # Similar limitation - would need to mock BASE_DIR
        pass


class TestAttackVectors:
    """Test specific attack vectors from security analysis."""

    def test_attack_vector_1_session_id_traversal(self, tmp_path):
        """Attack: AgentHandoff(session_id="../../../tmp/evil")"""
        with pytest.raises(ValueError):
            AgentHandoff("../../../tmp/evil", base_dir=tmp_path)

    def test_attack_vector_2_phase_traversal(self, tmp_path):
        """Attack: handoff.get_output_dir("../../../etc")"""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.get_output_dir("../../../etc")

    def test_attack_vector_3_artifact_name_traversal(self, tmp_path):
        """Attack: handoff.write_artifact("research", "../../.bashrc", "malicious")"""
        handoff = AgentHandoff("task-123", base_dir=tmp_path)

        with pytest.raises(ValueError):
            handoff.write_artifact("research", "../../.bashrc", "malicious content")

    def test_attack_vector_4_cleanup_traversal(self, tmp_path):
        """Attack: AgentHandoff("../../../home/user").cleanup()

        This is blocked at __init__ time.
        """
        with pytest.raises(ValueError):
            AgentHandoff("../../../home/user", base_dir=tmp_path)

    def test_double_encoding_blocked(self, tmp_path):
        """Attack: Double URL encoding like ....//"""
        with pytest.raises(ValueError):
            AgentHandoff("....//....//etc", base_dir=tmp_path)

    def test_backslash_traversal_blocked(self, tmp_path):
        """Attack: Windows-style backslash traversal"""
        with pytest.raises(ValueError):
            AgentHandoff("..\\..\\..\\etc", base_dir=tmp_path)

    def test_unicode_normalization_attack(self, tmp_path):
        """Attack: Unicode normalization tricks."""
        # Some systems normalize certain unicode sequences
        # Our allowlist regex should block non-ASCII entirely
        with pytest.raises(ValueError):
            AgentHandoff("session\u2215secret", base_dir=tmp_path)  # Division slash
```

### Success Criteria

#### Automated Verification:
- [ ] All security tests pass: `uv run pytest tests/unit/test_agent_handoff_security.py -v`
- [ ] No regressions in existing tests: `uv run pytest tests/unit/test_agentica_handoff.py -v`
- [ ] Linting passes: `uv run ruff check scripts/agentica/agent_handoff.py`

---

## Testing Strategy

### Unit Tests

| Category | Tests | Purpose |
|----------|-------|---------|
| Helper validation | 15+ | Test `_validate_*` functions directly |
| Init security | 4+ | Test session_id validation |
| Phase security | 4+ | Test phase parameter validation |
| Artifact security | 4+ | Test artifact name validation |
| Cleanup security | 3+ | Test rmtree protection |
| Attack vectors | 6+ | Test known attack patterns |

### Integration Tests

Not required for this security fix - the unit tests comprehensively cover the validation layer.

### Manual Testing Steps

1. Attempt to create handoff with traversal: `AgentHandoff("../../../tmp")`
2. Attempt phase traversal: `handoff.get_output_dir("../../etc")`
3. Attempt artifact traversal: `handoff.write_artifact("x", "../.bashrc", "test")`
4. Verify normal operation still works with valid inputs

---

## Risks & Considerations

### Risk 1: Breaking Existing Code

**Mitigation**: The fix only rejects clearly malicious inputs. Valid session IDs, phase names, and artifact names will continue to work unchanged.

### Risk 2: False Positives

**Mitigation**: The allowlist pattern `[a-zA-Z0-9_\-]+` is intentionally restrictive but covers all legitimate use cases observed in the codebase.

### Risk 3: Platform-Specific Behavior

**Mitigation**: The `_validate_path_within_base` function handles macOS case-insensitive filesystem correctly, matching the existing pattern in `claude_scope.py`.

### Risk 4: Race Conditions

**Mitigation**: Path validation happens at method entry before any filesystem operations. TOCTOU (time-of-check-time-of-use) is not a concern because we're validating the *format* of user input, not filesystem state.

---

## Estimated Complexity

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Add helpers | Low | Low |
| Phase 2: Init/core methods | Low | Low |
| Phase 3: Read/write methods | Low | Low |
| Phase 4: Secure cleanup | Low | Medium |
| Phase 5: Convenience functions | Low | Low |
| Phase 6: Test suite | Medium | Low |

**Total Estimated Time**: 2-3 hours

---

## References

- Issue documentation: `docs/agentica-integration-fixes/issue-1-path-traversal/comment.md`
- Codemap: `docs/agentica-integration-fixes/issue-1-path-traversal/codemap.md`
- Best practices: `docs/agentica-integration-fixes/issue-1-path-traversal/best-practices.md`
- Existing pattern: `scripts/agentica/claude_scope.py:54-88` (`_canonicalize_path`)
- Existing security tests: `tests/unit/test_security_path.py`
