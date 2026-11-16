# Asyncio Concurrency Bug Patterns

**Research Date**: 2025-12-29
**Researcher**: Research Agent (Claude Opus 4.5)
**Scope**: Python asyncio concurrency vulnerabilities and best practices

## Executive Summary

This research documents common Python asyncio concurrency bug patterns and cross-references them with the claude-continuity-kit codebase. The audit identified 39 total issues across 5 categories, with 11 HIGH priority findings. Several critical fixes have already been applied (e.g., threading.Lock to asyncio.Lock conversion, acquire_timeout configuration).

---

## Pattern 1: Threading Lock in Async Context

### Description
Using `threading.Lock` inside async functions blocks the entire event loop when the lock is held. Other coroutines cannot make progress even if they don't need the lock, because the GIL and the blocking lock semantics prevent the event loop from yielding.

### How to Detect
- Search for `threading.Lock()` in files that also contain `async def`
- Look for `with self._lock:` (sync context manager) inside async functions
- Check for `asyncio.gather()` calls that invoke code paths acquiring threading locks

### Code Pattern (BAD)
```python
import threading
import asyncio

class BadProcessor:
    def __init__(self):
        self._lock = threading.Lock()  # WRONG

    async def process(self, data):
        with self._lock:  # Blocks event loop!
            await self.do_work(data)
```

### Code Pattern (GOOD)
```python
import asyncio

class GoodProcessor:
    def __init__(self):
        self._lock = asyncio.Lock()  # Correct

    async def process(self, data):
        async with self._lock:  # Yields to event loop
            await self.do_work(data)
```

### Our Exposure
**STATUS: FIXED**

The codebase previously had this issue in `span_processor.py`. It has been corrected:
- `scripts/agentica/span_processor.py:142` now uses `_lock: asyncio.Lock = field(default_factory=asyncio.Lock)`
- Methods like `add_summary()`, `get_reference_context()`, and `all_summaries()` now use `async with self._lock:`

**Source**: Python asyncio documentation, PEP 3156

---

## Pattern 2: Check-Then-Act Race (Lazy Initialization)

### Description
Reading a shared variable, checking its value, and then acting based on that check is not atomic. Between the check and the act, another coroutine can change the value.

### How to Detect
- Look for patterns like `if self.x is None: self.x = await create()`
- Search for double-checked locking without proper synchronization
- Find lazy initialization patterns in concurrent code

### Code Pattern (BAD)
```python
async def ensure_resource(self):
    if self.resource is None:  # Check
        self.resource = await create_expensive_resource()  # Act
    return self.resource
# Two concurrent calls both see None, both create resources
```

### Code Pattern (GOOD)
```python
async def ensure_resource(self):
    async with self._init_lock:
        if self.resource is None:
            self.resource = await create_expensive_resource()
    return self.resource
```

### Our Exposure
**STATUS: DOCUMENTED**

This pattern exists in several places:
- `scripts/agentica/patterns/hierarchical.py:204-223` - `_ensure_coordinator()` lazy spawn
- `scripts/agentica/patterns/hierarchical.py:227-247` - `_ensure_specialist()` lazy spawn

The Hierarchical pattern needs `_coordinator_lock` and `_specialist_lock` added.

**Source**: Python threading documentation, concurrent programming best practices

---

## Pattern 3: Asyncio Lock Created at Wrong Scope

### Description
`asyncio.Lock()` is bound to the event loop that created it. If a lock is created in one event loop and accessed from another (common in tests with loop switching), it raises `RuntimeError: Event loop is closed` or behaves incorrectly.

### How to Detect
- Look for `asyncio.Lock()` created inside async functions (not in `__init__`)
- Check for locks passed via closures to nested coroutines
- Test with `asyncio.run()` vs `event_loop.run_until_complete()` differences

### Code Pattern (BAD)
```python
async def process_batch(items):
    lock = asyncio.Lock()  # Created inside function

    async def process_item(item):
        async with lock:  # May fail if event loop changes
            await do_work(item)

    await asyncio.gather(*[process_item(i) for i in items])
```

### Code Pattern (GOOD)
```python
class BatchProcessor:
    def __init__(self):
        self._lock = asyncio.Lock()  # Created at class level

    async def process_batch(self, items):
        async def process_item(item):
            async with self._lock:
                await do_work(item)
        await asyncio.gather(*[process_item(i) for i in items])
```

### Our Exposure
**STATUS: MEDIUM RISK**

Previously documented at `span_processor.py:699` where `decisions_lock = asyncio.Lock()` was created inside `extract_decisions()`. The current codebase shows this has been addressed in the context class.

**Source**: asyncio module documentation, Python issue tracker #32311

---

## Pattern 4: Missing asyncio.Lock for Concurrent State Mutations

### Description
Python dicts are thread-safe for atomic operations (single get/set), but compound operations (read-modify-write, iteration while mutating) are not. In async code with `await` points, even dict operations can race.

### How to Detect
- Look for shared dicts modified by multiple coroutines
- Find patterns like `d[key] = d.get(key, 0) + 1` without locks
- Check for dict iteration concurrent with modification

### Code Pattern (BAD)
```python
class SharedState:
    def __init__(self):
        self.data = {}

    async def increment(self, key):
        current = self.data.get(key, 0)  # Read
        await asyncio.sleep(0)  # Yield point - other coroutine can modify
        self.data[key] = current + 1  # Write - stale value!
```

### Code Pattern (GOOD)
```python
class SharedState:
    def __init__(self):
        self.data = {}
        self._lock = asyncio.Lock()

    async def increment(self, key):
        async with self._lock:
            self.data[key] = self.data.get(key, 0) + 1
```

### Our Exposure
**STATUS: FIXED**

Multiple patterns have been updated:
- `scripts/agentica/patterns/blackboard.py:63` - Now has `self._lock = asyncio.Lock()`
- `scripts/agentica/patterns/circuit_breaker.py:193,200` - Uses `self._state_lock`

**Source**: Python GIL documentation, asyncio concurrency guide

---

## Pattern 5: Task Cancellation Without Cleanup

### Description
When `asyncio.Task.cancel()` is called, a `CancelledError` is raised at the next `await` point. If cleanup code (releasing locks, closing connections) is not in `finally` blocks, resources leak.

### How to Detect
- Look for `asyncio.gather()` without `return_exceptions=True` for partial failures
- Find async context managers without `finally` blocks
- Check for `try/except` that catches `Exception` but not `CancelledError`

### Code Pattern (BAD)
```python
async def do_work():
    conn = await get_connection()
    result = await expensive_operation(conn)  # If cancelled here...
    await release_connection(conn)  # ...this never runs
    return result
```

### Code Pattern (GOOD)
```python
async def do_work():
    conn = await get_connection()
    try:
        result = await expensive_operation(conn)
        return result
    finally:
        await release_connection(conn)  # Always runs
```

### Our Exposure
**STATUS: PARTIAL**

The codebase uses `asyncio.gather()` extensively. Some locations handle exceptions properly, others may not. The async context manager patterns in `postgres_pool.py` are correctly implemented with `@asynccontextmanager` which handles cleanup.

**Source**: PEP 525 (Asynchronous Generators), asyncio.Task documentation

---

## Pattern 6: Pool Exhaustion Without Timeout

### Description
Connection pools without acquire timeouts can hang indefinitely if all connections are in use. Under load, new requests wait forever instead of failing fast.

### How to Detect
- Check `asyncpg.create_pool()` for `timeout` parameter (old) or connection limits
- Look for `pool.acquire()` without timeout
- Find any resource acquisition that can block indefinitely

### Code Pattern (BAD)
```python
pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
# No acquire_timeout - waits forever when pool exhausted
async with pool.acquire() as conn:
    await conn.fetch(...)
```

### Code Pattern (GOOD)
```python
pool = await asyncpg.create_pool(
    dsn,
    min_size=2,
    max_size=10,
    command_timeout=60,
)
# Use asyncio.wait_for for acquire timeout
try:
    conn = await asyncio.wait_for(pool.acquire(), timeout=30)
except asyncio.TimeoutError:
    raise PoolExhaustedError("Connection pool exhausted")
```

### Our Exposure
**STATUS: FIXED**

The `postgres_pool.py` module now has proper configuration:
- `scripts/agentica/postgres_pool.py:67,85` - `acquire_timeout` configurable via `AGENTICA_ACQUIRE_TIMEOUT` env var (default 30s)
- `scripts/agentica/postgres_pool.py:86` - `command_timeout=60` set

**Source**: asyncpg documentation, production database best practices

---

## Pattern 7: SQLite Without Busy Timeout

### Description
SQLite uses file-level locking. Without `PRAGMA busy_timeout`, concurrent access immediately fails with "database is locked" instead of waiting for the lock to be released.

### How to Detect
- Search for `sqlite3.connect()` or `aiosqlite.connect()` calls
- Check for `PRAGMA busy_timeout` execution after connection
- Look for "database is locked" error handling

### Code Pattern (BAD)
```python
async with aiosqlite.connect("db.sqlite") as db:
    await db.execute("INSERT ...")  # Fails immediately if locked
```

### Code Pattern (GOOD)
```python
async with aiosqlite.connect("db.sqlite") as db:
    await db.execute("PRAGMA busy_timeout = 5000")  # Wait up to 5 seconds
    await db.execute("INSERT ...")
```

### Our Exposure
**STATUS: DOCUMENTED (needs verification)**

The coordination database and memory service use SQLite. The audit identified this as a top-5 fix:
- TypeScript hooks making SQLite calls need `PRAGMA busy_timeout`
- Check `scripts/agentica/coordination.py` for busy_timeout usage

**Source**: SQLite documentation, "WAL mode" best practices

---

## Pattern 8: HTTP Client Created Per Request

### Description
Creating a new `httpx.AsyncClient` or `aiohttp.ClientSession` for each request wastes connection pool benefits and can exhaust file descriptors.

### How to Detect
- Look for `async with httpx.AsyncClient() as client:` inside request handlers
- Find `aiohttp.ClientSession()` created inside loops
- Check for client creation without reuse

### Code Pattern (BAD)
```python
async def fetch_data(url):
    async with httpx.AsyncClient() as client:  # New client per call!
        return await client.get(url)
```

### Code Pattern (GOOD)
```python
class DataFetcher:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def fetch_data(self, url):
        client = await self.get_client()
        return await client.get(url)

    async def close(self):
        if self._client:
            await self._client.aclose()
```

### Our Exposure
**STATUS: DOCUMENTED (HIGH PRIORITY)**

The audit identified `embedding_service.py` as creating HTTP clients per request:
- This causes connection pool exhaustion under load
- Each client creates new TCP connections (slow)
- File descriptor limits can be hit

**Source**: httpx documentation, aiohttp best practices

---

## Pattern 9: os.environ Mutation in Concurrent Code

### Description
`os.environ` is a global, mutable dict. Concurrent coroutines modifying environment variables race with each other, causing child processes to receive wrong values.

### How to Detect
- Look for `os.environ[key] = value` in async code
- Check for environment variable context managers that don't handle cancellation
- Find spawn calls that depend on recently-set env vars

### Code Pattern (BAD)
```python
async def spawn_agent(agent_id):
    os.environ["AGENT_ID"] = agent_id  # Race with other spawn calls
    proc = await asyncio.create_subprocess_exec(...)
```

### Code Pattern (GOOD)
```python
async def spawn_agent(agent_id):
    env = os.environ.copy()
    env["AGENT_ID"] = agent_id  # Local copy, no mutation
    proc = await asyncio.create_subprocess_exec(..., env=env)
```

### Our Exposure
**STATUS: MOSTLY FIXED**

Most patterns now use context managers or local copies:
- `scripts/agentica/patterns/swarm.py` - Uses `@contextmanager` (safer)
- `scripts/agentica/patterns/jury.py` - Uses `@contextmanager` (safer)
- Some patterns still mutate `os.environ` directly before spawn

Remaining risk: Context managers can leak if task is cancelled during yield.

**Source**: Python multiprocessing documentation, subprocess best practices

---

## Summary of Codebase Status

| Pattern | Status | Files Affected |
|---------|--------|----------------|
| Threading Lock in Async | FIXED | span_processor.py |
| Check-Then-Act Race | DOCUMENTED | hierarchical.py |
| Lock Created at Wrong Scope | MEDIUM RISK | (various) |
| Missing Lock for State | FIXED | blackboard.py, circuit_breaker.py |
| Task Cancellation Cleanup | PARTIAL | (various) |
| Pool Exhaustion | FIXED | postgres_pool.py |
| SQLite Busy Timeout | NEEDS VERIFICATION | coordination.py, hooks |
| HTTP Client Per Request | HIGH PRIORITY | embedding_service.py |
| os.environ Mutation | MOSTLY FIXED | pattern spawn code |

## Recommendations

### Immediate Actions
1. Verify SQLite `PRAGMA busy_timeout` is set in all database code
2. Refactor `embedding_service.py` to reuse HTTP clients
3. Add `asyncio.Lock` to Hierarchical pattern lazy initialization

### Best Practices Going Forward
1. Always use `asyncio.Lock` in async code, never `threading.Lock`
2. Create locks at class/module level, not inside async functions
3. Use `finally` blocks for all cleanup in async code
4. Pass environment as explicit `env=` parameter to subprocess
5. Set timeouts on all blocking operations (acquire, connect, execute)
6. Use connection pooling with health checks and limits

## Sources

- Python asyncio documentation: https://docs.python.org/3/library/asyncio.html
- asyncpg documentation: https://magicstack.github.io/asyncpg/
- httpx documentation: https://www.python-httpx.org/
- PEP 3156 - Asynchronous IO Support
- SQLite documentation: https://www.sqlite.org/pragma.html#pragma_busy_timeout
- Existing codebase audit: `/docs/concurrency-search/*.md`
