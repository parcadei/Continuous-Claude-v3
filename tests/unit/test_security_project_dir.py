"""Tests for project_dir deprecation warning.

Phase 21 of security hardening: Deprecate project_dir=None to encourage
path validation and prevent traversal attacks.
"""
import warnings
import pytest
import tempfile


class TestProjectDirDeprecation:
    """Tests for project_dir=None deprecation warning."""

    def test_deprecation_warning_when_none(self):
        """DeprecationWarning is raised when project_dir=None."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            create_claude_scope(project_dir=None)

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "project_dir=None is deprecated" in str(deprecation_warnings[0].message)

    def test_no_warning_when_set(self, tmp_path):
        """No warning when project_dir is set."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            create_claude_scope(project_dir=str(tmp_path))

            deprecation_warnings = [
                x for x in w
                if issubclass(x.category, DeprecationWarning)
                and "project_dir" in str(x.message)
            ]
            assert len(deprecation_warnings) == 0

    def test_warning_is_actionable(self):
        """Warning message tells user what to do."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            create_claude_scope(project_dir=None)

            # Filter for our specific deprecation warning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            msg = str(deprecation_warnings[0].message)
            assert "required in a future version" in msg
            assert "path validation" in msg or "traversal" in msg

    def test_warning_stacklevel_points_to_caller(self):
        """Warning stacklevel should point to caller, not internal."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            create_claude_scope(project_dir=None)

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            # Verify the warning references this test file (the caller)
            # rather than claude_scope.py (the internal implementation)
            assert "test_security_project_dir.py" in deprecation_warnings[0].filename

    def test_default_none_triggers_warning(self):
        """Default argument (no project_dir specified) triggers warning."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Call without specifying project_dir at all
            create_claude_scope()

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "project_dir=None is deprecated" in str(deprecation_warnings[0].message)


class TestProjectDirDeprecationShared:
    """Tests for project_dir=None deprecation in create_claude_scope_with_shared."""

    def test_deprecation_warning_when_none_shared(self):
        """DeprecationWarning is raised when project_dir=None in shared scope."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope_with_shared, SharedContext
        shared = SharedContext()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            create_claude_scope_with_shared(shared, project_dir=None)

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "project_dir=None is deprecated" in str(deprecation_warnings[0].message)

    def test_no_warning_when_set_shared(self, tmp_path):
        """No warning when project_dir is set in shared scope."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope_with_shared, SharedContext
        shared = SharedContext()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            create_claude_scope_with_shared(shared, project_dir=str(tmp_path))

            deprecation_warnings = [
                x for x in w
                if issubclass(x.category, DeprecationWarning)
                and "project_dir" in str(x.message)
            ]
            assert len(deprecation_warnings) == 0
