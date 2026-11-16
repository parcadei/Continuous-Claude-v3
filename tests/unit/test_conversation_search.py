"""Test conversation search functionality (Phase 3.6).

Tests cover:
- store_message: Store conversation messages with role
- conversation_search: Search messages with FTS
- Role filtering: Filter by user/assistant/tool
- Date filtering: Filter by datetime range
- Pagination: Support limit and offset
- Hybrid search: FTS + vector similarity

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection
- Migration 004_add_messages_table.sql applied

Run with:
    uv run pytest tests/unit/test_conversation_search.py -v
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-msg-{uuid4().hex[:8]}"


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
async def message_service(session_id):
    """Create a MessageMemoryService instance for testing."""
    from scripts.agentica_patterns.message_memory import MessageMemoryService
    from scripts.agentica_patterns.postgres_pool import get_connection

    service = MessageMemoryService(session_id=session_id)
    yield service

    # Cleanup after test
    async with get_connection() as conn:
        await conn.execute(
            "DELETE FROM memory_messages WHERE session_id = $1", session_id
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
            await conn.execute(
                "DELETE FROM memory_messages WHERE session_id = $1", sid
            )


class TestStoreMessage:
    """Test message storage operations."""

    @pytest.mark.asyncio
    async def test_store_message_returns_id(self, message_service):
        """store_message() should return a UUID for the stored message."""
        msg_id = await message_service.store_message(
            content="Hello, how can I help you?",
            role="assistant",
        )

        assert msg_id is not None
        # UUID format (36 chars with hyphens)
        assert len(msg_id) == 36

    @pytest.mark.asyncio
    async def test_store_message_user_role(self, message_service):
        """store_message() should accept user role."""
        msg_id = await message_service.store_message(
            content="I need help with Python",
            role="user",
        )

        assert msg_id is not None

    @pytest.mark.asyncio
    async def test_store_message_tool_role(self, message_service):
        """store_message() should accept tool role."""
        msg_id = await message_service.store_message(
            content="[Tool output: file contents...]",
            role="tool",
        )

        assert msg_id is not None

    @pytest.mark.asyncio
    async def test_store_message_invalid_role(self, message_service):
        """store_message() should reject invalid roles."""
        with pytest.raises((ValueError, Exception)):  # Could be DB constraint error
            await message_service.store_message(
                content="Invalid message",
                role="invalid_role",
            )

    @pytest.mark.asyncio
    async def test_store_message_with_agent_id(self, session_id):
        """store_message() should store agent_id when provided."""
        from scripts.agentica_patterns.message_memory import MessageMemoryService
        from scripts.agentica_patterns.postgres_pool import get_connection

        service = MessageMemoryService(session_id=session_id, agent_id="agent-123")
        msg_id = await service.store_message(
            content="Message from specific agent",
            role="assistant",
        )

        # Verify agent_id was stored
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT agent_id FROM memory_messages WHERE id = $1",
                msg_id,
            )
            assert row["agent_id"] == "agent-123"

        # Cleanup
        async with get_connection() as conn:
            await conn.execute(
                "DELETE FROM memory_messages WHERE session_id = $1", session_id
            )


class TestConversationSearchBasic:
    """Test basic conversation search functionality."""

    @pytest.mark.asyncio
    async def test_conversation_search_finds_message(self, message_service):
        """conversation_search() should find messages by query."""
        await message_service.store_message(
            content="Python is great for data science",
            role="assistant",
        )

        results = await message_service.conversation_search("Python", limit=10)

        assert len(results) >= 1
        assert any("Python" in r["content"] for r in results)

    @pytest.mark.asyncio
    async def test_conversation_search_returns_correct_fields(self, message_service):
        """conversation_search() results should have expected fields."""
        await message_service.store_message(
            content="Testing field structure",
            role="user",
        )

        results = await message_service.conversation_search("Testing", limit=10)

        assert len(results) >= 1
        result = results[0]
        assert "id" in result
        assert "content" in result
        assert "role" in result
        assert "created_at" in result
        assert "score" in result

    @pytest.mark.asyncio
    async def test_conversation_search_no_results(self, message_service):
        """conversation_search() should return empty list when no matches."""
        await message_service.store_message(
            content="Some unrelated content",
            role="user",
        )

        results = await message_service.conversation_search(
            "nonexistent_xyz_query", limit=10
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_conversation_search_ranked_by_relevance(self, message_service):
        """conversation_search() results should be ranked by relevance."""
        await message_service.store_message(
            content="Python is a programming language",
            role="assistant",
        )
        await message_service.store_message(
            content="Python is excellent for machine learning and Python AI development",
            role="assistant",
        )
        await message_service.store_message(
            content="The snake python lives in tropical regions",
            role="assistant",
        )

        results = await message_service.conversation_search(
            "Python machine learning", limit=3
        )

        assert len(results) >= 1
        # Most relevant result should be first (contains both Python and ML)
        assert "machine learning" in results[0]["content"].lower()


class TestConversationSearchFilterRole:
    """Test role filtering in conversation search."""

    @pytest.mark.asyncio
    async def test_filter_by_user_role(self, message_service):
        """conversation_search() should filter by user role."""
        await message_service.store_message(
            content="User asked about Python",
            role="user",
        )
        await message_service.store_message(
            content="Assistant answered about Python",
            role="assistant",
        )

        results = await message_service.conversation_search(
            "Python", limit=10, roles=["user"]
        )

        assert len(results) >= 1
        assert all(r["role"] == "user" for r in results)

    @pytest.mark.asyncio
    async def test_filter_by_assistant_role(self, message_service):
        """conversation_search() should filter by assistant role."""
        await message_service.store_message(
            content="User asked about JavaScript",
            role="user",
        )
        await message_service.store_message(
            content="Assistant explained JavaScript",
            role="assistant",
        )

        results = await message_service.conversation_search(
            "JavaScript", limit=10, roles=["assistant"]
        )

        assert len(results) >= 1
        assert all(r["role"] == "assistant" for r in results)

    @pytest.mark.asyncio
    async def test_filter_by_multiple_roles(self, message_service):
        """conversation_search() should filter by multiple roles."""
        await message_service.store_message(
            content="User asked about Rust",
            role="user",
        )
        await message_service.store_message(
            content="Assistant explained Rust",
            role="assistant",
        )
        await message_service.store_message(
            content="Tool executed Rust code",
            role="tool",
        )

        results = await message_service.conversation_search(
            "Rust", limit=10, roles=["user", "assistant"]
        )

        assert len(results) >= 2
        assert all(r["role"] in ["user", "assistant"] for r in results)
        # Should not include tool messages
        assert not any(r["role"] == "tool" for r in results)


class TestConversationSearchWithDates:
    """Test datetime filtering in conversation search."""

    @pytest.mark.asyncio
    async def test_filter_by_start_date(self, message_service):
        """conversation_search() should filter by start_date."""
        # Store messages (they'll have current timestamps)
        await message_service.store_message(
            content="Message about TypeScript",
            role="assistant",
        )

        # Search with start_date in the past should find it
        past_date = datetime.now(timezone.utc) - timedelta(hours=1)
        results = await message_service.conversation_search(
            "TypeScript", limit=10, start_date=past_date
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_filter_by_end_date(self, message_service):
        """conversation_search() should filter by end_date."""
        await message_service.store_message(
            content="Message about Go language",
            role="assistant",
        )

        # Search with end_date in the future should find it
        future_date = datetime.now(timezone.utc) + timedelta(hours=1)
        results = await message_service.conversation_search(
            "Go language", limit=10, end_date=future_date
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, message_service):
        """conversation_search() should filter by date range."""
        await message_service.store_message(
            content="Message about Swift programming",
            role="assistant",
        )

        # Search within a range that includes now
        past_date = datetime.now(timezone.utc) - timedelta(hours=1)
        future_date = datetime.now(timezone.utc) + timedelta(hours=1)

        results = await message_service.conversation_search(
            "Swift programming",
            limit=10,
            start_date=past_date,
            end_date=future_date,
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_filter_excludes_outside_range(self, message_service):
        """conversation_search() should exclude messages outside date range."""
        await message_service.store_message(
            content="Message about Kotlin",
            role="assistant",
        )

        # Search with end_date in the past should not find current message
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        results = await message_service.conversation_search(
            "Kotlin", limit=10, end_date=past_date
        )

        assert len(results) == 0


class TestConversationSearchPagination:
    """Test pagination in conversation search."""

    @pytest.mark.asyncio
    async def test_limit_results(self, message_service):
        """conversation_search() should respect limit parameter."""
        # Store multiple messages
        for i in range(5):
            await message_service.store_message(
                content=f"Message {i} about testing pagination",
                role="assistant",
            )

        results = await message_service.conversation_search(
            "pagination", limit=3
        )

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_offset_results(self, message_service):
        """conversation_search() should support offset for pagination."""
        # Store multiple messages
        for i in range(5):
            await message_service.store_message(
                content=f"Offset test message number {i}",
                role="assistant",
            )

        # Get first page
        page1 = await message_service.conversation_search(
            "Offset test", limit=2, offset=0
        )

        # Get second page
        page2 = await message_service.conversation_search(
            "Offset test", limit=2, offset=2
        )

        # Pages should have different messages (by ID)
        page1_ids = {r["id"] for r in page1}
        page2_ids = {r["id"] for r in page2}
        assert page1_ids.isdisjoint(page2_ids), "Offset should skip previous results"


class TestConversationSearchHybrid:
    """Test hybrid FTS + vector search (future enhancement)."""

    @pytest.mark.asyncio
    async def test_search_mode_fts(self, message_service):
        """conversation_search() with search_mode='fts' uses full-text search."""
        await message_service.store_message(
            content="Exploring hybrid search capabilities",
            role="assistant",
        )

        results = await message_service.conversation_search(
            "hybrid search", limit=10, search_mode="fts"
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_mode_defaults_to_hybrid(self, message_service):
        """conversation_search() should default to hybrid mode."""
        await message_service.store_message(
            content="Default search mode test",
            role="assistant",
        )

        # Should work without explicit search_mode
        results = await message_service.conversation_search(
            "Default search", limit=10
        )

        assert len(results) >= 1


class TestSessionIsolation:
    """Test session isolation for message memory."""

    @pytest.mark.asyncio
    async def test_messages_isolated_by_session(self, cleanup_session):
        """Different sessions should not see each other's messages."""
        from scripts.agentica_patterns.message_memory import MessageMemoryService
        from scripts.agentica_patterns.postgres_pool import get_connection

        session1 = unique_session_id()
        session2 = unique_session_id()
        cleanup_session(session1)
        cleanup_session(session2)

        service1 = MessageMemoryService(session_id=session1)
        service2 = MessageMemoryService(session_id=session2)

        # Store in session1
        await service1.store_message(
            content="Session1 private conversation about secrets",
            role="user",
        )

        # Store in session2
        await service2.store_message(
            content="Session2 different conversation about secrets",
            role="user",
        )

        # Session1 should only find its own messages
        results1 = await service1.conversation_search("secrets", limit=10)
        assert len(results1) == 1
        assert "Session1" in results1[0]["content"]

        # Session2 should only find its own messages
        results2 = await service2.conversation_search("secrets", limit=10)
        assert len(results2) == 1
        assert "Session2" in results2[0]["content"]


class TestGetRecentMessages:
    """Test getting recent messages for context."""

    @pytest.mark.asyncio
    async def test_get_recent_messages(self, message_service):
        """get_recent_messages() should return most recent messages."""
        # Store messages in order
        for i in range(5):
            await message_service.store_message(
                content=f"Recent message {i}",
                role="assistant",
            )

        messages = await message_service.get_recent_messages(limit=3)

        assert len(messages) <= 3

    @pytest.mark.asyncio
    async def test_get_recent_messages_filter_role(self, message_service):
        """get_recent_messages() should filter by role."""
        await message_service.store_message(
            content="User message for recent test",
            role="user",
        )
        await message_service.store_message(
            content="Assistant message for recent test",
            role="assistant",
        )

        messages = await message_service.get_recent_messages(limit=10, role="user")

        assert all(m.role == "user" for m in messages)

    @pytest.mark.asyncio
    async def test_get_recent_messages_returns_message_objects(self, message_service):
        """get_recent_messages() should return Message dataclass instances."""
        from scripts.agentica_patterns.message_memory import Message

        await message_service.store_message(
            content="Message for object test",
            role="assistant",
        )

        messages = await message_service.get_recent_messages(limit=1)

        assert len(messages) == 1
        assert isinstance(messages[0], Message)
        assert hasattr(messages[0], "id")
        assert hasattr(messages[0], "content")
        assert hasattr(messages[0], "role")
        assert hasattr(messages[0], "created_at")
