"""Unit tests for PostgreSQL connection pool acquire timeout.

Tests verify that:
1. Pool is created with acquire_timeout to prevent indefinite blocking
2. When pool is exhausted, acquire raises TimeoutError after timeout
3. Pool size is configurable via AGENTICA_MAX_POOL_SIZE env var

These tests are EXPECTED TO FAIL until the implementation is updated to:
- Add acquire_timeout parameter (default 30s) to asyncpg.create_pool()
- Read max_size from AGENTICA_MAX_POOL_SIZE env var

Reference: docs/concurrency-search/STARVATION_FINDINGS.md (Finding 2)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAcquireTimeout:
    """Test that pool.acquire() has a timeout configured."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_pool_created_with_acquire_timeout(self):
        """Pool should be created with acquire_timeout parameter.

        Without acquire_timeout, pool.acquire() blocks indefinitely when
        all connections are in use. This can cause agent starvation.

        Expected: asyncpg.create_pool() is called with acquire_timeout=30
        """
        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await get_pool()

            call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
            assert "acquire_timeout" in call_kwargs, (
                "Pool must be created with acquire_timeout parameter to prevent "
                "indefinite blocking when pool is exhausted"
            )
            assert call_kwargs["acquire_timeout"] == 30, (
                "Default acquire_timeout should be 30 seconds"
            )

    @pytest.mark.asyncio
    async def test_pool_with_retry_has_acquire_timeout(self):
        """Pool created via get_pool_with_retry should also have acquire_timeout.

        Both pool creation paths must include the timeout.
        """
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await get_pool_with_retry(max_retries=1, initial_delay=0.01)

            call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
            assert "acquire_timeout" in call_kwargs, (
                "get_pool_with_retry must also set acquire_timeout"
            )
            assert call_kwargs["acquire_timeout"] == 30

    @pytest.mark.asyncio
    async def test_acquire_timeout_raises_on_exhausted_pool(self):
        """When pool is exhausted, acquire should raise TimeoutError.

        Simulates scenario where all 10 connections are held and an 11th
        request comes in. With acquire_timeout, it should timeout rather
        than block forever.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            # Create a pool that simulates exhaustion
            mock_pool = MagicMock()

            # Mock acquire to raise TimeoutError (simulating exhausted pool)
            async def exhausted_acquire(*args, **kwargs):
                raise TimeoutError("connection pool exhausted")

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=exhausted_acquire)
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Should raise TimeoutError, not block forever
            with pytest.raises(TimeoutError):
                async with get_connection():
                    # Intentionally empty - just testing that acquire raises
                    ...  # noqa: S108


class TestConfigurablePoolSize:
    """Test that pool size is configurable via environment variable."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_default_max_pool_size(self):
        """Without env var, pool should use default max_size of 10."""
        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            with patch.dict("os.environ", {}, clear=True):
                mock_pool = AsyncMock()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

                await get_pool()

                call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
                assert call_kwargs.get("max_size") == 10

    @pytest.mark.asyncio
    async def test_configurable_max_pool_size_via_env(self):
        """AGENTICA_MAX_POOL_SIZE should control pool max_size.

        Operators may need to tune pool size based on workload and
        database connection limits.

        Expected: max_size reads from AGENTICA_MAX_POOL_SIZE env var
        """
        import os

        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            with patch.dict(os.environ, {"AGENTICA_MAX_POOL_SIZE": "25"}):
                mock_pool = AsyncMock()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

                await get_pool()

                call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
                assert call_kwargs.get("max_size") == 25, (
                    "Pool max_size should be configurable via AGENTICA_MAX_POOL_SIZE env var"
                )

    @pytest.mark.asyncio
    async def test_invalid_pool_size_env_uses_default(self):
        """Invalid AGENTICA_MAX_POOL_SIZE should fall back to default.

        If the env var contains a non-integer value, use the default
        rather than crashing.
        """
        import os

        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            with patch.dict(os.environ, {"AGENTICA_MAX_POOL_SIZE": "not-a-number"}):
                mock_pool = AsyncMock()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

                await get_pool()

                call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
                # Should fall back to default 10, not crash
                assert call_kwargs.get("max_size") == 10, (
                    "Invalid AGENTICA_MAX_POOL_SIZE should fall back to default 10"
                )

    @pytest.mark.asyncio
    async def test_pool_with_retry_respects_env_pool_size(self):
        """get_pool_with_retry should also read AGENTICA_MAX_POOL_SIZE."""
        import os

        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            with patch.dict(os.environ, {"AGENTICA_MAX_POOL_SIZE": "20"}):
                mock_pool = AsyncMock()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

                await get_pool_with_retry(max_retries=1, initial_delay=0.01)

                call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
                assert call_kwargs.get("max_size") == 20


class TestAcquireTimeoutConfigurable:
    """Test that acquire_timeout can be configured via environment."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_acquire_timeout_configurable_via_env(self):
        """AGENTICA_ACQUIRE_TIMEOUT should allow custom timeout.

        Some workloads may need shorter or longer timeouts.
        """
        import os

        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            with patch.dict(os.environ, {"AGENTICA_ACQUIRE_TIMEOUT": "60"}):
                mock_pool = AsyncMock()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

                await get_pool()

                call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
                assert call_kwargs.get("acquire_timeout") == 60, (
                    "acquire_timeout should be configurable via AGENTICA_ACQUIRE_TIMEOUT"
                )

    @pytest.mark.asyncio
    async def test_min_size_respects_env_pool_size(self):
        """min_size should scale with max_size (e.g., 20% of max).

        When pool size is increased, min_size should also increase
        to maintain warm connections.
        """
        import os

        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            with patch.dict(os.environ, {"AGENTICA_MAX_POOL_SIZE": "50"}):
                mock_pool = AsyncMock()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

                await get_pool()

                call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
                # min_size should scale: 50 * 0.2 = 10 (or at least > 2)
                assert call_kwargs.get("min_size", 2) >= 2
                # But for larger pools, min_size should be proportionally larger
                # e.g., for max_size=50, min_size should be ~10
                if call_kwargs.get("max_size", 10) >= 50:
                    assert call_kwargs.get("min_size", 2) >= 5, (
                        "min_size should scale with max_size for larger pools"
                    )
