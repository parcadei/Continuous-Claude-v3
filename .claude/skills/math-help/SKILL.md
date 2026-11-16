---
name: math-help
description: Guide to the math cognitive stack - what tools exist and when to use each
triggers: ["help", "guide", "how do I", "what math", "math help", "math tools", "which tool", "math tutorial"]
---

# Math Cognitive Stack Guide

Cognitive prosthetics for exact mathematical computation. This guide helps you choose the right tool for your math task.

## Quick Reference

| I want to... | Use this | Example |
|--------------|----------|---------|
| Solve equations | sympy_compute.py solve | `solve "x**2 - 4 = 0" --var x` |
| Integrate/differentiate | sympy_compute.py | `integrate "sin(x)" --var x` |
| Compute limits | sympy_compute.py limit | `limit "sin(x)/x" --var x --to 0` |
| Matrix operations | sympy_compute.py / numpy_compute.py | `det "[[1,2],[3,4]]"` |
| Verify a reasoning step | math_scratchpad.py verify | `verify "x = 2 implies x^2 = 4"` |
| Check a proof chain | math_scratchpad.py chain | `chain --steps '[...]'` |
| Get progressive hints | math_tutor.py hint | `hint "Solve x^2 - 4 = 0" --level 2` |
| Generate practice problems | math_tutor.py generate | `generate --topic algebra --difficulty 2` |
| Prove a theorem (constraints) | z3_solve.py prove | `prove "x + y == y + x" --vars x y` |
| Check satisfiability | z3_solve.py sat | `sat "x > 0, x < 10, x*x == 49"` |
| Optimize with constraints | z3_solve.py optimize | `optimize "x + y" --constraints "..."` |
| Plot 2D/3D functions | math_plot.py | `plot2d "sin(x)" --range -10 10` |
| Arbitrary precision | mpmath_compute.py | `pi --dps 100` |
| Numerical optimization | scipy_compute.py | `minimize "x**2 + 2*x" "5"` |
| Formal machine proof | Lean 4 (lean4 skill) | `/lean4` |

## The Five Layers

### Layer 1: SymPy (Symbolic Algebra)

**When:** Exact algebraic computation - solving, calculus, simplification, matrix algebra.

**Key Commands:**
```bash
# Solve equation
uv run python -m runtime.harness scripts/sympy_compute.py \
    solve "x**2 - 5*x + 6 = 0" --var x --domain real

# Integrate
uv run python -m runtime.harness scripts/sympy_compute.py \
    integrate "sin(x)" --var x

# Definite integral
uv run python -m runtime.harness scripts/sympy_compute.py \
    integrate "x**2" --var x --bounds 0 1

# Differentiate (2nd order)
uv run python -m runtime.harness scripts/sympy_compute.py \
    diff "x**3" --var x --order 2

# Simplify (trig strategy)
uv run python -m runtime.harness scripts/sympy_compute.py \
    simplify "sin(x)**2 + cos(x)**2" --strategy trig

# Limit
uv run python -m runtime.harness scripts/sympy_compute.py \
    limit "sin(x)/x" --var x --to 0

# Matrix eigenvalues
uv run python -m runtime.harness scripts/sympy_compute.py \
    eigenvalues "[[1,2],[3,4]]"
```

**Best For:** Closed-form solutions, calculus, exact algebra.

### Layer 2: Z3 (Constraint Solving & Theorem Proving)

**When:** Proving theorems, checking satisfiability, constraint optimization.

**Key Commands:**
```bash
# Prove commutativity
uv run python -m runtime.harness scripts/z3_solve.py \
    prove "x + y == y + x" --vars x y --type int

# Check satisfiability
uv run python -m runtime.harness scripts/z3_solve.py \
    sat "x > 0, x < 10, x*x == 49" --type int

# Optimize
uv run python -m runtime.harness scripts/z3_solve.py \
    optimize "x + y" --constraints "x >= 0, y >= 0, x + y <= 100" \
    --direction maximize --type real
```

**Best For:** Logical proofs, constraint satisfaction, optimization with constraints.

### Layer 3: Math Scratchpad (Reasoning Verification)

**When:** Verifying step-by-step reasoning, checking derivation chains.

**Key Commands:**
```bash
# Verify single step
uv run python -m runtime.harness scripts/math_scratchpad.py \
    verify "x = 2 implies x^2 = 4"

# Verify with context
uv run python -m runtime.harness scripts/math_scratchpad.py \
    verify "x^2 = 4" --context '{"x": 2}'

# Verify chain of reasoning
uv run python -m runtime.harness scripts/math_scratchpad.py \
    chain --steps '["x^2 - 4 = 0", "(x-2)(x+2) = 0", "x = 2 or x = -2"]'

# Explain a step
uv run python -m runtime.harness scripts/math_scratchpad.py \
    explain "d/dx(x^3) = 3*x^2"
```

**Best For:** Checking your work, validating derivations, step-by-step verification.

### Layer 4: Math Tutor (Educational)

**When:** Learning, getting hints, generating practice problems.

**Key Commands:**
```bash
# Step-by-step solution
uv run python scripts/math_tutor.py steps "x**2 - 5*x + 6 = 0" --operation solve

# Progressive hint (level 1-5)
uv run python scripts/math_tutor.py hint "Solve x**2 - 4 = 0" --level 2

# Generate practice problem
uv run python scripts/math_tutor.py generate --topic algebra --difficulty 2
```

**Best For:** Learning, tutoring, practice.

### Layer 5: Lean 4 (Formal Proofs)

**When:** Rigorous machine-verified mathematical proofs, category theory, type theory.

**Access:** Use `/lean4` skill for full documentation.

**Best For:** Publication-grade proofs, dependent types, category theory.

## Numerical Tools

For numerical (not symbolic) computation:

### NumPy (160 functions)
```bash
# Matrix operations
uv run python scripts/numpy_compute.py det "[[1,2],[3,4]]"
uv run python scripts/numpy_compute.py inv "[[1,2],[3,4]]"
uv run python scripts/numpy_compute.py eig "[[1,2],[3,4]]"
uv run python scripts/numpy_compute.py svd "[[1,2,3],[4,5,6]]"

# Solve linear system
uv run python scripts/numpy_compute.py solve "[[3,1],[1,2]]" "[9,8]"
```

### SciPy (289 functions)
```bash
# Minimize function
uv run python scripts/scipy_compute.py minimize "x**2 + 2*x" "5"

# Find root
uv run python scripts/scipy_compute.py root "x**3 - x - 2" "1.5"

# Curve fitting
uv run python scripts/scipy_compute.py curve_fit "a*exp(-b*x)" "0,1,2,3" "1,0.6,0.4,0.2" "1,0.5"
```

### mpmath (153 functions, arbitrary precision)
```bash
# Pi to 100 decimal places
uv run python scripts/mpmath_compute.py pi --dps 100

# Arbitrary precision sqrt
uv run python -m scripts.mpmath_compute mp_sqrt "2" --dps 100
```

## Visualization

### math_plot.py
```bash
# 2D plot
uv run python scripts/math_plot.py plot2d "sin(x)" \
    --var x --range -10 10 --output plot.png

# 3D surface
uv run python scripts/math_plot.py plot3d "x**2 + y**2" \
    --xvar x --yvar y --range 5 --output surface.html

# Multiple functions
uv run python scripts/math_plot.py plot2d-multi "sin(x),cos(x)" \
    --var x --range -6.28 6.28 --output multi.png

# LaTeX rendering
uv run python scripts/math_plot.py latex "\\int e^{-x^2} dx" --output equation.png
```

## Educational Features

### 5-Level Hint System

| Level | Category | What You Get |
|-------|----------|--------------|
| 1 | Conceptual | General direction, topic identification |
| 2 | Strategic | Approach to use, technique selection |
| 3 | Tactical | Specific steps, intermediate goals |
| 4 | Computational | Intermediate results, partial solutions |
| 5 | Answer | Full solution with explanation |

**Usage:**
```bash
# Start with conceptual hint
uv run python scripts/math_tutor.py hint "integrate x*sin(x)" --level 1

# Get more specific guidance
uv run python scripts/math_tutor.py hint "integrate x*sin(x)" --level 3
```

### Step-by-Step Solutions

```bash
uv run python scripts/math_tutor.py steps "x**2 - 5*x + 6 = 0" --operation solve
```

Returns structured steps with:
- Step number and type
- From/to expressions
- Rule applied
- Justification

## Common Workflows

### Workflow 1: Solve and Verify
1. Solve with sympy_compute.py
2. Verify solution with math_scratchpad.py
3. Plot to visualize (optional)

```bash
# Solve
uv run python -m runtime.harness scripts/sympy_compute.py \
    solve "x**2 - 4 = 0" --var x

# Verify the solutions work
uv run python -m runtime.harness scripts/math_scratchpad.py \
    verify "x = 2 implies x^2 - 4 = 0"
```

### Workflow 2: Learn a Concept
1. Generate practice problem with math_tutor.py
2. Use progressive hints (level 1, then 2, etc.)
3. Get full solution if stuck

```bash
# Generate problem
uv run python scripts/math_tutor.py generate --topic calculus --difficulty 2

# Get hints progressively
uv run python scripts/math_tutor.py hint "..." --level 1
uv run python scripts/math_tutor.py hint "..." --level 2

# Full solution
uv run python scripts/math_tutor.py steps "..." --operation integrate
```

### Workflow 3: Prove and Formalize
1. Check theorem with z3_solve.py (constraint-level proof)
2. If rigorous proof needed, use Lean 4

```bash
# Quick check with Z3
uv run python -m runtime.harness scripts/z3_solve.py \
    prove "x*y == y*x" --vars x y --type int

# For formal proof, use /lean4 skill
```

## Choosing the Right Tool

```
Is it SYMBOLIC (exact answers)?
  └─ Yes → Use SymPy
      ├─ Equations → sympy_compute.py solve
      ├─ Calculus → sympy_compute.py integrate/diff/limit
      └─ Simplify → sympy_compute.py simplify

Is it a PROOF or CONSTRAINT problem?
  └─ Yes → Use Z3
      ├─ True/False theorem → z3_solve.py prove
      ├─ Find values → z3_solve.py sat
      └─ Optimize → z3_solve.py optimize

Is it NUMERICAL (approximate answers)?
  └─ Yes → Use NumPy/SciPy
      ├─ Linear algebra → numpy_compute.py
      ├─ Optimization → scipy_compute.py minimize
      └─ High precision → mpmath_compute.py

Need to VERIFY reasoning?
  └─ Yes → Use Math Scratchpad
      ├─ Single step → math_scratchpad.py verify
      └─ Chain → math_scratchpad.py chain

Want to LEARN/PRACTICE?
  └─ Yes → Use Math Tutor
      ├─ Hints → math_tutor.py hint
      └─ Practice → math_tutor.py generate

Need MACHINE-VERIFIED formal proof?
  └─ Yes → Use Lean 4 (see /lean4 skill)
```

## Related Skills

- `/math` or `/math-mode` - Quick access to the orchestration skill
- `/lean4` - Formal theorem proving with Lean 4
- `/lean4-functors` - Category theory functors
- `/lean4-nat-trans` - Natural transformations
- `/lean4-limits` - Limits and colimits

## Requirements

All math scripts are installed via:
```bash
uv sync
```

Dependencies: sympy, z3-solver, numpy, scipy, mpmath, matplotlib, plotly
