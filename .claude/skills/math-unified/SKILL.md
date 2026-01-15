---
name: math-unified
description: Unified math capabilities - computation, solving, and explanation. I route to the right tool.
triggers: ["calculate", "compute", "solve", "integrate", "derivative", "eigenvalue", "matrix", "simplify", "factor", "limit", "series", "differential equation", "unit convert", "explain", "what is", "how does"]
allowed-tools: [Bash, Read, Write]
priority: high
---

# /math - Unified Math Capabilities

**One entry point for all computation and explanation.** I route to the right tool based on your request.

For formal proofs, use `/prove` instead.

---

## Quick Examples

| You Say | I Use |
|---------|-------|
| "Solve x² - 4 = 0" | SymPy solve |
| "Integrate sin(x) from 0 to π" | SymPy integrate |
| "Eigenvalues of [[1,2],[3,4]]" | SymPy eigenvalues |
| "Is x² + 1 > 0 for all x?" | Z3 prove |
| "Convert 5 miles to km" | Pint |
| "Explain what a functor is" | Category theory skill |

---

## Computation Scripts

### SymPy (Symbolic Math)
```bash
uv run python "$CLAUDE_PROJECT_DIR/.claude/scripts/cc_math/sympy_compute.py" <command> <args>
```

| Command | Description | Example |
|---------|-------------|---------|
| `solve` | Solve equations | `solve "x**2 - 4" --var x` |
| `integrate` | Definite/indefinite integral | `integrate "sin(x)" --var x --lower 0 --upper pi` |
| `diff` | Derivative | `diff "x**3" --var x` |
| `simplify` | Simplify expression | `simplify "sin(x)**2 + cos(x)**2"` |
| `limit` | Compute limit | `limit "sin(x)/x" --var x --point 0` |
| `series` | Taylor expansion | `series "exp(x)" --var x --point 0 --n 5` |
| `dsolve` | Solve ODE | `dsolve "f''(x) + f(x)" --func f --var x` |
| `laplace` | Laplace transform | `laplace "sin(t)" --var t` |

**Matrix Operations:**
| Command | Description |
|---------|-------------|
| `det` | Determinant |
| `eigenvalues` | Eigenvalues |
| `eigenvectors` | Eigenvectors with multiplicities |
| `inverse` | Matrix inverse |
| `transpose` | Transpose |
| `rref` | Row echelon form |
| `rank` | Matrix rank |
| `nullspace` | Null space basis |
| `linsolve` | Linear system Ax=b |
| `charpoly` | Characteristic polynomial |

**Number Theory:**
| Command | Description |
|---------|-------------|
| `factor` | Factor polynomial |
| `factorint` | Prime factorization |
| `isprime` | Primality test |
| `gcd` | Greatest common divisor |
| `lcm` | Least common multiple |
| `modinverse` | Modular inverse |

**Combinatorics:**
| Command | Description |
|---------|-------------|
| `binomial` | C(n,k) |
| `factorial` | n! |
| `permutation` | P(n,k) |
| `partition` | Integer partitions p(n) |
| `catalan` | Catalan numbers |
| `bell` | Bell numbers |

---

### Z3 (Constraint Solving)
```bash
uv run python "$CLAUDE_PROJECT_DIR/.claude/scripts/cc_math/z3_solve.py" <command> <args>
```

| Command | Use Case |
|---------|----------|
| `sat` | Is this satisfiable? |
| `prove` | Is this always true? |
| `optimize` | Find min/max subject to constraints |

---

### Pint (Units)
```bash
uv run python "$CLAUDE_PROJECT_DIR/.claude/scripts/cc_math/pint_compute.py" convert <value> <from_unit> <to_unit>
```

Example: `convert 5 miles kilometers`

---

### Math Router (Auto-Route)
```bash
uv run python "$CLAUDE_PROJECT_DIR/.claude/scripts/cc_math/math_router.py" route "<natural language request>"
```

Returns the exact command to run. Use when unsure which script.

---

## Topic Skills (For Explanation)

When the request is "explain X" or "what is X", I reference these:

| Topic | Skill Location | Key Concepts |
|-------|----------------|--------------|
| **Abstract Algebra** | `math/abstract-algebra/` | Groups, rings, fields, homomorphisms |
| **Category Theory** | `math/category-theory/` | Functors, natural transformations, limits |
| **Complex Analysis** | `math/complex-analysis/` | Analytic functions, residues, contour integrals |
| **Functional Analysis** | `math/functional-analysis/` | Banach spaces, operators, spectra |
| **Linear Algebra** | `math/linear-algebra/` | Matrices, eigenspaces, decompositions |
| **Mathematical Logic** | `math/mathematical-logic/` | Propositional, predicate, proof theory |
| **Measure Theory** | `math/measure-theory/` | Lebesgue, σ-algebras, integration |
| **Real Analysis** | `math/real-analysis/` | Limits, continuity, convergence |
| **Topology** | `math/topology/` | Open sets, compactness, connectedness |
| **ODEs/PDEs** | `math/odes-pdes/` | Differential equations, boundary problems |
| **Optimization** | `math/optimization/` | Convex, LP, gradient methods |
| **Numerical Methods** | `math/numerical-methods/` | Approximation, error analysis |
| **Graph/Number Theory** | `math/graph-number-theory/` | Graphs, primes, modular arithmetic |
| **Information Theory** | `math/information-theory/` | Entropy, coding, channels |

---

## Routing Logic

I decide based on your request:

```
"solve/calculate/compute" → SymPy (exact symbolic)
"is X always true?" → Z3 (constraint proving)
"convert units" → Pint
"explain/what is" → Topic skill for context
"prove formally" → Redirect to /prove
```

---

## Examples

### Solve Equation
```
User: Solve x² - 5x + 6 = 0
Claude: uv run python "$CLAUDE_PROJECT_DIR/.claude/scripts/cc_math/sympy_compute.py" solve "x**2 - 5*x + 6" --var x
Result: x = 2 or x = 3
```

### Compute Eigenvalues
```
User: Find eigenvalues of [[2, 1], [1, 2]]
Claude: uv run python "$CLAUDE_PROJECT_DIR/.claude/scripts/cc_math/sympy_compute.py" eigenvalues "[[2,1],[1,2]]"
Result: {1: 1, 3: 1}  (eigenvalue 1 with multiplicity 1, eigenvalue 3 with multiplicity 1)
```

### Prove Inequality
```
User: Is x² + y² ≥ 2xy always true?
Claude: uv run python "$CLAUDE_PROJECT_DIR/.claude/scripts/cc_math/z3_solve.py" prove "x**2 + y**2 >= 2*x*y"
Result: PROVED (equivalent to (x-y)² ≥ 0)
```

### Convert Units
```
User: How many kilometers in 26.2 miles?
Claude: uv run python "$CLAUDE_PROJECT_DIR/.claude/scripts/cc_math/pint_compute.py" convert 26.2 miles kilometers
Result: 42.16 km
```

---

## When to Use /prove Instead

Use `/prove` when you need:
- Machine-verified formal proof (Lean 4)
- Category theory proofs (functors, Yoneda, etc.)
- Publication-quality verification
- Abstract algebra proofs

`/math` is for computation. `/prove` is for verification.
