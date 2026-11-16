# Issue 01: Path Traversal Vulnerability in AgentHandoff

**Severity:** HIGH
**Files:** `scripts/agentica/agent_handoff.py`
**Lines:** 55-59, 69-73, 127-141, 299-305

## Summary

The `AgentHandoff` class uses `session_id`, `phase`, and artifact `name` parameters directly in path construction without validation. If any of these contain path traversal sequences like `../`, files can be read, written, or deleted outside the intended `.claude/cache/agents/` directory.

## Critical Concerns

1. **session_id** used directly in path construction (lines 55-59)
2. **phase** used directly in `get_output_dir` (lines 69-73)
3. **artifact name** used directly in `write_artifact` (lines 127-141)
4. **cleanup()** calls `shutil.rmtree()` on unvalidated `session_dir` (lines 299-305)

## CodeRabbit Proposed Fix

```python
def write_artifact(self, phase: str, name: str, content: str) -> Path:
    # Validate artifact name to prevent path traversal
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"Invalid artifact name: {name}")
    output_dir = self.get_output_dir(phase)
    artifact_path = output_dir / "artifacts" / name
    artifact_path.write_text(content)
    return artifact_path
```

```python
def cleanup(self) -> None:
    """Remove all handoff data for this session."""
    import shutil

    # Safety check: ensure path is within BASE_DIR
    if self.session_dir.exists() and self.session_dir.is_relative_to(self.base_dir):
        shutil.rmtree(self.session_dir)
    else:
        raise ValueError(f"Refusing to delete path outside base_dir: {self.session_dir}")
```

## Fix Requirements

1. Validate session_id, phase, and name parameters
2. Reject or normalize names containing path separators or parent references
3. Ensure resolved paths are inside intended output directory
4. Add safety check to cleanup() before shutil.rmtree
5. Add unit tests for path traversal prevention
