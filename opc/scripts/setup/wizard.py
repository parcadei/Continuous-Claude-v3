#!/usr/bin/env python3
"""Setup Wizard for OPC v3.

Interactive setup wizard for configuring the Claude Continuity Kit.
Handles prerequisite checking, database configuration, API keys,
and environment file generation.

USAGE:
    # Interactive install (default)
    python -m scripts.setup.wizard

    # Update mode (pull latest, smart sync)
    python -m scripts.setup.wizard --update

    # Update with dry-run (preview changes)
    python -m scripts.setup.wizard --update --dry-run

    # Update with verbose output
    python -m scripts.setup.wizard --update --verbose

    # Force skip confirmations
    python -m scripts.setup.wizard --update --force

Or run as a standalone script:
    python scripts/setup/wizard.py --update --dry-run
"""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path for imports when run as a script
# This handles both `python -m scripts.setup.wizard` and `python scripts/setup/wizard.py`
_this_file = Path(__file__).resolve()
_project_root = _this_file.parent.parent.parent  # scripts/setup/wizard.py -> opc/
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from rich.console import Console
    from rich.markup import escape as rich_escape
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt

    console = Console()
except ImportError:
    rich_escape = lambda x: x  # No escaping needed without Rich
    # Fallback for minimal environments
    class Console:
        def print(self, *args, **kwargs):
            print(*args)

    console = Console()


# =============================================================================
# CLI Argument Parsing
# =============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Namespace with parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="OPC v3 Setup Wizard - Install or update Claude Code integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Interactive install wizard
  %(prog)s --update           # Pull latest and update integration
  %(prog)s --update --dry-run # Preview what would be updated
  %(prog)s --update -f -v     # Force update with verbose output
        """,
    )

    parser.add_argument(
        "--update",
        action="store_true",
        help="Switch from install to update mode",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be changed without making modifications",
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip all confirmations (use defaults)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output",
    )

    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Skip git pull during update (use local files only)",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full update including uv sync, npm update, docker check",
    )

    parser.add_argument(
        "--migrate-only",
        action="store_true",
        help="Run database migrations only (skip other update steps)",
    )

    parser.add_argument(
        "--docker-auto",
        action="store_true",
        help="Auto-start Docker PostgreSQL, wait for healthy, run migrations",
    )

    parser.add_argument(
        "command",
        nargs="?",
        choices=["validate"],
        help="Command to run: validate - Check installation integrity",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output validation results as JSON (use with validate command)",
    )

    return parser.parse_args()


@dataclass
class UpdateSummary:
    """Summary of what was/would be updated."""

    hooks_added: list[str] = field(default_factory=list)
    hooks_updated: list[str] = field(default_factory=list)
    hooks_unchanged: list[str] = field(default_factory=list)
    skills_added: list[str] = field(default_factory=list)
    skills_updated: list[str] = field(default_factory=list)
    skills_unchanged: list[str] = field(default_factory=list)
    rules_added: list[str] = field(default_factory=list)
    rules_updated: list[str] = field(default_factory=list)
    rules_unchanged: list[str] = field(default_factory=list)
    agents_added: list[str] = field(default_factory=list)
    agents_updated: list[str] = field(default_factory=list)
    agents_unchanged: list[str] = field(default_factory=list)
    servers_added: list[str] = field(default_factory=list)
    servers_updated: list[str] = field(default_factory=list)
    servers_unchanged: list[str] = field(default_factory=list)
    scripts_updated: list[str] = field(default_factory=list)
    scripts_unchanged: list[str] = field(default_factory=list)
    typescript_rebuilt: bool = False
    files_changed: int = 0

    @property
    def total_changes(self) -> int:
        return (
            len(self.hooks_added)
            + len(self.hooks_updated)
            + len(self.skills_added)
            + len(self.skills_updated)
            + len(self.rules_added)
            + len(self.rules_updated)
            + len(self.agents_added)
            + len(self.agents_updated)
            + len(self.servers_added)
            + len(self.servers_updated)
        )


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hex string of the file's SHA256 hash
    """
    if not file_path.exists() or not file_path.is_file():
        return ""

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def compute_dir_hash(dir_path: Path, extensions: tuple | None = None) -> dict[str, str]:
    """Compute hashes for all files in a directory.

    Args:
        dir_path: Path to the directory
        extensions: Only include files with these extensions (e.g., (".py", ".sh"))

    Returns:
        Dict mapping relative file paths to their hashes
    """
    hashes = {}

    if not dir_path.exists():
        return hashes

    for file_path in dir_path.rglob("*"):
        if file_path.is_file():
            if extensions is None or file_path.suffix in extensions:
                rel_path = str(file_path.relative_to(dir_path))
                hashes[rel_path] = compute_file_hash(file_path)

    return hashes


def git_pull(repo_path: Path) -> tuple[bool, str]:
    """Pull latest changes from git.

    Args:
        repo_path: Path to the repository

    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if it's a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, "Not a git repository"

        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return False, "Uncommitted changes - stash or commit first"

        # Fetch and pull
        console.print("  Fetching latest changes...")
        result = subprocess.run(
            ["git", "fetch"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return False, f"Git fetch failed: {result.stderr[:200]}"

        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return False, f"Git pull failed: {result.stderr[:200]}"

        return True, result.stdout.strip() or "Already up to date"

    except subprocess.TimeoutExpired:
        return False, "Git command timed out"
    except FileNotFoundError:
        return False, "Git not found in PATH"
    except Exception as e:
        return False, f"Git error: {e}"


def copy_file_if_changed(
    src: Path,
    dst: Path,
    summary: UpdateSummary,
    category: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Copy a file only if content has changed.

    Args:
        src: Source file path
        dst: Destination file path
        summary: UpdateSummary to record changes
        category: Category name for logging (e.g., "hooks")
        dry_run: If True, only show what would change
        verbose: If True, show detailed output

    Returns:
        True if file was copied, False if unchanged
    """
    src_hash = compute_file_hash(src)
    dst_hash = compute_file_hash(dst) if dst.exists() else ""

    if src_hash == dst_hash:
        if hasattr(summary, f"{category}_unchanged"):
            getattr(summary, f"{category}_unchanged").append(dst.name)
        if verbose:
            console.print(f"    [dim]Unchanged: {dst.name}[/dim]")
        return False

    # File has changed
    if not dst.parent.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        console.print(f"    [yellow]Would update: {dst.name}[/yellow]")
    else:
        if verbose:
            console.print(f"    [green]Updating: {dst.name}[/green]")
        shutil.copy2(src, dst)

    if hasattr(summary, f"{category}_updated"):
        getattr(summary, f"{category}_updated").append(dst.name)
    summary.files_changed += 1

    return True


def sync_directory_update(
    src_dir: Path,
    dst_dir: Path,
    summary: UpdateSummary,
    category: str,
    extensions: tuple | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Sync a directory using hash-based comparison.

    Only copies files that have changed, preserves user customizations.

    Args:
        src_dir: Source directory (OPC source)
        dst_dir: Destination directory (~/.claude/...)
        summary: UpdateSummary to record changes
        category: Category name for logging
        extensions: Only sync files with these extensions
        dry_run: If True, only show what would change
        verbose: If True, show detailed output
    """
    if not src_dir.exists():
        if verbose:
            console.print(f"  [dim]Source directory not found: {src_dir}[/dim]")
        return

    # Ensure destination exists
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Compute source hashes
    src_hashes = compute_dir_hash(src_dir, extensions)

    # Track which files we've processed
    processed_files = set()

    # Check each source file
    for rel_path, src_hash in src_hashes.items():
        src_file = src_dir / rel_path
        dst_file = dst_dir / rel_path
        processed_files.add(rel_path)

        if not dst_file.exists():
            # New file
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            if dry_run:
                console.print(f"    [green]Would add: {rel_path}[/green]")
            else:
                if verbose:
                    console.print(f"    [green]Adding: {rel_path}[/green]")
                shutil.copy2(src_file, dst_file)

            if hasattr(summary, f"{category}_added"):
                getattr(summary, f"{category}_added").append(rel_path)
            summary.files_changed += 1
        else:
            # File exists - compare hashes
            dst_hash = compute_file_hash(dst_file)
            if src_hash != dst_hash:
                if dry_run:
                    console.print(f"    [yellow]Would update: {rel_path}[/yellow]")
                else:
                    if verbose:
                        console.print(f"    [green]Updating: {rel_path}[/green]")
                    shutil.copy2(src_file, dst_file)

                if hasattr(summary, f"{category}_updated"):
                    getattr(summary, f"{category}_updated").append(rel_path)
                summary.files_changed += 1
            else:
                if verbose:
                    console.print(f"    [dim]Unchanged: {rel_path}[/dim]")
                if hasattr(summary, f"{category}_unchanged"):
                    getattr(summary, f"{category}_unchanged").append(rel_path)

    if verbose and not processed_files:
        console.print(f"  [dim]No files found in {src_dir}[/dim]")


def check_typescript_files_changed(hooks_dir: Path) -> bool:
    """Check if any TypeScript files have changed.

    Args:
        hooks_dir: Path to hooks directory

    Returns:
        True if any .ts files exist and may need rebuilding
    """
    if not hooks_dir.exists():
        return False

    for ts_file in hooks_dir.glob("*.ts"):
        if ts_file.exists():
            return True
    return False


# =============================================================================
# Docker Health Check
# =============================================================================

def check_docker_postgres(
    force_restart: bool = False,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Check if PostgreSQL container is running and healthy.

    Args:
        force_restart: Force restart the container
        verbose: Show detailed output

    Returns:
        Tuple of (success, message)
    """
    import time

    try:
        # Check if docker is available
        docker_cmd = shutil.which("docker")
        if not docker_cmd:
            return False, "Docker not found"

        # Check if container exists
        result = subprocess.run(
            [docker_cmd, "ps", "-a", "--filter", "name=continuous-claude-postgres", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return False, f"Docker command failed: {result.stderr[:100]}"

        container_name = result.stdout.strip()

        if not container_name:
            return False, "PostgreSQL container not found"

        # Check container status
        result = subprocess.run(
            [docker_cmd, "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return False, f"Failed to inspect container: {result.stderr[:100]}"

        status = result.stdout.strip()

        if status == "running":
            # Check if healthy
            healthy_result = subprocess.run(
                [docker_cmd, "inspect", "--format", "{{.State.Health.Status}}", container_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            healthy = healthy_result.stdout.strip() if healthy_result.returncode == 0 else "unknown"

            if healthy == "healthy" and not force_restart:
                return True, f"PostgreSQL is healthy"

            if force_restart:
                if verbose:
                    console.print("  [dim]Force restart requested, restarting container...[/dim]")
            else:
                if verbose:
                    console.print(f"  [dim]PostgreSQL status: {healthy}, restarting...[/dim]")

        elif status != "running":
            if verbose:
                console.print(f"  [dim]PostgreSQL not running (status: {status}), starting...[/dim]")

        # Restart/start the container
        if force_restart or status != "running":
            # Stop if running
            subprocess.run(
                [docker_cmd, "stop", container_name],
                capture_output=True,
                timeout=30,
            )

            # Start container
            result = subprocess.run(
                [docker_cmd, "start", container_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return False, f"Failed to start container: {result.stderr[:100]}"

            # Wait for healthy
            max_wait = 60
            waited = 0
            while waited < max_wait:
                time.sleep(2)
                waited += 2

                status_result = subprocess.run(
                    [docker_cmd, "inspect", "--format", "{{.State.Health.Status}}", container_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if status_result.returncode == 0 and status_result.stdout.strip() == "healthy":
                    return True, "PostgreSQL container restarted and healthy"

            return True, "PostgreSQL container restarted"

        return True, "PostgreSQL is healthy"

    except subprocess.TimeoutExpired:
        return False, "Docker command timed out"
    except FileNotFoundError:
        return False, "Docker not found"
    except Exception as e:
        return False, str(e)


# =============================================================================
# Python Dependencies Update
# =============================================================================

def update_python_deps(opc_dir: Path, verbose: bool = False, force: bool = False) -> tuple[bool, str]:
    """Run uv sync to update Python dependencies.

    Args:
        opc_dir: Path to opc directory
        verbose: Show detailed output
        force: Always run even if no changes detected

    Returns:
        Tuple of (success, message)
    """
    pyproject = opc_dir / "pyproject.toml"
    if not pyproject.exists():
        return False, "pyproject.toml not found"

    try:
        # Check if pyproject.toml has changed by comparing modification times
        uv_lock = opc_dir / ".uv" / "pyproject.toml"
        needs_update = force

        if not force and uv_lock.exists():
            # Check if pyproject.toml is newer than lock file
            if pyproject.stat().st_mtime > uv_lock.stat().st_mtime:
                needs_update = True

        if not needs_update:
            return False, "Dependencies already up to date"

        if verbose:
            console.print("  [dim]Updating Python dependencies...[/dim]")

        # Run uv sync
        result = subprocess.run(
            ["uv", "sync"],
            cwd=opc_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            return False, f"uv sync failed: {result.stderr[:200]}"

        # Check if anything actually changed
        if "Nothing to do" in result.stdout or "Already up to date" in result.stdout:
            return False, "Dependencies already up to date"

        return True, "Python dependencies updated"

    except subprocess.TimeoutExpired:
        return False, "uv sync timed out"
    except FileNotFoundError:
        return False, "uv not found"
    except Exception as e:
        return False, str(e)


# =============================================================================
# NPM Package Updates
# =============================================================================

def update_npm_deps(hooks_dir: Path, verbose: bool = False, force: bool = False) -> tuple[bool, str]:
    """Update npm packages before building hooks.

    Args:
        hooks_dir: Path to hooks directory
        verbose: Show detailed output
        force: Always run npm update

    Returns:
        Tuple of (success, message)
    """
    package_json = hooks_dir / "package.json"
    if not package_json.exists():
        return False, "No package.json found"

    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        return False, "npm not found"

    try:
        # Check if package.json or package-lock.json has changed
        needs_update = force
        lock_file = hooks_dir / "package-lock.json"

        if not force and lock_file.exists():
            if package_json.stat().st_mtime > lock_file.stat().st_mtime:
                needs_update = True

        if not needs_update:
            return False, "NPM dependencies already up to date"

        if verbose:
            console.print("  [dim]Updating NPM dependencies...[/dim]")

        # Run npm update
        result = subprocess.run(
            [npm_cmd, "update"],
            cwd=hooks_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            return False, f"npm update failed: {result.stderr[:200]}"

        # Check if anything changed
        if "added" in result.stdout.lower() or "updated" in result.stdout.lower():
            return True, "NPM dependencies updated"
        elif "no packages updated" in result.stdout.lower():
            return False, "NPM dependencies already up to date"

        return True, "NPM dependencies updated"

    except subprocess.TimeoutExpired:
        return False, "npm update timed out"
    except Exception as e:
        return False, str(e)


# =============================================================================
# TLDR Index Rebuild
# =============================================================================

def rebuild_tldr_index(
    project_root: Path,
    force: bool = False,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Rebuild TLDR symbol index if hooks/scripts changed.

    Args:
        project_root: Path to project root
        force: Force reindex even if no changes detected
        verbose: Show detailed output

    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if tldr is available
        tldr_cmd = shutil.which("tldr")
        if not tldr_cmd:
            return False, "tldr not found"

        # Check if we should reindex based on file changes
        if not force:
            # Check if .claude files changed (hooks, skills, agents, rules, servers)
            claude_dir = project_root / ".claude"
            if claude_dir.exists():
                last_index = project_root / ".tldr_index_timestamp"
                last_modified = 0

                for f in claude_dir.rglob("*"):
                    if f.is_file():
                        last_modified = max(last_modified, f.stat().st_mtime)

                if last_index.exists():
                    last_index_time = last_index.stat().st_mtime
                    if last_modified <= last_index_time:
                        return False, "TLDR index up to date"

        if verbose:
            console.print("  [dim]Rebuilding TLDR index...[/dim]")

        # Run tldr reindex
        result = subprocess.run(
            [tldr_cmd, "reindex"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            # Try semantic reindex as fallback
            result = subprocess.run(
                [tldr_cmd, "semantic", "reindex"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                return False, f"TLDR reindex failed: {result.stderr[:200]}"

        # Update timestamp file
        timestamp_file = project_root / ".tldr_index_timestamp"
        timestamp_file.touch()

        return True, "TLDR index rebuilt"

    except subprocess.TimeoutExpired:
        return False, "TLDR reindex timed out"
    except Exception as e:
        return False, str(e)


# =============================================================================
# Cache Invalidation
# =============================================================================

def invalidate_cache(
    pattern: str | None = None,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Clear cache directories when relevant files change.

    Args:
        pattern: Optional pattern to match specific caches to clear
        verbose: Show detailed output

    Returns:
        Tuple of (success, message)
    """
    cleared = []

    # Define cache directories to check
    cache_dirs = [
        Path.home() / ".cache" / "tldr",
        Path.home() / ".cache" / "llm-tldr",
        Path.home() / ".cache" / "tldr-code",
    ]

    # Add project-specific caches if within project
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    cache_dirs.extend([
        project_root / ".tldr_cache",
        project_root / ".tldr_index",
    ])

    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                # Only clear if pattern matches or no pattern specified
                if pattern is None or pattern.lower() in str(cache_dir).lower():
                    if verbose:
                        console.print(f"  [dim]Clearing cache: {cache_dir}[/dim]")
                    shutil.rmtree(cache_dir)
                    cleared.append(str(cache_dir))
            except Exception as e:
                if verbose:
                    console.print(f"  [yellow]Could not clear {cache_dir}: {e}[/yellow]")

    if cleared:
        return True, f"Cleared {len(cleared)} cache directory(ies)"
    else:
        return True, "No caches to clear"


def run_update_mode(
    dry_run: bool = False,
    force: bool = False,
    verbose: bool = False,
    skip_git: bool = False,
    full_update: bool = False,
) -> dict[str, Any]:
    """Run the update mode - pull latest and sync changes.

    Args:
        dry_run: If True, only preview changes
        force: If True, skip confirmations
        verbose: If True, show detailed output
        skip_git: If True, skip git pull
        full_update: Run full update including uv sync, npm update, docker check

    Returns:
        Dict with update results
    """
    result = {
        "success": False,
        "git_updated": False,
        "summary": None,
        "error": None,
    }

    summary = UpdateSummary()

    try:
        # Get paths
        script_dir = Path(__file__).parent
        opc_root = script_dir.parent.parent
        project_root = opc_root.parent
        opc_source = project_root / ".claude"
        claude_dir = Path.home() / ".claude"

        console.print(Panel.fit("[bold]OPC v3 - UPDATE MODE[/bold]", border_style="green"))
        console.print("\n[bold]Pulling latest changes...[/bold]")

        # Step 1: Pull latest from git
        if not skip_git:
            success, msg = git_pull(project_root)
            if success:
                console.print(f"  [green]OK[/green] {msg}")
                result["git_updated"] = True
            else:
                console.print(f"  [yellow]WARN[/yellow] {msg}")
                console.print("  [dim]Continuing with local files...[/dim]")
        else:
            console.print("  [dim]Skipping git pull (--skip-git)[/dim]")

        # Step 1.5: Docker PostgreSQL health check (full update mode)
        if full_update:
            console.print("\n[bold]Step 1.5/9: Checking Docker PostgreSQL...[/bold]")
            success, msg = check_docker_postgres(force_restart=False, verbose=verbose)
            if success:
                console.print(f"  [green]OK[/green] {msg}")
            else:
                console.print(f"  [yellow]WARN[/yellow] {msg}")

        # Step 2: Run database migrations
        console.print("\n[bold]Step 2/9: Running database migrations...[/bold]")
        try:
            from scripts.migrations.migration_manager import MigrationManager

            manager = MigrationManager()
            pending = manager.get_pending_migrations()

            if pending:
                console.print(f"  [bold]{len(pending)}[/bold] pending migration(s)...")
                import asyncio

                mig_result = asyncio.run(manager.apply_all())
                if mig_result["applied"]:
                    console.print(f"  [green]Applied:[/green] {', '.join(mig_result['applied'])}")
                if mig_result["skipped"]:
                    console.print(f"  [yellow]Skipped:[/yellow] {', '.join(mig_result['skipped'])}")
                if mig_result["failed"]:
                    console.print(f"  [yellow]WARN[/yellow] Some migrations failed: {mig_result['error']}")
            else:
                console.print("  [dim]All migrations up to date[/dim]")
        except Exception as e:
            console.print(f"  [yellow]WARN[/yellow] Could not run migrations: {e}")
            console.print("  [dim]Database may not be available. Continue with file sync...[/dim]")

        # Step 3: Update Python dependencies (uv sync) - full update mode
        if full_update:
            console.print("\n[bold]Step 3/9: Updating Python dependencies...[/bold]")
            success, msg = update_python_deps(opc_root, verbose=verbose)
            if success:
                console.print(f"  [green]OK[/green] {msg}")
            else:
                console.print(f"  [dim]{msg}[/dim]")

        console.print("\n[bold]Syncing integration files...[/bold]")

        # Step 4: Sync hooks
        console.print("\n  [bold]Hooks:[/bold]")
        sync_directory_update(
            opc_source / "hooks",
            claude_dir / "hooks",
            summary,
            "hooks",
            extensions=(".sh", ".ts", ".py"),
            dry_run=dry_run,
            verbose=verbose,
        )

        # Step 5: Sync skills
        console.print("\n  [bold]Skills:[/bold]")
        sync_directory_update(
            opc_source / "skills",
            claude_dir / "skills",
            summary,
            "skills",
            dry_run=dry_run,
            verbose=verbose,
        )

        # Step 6: Sync rules
        console.print("\n  [bold]Rules:[/bold]")
        sync_directory_update(
            opc_source / "rules",
            claude_dir / "rules",
            summary,
            "rules",
            extensions=(".md",),
            dry_run=dry_run,
            verbose=verbose,
        )

        # Step 7: Sync agents
        console.print("\n  [bold]Agents:[/bold]")
        sync_directory_update(
            opc_source / "agents",
            claude_dir / "agents",
            summary,
            "agents",
            extensions=(".md",),
            dry_run=dry_run,
            verbose=verbose,
        )

        # Step 8: Sync servers (MCP tool wrappers)
        console.print("\n  [bold]Servers:[/bold]")
        sync_directory_update(
            opc_source / "servers",
            claude_dir / "servers",
            summary,
            "servers",
            dry_run=dry_run,
            verbose=verbose,
        )

        # Step 9: Update NPM dependencies (npm update) - full update mode
        if full_update:
            console.print("\n[bold]Step 9/9: Updating NPM dependencies...[/bold]")
            success, msg = update_npm_deps(claude_dir / "hooks", verbose=verbose)
            if success:
                console.print(f"  [green]OK[/green] {msg}")
            else:
                console.print(f"  [dim]{msg}[/dim]")

        # Step 10: Apply file updates (settings, scripts)
        console.print("\n[bold]Step 10/9: Applying file updates...[/bold]")

        # Sync settings.json
        opc_settings = opc_source / "settings.json"
        dst_settings = claude_dir / "settings.json"
        if opc_settings.exists():
            console.print("\n  [bold]Settings:[/bold]")
            copy_file_if_changed(
                opc_settings,
                dst_settings,
                summary,
                "settings",
                dry_run=dry_run,
                verbose=verbose,
            )

        # Sync scripts/core/
        console.print("\n  [bold]Scripts (core):[/bold]")
        sync_directory_update(
            opc_root / "scripts" / "core",
            claude_dir / "scripts" / "core",
            summary,
            "scripts",
            extensions=(".py",),
            dry_run=dry_run,
            verbose=verbose,
        )

        # Sync scripts/mathlib/
        console.print("\n  [bold]Scripts (mathlib):[/bold]")
        sync_directory_update(
            opc_root / "scripts" / "mathlib",
            claude_dir / "scripts" / "mathlib",
            summary,
            "scripts",
            extensions=(".py",),
            dry_run=dry_run,
            verbose=verbose,
        )

        # Sync scripts/tldr/
        console.print("\n  [bold]Scripts (tldr):[/bold]")
        sync_directory_update(
            opc_root / "scripts" / "tldr",
            claude_dir / "scripts" / "tldr",
            summary,
            "scripts",
            extensions=(".py",),
            dry_run=dry_run,
            verbose=verbose,
        )

        # Step 11: TLDR update + index rebuild - full update mode
        if full_update:
            console.print("\n[bold]Step 11/9: Checking TLDR updates...[/bold]")
            try:
                from scripts.setup.update import check_tldr_update, rebuild_tldr_index

                updated, msg = check_tldr_update(verbose=verbose)
                if updated:
                    console.print(f"  [green]OK[/green] {msg}")
                else:
                    console.print(f"  [dim]{msg}[/dim]")

                # Rebuild index
                success, msg = rebuild_tldr_index(project_root, force=False, verbose=verbose)
                if success:
                    console.print(f"  [green]OK[/green] {msg}")
                else:
                    console.print(f"  [dim]{msg}[/dim]")
            except Exception as e:
                console.print(f"  [yellow]WARN[/yellow] TLDR update failed: {e}")

            # Invalidate cache
            console.print("\n[bold]Step 12/9: Invalidating cache...[/bold]")
            success, msg = invalidate_cache(pattern="tldr", verbose=verbose)
            if success:
                console.print(f"  [green]OK[/green] {msg}")
            else:
                console.print(f"  [dim]{msg}[/dim]")

        # Step 13: Rebuild TypeScript hooks if needed
        console.print("\n[bold]Step 13/9: Rebuilding TypeScript hooks...[/bold]")
        if check_typescript_files_changed(claude_dir / "hooks"):
            console.print("  TypeScript hooks detected...")
            if dry_run:
                console.print("  [yellow]Would rebuild TypeScript hooks[/yellow]")
            else:
                success, msg = build_typescript_hooks(claude_dir / "hooks")
                if success:
                    console.print(f"  [green]OK[/green] {msg}")
                    summary.typescript_rebuilt = True
                else:
                    console.print(f"  [yellow]WARN[/yellow] {msg}")
                    console.print("  [dim]Build manually: cd ~/.claude/hooks && npm install && npm run build[/dim]")
        else:
            console.print("  [dim]No TypeScript changes detected, skipping build[/dim]")

        # Show summary
        console.print("\n" + "=" * 60)
        console.print("[bold]Update Summary[/bold]")

        if dry_run:
            console.print("[yellow](DRY RUN - no changes made)[/yellow]")
            console.print("")

        changes = summary.total_changes
        unchanged = (
            len(summary.hooks_unchanged)
            + len(summary.skills_unchanged)
            + len(summary.rules_unchanged)
            + len(summary.agents_unchanged)
            + len(summary.servers_unchanged)
            + len(summary.scripts_unchanged)
        )

        console.print(f"  Files changed: {changes}")
        console.print(f"  Files unchanged: {unchanged}")

        if full_update:
            console.print("  [dim](Full update mode - dependencies also checked)[/dim]")

        if changes > 0:
            console.print("\n  [bold]Changed files:[/bold]")
            if summary.hooks_added:
                console.print(f"    [green]+[/green] Hooks: {', '.join(summary.hooks_added)}")
            if summary.hooks_updated:
                console.print(f"    [yellow]~[/yellow] Hooks: {', '.join(summary.hooks_updated)}")
            if summary.skills_added:
                console.print(f"    [green]+[/green] Skills: {', '.join(summary.skills_added)}")
            if summary.skills_updated:
                console.print(f"    [yellow]~[/yellow] Skills: {', '.join(summary.skills_updated)}")
            if summary.rules_added:
                console.print(f"    [green]+[/green] Rules: {', '.join(summary.rules_added)}")
            if summary.rules_updated:
                console.print(f"    [yellow]~[/yellow] Rules: {', '.join(summary.rules_updated)}")
            if summary.agents_added:
                console.print(f"    [green]+[/green] Agents: {', '.join(summary.agents_added)}")
            if summary.agents_updated:
                console.print(f"    [yellow]~[/yellow] Agents: {', '.join(summary.agents_updated)}")
            if summary.servers_added:
                console.print(f"    [green]+[/green] Servers: {', '.join(summary.servers_added)}")
            if summary.servers_updated:
                console.print(f"    [yellow]~[/yellow] Servers: {', '.join(summary.servers_updated)}")

            if summary.typescript_rebuilt:
                console.print("\n  [green]TypeScript hooks rebuilt[/green]")

        if dry_run:
            console.print("\n[bold]To apply changes, run without --dry-run:[/bold]")
            console.print("  python -m scripts.setup.wizard --update")
        else:
            console.print("\n[bold green]Update complete![/bold green]")

        result["success"] = not dry_run or changes > 0
        result["summary"] = summary

    except Exception as e:
        result["error"] = str(e)
        console.print(f"\n[red]Error during update: {e}[/red]")

    return result


# =============================================================================
# Container Runtime Detection (Docker/Podman)
# =============================================================================

# Platform-specific Docker installation commands
DOCKER_INSTALL_COMMANDS = {
    "darwin": "brew install --cask docker",
    "linux": "sudo apt-get install docker.io docker-compose",
    "win32": "winget install Docker.DockerDesktop",
}


async def check_runtime_installed(runtime: str = "docker") -> dict[str, Any]:
    """Check if a container runtime (docker or podman) is installed.

    Args:
        runtime: The runtime to check ("docker" or "podman")

    Returns:
        dict with keys:
            - installed: bool - True if runtime binary exists
            - runtime: str - The runtime name that was checked
            - version: str | None - Version string if installed
            - daemon_running: bool - True if daemon/service is responding
    """
    result = {
        "installed": False,
        "runtime": runtime,
        "version": None,
        "daemon_running": False,
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            runtime,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            result["installed"] = True
            # Parse version from output like "Docker version 24.0.5" or "podman version 4.5.0"
            version_output = stdout.decode().strip()
            if "version" in version_output.lower():
                parts = version_output.split()
                for i, part in enumerate(parts):
                    if part.lower() == "version":
                        if i + 1 < len(parts):
                            result["version"] = parts[i + 1].rstrip(",")
                            break
            result["daemon_running"] = True
        elif proc.returncode == 1:
            # Binary exists but daemon not running
            stderr_text = stderr.decode().lower()
            if "cannot connect" in stderr_text or "daemon" in stderr_text:
                result["installed"] = True
                result["daemon_running"] = False

    except FileNotFoundError:
        pass
    except Exception:
        pass

    return result


async def check_container_runtime() -> dict[str, Any]:
    """Check for Docker or Podman, preferring Docker if both exist.

    Returns:
        dict with keys:
            - installed: bool - True if any runtime is available
            - runtime: str - "docker", "podman", or None
            - version: str | None - Version string
            - daemon_running: bool - True if service is responding
    """
    # Try Docker first (most common)
    result = await check_runtime_installed("docker")
    if result["installed"]:
        return result

    # Fall back to Podman (common on Fedora/RHEL)
    result = await check_runtime_installed("podman")
    return result


# Keep old function name for backwards compatibility
async def check_docker_installed() -> dict[str, Any]:
    """Check if Docker is installed. Deprecated: use check_container_runtime()."""
    return await check_container_runtime()


def get_docker_install_command() -> str:
    """Get platform-specific Docker installation command.

    Returns:
        str: Installation command for the current platform
    """
    platform = sys.platform

    if platform in DOCKER_INSTALL_COMMANDS:
        return DOCKER_INSTALL_COMMANDS[platform]

    # Unknown platform - provide generic guidance
    return "Visit https://docker.com/get-started to download Docker for your platform"


async def offer_docker_install() -> bool:
    """Offer to show Docker/Podman installation instructions.

    Returns:
        bool: True if user wants to proceed without container runtime
    """
    install_cmd = get_docker_install_command()
    console.print("\n  [yellow]Docker or Podman is required but not installed.[/yellow]")
    console.print(f"  Install Docker with: [bold]{install_cmd}[/bold]")
    console.print("  [dim]Or on Fedora/RHEL: sudo dnf install podman podman-compose[/dim]")

    return Confirm.ask("\n  Would you like to proceed without a container runtime?", default=False)


async def check_prerequisites_with_install_offers() -> dict[str, Any]:
    """Check prerequisites and offer installation help for missing items.

    Enhanced version of check_prerequisites that offers installation
    guidance when tools are missing.

    Returns:
        dict with keys: docker, container_runtime, python, uv, elan, all_present
    """
    result = {
        "docker": False,
        "container_runtime": None,  # "docker" or "podman"
        "python": shutil.which("python3") is not None,
        "uv": shutil.which("uv") is not None,
        "elan": shutil.which("elan") is not None,  # Lean4 version manager
    }

    # Check for Docker or Podman
    runtime_info = await check_container_runtime()
    result["docker"] = runtime_info["installed"] and runtime_info.get("daemon_running", False)
    result["container_runtime"] = runtime_info.get("runtime") if runtime_info["installed"] else None
    result["docker_version"] = runtime_info.get("version")
    result["docker_daemon_running"] = runtime_info.get("daemon_running", False)

    runtime_name = runtime_info.get("runtime", "Docker")

    # Offer install if missing
    if not runtime_info["installed"]:
        await offer_docker_install()
    elif not runtime_info.get("daemon_running", False):
        console.print(f"  [yellow]{runtime_name.title()} is installed but the daemon is not running.[/yellow]")
        if runtime_name == "docker":
            console.print("  Please start Docker Desktop or the Docker service.")
        else:
            console.print("  Please start the Podman service: systemctl --user start podman.socket")

        # Retry loop for daemon startup
        max_retries = 3
        for attempt in range(max_retries):
            if Confirm.ask(f"\n  Retry checking {runtime_name} daemon? (attempt {attempt + 1}/{max_retries})", default=True):
                console.print(f"  Checking {runtime_name} daemon...")
                await asyncio.sleep(2)  # Give daemon time to start
                runtime_info = await check_runtime_installed(runtime_name)
                if runtime_info.get("daemon_running", False):
                    result["docker"] = True
                    result["docker_daemon_running"] = True
                    console.print(f"  [green]OK[/green] {runtime_name.title()} daemon is now running!")
                    break
                else:
                    console.print(f"  [yellow]{runtime_name.title()} daemon still not running.[/yellow]")
            else:
                break

    # Check elan/Lean4 (optional, for theorem proving with /prove skill)
    if not result["elan"]:
        console.print("\n  [dim]Optional: Lean4/elan not found (needed for /prove skill)[/dim]")
        console.print("  [dim]Install with: curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh[/dim]")

    # elan is optional, so exclude from all_present check
    result["all_present"] = all([result["docker"], result["python"], result["uv"]])
    return result


# =============================================================================
# Security: Sandbox Risk Acknowledgment
# =============================================================================


def acknowledge_sandbox_risk() -> bool:
    """Get user acknowledgment for running without sandbox.

    Requires user to type an exact phrase to acknowledge the security
    implications of running agent-written code without sandbox protection.

    Returns:
        bool: True if user typed the correct acknowledgment phrase
    """
    print("\n  SECURITY WARNING")
    print("  Running without sandbox means agent-written code executes with full system access.")
    print("  This is a security risk. Only proceed if you understand the implications.")
    response = input("\n  Type 'I understand the risks' to continue without sandbox: ")
    return response.strip().lower() == "i understand the risks"


# =============================================================================
# Feature Toggle Confirmation
# =============================================================================


def confirm_feature_toggle(feature: str, current: bool, new: bool) -> bool:
    """Confirm feature toggle change with user.

    Asks for explicit confirmation before changing a feature's enabled state.

    Args:
        feature: Name of the feature being toggled
        current: Current enabled state
        new: New enabled state being requested

    Returns:
        bool: True if user confirms the change
    """
    action = "enable" if new else "disable"
    response = input(f"  Are you sure you want to {action} {feature}? [y/N]: ")
    return response.strip().lower() == "y"


def build_typescript_hooks(hooks_dir: Path) -> tuple[bool, str]:
    """Build TypeScript hooks using npm.

    Args:
        hooks_dir: Path to hooks directory

    Returns:
        Tuple of (success, message)
    """
    # Check if hooks directory exists
    if not hooks_dir.exists():
        return True, "Hooks directory does not exist"

    # Check if package.json exists
    if not (hooks_dir / "package.json").exists():
        return True, "No package.json found - no npm build needed"

    # Find npm executable
    npm_cmd = shutil.which("npm")
    if npm_cmd is None:
        if platform.system() == "Windows":
            npm_cmd = shutil.which("npm.cmd")
        if npm_cmd is None:
            return False, "npm not found in PATH - TypeScript hooks will not be built"

    try:
        # Install dependencies
        console.print("  Running npm install...")
        result = subprocess.run(
            [npm_cmd, "install"],
            cwd=hooks_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return False, f"npm install failed: {result.stderr[:200]}"

        # Build
        console.print("  Running npm run build...")
        result = subprocess.run(
            [npm_cmd, "run", "build"],
            cwd=hooks_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, f"npm build failed: {result.stderr[:200]}"

        return True, "TypeScript hooks built successfully"

    except subprocess.TimeoutExpired:
        return False, "npm command timed out"
    except OSError as e:
        return False, f"Failed to run npm: {e}"


async def check_prerequisites() -> dict[str, Any]:
    """Check if required tools are installed.

    Checks for:
    - Docker (required for stack)
    - Python 3.11+ (already running if here)
    - uv package manager (required for deps)
    - elan/Lean4 (optional, for theorem proving)

    Returns:
        dict with keys: docker, python, uv, elan, all_present
    """
    result = {
        "docker": shutil.which("docker") is not None,
        "python": shutil.which("python3") is not None,
        "uv": shutil.which("uv") is not None,
        "elan": shutil.which("elan") is not None,  # Optional: Lean4 version manager
    }
    # elan is optional, so exclude from all_present check
    result["all_present"] = all([result["docker"], result["python"], result["uv"]])
    return result


async def prompt_database_config() -> dict[str, Any]:
    """Prompt user for database configuration.

    Returns:
        dict with keys: host, port, database, user
    """
    host = Prompt.ask("PostgreSQL host", default="localhost")
    port_str = Prompt.ask("PostgreSQL port", default="5432")
    database = Prompt.ask("Database name", default="continuous_claude")
    user = Prompt.ask("Database user", default="claude")

    return {
        "host": host,
        "port": int(port_str),
        "database": database,
        "user": user,
    }


async def prompt_api_keys() -> dict[str, str]:
    """Prompt user for optional API keys.

    Returns:
        dict with keys: perplexity, nia, braintrust
    """
    console.print("\n[bold]API Keys (optional)[/bold]")
    console.print("Press Enter to skip any key you don't have.\n")

    perplexity = Prompt.ask("Perplexity API key (web search)", default="")
    nia = Prompt.ask("Nia API key (documentation search)", default="")
    braintrust = Prompt.ask("Braintrust API key (observability)", default="")

    return {
        "perplexity": perplexity,
        "nia": nia,
        "braintrust": braintrust,
    }


def generate_env_file(config: dict[str, Any], env_path: Path) -> None:
    """Generate .env file from configuration.

    If env_path exists, creates a backup before overwriting.

    Args:
        config: Configuration dict with 'database' and 'api_keys' sections
        env_path: Path to write .env file
    """
    # Backup existing .env if present
    if env_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = env_path.parent / f".env.backup.{timestamp}"
        shutil.copy(env_path, backup_path)

    # Build env content
    lines = []

    # Database config
    db = config.get("database", {})
    if db:
        mode = db.get("mode", "docker")
        lines.append(f"# Database Mode: {mode}")

        if mode == "docker":
            host = db.get('host', 'localhost')
            port = db.get('port', 5432)
            database = db.get('database', 'continuous_claude')
            user = db.get('user', 'claude')
            password = db.get('password', '')
            lines.append(f"POSTGRES_HOST={host}")
            lines.append(f"POSTGRES_PORT={port}")
            lines.append(f"POSTGRES_DB={database}")
            lines.append(f"POSTGRES_USER={user}")
            if password:
                lines.append(f"POSTGRES_PASSWORD={password}")
            lines.append("")
            lines.append("# Connection string for scripts")
            lines.append(f"DATABASE_URL=postgresql://{user}:{password}@{host}:{port}/{database}")
        elif mode == "embedded":
            pgdata = db.get("pgdata", "")
            venv = db.get("venv", "")
            lines.append(f"PGSERVER_PGDATA={pgdata}")
            lines.append(f"PGSERVER_VENV={venv}")
            lines.append("")
            lines.append("# Connection string (Unix socket)")
            lines.append(f"DATABASE_URL=postgresql://postgres:@/postgres?host={pgdata}")
        else:  # sqlite
            lines.append("# SQLite mode - no DATABASE_URL needed")
            lines.append("DATABASE_URL=")
        lines.append("")

    # API keys (only write non-empty keys)
    api_keys = config.get("api_keys", {})
    if api_keys:
        has_keys = any(v for v in api_keys.values())
        if has_keys:
            lines.append("# API Keys")
            if api_keys.get("perplexity"):
                lines.append(f"PERPLEXITY_API_KEY={api_keys['perplexity']}")
            if api_keys.get("nia"):
                lines.append(f"NIA_API_KEY={api_keys['nia']}")
            if api_keys.get("braintrust"):
                lines.append(f"BRAINTRUST_API_KEY={api_keys['braintrust']}")
            lines.append("")

    # Write file
    env_path.write_text("\n".join(lines))


async def run_setup_wizard() -> None:
    """Run the interactive setup wizard.

    Orchestrates the full setup flow:
    1. Check prerequisites
    2. Prompt for database config
    3. Prompt for API keys
    4. Generate .env file
    5. Start Docker stack
    6. Run migrations
    7. Install Claude Code integration (hooks, skills, rules)
    """
    console.print(
        Panel.fit("[bold]CLAUDE CONTINUITY KIT v3 - SETUP WIZARD[/bold]", border_style="blue")
    )

    # Determine project root (opc/ directory)
    project_root = Path.cwd()

    # Step 0: Backup global ~/.claude (safety first)
    console.print("\n[bold]Step 0/12: Backing up global Claude configuration...[/bold]")
    from scripts.setup.claude_integration import (
        backup_global_claude_dir,
        get_global_claude_dir,
    )

    global_claude = get_global_claude_dir()
    if global_claude.exists():
        backup_path = backup_global_claude_dir()
        if backup_path:
            console.print(f"  [green]OK[/green] Backed up ~/.claude to {backup_path.name}")
        else:
            console.print("  [yellow]WARN[/yellow] Could not create backup")
    else:
        console.print("  [dim]No existing ~/.claude found (clean install)[/dim]")

    # Step 1: Check prerequisites (with installation offers)
    console.print("\n[bold]Step 1/12: Checking system requirements...[/bold]")
    prereqs = await check_prerequisites_with_install_offers()

    if prereqs["docker"]:
        runtime = prereqs.get("container_runtime", "docker")
        console.print(f"  [green]OK[/green] {runtime.title()}")
    # Installation guidance already shown by check_prerequisites_with_install_offers()

    if prereqs["python"]:
        console.print("  [green]OK[/green] Python 3.11+")
    else:
        console.print("  [red]MISSING[/red] Python 3.11+")

    if prereqs["uv"]:
        console.print("  [green]OK[/green] uv package manager")
    else:
        console.print(
            "  [red]MISSING[/red] uv - install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        )

    if not prereqs["all_present"]:
        console.print("\n[red]Cannot continue without all prerequisites.[/red]")
        sys.exit(1)

    # Step 2: Database config
    console.print("\n[bold]Step 2/12: Database Configuration[/bold]")
    console.print("  Choose your database backend:")
    console.print("    [bold]docker[/bold]    - PostgreSQL in Docker (recommended)")
    console.print("    [bold]embedded[/bold]  - Embedded PostgreSQL (no Docker needed)")
    console.print("    [bold]sqlite[/bold]    - SQLite fallback (simplest, no cross-terminal)")
    db_mode = Prompt.ask("\n  Database mode", choices=["docker", "embedded", "sqlite"], default="docker")

    if db_mode == "embedded":
        from scripts.setup.embedded_postgres import setup_embedded_environment
        console.print("  Setting up embedded postgres (creates Python 3.12 environment)...")
        embed_result = await setup_embedded_environment()
        if embed_result["success"]:
            console.print(f"  [green]OK[/green] Embedded environment ready at {embed_result['venv']}")
            db_config = {"mode": "embedded", "pgdata": str(embed_result["pgdata"]), "venv": str(embed_result["venv"])}
        else:
            console.print(f"  [red]ERROR[/red] {embed_result.get('error', 'Unknown')}")
            console.print("  Falling back to Docker mode")
            db_mode = "docker"

    if db_mode == "sqlite":
        db_config = {"mode": "sqlite"}
        console.print("  [yellow]Note:[/yellow] Cross-terminal coordination disabled in SQLite mode")

    if db_mode == "docker":
        console.print("  [dim]Customize host/port for containers (podman, nerdctl) or remote postgres.[/dim]")
        if Confirm.ask("Configure database connection?", default=True):
            db_config = await prompt_database_config()
            password = Prompt.ask("Database password", password=True, default="claude_dev")
            db_config["password"] = password
        else:
            db_config = {
                "host": "localhost",
                "port": 5432,
                "database": "continuous_claude",
                "user": "claude",
                "password": "claude_dev",
            }
        db_config["mode"] = "docker"

    # Step 3: API keys
    console.print("\n[bold]Step 3/12: API Keys (Optional)[/bold]")
    if Confirm.ask("Configure API keys?", default=False):
        api_keys = await prompt_api_keys()
    else:
        api_keys = {"perplexity": "", "nia": "", "braintrust": ""}

    # Step 4: Generate .env
    console.print("\n[bold]Step 4/12: Generating configuration...[/bold]")
    config = {"database": db_config, "api_keys": api_keys}
    env_path = Path.cwd() / ".env"
    generate_env_file(config, env_path)
    console.print(f"  [green]OK[/green] Generated {env_path}")

    # Step 5: Container stack (Sandbox Infrastructure)
    runtime = prereqs.get("container_runtime", "docker")
    console.print(f"\n[bold]Step 5/12: Container Stack (Sandbox Infrastructure)[/bold]")
    console.print("  The sandbox requires PostgreSQL and Redis for:")
    console.print("  - Agent coordination and scheduling")
    console.print("  - Build cache and LSP index storage")
    console.print("  - Real-time agent status")
    if Confirm.ask(f"Start {runtime} stack (PostgreSQL, Redis)?", default=True):
        from scripts.setup.docker_setup import run_migrations, set_container_runtime, start_docker_stack, wait_for_services

        # Set the detected runtime before starting
        set_container_runtime(runtime)

        console.print(f"  [dim]Starting containers (first run downloads ~500MB, may take a few minutes)...[/dim]")
        result = await start_docker_stack(env_file=env_path)
        if result["success"]:
            console.print(f"  [green]OK[/green] {runtime.title()} stack started")

            # Wait for services
            console.print("  Waiting for services to be healthy...")
            health = await wait_for_services(timeout=60)
            if health["all_healthy"]:
                console.print("  [green]OK[/green] All services healthy")
            else:
                console.print("  [yellow]WARN[/yellow] Some services may not be healthy")
        else:
            console.print(f"  [red]ERROR[/red] {result.get('error', 'Unknown error')}")
            console.print(f"  You can start manually with: {runtime} compose up -d")

    # Step 6: Migrations
    console.print("\n[bold]Step 6/12: Database Setup[/bold]")
    if Confirm.ask("Run database migrations?", default=True):
        from scripts.setup.docker_setup import run_migrations, set_container_runtime

        # Ensure runtime is set (in case step 5 was skipped)
        set_container_runtime(runtime)
        result = await run_migrations()
        if result["success"]:
            console.print("  [green]OK[/green] Migrations complete")
        else:
            console.print(f"  [red]ERROR[/red] {result.get('error', 'Unknown error')}")

    # Step 7: Memory & Embeddings
    console.print("\n[bold]Step 7/12: Memory & Embeddings[/bold]")
    console.print("  Memory features enable semantic recall of past learnings:")
    console.print("    - Store session learnings with embeddings")
    console.print("    - Recall similar past solutions (semantic search)")
    console.print("    - Cross-terminal coordination (sessions, file claims)")
    console.print("")
    console.print("  [dim]Note: sentence-transformers requires ~2GB for model download.[/dim]")

    if Confirm.ask("\nInstall memory features (embeddings)?", default=True):
        import subprocess

        # Install sentence-transformers and torch
        console.print("  Installing sentence-transformers and torch...")
        try:
            result = subprocess.run(
                ["uv", "sync", "--extra", "embeddings"],
                capture_output=True,
                text=True,
                timeout=600,  # 10 min for torch download
            )
            if result.returncode == 0:
                console.print("  [green]OK[/green] Embeddings installed")

                # Also install postgres/pgvector for storage
                console.print("  Installing pgvector for PostgreSQL storage...")
                pg_result = subprocess.run(
                    ["uv", "sync", "--extra", "postgres"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if pg_result.returncode == 0:
                    console.print("  [green]OK[/green] pgvector installed")
                else:
                    console.print("  [yellow]WARN[/yellow] pgvector install failed (optional)")

                # Verify imports and load actual Qwen3 model
                console.print("  Loading Qwen3-Embedding-0.6B model...")
                verify_result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "python",
                        "-c",
                        "from sentence_transformers import SentenceTransformer; "
                        "m = SentenceTransformer('Qwen/Qwen3-Embedding-0.6B'); "
                        "print('OK dim:', m.get_sentence_embedding_dimension())",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2 min for first model download
                )
                if verify_result.returncode == 0 and "OK" in verify_result.stdout:
                    console.print(f"  [green]OK[/green] {verify_result.stdout.strip()}")
                else:
                    console.print("  [yellow]WARN[/yellow] Model verification failed")
                    console.print(f"       {verify_result.stderr[:200]}")

                # Verify reranker model
                console.print("  Loading BAAI/bge-reranker-base model...")
                rerank_result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "python",
                        "-c",
                        "from sentence_transformers import CrossEncoder; "
                        "m = CrossEncoder('BAAI/bge-reranker-base'); "
                        "print('OK')",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if rerank_result.returncode == 0:
                    console.print("  [green]OK[/green] Reranker verified")
                else:
                    console.print("  [yellow]WARN[/yellow] Reranker verification failed (optional)")

            else:
                console.print("  [red]ERROR[/red] Installation failed")
                console.print(f"       {result.stderr[:200]}")
                console.print("  Install manually with: uv sync --extra embeddings")
        except subprocess.TimeoutExpired:
            console.print("  [yellow]WARN[/yellow] Installation timed out")
            console.print("  Install manually with: uv sync --extra embeddings")
        except Exception as e:
            console.print(f"  [red]ERROR[/red] {e}")
            console.print("  Install manually with: uv sync --extra embeddings")
    else:
        console.print("  Skipped memory features")
        console.print("  [dim]Install later with: uv sync --extra embeddings[/dim]")

    # Step 8: Claude Code Integration
    console.print("\n[bold]Step 8/12: Claude Code Integration[/bold]")
    from scripts.setup.claude_integration import (
        analyze_conflicts,
        backup_claude_dir,
        detect_existing_setup,
        generate_migration_guidance,
        get_global_claude_dir,
        get_opc_integration_source,
        install_opc_integration,
    )

    claude_dir = get_global_claude_dir()  # Use global ~/.claude, not project-local
    existing = detect_existing_setup(claude_dir)

    if existing.has_existing:
        console.print("  Found existing configuration:")
        console.print(f"    - Hooks: {len(existing.hooks)}")
        console.print(f"    - Skills: {len(existing.skills)}")
        console.print(f"    - Rules: {len(existing.rules)}")
        console.print(f"    - MCPs: {len(existing.mcps)}")

        opc_source = get_opc_integration_source()
        conflicts = analyze_conflicts(existing, opc_source)

        if conflicts.has_conflicts:
            console.print("\n  [yellow]Conflicts detected:[/yellow]")
            if conflicts.hook_conflicts:
                console.print(f"    - Hook conflicts: {', '.join(conflicts.hook_conflicts)}")
            if conflicts.skill_conflicts:
                console.print(f"    - Skill conflicts: {', '.join(conflicts.skill_conflicts)}")
            if conflicts.mcp_conflicts:
                console.print(f"    - MCP conflicts: {', '.join(conflicts.mcp_conflicts)}")

        # Show migration guidance
        guidance = generate_migration_guidance(existing, conflicts)
        console.print(f"\n{guidance}")

        # Offer choices
        console.print("\n[bold]Installation Options:[/bold]")
        console.print("  1. Full install (backup existing, install OPC, merge non-conflicting)")
        console.print("  2. Fresh install (backup existing, install OPC only)")
        console.print("  3. Skip (keep existing configuration)")

        choice = Prompt.ask("Choose option", choices=["1", "2", "3"], default="1")

        if choice in ("1", "2"):
            # Backup first
            backup_path = backup_claude_dir(claude_dir)
            if backup_path:
                console.print(f"  [green]OK[/green] Backup created: {backup_path.name}")

            # Install
            merge = choice == "1"
            result = install_opc_integration(
                claude_dir,
                opc_source,
                merge_user_items=merge,
                existing=existing if merge else None,
                conflicts=conflicts if merge else None,
            )

            if result["success"]:
                console.print(f"  [green]OK[/green] Installed {result['installed_hooks']} hooks")
                console.print(f"  [green]OK[/green] Installed {result['installed_skills']} skills")
                console.print(f"  [green]OK[/green] Installed {result['installed_rules']} rules")
                console.print(f"  [green]OK[/green] Installed {result['installed_agents']} agents")
                console.print(f"  [green]OK[/green] Installed {result['installed_servers']} MCP servers")
                if result["merged_items"]:
                    console.print(
                        f"  [green]OK[/green] Merged {len(result['merged_items'])} custom items"
                    )

                # Build TypeScript hooks
                console.print("  Building TypeScript hooks...")
                hooks_dir = claude_dir / "hooks"
                build_success, build_msg = build_typescript_hooks(hooks_dir)
                if build_success:
                    console.print(f"  [green]OK[/green] {build_msg}")
                else:
                    console.print(f"  [yellow]WARN[/yellow] {build_msg}")
                    console.print("  [dim]You can build manually: cd ~/.claude/hooks && npm install && npm run build[/dim]")
            else:
                console.print(f"  [red]ERROR[/red] {result.get('error', 'Unknown error')}")
        else:
            console.print("  Skipped integration installation")
    else:
        # Clean install
        if Confirm.ask("Install Claude Code integration (hooks, skills, rules)?", default=True):
            opc_source = get_opc_integration_source()
            result = install_opc_integration(claude_dir, opc_source)

            if result["success"]:
                console.print(f"  [green]OK[/green] Installed {result['installed_hooks']} hooks")
                console.print(f"  [green]OK[/green] Installed {result['installed_skills']} skills")
                console.print(f"  [green]OK[/green] Installed {result['installed_rules']} rules")
                console.print(f"  [green]OK[/green] Installed {result['installed_agents']} agents")
                console.print(f"  [green]OK[/green] Installed {result['installed_servers']} MCP servers")

                # Build TypeScript hooks
                console.print("  Building TypeScript hooks...")
                hooks_dir = claude_dir / "hooks"
                build_success, build_msg = build_typescript_hooks(hooks_dir)
                if build_success:
                    console.print(f"  [green]OK[/green] {build_msg}")
                else:
                    console.print(f"  [yellow]WARN[/yellow] {build_msg}")
                    console.print("  [dim]You can build manually: cd ~/.claude/hooks && npm install && npm run build[/dim]")
            else:
                console.print(f"  [red]ERROR[/red] {result.get('error', 'Unknown error')}")

    # Step 9: Math Features (Optional)
    console.print("\n[bold]Step 9/12: Math Features (Optional)[/bold]")
    console.print("  Math features include:")
    console.print("    - SymPy: symbolic algebra, calculus, equation solving")
    console.print("    - Z3: SMT solver for constraint satisfaction & proofs")
    console.print("    - Pint: unit-aware computation (meters to feet, etc.)")
    console.print("    - SciPy/NumPy: scientific computing")
    console.print("    - Lean 4: theorem proving (requires separate Lean install)")
    console.print("")
    console.print("  [dim]Note: Z3 downloads a ~35MB binary. All packages have[/dim]")
    console.print("  [dim]pre-built wheels for Windows, macOS, and Linux.[/dim]")

    if Confirm.ask("\nInstall math features?", default=False):
        console.print("  Installing math dependencies...")
        import subprocess

        try:
            result = subprocess.run(
                ["uv", "sync", "--extra", "math"],
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout for large downloads
            )
            if result.returncode == 0:
                console.print("  [green]OK[/green] Math packages installed")

                # Verify imports work
                console.print("  Verifying installation...")
                verify_result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "python",
                        "-c",
                        "import sympy; import z3; import pint; print('OK')",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if verify_result.returncode == 0 and "OK" in verify_result.stdout:
                    console.print("  [green]OK[/green] All math imports verified")
                else:
                    console.print("  [yellow]WARN[/yellow] Some imports may have issues")
                    console.print(f"       {verify_result.stderr[:200]}")
            else:
                console.print("  [red]ERROR[/red] Installation failed")
                console.print(f"       {result.stderr[:200]}")
                console.print("  You can install manually with: uv sync --extra math")
        except subprocess.TimeoutExpired:
            console.print("  [yellow]WARN[/yellow] Installation timed out")
            console.print("  You can install manually with: uv sync --extra math")
        except Exception as e:
            console.print(f"  [red]ERROR[/red] {e}")
            console.print("  You can install manually with: uv sync --extra math")
    else:
        console.print("  Skipped math features")
        console.print("  [dim]Install later with: uv sync --extra math[/dim]")

    # Step 10: TLDR Code Analysis Tool
    console.print("\n[bold]Step 10/12: TLDR Code Analysis Tool[/bold]")
    console.print("  TLDR provides token-efficient code analysis for LLMs:")
    console.print("    - 95% token savings vs reading raw files")
    console.print("    - 155x faster queries with daemon mode")
    console.print("    - Semantic search, call graphs, program slicing")
    console.print("    - Works with Python, TypeScript, Go, Rust")
    console.print("")
    console.print("  [dim]Note: First semantic search downloads ~1.3GB embedding model.[/dim]")

    # Check for local llm-tldr fork
    local_tldr_path = project_root / "packages" / "llm-tldr"
    use_local = local_tldr_path.exists() and (local_tldr_path / "pyproject.toml").exists()

    if use_local:
        console.print(f"  [green]Using local fork: {local_tldr_path}[/green]")

    if Confirm.ask("\nInstall TLDR code analysis tool?", default=True):
        console.print("  Installing TLDR...")
        import subprocess

        try:
            if use_local:
                # Install from local path using pip install -e
                result = subprocess.run(
                    ["uv", "pip", "install", "-e", str(local_tldr_path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            else:
                # Install from PyPI
                result = subprocess.run(
                    ["uv", "pip", "install", "llm-tldr"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            if result.returncode == 0:
                console.print("  [green]OK[/green] TLDR installed")

                # Verify it works
                console.print("  Verifying installation...")
                verify_result = subprocess.run(
                    ["tldr", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if verify_result.returncode == 0:
                    console.print("  [green]OK[/green] TLDR CLI available")
                    console.print("")
                    console.print("  [dim]Quick start:[/dim]")
                    console.print("    tldr tree .              # See project structure")
                    console.print("    tldr structure . --lang python  # Code overview")
                    console.print("    tldr daemon start        # Start daemon (155x faster)")

                    # Configure semantic search
                    console.print("")
                    console.print("  [bold]Semantic Search Configuration[/bold]")
                    console.print("  Natural language code search using AI embeddings.")
                    console.print("  [dim]First run downloads ~1.3GB model and indexes your codebase.[/dim]")
                    console.print("  [dim]Auto-reindexes in background when files change.[/dim]")

                    if Confirm.ask("\n  Enable semantic search?", default=True):
                        # Get threshold
                        threshold_str = Prompt.ask(
                            "  Auto-reindex after how many file changes?",
                            default="20"
                        )
                        try:
                            threshold = int(threshold_str)
                        except ValueError:
                            threshold = 20

                        # Save config to global ~/.claude/settings.json
                        settings_path = get_global_claude_dir() / "settings.json"
                        settings = {}
                        if settings_path.exists():
                            try:
                                settings = json.loads(settings_path.read_text())
                            except Exception:
                                pass

                        # Detect GPU for model selection
                        # BGE-large (1.3GB) needs GPU, MiniLM (80MB) works on CPU
                        has_gpu = False
                        try:
                            import torch
                            has_gpu = torch.cuda.is_available() or torch.backends.mps.is_available()
                        except ImportError:
                            pass  # No torch = assume no GPU

                        if has_gpu:
                            model = "bge-large-en-v1.5"
                            timeout = 600  # 10 min with GPU
                        else:
                            model = "all-MiniLM-L6-v2"
                            timeout = 300  # 5 min for small model
                            console.print("  [dim]No GPU detected, using lightweight model[/dim]")

                        settings["semantic_search"] = {
                            "enabled": True,
                            "auto_reindex_threshold": threshold,
                            "model": model,
                        }

                        settings_path.parent.mkdir(parents=True, exist_ok=True)
                        settings_path.write_text(json.dumps(settings, indent=2))
                        console.print(f"  [green]OK[/green] Semantic search enabled (threshold: {threshold})")

                        # Offer to pre-download embedding model
                        # Note: We only download the model here, not index any directory.
                        # Indexing happens per-project when user runs `tldr semantic index .`
                        if Confirm.ask("\n  Pre-download embedding model now?", default=False):
                            console.print(f"  Downloading {model} embedding model...")
                            try:
                                # Just load the model to trigger download (no indexing)
                                download_result = subprocess.run(
                                    [sys.executable, "-c", f"from tldr.semantic import get_model; get_model('{model}')"],
                                    capture_output=True,
                                    text=True,
                                    timeout=timeout,
                                    env={**os.environ, "TLDR_AUTO_DOWNLOAD": "1"},
                                )
                                if download_result.returncode == 0:
                                    console.print("  [green]OK[/green] Embedding model downloaded")
                                else:
                                    console.print("  [yellow]WARN[/yellow] Download had issues")
                                    if download_result.stderr:
                                        console.print(f"       {download_result.stderr[:200]}")
                            except subprocess.TimeoutExpired:
                                console.print("  [yellow]WARN[/yellow] Download timed out")
                            except Exception as e:
                                console.print(f"  [yellow]WARN[/yellow] {e}")
                        else:
                            console.print("  [dim]Model downloads on first use of: tldr semantic index .[/dim]")
                    else:
                        console.print("  Semantic search disabled")
                        console.print("  [dim]Enable later in .claude/settings.json[/dim]")
                else:
                    console.print("  [yellow]WARN[/yellow] TLDR installed but not on PATH")
            else:
                console.print("  [red]ERROR[/red] Installation failed")
                console.print(f"       {result.stderr[:200]}")
                if use_local:
                    console.print("  Try installing from PyPI: pip install llm-tldr")
                else:
                    console.print("  You can install manually with: pip install llm-tldr")
        except subprocess.TimeoutExpired:
            console.print("  [yellow]WARN[/yellow] Installation timed out")
            console.print("  You can install manually with: pip install llm-tldr")
        except Exception as e:
            console.print(f"  [red]ERROR[/red] {e}")
            console.print("  You can install manually with: pip install llm-tldr")
    else:
        console.print("  Skipped TLDR installation")
        console.print("  [dim]Install later with: pip install llm-tldr[/dim]")

    # Step 11: Diagnostics Tools (Shift-Left Feedback)
    console.print("\n[bold]Step 11/12: Diagnostics Tools (Shift-Left Feedback)[/bold]")
    console.print("  Claude gets immediate type/lint feedback after editing files.")
    console.print("  This catches errors before tests run (shift-left).")
    console.print("")

    # Auto-detect what's installed
    diagnostics_tools = {
        "pyright": {"cmd": "pyright", "lang": "Python", "install": "pip install pyright"},
        "ruff": {"cmd": "ruff", "lang": "Python", "install": "pip install ruff"},
        "eslint": {"cmd": "eslint", "lang": "TypeScript/JS", "install": "npm install -g eslint"},
        "tsc": {"cmd": "tsc", "lang": "TypeScript", "install": "npm install -g typescript"},
        "go": {"cmd": "go", "lang": "Go", "install": "brew install go"},
        "clippy": {"cmd": "cargo", "lang": "Rust", "install": "rustup component add clippy"},
    }

    console.print("  [bold]Detected tools:[/bold]")
    missing_tools = []
    for name, info in diagnostics_tools.items():
        if shutil.which(info["cmd"]):
            console.print(f"    [green]✓[/green] {info['lang']}: {name}")
        else:
            console.print(f"    [red]✗[/red] {info['lang']}: {name}")
            missing_tools.append((name, info))

    if missing_tools:
        console.print("")
        console.print("  [bold]Install missing tools:[/bold]")
        for name, info in missing_tools:
            console.print(f"    {name}: [dim]{info['install']}[/dim]")
    else:
        console.print("")
        console.print("  [green]All diagnostics tools available![/green]")

    console.print("")
    console.print("  [dim]Note: Currently only Python diagnostics are wired up.[/dim]")
    console.print("  [dim]TypeScript, Go, Rust coming soon.[/dim]")

    # Step 12: Loogle (Lean 4 type search for /prove skill)
    console.print("\n[bold]Step 12/12: Loogle (Lean 4 Type Search)[/bold]")
    console.print("  Loogle enables type-aware search of Mathlib theorems:")
    console.print("    - Used by /prove skill for theorem proving")
    console.print("    - Search by type signature (e.g., 'Nontrivial _ ↔ _')")
    console.print("    - Find lemmas by shape, not just name")
    console.print("")
    console.print("  [dim]Note: Requires Lean 4 (elan) and ~2GB for Mathlib index.[/dim]")

    if Confirm.ask("\nInstall Loogle for theorem proving?", default=False):
        import os
        import subprocess

        # Check elan prerequisite
        if not shutil.which("elan"):
            console.print("  [yellow]WARN[/yellow] Lean 4 (elan) not installed")
            console.print("  Install with: curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh")
            console.print("  Then re-run the wizard to install Loogle.")
        else:
            console.print("  [green]OK[/green] elan found")

            # Determine platform-appropriate install location
            if sys.platform == "win32":
                loogle_home = Path(os.environ.get("LOCALAPPDATA", "")) / "loogle"
                bin_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "bin"
            else:
                loogle_home = Path.home() / ".local" / "share" / "loogle"
                bin_dir = Path.home() / ".local" / "bin"

            # Clone or update Loogle
            if loogle_home.exists():
                console.print(f"  [dim]Loogle already exists at {loogle_home}[/dim]")
                if Confirm.ask("  Update existing installation?", default=True):
                    console.print("  Updating Loogle...")
                    result = subprocess.run(
                        ["git", "pull"],
                        cwd=loogle_home,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode == 0:
                        console.print("  [green]OK[/green] Updated")
                    else:
                        console.print(f"  [yellow]WARN[/yellow] Update failed: {result.stderr[:100]}")
            else:
                console.print(f"  Cloning Loogle to {loogle_home}...")
                loogle_home.parent.mkdir(parents=True, exist_ok=True)
                try:
                    result = subprocess.run(
                        ["git", "clone", "https://github.com/nomeata/loogle", str(loogle_home)],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode == 0:
                        console.print("  [green]OK[/green] Cloned")
                    else:
                        console.print(f"  [red]ERROR[/red] Clone failed: {result.stderr[:100]}")
                except subprocess.TimeoutExpired:
                    console.print("  [red]ERROR[/red] Clone timed out")
                except Exception as e:
                    console.print(f"  [red]ERROR[/red] {e}")

            # Build Loogle (downloads Mathlib, takes time)
            if loogle_home.exists():
                console.print("  Building Loogle (downloads Mathlib ~2GB, may take 5-10 min)...")
                console.print("  [dim]Go grab a coffee...[/dim]")
                try:
                    result = subprocess.run(
                        ["lake", "build"],
                        cwd=loogle_home,
                        capture_output=True,
                        text=True,
                        timeout=1200,  # 20 min
                    )
                    if result.returncode == 0:
                        console.print("  [green]OK[/green] Loogle built")
                    else:
                        console.print(f"  [red]ERROR[/red] Build failed")
                        console.print(f"       {result.stderr[:200]}")
                        console.print("  You can build manually: cd ~/.local/share/loogle && lake build")
                except subprocess.TimeoutExpired:
                    console.print("  [yellow]WARN[/yellow] Build timed out (this is normal for first build)")
                    console.print("  Continue building manually: cd ~/.local/share/loogle && lake build")
                except Exception as e:
                    console.print(f"  [red]ERROR[/red] {e}")

            # Set LOOGLE_HOME environment variable
            console.print("  Setting LOOGLE_HOME environment variable...")
            shell_config = None
            shell = os.environ.get("SHELL", "")
            if "zsh" in shell:
                shell_config = Path.home() / ".zshrc"
            elif "bash" in shell:
                shell_config = Path.home() / ".bashrc"
            elif sys.platform == "win32":
                shell_config = None  # Windows uses different mechanism

            if shell_config and shell_config.exists():
                content = shell_config.read_text()
                export_line = f'export LOOGLE_HOME="{loogle_home}"'
                if "LOOGLE_HOME" not in content:
                    with open(shell_config, "a") as f:
                        f.write(f"\n# Loogle (Lean 4 type search)\n{export_line}\n")
                    console.print(f"  [green]OK[/green] Added LOOGLE_HOME to {shell_config.name}")
                else:
                    console.print(f"  [dim]LOOGLE_HOME already in {shell_config.name}[/dim]")
            elif sys.platform == "win32":
                console.print(f"  [yellow]NOTE[/yellow] Add to your environment:")
                console.print(f"       set LOOGLE_HOME={loogle_home}")
            else:
                console.print(f"  [yellow]NOTE[/yellow] Add to your shell config:")
                console.print(f'       export LOOGLE_HOME="{loogle_home}"')

            # Install loogle-search script
            console.print("  Installing loogle-search CLI...")
            bin_dir.mkdir(parents=True, exist_ok=True)
            src_script = Path.cwd() / "opc" / "scripts" / "loogle_search.py"
            dst_script = bin_dir / "loogle-search"

            if src_script.exists():
                shutil.copy(src_script, dst_script)
                dst_script.chmod(0o755)
                console.print(f"  [green]OK[/green] Installed to {dst_script}")

                # Also copy server script
                src_server = Path.cwd() / "opc" / "scripts" / "loogle_server.py"
                if src_server.exists():
                    dst_server = bin_dir / "loogle-server"
                    shutil.copy(src_server, dst_server)
                    dst_server.chmod(0o755)
                    console.print(f"  [green]OK[/green] Installed loogle-server")
            else:
                console.print(f"  [yellow]WARN[/yellow] loogle_search.py not found at {src_script}")

            console.print("")
            console.print('  [dim]Usage: loogle-search "Nontrivial _ ↔ _"[/dim]')
            console.print("  [dim]Or use /prove skill which calls it automatically[/dim]")
    else:
        console.print("  Skipped Loogle installation")
        console.print("  [dim]Install later by re-running the wizard[/dim]")

    # Done!
    console.print("\n" + "=" * 60)
    console.print("[bold green]Setup complete![/bold green]")
    console.print("\nTLDR commands:")
    console.print("  [bold]tldr tree .[/bold]       - See project structure")
    console.print("  [bold]tldr daemon start[/bold] - Start daemon (155x faster)")
    console.print("  [bold]tldr --help[/bold]       - See all commands")
    console.print("\nNext steps:")
    console.print("  1. Start Claude Code: [bold]claude[/bold]")
    console.print("  2. View docs: [bold]docs/QUICKSTART.md[/bold]")


def run_validate_mode(json_output: bool = False) -> dict:
    """Run validation checks on the installation.

    Args:
        json_output: If True, output results as JSON

    Returns:
        dict with validation results
    """
    from scripts.setup.claude_integration import get_global_claude_dir

    if not json_output:
        console.print("\n[bold]OPC v3 - VALIDATION MODE[/bold]\n")

    claude_dir = get_global_claude_dir()
    results = {
        "all_passed": True,
        "checks": [],
        "summary": {"passed": 0, "failed": 0, "warnings": 0},
    }

    # Helper to run a validation check
    def check(name: str, condition: bool, details: str = "") -> bool:
        status = "PASS" if condition else "FAIL"
        if not condition:
            results["all_passed"] = False
            results["summary"]["failed"] += 1
        else:
            results["summary"]["passed"] += 1

        check_result = {"name": name, "status": status, "details": details}
        results["checks"].append(check_result)

        if json_output:
            return condition

        if condition:
            console.print(f"  [green]✓[/green] {name}")
        else:
            console.print(f"  [red]✗[/green] {name}")
            if details:
                console.print(f"      [yellow]{details}[/yellow]")
        return condition

    # Check 1: Directory exists
    check("Global .claude directory exists", claude_dir.exists(),
          str(claude_dir))

    if not claude_dir.exists():
        console.print("  [red]Cannot continue - ~/.claude/ not found[/red]")
        return results

    # Check 2: settings.json exists and is valid
    settings_path = claude_dir / "settings.json"
    settings_valid = False
    settings_content = None
    if settings_path.exists():
        try:
            settings_content = json.loads(settings_path.read_text())
            settings_valid = True
        except json.JSONDecodeError as e:
            pass
    check("settings.json is valid JSON", settings_valid, str(settings_path))

    # Check 3: hooks/dist directory exists
    hooks_dist = claude_dir / "hooks" / "dist"
    check("hooks/dist directory exists", hooks_dist.exists())

    # Check 4: Built hooks exist
    hook_count = 0
    if hooks_dist.exists():
        hook_count = len(list(hooks_dist.glob("*.mjs")))
    check(f"Built hooks present ({hook_count} files)", hook_count > 0,
          f"Found {hook_count} hook files")

    # Check 5: skills directory has content
    skills_dir = claude_dir / "skills"
    skill_count = 0
    if skills_dir.exists():
        skill_count = len([d for d in skills_dir.iterdir() if d.is_dir()])
    check(f"Skills installed ({skill_count} skills)", skill_count > 0,
          f"Found {skill_count} skill directories")

    # Check 6: rules directory has content
    rules_dir = claude_dir / "rules"
    rule_count = 0
    if rules_dir.exists():
        rule_count = len(list(rules_dir.glob("*.md")))
    check(f"Rules installed ({rule_count} rules)", rule_count > 0,
          f"Found {rule_count} rule files")

    # Check 7: agents directory has content
    agents_dir = claude_dir / "agents"
    agent_count = 0
    if agents_dir.exists():
        agent_count = len(list(agents_dir.glob("*.md")))
    check(f"Agents installed ({agent_count} agents)", agent_count > 0,
          f"Found {agent_count} agent files")

    # Check 8: Scripts are executable
    scripts_dir = claude_dir / "scripts"
    if scripts_dir.exists():
        shell_scripts = list(scripts_dir.rglob("*.sh"))
        non_executable = [s for s in shell_scripts if not (s.stat().st_mode & 0o111)]
        check(f"All shell scripts executable ({len(shell_scripts)} scripts)",
              len(non_executable) == 0,
              f"{len(non_executable)} non-executable" if non_executable else "")

    # Check 9: MCP config
    mcp_path = claude_dir / "mcp_config.json"
    mcp_valid = False
    if mcp_path.exists():
        try:
            mcp_content = json.loads(mcp_path.read_text())
            mcp_valid = "mcpServers" in mcp_content
        except json.JSONDecodeError:
            pass
    check("mcp_config.json is valid", mcp_valid or not mcp_path.exists(),
          str(mcp_path) if mcp_path.exists() else "(not found - optional)")

    # Print summary
    if not json_output:
        console.print(f"\n{'=' * 60}")
        console.print(f"[bold]Validation Summary[/bold]")
        console.print(f"  Passed: {results['summary']['passed']}")
        console.print(f"  Failed: {results['summary']['failed']}")
        if results["all_passed"]:
            console.print("  [green]All checks passed![/green]")
        else:
            console.print("  [red]Some checks failed - review above[/red]")
    else:
        import json as json_mod
        console.print(json_mod.dumps(results, indent=2))

    return results


def run_migration_mode(verbose: bool = False) -> dict[str, Any]:
    """Run database migrations only (for --migrate-only mode).

    Args:
        verbose: If True, show detailed output

    Returns:
        Dict with migration results
    """
    try:
        from scripts.migrations.migration_manager import MigrationManager

        console.print(Panel.fit("[bold]OPC v3 - DATABASE MIGRATIONS[/bold]", border_style="green"))

        console.print("\n[bold]Discovering migrations...[/bold]")

        manager = MigrationManager()
        migrations = manager.get_migrations()

        if not migrations:
            console.print("  [yellow]No migration files found[/yellow]")
            return {"success": True, "applied": [], "skipped": [], "message": "No migrations found"}

        console.print(f"  Found {len(migrations)} migration(s)")

        # Get pending migrations
        pending = manager.get_pending_migrations()
        console.print(f"  [bold]{len(pending)}[/bold] pending migration(s)")

        if pending:
            console.print("\n[bold]Applying migrations...[/bold]")
        else:
            console.print("\n[bold]All migrations already applied[/bold]")

        # Run migrations
        import asyncio

        result = asyncio.run(manager.apply_all())

        # Show results
        if result["applied"]:
            console.print(f"  [green]Applied:[/green] {', '.join(result['applied'])}")

        if result["skipped"]:
            console.print(f"  [yellow]Skipped (already applied):[/yellow] {', '.join(result['skipped'])}")

        if result["failed"]:
            for failure in result["failed"]:
                console.print(f"  [red]Failed:[/red] {failure['migration_id']} - {failure['error']}")
            return {"success": False, "error": result["error"]}

        console.print("\n[bold green]All migrations completed successfully![/bold green]")
        return result

    except ImportError as e:
        console.print(f"\n[red]Error importing migration module: {e}[/red]")
        console.print("  Make sure the migration framework is installed.")
        return {"success": False, "error": str(e)}
    except Exception as e:
        console.print(f"\n[red]Migration error: {e}[/red]")
        return {"success": False, "error": str(e)}


async def main():
    """Entry point for the setup wizard."""
    args = parse_args()

    if args.command == "validate":
        # Run validation mode
        from scripts.setup.claude_integration import get_global_claude_dir
        result = run_validate_mode(
            json_output=args.json,
        )
        sys.exit(0 if result["all_passed"] else 1)

    elif args.update:
        # Run update mode (synchronous, no async needed)
        result = run_update_mode(
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
            skip_git=args.skip_git,
            full_update=args.full,
        )
        if not result["success"]:
            sys.exit(1)

    elif args.migrate_only:
        # Run migrations only (synchronous)
        result = run_migration_mode(verbose=args.verbose)
        if not result["success"]:
            sys.exit(1)

    elif args.docker_auto:
        # Run Docker auto-connect mode
        from scripts.integration.docker_auto_connect import auto_connect

        console.print(
            Panel.fit("[bold]OPC v3 - DOCKER AUTO-CONNECT[/bold]", border_style="green")
        )

        status = await auto_connect(
            start_if_stopped=True,
            wait_for_healthy=True,
            run_migrations_flag=True,
            set_env=True,
            verbose=True,
        )

        if status.database_reachable:
            console.print("\n[bold green]PostgreSQL is ready![/bold green]")
            sys.exit(0)
        else:
            console.print(f"\n[red]ERROR[/red] {status.error or 'PostgreSQL not available'}")
            sys.exit(1)

    else:
        # Run interactive install wizard
        try:
            await run_setup_wizard()
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Setup cancelled.[/yellow]")
            sys.exit(130)
        except Exception as e:
            console.print(f"\n[red]Error: {rich_escape(str(e))}[/red]")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
