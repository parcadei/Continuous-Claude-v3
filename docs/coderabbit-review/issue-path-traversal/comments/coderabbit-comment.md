# CodeRabbit Issue: Path Traversal in Artifact Names

**Severity:** 🟡 Minor (Potential Issue)
**File:** `scripts/agentica/agent_handoff.py` lines 127-141

## Issue Description

The `name` parameter is used directly in path construction without validation. If agent-generated names contain path separators (e.g., `../../../etc/passwd`), this could write files outside the intended artifacts directory.

## Proposed Fix (from CodeRabbit)

```python
def write_artifact(self, phase: str, name: str, content: str) -> Path:
    """Write an artifact file."""
    # Validate artifact name to prevent path traversal
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"Invalid artifact name: {name}")
    output_dir = self.get_output_dir(phase)
    artifact_path = output_dir / "artifacts" / name
    artifact_path.write_text(content)
    return artifact_path
```

## AI Agent Prompt

```
In scripts/agentica/agent_handoff.py around lines 127 to 141, the artifact
filename is used directly which allows path traversal; validate and sanitize the
`name` before writing: reject or normalize names containing path separators or
parent references (e.g., os.path.basename or Path(name).name) to strip
directories, ensure the resolved artifact_path is inside the intended
output_dir/artifacts (compare resolved paths and raise an exception if outside),
create the artifacts directory if missing, and return the safe path; update the
function to raise a clear ValueError for invalid names.
```
