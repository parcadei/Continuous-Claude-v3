#!/usr/bin/env python3
"""Task Decomposer: Data structures for task DAGs.

USAGE:
    # Validate a DAG from JSON
    uv run python scripts/agentica_patterns/task_decomposer.py validate dag.json

    # Get ready tasks given completed set
    uv run python scripts/agentica_patterns/task_decomposer.py ready dag.json --completed atom-1,atom-2

Claude decomposes complex tasks into atomic subtasks with dependencies.
This script provides data structures and validation; Claude provides the intelligence.

Data structures:
- TaskNode: Represents an atomic task with inputs, outputs, and dependencies
- TaskDAG: Directed Acyclic Graph of TaskNodes with validation and traversal

Example JSON format:
{
    "nodes": {
        "task-1": {
            "id": "task-1",
            "description": "Fetch user data",
            "formal": "fetch(user_id) -> UserData",
            "inputs": {"user_id": "string"},
            "output": {"user_data": "UserData"},
            "deps": []
        },
        "task-2": {
            "id": "task-2",
            "description": "Process user data",
            "formal": "process(UserData) -> Report",
            "inputs": {"user_data": "task-1.output.user_data"},
            "output": {"report": "Report"},
            "deps": ["task-1"]
        }
    }
}
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class TaskNode:
    """Represents an atomic task in the DAG.

    Attributes:
        id: Unique identifier for this task
        description: Human-readable description of what this task does
        formal: Optional formal logic notation (e.g., "fetch(x) -> y")
        inputs: Dictionary of input parameters and their sources
        output: Dictionary of output values produced by this task
        deps: List of task IDs that must complete before this task
    """
    id: str
    description: str
    formal: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    deps: list[str] = field(default_factory=list)


@dataclass
class TaskDAG:
    """Directed Acyclic Graph of TaskNodes.

    Provides methods for:
    - Adding nodes and edges
    - Validating the DAG (no cycles, all deps exist, etc.)
    - Finding ready tasks given a set of completed tasks
    - Checking completion status
    - Serialization/deserialization
    """
    nodes: dict[str, TaskNode] = field(default_factory=dict)

    def add_node(self, node: TaskNode) -> None:
        """Add a node to the DAG.

        If a node with the same ID already exists, it will be overwritten.

        Args:
            node: The TaskNode to add
        """
        self.nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge: to_id depends on from_id.

        Args:
            from_id: The ID of the task that must complete first
            to_id: The ID of the task that depends on from_id

        Raises:
            KeyError: If to_id does not exist in the DAG
        """
        if to_id not in self.nodes:
            raise KeyError(f"Node '{to_id}' does not exist in the DAG")
        if from_id not in self.nodes[to_id].deps:
            self.nodes[to_id].deps.append(from_id)

    def validate(self) -> list[str]:
        """Validate the DAG structure.

        Checks:
        - No self-dependencies
        - All dependency IDs exist in the DAG
        - No cycles (topological sort must succeed)

        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []

        # Check self-dependencies and missing dependencies
        for node_id, node in self.nodes.items():
            for dep_id in node.deps:
                if dep_id == node_id:
                    errors.append(f"Self-dependency: node '{node_id}' depends on itself")
                elif dep_id not in self.nodes:
                    errors.append(f"Missing dependency: node '{node_id}' depends on non-existent '{dep_id}'")

        # Check for cycles using Kahn's algorithm (topological sort)
        if self.nodes and not errors:
            cycle_error = self._detect_cycle()
            if cycle_error:
                errors.append(cycle_error)

        return errors

    def _detect_cycle(self) -> str | None:
        """Detect cycles using Kahn's algorithm.

        Returns:
            Error message if cycle detected, None otherwise.
        """
        # Build in-degree map (count of incoming edges for each node)
        in_degree: dict[str, int] = {node_id: 0 for node_id in self.nodes}
        for node in self.nodes.values():
            for dep_id in node.deps:
                if dep_id in in_degree:
                    # dep_id has an outgoing edge to this node
                    pass
            # Count incoming edges (this node depends on dep_id)
            # We need to count how many nodes depend on each node

        # Rebuild: for each node, count how many other nodes list it as a dependency
        in_degree = {node_id: 0 for node_id in self.nodes}
        for node in self.nodes.values():
            # This node has len(node.deps) incoming edges
            # But we need the reverse: how many nodes point TO each node
            pass

        # Actually: in DAG terms, if B depends on A, then A -> B
        # So A has outgoing edge to B, B has incoming edge from A
        # in_degree[B] counts how many nodes B depends on

        # For Kahn's algorithm, we want to process nodes with no incoming edges first
        # A node with no dependencies (deps = []) has in_degree 0

        # Rebuild correctly
        in_degree = {node_id: len(self.nodes[node_id].deps) for node_id in self.nodes}

        # Queue nodes with no dependencies
        queue = deque([node_id for node_id, deg in in_degree.items() if deg == 0])
        processed = 0

        # Build adjacency list (who depends on whom)
        dependents: dict[str, list[str]] = {node_id: [] for node_id in self.nodes}
        for node in self.nodes.values():
            for dep_id in node.deps:
                if dep_id in dependents:
                    dependents[dep_id].append(node.id)

        while queue:
            current = queue.popleft()
            processed += 1

            # For each node that depends on current
            for dependent in dependents[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if processed != len(self.nodes):
            return "Cycle detected: topological sort failed"
        return None

    def ready_tasks(self, completed: set[str]) -> list[TaskNode]:
        """Get tasks that are ready to execute.

        A task is ready if:
        - It has not been completed
        - All its dependencies have been completed

        Args:
            completed: Set of task IDs that have been completed

        Returns:
            List of TaskNodes that are ready to execute
        """
        ready = []
        for node in self.nodes.values():
            if node.id in completed:
                continue  # Already done
            # Check if all deps are completed
            if all(dep_id in completed for dep_id in node.deps):
                ready.append(node)
        return ready

    def is_complete(self, completed: set[str]) -> bool:
        """Check if all tasks in the DAG have been completed.

        Args:
            completed: Set of task IDs that have been completed

        Returns:
            True if all nodes are in the completed set
        """
        return all(node_id in completed for node_id in self.nodes)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the DAG to a dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "nodes": {
                node_id: asdict(node)
                for node_id, node in self.nodes.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskDAG:
        """Create a TaskDAG from a dictionary.

        Args:
            data: Dictionary with "nodes" key containing node definitions

        Returns:
            TaskDAG instance
        """
        dag = cls()
        nodes_data = data.get("nodes", {})
        for node_id, node_data in nodes_data.items():
            node = TaskNode(
                id=node_data.get("id", node_id),
                description=node_data.get("description", ""),
                formal=node_data.get("formal"),
                inputs=node_data.get("inputs", {}),
                output=node_data.get("output", {}),
                deps=node_data.get("deps", []),
            )
            dag.add_node(node)
        return dag


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Task Decomposer: Validate and query task DAGs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate a DAG
    python task_decomposer.py validate dag.json

    # Get ready tasks (none completed)
    python task_decomposer.py ready dag.json

    # Get ready tasks after some are done
    python task_decomposer.py ready dag.json --completed task-1,task-2
        """
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a DAG JSON file")
    validate_parser.add_argument("file", help="Path to DAG JSON file")

    # ready command
    ready_parser = subparsers.add_parser("ready", help="Get ready tasks")
    ready_parser.add_argument("file", help="Path to DAG JSON file")
    ready_parser.add_argument(
        "--completed", "-c",
        default="",
        help="Comma-separated list of completed task IDs"
    )

    args = parser.parse_args()

    # Load DAG from file
    try:
        with open(args.file, "r") as f:
            data = json.load(f)
        dag = TaskDAG.from_dict(data)
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if args.command == "validate":
        errors = dag.validate()
        if errors:
            print("Validation errors:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print(f"Valid DAG with {len(dag.nodes)} nodes")
            sys.exit(0)

    elif args.command == "ready":
        # First validate
        errors = dag.validate()
        if errors:
            print("Validation errors:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            sys.exit(1)

        # Parse completed set
        completed = set()
        if args.completed:
            completed = set(args.completed.split(","))

        ready = dag.ready_tasks(completed)
        if ready:
            print("Ready tasks:")
            for node in ready:
                print(f"  - {node.id}: {node.description}")
        else:
            if dag.is_complete(completed):
                print("All tasks completed!")
            else:
                print("No tasks ready (check for blocking dependencies)")


if __name__ == "__main__":
    main()
