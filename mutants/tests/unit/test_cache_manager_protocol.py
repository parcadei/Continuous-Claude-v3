"""Tests for CacheManager Protocol - TDD Phase 1 (Failing Tests).

This test file is part of Issue 2: Code Duplication refactor.
These tests should FAIL initially because CacheManager and LocalCacheManager
do not yet exist in unified_scope.py.

Test Coverage:
1. CacheManager Protocol existence
2. LocalCacheManager implements all required methods
3. SharedContext satisfies the Protocol (structural typing)
4. Unified _create_file_ops works with both cache managers
5. Cache behavior equivalence between old and new implementations

References:
- Plan: docs/agentica-integration-fixes/issue-2-code-duplication/plan.md
- Source: scripts/agentica/unified_scope.py
- SharedContext: scripts/agentica/claude_scope.py L139-208
"""

import pytest
from typing import Protocol, runtime_checkable
from pathlib import Path
from unittest.mock import patch, MagicMock


# ============================================================================
# Test 1: CacheManager Protocol Existence
# ============================================================================


class TestCacheManagerProtocolExists:
    """Test that CacheManager Protocol is defined."""

    def test_cachemanager_can_be_imported(self):
        """CacheManager should be importable from unified_scope."""
        from scripts.agentica.unified_scope import CacheManager

        # Should be a Protocol class
        assert hasattr(CacheManager, '__protocol_attrs__') or hasattr(CacheManager, '_is_protocol'), \
            "CacheManager should be a Protocol"

    def test_cachemanager_defines_get_cached(self):
        """CacheManager Protocol should define get_cached method."""
        from scripts.agentica.unified_scope import CacheManager

        # Check method exists in protocol
        assert hasattr(CacheManager, 'get_cached'), "CacheManager missing get_cached"

    def test_cachemanager_defines_set_cached(self):
        """CacheManager Protocol should define set_cached method."""
        from scripts.agentica.unified_scope import CacheManager

        assert hasattr(CacheManager, 'set_cached'), "CacheManager missing set_cached"

    def test_cachemanager_defines_invalidate(self):
        """CacheManager Protocol should define invalidate method."""
        from scripts.agentica.unified_scope import CacheManager

        assert hasattr(CacheManager, 'invalidate'), "CacheManager missing invalidate"

    def test_cachemanager_defines_log_operation(self):
        """CacheManager Protocol should define log_operation method."""
        from scripts.agentica.unified_scope import CacheManager

        assert hasattr(CacheManager, 'log_operation'), "CacheManager missing log_operation"

    def test_cachemanager_defines_get_all_cached(self):
        """CacheManager Protocol should define get_all_cached method."""
        from scripts.agentica.unified_scope import CacheManager

        assert hasattr(CacheManager, 'get_all_cached'), "CacheManager missing get_all_cached"

    def test_cachemanager_defines_get_all_operations(self):
        """CacheManager Protocol should define get_all_operations method."""
        from scripts.agentica.unified_scope import CacheManager

        assert hasattr(CacheManager, 'get_all_operations'), "CacheManager missing get_all_operations"

    def test_cachemanager_defines_clear_cache(self):
        """CacheManager Protocol should define clear_cache method."""
        from scripts.agentica.unified_scope import CacheManager

        assert hasattr(CacheManager, 'clear_cache'), "CacheManager missing clear_cache"


# ============================================================================
# Test 2: LocalCacheManager Implementation
# ============================================================================


class TestLocalCacheManagerExists:
    """Test that LocalCacheManager class is defined and implements Protocol."""

    def test_localcachemanager_can_be_imported(self):
        """LocalCacheManager should be importable from unified_scope."""
        from scripts.agentica.unified_scope import LocalCacheManager

        # Should be instantiable
        manager = LocalCacheManager()
        assert manager is not None

    def test_localcachemanager_implements_all_methods(self):
        """LocalCacheManager should implement all CacheManager methods."""
        from scripts.agentica.unified_scope import LocalCacheManager

        manager = LocalCacheManager()

        # All required methods should be callable
        assert callable(getattr(manager, 'get_cached', None)), "Missing get_cached"
        assert callable(getattr(manager, 'set_cached', None)), "Missing set_cached"
        assert callable(getattr(manager, 'invalidate', None)), "Missing invalidate"
        assert callable(getattr(manager, 'log_operation', None)), "Missing log_operation"
        assert callable(getattr(manager, 'get_all_cached', None)), "Missing get_all_cached"
        assert callable(getattr(manager, 'get_all_operations', None)), "Missing get_all_operations"
        assert callable(getattr(manager, 'clear_cache', None)), "Missing clear_cache"


class TestLocalCacheManagerBehavior:
    """Test LocalCacheManager behavior matches expected caching semantics."""

    def test_cache_reads_disabled_returns_none(self):
        """When cache_reads=False, get_cached should always return None."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager(cache_reads=False)
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")

        manager.set_cached("/test", result)
        assert manager.get_cached("/test") is None, "Cache should return None when disabled"

    def test_cache_reads_enabled_by_default(self):
        """cache_reads should default to True."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()  # default cache_reads=True
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")

        manager.set_cached("/test", result)
        cached = manager.get_cached("/test")

        assert cached is not None, "Cache should work by default"
        assert cached.content == "data", "Cached content should match"

    def test_get_cached_returns_none_for_missing(self):
        """get_cached should return None for paths not in cache."""
        from scripts.agentica.unified_scope import LocalCacheManager

        manager = LocalCacheManager()
        assert manager.get_cached("/nonexistent") is None

    def test_set_cached_stores_value(self):
        """set_cached should store value retrievable by get_cached."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        result = ClaudeResult(success=True, operation="read", path="/test", content="hello")

        manager.set_cached("/test", result)
        cached = manager.get_cached("/test")

        assert cached is not None
        assert cached.path == "/test"
        assert cached.content == "hello"

    def test_invalidate_removes_entry(self):
        """invalidate should remove cached entry."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")

        manager.set_cached("/test", result)
        manager.invalidate("/test")

        assert manager.get_cached("/test") is None, "Entry should be removed"

    def test_invalidate_nonexistent_is_safe(self):
        """invalidate on non-existent path should not raise."""
        from scripts.agentica.unified_scope import LocalCacheManager

        manager = LocalCacheManager()
        # Should not raise KeyError or any exception
        manager.invalidate("/nonexistent")

    def test_log_operation_accumulates(self):
        """log_operation should accumulate operations in order."""
        from scripts.agentica.unified_scope import LocalCacheManager

        manager = LocalCacheManager()

        manager.log_operation({"op": "read", "path": "/a"})
        manager.log_operation({"op": "write", "path": "/b"})
        manager.log_operation({"op": "edit", "path": "/c"})

        ops = manager.get_all_operations()

        assert len(ops) == 3
        assert ops[0]["path"] == "/a"
        assert ops[1]["path"] == "/b"
        assert ops[2]["path"] == "/c"

    def test_get_all_cached_returns_copy(self):
        """get_all_cached should return a copy, not the internal dict."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")
        manager.set_cached("/test", result)

        copy = manager.get_all_cached()
        copy["/modified"] = result  # Modify the copy

        # Original should be unchanged
        assert "/modified" not in manager.get_all_cached()

    def test_get_all_operations_returns_copy(self):
        """get_all_operations should return a copy, not the internal list."""
        from scripts.agentica.unified_scope import LocalCacheManager

        manager = LocalCacheManager()
        manager.log_operation({"op": "read"})

        copy = manager.get_all_operations()
        copy.append({"op": "fake"})  # Modify the copy

        # Original should be unchanged
        assert len(manager.get_all_operations()) == 1

    def test_clear_cache_removes_all_entries(self):
        """clear_cache should remove all cached entries."""
        from scripts.agentica.unified_scope import LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")

        manager.set_cached("/a", result)
        manager.set_cached("/b", result)
        manager.set_cached("/c", result)

        manager.clear_cache()

        assert manager.get_all_cached() == {}
        assert manager.get_cached("/a") is None
        assert manager.get_cached("/b") is None


# ============================================================================
# Test 3: SharedContext Satisfies Protocol (Structural Typing)
# ============================================================================


class TestSharedContextSatisfiesProtocol:
    """Test that SharedContext implements CacheManager protocol via duck typing."""

    def test_shared_context_has_get_cached(self):
        """SharedContext should have get_cached method."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()
        assert callable(getattr(shared, 'get_cached', None))

    def test_shared_context_has_set_cached(self):
        """SharedContext should have set_cached method."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()
        assert callable(getattr(shared, 'set_cached', None))

    def test_shared_context_has_invalidate(self):
        """SharedContext should have invalidate method."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()
        assert callable(getattr(shared, 'invalidate', None))

    def test_shared_context_has_log_operation(self):
        """SharedContext should have log_operation method."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()
        assert callable(getattr(shared, 'log_operation', None))

    def test_shared_context_has_get_all_cached(self):
        """SharedContext should have get_all_cached method."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()
        assert callable(getattr(shared, 'get_all_cached', None))

    def test_shared_context_has_get_all_operations(self):
        """SharedContext should have get_all_operations method."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()
        assert callable(getattr(shared, 'get_all_operations', None))

    def test_shared_context_has_clear_cache(self):
        """SharedContext should have clear_cache method."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()
        assert callable(getattr(shared, 'clear_cache', None))


# ============================================================================
# Test 4: Unified _create_file_ops Factory
# ============================================================================


class TestUnifiedCreateFileOps:
    """Test that unified _create_file_ops works with any CacheManager."""

    def test_create_file_ops_exists(self):
        """_create_file_ops should be importable from unified_scope."""
        from scripts.agentica.unified_scope import _create_file_ops

        assert callable(_create_file_ops)

    def test_create_file_ops_with_local_cache_manager(self):
        """_create_file_ops should work with LocalCacheManager."""
        from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager

        manager = LocalCacheManager()
        ops = _create_file_ops(manager)

        # Should return dict with all file operations
        assert isinstance(ops, dict)
        assert "read_file" in ops
        assert "write_file" in ops
        assert "edit_file" in ops
        assert "bash" in ops
        assert "grep" in ops
        assert "glob" in ops
        assert "debug_get_cache" in ops
        assert "debug_get_operation_log" in ops
        assert "debug_clear_cache" in ops

    def test_create_file_ops_with_shared_context(self):
        """_create_file_ops should work with SharedContext."""
        from scripts.agentica.unified_scope import _create_file_ops
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()
        ops = _create_file_ops(shared)

        # Should return dict with all file operations
        assert isinstance(ops, dict)
        assert "read_file" in ops
        assert "write_file" in ops

    def test_create_file_ops_returns_callable_functions(self):
        """All returned operations should be callable."""
        from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager

        ops = _create_file_ops(LocalCacheManager())

        for name, func in ops.items():
            assert callable(func), f"{name} should be callable"


# ============================================================================
# Test 5: Cache Behavior Equivalence
# ============================================================================


class TestCacheBehaviorEquivalence:
    """Test that new implementation matches old behavior."""

    @patch('scripts.agentica.unified_scope._call_claude_cli')
    def test_read_file_caches_result(self, mock_cli):
        """read_file should cache successful reads."""
        from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager

        mock_cli.return_value = "file content"
        manager = LocalCacheManager()
        ops = _create_file_ops(manager)

        # First read - should call CLI
        result1 = ops["read_file"]("/test/file.txt")
        assert result1["success"] is True
        assert result1["content"] == "file content"
        assert result1.get("cached") is False

        # Second read - should use cache
        result2 = ops["read_file"]("/test/file.txt")
        assert result2["success"] is True
        assert result2.get("cached") is True

        # CLI should only be called once
        assert mock_cli.call_count == 1

    @patch('scripts.agentica.unified_scope._call_claude_cli')
    def test_write_file_invalidates_cache(self, mock_cli):
        """write_file should invalidate cache for that path."""
        from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager

        mock_cli.return_value = "done"
        manager = LocalCacheManager()
        ops = _create_file_ops(manager)

        # Read first to cache
        mock_cli.return_value = "original content"
        ops["read_file"]("/test/file.txt")

        # Write should invalidate
        mock_cli.return_value = "written"
        ops["write_file"]("/test/file.txt", "new content")

        # Cache should be invalidated
        assert manager.get_cached("/test/file.txt") is None

    @patch('scripts.agentica.unified_scope._call_claude_cli')
    def test_edit_file_invalidates_cache(self, mock_cli):
        """edit_file should invalidate cache for that path."""
        from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager

        mock_cli.return_value = "done"
        manager = LocalCacheManager()
        ops = _create_file_ops(manager)

        # Read first to cache
        mock_cli.return_value = "original content"
        ops["read_file"]("/test/file.txt")

        # Edit should invalidate
        mock_cli.return_value = "edited"
        ops["edit_file"]("/test/file.txt", "old", "new")

        # Cache should be invalidated
        assert manager.get_cached("/test/file.txt") is None

    @patch('scripts.agentica.unified_scope._call_claude_cli')
    def test_operations_are_logged(self, mock_cli):
        """All operations should be logged."""
        from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager

        mock_cli.return_value = "result"
        manager = LocalCacheManager()
        ops = _create_file_ops(manager)

        ops["read_file"]("/test/file.txt")
        ops["bash"]("ls -la")
        ops["grep"]("pattern", "/path")

        log = manager.get_all_operations()

        assert len(log) >= 3
        operations = [op["operation"] for op in log]
        assert "read" in operations
        assert "bash" in operations
        assert "grep" in operations

    def test_debug_get_cache_returns_all_cached(self):
        """debug_get_cache should return all cached entries via manager."""
        from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        ops = _create_file_ops(manager)

        # Manually cache something
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")
        manager.set_cached("/test", result)

        cache = ops["debug_get_cache"]()
        assert "/test" in cache
        assert cache["/test"].content == "data"

    def test_debug_clear_cache_clears_all(self):
        """debug_clear_cache should clear all cached entries."""
        from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager
        from scripts.agentica.claude_scope import ClaudeResult

        manager = LocalCacheManager()
        ops = _create_file_ops(manager)

        # Cache something
        result = ClaudeResult(success=True, operation="read", path="/test", content="data")
        manager.set_cached("/test", result)

        ops["debug_clear_cache"]()

        assert manager.get_all_cached() == {}


# ============================================================================
# Test 6: Backward Compatibility Wrappers
# ============================================================================


class TestBackwardCompatibilityWrappers:
    """Test that existing wrapper functions still work."""

    def test_create_file_ops_with_shared_wrapper_exists(self):
        """_create_file_ops_with_shared should still exist."""
        from scripts.agentica.unified_scope import _create_file_ops_with_shared

        assert callable(_create_file_ops_with_shared)

    def test_create_file_ops_default_wrapper_exists(self):
        """_create_file_ops_default should still exist."""
        from scripts.agentica.unified_scope import _create_file_ops_default

        assert callable(_create_file_ops_default)

    @patch('scripts.agentica.unified_scope._call_claude_cli')
    def test_default_wrapper_uses_local_cache_manager(self, mock_cli):
        """_create_file_ops_default should use LocalCacheManager internally."""
        from scripts.agentica.unified_scope import _create_file_ops_default

        mock_cli.return_value = "content"
        ops = _create_file_ops_default()

        # Should work and cache
        result1 = ops["read_file"]("/test/file.txt")
        assert result1["success"] is True

        result2 = ops["read_file"]("/test/file.txt")
        assert result2.get("cached") is True

    @patch('scripts.agentica.unified_scope._call_claude_cli')
    def test_shared_wrapper_uses_shared_context(self, mock_cli):
        """_create_file_ops_with_shared should use provided SharedContext."""
        from scripts.agentica.unified_scope import _create_file_ops_with_shared
        from scripts.agentica.claude_scope import SharedContext

        mock_cli.return_value = "content"
        shared = SharedContext()
        ops = _create_file_ops_with_shared(shared)

        # Operations should log to shared context
        ops["read_file"]("/test/file.txt")

        log = shared.get_all_operations()
        assert len(log) >= 1
        assert log[0]["operation"] == "read"
