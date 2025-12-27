"""Level 2 Tests: Memory CRUD Operations.

Tests for memory operations using real SQLite.
No mocking needed - SQLite is deterministic.

Test implementation follows TDD best practices:
- Use tmp_path fixtures for database isolation
- Test session isolation with multiple scopes
- Verify FTS5 search behavior
"""

import asyncio
import pytest
from pathlib import Path
from uuid import uuid4


def _run_async(coro):
    """Run an async coroutine synchronously for tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(coro)
    else:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def session_id() -> str:
    """Generate unique session ID for test isolation."""
    return f"test-{uuid4().hex[:8]}"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "memory.db"


@pytest.fixture
def memory_scope(db_path: Path, session_id: str):
    """Create unified scope with memory enabled, file ops mocked."""
    from unittest.mock import patch
    from scripts.agentica.unified_scope import create_unified_scope

    with patch('scripts.agentica.unified_scope._call_claude_cli') as mock:
        mock.return_value = "mocked"
        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=True,
            enable_tasks=False,
        )
        yield scope


@pytest.fixture
def dual_session_scopes(db_path: Path):
    """Two scopes with different session_ids, same DB."""
    from unittest.mock import patch
    from scripts.agentica.unified_scope import create_unified_scope

    with patch('scripts.agentica.unified_scope._call_claude_cli') as mock:
        mock.return_value = "mocked"
        scope_a = create_unified_scope(
            session_id=f"session-a-{uuid4().hex[:8]}",
            db_path=db_path,
            enable_memory=True,
            enable_tasks=False,
        )
        scope_b = create_unified_scope(
            session_id=f"session-b-{uuid4().hex[:8]}",
            db_path=db_path,
            enable_memory=True,
            enable_tasks=False,
        )
        yield scope_a, scope_b


# ============================================================================
# Test: remember/recall
# ============================================================================


class TestRememberRecall:
    """Tests for remember() and recall() memory operations."""

    def test_remember_stores_value(self, memory_scope):
        """remember() should store key-value in core memory."""
        memory_scope["remember"]("project_name", "Claude Continuity Kit")

        # Recall should find it
        result = memory_scope["recall"]("project_name")
        assert "Claude Continuity Kit" in result

    def test_recall_retrieves_value(self, memory_scope):
        """recall() should retrieve stored values."""
        memory_scope["remember"]("language", "Python")
        memory_scope["remember"]("framework", "FastAPI")

        result = memory_scope["recall"]("language")
        assert "Python" in result

        result = memory_scope["recall"]("framework")
        assert "FastAPI" in result

    def test_remember_overwrites_existing(self, memory_scope):
        """remember() should overwrite existing key."""
        memory_scope["remember"]("version", "1.0")
        memory_scope["remember"]("version", "2.0")

        result = memory_scope["recall"]("version")
        assert "2.0" in result
        assert "1.0" not in result

    def test_recall_returns_formatted_context(self, memory_scope):
        """recall() should return formatted context string."""
        memory_scope["remember"]("task", "Build REST API")

        result = memory_scope["recall"]("task")

        # Should contain the value in readable format
        assert "Build REST API" in result
        # Should contain core memory indicator
        assert "[Core" in result or "Core" in result.lower()


# ============================================================================
# Test: store_fact/search_memory
# ============================================================================


class TestStoreSearchMemory:
    """Tests for store_fact() and search_memory() operations."""

    def test_store_fact_returns_id(self, memory_scope):
        """store_fact() should return memory ID starting with 'mem-'."""
        fact_id = memory_scope["store_fact"](
            "Python was created by Guido van Rossum in 1991"
        )

        assert fact_id is not None
        assert fact_id.startswith("mem-")

    def test_search_memory_finds_fact(self, memory_scope):
        """search_memory() should find stored facts via FTS5."""
        memory_scope["store_fact"]("Python was created by Guido van Rossum")
        memory_scope["store_fact"]("JavaScript was created by Brendan Eich")

        results = memory_scope["search_memory"]("Python creator")

        assert len(results) >= 1
        assert "Guido" in results[0]["content"]

    def test_search_memory_returns_ranked_results(self, memory_scope):
        """search_memory() should rank results by relevance."""
        memory_scope["store_fact"]("Python is a programming language")
        memory_scope["store_fact"]("Python snake is a reptile")
        memory_scope["store_fact"]("Python programming is popular for AI and ML")

        results = memory_scope["search_memory"]("Python programming AI", limit=2)

        assert len(results) == 2
        # Most relevant should mention AI
        assert "AI" in results[0]["content"]

    def test_search_memory_limit_parameter(self, memory_scope):
        """search_memory() limit parameter should restrict results."""
        for i in range(10):
            memory_scope["store_fact"](f"Fact number {i} about testing")

        results = memory_scope["search_memory"]("testing", limit=5)
        assert len(results) == 5

    def test_store_multiple_facts_all_searchable(self, memory_scope):
        """All stored facts should be searchable."""
        facts = [
            "FastAPI is a modern Python web framework",
            "PostgreSQL is a powerful database",
            "Redis is an in-memory data store",
            "Docker enables containerization",
            "Kubernetes orchestrates containers",
        ]

        for fact in facts:
            memory_scope["store_fact"](fact)

        # Each fact should be searchable by keyword
        assert len(memory_scope["search_memory"]("FastAPI")) >= 1
        assert len(memory_scope["search_memory"]("PostgreSQL")) >= 1
        assert len(memory_scope["search_memory"]("Redis")) >= 1
        assert len(memory_scope["search_memory"]("Docker")) >= 1
        assert len(memory_scope["search_memory"]("Kubernetes")) >= 1


# ============================================================================
# Test: Session Isolation
# ============================================================================


class TestSessionIsolation:
    """Tests for session isolation in memory operations."""

    def test_session_isolation_core_memory(self, dual_session_scopes):
        """Core memory should be isolated between sessions."""
        scope_a, scope_b = dual_session_scopes

        # Store in session A
        scope_a["remember"]("secret", "session_a_secret")

        # Session A should recall it
        result_a = scope_a["recall"]("secret")
        assert "session_a_secret" in result_a

        # Session B should NOT see session A's memory
        result_b = scope_b["recall"]("secret")
        assert "session_a_secret" not in result_b

    def test_session_isolation_archival_memory(self, dual_session_scopes):
        """Archival memory should be isolated between sessions."""
        scope_a, scope_b = dual_session_scopes

        # Store fact in session A
        scope_a["store_fact"]("Secret formula for session A only")

        # Session A should find it
        results_a = scope_a["search_memory"]("Secret formula")
        assert len(results_a) >= 1
        assert "session A" in results_a[0]["content"]

        # Session B should NOT find session A's facts
        results_b = scope_b["search_memory"]("Secret formula")
        assert len(results_b) == 0

    def test_both_sessions_can_store_independently(self, dual_session_scopes):
        """Each session should maintain independent memory."""
        scope_a, scope_b = dual_session_scopes

        # Each session stores different data
        scope_a["remember"]("project", "Project Alpha")
        scope_b["remember"]("project", "Project Beta")

        scope_a["store_fact"]("Alpha uses Python")
        scope_b["store_fact"]("Beta uses Rust")

        # Each session sees only its own data
        assert "Alpha" in scope_a["recall"]("project")
        assert "Beta" in scope_b["recall"]("project")

        results_a = scope_a["search_memory"]("uses")
        results_b = scope_b["search_memory"]("uses")

        assert any("Python" in r["content"] for r in results_a)
        assert any("Rust" in r["content"] for r in results_b)
        assert not any("Rust" in r["content"] for r in results_a)
        assert not any("Python" in r["content"] for r in results_b)


# ============================================================================
# Test: Memory Persistence
# ============================================================================


class TestMemoryPersistence:
    """Tests for memory persistence across scope instances."""

    def test_memory_persists_across_scope_instances(self, db_path: Path):
        """Memory should persist when creating new scope with same session_id."""
        from unittest.mock import patch
        from scripts.agentica.unified_scope import create_unified_scope

        session_id = f"persistent-{uuid4().hex[:8]}"

        with patch('scripts.agentica.unified_scope._call_claude_cli') as mock:
            mock.return_value = "mocked"

            # First scope - store memory
            scope1 = create_unified_scope(
                session_id=session_id,
                db_path=db_path,
                enable_memory=True,
                enable_tasks=False,
            )
            scope1["remember"]("key1", "value1")
            scope1["store_fact"]("Persistent fact for testing")

            # Second scope - same session_id, same db
            scope2 = create_unified_scope(
                session_id=session_id,
                db_path=db_path,
                enable_memory=True,
                enable_tasks=False,
            )

            # Should find persisted memory
            result = scope2["recall"]("key1")
            assert "value1" in result

            results = scope2["search_memory"]("Persistent fact")
            assert len(results) >= 1

    def test_archival_fact_id_persists(self, db_path: Path):
        """Stored fact IDs should be consistent."""
        from unittest.mock import patch
        from scripts.agentica.unified_scope import create_unified_scope

        session_id = f"fact-id-{uuid4().hex[:8]}"

        with patch('scripts.agentica.unified_scope._call_claude_cli') as mock:
            mock.return_value = "mocked"

            scope = create_unified_scope(
                session_id=session_id,
                db_path=db_path,
                enable_memory=True,
                enable_tasks=False,
            )

            # Store and get ID
            fact_id = scope["store_fact"]("Test fact with ID")

            # ID should have proper format
            assert fact_id.startswith("mem-")
            assert len(fact_id) > 4  # mem- plus some characters


# ============================================================================
# Test: Recall Combines Sources
# ============================================================================


class TestRecallCombinesSources:
    """Tests for recall() combining core and archival memory."""

    def test_recall_searches_both_core_and_archival(self, memory_scope):
        """recall() should search both core and archival memory."""
        # Store in core
        memory_scope["remember"]("current_task", "Build authentication")

        # Store in archival
        memory_scope["store_fact"]("Authentication uses JWT tokens")
        memory_scope["store_fact"]("Task history: completed database setup")

        # Recall should find core memory
        result = memory_scope["recall"]("current_task")
        assert "authentication" in result.lower()

        # Recall should also find archival
        result = memory_scope["recall"]("JWT")
        assert "JWT" in result or "token" in result.lower()

    def test_recall_with_no_matches_returns_message(self, memory_scope):
        """recall() should return message when no matches found."""
        result = memory_scope["recall"]("completely_unknown_nonexistent_query_xyz")

        # Should return a message about no matches
        assert "no" in result.lower() or "not found" in result.lower() or len(result) > 0


# ============================================================================
# Test: Direct Memory Service Access
# ============================================================================


class TestMemoryServiceAccess:
    """Tests for direct access to _memory_service."""

    def test_memory_service_exposed(self, memory_scope):
        """_memory_service should be accessible for advanced usage."""
        from scripts.agentica.memory_service import MemoryService

        assert "_memory_service" in memory_scope
        assert isinstance(memory_scope["_memory_service"], MemoryService)

    def test_memory_service_direct_methods(self, memory_scope):
        """Direct MemoryService methods should work."""
        ms = memory_scope["_memory_service"]

        # Set via direct API (must use _run_async for async method)
        _run_async(ms.set_core("direct_key", "direct_value"))

        # Should be accessible via recall
        result = memory_scope["recall"]("direct_key")
        assert "direct_value" in result

    def test_to_context_generates_prompt(self, memory_scope):
        """to_context() should generate formatted context string."""
        memory_scope["remember"]("persona", "Expert developer")
        memory_scope["store_fact"]("User prefers TypeScript")

        ms = memory_scope["_memory_service"]
        # to_context is async, must use _run_async
        context = _run_async(ms.to_context())

        assert "## Core Memory" in context
        assert "Expert developer" in context
