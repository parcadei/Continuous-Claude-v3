"""Test embedding dimension compatibility for PostgreSQL memory service.

Phase 3.0: Fix critical embedding dimension mismatch.

The schema (docker/init.sql) and code (memory_service_pg.py) must agree
on the embedding dimension. The code pads to 4096 dimensions, so the
schema must use vector(4096).

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection

Run with:
    uv run pytest tests/unit/test_memory_service_pg_embedding.py -v
"""

import pytest
from uuid import uuid4


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-embedding-{uuid4().hex[:8]}"


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
            await conn.execute(
                "DELETE FROM archival_memory WHERE session_id = $1", sid
            )


class TestEmbeddingDimension:
    """Test embedding dimension compatibility."""

    @pytest.mark.asyncio
    async def test_embedding_dimension_4096(self, session_id, cleanup_session):
        """Verify 4096-dim embeddings can be stored.

        The memory service pads embeddings to 4096 dimensions (Letta pattern).
        The database schema must accept this dimension.
        """
        from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

        cleanup_session(session_id)

        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()

        # Create a 4096-dim embedding directly
        embedding_4096 = [0.1] * 4096

        # This should NOT raise an error if schema is correct
        memory_id = await memory.store(
            content="Test content with 4096-dim embedding",
            embedding=embedding_4096,
        )

        assert memory_id is not None
        assert len(memory_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_embedding_dimension_padding(self, session_id, cleanup_session):
        """Verify smaller embeddings are padded to 4096.

        Voyage AI produces 1024-dim embeddings. The memory service
        should pad them to 4096 before storage.
        """
        from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

        cleanup_session(session_id)

        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()

        # Create a 1024-dim embedding (Voyage AI native dimension)
        embedding_1024 = [0.2] * 1024

        # This should pad to 4096 and store successfully
        memory_id = await memory.store(
            content="Test content with 1024-dim embedding (padded)",
            embedding=embedding_1024,
        )

        assert memory_id is not None
        assert len(memory_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_embedding_dimension_1536_padding(self, session_id, cleanup_session):
        """Verify OpenAI embeddings (1536-dim) are padded to 4096."""
        from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

        cleanup_session(session_id)

        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()

        # Create a 1536-dim embedding (OpenAI text-embedding-3-small)
        embedding_1536 = [0.3] * 1536

        # This should pad to 4096 and store successfully
        memory_id = await memory.store(
            content="Test content with 1536-dim embedding (padded)",
            embedding=embedding_1536,
        )

        assert memory_id is not None
        assert len(memory_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_vector_search_with_padded_embedding(
        self, session_id, cleanup_session
    ):
        """Verify vector search works with padded embeddings."""
        from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

        cleanup_session(session_id)

        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()

        # Store with 1024-dim embedding (will be padded to 4096)
        embedding_1024 = [0.5] * 1024
        await memory.store(
            content="Python is a programming language",
            embedding=embedding_1024,
        )

        # Search with similar embedding
        query_embedding = [0.5] * 1024  # Same embedding
        results = await memory.search_vector(query_embedding, limit=1)

        assert len(results) >= 1
        assert "Python" in results[0]["content"]
        assert results[0]["similarity"] > 0.99  # Should be very high similarity

    @pytest.mark.asyncio
    async def test_pad_embedding_method(self, session_id):
        """Test the _pad_embedding method directly."""
        from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

        memory = MemoryServicePG(session_id=session_id)

        # Test padding 1024 -> 4096
        vec_1024 = [1.0] * 1024
        padded = memory._pad_embedding(vec_1024)
        assert len(padded) == 4096
        assert padded[:1024] == vec_1024  # First 1024 should be unchanged
        assert all(v == 0.0 for v in padded[1024:])  # Rest should be zeros

        # Test padding 1536 -> 4096
        vec_1536 = [2.0] * 1536
        padded = memory._pad_embedding(vec_1536)
        assert len(padded) == 4096
        assert padded[:1536] == vec_1536

        # Test truncation when already >= 4096
        vec_5000 = [3.0] * 5000
        padded = memory._pad_embedding(vec_5000)
        assert len(padded) == 4096
        assert all(v == 3.0 for v in padded)


class TestTemporalFactsEmbedding:
    """Test temporal_facts table embedding dimension."""

    @pytest.mark.asyncio
    async def test_temporal_facts_embedding_dimension(self, cleanup_session):
        """Verify temporal_facts accepts 4096-dim embeddings.

        The temporal_facts table also has an embedding column that
        should match the 4096 dimension used elsewhere.
        """
        from scripts.agentica_patterns.postgres_pool import (
            get_connection,
            init_pgvector,
        )

        session_id = unique_session_id()
        cleanup_session(session_id)

        async with get_connection() as conn:
            await init_pgvector(conn)

            # Create a 4096-dim embedding
            embedding_4096 = [0.1] * 4096

            # This should NOT raise an error if schema is correct
            result = await conn.fetchrow(
                """
                INSERT INTO temporal_facts
                    (session_id, key, value, embedding)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """,
                session_id,
                "test_key",
                "test_value",
                embedding_4096,
            )

            assert result is not None
            assert result["id"] is not None

            # Cleanup
            await conn.execute(
                "DELETE FROM temporal_facts WHERE session_id = $1", session_id
            )
