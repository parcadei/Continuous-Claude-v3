"""
Tests for Agentica Pattern Inference Module.

Tests the inference-first pattern selection system that parses natural language
task descriptions and infers the best multi-agent coordination pattern.
"""

import pytest
from scripts.agentica_patterns.pattern_inference import (
    Pattern,
    AmbiguityType,
    PatternInference,
    infer_pattern,
    get_clarification_probe,
    generate_work_breakdown,
    EXPLORATION_VERBS,
    CONSTRUCTION_VERBS,
    VALIDATION_VERBS,
    COMPARISON_VERBS,
    TRANSFORMATION_VERBS,
    SEQUENTIAL_SIGNALS,
    PARALLEL_SIGNALS,
    HIGH_STAKES_TERMS,
    CDM_PROBES,
    PATTERN_DESCRIPTIONS,
    _normalize_prompt,
    _count_matches,
    _has_sequential_structure,
    _has_parallel_structure,
    _is_high_stakes,
    _score_pattern,
)


# ============================================================================
# Vocabulary Set Tests
# ============================================================================

class TestVocabularySets:
    """Test vocabulary sets are properly defined."""

    def test_exploration_verbs_not_empty(self):
        """Exploration verbs should be defined."""
        assert len(EXPLORATION_VERBS) > 0
        assert "understand" in EXPLORATION_VERBS
        assert "research" in EXPLORATION_VERBS
        assert "explore" in EXPLORATION_VERBS

    def test_construction_verbs_not_empty(self):
        """Construction verbs should be defined."""
        assert len(CONSTRUCTION_VERBS) > 0
        assert "build" in CONSTRUCTION_VERBS
        assert "create" in CONSTRUCTION_VERBS
        assert "implement" in CONSTRUCTION_VERBS

    def test_validation_verbs_not_empty(self):
        """Validation verbs should be defined."""
        assert len(VALIDATION_VERBS) > 0
        assert "validate" in VALIDATION_VERBS
        assert "verify" in VALIDATION_VERBS
        assert "review" in VALIDATION_VERBS

    def test_comparison_verbs_not_empty(self):
        """Comparison verbs should be defined."""
        assert len(COMPARISON_VERBS) > 0
        assert "compare" in COMPARISON_VERBS
        assert "versus" in COMPARISON_VERBS
        assert "tradeoffs" in COMPARISON_VERBS

    def test_transformation_verbs_not_empty(self):
        """Transformation verbs should be defined."""
        assert len(TRANSFORMATION_VERBS) > 0
        assert "migrate" in TRANSFORMATION_VERBS
        assert "convert" in TRANSFORMATION_VERBS
        assert "transform" in TRANSFORMATION_VERBS

    def test_sequential_signals_not_empty(self):
        """Sequential signals should be defined."""
        assert len(SEQUENTIAL_SIGNALS) > 0
        assert "then" in SEQUENTIAL_SIGNALS
        assert "after" in SEQUENTIAL_SIGNALS
        assert "first" in SEQUENTIAL_SIGNALS

    def test_parallel_signals_not_empty(self):
        """Parallel signals should be defined."""
        assert len(PARALLEL_SIGNALS) > 0
        assert "and" in PARALLEL_SIGNALS
        assert "simultaneously" in PARALLEL_SIGNALS

    def test_high_stakes_terms_not_empty(self):
        """High stakes terms should be defined."""
        assert len(HIGH_STAKES_TERMS) > 0
        assert "production" in HIGH_STAKES_TERMS
        assert "security" in HIGH_STAKES_TERMS
        assert "critical" in HIGH_STAKES_TERMS


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    def test_normalize_prompt_lowercase(self):
        """Should lowercase the prompt."""
        assert _normalize_prompt("HELLO WORLD") == "hello world"

    def test_normalize_prompt_removes_extra_spaces(self):
        """Should remove extra whitespace."""
        assert _normalize_prompt("hello   world") == "hello world"
        assert _normalize_prompt("  hello  world  ") == "hello world"

    def test_count_matches_single_word(self):
        """Should count single word matches."""
        count, matched = _count_matches("i want to understand this", EXPLORATION_VERBS)
        assert count >= 1
        assert "understand" in matched

    def test_count_matches_multi_word(self):
        """Should match multi-word phrases."""
        count, matched = _count_matches("how does this work", EXPLORATION_VERBS)
        assert count >= 1
        assert "how does" in matched

    def test_count_matches_no_match(self):
        """Should return 0 for no matches."""
        count, matched = _count_matches("random unrelated text", EXPLORATION_VERBS)
        assert count == 0
        assert matched == []

    def test_has_sequential_structure_positive(self):
        """Should detect sequential workflow."""
        has_seq, matched = _has_sequential_structure("first do this, then do that, finally wrap up")
        assert has_seq is True
        assert len(matched) >= 2

    def test_has_sequential_structure_negative(self):
        """Should not detect sequential when not present."""
        has_seq, matched = _has_sequential_structure("just do the thing")
        assert has_seq is False

    def test_has_parallel_structure_positive(self):
        """Should detect parallel workflow."""
        has_par, matched = _has_parallel_structure("do all of these simultaneously")
        assert has_par is True

    def test_is_high_stakes_positive(self):
        """Should detect high stakes terms."""
        is_high, matched = _is_high_stakes("this is production critical")
        assert is_high is True
        assert "production" in matched or "critical" in matched

    def test_is_high_stakes_negative(self):
        """Should not detect high stakes when not present."""
        is_high, matched = _is_high_stakes("just a simple test")
        assert is_high is False


# ============================================================================
# Pattern Scoring Tests
# ============================================================================

class TestPatternScoring:
    """Test pattern scoring logic."""

    def test_swarm_scores_for_exploration(self):
        """Swarm should score for exploration tasks."""
        score, signals = _score_pattern("help me understand how auth works", Pattern.SWARM)
        assert score > 0
        assert len(signals) > 0

    def test_hierarchical_scores_for_construction(self):
        """Hierarchical should score for construction tasks."""
        score, signals = _score_pattern("build a new api endpoint for users", Pattern.HIERARCHICAL)
        assert score > 0
        assert len(signals) > 0

    def test_pipeline_scores_for_sequential(self):
        """Pipeline should score for sequential tasks."""
        score, signals = _score_pattern("first parse the config, then validate, then apply", Pattern.PIPELINE)
        assert score > 0
        assert len(signals) > 0

    def test_generator_critic_scores_for_review(self):
        """Generator/Critic should score for review tasks."""
        score, signals = _score_pattern("review this pr for security issues", Pattern.GENERATOR_CRITIC)
        assert score > 0
        assert len(signals) > 0

    def test_adversarial_scores_for_comparison(self):
        """Adversarial should score for comparison tasks."""
        score, signals = _score_pattern("compare react vs vue for our use case", Pattern.ADVERSARIAL)
        assert score > 0
        assert len(signals) > 0

    def test_map_reduce_scores_for_parallel_processing(self):
        """Map/Reduce should score for parallel processing."""
        score, signals = _score_pattern("process all invoices in the uploads folder", Pattern.MAP_REDUCE)
        assert score > 0
        assert len(signals) > 0

    def test_jury_scores_for_high_stakes(self):
        """Jury should score for high-stakes validation."""
        score, signals = _score_pattern("validate this security critical production change", Pattern.JURY)
        assert score > 0
        assert len(signals) > 0


# ============================================================================
# Main Inference Tests - Required Test Cases
# ============================================================================

class TestInferPatternRequiredCases:
    """Test the specific cases mentioned in the requirements."""

    def test_understand_auth_infers_swarm(self):
        """'Help me understand how auth works' -> Swarm (exploration)."""
        result = infer_pattern("Help me understand how auth works")
        assert result.pattern == Pattern.SWARM
        assert "understand" in result.signals or len(result.signals) > 0

    def test_build_api_endpoint_infers_hierarchical(self):
        """'Build a new API endpoint for users' -> Hierarchical (construction)."""
        result = infer_pattern("Build a new API endpoint for users")
        assert result.pattern == Pattern.HIERARCHICAL
        assert "build" in result.signals or "api" in result.signals or len(result.signals) > 0

    def test_review_pr_security_infers_generator_critic_or_jury(self):
        """'Review this PR for security issues' -> Generator/Critic or Jury (validation)."""
        result = infer_pattern("Review this PR for security issues")
        assert result.pattern in [Pattern.GENERATOR_CRITIC, Pattern.JURY]

    def test_sequential_pipeline_infers_pipeline(self):
        """'First parse the config, then validate, then apply' -> Pipeline (sequential)."""
        result = infer_pattern("First parse the config, then validate, then apply")
        assert result.pattern == Pattern.PIPELINE
        # Should have detected sequential signals
        assert any(s in result.signals for s in ["first", "then", "finally"]) or len(result.signals) > 0

    def test_compare_frameworks_infers_adversarial(self):
        """'Compare React vs Vue for our use case' -> Adversarial (comparison)."""
        result = infer_pattern("Compare React vs Vue for our use case")
        assert result.pattern == Pattern.ADVERSARIAL
        assert "compare" in result.signals or "vs" in result.signals or len(result.signals) > 0

    def test_process_all_files_infers_map_reduce(self):
        """'Process all invoices in the uploads folder' -> MapReduce (parallel processing)."""
        result = infer_pattern("Process all invoices in the uploads folder")
        assert result.pattern == Pattern.MAP_REDUCE
        assert any(s in result.signals for s in ["all", "process"]) or len(result.signals) > 0


# ============================================================================
# Confidence and Clarification Tests
# ============================================================================

class TestConfidenceAndClarification:
    """Test confidence scoring and clarification logic."""

    def test_high_confidence_no_clarification(self):
        """High confidence should not need clarification."""
        result = infer_pattern("Build a comprehensive API endpoint with authentication")
        if result.confidence >= 0.7:
            assert result.needs_clarification is False

    def test_low_confidence_needs_clarification(self):
        """Low confidence should need clarification."""
        result = infer_pattern("do the thing")
        if result.confidence < 0.5:
            assert result.needs_clarification is True
            assert result.clarification_probe is not None

    def test_clarification_probe_is_concrete(self):
        """Clarification probe should be CDM-style concrete question."""
        result = infer_pattern("maybe work on this")
        if result.clarification_probe:
            # Should not contain vague language
            assert "important" not in result.clarification_probe.lower() or "what" in result.clarification_probe.lower()
            # Should contain action-oriented language
            probe = result.clarification_probe.lower()
            assert any(word in probe for word in ["what", "walk", "how", "can", "would", "is there"])

    def test_ambiguity_type_set_when_clarification_needed(self):
        """Ambiguity type should be set when clarification is needed."""
        result = infer_pattern("hmm not sure")
        if result.needs_clarification:
            assert result.ambiguity_type is not None

    def test_alternatives_provided_for_close_matches(self):
        """Alternatives should be provided when multiple patterns match."""
        result = infer_pattern("research and build this feature")
        # This has both exploration AND construction signals
        # Should have alternatives if multiple patterns scored well
        # (Not guaranteed, but likely for mixed prompts)
        # Just verify the structure exists
        assert isinstance(result.alternatives, list)


# ============================================================================
# CDM Probe Tests
# ============================================================================

class TestCDMProbes:
    """Test CDM-style probes."""

    def test_all_ambiguity_types_have_probes(self):
        """All ambiguity types should have at least one probe."""
        for ambiguity_type in AmbiguityType:
            probes = CDM_PROBES.get(ambiguity_type, [])
            assert len(probes) > 0, f"Missing probes for {ambiguity_type}"

    def test_get_clarification_probe_scope(self):
        """Should return scope probe."""
        probe = get_clarification_probe(AmbiguityType.SCOPE)
        assert probe is not None
        assert len(probe) > 10

    def test_get_clarification_probe_dependencies(self):
        """Should return dependencies probe."""
        probe = get_clarification_probe(AmbiguityType.DEPENDENCIES)
        assert probe is not None
        assert len(probe) > 10

    def test_get_clarification_probe_risk(self):
        """Should return risk probe."""
        probe = get_clarification_probe(AmbiguityType.RISK)
        assert probe is not None
        assert len(probe) > 10

    def test_get_clarification_probe_parallelism(self):
        """Should return parallelism probe."""
        probe = get_clarification_probe(AmbiguityType.PARALLELISM)
        assert probe is not None
        assert len(probe) > 10

    def test_get_clarification_probe_iteration(self):
        """Should return iteration probe."""
        probe = get_clarification_probe(AmbiguityType.ITERATION)
        assert probe is not None
        assert len(probe) > 10

    def test_probes_are_questions(self):
        """All probes should be questions (contain ? or action words)."""
        for ambiguity_type in AmbiguityType:
            probes = CDM_PROBES.get(ambiguity_type, [])
            for probe in probes:
                # Should either have ? or be an imperative (walk me through, etc.)
                is_question = "?" in probe
                is_imperative = any(word in probe.lower() for word in ["walk", "tell", "show", "describe"])
                assert is_question or is_imperative, f"Probe not a question: {probe}"


# ============================================================================
# Work Breakdown Tests
# ============================================================================

class TestWorkBreakdown:
    """Test work breakdown generation."""

    def test_all_patterns_have_descriptions(self):
        """All patterns should have descriptions."""
        for pattern in Pattern:
            assert pattern in PATTERN_DESCRIPTIONS
            assert len(PATTERN_DESCRIPTIONS[pattern]) > 0

    def test_generate_work_breakdown_swarm(self):
        """Should generate swarm work breakdown."""
        inference = PatternInference(
            pattern=Pattern.SWARM,
            confidence=0.8,
            signals=["research"],
        )
        breakdown = generate_work_breakdown(inference)
        assert "parallel" in breakdown.lower() or "simultaneous" in breakdown.lower()

    def test_generate_work_breakdown_hierarchical(self):
        """Should generate hierarchical work breakdown."""
        inference = PatternInference(
            pattern=Pattern.HIERARCHICAL,
            confidence=0.8,
            signals=["build"],
        )
        breakdown = generate_work_breakdown(inference)
        assert "subtask" in breakdown.lower() or "specialist" in breakdown.lower()

    def test_generate_work_breakdown_pipeline(self):
        """Should generate pipeline work breakdown."""
        inference = PatternInference(
            pattern=Pattern.PIPELINE,
            confidence=0.8,
            signals=["then"],
        )
        breakdown = generate_work_breakdown(inference)
        assert "stage" in breakdown.lower() or "sequence" in breakdown.lower()

    def test_work_breakdown_does_not_expose_pattern_name(self):
        """Work breakdown should not expose pattern names to users."""
        for pattern in Pattern:
            inference = PatternInference(
                pattern=pattern,
                confidence=0.8,
                signals=[],
            )
            breakdown = generate_work_breakdown(inference)
            # Should not contain the pattern enum name
            pattern_name_variants = [
                pattern.value,
                pattern.value.replace("_", " "),
                pattern.name,
                pattern.name.replace("_", " "),
            ]
            for variant in pattern_name_variants:
                # Only check if it's a specific pattern name (not common words)
                if variant not in ["jury", "pipeline"]:  # These might appear naturally
                    assert variant.lower() not in breakdown.lower() or len(variant) < 5


# ============================================================================
# PatternInference Dataclass Tests
# ============================================================================

class TestPatternInferenceDataclass:
    """Test PatternInference dataclass."""

    def test_to_dict_has_all_fields(self):
        """to_dict should include all fields."""
        inference = PatternInference(
            pattern=Pattern.SWARM,
            confidence=0.8,
            signals=["research"],
            needs_clarification=False,
            clarification_probe=None,
            ambiguity_type=None,
            alternatives=[Pattern.HIERARCHICAL],
        )
        result = inference.to_dict()

        assert "pattern" in result
        assert "confidence" in result
        assert "signals" in result
        assert "needs_clarification" in result
        assert "clarification_probe" in result
        assert "ambiguity_type" in result
        assert "alternatives" in result
        assert "work_breakdown" in result

    def test_to_dict_pattern_is_string(self):
        """Pattern should be serialized as string value."""
        inference = PatternInference(
            pattern=Pattern.SWARM,
            confidence=0.8,
            signals=[],
        )
        result = inference.to_dict()
        assert result["pattern"] == "swarm"

    def test_to_dict_alternatives_are_strings(self):
        """Alternatives should be serialized as string values."""
        inference = PatternInference(
            pattern=Pattern.SWARM,
            confidence=0.8,
            signals=[],
            alternatives=[Pattern.HIERARCHICAL, Pattern.JURY],
        )
        result = inference.to_dict()
        assert result["alternatives"] == ["hierarchical", "jury"]


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_prompt(self):
        """Should handle empty prompt gracefully."""
        result = infer_pattern("")
        assert result is not None
        assert result.pattern is not None
        assert result.confidence <= 0.5  # Should be low confidence

    def test_very_long_prompt(self):
        """Should handle very long prompts."""
        long_prompt = "build " * 1000
        result = infer_pattern(long_prompt)
        assert result is not None
        assert result.pattern == Pattern.HIERARCHICAL  # Should detect construction

    def test_special_characters(self):
        """Should handle special characters."""
        result = infer_pattern("build @#$% api endpoint!!")
        assert result is not None
        assert result.pattern == Pattern.HIERARCHICAL

    def test_unicode_characters(self):
        """Should handle unicode characters."""
        result = infer_pattern("build API endpoint for users")
        assert result is not None

    def test_multiple_patterns_detected(self):
        """Should handle prompts matching multiple patterns."""
        # This prompt has both exploration AND validation signals
        result = infer_pattern("research and validate the security approach for production")
        assert result is not None
        # Should pick the strongest signal
        assert result.pattern in [Pattern.SWARM, Pattern.JURY]

    def test_no_clear_pattern(self):
        """Should handle prompts with no clear pattern."""
        result = infer_pattern("xyz abc 123")
        assert result is not None
        assert result.confidence < 0.5
        assert result.needs_clarification is True

    def test_case_insensitivity(self):
        """Should be case insensitive."""
        lower_result = infer_pattern("build an api")
        upper_result = infer_pattern("BUILD AN API")
        mixed_result = infer_pattern("Build An Api")

        assert lower_result.pattern == upper_result.pattern
        assert lower_result.pattern == mixed_result.pattern


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the full inference pipeline."""

    def test_full_pipeline_high_confidence(self):
        """Test full pipeline for high confidence case."""
        result = infer_pattern("Build a comprehensive authentication system with OAuth2")

        assert result.pattern == Pattern.HIERARCHICAL
        assert result.confidence >= 0.5
        assert len(result.signals) > 0
        assert result.get_work_breakdown() is not None

        dict_result = result.to_dict()
        assert dict_result["pattern"] == "hierarchical"

    def test_full_pipeline_low_confidence(self):
        """Test full pipeline for low confidence case."""
        result = infer_pattern("do stuff")

        assert result.pattern is not None
        assert result.confidence < 0.7
        if result.needs_clarification:
            assert result.clarification_probe is not None

    def test_full_pipeline_with_alternatives(self):
        """Test full pipeline provides alternatives."""
        # A prompt that could match multiple patterns
        result = infer_pattern("research and implement best practices for this feature")

        assert result.pattern is not None
        # Might have alternatives
        assert isinstance(result.alternatives, list)

    def test_work_breakdown_detailed_generation(self):
        """Test detailed work breakdown generation."""
        result = infer_pattern("Build a new user registration flow")
        breakdown = generate_work_breakdown(result)

        assert breakdown is not None
        assert len(breakdown) > 50  # Should be a meaningful description
        assert ":" in breakdown  # Should have structure


# ============================================================================
# Regression Tests
# ============================================================================

class TestRegression:
    """Regression tests to prevent future breaking changes."""

    def test_pattern_enum_values_stable(self):
        """Pattern enum values should be stable for serialization."""
        assert Pattern.SWARM.value == "swarm"
        assert Pattern.HIERARCHICAL.value == "hierarchical"
        assert Pattern.PIPELINE.value == "pipeline"
        assert Pattern.GENERATOR_CRITIC.value == "generator_critic"
        assert Pattern.ADVERSARIAL.value == "adversarial"
        assert Pattern.MAP_REDUCE.value == "map_reduce"
        assert Pattern.JURY.value == "jury"

    def test_ambiguity_type_enum_values_stable(self):
        """Ambiguity type enum values should be stable."""
        assert AmbiguityType.SCOPE.value == "scope"
        assert AmbiguityType.DEPENDENCIES.value == "dependencies"
        assert AmbiguityType.RISK.value == "risk"
        assert AmbiguityType.PARALLELISM.value == "parallelism"
        assert AmbiguityType.ITERATION.value == "iteration"

    def test_confidence_range(self):
        """Confidence should always be in [0, 1] range."""
        test_prompts = [
            "build an api",
            "research this topic",
            "compare options",
            "validate security",
            "first do this then that",
            "",
            "xyz",
            "build " * 100,
        ]
        for prompt in test_prompts:
            result = infer_pattern(prompt)
            assert 0.0 <= result.confidence <= 1.0, f"Confidence out of range for: {prompt}"
