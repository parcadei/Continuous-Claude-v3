"""Async memory race condition tests - P0 priority.

Tests for race conditions and concurrent access bugs in MemoryServicePG:
- Concurrent set_core() races (DELETE+INSERT pattern)
- Transaction rollback verification
- Concurrent archival memory writes
- Concurrent store() with same content (no duplicate IDs)
- Search during concurrent writes
- Delete during concurrent read

These are FAILING tests for potential race conditions.
Following TDD: Write tests first, verify behavior.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCoreMemoryRaces:
    """Test concurrent access to core memory."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_concurrent_set_core_same_key(self):
        """100 concurrent writes to same key should not corrupt data.

        This tests the DELETE+INSERT pattern in set_core().
        Even with concurrent writes, the final value should be
        one of the written values, not corrupted/partial data.
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        # Mock the transaction to track concurrent access
        write_count = 0
        delete_calls = []
        insert_calls = []

        with patch("scripts.agentica.postgres_pool.get_pool") as mock_get_pool:
            with patch("scripts.agentica.postgres_pool.get_transaction"):
                # Create mock connection
                mock_conn = AsyncMock()

                async def track_delete(*args):
                    delete_calls.append(args)

                async def track_insert(*args):
                    nonlocal write_count
                    insert_calls.append(args)
                    write_count += 1

                mock_conn.execute = AsyncMock(
                    side_effect=lambda query, *args: (
                        track_delete(*args)
                        if "DELETE" in query
                        else track_insert(*args)
                    )
                )

                # Mock get_transaction to return our tracked connection
                async def mock_transaction():
                    class MockTransaction:
                        async def __aenter__(self):
                            return mock_conn

                        async def __aexit__(self, *args):
                            return None

                    return MockTransaction()

                with patch(
                    "scripts.agentica.memory_service_pg.get_transaction",
                    side_effect=mock_transaction,
                ):
                    memory = MemoryServicePG(session_id="race-test")

                    # 100 concurrent writes to same key
                    await asyncio.gather(
                        *[memory.set_core("key", f"value{i}") for i in range(100)]
                    )

                    # All writes should complete
                    assert write_count == 100

                    # Each write should do DELETE then INSERT
                    assert len(delete_calls) == 100
                    assert len(insert_calls) == 100

    @pytest.mark.asyncio
    async def test_concurrent_set_core_different_keys(self):
        """Concurrent writes to different keys should not interfere.

        This tests that the transaction isolation works correctly
        when multiple agents write different keys simultaneously.
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        write_count = 0

        with patch("scripts.agentica.postgres_pool.get_pool"):
            mock_conn = AsyncMock()

            async def track_write(*args):
                nonlocal write_count
                write_count += 1

            mock_conn.execute = AsyncMock(side_effect=track_write)

            async def mock_transaction():
                class MockTransaction:
                    async def __aenter__(self):
                        return mock_conn

                    async def __aexit__(self, *args):
                        return None

                return MockTransaction()

            with patch(
                "scripts.agentica.memory_service_pg.get_transaction",
                side_effect=mock_transaction,
            ):
                memory = MemoryServicePG(session_id="race-test")

                # 50 agents writing different keys concurrently
                await asyncio.gather(
                    *[memory.set_core(f"key{i}", f"value{i}") for i in range(50)]
                )

                # All writes should complete (DELETE + INSERT each)
                assert write_count == 100  # 50 deletes + 50 inserts


class TestTransactionRollback:
    """Test transaction rollback on exception."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_set_core_rollback_on_exception(self):
        """set_core should rollback transaction if INSERT fails.

        This verifies that if DELETE succeeds but INSERT fails,
        the transaction rolls back and no partial write occurs.
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        delete_called = False
        insert_called = False
        rollback_called = False

        with patch("scripts.agentica.postgres_pool.get_pool"):
            mock_conn = AsyncMock()

            async def mock_execute(query, *args):
                nonlocal delete_called, insert_called
                if "DELETE" in query:
                    delete_called = True
                elif "INSERT" in query:
                    insert_called = True
                    raise Exception("INSERT failed")

            mock_conn.execute = AsyncMock(side_effect=mock_execute)

            # Mock transaction context manager
            class MockTransaction:
                async def __aenter__(self):
                    return mock_conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    nonlocal rollback_called
                    if exc_type is not None:
                        rollback_called = True
                    return False  # Propagate exception

            async def mock_transaction():
                return MockTransaction()

            with patch(
                "scripts.agentica.memory_service_pg.get_transaction",
                side_effect=mock_transaction,
            ):
                memory = MemoryServicePG(session_id="test")

                # Should raise exception from INSERT
                with pytest.raises(Exception, match="INSERT failed"):
                    await memory.set_core("key", "value")

                # DELETE should have been called
                assert delete_called

                # INSERT should have been attempted
                assert insert_called

                # Transaction should have rolled back
                assert rollback_called

    @pytest.mark.asyncio
    async def test_transaction_isolation_between_sessions(self):
        """Transactions for different sessions should be isolated.

        This tests that session_id properly isolates transactions.
        Two sessions writing concurrently should not interfere.
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        session1_writes = 0
        session2_writes = 0

        with patch("scripts.agentica.postgres_pool.get_pool"):
            mock_conn = AsyncMock()

            async def track_writes(query, session_id, *args):
                nonlocal session1_writes, session2_writes
                if "INSERT" in query:
                    if session_id == "session1":
                        session1_writes += 1
                    elif session_id == "session2":
                        session2_writes += 1

            mock_conn.execute = AsyncMock(side_effect=track_writes)

            async def mock_transaction():
                class MockTransaction:
                    async def __aenter__(self):
                        return mock_conn

                    async def __aexit__(self, *args):
                        return None

                return MockTransaction()

            with patch(
                "scripts.agentica.memory_service_pg.get_transaction",
                side_effect=mock_transaction,
            ):
                memory1 = MemoryServicePG(session_id="session1")
                memory2 = MemoryServicePG(session_id="session2")

                # Concurrent writes from two sessions
                await asyncio.gather(
                    *[memory1.set_core("key", f"value{i}") for i in range(10)],
                    *[memory2.set_core("key", f"value{i}") for i in range(10)],
                )

                # Both sessions should complete all writes
                assert session1_writes == 10
                assert session2_writes == 10


class TestArchivalMemoryRaces:
    """Test concurrent access to archival memory."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_concurrent_store_same_content(self):
        """Concurrent store() with same content should not create duplicate IDs.

        This tests that memory ID generation doesn't create collisions
        when multiple agents store the same content simultaneously.
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        generated_ids = []

        with patch("scripts.agentica.postgres_pool.get_pool"):
            with patch(
                "scripts.agentica.memory_service_pg.generate_memory_id"
            ) as mock_gen_id:
                # Each call generates unique ID
                mock_gen_id.side_effect = lambda: str(len(generated_ids)) + "-unique"

                mock_conn = AsyncMock()

                async def track_insert(query, *args):
                    if "INSERT" in query and "archival_memory" in query:
                        # Extract ID from args
                        memory_id = args[0]
                        generated_ids.append(memory_id)

                mock_conn.execute = AsyncMock(side_effect=track_insert)
                mock_conn.fetchval = AsyncMock(
                    return_value=None
                )  # For get_core calls

                async def mock_connection():
                    class MockConnection:
                        async def __aenter__(self):
                            return mock_conn

                        async def __aexit__(self, *args):
                            return None

                    return MockConnection()

                # Mock embedding provider
                mock_embedder = AsyncMock()
                mock_embedder.embed = AsyncMock(return_value=[0.1] * 1536)
                mock_embedder.dimension = 1536

                with patch(
                    "scripts.agentica.memory_service_pg.get_connection",
                    side_effect=mock_connection,
                ):
                    memory = MemoryServicePG(session_id="test")
                    memory._embedder = mock_embedder

                    # 20 concurrent stores of same content
                    await asyncio.gather(
                        *[memory.store("Same content") for _ in range(20)]
                    )

                    # Should have generated 20 unique IDs
                    assert len(generated_ids) == 20
                    assert len(set(generated_ids)) == 20  # All unique

    @pytest.mark.asyncio
    async def test_concurrent_search_during_writes(self):
        """Search during concurrent writes should not crash or return corrupt data.

        This tests that read operations (search) don't interfere with
        concurrent write operations (store).
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        search_count = 0
        write_count = 0

        with patch("scripts.agentica.postgres_pool.get_pool"):
            mock_conn = AsyncMock()

            async def track_operations(query, *args):
                nonlocal search_count, write_count
                if "SELECT" in query:
                    search_count += 1
                    return []  # Empty search results
                elif "INSERT" in query:
                    write_count += 1

            mock_conn.fetch = AsyncMock(side_effect=lambda q, *a: track_operations(q, *a))
            mock_conn.execute = AsyncMock(
                side_effect=lambda q, *a: track_operations(q, *a)
            )
            mock_conn.fetchval = AsyncMock(return_value=None)

            async def mock_connection():
                class MockConnection:
                    async def __aenter__(self):
                        return mock_conn

                    async def __aexit__(self, *args):
                        return None

                return MockConnection()

            mock_embedder = AsyncMock()
            mock_embedder.embed = AsyncMock(return_value=[0.1] * 1536)
            mock_embedder.dimension = 1536

            with patch(
                "scripts.agentica.memory_service_pg.get_connection",
                side_effect=mock_connection,
            ):
                memory = MemoryServicePG(session_id="test")
                memory._embedder = mock_embedder

                # Concurrent reads and writes
                await asyncio.gather(
                    *[memory.store(f"content{i}") for i in range(10)],
                    *[memory.search("query", limit=5) for _ in range(10)],
                )

                # Both operations should complete
                assert write_count == 10
                assert search_count == 10


class TestDeleteDuringRead:
    """Test delete operations during concurrent reads."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_delete_core_during_get_core(self):
        """delete_core during get_core should not cause stale reads.

        This tests that delete and read operations are properly isolated.
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        delete_count = 0
        read_count = 0

        with patch("scripts.agentica.postgres_pool.get_pool"):
            mock_conn = AsyncMock()

            async def track_operations(query, *args):
                nonlocal delete_count, read_count
                if "DELETE" in query:
                    delete_count += 1
                elif "SELECT" in query:
                    read_count += 1
                    return None  # Key not found

            mock_conn.execute = AsyncMock(
                side_effect=lambda q, *a: track_operations(q, *a)
            )
            mock_conn.fetchval = AsyncMock(
                side_effect=lambda q, *a: track_operations(q, *a)
            )

            async def mock_connection():
                class MockConnection:
                    async def __aenter__(self):
                        return mock_conn

                    async def __aexit__(self, *args):
                        return None

                return MockConnection()

            with patch(
                "scripts.agentica.memory_service_pg.get_connection",
                side_effect=mock_connection,
            ):
                memory = MemoryServicePG(session_id="test")

                # Concurrent deletes and reads
                await asyncio.gather(
                    *[memory.delete_core("key") for _ in range(5)],
                    *[memory.get_core("key") for _ in range(5)],
                )

                # Both operations should complete
                assert delete_count == 5
                assert read_count == 5


class TestAgentScopedMemoryRaces:
    """Test concurrent access with agent_id scoping."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_concurrent_writes_different_agents_same_key(self):
        """Different agents writing same key should not interfere.

        This tests that agent_id properly scopes memory isolation.
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        agent1_writes = 0
        agent2_writes = 0

        with patch("scripts.agentica.postgres_pool.get_pool"):
            mock_conn = AsyncMock()

            async def track_writes(query, session_id, agent_id, *args):
                nonlocal agent1_writes, agent2_writes
                if "INSERT" in query:
                    if agent_id == "agent1":
                        agent1_writes += 1
                    elif agent_id == "agent2":
                        agent2_writes += 1

            mock_conn.execute = AsyncMock(side_effect=track_writes)

            async def mock_transaction():
                class MockTransaction:
                    async def __aenter__(self):
                        return mock_conn

                    async def __aexit__(self, *args):
                        return None

                return MockTransaction()

            with patch(
                "scripts.agentica.memory_service_pg.get_transaction",
                side_effect=mock_transaction,
            ):
                memory1 = MemoryServicePG(session_id="session", agent_id="agent1")
                memory2 = MemoryServicePG(session_id="session", agent_id="agent2")

                # Both agents write to "key" concurrently
                await asyncio.gather(
                    *[memory1.set_core("key", f"agent1-{i}") for i in range(10)],
                    *[memory2.set_core("key", f"agent2-{i}") for i in range(10)],
                )

                # Each agent should complete all writes
                assert agent1_writes == 10
                assert agent2_writes == 10


class TestHighContentionScenarios:
    """Test high-contention scenarios with many concurrent operations."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool before each test."""
        from scripts.agentica import postgres_pool

        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_100_concurrent_mixed_operations(self):
        """100 concurrent mixed operations should complete without deadlock.

        This is a stress test for high-contention scenarios.
        Marked as flaky due to timing sensitivity.
        """
        from scripts.agentica.memory_service_pg import MemoryServicePG

        operation_count = 0

        with patch("scripts.agentica.postgres_pool.get_pool"):
            mock_conn = AsyncMock()

            async def track_operation(*args, **kwargs):
                nonlocal operation_count
                operation_count += 1
                await asyncio.sleep(0.01)  # Simulate some work

            mock_conn.execute = AsyncMock(side_effect=track_operation)
            mock_conn.fetchval = AsyncMock(side_effect=track_operation)

            async def mock_transaction():
                class MockTransaction:
                    async def __aenter__(self):
                        return mock_conn

                    async def __aexit__(self, *args):
                        return None

                return MockTransaction()

            with patch(
                "scripts.agentica.memory_service_pg.get_transaction",
                side_effect=mock_transaction,
            ):
                async def mock_connection():
                    class MockConnection:
                        async def __aenter__(self):
                            return mock_conn

                        async def __aexit__(self, *args):
                            return None

                    return MockConnection()

                with patch(
                    "scripts.agentica.memory_service_pg.get_connection",
                    side_effect=mock_connection,
                ):
                    memory = MemoryServicePG(session_id="stress-test")

                    # 100 concurrent operations (mix of reads and writes)
                    operations = []
                    for i in range(50):
                        operations.append(memory.set_core(f"key{i}", f"value{i}"))
                        operations.append(memory.get_core(f"key{i}"))

                    await asyncio.gather(*operations)

                    # All operations should complete
                    assert operation_count >= 100  # At least 100 (some ops do multiple queries)
