# TDD Tests: httpx.AsyncClient Reuse

## Test File
`/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_embedding_client_reuse.py`

## Issue Reference
Finding 2 in `docs/concurrency-search/EXHAUSTION_FINDINGS.md`

## Source Code Locations
- `scripts/agentica/embedding_service.py:160` - OpenAI provider creates new client per request
- `scripts/agentica/embedding_service.py:266` - Voyage provider creates new client per request

## Test Summary

### TestAsyncClientReuse (3 tests)

| Test | Verifies | Current Failure |
|------|----------|-----------------|
| `test_openai_client_reused_across_embed_calls` | Single AsyncClient reused for 5 embed() calls | Creates 5 clients instead of 1 |
| `test_voyage_client_reused_across_embed_calls` | Voyage provider also reuses client | Creates 5 clients instead of 1 |
| `test_client_reused_across_batch_calls` | Client reused for batch operations | Creates 3 clients for 3 batches |

### TestAsyncClientLifecycle (4 tests)

| Test | Verifies | Current Failure |
|------|----------|-----------------|
| `test_openai_provider_has_close_method` | Provider has close()/aclose() | No close method exists |
| `test_voyage_provider_has_close_method` | Voyage has close method | No close method exists |
| `test_embedding_service_has_close_method` | Service wrapper exposes close | No close method exists |
| `test_provider_supports_async_context_manager` | Provider supports `async with` | Missing `__aenter__`/`__aexit__` |

### TestConnectionPoolExhaustion (2 tests)

| Test | Verifies | Current Failure |
|------|----------|-----------------|
| `test_no_exhaustion_after_100_rapid_calls` | 100 calls use 1 client | Creates 100 clients |
| `test_concurrent_calls_share_client` | Concurrent gather() shares client | Creates 10 clients for 10 concurrent calls |

### TestClientConfiguration (2 tests)

| Test | Verifies | Current Failure |
|------|----------|-----------------|
| `test_client_has_reasonable_timeout` | Persistent client has `_client` attr | No `_client` attribute exists |
| `test_client_persists_across_retries` | Same client for retry attempts | Creates 3 clients for 3 retries |

## Current Failure Output

```
FAILED tests/unit/test_embedding_client_reuse.py::TestAsyncClientReuse::test_openai_client_reused_across_embed_calls
  AssertionError: Expected 1 AsyncClient instance (reused), but got 5.
  The implementation creates a new client per request, leaking connections.

FAILED tests/unit/test_embedding_client_reuse.py::TestAsyncClientLifecycle::test_openai_provider_has_close_method
  AssertionError: Provider should have a close() or aclose() method
  to properly shut down the persistent client.

FAILED tests/unit/test_embedding_client_reuse.py::TestConnectionPoolExhaustion::test_no_exhaustion_after_100_rapid_calls
  AssertionError: Created 100 clients for 100 calls.
  This will exhaust connection pools. Should reuse 1 client.

FAILED tests/unit/test_embedding_client_reuse.py::TestClientConfiguration::test_client_persists_across_retries
  AssertionError: Created 3 clients for 3 retry attempts.
  Retries should reuse the same client.
```

## Implementation Required to Pass

### 1. Create persistent client in `__init__`

```python
class OpenAIEmbeddingProvider:
    def __init__(self, ...):
        # ... existing code ...
        self._client = httpx.AsyncClient(timeout=30.0)
```

### 2. Use persistent client in `_call_api`

```python
async def _call_api(self, texts: list[str]) -> list[list[float]]:
    for attempt in range(self.max_retries):
        try:
            # Use self._client instead of creating new one
            response = await self._client.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.MODEL, "input": texts},
            )
            response.raise_for_status()
            # ... rest of handling
        except Exception as e:
            # ... retry logic
```

### 3. Add cleanup methods

```python
class OpenAIEmbeddingProvider:
    async def aclose(self) -> None:
        """Close the persistent HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "OpenAIEmbeddingProvider":
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()
```

### 4. Apply same changes to VoyageEmbeddingProvider

Same pattern: persistent `_client`, reuse in `_call_api`, add `aclose()` and context manager.

### 5. Update EmbeddingService wrapper

```python
class EmbeddingService:
    async def aclose(self) -> None:
        """Close the underlying provider's client."""
        if hasattr(self._provider, "aclose"):
            await self._provider.aclose()
```

## Run Tests

```bash
uv run pytest tests/unit/test_embedding_client_reuse.py -v
```

## QLTY Notes

12 bandit B101 warnings about `assert` in tests - these are expected and acceptable for pytest test files.
