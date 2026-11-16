"""Tests for BeadsTaskGraph - hash-based task graph with blocked cache."""

import pytest
from pathlib import Path


class TestTaskIdGeneration:
    """Hash-based task ID generation."""

    @pytest.fixture
    def graph(self, tmp_path):
        from scripts.agentica_patterns.beads_task_graph import BeadsTaskGraph
        return BeadsTaskGraph(db_path=tmp_path / "tasks.db")

    def test_task_id_format(self, graph):
        """Task ID should have bd-XXXXXX format."""
        task_id = graph.add_task("Test task")
        assert task_id.startswith("bd-")
        assert len(task_id) == 9  # bd- + 6 chars

    def test_task_ids_are_unique(self, graph):
        """Each task should get unique ID."""
        ids = [graph.add_task(f"Task {i}") for i in range(100)]
        assert len(set(ids)) == 100

    def test_task_id_is_deterministic_hash(self, graph):
        """IDs should be hash-based (different content = different hash)."""
        id1 = graph.add_task("Task A")
        id2 = graph.add_task("Task B")
        assert id1 != id2


class TestDependencyTypes:
    """6 dependency types from Beads."""

    @pytest.fixture
    def graph(self, tmp_path):
        from scripts.agentica_patterns.beads_task_graph import BeadsTaskGraph
        return BeadsTaskGraph(db_path=tmp_path / "tasks.db")

    def test_blocks_dependency(self, graph):
        """blocks: A must complete before B starts."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])

        deps = graph.get_dependencies(task_b)
        assert task_a in deps["blocks"]

    def test_conditional_blocks_dependency(self, graph):
        """conditional-blocks: A blocks B only if A fails."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", conditional_blocks=[task_a])

        deps = graph.get_dependencies(task_b)
        assert task_a in deps["conditional_blocks"]

    def test_waits_for_dependency(self, graph):
        """waits-for: B waits for A but can proceed if A fails."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", waits_for=[task_a])

        deps = graph.get_dependencies(task_b)
        assert task_a in deps["waits_for"]

    def test_parent_child_dependency(self, graph):
        """parent-child: B is subtask of A."""
        task_a = graph.add_task("Parent task")
        task_b = graph.add_task("Child task", parent=task_a)

        deps = graph.get_dependencies(task_b)
        assert task_a == deps["parent"]

        children = graph.get_children(task_a)
        assert task_b in children

    def test_related_dependency(self, graph):
        """related: Informational link between tasks."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", related=[task_a])

        deps = graph.get_dependencies(task_b)
        assert task_a in deps["related"]

    def test_discovered_from_dependency(self, graph):
        """discovered-from: B was discovered while working on A."""
        task_a = graph.add_task("Original task")
        task_b = graph.add_task("Discovered task", discovered_from=task_a)

        deps = graph.get_dependencies(task_b)
        assert task_a == deps["discovered_from"]


class TestBlockedCache:
    """Pre-computed blocked cache for O(1) ready queries."""

    @pytest.fixture
    def graph(self, tmp_path):
        from scripts.agentica_patterns.beads_task_graph import BeadsTaskGraph
        return BeadsTaskGraph(db_path=tmp_path / "tasks.db")

    def test_task_without_deps_is_ready(self, graph):
        """Task with no dependencies should be ready."""
        task_id = graph.add_task("Independent task")
        ready = graph.get_ready_tasks()
        assert task_id in ready

    def test_blocked_task_not_ready(self, graph):
        """Blocked task should not be ready."""
        task_a = graph.add_task("Blocker")
        task_b = graph.add_task("Blocked", blocks=[task_a])

        ready = graph.get_ready_tasks()
        assert task_a in ready
        assert task_b not in ready

    def test_task_becomes_ready_after_blocker_complete(self, graph):
        """Task should become ready when blocker completes."""
        task_a = graph.add_task("Blocker")
        task_b = graph.add_task("Blocked", blocks=[task_a])

        graph.complete_task(task_a)

        ready = graph.get_ready_tasks()
        assert task_b in ready

    def test_blocked_cache_updated_on_status_change(self, graph):
        """Blocked cache should update when task status changes."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_b])

        # Initially only A is ready
        ready = graph.get_ready_tasks()
        assert task_a in ready
        assert task_b not in ready
        assert task_c not in ready

        # Complete A, B becomes ready
        graph.complete_task(task_a)
        ready = graph.get_ready_tasks()
        assert task_b in ready
        assert task_c not in ready

        # Complete B, C becomes ready
        graph.complete_task(task_b)
        ready = graph.get_ready_tasks()
        assert task_c in ready


class TestWisps:
    """Ephemeral tasks (wisps) for agent-internal state."""

    @pytest.fixture
    def graph(self, tmp_path):
        from scripts.agentica_patterns.beads_task_graph import BeadsTaskGraph
        return BeadsTaskGraph(db_path=tmp_path / "tasks.db")

    def test_create_wisp(self, graph):
        """Should create ephemeral wisp task."""
        wisp_id = graph.add_wisp("Internal thought")
        assert wisp_id.startswith("wp-")

    def test_wisp_excluded_from_ready(self, graph):
        """Wisps should not appear in ready tasks."""
        task_id = graph.add_task("Real task")
        wisp_id = graph.add_wisp("Internal thought")

        ready = graph.get_ready_tasks()
        assert task_id in ready
        assert wisp_id not in ready

    def test_wisp_excluded_from_all_tasks(self, graph):
        """Wisps should not appear in all_tasks view."""
        task_id = graph.add_task("Real task")
        wisp_id = graph.add_wisp("Internal thought")

        all_tasks = graph.get_all_tasks()
        task_ids = [t["id"] for t in all_tasks]
        assert task_id in task_ids
        assert wisp_id not in task_ids


class TestCycleDetection:
    """DAG validation with Kahn's algorithm."""

    @pytest.fixture
    def graph(self, tmp_path):
        from scripts.agentica_patterns.beads_task_graph import BeadsTaskGraph
        return BeadsTaskGraph(db_path=tmp_path / "tasks.db")

    def test_detect_direct_cycle(self, graph):
        """Should detect direct A->B->A cycle."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])

        with pytest.raises(ValueError, match="cycle"):
            graph.add_dependency(task_a, "blocks", task_b)

    def test_detect_indirect_cycle(self, graph):
        """Should detect indirect A->B->C->A cycle."""
        task_a = graph.add_task("Task A")
        task_b = graph.add_task("Task B", blocks=[task_a])
        task_c = graph.add_task("Task C", blocks=[task_b])

        with pytest.raises(ValueError, match="cycle"):
            graph.add_dependency(task_a, "blocks", task_c)
