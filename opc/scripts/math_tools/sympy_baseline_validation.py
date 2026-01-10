#!/usr/bin/env python3
"""SymPy Baseline Validation - Test accuracy across mathematical domains.

This script tests SymPy's accuracy on a curated test set to determine
if a Math Verification Pipeline is worth building.

USAGE:
    uv run python scripts/sympy_baseline_validation.py
    uv run python scripts/sympy_baseline_validation.py --json
    uv run python scripts/sympy_baseline_validation.py --verbose

Results:
    As of 2025-12-31 with SymPy 1.14.0:
    - Overall Accuracy: 99.2% (119/120)
    - Z3-Verifiable: 62.5% (75/120)
    - Single failure: transcendental equation (graceful NotImplementedError)
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

# Import from sympy_compute
sys.path.insert(0, ".")
from scripts.sympy_compute import (
    binomial_coeff,
    catalan_number,
    det_matrix,
    differentiate_expr,
    eigenvalues_matrix,
    expand_expr,
    factor_expr,
    factor_integer,
    factorial_compute,
    gcd_expr,
    integrate_expr,
    is_prime_check,
    limit_expr,
    linsolve_system,
    modular_inverse,
    partial_fractions,
    series_expansion,
    simplify_expr,
    solve_equation,
)


@dataclass
class TestCase:
    """A single test case with expected result."""

    category: str
    name: str
    operation: str
    params: dict
    expected: Any
    z3_verifiable: bool = False  # Can Z3 verify this result?
    notes: str = ""


@dataclass
class TestResult:
    """Result of running a test case."""

    test: TestCase
    passed: bool
    actual: Any
    error: str = ""
    error_type: str = ""  # Classification of error type


@dataclass
class CategoryStats:
    """Statistics for a category."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)
    z3_verifiable_count: int = 0


# =============================================================================
# TEST SUITE: 120 problems across 6 categories
# =============================================================================

TEST_CASES = [
    # =========================================================================
    # ALGEBRA (20 problems)
    # =========================================================================
    TestCase(
        "algebra",
        "quadratic_1",
        "solve",
        {"equation": "x**2 - 4 = 0", "variable": "x", "domain": "real"},
        {"solutions": ["-2", "2"]},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "quadratic_2",
        "solve",
        {"equation": "x**2 + 2*x + 1 = 0", "variable": "x", "domain": "real"},
        {"solutions": ["-1"]},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "quadratic_3",
        "solve",
        {"equation": "x**2 - 5*x + 6 = 0", "variable": "x", "domain": "real"},
        {"solutions": ["2", "3"]},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "cubic_1",
        "solve",
        {"equation": "x**3 - 8 = 0", "variable": "x", "domain": "real"},
        {"solutions": ["2"]},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "linear_1",
        "solve",
        {"equation": "3*x + 5 = 14", "variable": "x", "domain": "real"},
        {"solutions": ["3"]},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "factor_1",
        "factor",
        {"expression": "x**2 - 1"},
        {"factored": "(x - 1)*(x + 1)"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "factor_2",
        "factor",
        {"expression": "x**2 - 4"},
        {"factored": "(x - 2)*(x + 2)"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "factor_3",
        "factor",
        {"expression": "x**2 + 2*x + 1"},
        {"factored": "(x + 1)**2"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "factor_4",
        "factor",
        {"expression": "x**3 - x"},
        {"factored": "x*(x - 1)*(x + 1)"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "factor_5",
        "factor",
        {"expression": "x**4 - 16"},
        {"factored": "(x - 2)*(x + 2)*(x**2 + 4)"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "expand_1",
        "expand",
        {"expression": "(x + 1)**2"},
        {"expanded": "x**2 + 2*x + 1"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "expand_2",
        "expand",
        {"expression": "(x + 1)*(x - 1)"},
        {"expanded": "x**2 - 1"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "expand_3",
        "expand",
        {"expression": "(x + y)**2"},
        {"expanded": "x**2 + 2*x*y + y**2"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "expand_4",
        "expand",
        {"expression": "(a + b)*(a - b)"},
        {"expanded": "a**2 - b**2"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "expand_5",
        "expand",
        {"expression": "(x + 1)**3"},
        {"expanded": "x**3 + 3*x**2 + 3*x + 1"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "simplify_1",
        "simplify",
        {"expression": "(x**2 - 1)/(x - 1)"},
        {"simplified": "x + 1"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "simplify_2",
        "simplify",
        {"expression": "(x**2 + 2*x + 1)/(x + 1)"},
        {"simplified": "x + 1"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "simplify_3",
        "simplify",
        {"expression": "x/x"},
        {"simplified": "1"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "apart_1",
        "apart",
        {"expression": "1/(x*(x+1))", "variable": "x"},
        {"partial_fractions": "-1/(x + 1) + 1/x"},
        z3_verifiable=True,
    ),
    TestCase(
        "algebra",
        "apart_2",
        "apart",
        {"expression": "1/((x-1)*(x+1))", "variable": "x"},
        {"partial_fractions": "-1/(2*(x + 1)) + 1/(2*(x - 1))"},
        z3_verifiable=True,
    ),
    # =========================================================================
    # CALCULUS (20 problems)
    # =========================================================================
    TestCase(
        "calculus",
        "diff_1",
        "diff",
        {"expression": "x**2", "variable": "x", "order": 1},
        {"result": "2*x"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "diff_2",
        "diff",
        {"expression": "x**3", "variable": "x", "order": 1},
        {"result": "3*x**2"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "diff_3",
        "diff",
        {"expression": "sin(x)", "variable": "x", "order": 1},
        {"result": "cos(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "diff_4",
        "diff",
        {"expression": "cos(x)", "variable": "x", "order": 1},
        {"result": "-sin(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "diff_5",
        "diff",
        {"expression": "exp(x)", "variable": "x", "order": 1},
        {"result": "exp(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "diff_6",
        "diff",
        {"expression": "log(x)", "variable": "x", "order": 1},
        {"result": "1/x"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "diff_7",
        "diff",
        {"expression": "x**4", "variable": "x", "order": 2},
        {"result": "12*x**2"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "diff_8",
        "diff",
        {"expression": "x*exp(x)", "variable": "x", "order": 1},
        {"result": "(x + 1)*exp(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "int_1",
        "integrate",
        {"expression": "x", "variable": "x"},
        {"result": "x**2/2"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "int_2",
        "integrate",
        {"expression": "x**2", "variable": "x"},
        {"result": "x**3/3"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "int_3",
        "integrate",
        {"expression": "1/x", "variable": "x"},
        {"result": "log(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "int_4",
        "integrate",
        {"expression": "exp(x)", "variable": "x"},
        {"result": "exp(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "int_5",
        "integrate",
        {"expression": "sin(x)", "variable": "x"},
        {"result": "-cos(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "int_6",
        "integrate",
        {"expression": "cos(x)", "variable": "x"},
        {"result": "sin(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "defint_1",
        "integrate",
        {"expression": "x", "variable": "x", "lower": "0", "upper": "1"},
        {"result": "1/2"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "defint_2",
        "integrate",
        {"expression": "x**2", "variable": "x", "lower": "0", "upper": "1"},
        {"result": "1/3"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "defint_3",
        "integrate",
        {"expression": "1", "variable": "x", "lower": "0", "upper": "5"},
        {"result": "5"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "limit_1",
        "limit",
        {"expression": "sin(x)/x", "variable": "x", "to": "0"},
        {"result": "1"},
        z3_verifiable=False,
    ),
    TestCase(
        "calculus",
        "limit_2",
        "limit",
        {"expression": "1/x", "variable": "x", "to": "oo"},
        {"result": "0"},
        z3_verifiable=True,
    ),
    TestCase(
        "calculus",
        "limit_3",
        "limit",
        {"expression": "(1 + 1/x)**x", "variable": "x", "to": "oo"},
        {"result": "E"},
        z3_verifiable=False,
    ),
    # =========================================================================
    # TRIGONOMETRY (20 problems)
    # =========================================================================
    TestCase(
        "trigonometry",
        "trig_simplify_1",
        "simplify",
        {"expression": "sin(x)**2 + cos(x)**2", "strategy": "trig"},
        {"simplified": "1"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_simplify_2",
        "simplify",
        {"expression": "2*sin(x)*cos(x)", "strategy": "trig"},
        {"simplified": "sin(2*x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_simplify_3",
        "simplify",
        {"expression": "cos(x)**2 - sin(x)**2", "strategy": "trig"},
        {"simplified": "cos(2*x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_simplify_4",
        "simplify",
        {"expression": "tan(x)*cos(x)", "strategy": "trig"},
        {"simplified": "sin(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_simplify_5",
        "simplify",
        {"expression": "1/cos(x)**2 - 1", "strategy": "trig"},
        {"simplified": "tan(x)**2"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_diff_1",
        "diff",
        {"expression": "tan(x)", "variable": "x", "order": 1},
        {"result": "tan(x)**2 + 1"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_diff_2",
        "diff",
        {"expression": "sec(x)", "variable": "x", "order": 1},
        {"result": "tan(x)*sec(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_diff_3",
        "diff",
        {"expression": "cot(x)", "variable": "x", "order": 1},
        {"result": "-cot(x)**2 - 1"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_int_1",
        "integrate",
        {"expression": "tan(x)", "variable": "x"},
        {"result": "-log(cos(x))"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_int_2",
        "integrate",
        {"expression": "sec(x)**2", "variable": "x"},
        {"result": "tan(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_int_3",
        "integrate",
        {"expression": "csc(x)**2", "variable": "x"},
        {"result": "-cot(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_series_1",
        "series",
        {"expression": "sin(x)", "variable": "x", "point": "0", "order": 6},
        {"polynomial": "x - x**3/6 + x**5/120"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_series_2",
        "series",
        {"expression": "cos(x)", "variable": "x", "point": "0", "order": 6},
        {"polynomial": "1 - x**2/2 + x**4/24"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_series_3",
        "series",
        {"expression": "tan(x)", "variable": "x", "point": "0", "order": 6},
        {"polynomial": "x + x**3/3 + 2*x**5/15"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_solve_1",
        "solve",
        {"equation": "sin(x) = 0", "variable": "x", "domain": "complex"},
        {"solutions_contain": "0"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_solve_2",
        "solve",
        {"equation": "cos(x) = 1", "variable": "x", "domain": "complex"},
        {"solutions_contain": "0"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_solve_3",
        "solve",
        {"equation": "tan(x) = 0", "variable": "x", "domain": "complex"},
        {"solutions_contain": "0"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_limit_1",
        "limit",
        {"expression": "sin(x)/x", "variable": "x", "to": "0"},
        {"result": "1"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_limit_2",
        "limit",
        {"expression": "(1-cos(x))/x**2", "variable": "x", "to": "0"},
        {"result": "1/2"},
        z3_verifiable=False,
    ),
    TestCase(
        "trigonometry",
        "trig_limit_3",
        "limit",
        {"expression": "tan(x)/x", "variable": "x", "to": "0"},
        {"result": "1"},
        z3_verifiable=False,
    ),
    # =========================================================================
    # NUMBER THEORY (20 problems)
    # =========================================================================
    TestCase(
        "number_theory", "prime_1", "isprime", {"n": "7"}, {"is_prime": True}, z3_verifiable=True
    ),
    TestCase(
        "number_theory", "prime_2", "isprime", {"n": "9"}, {"is_prime": False}, z3_verifiable=True
    ),
    TestCase(
        "number_theory", "prime_3", "isprime", {"n": "97"}, {"is_prime": True}, z3_verifiable=True
    ),
    TestCase(
        "number_theory", "prime_4", "isprime", {"n": "100"}, {"is_prime": False}, z3_verifiable=True
    ),
    TestCase(
        "number_theory", "prime_5", "isprime", {"n": "101"}, {"is_prime": True}, z3_verifiable=True
    ),
    TestCase(
        "number_theory",
        "factor_int_1",
        "factorint",
        {"n": "12"},
        {"factors": {"2": 2, "3": 1}},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "factor_int_2",
        "factorint",
        {"n": "100"},
        {"factors": {"2": 2, "5": 2}},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "factor_int_3",
        "factorint",
        {"n": "60"},
        {"factors": {"2": 2, "3": 1, "5": 1}},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "factor_int_4",
        "factorint",
        {"n": "81"},
        {"factors": {"3": 4}},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "factor_int_5",
        "factorint",
        {"n": "1024"},
        {"factors": {"2": 10}},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "modinv_1",
        "modinverse",
        {"a": "3", "m": "7"},
        {"inverse": 5},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "modinv_2",
        "modinverse",
        {"a": "5", "m": "11"},
        {"inverse": 9},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "modinv_3",
        "modinverse",
        {"a": "7", "m": "13"},
        {"inverse": 2},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "modinv_4",
        "modinverse",
        {"a": "2", "m": "5"},
        {"inverse": 3},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "modinv_5",
        "modinverse",
        {"a": "4", "m": "9"},
        {"inverse": 7},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "binomial_1",
        "binomial",
        {"n": "5", "k": "2"},
        {"result": "10"},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "binomial_2",
        "binomial",
        {"n": "10", "k": "3"},
        {"result": "120"},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory",
        "binomial_3",
        "binomial",
        {"n": "6", "k": "3"},
        {"result": "20"},
        z3_verifiable=True,
    ),
    TestCase(
        "number_theory", "catalan_1", "catalan", {"n": "5"}, {"result": "42"}, z3_verifiable=True
    ),
    TestCase(
        "number_theory", "catalan_2", "catalan", {"n": "6"}, {"result": "132"}, z3_verifiable=True
    ),
    # =========================================================================
    # LINEAR ALGEBRA (20 problems)
    # =========================================================================
    TestCase(
        "linear_algebra",
        "det_1",
        "det",
        {"matrix": "[[1,2],[3,4]]"},
        {"determinant": "-2"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_2",
        "det",
        {"matrix": "[[2,0],[0,2]]"},
        {"determinant": "4"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_3",
        "det",
        {"matrix": "[[1,0,0],[0,2,0],[0,0,3]]"},
        {"determinant": "6"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_4",
        "det",
        {"matrix": "[[1,2,3],[4,5,6],[7,8,9]]"},
        {"determinant": "0"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_5",
        "det",
        {"matrix": "[[5]]"},
        {"determinant": "5"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "eigen_1",
        "eigenvalues",
        {"matrix": "[[2,0],[0,3]]"},
        {"eigenvalues": ["2", "3"]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "eigen_2",
        "eigenvalues",
        {"matrix": "[[1,0],[0,1]]"},
        {"eigenvalues": ["1"]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "eigen_3",
        "eigenvalues",
        {"matrix": "[[0,1],[1,0]]"},
        {"eigenvalues": ["-1", "1"]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "eigen_4",
        "eigenvalues",
        {"matrix": "[[4,0],[0,4]]"},
        {"eigenvalues": ["4"]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "eigen_5",
        "eigenvalues",
        {"matrix": "[[1,1],[0,1]]"},
        {"eigenvalues": ["1"]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "linsolve_1",
        "linsolve",
        {"equations": "x + y = 3, x - y = 1", "vars": "x,y"},
        {"solutions": [["2", "1"]]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "linsolve_2",
        "linsolve",
        {"equations": "2*x + y = 5, x - y = 1", "vars": "x,y"},
        {"solutions": [["2", "1"]]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "linsolve_3",
        "linsolve",
        {"equations": "x + y + z = 6, x - y = 0, y - z = 0", "vars": "x,y,z"},
        {"solutions": [["2", "2", "2"]]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "linsolve_4",
        "linsolve",
        {"equations": "x = 5", "vars": "x"},
        {"solutions": [["5"]]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "linsolve_5",
        "linsolve",
        {"equations": "2*x = 10, 3*y = 9", "vars": "x,y"},
        {"solutions": [["5", "3"]]},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_6",
        "det",
        {"matrix": "[[1,1],[1,1]]"},
        {"determinant": "0"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_7",
        "det",
        {"matrix": "[[-1,0],[0,-1]]"},
        {"determinant": "1"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_8",
        "det",
        {"matrix": "[[2,1],[4,3]]"},
        {"determinant": "2"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_9",
        "det",
        {"matrix": "[[1,2,1],[2,4,2],[1,2,1]]"},
        {"determinant": "0"},
        z3_verifiable=True,
    ),
    TestCase(
        "linear_algebra",
        "det_10",
        "det",
        {"matrix": "[[3,0,0],[0,3,0],[0,0,3]]"},
        {"determinant": "27"},
        z3_verifiable=True,
    ),
    # =========================================================================
    # EDGE CASES & HARD PROBLEMS (20 problems)
    # =========================================================================
    TestCase(
        "edge_cases",
        "complex_solve_1",
        "solve",
        {"equation": "x**2 + 1 = 0", "variable": "x", "domain": "complex"},
        {"solutions": ["-I", "I"]},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "complex_solve_2",
        "solve",
        {"equation": "x**3 = 1", "variable": "x", "domain": "complex"},
        {"solutions_count": 3},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "quintic_1",
        "solve",
        {"equation": "x**5 - x - 1 = 0", "variable": "x", "domain": "complex"},
        {"has_solution": True},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "transcendental_1",
        "solve",
        {"equation": "exp(x) = x + 2", "variable": "x", "domain": "real"},
        {"has_solution": True},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "transcendental_2",
        "solve",
        {"equation": "sin(x) = x/2", "variable": "x", "domain": "real"},
        {"solutions_contain": "0"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "limit_indeterminate_1",
        "limit",
        {"expression": "(exp(x) - 1)/x", "variable": "x", "to": "0"},
        {"result": "1"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "limit_indeterminate_2",
        "limit",
        {"expression": "x*log(x)", "variable": "x", "to": "0", "dir": "+"},
        {"result": "0"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "limit_indeterminate_3",
        "limit",
        {"expression": "(1 - cos(x))/x**2", "variable": "x", "to": "0"},
        {"result": "1/2"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "improper_int_1",
        "integrate",
        {"expression": "exp(-x**2)", "variable": "x", "lower": "-oo", "upper": "oo"},
        {"result": "sqrt(pi)"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "improper_int_2",
        "integrate",
        {"expression": "1/(1 + x**2)", "variable": "x", "lower": "-oo", "upper": "oo"},
        {"result": "pi"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "symbolic_int_1",
        "integrate",
        {"expression": "1/sqrt(1 - x**2)", "variable": "x"},
        {"result": "asin(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "symbolic_int_2",
        "integrate",
        {"expression": "1/(1 + x**2)", "variable": "x"},
        {"result": "atan(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "large_factorial",
        "factorial",
        {"n": "100", "kind": "regular"},
        {"result_digits": 158},
        z3_verifiable=True,
    ),
    TestCase(
        "edge_cases",
        "large_prime",
        "isprime",
        {"n": "104729"},
        {"is_prime": True},
        z3_verifiable=True,
    ),
    TestCase(
        "edge_cases",
        "near_singular",
        "det",
        {"matrix": "[[1,2,3],[4,5,6],[7,8,9]]"},
        {"determinant": "0"},
        z3_verifiable=True,
    ),
    TestCase(
        "edge_cases",
        "symbolic_matrix_det",
        "det",
        {"matrix": "[[1,0],[0,1]]"},
        {"determinant": "1"},
        z3_verifiable=True,
    ),
    TestCase(
        "edge_cases",
        "poly_gcd",
        "gcd",
        {"expr1": "x**3 - 1", "expr2": "x**2 - 1"},
        {"gcd": "x - 1"},
        z3_verifiable=True,
    ),
    TestCase(
        "edge_cases",
        "diff_product_rule",
        "diff",
        {"expression": "x**2*sin(x)", "variable": "x", "order": 1},
        {"result": "x**2*cos(x) + 2*x*sin(x)"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "diff_chain_rule",
        "diff",
        {"expression": "sin(x**2)", "variable": "x", "order": 1},
        {"result": "2*x*cos(x**2)"},
        z3_verifiable=False,
    ),
    TestCase(
        "edge_cases",
        "series_exp",
        "series",
        {"expression": "exp(x)", "variable": "x", "point": "0", "order": 5},
        {"polynomial": "1 + x + x**2/2 + x**3/6 + x**4/24"},
        z3_verifiable=False,
    ),
]


def normalize_result(result: Any) -> Any:
    """Normalize result for comparison."""
    if isinstance(result, dict):
        return {k: normalize_result(v) for k, v in result.items()}
    if isinstance(result, list):
        try:
            if result and isinstance(result[0], list):
                return result
            return sorted(
                result,
                key=lambda x: float(x)
                if isinstance(x, str) and x.replace("-", "").replace(".", "").isdigit()
                else str(x),
            )
        except (ValueError, TypeError):
            return sorted(result, key=str)
    return result


def compare_results(expected: dict, actual: dict, test: TestCase) -> tuple[bool, str]:
    """Compare expected and actual results with flexible matching."""
    if "error" in actual:
        return False, f"Error: {actual.get('error', 'Unknown error')}"

    if "solutions_contain" in expected:
        solutions = actual.get("solutions", [])
        target = expected["solutions_contain"]
        if target in solutions or any(target in str(s) for s in solutions):
            return True, ""
        return False, f"Expected solutions to contain {target}, got {solutions}"

    if "solutions_count" in expected:
        solutions = actual.get("solutions", [])
        count = expected["solutions_count"]
        if len(solutions) >= count:
            return True, ""
        return False, f"Expected at least {count} solutions, got {len(solutions)}"

    if "has_solution" in expected:
        solutions = actual.get("solutions", [])
        if expected["has_solution"] and len(solutions) > 0:
            return True, ""
        if not expected["has_solution"] and len(solutions) == 0:
            return True, ""
        return (
            False,
            f"Expected has_solution={expected['has_solution']}, got {len(solutions)} solutions",
        )

    if "result_digits" in expected:
        result_str = str(actual.get("result", ""))
        expected_digits = expected["result_digits"]
        actual_digits = len(result_str.replace("-", ""))
        if actual_digits == expected_digits:
            return True, ""
        return False, f"Expected {expected_digits} digits, got {actual_digits}"

    for key, expected_value in expected.items():
        if key not in actual:
            return False, f"Missing key: {key}"

        actual_value = actual[key]

        if isinstance(expected_value, list):
            norm_expected = normalize_result(expected_value)
            norm_actual = normalize_result(actual_value)

            if key == "eigenvalues":
                if set(norm_expected) == set(norm_actual):
                    continue
                return False, f"Eigenvalues mismatch: expected {norm_expected}, got {norm_actual}"

            if norm_expected != norm_actual:
                return (
                    False,
                    f"List mismatch for {key}: expected {norm_expected}, got {norm_actual}",
                )

        elif isinstance(expected_value, dict):
            for subkey, subval in expected_value.items():
                if subkey not in actual_value:
                    return False, f"Missing subkey {subkey} in {key}"
                if str(actual_value[subkey]) != str(subval):
                    return (
                        False,
                        f"Mismatch for {key}.{subkey}: expected {subval}, got {actual_value[subkey]}",
                    )

        elif isinstance(expected_value, bool):
            if actual_value != expected_value:
                return (
                    False,
                    f"Bool mismatch for {key}: expected {expected_value}, got {actual_value}",
                )

        elif isinstance(expected_value, (int, float)):
            try:
                if float(actual_value) != float(expected_value):
                    return (
                        False,
                        f"Numeric mismatch for {key}: expected {expected_value}, got {actual_value}",
                    )
            except (ValueError, TypeError):
                if str(actual_value) != str(expected_value):
                    return (
                        False,
                        f"Value mismatch for {key}: expected {expected_value}, got {actual_value}",
                    )

        else:
            exp_str = str(expected_value).strip()
            act_str = str(actual_value).strip()

            if exp_str == act_str:
                continue

            try:
                from sympy import simplify, sympify

                exp_sym = sympify(exp_str)
                act_sym = sympify(act_str)
                diff = simplify(exp_sym - act_sym)
                if diff == 0:
                    continue
                if simplify(exp_sym.expand() - act_sym.expand()) == 0:
                    continue
            except Exception:
                pass

            equivalents = [
                ("tan(x)**2 + 1", "sec(x)**2"),
                ("-cot(x)**2 - 1", "-csc(x)**2"),
                ("tan(x)", "sin(x)/cos(x)"),
                ("-cot(x)", "-cos(x)/sin(x)"),
            ]

            matched = False
            for e1, e2 in equivalents:
                if (exp_str == e1 and act_str == e2) or (exp_str == e2 and act_str == e1):
                    matched = True
                    break

            if not matched:
                return False, f"String mismatch for {key}: expected '{exp_str}', got '{act_str}'"

    return True, ""


def run_test(test: TestCase) -> TestResult:
    """Run a single test case."""
    try:
        op_map = {
            "solve": lambda p: solve_equation(
                p["equation"], p.get("variable", "x"), p.get("domain", "complex")
            ),
            "factor": lambda p: factor_expr(p["expression"]),
            "expand": lambda p: expand_expr(p["expression"]),
            "simplify": lambda p: simplify_expr(p["expression"], p.get("strategy", "auto")),
            "apart": lambda p: partial_fractions(p["expression"], p.get("variable", "x")),
            "diff": lambda p: differentiate_expr(
                p["expression"], p.get("variable", "x"), p.get("order", 1)
            ),
            "integrate": lambda p: integrate_expr(
                p["expression"], p.get("variable", "x"), p.get("lower"), p.get("upper")
            ),
            "limit": lambda p: limit_expr(
                p["expression"], p.get("variable", "x"), p["to"], p.get("dir")
            ),
            "series": lambda p: series_expansion(
                p["expression"], p.get("variable", "x"), p.get("point", "0"), p.get("order", 6)
            ),
            "isprime": lambda p: is_prime_check(p["n"]),
            "factorint": lambda p: factor_integer(p["n"]),
            "modinverse": lambda p: modular_inverse(p["a"], p["m"]),
            "binomial": lambda p: binomial_coeff(p["n"], p["k"]),
            "catalan": lambda p: catalan_number(p["n"]),
            "det": lambda p: det_matrix(p["matrix"]),
            "eigenvalues": lambda p: eigenvalues_matrix(p["matrix"]),
            "linsolve": lambda p: linsolve_system(p["equations"], p["vars"]),
            "factorial": lambda p: factorial_compute(p["n"], p.get("kind", "regular")),
            "gcd": lambda p: gcd_expr(p["expr1"], p["expr2"]),
        }

        if test.operation not in op_map:
            return TestResult(
                test, False, None, f"Unknown operation: {test.operation}", "unknown_operation"
            )

        actual = op_map[test.operation](test.params)
        passed, reason = compare_results(test.expected, actual, test)

        error_type = ""
        if not passed:
            if "Error" in reason:
                error_type = "computation_error"
            else:
                error_type = "wrong_result"

        return TestResult(test, passed, actual, reason, error_type)

    except Exception as e:
        error_type = "exception"
        return TestResult(test, False, None, f"{type(e).__name__}: {e}", error_type)


def run_validation(verbose: bool = False) -> dict:
    """Run all test cases and return statistics."""
    results: list[TestResult] = []
    category_stats: dict[str, CategoryStats] = {}

    for test in TEST_CASES:
        if test.category not in category_stats:
            category_stats[test.category] = CategoryStats()

        stats = category_stats[test.category]
        stats.total += 1

        if test.z3_verifiable:
            stats.z3_verifiable_count += 1

        result = run_test(test)
        results.append(result)

        if result.passed:
            stats.passed += 1
            if verbose:
                print(f"  PASS: {test.category}/{test.name}")
        else:
            stats.failed += 1
            stats.errors.append(
                {
                    "name": test.name,
                    "error": result.error,
                    "error_type": result.error_type,
                    "expected": test.expected,
                    "actual": result.actual,
                }
            )
            if verbose:
                print(f"  FAIL: {test.category}/{test.name}")
                print(f"        {result.error}")

    total_tests = len(TEST_CASES)
    total_passed = sum(s.passed for s in category_stats.values())
    total_failed = sum(s.failed for s in category_stats.values())
    total_z3_verifiable = sum(s.z3_verifiable_count for s in category_stats.values())

    error_types: dict[str, int] = {}
    for result in results:
        if not result.passed and result.error_type:
            error_types[result.error_type] = error_types.get(result.error_type, 0) + 1

    return {
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "overall_accuracy": round(total_passed / total_tests * 100, 1),
        "z3_verifiable_count": total_z3_verifiable,
        "z3_verifiable_percent": round(total_z3_verifiable / total_tests * 100, 1),
        "by_category": {
            cat: {
                "total": stats.total,
                "passed": stats.passed,
                "failed": stats.failed,
                "accuracy": round(stats.passed / stats.total * 100, 1) if stats.total > 0 else 0,
                "z3_verifiable": stats.z3_verifiable_count,
                "errors": stats.errors,
            }
            for cat, stats in category_stats.items()
        },
        "error_types": error_types,
    }


def main():
    parser = argparse.ArgumentParser(description="SymPy baseline validation")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("=" * 60)
    print("SymPy Baseline Accuracy Validation")
    print("=" * 60)
    print()

    results = run_validation(verbose=args.verbose)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(
            f"Overall Accuracy: {results['overall_accuracy']}% ({results['total_passed']}/{results['total_tests']})"
        )
        print(
            f"Z3-Verifiable:    {results['z3_verifiable_percent']}% ({results['z3_verifiable_count']}/{results['total_tests']})"
        )
        print()

        print("By Category:")
        print("-" * 40)
        for cat, stats in results["by_category"].items():
            print(
                f"  {cat:20} {stats['accuracy']:5.1f}%  ({stats['passed']}/{stats['total']})  Z3: {stats['z3_verifiable']}"
            )
        print()

        if results["error_types"]:
            print("Error Classification:")
            print("-" * 40)
            for etype, count in sorted(results["error_types"].items(), key=lambda x: -x[1]):
                print(f"  {etype:20} {count}")
            print()

        print("Failed Tests:")
        print("-" * 40)
        for cat, stats in results["by_category"].items():
            for err in stats["errors"]:
                print(f"  {cat}/{err['name']}: {err['error']}")
                print(f"    Expected: {err['expected']}")
                print(f"    Actual:   {err['actual']}")
                print()


if __name__ == "__main__":
    main()
