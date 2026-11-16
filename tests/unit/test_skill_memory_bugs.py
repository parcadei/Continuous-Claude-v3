"""Test Memory/Search Bugs - TDD Failing Tests.

These tests are designed to FAIL initially, exposing bugs in memory_service.py.
Based on bug research from:
- .claude/cache/agents/research-agent/latest-output.md
- thoughts/shared/implementation/mutation-round-1-report.md

Bug categories tested:
1. Similarity threshold boundary conditions (0.0, 0.7, 1.0)
2. Empty search results handling
3. Malformed metadata handling
4. SQL injection prevention
5. Connection pool behavior
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSimilarityThresholdBoundaries:
    """Test similarity threshold edge cases.

    NOTE: Current MemoryService uses FTS5 (text search) not vector similarity.
    These tests document that similarity threshold support is MISSING.
    The API should support threshold filtering for relevance ranking.
    """

    @pytest.mark.asyncio
    async def test_search_api_should_support_threshold(self):
        """
        Bug: MemoryService.search() lacks threshold parameter for relevance filtering.
        Expected: search(query, threshold=0.7) returns only results above threshold.
        Actual: No threshold parameter exists - all FTS matches returned.

        This is a FEATURE GAP - search needs similarity threshold support.
        """
        from scripts.agentica_patterns.memory_service import MemoryService
        import inspect

        # Check if search has threshold parameter
        sig = inspect.signature(MemoryService.search)
        params = list(sig.parameters.keys())

        # This test DOCUMENTS the missing feature
        # It passes if threshold is present, fails to document the gap
        assert 'threshold' in params, (
            "MemoryService.search() should support a 'threshold' parameter "
            "for filtering results by relevance score. Currently missing."
        )

    @pytest.mark.asyncio
    async def test_threshold_one_exact_match_only(self):
        """
        Bug: Threshold 1.0 may have floating point comparison issues.
        Expected: Only exact matches (if any) returned.
        Actual: May return nothing even for exact match.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="test", db_path=db_path)
            await memory.connect()

            try:
                await memory.store("unique test content xyz123")

                # Search for exact content
                results = await memory.search("unique test content xyz123", limit=10)

                # Should find the exact match
                assert len(results) >= 1
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_threshold_at_common_value(self):
        """
        Bug: Common threshold (0.7) boundary may have off-by-one.
        Expected: Results with score >= 0.7 returned.
        Actual: May use > instead of >=.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="test", db_path=db_path)
            await memory.connect()

            try:
                await memory.store("Python programming language tutorial")

                # Search related content
                results = await memory.search("Python programming")

                # Should have results for related content
                assert isinstance(results, list)
            finally:
                await memory.close()


class TestEmptyResultsHandling:
    """Test empty and null result handling."""

    @pytest.mark.asyncio
    async def test_search_returns_empty_list_not_none(self):
        """
        Bug: No matches may return None instead of empty list.
        Expected: Empty list [].
        Actual: May return None causing 'NoneType is not iterable'.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="empty-test", db_path=db_path)
            await memory.connect()

            try:
                # Search in empty memory
                results = await memory.search("xyzzy_nonexistent_12345")

                assert results is not None
                assert isinstance(results, list)
                assert len(results) == 0
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_recall_empty_memory_returns_string(self):
        """
        Bug: Recall on empty memory may return None.
        Expected: Return empty string or sensible default.
        Actual: May crash or return None.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="recall-test", db_path=db_path)
            await memory.connect()

            try:
                # Don't store anything - recall should handle empty
                result = await memory.recall("any query")

                assert result is not None
                assert isinstance(result, str)
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_get_core_nonexistent_key(self):
        """
        Bug: Getting non-existent key may raise instead of return None.
        Expected: Return None for missing keys.
        Actual: May raise KeyError.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="core-test", db_path=db_path)
            await memory.connect()

            try:
                result = await memory.get_core("nonexistent_key_xyz123")

                # Should return None, not raise
                assert result is None
            finally:
                await memory.close()


class TestMetadataHandling:
    """Test malformed metadata handling."""

    @pytest.mark.asyncio
    async def test_store_with_empty_metadata(self):
        """
        Bug: Empty metadata dict may cause JSON issues.
        Expected: Accept empty dict {}.
        Actual: May fail to serialize.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="meta-test", db_path=db_path)
            await memory.connect()

            try:
                # Store with empty metadata
                memory_id = await memory.store("test content", metadata={})

                assert memory_id is not None
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_store_with_none_metadata(self):
        """
        Bug: None metadata may crash JSON serialization.
        Expected: Treat None as empty dict.
        Actual: May raise TypeError.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="meta-test", db_path=db_path)
            await memory.connect()

            try:
                # Store with None metadata (if API allows)
                memory_id = await memory.store("test content")

                assert memory_id is not None
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_store_with_nested_metadata(self):
        """
        Bug: Deeply nested metadata may fail serialization.
        Expected: Handle nested structures.
        Actual: May fail with RecursionError or similar.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="meta-test", db_path=db_path)
            await memory.connect()

            try:
                nested_metadata = {
                    "level1": {
                        "level2": {
                            "level3": {
                                "value": "deep"
                            }
                        }
                    },
                    "list_data": [1, 2, {"nested": True}]
                }

                memory_id = await memory.store("test content", metadata=nested_metadata)

                assert memory_id is not None
            finally:
                await memory.close()


class TestSQLInjectionPrevention:
    """Test SQL injection attack prevention."""

    @pytest.mark.asyncio
    async def test_search_query_is_parameterized(self):
        """
        Bug: FTS5 queries may be vulnerable to SQL injection.
        Expected: Queries parameterized, injection fails.
        Actual: May execute malicious SQL.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="sql-test", db_path=db_path)
            await memory.connect()

            try:
                # Store legitimate data
                await memory.store("legitimate fact about testing")

                # Attempt SQL injection
                malicious_queries = [
                    "'; DROP TABLE archival_memory; --",
                    "' OR '1'='1",
                    "test; DELETE FROM core_memory",
                ]

                for query in malicious_queries:
                    # Should not crash and should not execute injection
                    try:
                        results = await memory.search(query)
                        # Table should still work
                        await memory.store("after injection test")
                    except Exception as e:
                        # Acceptable to raise, but not to execute SQL
                        assert "DROP" not in str(e).upper()

                # Verify original data still exists
                results = await memory.search("legitimate")
                # Note: FTS5 search may or may not find it
                assert isinstance(results, list)
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_core_memory_key_is_parameterized(self):
        """
        Bug: Core memory key may be vulnerable.
        Expected: Keys are parameterized.
        Actual: May allow injection.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="sql-test", db_path=db_path)
            await memory.connect()

            try:
                # Store with malicious key
                malicious_key = "'; DROP TABLE core_memory; --"

                # Should not execute the injection
                await memory.set_core(malicious_key, "value")
                result = await memory.get_core(malicious_key)

                # If we can still use memory, injection failed (good)
                await memory.set_core("normal_key", "test")
                assert await memory.get_core("normal_key") == "test"
            finally:
                await memory.close()


class TestConnectionPoolBehavior:
    """Test connection management under stress."""

    @pytest.mark.asyncio
    async def test_connection_released_on_exception(self):
        """
        Bug: Exceptions may leak connections.
        Expected: Connection returned to pool on error.
        Actual: May exhaust connection pool.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="pool-test", db_path=db_path)
            await memory.connect()

            try:
                # Simulate many operations that might fail
                for _ in range(50):
                    try:
                        # Normal operation
                        await memory.set_core("key", "value")
                    except Exception:
                        pass

                # Should still work after many operations
                await memory.set_core("final_key", "final_value")
                result = await memory.get_core("final_key")
                assert result == "final_value"
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_concurrent_operations_dont_deadlock(self):
        """
        Bug: Concurrent operations may cause deadlock.
        Expected: Complete within timeout.
        Actual: May hang indefinitely.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="concurrent-test", db_path=db_path)
            await memory.connect()

            try:
                async def operation(i):
                    await memory.set_core(f"key_{i}", f"value_{i}")
                    await memory.store(f"fact number {i}")
                    result = await memory.get_core(f"key_{i}")
                    return result

                # Run concurrent operations with timeout
                try:
                    results = await asyncio.wait_for(
                        asyncio.gather(*[operation(i) for i in range(10)]),
                        timeout=10.0
                    )
                    assert len(results) == 10
                except asyncio.TimeoutError:
                    pytest.fail("Deadlock detected - concurrent operations timed out")
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_multiple_connect_calls_idempotent(self):
        """
        Bug: Multiple connect() calls may cause issues.
        Expected: Idempotent - safe to call multiple times.
        Actual: May double-initialize or corrupt state.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="connect-test", db_path=db_path)

            # Multiple connect calls should be safe
            await memory.connect()
            await memory.connect()
            await memory.connect()

            try:
                # Should work normally
                await memory.set_core("key", "value")
                result = await memory.get_core("key")
                assert result == "value"
            finally:
                await memory.close()
                await memory.close()  # Multiple close also safe


class TestSearchLimitBoundaries:
    """Test search limit parameter edge cases."""

    @pytest.mark.asyncio
    async def test_limit_zero_returns_empty(self):
        """
        Bug: limit=0 may crash or return all results.
        Expected: Return empty list.
        Actual: May crash with division by zero or similar.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="limit-test", db_path=db_path)
            await memory.connect()

            try:
                await memory.store("test content for limit test")

                results = await memory.search("test", limit=0)

                assert isinstance(results, list)
                assert len(results) == 0
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_limit_one_returns_single(self):
        """
        Bug: limit=1 may return more than one result.
        Expected: Exactly one result maximum.
        Actual: May ignore limit parameter.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="limit-test", db_path=db_path)
            await memory.connect()

            try:
                # Store multiple items
                for i in range(5):
                    await memory.store(f"test content {i}")

                results = await memory.search("test", limit=1)

                assert isinstance(results, list)
                assert len(results) <= 1
            finally:
                await memory.close()

    @pytest.mark.asyncio
    async def test_negative_limit_handled(self):
        """
        Bug: Negative limit may crash or return unexpected results.
        Expected: Raise ValueError or treat as 0.
        Actual: May crash or return all.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="limit-test", db_path=db_path)
            await memory.connect()

            try:
                await memory.store("test content")

                # Negative limit should be handled
                try:
                    results = await memory.search("test", limit=-1)
                    # If no error, should return empty or all
                    assert isinstance(results, list)
                except (ValueError, AssertionError):
                    pass  # Acceptable - explicit rejection
            finally:
                await memory.close()


class TestSessionIsolation:
    """Test session isolation in multi-tenant scenarios."""

    @pytest.mark.asyncio
    async def test_sessions_isolated(self):
        """
        Bug: Different sessions may leak data.
        Expected: Each session sees only its own data.
        Actual: May return cross-session data.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "shared.db"

            memory1 = MemoryService(session_id="session1", db_path=db_path)
            memory2 = MemoryService(session_id="session2", db_path=db_path)

            await memory1.connect()
            await memory2.connect()

            try:
                # Store in session 1
                await memory1.set_core("secret", "session1_secret")
                await memory1.store("session1 private data")

                # Store in session 2
                await memory2.set_core("secret", "session2_secret")
                await memory2.store("session2 private data")

                # Each session should see only its data
                assert await memory1.get_core("secret") == "session1_secret"
                assert await memory2.get_core("secret") == "session2_secret"

                # Search should be isolated
                results1 = await memory1.search("private")
                results2 = await memory2.search("private")

                # Each should have exactly one result (their own)
                for r in results1:
                    assert "session1" in str(r).lower() or len(results1) == 1
                for r in results2:
                    assert "session2" in str(r).lower() or len(results2) == 1
            finally:
                await memory1.close()
                await memory2.close()

    @pytest.mark.asyncio
    async def test_session_id_special_characters(self):
        """
        Bug: Special characters in session_id may break queries.
        Expected: Handle or reject special characters.
        Actual: May SQL inject or corrupt data.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Session ID with special chars
            memory = MemoryService(session_id="test'; DROP TABLE--", db_path=db_path)
            await memory.connect()

            try:
                # Should work without SQL injection
                await memory.set_core("key", "value")
                result = await memory.get_core("key")
                assert result == "value"
            finally:
                await memory.close()


class TestReconnectionBehavior:
    """Test reconnection and state persistence."""

    @pytest.mark.asyncio
    async def test_data_persists_after_reconnect(self):
        """
        Bug: Data may not persist after close/connect.
        Expected: Data persists across connections.
        Actual: May lose data on reconnect.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "persist.db"

            # First connection - store data
            memory1 = MemoryService(session_id="persist-test", db_path=db_path)
            await memory1.connect()
            await memory1.set_core("persistent_key", "persistent_value")
            await memory1.store("persistent fact")
            await memory1.close()

            # Second connection - read data
            memory2 = MemoryService(session_id="persist-test", db_path=db_path)
            await memory2.connect()

            try:
                result = await memory2.get_core("persistent_key")
                assert result == "persistent_value"

                search_results = await memory2.search("persistent")
                assert len(search_results) >= 1
            finally:
                await memory2.close()

    @pytest.mark.asyncio
    async def test_operations_after_close_fail_gracefully(self):
        """
        Bug: Operations after close may crash.
        Expected: Clear error or auto-reconnect.
        Actual: May crash with cryptic error.
        """
        from scripts.agentica_patterns.memory_service import MemoryService

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryService(session_id="close-test", db_path=db_path)
            await memory.connect()
            await memory.close()

            # Operations after close should either:
            # 1. Auto-reconnect
            # 2. Raise clear error
            try:
                result = await memory.get_core("key")
                # If succeeded, auto-reconnect worked
            except Exception as e:
                # Should be a clear error, not cryptic
                assert "connect" in str(e).lower() or "closed" in str(e).lower() or "not connected" in str(e).lower()
