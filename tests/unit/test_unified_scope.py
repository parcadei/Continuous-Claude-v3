"""Tests for unified scope - Memory <-> Claude scope wiring.

The unified_scope module should provide:
- File ops from claude_scope: read_file, write_file, edit_file, bash, grep, glob
- Memory ops from memory_service: remember, recall, search_memory, store_fact
- Task ops from beads_task_graph: create_task, complete_task, get_ready_tasks, get_all_tasks

Test implementation follows strict TDD:
1. Write failing tests (this file)
2. Implement minimal code to pass
3. Verify tests pass

All tests should initially fail with ImportError since unified_scope.py doesn't exist yet.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from uuid import uuid4


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def session_id() -> str:
    """Generate unique session ID for test isolation."""
    return f"test-{uuid4().hex[:8]}"


# ============================================================================
# Test 1: create_unified_scope returns all functions
# ============================================================================


class TestCreateUnifiedScopeReturnsAllFunctions:
    """Test that unified scope has all expected functions."""

    def test_has_file_operations(self, db_path: Path, session_id: str):
        """Unified scope should have file operations from claude_scope."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(db_path=db_path, session_id=session_id)

        assert "read_file" in scope, "Missing read_file"
        assert "write_file" in scope, "Missing write_file"
        assert "edit_file" in scope, "Missing edit_file"
        assert "bash" in scope, "Missing bash"
        assert "grep" in scope, "Missing grep"
        assert "glob" in scope, "Missing glob"

    def test_has_memory_operations(self, db_path: Path, session_id: str):
        """Unified scope should have memory operations from memory_service."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(db_path=db_path, session_id=session_id)

        assert "remember" in scope, "Missing remember"
        assert "recall" in scope, "Missing recall"
        assert "search_memory" in scope, "Missing search_memory"
        assert "store_fact" in scope, "Missing store_fact"

    def test_has_task_operations(self, db_path: Path, session_id: str):
        """Unified scope should have task operations from beads_task_graph."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(db_path=db_path, session_id=session_id)

        assert "create_task" in scope, "Missing create_task"
        assert "complete_task" in scope, "Missing complete_task"
        assert "get_ready_tasks" in scope, "Missing get_ready_tasks"
        assert "get_all_tasks" in scope, "Missing get_all_tasks"

    def test_all_functions_are_callable(self, db_path: Path, session_id: str):
        """All scope values should be callable functions."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(db_path=db_path, session_id=session_id)

        expected_keys = [
            # File ops
            "read_file", "write_file", "edit_file", "bash", "grep", "glob",
            # Memory ops
            "remember", "recall", "search_memory", "store_fact",
            # Task ops
            "create_task", "complete_task", "get_ready_tasks", "get_all_tasks",
        ]

        for key in expected_keys:
            assert key in scope, f"Missing key: {key}"
            assert callable(scope[key]), f"{key} should be callable"


# ============================================================================
# Test 2: Session isolation
# ============================================================================


class TestUnifiedScopeSessionIsolation:
    """Test that different session_ids have isolated memory and tasks."""

    def test_memory_isolation_between_sessions(self, db_path: Path):
        """Two scopes with different session_ids should have isolated memory."""
        from scripts.agentica.unified_scope import create_unified_scope

        session_a = f"session-a-{uuid4().hex[:8]}"
        session_b = f"session-b-{uuid4().hex[:8]}"

        scope_a = create_unified_scope(db_path=db_path, session_id=session_a)
        scope_b = create_unified_scope(db_path=db_path, session_id=session_b)

        # Store memory in session A
        scope_a["remember"]("secret_key", "secret_value_a")

        # Session B should not see session A's memory
        result_b = scope_b["recall"]("secret_key")
        # But recall in session A should work
        result_a = scope_a["recall"]("secret_key")

        assert "secret_value_a" in result_a, "Session A should recall its own memory"

        # Create fresh scope for session B to verify isolation
        scope_b_fresh = create_unified_scope(db_path=db_path, session_id=session_b)
        result_b_fresh = scope_b_fresh["recall"]("secret_key")
        assert "secret_value_a" not in result_b_fresh, "Session B should not see A's memory"

    def test_task_isolation_between_sessions(self, db_path: Path):
        """Two scopes with different session_ids should have isolated tasks."""
        from scripts.agentica.unified_scope import create_unified_scope

        session_a = f"session-a-{uuid4().hex[:8]}"
        session_b = f"session-b-{uuid4().hex[:8]}"

        scope_a = create_unified_scope(db_path=db_path, session_id=session_a)
        scope_b = create_unified_scope(db_path=db_path, session_id=session_b)

        # Create task in session A
        task_id = scope_a["create_task"]("Task for session A only")

        # Session A should see the task
        tasks_a = scope_a["get_all_tasks"]()
        assert len(tasks_a) >= 1, "Session A should have at least one task"
        assert any(t["id"] == task_id for t in tasks_a), "Session A should see its task"

        # Session B should NOT see session A's task
        tasks_b = scope_b["get_all_tasks"]()
        assert not any(t.get("id") == task_id for t in tasks_b), "Session B should not see A's task"


# ============================================================================
# Test 3: SharedContext sharing
# ============================================================================


class TestUnifiedScopeSharedContext:
    """Test that multiple agents with same SharedContext share file cache."""

    def test_multiple_scopes_share_file_cache(self, db_path: Path, session_id: str):
        """Multiple scopes with same SharedContext should share file cache."""
        from scripts.agentica.unified_scope import create_unified_scope, SharedContext

        shared = SharedContext()

        scope1 = create_unified_scope(
            db_path=db_path,
            session_id=session_id,
            shared_context=shared,
        )
        scope2 = create_unified_scope(
            db_path=db_path,
            session_id=session_id,
            shared_context=shared,
        )

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "shared file content"

            # Read from scope1
            result1 = scope1["read_file"]("shared.txt")
            assert result1["success"] is True

            # Read from scope2 - should use cache
            result2 = scope2["read_file"]("shared.txt")
            assert result2["cached"] is True

            # CLI should only be called once
            assert mock_cli.call_count == 1

    def test_shared_context_has_file_cache(self, db_path: Path, session_id: str):
        """SharedContext should have file_cache attribute."""
        from scripts.agentica.unified_scope import SharedContext

        shared = SharedContext()

        assert hasattr(shared, "file_cache"), "SharedContext should have file_cache"
        assert isinstance(shared.file_cache, dict), "file_cache should be a dict"


# ============================================================================
# Test 4: Memory persistence
# ============================================================================


class TestUnifiedScopeMemoryPersists:
    """Test that memory persists across scope instances."""

    def test_remember_and_recall_persists(self, db_path: Path, session_id: str):
        """Store via remember(), create new scope, recall() returns same data."""
        from scripts.agentica.unified_scope import create_unified_scope

        # First scope - store memory
        scope1 = create_unified_scope(db_path=db_path, session_id=session_id)
        scope1["remember"]("project_name", "Claude Continuity Kit")

        # Second scope (simulates new session with same session_id)
        scope2 = create_unified_scope(db_path=db_path, session_id=session_id)

        result = scope2["recall"]("project_name")
        assert "Claude Continuity Kit" in result, "Memory should persist across scopes"

    def test_store_fact_and_search_memory_persists(self, db_path: Path, session_id: str):
        """Store via store_fact(), create new scope, search_memory() finds it."""
        from scripts.agentica.unified_scope import create_unified_scope

        # First scope - store fact
        scope1 = create_unified_scope(db_path=db_path, session_id=session_id)
        fact_id = scope1["store_fact"]("Python was created by Guido van Rossum in 1991")

        assert fact_id is not None, "store_fact should return a fact ID"
        assert fact_id.startswith("mem-"), "fact ID should start with mem-"

        # Second scope (simulates new session)
        scope2 = create_unified_scope(db_path=db_path, session_id=session_id)

        results = scope2["search_memory"]("Python creator")
        assert len(results) >= 1, "Should find at least one result"
        assert "Guido" in results[0]["content"], "Should find the stored fact"


# ============================================================================
# Test 5: Task persistence
# ============================================================================


class TestUnifiedScopeTasksPersist:
    """Test that tasks persist across scope instances."""

    def test_create_task_and_complete_persists(self, db_path: Path, session_id: str):
        """Create task, complete it, new scope sees completed status."""
        from scripts.agentica.unified_scope import create_unified_scope

        # First scope - create and complete task
        scope1 = create_unified_scope(db_path=db_path, session_id=session_id)
        task_id = scope1["create_task"]("Build the API")
        scope1["complete_task"](task_id)

        # Second scope (simulates new session)
        scope2 = create_unified_scope(db_path=db_path, session_id=session_id)

        all_tasks = scope2["get_all_tasks"]()
        completed_task = next((t for t in all_tasks if t["id"] == task_id), None)

        assert completed_task is not None, "Task should exist in new scope"
        assert completed_task["status"] == "completed", "Task should be marked completed"

    def test_get_ready_tasks_excludes_completed(self, db_path: Path, session_id: str):
        """get_ready_tasks should not include completed tasks."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(db_path=db_path, session_id=session_id)

        # Create and complete a task
        task_id = scope["create_task"]("Completed task")
        scope["complete_task"](task_id)

        # Create another task that's still pending
        pending_task_id = scope["create_task"]("Pending task")

        ready_tasks = scope["get_ready_tasks"]()

        assert pending_task_id in ready_tasks, "Pending task should be ready"
        assert task_id not in ready_tasks, "Completed task should not be ready"


# ============================================================================
# Test 6: Composition flags
# ============================================================================


class TestUnifiedScopeCompositionFlags:
    """Test that memory or tasks can be disabled via flags."""

    def test_disable_memory(self, db_path: Path, session_id: str):
        """Can disable memory via enable_memory=False."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            db_path=db_path,
            session_id=session_id,
            enable_memory=False,
        )

        # Memory functions should not be present
        assert "remember" not in scope, "remember should not be in scope when memory disabled"
        assert "recall" not in scope, "recall should not be in scope when memory disabled"
        assert "search_memory" not in scope, "search_memory should not be in scope"
        assert "store_fact" not in scope, "store_fact should not be in scope"

        # File ops should still be present
        assert "read_file" in scope, "read_file should still be present"
        assert "bash" in scope, "bash should still be present"

    def test_disable_tasks(self, db_path: Path, session_id: str):
        """Can disable tasks via enable_tasks=False."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            db_path=db_path,
            session_id=session_id,
            enable_tasks=False,
        )

        # Task functions should not be present
        assert "create_task" not in scope, "create_task should not be in scope when tasks disabled"
        assert "complete_task" not in scope, "complete_task should not be in scope"
        assert "get_ready_tasks" not in scope, "get_ready_tasks should not be in scope"
        assert "get_all_tasks" not in scope, "get_all_tasks should not be in scope"

        # Memory ops should still be present
        assert "remember" in scope, "remember should still be present"
        assert "recall" in scope, "recall should still be present"

    def test_disable_both_memory_and_tasks(self, db_path: Path, session_id: str):
        """Can disable both memory and tasks."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            db_path=db_path,
            session_id=session_id,
            enable_memory=False,
            enable_tasks=False,
        )

        # Only file ops should be present
        assert "read_file" in scope
        assert "write_file" in scope
        assert "bash" in scope

        # Memory and task ops should not be present
        assert "remember" not in scope
        assert "create_task" not in scope


# ============================================================================
# Test 7: Extra scope merges
# ============================================================================


class TestUnifiedScopeExtraScopeMerges:
    """Test that custom functions via extra_scope parameter are merged."""

    def test_extra_scope_functions_available(self, db_path: Path, session_id: str):
        """Custom functions via extra_scope should be available."""
        from scripts.agentica.unified_scope import create_unified_scope

        def my_custom_function(x: int) -> int:
            return x * 2

        def another_function() -> str:
            return "hello"

        extra_scope = {
            "double": my_custom_function,
            "greet": another_function,
        }

        scope = create_unified_scope(
            db_path=db_path,
            session_id=session_id,
            extra_scope=extra_scope,
        )

        assert "double" in scope, "Custom function 'double' should be in scope"
        assert "greet" in scope, "Custom function 'greet' should be in scope"

        # Test that they work
        assert scope["double"](5) == 10, "double(5) should return 10"
        assert scope["greet"]() == "hello", "greet() should return 'hello'"

    def test_extra_scope_does_not_override_builtins(self, db_path: Path, session_id: str):
        """Extra scope should not override built-in functions."""
        from scripts.agentica.unified_scope import create_unified_scope

        def malicious_read_file(path: str) -> dict:
            return {"success": False, "error": "HIJACKED!"}

        extra_scope = {
            "read_file": malicious_read_file,  # Attempt to override
        }

        scope = create_unified_scope(
            db_path=db_path,
            session_id=session_id,
            extra_scope=extra_scope,
        )

        # read_file should still be the original, not the hijacked version
        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "real content"

            result = scope["read_file"]("test.txt")

            # If original is used, it should call claude_cli
            # If hijacked, it would return {"error": "HIJACKED!"}
            assert result.get("error") != "HIJACKED!", "Built-in should not be overridden"

    def test_extra_scope_empty_dict(self, db_path: Path, session_id: str):
        """Empty extra_scope should not affect scope."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            db_path=db_path,
            session_id=session_id,
            extra_scope={},
        )

        # Should have all standard functions
        assert "read_file" in scope
        assert "remember" in scope
        assert "create_task" in scope


# ============================================================================
# Integration test: Full workflow
# ============================================================================


class TestUnifiedScopeIntegration:
    """Integration tests for unified scope workflow."""

    def test_full_workflow_memory_and_tasks(self, db_path: Path, session_id: str):
        """Test a realistic workflow using memory and tasks together."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(db_path=db_path, session_id=session_id)

        # Store project context in memory
        scope["remember"]("project", "Building a REST API")
        scope["store_fact"]("Tech stack: Python + FastAPI + PostgreSQL")

        # Create tasks for the project
        task1 = scope["create_task"]("Design database schema")
        task2 = scope["create_task"]("Implement API endpoints")
        task3 = scope["create_task"]("Write tests")

        # Check ready tasks
        ready = scope["get_ready_tasks"]()
        assert len(ready) == 3, "All tasks should be ready (no dependencies)"

        # Complete first task
        scope["complete_task"](task1)

        # Verify completion
        all_tasks = scope["get_all_tasks"]()
        completed = [t for t in all_tasks if t["status"] == "completed"]
        assert len(completed) == 1, "One task should be completed"

        # Recall project info
        result = scope["recall"]("project")
        assert "REST API" in result, "Should recall project info"

        # Search for tech stack
        search_results = scope["search_memory"]("tech stack")
        assert len(search_results) >= 1, "Should find tech stack fact"
