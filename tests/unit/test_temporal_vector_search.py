"""Tests for temporal vector search integration - Phase 3.6.

Tests the vector embedding support for temporal facts:
- Writing facts with embeddings via TemporalWriterPG
- Searching similar facts via TemporalMemoryStorePG
- Embedding padding/truncation to 4096 dimensions
- Graceful handling of facts without embeddings
- Session isolation for searches

Prerequisites:
- Docker must be running
- Run: ./docker/start-postgres.sh before tests
- pgvector extension must be available

Usage:
    uv run pytest tests/unit/test_temporal_vector_search.py -v
"""

from __future__ import annotations

import subprocess
import time

import pytest


def is_container_running(container_name: str = "agentica-postgres") -> bool:
    """Check if the PostgreSQL container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_container_healthy(container_name: str = "agentica-postgres") -> bool:
    """Check if the PostgreSQL container is healthy."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "healthy"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def ensure_postgres_running():
    """Ensure PostgreSQL container is running before tests."""
    import asyncio

    if not is_container_running():
        pytest.skip(
            "PostgreSQL container not running. "
            "Start with: ./docker/start-postgres.sh or "
            "docker compose -f docker/docker-compose.yml up -d"
        )

    # Wait for container to become healthy (max 30 seconds)
    for _ in range(30):
        if is_container_healthy():
            break
        time.sleep(1)
    else:
        pytest.skip("PostgreSQL container not healthy after 30 seconds")

    yield


@pytest.fixture(scope="function")
async def clean_temporal_tables(ensure_postgres_running):
    """Clean temporal tables before and after each test."""
    import asyncpg

    conn_string = "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
    conn = await asyncpg.connect(conn_string)
    try:
        await conn.execute("TRUNCATE temporal_facts, temporal_traces CASCADE")
    finally:
        await conn.close()

    yield

    # Clean after test
    conn = await asyncpg.connect(conn_string)
    try:
        await conn.execute("TRUNCATE temporal_facts, temporal_traces CASCADE")
    finally:
        await conn.close()


@pytest.fixture
async def pg_writer(clean_temporal_tables):
    """Create a TemporalWriterPG instance for testing."""
    from scripts.agentica_patterns.postgres_pool import reset_pool

    reset_pool()

    from scripts.backfill.temporal_writer_pg import TemporalWriterPG

    writer = TemporalWriterPG()
    await writer.connect()

    yield writer

    await writer.close()
    reset_pool()


@pytest.fixture
async def pg_store(clean_temporal_tables):
    """Create a TemporalMemoryStorePG instance for testing."""
    from scripts.agentica_patterns.postgres_pool import reset_pool

    reset_pool()

    from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

    store = TemporalMemoryStorePG(session_id="test-vector-session")
    await store.connect()

    yield store

    reset_pool()


class TestWriteFactWithEmbedding:
    """Test writing facts with vector embeddings."""

    @pytest.mark.asyncio
    async def test_write_fact_with_embedding(self, pg_writer) -> None:
        """Facts can be written with embeddings."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # Create a simple 128-dim embedding (will be padded to 4096)
        embedding = [0.1] * 128

        def mock_embedding_fn(text: str) -> list[float]:
            return embedding

        fact = SpanFact(key="file_read", value="/path/to/file.py", turn=1)
        outcome = SessionOutcome(
            session_id="session-embed-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        count = await pg_writer.write_facts_with_embeddings(
            session_id="session-embed-1",
            turn=1,
            facts=[fact],
            outcome=outcome,
            embedding_fn=mock_embedding_fn,
        )

        assert count == 1

        # Verify fact was written
        facts = await pg_writer.get_facts("session-embed-1")
        assert len(facts) == 1
        assert facts[0]["key"] == "file_read"

    @pytest.mark.asyncio
    async def test_write_facts_without_embedding_fn(self, pg_writer) -> None:
        """Facts can be written without embedding function (NULL embedding)."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        fact = SpanFact(key="file_read", value="/path/to/file.py", turn=1)
        outcome = SessionOutcome(
            session_id="session-no-embed",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        count = await pg_writer.write_facts_with_embeddings(
            session_id="session-no-embed",
            turn=1,
            facts=[fact],
            outcome=outcome,
            embedding_fn=None,  # No embedding function
        )

        assert count == 1

        # Verify fact was written
        facts = await pg_writer.get_facts("session-no-embed")
        assert len(facts) == 1


class TestSearchSimilar:
    """Test vector similarity search."""

    @pytest.mark.asyncio
    async def test_search_similar_returns_ranked(self, pg_writer, pg_store) -> None:
        """Similar facts returned by cosine similarity, ranked."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # Create embeddings that are similar (high similarity) and different (low similarity)
        # For cosine similarity, [1, 0, 0, ...] is similar to [0.9, 0.1, 0, ...]
        # but different from [0, 0, 1, ...]

        # Embedding 1: mostly in first dimension
        emb1 = [1.0] + [0.0] * 127
        # Embedding 2: similar to emb1
        emb2 = [0.9, 0.1] + [0.0] * 126
        # Embedding 3: orthogonal to emb1 (low similarity)
        emb3 = [0.0] * 64 + [1.0] + [0.0] * 63

        call_count = [0]
        embeddings = [emb1, emb2, emb3]

        def mock_embedding_fn(text: str) -> list[float]:
            result = embeddings[call_count[0] % 3]
            call_count[0] += 1
            return result

        outcome = SessionOutcome(
            session_id="test-vector-session",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        facts = [
            SpanFact(key="fact1", value="value1", turn=1),
            SpanFact(key="fact2", value="value2", turn=1),
            SpanFact(key="fact3", value="value3", turn=1),
        ]

        await pg_writer.write_facts_with_embeddings(
            session_id="test-vector-session",
            turn=1,
            facts=facts,
            outcome=outcome,
            embedding_fn=mock_embedding_fn,
        )

        # Query with embedding similar to emb1
        query_embedding = [1.0, 0.05] + [0.0] * 126

        results = await pg_store.search_similar(
            query_embedding=query_embedding,
            limit=10,
        )

        # Should return results (at least 2 with embeddings)
        assert len(results) >= 2

        # Results should have similarity scores
        assert all("similarity" in r for r in results)

        # Results should be ranked by similarity (descending)
        similarities = [r["similarity"] for r in results]
        assert similarities == sorted(similarities, reverse=True)

    @pytest.mark.asyncio
    async def test_search_without_embeddings(self, pg_writer, pg_store) -> None:
        """Search gracefully handles facts without embeddings (returns empty)."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # Write facts without embeddings (using regular write_facts)
        fact = SpanFact(key="no_embed", value="test", turn=1)
        outcome = SessionOutcome(
            session_id="test-vector-session",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        await pg_writer.write_facts("test-vector-session", [fact], outcome)

        # Search with an embedding - should return empty since no facts have embeddings
        query_embedding = [1.0] * 128

        results = await pg_store.search_similar(
            query_embedding=query_embedding,
            limit=10,
        )

        # Should return empty list (no facts with embeddings)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_by_session(self, pg_writer) -> None:
        """Search respects session isolation."""
        from scripts.agentica_patterns.postgres_pool import reset_pool
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        reset_pool()

        embedding = [1.0] * 128

        def mock_embedding_fn(text: str) -> list[float]:
            return embedding

        outcome1 = SessionOutcome(
            session_id="session-A",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )
        outcome2 = SessionOutcome(
            session_id="session-B",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        # Write to session A
        await pg_writer.write_facts_with_embeddings(
            session_id="session-A",
            turn=1,
            facts=[SpanFact(key="factA", value="valueA", turn=1)],
            outcome=outcome1,
            embedding_fn=mock_embedding_fn,
        )

        # Write to session B
        await pg_writer.write_facts_with_embeddings(
            session_id="session-B",
            turn=1,
            facts=[SpanFact(key="factB", value="valueB", turn=1)],
            outcome=outcome2,
            embedding_fn=mock_embedding_fn,
        )

        # Search in session A
        store_a = TemporalMemoryStorePG(session_id="session-A")
        await store_a.connect()
        results_a = await store_a.search_similar(query_embedding=embedding, limit=10)

        # Search in session B
        store_b = TemporalMemoryStorePG(session_id="session-B")
        await store_b.connect()
        results_b = await store_b.search_similar(query_embedding=embedding, limit=10)

        # Each session should only see its own facts
        assert len(results_a) == 1
        assert results_a[0]["key"] == "factA"

        assert len(results_b) == 1
        assert results_b[0]["key"] == "factB"


class TestEmbeddingDimensionHandling:
    """Test embedding padding and truncation."""

    @pytest.mark.asyncio
    async def test_embedding_padding(self, pg_writer) -> None:
        """Short embeddings are padded to target dimension (4096)."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # 128-dim embedding (will be padded to 4096)
        short_embedding = [0.5] * 128

        def mock_embedding_fn(text: str) -> list[float]:
            return short_embedding

        fact = SpanFact(key="test", value="v", turn=1)
        outcome = SessionOutcome(
            session_id="session-pad",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        # Should not raise - embedding will be padded
        count = await pg_writer.write_facts_with_embeddings(
            session_id="session-pad",
            turn=1,
            facts=[fact],
            outcome=outcome,
            embedding_fn=mock_embedding_fn,
        )

        assert count == 1

    @pytest.mark.asyncio
    async def test_embedding_truncation(self, pg_writer) -> None:
        """Long embeddings are truncated to target dimension (4096)."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # 5000-dim embedding (will be truncated to 4096)
        long_embedding = [0.3] * 5000

        def mock_embedding_fn(text: str) -> list[float]:
            return long_embedding

        fact = SpanFact(key="test", value="v", turn=1)
        outcome = SessionOutcome(
            session_id="session-trunc",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        # Should not raise - embedding will be truncated
        count = await pg_writer.write_facts_with_embeddings(
            session_id="session-trunc",
            turn=1,
            facts=[fact],
            outcome=outcome,
            embedding_fn=mock_embedding_fn,
        )

        assert count == 1

    @pytest.mark.asyncio
    async def test_exact_dimension_no_modification(self, pg_writer) -> None:
        """Embeddings with exact dimension (4096) are used as-is."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # Exact 4096-dim embedding
        exact_embedding = [0.2] * 4096

        def mock_embedding_fn(text: str) -> list[float]:
            return exact_embedding

        fact = SpanFact(key="test", value="v", turn=1)
        outcome = SessionOutcome(
            session_id="session-exact",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        count = await pg_writer.write_facts_with_embeddings(
            session_id="session-exact",
            turn=1,
            facts=[fact],
            outcome=outcome,
            embedding_fn=mock_embedding_fn,
        )

        assert count == 1


class TestSearchSimilarPadding:
    """Test that search also handles embedding dimension."""

    @pytest.mark.asyncio
    async def test_search_with_short_query_embedding(
        self, pg_writer, pg_store
    ) -> None:
        """Search pads short query embeddings to 4096."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # Write a fact with 128-dim embedding
        fact_embedding = [1.0] * 128

        def mock_embedding_fn(text: str) -> list[float]:
            return fact_embedding

        fact = SpanFact(key="test", value="v", turn=1)
        outcome = SessionOutcome(
            session_id="test-vector-session",
            outcome="SUCCEEDED",
            confidence_multiplier=1.0,
            method="context_db",
        )

        await pg_writer.write_facts_with_embeddings(
            session_id="test-vector-session",
            turn=1,
            facts=[fact],
            outcome=outcome,
            embedding_fn=mock_embedding_fn,
        )

        # Search with short embedding (should be padded internally)
        short_query = [1.0] * 64

        # Should not raise - query embedding will be padded
        results = await pg_store.search_similar(
            query_embedding=short_query,
            limit=10,
        )

        # Should find the fact (high similarity after padding)
        assert len(results) == 1
