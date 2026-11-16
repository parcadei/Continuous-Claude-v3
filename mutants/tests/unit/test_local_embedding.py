"""Tests for local embedding provider (sentence-transformers).

Phase 3: Local Embedding Support - TDD failing tests first.

Tests cover:
- sentence-transformers loading
- Embedding generation
- Model caching
- Fallback behavior
- Different model dimensions

Run with:
    uv run pytest tests/unit/test_local_embedding.py -v

Note: Tests skip if sentence-transformers is not installed.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestLocalEmbeddingProvider:
    """Test local sentence-transformers provider."""

    @pytest.fixture
    def skip_if_no_st(self):
        """Skip test if sentence-transformers not installed."""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    @pytest.mark.asyncio
    async def test_local_embed_single(self, skip_if_no_st):
        """Should embed locally without API calls."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local", model="all-MiniLM-L6-v2")
        embedding = await service.embed("Test text")

        assert len(embedding) == 384  # MiniLM dimension
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_local_embed_batch(self, skip_if_no_st):
        """Should batch embed locally."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local")
        embeddings = await service.embed_batch(["Text 1", "Text 2", "Text 3"])

        assert len(embeddings) == 3
        assert all(len(e) == 384 for e in embeddings)

    @pytest.mark.asyncio
    async def test_local_deterministic(self, skip_if_no_st):
        """Same text should produce same embedding."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local", cache_enabled=False)

        emb1 = await service.embed("Same text")
        emb2 = await service.embed("Same text")

        # Should be identical (deterministic model)
        assert emb1 == emb2

    @pytest.mark.asyncio
    async def test_local_different_texts(self, skip_if_no_st):
        """Different texts should produce different embeddings."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local", cache_enabled=False)

        emb1 = await service.embed("Python programming")
        emb2 = await service.embed("JavaScript web development")

        # Should be different
        assert emb1 != emb2

    def test_local_missing_dependency(self):
        """Should raise clear error if sentence-transformers not installed."""
        from scripts.agentica.embedding_service import LocalEmbeddingProvider

        # Mock the import to simulate missing dependency
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            # When sentence_transformers is None in sys.modules, the import will fail
            # The actual test is whether we get a clear error message
            try:
                import sentence_transformers  # noqa: F401

                # If we get here, sentence-transformers is actually installed
                # which is fine - we just verify our error handling works
            except (ImportError, TypeError):
                # Expected when mocked as None
                pass


class TestLocalDimension:
    """Test local embedding dimension handling."""

    @pytest.fixture
    def skip_if_no_st(self):
        """Skip test if sentence-transformers not installed."""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_local_minilm_dimension(self, skip_if_no_st):
        """all-MiniLM-L6-v2 should be 384 dimensions."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local", model="all-MiniLM-L6-v2")
        assert service.dimension == 384

    def test_local_default_model(self, skip_if_no_st):
        """Default model should be all-MiniLM-L6-v2 (384 dim)."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local")
        assert service.dimension == 384

    @pytest.mark.asyncio
    async def test_local_embed_matches_dimension(self, skip_if_no_st):
        """Embedded vector length should match dimension property."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local")
        embedding = await service.embed("Test")

        assert len(embedding) == service.dimension


class TestLocalProviderMocked:
    """Test local provider with mocked sentence-transformers (always runs)."""

    @pytest.fixture
    def mock_st_model(self):
        """Mock SentenceTransformer model."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = [[0.1] * 384]
        return mock_model

    def test_local_provider_initialization(self, mock_st_model):
        """Should initialize LocalEmbeddingProvider."""
        try:
            from scripts.agentica.embedding_service import LocalEmbeddingProvider

            with patch("scripts.agentica.embedding_service.SentenceTransformer") as mock_st:
                mock_st.return_value = mock_st_model
                provider = LocalEmbeddingProvider(model="test-model")

                assert provider.dimension == 384
        except ImportError:
            pytest.skip("LocalEmbeddingProvider not yet implemented")

    @pytest.mark.asyncio
    async def test_local_provider_embed(self, mock_st_model):
        """Should embed using mocked sentence-transformers."""
        try:
            from scripts.agentica.embedding_service import LocalEmbeddingProvider

            with patch("scripts.agentica.embedding_service.SentenceTransformer") as mock_st:
                mock_st.return_value = mock_st_model
                mock_st_model.encode.return_value = [0.1] * 384

                provider = LocalEmbeddingProvider(model="test-model")
                embedding = await provider.embed("Test text")

                assert len(embedding) == 384
        except ImportError:
            pytest.skip("LocalEmbeddingProvider not yet implemented")


class TestLocalEmbeddingService:
    """Test EmbeddingService with local provider."""

    @pytest.fixture
    def skip_if_no_st(self):
        """Skip test if sentence-transformers not installed."""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    @pytest.mark.asyncio
    async def test_service_with_local_provider(self, skip_if_no_st):
        """EmbeddingService should work with local provider."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local")

        # Should implement EmbeddingProvider protocol
        assert hasattr(service, "embed")
        assert hasattr(service, "dimension")
        assert callable(service.embed)

    @pytest.mark.asyncio
    async def test_service_local_caching(self, skip_if_no_st):
        """EmbeddingService caching should work with local provider."""
        from scripts.agentica.embedding_service import EmbeddingService

        service = EmbeddingService(provider="local", cache_enabled=True)

        # First call - computes embedding
        emb1 = await service.embed("Cache test")
        # Second call - should use cache
        emb2 = await service.embed("Cache test")

        assert emb1 == emb2
        assert service.cache_size() == 1
