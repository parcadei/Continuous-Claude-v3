#!/usr/bin/env python3
"""Generate auto-routes for all missing commands.

USAGE:
    uv run python scripts/generate_auto_routes.py > auto_routes.py
    uv run python scripts/generate_auto_routes.py --insert  # Insert directly into math_router.py
"""

import argparse
import json
import re
import sys
from pathlib import Path


# Category mapping for each script
SCRIPT_CATEGORIES = {
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


# Human-readable descriptions for common command patterns
DESCRIPTIONS = {
    # NumPy matrix/linalg
    "det": "Matrix determinant",
    "inv": "Matrix inverse",
    "pinv": "Pseudo-inverse",
    "matrix_power": "Matrix power",
    "matrix_rank": "Matrix rank",
    "trace": "Matrix trace",
    "norm": "Vector/matrix norm",
    "cond": "Condition number",
    "eig": "Eigenvalues and eigenvectors",
    "eigh": "Eigenvalues for Hermitian",
    "eigvals": "Eigenvalues only",
    "eigvalsh": "Eigenvalues for Hermitian (only)",
    "svd": "Singular value decomposition",
    "qr": "QR decomposition",
    "cholesky": "Cholesky decomposition",
    "lstsq": "Least squares solution",
    "solve": "Solve linear system",
    # NumPy FFT
    "fft": "Fast Fourier transform",
    "ifft": "Inverse FFT",
    "rfft": "Real FFT",
    "irfft": "Inverse real FFT",
    "fft2": "2D FFT",
    "ifft2": "Inverse 2D FFT",
    "fftn": "N-dimensional FFT",
    "ifftn": "Inverse N-D FFT",
    "fftfreq": "FFT sample frequencies",
    "rfftfreq": "Real FFT frequencies",
    "fftshift": "Shift zero-frequency",
    "ifftshift": "Inverse shift",
    # NumPy stats
    "mean": "Arithmetic mean",
    "median": "Median value",
    "std": "Standard deviation",
    "var": "Variance",
    "sum": "Sum of elements",
    "prod": "Product of elements",
    "cumsum": "Cumulative sum",
    "cumprod": "Cumulative product",
    "percentile": "Percentile value",
    "quantile": "Quantile value",
    "histogram": "Histogram",
    "corrcoef": "Correlation coefficients",
    "cov": "Covariance matrix",
    # NumPy array ops
    "sort": "Sort array",
    "argsort": "Indices for sorted",
    "argmax": "Index of maximum",
    "argmin": "Index of minimum",
    "where": "Conditional selection",
    "nonzero": "Non-zero indices",
    "unique": "Unique elements",
    "diff": "Differences along axis",
    "gradient": "Gradient of array",
    # NumPy trig
    "sin": "Sine",
    "cos": "Cosine",
    "tan": "Tangent",
    "arcsin": "Arc sine",
    "arccos": "Arc cosine",
    "arctan": "Arc tangent",
    "sinh": "Hyperbolic sine",
    "cosh": "Hyperbolic cosine",
    "tanh": "Hyperbolic tangent",
    # NumPy math
    "exp": "Exponential",
    "log": "Natural log",
    "log10": "Base-10 log",
    "log2": "Base-2 log",
    "sqrt": "Square root",
    "power": "Element-wise power",
    "absolute": "Absolute value",
    "floor": "Floor",
    "ceil": "Ceiling",
    "round": "Round",
    # SciPy optimization
    "minimize": "Minimize function",
    "minimize_scalar": "Minimize scalar",
    "root": "Find roots",
    "fsolve": "Solve equations",
    "brentq": "Brent root finding",
    "curve_fit": "Curve fitting",
    "linprog": "Linear programming",
    "differential_evolution": "Differential evolution",
    "basinhopping": "Basin hopping",
    # SciPy integration
    "quad": "Numerical integration",
    "dblquad": "Double integration",
    "tplquad": "Triple integration",
    "odeint": "ODE integration",
    "solve_ivp": "Solve IVP",
    # SciPy stats
    "ttest_1samp": "One-sample t-test",
    "ttest_ind": "Independent t-test",
    "kstest": "KS test",
    "pearsonr": "Pearson correlation",
    "spearmanr": "Spearman correlation",
    "linregress": "Linear regression",
    "normaltest": "Normality test",
    "shapiro": "Shapiro-Wilk test",
    # SciPy distributions
    "norm": "Normal distribution",
    "t": "Student's t",
    "chi2": "Chi-squared",
    "f": "F distribution",
    "uniform": "Uniform",
    "expon": "Exponential",
    "gamma": "Gamma distribution",
    "beta": "Beta distribution",
    "poisson": "Poisson",
    "binom": "Binomial",
    # mpmath constants
    "pi": "Pi constant",
    "e": "Euler's number e",
    "euler": "Euler-Mascheroni gamma",
    "phi": "Golden ratio",
    "catalan": "Catalan constant",
    "apery": "Apery's constant",
    # mpmath functions
    "zeta": "Riemann zeta",
    "gamma": "Gamma function",
    "factorial": "Factorial",
    "loggamma": "Log gamma",
    "digamma": "Digamma function",
    "erf": "Error function",
    "erfc": "Complementary error",
    "polylog": "Polylogarithm",
    "hyp2f1": "Hypergeometric 2F1",
    "besselj": "Bessel J",
    "bessely": "Bessel Y",
    "besseli": "Modified Bessel I",
    "besselk": "Modified Bessel K",
    # Sympy
    "integrate": "Integration",
    "diff": "Differentiation",
    "limit": "Limit",
    "simplify": "Simplify expression",
    "factor": "Factor polynomial",
    "expand": "Expand expression",
    "eigenvalues": "Eigenvalues",
    "eigenvectors": "Eigenvectors",
    "rref": "Row echelon form",
    "nullspace": "Null space",
    "rank": "Matrix rank",
    "laplace": "Laplace transform",
    "dsolve": "Solve ODE",
    "series": "Series expansion",
    # Pint
    "convert": "Unit conversion",
    "check": "Dimension check",
    "parse": "Parse quantity",
    "calc": "Unit calculation",
    # Shapely
    "measure": "Geometry measure",
    "op": "Geometry operation",
    "pred": "Geometry predicate",
    "distance": "Distance",
    "create": "Create geometry",
    "validate": "Validate geometry",
    "transform": "Transform geometry",
    # Z3
    "prove": "Prove theorem",
    "sat": "Satisfiability check",
    "optimize": "Optimization",
    # Math tools
    "verify": "Verify step",
    "explain": "Explain step",
    "chain": "Chain of steps",
    "hint": "Progressive hint",
    "steps": "Step-by-step",
    "generate": "Generate problem",
    "plot2d": "2D plot",
    "plot3d": "3D surface",
    "latex": "LaTeX render",
    "plot2d-multi": "Multi-function plot",
}


# Pattern generators for command names
def generate_pattern(cmd_name: str, script: str) -> str:
    """Generate regex pattern for command name."""
    # Handle np_ prefix for numpy
    if cmd_name.startswith("np_"):
        base_name = cmd_name[3:]  # Remove np_ prefix
        return rf'\bnp_{base_name}\b|\bnumpy\s+{base_name}\b|\b{base_name}\b'

    # Handle mp_ prefix for mpmath
    if cmd_name.startswith("mp_"):
        base_name = cmd_name[3:]  # Remove mp_ prefix
        return rf'\bmp_{base_name}\b|\bmpmath\s+{base_name}\b|\bhigh\s+precision\s+{base_name}\b'

    # Handle sp_ prefix for scipy special
    if cmd_name.startswith("sp_"):
        base_name = cmd_name[3:]
        return rf'\bsp_{base_name}\b|\bscipy\s+{base_name}\b|\bspecial\s+{base_name}\b'

    # Handle scipy_ prefix
    if cmd_name.startswith("scipy_"):
        base_name = cmd_name[6:]
        return rf'\bscipy_{base_name}\b|\bscipy\s+{base_name}\b'

    # Handle sig_ prefix (scipy signal)
    if cmd_name.startswith("sig_"):
        base_name = cmd_name[4:]
        return rf'\bsig_{base_name}\b|\bsignal\s+{base_name}\b|\b{base_name}\b'

    # Default: match command name as word
    return rf'\b{cmd_name}\b'


def generate_description(cmd_name: str, script: str) -> str:
    """Generate human-readable description."""
    # Check exact match first
    if cmd_name in DESCRIPTIONS:
        return DESCRIPTIONS[cmd_name]

    # Check with prefix stripped
    for prefix in ["np_", "mp_", "sp_", "scipy_", "sig_"]:
        if cmd_name.startswith(prefix):
            base = cmd_name[len(prefix):]
            if base in DESCRIPTIONS:
                return DESCRIPTIONS[base]

    # Generate from name
    # Convert underscores to spaces and capitalize
    words = cmd_name.replace("_", " ").replace("-", " ").split()
    # Remove prefix indicators
    words = [w for w in words if w not in ["np", "mp", "sp", "scipy", "sig"]]
    return " ".join(w.capitalize() for w in words)


def generate_extractor_name(cmd_name: str, script: str) -> str:
    """Generate argument extractor function name."""
    category = SCRIPT_CATEGORIES.get(script, "generic")

    # Determine extractor based on command type
    if script == "numpy_compute.py":
        if cmd_name in ["det", "inv", "pinv", "trace", "eig", "eigh", "eigvals", "eigvalsh", "svd", "qr", "cholesky", "matrix_power", "matrix_rank"]:
            return "extract_np_matrix"
        elif cmd_name.startswith("np_") and any(x in cmd_name for x in ["sin", "cos", "tan", "exp", "log", "sqrt"]):
            return "extract_np_array"
        elif cmd_name in ["mean", "std", "var", "median", "sum", "prod", "cumsum", "cumprod", "percentile", "quantile"]:
            return "extract_np_stats"
        elif cmd_name.startswith("fft") or cmd_name.startswith("ifft") or cmd_name.startswith("rfft"):
            return "extract_np_array"
        else:
            return "extract_np_array"

    elif script == "scipy_compute.py":
        if any(x in cmd_name for x in ["minimize", "root", "fsolve", "brentq", "curve_fit"]):
            return "extract_scipy_optimize"
        elif any(x in cmd_name for x in ["quad", "dblquad", "odeint", "solve_ivp"]):
            return "extract_scipy_integrate"
        elif any(x in cmd_name for x in ["ttest", "kstest", "pearsonr", "spearmanr", "normaltest"]):
            return "extract_scipy_stats"
        elif any(x in cmd_name for x in ["norm", "t", "chi2", "f", "uniform", "expon", "gamma", "beta", "poisson", "binom"]):
            return "extract_scipy_dist"
        else:
            return "extract_scipy_generic"

    elif script == "mpmath_compute.py":
        if cmd_name in ["pi", "e", "euler", "phi", "catalan", "apery", "khinchin", "glaisher", "mertens", "twinprime", "degree"]:
            return "extract_mpmath_constant"
        elif any(x in cmd_name for x in ["zeta", "gamma", "factorial", "erf", "besselj", "polylog", "hyp"]):
            return "extract_mpmath_function"
        elif any(x in cmd_name for x in ["matrix", "det", "inv", "eig", "svd", "qr", "lu", "cholesky"]):
            return "extract_mpmath_matrix"
        else:
            return "extract_mpmath_function"

    elif script == "sympy_compute.py":
        if cmd_name in ["det", "eigenvalues", "eigenvectors", "inverse", "transpose", "nullspace", "rref", "rank"]:
            return "extract_matrix"
        elif cmd_name in ["integrate", "diff", "series"]:
            return "extract_expr_var"
        elif cmd_name == "limit":
            return "extract_limit"
        elif cmd_name == "solve":
            return "extract_equation_var"
        elif cmd_name == "factor":
            return "extract_factor"
        elif cmd_name == "expand":
            return "extract_expand"
        else:
            return "extract_expr_var"

    elif script == "pint_compute.py":
        if cmd_name == "convert":
            return "extract_unit_conversion"
        elif cmd_name == "check":
            return "extract_dimension_check"
        else:
            return "extract_pint_generic"

    elif script == "shapely_compute.py":
        if cmd_name in ["measure", "area", "length", "centroid"]:
            return "extract_geom_measure"
        elif cmd_name in ["op", "intersection", "union", "difference", "buffer"]:
            return "extract_geom_op"
        elif cmd_name in ["pred", "contains", "intersects", "within", "touches"]:
            return "extract_geom_pred"
        elif cmd_name == "distance":
            return "extract_distance"
        else:
            return "extract_shapely_generic"

    elif script == "z3_solve.py":
        if cmd_name == "prove":
            return "extract_theorem"
        elif cmd_name == "sat":
            return "extract_constraint"
        elif cmd_name == "optimize":
            return "extract_optimization"
        else:
            return "extract_z3_generic"

    elif script == "math_scratchpad.py":
        if cmd_name == "verify":
            return "extract_verification"
        elif cmd_name == "explain":
            return "extract_step"
        elif cmd_name == "chain":
            return "extract_chain"
        else:
            return "extract_scratchpad_generic"

    elif script == "math_tutor.py":
        if cmd_name == "hint":
            return "extract_hint_request"
        elif cmd_name == "steps":
            return "extract_steps_request"
        elif cmd_name == "generate":
            return "extract_problem_gen"
        else:
            return "extract_tutor_generic"

    elif script == "math_plot.py":
        if cmd_name == "plot2d":
            return "extract_plot_params"
        elif cmd_name == "plot3d":
            return "extract_plot3d_params"
        elif cmd_name == "latex":
            return "extract_latex"
        elif cmd_name == "plot2d-multi":
            return "extract_plot_multi"
        else:
            return "extract_plot_generic"

    return "extract_generic"


def load_comparison() -> dict:
    """Load the comparison JSON from audit."""
    project_root = Path(__file__).parent.parent
    comparison_path = project_root / "thoughts" / "shared" / "agents" / "math-wrapper-pipeline" / "07-command-audit-comparison.json"

    if not comparison_path.exists():
        print(f"Error: Run audit first: uv run python scripts/audit_math_commands.py --compare --json", file=sys.stderr)
        sys.exit(1)

    with open(comparison_path) as f:
        return json.load(f)


def generate_auto_routes_code(comparison: dict) -> str:
    """Generate the AUTO_ROUTES dict and Route generation code."""
    lines = []

    lines.append("# =============================================================================")
    lines.append("# Auto-Generated Routes for Full Coverage")
    lines.append("# =============================================================================")
    lines.append("")
    lines.append("# Auto-generated patterns for missing commands")
    lines.append("# These supplement the hand-crafted routes above")
    lines.append("")
    lines.append("AUTO_ROUTES: dict[str, dict[str, list[str]]] = {")

    for script_name, data in comparison["scripts"].items():
        missing = data.get("missing_routes", [])
        if not missing:
            continue

        lines.append(f'    "{script_name}": {{')
        for cmd in sorted(missing):
            pattern = generate_pattern(cmd, script_name)
            # Escape backslashes for the string
            pattern_escaped = pattern.replace("\\", "\\\\")
            lines.append(f'        "{cmd}": r"{pattern_escaped}",')
        lines.append("    },")

    lines.append("}")
    lines.append("")
    lines.append("")
    lines.append("def generate_auto_route_objects() -> list[Route]:")
    lines.append('    """Generate Route objects from AUTO_ROUTES."""')
    lines.append("    routes = []")
    lines.append("    for script, commands in AUTO_ROUTES.items():")
    lines.append("        category = SCRIPT_CATEGORIES.get(script, 'generic')")
    lines.append("        for cmd, pattern in commands.items():")
    lines.append("            routes.append(Route(")
    lines.append("                pattern=pattern,")
    lines.append("                script=script,")
    lines.append("                subcommand=cmd,")
    lines.append("                arg_extractor=get_extractor_for_command(cmd, script),")
    lines.append("                description=generate_description(cmd, script),")
    lines.append("                category=category,")
    lines.append("                priority=1  # Lower priority than hand-crafted routes")
    lines.append("            ))")
    lines.append("    return routes")
    lines.append("")
    lines.append("")
    lines.append("# Script to category mapping")
    lines.append("SCRIPT_CATEGORIES: dict[str, str] = {")
    for script, category in SCRIPT_CATEGORIES.items():
        lines.append(f'    "{script}": "{category}",')
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def generate_extractors_code(comparison: dict) -> str:
    """Generate generic extractors for scripts that need them."""
    lines = []

    lines.append("# =============================================================================")
    lines.append("# Generic Extractors for Auto-Routes")
    lines.append("# =============================================================================")
    lines.append("")

    # NumPy generic
    lines.append("def extract_np_stats(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract array and axis for stats operations."""')
    lines.append("    array_match = re.search(r'\\[([\\d\\.,\\s\\-]+)\\]', intent)")
    lines.append('    array = f"[{array_match.group(1)}]" if array_match else "[1,2,3,4,5]"')
    lines.append("    axis_match = re.search(r'axis\\s*(\\d+)', intent, flags=re.IGNORECASE)")
    lines.append('    axis = int(axis_match.group(1)) if axis_match else None')
    lines.append('    return {"data": array, "axis": axis}')
    lines.append("")

    # SciPy generic
    lines.append("def extract_scipy_optimize(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract function and starting point for optimization."""')
    lines.append("    func_match = re.search(r'(?:minimize|maximize|root|solve)\\s+(.+?)(?:\\s+from|\\s+starting|$)', intent, flags=re.IGNORECASE)")
    lines.append('    func = func_match.group(1).strip() if func_match else "x**2"')
    lines.append("    x0_match = re.search(r'(?:from|starting|at)\\s*([\\d\\.\\-]+)', intent, flags=re.IGNORECASE)")
    lines.append('    x0 = x0_match.group(1) if x0_match else "0"')
    lines.append('    return {"func": func.replace("^", "**"), "x0": x0}')
    lines.append("")

    lines.append("def extract_scipy_integrate(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract function and bounds for scipy integration."""')
    lines.append("    func_match = re.search(r'(?:integrate|quad)\\s+(.+?)(?:\\s+from|\\s+over|$)', intent, flags=re.IGNORECASE)")
    lines.append('    func = func_match.group(1).strip() if func_match else "x**2"')
    lines.append("    bounds_match = re.search(r'from\\s*([\\d\\.\\-]+)\\s*to\\s*([\\d\\.\\-]+)', intent, flags=re.IGNORECASE)")
    lines.append('    a = bounds_match.group(1) if bounds_match else "0"')
    lines.append('    b = bounds_match.group(2) if bounds_match else "1"')
    lines.append('    return {"func": func.replace("^", "**"), "a": a, "b": b}')
    lines.append("")

    lines.append("def extract_scipy_stats(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract data for scipy stats tests."""')
    lines.append("    array_match = re.search(r'\\[([\\d\\.,\\s\\-]+)\\]', intent)")
    lines.append('    data = f"[{array_match.group(1)}]" if array_match else "[1,2,3,4,5]"')
    lines.append('    return {"data": data}')
    lines.append("")

    lines.append("def extract_scipy_dist(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract parameters for scipy distributions."""')
    lines.append("    x_match = re.search(r'(?:at|x\\s*=?)\\s*([\\d\\.\\-]+)', intent, flags=re.IGNORECASE)")
    lines.append('    x = x_match.group(1) if x_match else "0"')
    lines.append("    op_match = re.search(r'\\b(pdf|cdf|ppf|sf|isf|rvs)\\b', intent, flags=re.IGNORECASE)")
    lines.append('    op = op_match.group(1).lower() if op_match else "pdf"')
    lines.append('    return {"op": op, "x": x}')
    lines.append("")

    lines.append("def extract_scipy_generic(intent: str) -> dict[str, Any]:")
    lines.append('    """Generic extractor for scipy."""')
    lines.append("    array_match = re.search(r'\\[([\\d\\.,\\s\\-]+)\\]', intent)")
    lines.append('    data = f"[{array_match.group(1)}]" if array_match else "[1,2,3]"')
    lines.append('    return {"data": data}')
    lines.append("")

    # mpmath generic
    lines.append("def extract_mpmath_constant(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract precision for mpmath constants."""')
    lines.append("    dps_match = re.search(r'(?:dps|precision|digits)\\s*(\\d+)', intent, flags=re.IGNORECASE)")
    lines.append('    dps = int(dps_match.group(1)) if dps_match else 50')
    lines.append('    return {"dps": dps}')
    lines.append("")

    lines.append("def extract_mpmath_function(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract argument and precision for mpmath functions."""')
    lines.append("    x_match = re.search(r'\\(([\\d\\.\\-]+)\\)', intent)")
    lines.append('    if not x_match:')
    lines.append("        x_match = re.search(r'(?:of|at)\\s*([\\d\\.\\-]+)', intent, flags=re.IGNORECASE)")
    lines.append('    x = x_match.group(1) if x_match else "1"')
    lines.append("    dps_match = re.search(r'(?:dps|precision|digits)\\s*(\\d+)', intent, flags=re.IGNORECASE)")
    lines.append('    dps = int(dps_match.group(1)) if dps_match else 50')
    lines.append('    return {"x": x, "dps": dps}')
    lines.append("")

    lines.append("def extract_mpmath_matrix(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract matrix for mpmath operations."""')
    lines.append("    matrix_match = re.search(r'\\[\\[.+?\\]\\]', intent)")
    lines.append('    matrix = matrix_match.group(0) if matrix_match else "[[1,0],[0,1]]"')
    lines.append("    dps_match = re.search(r'(?:dps|precision|digits)\\s*(\\d+)', intent, flags=re.IGNORECASE)")
    lines.append('    dps = int(dps_match.group(1)) if dps_match else 50')
    lines.append('    return {"matrix": matrix, "dps": dps}')
    lines.append("")

    # Pint generic
    lines.append("def extract_pint_generic(intent: str) -> dict[str, Any]:")
    lines.append('    """Generic extractor for pint."""')
    lines.append("    qty_match = re.search(r'([\\d\\.]+\\s*\\w+)', intent)")
    lines.append('    quantity = qty_match.group(1) if qty_match else "1 meter"')
    lines.append('    return {"quantity": quantity}')
    lines.append("")

    # Shapely generic
    lines.append("def extract_shapely_generic(intent: str) -> dict[str, Any]:")
    lines.append('    """Generic extractor for shapely."""')
    lines.append("    wkt_match = re.search(r'(POLYGON|POINT|LINESTRING)\\s*\\([^)]+\\)', intent, flags=re.IGNORECASE)")
    lines.append('    geom = wkt_match.group(0) if wkt_match else "POINT(0 0)"')
    lines.append('    return {"geom": geom}')
    lines.append("")

    # Z3 generic
    lines.append("def extract_z3_generic(intent: str) -> dict[str, Any]:")
    lines.append('    """Generic extractor for z3."""')
    lines.append('    return {"constraints": intent}')
    lines.append("")

    # Scratchpad generic
    lines.append("def extract_chain(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract chain of reasoning steps."""')
    lines.append("    steps = re.sub(r'^chain\\s*', '', intent, flags=re.IGNORECASE)")
    lines.append('    return {"chain": steps.strip()}')
    lines.append("")

    lines.append("def extract_scratchpad_generic(intent: str) -> dict[str, Any]:")
    lines.append('    """Generic extractor for math scratchpad."""')
    lines.append('    return {"step": intent}')
    lines.append("")

    # Tutor generic
    lines.append("def extract_tutor_generic(intent: str) -> dict[str, Any]:")
    lines.append('    """Generic extractor for math tutor."""')
    lines.append('    return {"problem": intent}')
    lines.append("")

    # Plot generic
    lines.append("def extract_plot_multi(intent: str) -> dict[str, Any]:")
    lines.append('    """Extract multiple expressions for multi-plot."""')
    lines.append("    expr_match = re.search(r'(?:plot|graph)\\s+(.+?)(?:\\s+from|\\s+over|$)', intent, flags=re.IGNORECASE)")
    lines.append('    expressions = expr_match.group(1).strip() if expr_match else "sin(x),cos(x)"')
    lines.append("    range_match = re.search(r'from\\s*([\\d\\.\\-]+)\\s*to\\s*([\\d\\.\\-]+)', intent, flags=re.IGNORECASE)")
    lines.append('    x_min = float(range_match.group(1)) if range_match else -10')
    lines.append('    x_max = float(range_match.group(2)) if range_match else 10')
    lines.append('    return {"expressions": expressions, "var": "x", "range": [x_min, x_max], "output": "/tmp/multi_plot.png"}')
    lines.append("")

    lines.append("def extract_plot_generic(intent: str) -> dict[str, Any]:")
    lines.append('    """Generic extractor for plotting."""')
    lines.append("    expr_match = re.search(r'(?:plot|graph)\\s+(.+?)(?:\\s+from|\\s+over|$)', intent, flags=re.IGNORECASE)")
    lines.append('    expression = expr_match.group(1).strip() if expr_match else "x**2"')
    lines.append('    return {"expression": expression, "output": "/tmp/plot.png"}')
    lines.append("")

    lines.append("def extract_generic(intent: str) -> dict[str, Any]:")
    lines.append('    """Fallback generic extractor."""')
    lines.append('    return {"input": intent}')
    lines.append("")

    # Extractor lookup function
    lines.append("")
    lines.append("def get_extractor_for_command(cmd: str, script: str) -> Callable[[str], dict[str, Any]]:")
    lines.append('    """Get the appropriate extractor for a command."""')
    lines.append("    extractor_map = {")
    lines.append('        "extract_np_matrix": extract_np_matrix,')
    lines.append('        "extract_np_array": extract_np_array,')
    lines.append('        "extract_np_stats": extract_np_stats,')
    lines.append('        "extract_scipy_optimize": extract_scipy_optimize,')
    lines.append('        "extract_scipy_integrate": extract_scipy_integrate,')
    lines.append('        "extract_scipy_stats": extract_scipy_stats,')
    lines.append('        "extract_scipy_dist": extract_scipy_dist,')
    lines.append('        "extract_scipy_generic": extract_scipy_generic,')
    lines.append('        "extract_mpmath_constant": extract_mpmath_constant,')
    lines.append('        "extract_mpmath_function": extract_mpmath_function,')
    lines.append('        "extract_mpmath_matrix": extract_mpmath_matrix,')
    lines.append('        "extract_matrix": extract_matrix,')
    lines.append('        "extract_expr_var": extract_expr_var,')
    lines.append('        "extract_limit": extract_limit,')
    lines.append('        "extract_equation_var": extract_equation_var,')
    lines.append('        "extract_factor": extract_factor,')
    lines.append('        "extract_expand": extract_expand,')
    lines.append('        "extract_unit_conversion": extract_unit_conversion,')
    lines.append('        "extract_dimension_check": extract_dimension_check,')
    lines.append('        "extract_pint_generic": extract_pint_generic,')
    lines.append('        "extract_geom_measure": extract_geom_measure,')
    lines.append('        "extract_geom_op": extract_geom_op,')
    lines.append('        "extract_geom_pred": extract_geom_pred,')
    lines.append('        "extract_distance": extract_distance,')
    lines.append('        "extract_shapely_generic": extract_shapely_generic,')
    lines.append('        "extract_theorem": extract_theorem,')
    lines.append('        "extract_constraint": extract_constraint,')
    lines.append('        "extract_optimization": extract_optimization,')
    lines.append('        "extract_z3_generic": extract_z3_generic,')
    lines.append('        "extract_verification": extract_verification,')
    lines.append('        "extract_step": extract_step,')
    lines.append('        "extract_chain": extract_chain,')
    lines.append('        "extract_scratchpad_generic": extract_scratchpad_generic,')
    lines.append('        "extract_hint_request": extract_hint_request,')
    lines.append('        "extract_steps_request": extract_steps_request,')
    lines.append('        "extract_problem_gen": extract_problem_gen,')
    lines.append('        "extract_tutor_generic": extract_tutor_generic,')
    lines.append('        "extract_plot_params": extract_plot_params,')
    lines.append('        "extract_plot3d_params": extract_plot3d_params,')
    lines.append('        "extract_latex": extract_latex,')
    lines.append('        "extract_plot_multi": extract_plot_multi,')
    lines.append('        "extract_plot_generic": extract_plot_generic,')
    lines.append('        "extract_generic": extract_generic,')
    lines.append("    }")
    lines.append("    ")
    lines.append("    # Get extractor name based on command and script")
    lines.append("    extractor_name = _get_extractor_name(cmd, script)")
    lines.append("    return extractor_map.get(extractor_name, extract_generic)")
    lines.append("")
    lines.append("")
    lines.append("def _get_extractor_name(cmd: str, script: str) -> str:")
    lines.append('    """Map command and script to extractor name."""')

    # Add the extractor name logic
    for script, category in SCRIPT_CATEGORIES.items():
        lines.append(f'    if script == "{script}":')
        if script == "numpy_compute.py":
            lines.append('        if cmd in ["det", "inv", "pinv", "trace", "eig", "eigh", "eigvals", "eigvalsh", "svd", "qr", "cholesky", "matrix_power", "matrix_rank"]:')
            lines.append('            return "extract_np_matrix"')
            lines.append('        elif cmd in ["mean", "std", "var", "median", "sum", "prod", "cumsum", "cumprod", "percentile", "quantile", "histogram", "corrcoef", "cov"]:')
            lines.append('            return "extract_np_stats"')
            lines.append('        return "extract_np_array"')
        elif script == "scipy_compute.py":
            lines.append('        if any(x in cmd for x in ["minimize", "root", "fsolve", "brentq", "curve_fit", "linprog"]):')
            lines.append('            return "extract_scipy_optimize"')
            lines.append('        elif any(x in cmd for x in ["quad", "dblquad", "tplquad", "odeint", "solve_ivp"]):')
            lines.append('            return "extract_scipy_integrate"')
            lines.append('        elif any(x in cmd for x in ["ttest", "kstest", "pearsonr", "spearmanr", "normaltest", "shapiro", "chisquare"]):')
            lines.append('            return "extract_scipy_stats"')
            lines.append('        elif cmd in ["norm", "t", "chi2", "f", "uniform", "expon", "gamma", "beta", "poisson", "binom", "lognorm", "weibull_min", "cauchy", "laplace"]:')
            lines.append('            return "extract_scipy_dist"')
            lines.append('        return "extract_scipy_generic"')
        elif script == "mpmath_compute.py":
            lines.append('        if cmd in ["pi", "e", "euler", "phi", "catalan", "apery", "khinchin", "glaisher", "mertens", "twinprime", "degree", "inf", "nan", "j"]:')
            lines.append('            return "extract_mpmath_constant"')
            lines.append('        elif any(x in cmd for x in ["matrix", "det", "inv", "eig", "svd", "qr", "lu", "cholesky", "eye", "zeros", "ones", "diag"]):')
            lines.append('            return "extract_mpmath_matrix"')
            lines.append('        return "extract_mpmath_function"')
        elif script == "sympy_compute.py":
            lines.append('        if cmd in ["det", "eigenvalues", "eigenvectors", "inverse", "transpose", "nullspace", "rref", "rank", "linsolve", "charpoly"]:')
            lines.append('            return "extract_matrix"')
            lines.append('        elif cmd == "limit":')
            lines.append('            return "extract_limit"')
            lines.append('        elif cmd == "solve":')
            lines.append('            return "extract_equation_var"')
            lines.append('        elif cmd == "factor":')
            lines.append('            return "extract_factor"')
            lines.append('        elif cmd == "expand":')
            lines.append('            return "extract_expand"')
            lines.append('        return "extract_expr_var"')
        elif script == "pint_compute.py":
            lines.append('        if cmd == "convert":')
            lines.append('            return "extract_unit_conversion"')
            lines.append('        elif cmd == "check":')
            lines.append('            return "extract_dimension_check"')
            lines.append('        return "extract_pint_generic"')
        elif script == "shapely_compute.py":
            lines.append('        if cmd in ["measure"]:')
            lines.append('            return "extract_geom_measure"')
            lines.append('        elif cmd in ["op"]:')
            lines.append('            return "extract_geom_op"')
            lines.append('        elif cmd in ["pred"]:')
            lines.append('            return "extract_geom_pred"')
            lines.append('        elif cmd == "distance":')
            lines.append('            return "extract_distance"')
            lines.append('        return "extract_shapely_generic"')
        elif script == "z3_solve.py":
            lines.append('        if cmd == "prove":')
            lines.append('            return "extract_theorem"')
            lines.append('        elif cmd == "sat":')
            lines.append('            return "extract_constraint"')
            lines.append('        elif cmd == "optimize":')
            lines.append('            return "extract_optimization"')
            lines.append('        return "extract_z3_generic"')
        elif script == "math_scratchpad.py":
            lines.append('        if cmd == "verify":')
            lines.append('            return "extract_verification"')
            lines.append('        elif cmd == "explain":')
            lines.append('            return "extract_step"')
            lines.append('        elif cmd == "chain":')
            lines.append('            return "extract_chain"')
            lines.append('        return "extract_scratchpad_generic"')
        elif script == "math_tutor.py":
            lines.append('        if cmd == "hint":')
            lines.append('            return "extract_hint_request"')
            lines.append('        elif cmd == "steps":')
            lines.append('            return "extract_steps_request"')
            lines.append('        elif cmd == "generate":')
            lines.append('            return "extract_problem_gen"')
            lines.append('        return "extract_tutor_generic"')
        elif script == "math_plot.py":
            lines.append('        if cmd == "plot2d":')
            lines.append('            return "extract_plot_params"')
            lines.append('        elif cmd == "plot3d":')
            lines.append('            return "extract_plot3d_params"')
            lines.append('        elif cmd == "latex":')
            lines.append('            return "extract_latex"')
            lines.append('        elif cmd == "plot2d-multi":')
            lines.append('            return "extract_plot_multi"')
            lines.append('        return "extract_plot_generic"')
        else:
            lines.append('        return "extract_generic"')

    lines.append('    return "extract_generic"')
    lines.append("")

    # Description generator
    lines.append("")
    lines.append("def generate_description(cmd: str, script: str) -> str:")
    lines.append('    """Generate human-readable description for a command."""')
    lines.append("    DESCRIPTIONS = " + json.dumps(DESCRIPTIONS, indent=8))
    lines.append("    ")
    lines.append("    if cmd in DESCRIPTIONS:")
    lines.append("        return DESCRIPTIONS[cmd]")
    lines.append('    for prefix in ["np_", "mp_", "sp_", "scipy_", "sig_"]:')
    lines.append("        if cmd.startswith(prefix):")
    lines.append("            base = cmd[len(prefix):]")
    lines.append("            if base in DESCRIPTIONS:")
    lines.append("                return DESCRIPTIONS[base]")
    lines.append('    words = cmd.replace("_", " ").replace("-", " ").split()')
    lines.append('    words = [w for w in words if w not in ["np", "mp", "sp", "scipy", "sig"]]')
    lines.append('    return " ".join(w.capitalize() for w in words)')
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate auto-routes for missing commands")
    parser.add_argument("--insert", action="store_true", help="Insert directly into math_router.py")
    args = parser.parse_args()

    comparison = load_comparison()

    auto_routes = generate_auto_routes_code(comparison)
    extractors = generate_extractors_code(comparison)

    if args.insert:
        # Would need to insert into math_router.py
        print("Insertion mode not yet implemented. Use output redirection instead.", file=sys.stderr)
        print(extractors)
        print()
        print(auto_routes)
    else:
        print(extractors)
        print()
        print(auto_routes)


if __name__ == "__main__":
    main()
