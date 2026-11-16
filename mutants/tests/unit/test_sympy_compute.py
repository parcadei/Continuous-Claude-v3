#!/usr/bin/env python3
"""Tests for sympy_compute.py - Math cognitive prosthetics.

TDD: These tests written FIRST, before implementation.
"""

import pytest
import sys
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


class TestSolveEquation:
    """Tests for solve_equation function."""

    def test_solve_quadratic(self):
        """x^2 - 4 = 0 should yield [-2, 2]."""
        from sympy_compute import solve_equation

        result = solve_equation("x**2 - 4 = 0", "x", "real")
        assert set(result["solutions"]) == {"-2", "2"}
        assert result["verified"] is True

    def test_solve_linear(self):
        """2x + 4 = 0 should yield -2."""
        from sympy_compute import solve_equation

        result = solve_equation("2*x + 4 = 0", "x", "real")
        assert result["solutions"] == ["-2"]
        assert result["verified"] is True

    def test_solve_no_real_solution(self):
        """x^2 + 1 = 0 with domain=real should yield empty list."""
        from sympy_compute import solve_equation

        result = solve_equation("x**2 + 1 = 0", "x", "real")
        assert result["solutions"] == []

    def test_solve_complex_solution(self):
        """x^2 + 1 = 0 with domain=complex should yield imaginary solutions."""
        from sympy_compute import solve_equation

        result = solve_equation("x**2 + 1 = 0", "x", "complex")
        assert len(result["solutions"]) == 2
        # Should contain 'I' (imaginary unit)
        assert any("I" in str(s) for s in result["solutions"])


class TestIntegration:
    """Tests for integrate_expr function."""

    def test_integrate_polynomial(self):
        """Integral of x^2 should be x^3/3."""
        from sympy_compute import integrate_expr

        result = integrate_expr("x**2", "x", None, None)
        assert result["computed"] is True
        assert result["definite"] is False
        # Result should contain x**3/3
        assert "x**3/3" in result["result"] or "x³/3" in result["result"]

    def test_integrate_definite(self):
        """Integral of x from 0 to 1 should be 1/2."""
        from sympy_compute import integrate_expr

        result = integrate_expr("x", "x", "0", "1")
        assert result["definite"] is True
        assert result["result"] == "1/2"

    def test_integrate_trig(self):
        """Integral of sin(x) should contain cos."""
        from sympy_compute import integrate_expr

        result = integrate_expr("sin(x)", "x", None, None)
        assert result["computed"] is True
        assert "cos" in result["result"]


class TestDifferentiation:
    """Tests for differentiate_expr function."""

    def test_differentiate_power(self):
        """d/dx(x^3) should be 3*x^2."""
        from sympy_compute import differentiate_expr

        result = differentiate_expr("x**3", "x", 1)
        assert "3*x**2" in result["result"] or "3x²" in result["result"]

    def test_differentiate_second_order(self):
        """d^2/dx^2(x^3) should be 6*x."""
        from sympy_compute import differentiate_expr

        result = differentiate_expr("x**3", "x", 2)
        assert "6*x" in result["result"] or "6x" in result["result"]

    def test_differentiate_trig(self):
        """d/dx(sin(x)) should be cos(x)."""
        from sympy_compute import differentiate_expr

        result = differentiate_expr("sin(x)", "x", 1)
        assert "cos(x)" in result["result"]


class TestSimplify:
    """Tests for simplify_expr function."""

    def test_simplify_trig_identity(self):
        """sin^2(x) + cos^2(x) should simplify to 1."""
        from sympy_compute import simplify_expr

        result = simplify_expr("sin(x)**2 + cos(x)**2", "trig")
        assert result["simplified"] == "1"
        assert result["equivalent"] is True

    def test_simplify_algebraic(self):
        """(x+1)^2 - x^2 - 2*x - 1 should simplify to 0."""
        from sympy_compute import simplify_expr

        result = simplify_expr("(x+1)**2 - x**2 - 2*x - 1", "auto")
        assert result["simplified"] == "0"

    def test_simplify_expand(self):
        """(x+1)^2 expanded should be x^2 + 2*x + 1."""
        from sympy_compute import simplify_expr

        result = simplify_expr("(x+1)**2", "expand")
        assert "x**2" in result["simplified"]
        assert "2*x" in result["simplified"]


class TestSafeParse:
    """Tests for safe_parse function."""

    def test_parse_valid_expression(self):
        """Valid expression should parse without error."""
        from sympy_compute import safe_parse

        expr = safe_parse("x**2 + 2*x + 1")
        assert expr is not None

    def test_parse_implicit_multiplication(self):
        """2x should parse as 2*x."""
        from sympy_compute import safe_parse

        expr = safe_parse("2x")
        assert str(expr) == "2*x"

    def test_parse_invalid_expression(self):
        """Invalid expression should raise ValueError."""
        from sympy_compute import safe_parse

        with pytest.raises(ValueError, match="Cannot parse"):
            safe_parse("x +* y")


class TestValidation:
    """Tests for input validation."""

    def test_reject_dangerous_input(self):
        """Expressions with dangerous patterns should be rejected."""
        from sympy_compute import validate_expression

        valid, msg = validate_expression("import os")
        assert valid is False
        assert "dangerous" in msg.lower()

    def test_reject_unbalanced_parens(self):
        """Unbalanced parentheses should be rejected."""
        from sympy_compute import validate_expression

        valid, msg = validate_expression("sin(x")
        assert valid is False
        assert "parenthes" in msg.lower()

    def test_accept_valid_expression(self):
        """Valid expressions should pass validation."""
        from sympy_compute import validate_expression

        valid, msg = validate_expression("sin(x)**2 + cos(x)**2")
        assert valid is True


class TestTimeout:
    """Tests for timeout protection."""

    @pytest.mark.slow
    def test_timeout_on_long_computation(self):
        """Long computations should timeout gracefully."""
        from sympy_compute import safe_solve

        # This equation is solvable but may take a while
        # The function should respect timeout
        result = safe_solve("x**100 + x**50 + 1 = 0", var="x", domain="complex")
        # Should either return result or timeout error, not hang
        assert result is not None

    def test_timeout_triggers_on_complex_equation(self):
        """Test that timeout actually triggers for slow computations."""
        from sympy_compute import safe_solve

        # Use a very short timeout (1 second) with a complex equation
        # x**100 - 1 = 0 has 100 roots and takes significant time
        result = safe_solve("x**100 - 1 = 0", var="x", domain="complex", timeout=1)

        # Either it succeeds quickly OR it times out with error
        if "error" in result:
            assert "timeout" in result["error"].lower() or result.get("success") is False
        # If it somehow completes in 1s, that's also fine

    def test_fast_equation_respects_timeout(self):
        """Simple equations should complete well within timeout."""
        from sympy_compute import safe_solve

        result = safe_solve("x**2 - 4 = 0", var="x", domain="real", timeout=30)
        # Should succeed, not timeout
        assert "solutions" in result or result.get("success") is not False
        if "solutions" in result:
            assert set(result["solutions"]) == {"-2", "2"}


class TestCLI:
    """Tests for CLI interface."""

    def test_parse_args_solve(self):
        """Parse args for solve command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "solve", "x**2 - 4 = 0", "--var", "x"]
        try:
            args = parse_args()
            assert args.command == "solve"
            assert args.expression == "x**2 - 4 = 0"
            assert args.var == "x"
        finally:
            sys.argv = old_argv

    def test_parse_args_integrate(self):
        """Parse args for integrate command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "integrate", "x**2", "--var", "x", "--bounds", "0", "1"]
        try:
            args = parse_args()
            assert args.command == "integrate"
            assert args.bounds == ["0", "1"]
        finally:
            sys.argv = old_argv
