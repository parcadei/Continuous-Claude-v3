"""Security tests for path canonicalization (Phases 6-15).

These tests verify that:
1. _canonicalize_path helper resolves paths correctly
2. Path traversal attacks are blocked
3. Symlinks are resolved
4. All file operations validate paths

Test Strategy:
- Write FAILING tests first (TDD)
- Tests will fail until implementation is added
- Run with: uv run pytest tests/unit/test_security_path.py -v
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ============================================================================
# Phase 6: Test _canonicalize_path helper function
# ============================================================================


class TestCanonicalizePathHelper:
    """Test _canonicalize_path helper function."""

    def test_canonicalize_resolves_parent_references(self, tmp_path):
        """Should resolve ../ sequences in paths."""
        from scripts.agentica.claude_scope import _canonicalize_path

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        subdir = project_dir / "subdir"
        subdir.mkdir()

        # Test resolving ../
        path = str(subdir / ".." / "file.txt")
        result = _canonicalize_path(path, str(project_dir))

        # Should resolve to project_dir/file.txt
        expected = str(project_dir / "file.txt")
        assert result == expected

    def test_canonicalize_resolves_symlinks(self, tmp_path):
        """Should resolve symlinks to their real paths."""
        from scripts.agentica.claude_scope import _canonicalize_path

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        real_file = project_dir / "real.txt"
        real_file.write_text("content")
        symlink = project_dir / "link.txt"
        symlink.symlink_to(real_file)

        # Test resolving symlink
        result = _canonicalize_path(str(symlink), str(project_dir))

        # Should resolve to the real file
        expected = str(real_file)
        assert result == expected

    def test_canonicalize_raises_when_path_escapes_project_dir(self, tmp_path):
        """Should raise ValueError when path escapes project_dir."""
        from scripts.agentica.claude_scope import _canonicalize_path

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("secret")

        # Test path traversal attempt
        with pytest.raises(ValueError) as exc_info:
            _canonicalize_path("../secret.txt", str(project_dir))

        # Error message should mention escaping
        assert "escapes" in str(exc_info.value).lower()

    def test_canonicalize_allows_paths_within_project_dir(self, tmp_path):
        """Should allow paths within project_dir."""
        from scripts.agentica.claude_scope import _canonicalize_path

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        valid_file = project_dir / "valid.txt"
        valid_file.write_text("content")

        # Test valid path
        result = _canonicalize_path(str(valid_file), str(project_dir))

        # Should return the real path
        assert result == str(valid_file)

    def test_canonicalize_works_without_project_dir(self, tmp_path):
        """Should work without validation when project_dir is None."""
        from scripts.agentica.claude_scope import _canonicalize_path

        # Create file outside any project
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Test without project_dir (no validation)
        result = _canonicalize_path(str(test_file), project_dir=None)

        # Should return the real path without validation
        assert result == str(test_file)

    def test_canonicalize_expands_tilde(self, tmp_path):
        """Should expand ~ to user home directory."""
        from scripts.agentica.claude_scope import _canonicalize_path

        # Test with tilde (no project_dir validation)
        result = _canonicalize_path("~/test.txt", project_dir=None)

        # Should expand to full path
        assert not result.startswith("~")
        assert os.path.isabs(result)

    def test_canonicalize_raises_when_symlink_escapes(self, tmp_path):
        """Should raise ValueError when symlink points outside project_dir."""
        from scripts.agentica.claude_scope import _canonicalize_path

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("secret")

        # Create symlink inside project pointing outside
        sneaky_link = project_dir / "sneaky.txt"
        sneaky_link.symlink_to(secret_file)

        # Test symlink escape attempt
        with pytest.raises(ValueError) as exc_info:
            _canonicalize_path(str(sneaky_link), str(project_dir))

        # Error message should mention escaping
        assert "escapes" in str(exc_info.value).lower()


# ============================================================================
# Phase 7: Test read_file path validation (create_claude_scope)
# ============================================================================


class TestReadFilePathValidation:
    """Test read_file path validation in create_claude_scope."""

    def test_read_file_blocks_parent_traversal(self, tmp_path):
        """Should block ../secret.txt path traversal."""
        from scripts.agentica.claude_scope import create_claude_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("secret content")

        # Create scope with project_dir
        scope = create_claude_scope(project_dir=str(project_dir))

        # Attempt path traversal
        result = scope["read_file"]("../secret.txt")

        # Should fail with error
        assert result["success"] is False
        assert "error" in result
        assert "escapes" in result["error"].lower() or "project directory" in result["error"].lower()

    def test_read_file_blocks_absolute_path_outside_project(self, tmp_path):
        """Should block /etc/passwd when project_dir is set."""
        from scripts.agentica.claude_scope import create_claude_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create scope with project_dir
        scope = create_claude_scope(project_dir=str(project_dir))

        # Attempt to read /etc/passwd
        result = scope["read_file"]("/etc/passwd")

        # Should fail with error
        assert result["success"] is False
        assert "error" in result
        assert "escapes" in result["error"].lower() or "project directory" in result["error"].lower()

    def test_read_file_allows_valid_paths_within_project(self, tmp_path):
        """Should allow reading files within project_dir."""
        from scripts.agentica.claude_scope import create_claude_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        valid_file = project_dir / "valid.txt"
        valid_file.write_text("valid content")

        # Mock the CLI call to avoid actual subprocess
        with patch('scripts.agentica.claude_scope._call_claude_cli') as mock_cli:
            mock_cli.return_value = "valid content"

            # Create scope with project_dir
            scope = create_claude_scope(project_dir=str(project_dir))

            # Read valid file
            result = scope["read_file"](str(valid_file))

            # Should succeed
            assert result["success"] is True
            assert result["content"] == "valid content"


# ============================================================================
# Phase 8: Test write_file path validation (create_claude_scope)
# ============================================================================


class TestWriteFilePathValidation:
    """Test write_file path validation in create_claude_scope."""

    def test_write_file_blocks_path_outside_project(self, tmp_path):
        """Should block writing outside project_dir."""
        from scripts.agentica.claude_scope import create_claude_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create scope with project_dir
        scope = create_claude_scope(project_dir=str(project_dir))

        # Attempt to write outside project
        result = scope["write_file"]("../secret.txt", "malicious content")

        # Should fail with error
        assert result["success"] is False
        assert "error" in result
        assert "escapes" in result["error"].lower() or "project directory" in result["error"].lower()

    def test_write_file_blocks_symlink_escape(self, tmp_path):
        """Should block writing via symlink that escapes project_dir."""
        from scripts.agentica.claude_scope import create_claude_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("original")

        # Create symlink inside project pointing outside
        sneaky_link = project_dir / "sneaky.txt"
        sneaky_link.symlink_to(outside_file)

        # Create scope with project_dir
        scope = create_claude_scope(project_dir=str(project_dir))

        # Attempt to write via symlink
        result = scope["write_file"](str(sneaky_link), "malicious")

        # Should fail with error
        assert result["success"] is False
        assert "error" in result
        assert "escapes" in result["error"].lower()

    def test_write_file_allows_valid_paths_within_project(self, tmp_path):
        """Should allow writing files within project_dir."""
        from scripts.agentica.claude_scope import create_claude_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        target_file = project_dir / "new.txt"

        # Mock the CLI call
        with patch('scripts.agentica.claude_scope._call_claude_cli') as mock_cli:
            mock_cli.return_value = "File written successfully"

            # Create scope with project_dir
            scope = create_claude_scope(project_dir=str(project_dir))

            # Write to valid path
            result = scope["write_file"](str(target_file), "new content")

            # Should succeed
            assert result["success"] is True


# ============================================================================
# Phase 9: Test edit_file path validation (create_claude_scope)
# ============================================================================


class TestEditFilePathValidation:
    """Test edit_file path validation in create_claude_scope."""

    def test_edit_file_blocks_path_outside_project(self, tmp_path):
        """Should block editing files outside project_dir."""
        from scripts.agentica.claude_scope import create_claude_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create scope with project_dir
        scope = create_claude_scope(project_dir=str(project_dir))

        # Attempt to edit outside project
        result = scope["edit_file"]("../secret.txt", "old", "new")

        # Should fail with error
        assert result["success"] is False
        assert "error" in result
        assert "escapes" in result["error"].lower() or "project directory" in result["error"].lower()

    def test_edit_file_allows_valid_paths_within_project(self, tmp_path):
        """Should allow editing files within project_dir."""
        from scripts.agentica.claude_scope import create_claude_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        target_file = project_dir / "edit.txt"
        target_file.write_text("old content")

        # Mock the CLI call
        with patch('scripts.agentica.claude_scope._call_claude_cli') as mock_cli:
            mock_cli.return_value = "Edit successful"

            # Create scope with project_dir
            scope = create_claude_scope(project_dir=str(project_dir))

            # Edit valid path
            result = scope["edit_file"](str(target_file), "old", "new")

            # Should succeed
            assert result["success"] is True


# ============================================================================
# Phases 10-12: Test create_claude_scope_with_shared path validation
# ============================================================================


class TestSharedContextPathValidation:
    """Test path validation in create_claude_scope_with_shared."""

    def test_shared_read_file_blocks_traversal(self, tmp_path):
        """Should block path traversal in shared context."""
        from scripts.agentica.claude_scope import create_claude_scope_with_shared, SharedContext

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("secret")

        # Create shared context and scope
        shared = SharedContext()
        scope = create_claude_scope_with_shared(shared, project_dir=str(project_dir))

        # Attempt path traversal
        result = scope["read_file"]("../secret.txt")

        # Should fail
        assert result["success"] is False
        assert "escapes" in result["error"].lower()

    def test_shared_write_file_blocks_traversal(self, tmp_path):
        """Should block path traversal in write_file with shared context."""
        from scripts.agentica.claude_scope import create_claude_scope_with_shared, SharedContext

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create shared context and scope
        shared = SharedContext()
        scope = create_claude_scope_with_shared(shared, project_dir=str(project_dir))

        # Attempt path traversal
        result = scope["write_file"]("../secret.txt", "malicious")

        # Should fail
        assert result["success"] is False
        assert "escapes" in result["error"].lower()

    def test_shared_edit_file_blocks_traversal(self, tmp_path):
        """Should block path traversal in edit_file with shared context."""
        from scripts.agentica.claude_scope import create_claude_scope_with_shared, SharedContext

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create shared context and scope
        shared = SharedContext()
        scope = create_claude_scope_with_shared(shared, project_dir=str(project_dir))

        # Attempt path traversal
        result = scope["edit_file"]("../secret.txt", "old", "new")

        # Should fail
        assert result["success"] is False
        assert "escapes" in result["error"].lower()


# ============================================================================
# Phases 13-14: Test unified_scope path validation
# ============================================================================


class TestUnifiedScopePathValidation:
    """Test path validation in unified_scope."""

    def test_unified_scope_with_shared_blocks_traversal(self, tmp_path):
        """Should block path traversal in unified scope with shared context."""
        from scripts.agentica.unified_scope import create_unified_scope, SharedContext

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("secret")

        # Create unified scope with shared context
        shared = SharedContext()
        scope = create_unified_scope(
            session_id="test",
            shared_context=shared,
            project_dir=str(project_dir),
            enable_memory=False,
            enable_tasks=False,
        )

        # Attempt path traversal
        result = scope["read_file"]("../secret.txt")

        # Should fail
        assert result["success"] is False
        assert "escapes" in result["error"].lower()

    def test_unified_scope_default_blocks_traversal(self, tmp_path):
        """Should block path traversal in unified scope with default file ops."""
        from scripts.agentica.unified_scope import create_unified_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("secret")

        # Create unified scope without shared context
        scope = create_unified_scope(
            session_id="test",
            project_dir=str(project_dir),
            enable_memory=False,
            enable_tasks=False,
        )

        # Attempt path traversal
        result = scope["read_file"]("../secret.txt")

        # Should fail
        assert result["success"] is False
        assert "escapes" in result["error"].lower()


# ============================================================================
# Phase 15: Test create_unified_scope wiring
# ============================================================================


class TestUnifiedScopeWiring:
    """Test project_dir parameter wiring in create_unified_scope."""

    def test_unified_scope_respects_project_dir_parameter(self, tmp_path):
        """Should respect project_dir parameter and validate paths."""
        from scripts.agentica.unified_scope import create_unified_scope

        # Create directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create scope with project_dir
        scope = create_unified_scope(
            session_id="test",
            project_dir=str(project_dir),
            enable_memory=False,
            enable_tasks=False,
        )

        # Attempt to access outside project
        result = scope["read_file"]("/etc/passwd")

        # Should fail
        assert result["success"] is False
        assert "error" in result

    def test_unified_scope_allows_none_project_dir(self, tmp_path):
        """Should allow None project_dir (no validation)."""
        from scripts.agentica.unified_scope import create_unified_scope

        # Create scope without project_dir
        scope = create_unified_scope(
            session_id="test",
            project_dir=None,
            enable_memory=False,
            enable_tasks=False,
        )

        # Should have file operations
        assert "read_file" in scope
        assert "write_file" in scope
        assert "edit_file" in scope


# ============================================================================
# Additional Security Tests
# ============================================================================


class TestPathSecurityEdgeCases:
    """Test edge cases in path security."""

    def test_empty_path_handling(self, tmp_path):
        """Should handle empty paths gracefully."""
        from scripts.agentica.claude_scope import create_claude_scope

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        scope = create_claude_scope(project_dir=str(project_dir))

        result = scope["read_file"]("")

        # Should fail (empty path should not be valid)
        assert result["success"] is False

    def test_null_bytes_in_path(self, tmp_path):
        """Should reject paths with null bytes."""
        from scripts.agentica.claude_scope import create_claude_scope

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        scope = create_claude_scope(project_dir=str(project_dir))

        # Attempt path with null byte
        result = scope["read_file"]("file\x00.txt")

        # Should fail
        assert result["success"] is False

    def test_unicode_path_normalization(self, tmp_path):
        """Should handle Unicode path normalization."""
        from scripts.agentica.claude_scope import create_claude_scope

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create file with unicode name
        unicode_file = project_dir / "café.txt"
        unicode_file.write_text("content")

        # Mock the CLI call
        with patch('scripts.agentica.claude_scope._call_claude_cli') as mock_cli:
            mock_cli.return_value = "content"

            scope = create_claude_scope(project_dir=str(project_dir))

            # Read file with unicode name
            result = scope["read_file"](str(unicode_file))

            # Should succeed
            assert result["success"] is True
