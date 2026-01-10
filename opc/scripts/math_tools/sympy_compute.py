#!/usr/bin/env python3
"""Symbolic math computation script - Cognitive prosthetics for Claude.

USAGE:
    # Solve equations
    uv run python -m runtime.harness scripts/sympy_compute.py \
        solve "x**2 - 4 = 0" --var x --domain real

    # Integrate
    uv run python -m runtime.harness scripts/sympy_compute.py \
        integrate "sin(x)" --var x

    # Definite integral
    uv run python -m runtime.harness scripts/sympy_compute.py \
        integrate "x" --var x --bounds 0 1

    # Differentiate
    uv run python -m runtime.harness scripts/sympy_compute.py \
        diff "x**3" --var x --order 2

    # Simplify
    uv run python -m runtime.harness scripts/sympy_compute.py \
        simplify "sin(x)**2 + cos(x)**2" --strategy trig

    # Compute limit
    uv run python -m runtime.harness scripts/sympy_compute.py \
        limit "sin(x)/x" --var x --to 0

    # Limit at infinity
    uv run python -m runtime.harness scripts/sympy_compute.py \
        limit "1/x" --var x --to oo

    # One-sided limit (from the right)
    uv run python -m runtime.harness scripts/sympy_compute.py \
        limit "1/x" --var x --to 0 --dir +

    # Matrix determinant
    uv run python -m runtime.harness scripts/sympy_compute.py \
        det "[[1,2],[3,4]]"

    # Eigenvalues
    uv run python -m runtime.harness scripts/sympy_compute.py \
        eigenvalues "[[1,2],[3,4]]"

    # Characteristic polynomial
    uv run python -m runtime.harness scripts/sympy_compute.py \
        charpoly "[[1,2],[3,4]]" --var lambda

Requires: sympy (pip install sympy)
"""

import argparse
import asyncio
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any


def get_sympy():
    """Lazy import SymPy - only load when needed."""
    import sympy

    return sympy


def validate_expression(expr_str: str) -> tuple[bool, str]:
    """Validate expression before parsing.

    Returns:
        (valid, message)
    """
    # Check for dangerous patterns
    dangerous = ["import", "exec", "eval", "__", "open", "file"]
    for d in dangerous:
        if d in expr_str.lower():
            return False, f"Potentially dangerous pattern: {d}"

    # Check balanced parentheses
    count = 0
    for c in expr_str:
        if c == "(":
            count += 1
        elif c == ")":
            count -= 1
        if count < 0:
            return False, "Unbalanced parentheses"
    if count != 0:
        return False, "Unbalanced parentheses"

    # Check for empty expression
    if not expr_str.strip():
        return False, "Empty expression"

    return True, "Valid"


def safe_parse(expr_str: str, local_dict: dict = None) -> Any:
    """Safely parse a mathematical expression string.

    Args:
        expr_str: String like "x**2 + 2*x + 1"
        local_dict: Optional dict of predefined symbols

    Returns:
        SymPy expression

    Raises:
        ValueError: If expression cannot be parsed
    """
    sympy = get_sympy()
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    # Validate first
    valid, msg = validate_expression(expr_str)
    if not valid:
        raise ValueError(f"Cannot parse expression '{expr_str}': {msg}")

    # Default symbols
    if local_dict is None:
        local_dict = {
            "x": sympy.Symbol("x"),
            "y": sympy.Symbol("y"),
            "z": sympy.Symbol("z"),
            "n": sympy.Symbol("n", integer=True),
            "k": sympy.Symbol("k", integer=True),
        }

    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,  # Treat ^ as power, not XOR
    )

    try:
        return parse_expr(
            expr_str, local_dict=local_dict, transformations=transformations, evaluate=True
        )
    except Exception as e:
        raise ValueError(f"Cannot parse expression '{expr_str}': {e}")


def parse_matrix(matrix_str: str) -> Any:
    """Parse matrix notation into SymPy Matrix.

    Accepts:
        - "[[1,2],[3,4]]" - Python list literal (numeric)
        - "Matrix([[1,2],[3,4]])" - SymPy syntax

    Args:
        matrix_str: String representation of matrix

    Returns:
        sympy.Matrix

    Raises:
        ValueError: If matrix cannot be parsed
    """
    sympy = get_sympy()
    import ast

    # Clean up string
    matrix_str = matrix_str.strip()

    # Try Python literal first (numeric entries)
    try:
        data = ast.literal_eval(matrix_str)
        if isinstance(data, list):
            return sympy.Matrix(data)
    except (ValueError, SyntaxError):
        pass

    # Try SymPy Matrix(...) syntax
    if matrix_str.startswith("Matrix("):
        try:
            inner = matrix_str[7:-1]  # Remove Matrix( and )
            data = ast.literal_eval(inner)
            if isinstance(data, list):
                return sympy.Matrix(data)
        except (ValueError, SyntaxError):
            pass

    raise ValueError(f"Cannot parse matrix: {matrix_str}")


def _domain_assumptions(domain: str) -> dict:
    """Convert domain string to SymPy assumptions."""
    assumptions = {
        "real": {"real": True},
        "complex": {},
        "positive": {"positive": True, "real": True},
        "negative": {"negative": True, "real": True},
        "integer": {"integer": True},
        "natural": {"integer": True, "positive": True},
    }
    return assumptions.get(domain, {})


def solve_equation(equation: str, variable: str = "x", domain: str = "complex") -> dict:
    """Solve an equation for a variable.

    Args:
        equation: Either "lhs = rhs" or just "expr" (assumes = 0)
        variable: Variable to solve for
        domain: "real", "complex", "positive", "integer"

    Returns:
        {
            "solutions": [...],
            "latex": "x = ...",
            "verified": True/False
        }
    """
    sympy = get_sympy()

    # Create symbol with domain assumptions
    var = sympy.Symbol(variable, **_domain_assumptions(domain))

    # Create local dict with the variable
    local_dict = {
        variable: var,
        "x": sympy.Symbol("x", **_domain_assumptions(domain)) if variable != "x" else var,
        "y": sympy.Symbol("y"),
        "z": sympy.Symbol("z"),
    }

    # Parse equation
    if "=" in equation:
        lhs_str, rhs_str = equation.split("=", 1)
        lhs = safe_parse(lhs_str.strip(), local_dict)
        rhs = safe_parse(rhs_str.strip(), local_dict)
        expr = lhs - rhs
    else:
        expr = safe_parse(equation, local_dict)

    # Solve
    solutions = sympy.solve(expr, var, dict=False)

    # Convert to list if single solution
    if not isinstance(solutions, list):
        solutions = [solutions]

    # Filter for domain if real
    if domain == "real":
        solutions = [s for s in solutions if s.is_real]

    # Verify solutions
    verified = (
        all(sympy.simplify(expr.subs(var, sol)) == 0 for sol in solutions) if solutions else True
    )

    return {
        "solutions": [str(s) for s in solutions],
        "latex": sympy.latex(sympy.Eq(var, solutions[0])) if solutions else "No solution",
        "count": len(solutions),
        "verified": verified,
    }


def integrate_expr(
    expr_str: str, variable: str = "x", lower: str = None, upper: str = None
) -> dict:
    """Integrate an expression.

    Args:
        expr_str: Expression to integrate
        variable: Integration variable
        lower: Lower bound (for definite integral)
        upper: Upper bound (for definite integral)

    Returns:
        {
            "result": "...",
            "latex": "...",
            "definite": True/False
        }
    """
    sympy = get_sympy()

    expr = safe_parse(expr_str)
    var = sympy.Symbol(variable)

    if lower is not None and upper is not None:
        # Definite integral
        a = safe_parse(lower)
        b = safe_parse(upper)
        result = sympy.integrate(expr, (var, a, b))
        definite = True
    else:
        # Indefinite integral
        result = sympy.integrate(expr, var)
        definite = False

    # Check if integral was computed
    if result.has(sympy.Integral):
        return {
            "result": str(result),
            "latex": sympy.latex(result),
            "definite": definite,
            "computed": False,
            "note": "Integral could not be computed symbolically",
        }

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "definite": definite,
        "computed": True,
    }


def differentiate_expr(expr_str: str, variable: str = "x", order: int = 1) -> dict:
    """Differentiate an expression.

    Args:
        expr_str: Expression to differentiate
        variable: Differentiation variable
        order: Order of derivative (1, 2, 3, ...)

    Returns:
        {
            "result": "...",
            "latex": "...",
            "order": int
        }
    """
    sympy = get_sympy()

    expr = safe_parse(expr_str)
    var = sympy.Symbol(variable)

    result = sympy.diff(expr, var, order)

    return {"result": str(result), "latex": sympy.latex(result), "order": order}


def simplify_expr(expr_str: str, strategy: str = "auto") -> dict:
    """Simplify an expression using various strategies.

    Args:
        expr_str: Expression to simplify
        strategy: "auto", "trig", "rational", "radicals", "expand", "factor", "all"

    Returns:
        Simplified expression with comparison
    """
    sympy = get_sympy()

    expr = safe_parse(expr_str)

    strategies = {
        "auto": sympy.simplify,
        "trig": sympy.trigsimp,
        "rational": sympy.ratsimp,
        "radicals": sympy.radsimp,
        "expand": sympy.expand,
        "factor": sympy.factor,
        "collect": lambda e: sympy.collect(e, sympy.Symbol("x")),
    }

    if strategy == "all":
        results = {}
        for name, func in strategies.items():
            if name != "all":
                try:
                    results[name] = str(func(expr))
                except Exception:
                    results[name] = "N/A"
        return {"strategies": results, "original": str(expr)}

    func = strategies.get(strategy, sympy.simplify)
    simplified = func(expr)

    # Verify equivalence
    diff = sympy.simplify(expr - simplified)
    equivalent = diff == 0

    return {
        "original": str(expr),
        "simplified": str(simplified),
        "latex": sympy.latex(simplified),
        "equivalent": equivalent,
        "simpler": len(str(simplified)) < len(str(expr)),
    }


def limit_expr(expr_str: str, variable: str = "x", to: str = "0", direction: str = None) -> dict:
    """Compute limit of expression.

    Args:
        expr_str: Expression to take limit of
        variable: Limit variable
        to: Value to approach ("oo", "-oo", "0", "1", etc.)
        direction: "+" (from right) or "-" (from left), None for two-sided

    Returns:
        {
            "result": "...",
            "latex": "...",
            "expression": "...",
            "variable": "...",
            "point": "...",
            "direction": "+" | "-" | None,
            "exists": True/False
        }
    """
    sympy = get_sympy()

    expr = safe_parse(expr_str)
    var = sympy.Symbol(variable)

    # Parse limit point
    to_lower = to.lower() if isinstance(to, str) else str(to)
    if to_lower in ("oo", "inf", "infinity"):
        point = sympy.oo
    elif to_lower in ("-oo", "-inf", "-infinity"):
        point = -sympy.oo
    else:
        point = safe_parse(to)

    # Normalize direction
    dir_map = {"+": "+", "right": "+", "-": "-", "left": "-"}
    normalized_dir = dir_map.get(direction, direction) if direction else None

    # Compute limit
    if normalized_dir:
        result = sympy.limit(expr, var, point, normalized_dir)
    else:
        result = sympy.limit(expr, var, point)

    # Determine if limit exists (not nan, not unevaluated Limit)
    exists = result != sympy.nan and not result.has(sympy.Limit) and result.is_finite is not False

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "expression": str(expr),
        "variable": variable,
        "point": str(point),
        "direction": normalized_dir,
        "exists": exists,
    }


def det_matrix(matrix_str: str) -> dict:
    """Compute determinant of a matrix.

    Args:
        matrix_str: Matrix as "[[a,b],[c,d]]"

    Returns:
        {
            "determinant": "...",
            "latex": "...",
            "is_singular": True/False,
            "matrix_size": "NxM"
        }
    """
    sympy = get_sympy()

    M = parse_matrix(matrix_str)
    det = M.det()

    return {
        "determinant": str(det),
        "latex": sympy.latex(det),
        "is_singular": det == 0,
        "matrix_size": f"{M.rows}x{M.cols}",
    }


def eigenvalues_matrix(matrix_str: str) -> dict:
    """Compute eigenvalues of a matrix.

    Args:
        matrix_str: Matrix as "[[a,b],[c,d]]"

    Returns:
        {
            "eigenvalues": ["val1", "val2", ...],
            "multiplicities": {"val1": mult1, ...},
            "latex": "...",
            "matrix_size": "NxM"
        }
    """
    sympy = get_sympy()

    M = parse_matrix(matrix_str)
    eigenvals = M.eigenvals()  # Returns {eigenvalue: multiplicity}

    return {
        "eigenvalues": [str(ev) for ev in eigenvals.keys()],
        "multiplicities": {str(ev): mult for ev, mult in eigenvals.items()},
        "latex": sympy.latex(list(eigenvals.keys())),
        "matrix_size": f"{M.rows}x{M.cols}",
    }


def charpoly_matrix(matrix_str: str, variable: str = "lambda") -> dict:
    """Compute characteristic polynomial of a matrix.

    Args:
        matrix_str: Matrix as "[[a,b],[c,d]]"
        variable: Polynomial variable (default: lambda)

    Returns:
        {
            "polynomial": "...",
            "latex": "...",
            "degree": int,
            "matrix_size": "NxM"
        }
    """
    sympy = get_sympy()

    M = parse_matrix(matrix_str)
    var = sympy.Symbol(variable)
    cp = M.charpoly(var)
    poly = cp.as_expr()

    return {
        "polynomial": str(poly),
        "latex": sympy.latex(poly),
        "degree": M.rows,
        "matrix_size": f"{M.rows}x{M.cols}",
    }


def eigenvectors_matrix(matrix_str: str) -> dict:
    """Compute eigenvectors of a matrix.

    Args:
        matrix_str: Matrix as "[[a,b],[c,d]]"

    Returns:
        {
            "eigenvectors": [["vec1_str", ...], ...],
            "eigenvalues": ["val1", "val2", ...],
            "multiplicities": {"val": {"algebraic": n, "geometric": m}, ...},
            "latex": "...",
            "matrix_size": "NxM"
        }
    """
    sympy = get_sympy()

    M = parse_matrix(matrix_str)
    # eigenvects() returns [(eigenvalue, algebraic_mult, [eigenvectors]), ...]
    evects = M.eigenvects()

    eigenvectors = []
    eigenvalues = []
    multiplicities = {}

    for eigenval, alg_mult, vecs in evects:
        ev_str = str(eigenval)
        eigenvalues.append(ev_str)
        multiplicities[ev_str] = {"algebraic": alg_mult, "geometric": len(vecs)}
        for v in vecs:
            eigenvectors.append([str(c) for c in v])

    return {
        "eigenvectors": eigenvectors,
        "eigenvalues": eigenvalues,
        "multiplicities": multiplicities,
        "latex": sympy.latex(evects),
        "matrix_size": f"{M.rows}x{M.cols}",
    }


def inverse_matrix(matrix_str: str) -> dict:
    """Compute inverse of a matrix.

    Args:
        matrix_str: Matrix as "[[a,b],[c,d]]"

    Returns:
        {
            "inverse": "[[...],[...]]",
            "determinant": "...",
            "latex": "...",
            "matrix_size": "NxM"
        }
        Or {"error": "..."} if singular.
    """
    sympy = get_sympy()

    M = parse_matrix(matrix_str)
    det = M.det()

    if det == 0:
        return {
            "error": "Matrix is singular (determinant = 0)",
            "determinant": "0",
            "matrix_size": f"{M.rows}x{M.cols}",
        }

    M_inv = M.inv()
    # Convert to list format
    inv_list = [[str(M_inv[i, j]) for j in range(M_inv.cols)] for i in range(M_inv.rows)]

    return {
        "inverse": str(inv_list),
        "determinant": str(det),
        "latex": sympy.latex(M_inv),
        "matrix_size": f"{M.rows}x{M.cols}",
    }


def transpose_matrix(matrix_str: str) -> dict:
    """Compute transpose of a matrix.

    Args:
        matrix_str: Matrix as "[[a,b],[c,d]]"

    Returns:
        {
            "transpose": "[[...],[...]]",
            "latex": "...",
            "original_size": "NxM",
            "transpose_size": "MxN"
        }
    """
    sympy = get_sympy()

    M = parse_matrix(matrix_str)
    M_T = M.T
    # Convert to list format
    trans_list = [[str(M_T[i, j]) for j in range(M_T.cols)] for i in range(M_T.rows)]

    return {
        "transpose": str(trans_list),
        "latex": sympy.latex(M_T),
        "original_size": f"{M.rows}x{M.cols}",
        "transpose_size": f"{M_T.rows}x{M_T.cols}",
    }


# ============================================================================
# ============================================================================
# Linear Algebra Functions (linsolve, nullspace, rref, rank)
# ============================================================================


def linsolve_system(equations_str: str, vars_str: str) -> dict:
    """Solve a system of linear equations.

    Uses SymPy's linsolve function for efficient linear system solving.

    Args:
        equations_str: Comma-separated equations (e.g., "x + y - 1, x - y - 3")
                      Supports both "expr" (assumes = 0) and "lhs = rhs" formats
        vars_str: Comma-separated variable names (e.g., "x,y")

    Returns:
        {
            "solutions": [["2", "-1"]] or [] for no solution,
            "variables": ["x", "y"],
            "is_consistent": True/False,
            "is_unique": True/False,
            "latex": "..."
        }
    """
    sympy = get_sympy()
    from sympy import EmptySet, linsolve

    # Parse variables
    var_names = [v.strip() for v in vars_str.split(",")]
    symbols = [sympy.Symbol(name) for name in var_names]
    local_dict = {name: sym for name, sym in zip(var_names, symbols)}

    # Parse equations
    eq_strs = [eq.strip() for eq in equations_str.split(",")]
    exprs = []

    for eq_str in eq_strs:
        if "=" in eq_str:
            # lhs = rhs format
            lhs_str, rhs_str = eq_str.split("=", 1)
            lhs = safe_parse(lhs_str.strip(), local_dict)
            rhs = safe_parse(rhs_str.strip(), local_dict)
            exprs.append(lhs - rhs)
        else:
            # expr = 0 format
            exprs.append(safe_parse(eq_str, local_dict))

    # Solve using linsolve
    solution_set = linsolve(exprs, *symbols)

    # Process results
    if solution_set == EmptySet or len(solution_set) == 0:
        return {
            "solutions": [],
            "variables": var_names,
            "is_consistent": False,
            "is_unique": False,
            "latex": "\\emptyset",
        }

    # Convert FiniteSet to list
    solutions = []
    for sol in solution_set:
        solutions.append([str(s) for s in sol])

    # Check if solution is unique (no free variables)
    # If solution contains any of the original variables, it's parametric
    first_sol = list(solution_set)[0]
    has_free_vars = any(any(sym in expr.free_symbols for sym in symbols) for expr in first_sol)

    return {
        "solutions": solutions,
        "variables": var_names,
        "is_consistent": True,
        "is_unique": not has_free_vars,
        "latex": sympy.latex(solution_set),
    }


def nullspace_matrix(matrix_str: str) -> dict:
    """Compute the null space (kernel) of a matrix.

    Returns basis vectors spanning ker(A) = {x : Ax = 0}.

    Args:
        matrix_str: Matrix as "[[a,b,...],...]"

    Returns:
        {
            "nullspace": [["1", "-2", "1"], ...],  # Basis vectors as lists
            "dimension": int,  # Dimension of null space (nullity)
            "latex": "...",
            "matrix_size": "NxM"
        }
    """
    sympy = get_sympy()

    M = parse_matrix(matrix_str)
    ns = M.nullspace()

    # Convert each basis vector to list format
    nullspace_vecs = []
    for vec in ns:
        nullspace_vecs.append([str(vec[i, 0]) for i in range(vec.rows)])

    return {
        "nullspace": nullspace_vecs,
        "dimension": len(ns),
        "latex": sympy.latex(ns) if ns else "\\{\\}",
        "matrix_size": f"{M.rows}x{M.cols}",
    }


def rref_matrix(matrix_str: str) -> dict:
    """Compute the Reduced Row Echelon Form (RREF) of a matrix.

    Args:
        matrix_str: Matrix as "[[a,b,...],...]"

    Returns:
        {
            "rref": "[[1, 0, ...], [0, 1, ...], ...]",  # RREF as list
            "pivots": [0, 1, ...],  # Pivot column indices
            "rank": int,  # Rank = number of pivots
            "latex": "...",
            "matrix_size": "NxM"
        }
    """
    sympy = get_sympy()

    M = parse_matrix(matrix_str)
    rref_M, pivot_cols = M.rref()

    # Convert to list format
    rref_list = [[str(rref_M[i, j]) for j in range(rref_M.cols)] for i in range(rref_M.rows)]

    return {
        "rref": str(rref_list),
        "pivots": list(pivot_cols),
        "rank": len(pivot_cols),
        "latex": sympy.latex(rref_M),
        "matrix_size": f"{M.rows}x{M.cols}",
    }


def rank_matrix(matrix_str: str) -> dict:
    """Compute the rank of a matrix.

    Rank = number of linearly independent rows/columns.

    Args:
        matrix_str: Matrix as "[[a,b,...],...]"

    Returns:
        {
            "rank": int,
            "nullity": int,  # nullity = cols - rank
            "is_full_rank": True/False,
            "matrix_size": "NxM"
        }
    """
    M = parse_matrix(matrix_str)
    r = M.rank()

    return {
        "rank": r,
        "nullity": M.cols - r,
        "is_full_rank": r == min(M.rows, M.cols),
        "matrix_size": f"{M.rows}x{M.cols}",
    }


# ============================================================================
# Algebra Functions (factor, expand, apart, gcd, lcm)
# ============================================================================


def factor_expr(expr_str: str) -> dict:
    """Factor a polynomial expression.

    Uses SymPy's factor function.

    Args:
        expr_str: Polynomial expression to factor (e.g., "x**2 - 1")

    Returns:
        {
            "factored": "(x - 1)*(x + 1)",
            "original": "x**2 - 1",
            "latex": "..."
        }
    """
    sympy = get_sympy()

    expr = safe_parse(expr_str)
    factored = sympy.factor(expr)

    return {"factored": str(factored), "original": str(expr), "latex": sympy.latex(factored)}


def expand_expr(expr_str: str) -> dict:
    """Expand a polynomial expression.

    Uses SymPy's expand function.

    Args:
        expr_str: Expression to expand (e.g., "(x + 1)**2")

    Returns:
        {
            "expanded": "x**2 + 2*x + 1",
            "original": "(x + 1)**2",
            "latex": "..."
        }
    """
    sympy = get_sympy()

    expr = safe_parse(expr_str)
    expanded = sympy.expand(expr)

    return {"expanded": str(expanded), "original": str(expr), "latex": sympy.latex(expanded)}


def partial_fractions(expr_str: str, variable: str = "x") -> dict:
    """Perform partial fraction decomposition.

    Uses SymPy's apart function.

    Args:
        expr_str: Rational function to decompose (e.g., "1/(x*(x+1))")
        variable: Variable for decomposition

    Returns:
        {
            "partial_fractions": "1/x - 1/(x + 1)",
            "original": "1/(x*(x + 1))",
            "latex": "..."
        }
    """
    sympy = get_sympy()

    expr = safe_parse(expr_str)
    var = sympy.Symbol(variable)
    result = sympy.apart(expr, var)

    return {"partial_fractions": str(result), "original": str(expr), "latex": sympy.latex(result)}


def gcd_expr(expr1_str: str, expr2_str: str) -> dict:
    """Compute greatest common divisor of two expressions.

    Works for both integers and polynomials.

    Args:
        expr1_str: First expression (integer or polynomial)
        expr2_str: Second expression (integer or polynomial)

    Returns:
        {
            "gcd": "x - 1",
            "expr1": "x**2 - 1",
            "expr2": "x - 1",
            "latex": "..."
        }
    """
    sympy = get_sympy()

    expr1 = safe_parse(expr1_str)
    expr2 = safe_parse(expr2_str)
    result = sympy.gcd(expr1, expr2)

    return {
        "gcd": str(result),
        "expr1": str(expr1),
        "expr2": str(expr2),
        "latex": sympy.latex(result),
    }


def lcm_expr(expr1_str: str, expr2_str: str) -> dict:
    """Compute least common multiple of two expressions.

    Works for both integers and polynomials.

    Args:
        expr1_str: First expression (integer or polynomial)
        expr2_str: Second expression (integer or polynomial)

    Returns:
        {
            "lcm": "x**2 - 1",
            "expr1": "x**2 - 1",
            "expr2": "x - 1",
            "latex": "..."
        }
    """
    sympy = get_sympy()

    expr1 = safe_parse(expr1_str)
    expr2 = safe_parse(expr2_str)
    result = sympy.lcm(expr1, expr2)

    return {
        "lcm": str(result),
        "expr1": str(expr1),
        "expr2": str(expr2),
        "latex": sympy.latex(result),
    }


# ============================================================================
# Number Theory Functions
# ============================================================================


def factor_integer(n_str: str) -> dict:
    """Factor an integer into prime factors.

    Uses SymPy's factorint which returns {prime: exponent} dict.

    Args:
        n_str: Integer to factor as string

    Returns:
        {
            "factors": {"prime": exponent, ...},
            "n": "original number",
            "latex": "2^3 * 3^2 * 5"
        }
    """
    get_sympy()
    from sympy import Integer, Mul, Pow, factorint, latex

    n = int(n_str)
    factors = factorint(n)

    # Build LaTeX representation: 2^3 * 3^2 * 5
    if factors:
        terms = []
        for prime, exp in sorted(factors.items()):
            if exp == 1:
                terms.append(Integer(prime))
            else:
                terms.append(Pow(Integer(prime), Integer(exp)))
        expr = Mul(*terms) if len(terms) > 1 else terms[0]
        latex_str = latex(expr)
    else:
        latex_str = str(n)

    return {"factors": {str(p): e for p, e in factors.items()}, "n": n_str, "latex": latex_str}


def is_prime_check(n_str: str) -> dict:
    """Check if an integer is prime.

    Uses SymPy's isprime function.

    Args:
        n_str: Integer to check as string

    Returns:
        {
            "is_prime": True/False,
            "n": "original number"
        }
    """
    get_sympy()
    from sympy import isprime

    n = int(n_str)
    is_p = isprime(n)

    return {"is_prime": is_p, "n": n_str}


def modular_inverse(a_str: str, m_str: str) -> dict:
    """Compute modular multiplicative inverse.

    Finds x such that a*x ≡ 1 (mod m).
    Uses SymPy's mod_inverse function.

    Args:
        a_str: Integer a as string
        m_str: Modulus m as string

    Returns:
        {
            "inverse": int or None,
            "a": "a",
            "m": "m",
            "verified": True/False
        }
        Or {"error": "..."} if inverse doesn't exist.
    """
    get_sympy()
    from sympy import gcd, mod_inverse

    a = int(a_str)
    m = int(m_str)

    # Check if inverse exists (gcd must be 1)
    if gcd(a, m) != 1:
        return {
            "error": f"No modular inverse exists: gcd({a}, {m}) != 1",
            "inverse": None,
            "a": a_str,
            "m": m_str,
        }

    inv = mod_inverse(a, m)

    # Verify: a * inv ≡ 1 (mod m)
    verified = (a * inv) % m == 1

    return {"inverse": int(inv), "a": a_str, "m": m_str, "verified": verified}


# ============================================================================
# Combinatorics Functions
# ============================================================================


def binomial_coeff(n_str: str, k_str: str) -> dict:
    """Compute binomial coefficient C(n, k) = n! / (k! * (n-k)!).

    Args:
        n_str: Upper value (integer or expression)
        k_str: Lower value (integer or expression)

    Returns:
        {"result": "...", "latex": "...", "n": n, "k": k}
    """
    sympy = get_sympy()
    n = safe_parse(n_str)
    k = safe_parse(k_str)
    result = sympy.binomial(n, k)

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "n": n_str,
        "k": k_str,
    }


def factorial_compute(n_str: str, kind: str = "regular") -> dict:
    """Compute factorial variants.

    Args:
        n_str: Non-negative integer
        kind: "regular" (n!), "double" (n!!), "subfactorial" (!n)

    Returns:
        {"result": "...", "latex": "...", "n": "...", "kind": "..."}
    """
    sympy = get_sympy()
    n = int(n_str)

    if kind == "regular":
        result = sympy.factorial(n)
    elif kind == "double":
        result = sympy.factorial2(n)
    elif kind == "subfactorial":
        result = sympy.subfactorial(n)
    else:
        raise ValueError(f"Unknown factorial kind: {kind}")

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "n": n_str,
        "kind": kind,
    }


def permutation_count(n_str: str, k_str: str) -> dict:
    """Compute P(n, k) - number of k-permutations of n elements.

    Formula: P(n,k) = n! / (n-k)!

    Args:
        n_str: Total elements
        k_str: Elements to arrange

    Returns:
        {"result": "...", "latex": "...", "n": "...", "k": "..."}
    """
    from sympy.functions.combinatorial.numbers import nP

    sympy = get_sympy()
    n = int(n_str)
    k = int(k_str)
    result = nP(n, k)

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "n": n_str,
        "k": k_str,
    }


def partition_count(n_str: str) -> dict:
    """Compute partition number p(n) - ways to write n as sum of positive integers.

    Args:
        n_str: Non-negative integer

    Returns:
        {"result": "...", "latex": "...", "n": "..."}
    """
    sympy = get_sympy()
    n = int(n_str)
    result = sympy.partition(n)

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "n": n_str,
    }


def catalan_number(n_str: str) -> dict:
    """Compute nth Catalan number.

    Formula: C_n = binomial(2n, n) / (n + 1)

    Args:
        n_str: Non-negative integer index

    Returns:
        {"result": "...", "latex": "...", "n": "..."}
    """
    sympy = get_sympy()
    n = int(n_str)
    result = sympy.catalan(n)

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "n": n_str,
    }


def bell_number(n_str: str) -> dict:
    """Compute nth Bell number - number of set partitions.

    Args:
        n_str: Non-negative integer index

    Returns:
        {"result": "...", "latex": "...", "n": "..."}
    """
    sympy = get_sympy()
    n = int(n_str)
    result = sympy.bell(n)

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "n": n_str,
    }


# ============================================================================
# Calculus Functions (series, dsolve, laplace_transform)
# ============================================================================


def series_expansion(expr_str: str, variable: str = "x", point: str = "0", order: int = 6) -> dict:
    """Compute Taylor/Maclaurin series expansion.

    Args:
        expr_str: Expression to expand (e.g., "sin(x)")
        variable: Variable to expand around
        point: Point to expand around (default: 0 for Maclaurin)
        order: Order of expansion (terms up to O(x^n))

    Returns:
        {
            "series": "x - x**3/6 + x**5/120 + O(x**6)",
            "polynomial": "x - x**3/6 + x**5/120",
            "point": "0",
            "order": 6,
            "latex": "..."
        }
    """
    sympy = get_sympy()

    expr = safe_parse(expr_str)
    var = sympy.Symbol(variable)

    # Parse expansion point
    if point.lower() in ("oo", "inf", "infinity"):
        x0 = sympy.oo
    elif point.lower() in ("-oo", "-inf", "-infinity"):
        x0 = -sympy.oo
    else:
        x0 = safe_parse(point)

    # Compute series
    series_result = sympy.series(expr, var, x0, order)

    # Get polynomial form (without O term)
    polynomial = series_result.removeO()

    return {
        "series": str(series_result),
        "polynomial": str(polynomial),
        "point": point,
        "order": order,
        "latex": sympy.latex(series_result),
        "expression": str(expr),
        "variable": variable,
    }


def solve_ode(equation_str: str, func_str: str = "f(x)", ics: str = None) -> dict:
    """Solve ordinary differential equations.

    Args:
        equation_str: ODE expression (set equal to 0)
            e.g., "Derivative(f(x), x) - f(x)" means f'(x) = f(x)
        func_str: Dependent variable and independent var, e.g., "f(x)"
        ics: Initial conditions as string, e.g., "f(0)=1" or "f(0)=1,f'(0)=0"

    Returns:
        {
            "solution": "f(x) = C1*exp(x)",
            "order": 1,
            "latex": "...",
            "general": True/False
        }
    """
    import re

    from sympy import Derivative, Eq, Function, dsolve

    sympy = get_sympy()
    # Parse function and variable
    # func_str should be like "f(x)" - extract f and x
    match = re.match(r"(\w+)\((\w+)\)", func_str)
    if not match:
        raise ValueError(f"Cannot parse function: {func_str}. Expected format like 'f(x)'")

    func_name, var_name = match.groups()
    var = sympy.Symbol(var_name)
    f = Function(func_name)

    # Build local dict for parsing
    local_dict = {
        var_name: var,
        func_name: f,
        "Derivative": Derivative,
    }

    # Parse the ODE expression
    expr = safe_parse(equation_str, local_dict)

    # Determine the order by finding highest derivative
    order = 0
    for term in sympy.preorder_traversal(expr):
        if isinstance(term, Derivative):
            # Get derivative order from variables tuple
            d_vars = term.variables
            order = max(order, len(d_vars))

    # Parse initial conditions if provided
    ics_dict = None
    if ics:
        ics_dict = {}
        # Parse "f(0)=1" or "f(0)=1,f'(0)=0"
        for ic in ics.split(","):
            ic = ic.strip()
            if "=" in ic:
                lhs, rhs = ic.split("=", 1)
                lhs = lhs.strip()
                rhs_val = safe_parse(rhs.strip())

                # Handle f(0) or f'(0)
                if "'" in lhs:
                    # Derivative condition like f'(0)
                    deriv_match = re.match(r"(\w+)'*\((.+)\)", lhs)
                    if deriv_match:
                        num_primes = lhs.count("'")
                        pt = safe_parse(deriv_match.group(2))
                        deriv_expr = f(var).diff(var, num_primes).subs(var, pt)
                        ics_dict[deriv_expr] = rhs_val
                else:
                    # Function value like f(0)
                    pt_match = re.match(r"(\w+)\((.+)\)", lhs)
                    if pt_match:
                        pt = safe_parse(pt_match.group(2))
                        ics_dict[f(pt)] = rhs_val

    # Solve the ODE
    eq = Eq(expr, 0)
    if ics_dict:
        solution = dsolve(eq, f(var), ics=ics_dict)
    else:
        solution = dsolve(eq, f(var))

    # Determine if general solution (has C1, C2, etc.)
    sol_str = str(solution)
    general = "C1" in sol_str or "C2" in sol_str

    return {
        "solution": str(solution.rhs) if hasattr(solution, "rhs") else str(solution),
        "equation": str(solution) if hasattr(solution, "rhs") else str(solution),
        "order": max(order, 1),  # At least 1st order
        "latex": sympy.latex(solution),
        "general": general,
    }


def laplace_transform_expr(expr_str: str, t_var: str = "t", s_var: str = "s") -> dict:
    """Compute Laplace transform.

    Args:
        expr_str: Function of t to transform (e.g., "exp(-t)")
        t_var: Time domain variable (default: t)
        s_var: Frequency domain variable (default: s)

    Returns:
        {
            "transform": "1/(s + 1)",
            "convergence": "re(s) > -1",
            "latex": "...",
            "original": "exp(-t)"
        }
    """
    sympy = get_sympy()
    from sympy import laplace_transform

    # Create symbols
    t = sympy.Symbol(t_var, positive=True)
    s = sympy.Symbol(s_var)

    # Build local dict
    local_dict = {
        t_var: t,
        s_var: s,
        "x": sympy.Symbol("x"),
    }

    # Parse the expression
    expr = safe_parse(expr_str, local_dict)

    # Compute Laplace transform
    # Returns (F(s), a, cond) where a is convergence abscissa and cond is condition
    result = laplace_transform(expr, t, s)

    # Handle tuple result
    if isinstance(result, tuple):
        transform, abscissa, condition = result
    else:
        transform = result
        abscissa = None
        condition = True

    return {
        "transform": str(transform),
        "convergence": str(abscissa) if abscissa is not None else "0",
        "condition": str(condition),
        "latex": sympy.latex(transform),
        "original": str(expr),
        "t_var": t_var,
        "s_var": s_var,
    }


def _solve_internal(equation: str, var: str, domain: str) -> dict:
    """Internal solve function for process pool execution.

    This function runs in a separate process to enable timeout control.
    """
    return solve_equation(equation, var, domain)


def safe_solve(equation: str, var: str = "x", domain: str = "complex", timeout: int = 30) -> dict:
    """Solve with timeout protection.

    Uses ProcessPoolExecutor to run solve in a separate process,
    allowing true timeout enforcement even for blocking computations.

    Args:
        equation: Equation to solve (e.g., "x**2 - 4 = 0")
        var: Variable to solve for
        domain: "real", "complex", "positive", "integer"
        timeout: Maximum seconds to wait for solution

    Returns:
        dict with solutions on success, or error dict on failure/timeout
    """
    try:
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_solve_internal, equation, var, domain)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeout:
                return {
                    "success": False,
                    "error": f"Timeout after {timeout}s - computation too complex",
                }
    except Exception as e:
        return {"success": False, "error": "computation_error", "message": str(e)}


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Symbolic math computation - cognitive prosthetics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Solve command
    solve_p = subparsers.add_parser("solve", help="Solve equations")
    solve_p.add_argument("expression", help="Equation to solve (e.g., 'x**2 - 4 = 0')")
    solve_p.add_argument("--var", default="x", help="Variable to solve for")
    solve_p.add_argument(
        "--domain", default="complex", choices=["real", "complex", "positive", "integer"]
    )

    # Integrate command
    integrate_p = subparsers.add_parser("integrate", help="Integrate expressions")
    integrate_p.add_argument("expression", help="Expression to integrate")
    integrate_p.add_argument("--var", default="x", help="Integration variable")
    integrate_p.add_argument(
        "--bounds", nargs=2, metavar=("LOWER", "UPPER"), help="Bounds for definite integral"
    )

    # Differentiate command
    diff_p = subparsers.add_parser("diff", help="Differentiate expressions")
    diff_p.add_argument("expression", help="Expression to differentiate")
    diff_p.add_argument("--var", default="x", help="Differentiation variable")
    diff_p.add_argument("--order", type=int, default=1, help="Order of derivative")

    # Simplify command
    simplify_p = subparsers.add_parser("simplify", help="Simplify expressions")
    simplify_p.add_argument("expression", help="Expression to simplify")
    simplify_p.add_argument(
        "--strategy",
        default="auto",
        choices=["auto", "trig", "rational", "expand", "factor", "all"],
    )

    # Limit command
    limit_p = subparsers.add_parser("limit", help="Compute limits")
    limit_p.add_argument("expression", help="Expression to take limit of")
    limit_p.add_argument("--var", default="x", help="Limit variable")
    limit_p.add_argument("--to", required=True, help="Value to approach (e.g., 'oo', '0', '1')")
    limit_p.add_argument(
        "--dir", default=None, choices=["+", "-"], help="Direction (+ from right, - from left)"
    )

    # Determinant command
    det_p = subparsers.add_parser("det", help="Compute matrix determinant")
    det_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")

    # Eigenvalues command
    eigen_p = subparsers.add_parser("eigenvalues", help="Compute eigenvalues")
    eigen_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")

    # Characteristic polynomial command
    charpoly_p = subparsers.add_parser("charpoly", help="Characteristic polynomial")
    charpoly_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")
    charpoly_p.add_argument("--var", default="lambda", help="Polynomial variable")

    # Eigenvectors command
    eigenvects_p = subparsers.add_parser("eigenvectors", help="Compute eigenvectors")
    eigenvects_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")

    # Inverse command
    inverse_p = subparsers.add_parser("inverse", help="Compute matrix inverse")
    inverse_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")

    # Transpose command
    transpose_p = subparsers.add_parser("transpose", help="Compute matrix transpose")
    transpose_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")

    # Linear Algebra commands
    # Linsolve command
    linsolve_p = subparsers.add_parser("linsolve", help="Solve system of linear equations")
    linsolve_p.add_argument(
        "equations", help="Comma-separated equations (e.g., 'x + y - 1, x - y - 3')"
    )
    linsolve_p.add_argument("--vars", required=True, help="Comma-separated variables (e.g., 'x,y')")

    # Nullspace command
    nullspace_p = subparsers.add_parser("nullspace", help="Compute matrix null space")
    nullspace_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")

    # RREF command
    rref_p = subparsers.add_parser("rref", help="Compute reduced row echelon form")
    rref_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")

    # Rank command
    rank_p = subparsers.add_parser("rank", help="Compute matrix rank")
    rank_p.add_argument("matrix", help="Matrix as [[a,b],[c,d]]")

    # Algebra commands
    # Factor command
    factor_p = subparsers.add_parser("factor", help="Factor polynomial")
    factor_p.add_argument("expression", help="Polynomial to factor (e.g., 'x**2 - 1')")

    # Expand command
    expand_p = subparsers.add_parser("expand", help="Expand expression")
    expand_p.add_argument("expression", help="Expression to expand (e.g., '(x+1)**2')")

    # Apart (partial fractions) command
    apart_p = subparsers.add_parser("apart", help="Partial fraction decomposition")
    apart_p.add_argument("expression", help="Rational function to decompose")
    apart_p.add_argument("--var", default="x", help="Variable for decomposition")

    # GCD command
    gcd_p = subparsers.add_parser("gcd", help="Greatest common divisor")
    gcd_p.add_argument("expr1", help="First expression (integer or polynomial)")
    gcd_p.add_argument("expr2", help="Second expression (integer or polynomial)")

    # LCM command
    lcm_p = subparsers.add_parser("lcm", help="Least common multiple")
    lcm_p.add_argument("expr1", help="First expression (integer or polynomial)")
    lcm_p.add_argument("expr2", help="Second expression (integer or polynomial)")

    # Number Theory commands
    # Factorint command
    factorint_p = subparsers.add_parser("factorint", help="Factor integer into primes")
    factorint_p.add_argument("n", help="Integer to factor")

    # Isprime command
    isprime_p = subparsers.add_parser("isprime", help="Check if integer is prime")
    isprime_p.add_argument("n", help="Integer to check")

    # Modinverse command
    modinverse_p = subparsers.add_parser("modinverse", help="Compute modular inverse")
    modinverse_p.add_argument("a", help="Integer a")
    modinverse_p.add_argument("m", help="Modulus m")

    # Series command
    series_p = subparsers.add_parser("series", help="Taylor/Maclaurin series expansion")
    series_p.add_argument("expression", help="Expression to expand (e.g., 'sin(x)')")
    series_p.add_argument("--var", default="x", help="Variable to expand around")
    series_p.add_argument("--point", default="0", help="Point to expand around (default: 0)")
    series_p.add_argument("--order", type=int, default=6, help="Order of expansion")

    # Dsolve command
    dsolve_p = subparsers.add_parser("dsolve", help="Solve ordinary differential equations")
    dsolve_p.add_argument("equation", help="ODE expression (e.g., 'Derivative(f(x), x) - f(x)')")
    dsolve_p.add_argument("--func", default="f(x)", help="Function and variable (e.g., 'f(x)')")
    dsolve_p.add_argument("--ics", default=None, help="Initial conditions (e.g., 'f(0)=1')")

    # Laplace command
    laplace_p = subparsers.add_parser("laplace", help="Compute Laplace transform")
    laplace_p.add_argument("expression", help="Function of t to transform (e.g., 'exp(-t)')")
    laplace_p.add_argument("--var", default="t", help="Time domain variable (default: t)")
    laplace_p.add_argument("--svar", default="s", help="Frequency domain variable (default: s)")

    # Combinatorics commands
    # Binomial command
    binomial_p = subparsers.add_parser("binomial", help="Binomial coefficient C(n,k)")
    binomial_p.add_argument("n", help="Upper value")
    binomial_p.add_argument("k", help="Lower value")

    # Factorial command
    factorial_p = subparsers.add_parser("factorial", help="Factorial computation")
    factorial_p.add_argument("n", help="Non-negative integer")
    factorial_p.add_argument(
        "--kind",
        default="regular",
        choices=["regular", "double", "subfactorial"],
        help="Type: regular (n!), double (n!!), subfactorial (!n)",
    )

    # Permutation command
    perm_p = subparsers.add_parser("permutation", help="P(n,k) permutation count")
    perm_p.add_argument("n", help="Total elements")
    perm_p.add_argument("k", help="Elements to arrange")

    # Partition command
    partition_p = subparsers.add_parser("partition", help="Integer partition count p(n)")
    partition_p.add_argument("n", help="Non-negative integer")

    # Catalan command
    catalan_p = subparsers.add_parser("catalan", help="Catalan number C_n")
    catalan_p.add_argument("n", help="Non-negative integer index")

    # Bell command
    bell_p = subparsers.add_parser("bell", help="Bell number B_n")
    bell_p.add_argument("n", help="Non-negative integer index")

    # Common options
    for p in [
        solve_p,
        integrate_p,
        diff_p,
        simplify_p,
        limit_p,
        det_p,
        eigen_p,
        charpoly_p,
        eigenvects_p,
        inverse_p,
        transpose_p,
        linsolve_p,
        nullspace_p,
        rref_p,
        rank_p,
        factor_p,
        expand_p,
        apart_p,
        gcd_p,
        lcm_p,
        factorint_p,
        isprime_p,
        modinverse_p,
        series_p,
        dsolve_p,
        laplace_p,
        binomial_p,
        factorial_p,
        perm_p,
        partition_p,
        catalan_p,
        bell_p,
    ]:
        p.add_argument("--json", action="store_true", help="Output as JSON")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    args = parse_args()

    try:
        if args.command == "solve":
            result = solve_equation(args.expression, args.var, args.domain)
        elif args.command == "integrate":
            bounds = args.bounds or [None, None]
            result = integrate_expr(args.expression, args.var, bounds[0], bounds[1])
        elif args.command == "diff":
            result = differentiate_expr(args.expression, args.var, args.order)
        elif args.command == "simplify":
            result = simplify_expr(args.expression, args.strategy)
        elif args.command == "limit":
            result = limit_expr(args.expression, args.var, args.to, args.dir)
        elif args.command == "det":
            result = det_matrix(args.matrix)
        elif args.command == "eigenvalues":
            result = eigenvalues_matrix(args.matrix)
        elif args.command == "charpoly":
            result = charpoly_matrix(args.matrix, args.var)
        elif args.command == "eigenvectors":
            result = eigenvectors_matrix(args.matrix)
        elif args.command == "inverse":
            result = inverse_matrix(args.matrix)
        elif args.command == "transpose":
            result = transpose_matrix(args.matrix)
        elif args.command == "linsolve":
            result = linsolve_system(args.equations, args.vars)
        elif args.command == "nullspace":
            result = nullspace_matrix(args.matrix)
        elif args.command == "rref":
            result = rref_matrix(args.matrix)
        elif args.command == "rank":
            result = rank_matrix(args.matrix)
        elif args.command == "factor":
            result = factor_expr(args.expression)
        elif args.command == "expand":
            result = expand_expr(args.expression)
        elif args.command == "apart":
            result = partial_fractions(args.expression, args.var)
        elif args.command == "gcd":
            result = gcd_expr(args.expr1, args.expr2)
        elif args.command == "lcm":
            result = lcm_expr(args.expr1, args.expr2)
        elif args.command == "factorint":
            result = factor_integer(args.n)
        elif args.command == "isprime":
            result = is_prime_check(args.n)
        elif args.command == "modinverse":
            result = modular_inverse(args.a, args.m)
        elif args.command == "series":
            result = series_expansion(args.expression, args.var, args.point, args.order)
        elif args.command == "dsolve":
            result = solve_ode(args.equation, args.func, args.ics)
        elif args.command == "laplace":
            result = laplace_transform_expr(args.expression, args.var, args.svar)
        elif args.command == "binomial":
            result = binomial_coeff(args.n, args.k)
        elif args.command == "factorial":
            result = factorial_compute(args.n, args.kind)
        elif args.command == "permutation":
            result = permutation_count(args.n, args.k)
        elif args.command == "partition":
            result = partition_count(args.n)
        elif args.command == "catalan":
            result = catalan_number(args.n)
        elif args.command == "bell":
            result = bell_number(args.n)
        else:
            result = {"error": f"Unknown command: {args.command}"}

        # Output
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result, indent=2))

    except Exception as e:
        error_result = {"error": str(e), "command": args.command}
        print(json.dumps(error_result), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
