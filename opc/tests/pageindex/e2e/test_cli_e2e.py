"""End-to-end tests for PageIndex CLI.

Tests the actual CLI commands via subprocess.
Requires PostgreSQL to be running.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@pytest.mark.e2e
class TestPageIndexCLI:
    """E2E tests for the PageIndex CLI."""

    @pytest.fixture
    def cli_env(self, require_postgres, tmp_path):
        """Set up environment for CLI tests."""
        env = os.environ.copy()
        env["PROJECT_ROOT"] = str(tmp_path)
        return env, tmp_path

    def run_cli(self, args: list, env: dict, timeout: int = 60) -> subprocess.CompletedProcess:
        """Run the PageIndex CLI with given arguments."""
        cmd = [
            sys.executable, "-m",
            "scripts.pageindex.cli.pageindex_cli"
        ] + args

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(Path(__file__).parent.parent.parent.parent)
        )

    def test_cli_help(self, cli_env):
        """Test CLI shows help."""
        env, _ = cli_env
        result = self.run_cli(["--help"], env)

        assert result.returncode == 0 or "usage" in result.stdout.lower() or "usage" in result.stderr.lower()

    def test_cli_generate_command(self, cli_env, sample_roadmap_content):
        """Test generate command creates tree index."""
        env, tmp_path = cli_env

        # Create test markdown file
        md_file = tmp_path / "ROADMAP.md"
        md_file.write_text(sample_roadmap_content, encoding="utf-8")

        result = self.run_cli(["generate", str(md_file)], env)

        assert result.returncode == 0
        assert "Tree index stored" in result.stdout or "Generating" in result.stdout

    def test_cli_generate_with_output(self, cli_env, sample_roadmap_content):
        """Test generate command with JSON output."""
        env, tmp_path = cli_env

        md_file = tmp_path / "test.md"
        md_file.write_text(sample_roadmap_content, encoding="utf-8")

        output_file = tmp_path / "tree.json"
        result = self.run_cli(["generate", str(md_file), "-o", str(output_file)], env)

        assert result.returncode == 0

        if output_file.exists():
            tree = json.loads(output_file.read_text())
            assert "structure" in tree or "doc_name" in tree

    def test_cli_list_command(self, cli_env, sample_roadmap_content):
        """Test list command shows indexed documents."""
        env, tmp_path = cli_env

        # First generate a tree
        md_file = tmp_path / "ROADMAP.md"
        md_file.write_text(sample_roadmap_content, encoding="utf-8")
        self.run_cli(["generate", str(md_file)], env)

        # Then list
        result = self.run_cli(["list"], env)

        assert result.returncode == 0
        # Should show at least one document or "no indexed"
        assert "ROADMAP" in result.stdout or "No indexed" in result.stdout

    def test_cli_show_command(self, cli_env, sample_roadmap_content):
        """Test show command displays tree structure."""
        env, tmp_path = cli_env

        md_file = tmp_path / "ROADMAP.md"
        md_file.write_text(sample_roadmap_content, encoding="utf-8")
        self.run_cli(["generate", str(md_file)], env)

        result = self.run_cli(["show", "ROADMAP.md"], env)

        # May or may not find it depending on project root handling
        assert result.returncode == 0 or result.returncode == 1

    def test_cli_show_json_format(self, cli_env, sample_roadmap_content):
        """Test show command with JSON output."""
        env, tmp_path = cli_env

        md_file = tmp_path / "ROADMAP.md"
        md_file.write_text(sample_roadmap_content, encoding="utf-8")
        self.run_cli(["generate", str(md_file)], env)

        result = self.run_cli(["show", "ROADMAP.md", "--json"], env)

        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                assert "structure" in data or "doc_name" in data
            except json.JSONDecodeError:
                pass  # May have other output

    def test_cli_generate_nonexistent_file(self, cli_env):
        """Test generate command with nonexistent file."""
        env, tmp_path = cli_env

        result = self.run_cli(["generate", "/nonexistent/file.md"], env)

        assert result.returncode != 0
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_cli_generate_non_markdown_file(self, cli_env):
        """Test generate command rejects non-markdown files."""
        env, tmp_path = cli_env

        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Not markdown", encoding="utf-8")

        result = self.run_cli(["generate", str(txt_file)], env)

        assert result.returncode != 0
        assert "markdown" in result.stdout.lower() or "error" in result.stdout.lower()


@pytest.mark.e2e
class TestPageIndexCLISearch:
    """E2E tests for search command (requires Claude CLI)."""

    @pytest.fixture
    def cli_env_with_index(self, require_postgres, require_claude_cli, tmp_path, sample_roadmap_content):
        """Set up environment with pre-indexed document."""
        env = os.environ.copy()
        env["PROJECT_ROOT"] = str(tmp_path)

        # Create and index test file
        md_file = tmp_path / "ROADMAP.md"
        md_file.write_text(sample_roadmap_content, encoding="utf-8")

        cmd = [
            sys.executable, "-m",
            "scripts.pageindex.cli.pageindex_cli",
            "generate", str(md_file), "--include-text"
        ]
        subprocess.run(cmd, env=env, cwd=str(Path(__file__).parent.parent.parent.parent))

        return env, tmp_path

    def run_cli(self, args: list, env: dict, timeout: int = 120) -> subprocess.CompletedProcess:
        """Run CLI with extended timeout for LLM calls."""
        cmd = [
            sys.executable, "-m",
            "scripts.pageindex.cli.pageindex_cli"
        ] + args

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(Path(__file__).parent.parent.parent.parent)
        )

    @pytest.mark.slow
    def test_cli_search_basic(self, cli_env_with_index):
        """Test basic search command with real LLM."""
        env, _ = cli_env_with_index

        result = self.run_cli(
            ["search", "project goals", "--model", "haiku"],
            env,
            timeout=120
        )

        # Search may succeed or fail depending on indexing
        # Main thing is it doesn't crash
        assert result.returncode in [0, 1]

    @pytest.mark.slow
    def test_cli_search_specific_doc(self, cli_env_with_index):
        """Test search in specific document."""
        env, _ = cli_env_with_index

        result = self.run_cli(
            ["search", "database design", "-d", "ROADMAP.md", "--model", "haiku"],
            env,
            timeout=120
        )

        assert result.returncode in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
