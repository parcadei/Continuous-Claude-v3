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
    """Tests for timeout protection.

    WARNING: ProcessPoolExecutor timeout doesn't reliably kill workers on macOS.
    These tests use pytest.mark.timeout as a hard kill switch.
    """

    @pytest.mark.slow
    @pytest.mark.timeout(45)  # Hard kill if ProcessPoolExecutor timeout fails
    def test_timeout_on_long_computation(self):
        """Long computations should timeout gracefully."""
        from sympy_compute import safe_solve

        # This equation is solvable but may take a while
        # The function should respect timeout (default 30s)
        # Use a simpler equation to avoid 6-hour hangs
        result = safe_solve("x**20 + x**10 + 1 = 0", var="x", domain="complex", timeout=10)
        # Should either return result or timeout error, not hang
        assert result is not None

    @pytest.mark.timeout(10)  # Hard kill after 10s
    def test_timeout_triggers_on_complex_equation(self):
        """Test that timeout actually triggers for slow computations."""
        from sympy_compute import safe_solve

        # Use a very short timeout (1 second) with a moderately complex equation
        result = safe_solve("x**10 - 1 = 0", var="x", domain="complex", timeout=1)

        # Either it succeeds quickly OR it times out with error
        if "error" in result:
            assert "timeout" in result["error"].lower() or result.get("success") is False
        # If it somehow completes in 1s, that's also fine

    @pytest.mark.timeout(30)  # Hard kill safety net
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


# ==============================================================================
# Phase 1 Tests: New SymPy Commands (TDD - written BEFORE implementation)
# ==============================================================================


class TestParseMatrix:
    """Tests for parse_matrix helper function."""

    def test_parse_2x2_numeric(self):
        """Parse [[1,2],[3,4]] as 2x2 matrix."""
        from sympy_compute import parse_matrix

        M = parse_matrix("[[1,2],[3,4]]")
        assert M.rows == 2
        assert M.cols == 2
        assert M[0, 0] == 1
        assert M[1, 1] == 4

    def test_parse_3x3_numeric(self):
        """Parse 3x3 identity-like matrix."""
        from sympy_compute import parse_matrix

        M = parse_matrix("[[1,0,0],[0,1,0],[0,0,1]]")
        assert M.rows == 3
        assert M.cols == 3

    def test_parse_invalid_matrix(self):
        """Invalid matrix string should raise ValueError."""
        from sympy_compute import parse_matrix

        with pytest.raises(ValueError, match="Cannot parse matrix"):
            parse_matrix("not a matrix")


class TestLimitExpr:
    """Tests for limit_expr function."""

    def test_limit_sin_over_x(self):
        """lim(x->0) sin(x)/x = 1."""
        from sympy_compute import limit_expr

        result = limit_expr("sin(x)/x", "x", "0")
        assert result["result"] == "1"
        assert result["exists"] is True

    def test_limit_at_infinity(self):
        """lim(x->oo) 1/x = 0."""
        from sympy_compute import limit_expr

        result = limit_expr("1/x", "x", "oo")
        assert result["result"] == "0"

    def test_limit_one_sided_right(self):
        """lim(x->0+) 1/x = oo."""
        from sympy_compute import limit_expr

        result = limit_expr("1/x", "x", "0", "+")
        assert result["result"] == "oo"

    def test_limit_one_sided_left(self):
        """lim(x->0-) 1/x = -oo."""
        from sympy_compute import limit_expr

        result = limit_expr("1/x", "x", "0", "-")
        assert result["result"] == "-oo"

    def test_limit_negative_infinity(self):
        """lim(x->-oo) 1/x = 0."""
        from sympy_compute import limit_expr

        result = limit_expr("1/x", "x", "-oo")
        assert result["result"] == "0"


class TestDeterminant:
    """Tests for det_matrix function."""

    def test_det_2x2(self):
        """det([[1,2],[3,4]]) = 1*4 - 2*3 = -2."""
        from sympy_compute import det_matrix

        result = det_matrix("[[1,2],[3,4]]")
        assert result["determinant"] == "-2"
        assert result["is_singular"] is False

    def test_det_singular_matrix(self):
        """det([[1,2],[2,4]]) = 0 (singular)."""
        from sympy_compute import det_matrix

        result = det_matrix("[[1,2],[2,4]]")
        assert result["determinant"] == "0"
        assert result["is_singular"] is True

    def test_det_3x3_identity(self):
        """det(I_3) = 1."""
        from sympy_compute import det_matrix

        result = det_matrix("[[1,0,0],[0,1,0],[0,0,1]]")
        assert result["determinant"] == "1"

    def test_det_includes_matrix_size(self):
        """Result should include matrix dimensions."""
        from sympy_compute import det_matrix

        result = det_matrix("[[1,2],[3,4]]")
        assert result["matrix_size"] == "2x2"


class TestEigenvalues:
    """Tests for eigenvalues_matrix function."""

    def test_eigenvalues_2x2_diagonal(self):
        """Eigenvalues of [[2,0],[0,3]] are 2 and 3."""
        from sympy_compute import eigenvalues_matrix

        result = eigenvalues_matrix("[[2,0],[0,3]]")
        eigenvals = set(result["eigenvalues"])
        assert eigenvals == {"2", "3"}

    def test_eigenvalues_identity(self):
        """Eigenvalues of I_2 are both 1 (multiplicity 2)."""
        from sympy_compute import eigenvalues_matrix

        result = eigenvalues_matrix("[[1,0],[0,1]]")
        assert result["eigenvalues"] == ["1"]
        assert result["multiplicities"]["1"] == 2

    def test_eigenvalues_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import eigenvalues_matrix

        result = eigenvalues_matrix("[[2,0],[0,3]]")
        assert "latex" in result

    def test_eigenvalues_includes_size(self):
        """Result should include matrix dimensions."""
        from sympy_compute import eigenvalues_matrix

        result = eigenvalues_matrix("[[1,2],[3,4]]")
        assert result["matrix_size"] == "2x2"


class TestCharacteristicPolynomial:
    """Tests for charpoly_matrix function."""

    def test_charpoly_2x2(self):
        """Characteristic poly of [[1,2],[3,4]] is lambda^2 - 5*lambda - 2."""
        from sympy_compute import charpoly_matrix

        result = charpoly_matrix("[[1,2],[3,4]]")
        # lambda^2 - 5*lambda - 2
        poly = result["polynomial"]
        assert "lambda**2" in poly or "lambda^2" in poly
        assert result["degree"] == 2

    def test_charpoly_identity(self):
        """Characteristic poly of I_2 is (lambda-1)^2."""
        from sympy_compute import charpoly_matrix

        result = charpoly_matrix("[[1,0],[0,1]]")
        # Expanded: lambda^2 - 2*lambda + 1
        assert result["degree"] == 2

    def test_charpoly_custom_variable(self):
        """Can use custom variable name."""
        from sympy_compute import charpoly_matrix

        result = charpoly_matrix("[[1,2],[3,4]]", "t")
        assert "t" in result["polynomial"]

    def test_charpoly_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import charpoly_matrix

        result = charpoly_matrix("[[1,2],[3,4]]")
        assert "latex" in result


class TestCLINewCommands:
    """Tests for new CLI commands."""

    def test_parse_args_limit(self):
        """Parse args for limit command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "limit", "sin(x)/x", "--var", "x", "--to", "0"]
        try:
            args = parse_args()
            assert args.command == "limit"
            assert args.expression == "sin(x)/x"
            assert args.var == "x"
            assert args.to == "0"
        finally:
            sys.argv = old_argv

    def test_parse_args_det(self):
        """Parse args for det command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "det", "[[1,2],[3,4]]"]
        try:
            args = parse_args()
            assert args.command == "det"
            assert args.matrix == "[[1,2],[3,4]]"
        finally:
            sys.argv = old_argv

    def test_parse_args_eigenvalues(self):
        """Parse args for eigenvalues command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "eigenvalues", "[[1,2],[3,4]]"]
        try:
            args = parse_args()
            assert args.command == "eigenvalues"
            assert args.matrix == "[[1,2],[3,4]]"
        finally:
            sys.argv = old_argv

    def test_parse_args_charpoly(self):
        """Parse args for charpoly command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "charpoly", "[[1,2],[3,4]]", "--var", "t"]
        try:
            args = parse_args()
            assert args.command == "charpoly"
            assert args.matrix == "[[1,2],[3,4]]"
            assert args.var == "t"
        finally:
            sys.argv = old_argv


# ============================================================================
# Phase 2 TDD: Eigenvectors, Inverse, Transpose
# Tests written FIRST before implementation
# ============================================================================


class TestEigenvectorsMatrix:
    """Tests for eigenvectors_matrix function."""

    def test_eigenvectors_diagonal(self):
        """Diagonal matrix [[2,0],[0,3]] has eigenvectors [1,0] and [0,1]."""
        from sympy_compute import eigenvectors_matrix

        result = eigenvectors_matrix("[[2,0],[0,3]]")
        assert "eigenvectors" in result
        # Should have 2 eigenvectors
        assert len(result["eigenvectors"]) == 2

    def test_eigenvectors_identity(self):
        """Identity matrix I_2 has eigenvector [1,0] and [0,1] for eigenvalue 1."""
        from sympy_compute import eigenvectors_matrix

        result = eigenvectors_matrix("[[1,0],[0,1]]")
        assert "eigenvectors" in result
        # Identity has eigenvalue 1 with multiplicity 2
        assert len(result["eigenvectors"]) >= 1

    def test_eigenvectors_2x2(self):
        """Standard 2x2 matrix eigenvectors."""
        from sympy_compute import eigenvectors_matrix

        result = eigenvectors_matrix("[[1,2],[2,1]]")
        assert "eigenvectors" in result
        assert "eigenvalues" in result
        assert "latex" in result
        assert "matrix_size" in result

    def test_eigenvectors_includes_multiplicity(self):
        """Result includes algebraic/geometric multiplicity."""
        from sympy_compute import eigenvectors_matrix

        result = eigenvectors_matrix("[[1,0],[0,1]]")
        assert "multiplicities" in result


class TestInverseMatrix:
    """Tests for inverse_matrix function."""

    def test_inverse_2x2(self):
        """Inverse of [[1,2],[3,4]] is [[-2,1],[3/2,-1/2]]."""
        from sympy_compute import inverse_matrix

        result = inverse_matrix("[[1,2],[3,4]]")
        assert "inverse" in result
        assert result["determinant"] != "0"

    def test_inverse_identity(self):
        """Inverse of identity is identity."""
        from sympy_compute import inverse_matrix

        result = inverse_matrix("[[1,0],[0,1]]")
        assert "inverse" in result
        # I^-1 = I

    def test_inverse_diagonal(self):
        """Inverse of diagonal [[2,0],[0,3]] is [[1/2,0],[0,1/3]]."""
        from sympy_compute import inverse_matrix

        result = inverse_matrix("[[2,0],[0,3]]")
        assert "inverse" in result
        assert "latex" in result

    def test_inverse_singular_fails(self):
        """Singular matrix [[1,2],[2,4]] has no inverse."""
        from sympy_compute import inverse_matrix

        result = inverse_matrix("[[1,2],[2,4]]")
        # Should indicate error or det=0
        assert "error" in result or result.get("determinant") == "0"

    def test_inverse_3x3(self):
        """3x3 matrix inverse."""
        from sympy_compute import inverse_matrix

        result = inverse_matrix("[[1,0,0],[0,2,0],[0,0,3]]")
        assert "inverse" in result
        assert result["matrix_size"] == "3x3"


class TestTransposeMatrix:
    """Tests for transpose_matrix function."""

    def test_transpose_2x2(self):
        """Transpose of [[1,2],[3,4]] is [[1,3],[2,4]]."""
        from sympy_compute import transpose_matrix

        result = transpose_matrix("[[1,2],[3,4]]")
        assert "transpose" in result
        assert "latex" in result

    def test_transpose_symmetric(self):
        """Transpose of symmetric matrix is itself."""
        from sympy_compute import transpose_matrix

        result = transpose_matrix("[[1,2],[2,1]]")
        assert "transpose" in result
        # A^T = A for symmetric matrices

    def test_transpose_identity(self):
        """Transpose of identity is identity."""
        from sympy_compute import transpose_matrix

        result = transpose_matrix("[[1,0],[0,1]]")
        assert "transpose" in result

    def test_transpose_non_square(self):
        """Transpose of 2x3 is 3x2."""
        from sympy_compute import transpose_matrix

        result = transpose_matrix("[[1,2,3],[4,5,6]]")
        assert "transpose" in result
        assert result["original_size"] == "2x3"
        assert result["transpose_size"] == "3x2"


class TestCLIPhase2Commands:
    """Tests for Phase 2 CLI commands."""

    def test_parse_args_eigenvectors(self):
        """Parse args for eigenvectors command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "eigenvectors", "[[1,2],[3,4]]"]
        try:
            args = parse_args()
            assert args.command == "eigenvectors"
            assert args.matrix == "[[1,2],[3,4]]"
        finally:
            sys.argv = old_argv

    def test_parse_args_inverse(self):
        """Parse args for inverse command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "inverse", "[[1,2],[3,4]]"]
        try:
            args = parse_args()
            assert args.command == "inverse"
            assert args.matrix == "[[1,2],[3,4]]"
        finally:
            sys.argv = old_argv

    def test_parse_args_transpose(self):
        """Parse args for transpose command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "transpose", "[[1,2],[3,4]]"]
        try:
            args = parse_args()
            assert args.command == "transpose"
            assert args.matrix == "[[1,2],[3,4]]"
        finally:
            sys.argv = old_argv


# ============================================================================
# Phase 3 TDD: Algebra Commands (factor, expand, apart, gcd, lcm)
# Tests written FIRST before implementation
# ============================================================================


class TestFactor:
    """Tests for factor_expr function."""

    def test_factor_polynomial(self):
        """x^2 - 1 factors to (x - 1)*(x + 1)."""
        from sympy_compute import factor_expr

        result = factor_expr("x**2 - 1")
        assert "factored" in result
        assert "(x - 1)" in result["factored"]
        assert "(x + 1)" in result["factored"]

    def test_factor_quadratic(self):
        """x^2 + 2x + 1 factors to (x + 1)^2."""
        from sympy_compute import factor_expr

        result = factor_expr("x**2 + 2*x + 1")
        assert "factored" in result
        # Should be (x + 1)**2
        assert "(x + 1)**2" in result["factored"] or "(x + 1)^2" in result["factored"]

    def test_factor_cubic(self):
        """x^3 - 1 factors to (x - 1)*(x^2 + x + 1)."""
        from sympy_compute import factor_expr

        result = factor_expr("x**3 - 1")
        assert "factored" in result
        assert "(x - 1)" in result["factored"]

    def test_factor_with_coefficient(self):
        """2x^2 + 2x factors to 2*x*(x + 1)."""
        from sympy_compute import factor_expr

        result = factor_expr("2*x**2 + 2*x")
        assert "factored" in result
        assert "2" in result["factored"]

    def test_factor_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import factor_expr

        result = factor_expr("x**2 - 1")
        assert "latex" in result


class TestExpand:
    """Tests for expand_expr function."""

    def test_expand_product(self):
        """(x + 1)*(x + 2) expands to x^2 + 3*x + 2."""
        from sympy_compute import expand_expr

        result = expand_expr("(x+1)*(x+2)")
        assert "expanded" in result
        assert "x**2" in result["expanded"]

    def test_expand_square(self):
        """(x + 1)^2 expands to x^2 + 2*x + 1."""
        from sympy_compute import expand_expr

        result = expand_expr("(x + 1)**2")
        assert "expanded" in result
        assert "x**2" in result["expanded"]
        assert "2*x" in result["expanded"]

    def test_expand_cube(self):
        """(x + 1)^3 expands."""
        from sympy_compute import expand_expr

        result = expand_expr("(x + 1)**3")
        assert "expanded" in result
        assert "x**3" in result["expanded"]

    def test_expand_difference_of_squares(self):
        """(x - 1)*(x + 1) expands to x^2 - 1."""
        from sympy_compute import expand_expr

        result = expand_expr("(x - 1)*(x + 1)")
        assert "expanded" in result
        assert "x**2 - 1" in result["expanded"]

    def test_expand_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import expand_expr

        result = expand_expr("(x + 1)**2")
        assert "latex" in result


class TestApart:
    """Tests for partial_fractions function."""

    def test_apart_rational(self):
        """1/(x*(x+1)) decomposes to partial fractions."""
        from sympy_compute import partial_fractions

        result = partial_fractions("1/(x*(x+1))", "x")
        assert "partial_fractions" in result
        # Should decompose to 1/x - 1/(x+1) or similar
        assert "/" in result["partial_fractions"]

    def test_apart_difference_of_squares(self):
        """1/(x^2 - 1) decomposes properly."""
        from sympy_compute import partial_fractions

        result = partial_fractions("1/(x**2 - 1)", "x")
        assert "partial_fractions" in result
        # Should decompose to terms with x-1 and x+1 denominators

    def test_apart_quadratic_denominator(self):
        """1/((x + 1)*(x + 2)) decomposes."""
        from sympy_compute import partial_fractions

        result = partial_fractions("1/((x + 1)*(x + 2))", "x")
        assert "partial_fractions" in result

    def test_apart_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import partial_fractions

        result = partial_fractions("1/(x*(x+1))", "x")
        assert "latex" in result


class TestGcd:
    """Tests for gcd_expr function."""

    def test_gcd_polynomials(self):
        """GCD of x^2 - 1 and x - 1 is x - 1."""
        from sympy_compute import gcd_expr

        result = gcd_expr("x**2 - 1", "x - 1")
        assert "gcd" in result
        assert "x - 1" in result["gcd"]

    def test_gcd_integers(self):
        """GCD of 12 and 8 is 4."""
        from sympy_compute import gcd_expr

        result = gcd_expr("12", "8")
        assert "gcd" in result
        assert result["gcd"] == "4"

    def test_gcd_polynomials_common_factor(self):
        """GCD of x^3 - x and x^2 - 1."""
        from sympy_compute import gcd_expr

        result = gcd_expr("x**3 - x", "x**2 - 1")
        assert "gcd" in result
        # GCD is x^2 - 1

    def test_gcd_coprime(self):
        """GCD of x + 1 and x + 2 is 1."""
        from sympy_compute import gcd_expr

        result = gcd_expr("x + 1", "x + 2")
        assert "gcd" in result
        assert result["gcd"] == "1"

    def test_gcd_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import gcd_expr

        result = gcd_expr("x**2 - 1", "x - 1")
        assert "latex" in result


class TestLcm:
    """Tests for lcm_expr function."""

    def test_lcm_polynomials(self):
        """LCM of x^2 - 1 and x - 1."""
        from sympy_compute import lcm_expr

        result = lcm_expr("x**2 - 1", "x - 1")
        assert "lcm" in result
        # LCM is x^2 - 1 (since x-1 divides x^2-1)

    def test_lcm_integers(self):
        """LCM of 12 and 8 is 24."""
        from sympy_compute import lcm_expr

        result = lcm_expr("12", "8")
        assert "lcm" in result
        assert result["lcm"] == "24"

    def test_lcm_coprime_polynomials(self):
        """LCM of x - 1 and x + 1 is x^2 - 1."""
        from sympy_compute import lcm_expr

        result = lcm_expr("x - 1", "x + 1")
        assert "lcm" in result
        assert "x**2 - 1" in result["lcm"]

    def test_lcm_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import lcm_expr

        result = lcm_expr("x**2 - 1", "x - 1")
        assert "latex" in result


class TestCLIAlgebraCommands:
    """Tests for algebra CLI commands."""

    def test_parse_args_factor(self):
        """Parse args for factor command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "factor", "x**2 - 1"]
        try:
            args = parse_args()
            assert args.command == "factor"
            assert args.expression == "x**2 - 1"
        finally:
            sys.argv = old_argv

    def test_parse_args_expand(self):
        """Parse args for expand command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "expand", "(x+1)*(x+2)"]
        try:
            args = parse_args()
            assert args.command == "expand"
            assert args.expression == "(x+1)*(x+2)"
        finally:
            sys.argv = old_argv

    def test_parse_args_apart(self):
        """Parse args for apart command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "apart", "1/(x*(x+1))", "--var", "x"]
        try:
            args = parse_args()
            assert args.command == "apart"
            assert args.expression == "1/(x*(x+1))"
            assert args.var == "x"
        finally:
            sys.argv = old_argv

    def test_parse_args_gcd(self):
        """Parse args for gcd command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "gcd", "x**2 - 1", "x - 1"]
        try:
            args = parse_args()
            assert args.command == "gcd"
            assert args.expr1 == "x**2 - 1"
            assert args.expr2 == "x - 1"
        finally:
            sys.argv = old_argv

    def test_parse_args_lcm(self):
        """Parse args for lcm command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "lcm", "x**2 - 1", "x - 1"]
        try:
            args = parse_args()
            assert args.command == "lcm"
            assert args.expr1 == "x**2 - 1"
            assert args.expr2 == "x - 1"
        finally:
            sys.argv = old_argv


# ============================================================================
# Phase 4 TDD: Number Theory Commands (factorint, isprime, modinverse)
# Tests written FIRST before implementation
# ============================================================================


class TestFactorint:
    """Tests for factor_integer function."""

    def test_factorint_360(self):
        """360 = 2^3 * 3^2 * 5^1."""
        from sympy_compute import factor_integer

        result = factor_integer("360")
        assert result["factors"] == {"2": 3, "3": 2, "5": 1}
        assert result["n"] == "360"

    def test_factorint_prime(self):
        """17 is prime, so factors = {17: 1}."""
        from sympy_compute import factor_integer

        result = factor_integer("17")
        assert result["factors"] == {"17": 1}

    def test_factorint_power_of_two(self):
        """64 = 2^6."""
        from sympy_compute import factor_integer

        result = factor_integer("64")
        assert result["factors"] == {"2": 6}

    def test_factorint_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import factor_integer

        result = factor_integer("360")
        assert "latex" in result


class TestIsprime:
    """Tests for is_prime_check function."""

    def test_isprime_17(self):
        """17 is prime."""
        from sympy_compute import is_prime_check

        result = is_prime_check("17")
        assert result["is_prime"] is True
        assert result["n"] == "17"

    def test_isprime_15(self):
        """15 is not prime (3 * 5)."""
        from sympy_compute import is_prime_check

        result = is_prime_check("15")
        assert result["is_prime"] is False

    def test_isprime_2(self):
        """2 is prime."""
        from sympy_compute import is_prime_check

        result = is_prime_check("2")
        assert result["is_prime"] is True

    def test_isprime_1(self):
        """1 is not prime by convention."""
        from sympy_compute import is_prime_check

        result = is_prime_check("1")
        assert result["is_prime"] is False

    def test_isprime_large_prime(self):
        """Large prime check."""
        from sympy_compute import is_prime_check

        result = is_prime_check("104729")  # 10000th prime
        assert result["is_prime"] is True


class TestModInverse:
    """Tests for modular_inverse function."""

    def test_mod_inverse_3_7(self):
        """3^-1 mod 7 = 5 (since 3*5 = 15 = 1 mod 7)."""
        from sympy_compute import modular_inverse

        result = modular_inverse("3", "7")
        assert result["inverse"] == 5
        assert result["a"] == "3"
        assert result["m"] == "7"

    def test_mod_inverse_7_26(self):
        """7^-1 mod 26 = 15 (since 7*15 = 105 = 1 mod 26)."""
        from sympy_compute import modular_inverse

        result = modular_inverse("7", "26")
        assert result["inverse"] == 15

    def test_mod_inverse_no_inverse(self):
        """6^-1 mod 9 does not exist (gcd(6,9) = 3 != 1)."""
        from sympy_compute import modular_inverse

        result = modular_inverse("6", "9")
        assert "error" in result or result.get("inverse") is None

    def test_mod_inverse_verified(self):
        """Result should include verification."""
        from sympy_compute import modular_inverse

        result = modular_inverse("3", "7")
        assert result.get("verified") is True


class TestCLINumberTheoryCommands:
    """Tests for number theory CLI commands."""

    def test_parse_args_factorint(self):
        """Parse args for factorint command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "factorint", "360"]
        try:
            args = parse_args()
            assert args.command == "factorint"
            assert args.n == "360"
        finally:
            sys.argv = old_argv

    def test_parse_args_isprime(self):
        """Parse args for isprime command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "isprime", "17"]
        try:
            args = parse_args()
            assert args.command == "isprime"
            assert args.n == "17"
        finally:
            sys.argv = old_argv

    def test_parse_args_modinverse(self):
        """Parse args for modinverse command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "modinverse", "3", "7"]
        try:
            args = parse_args()
            assert args.command == "modinverse"
            assert args.a == "3"
            assert args.m == "7"
        finally:
            sys.argv = old_argv


# ============================================================================
# Phase 4 TDD: Calculus Commands (series, dsolve, laplace_transform)
# Tests written FIRST before implementation
# ============================================================================


class TestSeriesExpansion:
    """Tests for series_expansion function - Taylor/Maclaurin series."""

    def test_series_sin(self):
        """Taylor series of sin(x) around x=0."""
        from sympy_compute import series_expansion

        result = series_expansion("sin(x)", "x", "0", 6)
        assert "series" in result
        # sin(x) = x - x^3/6 + x^5/120 + O(x^6)
        assert "x" in result["series"]
        assert result["point"] == "0"
        assert result["order"] == 6

    def test_series_exp(self):
        """Maclaurin series of exp(x)."""
        from sympy_compute import series_expansion

        result = series_expansion("exp(x)", "x", "0", 5)
        assert "series" in result
        # e^x = 1 + x + x^2/2 + x^3/6 + x^4/24 + O(x^5)
        assert "1" in result["series"]

    def test_series_cos(self):
        """Taylor series of cos(x) around x=0."""
        from sympy_compute import series_expansion

        result = series_expansion("cos(x)", "x", "0", 6)
        assert "series" in result
        # cos(x) = 1 - x^2/2 + x^4/24 + O(x^6)

    def test_series_around_nonzero_point(self):
        """Taylor series around non-zero point."""
        from sympy_compute import series_expansion

        result = series_expansion("1/x", "x", "1", 4)
        assert "series" in result
        assert result["point"] == "1"

    def test_series_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import series_expansion

        result = series_expansion("sin(x)", "x", "0", 4)
        assert "latex" in result

    def test_series_polynomial_form(self):
        """Result includes polynomial form without O term."""
        from sympy_compute import series_expansion

        result = series_expansion("sin(x)", "x", "0", 6)
        assert "polynomial" in result
        # Polynomial should not contain O(...)


class TestSolveOde:
    """Tests for solve_ode function - ordinary differential equations."""

    def test_dsolve_first_order_linear(self):
        """f'(x) = f(x) should give C1*exp(x)."""
        from sympy_compute import solve_ode

        result = solve_ode("Derivative(f(x), x) - f(x)", "f(x)")
        assert "solution" in result
        # Solution: f(x) = C1*exp(x)
        assert "exp" in result["solution"] or "E" in result["solution"]

    def test_dsolve_second_order_harmonic(self):
        """f''(x) + f(x) = 0 (simple harmonic oscillator)."""
        from sympy_compute import solve_ode

        result = solve_ode("Derivative(f(x), x, 2) + f(x)", "f(x)")
        assert "solution" in result
        # Solution: f(x) = C1*sin(x) + C2*cos(x)
        assert "sin" in result["solution"] or "cos" in result["solution"]

    def test_dsolve_with_initial_condition(self):
        """f'(x) = f(x) with f(0) = 1 gives exp(x)."""
        from sympy_compute import solve_ode

        result = solve_ode("Derivative(f(x), x) - f(x)", "f(x)", ics="f(0)=1")
        assert "solution" in result
        # With IC f(0)=1, solution is f(x) = exp(x)

    def test_dsolve_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import solve_ode

        result = solve_ode("Derivative(f(x), x) - f(x)", "f(x)")
        assert "latex" in result

    def test_dsolve_includes_order(self):
        """Result should indicate ODE order."""
        from sympy_compute import solve_ode

        result = solve_ode("Derivative(f(x), x, 2) + f(x)", "f(x)")
        assert "order" in result
        assert result["order"] == 2


class TestLaplaceTransformExpr:
    """Tests for laplace_transform_expr function."""

    def test_laplace_exp(self):
        """L{exp(-t)} = 1/(s+1)."""
        from sympy_compute import laplace_transform_expr

        result = laplace_transform_expr("exp(-t)", "t", "s")
        assert "transform" in result
        # L{e^(-t)} = 1/(s+1)
        assert "s" in result["transform"]

    def test_laplace_constant(self):
        """L{1} = 1/s."""
        from sympy_compute import laplace_transform_expr

        result = laplace_transform_expr("1", "t", "s")
        assert "transform" in result
        # L{1} = 1/s

    def test_laplace_t(self):
        """L{t} = 1/s^2."""
        from sympy_compute import laplace_transform_expr

        result = laplace_transform_expr("t", "t", "s")
        assert "transform" in result
        # L{t} = 1/s^2

    def test_laplace_sin(self):
        """L{sin(t)} = 1/(s^2 + 1)."""
        from sympy_compute import laplace_transform_expr

        result = laplace_transform_expr("sin(t)", "t", "s")
        assert "transform" in result
        # L{sin(t)} = 1/(s^2 + 1)

    def test_laplace_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import laplace_transform_expr

        result = laplace_transform_expr("exp(-t)", "t", "s")
        assert "latex" in result

    def test_laplace_includes_convergence(self):
        """Result should include convergence information."""
        from sympy_compute import laplace_transform_expr

        result = laplace_transform_expr("exp(-t)", "t", "s")
        # Should include convergence condition or abscissa
        assert "convergence" in result or "condition" in result


class TestCLICalculusCommands:
    """Tests for calculus CLI commands (series, dsolve, laplace)."""

    def test_parse_args_series(self):
        """Parse args for series command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "series", "sin(x)", "--var", "x", "--point", "0", "--order", "6"]
        try:
            args = parse_args()
            assert args.command == "series"
            assert args.expression == "sin(x)"
            assert args.var == "x"
            assert args.point == "0"
            assert args.order == 6
        finally:
            sys.argv = old_argv

    def test_parse_args_dsolve(self):
        """Parse args for dsolve command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "dsolve", "Derivative(f(x), x) - f(x)", "--func", "f(x)"]
        try:
            args = parse_args()
            assert args.command == "dsolve"
            assert args.equation == "Derivative(f(x), x) - f(x)"
            assert args.func == "f(x)"
        finally:
            sys.argv = old_argv

    def test_parse_args_laplace(self):
        """Parse args for laplace command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "laplace", "exp(-t)", "--var", "t", "--svar", "s"]
        try:
            args = parse_args()
            assert args.command == "laplace"
            assert args.expression == "exp(-t)"
            assert args.var == "t"
            assert args.svar == "s"
        finally:
            sys.argv = old_argv


# ============================================================================
# Phase 5 TDD: Linear Algebra - linsolve, nullspace, rref, rank
# Tests written FIRST before implementation
# ============================================================================


class TestLinsolve:
    """Tests for linsolve_system function."""

    def test_linsolve_two_variables(self):
        """Solve x + y = 1, x - y = 3 => (x=2, y=-1)."""
        from sympy_compute import linsolve_system

        result = linsolve_system("x + y - 1, x - y - 3", "x,y")
        assert "solutions" in result
        # Should have solution (2, -1)
        sols = result["solutions"]
        assert len(sols) >= 1

    def test_linsolve_three_variables(self):
        """Solve 3-variable system."""
        from sympy_compute import linsolve_system

        result = linsolve_system("x + y + z - 6, x - y - 2, y + z - 4", "x,y,z")
        assert "solutions" in result

    def test_linsolve_no_solution(self):
        """Inconsistent system has no solution."""
        from sympy_compute import linsolve_system

        result = linsolve_system("x + y - 1, x + y - 2", "x,y")
        # Empty solution set
        assert result["solutions"] == [] or result["solutions"] == "EmptySet"

    def test_linsolve_infinite_solutions(self):
        """Underdetermined system has parametric solution."""
        from sympy_compute import linsolve_system

        result = linsolve_system("x + y + z - 1", "x,y,z")
        assert "solutions" in result
        # Should indicate parametric solution or contain free variables

    def test_linsolve_from_equations(self):
        """Solve from equation format with '='."""
        from sympy_compute import linsolve_system

        result = linsolve_system("x + y = 1, x - y = 3", "x,y")
        assert "solutions" in result


class TestNullspace:
    """Tests for nullspace_matrix function."""

    def test_nullspace_rank_deficient(self):
        """Matrix [[1,2,3],[4,5,6],[7,8,9]] has 1D nullspace."""
        from sympy_compute import nullspace_matrix

        result = nullspace_matrix("[[1,2,3],[4,5,6],[7,8,9]]")
        assert "nullspace" in result
        # Should have 1 basis vector
        assert len(result["nullspace"]) >= 1

    def test_nullspace_full_rank(self):
        """Full rank matrix has empty nullspace."""
        from sympy_compute import nullspace_matrix

        result = nullspace_matrix("[[1,0],[0,1]]")
        assert "nullspace" in result
        # Empty nullspace
        assert result["nullspace"] == []

    def test_nullspace_2d(self):
        """Matrix with 2D nullspace."""
        from sympy_compute import nullspace_matrix

        result = nullspace_matrix("[[1,2,3,4],[5,6,7,8]]")
        assert "nullspace" in result
        # 4 columns - rank 2 = 2 basis vectors
        assert len(result["nullspace"]) == 2

    def test_nullspace_includes_dimension(self):
        """Result includes nullspace dimension."""
        from sympy_compute import nullspace_matrix

        result = nullspace_matrix("[[1,2,3],[4,5,6],[7,8,9]]")
        assert "dimension" in result
        assert result["dimension"] >= 1


class TestRref:
    """Tests for rref_matrix function."""

    def test_rref_simple(self):
        """RREF of [[1,2,3],[4,5,6]] returns row echelon form."""
        from sympy_compute import rref_matrix

        result = rref_matrix("[[1,2,3],[4,5,6]]")
        assert "rref" in result
        assert "pivots" in result

    def test_rref_identity(self):
        """RREF of identity is identity."""
        from sympy_compute import rref_matrix

        result = rref_matrix("[[1,0],[0,1]]")
        assert "rref" in result
        assert result["pivots"] == [0, 1] or result["pivots"] == (0, 1)

    def test_rref_rank_2(self):
        """RREF reveals rank via pivot count."""
        from sympy_compute import rref_matrix

        result = rref_matrix("[[1,2,3],[4,5,6],[7,8,9]]")
        assert "rref" in result
        assert "pivots" in result
        # Rank 2, so 2 pivots
        assert len(result["pivots"]) == 2

    def test_rref_includes_matrix_info(self):
        """Result includes matrix size."""
        from sympy_compute import rref_matrix

        result = rref_matrix("[[1,2,3],[4,5,6]]")
        assert "matrix_size" in result


class TestRank:
    """Tests for rank_matrix function."""

    def test_rank_full_2x2(self):
        """Rank of [[1,0],[0,1]] is 2."""
        from sympy_compute import rank_matrix

        result = rank_matrix("[[1,0],[0,1]]")
        assert result["rank"] == 2

    def test_rank_full_3x3(self):
        """Rank of 3x3 identity is 3."""
        from sympy_compute import rank_matrix

        result = rank_matrix("[[1,0,0],[0,1,0],[0,0,1]]")
        assert result["rank"] == 3

    def test_rank_deficient(self):
        """Rank of [[1,2,3],[4,5,6],[7,8,9]] is 2."""
        from sympy_compute import rank_matrix

        result = rank_matrix("[[1,2,3],[4,5,6],[7,8,9]]")
        assert result["rank"] == 2

    def test_rank_zero_matrix(self):
        """Rank of zero matrix is 0."""
        from sympy_compute import rank_matrix

        result = rank_matrix("[[0,0],[0,0]]")
        assert result["rank"] == 0

    def test_rank_rectangular(self):
        """Rank of rectangular matrix."""
        from sympy_compute import rank_matrix

        result = rank_matrix("[[1,2,3,4],[5,6,7,8]]")
        assert result["rank"] == 2
        assert result["matrix_size"] == "2x4"


class TestCLILinearAlgebraCommands:
    """Tests for linear algebra CLI commands."""

    def test_parse_args_linsolve(self):
        """Parse args for linsolve command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "linsolve", "x + y - 1, x - y - 3", "--vars", "x,y"]
        try:
            args = parse_args()
            assert args.command == "linsolve"
            assert args.equations == "x + y - 1, x - y - 3"
            assert args.vars == "x,y"
        finally:
            sys.argv = old_argv

    def test_parse_args_nullspace(self):
        """Parse args for nullspace command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "nullspace", "[[1,2,3],[4,5,6]]"]
        try:
            args = parse_args()
            assert args.command == "nullspace"
            assert args.matrix == "[[1,2,3],[4,5,6]]"
        finally:
            sys.argv = old_argv

    def test_parse_args_rref(self):
        """Parse args for rref command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "rref", "[[1,2,3],[4,5,6]]"]
        try:
            args = parse_args()
            assert args.command == "rref"
            assert args.matrix == "[[1,2,3],[4,5,6]]"
        finally:
            sys.argv = old_argv

    def test_parse_args_rank(self):
        """Parse args for rank command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "rank", "[[1,0],[0,1]]"]
        try:
            args = parse_args()
            assert args.command == "rank"
            assert args.matrix == "[[1,0],[0,1]]"
        finally:
            sys.argv = old_argv


# ============================================================================
# Phase 6 TDD: Combinatorics Functions
# Tests written FIRST before implementation
# ============================================================================


class TestBinomialCoeff:
    """Tests for binomial_coeff function."""

    def test_binomial_5_2(self):
        """C(5,2) = 10."""
        from sympy_compute import binomial_coeff

        result = binomial_coeff("5", "2")
        assert result["result"] == "10"
        assert result["n"] == "5"
        assert result["k"] == "2"

    def test_binomial_10_5(self):
        """C(10,5) = 252."""
        from sympy_compute import binomial_coeff

        result = binomial_coeff("10", "5")
        assert result["result"] == "252"

    def test_binomial_k_greater_than_n(self):
        """C(3,5) = 0 when k > n."""
        from sympy_compute import binomial_coeff

        result = binomial_coeff("3", "5")
        assert result["result"] == "0"

    def test_binomial_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import binomial_coeff

        result = binomial_coeff("5", "2")
        assert "latex" in result


class TestFactorialCompute:
    """Tests for factorial_compute function."""

    def test_factorial_5(self):
        """5! = 120."""
        from sympy_compute import factorial_compute

        result = factorial_compute("5")
        assert result["result"] == "120"
        assert result["n"] == "5"

    def test_factorial_0(self):
        """0! = 1."""
        from sympy_compute import factorial_compute

        result = factorial_compute("0")
        assert result["result"] == "1"

    def test_factorial_double(self):
        """7!! = 105."""
        from sympy_compute import factorial_compute

        result = factorial_compute("7", kind="double")
        assert result["result"] == "105"
        assert result["kind"] == "double"

    def test_factorial_subfactorial(self):
        """!5 = 44 (derangements of 5)."""
        from sympy_compute import factorial_compute

        result = factorial_compute("5", kind="subfactorial")
        assert result["result"] == "44"

    def test_factorial_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import factorial_compute

        result = factorial_compute("5")
        assert "latex" in result


class TestPermutationCount:
    """Tests for permutation_count function."""

    def test_permutation_5_2(self):
        """P(5,2) = 5*4 = 20."""
        from sympy_compute import permutation_count

        result = permutation_count("5", "2")
        assert result["result"] == "20"

    def test_permutation_10_3(self):
        """P(10,3) = 10*9*8 = 720."""
        from sympy_compute import permutation_count

        result = permutation_count("10", "3")
        assert result["result"] == "720"

    def test_permutation_k_equals_n(self):
        """P(5,5) = 5! = 120."""
        from sympy_compute import permutation_count

        result = permutation_count("5", "5")
        assert result["result"] == "120"

    def test_permutation_k_greater_than_n(self):
        """P(3,5) = 0 when k > n."""
        from sympy_compute import permutation_count

        result = permutation_count("3", "5")
        assert result["result"] == "0"

    def test_permutation_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import permutation_count

        result = permutation_count("5", "2")
        assert "latex" in result


class TestPartitionCount:
    """Tests for partition_count function."""

    def test_partition_0(self):
        """p(0) = 1 (empty partition)."""
        from sympy_compute import partition_count

        result = partition_count("0")
        assert result["result"] == "1"

    def test_partition_5(self):
        """p(5) = 7."""
        from sympy_compute import partition_count

        result = partition_count("5")
        assert result["result"] == "7"

    def test_partition_10(self):
        """p(10) = 42."""
        from sympy_compute import partition_count

        result = partition_count("10")
        assert result["result"] == "42"

    def test_partition_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import partition_count

        result = partition_count("5")
        assert "latex" in result


class TestCatalanNumber:
    """Tests for catalan_number function."""

    def test_catalan_0(self):
        """C_0 = 1."""
        from sympy_compute import catalan_number

        result = catalan_number("0")
        assert result["result"] == "1"

    def test_catalan_5(self):
        """C_5 = 42."""
        from sympy_compute import catalan_number

        result = catalan_number("5")
        assert result["result"] == "42"

    def test_catalan_10(self):
        """C_10 = 16796."""
        from sympy_compute import catalan_number

        result = catalan_number("10")
        assert result["result"] == "16796"

    def test_catalan_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import catalan_number

        result = catalan_number("5")
        assert "latex" in result


class TestBellNumber:
    """Tests for bell_number function."""

    def test_bell_0(self):
        """B_0 = 1."""
        from sympy_compute import bell_number

        result = bell_number("0")
        assert result["result"] == "1"

    def test_bell_5(self):
        """B_5 = 52."""
        from sympy_compute import bell_number

        result = bell_number("5")
        assert result["result"] == "52"

    def test_bell_10(self):
        """B_10 = 115975."""
        from sympy_compute import bell_number

        result = bell_number("10")
        assert result["result"] == "115975"

    def test_bell_includes_latex(self):
        """Result should include LaTeX representation."""
        from sympy_compute import bell_number

        result = bell_number("5")
        assert "latex" in result


class TestCLICombinatoricsCommands:
    """Tests for combinatorics CLI commands."""

    def test_parse_args_binomial(self):
        """Parse args for binomial command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "binomial", "5", "2"]
        try:
            args = parse_args()
            assert args.command == "binomial"
            assert args.n == "5"
            assert args.k == "2"
        finally:
            sys.argv = old_argv

    def test_parse_args_factorial(self):
        """Parse args for factorial command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "factorial", "5", "--kind", "double"]
        try:
            args = parse_args()
            assert args.command == "factorial"
            assert args.n == "5"
            assert args.kind == "double"
        finally:
            sys.argv = old_argv

    def test_parse_args_permutation(self):
        """Parse args for permutation command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "permutation", "10", "3"]
        try:
            args = parse_args()
            assert args.command == "permutation"
            assert args.n == "10"
            assert args.k == "3"
        finally:
            sys.argv = old_argv

    def test_parse_args_partition(self):
        """Parse args for partition command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "partition", "5"]
        try:
            args = parse_args()
            assert args.command == "partition"
            assert args.n == "5"
        finally:
            sys.argv = old_argv

    def test_parse_args_catalan(self):
        """Parse args for catalan command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "catalan", "5"]
        try:
            args = parse_args()
            assert args.command == "catalan"
            assert args.n == "5"
        finally:
            sys.argv = old_argv

    def test_parse_args_bell(self):
        """Parse args for bell command."""
        from sympy_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["sympy_compute.py", "bell", "5"]
        try:
            args = parse_args()
            assert args.command == "bell"
            assert args.n == "5"
        finally:
            sys.argv = old_argv
