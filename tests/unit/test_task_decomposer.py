"""Unit tests for TaskNode and TaskDAG - TDD approach.

Write tests FIRST, then implement to make them pass.
"""

import pytest
from dataclasses import asdict

# Import will fail until implementation exists
from scripts.agentica_patterns.task_decomposer import TaskNode, TaskDAG


class TestTaskNode:
    """Tests for TaskNode dataclass."""

    def test_task_node_creation_minimal(self):
        """TaskNode can be created with just id and description."""
        node = TaskNode(id="task-1", description="Do something")
        assert node.id == "task-1"
        assert node.description == "Do something"
        assert node.formal is None
        assert node.inputs == {}
        assert node.output == {}
        assert node.deps == []

    def test_task_node_creation_full(self):
        """TaskNode can be created with all fields."""
        node = TaskNode(
            id="task-1",
            description="Process data",
            formal="process(x) -> y",
            inputs={"x": "input_data"},
            output={"y": "result"},
            deps=["task-0"],
        )
        assert node.id == "task-1"
        assert node.description == "Process data"
        assert node.formal == "process(x) -> y"
        assert node.inputs == {"x": "input_data"}
        assert node.output == {"y": "result"}
        assert node.deps == ["task-0"]


class TestTaskDAGBasics:
    """Basic TaskDAG operations."""

    def test_empty_dag_is_valid(self):
        """Empty DAG should validate."""
        dag = TaskDAG()
        errors = dag.validate()
        assert errors == []

    def test_single_node_dag(self):
        """Single atomic task, no deps."""
        dag = TaskDAG()
        node = TaskNode(id="atom-1", description="Atomic task")
        dag.add_node(node)

        errors = dag.validate()
        assert errors == []
        assert "atom-1" in dag.nodes

    def test_add_multiple_nodes(self):
        """Can add multiple nodes."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B"))
        dag.add_node(TaskNode(id="c", description="Task C"))

        assert len(dag.nodes) == 3
        assert "a" in dag.nodes
        assert "b" in dag.nodes
        assert "c" in dag.nodes


class TestTaskDAGDependencies:
    """Tests for dependency handling."""

    def test_linear_chain(self):
        """A -> B -> C sequential deps."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B", deps=["a"]))
        dag.add_node(TaskNode(id="c", description="Task C", deps=["b"]))

        errors = dag.validate()
        assert errors == []

    def test_diamond_dependency(self):
        """A -> B, A -> C, B -> D, C -> D (diamond shape)."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B", deps=["a"]))
        dag.add_node(TaskNode(id="c", description="Task C", deps=["a"]))
        dag.add_node(TaskNode(id="d", description="Task D", deps=["b", "c"]))

        errors = dag.validate()
        assert errors == []

    def test_add_edge_method(self):
        """add_edge adds dependency between nodes."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B"))
        dag.add_edge("a", "b")  # b depends on a

        assert "a" in dag.nodes["b"].deps


class TestTaskDAGValidation:
    """Tests for DAG validation."""

    def test_cycle_detection_simple(self):
        """A -> B -> A should fail validation."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A", deps=["b"]))
        dag.add_node(TaskNode(id="b", description="Task B", deps=["a"]))

        errors = dag.validate()
        assert len(errors) > 0
        assert any("cycle" in e.lower() for e in errors)

    def test_cycle_detection_longer(self):
        """A -> B -> C -> A should fail validation."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A", deps=["c"]))
        dag.add_node(TaskNode(id="b", description="Task B", deps=["a"]))
        dag.add_node(TaskNode(id="c", description="Task C", deps=["b"]))

        errors = dag.validate()
        assert len(errors) > 0
        assert any("cycle" in e.lower() for e in errors)

    def test_missing_dependency(self):
        """Node references non-existent dep should fail."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A", deps=["nonexistent"]))

        errors = dag.validate()
        assert len(errors) > 0
        assert any("nonexistent" in e for e in errors)

    def test_self_dependency(self):
        """Node depending on itself should fail."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A", deps=["a"]))

        errors = dag.validate()
        assert len(errors) > 0
        assert any("self" in e.lower() or "a" in e for e in errors)

    def test_multiple_validation_errors(self):
        """Multiple validation errors are all reported."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A", deps=["a", "missing"]))

        errors = dag.validate()
        assert len(errors) >= 2


class TestTaskDAGReadyTasks:
    """Tests for ready_tasks method."""

    def test_ready_tasks_initial(self):
        """Initially, only nodes with no deps are ready."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))  # No deps
        dag.add_node(TaskNode(id="b", description="Task B", deps=["a"]))
        dag.add_node(TaskNode(id="c", description="Task C"))  # No deps

        ready = dag.ready_tasks(completed=set())
        ready_ids = {t.id for t in ready}

        assert ready_ids == {"a", "c"}

    def test_ready_tasks_after_completion(self):
        """After completing deps, dependent nodes become ready."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B", deps=["a"]))
        dag.add_node(TaskNode(id="c", description="Task C", deps=["a", "b"]))

        # Initially only a is ready
        ready = dag.ready_tasks(completed=set())
        assert {t.id for t in ready} == {"a"}

        # After a completes, b is ready (c still needs b)
        ready = dag.ready_tasks(completed={"a"})
        assert {t.id for t in ready} == {"b"}

        # After a and b complete, c is ready
        ready = dag.ready_tasks(completed={"a", "b"})
        assert {t.id for t in ready} == {"c"}

    def test_ready_tasks_excludes_completed(self):
        """ready_tasks does not include already-completed tasks."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B"))

        ready = dag.ready_tasks(completed={"a"})
        ready_ids = {t.id for t in ready}

        assert "a" not in ready_ids
        assert "b" in ready_ids

    def test_ready_tasks_diamond(self):
        """Diamond pattern: d ready only after both b and c complete."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B", deps=["a"]))
        dag.add_node(TaskNode(id="c", description="Task C", deps=["a"]))
        dag.add_node(TaskNode(id="d", description="Task D", deps=["b", "c"]))

        # Only a is ready initially
        assert {t.id for t in dag.ready_tasks(set())} == {"a"}

        # After a, both b and c are ready
        assert {t.id for t in dag.ready_tasks({"a"})} == {"b", "c"}

        # After a and b, only c is ready (d needs c too)
        assert {t.id for t in dag.ready_tasks({"a", "b"})} == {"c"}

        # After a, b, and c, d is ready
        assert {t.id for t in dag.ready_tasks({"a", "b", "c"})} == {"d"}


class TestTaskDAGCompletion:
    """Tests for is_complete method."""

    def test_is_complete_empty_dag(self):
        """Empty DAG is always complete."""
        dag = TaskDAG()
        assert dag.is_complete(set()) is True

    def test_is_complete_all_done(self):
        """DAG is complete when all nodes are in completed set."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B"))

        assert dag.is_complete(set()) is False
        assert dag.is_complete({"a"}) is False
        assert dag.is_complete({"a", "b"}) is True

    def test_is_complete_ignores_extra(self):
        """Extra IDs in completed set don't affect is_complete."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))

        assert dag.is_complete({"a", "extra", "stuff"}) is True


class TestTaskDAGSerialization:
    """Tests for to_dict and from_dict."""

    def test_to_dict_empty(self):
        """Empty DAG serializes to empty nodes dict."""
        dag = TaskDAG()
        data = dag.to_dict()

        assert "nodes" in data
        assert data["nodes"] == {}

    def test_to_dict_with_nodes(self):
        """DAG with nodes serializes correctly."""
        dag = TaskDAG()
        dag.add_node(TaskNode(
            id="a",
            description="Task A",
            formal="do_a()",
            inputs={"x": 1},
            output={"y": 2},
            deps=[]
        ))

        data = dag.to_dict()
        assert "a" in data["nodes"]
        assert data["nodes"]["a"]["description"] == "Task A"
        assert data["nodes"]["a"]["formal"] == "do_a()"
        assert data["nodes"]["a"]["inputs"] == {"x": 1}
        assert data["nodes"]["a"]["output"] == {"y": 2}

    def test_from_dict_empty(self):
        """Can create DAG from empty dict."""
        data = {"nodes": {}}
        dag = TaskDAG.from_dict(data)

        assert len(dag.nodes) == 0

    def test_from_dict_with_nodes(self):
        """Can create DAG from dict with nodes."""
        data = {
            "nodes": {
                "a": {
                    "id": "a",
                    "description": "Task A",
                    "formal": None,
                    "inputs": {},
                    "output": {},
                    "deps": []
                },
                "b": {
                    "id": "b",
                    "description": "Task B",
                    "formal": None,
                    "inputs": {},
                    "output": {},
                    "deps": ["a"]
                }
            }
        }
        dag = TaskDAG.from_dict(data)

        assert len(dag.nodes) == 2
        assert dag.nodes["a"].description == "Task A"
        assert dag.nodes["b"].deps == ["a"]

    def test_to_dict_from_dict_roundtrip(self):
        """Serialization should preserve structure."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(
            id="b",
            description="Task B",
            formal="b(a) -> result",
            inputs={"input": "a.output"},
            output={"result": "value"},
            deps=["a"]
        ))
        dag.add_node(TaskNode(id="c", description="Task C", deps=["a", "b"]))

        # Roundtrip
        data = dag.to_dict()
        dag2 = TaskDAG.from_dict(data)

        # Verify structure preserved
        assert len(dag2.nodes) == 3
        assert dag2.nodes["a"].description == "Task A"
        assert dag2.nodes["b"].formal == "b(a) -> result"
        assert dag2.nodes["b"].inputs == {"input": "a.output"}
        assert dag2.nodes["c"].deps == ["a", "b"]

        # Validate still works
        assert dag2.validate() == []


class TestTaskDAGEdgeCases:
    """Edge cases and error handling."""

    def test_duplicate_node_id_overwrites(self):
        """Adding node with same ID overwrites previous."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Original"))
        dag.add_node(TaskNode(id="a", description="Updated"))

        assert dag.nodes["a"].description == "Updated"

    def test_add_edge_creates_dependency(self):
        """add_edge properly adds to deps list."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))
        dag.add_node(TaskNode(id="b", description="Task B"))
        dag.add_node(TaskNode(id="c", description="Task C"))

        dag.add_edge("a", "b")  # b depends on a
        dag.add_edge("a", "c")  # c depends on a
        dag.add_edge("b", "c")  # c depends on b

        assert "a" in dag.nodes["b"].deps
        assert "a" in dag.nodes["c"].deps
        assert "b" in dag.nodes["c"].deps

    def test_add_edge_nonexistent_to(self):
        """add_edge with nonexistent 'to' node raises error."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="Task A"))

        with pytest.raises(KeyError):
            dag.add_edge("a", "nonexistent")

    def test_large_dag_validates(self):
        """Large DAG with many nodes validates correctly."""
        dag = TaskDAG()
        # Create linear chain of 100 nodes
        dag.add_node(TaskNode(id="node-0", description="Node 0"))
        for i in range(1, 100):
            dag.add_node(TaskNode(
                id=f"node-{i}",
                description=f"Node {i}",
                deps=[f"node-{i-1}"]
            ))

        errors = dag.validate()
        assert errors == []

        # Only first node is ready initially
        ready = dag.ready_tasks(set())
        assert len(ready) == 1
        assert ready[0].id == "node-0"
