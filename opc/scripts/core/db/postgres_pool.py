"""PostgreSQL connection pool for async memory operations.

Provides connection pooling with proper lifecycle management.
Uses asyncpg for true async/await without blocking.

Usage:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetch("SELECT * FROM core_memory WHERE session_id = $1", session_id)

    # Or use the convenience context manager:
    async with get_connection() as conn:
        await conn.fetch(...)

    # For transactions:
    async with get_transaction() as conn:
        await conn.execute("INSERT ...")
        await conn.execute("UPDATE ...")
        # Auto-commits on success, rolls back on exception

    # For connection with retry:
    pool = await get_pool_with_retry(max_retries=5, initial_delay=0.5)

    # Health check:
    is_healthy, error = await health_check()

    # Clean up when done:
    await close_pool()
"""

import asyncio
import logging
import os
import random
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Connection, Pool

# Global pool instance
_pool: Pool | None = None
_pool_lock = asyncio.Lock()

# Logger for health checks
_logger = logging.getLogger(__name__)


def _is_production() -> bool:
    """Check if running in production mode.

    Returns True if AGENTICA_ENV is set to 'production'.
    """
    return os.environ.get("AGENTICA_ENV", "").lower() == "production"


def _get_pool_config() -> dict:
    """Get pool configuration from environment with defaults.

    Environment variables:
    - AGENTICA_MAX_POOL_SIZE: Maximum connections (default: 10, must be > 0)
    - AGENTICA_ACQUIRE_TIMEOUT: Seconds to wait for connection (default: 30, must be > 0)

    Returns:
        Dict with pool configuration parameters.

    Note:
        Invalid values (non-numeric, zero, or negative) are replaced with defaults.
        - Negative/zero max_size defaults to 10
        - Negative/zero acquire_timeout defaults to 30
    """
    max_size_str = os.environ.get("AGENTICA_MAX_POOL_SIZE", "10")
    acquire_timeout_str = os.environ.get("AGENTICA_ACQUIRE_TIMEOUT", "30")

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

    # Scale min_size with max_size (20% of max, minimum 2)
    min_size = max(2, max_size // 5)

    # Note: acquire_timeout is for pool.acquire(), not create_pool()
    # command_timeout is passed as a connect_kwarg
    return {
        "min_size": min_size,
        "max_size": max_size,
        "command_timeout": 60,
    }


def get_connection_string() -> str:
    """Get PostgreSQL connection string from environment or defaults.

    Checks env vars in order (single source of truth pattern):
    1. OPC_POSTGRES_URL - primary config used by wizard/docker-compose
    2. AGENTICA_POSTGRES_URL - legacy/alternative name
    3. DATABASE_URL - standard convention (used by settings.json)
    4. Development default if none set

    In production mode, one of these must be explicitly set.

    Raises:
        ValueError: If no URL is set in production mode.
    """
    # Check env vars in priority order
    url = (
        os.environ.get("OPC_POSTGRES_URL")
        or os.environ.get("AGENTICA_POSTGRES_URL")
        or os.environ.get("DATABASE_URL")
    )

    if url:
        return url

    if _is_production():
        raise ValueError(
            "OPC_POSTGRES_URL, AGENTICA_POSTGRES_URL, or DATABASE_URL must be set in production mode. "
            "Set AGENTICA_ENV=development for local defaults."
        )

    # Development-only defaults - matches docker-compose.yml (port 5434 on Windows)
    return "postgresql://claude:claude_dev@localhost:5434/continuous_claude"


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Initialize a new connection with pgvector codec.

    This is called automatically by asyncpg for each new connection in the pool.
    """
    await init_pgvector(conn)


async def get_pool() -> Pool:
    """Get or create the global connection pool.

    Thread-safe via asyncio.Lock.
    Creates pool with:
    - min_size=2 (always ready connections, scales with max_size)
    - max_size from AGENTICA_MAX_POOL_SIZE (default 10)
    - acquire_timeout from AGENTICA_ACQUIRE_TIMEOUT (default 30s)
    - statement_cache_size for prepared statements
    - init callback for pgvector codec registration
    """
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


async def close_pool() -> None:
    """Close the connection pool gracefully."""
    global _pool

    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None


def reset_pool() -> None:
    """Reset the pool reference and lock without closing.

    This is used for testing when the event loop changes.
    The old pool's connections will be garbage collected.
    Also resets the lock to avoid "bound to a different event loop" errors.
    """
    global _pool, _pool_lock
    _pool = None
    _pool_lock = asyncio.Lock()


@asynccontextmanager
async def get_connection():
    """Acquire a connection from the pool.

    Usage:
        async with get_connection() as conn:
            await conn.fetch(...)
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def init_pgvector(conn: asyncpg.Connection) -> None:
    """Initialize pgvector extension for a connection.

    Required for vector operations on each connection.
    From Letta pattern: register vector type with asyncpg.
    """
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Register vector type
    def _encode_vector(v):
        """Encode vector for pgvector.

        Handles both:
        - list[float]: Converts to pgvector string format
        - str: Already formatted, pass through (handles ::vector cast)
        """
        if isinstance(v, str):
            # Already formatted (e.g., from _pad_embedding), pass through
            return v
        # List of floats - format for pgvector
        return f"[{','.join(map(str, v))}]"

    await conn.set_type_codec(
        "vector",
        encoder=_encode_vector,
        decoder=lambda v: [float(x) for x in v.strip("[]").split(",")],
        schema="public",
        format="text",
    )


async def get_pool_with_retry(
    max_retries: int = 5,
    initial_delay: float = 0.5,
) -> Pool:
    """Get or create the global connection pool with retry on transient failures.

    Uses exponential backoff between retries. Lock is held throughout the entire
    retry loop to prevent race conditions where multiple callers attempt to create
    the pool simultaneously.

    Pool configuration is read from environment variables:
    - AGENTICA_MAX_POOL_SIZE: Maximum connections (default: 10)
    - AGENTICA_ACQUIRE_TIMEOUT: Seconds to wait for connection (default: 30)

    Args:
        max_retries: Maximum number of connection attempts.
        initial_delay: Initial delay in seconds between retries (doubles each time).

    Returns:
        The connection pool.

    Raises:
        The last connection error after all retries are exhausted.
    """
    global _pool

    async with _pool_lock:
        # Check if pool already exists (fast path)
        if _pool is not None:
            return _pool

        last_error: Exception | None = None
        config = _get_pool_config()

        for attempt in range(max_retries):
            try:
                pool = await asyncpg.create_pool(
                    get_connection_string(),
                    init=_init_connection,
                    **config,
                )
                _pool = pool
                return pool
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Full jitter: random(0, base * 2^attempt)
                    max_delay = initial_delay * (2**attempt)
                    jittered_delay = random.uniform(0, max_delay)
                    await asyncio.sleep(jittered_delay)

        # All retries exhausted
        if last_error is not None:
            raise last_error
        raise RuntimeError("Failed to create pool after retries")


async def health_check(log_errors: bool = False) -> tuple[bool, str | None]:
    """Check if the connection pool is healthy.

    Args:
        log_errors: If True, log error details at WARNING level.

    Returns:
        A tuple of (is_healthy, error_type) where:
        - is_healthy: True if a connection can be acquired and a simple query succeeds
        - error_type: None if healthy, otherwise a string describing the error type
    """
    try:
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        return (True, None)
    except asyncpg.PostgresConnectionError as e:
        error_type = "connection_error"
        if log_errors:
            _logger.warning("Health check failed with connection error: %s", e)
        return (False, error_type)
    except asyncpg.PostgresError as e:
        error_type = "postgres_error"
        if log_errors:
            _logger.warning("Health check failed with postgres error: %s", e)
        return (False, error_type)
    except Exception as e:
        error_type = type(e).__name__
        if log_errors:
            _logger.warning("Health check failed with %s: %s", error_type, e)
        return (False, error_type)


@asynccontextmanager
async def get_transaction() -> AsyncGenerator[Connection, None]:
    """Acquire a connection from the pool with a transaction.

    The transaction automatically commits on success and rolls back on exception.

    Usage:
        async with get_transaction() as conn:
            await conn.execute("INSERT INTO ...")
            await conn.execute("UPDATE ...")
            # Auto-commits if no exception

    Yields:
        A connection within an active transaction.
    """
    async with get_connection() as conn:
        async with conn.transaction():
            yield conn
