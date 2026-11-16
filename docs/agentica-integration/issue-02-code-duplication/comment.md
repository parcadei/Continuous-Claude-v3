# Issue 02: ~300 Lines Code Duplication in unified_scope.py

**Severity:** MAJOR (Refactor)
**File:** `scripts/agentica/unified_scope.py`
**Lines:** 58-663 (specifically comparing `_create_file_ops_with_shared` and `_create_file_ops_default`)

## Summary

The functions `_create_file_ops_with_shared()` and `_create_file_ops_default()` contain nearly identical implementations (~300 lines each), differing only in cache storage strategy (shared context vs. local dict). This duplication increases maintenance burden and risk of divergent behavior.

## CodeRabbit Proposed Refactoring

Extract a single factory that accepts a cache/log abstraction:

```python
def _create_file_ops(cache_manager) -> dict[str, Any]:
    """Create file operations with pluggable cache manager.

    Args:
        cache_manager: Object with methods:
            - get_cached(path) -> ClaudeResult | None
            - set_cached(path, result)
            - invalidate(path)
            - log_operation(op_dict)
    """
    def read_file(path: str) -> dict[str, Any]:
        cached = cache_manager.get_cached(path)
        if cached:
            return {"success": True, "path": path, "content": cached.content, "cached": True}
        # ... rest of implementation
    # ... other operations
    return {"read_file": read_file, ...}

# Then create thin wrappers:
def _create_file_ops_with_shared(shared: SharedContext, cache_reads: bool = True):
    return _create_file_ops(SharedCacheManager(shared, cache_reads))

def _create_file_ops_default(cache_reads: bool = True):
    return _create_file_ops(LocalCacheManager(cache_reads))
```

## Fix Requirements

1. Create a CacheManager protocol/interface
2. Implement SharedCacheManager (wraps SharedContext)
3. Implement LocalCacheManager (wraps local dicts)
4. Extract common file ops logic to single `_create_file_ops(cache_manager)`
5. Ensure all existing tests still pass
6. Reduces ~600 lines to ~300 lines
