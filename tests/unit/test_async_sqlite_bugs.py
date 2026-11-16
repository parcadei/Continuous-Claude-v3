"""Async SQLite bug tests - P1 priority.

Tests for SQLite-specific async issues with aiosqlite:
- Concurrent writes with WAL mode
- Connection reuse after exception (_get_conn context manager)
- FTS5 trigger consistency during concurrent operations
- Concurrent search during archival writes
- Connection close during active query
- Schema init idempotency

These are FAILING tests for SQLite-specific edge cases.
Following TDD: Write tests first, verify behavior.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSQLiteWALConcurrentWrites:
    """Test concurrent writes with WAL mode enabled."""

    @pytest.mark.asyncio
    async def test_10_concurrent_writes_with_wal(self):
        """10 concurrent writes should succeed with WAL mode.

        WAL mode allows concurrent readers and one writer.
        This tests that concurrent writes are properly serialized.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        # Use in-memory database for testing
        with patch("scripts.agentica_patterns.memory_service.Path") as mock_path:
            mock_path.return_value = Path(":memory:")

            memory = MemoryService(session_id="wal-test")
            await memory.connect()

            # 10 concurrent writes
            await asyncio.gather(
                *[memory.set_core(f"key{i}", f"value{i}") for i in range(10)]
            )

            # All writes should succeed
            # Verify by reading back
            results = await asyncio.gather(
                *[memory.get_core(f"key{i}") for i in range(10)]
            )

            # All values should be present
            assert all(r is not None for r in results)

            await memory.close()

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_wal_pragma_actually_set(self):
        """Verify WAL pragma is actually set on connections.

        This tests that _get_conn actually enables WAL mode.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        wal_mode_set = False

        async def mock_execute(query, *args):
            nonlocal wal_mode_set
            if "PRAGMA journal_mode=WAL" in query:
                wal_mode_set = True

        with patch("aiosqlite.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(side_effect=mock_execute)
            mock_conn.commit = AsyncMock()
            mock_conn.close = AsyncMock()
            mock_conn.row_factory = None

            mock_connect.return_value = mock_conn

            memory = MemoryService(session_id="test")

            # Use _get_conn context manager
            async with memory._get_conn() as conn:
                pass

            # WAL pragma should have been set
            assert wal_mode_set


class TestConnectionReuseAfterException:
    """Test connection cleanup after exceptions."""

    @pytest.mark.asyncio
    async def test_connection_reuse_after_exception(self):
        """_get_conn should allow reuse after exception.

        This tests that exceptions don't corrupt connection state.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="test")

        exception_count = 0

        with patch("aiosqlite.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.commit = AsyncMock()
            mock_conn.close = AsyncMock()
            mock_conn.row_factory = None

            mock_connect.return_value = mock_conn

            # First use raises exception
            try:
                async with memory._get_conn() as conn:
                    exception_count += 1
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Second use should work fine
            async with memory._get_conn() as conn:
                exception_count += 1

            # Both uses should complete
            assert exception_count == 2

            # Connection should be closed twice
            assert mock_conn.close.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_exception(self):
        """Connection should be closed even if exception occurs.

        This tests the finally block in _get_conn.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="test")

        close_called = False

        with patch("aiosqlite.connect") as mock_connect:
            async def mock_close():
                nonlocal close_called
                close_called = True

            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.commit = AsyncMock()
            mock_conn.close = AsyncMock(side_effect=mock_close)
            mock_conn.row_factory = None

            mock_connect.return_value = mock_conn

            try:
                async with memory._get_conn() as conn:
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Connection should be closed despite exception
            assert close_called


class TestFTS5TriggerConsistency:
    """Test FTS5 trigger consistency during concurrent operations."""

    @pytest.mark.asyncio
    async def test_fts5_insert_during_search(self):
        """FTS5 insert during search should not corrupt index.

        This tests that FTS5 triggers work correctly with
        concurrent read and write operations.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        # Use real in-memory database for FTS5 testing
        memory = MemoryService(session_id="fts-test")
        await memory.connect()

        # Insert initial data
        await memory.store("Initial content")

        # Concurrent inserts and searches
        await asyncio.gather(
            *[memory.store(f"Content {i}") for i in range(5)],
            *[memory.search("content", limit=10) for _ in range(5)],
        )

        # All data should be searchable
        results = await memory.search("content", limit=20)

        # Should find at least the items we inserted
        # (May find more if "content" matches test data)
        assert len(results) >= 6  # 1 initial + 5 concurrent

        await memory.close()

    @pytest.mark.asyncio
    async def test_concurrent_archival_writes(self):
        """Concurrent writes to archival memory should not corrupt data.

        This tests that FTS5 triggers handle concurrent inserts.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="concurrent-archival")
        await memory.connect()

        # 20 concurrent writes
        await asyncio.gather(
            *[memory.store(f"Fact {i}") for i in range(20)]
        )

        # All facts should be searchable
        results = await memory.search("Fact", limit=30)

        assert len(results) >= 20

        await memory.close()


class TestSchemaInitIdempotency:
    """Test schema initialization idempotency."""

    @pytest.mark.asyncio
    async def test_connect_multiple_times_idempotent(self):
        """connect() should be safe to call multiple times.

        This tests that schema init is idempotent.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="idempotent-test")

        # Connect multiple times
        await memory.connect()
        await memory.connect()
        await memory.connect()

        # Should work fine
        await memory.set_core("key", "value")
        result = await memory.get_core("key")

        assert result == "value"

        await memory.close()

    @pytest.mark.asyncio
    async def test_schema_init_concurrent_calls(self):
        """Concurrent connect() calls should not corrupt schema.

        This tests that schema init is thread-safe.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="concurrent-init")

        # Concurrent connect calls
        await asyncio.gather(*[memory.connect() for _ in range(5)])

        # Schema should be valid
        await memory.set_core("key", "value")
        result = await memory.get_core("key")

        assert result == "value"

        await memory.close()


class TestConnectionCloseEdgeCases:
    """Test connection close edge cases."""

    @pytest.mark.asyncio
    async def test_close_during_active_query(self):
        """close() during active query should not crash.

        This tests graceful handling of close during operation.
        Note: This might fail, which is OK - it's a TDD test.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="close-test")
        await memory.connect()

        async def long_operation():
            try:
                # Start a long operation
                await memory.store("test content")
                await asyncio.sleep(0.5)
                await memory.search("test", limit=10)
            except Exception:
                # Expected to fail if close happens
                pass

        async def close_connection():
            await asyncio.sleep(0.1)
            await memory.close()

        # Run concurrently
        await asyncio.gather(long_operation(), close_connection())

        # Should not crash (but operation may fail)

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """close() should be safe to call multiple times.

        This tests idempotency of close operation.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="close-idempotent")
        await memory.connect()

        # Close multiple times
        await memory.close()
        await memory.close()
        await memory.close()

        # Should not crash


class TestMemoryServiceConcurrentOperations:
    """Test high-level concurrent operations."""

    @pytest.mark.asyncio
    async def test_mixed_core_and_archival_concurrent_access(self):
        """Concurrent core and archival operations should not interfere.

        This tests that core memory and archival memory operations
        can run concurrently without corruption.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="mixed-ops")
        await memory.connect()

        # Concurrent core and archival operations
        await asyncio.gather(
            *[memory.set_core(f"core{i}", f"value{i}") for i in range(10)],
            *[memory.store(f"Archival fact {i}") for i in range(10)],
        )

        # Verify core memory
        core_results = await asyncio.gather(
            *[memory.get_core(f"core{i}") for i in range(10)]
        )
        assert all(r is not None for r in core_results)

        # Verify archival memory
        archival_results = await memory.search("Archival fact", limit=15)
        assert len(archival_results) >= 10

        await memory.close()

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_recall_during_concurrent_writes(self):
        """recall() during concurrent writes should not crash.

        This tests that recall (which queries multiple sources)
        works correctly during concurrent modifications.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="recall-concurrent")
        await memory.connect()

        # Populate initial data
        await memory.set_core("persona", "Assistant")
        await memory.store("Initial fact")

        # Concurrent recall and writes
        await asyncio.gather(
            *[memory.set_core(f"key{i}", f"val{i}") for i in range(5)],
            *[memory.store(f"Fact {i}") for i in range(5)],
            *[memory.recall("query") for _ in range(5)],
        )

        # Should complete without crashing
        final_recall = await memory.recall("Fact")
        assert final_recall is not None

        await memory.close()


class TestDatabasePathHandling:
    """Test database path handling edge cases."""

    @pytest.mark.asyncio
    async def test_custom_db_path(self):
        """Custom db_path should be respected.

        This tests that custom database paths work correctly.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "custom.db"

            memory = MemoryService(session_id="custom-path", db_path=custom_path)
            await memory.connect()

            await memory.set_core("key", "value")

            await memory.close()

            # Database file should exist
            assert custom_path.exists()

    @pytest.mark.asyncio
    async def test_in_memory_database(self):
        """In-memory database should work for testing.

        This tests that :memory: databases work correctly.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory = MemoryService(session_id="in-memory", db_path=Path(":memory:"))
        await memory.connect()

        await memory.set_core("key", "value")
        result = await memory.get_core("key")

        assert result == "value"

        await memory.close()


class TestSessionIsolation:
    """Test session isolation in SQLite backend."""

    @pytest.mark.asyncio
    async def test_different_sessions_isolated(self):
        """Different sessions should have isolated data.

        This tests that session_id properly isolates data.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory1 = MemoryService(session_id="session1")
        memory2 = MemoryService(session_id="session2")

        await memory1.connect()
        await memory2.connect()

        # Write to session1
        await memory1.set_core("key", "session1-value")

        # Session2 should not see it
        result = await memory2.get_core("key")
        assert result is None

        # Session1 should see it
        result = await memory1.get_core("key")
        assert result == "session1-value"

        await memory1.close()
        await memory2.close()

    @pytest.mark.asyncio
    async def test_concurrent_different_sessions(self):
        """Concurrent operations on different sessions should not interfere.

        This tests that session isolation works under concurrent load.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        memory1 = MemoryService(session_id="concurrent1")
        memory2 = MemoryService(session_id="concurrent2")

        await memory1.connect()
        await memory2.connect()

        # Concurrent writes to different sessions
        await asyncio.gather(
            *[memory1.set_core(f"key{i}", f"session1-{i}") for i in range(10)],
            *[memory2.set_core(f"key{i}", f"session2-{i}") for i in range(10)],
        )

        # Verify isolation
        for i in range(10):
            result1 = await memory1.get_core(f"key{i}")
            result2 = await memory2.get_core(f"key{i}")

            assert result1 == f"session1-{i}"
            assert result2 == f"session2-{i}"

        await memory1.close()
        await memory2.close()
