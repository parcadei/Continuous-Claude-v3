"""
WorkflowRegistry - Central registry for workflow definitions.

Provides service locator pattern for:
- Registering workflow definitions
- Retrieving workflows by name
- Listing available workflows
- Finding workflows by tag or goal type

Thread-safe singleton with clear() for testing.

Usage:
    registry = WorkflowRegistry.instance()
    registry.register(workflow)
    workflow = registry.get("my-workflow")
    all_names = registry.list()
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.agentica_patterns.workflow_registry_types import (
        WorkflowDefinition,
        PatternConfig,
        GoalType,
    )


class WorkflowNotFoundError(Exception):
    """Raised when a workflow is not found in the registry."""

    pass


class DuplicateWorkflowError(Exception):
    """Raised when registering a workflow with an existing name."""

    pass


class WorkflowRegistry:
    """
    Thread-safe singleton registry for workflow definitions.

    Follows the Service Locator pattern from research.
    """

    _instance: WorkflowRegistry | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize the registry. Use instance() for singleton access."""
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
            PatternConfig,
        )

        self._workflows: dict[str, WorkflowDefinition] = {}
        self._patterns: dict[str, PatternConfig] = {}
        self._aliases: dict[str, str] = {}  # alias -> subagent_type
        self._registry_lock = threading.RLock()

    @classmethod
    def instance(cls) -> WorkflowRegistry:
        """Get singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def clear(cls) -> None:
        """Clear singleton instance state (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                with cls._instance._registry_lock:
                    cls._instance._workflows.clear()
                    cls._instance._patterns.clear()
                    cls._instance._aliases.clear()

    # =========================================================================
    # Workflow Methods
    # =========================================================================

    def register(
        self,
        workflow: WorkflowDefinition,
        overwrite: bool = False,
    ) -> None:
        """
        Register a workflow definition.

        Args:
            workflow: WorkflowDefinition to register
            overwrite: If True, overwrite existing workflow with same name

        Raises:
            DuplicateWorkflowError: If workflow exists and overwrite=False
        """
        with self._registry_lock:
            if workflow.name in self._workflows and not overwrite:
                raise DuplicateWorkflowError(
                    f"Workflow '{workflow.name}' already registered"
                )
            self._workflows[workflow.name] = workflow

            # Auto-register aliases from workflow
            for alias, subagent_type in workflow.agent_mapping.items():
                self._aliases[alias] = subagent_type

    def get(self, name: str) -> WorkflowDefinition:
        """
        Get a workflow by name.

        Args:
            name: Workflow name

        Returns:
            WorkflowDefinition

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        with self._registry_lock:
            if name not in self._workflows:
                raise WorkflowNotFoundError(f"Workflow '{name}' not found")
            return self._workflows[name]

    def get_or_none(self, name: str) -> WorkflowDefinition | None:
        """Get a workflow by name, returning None if not found."""
        with self._registry_lock:
            return self._workflows.get(name)

    def list(self) -> list[str]:
        """List all registered workflow names."""
        with self._registry_lock:
            return list(self._workflows.keys())

    def find_by_tag(self, tag: str) -> "list[WorkflowDefinition]":
        """Find all workflows with a given tag."""
        with self._registry_lock:
            return [w for w in self._workflows.values() if tag in w.tags]

    def find_by_goal(self, goal: "GoalType") -> "list[WorkflowDefinition]":
        """Find all workflows for a given goal type."""
        with self._registry_lock:
            return [w for w in self._workflows.values() if w.goal_type == goal]

    def unregister(self, name: str) -> bool:
        """
        Unregister a workflow by name.

        Returns:
            True if workflow was removed, False if not found
        """
        with self._registry_lock:
            if name in self._workflows:
                del self._workflows[name]
                return True
            return False

    # =========================================================================
    # Pattern Configuration Methods
    # =========================================================================

    def register_pattern(self, config: PatternConfig) -> None:
        """Register a pattern configuration."""
        with self._registry_lock:
            self._patterns[config.name] = config

    def get_pattern_config(self, name: str) -> PatternConfig | None:
        """Get pattern configuration by name."""
        with self._registry_lock:
            return self._patterns.get(name)

    def list_patterns(self) -> list[str]:
        """List all registered pattern names."""
        with self._registry_lock:
            return list(self._patterns.keys())

    # =========================================================================
    # Alias Resolution Methods
    # =========================================================================

    def register_alias(self, alias: str, subagent_type: str) -> None:
        """Register an agent alias."""
        with self._registry_lock:
            self._aliases[alias] = subagent_type

    def resolve_alias(self, alias: str) -> str | None:
        """Resolve an alias to its subagent type."""
        with self._registry_lock:
            return self._aliases.get(alias)

    def list_aliases(self) -> dict[str, str]:
        """List all registered aliases."""
        with self._registry_lock:
            return dict(self._aliases)
