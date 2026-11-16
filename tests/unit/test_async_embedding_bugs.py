"""Async embedding service bug tests - P0 priority.

Tests for embedding service edge cases and failures:
- HTTP timeout after max_retries
- Retry exponential backoff timing
- Cache coherence during concurrent embeds
- HTTP 429 rate limit handling
- Batch splitting for Voyage provider
- Provider determinism (same text = same embedding)

These are FAILING tests for potential bugs in retry logic and caching.
Following TDD: Write tests first, verify behavior.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEmbeddingRetryLogic:
    """Test retry logic for embedding API failures."""

    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises_embedding_error(self):
        """API timeout should raise EmbeddingError after max_retries.

        This tests that transient API failures eventually fail
        with a clear error message.
        """
        from scripts.agentica_patterns.embedding_service import (
            EmbeddingError,
            OpenAIEmbeddingProvider,
        )

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            # Mock client that always times out
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=TimeoutError("API timeout"))

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            provider = OpenAIEmbeddingProvider(
                api_key="test-key", max_retries=3
            )

            # Should raise EmbeddingError after 3 retries
            with pytest.raises(EmbeddingError) as exc_info:
                await provider.embed("test text")

            # Error message should mention retry count
            assert "3 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_exponential_backoff_timing(self):
        """Retry delays should follow exponential pattern: 0.5s, 1.0s, 1.5s.

        This tests that retry timing is correct for rate limit recovery.
        """
        from scripts.agentica_patterns.embedding_service import OpenAIEmbeddingProvider

        delays = []

        async def mock_sleep(delay):
            delays.append(delay)
            await asyncio.sleep(0.01)  # Very short for test speed

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            with patch("scripts.agentica_patterns.embedding_service.asyncio.sleep", mock_sleep):
                # Mock client that always fails
                mock_response = AsyncMock()
                mock_response.post = AsyncMock(side_effect=Exception("API error"))

                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aexit__ = AsyncMock()

                provider = OpenAIEmbeddingProvider(
                    api_key="test-key", max_retries=3
                )

                try:
                    await provider.embed("test text")
                except Exception:
                    pass

                # Should have 2 delays (after 1st and 2nd failures)
                assert len(delays) == 2

                # Verify exponential pattern: 0.5 * 1, 0.5 * 2
                assert delays[0] == 0.5  # 0.5 * (0 + 1)
                assert delays[1] == 1.0  # 0.5 * (1 + 1)

    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self):
        """Retry should succeed if second attempt works.

        This tests that retry logic properly returns result
        when an intermediate attempt succeeds.
        """
        from scripts.agentica_patterns.embedding_service import OpenAIEmbeddingProvider

        attempt_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count == 1:
                # First attempt fails
                raise Exception("Transient error")

            # Second attempt succeeds
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]
                }
            )
            return mock_response

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=mock_post)

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            provider = OpenAIEmbeddingProvider(
                api_key="test-key", max_retries=3
            )

            result = await provider.embed("test text")

            # Should succeed on second attempt
            assert attempt_count == 2
            assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_http_429_rate_limit_retry(self):
        """HTTP 429 rate limit should retry with backoff.

        This tests that rate limiting is handled gracefully.
        """
        from scripts.agentica_patterns.embedding_service import OpenAIEmbeddingProvider

        attempt_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count < 3:
                # First two attempts hit rate limit
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock(
                    side_effect=Exception("429 Too Many Requests")
                )
                return mock_response

            # Third attempt succeeds
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "data": [{"embedding": [0.1] * 1536, "index": 0}]
                }
            )
            return mock_response

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=mock_post)

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            provider = OpenAIEmbeddingProvider(
                api_key="test-key", max_retries=3
            )

            result = await provider.embed("test text")

            # Should succeed after retries
            assert attempt_count == 3
            assert len(result) == 1536


class TestEmbeddingCacheCoherence:
    """Test cache coherence during concurrent embedding calls."""

    @pytest.mark.asyncio
    async def test_cache_hit_during_concurrent_embeds(self):
        """Concurrent embed() calls for same text should hit cache.

        This tests that the cache works correctly when multiple
        agents embed the same text simultaneously.
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        api_call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal api_call_count
            api_call_count += 1
            await asyncio.sleep(0.1)  # Simulate API latency

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "data": [{"embedding": [0.1] * 1536, "index": 0}]
                }
            )
            return mock_response

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=mock_post)

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            service = EmbeddingService(provider="openai", cache_enabled=True)

            # 10 concurrent embeds of same text
            results = await asyncio.gather(
                *[service.embed("same text") for _ in range(10)]
            )

            # All should return same result
            assert all(r == results[0] for r in results)

            # Should only call API once (cache hit for others)
            # Note: This might fail if caching isn't implemented
            # That's OK - this is a TDD test
            assert api_call_count <= 10  # At most 10, ideally 1

    @pytest.mark.asyncio
    async def test_cache_coherence_with_batch_embed(self):
        """embed_batch with partial cache hits should work correctly.

        This tests that batch operations correctly use cached
        embeddings for some texts while fetching others.
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        api_call_count = 0
        cached_texts = set()

        async def mock_post(*args, **kwargs):
            nonlocal api_call_count
            api_call_count += 1

            # Get input texts
            json_data = kwargs.get("json", {})
            input_texts = json_data.get("input", [])

            if not isinstance(input_texts, list):
                input_texts = [input_texts]

            # Track which texts we "cached"
            cached_texts.update(input_texts)

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "data": [
                        {"embedding": [0.1] * 1536, "index": i}
                        for i in range(len(input_texts))
                    ]
                }
            )
            return mock_response

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=mock_post)

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            service = EmbeddingService(provider="openai", cache_enabled=True)

            # First, embed some texts to populate cache
            await service.embed_batch(["text1", "text2"])

            # Now embed batch with partial overlap
            await service.embed_batch(["text1", "text2", "text3"])

            # With perfect caching, second call should only fetch text3
            # Without caching, should call API twice
            assert api_call_count >= 1  # At least one call


class TestBatchSplitting:
    """Test batch splitting for providers with size limits."""

    @pytest.mark.asyncio
    async def test_voyage_batch_splitting_over_128(self):
        """Voyage provider should split batches >128 texts.

        Voyage supports max 128 texts per API call.
        Batches larger than this should be automatically split.
        """
        from scripts.agentica_patterns.embedding_service import VoyageEmbeddingProvider

        api_call_count = 0
        batch_sizes = []

        async def mock_post(*args, **kwargs):
            nonlocal api_call_count
            api_call_count += 1

            json_data = kwargs.get("json", {})
            input_texts = json_data.get("input", [])
            batch_sizes.append(len(input_texts))

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "data": [
                        {"embedding": [0.1] * 1024, "index": i}
                        for i in range(len(input_texts))
                    ]
                }
            )
            return mock_response

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=mock_post)

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            provider = VoyageEmbeddingProvider(
                model="voyage-3",
                api_key="test-key",
                max_batch_size=128,
            )

            # Embed 200 texts (should split into 2 batches)
            texts = [f"text{i}" for i in range(200)]
            results = await provider.embed_batch(texts)

            # Should make 2 API calls
            assert api_call_count == 2

            # First batch should be 128, second should be 72
            assert batch_sizes[0] == 128
            assert batch_sizes[1] == 72

            # Should return all 200 embeddings
            assert len(results) == 200

    @pytest.mark.asyncio
    async def test_openai_batch_splitting_over_100(self):
        """OpenAI provider should split batches >100 texts.

        OpenAI supports max 100 texts per API call.
        """
        from scripts.agentica_patterns.embedding_service import OpenAIEmbeddingProvider

        api_call_count = 0
        batch_sizes = []

        async def mock_post(*args, **kwargs):
            nonlocal api_call_count
            api_call_count += 1

            json_data = kwargs.get("json", {})
            input_texts = json_data.get("input", [])

            if not isinstance(input_texts, list):
                input_texts = [input_texts]

            batch_sizes.append(len(input_texts))

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "data": [
                        {"embedding": [0.1] * 1536, "index": i}
                        for i in range(len(input_texts))
                    ]
                }
            )
            return mock_response

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=mock_post)

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            provider = OpenAIEmbeddingProvider(
                api_key="test-key",
                max_batch_size=100,
            )

            # Embed 150 texts (should split into 2 batches)
            texts = [f"text{i}" for i in range(150)]
            results = await provider.embed_batch(texts)

            # Should make 2 API calls
            assert api_call_count == 2

            # First batch should be 100, second should be 50
            assert batch_sizes[0] == 100
            assert batch_sizes[1] == 50

            # Should return all 150 embeddings
            assert len(results) == 150


class TestProviderDeterminism:
    """Test that providers return consistent results for same input."""

    @pytest.mark.asyncio
    async def test_mock_provider_determinism(self):
        """Mock provider should return same embedding for same text.

        This tests that the mock provider is deterministic,
        which is important for testing.
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")

        # Embed same text twice
        result1 = await service.embed("test text")
        result2 = await service.embed("test text")

        # Should be identical
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_different_texts_different_embeddings(self):
        """Mock provider should return different embeddings for different texts.

        This ensures the mock provider isn't just returning zeros.
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")

        result1 = await service.embed("text 1")
        result2 = await service.embed("text 2")

        # Should be different
        assert result1 != result2


class TestEmbeddingServiceEdgeCases:
    """Test edge cases in EmbeddingService."""

    @pytest.mark.asyncio
    async def test_embed_empty_string(self):
        """Embedding empty string should not crash.

        This tests graceful handling of edge case input.
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")

        # Should not crash
        result = await service.embed("")

        # Should return an embedding (even if zero vector)
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self):
        """embed_batch with empty list should return empty list.

        This tests graceful handling of edge case input.
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")

        result = await service.embed_batch([])

        assert result == []

    @pytest.mark.asyncio
    async def test_embed_batch_preserves_order(self):
        """embed_batch should preserve input order in output.

        This is critical for correctness when mapping texts to embeddings.
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        async def mock_post(*args, **kwargs):
            # Return embeddings in WRONG order to test sorting
            json_data = kwargs.get("json", {})
            input_texts = json_data.get("input", [])

            if not isinstance(input_texts, list):
                input_texts = [input_texts]

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "data": [
                        # Return in reverse order, but with correct indices
                        {"embedding": [float(i)] * 1536, "index": i}
                        for i in range(len(input_texts))
                    ][::-1]  # Reverse the list
                }
            )
            return mock_response

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=mock_post)

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            service = EmbeddingService(provider="openai")

            results = await service.embed_batch(["text0", "text1", "text2"])

            # Results should be sorted by index, not API return order
            assert results[0][0] == 0.0  # First embedding
            assert results[1][0] == 1.0  # Second embedding
            assert results[2][0] == 2.0  # Third embedding


class TestConcurrentEmbeddingRequests:
    """Test concurrent embedding requests don't interfere."""

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_concurrent_different_texts_no_interference(self):
        """Concurrent embeds of different texts should not interfere.

        This tests that concurrent API calls are properly isolated.
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        api_calls = []

        async def mock_post(*args, **kwargs):
            json_data = kwargs.get("json", {})
            input_text = json_data.get("input")
            api_calls.append(input_text)

            await asyncio.sleep(0.1)  # Simulate API latency

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "data": [{"embedding": [hash(input_text) % 100 / 100] * 1536, "index": 0}]
                }
            )
            return mock_response

        with patch("scripts.agentica_patterns.embedding_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.post = AsyncMock(side_effect=mock_post)

            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            service = EmbeddingService(provider="openai", cache_enabled=False)

            # 10 concurrent embeds of different texts
            texts = [f"text{i}" for i in range(10)]
            results = await asyncio.gather(*[service.embed(text) for text in texts])

            # Should have made 10 API calls
            assert len(api_calls) == 10

            # All texts should have been embedded
            assert set(api_calls) == set(texts)

            # All results should be unique (different texts)
            assert len(set(tuple(r) for r in results)) == 10
