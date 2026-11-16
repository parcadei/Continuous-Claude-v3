# Deadlock Vulnerability Audit

## Summary
- **Total issues found**: 6
- **High risk**: 2
- **Medium risk**: 3
- **Low risk**: 1

## Findings

### Finding 1: THREADING LOCK IN ASYNC CONTEXT (HIGHEST RISK)

- **File:Line**: `scripts/agentica/span_processor.py:143-173`
- **Pattern detected**: `SpanProcessingContext` uses `threading.Lock` for synchronization, but it's accessed from async contexts without proper coordination. In `extract_summaries()` (lines 558-645), the async `process_chunk()` function calls `context.add_summary()` which acquires a `threading.Lock` while inside an async function running under `asyncio.gather()`.
- **Risk level**: HIGH
- **Why it's a problem**:
  - Threading locks (synchronous) should NEVER be acquired from async code
  - When `asyncio.gather()` runs multiple `process_chunk()` coroutines, they may attempt to acquire the threading lock
  - If the event loop yields while holding a threading lock, other threads could deadlock
  - Python's asyncio is not thread-safe for blocking operations
- **Code path**:
  ```
  Line 645: await asyncio.gather(*[process_chunk(chunk) for chunk in chunks])
    └─> process_chunk() [async] at line 582
        └─> context.add_summary() at line 635
            └─> with self._lock: [threading.Lock] at line 149
  ```
- **Suggested fix**: Replace `threading.Lock` with `asyncio.Lock` in `SpanProcessingContext`, and use `async with` instead of `with` for all lock acquisitions. Update all methods to be async where they acquire locks.

---

### Finding 2: MIXED LOCK TYPES IN SAME OPERATION (HIGH RISK)

- **File:Line**: `scripts/agentica/span_processor.py:680-770`
- **Pattern detected**: In `extract_decisions()`, there's an `asyncio.Lock` (`decisions_lock` at line 699) protecting `decisions` list, but the same function uses `context.get_reference_context()` which acquires a `threading.Lock` internally.
- **Risk level**: HIGH
- **Why it's a problem**:
  - Line 707: `ref_context = context.get_reference_context(span_id)` acquires threading lock inside async coroutine
  - Line 758: `async with decisions_lock:` tries to acquire asyncio lock
  - If multiple tasks contend for these different lock types, it creates a mixed-lock scenario
  - Asyncio coroutines holding threading locks can block the event loop
  - Threading lock holders waiting for asyncio events cause deadlock
- **Code path**:
  ```
  Line 767: await asyncio.gather(*[process_chunk_with_context(chunk) for chunk in chunks])
    └─> process_chunk_with_context() [async] at line 701
        └─> context.get_reference_context() at line 707
            └─> with self._lock: [threading.Lock] at line 166
        └─> async with decisions_lock: [asyncio.Lock] at line 758
  ```
- **Suggested fix**: Convert `SpanProcessingContext` to use `asyncio.Lock` exclusively and make all methods async that acquire locks.

---

### Finding 3: LOCK ORDERING INCONSISTENCY (MEDIUM RISK)

- **File:Line**: `scripts/agentica/span_processor.py:960-961`
- **Pattern detected**: In `SpanProcessor.process()`, line 960-961 directly modifies `self.context.span_summaries` without acquiring the lock, while other code paths use `context.add_summary()`.
- **Risk level**: MEDIUM
- **Why it's a problem**:
  - Line 961: `self.context.span_summaries[span_id].references = refs` bypasses lock protection
  - Meanwhile, `all_summaries()` at line 181 acquires lock to read the same dict
  - Other threads/coroutines might be reading while direct assignment happens
  - Creates race condition for dictionary mutation
- **Code path**:
  ```python
  # Lines 959-961: Populate references in summaries from ref_graph
  for span_id, refs in ref_graph.items():
      if span_id in self.context.span_summaries:
          self.context.span_summaries[span_id].references = refs  # ← UNPROTECTED
  ```
- **Suggested fix**: Add a method `set_references()` to `SpanProcessingContext` that acquires the lock before modifying references.

---

### Finding 4: ASYNCIO LOCK CREATED IN FUNCTION (MEDIUM RISK)

- **File:Line**: `scripts/agentica/span_processor.py:699`
- **Pattern detected**: `decisions_lock = asyncio.Lock()` is created inside the async function `extract_decisions()`, then passed to nested async functions via closure.
- **Risk level**: MEDIUM
- **Why it's a problem**:
  - The lock is created in one event loop and used by coroutines
  - If `extract_decisions()` is called from different event loops, the lock becomes invalid
  - Asyncio locks are bound to the event loop that created them
  - Test environments with loop switching can cause "asyncio.InvalidStateError"
- **Suggested fix**: Create the lock at the class level (`SpanProcessor.__init__`) or use a context manager to ensure the lock is created and destroyed within the same event loop.

---

### Finding 5: SHARED THREADING LOCK IN CROSS-THREAD SCENARIO (MEDIUM RISK)

- **File:Line**: `scripts/agentica/claude_scope.py:147-207`
- **Pattern detected**: `SharedContext` uses `threading.Lock` (line 151) and is documented as "thread-safe using threading.Lock for cross-thread protection" (line 147), but it's used with `_run_async()` which creates new event loops in threads.
- **Risk level**: MEDIUM
- **Why it's a problem**:
  - The lock protects cache consistency, but `_run_async()` (lines 31-50) spawns threads with `ThreadPoolExecutor`
  - When ThreadPoolExecutor threads try to acquire the same threading.Lock while async coroutines hold it, deadlock risk exists
  - The docstring claims cross-thread safety but doesn't account for async code spawning threads
- **Suggested fix**: Document the exact threading model or switch to thread-safe data structures that don't require explicit locking.

---

### Finding 6: ASYNC LOCK WITHOUT TIMEOUT (LOW RISK)

- **File:Line**: `scripts/agentica/embedding_service.py:488-542`
- **Pattern detected**: `self._cache_lock = asyncio.Lock()` is used without timeout in `embed()` method.
- **Risk level**: LOW
- **Why it's a problem**:
  - While not a deadlock by itself, if the coroutine holding the lock crashes or hangs, all other tasks waiting on the lock will hang indefinitely
  - No timeout or context manager cleanup if exception occurs during lock hold
- **Suggested fix**: Consider adding optional timeout to lock acquisition or document the assumption that locked sections complete quickly.

---

## Recommended Priority Order

1. **CRITICAL**: Fix Finding 1 & 2 - threading locks in async contexts (can cause complete application freeze)
2. **HIGH**: Fix Finding 3 - race condition in reference assignment
3. **MEDIUM**: Fix Finding 4 & 5 - event loop binding and threading safety
4. **LOW**: Fix Finding 6 - add defensive timeout

## Root Cause

The root cause is mixing `threading.Lock` (synchronous) with `asyncio.Lock` (asynchronous) in the same operations. The span processor needs complete conversion to async-native locking.
