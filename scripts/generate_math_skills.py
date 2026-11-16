#!/usr/bin/env python3
"""
USAGE: Generate math skills from Ragie-indexed textbooks.

Examples:
    # Dry run - show what would be generated
    uv run python scripts/generate_math_skills.py --tier 1 --dry-run

    # Generate Tier 1 skills
    uv run python scripts/generate_math_skills.py --tier 1

    # Generate specific category only
    uv run python scripts/generate_math_skills.py --tier 1 --category real-analysis
"""

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()


def sanitize_for_yaml(text: str) -> str:
    """Sanitize text for use in YAML frontmatter.

    Removes newlines, collapses whitespace, escapes quotes, truncates.
    """
    # Remove newlines and collapse whitespace
    sanitized = ' '.join(text.split())
    # Remove characters that break YAML
    sanitized = sanitized.replace('"', "'").replace(':', ' -')
    # Truncate to reasonable length
    if len(sanitized) > 80:
        sanitized = sanitized[:77] + "..."
    return sanitized


@dataclass
class MathSkillSpec:
    """Specification for a math skill.

    Extends the basic SkillSpec with math-specific fields.
    """
    name: str                          # e.g., "limits"
    category: str                      # e.g., "real-analysis"
    tier: int                          # 1-5
    description: str                   # Brief description
    when_to_use: str                   # When to activate this skill
    techniques: list[str]              # Key techniques from Ragie
    decision_tree: str                 # Problem-solving decision tree
    tool_commands: dict[str, str]      # Tool -> example command mapping
    triggers: dict[str, list[str]] = field(
        default_factory=lambda: {"keywords": [], "intentPatterns": []}
    )

# Tier -> Category -> Topics mapping
TIER_TOPICS = {
    1: {
        "real-analysis": ["limits", "continuity", "convergence"],
        "linear-algebra": ["matrices", "eigenvalues", "vector-spaces"],
    },
    2: {
        "abstract-algebra": ["groups", "rings", "fields"],
        "topology": ["open-sets", "compactness", "connectedness"],
        "complex-analysis": ["analytic-functions", "contour-integrals", "residues"],
    },
    3: {
        "numerical-methods": ["interpolation", "numerical-integration", "root-finding"],
        "odes-pdes": ["first-order-odes", "second-order-odes", "boundary-value-problems"],
        "optimization": ["convex-optimization", "gradient-methods", "constrained-optimization"],
        "information-theory": ["entropy", "channel-capacity", "source-coding"],
    },
    4: {
        "mathematical-logic": ["propositional-logic", "predicate-logic", "proof-theory"],
        "category-theory": ["categories-functors", "natural-transformations", "limits-colimits"],
    },
    5: {
        "measure-theory": ["sigma-algebras", "lebesgue-measure", "integration-theory"],
        "functional-analysis": ["banach-spaces", "hilbert-spaces", "operator-theory"],
        "graph-number-theory": ["graph-algorithms", "prime-numbers", "modular-arithmetic"],
    },
}

# Decision trees for Tier 1 topics
DECISION_TREES = {
    "limits": """
1. **Direct Substitution**
   - Try plugging in the value directly
   - If you get a determinate form, that's the answer

2. **Indeterminate Form? (0/0, inf/inf)**
   - Try algebraic manipulation (factor, rationalize)
   - Try L'Hopital's rule: `sympy_compute.py diff` on numerator/denominator

3. **Squeeze Theorem**
   - If bounded: find g(x) <= f(x) <= h(x) where lim g = lim h
   - Verify bounds with `z3_solve.py prove`

4. **Epsilon-Delta Proof**
   - For rigorous proof: set up |f(x) - L| < epsilon
   - Find delta in terms of epsilon
   - Verify with `math_scratchpad.py verify`
""",
    "continuity": """
1. **Check Definition**
   - f(a) exists (function defined at point)
   - lim_{x->a} f(x) exists
   - lim_{x->a} f(x) = f(a)

2. **Use SymPy for Limit Check**
   - `sympy_compute.py limit "f(x)" --var x --at a`
   - Compare with f(a)

3. **Piecewise Functions**
   - Check left and right limits separately
   - `sympy_compute.py limit "f(x)" --var x --at a --dir left`

4. **Verify with Z3**
   - `z3_solve.py prove "limit_exists implies continuous"`
""",
    "convergence": """
1. **Identify Sequence/Series Type**
   - Geometric series: |r| < 1 converges
   - p-series: p > 1 converges
   - Alternating series: check decreasing + limit 0

2. **Apply Convergence Tests**
   - Ratio test: `sympy_compute.py limit "a_{n+1}/a_n"`
   - Root test: `sympy_compute.py limit "a_n^(1/n)"`
   - Comparison test: find bounding series

3. **Verify Bounds**
   - Use `z3_solve.py prove` for inequality bounds
   - Check monotonicity with derivatives

4. **Compute Sum (if convergent)**
   - `sympy_compute.py sum "a_n" --var n --from 0 --to oo`
""",
    "matrices": """
1. **Identify Matrix Type**
   - Square, symmetric, orthogonal, diagonal?
   - Check properties with `sympy_compute.py matrix_type`

2. **Basic Operations**
   - Multiplication: `sympy_compute.py matmul "A" "B"`
   - Inverse: `sympy_compute.py inverse "A"`
   - Transpose: `sympy_compute.py transpose "A"`

3. **Solve Linear Systems**
   - Ax = b: `sympy_compute.py linsolve "A" "b"`
   - Check consistency with `z3_solve.py sat`

4. **Decompositions**
   - LU: `sympy_compute.py lu "A"`
   - QR: `sympy_compute.py qr "A"`
   - SVD: `sympy_compute.py svd "A"`
""",
    "eigenvalues": """
1. **Compute Characteristic Polynomial**
   - det(A - lambda*I) = 0
   - `sympy_compute.py charpoly "[[a,b],[c,d]]" --var lam`

2. **Find Eigenvalues**
   - Solve characteristic polynomial
   - `sympy_compute.py eigenvalues "[[1,2],[3,4]]"`

3. **Find Eigenvectors**
   - For each eigenvalue lambda: solve (A - lambda*I)v = 0
   - `sympy_compute.py eigenvectors "[[1,2],[3,4]]"`

4. **Verify**
   - Check Av = lambda*v with `z3_solve.py prove`
   - Verify algebraic/geometric multiplicity
""",
    "vector-spaces": """
1. **Check Subspace**
   - Contains zero vector?
   - Closed under addition?
   - Closed under scalar multiplication?
   - Verify with `z3_solve.py prove`

2. **Linear Independence**
   - Set up Ax = 0 where columns are vectors
   - `sympy_compute.py nullspace "A"`
   - Trivial nullspace = independent

3. **Basis and Dimension**
   - Find spanning set, remove dependent vectors
   - `sympy_compute.py rref "A"` to find pivot columns
   - Dimension = number of pivots

4. **Change of Basis**
   - Find transition matrix P
   - New coords = P^(-1) * old coords
   - `sympy_compute.py inverse "P"`
""",
    # Tier 2: Abstract Algebra
    "groups": """
1. **Is G a group under operation *?**
   - Check closure: a,b in G implies a*b in G?
   - Check associativity: (a*b)*c = a*(b*c)?
   - Check identity: exists e such that e*a = a*e = a?
   - Check inverses: for all a exists a^(-1) such that a*a^(-1) = e?
   - Verify with `z3_solve.py prove "group_axioms"`

2. **Subgroup Test**
   - Show H is non-empty (usually by showing e in H)
   - Show that for all a, b in H: ab^(-1) in H
   - `z3_solve.py prove "subgroup_criterion"`

3. **Homomorphism Proof**
   - Verify phi(ab) = phi(a)phi(b) for all a, b in G1
   - Note: phi(e1) = e2 and phi(a^(-1)) = phi(a)^(-1) follow automatically
   - `sympy_compute.py simplify "phi(a*b) - phi(a)*phi(b)"`

4. **Order and Structure**
   - Element order: smallest n where a^n = e
   - Group order: |G| = number of elements
   - Lagrange: |H| divides |G| for subgroup H
""",
    "rings": """
1. **Is R a ring?**
   - (R, +) is an abelian group
   - Multiplication is associative
   - Distributive laws: a(b+c) = ab + ac and (a+b)c = ac + bc
   - `z3_solve.py prove "ring_axioms"`

2. **Ring Properties**
   - Commutative ring: ab = ba for all a, b?
   - Ring with unity: exists 1 such that 1*a = a*1 = a?
   - Integral domain: ab = 0 implies a = 0 or b = 0?
   - `z3_solve.py prove "integral_domain"`

3. **Ideals**
   - I is ideal if: I is additive subgroup AND for all r in R, a in I: ra in I, ar in I
   - Principal ideal: (a) = {ra : r in R}
   - `sympy_compute.py simplify "r*a"` for ideal multiplication

4. **Ring Homomorphisms**
   - phi(a + b) = phi(a) + phi(b)
   - phi(ab) = phi(a)phi(b)
   - phi(1) = 1 (for rings with unity)
""",
    "fields": """
1. **Is F a field?**
   - (F, +) is an abelian group with identity 0
   - (F \\ {0}, *) is an abelian group with identity 1
   - Distributive law holds
   - `z3_solve.py prove "field_axioms"`

2. **Field Extensions**
   - E is extension of F if F is subfield of E
   - Degree [E:F] = dimension of E as F-vector space
   - `sympy_compute.py minpoly "alpha" --var x` for minimal polynomial

3. **Characteristic**
   - char(F) = smallest n > 0 where n*1 = 0, or 0 if none exists
   - char(F) is 0 or prime
   - For finite field: |F| = p^n where p = char(F)

4. **Algebraic Elements**
   - alpha is algebraic over F if it satisfies polynomial with coefficients in F
   - `sympy_compute.py solve "p(alpha) = 0"` for algebraic relations
""",
    # Tier 2: Topology
    "open-sets": """
1. **Is f: X -> Y continuous?**
   - For metric spaces: x_n -> x implies f(x_n) -> f(x)?
   - For general spaces: f^(-1)(open) = open?
   - For products: Check each coordinate function
   - `z3_solve.py prove "preimage_open"`

2. **Open Set Verification**
   - For metric spaces: for all x in U, exists epsilon > 0 with B(x,epsilon) subset U
   - `z3_solve.py prove "ball_contained"` with epsilon witnesses

3. **Topological Properties**
   - Interior: int(A) = largest open subset of A
   - Closure: cl(A) = smallest closed superset of A
   - Boundary: bd(A) = cl(A) \\ int(A)

4. **Continuity Tests**
   - Epsilon-delta: for all epsilon > 0, exists delta > 0: d(x,a) < delta implies d(f(x),f(a)) < epsilon
   - `z3_solve.py prove "epsilon_delta_bound"`
""",
    "compactness": """
1. **Is X compact?**
   - If X subset R^n: Is X closed AND bounded? (Heine-Borel)
   - If X is metric: Does every sequence have convergent subsequence?
   - General: Does every open cover have finite subcover?
   - `z3_solve.py prove "bounded_and_closed"`

2. **Compactness Tests**
   - Heine-Borel (R^n): closed + bounded = compact
   - Sequential: every sequence has convergent subsequence
   - `sympy_compute.py limit "a_n" --var n` to check convergence

3. **Product Spaces**
   - Tychonoff: product of compact spaces is compact
   - Finite products preserve compactness directly

4. **Consequences of Compactness**
   - Continuous image of compact is compact
   - Continuous real function on compact attains max/min
   - `sympy_compute.py maximum "f(x)" --var x --domain "[a,b]"`
""",
    "connectedness": """
1. **Is X connected?**
   - Strategy 1 - Contradiction:
     * Assume X = U union V where U, V are disjoint, non-empty, and open
     * Derive a contradiction
   - Strategy 2 - Path connectedness:
     * Show for all x,y in X, exists continuous path f: [0,1] -> X with f(0)=x, f(1)=y
   - Strategy 3 - Fan lemma:
     * If {A_i} are connected sharing a common point, then union A_i is connected

2. **Connectedness Proofs**
   - Show no separation exists
   - `z3_solve.py prove "no_separation"`
   - Use intermediate value theorem for R subsets

3. **Path Connectedness**
   - Construct explicit path: f(t) = (1-t)x + ty for convex sets
   - `sympy_compute.py simplify "(1-t)*x + t*y"` to verify path

4. **Components**
   - Connected component: maximal connected subset containing x
   - Path component: maximal path-connected subset containing x
""",
    # Tier 2: Complex Analysis
    "analytic-functions": """
1. **Is f analytic at z0?**
   - Check Cauchy-Riemann equations: du/dx = dv/dy, du/dy = -dv/dx
   - Check if f has power series expansion around z0
   - Check if f is differentiable in neighborhood of z0
   - `sympy_compute.py diff "u" --var x` and `sympy_compute.py diff "v" --var y`

2. **Cauchy-Riemann Verification**
   - Write f(z) = u(x,y) + iv(x,y)
   - Compute partial derivatives
   - Verify: du/dx = dv/dy AND du/dy = -dv/dx
   - `z3_solve.py prove "cauchy_riemann"`

3. **Power Series**
   - f(z) = sum_{n=0}^{inf} a_n (z - z0)^n
   - Radius of convergence: R = 1/limsup |a_n|^(1/n)
   - `sympy_compute.py series "f(z)" --var z --at z0`

4. **Analytic Continuation**
   - Extend f beyond original domain via power series
   - Identity theorem: if f = g on set with limit point, then f = g everywhere
""",
    "contour-integrals": """
1. **Integral Type Selection**
   - For integral_{-inf}^{inf} f(x)dx where f decays like 1/x^a, a > 1:
     * Use semicircular contour (upper or lower half-plane)
   - For integral involving e^{ix} or trigonometric functions:
     * Close in upper half-plane for e^{ix} (Jordan's lemma)
     * Close in lower half-plane for e^{-ix}
   - For integral_0^{2pi} f(cos theta, sin theta)d theta:
     * Substitute z = e^{i theta}, use unit circle contour
   - For integrand with branch cuts:
     * Use keyhole or dogbone contour around cuts

2. **Contour Setup**
   - Identify singularities and their locations
   - Choose contour that encloses desired singularities
   - `sympy_compute.py solve "f(z) = inf"` to find poles

3. **Jordan's Lemma**
   - For integral over semicircle of radius R:
   - If |f(z)| -> 0 as |z| -> inf, semicircular contribution vanishes

4. **Compute with Residue Theorem**
   - oint_C f(z)dz = 2*pi*i * (sum of residues inside C)
   - `sympy_compute.py residue "f(z)" --var z --at z0`
""",
    "residues": """
1. **Computing Residues**
   - Simple pole at z0:
     * Res(f, z0) = lim_{z->z0} (z - z0)f(z)
     * `sympy_compute.py limit "(z - z0)*f(z)" --var z --at z0`
   - Pole of order n:
     * Res(f, z0) = (1/(n-1)!) * lim d^{n-1}/dz^{n-1}[(z-z0)^n f(z)]
     * `sympy_compute.py diff "((z-z0)**n)*f(z)" --var z --order n-1`
   - L'Hopital shortcut for f = g/h with simple pole:
     * Res(f, z0) = g(z0)/h'(z0)

2. **Identify Pole Order**
   - Simple pole: (z - z0)f(z) has finite limit
   - Order n: (z - z0)^n f(z) has finite limit, but (z - z0)^{n-1} f(z) doesn't
   - `sympy_compute.py limit "(z - z0)**n * f(z)" --var z --at z0`

3. **Essential Singularities**
   - Neither pole nor removable (e.g., e^{1/z} at z=0)
   - Compute residue via Laurent series
   - `sympy_compute.py series "exp(1/z)" --var z --at 0`

4. **Apply Residue Theorem**
   - oint_C f(z)dz = 2*pi*i * (sum of residues inside C)
   - Count only poles INSIDE the contour
   - `z3_solve.py prove "pole_inside_contour"`
""",
    # Tier 3: Numerical Methods
    "interpolation": """
1. **Assess Data Characteristics**
   - How many data points? Spacing uniform or non-uniform?
   - Is data smooth or noisy?
   - Need derivatives at endpoints?

2. **Select Interpolation Method**
   - Few points (<10): Polynomial (Lagrange, Newton)
   - Many points, smooth data: Cubic splines
   - Noisy data: Smoothing splines or least squares
   - High dimensions: Use simplex-based (n+1 neighbors vs 2^n)

3. **Implement with SciPy**
   - `scipy.interpolate.CubicSpline(x, y)` - natural cubic spline
   - `scipy.interpolate.make_interp_spline(x, y, k=3)` - B-spline
   - `scipy.interpolate.interp1d(x, y, kind='cubic')` - 1D interpolation

4. **Validate Results**
   - Check for Runge's phenomenon at boundaries (high-degree polynomials)
   - Cross-validate: leave-one-out error estimation
   - Visual inspection of interpolated curve
   - `sympy_compute.py limit "interp_error" --at boundaries`

5. **High-Dimensional Considerations**
   - Coxeter-Freudenthal-Kuhn triangulation for O(n log n) point location
   - Barycentric subdivision for balanced performance
""",
    "numerical-integration": """
1. **Identify Integral Type**
   - Definite integral over finite interval?
   - Improper integral (infinite bounds or singularities)?
   - Multiple dimensions?

2. **Select Quadrature Method**
   - Smooth function, finite interval: Gaussian quadrature
   - Oscillatory integrand: specialized methods (Filon, Levin)
   - Singularity at endpoint: adaptive methods
   - `scipy.integrate.quad(f, a, b)` for general 1D

3. **Adaptive Integration**
   - Let algorithm subdivide where needed
   - Specify error tolerances (rtol, atol)
   - `scipy.integrate.quad(f, a, b, epsabs=1e-8, epsrel=1e-8)`

4. **Multiple Dimensions**
   - `scipy.integrate.dblquad` for 2D
   - `scipy.integrate.tplquad` for 3D
   - Monte Carlo for higher dimensions

5. **Verify Accuracy**
   - Compare with known analytic solutions
   - Check convergence by refining tolerance
   - `sympy_compute.py integrate "f(x)" --var x --from a --to b`
""",
    "root-finding": """
1. **Characterize the Problem**
   - Single root or multiple roots?
   - Bracketed (know interval containing root)?
   - Derivatives available?

2. **Method Selection**
   | Situation | Method | Implementation |
   |-----------|--------|----------------|
   | Bracketed, no derivatives | Bisection, Brent | `scipy.optimize.brentq` |
   | Derivatives available | Newton-Raphson | `scipy.optimize.newton` |
   | No derivatives | Secant method | `scipy.optimize.newton` (no fprime) |
   | System of equations | `scipy.optimize.fsolve` | Requires Jacobian ideally |

3. **Implement Root Finding**
   - `scipy.optimize.brentq(f, a, b)` - guaranteed convergence if bracketed
   - `scipy.optimize.newton(f, x0, fprime=df)` - quadratic convergence near root
   - For systems: `scipy.optimize.fsolve(F, x0)`

4. **Handle Multiple Roots**
   - Deflation: divide out found roots
   - Multiple starting points
   - `sympy_compute.py solve "f(x)" --var x` for symbolic solutions

5. **Verify Solutions**
   - Check |f(root)| < tolerance
   - Verify root is in expected domain
   - `z3_solve.py prove "f(root) == 0"`
""",
    # Tier 3: ODEs and PDEs
    "first-order-odes": """
1. **Classify the ODE**
   - Linear: y' + P(x)y = Q(x)?
   - Separable: y' = f(x)g(y)?
   - Exact: M(x,y)dx + N(x,y)dy = 0 with dM/dy = dN/dx?
   - Bernoulli: y' + P(x)y = Q(x)y^n?

2. **Select Solution Method**
   | Type | Method |
   |------|--------|
   | Separable | Separate and integrate |
   | Linear | Integrating factor e^{int P dx} |
   | Exact | Find potential function |
   | Bernoulli | Substitute v = y^{1-n} |

3. **Numerical Solution (IVP)**
   - `scipy.integrate.solve_ivp(f, [t0, tf], y0, method='RK45')`
   - For stiff systems: `method='Radau'` or `method='BDF'`
   - Adaptive step size: specify rtol/atol, not step size

4. **Verify Solution**
   - Substitute back into ODE
   - Check initial/boundary conditions
   - `sympy_compute.py dsolve "y' + y = x" --ics "{y(0): 1}"`

5. **Phase Portrait (Autonomous)**
   - Find equilibria: f(y*) = 0
   - Analyze stability: sign of f'(y*)
   - `z3_solve.py solve "dy/dt == 0"`
""",
    "second-order-odes": """
1. **Classify the ODE**
   - Constant coefficients: ay'' + by' + cy = f(x)?
   - Variable coefficients: y'' + P(x)y' + Q(x)y = R(x)?
   - Cauchy-Euler: x^2 y'' + bxy' + cy = 0?

2. **Homogeneous with Constant Coefficients**
   - Characteristic equation: ar^2 + br + c = 0
   - Distinct real roots: y = c1*e^{r1*x} + c2*e^{r2*x}
   - Repeated root: y = (c1 + c2*x)e^{r*x}
   - Complex roots a +/- bi: y = e^{ax}(c1*cos(bx) + c2*sin(bx))
   - `sympy_compute.py solve "a*r**2 + b*r + c" --var r`

3. **Particular Solution (Non-homogeneous)**
   - Undetermined coefficients: guess based on f(x)
   - Variation of parameters: y_p = u1*y1 + u2*y2
   - `sympy_compute.py dsolve "y'' + y = sin(x)"`

4. **Numerical Solution**
   - Convert to first-order system: let v = y', then v' = y''
   - `solve_ivp(system, [t0, tf], [y0, v0])`

5. **Boundary Value Problems**
   - Shooting method: guess initial slope, iterate
   - `scipy.integrate.solve_bvp(ode, bc, x, y_init)`
""",
    "boundary-value-problems": """
1. **Problem Classification**
   - Two-point BVP: conditions at x=a and x=b?
   - Sturm-Liouville: eigenvalue problem?
   - Mixed conditions: Dirichlet, Neumann, Robin?

2. **Shooting Method**
   - Convert BVP to IVP
   - Guess missing initial conditions
   - Iterate to satisfy boundary conditions
   - `scipy.integrate.solve_ivp` + root finding

3. **Finite Difference Method**
   - Discretize domain: x_i = a + i*h
   - Replace derivatives with differences: y'' ~ (y_{i+1} - 2y_i + y_{i-1})/h^2
   - Solve resulting linear system
   - `sympy_compute.py linsolve "tridiagonal_matrix" "boundary_vector"`

4. **Collocation/BVP Solver**
   - `scipy.integrate.solve_bvp(ode, bc, x, y_init)`
   - Provide initial mesh and guess
   - Check residual for accuracy

5. **Eigenvalue Problems**
   - Sturm-Liouville form: -(p(x)y')' + q(x)y = lambda*w(x)*y
   - Eigenvalues are real if p, w > 0
   - Eigenfunctions orthogonal with weight w
   - `sympy_compute.py eigenvalues "sturm_liouville_matrix"`
""",
    # Tier 3: Optimization
    "convex-optimization": """
1. **Verify Convexity**
   - Objective function: Hessian positive semidefinite?
   - Constraint set: intersection of convex sets?
   - `z3_solve.py prove "hessian_psd"`

2. **Problem Classification**
   | Type | Solver |
   |------|--------|
   | Linear Programming | `scipy.optimize.linprog` |
   | Quadratic Programming | `scipy.optimize.minimize(method='SLSQP')` |
   | General Convex | Interior point methods |
   | Semidefinite | CVXPY with SDP solver |

3. **Standard Form**
   - minimize f(x) subject to g_i(x) <= 0, h_j(x) = 0
   - Convert max to min by negating
   - Convert >= to <= by negating

4. **KKT Conditions (Necessary & Sufficient)**
   - Stationarity: grad L = 0
   - Primal feasibility: g_i(x) <= 0, h_j(x) = 0
   - Dual feasibility: lambda_i >= 0
   - Complementary slackness: lambda_i * g_i(x) = 0
   - `z3_solve.py prove "kkt_conditions"`

5. **Solve and Verify**
   - `scipy.optimize.minimize(f, x0, constraints=cons)`
   - Check constraint satisfaction
   - Verify solution is global minimum (convex guarantees this)
""",
    "gradient-methods": """
1. **Basic Gradient Descent**
   - Update: x_{k+1} = x_k - alpha * grad f(x_k)
   - Step size alpha: fixed, diminishing, or line search
   - Convergence: O(1/k) for convex, linear for strongly convex

2. **Step Size Selection**
   | Method | Approach |
   |--------|----------|
   | Fixed | alpha constant (requires tuning) |
   | Backtracking | Armijo condition: f(x - alpha*grad) <= f(x) - c*alpha*||grad||^2 |
   | Exact line search | minimize f(x - alpha*grad) over alpha |
   | Adaptive | Adam, RMSprop (ML applications) |

3. **Accelerated Methods**
   - Momentum: add velocity term
   - Nesterov: look-ahead gradient
   - Conjugate gradient: for quadratic functions
   - `scipy.optimize.minimize(f, x0, method='CG')` - conjugate gradient

4. **Newton's Method**
   - Update: x_{k+1} = x_k - H^{-1} * grad f
   - Requires Hessian (expensive but quadratic convergence)
   - Quasi-Newton (BFGS): approximate Hessian
   - `scipy.optimize.minimize(f, x0, method='BFGS')`

5. **Convergence Diagnostics**
   - Monitor ||grad f|| < tolerance
   - Check function value decrease
   - Watch for oscillation (step size too large)
   - `sympy_compute.py diff "f" --var x` for gradient
""",
    "constrained-optimization": """
1. **Constraint Classification**
   - Equality: h(x) = 0
   - Inequality: g(x) <= 0
   - Bounds: l <= x <= u

2. **Lagrangian Method (Equality Constraints)**
   - L(x, lambda) = f(x) + sum lambda_j * h_j(x)
   - Solve: grad_x L = 0 and h(x) = 0
   - `sympy_compute.py solve "grad_L_system"`

3. **KKT Conditions (Inequality Constraints)**
   - Extend Lagrangian with mu_i for g_i(x) <= 0
   - Complementary slackness: mu_i * g_i(x) = 0
   - `z3_solve.py prove "kkt_satisfied"`

4. **Penalty and Barrier Methods**
   - Penalty: add P(x) = rho * sum max(0, g_i(x))^2
   - Barrier: add B(x) = -sum log(-g_i(x)) for interior point
   - Increase penalty/decrease barrier parameter iteratively

5. **SciPy Constrained Optimization**
   - `scipy.optimize.minimize(f, x0, method='SLSQP', constraints=cons)`
   - constraints = [{'type': 'eq', 'fun': h}, {'type': 'ineq', 'fun': lambda x: -g(x)}]
   - bounds = [(l1, u1), (l2, u2), ...]
""",
    # Tier 3: Information Theory
    "entropy": """
1. **Shannon Entropy**
   - H(X) = -sum p(x) log2 p(x)
   - Maximum for uniform distribution: H_max = log2(n)
   - Minimum = 0 for deterministic (one outcome certain)
   - `scipy.stats.entropy(p, base=2)` for discrete

2. **Entropy Properties**
   - Non-negative: H(X) >= 0
   - Concave in p
   - Chain rule: H(X,Y) = H(X) + H(Y|X)
   - `z3_solve.py prove "entropy_nonnegative"`

3. **Joint and Conditional Entropy**
   - H(X,Y) = -sum sum p(x,y) log2 p(x,y)
   - H(Y|X) = H(X,Y) - H(X)
   - H(Y|X) <= H(Y) with equality iff independent

4. **Differential Entropy (Continuous)**
   - h(X) = -integral f(x) log f(x) dx
   - Can be negative!
   - Gaussian: h(X) = 0.5 * log2(2*pi*e*sigma^2)
   - `sympy_compute.py integrate "-f(x)*log(f(x))" --var x`

5. **Maximum Entropy Principle**
   - Given constraints, max entropy distribution is least biased
   - Uniform for no constraints
   - Exponential for E[X] = mu constraint
   - Gaussian for E[X], Var[X] constraints
""",
    "channel-capacity": """
1. **Mutual Information**
   - I(X;Y) = H(X) + H(Y) - H(X,Y)
   - I(X;Y) = H(X) - H(X|Y) = H(Y) - H(Y|X)
   - Symmetric: I(X;Y) = I(Y;X)
   - `scipy.stats.entropy(p) + scipy.stats.entropy(q) - joint_entropy`

2. **Channel Model**
   - Input X, output Y, channel P(Y|X)
   - Channel matrix: rows = inputs, columns = outputs
   - Element (i,j) = P(Y=j | X=i)

3. **Channel Capacity**
   - C = max_{p(x)} I(X;Y)
   - Maximize over input distribution
   - Achieved by capacity-achieving distribution

4. **Common Channels**
   | Channel | Capacity |
   |---------|----------|
   | Binary Symmetric (BSC) | 1 - H(p) where p = crossover prob |
   | Binary Erasure (BEC) | 1 - epsilon where epsilon = erasure prob |
   | AWGN | 0.5 * log2(1 + SNR) |

5. **Blahut-Arimoto Algorithm**
   - Iterative algorithm to compute capacity
   - Alternates between optimizing p(x) and p(y|x)
   - Converges to capacity
   - `z3_solve.py prove "capacity_upper_bound"`
""",
    "source-coding": """
1. **Source Coding Theorem**
   - Minimum average code length >= H(X)
   - Achievable with optimal codes
   - `z3_solve.py prove "shannon_bound"`

2. **Huffman Coding**
   - Optimal prefix-free code for known distribution
   - Build tree: combine two least probable symbols
   - Average length: H(X) <= L < H(X) + 1
   - `sympy_compute.py simplify "expected_code_length"`

3. **Kraft Inequality**
   - For prefix-free code: sum 2^{-l_i} <= 1
   - Necessary and sufficient
   - `z3_solve.py prove "kraft_inequality"`

4. **Arithmetic Coding**
   - Approaches entropy for any distribution
   - Encodes entire message as interval [0,1)
   - Practical for adaptive/unknown distributions

5. **Rate-Distortion Theory**
   - Lossy compression: trade rate for distortion
   - R(D) = min_{p(x_hat|x): E[d(X,X_hat)]<=D} I(X;X_hat)
   - Minimum rate to achieve distortion D
   - `sympy_compute.py minimize "I(X;X_hat)" --constraint "E[d] <= D"`
""",
    # Tier 4: Mathematical Logic
    "propositional-logic": """
1. **Identify Formula Structure**
   - Classify: tautology, contradiction, or contingent?
   - Main connective: AND, OR, IMPLIES, NOT, IFF?
   - `z3_solve.py sat "formula"` to check satisfiability

2. **Truth Table Method**
   - For small formulas (<=4 variables): enumerate all valuations
   - `sympy_compute.py truthtable "p & (p -> q) -> q"`
   - Tautology = all T, Contradiction = all F

3. **Natural Deduction**
   - Apply inference rules: Modus Ponens, Modus Tollens
   - Conditional proof: assume antecedent, derive consequent
   - `z3_solve.py prove "Implies(And(p, Implies(p,q)), q)"`

4. **Semantic Tableaux**
   - Build tree by decomposing formula
   - Closed branches = contradictions
   - All branches closed = valid argument
""",
    "predicate-logic": """
1. **Quantifier Analysis**
   - Identify: ForAll (universal), Exists (existential)
   - Scope of quantifiers and free/bound variables
   - `z3_solve.py prove "ForAll([x], P(x)) implies P(a)"`

2. **Prenex Normal Form**
   - Move all quantifiers to front
   - Standardize variables to avoid capture
   - `sympy_compute.py simplify "prenex(formula)"`

3. **Skolemization (for Exists)**
   - Replace existential quantifiers with Skolem functions
   - Exists x. P(x) -> P(c) or P(f(y)) depending on scope
   - Needed for resolution-based proofs

4. **Resolution Proof**
   - Convert to CNF, negate conclusion
   - Apply resolution rule until empty clause or saturation
   - `z3_solve.py prove "resolution_valid"`

5. **Model Theory**
   - Construct countermodel to refute invalid argument
   - Finite model for finite domain
   - `z3_solve.py model "Exists([x], P(x) & Not(Q(x)))"`
""",
    "proof-theory": """
1. **Proof Strategy Selection**
   - Direct proof: assume premises, derive conclusion
   - Proof by contradiction: assume negation, derive false
   - Proof by cases: split on disjunction
   - Induction: base case + inductive step

2. **Structural Induction**
   - Define well-founded ordering on structures
   - Base: prove for minimal elements
   - Step: assume for smaller, prove for current
   - `z3_solve.py prove "induction_principle"`

3. **Cut Elimination**
   - Gentzen's Hauptsatz: cuts can be eliminated
   - Subformula property: only subformulas appear
   - Useful for proof normalization

4. **Completeness/Soundness Check**
   - Soundness: if provable then valid
   - Completeness: if valid then provable
   - `z3_solve.py prove "soundness_theorem"`

5. **Proof Verification**
   - Check each step follows from rules
   - Verify dependencies are satisfied
   - `math_scratchpad.py verify "proof_steps"`
""",
    # Tier 4: Category Theory (uses Lean 4 for formal verification)
    "categories-functors": """
1. **Verify Category Axioms**
   - Objects and morphisms (arrows) defined?
   - Identity morphism for each object: id_A: A -> A
   - Composition associative: (f . g) . h = f . (g . h)
   - Write Lean 4: `theorem assoc : (f ≫ g) ≫ h = f ≫ (g ≫ h) := Category.assoc`

2. **Check Functor Properties**
   - F: C -> D maps objects to objects, arrows to arrows
   - Preserves identity: F(id_A) = id_{F(A)}
   - Preserves composition: F(g . f) = F(g) . F(f)
   - Write Lean 4: `theorem comp : F.map (g ≫ f) = F.map g ≫ F.map f := F.map_comp`

3. **Functor Types**
   - Covariant: preserves arrow direction
   - Contravariant: reverses arrow direction
   - Faithful/Full: injective/surjective on Hom-sets
   - Equivalence: full, faithful, essentially surjective

4. **Common Functors**
   - Forgetful functor: forgets structure (e.g., Grp -> Set)
   - Free functor: left adjoint to forgetful
   - Hom functor: Hom(A, -) or Hom(-, B)
   - Power set functor: Set -> Set via X |-> P(X)

5. **Verify with Lean 4**
   - Compiler-in-the-loop: write proof, `lake build` checks
   - Mathlib has full category theory library
   - See: `.claude/skills/lean4-functors/SKILL.md` for exact syntax
""",
    "natural-transformations": """
1. **Verify Naturality**
   - eta: F => G is natural transformation between functors F, G: C -> D
   - For each f: A -> B in C, diagram commutes:
     G(f) . eta_A = eta_B . F(f)
   - Write Lean 4: `theorem nat : η.app B ≫ G.map f = F.map f ≫ η.app A := η.naturality`

2. **Component Analysis**
   - eta_A: F(A) -> G(A) for each object A
   - Each component is morphism in target category D
   - Lean 4: `def η : F ⟶ G where app := fun X => ...`

3. **Natural Isomorphism**
   - Each component eta_A is isomorphism
   - Functors F and G are naturally isomorphic
   - Notation: F ≅ G (NatIso in Mathlib)

4. **Functor Category**
   - [C, D] has functors as objects
   - Natural transformations as morphisms
   - Vertical composition: Lean 4 `CategoryTheory.NatTrans.vcomp`
   - Horizontal composition: `CategoryTheory.NatTrans.hcomp`

5. **Yoneda Lemma Application**
   - Nat(Hom(A, -), F) ~ F(A) naturally in A
   - Lean 4: `CategoryTheory.yonedaEquiv`
   - Fully embeds C into [C^op, Set]
   - See: `.claude/skills/lean4-nat-trans/SKILL.md` for exact syntax
""",
    "limits-colimits": """
1. **Identify Limit Type**
   - Product: limit of discrete diagram
   - Equalizer: limit of parallel pair f, g: A -> B
   - Pullback: limit of A -> C <- B
   - Terminal object: limit of empty diagram
   - Lean 4: `CategoryTheory.Limits` namespace

2. **Verify Universal Property**
   - Cone from L with projections pi_i: L -> D_i
   - For any cone from X, unique morphism u: X -> L
   - Triangles commute: pi_i . u = cone_i
   - Lean 4: `IsLimit.lift` gives the unique morphism

3. **Colimit (Dual)**
   - Coproduct: colimit of discrete diagram
   - Coequalizer: colimit of parallel pair
   - Pushout: colimit of A <- C -> B
   - Initial object: colimit of empty diagram

4. **Compute Limits Concretely**
   - In Set: product = Cartesian product
   - Equalizer = {x | f(x) = g(x)}
   - Pullback = {(a,b) | f(a) = g(b)}
   - `sympy_compute.py solve "f(a) == g(b)"`

5. **Preservation**
   - Right adjoint preserves limits
   - Left adjoint preserves colimits
   - Representable functors preserve limits
   - Lean 4: `Adjunction.rightAdjointPreservesLimits`
   - See: `.claude/skills/lean4-limits/SKILL.md` for exact syntax
""",
    # Tier 5: Measure Theory
    "sigma-algebras": """
1. **Verify sigma-algebra axioms**
   - X in F (whole space is measurable)
   - A in F implies A^c in F (closed under complements)
   - A_n in F implies union(A_n) in F (closed under countable unions)
   - `z3_solve.py prove "sigma_algebra_axioms"`

2. **sigma-algebra generation**
   - Start with generating collection C
   - sigma(C) = smallest sigma-algebra containing C
   - Use Dynkin's pi-lambda theorem for uniqueness

3. **Measurability verification**
   - f is measurable if f^{-1}(B) in F for all Borel B
   - Sufficient: check for open sets or intervals
   - `sympy_compute.py simplify "preimage(f, interval)"`

4. **Product sigma-algebras**
   - F1 x F2 = sigma{A x B : A in F1, B in F2}
   - Projections are measurable
""",
    "lebesgue-measure": """
1. **Outer measure construction**
   - m*(A) = inf{sum |I_n| : A subset union(I_n)}
   - `sympy_compute.py sum "length(I_n)" --var n`

2. **Caratheodory criterion**
   - E is measurable if: m*(A) = m*(A & E) + m*(A & E^c) for all A
   - `z3_solve.py prove "caratheodory_criterion"`

3. **Lebesgue measure properties**
   - Translation invariant: m(E + x) = m(E)
   - sigma-additive on measurable sets
   - m([a,b]) = b - a

4. **Regularity theorems**
   - Inner regularity: m(E) = sup{m(K) : K compact, K subset E}
   - Outer regularity: m(E) = inf{m(U) : U open, E subset U}
""",
    "integration-theory": """
1. **Simple function integration**
   - For s = sum(a_i * chi_{E_i}): integral s dmu = sum(a_i * mu(E_i))
   - `sympy_compute.py simplify "simple_integral"`

2. **Monotone Convergence Theorem (MCT)**
   - If 0 <= f_n <= f_{n+1} and f_n -> f:
   - lim integral(f_n) = integral(lim f_n)
   - Use for increasing sequences

3. **Dominated Convergence Theorem (DCT)**
   - If |f_n| <= g (integrable) and f_n -> f pointwise:
   - lim integral(f_n) = integral(f)
   - `z3_solve.py prove "dominated_convergence"`

4. **Fatou's Lemma**
   - integral(liminf f_n) <= liminf(integral f_n)
   - Use as lower bound when MCT/DCT don't apply

5. **Fubini-Tonelli**
   - For product measures: switch order of integration
   - Tonelli: non-negative functions (always valid)
   - Fubini: integrable functions
""",
    # Tier 5: Functional Analysis
    "banach-spaces": """
1. **Verify Banach space**
   - Complete normed vector space
   - Check: every Cauchy sequence converges
   - `z3_solve.py prove "completeness"`

2. **Hahn-Banach Theorem**
   - Extend bounded linear functionals
   - Separate convex sets
   - `z3_solve.py prove "extension_exists"`

3. **Open Mapping Theorem**
   - Surjective bounded operator between Banach spaces is open
   - Consequence: bounded inverse exists
   - `z3_solve.py prove "open_mapping"`

4. **Closed Graph Theorem**
   - T: X -> Y has closed graph implies T bounded
   - Strategy: verify graph closure, conclude boundedness
   - `z3_solve.py prove "closed_graph_implies_bounded"`

5. **Uniform Boundedness Principle**
   - Pointwise bounded family of operators is uniformly bounded
   - Application: prove operator families are bounded
""",
    "hilbert-spaces": """
1. **Orthogonal decomposition**
   - For closed subspace M: H = M + M^perp (direct sum)
   - Every x = P_M(x) + P_{M^perp}(x)
   - `sympy_compute.py simplify "x - projection"`

2. **Projection Theorem**
   - For closed convex C, unique nearest point exists
   - P_C is nonexpansive: ||P_C(x) - P_C(y)|| <= ||x - y||
   - `z3_solve.py prove "projection_exists_unique"`

3. **Riesz Representation**
   - Every f in H* has form f(x) = <x, y_f> for unique y_f
   - ||f|| = ||y_f||
   - `z3_solve.py prove "riesz_representation"`

4. **Parseval's Identity**
   - For orthonormal basis {e_n}: ||x||^2 = sum|<x, e_n>|^2
   - `sympy_compute.py sum "abs(<x, e_n>)**2"`

5. **Bessel's Inequality**
   - sum|<x, e_n>|^2 <= ||x||^2 for any orthonormal set
""",
    "operator-theory": """
1. **Bounded operator verification**
   - ||Tx|| <= M||x|| for some M
   - Operator norm: ||T|| = sup{||Tx|| : ||x|| = 1}
   - `z3_solve.py prove "operator_bounded"`

2. **Adjoint operator**
   - <Tx, y> = <x, T*y> defines T*
   - For matrices: T* = conjugate transpose
   - `sympy_compute.py simplify "<Tx, y> - <x, T*y>"`

3. **Spectral Theory**
   - Spectrum: sigma(T) = {lambda : T - lambda*I not invertible}
   - Self-adjoint: spectrum is real
   - `z3_solve.py prove "self_adjoint_real_spectrum"`

4. **Compact operators**
   - T compact if T(bounded set) has compact closure
   - Approximable by finite-rank operators
   - `sympy_compute.py limit "||T - T_n||" --var n`

5. **Spectral Theorem**
   - Self-adjoint compact: T = sum(lambda_n * P_n)
   - eigenvalues -> 0, eigenvectors form orthonormal basis
""",
    # Tier 5: Graph Theory & Number Theory
    "graph-algorithms": """
1. **Traversal selection**
   - BFS: shortest paths (unweighted), level structure
   - DFS: cycle detection, topological sort, SCC

2. **Shortest path algorithms**
   | Algorithm | Use Case | Complexity |
   |-----------|----------|------------|
   | Dijkstra | Non-negative weights | O((V+E) log V) |
   | Bellman-Ford | Negative weights | O(VE) |
   | Floyd-Warshall | All pairs | O(V^3) |

3. **Minimum Spanning Tree**
   - Prim's: dense graphs, greedy from vertex
   - Kruskal's: sparse graphs, union-find
   - `z3_solve.py prove "cut_property"`

4. **Network Flow**
   - Max-flow = min-cut (Ford-Fulkerson)
   - Matching via flow network
   - `sympy_compute.py linsolve "flow_conservation"`

5. **Graph properties**
   - Spectral: eigenvalues of adjacency matrix
   - Connectivity: via DFS/BFS
   - Coloring: greedy or SAT reduction
""",
    "prime-numbers": """
1. **Primality testing hierarchy**
   - Trial division: O(sqrt(n)), exact
   - Miller-Rabin: O(k log^3 n), probabilistic
   - AKS: O(log^6 n), deterministic polynomial

2. **Factorization**
   - Trial division for small factors
   - Pollard's rho: probabilistic, medium numbers
   - Quadratic sieve: large numbers
   - `sympy_compute.py factor "n"`

3. **Prime distribution**
   - Prime Number Theorem: pi(x) ~ x/ln(x)
   - Prime gaps: p_{n+1} - p_n
   - `sympy_compute.py limit "pi(x) * ln(x) / x"`

4. **Fermat's Little Theorem**
   - a^{p-1} = 1 (mod p) for a not divisible by p
   - Use for modular exponentiation
   - `z3_solve.py prove "fermat_little"`

5. **Wilson's Theorem**
   - (p-1)! = -1 (mod p) iff p is prime
""",
    "modular-arithmetic": """
1. **Extended Euclidean Algorithm**
   - Find gcd(a,b) and x,y with ax + by = gcd(a,b)
   - Modular inverse: a^{-1} mod n when gcd(a,n) = 1
   - `sympy_compute.py solve "a*x == 1 mod n"`

2. **Chinese Remainder Theorem**
   - System x = a_i (mod m_i) with coprime m_i
   - Unique solution mod prod(m_i)
   - `z3_solve.py prove "crt_solution_exists"`

3. **Euler's Theorem**
   - a^{phi(n)} = 1 (mod n) when gcd(a,n) = 1
   - phi(p^k) = p^{k-1}(p-1)
   - `sympy_compute.py simplify "euler_phi"`

4. **Quadratic Residues**
   - Legendre symbol: (a/p) = a^{(p-1)/2} mod p
   - Quadratic reciprocity: (p/q)(q/p) = (-1)^{...}
   - Tonelli-Shanks for square roots

5. **Order and Primitive Roots**
   - ord_n(a) = smallest k with a^k = 1 (mod n)
   - Primitive root: ord_n(a) = phi(n)
""",
}

# Tool command templates for Tier 1 topics
TOOL_COMMANDS = {
    "limits": {
        "sympy_limit": 'uv run python -m runtime.harness scripts/sympy_compute.py limit "sin(x)/x" --var x --at 0',
        "sympy_diff": 'uv run python -m runtime.harness scripts/sympy_compute.py diff "x**2" --var x',
        "z3_prove": 'uv run python -m runtime.harness scripts/z3_solve.py prove "limit_bound" --vars x',
    },
    "continuity": {
        "sympy_limit": 'uv run python -m runtime.harness scripts/sympy_compute.py limit "f(x)" --var x --at a',
        "sympy_limit_left": 'uv run python -m runtime.harness scripts/sympy_compute.py limit "f(x)" --var x --at a --dir left',
        "z3_prove": 'uv run python -m runtime.harness scripts/z3_solve.py prove "continuous_at_a"',
    },
    "convergence": {
        "sympy_limit": 'uv run python -m runtime.harness scripts/sympy_compute.py limit "a_n" --var n --at oo',
        "sympy_sum": 'uv run python -m runtime.harness scripts/sympy_compute.py sum "1/n**2" --var n --from 1 --to oo',
        "z3_prove": 'uv run python -m runtime.harness scripts/z3_solve.py prove "series_bounded"',
    },
    "matrices": {
        "sympy_inverse": 'uv run python -m runtime.harness scripts/sympy_compute.py inverse "[[1,2],[3,4]]"',
        "sympy_det": 'uv run python -m runtime.harness scripts/sympy_compute.py det "[[a,b],[c,d]]"',
        "sympy_linsolve": 'uv run python -m runtime.harness scripts/sympy_compute.py linsolve "[[1,2],[3,4]]" "[5,6]"',
    },
    "eigenvalues": {
        "sympy_eigenvalues": 'uv run python -m runtime.harness scripts/sympy_compute.py eigenvalues "[[1,2],[3,4]]"',
        "sympy_charpoly": 'uv run python -m runtime.harness scripts/sympy_compute.py charpoly "[[a,b],[c,d]]" --var lam',
        "z3_verify": 'uv run python -m runtime.harness scripts/z3_solve.py sat "det(A - lambda*I) == 0"',
    },
    "vector-spaces": {
        "sympy_nullspace": 'uv run python -m runtime.harness scripts/sympy_compute.py nullspace "[[1,2,3],[4,5,6]]"',
        "sympy_rref": 'uv run python -m runtime.harness scripts/sympy_compute.py rref "[[1,2,3],[4,5,6]]"',
        "z3_prove": 'uv run python -m runtime.harness scripts/z3_solve.py prove "subspace_closed"',
    },
    # Tier 2: Abstract Algebra
    "groups": {
        "z3_group_axioms": 'uv run python -m runtime.harness scripts/z3_solve.py prove "ForAll([a,b,c], op(op(a,b),c) == op(a,op(b,c)))"',
        "z3_subgroup": 'uv run python -m runtime.harness scripts/z3_solve.py prove "subgroup_criterion"',
        "sympy_simplify": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "phi(a*b) - phi(a)*phi(b)"',
    },
    "rings": {
        "z3_ring_axioms": 'uv run python -m runtime.harness scripts/z3_solve.py prove "ForAll([a,b,c], a*(b+c) == a*b + a*c)"',
        "z3_integral_domain": 'uv run python -m runtime.harness scripts/z3_solve.py prove "a*b == 0 implies a == 0 or b == 0"',
        "sympy_ideal": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "r*a"',
    },
    "fields": {
        "z3_field_axioms": 'uv run python -m runtime.harness scripts/z3_solve.py prove "field_axioms"',
        "sympy_minpoly": 'uv run python -m runtime.harness scripts/sympy_compute.py minpoly "sqrt(2)" --var x',
        "sympy_solve": 'uv run python -m runtime.harness scripts/sympy_compute.py solve "x**2 - 2" --var x',
    },
    # Tier 2: Topology
    "open-sets": {
        "z3_preimage_open": 'uv run python -m runtime.harness scripts/z3_solve.py prove "preimage_open"',
        "z3_epsilon_delta": 'uv run python -m runtime.harness scripts/z3_solve.py prove "ForAll(eps, Exists(delta, d(x,a) < delta implies d(f(x),f(a)) < eps))"',
        "z3_ball_contained": 'uv run python -m runtime.harness scripts/z3_solve.py prove "ball_contained"',
    },
    "compactness": {
        "z3_bounded_closed": 'uv run python -m runtime.harness scripts/z3_solve.py prove "bounded_and_closed"',
        "sympy_limit": 'uv run python -m runtime.harness scripts/sympy_compute.py limit "a_n" --var n --at oo',
        "sympy_maximum": 'uv run python -m runtime.harness scripts/sympy_compute.py maximum "f(x)" --var x --domain "[a,b]"',
    },
    "connectedness": {
        "z3_no_separation": 'uv run python -m runtime.harness scripts/z3_solve.py prove "no_separation"',
        "sympy_path": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "(1-t)*x + t*y"',
        "z3_ivt": 'uv run python -m runtime.harness scripts/z3_solve.py prove "intermediate_value"',
    },
    # Tier 2: Complex Analysis
    "analytic-functions": {
        "sympy_diff_u": 'uv run python -m runtime.harness scripts/sympy_compute.py diff "u(x,y)" --var x',
        "sympy_diff_v": 'uv run python -m runtime.harness scripts/sympy_compute.py diff "v(x,y)" --var y',
        "sympy_series": 'uv run python -m runtime.harness scripts/sympy_compute.py series "exp(z)" --var z --at 0',
        "z3_cauchy_riemann": 'uv run python -m runtime.harness scripts/z3_solve.py prove "diff(u,x) == diff(v,y)"',
    },
    "contour-integrals": {
        "sympy_residue": 'uv run python -m runtime.harness scripts/sympy_compute.py residue "1/(z**2 + 1)" --var z --at I',
        "sympy_poles": 'uv run python -m runtime.harness scripts/sympy_compute.py solve "z**2 + 1" --var z',
        "sympy_integrate": 'uv run python -m runtime.harness scripts/sympy_compute.py integrate "1/(x**2 + 1)" --var x --from "-oo" --to "oo"',
    },
    "residues": {
        "sympy_residue": 'uv run python -m runtime.harness scripts/sympy_compute.py residue "1/((z-1)*(z-2))" --var z --at 1',
        "sympy_limit": 'uv run python -m runtime.harness scripts/sympy_compute.py limit "(z - z0)*f(z)" --var z --at z0',
        "sympy_laurent": 'uv run python -m runtime.harness scripts/sympy_compute.py series "exp(1/z)" --var z --at 0',
        "z3_pole_inside": 'uv run python -m runtime.harness scripts/z3_solve.py prove "abs(z0) < R"',
    },
    # Tier 3: Numerical Methods
    "interpolation": {
        "scipy_cubic_spline": "uv run python -c \"from scipy.interpolate import CubicSpline; import numpy as np; x = np.array([0,1,2,3]); y = np.array([0,1,4,9]); cs = CubicSpline(x, y); print(cs(1.5))\"",
        "scipy_bspline": "uv run python -c \"from scipy.interpolate import make_interp_spline; import numpy as np; x = np.array([0,1,2,3]); y = np.array([0,1,4,9]); bspl = make_interp_spline(x, y, k=3); print(bspl(1.5))\"",
        "sympy_lagrange": "uv run python -m runtime.harness scripts/sympy_compute.py interpolate \"[(0,0),(1,1),(2,4)]\" --var x",
    },
    "numerical-integration": {
        "scipy_quad": "uv run python -c \"from scipy.integrate import quad; import numpy as np; result, err = quad(lambda x: np.sin(x), 0, np.pi); print('Integral:', result, 'Error:', err)\"",
        "scipy_dblquad": "uv run python -c \"from scipy.integrate import dblquad; result, err = dblquad(lambda y, x: x*y, 0, 1, 0, 1); print('Integral:', result)\"",
        "sympy_integrate": "uv run python -m runtime.harness scripts/sympy_compute.py integrate \"sin(x)\" --var x --from 0 --to \"pi\"",
    },
    "root-finding": {
        "scipy_brentq": "uv run python -c \"from scipy.optimize import brentq; root = brentq(lambda x: x**2 - 2, 0, 2); print('Root:', root)\"",
        "scipy_newton": "uv run python -c \"from scipy.optimize import newton; root = newton(lambda x: x**2 - 2, 1.0, fprime=lambda x: 2*x); print('Root:', root)\"",
        "sympy_solve": "uv run python -m runtime.harness scripts/sympy_compute.py solve \"x**3 - x - 1\" --var x",
    },
    # Tier 3: ODEs and PDEs
    "first-order-odes": {
        "scipy_solve_ivp": "uv run python -c \"from scipy.integrate import solve_ivp; sol = solve_ivp(lambda t, y: -y, [0, 5], [1]); print('y(5) =', sol.y[0][-1])\"",
        "sympy_dsolve": "uv run python -m runtime.harness scripts/sympy_compute.py dsolve \"Derivative(y,x) + y\" --ics \"{y(0): 1}\"",
        "z3_equilibrium": "uv run python -m runtime.harness scripts/z3_solve.py solve \"f(y_star) == 0\"",
    },
    "second-order-odes": {
        "scipy_solve_ivp_system": "uv run python -c \"from scipy.integrate import solve_ivp; sol = solve_ivp(lambda t, Y: [Y[1], -Y[0]], [0, 10], [1, 0]); print('y(10) =', sol.y[0][-1])\"",
        "sympy_charpoly": "uv run python -m runtime.harness scripts/sympy_compute.py solve \"r**2 + r + 1\" --var r",
        "sympy_dsolve_2nd": "uv run python -m runtime.harness scripts/sympy_compute.py dsolve \"Derivative(y,x,2) + y\"",
    },
    "boundary-value-problems": {
        "scipy_solve_bvp": "uv run python -c \"from scipy.integrate import solve_bvp; import numpy as np; ode = lambda x, y: [y[1], -y[0]]; bc = lambda ya, yb: [ya[0], yb[0]-1]; x = np.linspace(0, np.pi, 10); y = np.zeros((2, 10)); sol = solve_bvp(ode, bc, x, y); print('Solution at pi/2:', sol.sol(np.pi/2)[0])\"",
        "sympy_linsolve": "uv run python -m runtime.harness scripts/sympy_compute.py linsolve \"tridiagonal_matrix\" \"boundary_vector\"",
        "z3_sturm_liouville": "uv run python -m runtime.harness scripts/z3_solve.py prove \"eigenvalue_real\"",
    },
    # Tier 3: Optimization
    "convex-optimization": {
        "scipy_linprog": "uv run python -c \"from scipy.optimize import linprog; res = linprog([-1, -2], A_ub=[[1, 1], [2, 1]], b_ub=[4, 5]); print('Optimal:', -res.fun, 'at x=', res.x)\"",
        "scipy_minimize": "uv run python -c \"from scipy.optimize import minimize; res = minimize(lambda x: (x[0]-1)**2 + (x[1]-2)**2, [0, 0]); print('Minimum at', res.x)\"",
        "z3_kkt": "uv run python -m runtime.harness scripts/z3_solve.py prove \"kkt_conditions\"",
    },
    "gradient-methods": {
        "scipy_bfgs": "uv run python -c \"from scipy.optimize import minimize; res = minimize(lambda x: (x[0]-1)**2 + 100*(x[1]-x[0]**2)**2, [0, 0], method='BFGS'); print('Rosenbrock min at', res.x)\"",
        "scipy_cg": "uv run python -c \"from scipy.optimize import minimize; res = minimize(lambda x: x[0]**2 + x[1]**2, [1, 1], method='CG'); print('Min at', res.x)\"",
        "sympy_gradient": "uv run python -m runtime.harness scripts/sympy_compute.py diff \"x**2 + y**2\" --var \"[x, y]\"",
    },
    "constrained-optimization": {
        "scipy_slsqp": "uv run python -c \"from scipy.optimize import minimize; cons = dict(type='eq', fun=lambda x: x[0] + x[1] - 1); res = minimize(lambda x: x[0]**2 + x[1]**2, [1, 1], method='SLSQP', constraints=cons); print('Min at', res.x)\"",
        "sympy_lagrangian": "uv run python -m runtime.harness scripts/sympy_compute.py solve \"[2*x - lam, 2*y - lam, x + y - 1]\" --vars \"[x, y, lam]\"",
        "z3_kkt_satisfied": "uv run python -m runtime.harness scripts/z3_solve.py prove \"complementary_slackness\"",
    },
    # Tier 3: Information Theory
    "entropy": {
        "scipy_entropy": "uv run python -c \"from scipy.stats import entropy; p = [0.25, 0.25, 0.25, 0.25]; H = entropy(p, base=2); print('Entropy:', H, 'bits')\"",
        "scipy_kl_div": "uv run python -c \"from scipy.stats import entropy; p = [0.5, 0.5]; q = [0.9, 0.1]; kl = entropy(p, q); print('KL divergence:', kl)\"",
        "sympy_entropy": "uv run python -m runtime.harness scripts/sympy_compute.py simplify \"-p*log(p, 2) - (1-p)*log(1-p, 2)\"",
    },
    "channel-capacity": {
        "scipy_mutual_info": "uv run python -c \"from scipy.stats import entropy; p = [0.5, 0.5]; q = [0.6, 0.4]; H_X = entropy(p, base=2); H_Y = entropy(q, base=2); print('H(X)=', H_X, 'H(Y)=', H_Y)\"",
        "sympy_bsc_capacity": "uv run python -m runtime.harness scripts/sympy_compute.py simplify \"1 + p*log(p, 2) + (1-p)*log(1-p, 2)\"",
        "z3_capacity_bound": "uv run python -m runtime.harness scripts/z3_solve.py prove \"I(X;Y) <= H(X)\"",
    },
    "source-coding": {
        "scipy_huffman": "uv run python -c \"print('Huffman codes for a=0.5, b=0.25, c=0.125, d=0.125: a=0, b=10, c=110, d=111')\"",
        "sympy_kraft": "uv run python -m runtime.harness scripts/sympy_compute.py simplify \"2**(-l1) + 2**(-l2) + 2**(-l3) + 2**(-l4)\"",
        "z3_shannon_bound": "uv run python -m runtime.harness scripts/z3_solve.py prove \"expected_length >= entropy\"",
    },
    # Tier 4: Mathematical Logic
    "propositional-logic": {
        "z3_sat": 'uv run python -m runtime.harness scripts/z3_solve.py sat "And(p, Implies(p, q), Not(q))"',
        "z3_tautology": 'uv run python -m runtime.harness scripts/z3_solve.py prove "Implies(And(p, Implies(p, q)), q)"',
        "sympy_truthtable": 'uv run python -m runtime.harness scripts/sympy_compute.py truthtable "p & (p >> q) >> q"',
        "z3_modus_ponens": 'uv run python -m runtime.harness scripts/z3_solve.py prove "Implies(And(p, Implies(p,q)), q)"',
    },
    "predicate-logic": {
        "z3_forall": 'uv run python -m runtime.harness scripts/z3_solve.py prove "ForAll([x], Implies(P(x), Q(x)))"',
        "z3_exists": 'uv run python -m runtime.harness scripts/z3_solve.py sat "Exists([x], And(P(x), Not(Q(x))))"',
        "z3_universal_instantiation": 'uv run python -m runtime.harness scripts/z3_solve.py prove "Implies(ForAll([x], P(x)), P(a))"',
        "z3_model": 'uv run python -m runtime.harness scripts/z3_solve.py model "Exists([x], P(x))"',
    },
    "proof-theory": {
        "z3_induction_base": 'uv run python -m runtime.harness scripts/z3_solve.py prove "P(0)"',
        "z3_induction_step": 'uv run python -m runtime.harness scripts/z3_solve.py prove "ForAll([n], Implies(P(n), P(n+1)))"',
        "z3_soundness": 'uv run python -m runtime.harness scripts/z3_solve.py prove "Implies(derivable(phi), valid(phi))"',
        "math_verify": 'uv run python -m runtime.harness scripts/math_scratchpad.py verify "proof_structure"',
    },
    # Tier 4: Category Theory (Lean 4 + Mathlib for formal verification)
    "categories-functors": {
        "lean4_category": '# Lean 4 with Mathlib: import CategoryTheory.Category.Basic',
        "lean4_functor": '# Lean 4: theorem map_comp (F : C ⥤ D) : F.map (g ≫ f) = F.map g ≫ F.map f := F.map_comp',
        "lean4_build": 'lake build  # Compiler-in-the-loop verification',
    },
    "natural-transformations": {
        "lean4_naturality": '# Lean 4: theorem nat : η.app B ≫ G.map f = F.map f ≫ η.app A := η.naturality',
        "lean4_nat_trans": '# Lean 4: def η : F ⟶ G where app := fun X => component_X',
        "lean4_yoneda": '# Lean 4: CategoryTheory.yonedaEquiv -- Yoneda lemma',
        "lean4_build": 'lake build  # Compiler-in-the-loop verification',
    },
    "limits-colimits": {
        "lean4_limit": '# Lean 4: import CategoryTheory.Limits.Shapes.Products',
        "lean4_universal": '# Lean 4: IsLimit.lift cone -- unique morphism from universal property',
        "sympy_pullback": 'uv run python -m runtime.harness scripts/sympy_compute.py solve "f(a) == g(b)"',
        "lean4_build": 'lake build  # Compiler-in-the-loop verification',
    },
    # Tier 5: Measure Theory
    "sigma-algebras": {
        "z3_sigma_axioms": 'uv run python -m runtime.harness scripts/z3_solve.py prove "X_in_F and closed_under_complement and closed_under_countable_union"',
        "z3_dynkin_pi_lambda": 'uv run python -m runtime.harness scripts/z3_solve.py prove "pi_system_subset_lambda implies sigma_equal"',
        "sympy_preimage": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "f_inv(A_union_B) == f_inv(A) | f_inv(B)"',
    },
    "lebesgue-measure": {
        "sympy_outer_measure": 'uv run python -m runtime.harness scripts/sympy_compute.py sum "length(I_n)" --var n --from 1 --to oo',
        "z3_caratheodory": 'uv run python -m runtime.harness scripts/z3_solve.py prove "mu(A) == mu(A & E) + mu(A & E_complement)"',
        "sympy_borel_sets": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "open_set_countable_union"',
    },
    "integration-theory": {
        "sympy_simple_integral": 'uv run python -m runtime.harness scripts/sympy_compute.py integrate "sum(a_i * chi_E_i)" --var mu',
        "z3_mct": 'uv run python -m runtime.harness scripts/z3_solve.py prove "f_n_increasing implies lim_integral_equals_integral_lim"',
        "z3_dct": 'uv run python -m runtime.harness scripts/z3_solve.py prove "abs(f_n) <= g and g_integrable implies limit_exchange"',
        "sympy_fatou": 'uv run python -m runtime.harness scripts/sympy_compute.py limit "liminf(integral_f_n)" --comparison "integral_liminf_f_n"',
    },
    # Tier 5: Functional Analysis
    "banach-spaces": {
        "z3_completeness": 'uv run python -m runtime.harness scripts/z3_solve.py prove "cauchy_sequence implies convergent"',
        "z3_open_mapping": 'uv run python -m runtime.harness scripts/z3_solve.py prove "T_surjective_bounded implies T_open"',
        "z3_closed_graph": 'uv run python -m runtime.harness scripts/z3_solve.py prove "graph_closed implies T_bounded"',
        "sympy_norm": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "norm(alpha*x + beta*y)"',
    },
    "hilbert-spaces": {
        "sympy_inner_product": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "<x + y, z> == <x,z> + <y,z>"',
        "z3_projection": 'uv run python -m runtime.harness scripts/z3_solve.py prove "x - P_M(x) in M_perp"',
        "z3_riesz": 'uv run python -m runtime.harness scripts/z3_solve.py prove "bounded_linear_functional iff inner_product_form"',
        "sympy_parseval": 'uv run python -m runtime.harness scripts/sympy_compute.py sum "abs(<x, e_n>)**2" --var n --from 1 --to oo',
    },
    "operator-theory": {
        "z3_bounded_operator": 'uv run python -m runtime.harness scripts/z3_solve.py prove "norm(Tx) <= M*norm(x)"',
        "sympy_adjoint": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "<Tx, y> - <x, T_star_y>"',
        "z3_spectral": 'uv run python -m runtime.harness scripts/z3_solve.py prove "self_adjoint implies real_spectrum"',
        "sympy_compact": 'uv run python -m runtime.harness scripts/sympy_compute.py limit "norm(T - T_n)" --var n --at oo',
    },
    # Tier 5: Graph Theory & Number Theory
    "graph-algorithms": {
        "sympy_adjacency": 'uv run python -m runtime.harness scripts/sympy_compute.py eigenvalues "adjacency_matrix"',
        "z3_dijkstra": 'uv run python -m runtime.harness scripts/z3_solve.py prove "d[v] >= d[u] + w(u,v) for all edges"',
        "z3_mst_cut": 'uv run python -m runtime.harness scripts/z3_solve.py prove "min_edge_crossing_cut_in_mst"',
        "sympy_flow": 'uv run python -m runtime.harness scripts/sympy_compute.py linsolve "flow_conservation_equations"',
    },
    "prime-numbers": {
        "sympy_factor": 'uv run python -m runtime.harness scripts/sympy_compute.py factor "n"',
        "z3_primality": 'uv run python -m runtime.harness scripts/z3_solve.py prove "no_divisor_between_1_and_sqrt_n"',
        "sympy_prime_count": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "pi(x) ~ x/ln(x)"',
        "z3_fermat_little": 'uv run python -m runtime.harness scripts/z3_solve.py prove "a**(p-1) == 1 mod p"',
    },
    "modular-arithmetic": {
        "sympy_mod_inverse": 'uv run python -m runtime.harness scripts/sympy_compute.py solve "a*x == 1 mod n" --var x',
        "z3_crt": 'uv run python -m runtime.harness scripts/z3_solve.py prove "solution_exists_iff_pairwise_coprime"',
        "sympy_euler_phi": 'uv run python -m runtime.harness scripts/sympy_compute.py simplify "phi(p**k) == p**(k-1)*(p-1)"',
        "z3_quadratic_residue": 'uv run python -m runtime.harness scripts/z3_solve.py prove "legendre_symbol_multiplicative"',
    },
}


def sanitize_technique(text: str) -> str:
    """Clean Ragie chunk text for use in skills.

    Removes PDF artifacts, page numbers, garbled LaTeX, and extracts
    meaningful sentences only.

    Args:
        text: Raw chunk text from Ragie

    Returns:
        Cleaned text suitable for skill documentation
    """
    # Remove PDF filename header (first line if it ends with .pdf)
    lines = text.split('\n')
    if lines and lines[0].strip().endswith('.pdf'):
        lines = lines[1:]
    text = '\n'.join(lines)

    # Remove common LaTeX artifacts from PDF extraction
    latex_artifacts = [
        (r'\(cid:\d+\)', ''),           # (cid:15) -> ''
        (r'\(cid:[^\)]+\)', ''),         # any (cid:XXX) pattern
        (r'[\uf8f0-\uf8ff]', ''),        # Unicode private use area (ligatures)
        (r'[\ufb00-\ufb0f]', ''),        # More private use (Latin ligatures)
    ]
    for pattern, replacement in latex_artifacts:
        text = re.sub(pattern, replacement, text)

    # Remove page numbers (standalone numbers on their own line or at line boundaries)
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)

    # Remove problem numbers at start of sentences (e.g., "32. A point x")
    text = re.sub(r'^\d{1,3}\.\s+', '', text, flags=re.MULTILINE)

    # Remove section headers (e.g., "PROBLEMS", "Section 1.5")
    text = re.sub(r'^(PROBLEMS|Section \d+\.\d+|Chapter \d+)\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)

    # Collapse multiple newlines and whitespace
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    # Extract complete sentences (starts with capital, ends with period)
    # This filters out fragments and partial equations
    sentences = re.findall(r'[A-Z][^.!?]*[.!?]', text)

    # Filter sentences: must be substantial (>30 chars) and not just numbers/symbols
    good_sentences = []
    for s in sentences:
        s = s.strip()
        # Skip sentences that are mostly non-alphabetic
        alpha_ratio = sum(1 for c in s if c.isalpha()) / max(len(s), 1)
        # Skip sentences with too many mathematical symbols (suggests fragmented equation)
        math_symbols = sum(1 for c in s if c in '≤≥∫∑∏∈∉⊂⊃∀∃→←↔λμδεσπ')
        if len(s) > 30 and alpha_ratio > 0.5 and math_symbols < 5:
            good_sentences.append(s)

    # Join up to 3 good sentences
    result = ' '.join(good_sentences[:3])

    return result.strip()


def extract_techniques_from_chunks(chunks: list[dict]) -> list[str]:
    """Extract and clean technique descriptions from Ragie chunks.

    Args:
        chunks: List of scored_chunks from Ragie

    Returns:
        List of cleaned technique descriptions
    """
    techniques = []
    seen_content = set()  # Avoid duplicates

    for chunk in chunks[:10]:  # Check more chunks to find good ones
        text = chunk.get("text", "").strip()
        if not text:
            continue

        cleaned = sanitize_technique(text)

        # Skip if too short after cleaning
        if len(cleaned) < 50:
            continue

        # Skip near-duplicates (first 100 chars match)
        content_key = cleaned[:100].lower()
        if content_key in seen_content:
            continue
        seen_content.add(content_key)

        # Add source metadata
        doc_name = chunk.get("document_name", "")
        # Extract short name from full PDF filename
        short_name = doc_name.split('--')[0].strip() if '--' in doc_name else doc_name
        short_name = short_name.replace('.pdf', '').strip()
        if short_name.endswith('...'):
            short_name = short_name.rstrip('.')

        if short_name:
            techniques.append(f"[{short_name}] {cleaned}")
        else:
            techniques.append(cleaned)

        # Stop after 5 good techniques
        if len(techniques) >= 5:
            break

    return techniques


def query_ragie_for_topic(topic: str, category: str, top_k: int = 10) -> list[dict]:
    """Query Ragie for techniques related to a math topic.

    Args:
        topic: e.g., "limits", "eigenvalues"
        category: e.g., "real-analysis", "linear-algebra"
        top_k: Number of chunks to retrieve

    Returns:
        List of scored_chunks from Ragie
    """
    api_key = os.environ.get("RAGIE_API_KEY")
    if not api_key:
        raise RuntimeError("RAGIE_API_KEY not set")

    url = "https://api.ragie.ai/retrievals"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Construct a query that extracts problem-solving techniques
    query = f"What are the key techniques and problem-solving strategies for {topic} in {category.replace('-', ' ')}?"

    payload = {
        "query": query,
        "partition": "math-textbooks",
        "top_k": top_k,
        "rerank": True,
    }

    response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json().get("scored_chunks", [])


def render_math_skill(spec: MathSkillSpec) -> str:
    """Render a MathSkillSpec to SKILL.md content."""
    lines = [
        "---",
        f"name: {spec.name}",
        f'description: "{spec.description}"',
        "allowed-tools: [Bash, Read]",
        "---",
        "",
        f"# {spec.name.replace('-', ' ').title()}",
        "",
        "## When to Use",
        "",
        spec.when_to_use,
        "",
        "## Decision Tree",
        "",
        spec.decision_tree,
        "",
        "## Tool Commands",
        "",
    ]

    for tool, cmd in spec.tool_commands.items():
        lines.append(f"### {tool.title()}")
        lines.append("```bash")
        lines.append(cmd)
        lines.append("```")
        lines.append("")

    # Key Techniques section removed - Decision Tree provides actionable steps
    # RAG chunks were noisy and not directly useful

    lines.append("## Cognitive Tools Reference")
    lines.append("")
    lines.append("See `.claude/skills/math-mode/SKILL.md` for full tool documentation.")
    lines.append("")

    return "\n".join(lines)


def synthesize_skill(
    topic: str,
    category: str,
    tier: int,
    ragie_chunks: list[dict]
) -> MathSkillSpec:
    """Synthesize a MathSkillSpec from Ragie data and templates.

    Args:
        topic: Topic name (e.g., "limits")
        category: Category name (e.g., "real-analysis")
        tier: Tier number (1-5)
        ragie_chunks: Chunks from Ragie query

    Returns:
        Complete MathSkillSpec ready for rendering
    """
    techniques = extract_techniques_from_chunks(ragie_chunks)

    # Get decision tree (with fallback)
    decision_tree = DECISION_TREES.get(topic, f"TODO: Add decision tree for {topic}")

    # Get tool commands (with fallback)
    tool_commands = TOOL_COMMANDS.get(topic, {
        "sympy": f'uv run python -m runtime.harness scripts/sympy_compute.py solve "{topic}_equation"',
        "z3": f'uv run python -m runtime.harness scripts/z3_solve.py prove "{topic}_theorem"',
    })

    # Generate clean human-readable description
    description = f"Problem-solving strategies for {topic.replace('-', ' ')} in {category.replace('-', ' ')}"

    # Generate when_to_use
    when_to_use = f"Use this skill when working on {topic} problems in {category.replace('-', ' ')}."

    # Generate triggers
    triggers = {
        "keywords": [topic, category.replace('-', ' ')] + topic.split('-'),
        "intentPatterns": [f"(solve|prove|find|compute).*?{topic}"],
    }

    return MathSkillSpec(
        name=topic,
        category=category,
        tier=tier,
        description=description,
        when_to_use=when_to_use,
        techniques=techniques,
        decision_tree=decision_tree,
        tool_commands=tool_commands,
        triggers=triggers,
    )


def write_skill(spec: MathSkillSpec, dry_run: bool = False, base_path: Path | None = None) -> Path:
    """Write a MathSkillSpec to the skills directory.

    Args:
        spec: The skill specification
        dry_run: If True, don't write, just return path
        base_path: Base path for skills directory (default: .claude/skills)

    Returns:
        Path where skill was (or would be) written
    """
    base = base_path or Path(".claude/skills")
    skill_dir = base / "math" / spec.category / spec.name
    skill_path = skill_dir / "SKILL.md"

    if dry_run:
        print(f"[DRY-RUN] Would write: {skill_path}")
        return skill_path

    # Create directory
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Render and write
    content = render_math_skill(spec)
    skill_path.write_text(content)

    print(f"Wrote: {skill_path}")
    return skill_path


async def generate_tier(
    tier: int,
    category_filter: str | None = None,
    dry_run: bool = False,
    base_path: Path | None = None
) -> list[Path]:
    """Generate all skills for a tier.

    Args:
        tier: Tier number (1-5)
        category_filter: Optional category to limit generation
        dry_run: If True, don't write files
        base_path: Base path for skills directory (default: .claude/skills)

    Returns:
        List of paths where skills were written
    """
    if tier not in TIER_TOPICS:
        raise ValueError(f"Tier {tier} not defined yet")

    categories = TIER_TOPICS[tier]
    if category_filter:
        if category_filter not in categories:
            raise ValueError(f"Category {category_filter} not in tier {tier}")
        categories = {category_filter: categories[category_filter]}

    paths = []
    for category, topics in categories.items():
        for topic in topics:
            print(f"Generating skill for {category}/{topic}...")

            # Query Ragie
            try:
                chunks = query_ragie_for_topic(topic, category)
            except Exception as e:
                print(f"  Warning: Ragie query failed: {e}")
                chunks = []

            # Synthesize skill
            spec = synthesize_skill(topic, category, tier, chunks)

            # Write skill
            path = write_skill(spec, dry_run=dry_run, base_path=base_path)
            paths.append(path)

    return paths


def main():
    parser = argparse.ArgumentParser(description="Generate math skills from Ragie textbooks")
    parser.add_argument("--tier", type=int, required=True, choices=[1, 2, 3, 4, 5], help="Skill tier (1=Foundation)")
    parser.add_argument("--category", type=str, help="Limit to specific category (e.g., real-analysis)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without writing files")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    try:
        paths = asyncio.run(generate_tier(
            tier=args.tier,
            category_filter=args.category,
            dry_run=args.dry_run
        ))

        if args.json:
            print(json.dumps({"generated": [str(p) for p in paths], "count": len(paths)}))
        else:
            print(f"\nGenerated {len(paths)} skills for Tier {args.tier}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
