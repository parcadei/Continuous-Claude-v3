# Jury Review: httpx Client Reuse

## Verdict: APPROVE

### Correctness: APPROVE
- **Evidence**:
  - Single client created in `__init__`: Line 104 (`self._client = httpx.AsyncClient(timeout=30.0)`) for OpenAI, Line 251 for Voyage
  - Client reused in `_call_api`: Lines 173-180 use `self._client.post()` directly instead of `async with httpx.AsyncClient()`
  - Proper cleanup via `aclose()`: Lines 106-108 (OpenAI) and 253-255 (Voyage)
  - Test `test_no_exhaustion_after_100_rapid_calls` confirms 100 calls use exactly 1 client
  - Test `test_client_persists_across_retries` confirms retries reuse the same client

### Completeness: APPROVE
- **Evidence**:
  - **OpenAIEmbeddingProvider**: Fixed with persistent `_client` (line 104), `aclose()` method (lines 106-108), and async context manager (lines 110-116)
  - **VoyageEmbeddingProvider**: Fixed with same pattern - `_client` (line 251), `aclose()` (lines 253-255), async context manager (lines 257-263)
  - **EmbeddingService**: Updated with `aclose()` that delegates to provider (lines 632-635), and async context manager (lines 637-643)
  - All three classes implement the fix consistently

### Quality: APPROVE
- **Evidence**:
  - All 11 tests pass (verified via `pytest tests/unit/test_embedding_client_reuse.py -v`)
  - QLTY has only 1 pre-existing warning (`S1845`: naming conflict between `dimension` property and `DIMENSION` constant) - explicitly noted as not introduced by this change
  - Async context manager support enables clean resource management: `async with OpenAIEmbeddingProvider() as provider:`
  - Tests are comprehensive covering:
    - Client reuse (3 tests)
    - Lifecycle methods (4 tests)
    - Connection pool exhaustion (2 tests)
    - Client configuration (2 tests)
  - Implementation matches the suggested fix from Finding 2 in EXHAUSTION_FINDINGS.md

## Issues Found
- None blocking. The `S1845` QLTY warning is pre-existing and not related to this change.

## Recommendation
- **Ship it**. The implementation correctly addresses the HIGH-risk Finding 2 from the exhaustion audit.
- Before: 100 embed calls created 100 `httpx.AsyncClient` instances (connection pool exhaustion)
- After: 100 embed calls reuse 1 persistent `httpx.AsyncClient` instance (no exhaustion)
- The fix is well-tested, follows async context manager best practices, and maintains backward compatibility.
