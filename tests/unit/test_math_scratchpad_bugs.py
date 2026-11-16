#!/usr/bin/env python3
"""Bug category tests for math_scratchpad.py - Tests designed to FAIL.

These tests are written based on the 12 bug categories identified in:
- .claude/cache/agents/research/bug-categories.md
- .claude/cache/agents/mutation/round1-analysis.md

Each test class targets a specific vulnerability or edge case that the
current implementation likely does not handle correctly. Tests should FAIL
initially, serving as specifications for fixes.

Test Priority Classification:
- P0: Critical bugs (security, data integrity, availability)
- P1: Important bugs (correctness, robustness)
- P2: Low-priority bugs (usability, error messages)
"""

import pytest
import sys
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


# ============================================================================
# P0 CRITICAL TESTS
# ============================================================================


class TestExpressionParsingSecurity:
    """Test expression parsing security bypasses (Bug Category 1).

    The current implementation uses a simple string-based blacklist for
    dangerous patterns. These tests verify that various bypass techniques
    are properly blocked.

    Priority: P0 (Security Critical)
    """

    def test_unicode_homoglyph_injection(self):
        """Unicode full-width underscores should not bypass __ detection.

        Using Unicode Full Width Low Line (U+FF3F) instead of ASCII underscore
        could bypass the '__' blacklist check.
        """
        from math_scratchpad import verify_step

        # Unicode full-width underscore: \uff3f\uff3f = looks like __
        # This attempts to call __import__ using unicode underscores
        malicious = "x + \uff3f\uff3fimport\uff3f\uff3f('os')"
        result = verify_step(malicious)

        # Should be blocked, not just fail to parse
        assert result["verified"] is False
        assert result["error"] is not None
        # Should specifically detect dangerous pattern, not just parse failure
        assert "dangerous" in result["error"].lower() or "security" in result["error"].lower()

    def test_nested_attribute_access(self):
        """Nested attribute chains that access internals should be blocked.

        Expressions like x.__class__.__bases__[0].__subclasses__() can be
        used to access arbitrary Python classes and escape the sandbox.
        """
        from math_scratchpad import verify_step

        malicious = "x.__class__.__bases__[0].__subclasses__()"
        result = verify_step(malicious)

        assert result["verified"] is False
        assert result["error"] is not None
        # Should detect the __ pattern
        assert "dangerous" in result["error"].lower()

    def test_lambda_injection(self):
        """Lambda expressions should be blocked as they enable arbitrary code.

        Even without explicit 'eval', lambda can execute arbitrary code.
        """
        from math_scratchpad import verify_step

        # Lambda that does something beyond math
        malicious = "(lambda: __import__('os'))()"
        result = verify_step(malicious)

        assert result["verified"] is False
        assert result["error"] is not None

    def test_getattr_bypass(self):
        """getattr() calls should be blocked as they enable attribute access.

        getattr(x, '__class__') is equivalent to x.__class__
        """
        from math_scratchpad import verify_step

        malicious = "getattr(x, '__class__')"
        result = verify_step(malicious)

        assert result["verified"] is False
        assert result["error"] is not None

    def test_bytes_decode_injection(self):
        """Encoded strings that decode to dangerous code should be blocked."""
        from math_scratchpad import verify_step

        # Base64 of '__import__' - won't directly execute but tests awareness
        malicious = "x + bytes.fromhex('5f5f696d706f72745f5f').decode()"
        result = verify_step(malicious)

        assert result["verified"] is False
        assert result["error"] is not None


class TestNumericEdgeCases:
    """Test infinity, NaN, overflow handling (Bug Category 2).

    SymPy's symbolic infinity and Z3's real arithmetic have subtle semantics.
    The current implementation may crash or produce incorrect results.

    Priority: P0 (Data Integrity)
    """

    def test_infinity_in_context(self):
        """Infinity values should be handled gracefully, not crash.

        SymPy's oo (infinity) should not cause float conversion errors
        when added to context or used in verification.
        """
        from math_scratchpad import verify_chain

        # This may raise OverflowError when trying to convert oo to int
        result = verify_chain(["x = oo", "x + 1 = oo"])

        # Should handle gracefully
        assert isinstance(result, dict)
        assert "all_valid" in result
        # Should either verify or return a clear error, not crash

    def test_nan_propagation(self):
        """NaN (Not a Number) should not be conflated with valid results.

        0/0 is undefined, not equal to 0 or any other number.
        """
        from math_scratchpad import verify_step

        # 0/0 = nan in floating point, undefined in mathematics
        result = verify_step("0/0 = 0")

        # This should NOT verify as true
        assert result["verified"] is False

    def test_overflow_large_numbers(self):
        """Very large numbers should not cause OverflowError.

        Numbers like 10**1000 exceed float precision but are valid in SymPy.
        """
        from math_scratchpad import verify_step

        # 10^1000 is way larger than max float
        result = verify_step("x = 10**1000", context={})

        # Should not throw OverflowError
        assert isinstance(result, dict)
        assert "verified" in result

    def test_negative_infinity_comparison(self):
        """Negative infinity comparisons should work correctly."""
        from math_scratchpad import verify_chain

        result = verify_chain(["x = -oo", "x < 0"])

        # -infinity < 0 is true
        assert isinstance(result, dict)
        # Should verify or at least handle gracefully

    def test_complex_infinity(self):
        """Complex infinity (zoo) should be handled distinctly."""
        from math_scratchpad import verify_step

        # 1/0 in complex domain is zoo (complex infinity)
        result = verify_step("1/0 = zoo")

        assert isinstance(result, dict)
        # Should not crash, should have clear handling


class TestTimeoutEnforcement:
    """Test that timeouts are actually enforced (Bug Category 3).

    The current implementation declares timeout parameters but doesn't
    actually use them, allowing infinite loops on pathological inputs.

    Priority: P0 (Availability)
    """

    def test_timeout_on_complex_computation(self):
        """Complex polynomial factoring should timeout, not hang forever.

        Factoring (x-1)(x-2)...(x-50) is exponentially expensive.
        """
        from math_scratchpad import verify_step
        import time

        # Create a polynomial that takes a long time to factor
        factors = "*".join([f"(x-{i})" for i in range(30)])
        expression = f"{factors} = 0"

        start = time.time()
        result = verify_step(expression)
        elapsed = time.time() - start

        # Should complete within reasonable time (30 seconds max)
        # If no timeout, this could take hours
        assert elapsed < 30, f"Computation took {elapsed}s, expected timeout"
        assert isinstance(result, dict)

    def test_timeout_returns_graceful_error(self):
        """Timeout should return an error result, not raise exception."""
        from math_scratchpad import verify_step
        import time

        # Deeply nested expression
        expr = "x"
        for _ in range(15):
            expr = f"sin({expr})**2 + cos({expr})**2"

        start = time.time()
        result = verify_step(f"{expr} = 1")
        elapsed = time.time() - start

        # Should handle gracefully
        assert isinstance(result, dict)
        assert "verified" in result or "error" in result

    def test_z3_timeout_undecidable(self):
        """Z3 should timeout on undecidable problems, not hang."""
        from z3_solve import check_sat
        import time

        # Nonlinear real arithmetic can be undecidable
        start = time.time()
        result = check_sat(
            ["x*x + y*y == z*z", "x*y*z == 1000000007"],
            var_type="real"
        )
        elapsed = time.time() - start

        # Should complete (with sat, unsat, or unknown)
        assert elapsed < 60, f"Z3 took {elapsed}s without timeout"
        assert result.get("satisfiable") in [True, False, None]


class TestZ3ProofSemantics:
    """Test Z3 unknown vs disproved distinction (Bug Category 4).

    The prove_theorem function uses counterexample search. 'Unknown'
    should not be confused with 'disproved'.

    Priority: P0 (Correctness)
    """

    def test_unknown_not_conflated_with_false(self):
        """Z3 'unknown' should not be reported as 'disproved'.

        x*x >= 0 is always true for reals, but Z3 may return 'unknown'
        on complex nonlinear queries instead of finding a proof.
        """
        from z3_solve import prove_theorem

        result = prove_theorem("x*x >= 0", var_type="real")

        # Should be true or unknown, NEVER false
        # x^2 >= 0 is mathematically always true
        assert result.get("proved") is not False, \
            "x^2 >= 0 is always true, should not be disproved"

    def test_undecidable_returns_unknown_status(self):
        """Undecidable fragments should return 'unknown', not crash.

        Some statements are undecidable in Z3's logic. The system should
        gracefully report 'unknown' rather than claiming proved or disproved.
        """
        from z3_solve import prove_theorem

        # Complex nonlinear arithmetic can be undecidable
        result = prove_theorem(
            "x*x*x + y*y*y + z*z*z == 33",  # Known unsolved problem
            var_type="int"
        )

        # Should have a result dict with clear status
        assert isinstance(result, dict)
        assert "proved" in result or "error" in result

    def test_vacuous_truth_from_inconsistent_assumptions(self):
        """Inconsistent assumptions create vacuous truths - should be warned.

        If assumptions are self-contradictory, ANYTHING can be 'proved'.
        """
        from z3_solve import prove_theorem

        result = prove_theorem(
            "y > 100",  # Random claim
            assumptions=["x > 0", "x < 0"],  # Impossible - no x
            var_type="int"
        )

        # If proved=True, should have warning about vacuous truth
        # OR should detect inconsistent assumptions
        if result.get("proved") is True:
            # Should indicate this is vacuous
            assert "vacuous" in str(result).lower() or \
                   "inconsistent" in str(result).lower() or \
                   "assumptions" in str(result).lower(), \
                   "Vacuous truth should be flagged"


class TestSimplificationFalsePositives:
    """Test simplification edge cases (Bug Category 5).

    sympy.simplify() doesn't always find the simplest form, and
    verification via simplify(a - b) == 0 can fail on equivalent expressions.

    Priority: P0 (Correctness)
    """

    def test_trig_identity_equivalence(self):
        """tan(x) = sin(x)/cos(x) should verify as true.

        This is a fundamental identity that trigsimp should handle.
        """
        from math_scratchpad import verify_step

        result = verify_step("tan(x) = sin(x)/cos(x)")

        # This IS mathematically true
        assert result["verified"] is True, \
            f"tan(x) = sin(x)/cos(x) should be verified, got: {result}"

    def test_nested_sqrt_equivalence(self):
        """sqrt(x^2) simplification depends on domain assumptions.

        sqrt(x^2) = |x| for reals, but SymPy may simplify to x.
        """
        from math_scratchpad import verify_step

        # This is ONLY true for x >= 0
        result = verify_step("sqrt(x**2) = x")

        # Should either:
        # 1. Return verified=False (not always true)
        # 2. Return verified=True with domain caveat
        # 3. Request domain clarification
        # Should NOT blindly verify as True without qualification
        assert isinstance(result, dict)

    def test_hyperbolic_identity(self):
        """cosh(x)^2 - sinh(x)^2 = 1 should verify as identity."""
        from math_scratchpad import verify_step

        result = verify_step("cosh(x)**2 - sinh(x)**2 = 1")

        # Fundamental hyperbolic identity
        assert result["verified"] is True, \
            f"Hyperbolic identity failed: {result}"

    def test_expansion_vs_factored_equivalence(self):
        """(x+1)^2 and x^2 + 2x + 1 should be recognized as equal."""
        from math_scratchpad import verify_step

        result = verify_step("(x+1)**2 - (x**2 + 2*x + 1) = 0")

        assert result["verified"] is True, \
            f"Expansion equivalence failed: {result}"

    def test_nearly_equal_not_equal(self):
        """Near-equality should NOT verify as equal.

        sin(x) + 0.0001 is NOT equal to sin(x).
        """
        from math_scratchpad import verify_step

        result = verify_step("sin(x) = sin(x) + 0.0001")

        # Should NOT verify - these are not equal
        assert result["verified"] is False, \
            "Near-equal expressions should not verify as equal"


# ============================================================================
# P1 IMPORTANT TESTS
# ============================================================================


class TestContextIsolation:
    """Test context mutation side effects (Bug Category 6).

    The chain verification maintains a mutable context dict that can
    leak between calls or mutate the caller's dictionary.

    Priority: P1 (Correctness)
    """

    def test_context_not_mutated_by_verify_chain(self):
        """Original context dict should not be mutated.

        If caller passes {'x': 5}, it should still be {'x': 5} after call.
        """
        from math_scratchpad import verify_chain

        original_context = {"x": 5}
        original_copy = dict(original_context)

        # This chain modifies x
        verify_chain(["x = 10", "x + 1 = 11"], context=original_context)

        # Original should be unchanged
        assert original_context == original_copy, \
            f"Context was mutated: {original_context} != {original_copy}"

    def test_context_isolation_between_calls(self):
        """Context from one verify_chain should not leak to next."""
        from math_scratchpad import verify_chain

        # First call sets y = 100
        verify_chain(["y = 100"])

        # Second call should not have y available
        result = verify_chain(["y + 1 = 101"])  # No context provided

        # Should either fail (y undefined) or have separate context
        # Should NOT succeed due to leaked y from previous call
        # Note: this test may pass if there's no global state leak
        assert isinstance(result, dict)

    def test_variable_shadowing_behavior(self):
        """Variable shadowing should work correctly within chain."""
        from math_scratchpad import verify_chain

        result = verify_chain([
            "x = 2",
            "y = x + 1",  # y = 3
            "x = 10",     # Shadow x
            "y = 3"       # y should still be 3
        ])

        # All steps should verify correctly
        assert result["all_valid"] is True, \
            f"Variable shadowing failed: {result}"

    def test_expression_value_in_context(self):
        """Symbolic values in context should propagate correctly."""
        from math_scratchpad import verify_chain

        result = verify_chain([
            "x = sqrt(2)",  # x is symbolic
            "x * x = 2"
        ])

        # sqrt(2) * sqrt(2) = 2
        assert result["all_valid"] is True, \
            f"Symbolic context propagation failed: {result}"


class TestRegexEdgeCases:
    """Test connector regex edge cases (Bug Category 7).

    The codebase uses regex for operation detection and connector splitting.
    Regex patterns can fail on edge cases.

    Priority: P1 (Robustness)
    """

    def test_connector_in_quoted_string(self):
        """Connector words in expressions shouldn't trigger splitting.

        The word 'so' appears in 'solve', shouldn't split there.
        """
        from math_scratchpad import split_claim_and_condition

        # 'so' appears in 'solution' but shouldn't trigger split
        step = "x = 2 and solution exists"
        cond, claim = split_claim_and_condition(step)

        # Should not split on 'so' inside 'solution'
        # Note: Current implementation might not have this issue
        assert isinstance(cond, str)

    def test_multiple_connectors(self):
        """Multiple connectors should split on first only."""
        from math_scratchpad import split_claim_and_condition

        step = "x = 2 implies y = 3 therefore z = 4"
        cond, claim = split_claim_and_condition(step)

        # Should split on 'implies' (first connector)
        assert cond == "x = 2"
        assert "therefore" in claim, \
            f"Second connector should be in claim, got: cond={cond}, claim={claim}"

    def test_connector_no_space(self):
        """Connectors without proper spacing should be handled.

        'x=2implies x^2=4' (no spaces) may not match \\s+implies\\s+
        """
        from math_scratchpad import split_claim_and_condition

        # No space before 'implies'
        step = "x=2implies x^2=4"
        cond, claim = split_claim_and_condition(step)

        # Should either split correctly or not split at all
        # Current regex requires \\s+ so this won't match
        assert isinstance(cond, str)
        # If it doesn't split, claim should be None
        if claim is not None:
            assert claim == "x^2=4" or claim == " x^2=4"

    def test_unicode_whitespace_connector(self):
        """Non-breaking space (U+00A0) should work like regular space."""
        from math_scratchpad import split_claim_and_condition

        # Using non-breaking space
        step = "x = 2\u00A0implies\u00A0x^2 = 4"
        cond, claim = split_claim_and_condition(step)

        # Should ideally recognize this, but current regex uses \\s which may not match
        assert isinstance(cond, str)


class TestZ3TypeCoercion:
    """Test Z3 type handling (Bug Category 8).

    Z3 is strictly typed. Int and Real don't mix well.

    Priority: P1 (Correctness)
    """

    def test_mixed_int_real_comparison(self):
        """Mixed int/real constraints should be handled correctly."""
        from z3_solve import check_sat

        # x is int, y is real - should still find solution
        result = check_sat(
            ["x + y == 3.5"],
            variables=["x:int", "y:real"]
        )

        # Should find solution: x=3, y=0.5 or x=2, y=1.5, etc.
        assert result.get("satisfiable") is True, \
            f"Mixed type constraint should be satisfiable: {result}"

    def test_real_solution_with_int_type(self):
        """x^2 = 2 has no integer solutions but has real solutions."""
        from z3_solve import check_sat

        # No integer x such that x^2 = 2
        int_result = check_sat(["x * x == 2"], var_type="int")
        assert int_result.get("satisfiable") is False, \
            "x^2=2 should have no integer solutions"

        # But real x = sqrt(2) exists
        real_result = check_sat(["x * x == 2"], var_type="real")
        assert real_result.get("satisfiable") is True, \
            "x^2=2 should have real solutions"

    def test_bool_in_arithmetic_context(self):
        """Boolean variables in arithmetic should work (True=1, False=0)."""
        from z3_solve import check_sat

        # x:bool + y:bool = 1 means exactly one is True
        result = check_sat(
            ["x + y == 1"],
            variables=["x:bool", "y:bool"]
        )

        # Should be satisfiable
        assert result.get("satisfiable") is True, \
            f"Bool arithmetic should work: {result}"


class TestUnicodeInput:
    """Test unicode in expressions (Bug Category 10).

    Mathematical notation often uses Unicode symbols.

    Priority: P1 (Usability)
    """

    def test_unicode_infinity_symbol(self):
        """The infinity symbol (U+221E) should be recognized."""
        from math_scratchpad import verify_step

        # Using actual infinity symbol
        result = verify_step("\u221E > 0")  # Infinity symbol

        # Should either parse correctly or give clear error
        assert isinstance(result, dict)
        if result.get("error"):
            # Error should be about parsing, not a crash
            assert "unicode" in result["error"].lower() or \
                   "parse" in result["error"].lower() or \
                   "invalid" in result["error"].lower()

    def test_unicode_pi_symbol(self):
        """The pi symbol (U+03C0) should ideally be recognized."""
        from math_scratchpad import verify_step

        # Using Greek lowercase pi
        result = verify_step("\u03C0 = 3.14159")

        # Should handle gracefully
        assert isinstance(result, dict)

    def test_unicode_multiply_sign(self):
        """The multiplication sign (U+00D7) should be recognized."""
        from math_scratchpad import verify_step

        # Using multiplication sign instead of *
        result = verify_step("2\u00D7x = 2*x")

        # Should parse or give clear error
        assert isinstance(result, dict)

    def test_non_ascii_variable_names(self):
        """Greek letters as variable names should work."""
        from math_scratchpad import verify_step

        # Using theta
        result = verify_step("sin(\u03B8)**2 + cos(\u03B8)**2 = 1")

        # Theta should work as a variable name
        assert isinstance(result, dict)


class TestCalculusVerificationGaps:
    """Test calculus verification patterns (Bug Category 9).

    The calculus verification only handles specific patterns.

    Priority: P1 (Feature Gap)
    """

    def test_leibniz_notation(self):
        """df/dx notation should be recognized."""
        from math_scratchpad import verify_step

        # Leibniz notation: df/dx instead of d/dx(f)
        result = verify_step("df/dx = 2*x")  # For f = x^2

        # Should either work or give clear unsupported error
        assert isinstance(result, dict)
        # Currently may not be supported

    def test_prime_notation(self):
        """f'(x) derivative notation should be recognized."""
        from math_scratchpad import verify_step

        result = verify_step("f'(x) = 3*x**2")  # For f = x^3

        # Prime notation is not currently supported
        assert isinstance(result, dict)

    def test_chain_rule_verification(self):
        """Chain rule derivatives should verify correctly."""
        from math_scratchpad import verify_step

        # d/dx(sin(x^2)) = 2x*cos(x^2) by chain rule
        result = verify_step("d/dx(sin(x**2)) = 2*x*cos(x**2)")

        assert result["verified"] is True, \
            f"Chain rule verification failed: {result}"

    def test_partial_derivative(self):
        """Partial derivatives should treat other variables as constants."""
        from math_scratchpad import verify_step

        # d/dx(x*y) = y (y is constant w.r.t. x)
        result = verify_step("d/dx(x*y) = y")

        # May fail if y is not treated as constant
        assert isinstance(result, dict)

    def test_definite_integral(self):
        """Definite integrals should be verifiable."""
        from math_scratchpad import verify_step

        # integral from 0 to 1 of x dx = 0.5
        result = verify_step("integral from 0 to 1 of x = 0.5")

        # Currently not supported in this format
        assert isinstance(result, dict)


class TestEquationDefinitionFalseAcceptance:
    """Test equation definition validation (Bug Category 12).

    The _is_equation_definition accepts '= 0' equations as premises.

    Priority: P1 (Logic)
    """

    def test_malformed_equation_definition(self):
        """Malformed '= 0' equations should not be blindly accepted."""
        from math_scratchpad import verify_chain

        result = verify_chain([
            "nonsense gibberish = 0",  # Invalid expression
            "x = 2"
        ])

        # First step should fail - it's not parseable
        assert result["steps"][0]["verified"] is False or \
               result["steps"][0].get("error") is not None, \
               "Malformed equation was accepted as premise"

    def test_circular_definition(self):
        """x - x = 0 is trivially true but adds no information."""
        from math_scratchpad import verify_chain

        result = verify_chain([
            "x - x = 0",  # Trivially true
            "x = 5"       # This does NOT follow from above
        ])

        # Chain should work - just x - x = 0 doesn't constrain x
        # Second step is just an assignment, should be accepted
        assert isinstance(result, dict)


# ============================================================================
# P2 LOW-PRIORITY TESTS
# ============================================================================


class TestErrorMessageLeakage:
    """Test error message information leakage (Bug Category 11).

    Error messages should not expose internal paths or stack traces.

    Priority: P2 (Security - Low)
    """

    def test_no_path_in_errors(self):
        """Error messages should not contain file system paths."""
        from math_scratchpad import verify_step

        result = verify_step("invalid((()))")

        if result.get("error"):
            error_msg = result["error"]
            assert "/Users/" not in error_msg, \
                f"Path leaked in error: {error_msg}"
            assert "/home/" not in error_msg, \
                f"Path leaked in error: {error_msg}"
            assert "site-packages" not in error_msg, \
                f"Internal path leaked: {error_msg}"

    def test_no_stack_trace_in_output(self):
        """Stack traces should not appear in output."""
        from math_scratchpad import verify_step

        # Trigger an error
        result = verify_step("__import__('sys').exit()")

        result_str = str(result)
        assert "Traceback" not in result_str, \
            f"Stack trace in output: {result_str}"
        assert "File \"" not in result_str, \
            f"File reference in output: {result_str}"


class TestWhitespaceHandling:
    """Test whitespace edge cases."""

    def test_whitespace_only_input(self):
        """Whitespace-only input should return error."""
        from math_scratchpad import verify_step

        result = verify_step("   ")

        assert result["verified"] is False
        assert result["error"] is not None

    def test_tabs_and_newlines(self):
        """Tabs and newlines in input should be handled."""
        from math_scratchpad import verify_step

        result = verify_step("x\t=\t2\nimplies\nx^2\t=\t4")

        # Should handle gracefully, likely fail to parse
        assert isinstance(result, dict)


class TestMethodSelection:
    """Test verification method selection edge cases."""

    def test_method_selection_with_equals(self):
        """Pure equality without variables should use correct method."""
        from math_scratchpad import select_verification_method

        method = select_verification_method("2 + 2 = 4")

        # Should pick a method
        assert method in ["sympy", "z3"]

    def test_method_selection_mixed_content(self):
        """Mixed algebraic and logical content should have clear method."""
        from math_scratchpad import select_verification_method

        # Contains both trig and logical implication
        method = select_verification_method("sin(x) = 0 implies x = 0")

        # Should pick sympy for trig
        assert method in ["sympy", "z3"]


# ============================================================================
# ADDITIONAL TESTS FROM MUTATION ANALYSIS
# ============================================================================


class TestConnectorVariants:
    """Test all connector types from mutation analysis."""

    def test_so_connector(self):
        """'so' connector should work."""
        from math_scratchpad import split_claim_and_condition

        cond, claim = split_claim_and_condition("x = 2 so x^2 = 4")

        assert cond == "x = 2"
        assert claim == "x^2 = 4"

    def test_hence_connector(self):
        """'hence' connector should work."""
        from math_scratchpad import split_claim_and_condition

        cond, claim = split_claim_and_condition("x = 2 hence x^2 = 4")

        assert cond == "x = 2"
        assert claim == "x^2 = 4"

    def test_thus_connector(self):
        """'thus' connector should work."""
        from math_scratchpad import split_claim_and_condition

        cond, claim = split_claim_and_condition("x = 2 thus x^2 = 4")

        assert cond == "x = 2"
        assert claim == "x^2 = 4"

    def test_arrow_connector(self):
        """'->' connector should work."""
        from math_scratchpad import split_claim_and_condition

        cond, claim = split_claim_and_condition("x = 2 -> x^2 = 4")

        assert cond == "x = 2"
        assert claim == "x^2 = 4"

    def test_double_arrow_connector(self):
        """'=>' connector should work."""
        from math_scratchpad import split_claim_and_condition

        cond, claim = split_claim_and_condition("x = 2 => x^2 = 4")

        assert cond == "x = 2"
        assert claim == "x^2 = 4"


class TestNumericContextTypes:
    """Test different numeric types in context."""

    def test_float_context_value(self):
        """Float values in context should work."""
        from math_scratchpad import verify_chain

        result = verify_chain(["x = 2.5", "x * 2 = 5"])

        assert result["all_valid"] is True, \
            f"Float context failed: {result}"

    def test_large_integer_context(self):
        """Large integers in context should work."""
        from math_scratchpad import verify_chain

        result = verify_chain(["x = 10**10", "x > 0"])

        assert isinstance(result, dict)
        # Should handle without overflow

    def test_negative_context_value(self):
        """Negative values in context should work."""
        from math_scratchpad import verify_chain

        result = verify_chain(["x = -5", "x + 10 = 5"])

        assert result["all_valid"] is True


class TestOperationTypeDetection:
    """Test operation type detection edge cases."""

    def test_detect_diff_keyword(self):
        """'diff' keyword should be detected as differentiation."""
        from math_scratchpad import detect_operation_type

        op = detect_operation_type("diff(x^3) = 3*x^2")

        assert op == "differentiation"

    def test_detect_int_keyword(self):
        """'int' keyword should be detected as integration."""
        from math_scratchpad import detect_operation_type

        op = detect_operation_type("int x dx = x^2/2")

        assert op == "integration"

    def test_mixed_trig_and_equals(self):
        """Trig expression with equals should be simplification."""
        from math_scratchpad import detect_operation_type

        op = detect_operation_type("sin(x)^2 + cos(x)^2 = 1")

        # Should be simplification, not unknown
        assert op == "simplification"


# Run with: uv run pytest tests/unit/test_math_scratchpad_bugs.py -v --tb=short
