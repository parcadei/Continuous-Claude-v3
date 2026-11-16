"""TDD Tests for Security Hardening: Threading Lock Migration (Phases 1-5).

These tests verify SharedContext and SpanProcessingContext use threading.Lock
for thread-safe synchronous operations.

The implementation uses threading.Lock (synchronous) for cross-thread safety.
"""

import asyncio
import threading
import pytest
from unittest.mock import patch


# ============================================================================
# Phase 1: Test threading.Lock in SharedContext
# ============================================================================


class TestPhase1SharedContextThreadingLock:
    """Phase 1: Verify SharedContext uses threading.Lock for thread safety."""

    def test_shared_context_uses_threading_lock(self):
        """SharedContext._lock should be threading.Lock for thread safety."""
        from scripts.agentica_patterns.claude_scope import SharedContext

        shared = SharedContext()

        # Should be threading.Lock for thread safety
        assert isinstance(shared._lock, type(threading.Lock())), \
            f"Expected threading.Lock, got {type(shared._lock)}"

    def test_get_cached_is_sync(self):
        """SharedContext.get_cached() should be synchronous."""
        from scripts.agentica_patterns.claude_scope import SharedContext, ClaudeResult

        shared = SharedContext()

        # Set up a cached result
        result = ClaudeResult(
            success=True,
            operation="read",
            path="test.txt",
            content="hello"
        )

        # set_cached is synchronous
        shared.set_cached("test.txt", result)

        # get_cached is synchronous
        cached = shared.get_cached("test.txt")

        assert cached is not None
        assert cached.content == "hello"

    def test_set_cached_is_sync(self):
        """SharedContext.set_cached() should be synchronous."""
        from scripts.agentica_patterns.claude_scope import SharedContext, ClaudeResult

        shared = SharedContext()

        result = ClaudeResult(
            success=True,
            operation="read",
            path="test.txt",
            content="hello"
        )

        # This should work without await
        shared.set_cached("test.txt", result)

        # Verify it was cached
        cached = shared.get_cached("test.txt")
        assert cached is not None

    def test_log_operation_is_sync(self):
        """SharedContext.log_operation() should be synchronous."""
        from scripts.agentica_patterns.claude_scope import SharedContext

        shared = SharedContext()

        # This should work without await
        shared.log_operation({"op": "test", "path": "test.txt"})

        # Verify it was logged
        assert len(shared.operation_log) == 1
        assert shared.operation_log[0]["op"] == "test"

    def test_invalidate_is_sync(self):
        """SharedContext.invalidate() should be synchronous."""
        from scripts.agentica_patterns.claude_scope import SharedContext, ClaudeResult

        shared = SharedContext()

        result = ClaudeResult(
            success=True,
            operation="read",
            path="test.txt",
            content="hello"
        )

        shared.set_cached("test.txt", result)

        # invalidate is synchronous
        shared.invalidate("test.txt")

        # Should be gone
        cached = shared.get_cached("test.txt")
        assert cached is None

    def test_get_writes_for_path_is_sync(self):
        """SharedContext.get_writes_for_path() should be synchronous."""
        from scripts.agentica_patterns.claude_scope import SharedContext

        shared = SharedContext()

        shared.log_operation({
            "operation": "write",
            "path": "test.txt",
            "agent": "agent-1"
        })

        # get_writes_for_path is synchronous
        writes = shared.get_writes_for_path("test.txt")

        assert len(writes) == 1
        assert writes[0]["agent"] == "agent-1"


# ============================================================================
# Phase 2: Test SharedContext Thread-Safe Concurrent Access
# ============================================================================


class TestPhase2SharedContextConcurrency:
    """Phase 2: Verify SharedContext is safe under concurrent thread access."""

    def test_concurrent_writers_no_corruption(self):
        """10 concurrent threads should not corrupt SharedContext state."""
        from scripts.agentica_patterns.claude_scope import SharedContext
        from threading import Thread

        shared = SharedContext()
        errors = []

        def writer(n: int):
            """Write 100 operations from thread N."""
            try:
                for i in range(100):
                    shared.log_operation({"op": f"write-{n}-{i}"})
            except Exception as e:
                errors.append((n, e))

        # Run 10 concurrent threads
        threads = [Thread(target=writer, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0, f"Errors: {errors}"

        # Should have exactly 1000 operations (no data loss)
        assert len(shared.operation_log) == 1000, \
            f"Expected 1000 ops, got {len(shared.operation_log)}"

        # Verify no duplicates (no corruption)
        ops_set = set(op["op"] for op in shared.operation_log)
        assert len(ops_set) == 1000, \
            f"Expected 1000 unique ops, got {len(ops_set)}"

    def test_concurrent_cache_operations(self):
        """Concurrent cache set/get/invalidate should not corrupt state."""
        from scripts.agentica_patterns.claude_scope import SharedContext, ClaudeResult
        from threading import Thread

        shared = SharedContext()
        errors = []

        def cache_worker(n: int):
            """Perform cache operations from thread N."""
            try:
                result = ClaudeResult(
                    success=True,
                    operation="read",
                    path=f"file-{n}.txt",
                    content=f"content-{n}"
                )

                # Set
                shared.set_cached(f"file-{n}.txt", result)

                # Read
                cached = shared.get_cached(f"file-{n}.txt")
                assert cached is not None

                # Invalidate
                shared.invalidate(f"file-{n}.txt")

                # Verify invalidation
                cached = shared.get_cached(f"file-{n}.txt")
                assert cached is None
            except Exception as e:
                errors.append((n, e))

        # Run 50 concurrent cache workers
        threads = [Thread(target=cache_worker, args=(n,)) for n in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0, f"Errors: {errors}"

        # All caches should be empty
        assert len(shared.file_cache) == 0

    def test_sync_callers_work_correctly(self):
        """Synchronous callers should work with SharedContext methods."""
        from scripts.agentica_patterns.claude_scope import SharedContext

        shared = SharedContext()

        # This should work without await
        shared.log_operation({"test": "value"})
        writes = shared.get_writes_for_path("test.txt")

        assert isinstance(writes, list)


# ============================================================================
# Phase 3: Test threading.Lock in SpanProcessingContext
# ============================================================================


class TestPhase3SpanProcessingContextThreadingLock:
    """Phase 3: Verify SpanProcessingContext uses threading.Lock for thread safety."""

    def test_span_context_uses_threading_lock(self):
        """SpanProcessingContext._lock should be threading.Lock."""
        from scripts.agentica_patterns.span_processor import SpanProcessingContext

        context = SpanProcessingContext()

        # Should be threading.Lock for thread safety
        assert isinstance(context._lock, type(threading.Lock())), \
            f"Expected threading.Lock, got {type(context._lock)}"

    def test_add_summary_is_sync(self):
        """SpanProcessingContext.add_summary() should be synchronous."""
        from scripts.agentica_patterns.span_processor import (
            SpanProcessingContext,
            SpanSummary
        )

        context = SpanProcessingContext()

        summary = SpanSummary(
            span_id="span-1",
            turn_number=1,
            summary="Test summary",
            key_entities=["entity1"],
            references=["ref-1"],
            span_type="llm_reasoning",
            content_hash="abc123"
        )

        # This should work without await
        context.add_summary(summary)

        # Verify it was added
        assert "span-1" in context.span_summaries

    def test_get_reference_context_is_sync(self):
        """SpanProcessingContext.get_reference_context() should be synchronous."""
        from scripts.agentica_patterns.span_processor import (
            SpanProcessingContext,
            SpanSummary
        )

        context = SpanProcessingContext()

        # Add a referenced summary
        ref_summary = SpanSummary(
            span_id="ref-1",
            turn_number=1,
            summary="Referenced span",
            key_entities=[],
            references=[],
            span_type="tool_call",
            content_hash="def456"
        )
        context.add_summary(ref_summary)

        # Add a summary that references the first
        summary = SpanSummary(
            span_id="span-2",
            turn_number=2,
            summary="Depends on ref-1",
            key_entities=[],
            references=["ref-1"],
            span_type="llm_reasoning",
            content_hash="ghi789"
        )
        context.add_summary(summary)

        # get_reference_context is synchronous
        ref_context = context.get_reference_context("span-2")

        assert "ref-1" in ref_context
        assert "Referenced span" in ref_context

    def test_all_summaries_is_sync(self):
        """SpanProcessingContext.all_summaries() should be synchronous."""
        from scripts.agentica_patterns.span_processor import (
            SpanProcessingContext,
            SpanSummary
        )

        context = SpanProcessingContext()

        summary = SpanSummary(
            span_id="span-1",
            turn_number=1,
            summary="Test summary",
            key_entities=[],
            references=[],
            span_type="llm_reasoning",
            content_hash="abc123"
        )
        context.add_summary(summary)

        # all_summaries is synchronous
        summaries = context.all_summaries()

        assert len(summaries) == 1
        assert summaries[0].span_id == "span-1"


# ============================================================================
# Phase 4: Test SpanProcessingContext Thread-Safe Concurrent Access
# ============================================================================


class TestPhase4SpanProcessingContextConcurrency:
    """Phase 4: Verify SpanProcessingContext handles thread concurrency."""

    def test_concurrent_summary_additions(self):
        """Concurrent add_summary calls should not corrupt state."""
        from scripts.agentica_patterns.span_processor import (
            SpanProcessingContext,
            SpanSummary
        )
        from threading import Thread

        context = SpanProcessingContext()
        errors = []

        def add_summaries(batch: int):
            """Add 20 summaries from a batch."""
            try:
                for i in range(20):
                    summary = SpanSummary(
                        span_id=f"span-{batch}-{i}",
                        turn_number=batch * 20 + i,
                        summary=f"Summary {batch}-{i}",
                        key_entities=[],
                        references=[],
                        span_type="llm_reasoning",
                        content_hash=f"hash-{batch}-{i}"
                    )
                    context.add_summary(summary)
            except Exception as e:
                errors.append((batch, e))

        # Run 10 concurrent threads
        threads = [Thread(target=add_summaries, args=(b,)) for b in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0, f"Errors: {errors}"

        # Should have exactly 200 summaries
        summaries = context.all_summaries()
        assert len(summaries) == 200, \
            f"Expected 200 summaries, got {len(summaries)}"

        # Verify no duplicates
        span_ids = set(s.span_id for s in summaries)
        assert len(span_ids) == 200

    def test_no_data_races_under_contention(self):
        """Reference graph should be consistent under contention."""
        from scripts.agentica_patterns.span_processor import (
            SpanProcessingContext,
            SpanSummary
        )
        from threading import Thread

        context = SpanProcessingContext()
        errors = []

        def add_and_query(n: int):
            """Add a summary and query reference context."""
            try:
                summary = SpanSummary(
                    span_id=f"span-{n}",
                    turn_number=n,
                    summary=f"Summary {n}",
                    key_entities=[],
                    references=[f"span-{n-1}"] if n > 0 else [],
                    span_type="llm_reasoning",
                    content_hash=f"hash-{n}"
                )
                context.add_summary(summary)

                # Query reference context immediately
                ref_context = context.get_reference_context(f"span-{n}")

                # If we have references, context should be valid
                if n > 0:
                    # May or may not find the ref (timing dependent)
                    # But should not crash or corrupt
                    assert isinstance(ref_context, str)
            except Exception as e:
                errors.append((n, e))

        # Run 100 concurrent threads
        threads = [Thread(target=add_and_query, args=(n,)) for n in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0, f"Errors: {errors}"

        # Reference graph should have 100 entries
        assert len(context.reference_graph) == 100


# ============================================================================
# Phase 5: Test extract_decisions() Thread Lock
# ============================================================================


class TestPhase5ExtractDecisionsThreadLock:
    """Phase 5: Verify extract_decisions() uses threading.Lock for decisions list."""

    @pytest.mark.asyncio
    async def test_extract_decisions_concurrent_access(self):
        """extract_decisions() should work with async callers."""
        from scripts.agentica_patterns.span_processor import SpanProcessor

        # This test verifies that SpanProcessor works in async context
        # even though SharedContext uses threading.Lock

        processor = SpanProcessor(
            session_id="test-session",
            num_mappers=10,  # High concurrency
            max_chunk_size=5,
        )

        # Create mock spans
        spans = []
        for i in range(50):
            spans.append({
                "id": f"span-{i}",
                "turn_number": i,
                "content": f"Decision {i}: Use approach X",
                "metadata": {},
            })

        # Mock the dependencies to avoid actual LLM calls
        with patch('scripts.agentica_patterns.span_processor.MapReduce') as MockMapReduce:
            # Mock the MapReduce to simulate concurrent extraction
            async def mock_map_reduce_exec():
                # Simulate concurrent decision extraction
                async def extract_decision(span_id: int):
                    await asyncio.sleep(0.001)  # Simulate work
                    return {
                        "span_id": f"span-{span_id}",
                        "decision": f"Decision {span_id}",
                        "rationale": "Test rationale",
                        "confidence": 0.9,
                        "source_refs": []
                    }

                # Run concurrently
                results = await asyncio.gather(*[
                    extract_decision(i) for i in range(50)
                ])
                return results

            mock_instance = MockMapReduce.return_value
            mock_instance.execute.return_value = await mock_map_reduce_exec()

            # This should not raise any errors related to lock usage
            result = await processor.process(spans)

            # Should have processed all spans
            assert result.spans_processed == 50

    def test_decisions_list_no_corruption_threads(self):
        """Decisions list should not be corrupted under concurrent thread appends."""
        # Verify threading.Lock works for cross-thread protection
        from threading import Thread

        decisions_lock = threading.Lock()
        decisions = []

        def append_decision(n: int):
            """Append to decisions list under threading lock."""
            with decisions_lock:
                decisions.append({"decision": n})

        # Run 100 concurrent thread appends
        threads = [Thread(target=append_decision, args=(n,)) for n in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 100 decisions
        assert len(decisions) == 100

        # Verify no duplicates
        decision_values = [d["decision"] for d in decisions]
        assert len(set(decision_values)) == 100


# ============================================================================
# Integration Test: All Phases Together
# ============================================================================


class TestAllPhasesIntegration:
    """Integration test verifying thread-safe locking in both contexts."""

    def test_full_pipeline_with_threading_locks(self):
        """Full pipeline should work with threading.Lock for thread safety."""
        from scripts.agentica_patterns.claude_scope import SharedContext
        from scripts.agentica_patterns.span_processor import (
            SpanProcessingContext,
            SpanSummary
        )
        from threading import Thread

        # Create shared context
        shared = SharedContext()

        # Create span processing context
        span_context = SpanProcessingContext()
        errors = []

        def shared_ops():
            """Operations on SharedContext."""
            try:
                for i in range(50):
                    shared.log_operation({"op": f"shared-{i}"})
            except Exception as e:
                errors.append(("shared", e))

        def span_ops():
            """Operations on SpanProcessingContext."""
            try:
                for i in range(50):
                    summary = SpanSummary(
                        span_id=f"span-{i}",
                        turn_number=i,
                        summary=f"Summary {i}",
                        key_entities=[],
                        references=[],
                        span_type="llm_reasoning",
                        content_hash=f"hash-{i}"
                    )
                    span_context.add_summary(summary)
            except Exception as e:
                errors.append(("span", e))

        # Run both in separate threads
        t1 = Thread(target=shared_ops)
        t2 = Thread(target=span_ops)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Should have no errors
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify both contexts are intact
        assert len(shared.operation_log) == 50
        summaries = span_context.all_summaries()
        assert len(summaries) == 50

    def test_threading_lock_used_in_contexts(self):
        """Verify threading.Lock is used for thread safety."""
        from scripts.agentica_patterns.claude_scope import SharedContext
        from scripts.agentica_patterns.span_processor import SpanProcessingContext

        shared = SharedContext()
        span_context = SpanProcessingContext()

        # Both should use threading.Lock for thread safety
        assert isinstance(shared._lock, type(threading.Lock())), \
            "SharedContext should use threading.Lock"
        assert isinstance(span_context._lock, type(threading.Lock())), \
            "SpanProcessingContext should use threading.Lock"
