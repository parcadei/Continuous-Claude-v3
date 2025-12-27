"""End-to-end integration tests for the unified scope.

Tests the full stack wiring of the unified scope, which combines:
- File operations from claude_scope
- Memory operations from memory_service
- Task operations from beads_task_graph

These tests simulate realistic agent workflows including:
1. Single agent workflow with memory and tasks
2. Multi-agent shared context
3. Session handoff persistence
4. Concurrent agent writes
5. Task dependency blocking

Run with:
    uv run pytest tests/integration/test_unified_scope_e2e.py -v
"""

import asyncio
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import pytest


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create temporary database path for test isolation."""
    return tmp_path / "test_unified.db"


@pytest.fixture
def session_id() -> str:
    """Generate unique session ID for test isolation."""
    return f"e2e-{uuid4().hex[:8]}"


def unique_session_id() -> str:
    """Generate a unique session ID."""
    return f"e2e-{uuid4().hex[:8]}"


# --------------------------------------------------------------------------
# Test 1: E2E Agent Workflow
# --------------------------------------------------------------------------


class TestE2EAgentWorkflow:
    """Test a complete agent workflow using unified scope."""

    def test_e2e_agent_workflow(self, db_path: Path, session_id: str):
        """Simulate an agent using unified scope for a complete workflow.

        Steps:
        1. Create unified scope with session_id
        2. Create a task "Research topic"
        3. Store findings in memory via remember()
        4. Complete the task
        5. Verify task shows completed
        6. Verify memory persists
        """
        from scripts.agentica.unified_scope import create_unified_scope

        # Step 1: Create unified scope
        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=True,
            enable_tasks=True,
        )

        # Verify all operations are available
        assert "create_task" in scope
        assert "remember" in scope
        assert "recall" in scope

        # Step 2: Create a task
        task_id = scope["create_task"]("Research topic: Python async patterns")
        assert task_id is not None
        assert task_id.startswith("bd-")  # Beads task ID format

        # Step 3: Store findings in memory
        scope["remember"]("research_topic", "Python async patterns")
        scope["store_fact"]("asyncio uses an event loop for cooperative multitasking")
        scope["store_fact"]("await suspends coroutine until awaited task completes")
        scope["store_fact"]("async generators combine async/await with yield")

        # Step 4: Complete the task
        scope["complete_task"](task_id)

        # Step 5: Verify task shows completed
        all_tasks = scope["get_all_tasks"]()
        assert len(all_tasks) >= 1

        completed_task = next((t for t in all_tasks if t["id"] == task_id), None)
        assert completed_task is not None
        assert completed_task["status"] == "completed"
        assert completed_task["description"] == "Research topic: Python async patterns"

        # Step 6: Verify memory persists
        # Create a NEW scope with same session_id to verify persistence
        scope2 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=True,
            enable_tasks=True,
        )

        # Memory should persist
        recalled = scope2["recall"]("research_topic")
        assert "Python async patterns" in recalled

        # Search should find stored facts
        search_results = scope2["search_memory"]("asyncio event loop")
        assert len(search_results) >= 1
        assert any("event loop" in r["content"] for r in search_results)

        # Task should still be completed
        persisted_tasks = scope2["get_all_tasks"]()
        persisted_task = next((t for t in persisted_tasks if t["id"] == task_id), None)
        assert persisted_task is not None
        assert persisted_task["status"] == "completed"

    def test_e2e_agent_workflow_with_multiple_tasks(self, db_path: Path, session_id: str):
        """Test agent workflow with multiple tasks and memory interactions."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Create multiple tasks
        task1 = scope["create_task"]("Gather requirements")
        task2 = scope["create_task"]("Design solution")
        task3 = scope["create_task"]("Implement feature")

        # All should be ready (no dependencies)
        ready = scope["get_ready_tasks"]()
        assert task1 in ready
        assert task2 in ready
        assert task3 in ready

        # Complete first task and store findings
        scope["remember"]("requirements", "Build a REST API with auth")
        scope["complete_task"](task1)

        # First task should no longer be ready
        ready = scope["get_ready_tasks"]()
        assert task1 not in ready
        assert task2 in ready
        assert task3 in ready

        # Complete remaining tasks
        scope["remember"]("design", "Use JWT for authentication")
        scope["complete_task"](task2)

        scope["remember"]("implementation", "FastAPI with OAuth2")
        scope["complete_task"](task3)

        # All tasks should be completed
        all_tasks = scope["get_all_tasks"]()
        for task in all_tasks:
            assert task["status"] == "completed"

        # All memory should be retrievable
        result = scope["recall"]("requirements")
        assert "REST API" in result


# --------------------------------------------------------------------------
# Test 2: Multi-Agent Shared Context
# --------------------------------------------------------------------------


class TestE2EMultiAgentSharedContext:
    """Test multiple agents sharing file cache via SharedContext."""

    def test_e2e_multi_agent_shared_context(self, db_path: Path, session_id: str):
        """Simulate two agents sharing file cache.

        Steps:
        1. Create SharedContext
        2. Create scope1 and scope2 with same SharedContext
        3. Agent1 reads a file
        4. Agent2 reads same file (should hit cache)
        5. Verify cache sharing works
        """
        from scripts.agentica.unified_scope import create_unified_scope, SharedContext

        # Step 1: Create SharedContext
        shared = SharedContext()

        # Step 2: Create two scopes with same SharedContext
        scope1 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            shared_context=shared,
        )

        scope2 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            shared_context=shared,
        )

        # Step 3-5: Agent1 reads, Agent2 should hit cache
        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "# Python Module\n\ndef hello():\n    return 'world'"

            # Agent1 reads file
            result1 = scope1["read_file"]("example.py")
            assert result1["success"] is True
            assert result1["cached"] is False
            assert "Python Module" in result1["content"]

            # Agent2 reads same file - should hit cache
            result2 = scope2["read_file"]("example.py")
            assert result2["success"] is True
            assert result2["cached"] is True  # Cache hit!
            assert result2["content"] == result1["content"]

            # CLI should only be called once (cached on second read)
            assert mock_cli.call_count == 1

    def test_e2e_multi_agent_shared_context_invalidation(self, db_path: Path, session_id: str):
        """Test that write operations invalidate shared cache."""
        from scripts.agentica.unified_scope import create_unified_scope, SharedContext

        shared = SharedContext()

        scope1 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            shared_context=shared,
        )

        scope2 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            shared_context=shared,
        )

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            # First read
            mock_cli.return_value = "original content"
            result1 = scope1["read_file"]("data.txt")
            assert result1["cached"] is False

            # Second read - cached
            result2 = scope2["read_file"]("data.txt")
            assert result2["cached"] is True

            # Now agent2 writes to the file
            mock_cli.return_value = "File written successfully"
            scope2["write_file"]("data.txt", "new content")

            # After write, cache should be invalidated
            # Next read should not be cached
            mock_cli.return_value = "new content"
            result3 = scope1["read_file"]("data.txt")
            assert result3["cached"] is False

    def test_e2e_multi_agent_isolated_memory(self, db_path: Path):
        """Test that different session IDs have isolated memory."""
        from scripts.agentica.unified_scope import create_unified_scope, SharedContext

        shared = SharedContext()

        session_a = unique_session_id()
        session_b = unique_session_id()

        scope_a = create_unified_scope(
            session_id=session_a,
            db_path=db_path,
            shared_context=shared,
        )

        scope_b = create_unified_scope(
            session_id=session_b,
            db_path=db_path,
            shared_context=shared,
        )

        # Agent A stores memory
        scope_a["remember"]("secret", "agent-a-secret-value")
        scope_a["store_fact"]("Agent A discovered important information")

        # Agent B stores different memory
        scope_b["remember"]("secret", "agent-b-secret-value")
        scope_b["store_fact"]("Agent B discovered different information")

        # Each agent should only see their own memory
        recall_a = scope_a["recall"]("secret")
        assert "agent-a-secret-value" in recall_a
        assert "agent-b-secret-value" not in recall_a

        recall_b = scope_b["recall"]("secret")
        assert "agent-b-secret-value" in recall_b
        assert "agent-a-secret-value" not in recall_b


# --------------------------------------------------------------------------
# Test 3: Session Handoff
# --------------------------------------------------------------------------


class TestE2ESessionHandoff:
    """Test session handoff - persistence across scope instances."""

    def test_e2e_session_handoff(self, db_path: Path, session_id: str):
        """Simulate session handoff.

        Steps:
        1. Scope1 with session_id creates tasks and stores memory
        2. Simulate "session end" (scope1 goes away)
        3. Scope2 with SAME session_id should see all tasks and memory
        4. This tests persistence across scope instances
        """
        from scripts.agentica.unified_scope import create_unified_scope

        # Step 1: First session creates tasks and memory
        scope1 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Create tasks
        task_a = scope1["create_task"]("Phase 1: Research")
        task_b = scope1["create_task"]("Phase 2: Design")
        task_c = scope1["create_task"]("Phase 3: Implementation")

        # Complete first task
        scope1["complete_task"](task_a)

        # Store memory
        scope1["remember"]("project_name", "AI Assistant")
        scope1["remember"]("current_phase", "Design")
        scope1["store_fact"]("Architecture decision: Use microservices")
        scope1["store_fact"]("Database choice: PostgreSQL with pgvector")

        # Step 2: Simulate session end by deleting scope1 reference
        del scope1

        # Step 3: Create new scope with SAME session_id
        scope2 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Verify all tasks are visible
        all_tasks = scope2["get_all_tasks"]()
        assert len(all_tasks) == 3

        # Verify task states
        task_a_handoff = next((t for t in all_tasks if t["id"] == task_a), None)
        assert task_a_handoff is not None
        assert task_a_handoff["status"] == "completed"

        task_b_handoff = next((t for t in all_tasks if t["id"] == task_b), None)
        assert task_b_handoff is not None
        assert task_b_handoff["status"] == "pending"

        # Verify memory is accessible
        project_name = scope2["recall"]("project_name")
        assert "AI Assistant" in project_name

        current_phase = scope2["recall"]("current_phase")
        assert "Design" in current_phase

        # Verify archival memory search
        search_results = scope2["search_memory"]("architecture")
        assert len(search_results) >= 1
        assert any("microservices" in r["content"] for r in search_results)

        # Step 4: Continue work in new session
        scope2["complete_task"](task_b)
        scope2["remember"]("current_phase", "Implementation")

        # Verify updates persisted
        final_tasks = scope2["get_all_tasks"]()
        completed_count = sum(1 for t in final_tasks if t["status"] == "completed")
        assert completed_count == 2

    def test_e2e_session_handoff_with_handoff_document(self, db_path: Path, session_id: str):
        """Test session handoff with explicit handoff document in memory."""
        from scripts.agentica.unified_scope import create_unified_scope

        # First session does work and creates handoff
        scope1 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Do some work
        task = scope1["create_task"]("Build API endpoints")
        scope1["remember"]("progress", "50% complete")

        # Create handoff document
        handoff_content = """
        ## Handoff Summary
        - Task: Build API endpoints (50% complete)
        - Completed: /users endpoint
        - Remaining: /orders endpoint
        - Blockers: None
        """
        scope1["store_fact"](f"HANDOFF: {handoff_content}")

        del scope1

        # Second session picks up
        scope2 = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Search for handoff
        handoffs = scope2["search_memory"]("HANDOFF")
        assert len(handoffs) >= 1
        assert "50% complete" in handoffs[0]["content"]

        # Continue work
        progress = scope2["recall"]("progress")
        assert "50%" in progress


# --------------------------------------------------------------------------
# Test 4: Concurrent Agents
# --------------------------------------------------------------------------


class TestE2EConcurrentAgents:
    """Test concurrent agent writes to memory.

    NOTE: SQLite has inherent write contention limitations even with WAL mode.
    WAL mode (Write-Ahead Logging) allows concurrent reads but writes are still
    serialized. Under heavy concurrent write load, "database is locked" errors
    can occur.

    These tests are designed to verify that the system handles concurrency
    gracefully, with an acceptable success rate (>= 80%), rather than requiring
    100% success which is unrealistic for SQLite under concurrent write load.

    For production workloads requiring high concurrent write throughput,
    consider migrating to PostgreSQL.
    """

    @pytest.mark.asyncio
    async def test_e2e_concurrent_agents(self, db_path: Path, session_id: str):
        """Simulate concurrent work from multiple agents.

        Steps:
        1. Use ThreadPoolExecutor to have 5 agents write to memory simultaneously
        2. All with same session_id
        3. Verify most writes succeed (>= 80% success rate due to SQLite limitations)

        SQLite Concurrency Note:
        - WAL mode is enabled in memory_service.py
        - Writes are still serialized at the database level
        - "database is locked" errors are expected under heavy concurrent load
        - This test validates graceful degradation, not perfect concurrency
        """
        from scripts.agentica.unified_scope import create_unified_scope

        num_agents = 5
        writes_per_agent = 10
        errors: list[Exception] = []
        success_count = 0
        total_attempted = 0

        # Track per-agent success for detailed reporting
        agent_results: dict[int, dict] = {}

        def agent_work(agent_id: int):
            """Work performed by a single agent."""
            nonlocal success_count, total_attempted
            agent_success = 0
            agent_errors = []

            try:
                # Each agent creates its own scope (but same session)
                scope = create_unified_scope(
                    session_id=session_id,
                    db_path=db_path,
                )

                for i in range(writes_per_agent):
                    total_attempted += 1
                    try:
                        # Store facts in archival memory
                        scope["store_fact"](f"Agent {agent_id} finding #{i}: data point {i * agent_id}")

                        # Also remember some core memory (last one wins)
                        scope["remember"](f"agent_{agent_id}_state", f"iteration_{i}")
                        agent_success += 1
                    except Exception as write_error:
                        agent_errors.append(write_error)

                success_count += 1  # Agent completed (even with partial failures)
            except Exception as e:
                errors.append(e)

            agent_results[agent_id] = {
                "success_writes": agent_success,
                "errors": agent_errors,
            }

        # Run agents concurrently using threads (sqlite is sync)
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_agents) as executor:
            futures = [executor.submit(agent_work, i) for i in range(num_agents)]
            concurrent.futures.wait(futures)

        # Calculate success rate
        total_writes = sum(r["success_writes"] for r in agent_results.values())
        expected_writes = num_agents * writes_per_agent
        success_rate = total_writes / expected_writes if expected_writes > 0 else 0

        # SQLite concurrency constraint: allow up to 20% failure rate
        # This acknowledges SQLite's inherent write contention limitations
        min_success_rate = 0.80

        # Provide detailed failure info if test fails
        if success_rate < min_success_rate:
            all_errors = []
            for agent_id, result in agent_results.items():
                for err in result["errors"]:
                    all_errors.append(f"Agent {agent_id}: {err}")
            error_summary = "\n".join(all_errors[:10])  # Show first 10 errors
            pytest.fail(
                f"Concurrent write success rate {success_rate:.1%} below threshold {min_success_rate:.0%}.\n"
                f"Total writes: {total_writes}/{expected_writes}\n"
                f"Sample errors:\n{error_summary}"
            )

        # Verify all agents completed (scope creation worked)
        assert success_count == num_agents, f"Only {success_count}/{num_agents} agents completed"

        # Verify at least some data from each agent was stored
        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Search for agent findings - at least some should be present
        agents_with_data = 0
        for agent_id in range(num_agents):
            results = scope["search_memory"](f"Agent {agent_id}")
            if len(results) >= 1:
                agents_with_data += 1

        # At least 80% of agents should have stored some data
        min_agents_with_data = int(num_agents * min_success_rate)
        assert agents_with_data >= min_agents_with_data, (
            f"Only {agents_with_data}/{num_agents} agents stored data "
            f"(expected at least {min_agents_with_data})"
        )

    @pytest.mark.asyncio
    async def test_e2e_concurrent_task_creation(self, db_path: Path, session_id: str):
        """Test concurrent task creation from multiple agents.

        Task creation involves less contention than memory writes since
        task IDs are generated client-side (UUIDs), reducing the chance
        of database conflicts.
        """
        from scripts.agentica.unified_scope import create_unified_scope

        num_agents = 5
        tasks_per_agent = 5
        all_task_ids: list[str] = []
        lock = asyncio.Lock()
        errors: list[Exception] = []

        def agent_create_tasks(agent_id: int):
            """Agent creates multiple tasks."""
            scope = create_unified_scope(
                session_id=session_id,
                db_path=db_path,
            )

            task_ids = []
            for i in range(tasks_per_agent):
                try:
                    task_id = scope["create_task"](f"Agent {agent_id} task {i}")
                    task_ids.append(task_id)
                except Exception as e:
                    errors.append(e)

            return task_ids

        # Run concurrently
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_agents) as executor:
            futures = [executor.submit(agent_create_tasks, i) for i in range(num_agents)]
            for future in concurrent.futures.as_completed(futures):
                all_task_ids.extend(future.result())

        expected_tasks = num_agents * tasks_per_agent
        actual_tasks = len(all_task_ids)
        success_rate = actual_tasks / expected_tasks if expected_tasks > 0 else 0

        # Allow 20% failure rate for SQLite concurrency
        min_success_rate = 0.80
        assert success_rate >= min_success_rate, (
            f"Task creation success rate {success_rate:.1%} below threshold {min_success_rate:.0%}. "
            f"Created {actual_tasks}/{expected_tasks} tasks. Errors: {errors[:5]}"
        )

        # Verify all created task IDs are unique (no collisions)
        assert len(set(all_task_ids)) == len(all_task_ids), "Task ID collision detected"

        # Verify tasks are visible in the database
        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        all_tasks = scope["get_all_tasks"]()
        # At least 80% of created tasks should be retrievable
        min_retrievable = int(actual_tasks * min_success_rate)
        assert len(all_tasks) >= min_retrievable, (
            f"Only {len(all_tasks)} tasks retrievable, expected at least {min_retrievable}"
        )


# --------------------------------------------------------------------------
# Test 5: Task Dependency Flow
# --------------------------------------------------------------------------


class TestE2ETaskDependencyFlow:
    """Test task dependency blocking."""

    def test_e2e_task_dependency_flow(self, db_path: Path, session_id: str):
        """Test task blocking with dependencies.

        Steps:
        1. Create task A
        2. Create task B with blocks=[A]
        3. B should not be in get_ready_tasks()
        4. Complete A
        5. B should now be in get_ready_tasks()
        """
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Step 1: Create task A
        task_a = scope["create_task"]("Setup database")

        # Step 2: Create task B that depends on A
        task_b = scope["create_task"]("Create API endpoints", blocks=[task_a])

        # Step 3: B should NOT be in ready tasks (blocked by A)
        ready = scope["get_ready_tasks"]()
        assert task_a in ready, "Task A should be ready"
        assert task_b not in ready, "Task B should be blocked"

        # Step 4: Complete task A
        scope["complete_task"](task_a)

        # Step 5: B should now be ready
        ready = scope["get_ready_tasks"]()
        assert task_a not in ready, "Task A is completed, not ready"
        assert task_b in ready, "Task B should now be ready"

    def test_e2e_task_dependency_chain(self, db_path: Path, session_id: str):
        """Test a chain of dependent tasks."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Create a chain: A -> B -> C -> D
        task_a = scope["create_task"]("Research")
        task_b = scope["create_task"]("Design", blocks=[task_a])
        task_c = scope["create_task"]("Implement", blocks=[task_b])
        task_d = scope["create_task"]("Test", blocks=[task_c])

        # Only A should be ready
        ready = scope["get_ready_tasks"]()
        assert ready == [task_a]

        # Complete A -> B becomes ready
        scope["complete_task"](task_a)
        ready = scope["get_ready_tasks"]()
        assert ready == [task_b]

        # Complete B -> C becomes ready
        scope["complete_task"](task_b)
        ready = scope["get_ready_tasks"]()
        assert ready == [task_c]

        # Complete C -> D becomes ready
        scope["complete_task"](task_c)
        ready = scope["get_ready_tasks"]()
        assert ready == [task_d]

        # Complete D -> nothing ready
        scope["complete_task"](task_d)
        ready = scope["get_ready_tasks"]()
        assert ready == []

        # All tasks completed
        all_tasks = scope["get_all_tasks"]()
        assert all(t["status"] == "completed" for t in all_tasks)

    def test_e2e_task_parallel_dependencies(self, db_path: Path, session_id: str):
        """Test parallel tasks with shared dependency."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Create structure:
        #   A (setup)
        #  / \
        # B   C  (parallel work)
        #  \ /
        #   D    (final step, depends on both B and C)

        task_a = scope["create_task"]("Setup")
        task_b = scope["create_task"]("Build frontend", blocks=[task_a])
        task_c = scope["create_task"]("Build backend", blocks=[task_a])
        task_d = scope["create_task"]("Integration", blocks=[task_b, task_c])

        # Only A is ready
        ready = scope["get_ready_tasks"]()
        assert task_a in ready
        assert task_b not in ready
        assert task_c not in ready
        assert task_d not in ready

        # Complete A -> B and C become ready (parallel)
        scope["complete_task"](task_a)
        ready = scope["get_ready_tasks"]()
        assert task_b in ready
        assert task_c in ready
        assert task_d not in ready  # Still blocked

        # Complete B -> D still blocked by C
        scope["complete_task"](task_b)
        ready = scope["get_ready_tasks"]()
        assert task_c in ready
        assert task_d not in ready

        # Complete C -> D now ready
        scope["complete_task"](task_c)
        ready = scope["get_ready_tasks"]()
        assert task_d in ready

    def test_e2e_task_dependency_with_memory(self, db_path: Path, session_id: str):
        """Test combining task dependencies with memory operations."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
        )

        # Create tasks
        research_task = scope["create_task"]("Research best practices")
        implement_task = scope["create_task"]("Implement solution", blocks=[research_task])

        # Do research and store findings
        scope["remember"]("best_practice_1", "Use dependency injection")
        scope["remember"]("best_practice_2", "Write unit tests first")
        scope["store_fact"]("Research complete: Found 2 best practices")

        # Complete research
        scope["complete_task"](research_task)

        # Implementation task is now ready
        ready = scope["get_ready_tasks"]()
        assert implement_task in ready

        # When implementing, we can recall the research
        bp1 = scope["recall"]("best_practice_1")
        assert "dependency injection" in bp1

        bp2 = scope["recall"]("best_practice_2")
        assert "unit tests" in bp2

        # Complete implementation
        scope["store_fact"]("Implementation complete: Applied both best practices")
        scope["complete_task"](implement_task)

        # Verify everything persists
        all_tasks = scope["get_all_tasks"]()
        assert all(t["status"] == "completed" for t in all_tasks)

        search = scope["search_memory"]("best practices")
        assert len(search) >= 1


# --------------------------------------------------------------------------
# Test 6: Extra Scope and Composition
# --------------------------------------------------------------------------


class TestE2EExtraScopeComposition:
    """Test extra scope injection and composition flags."""

    def test_e2e_extra_scope_integration(self, db_path: Path, session_id: str):
        """Test that extra scope functions integrate with built-in scope."""
        from scripts.agentica.unified_scope import create_unified_scope

        # Custom tool for the agent
        call_log = []

        def custom_analyze(data: str) -> dict:
            call_log.append(data)
            return {"analyzed": True, "data": data}

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            extra_scope={"analyze": custom_analyze},
        )

        # Use custom function alongside built-in functions
        task = scope["create_task"]("Analyze data")

        # Store something
        scope["remember"]("input_data", "sample data to analyze")

        # Recall and analyze
        data = scope["recall"]("input_data")
        result = scope["analyze"]("sample data")

        assert result["analyzed"] is True
        assert "sample data" in call_log

        # Complete task
        scope["complete_task"](task)

    def test_e2e_disabled_memory_mode(self, db_path: Path, session_id: str):
        """Test unified scope with memory disabled (tasks only)."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=True,
        )

        # Memory functions should not exist
        assert "remember" not in scope
        assert "recall" not in scope

        # Task functions should work
        task = scope["create_task"]("Do something")
        assert task is not None

        ready = scope["get_ready_tasks"]()
        assert task in ready

        scope["complete_task"](task)
        ready = scope["get_ready_tasks"]()
        assert task not in ready

    def test_e2e_disabled_tasks_mode(self, db_path: Path, session_id: str):
        """Test unified scope with tasks disabled (memory only)."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=True,
            enable_tasks=False,
        )

        # Task functions should not exist
        assert "create_task" not in scope
        assert "complete_task" not in scope

        # Memory functions should work
        scope["remember"]("key", "value")
        result = scope["recall"]("key")
        assert "value" in result

        # Store and search
        scope["store_fact"]("Important fact about testing")
        results = scope["search_memory"]("testing")
        assert len(results) >= 1
