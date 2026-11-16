#!/usr/bin/env python3
"""Tests for math_scratchpad.py - Step-by-step mathematical reasoning verification.

TDD: These tests written FIRST, before implementation.

The math_scratchpad.py script provides cognitive prosthetics for verifying
mathematical reasoning step-by-step. It uses SymPy for algebraic claims
and Z3 for logical proofs.

Test classes:
- TestVerifyStep: Tests for verify_step() function
- TestVerifyChain: Tests for verify_chain() function
- TestExplainStep: Tests for explain_step() function
- TestEdgeCases: Edge cases like empty input, invalid expressions
- TestCLI: CLI argument parsing tests
"""

import pytest
import sys
import json
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


class TestVerifyStep:
    """Tests for verify_step() function - verifying single mathematical claims.

    verify_step() takes a step_text (e.g., "x = 2 implies x^2 = 4") and an
    optional context dict, returning verification results.
    """

    def test_verify_substitution(self):
        """x = 2 implies x^2 = 4 should verify as True.

        This is a basic substitution test: if x = 2, then x^2 = 4 is
        trivially verifiable by substitution.
        """
        from math_scratchpad import verify_step

        result = verify_step("x = 2 implies x^2 = 4")
        assert result["verified"] is True
        assert result["method"] in ["sympy", "z3"]
        assert "substitution" in result["explanation"].lower()
        assert result["error"] is None

    def test_verify_with_context(self):
        """x^2 = 4 with context {x: 2} should verify.

        When context is provided, verify_step uses those values
        to check the claim.
        """
        from math_scratchpad import verify_step

        result = verify_step("x**2 = 4", context={"x": 2})
        assert result["verified"] is True
        assert result["method"] == "sympy"
        assert result["error"] is None

    def test_verify_invalid_step(self):
        """x = 2 implies x^2 = 5 should fail verification.

        This is an incorrect claim - 2^2 = 4, not 5.
        """
        from math_scratchpad import verify_step

        result = verify_step("x = 2 implies x^2 = 5")
        assert result["verified"] is False
        assert result["error"] is not None
        assert "expected" in result["error"].lower() or "invalid" in result["error"].lower()

    def test_verify_trig_identity(self):
        """sin^2(x) + cos^2(x) = 1 should verify as a known identity.

        This is the fundamental trigonometric identity.
        """
        from math_scratchpad import verify_step

        result = verify_step("sin(x)**2 + cos(x)**2 = 1")
        assert result["verified"] is True
        assert result["method"] == "sympy"

    def test_verify_algebraic_identity(self):
        """(a+b)^2 = a^2 + 2ab + b^2 should verify.

        Classic algebraic identity for binomial expansion.
        """
        from math_scratchpad import verify_step

        result = verify_step("(a+b)**2 = a**2 + 2*a*b + b**2")
        assert result["verified"] is True

    def test_verify_with_multiple_vars_context(self):
        """Multi-variable substitution: x + y = 5 with x=2, y=3.

        Context can contain multiple variables.
        """
        from math_scratchpad import verify_step

        result = verify_step("x + y = 5", context={"x": 2, "y": 3})
        assert result["verified"] is True

    def test_verify_implication_with_therefore(self):
        """Test parsing 'therefore' as logical connector.

        verify_step should recognize 'therefore' as equivalent to 'implies'.
        """
        from math_scratchpad import verify_step

        result = verify_step("x = 3 therefore x^2 = 9")
        assert result["verified"] is True

    def test_verify_using_z3(self):
        """Test that Z3 is used for logical proofs like commutativity.

        For universal claims over all values, Z3 is more appropriate.
        """
        from math_scratchpad import verify_step

        result = verify_step("x + y = y + x")
        assert result["verified"] is True
        # This could use Z3 or SymPy (both can verify)


class TestVerifyChain:
    """Tests for verify_chain() function - verifying sequences of reasoning steps.

    verify_chain() takes a list of steps and verifies each one,
    tracking context and detecting the first error.
    """

    def test_chain_all_valid(self):
        """Valid reasoning chain: x^2 - 4 = 0 -> factors -> solutions.

        All steps in this chain are mathematically valid.
        """
        from math_scratchpad import verify_chain

        result = verify_chain([
            "x^2 - 4 = 0",
            "(x-2)(x+2) = 0",
            "x = 2 or x = -2"
        ])
        assert result["all_valid"] is True
        assert result["first_error"] is None
        assert len(result["steps"]) == 3
        assert all(step["verified"] for step in result["steps"])

    def test_chain_with_error(self):
        """Chain with error should identify first invalid step.

        x = 2 -> x^2 = 4 -> x^2 + 1 = 6 (error: should be 5)
        """
        from math_scratchpad import verify_chain

        result = verify_chain([
            "x = 2",
            "x^2 = 4",
            "x^2 + 1 = 6"  # Error: should be 5
        ])
        assert result["all_valid"] is False
        assert result["first_error"] is not None
        assert result["first_error"]["step_index"] == 2
        # Steps 0 and 1 should be valid
        assert result["steps"][0]["verified"] is True
        assert result["steps"][1]["verified"] is True
        assert result["steps"][2]["verified"] is False

    def test_chain_empty(self):
        """Empty chain should return all_valid True.

        An empty chain has no invalid steps, so it's vacuously valid.
        """
        from math_scratchpad import verify_chain

        result = verify_chain([])
        assert result["all_valid"] is True
        assert result["first_error"] is None
        assert result["steps"] == []

    def test_chain_single_step(self):
        """Single-step chain should work.

        Edge case: chain with just one step.
        """
        from math_scratchpad import verify_chain

        result = verify_chain(["sin(x)**2 + cos(x)**2 = 1"])
        assert result["all_valid"] is True
        assert len(result["steps"]) == 1

    def test_chain_context_propagation(self):
        """Context should propagate through chain.

        Variables defined in step N should be available in step N+1.
        """
        from math_scratchpad import verify_chain

        result = verify_chain([
            "x = 3",
            "y = x + 2",  # y = 5
            "x + y = 8"   # 3 + 5 = 8
        ])
        assert result["all_valid"] is True

    def test_chain_error_at_first_step(self):
        """Error at first step should be detected.

        First step is already wrong.
        """
        from math_scratchpad import verify_chain

        result = verify_chain([
            "1 = 2",  # Obviously wrong
            "2 = 2"   # Valid
        ])
        assert result["all_valid"] is False
        assert result["first_error"]["step_index"] == 0

    def test_chain_with_integration(self):
        """Chain involving calculus (integration).

        d/dx(x^3) = 3x^2, integral of 3x^2 = x^3
        """
        from math_scratchpad import verify_chain

        result = verify_chain([
            "d/dx(x^3) = 3*x^2",
            "integral of 3*x^2 = x^3"
        ])
        # These should verify using SymPy's diff/integrate
        assert result["all_valid"] is True


class TestExplainStep:
    """Tests for explain_step() function - explaining what a mathematical step does.

    explain_step() takes a step_text and returns an explanation including
    the operation type, input, output, and detailed explanation.
    """

    def test_explain_derivative(self):
        """Should explain differentiation: d/dx(x^3) = 3x^2.

        The explanation should identify the power rule.
        """
        from math_scratchpad import explain_step

        result = explain_step("d/dx(x^3) = 3*x^2")
        assert result["operation"] == "differentiation"
        assert result["input"] == "x**3" or result["input"] == "x^3"
        assert "3" in result["output"]
        assert "power rule" in result["explanation"].lower()

    def test_explain_factoring(self):
        """Should explain factoring: x^2 - 4 = (x-2)(x+2).

        The explanation should identify difference of squares.
        """
        from math_scratchpad import explain_step

        result = explain_step("x^2 - 4 = (x-2)(x+2)")
        assert result["operation"] == "factoring"
        assert "difference" in result["explanation"].lower() or "factor" in result["explanation"].lower()

    def test_explain_integration(self):
        """Should explain integration: integral of x^2 = x^3/3.

        The explanation should identify the power rule for integration.
        """
        from math_scratchpad import explain_step

        result = explain_step("integral of x^2 = x^3/3")
        assert result["operation"] == "integration"
        assert "x**3" in result["output"] or "x^3" in result["output"]

    def test_explain_simplification(self):
        """Should explain simplification: sin^2(x) + cos^2(x) = 1.

        The explanation should reference the Pythagorean identity.
        """
        from math_scratchpad import explain_step

        result = explain_step("sin(x)^2 + cos(x)^2 = 1")
        assert result["operation"] == "simplification"
        assert "identity" in result["explanation"].lower() or "trig" in result["explanation"].lower()

    def test_explain_substitution(self):
        """Should explain substitution: if x=2, x^2=4.

        The explanation should mention substitution.
        """
        from math_scratchpad import explain_step

        result = explain_step("x = 2 therefore x^2 = 4")
        assert result["operation"] == "substitution"
        assert "substitut" in result["explanation"].lower()


class TestEdgeCases:
    """Tests for edge cases - empty input, invalid expressions, etc."""

    def test_verify_empty_string(self):
        """Empty string should return error.

        Empty input is not a valid mathematical claim.
        """
        from math_scratchpad import verify_step

        result = verify_step("")
        assert result["verified"] is False
        assert result["error"] is not None

    def test_verify_nonsense_input(self):
        """Non-mathematical input should return error.

        Random text is not a valid expression.
        """
        from math_scratchpad import verify_step

        result = verify_step("hello world")
        assert result["verified"] is False
        assert result["error"] is not None

    def test_verify_invalid_expression(self):
        """Syntactically invalid expression should return error.

        x +* y is not valid Python/SymPy syntax.
        """
        from math_scratchpad import verify_step

        result = verify_step("x +* y = z")
        assert result["verified"] is False
        assert result["error"] is not None
        assert "parse" in result["error"].lower() or "syntax" in result["error"].lower()

    def test_verify_unbalanced_parens(self):
        """Unbalanced parentheses should return error.

        sin(x should fail validation.
        """
        from math_scratchpad import verify_step

        result = verify_step("sin(x = 1")
        assert result["verified"] is False
        assert result["error"] is not None

    def test_explain_empty_string(self):
        """explain_step with empty string should handle gracefully."""
        from math_scratchpad import explain_step

        result = explain_step("")
        assert result["operation"] == "unknown" or result.get("error") is not None

    def test_chain_with_none(self):
        """verify_chain with None should raise appropriate error."""
        from math_scratchpad import verify_chain

        with pytest.raises((TypeError, ValueError)):
            verify_chain(None)

    def test_verify_dangerous_input(self):
        """Dangerous input (injection attempt) should be rejected.

        Expressions containing 'import', 'exec', etc. should be rejected.
        """
        from math_scratchpad import verify_step

        result = verify_step("import os; x = 1")
        assert result["verified"] is False
        assert result["error"] is not None
        assert "dangerous" in result["error"].lower() or "invalid" in result["error"].lower()


class TestCLI:
    """Tests for CLI argument parsing."""

    def test_parse_args_verify(self):
        """Parse args for verify command."""
        from math_scratchpad import parse_args

        old_argv = sys.argv
        sys.argv = ["math_scratchpad.py", "verify", "x = 2 implies x^2 = 4"]
        try:
            args = parse_args()
            assert args.command == "verify"
            assert args.step == "x = 2 implies x^2 = 4"
        finally:
            sys.argv = old_argv

    def test_parse_args_verify_with_context(self):
        """Parse args for verify command with --context."""
        from math_scratchpad import parse_args

        context = '{"x": 2}'
        old_argv = sys.argv
        sys.argv = ["math_scratchpad.py", "verify", "x^2 = 4", "--context", context]
        try:
            args = parse_args()
            assert args.command == "verify"
            assert args.step == "x^2 = 4"
            assert json.loads(args.context) == {"x": 2}
        finally:
            sys.argv = old_argv

    def test_parse_args_chain(self):
        """Parse args for chain command with --steps."""
        from math_scratchpad import parse_args

        steps = '["x = 2", "x^2 = 4"]'
        old_argv = sys.argv
        sys.argv = ["math_scratchpad.py", "chain", "--steps", steps]
        try:
            args = parse_args()
            assert args.command == "chain"
            assert json.loads(args.steps) == ["x = 2", "x^2 = 4"]
        finally:
            sys.argv = old_argv

    def test_parse_args_explain(self):
        """Parse args for explain command."""
        from math_scratchpad import parse_args

        old_argv = sys.argv
        sys.argv = ["math_scratchpad.py", "explain", "d/dx(x^3) = 3*x^2"]
        try:
            args = parse_args()
            assert args.command == "explain"
            assert args.step == "d/dx(x^3) = 3*x^2"
        finally:
            sys.argv = old_argv


class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_split_claim_and_condition(self):
        """Test parsing 'X implies Y' into parts.

        Should split on logical connectors like 'implies', 'therefore', 'so'.
        """
        from math_scratchpad import split_claim_and_condition

        cond, claim = split_claim_and_condition("x = 2 implies x^2 = 4")
        assert cond == "x = 2"
        assert claim == "x^2 = 4"

    def test_split_claim_and_condition_therefore(self):
        """Test parsing 'X therefore Y'."""
        from math_scratchpad import split_claim_and_condition

        cond, claim = split_claim_and_condition("x = 2 therefore x^2 = 4")
        assert cond == "x = 2"
        assert claim == "x^2 = 4"

    def test_split_claim_and_condition_no_connector(self):
        """Test when no connector is present."""
        from math_scratchpad import split_claim_and_condition

        result, claim = split_claim_and_condition("x^2 + 1 = 5")
        assert result == "x^2 + 1 = 5"
        assert claim is None

    def test_detect_operation_type(self):
        """Test detecting mathematical operation types."""
        from math_scratchpad import detect_operation_type

        assert detect_operation_type("d/dx(x^3) = 3*x^2") == "differentiation"
        assert detect_operation_type("integral of x^2 = x^3/3") == "integration"
        assert detect_operation_type("(x-2)(x+2) = x^2 - 4") == "factoring"
        assert detect_operation_type("x = 2 implies x^2 = 4") == "substitution"

    def test_select_verification_method(self):
        """Test method selection (SymPy vs Z3).

        Algebraic claims should use SymPy, logical proofs should use Z3.
        """
        from math_scratchpad import select_verification_method

        # Algebraic substitution -> SymPy
        assert select_verification_method("x = 2 implies x^2 = 4") == "sympy"
        # Universal claim -> Z3
        assert select_verification_method("x + y = y + x") == "z3"
        # Trig identity -> SymPy
        assert select_verification_method("sin(x)^2 + cos(x)^2 = 1") == "sympy"
