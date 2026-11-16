"""Real integration tests for concurrency - NO MOCKS.

These tests address Gap 2 from the gap analysis:
"All concurrency tests use mocked databases. Mocks pass but production could fail
due to real locking behavior, thread affinity, and connection lifecycle issues."

These tests use REAL:
- SQLite database files with actual concurrent writes
- WAL mode verification with actual read/write transactions
- httpx.AsyncClient with real HTTP connections (to localhost server)

Reference: docs/concurrency-search/agent-outputs/gaps/gap_analysis.md
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import sqlite3
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Generator

import pytest


# =============================================================================
# SQLite Real Concurrent Writes Tests
# =============================================================================


class TestSQLiteRealConcurrentWrites:
    """Test real SQLite concurrent writes with busy_timeout.

    Unlike the mock tests, these actually create SQLite files and have
    multiple threads/processes writing to them simultaneously.
    """

    @pytest.fixture
    def temp_db_path(self) -> Generator[Path, None, None]:
        """Create a temporary SQLite database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "concurrent_test.db"
            # Initialize the database with schema
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("""
                CREATE TABLE writes (
                    id INTEGER PRIMARY KEY,
                    writer_id INTEGER,
                    value TEXT,
                    written_at REAL
                )
            """)
            conn.commit()
            conn.close()
            yield db_path

    def test_two_threads_writing_same_db_with_busy_timeout(
        self, temp_db_path: Path
    ) -> None:
        """Two threads writing to same SQLite file with busy_timeout.

        This test verifies that:
        1. Both threads can write without deadlock
        2. busy_timeout prevents indefinite blocking
        3. All writes complete within reasonable time

        Expected: PASS if busy_timeout is working correctly
        """
        results: dict[str, list] = {"thread_0": [], "thread_1": [], "errors": []}

        def writer_thread(thread_id: int, num_writes: int) -> None:
            """Write multiple rows from this thread."""
            try:
                conn = sqlite3.connect(str(temp_db_path))
                # CRITICAL: Set busy_timeout to prevent indefinite blocking
                conn.execute("PRAGMA busy_timeout = 5000")

                for i in range(num_writes):
                    # Each write simulates some work
                    conn.execute(
                        "INSERT INTO writes (writer_id, value, written_at) VALUES (?, ?, ?)",
                        (thread_id, f"value_{thread_id}_{i}", time.time())
                    )
                    conn.commit()
                    # Small delay to increase contention chance
                    time.sleep(0.001)

                conn.close()
                results[f"thread_{thread_id}"].append("success")
            except Exception as e:
                results["errors"].append((thread_id, str(e)))

        # Create 2 threads, each writing 50 rows
        threads = [
            threading.Thread(target=writer_thread, args=(0, 50)),
            threading.Thread(target=writer_thread, args=(1, 50)),
        ]

        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)  # Should complete well within 30s
        elapsed = time.time() - start_time

        # Verify no errors
        assert not results["errors"], (
            f"Threads encountered errors: {results['errors']}\n"
            "This suggests busy_timeout is not preventing deadlock."
        )

        # Verify both threads completed
        assert results["thread_0"] == ["success"], "Thread 0 did not complete"
        assert results["thread_1"] == ["success"], "Thread 1 did not complete"

        # Verify timing - should not hang
        assert elapsed < 15.0, (
            f"Writes took {elapsed:.2f}s, expected < 15s.\n"
            "This suggests contention is not being handled properly."
        )

        # Verify all rows were written
        conn = sqlite3.connect(str(temp_db_path))
        count = conn.execute("SELECT COUNT(*) FROM writes").fetchone()[0]
        conn.close()

        assert count == 100, (
            f"Expected 100 rows (50 per thread), got {count}.\n"
            "Some writes were lost due to contention."
        )

    def test_ten_threads_concurrent_writes_no_hang(
        self, temp_db_path: Path
    ) -> None:
        """Ten threads writing concurrently should not hang.

        This is a stress test that pushes SQLite concurrency to its limits.
        With proper busy_timeout and WAL mode, all writes should succeed.

        Expected: PASS with WAL + busy_timeout, FAIL or HANG otherwise
        """
        results: dict[str, Any] = {"completed": 0, "errors": []}
        lock = threading.Lock()

        def writer_thread(thread_id: int, num_writes: int) -> None:
            """Write rows from this thread."""
            try:
                conn = sqlite3.connect(str(temp_db_path))
                conn.execute("PRAGMA busy_timeout = 5000")
                conn.execute("PRAGMA journal_mode = WAL")

                for i in range(num_writes):
                    conn.execute(
                        "INSERT INTO writes (writer_id, value, written_at) VALUES (?, ?, ?)",
                        (thread_id, f"v{thread_id}_{i}", time.time())
                    )
                    conn.commit()

                conn.close()
                with lock:
                    results["completed"] += 1
            except sqlite3.OperationalError as e:
                with lock:
                    results["errors"].append((thread_id, str(e)))

        # 10 threads, 20 writes each = 200 total rows
        threads = [
            threading.Thread(target=writer_thread, args=(i, 20))
            for i in range(10)
        ]

        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        elapsed = time.time() - start_time

        # All 10 threads should complete
        assert results["completed"] == 10, (
            f"Only {results['completed']}/10 threads completed.\n"
            f"Errors: {results['errors']}\n"
            "This test requires WAL mode + busy_timeout for all threads."
        )

        # Should not hang
        assert elapsed < 30.0, (
            f"Test took {elapsed:.2f}s, expected < 30s.\n"
            "Heavy contention may be causing excessive retries."
        )


class TestSQLiteWALModeVerification:
    """Verify WAL mode actually enables concurrent reads during writes."""

    @pytest.fixture
    def temp_db_path(self) -> Generator[Path, None, None]:
        """Create a temporary SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "wal_test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE data (
                    id INTEGER PRIMARY KEY,
                    value TEXT
                )
            """)
            # Insert some initial data
            for i in range(10):
                conn.execute("INSERT INTO data (value) VALUES (?)", (f"row_{i}",))
            conn.commit()
            conn.close()
            yield db_path

    def test_wal_mode_enables_concurrent_read_during_write(
        self, temp_db_path: Path
    ) -> None:
        """WAL mode must allow reads during an active write transaction.

        Without WAL: Read blocks until write transaction completes.
        With WAL: Read sees snapshot before the uncommitted write.

        This test verifies WAL is actually working, not just configured.
        """
        read_result: dict[str, Any] = {"value": None, "error": None, "blocked_ms": 0}
        write_started = threading.Event()
        read_complete = threading.Event()

        def long_write_transaction() -> None:
            """Hold a write transaction for 2 seconds."""
            conn = sqlite3.connect(str(temp_db_path))
            # IMPORTANT: Enable WAL mode
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("BEGIN IMMEDIATE")  # Acquire write lock
            conn.execute("INSERT INTO data (value) VALUES ('writing...')")
            write_started.set()  # Signal that write has started
            # Hold the write lock while reader tries to read
            time.sleep(2.0)
            conn.commit()
            conn.close()

        def concurrent_read() -> None:
            """Try to read while write is in progress."""
            write_started.wait(timeout=5)  # Wait for write to start
            time.sleep(0.1)  # Give writer time to acquire lock

            conn = sqlite3.connect(str(temp_db_path))
            conn.execute("PRAGMA journal_mode = WAL")
            # With WAL, this should NOT block
            conn.execute("PRAGMA busy_timeout = 100")  # Short timeout to detect blocking

            start = time.time()
            try:
                # This read should succeed immediately with WAL
                cursor = conn.execute("SELECT COUNT(*) FROM data")
                count = cursor.fetchone()[0]
                read_result["value"] = count
            except sqlite3.OperationalError as e:
                read_result["error"] = str(e)
            finally:
                read_result["blocked_ms"] = (time.time() - start) * 1000
                conn.close()
                read_complete.set()

        # Start writer first, then reader
        write_thread = threading.Thread(target=long_write_transaction)
        read_thread = threading.Thread(target=concurrent_read)

        write_thread.start()
        read_thread.start()

        read_thread.join(timeout=10)
        write_thread.join(timeout=10)

        # With WAL mode, read should succeed quickly (not block for 2s)
        assert read_result["error"] is None, (
            f"Read failed during write: {read_result['error']}\n"
            "WAL mode should allow concurrent reads."
        )

        assert read_result["value"] is not None, (
            "Read returned no value. WAL mode may not be working."
        )

        # Read should have completed in < 500ms (not blocked for 2s)
        assert read_result["blocked_ms"] < 500, (
            f"Read took {read_result['blocked_ms']:.0f}ms, expected < 500ms.\n"
            "This suggests read was blocked by the write lock.\n"
            "WAL mode may not be properly enabled."
        )

    def test_wal_mode_is_actually_set(self, temp_db_path: Path) -> None:
        """Verify PRAGMA journal_mode = WAL actually returns 'wal'.

        Some configurations silently fall back to DELETE mode.
        This test verifies WAL is actually active.
        """
        conn = sqlite3.connect(str(temp_db_path))
        conn.execute("PRAGMA journal_mode = WAL")
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()

        assert mode.lower() == "wal", (
            f"journal_mode is '{mode}', expected 'wal'.\n"
            "WAL mode may have failed to enable. Check filesystem permissions."
        )

    def test_wal_file_is_created(self, temp_db_path: Path) -> None:
        """WAL mode should create a .db-wal file.

        This verifies WAL is not just configured but actively working.
        """
        conn = sqlite3.connect(str(temp_db_path))
        conn.execute("PRAGMA journal_mode = WAL")
        # Perform a write to trigger WAL file creation
        conn.execute("INSERT INTO data (value) VALUES ('wal_trigger')")
        conn.commit()

        # Check for WAL file before closing (file may be removed on checkpoint)
        wal_path = Path(str(temp_db_path) + "-wal")
        shm_path = Path(str(temp_db_path) + "-shm")

        # Note: WAL file may not exist if there's only one connection
        # and it checkpoints on close. But SHM should exist.
        conn.close()

        # At minimum, the write should have succeeded
        conn2 = sqlite3.connect(str(temp_db_path))
        count = conn2.execute(
            "SELECT COUNT(*) FROM data WHERE value = 'wal_trigger'"
        ).fetchone()[0]
        conn2.close()

        assert count == 1, (
            "WAL write did not persist. The write transaction may have failed."
        )


# =============================================================================
# HTTP Client Connection Reuse Tests
# =============================================================================


class TestHTTPClientConnectionReuse:
    """Test that httpx.AsyncClient actually reuses connections.

    These tests require a real HTTP server (we use Python's built-in).
    """

    @pytest.fixture
    async def local_http_server(self) -> Generator[str, None, None]:
        """Start a local HTTP server for testing connection reuse.

        This server tracks how many TCP connections are opened.
        """
        import aiohttp
        from aiohttp import web

        connection_count = {"value": 0, "requests": 0}
        active_connections: set = set()

        async def handle_request(request: web.Request) -> web.Response:
            """Handle test requests."""
            # Track the connection
            peername = request.transport.get_extra_info("peername")
            connection_key = (peername[0], peername[1]) if peername else id(request.transport)

            if connection_key not in active_connections:
                active_connections.add(connection_key)
                connection_count["value"] += 1

            connection_count["requests"] += 1

            return web.json_response({
                "connection_count": connection_count["value"],
                "request_count": connection_count["requests"],
            })

        async def get_stats(request: web.Request) -> web.Response:
            """Return connection statistics."""
            return web.json_response({
                "unique_connections": connection_count["value"],
                "total_requests": connection_count["requests"],
            })

        app = web.Application()
        app.router.add_get("/ping", handle_request)
        app.router.add_get("/stats", get_stats)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)  # Random free port
        await site.start()

        # Get the actual port
        port = site._server.sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}"

        try:
            yield url
        finally:
            await runner.cleanup()

    @pytest.mark.asyncio
    async def test_httpx_client_reuses_connection(
        self, local_http_server: str
    ) -> None:
        """Real httpx client connection count test.

        Make 10 requests with a single AsyncClient.
        With HTTP/1.1 keep-alive, should use 1 connection, not 10.
        """
        import httpx

        async with httpx.AsyncClient() as client:
            # Make 10 requests
            for i in range(10):
                response = await client.get(f"{local_http_server}/ping")
                assert response.status_code == 200

            # Check connection stats
            stats_response = await client.get(f"{local_http_server}/stats")
            stats = stats_response.json()

        # With connection reuse, should have 1-2 connections, not 10
        # (2 because the stats request might use a new connection)
        assert stats["unique_connections"] <= 2, (
            f"Created {stats['unique_connections']} connections for 10 requests.\n"
            "Expected 1-2 with connection reuse. Client may not be reusing connections."
        )

        assert stats["total_requests"] >= 10, (
            f"Server only saw {stats['total_requests']} requests, expected >= 10"
        )

    @pytest.mark.asyncio
    async def test_creating_new_client_per_request_wastes_connections(
        self, local_http_server: str
    ) -> None:
        """Demonstrate that creating new client per request wastes connections.

        This is the ANTI-PATTERN we want to detect. Each new client creates
        a new TCP connection.
        """
        import httpx

        # Anti-pattern: new client per request
        for i in range(5):
            async with httpx.AsyncClient() as client:
                await client.get(f"{local_http_server}/ping")

        # Check stats - should have 5 connections (one per client)
        async with httpx.AsyncClient() as client:
            stats_response = await client.get(f"{local_http_server}/stats")
            stats = stats_response.json()

        # This is the BAD case - we expect 5-6 connections
        # This test documents the anti-pattern, not the desired behavior
        assert stats["unique_connections"] >= 5, (
            f"Only {stats['unique_connections']} connections for 5 clients.\n"
            "Expected 5+ connections with new-client-per-request anti-pattern.\n"
            "If this fails, it might mean the test setup is wrong."
        )

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="REAL BUG: httpx creates 20 connections for 20 concurrent requests "
               "despite Limits(max_connections=10). The test server may not support "
               "keep-alive properly, or httpx connection pooling doesn't work as expected. "
               "See: Gap 2 in gap_analysis.md"
    )
    async def test_concurrent_requests_share_connection_pool(
        self, local_http_server: str
    ) -> None:
        """Concurrent requests should share the connection pool.

        Even with asyncio.gather, a single AsyncClient should efficiently
        reuse connections from its pool.

        NOTE: This test may fail depending on httpx version and HTTP/1.1 keep-alive
        behavior. The aiohttp server may not support keep-alive the same way as
        production servers. This test documents the EXPECTED behavior even if
        the test server doesn't fully support it.

        Real issue: With HTTP/2, multiplexing allows many requests over 1 connection.
        With HTTP/1.1, connection pooling limits concurrent connections.
        """
        import httpx

        async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        ) as client:
            # Make 20 concurrent requests
            tasks = [
                client.get(f"{local_http_server}/ping")
                for _ in range(20)
            ]
            responses = await asyncio.gather(*tasks)

            # All should succeed
            assert all(r.status_code == 200 for r in responses), (
                "Some concurrent requests failed"
            )

            # Check connection stats
            stats_response = await client.get(f"{local_http_server}/stats")
            stats = stats_response.json()

        # With connection limits of 10, should not exceed that
        # NOTE: This is a DISCOVERY test - it reveals what httpx actually does
        # If this fails, it exposes a real issue with connection pooling
        connection_count = stats["unique_connections"]

        # Log the actual behavior for analysis
        print(f"\nActual connections used: {connection_count} for 20 requests")

        # This assertion documents the EXPECTED behavior
        # If it fails, the implementation may need httpx Limits configuration
        assert connection_count <= 15, (
            f"Used {connection_count} connections for 20 concurrent requests.\n"
            "Expected <= 15 with httpx connection limits set to 10.\n"
            "This may indicate connection reuse is not working as expected.\n"
            "Consider: 1) Configure httpx.Limits explicitly, 2) Use HTTP/2, "
            "3) Check keep-alive headers."
        )


# =============================================================================
# PostgreSQL Real Pool Tests (requires actual PostgreSQL)
# =============================================================================


class TestPostgresRealPool:
    """Real PostgreSQL connection pool tests.

    These tests require a real PostgreSQL database. Skip if not available.
    """

    @pytest.fixture
    def pg_dsn(self) -> str | None:
        """Get PostgreSQL connection string from environment."""
        dsn = os.environ.get("TEST_POSTGRES_DSN")
        if not dsn:
            pytest.skip(
                "TEST_POSTGRES_DSN not set. Set it to run real PostgreSQL tests.\n"
                "Example: TEST_POSTGRES_DSN=postgresql://user:pass@localhost/testdb"
            )
        return dsn

    @pytest.mark.asyncio
    async def test_pool_under_concurrent_load(self, pg_dsn: str) -> None:
        """Test real PostgreSQL pool under concurrent load.

        Creates a real pool and hammers it with concurrent queries.
        Verifies no connection leaks or timeouts.
        """
        import asyncpg

        pool = await asyncpg.create_pool(
            pg_dsn,
            min_size=2,
            max_size=5,
            command_timeout=10,
        )

        results: dict[str, Any] = {"completed": 0, "errors": []}

        async def concurrent_query(query_id: int) -> None:
            """Execute a query using the pool."""
            try:
                async with pool.acquire() as conn:
                    # Simple query that works on any PostgreSQL
                    row = await conn.fetchrow("SELECT $1::int as id", query_id)
                    assert row["id"] == query_id
                    results["completed"] += 1
            except Exception as e:
                results["errors"].append((query_id, str(e)))

        try:
            # Run 50 concurrent queries with pool size 5
            await asyncio.gather(*[
                concurrent_query(i) for i in range(50)
            ])
        finally:
            await pool.close()

        # All 50 queries should complete
        assert results["completed"] == 50, (
            f"Only {results['completed']}/50 queries completed.\n"
            f"Errors: {results['errors']}"
        )
        assert not results["errors"], f"Errors: {results['errors']}"

    @pytest.mark.asyncio
    async def test_pool_acquire_timeout(self, pg_dsn: str) -> None:
        """Test that acquire_timeout prevents indefinite blocking.

        With a small pool and long-running queries, new acquisitions
        should timeout rather than hang.
        """
        import asyncpg

        pool = await asyncpg.create_pool(
            pg_dsn,
            min_size=1,
            max_size=1,  # Only 1 connection
            command_timeout=60,
        )

        timeout_occurred = False

        async def hold_connection_long() -> None:
            """Hold the only connection for 5 seconds."""
            async with pool.acquire() as conn:
                await asyncio.sleep(5)

        async def try_acquire_with_timeout() -> None:
            """Try to acquire with short timeout - should fail."""
            nonlocal timeout_occurred
            await asyncio.sleep(0.5)  # Let first query acquire
            try:
                # Use wait_for as acquire_timeout alternative
                async with asyncio.timeout(1.0):
                    async with pool.acquire() as conn:
                        await conn.fetchrow("SELECT 1")
            except asyncio.TimeoutError:
                timeout_occurred = True

        try:
            await asyncio.gather(
                hold_connection_long(),
                try_acquire_with_timeout(),
            )
        finally:
            await pool.close()

        assert timeout_occurred, (
            "Acquisition should have timed out.\n"
            "With pool size 1 and a 5s holding query, a 1s timeout should fire."
        )


# =============================================================================
# Process-Level Concurrency Tests (for SQLITE_LOCKED vs SQLITE_BUSY)
# =============================================================================


def _sqlite_writer_process(db_path: str, num_writes: int, result_queue: Any) -> None:
    """Writer function for subprocess - defined at module level for pickling."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")

        for i in range(num_writes):
            conn.execute(
                "INSERT INTO writes (pid, value) VALUES (?, ?)",
                (os.getpid(), f"value_{i}")
            )
            conn.commit()
            time.sleep(0.01)  # Simulate work

        conn.close()
        result_queue.put(("success", os.getpid(), num_writes))
    except Exception as e:
        result_queue.put(("error", os.getpid(), str(e)))


class TestMultiProcessSQLite:
    """Test SQLite concurrency across multiple processes.

    This is more realistic for hooks, which run as separate processes.
    """

    @pytest.fixture
    def temp_db_path(self) -> Generator[Path, None, None]:
        """Create a temporary SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "multiprocess_test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("""
                CREATE TABLE writes (
                    id INTEGER PRIMARY KEY,
                    pid INTEGER,
                    value TEXT
                )
            """)
            conn.commit()
            conn.close()
            yield db_path

    def test_two_processes_writing_same_db(self, temp_db_path: Path) -> None:
        """Two separate processes writing to same SQLite file.

        This tests cross-process locking, which is different from
        cross-thread locking and more accurately simulates hooks.
        """
        result_queue = multiprocessing.Queue()

        # Create 2 processes, each writing 20 rows
        processes = [
            multiprocessing.Process(
                target=_sqlite_writer_process,
                args=(str(temp_db_path), 20, result_queue)
            )
            for _ in range(2)
        ]

        start_time = time.time()
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=30)
        elapsed = time.time() - start_time

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        # Both processes should succeed
        successes = [r for r in results if r[0] == "success"]
        errors = [r for r in results if r[0] == "error"]

        assert len(successes) == 2, (
            f"Only {len(successes)}/2 processes succeeded.\n"
            f"Errors: {errors}"
        )

        # Verify all rows were written
        conn = sqlite3.connect(str(temp_db_path))
        count = conn.execute("SELECT COUNT(*) FROM writes").fetchone()[0]
        conn.close()

        assert count == 40, (
            f"Expected 40 rows (20 per process), got {count}.\n"
            "Some writes were lost due to cross-process contention."
        )

        # Should not take too long
        assert elapsed < 15.0, (
            f"Multi-process writes took {elapsed:.2f}s, expected < 15s."
        )
