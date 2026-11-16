"""Tests for agent scope injection with memory and task functions."""

import pytest
from pathlib import Path


class TestScopeInjection:
    """Test memory/task function injection into agent scope."""

    @pytest.fixture
    def db_path(self, tmp_path):
        return tmp_path / "test.db"

    def test_create_agent_scope_includes_memory(self, db_path):
        """Agent scope should include memory functions."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(session_id="test", db_path=db_path)

        assert "remember" in scope
        assert "recall" in scope
        assert "search_memory" in scope
        assert callable(scope["remember"])

    def test_create_agent_scope_includes_tasks(self, db_path):
        """Agent scope should include task functions."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(session_id="test", db_path=db_path)

        assert "create_task" in scope
        assert "complete_task" in scope
        assert "get_ready_tasks" in scope
        assert callable(scope["create_task"])

    def test_remember_and_recall_work(self, db_path):
        """Should store and retrieve via scope functions."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(session_id="test", db_path=db_path)

        scope["remember"]("user_preference", "Prefers Python over JavaScript")
        result = scope["recall"]("user_preference")

        assert "Python" in result

    def test_task_functions_work(self, db_path):
        """Should create and complete tasks via scope functions."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(session_id="test", db_path=db_path)

        task_id = scope["create_task"]("Research API options")
        ready = scope["get_ready_tasks"]()

        assert task_id in ready

        scope["complete_task"](task_id)
        ready = scope["get_ready_tasks"]()

        assert task_id not in ready

    def test_scope_shares_session_id(self, db_path):
        """Memory and tasks should share session isolation."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope1 = create_agent_scope(session_id="session1", db_path=db_path)
        scope2 = create_agent_scope(session_id="session2", db_path=db_path)

        scope1["remember"]("key", "value1")
        scope2["remember"]("key", "value2")

        assert "value1" in scope1["recall"]("key")
        assert "value2" in scope2["recall"]("key")

    def test_include_memory_flag(self, db_path):
        """Should respect include_memory flag."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(
            session_id="test", db_path=db_path, include_memory=False
        )

        assert "remember" not in scope
        assert "recall" not in scope
        assert "create_task" in scope  # Tasks still included

    def test_include_tasks_flag(self, db_path):
        """Should respect include_tasks flag."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(
            session_id="test", db_path=db_path, include_tasks=False
        )

        assert "create_task" not in scope
        assert "complete_task" not in scope
        assert "remember" in scope  # Memory still included

    def test_extra_scope_items(self, db_path):
        """Should merge extra scope items."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        def custom_tool(x: str) -> str:
            return f"processed: {x}"

        scope = create_agent_scope(
            session_id="test",
            db_path=db_path,
            extra_scope={"custom_tool": custom_tool, "config": {"key": "value"}},
        )

        assert "custom_tool" in scope
        assert "config" in scope
        assert callable(scope["custom_tool"])
        assert scope["custom_tool"]("test") == "processed: test"

    def test_store_fact_function(self, db_path):
        """Should include store_fact for archival memory."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(session_id="test", db_path=db_path)

        assert "store_fact" in scope
        memory_id = scope["store_fact"]("User prefers dark mode")
        assert memory_id.startswith("mem-")

        results = scope["search_memory"]("dark mode")
        assert len(results) > 0
        assert "dark mode" in results[0]["content"]

    def test_get_all_tasks_function(self, db_path):
        """Should include get_all_tasks function."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(session_id="test", db_path=db_path)

        assert "get_all_tasks" in scope
        task1 = scope["create_task"]("Task 1")
        task2 = scope["create_task"]("Task 2")

        all_tasks = scope["get_all_tasks"]()
        assert len(all_tasks) == 2
        assert any(t["id"] == task1 for t in all_tasks)
        assert any(t["id"] == task2 for t in all_tasks)

    async def test_advanced_access_services(self, db_path):
        """Should expose underlying services for advanced access."""
        from scripts.agentica_patterns.agent_scope import create_agent_scope

        scope = create_agent_scope(session_id="test", db_path=db_path)

        assert "_memory_service" in scope
        assert "_task_graph" in scope

        # Should be actual service instances
        memory = scope["_memory_service"]
        tasks = scope["_task_graph"]

        # Test direct service access (async)
        await memory.set_core("test_key", "test_value")
        assert await memory.get_core("test_key") == "test_value"

        task_id = tasks.add_task("Direct task")
        assert task_id in tasks.get_ready_tasks()
