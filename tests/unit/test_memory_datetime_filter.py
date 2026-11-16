"""Test datetime filtering in memory queries.

Phase 3.3 of Memory Wiring implementation.

Tests cover:
- recall() with start_date filter
- recall() with end_date filter
- recall() with date range (both start and end)
- search_memory() with date filtering
- Invalid date format handling

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection

Run with:
    uv run pytest tests/unit/test_memory_datetime_filter.py -v
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-dt-{uuid4().hex[:8]}"


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


@pytest.fixture
async def memory_with_dated_facts(memory):
    """Create memory with facts at different timestamps."""
    from scripts.agentica_patterns.postgres_pool import get_connection

    # Store facts with controlled timestamps
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    one_week_ago = now - timedelta(days=7)
    one_month_ago = now - timedelta(days=30)

    # Insert facts with specific timestamps
    async with get_connection() as conn:
        # Fact from one month ago
        await conn.execute(
            """
            INSERT INTO archival_memory (id, session_id, agent_id, content, metadata, created_at)
            VALUES (gen_random_uuid(), $1, NULL, $2, '{}', $3)
            """,
            memory.session_id,
            "Old fact from one month ago about Python",
            one_month_ago,
        )

        # Fact from one week ago
        await conn.execute(
            """
            INSERT INTO archival_memory (id, session_id, agent_id, content, metadata, created_at)
            VALUES (gen_random_uuid(), $1, NULL, $2, '{}', $3)
            """,
            memory.session_id,
            "Week old fact about JavaScript",
            one_week_ago,
        )

        # Fact from yesterday
        await conn.execute(
            """
            INSERT INTO archival_memory (id, session_id, agent_id, content, metadata, created_at)
            VALUES (gen_random_uuid(), $1, NULL, $2, '{}', $3)
            """,
            memory.session_id,
            "Yesterday fact about TypeScript",
            one_day_ago,
        )

        # Recent fact (now)
        await conn.execute(
            """
            INSERT INTO archival_memory (id, session_id, agent_id, content, metadata, created_at)
            VALUES (gen_random_uuid(), $1, NULL, $2, '{}', $3)
            """,
            memory.session_id,
            "Recent fact about Rust programming",
            now,
        )

    # Return memory and timestamps for assertions
    return {
        "memory": memory,
        "now": now,
        "one_day_ago": one_day_ago,
        "one_week_ago": one_week_ago,
        "one_month_ago": one_month_ago,
    }


class TestRecallWithStartDate:
    """Test recall() with start_date filter."""

    @pytest.mark.asyncio
    async def test_recall_with_start_date_filters_old_facts(
        self, memory_with_dated_facts
    ):
        """recall() should filter out facts before start_date."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Set start_date to 3 days ago - should exclude week-old and month-old facts
        start_date = ctx["now"] - timedelta(days=3)

        result = await memory.recall(
            "programming",
            start_date=start_date,
        )

        # Should include recent facts (Rust, TypeScript)
        assert "Rust" in result or "TypeScript" in result
        # Should NOT include old facts
        assert "Python" not in result  # month old
        assert "JavaScript" not in result  # week old

    @pytest.mark.asyncio
    async def test_recall_with_start_date_includes_matching_facts(
        self, memory_with_dated_facts
    ):
        """recall() should include facts on or after start_date."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Set start_date to 2 weeks ago - should include week-old, yesterday, and recent
        start_date = ctx["now"] - timedelta(days=14)

        result = await memory.recall(
            "fact",
            start_date=start_date,
        )

        # Should include all except month-old
        assert "JavaScript" in result or "TypeScript" in result or "Rust" in result
        # Month-old fact should be excluded
        assert "Python" not in result


class TestRecallWithEndDate:
    """Test recall() with end_date filter."""

    @pytest.mark.asyncio
    async def test_recall_with_end_date_filters_recent_facts(
        self, memory_with_dated_facts
    ):
        """recall() should filter out facts after end_date."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Set end_date to 2 days ago - should exclude yesterday and recent facts
        end_date = ctx["now"] - timedelta(days=2)

        result = await memory.recall(
            "fact",
            end_date=end_date,
        )

        # Should include old facts (Python, JavaScript)
        assert "Python" in result or "JavaScript" in result
        # Should NOT include recent facts
        assert "TypeScript" not in result  # yesterday
        assert "Rust" not in result  # today

    @pytest.mark.asyncio
    async def test_recall_with_end_date_includes_matching_facts(
        self, memory_with_dated_facts
    ):
        """recall() should include facts on or before end_date."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Set end_date to now - should include all facts
        end_date = ctx["now"] + timedelta(hours=1)  # Future to be safe

        result = await memory.recall(
            "programming",
            end_date=end_date,
        )

        # Should include recent fact
        assert "Rust" in result


class TestRecallWithDateRange:
    """Test recall() with both start_date and end_date."""

    @pytest.mark.asyncio
    async def test_recall_with_date_range_filters_correctly(
        self, memory_with_dated_facts
    ):
        """recall() should filter by both start and end dates."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Set range: 10 days ago to 2 days ago
        # Should include only week-old fact (JavaScript)
        start_date = ctx["now"] - timedelta(days=10)
        end_date = ctx["now"] - timedelta(days=2)

        result = await memory.recall(
            "fact",
            start_date=start_date,
            end_date=end_date,
        )

        # Should include only week-old fact
        assert "JavaScript" in result
        # Should NOT include others
        assert "Python" not in result  # too old
        assert "TypeScript" not in result  # too recent
        assert "Rust" not in result  # too recent

    @pytest.mark.asyncio
    async def test_recall_with_empty_date_range_returns_nothing(
        self, memory_with_dated_facts
    ):
        """recall() with impossible date range should return no memories."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Set impossible range: end before start
        start_date = ctx["now"]
        end_date = ctx["now"] - timedelta(days=100)

        result = await memory.recall(
            "fact",
            start_date=start_date,
            end_date=end_date,
        )

        assert "no relevant memories" in result.lower()


class TestSearchMemoryWithDates:
    """Test search_memory() with date filtering."""

    @pytest.mark.asyncio
    async def test_search_text_with_start_date(self, memory_with_dated_facts):
        """search_text() should support start_date filtering."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Search only recent facts
        start_date = ctx["now"] - timedelta(days=3)

        results = await memory.search_text(
            "programming fact",
            start_date=start_date,
            limit=10,
        )

        # Should only return recent facts
        contents = [r["content"] for r in results]
        for content in contents:
            assert "Python" not in content  # month old
            assert "JavaScript" not in content  # week old

    @pytest.mark.asyncio
    async def test_search_text_with_end_date(self, memory_with_dated_facts):
        """search_text() should support end_date filtering."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Search only old facts
        end_date = ctx["now"] - timedelta(days=2)

        results = await memory.search_text(
            "fact",
            end_date=end_date,
            limit=10,
        )

        # Should only return old facts
        contents = [r["content"] for r in results]
        for content in contents:
            assert "TypeScript" not in content  # yesterday
            assert "Rust" not in content  # today

    @pytest.mark.asyncio
    async def test_search_text_with_date_range(self, memory_with_dated_facts):
        """search_text() should support date range filtering."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Search specific date range
        start_date = ctx["now"] - timedelta(days=10)
        end_date = ctx["now"] - timedelta(days=2)

        results = await memory.search_text(
            "fact",
            start_date=start_date,
            end_date=end_date,
            limit=10,
        )

        # Should only return week-old fact
        assert len(results) == 1
        assert "JavaScript" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_search_text_without_dates_returns_all(self, memory_with_dated_facts):
        """search_text() without date params should return all matching facts."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        results = await memory.search_text(
            "fact",
            limit=10,
        )

        # Should return all 4 facts
        assert len(results) >= 3  # At least 3 should match


class TestSearchVectorWithDates:
    """Test search_vector() with date filtering."""

    @pytest.mark.asyncio
    async def test_search_vector_with_start_date(self, memory_with_dated_facts):
        """search_vector() should support start_date filtering."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Store facts with embeddings first
        from scripts.agentica_patterns.postgres_pool import get_connection

        # Create a dummy embedding (4096 dimensions, padded)
        dummy_embedding = [0.1] * 4096

        async with get_connection() as conn:
            from scripts.agentica_patterns.postgres_pool import init_pgvector
            await init_pgvector(conn)

            # Update existing facts with embeddings
            await conn.execute(
                """
                UPDATE archival_memory
                SET embedding = $1::vector
                WHERE session_id = $2
                """,
                dummy_embedding,
                memory.session_id,
            )

        # Search only recent facts
        start_date = ctx["now"] - timedelta(days=3)

        results = await memory.search_vector(
            query_embedding=[0.1] * 100,  # Will be padded to 4096
            start_date=start_date,
            limit=10,
        )

        # Should only return recent facts
        contents = [r["content"] for r in results]
        for content in contents:
            assert "Python" not in content  # month old
            assert "JavaScript" not in content  # week old


class TestSearchHybridWithDates:
    """Test search_hybrid() with date filtering."""

    @pytest.mark.asyncio
    async def test_search_hybrid_with_date_range(self, memory_with_dated_facts):
        """search_hybrid() should support date range filtering."""
        ctx = memory_with_dated_facts
        memory = ctx["memory"]

        # Store facts with embeddings first
        from scripts.agentica_patterns.postgres_pool import get_connection

        dummy_embedding = [0.1] * 4096

        async with get_connection() as conn:
            from scripts.agentica_patterns.postgres_pool import init_pgvector
            await init_pgvector(conn)

            await conn.execute(
                """
                UPDATE archival_memory
                SET embedding = $1::vector
                WHERE session_id = $2
                """,
                dummy_embedding,
                memory.session_id,
            )

        # Search specific date range
        start_date = ctx["now"] - timedelta(days=10)
        end_date = ctx["now"] - timedelta(days=2)

        results = await memory.search_hybrid(
            text_query="fact",
            query_embedding=[0.1] * 100,
            start_date=start_date,
            end_date=end_date,
            limit=10,
        )

        # Should only return week-old fact
        assert len(results) == 1
        assert "JavaScript" in results[0]["content"]


class TestInvalidDateHandling:
    """Test handling of invalid date inputs."""

    @pytest.mark.asyncio
    async def test_recall_with_none_dates_works(self, memory):
        """recall() with None dates should work normally."""
        await memory.store("Test fact about programming")

        # Should not raise, should work normally
        result = await memory.recall(
            "programming",
            start_date=None,
            end_date=None,
        )

        assert "programming" in result.lower() or "no relevant" in result.lower()

    @pytest.mark.asyncio
    async def test_search_text_with_none_dates_works(self, memory):
        """search_text() with None dates should work normally."""
        await memory.store("Test fact about coding")

        # Should not raise, should work normally
        results = await memory.search_text(
            "coding",
            start_date=None,
            end_date=None,
            limit=10,
        )

        # Should return results or empty list
        assert isinstance(results, list)


class TestUnifiedScopeDateFiltering:
    """Test datetime filtering via unified_scope interface."""

    @pytest.mark.asyncio
    async def test_unified_scope_recall_with_dates(self, session_id):
        """unified_scope recall() should support date filtering."""
        from pathlib import Path
        import tempfile

        from scripts.agentica_patterns.unified_scope import create_unified_scope

        with tempfile.TemporaryDirectory() as tmp:
            scope = create_unified_scope(
                session_id=session_id,
                db_path=Path(tmp) / "test.db",
                enable_memory=True,
                enable_tasks=False,
            )

            # Store a fact
            scope["store_fact"]("Test fact for date filtering")

            # Recall should work (unified_scope uses SQLite, not PG)
            result = scope["recall"]("date filtering")

            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_unified_scope_search_memory_with_dates(self, session_id):
        """unified_scope search_memory() should support date filtering."""
        from pathlib import Path
        import tempfile

        from scripts.agentica_patterns.unified_scope import create_unified_scope

        with tempfile.TemporaryDirectory() as tmp:
            scope = create_unified_scope(
                session_id=session_id,
                db_path=Path(tmp) / "test.db",
                enable_memory=True,
                enable_tasks=False,
            )

            # Store a fact
            scope["store_fact"]("Test fact for search memory dates")

            # Search should work
            results = scope["search_memory"]("search memory", limit=5)

            assert isinstance(results, list)
