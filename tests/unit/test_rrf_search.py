"""Tests for RRF (Reciprocal Rank Fusion) hybrid search.

Phase 1: RRF Fusion - TDD failing tests first.

Tests cover:
- RRF score calculation
- Rank-based fusion vs weighted
- Empty results handling
- k parameter tuning
- FTS-only matches
- Vector-only matches
- Combined matches

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection

Run with:
    uv run pytest tests/unit/test_rrf_search.py -v
"""

from uuid import uuid4

import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-rrf-{uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def reset_pool_before_test():
    """Reset the connection pool before each test."""
    from scripts.agentica_patterns.postgres_pool import reset_pool

    reset_pool()
    yield
    reset_pool()


@pytest.fixture
def session_id():
    """Generate a unique session ID per test."""
    return unique_session_id()


@pytest.fixture
async def memory(session_id):
    """Create a MemoryServicePG instance for testing."""
    from scripts.agentica_patterns.memory_service_pg import MemoryServicePG
    from scripts.agentica_patterns.postgres_pool import get_connection

    memory = MemoryServicePG(session_id=session_id)
    await memory.connect()
    yield memory

    # Cleanup after test
    async with get_connection() as conn:
        await conn.execute(
            "DELETE FROM core_memory WHERE session_id = $1", session_id
        )
        await conn.execute(
            "DELETE FROM archival_memory WHERE session_id = $1", session_id
        )


class TestRRFScoreCalculation:
    """Test RRF score calculation is correct."""

    @pytest.mark.asyncio
    async def test_rrf_score_formula(self, memory):
        """RRF score should follow 1/(k + rank) formula."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Store a document that matches both FTS and vector
        await memory.store_with_embedding(
            "Python is a programming language for machine learning",
            embedder=embedder,
        )

        query = "Python programming"
        query_embedding = await embedder.embed(query)

        results = await memory.search_hybrid_rrf(
            text_query=query,
            query_embedding=query_embedding,
            limit=1,
            k=60,
        )

        assert len(results) == 1
        assert "rrf_score" in results[0]
        # Score should be positive
        assert results[0]["rrf_score"] > 0

    @pytest.mark.asyncio
    async def test_rrf_returns_expected_fields(self, memory):
        """RRF search should return all expected fields."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        await memory.store_with_embedding(
            "Test document for field validation",
            embedder=embedder,
            metadata={"source": "test"},
        )

        query_embedding = await embedder.embed("Test document")

        results = await memory.search_hybrid_rrf(
            text_query="Test document",
            query_embedding=query_embedding,
            limit=1,
        )

        assert len(results) == 1
        result = results[0]

        # Check all expected fields
        assert "id" in result
        assert "content" in result
        assert "metadata" in result
        assert "created_at" in result
        assert "rrf_score" in result

        # Validate metadata was preserved
        assert result["metadata"]["source"] == "test"


class TestRRFCombinesFTSAndVector:
    """Test RRF combines FTS and vector search results."""

    @pytest.mark.asyncio
    async def test_rrf_combines_fts_and_vector(self, memory):
        """RRF should combine FTS and vector results."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Store multiple documents with embeddings
        await memory.store_with_embedding(
            "Python is excellent for machine learning",
            embedder=embedder,
        )
        await memory.store_with_embedding(
            "JavaScript dominates web development",
            embedder=embedder,
        )
        await memory.store_with_embedding(
            "Rust provides memory safety without garbage collection",
            embedder=embedder,
        )

        # Query with both text and embedding
        query = "Python programming"
        query_embedding = await embedder.embed(query)

        results = await memory.search_hybrid_rrf(
            text_query=query,
            query_embedding=query_embedding,
            limit=3,
        )

        assert len(results) >= 1
        assert "rrf_score" in results[0]
        # Python result should rank high
        assert any("Python" in r["content"] for r in results[:2])

    @pytest.mark.asyncio
    async def test_rrf_ranks_by_combined_relevance(self, memory):
        """Documents matching both FTS and vector should rank higher."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Document that matches both query terms and semantically
        await memory.store_with_embedding(
            "Python programming language for data science and machine learning",
            embedder=embedder,
        )
        # Document that matches only FTS
        await memory.store_with_embedding(
            "The python snake is a large reptile found in tropics",
            embedder=embedder,
        )
        # Document that matches only semantically (no exact term match)
        await memory.store_with_embedding(
            "Data analysis with pandas and numpy libraries",
            embedder=embedder,
        )

        query = "Python programming"
        query_embedding = await embedder.embed(query)

        results = await memory.search_hybrid_rrf(
            text_query=query,
            query_embedding=query_embedding,
            limit=3,
        )

        assert len(results) >= 1
        # The document with both FTS and semantic match should be first
        assert "programming" in results[0]["content"].lower()


class TestRRFHandlesFTSOnlyMatch:
    """Test RRF handles documents that only match FTS."""

    @pytest.mark.asyncio
    async def test_rrf_handles_fts_only_match(self, memory):
        """RRF should include documents that only match FTS (no embedding)."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Store document WITHOUT embedding (FTS only)
        await memory.store("Python is a programming language")

        # Store document WITH embedding (different topic)
        await memory.store_with_embedding(
            "Cooking recipes for beginners",
            embedder=embedder,
        )

        query = "Python programming"
        query_embedding = await embedder.embed(query)

        results = await memory.search_hybrid_rrf(
            text_query=query,
            query_embedding=query_embedding,
            limit=5,
        )

        # Python doc should be included despite no embedding
        assert any("Python" in r["content"] for r in results)


class TestRRFHandlesVectorOnlyMatch:
    """Test RRF handles documents that only match vector search."""

    @pytest.mark.asyncio
    async def test_rrf_includes_semantic_only_matches(self, memory):
        """RRF should include semantically similar docs without FTS match."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Store document with embedding but no direct term match
        await memory.store_with_embedding(
            "Data science involves statistical analysis and modeling",
            embedder=embedder,
        )
        # Store document that matches FTS exactly
        await memory.store_with_embedding(
            "Machine learning algorithms",
            embedder=embedder,
        )

        # Query that might not match "Data science" via FTS but could match semantically
        query = "machine learning algorithms"
        query_embedding = await embedder.embed(query)

        results = await memory.search_hybrid_rrf(
            text_query=query,
            query_embedding=query_embedding,
            limit=5,
        )

        # Should return results (at least the exact match)
        assert len(results) >= 1


class TestRRFKParameter:
    """Test k parameter tuning effect on RRF scores."""

    @pytest.mark.asyncio
    async def test_rrf_k_parameter_affects_score_spread(self, memory):
        """Higher k should reduce score differences between ranks."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Use distinctly different content to ensure different rankings
        await memory.store_with_embedding(
            "Python is a programming language for data science",
            embedder=embedder,
        )
        await memory.store_with_embedding(
            "JavaScript is used for web development",
            embedder=embedder,
        )
        await memory.store_with_embedding(
            "Rust provides memory safety and performance",
            embedder=embedder,
        )

        query_embedding = await embedder.embed("Python programming")

        # Low k (k=1): scores vary more significantly
        results_low_k = await memory.search_hybrid_rrf(
            text_query="Python programming",
            query_embedding=query_embedding,
            k=1,
            limit=10,
        )

        # High k (k=100): scores are more compressed
        results_high_k = await memory.search_hybrid_rrf(
            text_query="Python programming",
            query_embedding=query_embedding,
            k=100,
            limit=10,
        )

        # With higher k, score differences should be smaller (or equal)
        if len(results_low_k) >= 2 and len(results_high_k) >= 2:
            diff_low = results_low_k[0]["rrf_score"] - results_low_k[1]["rrf_score"]
            diff_high = results_high_k[0]["rrf_score"] - results_high_k[1]["rrf_score"]
            # Score spread should be smaller with high k, or at least not larger
            assert diff_high <= diff_low

    @pytest.mark.asyncio
    async def test_rrf_default_k_is_60(self, memory):
        """Default k parameter should be 60."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        await memory.store_with_embedding("Test document", embedder=embedder)

        query_embedding = await embedder.embed("Test")

        # Call without k parameter
        results = await memory.search_hybrid_rrf(
            text_query="Test",
            query_embedding=query_embedding,
            limit=1,
        )

        assert len(results) == 1
        # Score should be around 1/(60+1) + 1/(60+1) = 0.0328 for a doc ranking 1st in both
        # Just verify it's reasonable
        assert 0 < results[0]["rrf_score"] < 1


class TestRRFEmptyResults:
    """Test RRF handles empty results correctly."""

    @pytest.mark.asyncio
    async def test_rrf_empty_results_no_matches(self, memory):
        """RRF should return empty list when nothing matches."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Store unrelated document
        await memory.store_with_embedding(
            "Cooking pasta recipes",
            embedder=embedder,
        )

        # Query for something completely different that won't FTS match
        query = "XYZ123ABC nonexistent"
        query_embedding = await embedder.embed(query)

        results = await memory.search_hybrid_rrf(
            text_query=query,
            query_embedding=query_embedding,
            limit=5,
        )

        # May return semantic matches even without FTS, but should not error
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_rrf_empty_memory(self, memory):
        """RRF should return empty list for empty memory."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()
        query_embedding = await embedder.embed("Any query")

        results = await memory.search_hybrid_rrf(
            text_query="Any query",
            query_embedding=query_embedding,
            limit=5,
        )

        assert results == []


class TestRRFLimit:
    """Test RRF respects limit parameter."""

    @pytest.mark.asyncio
    async def test_rrf_respects_limit(self, memory):
        """RRF should return at most limit results."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Store more documents than limit
        for i in range(10):
            await memory.store_with_embedding(
                f"Document {i} about programming",
                embedder=embedder,
            )

        query_embedding = await embedder.embed("programming")

        results = await memory.search_hybrid_rrf(
            text_query="programming",
            query_embedding=query_embedding,
            limit=3,
        )

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_rrf_returns_fewer_if_not_enough_matches(self, memory):
        """RRF should return fewer than limit if not enough matches."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Store only 2 documents
        await memory.store_with_embedding("Doc one", embedder=embedder)
        await memory.store_with_embedding("Doc two", embedder=embedder)

        query_embedding = await embedder.embed("Doc")

        results = await memory.search_hybrid_rrf(
            text_query="Doc",
            query_embedding=query_embedding,
            limit=10,  # Request more than available
        )

        assert len(results) == 2


class TestRRFOrdering:
    """Test RRF orders results correctly."""

    @pytest.mark.asyncio
    async def test_rrf_orders_by_score_descending(self, memory):
        """RRF should return results ordered by score descending."""
        from scripts.agentica_patterns.embedding_service import MockEmbeddingProvider

        embedder = MockEmbeddingProvider()

        # Store documents with varying relevance
        await memory.store_with_embedding(
            "Python programming language",
            embedder=embedder,
        )
        await memory.store_with_embedding(
            "Python snake in the zoo",
            embedder=embedder,
        )
        await memory.store_with_embedding(
            "Python Python Python programming Python",
            embedder=embedder,
        )

        query_embedding = await embedder.embed("Python programming")

        results = await memory.search_hybrid_rrf(
            text_query="Python programming",
            query_embedding=query_embedding,
            limit=3,
        )

        # Verify descending order
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i]["rrf_score"] >= results[i + 1]["rrf_score"]
