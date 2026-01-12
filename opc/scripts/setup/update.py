#!/usr/bin/env python3
"""OPC Incremental Update Script - Pull latest and update installed components.

Updates hooks, skills, rules, agents, servers, scripts from the latest OPC repo.
Uses hash-based comparison to only copy changed files for efficiency.

USAGE:
    uv run python -m scripts.setup.update [OPTIONS]

OPTIONS:
    --dry-run      Show what would change without making changes
    --force        Skip all confirmations
    --verbose      Show detailed output
    --skip-git     Don't pull from git
    --skip-build   Don't rebuild TypeScript hooks
    --full         Run full update including uv sync, npm update, docker check
    --restart-docker   Force restart Docker PostgreSQL container
    --reindex      Force rebuild TLDR index
    --update-deps  Update Python dependencies only (uv sync)
    --update-npm   Update NPM dependencies only (npm update)
    --migrate      Run database migrations after git pull

EXAMPLES:
    uv run python -m scripts.setup.update              # Normal update
    uv run python -m scripts.setup.update --dry-run    # Preview changes
    uv run python -m scripts.setup.update --full -v    # Full update with all features
    uv run python -m scripts.setup.update --force -v   # Verbose, no prompts
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path for imports
_this_file = Path(__file__).resolve()
_project_root = _this_file.parent.parent.parent  # scripts/setup/update.py -> opc/
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from rich.console import Console
    from rich.prompt import Confirm
    from rich.table import Table
    console = Console()
except ImportError:
    class _FallbackConsole:
        def print(self, *args, **kwargs):
            text = args[0] if args else ""
            import re
            text = re.sub(r'\[.*?\]', '', str(text))
            print(text)

    console = _FallbackConsole()
    Confirm = None  # type: ignore


@dataclass
class UpdateSummary:
    """Summary of changes made during update."""
    files_new: list[str] = field(default_factory=list)
    files_updated: list[str] = field(default_factory=list)
    files_unchanged: list[str] = field(default_factory=list)
    hooks_built: bool = False
    settings_merged: bool = False
    git_updated: bool = False
    git_message: str = ""
    python_updated: bool = False
    npm_updated: bool = False
    docker_restarted: bool = False
    tldr_updated: bool = False
    tldr_reindexed: bool = False
    cache_invalidated: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.files_new or self.files_updated)


def file_hash(path: Path) -> str:
    """Get MD5 hash of file contents."""
    if not path.exists():
        return ""
    return hashlib.md5(path.read_bytes()).hexdigest()


def file_hash_hex(path: Path) -> str:
    """Get SHA256 hex hash of file contents (for stronger comparison)."""
    if not path.exists():
        return ""
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_opc_dir() -> Path:
    """Get OPC directory (where this script lives)."""
    return Path(__file__).resolve().parent.parent.parent


def get_global_claude_dir() -> Path:
    """Get global ~/.claude directory."""
    return Path.home() / ".claude"


def get_project_root() -> Path:
    """Get project root (parent of opc/ directory)."""
    return get_opc_dir().parent


def git_pull(repo_dir: Path, verbose: bool = False) -> tuple[bool, str]:
    """Pull latest from git remote.

    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, "Not a git repository"

        # Get current commit
        before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        ).stdout.strip()[:8]

        if verbose:
            console.print(f"  [dim]Current commit: {before}[/dim]")

        # Pull latest
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            if "diverged" in result.stderr.lower():
                return False, "Local changes conflict with remote. Commit or stash first."
            elif "couldn't find remote ref" in result.stderr.lower():
                return False, "No remote branch configured"
            return False, f"Git pull failed: {result.stderr[:200]}"

        # Get new commit
        after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        ).stdout.strip()[:8]

        if before == after:
            return True, "Already up to date"
        else:
            return True, f"Updated {before} -> {after}"

    except subprocess.TimeoutExpired:
        return False, "Git pull timed out"
    except FileNotFoundError:
        return False, "Git not found"
    except Exception as e:
        return False, str(e)


def compare_directories(
    source: Path,
    installed: Path,
    extensions: set[str] | None = None,
    skip_patterns: set[str] | None = None,
) -> dict:
    """Compare source and installed directories using hash-based comparison.

    Args:
        source: OPC source directory
        installed: User's installed directory
        extensions: File extensions to check (e.g., {'.ts', '.py', '.md'})
        skip_patterns: Patterns to skip (e.g., {'node_modules', 'dist', '__pycache__'})

    Returns:
        Dict with 'new', 'updated', 'unchanged' lists of relative paths
    """
    result = {"new": [], "updated": [], "unchanged": []}
    skip_patterns = skip_patterns or {'.', '__', 'node_modules', 'dist', 'target'}

    if not source.exists():
        return result

    # Build set of source file hashes for comparison
    source_hashes: dict[str, str] = {}
    for src_file in source.rglob("*"):
        if src_file.is_dir():
            continue
        if extensions and src_file.suffix not in extensions:
            continue

        rel_path = src_file.relative_to(source)

        # Skip hidden dirs, node_modules, etc.
        if any(part.startswith(tuple(skip_patterns)) for part in rel_path.parts):
            continue

        source_hashes[str(rel_path)] = file_hash(src_file)

    # Compare against installed files
    for rel_path_str, src_hash in source_hashes.items():
        inst_file = installed / rel_path_str

        if not inst_file.exists():
            result["new"].append(rel_path_str)
        elif file_hash(inst_file) != src_hash:
            result["updated"].append(rel_path_str)
        else:
            result["unchanged"].append(rel_path_str)

    return result


def copy_file(src: Path, dst: Path, verbose: bool = False) -> bool:
    """Copy file, creating parent directories as needed."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if verbose:
            console.print(f"    [dim]Copied: {dst}[/dim]")
        return True
    except Exception as e:
        if verbose:
            console.print(f"    [red]Failed: {e}[/red]")
        return False


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
# TLDR Index Rebuild
# =============================================================================

def rebuild_tldr_index(
    project_root: Path,
    force: bool = False,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Rebuild TLDR symbol index if hooks/scripts changed.

    Uses the local build_symbol_index.py script for AST-based indexing.

    Args:
        project_root: Path to project root
        force: Force reindex even if no changes detected
        verbose: Show detailed output

    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if we should reindex based on file changes
        if not force:
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

        # Use local build_symbol_index.py script
        opc_dir = project_root / "opc"
        index_script = opc_dir / "scripts" / "tldr" / "build_symbol_index.py"

        if not index_script.exists():
            return False, f"TLDR index script not found: {index_script}"

        # Run the local Python script via uv
        uv_cmd = shutil.which("uv")
        if not uv_cmd:
            return False, "uv not found"

        result = subprocess.run(
            [uv_cmd, "run", "python", str(index_script), str(project_root)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout for large projects
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
    project_root = get_project_root()
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


def build_typescript_hooks(hooks_dir: Path, verbose: bool = False) -> tuple[bool, str]:
    """Build TypeScript hooks using npm."""
    package_json = hooks_dir / "package.json"
    if not package_json.exists():
        return True, "No package.json found"

    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        return False, "npm not found"

    if verbose:
        console.print(f"  [dim]Building hooks in: {hooks_dir}[/dim]")

    try:
        # Install deps if node_modules missing
        node_modules = hooks_dir / "node_modules"
        if not node_modules.exists():
            if verbose:
                console.print("  [dim]Installing npm dependencies...[/dim]")
            result = subprocess.run(
                [npm_cmd, "install"],
                cwd=hooks_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                return False, f"npm install failed: {result.stderr[:100]}"

        # Build
        result = subprocess.run(
            [npm_cmd, "run", "build"],
            cwd=hooks_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, f"npm build failed: {result.stderr[:100]}"

        return True, "Built successfully"

    except subprocess.TimeoutExpired:
        return False, "Timed out"
    except Exception as e:
        return False, str(e)


def merge_settings_smart(
    opc_settings: Path,
    user_settings: Path,
    output_path: Path,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Smart merge of settings.json files.

    Preserves user's MCP servers, hooks, and custom settings while
    updating OPC defaults.

    Args:
        opc_settings: Path to OPC settings.json
        user_settings: Path to user's settings.json
        output_path: Path to write merged settings
        verbose: Print verbose output

    Returns:
        Tuple of (success, message)
    """
    try:
        # Load OPC settings
        if not opc_settings.exists():
            return False, "OPC settings.json not found"

        opc_config = json.loads(opc_settings.read_text())

        # Load user settings (may not exist)
        user_config = {}
        if user_settings.exists():
            try:
                user_config = json.loads(user_settings.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        merged = opc_config.copy()

        # Preserve user's mcpServers (don't overwrite custom MCPs)
        if "mcpServers" in user_config:
            if verbose:
                console.print(f"  [dim]Preserving {len(user_config['mcpServers'])} user MCP servers[/dim]")
            if "mcpServers" not in merged:
                merged["mcpServers"] = {}
            # Merge but don't overwrite user servers
            for server_name, server_config in user_config["mcpServers"].items():
                if server_name not in merged["mcpServers"]:
                    merged["mcpServers"][server_name] = server_config

        # Preserve user's hooks configuration
        if "hooks" in user_config:
            if verbose:
                console.print(f"  [dim]Preserving user hooks config[/dim]")
            if "hooks" not in merged:
                merged["hooks"] = {}
            merged["hooks"].update(user_config["hooks"])

        # Preserve any other top-level keys the user has set
        for key in user_config:
            if key not in ("mcpServers", "hooks"):
                if verbose:
                    console.print(f"  [dim]Preserving user setting: {key}[/dim]")
                merged[key] = user_config[key]

        # Write merged settings
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(merged, indent=2))

        return True, "Settings merged successfully"

    except Exception as e:
        return False, f"Settings merge failed: {e}"


def apply_updates(
    source_path: Path,
    installed_path: Path,
    file_list: list[str],
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Apply file updates from source to installed directory.

    Args:
        source_path: Source directory
        installed_path: Target directory
        file_list: List of relative file paths to copy
        dry_run: If True, simulate without making changes
        verbose: Print verbose output

    Returns:
        Number of files copied
    """
    copied = 0
    for rel_path in file_list:
        src = source_path / rel_path
        dst = installed_path / rel_path

        if dry_run:
            if verbose:
                console.print(f"  [yellow][DRY-RUN][/yellow] Would copy: {rel_path}")
        else:
            if verbose:
                console.print(f"  [dim]Copying: {rel_path}[/dim]")
            if copy_file(src, dst, verbose=verbose):
                copied += 1

    return copied


def check_tldr_update(verbose: bool = False) -> tuple[bool, str]:
    """Check if TLDR needs update and update if needed.

    Returns:
        Tuple of (updated, message)
    """
    opc_dir = get_opc_dir()

    # Check for local dev install first
    tldr_local_venv = opc_dir / "packages" / "tldr-code" / ".venv"
    tldr_local_pkg = opc_dir / "packages" / "tldr-code"

    if tldr_local_venv.exists() and (tldr_local_pkg / "pyproject.toml").exists():
        if verbose:
            console.print("  [dim]Detected local TLDR dev install[/dim]")
        # Dev install - reinstall from local source
        try:
            result = subprocess.run(
                ["uv", "pip", "install", "-e", "."],
                cwd=tldr_local_pkg,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return True, "TLDR dev install updated"
            else:
                return False, f"TLDR dev install failed: {result.stderr[:100]}"
        except Exception as e:
            return False, str(e)
    elif shutil.which("tldr"):
        # PyPI install - update from PyPI
        try:
            result = subprocess.run(
                ["uv", "pip", "install", "--upgrade", "llm-tldr"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                if "already satisfied" in result.stdout.lower():
                    return False, "TLDR already up to date"
                return True, "TLDR updated from PyPI"
            else:
                return False, f"TLDR update failed: {result.stderr[:100]}"
        except Exception as e:
            return False, str(e)
    else:
        return False, "TLDR not installed"


def print_summary(summary: UpdateSummary, verbose: bool = False) -> None:
    """Print summary of update changes."""
    console.print("\n" + "=" * 50)
    console.print("[bold]UPDATE SUMMARY[/bold]")
    print("=" * 50)

    # Git status
    if summary.git_updated:
        console.print(f"[green]Git:[/green] {summary.git_message}")
    else:
        console.print(f"[dim]Git:[/dim] {summary.git_message}")

    # File changes
    console.print(f"\nFiles:")
    if summary.files_new:
        console.print(f"  [green]+ {len(summary.files_new)} new[/green]")
        if verbose:
            for f in summary.files_new[:10]:
                console.print(f"      {f}")
            if len(summary.files_new) > 10:
                console.print(f"      ... and {len(summary.files_new) - 10} more")

    if summary.files_updated:
        console.print(f"  [yellow]~ {len(summary.files_updated)} updated[/yellow]")
        if verbose:
            for f in summary.files_updated[:10]:
                console.print(f"      {f}")
            if len(summary.files_updated) > 10:
                console.print(f"      ... and {len(summary.files_updated) - 10} more")

    if summary.files_unchanged:
        console.print(f"  [dim]- {len(summary.files_unchanged)} unchanged[/dim]")

    # Dependency updates
    console.print(f"\nDependencies:")
    if summary.python_updated:
        console.print("  [green]Python dependencies updated[/green]")
    if summary.npm_updated:
        console.print("  [green]NPM dependencies updated[/green]")

    # Docker status
    if summary.docker_restarted:
        console.print("  [green]Docker PostgreSQL restarted[/green]")

    # TLDR status
    if summary.tldr_updated:
        console.print("  [green]TLDR CLI updated[/green]")
    if summary.tldr_reindexed:
        console.print("  [green]TLDR index rebuilt[/green]")

    # Cache status
    if summary.cache_invalidated:
        console.print("  [green]Cache cleared[/green]")

    # Other actions
    console.print(f"\nOther actions:")
    if summary.hooks_built:
        console.print("  [green]Hooks rebuilt[/green]")
    if summary.settings_merged:
        console.print("  [green]Settings merged[/green]")
    if summary.errors:
        console.print(f"  [red]{len(summary.errors)} errors[/red]")
        for err in summary.errors:
            console.print(f"      {err}")

    console.print("\n" + "=" * 50)


def run_update(
    dry_run: bool = False,
    force: bool = False,
    verbose: bool = False,
    skip_git: bool = False,
    skip_build: bool = False,
    run_migrations: bool = False,
    full_update: bool = False,
    restart_docker: bool = False,
    reindex_tldr: bool = False,
    update_deps_only: bool = False,
    update_npm_only: bool = False,
) -> UpdateSummary:
    """Run the incremental update.

    Args:
        dry_run: Show what would change without making changes
        force: Skip all confirmations
        verbose: Show detailed output
        skip_git: Don't pull from git
        skip_build: Don't rebuild TypeScript hooks
        run_migrations: Run database migrations after git pull
        full_update: Run full update including uv sync, npm update, docker check
        restart_docker: Force restart Docker PostgreSQL container
        reindex_tldr: Force rebuild TLDR index
        update_deps_only: Update Python dependencies only
        update_npm_only: Update NPM dependencies only

    Returns:
        UpdateSummary with details of changes made
    """
    summary = UpdateSummary()

    if dry_run:
        console.print("[bold yellow][DRY-RUN MODE][/bold yellow]")
        console.print("[dim]No changes will be made.\n[/dim]")

    opc_dir = get_opc_dir()
    project_root = get_project_root()
    claude_dir = get_global_claude_dir()

    # Check if installed
    if not claude_dir.exists():
        console.print("[red]No ~/.claude found. Run the install wizard first:[/red]")
        console.print("  uv run python -m scripts.setup.wizard")
        summary.errors.append("~/.claude not found")
        return summary

    if verbose:
        console.print(f"[dim]OPC dir: {opc_dir}[/dim]")
        console.print(f"[dim]Claude dir: {claude_dir}[/dim]")
        console.print(f"[dim]Project root: {project_root}[/dim]")

    # Handle single-mode options
    if update_deps_only:
        console.print("\n[bold]Updating Python dependencies only...[/bold]")
        success, msg = update_python_deps(opc_dir, verbose=verbose, force=True)
        summary.python_updated = success
        console.print(f"  [{'green' if success else 'dim'}]{msg}[/{'green' if success else 'dim'}]")
        return summary

    if update_npm_only:
        console.print("\n[bold]Updating NPM dependencies only...[/bold]")
        success, msg = update_npm_deps(claude_dir / "hooks", verbose=verbose, force=True)
        summary.npm_updated = success
        console.print(f"  [{'green' if success else 'dim'}]{msg}[/{'green' if success else 'dim'}]")
        return summary

    if embeddings_only:
        console.print("\n[bold]Installing embeddings dependencies...[/bold]")
        try:
            result = subprocess.run(
                ["uv", "sync", "--extra", "embeddings"],
                cwd=opc_dir,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                console.print("  [green]OK[/green] Embeddings installed")
                # Validate
                test_result = subprocess.run(
                    ["uv", "run", "python", "-c",
                     "from sentence_transformers import SentenceTransformer; "
                     "m = SentenceTransformer('Qwen/Qwen3-Embedding-0.6B'); "
                     "print('Model loaded:', m.get_sentence_embedding_dimension(), 'dims')"],
                    cwd=opc_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if test_result.returncode == 0:
                    console.print(f"  [green]OK[/green] {test_result.stdout.strip()}")
            else:
                console.print("  [red]ERROR[/red] Embeddings install failed")
                console.print(f"       {result.stderr[:200]}")
        except Exception as e:
            console.print(f"  [red]ERROR[/red] {e}")
        return summary

    # Step 1: Git pull (unless skipped)
    console.print("\n[bold]Step 1/9: Checking git status...[/bold]")

    if skip_git:
        console.print("  [dim]Skipped (--skip-git)[/dim]")
        summary.git_message = "Skipped"
    else:
        success, msg = git_pull(project_root, verbose=verbose)
        if success:
            summary.git_updated = True
            summary.git_message = msg
            console.print(f"  [green]OK[/green] {msg}")
        else:
            summary.git_message = msg
            console.print(f"  [yellow]WARN[/yellow] {msg}")
            if not force and Confirm and not Confirm.ask("Continue anyway?", default=False):
                summary.errors.append("User cancelled due to git failure")
                return summary

    # Step 1.5: Docker PostgreSQL health check
    if full_update or restart_docker:
        console.print("\n[bold]Step 1.5/9: Checking Docker PostgreSQL...[/bold]")
        success, msg = check_docker_postgres(force_restart=restart_docker, verbose=verbose)
        if success:
            summary.docker_restarted = restart_docker or "restarted" in msg.lower()
            console.print(f"  [green]OK[/green] {msg}")
        else:
            console.print(f"  [yellow]WARN[/yellow] {msg}")
            summary.errors.append(f"Docker check: {msg}")

    # Step 1.5 (original): Run database migrations (if requested)
    if run_migrations:
        console.print("\n[bold]Step 1.5/9: Running database migrations...[/bold]")
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
                    console.print(f"  [yellow]WARN[/yellow] Migration failed: {mig_result['error']}")
                    summary.errors.append(f"Migration failed: {mig_result['error']}")
            else:
                console.print("  [dim]All migrations up to date[/dim]")
        except Exception as e:
            console.print(f"  [yellow]WARN[/yellow] Could not run migrations: {e}")
            summary.errors.append(f"Migration error: {e}")

    # Step 2: Update Python dependencies (uv sync)
    if full_update:
        console.print("\n[bold]Step 2/9: Updating Python dependencies...[/bold]")
        success, msg = update_python_deps(opc_dir, verbose=verbose)
        summary.python_updated = success
        if success:
            console.print(f"  [green]OK[/green] {msg}")
        else:
            console.print(f"  [dim]{msg}[/dim]")

        # Step 2.5: Update embeddings dependencies (sentence-transformers, torch)
        console.print("\n[bold]Step 2.5/9: Updating embeddings dependencies...[/bold]")
        try:
            result = subprocess.run(
                ["uv", "sync", "--extra", "embeddings"],
                cwd=opc_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                console.print("  [green]OK[/green] Embeddings dependencies updated")
            elif "Nothing to do" in result.stdout or "Already up to date" in result.stdout:
                console.print("  [dim]Embeddings dependencies already up to date[/dim]")
            else:
                console.print(f"  [yellow]WARN[/yellow] Embeddings update failed")
        except subprocess.TimeoutExpired:
            console.print("  [yellow]WARN[/yellow] Embeddings update timed out")
        except Exception as e:
            console.print(f"  [yellow]WARN[/yellow] Embeddings update error: {e}")

        # Step 2.6: Validate embedding models
        console.print("\n[bold]Step 2.6/9: Validating embedding models...[/bold]")
        try:
            # Test Qwen3-Embedding-0.6B
            test_result = subprocess.run(
                ["uv", "run", "python", "-c",
                 "from sentence_transformers import SentenceTransformer; "
                 "m = SentenceTransformer('Qwen/Qwen3-Embedding-0.6B'); "
                 "print('OK dim:', m.get_sentence_embedding_dimension())"],
                cwd=opc_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if test_result.returncode == 0 and "OK" in test_result.stdout:
                console.print(f"  [green]OK[/green] Qwen3-Embedding-0.6B: {test_result.stdout.strip()}")
            else:
                console.print("  [yellow]WARN[/yellow] Qwen3-Embedding-0.6B validation failed")
        except Exception as e:
            console.print(f"  [yellow]WARN[/yellow] Embedding validation error: {e}")

    # Step 3: Compare directories (hooks, skills, rules, agents, servers)
    console.print("\n[bold]Step 3/9: Comparing installed files...[/bold]")

    # Source directories are in the repo's .claude/ integration folder
    integration_source = project_root / ".claude"

    # Define what to check: (source_subdir, installed_subdir, extensions, description)
    checks = [
        ("hooks/src", claude_dir / "hooks" / "src", ".ts", "TypeScript hooks"),
        ("hooks", claude_dir / "hooks", ".sh", "Shell hooks"),
        ("skills", claude_dir / "skills", None, "Skills"),
        ("rules", claude_dir / "rules", ".md", "Rules"),
        ("agents", claude_dir / "agents", ".md", "Agents"),
        ("servers", claude_dir / "servers", None, "MCP Servers"),
    ]

    all_new: list[tuple[str, Path, Path]] = []
    all_updated: list[tuple[str, Path, Path]] = []
    ts_files_updated = False
    sh_files_updated = False
    servers_updated = False

    for subdir, installed_path, ext, desc in checks:
        source_path = integration_source / subdir
        extensions = {ext} if ext else None

        if verbose:
            console.print(f"  [dim]Checking {desc}...[/dim]")

        diff = compare_directories(source_path, installed_path, extensions)

        for f in diff["new"]:
            all_new.append((f, source_path, installed_path))
        for f in diff["updated"]:
            all_updated.append((f, source_path, installed_path))
            if f.endswith(".ts"):
                ts_files_updated = True
            elif f.endswith(".sh"):
                sh_files_updated = True
            elif desc == "MCP Servers":
                servers_updated = True

        # Show status
        status_parts = []
        if diff["new"]:
            status_parts.append(f"{len(diff['new'])} new")
        if diff["updated"]:
            status_parts.append(f"{len(diff['updated'])} updated")
        if diff["unchanged"]:
            status_parts.append(f"{len(diff['unchanged'])} unchanged")

        if status_parts:
            console.print(f"  {desc}: {', '.join(status_parts)}")
        else:
            console.print(f"  {desc}: [dim]not found in source[/dim]")

    # Step 4: Update NPM dependencies
    if full_update:
        console.print("\n[bold]Step 4/9: Updating NPM dependencies...[/bold]")
        success, msg = update_npm_deps(claude_dir / "hooks", verbose=verbose)
        summary.npm_updated = success
        if success:
            console.print(f"  [green]OK[/green] {msg}")
        else:
            console.print(f"  [dim]{msg}[/dim]")

    # Step 5: Apply file updates
    console.print("\n[bold]Step 5/9: Applying file updates...[/bold]")

    if not all_new and not all_updated:
        console.print("  [green]Everything is up to date![/green]")
    else:
        # Show summary of changes
        console.print(f"  New files: {len(all_new)}")
        console.print(f"  Updated files: {len(all_updated)}")

        if dry_run:
            if all_new:
                console.print("\n  [yellow]Would add new files:[/yellow]")
                for f, _, _ in all_new[:10]:
                    console.print(f"    + {f}")
                if len(all_new) > 10:
                    console.print(f"    ... and {len(all_new) - 10} more")

            if all_updated:
                console.print("\n  [yellow]Would update files:[/yellow]")
                for f, _, _ in all_updated[:10]:
                    console.print(f"    ~ {f}")
                if len(all_updated) > 10:
                    console.print(f"    ... and {len(all_updated) - 10} more")
        else:
            # Confirm unless force
            if not force and Confirm and not Confirm.ask("\n  Apply these updates?", default=True):
                console.print("  Cancelled.")
                summary.errors.append("User cancelled file updates")
                return summary

            # Apply new files
            if all_new:
                if verbose:
                    console.print("\n  [dim]Adding new files...[/dim]")
                for f, source_path, installed_path in all_new:
                    if dry_run:
                        if verbose:
                            console.print(f"  [yellow][DRY-RUN][/yellow] Would copy: {f}")
                    else:
                        if verbose:
                            console.print(f"  [dim]Copying: {f}[/dim]")
                        copy_file(source_path / f, installed_path / f, verbose=verbose)

            # Apply updated files
            if all_updated:
                if verbose:
                    console.print("\n  [dim]Updating existing files...[/dim]")
                for f, source_path, installed_path in all_updated:
                    if dry_run:
                        if verbose:
                            console.print(f"  [yellow][DRY-RUN][/yellow] Would update: {f}")
                    else:
                        if verbose:
                            console.print(f"  [dim]Updating: {f}[/dim]")
                        copy_file(source_path / f, installed_path / f, verbose=verbose)

        # Update summary
        summary.files_new = [f for f, _, _ in all_new]
        summary.files_updated = [f for f, _, _ in all_updated]

    # Step 6: Settings merge
    console.print("\n[bold]Step 6/9: Merging settings...[/bold]")

    opc_settings = integration_source / "settings.json"
    user_settings = claude_dir / "settings.local.json"
    output_settings = claude_dir / "settings.json"

    if opc_settings.exists():
        success, msg = merge_settings_smart(
            opc_settings, user_settings, output_settings, verbose=verbose
        )
        if success:
            summary.settings_merged = True
            console.print(f"  [green]OK[/green] {msg}")
        else:
            console.print(f"  [yellow]WARN[/yellow] {msg}")
    else:
        console.print("  [dim]No OPC settings.json found, skipping[/dim]")

    # Step 7: Update TLDR and rebuild index
    console.print("\n[bold]Step 7/9: Checking TLDR...[/bold]")

    updated, msg = check_tldr_update(verbose=verbose)
    if updated:
        summary.tldr_updated = True
        console.print(f"  [green]OK[/green] {msg}")
    else:
        console.print(f"  [dim]{msg}[/dim]")

    # Rebuild TLDR index if needed
    if reindex_tldr or servers_updated or full_update:
        console.print("\n[bold]Step 7.5/9: Rebuilding TLDR index...[/bold]")
        success, msg = rebuild_tldr_index(project_root, force=reindex_tldr, verbose=verbose)
        if success:
            summary.tldr_reindexed = success
            console.print(f"  [green]OK[/green] {msg}")
        else:
            console.print(f"  [dim]{msg}[/dim]")

    # Step 8: Cache invalidation
    if servers_updated or full_update:
        console.print("\n[bold]Step 8/9: Invalidating cache...[/bold]")
        success, msg = invalidate_cache(
            pattern="tldr" if servers_updated else None,
            verbose=verbose,
        )
        if success:
            summary.cache_invalidated = True
            console.print(f"  [green]OK[/green] {msg}")
        else:
            console.print(f"  [dim]{msg}[/dim]")

    # Step 9: Rebuild TypeScript hooks if needed
    console.print("\n[bold]Step 9/9: Rebuilding TypeScript hooks...[/bold]")

    if skip_build:
        console.print("  [dim]Skipped (--skip-build)[/dim]")
    elif ts_files_updated or sh_files_updated or not all_updated:
        hooks_dir = claude_dir / "hooks"
        if (hooks_dir / "package.json").exists():
            success, msg = build_typescript_hooks(hooks_dir, verbose=verbose)
            if success:
                summary.hooks_built = True
                console.print(f"  [green]OK[/green] {msg}")
            else:
                console.print(f"  [yellow]WARN[/yellow] {msg}")
                console.print("  You can build manually: cd ~/.claude/hooks && npm run build")
        else:
            console.print("  [dim]No hooks to build[/dim]")
    else:
        console.print("  [dim]No hook changes, skipping build[/dim]")

    # Final message
    if dry_run:
        console.print("\n[bold yellow][DRY-RUN COMPLETE][/bold yellow]")
        console.print("[dim]Run without --dry-run to apply these changes.[/dim]")
    else:
        console.print("\n[bold green]Update complete![/bold green]")

    return summary


def main() -> int:
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Incremental update for OPC integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without making changes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip all confirmations",
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
        help="Don't pull from git",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Don't rebuild TypeScript hooks",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Run database migrations after git pull",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full update including uv sync, npm update, docker check",
    )
    parser.add_argument(
        "--restart-docker",
        action="store_true",
        help="Force restart Docker PostgreSQL container",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force rebuild TLDR index",
    )
    parser.add_argument(
        "--update-deps",
        action="store_true",
        help="Update Python dependencies only (uv sync)",
    )
    parser.add_argument(
        "--update-npm",
        action="store_true",
        help="Update NPM dependencies only (npm update)",
    )
    parser.add_argument(
        "--embeddings",
        action="store_true",
        help="Install embeddings dependencies (sentence-transformers, torch)",
    )

    args = parser.parse_args()

    try:
        summary = run_update(
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
            skip_git=args.skip_git,
            skip_build=args.skip_build,
            run_migrations=args.migrate,
            full_update=args.full,
            restart_docker=args.restart_docker,
            reindex_tldr=args.reindex,
            update_deps_only=args.update_deps,
            update_npm_only=args.update_npm,
            embeddings_only=args.embeddings,
        )

        # Print summary if verbose or there were changes
        if args.verbose or (summary.has_changes and not args.dry_run):
            print_summary(summary, verbose=args.verbose)

        return 0 if not summary.errors else 1

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        return 130
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if args.verbose:
            import traceback
            console.print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
