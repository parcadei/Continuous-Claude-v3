"""Tests for path traversal prevention."""
import os

import pytest


class TestPathCanonicalization:
    """Tests for path traversal prevention via _canonicalize_path."""

    def test_path_traversal_blocked(self, tmp_path):
        """Attempting to escape project_dir raises ValueError."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        project_dir = str(tmp_path / "project")
        os.makedirs(project_dir)

        with pytest.raises(ValueError, match="escapes project directory"):
            _canonicalize_path("../../../etc/passwd", project_dir)

    def test_symlink_traversal_blocked(self, tmp_path):
        """Symlinks that escape project_dir are blocked."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create external file
        external = tmp_path / "external"
        external.write_text("secret")

        # Create symlink inside project pointing outside
        symlink = project_dir / "escape"
        symlink.symlink_to(external)

        with pytest.raises(ValueError, match="escapes project directory"):
            _canonicalize_path(str(symlink), str(project_dir))

    def test_valid_path_within_project(self, tmp_path):
        """Valid paths within project_dir are allowed."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "src").mkdir()
        valid_file = project_dir / "src" / "main.py"
        valid_file.write_text("# code")

        result = _canonicalize_path(str(valid_file), str(project_dir))
        assert result == str(valid_file.resolve())

    def test_relative_path_resolved(self, tmp_path):
        """Relative paths are resolved correctly."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        subdir = project_dir / "subdir"
        subdir.mkdir()
        file_path = subdir / "file.txt"
        file_path.write_text("content")

        # Test relative path from project dir
        # Note: _canonicalize_path uses os.path.realpath which resolves from cwd,
        # not from project_dir. The function resolves symlinks but doesn't
        # change directory context for relative paths.
        # To test relative path resolution, we need to be in the project_dir
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_dir))
            result = _canonicalize_path("subdir/file.txt", str(project_dir))
            assert result == str(file_path.resolve())
        finally:
            os.chdir(original_cwd)

    def test_double_dot_in_middle_blocked(self, tmp_path):
        """Paths with .. in middle that escape are blocked."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "subdir").mkdir()

        with pytest.raises(ValueError, match="escapes project directory"):
            _canonicalize_path("subdir/../../etc/passwd", str(project_dir))

    def test_canonicalize_path_exists(self):
        """_canonicalize_path function is exported from module."""
        from scripts.agentica_patterns import claude_scope
        assert hasattr(claude_scope, '_canonicalize_path')
        assert callable(claude_scope._canonicalize_path)

    def test_path_without_project_dir_allowed(self, tmp_path):
        """Paths without project_dir constraint are resolved but not validated."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        # Should not raise even for paths outside any directory
        result = _canonicalize_path("/etc/passwd", None)
        assert result == os.path.realpath("/etc/passwd")

    def test_project_dir_itself_allowed(self, tmp_path):
        """The project directory itself is a valid path."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = _canonicalize_path(str(project_dir), str(project_dir))
        assert result == str(project_dir.resolve())

    def test_nested_symlinks_blocked(self, tmp_path):
        """Nested symlinks that eventually escape are blocked."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create external file
        external = tmp_path / "external_secret"
        external.write_text("super secret")

        # Create chain of symlinks
        link1 = project_dir / "link1"
        link2 = project_dir / "link2"

        # link1 -> link2 -> external (outside project)
        link2.symlink_to(external)
        link1.symlink_to(link2)

        with pytest.raises(ValueError, match="escapes project directory"):
            _canonicalize_path(str(link1), str(project_dir))

    def test_tilde_expansion(self, tmp_path):
        """Tilde in path is expanded."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        # Without project_dir constraint, tilde should expand
        result = _canonicalize_path("~", None)
        assert result == os.path.realpath(os.path.expanduser("~"))

    def test_absolute_path_outside_project_blocked(self, tmp_path):
        """Absolute paths outside project_dir are blocked."""
        from scripts.agentica_patterns.claude_scope import _canonicalize_path

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with pytest.raises(ValueError, match="escapes project directory"):
            _canonicalize_path("/etc/passwd", str(project_dir))
