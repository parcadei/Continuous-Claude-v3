# Issue 2: Code Duplication (MAJOR REFACTOR)

## Location
- `scripts/agentica/unified_scope.py` lines 58-663

## Description
The functions `_create_file_ops_with_shared()` and `_create_file_ops_default()` contain nearly identical implementations (~300 lines each), differing only in cache storage strategy (shared context vs. local dict).

This duplication:
- Increases maintenance burden
- Risks divergent behavior between the two paths
- Violates DRY principle

## Proposed Fix
Extract a single factory that accepts a cache/log abstraction:

```python
def _create_file_ops(cache_manager) -> dict[str, Any]:
    """Create file operations with pluggable cache manager."""
    def read_file(path: str) -> dict[str, Any]:
        cached = cache_manager.get_cached(path)
        if cached:
            return {"success": True, "path": path, "content": cached.content, "cached": True}
        # ... rest of implementation
    return {"read_file": read_file, ...}

# Thin wrappers:
def _create_file_ops_with_shared(shared: SharedContext, cache_reads: bool = True):
    return _create_file_ops(SharedCacheManager(shared, cache_reads))

def _create_file_ops_default(cache_reads: bool = True):
    return _create_file_ops(LocalCacheManager(cache_reads))
```

## Impact
- Reduces code from 600+ lines to ~300 lines
- Ensures consistent behavior between shared and local contexts
