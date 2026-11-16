"""Unit tests for PostgreSQL memory service (Phase 3: TDD).

Tests are designed to run against a PostgreSQL + pgvector database.
These tests cover:
- Core memory CRUD operations
- Archival memory storage and text search
- Session isolation (different sessions don't see each other's data)
- Agent isolation within session
- Concurrent writes (10 agents writing simultaneously)
- Update existing memory
- Delete memory

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection

Run with:
    uv run pytest tests/unit/test_memory_service_pg.py -v
"""

import asyncio
from uuid import uuid4

import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-{uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def reset_pool_before_test():
    """Reset the connection pool before each test.

    This is needed because pytest-asyncio creates a new event loop for each test,
    and the global pool becomes invalid when the previous loop closes.
    """
    from scripts.agentica.postgres_pool import reset_pool

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
    from scripts.agentica.memory_service_pg import MemoryServicePG

    from scripts.agentica.postgres_pool import get_connection

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
    from scripts.agentica.postgres_pool import get_connection

    async with get_connection() as conn:
        for sid in sessions_to_clean:
            await conn.execute("DELETE FROM core_memory WHERE session_id = $1", sid)
            await conn.execute(
                "DELETE FROM archival_memory WHERE session_id = $1", sid
            )


class TestCoreMemory:
    """Test core memory operations."""

    @pytest.mark.asyncio
    async def test_store_core_memory(self, memory):
        """Should store a value in core memory."""
        await memory.set_core("persona", "You are a helpful assistant")
        result = await memory.get_core("persona")
        assert result == "You are a helpful assistant"

    @pytest.mark.asyncio
    async def test_recall_core_memory(self, memory):
        """Should retrieve a value from core memory."""
        await memory.set_core("task", "Build a REST API")
        result = await memory.get_core("task")
        assert result == "Build a REST API"

    @pytest.mark.asyncio
    async def test_update_existing_memory(self, memory):
        """Should update an existing core memory block."""
        await memory.set_core("project", "Version 1")
        await memory.set_core("project", "Version 2")
        result = await memory.get_core("project")
        assert result == "Version 2"

    @pytest.mark.asyncio
    async def test_delete_memory(self, memory):
        """Should delete a core memory block."""
        await memory.set_core("temp_key", "temp_value")
        await memory.delete_core("temp_key")
        result = await memory.get_core("temp_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_core_keys(self, memory):
        """Should list all core memory keys."""
        await memory.set_core("key1", "value1")
        await memory.set_core("key2", "value2")
        await memory.set_core("key3", "value3")

        keys = await memory.list_core_keys()

        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys

    @pytest.mark.asyncio
    async def test_get_all_core(self, memory):
        """Should get all core memory blocks as dict."""
        await memory.set_core("persona", "Assistant")
        await memory.set_core("task", "Help user")

        all_core = await memory.get_all_core()

        assert all_core["persona"] == "Assistant"
        assert all_core["task"] == "Help user"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, memory):
        """Should return None for nonexistent key."""
        result = await memory.get_core("nonexistent_key")
        assert result is None


class TestArchivalMemory:
    """Test archival memory operations."""

    @pytest.mark.asyncio
    async def test_store_archival_memory(self, memory):
        """Should store content in archival memory and return an ID."""
        memory_id = await memory.store("Python was created by Guido van Rossum")

        assert memory_id is not None
        # Memory ID is a UUID string (36 chars with hyphens)
        assert len(memory_id) == 36

    @pytest.mark.asyncio
    async def test_search_archival_memory_text(self, memory):
        """Should search archival memory using full-text search."""
        await memory.store("Python is a programming language")
        await memory.store("JavaScript is also a programming language")
        await memory.store("Rust is a systems programming language")

        results = await memory.search_text("Python", limit=5)

        assert len(results) >= 1
        assert any("Python" in r["content"] for r in results)

    @pytest.mark.asyncio
    async def test_store_archival_with_metadata(self, memory):
        """Should store archival memory with metadata."""
        await memory.store(
            "Important fact about the project",
            metadata={"source": "user", "priority": "high"},
        )

        results = await memory.search_text("Important fact", limit=1)

        assert len(results) == 1
        assert results[0]["metadata"]["source"] == "user"
        assert results[0]["metadata"]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_delete_archival_memory(self, memory):
        """Should delete a fact from archival memory."""
        memory_id = await memory.store("Temporary archival fact")

        await memory.delete_archival(memory_id)

        results = await memory.search_text("Temporary archival", limit=1)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_returns_ranked_results(self, memory):
        """Should return results ranked by relevance."""
        await memory.store("Python is used for web development")
        await memory.store("Python is excellent for machine learning and AI")
        await memory.store("The snake python lives in tropical regions")

        results = await memory.search_text("Python machine learning", limit=3)

        assert len(results) >= 1
        # First result should be most relevant (mentions both Python and ML)
        assert "machine learning" in results[0]["content"].lower()


class TestSessionIsolation:
    """Test that different sessions don't see each other's data."""

    @pytest.mark.asyncio
    async def test_core_memory_session_isolation(self, cleanup_session):
        """Different sessions should not see each other's core memory."""
        from scripts.agentica.memory_service_pg import MemoryServicePG

        session1 = unique_session_id()
        session2 = unique_session_id()
        cleanup_session(session1)
        cleanup_session(session2)

        memory1 = MemoryServicePG(session_id=session1)
        memory2 = MemoryServicePG(session_id=session2)
        await memory1.connect()
        await memory2.connect()

        # Store in session1
        await memory1.set_core("secret", "session1_secret")

        # Session2 should not see it
        result = await memory2.get_core("secret")
        assert result is None

        # Session2 stores its own value
        await memory2.set_core("secret", "session2_secret")

        # Each sees only their own
        assert await memory1.get_core("secret") == "session1_secret"
        assert await memory2.get_core("secret") == "session2_secret"

    @pytest.mark.asyncio
    async def test_archival_memory_session_isolation(self, cleanup_session):
        """Different sessions should not see each other's archival memory."""
        from scripts.agentica.memory_service_pg import MemoryServicePG

        session1 = unique_session_id()
        session2 = unique_session_id()
        cleanup_session(session1)
        cleanup_session(session2)

        memory1 = MemoryServicePG(session_id=session1)
        memory2 = MemoryServicePG(session_id=session2)
        await memory1.connect()
        await memory2.connect()

        # Store in session1
        await memory1.store("Session1 private data: Python rocks")

        # Store in session2
        await memory2.store("Session2 private data: JavaScript rocks")

        # Session1 should only see its own data
        results1 = await memory1.search_text("rocks", limit=10)
        assert len(results1) == 1
        assert "Session1" in results1[0]["content"]

        # Session2 should only see its own data
        results2 = await memory2.search_text("rocks", limit=10)
        assert len(results2) == 1
        assert "Session2" in results2[0]["content"]


class TestAgentIsolation:
    """Test that different agents within a session have isolated memory."""

    @pytest.mark.asyncio
    async def test_agent_core_memory_isolation(self, session_id, cleanup_session):
        """Different agents in same session should have isolated core memory."""
        from scripts.agentica.memory_service_pg import MemoryServicePG

        cleanup_session(session_id)

        agent1_memory = MemoryServicePG(session_id=session_id, agent_id="agent-1")
        agent2_memory = MemoryServicePG(session_id=session_id, agent_id="agent-2")
        await agent1_memory.connect()
        await agent2_memory.connect()

        # Agent1 stores its persona
        await agent1_memory.set_core("persona", "I am agent-1, a researcher")

        # Agent2 should not see agent1's persona
        result = await agent2_memory.get_core("persona")
        assert result is None

        # Agent2 stores its own persona
        await agent2_memory.set_core("persona", "I am agent-2, a writer")

        # Each agent sees only their own
        assert await agent1_memory.get_core("persona") == "I am agent-1, a researcher"
        assert await agent2_memory.get_core("persona") == "I am agent-2, a writer"

    @pytest.mark.asyncio
    async def test_agent_archival_memory_isolation(self, session_id, cleanup_session):
        """Different agents in same session should have isolated archival memory."""
        from scripts.agentica.memory_service_pg import MemoryServicePG

        cleanup_session(session_id)

        agent1_memory = MemoryServicePG(session_id=session_id, agent_id="agent-1")
        agent2_memory = MemoryServicePG(session_id=session_id, agent_id="agent-2")
        await agent1_memory.connect()
        await agent2_memory.connect()

        # Agent1 stores a fact
        await agent1_memory.store("Agent1 learned: Python is great for data science")

        # Agent2 stores a different fact
        await agent2_memory.store("Agent2 learned: Rust is great for systems programming")

        # Agent1 should only find its own facts
        results1 = await agent1_memory.search_text("great", limit=10)
        assert len(results1) == 1
        assert "Agent1" in results1[0]["content"]

        # Agent2 should only find its own facts
        results2 = await agent2_memory.search_text("great", limit=10)
        assert len(results2) == 1
        assert "Agent2" in results2[0]["content"]


class TestConcurrentWrites:
    """Test concurrent write scenarios (multi-agent)."""

    @pytest.mark.asyncio
    async def test_concurrent_core_memory_writes(self, cleanup_session):
        """10 agents writing to core memory simultaneously should not error."""
        from scripts.agentica.memory_service_pg import MemoryServicePG

        session_id = unique_session_id()
        cleanup_session(session_id)

        error_count = 0
        success_count = 0
        errors: list[Exception] = []

        async def agent_work(agent_id: str):
            nonlocal error_count, success_count
            memory = MemoryServicePG(session_id=session_id, agent_id=agent_id)
            await memory.connect()

            for i in range(10):  # 10 writes per agent
                try:
                    await memory.set_core(f"key-{i}", f"value-{i}-from-{agent_id}")
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(e)

        # Run 10 agents concurrently
        agents = [agent_work(f"agent-{i}") for i in range(10)]
        await asyncio.gather(*agents, return_exceptions=True)

        # Calculate error rate
        total_writes = 10 * 10  # 10 agents * 10 writes
        error_rate = error_count / total_writes if total_writes > 0 else 0

        # Assert <5% error rate
        assert error_rate < 0.05, (
            f"Error rate {error_rate:.2%} exceeds 5% threshold. "
            f"Errors: {errors[:5]}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_archival_memory_writes(self, cleanup_session):
        """10 agents writing to archival memory simultaneously should not error."""
        from scripts.agentica.memory_service_pg import MemoryServicePG

        session_id = unique_session_id()
        cleanup_session(session_id)

        error_count = 0
        success_count = 0
        errors: list[Exception] = []

        async def agent_work(agent_id: str):
            nonlocal error_count, success_count
            memory = MemoryServicePG(session_id=session_id, agent_id=agent_id)
            await memory.connect()

            for i in range(10):  # 10 writes per agent
                try:
                    await memory.store(f"Fact {i} from {agent_id}")
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(e)

        # Run 10 agents concurrently
        agents = [agent_work(f"agent-{i}") for i in range(10)]
        await asyncio.gather(*agents, return_exceptions=True)

        # Calculate error rate
        total_writes = 10 * 10  # 10 agents * 10 writes
        error_rate = error_count / total_writes if total_writes > 0 else 0

        # Assert <5% error rate
        assert error_rate < 0.05, (
            f"Error rate {error_rate:.2%} exceeds 5% threshold. "
            f"Errors: {errors[:5]}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, cleanup_session):
        """10 agents doing mixed operations should not error."""
        from scripts.agentica.memory_service_pg import MemoryServicePG

        session_id = unique_session_id()
        cleanup_session(session_id)

        error_count = 0
        success_count = 0
        errors: list[Exception] = []

        async def agent_work(agent_id: str):
            nonlocal error_count, success_count
            memory = MemoryServicePG(session_id=session_id, agent_id=agent_id)
            await memory.connect()

            for i in range(10):
                try:
                    # Mix of operations
                    await memory.set_core(f"key-{i}", f"value-{i}")
                    await memory.store(f"Fact {i} from {agent_id}")
                    await memory.get_core(f"key-{i}")
                    success_count += 3  # Count each operation
                except Exception as e:
                    error_count += 3  # Assume all failed in this iteration
                    errors.append(e)

        # Run 10 agents concurrently
        agents = [agent_work(f"agent-{i}") for i in range(10)]
        await asyncio.gather(*agents, return_exceptions=True)

        # Calculate error rate
        total_operations = 10 * 10 * 3  # 10 agents * 10 iterations * 3 ops
        error_rate = error_count / total_operations if total_operations > 0 else 0

        # Assert <5% error rate
        assert error_rate < 0.05, (
            f"Error rate {error_rate:.2%} exceeds 5% threshold. "
            f"Errors: {errors[:5]}"
        )


class TestRecallMemory:
    """Test recall (cross-source query) operations."""

    @pytest.mark.asyncio
    async def test_recall_from_core(self, memory):
        """Should recall matching content from core memory."""
        await memory.set_core("persona", "I am a helpful coding assistant")

        result = await memory.recall("persona")

        assert "helpful coding assistant" in result

    @pytest.mark.asyncio
    async def test_recall_from_archival(self, memory):
        """Should recall matching content from archival memory."""
        await memory.store("User prefers TypeScript over JavaScript")

        result = await memory.recall("TypeScript")

        assert "TypeScript" in result

    @pytest.mark.asyncio
    async def test_recall_combines_sources(self, memory):
        """Should combine results from both core and archival memory."""
        await memory.set_core("project", "E-commerce platform")
        await memory.store("The project uses React for frontend")
        await memory.store("The project uses FastAPI for backend")

        result = await memory.recall("project")

        # Should include either core or archival mentions
        assert "E-commerce" in result or "project" in result.lower()

    @pytest.mark.asyncio
    async def test_recall_no_matches(self, memory):
        """Should return 'no memories' message when nothing matches."""
        result = await memory.recall("nonexistent_xyz_query")

        assert "no relevant memories" in result.lower()


class TestToContext:
    """Test context generation for prompt injection."""

    @pytest.mark.asyncio
    async def test_to_context_includes_core(self, memory):
        """Should include core memory in context."""
        await memory.set_core("persona", "Expert Python developer")
        await memory.set_core("task", "Build a web scraper")

        context = await memory.to_context()

        assert "## Core Memory" in context
        assert "Expert Python developer" in context
        assert "Build a web scraper" in context

    @pytest.mark.asyncio
    async def test_to_context_includes_archival(self, memory):
        """Should include recent archival memory in context."""
        await memory.store("User prefers async/await patterns")
        await memory.store("Project requires Python 3.11+")

        context = await memory.to_context()

        assert "## Recent Archival Memory" in context
        assert "async/await" in context or "Python 3.11" in context

    @pytest.mark.asyncio
    async def test_to_context_empty_memory(self, memory):
        """Should handle empty memory gracefully."""
        context = await memory.to_context()

        assert "## Core Memory" in context
        assert "(empty)" in context


class TestUpdateOperations:
    """Test update operations for existing memory."""

    @pytest.mark.asyncio
    async def test_update_core_memory_preserves_other_keys(self, memory):
        """Updating one key should not affect other keys."""
        await memory.set_core("key1", "value1")
        await memory.set_core("key2", "value2")

        await memory.set_core("key1", "updated_value1")

        assert await memory.get_core("key1") == "updated_value1"
        assert await memory.get_core("key2") == "value2"

    @pytest.mark.asyncio
    async def test_rapid_updates_to_same_key(self, memory):
        """Rapid updates to the same key should result in last value."""
        for i in range(100):
            await memory.set_core("rapid_key", f"value_{i}")

        result = await memory.get_core("rapid_key")
        assert result == "value_99"
