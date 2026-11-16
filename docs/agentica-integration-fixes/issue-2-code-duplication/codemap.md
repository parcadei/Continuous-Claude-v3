# Codemap: Code Duplication in unified_scope.py

## Overview

**File:** `scripts/agentica/unified_scope.py` (lines 58-740)
**Issue:** Two nearly identical factory functions with ~350 lines of duplicated logic

## Duplicated Functions

### _create_file_ops_with_shared (L59-404)
```
Uses: SharedContext (thread-safe, shared across agents)
Cache: shared.get_cached() / shared.set_cached()
Invalidate: shared.invalidate(path)
Log: shared.log_operation({...})
Debug: shared.get_all_cached() / shared.get_all_operations() / shared.clear_cache()
```

### _create_file_ops_default (L407-740)
```
Uses: Local dict + list (not thread-safe, single agent)
Cache: file_cache[path] / file_cache[path] = result
Invalidate: del file_cache[path]
Log: operation_log.append({...})
Debug: file_cache.copy() / operation_log.copy() / file_cache.clear()
```

## Side-by-Side Comparison

| Operation | with_shared | default | Difference |
|-----------|-------------|---------|------------|
| read_file | L71-138 | L415-481 | Cache access method |
| write_file | L140-190 | L483-534 | Cache invalidation method |
| edit_file | L192-247 | L536-592 | Cache invalidation method |
| bash | L249-286 | L594-631 | Log method |
| grep | L288-326 | L633-671 | Log method |
| glob_search | L328-369 | L673-714 | Log method |
| debug_get_cache | L372-377 | L717-719 | Access method |
| debug_get_operation_log | L379-384 | L721-723 | Access method |
| debug_clear_cache | L386-391 | L725-727 | Clear method |

## Common Pattern Structure

Each file operation follows this pattern:

```
1. Path validation via _canonicalize_path()
2. [read only] Cache check
3. Build Claude CLI prompt
4. Call _call_claude_cli(prompt, allowed_tools)
5. [write/edit] Invalidate cache
6. Log operation
7. Return result dict
8. Catch exception, log failure, return error dict
```

## Abstraction Required: CacheManager Protocol

```python
from typing import Protocol, Any

class CacheManager(Protocol):
    """Unified interface for cache/log operations."""

    # Cache operations
    def get_cached(self, path: str) -> ClaudeResult | None: ...
    def set_cached(self, path: str, result: ClaudeResult) -> None: ...
    def invalidate(self, path: str) -> None: ...

    # Log operations
    def log_operation(self, operation: dict[str, Any]) -> None: ...

    # Debug operations
    def get_all_cached(self) -> dict[str, ClaudeResult]: ...
    def get_all_operations(self) -> list[dict[str, Any]]: ...
    def clear_cache(self) -> None: ...
```

## Implementation: LocalCacheManager

```python
@dataclass
class LocalCacheManager:
    """Non-shared cache for single-agent use."""
    _file_cache: dict[str, ClaudeResult] = field(default_factory=dict)
    _operation_log: list[dict[str, Any]] = field(default_factory=list)

    def get_cached(self, path: str) -> ClaudeResult | None:
        return self._file_cache.get(path)

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        self._file_cache[path] = result

    def invalidate(self, path: str) -> None:
        self._file_cache.pop(path, None)

    def log_operation(self, operation: dict[str, Any]) -> None:
        self._operation_log.append(operation)

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        return self._file_cache.copy()

    def get_all_operations(self) -> list[dict[str, Any]]:
        return self._operation_log.copy()

    def clear_cache(self) -> None:
        self._file_cache.clear()
```

## Refactored: Single Factory Function

```python
def _create_file_ops(
    cache_manager: CacheManager,
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations using any cache manager."""

    def read_file(path: str) -> dict[str, Any]:
        try:
            path = _canonicalize_path(path, project_dir)
        except ValueError as e:
            return {"success": False, "path": path, "content": None, "error": str(e)}

        if cache_reads:
            cached = cache_manager.get_cached(path)
            if cached:
                return {"success": cached.success, "path": cached.path,
                        "content": cached.content, "cached": True}

        prompt = f"Read the file at: {path}\n\nReturn the file content..."

        try:
            response = _call_claude_cli(prompt, ["Read"])
            result = ClaudeResult(success=True, operation="read", path=path,
                                  content=response, raw_response=response)

            if cache_reads:
                cache_manager.set_cached(path, result)

            cache_manager.log_operation({"operation": "read", "path": path, "success": True})
            return {"success": True, "path": path, "content": response, "cached": False}

        except Exception as e:
            cache_manager.log_operation({"operation": "read", "path": path,
                                         "success": False, "error": str(e)})
            return {"success": False, "path": path, "content": None, "error": str(e)}

    # ... similar for write_file, edit_file, bash, grep, glob_search

    return {
        "read_file": read_file,
        "write_file": write_file,
        # ...
    }
```

## Call Sites Update

### Before (create_unified_scope, L743+)
```python
if shared_context:
    file_ops = _create_file_ops_with_shared(shared_context, cache_reads=True, project_dir=project_dir)
else:
    file_ops = _create_file_ops_default(cache_reads=True, project_dir=project_dir)
```

### After
```python
cache_manager = shared_context if shared_context else LocalCacheManager()
file_ops = _create_file_ops(cache_manager, cache_reads=True, project_dir=project_dir)
```

## SharedContext Already Conforms

`SharedContext` (claude_scope.py L140-208) already implements:
- `get_cached(path)` - L154-157
- `set_cached(path, result)` - L159-162
- `invalidate(path)` - L164-168
- `log_operation(operation)` - L170-173
- `get_all_cached()` - L183-190
- `get_all_operations()` - L192-199
- `clear_cache()` - L201-207

No changes needed to SharedContext.

## Impact Analysis

| Metric | Before | After |
|--------|--------|-------|
| Lines of code | ~680 (L59-740) | ~380 |
| Duplicated functions | 9 pairs | 0 |
| Cache implementations | 2 (inline) | 2 (classes) |
| Test coverage surface | 2x | 1x |

## Files to Modify

1. `scripts/agentica/unified_scope.py`
   - Add `LocalCacheManager` class
   - Add `CacheManager` Protocol (or use structural typing)
   - Replace two factory functions with one `_create_file_ops()`
   - Update `create_unified_scope()` call site

2. `tests/unit/test_unified_scope.py` (if exists)
   - Update test fixtures to use new pattern
   - Add `LocalCacheManager` tests

## Migration Path

1. Add `LocalCacheManager` class (non-breaking)
2. Add `_create_file_ops()` alongside existing functions (non-breaking)
3. Update `create_unified_scope()` to use new function
4. Delete `_create_file_ops_with_shared()` and `_create_file_ops_default()`
5. Run tests to verify behavior unchanged
