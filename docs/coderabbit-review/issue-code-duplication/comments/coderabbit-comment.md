# CodeRabbit Issue: Code Duplication in File Operation Factories

**Severity:** 🟠 Major (Refactor Suggestion)
**File:** `scripts/agentica/unified_scope.py` lines 58-663

## Issue Description

The functions `_create_file_ops_with_shared()` and `_create_file_ops_default()` contain nearly identical implementations (~300 lines each), differing only in cache storage strategy (shared context vs. local dict). This duplication increases maintenance burden and the risk of divergent behavior.

## Proposed Fix (from CodeRabbit)

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

This reduces the code to ~300 lines total (from 600+) and ensures consistent behavior.

## Ruff Linting Issues (25 total)

- TRY300: Multiple instances of "Consider moving this statement to an else block"
- BLE001: Multiple instances of "Do not catch blind exception: Exception"
- RUF051: Use `pop` instead of `key in dict` followed by `del dict[key]`

## AI Agent Prompt

```
In scripts/agentica/unified_scope.py around lines 58 to 663, there's ~300 lines
of duplicated code between _create_file_ops_with_shared() and
_create_file_ops_default(). Extract a CacheManager protocol, implement
SharedCacheManager and LocalCacheManager, and refactor to a single
_create_file_ops(cache_manager) factory.
```
