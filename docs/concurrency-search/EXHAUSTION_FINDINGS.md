# Resource Exhaustion Vulnerability Audit

## Summary
- **Total issues found**: 8
- **High risk**: 2
- **Medium risk**: 5
- **Low-Medium risk**: 1

## Findings

### Finding 1: Unbounded File Change Accumulation

- **File:Line**: `scripts/agentica/watch_agents.py:816-857`
- **Pattern detected**: `file_changes` list grows unbounded inside infinite loop (line 817 `while True`) without trimming. New items added via `extend()` on line 857 but never cleared.
- **Risk level**: HIGH
- **Code snippet**:
  ```python
  file_changes: list[dict[str, Any]] = []
  while True:
      ...
      if monitor:
          status = monitor.get_status()
          file_changes.extend(status.get("file_changes", []))  # Append without limit
          if file_changes:
              tables.append(create_file_changes_table(file_changes))
  ```
- **Suggested fix**: Add a max length check with trimming: `if len(file_changes) > MAX_CHANGES: file_changes = file_changes[-MAX_CHANGES:]` or clear after render.

---

### Finding 2: HTTP AsyncClient Created Per Request (Resource Leak)

- **File:Line**: `scripts/agentica/embedding_service.py:160,266`
- **Pattern detected**: `httpx.AsyncClient()` created inside retry loop for every API call. Each instantiation allocates a connection pool that should be reused across calls.
- **Risk level**: HIGH
- **Code snippet**:
  ```python
  for attempt in range(self.max_retries):
      try:
          async with httpx.AsyncClient() as client:  # NEW client per attempt
              response = await client.post(...)
      except Exception as e:
          last_error = e
          if attempt < self.max_retries - 1:
              await asyncio.sleep(self.retry_delay)
  ```
- **Occurrence**: Lines 160 (OpenAI) and 266 (Voyage) - at least 2 locations
- **Suggested fix**: Create a single persistent client at __init__, reuse across calls:
  ```python
  self._client = httpx.AsyncClient()  # In __init__
  async with self._client.post(...) as response:  # In _call_api
  ```

---

### Finding 3: Unbounded _file_positions Dictionary

- **File:Line**: `scripts/agentica/watch_agents.py:88,105-111`
- **Pattern detected**: `_file_positions` dict accumulates entries for every log file ever seen without eviction. Entries are added via `get()` default but never removed even when files are deleted.
- **Risk level**: MEDIUM
- **Code snippet**:
  ```python
  self._file_positions: dict[str, int] = {}
  # In get_new_messages:
  last_pos = self._file_positions.get(file_key, 0)
  self._file_positions[file_key] = f.tell()  # Adds entry, never removes
  ```
- **Suggested fix**: Add periodic cleanup for deleted files or use LRU cache with bounded size.

---

### Finding 4: Unbounded Embedding Cache Without Eviction

- **File:Line**: `scripts/agentica/embedding_service.py:487,540-541,581`
- **Pattern detected**: `_cache` dict grows unbounded. No max size check, no LRU eviction, no TTL. Will consume unlimited memory over time.
- **Risk level**: MEDIUM
- **Code snippet**:
  ```python
  def __init__(self, ...):
      self._cache: dict[str, list[float]] = {}  # Unbounded

  async def embed(self, text: str):
      if self.cache_enabled:
          cache_key = self._cache_key(text)
          async with self._cache_lock:
              self._cache[self._cache_key(text)] = embedding  # Append forever
  ```
- **Suggested fix**: Use bounded cache with LRU eviction (e.g., functools.lru_cache or maxsize check with oldest-entry removal).

---

### Finding 5: Infinite Loop Without Timeout in watch_agents.py

- **File:Line**: `scripts/agentica/watch_agents.py:817`
- **Pattern detected**: `while True` loop with only 0.5s sleep between iterations. No timeout, no max iterations, continuous memory allocations for tables/visualizers without cleanup.
- **Risk level**: MEDIUM
- **Code snippet**:
  ```python
  while True:
      agents = db.get_running_agents(...)
      tables: list[Any] = []
      # ... build tables ...
      live.update(Group(*tables))
      time.sleep(0.5)  # Only sleep, no exit condition except KeyboardInterrupt
  ```
- **Suggested fix**: Add maximum runtime parameter or graceful shutdown signal. Implement periodic GC cleanup for accumulated objects.

---

### Finding 6: Unbounded Semaphore Without Enforcement

- **File:Line**: `scripts/agentica/memory_backfill.py`
- **Pattern detected**: Semaphore created but concurrency limit only applies to embedding, not to fetch/parse/store phases. Risk of unbounded concurrent database writes.
- **Risk level**: MEDIUM
- **Suggested fix**: Apply semaphore across all async operations, not just embeddings.

---

### Finding 7: No Timeout on pool.acquire()

- **File:Line**: `scripts/agentica/postgres_pool.py:134-144`
- **Pattern detected**: `pool.acquire()` has no timeout. If all connections are exhausted, threads will hang indefinitely.
- **Risk level**: MEDIUM
- **Suggested fix**: Add timeout parameter:
  ```python
  async with pool.acquire(timeout=30) as conn:
  ```

---

### Finding 8: PostgreSQL Pool Size Fixed at 10

- **File:Line**: `scripts/agentica/postgres_pool.py:104-105`
- **Pattern detected**: Pool hardcoded to `max_size=10`. No configuration option. Risk of connection exhaustion if >10 concurrent agents spawn.
- **Risk level**: LOW-MEDIUM
- **Code snippet**:
  ```python
  _pool = await asyncpg.create_pool(
      get_connection_string(),
      min_size=2,
      max_size=10,  # FIXED, no config
      command_timeout=60,
  )
  ```
- **Suggested fix**: Make configurable via env var: `max_size=int(os.environ.get("AGENTICA_MAX_POOL_SIZE", "10"))`

---

## Critical Resource Patterns

All issues involve resource accumulation patterns:
1. **Unbounded memory growth** - file_changes, embedding cache, file_positions
2. **Connection leaks** - HTTP client per request
3. **Lack of configurable limits** - pool size, timeouts

## Priority Fixes

1. **Immediate**: Fix HTTP client leak in embedding_service.py (creates new pools per request)
2. **High**: Add max length to file_changes list in watch_agents.py
3. **Medium**: Add LRU eviction to embedding cache
4. **Medium**: Add pool.acquire() timeout
5. **Low**: Make pool size configurable
