"""Shared utilities for math computation CLI scripts.

This module provides:
- JSON output formatting with consistent structure
- Input parsers for matrices, expressions, arrays
- LaTeX formatters for common mathematical types
- CLI builder utilities (subparser factory)
- Error handling wrapper for consistent error JSON
- Decorator for function registration

USAGE:
    from scripts.math_base import (
        math_command, format_output, format_error,
        parse_matrix, parse_array, parse_expression,
        format_latex_matrix, format_latex_scalar,
        create_subparser, register_commands,
        parse_bound, parse_complex
    )
"""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Dict, List, Optional, TypeVar, Union

# Type variables for generic decorators
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Command Registry
# =============================================================================


@dataclass
class MathCommand:
    """Metadata for a registered math command."""

    name: str
    func: Callable
    category: str
    description: str
    latex_template: str | None = None
    args: list[Dict[str, Any]] = field(default_factory=list)


# Global registry per script - use module-level dict
_command_registry: dict[str, MathCommand] = {}


def math_command(
    name: str,
    category: str,
    description: str = "",
    latex_template: str | None = None,
    args: List[Dict[str, Any]] | None = None,
) -> Callable[[F], F]:
    """Decorator to register a math command.

    Args:
        name: CLI command name (e.g., "det", "solve")
        category: Category for help grouping (e.g., "linalg", "calculus")
        description: Help text for the command
        latex_template: Optional LaTeX template with {result} placeholder
        args: List of argument specifications for argparse

    Returns:
        Decorated function

    Example:
        @math_command(
            name="det",
            category="linalg",
            description="Compute matrix determinant",
            latex_template=r"\\det(A) = {result}",
            args=[
                {"name": "matrix", "help": "Matrix as [[a,b],[c,d]]"},
                {"name": "--precision", "type": int, "default": 15}
            ]
        )
        def compute_det(matrix: str, precision: int = 15) -> dict:
            result = np.linalg.det(parse_matrix(matrix))
            return {"result": result}
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return format_output(result, latex_template)
            except Exception as e:
                return format_error(str(e), name)

        # Register the command
        _command_registry[name] = MathCommand(
            name=name,
            func=wrapper,
            category=category,
            description=description,
            latex_template=latex_template,
            args=args or [],
        )

        # Preserve original function for testing
        wrapper._original = func
        wrapper._command_meta = _command_registry[name]

        return wrapper

    return decorator


def get_registry() -> dict[str, MathCommand]:
    """Get the command registry."""
    return _command_registry.copy()


def clear_registry() -> None:
    """Clear the registry (useful for testing)."""
    _command_registry.clear()


# =============================================================================
# Output Formatting
# =============================================================================


def format_output(result: dict[str, Any], latex_template: str | None = None) -> Dict[str, Any]:
    """Format computation result as standardized JSON.

    Output structure:
    {
        "result": <computed value>,
        "latex": "<LaTeX representation>",
        "metadata": {
            "type": "<result type>",
            "shape": "<shape if array>",
            ...
        }
    }
    """
    output = {"result": result.get("result"), "metadata": {}}

    # Add LaTeX if provided in result or via template
    if "latex" in result:
        output["latex"] = result["latex"]
    elif latex_template and "result" in result:
        output["latex"] = latex_template.format(result=result["result"])

    # Add any additional fields to metadata
    for key, value in result.items():
        if key not in ("result", "latex"):
            output["metadata"][key] = value

    return output


def format_error(message: str, command: str = "unknown") -> dict[str, Any]:
    """Format error as standardized JSON.

    Output structure:
    {
        "error": true,
        "message": "<error message>",
        "command": "<command that failed>"
    }
    """
    return {"error": True, "message": message, "command": command}


def output_json(data: dict[str, Any], indent: int = 2) -> None:
    """Print data as JSON to stdout."""
    print(json.dumps(data, indent=indent, default=_json_serializer))


def output_error_json(data: dict[str, Any]) -> None:
    """Print error data as JSON to stderr."""
    print(json.dumps(data, indent=2, default=_json_serializer), file=sys.stderr)


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for numpy/mpmath types."""
    # Handle numpy types
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if hasattr(obj, "item"):
        return obj.item()
    # Handle complex numbers
    if isinstance(obj, complex):
        return {"real": obj.real, "imag": obj.imag, "_type": "complex"}
    # Handle mpmath types
    if hasattr(obj, "__float__"):
        try:
            return float(obj)
        except (ValueError, TypeError):
            pass
    # Fallback to string
    return str(obj)


# =============================================================================
# Input Parsers
# =============================================================================


def parse_matrix(matrix_str: str, dtype: str = "float") -> Any:
    """Parse matrix notation into numpy array.

    Accepts:
        - "[[1,2],[3,4]]" - Python list literal
        - "1 2; 3 4" - MATLAB-style with semicolons
        - "1,2,3,4 shape=2,2" - Flat with shape specification

    Args:
        matrix_str: String representation of matrix
        dtype: Target dtype ("float", "complex", "int")

    Returns:
        numpy.ndarray

    Raises:
        ValueError: If matrix cannot be parsed
    """
    import ast

    matrix_str = matrix_str.strip()

    # Try Python literal first
    try:
        data = ast.literal_eval(matrix_str)
        if isinstance(data, list):
            # Import numpy lazily
            import numpy as np

            dtype_map = {"float": np.float64, "complex": np.complex128, "int": np.int64}
            return np.array(data, dtype=dtype_map.get(dtype, np.float64))
    except (ValueError, SyntaxError):
        pass

    # Try MATLAB-style: "1 2; 3 4"
    if ";" in matrix_str:
        import numpy as np

        rows = matrix_str.split(";")
        data = []
        for row in rows:
            row = row.strip()
            if row:
                # Handle both space and comma separated
                if "," in row:
                    data.append([float(x.strip()) for x in row.split(",")])
                else:
                    data.append([float(x) for x in row.split()])
        return np.array(data)

    # Try flat with shape: "1,2,3,4 shape=2,2"
    if "shape=" in matrix_str:
        import numpy as np

        parts = matrix_str.split("shape=")
        values_str = parts[0].strip()
        shape_str = parts[1].strip()

        # Parse values
        if "," in values_str:
            values = [float(x.strip()) for x in values_str.split(",") if x.strip()]
        else:
            values = [float(x) for x in values_str.split() if x.strip()]

        # Parse shape
        shape = tuple(int(x.strip()) for x in shape_str.split(","))
        return np.array(values).reshape(shape)

    raise ValueError(f"Cannot parse matrix: {matrix_str}")


def parse_array(array_str: str, dtype: str = "float") -> Any:
    """Parse array/vector notation.

    Accepts:
        - "[1,2,3,4]" - Python list literal
        - "1 2 3 4" - Space-separated
        - "1,2,3,4" - Comma-separated
    """
    import ast

    array_str = array_str.strip()

    # Try Python literal
    try:
        data = ast.literal_eval(array_str)
        if isinstance(data, (list, tuple)):
            import numpy as np

            dtype_map = {"float": np.float64, "complex": np.complex128, "int": np.int64}
            return np.array(data, dtype=dtype_map.get(dtype, np.float64))
    except (ValueError, SyntaxError):
        pass

    # Try space-separated (only if no commas or brackets)
    if " " in array_str and "," not in array_str and "[" not in array_str:
        import numpy as np

        values = [float(x) for x in array_str.split() if x.strip()]
        return np.array(values)

    # Try comma-separated (without brackets)
    if "," in array_str and "[" not in array_str:
        import numpy as np

        values = [float(x.strip()) for x in array_str.split(",") if x.strip()]
        return np.array(values)

    raise ValueError(f"Cannot parse array: {array_str}")


def parse_expression(expr_str: str, library: str = "numpy") -> Any:
    """Parse mathematical expression string.

    Supports:
        - Numeric literals: "3.14", "2+3j"
        - Scientific notation: "1e-10"
        - Special values: "inf", "-inf", "nan", "pi", "e"

    Args:
        expr_str: Expression string
        library: Target library ("numpy", "scipy", "mpmath")

    Returns:
        Parsed value appropriate for the library
    """
    expr_str = expr_str.strip().lower()

    # Handle special values
    special_map = {
        "inf": float("inf"),
        "-inf": float("-inf"),
        "infinity": float("inf"),
        "-infinity": float("-inf"),
        "nan": float("nan"),
    }

    if expr_str in special_map:
        return special_map[expr_str]

    # Handle constants
    if library == "mpmath":
        try:
            from mpmath import mp

            if expr_str == "pi":
                return mp.pi
            elif expr_str == "e":
                return mp.e
        except ImportError:
            pass
    else:
        import numpy as np

        if expr_str == "pi":
            return np.pi
        elif expr_str == "e":
            return np.e

    # Handle complex notation
    if "j" in expr_str or "i" in expr_str:
        expr_str_fixed = expr_str.replace("i", "j")
        if library == "mpmath":
            try:
                from mpmath import mpc

                return mpc(complex(expr_str_fixed))
            except ImportError:
                pass
        return complex(expr_str_fixed)

    # Try numeric parsing
    try:
        if "." in expr_str or "e" in expr_str:
            return float(expr_str)
        else:
            return int(expr_str)
    except ValueError:
        pass

    raise ValueError(f"Cannot parse expression: {expr_str}")


def parse_bound(s: str) -> Any:
    """Parse a bound that might be a number, 'inf', '-inf', 'pi', etc.

    For use with mpmath integration functions.

    Args:
        s: Bound string (e.g., "0", "pi", "-pi", "inf", "2*pi")

    Returns:
        mpmath number or infinity
    """
    from mpmath import mp

    s = str(s).strip().lower()

    # Handle infinities first
    if s == "inf" or s == "+inf":
        return mp.inf
    elif s == "-inf":
        return -mp.inf

    # Handle symbolic constants
    if s == "pi":
        return mp.pi
    elif s == "-pi":
        return -mp.pi
    elif s == "2*pi" or s == "2pi":
        return 2 * mp.pi
    elif s == "-2*pi" or s == "-2pi":
        return -2 * mp.pi
    elif s == "pi/2":
        return mp.pi / 2
    elif s == "-pi/2":
        return -mp.pi / 2
    elif s == "e":
        return mp.e
    elif s == "-e":
        return -mp.e

    # Try to parse as a number
    try:
        return mp.mpf(s)
    except (ValueError, TypeError):
        raise ValueError(f"Cannot parse bound: {s}")


def parse_complex(s: str) -> Any:
    """Parse a complex number string for mpmath.

    Handles formats like:
        - "1+2j", "1+2i"
        - "3-4j", "3-4i"
        - "5j", "5i"
        - "3" (real only)

    Args:
        s: Complex number string

    Returns:
        mpmath mpc complex number
    """
    from mpmath import mp, mpc

    s = str(s).strip()

    # Replace 'i' with 'j' for Python complex parsing
    s_normalized = s.replace("i", "j")

    # Check if it contains imaginary component
    if "j" in s_normalized:
        try:
            # Use Python's complex() then convert to mpc
            c = complex(s_normalized)
            return mpc(c.real, c.imag)
        except ValueError:
            # Try mpmath's mpc directly
            return mpc(s_normalized)
    else:
        # Real number only
        return mp.mpf(s)


def parse_callable(func_str: str, variables: list[str] = None, library: str = "numpy") -> Callable:
    """Parse a mathematical function string into a callable.

    Args:
        func_str: Function definition like "x**2 + y" or "lambda x: x**2"
        variables: Variable names for non-lambda syntax
        library: Target library ("numpy" or "mpmath")

    Returns:
        Callable that evaluates the function

    WARNING: Uses eval() - only use with trusted input
    """
    func_str = func_str.strip()

    # Create namespace based on library
    if library == "mpmath":
        from mpmath import cos, e, exp, log, mp, pi, sin, sqrt, tan

        namespace = {
            "mp": mp,
            "sin": sin,
            "cos": cos,
            "tan": tan,
            "exp": exp,
            "log": log,
            "sqrt": sqrt,
            "pi": pi,
            "e": e,
        }
    else:
        import numpy as np

        namespace = {
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "tan": np.tan,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "abs": np.abs,
            "power": np.power,
            "pi": np.pi,
            "e": np.e,
        }

    # If it's already a lambda, evaluate directly
    if func_str.startswith("lambda"):
        # Use namespace as globals so lambda can access them
        return eval(func_str, namespace, {})

    # Convert expression to lambda
    if variables is None:
        variables = ["x"]

    var_str = ", ".join(variables)
    lambda_str = f"lambda {var_str}: {func_str}"

    # Use namespace as globals so lambda can access them
    return eval(lambda_str, namespace, {})


# =============================================================================
# LaTeX Formatters
# =============================================================================


def format_latex_scalar(value: Any, precision: int = 6) -> str:
    """Format scalar value as LaTeX."""
    if isinstance(value, complex):
        real = f"{value.real:.{precision}g}"
        imag = f"{abs(value.imag):.{precision}g}"
        sign = "+" if value.imag >= 0 else "-"
        return f"{real} {sign} {imag}i"
    elif isinstance(value, float):
        return f"{value:.{precision}g}"
    else:
        return str(value)


def format_latex_matrix(matrix: Any, precision: int = 4) -> str:
    """Format matrix as LaTeX bmatrix.

    Example output:
        \\begin{bmatrix} 1 & 2 \\\\ 3 & 4 \\end{bmatrix}
    """
    import numpy as np

    if not isinstance(matrix, np.ndarray):
        matrix = np.array(matrix)

    if matrix.ndim == 1:
        # Vector case - single row
        cells = [format_latex_scalar(v, precision) for v in matrix]
        return r"\begin{bmatrix} " + " & ".join(cells) + r" \end{bmatrix}"

    rows = []
    for row in matrix:
        cells = [format_latex_scalar(v, precision) for v in row]
        rows.append(" & ".join(cells))

    return r"\begin{bmatrix} " + r" \\ ".join(rows) + r" \end{bmatrix}"


def format_latex_array(array: Any, precision: int = 6, max_items: int = 10) -> str:
    """Format 1D array as LaTeX."""
    import numpy as np

    if not isinstance(array, np.ndarray):
        array = np.array(array)

    flat = array.flatten()
    values = [format_latex_scalar(v, precision) for v in flat[:max_items]]
    if len(flat) > max_items:
        values.append(r"\ldots")

    return r"\left[ " + ", ".join(values) + r" \right]"


def format_latex_polynomial(coeffs: Any, variable: str = "x") -> str:
    """Format polynomial coefficients as LaTeX.

    Args:
        coeffs: Coefficients in descending order [a_n, a_{n-1}, ..., a_1, a_0]
        variable: Variable name

    Returns:
        LaTeX string like "x^2 + 2x + 1"
    """
    import numpy as np

    if not isinstance(coeffs, np.ndarray):
        coeffs = np.array(coeffs)

    degree = len(coeffs) - 1
    terms = []

    for i, c in enumerate(coeffs):
        power = degree - i
        if abs(c) < 1e-10:
            continue

        # Format coefficient
        if power == 0:
            term = format_latex_scalar(c, 4)
        elif power == 1:
            if abs(c - 1) < 1e-10:
                term = variable
            elif abs(c + 1) < 1e-10:
                term = f"-{variable}"
            else:
                term = f"{format_latex_scalar(c, 4)}{variable}"
        else:
            if abs(c - 1) < 1e-10:
                term = f"{variable}^{{{power}}}"
            elif abs(c + 1) < 1e-10:
                term = f"-{variable}^{{{power}}}"
            else:
                term = f"{format_latex_scalar(c, 4)}{variable}^{{{power}}}"

        terms.append(term)

    if not terms:
        return "0"

    # Join with + and handle signs
    result = terms[0]
    for term in terms[1:]:
        if term.startswith("-"):
            result += f" - {term[1:]}"
        else:
            result += f" + {term}"

    return result


# =============================================================================
# CLI Builder Utilities
# =============================================================================


def create_subparser(
    subparsers: argparse._SubParsersAction, command: MathCommand
) -> argparse.ArgumentParser:
    """Create subparser for a registered command.

    Args:
        subparsers: Subparser action from main parser
        command: MathCommand metadata

    Returns:
        Configured subparser
    """
    parser = subparsers.add_parser(
        command.name, help=command.description, description=command.description
    )

    for arg in command.args:
        arg_copy = arg.copy()
        name = arg_copy.pop("name")
        if name.startswith("--"):
            parser.add_argument(name, **arg_copy)
        else:
            parser.add_argument(name, **arg_copy)

    # Add common options
    parser.add_argument("--json", action="store_true", help="Output as JSON (default)")
    parser.add_argument(
        "--precision", type=int, default=15, help="Output precision (decimal places)"
    )

    return parser


def register_commands(
    parser: argparse.ArgumentParser, registry: dict[str, MathCommand] | None = None
) -> argparse._SubParsersAction:
    """Register all commands from registry with parser.

    Args:
        parser: Main argument parser
        registry: Command registry (uses global if None)

    Returns:
        Subparsers action for additional customization
    """
    if registry is None:
        registry = _command_registry

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Group by category
    categories: dict[str, list[MathCommand]] = {}
    for cmd in registry.values():
        categories.setdefault(cmd.category, []).append(cmd)

    # Create subparsers
    for cmd in registry.values():
        create_subparser(subparsers, cmd)

    return subparsers


def run_command(
    args: argparse.Namespace, registry: dict[str, MathCommand] | None = None
) -> Dict[str, Any]:
    """Run command based on parsed arguments.

    Args:
        args: Parsed command-line arguments
        registry: Command registry (uses global if None)

    Returns:
        Command result dictionary
    """
    if registry is None:
        registry = _command_registry

    if args.command not in registry:
        return format_error(f"Unknown command: {args.command}")

    command = registry[args.command]

    # Extract function arguments from namespace
    func_args = {}
    for arg in command.args:
        name = arg["name"].lstrip("-").replace("-", "_")
        if hasattr(args, name):
            func_args[name] = getattr(args, name)

    return command.func(**func_args)


# =============================================================================
# Error Handling Wrapper
# =============================================================================


def safe_compute(func: Callable, *args, timeout: int = 30, **kwargs) -> dict[str, Any]:
    """Execute computation with timeout and error handling.

    Args:
        func: Function to execute
        *args: Positional arguments
        timeout: Maximum seconds
        **kwargs: Keyword arguments

    Returns:
        Result dict or error dict
    """
    from concurrent.futures import ProcessPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    def _wrapper():
        return func(*args, **kwargs)

    try:
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_wrapper)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeout:
                return format_error(f"Timeout after {timeout}s", func.__name__)
    except Exception as e:
        return format_error(str(e), func.__name__)


# =============================================================================
# Main CLI Template
# =============================================================================


def create_main_parser(prog: str, description: str, epilog: str = "") -> argparse.ArgumentParser:
    """Create main argument parser with standard options.

    Args:
        prog: Program name
        description: Program description
        epilog: Additional help text (typically usage examples)

    Returns:
        Configured ArgumentParser
    """
    return argparse.ArgumentParser(
        prog=prog,
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def main_cli(
    parser: argparse.ArgumentParser, registry: dict[str, MathCommand] | None = None
) -> int:
    """Template main function for CLI scripts.

    Args:
        parser: Configured argument parser
        registry: Command registry (uses global if None)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    if registry is None:
        registry = _command_registry

    # Register commands
    register_commands(parser, registry)

    # Parse arguments
    args = parser.parse_args()

    # Run command
    result = run_command(args, registry)

    # Output
    if result.get("error"):
        output_error_json(result)
        return 1
    else:
        output_json(result)
        return 0


# =============================================================================
# Utility Functions
# =============================================================================


def ensure_2d(arr: Any) -> Any:
    """Ensure array is 2D (for matrix operations)."""
    import numpy as np

    arr = np.asarray(arr)
    if arr.ndim == 1:
        return arr.reshape(-1, 1)
    return arr


def ensure_1d(arr: Any) -> Any:
    """Ensure array is 1D (for vector operations)."""
    import numpy as np

    arr = np.asarray(arr)
    return arr.flatten()


def validate_square(matrix: Any, operation: str = "operation") -> None:
    """Validate that matrix is square."""
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"{operation} requires square matrix, got {matrix.shape}")


def validate_positive_definite(matrix: Any) -> bool:
    """Check if matrix is positive definite."""
    import numpy as np

    try:
        np.linalg.cholesky(matrix)
        return True
    except np.linalg.LinAlgError:
        return False


def get_array_info(arr: Any) -> dict[str, Any]:
    """Get metadata about an array."""
    import numpy as np

    arr = np.asarray(arr)
    return {
        "shape": arr.shape,
        "dtype": str(arr.dtype),
        "size": arr.size,
        "ndim": arr.ndim,
    }
