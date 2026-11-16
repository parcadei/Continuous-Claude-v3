"""Tests for EmbeddingService - Embedding generation with caching and batching.

Phase 5: Embedding Pipeline Integration

Tests cover:
- Single text embedding
- Batch embedding
- Embedding dimension validation
- Caching (same text returns same embedding without API call)
- Rate limiting / batching
- Error handling (API failure)
- Fallback behavior
- Integration with MemoryServicePG
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Helper to create mock httpx client
HTTPX_PATCH_PATH = "scripts.agentica.embedding_service.httpx.AsyncClient"


def create_mock_client(mock_response):
    """Create a properly configured mock httpx client."""
    mock_client = MagicMock()
    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    mock_client.return_value = mock_instance
    return mock_client


class TestEmbeddingSingleText:
    """Test embedding single text strings."""

    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 1536}],
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        }
        mock_response.raise_for_status = MagicMock()
        return mock_response

    @pytest.mark.asyncio
    async def test_embed_single_text(self, mock_openai_response):
        """Should embed a single text and return 1536-dim vector."""
        from scripts.agentica.embedding_service import EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_openai_response)
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai")
                embedding = await service.embed("Hello, world!")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_embed_returns_correct_dimension(self, mock_openai_response):
        """Should return embedding with correct dimension based on provider."""
        from scripts.agentica.embedding_service import EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_openai_response)
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai")
                embedding = await service.embed("Test text")

        # OpenAI text-embedding-3-small is 1536 dimensions
        assert service.dimension == 1536
        assert len(embedding) == service.dimension


class TestEmbeddingBatch:
    """Test batch embedding operations."""

    @pytest.fixture
    def mock_batch_response(self):
        """Mock OpenAI batch API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 1536, "index": 0},
                {"embedding": [0.2] * 1536, "index": 1},
                {"embedding": [0.3] * 1536, "index": 2},
            ],
            "usage": {"prompt_tokens": 30, "total_tokens": 30},
        }
        mock_response.raise_for_status = MagicMock()
        return mock_response

    @pytest.mark.asyncio
    async def test_embed_batch(self, mock_batch_response):
        """Should embed multiple texts in a single API call."""
        from scripts.agentica.embedding_service import EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_batch_response)
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai")
                embeddings = await service.embed_batch(
                    ["Text 1", "Text 2", "Text 3"]
                )

        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self):
        """Should return empty list for empty input."""
        from scripts.agentica.embedding_service import EmbeddingService

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            service = EmbeddingService(provider="openai")
            embeddings = await service.embed_batch([])

        assert embeddings == []

    @pytest.mark.asyncio
    async def test_embed_batch_preserves_order(self, mock_batch_response):
        """Should preserve order of inputs in batch response."""
        from scripts.agentica.embedding_service import EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_batch_response)
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai")
                embeddings = await service.embed_batch(["A", "B", "C"])

        # Each embedding should be different based on mock data
        assert embeddings[0][0] == 0.1
        assert embeddings[1][0] == 0.2
        assert embeddings[2][0] == 0.3


class TestEmbeddingCaching:
    """Test embedding caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_returns_same_embedding(self):
        """Should return cached embedding without API call."""
        from scripts.agentica.embedding_service import EmbeddingService

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": [0.5] * 1536}]}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = mock_post
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai", cache_enabled=True)

                # First call - hits API
                embedding1 = await service.embed("Same text")
                # Second call - should use cache
                embedding2 = await service.embed("Same text")

        assert call_count == 1  # Only one API call
        assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_cache_content_hash_based(self):
        """Should cache based on content hash, not object identity."""
        from scripts.agentica.embedding_service import EmbeddingService

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": [0.5] * 1536}]}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = mock_post
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai", cache_enabled=True)

                text1 = "Hello"
                text2 = "Hel" + "lo"  # Same content, different object

                await service.embed(text1)
                await service.embed(text2)

        assert call_count == 1  # Same content hash

    @pytest.mark.asyncio
    async def test_cache_different_texts_make_separate_calls(self):
        """Should make separate API calls for different texts."""
        from scripts.agentica.embedding_service import EmbeddingService

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [{"embedding": [call_count * 0.1] * 1536}]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = mock_post
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai", cache_enabled=True)

                await service.embed("Text A")
                await service.embed("Text B")
                await service.embed("Text C")

        assert call_count == 3  # Three different texts

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Should not cache when cache_enabled=False."""
        from scripts.agentica.embedding_service import EmbeddingService

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": [0.5] * 1536}]}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = mock_post
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai", cache_enabled=False)

                await service.embed("Same text")
                await service.embed("Same text")

        assert call_count == 2  # Two API calls for same text


class TestEmbeddingBatching:
    """Test rate limiting and automatic batching."""

    @pytest.mark.asyncio
    async def test_large_batch_splits_into_chunks(self):
        """Should split large batches to respect API limits."""
        from scripts.agentica.embedding_service import EmbeddingService

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return embeddings for the number of inputs in this chunk
            json_data = kwargs.get("json", {})
            inputs = json_data.get("input", [])
            if isinstance(inputs, str):
                inputs = [inputs]

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {"embedding": [0.1] * 1536, "index": i} for i in range(len(inputs))
                ]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = mock_post
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                # Default batch size is 100, so 250 texts should split into 3 chunks
                service = EmbeddingService(provider="openai", max_batch_size=100)
                texts = [f"Text {i}" for i in range(250)]
                embeddings = await service.embed_batch(texts)

        assert call_count == 3  # 100 + 100 + 50
        assert len(embeddings) == 250


class TestEmbeddingErrorHandling:
    """Test error handling for API failures."""

    @pytest.mark.asyncio
    async def test_api_error_raises_exception(self):
        """Should raise exception on API error."""
        from scripts.agentica.embedding_service import EmbeddingError, EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock(
                side_effect=Exception("API rate limit exceeded")
            )

            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai")

                with pytest.raises(EmbeddingError) as exc_info:
                    await service.embed("Test text")

        assert "API" in str(exc_info.value) or "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_error(self):
        """Should raise error if API key is missing."""
        from scripts.agentica.embedding_service import EmbeddingService

        with patch.dict("os.environ", {}, clear=True):
            # Remove any existing OPENAI_API_KEY
            import os

            os.environ.pop("OPENAI_API_KEY", None)

            with pytest.raises(ValueError) as exc_info:
                EmbeddingService(provider="openai")

        assert "OPENAI_API_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Should retry on transient errors."""
        from scripts.agentica.embedding_service import EmbeddingService

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()

            if call_count < 3:
                # First two calls fail
                mock_response.raise_for_status = MagicMock(
                    side_effect=Exception("Temporary error")
                )
            else:
                # Third call succeeds
                mock_response.json.return_value = {"data": [{"embedding": [0.5] * 1536}]}
                mock_response.raise_for_status = MagicMock()

            return mock_response

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = mock_post
            mock_client.return_value = mock_instance

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                service = EmbeddingService(provider="openai", max_retries=3)
                embedding = await service.embed("Test text")

        assert call_count == 3
        assert len(embedding) == 1536


class TestEmbeddingFallback:
    """Test fallback behavior when primary provider fails."""

    @pytest.mark.asyncio
    async def test_fallback_to_mock_provider(self):
        """Should fallback to mock provider when specified."""
        from scripts.agentica.embedding_service import EmbeddingService

        # Mock provider always works without API calls
        service = EmbeddingService(provider="mock")
        embedding = await service.embed("Any text")

        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_mock_provider_deterministic(self):
        """Mock provider should return deterministic embeddings based on text."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")

        embedding1 = await service.embed("Same text")
        embedding2 = await service.embed("Same text")

        assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_mock_provider_different_texts(self):
        """Mock provider should return different embeddings for different texts."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")

        embedding1 = await service.embed("Text A")
        embedding2 = await service.embed("Text B")

        # Should be different (not necessarily orthogonal, but different)
        assert embedding1 != embedding2


class TestEmbeddingProviderProtocol:
    """Test that EmbeddingService satisfies EmbeddingProvider protocol."""

    @pytest.mark.asyncio
    async def test_implements_protocol(self):
        """EmbeddingService should implement EmbeddingProvider protocol."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")

        # Check protocol methods exist (EmbeddingProvider from memory_service_pg)
        assert hasattr(service, "embed")
        assert hasattr(service, "dimension")
        assert callable(service.embed)

    @pytest.mark.asyncio
    async def test_works_with_memory_service(self):
        """EmbeddingService should work with MemoryServicePG.store_with_embedding."""
        from scripts.agentica.embedding_service import EmbeddingService

        # This is a protocol compliance test - we just verify the interface
        # Actual integration requires PostgreSQL
        service = EmbeddingService(provider="mock")

        # These are the methods required by EmbeddingProvider
        embedding = await service.embed("Test content")
        dimension = service.dimension

        assert isinstance(embedding, list)
        assert isinstance(dimension, int)
        assert len(embedding) == dimension


class TestEmbeddingDimension:
    """Test embedding dimension configuration."""

    def test_openai_dimension(self):
        """OpenAI text-embedding-3-small should be 1536 dimensions."""
        from scripts.agentica.embedding_service import EmbeddingService

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            service = EmbeddingService(provider="openai")

        assert service.dimension == 1536

    def test_mock_dimension(self):
        """Mock provider should match OpenAI dimension by default."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")
        assert service.dimension == 1536

    def test_configurable_dimension(self):
        """Should support configurable dimension for mock provider."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock", dimension=768)
        assert service.dimension == 768

    @pytest.mark.asyncio
    async def test_embed_matches_dimension(self):
        """Embedded vector length should match dimension property."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock", dimension=768)
        embedding = await service.embed("Test")

        assert len(embedding) == service.dimension == 768
