"""
PatternResolver - Bridges task descriptions to pattern execution.

Provides:
- Automatic pattern selection from task semantics via pattern_inference.py
- Explicit hint overrides for user control
- Composition validation at spawn time via validate_composition.py
- Confidence scoring for ambiguity detection

Resolution Priority:
1. Explicit hint (task.metadata["pattern_hint"])
2. Keyword matching (vocabulary analysis via infer_pattern)
3. Default pattern (configurable fallback)

Usage:
    resolver = PatternResolver(default_pattern="Pipeline")
    selection = resolver.resolve(task)
    plan = resolver.resolve_batch(tasks, validate=True)

Integration:
- Reuses infer_pattern() from pattern_inference.py for keyword matching
- Reuses can_compose() from validate_composition.py for validation
- Integrates with ScopeType from scope_manager.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from scripts.agentica_patterns.pattern_inference import (
    Pattern,
    infer_pattern,
)
from scripts.validate_composition import (
    Operator,
    ScopeType,
    ValidationResult,
    can_compose,
    normalize_pattern_name,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Type Aliases
# ============================================================================

ResolutionSource = Literal["hint", "keyword", "default"]


# ============================================================================
# Pattern to Scope Mapping
# ============================================================================

# Based on PATTERNS dict from validate_composition.py
PATTERN_DEFAULT_SCOPE: dict[str, ScopeType] = {
    # Sequential patterns -> HANDOFF (state transfer at boundaries)
    "Pipeline": ScopeType.HANDOFF,
    "GeneratorCritic": ScopeType.HANDOFF,
    "ChainOfResponsibility": ScopeType.HANDOFF,
    "Aggregator": ScopeType.HANDOFF,
    "MapReduce": ScopeType.HANDOFF,  # Prefer handoff for aggregation

    # Parallel isolated patterns -> ISOLATED (no shared state)
    "Swarm": ScopeType.ISOLATED,
    "Jury": ScopeType.ISOLATED,
    "CircuitBreaker": ScopeType.ISOLATED,
    "Adversarial": ScopeType.ISOLATED,

    # Shared state patterns -> SHARED
    "Blackboard": ScopeType.SHARED,
    "Broadcast": ScopeType.SHARED,
    "Consensus": ScopeType.SHARED,
    "EventDriven": ScopeType.SHARED,

    # Hierarchical -> FEDERATED (coordinator reads child state)
    "Hierarchical": ScopeType.FEDERATED,
}


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class PatternSelection:
    """Result of pattern resolution for a single task."""

    pattern: str                    # Pattern name (e.g., "Swarm", "Pipeline")
    confidence: float               # 0.0-1.0, based on signal strength
    scope_type: ScopeType           # Recommended scope for this pattern
    source: ResolutionSource        # How pattern was determined
    signals: list[str] = field(default_factory=list)  # Matched keywords
    alternatives: list[str] = field(default_factory=list)  # Other viable patterns


@dataclass
class CompositionStep:
    """A single step in a composition plan."""

    task_id: str
    pattern: str
    scope_type: ScopeType
    depends_on: list[str]           # Task IDs this step depends on
    selection: PatternSelection


@dataclass
class CompositionPlan:
    """Validated plan for executing multiple tasks."""

    steps: list[CompositionStep]
    valid: bool
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)


# ============================================================================
# Pattern Enum to Name Mapping
# ============================================================================

def _pattern_enum_to_name(pattern: Pattern) -> str:
    """Convert Pattern enum to canonical pattern name."""
    # Map Pattern enum values to PATTERNS dict keys
    mapping = {
        Pattern.SWARM: "Swarm",
        Pattern.HIERARCHICAL: "Hierarchical",
        Pattern.PIPELINE: "Pipeline",
        Pattern.GENERATOR_CRITIC: "GeneratorCritic",
        Pattern.ADVERSARIAL: "Adversarial",
        Pattern.MAP_REDUCE: "MapReduce",
        Pattern.JURY: "Jury",
        Pattern.BLACKBOARD: "Blackboard",
        Pattern.CIRCUIT_BREAKER: "CircuitBreaker",
        Pattern.CHAIN_OF_RESPONSIBILITY: "ChainOfResponsibility",
        Pattern.EVENT_DRIVEN: "EventDriven",
    }
    return mapping.get(pattern, "Pipeline")


def _get_default_scope(pattern_name: str) -> ScopeType:
    """Get default scope for a pattern."""
    return PATTERN_DEFAULT_SCOPE.get(pattern_name, ScopeType.HANDOFF)


# ============================================================================
# PatternResolver Class
# ============================================================================


class PatternResolver:
    """
    Resolves task descriptions to pattern selections.

    Resolution priority:
    1. Explicit hint (task.metadata["pattern_hint"])
    2. Keyword matching (vocabulary analysis)
    3. Default pattern (configurable fallback)

    Usage:
        resolver = PatternResolver(default_pattern="Pipeline")
        selection = resolver.resolve(task)
        plan = resolver.resolve_batch(tasks, validate=True)
    """

    def __init__(
        self,
        default_pattern: str = "Pipeline",
        min_confidence: float = 0.3,
    ) -> None:
        """
        Initialize PatternResolver.

        Args:
            default_pattern: Fallback pattern when no signals detected
            min_confidence: Minimum confidence for keyword matches
        """
        self.default_pattern = default_pattern
        self.min_confidence = min_confidence

    def resolve(
        self,
        task: dict[str, Any] | Any,
        context: dict[str, Any] | None = None,
    ) -> PatternSelection:
        """
        Resolve a single task to a pattern selection.

        Args:
            task: Task dict with description and optional metadata
                  Supports BeadsTask or dict-like objects
            context: Optional context (completed tasks, parent pattern)

        Returns:
            PatternSelection with pattern, confidence, scope, source
        """
        # Extract task fields (support both dict and object-like access)
        if isinstance(task, dict):
            description = task.get("description", "")
            metadata = task.get("metadata", {})
        else:
            description = getattr(task, "description", "")
            metadata = getattr(task, "metadata", {})

        # Step 1: Check explicit hint
        pattern_hint = metadata.get("pattern_hint")
        if pattern_hint:
            normalized_hint = normalize_pattern_name(pattern_hint)
            if normalized_hint:
                return PatternSelection(
                    pattern=normalized_hint,
                    confidence=1.0,
                    scope_type=_get_default_scope(normalized_hint),
                    source="hint",
                    signals=[],
                    alternatives=[],
                )
            else:
                # Invalid hint, log warning and fall through
                logger.warning(
                    f"Invalid pattern_hint '{pattern_hint}', falling through to keyword matching"
                )

        # Step 2: Keyword matching via pattern_inference.py
        if description:
            inference = infer_pattern(description)

            # Convert Pattern enum to string
            pattern_name = _pattern_enum_to_name(inference.pattern)

            # Get alternatives as strings
            alternatives = [
                _pattern_enum_to_name(p)
                for p in inference.alternatives[:3]
            ]

            if inference.confidence >= self.min_confidence:
                return PatternSelection(
                    pattern=pattern_name,
                    confidence=inference.confidence,
                    scope_type=_get_default_scope(pattern_name),
                    source="keyword",
                    signals=inference.signals,
                    alternatives=alternatives,
                )

        # Step 3: Default fallback
        return PatternSelection(
            pattern=self.default_pattern,
            confidence=0.2,  # Low confidence for defaults
            scope_type=_get_default_scope(self.default_pattern),
            source="default",
            signals=[],
            alternatives=[],
        )

    def resolve_from_workflow(
        self,
        workflow_name: str,
    ) -> PatternSelection | None:
        """
        Resolve pattern from a registered workflow definition.

        Looks up the workflow in WorkflowRegistry and returns a PatternSelection
        based on the workflow's default_pattern and pattern_config.

        Args:
            workflow_name: Name of the registered workflow

        Returns:
            PatternSelection if workflow found, None otherwise
        """
        try:
            from scripts.agentica_patterns.workflow_registry import (
                WorkflowRegistry,
            )

            registry = WorkflowRegistry.instance()
            workflow = registry.get_or_none(workflow_name)

            if workflow is None:
                return None

            # Get pattern from workflow definition
            pattern = workflow.default_pattern or self.default_pattern
            scope_type = _get_default_scope(pattern)

            # Build signals from pattern_config keys
            signals = list(workflow.pattern_config.keys()) if workflow.pattern_config else []

            return PatternSelection(
                pattern=pattern,
                confidence=0.9,  # High confidence for explicit workflow
                scope_type=scope_type,
                source="hint",  # Use "hint" since it's an explicit definition
                signals=signals,
                alternatives=[],
            )
        except ImportError:
            # WorkflowRegistry not available
            logger.warning("WorkflowRegistry not available for workflow resolution")
            return None

    def resolve_batch(
        self,
        tasks: list[dict[str, Any] | Any],
        validate: bool = True,
    ) -> CompositionPlan:
        """
        Resolve multiple tasks and validate compositions.

        Args:
            tasks: List of task dicts or BeadsTask instances
            validate: Whether to validate pattern compositions

        Returns:
            CompositionPlan with steps and validation status
        """
        if not tasks:
            return CompositionPlan(steps=[], valid=True)

        # Step 1: Resolve each task independently
        selections: dict[str, PatternSelection] = {}
        task_deps: dict[str, list[str]] = {}

        for task in tasks:
            # Get task ID
            if isinstance(task, dict):
                task_id = task.get("id")
                metadata = task.get("metadata", {})
            else:
                task_id = getattr(task, "id", None)
                metadata = getattr(task, "metadata", {})

            if not task_id:
                raise ValueError("Task must have an 'id' field")

            selections[task_id] = self.resolve(task)
            task_deps[task_id] = metadata.get("depends_on", [])

        # Step 2: Check for circular dependencies
        validation_errors: list[str] = []
        validation_warnings: list[str] = []

        if validate:
            # Detect cycles
            cycle = self._detect_cycle(task_deps)
            if cycle:
                validation_errors.append(
                    f"Circular dependency detected: {' -> '.join(cycle)}"
                )

            # Validate compositions for each dependency pair
            for task_id, deps in task_deps.items():
                for dep_id in deps:
                    if dep_id not in selections:
                        # Dependency task not in batch (external)
                        continue

                    result = self.validate(
                        selections[dep_id].pattern,
                        selections[task_id].pattern,
                        selections[task_id].scope_type,
                    )

                    if not result.valid:
                        validation_errors.extend(result.errors)

                    validation_warnings.extend(result.warnings)

        # Step 3: Build composition plan (topologically sorted if no cycles)
        if validation_errors and any("Circular" in e for e in validation_errors):
            # Can't sort with cycles, use original order
            sorted_ids = [
                task.get("id") if isinstance(task, dict) else getattr(task, "id")
                for task in tasks
            ]
        else:
            sorted_ids = self._topological_sort(task_deps)

        steps = [
            CompositionStep(
                task_id=tid,
                pattern=selections[tid].pattern,
                scope_type=selections[tid].scope_type,
                depends_on=task_deps.get(tid, []),
                selection=selections[tid],
            )
            for tid in sorted_ids
        ]

        return CompositionPlan(
            steps=steps,
            valid=len(validation_errors) == 0,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
        )

    def validate(
        self,
        pattern_a: str,
        pattern_b: str,
        scope: ScopeType,
    ) -> ValidationResult:
        """
        Validate if two patterns can compose under given scope.

        Delegates to can_compose() from validate_composition.py.

        Args:
            pattern_a: First pattern name
            pattern_b: Second pattern name
            scope: ScopeType for composition

        Returns:
            ValidationResult with valid flag and errors
        """
        return can_compose(pattern_a, pattern_b, scope, Operator.SEQUENTIAL)

    def _detect_cycle(self, deps: dict[str, list[str]]) -> list[str] | None:
        """
        Detect cycle in dependency graph using DFS.

        Returns the cycle path if found, None otherwise.
        """
        white, gray, black = 0, 1, 2
        color: dict[str, int] = {k: white for k in deps}
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            if node not in color:
                return None

            color[node] = gray
            path.append(node)

            for neighbor in deps.get(node, []):
                if neighbor not in color:
                    continue

                if color[neighbor] == gray:
                    # Found cycle - return path from neighbor to current
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

                if color[neighbor] == white:
                    result = dfs(neighbor)
                    if result:
                        return result

            path.pop()
            color[node] = black
            return None

        for node in deps:
            if color[node] == white:
                result = dfs(node)
                if result:
                    return result

        return None

    def _topological_sort(self, deps: dict[str, list[str]]) -> list[str]:
        """
        Topologically sort tasks by dependencies.

        Returns list of task IDs in execution order.
        """
        # Kahn's algorithm
        in_degree: dict[str, int] = {k: 0 for k in deps}

        for task_id, task_deps in deps.items():
            for dep in task_deps:
                if dep in in_degree:
                    in_degree[task_id] += 1

        # Start with nodes that have no dependencies
        queue = [k for k, v in in_degree.items() if v == 0]
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # Find all tasks that depend on this node
            for task_id, task_deps in deps.items():
                if node in task_deps:
                    in_degree[task_id] -= 1
                    if in_degree[task_id] == 0 and task_id not in result:
                        queue.append(task_id)

        # Add any remaining tasks (no dependencies declared)
        for task_id in deps:
            if task_id not in result:
                result.append(task_id)

        return result
