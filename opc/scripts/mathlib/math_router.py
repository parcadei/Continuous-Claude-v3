#!/usr/bin/env python3
"""Deterministic router for math cognitive stack.

Given a user intent, returns the exact CLI command to run without
needing to read skill documentation at runtime.

USAGE:
    # Route a math request
    uv run python scripts/math_router.py route "integrate sin(x)"
    uv run python scripts/math_router.py route "convert 5 meters to feet"
    uv run python scripts/math_router.py route "prove x + y == y + x"

    # List all available commands
    uv run python scripts/math_router.py list

    # List commands for a category
    uv run python scripts/math_router.py list --category sympy

    # Show route confidence details
    uv run python scripts/math_router.py route "differentiate x^3" --verbose
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Optional
from collections.abc import Callable

# =============================================================================
# Route Configuration
# =============================================================================


@dataclass
class Route:
    """A route mapping pattern to script command."""

    pattern: str
    script: str
    subcommand: str
    arg_extractor: Callable[[str], dict[str, Any]]
    description: str
    category: str
    priority: int = 0  # Higher = more specific


@dataclass
class RouteMatch:
    """Result of routing an intent."""

    command: str
    script: str
    subcommand: str
    args: dict[str, Any]
    confidence: float
    pattern: str
    alternatives: list[dict[str, Any]]


# =============================================================================
# Argument Extractors
# =============================================================================


def extract_expr_var(intent: str) -> dict[str, Any]:
    """Extract expression and variable from 'integrate sin(x)' -> ('sin(x)', 'x')."""
    # Remove common prefixes
    intent = re.sub(
        r"^(integrate|differentiate|diff|derivative of|integral of)\s*",
        "",
        intent,
        flags=re.IGNORECASE,
    )
    intent = intent.strip()

    # Look for variable in expression
    var_match = re.search(r"\b([a-z])\b", intent)
    var = var_match.group(1) if var_match else "x"

    # Clean up the expression
    expr = intent.strip()
    # Convert ^ to ** for Python/SymPy
    expr = expr.replace("^", "**")

    return {"expression": expr, "var": var}


def extract_diff_expr(intent: str) -> dict[str, Any]:
    """Extract expression for differentiation."""
    result = extract_expr_var(intent)
    # Check for order specification
    order_match = re.search(
        r"(\d+)(?:st|nd|rd|th)?\s*(?:derivative|order)", intent, flags=re.IGNORECASE
    )
    if order_match:
        result["order"] = int(order_match.group(1))
    else:
        result["order"] = 1
    return result


def extract_integrate_expr(intent: str) -> dict[str, Any]:
    """Extract expression and bounds for integration."""
    result = extract_expr_var(intent)

    # Check for definite integral bounds
    bounds_match = re.search(r"from\s*([\d\.\-]+)\s*to\s*([\d\.\-]+)", intent, flags=re.IGNORECASE)
    if bounds_match:
        result["bounds"] = [bounds_match.group(1), bounds_match.group(2)]

    return result


def extract_equation_var(intent: str) -> dict[str, Any]:
    """Extract equation and variable from 'solve x^2 - 4 = 0'."""
    # Remove "solve" prefix
    intent = re.sub(r"^solve\s*:?\s*", "", intent, flags=re.IGNORECASE)
    intent = re.sub(r"\s*for\s+[a-z]\s*$", "", intent, flags=re.IGNORECASE)

    # Extract variable if specified
    var_match = re.search(r"\bfor\s+([a-z])\b", intent, flags=re.IGNORECASE)
    var = var_match.group(1) if var_match else "x"

    # Clean equation
    equation = intent.strip()
    equation = equation.replace("^", "**")

    # Check for domain specification
    domain = "complex"
    if re.search(r"\breal\b", intent, flags=re.IGNORECASE):
        domain = "real"
    elif re.search(r"\bpositive\b", intent, flags=re.IGNORECASE):
        domain = "positive"
    elif re.search(r"\binteger\b", intent, flags=re.IGNORECASE):
        domain = "integer"

    return {"expression": equation, "var": var, "domain": domain}


def extract_simplify_expr(intent: str) -> dict[str, Any]:
    """Extract expression for simplification."""
    intent = re.sub(r"^simplify\s*", "", intent, flags=re.IGNORECASE)
    expr = intent.strip().replace("^", "**")

    # Detect strategy
    strategy = "auto"
    if re.search(r"\btrig", intent, flags=re.IGNORECASE):
        strategy = "trig"
    elif re.search(r"\brational\b", intent, flags=re.IGNORECASE):
        strategy = "rational"
    elif re.search(r"\bfactor\b", intent, flags=re.IGNORECASE):
        strategy = "factor"
    elif re.search(r"\bexpand\b", intent, flags=re.IGNORECASE):
        strategy = "expand"

    return {"expression": expr, "strategy": strategy}


def extract_limit(intent: str) -> dict[str, Any]:
    """Extract expression, variable, and point for limit."""
    # Pattern: limit of expr as x -> point
    expr_match = re.search(
        r"limit\s+(?:of\s+)?(.+?)\s+(?:as\s+)?([a-z])\s*(?:->|approaches?|to)\s*(.+)",
        intent,
        flags=re.IGNORECASE,
    )

    if expr_match:
        expr = expr_match.group(1).strip().replace("^", "**")
        var = expr_match.group(2)
        point = expr_match.group(3).strip()

        # Normalize infinity
        point = re.sub(r"\binfinity\b|\binf\b", "oo", point, flags=re.IGNORECASE)
        point = re.sub(r"\+\s*oo", "oo", point)

        # Check for direction
        direction = None
        if re.search(r"\bfrom\s+(?:the\s+)?right\b|\+\s*$", intent, flags=re.IGNORECASE):
            direction = "+"
        elif re.search(r"\bfrom\s+(?:the\s+)?left\b|\-\s*$", intent, flags=re.IGNORECASE):
            direction = "-"

        return {"expression": expr, "var": var, "to": point, "dir": direction}

    # Simpler pattern: limit expr to point
    simple_match = re.search(r"limit\s+(.+?)\s+(?:to|at)\s+(.+)", intent, flags=re.IGNORECASE)
    if simple_match:
        expr = simple_match.group(1).strip().replace("^", "**")
        point = simple_match.group(2).strip()
        return {"expression": expr, "var": "x", "to": point, "dir": None}

    return {"expression": intent, "var": "x", "to": "0", "dir": None}


def extract_matrix(intent: str) -> dict[str, Any]:
    """Extract matrix from intent."""
    # Look for [[...]] pattern
    matrix_match = re.search(r"\[\[.+?\]\]", intent)
    if matrix_match:
        return {"matrix": matrix_match.group(0)}

    # Try to find matrix in natural language
    # e.g., "2x2 matrix 1 2 3 4" or "matrix [[1,2],[3,4]]"
    return {"matrix": "[[1,0],[0,1]]"}  # Default to identity


def extract_unit_conversion(intent: str) -> dict[str, Any]:
    """Extract from 'convert 5 meters to feet' -> ('5 meters', 'feet')."""
    # Pattern: convert X to Y
    match = re.search(r"convert\s+(.+?)\s+to\s+(.+)", intent, flags=re.IGNORECASE)
    if match:
        quantity = match.group(1).strip()
        target = match.group(2).strip()
        return {"quantity": quantity, "to": target}

    # Pattern: X to Y (without "convert")
    match = re.search(r"(\d+(?:\.\d+)?\s*\w+)\s+(?:to|in)\s+(\w+)", intent, flags=re.IGNORECASE)
    if match:
        return {"quantity": match.group(1).strip(), "to": match.group(2).strip()}

    return {"quantity": intent, "to": ""}


def extract_dimension_check(intent: str) -> dict[str, Any]:
    """Extract units for dimensional check."""
    # Pattern: check if X compatible with Y
    match = re.search(
        r"(?:check|are)\s+(.+?)\s+(?:compatible|equivalent|same)\s+(?:with|as|to)?\s+(.+)",
        intent,
        flags=re.IGNORECASE,
    )
    if match:
        return {"unit1": match.group(1).strip(), "against": match.group(2).strip()}

    return {"unit1": "", "against": ""}


def extract_geom_measure(intent: str) -> dict[str, Any]:
    """Extract geometry for measurement."""
    # Look for WKT pattern
    wkt_match = re.search(r"(POLYGON|POINT|LINESTRING)\s*\([^)]+\)", intent, flags=re.IGNORECASE)
    if wkt_match:
        return {"geom": wkt_match.group(0), "what": "all"}

    # Determine what to measure
    what = "all"
    if re.search(r"\barea\b", intent, flags=re.IGNORECASE):
        what = "area"
    elif re.search(r"\blength\b|\bperimeter\b", intent, flags=re.IGNORECASE):
        what = "length"
    elif re.search(r"\bcentroid\b|\bcenter\b", intent, flags=re.IGNORECASE):
        what = "centroid"

    return {"geom": "", "what": what}


def extract_geom_op(intent: str) -> dict[str, Any]:
    """Extract geometries for operation."""
    # Look for operation type
    op = "intersection"
    if re.search(r"\bunion\b", intent, flags=re.IGNORECASE):
        op = "union"
    elif re.search(r"\bdifference\b", intent, flags=re.IGNORECASE):
        op = "difference"
    elif re.search(r"\bbuffer\b", intent, flags=re.IGNORECASE):
        op = "buffer"

    # Extract WKT patterns
    wkt_matches = re.findall(
        r"((?:POLYGON|POINT|LINESTRING)\s*\([^)]+\))", intent, flags=re.IGNORECASE
    )

    g1 = wkt_matches[0] if len(wkt_matches) > 0 else ""
    g2 = wkt_matches[1] if len(wkt_matches) > 1 else ""

    return {"operation": op, "g1": g1, "g2": g2}


def extract_geom_pred(intent: str) -> dict[str, Any]:
    """Extract geometries for predicate."""
    pred = "contains"
    if re.search(r"\bintersects?\b", intent, flags=re.IGNORECASE):
        pred = "intersects"
    elif re.search(r"\bwithin\b", intent, flags=re.IGNORECASE):
        pred = "within"
    elif re.search(r"\btouches?\b", intent, flags=re.IGNORECASE):
        pred = "touches"

    wkt_matches = re.findall(
        r"((?:POLYGON|POINT|LINESTRING)\s*\([^)]+\))", intent, flags=re.IGNORECASE
    )

    g1 = wkt_matches[0] if len(wkt_matches) > 0 else ""
    g2 = wkt_matches[1] if len(wkt_matches) > 1 else ""

    return {"predicate": pred, "g1": g1, "g2": g2}


def extract_distance(intent: str) -> dict[str, Any]:
    """Extract geometries for distance calculation."""
    wkt_matches = re.findall(
        r"((?:POLYGON|POINT|LINESTRING)\s*\([^)]+\))", intent, flags=re.IGNORECASE
    )

    g1 = wkt_matches[0] if len(wkt_matches) > 0 else ""
    g2 = wkt_matches[1] if len(wkt_matches) > 1 else ""

    return {"g1": g1, "g2": g2}


def extract_theorem(intent: str) -> dict[str, Any]:
    """Extract theorem statement for proving."""
    # Remove prove prefix
    theorem = re.sub(r"^prove\s+(?:that\s+)?", "", intent, flags=re.IGNORECASE)
    theorem = theorem.strip()

    # Normalize equality
    theorem = theorem.replace("=", "==").replace("====", "==").replace("===", "==")

    # Extract variables
    vars_found = set(re.findall(r"\b([a-z])\b", theorem))
    vars_list = sorted(list(vars_found))

    return {"theorem": theorem, "vars": vars_list, "var_type": "int"}


def extract_constraint(intent: str) -> dict[str, Any]:
    """Extract constraints for SAT check."""
    # Remove sat/satisfiable prefix
    constraints_str = re.sub(
        r"^(?:is\s+)?(?:sat|satisfiable)\s*:?\s*", "", intent, flags=re.IGNORECASE
    )

    # Split by comma or 'and'
    constraints = re.split(r",|\band\b", constraints_str)
    constraints = [c.strip() for c in constraints if c.strip()]

    return {"constraints": ", ".join(constraints), "var_type": "int"}


def extract_optimization(intent: str) -> dict[str, Any]:
    """Extract optimization objective and constraints."""
    direction = (
        "maximize"
        if re.search(r"\bmaximize\b|\bmax\b", intent, flags=re.IGNORECASE)
        else "minimize"
    )

    # Extract objective
    obj_match = re.search(
        r"(?:minimize|maximize|min|max)\s+(.+?)(?:\s+subject\s+to|\s+s\.t\.|\s+where|\s+with|$)",
        intent,
        flags=re.IGNORECASE,
    )
    objective = obj_match.group(1).strip() if obj_match else ""

    # Extract constraints
    constraints_match = re.search(
        r"(?:subject\s+to|s\.t\.|where|with)\s+(.+)", intent, flags=re.IGNORECASE
    )
    constraints = constraints_match.group(1).strip() if constraints_match else ""

    return {
        "objective": objective,
        "constraints": constraints,
        "direction": direction,
        "var_type": "real",
    }


def extract_verification(intent: str) -> dict[str, Any]:
    """Extract step for verification."""
    step = re.sub(r"^verify\s+(?:that\s+)?", "", intent, flags=re.IGNORECASE)
    return {"step": step.strip()}


def extract_step(intent: str) -> dict[str, Any]:
    """Extract step for explanation."""
    step = re.sub(r"^explain\s+(?:the\s+)?(?:step\s+)?", "", intent, flags=re.IGNORECASE)
    return {"step": step.strip()}


def extract_hint_request(intent: str) -> dict[str, Any]:
    """Extract problem for hint."""
    problem = re.sub(
        r"^(?:give\s+(?:me\s+)?(?:a\s+)?)?hint\s+(?:for\s+)?", "", intent, flags=re.IGNORECASE
    )

    # Check for level
    level_match = re.search(r"level\s*(\d+)", intent, flags=re.IGNORECASE)
    level = int(level_match.group(1)) if level_match else 1

    return {"problem": problem.strip(), "level": level}


def extract_steps_request(intent: str) -> dict[str, Any]:
    """Extract problem for step-by-step solution."""
    problem = re.sub(
        r"^(?:show\s+)?(?:step\s+by\s+step|steps)\s+(?:for\s+)?", "", intent, flags=re.IGNORECASE
    )

    # Detect operation
    operation = "solve"
    if re.search(r"\bdifferentiat", intent, flags=re.IGNORECASE):
        operation = "diff"
    elif re.search(r"\bintegrat", intent, flags=re.IGNORECASE):
        operation = "integrate"
    elif re.search(r"\bsimplif", intent, flags=re.IGNORECASE):
        operation = "simplify"

    return {"problem": problem.strip(), "operation": operation}


def extract_problem_gen(intent: str) -> dict[str, Any]:
    """Extract parameters for problem generation."""
    # Detect topic
    topic = "algebra"
    if re.search(r"\bquadratic\b", intent, flags=re.IGNORECASE):
        topic = "quadratic"
    elif re.search(r"\blinear\b", intent, flags=re.IGNORECASE):
        topic = "linear_equation"
    elif re.search(r"\bderivative\b|\bcalculus\b", intent, flags=re.IGNORECASE):
        topic = "calculus"

    # Detect difficulty
    diff_match = re.search(r"(?:difficulty|level)\s*(\d+)", intent, flags=re.IGNORECASE)
    difficulty = int(diff_match.group(1)) if diff_match else 2

    # Check for easy/medium/hard
    if re.search(r"\beasy\b", intent, flags=re.IGNORECASE):
        difficulty = 1
    elif re.search(r"\bmedium\b", intent, flags=re.IGNORECASE):
        difficulty = 2
    elif re.search(r"\bhard\b", intent, flags=re.IGNORECASE):
        difficulty = 4

    return {"topic": topic, "difficulty": difficulty}


def extract_plot_params(intent: str) -> dict[str, Any]:
    """Extract parameters for 2D plot."""
    # Extract expression
    expr_match = re.search(
        r"(?:plot|graph)\s+(.+?)(?:\s+from|\s+for|\s+over|$)", intent, flags=re.IGNORECASE
    )
    expression = expr_match.group(1).strip() if expr_match else ""
    expression = expression.replace("^", "**")

    # Extract range
    range_match = re.search(
        r"(?:from|over)\s*([\-\d\.]+)\s*to\s*([\-\d\.]+)", intent, flags=re.IGNORECASE
    )
    x_min = float(range_match.group(1)) if range_match else -10
    x_max = float(range_match.group(2)) if range_match else 10

    # Extract variable
    var_match = re.search(r"\b([a-z])\b", expression)
    var = var_match.group(1) if var_match else "x"

    return {
        "expression": expression,
        "var": var,
        "range": [x_min, x_max],
        "output": "/tmp/plot.png",
    }


def extract_plot3d_params(intent: str) -> dict[str, Any]:
    """Extract parameters for 3D plot."""
    # Extract expression
    expr_match = re.search(
        r"(?:3d\s+)?(?:plot|surface|graph)\s+(.+?)(?:\s+from|\s+for|\s+over|$)",
        intent,
        flags=re.IGNORECASE,
    )
    expression = expr_match.group(1).strip() if expr_match else ""
    expression = expression.replace("^", "**")

    # Extract range
    range_match = re.search(r"range\s*([\d\.]+)", intent, flags=re.IGNORECASE)
    range_val = float(range_match.group(1)) if range_match else 5

    return {
        "expression": expression,
        "xvar": "x",
        "yvar": "y",
        "range": range_val,
        "output": "/tmp/surface.html",
    }


def extract_latex(intent: str) -> dict[str, Any]:
    """Extract LaTeX for rendering."""
    # Look for LaTeX between delimiters
    latex_match = re.search(r"\$(.+?)\$|\\(.+?)\\", intent)
    if latex_match:
        latex = latex_match.group(1) or latex_match.group(2)
    else:
        latex = re.sub(r"^(?:render\s+)?latex\s+", "", intent, flags=re.IGNORECASE)

    return {"equation": latex.strip(), "output": "/tmp/equation.png"}


def extract_series(intent: str) -> dict[str, Any]:
    """Extract parameters for series expansion."""
    # Extract expression
    expr_match = re.search(
        r"(?:series|taylor|maclaurin)\s+(?:expansion\s+(?:of\s+)?)?(.+?)(?:\s+around|\s+at|\s+about|$)",
        intent,
        flags=re.IGNORECASE,
    )
    expression = expr_match.group(1).strip() if expr_match else ""
    expression = expression.replace("^", "**")

    # Extract point
    point_match = re.search(r"(?:around|at|about)\s*([\d\.\-]+|0)", intent, flags=re.IGNORECASE)
    point = point_match.group(1) if point_match else "0"

    # Extract order
    order_match = re.search(r"order\s*(\d+)", intent, flags=re.IGNORECASE)
    order = int(order_match.group(1)) if order_match else 6

    return {"expression": expression, "var": "x", "point": point, "order": order}


def extract_factor(intent: str) -> dict[str, Any]:
    """Extract expression for factoring."""
    expr = re.sub(r"^factor\s+", "", intent, flags=re.IGNORECASE)
    expr = expr.strip().replace("^", "**")
    return {"expression": expr}


def extract_expand(intent: str) -> dict[str, Any]:
    """Extract expression for expanding."""
    expr = re.sub(r"^expand\s+", "", intent, flags=re.IGNORECASE)
    expr = expr.strip().replace("^", "**")
    return {"expression": expr}


# =============================================================================
# NumPy/SciPy/mpmath Argument Extractors
# =============================================================================


def extract_np_matrix(intent: str) -> dict[str, Any]:
    """Extract matrix for NumPy operations."""
    # Look for [[...]] pattern
    matrix_match = re.search(r"\[\[.+?\]\]", intent)
    if matrix_match:
        return {"matrix": matrix_match.group(0)}
    return {"matrix": "[[1,0],[0,1]]"}


def extract_np_array(intent: str) -> dict[str, Any]:
    """Extract array for NumPy stats operations."""
    # Look for [...] or comma-separated numbers
    array_match = re.search(r"\[[\d\.,\s\-]+\]", intent)
    if array_match:
        return {"array": array_match.group(0)}

    # Look for "of" followed by numbers
    of_match = re.search(r"(?:of|for)\s+\[?([\d\.,\s\-]+)\]?", intent, flags=re.IGNORECASE)
    if of_match:
        return {"array": "[" + of_match.group(1).strip() + "]"}

    return {"array": "[1,2,3,4,5]"}


def extract_np_fft(intent: str) -> dict[str, Any]:
    """Extract signal array for FFT."""
    array_match = re.search(r"\[[\d\.,\s\-]+\]", intent)
    if array_match:
        return {"signal": array_match.group(0)}
    return {"signal": "[1,0,1,0]"}


def extract_scipy_minimize(intent: str) -> dict[str, Any]:
    """Extract function and initial guess for minimize."""
    # Remove prefix
    intent = re.sub(r"^(?:minimize|min)\s+", "", intent, flags=re.IGNORECASE)

    # Look for function expression (before "from" or "starting")
    func_match = re.search(
        r"^(.+?)(?:\s+from|\s+starting|\s+at|\s+x0|$)", intent, flags=re.IGNORECASE
    )
    func = func_match.group(1).strip() if func_match else "x**2"
    func = func.replace("^", "**")

    # Look for initial guess
    x0_match = re.search(
        r"(?:from|starting|at|x0)\s*=?\s*([\d\.\-,]+)", intent, flags=re.IGNORECASE
    )
    x0 = x0_match.group(1) if x0_match else "0"

    # Look for method
    method_match = re.search(r"method\s*=?\s*(\w+)", intent, flags=re.IGNORECASE)
    method = method_match.group(1) if method_match else "BFGS"

    return {"func": func, "x0": x0, "method": method}


def extract_scipy_root(intent: str) -> dict[str, Any]:
    """Extract function for root finding."""
    # Remove prefix
    intent = re.sub(r"^(?:find\s+)?(?:root|zero)\s+(?:of\s+)?", "", intent, flags=re.IGNORECASE)

    # Look for function expression
    func_match = re.search(
        r"^(.+?)(?:\s+from|\s+starting|\s+near|\s+x0|$)", intent, flags=re.IGNORECASE
    )
    func = func_match.group(1).strip() if func_match else "x**2 - 2"
    func = func.replace("^", "**").replace("=", "-")

    # Look for initial guess
    x0_match = re.search(
        r"(?:from|starting|near|x0)\s*=?\s*([\d\.\-,]+)", intent, flags=re.IGNORECASE
    )
    x0 = x0_match.group(1) if x0_match else "1"

    return {"func": func, "x0": x0}


def extract_scipy_quad(intent: str) -> dict[str, Any]:
    """Extract function and bounds for numerical integration."""
    # Remove prefix
    intent = re.sub(r"^(?:numerically?\s+)?(?:integrate|quad)\s+", "", intent, flags=re.IGNORECASE)

    # Look for function expression
    func_match = re.search(r"^(.+?)(?:\s+from|\s+over|$)", intent, flags=re.IGNORECASE)
    func = func_match.group(1).strip() if func_match else "x**2"
    func = func.replace("^", "**")

    # Look for bounds
    bounds_match = re.search(r"from\s*([\d\.\-]+)\s*to\s*([\d\.\-]+)", intent, flags=re.IGNORECASE)
    a = bounds_match.group(1) if bounds_match else "0"
    b = bounds_match.group(2) if bounds_match else "1"

    return {"func": func, "a": a, "b": b}


def extract_scipy_odeint(intent: str) -> dict[str, Any]:
    """Extract ODE for solving."""
    # Remove prefix
    intent = re.sub(r"^(?:solve\s+)?(?:ode|odeint|ivp)\s+", "", intent, flags=re.IGNORECASE)

    # Look for function (dy/dt = ...)
    func_match = re.search(
        r"(?:dy/dt|y\')\s*=\s*(.+?)(?:\s+y0|\s+from|$)", intent, flags=re.IGNORECASE
    )
    func = func_match.group(1).strip() if func_match else "-y"
    func = func.replace("^", "**")

    # Look for initial condition
    y0_match = re.search(r"y0\s*=\s*([\d\.\-,]+)", intent, flags=re.IGNORECASE)
    y0 = y0_match.group(1) if y0_match else "1"

    # Look for time span
    t_match = re.search(r"t\s*=\s*\[?([\d\.\-,\s]+)\]?", intent, flags=re.IGNORECASE)
    t_span = t_match.group(1) if t_match else "0,10"

    return {"func": func, "y0": y0, "t_span": t_span}


def extract_scipy_distribution(intent: str) -> dict[str, Any]:
    """Extract distribution parameters."""
    # Detect distribution type
    dist = "norm"
    if re.search(r"\bt[\-\s]?dist", intent, flags=re.IGNORECASE):
        dist = "t"
    elif re.search(r"\bchi[\-\s]?sq", intent, flags=re.IGNORECASE):
        dist = "chi2"
    elif re.search(r"\bexpon", intent, flags=re.IGNORECASE):
        dist = "expon"
    elif re.search(r"\buniform", intent, flags=re.IGNORECASE):
        dist = "uniform"
    elif re.search(r"\bpoisson", intent, flags=re.IGNORECASE):
        dist = "poisson"
    elif re.search(r"\bbinom", intent, flags=re.IGNORECASE):
        dist = "binom"

    # Detect function type
    func = "pdf"
    if re.search(r"\bcdf\b", intent, flags=re.IGNORECASE):
        func = "cdf"
    elif re.search(r"\bppf\b|\bquantile\b|\bpercentile\b", intent, flags=re.IGNORECASE):
        func = "ppf"
    elif re.search(r"\bsf\b|\bsurvival\b", intent, flags=re.IGNORECASE):
        func = "sf"
    elif re.search(r"\brvs\b|\brandom\b|\bsample\b", intent, flags=re.IGNORECASE):
        func = "rvs"

    # Extract x value
    x_match = re.search(r"(?:at|x\s*=)\s*([\d\.\-]+)", intent, flags=re.IGNORECASE)
    x = x_match.group(1) if x_match else "0"

    return {"dist": dist, "func": func, "x": x}


def extract_scipy_ttest(intent: str) -> dict[str, Any]:
    """Extract t-test parameters."""
    # Detect test type
    test_type = "1samp"
    if re.search(r"\bind\w*\b|\btwo[\-\s]?sample", intent, flags=re.IGNORECASE):
        test_type = "ind"
    elif re.search(r"\brel\w*\b|\bpaired\b", intent, flags=re.IGNORECASE):
        test_type = "rel"

    # Extract data
    data_match = re.search(r"\[[\d\.,\s\-]+\]", intent)
    data = data_match.group(0) if data_match else "[1,2,3,4,5]"

    # Extract popmean for 1-sample
    mean_match = re.search(r"(?:mean|mu)\s*=?\s*([\d\.\-]+)", intent, flags=re.IGNORECASE)
    popmean = mean_match.group(1) if mean_match else "0"

    return {"test_type": test_type, "data": data, "popmean": popmean}


def extract_mpmath_constant(intent: str) -> dict[str, Any]:
    """Extract precision for mpmath constant."""
    # Look for precision/dps
    dps_match = re.search(
        r"(?:to|with|dps\s*=?)\s*(\d+)\s*(?:digits?|dps|precision)?", intent, flags=re.IGNORECASE
    )
    dps = int(dps_match.group(1)) if dps_match else 50

    return {"dps": dps}


def extract_mpmath_func(intent: str) -> dict[str, Any]:
    """Extract arguments for mpmath function."""
    # Extract value
    val_match = re.search(r"(?:of\s+)?([\d\.\-]+)", intent)
    x = val_match.group(1) if val_match else "1"

    # Look for precision/dps
    dps_match = re.search(r"(?:with|dps\s*=?|precision)\s*(\d+)", intent, flags=re.IGNORECASE)
    dps = int(dps_match.group(1)) if dps_match else 50

    return {"x": x, "dps": dps}


def extract_mpmath_zeta(intent: str) -> dict[str, Any]:
    """Extract s value for zeta function."""
    # Extract s
    s_match = re.search(r"zeta\s*\(\s*([\d\.\-]+)\s*\)", intent, flags=re.IGNORECASE)
    if not s_match:
        s_match = re.search(r"zeta\s+(?:of\s+)?([\d\.\-]+)", intent, flags=re.IGNORECASE)
    s = s_match.group(1) if s_match else "2"

    # Look for precision/dps
    dps_match = re.search(r"(?:with|dps\s*=?|precision)\s*(\d+)", intent, flags=re.IGNORECASE)
    dps = int(dps_match.group(1)) if dps_match else 50

    return {"s": s, "dps": dps}


def extract_mpmath_gamma(intent: str) -> dict[str, Any]:
    """Extract x value for gamma function."""
    # Extract x
    x_match = re.search(r"gamma\s*\(\s*([\d\.\-]+)\s*\)", intent, flags=re.IGNORECASE)
    if not x_match:
        x_match = re.search(r"gamma\s+(?:of\s+)?([\d\.\-]+)", intent, flags=re.IGNORECASE)
    x = x_match.group(1) if x_match else "5"

    # Look for precision/dps
    dps_match = re.search(r"(?:with|dps\s*=?|precision)\s*(\d+)", intent, flags=re.IGNORECASE)
    dps = int(dps_match.group(1)) if dps_match else 50

    return {"x": x, "dps": dps}


# =============================================================================
# Route Definitions
# =============================================================================


ROUTES: list[Route] = [
    # ============ SymPy Calculus ============
    Route(
        pattern=r"\bintegrat\w*\b|\bantiderivat\w*\b|\bintegral\b",
        script="sympy_compute.py",
        subcommand="integrate",
        arg_extractor=extract_integrate_expr,
        description="Compute integral (indefinite or definite)",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\bdifferentiat\w*\b|\bderivativ\w*\b|\bd/dx\b|\bdiff\b",
        script="sympy_compute.py",
        subcommand="diff",
        arg_extractor=extract_diff_expr,
        description="Compute derivative",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\blimit\b",
        script="sympy_compute.py",
        subcommand="limit",
        arg_extractor=extract_limit,
        description="Compute limit",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\bseries\b|\btaylor\b|\bmaclaurin\b",
        script="sympy_compute.py",
        subcommand="series",
        arg_extractor=extract_series,
        description="Taylor/Maclaurin series expansion",
        category="sympy",
        priority=10,
    ),
    # ============ SymPy Algebra ============
    Route(
        pattern=r"\bsolve\b",
        script="sympy_compute.py",
        subcommand="solve",
        arg_extractor=extract_equation_var,
        description="Solve equation",
        category="sympy",
        priority=15,
    ),
    Route(
        pattern=r"\bsimplif\w*\b",
        script="sympy_compute.py",
        subcommand="simplify",
        arg_extractor=extract_simplify_expr,
        description="Simplify expression",
        category="sympy",
        priority=5,
    ),
    Route(
        pattern=r"\bfactor\b(?!\s*int)",
        script="sympy_compute.py",
        subcommand="factor",
        arg_extractor=extract_factor,
        description="Factor polynomial",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\bexpand\b",
        script="sympy_compute.py",
        subcommand="expand",
        arg_extractor=extract_expand,
        description="Expand expression",
        category="sympy",
        priority=10,
    ),
    # ============ SymPy Linear Algebra ============
    Route(
        pattern=r"\beigenvalue\w*\b",
        script="sympy_compute.py",
        subcommand="eigenvalues",
        arg_extractor=extract_matrix,
        description="Compute eigenvalues",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\beigenvector\w*\b",
        script="sympy_compute.py",
        subcommand="eigenvectors",
        arg_extractor=extract_matrix,
        description="Compute eigenvectors",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\bdeterminant\b|\bdet\b",
        script="sympy_compute.py",
        subcommand="det",
        arg_extractor=extract_matrix,
        description="Compute matrix determinant",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\binverse\b.*\bmatrix\b|\bmatrix\b.*\binverse\b",
        script="sympy_compute.py",
        subcommand="inverse",
        arg_extractor=extract_matrix,
        description="Compute matrix inverse",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\brref\b|\breduced\s+row\b",
        script="sympy_compute.py",
        subcommand="rref",
        arg_extractor=extract_matrix,
        description="Compute RREF",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\bnull\s*space\b|\bkernel\b",
        script="sympy_compute.py",
        subcommand="nullspace",
        arg_extractor=extract_matrix,
        description="Compute null space",
        category="sympy",
        priority=10,
    ),
    Route(
        pattern=r"\brank\b.*\bmatrix\b|\bmatrix\b.*\brank\b",
        script="sympy_compute.py",
        subcommand="rank",
        arg_extractor=extract_matrix,
        description="Compute matrix rank",
        category="sympy",
        priority=10,
    ),
    # ============ Pint Unit Conversion ============
    Route(
        pattern=r"\bconvert\b.*\bto\b|\b\d+\s*\w+\s+to\s+\w+",
        script="pint_compute.py",
        subcommand="convert",
        arg_extractor=extract_unit_conversion,
        description="Convert between units",
        category="pint",
        priority=20,
    ),
    Route(
        pattern=r"\bdimension\w*\s+compat\w*\b|\bcompat\w*\s+dimension\w*\b|\bunits?\s+compat\w*\b|\bcompat\w*\b",
        script="pint_compute.py",
        subcommand="check",
        arg_extractor=extract_dimension_check,
        description="Check dimensional compatibility",
        category="pint",
        priority=10,
    ),
    # ============ Shapely Geometry ============
    Route(
        pattern=r"\barea\b.*\bpolygon\b|\bpolygon\b.*\barea\b",
        script="shapely_compute.py",
        subcommand="measure",
        arg_extractor=extract_geom_measure,
        description="Measure polygon area",
        category="shapely",
        priority=15,
    ),
    Route(
        pattern=r"\bintersection\b.*\bpolygon\b|\bpolygon\b.*\bintersection\b",
        script="shapely_compute.py",
        subcommand="op",
        arg_extractor=extract_geom_op,
        description="Compute geometry intersection",
        category="shapely",
        priority=10,
    ),
    Route(
        pattern=r"\bcontains?\b.*\bpoint\b|\bpoint\b.*\bin\b.*\bpolygon\b",
        script="shapely_compute.py",
        subcommand="pred",
        arg_extractor=extract_geom_pred,
        description="Check point in polygon",
        category="shapely",
        priority=10,
    ),
    Route(
        pattern=r"\bdistance\s+between\b",
        script="shapely_compute.py",
        subcommand="distance",
        arg_extractor=extract_distance,
        description="Compute distance between geometries",
        category="shapely",
        priority=10,
    ),
    # ============ Z3 Theorem Proving ============
    Route(
        pattern=r"\bprove\b|\btheorem\b|\bverify\s+forall\b",
        script="z3_solve.py",
        subcommand="prove",
        arg_extractor=extract_theorem,
        description="Prove theorem (find counterexample)",
        category="z3",
        priority=10,
    ),
    Route(
        pattern=r"\bsatisfiable\b|\bsat\b(?!\w)",
        script="z3_solve.py",
        subcommand="sat",
        arg_extractor=extract_constraint,
        description="Check satisfiability",
        category="z3",
        priority=10,
    ),
    Route(
        pattern=r"\boptimize\b|\bminimize\b|\bmaximize\b",
        script="z3_solve.py",
        subcommand="optimize",
        arg_extractor=extract_optimization,
        description="Optimize objective",
        category="z3",
        priority=10,
    ),
    # ============ Math Scratchpad ============
    Route(
        pattern=r"\bverify\b.*\bstep\b|\bcheck\b.*\bstep\b",
        script="math_scratchpad.py",
        subcommand="verify",
        arg_extractor=extract_verification,
        description="Verify mathematical step",
        category="scratchpad",
        priority=10,
    ),
    Route(
        pattern=r"\bexplain\b.*\bstep\b",
        script="math_scratchpad.py",
        subcommand="explain",
        arg_extractor=extract_step,
        description="Explain mathematical step",
        category="scratchpad",
        priority=10,
    ),
    # ============ Math Tutor ============
    Route(
        pattern=r"\bhint\b|\bgive\s+(?:me\s+)?(?:a\s+)?hint\b",
        script="math_tutor.py",
        subcommand="hint",
        arg_extractor=extract_hint_request,
        description="Get progressive hint",
        category="tutor",
        priority=10,
    ),
    Route(
        pattern=r"\bstep\s+by\s+step\b|\bshow\s+steps\b",
        script="math_tutor.py",
        subcommand="steps",
        arg_extractor=extract_steps_request,
        description="Step-by-step solution",
        category="tutor",
        priority=10,
    ),
    Route(
        pattern=r"\bgenerate\b.*\bproblem\b|\bpractice\b.*\bproblem\b",
        script="math_tutor.py",
        subcommand="generate",
        arg_extractor=extract_problem_gen,
        description="Generate practice problem",
        category="tutor",
        priority=10,
    ),
    # ============ Math Plot ============
    Route(
        pattern=r"\bplot\b|\bgraph\b|\bvisualize\b",
        script="math_plot.py",
        subcommand="plot2d",
        arg_extractor=extract_plot_params,
        description="Create 2D plot",
        category="plot",
        priority=5,
    ),
    Route(
        pattern=r"\b3d\s*plot\b|\bsurface\b",
        script="math_plot.py",
        subcommand="plot3d",
        arg_extractor=extract_plot3d_params,
        description="Create 3D surface plot",
        category="plot",
        priority=15,
    ),
    Route(
        pattern=r"\brender\s+latex\b|\blatex\s+(?:to\s+)?(?:png|image)\b",
        script="math_plot.py",
        subcommand="latex",
        arg_extractor=extract_latex,
        description="Render LaTeX to image",
        category="plot",
        priority=10,
    ),
    # ============ NumPy Linear Algebra ============
    Route(
        pattern=r"\bnumpy\s+det\w*\b|\bnp\.linalg\.det\b|\bnumpy\s+determinant\b",
        script="numpy_compute.py",
        subcommand="det",
        arg_extractor=extract_np_matrix,
        description="NumPy matrix determinant",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+inv\w*\b|\bnp\.linalg\.inv\b|\bnumpy\s+inverse\b",
        script="numpy_compute.py",
        subcommand="inv",
        arg_extractor=extract_np_matrix,
        description="NumPy matrix inverse",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+pinv\b|\bnp\.linalg\.pinv\b|\bpseudo[\-\s]?inverse\b",
        script="numpy_compute.py",
        subcommand="pinv",
        arg_extractor=extract_np_matrix,
        description="NumPy Moore-Penrose pseudo-inverse",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+eig\w*\b|\bnp\.linalg\.eig\b|\bnumerical\s+eigenvalue",
        script="numpy_compute.py",
        subcommand="eig",
        arg_extractor=extract_np_matrix,
        description="NumPy eigenvalue decomposition",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+svd\b|\bnp\.linalg\.svd\b|\bsingular\s+value\s+decomp",
        script="numpy_compute.py",
        subcommand="svd",
        arg_extractor=extract_np_matrix,
        description="NumPy singular value decomposition",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+solve\b|\bnp\.linalg\.solve\b|\bnumerical\s+linear\s+system",
        script="numpy_compute.py",
        subcommand="solve",
        arg_extractor=extract_np_matrix,
        description="NumPy solve linear system",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+lstsq\b|\bnp\.linalg\.lstsq\b|\bleast\s+squares\b",
        script="numpy_compute.py",
        subcommand="lstsq",
        arg_extractor=extract_np_matrix,
        description="NumPy least squares",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+norm\b|\bnp\.linalg\.norm\b|\bmatrix\s+norm\b",
        script="numpy_compute.py",
        subcommand="norm",
        arg_extractor=extract_np_matrix,
        description="NumPy matrix/vector norm",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+cond\b|\bnp\.linalg\.cond\b|\bcondition\s+number\b",
        script="numpy_compute.py",
        subcommand="cond",
        arg_extractor=extract_np_matrix,
        description="NumPy condition number",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+qr\b|\bnp\.linalg\.qr\b|\bqr\s+decomp",
        script="numpy_compute.py",
        subcommand="qr",
        arg_extractor=extract_np_matrix,
        description="NumPy QR decomposition",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+cholesky\b|\bnp\.linalg\.cholesky\b",
        script="numpy_compute.py",
        subcommand="cholesky",
        arg_extractor=extract_np_matrix,
        description="NumPy Cholesky decomposition",
        category="numpy",
        priority=15,
    ),
    # ============ NumPy Statistics ============
    Route(
        pattern=r"\bnumpy\s+mean\b|\bnp\.mean\b|\barray\s+mean\b",
        script="numpy_compute.py",
        subcommand="mean",
        arg_extractor=extract_np_array,
        description="NumPy array mean",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+std\b|\bnp\.std\b|\bstandard\s+deviation\b.*\barray\b",
        script="numpy_compute.py",
        subcommand="std",
        arg_extractor=extract_np_array,
        description="NumPy standard deviation",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+var\b|\bnp\.var\b|\barray\s+variance\b",
        script="numpy_compute.py",
        subcommand="var",
        arg_extractor=extract_np_array,
        description="NumPy variance",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+median\b|\bnp\.median\b|\barray\s+median\b",
        script="numpy_compute.py",
        subcommand="median",
        arg_extractor=extract_np_array,
        description="NumPy median",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+percentile\b|\bnp\.percentile\b",
        script="numpy_compute.py",
        subcommand="percentile",
        arg_extractor=extract_np_array,
        description="NumPy percentile",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+sum\b|\bnp\.sum\b|\barray\s+sum\b",
        script="numpy_compute.py",
        subcommand="sum",
        arg_extractor=extract_np_array,
        description="NumPy array sum",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+prod\b|\bnp\.prod\b|\barray\s+product\b",
        script="numpy_compute.py",
        subcommand="prod",
        arg_extractor=extract_np_array,
        description="NumPy array product",
        category="numpy",
        priority=15,
    ),
    # ============ NumPy FFT ============
    Route(
        pattern=r"\bnumpy\s+fft\b|\bnp\.fft\.fft\b|\bfourier\s+transform\b",
        script="numpy_compute.py",
        subcommand="fft",
        arg_extractor=extract_np_fft,
        description="NumPy FFT",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+ifft\b|\bnp\.fft\.ifft\b|\binverse\s+fft\b",
        script="numpy_compute.py",
        subcommand="ifft",
        arg_extractor=extract_np_fft,
        description="NumPy inverse FFT",
        category="numpy",
        priority=15,
    ),
    Route(
        pattern=r"\bnumpy\s+rfft\b|\bnp\.fft\.rfft\b|\breal\s+fft\b",
        script="numpy_compute.py",
        subcommand="rfft",
        arg_extractor=extract_np_fft,
        description="NumPy real FFT",
        category="numpy",
        priority=15,
    ),
    # ============ SciPy Optimize ============
    Route(
        pattern=r"\bscipy\s+minimize\b|\bscipy\.optimize\.minimize\b|\bnumerically\s+minimize\b",
        script="scipy_compute.py",
        subcommand="minimize",
        arg_extractor=extract_scipy_minimize,
        description="SciPy minimize function",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+minimize_scalar\b|\bscipy\.optimize\.minimize_scalar\b",
        script="scipy_compute.py",
        subcommand="minimize_scalar",
        arg_extractor=extract_scipy_minimize,
        description="SciPy minimize scalar function",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+root\b|\bscipy\.optimize\.root\b|\bnumerical\s+root\b",
        script="scipy_compute.py",
        subcommand="root",
        arg_extractor=extract_scipy_root,
        description="SciPy find root",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+fsolve\b|\bscipy\.optimize\.fsolve\b",
        script="scipy_compute.py",
        subcommand="fsolve",
        arg_extractor=extract_scipy_root,
        description="SciPy solve nonlinear equations",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+brentq\b|\bscipy\.optimize\.brentq\b|\bbrent\s+root\b",
        script="scipy_compute.py",
        subcommand="brentq",
        arg_extractor=extract_scipy_root,
        description="SciPy Brent root finding",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+curve_fit\b|\bscipy\.optimize\.curve_fit\b|\bfit\s+curve\b",
        script="scipy_compute.py",
        subcommand="curve_fit",
        arg_extractor=extract_scipy_minimize,
        description="SciPy curve fitting",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+linprog\b|\bscipy\.optimize\.linprog\b|\blinear\s+programming\b",
        script="scipy_compute.py",
        subcommand="linprog",
        arg_extractor=extract_scipy_minimize,
        description="SciPy linear programming",
        category="scipy",
        priority=20,
    ),
    # ============ SciPy Integrate ============
    Route(
        pattern=r"\bscipy\s+quad\b|\bscipy\.integrate\.quad\b|\bnumerical\s+integra",
        script="scipy_compute.py",
        subcommand="quad",
        arg_extractor=extract_scipy_quad,
        description="SciPy numerical integration",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+dblquad\b|\bscipy\.integrate\.dblquad\b|\bdouble\s+integra",
        script="scipy_compute.py",
        subcommand="dblquad",
        arg_extractor=extract_scipy_quad,
        description="SciPy double integration",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+odeint\b|\bscipy\.integrate\.odeint\b|\bsolve\s+ode\b",
        script="scipy_compute.py",
        subcommand="odeint",
        arg_extractor=extract_scipy_odeint,
        description="SciPy ODE integration",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+solve_ivp\b|\bscipy\.integrate\.solve_ivp\b|\binitial\s+value\s+problem\b",
        script="scipy_compute.py",
        subcommand="solve_ivp",
        arg_extractor=extract_scipy_odeint,
        description="SciPy solve initial value problem",
        category="scipy",
        priority=20,
    ),
    # ============ SciPy Stats ============
    Route(
        pattern=r"\bscipy\s+norm\b|\bscipy\.stats\.norm\b|\bnormal\s+distribution\b",
        script="scipy_compute.py",
        subcommand="norm",
        arg_extractor=extract_scipy_distribution,
        description="SciPy normal distribution",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+t[\-\s]?dist\b|\bscipy\.stats\.t\b|\bt[\-\s]?distribution\b",
        script="scipy_compute.py",
        subcommand="t",
        arg_extractor=extract_scipy_distribution,
        description="SciPy t-distribution",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+chi2\b|\bscipy\.stats\.chi2\b|\bchi[\-\s]?squared?\b",
        script="scipy_compute.py",
        subcommand="chi2",
        arg_extractor=extract_scipy_distribution,
        description="SciPy chi-squared distribution",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+ttest\b|\bscipy\.stats\.ttest\b|\bt[\-\s]?test\b",
        script="scipy_compute.py",
        subcommand="ttest_1samp",
        arg_extractor=extract_scipy_ttest,
        description="SciPy t-test",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+kstest\b|\bscipy\.stats\.kstest\b|\bkolmogorov[\-\s]?smirnov\b",
        script="scipy_compute.py",
        subcommand="kstest",
        arg_extractor=extract_scipy_ttest,
        description="SciPy Kolmogorov-Smirnov test",
        category="scipy",
        priority=20,
    ),
    Route(
        pattern=r"\bscipy\s+pearsonr\b|\bscipy\.stats\.pearsonr\b|\bpearson\s+corr",
        script="scipy_compute.py",
        subcommand="pearsonr",
        arg_extractor=extract_scipy_ttest,
        description="SciPy Pearson correlation",
        category="scipy",
        priority=20,
    ),
    # ============ mpmath Constants ============
    Route(
        pattern=r"\bmpmath\s+pi\b|\bmp\.pi\b|\barbitrary\s+precision\s+pi\b|\bpi\s+to\s+\d+\s*digits?\b|high\s+precision\s+pi",
        script="mpmath_compute.py",
        subcommand="pi",
        arg_extractor=extract_mpmath_constant,
        description="mpmath pi to arbitrary precision",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+e\b|\bmp\.e\b|\barbitrary\s+precision\s+e\b|\be\s+to\s+\d+\s*digits?\b",
        script="mpmath_compute.py",
        subcommand="e",
        arg_extractor=extract_mpmath_constant,
        description="mpmath e to arbitrary precision",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+euler\b|\bmp\.euler\b|\beuler[\-\s]?mascheroni\b|\beuler\s+gamma\b",
        script="mpmath_compute.py",
        subcommand="euler",
        arg_extractor=extract_mpmath_constant,
        description="mpmath Euler-Mascheroni constant",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+phi\b|\bmp\.phi\b|\bgolden\s+ratio\b",
        script="mpmath_compute.py",
        subcommand="phi",
        arg_extractor=extract_mpmath_constant,
        description="mpmath golden ratio",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+catalan\b|\bmp\.catalan\b|\bcatalan\s+constant\b",
        script="mpmath_compute.py",
        subcommand="catalan",
        arg_extractor=extract_mpmath_constant,
        description="mpmath Catalan constant",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+apery\b|\bmp\.apery\b|\bapery\s+constant\b",
        script="mpmath_compute.py",
        subcommand="apery",
        arg_extractor=extract_mpmath_constant,
        description="mpmath Apery constant (zeta(3))",
        category="mpmath",
        priority=25,
    ),
    # ============ mpmath Elementary Functions ============
    Route(
        pattern=r"\bmpmath\s+sqrt\b|\bmp\.sqrt\b|\bhigh\s+precision\s+sqrt\b",
        script="mpmath_compute.py",
        subcommand="mp_sqrt",
        arg_extractor=extract_mpmath_func,
        description="mpmath square root",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+exp\b|\bmp\.exp\b|\bhigh\s+precision\s+exp\b",
        script="mpmath_compute.py",
        subcommand="mp_exp",
        arg_extractor=extract_mpmath_func,
        description="mpmath exponential",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+log\b|\bmp\.log\b|\bhigh\s+precision\s+log\b",
        script="mpmath_compute.py",
        subcommand="mp_log",
        arg_extractor=extract_mpmath_func,
        description="mpmath natural logarithm",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+power\b|\bmp\.power\b|\bhigh\s+precision\s+power\b",
        script="mpmath_compute.py",
        subcommand="mp_power",
        arg_extractor=extract_mpmath_func,
        description="mpmath power function",
        category="mpmath",
        priority=25,
    ),
    # ============ mpmath Special Functions ============
    Route(
        pattern=r"\bmpmath\s+gamma\b|\bmp\.gamma\b|\bhigh\s+precision\s+gamma\b",
        script="mpmath_compute.py",
        subcommand="mp_gamma",
        arg_extractor=extract_mpmath_gamma,
        description="mpmath gamma function",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+factorial\b|\bmp\.factorial\b|\bhigh\s+precision\s+factorial\b",
        script="mpmath_compute.py",
        subcommand="mp_factorial",
        arg_extractor=extract_mpmath_func,
        description="mpmath factorial",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+zeta\b|\bmp\.zeta\b|\briemann\s+zeta\b|\bhigh\s+precision\s+zeta\b",
        script="mpmath_compute.py",
        subcommand="mp_zeta",
        arg_extractor=extract_mpmath_zeta,
        description="mpmath Riemann zeta function",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+beta\b|\bmp\.beta\b|\bhigh\s+precision\s+beta\b",
        script="mpmath_compute.py",
        subcommand="mp_beta",
        arg_extractor=extract_mpmath_func,
        description="mpmath beta function",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+erf\b|\bmp\.erf\b|\bhigh\s+precision\s+erf\b|\berror\s+function\b",
        script="mpmath_compute.py",
        subcommand="mp_erf",
        arg_extractor=extract_mpmath_func,
        description="mpmath error function",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+besselj\b|\bmp\.besselj\b|\bbessel\s+j\b",
        script="mpmath_compute.py",
        subcommand="mp_besselj",
        arg_extractor=extract_mpmath_func,
        description="mpmath Bessel J function",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+polylog\b|\bmp\.polylog\b|\bpolylogarithm\b",
        script="mpmath_compute.py",
        subcommand="mp_polylog",
        arg_extractor=extract_mpmath_func,
        description="mpmath polylogarithm",
        category="mpmath",
        priority=25,
    ),
    Route(
        pattern=r"\bmpmath\s+hyp2f1\b|\bmp\.hyp2f1\b|\bhypergeometric\b",
        script="mpmath_compute.py",
        subcommand="mp_hyp2f1",
        arg_extractor=extract_mpmath_func,
        description="mpmath hypergeometric 2F1",
        category="mpmath",
        priority=25,
    ),
]


# =============================================================================
# Auto-Generated Routes for Full Coverage
# =============================================================================

# Script to category mapping
SCRIPT_CATEGORIES: dict[str, str] = {
    "sympy_compute.py": "sympy",
    "numpy_compute.py": "numpy",
    "scipy_compute.py": "scipy",
    "mpmath_compute.py": "mpmath",
    "pint_compute.py": "pint",
    "shapely_compute.py": "shapely",
    "z3_solve.py": "z3",
    "math_scratchpad.py": "scratchpad",
    "math_tutor.py": "tutor",
    "math_plot.py": "plot",
}


def extract_generic(intent: str) -> dict[str, Any]:
    """Generic extractor that captures the whole intent.

    For auto-generated routes, we pass the intent as-is since
    specific argument parsing would require per-command knowledge.
    The CLI scripts handle argument parsing themselves.
    """
    # Try to extract common patterns
    result: dict[str, Any] = {"input": intent}

    # Extract array if present
    array_match = re.search(r"\[[\d\.,\s\-]+\]", intent)
    if array_match:
        result["array"] = array_match.group(0)

    # Extract matrix if present
    matrix_match = re.search(r"\[\[.+?\]\]", intent)
    if matrix_match:
        result["matrix"] = matrix_match.group(0)

    # Extract expression (anything that looks mathematical)
    expr_match = re.search(
        r"(?:of|for|compute|calculate)\s+(.+?)(?:\s+from|\s+to|\s+with|$)",
        intent,
        flags=re.IGNORECASE,
    )
    if expr_match:
        result["expression"] = expr_match.group(1).strip().replace("^", "**")

    # Extract precision for mpmath
    dps_match = re.search(r"(?:dps|precision|digits)\s*=?\s*(\d+)", intent, flags=re.IGNORECASE)
    if dps_match:
        result["dps"] = int(dps_match.group(1))

    return result


# =============================================================================
# Smart Extractor Integration
# =============================================================================


def create_smart_extractor(expected_args: list[str]) -> Callable[[str], dict[str, Any]]:
    """Create a smart extractor function for a command with given arguments.

    Args:
        expected_args: List of argument names (e.g., ["matrix", "n"] or ["x", "dps"])

    Returns:
        Extractor function that takes intent string and returns extracted args
    """

    def extractor(intent: str) -> dict[str, Any]:
        # Use smart_extract with the expected args for this command
        result = smart_extract(intent, expected_args)
        # Always include input as fallback for CLI parsing
        result["input"] = intent
        return result

    return extractor


def _is_math_command_decorator(decorator) -> bool:
    """Check if decorator is a @math_command call."""
    import ast
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    return isinstance(func, ast.Name) and func.id == "math_command"


def _extract_arg_names_from_args_kwarg(args_value) -> list[str]:
    """Extract argument names from the 'args' keyword argument value."""
    import ast
    arg_names: list[str] = []
    if not isinstance(args_value, ast.List):
        return arg_names
    
    for elt in args_value.elts:
        if not isinstance(elt, ast.Dict):
            continue
        for key, val in zip(elt.keys, elt.values):
            if (key is not None 
                and isinstance(key, ast.Constant) 
                and key.value == "name"
                and isinstance(val, ast.Constant)):
                arg_name = val.value.lstrip("-")
                arg_names.append(arg_name)
                break
    
    return arg_names


def _extract_schema_from_decorator(decorator) -> tuple[str | None, list[str]]:
    """Extract command name and argument names from a math_command decorator."""
    import ast
    cmd_name = None
    arg_names: list[str] = []
    
    for kw in decorator.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
            cmd_name = kw.value.value
        elif kw.arg == "args":
            arg_names = _extract_arg_names_from_args_kwarg(kw.value)
    
    return cmd_name, arg_names


def _extract_command_schemas_from_file(filepath: str) -> dict[str, list[str]]:
    """Extract command argument schemas from a script using AST parsing.

    Args:
        filepath: Path to the script file

    Returns:
        Dictionary mapping command names to list of argument names
    """
    import ast
    import os

    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath) as f:
            source = f.read()
        tree = ast.parse(source)
    except (SyntaxError, FileNotFoundError):
        return {}

    schemas: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        for decorator in node.decorator_list:
            if not _is_math_command_decorator(decorator):
                continue
            
            cmd_name, arg_names = _extract_schema_from_decorator(decorator)
            if cmd_name:
                schemas[cmd_name] = arg_names

    return schemas


def _load_command_schemas() -> dict[str, dict[str, list[str]]]:
    """Load command schemas from all math scripts at module load time.

    Returns:
        Dictionary mapping script names to {command_name: [arg_names]}
    """
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    all_schemas: dict[str, dict[str, list[str]]] = {}

    for script_name in SCRIPT_CATEGORIES:
        script_path = os.path.join(script_dir, script_name)
        schemas = _extract_command_schemas_from_file(script_path)
        if schemas:
            all_schemas[script_name] = schemas

    return all_schemas


# Load schemas at module load time (cached)
_COMMAND_SCHEMAS: dict[str, dict[str, list[str]]] | None = None


def _get_command_schemas() -> dict[str, dict[str, list[str]]]:
    """Get cached command schemas, loading if needed."""
    global _COMMAND_SCHEMAS
    if _COMMAND_SCHEMAS is None:
        _COMMAND_SCHEMAS = _load_command_schemas()
    return _COMMAND_SCHEMAS


def _extract_script_subcommands(script_path: str) -> list[str]:
    """Extract all subcommands from a script using regex.

    Looks for both add_parser() calls and @math_command decorators.
    """
    import os

    if not os.path.exists(script_path):
        return []

    with open(script_path) as f:
        content = f.read()

    commands = set()

    # Pattern 1: subparsers.add_parser("command")
    add_parser_pattern = r'subparsers\.add_parser\s*\(\s*["\']([^"\']+)["\']'
    commands.update(re.findall(add_parser_pattern, content))

    # Pattern 2: @math_command(...name="command_name"...)
    math_cmd_pattern = r'@math_command\s*\([^)]*name\s*=\s*["\']([^"\']+)["\']'
    commands.update(re.findall(math_cmd_pattern, content, re.DOTALL))

    # Pattern 3: def cmd_XXX functions
    cmd_fn_pattern = r"def cmd_([a-zA-Z0-9_]+)\s*\("
    commands.update(re.findall(cmd_fn_pattern, content))

    return sorted(list(commands))


def _generate_auto_pattern(cmd_name: str, script: str) -> str:
    """Generate a simple regex pattern for a command name.

    Uses word boundary matching with optional prefixes for NumPy/mpmath/SciPy.
    """
    # Handle np_ prefix for numpy
    if cmd_name.startswith("np_"):
        base = cmd_name[3:]
        return rf"\b{cmd_name}\b|\bnumpy\s+{base}\b"

    # Handle mp_ prefix for mpmath
    if cmd_name.startswith("mp_"):
        base = cmd_name[3:]
        return rf"\b{cmd_name}\b|\bmpmath\s+{base}\b|\bhigh\s+precision\s+{base}\b"

    # Handle sp_ prefix for scipy special
    if cmd_name.startswith("sp_"):
        base = cmd_name[3:]
        return rf"\b{cmd_name}\b|\bscipy\s+{base}\b|\bspecial\s+{base}\b"

    # Handle sig_ prefix (scipy signal)
    if cmd_name.startswith("sig_"):
        base = cmd_name[4:]
        return rf"\b{cmd_name}\b|\bsignal\s+{base}\b"

    # Default: match command name as word
    return rf"\b{cmd_name}\b"


def _generate_auto_description(cmd_name: str, script: str) -> str:
    """Generate human-readable description from command name."""
    # Common descriptions
    COMMON_DESCS = {
        "det": "Matrix determinant",
        "inv": "Matrix inverse",
        "svd": "Singular value decomposition",
        "qr": "QR decomposition",
        "eig": "Eigenvalues and eigenvectors",
        "fft": "Fast Fourier transform",
        "ifft": "Inverse FFT",
        "mean": "Arithmetic mean",
        "std": "Standard deviation",
        "var": "Variance",
        "median": "Median",
        "sum": "Sum",
        "prod": "Product",
        "solve": "Solve equations",
        "integrate": "Integration",
        "diff": "Differentiation",
        "limit": "Limit",
        "series": "Series expansion",
        "factor": "Factorization",
        "expand": "Expand expression",
        "simplify": "Simplify expression",
        "prove": "Prove theorem",
        "sat": "Satisfiability check",
        "optimize": "Optimization",
        "convert": "Unit conversion",
        "check": "Dimensional check",
        "measure": "Geometry measure",
        "distance": "Distance calculation",
        "plot2d": "2D plot",
        "plot3d": "3D surface plot",
        "latex": "LaTeX rendering",
        "hint": "Progressive hint",
        "steps": "Step-by-step solution",
        "verify": "Verify step",
        "explain": "Explain step",
        "chain": "Chain reasoning",
    }

    if cmd_name in COMMON_DESCS:
        return COMMON_DESCS[cmd_name]

    # Strip prefix and check again
    for prefix in ["np_", "mp_", "sp_", "scipy_", "sig_"]:
        if cmd_name.startswith(prefix):
            base = cmd_name[len(prefix) :]
            if base in COMMON_DESCS:
                return COMMON_DESCS[base]
            # Generate from base name
            words = base.replace("_", " ").split()
            return " ".join(w.capitalize() for w in words)

    # Generate from command name
    words = cmd_name.replace("_", " ").replace("-", " ").split()
    return " ".join(w.capitalize() for w in words)


def generate_fallback_routes() -> list[Route]:
    """Generate routes for all commands not yet covered by hand-crafted routes.

    These routes have LOW PRIORITY (1) so hand-crafted routes (priority 10+)
    always take precedence.

    Uses smart extractors when command argument schemas are available,
    falling back to extract_generic for commands without schema info.
    """
    import os

    # Get existing subcommands from ROUTES
    existing_routes: dict[str, set[str]] = {}
    for r in ROUTES:
        if r.script not in existing_routes:
            existing_routes[r.script] = set()
        existing_routes[r.script].add(r.subcommand)

    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Load command schemas for smart extraction
    schemas = _get_command_schemas()

    auto_routes: list[Route] = []

    for script_name, category in SCRIPT_CATEGORIES.items():
        script_path = os.path.join(script_dir, script_name)

        # Get all subcommands from the script
        all_subcommands = _extract_script_subcommands(script_path)

        # Get existing routes for this script
        routed = existing_routes.get(script_name, set())

        # Get schema for this script (command -> arg_names)
        script_schema = schemas.get(script_name, {})

        # Generate routes for missing commands
        for cmd in all_subcommands:
            if cmd not in routed:
                # Get expected args for this command from schema
                arg_names = script_schema.get(cmd, [])

                # Use smart extractor if we have schema info, otherwise generic
                if arg_names:
                    extractor = create_smart_extractor(arg_names)
                else:
                    extractor = extract_generic

                auto_routes.append(
                    Route(
                        pattern=_generate_auto_pattern(cmd, script_name),
                        script=script_name,
                        subcommand=cmd,
                        arg_extractor=extractor,
                        description=_generate_auto_description(cmd, script_name),
                        category=category,
                        priority=1,  # Low priority - hand-crafted routes take precedence
                    )
                )

    return auto_routes


# Extend ROUTES with auto-generated fallback routes
ROUTES.extend(generate_fallback_routes())


# =============================================================================
# Command Builders - Dispatch Table Pattern
# =============================================================================


def _append_optional_arg(cmd_parts: list[str], args: dict, key: str, flag: str) -> None:
    """Append optional argument if present and non-default."""
    if args.get(key):
        cmd_parts.append(f"--{flag} {args[key]}")


def _append_optional_with_default(
    cmd_parts: list[str], args: dict, key: str, flag: str, default: Any
) -> None:
    """Append optional argument if different from default."""
    if args.get(key, default) != default:
        cmd_parts.append(f"--{flag} {args[key]}")


def _build_sympy_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build SymPy command arguments."""
    EXPR_SUBCOMMANDS = {
        "solve", "integrate", "diff", "simplify",
        "limit", "series", "factor", "expand",
    }
    MATRIX_SUBCOMMANDS = {
        "det", "eigenvalues", "eigenvectors", "inverse",
        "rref", "nullspace", "rank", "transpose",
    }

    if subcommand in EXPR_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("expression", "")}"')
        _append_optional_arg(cmd_parts, args, "var", "var")
        _append_optional_with_default(cmd_parts, args, "order", "order", 1)
        if args.get("bounds"):
            cmd_parts.append(f"--bounds {args['bounds'][0]} {args['bounds'][1]}")
        _append_optional_arg(cmd_parts, args, "to", "to")
        _append_optional_arg(cmd_parts, args, "dir", "dir")
        _append_optional_with_default(cmd_parts, args, "domain", "domain", "complex")
        _append_optional_with_default(cmd_parts, args, "strategy", "strategy", "auto")
        _append_optional_with_default(cmd_parts, args, "point", "point", "0")
    elif subcommand in MATRIX_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("matrix", "")}"')


def _build_pint_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build Pint unit conversion command arguments."""
    if subcommand == "convert":
        cmd_parts.append(f'"{args.get("quantity", "")}"')
        cmd_parts.append(f'--to "{args.get("to", "")}"')
    elif subcommand == "check":
        cmd_parts.append(f'"{args.get("unit1", "")}"')
        cmd_parts.append(f'--against "{args.get("against", "")}"')


def _build_shapely_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build Shapely geometry command arguments."""
    if subcommand == "measure":
        cmd_parts.append(args.get("what", "all"))
        cmd_parts.append(f'--geom "{args.get("geom", "")}"')
    elif subcommand == "op":
        cmd_parts.append(args.get("operation", "intersection"))
        cmd_parts.append(f'--g1 "{args.get("g1", "")}"')
        if args.get("g2"):
            cmd_parts.append(f'--g2 "{args.get("g2", "")}"')
    elif subcommand == "pred":
        cmd_parts.append(args.get("predicate", "contains"))
        cmd_parts.append(f'--g1 "{args.get("g1", "")}"')
        cmd_parts.append(f'--g2 "{args.get("g2", "")}"')
    elif subcommand == "distance":
        cmd_parts.append(f'--g1 "{args.get("g1", "")}"')
        cmd_parts.append(f'--g2 "{args.get("g2", "")}"')


def _build_z3_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build Z3 solver command arguments."""
    if subcommand == "prove":
        cmd_parts.append(f'"{args.get("theorem", "")}"')
        if args.get("vars"):
            cmd_parts.append(f"--vars {' '.join(args['vars'])}")
        if args.get("var_type"):
            cmd_parts.append(f"--type {args['var_type']}")
    elif subcommand == "sat":
        cmd_parts.append(f'"{args.get("constraints", "")}"')
        if args.get("var_type"):
            cmd_parts.append(f"--type {args['var_type']}")
    elif subcommand == "optimize":
        cmd_parts.append(f'"{args.get("objective", "")}"')
        cmd_parts.append(f'--constraints "{args.get("constraints", "")}"')
        cmd_parts.append(f"--direction {args.get('direction', 'minimize')}")
        if args.get("var_type"):
            cmd_parts.append(f"--type {args['var_type']}")


def _build_scratchpad_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build Math Scratchpad command arguments."""
    cmd_parts.append(f'"{args.get("step", "")}"')


def _build_tutor_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build Math Tutor command arguments."""
    if subcommand == "hint":
        cmd_parts.append(f'"{args.get("problem", "")}"')
        if args.get("level", 1) != 1:
            cmd_parts.append(f"--level {args['level']}")
    elif subcommand == "steps":
        cmd_parts.append(f'"{args.get("problem", "")}"')
        if args.get("operation", "solve") != "solve":
            cmd_parts.append(f"--operation {args['operation']}")
    elif subcommand == "generate":
        cmd_parts.append(f"--topic {args.get('topic', 'algebra')}")
        cmd_parts.append(f"--difficulty {args.get('difficulty', 2)}")


def _build_plot_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build Math Plot command arguments."""
    if subcommand == "plot2d":
        cmd_parts.append(f'"{args.get("expression", "")}"')
        cmd_parts.append(f"--var {args.get('var', 'x')}")
        range_vals = args.get("range", [-10, 10])
        cmd_parts.append(f"--range {range_vals[0]} {range_vals[1]}")
        cmd_parts.append(f"--output {args.get('output', '/tmp/plot.png')}")
    elif subcommand == "plot3d":
        cmd_parts.append(f'"{args.get("expression", "")}"')
        cmd_parts.append(f"--xvar {args.get('xvar', 'x')}")
        cmd_parts.append(f"--yvar {args.get('yvar', 'y')}")
        cmd_parts.append(f"--range {args.get('range', 5)}")
        cmd_parts.append(f"--output {args.get('output', '/tmp/surface.html')}")
    elif subcommand == "latex":
        cmd_parts.append(f'"{args.get("equation", "")}"')
        cmd_parts.append(f"--output {args.get('output', '/tmp/equation.png')}")


def _build_numpy_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build NumPy command arguments."""
    LINALG_SUBCOMMANDS = {
        "det", "inv", "pinv", "eig", "svd", "solve",
        "lstsq", "norm", "cond", "qr", "cholesky",
    }
    STATS_SUBCOMMANDS = {"mean", "std", "var", "median", "percentile", "sum", "prod"}
    FFT_SUBCOMMANDS = {"fft", "ifft", "rfft"}

    if subcommand in LINALG_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("matrix", "")}"')
    elif subcommand in STATS_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("array", "")}"')
    elif subcommand in FFT_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("signal", "")}"')


def _build_scipy_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build SciPy command arguments."""
    OPTIMIZE_SUBCOMMANDS = {"minimize", "minimize_scalar", "curve_fit", "linprog"}
    ROOT_SUBCOMMANDS = {"root", "fsolve", "brentq"}
    INTEGRATE_SUBCOMMANDS = {"quad", "dblquad"}
    ODE_SUBCOMMANDS = {"odeint", "solve_ivp"}
    DIST_SUBCOMMANDS = {"norm", "t", "chi2"}
    STAT_TEST_SUBCOMMANDS = {"ttest_1samp", "kstest", "pearsonr"}

    if subcommand in OPTIMIZE_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("func", "")}"')
        if args.get("x0"):
            cmd_parts.append(f'"{args.get("x0", "0")}"')
        if args.get("method") and args["method"] != "BFGS":
            cmd_parts.append(f"--method {args['method']}")
    elif subcommand in ROOT_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("func", "")}"')
        cmd_parts.append(f'"{args.get("x0", "1")}"')
    elif subcommand in INTEGRATE_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("func", "")}"')
        cmd_parts.append(f'"{args.get("a", "0")}"')
        cmd_parts.append(f'"{args.get("b", "1")}"')
    elif subcommand in ODE_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("func", "")}"')
        cmd_parts.append(f'"{args.get("y0", "1")}"')
        cmd_parts.append(f'--t_span "{args.get("t_span", "0,10")}"')
    elif subcommand in DIST_SUBCOMMANDS:
        cmd_parts.append(args.get("func", "pdf"))
        cmd_parts.append(f'"{args.get("x", "0")}"')
    elif subcommand in STAT_TEST_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("data", "")}"')
        if args.get("popmean"):
            cmd_parts.append(f"--popmean {args['popmean']}")


def _append_mpmath_dps(cmd_parts: list[str], args: dict[str, Any]) -> None:
    """Append --dps if non-default precision specified."""
    if args.get("dps") and args["dps"] != 50:
        cmd_parts.append(f"--dps {args['dps']}")


def _build_mpmath_command(
    cmd_parts: list[str], subcommand: str, args: dict[str, Any]
) -> None:
    """Build mpmath command arguments."""
    CONSTANT_SUBCOMMANDS = {"pi", "e", "euler", "phi", "catalan", "apery"}
    FUNC_SUBCOMMANDS = {
        "mp_sqrt", "mp_exp", "mp_log", "mp_power", "mp_factorial",
        "mp_erf", "mp_besselj", "mp_polylog", "mp_hyp2f1", "mp_beta",
    }
    # Argument name and default for special functions
    SPECIAL_FUNCS = {"mp_gamma": ("x", "5"), "mp_zeta": ("s", "2")}

    if subcommand in CONSTANT_SUBCOMMANDS:
        _append_mpmath_dps(cmd_parts, args)
    elif subcommand in FUNC_SUBCOMMANDS:
        cmd_parts.append(f'"{args.get("x", "1")}"')
        _append_mpmath_dps(cmd_parts, args)
    elif subcommand in SPECIAL_FUNCS:
        arg_name, default = SPECIAL_FUNCS[subcommand]
        cmd_parts.append(f'"{args.get(arg_name, default)}"')
        _append_mpmath_dps(cmd_parts, args)


# Dispatch table mapping script names to builder functions
COMMAND_BUILDERS: dict[str, Callable[[list[str], str, dict[str, Any]], None]] = {
    "sympy_compute.py": _build_sympy_command,
    "pint_compute.py": _build_pint_command,
    "shapely_compute.py": _build_shapely_command,
    "z3_solve.py": _build_z3_command,
    "math_scratchpad.py": _build_scratchpad_command,
    "math_tutor.py": _build_tutor_command,
    "math_plot.py": _build_plot_command,
    "numpy_compute.py": _build_numpy_command,
    "scipy_compute.py": _build_scipy_command,
    "mpmath_compute.py": _build_mpmath_command,
}


def _apply_fallback_args(
    cmd_parts: list[str], script: str, args: dict[str, Any]
) -> None:
    """Apply fallback argument handling for unhandled scripts/subcommands."""
    if len(cmd_parts) != 5:  # Only apply if no args were added
        return

    # Check if we have useful extracted data
    if args.get("matrix"):
        cmd_parts.append(f'"{args["matrix"]}"')
    elif args.get("array"):
        cmd_parts.append(f'"{args["array"]}"')
    elif args.get("expression"):
        cmd_parts.append(f'"{args["expression"]}"')
    elif args.get("input") and args["input"] != "":
        # For generic routes, pass input as quoted argument
        # But only if it looks like a value, not a full sentence
        input_val = args["input"]
        # Don't pass long sentences as arguments
        if len(input_val) < 100 and not re.search(
            r"\b(what|how|can|please|help|the)\b", input_val, re.IGNORECASE
        ):
            cmd_parts.append(f'"{input_val}"')

    # Add dps if present for mpmath commands (but not default value)
    if args.get("dps") and script == "mpmath_compute.py" and args["dps"] != 50:
        cmd_parts.append(f"--dps {args['dps']}")


# =============================================================================
# Routing Logic
# =============================================================================


def build_command(script: str, subcommand: str, args: dict[str, Any]) -> str:
    """Build CLI command from route and arguments.

    Uses dispatch table pattern to route to script-specific builders,
    keeping complexity low and logic modular.
    """
    cmd_parts = ["uv", "run", "python", f"scripts/{script}", subcommand]

    # Dispatch to script-specific builder if available
    builder = COMMAND_BUILDERS.get(script)
    if builder:
        builder(cmd_parts, subcommand, args)

    # Apply fallback for unhandled cases
    _apply_fallback_args(cmd_parts, script, args)

    return " ".join(cmd_parts)


def route(intent: str) -> RouteMatch:
    """Route user intent to CLI command.

    Args:
        intent: Natural language math request

    Returns:
        RouteMatch with command and alternatives
    """
    intent_lower = intent.lower()

    matches: list[tuple[Route, float]] = []

    for r in ROUTES:
        pattern = re.compile(r.pattern, re.IGNORECASE)
        match = pattern.search(intent_lower)
        if match:
            # Calculate confidence based on match specificity
            match_len = match.end() - match.start()
            specificity = match_len / len(intent_lower) if intent_lower else 0
            confidence = min(0.5 + specificity * 0.5 + (r.priority / 100), 1.0)
            matches.append((r, confidence))

    if not matches:
        return RouteMatch(
            command="",
            script="",
            subcommand="",
            args={},
            confidence=0.0,
            pattern="",
            alternatives=[],
        )

    # Sort by confidence (and priority as tiebreaker)
    matches.sort(key=lambda x: (x[1], x[0].priority), reverse=True)

    best_route, best_confidence = matches[0]
    args = best_route.arg_extractor(intent)
    command = build_command(best_route.script, best_route.subcommand, args)

    # Build alternatives
    alternatives = []
    for r, conf in matches[1:4]:  # Top 3 alternatives
        alt_args = r.arg_extractor(intent)
        alt_cmd = build_command(r.script, r.subcommand, alt_args)
        alternatives.append(
            {
                "command": alt_cmd,
                "script": r.script,
                "subcommand": r.subcommand,
                "confidence": conf,
                "description": r.description,
            }
        )

    return RouteMatch(
        command=command,
        script=best_route.script,
        subcommand=best_route.subcommand,
        args=args,
        confidence=best_confidence,
        pattern=best_route.pattern,
        alternatives=alternatives,
    )


def list_commands(category: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """List all available commands.

    Args:
        category: Optional category filter

    Returns:
        Dict mapping category to list of command info
    """
    result: dict[str, list[dict[str, Any]]] = {}

    for r in ROUTES:
        if category and r.category != category:
            continue

        if r.category not in result:
            result[r.category] = []

        result[r.category].append(
            {
                "script": r.script,
                "subcommand": r.subcommand,
                "description": r.description,
                "pattern": r.pattern,
            }
        )

    return result


# =============================================================================
# CLI Interface
# =============================================================================


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Deterministic router for math cognitive stack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Route command
    route_p = subparsers.add_parser("route", help="Route a math intent to CLI command")
    route_p.add_argument("intent", help="Natural language math request")
    route_p.add_argument("--verbose", "-v", action="store_true", help="Show confidence details")

    # List command
    list_p = subparsers.add_parser("list", help="List available commands")
    list_p.add_argument(
        "--category",
        "-c",
        help="Filter by category (sympy, pint, shapely, z3, tutor, plot, scratchpad)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    try:
        if args.command == "route":
            result = route(args.intent)

            if result.confidence == 0:
                output = {
                    "error": "No matching route found",
                    "intent": args.intent,
                    "suggestion": "Try rephrasing or use 'list' to see available commands",
                }
            else:
                output = {
                    "command": result.command,
                    "script": result.script,
                    "subcommand": result.subcommand,
                    "confidence": round(result.confidence, 3),
                }

                if args.verbose:
                    output["pattern"] = result.pattern
                    output["args"] = result.args
                    output["alternatives"] = result.alternatives

            print(json.dumps(output, indent=2))

        elif args.command == "list":
            result = list_commands(args.category)
            print(json.dumps(result, indent=2))

        else:
            print(json.dumps({"error": f"Unknown command: {args.command}"}))
            sys.exit(1)

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Smart Argument Extraction
# =============================================================================


# =============================================================================
# Smart Extraction Dispatch Helpers
# =============================================================================

# Argument categories for dispatch
_ARRAY_ARGS = frozenset(["matrix", "A", "b", "data", "signal", "array"])
_BOUNDS_ARGS = frozenset(["lower", "upper", "a", "b", "bounds", "x_min", "x_max"])
_FUNCTION_ARGS = frozenset(["func", "expression", "expr"])
_INTEGER_ARGS = frozenset(["n", "k", "m", "axis", "order", "degree"])
_POSITIONAL_ARGS = frozenset(["x", "a", "b", "y", "z", "v", "t", "c", "q", "s", "p", "value"])


def _extract_explicit_array_assignment(
    intent: str, arg: str, result: dict, used_values: set
) -> bool:
    """Try to extract explicit array assignment like arg=[[...]] or arg=[...]."""
    explicit_start = re.search(
        rf"\b{re.escape(arg)}\s*=\s*\[\[", intent, re.IGNORECASE
    )
    if explicit_start:
        start_pos = explicit_start.end() - 2
        value = _extract_nested_brackets(intent[start_pos:])
        if value:
            result[arg] = value
            used_values.add(value)
            return True
    # Try single bracket
    explicit_single_pattern = rf"\b{re.escape(arg)}\s*=\s*(\[[^\]]+\])"
    match = re.search(explicit_single_pattern, intent, re.IGNORECASE)
    if match:
        result[arg] = match.group(1)
        used_values.add(match.group(1))
        return True
    return False


def _extract_explicit_complex_assignment(
    intent: str, arg: str, result: dict, used_values: set
) -> bool:
    """Try to extract explicit complex number assignment like z=3+4j."""
    complex_pattern = rf"\b{re.escape(arg)}\s*=\s*(-?[\d\.]+[+-][\d\.]*[ij])"
    match = re.search(complex_pattern, intent, re.IGNORECASE)
    if match:
        result[arg] = match.group(1)
        used_values.add(match.group(1))
        return True
    return False


def _extract_explicit_value_assignment(
    intent: str, arg: str, result: dict, used_values: set
) -> bool:
    """Try to extract explicit value assignment like arg=value."""
    explicit_pattern = rf"\b{re.escape(arg)}\s*=\s*(-?[\d\.]+(?:[eE][+-]?\d+)?|[\w\.]+)"
    match = re.search(explicit_pattern, intent, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        result[arg] = value
        used_values.add(value)
        return True
    return False


def _extract_explicit_assignments(
    intent: str, expected_args: list[str], result: dict, used_values: set
) -> None:
    """PASS 1: Extract explicit assignments (arg=value patterns)."""
    for arg in expected_args:
        if arg in result:
            continue
        
        if arg in _ARRAY_ARGS:
            if _extract_explicit_array_assignment(intent, arg, result, used_values):
                continue
        
        if arg == "z":
            if _extract_explicit_complex_assignment(intent, arg, result, used_values):
                continue
        
        _extract_explicit_value_assignment(intent, arg, result, used_values)


def _extract_array_typed_args(
    intent: str, expected_set: set, result: dict, used_values: set
) -> None:
    """Extract matrix/array typed arguments."""
    for arg in _ARRAY_ARGS:
        if arg in expected_set and arg not in result:
            array_value = _extract_array(intent, arg, used_values)
            if array_value:
                result[arg] = array_value
                used_values.add(array_value)


def _extract_bounds_typed_args(
    intent: str, expected_args: list[str], expected_set: set, result: dict, used_values: set
) -> None:
    """Extract bounds typed arguments."""
    if not (expected_set & _BOUNDS_ARGS):
        return
    bounds = _extract_bounds(intent, expected_args)
    for k, v in bounds.items():
        if k in expected_set and k not in result:
            result[k] = v
            used_values.add(v)


def _extract_function_typed_args(intent: str, expected_set: set, result: dict) -> None:
    """Extract function/expression typed arguments."""
    for arg in _FUNCTION_ARGS:
        if arg in expected_set and arg not in result:
            func_value = _extract_function(intent, arg)
            if func_value:
                result[arg] = func_value


def _extract_integer_typed_args(
    intent: str, expected_set: set, result: dict, used_values: set
) -> None:
    """Extract integer typed arguments."""
    for arg in _INTEGER_ARGS:
        if arg in expected_set and arg not in result:
            int_value = _extract_integer_arg(intent, arg)
            if int_value:
                result[arg] = int_value
                used_values.add(int_value)


def _try_extract_arg(
    arg: str, extractor, intent: str, expected_set: set, result: dict
) -> None:
    """Try to extract a single argument using its extractor."""
    if arg in expected_set and arg not in result:
        value = extractor(intent)
        if value:
            result[arg] = value


def _extract_special_typed_args(
    intent: str, intent_lower: str, expected_set: set, result: dict
) -> None:
    """Extract special typed arguments (dps, var, to, point, x0)."""
    # Each special arg has its own extractor
    _try_extract_arg("dps", _extract_dps, intent_lower, expected_set, result)
    _try_extract_arg("var", _extract_variable, intent, expected_set, result)
    _try_extract_arg("to", _extract_limit_to, intent, expected_set, result)
    _try_extract_arg("point", _extract_point, intent, expected_set, result)
    _try_extract_arg("x0", _extract_x0, intent, expected_set, result)


def _extract_typed_args(
    intent: str, intent_lower: str, expected_args: list[str], result: dict, used_values: set
) -> None:
    """PASS 2: Extract by argument type patterns."""
    expected_set = set(expected_args)
    
    # Extract each type category
    _extract_special_typed_args(intent, intent_lower, expected_set, result)
    _extract_array_typed_args(intent, expected_set, result, used_values)
    _extract_bounds_typed_args(intent, expected_args, expected_set, result, used_values)
    _extract_function_typed_args(intent, expected_set, result)
    _extract_integer_typed_args(intent, expected_set, result, used_values)


def smart_extract(intent: str, expected_args: list[str] | None) -> dict[str, str]:
    """Extract argument values from natural language intent.

    Args:
        intent: Natural language math request
        expected_args: List of argument names to extract (e.g., ["x", "dps", "matrix"])

    Returns:
        Dictionary mapping argument names to extracted string values
    """
    # Handle edge cases
    if expected_args is None or len(expected_args) == 0:
        return {}

    if not intent or not intent.strip():
        return {}

    # Normalize whitespace but preserve case for later
    intent_normalized = " ".join(intent.split())
    intent_lower = intent_normalized.lower()

    result: dict[str, str] = {}
    used_values: set[str] = set()

    # PASS 1: Extract explicit assignments (arg=value patterns)
    _extract_explicit_assignments(intent_normalized, expected_args, result, used_values)

    # PASS 2: Extract by argument type patterns
    _extract_typed_args(intent_normalized, intent_lower, expected_args, result, used_values)

    # PASS 3: Complex number extraction for z
    if "z" in expected_args and "z" not in result:
        z_value = _extract_complex(intent_normalized)
        if z_value:
            result["z"] = z_value
            used_values.add(z_value)

    # PASS 4: Extract positional value arguments
    value_args = [a for a in expected_args if a in _POSITIONAL_ARGS]
    if value_args:
        positional_values = _extract_positional_values(
            intent_normalized, value_args, result, used_values
        )
        for k, v in positional_values.items():
            if k not in result:
                result[k] = v

    return result


def _extract_dps(intent_lower: str) -> str | None:
    """Extract precision/dps value from intent."""
    # Pattern: dps=N or dps = N
    match = re.search(r"dps\s*=\s*(\d+)", intent_lower)
    if match:
        return match.group(1)

    # Pattern: N digits or N digit precision
    match = re.search(r"(\d+)\s*digit(?:s)?(?:\s+precision)?", intent_lower)
    if match:
        return match.group(1)

    # Pattern: precision N or precision=N
    match = re.search(r"precision\s*=?\s*(\d+)", intent_lower)
    if match:
        return match.group(1)

    # Pattern: to N decimal places
    match = re.search(r"to\s+(\d+)\s+decimal\s+place", intent_lower)
    if match:
        return match.group(1)

    return None


def _extract_brackets_from_position(text: str, start: int) -> str | None:
    """Extract balanced bracket structure starting at given position."""
    if start >= len(text) or text[start] != "[":
        return None

    depth = 0
    i = start
    while i < len(text):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1

    return None


def _try_explicit_array_extract(intent: str, arg_name: str) -> str | None:
    """Try explicit array assignment like arg=[[...]] or arg=[...]."""
    explicit_start_pattern = rf"\b{re.escape(arg_name)}\s*=\s*\["
    match = re.search(explicit_start_pattern, intent, re.IGNORECASE)
    if match:
        bracket_start = match.end() - 1
        value = _extract_brackets_from_position(intent, bracket_start)
        if value:
            return value
    
    # Fallback: single brackets
    explicit_single_pattern = rf"\b{re.escape(arg_name)}\s*=\s*(\[[^\]]+\])"
    match = re.search(explicit_single_pattern, intent, re.IGNORECASE)
    return match.group(1) if match else None


def _try_single_bracket_extract(intent: str, used_values: set[str]) -> str | None:
    """Try to extract a single bracket array [...] not in used_values."""
    for match in re.finditer(r"(\[[^\[\]]+\])", intent):
        value = match.group(1)
        if value not in used_values:
            return value
    return None


def _extract_array(intent: str, arg_name: str, used_values: set[str]) -> str | None:
    """Extract array or matrix from intent."""
    # First check for explicit assignment
    explicit_value = _try_explicit_array_extract(intent, arg_name)
    if explicit_value:
        return explicit_value

    # Matrix/A: look for [[...]] pattern
    if arg_name in ["matrix", "A"]:
        matrix_value = _extract_nested_brackets(intent)
        if matrix_value and matrix_value not in used_values:
            return matrix_value
        return None

    # data/signal/array: can also be nested arrays or single brackets
    if arg_name in ["data", "signal", "array"]:
        nested_value = _extract_nested_brackets(intent)
        if nested_value and nested_value not in used_values:
            return nested_value
        return _try_single_bracket_extract(intent, used_values)

    # b: single bracket only
    if arg_name == "b":
        return _try_single_bracket_extract(intent, used_values)

    return None


def _extract_nested_brackets(text: str) -> str | None:
    """Extract nested bracket structure like [[1,2],[3,4]] using balanced matching."""
    # Find start of nested brackets
    start_idx = text.find("[[")
    if start_idx == -1:
        return None

    # Count brackets to find matching end
    depth = 0
    i = start_idx
    while i < len(text):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]
        i += 1

    return None


def _assign_bounds_to_args(
    result: dict[str, str], lower: str, upper: str, expected_args: list[str]
) -> None:
    """Assign lower/upper bounds to appropriate argument names."""
    if "lower" in expected_args and "upper" in expected_args:
        result["lower"] = lower
        result["upper"] = upper
    elif "a" in expected_args and "b" in expected_args:
        result["a"] = lower
        result["b"] = upper
    elif "x_min" in expected_args and "x_max" in expected_args:
        result["x_min"] = lower
        result["x_max"] = upper


def _extract_from_to_bounds(intent_lower: str, expected_args: list[str], result: dict) -> None:
    """Extract from 'from X to Y' pattern."""
    match = re.search(
        r"from\s+(-?[\d\.]+|[\-]?(?:pi|e|oo|inf|infinity))\s+to\s+(-?[\d\.]+|[\-]?(?:pi|e|oo|inf|infinity))",
        intent_lower,
    )
    if match:
        lower = _normalize_infinity(match.group(1))
        upper = _normalize_infinity(match.group(2))
        _assign_bounds_to_args(result, lower, upper, expected_args)


def _extract_interval_bounds(intent_lower: str, expected_args: list[str], result: dict) -> None:
    """Extract from 'interval [X, Y]' pattern."""
    if result:  # Skip if already have bounds
        return
    match = re.search(
        r"(?:interval|range)\s*[\(\[]\s*(-?[\d\.]+|pi|e)\s*,\s*(-?[\d\.]+|pi|e)\s*[\)\]]",
        intent_lower,
    )
    if match:
        lower = match.group(1)
        upper = match.group(2)
        _assign_bounds_to_args(result, lower, upper, expected_args)


def _extract_bracket_bounds(intent: str, expected_args: list[str], result: dict) -> None:
    """Extract bounds from bracket notation [X, Y]."""
    if "bounds" not in expected_args or "bounds" in result:
        return
    
    match = re.search(r"\[([^\]]+)\]", intent)
    if match and "," in match.group(1):
        result["bounds"] = match.group(0)
    
    if "bounds" not in result:
        match = re.search(r"over\s+(\[[^\]]+\])", intent)
        if match:
            result["bounds"] = match.group(1)


def _extract_bounds(intent: str, expected_args: list[str]) -> dict[str, str]:
    """Extract bounds from intent."""
    result: dict[str, str] = {}
    intent_lower = intent.lower()

    _extract_from_to_bounds(intent_lower, expected_args, result)
    _extract_bracket_bounds(intent, expected_args, result)
    _extract_interval_bounds(intent_lower, expected_args, result)

    return result


def _normalize_infinity(value: str) -> str:
    """Normalize infinity representations."""
    value_lower = value.lower()
    if value_lower in ["infinity", "inf"]:
        return "oo"
    if value_lower in ["-infinity", "-inf"]:
        return "-oo"
    return value


def _extract_function(intent: str, arg_name: str) -> str | None:
    """Extract function/expression from intent."""
    # Remove command prefixes
    cleaned = intent
    for prefix in [
        "minimize",
        "maximize",
        "integrate",
        "differentiate",
        "diff",
        "derivative of",
        "integral of",
        "root find",
        "sympy solve",
        "solve",
    ]:
        pattern = rf"^{re.escape(prefix)}\s+"
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Remove suffixes like "starting from X", "from X to Y", "with respect to X"
    cleaned = re.sub(r"\s+starting\s+from\s+.+$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+from\s+[\d\.]+\s+to\s+[\d\.]+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+with\s+respect\s+to\s+\w+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+wrt\s+\w+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+and\s+explain.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+and\s+then\s+.*$", "", cleaned, flags=re.IGNORECASE)

    # Handle lambda style: "lambda x: expr"
    lambda_match = re.search(
        r"lambda\s+\w+\s*:\s*(.+?)(?:\s+from|\s+starting|$)", cleaned, re.IGNORECASE
    )
    if lambda_match:
        expr = lambda_match.group(1).strip()
        return _normalize_expression(expr)

    # Handle ODE style: "dy/dt = expr" or "y' = expr"
    ode_match = re.search(r"(?:dy/dt|y')\s*=\s*(.+?)(?:\s+y0|\s+from|$)", cleaned, re.IGNORECASE)
    if ode_match:
        return ode_match.group(1).strip()

    # Handle "of expr" pattern
    of_match = re.search(r"\bof\s+(.+?)(?:\s+as\s+|\s+around\s+|$)", cleaned, re.IGNORECASE)
    if of_match:
        expr = of_match.group(1).strip()
        if _looks_like_expression(expr):
            return _normalize_expression(expr)

    # Clean remaining text as expression
    cleaned = cleaned.strip()

    # If it looks like an expression, return it
    if cleaned and _looks_like_expression(cleaned):
        return _normalize_expression(cleaned)

    return None


def _looks_like_expression(text: str) -> bool:
    """Check if text looks like a mathematical expression."""
    # Contains math operators or function calls
    if re.search(r"[\+\-\*/\^]|[a-z]\s*\(|[a-z]\*\*\d", text, re.IGNORECASE):
        return True
    # Contains variables with exponents
    if re.search(r"[a-z]\s*\*\*\s*\d", text, re.IGNORECASE):
        return True
    # Just a variable
    if re.match(r"^[a-z]$", text, re.IGNORECASE):
        return True
    return False


def _normalize_expression(expr: str) -> str:
    """Normalize expression: convert ^ to ** and clean up."""
    return expr.replace("^", "**")


def _extract_variable(intent: str) -> str | None:
    """Extract variable name from intent."""
    # Pattern: with respect to X or wrt X
    match = re.search(r"(?:with\s+respect\s+to|wrt)\s+([a-z])\b", intent, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # Pattern: as X -> (for limits)
    match = re.search(r"\bas\s+([a-z])\s*(?:->|approaches?)", intent, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # Pattern: f(x) = ... extract x as variable
    match = re.search(r"f\(([a-z])\)\s*=", intent, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # Pattern: look for variable in function call like sin(t)
    match = re.search(r"\b(?:sin|cos|tan|exp|log|sqrt)\s*\(\s*([a-z])\s*\)", intent, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    return None


# Integer argument extraction patterns by arg name
_INTEGER_N_PATTERNS = [
    r"(\d+)(?:st|nd|rd|th)\b",  # Nth ordinal
    r"order\s+(\d+)",  # order N
    r"degree\s+(\d+)",  # degree N
    r"(?:factorial|fibonacci|prime|bernoulli)\s+(?:of\s+)?(\d+)",  # func of N
    r"(?:factorial|fibonacci|prime|bernoulli)\s*\(\s*(\d+)\s*\)",  # func(N)
    r"\bis\s+(\d+)\s+prime\b",  # is N prime
]


def _try_match_patterns(patterns: list[str], intent_lower: str) -> str | None:
    """Try each pattern and return first match."""
    for pattern in patterns:
        match = re.search(pattern, intent_lower)
        if match:
            return match.group(1)
    return None


def _extract_integer_arg(intent: str, arg_name: str) -> str | None:
    """Extract integer argument like n, k, m, axis, order, degree."""
    intent_lower = intent.lower()

    # Pattern: explicit arg=N
    match = re.search(rf"\b{arg_name}\s*=\s*(-?\d+)", intent, re.IGNORECASE)
    if match:
        return match.group(1)

    # Dispatch by arg name
    if arg_name == "n":
        return _try_match_patterns(_INTEGER_N_PATTERNS, intent_lower)
    
    if arg_name == "axis":
        match = re.search(r"axis\s*(-?\d+)", intent_lower)
        return match.group(1) if match else None
    
    if arg_name == "m":
        match = re.search(r"(?:mod|modulus)\s+(\d+)", intent_lower)
        return match.group(1) if match else None
    
    if arg_name == "order":
        match = re.search(r"order\s+(\d+)", intent_lower)
        return match.group(1) if match else None

    return None


def _extract_limit_to(intent: str) -> str | None:
    """Extract the 'to' value for limits."""
    intent_lower = intent.lower()

    # Pattern: as x -> VALUE or x approaches VALUE
    match = re.search(
        r"(?:->|approaches?|to)\s*(-?[\d\.]+|oo|inf|infinity|-oo|-inf|-infinity|pi|e)", intent_lower
    )
    if match:
        value = match.group(1)
        return _normalize_infinity(value)

    return None


def _extract_point(intent: str) -> str | None:
    """Extract point for taylor series (around X, at X, about X)."""
    match = re.search(r"(?:around|at|about)\s*(-?[\d\.]+)", intent, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_x0(intent: str) -> str | None:
    """Extract starting point x0."""
    # Pattern: starting from X, initial guess X, x0=X
    match = re.search(
        r"(?:starting\s+from|initial\s+guess|x0\s*=)\s*([^\s,]+)", intent, re.IGNORECASE
    )
    if match:
        return match.group(1)
    return None


def _extract_from_func_call(
    intent: str, value_args: list[str], existing: dict[str, str], used_values: set[str]
) -> dict[str, str]:
    """Extract values from function call syntax like func(val1, val2)."""
    result: dict[str, str] = {}
    func_call_match = re.search(r"\b\w+\s*\(\s*([^)]+)\s*\)", intent)
    if not func_call_match:
        return result
    
    args_str = func_call_match.group(1)
    parts = [p.strip() for p in args_str.split(",")]
    valid_parts = [p for p in parts if _is_valid_value(p) and p not in used_values]
    remaining_args = [a for a in value_args if a not in existing]
    
    for i, val in enumerate(valid_parts):
        if i < len(remaining_args):
            result[remaining_args[i]] = val
            used_values.add(val)
    
    return result


def _extract_from_and_pattern(
    intent_lower: str, value_args: list[str], existing: dict[str, str], 
    result: dict[str, str], used_values: set[str]
) -> None:
    """Extract from 'X and Y' pattern (for gcd, lcm)."""
    and_match = re.search(r"of\s+(-?[\d\.]+)\s+and\s+(-?[\d\.]+)", intent_lower)
    if not and_match:
        return
    
    vals = [and_match.group(1), and_match.group(2)]
    remaining_args = [a for a in value_args if a not in existing and a not in result]
    for i, val in enumerate(vals):
        if i < len(remaining_args) and val not in used_values:
            result[remaining_args[i]] = val
            used_values.add(val)


def _extract_from_of_pattern(
    intent_lower: str, value_args: list[str], existing: dict[str, str],
    result: dict[str, str], used_values: set[str]
) -> None:
    """Extract from 'of X' pattern."""
    of_match = re.search(
        r"\bof\s+(-?[\d\.]+(?:[eE][+-]?\d+)?(?:/\d+)?|pi|e|nan)\b", intent_lower
    )
    if not of_match:
        return
    
    val = of_match.group(1)
    remaining_args = [a for a in value_args if a not in existing and a not in result]
    if remaining_args and val not in used_values:
        result[remaining_args[0]] = val
        used_values.add(val)


def _extract_from_at_pattern(
    intent_lower: str, value_args: list[str], existing: dict[str, str],
    result: dict[str, str], used_values: set[str]
) -> None:
    """Extract from 'at X' pattern (for bessel functions)."""
    at_match = re.search(r"\bat\s+(-?[\d\.]+)", intent_lower)
    if not at_match:
        return
    
    val = at_match.group(1)
    if "x" in value_args and "x" not in existing and "x" not in result and val not in used_values:
        result["x"] = val
        used_values.add(val)


def _extract_numeric_fallback(
    intent: str, value_args: list[str], existing: dict[str, str],
    result: dict[str, str], used_values: set[str]
) -> None:
    """Extract first valid numeric values as fallback."""
    remaining_args = [a for a in value_args if a not in existing and a not in result]
    if not remaining_args:
        return
    
    numbers = re.findall(r"(?<![a-z])(-?[\d\.]+(?:[eE][+-]?\d+)?(?:/\d+)?|pi|e)\b", intent)
    valid_numbers = [n for n in numbers if n not in used_values and _is_valid_value(n)]
    
    for i, num in enumerate(valid_numbers):
        if i < len(remaining_args):
            result[remaining_args[i]] = num
            used_values.add(num)


def _extract_positional_values(
    intent: str, value_args: list[str], existing: dict[str, str], used_values: set[str]
) -> dict[str, str]:
    """Extract positional value arguments (x, a, b, y, z, s, etc.)."""
    intent_lower = intent.lower()
    
    # Try function call syntax first
    result = _extract_from_func_call(intent, value_args, existing, used_values)
    
    # Try "X and Y" pattern
    _extract_from_and_pattern(intent_lower, value_args, existing, result, used_values)
    
    # Try "of X" pattern if no results yet
    if not result:
        _extract_from_of_pattern(intent_lower, value_args, existing, result, used_values)
    
    # Try "at X" pattern if no results yet
    if not result:
        _extract_from_at_pattern(intent_lower, value_args, existing, result, used_values)
    
    # Fallback to finding numeric values
    if not result:
        _extract_numeric_fallback(intent, value_args, existing, result, used_values)
    
    return result


def _is_valid_value(text: str) -> bool:
    """Check if text is a valid numeric value or special constant."""
    text = text.strip()
    # Numeric (int, float, scientific)
    if re.match(r"^-?[\d\.]+(?:[eE][+-]?\d+)?$", text):
        return True
    # Special constants
    if text.lower() in ["pi", "e", "nan", "inf", "oo", "infinity"]:
        return True
    # Complex number
    if re.match(r"^-?[\d\.]+[+-][\d\.]*[ij]$", text):
        return True
    # Fraction
    if re.match(r"^\d+/\d+$", text):
        return True
    return False


def _extract_complex(intent: str) -> str | None:
    """Extract complex number from intent."""
    # Pattern: X+Yj or X-Yj or X+Yi (with required imaginary part)
    match = re.search(r"(-?[\d\.]+[+-][\d\.]+[ij])", intent, re.IGNORECASE)
    if match:
        return match.group(1)

    # Pattern: X+Yj where Y can be empty (implied 1)
    match = re.search(r"(-?[\d\.]+[+-][ij])", intent, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


if __name__ == "__main__":
    main()
