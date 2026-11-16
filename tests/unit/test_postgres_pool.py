"""Unit tests for PostgreSQL connection pool.

Tests the asyncpg connection pool with:
- Singleton pattern
- Connection acquisition with context manager
- Concurrent connection handling
- Pool cleanup on shutdown
- pgvector codec registration
- Connection retry on transient failure
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPoolSingleton:
    """Test pool singleton pattern works."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        # Reset global state
        postgres_pool._pool = None
        yield
        # Cleanup after test
        if postgres_pool._pool is not None:
            await postgres_pool.close_pool()

    @pytest.mark.asyncio
    async def test_get_pool_returns_same_instance(self):
        """Getting pool multiple times should return the same instance."""
        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            pool1 = await get_pool()
            pool2 = await get_pool()

            assert pool1 is pool2
            # Should only create pool once
            assert mock_asyncpg.create_pool.call_count == 1

    @pytest.mark.asyncio
    async def test_get_pool_thread_safe(self):
        """Multiple concurrent get_pool calls should still return singleton."""
        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Concurrent pool requests
            pools = await asyncio.gather(*[get_pool() for _ in range(10)])

            # All should be the same instance
            assert all(p is pools[0] for p in pools)
            # Should only create pool once
            assert mock_asyncpg.create_pool.call_count == 1

    @pytest.mark.asyncio
    async def test_get_pool_includes_init_callback(self):
        """Pool should be created with init callback for pgvector."""
        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await get_pool()

            call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
            assert "init" in call_kwargs
            assert call_kwargs["init"] is not None


class TestConnectionAcquisition:
    """Test connection acquisition with context manager."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        # Directly reset the global, don't call close_pool which awaits on mock
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_get_connection_context_manager(self):
        """Should acquire and release connection via context manager."""
        from scripts.agentica_patterns.postgres_pool import get_connection

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_conn = AsyncMock()
            mock_pool = MagicMock()
            mock_acquire_ctx = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock()
            )
            mock_pool.acquire = MagicMock(return_value=mock_acquire_ctx)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            async with get_connection() as conn:
                assert conn is mock_conn

    @pytest.mark.asyncio
    async def test_connection_released_on_exception(self):
        """Connection should be released even if exception occurs."""
        from scripts.agentica_patterns.postgres_pool import get_connection

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_conn = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_context.__aexit__ = AsyncMock(return_value=False)

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            with pytest.raises(ValueError):
                async with get_connection():
                    raise ValueError("Test error")

            # __aexit__ should have been called
            mock_context.__aexit__.assert_called_once()


class TestConcurrentConnections:
    """Test concurrent connection handling."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        # Directly reset the global, don't call close_pool which awaits on mock
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_10_concurrent_connections(self):
        """Should handle 10+ simultaneous connection acquisitions."""
        from scripts.agentica_patterns.postgres_pool import get_connection

        # Track connection usage
        active_connections = 0
        max_active = 0

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            async def mock_acquire_fn():
                nonlocal active_connections, max_active
                mock_conn = AsyncMock()
                active_connections += 1
                max_active = max(max_active, active_connections)
                await asyncio.sleep(0.01)  # Simulate work
                return mock_conn

            async def mock_release_fn(*args):
                nonlocal active_connections
                active_connections -= 1

            # Create AsyncMock with proper __aenter__ and __aexit__
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=mock_acquire_fn)
            mock_context.__aexit__ = AsyncMock(side_effect=mock_release_fn)

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            async def work():
                async with get_connection():
                    await asyncio.sleep(0.01)

            # Run 10+ concurrent connections
            await asyncio.gather(*[work() for _ in range(12)])

            # All connections should be released
            assert active_connections == 0
            # Should have had concurrent connections
            assert max_active >= 1

    @pytest.mark.asyncio
    async def test_pool_max_size_respected(self):
        """Pool should respect max_size configuration."""
        from scripts.agentica_patterns.postgres_pool import get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await get_pool()

            # Verify pool was created with correct max_size
            call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
            assert call_kwargs.get("max_size") == 10


class TestPoolCleanup:
    """Test pool cleanup on shutdown."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        if postgres_pool._pool is not None:
            await postgres_pool.close_pool()

    @pytest.mark.asyncio
    async def test_close_pool_closes_connections(self):
        """close_pool should close all connections gracefully."""
        from scripts.agentica_patterns.postgres_pool import close_pool, get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await get_pool()
            await close_pool()

            mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_pool_resets_singleton(self):
        """close_pool should reset the singleton so new pool can be created."""
        from scripts.agentica_patterns import postgres_pool
        from scripts.agentica_patterns.postgres_pool import close_pool, get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool1 = AsyncMock()
            mock_pool2 = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(side_effect=[mock_pool1, mock_pool2])

            await get_pool()
            await close_pool()
            await get_pool()

            assert postgres_pool._pool is mock_pool2
            assert mock_asyncpg.create_pool.call_count == 2

    @pytest.mark.asyncio
    async def test_close_pool_idempotent(self):
        """close_pool should be safe to call multiple times."""
        from scripts.agentica_patterns.postgres_pool import close_pool, get_pool

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await get_pool()
            await close_pool()
            await close_pool()  # Should not raise

            # Close only called once
            mock_pool.close.assert_called_once()


class TestPgvectorCodec:
    """Test pgvector codec registration."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        if postgres_pool._pool is not None:
            await postgres_pool.close_pool()

    @pytest.mark.asyncio
    async def test_init_pgvector_registers_codec(self):
        """init_pgvector should register vector type codec."""
        from scripts.agentica_patterns.postgres_pool import init_pgvector

        mock_conn = AsyncMock()

        await init_pgvector(mock_conn)

        # Should register vector type
        mock_conn.set_type_codec.assert_called_once()
        call_args = mock_conn.set_type_codec.call_args
        assert call_args.args[0] == "vector"
        assert call_args.kwargs.get("schema") == "public"
        assert call_args.kwargs.get("format") == "text"

    @pytest.mark.asyncio
    async def test_vector_encoder(self):
        """Vector encoder should convert list to pgvector format."""
        from scripts.agentica_patterns.postgres_pool import init_pgvector

        mock_conn = AsyncMock()
        await init_pgvector(mock_conn)

        # Get the encoder from the call
        encoder = mock_conn.set_type_codec.call_args.kwargs["encoder"]
        result = encoder([1.0, 2.0, 3.0])

        assert result == "[1.0,2.0,3.0]"

    @pytest.mark.asyncio
    async def test_vector_decoder(self):
        """Vector decoder should convert pgvector format to list."""
        from scripts.agentica_patterns.postgres_pool import init_pgvector

        mock_conn = AsyncMock()
        await init_pgvector(mock_conn)

        # Get the decoder from the call
        decoder = mock_conn.set_type_codec.call_args.kwargs["decoder"]
        result = decoder("[1.0,2.0,3.0]")

        assert result == [1.0, 2.0, 3.0]

    @pytest.mark.asyncio
    async def test_init_pgvector_creates_extension(self):
        """init_pgvector should create vector extension if not exists."""
        from scripts.agentica_patterns.postgres_pool import init_pgvector

        mock_conn = AsyncMock()

        await init_pgvector(mock_conn)

        mock_conn.execute.assert_called_once_with(
            "CREATE EXTENSION IF NOT EXISTS vector"
        )

    @pytest.mark.asyncio
    async def test_init_connection_calls_init_pgvector(self):
        """_init_connection should call init_pgvector."""
        from scripts.agentica_patterns.postgres_pool import _init_connection

        mock_conn = AsyncMock()

        with patch("scripts.agentica_patterns.postgres_pool.init_pgvector") as mock_init:
            await _init_connection(mock_conn)
            mock_init.assert_called_once_with(mock_conn)


class TestConnectionRetry:
    """Test connection retry on transient failure."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        if postgres_pool._pool is not None:
            await postgres_pool.close_pool()

    @pytest.mark.asyncio
    async def test_retry_on_connection_failure(self):
        """Should retry connection on transient failure."""
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            # Fail twice, then succeed
            mock_asyncpg.create_pool = AsyncMock(
                side_effect=[
                    ConnectionError("Connection refused"),
                    ConnectionError("Connection refused"),
                    mock_pool,
                ]
            )

            pool = await get_pool_with_retry(max_retries=3, initial_delay=0.01)

            assert pool is mock_pool
            assert mock_asyncpg.create_pool.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self):
        """Should raise after max retries exhausted."""
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = AsyncMock(
                side_effect=ConnectionError("Connection refused")
            )

            with pytest.raises(ConnectionError):
                await get_pool_with_retry(max_retries=3, initial_delay=0.01)

            assert mock_asyncpg.create_pool.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Should use exponential backoff between retries."""
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        delays = []

        async def mock_sleep(delay):
            delays.append(delay)

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            with patch("scripts.agentica_patterns.postgres_pool.asyncio.sleep", mock_sleep):
                mock_pool = AsyncMock()
                # Fail twice, succeed on third
                mock_asyncpg.create_pool = AsyncMock(
                    side_effect=[
                        ConnectionError("Connection refused"),
                        ConnectionError("Connection refused"),
                        mock_pool,
                    ]
                )

                await get_pool_with_retry(max_retries=3, initial_delay=0.1)

                # Should have exponential backoff: 0.1, 0.2
                assert len(delays) == 2
                assert delays[1] > delays[0]  # Exponential increase

    @pytest.mark.asyncio
    async def test_retry_includes_init_callback(self):
        """Pool with retry should include init callback for pgvector."""
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_pool = AsyncMock()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await get_pool_with_retry(max_retries=1, initial_delay=0.01)

            call_kwargs = mock_asyncpg.create_pool.call_args.kwargs
            assert "init" in call_kwargs
            assert call_kwargs["init"] is not None

    @pytest.mark.asyncio
    async def test_retry_holds_lock_throughout(self):
        """Lock should be held throughout entire retry loop to prevent race."""
        from scripts.agentica_patterns import postgres_pool
        from scripts.agentica_patterns.postgres_pool import get_pool_with_retry

        lock_acquired_during_retry = False

        original_create_pool = None

        async def track_lock_during_retry(*args, **kwargs):
            nonlocal lock_acquired_during_retry
            # Check if lock is held (locked() returns True if lock is acquired)
            lock_acquired_during_retry = postgres_pool._pool_lock.locked()
            raise ConnectionError("Still failing")

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = AsyncMock(side_effect=track_lock_during_retry)

            with pytest.raises(ConnectionError):
                await get_pool_with_retry(max_retries=2, initial_delay=0.01)

            # Lock should have been held during the retry attempts
            assert lock_acquired_during_retry


class TestHealthCheck:
    """Test health check method."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        if postgres_pool._pool is not None:
            await postgres_pool.close_pool()

    @pytest.mark.asyncio
    async def test_health_check_returns_tuple_when_healthy(self):
        """health_check should return (True, None) when pool is healthy."""
        from scripts.agentica_patterns.postgres_pool import health_check

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=1)
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_context.__aexit__ = AsyncMock()
            mock_get_conn.return_value = mock_context

            result = await health_check()

            assert result == (True, None)
            mock_conn.fetchval.assert_called_once_with("SELECT 1")

    @pytest.mark.asyncio
    async def test_health_check_returns_tuple_when_unhealthy(self):
        """health_check should return (False, error_type) when pool is unhealthy."""
        from scripts.agentica_patterns.postgres_pool import health_check

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
            mock_get_conn.return_value = mock_context

            result = await health_check()

            assert result[0] is False
            assert result[1] == "Exception"

    @pytest.mark.asyncio
    async def test_health_check_logs_errors_when_enabled(self):
        """health_check should log errors when log_errors=True."""
        from scripts.agentica_patterns.postgres_pool import health_check

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            with patch("scripts.agentica_patterns.postgres_pool._logger") as mock_logger:
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
                mock_get_conn.return_value = mock_context

                result = await health_check(log_errors=True)

                assert result[0] is False
                mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_does_not_log_by_default(self):
        """health_check should not log errors by default."""
        from scripts.agentica_patterns.postgres_pool import health_check

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            with patch("scripts.agentica_patterns.postgres_pool._logger") as mock_logger:
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
                mock_get_conn.return_value = mock_context

                result = await health_check()

                assert result[0] is False
                mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_health_check_connection_error_type(self):
        """health_check should return 'connection_error' for PostgresConnectionError."""
        import asyncpg

        from scripts.agentica_patterns.postgres_pool import health_check

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(
                side_effect=asyncpg.PostgresConnectionError("Connection refused")
            )
            mock_get_conn.return_value = mock_context

            result = await health_check()

            assert result == (False, "connection_error")

    @pytest.mark.asyncio
    async def test_health_check_postgres_error_type(self):
        """health_check should return 'postgres_error' for PostgresError."""
        import asyncpg

        from scripts.agentica_patterns.postgres_pool import health_check

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            mock_context = AsyncMock()
            # PostgresError needs specific subclass - use a syntax error
            mock_context.__aenter__ = AsyncMock(
                side_effect=asyncpg.PostgresSyntaxError("syntax error")
            )
            mock_get_conn.return_value = mock_context

            result = await health_check()

            assert result == (False, "postgres_error")


class TestTransactionContextManager:
    """Test transaction context manager."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool

        postgres_pool._pool = None
        yield
        if postgres_pool._pool is not None:
            await postgres_pool.close_pool()

    @pytest.mark.asyncio
    async def test_transaction_commits_on_success(self):
        """Transaction should commit on successful completion."""
        from scripts.agentica_patterns.postgres_pool import get_transaction

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            mock_conn = AsyncMock()
            mock_tx = AsyncMock()
            mock_conn.transaction = MagicMock(return_value=mock_tx)

            mock_conn_context = AsyncMock()
            mock_conn_context.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn_context.__aexit__ = AsyncMock()
            mock_get_conn.return_value = mock_conn_context

            async with get_transaction() as conn:
                await conn.execute("INSERT INTO test VALUES (1)")

            # Transaction should have started and committed
            mock_tx.__aenter__.assert_called_once()
            mock_tx.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_rolls_back_on_exception(self):
        """Transaction should rollback on exception."""
        from scripts.agentica_patterns.postgres_pool import get_transaction

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            mock_conn = AsyncMock()
            mock_tx = AsyncMock()
            # Return False to propagate exception
            mock_tx.__aexit__ = AsyncMock(return_value=False)
            mock_conn.transaction = MagicMock(return_value=mock_tx)

            # get_connection is an @asynccontextmanager, so we need to mock it properly
            @asynccontextmanager
            async def fake_get_connection():
                yield mock_conn

            mock_get_conn.side_effect = fake_get_connection

            with pytest.raises(ValueError):
                async with get_transaction():
                    raise ValueError("Test error")

            # Transaction __aexit__ should have been called with exception info
            mock_tx.__aexit__.assert_called_once()
            # First arg should be exception type
            call_args = mock_tx.__aexit__.call_args[0]
            assert call_args[0] is ValueError
