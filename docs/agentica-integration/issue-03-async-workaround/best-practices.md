# Python Async Best Practices: Handling Sync/Async Boundaries

Generated: 2025-12-29

## Executive Summary

The `_run_async` function in `unified_scope.py` uses ThreadPoolExecutor to handle nested event loops, adding overhead for every async call. This document provides best practices for handling sync/async boundaries in Python, with specific recommendations for the agentica codebase. The key recommendation is: **Design async-first APIs and provide thin sync wrappers only at public interface boundaries.**

## Research Question

How to properly handle sync/async boundaries in Python without the overhead of ThreadPoolExecutor for every call?

## Key Findings

### Finding 1: The Nested Event Loop Problem

Python's asyncio does not allow nested event loops. Calling `asyncio.run()` from within an already-running event loop raises `RuntimeError`:

```python
import asyncio

async def inner():
    return "result"

async def outer():
    # This raises RuntimeError: cannot be called from a running event loop
    return asyncio.run(inner())

asyncio.run(outer())
```

The current workaround in `unified_scope.py`:

```python
def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(coro)
    else:
        # Thread pool workaround
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
```

**Problems with this approach:**
1. **Thread churn:** Creates new thread for every async operation
2. **Context loss:** New event loop loses current task/context
3. **Performance overhead:** Thread creation ~1ms, context switch ~10-100us
4. **Hidden complexity:** Debugging async issues becomes harder

- Source: Python asyncio documentation, concurrent.futures

### Finding 2: When ThreadPoolExecutor is Actually Justified

ThreadPoolExecutor overhead IS justified for:

1. **CPU-bound work:** Offloading to avoid blocking the event loop
2. **Blocking I/O:** Libraries without async support (e.g., legacy DB drivers)
3. **Third-party sync code:** When you can't control the calling code

ThreadPoolExecutor overhead is NOT justified for:

1. **Pure async operations:** Memory service is already async
2. **Code you control:** Can be refactored to async-first
3. **High-frequency operations:** Database queries, cache lookups

**In this codebase:** The memory service (`MemoryService`) is fully async. Using ThreadPoolExecutor to call it from sync wrappers adds unnecessary overhead.

- Source: Python Performance Patterns, asyncio best practices

### Finding 3: Async-First API Design Pattern

**The Recommended Pattern:**

```python
class Service:
    """Async-first service with thin sync wrappers."""

    # === ASYNC CORE (where the work happens) ===

    async def _do_operation_async(self, args) -> Result:
        """Actual implementation - fully async."""
        async with self._get_connection() as conn:
            return await conn.execute(query)

    # === PUBLIC ASYNC API ===

    async def operation_async(self, args) -> Result:
        """Public async interface."""
        return await self._do_operation_async(args)

    # === SYNC WRAPPERS (optional, at boundary only) ===

    def operation(self, args) -> Result:
        """Sync wrapper - only for external callers."""
        return asyncio.run(self._do_operation_async(args))
```

**Key Principles:**

1. **Internal code stays async:** No sync wrappers for internal calls
2. **Sync wrappers at API boundary only:** For external/legacy callers
3. **Sync wrappers fail-fast:** Don't hide nested loop issues

```python
def operation(self, args) -> Result:
    """Sync wrapper - fails if called from async context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(self._do_operation_async(args))
    else:
        raise RuntimeError(
            "Cannot call sync wrapper from async context. "
            "Use operation_async() instead."
        )
```

- Source: FastAPI patterns, aiohttp design

### Finding 4: Connection Pooling for Async Operations

When async operations involve connections (DB, HTTP, etc.), pooling amortizes overhead:

```python
class PooledService:
    """Service with connection pool for async operations."""

    def __init__(self, pool_size: int = 5):
        self._pool: asyncio.Queue | None = None
        self._pool_size = pool_size

    async def _init_pool(self) -> None:
        """Initialize connection pool once."""
        if self._pool is not None:
            return

        self._pool = asyncio.Queue(maxsize=self._pool_size)
        for _ in range(self._pool_size):
            conn = await self._create_connection()
            await self._pool.put(conn)

    @asynccontextmanager
    async def _get_connection(self):
        """Get connection from pool, return when done."""
        await self._init_pool()
        conn = await self._pool.get()
        try:
            yield conn
        finally:
            await self._pool.put(conn)

    async def operation(self, args) -> Result:
        """Use pooled connection."""
        async with self._get_connection() as conn:
            return await conn.execute(query)
```

**For SQLite (aiosqlite):**

```python
class MemoryService:
    """Memory service with connection reuse."""

    def __init__(self):
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize single connection (reused)."""
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(str(self._db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")

    async def operation(self, args) -> Result:
        """Reuse existing connection."""
        if self._conn is None:
            await self.connect()
        return await self._conn.execute(query)

    async def close(self) -> None:
        """Close when done."""
        if self._conn:
            await self._conn.close()
            self._conn = None
```

- Source: aiohttp, databases, SQLAlchemy async patterns

### Finding 5: Best Practices for Sync Wrappers

When you MUST provide sync wrappers (e.g., for CLI tools or legacy integrations):

**Pattern 1: Module-Level Sync Functions**

```python
# memory_sync.py - Sync interface module

from .memory_service import MemoryService

_service: MemoryService | None = None

def _get_service() -> MemoryService:
    """Lazy initialization of service."""
    global _service
    if _service is None:
        _service = MemoryService()
        asyncio.run(_service.connect())
    return _service

def remember(key: str, value: str) -> None:
    """Sync wrapper for remember operation."""
    service = _get_service()
    asyncio.run(service.store(value))

def recall(query: str) -> list[str]:
    """Sync wrapper for recall operation."""
    service = _get_service()
    return asyncio.run(service.recall(query))
```

**Pattern 2: Context Manager for Batch Operations**

```python
@contextmanager
def sync_memory_session(session_id: str):
    """Sync context manager that batches async operations."""
    service = MemoryService(session_id=session_id)

    # Run setup in single asyncio.run
    asyncio.run(service.connect())

    try:
        # Provide sync methods that queue operations
        yield SyncMemoryWrapper(service)
    finally:
        # Cleanup in single asyncio.run
        asyncio.run(service.close())


class SyncMemoryWrapper:
    """Wrapper that provides sync methods for async service."""

    def __init__(self, service: MemoryService):
        self._service = service

    def remember(self, key: str, value: str) -> None:
        asyncio.run(self._service.store(value))

    def recall(self, query: str) -> list[str]:
        return asyncio.run(self._service.recall(query))
```

**Pattern 3: Fail-Fast for Async Context (Recommended)**

```python
def _run_sync(coro):
    """Run coroutine synchronously - fails if in async context.

    This is intentionally NOT compatible with nested event loops.
    If you need async behavior, use the async API directly.
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
            "Use async methods (e.g., remember_async) instead."
        )
```

- Source: Click async patterns, Typer, Python packaging best practices

## Codebase-Specific Recommendations

### For `unified_scope.py`

**Current State:**
- Uses ThreadPoolExecutor for every async call
- Memory operations incur thread overhead
- Task graph operations incur thread overhead

**Recommended Refactor:**

```python
# Option 1: Make the scope async-first

async def create_unified_scope_async(
    session_id: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Create unified scope - async version (preferred)."""
    memory = MemoryService(session_id=session_id, db_path=db_path)
    await memory.connect()
    task_graph = BeadsTaskGraph(db_path=db_path)
    await task_graph.connect()

    return {
        "remember": memory.store,  # Already async
        "recall": memory.recall,    # Already async
        "create_task": task_graph.create_task,
        # ... other async operations
    }


# Option 2: Keep sync interface but fail-fast

def create_unified_scope(
    session_id: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Create unified scope - sync version.

    Raises:
        RuntimeError: If called from async context
    """
    # Fail fast if in async context
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass  # Good - no running loop
    else:
        raise RuntimeError(
            "Cannot call create_unified_scope from async context. "
            "Use create_unified_scope_async() instead."
        )

    # ... rest of implementation using asyncio.run()
```

### For Test Compatibility

If tests run in async context (pytest-asyncio), they should use async API:

```python
# tests/test_unified_scope.py

import pytest

@pytest.fixture
async def scope():
    """Async fixture for unified scope."""
    scope = await create_unified_scope_async(session_id="test")
    yield scope
    await scope["close"]()

@pytest.mark.asyncio
async def test_remember_recall(scope):
    await scope["remember"]("key", "value")
    result = await scope["recall"]("key")
    assert result is not None
```

## Performance Comparison

| Approach | Overhead per call | Use case |
|----------|------------------|----------|
| Direct async | ~0 | Internal code, async callers |
| asyncio.run() | ~100us | Sync callers, no nesting |
| ThreadPoolExecutor | ~1-5ms | Blocking I/O, CPU-bound |
| nest_asyncio | ~10us | Jupyter notebooks only |

For high-frequency operations (memory queries, task graph updates), the difference is significant:

- 1000 operations with ThreadPoolExecutor: ~1-5 seconds overhead
- 1000 operations with direct async: ~0.1 seconds overhead

## Sources

1. **Python asyncio documentation**
   - https://docs.python.org/3/library/asyncio.html

2. **PEP 492 - Coroutines with async and await syntax**
   - https://peps.python.org/pep-0492/

3. **aiohttp design patterns**
   - https://docs.aiohttp.org/en/stable/

4. **FastAPI async architecture**
   - https://fastapi.tiangolo.com/async/

5. **aiosqlite documentation**
   - https://aiosqlite.omnilib.dev/

6. **Python concurrent.futures**
   - https://docs.python.org/3/library/concurrent.futures.html

## Recommendations Summary

1. **Design async-first:** Make core logic async, add sync wrappers only at boundaries

2. **Fail-fast for nesting:** Don't hide nested loop errors with ThreadPoolExecutor

3. **Remove ThreadPoolExecutor workaround:** Current code should either:
   - Expose async API for async callers
   - Use simple `asyncio.run()` for sync callers with fail-fast

4. **Connection pooling:** Reuse connections instead of creating new ones per operation

5. **Document API expectations:** Clearly indicate which methods are sync vs async

6. **Test appropriately:** Use pytest-asyncio for async tests, sync tests for sync API

## Open Questions

1. **Who calls unified_scope from async context?** If no one does, ThreadPoolExecutor is pure overhead.

2. **Is nest_asyncio acceptable?** For Jupyter/IPython environments only.

3. **Should memory service maintain connection?** Currently creates new connection per context manager entry.

4. **What's the call frequency?** High-frequency operations benefit more from optimization.
