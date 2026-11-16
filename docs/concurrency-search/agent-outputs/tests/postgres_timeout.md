# PostgreSQL Pool Timeout Tests

## Test File
`/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_postgres_pool_timeout.py`

## Reference
Finding 2 in `docs/concurrency-search/STARVATION_FINDINGS.md`

## Test Summary

| Test Name | What It Verifies | Status |
|-----------|------------------|--------|
| `test_pool_created_with_acquire_timeout` | `asyncpg.create_pool()` includes `acquire_timeout=30` | FAILS |
| `test_pool_with_retry_has_acquire_timeout` | `get_pool_with_retry()` also sets `acquire_timeout` | FAILS |
| `test_acquire_timeout_raises_on_exhausted_pool` | TimeoutError is raised when pool is exhausted | PASSES (mocked) |
| `test_default_max_pool_size` | Default `max_size=10` when no env var | PASSES |
| `test_configurable_max_pool_size_via_env` | `AGENTICA_MAX_POOL_SIZE` env var controls max_size | FAILS |
| `test_invalid_pool_size_env_uses_default` | Invalid env var falls back to default | PASSES |
| `test_pool_with_retry_respects_env_pool_size` | Both creation paths read env var | FAILS |
| `test_acquire_timeout_configurable_via_env` | `AGENTICA_ACQUIRE_TIMEOUT` env var controls timeout | FAILS |
| `test_min_size_respects_env_pool_size` | min_size scales with max_size | PASSES (always true for default) |

## Current Failure Output

```
FAILED tests/unit/test_postgres_pool_timeout.py::TestAcquireTimeout::test_pool_created_with_acquire_timeout
    AssertionError: Pool must be created with acquire_timeout parameter to prevent indefinite blocking when pool is exhausted
    assert 'acquire_timeout' in {'command_timeout': 60, 'init': ..., 'max_size': 10, 'min_size': 2, ...}

FAILED tests/unit/test_postgres_pool_timeout.py::TestAcquireTimeout::test_pool_with_retry_has_acquire_timeout
    AssertionError: get_pool_with_retry must also set acquire_timeout

FAILED tests/unit/test_postgres_pool_timeout.py::TestConfigurablePoolSize::test_configurable_max_pool_size_via_env
    AssertionError: Pool max_size should be configurable via AGENTICA_MAX_POOL_SIZE env var
    assert 10 == 25

FAILED tests/unit/test_postgres_pool_timeout.py::TestConfigurablePoolSize::test_pool_with_retry_respects_env_pool_size
    assert 10 == 20

FAILED tests/unit/test_postgres_pool_timeout.py::TestAcquireTimeoutConfigurable::test_acquire_timeout_configurable_via_env
    AssertionError: acquire_timeout should be configurable via AGENTICA_ACQUIRE_TIMEOUT
    assert None == 60
```

## Implementation Required

To make these tests pass, update `scripts/agentica/postgres_pool.py`:

### 1. Add helper function for pool configuration

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

### 2. Update get_pool()

```python
async def get_pool() -> Pool:
    global _pool

    async with _pool_lock:
        if _pool is None:
            config = _get_pool_config()
            _pool = await asyncpg.create_pool(
                get_connection_string(),
                init=_init_connection,
                **config,
            )

    return _pool
```

### 3. Update get_pool_with_retry()

Apply the same `_get_pool_config()` call to the retry path.

## Starvation Prevention

Without `acquire_timeout`:
- When all 10 connections are held by agents waiting for I/O
- New connection requests block indefinitely
- This causes cascading starvation across the agent system

With `acquire_timeout=30`:
- New requests timeout after 30 seconds
- TimeoutError is raised, allowing graceful degradation
- Callers can implement retry logic or fail fast

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTICA_MAX_POOL_SIZE` | 10 | Maximum concurrent connections |
| `AGENTICA_ACQUIRE_TIMEOUT` | 30 | Seconds to wait for connection |
