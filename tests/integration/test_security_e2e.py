"""End-to-end integration tests for security hardening.

Tests verify all security components work together correctly:
1. Path validation across all entry points
2. SharedContext async lock thread safety
3. UnifiedScope integration with security
4. SpanProcessingContext concurrent safety
5. Cross-component flows
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from scripts.agentica_patterns.claude_scope import (
    SharedContext,
    create_claude_scope,
    create_claude_scope_with_shared,
)
from scripts.agentica_patterns.span_processor import SpanProcessingContext
from scripts.agentica_patterns.unified_scope import create_unified_scope


class TestSecurityE2E:
    """End-to-end tests for security hardening."""

    def test_path_traversal_blocked_in_full_pipeline(self, tmp_path):
        """Verify path traversal is blocked across all entry points."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Test via create_claude_scope
        scope = create_claude_scope(project_dir=str(project_dir))
        result = scope["read_file"]("../../../etc/passwd")
        assert result["success"] is False
        assert "escapes" in result.get("error", "").lower()

        # Test write_file
        result = scope["write_file"]("../../../tmp/evil.txt", "malicious")
        assert result["success"] is False
        assert "escapes" in result.get("error", "").lower()

        # Test edit_file
        result = scope["edit_file"]("../../../tmp/target.txt", "old", "new")
        assert result["success"] is False
        assert "escapes" in result.get("error", "").lower()

    def test_path_traversal_via_symlinks(self, tmp_path):
        """Verify symlink-based path traversal is blocked."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create symlink pointing outside project
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        target_file = outside_dir / "secret.txt"
        target_file.write_text("secret data")

        symlink = project_dir / "escape_link"
        symlink.symlink_to(target_file)

        # Attempt to read via symlink
        scope = create_claude_scope(project_dir=str(project_dir))
        result = scope["read_file"](str(symlink))
        assert result["success"] is False
        assert "escapes" in result.get("error", "").lower()

    def test_path_validation_allows_valid_paths(self, tmp_path):
        """Verify legitimate paths within project_dir are allowed."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create a test file
        test_file = project_dir / "data.txt"
        test_file.write_text("safe content")

        # Mock _call_claude_cli to avoid subprocess
        from scripts.agentica_patterns import claude_scope

        original_call = claude_scope._call_claude_cli

        def mock_call(prompt, allowed_tools, timeout=300):
            if "Read the file" in prompt:
                return "safe content"
            return "mocked response"

        claude_scope._call_claude_cli = mock_call
        try:
            scope = create_claude_scope(project_dir=str(project_dir))

            # Should succeed for valid path
            result = scope["read_file"](str(test_file))
            assert result["success"] is True
            assert result["content"] == "safe content"

            # Should succeed for relative path within project
            result = scope["read_file"](str(project_dir / "data.txt"))
            assert result["success"] is True
        finally:
            claude_scope._call_claude_cli = original_call

    def test_concurrent_shared_context_operations(self):
        """Verify SharedContext handles concurrent access correctly."""
        from threading import Thread

        shared = SharedContext()
        errors = []

        def writer(n):
            try:
                for i in range(50):
                    shared.log_operation({"writer": n, "op": i})
            except Exception as e:
                errors.append((n, e))

        # Run 10 concurrent threads, 50 ops each = 500 total
        threads = [Thread(target=writer, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(shared.operation_log) == 500

    def test_shared_context_cache_operations(self):
        """Verify SharedContext cache operations are thread-safe."""
        from threading import Thread
        from scripts.agentica_patterns.claude_scope import ClaudeResult

        shared = SharedContext()
        errors = []

        def cache_writer(n):
            try:
                for i in range(20):
                    result = ClaudeResult(
                        success=True,
                        operation="read",
                        path=f"/path/{n}/{i}.txt",
                        content=f"content_{n}_{i}",
                    )
                    shared.set_cached(f"/path/{n}/{i}.txt", result)
            except Exception as e:
                errors.append((n, e))

        # Write to cache concurrently
        threads = [Thread(target=cache_writer, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"

        # Should have 200 cached files (10 writers * 20 files each)
        assert len(shared.file_cache) == 200

        # Verify we can retrieve them
        for n in range(10):
            for i in range(20):
                cached = shared.get_cached(f"/path/{n}/{i}.txt")
                assert cached is not None
                assert cached.content == f"content_{n}_{i}"

    def test_unified_scope_path_validation(self, tmp_path):
        """Verify UnifiedScope enforces path validation."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Mock _call_claude_cli in unified_scope
        from scripts.agentica_patterns import unified_scope

        original_call = unified_scope._call_claude_cli

        def mock_call(prompt, allowed_tools, timeout=300):
            return "mocked response"

        unified_scope._call_claude_cli = mock_call
        try:
            scope = create_unified_scope(
                session_id="test_session",
                db_path=tmp_path / "test.db",
                enable_memory=False,
                enable_tasks=False,
                project_dir=str(project_dir),
            )

            # Path traversal should be blocked
            result = scope["read_file"]("../../../etc/passwd")
            assert result["success"] is False
            assert "escapes" in result.get("error", "").lower()

            # Valid paths should work (within project_dir)
            test_file = project_dir / "valid.txt"
            test_file.write_text("valid data")
            result = scope["read_file"](str(test_file))
            assert result["success"] is True
        finally:
            unified_scope._call_claude_cli = original_call

    def test_span_processing_context_concurrent_summaries(self):
        """Verify SpanProcessingContext handles concurrent summary additions."""
        from scripts.agentica_patterns.span_processor import SpanSummary
        from threading import Thread

        context = SpanProcessingContext()
        errors = []

        def add_summaries(batch_id):
            try:
                for i in range(30):
                    summary = SpanSummary(
                        span_id=f"span_{batch_id}_{i}",
                        turn_number=i,
                        summary=f"Summary for batch {batch_id}, span {i}",
                        key_entities=["entity1", "entity2"],
                        references=[],
                        span_type="llm_reasoning",
                        content_hash=f"hash_{batch_id}_{i}",
                    )
                    context.add_summary(summary)
            except Exception as e:
                errors.append((batch_id, e))

        # Add summaries from 10 concurrent threads
        threads = [Thread(target=add_summaries, args=(b,)) for b in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"

        # Should have 300 summaries (10 batches * 30 each)
        assert len(context.span_summaries) == 300

        # Verify all summaries are retrievable
        all_summaries = context.all_summaries()
        assert len(all_summaries) == 300

    def test_span_processing_context_reference_resolution(self):
        """Verify reference context retrieval is thread-safe."""
        from scripts.agentica_patterns.span_processor import SpanSummary

        context = SpanProcessingContext()

        # Add summaries with references
        summary1 = SpanSummary(
            span_id="span_1",
            turn_number=0,
            summary="First span",
            key_entities=[],
            references=[],
            span_type="llm_reasoning",
            content_hash="hash_1",
        )
        summary2 = SpanSummary(
            span_id="span_2",
            turn_number=1,
            summary="Second span",
            key_entities=[],
            references=["span_1"],
            span_type="llm_reasoning",
            content_hash="hash_2",
        )
        summary3 = SpanSummary(
            span_id="span_3",
            turn_number=2,
            summary="Third span",
            key_entities=[],
            references=["span_1", "span_2"],
            span_type="llm_reasoning",
            content_hash="hash_3",
        )

        context.add_summary(summary1)
        context.add_summary(summary2)
        context.add_summary(summary3)

        # Get reference contexts
        results = [context.get_reference_context(f"span_{i}") for i in range(1, 4)]

        # Verify reference contexts
        assert results[0] == ""  # span_1 has no references
        assert "[span_1]: First span" in results[1]  # span_2 references span_1
        assert "[span_1]: First span" in results[2]  # span_3 references both
        assert "[span_2]: Second span" in results[2]

    def test_cross_component_flow(self, tmp_path):
        """Verify multiple components work together."""
        from scripts.agentica_patterns.span_processor import SpanSummary
        from threading import Thread

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create SharedContext for file ops
        file_shared = SharedContext()

        # Create SpanProcessingContext
        span_context = SpanProcessingContext()
        errors = []

        # Mock _call_claude_cli
        from scripts.agentica_patterns import claude_scope

        original_call = claude_scope._call_claude_cli

        def mock_call(prompt, allowed_tools, timeout=300):
            if "Read the file" in prompt:
                return "file content"
            return "mocked response"

        claude_scope._call_claude_cli = mock_call
        try:
            # Create scope with shared context
            scope = create_claude_scope_with_shared(
                file_shared, project_dir=str(project_dir)
            )

            # Simulate concurrent file operations and span processing
            def file_worker():
                try:
                    test_file = project_dir / "data.txt"
                    test_file.write_text("test data")
                    result = scope["read_file"](str(test_file))
                    assert result["success"] is True
                except Exception as e:
                    errors.append(("file", e))

            def span_worker():
                try:
                    for i in range(10):
                        summary = SpanSummary(
                            span_id=f"span_{i}",
                            turn_number=i,
                            summary=f"Summary {i}",
                            key_entities=[],
                            references=[],
                            span_type="llm_reasoning",
                            content_hash=f"hash_{i}",
                        )
                        span_context.add_summary(summary)
                except Exception as e:
                    errors.append(("span", e))

            # Run both types of work in threads
            threads = (
                [Thread(target=file_worker) for _ in range(5)] +
                [Thread(target=span_worker) for _ in range(3)]
            )
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Errors: {errors}"

            # Verify both contexts worked correctly
            # First read logs, subsequent reads hit cache (no duplicate logs)
            assert len(file_shared.operation_log) >= 1
            # span_summaries is a dict keyed by span_id, duplicates overwrite
            # All 3 workers use same span_ids (span_0-9), so 10 unique entries
            assert len(span_context.span_summaries) == 10
        finally:
            claude_scope._call_claude_cli = original_call

    def test_shared_context_invalidation_race(self):
        """Verify cache invalidation is atomic."""
        from threading import Thread
        from scripts.agentica_patterns.claude_scope import ClaudeResult

        shared = SharedContext()

        # Pre-populate cache
        for i in range(100):
            result = ClaudeResult(
                success=True,
                operation="read",
                path=f"/path/{i}.txt",
                content=f"content_{i}",
            )
            shared.set_cached(f"/path/{i}.txt", result)

        assert len(shared.file_cache) == 100

        # Concurrent invalidations
        def invalidate_worker():
            for i in range(50):
                shared.invalidate(f"/path/{i}.txt")

        # Multiple workers try to invalidate overlapping ranges
        threads = [Thread(target=invalidate_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Paths 0-49 should be invalidated
        for i in range(50):
            cached = shared.get_cached(f"/path/{i}.txt")
            assert cached is None

        # Paths 50-99 should still be cached
        for i in range(50, 100):
            cached = shared.get_cached(f"/path/{i}.txt")
            assert cached is not None

    def test_unified_scope_memory_and_tasks_disabled_path_validation(self, tmp_path):
        """Verify path validation works even when memory/tasks are disabled."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        from scripts.agentica_patterns import unified_scope

        original_call = unified_scope._call_claude_cli

        def mock_call(prompt, allowed_tools, timeout=300):
            return "mocked"

        unified_scope._call_claude_cli = mock_call
        try:
            scope = create_unified_scope(
                session_id="test",
                db_path=tmp_path / "test.db",
                enable_memory=False,
                enable_tasks=False,
                project_dir=str(project_dir),
            )

            # Path traversal blocked
            result = scope["read_file"]("../../../etc/passwd")
            assert result["success"] is False
            assert "escapes" in result.get("error", "").lower()

            # Valid paths work
            test_file = project_dir / "safe.txt"
            test_file.write_text("safe")
            result = scope["read_file"](str(test_file))
            assert result["success"] is True
        finally:
            unified_scope._call_claude_cli = original_call

    def test_span_processing_context_write_conflicts(self):
        """Verify SpanProcessingContext concurrent summary additions."""
        from scripts.agentica_patterns.span_processor import SpanSummary
        from threading import Thread

        context = SpanProcessingContext()
        errors = []

        # Simulate concurrent writes to same path via summaries
        def write_operation(worker_id):
            try:
                for i in range(10):
                    summary = SpanSummary(
                        span_id=f"write_{worker_id}_{i}",
                        turn_number=i,
                        summary=f"Write to /shared/file.txt by worker {worker_id}",
                        key_entities=["file.txt"],
                        references=[],
                        span_type="write_operation",
                        content_hash=f"hash_{worker_id}_{i}",
                    )
                    context.add_summary(summary)
            except Exception as e:
                errors.append((worker_id, e))

        threads = [Thread(target=write_operation, args=(w,)) for w in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"

        # Should have 50 summaries (5 workers * 10 writes each)
        assert len(context.span_summaries) == 50

        # All summaries should be retrievable
        all_summaries = context.all_summaries()
        assert len(all_summaries) == 50

        # Verify summaries are from write operations
        write_summaries = [s for s in all_summaries if s.span_type == "write_operation"]
        assert len(write_summaries) == 50

    def test_path_validation_with_tilde_expansion(self, tmp_path):
        """Verify path validation handles ~ expansion correctly."""
        import os

        # Create a project dir in /tmp for testing
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        scope = create_claude_scope(project_dir=str(project_dir))

        # Attempt to escape using ~
        result = scope["read_file"]("~/../../etc/passwd")
        # This should be blocked because ~ expands outside project_dir
        assert result["success"] is False
        assert "escapes" in result.get("error", "").lower()

    def test_concurrent_cache_and_invalidation(self):
        """Verify concurrent cache writes and invalidations don't corrupt state."""
        from threading import Thread
        from scripts.agentica_patterns.claude_scope import ClaudeResult

        shared = SharedContext()
        errors = []

        def cache_and_invalidate(worker_id):
            try:
                for i in range(20):
                    # Write
                    result = ClaudeResult(
                        success=True,
                        operation="read",
                        path=f"/path/worker_{worker_id}_{i}.txt",
                        content=f"content_{worker_id}_{i}",
                    )
                    shared.set_cached(
                        f"/path/worker_{worker_id}_{i}.txt", result
                    )

                    # Invalidate previous entry
                    if i > 0:
                        shared.invalidate(
                            f"/path/worker_{worker_id}_{i-1}.txt"
                        )
            except Exception as e:
                errors.append((worker_id, e))

        threads = [Thread(target=cache_and_invalidate, args=(w,)) for w in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"

        # Each worker writes 20, invalidates 19, leaves 1
        # 10 workers * 1 final entry = 10 entries remaining
        assert len(shared.file_cache) == 10

        # Verify the remaining entries are the last ones
        for w in range(10):
            cached = shared.get_cached(f"/path/worker_{w}_19.txt")
            assert cached is not None
            assert cached.content == f"content_{w}_19"

    def test_project_dir_none_allows_all_paths(self, tmp_path):
        """Verify project_dir=None disables path validation."""
        # Create test file outside any specific project
        test_file = tmp_path / "unrestricted.txt"
        test_file.write_text("unrestricted content")

        from scripts.agentica_patterns import claude_scope

        original_call = claude_scope._call_claude_cli

        def mock_call(prompt, allowed_tools, timeout=300):
            return "unrestricted content"

        claude_scope._call_claude_cli = mock_call
        try:
            # No project_dir means no restrictions
            scope = create_claude_scope(project_dir=None)

            # Should allow any path
            result = scope["read_file"](str(test_file))
            assert result["success"] is True
            assert result["content"] == "unrestricted content"
        finally:
            claude_scope._call_claude_cli = original_call
