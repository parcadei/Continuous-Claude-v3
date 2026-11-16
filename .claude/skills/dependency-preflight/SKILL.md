---
name: dependency-preflight
description: Diagnose and fix Python import/dependency errors systematically
allowed-tools: [Bash, Read, Write, Edit]
---

# Dependency Preflight

Systematic troubleshooting for Python import errors and dependency issues.

## When to Use

- `ModuleNotFoundError: No module named 'X'`
- `ImportError: cannot import name 'Y'`
- `pip install` or `uv sync` fails
- Tests fail due to missing dependencies
- Circular import errors

## Diagnostic Workflow

### Phase 1: Environment Check

```bash
# What Python is uv actually using?
uv run python --version

# What's pinned in the project?
cat .python-version

# Is the module installed?
uv pip show <module_name>

# Can it be imported?
uv run python -c "import <module_name>; print(<module_name>.__version__)"
```

### Phase 2: Common Fixes

**Module not installed:**
```bash
uv add <module_name>
# or with extras
uv add "<module_name>[extra1,extra2]"
```

**Wrong Python version (optional deps require 3.12+):**
```bash
echo "3.13" > .python-version
rm -rf .venv && uv venv && uv sync --all-extras
```

**Circular import:**
```python
# Move import inside function (lazy import)
def my_function():
    from module import thing  # NOT at file top
    return thing.do_stuff()
```

### Phase 3: Verify Fix

```bash
# Re-run the failing command
uv run pytest tests/unit/test_<module>.py -v

# Or verify import directly
uv run python -c "import <module_name>"
```

## Decision Tree

```
Error: ModuleNotFoundError
├── Is module in pyproject.toml?
│   ├── NO → uv add <module>
│   └── YES → Is .python-version correct?
│       ├── NO → Update .python-version, recreate venv
│       └── YES → Check for typos in import statement
│
Error: ImportError (circular)
├── Two modules import each other?
│   └── YES → Move import inside function (lazy import)
│
Error: pip/uv install fails
├── Network issue?
│   └── Try: uv sync --offline (use cached)
├── Version conflict?
│   └── Check: uv pip compile pyproject.toml
```

## Evidence

This pattern was derived from 60% of git fixes being path/environment related:
- Sessions: 2243c067, 4784f390, 5e6aada8, 4500e7cd
- Common root cause: uv using different Python than expected
