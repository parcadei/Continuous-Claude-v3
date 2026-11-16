# Codemap: Issue 02 - Code Duplication Analysis

## Summary

The issue describes ~300 lines of duplication between `_create_file_ops_with_shared()` and `_create_file_ops_default()` in unified_scope.py. Analysis reveals:

**unified_scope.py** - ALREADY REFACTORED (Issue resolved here)
**claude_scope.py** - STILL HAS DUPLICATION (~800 lines remaining)

---

## File: unified_scope.py (REFACTORED)

**Path:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/unified_scope.py`

**Total lines:** 643

### Architecture (Clean)

```
CacheManager (Protocol, L43-81)
    |- get_cached(path) -> ClaudeResult | None
    |- set_cached(path, result) -> None
    |- invalidate(path) -> None
    |- log_operation(operation) -> None
    |- get_all_cached() -> dict
    |- get_all_operations() -> list
    |- clear_cache() -> None

LocalCacheManager (L83-129)
    |- Implements CacheManager for single-agent use
    |- Not thread-safe (intentional)
    |- Uses local dict storage

_create_file_ops(cache_manager, project_dir) -> dict  (L154-482)
    |- read_file (L172-234)
    |- write_file (L236-283)
    |- edit_file (L285-337)
    |- bash (L339-376)
    |- grep (L378-416)
    |- glob_search (L418-458)
    |- debug_get_cache (L460-462)
    |- debug_get_operation_log (L464-466)
    |- debug_clear_cache (L468-470)

_create_file_ops_with_shared(shared, cache_reads, project_dir)  (L485-510)
    |- Thin wrapper: 25 lines
    |- Delegates to _create_file_ops(shared, project_dir)

_create_file_ops_default(cache_reads, project_dir)  (L513-530)
    |- Thin wrapper: 17 lines
    |- Delegates to _create_file_ops(LocalCacheManager(cache_reads), project_dir)

create_unified_scope(...)  (L533-642)
    |- Combines file ops + memory + tasks
```

### Line Counts (unified_scope.py)

| Component | Lines | Notes |
|-----------|-------|-------|
| CacheManager Protocol | 38 (L43-81) | Interface definition |
| LocalCacheManager | 46 (L83-129) | Local dict implementation |
| _create_file_ops | 328 (L154-482) | Single implementation |
| _create_file_ops_with_shared | 25 (L485-510) | Thin wrapper |
| _create_file_ops_default | 17 (L513-530) | Thin wrapper |
| create_unified_scope | 109 (L533-642) | Factory function |

**Status:** Refactoring COMPLETE. No duplication in unified_scope.py.

---

## File: claude_scope.py (NEEDS REFACTORING)

**Path:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/claude_scope.py`

**Total lines:** 1091

### Architecture (Duplicated)

```
create_claude_scope(cache_reads, project_dir) -> dict  (L276-690)
    |- Uses local dict: file_cache, operation_log
    |- read_file (L301-374)
    |- write_file (L376-435)
    |- edit_file (L437-502)
    |- bash (L504-561)
    |- grep (L563-609)
    |- glob_search (L611-659)
    |- get_cache (L661-663)
    |- get_operation_log (L665-667)
    |- clear_cache (L669-671)
    |- Returns: 10 functions + 3 broadcast functions

create_claude_scope_with_shared(shared, cache_reads, project_dir) -> dict  (L693-1091)
    |- Uses SharedContext methods
    |- read_file (L720-794) - DUPLICATE
    |- write_file (L796-854) - DUPLICATE
    |- edit_file (L856-920) - DUPLICATE
    |- bash (L922-979) - DUPLICATE
    |- grep (L981-1027) - DUPLICATE
    |- glob_search (L1029-1077) - DUPLICATE
    |- Returns: 7 functions
```

### Line Counts (claude_scope.py)

| Component | Lines | Notes |
|-----------|-------|-------|
| SharedContext | 68 (L139-208) | Already implements CacheManager protocol |
| create_claude_scope | 414 (L276-690) | Local dict version |
| create_claude_scope_with_shared | 398 (L693-1091) | Shared context version |
| **Total duplicated** | **~800** | Both functions implement same file ops |

---

## Difference Analysis

### What's IDENTICAL between the two claude_scope functions:

| Operation | Local Version | Shared Version | Identical? |
|-----------|---------------|----------------|------------|
| read_file | L301-374 (73 lines) | L720-794 (74 lines) | 99% (cache access differs) |
| write_file | L376-435 (59 lines) | L796-854 (58 lines) | 99% (invalidate differs) |
| edit_file | L437-502 (65 lines) | L856-920 (64 lines) | 99% (invalidate differs) |
| bash | L504-561 (57 lines) | L922-979 (57 lines) | 99% (log differs) |
| grep | L563-609 (46 lines) | L981-1027 (46 lines) | 99% (log differs) |
| glob | L611-659 (48 lines) | L1029-1077 (48 lines) | 99% (log differs) |

### What's DIFFERENT:

| Aspect | create_claude_scope | create_claude_scope_with_shared |
|--------|---------------------|--------------------------------|
| Cache storage | `file_cache[path]` (local dict) | `shared.get_cached(path)` |
| Cache write | `file_cache[path] = result` | `shared.set_cached(path, result)` |
| Invalidation | `del file_cache[path]` | `shared.invalidate(path)` |
| Logging | `operation_log.append(...)` | `shared.log_operation(...)` |
| Thread safety | No | Yes (via SharedContext._lock) |
| Broadcast funcs | Included | Not included |

---

## Recommended Refactoring for claude_scope.py

### Option 1: Use unified_scope.py Pattern

claude_scope.py already has SharedContext which implements the CacheManager protocol. Apply the same pattern:

```python
# Add to claude_scope.py
from scripts.agentica.unified_scope import CacheManager, LocalCacheManager, _create_file_ops

def create_claude_scope(cache_reads: bool = True, project_dir: str | None = None) -> dict:
    """Create scope with Claude CLI functions."""
    ops = _create_file_ops(LocalCacheManager(cache_reads), project_dir)
    ops.update({
        "broadcast_finding": broadcast_finding,
        "broadcast_blocker": broadcast_blocker,
        "broadcast_done": broadcast_done,
    })
    return ops

def create_claude_scope_with_shared(shared: SharedContext, ...) -> dict:
    """Create scope with shared context for multi-agent coordination."""
    return _create_file_ops(shared, project_dir)
```

**Lines saved:** ~700 lines (from 812 to ~100)

### Option 2: Inline Refactoring

If importing from unified_scope.py creates circular dependencies:

1. Move CacheManager protocol to claude_scope.py
2. Create LocalCacheManager class in claude_scope.py
3. Extract single `_create_file_ops()` factory
4. Thin wrappers call factory with appropriate CacheManager

---

## Files to Modify

| File | Action | Impact |
|------|--------|--------|
| unified_scope.py | None | Already refactored |
| claude_scope.py | Refactor | Remove ~700 duplicate lines |

---

## Test Commands

```bash
# Verify unified_scope tests pass
uv run pytest tests/unit/test_unified_scope.py -v

# Verify claude_scope tests pass
uv run pytest tests/unit/test_claude_scope.py -v

# Integration tests
uv run pytest tests/integration/test_unified_scope_e2e.py -v
```
