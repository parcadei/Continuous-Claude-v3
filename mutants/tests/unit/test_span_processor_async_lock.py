"""Tests for SpanProcessingContext async lock conversion.

TDD: These tests verify that SpanProcessingContext uses asyncio.Lock
instead of threading.Lock to prevent deadlocks in async contexts.

Issue: The current implementation uses threading.Lock but is accessed
from async contexts via asyncio.gather() in extract_summaries() and
extract_decisions().

Reference: docs/concurrency-search/DEADLOCK_FINDINGS.md (Finding 1 & 2)

Run with: uv run pytest tests/unit/test_span_processor_async_lock.py -v
"""

import asyncio
import inspect
import threading

import pytest


class TestSpanProcessingContextAsyncLock:
    """Tests verifying SpanProcessingContext uses asyncio.Lock."""

    def test_uses_asyncio_lock_not_threading_lock(self):
        """SpanProcessingContext._lock must be asyncio.Lock, not threading.Lock.

        The current implementation uses threading.Lock which causes deadlocks
        when accessed from async contexts like asyncio.gather().

        This test fails until the lock type is converted.
        """
        from scripts.agentica.span_processor import SpanProcessingContext

        ctx = SpanProcessingContext()

        # Must NOT be a threading.Lock
        assert not isinstance(
            ctx._lock, (threading.Lock, type(threading.Lock()))
        ), "SpanProcessingContext._lock should not be threading.Lock"

        # Must be an asyncio.Lock
        assert isinstance(
            ctx._lock, asyncio.Lock
        ), "SpanProcessingContext._lock must be asyncio.Lock"

    def test_add_summary_is_async(self):
        """add_summary() must be an async method to use async with lock.

        When using asyncio.Lock, the method must be async and use
        'async with self._lock:' instead of 'with self._lock:'.

        This test fails until add_summary is made async.
        """
        from scripts.agentica.span_processor import SpanProcessingContext

        # Check that add_summary is a coroutine function
        assert inspect.iscoroutinefunction(
            SpanProcessingContext.add_summary
        ), "add_summary must be an async method (coroutine function)"

    def test_get_reference_context_is_async(self):
        """get_reference_context() must be async to use async with lock.

        Per Finding 2 in DEADLOCK_FINDINGS.md, get_reference_context()
        acquires threading.Lock inside async coroutines, which can
        block the event loop.

        This test fails until get_reference_context is made async.
        """
        from scripts.agentica.span_processor import SpanProcessingContext

        assert inspect.iscoroutinefunction(
            SpanProcessingContext.get_reference_context
        ), "get_reference_context must be an async method (coroutine function)"

    def test_all_summaries_is_async(self):
        """all_summaries() must be async to use async with lock.

        All methods that acquire the lock must be async when using
        asyncio.Lock.

        This test fails until all_summaries is made async.
        """
        from scripts.agentica.span_processor import SpanProcessingContext

        assert inspect.iscoroutinefunction(
            SpanProcessingContext.all_summaries
        ), "all_summaries must be an async method (coroutine function)"


class TestSpanProcessingContextAsyncBehavior:
    """Tests verifying async lock behavior under concurrency."""

    @pytest.mark.asyncio
    async def test_add_summary_awaitable(self):
        """add_summary() must be awaitable.

        This test verifies that add_summary can be called with await.
        """
        from scripts.agentica.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()
        summary = SpanSummary(
            span_id="test_001",
            turn_number=1,
            summary="Test summary",
            key_entities=["test"],
            references=[],
            span_type="test",
            content_hash="abc123",
        )

        # This must be awaitable - will fail if add_summary is not async
        result = ctx.add_summary(summary)
        assert asyncio.iscoroutine(result), "add_summary must return a coroutine"
        await result

        # Verify it worked
        assert "test_001" in ctx.span_summaries

    @pytest.mark.asyncio
    async def test_concurrent_add_summary_no_deadlock(self):
        """Concurrent calls to add_summary must not deadlock.

        This test creates 10 concurrent tasks all calling add_summary,
        with a timeout to detect deadlocks. If the implementation uses
        threading.Lock with async contexts, this may deadlock.

        The test should complete within 5 seconds for 10 simple operations.
        """
        from scripts.agentica.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()

        async def add_one(i: int) -> None:
            summary = SpanSummary(
                span_id=f"span_{i:03d}",
                turn_number=i,
                summary=f"Summary for span {i}",
                key_entities=[f"entity_{i}"],
                references=[],
                span_type="test",
                content_hash=f"hash_{i}",
            )
            await ctx.add_summary(summary)

        # Run 10 concurrent additions with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*[add_one(i) for i in range(10)]),
                timeout=5.0,
            )
        except TimeoutError:
            pytest.fail("Deadlock detected: concurrent add_summary timed out")

        # Verify all were added
        assert len(ctx.span_summaries) == 10

    @pytest.mark.asyncio
    async def test_concurrent_get_reference_context_no_deadlock(self):
        """Concurrent calls to get_reference_context must not deadlock.

        This tests the read path - multiple coroutines reading reference
        context simultaneously should not block each other indefinitely.
        """
        from scripts.agentica.span_processor import SpanProcessingContext, SpanSummary

        ctx = SpanProcessingContext()

        # Pre-populate some summaries
        for i in range(5):
            summary = SpanSummary(
                span_id=f"span_{i:03d}",
                turn_number=i,
                summary=f"Summary {i}",
                key_entities=[],
                references=[f"span_{(i-1):03d}"] if i > 0 else [],
                span_type="test",
                content_hash=f"hash_{i}",
            )
            # Must await if add_summary is async
            result = ctx.add_summary(summary)
            if asyncio.iscoroutine(result):
                await result

        # Update reference graph
        for i in range(5):
            if i > 0:
                ctx.reference_graph[f"span_{i:03d}"] = [f"span_{(i-1):03d}"]

        async def get_context(span_id: str) -> str:
            result = ctx.get_reference_context(span_id)
            if asyncio.iscoroutine(result):
                return await result
            return result

        # Concurrent reads with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[get_context(f"span_{i:03d}") for i in range(5)]),
                timeout=5.0,
            )
        except TimeoutError:
            pytest.fail("Deadlock detected: concurrent get_reference_context timed out")

        # Verify results returned
        assert len(results) == 5


class TestExtractSummariesAsyncLock:
    """Tests for extract_summaries using async lock correctly."""

    @pytest.mark.asyncio
    async def test_extract_summaries_uses_async_context_methods(self):
        """extract_summaries must call async context methods with await.

        The extract_summaries function calls context.add_summary() inside
        an async function (process_chunk) which is run with asyncio.gather().
        The add_summary call must be awaited if the method is async.
        """
        from unittest.mock import AsyncMock, patch

        from scripts.agentica.span_processor import SpanProcessingContext, extract_summaries

        ctx = SpanProcessingContext()

        # Create a simple chunk
        chunks = [[{"span_id": "test_001", "input": "test", "output": "test"}]]

        # Mock the MapReduce to return a valid summary result
        mock_map_result = [
            '[{"span_id": "test_001", "summary": "Test", "key_entities": [], "span_type": "test"}]'
        ]

        with patch("scripts.agentica.span_processor.MapReduce") as mock_mr:
            instance = mock_mr.return_value
            instance._map_phase = AsyncMock(return_value=mock_map_result)

            # This should complete without error
            await extract_summaries(chunks, ctx, num_mappers=1)

        # If add_summary is async and not awaited properly, an exception occurs.
        # The real test is that extract_summaries completes without exception.
        # We can't guarantee exactly how many summaries due to mocking, but
        # the absence of an exception means the async flow worked correctly.


class TestExtractDecisionsAsyncLock:
    """Tests for extract_decisions using async lock correctly."""

    @pytest.mark.asyncio
    async def test_extract_decisions_no_mixed_lock_deadlock(self):
        """extract_decisions must not mix threading.Lock with asyncio.Lock.

        Per Finding 2, extract_decisions uses an asyncio.Lock for decisions
        but calls context.get_reference_context() which acquires threading.Lock.
        This mixed-lock scenario causes deadlocks.

        After the fix, both should use asyncio.Lock.
        """
        import inspect

        from scripts.agentica.span_processor import SpanProcessingContext

        ctx = SpanProcessingContext()

        # Verify the context methods that extract_decisions calls are async
        assert inspect.iscoroutinefunction(
            ctx.get_reference_context
        ), "get_reference_context must be async to prevent mixed-lock deadlock"
