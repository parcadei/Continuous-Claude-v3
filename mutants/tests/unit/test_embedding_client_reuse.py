"""Tests for httpx.AsyncClient reuse in EmbeddingService.

TDD tests that verify:
1. A single AsyncClient is reused across multiple embed() calls
2. The client is properly closed on service shutdown
3. Connection pool is not exhausted after rapid calls

These tests verify the implementation creates a persistent client in __init__
and reuses it across all API calls (see Finding 2 in EXHAUSTION_FINDINGS.md).

Issue location: scripts/agentica/embedding_service.py lines 160, 266
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

HTTPX_PATCH_PATH = "scripts.agentica.embedding_service.httpx.AsyncClient"


class TestAsyncClientReuse:
    """Verify that a single httpx.AsyncClient is reused across calls."""

    @pytest.fixture
    def mock_response(self):
        """Mock successful API response."""
        response = MagicMock()
        response.json.return_value = {"data": [{"embedding": [0.1] * 1536}]}
        response.raise_for_status = MagicMock()
        return response

    @pytest.mark.asyncio
    async def test_openai_client_reused_across_embed_calls(self, mock_response):
        """A single AsyncClient should be reused for multiple embed() calls.

        Expected behavior: Reuses same client instance (PASS)
        """
        from scripts.agentica.embedding_service import OpenAIEmbeddingProvider

        client_init_count = 0

        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                nonlocal client_init_count
                client_init_count += 1
                # Persistent client needs post method directly
                self.post = AsyncMock(return_value=mock_response)

            async def aclose(self):
                pass  # Mock cleanup

        with (
            patch(HTTPX_PATCH_PATH, MockAsyncClient),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
        ):
            provider = OpenAIEmbeddingProvider()

            # Make 5 embed calls
            for _ in range(5):
                await provider.embed("Text")

        # Should be 1 (client reused)
        assert client_init_count == 1, (
            f"Expected 1 AsyncClient instance (reused), but got {client_init_count}. "
            "The implementation creates a new client per request, leaking connections."
        )

    @pytest.mark.asyncio
    async def test_voyage_client_reused_across_embed_calls(self, mock_response):
        """Voyage provider should also reuse a single AsyncClient.

        Expected behavior: Reuses same client instance (PASS)
        """
        from scripts.agentica.embedding_service import VoyageEmbeddingProvider

        client_init_count = 0

        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                nonlocal client_init_count
                client_init_count += 1
                # Persistent client needs post method directly
                self.post = AsyncMock(return_value=mock_response)

            async def aclose(self):
                pass  # Mock cleanup

        with (
            patch(HTTPX_PATCH_PATH, MockAsyncClient),
            patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}),
        ):
            provider = VoyageEmbeddingProvider(model="voyage-3")

            # Make 5 embed calls
            for _ in range(5):
                await provider.embed("Text")

        assert client_init_count == 1, (
            f"Expected 1 AsyncClient instance (reused), but got {client_init_count}. "
            "Voyage provider also leaks connections."
        )

    @pytest.mark.asyncio
    async def test_client_reused_across_batch_calls(self, mock_response):
        """Client should be reused across batch_embed calls too.

        Expected behavior: Reuses same client instance (PASS)
        """
        from scripts.agentica.embedding_service import OpenAIEmbeddingProvider

        client_init_count = 0

        # Mock batch response
        batch_response = MagicMock()
        batch_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 1536, "index": i} for i in range(10)
            ]
        }
        batch_response.raise_for_status = MagicMock()

        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                nonlocal client_init_count
                client_init_count += 1
                # Persistent client needs post method directly
                self.post = AsyncMock(return_value=batch_response)

            async def aclose(self):
                pass  # Mock cleanup

        with (
            patch(HTTPX_PATCH_PATH, MockAsyncClient),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
        ):
            provider = OpenAIEmbeddingProvider(max_batch_size=10)

            # Make 3 batch calls
            for _ in range(3):
                await provider.embed_batch([f"Text {j}" for j in range(10)])

        assert client_init_count == 1, (
            f"Expected 1 AsyncClient for all batch calls, but got {client_init_count}"
        )


class TestAsyncClientLifecycle:
    """Verify proper client lifecycle management."""

    @pytest.mark.asyncio
    async def test_openai_provider_has_close_method(self):
        """Provider should have an explicit close() method for cleanup.

        Current behavior: No close() method exists (FAIL)
        Expected behavior: close() method properly closes the client (PASS)
        """
        from scripts.agentica.embedding_service import OpenAIEmbeddingProvider

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIEmbeddingProvider()

        # Provider should have a close() or aclose() method
        has_close = hasattr(provider, "close") or hasattr(provider, "aclose")
        assert has_close, (
            "Provider should have a close() or aclose() method "
            "to properly shut down the persistent client."
        )

    @pytest.mark.asyncio
    async def test_voyage_provider_has_close_method(self):
        """Voyage provider should also have close() method.

        Current behavior: No close() method exists (FAIL)
        Expected behavior: close() method properly closes the client (PASS)
        """
        from scripts.agentica.embedding_service import VoyageEmbeddingProvider

        with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
            provider = VoyageEmbeddingProvider(model="voyage-3")

        has_close = hasattr(provider, "close") or hasattr(provider, "aclose")
        assert has_close, (
            "Voyage provider should have a close() or aclose() method."
        )

    @pytest.mark.asyncio
    async def test_embedding_service_has_close_method(self):
        """EmbeddingService wrapper should expose close() method.

        Current behavior: No close() method exists (FAIL)
        Expected behavior: close() delegates to provider's close() (PASS)
        """
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")

        has_close = hasattr(service, "close") or hasattr(service, "aclose")
        assert has_close, (
            "EmbeddingService should have a close() or aclose() method "
            "to properly shut down the underlying provider's client."
        )

    @pytest.mark.asyncio
    async def test_provider_supports_async_context_manager(self):
        """Provider should support async context manager protocol.

        Expected: async with provider: ... for automatic cleanup
        """
        from scripts.agentica.embedding_service import OpenAIEmbeddingProvider

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIEmbeddingProvider()

        has_aenter = hasattr(provider, "__aenter__")
        has_aexit = hasattr(provider, "__aexit__")

        assert has_aenter and has_aexit, (
            "Provider should support async context manager protocol "
            "for automatic resource cleanup: async with Provider() as p: ..."
        )


class TestConnectionPoolExhaustion:
    """Verify connection pool is not exhausted under load."""

    @pytest.fixture
    def mock_response(self):
        """Mock successful API response."""
        response = MagicMock()
        response.json.return_value = {"data": [{"embedding": [0.1] * 1536}]}
        response.raise_for_status = MagicMock()
        return response

    @pytest.mark.asyncio
    async def test_no_exhaustion_after_100_rapid_calls(self, mock_response):
        """100 rapid embed() calls should not exhaust connection pool.

        Expected behavior: Reuses 1 client, no exhaustion (PASS)
        """
        from scripts.agentica.embedding_service import OpenAIEmbeddingProvider

        client_init_count = 0
        max_concurrent_clients = 0

        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                nonlocal client_init_count, max_concurrent_clients
                client_init_count += 1
                max_concurrent_clients = max(max_concurrent_clients, client_init_count)
                # Persistent client needs post method directly
                self.post = AsyncMock(return_value=mock_response)

            async def aclose(self):
                pass  # Mock cleanup

        with (
            patch(HTTPX_PATCH_PATH, MockAsyncClient),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
        ):
            provider = OpenAIEmbeddingProvider()

            # Make 100 rapid sequential calls
            for i in range(100):
                await provider.embed(f"Text {i}")

        # With client reuse, should create exactly 1 client
        assert client_init_count == 1, (
            f"Created {client_init_count} clients for 100 calls. "
            "This will exhaust connection pools. Should reuse 1 client."
        )

        # Maximum concurrent clients should be 1
        assert max_concurrent_clients == 1, (
            f"Max concurrent clients was {max_concurrent_clients}. "
            "With proper reuse, only 1 client should exist at a time."
        )

    @pytest.mark.asyncio
    async def test_concurrent_calls_share_client(self, mock_response):
        """Concurrent embed() calls should share the same client.

        This tests that even with asyncio.gather, the same client is used.
        """
        import asyncio

        from scripts.agentica.embedding_service import OpenAIEmbeddingProvider

        client_init_count = 0

        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                nonlocal client_init_count
                client_init_count += 1
                # Persistent client needs post method directly
                self.post = AsyncMock(return_value=mock_response)

            async def aclose(self):
                pass  # Mock cleanup

        with (
            patch(HTTPX_PATCH_PATH, MockAsyncClient),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
        ):
            provider = OpenAIEmbeddingProvider()

            # Make 10 concurrent calls
            await asyncio.gather(*[
                provider.embed(f"Text {i}") for i in range(10)
            ])

        # Even concurrent calls should share 1 client
        assert client_init_count == 1, (
            f"Created {client_init_count} clients for 10 concurrent calls. "
            "Concurrent calls should share the same client."
        )


class TestClientConfiguration:
    """Verify client is configured correctly when reused."""

    @pytest.mark.asyncio
    async def test_client_has_reasonable_timeout(self):
        """Persistent client should have reasonable default timeout.

        Expected: timeout >= 30s for embedding API calls
        """
        from scripts.agentica.embedding_service import OpenAIEmbeddingProvider

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIEmbeddingProvider()

        # Check if provider has a _client attribute (after fix)
        if hasattr(provider, "_client"):
            client = provider._client
            # httpx.AsyncClient has a timeout property
            assert client.timeout.connect is not None or client.timeout.read is not None
        else:
            # Before fix: no persistent client exists
            pytest.fail(
                "Provider does not have a persistent _client attribute. "
                "Implement client reuse by creating self._client in __init__."
            )

    @pytest.mark.asyncio
    async def test_client_persists_across_retries(self):
        """Same client should be used across retry attempts.

        Expected behavior: Same client reused for retries (PASS)
        """
        from scripts.agentica.embedding_service import (
            EmbeddingError,
            OpenAIEmbeddingProvider,
        )

        client_init_count = 0
        call_count = 0

        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                nonlocal client_init_count
                client_init_count += 1

                async def mock_post(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    # Return a response that fails on raise_for_status
                    error_response = MagicMock()
                    error_response.raise_for_status.side_effect = Exception("API error")
                    return error_response

                self.post = mock_post

            async def aclose(self):
                pass  # Mock cleanup

        with (
            patch(HTTPX_PATCH_PATH, MockAsyncClient),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
        ):
            provider = OpenAIEmbeddingProvider(max_retries=3)

            with pytest.raises(EmbeddingError):
                await provider.embed("Test")

        # 3 retries should use 1 client, not 3
        assert client_init_count == 1, (
            f"Created {client_init_count} clients for {call_count} retry attempts. "
            "Retries should reuse the same client."
        )
