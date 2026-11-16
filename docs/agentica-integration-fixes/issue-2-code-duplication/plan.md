# Implementation Plan: Eliminate Code Duplication in unified_scope.py

Generated: 2025-12-29

## Overview

Refactor `scripts/agentica/unified_scope.py` to eliminate ~350 lines of duplicated code between `_create_file_ops_with_shared()` (L59-404) and `_create_file_ops_default()` (L407-740) by introducing a `CacheManager` Protocol and two concrete implementations.

## Current State Analysis

### The Problem

Two factory functions contain nearly identical implementations of 9 file operations:
- `read_file`, `write_file`, `edit_file`, `bash`, `grep`, `glob_search`
- `debug_get_cache`, `debug_get_operation_log`, `debug_clear_cache`

The only difference is how they access cache and log operations:

| Operation | `_with_shared` | `_default` |
|-----------|----------------|------------|
| Cache get | `shared.get_cached(path)` | `file_cache.get(path)` |
| Cache set | `shared.set_cached(path, result)` | `file_cache[path] = result` |
| Invalidate | `shared.invalidate(path)` | `del file_cache[path]` |
| Log | `shared.log_operation({...})` | `operation_log.append({...})` |
| Get all cached | `shared.get_all_cached()` | `file_cache.copy()` |
| Get all ops | `shared.get_all_operations()` | `operation_log.copy()` |
| Clear cache | `shared.clear_cache()` | `file_cache.clear()` |

### Key Discovery: SharedContext Already Conforms

`SharedContext` in `claude_scope.py` (L139-208) already implements all required methods:
- `get_cached(path)` - L154-157
- `set_cached(path, result)` - L159-162
- `invalidate(path)` - L164-168
- `log_operation(operation)` - L170-173
- `get_all_cached()` - L183-190
- `get_all_operations()` - L192-199
- `clear_cache()` - L201-207

This means we can use Python's structural typing (Protocol) without modifying `SharedContext`.

## Desired End State

1. **Single factory function** `_create_file_ops(cache_manager)` containing all file operation logic
2. **CacheManager Protocol** defining the interface
3. **LocalCacheManager class** implementing the protocol for single-agent use
4. **Thin wrapper functions** for backward compatibility
5. **~350 lines removed** from unified_scope.py

### Verification

```bash
# All tests pass
uv run pytest tests/unit/test_unified_scope.py -v
uv run pytest tests/unit/test_claude_scope.py -v

# Type checking passes
uv run mypy scripts/agentica/unified_scope.py
```

## What We're NOT Doing

- Modifying `SharedContext` class (it already conforms to Protocol)
- Changing the public API of `create_unified_scope()`
- Adding thread-safety to `LocalCacheManager` (intentionally single-agent)
- Adding cache TTL or metrics (out of scope)
- Refactoring `claude_scope.py` (separate concern)

## Implementation Approach

Use Strategy Pattern with Python Protocol for structural typing:
1. Define interface via Protocol (no runtime overhead)
2. Create concrete implementation for local caching
3. SharedContext satisfies Protocol without modification (duck typing)
4. Single factory function accepts any CacheManager
5. Backward-compatible wrappers for gradual migration

---

## Phase 1: Add CacheManager Protocol and LocalCacheManager

### Overview
Add the abstraction layer without modifying any existing functions. This is purely additive and non-breaking.

### Changes Required:

#### 1. Add imports and Protocol definition
**File**: `scripts/agentica/unified_scope.py`
**Location**: After existing imports (around L31)

```python
from typing import Protocol


class CacheManager(Protocol):
    """Protocol for cache/log operations in file ops factory.

    This protocol defines the interface that both SharedContext and
    LocalCacheManager implement, enabling a single _create_file_ops()
    factory to work with either caching strategy.

    SharedContext (claude_scope.py) already implements this interface
    via structural typing - no changes needed there.
    """

    def get_cached(self, path: str) -> ClaudeResult | None:
        """Get cached result for path, or None if not cached."""
        ...

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        """Cache result for path."""
        ...

    def invalidate(self, path: str) -> None:
        """Invalidate cache entry for path (if exists)."""
        ...

    def log_operation(self, operation: dict[str, Any]) -> None:
        """Log an operation."""
        ...

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        """Get copy of all cached results."""
        ...

    def get_all_operations(self) -> list[dict[str, Any]]:
        """Get copy of all logged operations."""
        ...

    def clear_cache(self) -> None:
        """Clear all cached results."""
        ...
```

#### 2. Add LocalCacheManager class
**File**: `scripts/agentica/unified_scope.py`
**Location**: After CacheManager Protocol

```python
class LocalCacheManager:
    """Cache manager with local dict storage for single-agent use.

    Not thread-safe - intentionally designed for single-agent contexts
    where SharedContext's locking overhead is unnecessary.
    """

    def __init__(self, cache_reads: bool = True):
        """Initialize local cache manager.

        Args:
            cache_reads: Whether to cache read operations
        """
        self._cache_reads = cache_reads
        self._cache: dict[str, ClaudeResult] = {}
        self._operations: list[dict[str, Any]] = []

    def get_cached(self, path: str) -> ClaudeResult | None:
        """Get cached result for path."""
        if not self._cache_reads:
            return None
        return self._cache.get(path)

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        """Cache result for path."""
        if self._cache_reads:
            self._cache[path] = result

    def invalidate(self, path: str) -> None:
        """Invalidate cache entry for path."""
        self._cache.pop(path, None)

    def log_operation(self, operation: dict[str, Any]) -> None:
        """Log an operation."""
        self._operations.append(operation)

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        """Get copy of all cached results."""
        return dict(self._cache)

    def get_all_operations(self) -> list[dict[str, Any]]:
        """Get copy of all logged operations."""
        return list(self._operations)

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
```

### Success Criteria:

#### Automated Verification:
- [ ] Type checking passes: `uv run mypy scripts/agentica/unified_scope.py`
- [ ] Existing tests still pass: `uv run pytest tests/unit/test_unified_scope.py -v`
- [ ] Import works: `python -c "from scripts.agentica.unified_scope import CacheManager, LocalCacheManager"`

#### Manual Verification:
- [ ] Review Protocol matches SharedContext method signatures

---

## Phase 2: Add Unified _create_file_ops Factory

### Overview
Create the single factory function that accepts a CacheManager. Keep existing functions unchanged.

### Changes Required:

#### 1. Add new unified factory function
**File**: `scripts/agentica/unified_scope.py`
**Location**: After LocalCacheManager class (before `_create_file_ops_with_shared`)

```python
def _create_file_ops(
    cache_manager: CacheManager,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with pluggable cache manager.

    This is the unified implementation that handles all caching strategies.
    The cache_manager parameter determines whether caching uses shared
    context (inter-agent, thread-safe) or local dict (single agent).

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

    def bash(command: str) -> dict[str, Any]:
        """Run a bash command using Claude CLI."""
        prompt = f"""Run this bash command:

```bash
{command}
```

Return the output."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            cache_manager.log_operation({
                "operation": "bash",
                "command": command,
                "success": True,
            })

            return {
                "success": True,
                "command": command,
                "output": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "bash",
                "command": command,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "command": command,
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
- [ ] Type checking passes: `uv run mypy scripts/agentica/unified_scope.py`
- [ ] Existing tests still pass: `uv run pytest tests/unit/test_unified_scope.py -v`
- [ ] New function can be called with LocalCacheManager:
  ```python
  python -c "
  from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager
  ops = _create_file_ops(LocalCacheManager())
  print('Functions:', list(ops.keys()))
  "
  ```

#### Manual Verification:
- [ ] New `_create_file_ops` function matches behavior of originals

---

## Phase 3: Convert Existing Functions to Thin Wrappers

### Overview
Replace the 350+ line implementations with thin wrappers that delegate to `_create_file_ops`.

### Changes Required:

#### 1. Replace `_create_file_ops_with_shared`
**File**: `scripts/agentica/unified_scope.py`
**Location**: Replace L59-404

```python
def _create_file_ops_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with shared context for multi-agent use.

    This is a thin wrapper around _create_file_ops that uses SharedContext
    as the cache manager. SharedContext provides thread-safe caching
    across multiple agents.

    Note: The cache_reads parameter is handled by SharedContext's methods,
    which always cache (SharedContext doesn't have a cache_reads flag).
    If cache_reads=False is needed with SharedContext, a wrapper class
    could be added, but current usage always has cache_reads=True.

    Args:
        shared: SharedContext for thread-safe multi-agent caching
        cache_reads: Whether to cache read operations (default: True)
        project_dir: Optional project directory for path validation

    Returns:
        Dict of file operation functions using shared context
    """
    # SharedContext implements CacheManager protocol via structural typing
    return _create_file_ops(shared, project_dir)
```

#### 2. Replace `_create_file_ops_default`
**File**: `scripts/agentica/unified_scope.py`
**Location**: Replace L407-740

```python
def _create_file_ops_default(
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with local cache for single-agent use.

    This is a thin wrapper around _create_file_ops that uses LocalCacheManager.
    LocalCacheManager is not thread-safe but has lower overhead for
    single-agent contexts.

    Args:
        cache_reads: Whether to cache read operations (default: True)
        project_dir: Optional project directory for path validation

    Returns:
        Dict of file operation functions with local caching
    """
    return _create_file_ops(LocalCacheManager(cache_reads), project_dir)
```

### Success Criteria:

#### Automated Verification:
- [ ] All existing tests pass: `uv run pytest tests/unit/test_unified_scope.py -v`
- [ ] Integration tests pass: `uv run pytest tests/integration/test_unified_scope_e2e.py -v`
- [ ] Type checking passes: `uv run mypy scripts/agentica/unified_scope.py`
- [ ] Linting passes: `uv run ruff check scripts/agentica/unified_scope.py`

#### Manual Verification:
- [ ] File line count reduced by ~300 lines
- [ ] No functional changes to `create_unified_scope()` behavior

---

## Phase 4: Add Unit Tests for New Classes

### Overview
Add tests specifically for CacheManager protocol compliance and LocalCacheManager behavior.

### Changes Required:

#### 1. Add tests to `tests/unit/test_unified_scope.py`
**File**: `tests/unit/test_unified_scope.py`
**Location**: Add new test class

```python
class TestCacheManagerProtocol:
    """Test that cache managers satisfy the CacheManager protocol."""

    def test_local_cache_manager_implements_protocol(self):
        """LocalCacheManager should implement all CacheManager methods."""
        from scripts.agentica.unified_scope import LocalCacheManager, CacheManager
        from typing import runtime_checkable, Protocol

        manager = LocalCacheManager()

        # Verify all protocol methods exist and are callable
        assert callable(getattr(manager, 'get_cached', None))
        assert callable(getattr(manager, 'set_cached', None))
        assert callable(getattr(manager, 'invalidate', None))
        assert callable(getattr(manager, 'log_operation', None))
        assert callable(getattr(manager, 'get_all_cached', None))
        assert callable(getattr(manager, 'get_all_operations', None))
        assert callable(getattr(manager, 'clear_cache', None))

    def test_shared_context_implements_protocol(self):
        """SharedContext should implement all CacheManager methods."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()

        # Verify all protocol methods exist and are callable
        assert callable(getattr(shared, 'get_cached', None))
        assert callable(getattr(shared, 'set_cached', None))
        assert callable(getattr(shared, 'invalidate', None))
        assert callable(getattr(shared, 'log_operation', None))
        assert callable(getattr(shared, 'get_all_cached', None))
        assert callable(getattr(shared, 'get_all_operations', None))
        assert callable(getattr(shared, 'clear_cache', None))


class TestLocalCacheManager:
    """Test LocalCacheManager behavior."""

    def test_cache_reads_disabled(self):
        """When cache_reads=False, get_cached should always return None."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager(cache_reads=False)
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")

        manager.set_cached("/test", result)
        assert manager.get_cached("/test") is None

    def test_cache_reads_enabled(self):
        """When cache_reads=True (default), caching should work."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")

        manager.set_cached("/test", result)
        cached = manager.get_cached("/test")
        assert cached is not None
        assert cached.content == "data"

    def test_invalidate_removes_entry(self):
        """Invalidate should remove cached entry."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")

        manager.set_cached("/test", result)
        manager.invalidate("/test")
        assert manager.get_cached("/test") is None

    def test_invalidate_nonexistent_is_safe(self):
        """Invalidating a non-existent path should not raise."""
        from scripts.agentica.unified_scope import LocalCacheManager

        manager = LocalCacheManager()
        manager.invalidate("/nonexistent")  # Should not raise

    def test_log_operation_accumulates(self):
        """Operations should accumulate in log."""
        from scripts.agentica.unified_scope import LocalCacheManager

        manager = LocalCacheManager()

        manager.log_operation({"op": "read", "path": "/a"})
        manager.log_operation({"op": "write", "path": "/b"})

        ops = manager.get_all_operations()
        assert len(ops) == 2
        assert ops[0]["path"] == "/a"
        assert ops[1]["path"] == "/b"

    def test_get_all_cached_returns_copy(self):
        """get_all_cached should return a copy, not the internal dict."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")
        manager.set_cached("/test", result)

        copy = manager.get_all_cached()
        copy["/modified"] = result

        # Original should be unchanged
        assert "/modified" not in manager.get_all_cached()

    def test_clear_cache_removes_all(self):
        """clear_cache should remove all cached entries."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")

        manager.set_cached("/a", result)
        manager.set_cached("/b", result)
        manager.clear_cache()

        assert manager.get_all_cached() == {}
```

### Success Criteria:

#### Automated Verification:
- [ ] New tests pass: `uv run pytest tests/unit/test_unified_scope.py::TestCacheManagerProtocol -v`
- [ ] New tests pass: `uv run pytest tests/unit/test_unified_scope.py::TestLocalCacheManager -v`
- [ ] All tests pass: `uv run pytest tests/unit/test_unified_scope.py -v`

#### Manual Verification:
- [ ] Test coverage for new classes is complete

---

## Testing Strategy

### Unit Tests
- `TestCacheManagerProtocol` - Verify both implementations satisfy protocol
- `TestLocalCacheManager` - Test all LocalCacheManager methods
- Existing tests in `test_unified_scope.py` verify behavior is unchanged

### Integration Tests
- Existing `test_unified_scope_e2e.py` should pass without modification
- These tests verify end-to-end behavior with mocked Claude CLI

### Regression Testing
Run full test suite to ensure no behavioral changes:
```bash
uv run pytest tests/unit/test_unified_scope.py tests/unit/test_claude_scope.py -v
uv run pytest tests/integration/test_unified_scope_e2e.py -v
```

## Migration Notes

### Backward Compatibility

The refactoring maintains full backward compatibility:
1. `_create_file_ops_with_shared()` signature unchanged
2. `_create_file_ops_default()` signature unchanged
3. `create_unified_scope()` unchanged
4. All existing tests pass without modification

### For Future Callers

New code can use `_create_file_ops()` directly with any CacheManager:
```python
# With SharedContext
ops = _create_file_ops(shared_context, project_dir="/path")

# With LocalCacheManager
ops = _create_file_ops(LocalCacheManager(), project_dir="/path")

# With custom implementation
ops = _create_file_ops(MyCacheManager(), project_dir="/path")
```

## Performance Considerations

- **No performance impact**: Protocol typing is erased at runtime
- **LocalCacheManager** is marginally faster than SharedContext (no locking)
- **Memory unchanged**: Same caching behavior, just abstracted

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Behavioral difference between old/new | Low | High | Comprehensive test suite, side-by-side review |
| SharedContext doesn't match Protocol | Very Low | Medium | Protocol designed from SharedContext methods |
| Test coverage gaps | Low | Medium | Add specific tests for new classes |

## References

- Issue description: `docs/agentica-integration-fixes/issue-2-code-duplication/comment.md`
- Codemap: `docs/agentica-integration-fixes/issue-2-code-duplication/codemap.md`
- Best practices research: `docs/agentica-integration-fixes/issue-2-code-duplication/best-practices.md`
- Source file: `scripts/agentica/unified_scope.py`
- SharedContext: `scripts/agentica/claude_scope.py` L139-208
- Existing tests: `tests/unit/test_unified_scope.py`

## Estimated Complexity

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Add Protocol + LocalCacheManager | Low | Very Low |
| Phase 2: Add unified factory | Medium | Low |
| Phase 3: Convert to thin wrappers | Low | Medium |
| Phase 4: Add tests | Low | Very Low |

**Total estimated effort**: 2-3 hours

**Lines of code impact**:
- Added: ~120 lines (Protocol, LocalCacheManager, unified factory)
- Removed: ~350 lines (duplicated implementations)
- Net: ~230 lines reduced
