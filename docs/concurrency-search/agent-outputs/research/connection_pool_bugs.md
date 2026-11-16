# Connection Pool Bug Patterns

Generated: 2025-12-29

## Executive Summary

This research documents connection pooling best practices for asyncpg and httpx AsyncClient, and verifies our implementation against these patterns. The codebase (`postgres_pool.py` and `embedding_service.py`) follows most best practices correctly, with proper singleton patterns, context managers, retry logic, and client reuse.

## Research Question

What are the best practices for asyncpg connection pools and httpx AsyncClient connection pooling, and does our implementation follow them?

---

## asyncpg Pool Best Practices

### Pattern 1: Pool Exhaustion Under Load

**Description:**
When all connections in the pool are in use, new acquire() calls will block. Without a timeout, this can cause indefinite hangs (starvation).

**Best Practice:**
- Always set `acquire_timeout` when creating the pool
- Default should be reasonable (30 seconds is common)
- Monitor for TimeoutError and handle gracefully

**Our Implementation (postgres_pool.py):**
```python
# Lines 56-88: _get_pool_config()
def _get_pool_config() -> dict:
    max_size_str = os.environ.get("AGENTICA_MAX_POOL_SIZE", "10")
    acquire_timeout_str = os.environ.get("AGENTICA_ACQUIRE_TIMEOUT", "30")
    ...
    return {
        "min_size": min_size,
        "max_size": max_size,
        "acquire_timeout": acquire_timeout,  # CORRECTLY SET
        "command_timeout": 60,
        "statement_cache_size": 100,
    }
```

**Status: COMPLIANT** - `acquire_timeout` is set to 30 seconds by default and is configurable via `AGENTICA_ACQUIRE_TIMEOUT` environment variable.

---

### Pattern 2: Singleton Pool with Thread-Safe Initialization

**Description:**
Multiple concurrent callers might try to create the pool simultaneously, leading to multiple pool instances or race conditions.

**Best Practice:**
- Use a lock to protect pool creation
- Check for existing pool inside the lock
- Make initialization idempotent

**Our Implementation (postgres_pool.py):**
```python
# Lines 40-42: Global state
_pool: Pool | None = None
_pool_lock = asyncio.Lock()

# Lines 123-145: get_pool()
async def get_pool() -> Pool:
    global _pool
    async with _pool_lock:
        if _pool is None:
            config = _get_pool_config()
            _pool = await asyncpg.create_pool(
                get_connection_string(),
                init=_init_connection,
                **config,
            )
    return _pool
```

**Status: COMPLIANT** - Uses `asyncio.Lock()` for thread-safe singleton initialization. Tests verify this in `test_postgres_pool.py:TestPoolSingleton`.

---

### Pattern 3: Connection Leak Prevention

**Description:**
Connections can leak if exceptions occur and the connection is not returned to the pool.

**Best Practice:**
- Always use context managers (`async with pool.acquire()`)
- Never manually acquire without a try/finally
- Test with exception scenarios

**Our Implementation (postgres_pool.py):**
```python
# Lines 168-178: get_connection()
@asynccontextmanager
async def get_connection():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
```

**Status: COMPLIANT** - Uses `@asynccontextmanager` and nested `async with` for guaranteed cleanup. Tests verify in `test_async_pool_bugs.py:test_connection_leak_after_many_exceptions`.

---

### Pattern 4: Retry with Exponential Backoff

**Description:**
Database connections can fail transiently (network issues, database restarts). Immediate retries without backoff can overwhelm the database.

**Best Practice:**
- Implement exponential backoff between retries
- Set a maximum retry count
- Raise the last error after exhausting retries

**Our Implementation (postgres_pool.py):**
```python
# Lines 199-252: get_pool_with_retry()
async def get_pool_with_retry(
    max_retries: int = 5,
    initial_delay: float = 0.5,
) -> Pool:
    ...
    for attempt in range(max_retries):
        try:
            pool = await asyncpg.create_pool(...)
            _pool = pool
            return pool
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
    ...
```

**Status: COMPLIANT** - Implements exponential backoff (delay doubles each attempt). Tests verify in `test_postgres_pool.py:TestConnectionRetry`.

---

### Pattern 5: Lock Held During Retry Loop

**Description:**
If the lock is released between retry attempts, multiple callers might race to create pools.

**Best Practice:**
- Hold the lock throughout the entire retry loop
- Fast-path check if pool already exists

**Our Implementation (postgres_pool.py):**
```python
# Lines 225-252: Lock held throughout
async with _pool_lock:
    # Check if pool already exists (fast path)
    if _pool is not None:
        return _pool

    # Retry loop happens INSIDE the lock
    for attempt in range(max_retries):
        ...
```

**Status: COMPLIANT** - Lock is held during entire retry sequence. Test verifies in `test_postgres_pool.py:test_retry_holds_lock_throughout`.

---

### Pattern 6: Health Check

**Description:**
Applications need a way to verify pool health without crashing.

**Best Practice:**
- Provide a health check function that acquires and releases a connection
- Return structured error information, not just boolean
- Make logging optional

**Our Implementation (postgres_pool.py):**
```python
# Lines 255-284: health_check()
async def health_check(log_errors: bool = False) -> tuple[bool, str | None]:
    try:
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        return (True, None)
    except asyncpg.PostgresConnectionError as e:
        error_type = "connection_error"
        ...
        return (False, error_type)
```

**Status: COMPLIANT** - Returns tuple of (is_healthy, error_type) with optional logging.

---

### Pattern 7: Transaction Context Manager

**Description:**
Transactions should auto-commit on success and rollback on exception.

**Best Practice:**
- Wrap transaction in context manager
- Use asyncpg's built-in transaction() method
- Nest inside connection context manager

**Our Implementation (postgres_pool.py):**
```python
# Lines 287-304: get_transaction()
@asynccontextmanager
async def get_transaction() -> AsyncGenerator[Connection, None]:
    async with get_connection() as conn:
        async with conn.transaction():
            yield conn
```

**Status: COMPLIANT** - Properly nests transaction inside connection context.

---

### Pattern 8: min_size Scaling

**Description:**
`min_size` should scale with `max_size` to maintain warm connections.

**Best Practice:**
- Scale min_size as a percentage of max_size (e.g., 20%)
- Set a minimum floor (e.g., 2 connections)

**Our Implementation (postgres_pool.py):**
```python
# Lines 79-80: Scaling logic
min_size = max(2, max_size // 5)  # 20% of max, minimum 2
```

**Status: COMPLIANT** - Scales at 20% with floor of 2.

---

## httpx AsyncClient Best Practices

### Pattern 1: Connection Reuse vs Fresh Connections

**Description:**
Creating a new `httpx.AsyncClient` for each request defeats connection pooling. Each client manages its own connection pool.

**Best Practice:**
- Create one AsyncClient instance and reuse it across requests
- Store the client as an instance attribute in `__init__`
- Avoid creating clients inside request methods

**Our Implementation (embedding_service.py):**
```python
# Lines 85-104: OpenAIEmbeddingProvider.__init__()
def __init__(
    self,
    api_key: str | None = None,
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
):
    ...
    self._client = httpx.AsyncClient(timeout=30.0)  # PERSISTENT CLIENT

# Lines 106-108: Cleanup method
async def aclose(self) -> None:
    await self._client.aclose()
```

**Status: COMPLIANT** - Client is created once in `__init__` and reused. Tests verify in `test_embedding_client_reuse.py`.

---

### Pattern 2: Proper Client Lifecycle Management

**Description:**
AsyncClient must be explicitly closed to release connections and avoid resource leaks.

**Best Practice:**
- Implement `aclose()` method for explicit cleanup
- Support async context manager protocol (`__aenter__`, `__aexit__`)
- Close the client when the service shuts down

**Our Implementation (embedding_service.py):**
```python
# Lines 110-116: Context manager support
async def __aenter__(self) -> OpenAIEmbeddingProvider:
    return self

async def __aexit__(self, *args) -> None:
    await self.aclose()
```

**Status: COMPLIANT** - Full async context manager support. Same pattern in VoyageEmbeddingProvider (lines 253-263).

---

### Pattern 3: Timeout Configuration

**Description:**
HTTP requests can hang indefinitely without proper timeouts.

**Best Practice:**
- Set reasonable connect and read timeouts
- 30 seconds is a common default for API calls

**Our Implementation (embedding_service.py):**
```python
# Line 104: Timeout set in constructor
self._client = httpx.AsyncClient(timeout=30.0)

# Line 251: VoyageEmbeddingProvider also sets timeout
self._client = httpx.AsyncClient(timeout=30.0)
```

**Status: COMPLIANT** - 30 second timeout configured.

---

### Pattern 4: Retry Logic for Transient Failures

**Description:**
API calls can fail transiently. Immediate retries without delay can trigger rate limiting.

**Best Practice:**
- Implement retry with exponential backoff
- Set a maximum retry count
- Increase delay on each retry

**Our Implementation (embedding_service.py):**
```python
# Lines 157-193: _call_api() with retries
async def _call_api(self, texts: list[str]) -> list[list[float]]:
    last_error: Exception | None = None

    for attempt in range(self.max_retries):
        try:
            response = await self._client.post(...)
            response.raise_for_status()
            ...
        except Exception as e:
            last_error = e
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))

    raise EmbeddingError(f"API call failed after {self.max_retries} attempts: {last_error}")
```

**Status: COMPLIANT** - Linear backoff (delay * attempt). VoyageEmbeddingProvider uses same pattern (lines 284-316).

---

### Pattern 5: Service Wrapper Cleanup

**Description:**
When wrapping providers in a service class, the wrapper must also expose cleanup methods.

**Best Practice:**
- EmbeddingService should delegate `aclose()` to the underlying provider
- Support async context manager at the service level

**Our Implementation (embedding_service.py):**
```python
# Lines 632-643: EmbeddingService lifecycle
async def aclose(self) -> None:
    if hasattr(self._provider, "aclose"):
        await self._provider.aclose()

async def __aenter__(self) -> EmbeddingService:
    return self

async def __aexit__(self, *args) -> None:
    await self.aclose()
```

**Status: COMPLIANT** - Properly delegates to provider.

---

### Pattern 6: Thread-Safe Cache Access

**Description:**
Embedding caches shared across concurrent requests need synchronization.

**Best Practice:**
- Use asyncio.Lock for cache access
- Release lock before making network calls

**Our Implementation (embedding_service.py):**
```python
# Lines 509-510: Cache lock
self._cache: dict[str, list[float]] = {}
self._cache_lock = asyncio.Lock()

# Lines 553-565: embed() with lock
async def embed(self, text: str) -> list[float]:
    if self.cache_enabled:
        cache_key = self._cache_key(text)
        async with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

    embedding = await self._provider.embed(text)  # OUTSIDE lock

    if self.cache_enabled:
        async with self._cache_lock:
            self._cache[self._cache_key(text)] = embedding
```

**Status: COMPLIANT** - Lock held only during cache access, not during API calls.

---

## Sources

- asyncpg documentation: https://magicstack.github.io/asyncpg/current/
- httpx documentation: https://www.python-httpx.org/async/
- Codebase files:
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/postgres_pool.py`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/embedding_service.py`
- Test files:
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_postgres_pool.py`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_postgres_pool_timeout.py`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_async_pool_bugs.py`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_embedding_client_reuse.py`

## Recommendations

1. **All patterns are correctly implemented** - Both `postgres_pool.py` and `embedding_service.py` follow established best practices.

2. **Consider adding connection pool metrics** - For production observability, consider exposing:
   - Current pool size
   - Available connections
   - Acquisition wait times
   - Connection error rates

3. **Document environment variables** - The following are configurable but could use more visibility:
   - `AGENTICA_MAX_POOL_SIZE` (default: 10)
   - `AGENTICA_ACQUIRE_TIMEOUT` (default: 30s)
   - `AGENTICA_POSTGRES_URL` (required in production)

## Open Questions

1. **Backoff strategy difference**: postgres_pool uses true exponential backoff (doubles), while embedding_service uses linear backoff (multiplies by attempt number). Is this intentional?

2. **Statement cache size**: `statement_cache_size=100` is set in postgres_pool. Is this value tuned for the workload, or a default?

3. **Local embedding provider**: Uses `run_in_executor` for sync sentence-transformers. Under high concurrency, could this exhaust the executor thread pool?
