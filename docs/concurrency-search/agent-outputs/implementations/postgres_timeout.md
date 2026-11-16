# PostgreSQL Pool acquire_timeout Implementation

## Summary

Added `acquire_timeout` parameter to asyncpg connection pool to prevent indefinite blocking when the pool is exhausted. Pool configuration is now read from environment variables for runtime tuning.

## Files Modified

| File | Change |
|------|--------|
| `scripts/agentica/postgres_pool.py` | Added `_get_pool_config()` helper, updated `get_pool()` and `get_pool_with_retry()` to use configurable pool settings |

## Changes Made

### 1. Added `_get_pool_config()` helper function

```python
def _get_pool_config() -> dict:
    """Get pool configuration from environment with defaults."""
    max_size_str = os.environ.get("AGENTICA_MAX_POOL_SIZE", "10")
    acquire_timeout_str = os.environ.get("AGENTICA_ACQUIRE_TIMEOUT", "30")

    try:
        max_size = int(max_size_str)
    except ValueError:
        max_size = 10

    try:
        acquire_timeout = int(acquire_timeout_str)
    except ValueError:
        acquire_timeout = 30

    # Scale min_size with max_size (20% of max, minimum 2)
    min_size = max(2, max_size // 5)

    return {
        "min_size": min_size,
        "max_size": max_size,
        "acquire_timeout": acquire_timeout,
        "command_timeout": 60,
        "statement_cache_size": 100,
    }
```

### 2. Updated `get_pool()` to use config

- Replaced hardcoded parameters with `**config` spread
- Pool now includes `acquire_timeout=30` by default

### 3. Updated `get_pool_with_retry()` to use config

- Same pattern as `get_pool()`
- Config read once before retry loop for consistency

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTICA_MAX_POOL_SIZE` | 10 | Maximum concurrent connections |
| `AGENTICA_ACQUIRE_TIMEOUT` | 30 | Seconds to wait for connection before TimeoutError |

## Test Results

```
tests/unit/test_postgres_pool_timeout.py::TestAcquireTimeout::test_pool_created_with_acquire_timeout PASSED
tests/unit/test_postgres_pool_timeout.py::TestAcquireTimeout::test_pool_with_retry_has_acquire_timeout PASSED
tests/unit/test_postgres_pool_timeout.py::TestAcquireTimeout::test_acquire_timeout_raises_on_exhausted_pool PASSED
tests/unit/test_postgres_pool_timeout.py::TestConfigurablePoolSize::test_default_max_pool_size PASSED
tests/unit/test_postgres_pool_timeout.py::TestConfigurablePoolSize::test_configurable_max_pool_size_via_env PASSED
tests/unit/test_postgres_pool_timeout.py::TestConfigurablePoolSize::test_invalid_pool_size_env_uses_default PASSED
tests/unit/test_postgres_pool_timeout.py::TestConfigurablePoolSize::test_pool_with_retry_respects_env_pool_size PASSED
tests/unit/test_postgres_pool_timeout.py::TestAcquireTimeoutConfigurable::test_acquire_timeout_configurable_via_env PASSED
tests/unit/test_postgres_pool_timeout.py::TestAcquireTimeoutConfigurable::test_min_size_respects_env_pool_size PASSED

9 passed in 0.05s
```

## Code Quality

```
uv run qlty check scripts/agentica/postgres_pool.py
No issues
```

## Starvation Prevention

Without `acquire_timeout`:
- When all connections are held by agents waiting for I/O
- New connection requests block indefinitely
- This causes cascading starvation across the agent system

With `acquire_timeout=30`:
- New requests timeout after 30 seconds
- `TimeoutError` is raised, allowing graceful degradation
- Callers can implement retry logic or fail fast

## Issues Encountered

None.

## Reference

- Finding 2 in `docs/concurrency-search/STARVATION_FINDINGS.md`
- Test requirements in `docs/concurrency-search/agent-outputs/tests/postgres_timeout.md`
