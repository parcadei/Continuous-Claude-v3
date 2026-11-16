"""Tests for Voyage AI embedding provider.

Phase 2: Voyage AI Provider - TDD failing tests first.

Tests cover:
- voyage-3 embedding (1024 dim)
- voyage-code-3 embedding (1024 dim)
- voyage-3-lite embedding (512 dim)
- Dimension handling
- API error handling
- Missing API key error
- Provider shorthand (provider="voyage-3")

Run with:
    uv run pytest tests/unit/test_voyage_embedding.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


HTTPX_PATCH_PATH = "scripts.agentica_patterns.embedding_service.httpx.AsyncClient"


class TestVoyageEmbeddingProvider:
    """Test Voyage AI embedding provider."""

    @pytest.fixture
    def mock_voyage_response(self):
        """Mock Voyage API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 1024, "index": 0}],
            "usage": {"total_tokens": 10},
        }
        mock_response.raise_for_status = MagicMock()
        return mock_response

    @pytest.mark.asyncio
    async def test_voyage_embed_single(self, mock_voyage_response):
        """Should embed with Voyage API."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_voyage_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
                service = EmbeddingService(provider="voyage")
                embedding = await service.embed("Test text")

        assert len(embedding) == 1024  # voyage-3 dimension

    @pytest.mark.asyncio
    async def test_voyage_model_selection(self):
        """Should support different Voyage models."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
            # voyage-3 (default)
            service1 = EmbeddingService(provider="voyage", model="voyage-3")
            assert service1.dimension == 1024

            # voyage-code-3
            service2 = EmbeddingService(provider="voyage", model="voyage-code-3")
            assert service2.dimension == 1024

            # voyage-3-lite
            service3 = EmbeddingService(provider="voyage", model="voyage-3-lite")
            assert service3.dimension == 512

    @pytest.mark.asyncio
    async def test_voyage_shorthand(self):
        """Should support provider='voyage-3' shorthand."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
            service = EmbeddingService(provider="voyage-code-3")
            assert service.dimension == 1024

    @pytest.mark.asyncio
    async def test_voyage_missing_api_key(self):
        """Should raise error if VOYAGE_API_KEY missing."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch.dict("os.environ", {}, clear=True):
            import os

            os.environ.pop("VOYAGE_API_KEY", None)

            with pytest.raises(ValueError) as exc_info:
                EmbeddingService(provider="voyage")

        assert "VOYAGE_API_KEY" in str(exc_info.value)


class TestVoyageBatchEmbedding:
    """Test Voyage batch embedding operations."""

    @pytest.fixture
    def mock_batch_response(self):
        """Mock Voyage batch API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 1024, "index": 0},
                {"embedding": [0.2] * 1024, "index": 1},
                {"embedding": [0.3] * 1024, "index": 2},
            ],
            "usage": {"total_tokens": 30},
        }
        mock_response.raise_for_status = MagicMock()
        return mock_response

    @pytest.mark.asyncio
    async def test_voyage_embed_batch(self, mock_batch_response):
        """Should embed multiple texts in a single API call."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_batch_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
                service = EmbeddingService(provider="voyage")
                embeddings = await service.embed_batch(
                    ["Text 1", "Text 2", "Text 3"]
                )

        assert len(embeddings) == 3
        assert all(len(e) == 1024 for e in embeddings)

    @pytest.mark.asyncio
    async def test_voyage_batch_preserves_order(self, mock_batch_response):
        """Should preserve order of inputs in batch response."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_batch_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
                service = EmbeddingService(provider="voyage")
                embeddings = await service.embed_batch(["A", "B", "C"])

        # Each embedding should be different based on mock data
        assert embeddings[0][0] == 0.1
        assert embeddings[1][0] == 0.2
        assert embeddings[2][0] == 0.3


class TestVoyageErrorHandling:
    """Test Voyage API error handling."""

    @pytest.mark.asyncio
    async def test_voyage_api_error_raises_exception(self):
        """Should raise exception on API error."""
        from scripts.agentica_patterns.embedding_service import EmbeddingError, EmbeddingService

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock(
                side_effect=Exception("API rate limit exceeded")
            )

            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
                service = EmbeddingService(provider="voyage")

                with pytest.raises(EmbeddingError) as exc_info:
                    await service.embed("Test text")

        assert "Voyage" in str(exc_info.value) or "API" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_voyage_retry_on_transient_error(self):
        """Should retry on transient errors."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

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
                mock_response.json.return_value = {
                    "data": [{"embedding": [0.5] * 1024, "index": 0}]
                }
                mock_response.raise_for_status = MagicMock()

            return mock_response

        with patch(HTTPX_PATCH_PATH) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = mock_post
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
                service = EmbeddingService(provider="voyage", max_retries=3)
                embedding = await service.embed("Test text")

        assert call_count == 3
        assert len(embedding) == 1024


class TestVoyageDimension:
    """Test Voyage embedding dimension handling."""

    def test_voyage_3_dimension(self):
        """voyage-3 should be 1024 dimensions."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
            service = EmbeddingService(provider="voyage", model="voyage-3")
        assert service.dimension == 1024

    def test_voyage_code_3_dimension(self):
        """voyage-code-3 should be 1024 dimensions."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
            service = EmbeddingService(provider="voyage", model="voyage-code-3")
        assert service.dimension == 1024

    def test_voyage_3_lite_dimension(self):
        """voyage-3-lite should be 512 dimensions."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
            service = EmbeddingService(provider="voyage", model="voyage-3-lite")
        assert service.dimension == 512

    def test_voyage_invalid_model_raises_error(self):
        """Should raise error for unknown Voyage model."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        with patch.dict("os.environ", {"VOYAGE_API_KEY": "test-key"}):
            with pytest.raises(ValueError) as exc_info:
                EmbeddingService(provider="voyage", model="voyage-invalid")

        assert "Unknown Voyage model" in str(exc_info.value)
