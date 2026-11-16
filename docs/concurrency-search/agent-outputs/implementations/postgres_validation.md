# PostgreSQL Pool Parameter Validation Fix

**Date:** 2025-12-29
**Gap Reference:** Gap 7 - Negative/Zero Value Handling for Timeouts
**Status:** FIXED

---

## Problem

The `_get_pool_config()` function in `scripts/agentica/postgres_pool.py` accepted invalid values for pool configuration:

- **Negative timeout** (e.g., `-1`): Undefined behavior in asyncpg
- **Zero timeout** (e.g., `0`): Infinite wait, defeating timeout purpose
- **Negative pool size** (e.g., `-5`): Invalid configuration
- **Zero pool size** (e.g., `0`): Invalid configuration

### Original Code

```python
try:
    max_size = int(max_size_str)
except ValueError:
    max_size = 10  # Only handles non-numeric

try:
    acquire_timeout = int(acquire_timeout_str)
except ValueError:
    acquire_timeout = 30  # Only handles non-numeric
```

The code only caught `ValueError` for non-numeric strings, but did not validate that the parsed values were positive.

---

## Solution

Added validation to reject zero and negative values, defaulting to safe values:

```python
# Parse max_size with validation
try:
    max_size = int(max_size_str)
    if max_size <= 0:
        max_size = 10  # default for invalid values
except ValueError:
    max_size = 10

# Parse acquire_timeout with validation
try:
    acquire_timeout = float(acquire_timeout_str)
    if acquire_timeout <= 0:
        acquire_timeout = 30.0  # default for invalid values
except ValueError:
    acquire_timeout = 30.0
```

### Key Changes

1. **Validation for positive values**: Added `if max_size <= 0` and `if acquire_timeout <= 0` checks
2. **Float for timeout**: Changed `acquire_timeout` from `int` to `float` to support fractional seconds
3. **Updated docstring**: Documented the validation behavior

---

## Tests Fixed

| Test | Before | After |
|------|--------|-------|
| `test_postgres_pool_rejects_negative_timeout` | FAILED | PASSED |
| `test_postgres_pool_rejects_zero_timeout` | FAILED | PASSED |
| `test_postgres_pool_rejects_zero_pool_size` | FAILED | PASSED |
| `test_postgres_pool_rejects_negative_pool_size` | FAILED | PASSED |

---

## Verification

```bash
uv run pytest tests/unit/test_concurrency_edge_cases.py::TestPostgresPoolTimeoutValidation -v
# Result: 4 passed
```

---

## Files Modified

- `scripts/agentica/postgres_pool.py` - Added validation in `_get_pool_config()`

---

## Design Decision: Default vs Raise

The implementation chooses to **default to safe values** rather than raising exceptions for invalid input. Rationale:

1. **Graceful degradation**: Pool creation won't fail due to misconfiguration
2. **Production safety**: System continues operating with sensible defaults
3. **Consistent with existing behavior**: Non-numeric strings already defaulted silently

Alternative approach (not implemented):
```python
if max_size <= 0:
    raise ValueError(f"AGENTICA_MAX_POOL_SIZE must be > 0, got {max_size}")
```

This would be more explicit but could cause unexpected failures in production if environment variables are misconfigured.
