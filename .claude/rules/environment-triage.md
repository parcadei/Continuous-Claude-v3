# Environment Triage

When `uv sync` or `pip install` behaves unexpectedly, check the actual interpreter.

## Pattern

System Python is not authoritative if uv/venv selects a different interpreter.

## DO

```bash
# What uv ACTUALLY uses
uv run python --version

# What's pinned (this controls uv)
cat .python-version

# Confirm package is installed
uv pip show <package>

# Confirm import works in uv context
uv run python -c "import <package>; print(<package>.__version__)"
```

## Common Fix

If optional deps require Python 3.12+ but .python-version is 3.11:

```bash
echo "3.13" > .python-version
rm -rf .venv && uv venv && uv sync --all-extras
```

## DON'T

- Trust `python3 --version` when using uv
- Assume install succeeded without verifying import
- Debug further before checking interpreter version

## Source Sessions

- 2243c067: symbolica-agentica skipped due to `python_version >= 3.12` marker, but uv was using 3.11
- 4784f390: agentica import failures traced to wrong interpreter
