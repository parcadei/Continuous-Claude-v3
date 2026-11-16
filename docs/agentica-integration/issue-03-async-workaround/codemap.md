# Codemap: Async Workaround Pattern

## Overview

The `_run_async` function is a sync-to-async bridge that handles nested event loop scenarios by spawning threads. This pattern exists in two files and is called 5 times for memory operations.

## Primary Location

### `scripts/agentica/unified_scope.py` (L132-151)

```python
def _run_async(coro):
    """Run an async coroutine synchronously."""
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

### Duplicate in `scripts/agentica/claude_scope.py` (L32-51)

Identical implementation - code duplication issue (see issue-02).

## Call Sites in unified_scope.py

| Line | Function | Async Method Called |
|------|----------|---------------------|
| 581 | `create_unified_scope` | `memory.connect()` |
| 585 | `remember()` | `memory.set_core(key, value)` |
| 589 | `recall()` | `memory.recall(query)` |
| 593 | `search_memory()` | `memory.search(query, limit)` |
| 597 | `store_fact()` | `memory.store(content)` |

## Memory Service Async Interface

Source: `scripts/agentica/memory_service.py`

```python
# All methods are async
async def connect(self) -> None           # L100
async def set_core(key, value) -> None    # L168
async def store(content) -> str           # L244
async def search(query, limit) -> list    # L299
async def recall(query) -> str            # L359
```

## Execution Flow

```
create_unified_scope()
    |
    v
MemoryService(session_id, db_path)
    |
    v
_run_async(memory.connect())
    |
    +--[no loop running]--> asyncio.run(coro)
    |
    +--[loop running]-----> ThreadPoolExecutor()
                                |
                                v
                            pool.submit(asyncio.run, coro)
                                |
                                v
                            future.result()  # blocks
```

## Why ThreadPoolExecutor?

**Problem:** Python's `asyncio.run()` cannot be called from within an existing event loop. This raises `RuntimeError: This event loop is already running`.

**Common scenarios triggering nested loops:**
1. pytest-asyncio test fixtures
2. Jupyter notebooks
3. Framework event loops (Starlette, FastAPI)
4. Agents spawning agents in async context

**Current workaround:** Create a new thread with its own event loop via ThreadPoolExecutor.

## Performance Impact

Each `_run_async` call when a loop is running:
1. Creates a ThreadPoolExecutor (with default workers)
2. Spawns a new thread
3. Creates a new event loop in that thread
4. Runs the coroutine
5. Waits for result (blocks calling thread)
6. Tears down executor and thread

For high-frequency operations like `remember()` and `recall()`, this adds ~1-5ms overhead per call.

## Other Files Using Similar Patterns

| File | Pattern | Notes |
|------|---------|-------|
| `tests/unit/test_crud_memory_ops.py` | Same `_run_async` | L18-29 |
| `scripts/agentica/postgres_pool.py` | `asyncio.Lock` | L42 |
| `scripts/agentica/embedding_service.py` | `asyncio.Lock` | L488 |
| `scripts/agentica/span_processor.py` | `asyncio.Lock` | L699 |

## Cross-Thread Safety Concern

The `asyncio.Lock` used in other files does NOT provide cross-thread synchronization. When `_run_async` creates new event loops in threads, each thread gets an isolated lock context.

From `docs/v3/JOURNEY.md`:
> "asyncio.Lock only works within a single event loop. When `_run_async()` creates new event loops in threads, each gets isolated lock context."

## Alternative Approaches

### 1. Fail-Fast (CodeRabbit suggestion)

```python
def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        raise RuntimeError(
            "Cannot use unified_scope from within async context. "
            "Use async variants or refactor to avoid nesting."
        )
```

**Pros:** No thread overhead, clear error message
**Cons:** Breaks existing code that relies on nested loop support

### 2. Async-First API

```python
# Expose async methods directly
async def create_unified_scope_async(...):
    scope["remember"] = memory.set_core  # async
    scope["recall"] = memory.recall      # async
    return scope
```

**Pros:** Native async, no bridging needed
**Cons:** Requires caller to handle async

### 3. Reuse ThreadPoolExecutor

```python
_executor: ThreadPoolExecutor | None = None

def _run_async(coro):
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4)
    # ... use shared executor
```

**Pros:** Reduces thread churn
**Cons:** Module-level state, cleanup complexity

## Recommendations

1. **Document the pattern** - Add performance notes to `_run_async` docstring
2. **Evaluate fail-fast** - Test if any production code actually hits the nested loop path
3. **Consider async variants** - For performance-critical paths, expose async API
4. **Profile thread overhead** - Measure actual impact in typical usage patterns
