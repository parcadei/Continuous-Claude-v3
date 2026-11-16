# Code Duplication Analysis: unified_scope.py

## Status: REFACTOR ALREADY COMPLETED

The CodeRabbit issue has already been addressed. The code now uses a single `_create_file_ops()` factory with a `CacheManager` protocol.

---

## Current Architecture (Post-Refactor)

### File: `scripts/agentica/unified_scope.py` (664 lines)

```
Lines 43-81:   CacheManager Protocol (39 lines)
Lines 83-130: LocalCacheManager class (48 lines)
Lines 132-152: _run_async helper (21 lines)
Lines 154-504: _create_file_ops() - SINGLE FACTORY (~350 lines)
Lines 507-532: _create_file_ops_with_shared() - THIN WRAPPER (26 lines)
Lines 535-553: _create_file_ops_default() - THIN WRAPPER (19 lines)
Lines 555-665: create_unified_scope() (110 lines)
```

---

## Side-by-Side: Wrappers Are Now Thin

### _create_file_ops_with_shared (L507-532)
```python
def _create_file_ops_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    # SharedContext implements CacheManager protocol via structural typing
    return _create_file_ops(shared, project_dir)
```

### _create_file_ops_default (L535-553)
```python
def _create_file_ops_default(
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    return _create_file_ops(LocalCacheManager(cache_reads), project_dir)
```

**Difference:** Only the cache manager instantiation differs:
- `_with_shared`: Uses `SharedContext` directly (thread-safe, multi-agent)
- `_default`: Uses `LocalCacheManager(cache_reads)` (single-agent, simpler)

---

## CacheManager Protocol (L43-81)

```python
class CacheManager(Protocol):
    def get_cached(self, path: str) -> ClaudeResult | None: ...
    def set_cached(self, path: str, result: ClaudeResult) -> None: ...
    def invalidate(self, path: str) -> None: ...
    def log_operation(self, operation: dict[str, Any]) -> None: ...
    def get_all_cached(self) -> dict[str, ClaudeResult]: ...
    def get_all_operations(self) -> list[dict[str, Any]]: ...
    def clear_cache(self) -> None: ...
```

---

## Implementations

### 1. LocalCacheManager (L83-130) - unified_scope.py
- Simple dict-based storage
- Not thread-safe (intentional for single-agent)
- Respects `cache_reads` flag

### 2. SharedContext (L138-207) - claude_scope.py
- Thread-safe with `threading.Lock`
- Multi-agent coordination
- Always caches (no `cache_reads` flag - structural typing match)

---

## Caller Dependency Graph

```
create_unified_scope()
    ├── _create_file_ops_with_shared(shared_context)
    │       └── _create_file_ops(shared_context)  # SharedContext as CacheManager
    └── _create_file_ops_default()
            └── _create_file_ops(LocalCacheManager(cache_reads))

create_claude_scope() [claude_scope.py]
    └── _create_file_ops(LocalCacheManager(cache_reads))

create_claude_scope_with_shared() [claude_scope.py]
    └── _create_file_ops(shared)  # SharedContext
```

### External Callers (from grep results)
| File | Function Called |
|------|-----------------|
| `scripts/agentica/unified_scope.py` | `_create_file_ops_with_shared`, `_create_file_ops_default` |
| `scripts/agentica/claude_scope.py` | `_create_file_ops` (via lazy import) |
| `tests/unit/test_unified_scope.py` | `create_unified_scope` |
| `tests/unit/test_cache_manager_protocol.py` | `CacheManager`, `LocalCacheManager` |
| `tests/integration/test_unified_scope_e2e.py` | `create_unified_scope` |

---

## Operations in _create_file_ops() (L154-504)

| Operation | CacheManager Methods Used |
|-----------|--------------------------|
| `read_file` | `get_cached`, `set_cached`, `log_operation` |
| `write_file` | `invalidate`, `log_operation` |
| `edit_file` | `invalidate`, `log_operation` |
| `bash` | `log_operation` |
| `grep` | `log_operation` |
| `glob_search` | `log_operation` |
| `debug_get_cache` | `get_all_cached` |
| `debug_get_operation_log` | `get_all_operations` |
| `debug_clear_cache` | `clear_cache` |

---

## Remaining Ruff Issues (from CodeRabbit comment)

The original review mentioned 25 Ruff issues. These are **linting improvements**, not duplication:

1. **TRY300**: "Consider moving this statement to an else block"
   - Affects: Multiple try/except blocks in `_create_file_ops`

2. **BLE001**: "Do not catch blind exception: Exception"
   - Affects: All exception handlers in file ops

3. **RUF051**: "Use pop instead of key in dict followed by del dict[key]"
   - Fixed in `SharedContext.invalidate()` (now uses pattern that avoids this)

---

## Conclusion

The CodeRabbit code duplication issue is **RESOLVED**:
- Single `_create_file_ops(cache_manager)` factory (350 lines)
- Two thin wrappers (45 lines combined)
- Total: ~395 lines vs original ~600 lines (34% reduction)
- `CacheManager` protocol enables clean dependency injection

Remaining work is linting improvements, not structural refactoring.
