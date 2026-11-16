# Issue 1: Path Traversal Vulnerability (HIGH SEVERITY)

## Location
- `scripts/agentica/agent_handoff.py` lines 55-59, 69-73, 127-141, 299-305

## Description
The `AgentHandoff` class uses `session_id`, `phase`, and artifact `name` parameters directly in path construction without validation. If any contain path traversal sequences like `../`, files can be read, written, or deleted outside the intended `.claude/cache/agents/` directory.

Most critically, the `cleanup()` method calls `shutil.rmtree()` on the unvalidated `session_dir`, which could delete arbitrary directories.

## Proposed Fix
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

## Impact
- Security vulnerability that contradicts PR claims of "path traversal protection"
- Could allow arbitrary file deletion via `cleanup()`
- Could allow writing files outside intended directory
