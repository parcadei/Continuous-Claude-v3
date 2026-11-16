"""Unit tests for tag filtering in memory (Phase 3.4: TDD).

Tests for:
- Storing facts with tags
- Searching with tag filtering (any mode - OR)
- Searching with tag filtering (all mode - AND)
- Tag CRUD operations
- Empty tags behavior

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection

Run with:
    uv run pytest tests/unit/test_memory_tags.py -v
"""

import asyncio
from uuid import uuid4

import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-tags-{uuid4().hex[:8]}"


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
            "DELETE FROM memory_tags WHERE session_id = $1", session_id
        )
        await conn.execute(
            "DELETE FROM archival_memory WHERE session_id = $1", session_id
        )
        await conn.execute(
            "DELETE FROM core_memory WHERE session_id = $1", session_id
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
            await conn.execute("DELETE FROM memory_tags WHERE session_id = $1", sid)
            await conn.execute("DELETE FROM archival_memory WHERE session_id = $1", sid)
            await conn.execute("DELETE FROM core_memory WHERE session_id = $1", sid)


class TestStoreFactWithTags:
    """Test storing facts with tags."""

    @pytest.mark.asyncio
    async def test_store_fact_with_single_tag(self, memory):
        """store() should accept tags parameter and store tags."""
        memory_id = await memory.store(
            "User prefers Python for data science",
            tags=["preference"],
        )

        assert memory_id is not None
        assert len(memory_id) == 36  # UUID format

        # Verify tags were stored
        tags = await memory.get_tags(memory_id)
        assert "preference" in tags

    @pytest.mark.asyncio
    async def test_store_fact_with_multiple_tags(self, memory):
        """store() should accept multiple tags."""
        memory_id = await memory.store(
            "Important project deadline is next Friday",
            tags=["important", "deadline", "project"],
        )

        tags = await memory.get_tags(memory_id)
        assert len(tags) == 3
        assert "important" in tags
        assert "deadline" in tags
        assert "project" in tags

    @pytest.mark.asyncio
    async def test_store_fact_without_tags(self, memory):
        """store() without tags should work as before."""
        memory_id = await memory.store("A simple fact without tags")

        assert memory_id is not None
        tags = await memory.get_tags(memory_id)
        assert len(tags) == 0

    @pytest.mark.asyncio
    async def test_store_fact_with_empty_tags_list(self, memory):
        """store() with empty tags list should work."""
        memory_id = await memory.store(
            "Fact with empty tags list",
            tags=[],
        )

        assert memory_id is not None
        tags = await memory.get_tags(memory_id)
        assert len(tags) == 0

    @pytest.mark.asyncio
    async def test_store_fact_duplicate_tags_deduplicated(self, memory):
        """Duplicate tags should be deduplicated."""
        memory_id = await memory.store(
            "Fact with duplicate tags",
            tags=["important", "important", "urgent"],
        )

        tags = await memory.get_tags(memory_id)
        assert len(tags) == 2
        assert "important" in tags
        assert "urgent" in tags


class TestRecallFilterTagsAny:
    """Test recall() with tags and tag_match_mode='any' (OR logic)."""

    @pytest.mark.asyncio
    async def test_recall_filter_tags_any_single_tag(self, memory):
        """recall() with single tag should return matching facts."""
        await memory.store("Python is great for ML", tags=["python", "ml"])
        await memory.store("JavaScript for web dev", tags=["javascript", "web"])
        await memory.store("Rust for systems", tags=["rust", "systems"])

        results = await memory.search_with_tags(
            query="great",
            tags=["python"],
            tag_match_mode="any",
            limit=10,
        )

        # Should only return facts tagged with "python"
        assert len(results) >= 1
        assert any("Python" in r["content"] for r in results)
        assert not any("JavaScript" in r["content"] for r in results)

    @pytest.mark.asyncio
    async def test_recall_filter_tags_any_multiple_tags(self, memory):
        """recall() with multiple tags in 'any' mode returns OR matches."""
        await memory.store("Python data science rocks", tags=["python", "data"])
        await memory.store("JavaScript frontend rocks", tags=["javascript", "frontend"])
        await memory.store("Rust backend rocks", tags=["rust", "backend"])

        results = await memory.search_with_tags(
            query="rocks",
            tags=["python", "rust"],
            tag_match_mode="any",
            limit=10,
        )

        # Should return facts tagged with python OR rust
        contents = [r["content"] for r in results]
        assert any("Python" in c for c in contents) or any("Rust" in c for c in contents)
        # JavaScript should not be included
        assert not any("JavaScript" in c for c in contents)

    @pytest.mark.asyncio
    async def test_recall_filter_tags_any_no_matches(self, memory):
        """recall() with non-matching tags returns empty."""
        await memory.store("Python fact", tags=["python"])

        results = await memory.search_with_tags(
            query="Python",
            tags=["nonexistent_tag"],
            tag_match_mode="any",
            limit=10,
        )

        assert len(results) == 0


class TestRecallFilterTagsAll:
    """Test recall() with tags and tag_match_mode='all' (AND logic)."""

    @pytest.mark.asyncio
    async def test_recall_filter_tags_all_requires_all(self, memory):
        """recall() with 'all' mode requires ALL specified tags."""
        await memory.store("Python ML project", tags=["python", "ml", "project"])
        await memory.store("Python web project", tags=["python", "web", "project"])
        await memory.store("JavaScript project", tags=["javascript", "project"])

        results = await memory.search_with_tags(
            query="project",
            tags=["python", "ml"],
            tag_match_mode="all",
            limit=10,
        )

        # Should only return facts with BOTH python AND ml tags
        assert len(results) == 1
        assert "ML" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_recall_filter_tags_all_partial_match_excluded(self, memory):
        """Facts with only some tags should be excluded in 'all' mode."""
        await memory.store("Partial match fact", tags=["tag1"])

        results = await memory.search_with_tags(
            query="match",
            tags=["tag1", "tag2"],
            tag_match_mode="all",
            limit=10,
        )

        # Should not return the fact since it only has tag1, not tag2
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_recall_filter_tags_all_with_extra_tags(self, memory):
        """Facts with extra tags should still match if they have all required tags."""
        await memory.store(
            "Full match with extras",
            tags=["required1", "required2", "extra"],
        )

        results = await memory.search_with_tags(
            query="match",
            tags=["required1", "required2"],
            tag_match_mode="all",
            limit=10,
        )

        # Should return the fact since it has both required tags
        assert len(results) == 1
        assert "Full match" in results[0]["content"]


class TestSearchMemoryWithTags:
    """Test search_memory() with tag filtering."""

    @pytest.mark.asyncio
    async def test_search_memory_with_tags_integration(self, memory):
        """search() alias should support tag filtering."""
        await memory.store("Important meeting notes", tags=["meeting", "important"])
        await memory.store("Casual chat notes", tags=["chat"])

        # Using search_with_tags directly
        results = await memory.search_with_tags(
            query="notes",
            tags=["important"],
            tag_match_mode="any",
            limit=10,
        )

        assert len(results) == 1
        assert "Important" in results[0]["content"]


class TestEmptyTagsReturnsAll:
    """Test that empty tags list returns all matching results."""

    @pytest.mark.asyncio
    async def test_empty_tags_returns_all_fts_matches(self, memory):
        """Empty tags list should return all FTS matches."""
        await memory.store("Python fact one", tags=["python"])
        await memory.store("Python fact two", tags=["different"])
        await memory.store("Python fact three")  # No tags

        results = await memory.search_with_tags(
            query="Python",
            tags=[],
            tag_match_mode="any",
            limit=10,
        )

        # Should return all Python facts regardless of tags
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_none_tags_returns_all_fts_matches(self, memory):
        """None tags should return all FTS matches."""
        await memory.store("Test fact one", tags=["tag1"])
        await memory.store("Test fact two", tags=["tag2"])

        results = await memory.search_with_tags(
            query="Test",
            tags=None,
            tag_match_mode="any",
            limit=10,
        )

        # Should return all matching facts
        assert len(results) == 2


class TestTagCRUD:
    """Test tag CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_tags_for_memory(self, memory):
        """get_tags() should return tags for a memory ID."""
        memory_id = await memory.store("Tagged fact", tags=["tag1", "tag2"])

        tags = await memory.get_tags(memory_id)

        assert set(tags) == {"tag1", "tag2"}

    @pytest.mark.asyncio
    async def test_add_tag_to_existing_memory(self, memory):
        """add_tag() should add a tag to existing memory."""
        memory_id = await memory.store("Fact to tag", tags=["initial"])

        await memory.add_tag(memory_id, "new_tag")

        tags = await memory.get_tags(memory_id)
        assert "initial" in tags
        assert "new_tag" in tags

    @pytest.mark.asyncio
    async def test_remove_tag_from_memory(self, memory):
        """remove_tag() should remove a tag from memory."""
        memory_id = await memory.store("Fact with tags", tags=["keep", "remove"])

        await memory.remove_tag(memory_id, "remove")

        tags = await memory.get_tags(memory_id)
        assert "keep" in tags
        assert "remove" not in tags

    @pytest.mark.asyncio
    async def test_get_all_tags_for_session(self, memory, session_id):
        """get_all_session_tags() should return all unique tags in session."""
        await memory.store("Fact 1", tags=["tag_a", "tag_b"])
        await memory.store("Fact 2", tags=["tag_b", "tag_c"])
        await memory.store("Fact 3", tags=["tag_a", "tag_d"])

        all_tags = await memory.get_all_session_tags()

        assert set(all_tags) == {"tag_a", "tag_b", "tag_c", "tag_d"}


class TestTagSessionIsolation:
    """Test that tags are isolated between sessions."""

    @pytest.mark.asyncio
    async def test_tags_isolated_between_sessions(self, cleanup_session):
        """Tags should be isolated between different sessions."""
        from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

        session1 = unique_session_id()
        session2 = unique_session_id()
        cleanup_session(session1)
        cleanup_session(session2)

        memory1 = MemoryServicePG(session_id=session1)
        memory2 = MemoryServicePG(session_id=session2)
        await memory1.connect()
        await memory2.connect()

        # Store in session1 with tags
        await memory1.store("Session1 fact", tags=["session1_tag"])

        # Store in session2 with different tags
        await memory2.store("Session2 fact", tags=["session2_tag"])

        # Session1 should only see its tags
        tags1 = await memory1.get_all_session_tags()
        assert "session1_tag" in tags1
        assert "session2_tag" not in tags1

        # Session2 should only see its tags
        tags2 = await memory2.get_all_session_tags()
        assert "session2_tag" in tags2
        assert "session1_tag" not in tags2

    @pytest.mark.asyncio
    async def test_search_with_tags_respects_session(self, cleanup_session):
        """search_with_tags should only search within session."""
        from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

        session1 = unique_session_id()
        session2 = unique_session_id()
        cleanup_session(session1)
        cleanup_session(session2)

        memory1 = MemoryServicePG(session_id=session1)
        memory2 = MemoryServicePG(session_id=session2)
        await memory1.connect()
        await memory2.connect()

        # Both sessions store facts with same tag
        await memory1.store("Session1 Python fact", tags=["python"])
        await memory2.store("Session2 Python fact", tags=["python"])

        # Session1 search should only return session1 results
        results1 = await memory1.search_with_tags(
            query="Python",
            tags=["python"],
            tag_match_mode="any",
            limit=10,
        )
        assert len(results1) == 1
        assert "Session1" in results1[0]["content"]

        # Session2 search should only return session2 results
        results2 = await memory2.search_with_tags(
            query="Python",
            tags=["python"],
            tag_match_mode="any",
            limit=10,
        )
        assert len(results2) == 1
        assert "Session2" in results2[0]["content"]


class TestTagCascadeDelete:
    """Test that tags are deleted when memory is deleted."""

    @pytest.mark.asyncio
    async def test_tags_deleted_with_memory(self, memory):
        """Tags should be deleted when memory is deleted (CASCADE)."""
        memory_id = await memory.store("Fact to delete", tags=["tag1", "tag2"])

        # Verify tags exist
        tags_before = await memory.get_tags(memory_id)
        assert len(tags_before) == 2

        # Delete the memory
        await memory.delete_archival(memory_id)

        # Tags should be gone (CASCADE DELETE)
        tags_after = await memory.get_tags(memory_id)
        assert len(tags_after) == 0
