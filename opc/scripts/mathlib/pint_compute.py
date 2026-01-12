#!/usr/bin/env python3
"""Unit conversion computation script - Cognitive prosthetics for Claude.

USAGE:
    # Parse a quantity
    uv run python -m runtime.harness scripts/pint_compute.py \
        parse "100 km/h"

    # Convert between units
    uv run python -m runtime.harness scripts/pint_compute.py \
        convert "5 meters" --to feet

    # Unit-aware calculation
    uv run python -m runtime.harness scripts/pint_compute.py \
        calc "5 m * 3 s"

    # Check dimensional compatibility
    uv run python -m runtime.harness scripts/pint_compute.py \
        check newton --against "kg * m / s^2"

    # Simplify compound units
    uv run python -m runtime.harness scripts/pint_compute.py \
        simplify "1 kg*m/s^2"

Requires: pint (pip install pint)
"""

import argparse
import asyncio
import json
import re
import sys
from typing import Any

# =============================================================================
# Lazy Import
# =============================================================================


_ureg = None


def get_pint():
    """Lazy import Pint - only load when needed."""
    global _ureg
    if _ureg is None:
        import pint

        _ureg = pint.UnitRegistry()
    return _ureg


# =============================================================================
# Input Validation
# =============================================================================


def validate_expression(expr_str: str) -> tuple[bool, str]:
    """Validate expression before parsing.

    Returns:
        (valid, message)
    """
    # Check for dangerous patterns
    dangerous = ["import", "exec", "eval", "__", "open", "file", "os.", "subprocess"]
    expr_lower = expr_str.lower()
    for d in dangerous:
        if d in expr_lower:
            return False, f"Potentially dangerous pattern: {d}"

    # Check for empty expression
    if not expr_str.strip():
        return False, "Empty expression"

    return True, "Valid"


# =============================================================================
# Core Functions
# =============================================================================


def parse_quantity(qty_str: str) -> dict:
    """Parse a quantity string into magnitude and units.

    Args:
        qty_str: String like "5 meters", "10 kg*m/s^2", "100 km/h"

    Returns:
        {
            "magnitude": float,
            "units": str,
            "dimensionality": str,
            "latex": str
        }
        Or {"error": str} on failure.
    """
    # Validate first
    valid, msg = validate_expression(qty_str)
    if not valid:
        return {"error": msg}

    if not qty_str.strip():
        return {"error": "Empty expression"}

    try:
        ureg = get_pint()
        quantity = ureg.parse_expression(qty_str)

        return {
            "magnitude": float(quantity.magnitude),
            "units": str(quantity.units),
            "dimensionality": str(quantity.dimensionality),
            "latex": f"{quantity.magnitude:g}\\,\\mathrm{{{quantity.units:~P}}}",
        }
    except Exception as e:
        error_msg = str(e).lower()
        if "undefined" in error_msg or "unknown" in error_msg:
            return {"error": f"Undefined unit in '{qty_str}': {e}"}
        return {"error": f"Cannot parse quantity '{qty_str}': {e}"}


def convert_units(qty_str: str, to_unit: str) -> dict:
    """Convert a quantity to different units.

    Args:
        qty_str: Quantity to convert (e.g., "5 meters")
        to_unit: Target units (e.g., "feet")

    Returns:
        {
            "result": str,
            "magnitude": float,
            "units": str,
            "original": str,
            "latex": str
        }
        Or {"error": str} on failure.
    """
    # Validate inputs
    valid, msg = validate_expression(qty_str)
    if not valid:
        return {"error": msg}

    valid, msg = validate_expression(to_unit)
    if not valid:
        return {"error": msg}

    try:
        ureg = get_pint()
        quantity = ureg.parse_expression(qty_str)
        target = ureg.parse_expression(to_unit)

        # Convert
        converted = quantity.to(target.units)

        return {
            "result": str(converted),
            "magnitude": float(converted.magnitude),
            "units": str(converted.units),
            "original": qty_str,
            "target_units": to_unit,
            "latex": f"{converted.magnitude:g}\\,\\mathrm{{{converted.units:~P}}}",
        }
    except Exception as e:
        error_msg = str(e).lower()
        if "dimension" in error_msg or "cannot convert" in error_msg:
            return {
                "error": f"Dimensionality error: Cannot convert '{qty_str}' to '{to_unit}'. {e}"
            }
        return {"error": f"Conversion error: {e}"}


def unit_calc(expr_str: str) -> dict:
    """Perform unit-aware calculation.

    Args:
        expr_str: Expression like "5 m * 3 s", "10 m / 2 s", "5 m + 300 cm"

    Returns:
        {
            "result": str,
            "magnitude": float,
            "units": str,
            "expression": str,
            "latex": str
        }
        Or {"error": str} on failure.
    """
    # Validate
    valid, msg = validate_expression(expr_str)
    if not valid:
        return {"error": msg}

    try:
        ureg = get_pint()

        # Parse the expression - pint can handle basic arithmetic
        # We need to be careful about how we evaluate this
        # Use a safe evaluation approach

        # Replace ^ with ** for exponentiation
        expr_normalized = expr_str.replace("^", "**")

        # Parse the expression safely using pint's expression parser
        # For compound expressions, we need to handle operators
        result = _safe_unit_eval(expr_normalized, ureg)

        return {
            "result": str(result),
            "magnitude": float(result.magnitude),
            "units": str(result.units),
            "expression": expr_str,
            "dimensionality": str(result.dimensionality),
            "latex": f"{result.magnitude:g}\\,\\mathrm{{{result.units:~P}}}",
        }
    except Exception as e:
        error_msg = str(e).lower()
        if "dimension" in error_msg or "cannot convert" in error_msg:
            return {
                "error": f"Dimensionality error: Cannot perform operation. Units are not compatible. {e}"
            }
        return {"error": f"Calculation error: {e}"}


def _safe_unit_eval(expr: str, ureg) -> Any:
    """Safely evaluate a unit expression.

    This uses a restricted evaluation with only pint quantities.
    """
    # Tokenize and parse the expression
    # We'll handle simple binary operations

    # First, try direct parsing (works for simple quantities)
    try:
        # Check if it's a simple quantity (no operators except in units)
        if not any(
            op in expr
            for op in ["+", "-", "*", "/", "**"]
            if op not in ["*", "/"] or not re.match(r"^[\d\s\w\.\^*/]+$", expr.replace("**", "^"))
        ):
            return ureg.parse_expression(expr)
    except Exception:
        pass

    # For expressions with operators, we need to parse more carefully
    # Split by operators while keeping them
    # Handle parentheses first

    # Simple approach: use Python's eval with a restricted namespace
    # containing only pint quantities

    # Create a safe namespace
    safe_namespace = {
        "ureg": ureg,
        "Q_": ureg.Quantity,
    }

    # Preprocess: wrap bare numbers with units
    # Pattern: find "number unit" patterns and wrap them
    # This is a simplified approach

    # Tokenize by operators
    tokens = _tokenize_expr(expr)

    # Convert quantity tokens to Q_ format
    processed_tokens = []
    for token in tokens:
        token = token.strip()
        if token in ["+", "-", "*", "/", "**", "(", ")"]:
            processed_tokens.append(token)
        elif token:
            # Try to parse as a quantity
            try:
                ureg.parse_expression(token)
                processed_tokens.append(f"ureg.parse_expression('{token}')")
            except Exception:
                processed_tokens.append(token)

    # Join and evaluate
    safe_expr = " ".join(processed_tokens)

    # Use restricted eval
    result = eval(safe_expr, {"__builtins__": {}}, safe_namespace)

    return result


def _tokenize_expr(expr: str) -> list:
    """Tokenize a unit expression into quantities and operators."""
    tokens = []
    current = ""
    i = 0
    paren_depth = 0

    while i < len(expr):
        c = expr[i]

        if c == "(":
            if current.strip():
                tokens.append(current.strip())
                current = ""
            tokens.append("(")
            paren_depth += 1
        elif c == ")":
            if current.strip():
                tokens.append(current.strip())
                current = ""
            tokens.append(")")
            paren_depth -= 1
        elif c == "*" and i + 1 < len(expr) and expr[i + 1] == "*":
            # Exponentiation
            if current.strip():
                tokens.append(current.strip())
                current = ""
            tokens.append("**")
            i += 1
        elif c in ["+", "-"]:
            # Could be operator or sign
            # If previous token exists and is not an operator, treat as operator
            if current.strip() and current.strip()[-1] not in "+-*/(":
                tokens.append(current.strip())
                current = ""
                tokens.append(c)
            else:
                current += c
        elif c == "*" or c == "/":
            # Check if this is a unit separator or operator
            # Unit separators are typically not surrounded by spaces for units
            # like "kg*m/s^2", while operators have quantities like "5 m * 3 s"

            # Look ahead and behind for spaces to determine
            has_space_before = i > 0 and expr[i - 1] == " "
            has_space_after = i + 1 < len(expr) and expr[i + 1] == " "

            if has_space_before or has_space_after:
                # This is an operator
                if current.strip():
                    tokens.append(current.strip())
                    current = ""
                tokens.append(c)
            else:
                # This is part of a unit
                current += c
        else:
            current += c

        i += 1

    if current.strip():
        tokens.append(current.strip())

    return tokens


def check_dimensions(unit1: str, unit2: str) -> dict:
    """Check if two units have compatible dimensions.

    Args:
        unit1: First unit expression (e.g., "newton")
        unit2: Second unit expression (e.g., "kg * m / s^2")

    Returns:
        {
            "compatible": bool,
            "dim1": str,
            "dim2": str,
            "unit1": str,
            "unit2": str
        }
    """
    # Validate inputs
    valid, msg = validate_expression(unit1)
    if not valid:
        return {"error": msg}

    valid, msg = validate_expression(unit2)
    if not valid:
        return {"error": msg}

    try:
        ureg = get_pint()

        # Parse both as quantities (with magnitude 1)
        q1 = ureg.parse_expression(f"1 {unit1}")
        q2 = ureg.parse_expression(f"1 {unit2}")

        # Compare dimensionality
        compatible = q1.dimensionality == q2.dimensionality

        return {
            "compatible": compatible,
            "dim1": str(q1.dimensionality),
            "dim2": str(q2.dimensionality),
            "unit1": unit1,
            "unit2": unit2,
            "dimensionality": str(q1.dimensionality) if compatible else None,
        }
    except Exception as e:
        return {"error": f"Dimension check error: {e}"}


def simplify_units(qty_str: str) -> dict:
    """Simplify compound units to base or named units.

    Args:
        qty_str: Quantity with compound units (e.g., "1 kg*m/s^2")

    Returns:
        {
            "simplified": str,
            "magnitude": float,
            "base_units": str,
            "dimensionality": str,
            "latex": str
        }
    """
    # Validate
    valid, msg = validate_expression(qty_str)
    if not valid:
        return {"error": msg}

    try:
        ureg = get_pint()
        quantity = ureg.parse_expression(qty_str)

        # Get base units representation
        base_quantity = quantity.to_base_units()

        # Try to get a compact representation
        try:
            compact = quantity.to_compact()
            compact_str = str(compact)
        except Exception:
            compact_str = str(quantity)

        return {
            "simplified": compact_str,
            "magnitude": float(quantity.magnitude),
            "base_units": str(base_quantity.units),
            "base_magnitude": float(base_quantity.magnitude),
            "dimensionality": str(quantity.dimensionality),
            "original": qty_str,
            "latex": f"{quantity.magnitude:g}\\,\\mathrm{{{quantity.units:~P}}}",
        }
    except Exception as e:
        return {"error": f"Simplification error: {e}"}


# =============================================================================
# CLI Interface
# =============================================================================


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Unit conversion computation - cognitive prosthetics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Parse command
    parse_p = subparsers.add_parser("parse", help="Parse a quantity")
    parse_p.add_argument("quantity", help="Quantity to parse (e.g., '100 km/h')")

    # Convert command
    convert_p = subparsers.add_parser("convert", help="Convert between units")
    convert_p.add_argument("quantity", help="Quantity to convert (e.g., '5 meters')")
    convert_p.add_argument("--to", required=True, help="Target units (e.g., 'feet')")

    # Calc command
    calc_p = subparsers.add_parser("calc", help="Unit-aware calculation")
    calc_p.add_argument("expression", help="Expression to evaluate (e.g., '5 m * 3 s')")

    # Check command
    check_p = subparsers.add_parser("check", help="Check dimensional compatibility")
    check_p.add_argument("unit1", help="First unit (e.g., 'newton')")
    check_p.add_argument("--against", required=True, help="Second unit (e.g., 'kg * m / s^2')")

    # Simplify command
    simplify_p = subparsers.add_parser("simplify", help="Simplify compound units")
    simplify_p.add_argument("quantity", help="Quantity to simplify (e.g., '1 kg*m/s^2')")

    # Common options
    for p in [parse_p, convert_p, calc_p, check_p, simplify_p]:
        p.add_argument("--json", action="store_true", help="Output as JSON")

    # Filter out script path from args
    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def main():
    """Main entry point."""
    args = parse_args()

    try:
        if args.command == "parse":
            result = parse_quantity(args.quantity)
        elif args.command == "convert":
            result = convert_units(args.quantity, args.to)
        elif args.command == "calc":
            result = unit_calc(args.expression)
        elif args.command == "check":
            result = check_dimensions(args.unit1, args.against)
        elif args.command == "simplify":
            result = simplify_units(args.quantity)
        else:
            result = {"error": f"Unknown command: {args.command}"}

        # Output
        print(json.dumps(result, indent=2))

        # Exit with error code if result contains error
        if result.get("error"):
            sys.exit(1)

    except Exception as e:
        error_result = {"error": str(e), "command": args.command}
        print(json.dumps(error_result), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
