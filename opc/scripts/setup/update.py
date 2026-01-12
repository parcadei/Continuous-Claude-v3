#!/usr/bin/env python3
"""OPC Incremental Update Script - Pull latest and update installed components.

Updates hooks, skills, rules, agents, and scripts from the latest OPC repo.
Uses hash-based comparison to only copy changed files for efficiency.

USAGE:
    uv run python -m scripts.setup.update [OPTIONS]

OPTIONS:
    --dry-run      Show what would change without making changes
    --force        Skip all confirmations
    --verbose      Show detailed output
    --skip-git     Don't pull from git
    --skip-build   Don't rebuild TypeScript hooks

EXAMPLES:
    uv run python -m scripts.setup.update              # Normal update
    uv run python -m scripts.setup.update --dry-run    # Preview changes
    uv run python -m scripts.setup.update --force -v   # Verbose, no prompts
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
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

    Preserves user MCP servers, hooks, and custom settings while
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
) -> UpdateSummary:
    """Run the incremental update.

    Args:
        dry_run: Show what would change without making changes
        force: Skip all confirmations
        verbose: Show detailed output
        skip_git: Don't pull from git
        skip_build: Don't rebuild TypeScript hooks

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

    # Step 1: Git pull (unless skipped)
    console.print("\n[bold]Step 1/6: Checking git status...[/bold]")

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

    # Step 2: Compare directories
    console.print("\n[bold]Step 2/6: Comparing installed files...[/bold]")

    # Source directories are in the repo's .claude/ integration folder
    integration_source = project_root / ".claude"

    # Define what to check: (source_subdir, installed_subdir, extensions, description)
    checks = [
        ("hooks/src", claude_dir / "hooks" / "src", ".ts", "TypeScript hooks"),
        ("hooks", claude_dir / "hooks", ".sh", "Shell hooks"),
        ("skills", claude_dir / "skills", None, "Skills"),
        ("rules", claude_dir / "rules", ".md", "Rules"),
        ("agents", claude_dir / "agents", ".md", "Agents"),
    ]

    all_new: list[tuple[str, Path, Path]] = []
    all_updated: list[tuple[str, Path, Path]] = []
    ts_files_updated = False
    sh_files_updated = False

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

    # Step 3: Settings merge
    console.print("\n[bold]Step 3/6: Merging settings...[/bold]")

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

    # Step 4: Apply file updates
    console.print("\n[bold]Step 4/6: Applying file updates...[/bold]")

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

    # Step 5: Update TLDR
    console.print("\n[bold]Step 5/6: Checking TLDR...[/bold]")

    updated, msg = check_tldr_update(verbose=verbose)
    if updated:
        console.print(f"  [green]OK[/green] {msg}")
    else:
        console.print(f"  [dim]{msg}[/dim]")

    # Step 6: Rebuild TypeScript hooks if needed
    console.print("\n[bold]Step 6/6: Rebuilding TypeScript hooks...[/bold]")

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

    args = parser.parse_args()

    try:
        summary = run_update(
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
            skip_git=args.skip_git,
            skip_build=args.skip_build,
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
