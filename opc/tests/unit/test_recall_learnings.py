"""Unit tests for recall_learnings.py search functions.

Tests cover:
- search_learnings_text_only_postgres: OR semantics, stopword removal, ILIKE fallback
- search_learnings_hybrid_rrf: RRF score calculation, threshold filtering
- search_learnings_postgres: Vector search, recency boost
- search_learnings: Backend selection, empty query handling
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.conftest import MockEmbeddingService, MockRecord, make_db_row, make_learning


class TestGetBackend:
    """Tests for backend selection logic."""

    def test_explicit_sqlite_backend(self, monkeypatch):
        """Explicit AGENTICA_MEMORY_BACKEND=sqlite wins."""
        monkeypatch.setenv("AGENTICA_MEMORY_BACKEND", "sqlite")
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")

        from scripts.core.recall_learnings import get_backend
        assert get_backend() == "sqlite"

    def test_explicit_postgres_backend(self, monkeypatch):
        """Explicit AGENTICA_MEMORY_BACKEND=postgres wins."""
        monkeypatch.setenv("AGENTICA_MEMORY_BACKEND", "postgres")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        from scripts.core.recall_learnings import get_backend
        assert get_backend() == "postgres"

    def test_database_url_implies_postgres(self, monkeypatch):
        """DATABASE_URL present implies postgres backend."""
        monkeypatch.delenv("AGENTICA_MEMORY_BACKEND", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")

        from scripts.core.recall_learnings import get_backend
        assert get_backend() == "postgres"

    def test_continuous_claude_db_url_implies_postgres(self, monkeypatch):
        """CONTINUOUS_CLAUDE_DB_URL present implies postgres backend."""
        monkeypatch.delenv("AGENTICA_MEMORY_BACKEND", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("CONTINUOUS_CLAUDE_DB_URL", "postgresql://localhost/db")

        from scripts.core.recall_learnings import get_backend
        assert get_backend() == "postgres"

    def test_default_is_sqlite(self, monkeypatch):
        """No env vars defaults to sqlite."""
        monkeypatch.delenv("AGENTICA_MEMORY_BACKEND", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("CONTINUOUS_CLAUDE_DB_URL", raising=False)

        from scripts.core.recall_learnings import get_backend
        assert get_backend() == "sqlite"


class TestSearchLearnings:
    """Tests for the main search_learnings dispatcher."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self, monkeypatch):
        """Verify empty query returns empty list without calling backend."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")

        from scripts.core.recall_learnings import search_learnings
        results = await search_learnings("", k=5)
        assert results == []

        results = await search_learnings("   ", k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_sqlite_backend_selection(self, monkeypatch, tmp_path):
        """Verify SQLite backend is used when configured."""
        monkeypatch.setenv("AGENTICA_MEMORY_BACKEND", "sqlite")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        db_path = tmp_path / "memory.db"

        with patch("scripts.core.recall_learnings.search_learnings_sqlite", new_callable=AsyncMock) as mock_sqlite:
            mock_sqlite.return_value = []
            from scripts.core.recall_learnings import search_learnings
            await search_learnings("test query", k=5)

        mock_sqlite.assert_called_once_with("test query", 5)

    @pytest.mark.asyncio
    async def test_postgres_backend_selection(self, monkeypatch):
        """Verify PostgreSQL backend is used when configured."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
        monkeypatch.delenv("AGENTICA_MEMORY_BACKEND", raising=False)

        with patch("scripts.core.recall_learnings.search_learnings_postgres", new_callable=AsyncMock) as mock_pg:
            mock_pg.return_value = []
            from scripts.core.recall_learnings import search_learnings
            await search_learnings("test query", k=5)

        mock_pg.assert_called_once()


class TestFormatResultPreview:
    """Tests for result preview formatting."""

    def test_short_content_unchanged(self):
        """Content under max_length is returned unchanged."""
        from scripts.core.recall_learnings import format_result_preview
        content = "Short content"
        assert format_result_preview(content, 200) == content

    def test_long_content_truncated(self):
        """Content over max_length is truncated with ellipsis."""
        from scripts.core.recall_learnings import format_result_preview
        content = "A" * 300
        result = format_result_preview(content, 200)
        assert len(result) == 203
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        """Content exactly at max_length is unchanged."""
        from scripts.core.recall_learnings import format_result_preview
        content = "A" * 200
        assert format_result_preview(content, 200) == content


class TestSearchLearningsTextOnlyPostgres:
    """Tests for text-only PostgreSQL search.

    These tests verify the query-building logic in isolation
    by mocking the database pool.
    """

    @pytest.fixture
    def mock_db_pool(self):
        """Create a mock pool with async context manager support."""
        pool = MagicMock()
        conn = AsyncMock()

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = cm

        return pool, conn

    @pytest.mark.asyncio
    async def test_or_semantics_query_building(self, mock_db_pool, sample_learnings):
        """Verify OR-based query construction from search terms."""
        pool, conn = mock_db_pool
        rows = [make_db_row(sample_learnings[0])]
        conn.fetch = AsyncMock(return_value=rows)

        async def mock_get_pool():
            return pool

        with patch("db.postgres_pool.get_pool", mock_get_pool):
            from scripts.core.recall_learnings import search_learnings_text_only_postgres
            results = await search_learnings_text_only_postgres("typescript hooks", k=5)

        call_args = conn.fetch.call_args
        query_arg = call_args[0][1]
        assert "|" in query_arg

    @pytest.mark.asyncio
    async def test_stopword_removal(self, mock_db_pool, sample_learnings):
        """Verify meta-words are stripped from query."""
        pool, conn = mock_db_pool
        rows = [make_db_row(sample_learnings[0])]
        conn.fetch = AsyncMock(return_value=rows)

        async def mock_get_pool():
            return pool

        with patch("db.postgres_pool.get_pool", mock_get_pool):
            from scripts.core.recall_learnings import search_learnings_text_only_postgres
            await search_learnings_text_only_postgres("help me find typescript", k=5)

        call_args = conn.fetch.call_args
        query_arg = call_args[0][1]
        assert "help" not in query_arg.lower()
        assert "find" not in query_arg.lower()
        assert "typescript" in query_arg.lower()

    @pytest.mark.asyncio
    async def test_ilike_fallback_when_no_fts_results(self, mock_db_pool, sample_learnings):
        """Verify ILIKE fallback when FTS returns empty."""
        pool, conn = mock_db_pool
        rows = [make_db_row(sample_learnings[0])]
        conn.fetch = AsyncMock(side_effect=[[], rows])

        async def mock_get_pool():
            return pool

        with patch("db.postgres_pool.get_pool", mock_get_pool):
            from scripts.core.recall_learnings import search_learnings_text_only_postgres
            results = await search_learnings_text_only_postgres("rare_term", k=5)

        assert conn.fetch.call_count == 2
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_hyphen_normalization(self, mock_db_pool, sample_learnings):
        """Verify hyphenated terms are split for matching."""
        pool, conn = mock_db_pool
        rows = [make_db_row(sample_learnings[1])]
        conn.fetch = AsyncMock(return_value=rows)

        async def mock_get_pool():
            return pool

        with patch("db.postgres_pool.get_pool", mock_get_pool):
            from scripts.core.recall_learnings import search_learnings_text_only_postgres
            await search_learnings_text_only_postgres("multi-terminal", k=5)

        call_args = conn.fetch.call_args
        query_arg = call_args[0][1]
        assert "multi" in query_arg.lower()
        assert "terminal" in query_arg.lower()

    @pytest.mark.asyncio
    async def test_result_structure(self, mock_db_pool, sample_learnings):
        """Verify returned results have correct structure."""
        pool, conn = mock_db_pool
        rows = [make_db_row(sample_learnings[0])]
        conn.fetch = AsyncMock(return_value=rows)

        async def mock_get_pool():
            return pool

        with patch("db.postgres_pool.get_pool", mock_get_pool):
            from scripts.core.recall_learnings import search_learnings_text_only_postgres
            results = await search_learnings_text_only_postgres("typescript", k=5)

        assert len(results) == 1
        result = results[0]
        assert "id" in result
        assert "session_id" in result
        assert "content" in result
        assert "metadata" in result
        assert "created_at" in result
        assert "similarity" in result


class TestSearchLearningsHybridRRF:
    """Tests for hybrid RRF search combining text and vector."""

    @pytest.fixture
    def mock_db_pool(self):
        """Create a mock pool with async context manager support."""
        pool = MagicMock()
        conn = AsyncMock()

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = cm

        return pool, conn

    @pytest.mark.asyncio
    async def test_rrf_score_calculation(self, mock_db_pool, sample_learnings):
        """Verify RRF scores are calculated correctly."""
        pool, conn = mock_db_pool
        rrf_row = MockRecord({
            "id": sample_learnings[0]["id"],
            "session_id": sample_learnings[0]["session_id"],
            "content": sample_learnings[0]["content"],
            "metadata": json.dumps(sample_learnings[0]["metadata"]),
            "created_at": sample_learnings[0]["created_at"],
            "rrf_score": 0.032,
            "fts_rank": 1,
            "vec_rank": 2,
        })
        conn.fetch = AsyncMock(return_value=[rrf_row])

        mock_embedder = MockEmbeddingService()

        async def mock_get_pool():
            return pool

        async def mock_init_pgvector(conn):
            pass

        with patch("db.postgres_pool.get_pool", mock_get_pool), \
             patch("db.postgres_pool.init_pgvector", mock_init_pgvector), \
             patch("db.embedding_service.EmbeddingService", return_value=mock_embedder):
            from scripts.core.recall_learnings import search_learnings_hybrid_rrf
            results = await search_learnings_hybrid_rrf("typescript hooks", k=5)

        assert len(results) == 1
        assert results[0]["similarity"] == 0.032
        assert results[0]["fts_rank"] == 1
        assert results[0]["vec_rank"] == 2

    @pytest.mark.asyncio
    async def test_threshold_filtering(self, mock_db_pool, sample_learnings):
        """Verify results below threshold are filtered out."""
        pool, conn = mock_db_pool
        rows = [
            MockRecord({
                "id": sample_learnings[0]["id"],
                "session_id": sample_learnings[0]["session_id"],
                "content": sample_learnings[0]["content"],
                "metadata": json.dumps(sample_learnings[0]["metadata"]),
                "created_at": sample_learnings[0]["created_at"],
                "rrf_score": 0.03,
                "fts_rank": 1,
                "vec_rank": 1,
            }),
            MockRecord({
                "id": sample_learnings[1]["id"],
                "session_id": sample_learnings[1]["session_id"],
                "content": sample_learnings[1]["content"],
                "metadata": json.dumps(sample_learnings[1]["metadata"]),
                "created_at": sample_learnings[1]["created_at"],
                "rrf_score": 0.005,
                "fts_rank": 10,
                "vec_rank": 10,
            }),
        ]
        conn.fetch = AsyncMock(return_value=rows)

        mock_embedder = MockEmbeddingService()

        async def mock_get_pool():
            return pool

        async def mock_init_pgvector(conn):
            pass

        with patch("db.postgres_pool.get_pool", mock_get_pool), \
             patch("db.postgres_pool.init_pgvector", mock_init_pgvector), \
             patch("db.embedding_service.EmbeddingService", return_value=mock_embedder):
            from scripts.core.recall_learnings import search_learnings_hybrid_rrf
            results = await search_learnings_hybrid_rrf(
                "typescript", k=5, similarity_threshold=0.01
            )

        assert len(results) == 1
        assert results[0]["similarity"] >= 0.01


class TestSearchLearningsPostgres:
    """Tests for PostgreSQL vector search."""

    @pytest.fixture
    def mock_db_pool(self):
        """Create a mock pool with async context manager support."""
        pool = MagicMock()
        conn = AsyncMock()

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = cm

        return pool, conn

    @pytest.mark.asyncio
    async def test_vector_search_with_embeddings(self, mock_db_pool, sample_learnings):
        """Verify vector search when embeddings exist."""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"cnt": 5})
        rows = [make_db_row(sample_learnings[0])]
        conn.fetch = AsyncMock(return_value=rows)

        mock_embedder = MockEmbeddingService()

        async def mock_get_pool():
            return pool

        async def mock_init_pgvector(conn):
            pass

        with patch("db.postgres_pool.get_pool", mock_get_pool), \
             patch("db.postgres_pool.init_pgvector", mock_init_pgvector), \
             patch("db.embedding_service.EmbeddingService", return_value=mock_embedder):
            from scripts.core.recall_learnings import search_learnings_postgres
            results = await search_learnings_postgres("typescript", k=5)

        assert len(results) == 1
        assert mock_embedder.calls == ["typescript"]

    @pytest.mark.asyncio
    async def test_text_fallback_when_no_embeddings(self, mock_db_pool, sample_learnings):
        """Verify ILIKE fallback when no embeddings in database."""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"cnt": 0})
        rows = [make_db_row(sample_learnings[0], similarity=0.5)]
        conn.fetch = AsyncMock(return_value=rows)

        async def mock_get_pool():
            return pool

        with patch("db.postgres_pool.get_pool", mock_get_pool):
            from scripts.core.recall_learnings import search_learnings_postgres
            results = await search_learnings_postgres("typescript", k=5, text_fallback=True)

        assert len(results) == 1
        assert results[0]["similarity"] == 0.5

    @pytest.mark.asyncio
    async def test_no_results_when_fallback_disabled(self, mock_db_pool):
        """Verify empty results when text_fallback=False and no embeddings."""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"cnt": 0})

        async def mock_get_pool():
            return pool

        with patch("db.postgres_pool.get_pool", mock_get_pool):
            from scripts.core.recall_learnings import search_learnings_postgres
            results = await search_learnings_postgres("typescript", k=5, text_fallback=False)

        assert results == []

    @pytest.mark.asyncio
    async def test_recency_boost(self, mock_db_pool, sample_learnings):
        """Verify recency weight affects scoring."""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"cnt": 5})
        row = MockRecord({
            "id": sample_learnings[0]["id"],
            "session_id": sample_learnings[0]["session_id"],
            "content": sample_learnings[0]["content"],
            "metadata": json.dumps(sample_learnings[0]["metadata"]),
            "created_at": sample_learnings[0]["created_at"],
            "similarity": 0.7,
            "recency": 0.9,
            "combined_score": 0.74,
        })
        conn.fetch = AsyncMock(return_value=[row])

        mock_embedder = MockEmbeddingService()

        async def mock_get_pool():
            return pool

        async def mock_init_pgvector(conn):
            pass

        with patch("db.postgres_pool.get_pool", mock_get_pool), \
             patch("db.postgres_pool.init_pgvector", mock_init_pgvector), \
             patch("db.embedding_service.EmbeddingService", return_value=mock_embedder):
            from scripts.core.recall_learnings import search_learnings_postgres
            results = await search_learnings_postgres("typescript", k=5, recency_weight=0.2)

        assert len(results) == 1
        assert results[0]["similarity"] == 0.74
        assert "raw_similarity" in results[0]
        assert "recency" in results[0]
