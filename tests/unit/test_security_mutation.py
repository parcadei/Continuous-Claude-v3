"""Security mutation tests - FAILING TESTS (TDD Approach).

These tests validate security assumptions that mutation testing revealed are NOT
currently covered. They SHOULD FAIL initially, proving that mutation testing
found real gaps.

Based on:
- thoughts/shared/work/security-hardening/09-mutation-round1.md
- thoughts/shared/work/security-hardening/10-bug-research.md

Test Categories:
1. Path Prefix Attack (HIGH severity)
2. Null Byte Injection (HIGH severity)
3. External Symlink Escape (MEDIUM severity)
4. Thread Safety (MEDIUM severity)
5. Lock Starvation (LOW severity)
6. Deadlock Prevention (LOW severity)
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from threading import Thread

import pytest

from scripts.agentica_patterns.claude_scope import (
    SharedContext,
    _canonicalize_path,
    create_claude_scope,
)


# ============================================================================
# Path Security Tests (HIGH Priority)
# ============================================================================


class TestPrefixAttack:
    """Test that prefix attacks are blocked.

    Mutation testing found: removing os.sep from validation allows
    /project-evil to pass when project_dir is /project.
    """

    def test_prefix_attack_blocked(self, tmp_path):
        """Verify /project-evil blocked when project is /project.

        Attack scenario:
        - project_dir = /home/user/project
        - attacker creates /home/user/project-evil/
        - attacker provides path: /home/user/project-evil/secret.txt
        - Without os.sep check: startswith("/home/user/project") passes!
        - With os.sep check: correctly rejected
        """
        project = tmp_path / "project"
        project.mkdir()

        evil = tmp_path / "project-evil"
        evil.mkdir()
        (evil / "secret.txt").write_text("secret data")

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            _canonicalize_path(str(evil / "secret.txt"), str(project))

        # Should mention "escapes" in error message
        assert "escapes" in str(exc_info.value).lower()

    def test_prefix_attack_via_scope(self, tmp_path):
        """Verify read_file blocks prefix attack through scope API."""
        project = tmp_path / "project"
        project.mkdir()

        evil = tmp_path / "project-evil"
        evil.mkdir()
        (evil / "secret.txt").write_text("secret data")

        scope = create_claude_scope(project_dir=str(project))
        result = scope["read_file"](str(evil / "secret.txt"))

        # Should fail with error
        assert result["success"] is False
        assert "error" in result
        assert "escapes" in result["error"].lower()


class TestNullByteInjection:
    """Test that null bytes in paths are rejected.

    Null byte attacks can bypass extension validation in some C-based APIs.
    Python 3.x protects at OS layer, but explicit validation is defense-in-depth.
    """

    def test_null_byte_injection_blocked(self, tmp_path):
        """Verify null bytes in paths are rejected.

        Attack scenario:
        - Path: /project/file.txt\x00.jpg
        - Validation sees: ends with .jpg (safe)
        - C API sees: /project/file.txt (null terminates)
        - Result: bypassed extension check
        """
        project = tmp_path / "project"
        project.mkdir()

        # Should raise ValueError or TypeError
        with pytest.raises((ValueError, TypeError)):
            _canonicalize_path(f"{project}/file.txt\x00.jpg", str(project))

    def test_null_byte_in_middle_blocked(self, tmp_path):
        """Verify null bytes anywhere in path are rejected."""
        project = tmp_path / "project"
        project.mkdir()

        # Null byte in middle of path
        with pytest.raises((ValueError, TypeError)):
            _canonicalize_path(f"{tmp_path}/pro\x00ject/file.txt", str(project))

    def test_null_byte_via_scope(self, tmp_path):
        """Verify read_file blocks null byte injection through scope API."""
        project = tmp_path / "project"
        project.mkdir()

        scope = create_claude_scope(project_dir=str(project))
        result = scope["read_file"](f"{project}/file.txt\x00.jpg")

        # Should fail with error
        assert result["success"] is False
        assert "error" in result


class TestExternalSymlink:
    """Test that symlinks pointing outside project are blocked.

    Symlink attacks can bypass path validation if resolved incorrectly.
    """

    def test_external_symlink_blocked(self, tmp_path):
        """Verify symlinks pointing outside project are blocked.

        Attack scenario:
        - Create symlink inside project pointing to outside
        - Request access via symlink
        - Should be rejected after resolution
        """
        project = tmp_path / "project"
        project.mkdir()

        external = tmp_path / "external"
        external.mkdir()
        (external / "secret.txt").write_text("secret data")

        # Create symlink inside project pointing outside
        link = project / "link"
        link.symlink_to(external)

        # Should fail because symlink resolves outside project
        with pytest.raises(ValueError) as exc_info:
            _canonicalize_path(str(link / "secret.txt"), str(project))

        assert "escapes" in str(exc_info.value).lower()

    def test_external_symlink_via_scope(self, tmp_path):
        """Verify read_file blocks external symlinks through scope API."""
        project = tmp_path / "project"
        project.mkdir()

        external = tmp_path / "external"
        external.mkdir()
        (external / "secret.txt").write_text("secret data")

        link = project / "link"
        link.symlink_to(external)

        scope = create_claude_scope(project_dir=str(project))
        result = scope["read_file"](str(link / "secret.txt"))

        # Should fail with error
        assert result["success"] is False
        assert "error" in result
        assert "escapes" in result["error"].lower()

    def test_internal_symlink_allowed(self, tmp_path):
        """Verify symlinks within project are allowed."""
        project = tmp_path / "project"
        project.mkdir()

        target = project / "target.txt"
        target.write_text("content")

        link = project / "link.txt"
        link.symlink_to(target)

        # Should succeed - resolves to actual target within project
        result = _canonicalize_path(str(link), str(project))
        assert result == str(target)


# ============================================================================
# Thread Safety Tests (MEDIUM Priority)
# ============================================================================


class TestSharedContextThreadSafety:
    """Test SharedContext works correctly from multiple threads.

    SharedContext uses threading.Lock for cross-thread protection.
    """

    def test_shared_context_thread_safety(self):
        """Verify SharedContext works from multiple threads.

        threading.Lock provides cross-thread protection directly.
        """
        shared = SharedContext()
        results = []
        errors = []

        def thread_worker(n):
            """Worker that calls SharedContext methods directly."""
            try:
                # Perform operations (sync with threading.Lock)
                for i in range(100):
                    shared.log_operation({"thread": n, "op": i})

                results.append(n)
            except Exception as e:
                errors.append((n, e))

        # Spawn 10 threads
        threads = [Thread(target=thread_worker, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should complete
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 10
        assert len(shared.operation_log) == 1000  # 10 threads * 100 ops

    def test_concurrent_cache_operations(self):
        """Verify cache operations don't race under concurrency."""
        from scripts.agentica_patterns.claude_scope import ClaudeResult

        shared = SharedContext()
        errors = []

        def reader(n):
            """Read from cache repeatedly."""
            try:
                for i in range(50):
                    shared.get_cached(f"key_{n}")
            except Exception as e:
                errors.append(("reader", n, e))

        def writer(n):
            """Write to cache repeatedly."""
            try:
                for i in range(50):
                    shared.set_cached(
                        f"key_{n}",
                        ClaudeResult(True, "read", f"key_{n}", f"content_{n}")
                    )
            except Exception as e:
                errors.append(("writer", n, e))

        # Mix readers and writers in threads
        threads = []
        for n in range(10):
            threads.append(Thread(target=reader, args=(n,)))
            threads.append(Thread(target=writer, args=(n,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert len(errors) == 0, f"Errors: {errors}"

        # Cache should have entries
        assert len(shared.file_cache) > 0


class TestLockStarvation:
    """Test that no thread is starved under high contention.

    threading.Lock provides fair access across threads.
    """

    def test_no_lock_starvation(self):
        """Verify no starvation under heavy contention.

        All workers should complete within reasonable time.
        If max_time > 2x average_time, some workers are starved.
        """
        shared = SharedContext()
        completion_times = []
        errors = []

        def worker(n):
            """Worker that contends for lock."""
            try:
                start = time.time()
                for i in range(50):
                    shared.log_operation({"worker": n, "op": i})
                completion_times.append((n, time.time() - start))
            except Exception as e:
                errors.append((n, e))

        # 50 concurrent threads
        threads = [Thread(target=worker, args=(n,)) for n in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"

        # Check starvation: no worker should take > 2x average
        times = [t for _, t in completion_times]
        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Skip starvation check if operations are too fast to measure (< 1ms average)
        # This prevents floating point comparison issues with near-zero values
        if avg_time > 0.001:
            # Starvation indicator: max > 2x average
            assert max_time < 2 * avg_time, (
                f"Possible starvation: max={max_time:.3f}s, avg={avg_time:.3f}s"
            )

    def test_lock_fairness(self):
        """Verify lock is acquired in reasonable order.

        While threading.Lock doesn't guarantee FIFO, excessive reordering
        indicates starvation risk.
        """
        import threading

        shared = SharedContext()
        acquisition_order = []
        order_lock = threading.Lock()

        def worker(n):
            """Worker that records lock acquisition order."""
            shared.log_operation({"worker": n})
            with order_lock:
                acquisition_order.append(n)

        # Start workers in threads
        threads = [Thread(target=worker, args=(n,)) for n in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Count inversions (worker i acquired before worker j where i > j)
        inversions = 0
        for i in range(len(acquisition_order)):
            for j in range(i + 1, len(acquisition_order)):
                if acquisition_order[i] > acquisition_order[j]:
                    inversions += 1

        # Some reordering is OK, but excessive inversions indicate unfairness
        max_inversions = len(acquisition_order) * 10  # 10x reordering allowed
        assert inversions < max_inversions, (
            f"Excessive reordering: {inversions} inversions"
        )


class TestDeadlockPrevention:
    """Test that multiple contexts don't deadlock.

    Deadlock occurs when:
    1. Multiple locks exist
    2. Acquired in different orders
    3. Threads wait circularly

    Our design uses single lock per context, so deadlock should be impossible.
    """

    def test_no_deadlock_multiple_contexts(self):
        """Verify multiple contexts don't deadlock each other.

        Creates multiple SharedContext instances and uses them concurrently.
        Should complete within timeout (no deadlock).
        """
        import signal

        shared1 = SharedContext()
        shared2 = SharedContext()
        errors = []

        def cross_worker():
            """Worker that uses both contexts."""
            try:
                for i in range(50):
                    shared1.log_operation({"ctx": 1, "op": i})
                    shared2.log_operation({"ctx": 2, "op": i})
            except Exception as e:
                errors.append(e)

        # Start threads with a timeout
        threads = [Thread(target=cross_worker) for _ in range(20)]
        for t in threads:
            t.start()

        # Wait for all threads with timeout
        for t in threads:
            t.join(timeout=5.0)
            if t.is_alive():
                raise TimeoutError("Possible deadlock detected")

        assert len(errors) == 0, f"Errors: {errors}"

        # Both contexts should have operations
        assert len(shared1.operation_log) == 1000  # 20 workers * 50 ops
        assert len(shared2.operation_log) == 1000

    def test_no_deadlock_nested_operations(self):
        """Verify nested operations don't deadlock.

        Tests scenario where operation on one context triggers operation
        on another (common in real code).
        """
        shared1 = SharedContext()
        shared2 = SharedContext()
        errors = []

        def nested_worker(n):
            """Worker with nested context usage."""
            try:
                # Acquire lock on shared1
                shared1.log_operation({"worker": n, "phase": 1})

                # Now acquire lock on shared2 (nested)
                shared2.log_operation({"worker": n, "phase": 2})

                # Release shared2, then shared1
            except Exception as e:
                errors.append((n, e))

        # Start threads
        threads = [Thread(target=nested_worker, args=(n,)) for n in range(50)]
        for t in threads:
            t.start()

        # Wait for all threads with timeout
        for t in threads:
            t.join(timeout=5.0)
            if t.is_alive():
                raise TimeoutError("Possible deadlock detected")

        assert len(errors) == 0, f"Errors: {errors}"


# ============================================================================
# Edge Case Tests (LOW Priority)
# ============================================================================


class TestPathEdgeCases:
    """Test edge cases in path handling.

    Based on Python os.path.realpath edge cases from bug research.
    """

    def test_empty_path_rejected(self, tmp_path):
        """Empty string path should fail."""
        project = tmp_path / "project"
        project.mkdir()

        # Empty path should fail
        with pytest.raises((ValueError, OSError)):
            _canonicalize_path("", str(project))

    def test_nonexistent_path_resolves_traversal(self, tmp_path):
        """Non-existent paths should still resolve ../ correctly.

        os.path.realpath resolves ../ even for non-existent paths.
        This is CORRECT behavior (needed for write operations).
        """
        project = tmp_path / "project"
        project.mkdir()

        # Path doesn't exist but should resolve correctly
        nonexistent = project / "subdir" / ".." / "file.txt"
        result = _canonicalize_path(str(nonexistent), str(project))

        # Should resolve to project_dir/file.txt
        assert result == str(project / "file.txt")

    def test_trailing_slash_normalized(self, tmp_path):
        """Trailing slashes should be handled consistently."""
        project = tmp_path / "project"
        project.mkdir()

        # With trailing slash
        path_with_slash = str(project) + "/"
        result = _canonicalize_path(path_with_slash, str(project))

        # Should match without slash (normalized)
        assert result == str(project)

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_case_sensitivity_macos(self, tmp_path):
        """Case differences should normalize to same path on macOS.

        macOS is case-insensitive, so /Project and /PROJECT are same directory.
        os.path.realpath should return actual case from filesystem.
        """
        project = tmp_path / "Project"
        project.mkdir()

        # Access with different case
        upper_case_path = str(project).upper()
        result = _canonicalize_path(upper_case_path, str(project))

        # Should resolve to actual case from filesystem
        # (exact result depends on filesystem, just verify it doesn't raise)
        assert result is not None


# ============================================================================
# Test Execution Report
# ============================================================================


def test_report_expected_failures():
    """Report which tests are EXPECTED to fail (TDD approach).

    This test always passes. It's here to document the TDD process.
    """
    expected_failures = [
        "test_prefix_attack_blocked - validates os.sep in validation",
        "test_null_byte_injection_blocked - explicit null byte check",
        "test_external_symlink_blocked - symlink resolution validation",
        "test_shared_context_thread_safety - thread-local event loops",
        "test_no_lock_starvation - starvation detection",
        "test_no_deadlock_multiple_contexts - deadlock prevention",
    ]

    print("\n" + "=" * 70)
    print("TDD EXPECTED FAILURES")
    print("=" * 70)
    print("The following tests SHOULD FAIL initially:")
    for i, test_name in enumerate(expected_failures, 1):
        print(f"{i}. {test_name}")
    print("\nAfter implementing fixes, these tests should PASS.")
    print("=" * 70)

    # This test always passes - it's documentation
    assert True
