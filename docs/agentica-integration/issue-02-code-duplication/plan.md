# Implementation Plan: Refactor claude_scope.py Code Duplication

Generated: 2025-12-29

## Goal

Eliminate ~800 lines of code duplication between `create_claude_scope()` (L276-690) and `create_claude_scope_with_shared()` (L693-1091) in `claude_scope.py` by applying the CacheManager protocol pattern already proven in `unified_scope.py`.

**Success Criteria:**
- Reduce claude_scope.py from ~1091 lines to ~400 lines
- All 43 existing tests pass unchanged
- SharedContext remains backward compatible
- No circular imports

---

## Current State Analysis

### File: `scripts/agentica/claude_scope.py` (1091 lines)

| Component | Lines | Purpose |
|-----------|-------|---------|
| Imports + helpers | L1-137 | `_run_async`, `_canonicalize_path`, `ClaudeResult` |
| SharedContext | L139-208 | Thread-safe cache (already implements CacheManager protocol) |
| Broadcast functions | L210-273 | `broadcast_finding`, `broadcast_blocker`, `broadcast_done` |
| **create_claude_scope** | L276-690 (414 lines) | Local dict caching |
| **create_claude_scope_with_shared** | L693-1091 (398 lines) | SharedContext caching |

### Difference Analysis

The two factory functions are **99% identical**. The only differences:

| Operation | create_claude_scope | create_claude_scope_with_shared |
|-----------|---------------------|--------------------------------|
| Cache get | `file_cache.get(path)` | `shared.get_cached(path)` |
| Cache set | `file_cache[path] = result` | `shared.set_cached(path, result)` |
| Invalidate | `del file_cache[path]` | `shared.invalidate(path)` |
| Log | `operation_log.append(...)` | `shared.log_operation(...)` |
| Returns | 10 functions + 3 broadcast | 7 functions + shared ref |

### Solution: unified_scope.py Already Has the Pattern

`unified_scope.py` (L43-530) correctly implements:
1. `CacheManager` Protocol (L43-81)
2. `LocalCacheManager` class (L83-129)
3. Single `_create_file_ops(cache_manager)` factory (L154-482)
4. Thin wrappers: `_create_file_ops_with_shared()` and `_create_file_ops_default()`

**Key Insight:** `SharedContext` in claude_scope.py already implements the CacheManager protocol via structural typing - no changes needed.

---

## What We're NOT Doing

- NOT modifying SharedContext class (already implements CacheManager)
- NOT changing the public API of create_claude_scope() or create_claude_scope_with_shared()
- NOT modifying unified_scope.py (it's already correct)
- NOT changing test files (they should pass as-is)
- NOT adding new dependencies

---

## Implementation Approach

**Strategy: Import and Reuse from unified_scope.py**

Since unified_scope.py already has the refactored `_create_file_ops()` factory and imports from claude_scope.py, we can:

1. Import `_create_file_ops` and `LocalCacheManager` from unified_scope.py
2. Replace ~800 lines of duplicate file ops with thin wrappers
3. Maintain backward compatibility by keeping the same function signatures

**Alternative (if circular imports occur):** Inline the pattern by moving `_create_file_ops` to claude_scope.py and have unified_scope.py import from there.

---

## Phase 1: Verify No Circular Import

### Overview
Test that importing from unified_scope.py doesn't cause circular imports.

### Steps:

#### 1.1 Create test script

**File:** (temporary, in workspace/)

```python
# Test import order
from scripts.agentica.claude_scope import SharedContext, ClaudeResult
from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager
print("No circular import!")
```

#### 1.2 Run test

```bash
uv run python -c "
from scripts.agentica.claude_scope import SharedContext, ClaudeResult
from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager
print('No circular import!')
"
```

### Success Criteria:

#### Automated Verification:
- [ ] Import test passes without ImportError
- [ ] No circular import warning

#### Decision Point:
- If circular import occurs, proceed with Phase 1B (inline pattern)
- If no circular import, proceed to Phase 2

---

## Phase 1B: Handle Circular Import (if needed)

### Overview
If circular imports occur, move `_create_file_ops` to claude_scope.py and have unified_scope.py import from there.

### Steps:

#### 1B.1 Move CacheManager Protocol to claude_scope.py

Add after SharedContext class (around L209):

```python
from typing import Protocol

class CacheManager(Protocol):
    """Protocol for cache/log operations in file ops factory."""

    def get_cached(self, path: str) -> ClaudeResult | None:
        ...

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        ...

    def invalidate(self, path: str) -> None:
        ...

    def log_operation(self, operation: dict[str, Any]) -> None:
        ...

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        ...

    def get_all_operations(self) -> list[dict[str, Any]]:
        ...

    def clear_cache(self) -> None:
        ...
```

#### 1B.2 Move LocalCacheManager to claude_scope.py

Add after CacheManager Protocol:

```python
class LocalCacheManager:
    """Cache manager with local dict storage for single-agent use."""

    def __init__(self, cache_reads: bool = True):
        self._cache_reads = cache_reads
        self._cache: dict[str, ClaudeResult] = {}
        self._operations: list[dict[str, Any]] = []

    def get_cached(self, path: str) -> ClaudeResult | None:
        if not self._cache_reads:
            return None
        return self._cache.get(path)

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        if self._cache_reads:
            self._cache[path] = result

    def invalidate(self, path: str) -> None:
        self._cache.pop(path, None)

    def log_operation(self, operation: dict[str, Any]) -> None:
        self._operations.append(operation)

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        return dict(self._cache)

    def get_all_operations(self) -> list[dict[str, Any]]:
        return list(self._operations)

    def clear_cache(self) -> None:
        self._cache.clear()
```

#### 1B.3 Update unified_scope.py imports

Change:
```python
# Remove CacheManager and LocalCacheManager definitions
# Add import:
from scripts.agentica.claude_scope import (
    CacheManager,
    ClaudeResult,
    LocalCacheManager,
    SharedContext,
    _call_claude_cli,
    _canonicalize_path,
)
```

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/unit/test_unified_scope.py -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py -v` passes

---

## Phase 2: Add _create_file_ops Factory to claude_scope.py

### Overview
Add the unified file ops factory function to claude_scope.py.

### Changes Required:

#### 2.1 Add _create_file_ops function

**File:** `scripts/agentica/claude_scope.py`
**Location:** After LocalCacheManager class (before broadcast functions)

```python
def _create_file_ops(
    cache_manager: CacheManager,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with pluggable cache manager.

    Args:
        cache_manager: CacheManager implementation (SharedContext or LocalCacheManager)
        project_dir: Optional project directory for path validation

    Returns:
        Dict of file operation functions
    """

    def read_file(path: str) -> dict[str, Any]:
        """Read a file using Claude CLI."""
        try:
            path = _canonicalize_path(path, project_dir)
        except ValueError as e:
            return {
                "success": False,
                "path": path,
                "content": None,
                "error": str(e),
            }

        cached = cache_manager.get_cached(path)
        if cached:
            return {
                "success": cached.success,
                "path": cached.path,
                "content": cached.content,
                "cached": True,
            }

        prompt = f"""Read the file at: {path}

Return the file content. If the file doesn't exist, explain the error."""

        try:
            response = _call_claude_cli(prompt, ["Read"])

            result = ClaudeResult(
                success=True,
                operation="read",
                path=path,
                content=response,
                raw_response=response,
            )

            cache_manager.set_cached(path, result)
            cache_manager.log_operation({
                "operation": "read",
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "path": path,
                "content": response,
                "cached": False,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "read",
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "path": path,
                "content": None,
                "error": str(e),
            }

    def write_file(path: str, content: str) -> dict[str, Any]:
        """Write content to a file using Claude CLI."""
        try:
            path = _canonicalize_path(path, project_dir)
        except ValueError as e:
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }

        prompt = f"""Write the following content to the file at: {path}

Content to write:
```
{content}
```

Confirm when the file has been written."""

        try:
            response = _call_claude_cli(prompt, ["Write"])

            cache_manager.invalidate(path)
            cache_manager.log_operation({
                "operation": "write",
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "path": path,
                "response": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "write",
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }

    def edit_file(path: str, old_text: str, new_text: str) -> dict[str, Any]:
        """Edit a file by replacing text using Claude CLI."""
        try:
            path = _canonicalize_path(path, project_dir)
        except ValueError as e:
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }

        prompt = f"""Edit the file at: {path}

Find this text:
```
{old_text}
```

Replace it with:
```
{new_text}
```

Confirm when the edit is complete."""

        try:
            response = _call_claude_cli(prompt, ["Read", "Edit"])

            cache_manager.invalidate(path)
            cache_manager.log_operation({
                "operation": "edit",
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "path": path,
                "response": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "edit",
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }

    def bash(command: str, args: list[str] | None = None) -> dict[str, Any]:
        """Run a bash command using Claude CLI."""
        if args:
            quoted_args = " ".join(shlex.quote(arg) for arg in args)
            full_command = f"{command} {quoted_args}"
        else:
            full_command = command

        prompt = f"""Run this bash command:

```bash
{full_command}
```

Return the output."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            cache_manager.log_operation({
                "operation": "bash",
                "command": full_command,
                "success": True,
            })

            return {
                "success": True,
                "command": full_command,
                "output": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "bash",
                "command": full_command,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "command": full_command,
                "output": None,
                "error": str(e),
            }

    def grep(pattern: str, path: str = ".") -> dict[str, Any]:
        """Search for pattern in files using Claude CLI."""
        prompt = f"""Search for the pattern "{pattern}" in {path}

Use grep or similar to find all occurrences.
Return the matching lines with file paths and line numbers."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            cache_manager.log_operation({
                "operation": "grep",
                "pattern": pattern,
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "pattern": pattern,
                "path": path,
                "matches": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "grep",
                "pattern": pattern,
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "pattern": pattern,
                "path": path,
                "matches": None,
                "error": str(e),
            }

    def glob_search(pattern: str) -> dict[str, Any]:
        """Find files matching glob pattern using Claude CLI."""
        prompt = f"""Find all files matching the pattern: {pattern}

List all matching file paths."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            files = [
                line.strip()
                for line in response.split("\n")
                if line.strip() and not line.startswith("#")
            ]

            cache_manager.log_operation({
                "operation": "glob",
                "pattern": pattern,
                "success": True,
                "count": len(files),
            })

            return {
                "success": True,
                "pattern": pattern,
                "files": files,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "glob",
                "pattern": pattern,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "pattern": pattern,
                "files": [],
                "error": str(e),
            }

    def debug_get_cache() -> dict[str, ClaudeResult]:
        """Get the file cache (for debugging/inspection)."""
        return cache_manager.get_all_cached()

    def debug_get_operation_log() -> list[dict[str, Any]]:
        """Get the operation log (for debugging/inspection)."""
        return cache_manager.get_all_operations()

    def debug_clear_cache() -> None:
        """Clear the file cache."""
        cache_manager.clear_cache()

    return {
        "read_file": read_file,
        "write_file": write_file,
        "edit_file": edit_file,
        "bash": bash,
        "grep": grep,
        "glob": glob_search,
        "debug_get_cache": debug_get_cache,
        "debug_get_operation_log": debug_get_operation_log,
        "debug_clear_cache": debug_clear_cache,
    }
```

### Success Criteria:

#### Automated Verification:
- [ ] File compiles without syntax errors: `uv run python -c "from scripts.agentica.claude_scope import _create_file_ops"`

---

## Phase 3: Refactor create_claude_scope()

### Overview
Replace the ~414 lines of create_claude_scope() with a thin wrapper.

### Changes Required:

#### 3.1 Replace create_claude_scope implementation

**File:** `scripts/agentica/claude_scope.py`
**Replace:** Lines 276-690

**New implementation:**

```python
def create_claude_scope(
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create scope with Claude CLI functions.

    Args:
        cache_reads: Whether to cache file reads (default: True)
        project_dir: Optional project directory for relative paths

    Returns:
        Scope dict with callable functions
    """
    if project_dir is None:
        warnings.warn(
            "project_dir=None is deprecated and will be required in a future version. "
            "Set project_dir to enable path validation and prevent traversal attacks.",
            DeprecationWarning,
            stacklevel=2
        )

    # Use LocalCacheManager for single-agent use
    ops = _create_file_ops(LocalCacheManager(cache_reads), project_dir)

    # Add broadcast functions for swarm coordination
    ops.update({
        "broadcast_finding": broadcast_finding,
        "broadcast_blocker": broadcast_blocker,
        "broadcast_done": broadcast_done,
    })

    return ops
```

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestCreateClaudeScope -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestReadFile -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestWriteFile -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestEditFile -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestBash -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestGrepAndGlob -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestOperationLog -v` passes

---

## Phase 4: Refactor create_claude_scope_with_shared()

### Overview
Replace the ~398 lines of create_claude_scope_with_shared() with a thin wrapper.

### Changes Required:

#### 4.1 Replace create_claude_scope_with_shared implementation

**File:** `scripts/agentica/claude_scope.py`
**Replace:** Lines 693-1091 (now ~320-750 after Phase 3)

**New implementation:**

```python
def create_claude_scope_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create scope with shared context for multi-agent coordination.

    Args:
        shared: SharedContext instance to share across agents
        cache_reads: Whether to cache file reads
        project_dir: Optional project directory for path validation

    Returns:
        Scope dict with callable functions using shared context

    Note:
        Functions are synchronous for backward compatibility.
        SharedContext methods are thread-safe using threading.Lock.
    """
    if project_dir is None:
        warnings.warn(
            "project_dir=None is deprecated and will be required in a future version. "
            "Set project_dir to enable path validation and prevent traversal attacks.",
            DeprecationWarning,
            stacklevel=2
        )

    # SharedContext implements CacheManager protocol via structural typing
    # Note: cache_reads parameter is not used here because SharedContext
    # always caches. If cache_reads=False is needed with SharedContext,
    # a wrapper class could be added.
    ops = _create_file_ops(shared, project_dir)

    # Add shared context reference
    ops["shared"] = shared

    return ops
```

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestSharedContext -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestSharedContextIntegration -v` passes
- [ ] `uv run pytest tests/unit/test_claude_scope.py::TestPatternIntegration -v` passes

---

## Phase 5: Update unified_scope.py Imports

### Overview
Update unified_scope.py to import from claude_scope.py instead of duplicating.

### Changes Required:

#### 5.1 Update unified_scope.py imports

**File:** `scripts/agentica/unified_scope.py`
**Replace:** Lines 43-130 (CacheManager and LocalCacheManager definitions)

**New imports:**

```python
from scripts.agentica.claude_scope import (
    CacheManager,
    ClaudeResult,
    LocalCacheManager,
    SharedContext,
    _call_claude_cli,
    _canonicalize_path,
    _create_file_ops,
)
```

#### 5.2 Remove duplicate definitions

Remove from unified_scope.py:
- CacheManager Protocol (L43-81)
- LocalCacheManager class (L83-130)
- _create_file_ops function (L154-482)
- _create_file_ops_with_shared function (L485-510)
- _create_file_ops_default function (L513-530)

#### 5.3 Simplify create_unified_scope

Update to use imported _create_file_ops:

```python
def create_unified_scope(
    session_id: str,
    db_path: Path | None = None,
    enable_memory: bool = True,
    enable_tasks: bool = True,
    shared_context: SharedContext | None = None,
    extra_scope: dict[str, Any] | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create unified scope with file, memory, and task operations."""
    scope: dict[str, Any] = {}

    # 1. Add file operations
    if shared_context is not None:
        file_ops = _create_file_ops(shared_context, project_dir)
    else:
        file_ops = _create_file_ops(LocalCacheManager(), project_dir)

    scope.update(file_ops)

    # ... rest of the function unchanged
```

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/unit/test_unified_scope.py -v` passes
- [ ] `uv run pytest tests/integration/test_unified_scope_e2e.py -v` passes

---

## Phase 6: Final Verification

### Overview
Run all tests and verify line count reduction.

### Steps:

#### 6.1 Run full test suite

```bash
uv run pytest tests/unit/test_claude_scope.py tests/unit/test_unified_scope.py -v
```

#### 6.2 Run integration tests

```bash
uv run pytest tests/integration/test_claude_scope_e2e.py tests/integration/test_unified_scope_e2e.py -v
```

#### 6.3 Verify line count

```bash
wc -l scripts/agentica/claude_scope.py
# Expected: ~400 lines (down from 1091)

wc -l scripts/agentica/unified_scope.py
# Expected: ~200 lines (down from 643)
```

#### 6.4 Type check

```bash
uv run mypy scripts/agentica/claude_scope.py scripts/agentica/unified_scope.py --ignore-missing-imports
```

### Success Criteria:

#### Automated Verification:
- [ ] All unit tests pass: `uv run pytest tests/unit/test_claude_scope.py tests/unit/test_unified_scope.py -v`
- [ ] All integration tests pass: `uv run pytest tests/integration/ -k "claude_scope or unified_scope" -v`
- [ ] claude_scope.py < 500 lines
- [ ] unified_scope.py < 300 lines
- [ ] No mypy errors (with --ignore-missing-imports)

#### Manual Verification:
- [ ] Review git diff to confirm no unintended changes
- [ ] Verify SharedContext API unchanged

---

## Testing Strategy

### Unit Tests (existing, should pass unchanged)

```bash
# All 43 tests in test_claude_scope.py
uv run pytest tests/unit/test_claude_scope.py -v

# All tests in test_unified_scope.py
uv run pytest tests/unit/test_unified_scope.py -v
```

### Integration Tests

```bash
uv run pytest tests/integration/test_claude_scope_e2e.py -v
uv run pytest tests/integration/test_unified_scope_e2e.py -v
```

### Manual Testing

1. Verify create_claude_scope() works as before:
```python
from scripts.agentica.claude_scope import create_claude_scope
scope = create_claude_scope()
assert "read_file" in scope
assert "broadcast_finding" in scope
```

2. Verify create_claude_scope_with_shared() works:
```python
from scripts.agentica.claude_scope import SharedContext, create_claude_scope_with_shared
shared = SharedContext()
scope = create_claude_scope_with_shared(shared)
assert "read_file" in scope
assert scope["shared"] is shared
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Circular import | Medium | High | Phase 1B provides fallback plan |
| Test failures | Low | Medium | Run tests after each phase |
| API breakage | Low | High | Keep exact same function signatures |
| Performance regression | Low | Low | LocalCacheManager is simpler than dict |

---

## Estimated Complexity

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Import test | 5 min | Low |
| Phase 1B: Circular import fix | 30 min | Medium |
| Phase 2: Add _create_file_ops | 15 min | Low |
| Phase 3: Refactor create_claude_scope | 10 min | Low |
| Phase 4: Refactor create_claude_scope_with_shared | 10 min | Low |
| Phase 5: Update unified_scope.py | 20 min | Medium |
| Phase 6: Final verification | 10 min | Low |

**Total: ~1.5 hours**

---

## References

- Issue: `docs/agentica-integration/issue-02-code-duplication/comment.md`
- Codemap: `docs/agentica-integration/issue-02-code-duplication/codemap.md`
- Best practices: `docs/agentica-integration/issue-02-code-duplication/best-practices.md`
- Source files:
  - `scripts/agentica/claude_scope.py` (1091 lines)
  - `scripts/agentica/unified_scope.py` (643 lines)
- Test files:
  - `tests/unit/test_claude_scope.py` (43 tests)
  - `tests/unit/test_unified_scope.py`
  - `tests/integration/test_claude_scope_e2e.py`
  - `tests/integration/test_unified_scope_e2e.py`
