"""Level 1 Tests: Scope CRUD Operations.

Tests for scope file operations with mocked _call_claude_cli.
No real Claude CLI calls - all deterministic.

Test implementation follows TDD best practices:
- Mock _call_claude_cli at unified_scope module level
- Test structure and behavior, not exact output
- Use tmp_path fixtures for isolation
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from uuid import uuid4


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def session_id() -> str:
    """Generate unique session ID for test isolation."""
    return f"test-{uuid4().hex[:8]}"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def mock_claude_cli():
    """Patch _call_claude_cli to return deterministic responses."""
    with patch('scripts.agentica.unified_scope._call_claude_cli') as mock:
        mock.return_value = "Mocked CLI response"
        yield mock


@pytest.fixture
def scope_with_mock(mock_claude_cli, db_path: Path, session_id: str):
    """Create unified scope with mocked CLI."""
    from scripts.agentica.unified_scope import create_unified_scope

    return create_unified_scope(
        session_id=session_id,
        db_path=db_path,
        enable_memory=False,
        enable_tasks=False,
    )


# ============================================================================
# Test: read_file
# ============================================================================


class TestReadFile:
    """Tests for read_file scope operation."""

    def test_read_file_returns_content(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """read_file should return success with content from CLI."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "file content here"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["read_file"]("test.txt")

        assert result["success"] is True
        assert result["path"] == "test.txt"
        assert result["content"] == "file content here"
        assert result["cached"] is False
        mock_claude_cli.assert_called_once()

    def test_read_file_caches_result(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """Second read_file call should use cache, not call CLI again."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "cached content"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        # First call
        result1 = scope["read_file"]("cached.txt")
        assert result1["cached"] is False

        # Second call - should use cache
        result2 = scope["read_file"]("cached.txt")
        assert result2["cached"] is True
        assert result2["content"] == "cached content"

        # CLI should only be called once
        assert mock_claude_cli.call_count == 1

    def test_read_file_returns_error_on_exception(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """read_file should return error dict when CLI fails."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.side_effect = RuntimeError("File not found")

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["read_file"]("nonexistent.txt")

        assert result["success"] is False
        assert result["path"] == "nonexistent.txt"
        assert "File not found" in result["error"]
        assert result["content"] is None


# ============================================================================
# Test: write_file
# ============================================================================


class TestWriteFile:
    """Tests for write_file scope operation."""

    def test_write_file_creates_file(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """write_file should call CLI with content and return success."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "File written successfully"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["write_file"]("new_file.txt", "new content")

        assert result["success"] is True
        assert result["path"] == "new_file.txt"
        mock_claude_cli.assert_called_once()

        # Verify CLI was called with content in prompt
        call_args = mock_claude_cli.call_args
        prompt = call_args[0][0]
        assert "new_file.txt" in prompt
        assert "new content" in prompt

    def test_write_file_invalidates_cache(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """write_file should invalidate cache for the written path."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        # Read file first to populate cache
        mock_claude_cli.return_value = "original content"
        result1 = scope["read_file"]("file.txt")
        assert result1["cached"] is False

        # Write to same file
        mock_claude_cli.return_value = "Written"
        scope["write_file"]("file.txt", "new content")

        # Read again - should not be cached (invalidated by write)
        mock_claude_cli.return_value = "new content"
        result2 = scope["read_file"]("file.txt")
        assert result2["cached"] is False

        # CLI should have been called 3 times (read, write, read)
        assert mock_claude_cli.call_count == 3


# ============================================================================
# Test: edit_file
# ============================================================================


class TestEditFile:
    """Tests for edit_file scope operation."""

    def test_edit_file_replaces_text(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """edit_file should call CLI with old and new text."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "Edit complete"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["edit_file"]("code.py", "old_function", "new_function")

        assert result["success"] is True
        assert result["path"] == "code.py"

        # Verify CLI was called with both texts in prompt
        call_args = mock_claude_cli.call_args
        prompt = call_args[0][0]
        assert "code.py" in prompt
        assert "old_function" in prompt
        assert "new_function" in prompt

        # Verify correct tools were requested
        allowed_tools = call_args[0][1]
        assert "Read" in allowed_tools
        assert "Edit" in allowed_tools

    def test_edit_file_invalidates_cache(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """edit_file should invalidate cache for the edited path."""
        from scripts.agentica.unified_scope import create_unified_scope

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        # Read file first
        mock_claude_cli.return_value = "def old_func(): pass"
        scope["read_file"]("code.py")

        # Edit file
        mock_claude_cli.return_value = "Edited"
        scope["edit_file"]("code.py", "old_func", "new_func")

        # Read again - should not be cached
        mock_claude_cli.return_value = "def new_func(): pass"
        result = scope["read_file"]("code.py")
        assert result["cached"] is False


# ============================================================================
# Test: bash
# ============================================================================


class TestBash:
    """Tests for bash scope operation."""

    def test_bash_executes_command(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """bash should execute command and return output."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "file1.txt\nfile2.txt"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["bash"]("ls -la")

        assert result["success"] is True
        assert result["command"] == "ls -la"
        assert result["output"] == "file1.txt\nfile2.txt"

        # Verify CLI was called with command in prompt
        call_args = mock_claude_cli.call_args
        prompt = call_args[0][0]
        assert "ls -la" in prompt

        # Verify Bash tool was requested
        allowed_tools = call_args[0][1]
        assert "Bash" in allowed_tools

    def test_bash_returns_error_on_exception(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """bash should return error dict when CLI fails."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.side_effect = RuntimeError("Command failed")

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["bash"]("invalid_command")

        assert result["success"] is False
        assert "Command failed" in result["error"]
        assert result["output"] is None


# ============================================================================
# Test: grep
# ============================================================================


class TestGrep:
    """Tests for grep scope operation."""

    def test_grep_finds_pattern(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """grep should search for pattern and return matches."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "file.py:10: def search_function():"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["grep"]("search_function", "src/")

        assert result["success"] is True
        assert result["pattern"] == "search_function"
        assert result["path"] == "src/"
        assert "file.py:10" in result["matches"]

        # Verify CLI was called with pattern in prompt
        call_args = mock_claude_cli.call_args
        prompt = call_args[0][0]
        assert "search_function" in prompt
        assert "src/" in prompt

    def test_grep_uses_default_path(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """grep should use current directory as default path."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "matches here"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["grep"]("TODO")

        assert result["success"] is True
        assert result["path"] == "."


# ============================================================================
# Test: glob
# ============================================================================


class TestGlob:
    """Tests for glob scope operation."""

    def test_glob_matches_files(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """glob should return list of matching files."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "src/main.py\nsrc/utils.py\ntests/test_main.py"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["glob"]("**/*.py")

        assert result["success"] is True
        assert result["pattern"] == "**/*.py"
        assert "src/main.py" in result["files"]
        assert "src/utils.py" in result["files"]
        assert "tests/test_main.py" in result["files"]
        assert len(result["files"]) == 3

    def test_glob_filters_empty_lines(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """glob should filter out empty lines and comments."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "file1.py\n\nfile2.py\n# comment\nfile3.py\n"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        result = scope["glob"]("*.py")

        assert result["success"] is True
        assert len(result["files"]) == 3
        assert "" not in result["files"]
        assert "# comment" not in result["files"]


# ============================================================================
# Test: Operation Logging
# ============================================================================


class TestOperationLogging:
    """Tests for operation log tracking."""

    def test_operations_are_logged(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """All operations should be logged in operation_log."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "response"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        # Perform various operations
        scope["read_file"]("file1.txt")
        scope["write_file"]("file2.txt", "content")
        scope["bash"]("echo hello")

        # Check operation log
        log = scope["debug_get_operation_log"]()
        assert len(log) == 3

        # Verify operations are logged correctly
        operations = [entry["operation"] for entry in log]
        assert "read" in operations
        assert "write" in operations
        assert "bash" in operations

    def test_failed_operations_logged_with_error(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """Failed operations should be logged with error info."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.side_effect = RuntimeError("Failed")

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        scope["read_file"]("error.txt")

        log = scope["debug_get_operation_log"]()
        assert len(log) == 1
        assert log[0]["success"] is False
        assert "Failed" in log[0]["error"]


# ============================================================================
# Test: Cache Utilities
# ============================================================================


class TestCacheUtilities:
    """Tests for cache utility functions."""

    def test_debug_get_cache_returns_cached_files(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """debug_get_cache should return all cached files."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "content"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        scope["read_file"]("file1.txt")
        scope["read_file"]("file2.txt")

        cache = scope["debug_get_cache"]()
        assert "file1.txt" in cache
        assert "file2.txt" in cache

    def test_debug_clear_cache_empties_cache(
        self, mock_claude_cli, db_path: Path, session_id: str
    ):
        """debug_clear_cache should empty the file cache."""
        from scripts.agentica.unified_scope import create_unified_scope

        mock_claude_cli.return_value = "content"

        scope = create_unified_scope(
            session_id=session_id,
            db_path=db_path,
            enable_memory=False,
            enable_tasks=False,
        )

        scope["read_file"]("file.txt")
        assert len(scope["debug_get_cache"]()) == 1

        scope["debug_clear_cache"]()
        assert len(scope["debug_get_cache"]()) == 0

        # After clear, next read should not be cached
        scope["read_file"]("file.txt")
        assert mock_claude_cli.call_count == 2  # Called twice, not cached
