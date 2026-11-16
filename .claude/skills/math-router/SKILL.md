---
name: math-router
description: Deterministic router for math cognitive stack - maps user intent to exact CLI commands
triggers: ["math", "calculate", "compute", "solve", "integrate", "derivative", "plot", "convert", "prove"]
priority: high
---

# Math Router

**ALWAYS use this router first for math requests.**

Instead of reading individual skill documentation, call the router to get the exact command:

## Usage

```bash
# Route any math intent to get the CLI command
uv run python scripts/math_router.py route "<user's math request>"
```

## Example Workflow

1. User says: "integrate sin(x) from 0 to pi"
2. You run: `uv run python scripts/math_router.py route "integrate sin(x) from 0 to pi"`
3. Router returns:
   ```json
   {
     "command": "uv run python scripts/sympy_compute.py integrate \"sin(x)\" --var x --lower 0 --upper pi",
     "confidence": 0.95
   }
   ```
4. You execute the returned command
5. Return result to user

## Why Use The Router

- **Faster**: No need to read skill docs
- **Deterministic**: Pattern-based, not LLM inference
- **Accurate**: Extracts arguments correctly
- **Complete**: Covers 32 routes across 7 scripts

## Available Routes

| Category | Commands |
|----------|----------|
| sympy | integrate, diff, solve, simplify, limit, det, eigenvalues, inv, expand, factor, series, laplace, fourier |
| pint | convert, check |
| shapely | create, measure, pred, op |
| z3 | prove, sat, optimize |
| scratchpad | verify, explain |
| tutor | hint, steps, generate |
| plot | plot2d, plot3d, latex |

## List All Commands

```bash
# List all available routes
uv run python scripts/math_router.py list

# List routes by category
uv run python scripts/math_router.py list --category sympy
```

## Fallback

If the router returns `{"command": null}`, the intent wasn't recognized. Then:
1. Ask user to clarify
2. Or use individual skills: /sympy-compute, /z3-solve, /pint-compute, etc.
