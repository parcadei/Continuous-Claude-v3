"""Tests for cross-encoder re-ranker.

Phase 4: Cross-Encoder Re-ranker - TDD failing tests first.

Tests cover:
- Cross-encoder scoring
- Batch re-ranking
- Cohere reranker mock
- Empty documents handling
- top_k parameter
- Original rank preservation

Run with:
    uv run pytest tests/unit/test_reranker.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCrossEncoderReranker:
    """Test local cross-encoder reranker."""

    @pytest.fixture
    def skip_if_no_st(self):
        """Skip if sentence-transformers not installed."""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    @pytest.mark.asyncio
    async def test_rerank_orders_by_relevance(self, skip_if_no_st):
        """Should order documents by relevance to query."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()

        documents = [
            "Python is a programming language",
            "Cooking recipes for pasta",
            "Python machine learning tutorial",
        ]

        results = await reranker.rerank("Python programming", documents)

        assert len(results) == 3
        # Python-related docs should rank higher
        assert "Python" in results[0].content
        assert "Cooking" not in results[0].content

    @pytest.mark.asyncio
    async def test_rerank_top_k(self, skip_if_no_st):
        """Should respect top_k parameter."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        documents = [f"Document {i}" for i in range(10)]

        results = await reranker.rerank("test query", documents, top_k=3)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self, skip_if_no_st):
        """Should handle empty document list."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        results = await reranker.rerank("query", [])

        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_preserves_original_rank(self, skip_if_no_st):
        """Should track original document position."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        documents = ["Doc A", "Doc B", "Doc C"]

        results = await reranker.rerank("query", documents)

        # All original ranks should be present
        original_ranks = {r.original_rank for r in results}
        assert original_ranks == {0, 1, 2}

    @pytest.mark.asyncio
    async def test_rerank_returns_scores(self, skip_if_no_st):
        """Should return relevance scores."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        documents = ["Python programming", "Java development"]

        results = await reranker.rerank("Python", documents)

        assert len(results) == 2
        for result in results:
            assert hasattr(result, "score")
            assert isinstance(result.score, float)


class TestCohereReranker:
    """Test Cohere API reranker."""

    @pytest.fixture
    def mock_cohere_response(self):
        """Mock Cohere API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.80},
                {"index": 1, "relevance_score": 0.30},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        return mock_response

    @pytest.mark.asyncio
    async def test_cohere_rerank(self, mock_cohere_response):
        """Should call Cohere API and parse response."""
        from scripts.agentica.reranker import CohereReranker

        with patch("scripts.agentica.reranker.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_cohere_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
                reranker = CohereReranker()
                results = await reranker.rerank(
                    "query", ["Doc A", "Doc B", "Doc C"]
                )

        assert len(results) == 3
        assert results[0].score == 0.95
        assert results[0].content == "Doc C"  # index 2

    def test_cohere_missing_api_key(self):
        """Should raise error if COHERE_API_KEY missing."""
        from scripts.agentica.reranker import CohereReranker

        with patch.dict("os.environ", {}, clear=True):
            import os

            os.environ.pop("COHERE_API_KEY", None)

            with pytest.raises(ValueError) as exc_info:
                CohereReranker()

        assert "COHERE_API_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cohere_respects_top_k(self, mock_cohere_response):
        """Should pass top_n parameter to Cohere API."""
        from scripts.agentica.reranker import CohereReranker

        with patch("scripts.agentica.reranker.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_cohere_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
                reranker = CohereReranker()
                await reranker.rerank(
                    "query", ["Doc A", "Doc B", "Doc C"], top_k=2
                )

            # Verify API was called with top_n
            call_args = mock_instance.post.call_args
            json_data = call_args.kwargs.get("json", {})
            assert json_data.get("top_n") == 2

    @pytest.mark.asyncio
    async def test_cohere_empty_documents(self, mock_cohere_response):
        """Should handle empty document list."""
        from scripts.agentica.reranker import CohereReranker

        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            reranker = CohereReranker()
            results = await reranker.rerank("query", [])

        assert results == []


class TestRerankerFactory:
    """Test reranker factory function."""

    @pytest.fixture
    def skip_if_no_st(self):
        """Skip if sentence-transformers not installed."""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_get_local_reranker(self, skip_if_no_st):
        """Should create local reranker."""
        from scripts.agentica.reranker import get_reranker

        reranker = get_reranker("local")
        assert reranker is not None

    def test_get_cohere_reranker(self):
        """Should create Cohere reranker."""
        from scripts.agentica.reranker import get_reranker

        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            reranker = get_reranker("cohere")
            assert reranker is not None

    def test_unknown_provider(self):
        """Should raise for unknown provider."""
        from scripts.agentica.reranker import get_reranker

        with pytest.raises(ValueError):
            get_reranker("unknown")


class TestRankedDocument:
    """Test RankedDocument dataclass."""

    def test_ranked_document_fields(self):
        """Should have all expected fields."""
        from scripts.agentica.reranker import RankedDocument

        doc = RankedDocument(
            content="Test content",
            score=0.95,
            original_rank=2,
            metadata={"source": "test"},
        )

        assert doc.content == "Test content"
        assert doc.score == 0.95
        assert doc.original_rank == 2
        assert doc.metadata == {"source": "test"}

    def test_ranked_document_optional_metadata(self):
        """Metadata should be optional."""
        from scripts.agentica.reranker import RankedDocument

        doc = RankedDocument(
            content="Test content",
            score=0.95,
            original_rank=0,
        )

        assert doc.metadata is None


class TestRerankerAbstractInterface:
    """Test Reranker abstract interface."""

    def test_reranker_is_abstract(self):
        """Reranker should be an abstract base class."""
        from scripts.agentica.reranker import Reranker

        # Should not be directly instantiable
        with pytest.raises(TypeError):
            Reranker()


class TestRerankerHardening:
    """Test HIGH priority edge cases and error handling.

    Based on mutation analysis in:
    thoughts/shared/work/reranker-pipeline/phase2-hardening/01-mutation-bugs.md
    """

    @pytest.fixture
    def skip_if_no_st(self):
        """Skip if sentence-transformers not installed."""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    # Boundary Conditions - HIGH PRIORITY

    @pytest.mark.asyncio
    async def test_top_k_zero_returns_empty(self, skip_if_no_st):
        """top_k=0 should return empty list, not error."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        documents = ["Doc A", "Doc B", "Doc C"]

        results = await reranker.rerank("query", documents, top_k=0)

        assert results == []

    @pytest.mark.asyncio
    async def test_top_k_negative_raises(self, skip_if_no_st):
        """Negative top_k should raise ValueError."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        documents = ["Doc A", "Doc B"]

        with pytest.raises(ValueError) as exc_info:
            await reranker.rerank("query", documents, top_k=-1)

        assert "top_k" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_empty_query_handled(self, skip_if_no_st):
        """Empty query should be valid but return results."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        documents = ["Doc A", "Doc B"]

        # Should not raise - empty query is technically valid
        results = await reranker.rerank("", documents)

        assert len(results) == 2  # Returns all docs with low scores

    @pytest.mark.asyncio
    async def test_whitespace_documents_filtered(self, skip_if_no_st):
        """Documents with only whitespace should be filtered out."""
        from scripts.agentica.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        documents = ["Real document", "   ", "", "Another real one"]

        results = await reranker.rerank("query", documents)

        # Should only return non-whitespace docs
        assert len(results) == 2
        assert all(r.content.strip() for r in results)

    # Error Handling - HIGH PRIORITY (Cohere)

    @pytest.mark.asyncio
    async def test_cohere_timeout_raises(self):
        """Cohere API timeout should raise httpx.TimeoutException."""
        from scripts.agentica.reranker import CohereReranker

        with patch("scripts.agentica.reranker.httpx.AsyncClient") as mock_client:
            # Simulate timeout
            mock_instance = AsyncMock()
            import httpx
            mock_instance.post.side_effect = httpx.TimeoutException("Request timed out")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
                reranker = CohereReranker()

                with pytest.raises(httpx.TimeoutException):
                    await reranker.rerank("query", ["Doc A", "Doc B"])

    @pytest.mark.asyncio
    async def test_cohere_http_error_raises(self):
        """Cohere API HTTP 500 should raise httpx.HTTPStatusError."""
        from scripts.agentica.reranker import CohereReranker

        with patch("scripts.agentica.reranker.httpx.AsyncClient") as mock_client:
            # Simulate HTTP 500 error
            mock_response = MagicMock()
            import httpx
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )

            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
                reranker = CohereReranker()

                with pytest.raises(httpx.HTTPStatusError):
                    await reranker.rerank("query", ["Doc A", "Doc B"])
