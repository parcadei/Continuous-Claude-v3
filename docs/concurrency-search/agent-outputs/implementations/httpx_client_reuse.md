# Implementation: httpx.AsyncClient Reuse

## Issue Reference
Finding 2 in `docs/concurrency-search/EXHAUSTION_FINDINGS.md`

## Problem
The `OpenAIEmbeddingProvider` and `VoyageEmbeddingProvider` classes created a new `httpx.AsyncClient` instance for every API call. This caused:
- Connection pool exhaustion under load
- Resource leaks (unclosed connections)
- No ability to properly clean up resources

## Files Modified

### 1. `scripts/agentica/embedding_service.py`

**Changes to `OpenAIEmbeddingProvider`:**
- Added persistent `self._client = httpx.AsyncClient(timeout=30.0)` in `__init__`
- Updated `_call_api` to use `self._client` directly instead of `async with httpx.AsyncClient()`
- Added `async def aclose(self)` method to close the client
- Added `__aenter__` and `__aexit__` for async context manager support

**Changes to `VoyageEmbeddingProvider`:**
- Same pattern: persistent client, direct usage, cleanup methods

**Changes to `EmbeddingService`:**
- Added `async def aclose(self)` that delegates to provider's `aclose()` if available
- Added `__aenter__` and `__aexit__` for async context manager support

### 2. `tests/unit/test_embedding_client_reuse.py`

Updated tests to mock the persistent client pattern correctly:
- Changed `MockAsyncClient` to provide `post` method directly (instead of via `__aenter__`)
- Added `aclose` mock method for cleanup verification

## Code Changes

### Before (created new client per request):
```python
async def _call_api(self, texts: list[str]) -> list[list[float]]:
    for attempt in range(self.max_retries):
        try:
            async with httpx.AsyncClient() as client:  # NEW client per call
                response = await client.post(...)
```

### After (reuses persistent client):
```python
def __init__(self, ...):
    self._client = httpx.AsyncClient(timeout=30.0)

async def _call_api(self, texts: list[str]) -> list[list[float]]:
    for attempt in range(self.max_retries):
        try:
            response = await self._client.post(...)  # REUSE persistent client

async def aclose(self) -> None:
    await self._client.aclose()

async def __aenter__(self) -> OpenAIEmbeddingProvider:
    return self

async def __aexit__(self, *args) -> None:
    await self.aclose()
```

## Test Results

```
tests/unit/test_embedding_client_reuse.py - 11 passed

TestAsyncClientReuse:
  - test_openai_client_reused_across_embed_calls PASSED
  - test_voyage_client_reused_across_embed_calls PASSED
  - test_client_reused_across_batch_calls PASSED

TestAsyncClientLifecycle:
  - test_openai_provider_has_close_method PASSED
  - test_voyage_provider_has_close_method PASSED
  - test_embedding_service_has_close_method PASSED
  - test_provider_supports_async_context_manager PASSED

TestConnectionPoolExhaustion:
  - test_no_exhaustion_after_100_rapid_calls PASSED
  - test_concurrent_calls_share_client PASSED

TestClientConfiguration:
  - test_client_has_reasonable_timeout PASSED
  - test_client_persists_across_retries PASSED
```

## QLTY Check Results

After fixes:
- Fixed 3 ruff:UP037 warnings (removed quotes from type annotations)
- 1 remaining warning: `radarlint-python:python:S1845` - pre-existing naming conflict between `dimension` property and `DIMENSION` constant (not introduced by this change)

## Usage

Providers now support async context manager for automatic cleanup:

```python
# With async context manager (recommended)
async with OpenAIEmbeddingProvider() as provider:
    embedding = await provider.embed("text")
# Client automatically closed on exit

# Manual lifecycle management
provider = OpenAIEmbeddingProvider()
try:
    embedding = await provider.embed("text")
finally:
    await provider.aclose()
```

## Impact

- **Before**: 100 embed calls created 100 `httpx.AsyncClient` instances
- **After**: 100 embed calls reuse 1 persistent `httpx.AsyncClient` instance
- Connection pool exhaustion eliminated
- Resources properly cleaned up via `aclose()` or context manager
