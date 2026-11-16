"""
Type definitions for WorkflowRegistry.

Provides structured types for:
- WorkflowDefinition: Complete workflow specification
- PatternConfig: Pattern-specific configuration
- StepDefinition: Individual step in a workflow
- GoalType: Workflow goal types (research, plan, build, fix)
- ResourceAllocation: Agent resource allocation levels
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from scripts.validate_composition import ScopeType


class GoalType(Enum):
    """Goal types matching workflow-router SKILL.md."""

    RESEARCH = "research"
    PLAN = "plan"
    BUILD = "build"
    FIX = "fix"


class ResourceAllocation(Enum):
    """Resource allocation levels."""

    CONSERVATIVE = "conservative"  # 1-2 agents, sequential
    BALANCED = "balanced"  # Appropriate agents, some parallelism
    AGGRESSIVE = "aggressive"  # Max parallel agents


@dataclass
class StepDefinition:
    """A single step in a workflow."""

    id: str
    type: str  # Pattern name or custom handler
    depends_on: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    input: str | None = None
    rules: list[Any] | None = None
    operations: list[dict[str, Any]] | None = None


@dataclass
class TriggerDefinition:
    """Workflow trigger configuration."""

    schedule: str | None = None  # Cron expression
    event: str | None = None  # Event name


@dataclass
class InputDefinition:
    """Workflow input parameter definition."""

    name: str
    type: str = "string"
    required: bool = False
    default: Any = None
    choices: list[Any] | None = None


@dataclass
class PatternConfig:
    """Configuration for a specific pattern."""

    name: str
    class_name: str  # Swarm, Pipeline, etc.
    required_params: list[str] = field(default_factory=list)
    optional_params: dict[str, Any] = field(default_factory=dict)
    compatible_scopes: list[ScopeType] = field(default_factory=list)


@dataclass
class WorkflowDefinition:
    """Complete workflow specification."""

    name: str
    version: str = "1.0"
    description: str = ""
    goal_type: GoalType = GoalType.BUILD

    # Agent configuration
    agent_mapping: dict[str, str] = field(
        default_factory=dict
    )  # alias -> subagent_type
    default_pattern: str = "Pipeline"
    resource_allocation: ResourceAllocation = ResourceAllocation.BALANCED

    # Pattern configuration
    pattern_config: dict[str, Any] = field(default_factory=dict)

    # Workflow steps
    steps: list[StepDefinition] = field(default_factory=list)

    # Metadata
    triggers: list[TriggerDefinition] = field(default_factory=list)
    inputs: dict[str, InputDefinition] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    on_failure: list[dict[str, Any]] = field(default_factory=list)
