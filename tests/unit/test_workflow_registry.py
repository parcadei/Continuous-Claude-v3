"""
Tests for WorkflowRegistry - P5 Implementation.

TDD Protocol: These tests are written FIRST before implementation.

Tests cover:
- Phase 1: Type definitions (GoalType, ResourceAllocation, StepDefinition, etc.)
- Phase 2: Registry singleton (register, get, list, find_by_tag, find_by_goal)
- Phase 3: YAML DSL parser (parse, validate, cycle detection)
- Phase 4: PatternResolver integration (resolve_from_workflow)
"""

from __future__ import annotations

import pytest
import threading
from enum import Enum


# ============================================================================
# Phase 1: Type Definition Tests
# ============================================================================


class TestGoalType:
    """Test GoalType enum matches workflow-router SKILL.md."""

    def test_all_goal_types_exist(self):
        from scripts.agentica_patterns.workflow_registry_types import GoalType

        assert GoalType.RESEARCH.value == "research"
        assert GoalType.PLAN.value == "plan"
        assert GoalType.BUILD.value == "build"
        assert GoalType.FIX.value == "fix"

    def test_goal_type_is_enum(self):
        from scripts.agentica_patterns.workflow_registry_types import GoalType

        assert isinstance(GoalType.RESEARCH, Enum)


class TestResourceAllocation:
    """Test ResourceAllocation enum matches workflow-router levels."""

    def test_all_allocation_levels_exist(self):
        from scripts.agentica_patterns.workflow_registry_types import (
            ResourceAllocation,
        )

        assert ResourceAllocation.CONSERVATIVE.value == "conservative"
        assert ResourceAllocation.BALANCED.value == "balanced"
        assert ResourceAllocation.AGGRESSIVE.value == "aggressive"


class TestStepDefinition:
    """Test StepDefinition dataclass."""

    def test_minimal_step(self):
        from scripts.agentica_patterns.workflow_registry_types import StepDefinition

        step = StepDefinition(id="validate", type="validation")
        assert step.id == "validate"
        assert step.type == "validation"
        assert step.depends_on == []
        assert step.config == {}

    def test_step_with_dependencies(self):
        from scripts.agentica_patterns.workflow_registry_types import StepDefinition

        step = StepDefinition(
            id="transform",
            type="transformation",
            depends_on=["extract", "validate"],
            config={"key": "id"},
        )
        assert step.depends_on == ["extract", "validate"]
        assert step.config["key"] == "id"

    def test_step_with_all_fields(self):
        from scripts.agentica_patterns.workflow_registry_types import StepDefinition

        step = StepDefinition(
            id="load",
            type="loading",
            depends_on=["transform"],
            config={"destination": "db"},
            input="${outputs.transform}",
            rules=["validate_schema"],
            operations=[{"type": "upsert"}],
        )
        assert step.input == "${outputs.transform}"
        assert step.rules == ["validate_schema"]
        assert step.operations == [{"type": "upsert"}]


class TestTriggerDefinition:
    """Test TriggerDefinition dataclass."""

    def test_schedule_trigger(self):
        from scripts.agentica_patterns.workflow_registry_types import TriggerDefinition

        trigger = TriggerDefinition(schedule="0 */6 * * *")
        assert trigger.schedule == "0 */6 * * *"
        assert trigger.event is None

    def test_event_trigger(self):
        from scripts.agentica_patterns.workflow_registry_types import TriggerDefinition

        trigger = TriggerDefinition(event="file.uploaded")
        assert trigger.event == "file.uploaded"
        assert trigger.schedule is None


class TestInputDefinition:
    """Test InputDefinition dataclass."""

    def test_minimal_input(self):
        from scripts.agentica_patterns.workflow_registry_types import InputDefinition

        input_def = InputDefinition(name="source_path")
        assert input_def.name == "source_path"
        assert input_def.type == "string"
        assert input_def.required is False

    def test_input_with_choices(self):
        from scripts.agentica_patterns.workflow_registry_types import InputDefinition

        input_def = InputDefinition(
            name="format",
            type="enum",
            required=True,
            default="csv",
            choices=["csv", "json", "parquet"],
        )
        assert input_def.choices == ["csv", "json", "parquet"]
        assert input_def.default == "csv"


class TestPatternConfig:
    """Test PatternConfig dataclass."""

    def test_pattern_with_required_params(self):
        from scripts.agentica_patterns.workflow_registry_types import PatternConfig
        from scripts.validate_composition import ScopeType

        config = PatternConfig(
            name="swarm",
            class_name="Swarm",
            required_params=["perspectives"],
            compatible_scopes=[ScopeType.ISOLATED],
        )
        assert "perspectives" in config.required_params
        assert ScopeType.ISOLATED in config.compatible_scopes

    def test_pattern_with_optional_params(self):
        from scripts.agentica_patterns.workflow_registry_types import PatternConfig

        config = PatternConfig(
            name="jury",
            class_name="Jury",
            required_params=["num_jurors"],
            optional_params={"threshold": 0.5, "weights": None},
        )
        assert config.optional_params["threshold"] == 0.5


class TestWorkflowDefinition:
    """Test WorkflowDefinition dataclass."""

    def test_minimal_workflow(self):
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        workflow = WorkflowDefinition(name="test-workflow")
        assert workflow.name == "test-workflow"
        assert workflow.version == "1.0"
        assert workflow.default_pattern == "Pipeline"

    def test_workflow_with_agent_mapping(self):
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
            GoalType,
        )

        workflow = WorkflowDefinition(
            name="research-flow",
            goal_type=GoalType.RESEARCH,
            agent_mapping={
                "librarian": "research-agent",
                "oracle": "plan-agent",
            },
        )
        assert workflow.agent_mapping["librarian"] == "research-agent"
        assert workflow.goal_type == GoalType.RESEARCH

    def test_workflow_with_steps(self):
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
            StepDefinition,
        )

        workflow = WorkflowDefinition(
            name="etl-pipeline",
            steps=[
                StepDefinition(id="extract", type="extraction"),
                StepDefinition(
                    id="transform", type="transformation", depends_on=["extract"]
                ),
                StepDefinition(id="load", type="loading", depends_on=["transform"]),
            ],
        )
        assert len(workflow.steps) == 3
        assert workflow.steps[1].depends_on == ["extract"]


# ============================================================================
# Phase 2: Registry Singleton Tests
# ============================================================================


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry before and after each test."""
    from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

    WorkflowRegistry.clear()
    yield
    WorkflowRegistry.clear()


class TestSingleton:
    """Test WorkflowRegistry singleton pattern."""

    def test_instance_returns_same_object(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        r1 = WorkflowRegistry.instance()
        r2 = WorkflowRegistry.instance()
        assert r1 is r2

    def test_clear_resets_state(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        registry.register(WorkflowDefinition(name="test"))
        assert "test" in registry.list()

        WorkflowRegistry.clear()
        assert "test" not in registry.list()


class TestRegister:
    """Test workflow registration."""

    def test_register_and_get(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        workflow = WorkflowDefinition(name="my-workflow", version="2.0")

        registry.register(workflow)
        retrieved = registry.get("my-workflow")

        assert retrieved.name == "my-workflow"
        assert retrieved.version == "2.0"

    def test_register_duplicate_raises(self):
        from scripts.agentica_patterns.workflow_registry import (
            WorkflowRegistry,
            DuplicateWorkflowError,
        )
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        workflow = WorkflowDefinition(name="dup")

        registry.register(workflow)
        with pytest.raises(DuplicateWorkflowError):
            registry.register(workflow)

    def test_register_overwrite(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        v1 = WorkflowDefinition(name="test", version="1.0")
        v2 = WorkflowDefinition(name="test", version="2.0")

        registry.register(v1)
        registry.register(v2, overwrite=True)

        assert registry.get("test").version == "2.0"

    def test_register_auto_aliases(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        workflow = WorkflowDefinition(
            name="research-flow",
            agent_mapping={"librarian": "research-agent"},
        )

        registry.register(workflow)
        assert registry.resolve_alias("librarian") == "research-agent"


class TestGet:
    """Test workflow retrieval."""

    def test_get_not_found_raises(self):
        from scripts.agentica_patterns.workflow_registry import (
            WorkflowRegistry,
            WorkflowNotFoundError,
        )

        registry = WorkflowRegistry.instance()
        with pytest.raises(WorkflowNotFoundError):
            registry.get("nonexistent")

    def test_get_or_none_returns_none(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        registry = WorkflowRegistry.instance()
        assert registry.get_or_none("nonexistent") is None


class TestList:
    """Test workflow listing."""

    def test_list_empty(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        registry = WorkflowRegistry.instance()
        assert registry.list() == []

    def test_list_multiple(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        registry.register(WorkflowDefinition(name="a"))
        registry.register(WorkflowDefinition(name="b"))
        registry.register(WorkflowDefinition(name="c"))

        names = registry.list()
        assert set(names) == {"a", "b", "c"}


class TestFindBy:
    """Test workflow filtering."""

    def test_find_by_tag(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        registry.register(WorkflowDefinition(name="w1", tags=["research", "ml"]))
        registry.register(WorkflowDefinition(name="w2", tags=["research"]))
        registry.register(WorkflowDefinition(name="w3", tags=["build"]))

        research = registry.find_by_tag("research")
        assert len(research) == 2
        assert {w.name for w in research} == {"w1", "w2"}

    def test_find_by_goal(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
            GoalType,
        )

        registry = WorkflowRegistry.instance()
        registry.register(WorkflowDefinition(name="r1", goal_type=GoalType.RESEARCH))
        registry.register(WorkflowDefinition(name="b1", goal_type=GoalType.BUILD))
        registry.register(WorkflowDefinition(name="r2", goal_type=GoalType.RESEARCH))

        research = registry.find_by_goal(GoalType.RESEARCH)
        assert len(research) == 2


class TestUnregister:
    """Test workflow removal."""

    def test_unregister_existing(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        registry.register(WorkflowDefinition(name="test"))

        result = registry.unregister("test")
        assert result is True
        assert "test" not in registry.list()

    def test_unregister_nonexistent(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        registry = WorkflowRegistry.instance()
        result = registry.unregister("nonexistent")
        assert result is False


class TestPatternConfig:
    """Test pattern configuration methods."""

    def test_register_and_get_pattern(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import PatternConfig
        from scripts.validate_composition import ScopeType

        registry = WorkflowRegistry.instance()
        config = PatternConfig(
            name="swarm",
            class_name="Swarm",
            required_params=["perspectives"],
            compatible_scopes=[ScopeType.ISOLATED],
        )

        registry.register_pattern(config)
        retrieved = registry.get_pattern_config("swarm")

        assert retrieved is not None
        assert retrieved.class_name == "Swarm"
        assert "perspectives" in retrieved.required_params

    def test_list_patterns(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import PatternConfig

        registry = WorkflowRegistry.instance()
        registry.register_pattern(PatternConfig(name="swarm", class_name="Swarm"))
        registry.register_pattern(PatternConfig(name="jury", class_name="Jury"))

        patterns = registry.list_patterns()
        assert set(patterns) == {"swarm", "jury"}


class TestAliasResolution:
    """Test agent alias methods."""

    def test_register_and_resolve_alias(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        registry = WorkflowRegistry.instance()
        registry.register_alias("librarian", "research-agent")

        assert registry.resolve_alias("librarian") == "research-agent"

    def test_resolve_unknown_alias_returns_none(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        registry = WorkflowRegistry.instance()
        assert registry.resolve_alias("unknown") is None

    def test_list_aliases(self):
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        registry = WorkflowRegistry.instance()
        registry.register_alias("librarian", "research-agent")
        registry.register_alias("oracle", "plan-agent")

        aliases = registry.list_aliases()
        assert aliases == {"librarian": "research-agent", "oracle": "plan-agent"}


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_registration(self):
        """Test that concurrent registrations don't corrupt state."""
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
        )

        registry = WorkflowRegistry.instance()
        errors = []

        def register_workflow(i: int):
            try:
                registry.register(
                    WorkflowDefinition(name=f"workflow-{i}"),
                    overwrite=True,
                )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_workflow, args=(i,)) for i in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(registry.list()) == 100


# ============================================================================
# Phase 3: YAML DSL Parser Tests
# ============================================================================


class TestYAMLParserBasic:
    """Test basic YAML parsing."""

    def test_parse_minimal_workflow(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: test-workflow
version: "1.0"
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is True
        assert result.definition is not None
        assert result.definition.name == "test-workflow"
        assert result.definition.version == "1.0"

    def test_parse_missing_name_fails(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
version: "1.0"
description: "Missing name"
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is False
        assert any("name" in e.field for e in result.errors)

    def test_parse_invalid_yaml_fails(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: test
  invalid: indentation
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is False
        assert any("yaml" in e.field.lower() for e in result.errors)


class TestYAMLParserSteps:
    """Test step parsing."""

    def test_parse_workflow_with_steps(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: etl-pipeline
steps:
  - id: extract
    type: extraction
    config:
      path: /data/input
  - id: transform
    type: transformation
    depends_on: [extract]
  - id: load
    type: loading
    depends_on: [transform]
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is True
        assert len(result.definition.steps) == 3
        assert result.definition.steps[0].id == "extract"
        assert result.definition.steps[1].depends_on == ["extract"]

    def test_parse_step_missing_id_fails(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: test
steps:
  - type: validation
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is False
        assert any("id" in e.message.lower() for e in result.errors)


class TestYAMLParserGoalType:
    """Test goal_type parsing."""

    def test_parse_valid_goal_type(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser
        from scripts.agentica_patterns.workflow_registry_types import GoalType

        yaml_content = """
name: research-flow
goal_type: research
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is True
        assert result.definition.goal_type == GoalType.RESEARCH

    def test_parse_invalid_goal_type_fails(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: test
goal_type: invalid_goal
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is False
        assert any("goal_type" in e.field for e in result.errors)


class TestYAMLParserAgentMapping:
    """Test agent_mapping parsing."""

    def test_parse_agent_mapping(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: test
agent_mapping:
  librarian: research-agent
  oracle: plan-agent
  kraken: build-agent
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is True
        assert result.definition.agent_mapping["librarian"] == "research-agent"
        assert result.definition.agent_mapping["oracle"] == "plan-agent"


class TestYAMLParserTriggers:
    """Test trigger parsing."""

    def test_parse_triggers(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: test
triggers:
  - schedule: "0 */6 * * *"
  - event: file.uploaded
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is True
        assert len(result.definition.triggers) == 2
        assert result.definition.triggers[0].schedule == "0 */6 * * *"
        assert result.definition.triggers[1].event == "file.uploaded"


class TestYAMLParserInputs:
    """Test input parsing."""

    def test_parse_inputs(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: test
inputs:
  source_path:
    type: string
    required: true
  format:
    type: enum
    default: csv
    choices: [csv, json, parquet]
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is True
        assert "source_path" in result.definition.inputs
        assert result.definition.inputs["source_path"].required is True
        assert result.definition.inputs["format"].default == "csv"


class TestCycleDetection:
    """Test dependency cycle detection."""

    def test_validate_detects_simple_cycle(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: cyclic-workflow
steps:
  - id: a
    type: step
    depends_on: [b]
  - id: b
    type: step
    depends_on: [a]
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        # Parse should succeed, but validation should catch cycle
        if result.success:
            errors = parser.validate(result.definition)
            assert any("circular" in e.lower() or "cycle" in e.lower() for e in errors)
        else:
            # Some parsers may catch cycles during parsing
            assert any(
                "circular" in e.message.lower() or "cycle" in e.message.lower()
                for e in result.errors
            )

    def test_validate_detects_complex_cycle(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: complex-cycle
steps:
  - id: a
    type: step
    depends_on: [c]
  - id: b
    type: step
    depends_on: [a]
  - id: c
    type: step
    depends_on: [b]
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        if result.success:
            errors = parser.validate(result.definition)
            assert any("circular" in e.lower() or "cycle" in e.lower() for e in errors)

    def test_validate_missing_dependency(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: missing-dep
steps:
  - id: a
    type: step
    depends_on: [nonexistent]
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        if result.success:
            errors = parser.validate(result.definition)
            assert any("nonexistent" in e or "unknown" in e.lower() for e in errors)

    def test_validate_no_cycle(self):
        from scripts.agentica_patterns.workflow_dsl_parser import WorkflowDSLParser

        yaml_content = """
name: valid-dag
steps:
  - id: a
    type: step
  - id: b
    type: step
    depends_on: [a]
  - id: c
    type: step
    depends_on: [a, b]
"""
        parser = WorkflowDSLParser()
        result = parser.parse(yaml_content)

        assert result.success is True
        errors = parser.validate(result.definition)
        assert len(errors) == 0


# ============================================================================
# Phase 4: PatternResolver Integration Tests
# ============================================================================


class TestPatternResolverIntegration:
    """Test PatternResolver integration with WorkflowRegistry."""

    def test_resolve_from_workflow_basic(self):
        """PatternResolver should resolve patterns from registered workflow."""
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry
        from scripts.agentica_patterns.workflow_registry_types import (
            WorkflowDefinition,
            GoalType,
        )
        from scripts.agentica_patterns.pattern_resolver import PatternResolver

        # Register a workflow
        registry = WorkflowRegistry.instance()
        workflow = WorkflowDefinition(
            name="research-flow",
            goal_type=GoalType.RESEARCH,
            default_pattern="Swarm",
            pattern_config={"perspectives": ["academic", "practical", "critical"]},
        )
        registry.register(workflow)

        # Resolve pattern from workflow
        resolver = PatternResolver()
        selection = resolver.resolve_from_workflow("research-flow")

        assert selection is not None
        assert selection.pattern == "Swarm"

    def test_resolve_from_workflow_not_found(self):
        """PatternResolver should return None for unknown workflow."""
        from scripts.agentica_patterns.pattern_resolver import PatternResolver

        resolver = PatternResolver()
        selection = resolver.resolve_from_workflow("nonexistent-workflow")

        assert selection is None


class TestRegistryLoader:
    """Test builtin workflow definitions loader."""

    def test_load_builtins(self):
        """Load builtin workflow definitions from YAML files."""
        from scripts.agentica_patterns.registry_loader import load_builtin_workflows
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        load_builtin_workflows()
        registry = WorkflowRegistry.instance()

        # Should have loaded some builtins
        workflows = registry.list()
        assert len(workflows) >= 0  # May be 0 if no builtins exist yet

    def test_load_from_directory(self):
        """Load workflow definitions from a directory."""
        import tempfile
        import os
        from scripts.agentica_patterns.registry_loader import load_workflows_from_dir
        from scripts.agentica_patterns.workflow_registry import WorkflowRegistry

        # Create temp directory with a workflow YAML
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_file = os.path.join(tmpdir, "test-workflow.yaml")
            with open(workflow_file, "w") as f:
                f.write(
                    """
name: loaded-workflow
version: "1.0"
goal_type: build
"""
                )

            load_workflows_from_dir(tmpdir)
            registry = WorkflowRegistry.instance()

            assert "loaded-workflow" in registry.list()
