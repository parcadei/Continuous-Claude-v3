#!/usr/bin/env python3
"""Tests for the math router deterministic routing system."""

import pytest
import sys
import os

# Add scripts to path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

from math_router import (
    route,
    list_commands,
    build_command,
    extract_expr_var,
    extract_integrate_expr,
    extract_equation_var,
    extract_unit_conversion,
    extract_theorem,
    extract_plot_params,
    extract_hint_request,
    extract_problem_gen,
    extract_limit,
    extract_optimization,
    # NumPy/SciPy/mpmath extractors
    extract_np_matrix,
    extract_np_array,
    extract_np_fft,
    extract_scipy_minimize,
    extract_scipy_root,
    extract_scipy_quad,
    extract_mpmath_constant,
    extract_mpmath_func,
    extract_mpmath_zeta,
    extract_mpmath_gamma,
    RouteMatch,
)


class TestRouteMatching:
    """Test pattern matching for different math intents."""

    # ============ SymPy Calculus Routes ============

    def test_route_integrate_basic(self):
        """Test routing integration requests."""
        result = route("integrate sin(x)")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "integrate"
        assert result.confidence > 0.5

    def test_route_integrate_antiderivative(self):
        """Test 'antiderivative' keyword routes to integrate."""
        result = route("find the antiderivative of x^2")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "integrate"

    def test_route_integral_keyword(self):
        """Test 'integral' keyword routes to integrate."""
        result = route("what is the integral of cos(x)")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "integrate"

    def test_route_differentiate_basic(self):
        """Test routing differentiation requests."""
        result = route("differentiate x^3")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "diff"
        assert result.confidence > 0.5

    def test_route_derivative_keyword(self):
        """Test 'derivative' keyword routes to diff."""
        result = route("find the derivative of sin(x)")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "diff"

    def test_route_diff_keyword(self):
        """Test 'diff' keyword routes correctly."""
        result = route("diff x^4 + 2x")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "diff"

    def test_route_limit_basic(self):
        """Test routing limit requests."""
        result = route("limit of sin(x)/x as x -> 0")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "limit"

    def test_route_series_taylor(self):
        """Test routing Taylor series requests."""
        result = route("taylor series of sin(x)")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "series"

    def test_route_series_maclaurin(self):
        """Test routing Maclaurin series requests."""
        result = route("maclaurin expansion of exp(x)")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "series"

    # ============ SymPy Algebra Routes ============

    def test_route_solve_equation(self):
        """Test routing solve requests."""
        result = route("solve x^2 - 4 = 0")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "solve"

    def test_route_solve_for_variable(self):
        """Test routing 'solve for' requests."""
        result = route("solve for x in x^2 + 2x - 3 = 0")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "solve"

    def test_route_simplify(self):
        """Test routing simplify requests."""
        result = route("simplify (x+1)^2 - x^2")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "simplify"

    def test_route_factor(self):
        """Test routing factor requests."""
        result = route("factor x^2 - 1")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "factor"

    def test_route_expand(self):
        """Test routing expand requests."""
        result = route("expand (x+1)^3")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "expand"

    # ============ SymPy Linear Algebra Routes ============

    def test_route_eigenvalues(self):
        """Test routing eigenvalue requests."""
        result = route("find eigenvalues of [[1,2],[3,4]]")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "eigenvalues"

    def test_route_eigenvectors(self):
        """Test routing eigenvector requests."""
        result = route("compute eigenvectors of [[1,0],[0,2]]")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "eigenvectors"

    def test_route_determinant(self):
        """Test routing determinant requests."""
        result = route("determinant of [[1,2],[3,4]]")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "det"

    def test_route_matrix_inverse(self):
        """Test routing matrix inverse requests."""
        result = route("inverse of matrix [[1,2],[3,4]]")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "inverse"

    def test_route_rref(self):
        """Test routing RREF requests."""
        result = route("find rref of [[1,2,3],[4,5,6]]")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "rref"

    def test_route_nullspace(self):
        """Test routing null space requests."""
        result = route("compute the null space of [[1,2],[2,4]]")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "nullspace"

    def test_route_matrix_rank(self):
        """Test routing matrix rank requests."""
        result = route("what is the rank of matrix [[1,0],[0,1]]")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "rank"

    # ============ Pint Unit Conversion Routes ============

    def test_route_convert_units(self):
        """Test routing unit conversion requests."""
        result = route("convert 5 meters to feet")
        assert result.script == "pint_compute.py"
        assert result.subcommand == "convert"

    def test_route_convert_without_keyword(self):
        """Test routing implicit conversion requests."""
        result = route("10 kg to pounds")
        assert result.script == "pint_compute.py"
        assert result.subcommand == "convert"

    def test_route_dimension_check(self):
        """Test routing dimensional compatibility check."""
        result = route("are newton and kg*m/s^2 compatible")
        assert result.script == "pint_compute.py"
        assert result.subcommand == "check"

    # ============ Z3 Routes ============

    def test_route_prove_theorem(self):
        """Test routing prove requests."""
        result = route("prove x + y == y + x")
        assert result.script == "z3_solve.py"
        assert result.subcommand == "prove"

    def test_route_prove_theorem_keyword(self):
        """Test routing theorem keyword."""
        result = route("theorem: a*b == b*a")
        assert result.script == "z3_solve.py"
        assert result.subcommand == "prove"

    def test_route_satisfiable(self):
        """Test routing SAT check requests."""
        result = route("is satisfiable x > 0, x < 10, x*x == 49")
        assert result.script == "z3_solve.py"
        assert result.subcommand == "sat"

    def test_route_optimize(self):
        """Test routing optimization requests."""
        result = route("maximize x + y subject to x >= 0, y >= 0, x + y <= 10")
        assert result.script == "z3_solve.py"
        assert result.subcommand == "optimize"

    def test_route_minimize(self):
        """Test routing minimize requests."""
        result = route("minimize x^2 + y^2 where x + y >= 10")
        assert result.script == "z3_solve.py"
        assert result.subcommand == "optimize"

    # ============ Math Tutor Routes ============

    def test_route_hint(self):
        """Test routing hint requests."""
        result = route("give me a hint for x^2 - 4 = 0")
        assert result.script == "math_tutor.py"
        assert result.subcommand == "hint"

    def test_route_step_by_step(self):
        """Test routing step-by-step requests."""
        result = route("step by step solution for x^2 - 4 = 0")
        assert result.script == "math_tutor.py"
        assert result.subcommand == "steps"

    def test_route_show_steps(self):
        """Test routing show steps requests."""
        result = route("show steps for solving 2x + 3 = 7")
        assert result.script == "math_tutor.py"
        assert result.subcommand == "steps"

    def test_route_generate_problem(self):
        """Test routing problem generation requests."""
        result = route("generate a practice problem about algebra")
        assert result.script == "math_tutor.py"
        assert result.subcommand == "generate"

    # ============ Math Scratchpad Routes ============

    def test_route_verify_step(self):
        """Test routing verify step requests."""
        result = route("verify that step x = 2 implies x^2 = 4")
        assert result.script == "math_scratchpad.py"
        assert result.subcommand == "verify"

    def test_route_explain_step(self):
        """Test routing explain step requests."""
        result = route("explain the step d/dx(x^3) = 3x^2")
        assert result.script == "math_scratchpad.py"
        assert result.subcommand == "explain"

    # ============ Math Plot Routes ============

    def test_route_plot_2d(self):
        """Test routing 2D plot requests."""
        result = route("plot sin(x)")
        assert result.script == "math_plot.py"
        assert result.subcommand == "plot2d"

    def test_route_graph(self):
        """Test routing graph requests."""
        result = route("graph x^2 from -5 to 5")
        assert result.script == "math_plot.py"
        assert result.subcommand == "plot2d"

    def test_route_3d_plot(self):
        """Test routing 3D plot requests."""
        result = route("3d plot of x^2 + y^2")
        assert result.script == "math_plot.py"
        assert result.subcommand == "plot3d"

    def test_route_surface(self):
        """Test routing surface plot requests."""
        result = route("surface plot z = x*y")
        assert result.script == "math_plot.py"
        assert result.subcommand == "plot3d"

    def test_route_latex_render(self):
        """Test routing LaTeX render requests."""
        result = route("render latex \\int e^{-x^2} dx")
        assert result.script == "math_plot.py"
        assert result.subcommand == "latex"


class TestArgumentExtraction:
    """Test argument extraction from natural language."""

    def test_extract_expr_var_integrate(self):
        """Test extracting expression and variable for integration."""
        result = extract_expr_var("integrate sin(x)")
        assert result["expression"] == "sin(x)"
        assert result["var"] == "x"

    def test_extract_expr_var_with_caret(self):
        """Test caret to ** conversion."""
        result = extract_expr_var("differentiate x^3")
        assert result["expression"] == "x**3"

    def test_extract_integrate_bounds(self):
        """Test extracting definite integral bounds."""
        result = extract_integrate_expr("integrate x from 0 to 1")
        assert result["bounds"] == ["0", "1"]

    def test_extract_equation_var(self):
        """Test extracting equation and solve variable."""
        result = extract_equation_var("solve x^2 - 4 = 0")
        assert "x**2 - 4" in result["expression"] or "x**2" in result["expression"]
        assert result["var"] == "x"

    def test_extract_equation_with_domain(self):
        """Test extracting domain specification."""
        result = extract_equation_var("solve x^2 - 4 = 0 for real x")
        assert result["domain"] == "real"

    def test_extract_unit_conversion(self):
        """Test extracting unit conversion parameters."""
        result = extract_unit_conversion("convert 5 meters to feet")
        assert result["quantity"] == "5 meters"
        assert result["to"] == "feet"

    def test_extract_unit_conversion_implicit(self):
        """Test extracting implicit conversion."""
        result = extract_unit_conversion("10 kg to pounds")
        assert "10" in result["quantity"] and "kg" in result["quantity"]
        assert result["to"] == "pounds"

    def test_extract_theorem(self):
        """Test extracting theorem statement."""
        result = extract_theorem("prove x + y == y + x")
        assert "x + y" in result["theorem"]
        assert "x" in result["vars"]
        assert "y" in result["vars"]

    def test_extract_plot_params(self):
        """Test extracting plot parameters."""
        result = extract_plot_params("plot sin(x) from -10 to 10")
        assert result["expression"] == "sin(x)"
        assert result["range"] == [-10.0, 10.0]
        assert result["var"] == "x"

    def test_extract_hint_request(self):
        """Test extracting hint request parameters."""
        result = extract_hint_request("hint for x^2 - 4 = 0 level 2")
        assert result["level"] == 2
        assert "x" in result["problem"]

    def test_extract_problem_gen(self):
        """Test extracting problem generation parameters."""
        result = extract_problem_gen("generate easy quadratic problem")
        assert result["topic"] == "quadratic"
        assert result["difficulty"] == 1  # easy = 1

    def test_extract_problem_gen_hard(self):
        """Test extracting hard difficulty."""
        result = extract_problem_gen("generate hard algebra problem")
        assert result["difficulty"] == 4  # hard = 4

    def test_extract_limit(self):
        """Test extracting limit parameters."""
        result = extract_limit("limit of sin(x)/x as x -> 0")
        assert "sin(x)/x" in result["expression"] or "sin" in result["expression"]
        assert result["var"] == "x"
        assert result["to"] == "0"

    def test_extract_limit_infinity(self):
        """Test extracting limit at infinity."""
        result = extract_limit("limit of 1/x as x approaches infinity")
        assert result["to"] == "oo"

    def test_extract_limit_one_sided(self):
        """Test extracting one-sided limit."""
        result = extract_limit("limit of 1/x as x -> 0 from the right")
        assert result["dir"] == "+"

    def test_extract_optimization(self):
        """Test extracting optimization parameters."""
        result = extract_optimization("maximize x + y subject to x >= 0, y >= 0")
        assert "x + y" in result["objective"]
        assert result["direction"] == "maximize"
        assert "x >= 0" in result["constraints"]


class TestCommandBuilding:
    """Test CLI command building."""

    def test_build_integrate_command(self):
        """Test building integrate command."""
        cmd = build_command(
            "sympy_compute.py",
            "integrate",
            {"expression": "sin(x)", "var": "x"}
        )
        assert "sympy_compute.py" in cmd
        assert "integrate" in cmd
        assert "sin(x)" in cmd

    def test_build_solve_command(self):
        """Test building solve command."""
        cmd = build_command(
            "sympy_compute.py",
            "solve",
            {"expression": "x**2 - 4", "var": "x", "domain": "real"}
        )
        assert "solve" in cmd
        assert "--domain real" in cmd

    def test_build_convert_command(self):
        """Test building convert command."""
        cmd = build_command(
            "pint_compute.py",
            "convert",
            {"quantity": "5 meters", "to": "feet"}
        )
        assert "pint_compute.py" in cmd
        assert "convert" in cmd
        assert "5 meters" in cmd
        assert "--to" in cmd
        assert "feet" in cmd

    def test_build_prove_command(self):
        """Test building prove command."""
        cmd = build_command(
            "z3_solve.py",
            "prove",
            {"theorem": "x + y == y + x", "vars": ["x", "y"], "var_type": "int"}
        )
        assert "prove" in cmd
        assert "x + y == y + x" in cmd
        assert "--vars x y" in cmd

    def test_build_plot_command(self):
        """Test building plot command."""
        cmd = build_command(
            "math_plot.py",
            "plot2d",
            {"expression": "sin(x)", "var": "x", "range": [-10, 10], "output": "/tmp/plot.png"}
        )
        assert "plot2d" in cmd
        assert "sin(x)" in cmd
        assert "--range -10 10" in cmd


class TestListCommands:
    """Test listing available commands."""

    def test_list_all_commands(self):
        """Test listing all commands."""
        result = list_commands()
        assert "sympy" in result
        assert "pint" in result
        assert "z3" in result
        assert "tutor" in result
        assert "plot" in result

    def test_list_sympy_commands(self):
        """Test listing SymPy commands only."""
        result = list_commands("sympy")
        assert "sympy" in result
        assert len(result) == 1
        assert len(result["sympy"]) > 0

    def test_list_z3_commands(self):
        """Test listing Z3 commands only."""
        result = list_commands("z3")
        assert "z3" in result
        subcommands = [cmd["subcommand"] for cmd in result["z3"]]
        assert "prove" in subcommands
        assert "sat" in subcommands
        assert "optimize" in subcommands


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_no_match_returns_empty(self):
        """Test that unrecognized intents return empty match."""
        result = route("random gibberish that matches nothing")
        assert result.confidence == 0.0
        assert result.command == ""

    def test_ambiguous_intent_has_alternatives(self):
        """Test that ambiguous intents provide alternatives."""
        result = route("simplify and factor x^2 - 1")  # Could be simplify or factor
        # Should match something and potentially have alternatives
        assert result.confidence > 0

    def test_case_insensitivity(self):
        """Test case insensitivity of routing."""
        result1 = route("INTEGRATE sin(x)")
        result2 = route("integrate sin(x)")
        assert result1.script == result2.script
        assert result1.subcommand == result2.subcommand

    def test_empty_intent(self):
        """Test handling of empty intent."""
        result = route("")
        assert result.confidence == 0.0

    def test_special_characters(self):
        """Test handling of special mathematical characters."""
        result = route("integrate sin(x) * cos(x)")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "integrate"

    def test_priority_ordering(self):
        """Test that higher priority routes win."""
        # 'solve for' should beat general patterns
        result = route("solve x^2 - 4 = 0 for x")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "solve"


class TestRouteMatchStructure:
    """Test the RouteMatch structure."""

    def test_route_match_fields(self):
        """Test that RouteMatch contains all expected fields."""
        result = route("integrate sin(x)")
        assert hasattr(result, 'command')
        assert hasattr(result, 'script')
        assert hasattr(result, 'subcommand')
        assert hasattr(result, 'args')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'pattern')
        assert hasattr(result, 'alternatives')

    def test_route_match_args_dict(self):
        """Test that args is a dict with extracted arguments."""
        result = route("integrate sin(x)")
        assert isinstance(result.args, dict)
        assert "expression" in result.args

    def test_route_match_alternatives_list(self):
        """Test that alternatives is a list."""
        result = route("integrate sin(x)")
        assert isinstance(result.alternatives, list)


class TestRealWorldExamples:
    """Test with realistic user queries."""

    def test_calculus_homework(self):
        """Test typical calculus homework queries."""
        # Integration
        result = route("what is the integral of x^2 dx")
        assert result.subcommand == "integrate"

        # Derivative
        result = route("find d/dx of sin(x) * x")
        assert result.subcommand == "diff"

    def test_physics_unit_conversion(self):
        """Test typical physics unit conversions."""
        result = route("convert 100 km/h to m/s")
        assert result.script == "pint_compute.py"
        assert result.subcommand == "convert"

    def test_linear_algebra_query(self):
        """Test typical linear algebra queries."""
        result = route("what are the eigenvalues of the matrix [[2,1],[1,2]]")
        assert result.script == "sympy_compute.py"
        assert result.subcommand == "eigenvalues"

    def test_geometry_plotting(self):
        """Test geometry visualization queries."""
        result = route("visualize the function x^2 + y^2 = 1")
        assert result.script == "math_plot.py"

    def test_proof_verification(self):
        """Test proof verification queries."""
        result = route("prove that addition is commutative: a + b = b + a")
        assert result.script == "z3_solve.py"
        assert result.subcommand == "prove"


class TestNumpyRoutes:
    """Test NumPy route matching."""

    # ============ NumPy Linear Algebra Routes ============

    def test_route_numpy_det(self):
        """Test routing NumPy determinant requests."""
        result = route("numpy det [[1,2],[3,4]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "det"

    def test_route_numpy_determinant(self):
        """Test routing numpy determinant keyword."""
        result = route("numpy determinant of [[1,0],[0,1]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "det"

    def test_route_numpy_inv(self):
        """Test routing NumPy inverse requests."""
        result = route("numpy inv [[1,2],[3,4]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "inv"

    def test_route_numpy_inverse(self):
        """Test routing numpy inverse keyword."""
        result = route("numpy inverse [[2,1],[1,2]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "inv"

    def test_route_numpy_pinv(self):
        """Test routing NumPy pseudo-inverse requests."""
        result = route("numpy pinv [[1,2,3],[4,5,6]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "pinv"

    def test_route_pseudo_inverse(self):
        """Test routing pseudo-inverse keyword."""
        result = route("compute pseudo-inverse of [[1,2],[3,4],[5,6]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "pinv"

    def test_route_numpy_eig(self):
        """Test routing NumPy eigenvalue requests."""
        result = route("numpy eig [[1,2],[3,4]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "eig"

    def test_route_numerical_eigenvalue(self):
        """Test routing numerical eigenvalue keyword."""
        result = route("numerical eigenvalue decomposition of [[2,1],[1,2]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "eig"

    def test_route_numpy_svd(self):
        """Test routing NumPy SVD requests."""
        result = route("numpy svd [[1,2,3],[4,5,6]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "svd"

    def test_route_singular_value_decomposition(self):
        """Test routing singular value decomposition keyword."""
        result = route("singular value decomposition of [[1,0],[0,1]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "svd"

    def test_route_numpy_solve(self):
        """Test routing NumPy linear system solve."""
        result = route("numpy solve [[3,1],[1,2]] [9,8]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "solve"

    def test_route_numpy_lstsq(self):
        """Test routing NumPy least squares."""
        result = route("numpy lstsq [[1,1],[1,2],[1,3]] [1,2,2]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "lstsq"

    def test_route_least_squares(self):
        """Test routing least squares keyword."""
        result = route("least squares fit for [[1,1],[2,1],[3,1]] [2,3,4]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "lstsq"

    def test_route_numpy_norm(self):
        """Test routing NumPy norm."""
        result = route("numpy norm [[1,2],[3,4]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "norm"

    def test_route_matrix_norm(self):
        """Test routing matrix norm keyword."""
        result = route("matrix norm of [[1,2],[3,4]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "norm"

    def test_route_numpy_cond(self):
        """Test routing NumPy condition number."""
        result = route("numpy cond [[1,2],[3,4]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "cond"

    def test_route_condition_number(self):
        """Test routing condition number keyword."""
        result = route("condition number of [[1,0],[0,1]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "cond"

    def test_route_numpy_qr(self):
        """Test routing NumPy QR decomposition."""
        result = route("numpy qr [[1,2],[3,4]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "qr"

    def test_route_qr_decomposition(self):
        """Test routing QR decomposition keyword."""
        result = route("qr decomposition of [[1,2],[3,4]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "qr"

    def test_route_numpy_cholesky(self):
        """Test routing NumPy Cholesky decomposition."""
        result = route("numpy cholesky [[4,2],[2,5]]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "cholesky"

    # ============ NumPy Statistics Routes ============

    def test_route_numpy_mean(self):
        """Test routing NumPy mean."""
        result = route("numpy mean [1,2,3,4,5]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "mean"

    def test_route_array_mean(self):
        """Test routing array mean keyword."""
        result = route("array mean of [1,2,3,4,5]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "mean"

    def test_route_numpy_std(self):
        """Test routing NumPy standard deviation."""
        result = route("numpy std [1,2,3,4,5]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "std"

    def test_route_numpy_var(self):
        """Test routing NumPy variance."""
        result = route("numpy var [1,2,3,4,5]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "var"

    def test_route_numpy_median(self):
        """Test routing NumPy median."""
        result = route("numpy median [1,2,3,4,5]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "median"

    def test_route_numpy_sum(self):
        """Test routing NumPy sum."""
        result = route("numpy sum [1,2,3,4,5]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "sum"

    def test_route_numpy_prod(self):
        """Test routing NumPy product."""
        result = route("numpy prod [1,2,3,4,5]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "prod"

    # ============ NumPy FFT Routes ============

    def test_route_numpy_fft(self):
        """Test routing NumPy FFT."""
        result = route("numpy fft [1,0,1,0]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "fft"

    def test_route_fourier_transform(self):
        """Test routing Fourier transform keyword."""
        result = route("fourier transform of [1,0,1,0,1,0,1,0]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "fft"

    def test_route_numpy_ifft(self):
        """Test routing NumPy inverse FFT."""
        result = route("numpy ifft [2,0,2,0]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "ifft"

    def test_route_inverse_fft(self):
        """Test routing inverse FFT keyword."""
        result = route("inverse fft of [2,0,2,0]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "ifft"

    def test_route_numpy_rfft(self):
        """Test routing NumPy real FFT."""
        result = route("numpy rfft [1,2,3,4]")
        assert result.script == "numpy_compute.py"
        assert result.subcommand == "rfft"


class TestScipyRoutes:
    """Test SciPy route matching."""

    # ============ SciPy Optimize Routes ============

    def test_route_scipy_minimize(self):
        """Test routing SciPy minimize."""
        result = route("scipy minimize x**2 + 2*x from 5")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "minimize"

    def test_route_numerically_minimize(self):
        """Test routing numerically minimize keyword."""
        result = route("numerically minimize x**2 starting at 3")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "minimize"

    def test_route_scipy_root(self):
        """Test routing SciPy root."""
        result = route("scipy root x**3 - x - 2 near 1.5")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "root"

    def test_route_numerical_root(self):
        """Test routing numerical root keyword."""
        result = route("numerical root of x**2 - 2 starting at 1")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "root"

    def test_route_scipy_fsolve(self):
        """Test routing SciPy fsolve."""
        result = route("scipy fsolve x**2 - 4")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "fsolve"

    def test_route_scipy_brentq(self):
        """Test routing SciPy Brent's method."""
        result = route("scipy brentq x**3 - 1")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "brentq"

    def test_route_scipy_curve_fit(self):
        """Test routing SciPy curve fit."""
        result = route("scipy curve_fit a*exp(-b*x)")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "curve_fit"

    def test_route_fit_curve(self):
        """Test routing fit curve keyword."""
        result = route("fit curve a*x**2 + b*x + c")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "curve_fit"

    def test_route_scipy_linprog(self):
        """Test routing SciPy linear programming."""
        result = route("scipy linprog -1,-2 [[1,1],[2,1]] [4,5]")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "linprog"

    def test_route_linear_programming(self):
        """Test routing linear programming keyword."""
        result = route("linear programming maximize -x - 2y")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "linprog"

    # ============ SciPy Integrate Routes ============

    def test_route_scipy_quad(self):
        """Test routing SciPy quad."""
        result = route("scipy quad x**2 from 0 to 1")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "quad"

    def test_route_numerical_integrate(self):
        """Test routing numerical integration keyword."""
        result = route("numerical integration of sin(x) from 0 to pi")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "quad"

    def test_route_scipy_dblquad(self):
        """Test routing SciPy double integration."""
        result = route("scipy dblquad x*y")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "dblquad"

    def test_route_double_integration(self):
        """Test routing double integration keyword."""
        result = route("double integration of x*y")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "dblquad"

    def test_route_scipy_odeint(self):
        """Test routing SciPy odeint."""
        result = route("scipy odeint dy/dt = -y y0=1")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "odeint"

    def test_route_solve_ode(self):
        """Test routing solve ODE keyword."""
        result = route("solve ode dy/dt = -0.5*y y0=2")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "odeint"

    def test_route_scipy_solve_ivp(self):
        """Test routing SciPy solve_ivp."""
        result = route("scipy solve_ivp dy/dt = y")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "solve_ivp"

    def test_route_initial_value_problem(self):
        """Test routing initial value problem keyword."""
        result = route("initial value problem dy/dt = -y with y(0) = 1")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "solve_ivp"

    # ============ SciPy Stats Routes ============

    def test_route_scipy_norm(self):
        """Test routing SciPy normal distribution."""
        result = route("scipy norm pdf at 0")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "norm"

    def test_route_normal_distribution(self):
        """Test routing normal distribution keyword."""
        result = route("normal distribution cdf at 1.96")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "norm"

    def test_route_scipy_t_distribution(self):
        """Test routing SciPy t-distribution."""
        result = route("scipy t-dist pdf at 0")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "t"

    def test_route_t_distribution(self):
        """Test routing t-distribution keyword."""
        result = route("t-distribution cdf at 2.0")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "t"

    def test_route_scipy_chi2(self):
        """Test routing SciPy chi-squared."""
        result = route("scipy chi2 pdf at 5")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "chi2"

    def test_route_chi_squared(self):
        """Test routing chi-squared keyword."""
        result = route("chi-squared distribution cdf at 10")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "chi2"

    def test_route_scipy_ttest(self):
        """Test routing SciPy t-test."""
        result = route("scipy ttest [1,2,3,4,5] mean=2")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "ttest_1samp"

    def test_route_t_test(self):
        """Test routing t-test keyword."""
        result = route("t-test on [1,2,3,4,5]")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "ttest_1samp"

    def test_route_scipy_kstest(self):
        """Test routing SciPy Kolmogorov-Smirnov test."""
        result = route("scipy kstest [1,2,3,4,5]")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "kstest"

    def test_route_scipy_pearsonr(self):
        """Test routing SciPy Pearson correlation."""
        result = route("scipy pearsonr [1,2,3] [4,5,6]")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "pearsonr"

    def test_route_pearson_correlation(self):
        """Test routing Pearson correlation keyword."""
        result = route("pearson correlation of [1,2,3] and [4,5,6]")
        assert result.script == "scipy_compute.py"
        assert result.subcommand == "pearsonr"


class TestMpmathRoutes:
    """Test mpmath route matching."""

    # ============ mpmath Constants Routes ============

    def test_route_mpmath_pi(self):
        """Test routing mpmath pi."""
        result = route("mpmath pi to 100 digits")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "pi"

    def test_route_arbitrary_precision_pi(self):
        """Test routing arbitrary precision pi keyword."""
        result = route("arbitrary precision pi with 50 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "pi"

    def test_route_pi_to_digits(self):
        """Test routing pi to N digits."""
        result = route("pi to 1000 digits")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "pi"

    def test_route_high_precision_pi(self):
        """Test routing high precision pi keyword."""
        result = route("high precision pi")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "pi"

    def test_route_mpmath_e(self):
        """Test routing mpmath e."""
        result = route("mpmath e to 50 digits")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "e"

    def test_route_mpmath_euler(self):
        """Test routing mpmath Euler constant."""
        result = route("mpmath euler constant")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "euler"

    def test_route_euler_mascheroni(self):
        """Test routing Euler-Mascheroni keyword."""
        result = route("euler-mascheroni constant to 30 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "euler"

    def test_route_mpmath_phi(self):
        """Test routing mpmath golden ratio."""
        result = route("mpmath phi to 100 digits")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "phi"

    def test_route_golden_ratio(self):
        """Test routing golden ratio keyword."""
        result = route("golden ratio to 50 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "phi"

    def test_route_mpmath_catalan(self):
        """Test routing mpmath Catalan constant."""
        result = route("mpmath catalan to 30 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "catalan"

    def test_route_catalan_constant(self):
        """Test routing Catalan constant keyword."""
        result = route("catalan constant to 50 digits")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "catalan"

    def test_route_mpmath_apery(self):
        """Test routing mpmath Apery constant."""
        result = route("mpmath apery constant")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "apery"

    def test_route_apery_constant(self):
        """Test routing Apery constant keyword."""
        result = route("apery constant to 30 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "apery"

    # ============ mpmath Elementary Functions Routes ============

    def test_route_mpmath_sqrt(self):
        """Test routing mpmath square root."""
        result = route("mpmath sqrt 2 to 100 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_sqrt"

    def test_route_high_precision_sqrt(self):
        """Test routing high precision sqrt keyword."""
        result = route("high precision sqrt of 2")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_sqrt"

    def test_route_mpmath_exp(self):
        """Test routing mpmath exponential."""
        result = route("mpmath exp 1 to 50 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_exp"

    def test_route_high_precision_exp(self):
        """Test routing high precision exp keyword."""
        result = route("high precision exp of 1")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_exp"

    def test_route_mpmath_log(self):
        """Test routing mpmath logarithm."""
        result = route("mpmath log 2 to 100 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_log"

    def test_route_high_precision_log(self):
        """Test routing high precision log keyword."""
        result = route("high precision log of 2")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_log"

    def test_route_mpmath_power(self):
        """Test routing mpmath power."""
        result = route("mpmath power 2 10")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_power"

    # ============ mpmath Special Functions Routes ============

    def test_route_mpmath_gamma(self):
        """Test routing mpmath gamma function."""
        result = route("mpmath gamma 5 to 50 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_gamma"

    def test_route_high_precision_gamma(self):
        """Test routing high precision gamma keyword."""
        result = route("high precision gamma of 0.5")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_gamma"

    def test_route_mpmath_factorial(self):
        """Test routing mpmath factorial."""
        result = route("mpmath factorial 100")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_factorial"

    def test_route_high_precision_factorial(self):
        """Test routing high precision factorial keyword."""
        result = route("high precision factorial of 50")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_factorial"

    def test_route_mpmath_zeta(self):
        """Test routing mpmath Riemann zeta."""
        result = route("mpmath zeta 2 to 100 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_zeta"

    def test_route_riemann_zeta(self):
        """Test routing Riemann zeta keyword."""
        result = route("riemann zeta of 2 to 50 digits")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_zeta"

    def test_route_mpmath_beta(self):
        """Test routing mpmath beta function."""
        result = route("mpmath beta 2 3")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_beta"

    def test_route_mpmath_erf(self):
        """Test routing mpmath error function."""
        result = route("mpmath erf 1")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_erf"

    def test_route_error_function(self):
        """Test routing error function keyword."""
        result = route("error function of 1 with 50 dps")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_erf"

    def test_route_mpmath_besselj(self):
        """Test routing mpmath Bessel J."""
        result = route("mpmath besselj 0 1")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_besselj"

    def test_route_bessel_j(self):
        """Test routing Bessel J keyword."""
        result = route("bessel j function")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_besselj"

    def test_route_mpmath_polylog(self):
        """Test routing mpmath polylogarithm."""
        result = route("mpmath polylog 2 0.5")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_polylog"

    def test_route_polylogarithm(self):
        """Test routing polylogarithm keyword."""
        result = route("polylogarithm of order 2 at 0.5")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_polylog"

    def test_route_mpmath_hyp2f1(self):
        """Test routing mpmath hypergeometric 2F1."""
        result = route("mpmath hyp2f1 1 2 3 0.5")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_hyp2f1"

    def test_route_hypergeometric(self):
        """Test routing hypergeometric keyword."""
        result = route("hypergeometric function 2F1")
        assert result.script == "mpmath_compute.py"
        assert result.subcommand == "mp_hyp2f1"


class TestNumpyExtractors:
    """Test NumPy argument extraction."""

    def test_extract_np_matrix_with_brackets(self):
        """Test extracting matrix from intent."""
        result = extract_np_matrix("det [[1,2],[3,4]]")
        assert result["matrix"] == "[[1,2],[3,4]]"

    def test_extract_np_matrix_default(self):
        """Test default matrix when none found."""
        result = extract_np_matrix("compute det")
        assert result["matrix"] == "[[1,0],[0,1]]"

    def test_extract_np_array_with_brackets(self):
        """Test extracting array from intent."""
        result = extract_np_array("mean of [1,2,3,4,5]")
        assert result["array"] == "[1,2,3,4,5]"

    def test_extract_np_array_default(self):
        """Test default array when none found."""
        result = extract_np_array("compute mean")
        assert result["array"] == "[1,2,3,4,5]"

    def test_extract_np_fft_with_array(self):
        """Test extracting FFT signal."""
        result = extract_np_fft("fft of [1,0,1,0]")
        assert result["signal"] == "[1,0,1,0]"


class TestScipyExtractors:
    """Test SciPy argument extraction."""

    def test_extract_scipy_minimize_func(self):
        """Test extracting minimize function."""
        result = extract_scipy_minimize("minimize x**2 + 2*x from 5")
        assert "x**2 + 2*x" in result["func"]
        assert result["x0"] == "5"

    def test_extract_scipy_minimize_method(self):
        """Test extracting minimize method."""
        result = extract_scipy_minimize("minimize x**2 method=Powell")
        assert result["method"] == "Powell"

    def test_extract_scipy_root_func(self):
        """Test extracting root function."""
        result = extract_scipy_root("root of x**3 - 2 near 1.5")
        assert "x**3 - 2" in result["func"]
        assert result["x0"] == "1.5"

    def test_extract_scipy_quad_bounds(self):
        """Test extracting quad bounds."""
        result = extract_scipy_quad("integrate x**2 from 0 to 1")
        assert "x**2" in result["func"]
        assert result["a"] == "0"
        assert result["b"] == "1"


class TestMpmathExtractors:
    """Test mpmath argument extraction."""

    def test_extract_mpmath_constant_dps(self):
        """Test extracting precision from constant request."""
        result = extract_mpmath_constant("pi to 100 digits")
        assert result["dps"] == 100

    def test_extract_mpmath_constant_default(self):
        """Test default precision for constants."""
        result = extract_mpmath_constant("compute pi")
        assert result["dps"] == 50

    def test_extract_mpmath_func_value(self):
        """Test extracting function value."""
        result = extract_mpmath_func("sqrt of 2")
        assert result["x"] == "2"

    def test_extract_mpmath_func_dps(self):
        """Test extracting function precision."""
        result = extract_mpmath_func("sqrt of 2 with precision 100")
        assert result["dps"] == 100

    def test_extract_mpmath_zeta_s(self):
        """Test extracting zeta s value."""
        result = extract_mpmath_zeta("zeta(2)")
        assert result["s"] == "2"

    def test_extract_mpmath_zeta_word_form(self):
        """Test extracting zeta s value word form."""
        result = extract_mpmath_zeta("zeta of 3")
        assert result["s"] == "3"

    def test_extract_mpmath_gamma_x(self):
        """Test extracting gamma x value."""
        result = extract_mpmath_gamma("gamma(5)")
        assert result["x"] == "5"

    def test_extract_mpmath_gamma_word_form(self):
        """Test extracting gamma x value word form."""
        result = extract_mpmath_gamma("gamma of 0.5")
        assert result["x"] == "0.5"


class TestNumpyCommandBuilding:
    """Test command building for NumPy scripts."""

    def test_build_numpy_det_command(self):
        """Test building NumPy det command."""
        cmd = build_command("numpy_compute.py", "det", {"matrix": "[[1,2],[3,4]]"})
        assert "numpy_compute.py" in cmd
        assert "det" in cmd
        assert "[[1,2],[3,4]]" in cmd

    def test_build_numpy_mean_command(self):
        """Test building NumPy mean command."""
        cmd = build_command("numpy_compute.py", "mean", {"array": "[1,2,3,4,5]"})
        assert "numpy_compute.py" in cmd
        assert "mean" in cmd
        assert "[1,2,3,4,5]" in cmd

    def test_build_numpy_fft_command(self):
        """Test building NumPy fft command."""
        cmd = build_command("numpy_compute.py", "fft", {"signal": "[1,0,1,0]"})
        assert "numpy_compute.py" in cmd
        assert "fft" in cmd
        assert "[1,0,1,0]" in cmd


class TestScipyCommandBuilding:
    """Test command building for SciPy scripts."""

    def test_build_scipy_minimize_command(self):
        """Test building SciPy minimize command."""
        cmd = build_command("scipy_compute.py", "minimize", {"func": "x**2", "x0": "5", "method": "BFGS"})
        assert "scipy_compute.py" in cmd
        assert "minimize" in cmd
        assert "x**2" in cmd

    def test_build_scipy_root_command(self):
        """Test building SciPy root command."""
        cmd = build_command("scipy_compute.py", "root", {"func": "x**3 - 2", "x0": "1"})
        assert "scipy_compute.py" in cmd
        assert "root" in cmd
        assert "x**3 - 2" in cmd

    def test_build_scipy_quad_command(self):
        """Test building SciPy quad command."""
        cmd = build_command("scipy_compute.py", "quad", {"func": "x**2", "a": "0", "b": "1"})
        assert "scipy_compute.py" in cmd
        assert "quad" in cmd
        assert "x**2" in cmd


class TestMpmathCommandBuilding:
    """Test command building for mpmath scripts."""

    def test_build_mpmath_pi_command(self):
        """Test building mpmath pi command."""
        cmd = build_command("mpmath_compute.py", "pi", {"dps": 100})
        assert "mpmath_compute.py" in cmd
        assert "pi" in cmd
        assert "--dps 100" in cmd

    def test_build_mpmath_pi_default_dps(self):
        """Test building mpmath pi command with default dps."""
        cmd = build_command("mpmath_compute.py", "pi", {"dps": 50})
        assert "mpmath_compute.py" in cmd
        assert "pi" in cmd
        assert "--dps" not in cmd  # Default dps shouldn't be added

    def test_build_mpmath_sqrt_command(self):
        """Test building mpmath sqrt command."""
        cmd = build_command("mpmath_compute.py", "mp_sqrt", {"x": "2", "dps": 100})
        assert "mpmath_compute.py" in cmd
        assert "mp_sqrt" in cmd
        assert '"2"' in cmd
        assert "--dps 100" in cmd

    def test_build_mpmath_zeta_command(self):
        """Test building mpmath zeta command."""
        cmd = build_command("mpmath_compute.py", "mp_zeta", {"s": "2", "dps": 50})
        assert "mpmath_compute.py" in cmd
        assert "mp_zeta" in cmd
        assert '"2"' in cmd

    def test_build_mpmath_gamma_command(self):
        """Test building mpmath gamma command."""
        cmd = build_command("mpmath_compute.py", "mp_gamma", {"x": "5", "dps": 100})
        assert "mpmath_compute.py" in cmd
        assert "mp_gamma" in cmd
        assert '"5"' in cmd
        assert "--dps 100" in cmd


class TestListCommandsWithNewCategories:
    """Test listing commands includes new categories."""

    def test_list_includes_numpy_category(self):
        """Test that list_commands includes numpy category."""
        result = list_commands()
        assert "numpy" in result
        assert len(result["numpy"]) > 0

    def test_list_includes_scipy_category(self):
        """Test that list_commands includes scipy category."""
        result = list_commands()
        assert "scipy" in result
        assert len(result["scipy"]) > 0

    def test_list_includes_mpmath_category(self):
        """Test that list_commands includes mpmath category."""
        result = list_commands()
        assert "mpmath" in result
        assert len(result["mpmath"]) > 0

    def test_list_numpy_commands(self):
        """Test listing only NumPy commands."""
        result = list_commands("numpy")
        assert "numpy" in result
        assert len(result) == 1
        subcommands = [cmd["subcommand"] for cmd in result["numpy"]]
        assert "det" in subcommands
        assert "inv" in subcommands
        assert "mean" in subcommands
        assert "fft" in subcommands

    def test_list_scipy_commands(self):
        """Test listing only SciPy commands."""
        result = list_commands("scipy")
        assert "scipy" in result
        assert len(result) == 1
        subcommands = [cmd["subcommand"] for cmd in result["scipy"]]
        assert "minimize" in subcommands
        assert "quad" in subcommands
        assert "norm" in subcommands

    def test_list_mpmath_commands(self):
        """Test listing only mpmath commands."""
        result = list_commands("mpmath")
        assert "mpmath" in result
        assert len(result) == 1
        subcommands = [cmd["subcommand"] for cmd in result["mpmath"]]
        assert "pi" in subcommands
        assert "mp_zeta" in subcommands
        assert "mp_gamma" in subcommands


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
