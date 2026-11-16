---
name: math-mode
description: Symbolic math (SymPy) and constraint solving (Z3) - cognitive prosthetics for exact computation
allowed-tools: [Bash, Read]
---

# Math Mode

Cognitive prosthetics for exact mathematical computation. Use SymPy for symbolic algebra, Z3 for proofs and constraints, and Math Scratchpad for step verification.

## When to Use

- Solve equations symbolically (not approximate)
- Integrate or differentiate expressions
- Prove mathematical theorems
- Verify step-by-step reasoning
- Check constraint satisfiability
- Simplify expressions

## Quick Reference

```bash
# Solve equation
uv run python -m runtime.harness scripts/sympy_compute.py \
    solve "x**2 - 4 = 0" --var x --domain real

# Prove theorem
uv run python -m runtime.harness scripts/z3_solve.py \
    prove "x + y == y + x" --vars x y --type int

# Verify reasoning step
uv run python -m runtime.harness scripts/math_scratchpad.py \
    verify "x = 2 implies x^2 = 4"

# Verify chain of reasoning
uv run python -m runtime.harness scripts/math_scratchpad.py \
    chain --steps '["x^2 - 4 = 0", "(x-2)(x+2) = 0", "x = 2 or x = -2"]'
```

## Tool Selection

| Need | Tool | Command |
|------|------|---------|
| Solve equations | SymPy | `sympy_compute.py solve` |
| Integrate/differentiate | SymPy | `sympy_compute.py integrate/diff` |
| Simplify expressions | SymPy | `sympy_compute.py simplify` |
| Prove theorems | Z3 | `z3_solve.py prove` |
| Check satisfiability | Z3 | `z3_solve.py sat` |
| Optimize | Z3 | `z3_solve.py optimize` |
| Verify reasoning | Scratchpad | `math_scratchpad.py verify/chain` |

## SymPy Commands

### Solve
```bash
uv run python -m runtime.harness scripts/sympy_compute.py \
    solve "x**2 - 4 = 0" --var x --domain real
```

### Integrate
```bash
# Indefinite
uv run python -m runtime.harness scripts/sympy_compute.py \
    integrate "sin(x)" --var x

# Definite
uv run python -m runtime.harness scripts/sympy_compute.py \
    integrate "x" --var x --bounds 0 1
```

### Differentiate
```bash
uv run python -m runtime.harness scripts/sympy_compute.py \
    diff "x**3" --var x --order 2
```

### Simplify
```bash
uv run python -m runtime.harness scripts/sympy_compute.py \
    simplify "sin(x)**2 + cos(x)**2" --strategy trig
```

## Z3 Commands

### SAT Check
```bash
uv run python -m runtime.harness scripts/z3_solve.py \
    sat "x > 0, x < 10, x*x == 49" --type int
```

### Prove
```bash
uv run python -m runtime.harness scripts/z3_solve.py \
    prove "x + y == y + x" --vars x y --type int
```

### Optimize
```bash
uv run python -m runtime.harness scripts/z3_solve.py \
    optimize "x + y" --constraints "x >= 0, y >= 0, x + y <= 100" \
    --direction maximize --type real
```

## Math Scratchpad Commands

### Verify Step
```bash
uv run python -m runtime.harness scripts/math_scratchpad.py \
    verify "x = 2 implies x^2 = 4"
```

### Verify Chain
```bash
uv run python -m runtime.harness scripts/math_scratchpad.py \
    chain --steps '["x^2 - 4 = 0", "(x-2)(x+2) = 0", "x = 2 or x = -2"]'
```

### Explain Step
```bash
uv run python -m runtime.harness scripts/math_scratchpad.py \
    explain "d/dx(x^3) = 3*x^2"
```

## Requirements

- SymPy: symbolic math (included in deps)
- Z3: constraint solving (included in deps)
- Both installed via `uv sync`
