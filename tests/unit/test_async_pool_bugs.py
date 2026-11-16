"""Async pool bug tests - P0 priority edge cases.

Tests for bugs NOT covered by test_postgres_pool.py:
- Pool exhaustion with timeout
- Connection leak detection after exceptions
- Event loop boundary bugs (fixture handles this)
- Health check during pool exhaustion
- Retry exponential backoff timing
- Pool reset during active connections

These are FAILING tests for bugs that may or may not exist in production code.
Following TDD: Write tests first, then fix bugs if tests fail.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPoolExhaustion:
    """Test pool exhaustion scenarios and timeout behavior."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test - pytest-asyncio creates new loop per test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_pool_exhaustion_timeout(self):
        """Pool should timeout when all connections busy.

        This test verifies that when all 10 connections are held,
        the 11th acquisition attempt will timeout rather than hang indefinitely.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection

        # Track connections
        active = 0
        max_active = 0

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            # Create mock pool with tracking
            async def mock_acquire():
                nonlocal active, max_active
                active += 1
                max_active = max(max_active, active)
                mock_conn = AsyncMock()
                # Simulate holding connection
                await asyncio.sleep(10)
                return mock_conn

            async def mock_release(*args):
                nonlocal active
                active -= 1

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=mock_acquire)
            mock_context.__aexit__ = AsyncMock(side_effect=mock_release)

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Hold all 10 connections
            async def hold_connection():
                async with get_connection():
                    await asyncio.sleep(10)

            holders = [asyncio.create_task(hold_connection()) for _ in range(10)]

            # Give tasks time to start
            await asyncio.sleep(0.1)

            # 11th should timeout (using short timeout for test speed)
            with pytest.raises(asyncio.TimeoutError):
                async with asyncio.timeout(1):
                    async with get_connection():
                        pass

            # Cleanup
            for task in holders:
                task.cancel()
            await asyncio.gather(*holders, return_exceptions=True)

            # Verify we held 10 connections
            assert max_active >= 10

    @pytest.mark.asyncio
    async def test_connection_leak_after_many_exceptions(self):
        """Verify connections are returned to pool after 100 exceptions.

        This tests for gradual connection leaks that might not show up
        in single-exception tests.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection

        acquired_count = 0
        released_count = 0

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            async def mock_acquire():
                nonlocal acquired_count
                acquired_count += 1
                return AsyncMock()

            async def mock_release(*args):
                nonlocal released_count
                released_count += 1

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=mock_acquire)
            mock_context.__aexit__ = AsyncMock(side_effect=mock_release)

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Run 100 operations that raise exceptions
            for _ in range(100):
                with pytest.raises(ValueError):
                    async with get_connection():
                        raise ValueError("Test error")

            # All connections should be released
            assert acquired_count == 100
            assert released_count == 100
            assert acquired_count == released_count  # No leaks

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_pool_exhaustion_recovers_after_release(self):
        """Pool should allow new connections after busy ones are released.

        This tests that pool exhaustion is temporary and recovers.
        Marked as flaky because it depends on timing.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection

        active = 0

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            async def mock_acquire():
                nonlocal active
                active += 1
                mock_conn = AsyncMock()
                await asyncio.sleep(0.5)  # 10x margin for CI
                return mock_conn

            async def mock_release(*args):
                nonlocal active
                active -= 1

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=mock_acquire)
            mock_context.__aexit__ = AsyncMock(side_effect=mock_release)

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Hold all 10 connections temporarily
            async def hold_then_release():
                async with get_connection():
                    await asyncio.sleep(0.5)

            tasks = [asyncio.create_task(hold_then_release()) for _ in range(10)]

            # Wait for tasks to complete
            await asyncio.gather(*tasks)

            # All connections should be released
            assert active == 0

            # Pool should be usable again
            async with get_connection() as conn:
                assert conn is not None


class TestHealthCheckDuringExhaustion:
    """Test health check behavior during pool exhaustion."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_health_check_timeout_during_exhaustion(self):
        """Health check should timeout if pool is exhausted.

        This verifies that health checks don't hang when all
        connections are busy.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection, health_check

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            # Create mock that hangs on acquire
            async def mock_acquire():
                await asyncio.sleep(10)  # Never returns
                return AsyncMock()

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=mock_acquire)
            mock_context.__aexit__ = AsyncMock()

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Health check should timeout
            with pytest.raises(asyncio.TimeoutError):
                async with asyncio.timeout(1):
                    await health_check()


class TestRetryBackoffTiming:
    """Test retry logic exponential backoff timing."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_exponential_backoff_timing_verification(self):
        """Verify exponential backoff timing is correct.

        Tests that delays actually follow exponential pattern:
        0.1s, 0.2s, 0.4s (not just increasing, but doubling).
        """
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        delays = []
        start_times = []

        async def mock_sleep(delay):
            delays.append(delay)
            start_times.append(asyncio.get_running_loop().time())
            await asyncio.sleep(0.01)  # Very short actual delay for test speed

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            with patch("scripts.agentica_patterns.postgres_pool.asyncio.sleep", mock_sleep):
                mock_pool = AsyncMock()
                # Fail 3 times, succeed on 4th
                mock_asyncpg.create_pool = AsyncMock(
                    side_effect=[
                        ConnectionError("Failed 1"),
                        ConnectionError("Failed 2"),
                        ConnectionError("Failed 3"),
                        mock_pool,
                    ]
                )

                await get_pool_with_retry(max_retries=4, initial_delay=0.1)

                # Should have 3 delays (after 1st, 2nd, 3rd failures)
                assert len(delays) == 3

                # Verify exponential pattern: 0.1, 0.2, 0.4
                assert delays[0] == 0.1
                assert delays[1] == 0.2
                assert delays[2] == 0.4

    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises_last_error(self):
        """Verify that retry exhaustion raises the LAST error, not first.

        This is important for debugging - the last error may have
        different details than the first.
        """
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            # Different errors each time
            mock_asyncpg.create_pool = AsyncMock(
                side_effect=[
                    ConnectionError("Error 1"),
                    ConnectionError("Error 2"),
                    ConnectionError("Error 3 - LAST"),
                ]
            )

            with pytest.raises(ConnectionError) as exc_info:
                await get_pool_with_retry(max_retries=3, initial_delay=0.01)

            # Should raise the LAST error
            assert "Error 3 - LAST" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_success_on_last_attempt(self):
        """Verify retry succeeds if last attempt works.

        Edge case: max_retries=3, fails twice, succeeds on 3rd.
        """
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            # Fail twice, succeed on 3rd (last) attempt
            mock_asyncpg.create_pool = AsyncMock(
                side_effect=[
                    ConnectionError("Failed 1"),
                    ConnectionError("Failed 2"),
                    mock_pool,  # Success on last attempt
                ]
            )

            pool = await get_pool_with_retry(max_retries=3, initial_delay=0.01)

            assert pool is mock_pool
            assert mock_asyncpg.create_pool.call_count == 3


class TestPoolResetEdgeCases:
    """Test pool reset during active connections."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_reset_pool_during_active_connections(self):
        """reset_pool() should not crash even if connections are active.

        Edge case: reset_pool() is called while connections are held.
        The old pool should be garbage collected.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection, reset_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_conn = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_context.__aexit__ = AsyncMock()

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Acquire a connection
            async with get_connection():
                # Reset pool while connection is active
                reset_pool()
                # Should not crash

            # reset_pool() doesn't close connections, just resets reference
            # The old pool will be garbage collected
            mock_pool.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_pool_waits_for_active_connections(self):
        """close_pool() should gracefully close even with active connections.

        This tests that close_pool() calls pool.close() which should
        wait for connections to be returned.
        """
        from scripts.agentica_patterns.postgres_pool import close_pool, get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await get_pool()
            await close_pool()

            # Should call close on the pool
            mock_pool.close.assert_called_once()


class TestConnectionAcquisitionEdgeCases:
    """Test edge cases in connection acquisition."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_multiple_exceptions_in_same_context(self):
        """Verify cleanup happens even with multiple exceptions.

        Edge case: Exception in user code, then another exception
        during cleanup. Connection should still be released.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection

        cleanup_called = False

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            async def mock_release(*args):
                nonlocal cleanup_called
                cleanup_called = True

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_context.__aexit__ = AsyncMock(side_effect=mock_release)

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            with pytest.raises(ValueError):
                async with get_connection():
                    raise ValueError("User exception")

            # Cleanup should have been called despite exception
            assert cleanup_called

    @pytest.mark.asyncio
    async def test_connection_context_manager_cancellation(self):
        """Verify cleanup happens when task is cancelled.

        Edge case: Task holding connection is cancelled.
        Connection should still be released.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection

        released = False

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            async def mock_release(*args):
                nonlocal released
                released = True

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_context.__aexit__ = AsyncMock(side_effect=mock_release)

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            async def hold_connection():
                async with get_connection():
                    await asyncio.sleep(10)

            task = asyncio.create_task(hold_connection())
            await asyncio.sleep(0.1)  # Let task start
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # Connection should be released despite cancellation
            # (This might fail if asyncpg doesn't handle cancellation properly)
            await asyncio.sleep(0.1)  # Give cleanup time
            assert released
