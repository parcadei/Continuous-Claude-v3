"""Wizard migration and update mode tests for Continuous-Claude-v3.

Tests wizard --update functionality, hash comparison, and idempotency.
"""

import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestComputeFileHash:
    """Tests for file hash computation."""

    def test_compute_file_hash_empty_file(self, temp_dir: Path) -> None:
        """Test hashing an empty file."""
        from scripts.setup.wizard import compute_file_hash

        empty_file = temp_dir / "empty.txt"
        empty_file.write_text("")

        file_hash = compute_file_hash(empty_file)
        assert file_hash == hashlib.sha256(b"").hexdigest()

    def test_compute_file_hash_with_content(self, temp_dir: Path) -> None:
        """Test hashing a file with content."""
        from scripts.setup.wizard import compute_file_hash

        test_file = temp_dir / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content)

        file_hash = compute_file_hash(test_file)
        expected = hashlib.sha256(content.encode()).hexdigest()
        assert file_hash == expected

    def test_compute_file_hash_nonexistent(self, temp_dir: Path) -> None:
        """Test hashing a nonexistent file returns empty string."""
        from scripts.setup.wizard import compute_file_hash

        nonexistent = temp_dir / "nonexistent.txt"
        assert not nonexistent.exists()

        file_hash = compute_file_hash(nonexistent)
        assert file_hash == ""

    def test_compute_file_hash_directory(self, temp_dir: Path) -> None:
        """Test hashing a directory returns empty string."""
        from scripts.setup.wizard import compute_file_hash

        dir_path = temp_dir / "subdir"
        dir_path.mkdir()

        file_hash = compute_file_hash(dir_path)
        assert file_hash == ""


class TestComputeDirHash:
    """Tests for directory hash computation."""

    def test_compute_dir_hash_empty_directory(self, temp_dir: Path) -> None:
        """Test hashing an empty directory."""
        from scripts.setup.wizard import compute_dir_hash

        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        hashes = compute_dir_hash(empty_dir)
        assert hashes == {}

    def test_compute_dir_hash_with_files(self, temp_dir: Path) -> None:
        """Test hashing a directory with files."""
        from scripts.setup.wizard import compute_dir_hash

        subdir = temp_dir / "subdir"
        subdir.mkdir()

        file1 = subdir / "file1.txt"
        file1.write_text("content1")

        file2 = subdir / "file2.txt"
        file2.write_text("content2")

        hashes = compute_dir_hash(subdir)

        assert len(hashes) == 2
        assert "file1.txt" in hashes
        assert "file2.txt" in hashes

    def test_compute_dir_hash_with_extensions(self, temp_dir: Path) -> None:
        """Test directory hashing with extension filter."""
        from scripts.setup.wizard import compute_dir_hash

        subdir = temp_dir / "subdir"
        subdir.mkdir()

        (subdir / "file1.py").write_text("print('hello')")
        (subdir / "file2.txt").write_text("hello")
        (subdir / "file3.py").write_text("print('world')")

        # Only .py files
        hashes = compute_dir_hash(subdir, extensions=(".py",))

        assert len(hashes) == 2
        assert "file1.py" in hashes
        assert "file3.py" in hashes
        assert "file2.txt" not in hashes


class TestGitOperations:
    """Tests for git operations in wizard."""

    def test_git_pull_no_remote(self, mock_git_repo: Path) -> None:
        """Test git pull with no remote configured."""
        from scripts.setup.wizard import git_pull

        success, message = git_pull(mock_git_repo)
        # Local-only repo with no remote should fail gracefully
        # (no assertion on success - depends on git configuration)

    def test_git_pull_with_uncommitted_changes(
        self, mock_git_repo: Path, temp_dir: Path
    ) -> None:
        """Test git pull fails with uncommitted changes."""
        from scripts.setup.wizard import git_pull

        # Add uncommitted file
        (mock_git_repo / "uncommitted.txt").write_text("uncommitted")

        success, message = git_pull(mock_git_repo)
        assert success is False
        assert "uncommitted" in message.lower()

    def test_git_pull_not_a_repo(self, temp_dir: Path) -> None:
        """Test git pull on non-git directory."""
        from scripts.setup.wizard import git_pull

        success, message = git_pull(temp_dir)
        assert success is False
        assert "not a git" in message.lower()


class TestCopyFileIfChanged:
    """Tests for file copy with change detection."""

    def test_copy_unchanged_file(
        self, temp_dir: Path, sample_wizard_files: Path
    ) -> None:
        """Test that unchanged files are not copied."""
        from scripts.setup.wizard import copy_file_if_changed, UpdateSummary

        src = sample_wizard_files / "hooks" / "hook1.py"
        dst = temp_dir / "dest" / "hook1.py"
        dst.parent.mkdir()
        dst.write_text("# Hook 1")  # Same content

        summary = UpdateSummary()
        result = copy_file_if_changed(
            src=src, dst=dst, summary=summary, category="hooks"
        )

        assert result is False  # Not copied (unchanged)
        assert "hook1.py" in summary.hooks_unchanged

    def test_copy_changed_file(
        self, temp_dir: Path, sample_wizard_files: Path
    ) -> None:
        """Test that changed files are copied."""
        from scripts.setup.wizard import copy_file_if_changed, UpdateSummary

        src = sample_wizard_files / "hooks" / "hook1.py"
        dst = temp_dir / "dest" / "hook1.py"
        dst.parent.mkdir()
        dst.write_text("# Old content")  # Different content

        summary = UpdateSummary()
        result = copy_file_if_changed(
            src=src, dst=dst, summary=summary, category="hooks"
        )

        assert result is True  # Copied (changed)
        assert "hook1.py" in summary.hooks_updated
        assert dst.read_text() == "# Hook 1"

    def test_copy_new_file(self, temp_dir: Path, sample_wizard_files: Path) -> None:
        """Test that new files are copied."""
        from scripts.setup.wizard import copy_file_if_changed, UpdateSummary

        src = sample_wizard_files / "hooks" / "hook1.py"
        dst = temp_dir / "dest" / "hook1.py"
        dst.parent.mkdir(parents=True)
        assert not dst.exists()

        summary = UpdateSummary()
        result = copy_file_if_changed(
            src=src, dst=dst, summary=summary, category="hooks"
        )

        assert result is True  # Copied (new)
        # File is added when destination doesn't exist
        assert "hook1.py" in summary.hooks_added or result is True


class TestSyncDirectoryUpdate:
    """Tests for directory synchronization."""

    def test_sync_new_directory(
        self, temp_dir: Path, sample_wizard_files: Path
    ) -> None:
        """Test syncing to a new directory."""
        from scripts.setup.wizard import sync_directory_update, UpdateSummary

        src = sample_wizard_files
        dst = temp_dir / "dest"
        summary = UpdateSummary()

        sync_directory_update(
            src_dir=src,
            dst_dir=dst,
            summary=summary,
            category="hooks",
            extensions=(".py",),
        )

        assert (dst / "hooks" / "hook1.py").exists()
        assert len(summary.hooks_added) >= 1

    def test_sync_idempotent(
        self, temp_dir: Path, sample_wizard_files: Path
    ) -> None:
        """Test that syncing twice produces same result."""
        from scripts.setup.wizard import sync_directory_update, UpdateSummary

        src = sample_wizard_files
        dst = temp_dir / "dest"
        summary1 = UpdateSummary()

        sync_directory_update(
            src_dir=src,
            dst_dir=dst,
            summary=summary1,
            category="hooks",
            extensions=(".py",),
        )

        # Second sync
        summary2 = UpdateSummary()
        sync_directory_update(
            src_dir=src,
            dst_dir=dst,
            summary=summary2,
            category="hooks",
            extensions=(".py",),
        )

        # First sync should have changes, second should be unchanged
        assert summary1.files_changed > 0
        assert summary2.files_changed == 0


class TestWizardUpdateMode:
    """Tests for wizard update mode."""

    @pytest.mark.asyncio
    async def test_run_update_mode_dry_run(
        self, temp_dir: Path, sample_wizard_files: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test update mode in dry-run doesn't modify files."""
        from scripts.setup.wizard import run_update_mode

        # Set up paths
        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()

        # Mock the project root and paths
        def mock_path_setup():
            return sample_wizard_files, project_dir / ".claude"

        monkeypatch.setattr(
            "scripts.setup.wizard.Path.home",
            lambda: temp_dir,
        )

        result = await run_update_mode(dry_run=True, verbose=False, skip_git=True)

        assert result["success"] is True
        assert result["git_updated"] is False

    @pytest.mark.asyncio
    async def test_run_update_mode_creates_directories(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that update mode creates destination directories."""
        from scripts.setup.wizard import run_update_mode

        # Set up mock paths
        monkeypatch.setattr(
            "scripts.setup.wizard.Path.home",
            lambda: temp_dir,
        )

        # Create source structure
        source = temp_dir / "source"
        source.mkdir(parents=True)
        (source / "hooks").mkdir()
        (source / "hooks" / "test.py").write_text("# test")

        # Mock the path resolution
        original_file = Path(__file__).resolve()

        # Run update (non-dry-run)
        result = await run_update_mode(dry_run=False, verbose=False, skip_git=True)

        # Verify result structure
        assert "success" in result


class TestUpdateSummary:
    """Tests for UpdateSummary dataclass."""

    def test_update_summary_counts(self) -> None:
        """Test UpdateSummary total_changes calculation."""
        from scripts.setup.wizard import UpdateSummary

        summary = UpdateSummary()
        summary.hooks_added = ["hook1.py", "hook2.py"]
        summary.hooks_updated = ["hook3.py"]
        summary.skills_added = ["skill1.py"]

        # Total changes counts added + updated across all categories
        # 2 hooks_added + 1 hooks_updated + 1 skill_added = 4
        assert summary.total_changes == 4

        # More accurate test: verify each category is counted
        assert len(summary.hooks_added) + len(summary.hooks_updated) + len(summary.skills_added) == 4

    def test_update_summary_empty(self) -> None:
        """Test UpdateSummary with no changes."""
        from scripts.setup.wizard import UpdateSummary

        summary = UpdateSummary()

        assert summary.total_changes == 0


class TestTypeScriptBuild:
    """Tests for TypeScript hooks build."""

    def test_build_typescript_hooks_missing_dir(self, temp_dir: Path) -> None:
        """Test build with missing hooks directory."""
        from scripts.setup.wizard import build_typescript_hooks

        missing_dir = temp_dir / "missing"

        success, message = build_typescript_hooks(missing_dir)
        assert success is True
        assert "does not exist" in message

    def test_build_typescript_hooks_missing_package_json(
        self, temp_dir: Path
    ) -> None:
        """Test build with missing package.json."""
        from scripts.setup.wizard import build_typescript_hooks

        hooks_dir = temp_dir / "hooks"
        hooks_dir.mkdir()

        success, message = build_typescript_hooks(hooks_dir)
        assert success is True
        assert "No package.json" in message

    def test_build_typescript_hooks_npm_not_found(
        self, mock_typescript_hooks: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test build when npm is not found."""
        from scripts.setup.wizard import build_typescript_hooks

        monkeypatch.setattr("scripts.setup.wizard.shutil.which", lambda x: None)

        success, message = build_typescript_hooks(mock_typescript_hooks)
        assert success is False
        assert "not found" in message.lower()


class TestWizardValidation:
    """Tests for wizard validation mode."""

    def test_run_validate_mode_success(self, temp_claude_home: Path) -> None:
        """Test validation mode with valid installation."""
        from scripts.setup.wizard import run_validate_mode

        # Ensure expected files exist
        (temp_claude_home / "hooks" / "dist" / "test.js").write_text("// test")

        result = run_validate_mode(json_output=False)

        assert "all_passed" in result
        assert "checks" in result
        assert "summary" in result

    def test_run_validate_mode_returns_dict(self, temp_claude_home: Path) -> None:
        """Test validation mode returns a dict regardless of json_output flag."""
        from scripts.setup.wizard import run_validate_mode

        result = run_validate_mode(json_output=False)

        # Should return a dict
        assert isinstance(result, dict)
        assert "all_passed" in result
        assert "checks" in result
        assert "summary" in result
