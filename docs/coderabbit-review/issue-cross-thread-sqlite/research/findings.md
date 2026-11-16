# Cross-Thread SQLite Connection Research Findings

**Date:** 2025-12-29
**Issue:** CodeRabbit cross-thread SQLite connection usage (Cursor HIGH)
**File:** `scripts/agentica/unified_scope.py:132-151`

## Executive Summary

The `_run_async()` function in `unified_scope.py` uses `ThreadPoolExecutor` when an event loop already exists. This pattern can cause SQLite connection errors because connections created in one thread may be used in another. The codebase uses both synchronous `sqlite3` (BeadsTaskGraph) and asynchronous `aiosqlite` (MemoryService), and the current pattern creates potential thread-safety violations.

## The Problem

### Code Under Review

```python
# unified_scope.py:132-151
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

### How It's Used

```python
# unified_scope.py:601-619
if enable_memory:
    memory = MemoryService(session_id=session_id, db_path=db_path)
    _run_async(memory.connect())  # Creates connection in worker thread

    def remember(key: str, value: str) -> None:
        _run_async(memory.set_core(key, value))  # Uses connection in potentially different thread
```

## Python SQLite Thread Safety

### sqlite3 Module Threading Modes

| Mode | Value | Behavior |
|------|-------|----------|
| Single-thread | 0 | No mutexes, unsafe across threads |
| Multi-thread | 1 | Safe across threads, but NOT connections |
| Serialized | 2 | Fully thread-safe (default) |

**Key Constraint:** Even in serialized mode, SQLite connections should NOT be shared across threads. The CPython sqlite3 module explicitly checks and raises `ProgrammingError: SQLite objects created in a thread can only be used in that same thread.`

### sqlite3 check_same_thread Parameter

```python
# Default behavior - raises error if connection used from different thread
conn = sqlite3.connect("db.sqlite")  # check_same_thread=True (default)

# Allows cross-thread usage - bypasses the check
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
```

**Warning:** Using `check_same_thread=False` without external synchronization can cause corruption.

## aiosqlite Thread Safety

### How aiosqlite Works

aiosqlite uses a background thread with a queue to serialize all database operations:

```
Main Thread                 Worker Thread
    |                           |
    |--- put(operation) ------->|
    |                           |--- execute(operation)
    |<-- get(result) -----------|
    |                           |
```

### aiosqlite Thread Safety Model

| Aspect | Behavior |
|--------|----------|
| Connection creation | Must happen in worker thread |
| Operation dispatch | Thread-safe queue |
| Connection sharing | Safe across async tasks (not across threads) |
| Event loop affinity | Connection is bound to one event loop |

**Critical:** aiosqlite connections are bound to the event loop in which they were created. Using `asyncio.run()` in a ThreadPoolExecutor creates a NEW event loop per call, which breaks connection affinity.

## The Specific Bug Pattern

### Scenario: Running Inside Existing Event Loop

1. Main async code has a running event loop
2. `_run_async(memory.connect())` is called
3. ThreadPoolExecutor creates worker thread A
4. Worker thread A creates NEW event loop, runs `memory.connect()`
5. aiosqlite creates connection in worker thread A's event loop
6. Later, `_run_async(memory.set_core(...))` is called
7. ThreadPoolExecutor creates worker thread B
8. Worker thread B creates NEW event loop, tries to use the connection
9. Connection was created in thread A's event loop - **BUG**

### Manifestation

| Error Type | When It Occurs |
|------------|----------------|
| `sqlite3.ProgrammingError` | sqlite3 with check_same_thread=True (default) |
| `RuntimeError: attached to different loop` | aiosqlite connection used from wrong event loop |
| Silent corruption | check_same_thread=False without proper locking |

## Best Practices

### Pattern 1: asyncio.run() for Sync-Only Callers

```python
def sync_wrapper():
    # Only works when NO event loop is running
    return asyncio.run(async_operation())
```

**Limitation:** Crashes if called from within an async context.

### Pattern 2: nest_asyncio for Jupyter/REPL

```python
import nest_asyncio
nest_asyncio.apply()

# Now asyncio.run() works even with running loop
asyncio.run(async_operation())
```

**Limitation:** Modifies global event loop behavior, may cause other issues.

### Pattern 3: Dedicated Background Thread with Single Event Loop

```python
class AsyncRunner:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()
```

**Advantage:** All async operations run in SAME thread with SAME event loop.

### Pattern 4: Connection Per Call (Current MemoryService Pattern)

```python
# MemoryService._get_conn() creates fresh connection each call
@asynccontextmanager
async def _get_conn(self):
    conn = await aiosqlite.connect(str(self._db_path))
    try:
        yield conn
    finally:
        await conn.close()
```

**Analysis:** MemoryService already uses this pattern - each operation gets a fresh connection. This SHOULD work with ThreadPoolExecutor because no connection is reused across threads.

### Pattern 5: Sync-First with Async Escape Hatch

```python
# Make the base implementation synchronous, add async wrapper
class SyncMemoryService:
    def set_core(self, key: str, value: str) -> None:
        with self._get_conn() as conn:
            conn.execute(...)

async def async_set_core(self, key, value):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self.set_core, key, value)
```

## Analysis of Current Codebase

### MemoryService (aiosqlite)

| Aspect | Implementation | Thread Safety |
|--------|----------------|---------------|
| Connection creation | Fresh per operation | Safe |
| Connection caching | None (uses context manager) | Safe |
| Event loop affinity | New loop per ThreadPoolExecutor call | Issue with long-lived connections |

**Assessment:** Because `_get_conn()` creates a fresh connection each call, MemoryService is actually safe despite the ThreadPoolExecutor pattern. Each worker thread creates its own event loop and its own connection.

### BeadsTaskGraph (sqlite3)

| Aspect | Implementation | Thread Safety |
|--------|----------------|---------------|
| Connection creation | Fresh per operation | Safe |
| Connection caching | None (uses context manager) | Safe |
| check_same_thread | Default (True) | Safe |

**Assessment:** BeadsTaskGraph uses synchronous sqlite3 with connection-per-operation pattern. This is thread-safe.

### LocalCacheManager

| Aspect | Implementation | Thread Safety |
|--------|----------------|---------------|
| Storage | In-memory dict | NOT thread-safe |
| Documented | "Not thread-safe - intentionally" | Correct |

**Assessment:** LocalCacheManager is documented as not thread-safe. If used with ThreadPoolExecutor, race conditions are possible.

## Risk Assessment

| Component | Risk Level | Reason |
|-----------|------------|--------|
| MemoryService | LOW | Connection-per-operation pattern |
| BeadsTaskGraph | LOW | Connection-per-operation pattern |
| LocalCacheManager | MEDIUM | Not thread-safe, but single-agent intended |
| _run_async pattern | MEDIUM | Correct but fragile - future changes could break |

## Recommendations Summary

1. **Current code is safe due to connection-per-operation pattern** - Both MemoryService and BeadsTaskGraph create fresh connections for each operation, avoiding cross-thread connection sharing.

2. **The ThreadPoolExecutor pattern is fragile** - If anyone adds connection caching or reuse, the code will break. Consider documenting this constraint.

3. **Consider nest_asyncio for simpler nesting** - Would eliminate need for ThreadPoolExecutor at the cost of global event loop modification.

4. **Consider dedicated runner thread** - Pattern 3 above would be more robust for long-term maintenance.

5. **LocalCacheManager documentation is correct** - The "not thread-safe" comment accurately reflects the design intention.

## References

- Python sqlite3 documentation: https://docs.python.org/3/library/sqlite3.html#multithreading
- aiosqlite documentation: https://aiosqlite.omnilib.dev/en/stable/
- asyncio thread safety: https://docs.python.org/3/library/asyncio-dev.html#concurrency-and-multithreading
- SQLite threading modes: https://www.sqlite.org/threadsafe.html
- nest_asyncio: https://github.com/erdewit/nest_asyncio
