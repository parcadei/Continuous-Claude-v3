"""
RegistryLoader - Load workflow definitions from various sources.

Provides:
- load_builtin_workflows(): Load predefined workflow definitions
- load_workflows_from_dir(): Load workflow YAML files from a directory
- load_workflow_from_file(): Load a single workflow YAML file

Usage:
    from scripts.agentica_patterns.registry_loader import load_builtin_workflows
    load_builtin_workflows()  # Populates WorkflowRegistry
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
    from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

logger = logging.getLogger(__name__)


def load_builtin_workflows() -> int:
    """
    Load built-in workflow definitions into the registry.

    These are predefined workflows that ship with the system.

    Returns:
        Number of workflows loaded
    """
    from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
    from scripts.agentica_patterns.workflow_registry_types import (
        WorkflowDefinition,
        GoalType,
        ResourceAllocation,
    )

    registry = WorkflowRegistry.instance()
    count = 0

    # Define built-in workflows based on workflow-router SKILL.md
    builtins = [
        WorkflowDefinition(
            name="research-workflow",
            version="1.0",
            description="Multi-perspective research workflow",
            goal_type=GoalType.RESEARCH,
            default_pattern="Swarm",
            agent_mapping={
                "librarian": "research-agent",
            },
            resource_allocation=ResourceAllocation.BALANCED,
            pattern_config={
                "perspectives": ["academic", "practical", "critical"],
            },
            tags=["research", "exploration", "investigation"],
        ),
        WorkflowDefinition(
            name="plan-workflow",
            version="1.0",
            description="Sequential planning workflow",
            goal_type=GoalType.PLAN,
            default_pattern="Pipeline",
            agent_mapping={
                "oracle": "plan-agent",
            },
            resource_allocation=ResourceAllocation.CONSERVATIVE,
            tags=["plan", "design", "architecture"],
        ),
        WorkflowDefinition(
            name="build-workflow",
            version="1.0",
            description="Hierarchical implementation workflow",
            goal_type=GoalType.BUILD,
            default_pattern="Hierarchical",
            agent_mapping={
                "kraken": "build-agent",
            },
            resource_allocation=ResourceAllocation.BALANCED,
            tags=["build", "implement", "create"],
        ),
        WorkflowDefinition(
            name="fix-workflow",
            version="1.0",
            description="Debug and fix workflow with validation",
            goal_type=GoalType.FIX,
            default_pattern="GeneratorCritic",
            agent_mapping={
                "sentinel": "debug-agent",
            },
            resource_allocation=ResourceAllocation.CONSERVATIVE,
            tags=["fix", "debug", "resolve"],
        ),
    ]

    for workflow in builtins:
        try:
            registry.register(workflow, overwrite=False)
            count += 1
        except Exception as e:
            logger.debug(f"Skipping builtin workflow '{workflow.name}': {e}")

    return count


def load_workflows_from_dir(directory: str | Path) -> int:
    """
    Load workflow definitions from YAML files in a directory.

    Scans the directory for .yaml and .yml files, parses each one,
    and registers valid workflows.

    Args:
        directory: Path to directory containing workflow YAML files

    Returns:
        Number of workflows successfully loaded
    """
    from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
    from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

    directory = Path(directory)
    if not directory.exists():
        logger.warning(f"Workflow directory does not exist: {directory}")
        return 0

    registry = WorkflowRegistry.instance()
    parser = WorkflowDSLParser()
    count = 0

    for ext in ["*.yaml", "*.yml"]:
        for file_path in directory.glob(ext):
            try:
                result = load_workflow_from_file(file_path, registry, parser)
                if result:
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to load workflow from {file_path}: {e}")

    return count


def load_workflow_from_file(
    file_path: str | Path,
    registry: "WorkflowRegistry | None" = None,
    parser: "WorkflowDSLParser | None" = None,
) -> bool:
    """
    Load a single workflow definition from a YAML file.

    Args:
        file_path: Path to workflow YAML file
        registry: Optional WorkflowRegistry instance (uses singleton if not provided)
        parser: Optional WorkflowDSLParser instance (creates new if not provided)

    Returns:
        True if workflow was successfully loaded
    """
    from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
    from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

    file_path = Path(file_path)

    if registry is None:
        registry = WorkflowRegistry.instance()
    if parser is None:
        parser = WorkflowDSLParser()

    try:
        with open(file_path, "r") as f:
            yaml_content = f.read()

        result = parser.parse(yaml_content)

        if not result.success:
            error_msgs = [f"{e.field}: {e.message}" for e in result.errors]
            logger.warning(f"Failed to parse {file_path}: {error_msgs}")
            return False

        # Validate the workflow
        if result.definition is None:
            logger.warning(f"No definition parsed from {file_path}")
            return False

        validation_errors = parser.validate(result.definition)
        if validation_errors:
            logger.warning(f"Validation errors in {file_path}: {validation_errors}")
            return False

        # Register the workflow
        registry.register(result.definition, overwrite=True)
        logger.debug(f"Loaded workflow '{result.definition.name}' from {file_path}")
        return True

    except FileNotFoundError:
        logger.warning(f"Workflow file not found: {file_path}")
        return False
    except Exception as e:
        logger.warning(f"Error loading workflow from {file_path}: {e}")
        return False
