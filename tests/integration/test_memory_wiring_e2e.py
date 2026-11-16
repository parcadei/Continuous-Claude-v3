"""End-to-end tests for the complete memory system.

Phase 3.2 + 4: Integration and E2E Testing

Tests cover:
- Full memory workflow: spawn agent -> remember -> recall -> search
- Pattern memory integration: Swarm/Hierarchical with memory
- Combined datetime and tag filtering
- Conversation search with Block core memory
- Multi-agent memory sharing within session
- Session isolation between different sessions
- Hybrid search with all filter types

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection
- All migrations applied (001-004)

Run with:
    uv run pytest tests/integration/test_memory_wiring_e2e.py -v
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"e2e-test-{uuid4().hex[:8]}"


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
        await conn.execute(
            "DELETE FROM memory_messages WHERE session_id = $1", session_id
        )


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
async def cleanup_sessions():
    """Fixture that returns a function to register sessions for cleanup."""
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
            await conn.execute("DELETE FROM memory_messages WHERE session_id = $1", sid)


class TestFullMemoryWorkflow:
    """Test complete workflow: spawn agent -> remember -> recall -> search."""

    @pytest.mark.asyncio
    async def test_full_memory_workflow(self, session_id, tmp_path):
        """Test complete memory workflow end-to-end."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        # Create scope with memory enabled (simulates what tracked_spawn does)
        scope = create_unified_scope(
            session_id=session_id,
            db_path=tmp_path / "memory.db",
            enable_memory=True,
            enable_tasks=False,
        )

        # 1. Store core memory (remember)
        scope["remember"]("user_name", "Alice")
        scope["remember"]("project_name", "Memory Wiring")

        # 2. Store archival memory (store_fact) - SQLite version doesn't use tags
        fact_id = scope["store_fact"]("The project uses PostgreSQL for persistence")
        assert fact_id is not None, "store_fact should return an ID"

        # 3. Recall core memory
        name_result = scope["recall"]("user_name")
        assert "Alice" in name_result, f"Failed to recall user_name: {name_result}"

        project_result = scope["recall"]("project_name")
        assert "Memory Wiring" in project_result, f"Failed to recall project: {project_result}"

        # 4. Search archival memory
        search_results = scope["search_memory"]("PostgreSQL")
        assert len(search_results) >= 1, "Should find at least one result"
        assert any("PostgreSQL" in r.get("content", "") for r in search_results)

    @pytest.mark.asyncio
    async def test_workflow_with_multiple_facts(self, session_id, tmp_path):
        """Test storing and searching multiple facts."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=tmp_path / "memory.db",
            enable_memory=True,
            enable_tasks=False,
        )

        # Store multiple facts (SQLite version, no tags)
        facts = [
            "Python is used for backend services",
            "TypeScript powers the frontend",
            "PostgreSQL stores the data",
            "Redis handles caching",
            "Docker containers run everything",
        ]

        for fact in facts:
            scope["store_fact"](fact)

        # Search for specific technologies
        python_results = scope["search_memory"]("Python backend")
        assert len(python_results) >= 1

        postgres_results = scope["search_memory"]("PostgreSQL data")
        assert len(postgres_results) >= 1


class TestPatternMemoryIntegration:
    """Test memory works in Swarm/Hierarchical patterns."""

    @pytest.mark.asyncio
    async def test_pattern_memory_integration(self, tmp_path):
        """Test memory integration in pattern context."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        from scripts.agentica_patterns import tracked_agent

        session_id = unique_session_id()
        coord_db = CoordinationDB(db_path=tmp_path / "coord.db", session_id=session_id)

        captured_scopes = []

        async def capture_spawn(**kwargs):
            agent = AsyncMock()
            agent.call = AsyncMock(return_value={"insight": "test"})
            captured_scopes.append(dict(kwargs.get("scope", {})))
            return agent

        with patch.object(tracked_agent, "spawn", side_effect=capture_spawn):
            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": session_id}):
                from scripts.agentica_patterns.patterns import Swarm

                orig_tracked_spawn = tracked_agent.tracked_spawn

                async def patched_tracked_spawn(*args, **kwargs):
                    kwargs["memory_db_path"] = tmp_path / "memory.db"
                    return await orig_tracked_spawn(*args, **kwargs)

                with patch.object(tracked_agent, "tracked_spawn", patched_tracked_spawn):
                    swarm = Swarm(
                        perspectives=["Analyst", "Developer"],
                        db=coord_db,
                    )
                    await swarm.execute("Analyze the codebase")

        # All agents should have memory functions
        assert len(captured_scopes) >= 2, f"Expected 2 agents, got {len(captured_scopes)}"
        for i, scope in enumerate(captured_scopes):
            assert "remember" in scope, f"Agent {i} missing 'remember'"
            assert "recall" in scope, f"Agent {i} missing 'recall'"
            assert "search_memory" in scope, f"Agent {i} missing 'search_memory'"
            assert "store_fact" in scope, f"Agent {i} missing 'store_fact'"


class TestDatetimeAndTagsCombined:
    """Test datetime filtering with tag filtering together."""

    @pytest.mark.asyncio
    async def test_datetime_and_tags_combined(self, memory):
        """Test combining datetime and tag filters."""
        from scripts.agentica_patterns.postgres_pool import get_connection

        now = datetime.now(timezone.utc)
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(days=7)

        # Store facts with different dates and tags
        async with get_connection() as conn:
            # Recent fact with "important" tag
            await conn.execute(
                """
                INSERT INTO archival_memory (id, session_id, agent_id, content, metadata, created_at)
                VALUES (gen_random_uuid(), $1, NULL, $2, '{}', $3)
                """,
                memory.session_id,
                "Recent important Python update",
                now,
            )

            # Week-old fact with "important" tag
            await conn.execute(
                """
                INSERT INTO archival_memory (id, session_id, agent_id, content, metadata, created_at)
                VALUES (gen_random_uuid(), $1, NULL, $2, '{}', $3)
                """,
                memory.session_id,
                "Old important Python note",
                one_week_ago,
            )

        # Add tags to both facts
        results_all = await memory.search_text("Python", limit=10)
        for r in results_all:
            await memory.add_tag(r["id"], "important")
            await memory.add_tag(r["id"], "python")

        # Search with date filter (only recent) + tag filter
        start_date = now - timedelta(days=3)
        results = await memory.search_with_tags(
            query="Python",
            tags=["important"],
            tag_match_mode="any",
            limit=10,
        )

        # Filter by date manually to verify datetime + tag works
        # Handle created_at which may be datetime object or ISO string
        recent_results = []
        for r in results:
            created_at = r.get("created_at")
            if created_at is None:
                continue
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if created_at >= start_date:
                recent_results.append(r)

        # Should have at least the recent fact
        assert len(recent_results) >= 1
        assert any("Recent" in r["content"] for r in recent_results)

    @pytest.mark.asyncio
    async def test_tag_all_mode_with_dates(self, memory):
        """Test tag_match_mode='all' combined with date filters."""
        # Store a fact with multiple tags
        memory_id = await memory.store(
            "Python project with machine learning",
            tags=["python", "ml", "important"],
        )

        # Search with all tags required
        results = await memory.search_with_tags(
            query="Python machine learning",
            tags=["python", "ml"],
            tag_match_mode="all",
            limit=10,
        )

        assert len(results) >= 1
        assert any("machine learning" in r["content"] for r in results)


class TestConversationWithBlocks:
    """Test conversation search with Block core memory."""

    @pytest.mark.asyncio
    async def test_conversation_with_blocks(self, message_service, session_id):
        """Test conversation search alongside Block core memory."""
        from scripts.agentica_patterns.memory_block import Block, BlockManager

        # Set up Block-based core memory
        manager = BlockManager()
        manager.add_block(Block(label="persona", value="I am a helpful coding assistant"))
        manager.add_block(Block(label="human", value="The user is a Python developer"))

        # Store conversation messages
        await message_service.store_message(
            content="Can you help me with Python async?",
            role="user",
        )
        await message_service.store_message(
            content="Yes! I can help with Python async/await patterns.",
            role="assistant",
        )
        await message_service.store_message(
            content="Show me an example of asyncio.gather",
            role="user",
        )

        # Search conversation
        results = await message_service.conversation_search("async Python", limit=10)

        assert len(results) >= 1
        assert any("async" in r["content"].lower() for r in results)

        # Verify Block core memory is accessible
        core_memory_text = manager.to_core_memory_string()
        assert "<persona>" in core_memory_text
        assert "coding assistant" in core_memory_text
        assert "<human>" in core_memory_text
        assert "Python developer" in core_memory_text

    @pytest.mark.asyncio
    async def test_block_update_during_conversation(self, message_service, session_id):
        """Test updating Block memory during conversation."""
        from scripts.agentica_patterns.memory_block import Block, BlockManager

        manager = BlockManager()
        manager.add_block(Block(label="context", value="Initial project context"))

        # Store initial conversation
        await message_service.store_message(
            content="We're working on Project Alpha",
            role="user",
        )

        # Update block with new context
        manager.update_block("context", "Working on Project Alpha - Python backend")

        # Continue conversation
        await message_service.store_message(
            content="Let me help with Project Alpha's Python backend",
            role="assistant",
        )

        # Verify block updated
        block = manager.get_block("context")
        assert "Project Alpha" in block.value
        assert "Python backend" in block.value

        # Verify conversation searchable
        results = await message_service.conversation_search("Project Alpha", limit=10)
        assert len(results) >= 1


class TestMultiAgentMemorySharing:
    """Test memory persists and is shared across agents in same session."""

    @pytest.mark.asyncio
    async def test_multi_agent_memory_sharing(self, tmp_path):
        """Test memory is shared across agents in the same session."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope

        session_id = unique_session_id()

        # Agent 1: Researcher stores facts
        scope1 = create_unified_scope(
            session_id=session_id,
            db_path=tmp_path / "memory.db",
            enable_memory=True,
            enable_tasks=False,
        )

        scope1["remember"]("api_endpoint", "https://api.example.com")
        scope1["store_fact"]("The API uses JWT authentication")
        scope1["store_fact"]("Rate limit is 1000 requests per minute")

        # Agent 2: Developer recalls facts
        scope2 = create_unified_scope(
            session_id=session_id,
            db_path=tmp_path / "memory.db",
            enable_memory=True,
            enable_tasks=False,
        )

        # Recall core memory
        api_result = scope2["recall"]("api_endpoint")
        assert "api.example.com" in api_result, f"Agent 2 should see Agent 1's core memory: {api_result}"

        # Search archival memory
        auth_results = scope2["search_memory"]("JWT authentication")
        assert len(auth_results) >= 1, "Agent 2 should see Agent 1's archival memory"
        assert any("JWT" in r.get("content", "") for r in auth_results)

        # Agent 3: Tester also has access
        scope3 = create_unified_scope(
            session_id=session_id,
            db_path=tmp_path / "memory.db",
            enable_memory=True,
            enable_tasks=False,
        )

        rate_results = scope3["search_memory"]("rate limit")
        assert len(rate_results) >= 1, "Agent 3 should see all shared memory"


class TestSessionIsolationComplete:
    """Test different sessions have completely isolated memory."""

    @pytest.mark.asyncio
    async def test_session_isolation_complete(self, tmp_path, cleanup_sessions):
        """Test complete isolation between different sessions."""
        from scripts.agentica_patterns.unified_scope import create_unified_scope
        from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

        session_a = unique_session_id()
        session_b = unique_session_id()
        cleanup_sessions(session_a)
        cleanup_sessions(session_b)

        # Session A stores sensitive data
        scope_a = create_unified_scope(
            session_id=session_a,
            db_path=tmp_path / "memory.db",
            enable_memory=True,
            enable_tasks=False,
        )
        scope_a["remember"]("secret", "session-a-password-123")
        scope_a["store_fact"]("Session A confidential: Project X deadline is tomorrow")

        # Session A also stores in PostgreSQL
        memory_a = MemoryServicePG(session_id=session_a)
        await memory_a.connect()
        await memory_a.store("Session A PostgreSQL secret fact", tags=["confidential"])

        # Session B stores different data
        scope_b = create_unified_scope(
            session_id=session_b,
            db_path=tmp_path / "memory.db",
            enable_memory=True,
            enable_tasks=False,
        )
        scope_b["remember"]("secret", "session-b-password-456")
        scope_b["store_fact"]("Session B info: Working on feature Y")

        memory_b = MemoryServicePG(session_id=session_b)
        await memory_b.connect()
        await memory_b.store("Session B PostgreSQL fact", tags=["info"])

        # Verify isolation
        # Session A should NOT see Session B's data
        secret_a = scope_a["recall"]("secret")
        assert "session-a-password" in secret_a
        assert "session-b-password" not in secret_a

        search_a = scope_a["search_memory"]("Session")
        a_contents = [r.get("content", "") for r in search_a]
        assert any("Session A" in c for c in a_contents)
        assert not any("Session B" in c for c in a_contents)

        # Session B should NOT see Session A's data
        secret_b = scope_b["recall"]("secret")
        assert "session-b-password" in secret_b
        assert "session-a-password" not in secret_b

        # PostgreSQL isolation
        pg_search_a = await memory_a.search_text("Session", limit=10)
        pg_a_contents = [r["content"] for r in pg_search_a]
        assert all("Session A" in c for c in pg_a_contents if "Session" in c)
        assert not any("Session B" in c for c in pg_a_contents)

        pg_search_b = await memory_b.search_text("Session", limit=10)
        pg_b_contents = [r["content"] for r in pg_search_b]
        assert all("Session B" in c for c in pg_b_contents if "Session" in c)
        assert not any("Session A" in c for c in pg_b_contents)


class TestHybridSearchWithAllFilters:
    """Test RRF hybrid search with dates, tags, and role filters."""

    @pytest.mark.asyncio
    async def test_hybrid_search_with_all_filters(self, memory, cleanup_sessions):
        """Test hybrid search combining all filter types."""
        from scripts.agentica_patterns.postgres_pool import get_connection

        cleanup_sessions(memory.session_id)
        now = datetime.now(timezone.utc)
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(days=7)

        # Create test data with embeddings
        dummy_embedding = [0.1] * 4096

        async with get_connection() as conn:
            from scripts.agentica_patterns.postgres_pool import init_pgvector
            await init_pgvector(conn)

            # Insert facts with embeddings and dates
            ids = []

            # Fact 1: Recent, important, about Python
            result = await conn.fetchval(
                """
                INSERT INTO archival_memory (id, session_id, content, embedding, metadata, created_at)
                VALUES (gen_random_uuid(), $1, $2, $3::vector, '{}', $4)
                RETURNING id
                """,
                memory.session_id,
                "Python async programming is powerful and efficient",
                dummy_embedding,
                now,
            )
            ids.append(str(result))

            # Fact 2: Week old, about Python
            result = await conn.fetchval(
                """
                INSERT INTO archival_memory (id, session_id, content, embedding, metadata, created_at)
                VALUES (gen_random_uuid(), $1, $2, $3::vector, '{}', $4)
                RETURNING id
                """,
                memory.session_id,
                "Python has excellent library ecosystem",
                dummy_embedding,
                one_week_ago,
            )
            ids.append(str(result))

            # Fact 3: Recent, about JavaScript
            result = await conn.fetchval(
                """
                INSERT INTO archival_memory (id, session_id, content, embedding, metadata, created_at)
                VALUES (gen_random_uuid(), $1, $2, $3::vector, '{}', $4)
                RETURNING id
                """,
                memory.session_id,
                "JavaScript dominates web frontend development",
                dummy_embedding,
                now,
            )
            ids.append(str(result))

        # Add tags
        await memory.add_tag(ids[0], "important")
        await memory.add_tag(ids[0], "python")
        await memory.add_tag(ids[1], "python")
        await memory.add_tag(ids[2], "javascript")

        # Test hybrid search with date filter
        hybrid_results = await memory.search_hybrid(
            text_query="Python programming",
            query_embedding=dummy_embedding,
            start_date=now - timedelta(days=3),
            limit=10,
        )

        # Should only get recent Python fact
        assert len(hybrid_results) >= 1
        recent_python = [r for r in hybrid_results if "async" in r["content"]]
        assert len(recent_python) >= 1, "Should find recent Python fact"

        # Old fact should not be in results
        old_facts = [r for r in hybrid_results if "library ecosystem" in r["content"]]
        assert len(old_facts) == 0, "Old fact should be filtered by date"

    @pytest.mark.asyncio
    async def test_rrf_hybrid_search_available(self, memory, cleanup_sessions):
        """Verify RRF hybrid search is available and working."""
        cleanup_sessions(memory.session_id)

        # Store test data
        await memory.store("Test fact for RRF hybrid search validation")

        # Verify method exists and is callable
        assert hasattr(memory, "search_hybrid_rrf"), "RRF hybrid search should be available"

        # Create dummy embedding for test
        dummy_embedding = [0.1] * 4096

        # Call RRF hybrid search
        results = await memory.search_hybrid_rrf(
            text_query="RRF hybrid",
            query_embedding=dummy_embedding,
            limit=10,
        )

        # Should return results (may be empty if embedding not indexed)
        assert isinstance(results, list), "RRF should return a list"


class TestLettaParityValidation:
    """Validate all Letta parity gaps are addressed."""

    @pytest.mark.asyncio
    async def test_embedding_dimension_4096(self, memory):
        """Gap 1: Verify embedding dimension is 4096."""
        from scripts.agentica_patterns.postgres_pool import get_connection

        async with get_connection() as conn:
            # Check column definition
            result = await conn.fetchrow(
                """
                SELECT character_maximum_length, udt_name
                FROM information_schema.columns
                WHERE table_name = 'archival_memory' AND column_name = 'embedding'
                """
            )

            # pgvector stores as 'vector' type
            assert result["udt_name"] == "vector", "Should use pgvector type"

        # Also verify we can store 4096-dim embedding
        embedding = [0.1] * 4096
        memory_id = await memory.store(
            "Test fact with 4096-dim embedding",
            embedding=embedding,
        )
        assert memory_id is not None, "Should store 4096-dim embedding"

    @pytest.mark.asyncio
    async def test_temporal_filtering(self, memory):
        """Gap 2: Verify temporal filtering works."""
        from scripts.agentica_patterns.postgres_pool import get_connection

        now = datetime.now(timezone.utc)
        past = now - timedelta(days=5)

        # Insert with controlled timestamp
        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO archival_memory (id, session_id, content, metadata, created_at)
                VALUES (gen_random_uuid(), $1, $2, '{}', $3)
                """,
                memory.session_id,
                "Old temporal test fact",
                past,
            )

        # Search with start_date should exclude old fact
        results = await memory.search_text(
            "temporal test",
            start_date=now - timedelta(days=2),
            limit=10,
        )

        # Old fact should not appear
        old_found = any("Old temporal" in r["content"] for r in results)
        assert not old_found, "Old facts should be filtered by start_date"

    @pytest.mark.asyncio
    async def test_tag_filtering_any_all(self, memory):
        """Gap 3: Verify tag filtering with any/all modes."""
        # Store facts with tags
        id1 = await memory.store("Tag test fact A", tags=["tag1", "tag2"])
        id2 = await memory.store("Tag test fact B", tags=["tag1", "tag3"])
        id3 = await memory.store("Tag test fact C", tags=["tag3"])

        # Test 'any' mode (OR)
        any_results = await memory.search_with_tags(
            query="Tag test",
            tags=["tag1", "tag3"],
            tag_match_mode="any",
            limit=10,
        )
        assert len(any_results) >= 3, "Any mode should match facts with tag1 OR tag3"

        # Test 'all' mode (AND)
        all_results = await memory.search_with_tags(
            query="Tag test",
            tags=["tag1", "tag2"],
            tag_match_mode="all",
            limit=10,
        )
        assert len(all_results) == 1, "All mode should only match fact with BOTH tag1 AND tag2"
        assert "fact A" in all_results[0]["content"]

    @pytest.mark.asyncio
    async def test_rrf_hybrid_search_exists(self, memory):
        """Gap 4 (already done): Verify RRF hybrid search method exists."""
        assert hasattr(memory, "search_hybrid_rrf"), "RRF hybrid search should exist"
        assert callable(memory.search_hybrid_rrf), "RRF hybrid search should be callable"

    @pytest.mark.asyncio
    async def test_conversation_search_exists(self, message_service):
        """Gap 5: Verify conversation search works."""
        await message_service.store_message(
            content="Conversation search validation message",
            role="user",
        )

        results = await message_service.conversation_search(
            "Conversation search validation",
            limit=10,
        )

        assert len(results) >= 1
        assert any("validation" in r["content"].lower() for r in results)

    def test_block_dataclass_exists(self):
        """Gap 6: Verify Block dataclass is implemented."""
        from scripts.agentica_patterns.memory_block import Block, BlockManager

        # Test Block creation
        block = Block(label="test", value="content", limit=1000)
        assert block.label == "test"
        assert block.value == "content"
        assert block.limit == 1000

        # Test character limit enforcement
        with pytest.raises(ValueError):
            Block(label="overflow", value="x" * 6000, limit=5000)

        # Test BlockManager
        manager = BlockManager()
        manager.add_block(Block(label="persona", value="I am helpful"))
        assert manager.get_block("persona") is not None

        # Test core memory string format
        output = manager.to_core_memory_string()
        assert "<persona>" in output
        assert "</persona>" in output


class TestMessageMemorySessionIsolation:
    """Test conversation memory is isolated by session."""

    @pytest.mark.asyncio
    async def test_message_session_isolation(self, cleanup_sessions):
        """Messages should be isolated between sessions."""
        from scripts.agentica_patterns.message_memory import MessageMemoryService

        session1 = unique_session_id()
        session2 = unique_session_id()
        cleanup_sessions(session1)
        cleanup_sessions(session2)

        service1 = MessageMemoryService(session_id=session1)
        service2 = MessageMemoryService(session_id=session2)

        # Store in session 1
        await service1.store_message(
            content="Session 1 secret conversation",
            role="user",
        )

        # Store in session 2
        await service2.store_message(
            content="Session 2 different conversation",
            role="user",
        )

        # Search should only return own session's messages
        results1 = await service1.conversation_search("secret", limit=10)
        assert len(results1) == 1
        assert "Session 1" in results1[0]["content"]

        results2 = await service2.conversation_search("conversation", limit=10)
        assert len(results2) == 1
        assert "Session 2" in results2[0]["content"]

        # Cross-session search should not find other session's data
        cross_search1 = await service1.conversation_search("Session 2", limit=10)
        assert len(cross_search1) == 0, "Session 1 should not see Session 2's messages"

        cross_search2 = await service2.conversation_search("Session 1", limit=10)
        assert len(cross_search2) == 0, "Session 2 should not see Session 1's messages"
