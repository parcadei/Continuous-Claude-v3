"""
WorkflowDSLParser - Parse YAML workflow definitions.

Provides:
- YAML to WorkflowDefinition conversion
- Validation with helpful error messages
- Cycle detection in step dependencies
- Variable interpolation support (future)

Usage:
    parser = WorkflowDSLParser()
    result = parser.parse(yaml_content)
    if result.success:
        workflow = result.definition
        errors = parser.validate(workflow)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from scripts.agentica_patterns.workflow_registry_types import (
    WorkflowDefinition,
    StepDefinition,
    TriggerDefinition,
    InputDefinition,
    GoalType,
    ResourceAllocation,
)


@dataclass
class ParseError:
    """Error encountered during parsing."""

    field: str
    message: str
    line: int | None = None


@dataclass
class ParseResult:
    """Result of parsing a workflow definition."""

    success: bool
    definition: WorkflowDefinition | None
    errors: list[ParseError]
    warnings: list[str] = field(default_factory=list)


class WorkflowDSLParser:
    """
    Parse YAML workflow definitions into WorkflowDefinition objects.

    Supports the format from research.md YAML DSL examples.
    """

    def parse(self, yaml_content: str) -> ParseResult:
        """
        Parse YAML content into a WorkflowDefinition.

        Args:
            yaml_content: YAML string

        Returns:
            ParseResult with definition or errors
        """
        errors: list[ParseError] = []
        warnings: list[str] = []

        try:
            raw = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return ParseResult(
                success=False,
                definition=None,
                errors=[ParseError("yaml", f"Invalid YAML: {e}")],
                warnings=[],
            )

        if not isinstance(raw, dict):
            return ParseResult(
                success=False,
                definition=None,
                errors=[ParseError("root", "Root must be a mapping")],
                warnings=[],
            )

        # Required field: name
        name = raw.get("name")
        if not name:
            errors.append(ParseError("name", "name is required"))
            return ParseResult(False, None, errors, warnings)

        # Parse optional fields
        version = raw.get("version", "1.0")
        description = raw.get("description", "")

        # Parse goal_type
        goal_type = GoalType.BUILD
        if "goal_type" in raw:
            try:
                goal_type = GoalType(raw["goal_type"])
            except ValueError:
                errors.append(
                    ParseError(
                        "goal_type",
                        f"Invalid goal_type: {raw['goal_type']}. "
                        f"Must be one of: {[g.value for g in GoalType]}",
                    )
                )

        # Parse resource_allocation
        resource_allocation = ResourceAllocation.BALANCED
        if "resource_allocation" in raw:
            try:
                resource_allocation = ResourceAllocation(raw["resource_allocation"])
            except ValueError:
                errors.append(
                    ParseError(
                        "resource_allocation",
                        f"Invalid resource_allocation: {raw['resource_allocation']}",
                    )
                )

        # Parse steps
        steps = self._parse_steps(raw.get("steps", []), errors)

        # Parse triggers
        triggers = self._parse_triggers(raw.get("triggers", []), errors)

        # Parse inputs
        inputs = self._parse_inputs(raw.get("inputs", {}), errors)

        # Parse agent_mapping
        agent_mapping = raw.get("agent_mapping", {})
        if not isinstance(agent_mapping, dict):
            errors.append(ParseError("agent_mapping", "agent_mapping must be a mapping"))
            agent_mapping = {}

        # Parse tags
        tags = raw.get("tags", [])
        if not isinstance(tags, list):
            errors.append(ParseError("tags", "tags must be a list"))
            tags = []

        if errors:
            return ParseResult(False, None, errors, warnings)

        definition = WorkflowDefinition(
            name=name,
            version=str(version),
            description=description,
            goal_type=goal_type,
            agent_mapping=agent_mapping,
            default_pattern=raw.get("default_pattern", "Pipeline"),
            resource_allocation=resource_allocation,
            pattern_config=raw.get("pattern_config", {}),
            steps=steps,
            triggers=triggers,
            inputs=inputs,
            tags=tags,
            on_failure=raw.get("on_failure", []),
        )

        return ParseResult(True, definition, [], warnings)

    def _parse_steps(
        self,
        raw_steps: list[dict[str, Any]],
        errors: list[ParseError],
    ) -> list[StepDefinition]:
        """Parse step definitions from raw YAML."""
        steps = []

        if not isinstance(raw_steps, list):
            errors.append(ParseError("steps", "steps must be a list"))
            return []

        for i, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, dict):
                errors.append(ParseError(f"steps[{i}]", "step must be a mapping"))
                continue

            step_id = raw_step.get("id")
            step_type = raw_step.get("type")

            if not step_id:
                errors.append(ParseError(f"steps[{i}]", "step.id is required"))
                continue
            if not step_type:
                errors.append(ParseError(f"steps[{i}]", "step.type is required"))
                continue

            depends_on = raw_step.get("depends_on", [])
            if not isinstance(depends_on, list):
                depends_on = [depends_on] if depends_on else []

            steps.append(
                StepDefinition(
                    id=step_id,
                    type=step_type,
                    depends_on=depends_on,
                    config=raw_step.get("config", {}),
                    input=raw_step.get("input"),
                    rules=raw_step.get("rules"),
                    operations=raw_step.get("operations"),
                )
            )

        return steps

    def _parse_triggers(
        self,
        raw_triggers: list[dict[str, Any]],
        errors: list[ParseError],
    ) -> list[TriggerDefinition]:
        """Parse trigger definitions from raw YAML."""
        triggers = []

        if not isinstance(raw_triggers, list):
            errors.append(ParseError("triggers", "triggers must be a list"))
            return []

        for raw_trigger in raw_triggers:
            if not isinstance(raw_trigger, dict):
                continue
            triggers.append(
                TriggerDefinition(
                    schedule=raw_trigger.get("schedule"),
                    event=raw_trigger.get("event"),
                )
            )

        return triggers

    def _parse_inputs(
        self,
        raw_inputs: dict[str, dict[str, Any]],
        errors: list[ParseError],
    ) -> dict[str, InputDefinition]:
        """Parse input definitions from raw YAML."""
        inputs = {}

        if not isinstance(raw_inputs, dict):
            errors.append(ParseError("inputs", "inputs must be a mapping"))
            return {}

        for name, spec in raw_inputs.items():
            if not isinstance(spec, dict):
                spec = {}

            inputs[name] = InputDefinition(
                name=name,
                type=spec.get("type", "string"),
                required=spec.get("required", False),
                default=spec.get("default"),
                choices=spec.get("choices"),
            )

        return inputs

    def validate(self, definition: WorkflowDefinition) -> list[str]:
        """
        Validate workflow definition for common errors.

        Args:
            definition: WorkflowDefinition to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check step dependencies exist
        step_ids = {s.id for s in definition.steps}
        for step in definition.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(
                        f"Step '{step.id}' depends on unknown step '{dep}'"
                    )

        # Check for cycles
        if self._has_cycle(definition.steps):
            errors.append("Workflow contains circular dependencies")

        return errors

    def _has_cycle(self, steps: list[StepDefinition]) -> bool:
        """
        Detect cycles in step dependencies using DFS.

        Args:
            steps: List of step definitions

        Returns:
            True if a cycle is detected
        """
        step_map = {s.id: s for s in steps}
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(step_id: str) -> bool:
            if step_id not in step_map:
                return False

            visited.add(step_id)
            rec_stack.add(step_id)

            step = step_map[step_id]
            for dep in step.depends_on:
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(step_id)
            return False

        for step in steps:
            if step.id not in visited:
                if dfs(step.id):
                    return True
        return False
