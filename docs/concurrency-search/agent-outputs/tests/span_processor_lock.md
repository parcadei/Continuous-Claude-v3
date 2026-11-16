# SpanProcessingContext Async Lock Tests

## Test File

**Path**: `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_span_processor_async_lock.py`

## Test Summary

| Test Name | What It Verifies | Status |
|-----------|------------------|--------|
| `test_uses_asyncio_lock_not_threading_lock` | `SpanProcessingContext._lock` is `asyncio.Lock`, not `threading.Lock` | FAILED |
| `test_add_summary_is_async` | `add_summary()` is an async method (coroutine function) | FAILED |
| `test_get_reference_context_is_async` | `get_reference_context()` is an async method | FAILED |
| `test_all_summaries_is_async` | `all_summaries()` is an async method | FAILED |
| `test_add_summary_awaitable` | `add_summary()` returns a coroutine that can be awaited | FAILED |
| `test_concurrent_add_summary_no_deadlock` | Concurrent `add_summary()` calls complete without deadlock | FAILED |
| `test_concurrent_get_reference_context_no_deadlock` | Concurrent `get_reference_context()` calls complete | PASSED |
| `test_extract_summaries_uses_async_context_methods` | `extract_summaries()` properly awaits async context methods | PASSED |
| `test_extract_decisions_no_mixed_lock_deadlock` | `get_reference_context()` is async to prevent mixed-lock deadlock | FAILED |

**Result**: 7 FAILED, 2 PASSED

## Current Failure Output

```
FAILED tests/unit/test_span_processor_async_lock.py::TestSpanProcessingContextAsyncLock::test_uses_asyncio_lock_not_threading_lock
  AssertionError: SpanProcessingContext._lock should not be threading.Lock

FAILED tests/unit/test_span_processor_async_lock.py::TestSpanProcessingContextAsyncLock::test_add_summary_is_async
  AssertionError: add_summary must be an async method (coroutine function)

FAILED tests/unit/test_span_processor_async_lock.py::TestSpanProcessingContextAsyncLock::test_get_reference_context_is_async
  AssertionError: get_reference_context must be an async method (coroutine function)

FAILED tests/unit/test_span_processor_async_lock.py::TestSpanProcessingContextAsyncLock::test_all_summaries_is_async
  AssertionError: all_summaries must be an async method (coroutine function)

FAILED tests/unit/test_span_processor_async_lock.py::TestSpanProcessingContextAsyncBehavior::test_add_summary_awaitable
  AssertionError: add_summary must return a coroutine

FAILED tests/unit/test_span_processor_async_lock.py::TestSpanProcessingContextAsyncBehavior::test_concurrent_add_summary_no_deadlock
  TypeError: object NoneType can't be used in 'await' expression

FAILED tests/unit/test_span_processor_async_lock.py::TestExtractDecisionsAsyncLock::test_extract_decisions_no_mixed_lock_deadlock
  AssertionError: get_reference_context must be async to prevent mixed-lock deadlock
```

## Implementation Needed

To make all tests pass, the following changes are required in `scripts/agentica/span_processor.py`:

### 1. Change Lock Type (line 141)

**Before:**
```python
_lock: threading.Lock = field(default_factory=threading.Lock)
```

**After:**
```python
_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
```

### 2. Convert `add_summary()` to Async (lines 143-155)

**Before:**
```python
def add_summary(self, summary: SpanSummary) -> None:
    with self._lock:
        self.span_summaries[summary.span_id] = summary
        # ...
```

**After:**
```python
async def add_summary(self, summary: SpanSummary) -> None:
    async with self._lock:
        self.span_summaries[summary.span_id] = summary
        # ...
```

### 3. Convert `get_reference_context()` to Async (lines 157-173)

**Before:**
```python
def get_reference_context(self, span_id: str) -> str:
    with self._lock:
        # ...
```

**After:**
```python
async def get_reference_context(self, span_id: str) -> str:
    async with self._lock:
        # ...
```

### 4. Convert `all_summaries()` to Async (lines 175-182)

**Before:**
```python
def all_summaries(self) -> list[SpanSummary]:
    with self._lock:
        return list(self.span_summaries.values())
```

**After:**
```python
async def all_summaries(self) -> list[SpanSummary]:
    async with self._lock:
        return list(self.span_summaries.values())
```

### 5. Update Callers in `extract_summaries()` (line 635)

**Before:**
```python
context.add_summary(summary)
```

**After:**
```python
await context.add_summary(summary)
```

### 6. Update Callers in `extract_decisions()` (line 707)

**Before:**
```python
ref_context = context.get_reference_context(span_id)
```

**After:**
```python
ref_context = await context.get_reference_context(span_id)
```

### 7. Update Callers in `embed_and_persist_summaries()` (line 794)

**Before:**
```python
summaries = context.all_summaries()
```

**After:**
```python
summaries = await context.all_summaries()
```

## Issue Reference

This addresses **Finding 1** and **Finding 2** from `docs/concurrency-search/DEADLOCK_FINDINGS.md`:
- Finding 1: THREADING LOCK IN ASYNC CONTEXT (HIGHEST RISK)
- Finding 2: MIXED LOCK TYPES IN SAME OPERATION (HIGH RISK)

## Run Command

```bash
uv run pytest tests/unit/test_span_processor_async_lock.py -v
```
