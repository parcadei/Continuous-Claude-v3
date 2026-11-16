# Implementation Plan: Replace ThreadPoolExecutor with Fail-Fast Pattern

## Overview

Replace the `_run_async` ThreadPoolExecutor workaround in `unified_scope.py` and `claude_scope.py` with a fail-fast pattern that eliminates 1-5ms overhead per async call while providing clear error guidance for async context usage.

## Current State Analysis

### What Exists Now

The `_run_async` function exists in two files with identical implementation:

1. **`scripts/agentica/unified_scope.py`** (L132-151)
2. **`scripts/agentica/claude_scope.py`** (L32-51)

```python
def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(coro)
    else:
        # Thread pool workaround - adds 1-5ms overhead
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
```

### Call Sites in unified_scope.py (L577-597)

| Line | Function | Async Method Called |
|------|----------|---------------------|
| 581 | `create_unified_scope` | `memory.connect()` |
| 585 | `remember()` | `memory.set_core(key, value)` |
| 589 | `recall()` | `memory.recall(query)` |
| 593 | `search_memory()` | `memory.search(query, limit)` |
| 597 | `store_fact()` | `memory.store(content)` |

### Key Constraints

- Tests use pytest (not pytest-asyncio) - run in sync context
- Memory service is fully async (`MemoryService` in `memory_service.py`)
- Current tests do NOT call scope functions from async context
- The ThreadPoolExecutor path was added for "test environments" but pytest runs sync

## Desired End State

After implementation:

1. `_run_async` uses simple `asyncio.run()` with fail-fast for nested loops
2. Async variants of scope functions exist for async callers
3. Documentation guides users to appropriate API
4. Performance overhead eliminated for sync callers
5. All existing tests pass without modification

### Verification

```bash
# All tests pass
uv run pytest tests/unit/test_unified_scope.py -v
uv run pytest tests/unit/test_claude_scope.py -v
uv run pytest tests/integration/test_unified_scope_e2e.py -v

# No ThreadPoolExecutor imports remain
grep -r "ThreadPoolExecutor" scripts/agentica/unified_scope.py
grep -r "ThreadPoolExecutor" scripts/agentica/claude_scope.py
```

## What We're NOT Doing

- NOT changing the MemoryService async implementation
- NOT adding nest_asyncio dependency
- NOT modifying pytest to use pytest-asyncio
- NOT breaking backward compatibility for sync callers
- NOT refactoring BeadsTaskGraph (it's already sync)

## Implementation Approach

**Strategy:** Replace ThreadPoolExecutor with fail-fast, add async variants for future async callers.

**Risk Mitigation:** The fail-fast pattern only affects callers in async context. Current tests run sync, so they won't trigger the error path. If any hidden async usage exists, we'll discover it during testing.

---

## Phase 1: Update _run_async in unified_scope.py

### Overview

Replace ThreadPoolExecutor workaround with fail-fast pattern in the primary file.

### Changes Required

#### 1. Update `_run_async` function

**File**: `scripts/agentica/unified_scope.py`
**Lines**: 132-151

**Current code:**
```python
def _run_async(coro):
    """Run an async coroutine synchronously.

    Handles both cases:
    - When called from sync context: creates new event loop
    - Works with nested event loops in test environments
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        # No running loop - create one and run
        return asyncio.run(coro)
    else:
        # There's a running loop - use thread pool to avoid nested loop issues
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
```

**New code:**
```python
def _run_async(coro):
    """Run an async coroutine synchronously.

    This function is for sync callers only. If you're in an async context,
    use the async variants (e.g., create_unified_scope_async) instead.

    Raises:
        RuntimeError: If called from within an async context (running event loop).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to create one
        return asyncio.run(coro)
    else:
        # Already in async context - caller should use async API
        raise RuntimeError(
            "Cannot use sync API from async context. "
            "Use async methods (remember_async, recall_async, etc.) or "
            "create_unified_scope_async() instead."
        )
```

#### 2. Remove unused import

**File**: `scripts/agentica/unified_scope.py`
**Lines**: Check imports section (around L1-30)

Remove `concurrent.futures` import if only used by `_run_async`.

### Success Criteria

#### Automated Verification:
- [ ] Existing sync tests pass: `uv run pytest tests/unit/test_unified_scope.py -v`
- [ ] E2E tests pass: `uv run pytest tests/integration/test_unified_scope_e2e.py -v`
- [ ] Type checking passes: `uv run mypy scripts/agentica/unified_scope.py`
- [ ] No `ThreadPoolExecutor` in file: `grep ThreadPoolExecutor scripts/agentica/unified_scope.py` returns empty

#### Manual Verification:
- [ ] Review diff to confirm only _run_async changed

---

## Phase 2: Update _run_async in claude_scope.py

### Overview

Apply the same fail-fast pattern to the duplicate implementation.

### Changes Required

#### 1. Update `_run_async` function

**File**: `scripts/agentica/claude_scope.py`
**Lines**: 32-51

Apply identical changes as Phase 1.

**New code:**
```python
def _run_async(coro):
    """Run an async coroutine synchronously.

    This function is for sync callers only. If you're in an async context,
    use the async variants instead.

    Raises:
        RuntimeError: If called from within an async context (running event loop).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to create one
        return asyncio.run(coro)
    else:
        # Already in async context - caller should use async API
        raise RuntimeError(
            "Cannot use sync API from async context. "
            "Use async methods or create_claude_scope_async() instead."
        )
```

#### 2. Remove unused import

**File**: `scripts/agentica/claude_scope.py`
**Lines**: Check imports section

Remove `concurrent.futures` import if only used by `_run_async`.

### Success Criteria

#### Automated Verification:
- [ ] Existing sync tests pass: `uv run pytest tests/unit/test_claude_scope.py -v`
- [ ] E2E tests pass: `uv run pytest tests/integration/test_claude_scope_e2e.py -v`
- [ ] Type checking passes: `uv run mypy scripts/agentica/claude_scope.py`
- [ ] No `ThreadPoolExecutor` in file: `grep ThreadPoolExecutor scripts/agentica/claude_scope.py` returns empty

#### Manual Verification:
- [ ] Review diff to confirm only _run_async changed

---

## Phase 3: Add Async Variants to unified_scope.py

### Overview

Add async versions of scope functions for callers in async context.

### Changes Required

#### 1. Add async scope factory

**File**: `scripts/agentica/unified_scope.py`
**Location**: After `create_unified_scope` function (around L700)

```python
async def create_unified_scope_async(
    session_id: str | None = None,
    db_path: Path | str | None = None,
    project_dir: str | None = None,
    enable_memory: bool = True,
    enable_tasks: bool = True,
    cache_manager: CacheManager | None = None,
) -> dict[str, Any]:
    """Create unified scope for async callers.

    This is the async variant of create_unified_scope. Use this when calling
    from within an async context (e.g., async test, async framework).

    Returns:
        Scope dict with async memory functions (remember_async, recall_async, etc.)
    """
    # Resolve session_id and db_path same as sync version
    if session_id is None:
        session_id = os.environ.get("SESSION_ID", str(uuid4()))

    if db_path is None:
        db_path = _get_default_db_path()
    elif isinstance(db_path, str):
        db_path = Path(db_path)

    if project_dir is None:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR")

    # Create scope dict
    scope: dict[str, Any] = {}

    # 1. Add file operations (sync - no async needed for file ops)
    if cache_manager is None:
        cache_manager = LocalCacheManager()
    file_ops = _create_file_ops(cache_manager, project_dir)
    scope.update(file_ops)

    # 2. Add async memory operations
    if enable_memory:
        memory = MemoryService(session_id=session_id, db_path=db_path)
        await memory.connect()

        # Expose async methods directly
        scope["remember_async"] = memory.set_core
        scope["recall_async"] = memory.recall
        scope["search_memory_async"] = memory.search
        scope["store_fact_async"] = memory.store
        scope["_memory_service"] = memory

    # 3. Add task operations (already sync)
    if enable_tasks:
        tasks = BeadsTaskGraph(session_id=session_id, db_path=db_path)
        scope["create_task"] = lambda desc, blocks=None, **kw: tasks.add_task(desc, blocks=blocks, **kw)
        scope["complete_task"] = tasks.complete_task
        scope["get_ready_tasks"] = tasks.get_ready_tasks
        scope["get_all_tasks"] = tasks.get_all_tasks
        scope["_task_graph"] = tasks

    return scope
```

#### 2. Add module-level exports

**File**: `scripts/agentica/unified_scope.py`
**Location**: Update `__all__` if present, or add at module level

```python
__all__ = [
    "create_unified_scope",
    "create_unified_scope_async",
    # ... existing exports
]
```

### Success Criteria

#### Automated Verification:
- [ ] Import works: `python -c "from scripts.agentica.unified_scope import create_unified_scope_async"`
- [ ] Type checking passes: `uv run mypy scripts/agentica/unified_scope.py`
- [ ] Existing tests still pass: `uv run pytest tests/unit/test_unified_scope.py -v`

#### Manual Verification:
- [ ] Async function signature matches sync version (same parameters)

---

## Phase 4: Add Async Test Coverage

### Overview

Add tests to verify async variants work and fail-fast triggers correctly.

### Changes Required

#### 1. Add async variant tests

**File**: `tests/unit/test_unified_scope.py`
**Location**: Add new test class at end of file

```python
# ============================================================================
# Test: Async Variants
# ============================================================================


class TestAsyncVariants:
    """Test async scope creation and usage."""

    @pytest.mark.asyncio
    async def test_create_unified_scope_async_returns_scope(
        self, db_path: Path, session_id: str
    ):
        """Async scope creation should return dict with async functions."""
        from scripts.agentica.unified_scope import create_unified_scope_async

        scope = await create_unified_scope_async(
            db_path=db_path, session_id=session_id
        )

        assert "remember_async" in scope
        assert "recall_async" in scope
        assert "search_memory_async" in scope
        assert "store_fact_async" in scope

    @pytest.mark.asyncio
    async def test_async_remember_and_recall(
        self, db_path: Path, session_id: str
    ):
        """Async remember/recall should work without blocking."""
        from scripts.agentica.unified_scope import create_unified_scope_async

        scope = await create_unified_scope_async(
            db_path=db_path, session_id=session_id
        )

        await scope["remember_async"]("test_key", "test_value")
        result = await scope["recall_async"]("test_key")

        assert "test_value" in result or "test_key" in result


class TestFailFastBehavior:
    """Test that sync API fails fast in async context."""

    @pytest.mark.asyncio
    async def test_sync_scope_fails_in_async_context(
        self, db_path: Path, session_id: str
    ):
        """Calling sync create_unified_scope from async should raise."""
        from scripts.agentica.unified_scope import create_unified_scope

        with pytest.raises(RuntimeError, match="Cannot use sync API from async context"):
            create_unified_scope(db_path=db_path, session_id=session_id)
```

#### 2. Add pytest-asyncio marker configuration

**File**: `pyproject.toml` or `pytest.ini`
**Check if pytest-asyncio is configured**

If not present, add:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

And add dependency:

```bash
uv add --dev pytest-asyncio
```

### Success Criteria

#### Automated Verification:
- [ ] New async tests pass: `uv run pytest tests/unit/test_unified_scope.py::TestAsyncVariants -v`
- [ ] Fail-fast test passes: `uv run pytest tests/unit/test_unified_scope.py::TestFailFastBehavior -v`
- [ ] All tests still pass: `uv run pytest tests/unit/test_unified_scope.py -v`

#### Manual Verification:
- [ ] Review test coverage for async edge cases

---

## Phase 5: Update Documentation

### Overview

Document the async API and migration path.

### Changes Required

#### 1. Update best-practices.md

**File**: `docs/agentica-integration/issue-03-async-workaround/best-practices.md`
**Location**: Add new section after "Open Questions"

Add section:

```markdown
## Resolution

The ThreadPoolExecutor workaround was replaced with a fail-fast pattern:

### For Sync Callers (CLI, scripts, hooks)

```python
from scripts.agentica.unified_scope import create_unified_scope

# Works as before - no change needed
scope = create_unified_scope(session_id="test")
scope["remember"]("key", "value")
result = scope["recall"]("query")
```

### For Async Callers (frameworks, async tests)

```python
from scripts.agentica.unified_scope import create_unified_scope_async

# Use async variant
scope = await create_unified_scope_async(session_id="test")
await scope["remember_async"]("key", "value")
result = await scope["recall_async"]("query")
```

### Migration Guide

If you get `RuntimeError: Cannot use sync API from async context`:

1. **Are you in an async function?** Use `create_unified_scope_async()` instead
2. **Are you in a pytest async test?** Add `@pytest.mark.asyncio` and use async API
3. **Are you in a framework event loop?** Use async API with `await`
```

#### 2. Add inline docstrings

Already included in Phase 1-3 code changes.

### Success Criteria

#### Automated Verification:
- [ ] Documentation file exists and is valid markdown
- [ ] Code examples in docs are syntactically correct

#### Manual Verification:
- [ ] Documentation clearly explains when to use sync vs async API
- [ ] Migration path is clear for users hitting the RuntimeError

---

## Phase 6: Cleanup and Final Verification

### Overview

Remove dead code, verify all tests pass, measure performance improvement.

### Changes Required

#### 1. Remove any remaining ThreadPoolExecutor references

Search and remove if found:

```bash
grep -rn "ThreadPoolExecutor" scripts/agentica/
grep -rn "concurrent.futures" scripts/agentica/unified_scope.py
grep -rn "concurrent.futures" scripts/agentica/claude_scope.py
```

#### 2. Run full test suite

```bash
uv run pytest tests/unit/ -v --tb=short
uv run pytest tests/integration/ -v --tb=short
```

#### 3. Measure performance improvement (optional)

Create a quick benchmark:

```python
# benchmark_async.py
import time
from scripts.agentica.unified_scope import create_unified_scope

def benchmark():
    scope = create_unified_scope(session_id="benchmark")

    start = time.perf_counter()
    for i in range(100):
        scope["remember"](f"key_{i}", f"value_{i}")
    elapsed = time.perf_counter() - start

    print(f"100 remember ops: {elapsed:.3f}s ({elapsed*10:.1f}ms/op)")

if __name__ == "__main__":
    benchmark()
```

Expected: ~0.1ms/op (down from 1-5ms/op with ThreadPoolExecutor).

### Success Criteria

#### Automated Verification:
- [ ] Full unit test suite passes: `uv run pytest tests/unit/ -v`
- [ ] Full integration test suite passes: `uv run pytest tests/integration/ -v`
- [ ] No ThreadPoolExecutor in scope files: `grep -c ThreadPoolExecutor scripts/agentica/*_scope.py` returns 0
- [ ] Type checking passes: `uv run mypy scripts/agentica/unified_scope.py scripts/agentica/claude_scope.py`

#### Manual Verification:
- [ ] Performance improvement confirmed (if benchmark run)
- [ ] No regressions in any existing functionality

---

## Testing Strategy

### Unit Tests

- `tests/unit/test_unified_scope.py` - Existing tests plus new async tests
- `tests/unit/test_claude_scope.py` - Existing tests

### Integration Tests

- `tests/integration/test_unified_scope_e2e.py` - End-to-end scope usage
- `tests/integration/test_claude_scope_e2e.py` - End-to-end Claude scope usage

### Edge Cases to Cover

1. **Sync context calling sync API** - Should work (existing behavior)
2. **Async context calling sync API** - Should raise RuntimeError
3. **Async context calling async API** - Should work
4. **Nested async calls** - Should work with async API

## Performance Considerations

| Metric | Before | After |
|--------|--------|-------|
| Memory op overhead (sync context) | ~0.1ms | ~0.1ms (unchanged) |
| Memory op overhead (nested loop) | 1-5ms | N/A (fails fast) |
| Thread creation | Per call | None |
| Event loop creation | Per call (nested) | None (fails fast) |

## Risks & Considerations

1. **Breaking async callers:** If any production code calls sync API from async context, it will now fail. Mitigation: Tests should catch this; error message guides to async API.

2. **Test environment differences:** pytest-asyncio may behave differently across versions. Mitigation: Pin pytest-asyncio version.

3. **Future async requirements:** If sync-to-async bridging is needed later, can add back with proper pooling. Mitigation: This is additive, not removing capability.

## Estimated Complexity

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1 | Low | Low |
| Phase 2 | Low | Low |
| Phase 3 | Medium | Low |
| Phase 4 | Medium | Medium |
| Phase 5 | Low | Low |
| Phase 6 | Low | Low |

**Total estimate:** 2-3 hours

## References

- Original issue: `docs/agentica-integration/issue-03-async-workaround/comment.md`
- Codemap: `docs/agentica-integration/issue-03-async-workaround/codemap.md`
- Best practices research: `docs/agentica-integration/issue-03-async-workaround/best-practices.md`
- Source files:
  - `scripts/agentica/unified_scope.py:132-151`
  - `scripts/agentica/claude_scope.py:32-51`
