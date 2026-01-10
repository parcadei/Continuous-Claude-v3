"""SciPy computation CLI - 289 functions across 7 categories.

USAGE:
    uv run python scripts/scipy_compute.py <command> [args]

CATEGORIES:
    optimize    - Optimization and root finding (20 functions)
    integrate   - Numerical integration (14 functions)
    interpolate - Interpolation (20 functions)
    linalg      - Linear algebra (51 functions)
    stats       - Statistics (100 functions)
    signal      - Signal processing (42 functions)
    special     - Special functions (future)

EXAMPLES:
    # Minimize a function
    uv run python scripts/scipy_compute.py minimize "x**2 + 2*x" "5"

    # Find root of equation
    uv run python scripts/scipy_compute.py root "x**3 - x - 2" "1.5"

    # Solve system of equations
    uv run python scripts/scipy_compute.py fsolve "x[0]**2 + x[1]**2 - 1, x[0] - x[1]" "0.5,0.5"

    # Find root in bracket
    uv run python scripts/scipy_compute.py brentq "x**3 - 1" "0" "2"

    # Linear programming
    uv run python scripts/scipy_compute.py linprog "-1,-2" "[[1,1],[2,1]]" "[4,5]"

    # Curve fitting
    uv run python scripts/scipy_compute.py curve_fit "a*exp(-b*x)" "0,1,2,3" "1,0.6,0.4,0.2" "1,0.5"
"""

import sys

from scripts.math_base import (
    create_main_parser,
    get_registry,
    main_cli,
    math_command,
    parse_array,
    parse_callable,
    parse_matrix,
)

# =============================================================================
# OPTIMIZE CATEGORY (20 functions)
# =============================================================================


@math_command(
    name="minimize",
    category="optimize",
    description="Minimize a scalar function of one or more variables",
    args=[
        {"name": "func", "help": "Function to minimize, e.g., 'x**2 + 2*x'"},
        {"name": "x0", "help": "Initial guess (scalar or comma-separated for multivariate)"},
        {
            "name": "--method",
            "default": "BFGS",
            "help": "Optimization method (BFGS, Nelder-Mead, Powell, CG, L-BFGS-B, TNC, COBYLA, SLSQP, trust-constr)",
        },
        {"name": "--tol", "type": float, "default": 1e-8, "help": "Tolerance for termination"},
        {"name": "--maxiter", "type": int, "default": 1000, "help": "Maximum iterations"},
    ],
)
def cmd_minimize(
    func: str, x0: str, method: str = "BFGS", tol: float = 1e-8, maxiter: int = 1000
) -> dict:
    """Minimize a scalar function using scipy.optimize.minimize."""
    import numpy as np
    from scipy.optimize import minimize

    f = parse_callable(func)

    # Parse initial guess (can be scalar or array)
    if "," in x0:
        x0_val = parse_array(x0)
    else:
        x0_val = np.array([float(x0)])

    result = minimize(f, x0_val, method=method, tol=tol, options={"maxiter": maxiter})

    return {
        "result": result.x.tolist() if result.x.size > 1 else float(result.x[0]),
        "fun": float(result.fun),
        "success": result.success,
        "message": result.message,
        "nit": result.nit,
        "nfev": result.nfev,
    }


@math_command(
    name="minimize_scalar",
    category="optimize",
    description="Minimize a scalar function of a single variable",
    args=[
        {"name": "func", "help": "Function to minimize, e.g., 'x**2 - 4*x'"},
        {"name": "--method", "default": "brent", "help": "Method: brent, bounded, golden"},
        {"name": "--bounds", "default": None, "help": "Bounds for bounded method, e.g., '-10,10'"},
        {"name": "--tol", "type": float, "default": 1e-8, "help": "Tolerance"},
    ],
)
def cmd_minimize_scalar(
    func: str, method: str = "brent", bounds: str = None, tol: float = 1e-8
) -> dict:
    """Minimize a scalar function of a single variable."""
    from scipy.optimize import minimize_scalar

    f = parse_callable(func)

    kwargs = {"method": method, "tol": tol}
    if bounds and method == "bounded":
        bounds_arr = parse_array(bounds)
        kwargs["bounds"] = (float(bounds_arr[0]), float(bounds_arr[1]))

    result = minimize_scalar(f, **kwargs)

    return {
        "result": float(result.x),
        "fun": float(result.fun),
        "success": result.success,
        "nfev": result.nfev,
    }


@math_command(
    name="root",
    category="optimize",
    description="Find a root of a vector function",
    args=[
        {
            "name": "func",
            "help": "Function (multivariate), e.g., 'x[0]**2 + x[1] - 1, x[0] - x[1]'",
        },
        {"name": "x0", "help": "Initial guess, comma-separated"},
        {
            "name": "--method",
            "default": "hybr",
            "help": "Method: hybr, lm, broyden1, broyden2, anderson, linearmixing, diagbroyden, excitingmixing, krylov, df-sane",
        },
    ],
)
def cmd_root(func: str, x0: str, method: str = "hybr") -> dict:
    """Find a root of a vector function."""
    import numpy as np
    from scipy.optimize import root

    # Parse multi-equation function
    if "," in func and "[" in func:
        # Multiple equations: "x[0]**2 + x[1], x[0] - x[1]"
        equations = [eq.strip() for eq in func.split(",")]

        def f(x):
            namespace = {
                "x": x,
                "np": np,
                "sin": np.sin,
                "cos": np.cos,
                "exp": np.exp,
                "log": np.log,
                "sqrt": np.sqrt,
            }
            return np.array([eval(eq, namespace) for eq in equations])
    else:
        f = parse_callable(func)

    x0_val = parse_array(x0)
    result = root(f, x0_val, method=method)

    return {
        "result": result.x.tolist(),
        "fun": result.fun.tolist() if hasattr(result.fun, "tolist") else result.fun,
        "success": result.success,
        "message": result.message,
    }


@math_command(
    name="root_scalar",
    category="optimize",
    description="Find a root of a scalar function",
    args=[
        {"name": "func", "help": "Function, e.g., 'x**3 - x - 2'"},
        {"name": "--bracket", "default": None, "help": "Bracket [a, b], e.g., '0,2'"},
        {"name": "--x0", "default": None, "help": "Initial guess"},
        {
            "name": "--method",
            "default": "brentq",
            "help": "Method: brentq, brenth, ridder, bisect, newton, secant, halley",
        },
    ],
)
def cmd_root_scalar(func: str, bracket: str = None, x0: str = None, method: str = "brentq") -> dict:
    """Find a root of a scalar function."""
    from scipy.optimize import root_scalar

    f = parse_callable(func)

    kwargs = {"method": method}
    if bracket:
        bracket_arr = parse_array(bracket)
        kwargs["bracket"] = [float(bracket_arr[0]), float(bracket_arr[1])]
    if x0:
        kwargs["x0"] = float(x0)

    result = root_scalar(f, **kwargs)

    return {
        "result": float(result.root),
        "iterations": result.iterations,
        "function_calls": result.function_calls,
        "converged": result.converged,
    }


@math_command(
    name="fsolve",
    category="optimize",
    description="Find roots of a function (wrapper around MINPACK hybrd/hybrj)",
    args=[
        {"name": "func", "help": "Function(s), e.g., 'x[0]**2 + x[1]**2 - 1, x[0] - x[1]'"},
        {"name": "x0", "help": "Initial guess, comma-separated"},
        {"name": "--full_output", "action": "store_true", "help": "Return additional info"},
    ],
)
def cmd_fsolve(func: str, x0: str, full_output: bool = False) -> dict:
    """Find roots using fsolve (legacy MINPACK interface)."""
    import numpy as np
    from scipy.optimize import fsolve

    # Parse multi-equation function
    if "," in func and "[" in func:
        equations = [eq.strip() for eq in func.split(",")]

        def f(x):
            namespace = {
                "x": x,
                "np": np,
                "sin": np.sin,
                "cos": np.cos,
                "exp": np.exp,
                "log": np.log,
                "sqrt": np.sqrt,
            }
            return np.array([eval(eq, namespace) for eq in equations])
    else:
        f = parse_callable(func)

    x0_val = parse_array(x0)

    if full_output:
        result, info, ier, mesg = fsolve(f, x0_val, full_output=True)
        return {
            "result": result.tolist(),
            "info": {"nfev": info.get("nfev", 0)},
            "ier": ier,
            "message": mesg,
        }
    else:
        result = fsolve(f, x0_val)
        return {"result": result.tolist()}


@math_command(
    name="brentq",
    category="optimize",
    description="Find root using Brent's method in a bracketing interval",
    args=[
        {"name": "func", "help": "Function, e.g., 'x**3 - x - 2'"},
        {"name": "a", "help": "Lower bracket bound"},
        {"name": "b", "help": "Upper bracket bound"},
        {"name": "--xtol", "type": float, "default": 2e-12, "help": "Tolerance"},
        {"name": "--maxiter", "type": int, "default": 100, "help": "Maximum iterations"},
    ],
)
def cmd_brentq(func: str, a: str, b: str, xtol: float = 2e-12, maxiter: int = 100) -> dict:
    """Find root using Brent's method."""
    from scipy.optimize import brentq

    f = parse_callable(func)
    result = brentq(f, float(a), float(b), xtol=xtol, maxiter=maxiter, full_output=True)

    root_val, info = result
    return {
        "result": float(root_val),
        "iterations": info.iterations,
        "function_calls": info.function_calls,
        "converged": info.flag == 0,
    }


@math_command(
    name="bisect",
    category="optimize",
    description="Find root using bisection method",
    args=[
        {"name": "func", "help": "Function, e.g., 'x**2 - 2'"},
        {"name": "a", "help": "Lower bracket bound"},
        {"name": "b", "help": "Upper bracket bound"},
        {"name": "--xtol", "type": float, "default": 2e-12, "help": "Tolerance"},
    ],
)
def cmd_bisect(func: str, a: str, b: str, xtol: float = 2e-12) -> dict:
    """Find root using bisection method."""
    from scipy.optimize import bisect

    f = parse_callable(func)
    result = bisect(f, float(a), float(b), xtol=xtol, full_output=True)

    root_val, info = result
    return {
        "result": float(root_val),
        "iterations": info.iterations,
        "function_calls": info.function_calls,
        "converged": info.flag == 0,
    }


@math_command(
    name="newton",
    category="optimize",
    description="Find root using Newton-Raphson (or secant) method",
    args=[
        {"name": "func", "help": "Function, e.g., 'x**3 - x - 2'"},
        {"name": "x0", "help": "Initial guess"},
        {"name": "--fprime", "default": None, "help": "Derivative function (optional)"},
        {"name": "--tol", "type": float, "default": 1.48e-8, "help": "Tolerance"},
        {"name": "--maxiter", "type": int, "default": 50, "help": "Maximum iterations"},
    ],
)
def cmd_newton(
    func: str, x0: str, fprime: str = None, tol: float = 1.48e-8, maxiter: int = 50
) -> dict:
    """Find root using Newton-Raphson method."""
    from scipy.optimize import newton

    f = parse_callable(func)

    kwargs = {"x0": float(x0), "tol": tol, "maxiter": maxiter, "full_output": True}
    if fprime:
        kwargs["fprime"] = parse_callable(fprime)

    result = newton(f, **kwargs)
    root_val, info = result

    return {
        "result": float(root_val),
        "iterations": info.iterations,
        "function_calls": info.function_calls,
        "converged": info.converged,
    }


@math_command(
    name="curve_fit",
    category="optimize",
    description="Fit a function to data using non-linear least squares",
    args=[
        {"name": "func", "help": "Model function with parameters, e.g., 'a*exp(-b*x)'"},
        {"name": "xdata", "help": "X data points, comma-separated"},
        {"name": "ydata", "help": "Y data points, comma-separated"},
        {"name": "p0", "help": "Initial parameter guesses, comma-separated"},
        {"name": "--bounds", "default": None, "help": "Parameter bounds, e.g., '0,0:inf,inf'"},
    ],
)
def cmd_curve_fit(func: str, xdata: str, ydata: str, p0: str, bounds: str = None) -> dict:
    """Fit a curve to data."""
    import numpy as np
    from scipy.optimize import curve_fit

    xdata_arr = parse_array(xdata)
    ydata_arr = parse_array(ydata)
    p0_arr = parse_array(p0)

    # Build function with named parameters
    # Parse function to extract parameter names (assume single letter params: a, b, c, ...)
    # The function should use x as the independent variable
    def model(x, *params):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        # Assign parameters to common names
        param_names = ["a", "b", "c", "d", "e", "f", "g", "h"]
        for i, p in enumerate(params):
            if i < len(param_names):
                namespace[param_names[i]] = p
        return eval(func, namespace)

    kwargs = {"p0": p0_arr}
    if bounds:
        # Parse bounds: "0,0:inf,inf" -> ([0,0], [inf,inf])
        parts = bounds.split(":")
        lower = parse_array(parts[0].replace("inf", "np.inf").replace("-inf", "-np.inf"))
        upper = parse_array(parts[1].replace("inf", "np.inf").replace("-inf", "-np.inf"))
        # Replace string inf with actual inf
        lower = np.array(
            [
                np.inf if x == "inf" else (-np.inf if x == "-inf" else float(x))
                for x in parts[0].split(",")
            ]
        )
        upper = np.array(
            [
                np.inf if x == "inf" else (-np.inf if x == "-inf" else float(x))
                for x in parts[1].split(",")
            ]
        )
        kwargs["bounds"] = (lower, upper)

    popt, pcov = curve_fit(model, xdata_arr, ydata_arr, **kwargs)

    # Calculate standard errors
    perr = np.sqrt(np.diag(pcov))

    return {
        "result": popt.tolist(),
        "covariance": pcov.tolist(),
        "std_errors": perr.tolist(),
        "param_names": ["a", "b", "c", "d", "e", "f", "g", "h"][: len(popt)],
    }


@math_command(
    name="least_squares",
    category="optimize",
    description="Solve a nonlinear least-squares problem with bounds",
    args=[
        {"name": "func", "help": "Residual function, e.g., 'x[0]*exp(-x[1]*t) - y'"},
        {"name": "x0", "help": "Initial parameter guess, comma-separated"},
        {"name": "--bounds", "default": None, "help": "Bounds: 'lower:upper', e.g., '0,0:1,1'"},
        {"name": "--method", "default": "trf", "help": "Method: trf, dogbox, lm"},
    ],
)
def cmd_least_squares(func: str, x0: str, bounds: str = None, method: str = "trf") -> dict:
    """Solve nonlinear least-squares with bounds."""
    import numpy as np
    from scipy.optimize import least_squares

    x0_arr = parse_array(x0)

    # Create residual function
    def residuals(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
        }
        return eval(func, namespace)

    kwargs = {"method": method}
    if bounds:
        parts = bounds.split(":")
        lower = parse_array(parts[0])
        upper = parse_array(parts[1])
        kwargs["bounds"] = (lower, upper)
    else:
        kwargs["bounds"] = (-np.inf, np.inf)

    result = least_squares(residuals, x0_arr, **kwargs)

    return {
        "result": result.x.tolist(),
        "cost": float(result.cost),
        "optimality": float(result.optimality),
        "success": result.success,
        "message": result.message,
        "nfev": result.nfev,
    }


@math_command(
    name="linprog",
    category="optimize",
    description="Linear programming: minimize c @ x subject to constraints",
    args=[
        {"name": "c", "help": "Coefficients of linear objective, comma-separated"},
        {"name": "A_ub", "help": "Inequality constraint matrix (A_ub @ x <= b_ub)"},
        {"name": "b_ub", "help": "Inequality constraint bounds, comma-separated"},
        {"name": "--A_eq", "default": None, "help": "Equality constraint matrix"},
        {"name": "--b_eq", "default": None, "help": "Equality constraint bounds"},
        {"name": "--bounds", "default": None, "help": "Variable bounds, e.g., '0,None:0,None'"},
        {
            "name": "--method",
            "default": "highs",
            "help": "Method: highs, highs-ds, highs-ipm, interior-point, revised simplex, simplex",
        },
    ],
)
def cmd_linprog(
    c: str,
    A_ub: str,
    b_ub: str,
    A_eq: str = None,
    b_eq: str = None,
    bounds: str = None,
    method: str = "highs",
) -> dict:
    """Solve linear programming problem."""
    from scipy.optimize import linprog

    c_arr = parse_array(c)
    A_ub_arr = parse_matrix(A_ub)
    b_ub_arr = parse_array(b_ub)

    kwargs = {"c": c_arr, "A_ub": A_ub_arr, "b_ub": b_ub_arr, "method": method}

    if A_eq:
        kwargs["A_eq"] = parse_matrix(A_eq)
    if b_eq:
        kwargs["b_eq"] = parse_array(b_eq)
    if bounds:
        # Parse bounds: "0,None:0,None" -> [(0, None), (0, None)]
        var_bounds = []
        for b in bounds.split(":"):
            parts = b.split(",")
            lb = None if parts[0].strip().lower() == "none" else float(parts[0])
            ub = None if parts[1].strip().lower() == "none" else float(parts[1])
            var_bounds.append((lb, ub))
        kwargs["bounds"] = var_bounds

    result = linprog(**kwargs)

    return {
        "result": result.x.tolist() if result.x is not None else None,
        "fun": float(result.fun) if result.fun is not None else None,
        "success": result.success,
        "message": result.message,
        "nit": result.nit,
    }


@math_command(
    name="differential_evolution",
    category="optimize",
    description="Global optimization using differential evolution",
    args=[
        {"name": "func", "help": "Function to minimize, e.g., 'x[0]**2 + x[1]**2'"},
        {"name": "bounds", "help": "Bounds for each variable, e.g., '-5,5:-5,5'"},
        {"name": "--strategy", "default": "best1bin", "help": "DE strategy"},
        {"name": "--maxiter", "type": int, "default": 1000, "help": "Maximum iterations"},
        {"name": "--popsize", "type": int, "default": 15, "help": "Population size multiplier"},
        {"name": "--seed", "type": int, "default": None, "help": "Random seed"},
    ],
)
def cmd_differential_evolution(
    func: str,
    bounds: str,
    strategy: str = "best1bin",
    maxiter: int = 1000,
    popsize: int = 15,
    seed: int = None,
) -> dict:
    """Global optimization using differential evolution."""
    import numpy as np
    from scipy.optimize import differential_evolution

    # Parse function for array input
    def f(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
        }
        return eval(func, namespace)

    # Parse bounds: "-5,5:-5,5" -> [(-5, 5), (-5, 5)]
    bounds_list = []
    for b in bounds.split(":"):
        parts = b.split(",")
        bounds_list.append((float(parts[0]), float(parts[1])))

    result = differential_evolution(
        f, bounds_list, strategy=strategy, maxiter=maxiter, popsize=popsize, seed=seed
    )

    return {
        "result": result.x.tolist(),
        "fun": float(result.fun),
        "success": result.success,
        "message": result.message,
        "nit": result.nit,
        "nfev": result.nfev,
    }


@math_command(
    name="basinhopping",
    category="optimize",
    description="Global optimization using basin-hopping",
    args=[
        {"name": "func", "help": "Function to minimize"},
        {"name": "x0", "help": "Initial guess, comma-separated"},
        {
            "name": "--niter",
            "type": int,
            "default": 100,
            "help": "Number of basin-hopping iterations",
        },
        {"name": "--T", "type": float, "default": 1.0, "help": "Temperature parameter"},
        {"name": "--stepsize", "type": float, "default": 0.5, "help": "Step size"},
        {"name": "--seed", "type": int, "default": None, "help": "Random seed"},
    ],
)
def cmd_basinhopping(
    func: str, x0: str, niter: int = 100, T: float = 1.0, stepsize: float = 0.5, seed: int = None
) -> dict:
    """Global optimization using basin-hopping."""
    import numpy as np
    from scipy.optimize import basinhopping

    def f(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
        }
        # Handle scalar case
        if np.isscalar(x) or x.size == 1:
            namespace["x"] = float(x) if np.isscalar(x) else float(x[0])
            return eval(func.replace("x[0]", "x"), namespace)
        return eval(func, namespace)

    x0_arr = parse_array(x0)

    result = basinhopping(f, x0_arr, niter=niter, T=T, stepsize=stepsize, seed=seed)

    return {
        "result": result.x.tolist() if hasattr(result.x, "tolist") else [float(result.x)],
        "fun": float(result.fun),
        "success": result.lowest_optimization_result.success,
        "message": result.message[0] if isinstance(result.message, list) else str(result.message),
        "nit": result.nit,
    }


@math_command(
    name="dual_annealing",
    category="optimize",
    description="Global optimization using dual annealing",
    args=[
        {"name": "func", "help": "Function to minimize"},
        {"name": "bounds", "help": "Bounds for each variable, e.g., '-5,5:-5,5'"},
        {"name": "--maxiter", "type": int, "default": 1000, "help": "Maximum iterations"},
        {"name": "--initial_temp", "type": float, "default": 5230.0, "help": "Initial temperature"},
        {"name": "--seed", "type": int, "default": None, "help": "Random seed"},
    ],
)
def cmd_dual_annealing(
    func: str, bounds: str, maxiter: int = 1000, initial_temp: float = 5230.0, seed: int = None
) -> dict:
    """Global optimization using dual annealing."""
    import numpy as np
    from scipy.optimize import dual_annealing

    def f(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
        }
        return eval(func, namespace)

    # Parse bounds
    bounds_list = []
    for b in bounds.split(":"):
        parts = b.split(",")
        bounds_list.append((float(parts[0]), float(parts[1])))

    result = dual_annealing(f, bounds_list, maxiter=maxiter, initial_temp=initial_temp, seed=seed)

    return {
        "result": result.x.tolist(),
        "fun": float(result.fun),
        "success": result.success,
        "message": result.message,
        "nit": result.nit,
        "nfev": result.nfev,
    }


@math_command(
    name="shgo",
    category="optimize",
    description="Global optimization using simplicial homology (SHGO)",
    args=[
        {"name": "func", "help": "Function to minimize"},
        {"name": "bounds", "help": "Bounds for each variable, e.g., '-5,5:-5,5'"},
        {"name": "--n", "type": int, "default": 100, "help": "Number of sampling points"},
        {"name": "--iters", "type": int, "default": 1, "help": "Number of iterations"},
        {
            "name": "--sampling_method",
            "default": "simplicial",
            "help": "Sampling method: simplicial, halton, sobol",
        },
    ],
)
def cmd_shgo(
    func: str, bounds: str, n: int = 100, iters: int = 1, sampling_method: str = "simplicial"
) -> dict:
    """Global optimization using SHGO."""
    import numpy as np
    from scipy.optimize import shgo

    def f(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
        }
        return eval(func, namespace)

    # Parse bounds
    bounds_list = []
    for b in bounds.split(":"):
        parts = b.split(",")
        bounds_list.append((float(parts[0]), float(parts[1])))

    result = shgo(f, bounds_list, n=n, iters=iters, sampling_method=sampling_method)

    return {
        "result": result.x.tolist(),
        "fun": float(result.fun),
        "success": result.success,
        "message": result.message,
        "nfev": result.nfev,
        "nit": result.nit if hasattr(result, "nit") else None,
    }


@math_command(
    name="brute",
    category="optimize",
    description="Global optimization using brute force grid search",
    args=[
        {"name": "func", "help": "Function to minimize"},
        {
            "name": "ranges",
            "help": "Ranges for each variable, e.g., '-5,5,0.5:-5,5,0.5' (min,max,step)",
        },
        {
            "name": "--Ns",
            "type": int,
            "default": 20,
            "help": "Number of grid points per dimension (if step not specified)",
        },
        {"name": "--finish", "action": "store_true", "help": "Polish with local optimizer"},
    ],
)
def cmd_brute(func: str, ranges: str, Ns: int = 20, finish: bool = False) -> dict:
    """Global optimization using brute force."""
    import numpy as np
    from scipy.optimize import brute, fmin

    def f(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
        }
        # Handle 1D case
        if np.isscalar(x):
            namespace["x"] = np.array([x])
        return eval(func, namespace)

    # Parse ranges: "-5,5,0.5:-5,5,0.5" or "-5,5:-5,5"
    ranges_list = []
    for r in ranges.split(":"):
        parts = r.split(",")
        if len(parts) == 3:
            ranges_list.append(slice(float(parts[0]), float(parts[1]), float(parts[2])))
        else:
            ranges_list.append(slice(float(parts[0]), float(parts[1])))

    finish_func = fmin if finish else None

    result = brute(f, ranges_list, Ns=Ns, finish=finish_func, full_output=True)

    x_opt, fval, grid, Jout = result

    return {
        "result": x_opt.tolist() if hasattr(x_opt, "tolist") else [float(x_opt)],
        "fun": float(fval),
    }


@math_command(
    name="golden",
    category="optimize",
    description="Find minimum using golden section search",
    args=[
        {"name": "func", "help": "Function to minimize"},
        {"name": "brack", "help": "Bracketing interval, e.g., '0,1' or '0,0.5,1'"},
        {"name": "--tol", "type": float, "default": 1.48e-8, "help": "Tolerance"},
    ],
)
def cmd_golden(func: str, brack: str, tol: float = 1.48e-8) -> dict:
    """Find minimum using golden section search."""
    from scipy.optimize import golden

    f = parse_callable(func)

    brack_arr = parse_array(brack)
    brack_tuple = tuple(brack_arr)

    result = golden(f, brack=brack_tuple, tol=tol, full_output=True)

    xmin, fval, funcalls = result

    return {"result": float(xmin), "fun": float(fval), "function_calls": funcalls}


@math_command(
    name="brent",
    category="optimize",
    description="Find minimum using Brent's method",
    args=[
        {"name": "func", "help": "Function to minimize"},
        {"name": "brack", "help": "Bracketing interval, e.g., '0,1' or '0,0.5,1'"},
        {"name": "--tol", "type": float, "default": 1.48e-8, "help": "Tolerance"},
    ],
)
def cmd_brent(func: str, brack: str, tol: float = 1.48e-8) -> dict:
    """Find minimum using Brent's method."""
    from scipy.optimize import brent

    f = parse_callable(func)

    brack_arr = parse_array(brack)
    brack_tuple = tuple(brack_arr)

    result = brent(f, brack=brack_tuple, tol=tol, full_output=True)

    xmin, fval, iters, funcalls = result

    return {
        "result": float(xmin),
        "fun": float(fval),
        "iterations": iters,
        "function_calls": funcalls,
    }


@math_command(
    name="fminbound",
    category="optimize",
    description="Find minimum of scalar function in bounded interval",
    args=[
        {"name": "func", "help": "Function to minimize"},
        {"name": "x1", "help": "Lower bound"},
        {"name": "x2", "help": "Upper bound"},
        {"name": "--xtol", "type": float, "default": 1e-5, "help": "Tolerance"},
    ],
)
def cmd_fminbound(func: str, x1: str, x2: str, xtol: float = 1e-5) -> dict:
    """Find minimum in bounded interval."""
    from scipy.optimize import fminbound

    f = parse_callable(func)

    result = fminbound(f, float(x1), float(x2), xtol=xtol, full_output=True)

    xopt, fval, ierr, numfunc = result

    return {
        "result": float(xopt),
        "fun": float(fval),
        "converged": ierr == 0,
        "function_calls": numfunc,
    }


@math_command(
    name="direct",
    category="optimize",
    description="Global optimization using DIRECT algorithm (Dividing Rectangles)",
    args=[
        {"name": "func", "help": "Function to minimize"},
        {"name": "bounds", "help": "Bounds for each variable, e.g., '-5,5:-5,5'"},
        {"name": "--eps", "type": float, "default": 1e-4, "help": "Convergence tolerance"},
        {"name": "--maxfun", "type": int, "default": None, "help": "Maximum function evaluations"},
        {"name": "--maxiter", "type": int, "default": 1000, "help": "Maximum iterations"},
        {"name": "--locally_biased", "action": "store_true", "help": "Use locally-biased variant"},
    ],
)
def cmd_direct(
    func: str,
    bounds: str,
    eps: float = 1e-4,
    maxfun: int = None,
    maxiter: int = 1000,
    locally_biased: bool = False,
) -> dict:
    """Global optimization using DIRECT algorithm."""
    import numpy as np
    from scipy.optimize import direct

    def f(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
        }
        return eval(func, namespace)

    # Parse bounds: "-5,5:-5,5" -> [(-5, 5), (-5, 5)]
    bounds_list = []
    for b in bounds.split(":"):
        parts = b.split(",")
        bounds_list.append((float(parts[0]), float(parts[1])))

    result = direct(
        f, bounds_list, eps=eps, maxfun=maxfun, maxiter=maxiter, locally_biased=locally_biased
    )

    return {
        "result": result.x.tolist(),
        "fun": float(result.fun),
        "success": result.success,
        "message": result.message,
        "nfev": result.nfev,
        "nit": result.nit,
    }


# =============================================================================
# INTEGRATE CATEGORY (14 functions)
# =============================================================================


@math_command(
    name="quad",
    category="integrate",
    description="Adaptive quadrature for definite integrals",
    args=[
        {"name": "func", "help": "Function to integrate, e.g., 'x**2'"},
        {"name": "a", "help": "Lower integration bound"},
        {"name": "b", "help": "Upper integration bound"},
        {"name": "--epsabs", "type": float, "default": 1.49e-8, "help": "Absolute tolerance"},
        {"name": "--epsrel", "type": float, "default": 1.49e-8, "help": "Relative tolerance"},
        {"name": "--limit", "type": int, "default": 50, "help": "Upper bound on subdivisions"},
    ],
)
def cmd_quad(
    func: str, a: str, b: str, epsabs: float = 1.49e-8, epsrel: float = 1.49e-8, limit: int = 50
) -> dict:
    """Compute definite integral using adaptive quadrature."""
    import numpy as np
    from scipy.integrate import quad

    f = parse_callable(func)

    # Handle inf bounds
    a_val = (
        -np.inf
        if a.strip().lower() == "-inf"
        else (np.inf if a.strip().lower() == "inf" else float(a))
    )
    b_val = (
        -np.inf
        if b.strip().lower() == "-inf"
        else (np.inf if b.strip().lower() == "inf" else float(b))
    )

    result, error = quad(f, a_val, b_val, epsabs=epsabs, epsrel=epsrel, limit=limit)

    return {"result": float(result), "error": float(error)}


@math_command(
    name="dblquad",
    category="integrate",
    description="Double integral over a region",
    args=[
        {"name": "func", "help": "Function f(y, x) to integrate, e.g., 'x*y'"},
        {"name": "a", "help": "Lower x bound"},
        {"name": "b", "help": "Upper x bound"},
        {"name": "gfun", "help": "Lower y bound function of x, e.g., '0' or 'x'"},
        {"name": "hfun", "help": "Upper y bound function of x, e.g., '1' or '1-x'"},
        {"name": "--epsabs", "type": float, "default": 1.49e-8, "help": "Absolute tolerance"},
        {"name": "--epsrel", "type": float, "default": 1.49e-8, "help": "Relative tolerance"},
    ],
)
def cmd_dblquad(
    func: str,
    a: str,
    b: str,
    gfun: str,
    hfun: str,
    epsabs: float = 1.49e-8,
    epsrel: float = 1.49e-8,
) -> dict:
    """Compute double integral."""
    import numpy as np
    from scipy.integrate import dblquad

    # Function takes (y, x) as arguments
    def f(y, x):
        namespace = {
            "x": x,
            "y": y,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        return eval(func, namespace)

    # Bound functions take x as argument
    def g(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        return eval(gfun, namespace)

    def h(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        return eval(hfun, namespace)

    result, error = dblquad(f, float(a), float(b), g, h, epsabs=epsabs, epsrel=epsrel)

    return {"result": float(result), "error": float(error)}


@math_command(
    name="tplquad",
    category="integrate",
    description="Triple integral over a region",
    args=[
        {"name": "func", "help": "Function f(z, y, x) to integrate"},
        {"name": "a", "help": "Lower x bound"},
        {"name": "b", "help": "Upper x bound"},
        {"name": "gfun", "help": "Lower y bound function of x"},
        {"name": "hfun", "help": "Upper y bound function of x"},
        {"name": "qfun", "help": "Lower z bound function of x, y"},
        {"name": "rfun", "help": "Upper z bound function of x, y"},
        {"name": "--epsabs", "type": float, "default": 1.49e-8, "help": "Absolute tolerance"},
        {"name": "--epsrel", "type": float, "default": 1.49e-8, "help": "Relative tolerance"},
    ],
)
def cmd_tplquad(
    func: str,
    a: str,
    b: str,
    gfun: str,
    hfun: str,
    qfun: str,
    rfun: str,
    epsabs: float = 1.49e-8,
    epsrel: float = 1.49e-8,
) -> dict:
    """Compute triple integral."""
    import numpy as np
    from scipy.integrate import tplquad

    def f(z, y, x):
        namespace = {
            "x": x,
            "y": y,
            "z": z,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        return eval(func, namespace)

    def g(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        return eval(gfun, namespace)

    def h(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        return eval(hfun, namespace)

    def q(x, y):
        namespace = {
            "x": x,
            "y": y,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        return eval(qfun, namespace)

    def r(x, y):
        namespace = {
            "x": x,
            "y": y,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        return eval(rfun, namespace)

    result, error = tplquad(f, float(a), float(b), g, h, q, r, epsabs=epsabs, epsrel=epsrel)

    return {"result": float(result), "error": float(error)}


@math_command(
    name="nquad",
    category="integrate",
    description="N-dimensional integration over a hyper-rectangular region",
    args=[
        {"name": "func", "help": "Function to integrate, using x[0], x[1], etc."},
        {"name": "ranges", "help": "Integration ranges, e.g., '0,1:0,1' for 2D"},
        {"name": "--opts", "default": None, "help": "Options dict as JSON string"},
    ],
)
def cmd_nquad(func: str, ranges: str, opts: str = None) -> dict:
    """Compute N-dimensional integral."""
    import json

    import numpy as np
    from scipy.integrate import nquad

    def f(*args):
        namespace = {
            "x": np.array(args),
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        # Also provide individual variables
        for i, val in enumerate(args):
            namespace[f"x{i}"] = val
        return eval(func, namespace)

    # Parse ranges: "0,1:0,1" -> [[0, 1], [0, 1]]
    ranges_list = []
    for r in ranges.split(":"):
        parts = r.split(",")
        ranges_list.append([float(parts[0]), float(parts[1])])

    kwargs = {}
    if opts:
        kwargs["opts"] = json.loads(opts)

    result, error = nquad(f, ranges_list, **kwargs)

    return {"result": float(result), "error": float(error)}


@math_command(
    name="fixed_quad",
    category="integrate",
    description="Fixed-order Gaussian quadrature",
    args=[
        {"name": "func", "help": "Function to integrate"},
        {"name": "a", "help": "Lower bound"},
        {"name": "b", "help": "Upper bound"},
        {"name": "--n", "type": int, "default": 5, "help": "Order of quadrature (1-5)"},
    ],
)
def cmd_fixed_quad(func: str, a: str, b: str, n: int = 5) -> dict:
    """Compute integral using fixed-order Gaussian quadrature."""
    from scipy.integrate import fixed_quad

    f = parse_callable(func)
    result, _ = fixed_quad(f, float(a), float(b), n=n)

    return {"result": float(result)}


@math_command(
    name="simpson",
    category="integrate",
    description="Simpson's rule integration from samples",
    args=[
        {"name": "y", "help": "Y values (samples), comma-separated"},
        {"name": "--x", "default": None, "help": "X values (optional), comma-separated"},
        {"name": "--dx", "type": float, "default": 1.0, "help": "Spacing if x not provided"},
    ],
)
def cmd_simpson(y: str, x: str = None, dx: float = 1.0) -> dict:
    """Integrate samples using Simpson's rule."""
    from scipy.integrate import simpson

    y_arr = parse_array(y)

    kwargs = {}
    if x:
        kwargs["x"] = parse_array(x)
    else:
        kwargs["dx"] = dx

    result = simpson(y_arr, **kwargs)

    return {"result": float(result)}


@math_command(
    name="trapezoid",
    category="integrate",
    description="Trapezoidal rule integration from samples",
    args=[
        {"name": "y", "help": "Y values (samples), comma-separated"},
        {"name": "--x", "default": None, "help": "X values (optional), comma-separated"},
        {"name": "--dx", "type": float, "default": 1.0, "help": "Spacing if x not provided"},
    ],
)
def cmd_trapezoid(y: str, x: str = None, dx: float = 1.0) -> dict:
    """Integrate samples using trapezoidal rule."""
    from scipy.integrate import trapezoid

    y_arr = parse_array(y)

    kwargs = {}
    if x:
        kwargs["x"] = parse_array(x)
    else:
        kwargs["dx"] = dx

    result = trapezoid(y_arr, **kwargs)

    return {"result": float(result)}


@math_command(
    name="cumulative_trapezoid",
    category="integrate",
    description="Cumulative trapezoidal integration from samples",
    args=[
        {"name": "y", "help": "Y values (samples), comma-separated"},
        {"name": "--x", "default": None, "help": "X values (optional), comma-separated"},
        {"name": "--dx", "type": float, "default": 1.0, "help": "Spacing if x not provided"},
        {"name": "--initial", "type": float, "default": None, "help": "Initial value (optional)"},
    ],
)
def cmd_cumulative_trapezoid(y: str, x: str = None, dx: float = 1.0, initial: float = None) -> dict:
    """Compute cumulative integral using trapezoidal rule."""
    from scipy.integrate import cumulative_trapezoid

    y_arr = parse_array(y)

    kwargs = {}
    if x:
        kwargs["x"] = parse_array(x)
    else:
        kwargs["dx"] = dx
    if initial is not None:
        kwargs["initial"] = initial

    result = cumulative_trapezoid(y_arr, **kwargs)

    return {"result": result.tolist()}


@math_command(
    name="odeint",
    category="integrate",
    description="Integrate ODEs using LSODA (legacy interface)",
    args=[
        {
            "name": "func",
            "help": "Derivative function dy/dt = f(y, t), e.g., '-y' for exponential decay",
        },
        {"name": "y0", "help": "Initial conditions, comma-separated"},
        {"name": "t", "help": "Time points, comma-separated or 'start,end,n'"},
        {
            "name": "--tfirst",
            "action": "store_true",
            "help": "If True, function signature is f(t, y)",
        },
    ],
)
def cmd_odeint(func: str, y0: str, t: str, tfirst: bool = False) -> dict:
    """Integrate system of ODEs using LSODA."""
    import numpy as np
    from scipy.integrate import odeint

    y0_arr = parse_array(y0)

    # Parse time array
    if t.count(",") == 2 and ":" not in t:
        # Assume "start,end,n" format
        parts = t.split(",")
        t_arr = np.linspace(float(parts[0]), float(parts[1]), int(parts[2]))
    else:
        t_arr = parse_array(t)

    # Create ODE function
    def f(y, t_val):
        namespace = {
            "y": y,
            "t": t_val,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        # For scalar y, also provide as 'y' directly
        if np.isscalar(y) or (hasattr(y, "size") and y.size == 1):
            namespace["y"] = float(y) if np.isscalar(y) else float(y[0])
        result = eval(func, namespace)
        return np.atleast_1d(result)

    if tfirst:

        def f_tfirst(y, t_val):
            return f(y, t_val)

        result = odeint(f_tfirst, y0_arr, t_arr, tfirst=False)
    else:
        result = odeint(f, y0_arr, t_arr)

    return {"t": t_arr.tolist(), "y": result.tolist()}


@math_command(
    name="solve_ivp",
    category="integrate",
    description="Solve initial value problem for ODEs",
    args=[
        {"name": "func", "help": "Derivative function dy/dt = f(t, y)"},
        {"name": "t_span", "help": "Time span: 'start,end'"},
        {"name": "y0", "help": "Initial conditions, comma-separated"},
        {
            "name": "--method",
            "default": "RK45",
            "help": "Method: RK45, RK23, DOP853, Radau, BDF, LSODA",
        },
        {"name": "--t_eval", "default": None, "help": "Times to evaluate, comma-separated"},
        {"name": "--max_step", "type": float, "default": None, "help": "Maximum step size"},
        {"name": "--rtol", "type": float, "default": 1e-3, "help": "Relative tolerance"},
        {"name": "--atol", "type": float, "default": 1e-6, "help": "Absolute tolerance"},
    ],
)
def cmd_solve_ivp(
    func: str,
    t_span: str,
    y0: str,
    method: str = "RK45",
    t_eval: str = None,
    max_step: float = None,
    rtol: float = 1e-3,
    atol: float = 1e-6,
) -> dict:
    """Solve initial value problem using modern interface."""
    import numpy as np
    from scipy.integrate import solve_ivp

    y0_arr = parse_array(y0)
    t_span_arr = parse_array(t_span)

    def f(t, y):
        namespace = {
            "t": t,
            "y": y,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        # For scalar y
        if np.isscalar(y) or (hasattr(y, "size") and y.size == 1):
            namespace["y"] = float(y) if np.isscalar(y) else float(y[0])
        result = eval(func, namespace)
        return np.atleast_1d(result)

    kwargs = {"method": method, "rtol": rtol, "atol": atol}
    if t_eval:
        kwargs["t_eval"] = parse_array(t_eval)
    if max_step:
        kwargs["max_step"] = max_step

    result = solve_ivp(f, (t_span_arr[0], t_span_arr[1]), y0_arr, **kwargs)

    return {
        "t": result.t.tolist(),
        "y": result.y.tolist(),
        "success": result.success,
        "message": result.message,
        "nfev": result.nfev,
    }


@math_command(
    name="solve_bvp",
    category="integrate",
    description="Solve boundary value problem for ODEs",
    args=[
        {"name": "func", "help": "Derivative function dy/dx = f(x, y)"},
        {"name": "bc", "help": "Boundary condition residuals, e.g., 'ya[0]-0, yb[0]-1'"},
        {"name": "x", "help": "Initial mesh points, comma-separated"},
        {
            "name": "y_init",
            "help": "Initial guess for y, format: 'y0_vals;y1_vals' for multiple components",
        },
        {"name": "--tol", "type": float, "default": 1e-3, "help": "Tolerance"},
        {"name": "--max_nodes", "type": int, "default": 1000, "help": "Maximum mesh nodes"},
    ],
)
def cmd_solve_bvp(
    func: str, bc: str, x: str, y_init: str, tol: float = 1e-3, max_nodes: int = 1000
) -> dict:
    """Solve boundary value problem."""
    import numpy as np
    from scipy.integrate import solve_bvp

    x_arr = parse_array(x)

    # Parse y_init: "1,1,1;0,0,0" -> [[1,1,1], [0,0,0]]
    if ";" in y_init:
        y_init_arr = np.array([parse_array(row) for row in y_init.split(";")])
    else:
        y_init_arr = np.array([parse_array(y_init)])

    def f(x_val, y):
        namespace = {
            "x": x_val,
            "y": y,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        result = eval(func, namespace)
        return np.atleast_1d(result)

    def bc_func(ya, yb):
        namespace = {
            "ya": ya,
            "yb": yb,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        # Parse boundary conditions
        bc_eqs = [eq.strip() for eq in bc.split(",")]
        return np.array([eval(eq, namespace) for eq in bc_eqs])

    result = solve_bvp(f, bc_func, x_arr, y_init_arr, tol=tol, max_nodes=max_nodes)

    return {
        "x": result.x.tolist(),
        "y": result.y.tolist(),
        "success": result.success,
        "message": result.message,
        "niter": result.niter,
    }


@math_command(
    name="quad_vec",
    category="integrate",
    description="Adaptive quadrature for vector-valued functions",
    args=[
        {"name": "func", "help": "Vector-valued function, e.g., '[x, x**2, x**3]'"},
        {"name": "a", "help": "Lower bound"},
        {"name": "b", "help": "Upper bound"},
        {"name": "--epsabs", "type": float, "default": 1e-200, "help": "Absolute tolerance"},
        {"name": "--epsrel", "type": float, "default": 1e-8, "help": "Relative tolerance"},
        {"name": "--limit", "type": int, "default": 10000, "help": "Maximum subdivisions"},
    ],
)
def cmd_quad_vec(
    func: str, a: str, b: str, epsabs: float = 1e-200, epsrel: float = 1e-8, limit: int = 10000
) -> dict:
    """Compute integral of vector-valued function."""
    import numpy as np
    from scipy.integrate import quad_vec

    def f(x):
        namespace = {
            "x": x,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
        }
        result = eval(func, namespace)
        return np.array(result)

    # Handle inf bounds
    a_val = (
        -np.inf
        if a.strip().lower() == "-inf"
        else (np.inf if a.strip().lower() == "inf" else float(a))
    )
    b_val = (
        -np.inf
        if b.strip().lower() == "-inf"
        else (np.inf if b.strip().lower() == "inf" else float(b))
    )

    result, error = quad_vec(f, a_val, b_val, epsabs=epsabs, epsrel=epsrel, limit=limit)

    return {"result": result.tolist(), "error": float(error)}


# =============================================================================
# INTERPOLATE CATEGORY (20 functions)
# =============================================================================


@math_command(
    name="interp1d",
    category="interpolate",
    description="1D interpolation (legacy, use make_interp_spline for new code)",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "x_new", "help": "X points to interpolate at, comma-separated"},
        {
            "name": "--kind",
            "default": "linear",
            "help": "Kind: linear, nearest, zero, slinear, quadratic, cubic, previous, next",
        },
    ],
)
def cmd_interp1d(x: str, y: str, x_new: str, kind: str = "linear") -> dict:
    """Perform 1D interpolation."""
    from scipy.interpolate import interp1d

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    x_new_arr = parse_array(x_new)

    f = interp1d(x_arr, y_arr, kind=kind)
    result = f(x_new_arr)

    return {"result": result.tolist()}


@math_command(
    name="CubicSpline",
    category="interpolate",
    description="Cubic spline interpolation",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "x_new", "help": "X points to interpolate at, comma-separated"},
        {
            "name": "--bc_type",
            "default": "not-a-knot",
            "help": "Boundary condition: not-a-knot, periodic, clamped, natural",
        },
        {"name": "--extrapolate", "action": "store_true", "help": "Allow extrapolation"},
    ],
)
def cmd_CubicSpline(
    x: str, y: str, x_new: str, bc_type: str = "not-a-knot", extrapolate: bool = False
) -> dict:
    """Perform cubic spline interpolation."""
    from scipy.interpolate import CubicSpline

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    x_new_arr = parse_array(x_new)

    cs = CubicSpline(x_arr, y_arr, bc_type=bc_type, extrapolate=extrapolate)
    result = cs(x_new_arr)

    return {"result": result.tolist()}


@math_command(
    name="PchipInterpolator",
    category="interpolate",
    description="PCHIP monotonic cubic interpolation",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "x_new", "help": "X points to interpolate at, comma-separated"},
        {"name": "--extrapolate", "action": "store_true", "help": "Allow extrapolation"},
    ],
)
def cmd_PchipInterpolator(x: str, y: str, x_new: str, extrapolate: bool = False) -> dict:
    """Perform PCHIP monotonic interpolation."""
    from scipy.interpolate import PchipInterpolator

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    x_new_arr = parse_array(x_new)

    pchip = PchipInterpolator(x_arr, y_arr, extrapolate=extrapolate)
    result = pchip(x_new_arr)

    return {"result": result.tolist()}


@math_command(
    name="Akima1DInterpolator",
    category="interpolate",
    description="Akima interpolation (avoids oscillation)",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "x_new", "help": "X points to interpolate at, comma-separated"},
    ],
)
def cmd_Akima1DInterpolator(x: str, y: str, x_new: str) -> dict:
    """Perform Akima interpolation."""
    from scipy.interpolate import Akima1DInterpolator

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    x_new_arr = parse_array(x_new)

    akima = Akima1DInterpolator(x_arr, y_arr)
    result = akima(x_new_arr)

    return {"result": result.tolist()}


@math_command(
    name="BSpline",
    category="interpolate",
    description="Evaluate B-spline from knots and coefficients",
    args=[
        {"name": "t", "help": "Knot vector, comma-separated"},
        {"name": "c", "help": "B-spline coefficients, comma-separated"},
        {"name": "k", "help": "Spline degree"},
        {"name": "x_new", "help": "X points to evaluate at, comma-separated"},
        {"name": "--extrapolate", "action": "store_true", "help": "Allow extrapolation"},
    ],
)
def cmd_BSpline(t: str, c: str, k: str, x_new: str, extrapolate: bool = False) -> dict:
    """Evaluate B-spline."""
    from scipy.interpolate import BSpline

    t_arr = parse_array(t)
    c_arr = parse_array(c)
    x_new_arr = parse_array(x_new)

    bspl = BSpline(t_arr, c_arr, int(k), extrapolate=extrapolate)
    result = bspl(x_new_arr)

    return {"result": result.tolist()}


@math_command(
    name="make_interp_spline",
    category="interpolate",
    description="Construct interpolating B-spline",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "x_new", "help": "X points to interpolate at, comma-separated"},
        {"name": "--k", "type": int, "default": 3, "help": "Spline degree (default: 3, cubic)"},
    ],
)
def cmd_make_interp_spline(x: str, y: str, x_new: str, k: int = 3) -> dict:
    """Construct and evaluate interpolating B-spline."""
    from scipy.interpolate import make_interp_spline

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    x_new_arr = parse_array(x_new)

    bspl = make_interp_spline(x_arr, y_arr, k=k)
    result = bspl(x_new_arr)

    return {
        "result": result.tolist(),
        "knots": bspl.t.tolist(),
        "coeffs": bspl.c.tolist(),
        "degree": bspl.k,
    }


@math_command(
    name="splrep",
    category="interpolate",
    description="Find B-spline representation of 1D curve",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "--k", "type": int, "default": 3, "help": "Spline degree"},
        {
            "name": "--s",
            "type": float,
            "default": 0,
            "help": "Smoothing factor (0 = interpolating)",
        },
    ],
)
def cmd_splrep(x: str, y: str, k: int = 3, s: float = 0) -> dict:
    """Find B-spline representation (tck tuple)."""
    from scipy.interpolate import splrep

    x_arr = parse_array(x)
    y_arr = parse_array(y)

    tck = splrep(x_arr, y_arr, k=k, s=s)

    return {"t": tck[0].tolist(), "c": tck[1].tolist(), "k": tck[2]}


@math_command(
    name="splev",
    category="interpolate",
    description="Evaluate B-spline from tck representation",
    args=[
        {"name": "x_new", "help": "X points to evaluate at, comma-separated"},
        {"name": "t", "help": "Knot vector, comma-separated"},
        {"name": "c", "help": "Coefficients, comma-separated"},
        {"name": "k", "help": "Spline degree"},
        {"name": "--der", "type": int, "default": 0, "help": "Derivative order"},
    ],
)
def cmd_splev(x_new: str, t: str, c: str, k: str, der: int = 0) -> dict:
    """Evaluate B-spline at points."""
    from scipy.interpolate import splev

    x_new_arr = parse_array(x_new)
    t_arr = parse_array(t)
    c_arr = parse_array(c)

    tck = (t_arr, c_arr, int(k))
    result = splev(x_new_arr, tck, der=der)

    return {"result": result.tolist() if hasattr(result, "tolist") else [result]}


@math_command(
    name="splint",
    category="interpolate",
    description="Evaluate definite integral of B-spline",
    args=[
        {"name": "a", "help": "Lower bound"},
        {"name": "b", "help": "Upper bound"},
        {"name": "t", "help": "Knot vector, comma-separated"},
        {"name": "c", "help": "Coefficients, comma-separated"},
        {"name": "k", "help": "Spline degree"},
    ],
)
def cmd_splint(a: str, b: str, t: str, c: str, k: str) -> dict:
    """Compute definite integral of B-spline."""
    from scipy.interpolate import splint

    t_arr = parse_array(t)
    c_arr = parse_array(c)

    tck = (t_arr, c_arr, int(k))
    result = splint(float(a), float(b), tck)

    return {"result": float(result)}


@math_command(
    name="splder",
    category="interpolate",
    description="Compute B-spline representation of derivative",
    args=[
        {"name": "t", "help": "Knot vector, comma-separated"},
        {"name": "c", "help": "Coefficients, comma-separated"},
        {"name": "k", "help": "Spline degree"},
        {"name": "--n", "type": int, "default": 1, "help": "Derivative order"},
    ],
)
def cmd_splder(t: str, c: str, k: str, n: int = 1) -> dict:
    """Compute derivative of B-spline."""
    from scipy.interpolate import splder

    t_arr = parse_array(t)
    c_arr = parse_array(c)

    tck = (t_arr, c_arr, int(k))
    tck_der = splder(tck, n=n)

    return {"t": tck_der[0].tolist(), "c": tck_der[1].tolist(), "k": tck_der[2]}


@math_command(
    name="sproot",
    category="interpolate",
    description="Find roots of cubic B-spline",
    args=[
        {"name": "t", "help": "Knot vector, comma-separated"},
        {"name": "c", "help": "Coefficients, comma-separated"},
        {"name": "k", "help": "Spline degree (must be 3)"},
    ],
)
def cmd_sproot(t: str, c: str, k: str) -> dict:
    """Find roots of cubic B-spline."""
    from scipy.interpolate import sproot

    t_arr = parse_array(t)
    c_arr = parse_array(c)

    tck = (t_arr, c_arr, int(k))
    roots = sproot(tck)

    return {"roots": roots.tolist()}


@math_command(
    name="UnivariateSpline",
    category="interpolate",
    description="Smoothing univariate spline",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "x_new", "help": "X points to evaluate at, comma-separated"},
        {"name": "--k", "type": int, "default": 3, "help": "Spline degree"},
        {"name": "--s", "type": float, "default": None, "help": "Smoothing factor"},
    ],
)
def cmd_UnivariateSpline(x: str, y: str, x_new: str, k: int = 3, s: float = None) -> dict:
    """Fit and evaluate smoothing spline."""
    from scipy.interpolate import UnivariateSpline

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    x_new_arr = parse_array(x_new)

    spl = UnivariateSpline(x_arr, y_arr, k=k, s=s)
    result = spl(x_new_arr)

    return {
        "result": result.tolist(),
        "knots": spl.get_knots().tolist(),
        "coeffs": spl.get_coeffs().tolist(),
        "residual": float(spl.get_residual()),
    }


@math_command(
    name="InterpolatedUnivariateSpline",
    category="interpolate",
    description="Interpolating univariate spline (passes through all points)",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "x_new", "help": "X points to evaluate at, comma-separated"},
        {"name": "--k", "type": int, "default": 3, "help": "Spline degree"},
    ],
)
def cmd_InterpolatedUnivariateSpline(x: str, y: str, x_new: str, k: int = 3) -> dict:
    """Fit and evaluate interpolating spline."""
    from scipy.interpolate import InterpolatedUnivariateSpline

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    x_new_arr = parse_array(x_new)

    spl = InterpolatedUnivariateSpline(x_arr, y_arr, k=k)
    result = spl(x_new_arr)

    return {
        "result": result.tolist(),
        "knots": spl.get_knots().tolist(),
        "coeffs": spl.get_coeffs().tolist(),
    }


@math_command(
    name="LSQUnivariateSpline",
    category="interpolate",
    description="Least-squares univariate spline with specified knots",
    args=[
        {"name": "x", "help": "X data points, comma-separated"},
        {"name": "y", "help": "Y data points, comma-separated"},
        {"name": "t", "help": "Interior knots, comma-separated"},
        {"name": "x_new", "help": "X points to evaluate at, comma-separated"},
        {"name": "--k", "type": int, "default": 3, "help": "Spline degree"},
    ],
)
def cmd_LSQUnivariateSpline(x: str, y: str, t: str, x_new: str, k: int = 3) -> dict:
    """Fit and evaluate least-squares spline."""
    from scipy.interpolate import LSQUnivariateSpline

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    t_arr = parse_array(t)
    x_new_arr = parse_array(x_new)

    spl = LSQUnivariateSpline(x_arr, y_arr, t_arr, k=k)
    result = spl(x_new_arr)

    return {
        "result": result.tolist(),
        "knots": spl.get_knots().tolist(),
        "coeffs": spl.get_coeffs().tolist(),
        "residual": float(spl.get_residual()),
    }


@math_command(
    name="RectBivariateSpline",
    category="interpolate",
    description="Bivariate spline on a rectangular mesh",
    args=[
        {"name": "x", "help": "X grid coordinates, comma-separated"},
        {"name": "y", "help": "Y grid coordinates, comma-separated"},
        {"name": "z", "help": "Z values on grid, semicolon-separated rows"},
        {"name": "x_new", "help": "X points to evaluate at, comma-separated"},
        {"name": "y_new", "help": "Y points to evaluate at, comma-separated"},
        {"name": "--kx", "type": int, "default": 3, "help": "X spline degree"},
        {"name": "--ky", "type": int, "default": 3, "help": "Y spline degree"},
    ],
)
def cmd_RectBivariateSpline(
    x: str, y: str, z: str, x_new: str, y_new: str, kx: int = 3, ky: int = 3
) -> dict:
    """Fit and evaluate 2D spline on rectangular grid."""
    import numpy as np
    from scipy.interpolate import RectBivariateSpline

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    x_new_arr = parse_array(x_new)
    y_new_arr = parse_array(y_new)

    # Parse z: "1,2,3;4,5,6" -> [[1,2,3], [4,5,6]]
    z_arr = np.array([parse_array(row) for row in z.split(";")])

    spl = RectBivariateSpline(x_arr, y_arr, z_arr, kx=kx, ky=ky)
    result = spl(x_new_arr, y_new_arr)

    return {"result": result.tolist()}


@math_command(
    name="griddata",
    category="interpolate",
    description="Interpolate unstructured N-D data",
    args=[
        {"name": "points", "help": "Data point coordinates, e.g., '0,0;1,0;0,1' for 2D"},
        {"name": "values", "help": "Data values at points, comma-separated"},
        {"name": "xi", "help": "Points to interpolate at, e.g., '0.5,0.5;0.25,0.25'"},
        {"name": "--method", "default": "linear", "help": "Method: linear, nearest, cubic"},
    ],
)
def cmd_griddata(points: str, values: str, xi: str, method: str = "linear") -> dict:
    """Interpolate unstructured data."""
    import numpy as np
    from scipy.interpolate import griddata

    # Parse points: "0,0;1,0;0,1" -> [[0,0], [1,0], [0,1]]
    points_arr = np.array([parse_array(row) for row in points.split(";")])
    values_arr = parse_array(values)
    xi_arr = np.array([parse_array(row) for row in xi.split(";")])

    result = griddata(points_arr, values_arr, xi_arr, method=method)

    return {"result": result.tolist()}


@math_command(
    name="NearestNDInterpolator",
    category="interpolate",
    description="Nearest-neighbor interpolation in N dimensions",
    args=[
        {"name": "points", "help": "Data point coordinates, e.g., '0,0;1,0;0,1' for 2D"},
        {"name": "values", "help": "Data values at points, comma-separated"},
        {"name": "xi", "help": "Points to interpolate at, e.g., '0.5,0.5;0.25,0.25'"},
    ],
)
def cmd_NearestNDInterpolator(points: str, values: str, xi: str) -> dict:
    """Perform nearest-neighbor interpolation."""
    import numpy as np
    from scipy.interpolate import NearestNDInterpolator

    points_arr = np.array([parse_array(row) for row in points.split(";")])
    values_arr = parse_array(values)
    xi_arr = np.array([parse_array(row) for row in xi.split(";")])

    interp = NearestNDInterpolator(points_arr, values_arr)
    result = interp(xi_arr)

    return {"result": result.tolist()}


@math_command(
    name="LinearNDInterpolator",
    category="interpolate",
    description="Piecewise linear interpolation in N dimensions",
    args=[
        {"name": "points", "help": "Data point coordinates, e.g., '0,0;1,0;0,1' for 2D"},
        {"name": "values", "help": "Data values at points, comma-separated"},
        {"name": "xi", "help": "Points to interpolate at, e.g., '0.5,0.5;0.25,0.25'"},
    ],
)
def cmd_LinearNDInterpolator(points: str, values: str, xi: str) -> dict:
    """Perform piecewise linear interpolation in N-D."""
    import numpy as np
    from scipy.interpolate import LinearNDInterpolator

    points_arr = np.array([parse_array(row) for row in points.split(";")])
    values_arr = parse_array(values)
    xi_arr = np.array([parse_array(row) for row in xi.split(";")])

    interp = LinearNDInterpolator(points_arr, values_arr)
    result = interp(xi_arr)

    return {"result": result.tolist()}


@math_command(
    name="CloughTocher2DInterpolator",
    category="interpolate",
    description="Clough-Tocher cubic interpolation in 2D",
    args=[
        {"name": "points", "help": "Data point coordinates, e.g., '0,0;1,0;0,1;1,1'"},
        {"name": "values", "help": "Data values at points, comma-separated"},
        {"name": "xi", "help": "Points to interpolate at, e.g., '0.5,0.5;0.25,0.75'"},
    ],
)
def cmd_CloughTocher2DInterpolator(points: str, values: str, xi: str) -> dict:
    """Perform Clough-Tocher cubic interpolation in 2D."""
    import numpy as np
    from scipy.interpolate import CloughTocher2DInterpolator

    points_arr = np.array([parse_array(row) for row in points.split(";")])
    values_arr = parse_array(values)
    xi_arr = np.array([parse_array(row) for row in xi.split(";")])

    interp = CloughTocher2DInterpolator(points_arr, values_arr)
    result = interp(xi_arr)

    return {"result": result.tolist()}


@math_command(
    name="RBFInterpolator",
    category="interpolate",
    description="Radial basis function interpolation",
    args=[
        {"name": "y", "help": "Data point coordinates, e.g., '0,0;1,0;0,1' for 2D"},
        {"name": "d", "help": "Data values at points, comma-separated"},
        {"name": "x", "help": "Points to interpolate at, e.g., '0.5,0.5;0.25,0.25'"},
        {
            "name": "--kernel",
            "default": "thin_plate_spline",
            "help": "Kernel: linear, thin_plate_spline, cubic, quintic, multiquadric, inverse_multiquadric, inverse_quadratic, gaussian",
        },
        {"name": "--smoothing", "type": float, "default": 0.0, "help": "Smoothing parameter"},
    ],
)
def cmd_RBFInterpolator(
    y: str, d: str, x: str, kernel: str = "thin_plate_spline", smoothing: float = 0.0
) -> dict:
    """Perform RBF interpolation."""
    import numpy as np
    from scipy.interpolate import RBFInterpolator

    y_arr = np.array([parse_array(row) for row in y.split(";")])
    d_arr = parse_array(d)
    x_arr = np.array([parse_array(row) for row in x.split(";")])

    interp = RBFInterpolator(y_arr, d_arr, kernel=kernel, smoothing=smoothing)
    result = interp(x_arr)

    return {"result": result.tolist()}


# =============================================================================
# LINALG CATEGORY (51 functions)
# =============================================================================


@math_command(
    name="scipy_solve",
    category="linalg",
    description="Solve the linear system A @ x = b for x",
    args=[
        {"name": "A", "help": "Coefficient matrix, e.g., '[[1,2],[3,4]]'"},
        {"name": "b", "help": "Right-hand side vector, e.g., '1,2'"},
    ],
)
def cmd_scipy_solve(A: str, b: str) -> dict:
    """Solve linear system Ax = b."""
    from scipy.linalg import solve

    M = parse_matrix(A)
    v = parse_array(b)
    r = solve(M, v)
    return {"result": r.tolist()}


@math_command(
    name="solve_triangular",
    category="linalg",
    description="Solve a triangular linear system A @ x = b",
    args=[
        {"name": "A", "help": "Triangular coefficient matrix"},
        {"name": "b", "help": "Right-hand side vector"},
        {
            "name": "--lower",
            "action": "store_true",
            "help": "A is lower triangular (default: upper)",
        },
    ],
)
def cmd_solve_triangular(A: str, b: str, lower: bool = False) -> dict:
    """Solve triangular system."""
    from scipy.linalg import solve_triangular

    M = parse_matrix(A)
    v = parse_array(b)
    r = solve_triangular(M, v, lower=lower)
    return {"result": r.tolist()}


@math_command(
    name="solve_banded",
    category="linalg",
    description="Solve a banded linear system",
    args=[
        {"name": "l_and_u", "help": "Number of lower and upper diagonals, e.g., '1,1'"},
        {"name": "ab", "help": "Banded matrix in compact form"},
        {"name": "b", "help": "Right-hand side vector"},
    ],
)
def cmd_solve_banded(l_and_u: str, ab: str, b: str) -> dict:
    """Solve banded system."""
    from scipy.linalg import solve_banded

    lu = parse_array(l_and_u)
    ab_mat = parse_matrix(ab)
    v = parse_array(b)
    r = solve_banded((int(lu[0]), int(lu[1])), ab_mat, v)
    return {"result": r.tolist()}


@math_command(
    name="solveh_banded",
    category="linalg",
    description="Solve a Hermitian positive-definite banded system",
    args=[
        {"name": "ab", "help": "Banded matrix in compact form"},
        {"name": "b", "help": "Right-hand side vector"},
        {"name": "--lower", "action": "store_true", "help": "ab contains lower band"},
    ],
)
def cmd_solveh_banded(ab: str, b: str, lower: bool = False) -> dict:
    """Solve Hermitian banded system."""
    from scipy.linalg import solveh_banded

    ab_mat = parse_matrix(ab)
    v = parse_array(b)
    r = solveh_banded(ab_mat, v, lower=lower)
    return {"result": r.tolist()}


@math_command(
    name="cho_solve",
    category="linalg",
    description="Solve a linear system using Cholesky factorization",
    args=[
        {"name": "c", "help": "Cholesky factor (from cho_factor)"},
        {"name": "b", "help": "Right-hand side vector"},
        {"name": "--lower", "action": "store_true", "help": "c is lower triangular"},
    ],
)
def cmd_cho_solve(c: str, b: str, lower: bool = False) -> dict:
    """Solve using Cholesky factorization."""
    from scipy.linalg import cho_solve

    c_mat = parse_matrix(c)
    v = parse_array(b)
    r = cho_solve((c_mat, lower), v)
    return {"result": r.tolist()}


@math_command(
    name="lu_solve",
    category="linalg",
    description="Solve a linear system using LU factorization",
    args=[
        {"name": "lu", "help": "LU factored matrix (from lu_factor)"},
        {"name": "piv", "help": "Pivot indices"},
        {"name": "b", "help": "Right-hand side vector"},
    ],
)
def cmd_lu_solve(lu: str, piv: str, b: str) -> dict:
    """Solve using LU factorization."""
    import numpy as np
    from scipy.linalg import lu_solve

    lu_mat = parse_matrix(lu)
    piv_arr = parse_array(piv).astype(np.int32)
    v = parse_array(b)
    r = lu_solve((lu_mat, piv_arr), v)
    return {"result": r.tolist()}


@math_command(
    name="scipy_lu",
    category="linalg",
    description="Compute LU decomposition with pivoting: P @ L @ U = A",
    args=[
        {"name": "A", "help": "Input matrix"},
        {
            "name": "--permute_l",
            "action": "store_true",
            "help": "Return P @ L instead of separate P, L",
        },
    ],
)
def cmd_scipy_lu(A: str, permute_l: bool = False) -> dict:
    """Compute LU decomposition."""
    from scipy.linalg import lu

    M = parse_matrix(A)
    if permute_l:
        pl, u = lu(M, permute_l=True)
        return {"PL": pl.tolist(), "U": u.tolist()}
    else:
        p, l, u = lu(M, permute_l=False)
        return {"P": p.tolist(), "L": l.tolist(), "U": u.tolist()}


@math_command(
    name="lu_factor",
    category="linalg",
    description="Compute LU factorization for use with lu_solve",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_lu_factor(A: str) -> dict:
    """Compute LU factorization."""
    from scipy.linalg import lu_factor

    M = parse_matrix(A)
    lu_mat, piv = lu_factor(M)
    return {"lu": lu_mat.tolist(), "piv": piv.tolist()}


@math_command(
    name="scipy_qr",
    category="linalg",
    description="Compute QR decomposition: A = Q @ R",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--mode", "default": "full", "help": "Mode: full, r, economic, raw"},
    ],
)
def cmd_scipy_qr(A: str, mode: str = "full") -> dict:
    """Compute QR decomposition."""
    from scipy.linalg import qr

    M = parse_matrix(A)
    result = qr(M, mode=mode)
    if mode == "r":
        return {"R": result.tolist()}
    elif mode == "raw":
        h, tau = result
        return {"H": h.tolist(), "tau": tau.tolist()}
    else:
        q, r = result
        return {"Q": q.tolist(), "R": r.tolist()}


@math_command(
    name="qr_multiply",
    category="linalg",
    description="Multiply Q from QR decomposition with a matrix",
    args=[
        {"name": "a", "help": "Matrix A from QR factorization"},
        {"name": "c", "help": "Matrix to multiply"},
        {"name": "--mode", "default": "left", "help": "Mode: left or right"},
    ],
)
def cmd_qr_multiply(a: str, c: str, mode: str = "left") -> dict:
    """Multiply Q with matrix."""
    from scipy.linalg import qr_multiply

    A = parse_matrix(a)
    C = parse_matrix(c)
    result, r = qr_multiply(A, C, mode=mode)
    return {"result": result.tolist(), "R": r.tolist()}


@math_command(
    name="rq",
    category="linalg",
    description="Compute RQ decomposition: A = R @ Q",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--mode", "default": "full", "help": "Mode: full, r, economic"},
    ],
)
def cmd_rq(A: str, mode: str = "full") -> dict:
    """Compute RQ decomposition."""
    from scipy.linalg import rq

    M = parse_matrix(A)
    result = rq(M, mode=mode)
    if mode == "r":
        return {"R": result.tolist()}
    else:
        r, q = result
        return {"R": r.tolist(), "Q": q.tolist()}


@math_command(
    name="scipy_svd",
    category="linalg",
    description="Compute singular value decomposition: A = U @ S @ Vh",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--full_matrices", "action": "store_true", "help": "Compute full-size U and Vh"},
    ],
)
def cmd_scipy_svd(A: str, full_matrices: bool = False) -> dict:
    """Compute SVD."""
    from scipy.linalg import svd

    M = parse_matrix(A)
    u, s, vh = svd(M, full_matrices=full_matrices)
    return {"U": u.tolist(), "s": s.tolist(), "Vh": vh.tolist()}


@math_command(
    name="svdvals",
    category="linalg",
    description="Compute singular values only",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_svdvals(A: str) -> dict:
    """Compute singular values."""
    from scipy.linalg import svdvals

    M = parse_matrix(A)
    s = svdvals(M)
    return {"result": s.tolist()}


@math_command(
    name="diagsvd",
    category="linalg",
    description="Construct diagonal matrix from singular values",
    args=[
        {"name": "s", "help": "Singular values, comma-separated"},
        {"name": "M", "help": "Number of rows"},
        {"name": "N", "help": "Number of columns"},
    ],
)
def cmd_diagsvd(s: str, M: str, N: str) -> dict:
    """Construct diagonal SVD matrix."""
    from scipy.linalg import diagsvd

    s_arr = parse_array(s)
    result = diagsvd(s_arr, int(M), int(N))
    return {"result": result.tolist()}


@math_command(
    name="orth",
    category="linalg",
    description="Construct orthonormal basis for column space of A",
    args=[
        {"name": "A", "help": "Input matrix"},
        {
            "name": "--rcond",
            "type": float,
            "default": None,
            "help": "Relative condition number cutoff",
        },
    ],
)
def cmd_orth(A: str, rcond: float = None) -> dict:
    """Compute orthonormal basis for column space."""
    from scipy.linalg import orth

    M = parse_matrix(A)
    kwargs = {} if rcond is None else {"rcond": rcond}
    result = orth(M, **kwargs)
    return {"result": result.tolist(), "rank": result.shape[1]}


@math_command(
    name="null_space",
    category="linalg",
    description="Construct orthonormal basis for null space of A",
    args=[
        {"name": "A", "help": "Input matrix"},
        {
            "name": "--rcond",
            "type": float,
            "default": None,
            "help": "Relative condition number cutoff",
        },
    ],
)
def cmd_null_space(A: str, rcond: float = None) -> dict:
    """Compute null space basis."""
    from scipy.linalg import null_space

    M = parse_matrix(A)
    kwargs = {} if rcond is None else {"rcond": rcond}
    result = null_space(M, **kwargs)
    return {"result": result.tolist(), "nullity": result.shape[1]}


@math_command(
    name="ldl",
    category="linalg",
    description="Compute LDL^T decomposition of a symmetric/Hermitian matrix",
    args=[
        {"name": "A", "help": "Symmetric/Hermitian matrix"},
        {"name": "--lower", "action": "store_true", "help": "Return lower triangular factor"},
    ],
)
def cmd_ldl(A: str, lower: bool = False) -> dict:
    """Compute LDL decomposition."""
    from scipy.linalg import ldl

    M = parse_matrix(A)
    l, d, perm = ldl(M, lower=lower)
    return {"L": l.tolist(), "D": d.tolist(), "perm": perm.tolist()}


@math_command(
    name="scipy_cholesky",
    category="linalg",
    description="Compute Cholesky decomposition: A = L @ L.H",
    args=[
        {"name": "A", "help": "Positive-definite matrix"},
        {
            "name": "--lower",
            "action": "store_true",
            "help": "Return lower triangular (default: upper)",
        },
    ],
)
def cmd_scipy_cholesky(A: str, lower: bool = False) -> dict:
    """Compute Cholesky decomposition."""
    from scipy.linalg import cholesky

    M = parse_matrix(A)
    result = cholesky(M, lower=lower)
    return {"result": result.tolist()}


@math_command(
    name="cholesky_banded",
    category="linalg",
    description="Cholesky decomposition of a banded Hermitian positive-definite matrix",
    args=[
        {"name": "ab", "help": "Banded matrix in compact form"},
        {"name": "--lower", "action": "store_true", "help": "ab contains lower band"},
    ],
)
def cmd_cholesky_banded(ab: str, lower: bool = False) -> dict:
    """Compute banded Cholesky decomposition."""
    from scipy.linalg import cholesky_banded

    ab_mat = parse_matrix(ab)
    result = cholesky_banded(ab_mat, lower=lower)
    return {"result": result.tolist()}


@math_command(
    name="cho_factor",
    category="linalg",
    description="Compute Cholesky factorization for use with cho_solve",
    args=[
        {"name": "A", "help": "Positive-definite matrix"},
        {"name": "--lower", "action": "store_true", "help": "Compute lower triangular"},
    ],
)
def cmd_cho_factor(A: str, lower: bool = False) -> dict:
    """Compute Cholesky factorization."""
    from scipy.linalg import cho_factor

    M = parse_matrix(A)
    c, low = cho_factor(M, lower=lower)
    return {"c": c.tolist(), "lower": low}


@math_command(
    name="scipy_eig",
    category="linalg",
    description="Compute eigenvalues and eigenvectors of a general matrix",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--left", "action": "store_true", "help": "Compute left eigenvectors"},
        {"name": "--right", "action": "store_true", "help": "Compute right eigenvectors (default)"},
    ],
)
def cmd_scipy_eig(A: str, left: bool = False, right: bool = True) -> dict:
    """Compute eigenvalues and eigenvectors."""
    import numpy as np
    from scipy.linalg import eig

    M = parse_matrix(A)
    result = eig(M, left=left, right=right)
    if left and right:
        w, vl, vr = result
        return {
            "eigenvalues": np.array(w).tolist(),
            "left_eigenvectors": vl.tolist(),
            "right_eigenvectors": vr.tolist(),
        }
    elif left:
        w, vl = result
        return {"eigenvalues": np.array(w).tolist(), "left_eigenvectors": vl.tolist()}
    else:
        w, vr = result
        return {"eigenvalues": np.array(w).tolist(), "eigenvectors": vr.tolist()}


@math_command(
    name="scipy_eigh",
    category="linalg",
    description="Compute eigenvalues and eigenvectors of a Hermitian/symmetric matrix",
    args=[
        {"name": "A", "help": "Hermitian/symmetric matrix"},
        {"name": "--lower", "action": "store_true", "help": "Use lower triangle"},
        {"name": "--eigvals_only", "action": "store_true", "help": "Only compute eigenvalues"},
    ],
)
def cmd_scipy_eigh(A: str, lower: bool = False, eigvals_only: bool = False) -> dict:
    """Compute eigenvalues/vectors of Hermitian matrix."""
    from scipy.linalg import eigh

    M = parse_matrix(A)
    result = eigh(M, lower=lower, eigvals_only=eigvals_only)
    if eigvals_only:
        return {"eigenvalues": result.tolist()}
    else:
        w, v = result
        return {"eigenvalues": w.tolist(), "eigenvectors": v.tolist()}


@math_command(
    name="scipy_eigvals",
    category="linalg",
    description="Compute eigenvalues of a general matrix",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_scipy_eigvals(A: str) -> dict:
    """Compute eigenvalues only."""
    import numpy as np
    from scipy.linalg import eigvals

    M = parse_matrix(A)
    w = eigvals(M)
    return {"result": np.array(w).tolist()}


@math_command(
    name="eigvalsh",
    category="linalg",
    description="Compute eigenvalues of a Hermitian/symmetric matrix",
    args=[
        {"name": "A", "help": "Hermitian/symmetric matrix"},
        {"name": "--lower", "action": "store_true", "help": "Use lower triangle"},
    ],
)
def cmd_eigvalsh(A: str, lower: bool = False) -> dict:
    """Compute eigenvalues of Hermitian matrix."""
    from scipy.linalg import eigvalsh

    M = parse_matrix(A)
    w = eigvalsh(M, lower=lower)
    return {"result": w.tolist()}


@math_command(
    name="schur",
    category="linalg",
    description="Compute Schur decomposition: A = Z @ T @ Z.H",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--output", "default": "real", "help": "Output form: real or complex"},
    ],
)
def cmd_schur(A: str, output: str = "real") -> dict:
    """Compute Schur decomposition."""
    from scipy.linalg import schur

    M = parse_matrix(A)
    t, z = schur(M, output=output)
    return {"T": t.tolist(), "Z": z.tolist()}


@math_command(
    name="rsf2csf",
    category="linalg",
    description="Convert real Schur form to complex Schur form",
    args=[
        {"name": "T", "help": "Schur form matrix"},
        {"name": "Z", "help": "Unitary matrix from Schur decomposition"},
    ],
)
def cmd_rsf2csf(T: str, Z: str) -> dict:
    """Convert real to complex Schur form."""
    from scipy.linalg import rsf2csf

    t_mat = parse_matrix(T)
    z_mat = parse_matrix(Z)
    t_c, z_c = rsf2csf(t_mat, z_mat)
    return {"T": t_c.tolist(), "Z": z_c.tolist()}


@math_command(
    name="hessenberg",
    category="linalg",
    description="Compute Hessenberg form: A = Q @ H @ Q.H",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--calc_q", "action": "store_true", "help": "Also compute Q"},
    ],
)
def cmd_hessenberg(A: str, calc_q: bool = False) -> dict:
    """Compute Hessenberg form."""
    from scipy.linalg import hessenberg

    M = parse_matrix(A)
    result = hessenberg(M, calc_q=calc_q)
    if calc_q:
        h, q = result
        return {"H": h.tolist(), "Q": q.tolist()}
    else:
        return {"H": result.tolist()}


@math_command(
    name="cdf2rdf",
    category="linalg",
    description="Convert complex diagonal form to real diagonal form",
    args=[
        {"name": "w", "help": "Complex eigenvalues, comma-separated"},
        {"name": "v", "help": "Complex eigenvector matrix"},
    ],
)
def cmd_cdf2rdf(w: str, v: str) -> dict:
    """Convert complex to real diagonal form."""
    import numpy as np
    from scipy.linalg import cdf2rdf

    # Parse complex eigenvalues
    w_arr = np.array([complex(x.strip()) for x in w.split(",")])
    v_mat = parse_matrix(v)
    wr, vr = cdf2rdf(w_arr, v_mat)
    return {"eigenvalues": wr.tolist(), "eigenvectors": vr.tolist()}


@math_command(
    name="scipy_det",
    category="linalg",
    description="Compute determinant of a matrix",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_scipy_det(A: str) -> dict:
    """Compute determinant."""
    from scipy.linalg import det

    M = parse_matrix(A)
    result = det(M)
    return {
        "result": float(result)
        if not isinstance(result, complex)
        else {"real": result.real, "imag": result.imag}
    }


@math_command(
    name="scipy_inv",
    category="linalg",
    description="Compute inverse of a matrix",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_scipy_inv(A: str) -> dict:
    """Compute matrix inverse."""
    from scipy.linalg import inv

    M = parse_matrix(A)
    result = inv(M)
    return {"result": result.tolist()}


@math_command(
    name="scipy_pinv",
    category="linalg",
    description="Compute Moore-Penrose pseudo-inverse",
    args=[
        {"name": "A", "help": "Input matrix"},
        {
            "name": "--rcond",
            "type": float,
            "default": None,
            "help": "Relative condition number cutoff",
        },
    ],
)
def cmd_scipy_pinv(A: str, rcond: float = None) -> dict:
    """Compute pseudo-inverse."""
    from scipy.linalg import pinv

    M = parse_matrix(A)
    kwargs = {} if rcond is None else {"rcond": rcond}
    result = pinv(M, **kwargs)
    return {"result": result.tolist()}


@math_command(
    name="pinvh",
    category="linalg",
    description="Compute pseudo-inverse of a Hermitian matrix",
    args=[
        {"name": "A", "help": "Hermitian matrix"},
        {
            "name": "--rcond",
            "type": float,
            "default": None,
            "help": "Relative condition number cutoff",
        },
    ],
)
def cmd_pinvh(A: str, rcond: float = None) -> dict:
    """Compute Hermitian pseudo-inverse."""
    from scipy.linalg import pinvh

    M = parse_matrix(A)
    kwargs = {} if rcond is None else {"rcond": rcond}
    result = pinvh(M, **kwargs)
    return {"result": result.tolist()}


@math_command(
    name="scipy_norm",
    category="linalg",
    description="Compute matrix or vector norm",
    args=[
        {"name": "A", "help": "Input matrix or vector"},
        {"name": "--ord", "default": None, "help": "Norm order: fro, nuc, 1, 2, inf, -1, -2, -inf"},
    ],
)
def cmd_scipy_norm(A: str, ord: str = None) -> dict:
    """Compute norm."""
    import numpy as np
    from scipy.linalg import norm

    M = parse_matrix(A) if "," in A and "[" in A else parse_array(A)
    # Parse ord
    ord_val = None
    if ord:
        if ord == "fro":
            ord_val = "fro"
        elif ord == "nuc":
            ord_val = "nuc"
        elif ord == "inf":
            ord_val = np.inf
        elif ord == "-inf":
            ord_val = -np.inf
        else:
            ord_val = int(ord)
    result = norm(M, ord=ord_val)
    return {"result": float(result)}


@math_command(
    name="matrix_balance",
    category="linalg",
    description="Compute balanced matrix to improve eigenvalue accuracy",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--scale", "action": "store_true", "help": "Return scaling factors"},
        {"name": "--permute", "action": "store_true", "help": "Permute to isolate eigenvalues"},
    ],
)
def cmd_matrix_balance(A: str, scale: bool = True, permute: bool = True) -> dict:
    """Compute balanced matrix."""
    from scipy.linalg import matrix_balance

    M = parse_matrix(A)
    result = matrix_balance(M, scale=scale, permute=permute, separate=True)
    B, (scale_arr, perm) = result
    return {"B": B.tolist(), "scale": scale_arr.tolist(), "perm": perm.tolist()}


@math_command(
    name="expm",
    category="linalg",
    description="Compute matrix exponential: exp(A)",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_expm(A: str) -> dict:
    """Compute matrix exponential."""
    from scipy.linalg import expm

    M = parse_matrix(A)
    result = expm(M)
    return {"result": result.tolist()}


@math_command(
    name="logm",
    category="linalg",
    description="Compute matrix logarithm: log(A)",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_logm(A: str) -> dict:
    """Compute matrix logarithm."""
    from scipy.linalg import logm

    M = parse_matrix(A)
    result = logm(M)
    return {"result": result.tolist()}


@math_command(
    name="sqrtm",
    category="linalg",
    description="Compute matrix square root: sqrt(A)",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--disp", "action": "store_true", "help": "Display warning on poor condition"},
    ],
)
def cmd_sqrtm(A: str, disp: bool = False) -> dict:
    """Compute matrix square root."""
    from scipy.linalg import sqrtm

    M = parse_matrix(A)
    result = sqrtm(M, disp=disp)
    if disp:
        return {"result": result.tolist()}
    else:
        sqrt_m, errest = result
        return {"result": sqrt_m.tolist(), "errest": float(errest)}


@math_command(
    name="cosm",
    category="linalg",
    description="Compute matrix cosine: cos(A)",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_cosm(A: str) -> dict:
    """Compute matrix cosine."""
    from scipy.linalg import cosm

    M = parse_matrix(A)
    result = cosm(M)
    return {"result": result.tolist()}


@math_command(
    name="sinm",
    category="linalg",
    description="Compute matrix sine: sin(A)",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_sinm(A: str) -> dict:
    """Compute matrix sine."""
    from scipy.linalg import sinm

    M = parse_matrix(A)
    result = sinm(M)
    return {"result": result.tolist()}


@math_command(
    name="tanm",
    category="linalg",
    description="Compute matrix tangent: tan(A)",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_tanm(A: str) -> dict:
    """Compute matrix tangent."""
    from scipy.linalg import tanm

    M = parse_matrix(A)
    result = tanm(M)
    return {"result": result.tolist()}


@math_command(
    name="coshm",
    category="linalg",
    description="Compute matrix hyperbolic cosine: cosh(A)",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_coshm(A: str) -> dict:
    """Compute matrix hyperbolic cosine."""
    from scipy.linalg import coshm

    M = parse_matrix(A)
    result = coshm(M)
    return {"result": result.tolist()}


@math_command(
    name="sinhm",
    category="linalg",
    description="Compute matrix hyperbolic sine: sinh(A)",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_sinhm(A: str) -> dict:
    """Compute matrix hyperbolic sine."""
    from scipy.linalg import sinhm

    M = parse_matrix(A)
    result = sinhm(M)
    return {"result": result.tolist()}


@math_command(
    name="tanhm",
    category="linalg",
    description="Compute matrix hyperbolic tangent: tanh(A)",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_tanhm(A: str) -> dict:
    """Compute matrix hyperbolic tangent."""
    from scipy.linalg import tanhm

    M = parse_matrix(A)
    result = tanhm(M)
    return {"result": result.tolist()}


@math_command(
    name="signm",
    category="linalg",
    description="Compute matrix sign function",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "--disp", "action": "store_true", "help": "Display warning on poor condition"},
    ],
)
def cmd_signm(A: str, disp: bool = False) -> dict:
    """Compute matrix sign function."""
    from scipy.linalg import signm

    M = parse_matrix(A)
    # signm always returns just the sign matrix; disp controls whether it prints warnings
    result = signm(M, disp=disp)
    return {"result": result.tolist()}


@math_command(
    name="funm",
    category="linalg",
    description="Evaluate a matrix function",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "func", "help": "Function to apply, e.g., 'np.exp' or 'np.cos'"},
    ],
)
def cmd_funm(A: str, func: str) -> dict:
    """Evaluate general matrix function."""
    import numpy as np
    from scipy.linalg import funm

    M = parse_matrix(A)
    # Parse function name
    f = eval(func, {"np": np, "numpy": np})
    result = funm(M, f)
    return {"result": result.tolist()}


@math_command(
    name="expm_frechet",
    category="linalg",
    description="Compute Frechet derivative of matrix exponential",
    args=[
        {"name": "A", "help": "Input matrix"},
        {"name": "E", "help": "Direction matrix"},
        {"name": "--compute_expm", "action": "store_true", "help": "Also return expm(A)"},
    ],
)
def cmd_expm_frechet(A: str, E: str, compute_expm: bool = True) -> dict:
    """Compute Frechet derivative of matrix exponential."""
    from scipy.linalg import expm_frechet

    A_mat = parse_matrix(A)
    E_mat = parse_matrix(E)
    result = expm_frechet(A_mat, E_mat, compute_expm=compute_expm)
    if compute_expm:
        expm_A, expm_frechet_AE = result
        return {"expm_A": expm_A.tolist(), "expm_frechet_AE": expm_frechet_AE.tolist()}
    else:
        return {"expm_frechet_AE": result.tolist()}


@math_command(
    name="expm_cond",
    category="linalg",
    description="Compute relative condition number of matrix exponential",
    args=[{"name": "A", "help": "Input matrix"}],
)
def cmd_expm_cond(A: str) -> dict:
    """Compute condition number of matrix exponential."""
    from scipy.linalg import expm_cond

    M = parse_matrix(A)
    result = expm_cond(M)
    return {"result": float(result)}


@math_command(
    name="scipy_kron",
    category="linalg",
    description="Compute Kronecker product of two matrices",
    args=[{"name": "A", "help": "First matrix"}, {"name": "B", "help": "Second matrix"}],
)
def cmd_scipy_kron(A: str, B: str) -> dict:
    """Compute Kronecker product."""
    from scipy.linalg import kron

    A_mat = parse_matrix(A)
    B_mat = parse_matrix(B)
    result = kron(A_mat, B_mat)
    return {"result": result.tolist()}


@math_command(
    name="scipy_block_diag",
    category="linalg",
    description="Create block diagonal matrix from input arrays",
    args=[
        {"name": "arrays", "help": "Semicolon-separated matrices, e.g., '[[1,2],[3,4]];[[5,6]]'"}
    ],
)
def cmd_scipy_block_diag(arrays: str) -> dict:
    """Create block diagonal matrix."""
    from scipy.linalg import block_diag

    # Parse semicolon-separated matrices
    matrices = [parse_matrix(a.strip()) for a in arrays.split(";")]
    result = block_diag(*matrices)
    return {"result": result.tolist()}


@math_command(
    name="companion",
    category="linalg",
    description="Create companion matrix from polynomial coefficients",
    args=[{"name": "a", "help": "Polynomial coefficients (highest degree first), comma-separated"}],
)
def cmd_companion(a: str) -> dict:
    """Create companion matrix."""
    from scipy.linalg import companion

    a_arr = parse_array(a)
    result = companion(a_arr)
    return {"result": result.tolist()}


@math_command(
    name="helmert",
    category="linalg",
    description="Create Helmert matrix of order n",
    args=[
        {"name": "n", "help": "Order of the Helmert matrix"},
        {
            "name": "--full",
            "action": "store_true",
            "help": "Return full matrix (default: omit first row)",
        },
    ],
)
def cmd_helmert(n: str, full: bool = False) -> dict:
    """Create Helmert matrix."""
    from scipy.linalg import helmert

    result = helmert(int(n), full=full)
    return {"result": result.tolist()}


# =============================================================================
# STATS CATEGORY (86 functions total, 42 here - first half)
# =============================================================================


@math_command(
    name="describe",
    category="stats",
    description="Compute descriptive statistics for data",
    args=[{"name": "data", "help": "Comma-separated data values"}],
)
def cmd_describe(data: str) -> dict:
    """Compute descriptive statistics."""
    from scipy.stats import describe

    arr = parse_array(data)
    d = describe(arr)
    return {
        "result": {
            "nobs": d.nobs,
            "mean": float(d.mean),
            "variance": float(d.variance),
            "skewness": float(d.skewness),
            "kurtosis": float(d.kurtosis),
            "min": float(d.minmax[0]),
            "max": float(d.minmax[1]),
        }
    }


@math_command(
    name="moment",
    category="stats",
    description="Calculate the nth moment about the mean",
    args=[
        {"name": "data", "help": "Comma-separated data values"},
        {
            "name": "--order",
            "type": int,
            "default": 1,
            "help": "Order of central moment (default: 1)",
        },
    ],
)
def cmd_moment(data: str, order: int = 1) -> dict:
    """Calculate the nth central moment."""
    from scipy.stats import moment

    arr = parse_array(data)
    result = moment(arr, moment=order)
    return {"result": float(result)}


@math_command(
    name="skew",
    category="stats",
    description="Compute sample skewness of data",
    args=[
        {"name": "data", "help": "Comma-separated data values"},
        {"name": "--bias", "action": "store_true", "help": "Use biased estimator"},
    ],
)
def cmd_skew(data: str, bias: bool = False) -> dict:
    """Compute sample skewness."""
    from scipy.stats import skew

    arr = parse_array(data)
    result = skew(arr, bias=bias)
    return {"result": float(result)}


@math_command(
    name="kurtosis",
    category="stats",
    description="Compute sample kurtosis of data",
    args=[
        {"name": "data", "help": "Comma-separated data values"},
        {
            "name": "--fisher",
            "action": "store_true",
            "help": "Fisher's definition (normal ==> 0.0)",
        },
        {"name": "--bias", "action": "store_true", "help": "Use biased estimator"},
    ],
)
def cmd_kurtosis(data: str, fisher: bool = True, bias: bool = False) -> dict:
    """Compute sample kurtosis."""
    from scipy.stats import kurtosis

    arr = parse_array(data)
    result = kurtosis(arr, fisher=fisher, bias=bias)
    return {"result": float(result)}


@math_command(
    name="sem",
    category="stats",
    description="Compute standard error of the mean",
    args=[
        {"name": "data", "help": "Comma-separated data values"},
        {"name": "--ddof", "type": int, "default": 1, "help": "Degrees of freedom correction"},
    ],
)
def cmd_sem(data: str, ddof: int = 1) -> dict:
    """Compute standard error of the mean."""
    from scipy.stats import sem

    arr = parse_array(data)
    result = sem(arr, ddof=ddof)
    return {"result": float(result)}


@math_command(
    name="zscore",
    category="stats",
    description="Compute z-scores for data",
    args=[
        {"name": "data", "help": "Comma-separated data values"},
        {"name": "--ddof", "type": int, "default": 0, "help": "Degrees of freedom correction"},
    ],
)
def cmd_zscore(data: str, ddof: int = 0) -> dict:
    """Compute z-scores."""
    from scipy.stats import zscore

    arr = parse_array(data)
    result = zscore(arr, ddof=ddof)
    return {"result": result.tolist()}


@math_command(
    name="iqr",
    category="stats",
    description="Compute interquartile range",
    args=[
        {"name": "data", "help": "Comma-separated data values"},
        {"name": "--rng", "default": "25,75", "help": "Percentile range, e.g., '25,75'"},
    ],
)
def cmd_iqr(data: str, rng: str = "25,75") -> dict:
    """Compute interquartile range."""
    from scipy.stats import iqr

    arr = parse_array(data)
    rng_tuple = tuple(float(x) for x in rng.split(","))
    result = iqr(arr, rng=rng_tuple)
    return {"result": float(result)}


@math_command(
    name="median_abs_deviation",
    category="stats",
    description="Compute median absolute deviation",
    args=[
        {"name": "data", "help": "Comma-separated data values"},
        {"name": "--scale", "default": "normal", "help": "Scale factor ('normal' or numeric)"},
    ],
)
def cmd_median_abs_deviation(data: str, scale: str = "normal") -> dict:
    """Compute median absolute deviation."""
    from scipy.stats import median_abs_deviation

    arr = parse_array(data)
    try:
        scale_val = float(scale)
    except ValueError:
        scale_val = scale
    result = median_abs_deviation(arr, scale=scale_val)
    return {"result": float(result)}


@math_command(
    name="entropy",
    category="stats",
    description="Compute entropy of a distribution (given probabilities)",
    args=[
        {"name": "pk", "help": "Probability distribution (comma-separated, must sum to 1)"},
        {
            "name": "--qk",
            "default": None,
            "help": "Second distribution for relative entropy (KL divergence)",
        },
        {"name": "--base", "type": float, "default": None, "help": "Logarithm base (default: e)"},
    ],
)
def cmd_entropy(pk: str, qk: str = None, base: float = None) -> dict:
    """Compute Shannon entropy or KL divergence."""
    from scipy.stats import entropy

    pk_arr = parse_array(pk)
    qk_arr = parse_array(qk) if qk else None
    result = entropy(pk_arr, qk=qk_arr, base=base)
    return {"result": float(result)}


@math_command(
    name="differential_entropy",
    category="stats",
    description="Compute differential entropy of continuous data",
    args=[
        {"name": "data", "help": "Comma-separated data values"},
        {
            "name": "--method",
            "default": "auto",
            "help": "Estimation method: vasicek, van_es, ebrahimi, correa, auto",
        },
    ],
)
def cmd_differential_entropy(data: str, method: str = "auto") -> dict:
    """Compute differential entropy."""
    from scipy.stats import differential_entropy

    arr = parse_array(data)
    result = differential_entropy(arr, method=method)
    return {"result": float(result)}


@math_command(
    name="pearsonr",
    category="stats",
    description="Compute Pearson correlation coefficient and p-value",
    args=[
        {"name": "x", "help": "First variable (comma-separated)"},
        {"name": "y", "help": "Second variable (comma-separated)"},
    ],
)
def cmd_pearsonr(x: str, y: str) -> dict:
    """Compute Pearson correlation."""
    from scipy.stats import pearsonr

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    stat, pvalue = pearsonr(x_arr, y_arr)
    return {"result": {"correlation": float(stat), "pvalue": float(pvalue)}}


@math_command(
    name="spearmanr",
    category="stats",
    description="Compute Spearman rank correlation coefficient",
    args=[
        {"name": "x", "help": "First variable (comma-separated)"},
        {"name": "y", "help": "Second variable (comma-separated)"},
    ],
)
def cmd_spearmanr(x: str, y: str) -> dict:
    """Compute Spearman rank correlation."""
    from scipy.stats import spearmanr

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    result = spearmanr(x_arr, y_arr)
    return {"result": {"correlation": float(result.correlation), "pvalue": float(result.pvalue)}}


@math_command(
    name="kendalltau",
    category="stats",
    description="Compute Kendall's tau correlation coefficient",
    args=[
        {"name": "x", "help": "First variable (comma-separated)"},
        {"name": "y", "help": "Second variable (comma-separated)"},
    ],
)
def cmd_kendalltau(x: str, y: str) -> dict:
    """Compute Kendall's tau."""
    from scipy.stats import kendalltau

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    result = kendalltau(x_arr, y_arr)
    return {"result": {"correlation": float(result.correlation), "pvalue": float(result.pvalue)}}


@math_command(
    name="pointbiserialr",
    category="stats",
    description="Compute point biserial correlation (binary vs continuous)",
    args=[
        {"name": "x", "help": "Binary variable (0s and 1s, comma-separated)"},
        {"name": "y", "help": "Continuous variable (comma-separated)"},
    ],
)
def cmd_pointbiserialr(x: str, y: str) -> dict:
    """Compute point biserial correlation."""
    from scipy.stats import pointbiserialr

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    result = pointbiserialr(x_arr, y_arr)
    return {"result": {"correlation": float(result.correlation), "pvalue": float(result.pvalue)}}


@math_command(
    name="linregress",
    category="stats",
    description="Perform simple linear regression",
    args=[
        {"name": "x", "help": "Independent variable (comma-separated)"},
        {"name": "y", "help": "Dependent variable (comma-separated)"},
    ],
)
def cmd_linregress(x: str, y: str) -> dict:
    """Perform simple linear regression."""
    from scipy.stats import linregress

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    result = linregress(x_arr, y_arr)
    return {
        "result": {
            "slope": float(result.slope),
            "intercept": float(result.intercept),
            "rvalue": float(result.rvalue),
            "pvalue": float(result.pvalue),
            "stderr": float(result.stderr),
            "intercept_stderr": float(result.intercept_stderr),
        }
    }


@math_command(
    name="theilslopes",
    category="stats",
    description="Compute Theil-Sen slope estimator (robust regression)",
    args=[
        {"name": "y", "help": "Dependent variable (comma-separated)"},
        {
            "name": "--x",
            "default": None,
            "help": "Independent variable (optional, defaults to arange)",
        },
    ],
)
def cmd_theilslopes(y: str, x: str = None) -> dict:
    """Compute Theil-Sen slope estimator."""
    from scipy.stats import theilslopes

    y_arr = parse_array(y)
    x_arr = parse_array(x) if x else None
    result = theilslopes(y_arr, x=x_arr)
    return {
        "result": {
            "slope": float(result.slope),
            "intercept": float(result.intercept),
            "low_slope": float(result.low_slope),
            "high_slope": float(result.high_slope),
        }
    }


@math_command(
    name="siegelslopes",
    category="stats",
    description="Compute Siegel slope estimator (repeated medians)",
    args=[
        {"name": "y", "help": "Dependent variable (comma-separated)"},
        {
            "name": "--x",
            "default": None,
            "help": "Independent variable (optional, defaults to arange)",
        },
    ],
)
def cmd_siegelslopes(y: str, x: str = None) -> dict:
    """Compute Siegel slope estimator."""
    from scipy.stats import siegelslopes

    y_arr = parse_array(y)
    x_arr = parse_array(x) if x else None
    result = siegelslopes(y_arr, x=x_arr)
    return {"result": {"slope": float(result.slope), "intercept": float(result.intercept)}}


@math_command(
    name="ttest_1samp",
    category="stats",
    description="One-sample t-test for population mean",
    args=[
        {"name": "data", "help": "Sample data (comma-separated)"},
        {"name": "popmean", "help": "Expected population mean"},
    ],
)
def cmd_ttest_1samp(data: str, popmean: str) -> dict:
    """One-sample t-test."""
    from scipy.stats import ttest_1samp

    arr = parse_array(data)
    result = ttest_1samp(arr, float(popmean))
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="ttest_ind",
    category="stats",
    description="Two-sample independent t-test",
    args=[
        {"name": "a", "help": "First sample (comma-separated)"},
        {"name": "b", "help": "Second sample (comma-separated)"},
        {
            "name": "--equal_var",
            "action": "store_true",
            "help": "Assume equal variances (default: Welch's)",
        },
    ],
)
def cmd_ttest_ind(a: str, b: str, equal_var: bool = False) -> dict:
    """Two-sample independent t-test."""
    from scipy.stats import ttest_ind

    a_arr = parse_array(a)
    b_arr = parse_array(b)
    result = ttest_ind(a_arr, b_arr, equal_var=equal_var)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="ttest_rel",
    category="stats",
    description="Paired samples t-test",
    args=[
        {"name": "a", "help": "First sample (comma-separated)"},
        {"name": "b", "help": "Second sample (comma-separated)"},
    ],
)
def cmd_ttest_rel(a: str, b: str) -> dict:
    """Paired samples t-test."""
    from scipy.stats import ttest_rel

    a_arr = parse_array(a)
    b_arr = parse_array(b)
    result = ttest_rel(a_arr, b_arr)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="chisquare",
    category="stats",
    description="Chi-square test for goodness of fit",
    args=[
        {"name": "f_obs", "help": "Observed frequencies (comma-separated)"},
        {
            "name": "--f_exp",
            "default": None,
            "help": "Expected frequencies (optional, defaults to uniform)",
        },
    ],
)
def cmd_chisquare(f_obs: str, f_exp: str = None) -> dict:
    """Chi-square goodness of fit test."""
    from scipy.stats import chisquare

    obs = parse_array(f_obs)
    exp = parse_array(f_exp) if f_exp else None
    result = chisquare(obs, f_exp=exp)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="ks_1samp",
    category="stats",
    description="One-sample Kolmogorov-Smirnov test",
    args=[
        {"name": "data", "help": "Sample data (comma-separated)"},
        {"name": "cdf", "help": "CDF name: norm, expon, uniform, etc."},
    ],
)
def cmd_ks_1samp(data: str, cdf: str) -> dict:
    """One-sample Kolmogorov-Smirnov test."""
    from scipy import stats
    from scipy.stats import ks_1samp

    arr = parse_array(data)
    dist = getattr(stats, cdf)
    result = ks_1samp(arr, dist.cdf)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="ks_2samp",
    category="stats",
    description="Two-sample Kolmogorov-Smirnov test",
    args=[
        {"name": "data1", "help": "First sample (comma-separated)"},
        {"name": "data2", "help": "Second sample (comma-separated)"},
    ],
)
def cmd_ks_2samp(data1: str, data2: str) -> dict:
    """Two-sample Kolmogorov-Smirnov test."""
    from scipy.stats import ks_2samp

    arr1 = parse_array(data1)
    arr2 = parse_array(data2)
    result = ks_2samp(arr1, arr2)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="kstest",
    category="stats",
    description="Kolmogorov-Smirnov test against named distribution",
    args=[
        {"name": "data", "help": "Sample data (comma-separated)"},
        {"name": "cdf", "help": "Distribution name: norm, expon, uniform, etc."},
        {"name": "--args", "default": "", "help": "Distribution parameters (comma-separated)"},
    ],
)
def cmd_kstest(data: str, cdf: str, args: str = "") -> dict:
    """Kolmogorov-Smirnov test against named distribution."""
    from scipy.stats import kstest

    arr = parse_array(data)
    dist_args = tuple(float(x) for x in args.split(",")) if args else ()
    result = kstest(arr, cdf, args=dist_args)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="anderson",
    category="stats",
    description="Anderson-Darling test for data from a distribution",
    args=[
        {"name": "data", "help": "Sample data (comma-separated)"},
        {
            "name": "--dist",
            "default": "norm",
            "help": "Distribution: norm, expon, logistic, gumbel, gumbel_l, gumbel_r, extreme1",
        },
    ],
)
def cmd_anderson(data: str, dist: str = "norm") -> dict:
    """Anderson-Darling test."""
    from scipy.stats import anderson

    arr = parse_array(data)
    result = anderson(arr, dist=dist)
    return {
        "result": {
            "statistic": float(result.statistic),
            "critical_values": list(result.critical_values),
            "significance_level": list(result.significance_level),
        }
    }


@math_command(
    name="normaltest",
    category="stats",
    description="Test whether sample differs from normal distribution",
    args=[{"name": "data", "help": "Sample data (comma-separated)"}],
)
def cmd_normaltest(data: str) -> dict:
    """Test for normality using D'Agostino and Pearson's test."""
    from scipy.stats import normaltest

    arr = parse_array(data)
    result = normaltest(arr)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="shapiro",
    category="stats",
    description="Shapiro-Wilk test for normality",
    args=[{"name": "data", "help": "Sample data (comma-separated)"}],
)
def cmd_shapiro(data: str) -> dict:
    """Shapiro-Wilk test for normality."""
    from scipy.stats import shapiro

    arr = parse_array(data)
    result = shapiro(arr)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="bartlett",
    category="stats",
    description="Bartlett's test for equal variances",
    args=[
        {"name": "sample1", "help": "First sample (comma-separated)"},
        {"name": "sample2", "help": "Second sample (comma-separated)"},
        {"name": "--sample3", "default": None, "help": "Third sample (optional)"},
    ],
)
def cmd_bartlett(sample1: str, sample2: str, sample3: str = None) -> dict:
    """Bartlett's test for equal variances."""
    from scipy.stats import bartlett

    samples = [parse_array(sample1), parse_array(sample2)]
    if sample3:
        samples.append(parse_array(sample3))
    result = bartlett(*samples)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="levene",
    category="stats",
    description="Levene's test for equal variances",
    args=[
        {"name": "sample1", "help": "First sample (comma-separated)"},
        {"name": "sample2", "help": "Second sample (comma-separated)"},
        {"name": "--sample3", "default": None, "help": "Third sample (optional)"},
        {"name": "--center", "default": "median", "help": "Center: mean, median, trimmed"},
    ],
)
def cmd_levene(sample1: str, sample2: str, sample3: str = None, center: str = "median") -> dict:
    """Levene's test for equal variances."""
    from scipy.stats import levene

    samples = [parse_array(sample1), parse_array(sample2)]
    if sample3:
        samples.append(parse_array(sample3))
    result = levene(*samples, center=center)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="fligner",
    category="stats",
    description="Fligner-Killeen test for equal variances",
    args=[
        {"name": "sample1", "help": "First sample (comma-separated)"},
        {"name": "sample2", "help": "Second sample (comma-separated)"},
        {"name": "--sample3", "default": None, "help": "Third sample (optional)"},
    ],
)
def cmd_fligner(sample1: str, sample2: str, sample3: str = None) -> dict:
    """Fligner-Killeen test for equal variances."""
    from scipy.stats import fligner

    samples = [parse_array(sample1), parse_array(sample2)]
    if sample3:
        samples.append(parse_array(sample3))
    result = fligner(*samples)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="mannwhitneyu",
    category="stats",
    description="Mann-Whitney U rank test (non-parametric)",
    args=[
        {"name": "x", "help": "First sample (comma-separated)"},
        {"name": "y", "help": "Second sample (comma-separated)"},
        {
            "name": "--alternative",
            "default": "two-sided",
            "help": "Alternative: two-sided, less, greater",
        },
    ],
)
def cmd_mannwhitneyu(x: str, y: str, alternative: str = "two-sided") -> dict:
    """Mann-Whitney U test."""
    from scipy.stats import mannwhitneyu

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    result = mannwhitneyu(x_arr, y_arr, alternative=alternative)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="wilcoxon",
    category="stats",
    description="Wilcoxon signed-rank test",
    args=[
        {"name": "x", "help": "First sample (comma-separated)"},
        {"name": "--y", "default": None, "help": "Second sample for paired test (optional)"},
        {
            "name": "--alternative",
            "default": "two-sided",
            "help": "Alternative: two-sided, less, greater",
        },
    ],
)
def cmd_wilcoxon(x: str, y: str = None, alternative: str = "two-sided") -> dict:
    """Wilcoxon signed-rank test."""
    from scipy.stats import wilcoxon

    x_arr = parse_array(x)
    y_arr = parse_array(y) if y else None
    result = wilcoxon(x_arr, y=y_arr, alternative=alternative)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="kruskal",
    category="stats",
    description="Kruskal-Wallis H-test (non-parametric ANOVA)",
    args=[
        {"name": "sample1", "help": "First sample (comma-separated)"},
        {"name": "sample2", "help": "Second sample (comma-separated)"},
        {"name": "--sample3", "default": None, "help": "Third sample (optional)"},
    ],
)
def cmd_kruskal(sample1: str, sample2: str, sample3: str = None) -> dict:
    """Kruskal-Wallis H-test."""
    from scipy.stats import kruskal

    samples = [parse_array(sample1), parse_array(sample2)]
    if sample3:
        samples.append(parse_array(sample3))
    result = kruskal(*samples)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="friedmanchisquare",
    category="stats",
    description="Friedman test for repeated measurements",
    args=[
        {"name": "sample1", "help": "First measurement (comma-separated)"},
        {"name": "sample2", "help": "Second measurement (comma-separated)"},
        {"name": "sample3", "help": "Third measurement (comma-separated)"},
    ],
)
def cmd_friedmanchisquare(sample1: str, sample2: str, sample3: str) -> dict:
    """Friedman test for repeated measurements."""
    from scipy.stats import friedmanchisquare

    arr1 = parse_array(sample1)
    arr2 = parse_array(sample2)
    arr3 = parse_array(sample3)
    result = friedmanchisquare(arr1, arr2, arr3)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="brunnermunzel",
    category="stats",
    description="Brunner-Munzel test for stochastic equality",
    args=[
        {"name": "x", "help": "First sample (comma-separated)"},
        {"name": "y", "help": "Second sample (comma-separated)"},
        {
            "name": "--alternative",
            "default": "two-sided",
            "help": "Alternative: two-sided, less, greater",
        },
    ],
)
def cmd_brunnermunzel(x: str, y: str, alternative: str = "two-sided") -> dict:
    """Brunner-Munzel test."""
    from scipy.stats import brunnermunzel

    x_arr = parse_array(x)
    y_arr = parse_array(y)
    result = brunnermunzel(x_arr, y_arr, alternative=alternative)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="f_oneway",
    category="stats",
    description="One-way ANOVA F-test",
    args=[
        {"name": "sample1", "help": "First group (comma-separated)"},
        {"name": "sample2", "help": "Second group (comma-separated)"},
        {"name": "--sample3", "default": None, "help": "Third group (optional)"},
    ],
)
def cmd_f_oneway(sample1: str, sample2: str, sample3: str = None) -> dict:
    """One-way ANOVA."""
    from scipy.stats import f_oneway

    samples = [parse_array(sample1), parse_array(sample2)]
    if sample3:
        samples.append(parse_array(sample3))
    result = f_oneway(*samples)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="alexandergovern",
    category="stats",
    description="Alexander-Govern test (ANOVA alternative for unequal variances)",
    args=[
        {"name": "sample1", "help": "First group (comma-separated)"},
        {"name": "sample2", "help": "Second group (comma-separated)"},
        {"name": "--sample3", "default": None, "help": "Third group (optional)"},
    ],
)
def cmd_alexandergovern(sample1: str, sample2: str, sample3: str = None) -> dict:
    """Alexander-Govern test."""
    from scipy.stats import alexandergovern

    samples = [parse_array(sample1), parse_array(sample2)]
    if sample3:
        samples.append(parse_array(sample3))
    result = alexandergovern(*samples)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="power_divergence",
    category="stats",
    description="Power divergence statistic and goodness of fit test",
    args=[
        {"name": "f_obs", "help": "Observed frequencies (comma-separated)"},
        {"name": "--f_exp", "default": None, "help": "Expected frequencies (optional)"},
        {
            "name": "--lambda_",
            "default": "pearson",
            "help": "Lambda: pearson, log-likelihood, freeman-tukey, mod-log-likelihood, neyman, cressie-read",
        },
    ],
)
def cmd_power_divergence(f_obs: str, f_exp: str = None, lambda_: str = "pearson") -> dict:
    """Power divergence statistic."""
    from scipy.stats import power_divergence

    obs = parse_array(f_obs)
    exp = parse_array(f_exp) if f_exp else None
    # Map string to lambda value
    lambda_map = {
        "pearson": 1,
        "log-likelihood": 0,
        "freeman-tukey": -0.5,
        "mod-log-likelihood": -1,
        "neyman": -2,
        "cressie-read": 2 / 3,
    }
    lam = lambda_map.get(lambda_, lambda_) if isinstance(lambda_, str) else lambda_
    result = power_divergence(obs, f_exp=exp, lambda_=lam)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="binomtest",
    category="stats",
    description="Exact binomial test",
    args=[
        {"name": "k", "help": "Number of successes"},
        {"name": "n", "help": "Number of trials"},
        {
            "name": "--p",
            "type": float,
            "default": 0.5,
            "help": "Hypothesized probability of success",
        },
        {
            "name": "--alternative",
            "default": "two-sided",
            "help": "Alternative: two-sided, less, greater",
        },
    ],
)
def cmd_binomtest(k: str, n: str, p: float = 0.5, alternative: str = "two-sided") -> dict:
    """Exact binomial test."""
    from scipy.stats import binomtest

    result = binomtest(int(k), int(n), p=p, alternative=alternative)
    return {
        "result": {
            "statistic": float(result.statistic),
            "pvalue": float(result.pvalue),
            "proportion_estimate": float(result.proportion_estimate),
        }
    }


@math_command(
    name="fisher_exact",
    category="stats",
    description="Fisher's exact test on 2x2 contingency table",
    args=[
        {"name": "table", "help": "2x2 contingency table as '[[a,b],[c,d]]' or 'a,b;c,d'"},
        {
            "name": "--alternative",
            "default": "two-sided",
            "help": "Alternative: two-sided, less, greater",
        },
    ],
)
def cmd_fisher_exact(table: str, alternative: str = "two-sided") -> dict:
    """Fisher's exact test."""
    from scipy.stats import fisher_exact

    tbl = parse_matrix(table)
    result = fisher_exact(tbl, alternative=alternative)
    return {"result": {"oddsr": float(result[0]), "pvalue": float(result[1])}}


@math_command(
    name="boschloo_exact",
    category="stats",
    description="Boschloo's exact test on 2x2 contingency table",
    args=[
        {"name": "table", "help": "2x2 contingency table as '[[a,b],[c,d]]' or 'a,b;c,d'"},
        {
            "name": "--alternative",
            "default": "two-sided",
            "help": "Alternative: two-sided, less, greater",
        },
    ],
)
def cmd_boschloo_exact(table: str, alternative: str = "two-sided") -> dict:
    """Boschloo's exact test."""
    from scipy.stats import boschloo_exact

    tbl = parse_matrix(table)
    result = boschloo_exact(tbl, alternative=alternative)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


@math_command(
    name="barnard_exact",
    category="stats",
    description="Barnard's exact test on 2x2 contingency table",
    args=[
        {"name": "table", "help": "2x2 contingency table as '[[a,b],[c,d]]' or 'a,b;c,d'"},
        {
            "name": "--alternative",
            "default": "two-sided",
            "help": "Alternative: two-sided, less, greater",
        },
    ],
)
def cmd_barnard_exact(table: str, alternative: str = "two-sided") -> dict:
    """Barnard's exact test."""
    from scipy.stats import barnard_exact

    tbl = parse_matrix(table)
    result = barnard_exact(tbl, alternative=alternative)
    return {"result": {"statistic": float(result.statistic), "pvalue": float(result.pvalue)}}


# =============================================================================
# SIGNAL CATEGORY (42 functions)
# =============================================================================


@math_command(
    name="sig_convolve",
    category="signal",
    description="1D convolution of two arrays",
    args=[
        {"name": "a", "help": "First input array, comma-separated"},
        {"name": "b", "help": "Second input array, comma-separated"},
        {"name": "--mode", "default": "full", "help": "Mode: full, same, valid"},
    ],
)
def cmd_sig_convolve(a: str, b: str, mode: str = "full") -> dict:
    """Convolve two 1D arrays."""
    from scipy.signal import convolve

    A = parse_array(a)
    B = parse_array(b)
    result = convolve(A, B, mode=mode)
    return {"result": result.tolist()}


@math_command(
    name="sig_correlate",
    category="signal",
    description="Cross-correlation of two 1D arrays",
    args=[
        {"name": "a", "help": "First input array, comma-separated"},
        {"name": "b", "help": "Second input array, comma-separated"},
        {"name": "--mode", "default": "full", "help": "Mode: full, same, valid"},
    ],
)
def cmd_sig_correlate(a: str, b: str, mode: str = "full") -> dict:
    """Cross-correlate two 1D arrays."""
    from scipy.signal import correlate

    A = parse_array(a)
    B = parse_array(b)
    result = correlate(A, B, mode=mode)
    return {"result": result.tolist()}


@math_command(
    name="fftconvolve",
    category="signal",
    description="FFT-based convolution (faster for large arrays)",
    args=[
        {"name": "a", "help": "First input array, comma-separated"},
        {"name": "b", "help": "Second input array, comma-separated"},
        {"name": "--mode", "default": "full", "help": "Mode: full, same, valid"},
    ],
)
def cmd_fftconvolve(a: str, b: str, mode: str = "full") -> dict:
    """FFT-based convolution."""
    from scipy.signal import fftconvolve

    A = parse_array(a)
    B = parse_array(b)
    result = fftconvolve(A, B, mode=mode)
    return {"result": result.tolist()}


@math_command(
    name="oaconvolve",
    category="signal",
    description="Overlap-add convolution (memory efficient for large arrays)",
    args=[
        {"name": "a", "help": "First input array, comma-separated"},
        {"name": "b", "help": "Second input array, comma-separated"},
        {"name": "--mode", "default": "full", "help": "Mode: full, same, valid"},
    ],
)
def cmd_oaconvolve(a: str, b: str, mode: str = "full") -> dict:
    """Overlap-add convolution."""
    from scipy.signal import oaconvolve

    A = parse_array(a)
    B = parse_array(b)
    result = oaconvolve(A, B, mode=mode)
    return {"result": result.tolist()}


@math_command(
    name="convolve2d",
    category="signal",
    description="2D convolution",
    args=[
        {"name": "a", "help": "First 2D array, semicolon-separated rows"},
        {"name": "b", "help": "Second 2D array (kernel), semicolon-separated rows"},
        {"name": "--mode", "default": "full", "help": "Mode: full, same, valid"},
        {"name": "--boundary", "default": "fill", "help": "Boundary: fill, wrap, symm"},
    ],
)
def cmd_convolve2d(a: str, b: str, mode: str = "full", boundary: str = "fill") -> dict:
    """2D convolution."""
    import numpy as np
    from scipy.signal import convolve2d

    A = np.array([parse_array(row) for row in a.split(";")])
    B = np.array([parse_array(row) for row in b.split(";")])
    result = convolve2d(A, B, mode=mode, boundary=boundary)
    return {"result": result.tolist()}


@math_command(
    name="correlate2d",
    category="signal",
    description="2D cross-correlation",
    args=[
        {"name": "a", "help": "First 2D array, semicolon-separated rows"},
        {"name": "b", "help": "Second 2D array, semicolon-separated rows"},
        {"name": "--mode", "default": "full", "help": "Mode: full, same, valid"},
        {"name": "--boundary", "default": "fill", "help": "Boundary: fill, wrap, symm"},
    ],
)
def cmd_correlate2d(a: str, b: str, mode: str = "full", boundary: str = "fill") -> dict:
    """2D cross-correlation."""
    import numpy as np
    from scipy.signal import correlate2d

    A = np.array([parse_array(row) for row in a.split(";")])
    B = np.array([parse_array(row) for row in b.split(";")])
    result = correlate2d(A, B, mode=mode, boundary=boundary)
    return {"result": result.tolist()}


@math_command(
    name="sepfir2d",
    category="signal",
    description="Separable 2D FIR filter",
    args=[
        {"name": "input", "help": "2D input array, semicolon-separated rows"},
        {"name": "hrow", "help": "Row filter coefficients, comma-separated"},
        {"name": "hcol", "help": "Column filter coefficients, comma-separated"},
    ],
)
def cmd_sepfir2d(input: str, hrow: str, hcol: str) -> dict:
    """Apply separable 2D FIR filter."""
    import numpy as np
    from scipy.signal import sepfir2d

    inp = np.array([parse_array(row) for row in input.split(";")])
    hr = parse_array(hrow)
    hc = parse_array(hcol)
    result = sepfir2d(inp, hr, hc)
    return {"result": result.tolist()}


@math_command(
    name="choose_conv_method",
    category="signal",
    description="Choose fastest convolution method for given inputs",
    args=[
        {"name": "a", "help": "First input array, comma-separated"},
        {"name": "b", "help": "Second input array, comma-separated"},
        {"name": "--mode", "default": "full", "help": "Mode: full, same, valid"},
    ],
)
def cmd_choose_conv_method(a: str, b: str, mode: str = "full") -> dict:
    """Choose optimal convolution method."""
    from scipy.signal import choose_conv_method

    A = parse_array(a)
    B = parse_array(b)
    method = choose_conv_method(A, B, mode=mode)
    return {"method": method}


@math_command(
    name="wiener",
    category="signal",
    description="Wiener filter (noise reduction)",
    args=[
        {
            "name": "im",
            "help": "Input array, comma-separated (1D) or semicolon-separated rows (2D)",
        },
        {
            "name": "--mysize",
            "type": int,
            "default": None,
            "help": "Filter size (scalar for all dimensions)",
        },
        {"name": "--noise", "type": float, "default": None, "help": "Noise power estimate"},
    ],
)
def cmd_wiener(im: str, mysize: int = None, noise: float = None) -> dict:
    """Apply Wiener filter."""
    import numpy as np
    from scipy.signal import wiener

    if ";" in im:
        arr = np.array([parse_array(row) for row in im.split(";")])
    else:
        arr = parse_array(im)
    kwargs = {}
    if mysize is not None:
        kwargs["mysize"] = mysize
    if noise is not None:
        kwargs["noise"] = noise
    result = wiener(arr, **kwargs)
    return {"result": result.tolist()}


@math_command(
    name="medfilt",
    category="signal",
    description="1D median filter",
    args=[
        {"name": "volume", "help": "Input array, comma-separated"},
        {"name": "--kernel_size", "type": int, "default": 3, "help": "Kernel size (odd integer)"},
    ],
)
def cmd_medfilt(volume: str, kernel_size: int = 3) -> dict:
    """Apply 1D median filter."""
    from scipy.signal import medfilt

    arr = parse_array(volume)
    result = medfilt(arr, kernel_size=kernel_size)
    return {"result": result.tolist()}


@math_command(
    name="medfilt2d",
    category="signal",
    description="2D median filter",
    args=[
        {"name": "input", "help": "2D input array, semicolon-separated rows"},
        {"name": "--kernel_size", "default": "3", "help": "Kernel size (odd integer or pair)"},
    ],
)
def cmd_medfilt2d(input: str, kernel_size: str = "3") -> dict:
    """Apply 2D median filter."""
    import numpy as np
    from scipy.signal import medfilt2d

    arr = np.array([parse_array(row) for row in input.split(";")])
    if "," in kernel_size:
        ks = tuple(int(x) for x in kernel_size.split(","))
    else:
        ks = int(kernel_size)
    result = medfilt2d(arr, kernel_size=ks)
    return {"result": result.tolist()}


@math_command(
    name="order_filter",
    category="signal",
    description="N-dimensional order filter (generalized median)",
    args=[
        {"name": "a", "help": "Input array, comma-separated (1D) or semicolon-separated rows (2D)"},
        {
            "name": "domain",
            "help": "Domain mask, comma-separated (1D) or semicolon-separated rows (2D)",
        },
        {"name": "rank", "help": "Rank (0=min, n-1=max, n//2=median)"},
    ],
)
def cmd_order_filter(a: str, domain: str, rank: str) -> dict:
    """Apply order filter."""
    import numpy as np
    from scipy.signal import order_filter

    if ";" in a:
        arr = np.array([parse_array(row) for row in a.split(";")])
        dom = np.array([parse_array(row) for row in domain.split(";")])
    else:
        arr = parse_array(a)
        dom = parse_array(domain)
    result = order_filter(arr, dom, int(rank))
    return {"result": result.tolist()}


@math_command(
    name="butter",
    category="signal",
    description="Butterworth filter design",
    args=[
        {"name": "n", "type": int, "help": "Filter order"},
        {"name": "wn", "help": "Critical frequency (scalar or low,high for bandpass)"},
        {"name": "--btype", "default": "low", "help": "Type: low, high, band, bandstop"},
        {"name": "--analog", "action": "store_true", "help": "Design analog filter"},
        {"name": "--output", "default": "ba", "help": "Output: ba, zpk, sos"},
    ],
)
def cmd_butter(
    n: int, wn: str, btype: str = "low", analog: bool = False, output: str = "ba"
) -> dict:
    """Design Butterworth filter."""
    from scipy.signal import butter

    Wn = float(wn) if "," not in wn else [float(x) for x in wn.split(",")]
    result = butter(n, Wn, btype=btype, analog=analog, output=output)
    if output == "ba":
        return {"b": result[0].tolist(), "a": result[1].tolist()}
    elif output == "zpk":
        return {"z": result[0].tolist(), "p": result[1].tolist(), "k": float(result[2])}
    else:  # sos
        return {"sos": result.tolist()}


@math_command(
    name="cheby1",
    category="signal",
    description="Chebyshev type I filter design",
    args=[
        {"name": "n", "type": int, "help": "Filter order"},
        {"name": "rp", "type": float, "help": "Maximum ripple in passband (dB)"},
        {"name": "wn", "help": "Critical frequency"},
        {"name": "--btype", "default": "low", "help": "Type: low, high, band, bandstop"},
        {"name": "--analog", "action": "store_true", "help": "Design analog filter"},
        {"name": "--output", "default": "ba", "help": "Output: ba, zpk, sos"},
    ],
)
def cmd_cheby1(
    n: int, rp: float, wn: str, btype: str = "low", analog: bool = False, output: str = "ba"
) -> dict:
    """Design Chebyshev type I filter."""
    from scipy.signal import cheby1

    Wn = float(wn) if "," not in wn else [float(x) for x in wn.split(",")]
    result = cheby1(n, rp, Wn, btype=btype, analog=analog, output=output)
    if output == "ba":
        return {"b": result[0].tolist(), "a": result[1].tolist()}
    elif output == "zpk":
        return {"z": result[0].tolist(), "p": result[1].tolist(), "k": float(result[2])}
    else:
        return {"sos": result.tolist()}


@math_command(
    name="cheby2",
    category="signal",
    description="Chebyshev type II filter design",
    args=[
        {"name": "n", "type": int, "help": "Filter order"},
        {"name": "rs", "type": float, "help": "Minimum attenuation in stopband (dB)"},
        {"name": "wn", "help": "Critical frequency"},
        {"name": "--btype", "default": "low", "help": "Type: low, high, band, bandstop"},
        {"name": "--analog", "action": "store_true", "help": "Design analog filter"},
        {"name": "--output", "default": "ba", "help": "Output: ba, zpk, sos"},
    ],
)
def cmd_cheby2(
    n: int, rs: float, wn: str, btype: str = "low", analog: bool = False, output: str = "ba"
) -> dict:
    """Design Chebyshev type II filter."""
    from scipy.signal import cheby2

    Wn = float(wn) if "," not in wn else [float(x) for x in wn.split(",")]
    result = cheby2(n, rs, Wn, btype=btype, analog=analog, output=output)
    if output == "ba":
        return {"b": result[0].tolist(), "a": result[1].tolist()}
    elif output == "zpk":
        return {"z": result[0].tolist(), "p": result[1].tolist(), "k": float(result[2])}
    else:
        return {"sos": result.tolist()}


@math_command(
    name="ellip",
    category="signal",
    description="Elliptic (Cauer) filter design",
    args=[
        {"name": "n", "type": int, "help": "Filter order"},
        {"name": "rp", "type": float, "help": "Maximum ripple in passband (dB)"},
        {"name": "rs", "type": float, "help": "Minimum attenuation in stopband (dB)"},
        {"name": "wn", "help": "Critical frequency"},
        {"name": "--btype", "default": "low", "help": "Type: low, high, band, bandstop"},
        {"name": "--analog", "action": "store_true", "help": "Design analog filter"},
        {"name": "--output", "default": "ba", "help": "Output: ba, zpk, sos"},
    ],
)
def cmd_ellip(
    n: int,
    rp: float,
    rs: float,
    wn: str,
    btype: str = "low",
    analog: bool = False,
    output: str = "ba",
) -> dict:
    """Design elliptic filter."""
    from scipy.signal import ellip

    Wn = float(wn) if "," not in wn else [float(x) for x in wn.split(",")]
    result = ellip(n, rp, rs, Wn, btype=btype, analog=analog, output=output)
    if output == "ba":
        return {"b": result[0].tolist(), "a": result[1].tolist()}
    elif output == "zpk":
        return {"z": result[0].tolist(), "p": result[1].tolist(), "k": float(result[2])}
    else:
        return {"sos": result.tolist()}


@math_command(
    name="bessel",
    category="signal",
    description="Bessel/Thomson filter design",
    args=[
        {"name": "n", "type": int, "help": "Filter order"},
        {"name": "wn", "help": "Critical frequency"},
        {"name": "--btype", "default": "low", "help": "Type: low, high, band, bandstop"},
        {"name": "--analog", "action": "store_true", "help": "Design analog filter"},
        {"name": "--output", "default": "ba", "help": "Output: ba, zpk, sos"},
        {"name": "--norm", "default": "phase", "help": "Normalization: phase, delay, mag"},
    ],
)
def cmd_bessel(
    n: int,
    wn: str,
    btype: str = "low",
    analog: bool = False,
    output: str = "ba",
    norm: str = "phase",
) -> dict:
    """Design Bessel filter."""
    from scipy.signal import bessel

    Wn = float(wn) if "," not in wn else [float(x) for x in wn.split(",")]
    result = bessel(n, Wn, btype=btype, analog=analog, output=output, norm=norm)
    if output == "ba":
        return {"b": result[0].tolist(), "a": result[1].tolist()}
    elif output == "zpk":
        return {"z": result[0].tolist(), "p": result[1].tolist(), "k": float(result[2])}
    else:
        return {"sos": result.tolist()}


@math_command(
    name="iirnotch",
    category="signal",
    description="Design second-order IIR notch filter",
    args=[
        {"name": "w0", "type": float, "help": "Frequency to remove (normalized 0-1)"},
        {"name": "Q", "type": float, "help": "Quality factor"},
    ],
)
def cmd_iirnotch(w0: float, Q: float) -> dict:
    """Design IIR notch filter."""
    from scipy.signal import iirnotch

    b, a = iirnotch(w0, Q)
    return {"b": b.tolist(), "a": a.tolist()}


@math_command(
    name="iirpeak",
    category="signal",
    description="Design second-order IIR peaking filter",
    args=[
        {"name": "w0", "type": float, "help": "Frequency to boost (normalized 0-1)"},
        {"name": "Q", "type": float, "help": "Quality factor"},
    ],
)
def cmd_iirpeak(w0: float, Q: float) -> dict:
    """Design IIR peaking filter."""
    from scipy.signal import iirpeak

    b, a = iirpeak(w0, Q)
    return {"b": b.tolist(), "a": a.tolist()}


@math_command(
    name="iirdesign",
    category="signal",
    description="Complete IIR filter design from specifications",
    args=[
        {"name": "wp", "help": "Passband edge frequency"},
        {"name": "ws", "help": "Stopband edge frequency"},
        {"name": "gpass", "type": float, "help": "Maximum passband loss (dB)"},
        {"name": "gstop", "type": float, "help": "Minimum stopband attenuation (dB)"},
        {
            "name": "--ftype",
            "default": "ellip",
            "help": "Filter type: butter, cheby1, cheby2, ellip, bessel",
        },
        {"name": "--analog", "action": "store_true", "help": "Design analog filter"},
        {"name": "--output", "default": "ba", "help": "Output: ba, zpk, sos"},
    ],
)
def cmd_iirdesign(
    wp: str,
    ws: str,
    gpass: float,
    gstop: float,
    ftype: str = "ellip",
    analog: bool = False,
    output: str = "ba",
) -> dict:
    """Design IIR filter from specifications."""
    from scipy.signal import iirdesign

    Wp = float(wp) if "," not in wp else [float(x) for x in wp.split(",")]
    Ws = float(ws) if "," not in ws else [float(x) for x in ws.split(",")]
    result = iirdesign(Wp, Ws, gpass, gstop, ftype=ftype, analog=analog, output=output)
    if output == "ba":
        return {"b": result[0].tolist(), "a": result[1].tolist()}
    elif output == "zpk":
        return {"z": result[0].tolist(), "p": result[1].tolist(), "k": float(result[2])}
    else:
        return {"sos": result.tolist()}


@math_command(
    name="freqs",
    category="signal",
    description="Frequency response of analog filter",
    args=[
        {"name": "b", "help": "Numerator polynomial coefficients, comma-separated"},
        {"name": "a", "help": "Denominator polynomial coefficients, comma-separated"},
        {"name": "worN", "help": "Frequencies to evaluate (comma-separated) or number of points"},
    ],
)
def cmd_freqs(b: str, a: str, worN: str) -> dict:
    """Compute analog filter frequency response."""
    import numpy as np
    from scipy.signal import freqs

    B = parse_array(b)
    A = parse_array(a)
    if "," in worN:
        w = parse_array(worN)
    else:
        w = int(worN)
    w_out, h = freqs(B, A, worN=w)
    return {
        "w": w_out.tolist(),
        "h_real": np.real(h).tolist(),
        "h_imag": np.imag(h).tolist(),
        "h_mag": np.abs(h).tolist(),
        "h_phase": np.angle(h).tolist(),
    }


@math_command(
    name="freqz",
    category="signal",
    description="Frequency response of digital filter",
    args=[
        {"name": "b", "help": "Numerator polynomial coefficients, comma-separated"},
        {"name": "a", "help": "Denominator polynomial coefficients, comma-separated"},
        {
            "name": "--worN",
            "default": "512",
            "help": "Frequencies to evaluate (comma-separated) or number of points",
        },
        {"name": "--fs", "type": float, "default": None, "help": "Sample frequency"},
    ],
)
def cmd_freqz(b: str, a: str, worN: str = "512", fs: float = None) -> dict:
    """Compute digital filter frequency response."""
    import numpy as np
    from scipy.signal import freqz

    B = parse_array(b)
    A = parse_array(a)
    if "," in worN:
        w = parse_array(worN)
    else:
        w = int(worN)
    kwargs = {"worN": w}
    if fs is not None:
        kwargs["fs"] = fs
    w_out, h = freqz(B, A, **kwargs)
    return {
        "w": w_out.tolist(),
        "h_real": np.real(h).tolist(),
        "h_imag": np.imag(h).tolist(),
        "h_mag": np.abs(h).tolist(),
        "h_phase": np.angle(h).tolist(),
    }


@math_command(
    name="sosfreqz",
    category="signal",
    description="Frequency response of SOS filter",
    args=[
        {"name": "sos", "help": "SOS coefficients, semicolon-separated sections"},
        {"name": "--worN", "default": "512", "help": "Frequencies to evaluate or number of points"},
        {"name": "--fs", "type": float, "default": None, "help": "Sample frequency"},
    ],
)
def cmd_sosfreqz(sos: str, worN: str = "512", fs: float = None) -> dict:
    """Compute SOS filter frequency response."""
    import numpy as np
    from scipy.signal import sosfreqz

    sos_arr = np.array([parse_array(row) for row in sos.split(";")])
    if "," in worN:
        w = parse_array(worN)
    else:
        w = int(worN)
    kwargs = {"worN": w}
    if fs is not None:
        kwargs["fs"] = fs
    w_out, h = sosfreqz(sos_arr, **kwargs)
    return {
        "w": w_out.tolist(),
        "h_real": np.real(h).tolist(),
        "h_imag": np.imag(h).tolist(),
        "h_mag": np.abs(h).tolist(),
        "h_phase": np.angle(h).tolist(),
    }


@math_command(
    name="group_delay",
    category="signal",
    description="Compute group delay of digital filter",
    args=[
        {"name": "b", "help": "Numerator polynomial coefficients, comma-separated"},
        {"name": "a", "help": "Denominator polynomial coefficients, comma-separated"},
        {"name": "--w", "default": "512", "help": "Frequencies or number of points"},
        {"name": "--fs", "type": float, "default": None, "help": "Sample frequency"},
    ],
)
def cmd_group_delay(b: str, a: str, w: str = "512", fs: float = None) -> dict:
    """Compute group delay."""
    from scipy.signal import group_delay

    B = parse_array(b)
    A = parse_array(a)
    if "," in w:
        w_arr = parse_array(w)
    else:
        w_arr = int(w)
    kwargs = {"w": w_arr}
    if fs is not None:
        kwargs["fs"] = fs
    w_out, gd = group_delay((B, A), **kwargs)
    return {"w": w_out.tolist(), "group_delay": gd.tolist()}


@math_command(
    name="tf2zpk",
    category="signal",
    description="Convert transfer function to zero-pole-gain form",
    args=[
        {"name": "b", "help": "Numerator polynomial coefficients, comma-separated"},
        {"name": "a", "help": "Denominator polynomial coefficients, comma-separated"},
    ],
)
def cmd_tf2zpk(b: str, a: str) -> dict:
    """Convert transfer function to zpk."""
    import numpy as np
    from scipy.signal import tf2zpk

    B = parse_array(b)
    A = parse_array(a)
    z, p, k = tf2zpk(B, A)
    return {
        "z_real": np.real(z).tolist(),
        "z_imag": np.imag(z).tolist(),
        "p_real": np.real(p).tolist(),
        "p_imag": np.imag(p).tolist(),
        "k": float(k),
    }


@math_command(
    name="zpk2tf",
    category="signal",
    description="Convert zero-pole-gain to transfer function form",
    args=[
        {"name": "z", "help": "Zeros, comma-separated (real parts; use z_imag for complex)"},
        {"name": "p", "help": "Poles, comma-separated (real parts; use p_imag for complex)"},
        {"name": "k", "type": float, "help": "System gain"},
        {"name": "--z_imag", "default": None, "help": "Imaginary parts of zeros, comma-separated"},
        {"name": "--p_imag", "default": None, "help": "Imaginary parts of poles, comma-separated"},
    ],
)
def cmd_zpk2tf(z: str, p: str, k: float, z_imag: str = None, p_imag: str = None) -> dict:
    """Convert zpk to transfer function."""
    import numpy as np
    from scipy.signal import zpk2tf

    z_real = parse_array(z)
    p_real = parse_array(p)
    if z_imag:
        z_arr = z_real + 1j * parse_array(z_imag)
    else:
        z_arr = z_real
    if p_imag:
        p_arr = p_real + 1j * parse_array(p_imag)
    else:
        p_arr = p_real
    b, a = zpk2tf(z_arr, p_arr, k)
    return {"b": np.real(b).tolist(), "a": np.real(a).tolist()}


@math_command(
    name="tf2sos",
    category="signal",
    description="Convert transfer function to second-order sections",
    args=[
        {"name": "b", "help": "Numerator polynomial coefficients, comma-separated"},
        {"name": "a", "help": "Denominator polynomial coefficients, comma-separated"},
        {
            "name": "--pairing",
            "default": "nearest",
            "help": "Pairing method: nearest, keep_odd, minimal",
        },
    ],
)
def cmd_tf2sos(b: str, a: str, pairing: str = "nearest") -> dict:
    """Convert transfer function to SOS."""
    from scipy.signal import tf2sos

    B = parse_array(b)
    A = parse_array(a)
    sos = tf2sos(B, A, pairing=pairing)
    return {"sos": sos.tolist()}


@math_command(
    name="sos2tf",
    category="signal",
    description="Convert second-order sections to transfer function",
    args=[{"name": "sos", "help": "SOS coefficients, semicolon-separated sections"}],
)
def cmd_sos2tf(sos: str) -> dict:
    """Convert SOS to transfer function."""
    import numpy as np
    from scipy.signal import sos2tf

    sos_arr = np.array([parse_array(row) for row in sos.split(";")])
    b, a = sos2tf(sos_arr)
    return {"b": b.tolist(), "a": a.tolist()}


@math_command(
    name="bilinear",
    category="signal",
    description="Bilinear transformation from analog to digital filter",
    args=[
        {"name": "b", "help": "Analog numerator coefficients, comma-separated"},
        {"name": "a", "help": "Analog denominator coefficients, comma-separated"},
        {"name": "fs", "type": float, "help": "Sample rate"},
    ],
)
def cmd_bilinear(b: str, a: str, fs: float) -> dict:
    """Apply bilinear transformation."""
    from scipy.signal import bilinear

    B = parse_array(b)
    A = parse_array(a)
    bd, ad = bilinear(B, A, fs)
    return {"b": bd.tolist(), "a": ad.tolist()}


@math_command(
    name="bilinear_zpk",
    category="signal",
    description="Bilinear transformation in zpk form",
    args=[
        {"name": "z", "help": "Analog zeros, comma-separated"},
        {"name": "p", "help": "Analog poles, comma-separated"},
        {"name": "k", "type": float, "help": "System gain"},
        {"name": "fs", "type": float, "help": "Sample rate"},
    ],
)
def cmd_bilinear_zpk(z: str, p: str, k: float, fs: float) -> dict:
    """Apply bilinear transformation in zpk form."""
    import numpy as np
    from scipy.signal import bilinear_zpk

    z_arr = parse_array(z)
    p_arr = parse_array(p)
    zd, pd, kd = bilinear_zpk(z_arr, p_arr, k, fs)
    return {
        "z_real": np.real(zd).tolist(),
        "z_imag": np.imag(zd).tolist(),
        "p_real": np.real(pd).tolist(),
        "p_imag": np.imag(pd).tolist(),
        "k": float(kd),
    }


@math_command(
    name="lfilter",
    category="signal",
    description="Filter data with IIR or FIR filter",
    args=[
        {"name": "b", "help": "Numerator coefficients, comma-separated"},
        {"name": "a", "help": "Denominator coefficients, comma-separated"},
        {"name": "x", "help": "Input signal, comma-separated"},
    ],
)
def cmd_lfilter(b: str, a: str, x: str) -> dict:
    """Apply IIR/FIR filter."""
    from scipy.signal import lfilter

    B = parse_array(b)
    A = parse_array(a)
    X = parse_array(x)
    result = lfilter(B, A, X)
    return {"result": result.tolist()}


@math_command(
    name="sosfilt",
    category="signal",
    description="Filter data with second-order sections",
    args=[
        {"name": "sos", "help": "SOS coefficients, semicolon-separated sections"},
        {"name": "x", "help": "Input signal, comma-separated"},
    ],
)
def cmd_sosfilt(sos: str, x: str) -> dict:
    """Apply SOS filter."""
    import numpy as np
    from scipy.signal import sosfilt

    sos_arr = np.array([parse_array(row) for row in sos.split(";")])
    X = parse_array(x)
    result = sosfilt(sos_arr, X)
    return {"result": result.tolist()}


@math_command(
    name="filtfilt",
    category="signal",
    description="Zero-phase digital filtering (forward-backward)",
    args=[
        {"name": "b", "help": "Numerator coefficients, comma-separated"},
        {"name": "a", "help": "Denominator coefficients, comma-separated"},
        {"name": "x", "help": "Input signal, comma-separated"},
        {"name": "--padtype", "default": "odd", "help": "Padding: odd, even, constant, None"},
        {"name": "--padlen", "type": int, "default": None, "help": "Pad length"},
    ],
)
def cmd_filtfilt(b: str, a: str, x: str, padtype: str = "odd", padlen: int = None) -> dict:
    """Apply zero-phase filter."""
    from scipy.signal import filtfilt

    B = parse_array(b)
    A = parse_array(a)
    X = parse_array(x)
    kwargs = {"padtype": padtype if padtype.lower() != "none" else None}
    if padlen is not None:
        kwargs["padlen"] = padlen
    result = filtfilt(B, A, X, **kwargs)
    return {"result": result.tolist()}


@math_command(
    name="sosfiltfilt",
    category="signal",
    description="Zero-phase SOS filtering (forward-backward)",
    args=[
        {"name": "sos", "help": "SOS coefficients, semicolon-separated sections"},
        {"name": "x", "help": "Input signal, comma-separated"},
        {"name": "--padtype", "default": "odd", "help": "Padding: odd, even, constant, None"},
        {"name": "--padlen", "type": int, "default": None, "help": "Pad length"},
    ],
)
def cmd_sosfiltfilt(sos: str, x: str, padtype: str = "odd", padlen: int = None) -> dict:
    """Apply zero-phase SOS filter."""
    import numpy as np
    from scipy.signal import sosfiltfilt

    sos_arr = np.array([parse_array(row) for row in sos.split(";")])
    X = parse_array(x)
    kwargs = {"padtype": padtype if padtype.lower() != "none" else None}
    if padlen is not None:
        kwargs["padlen"] = padlen
    result = sosfiltfilt(sos_arr, X, **kwargs)
    return {"result": result.tolist()}


@math_command(
    name="lfiltic",
    category="signal",
    description="Construct initial conditions for lfilter",
    args=[
        {"name": "b", "help": "Numerator coefficients, comma-separated"},
        {"name": "a", "help": "Denominator coefficients, comma-separated"},
        {"name": "y", "help": "Initial output values, comma-separated"},
        {"name": "--x", "default": None, "help": "Initial input values, comma-separated"},
    ],
)
def cmd_lfiltic(b: str, a: str, y: str, x: str = None) -> dict:
    """Construct lfilter initial conditions."""
    from scipy.signal import lfiltic

    B = parse_array(b)
    A = parse_array(a)
    Y = parse_array(y)
    X = parse_array(x) if x else None
    zi = lfiltic(B, A, Y, x=X)
    return {"zi": zi.tolist()}


@math_command(
    name="deconvolve",
    category="signal",
    description="Deconvolve signal from another",
    args=[
        {"name": "signal", "help": "Convolved signal, comma-separated"},
        {"name": "divisor", "help": "Signal to deconvolve, comma-separated"},
    ],
)
def cmd_deconvolve(signal: str, divisor: str) -> dict:
    """Deconvolve signals."""
    from scipy.signal import deconvolve

    sig = parse_array(signal)
    div = parse_array(divisor)
    quotient, remainder = deconvolve(sig, div)
    return {"quotient": quotient.tolist(), "remainder": remainder.tolist()}


@math_command(
    name="sig_hilbert",
    category="signal",
    description="Compute analytic signal using Hilbert transform",
    args=[
        {"name": "x", "help": "Input signal, comma-separated"},
        {"name": "--N", "type": int, "default": None, "help": "Number of FFT points"},
    ],
)
def cmd_sig_hilbert(x: str, N: int = None) -> dict:
    """Compute Hilbert transform."""
    import numpy as np
    from scipy.signal import hilbert

    X = parse_array(x)
    kwargs = {}
    if N is not None:
        kwargs["N"] = N
    analytic = hilbert(X, **kwargs)
    return {
        "real": np.real(analytic).tolist(),
        "imag": np.imag(analytic).tolist(),
        "envelope": np.abs(analytic).tolist(),
        "phase": np.angle(analytic).tolist(),
    }


@math_command(
    name="decimate",
    category="signal",
    description="Downsample signal after lowpass filtering",
    args=[
        {"name": "x", "help": "Input signal, comma-separated"},
        {"name": "q", "type": int, "help": "Downsampling factor"},
        {"name": "--n", "type": int, "default": None, "help": "Filter order"},
        {"name": "--ftype", "default": "iir", "help": "Filter type: iir, fir"},
        {"name": "--zero_phase", "action": "store_true", "help": "Use zero-phase filtering"},
    ],
)
def cmd_decimate(
    x: str, q: int, n: int = None, ftype: str = "iir", zero_phase: bool = False
) -> dict:
    """Decimate signal."""
    from scipy.signal import decimate

    X = parse_array(x)
    kwargs = {"ftype": ftype, "zero_phase": zero_phase}
    if n is not None:
        kwargs["n"] = n
    result = decimate(X, q, **kwargs)
    return {"result": result.tolist()}


@math_command(
    name="resample",
    category="signal",
    description="Resample signal using Fourier method",
    args=[
        {"name": "x", "help": "Input signal, comma-separated"},
        {"name": "num", "type": int, "help": "Number of output samples"},
        {"name": "--t", "default": None, "help": "Sample times (optional), comma-separated"},
        {"name": "--window", "default": None, "help": "Window function"},
    ],
)
def cmd_resample(x: str, num: int, t: str = None, window: str = None) -> dict:
    """Resample signal."""
    from scipy.signal import resample

    X = parse_array(x)
    kwargs = {}
    if t:
        kwargs["t"] = parse_array(t)
    if window:
        kwargs["window"] = window
    result = resample(X, num, **kwargs)
    if isinstance(result, tuple):
        return {"result": result[0].tolist(), "t_new": result[1].tolist()}
    return {"result": result.tolist()}


@math_command(
    name="resample_poly",
    category="signal",
    description="Resample signal using polyphase filtering",
    args=[
        {"name": "x", "help": "Input signal, comma-separated"},
        {"name": "up", "type": int, "help": "Upsampling factor"},
        {"name": "down", "type": int, "help": "Downsampling factor"},
        {"name": "--window", "default": "kaiser", "help": "Window function or (window, beta)"},
        {
            "name": "--padtype",
            "default": "constant",
            "help": "Padding: constant, line, mean, minimum, maximum, reflect, wrap",
        },
    ],
)
def cmd_resample_poly(
    x: str, up: int, down: int, window: str = "kaiser", padtype: str = "constant"
) -> dict:
    """Resample using polyphase filter."""
    from scipy.signal import resample_poly

    X = parse_array(x)
    result = resample_poly(X, up, down, window=window, padtype=padtype)
    return {"result": result.tolist()}


@math_command(
    name="upfirdn",
    category="signal",
    description="Upsample, FIR filter, downsample",
    args=[
        {"name": "h", "help": "FIR filter coefficients, comma-separated"},
        {"name": "x", "help": "Input signal, comma-separated"},
        {"name": "--up", "type": int, "default": 1, "help": "Upsampling factor"},
        {"name": "--down", "type": int, "default": 1, "help": "Downsampling factor"},
    ],
)
def cmd_upfirdn(h: str, x: str, up: int = 1, down: int = 1) -> dict:
    """Apply upfirdn operation."""
    from scipy.signal import upfirdn

    H = parse_array(h)
    X = parse_array(x)
    result = upfirdn(H, X, up=up, down=down)
    return {"result": result.tolist()}


@math_command(
    name="firwin",
    category="signal",
    description="FIR filter design using window method",
    args=[
        {"name": "numtaps", "type": int, "help": "Number of filter taps (odd for type I)"},
        {"name": "cutoff", "help": "Cutoff frequency (scalar or pair for bandpass)"},
        {"name": "--window", "default": "hamming", "help": "Window function"},
        {
            "name": "--pass_zero",
            "default": "True",
            "help": "Include DC: True, False, bandpass, bandstop",
        },
        {"name": "--fs", "type": float, "default": 2.0, "help": "Sample frequency"},
    ],
)
def cmd_firwin(
    numtaps: int, cutoff: str, window: str = "hamming", pass_zero: str = "True", fs: float = 2.0
) -> dict:
    """Design FIR filter."""
    from scipy.signal import firwin

    if "," in cutoff:
        cut = [float(x) for x in cutoff.split(",")]
    else:
        cut = float(cutoff)
    # Handle pass_zero as boolean or string
    if pass_zero.lower() == "true":
        pz = True
    elif pass_zero.lower() == "false":
        pz = False
    else:
        pz = pass_zero
    result = firwin(numtaps, cut, window=window, pass_zero=pz, fs=fs)
    return {"result": result.tolist()}


# =============================================================================
# SPECIAL CATEGORY (38 functions)
# =============================================================================

# --- Gamma functions ---


@math_command(
    name="sp_gamma",
    category="special",
    description="Gamma function Γ(x)",
    args=[{"name": "x", "help": "Input value"}],
)
def cmd_sp_gamma(x: str) -> dict:
    """Compute the gamma function."""
    from scipy.special import gamma

    r = gamma(float(x))
    return {"result": float(r), "latex": f"\\Gamma({x})"}


@math_command(
    name="sp_gammaln",
    category="special",
    description="Log of absolute value of gamma function",
    args=[{"name": "x", "help": "Input value"}],
)
def cmd_sp_gammaln(x: str) -> dict:
    """Compute log of absolute value of gamma function."""
    from scipy.special import gammaln

    r = gammaln(float(x))
    return {"result": float(r), "latex": f"\\ln|\\Gamma({x})|"}


@math_command(
    name="sp_loggamma",
    category="special",
    description="Principal branch of log of gamma function",
    args=[{"name": "x", "help": "Input value"}],
)
def cmd_sp_loggamma(x: str) -> dict:
    """Compute principal branch of log gamma."""
    from scipy.special import loggamma

    r = loggamma(float(x))
    return {"result": complex(r) if hasattr(r, "imag") else float(r), "latex": f"\\log\\Gamma({x})"}


@math_command(
    name="sp_gammainc",
    category="special",
    description="Regularized lower incomplete gamma function",
    args=[
        {"name": "a", "help": "Parameter a > 0"},
        {"name": "x", "help": "Upper limit of integration"},
    ],
)
def cmd_sp_gammainc(a: str, x: str) -> dict:
    """Compute regularized lower incomplete gamma function."""
    from scipy.special import gammainc

    r = gammainc(float(a), float(x))
    return {"result": float(r), "latex": f"P({a}, {x})"}


@math_command(
    name="sp_gammaincc",
    category="special",
    description="Regularized upper incomplete gamma function",
    args=[
        {"name": "a", "help": "Parameter a > 0"},
        {"name": "x", "help": "Lower limit of integration"},
    ],
)
def cmd_sp_gammaincc(a: str, x: str) -> dict:
    """Compute regularized upper incomplete gamma function."""
    from scipy.special import gammaincc

    r = gammaincc(float(a), float(x))
    return {"result": float(r), "latex": f"Q({a}, {x})"}


@math_command(
    name="sp_gammaincinv",
    category="special",
    description="Inverse of regularized lower incomplete gamma function",
    args=[{"name": "a", "help": "Parameter a > 0"}, {"name": "y", "help": "Value in [0, 1]"}],
)
def cmd_sp_gammaincinv(a: str, y: str) -> dict:
    """Compute inverse of regularized lower incomplete gamma."""
    from scipy.special import gammaincinv

    r = gammaincinv(float(a), float(y))
    return {"result": float(r), "latex": f"P^{{-1}}({a}, {y})"}


@math_command(
    name="sp_gammainccinv",
    category="special",
    description="Inverse of regularized upper incomplete gamma function",
    args=[{"name": "a", "help": "Parameter a > 0"}, {"name": "y", "help": "Value in [0, 1]"}],
)
def cmd_sp_gammainccinv(a: str, y: str) -> dict:
    """Compute inverse of regularized upper incomplete gamma."""
    from scipy.special import gammainccinv

    r = gammainccinv(float(a), float(y))
    return {"result": float(r), "latex": f"Q^{{-1}}({a}, {y})"}


@math_command(
    name="sp_digamma",
    category="special",
    description="Digamma function (psi function, derivative of log gamma)",
    args=[{"name": "x", "help": "Input value"}],
)
def cmd_sp_digamma(x: str) -> dict:
    """Compute the digamma function."""
    from scipy.special import digamma

    r = digamma(float(x))
    return {"result": float(r), "latex": f"\\psi({x})"}


@math_command(
    name="sp_polygamma",
    category="special",
    description="Polygamma function (n-th derivative of digamma)",
    args=[
        {"name": "n", "type": int, "help": "Order of derivative (0 = digamma)"},
        {"name": "x", "help": "Input value"},
    ],
)
def cmd_sp_polygamma(n: int, x: str) -> dict:
    """Compute the polygamma function."""
    from scipy.special import polygamma

    r = polygamma(n, float(x))
    return {"result": float(r), "latex": f"\\psi^{{({n})}}({x})"}


# --- Beta functions ---


@math_command(
    name="sp_beta",
    category="special",
    description="Beta function B(a, b)",
    args=[{"name": "a", "help": "First parameter"}, {"name": "b", "help": "Second parameter"}],
)
def cmd_sp_beta(a: str, b: str) -> dict:
    """Compute the beta function."""
    from scipy.special import beta

    r = beta(float(a), float(b))
    return {"result": float(r), "latex": f"B({a}, {b})"}


@math_command(
    name="sp_betaln",
    category="special",
    description="Log of absolute value of beta function",
    args=[{"name": "a", "help": "First parameter"}, {"name": "b", "help": "Second parameter"}],
)
def cmd_sp_betaln(a: str, b: str) -> dict:
    """Compute log of absolute value of beta function."""
    from scipy.special import betaln

    r = betaln(float(a), float(b))
    return {"result": float(r), "latex": f"\\ln|B({a}, {b})|"}


@math_command(
    name="sp_betainc",
    category="special",
    description="Regularized incomplete beta function",
    args=[
        {"name": "a", "help": "First parameter"},
        {"name": "b", "help": "Second parameter"},
        {"name": "x", "help": "Upper limit of integration in [0, 1]"},
    ],
)
def cmd_sp_betainc(a: str, b: str, x: str) -> dict:
    """Compute regularized incomplete beta function."""
    from scipy.special import betainc

    r = betainc(float(a), float(b), float(x))
    return {"result": float(r), "latex": f"I_{{{x}}}({a}, {b})"}


@math_command(
    name="sp_betaincinv",
    category="special",
    description="Inverse of regularized incomplete beta function",
    args=[
        {"name": "a", "help": "First parameter"},
        {"name": "b", "help": "Second parameter"},
        {"name": "y", "help": "Value in [0, 1]"},
    ],
)
def cmd_sp_betaincinv(a: str, b: str, y: str) -> dict:
    """Compute inverse of regularized incomplete beta function."""
    from scipy.special import betaincinv

    r = betaincinv(float(a), float(b), float(y))
    return {"result": float(r), "latex": f"I^{{-1}}_{{{y}}}({a}, {b})"}


# --- Combinatorial functions ---


@math_command(
    name="sp_factorial",
    category="special",
    description="Factorial n!",
    args=[
        {"name": "n", "type": int, "help": "Non-negative integer"},
        {"name": "--exact", "action": "store_true", "help": "Return exact integer result"},
    ],
)
def cmd_sp_factorial(n: int, exact: bool = False) -> dict:
    """Compute factorial."""
    from scipy.special import factorial

    r = factorial(n, exact=exact)
    return {"result": int(r) if exact else float(r), "latex": f"{n}!"}


@math_command(
    name="sp_factorial2",
    category="special",
    description="Double factorial n!!",
    args=[
        {"name": "n", "type": int, "help": "Non-negative integer"},
        {"name": "--exact", "action": "store_true", "help": "Return exact integer result"},
    ],
)
def cmd_sp_factorial2(n: int, exact: bool = False) -> dict:
    """Compute double factorial."""
    from scipy.special import factorial2

    r = factorial2(n, exact=exact)
    return {"result": int(r) if exact else float(r), "latex": f"{n}!!"}


@math_command(
    name="sp_comb",
    category="special",
    description="Binomial coefficient C(n, k)",
    args=[
        {"name": "n", "type": int, "help": "Total number of items"},
        {"name": "k", "type": int, "help": "Number of items to choose"},
        {"name": "--exact", "action": "store_true", "help": "Return exact integer result"},
        {"name": "--repetition", "action": "store_true", "help": "Allow repetition"},
    ],
)
def cmd_sp_comb(n: int, k: int, exact: bool = False, repetition: bool = False) -> dict:
    """Compute binomial coefficient."""
    from scipy.special import comb

    r = comb(n, k, exact=exact, repetition=repetition)
    return {"result": int(r) if exact else float(r), "latex": f"\\binom{{{n}}}{{{k}}}"}


@math_command(
    name="sp_perm",
    category="special",
    description="Permutations P(n, k)",
    args=[
        {"name": "n", "type": int, "help": "Total number of items"},
        {"name": "k", "type": int, "help": "Number of items to arrange"},
        {"name": "--exact", "action": "store_true", "help": "Return exact integer result"},
    ],
)
def cmd_sp_perm(n: int, k: int, exact: bool = False) -> dict:
    """Compute permutations."""
    from scipy.special import perm

    r = perm(n, k, exact=exact)
    return {"result": int(r) if exact else float(r), "latex": f"P({n}, {k})"}


# --- Error functions ---


@math_command(
    name="sp_erf",
    category="special",
    description="Error function",
    args=[{"name": "x", "help": "Input value"}],
)
def cmd_sp_erf(x: str) -> dict:
    """Compute error function."""
    from scipy.special import erf

    r = erf(float(x))
    return {"result": float(r), "latex": f"\\mathrm{{erf}}({x})"}


@math_command(
    name="sp_erfc",
    category="special",
    description="Complementary error function (1 - erf(x))",
    args=[{"name": "x", "help": "Input value"}],
)
def cmd_sp_erfc(x: str) -> dict:
    """Compute complementary error function."""
    from scipy.special import erfc

    r = erfc(float(x))
    return {"result": float(r), "latex": f"\\mathrm{{erfc}}({x})"}


@math_command(
    name="sp_erfcx",
    category="special",
    description="Scaled complementary error function exp(x^2) * erfc(x)",
    args=[{"name": "x", "help": "Input value"}],
)
def cmd_sp_erfcx(x: str) -> dict:
    """Compute scaled complementary error function."""
    from scipy.special import erfcx

    r = erfcx(float(x))
    return {"result": float(r), "latex": f"\\mathrm{{erfcx}}({x})"}


@math_command(
    name="sp_erfi",
    category="special",
    description="Imaginary error function -i * erf(i*x)",
    args=[{"name": "x", "help": "Input value"}],
)
def cmd_sp_erfi(x: str) -> dict:
    """Compute imaginary error function."""
    from scipy.special import erfi

    r = erfi(float(x))
    return {"result": float(r), "latex": f"\\mathrm{{erfi}}({x})"}


@math_command(
    name="sp_erfinv",
    category="special",
    description="Inverse of error function",
    args=[{"name": "y", "help": "Value in (-1, 1)"}],
)
def cmd_sp_erfinv(y: str) -> dict:
    """Compute inverse error function."""
    from scipy.special import erfinv

    r = erfinv(float(y))
    return {"result": float(r), "latex": f"\\mathrm{{erf}}^{{-1}}({y})"}


@math_command(
    name="sp_erfcinv",
    category="special",
    description="Inverse of complementary error function",
    args=[{"name": "y", "help": "Value in (0, 2)"}],
)
def cmd_sp_erfcinv(y: str) -> dict:
    """Compute inverse complementary error function."""
    from scipy.special import erfcinv

    r = erfcinv(float(y))
    return {"result": float(r), "latex": f"\\mathrm{{erfc}}^{{-1}}({y})"}


# --- Bessel functions ---


@math_command(
    name="sp_jv",
    category="special",
    description="Bessel function of the first kind J_v(x)",
    args=[{"name": "v", "help": "Order (can be non-integer)"}, {"name": "x", "help": "Argument"}],
)
def cmd_sp_jv(v: str, x: str) -> dict:
    """Compute Bessel function of the first kind."""
    from scipy.special import jv

    r = jv(float(v), float(x))
    return {"result": float(r), "latex": f"J_{{{v}}}({x})"}


@math_command(
    name="sp_yv",
    category="special",
    description="Bessel function of the second kind Y_v(x)",
    args=[
        {"name": "v", "help": "Order (can be non-integer)"},
        {"name": "x", "help": "Argument (must be positive)"},
    ],
)
def cmd_sp_yv(v: str, x: str) -> dict:
    """Compute Bessel function of the second kind."""
    from scipy.special import yv

    r = yv(float(v), float(x))
    return {"result": float(r), "latex": f"Y_{{{v}}}({x})"}


@math_command(
    name="sp_iv",
    category="special",
    description="Modified Bessel function of the first kind I_v(x)",
    args=[{"name": "v", "help": "Order (can be non-integer)"}, {"name": "x", "help": "Argument"}],
)
def cmd_sp_iv(v: str, x: str) -> dict:
    """Compute modified Bessel function of the first kind."""
    from scipy.special import iv

    r = iv(float(v), float(x))
    return {"result": float(r), "latex": f"I_{{{v}}}({x})"}


@math_command(
    name="sp_kv",
    category="special",
    description="Modified Bessel function of the second kind K_v(x)",
    args=[
        {"name": "v", "help": "Order (can be non-integer)"},
        {"name": "x", "help": "Argument (must be positive)"},
    ],
)
def cmd_sp_kv(v: str, x: str) -> dict:
    """Compute modified Bessel function of the second kind."""
    from scipy.special import kv

    r = kv(float(v), float(x))
    return {"result": float(r), "latex": f"K_{{{v}}}({x})"}


@math_command(
    name="sp_jve",
    category="special",
    description="Exponentially scaled Bessel function of first kind: J_v(x) * exp(-abs(imag(x)))",
    args=[{"name": "v", "help": "Order"}, {"name": "x", "help": "Argument"}],
)
def cmd_sp_jve(v: str, x: str) -> dict:
    """Compute exponentially scaled Bessel function of first kind."""
    from scipy.special import jve

    r = jve(float(v), float(x))
    return {"result": float(r), "latex": f"J_{{{v}}}^{{(e)}}({x})"}


@math_command(
    name="sp_yve",
    category="special",
    description="Exponentially scaled Bessel function of second kind: Y_v(x) * exp(-abs(imag(x)))",
    args=[{"name": "v", "help": "Order"}, {"name": "x", "help": "Argument"}],
)
def cmd_sp_yve(v: str, x: str) -> dict:
    """Compute exponentially scaled Bessel function of second kind."""
    from scipy.special import yve

    r = yve(float(v), float(x))
    return {"result": float(r), "latex": f"Y_{{{v}}}^{{(e)}}({x})"}


@math_command(
    name="sp_ive",
    category="special",
    description="Exponentially scaled modified Bessel function of first kind: I_v(x) * exp(-abs(real(x)))",
    args=[{"name": "v", "help": "Order"}, {"name": "x", "help": "Argument"}],
)
def cmd_sp_ive(v: str, x: str) -> dict:
    """Compute exponentially scaled modified Bessel function of first kind."""
    from scipy.special import ive

    r = ive(float(v), float(x))
    return {"result": float(r), "latex": f"I_{{{v}}}^{{(e)}}({x})"}


@math_command(
    name="sp_kve",
    category="special",
    description="Exponentially scaled modified Bessel function of second kind: K_v(x) * exp(x)",
    args=[{"name": "v", "help": "Order"}, {"name": "x", "help": "Argument"}],
)
def cmd_sp_kve(v: str, x: str) -> dict:
    """Compute exponentially scaled modified Bessel function of second kind."""
    from scipy.special import kve

    r = kve(float(v), float(x))
    return {"result": float(r), "latex": f"K_{{{v}}}^{{(e)}}({x})"}


@math_command(
    name="sp_hankel1",
    category="special",
    description="Hankel function of the first kind H1_v(x) = J_v(x) + i*Y_v(x)",
    args=[{"name": "v", "help": "Order"}, {"name": "x", "help": "Argument"}],
)
def cmd_sp_hankel1(v: str, x: str) -> dict:
    """Compute Hankel function of the first kind."""
    from scipy.special import hankel1

    r = hankel1(float(v), float(x))
    return {
        "result": {"real": float(r.real), "imag": float(r.imag)},
        "latex": f"H_{{{v}}}^{{(1)}}({x})",
    }


@math_command(
    name="sp_hankel2",
    category="special",
    description="Hankel function of the second kind H2_v(x) = J_v(x) - i*Y_v(x)",
    args=[{"name": "v", "help": "Order"}, {"name": "x", "help": "Argument"}],
)
def cmd_sp_hankel2(v: str, x: str) -> dict:
    """Compute Hankel function of the second kind."""
    from scipy.special import hankel2

    r = hankel2(float(v), float(x))
    return {
        "result": {"real": float(r.real), "imag": float(r.imag)},
        "latex": f"H_{{{v}}}^{{(2)}}({x})",
    }


# --- Airy functions ---


@math_command(
    name="sp_airy",
    category="special",
    description="Airy functions Ai(x), Ai'(x), Bi(x), Bi'(x)",
    args=[{"name": "x", "help": "Argument"}],
)
def cmd_sp_airy(x: str) -> dict:
    """Compute Airy functions and their derivatives."""
    from scipy.special import airy

    ai, aip, bi, bip = airy(float(x))
    return {
        "result": {
            "Ai": float(ai),
            "Ai_prime": float(aip),
            "Bi": float(bi),
            "Bi_prime": float(bip),
        },
        "latex": f"\\mathrm{{Ai}}({x}), \\mathrm{{Bi}}({x})",
    }


# --- Elliptic functions ---


@math_command(
    name="sp_ellipk",
    category="special",
    description="Complete elliptic integral of the first kind K(m)",
    args=[{"name": "m", "help": "Parameter m (0 <= m < 1)"}],
)
def cmd_sp_ellipk(m: str) -> dict:
    """Compute complete elliptic integral of the first kind."""
    from scipy.special import ellipk

    r = ellipk(float(m))
    return {"result": float(r), "latex": f"K({m})"}


@math_command(
    name="sp_ellipe",
    category="special",
    description="Complete elliptic integral of the second kind E(m)",
    args=[{"name": "m", "help": "Parameter m (0 <= m <= 1)"}],
)
def cmd_sp_ellipe(m: str) -> dict:
    """Compute complete elliptic integral of the second kind."""
    from scipy.special import ellipe

    r = ellipe(float(m))
    return {"result": float(r), "latex": f"E({m})"}


@math_command(
    name="sp_ellipkinc",
    category="special",
    description="Incomplete elliptic integral of the first kind F(phi, m)",
    args=[
        {"name": "phi", "help": "Amplitude angle in radians"},
        {"name": "m", "help": "Parameter m (0 <= m < 1)"},
    ],
)
def cmd_sp_ellipkinc(phi: str, m: str) -> dict:
    """Compute incomplete elliptic integral of the first kind."""
    from scipy.special import ellipkinc

    r = ellipkinc(float(phi), float(m))
    return {"result": float(r), "latex": f"F({phi}, {m})"}


@math_command(
    name="sp_ellipeinc",
    category="special",
    description="Incomplete elliptic integral of the second kind E(phi, m)",
    args=[
        {"name": "phi", "help": "Amplitude angle in radians"},
        {"name": "m", "help": "Parameter m (0 <= m <= 1)"},
    ],
)
def cmd_sp_ellipeinc(phi: str, m: str) -> dict:
    """Compute incomplete elliptic integral of the second kind."""
    from scipy.special import ellipeinc

    r = ellipeinc(float(phi), float(m))
    return {"result": float(r), "latex": f"E({phi}, {m})"}


# =============================================================================
# DISTRIBUTIONS CATEGORY (20 distributions)
# =============================================================================


@math_command(
    name="norm",
    category="distributions",
    description="Normal distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location (mean)"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale (std dev)"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_norm(op: str, x: str = None, loc: float = 0.0, scale: float = 1.0, size: int = 1) -> dict:
    """Normal distribution operations."""
    from scipy.stats import norm

    dist = norm(loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="t",
    category="distributions",
    description="Student's t distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--df", "type": float, "default": 1.0, "help": "Degrees of freedom"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_t(
    op: str, x: str = None, df: float = 1.0, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Student's t distribution operations."""
    from scipy.stats import t

    dist = t(df=df, loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="chi2",
    category="distributions",
    description="Chi-squared distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--df", "type": float, "default": 1.0, "help": "Degrees of freedom"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_chi2(
    op: str, x: str = None, df: float = 1.0, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Chi-squared distribution operations."""
    from scipy.stats import chi2

    dist = chi2(df=df, loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="f",
    category="distributions",
    description="F distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--dfn", "type": float, "default": 1.0, "help": "Numerator degrees of freedom"},
        {"name": "--dfd", "type": float, "default": 1.0, "help": "Denominator degrees of freedom"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_f(
    op: str,
    x: str = None,
    dfn: float = 1.0,
    dfd: float = 1.0,
    loc: float = 0.0,
    scale: float = 1.0,
    size: int = 1,
) -> dict:
    """F distribution operations."""
    from scipy.stats import f

    dist = f(dfn=dfn, dfd=dfd, loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="expon",
    category="distributions",
    description="Exponential distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale (1/lambda)"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_expon(op: str, x: str = None, loc: float = 0.0, scale: float = 1.0, size: int = 1) -> dict:
    """Exponential distribution operations."""
    from scipy.stats import expon

    dist = expon(loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="uniform",
    category="distributions",
    description="Uniform distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Lower bound"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Width (upper - lower)"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_uniform(
    op: str, x: str = None, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Uniform distribution operations."""
    from scipy.stats import uniform

    dist = uniform(loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="gamma",
    category="distributions",
    description="Gamma distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--a", "type": float, "default": 1.0, "help": "Shape parameter"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_gamma(
    op: str, x: str = None, a: float = 1.0, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Gamma distribution operations."""
    from scipy.stats import gamma

    dist = gamma(a=a, loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="beta",
    category="distributions",
    description="Beta distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--a", "type": float, "default": 1.0, "help": "Alpha shape parameter"},
        {"name": "--b", "type": float, "default": 1.0, "help": "Beta shape parameter"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_beta(
    op: str,
    x: str = None,
    a: float = 1.0,
    b: float = 1.0,
    loc: float = 0.0,
    scale: float = 1.0,
    size: int = 1,
) -> dict:
    """Beta distribution operations."""
    from scipy.stats import beta

    dist = beta(a=a, b=b, loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="lognorm",
    category="distributions",
    description="Log-normal distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--s", "type": float, "default": 1.0, "help": "Shape parameter (sigma of log)"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale (exp(mu))"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_lognorm(
    op: str, x: str = None, s: float = 1.0, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Log-normal distribution operations."""
    from scipy.stats import lognorm

    dist = lognorm(s=s, loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s_stat, k = dist.stats(moments="mvsk")
        return {
            "result": {
                "mean": float(m),
                "var": float(v),
                "skew": float(s_stat),
                "kurtosis": float(k),
            }
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="weibull_min",
    category="distributions",
    description="Weibull minimum distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--c", "type": float, "default": 1.0, "help": "Shape parameter"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_weibull_min(
    op: str, x: str = None, c: float = 1.0, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Weibull minimum distribution operations."""
    from scipy.stats import weibull_min

    dist = weibull_min(c=c, loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="pareto",
    category="distributions",
    description="Pareto distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--b", "type": float, "default": 1.0, "help": "Shape parameter"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_pareto(
    op: str, x: str = None, b: float = 1.0, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Pareto distribution operations."""
    from scipy.stats import pareto

    dist = pareto(b=b, loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="cauchy",
    category="distributions",
    description="Cauchy distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location (x0)"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale (gamma)"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_cauchy(op: str, x: str = None, loc: float = 0.0, scale: float = 1.0, size: int = 1) -> dict:
    """Cauchy distribution operations."""
    from scipy.stats import cauchy

    dist = cauchy(loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        # Cauchy has undefined moments, stats returns nan
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="laplace",
    category="distributions",
    description="Laplace distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location (mu)"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale (b)"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_laplace(
    op: str, x: str = None, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Laplace distribution operations."""
    from scipy.stats import laplace

    dist = laplace(loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="logistic",
    category="distributions",
    description="Logistic distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location (mu)"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale (s)"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_logistic(
    op: str, x: str = None, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Logistic distribution operations."""
    from scipy.stats import logistic

    dist = logistic(loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="gumbel_r",
    category="distributions",
    description="Gumbel right (maximum) distribution",
    args=[
        {"name": "op", "help": "Operation: pdf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pdf/cdf/ppf"},
        {"name": "--loc", "type": float, "default": 0.0, "help": "Location (mu)"},
        {"name": "--scale", "type": float, "default": 1.0, "help": "Scale (beta)"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_gumbel_r(
    op: str, x: str = None, loc: float = 0.0, scale: float = 1.0, size: int = 1
) -> dict:
    """Gumbel right distribution operations."""
    from scipy.stats import gumbel_r

    dist = gumbel_r(loc=loc, scale=scale)
    if op == "pdf":
        return {"result": float(dist.pdf(float(x)))}
    elif op == "cdf":
        return {"result": float(dist.cdf(float(x)))}
    elif op == "ppf":
        return {"result": float(dist.ppf(float(x)))}
    elif op == "rvs":
        return {"result": dist.rvs(size=size).tolist() if size > 1 else float(dist.rvs())}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pdf|cdf|ppf|rvs|stats")


@math_command(
    name="poisson",
    category="distributions",
    description="Poisson distribution (discrete)",
    args=[
        {"name": "op", "help": "Operation: pmf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pmf/cdf/ppf"},
        {"name": "--mu", "type": float, "default": 1.0, "help": "Rate parameter (lambda)"},
        {"name": "--loc", "type": int, "default": 0, "help": "Location"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_poisson(op: str, x: str = None, mu: float = 1.0, loc: int = 0, size: int = 1) -> dict:
    """Poisson distribution operations."""
    from scipy.stats import poisson

    dist = poisson(mu=mu, loc=loc)
    if op == "pmf" or op == "pdf":
        return {"result": float(dist.pmf(int(float(x))))}
    elif op == "cdf":
        return {"result": float(dist.cdf(int(float(x))))}
    elif op == "ppf":
        return {"result": int(dist.ppf(float(x)))}
    elif op == "rvs":
        samples = dist.rvs(size=size)
        return {"result": samples.tolist() if size > 1 else int(samples)}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pmf|cdf|ppf|rvs|stats")


@math_command(
    name="binom",
    category="distributions",
    description="Binomial distribution (discrete)",
    args=[
        {"name": "op", "help": "Operation: pmf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pmf/cdf/ppf"},
        {"name": "--n", "type": int, "default": 1, "help": "Number of trials"},
        {"name": "--p", "type": float, "default": 0.5, "help": "Probability of success"},
        {"name": "--loc", "type": int, "default": 0, "help": "Location"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_binom(
    op: str, x: str = None, n: int = 1, p: float = 0.5, loc: int = 0, size: int = 1
) -> dict:
    """Binomial distribution operations."""
    from scipy.stats import binom

    dist = binom(n=n, p=p, loc=loc)
    if op == "pmf" or op == "pdf":
        return {"result": float(dist.pmf(int(float(x))))}
    elif op == "cdf":
        return {"result": float(dist.cdf(int(float(x))))}
    elif op == "ppf":
        return {"result": int(dist.ppf(float(x)))}
    elif op == "rvs":
        samples = dist.rvs(size=size)
        return {"result": samples.tolist() if size > 1 else int(samples)}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pmf|cdf|ppf|rvs|stats")


@math_command(
    name="nbinom",
    category="distributions",
    description="Negative binomial distribution (discrete)",
    args=[
        {"name": "op", "help": "Operation: pmf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pmf/cdf/ppf"},
        {"name": "--n", "type": int, "default": 1, "help": "Number of successes"},
        {"name": "--p", "type": float, "default": 0.5, "help": "Probability of success"},
        {"name": "--loc", "type": int, "default": 0, "help": "Location"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_nbinom(
    op: str, x: str = None, n: int = 1, p: float = 0.5, loc: int = 0, size: int = 1
) -> dict:
    """Negative binomial distribution operations."""
    from scipy.stats import nbinom

    dist = nbinom(n=n, p=p, loc=loc)
    if op == "pmf" or op == "pdf":
        return {"result": float(dist.pmf(int(float(x))))}
    elif op == "cdf":
        return {"result": float(dist.cdf(int(float(x))))}
    elif op == "ppf":
        return {"result": int(dist.ppf(float(x)))}
    elif op == "rvs":
        samples = dist.rvs(size=size)
        return {"result": samples.tolist() if size > 1 else int(samples)}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pmf|cdf|ppf|rvs|stats")


@math_command(
    name="geom",
    category="distributions",
    description="Geometric distribution (discrete)",
    args=[
        {"name": "op", "help": "Operation: pmf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pmf/cdf/ppf"},
        {"name": "--p", "type": float, "default": 0.5, "help": "Probability of success"},
        {"name": "--loc", "type": int, "default": 0, "help": "Location"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_geom(op: str, x: str = None, p: float = 0.5, loc: int = 0, size: int = 1) -> dict:
    """Geometric distribution operations."""
    from scipy.stats import geom

    dist = geom(p=p, loc=loc)
    if op == "pmf" or op == "pdf":
        return {"result": float(dist.pmf(int(float(x))))}
    elif op == "cdf":
        return {"result": float(dist.cdf(int(float(x))))}
    elif op == "ppf":
        return {"result": int(dist.ppf(float(x)))}
    elif op == "rvs":
        samples = dist.rvs(size=size)
        return {"result": samples.tolist() if size > 1 else int(samples)}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pmf|cdf|ppf|rvs|stats")


@math_command(
    name="hypergeom",
    category="distributions",
    description="Hypergeometric distribution (discrete)",
    args=[
        {"name": "op", "help": "Operation: pmf|cdf|ppf|rvs|stats"},
        {"name": "x", "nargs": "?", "default": None, "help": "Value for pmf/cdf/ppf"},
        {"name": "--M", "type": int, "default": 20, "help": "Total population size"},
        {
            "name": "--n",
            "type": int,
            "default": 7,
            "help": "Number of success states in population",
        },
        {"name": "--N", "type": int, "default": 12, "help": "Number of draws"},
        {"name": "--loc", "type": int, "default": 0, "help": "Location"},
        {"name": "--size", "type": int, "default": 1, "help": "Number of samples for rvs"},
    ],
)
def cmd_hypergeom(
    op: str, x: str = None, M: int = 20, n: int = 7, N: int = 12, loc: int = 0, size: int = 1
) -> dict:
    """Hypergeometric distribution operations."""
    from scipy.stats import hypergeom

    dist = hypergeom(M=M, n=n, N=N, loc=loc)
    if op == "pmf" or op == "pdf":
        return {"result": float(dist.pmf(int(float(x))))}
    elif op == "cdf":
        return {"result": float(dist.cdf(int(float(x))))}
    elif op == "ppf":
        return {"result": int(dist.ppf(float(x)))}
    elif op == "rvs":
        samples = dist.rvs(size=size)
        return {"result": samples.tolist() if size > 1 else int(samples)}
    elif op == "stats":
        m, v, s, k = dist.stats(moments="mvsk")
        return {
            "result": {"mean": float(m), "var": float(v), "skew": float(s), "kurtosis": float(k)}
        }
    else:
        raise ValueError(f"Unknown operation: {op}. Use pmf|cdf|ppf|rvs|stats")


# =============================================================================
# MAIN CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = create_main_parser(
        "scipy_compute",
        "SciPy computation CLI - optimization and scientific computing",
        epilog=__doc__,
    )
    sys.exit(main_cli(parser, get_registry()))
