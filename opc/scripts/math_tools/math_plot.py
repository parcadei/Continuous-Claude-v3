#!/usr/bin/env python3
"""Math visualization script - plots, 3D surfaces, LaTeX rendering.

USAGE:
    # 2D plot
    uv run python scripts/math_plot.py plot2d "sin(x)" \\
        --var x --range -10 10 --output plot.png

    # 3D surface
    uv run python scripts/math_plot.py plot3d "x**2 + y**2" \\
        --xvar x --yvar y --range 5 --output surface.html

    # LaTeX to PNG
    uv run python scripts/math_plot.py latex "\\int e^{-x^2} dx" --output equation.png

    # Multiple 2D functions
    uv run python scripts/math_plot.py plot2d-multi "sin(x),cos(x)" \\
        --var x --range -6.28 6.28 --output multi.png

Requires: matplotlib, plotly, sympy, numpy
"""

import argparse
import json
import sys


def get_numpy():
    """Lazy import numpy."""
    import numpy as np

    return np


def get_matplotlib():
    """Lazy import matplotlib."""
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend for file output
    import matplotlib.pyplot as plt

    return plt


def get_plotly():
    """Lazy import plotly."""
    import plotly.graph_objects as go

    return go


def get_sympy():
    """Lazy import SymPy for expression parsing."""
    import sympy

    return sympy


def validate_expression(expr_str: str) -> tuple[bool, str]:
    """Validate expression before parsing.

    Returns:
        (valid, message)
    """
    # Check for dangerous patterns
    dangerous = ["import", "exec", "eval", "__", "open", "file", "os.", "subprocess"]
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


def safe_parse(expr_str: str, local_dict: dict = None):
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
            "t": sympy.Symbol("t"),
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


def plot_2d(
    expr_str: str,
    var: str,
    x_min: float,
    x_max: float,
    output_path: str,
    num_points: int = 400,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    dpi: int = 150,
) -> dict:
    """Plot a 2D function using matplotlib.

    Args:
        expr_str: Expression to plot (e.g., "sin(x)")
        var: Variable name (e.g., "x")
        x_min: Minimum x value
        x_max: Maximum x value
        output_path: Path to save the plot
        num_points: Number of points to sample
        title: Optional plot title
        xlabel: Optional x-axis label
        ylabel: Optional y-axis label
        dpi: Image DPI

    Returns:
        {
            "success": True/False,
            "output_path": "...",
            "error": "..." (if failed)
        }
    """
    try:
        np = get_numpy()
        plt = get_matplotlib()
        sympy = get_sympy()

        # Parse expression
        sym_var = sympy.Symbol(var)
        local_dict = {var: sym_var}
        expr = safe_parse(expr_str, local_dict)

        # Create numpy function from sympy expression
        f = sympy.lambdify(sym_var, expr, modules=["numpy"])

        # Generate x values
        x = np.linspace(float(x_min), float(x_max), int(num_points))

        # Evaluate function
        with np.errstate(divide="ignore", invalid="ignore"):
            y = f(x)
            # Replace inf/nan with nan for cleaner plotting
            y = np.where(np.isfinite(y), y, np.nan)

        # Create plot
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x, y, "b-", linewidth=2, label=f"${sympy.latex(expr)}$")

        # Set labels
        ax.set_xlabel(xlabel or var)
        ax.set_ylabel(ylabel or "y")
        ax.set_title(title or f"Plot of {expr_str}")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Save figure
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return {
            "success": True,
            "output_path": output_path,
            "expression": expr_str,
            "latex": sympy.latex(expr),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "expression": expr_str}


def plot_2d_multi(
    expressions: list[str],
    var: str,
    x_min: float,
    x_max: float,
    output_path: str,
    labels: list[str] | None = None,
    num_points: int = 400,
    title: str | None = None,
    dpi: int = 150,
) -> dict:
    """Plot multiple 2D functions on the same plot.

    Args:
        expressions: List of expressions to plot
        var: Variable name
        x_min: Minimum x value
        x_max: Maximum x value
        output_path: Path to save the plot
        labels: Optional list of labels for each expression
        num_points: Number of points to sample
        title: Optional plot title
        dpi: Image DPI

    Returns:
        {
            "success": True/False,
            "output_path": "...",
            "error": "..." (if failed)
        }
    """
    try:
        np = get_numpy()
        plt = get_matplotlib()
        sympy = get_sympy()

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Generate x values
        x = np.linspace(float(x_min), float(x_max), int(num_points))

        # Parse and plot each expression
        sym_var = sympy.Symbol(var)
        local_dict = {var: sym_var}
        colors = plt.cm.tab10.colors

        for i, expr_str in enumerate(expressions):
            expr = safe_parse(expr_str, local_dict)
            f = sympy.lambdify(sym_var, expr, modules=["numpy"])

            with np.errstate(divide="ignore", invalid="ignore"):
                y = f(x)
                y = np.where(np.isfinite(y), y, np.nan)

            label = labels[i] if labels and i < len(labels) else f"${sympy.latex(expr)}$"
            color = colors[i % len(colors)]
            ax.plot(x, y, color=color, linewidth=2, label=label)

        # Set labels
        ax.set_xlabel(var)
        ax.set_ylabel("y")
        ax.set_title(title or "Multiple Functions")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Save figure
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return {
            "success": True,
            "output_path": output_path,
            "expressions": expressions,
            "count": len(expressions),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "expressions": expressions}


def plot_3d(
    expr_str: str,
    xvar: str,
    yvar: str,
    range_val: float,
    output_path: str,
    resolution: int = 50,
    colorscale: str = "Viridis",
    title: str | None = None,
) -> dict:
    """Plot a 3D surface using plotly.

    Args:
        expr_str: Expression to plot (e.g., "x**2 + y**2")
        xvar: X variable name
        yvar: Y variable name
        range_val: Range for both x and y (symmetric: -range_val to +range_val)
        output_path: Path to save the plot (HTML)
        resolution: Grid resolution (number of points per axis)
        colorscale: Plotly colorscale name
        title: Optional plot title

    Returns:
        {
            "success": True/False,
            "output_path": "...",
            "error": "..." (if failed)
        }
    """
    try:
        np = get_numpy()
        go = get_plotly()
        sympy = get_sympy()

        # Parse expression
        sym_x = sympy.Symbol(xvar)
        sym_y = sympy.Symbol(yvar)
        local_dict = {xvar: sym_x, yvar: sym_y}
        expr = safe_parse(expr_str, local_dict)

        # Create numpy function from sympy expression
        f = sympy.lambdify((sym_x, sym_y), expr, modules=["numpy"])

        # Create mesh grid
        x_arr = np.linspace(-float(range_val), float(range_val), int(resolution))
        y_arr = np.linspace(-float(range_val), float(range_val), int(resolution))
        x_grid, y_grid = np.meshgrid(x_arr, y_arr)

        # Evaluate function
        with np.errstate(divide="ignore", invalid="ignore"):
            z_vals = f(x_grid, y_grid)
            # Replace inf/nan with nan
            z_vals = np.where(np.isfinite(z_vals), z_vals, np.nan)

        # Create surface plot
        fig = go.Figure(data=[go.Surface(z=z_vals, x=x_arr, y=y_arr, colorscale=colorscale)])

        fig.update_layout(
            title=title or f"3D Surface: {expr_str}",
            scene=dict(xaxis_title=xvar, yaxis_title=yvar, zaxis_title="z"),
        )

        # Save as HTML (interactive)
        fig.write_html(output_path)

        return {
            "success": True,
            "output_path": output_path,
            "expression": expr_str,
            "latex": sympy.latex(expr),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "expression": expr_str}


def render_latex(latex_str: str, output_path: str, dpi: int = 200, fontsize: int = 24) -> dict:
    """Render a LaTeX equation to PNG using matplotlib.

    Args:
        latex_str: LaTeX equation string (without $ delimiters)
        output_path: Path to save the image
        dpi: Image DPI
        fontsize: Font size for the equation

    Returns:
        {
            "success": True/False,
            "output_path": "...",
            "error": "..." (if failed)
        }
    """
    try:
        plt = get_matplotlib()

        # Create figure
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.axis("off")

        # Ensure LaTeX string is wrapped in $ for matplotlib
        if not latex_str.startswith("$"):
            latex_display = f"${latex_str}$"
        else:
            latex_display = latex_str

        # Render LaTeX equation
        ax.text(
            0.5,
            0.5,
            latex_display,
            fontsize=fontsize,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

        # Save figure
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white", edgecolor="none")
        plt.close(fig)

        return {"success": True, "output_path": output_path, "latex": latex_str}

    except Exception as e:
        return {"success": False, "error": str(e), "latex": latex_str}


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Math visualization - 2D plots, 3D surfaces, LaTeX rendering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # plot2d command
    plot2d_p = subparsers.add_parser("plot2d", help="Plot a 2D function")
    plot2d_p.add_argument("expression", help="Expression to plot (e.g., 'sin(x)')")
    plot2d_p.add_argument("--var", default="x", help="Variable name")
    plot2d_p.add_argument(
        "--range", nargs=2, type=float, required=True, metavar=("MIN", "MAX"), help="X range"
    )
    plot2d_p.add_argument("--output", required=True, help="Output file path")
    plot2d_p.add_argument("--points", type=int, default=400, help="Number of sample points")
    plot2d_p.add_argument("--title", help="Plot title")
    plot2d_p.add_argument("--dpi", type=int, default=150, help="Image DPI")

    # plot2d-multi command
    multi_p = subparsers.add_parser("plot2d-multi", help="Plot multiple 2D functions")
    multi_p.add_argument("expressions", help="Comma-separated expressions")
    multi_p.add_argument("--var", default="x", help="Variable name")
    multi_p.add_argument(
        "--range", nargs=2, type=float, required=True, metavar=("MIN", "MAX"), help="X range"
    )
    multi_p.add_argument("--output", required=True, help="Output file path")
    multi_p.add_argument("--labels", help="Comma-separated labels")
    multi_p.add_argument("--points", type=int, default=400, help="Number of sample points")
    multi_p.add_argument("--title", help="Plot title")
    multi_p.add_argument("--dpi", type=int, default=150, help="Image DPI")

    # plot3d command
    plot3d_p = subparsers.add_parser("plot3d", help="Plot a 3D surface")
    plot3d_p.add_argument("expression", help="Expression to plot (e.g., 'x**2 + y**2')")
    plot3d_p.add_argument("--xvar", default="x", help="X variable name")
    plot3d_p.add_argument("--yvar", default="y", help="Y variable name")
    plot3d_p.add_argument("--range", type=float, required=True, help="Range (symmetric)")
    plot3d_p.add_argument("--output", required=True, help="Output file path (HTML)")
    plot3d_p.add_argument("--resolution", type=int, default=50, help="Grid resolution")
    plot3d_p.add_argument("--colorscale", default="Viridis", help="Plotly colorscale")
    plot3d_p.add_argument("--title", help="Plot title")

    # latex command
    latex_p = subparsers.add_parser("latex", help="Render LaTeX equation to PNG")
    latex_p.add_argument("equation", help="LaTeX equation string")
    latex_p.add_argument("--output", required=True, help="Output file path")
    latex_p.add_argument("--dpi", type=int, default=200, help="Image DPI")
    latex_p.add_argument("--fontsize", type=int, default=24, help="Font size")

    # Common options
    for p in [plot2d_p, multi_p, plot3d_p, latex_p]:
        p.add_argument("--json", action="store_true", help="Output as JSON")

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


def main():
    args = parse_args()

    try:
        if args.command == "plot2d":
            result = plot_2d(
                args.expression,
                args.var,
                args.range[0],
                args.range[1],
                args.output,
                num_points=args.points,
                title=args.title,
                dpi=args.dpi,
            )
        elif args.command == "plot2d-multi":
            expressions = [e.strip() for e in args.expressions.split(",")]
            labels = [lbl.strip() for lbl in args.labels.split(",")] if args.labels else None
            result = plot_2d_multi(
                expressions,
                args.var,
                args.range[0],
                args.range[1],
                args.output,
                labels=labels,
                num_points=args.points,
                title=args.title,
                dpi=args.dpi,
            )
        elif args.command == "plot3d":
            result = plot_3d(
                args.expression,
                args.xvar,
                args.yvar,
                args.range,
                args.output,
                resolution=args.resolution,
                colorscale=args.colorscale,
                title=args.title,
            )
        elif args.command == "latex":
            result = render_latex(args.equation, args.output, dpi=args.dpi, fontsize=args.fontsize)
        else:
            result = {"success": False, "error": f"Unknown command: {args.command}"}

        # Output
        print(json.dumps(result, indent=2))

        # Exit code based on success
        sys.exit(0 if result.get("success") else 1)

    except Exception as e:
        error_result = {"success": False, "error": str(e), "command": args.command}
        print(json.dumps(error_result), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
