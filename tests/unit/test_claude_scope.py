"""Tests for Claude CLI scope functions - TDD Implementation.

The claude_scope module provides:
- read_file(), write_file(), edit_file() for file operations
- bash() for command execution
- grep(), glob() for search operations
- Caching for scope persistence

Test implementation follows strict TDD:
1. Write failing tests
2. Implement minimal code to pass
3. Verify tests pass
"""

import pytest
from unittest.mock import patch, MagicMock


# ============================================================================
# Phase 1: create_claude_scope Tests
# ============================================================================


class TestCreateClaudeScope:
    """Test create_claude_scope factory function."""

    def test_returns_dict_with_expected_keys(self):
        """Should return scope dict with all expected functions."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        assert "read_file" in scope
        assert "write_file" in scope
        assert "edit_file" in scope
        assert "bash" in scope
        assert "grep" in scope
        assert "glob" in scope
        assert "debug_get_cache" in scope
        assert "debug_get_operation_log" in scope

    def test_functions_are_callable(self):
        """All scope values should be callable functions."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        for key, value in scope.items():
            assert callable(value), f"{key} should be callable"


# ============================================================================
# Phase 2: read_file Tests
# ============================================================================


class TestReadFile:
    """Test read_file scope function."""

    def test_read_file_success(self):
        """Should return success dict with file content."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "file content here"

            result = scope["read_file"]("test.txt")

            assert result["success"] is True
            assert result["path"].endswith("test.txt")
            assert result["content"] == "file content here"
            assert result["cached"] is False

    def test_read_file_uses_cache(self):
        """Second read should use cache and not call CLI."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope(cache_reads=True)

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "cached content"

            # First read
            result1 = scope["read_file"]("test.txt")
            # Second read
            result2 = scope["read_file"]("test.txt")

            # CLI should only be called once
            assert mock_cli.call_count == 1
            assert result2["cached"] is True
            assert result2["content"] == "cached content"

    def test_read_file_error(self):
        """Should return error dict on failure."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.side_effect = RuntimeError("File not found")

            result = scope["read_file"]("nonexistent.txt")

            assert result["success"] is False
            assert result["path"].endswith("nonexistent.txt")
            assert "File not found" in result["error"]

    def test_read_file_cache_disabled(self):
        """Should not cache when cache_reads=False."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope(cache_reads=False)

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "content"

            scope["read_file"]("test.txt")
            scope["read_file"]("test.txt")

            # CLI should be called twice
            assert mock_cli.call_count == 2


# ============================================================================
# Phase 3: write_file Tests
# ============================================================================


class TestWriteFile:
    """Test write_file scope function."""

    def test_write_file_success(self):
        """Should return success dict after writing."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "File written successfully"

            result = scope["write_file"]("test.txt", "new content")

            assert result["success"] is True
            assert result["path"].endswith("test.txt")
            mock_cli.assert_called_once()

    def test_write_file_invalidates_cache(self):
        """Writing should invalidate cached read for same file."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope(cache_reads=True)

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "content"

            # Read to populate cache
            scope["read_file"]("test.txt")

            # Write should invalidate
            scope["write_file"]("test.txt", "new content")

            # Read again - should call CLI (not cached)
            scope["read_file"]("test.txt")

            assert mock_cli.call_count == 3  # read, write, read

    def test_write_file_error(self):
        """Should return error dict on failure."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.side_effect = RuntimeError("Permission denied")

            result = scope["write_file"]("readonly.txt", "content")

            assert result["success"] is False
            assert "Permission denied" in result["error"]


# ============================================================================
# Phase 4: edit_file Tests
# ============================================================================


class TestEditFile:
    """Test edit_file scope function."""

    def test_edit_file_success(self):
        """Should return success dict after editing."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "Edit complete"

            result = scope["edit_file"]("test.txt", "old", "new")

            assert result["success"] is True
            assert result["path"].endswith("test.txt")

    def test_edit_file_invalidates_cache(self):
        """Editing should invalidate cached read for same file."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope(cache_reads=True)

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "content"

            # Read to populate cache
            scope["read_file"]("test.txt")

            # Edit should invalidate
            scope["edit_file"]("test.txt", "old", "new")

            # Verify cache is cleared
            cache = scope["debug_get_cache"]()
            assert "test.txt" not in cache


# ============================================================================
# Phase 5: bash Tests
# ============================================================================


class TestBash:
    """Test bash scope function."""

    def test_bash_success(self):
        """Should return success dict with command output."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "file1.txt\nfile2.txt"

            result = scope["bash"]("ls")

            assert result["success"] is True
            assert result["command"] == "ls"
            assert "file1.txt" in result["output"]

    def test_bash_error(self):
        """Should return error dict on failure."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.side_effect = RuntimeError("Command failed")

            result = scope["bash"]("invalid_command")

            assert result["success"] is False
            assert "Command failed" in result["error"]


# ============================================================================
# Phase 6: grep and glob Tests
# ============================================================================


class TestGrepAndGlob:
    """Test grep and glob scope functions."""

    def test_grep_success(self):
        """Should return success dict with matches."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "test.py:10:pattern found"

            result = scope["grep"]("pattern", ".")

            assert result["success"] is True
            assert result["pattern"] == "pattern"
            assert "pattern found" in result["matches"]

    def test_glob_success(self):
        """Should return success dict with file list."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "src/main.py\nsrc/util.py"

            result = scope["glob"]("**/*.py")

            assert result["success"] is True
            assert result["pattern"] == "**/*.py"
            assert "src/main.py" in result["files"]
            assert len(result["files"]) == 2


# ============================================================================
# Phase 7: Operation Log Tests
# ============================================================================


class TestOperationLog:
    """Test operation logging."""

    def test_operations_logged(self):
        """All operations should be logged."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "result"

            scope["read_file"]("file1.txt")
            scope["write_file"]("file2.txt", "content")
            scope["bash"]("ls")

            log = scope["debug_get_operation_log"]()

            assert len(log) == 3
            assert log[0]["operation"] == "read"
            assert log[1]["operation"] == "write"
            assert log[2]["operation"] == "bash"

    def test_failed_operations_logged(self):
        """Failed operations should also be logged."""
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.side_effect = RuntimeError("Failed")

            scope["read_file"]("fail.txt")

            log = scope["debug_get_operation_log"]()

            assert len(log) == 1
            assert log[0]["success"] is False
            assert "Failed" in log[0]["error"]


# ============================================================================
# Phase 8: SharedContext Tests
# ============================================================================


class TestSharedContext:
    """Test SharedContext for multi-agent coordination.

    Note: SharedContext methods are synchronous with threading.Lock.
    """

    def test_shared_context_creation(self):
        """Should create SharedContext with empty state."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()

        assert shared.file_cache == {}
        assert shared.operation_log == []

    def test_shared_context_caching(self):
        """Should cache and retrieve file content."""
        from scripts.agentica.claude_scope import SharedContext, ClaudeResult

        shared = SharedContext()

        result = ClaudeResult(
            success=True,
            operation="read",
            path="test.txt",
            content="hello"
        )

        shared.set_cached("test.txt", result)
        cached = shared.get_cached("test.txt")

        assert cached is not None
        assert cached.content == "hello"

    def test_shared_context_invalidation(self):
        """Should invalidate cached entries."""
        from scripts.agentica.claude_scope import SharedContext, ClaudeResult

        shared = SharedContext()

        result = ClaudeResult(
            success=True,
            operation="read",
            path="test.txt",
            content="hello"
        )

        shared.set_cached("test.txt", result)
        shared.invalidate("test.txt")

        cached = shared.get_cached("test.txt")
        assert cached is None

    def test_shared_context_operation_logging(self):
        """Should log operations."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()

        shared.log_operation({"operation": "read", "path": "test.txt"})
        shared.log_operation({"operation": "write", "path": "test.txt"})

        assert len(shared.operation_log) == 2

    def test_shared_context_conflict_detection(self):
        """Should detect write conflicts."""
        from scripts.agentica.claude_scope import SharedContext

        shared = SharedContext()

        shared.log_operation({
            "operation": "write",
            "path": "test.txt",
            "agent": "agent-1"
        })
        shared.log_operation({
            "operation": "write",
            "path": "test.txt",
            "agent": "agent-2"
        })

        writes = shared.get_writes_for_path("test.txt")
        assert len(writes) == 2

    def test_create_scope_with_shared(self):
        """Should create scope using shared context."""
        from scripts.agentica.claude_scope import (
            SharedContext,
            create_claude_scope_with_shared
        )

        shared = SharedContext()
        scope = create_claude_scope_with_shared(shared)

        assert "read_file" in scope
        assert "write_file" in scope


class TestSharedContextIntegration:
    """Test SharedContext with multiple scopes.

    Note: Scope functions are sync (backward compatible) even though
    SharedContext methods are async internally.
    """

    def test_multiple_scopes_share_cache(self):
        """Multiple scopes should share the same cache."""
        from scripts.agentica.claude_scope import (
            SharedContext,
            create_claude_scope_with_shared,
            ClaudeResult
        )

        shared = SharedContext()
        scope1 = create_claude_scope_with_shared(shared)
        scope2 = create_claude_scope_with_shared(shared)

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "shared content"

            # Read from scope1
            result1 = scope1["read_file"]("shared.txt")

            # Read from scope2 - should use cache
            result2 = scope2["read_file"]("shared.txt")

            assert mock_cli.call_count == 1
            assert result2["cached"] is True

    def test_shared_operation_log(self):
        """Operations from all scopes should be logged together."""
        from scripts.agentica.claude_scope import (
            SharedContext,
            create_claude_scope_with_shared
        )

        shared = SharedContext()
        scope1 = create_claude_scope_with_shared(shared)
        scope2 = create_claude_scope_with_shared(shared)

        with patch(
            'scripts.agentica.unified_scope._call_claude_cli'
        ) as mock_cli:
            mock_cli.return_value = "result"

            scope1["read_file"]("file1.txt")
            scope2["write_file"]("file2.txt", "content")

            assert len(shared.operation_log) == 2


# ============================================================================
# Phase 9: Integration with Patterns Tests
# ============================================================================


class TestPatternIntegration:
    """Test integration with Agentica patterns."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_scope_with_dependency_swarm(self, db):
        """Should work with DependencySwarm pattern."""
        from scripts.agentica.dependency_swarm import DependencySwarm
        from scripts.agentica.claude_scope import create_claude_scope

        scope = create_claude_scope()
        swarm = DependencySwarm(db=db, scope=scope)

        swarm.add_task("A", "Read and process file")

        with patch('scripts.agentica.dependency_swarm.tracked_spawn') as mock_spawn:
            mock_agent = MagicMock()

            # Mock the agent.call to be async
            async def async_call(*args, **kwargs):
                return "result"

            # Mock the agent.close to be async
            async def async_close():
                pass

            mock_agent.call = async_call
            mock_agent.close = async_close

            async def async_return(*args, **kwargs):
                return mock_agent

            mock_spawn.side_effect = async_return

            await swarm.execute()

            # Verify scope was passed to tracked_spawn
            call_kwargs = mock_spawn.call_args.kwargs
            assert "scope" in call_kwargs
            assert "read_file" in call_kwargs["scope"]

    @pytest.mark.asyncio
    async def test_use_claude_scope_parameter(self, db):
        """DependencySwarm should accept use_claude_scope parameter."""
        from scripts.agentica.dependency_swarm import DependencySwarm

        # Without use_claude_scope, scope should be empty or minimal
        swarm1 = DependencySwarm(db=db)
        assert "read_file" not in swarm1.scope

        # With use_claude_scope, scope should have claude functions
        swarm2 = DependencySwarm(db=db, use_claude_scope=True)
        assert "read_file" in swarm2.scope
        assert "write_file" in swarm2.scope
        assert "bash" in swarm2.scope
