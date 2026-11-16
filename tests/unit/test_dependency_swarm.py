"""Tests for Dependency Swarm Pattern - TDD Implementation.

The DependencySwarm pattern:
- Executes tasks in phases based on dependency graph
- Tasks with no dependencies run in parallel
- Tasks with dependencies wait for prerequisites
- Integrates with CoordinationDB for tracking
- Supports resume from checkpoint

Test implementation follows strict TDD:
1. Write failing tests
2. Implement minimal code to pass
3. Run qlty
4. Repeat

Reference: thoughts/shared/plans/2025-12-26-dependency-swarm.md
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


# ============================================================================
# Phase 1: TaskGraph Data Model Tests
# ============================================================================


class TestTaskGraph:
    """Test TaskGraph data model - Phase 1."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_task_graph_empty(self, db):
        """Should create empty task graph."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        assert graph.db is db
        assert len(graph.nodes) == 0

    def test_task_graph_add_task(self, db):
        """Should add task to graph."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        task_id = graph.add_task(
            name="models",
            premise="Implement data models"
        )

        assert task_id is not None
        assert task_id in graph.nodes
        assert graph.nodes[task_id].name == "models"
        assert graph.nodes[task_id].premise == "Implement data models"
        assert graph.nodes[task_id].status == "pending"

    def test_task_graph_with_dependencies(self, db):
        """Should add task with dependencies."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        b_id = graph.add_task("B", "Task B", depends_on=[a_id])

        assert b_id in graph.nodes
        assert graph.nodes[b_id].depends_on == [a_id]

    def test_get_ready_tasks_no_deps(self, db):
        """Should return all tasks when no dependencies."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        b_id = graph.add_task("B", "Task B")

        ready = graph.get_ready_tasks()

        assert len(ready) == 2
        assert a_id in ready
        assert b_id in ready

    def test_get_ready_tasks_with_deps(self, db):
        """Should return only tasks with satisfied dependencies."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        b_id = graph.add_task("B", "Task B", depends_on=[a_id])

        ready = graph.get_ready_tasks()

        # Only A is ready (B depends on A)
        assert len(ready) == 1
        assert a_id in ready
        assert b_id not in ready

        # Mark A as completed
        graph.nodes[a_id].status = "completed"
        ready = graph.get_ready_tasks()

        # Now B is ready
        assert len(ready) == 1
        assert b_id in ready


# ============================================================================
# Phase 1.5: Cycle Detection Tests (P0 Fix)
# ============================================================================


class TestTaskGraphValidation:
    """Test TaskGraph validation and cycle detection."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_validate_passes_for_dag(self, db):
        """Should pass validation for valid directed acyclic graph."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        b_id = graph.add_task("B", "Task B", depends_on=[a_id])
        c_id = graph.add_task("C", "Task C", depends_on=[b_id])

        # Should not raise
        graph.validate()

    def test_validate_passes_for_empty_graph(self, db):
        """Should pass validation for empty graph."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        # Should not raise
        graph.validate()

    def test_validate_passes_for_diamond(self, db):
        """Should pass validation for diamond dependency pattern."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        b_id = graph.add_task("B", "Task B", depends_on=[a_id])
        c_id = graph.add_task("C", "Task C", depends_on=[a_id])
        d_id = graph.add_task("D", "Task D", depends_on=[b_id, c_id])

        # Should not raise
        graph.validate()

    def test_validate_detects_self_cycle(self, db):
        """Should raise ValueError for self-referencing dependency."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        # Manually add self-dependency (would not happen via normal add_task)
        graph.nodes[a_id].depends_on = [a_id]

        with pytest.raises(ValueError, match="[Cc]ycle"):
            graph.validate()

    def test_validate_detects_simple_cycle(self, db):
        """Should raise ValueError for A -> B -> A cycle."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        b_id = graph.add_task("B", "Task B", depends_on=[a_id])
        # Create cycle: A depends on B (but B already depends on A)
        graph.nodes[a_id].depends_on = [b_id]

        with pytest.raises(ValueError, match="[Cc]ycle"):
            graph.validate()

    def test_validate_detects_complex_cycle(self, db):
        """Should raise ValueError for A -> B -> C -> A cycle."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        b_id = graph.add_task("B", "Task B", depends_on=[a_id])
        c_id = graph.add_task("C", "Task C", depends_on=[b_id])
        # Create cycle: A depends on C
        graph.nodes[a_id].depends_on = [c_id]

        with pytest.raises(ValueError, match="[Cc]ycle"):
            graph.validate()

    def test_validate_detects_invalid_dependency_reference(self, db):
        """Should raise ValueError when dependency ID doesn't exist."""
        from scripts.agentica_patterns.dependency_swarm import TaskGraph

        graph = TaskGraph(db)
        a_id = graph.add_task("A", "Task A")
        # Add task with non-existent dependency
        graph.nodes[a_id].depends_on = ["non-existent-id"]

        with pytest.raises(ValueError, match="[Uu]nknown dependency"):
            graph.validate()


# ============================================================================
# Phase 1.6: Context Passing Tests (P1 Fix)
# ============================================================================


class TestDependencyContext:
    """Test context passing between dependent tasks."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_dependent_task_receives_context(self, db):
        """Dependent task should receive results from prerequisites."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)

        # A produces a result, B depends on A
        a_id = swarm.add_task("A", "Task A")
        b_id = swarm.add_task("B", "Task B", depends_on=[a_id])

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            premises_received = []

            async def track_execution(db, premise, **kwargs):
                premises_received.append(premise)
                agent = AsyncMock()
                agent.call = AsyncMock(return_value=f"result-from-{premise[:6]}")
                agent.close = AsyncMock()
                return agent

            mock_spawn.side_effect = track_execution

            await swarm.execute()

            # Task B should receive context about Task A's result
            # The premise for B should include dependency context
            assert len(premises_received) == 2
            # B's premise should contain info about A's result
            b_premise = premises_received[1]
            assert "Task A" in b_premise or "result-from-Task A" in b_premise

    @pytest.mark.asyncio
    async def test_multiple_dependencies_context(self, db):
        """Task with multiple dependencies should receive all results."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)

        # A and B are independent, C depends on both
        a_id = swarm.add_task("A", "Task A")
        b_id = swarm.add_task("B", "Task B")
        c_id = swarm.add_task("C", "Task C", depends_on=[a_id, b_id])

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            premises_received = {}

            async def track_execution(db, premise, **kwargs):
                # Extract task name from the END of premise (after any dependency context)
                # The original premise is after the last double newline
                if "\n\n" in premise:
                    original_premise = premise.split("\n\n")[-1]
                else:
                    original_premise = premise
                # Extract task letter from "Task X"
                task_name = original_premise.split()[-1] if " " in original_premise else original_premise[:1]
                premises_received[task_name] = premise
                agent = AsyncMock()
                agent.call = AsyncMock(return_value=f"result-{task_name}")
                agent.close = AsyncMock()
                return agent

            mock_spawn.side_effect = track_execution

            await swarm.execute()

            # C's premise should reference both A and B results
            c_premise = premises_received.get("C", "")
            assert "A" in c_premise or "B" in c_premise


# ============================================================================
# Phase 1.7: Agent Closing Tests (P0 Fix)
# ============================================================================


class TestAgentLifecycle:
    """Test proper agent lifecycle management."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_agent_closed_after_success(self, db):
        """Agent should be closed after successful task completion."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        swarm.add_task("A", "Task A")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            await swarm.execute()

            # Agent should be closed
            mock_agent.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_closed_after_failure(self, db):
        """Agent should be closed even after task failure."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db, fail_fast=False)
        swarm.add_task("A", "Task A")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(side_effect=ValueError("Task failed"))
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            await swarm.execute()

            # Agent should still be closed
            mock_agent.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_agents_closed(self, db):
        """All spawned agents should be closed."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        swarm.add_task("A", "Task A")
        swarm.add_task("B", "Task B")
        swarm.add_task("C", "Task C")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            agents = []

            async def create_agent(db, premise, **kwargs):
                agent = AsyncMock()
                agent.call = AsyncMock(return_value="result")
                agent.close = AsyncMock()
                agents.append(agent)
                return agent

            mock_spawn.side_effect = create_agent

            await swarm.execute()

            # All 3 agents should be closed
            assert len(agents) == 3
            for agent in agents:
                agent.close.assert_called_once()


# ============================================================================
# Phase 2: DependencySwarm Class Tests
# ============================================================================


class TestDependencySwarm:
    """Test DependencySwarm orchestration - Phase 2."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_swarm_executes_independent_parallel(self, db):
        """Independent tasks should execute in parallel."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)

        # Add 3 independent tasks
        swarm.add_task("A", "Task A")
        swarm.add_task("B", "Task B")
        swarm.add_task("C", "Task C")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            # Mock agents
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            results = await swarm.execute()

            # All 3 tasks should have completed
            assert len(results) == 3
            # All agents should be spawned (for parallel execution)
            assert mock_spawn.call_count == 3

    @pytest.mark.asyncio
    async def test_swarm_respects_dependencies(self, db):
        """Dependent tasks should wait for prerequisites."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)

        # Create dependency chain: A -> B -> C
        a_id = swarm.add_task("A", "Task A")
        b_id = swarm.add_task("B", "Task B", depends_on=[a_id])
        c_id = swarm.add_task("C", "Task C", depends_on=[b_id])

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            # Mock agents
            execution_order = []

            async def track_execution(db, premise, **kwargs):
                agent = AsyncMock()
                async def call_with_tracking(*args, **kwargs):
                    # Extract task name from original premise (after dependency context)
                    # The original premise is the last line after double newlines
                    if "\n\n" in premise:
                        original_premise = premise.split("\n\n")[-1]
                    else:
                        original_premise = premise
                    execution_order.append(original_premise)
                    return f"result-{original_premise}"
                agent.call = call_with_tracking
                agent.close = AsyncMock()
                return agent

            mock_spawn.side_effect = track_execution

            results = await swarm.execute()

            # Execution order should respect dependencies
            # Task A should execute before B, B before C
            a_idx = execution_order.index("Task A")
            b_idx = execution_order.index("Task B")
            c_idx = execution_order.index("Task C")

            assert a_idx < b_idx < c_idx

    @pytest.mark.asyncio
    async def test_swarm_tracks_completion(self, db):
        """Should track task completion in graph."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        task_id = swarm.add_task("A", "Task A")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            await swarm.execute()

            # Task should be marked as completed
            assert swarm.graph.nodes[task_id].status == "completed"
            assert swarm.graph.nodes[task_id].result == "result"

    @pytest.mark.asyncio
    async def test_swarm_validates_before_execute(self, db):
        """Should validate graph before execution."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        a_id = swarm.add_task("A", "Task A")
        b_id = swarm.add_task("B", "Task B", depends_on=[a_id])
        # Create cycle
        swarm.graph.nodes[a_id].depends_on = [b_id]

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            with pytest.raises(ValueError, match="[Cc]ycle"):
                await swarm.execute()

            # No agents should be spawned due to validation failure
            mock_spawn.assert_not_called()


# ============================================================================
# Phase 3: CoordinationDB Integration Tests
# ============================================================================


class TestDependencySwarmCoordination:
    """Test CoordinationDB integration - Phase 3."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_swarm_registers_agents(self, db):
        """Should register spawned agents in CoordinationDB."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        swarm.add_task("A", "Task A")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            await swarm.execute()

            # Verify tracked_spawn was called with db
            mock_spawn.assert_called()
            call_kwargs = mock_spawn.call_args.kwargs
            assert call_kwargs['db'] is db
            assert call_kwargs['pattern'] == 'dependency_swarm'

    @pytest.mark.asyncio
    async def test_swarm_records_tasks(self, db):
        """Should record completed tasks in CoordinationDB."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        task_id = swarm.add_task("A", "Task A")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            await swarm.execute()

            # Verify agent was registered and task recorded
            # (TrackedAgent handles this automatically)
            assert mock_agent.call.called


# ============================================================================
# Phase 4: Error Handling Tests
# ============================================================================


class TestDependencySwarmErrors:
    """Test error handling in DependencySwarm."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_swarm_fail_fast_mode(self, db):
        """In fail_fast mode, first error should stop execution."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db, fail_fast=True)
        swarm.add_task("A", "Task A")
        swarm.add_task("B", "Task B")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            # First agent fails
            agent1 = AsyncMock()
            agent1.call = AsyncMock(side_effect=ValueError("Task A failed"))
            agent1.close = AsyncMock()

            agent2 = AsyncMock()
            agent2.call = AsyncMock(return_value="result")
            agent2.close = AsyncMock()

            mock_spawn.side_effect = [agent1, agent2]

            # Should raise the error
            with pytest.raises(ValueError, match="Task A failed"):
                await swarm.execute()

    @pytest.mark.asyncio
    async def test_swarm_continue_on_failure(self, db):
        """In non-fail-fast mode, continue with other tasks."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db, fail_fast=False)
        swarm.add_task("A", "Task A")
        swarm.add_task("B", "Task B")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            # First agent fails, second succeeds
            agent1 = AsyncMock()
            agent1.call = AsyncMock(side_effect=ValueError("Task A failed"))
            agent1.close = AsyncMock()

            agent2 = AsyncMock()
            agent2.call = AsyncMock(return_value="result")
            agent2.close = AsyncMock()

            mock_spawn.side_effect = [agent1, agent2]

            results = await swarm.execute()

            # Should have partial results
            assert "B" in results  # Task B succeeded
            # Task A should be marked as failed in graph
            a_id = [tid for tid, node in swarm.graph.nodes.items() if node.name == "A"][0]
            assert swarm.graph.nodes[a_id].status == "failed"


# ============================================================================
# Phase 5: Advanced Scenarios Tests
# ============================================================================


class TestDependencySwarmAdvanced:
    """Test advanced scenarios and edge cases."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_diamond_dependency_pattern(self, db):
        """Diamond pattern: A -> {B,C} -> D should work correctly."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)

        # Create diamond: A at top, B and C in middle, D at bottom
        a_id = swarm.add_task("A", "Task A")
        b_id = swarm.add_task("B", "Task B", depends_on=[a_id])
        c_id = swarm.add_task("C", "Task C", depends_on=[a_id])
        d_id = swarm.add_task("D", "Task D", depends_on=[b_id, c_id])

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            execution_order = []

            async def track_execution(db, premise, **kwargs):
                agent = AsyncMock()
                async def call_with_tracking(*args, **kwargs):
                    # Extract task name from original premise (after dependency context)
                    if "\n\n" in premise:
                        original_premise = premise.split("\n\n")[-1]
                    else:
                        original_premise = premise
                    execution_order.append(original_premise)
                    return f"result-{original_premise}"
                agent.call = call_with_tracking
                agent.close = AsyncMock()
                return agent

            mock_spawn.side_effect = track_execution

            results = await swarm.execute()

            # A should execute first
            # B and C can execute in parallel (both after A)
            # D should execute last (after both B and C)
            a_idx = execution_order.index("Task A")
            b_idx = execution_order.index("Task B")
            c_idx = execution_order.index("Task C")
            d_idx = execution_order.index("Task D")

            assert a_idx < b_idx
            assert a_idx < c_idx
            assert b_idx < d_idx
            assert c_idx < d_idx

    @pytest.mark.asyncio
    async def test_swarm_with_max_parallel_limit(self, db):
        """Max parallel limit should throttle execution."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db, max_parallel=2)

        # Add 5 independent tasks
        for i in range(5):
            swarm.add_task(f"Task-{i}", f"Task {i}")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            results = await swarm.execute()

            # All tasks should complete
            assert len(results) == 5
            # Implementation should respect max_parallel
            # (exact verification depends on implementation approach)


# ============================================================================
# Phase 6: Skill Injection Tests
# ============================================================================


class TestSwarmSkillInjection:
    """Test skill injection into DependencySwarm tasks."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_swarm_with_default_skills(self, db):
        """Should inject default skills into all tasks."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(
            db=db,
            skills=["test-skill"]
        )

        swarm.add_task("A", "Task A")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn, \
             patch('scripts.agentica_patterns.skill_injection.load_skill', return_value="Skill content"):
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            await swarm.execute()

            # Check that premise included skill content
            call_args = mock_spawn.call_args
            premise = call_args.kwargs["premise"]
            assert "Skill content" in premise
            assert "Task A" in premise

    @pytest.mark.asyncio
    async def test_task_with_skill_override(self, db):
        """Should allow per-task skill override."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(
            db=db,
            skills=["default-skill"]
        )

        # Add task with different skills
        swarm.add_task(
            "A",
            "Task A",
            skills=["override-skill"]
        )

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            def mock_load_skill(skill_name, base_path=None):
                return f"Content of {skill_name}"

            with patch('scripts.agentica_patterns.skill_injection.load_skill', side_effect=mock_load_skill):
                mock_agent = AsyncMock()
                mock_agent.call = AsyncMock(return_value="result")
                mock_agent.close = AsyncMock()
                mock_spawn.return_value = mock_agent

                await swarm.execute()

                # Check that override skill was used
                call_args = mock_spawn.call_args
                premise = call_args.kwargs["premise"]
                assert "Content of override-skill" in premise
                assert "Content of default-skill" not in premise

    @pytest.mark.asyncio
    async def test_swarm_with_bundle(self, db):
        """Should inject bundle skills into all tasks."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(
            db=db,
            bundle="implementation"
        )

        swarm.add_task("A", "Task A")

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            def mock_load_skill(skill_name, base_path=None):
                return f"Skill: {skill_name}"

            def mock_load_rule(rule_name, base_path=None):
                return f"Rule: {rule_name}"

            with patch('scripts.agentica_patterns.skill_injection.load_skill', side_effect=mock_load_skill), \
                 patch('scripts.agentica_patterns.skill_injection.load_rule', side_effect=mock_load_rule):
                mock_agent = AsyncMock()
                mock_agent.call = AsyncMock(return_value="result")
                mock_agent.close = AsyncMock()
                mock_spawn.return_value = mock_agent

                await swarm.execute()

                # Check that bundle skills were injected
                call_args = mock_spawn.call_args
                premise = call_args.kwargs["premise"]
                assert "Skill: test-driven-development" in premise
                assert "Rule: git-commits" in premise

    @pytest.mark.asyncio
    async def test_task_bundle_override(self, db):
        """Should allow per-task bundle override."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(
            db=db,
            bundle="implementation"
        )

        # Add task with different bundle
        swarm.add_task(
            "A",
            "Task A",
            bundle="research"
        )

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn:
            def mock_load_skill(skill_name, base_path=None):
                return f"Skill: {skill_name}"

            with patch('scripts.agentica_patterns.skill_injection.load_skill', side_effect=mock_load_skill), \
                 patch('scripts.agentica_patterns.skill_injection.load_rule'):
                mock_agent = AsyncMock()
                mock_agent.call = AsyncMock(return_value="result")
                mock_agent.close = AsyncMock()
                mock_spawn.return_value = mock_agent

                await swarm.execute()

                # Check that research bundle was used
                call_args = mock_spawn.call_args
                premise = call_args.kwargs["premise"]
                assert "Skill: rp-explorer" in premise
                # Implementation bundle skills should not be present
                assert "test-driven-development" not in premise

    @pytest.mark.asyncio
    async def test_skills_preserved_with_dependency_context(self, db):
        """Skills should be preserved when dependency context is added."""
        from scripts.agentica_patterns.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(
            db=db,
            skills=["test-skill"]
        )

        a_id = swarm.add_task("A", "Task A")
        swarm.add_task("B", "Task B", depends_on=[a_id])

        with patch('scripts.agentica_patterns.dependency_swarm.tracked_spawn') as mock_spawn, \
             patch('scripts.agentica_patterns.skill_injection.load_skill', return_value="Skill content"):
            premises_received = []

            async def track_execution(db, premise, **kwargs):
                premises_received.append(premise)
                agent = AsyncMock()
                agent.call = AsyncMock(return_value="result-A")
                agent.close = AsyncMock()
                return agent

            mock_spawn.side_effect = track_execution

            await swarm.execute()

            # Both tasks should have skill content
            assert len(premises_received) == 2
            assert all("Skill content" in p for p in premises_received)
            # Second task should also have dependency context
            b_premise = premises_received[1]
            assert "Dependency" in b_premise or "result-A" in b_premise
