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

Requires: sympy (pip install sympy)
"""

import argparse
import asyncio
import json
import signal
import sys
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Optional


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
    dangerous = ['import', 'exec', 'eval', '__', 'open', 'file']
    for d in dangerous:
        if d in expr_str.lower():
            return False, f"Potentially dangerous pattern: {d}"

    # Check balanced parentheses
    count = 0
    for c in expr_str:
        if c == '(':
            count += 1
        elif c == ')':
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
        parse_expr, standard_transformations,
        implicit_multiplication_application,
        convert_xor
    )

    # Validate first
    valid, msg = validate_expression(expr_str)
    if not valid:
        raise ValueError(f"Cannot parse expression '{expr_str}': {msg}")

    # Default symbols
    if local_dict is None:
        local_dict = {
            'x': sympy.Symbol('x'),
            'y': sympy.Symbol('y'),
            'z': sympy.Symbol('z'),
            'n': sympy.Symbol('n', integer=True),
            'k': sympy.Symbol('k', integer=True),
        }

    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,  # Treat ^ as power, not XOR
    )

    try:
        return parse_expr(
            expr_str,
            local_dict=local_dict,
            transformations=transformations,
            evaluate=True
        )
    except Exception as e:
        raise ValueError(f"Cannot parse expression '{expr_str}': {e}")


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


def solve_equation(
    equation: str,
    variable: str = "x",
    domain: str = "complex"
) -> dict:
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
        'x': sympy.Symbol('x', **_domain_assumptions(domain)) if variable != 'x' else var,
        'y': sympy.Symbol('y'),
        'z': sympy.Symbol('z'),
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
    verified = all(
        sympy.simplify(expr.subs(var, sol)) == 0
        for sol in solutions
    ) if solutions else True

    return {
        "solutions": [str(s) for s in solutions],
        "latex": sympy.latex(sympy.Eq(var, solutions[0])) if solutions else "No solution",
        "count": len(solutions),
        "verified": verified
    }


def integrate_expr(
    expr_str: str,
    variable: str = "x",
    lower: str = None,
    upper: str = None
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
            "note": "Integral could not be computed symbolically"
        }

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "definite": definite,
        "computed": True
    }


def differentiate_expr(
    expr_str: str,
    variable: str = "x",
    order: int = 1
) -> dict:
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

    return {
        "result": str(result),
        "latex": sympy.latex(result),
        "order": order
    }


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
        "collect": lambda e: sympy.collect(e, sympy.Symbol('x')),
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
        "simpler": len(str(simplified)) < len(str(expr))
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
                    "error": f"Timeout after {timeout}s - computation too complex"
                }
    except Exception as e:
        return {"success": False, "error": "computation_error", "message": str(e)}


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Symbolic math computation - cognitive prosthetics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Solve command
    solve_p = subparsers.add_parser("solve", help="Solve equations")
    solve_p.add_argument("expression", help="Equation to solve (e.g., 'x**2 - 4 = 0')")
    solve_p.add_argument("--var", default="x", help="Variable to solve for")
    solve_p.add_argument("--domain", default="complex",
                         choices=["real", "complex", "positive", "integer"])

    # Integrate command
    integrate_p = subparsers.add_parser("integrate", help="Integrate expressions")
    integrate_p.add_argument("expression", help="Expression to integrate")
    integrate_p.add_argument("--var", default="x", help="Integration variable")
    integrate_p.add_argument("--bounds", nargs=2, metavar=("LOWER", "UPPER"),
                             help="Bounds for definite integral")

    # Differentiate command
    diff_p = subparsers.add_parser("diff", help="Differentiate expressions")
    diff_p.add_argument("expression", help="Expression to differentiate")
    diff_p.add_argument("--var", default="x", help="Differentiation variable")
    diff_p.add_argument("--order", type=int, default=1, help="Order of derivative")

    # Simplify command
    simplify_p = subparsers.add_parser("simplify", help="Simplify expressions")
    simplify_p.add_argument("expression", help="Expression to simplify")
    simplify_p.add_argument("--strategy", default="auto",
                            choices=["auto", "trig", "rational", "expand", "factor", "all"])

    # Common options
    for p in [solve_p, integrate_p, diff_p, simplify_p]:
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
        else:
            result = {"error": f"Unknown command: {args.command}"}

        # Output
        if getattr(args, 'json', False):
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result, indent=2))

    except Exception as e:
        error_result = {"error": str(e), "command": args.command}
        print(json.dumps(error_result), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
