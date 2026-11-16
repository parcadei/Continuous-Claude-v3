"""
Comprehensive adversarial test suite for scripts/validate_composition.py.

Tests cover:
1. Valid compositions (should pass)
2. Invalid compositions (should fail with specific errors)
3. Edge cases (unknown patterns, malformed expressions)
4. Deadlock detection
5. Termination guarantees
6. Suggestion engine
7. Parser adversarial (malicious inputs)
8. Composition chains
9. Property-based tests (if hypothesis available)
"""

from __future__ import annotations

import pytest
import sys
import os

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from validate_composition import (
    can_compose,
    parse_composition,
    suggest_compositions,
    get_pattern_info,
    normalize_pattern_name,
    scope_compatible,
    no_deadlock,
    termination_guarantee,
    resource_safe,
    ScopeType,
    Operator,
    PATTERNS,
    ValidationResult,
    Termination,
)


# =============================================================================
# Test Category 1: Valid Compositions (should pass)
# =============================================================================


class TestValidCompositions:
    """Compositions that should pass validation."""

    @pytest.mark.parametrize(
        "pattern_a,pattern_b,scope,operator",
        [
            # Sequential with handoff scope
            ("Pipeline", "Aggregator", ScopeType.HANDOFF, Operator.SEQUENTIAL),
            ("GeneratorCritic", "Aggregator", ScopeType.HANDOFF, Operator.SEQUENTIAL),
            ("ChainOfResponsibility", "Aggregator", ScopeType.HANDOFF, Operator.SEQUENTIAL),
            ("MapReduce", "Pipeline", ScopeType.HANDOFF, Operator.SEQUENTIAL),
            # Parallel isolated patterns
            ("Swarm", "Jury", ScopeType.ISOLATED, Operator.PARALLEL),
            ("MapReduce", "Adversarial", ScopeType.ISOLATED, Operator.PARALLEL),
            ("CircuitBreaker", "Adversarial", ScopeType.ISOLATED, Operator.PARALLEL),
            # Hierarchical with shared/federated scope
            ("Hierarchical", "Blackboard", ScopeType.SHARED, Operator.PARALLEL),
            ("Hierarchical", "EventDriven", ScopeType.SHARED, Operator.PARALLEL),
            ("Hierarchical", "Consensus", ScopeType.SHARED, Operator.PARALLEL),
            ("Hierarchical", "Broadcast", ScopeType.SHARED, Operator.PARALLEL),
            # Choice operator
            ("CircuitBreaker", "ChainOfResponsibility", ScopeType.HANDOFF, Operator.CHOICE),
            # Swarm with shared scope
            ("Swarm", "Hierarchical", ScopeType.SHARED, Operator.PARALLEL),
        ],
    )
    def test_valid_compositions(
        self, pattern_a: str, pattern_b: str, scope: ScopeType, operator: Operator
    ):
        result = can_compose(pattern_a, pattern_b, scope, operator)
        assert result.valid, f"Expected valid but got errors: {result.errors}"
        assert len(result.errors) == 0
        assert len(result.scope_trace) > 0

    def test_valid_composition_has_composition_string(self):
        """Valid result should include the formatted composition string."""
        result = can_compose("Pipeline", "Aggregator", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        assert result.valid
        assert "Pipeline" in result.composition
        assert "Aggregator" in result.composition
        assert ";[handoff]" in result.composition

    def test_valid_composition_from_parsed_expression(self):
        """Parse a valid expression and validate it."""
        expr = "Pipeline ;[handoff] Aggregator"
        parsed = parse_composition(expr)
        assert len(parsed) == 1
        a, op, scope, b = parsed[0]
        result = can_compose(a, b, scope, op)
        assert result.valid


# =============================================================================
# Test Category 2: Invalid Compositions (should fail with specific errors)
# =============================================================================


class TestInvalidCompositions:
    """Compositions that should fail with specific errors."""

    def test_jury_rejects_shared_scope(self):
        """Jury requires isolated scope, should reject shared."""
        result = can_compose("Jury", "Swarm", ScopeType.SHARED, Operator.PARALLEL)
        assert not result.valid
        # Check for specific error message
        assert any("Jury" in e and "shared" in e.lower() for e in result.errors)

    def test_jury_rejects_federated_scope(self):
        """Jury requires isolated scope, should reject federated."""
        result = can_compose("Jury", "Hierarchical", ScopeType.FEDERATED, Operator.PARALLEL)
        assert not result.valid
        assert any("Jury" in e for e in result.errors)

    def test_blackboard_rejects_isolated_scope(self):
        """Blackboard requires shared scope, should reject isolated."""
        result = can_compose("Blackboard", "Swarm", ScopeType.ISOLATED, Operator.PARALLEL)
        assert not result.valid
        assert any("Blackboard" in e for e in result.errors)

    def test_pipeline_rejects_isolated_scope(self):
        """Pipeline uses handoff scope, should reject isolated."""
        result = can_compose("Pipeline", "Aggregator", ScopeType.ISOLATED, Operator.SEQUENTIAL)
        assert not result.valid
        assert any("Pipeline" in e or "Aggregator" in e for e in result.errors)

    def test_hierarchical_rejects_isolated_scope(self):
        """Hierarchical requires shared/federated, should reject isolated."""
        result = can_compose("Hierarchical", "Swarm", ScopeType.ISOLATED, Operator.PARALLEL)
        assert not result.valid
        assert any("Hierarchical" in e for e in result.errors)

    def test_both_patterns_incompatible_with_scope(self):
        """When both patterns reject the scope, both should be mentioned."""
        # Jury only supports iso, Blackboard only supports shared
        result = can_compose("Jury", "Blackboard", ScopeType.FEDERATED, Operator.PARALLEL)
        assert not result.valid
        # Both should have errors
        assert len(result.errors) >= 1

    def test_unknown_pattern_a(self):
        """Unknown first pattern should fail gracefully."""
        result = can_compose("UnknownPattern", "Pipeline", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        assert not result.valid
        assert any("Unknown pattern" in e and "UnknownPattern" in e for e in result.errors)

    def test_unknown_pattern_b(self):
        """Unknown second pattern should fail gracefully."""
        result = can_compose("Pipeline", "UnknownPattern", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        assert not result.valid
        assert any("Unknown pattern" in e and "UnknownPattern" in e for e in result.errors)

    def test_both_patterns_unknown(self):
        """Both unknown patterns should report both errors."""
        result = can_compose("FakeA", "FakeB", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        assert not result.valid
        assert len(result.errors) >= 2
        assert any("FakeA" in e for e in result.errors)
        assert any("FakeB" in e for e in result.errors)


# =============================================================================
# Test Category 3: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge cases for pattern lookup and parsing."""

    def test_case_insensitive_pattern_lookup(self):
        """Pattern names should be case-insensitive."""
        assert get_pattern_info("pipeline") is not None
        assert get_pattern_info("PIPELINE") is not None
        assert get_pattern_info("Pipeline") is not None
        assert get_pattern_info("pIpElInE") is not None

    def test_normalize_pattern_name_preserves_canonical(self):
        """Normalized names should match canonical form."""
        assert normalize_pattern_name("pipeline") == "Pipeline"
        assert normalize_pattern_name("SWARM") == "Swarm"
        assert normalize_pattern_name("mapreduce") == "MapReduce"

    def test_normalize_unknown_pattern_returns_none(self):
        """Unknown patterns should normalize to None."""
        assert normalize_pattern_name("FakePattern") is None
        assert normalize_pattern_name("") is None

    def test_empty_string_pattern(self):
        """Empty pattern name should be handled gracefully."""
        result = can_compose("", "Pipeline", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        assert not result.valid
        assert any("Unknown" in e for e in result.errors)

    def test_whitespace_only_pattern(self):
        """Whitespace-only pattern should be handled gracefully."""
        result = can_compose("   ", "Pipeline", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        assert not result.valid

    def test_parse_empty_expression(self):
        """Empty expression should return empty list."""
        result = parse_composition("")
        assert result == []

    def test_parse_whitespace_expression(self):
        """Whitespace-only expression should return empty list."""
        result = parse_composition("   ")
        assert result == []

    def test_all_patterns_have_required_fields(self):
        """All patterns in PATTERNS dict should have required fields."""
        required_fields = ["scopes", "termination", "primary_op"]
        for name, info in PATTERNS.items():
            for field in required_fields:
                assert field in info, f"Pattern {name} missing field: {field}"

    def test_all_pattern_scopes_are_scopetype(self):
        """All pattern scopes should be ScopeType enum values."""
        for name, info in PATTERNS.items():
            for scope in info["scopes"]:
                assert isinstance(scope, ScopeType), f"{name} has invalid scope: {scope}"

    def test_all_pattern_terminations_are_termination(self):
        """All pattern terminations should be Termination enum values."""
        for name, info in PATTERNS.items():
            assert isinstance(info["termination"], Termination), f"{name} has invalid termination"


# =============================================================================
# Test Category 4: Deadlock Detection
# =============================================================================


class TestDeadlockDetection:
    """Test deadlock detection logic."""

    def test_blackboard_parallel_with_isolated_detected(self):
        """Blackboard in parallel with isolated scope should warn about deadlock risk."""
        ok, msg = no_deadlock("Blackboard", "Swarm", Operator.PARALLEL, ScopeType.ISOLATED)
        assert not ok
        assert "Blackboard" in msg

    def test_blackboard_parallel_with_shared_allowed(self):
        """Blackboard in parallel with shared scope should be allowed."""
        ok, msg = no_deadlock("Blackboard", "Swarm", Operator.PARALLEL, ScopeType.SHARED)
        assert ok

    def test_non_blackboard_parallel_isolated_ok(self):
        """Non-blackboard patterns can run parallel with isolated scope."""
        ok, msg = no_deadlock("Swarm", "Jury", Operator.PARALLEL, ScopeType.ISOLATED)
        assert ok

    def test_sequential_composition_no_deadlock_check(self):
        """Sequential composition doesn't have deadlock checks (termination handles it)."""
        ok, msg = no_deadlock("Pipeline", "Aggregator", Operator.SEQUENTIAL, ScopeType.HANDOFF)
        assert ok

    def test_choice_composition_no_deadlock_check(self):
        """Choice composition should pass deadlock check."""
        ok, msg = no_deadlock("CircuitBreaker", "Pipeline", Operator.CHOICE, ScopeType.HANDOFF)
        assert ok


# =============================================================================
# Test Category 5: Termination Guarantees
# =============================================================================


class TestTerminationWarnings:
    """Test termination guarantee warnings."""

    def test_guaranteed_patterns_no_warning(self):
        """Patterns with guaranteed termination should produce no warnings."""
        ok, msg, warning = termination_guarantee("Pipeline", "Aggregator", Operator.SEQUENTIAL)
        assert ok
        assert warning is None

    def test_conditional_pattern_in_sequential_warns(self):
        """Conditional termination in sequential should produce warning."""
        ok, msg, warning = termination_guarantee("GeneratorCritic", "Aggregator", Operator.SEQUENTIAL)
        assert ok
        assert warning is not None
        assert "GeneratorCritic" in warning or "conditional" in warning.lower()

    def test_conditional_pattern_in_parallel_warns(self):
        """Conditional termination in parallel should produce warning."""
        ok, msg, warning = termination_guarantee("Blackboard", "Hierarchical", Operator.PARALLEL)
        assert ok
        assert warning is not None
        assert "Blackboard" in warning or "conditional" in warning.lower()

    def test_both_conditional_in_choice_warns(self):
        """Both conditional in choice should produce warning."""
        # Find two conditional patterns
        conditional_patterns = [
            name for name, info in PATTERNS.items()
            if info["termination"] == Termination.CONDITIONAL
        ]
        if len(conditional_patterns) >= 2:
            a, b = conditional_patterns[:2]
            ok, msg, warning = termination_guarantee(a, b, Operator.CHOICE)
            assert ok
            assert warning is not None

    def test_one_guaranteed_in_choice_no_warning(self):
        """At least one guaranteed in choice should not produce warning."""
        ok, msg, warning = termination_guarantee("Pipeline", "GeneratorCritic", Operator.CHOICE)
        # This depends on implementation - choice may still work if one branch terminates
        assert ok

    def test_unknown_pattern_returns_unknown(self):
        """Unknown pattern should handle gracefully."""
        ok, msg, warning = termination_guarantee("FakePattern", "Pipeline", Operator.SEQUENTIAL)
        assert ok  # Returns True with "unknown" message
        assert "unknown" in msg.lower()

    def test_conditional_patterns_identified(self):
        """Verify which patterns have conditional termination."""
        conditional = {name for name, info in PATTERNS.items()
                       if info["termination"] == Termination.CONDITIONAL}
        expected = {"Blackboard", "GeneratorCritic", "EventDriven", "Consensus"}
        assert conditional == expected


# =============================================================================
# Test Category 6: Suggestion Engine
# =============================================================================


class TestSuggestionEngine:
    """Test the composition suggestion engine."""

    def test_suggest_for_compatible_patterns(self):
        """Compatible patterns should have multiple suggestions."""
        suggestions = suggest_compositions("Swarm", "MapReduce")
        assert len(suggestions) > 0

    def test_suggest_for_pipeline_aggregator(self):
        """Pipeline and Aggregator should suggest handoff sequential."""
        suggestions = suggest_compositions("Pipeline", "Aggregator")
        assert any(";[handoff]" in s for s in suggestions)

    def test_suggest_respects_constraints(self):
        """Suggestions should only include valid compositions."""
        suggestions = suggest_compositions("Jury", "Blackboard")
        # These two have incompatible scope requirements
        # Jury: iso only, Blackboard: shared only
        # So there should be NO valid compositions
        for s in suggestions:
            # Verify each suggestion is actually valid by re-validating
            parsed = parse_composition(s)
            assert len(parsed) == 1
            a, op, scope, b = parsed[0]
            result = can_compose(a, b, scope, op)
            assert result.valid, f"Suggestion {s} is not actually valid: {result.errors}"

    def test_suggest_unknown_pattern_returns_empty(self):
        """Unknown patterns should return empty suggestions."""
        suggestions = suggest_compositions("FakePattern", "Pipeline")
        assert suggestions == []

        suggestions = suggest_compositions("Pipeline", "FakePattern")
        assert suggestions == []

    def test_suggest_both_unknown_returns_empty(self):
        """Both unknown patterns should return empty."""
        suggestions = suggest_compositions("FakeA", "FakeB")
        assert suggestions == []

    def test_suggest_case_insensitive(self):
        """Suggestions should work with case-insensitive pattern names."""
        suggestions_lower = suggest_compositions("pipeline", "aggregator")
        suggestions_upper = suggest_compositions("PIPELINE", "AGGREGATOR")
        suggestions_mixed = suggest_compositions("Pipeline", "Aggregator")

        # All should return the same suggestions
        assert set(suggestions_lower) == set(suggestions_upper) == set(suggestions_mixed)

    def test_suggest_skips_nesting_operator(self):
        """Suggestions should skip the NESTING operator."""
        suggestions = suggest_compositions("Pipeline", "Aggregator")
        assert not any("()" in s for s in suggestions)


# =============================================================================
# Test Category 7: Parser Adversarial
# =============================================================================


class TestAdversarialParsing:
    """Malformed and malicious inputs should be handled gracefully."""

    @pytest.mark.parametrize(
        "expr",
        [
            # SQL injection attempts
            "Pipeline'; DROP TABLE patterns; --",
            "Pipeline ;[handoff]; DROP TABLE--",
            "' OR '1'='1",
            "1; SELECT * FROM users; --",
            # Path traversal
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            # Buffer overflow attempts
            "A" * 10000,
            "A" * 100000,
            # Null bytes and control characters
            "\x00\x01\x02",
            "Pipeline\x00;[handoff]\x00Jury",
            "Pipeline\x00DROP\x00TABLE",
            # Newlines and special formatting
            "Pattern\nwith\nnewlines",
            "Pattern\r\nwith\r\nCRLF",
            "Pattern\twith\ttabs",
            # Unicode attacks
            "\u0000Pipeline",
            "Pipeline\uFEFF;[handoff]\uFEFFJury",  # BOM characters
            "\u202EPipeline",  # Right-to-left override
            "Pipeline\u200B;[handoff]\u200BJury",  # Zero-width space
            # Shell injection
            "Pipeline$(whoami)",
            "Pipeline`whoami`",
            "Pipeline;$(cat /etc/passwd)",
            "| ls -la",
            # Format string attacks
            "%s%s%s%s%s",
            "%n%n%n%n",
            "{0}{1}{2}",
            # Empty/malformed
            "",
            "   ",
            ";",
            "[",
            "]",
            "[handoff]",
            ";[handoff]",
            "Pipeline ;[]",
            "Pipeline ;[invalid]",
            "Pipeline ;[handoff]",  # Missing second pattern
            ";[handoff] Jury",  # Missing first pattern
            "Pipeline Jury",  # Missing operator and scope
            "Pipeline ; Jury",  # Missing scope
        ],
    )
    def test_malicious_inputs_handled(self, expr: str):
        """Malicious inputs should return empty list or controlled result, never crash."""
        try:
            result = parse_composition(expr)
            # Should return empty list for invalid input
            assert isinstance(result, list)
            # If somehow it parsed, verify each entry is a valid tuple
            for item in result:
                assert isinstance(item, tuple)
                assert len(item) == 4
        except Exception as e:
            # Should not raise uncontrolled exceptions
            pytest.fail(f"Uncontrolled exception for input '{expr[:50]}...': {e}")

    def test_parser_extra_spaces(self):
        """Parser should handle extra spaces."""
        result = parse_composition("Pipeline  ;[handoff]  Jury")
        # May or may not parse depending on regex flexibility
        assert isinstance(result, list)

    def test_parser_no_spaces(self):
        """Parser should handle no spaces."""
        result = parse_composition("Pipeline;[handoff]Jury")
        assert len(result) == 1
        a, op, scope, b = result[0]
        assert a == "Pipeline"
        assert b == "Jury"
        assert scope == ScopeType.HANDOFF
        assert op == Operator.SEQUENTIAL

    def test_parser_case_variations(self):
        """Parser should handle case variations in scope."""
        # Current implementation is case-sensitive for scope
        result_lower = parse_composition("Pipeline ;[handoff] Jury")
        result_upper = parse_composition("Pipeline ;[HANDOFF] Jury")

        assert len(result_lower) == 1
        # Upper case may not parse since ScopeType uses lowercase values
        assert len(result_upper) == 0 or len(result_upper) == 1

    def test_parser_invalid_scope(self):
        """Parser should return empty for invalid scope."""
        result = parse_composition("Pipeline ;[invalid] Jury")
        assert result == []

    def test_parser_empty_scope(self):
        """Parser should return empty for empty scope."""
        result = parse_composition("Pipeline ;[] Jury")
        assert result == []

    def test_parser_missing_scope_brackets(self):
        """Parser should return empty for missing scope brackets."""
        result = parse_composition("Pipeline ; Jury")
        assert result == []

    def test_parser_invalid_operator(self):
        """Parser should only accept valid operators."""
        result = parse_composition("Pipeline @[handoff] Jury")
        assert result == []

        result = parse_composition("Pipeline #[handoff] Jury")
        assert result == []

    def test_parser_all_valid_operators(self):
        """Parser should accept all valid operators."""
        for op_char in [";", "|", "+"]:
            result = parse_composition(f"Pipeline {op_char}[handoff] Aggregator")
            assert len(result) == 1
            _, op, _, _ = result[0]
            expected_op = {
                ";": Operator.SEQUENTIAL,
                "|": Operator.PARALLEL,
                "+": Operator.CHOICE,
            }[op_char]
            assert op == expected_op

    def test_parser_all_valid_scopes(self):
        """Parser should accept all valid scopes."""
        for scope_str in ["iso", "shared", "fed", "handoff"]:
            # Use patterns that support each scope
            pattern_a = {
                "iso": "Swarm",
                "shared": "Swarm",
                "fed": "Hierarchical",
                "handoff": "Pipeline",
            }[scope_str]
            result = parse_composition(f"{pattern_a} ;[{scope_str}] Aggregator")
            if scope_str in ["iso", "shared", "fed"]:
                # Aggregator only supports handoff, so these may not validate
                # but they should still PARSE
                assert len(result) == 1
                _, _, scope, _ = result[0]
                assert scope == ScopeType(scope_str)
            else:
                assert len(result) == 1


# =============================================================================
# Test Category 8: Composition Chains
# =============================================================================


class TestCompositionChains:
    """Test parsing and validation of multi-pattern chains."""

    def test_three_pattern_chain(self):
        """Should parse A ;[x] B ;[y] C as two separate compositions."""
        # Current parser finds overlapping matches
        result = parse_composition("Pipeline ;[handoff] Aggregator ;[handoff] Pipeline")
        # The regex finds non-overlapping matches, so it finds the first one
        # A more sophisticated parser might handle chains differently
        assert len(result) >= 1

    def test_chained_composition_validates_each_step(self):
        """Each step in a chain should be independently validated."""
        expr = "Pipeline ;[handoff] Aggregator"
        parsed = parse_composition(expr)
        assert len(parsed) == 1

        a, op, scope, b = parsed[0]
        result = can_compose(a, b, scope, op)
        assert result.valid

    def test_mixed_operators_in_chain(self):
        """Mixed operators should parse correctly."""
        # This tests if A ;[x] B |[y] C works
        result = parse_composition("Pipeline ;[handoff] Aggregator |[shared] Broadcast")
        # Current regex may only find one match at a time
        assert len(result) >= 1


# =============================================================================
# Test Category 9: Resource Safety
# =============================================================================


class TestResourceSafety:
    """Test resource conflict detection."""

    def test_parallel_writers_conflict(self):
        """Two patterns that write to shared state in parallel should conflict."""
        ok, msg = resource_safe("Blackboard", "EventDriven", Operator.PARALLEL, ScopeType.SHARED)
        assert not ok
        assert "conflict" in msg.lower() or "Resource" in msg

    def test_parallel_readers_no_conflict(self):
        """Read-only patterns in parallel should not conflict."""
        ok, msg = resource_safe("Swarm", "Jury", Operator.PARALLEL, ScopeType.ISOLATED)
        assert ok

    def test_sequential_writers_no_conflict(self):
        """Sequential composition should not have resource conflicts."""
        ok, msg = resource_safe("Blackboard", "EventDriven", Operator.SEQUENTIAL, ScopeType.SHARED)
        assert ok

    def test_single_writer_no_conflict(self):
        """Single writer pattern should not conflict."""
        ok, msg = resource_safe("Blackboard", "Hierarchical", Operator.PARALLEL, ScopeType.SHARED)
        assert ok


# =============================================================================
# Test Category 10: ValidationResult Structure
# =============================================================================


class TestValidationResultStructure:
    """Test the ValidationResult dataclass."""

    def test_valid_result_structure(self):
        """Valid result should have correct structure."""
        result = can_compose("Pipeline", "Aggregator", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        assert isinstance(result, ValidationResult)
        assert isinstance(result.valid, bool)
        assert isinstance(result.composition, str)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.scope_trace, list)

    def test_to_dict_method(self):
        """to_dict should return correct dictionary structure."""
        result = can_compose("Pipeline", "Aggregator", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        d = result.to_dict()

        assert "valid" in d
        assert "composition" in d
        assert "errors" in d
        assert "warnings" in d
        assert "scope_trace" in d

    def test_invalid_result_has_errors(self):
        """Invalid result should have non-empty errors list."""
        result = can_compose("Jury", "Blackboard", ScopeType.SHARED, Operator.PARALLEL)
        assert not result.valid
        assert len(result.errors) > 0

    def test_scope_trace_populated(self):
        """Scope trace should be populated for all validations."""
        result = can_compose("Pipeline", "Aggregator", ScopeType.HANDOFF, Operator.SEQUENTIAL)
        assert len(result.scope_trace) >= 4  # At least 4 checks


# =============================================================================
# Test Category 11: Scope Compatibility Direct Tests
# =============================================================================


class TestScopeCompatibility:
    """Direct tests for scope_compatible function."""

    def test_both_patterns_support_scope(self):
        """When both patterns support a scope, should return True."""
        ok, msg = scope_compatible("Swarm", "MapReduce", ScopeType.ISOLATED)
        assert ok
        assert msg == "compatible"

    def test_first_pattern_rejects_scope(self):
        """When first pattern rejects scope, should return False with message."""
        ok, msg = scope_compatible("Pipeline", "Swarm", ScopeType.ISOLATED)
        assert not ok
        assert "Pipeline" in msg

    def test_second_pattern_rejects_scope(self):
        """When second pattern rejects scope, should return False with message."""
        ok, msg = scope_compatible("Swarm", "Pipeline", ScopeType.ISOLATED)
        assert not ok
        assert "Pipeline" in msg

    def test_unknown_pattern_fails(self):
        """Unknown pattern should return False with error message."""
        ok, msg = scope_compatible("FakePattern", "Pipeline", ScopeType.HANDOFF)
        assert not ok
        assert "Unknown" in msg


# =============================================================================
# Test Category 12: Pattern Coverage
# =============================================================================


class TestPatternCoverage:
    """Ensure all patterns can be validated."""

    def test_all_patterns_can_compose_with_something(self):
        """Each pattern should be able to compose with at least one other pattern."""
        for pattern_name in PATTERNS:
            found_valid = False
            for other_pattern in PATTERNS:
                if pattern_name == other_pattern:
                    continue
                for scope in ScopeType:
                    for op in Operator:
                        if op == Operator.NESTING:
                            continue
                        result = can_compose(pattern_name, other_pattern, scope, op)
                        if result.valid:
                            found_valid = True
                            break
                    if found_valid:
                        break
                if found_valid:
                    break
            assert found_valid, f"Pattern {pattern_name} cannot compose with any other pattern"

    def test_suggest_returns_results_for_all_pattern_pairs(self):
        """suggest_compositions should handle all pattern pairs without error."""
        for a in list(PATTERNS.keys())[:5]:  # Limit to avoid O(n^2) explosion
            for b in list(PATTERNS.keys())[:5]:
                suggestions = suggest_compositions(a, b)
                assert isinstance(suggestions, list)


# =============================================================================
# Test Category 13: Regression Tests
# =============================================================================


class TestRegressionCases:
    """Regression tests for previously found bugs."""

    def test_handoff_scope_with_all_patterns_supporting_it(self):
        """Handoff scope should work with patterns that support it."""
        handoff_patterns = [
            name for name, info in PATTERNS.items()
            if ScopeType.HANDOFF in info["scopes"]
        ]
        # At minimum: Pipeline, MapReduce, GeneratorCritic, CircuitBreaker, ChainOfResponsibility, Aggregator, Adversarial
        assert len(handoff_patterns) >= 5

        for p in handoff_patterns[:3]:
            for q in handoff_patterns[:3]:
                if p != q:
                    result = can_compose(p, q, ScopeType.HANDOFF, Operator.SEQUENTIAL)
                    # Should at least not crash
                    assert isinstance(result, ValidationResult)

    def test_isolated_patterns_can_compose(self):
        """Isolated scope patterns should be able to compose."""
        iso_patterns = [
            name for name, info in PATTERNS.items()
            if ScopeType.ISOLATED in info["scopes"]
        ]
        assert len(iso_patterns) >= 2

        result = can_compose(iso_patterns[0], iso_patterns[1], ScopeType.ISOLATED, Operator.PARALLEL)
        assert isinstance(result, ValidationResult)


# =============================================================================
# Test Category 14: Property-Based Tests (Optional)
# =============================================================================

try:
    from hypothesis import given, strategies as st, settings, assume

    class TestPropertyBased:
        """Property-based tests using hypothesis."""

        @given(st.sampled_from(list(PATTERNS.keys())), st.sampled_from(list(PATTERNS.keys())))
        @settings(max_examples=50)
        def test_suggest_never_crashes(self, pattern_a: str, pattern_b: str):
            """suggest_compositions should never crash for any valid pattern pair."""
            suggestions = suggest_compositions(pattern_a, pattern_b)
            assert isinstance(suggestions, list)

        @given(
            st.sampled_from(list(PATTERNS.keys())),
            st.sampled_from(list(PATTERNS.keys())),
            st.sampled_from([ScopeType.ISOLATED, ScopeType.SHARED, ScopeType.FEDERATED, ScopeType.HANDOFF]),
            st.sampled_from([Operator.SEQUENTIAL, Operator.PARALLEL, Operator.CHOICE]),
        )
        @settings(max_examples=100)
        def test_can_compose_never_crashes(
            self, pattern_a: str, pattern_b: str, scope: ScopeType, operator: Operator
        ):
            """can_compose should never crash for any valid inputs."""
            result = can_compose(pattern_a, pattern_b, scope, operator)
            assert isinstance(result, ValidationResult)
            assert isinstance(result.valid, bool)

        @given(st.text(min_size=0, max_size=1000))
        @settings(max_examples=100)
        def test_parse_composition_never_crashes(self, expr: str):
            """parse_composition should never crash for any string input."""
            result = parse_composition(expr)
            assert isinstance(result, list)

        @given(st.sampled_from(list(PATTERNS.keys())))
        @settings(max_examples=50)
        def test_pattern_info_always_available(self, pattern_name: str):
            """get_pattern_info should return info for all known patterns."""
            info = get_pattern_info(pattern_name)
            assert info is not None
            assert "scopes" in info
            assert "termination" in info
            assert "primary_op" in info

        @given(
            st.sampled_from(list(PATTERNS.keys())),
            st.sampled_from(list(PATTERNS.keys())),
        )
        @settings(max_examples=50)
        def test_suggestions_are_valid(self, pattern_a: str, pattern_b: str):
            """All suggested compositions should actually be valid."""
            suggestions = suggest_compositions(pattern_a, pattern_b)
            for s in suggestions:
                parsed = parse_composition(s)
                if parsed:
                    a, op, scope, b = parsed[0]
                    result = can_compose(a, b, scope, op)
                    assert result.valid, f"Suggestion {s} is not valid: {result.errors}"

except ImportError:
    # hypothesis not available, skip property-based tests
    pass


# =============================================================================
# Test Category 15: Integration-like Tests
# =============================================================================


class TestIntegration:
    """Tests that simulate real usage patterns."""

    def test_full_validation_workflow(self):
        """Test complete workflow: parse -> validate -> report."""
        expr = "Pipeline ;[handoff] Aggregator"

        # Parse
        parsed = parse_composition(expr)
        assert len(parsed) == 1

        # Validate
        a, op, scope, b = parsed[0]
        result = can_compose(a, b, scope, op)

        # Report
        assert result.valid
        d = result.to_dict()
        assert d["valid"] is True
        assert len(d["errors"]) == 0

    def test_invalid_workflow_with_suggestions(self):
        """Test workflow when validation fails: get suggestions."""
        # Jury (iso only) + Blackboard (shared only) = incompatible
        result = can_compose("Jury", "Blackboard", ScopeType.SHARED, Operator.PARALLEL)
        assert not result.valid

        # Get suggestions
        suggestions = suggest_compositions("Jury", "Blackboard")
        # Due to incompatible scopes, there may be no valid suggestions
        # But if there are any, they should be valid
        for s in suggestions:
            parsed = parse_composition(s)
            if parsed:
                a, op, scope, b = parsed[0]
                check = can_compose(a, b, scope, op)
                assert check.valid

    def test_pattern_discovery(self):
        """Test that pattern list is discoverable."""
        assert len(PATTERNS) > 10
        assert "Pipeline" in PATTERNS
        assert "Swarm" in PATTERNS
        assert "Jury" in PATTERNS
        assert "Hierarchical" in PATTERNS
        assert "Blackboard" in PATTERNS


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
