#!/usr/bin/env python3
"""Z3 constraint solving script - Cognitive prosthetics for Claude.

USAGE:
    # Check satisfiability
    uv run python -m runtime.harness scripts/z3_solve.py \
        sat "x > 0, x < 10, x*x == 49" --type int

    # Prove theorem
    uv run python -m runtime.harness scripts/z3_solve.py \
        prove "x + y == y + x" --vars x y --type int

    # Optimize
    uv run python -m runtime.harness scripts/z3_solve.py \
        optimize "x + y" --constraints "x >= 0, y >= 0, x + y <= 100" \
        --direction maximize --type real

Requires: z3-solver (pip install z3-solver)
"""

import argparse
import asyncio
import json
import re
import sys
from typing import Any, Dict, List


def get_z3():
    """Lazy import Z3."""
    import z3

    return z3


def _extract_variables(constraints: list[str]) -> list[str]:
    """Extract variable names from constraint strings."""
    all_vars = set()
    for c in constraints:
        # Find all identifiers
        identifiers = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", c)
        # Filter out operators and keywords
        keywords = {"And", "Or", "Not", "If", "Implies", "True", "False", "and", "or", "not", "if"}
        all_vars.update(id for id in identifiers if id not in keywords)
    return list(all_vars)


def create_variables(var_specs: list[str], var_type: str = "int") -> dict[str, Any]:
    """Create Z3 variables from specifications.

    Args:
        var_specs: List like ["x", "y", "z"] or ["x:int", "y:real"]
        var_type: Default type if not specified

    Returns:
        Dict mapping names to Z3 variables
    """
    z3 = get_z3()

    type_map = {
        "int": z3.Int,
        "real": z3.Real,
        "bool": z3.Bool,
    }

    variables = {}
    for spec in var_specs:
        if ":" in spec:
            name, vtype = spec.split(":", 1)
        else:
            name, vtype = spec, var_type

        constructor = type_map.get(vtype, z3.Int)
        variables[name] = constructor(name)

    return variables


def parse_constraint(constraint_str: str, variables: dict[str, Any]) -> Any:
    """Parse a constraint string into Z3 expression.

    Args:
        constraint_str: String like "x > 0" or "x + y == 10"
        variables: Dict mapping names to Z3 variables

    Returns:
        Z3 constraint expression
    """
    z3 = get_z3()

    # Build evaluation context
    ctx = dict(variables)
    ctx.update(
        {
            "And": z3.And,
            "Or": z3.Or,
            "Not": z3.Not,
            "If": z3.If,
            "Implies": z3.Implies,
        }
    )

    # Replace operators for Python eval
    constraint_str = constraint_str.replace("&&", " and ")
    constraint_str = constraint_str.replace("||", " or ")
    constraint_str = constraint_str.replace("!", " not ")

    try:
        return eval(constraint_str, {"__builtins__": {}}, ctx)
    except Exception as e:
        raise ValueError(f"Cannot parse constraint '{constraint_str}': {e}")


def check_sat(constraints: list[str], variables: list[str] = None, var_type: str = "int") -> dict:
    """Check satisfiability and find a model if SAT.

    Args:
        constraints: List of constraint strings
        variables: Variable names (auto-detected if None)
        var_type: Default variable type

    Returns:
        {
            "satisfiable": True/False,
            "model": {...} or None,
            "reason": "..." if UNSAT
        }
    """
    z3 = get_z3()

    # Auto-detect variables if not provided
    if variables is None:
        variables = _extract_variables(constraints)

    vars_dict = create_variables(variables, var_type)

    solver = z3.Solver()

    for c_str in constraints:
        constraint = parse_constraint(c_str, vars_dict)
        solver.add(constraint)

    result = solver.check()

    if result == z3.sat:
        model = solver.model()
        model_dict = {}
        for v in variables:
            if v in vars_dict:
                val = model[vars_dict[v]]
                if val is not None:
                    model_dict[v] = str(val)
        return {"satisfiable": True, "model": model_dict}
    elif result == z3.unsat:
        return {"satisfiable": False, "model": None, "reason": "Constraints are unsatisfiable"}
    else:
        return {"satisfiable": None, "model": None, "reason": "Unknown (timeout or resource limit)"}


def prove_theorem(
    theorem: str, assumptions: list[str] = None, variables: list[str] = None, var_type: str = "int"
) -> dict:
    """Attempt to prove a theorem.

    Strategy: Try to find a counterexample. If UNSAT, theorem is proved.

    Args:
        theorem: Statement to prove (e.g., "x + y == y + x")
        assumptions: Preconditions
        variables: Variable names
        var_type: Variable type

    Returns:
        {
            "proved": True/False,
            "counterexample": {...} if not proved,
            "method": "...",
            "vacuous": True if assumptions are inconsistent
        }
    """
    z3 = get_z3()

    if variables is None:
        all_constraints = [theorem] + (assumptions or [])
        variables = _extract_variables(all_constraints)

    vars_dict = create_variables(variables, var_type)

    # First, check if assumptions are consistent (vacuous truth detection)
    if assumptions:
        assumption_solver = z3.Solver()
        for a_str in assumptions:
            assumption_solver.add(parse_constraint(a_str, vars_dict))
        assumption_check = assumption_solver.check()
        if assumption_check == z3.unsat:
            # Assumptions are inconsistent - vacuous truth
            return {
                "proved": True,
                "counterexample": None,
                "method": "Vacuous truth - assumptions are inconsistent",
                "vacuous": True,
                "warning": "Assumptions are inconsistent, anything can be proved",
            }

    solver = z3.Solver()

    # Add assumptions
    if assumptions:
        for a_str in assumptions:
            solver.add(parse_constraint(a_str, vars_dict))

    # Add negation of theorem (looking for counterexample)
    theorem_expr = parse_constraint(theorem, vars_dict)
    solver.add(z3.Not(theorem_expr))

    result = solver.check()

    if result == z3.unsat:
        return {"proved": True, "counterexample": None, "method": "No counterexample exists"}
    elif result == z3.sat:
        model = solver.model()
        counterexample = {}
        for v in variables:
            if v in vars_dict:
                val = model[vars_dict[v]]
                if val is not None:
                    counterexample[v] = str(val)
        return {"proved": False, "counterexample": counterexample, "method": "Counterexample found"}
    else:
        return {"proved": None, "counterexample": None, "method": "Could not determine (timeout)"}


def optimize(
    objective: str,
    constraints: list[str],
    variables: list[str] = None,
    var_type: str = "real",
    direction: str = "minimize",
) -> dict:
    """Optimize an objective subject to constraints.

    Args:
        objective: Expression to optimize
        constraints: List of constraints
        variables: Variable names
        var_type: Variable type (usually "real" for optimization)
        direction: "minimize" or "maximize"

    Returns:
        {
            "optimal": True/False,
            "value": ...,
            "model": {...}
        }
    """
    z3 = get_z3()

    if variables is None:
        all_exprs = [objective] + constraints
        variables = _extract_variables(all_exprs)

    vars_dict = create_variables(variables, var_type)

    opt = z3.Optimize()

    # Add constraints
    for c_str in constraints:
        opt.add(parse_constraint(c_str, vars_dict))

    # Set objective
    obj_expr = parse_constraint(objective, vars_dict)
    if direction == "minimize":
        opt.minimize(obj_expr)
    else:
        opt.maximize(obj_expr)

    result = opt.check()

    if result == z3.sat:
        model = opt.model()
        model_dict = {}
        for v in variables:
            if v in vars_dict:
                val = model[vars_dict[v]]
                if val is not None:
                    model_dict[v] = str(val)
        # Evaluate objective at solution
        obj_value = model.eval(obj_expr)
        return {"optimal": True, "value": str(obj_value), "model": model_dict}
    else:
        return {"optimal": False, "value": None, "model": None, "reason": "No feasible solution"}


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Z3 constraint solving - cognitive prosthetics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # SAT command
    sat_p = subparsers.add_parser("sat", help="Check satisfiability")
    sat_p.add_argument("constraints", help="Comma-separated constraints")
    sat_p.add_argument("--vars", nargs="+", help="Variable names")
    sat_p.add_argument("--type", dest="var_type", default="int", choices=["int", "real", "bool"])

    # Prove command
    prove_p = subparsers.add_parser("prove", help="Prove theorems")
    prove_p.add_argument("theorem", help="Statement to prove")
    prove_p.add_argument("--assume", nargs="+", help="Assumptions")
    prove_p.add_argument("--vars", nargs="+", help="Variable names")
    prove_p.add_argument("--type", dest="var_type", default="int", choices=["int", "real", "bool"])

    # Optimize command
    opt_p = subparsers.add_parser("optimize", help="Optimize objective")
    opt_p.add_argument("objective", help="Expression to optimize")
    opt_p.add_argument("--constraints", required=True, help="Comma-separated constraints")
    opt_p.add_argument("--direction", default="minimize", choices=["minimize", "maximize"])
    opt_p.add_argument("--vars", nargs="+", help="Variable names")
    opt_p.add_argument("--type", dest="var_type", default="real", choices=["int", "real", "bool"])

    # Common options
    for p in [sat_p, prove_p, opt_p]:
        p.add_argument("--json", action="store_true", help="Output as JSON")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    args = parse_args()

    try:
        if args.command == "sat":
            constraints = [c.strip() for c in args.constraints.split(",")]
            result = check_sat(constraints, args.vars, args.var_type)
        elif args.command == "prove":
            result = prove_theorem(args.theorem, args.assume, args.vars, args.var_type)
        elif args.command == "optimize":
            constraints = [c.strip() for c in args.constraints.split(",")]
            result = optimize(args.objective, constraints, args.vars, args.var_type, args.direction)
        else:
            result = {"error": f"Unknown command: {args.command}"}

        # Output
        print(json.dumps(result, indent=2))

    except Exception as e:
        error_result = {"error": str(e), "command": args.command}
        print(json.dumps(error_result), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
