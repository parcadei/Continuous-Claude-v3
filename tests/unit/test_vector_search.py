"""Unit tests for vector similarity search (Phase 4: TDD).

Tests are designed to run against a PostgreSQL + pgvector database.
These tests cover:
- Store memory with embedding
- Cosine similarity search
- Top-k retrieval
- Hybrid search (vector + metadata filter)
- Embedding dimension validation (4096)
- Empty embedding handling
- Search with threshold
- store_with_embedding() method with EmbeddingService

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection

Run with:
    uv run pytest tests/unit/test_vector_search.py -v
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-vec-{uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def reset_pool_before_test():
    """Reset the connection pool before each test.

    This is needed because pytest-asyncio creates a new event loop for each test,
    and the global pool becomes invalid when the previous loop closes.
    """
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


@pytest.fixture
async def cleanup_session():
    """Fixture that returns a function to clean up a session."""
    sessions_to_clean: list[str] = []

    def register(session_id: str):
        sessions_to_clean.append(session_id)

    yield register

    # Cleanup all registered sessions
    from scripts.agentica_patterns.postgres_pool import get_connection

    async with get_connection() as conn:
        for sid in sessions_to_clean:
            await conn.execute("DELETE FROM core_memory WHERE session_id = $1", sid)
            await conn.execute(
                "DELETE FROM archival_memory WHERE session_id = $1", sid
            )


class TestStoreWithEmbedding:
    """Test storing facts with embeddings."""

    @pytest.mark.asyncio
    async def test_store_with_embedding_returns_id(self, memory):
        """Should store a fact with embedding and return a valid ID."""
        embedding = np.random.rand(1536).tolist()  # OpenAI dimension

        memory_id = await memory.store(
            "Python is a programming language",
            embedding=embedding,
        )

        # Memory ID should be a valid UUID
        assert memory_id is not None
        assert len(memory_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_store_with_embedding_is_searchable(self, memory):
        """Should be able to find stored embedding via vector search."""
        # Create a normalized embedding for more predictable similarity
        embedding = np.random.rand(1536)
        embedding = (embedding / np.linalg.norm(embedding)).tolist()

        await memory.store(
            "Python is great for AI development",
            embedding=embedding,
        )

        # Use same embedding to search (should find exact match)
        results = await memory.search_vector(embedding, limit=5)

        assert len(results) >= 1
        assert "Python" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_store_with_metadata_and_embedding(self, memory):
        """Should store both metadata and embedding together."""
        embedding = np.random.rand(1536).tolist()

        await memory.store(
            "Important AI research finding",
            metadata={"source": "paper", "year": 2024},
            embedding=embedding,
        )

        results = await memory.search_vector(embedding, limit=1)

        assert len(results) == 1
        assert results[0]["metadata"]["source"] == "paper"
        assert results[0]["metadata"]["year"] == 2024


class TestCosineSimilaritySearch:
    """Test cosine similarity search operations."""

    @pytest.mark.asyncio
    async def test_similar_embeddings_have_high_similarity(self, memory):
        """Similar embeddings should have similarity close to 1.0."""
        # Create a base embedding
        base_embedding = np.random.rand(1536)
        base_embedding = base_embedding / np.linalg.norm(base_embedding)

        # Store with base embedding
        await memory.store("Original content", embedding=base_embedding.tolist())

        # Create a very similar embedding (small perturbation)
        query_embedding = base_embedding + np.random.normal(0, 0.01, 1536)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        results = await memory.search_vector(query_embedding.tolist(), limit=1)

        assert len(results) == 1
        # Similarity should be very high (> 0.9)
        assert results[0]["similarity"] > 0.9

    @pytest.mark.asyncio
    async def test_dissimilar_embeddings_have_low_similarity(self, memory):
        """Dissimilar embeddings should have lower similarity scores."""
        # Create two orthogonal embeddings
        embedding1 = np.zeros(1536)
        embedding1[0] = 1.0  # Unit vector in first dimension

        embedding2 = np.zeros(1536)
        embedding2[1] = 1.0  # Unit vector in second dimension

        await memory.store("Content A", embedding=embedding1.tolist())

        results = await memory.search_vector(embedding2.tolist(), limit=1)

        assert len(results) == 1
        # Similarity should be low for orthogonal vectors
        assert results[0]["similarity"] < 0.5

    @pytest.mark.asyncio
    async def test_search_orders_by_similarity(self, memory):
        """Results should be ordered by similarity (most similar first)."""
        # Create a reference embedding
        reference = np.random.rand(1536)
        reference = reference / np.linalg.norm(reference)

        # Create embeddings with decreasing similarity
        high_sim = reference + np.random.normal(0, 0.05, 1536)
        high_sim = high_sim / np.linalg.norm(high_sim)

        low_sim = reference + np.random.normal(0, 0.5, 1536)
        low_sim = low_sim / np.linalg.norm(low_sim)

        # Store in reverse order of similarity
        await memory.store("Low similarity content", embedding=low_sim.tolist())
        await memory.store("High similarity content", embedding=high_sim.tolist())

        # Search with reference embedding
        results = await memory.search_vector(reference.tolist(), limit=2)

        assert len(results) == 2
        # First result should be more similar
        assert results[0]["similarity"] > results[1]["similarity"]
        assert "High" in results[0]["content"]


class TestTopKRetrieval:
    """Test top-k retrieval functionality."""

    @pytest.mark.asyncio
    async def test_limit_respects_k_value(self, memory):
        """Should return at most k results."""
        # Store 10 facts with embeddings
        for i in range(10):
            embedding = np.random.rand(1536).tolist()
            await memory.store(f"Fact number {i}", embedding=embedding)

        # Query with limit=3
        query_embedding = np.random.rand(1536).tolist()
        results = await memory.search_vector(query_embedding, limit=3)

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_returns_all_when_fewer_than_k(self, memory):
        """Should return all results when fewer than k exist."""
        embedding = np.random.rand(1536).tolist()
        await memory.store("Only fact", embedding=embedding)

        results = await memory.search_vector(embedding, limit=100)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_default_limit_is_10(self, memory):
        """Default limit should be 10."""
        # Store 15 facts
        base_embedding = np.random.rand(1536)
        for i in range(15):
            embedding = base_embedding + np.random.normal(0, 0.1, 1536)
            await memory.store(f"Fact {i}", embedding=embedding.tolist())

        # Query without explicit limit
        results = await memory.search_vector(base_embedding.tolist())

        assert len(results) <= 10


class TestHybridSearch:
    """Test hybrid search (vector + metadata filter)."""

    @pytest.mark.asyncio
    async def test_search_vector_with_metadata_filter(self, memory):
        """Should filter vector search results by metadata."""
        embedding = np.random.rand(1536)
        embedding = embedding / np.linalg.norm(embedding)

        # Store with different categories
        await memory.store(
            "Python for web development",
            metadata={"category": "web"},
            embedding=embedding.tolist(),
        )
        await memory.store(
            "Python for data science",
            metadata={"category": "data"},
            embedding=embedding.tolist(),
        )
        await memory.store(
            "Python for machine learning",
            metadata={"category": "ml"},
            embedding=embedding.tolist(),
        )

        # Search with metadata filter
        results = await memory.search_vector_with_filter(
            embedding.tolist(),
            metadata_filter={"category": "ml"},
            limit=5,
        )

        assert len(results) == 1
        assert "machine learning" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_text_and_vector(self, memory):
        """Should support hybrid search combining FTS and vector similarity."""
        embedding = np.random.rand(1536)
        embedding = embedding / np.linalg.norm(embedding)

        await memory.store(
            "Python machine learning tutorial",
            embedding=embedding.tolist(),
        )
        await memory.store(
            "JavaScript web development guide",
            embedding=(np.random.rand(1536)).tolist(),
        )

        # Hybrid search: text filter + vector ranking
        results = await memory.search_hybrid(
            text_query="Python",
            query_embedding=embedding.tolist(),
            limit=5,
        )

        # Should find Python content
        assert len(results) >= 1
        assert "Python" in results[0]["content"]


class TestEmbeddingDimensionValidation:
    """Test embedding dimension validation (4096 max)."""

    @pytest.mark.asyncio
    async def test_pads_smaller_embeddings_to_4096(self, memory):
        """Should pad embeddings smaller than 4096 to target dimension."""
        small_embedding = np.random.rand(1536).tolist()  # OpenAI dimension

        padded = memory._pad_embedding(small_embedding)

        assert len(padded) == 4096
        # First 1536 elements should match original
        assert padded[:1536] == small_embedding
        # Rest should be zeros
        assert all(v == 0.0 for v in padded[1536:])

    @pytest.mark.asyncio
    async def test_truncates_larger_embeddings_to_4096(self, memory):
        """Should truncate embeddings larger than 4096."""
        large_embedding = np.random.rand(5000).tolist()

        padded = memory._pad_embedding(large_embedding)

        assert len(padded) == 4096
        # Should match first 4096 elements
        assert padded == large_embedding[:4096]

    @pytest.mark.asyncio
    async def test_preserves_4096_dimension_embedding(self, memory):
        """Should preserve embeddings already at 4096 dimensions."""
        exact_embedding = np.random.rand(4096).tolist()

        padded = memory._pad_embedding(exact_embedding)

        assert len(padded) == 4096
        assert padded == exact_embedding

    @pytest.mark.asyncio
    async def test_different_embedding_dimensions_work(self, memory):
        """Should handle various common embedding dimensions."""
        dimensions = [384, 768, 1024, 1536, 3072, 4096]

        for dim in dimensions:
            embedding = np.random.rand(dim).tolist()
            memory_id = await memory.store(f"Content with {dim} dim", embedding=embedding)
            assert memory_id is not None

            # Should be searchable
            results = await memory.search_vector(embedding, limit=1)
            assert len(results) >= 1


class TestEmptyEmbeddingHandling:
    """Test handling of empty or None embeddings."""

    @pytest.mark.asyncio
    async def test_store_without_embedding(self, memory):
        """Should store content without embedding (text-only)."""
        memory_id = await memory.store("Text-only content, no embedding")

        assert memory_id is not None
        # Should be searchable via text search, not vector
        results = await memory.search_text("Text-only", limit=1)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_vector_search_excludes_no_embedding(self, memory):
        """Vector search should not return records without embeddings."""
        # Store without embedding
        await memory.store("No embedding content")

        # Store with embedding
        embedding = np.random.rand(1536).tolist()
        await memory.store("Has embedding", embedding=embedding)

        # Vector search should only find the one with embedding
        results = await memory.search_vector(embedding, limit=10)

        assert len(results) == 1
        assert "Has embedding" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_empty_list_embedding_treated_as_none(self, memory):
        """Empty list embedding should be treated as no embedding."""
        # This tests edge case handling
        memory_id = await memory.store("Content", embedding=[])

        # Should still be stored
        assert memory_id is not None

        # Should not appear in vector search
        query = np.random.rand(1536).tolist()
        results = await memory.search_vector(query, limit=10)

        # Either no results or not containing this content
        assert all("Content" != r["content"] for r in results) or len(results) == 0


class TestSearchWithThreshold:
    """Test vector search with similarity threshold."""

    @pytest.mark.asyncio
    async def test_threshold_filters_low_similarity(self, memory):
        """Should filter out results below similarity threshold."""
        # Create distinct embeddings
        embedding1 = np.zeros(1536)
        embedding1[0] = 1.0

        embedding2 = np.zeros(1536)
        embedding2[1] = 1.0

        await memory.store("Content A", embedding=embedding1.tolist())
        await memory.store("Content B", embedding=embedding2.tolist())

        # Search with high threshold - should only find near-exact matches
        results = await memory.search_vector_with_threshold(
            embedding1.tolist(),
            threshold=0.9,
            limit=10,
        )

        # Should find Content A (exact match) but not Content B (orthogonal)
        assert len(results) <= 2
        if len(results) > 0:
            assert all(r["similarity"] >= 0.9 for r in results)

    @pytest.mark.asyncio
    async def test_zero_threshold_returns_all(self, memory):
        """Threshold of 0 should return all results."""
        embedding = np.random.rand(1536).tolist()
        await memory.store("Content", embedding=embedding)

        results = await memory.search_vector_with_threshold(
            embedding,
            threshold=0.0,
            limit=10,
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_threshold_near_one_returns_only_exact(self, memory):
        """Very high threshold should only return near-exact matches."""
        embedding = np.random.rand(1536)
        embedding = embedding / np.linalg.norm(embedding)

        await memory.store("Exact match", embedding=embedding.tolist())

        # Add noise to create a less similar embedding
        noisy = embedding + np.random.normal(0, 0.5, 1536)
        noisy = noisy / np.linalg.norm(noisy)
        await memory.store("Noisy match", embedding=noisy.tolist())

        # Search with very high threshold
        results = await memory.search_vector_with_threshold(
            embedding.tolist(),
            threshold=0.99,
            limit=10,
        )

        # Should only find the exact match
        assert len(results) <= 1
        if len(results) == 1:
            assert "Exact" in results[0]["content"]


class TestStoreWithEmbeddingMethod:
    """Test the store_with_embedding() method using EmbeddingService."""

    @pytest.mark.asyncio
    async def test_store_with_embedder_generates_embedding(self, memory):
        """Should auto-generate embedding using provided embedder."""
        # Create a mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(return_value=np.random.rand(1536).tolist())
        mock_embedder.dimension = 1536

        memory_id = await memory.store_with_embedding(
            "Content to embed",
            embedder=mock_embedder,
        )

        # Should have called the embedder
        mock_embedder.embed.assert_called_once_with("Content to embed")
        assert memory_id is not None

    @pytest.mark.asyncio
    async def test_store_with_embedder_and_metadata(self, memory):
        """Should store with both generated embedding and metadata."""
        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(return_value=np.random.rand(1536).tolist())

        await memory.store_with_embedding(
            "Content to embed",
            metadata={"key": "value"},
            embedder=mock_embedder,
        )

        # Should be searchable
        results = await memory.search_text("Content", limit=1)
        assert len(results) == 1
        assert results[0]["metadata"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_store_with_embedding_without_embedder(self, memory):
        """Should store without embedding when no embedder provided."""
        # store_with_embedding without embedder should work like regular store
        memory_id = await memory.store_with_embedding("Just text, no embedder")

        assert memory_id is not None
        results = await memory.search_text("Just text", limit=1)
        assert len(results) == 1


class TestVectorSearchEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_search_empty_database(self, memory):
        """Should handle search on empty database gracefully."""
        embedding = np.random.rand(1536).tolist()
        results = await memory.search_vector(embedding, limit=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_all_zeros_embedding(self, memory):
        """Should handle all-zeros embedding gracefully."""
        zeros = [0.0] * 1536

        await memory.store("Content", embedding=np.random.rand(1536).tolist())

        # Search with zeros - should not crash
        results = await memory.search_vector(zeros, limit=5)

        # Should return results (similarity will be undefined/0)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_very_small_embedding_dimension(self, memory):
        """Should handle very small embedding dimensions."""
        tiny_embedding = [0.5, 0.5, 0.5]  # 3 dimensions

        memory_id = await memory.store("Tiny embedding", embedding=tiny_embedding)
        assert memory_id is not None

        # Should be padded and searchable
        results = await memory.search_vector(tiny_embedding, limit=1)
        assert len(results) >= 1
