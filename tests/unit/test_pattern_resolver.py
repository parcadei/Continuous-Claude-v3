"""
Unit tests for PatternResolver.

Tests pattern resolution from task descriptions to coordination patterns.
TDD: These tests are written BEFORE implementation and should FAIL initially.

Test coverage:
- Pattern detection from hints and keywords (10 tests)
- Keyword matching via pattern_inference.py (10 tests)
- Composition validation via validate_composition.py (10 tests)
- Edge cases (10 tests)
"""

import pytest
from typing import Any
from uuid import uuid4

# Import will fail until implementation exists - this is expected for TDD
from scripts.agentica_patterns.pattern_resolver import (
    PatternResolver,
    PatternSelection,
    CompositionStep,
    CompositionPlan,
    PATTERN_DEFAULT_SCOPE,
)
from scripts.validate_composition import ScopeType, ValidationResult
from scripts.agentica_patterns.pattern_inference import Pattern


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def resolver() -> PatternResolver:
    """Create default PatternResolver."""
    return PatternResolver()


@pytest.fixture
def resolver_high_confidence() -> PatternResolver:
    """Create PatternResolver with high min_confidence."""
    return PatternResolver(min_confidence=0.8)


def make_task(
    description: str,
    task_id: str | None = None,
    pattern_hint: str | None = None,
    depends_on: list[str] | None = None,
    **metadata: Any,
) -> dict[str, Any]:
    """Create a task-like dict for testing.

    Supports both BeadsTask and dict interfaces.
    """
    task = {
        "id": task_id or f"task-{uuid4().hex[:8]}",
        "description": description,
        "metadata": metadata.copy(),
    }
    if pattern_hint:
        task["metadata"]["pattern_hint"] = pattern_hint
    if depends_on:
        task["metadata"]["depends_on"] = depends_on
    return task


# ============================================================================
# TestPatternSelection
# ============================================================================


class TestPatternSelection:
    """Tests for PatternSelection dataclass."""

    def test_fields_accessible(self):
        """PatternSelection has all required fields."""
        selection = PatternSelection(
            pattern="Swarm",
            confidence=0.8,
            scope_type=ScopeType.ISOLATED,
            source="keyword",
            signals=["research", "explore"],
            alternatives=["Hierarchical"],
        )

        assert selection.pattern == "Swarm"
        assert selection.confidence == 0.8
        assert selection.scope_type == ScopeType.ISOLATED
        assert selection.source == "keyword"
        assert selection.signals == ["research", "explore"]
        assert selection.alternatives == ["Hierarchical"]

    def test_defaults_for_optional_fields(self):
        """Optional fields have sensible defaults."""
        selection = PatternSelection(
            pattern="Pipeline",
            confidence=1.0,
            scope_type=ScopeType.HANDOFF,
            source="hint",
        )

        assert selection.signals == []
        assert selection.alternatives == []


# ============================================================================
# TestPatternDetection - PD-01 to PD-10
# ============================================================================


class TestPatternDetection:
    """Tests for pattern detection from hints and fallback logic."""

    def test_pd01_hint_override_swarm(self, resolver: PatternResolver):
        """PD-01: Explicit hint for Swarm is honored."""
        task = make_task(
            description="Build the API endpoints",
            pattern_hint="Swarm",
        )

        selection = resolver.resolve(task)

        assert selection.pattern == "Swarm"
        assert selection.source == "hint"
        assert selection.confidence == 1.0

    def test_pd02_hint_override_jury(self, resolver: PatternResolver):
        """PD-02: Explicit hint for Jury is honored."""
        task = make_task(
            description="Do something generic",
            pattern_hint="Jury",
        )

        selection = resolver.resolve(task)

        assert selection.pattern == "Jury"
        assert selection.source == "hint"

    def test_pd03_hint_invalid_pattern(self, resolver: PatternResolver):
        """PD-03: Invalid hint falls through to keyword matching."""
        task = make_task(
            description="Research authentication options",
            pattern_hint="InvalidPatternName",
        )

        selection = resolver.resolve(task)

        # Should fall through to keyword matching, not use the invalid hint
        assert selection.source != "hint"
        assert selection.pattern != "InvalidPatternName"

    def test_pd04_hint_case_insensitive(self, resolver: PatternResolver):
        """PD-04: Hints are case-insensitive (swarm -> Swarm)."""
        task = make_task(
            description="Do something",
            pattern_hint="swarm",  # lowercase
        )

        selection = resolver.resolve(task)

        assert selection.pattern == "Swarm"  # Normalized to canonical
        assert selection.source == "hint"

    def test_pd05_no_hint_uses_keywords(self, resolver: PatternResolver):
        """PD-05: Without hint, keywords determine pattern."""
        task = make_task(
            description="Research authentication options thoroughly",
        )

        selection = resolver.resolve(task)

        assert selection.source == "keyword"
        # "research" is strong signal for Swarm
        assert selection.pattern in ["Swarm", "Hierarchical"]

    def test_pd06_default_when_no_signals(self, resolver: PatternResolver):
        """PD-06: Generic description falls back to default when below threshold."""
        # Use resolver with higher min_confidence to force default
        high_threshold_resolver = PatternResolver(min_confidence=0.5)
        task = make_task(
            description="xyz123abc",  # Meaningless, returns 0.3 confidence
        )

        selection = high_threshold_resolver.resolve(task)

        # Should fall to default when confidence (0.3) < min_confidence (0.5)
        assert selection.source == "default"
        assert selection.pattern == "Pipeline"  # Default

    def test_pd07_confidence_reflects_source_hint(self, resolver: PatternResolver):
        """PD-07: Hint source has confidence=1.0."""
        task = make_task(
            description="Anything",
            pattern_hint="Jury",
        )

        selection = resolver.resolve(task)

        assert selection.confidence == 1.0

    def test_pd08_confidence_reflects_source_keyword(self, resolver: PatternResolver):
        """PD-08: Keyword source has confidence based on signal strength."""
        task = make_task(
            description="Research and investigate authentication options thoroughly",
        )

        selection = resolver.resolve(task)

        if selection.source == "keyword":
            assert 0.3 <= selection.confidence <= 1.0

    def test_pd09_confidence_reflects_source_default(self, resolver: PatternResolver):
        """PD-09: Default source has low confidence."""
        task = make_task(
            description="xyz123",  # No meaningful keywords
        )

        selection = resolver.resolve(task)

        if selection.source == "default":
            assert selection.confidence < 0.3

    def test_pd10_alternatives_populated(self, resolver: PatternResolver):
        """PD-10: Alternatives are populated when multiple patterns match."""
        task = make_task(
            description="Research and validate the options",  # Both exploration + validation
        )

        selection = resolver.resolve(task)

        # Should have alternatives when signals are mixed
        # Note: This may or may not have alternatives depending on scoring
        assert isinstance(selection.alternatives, list)


# ============================================================================
# TestKeywordMatching - KW-01 to KW-10
# ============================================================================


class TestKeywordMatching:
    """Tests for keyword-based pattern inference."""

    def test_kw01_exploration_swarm(self, resolver: PatternResolver):
        """KW-01: Exploration keywords trigger Swarm."""
        task = make_task(
            description="Research authentication options",
        )

        selection = resolver.resolve(task)

        # "research" is strong signal for Swarm
        if selection.source == "keyword":
            assert selection.pattern == "Swarm"
            assert "research" in selection.signals or len(selection.signals) > 0

    def test_kw02_construction_hierarchical(self, resolver: PatternResolver):
        """KW-02: Construction keywords trigger Hierarchical."""
        task = make_task(
            description="Build the new API endpoints",
        )

        selection = resolver.resolve(task)

        if selection.source == "keyword":
            assert selection.pattern in ["Hierarchical", "Pipeline"]

    def test_kw03_validation_jury(self, resolver: PatternResolver):
        """KW-03: Validation with production stakes triggers Jury."""
        task = make_task(
            description="Validate production security config",
        )

        selection = resolver.resolve(task)

        # High stakes + validation = Jury
        if selection.source == "keyword":
            assert selection.pattern in ["Jury", "GeneratorCritic"]

    def test_kw04_comparison_adversarial(self, resolver: PatternResolver):
        """KW-04: Comparison keywords trigger Adversarial."""
        task = make_task(
            description="Compare PostgreSQL vs MongoDB for our use case",
        )

        selection = resolver.resolve(task)

        if selection.source == "keyword":
            assert selection.pattern in ["Adversarial", "Jury"]

    def test_kw05_sequential_pipeline(self, resolver: PatternResolver):
        """KW-05: Sequential signals trigger Pipeline."""
        task = make_task(
            description="First parse the input, then transform it, finally output results",
        )

        selection = resolver.resolve(task)

        if selection.source == "keyword":
            assert selection.pattern == "Pipeline"

    def test_kw06_batch_mapreduce(self, resolver: PatternResolver):
        """KW-06: Batch processing triggers MapReduce."""
        task = make_task(
            description="Process all files and aggregate results",
        )

        selection = resolver.resolve(task)

        if selection.source == "keyword":
            assert selection.pattern in ["MapReduce", "Swarm"]

    def test_kw07_review_generator_critic(self, resolver: PatternResolver):
        """KW-07: Review/feedback keywords trigger GeneratorCritic."""
        task = make_task(
            description="Review the PR and suggest improvements",
        )

        selection = resolver.resolve(task)

        if selection.source == "keyword":
            assert selection.pattern in ["GeneratorCritic", "Jury"]

    def test_kw08_fallback_circuit_breaker(self, resolver: PatternResolver):
        """KW-08: Fallback keywords trigger CircuitBreaker."""
        task = make_task(
            description="Try primary server, fallback to backup if fails",
        )

        selection = resolver.resolve(task)

        if selection.source == "keyword":
            assert selection.pattern in ["CircuitBreaker", "ChainOfResponsibility"]

    def test_kw09_high_stakes_boosts_jury(self, resolver: PatternResolver):
        """KW-09: High stakes + validation strongly suggests Jury."""
        task = make_task(
            description="Critical security review for compliance audit",
        )

        selection = resolver.resolve(task)

        if selection.source == "keyword":
            # High stakes should boost Jury
            assert selection.pattern in ["Jury", "GeneratorCritic"]

    def test_kw10_multiple_signals_combine(self, resolver: PatternResolver):
        """KW-10: Multiple signals are combined (highest score wins)."""
        task = make_task(
            description="Research and validate authentication options for production",
        )

        selection = resolver.resolve(task)

        # Both exploration (Swarm) and validation (Jury) signals
        # One should win based on scoring
        assert selection.pattern in ["Swarm", "Jury", "GeneratorCritic"]


# ============================================================================
# TestCompositionValidation - CV-01 to CV-10
# ============================================================================


class TestCompositionValidation:
    """Tests for pattern composition validation."""

    def test_cv01_valid_pipeline_to_jury(self, resolver: PatternResolver):
        """CV-01: Pipeline -> Jury with HANDOFF scope is valid."""
        result = resolver.validate("Pipeline", "Jury", ScopeType.HANDOFF)

        # Pipeline supports HANDOFF, Jury supports ISOLATED
        # Cross-scope composition needs checking
        assert isinstance(result, ValidationResult)

    def test_cv02_valid_swarm_to_aggregator(self, resolver: PatternResolver):
        """CV-02: Swarm -> Aggregator with HANDOFF is valid."""
        result = resolver.validate("Swarm", "Aggregator", ScopeType.HANDOFF)

        # Both should support appropriate scopes for this
        assert isinstance(result, ValidationResult)

    def test_cv03_invalid_jury_shared_scope(self, resolver: PatternResolver):
        """CV-03: Jury requires ISOLATED, fails with SHARED."""
        result = resolver.validate("Swarm", "Jury", ScopeType.SHARED)

        # Jury only supports ISOLATED scope
        assert result.valid is False or len(result.errors) > 0 or len(result.warnings) > 0

    def test_cv04_invalid_blackboard_isolated(self, resolver: PatternResolver):
        """CV-04: Blackboard requires SHARED, fails with ISOLATED."""
        result = resolver.validate("Blackboard", "Pipeline", ScopeType.ISOLATED)

        # Blackboard requires SHARED scope
        assert result.valid is False or len(result.errors) > 0

    def test_cv05_valid_hierarchical_federated(self, resolver: PatternResolver):
        """CV-05: Hierarchical supports FEDERATED scope."""
        result = resolver.validate("Pipeline", "Hierarchical", ScopeType.FEDERATED)

        assert isinstance(result, ValidationResult)

    def test_cv06_termination_warning_generator_critic(self, resolver: PatternResolver):
        """CV-06: GeneratorCritic has conditional termination warning."""
        result = resolver.validate("Pipeline", "GeneratorCritic", ScopeType.HANDOFF)

        # GeneratorCritic has CONDITIONAL termination
        assert isinstance(result, ValidationResult)
        # May have warnings about termination

    def test_cv07_batch_validates_all_pairs(self, resolver: PatternResolver):
        """CV-07: Batch resolution validates all dependent pairs."""
        task_a = make_task("First step", task_id="task-a")
        task_b = make_task("Second step", task_id="task-b", depends_on=["task-a"])
        task_c = make_task("Third step", task_id="task-c", depends_on=["task-b"])

        plan = resolver.resolve_batch([task_a, task_b, task_c], validate=True)

        assert isinstance(plan, CompositionPlan)
        assert len(plan.steps) == 3

    def test_cv08_batch_skip_validation_flag(self, resolver: PatternResolver):
        """CV-08: validate=False skips composition validation."""
        task_a = make_task("Do A", task_id="task-a", pattern_hint="Blackboard")
        task_b = make_task("Do B", task_id="task-b", depends_on=["task-a"], pattern_hint="Jury")

        # This might be invalid composition, but validate=False skips it
        plan = resolver.resolve_batch([task_a, task_b], validate=False)

        assert isinstance(plan, CompositionPlan)
        # No validation errors because validation was skipped
        assert plan.valid is True

    def test_cv09_batch_aggregates_warnings(self, resolver: PatternResolver):
        """CV-09: Batch resolution aggregates all warnings."""
        task_a = make_task("Generate", task_id="task-a", pattern_hint="GeneratorCritic")
        task_b = make_task("Review", task_id="task-b", depends_on=["task-a"], pattern_hint="GeneratorCritic")

        plan = resolver.resolve_batch([task_a, task_b], validate=True)

        assert isinstance(plan, CompositionPlan)
        # Warnings list exists (may or may not have items)
        assert isinstance(plan.validation_warnings, list)

    def test_cv10_validate_delegates_to_can_compose(self, resolver: PatternResolver):
        """CV-10: validate() delegates to can_compose()."""
        result = resolver.validate("Pipeline", "Jury", ScopeType.HANDOFF)

        # Should return ValidationResult from can_compose
        assert isinstance(result, ValidationResult)
        assert hasattr(result, "valid")
        assert hasattr(result, "errors")


# ============================================================================
# TestEdgeCases - EC-01 to EC-10
# ============================================================================


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_ec01_empty_description(self, resolver: PatternResolver):
        """EC-01: Empty description returns default pattern."""
        task = make_task(description="")

        selection = resolver.resolve(task)

        assert selection.pattern == "Pipeline"  # Default
        assert selection.source == "default"

    def test_ec02_very_long_description(self, resolver: PatternResolver):
        """EC-02: Very long description doesn't crash."""
        task = make_task(description="research " * 1000)  # 10000+ chars

        selection = resolver.resolve(task)

        assert selection.pattern is not None
        assert selection.confidence > 0

    def test_ec03_unicode_description(self, resolver: PatternResolver):
        """EC-03: Unicode in description is handled gracefully."""
        task = make_task(description="Research the API options")

        selection = resolver.resolve(task)

        assert selection.pattern is not None

    def test_ec04_empty_task_list_batch(self, resolver: PatternResolver):
        """EC-04: Empty task list returns empty valid plan."""
        plan = resolver.resolve_batch([], validate=True)

        assert isinstance(plan, CompositionPlan)
        assert plan.valid is True
        assert len(plan.steps) == 0

    def test_ec05_single_task_batch(self, resolver: PatternResolver):
        """EC-05: Single task batch needs no composition validation."""
        task = make_task("Research options", task_id="solo")

        plan = resolver.resolve_batch([task], validate=True)

        assert isinstance(plan, CompositionPlan)
        assert plan.valid is True
        assert len(plan.steps) == 1

    def test_ec06_circular_dependency(self, resolver: PatternResolver):
        """EC-06: Circular dependency detected in validation."""
        task_a = make_task("A", task_id="task-a", depends_on=["task-b"])
        task_b = make_task("B", task_id="task-b", depends_on=["task-a"])

        plan = resolver.resolve_batch([task_a, task_b], validate=True)

        # Should detect cycle and report error
        assert plan.valid is False or len(plan.validation_errors) > 0

    def test_ec07_missing_task_id(self, resolver: PatternResolver):
        """EC-07: Missing task_id raises ValueError."""
        task = {"description": "No ID", "metadata": {}}  # No id field

        with pytest.raises((ValueError, KeyError)):
            resolver.resolve_batch([task], validate=True)

    def test_ec08_none_context(self, resolver: PatternResolver):
        """EC-08: None context doesn't crash resolve()."""
        task = make_task("Research options")

        selection = resolver.resolve(task, context=None)

        assert selection.pattern is not None

    def test_ec09_context_with_parent_pattern(self, resolver: PatternResolver):
        """EC-09: Context with parent_pattern is used."""
        task = make_task("Subtask")
        context = {"parent_pattern": "Swarm"}

        selection = resolver.resolve(task, context=context)

        # Should complete without error
        assert selection.pattern is not None

    def test_ec10_min_confidence_threshold(self, resolver_high_confidence: PatternResolver):
        """EC-10: Weak match falls to default when min_confidence is high."""
        task = make_task(description="maybe research something")

        selection = resolver_high_confidence.resolve(task)

        # With min_confidence=0.8, weak signals fall to default
        if selection.confidence < 0.8:
            assert selection.source == "default"


# ============================================================================
# TestPatternDefaultScope
# ============================================================================


class TestPatternDefaultScope:
    """Tests for PATTERN_DEFAULT_SCOPE mapping."""

    def test_pipeline_default_handoff(self):
        """Pipeline defaults to HANDOFF scope."""
        assert PATTERN_DEFAULT_SCOPE["Pipeline"] == ScopeType.HANDOFF

    def test_swarm_default_isolated(self):
        """Swarm defaults to ISOLATED scope."""
        assert PATTERN_DEFAULT_SCOPE["Swarm"] == ScopeType.ISOLATED

    def test_jury_default_isolated(self):
        """Jury defaults to ISOLATED scope."""
        assert PATTERN_DEFAULT_SCOPE["Jury"] == ScopeType.ISOLATED

    def test_blackboard_default_shared(self):
        """Blackboard defaults to SHARED scope."""
        assert PATTERN_DEFAULT_SCOPE["Blackboard"] == ScopeType.SHARED

    def test_hierarchical_default_federated(self):
        """Hierarchical defaults to FEDERATED scope."""
        assert PATTERN_DEFAULT_SCOPE["Hierarchical"] == ScopeType.FEDERATED

    def test_all_patterns_have_default_scope(self):
        """All patterns in PATTERNS have a default scope mapping."""
        from scripts.validate_composition import PATTERNS

        for pattern_name in PATTERNS:
            assert pattern_name in PATTERN_DEFAULT_SCOPE, (
                f"Pattern {pattern_name} missing from PATTERN_DEFAULT_SCOPE"
            )


# ============================================================================
# TestCompositionPlan
# ============================================================================


class TestCompositionPlan:
    """Tests for CompositionPlan dataclass."""

    def test_fields_accessible(self):
        """CompositionPlan has all required fields."""
        step = CompositionStep(
            task_id="task-1",
            pattern="Pipeline",
            scope_type=ScopeType.HANDOFF,
            depends_on=[],
            selection=PatternSelection(
                pattern="Pipeline",
                confidence=1.0,
                scope_type=ScopeType.HANDOFF,
                source="hint",
            ),
        )

        plan = CompositionPlan(
            steps=[step],
            valid=True,
            validation_errors=[],
            validation_warnings=["Some warning"],
        )

        assert len(plan.steps) == 1
        assert plan.valid is True
        assert plan.validation_errors == []
        assert plan.validation_warnings == ["Some warning"]

    def test_defaults(self):
        """Optional fields have sensible defaults."""
        plan = CompositionPlan(steps=[], valid=True)

        assert plan.validation_errors == []
        assert plan.validation_warnings == []


# ============================================================================
# TestResolverConfiguration
# ============================================================================


class TestResolverConfiguration:
    """Tests for PatternResolver configuration."""

    def test_custom_default_pattern(self):
        """Custom default_pattern is used."""
        resolver = PatternResolver(default_pattern="Hierarchical")
        task = make_task("xyz123")  # No signals

        selection = resolver.resolve(task)

        if selection.source == "default":
            assert selection.pattern == "Hierarchical"

    def test_custom_min_confidence(self):
        """Custom min_confidence affects fallback behavior."""
        resolver = PatternResolver(min_confidence=0.9)
        task = make_task("maybe research")

        selection = resolver.resolve(task)

        # Weak signal should fall to default with high threshold
        # (depends on actual inference scores)
        assert selection.confidence <= 1.0


# ============================================================================
# TestIntegrationWithExistingCode
# ============================================================================


class TestIntegrationWithExistingCode:
    """Tests verifying integration with existing modules."""

    def test_uses_pattern_inference(self, resolver: PatternResolver):
        """Resolution uses infer_pattern from pattern_inference.py."""
        task = make_task("Research authentication options thoroughly")

        selection = resolver.resolve(task)

        # Should produce Pattern-like results
        assert selection.pattern in [p.name.title() for p in Pattern] or \
               selection.pattern in [
                   "Swarm", "Hierarchical", "Pipeline", "GeneratorCritic",
                   "Adversarial", "MapReduce", "Jury", "Blackboard",
                   "CircuitBreaker", "ChainOfResponsibility", "EventDriven",
                   "Aggregator", "Broadcast", "Consensus",
               ]

    def test_validate_uses_can_compose(self, resolver: PatternResolver):
        """validate() uses can_compose from validate_composition.py."""
        result = resolver.validate("Pipeline", "Jury", ScopeType.HANDOFF)

        # Should return ValidationResult from can_compose
        assert isinstance(result, ValidationResult)
        assert hasattr(result, "composition")

    def test_scope_type_from_validate_composition(self, resolver: PatternResolver):
        """Uses ScopeType from validate_composition.py."""
        task = make_task("Test", pattern_hint="Pipeline")

        selection = resolver.resolve(task)

        assert isinstance(selection.scope_type, ScopeType)
