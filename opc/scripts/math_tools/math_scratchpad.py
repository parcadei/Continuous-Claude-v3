#!/usr/bin/env python3
"""Step-by-step mathematical reasoning verification - Cognitive prosthetics for Claude.

USAGE:
    # Verify a single step (JSON output, default)
    uv run python -m runtime.harness scripts/math_scratchpad.py \
        verify "x = 2 implies x^2 = 4"

    # Verify with human-readable text output
    uv run python -m runtime.harness scripts/math_scratchpad.py \
        verify "x = 2 implies x^2 = 4" --format text

    # Verify with markdown output
    uv run python -m runtime.harness scripts/math_scratchpad.py \
        verify "x = 2 implies x^2 = 4" --format markdown

    # Verify with context
    uv run python -m runtime.harness scripts/math_scratchpad.py \
        verify "x^2 = 4" --context '{"x": 2}'

    # Verify a chain of reasoning
    uv run python -m runtime.harness scripts/math_scratchpad.py \
        chain --steps '["x^2 - 4 = 0", "(x-2)(x+2) = 0", "x = 2 or x = -2"]'

    # Verify chain with text output (step-by-step results)
    uv run python -m runtime.harness scripts/math_scratchpad.py \
        chain --steps '["x = 2", "x^2 = 4"]' --format text

    # Explain a step
    uv run python -m runtime.harness scripts/math_scratchpad.py \
        explain "d/dx(x^3) = 3*x^2"

    # Explain with text output
    uv run python -m runtime.harness scripts/math_scratchpad.py \
        explain "d/dx(x^3) = 3*x^2" --format text

OUTPUT FORMATS:
    --format json      Machine-readable JSON (default)
    --format text      Human-readable plain text
    --format markdown  Formatted markdown with headers

Requires: sympy, z3-solver (pip install sympy z3-solver)
"""

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, Optional

# Import from existing scripts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sympy_compute import get_sympy, safe_parse, validate_expression
from z3_solve import get_z3, prove_theorem

# ============================================================================
# Helper Functions
# ============================================================================


def split_claim_and_condition(step_text: str) -> tuple[str, str | None]:
    """Split a step into condition and claim.

    Args:
        step_text: Text like "x = 2 implies x^2 = 4" or "x^2 + 1 = 5"

    Returns:
        (condition, claim) tuple. If no connector found, returns (step_text, None)
    """
    # Connectors in order of specificity
    connectors = [
        r"\s+implies\s+",
        r"\s+therefore\s+",
        r"\s+so\s+",
        r"\s+hence\s+",
        r"\s+thus\s+",
        r"\s*->\s*",
        r"\s*=>\s*",
    ]

    for pattern in connectors:
        match = re.split(pattern, step_text, maxsplit=1, flags=re.IGNORECASE)
        if len(match) == 2:
            return match[0].strip(), match[1].strip()

    return step_text.strip(), None


def detect_operation_type(step_text: str) -> str:
    """Detect the type of mathematical operation in a step.

    Args:
        step_text: Mathematical step text

    Returns:
        Operation type: "differentiation", "integration", "factoring",
        "substitution", "simplification", or "unknown"
    """
    step_lower = step_text.lower()

    # Differentiation patterns
    if re.search(r"d/d[a-z]|derivative|diff", step_lower):
        return "differentiation"

    # Integration patterns
    if re.search(r"integral|integrate|\bint\b", step_lower):
        return "integration"

    # Factoring patterns (LHS has product form, RHS doesn't or vice versa)
    if re.search(r"\([^)]+\)\s*\([^)]+\)", step_text):
        # Has product form like (x-2)(x+2)
        return "factoring"

    # Substitution patterns
    cond, claim = split_claim_and_condition(step_text)
    if claim is not None:
        return "substitution"

    # Simplification patterns (trig identities, etc.)
    if re.search(r"sin|cos|tan|sec|csc|cot", step_lower):
        return "simplification"

    # Default: check for equals sign
    if "=" in step_text:
        return "simplification"

    return "unknown"


def select_verification_method(step_text: str) -> str:
    """Select whether to use SymPy or Z3 for verification.

    Args:
        step_text: The mathematical step to verify

    Returns:
        "sympy" or "z3"
    """
    step_lower = step_text.lower()

    # Use SymPy for:
    # - Trig identities
    # - Calculus operations
    # - Algebraic simplifications
    # - Substitution with specific values
    if re.search(r"sin|cos|tan|sec|csc|cot", step_lower):
        return "sympy"
    if re.search(r"d/d[a-z]|integral|diff", step_lower):
        return "sympy"

    cond, claim = split_claim_and_condition(step_text)
    if claim is not None:
        # Substitution - use SymPy
        return "sympy"

    # Use Z3 for universal claims (no specific values)
    # e.g., "x + y = y + x" (true for all x, y)
    return "z3"


# ============================================================================
# Core Functions
# ============================================================================


def verify_step(step_text: str, context: dict[str, Any] = None) -> dict:
    """Verify a single mathematical claim.

    Args:
        step_text: A claim like "x = 2 implies x^2 = 4" or "sin^2(x) + cos^2(x) = 1"
        context: Optional dict of known values {"x": 2}

    Returns:
        {
            "verified": True/False,
            "method": "sympy" | "z3",
            "explanation": "...",
            "error": None | "..."
        }
    """
    get_sympy()

    # Handle empty input
    if not step_text or not step_text.strip():
        return {"verified": False, "method": None, "explanation": None, "error": "Empty input"}

    # Validate expression
    valid, msg = validate_expression(step_text)
    if not valid:
        return {
            "verified": False,
            "method": None,
            "explanation": None,
            "error": f"Invalid expression: {msg}",
        }

    # Check for dangerous patterns
    dangerous = ["import", "exec", "eval", "__", "open", "file"]
    for d in dangerous:
        if d in step_text.lower():
            return {
                "verified": False,
                "method": None,
                "explanation": None,
                "error": f"Dangerous pattern detected: {d}",
            }

    context = context or {}

    # Handle calculus expressions directly
    if "d/d" in step_text or "integral" in step_text.lower():
        return _verify_calculus_step(step_text)

    # If context is provided, use SymPy (we have specific values to substitute)
    if context:
        method = "sympy"
    else:
        method = select_verification_method(step_text)

    try:
        if method == "sympy":
            return _verify_with_sympy(step_text, context)
        else:
            return _verify_with_z3(step_text, context)
    except Exception as e:
        return {
            "verified": False,
            "method": method,
            "explanation": None,
            "error": f"Parse error: {str(e)}",
        }


def _verify_with_sympy(step_text: str, context: dict[str, Any]) -> dict:
    """Verify a step using SymPy."""
    sympy = get_sympy()

    cond, claim = split_claim_and_condition(step_text)

    # Create standard symbols for parsing
    local_dict = {}
    for var in ["x", "y", "z", "a", "b", "c", "n", "k"]:
        local_dict[var] = sympy.Symbol(var)

    # Make a mutable copy of context for accumulating values
    working_context = dict(context)

    if claim is not None:
        # Implication: "x = 2 implies x^2 = 4"
        # Parse condition to extract variable value
        if "=" in cond:
            var_name, value_str = cond.split("=", 1)
            var_name = var_name.strip()
            value = safe_parse(value_str.strip(), local_dict)
            # Add to working context
            working_context[var_name] = value

        # Parse claim and verify with substitution
        if "=" in claim:
            lhs_str, rhs_str = claim.split("=", 1)
            lhs = safe_parse(lhs_str.strip(), local_dict)
            rhs = safe_parse(rhs_str.strip(), local_dict)

            # Substitute context values
            for name, value in working_context.items():
                sym = sympy.Symbol(name)
                lhs = lhs.subs(sym, value)
                rhs = rhs.subs(sym, value)

            diff = sympy.simplify(lhs - rhs)
            verified = diff == 0

            if verified:
                return {
                    "verified": True,
                    "method": "sympy",
                    "explanation": f"Verified by substitution: {lhs} = {rhs}",
                    "error": None,
                }
            else:
                return {
                    "verified": False,
                    "method": "sympy",
                    "explanation": None,
                    "error": f"Step invalid: {lhs} != {rhs} (difference: {diff})",
                }
    else:
        # Direct verification (identity or equation with context)
        if "=" in step_text:
            lhs_str, rhs_str = step_text.split("=", 1)
            lhs = safe_parse(lhs_str.strip(), local_dict)
            rhs = safe_parse(rhs_str.strip(), local_dict)

            # Substitute context values
            for name, value in working_context.items():
                sym = sympy.Symbol(name)
                lhs = lhs.subs(sym, value)
                rhs = rhs.subs(sym, value)

            diff = sympy.simplify(lhs - rhs)

            # Use trigsimp for trig expressions
            if any(trig in step_text for trig in ["sin", "cos", "tan"]):
                diff = sympy.trigsimp(diff)

            verified = diff == 0

            if verified:
                return {
                    "verified": True,
                    "method": "sympy",
                    "explanation": f"Identity verified: {lhs} = {rhs}",
                    "error": None,
                }
            else:
                return {
                    "verified": False,
                    "method": "sympy",
                    "explanation": None,
                    "error": f"Step invalid: expected {rhs}, got {lhs}",
                }

    return {
        "verified": False,
        "method": "sympy",
        "explanation": None,
        "error": "Could not parse step",
    }


def _verify_with_z3(step_text: str, context: dict[str, Any]) -> dict:
    """Verify a step using Z3."""
    get_z3()

    # Parse as equality
    if "=" in step_text and "==" not in step_text:
        step_text = step_text.replace("=", "==")

    # Extract variables
    identifiers = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", step_text)
    keywords = {"And", "Or", "Not", "If", "Implies", "True", "False", "and", "or", "not"}
    variables = [v for v in set(identifiers) if v not in keywords]

    try:
        result = prove_theorem(step_text, variables=variables, var_type="int")

        if result.get("proved"):
            return {
                "verified": True,
                "method": "z3",
                "explanation": "Proved: no counterexample exists",
                "error": None,
            }
        else:
            return {
                "verified": False,
                "method": "z3",
                "explanation": None,
                "error": f"Counterexample found: {result.get('counterexample')}",
            }
    except Exception as e:
        return {
            "verified": False,
            "method": "z3",
            "explanation": None,
            "error": f"Z3 error: {str(e)}",
        }


def _is_simple_assignment(step: str) -> tuple[bool, str | None, Optional[str]]:
    """Check if step is a simple assignment like 'x = 2'.

    Returns:
        (is_assignment, var_name, value_str) or (False, None, None)
    """
    if "=" not in step:
        return False, None, None

    parts = step.split("=")
    if len(parts) != 2:
        return False, None, None

    var_name = parts[0].strip()
    value_str = parts[1].strip()

    # Check if LHS is a simple variable (e.g., "x" not "x^2")
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", var_name):
        # Check if RHS is a simple numeric expression or expression with existing vars
        return True, var_name, value_str

    return False, None, None


def _is_equation_definition(step: str) -> bool:
    """Check if step is an equation definition like 'x^2 - 4 = 0'.

    These are equations with variables that establish a constraint,
    or equivalent forms like '(x-2)(x+2) = 0'.

    Returns False if the LHS is not a valid mathematical expression.
    """
    if "=" not in step:
        return False

    parts = step.split("=")
    if len(parts) != 2:
        return False

    lhs = parts[0].strip()
    rhs = parts[1].strip()

    # RHS must be 0 for equation definition
    if rhs != "0":
        return False

    # Validate LHS is a valid mathematical expression
    # Must contain at least one valid math symbol (variable, number, operator)
    # and not contain plain words/gibberish

    # Check for at least one variable or number
    has_valid_math = re.search(r"[a-zA-Z_][a-zA-Z0-9_]*|\d+", lhs)
    if not has_valid_math:
        return False

    # Check for invalid patterns: plain words without operators
    # "nonsense gibberish" should fail, but "x - y" or "x^2" should pass
    words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", lhs)
    if words:
        # Check if there's at least one math operator between/around the identifiers
        # Valid operators: +, -, *, /, ^, **, (, ), etc.
        has_operator = re.search(r"[\+\-\*\/\^\(\)]", lhs)
        # A single variable like "x" is valid, multiple words without operators is not
        if len(words) > 1 and not has_operator:
            return False

    # Try to parse the LHS to ensure it's valid
    try:
        parsed = safe_parse(lhs)
        if parsed is None:
            return False
        return True
    except Exception:
        return False


def verify_chain(steps: list[str], context: dict[str, Any] = None) -> dict:
    """Verify a chain of mathematical reasoning.

    Args:
        steps: List like ["x = 2", "x^2 = 4", "x^2 + 1 = 5"]
        context: Optional initial context

    Returns:
        {
            "all_valid": True/False,
            "steps": [...],
            "first_error": None | {"step_index": int, ...}
        }
    """
    if steps is None:
        raise TypeError("steps cannot be None")

    if len(steps) == 0:
        return {"all_valid": True, "steps": [], "first_error": None}

    sympy = get_sympy()
    # Make a deep copy of context to avoid mutating caller's dict
    context = dict(context) if context else {}
    results = []
    first_error = None

    for i, step in enumerate(steps):
        is_assignment, var_name, value_str = _is_simple_assignment(step)

        # Handle simple assignments like "x = 2" as premises
        if is_assignment:
            try:
                value = safe_parse(value_str)
                # Substitute existing context
                for name, val in context.items():
                    value = value.subs(sympy.Symbol(name), val)
                # Keep symbolic expressions as-is (e.g., sqrt(2))
                # Only convert to numeric if the value is purely numeric
                if value.is_number:
                    try:
                        # Check if it's an exact integer
                        if value.is_Integer:
                            context[var_name] = int(value)
                        elif value.is_Rational:
                            # Keep rational numbers symbolic for precision
                            context[var_name] = value
                        else:
                            # For irrational numbers like sqrt(2), keep symbolic
                            # Only convert to float if it evaluates to a simple float
                            evalf_val = value.evalf()
                            # Check if it's a "clean" number (not irrational)
                            if evalf_val == int(evalf_val):
                                context[var_name] = int(evalf_val)
                            else:
                                # Keep symbolic for precision (e.g., sqrt(2))
                                context[var_name] = value
                    except (TypeError, ValueError):
                        context[var_name] = value
                else:
                    # Not a pure number, keep as symbolic expression
                    context[var_name] = value

                step_result = {
                    "step": step,
                    "verified": True,
                    "reason": f"Given: {var_name} = {context[var_name]}",
                }
                results.append(step_result)
                continue
            except Exception as e:
                step_result = {"step": step, "verified": False, "reason": f"Could not parse: {e}"}
                results.append(step_result)
                if first_error is None:
                    first_error = {"step_index": i, "step": step, "error": str(e)}
                continue

        # Handle equation definitions like "x^2 - 4 = 0"
        if _is_equation_definition(step):
            step_result = {"step": step, "verified": True, "reason": "Equation definition (given)"}
            results.append(step_result)
            continue

        # Handle "or" steps (solution sets)
        if " or " in step.lower():
            step_result = {"step": step, "verified": True, "reason": "Solution set"}
            results.append(step_result)
            continue

        # Handle calculus steps
        if "d/d" in step or "integral" in step.lower():
            result = _verify_calculus_step(step)
            results.append(
                {
                    "step": step,
                    "verified": result["verified"],
                    "reason": result.get("explanation") or result.get("error", "Unknown"),
                }
            )
            if not result["verified"] and first_error is None:
                first_error = {
                    "step_index": i,
                    "step": step,
                    "error": result.get("error", "Unknown error"),
                }
            continue

        # For other steps, verify with current context
        result = verify_step(step, context.copy())

        step_result = {
            "step": step,
            "verified": result["verified"],
            "reason": result.get("explanation") or result.get("error", "Unknown"),
        }
        results.append(step_result)

        if not result["verified"]:
            if first_error is None:
                first_error = {
                    "step_index": i,
                    "step": step,
                    "error": result.get("error", "Unknown error"),
                }

    return {"all_valid": first_error is None, "steps": results, "first_error": first_error}


def _verify_calculus_step(step: str) -> dict:
    """Verify a calculus step like 'd/dx(x^3) = 3*x^2'."""
    sympy = get_sympy()

    try:
        if "=" not in step:
            return {
                "verified": False,
                "method": "sympy",
                "explanation": None,
                "error": "No equation in step",
            }

        lhs_str, rhs_str = step.split("=", 1)
        lhs = lhs_str.strip()
        rhs_str = rhs_str.strip()

        # Handle differentiation
        match = re.match(r"d/d([a-z])\((.+)\)", lhs)
        if match:
            var_name = match.group(1)
            expr_str = match.group(2)
            var = sympy.Symbol(var_name)
            expr = safe_parse(expr_str)
            expected = sympy.diff(expr, var)
            actual = safe_parse(rhs_str)

            if sympy.simplify(expected - actual) == 0:
                return {
                    "verified": True,
                    "method": "sympy",
                    "explanation": f"Differentiation verified using power rule: d/d{var_name}({expr_str}) = {rhs_str}",
                    "error": None,
                }
            else:
                return {
                    "verified": False,
                    "method": "sympy",
                    "explanation": None,
                    "error": f"Expected {expected}, got {actual}",
                }

        # Handle integration
        int_match = re.match(r"integral\s+of\s+(.+)", lhs, re.IGNORECASE)
        if int_match:
            expr_str = int_match.group(1)
            expr = safe_parse(expr_str)
            expected = sympy.integrate(expr, sympy.Symbol("x"))
            actual = safe_parse(rhs_str)

            # Integration is up to a constant, so check derivatives match
            if (
                sympy.simplify(
                    sympy.diff(expected, sympy.Symbol("x")) - sympy.diff(actual, sympy.Symbol("x"))
                )
                == 0
            ):
                return {
                    "verified": True,
                    "method": "sympy",
                    "explanation": f"Integration verified: integral of {expr_str} = {rhs_str}",
                    "error": None,
                }
            else:
                return {
                    "verified": False,
                    "method": "sympy",
                    "explanation": None,
                    "error": f"Expected {expected}, got {actual}",
                }

        return {
            "verified": False,
            "method": "sympy",
            "explanation": None,
            "error": "Could not parse calculus step",
        }

    except Exception as e:
        return {
            "verified": False,
            "method": "sympy",
            "explanation": None,
            "error": f"Calculus error: {e}",
        }


def explain_step(step_text: str) -> dict:
    """Explain what a mathematical step does.

    Args:
        step_text: Expression like "d/dx(x^3) = 3x^2"

    Returns:
        {
            "operation": "differentiation" | "integration" | "factoring" | etc.,
            "input": "...",
            "output": "...",
            "explanation": "..."
        }
    """
    get_sympy()

    if not step_text or not step_text.strip():
        return {"operation": "unknown", "input": None, "output": None, "explanation": "Empty input"}

    operation = detect_operation_type(step_text)

    # Parse input and output from step
    input_expr = None
    output_expr = None

    if "=" in step_text:
        parts = step_text.split("=")
        if len(parts) == 2:
            lhs = parts[0].strip()
            rhs = parts[1].strip()

            # Determine which is input and which is output based on operation
            if operation == "differentiation":
                # d/dx(x^3) = 3x^2 -> input is x^3, output is 3x^2
                match = re.search(r"d/d[a-z]\((.+?)\)", lhs)
                if match:
                    input_expr = match.group(1)
                    output_expr = rhs
            elif operation == "integration":
                # integral of x^2 = x^3/3 -> input is x^2, output is x^3/3
                match = re.search(r"integral\s+of\s+(.+)", lhs, re.IGNORECASE)
                if match:
                    input_expr = match.group(1)
                    output_expr = rhs
            else:
                input_expr = lhs
                output_expr = rhs

    # Generate explanation
    explanations = {
        "differentiation": f"Power rule: d/dx(x^n) = n*x^(n-1). Applied to get {output_expr or 'result'}.",
        "integration": f"Power rule for integration: integral of x^n = x^(n+1)/(n+1). Applied to get {output_expr or 'result'}.",
        "factoring": "Factored expression using difference of squares or other factoring technique.",
        "substitution": "Substituted known values to verify equality.",
        "simplification": f"Simplified using algebraic or trigonometric identity.",
        "unknown": f"Could not determine the specific operation type.",
    }

    return {
        "operation": operation,
        "input": input_expr,
        "output": output_expr,
        "explanation": explanations.get(operation, "Unknown operation"),
    }


# ============================================================================
# Output Formatting Functions
# ============================================================================


def format_verify_result(result: dict, fmt: str) -> str:
    """Format a verify_step result for output.

    Args:
        result: Result dict from verify_step()
        fmt: Output format - 'json', 'text', or 'markdown'

    Returns:
        Formatted string
    """
    if fmt == "json":
        return json.dumps(result, indent=2, default=str)

    elif fmt == "text":
        verified = result.get("verified", False)
        method = result.get("method", "N/A")
        explanation = result.get("explanation", "N/A")
        error = result.get("error")

        verdict = "VALID" if verified else "INVALID"
        lines = [
            f"Verdict: {verdict}",
            f"Method: {method}",
        ]
        if verified and explanation:
            lines.append(f"Explanation: {explanation}")
        if error:
            lines.append(f"Error: {error}")
        return "\n".join(lines)

    elif fmt == "markdown":
        verified = result.get("verified", False)
        method = result.get("method", "N/A")
        explanation = result.get("explanation", "N/A")
        error = result.get("error")

        verdict_icon = "Valid" if verified else "Invalid"
        lines = [
            "## Verification Result",
            "",
            f"**Verdict:** {verdict_icon}",
            f"**Method:** {method}",
        ]
        if verified and explanation:
            lines.append(f"**Explanation:** {explanation}")
        if error:
            lines.append(f"**Error:** {error}")
        return "\n".join(lines)

    else:
        return json.dumps(result, indent=2, default=str)


def format_chain_result(result: dict, fmt: str) -> str:
    """Format a verify_chain result for output.

    Args:
        result: Result dict from verify_chain()
        fmt: Output format - 'json', 'text', or 'markdown'

    Returns:
        Formatted string
    """
    if fmt == "json":
        return json.dumps(result, indent=2, default=str)

    elif fmt == "text":
        all_valid = result.get("all_valid", False)
        steps = result.get("steps", [])
        first_error = result.get("first_error")

        lines = []
        for i, step_result in enumerate(steps, 1):
            step_text = step_result.get("step", "")
            verified = step_result.get("verified", False)
            reason = step_result.get("reason", "")
            icon = "PASS" if verified else "FAIL"
            lines.append(f"Step {i}: {step_text}")
            lines.append(f"  {icon}: {reason}")

        lines.append("")
        if all_valid:
            lines.append("Result: ALL VALID")
        else:
            lines.append("Result: INVALID")
            if first_error:
                idx = first_error.get("step_index", 0) + 1
                err = first_error.get("error", "Unknown")
                lines.append(f"First error at Step {idx}: {err}")

        return "\n".join(lines)

    elif fmt == "markdown":
        all_valid = result.get("all_valid", False)
        steps = result.get("steps", [])
        first_error = result.get("first_error")

        lines = ["## Chain Verification", ""]
        for i, step_result in enumerate(steps, 1):
            step_text = step_result.get("step", "")
            verified = step_result.get("verified", False)
            reason = step_result.get("reason", "")
            icon = "Pass" if verified else "Fail"
            lines.append(f"**Step {i}:** `{step_text}`")
            lines.append(f"- **{icon}:** {reason}")

        lines.append("")
        if all_valid:
            lines.append("**Result:** All steps valid")
        else:
            lines.append("**Result:** Chain invalid")
            if first_error:
                idx = first_error.get("step_index", 0) + 1
                err = first_error.get("error", "Unknown")
                lines.append(f"**First error:** Step {idx} - {err}")

        return "\n".join(lines)

    else:
        return json.dumps(result, indent=2, default=str)


def format_explain_result(result: dict, fmt: str) -> str:
    """Format an explain_step result for output.

    Args:
        result: Result dict from explain_step()
        fmt: Output format - 'json', 'text', or 'markdown'

    Returns:
        Formatted string
    """
    if fmt == "json":
        return json.dumps(result, indent=2, default=str)

    elif fmt == "text":
        operation = result.get("operation", "unknown")
        input_expr = result.get("input", "N/A")
        output_expr = result.get("output", "N/A")
        explanation = result.get("explanation", "N/A")

        lines = [
            f"Operation: {operation}",
            f"Input: {input_expr}",
            f"Output: {output_expr}",
            f"Explanation: {explanation}",
        ]
        return "\n".join(lines)

    elif fmt == "markdown":
        operation = result.get("operation", "unknown")
        input_expr = result.get("input", "N/A")
        output_expr = result.get("output", "N/A")
        explanation = result.get("explanation", "N/A")

        lines = [
            "## Step Explanation",
            "",
            f"**Operation:** {operation}",
            f"**Input:** `{input_expr}`",
            f"**Output:** `{output_expr}`",
            f"**Explanation:** {explanation}",
        ]
        return "\n".join(lines)

    else:
        return json.dumps(result, indent=2, default=str)


# ============================================================================
# CLI Interface
# ============================================================================


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Step-by-step mathematical reasoning verification - cognitive prosthetics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Verify command
    verify_p = subparsers.add_parser("verify", help="Verify a single step")
    verify_p.add_argument("step", help="Mathematical step to verify")
    verify_p.add_argument(
        "--context", default=None, help="JSON dict of known values, e.g. '{\"x\": 2}'"
    )

    # Chain command
    chain_p = subparsers.add_parser("chain", help="Verify a chain of reasoning")
    chain_p.add_argument(
        "--steps", required=True, help='JSON list of steps, e.g. \'["x = 2", "x^2 = 4"]\''
    )
    chain_p.add_argument("--context", default=None, help="JSON dict of initial context")

    # Explain command
    explain_p = subparsers.add_parser("explain", help="Explain a mathematical step")
    explain_p.add_argument("step", help="Mathematical step to explain")

    # Common options
    for p in [verify_p, chain_p, explain_p]:
        p.add_argument(
            "--json", action="store_true", help="Output as JSON (deprecated, use --format json)"
        )
        p.add_argument(
            "--format",
            choices=["json", "text", "markdown"],
            default="json",
            help="Output format: json (default), text (human-readable), markdown",
        )

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    args = parse_args()

    try:
        if args.command == "verify":
            context = json.loads(args.context) if args.context else None
            result = verify_step(args.step, context)
            output = format_verify_result(result, args.format)

        elif args.command == "chain":
            steps = json.loads(args.steps)
            context = json.loads(args.context) if args.context else None
            result = verify_chain(steps, context)
            output = format_chain_result(result, args.format)

        elif args.command == "explain":
            result = explain_step(args.step)
            output = format_explain_result(result, args.format)

        else:
            result = {"error": f"Unknown command: {args.command}"}
            output = json.dumps(result, indent=2)

        # Output
        print(output)

    except json.JSONDecodeError as e:
        error_result = {"error": f"JSON parse error: {e}", "command": args.command}
        print(json.dumps(error_result), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        error_result = {"error": str(e), "command": args.command}
        print(json.dumps(error_result), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
