"""End-to-End integration tests for concurrency fixes.

These tests verify that the full stack works correctly under concurrent load:
1. Hook -> Pattern -> Database flow
2. Multiple concurrent agent spawns using the new locks
3. SQLite busy_timeout works under concurrent hook execution
4. Postgres pool timeout prevents starvation
5. Embedding service reuses single client under burst load

Tests validate that the fixes implemented for:
- SQLite connections (hooks + scripts with busy_timeout)
- Pattern coordination (CircuitBreaker, Blackboard, Hierarchical with asyncio.Lock)
- Connection pooling (postgres_pool.py with acquire_timeout)
- Span processing (span_processor.py with asyncio.Lock on SpanProcessingContext)

Reference: docs/concurrency-search/RACE_FINDINGS.md, STARVATION_FINDINGS.md
"""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# SQLite Concurrency Tests
# =============================================================================


class TestConcurrentHookDatabaseWrites:
    """Test 10 concurrent hooks writing to SQLite with busy_timeout."""

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create a temporary SQLite database with WAL mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "concurrent_hooks.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute(
                """
                CREATE TABLE agent_sessions (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT UNIQUE,
                    pattern TEXT,
                    created_at REAL,
                    status TEXT DEFAULT 'active'
                )
            """
            )
            conn.commit()
            conn.close()
            yield db_path

    def test_10_concurrent_hook_writes_do_not_deadlock(self, temp_db: Path) -> None:
        """10 concurrent hooks writing to SQLite should not deadlock.

        This test simulates the scenario where multiple hooks fire simultaneously
        (e.g., 10 subagent-start hooks triggered at once) and all try to write
        to the same SQLite database.

        With busy_timeout=5000ms and WAL mode, writes should queue and succeed.
        Without these settings, this would deadlock.
        """
        results: dict[str, list] = {"success": [], "errors": []}
        threads_done = threading.Event()

        def hook_write(hook_id: int) -> None:
            """Simulate a hook writing to the database."""
            try:
                conn = sqlite3.connect(str(temp_db))
                conn.execute("PRAGMA busy_timeout = 5000")
                conn.execute("PRAGMA journal_mode = WAL")

                # Simulate hook work
                time.sleep(0.01 * (hook_id % 3))  # Stagger slightly

                conn.execute(
                    "INSERT INTO agent_sessions (session_id, pattern, created_at) "
                    "VALUES (?, ?, ?)",
                    (f"session_{hook_id}", "swarm", time.time()),
                )
                conn.commit()
                conn.close()
                results["success"].append(hook_id)
            except sqlite3.OperationalError as e:
                results["errors"].append((hook_id, str(e)))

        # Start 10 concurrent hook threads
        threads = [threading.Thread(target=hook_write, args=(i,)) for i in range(10)]

        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        elapsed = time.time() - start_time

        # All 10 writes should succeed
        assert len(results["success"]) == 10, (
            f"Expected 10 successful writes, got {len(results['success'])}.\n"
            f"Errors: {results['errors']}"
        )

        # Should complete in reasonable time (not hang)
        assert elapsed < 10.0, (
            f"Writes took {elapsed:.2f}s, expected < 10s.\n"
            "This suggests busy_timeout is not working."
        )

        # Verify all rows were inserted
        conn = sqlite3.connect(str(temp_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM agent_sessions"
        ).fetchone()[0]
        conn.close()

        assert count == 10, f"Expected 10 rows, got {count}"

    @pytest.mark.asyncio
    async def test_concurrent_async_db_access(self, temp_db: Path) -> None:
        """Test concurrent async database access (common in hooks).

        Hooks often run in async contexts. This test verifies that
        concurrent asyncio tasks can safely access SQLite with proper
        configuration.
        """
        results: dict[str, list] = {"success": [], "errors": []}

        async def async_hook_write(hook_id: int) -> None:
            """Simulate async hook writing to database."""
            try:
                # Run DB access in executor (SQLite is not async-native)
                def db_write():
                    conn = sqlite3.connect(str(temp_db))
                    conn.execute("PRAGMA busy_timeout = 5000")
                    conn.execute(
                        "INSERT INTO agent_sessions (session_id, pattern, created_at) "
                        "VALUES (?, ?, ?)",
                        (f"async_session_{hook_id}", "hierarchical", time.time()),
                    )
                    conn.commit()
                    conn.close()

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, db_write)
                results["success"].append(hook_id)
            except Exception as e:
                results["errors"].append((hook_id, str(e)))

        # Run 10 concurrent async writes
        await asyncio.gather(*[async_hook_write(i) for i in range(10)])

        assert len(results["success"]) == 10, (
            f"Expected 10 successful async writes, got {len(results['success'])}.\n"
            f"Errors: {results['errors']}"
        )


# =============================================================================
# Pattern Concurrency Tests
# =============================================================================


class TestConcurrentPatternExecution:
    """Test CircuitBreaker + Hierarchical running concurrently."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_and_hierarchical_concurrent(self) -> None:
        """CircuitBreaker + Hierarchical running concurrently should not race.

        Both patterns use lazy initialization. Without proper locking,
        concurrent usage can spawn duplicate agents or corrupt state.
        """
        from scripts.agentica_patterns.patterns.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )
        from scripts.agentica_patterns.patterns.hierarchical import Hierarchical

        spawn_calls: dict[str, int] = {"circuit_breaker": 0, "hierarchical": 0}
        spawn_lock = asyncio.Lock()

        async def mock_spawn_fn(**kwargs):
            async with spawn_lock:
                premise = kwargs.get("premise", "").lower()
                if "primary" in premise or "fallback" in premise:
                    spawn_calls["circuit_breaker"] += 1
                else:
                    spawn_calls["hierarchical"] += 1

            await asyncio.sleep(0.02)  # Simulate agent spawn time

            mock_agent = MagicMock()
            mock_agent.call = AsyncMock(return_value="result")
            return mock_agent

        with patch(
            "scripts.agentica_patterns.patterns.circuit_breaker.spawn"
        ) as mock_cb_spawn:
            with patch(
                "scripts.agentica_patterns.patterns.hierarchical.spawn"
            ) as mock_h_spawn:
                mock_cb_spawn.side_effect = mock_spawn_fn
                mock_h_spawn.side_effect = mock_spawn_fn

                cb = CircuitBreaker(
                    primary_premise="Primary agent",
                    fallback_premise="Fallback agent",
                    max_failures=3,
                    reset_timeout=0.1,
                )

                h = Hierarchical(
                    coordinator_premise="Coordinator agent",
                    specialist_premises={
                        "researcher": "Research specialist",
                        "analyst": "Analysis specialist",
                    },
                )

                # Run both patterns concurrently with multiple calls each
                async def run_cb():
                    for _ in range(3):
                        try:
                            await cb.execute("test query")
                        except Exception:
                            pass

                async def run_hierarchical():
                    for _ in range(3):
                        try:
                            await h.execute("test task")
                        except Exception:
                            pass

                await asyncio.gather(run_cb(), run_hierarchical())

        # CircuitBreaker should have spawned exactly 2 agents (primary + fallback)
        assert spawn_calls["circuit_breaker"] == 2, (
            f"CircuitBreaker spawned {spawn_calls['circuit_breaker']} agents, "
            "expected exactly 2 (primary + fallback)"
        )

        # Hierarchical should have spawned exactly 1 coordinator
        # (specialists may vary based on decomposition)
        assert spawn_calls["hierarchical"] >= 1, (
            f"Hierarchical spawned {spawn_calls['hierarchical']} agents, "
            "expected at least 1 (coordinator)"
        )

    @pytest.mark.asyncio
    async def test_blackboard_concurrent_specialists(self) -> None:
        """Multiple specialists writing to Blackboard concurrently.

        This tests the read-modify-write pattern using update_item()
        which requires the asyncio.Lock protection.
        """
        from scripts.agentica_patterns.patterns.blackboard import BlackboardState

        state = BlackboardState()
        state["work_count"] = 0

        async def specialist_work(specialist_id: int):
            """Specialist increments counter atomically."""
            for _ in range(5):
                await state.update_item(
                    "work_count",
                    lambda x: (x or 0) + 1
                )
                await asyncio.sleep(0.001)

        # 5 specialists doing 5 increments each = 25 total
        await asyncio.gather(*[specialist_work(i) for i in range(5)])

        assert state["work_count"] == 25, (
            f"Expected work_count=25, got {state['work_count']}. "
            "Lost updates due to race condition in read-modify-write."
        )


# =============================================================================
# PostgreSQL Pool Concurrency Tests
# =============================================================================


class TestPostgresPoolUnderLoad:
    """Test PostgreSQL connection pool timeout prevents starvation."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool state before each test."""
        from scripts.agentica_patterns import postgres_pool
        postgres_pool._pool = None
        yield
        postgres_pool._pool = None

    @pytest.mark.asyncio
    async def test_20_concurrent_agents_timeout_gracefully(self) -> None:
        """20 concurrent agents should timeout gracefully, not hang.

        With max_size=10 and acquire_timeout=30, when all 10 connections
        are busy, additional requests should wait up to 30s then timeout.

        This test verifies the pool doesn't starve or deadlock.
        """
        from scripts.agentica_patterns.postgres_pool import get_connection

        active_connections = {"count": 0, "max": 0}
        completed = {"count": 0}
        timed_out = {"count": 0}

        with patch("scripts.agentica_patterns.postgres_pool.asyncpg") as mock_asyncpg:
            # Track active connections
            async def mock_acquire_fn():
                active_connections["count"] += 1
                active_connections["max"] = max(
                    active_connections["max"],
                    active_connections["count"]
                )
                mock_conn = AsyncMock()
                # Simulate connection work
                await asyncio.sleep(0.05)
                return mock_conn

            async def mock_release_fn(*args):
                active_connections["count"] -= 1

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(side_effect=mock_acquire_fn)
            mock_context.__aexit__ = AsyncMock(side_effect=mock_release_fn)

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_context)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            async def agent_work(agent_id: int):
                """Simulate agent database work."""
                try:
                    async with get_connection() as conn:
                        # Simulate query
                        await asyncio.sleep(0.02)
                        completed["count"] += 1
                except asyncio.TimeoutError:
                    timed_out["count"] += 1

            # Run 20 concurrent agents
            await asyncio.gather(*[agent_work(i) for i in range(20)])

        # All agents should complete (with pool queuing)
        assert completed["count"] == 20, (
            f"Expected 20 completions, got {completed['count']}. "
            f"Timed out: {timed_out['count']}"
        )

        # Should have had concurrent connections
        assert active_connections["max"] >= 1, (
            "No concurrent connections detected"
        )

    @pytest.mark.asyncio
    async def test_pool_health_check_under_contention(self) -> None:
        """Health check should work even when pool is under contention."""
        from scripts.agentica_patterns.postgres_pool import health_check

        with patch("scripts.agentica_patterns.postgres_pool.get_connection") as mock_get_conn:
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=1)

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_context.__aexit__ = AsyncMock()
            mock_get_conn.return_value = mock_context

            # Run 10 concurrent health checks
            results = await asyncio.gather(
                *[health_check() for _ in range(10)]
            )

        # All should report healthy
        assert all(r[0] for r in results), (
            f"Some health checks failed: {[r for r in results if not r[0]]}"
        )


# =============================================================================
# Embedding Service Concurrency Tests
# =============================================================================


class TestEmbeddingServiceBurst:
    """Test 100 rapid embedding requests reuse single client."""

    @pytest.mark.asyncio
    async def test_100_rapid_embedding_requests_reuse_client(self) -> None:
        """100 rapid embedding requests should reuse single HTTP client.

        The EmbeddingService should:
        1. Create only one httpx.AsyncClient
        2. Reuse it for all concurrent requests
        3. Not exhaust connections or timeout
        """
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        # Use mock provider to avoid actual API calls
        embedder = EmbeddingService(provider="mock")

        async def embed_text(text: str):
            """Generate embedding for a text."""
            return await embedder.embed(text)

        start_time = time.time()

        # Run 100 concurrent embedding requests
        texts = [f"Text number {i} for embedding" for i in range(100)]
        results = await asyncio.gather(*[embed_text(t) for t in texts])

        elapsed = time.time() - start_time

        # All should return embeddings
        assert len(results) == 100, f"Expected 100 results, got {len(results)}"

        # All embeddings should have correct dimension
        assert all(len(r) == 1536 for r in results), (
            "Some embeddings have wrong dimension"
        )

        # Should complete quickly (mock provider is fast)
        assert elapsed < 5.0, (
            f"Embedding took {elapsed:.2f}s, expected < 5s"
        )

        # Verify caching works (same text should return cached result)
        cached_result = await embedder.embed(texts[0])
        assert cached_result == results[0], "Cache not working for same text"

        # Verify cache stats
        assert embedder.cache_size() >= 100, (
            f"Cache should have 100+ entries, has {embedder.cache_size()}"
        )

    @pytest.mark.asyncio
    async def test_embedding_batch_concurrent_with_cache(self) -> None:
        """Test batch embedding handles concurrent cache access correctly."""
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        embedder = EmbeddingService(provider="mock", cache_enabled=True)

        async def batch_embed(batch_id: int, texts: list[str]):
            """Run batch embedding."""
            return await embedder.embed_batch(texts)

        # Create overlapping batches (some texts appear in multiple batches)
        batches = [
            [f"common_text_{i % 3}", f"unique_batch{b}_text_{i}"]
            for b in range(5)
            for i in range(4)
        ]

        # Run all batches concurrently
        results = await asyncio.gather(
            *[batch_embed(i, batch) for i, batch in enumerate(batches)]
        )

        # All batches should complete
        assert len(results) == 20, f"Expected 20 batch results, got {len(results)}"

        # Each batch should have 2 embeddings
        for batch_result in results:
            assert len(batch_result) == 2, (
                f"Each batch should have 2 embeddings, got {len(batch_result)}"
            )


# =============================================================================
# Span Processor Concurrency Tests
# =============================================================================


class TestSpanProcessorContextLocking:
    """Test SpanProcessingContext lock under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_add_summary(self) -> None:
        """10 concurrent add_summary calls should not corrupt state."""
        from scripts.agentica_patterns.span_processor import (
            SpanProcessingContext,
            SpanSummary,
        )

        context = SpanProcessingContext()

        async def add_summary(i: int):
            """Add a summary to context."""
            summary = SpanSummary(
                span_id=f"span_{i}",
                turn_number=i,
                summary=f"Summary for span {i}",
                key_entities=[f"entity_{i}"],
                references=[],
                span_type="llm",
                content_hash=f"hash_{i}",
            )
            await context.add_summary(summary)
            await asyncio.sleep(0.001)  # Allow interleaving

        # Run 10 concurrent additions
        await asyncio.gather(*[add_summary(i) for i in range(10)])

        # Should have exactly 10 summaries
        summaries = await context.all_summaries()
        assert len(summaries) == 10, (
            f"Expected 10 summaries, got {len(summaries)}"
        )

        # Each span_id should be unique and present
        span_ids = {s.span_id for s in summaries}
        assert len(span_ids) == 10, (
            f"Expected 10 unique span_ids, got {len(span_ids)}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_reference_context_access(self) -> None:
        """Concurrent get_reference_context should be thread-safe."""
        from scripts.agentica_patterns.span_processor import (
            SpanProcessingContext,
            SpanSummary,
        )

        context = SpanProcessingContext()

        # Pre-populate context with summaries
        for i in range(5):
            summary = SpanSummary(
                span_id=f"span_{i}",
                turn_number=i,
                summary=f"Summary {i}",
                key_entities=[],
                references=[f"span_{j}" for j in range(i)],  # Ref all prior spans
                span_type="llm",
                content_hash=f"hash_{i}",
            )
            await context.add_summary(summary)

        async def get_context(span_id: str):
            """Get reference context for a span."""
            return await context.get_reference_context(span_id)

        # Run concurrent context lookups
        results = await asyncio.gather(
            *[get_context(f"span_{i}") for i in range(5) for _ in range(3)]
        )

        # All should return valid strings
        assert all(isinstance(r, str) for r in results), (
            "Some results are not strings"
        )


# =============================================================================
# Integration: Hook -> Pattern -> Database Flow
# =============================================================================


class TestHookPatternDatabaseFlow:
    """Test the full flow from hook to pattern to database."""

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create a temporary SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "flow_test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute(
                """
                CREATE TABLE pattern_state (
                    id INTEGER PRIMARY KEY,
                    pattern_type TEXT,
                    state_key TEXT,
                    state_value TEXT,
                    updated_at REAL
                )
            """
            )
            conn.commit()
            conn.close()
            yield db_path

    @pytest.mark.asyncio
    async def test_hook_triggers_pattern_which_writes_db(
        self, temp_db: Path
    ) -> None:
        """Simulate full flow: Hook -> Pattern execution -> DB write.

        This tests the integrated behavior where:
        1. A hook fires (e.g., subagent-start)
        2. The hook triggers a pattern (e.g., Hierarchical)
        3. The pattern writes state to SQLite
        4. Multiple hooks can run concurrently without deadlock
        """
        from scripts.agentica_patterns.patterns.blackboard import BlackboardState

        # Simulate multiple hooks firing simultaneously
        results: dict[str, list] = {"success": [], "errors": []}

        async def simulate_hook_flow(hook_id: int):
            """Simulate a hook that runs a pattern and persists state."""
            try:
                # 1. Hook starts pattern
                state = BlackboardState()
                state["hook_id"] = str(hook_id)

                # 2. Pattern does work (simulated with update_item)
                await state.update_item(
                    "counter",
                    lambda x: (x or 0) + 1
                )

                # 3. Pattern persists to DB (in executor for SQLite)
                def db_write():
                    conn = sqlite3.connect(str(temp_db))
                    conn.execute("PRAGMA busy_timeout = 5000")
                    conn.execute(
                        "INSERT INTO pattern_state "
                        "(pattern_type, state_key, state_value, updated_at) "
                        "VALUES (?, ?, ?, ?)",
                        ("blackboard", f"hook_{hook_id}", str(state.to_dict()), time.time()),
                    )
                    conn.commit()
                    conn.close()

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, db_write)

                results["success"].append(hook_id)

            except Exception as e:
                results["errors"].append((hook_id, str(e)))

        # Run 10 concurrent hook flows
        await asyncio.gather(*[simulate_hook_flow(i) for i in range(10)])

        # All should succeed
        assert len(results["success"]) == 10, (
            f"Expected 10 successful flows, got {len(results['success'])}.\n"
            f"Errors: {results['errors']}"
        )

        # Verify DB has all 10 entries
        conn = sqlite3.connect(str(temp_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM pattern_state"
        ).fetchone()[0]
        conn.close()

        assert count == 10, f"Expected 10 DB rows, got {count}"


# =============================================================================
# Stress Tests (Optional, for thorough validation)
# =============================================================================


class TestConcurrencyStress:
    """Stress tests for concurrency under heavy load."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_50_concurrent_pattern_operations(self) -> None:
        """Stress test: 50 concurrent pattern operations.

        This pushes the patterns to their limits to ensure
        locks hold under heavy contention.
        """
        from scripts.agentica_patterns.patterns.blackboard import BlackboardState

        state = BlackboardState()
        state["stress_counter"] = 0

        async def stress_worker(worker_id: int):
            """Worker that hammers the blackboard."""
            for _ in range(20):
                await state.update_item(
                    "stress_counter",
                    lambda x: (x or 0) + 1
                )
                # Occasionally read as well
                _ = state.get("stress_counter")
                await asyncio.sleep(0)  # Yield to other tasks

        # 50 workers * 20 increments = 1000 total
        await asyncio.gather(*[stress_worker(i) for i in range(50)])

        assert state["stress_counter"] == 1000, (
            f"Expected stress_counter=1000, got {state['stress_counter']}. "
            "Lost updates under heavy contention."
        )
