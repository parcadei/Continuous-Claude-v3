#!/usr/bin/env python3
"""Continuous Claude v3 Updater/Installer.

Cross-platform script that installs or updates Continuous Claude v3 components
to the global ~/.claude directory while preserving user-specific data.

USAGE:
    python -m scripts.setup.update_claude [OPTIONS]
    python opc/scripts/setup/update_claude.py [OPTIONS]

OPTIONS:
    --dry-run    Show what would be done without making changes
    --force      Skip confirmation prompts
    --no-build   Skip npm build step for TypeScript hooks
    --help       Show this help message

Works on: Windows, macOS, Linux
"""

from __future__ import annotations

import argparse
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

# Handle imports for both module and standalone execution
try:
    # When run as: python -m scripts.setup.update_claude (from opc/)
    from scripts.setup.claude_integration import (
        ConflictReport,
        ExistingSetup,
        analyze_conflicts,
        backup_global_claude_dir,
        detect_existing_setup,
        get_global_claude_dir,
    )
    _IMPORTS_AVAILABLE = True
except ImportError:
    # When run standalone, define minimal required types/functions inline
    _IMPORTS_AVAILABLE = False

    @dataclass
    class ExistingSetup:
        """Detected existing Claude Code configuration."""
        hooks: list[Path] = field(default_factory=list)
        skills: list[Path] = field(default_factory=list)
        rules: list[Path] = field(default_factory=list)
        mcps: dict[str, Any] = field(default_factory=dict)
        settings_json: dict[str, Any] | None = None
        claude_dir: Path | None = None

        @property
        def has_existing(self) -> bool:
            return bool(self.hooks or self.skills or self.rules or self.mcps)

    @dataclass
    class ConflictReport:
        """Analysis of conflicts between user config and OPC."""
        hook_conflicts: list[str] = field(default_factory=list)
        skill_conflicts: list[str] = field(default_factory=list)
        rule_conflicts: list[str] = field(default_factory=list)
        mcp_conflicts: list[str] = field(default_factory=list)
        mergeable_hooks: list[str] = field(default_factory=list)
        mergeable_skills: list[str] = field(default_factory=list)
        mergeable_rules: list[str] = field(default_factory=list)
        mergeable_mcps: list[str] = field(default_factory=list)

        @property
        def has_conflicts(self) -> bool:
            return bool(
                self.hook_conflicts or self.skill_conflicts
                or self.rule_conflicts or self.mcp_conflicts
            )

    def get_global_claude_dir() -> Path:
        """Get the global ~/.claude directory path."""
        return Path.home() / ".claude"

    def detect_existing_setup(claude_dir: Path) -> ExistingSetup:
        """Detect existing Claude Code configuration."""
        setup = ExistingSetup(claude_dir=claude_dir)
        if not claude_dir.exists():
            return setup

        hooks_dir = claude_dir / "hooks"
        if hooks_dir.exists():
            setup.hooks = [
                f for f in hooks_dir.iterdir()
                if f.is_file() and f.suffix in (".sh", ".ts", ".py")
            ]

        skills_dir = claude_dir / "skills"
        if skills_dir.exists():
            setup.skills = [
                d for d in skills_dir.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            ]

        rules_dir = claude_dir / "rules"
        if rules_dir.exists():
            setup.rules = [
                f for f in rules_dir.iterdir()
                if f.is_file() and f.suffix == ".md"
            ]

        settings_path = claude_dir / "settings.json"
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                setup.settings_json = settings
                if "mcpServers" in settings:
                    setup.mcps = settings["mcpServers"]
            except (json.JSONDecodeError, OSError):
                pass

        return setup

    def analyze_conflicts(existing: ExistingSetup, opc_source: Path) -> ConflictReport:
        """Analyze conflicts between existing config and OPC."""
        report = ConflictReport()

        opc_hooks_dir = opc_source / "hooks"
        opc_hook_names = set()
        if opc_hooks_dir.exists():
            opc_hook_names = {
                f.name for f in opc_hooks_dir.iterdir()
                if f.is_file() and f.suffix in (".sh", ".ts", ".py")
            }

        for hook in existing.hooks:
            if hook.name in opc_hook_names:
                report.hook_conflicts.append(hook.name)
            else:
                report.mergeable_hooks.append(hook.name)

        opc_skills_dir = opc_source / "skills"
        opc_skill_names = set()
        if opc_skills_dir.exists():
            opc_skill_names = {d.name for d in opc_skills_dir.iterdir() if d.is_dir()}

        for skill in existing.skills:
            if skill.name in opc_skill_names:
                report.skill_conflicts.append(skill.name)
            else:
                report.mergeable_skills.append(skill.name)

        opc_rules_dir = opc_source / "rules"
        opc_rule_names = set()
        if opc_rules_dir.exists():
            opc_rule_names = {
                f.name for f in opc_rules_dir.iterdir()
                if f.is_file() and f.suffix == ".md"
            }

        for rule in existing.rules:
            if rule.name in opc_rule_names:
                report.rule_conflicts.append(rule.name)
            else:
                report.mergeable_rules.append(rule.name)

        opc_settings_path = opc_source / "settings.json"
        opc_mcp_names = set()
        if opc_settings_path.exists():
            try:
                opc_settings = json.loads(opc_settings_path.read_text(encoding="utf-8"))
                if "mcpServers" in opc_settings:
                    opc_mcp_names = set(opc_settings["mcpServers"].keys())
            except (json.JSONDecodeError, OSError):
                pass

        for mcp_name in existing.mcps:
            if mcp_name in opc_mcp_names:
                report.mcp_conflicts.append(mcp_name)
            else:
                report.mergeable_mcps.append(mcp_name)

        return report

    def backup_global_claude_dir() -> Path | None:
        """Create timestamped backup of global ~/.claude directory.

        Returns:
            Path to backup directory, or None if no backup needed

        Raises:
            OSError: If backup creation fails
        """
        global_dir = get_global_claude_dir()
        if not global_dir.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = global_dir.parent / f".claude.backup.{timestamp}"

        # Handle race condition: if backup path exists, add counter
        counter = 0
        original_backup_path = backup_path
        while backup_path.exists():
            counter += 1
            backup_path = global_dir.parent / f".claude.backup.{timestamp}_{counter}"
            if counter > 100:  # Safety limit
                raise OSError(f"Too many backup attempts: {original_backup_path}")

        try:
            shutil.copytree(global_dir, backup_path)
        except shutil.Error as e:
            # shutil.Error contains a list of (src, dst, error) tuples
            # Partial copy may have occurred - clean up and re-raise
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            raise OSError(f"Backup failed: {e}") from e

        return backup_path


# Directories that OPC manages (will be replaced/updated)
OPC_MANAGED_DIRS = frozenset({
    "hooks",
    "skills",
    "rules",
    "agents",
    "servers",
    "runtime",
    "scripts",
    "plugins",
})

# Files/directories that are user-specific and must be preserved
USER_PRESERVED_ITEMS = frozenset({
    # User data files
    "history.jsonl",
    ".credentials.json",
    "credentials.json",
    "config.json",
    "settings.local.json",
    "__store.db",
    "stats-cache.json",
    "CLAUDE.md",
    # User data directories
    "projects",
    "session-env",
    "file-history",
    "plans",
    "cache",
    "chrome",
    "debug",
    "downloads",
    "errors",
    "ide",
    "shell-snapshots",
    "state",
    "statsig",
    "telemetry",
    "todos",
})


class UpdateResult:
    """Result of the update operation."""

    def __init__(self) -> None:
        self.success: bool = False
        self.backup_path: Path | None = None
        self.installed_hooks: int = 0
        self.installed_skills: int = 0
        self.installed_rules: int = 0
        self.installed_agents: int = 0
        self.installed_servers: int = 0
        self.installed_scripts: int = 0
        self.installed_plugins: int = 0
        self.installed_runtime: int = 0
        self.merged_user_items: list[str] = []
        self.preserved_items: list[str] = []
        self.npm_build_success: bool | None = None
        self.errors: list[str] = []
        self.warnings: list[str] = []


def get_project_root() -> Path:
    """Get the Continuous Claude v3 project root.

    Returns:
        Path to project root (contains .claude/ directory)

    Raises:
        FileNotFoundError: If project root cannot be determined
    """
    # This script is at opc/scripts/setup/update_claude.py
    # Project root is 3 levels up
    # Use resolve() to handle symlinks correctly
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent.parent.parent

    # Validate the project root has expected structure
    if not (project_root / ".claude").exists():
        # Try alternative: maybe script was copied elsewhere
        # Walk up looking for .claude directory
        current = script_path.parent
        for _ in range(10):  # Limit search depth
            if (current / ".claude").exists():
                return current
            if current.parent == current:  # Reached filesystem root
                break
            current = current.parent
        raise FileNotFoundError(
            f"Cannot find project root with .claude directory. "
            f"Script location: {script_path}"
        )

    return project_root


def resolve_symlinks_in_target(target_dir: Path) -> list[Path]:
    """Find and resolve symlinks in target directory.

    Symlinks can cause issues when copying over them. This function
    identifies symlinks that would be replaced.

    Args:
        target_dir: Target .claude directory

    Returns:
        List of symlink paths found
    """
    symlinks = []
    if not target_dir.exists():
        return symlinks

    try:
        items = list(target_dir.iterdir())
    except PermissionError:
        print(f"  WARNING: Cannot read {target_dir} - permission denied")
        return symlinks
    except OSError as e:
        print(f"  WARNING: Cannot read {target_dir}: {e}")
        return symlinks

    for item in items:
        try:
            if item.is_symlink():
                symlinks.append(item)
            elif item.is_dir() and item.name in OPC_MANAGED_DIRS:
                # Check for symlinks inside OPC-managed dirs
                try:
                    for subitem in item.rglob("*"):
                        if subitem.is_symlink():
                            symlinks.append(subitem)
                except PermissionError:
                    print(f"  WARNING: Cannot fully scan {item} - permission denied")
                except OSError as e:
                    print(f"  WARNING: Cannot fully scan {item}: {e}")
        except OSError:
            # is_symlink() or is_dir() can fail on broken symlinks or permission issues
            pass

    return symlinks


def remove_symlinks(symlinks: list[Path], dry_run: bool = False) -> list[str]:
    """Remove symlinks before copying.

    Args:
        symlinks: List of symlink paths to remove
        dry_run: If True, only print what would be done

    Returns:
        List of error messages for symlinks that couldn't be removed
    """
    errors = []
    for link in symlinks:
        if dry_run:
            print(f"  [DRY-RUN] Would remove symlink: {link}")
        else:
            try:
                link.unlink()
            except FileNotFoundError:
                # Symlink already removed (race condition) - ignore
                pass
            except PermissionError as e:
                errors.append(f"Cannot remove symlink {link}: {e}")
                print(f"  WARNING: Cannot remove {link}: {e}")
            except OSError as e:
                errors.append(f"Failed to remove symlink {link}: {e}")
                print(f"  WARNING: Failed to remove {link}: {e}")
    return errors


def _handle_remove_readonly_onexc(func, path, exc):
    """Error handler for shutil.rmtree to handle read-only files on Windows.

    This is the Python 3.12+ version using the onexc parameter.

    On Windows, files may be read-only and rmtree will fail. This handler
    removes the read-only attribute and retries.

    Args:
        func: The function that raised the exception (os.remove, os.rmdir, etc.)
        path: The path being removed
        exc: The exception instance
    """
    import stat

    # Only handle permission errors
    if not isinstance(exc, PermissionError):
        raise exc

    # Check if the error is due to access denied (file is read-only)
    if not os.access(path, os.W_OK):
        try:
            # Remove read-only attribute and retry
            os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
            func(path)
        except OSError:
            # If retry fails, re-raise original exception
            raise exc
    else:
        # Not a read-only issue, re-raise
        raise exc


def _handle_remove_readonly_onerror(func, path, exc_info):
    """Error handler for shutil.rmtree to handle read-only files on Windows.

    This is the legacy version for Python < 3.12 using the onerror parameter.

    Args:
        func: The function that raised the exception (os.remove, os.rmdir, etc.)
        path: The path being removed
        exc_info: Exception info tuple (type, value, traceback)
    """
    exc_type, exc_value, _ = exc_info
    exc = exc_value if exc_type else OSError(f"Unknown error at {path}")
    _handle_remove_readonly_onexc(func, path, exc)


def _rmtree_robust(path: Path) -> None:
    """Remove directory tree with cross-platform and cross-version compatibility.

    Handles read-only files on Windows and uses the correct shutil.rmtree
    API for the current Python version.

    Args:
        path: Path to directory to remove

    Raises:
        OSError: If removal fails
    """
    import sys

    if sys.version_info >= (3, 12):
        # Python 3.12+: use onexc (onerror is deprecated)
        shutil.rmtree(path, onexc=_handle_remove_readonly_onexc)
    else:
        # Python < 3.12: use onerror
        shutil.rmtree(path, onerror=_handle_remove_readonly_onerror)


def copy_opc_directory(
    source_dir: Path,
    target_dir: Path,
    dir_name: str,
    dry_run: bool = False,
) -> int:
    """Copy an OPC directory to target.

    Args:
        source_dir: Source .claude directory
        target_dir: Target .claude directory
        dir_name: Name of directory to copy (e.g., "hooks")
        dry_run: If True, only print what would be done

    Returns:
        Number of items in copied directory (files only, not directories)

    Raises:
        OSError: If copy operation fails
    """
    src = source_dir / dir_name
    dst = target_dir / dir_name

    if not src.exists():
        return 0

    # Count only files, not directories, for consistent reporting
    file_count = len([f for f in src.rglob("*") if f.is_file()])

    if dry_run:
        print(f"  [DRY-RUN] Would copy {dir_name}/ ({file_count} files)")
        return file_count

    # Remove existing directory if present
    if dst.exists():
        if dst.is_symlink():
            dst.unlink()
        else:
            # Use robust removal for Windows read-only files and Python version compat
            _rmtree_robust(dst)

    # Ensure parent directory exists
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Copy directory, following symlinks (copy actual files)
    try:
        shutil.copytree(src, dst, symlinks=False)
    except shutil.Error as e:
        # shutil.Error for partial failures - log but continue
        print(f"  WARNING: Some files in {dir_name}/ could not be copied: {e}")
    except OSError as e:
        raise OSError(f"Failed to copy {dir_name}/: {e}") from e

    # Count files in destination for accurate reporting
    # Use try-except in case dst is in an inconsistent state after partial copy
    try:
        return len([f for f in dst.rglob("*") if f.is_file()])
    except OSError:
        # Fallback: return source file count if destination can't be read
        return file_count


def deep_merge_dicts(
    base: dict[str, Any],
    override: dict[str, Any],
    override_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Args:
        base: Base dictionary (user settings - preserved by default)
        override: Override dictionary (OPC settings)
        override_keys: Keys where override completely replaces base (e.g., "hooks")
                      For these keys, no deep merge happens - override wins entirely.

    Returns:
        Merged dictionary
    """
    if override_keys is None:
        override_keys = frozenset()

    result = base.copy()

    for key, value in override.items():
        if key in override_keys:
            # For specified keys, override completely replaces
            result[key] = value
        elif key not in result:
            # Key only in override - add it
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            # Both are dicts - deep merge recursively
            result[key] = deep_merge_dicts(result[key], value, override_keys)
        else:
            # Non-dict conflict: override wins for OPC-managed settings
            # User wins for user settings (base already has user value)
            pass  # Keep base value (user settings preserved)

    return result


def merge_settings_json(
    source_settings: Path,
    target_settings: Path,
    existing_setup: ExistingSetup | None,
    backup_settings: Path | None = None,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Smart merge of settings.json preserving user preferences.

    Merge strategy:
    - Start with user's settings as BASE (preserves permissions, plugins, etc.)
    - OPC's "hooks" section ALWAYS wins (managed by OPC)
    - OPC's "statusLine" ALWAYS wins (managed by OPC)
    - User's mcpServers are preserved and merged with OPC's
    - All other user settings are PRESERVED

    Args:
        source_settings: Source settings.json from OPC
        target_settings: Target settings.json in ~/.claude
        existing_setup: Existing user setup (contains parsed settings)
        backup_settings: Path to backup settings.json (for restoring user prefs)
        dry_run: If True, only print what would be done

    Returns:
        Tuple of (success, message)
    """
    if not source_settings.exists():
        return True, "No source settings.json"

    # Load OPC settings
    try:
        opc_settings = json.loads(source_settings.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in source settings.json: {e}"
    except OSError as e:
        return False, f"Cannot read source settings.json: {e}"

    # Load user's original settings from backup or existing
    user_settings: dict[str, Any] = {}
    user_settings_source = "none"

    # Try backup first (most reliable - pre-update state)
    if backup_settings and backup_settings.exists():
        try:
            user_settings = json.loads(backup_settings.read_text(encoding="utf-8"))
            user_settings_source = "backup"
        except (json.JSONDecodeError, OSError):
            pass

    # Fall back to existing_setup if backup didn't work
    if not user_settings and existing_setup and existing_setup.settings_json:
        user_settings = existing_setup.settings_json
        user_settings_source = "existing"

    # Collect what will be preserved for reporting
    preserved_items: list[str] = []
    if user_settings:
        # Keys that user has but OPC doesn't have or we want to preserve
        for key in user_settings:
            if key not in ("hooks", "statusLine", "mcpServers"):
                preserved_items.append(key)

    # Collect user MCPs that will be preserved
    user_mcps = user_settings.get("mcpServers", {})
    opc_mcps = opc_settings.get("mcpServers", {})
    user_mcps_to_preserve = [name for name in user_mcps if name not in opc_mcps]

    if dry_run:
        print("  [DRY-RUN] Would merge settings.json (smart merge)")
        if preserved_items:
            print(f"  [DRY-RUN] Would preserve user settings: {preserved_items}")
        if user_mcps_to_preserve:
            print(f"  [DRY-RUN] Would preserve user MCPs: {user_mcps_to_preserve}")
        print("  [DRY-RUN] OPC hooks and statusLine will be used")
        return True, "Dry run - settings merge skipped"

    # Perform smart merge:
    # 1. Start with user settings as base
    # 2. Override with OPC's hooks and statusLine (these are OPC-managed)
    # 3. Merge mcpServers (user + OPC)

    if user_settings:
        # Deep merge with OPC overriding hooks and statusLine
        merged = deep_merge_dicts(
            user_settings,
            opc_settings,
            override_keys=frozenset({"hooks", "statusLine"}),
        )

        # Merge mcpServers: user's + OPC's (OPC wins on conflicts)
        if user_mcps or opc_mcps:
            merged_mcps = user_mcps.copy()
            merged_mcps.update(opc_mcps)  # OPC wins on conflicts
            merged["mcpServers"] = merged_mcps
    else:
        # No user settings - just use OPC settings
        merged = opc_settings

    # Write merged settings
    try:
        target_settings.parent.mkdir(parents=True, exist_ok=True)
        target_settings.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except OSError as e:
        return False, f"Cannot write settings.json: {e}"

    # Build result message
    msg_parts = []
    if preserved_items:
        msg_parts.append(f"{len(preserved_items)} user settings preserved")
    if user_mcps_to_preserve:
        msg_parts.append(f"{len(user_mcps_to_preserve)} user MCPs preserved")
    msg_parts.append("OPC hooks applied")

    return True, "Settings merged: " + ", ".join(msg_parts)


def build_typescript_hooks(hooks_dir: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Build TypeScript hooks using npm.

    Args:
        hooks_dir: Path to hooks directory
        dry_run: If True, only print what would be done

    Returns:
        Tuple of (success, message)
    """
    if dry_run:
        print("  [DRY-RUN] Would run: npm install && npm run build in hooks/")
        return True, "Dry run - npm build skipped"

    # Check if hooks directory exists
    if not hooks_dir.exists():
        return True, "Hooks directory does not exist - no npm build needed"

    # Check if package.json exists
    if not (hooks_dir / "package.json").exists():
        return True, "No package.json found - no npm build needed"

    # Find npm executable using shutil.which for cross-platform compatibility
    npm_cmd = shutil.which("npm")
    if npm_cmd is None:
        # Fallback for Windows where .cmd extension might be needed
        if platform.system() == "Windows":
            npm_cmd = shutil.which("npm.cmd")
        if npm_cmd is None:
            return False, "npm not found in PATH - TypeScript hooks will not be built"

    try:
        # Verify npm is functional
        subprocess.run(
            [npm_cmd, "--version"],
            capture_output=True,
            check=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "npm version check timed out"
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return False, f"npm not functional: {e}"

    try:
        # Install dependencies with timeout
        print("  Running npm install...")
        subprocess.run(
            [npm_cmd, "install"],
            cwd=hooks_dir,
            capture_output=True,
            check=True,
            timeout=300,  # 5 minute timeout for npm install
        )

        # Build with timeout
        print("  Running npm run build...")
        subprocess.run(
            [npm_cmd, "run", "build"],
            cwd=hooks_dir,
            capture_output=True,
            check=True,
            timeout=120,  # 2 minute timeout for build
        )

        return True, "TypeScript hooks built successfully"

    except subprocess.TimeoutExpired as e:
        # e.cmd is a list, format it as a readable command string
        cmd_str = " ".join(str(arg) for arg in e.cmd) if isinstance(e.cmd, list) else str(e.cmd)
        return False, f"npm command timed out after {e.timeout}s: {cmd_str}"
    except subprocess.CalledProcessError as e:
        # Decode stderr, handling potential encoding issues
        try:
            error_msg = e.stderr.decode("utf-8") if e.stderr else ""
        except UnicodeDecodeError:
            error_msg = e.stderr.decode("latin-1") if e.stderr else ""
        if not error_msg:
            error_msg = str(e)
        # Truncate very long error messages
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "... (truncated)"
        return False, f"npm build failed: {error_msg}"
    except OSError as e:
        return False, f"Failed to run npm: {e}"


def merge_user_custom_items(
    existing_setup: ExistingSetup,
    conflicts: ConflictReport,
    target_dir: Path,
    backup_dir: Path | None,
    dry_run: bool = False,
) -> list[str]:
    """Merge user's custom items that don't conflict.

    Args:
        existing_setup: User's existing setup
        conflicts: Conflict analysis
        target_dir: Target .claude directory
        backup_dir: Backup directory to restore from (can be None for dry_run preview)
        dry_run: If True, only print what would be done

    Returns:
        List of merged item names
    """
    merged = []

    if not existing_setup.claude_dir:
        return merged

    # In dry_run mode, we use the original claude_dir for preview since backup doesn't exist
    # In real mode, we use backup_dir to restore from the backup
    source_dir = existing_setup.claude_dir if dry_run else backup_dir

    if source_dir is None:
        # This shouldn't happen if existing_setup.has_existing is True, but guard against it
        if not dry_run and existing_setup.claude_dir:
            print("  WARNING: Backup directory is None but existing setup exists - "
                  "cannot merge custom items. Your custom items are NOT lost, "
                  "check your ~/.claude directory.")
        return merged

    # Merge non-conflicting hooks
    for hook_name in conflicts.mergeable_hooks:
        src = source_dir / "hooks" / hook_name
        dst = target_dir / "hooks" / hook_name
        if src.exists():
            if dry_run:
                print(f"  [DRY-RUN] Would preserve user hook: {hook_name}")
                merged.append(f"hook:{hook_name}")
            else:
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    merged.append(f"hook:{hook_name}")
                except OSError as e:
                    print(f"  WARNING: Failed to copy hook {hook_name}: {e}")

    # Merge non-conflicting skills
    for skill_name in conflicts.mergeable_skills:
        src = source_dir / "skills" / skill_name
        dst = target_dir / "skills" / skill_name
        if src.exists() and src.is_dir():
            if dry_run:
                print(f"  [DRY-RUN] Would preserve user skill: {skill_name}")
                merged.append(f"skill:{skill_name}")
            else:
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if dst.exists():
                        _rmtree_robust(dst)
                    shutil.copytree(src, dst)
                    merged.append(f"skill:{skill_name}")
                except OSError as e:
                    print(f"  WARNING: Failed to copy skill {skill_name}: {e}")

    # Merge non-conflicting rules
    for rule_name in conflicts.mergeable_rules:
        src = source_dir / "rules" / rule_name
        dst = target_dir / "rules" / rule_name
        if src.exists():
            if dry_run:
                print(f"  [DRY-RUN] Would preserve user rule: {rule_name}")
                merged.append(f"rule:{rule_name}")
            else:
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    merged.append(f"rule:{rule_name}")
                except OSError as e:
                    print(f"  WARNING: Failed to copy rule {rule_name}: {e}")

    # Merge non-conflicting agents
    agents_src_dir = source_dir / "agents"
    if agents_src_dir.exists():
        for agent_file in agents_src_dir.glob("*.md"):
            opc_agents_dir = target_dir / "agents"
            if not (opc_agents_dir / agent_file.name).exists():
                dst = opc_agents_dir / agent_file.name
                if dry_run:
                    print(f"  [DRY-RUN] Would preserve user agent: {agent_file.name}")
                    merged.append(f"agent:{agent_file.name}")
                else:
                    try:
                        opc_agents_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(agent_file, dst)
                        merged.append(f"agent:{agent_file.name}")
                    except OSError as e:
                        print(f"  WARNING: Failed to copy agent {agent_file.name}: {e}")

    return merged


def run_update(
    dry_run: bool = False,
    force: bool = False,
    no_build: bool = False,
) -> UpdateResult:
    """Run the update/installation process.

    Args:
        dry_run: If True, only show what would be done
        force: If True, skip confirmation prompts
        no_build: If True, skip npm build step

    Returns:
        UpdateResult with details of the operation
    """
    result = UpdateResult()
    project_root = get_project_root()
    source_claude = project_root / ".claude"
    target_claude = get_global_claude_dir()

    print(f"\n{'=' * 60}")
    print("Continuous Claude v3 Updater")
    print(f"{'=' * 60}")
    print(f"Source: {source_claude}")
    print(f"Target: {target_claude}")
    print(f"Platform: {platform.system()} {platform.release()}")
    if dry_run:
        print("\n[DRY-RUN MODE - No changes will be made]")
    print()

    # Validate source exists
    if not source_claude.exists():
        result.errors.append(f"Source .claude directory not found: {source_claude}")
        return result

    # Detect existing setup
    print("Analyzing existing setup...")
    existing_setup = detect_existing_setup(target_claude)

    if existing_setup.has_existing:
        print(f"  Found {len(existing_setup.hooks)} hooks")
        print(f"  Found {len(existing_setup.skills)} skills")
        print(f"  Found {len(existing_setup.rules)} rules")
        print(f"  Found {len(existing_setup.mcps)} MCPs")
    else:
        print("  No existing configuration found (clean install)")

    # Analyze conflicts
    conflicts = analyze_conflicts(existing_setup, source_claude)

    if conflicts.has_conflicts:
        print("\nConflicts detected (OPC versions will be used):")
        if conflicts.hook_conflicts:
            print(f"  Hooks: {conflicts.hook_conflicts}")
        if conflicts.skill_conflicts:
            print(f"  Skills: {len(conflicts.skill_conflicts)} conflicts")
        if conflicts.rule_conflicts:
            print(f"  Rules: {conflicts.rule_conflicts}")
        if conflicts.mcp_conflicts:
            print(f"  MCPs: {conflicts.mcp_conflicts}")

    # Check for symlinks
    symlinks = resolve_symlinks_in_target(target_claude)
    if symlinks:
        print(f"\nFound {len(symlinks)} symlinks that will be replaced")
        if not dry_run and not force:
            for link in symlinks[:5]:  # Show first 5
                print(f"  - {link}")
            if len(symlinks) > 5:
                print(f"  ... and {len(symlinks) - 5} more")

    # Confirmation
    if not force and not dry_run:
        print("\nThis will:")
        print("  1. Create a timestamped backup of ~/.claude")
        print("  2. Install OPC components (hooks, skills, rules, agents,")
        print("     servers, runtime, scripts, plugins)")
        print("  3. Preserve your personal data (history, credentials, projects, etc.)")
        print("  4. Merge your custom items that don't conflict")
        if not no_build:
            print("  5. Build TypeScript hooks (npm install && npm run build)")

        try:
            response = input("\nProceed? [y/N] ").strip().lower()
            if response not in ("y", "yes"):
                print("Aborted.")
                return result
        except EOFError:
            print("\nNo input available. Use --force to skip confirmation.")
            return result

    # Create backup (MUST happen before any modifications)
    print("\nCreating backup...")
    if not dry_run:
        try:
            backup_path = backup_global_claude_dir()
            if backup_path:
                print(f"  Backup created: {backup_path}")
                result.backup_path = backup_path
            else:
                print("  No existing ~/.claude to backup")
        except OSError as e:
            result.errors.append(f"Failed to create backup: {e}")
            print(f"  ERROR: {e}")
            print("  Aborting to prevent data loss.")
            return result
    else:
        if target_claude.exists():
            print("  [DRY-RUN] Would create backup of existing ~/.claude")
        else:
            print("  [DRY-RUN] No existing ~/.claude to backup")

    # Remove symlinks if any
    if symlinks:
        print("\nRemoving symlinks...")
        symlink_errors = remove_symlinks(symlinks, dry_run)
        if symlink_errors:
            result.warnings.extend(symlink_errors)

    # Ensure target directory exists
    # Handle case where target_claude itself is a symlink to a directory
    if not dry_run:
        if target_claude.is_symlink():
            # Resolve symlink to get actual target, or remove if dangling
            try:
                resolved = target_claude.resolve()
                if not resolved.exists():
                    # Dangling symlink - remove it
                    print(f"  Removing dangling symlink: {target_claude}")
                    target_claude.unlink()
                # If symlink points to valid dir, we can use it as-is
            except OSError:
                # Failed to resolve - remove the symlink
                target_claude.unlink()
        target_claude.mkdir(parents=True, exist_ok=True)
    elif not target_claude.exists():
        print(f"  [DRY-RUN] Would create {target_claude}")
    elif target_claude.is_symlink():
        print(f"  [DRY-RUN] {target_claude} is a symlink - would resolve it")

    # Copy OPC directories
    print("\nCopying OPC components...")

    result.installed_hooks = copy_opc_directory(source_claude, target_claude, "hooks", dry_run)
    print(f"  hooks: {result.installed_hooks} files")

    result.installed_skills = copy_opc_directory(source_claude, target_claude, "skills", dry_run)
    print(f"  skills: {result.installed_skills} files")

    result.installed_rules = copy_opc_directory(source_claude, target_claude, "rules", dry_run)
    print(f"  rules: {result.installed_rules} files")

    result.installed_agents = copy_opc_directory(source_claude, target_claude, "agents", dry_run)
    print(f"  agents: {result.installed_agents} files")

    result.installed_servers = copy_opc_directory(source_claude, target_claude, "servers", dry_run)
    print(f"  servers: {result.installed_servers} files")

    result.installed_runtime = copy_opc_directory(source_claude, target_claude, "runtime", dry_run)
    print(f"  runtime: {result.installed_runtime} files")

    result.installed_plugins = copy_opc_directory(source_claude, target_claude, "plugins", dry_run)
    print(f"  plugins: {result.installed_plugins} files")

    # Copy scripts from opc/scripts/ to ~/.claude/scripts/
    print("\nCopying support scripts...")
    opc_scripts = project_root / "opc" / "scripts"
    scripts_to_copy = ["core", "math", "tldr"]
    total_scripts = 0

    for script_dir in scripts_to_copy:
        src = opc_scripts / script_dir
        if src.exists():
            dst = target_claude / "scripts" / script_dir
            if dry_run:
                count = len(list(src.rglob("*.py")))
                print(f"  [DRY-RUN] Would copy scripts/{script_dir}/ ({count} files)")
                total_scripts += count
            else:
                try:
                    if dst.exists():
                        _rmtree_robust(dst)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(src, dst)
                    file_count = len(list(dst.rglob("*.py")))
                    total_scripts += file_count
                    print(f"  scripts/{script_dir}: {file_count} files")
                except OSError as e:
                    result.warnings.append(f"Failed to copy scripts/{script_dir}: {e}")
                    print(f"  WARNING: scripts/{script_dir}: {e}")

    result.installed_scripts = total_scripts

    # Copy individual root scripts
    root_scripts = [
        "ast_grep_find.py",
        "braintrust_analyze.py",
        "qlty_check.py",
        "research_implement_pipeline.py",
        "test_research_pipeline.py",
        "multi_tool_pipeline.py",
        "recall_temporal_facts.py",
    ]
    for script_name in root_scripts:
        src = opc_scripts / script_name
        if src.exists():
            dst = target_claude / "scripts" / script_name
            if dry_run:
                print(f"  [DRY-RUN] Would copy {script_name}")
                result.installed_scripts += 1
            else:
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    result.installed_scripts += 1
                except OSError as e:
                    result.warnings.append(f"Failed to copy {script_name}: {e}")
                    print(f"  WARNING: {script_name}: {e}")

    # Merge settings.json
    print("\nMerging settings.json...")
    # Determine backup settings path for smart merge
    backup_settings_path = None
    if result.backup_path:
        backup_settings_path = result.backup_path / "settings.json"
    settings_success, settings_msg = merge_settings_json(
        source_claude / "settings.json",
        target_claude / "settings.json",
        existing_setup,
        backup_settings=backup_settings_path,
        dry_run=dry_run,
    )
    if settings_success:
        print(f"  {settings_msg}")
    else:
        result.warnings.append(settings_msg)
        print(f"  WARNING: {settings_msg}")

    # Merge user's custom items
    # In dry_run mode, backup_path is None but we still want to preview what would
    # be merged. merge_user_custom_items handles this by using existing_setup.claude_dir
    if existing_setup.has_existing:
        print("\nPreserving user custom items...")
        result.merged_user_items = merge_user_custom_items(
            existing_setup,
            conflicts,
            target_claude,
            result.backup_path,  # May be None for dry_run, function handles this
            dry_run,
        )
        if result.merged_user_items:
            print(f"  Merged {len(result.merged_user_items)} custom items")
        else:
            print("  No non-conflicting custom items to merge")

    # Build TypeScript hooks
    if not no_build:
        print("\nBuilding TypeScript hooks...")
        build_success, build_msg = build_typescript_hooks(target_claude / "hooks", dry_run)
        result.npm_build_success = build_success
        if build_success:
            print(f"  {build_msg}")
        else:
            result.warnings.append(build_msg)
            print(f"  WARNING: {build_msg}")
    else:
        print("\nSkipping TypeScript hook build (--no-build)")
        result.npm_build_success = None

    # Summary
    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}")

    if dry_run:
        print("[DRY-RUN] No changes were made")
    else:
        result.success = True
        print("Installation complete!")
        if result.backup_path:
            print(f"\nBackup location: {result.backup_path}")
        print(f"\nInstalled to: {target_claude}")
        print(f"  - {result.installed_hooks} hook files")
        print(f"  - {result.installed_skills} skill files")
        print(f"  - {result.installed_rules} rule files")
        print(f"  - {result.installed_agents} agent files")
        print(f"  - {result.installed_servers} server files")
        print(f"  - {result.installed_runtime} runtime files")
        print(f"  - {result.installed_plugins} plugin files")
        print(f"  - {result.installed_scripts} script files")

        if result.merged_user_items:
            print(f"\nPreserved {len(result.merged_user_items)} custom items")

        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

    # Show migration guidance if there were conflicts
    if conflicts.has_conflicts and not dry_run:
        print("\n" + "-" * 60)
        print("Note: Some of your custom items conflicted with OPC versions.")
        print(f"Your originals are preserved in: {result.backup_path}")
        print("Review the backup if you need to port custom functionality.")

    return result


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Install or update Continuous Claude v3 components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Preview changes without making them
    python -m scripts.setup.update_claude --dry-run

    # Install/update without prompts
    python -m scripts.setup.update_claude --force

    # Update without building TypeScript hooks
    python -m scripts.setup.update_claude --no-build
""",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip npm build step for TypeScript hooks",
    )

    args = parser.parse_args()

    try:
        result = run_update(
            dry_run=args.dry_run,
            force=args.force,
            no_build=args.no_build,
        )

        if result.errors:
            print("\nErrors:")
            for error in result.errors:
                print(f"  - {error}")
            return 1

        return 0 if result.success or args.dry_run else 1

    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        return 130
    except FileNotFoundError as e:
        print(f"\nFile or directory not found: {e}")
        print("Ensure you are running from within the Continuous Claude v3 project.")
        return 1
    except PermissionError as e:
        print(f"\nPermission denied: {e}")
        print("Try running with elevated privileges or check file permissions.")
        return 1
    except OSError as e:
        # Catch other OS-level errors (disk full, etc.)
        print(f"\nOS error: {e}")
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main())
