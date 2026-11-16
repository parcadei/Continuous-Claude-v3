"""Tests for temporal_sessions table and population.

TDD approach:
1. Test schema exists
2. Test population from handoffs
3. Test embedding generation
"""

from __future__ import annotations

import pytest

# Schema tests - these should FAIL until migration runs


class TestTemporalSessionsSchema:
    """Test the temporal_sessions table schema exists."""

    @pytest.mark.asyncio
    async def test_temporal_sessions_table_exists(self, pg_connection):
        """Verify temporal_sessions table exists in PostgreSQL."""
        result = await pg_connection.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'temporal_sessions'
            )
        """)
        assert result is True, "temporal_sessions table should exist"

    @pytest.mark.asyncio
    async def test_temporal_sessions_has_required_columns(self, pg_connection):
        """Verify temporal_sessions has all required columns."""
        columns = await pg_connection.fetch("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'temporal_sessions'
            ORDER BY ordinal_position
        """)
        column_names = {row['column_name'] for row in columns}

        required = {
            'session_id', 'session_name', 'summary', 'key_decisions',
            'what_worked', 'what_failed', 'outcome', 'embedding', 'created_at'
        }
        assert required.issubset(column_names), f"Missing columns: {required - column_names}"

    @pytest.mark.asyncio
    async def test_temporal_sessions_embedding_is_vector(self, pg_connection):
        """Verify embedding column is vector type."""
        result = await pg_connection.fetchrow("""
            SELECT udt_name, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'temporal_sessions' AND column_name = 'embedding'
        """)
        assert result['udt_name'] == 'vector', "embedding should be vector type"

    @pytest.mark.asyncio
    async def test_temporal_sessions_fts_index_exists(self, pg_connection):
        """Verify FTS index exists for summary column."""
        result = await pg_connection.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'temporal_sessions'
                AND indexname LIKE '%fts%'
            )
        """)
        assert result is True, "FTS index should exist on summary column"


class TestTemporalSessionsPopulation:
    """Test populating temporal_sessions from handoffs."""

    @pytest.mark.asyncio
    async def test_insert_session_from_handoff(self, pg_connection):
        """Test inserting a session record from handoff data."""
        await pg_connection.execute("DELETE FROM temporal_sessions WHERE session_id = 'test-session-123'")

        await pg_connection.execute("""
            INSERT INTO temporal_sessions (
                session_id, session_name, summary, key_decisions,
                what_worked, what_failed, outcome
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
            'test-session-123',
            'test-session',
            'Implemented feature X',
            'Chose PostgreSQL over Redis',
            'TDD approach worked well',
            'Initial design was too complex',
            'SUCCEEDED'
        )

        result = await pg_connection.fetchrow("""
            SELECT * FROM temporal_sessions WHERE session_id = $1
        """, 'test-session-123')

        assert result is not None
        assert result['summary'] == 'Implemented feature X'
        assert result['outcome'] == 'SUCCEEDED'

        # Cleanup
        await pg_connection.execute("DELETE FROM temporal_sessions WHERE session_id = 'test-session-123'")

    @pytest.mark.asyncio
    async def test_insert_session_with_embedding(self, pg_connection):
        """Test inserting a session with embedding vector."""
        await pg_connection.execute("DELETE FROM temporal_sessions WHERE session_id = 'test-embed-123'")

        # Create a 1024-dim embedding (native Voyage dimension)
        embedding = [0.1] * 1024  # 1024 native dimensions
        # pgvector expects string format: '[0.1, 0.2, ...]'
        embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

        await pg_connection.execute("""
            INSERT INTO temporal_sessions (session_id, session_name, summary, embedding)
            VALUES ($1, $2, $3, $4::vector)
        """, 'test-embed-123', 'test', 'Test summary', embedding_str)

        result = await pg_connection.fetchrow("""
            SELECT session_id, embedding IS NOT NULL as has_embedding
            FROM temporal_sessions WHERE session_id = $1
        """, 'test-embed-123')

        assert result['has_embedding'] is True

        # Cleanup
        await pg_connection.execute("DELETE FROM temporal_sessions WHERE session_id = 'test-embed-123'")

    @pytest.mark.asyncio
    async def test_vector_similarity_search(self, pg_connection):
        """Test cosine similarity search on session embeddings."""
        # Helper to convert embedding list to pgvector string
        def to_vector_str(emb: list[float]) -> str:
            return '[' + ','.join(str(x) for x in emb) + ']'

        # Insert test sessions
        await pg_connection.execute("DELETE FROM temporal_sessions WHERE session_id LIKE 'test-search-%'")

        # Session about PostgreSQL (embedding biased toward first dims)
        pg_embedding = [0.9] * 512 + [0.1] * 512  # 1024 dims
        await pg_connection.execute("""
            INSERT INTO temporal_sessions (session_id, session_name, summary, embedding)
            VALUES ($1, $2, $3, $4::vector)
        """, 'test-search-pg', 'postgres-session', 'PostgreSQL migration', to_vector_str(pg_embedding))

        # Session about Redis (embedding biased toward middle dims)
        redis_embedding = [0.1] * 512 + [0.9] * 512  # 1024 dims
        await pg_connection.execute("""
            INSERT INTO temporal_sessions (session_id, session_name, summary, embedding)
            VALUES ($1, $2, $3, $4::vector)
        """, 'test-search-redis', 'redis-session', 'Redis caching', to_vector_str(redis_embedding))

        # Query similar to PostgreSQL
        query_embedding = [0.8] * 512 + [0.2] * 512  # 1024 dims

        results = await pg_connection.fetch("""
            SELECT session_id, summary, 1 - (embedding <=> $1::vector) as similarity
            FROM temporal_sessions
            WHERE session_id LIKE 'test-search-%'
            ORDER BY embedding <=> $1::vector
            LIMIT 5
        """, to_vector_str(query_embedding))

        # PostgreSQL session should be more similar
        assert len(results) == 2
        assert results[0]['session_id'] == 'test-search-pg'
        assert results[0]['similarity'] > results[1]['similarity']

        # Cleanup
        await pg_connection.execute("DELETE FROM temporal_sessions WHERE session_id LIKE 'test-search-%'")


# Fixture for PostgreSQL connection
@pytest.fixture
async def pg_connection():
    """Get PostgreSQL connection for testing."""
    import asyncpg
    import os

    url = os.environ.get(
        'AGENTICA_POSTGRES_URL',
        'postgresql://agentica:agentica_dev@localhost:5433/agentica_memory'
    )

    conn = await asyncpg.connect(url)
    # Enable pgvector
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    yield conn

    await conn.close()
