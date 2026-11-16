# Cross-Thread SQLite Analysis: unified_scope.py

## Executive Summary

The `_run_async` function in `unified_scope.py` creates **new threads with separate event loops** for each async operation when called from within an existing event loop. This pattern, combined with aiosqlite's connection-per-call approach, creates a **cross-thread SQLite access issue** where database connections are used from threads different from where they were created.

---

## 1. _run_async Function Analysis

**Location:** `scripts/agentica/unified_scope.py` L132-151

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

### Behavior Matrix

| Context | Code Path | Thread | Event Loop |
|---------|-----------|--------|------------|
| No running loop | `asyncio.run(coro)` | Same thread | New loop, destroyed after |
| Running loop exists | ThreadPoolExecutor | **New thread** | **New loop in new thread** |

### Critical Issue

When a running loop exists (common in pytest-asyncio, Jupyter, agentica REPL):
1. A **new thread** is spawned via ThreadPoolExecutor
2. A **new event loop** is created in that thread via `asyncio.run()`
3. The coroutine runs in this isolated context
4. Any SQLite connection created/used spans thread boundaries

---

## 2. ThreadPoolExecutor Usage Sites

### Direct Usage in _run_async

**File:** `scripts/agentica/unified_scope.py`
**Line:** 149-151

```python
with concurrent.futures.ThreadPoolExecutor() as pool:
    future = pool.submit(asyncio.run, coro)
    return future.result()
```

**Impact:** Every `_run_async` call from an async context spawns a thread.

### Duplicate in claude_scope.py

**File:** `scripts/agentica/claude_scope.py`
**Line:** 31-50 (identical implementation)

---

## 3. MemoryService Connection Pattern

**File:** `scripts/agentica/memory_service.py`

### Connection Strategy (L88-98)

```python
@asynccontextmanager
async def _get_conn(self):
    """Get async database connection with WAL mode."""
    conn = await aiosqlite.connect(str(self._db_path))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        await conn.commit()
    finally:
        await conn.close()
```

**Pattern:** Connection-per-operation (no connection pooling)

### Thread Safety Issue

Each method creates a **new connection** in `_get_conn()`:
- L176: `set_core` - new connection
- L194: `get_core` - new connection
- L263: `store` - new connection
- L311: `search` - new connection

When these run via `_run_async` from async context:
1. Connection opens in **ThreadPool thread**
2. Operations execute in that thread
3. Connection closes in that thread

**SQLite Constraint:** "A connection can only be used from the thread that created it" (sqlite3 module default, inherited by aiosqlite).

---

## 4. All Callers of _run_async

### In unified_scope.py (5 calls)

| Line | Call | Purpose |
|------|------|---------|
| 603 | `_run_async(memory.connect())` | Initialize memory schema |
| 607 | `_run_async(memory.set_core(key, value))` | Store key-value |
| 611 | `_run_async(memory.recall(query))` | Query memory |
| 615 | `_run_async(memory.search(query, limit=limit))` | FTS search |
| 619 | `_run_async(memory.store(content))` | Store archival fact |

### Call Context (create_unified_scope, L555-664)

```python
def create_unified_scope(
    session_id: str,
    db_path: Path | None = None,
    enable_memory: bool = True,
    ...
) -> dict[str, Any]:
    ...
    if enable_memory:
        memory = MemoryService(session_id=session_id, db_path=db_path)
        # Initialize schema synchronously
        _run_async(memory.connect())  # L603

        def remember(key: str, value: str) -> None:
            _run_async(memory.set_core(key, value))  # L607

        def recall(query: str) -> str:
            return _run_async(memory.recall(query))  # L611

        def search_memory(query: str, limit: int = 10):
            return _run_async(memory.search(query, limit=limit))  # L615

        def store_fact(content: str) -> str:
            return _run_async(memory.store(content))  # L619
```

### In test_crud_memory_ops.py (L18-29)

```python
def _run_async(coro):
    # Identical implementation - duplicated for test isolation
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(coro)
    else:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
```

---

## 5. Thread/Connection Flow Diagram

```
Main Thread (async context)              ThreadPool Thread
==============================          ===================
create_unified_scope()
    |
    v
_run_async(memory.connect())
    |
    +---> [running loop detected]
    |
    v
ThreadPoolExecutor.submit()  ---------> asyncio.run(memory.connect())
    |                                       |
    |                                       v
    |                                   _get_conn()
    |                                       |
    |                                       v
    |                                   aiosqlite.connect() [Thread B]
    |                                       |
    |                                       v
    |                                   _init_schema() [Thread B]
    |                                       |
    |                                       v
    |                                   conn.close() [Thread B]
    |                                       |
future.result()  <---------------------- return
    |
    v
remember("key", "value")
    |
    v
_run_async(memory.set_core())
    |
    +---> [running loop detected]
    |
    v
ThreadPoolExecutor.submit()  ---------> asyncio.run(memory.set_core())
                                            |
                                            v
                                        _get_conn()
                                            |
                                            v
                                        aiosqlite.connect() [Thread C]  <-- DIFFERENT THREAD!
                                            |
                                            v
                                        INSERT ... [Thread C]
```

---

## 6. Why This Doesn't Always Fail

### SQLite Threading Modes

SQLite has three threading modes:
1. **Single-thread** - Not thread-safe at all
2. **Multi-thread** - Safe if connections aren't shared
3. **Serialized** - Fully thread-safe (default in Python)

Python's sqlite3 defaults to `check_same_thread=True`, but aiosqlite sets `check_same_thread=False` internally to support async.

### Current Mitigating Factors

1. **Connection-per-operation** - Each `_get_conn()` creates fresh connection
2. **No connection reuse** - MemoryService doesn't pool connections
3. **WAL mode** - Better concurrency for readers/writers
4. **Short-lived connections** - Close immediately after operation

### When It Would Fail

- Connection passed between methods within single operation
- Long-running transactions spanning multiple `_run_async` calls
- Connection pooling added without thread awareness
- High concurrency with same-row updates

---

## 7. Related Documentation

| File | Topic |
|------|-------|
| `docs/agentica-integration/issue-03-async-workaround/codemap.md` | Previous async workaround analysis |
| `docs/agentica-integration/issue-03-async-workaround/plan.md` | Proposed fix: fail-fast pattern |
| `docs/security-hardening/decisions.md` | Decision 3: _run_async Sync Bridge Pattern |
| `docs/security-hardening/technical-debt.md` | Threading model debt documentation |
| `docs/v3/JOURNEY.md` L267 | asyncio.Lock cross-thread limitation |

---

## 8. Risk Assessment

| Risk | Severity | Likelihood | Current Mitigation |
|------|----------|------------|-------------------|
| Connection used cross-thread | High | Low | Connection-per-operation |
| asyncio.Lock ineffective | Medium | Medium | Not using locks for SQLite |
| Data corruption | High | Very Low | WAL mode + serialized |
| Performance overhead | Low | High | ~1-5ms per ThreadPool spawn |

---

## 9. Recommendations

### Short-term (Safe)

1. **Document the pattern** - Add warning to `_run_async` docstring
2. **Keep connection-per-operation** - Don't add connection pooling
3. **Avoid long transactions** - Keep each `_run_async` atomic

### Medium-term (Proper Fix)

1. **Async-first API** - Remove sync wrappers, use async throughout
2. **Fail-fast pattern** - Raise error if nested loop detected
3. **Explicit async context** - Require callers to manage event loop

### Long-term (Architectural)

1. **Sync database layer** - Use synchronous sqlite3 for sync contexts
2. **Connection pool with thread affinity** - If async needed
3. **Remove dual sync/async interface** - Pick one pattern
