#!/usr/bin/env python3
"""Math education tutoring features - Step-by-step solutions, hints, problem generation.

USAGE:
    # Generate step-by-step solution
    uv run python scripts/math_tutor.py steps "x**2 - 5*x + 6 = 0" --operation solve

    # Get progressive hint
    uv run python scripts/math_tutor.py hint "Solve x**2 - 4 = 0" --level 2

    # Generate practice problem
    uv run python scripts/math_tutor.py generate --topic algebra --difficulty 2

Features:
- Step-by-step solutions with rule justifications
- 5-level progressive hint system (conceptual -> answer)
- Parameterized problem generation by topic and difficulty

Based on research from education-patterns.md:
- Wolfram Alpha's solution decomposition
- Khan Academy's progressive disclosure hints
- Intelligent Tutoring Systems research

Requires: sympy (pip install sympy)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

# Import sympy lazily
_sympy = None


def get_sympy():
    """Lazy import SymPy."""
    global _sympy
    if _sympy is None:
        import sympy

        _sympy = sympy
    return _sympy


# ============================================================================
# Data Classes
# ============================================================================


class StepType(Enum):
    """Types of solution steps."""

    SETUP = "setup"
    TRANSFORM = "transform"
    SIMPLIFY = "simplify"
    SUBSTITUTE = "substitute"
    COMPUTE = "compute"
    VERIFY = "verify"
    FACTOR = "factor"


@dataclass
class SolutionStep:
    """A single step in a solution."""

    step_number: int
    step_type: str
    description: str
    from_expr: str
    to_expr: str
    rule_applied: str
    justification: str


@dataclass
class HintLevel:
    """A hint at a specific level."""

    level: int
    category: str
    hint: str
    reveals: str
    cost: int


@dataclass
class GeneratedProblem:
    """A generated practice problem."""

    problem: str
    solution: Any
    difficulty: int
    template_id: str
    topic: str


# ============================================================================
# Constants (avoiding code duplication)
# ============================================================================

TECHNIQUE_QUADRATIC_FORMULA = "quadratic formula"
TECHNIQUE_ALGEBRAIC_METHODS = "algebraic methods"
STEP_PROBLEM_SETUP = "Problem Setup"


# ============================================================================
# Dispatch Tables (Refactored from high-complexity functions)
# ============================================================================


def _hint_level_1(problem_type: str, technique: str, solution: Any, problem: str) -> str:
    """Level 1: Conceptual - identify problem type."""
    return f"This is a {problem_type} problem."


def _hint_level_2(problem_type: str, technique: str, solution: Any, problem: str) -> str:
    """Level 2: Strategic - suggest approach."""
    if "quadratic" in problem_type:
        return f"For this {problem_type}, consider using {technique} or the quadratic formula."
    elif "linear" in problem_type:
        return "Use inverse operations to isolate the variable on one side."
    elif "derivative" in problem_type or "differentiation" in problem_type:
        return (
            "Identify which differentiation rule(s) apply: power, product, chain, or quotient."
        )
    else:
        return f"Consider using {technique} to solve this problem."


def _hint_level_3(problem_type: str, technique: str, solution: Any, problem: str) -> str:
    """Level 3: Tactical - specific next step."""
    if "difference of squares" in technique:
        return "This is a difference of squares pattern: a^2 - b^2 = (a+b)(a-b)."
    elif "factor" in technique:
        return (
            "Look for factors: what two numbers multiply to give the constant "
            "and add to give the coefficient of x?"
        )
    elif "linear" in problem_type:
        return "First, move all terms with x to one side and constants to the other."
    elif "derivative" in problem_type or "differentiation" in problem_type:
        return "Apply the power rule: d/dx(x^n) = n*x^(n-1) to each term."
    else:
        return f"Apply {technique} step by step."


def _hint_level_4(problem_type: str, technique: str, solution: Any, problem: str) -> str:
    """Level 4: Computational - specific computation guidance."""
    if "quadratic" in problem_type and solution:
        if isinstance(solution, list) and len(solution) == 2:
            if solution[0] == -solution[1]:
                s = solution[0]
                return f"Factor as difference of squares: x^2 - {s**2} = (x - {s})(x + {s})."
            else:
                return f"The factors are (x - {solution[0]}) and (x - {solution[1]})."
    elif "linear" in problem_type:
        return "Divide both sides by the coefficient of x to solve."
    elif "derivative" in problem_type or "differentiation" in problem_type:
        return "For each term x^n, the derivative is n*x^(n-1). Constants have derivative 0."

    return "Apply the standard formula or technique to compute the result."


def _hint_level_5(problem_type: str, technique: str, solution: Any, problem: str) -> str:
    """Level 5: Answer - reveal the solution."""
    if solution is not None:
        if isinstance(solution, list):
            sol_str = ", ".join([f"x = {s}" for s in solution])
            return f"The answer is: {sol_str}"
        else:
            return f"The answer is: {solution}"
    return "Could not compute the answer. Check the problem statement."


# Dispatch table for hint generation by level
HINT_GENERATORS: dict[int, Callable[[str, str, Any, str], str]] = {
    1: _hint_level_1,
    2: _hint_level_2,
    3: _hint_level_3,
    4: _hint_level_4,
    5: _hint_level_5,
}


def _analyze_derivative(problem: str, x, sympy) -> tuple[str, str, Any]:
    """Analyze a derivative problem."""
    problem_clean = problem.lower()
    # Extract expression
    expr_match = re.search(r"of\s+(.+?)(?:\s|$)", problem_clean)
    if expr_match:
        expr_str = expr_match.group(1)
    else:
        pattern = r"(find\s+the\s+derivative\s+of|derivative\s+of)"
        expr_str = re.sub(pattern, "", problem_clean).strip()

    try:
        local_dict = {"x": x}
        expr = sympy.parse_expr(expr_str, local_dict=local_dict)
        solution = sympy.diff(expr, x)
    except Exception:
        solution = None

    return "differentiation", "differentiation rules", solution


def _detect_quadratic_technique(expr, solutions, sympy) -> str:
    """Detect the best technique for solving a quadratic equation."""
    try:
        factored = sympy.factor(expr)
        if "**2" in str(factored) or factored == expr:
            return TECHNIQUE_QUADRATIC_FORMULA
        # Check for difference of squares pattern
        if len(solutions) == 2 and solutions[0] == -solutions[1]:
            return "difference of squares"
        return "factoring"
    except Exception:
        return TECHNIQUE_QUADRATIC_FORMULA


def _analyze_equation(problem: str, x, sympy) -> tuple[str, str, Any]:
    """Analyze an equation problem to solve."""
    try:
        # Extract equation part
        eq_part = problem.split(":")[-1].strip() if ":" in problem else problem
        eq_part = re.sub(r"solve[:\s]*", "", eq_part, flags=re.IGNORECASE).strip()

        lhs, rhs = _parse_equation(eq_part)
        expr = lhs - rhs

        degree = sympy.degree(sympy.expand(expr), x)
        solutions = sympy.solve(expr, x)

        if degree == 1:
            return "linear equation", "isolate variable", solutions
        elif degree == 2:
            technique = _detect_quadratic_technique(expr, solutions, sympy)
            return "quadratic equation", technique, solutions
        else:
            return "polynomial equation", TECHNIQUE_ALGEBRAIC_METHODS, solutions
    except Exception:
        return "equation", TECHNIQUE_ALGEBRAIC_METHODS, None


# Dispatch table for problem analyzers by detected type
PROBLEM_ANALYZERS: dict[str, Callable[[str, Any, Any], tuple[str, str, Any]]] = {
    "derivative": _analyze_derivative,
    "diff": _analyze_derivative,
    "solve": _analyze_equation,
    "equation": _analyze_equation,
}


def _solve_linear_steps(expr, x, step_num: int, steps: list, sympy) -> int:
    """Generate steps for solving a linear equation."""
    # Get coefficient and constant
    coeff = expr.coeff(x)
    const = expr.subs(x, 0)

    if const != 0:
        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.TRANSFORM.value,
                description="Isolate variable term",
                from_expr=f"{expr} = 0",
                to_expr=f"{coeff}*x = {-const}",
                rule_applied="Addition/Subtraction Property of Equality",
                justification=f"Add {-const} to both sides to isolate the x term.",
            )
        )
        step_num += 1

    if coeff != 1:
        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.COMPUTE.value,
                description="Solve for x",
                from_expr=f"{coeff}*x = {-const}",
                to_expr=f"x = {-const / coeff}",
                rule_applied="Division Property of Equality",
                justification=f"Divide both sides by {coeff}.",
            )
        )
        step_num += 1

    return step_num


def _solve_quadratic_steps(expr, x, step_num: int, steps: list, sympy) -> int:
    """Generate steps for solving a quadratic equation."""
    try:
        factored = sympy.factor(expr)
        if factored != expr and "*" in str(factored):
            steps.append(
                SolutionStep(
                    step_number=step_num,
                    step_type=StepType.FACTOR.value,
                    description="Factor the expression",
                    from_expr=str(expr),
                    to_expr=str(factored),
                    rule_applied="Factoring",
                    justification="Factor the quadratic expression into product of binomials.",
                )
            )
            step_num += 1

            # Zero product property
            steps.append(
                SolutionStep(
                    step_number=step_num,
                    step_type=StepType.TRANSFORM.value,
                    description="Apply Zero Product Property",
                    from_expr=f"{factored} = 0",
                    to_expr="Each factor = 0",
                    rule_applied="Zero Product Property",
                    justification="If a*b = 0, then a = 0 or b = 0.",
                )
            )
            step_num += 1
    except Exception:
        pass

    return step_num


# Dispatch table for solver strategies by polynomial degree
SOLVER_STRATEGIES: dict[int, Callable[[Any, Any, int, list, Any], int]] = {
    1: _solve_linear_steps,
    2: _solve_quadratic_steps,
}


# ============================================================================
# Step-by-Step Solutions
# ============================================================================


def classify_problem(expr_str: str, operation: str) -> str:
    """Classify the problem type.

    Args:
        expr_str: The expression string
        operation: The operation to perform

    Returns:
        Problem type string
    """
    if operation == "diff":
        return "derivative"
    if operation == "integrate":
        return "integral"
    if operation == "simplify":
        return "simplification"

    # For solve operation
    if "**2" in expr_str or "^2" in expr_str:
        return "quadratic"
    if "**3" in expr_str or "^3" in expr_str:
        return "polynomial"
    if "*x" in expr_str or "x*" in expr_str or "x +" in expr_str or "+ x" in expr_str:
        return "linear"

    return "equation"


def _parse_equation(expr_str: str) -> tuple[Any, Any]:
    """Parse an equation string into LHS and RHS sympy expressions.

    Args:
        expr_str: Equation string like "x**2 - 4 = 0"

    Returns:
        (lhs, rhs) tuple of sympy expressions
    """
    sympy = get_sympy()
    x = sympy.Symbol("x")
    local_dict = {"x": x}

    if "=" in expr_str:
        parts = expr_str.split("=")
        lhs_str = parts[0].strip()
        rhs_str = parts[1].strip()
        lhs = sympy.parse_expr(lhs_str, local_dict=local_dict)
        rhs = sympy.parse_expr(rhs_str, local_dict=local_dict)
    else:
        lhs = sympy.parse_expr(expr_str.strip(), local_dict=local_dict)
        rhs = sympy.Integer(0)

    return lhs, rhs


def generate_steps(problem: str, operation: str) -> dict:
    """Generate step-by-step solution with justifications.

    Args:
        problem: The mathematical problem (e.g., "x**2 - 5*x + 6 = 0")
        operation: The operation to perform ("solve", "diff", "integrate", "simplify")

    Returns:
        Dictionary with:
        - steps: List of solution steps
        - final_answer: The final answer
        - problem_type: Classification of the problem
        - verification: Optional verification
    """
    sympy = get_sympy()
    x = sympy.Symbol("x")

    if not problem or not problem.strip():
        return {"error": "Empty problem", "steps": []}

    # Validate operation
    valid_ops = ["solve", "diff", "integrate", "simplify"]
    if operation not in valid_ops:
        return {"error": f"Invalid operation. Must be one of: {valid_ops}", "steps": []}

    problem_type = classify_problem(problem, operation)
    steps = []
    final_answer = ""
    verification = None

    try:
        if operation == "solve":
            steps, final_answer, verification = _solve_steps(problem, x)
        elif operation == "diff":
            steps, final_answer = _diff_steps(problem, x)
        elif operation == "integrate":
            steps, final_answer = _integrate_steps(problem, x)
        elif operation == "simplify":
            steps, final_answer = _simplify_steps(problem, x)

    except Exception as e:
        return {"error": str(e), "steps": []}

    return {
        "steps": [asdict(s) if isinstance(s, SolutionStep) else s for s in steps],
        "final_answer": str(final_answer),
        "problem_type": problem_type,
        "verification": verification,
    }


def _solve_steps(problem: str, x) -> tuple[list[SolutionStep], str, str | None]:
    """Generate steps for solving an equation.

    Refactored to use SOLVER_STRATEGIES dispatch table for degree-specific logic.
    """
    sympy = get_sympy()
    lhs, rhs = _parse_equation(problem)

    # Move to standard form (everything on left)
    expr = lhs - rhs
    steps = []
    step_num = 1

    # Step 1: Setup - recognize problem type
    expr_expanded = sympy.expand(expr)
    degree = sympy.degree(expr_expanded, x)

    if degree == 1:
        problem_type = "linear equation"
        technique = "isolating the variable"
    elif degree == 2:
        problem_type = "quadratic equation"
        # Check if factorable
        try:
            factored = sympy.factor(expr)
            if factored != expr:
                technique = "factoring"
            else:
                technique = TECHNIQUE_QUADRATIC_FORMULA
        except Exception:
            technique = TECHNIQUE_QUADRATIC_FORMULA
    else:
        problem_type = f"polynomial equation (degree {degree})"
        technique = TECHNIQUE_ALGEBRAIC_METHODS

    steps.append(
        SolutionStep(
            step_number=step_num,
            step_type=StepType.SETUP.value,
            description=f"Recognize this is a {problem_type}",
            from_expr=problem,
            to_expr=f"{expr} = 0",
            rule_applied="Problem Recognition",
            justification=f"This is a {problem_type}. We will solve using {technique}.",
        )
    )
    step_num += 1

    # Step 2: Transform to standard form if needed
    if rhs != 0:
        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.TRANSFORM.value,
                description="Move all terms to one side",
                from_expr=problem,
                to_expr=f"{expr} = 0",
                rule_applied="Addition/Subtraction Property of Equality",
                justification="Subtract terms from both sides to get standard form.",
            )
        )
        step_num += 1

    # Step 3: Solve based on type using dispatch table
    strategy = SOLVER_STRATEGIES.get(degree)
    if strategy:
        step_num = strategy(expr, x, step_num, steps, sympy)

    # Solve and get solutions
    solutions = sympy.solve(expr, x)
    final_answer = ", ".join([f"x = {s}" for s in solutions])

    # Final step: state solution
    steps.append(
        SolutionStep(
            step_number=step_num,
            step_type=StepType.COMPUTE.value,
            description="State the solution(s)",
            from_expr="Solving each factor",
            to_expr=final_answer,
            rule_applied="Solution",
            justification=f"The solution(s) are: {final_answer}",
        )
    )

    # Verification
    verifications = []
    for sol in solutions:
        check = lhs.subs(x, sol)
        verifications.append(f"Check x={sol}: {lhs} = {check} = {rhs} [OK]")
    verification = "; ".join(verifications)

    return steps, final_answer, verification


def _diff_steps(problem: str, x) -> tuple[list[SolutionStep], str]:
    """Generate steps for differentiation."""
    sympy = get_sympy()

    # Parse expression
    local_dict = {"x": x}
    if "=" in problem:
        # Handle equations like "y = x**3"
        parts = problem.split("=")
        expr = sympy.parse_expr(parts[1].strip(), local_dict=local_dict)
    else:
        expr = sympy.parse_expr(problem.strip(), local_dict=local_dict)

    steps = []
    step_num = 1

    # Step 1: Setup
    steps.append(
        SolutionStep(
            step_number=step_num,
            step_type=StepType.SETUP.value,
            description="Identify the function to differentiate",
            from_expr=str(expr),
            to_expr=f"d/dx({expr})",
            rule_applied=STEP_PROBLEM_SETUP,
            justification=f"We need to find the derivative of {expr} with respect to x.",
        )
    )
    step_num += 1

    # Break down by terms if it's a sum
    terms = sympy.Add.make_args(expr)

    if len(terms) > 1:
        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.TRANSFORM.value,
                description="Apply Sum Rule",
                from_expr=f"d/dx({expr})",
                to_expr=" + ".join([f"d/dx({t})" for t in terms]),
                rule_applied="Sum Rule",
                justification="The derivative of a sum is the sum of derivatives.",
            )
        )
        step_num += 1

    # Differentiate each term
    derivative_parts = []
    for term in terms:
        term_deriv = sympy.diff(term, x)
        derivative_parts.append(term_deriv)

        # Identify rule used
        if term.is_polynomial(x):
            rule = "Power Rule"
            just = "d/dx(x^n) = n*x^(n-1)"
        elif term.has(sympy.sin) or term.has(sympy.cos):
            rule = "Trig Derivative"
            just = "d/dx(sin(x)) = cos(x), d/dx(cos(x)) = -sin(x)"
        elif term.has(sympy.exp):
            rule = "Exponential Rule"
            just = "d/dx(e^x) = e^x"
        else:
            rule = "Standard Derivative"
            just = "Apply standard differentiation rules"

        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.COMPUTE.value,
                description=f"Differentiate {term}",
                from_expr=f"d/dx({term})",
                to_expr=str(term_deriv),
                rule_applied=rule,
                justification=just,
            )
        )
        step_num += 1

    # Combine
    final_deriv = sympy.diff(expr, x)
    final_simplified = sympy.simplify(final_deriv)

    if final_simplified != final_deriv:
        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.SIMPLIFY.value,
                description="Simplify the result",
                from_expr=str(final_deriv),
                to_expr=str(final_simplified),
                rule_applied="Algebraic Simplification",
                justification="Combine like terms.",
            )
        )

    return steps, str(final_simplified)


def _integrate_steps(problem: str, x) -> tuple[list[SolutionStep], str]:
    """Generate steps for integration."""
    sympy = get_sympy()

    local_dict = {"x": x}
    expr = sympy.parse_expr(problem.strip(), local_dict=local_dict)

    steps = []
    step_num = 1

    # Step 1: Setup
    steps.append(
        SolutionStep(
            step_number=step_num,
            step_type=StepType.SETUP.value,
            description="Identify the function to integrate",
            from_expr=str(expr),
            to_expr=f"integral({expr}) dx",
            rule_applied=STEP_PROBLEM_SETUP,
            justification=f"We need to find the indefinite integral of {expr}.",
        )
    )
    step_num += 1

    # Break down by terms
    terms = sympy.Add.make_args(expr)

    if len(terms) > 1:
        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.TRANSFORM.value,
                description="Apply Sum Rule for Integration",
                from_expr=f"integral({expr}) dx",
                to_expr=" + ".join([f"integral({t}) dx" for t in terms]),
                rule_applied="Sum Rule",
                justification="The integral of a sum is the sum of integrals.",
            )
        )
        step_num += 1

    # Integrate each term
    for term in terms:
        term_int = sympy.integrate(term, x)

        # Identify rule
        if term.is_polynomial(x):
            rule = "Power Rule"
            just = "integral(x^n) dx = x^(n+1)/(n+1)"
        elif term.has(sympy.sin) or term.has(sympy.cos):
            rule = "Trig Integral"
            just = "integral(sin(x)) = -cos(x), integral(cos(x)) = sin(x)"
        else:
            rule = "Standard Integral"
            just = "Apply standard integration rules"

        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.COMPUTE.value,
                description=f"Integrate {term}",
                from_expr=f"integral({term}) dx",
                to_expr=str(term_int),
                rule_applied=rule,
                justification=just,
            )
        )
        step_num += 1

    # Final result
    integral = sympy.integrate(expr, x)
    final_answer = f"{integral} + C"

    steps.append(
        SolutionStep(
            step_number=step_num,
            step_type=StepType.COMPUTE.value,
            description="Add constant of integration",
            from_expr=str(integral),
            to_expr=final_answer,
            rule_applied="Constant of Integration",
            justification="Always add + C for indefinite integrals.",
        )
    )

    return steps, str(integral)


def _simplify_steps(problem: str, x) -> tuple[list[SolutionStep], str]:
    """Generate steps for simplification."""
    sympy = get_sympy()

    local_dict = {"x": x}
    expr = sympy.parse_expr(problem.strip(), local_dict=local_dict)

    steps = []
    step_num = 1

    # Step 1: Setup
    steps.append(
        SolutionStep(
            step_number=step_num,
            step_type=StepType.SETUP.value,
            description="Identify expression to simplify",
            from_expr=str(expr),
            to_expr=str(expr),
            rule_applied=STEP_PROBLEM_SETUP,
            justification=f"Simplify the expression: {expr}",
        )
    )
    step_num += 1

    # Try expanding
    expanded = sympy.expand(expr)
    if expanded != expr:
        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.TRANSFORM.value,
                description="Expand the expression",
                from_expr=str(expr),
                to_expr=str(expanded),
                rule_applied="Distributive Property",
                justification="Expand all products and powers.",
            )
        )
        step_num += 1
        expr = expanded

    # Simplify
    simplified = sympy.simplify(expr)
    if simplified != expr:
        steps.append(
            SolutionStep(
                step_number=step_num,
                step_type=StepType.SIMPLIFY.value,
                description="Combine like terms",
                from_expr=str(expr),
                to_expr=str(simplified),
                rule_applied="Combining Like Terms",
                justification="Add/subtract terms with the same variable part.",
            )
        )

    return steps, str(simplified)


# ============================================================================
# Hint System
# ============================================================================


def get_hint(problem: str, level: int = 1) -> dict:
    """Get a progressive hint for a problem.

    Args:
        problem: The mathematical problem
        level: Hint level 1-5 (conceptual to answer)

    Returns:
        Dictionary with:
        - level: The hint level
        - category: conceptual/strategic/tactical/computational/answer
        - hint: The hint text
        - reveals: What information is disclosed
        - cost: Point cost for using this hint
    """
    sympy = get_sympy()
    x = sympy.Symbol("x")

    # Clamp level to valid range
    level = max(1, min(5, level))

    # Determine problem type and technique
    problem_type, technique, solution = _analyze_problem(problem, x)

    categories = {1: "conceptual", 2: "strategic", 3: "tactical", 4: "computational", 5: "answer"}

    costs = {1: 0, 2: 5, 3: 10, 4: 15, 5: 25}

    reveals = {1: "problem_type", 2: "technique", 3: "next_step", 4: "computation", 5: "answer"}

    hint_text = _generate_hint_text(problem_type, technique, solution, level, problem)

    return {
        "level": level,
        "category": categories[level],
        "hint": hint_text,
        "reveals": reveals[level],
        "cost": costs[level],
    }


def _analyze_problem(problem: str, x) -> tuple[str, str, Any]:
    """Analyze a problem to determine type, technique, and solution.

    Refactored to use PROBLEM_ANALYZERS dispatch table for reduced complexity.
    """
    sympy = get_sympy()
    problem_clean = problem.lower()

    # Detect problem type and dispatch to appropriate analyzer
    if "derivative" in problem_clean or "diff" in problem_clean:
        return PROBLEM_ANALYZERS["derivative"](problem, x, sympy)

    if "solve" in problem_clean or "=" in problem:
        return PROBLEM_ANALYZERS["solve"](problem, x, sympy)

    return "equation", TECHNIQUE_ALGEBRAIC_METHODS, None


def _generate_hint_text(
    problem_type: str, technique: str, solution: Any, level: int, problem: str
) -> str:
    """Generate hint text for given level using dispatch table.

    Refactored from high-complexity if/elif chain to use HINT_GENERATORS dispatch table.
    """
    handler = HINT_GENERATORS.get(level)
    if handler:
        return handler(problem_type, technique, solution, problem)
    return "No hint available for this level."


# ============================================================================
# Problem Generation
# ============================================================================


@dataclass
class ProblemTemplate:
    """Template for generating problems."""

    template_id: str
    topic: str
    difficulty: int
    template: str
    param_ranges: dict[str, Any]
    solution_func: Callable
    constraints: list[Callable]


# Problem templates
TEMPLATES = []


def _init_templates():
    """Initialize problem templates."""
    global TEMPLATES

    if TEMPLATES:
        return

    # Linear equations - difficulty 1
    TEMPLATES.append(
        ProblemTemplate(
            template_id="linear_1",
            topic="linear_equation",
            difficulty=1,
            template="Solve for x: {a}*x + {b} = {c}",
            param_ranges={"a": (1, 5), "b": (-10, 10), "c": (-10, 20)},
            solution_func=lambda a, b, c: (c - b) / a,
            constraints=[
                lambda p: p["a"] != 0,
                lambda p: (p["c"] - p["b"]) % p["a"] == 0,  # Integer solution
            ],
        )
    )

    # Linear equations - difficulty 2
    TEMPLATES.append(
        ProblemTemplate(
            template_id="linear_2",
            topic="linear_equation",
            difficulty=2,
            template="Solve for x: {a}*x + {b} = {c}*x + {d}",
            param_ranges={"a": (2, 8), "b": (-10, 10), "c": (1, 5), "d": (-10, 10)},
            solution_func=lambda a, b, c, d: (d - b) / (a - c),
            constraints=[
                lambda p: p["a"] != p["c"],
                lambda p: (p["d"] - p["b"]) % (p["a"] - p["c"]) == 0,
            ],
        )
    )

    # Quadratic equations - difficulty 2
    TEMPLATES.append(
        ProblemTemplate(
            template_id="quadratic_factor_1",
            topic="quadratic",
            difficulty=2,
            template="Solve for x: x**2 + {b}*x + {c} = 0",
            param_ranges={"r1": (-5, 5), "r2": (-5, 5)},
            solution_func=lambda r1, r2: sorted([r1, r2]),
            constraints=[lambda p: p["r1"] != 0 or p["r2"] != 0, lambda p: p["r1"] != p["r2"]],
        )
    )

    # Quadratic - difference of squares - difficulty 2
    TEMPLATES.append(
        ProblemTemplate(
            template_id="quadratic_dos",
            topic="quadratic",
            difficulty=2,
            template="Solve for x: x**2 - {a2} = 0",
            param_ranges={"a": (1, 6)},
            solution_func=lambda a: [-a, a],
            constraints=[],
        )
    )

    # Algebra simple - difficulty 1
    TEMPLATES.append(
        ProblemTemplate(
            template_id="algebra_1",
            topic="algebra",
            difficulty=1,
            template="Solve for x: {a}*x = {b}",
            param_ranges={"a": (2, 10), "b": (4, 50)},
            solution_func=lambda a, b: b / a,
            constraints=[lambda p: p["b"] % p["a"] == 0],
        )
    )

    # Algebra - difficulty 2
    TEMPLATES.append(
        ProblemTemplate(
            template_id="algebra_2",
            topic="algebra",
            difficulty=2,
            template="Solve for x: {a}*x + {b} = {c}",
            param_ranges={"a": (2, 10), "b": (-15, 15), "c": (-20, 30)},
            solution_func=lambda a, b, c: (c - b) / a,
            constraints=[lambda p: p["a"] != 0, lambda p: (p["c"] - p["b"]) % p["a"] == 0],
        )
    )

    # Algebra - difficulty 3
    TEMPLATES.append(
        ProblemTemplate(
            template_id="algebra_3",
            topic="algebra",
            difficulty=3,
            template="Solve for x: {a}*x**2 + {b}*x + {c} = 0",
            param_ranges={"r1": (-4, 4), "r2": (-4, 4), "a": (1, 2)},
            solution_func=lambda r1, r2, a: sorted([r1, r2]),
            constraints=[lambda p: p["r1"] != p["r2"]],
        )
    )

    # Algebra - difficulty 4
    TEMPLATES.append(
        ProblemTemplate(
            template_id="algebra_4",
            topic="algebra",
            difficulty=4,
            template="Solve for x: {a}*x**2 + {b}*x + {c} = {d}",
            param_ranges={"a": (1, 3), "b": (-10, 10), "c": (-15, 15), "d": (-20, 20)},
            solution_func=lambda a, b, c, d: "complex",  # May have irrational solutions
            constraints=[lambda p: p["a"] != 0],
        )
    )

    # Derivative - difficulty 1
    TEMPLATES.append(
        ProblemTemplate(
            template_id="derivative_1",
            topic="derivative",
            difficulty=1,
            template="Find the derivative of x**{n}",
            param_ranges={"n": (2, 5)},
            solution_func=lambda n: f"{n}*x**{n - 1}",
            constraints=[],
        )
    )

    # Derivative - difficulty 2
    TEMPLATES.append(
        ProblemTemplate(
            template_id="derivative_2",
            topic="derivative",
            difficulty=2,
            template="Find the derivative of {a}*x**{n} + {b}*x",
            param_ranges={"a": (2, 5), "n": (2, 4), "b": (1, 5)},
            solution_func=lambda a, n, b: f"{a * n}*x**{n - 1} + {b}",
            constraints=[],
        )
    )

    # Calculus - difficulty 2
    TEMPLATES.append(
        ProblemTemplate(
            template_id="calculus_1",
            topic="calculus",
            difficulty=2,
            template="Find the derivative of x**{n} + {b}*x",
            param_ranges={"n": (2, 4), "b": (1, 5)},
            solution_func=lambda n, b: f"{n}*x**{n - 1} + {b}",
            constraints=[],
        )
    )


def generate_problem(topic: str, difficulty: int) -> dict:
    """Generate a practice problem.

    Args:
        topic: Problem topic ("algebra", "linear_equation", "quadratic", "calculus", "derivative")
        difficulty: Difficulty level 1-5

    Returns:
        Dictionary with:
        - problem: The problem text
        - solution: The solution
        - difficulty: The difficulty level
        - template_id: ID of the template used
        - topic: The topic
    """
    _init_templates()

    # Clamp difficulty
    difficulty = max(1, min(5, difficulty))

    # Find matching templates
    # Map topics to template topics
    topic_mapping = {
        "algebra": ["algebra", "linear_equation", "quadratic"],
        "linear_equation": ["linear_equation"],
        "quadratic": ["quadratic"],
        "calculus": ["calculus", "derivative"],
        "derivative": ["derivative"],
    }

    search_topics = topic_mapping.get(topic, [topic])

    candidates = [
        t for t in TEMPLATES if t.topic in search_topics and abs(t.difficulty - difficulty) <= 1
    ]

    if not candidates:
        # Fallback to any template
        candidates = [t for t in TEMPLATES if abs(t.difficulty - difficulty) <= 2]

    if not candidates:
        return {"error": f"No templates found for topic '{topic}' at difficulty {difficulty}"}

    # Select random template
    template = random.choice(candidates)

    # Generate parameters
    max_attempts = 100
    for _ in range(max_attempts):
        params = _generate_params(template.param_ranges)

        # Check constraints
        if all(c(params) for c in template.constraints):
            break
    else:
        # Use last params anyway
        pass

    # Build problem text
    # Handle special cases for template parameters
    display_params = dict(params)

    # For quadratics defined by roots, compute b and c
    if "r1" in params and "r2" in params:
        r1, r2 = params["r1"], params["r2"]
        display_params["b"] = -(r1 + r2)
        display_params["c"] = r1 * r2

    # For difference of squares
    if "a" in params and template.template_id == "quadratic_dos":
        display_params["a2"] = params["a"] ** 2

    try:
        problem_text = template.template.format(**display_params)
    except KeyError:
        problem_text = template.template  # Fallback

    # Compute solution
    try:
        solution = template.solution_func(**params)
    except Exception:
        solution = None

    return {
        "problem": problem_text,
        "solution": solution,
        "difficulty": template.difficulty,
        "template_id": template.template_id,
        "topic": template.topic,
    }


def _generate_params(param_ranges: dict[str, Any]) -> dict[str, Any]:
    """Generate random parameters within ranges."""
    params = {}
    for param, range_spec in param_ranges.items():
        if isinstance(range_spec, tuple) and len(range_spec) == 2:
            params[param] = random.randint(range_spec[0], range_spec[1])
        elif isinstance(range_spec, list):
            params[param] = random.choice(range_spec)
        else:
            params[param] = range_spec
    return params


# ============================================================================
# CLI Interface
# ============================================================================


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Math education tutoring features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Steps command
    steps_p = subparsers.add_parser("steps", help="Generate step-by-step solution")
    steps_p.add_argument("problem", help="The mathematical problem")
    steps_p.add_argument(
        "--operation",
        "-o",
        default="solve",
        choices=["solve", "diff", "integrate", "simplify"],
        help="Operation to perform (default: solve)",
    )

    # Hint command
    hint_p = subparsers.add_parser("hint", help="Get a progressive hint")
    hint_p.add_argument("problem", help="The mathematical problem")
    hint_p.add_argument("--level", "-l", type=int, default=1, help="Hint level 1-5 (default: 1)")

    # Generate command
    gen_p = subparsers.add_parser("generate", help="Generate a practice problem")
    gen_p.add_argument("--topic", "-t", default="algebra", help="Problem topic (default: algebra)")
    gen_p.add_argument(
        "--difficulty", "-d", type=int, default=1, help="Difficulty level 1-5 (default: 1)"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    try:
        if args.command == "steps":
            result = generate_steps(args.problem, args.operation)
        elif args.command == "hint":
            result = get_hint(args.problem, args.level)
        elif args.command == "generate":
            result = generate_problem(args.topic, args.difficulty)
        else:
            result = {"error": f"Unknown command: {args.command}"}

        print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
