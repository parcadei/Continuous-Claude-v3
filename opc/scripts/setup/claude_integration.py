#!/usr/bin/env python3
"""Claude Code Integration Installer for OPC v3.

Cross-platform installer that:
1. Detects existing Claude Code setup (hooks, skills, MCPs, rules)
2. Backs up user's current .claude/ directory
3. Analyzes conflicts and generates migration guidance
4. Installs OPC integration with user's choice of merge strategy

USAGE:
    python -m scripts.setup.claude_integration

Works on: Windows, macOS, Linux
"""

import json
import platform
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


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
        """Check if any existing configuration was found."""
        return bool(self.hooks or self.skills or self.rules or self.mcps)


@dataclass
class ConflictReport:
    """Analysis of conflicts between user config and OPC."""

    hook_conflicts: list[str] = field(default_factory=list)  # Same filename
    skill_conflicts: list[str] = field(default_factory=list)
    rule_conflicts: list[str] = field(default_factory=list)
    mcp_conflicts: list[str] = field(default_factory=list)  # Same server name

    # Items that can be safely merged (no conflicts)
    mergeable_hooks: list[str] = field(default_factory=list)
    mergeable_skills: list[str] = field(default_factory=list)
    mergeable_rules: list[str] = field(default_factory=list)
    mergeable_mcps: list[str] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """Check if there are any conflicts."""
        return bool(
            self.hook_conflicts or self.skill_conflicts or self.rule_conflicts or self.mcp_conflicts
        )


def get_claude_dir(project_dir: Path | None = None) -> Path:
    """Get the .claude directory path.

    Args:
        project_dir: Project directory. If None, uses cwd.

    Returns:
        Path to .claude directory (may not exist)
    """
    base = project_dir or Path.cwd()
    return base / ".claude"


def detect_existing_setup(claude_dir: Path) -> ExistingSetup:
    """Detect existing Claude Code configuration.

    Scans the .claude directory for:
    - hooks/ directory contents
    - skills/ directory contents
    - rules/ directory contents
    - settings.json for MCP servers

    Args:
        claude_dir: Path to .claude directory

    Returns:
        ExistingSetup with all detected configuration
    """
    setup = ExistingSetup(claude_dir=claude_dir)

    if not claude_dir.exists():
        return setup

    # Detect hooks
    hooks_dir = claude_dir / "hooks"
    if hooks_dir.exists():
        setup.hooks = [
            f for f in hooks_dir.iterdir() if f.is_file() and f.suffix in (".sh", ".ts", ".py")
        ]

    # Detect skills
    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        setup.skills = [d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]

    # Detect rules
    rules_dir = claude_dir / "rules"
    if rules_dir.exists():
        setup.rules = [f for f in rules_dir.iterdir() if f.is_file() and f.suffix == ".md"]

    # Detect MCPs from settings.json
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            setup.settings_json = settings
            # MCPs are in mcpServers key
            if "mcpServers" in settings:
                setup.mcps = settings["mcpServers"]
        except (json.JSONDecodeError, OSError):
            pass

    return setup


def get_opc_integration_source() -> Path:
    """Get path to .claude directory to install from.

    Returns:
        Path to the project root .claude source directory
    """
    # The source is relative to this script
    script_dir = Path(__file__).parent
    # scripts/setup/ -> scripts/ -> opc/ -> project root
    opc_root = script_dir.parent.parent
    project_root = opc_root.parent
    return project_root / ".claude"


def analyze_conflicts(
    existing: ExistingSetup,
    opc_source: Path,
) -> ConflictReport:
    """Analyze conflicts between existing config and OPC.

    Compares filenames/names to identify:
    - Conflicts (same name, different content)
    - Mergeable (exists in user config, not in OPC)

    Args:
        existing: User's existing setup
        opc_source: Path to OPC's .claude directory

    Returns:
        ConflictReport with all conflicts and mergeable items
    """
    report = ConflictReport()

    # Get OPC hook names
    opc_hooks_dir = opc_source / "hooks"
    opc_hook_names = set()
    if opc_hooks_dir.exists():
        opc_hook_names = {
            f.name
            for f in opc_hooks_dir.iterdir()
            if f.is_file() and f.suffix in (".sh", ".ts", ".py")
        }

    # Compare hooks
    for hook in existing.hooks:
        if hook.name in opc_hook_names:
            report.hook_conflicts.append(hook.name)
        else:
            report.mergeable_hooks.append(hook.name)

    # Get OPC skill names
    opc_skills_dir = opc_source / "skills"
    opc_skill_names = set()
    if opc_skills_dir.exists():
        opc_skill_names = {d.name for d in opc_skills_dir.iterdir() if d.is_dir()}

    # Compare skills
    for skill in existing.skills:
        if skill.name in opc_skill_names:
            report.skill_conflicts.append(skill.name)
        else:
            report.mergeable_skills.append(skill.name)

    # Get OPC rule names
    opc_rules_dir = opc_source / "rules"
    opc_rule_names = set()
    if opc_rules_dir.exists():
        opc_rule_names = {
            f.name for f in opc_rules_dir.iterdir() if f.is_file() and f.suffix == ".md"
        }

    # Compare rules
    for rule in existing.rules:
        if rule.name in opc_rule_names:
            report.rule_conflicts.append(rule.name)
        else:
            report.mergeable_rules.append(rule.name)

    # Get OPC MCP names from settings.json
    opc_settings_path = opc_source / "settings.json"
    opc_mcp_names = set()
    if opc_settings_path.exists():
        try:
            opc_settings = json.loads(opc_settings_path.read_text())
            if "mcpServers" in opc_settings:
                opc_mcp_names = set(opc_settings["mcpServers"].keys())
        except (json.JSONDecodeError, OSError):
            pass

    # Compare MCPs
    for mcp_name in existing.mcps:
        if mcp_name in opc_mcp_names:
            report.mcp_conflicts.append(mcp_name)
        else:
            report.mergeable_mcps.append(mcp_name)

    return report


def backup_claude_dir(claude_dir: Path) -> Path | None:
    """Create timestamped backup of .claude directory.

    Cross-platform backup using shutil.copytree.

    Args:
        claude_dir: Path to .claude directory to backup

    Returns:
        Path to backup directory, or None if nothing to backup
    """
    if not claude_dir.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = claude_dir.parent / f".claude.backup.{timestamp}"

    shutil.copytree(claude_dir, backup_path)

    return backup_path


def get_global_claude_dir() -> Path:
    """Get the global ~/.claude directory path.

    Returns:
        Path to global .claude directory (may not exist)
    """
    return Path.home() / ".claude"


def backup_global_claude_dir() -> Path | None:
    """Create timestamped backup of global ~/.claude directory.

    This preserves user's global Claude Code configuration before
    any modifications.

    Returns:
        Path to backup directory, or None if nothing to backup
    """
    global_dir = get_global_claude_dir()
    if not global_dir.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = global_dir.parent / f".claude.backup.{timestamp}"

    shutil.copytree(global_dir, backup_path)

    return backup_path


def generate_migration_guidance(
    existing: ExistingSetup,
    conflicts: ConflictReport,
) -> str:
    """Generate human-readable migration guidance.

    Explains what the user needs to do to migrate their
    custom hooks/skills to work with OPC.

    Args:
        existing: User's existing setup
        conflicts: Conflict analysis

    Returns:
        Markdown-formatted guidance text
    """
    lines = ["# Migration Guidance\n"]

    if not existing.has_existing:
        lines.append("No existing configuration detected. Clean install!\n")
        return "\n".join(lines)

    # Summary
    lines.append("## Summary\n")
    lines.append(f"- Hooks: {len(existing.hooks)} found")
    lines.append(f"- Skills: {len(existing.skills)} found")
    lines.append(f"- Rules: {len(existing.rules)} found")
    lines.append(f"- MCPs: {len(existing.mcps)} found\n")

    # Conflicts
    if conflicts.has_conflicts:
        lines.append("## Conflicts (same name as OPC)\n")
        lines.append("These will be replaced by OPC versions:\n")

        if conflicts.hook_conflicts:
            lines.append("### Hooks")
            for h in conflicts.hook_conflicts:
                lines.append(f"- `{h}` - review OPC version, port custom logic if needed")

        if conflicts.skill_conflicts:
            lines.append("\n### Skills")
            for s in conflicts.skill_conflicts:
                lines.append(f"- `{s}` - OPC version will be used")

        if conflicts.rule_conflicts:
            lines.append("\n### Rules")
            for r in conflicts.rule_conflicts:
                lines.append(f"- `{r}` - OPC version will be used")

        if conflicts.mcp_conflicts:
            lines.append("\n### MCPs")
            for m in conflicts.mcp_conflicts:
                lines.append(f"- `{m}` - check if OPC config differs")

        lines.append("")

    # Mergeable
    mergeable_count = (
        len(conflicts.mergeable_hooks)
        + len(conflicts.mergeable_skills)
        + len(conflicts.mergeable_rules)
        + len(conflicts.mergeable_mcps)
    )

    if mergeable_count > 0:
        lines.append("## Your Custom Items (will be preserved)\n")

        if conflicts.mergeable_hooks:
            lines.append("### Hooks")
            for h in conflicts.mergeable_hooks:
                lines.append(f"- `{h}` - will be copied to new setup")

        if conflicts.mergeable_skills:
            lines.append("\n### Skills")
            for s in conflicts.mergeable_skills:
                lines.append(f"- `{s}` - will be preserved")

        if conflicts.mergeable_rules:
            lines.append("\n### Rules")
            for r in conflicts.mergeable_rules:
                lines.append(f"- `{r}` - will be merged")

        if conflicts.mergeable_mcps:
            lines.append("\n### MCPs")
            for m in conflicts.mergeable_mcps:
                lines.append(f"- `{m}` - will be added to settings.json")

    # Instructions for custom hooks
    if existing.hooks:
        lines.append("\n## Porting Custom Hooks\n")
        lines.append("If you have custom hooks you want to keep with OPC:\n")
        lines.append("1. Check your backup at `.claude.backup.<timestamp>/`")
        lines.append("2. For each hook, check if OPC has equivalent functionality")
        lines.append("3. To port a hook:")
        lines.append("   - Copy the hook file to `.claude/hooks/`")
        lines.append("   - Register it in `.claude/settings.json` under `hooks`")
        lines.append("   - Test with: `echo '{}' | .claude/hooks/your-hook.sh`\n")

    return "\n".join(lines)


def install_opc_integration(
    target_dir: Path,
    opc_source: Path,
    merge_user_items: bool = True,
    existing: ExistingSetup | None = None,
    conflicts: ConflictReport | None = None,
) -> dict[str, Any]:
    """Install OPC integration files.

    Copies OPC's .claude directory to target, optionally
    merging user's non-conflicting items.

    Args:
        target_dir: Target .claude directory
        opc_source: Source OPC .claude directory
        merge_user_items: If True, preserve user's non-conflicting items
        existing: User's existing setup (for merging)
        conflicts: Conflict analysis (for merging)

    Returns:
        dict with keys: success, installed_hooks, installed_skills, merged_items
    """
    result = {
        "success": False,
        "installed_hooks": 0,
        "installed_skills": 0,
        "installed_rules": 0,
        "installed_agents": 0,
        "installed_servers": 0,
        "installed_scripts": 0,
        "merged_items": [],
        "error": None,
    }

    try:
        # Ensure target exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy hooks
        opc_hooks = opc_source / "hooks"
        target_hooks = target_dir / "hooks"
        if opc_hooks.exists():
            if target_hooks.exists():
                shutil.rmtree(target_hooks)
            shutil.copytree(opc_hooks, target_hooks)
            result["installed_hooks"] = len(list(target_hooks.glob("*")))

        # Copy skills
        opc_skills = opc_source / "skills"
        target_skills = target_dir / "skills"
        if opc_skills.exists():
            if target_skills.exists():
                shutil.rmtree(target_skills)
            shutil.copytree(opc_skills, target_skills)
            result["installed_skills"] = len(list(target_skills.glob("*")))

        # Copy rules
        opc_rules = opc_source / "rules"
        target_rules = target_dir / "rules"
        if opc_rules.exists():
            if target_rules.exists():
                shutil.rmtree(target_rules)
            shutil.copytree(opc_rules, target_rules)
            result["installed_rules"] = len(list(target_rules.glob("*")))

        # Copy agents
        opc_agents = opc_source / "agents"
        target_agents = target_dir / "agents"
        if opc_agents.exists():
            if target_agents.exists():
                shutil.rmtree(target_agents)
            shutil.copytree(opc_agents, target_agents)
            result["installed_agents"] = len(list(target_agents.glob("*.md")))

        # Copy servers (MCP tool wrappers)
        opc_servers = opc_source / "servers"
        target_servers = target_dir / "servers"
        if opc_servers.exists():
            if target_servers.exists():
                shutil.rmtree(target_servers)
            shutil.copytree(opc_servers, target_servers)
            result["installed_servers"] = len(list(target_servers.glob("*")))

        # Copy plugins (e.g., braintrust-tracing)
        opc_plugins = opc_source / "plugins"
        target_plugins = target_dir / "plugins"
        if opc_plugins.exists():
            if target_plugins.exists():
                shutil.rmtree(target_plugins)
            shutil.copytree(opc_plugins, target_plugins)

        # Copy runtime (MCP harness for servers)
        opc_runtime = opc_source / "runtime"
        target_runtime = target_dir / "runtime"
        if opc_runtime.exists():
            if target_runtime.exists():
                shutil.rmtree(target_runtime)
            shutil.copytree(opc_runtime, target_runtime)

        # Copy settings.json
        opc_settings_path = opc_source / "settings.json"
        target_settings_path = target_dir / "settings.json"
        if opc_settings_path.exists():
            shutil.copy2(opc_settings_path, target_settings_path)

        # Copy scripts/core/ for memory/artifact support
        # This enables recall_learnings, store_learning, and artifact_* scripts
        opc_scripts_core = opc_source.parent / "opc" / "scripts" / "core"
        target_scripts_core = target_dir / "scripts" / "core"
        if opc_scripts_core.exists():
            target_scripts_core.parent.mkdir(parents=True, exist_ok=True)
            if target_scripts_core.exists():
                shutil.rmtree(target_scripts_core)
            shutil.copytree(opc_scripts_core, target_scripts_core)
            result["installed_scripts"] = len(list(target_scripts_core.rglob("*.py")))

        # Copy scripts/mathlib/ for math computation support
        # This enables sympy_compute, pint_compute, math_router, etc.
        opc_scripts_math = opc_source.parent / "opc" / "scripts" / "mathlib"
        target_scripts_math = target_dir / "scripts" / "mathlib"
        if opc_scripts_math.exists():
            if target_scripts_math.exists():
                shutil.rmtree(target_scripts_math)
            shutil.copytree(opc_scripts_math, target_scripts_math)
            result["installed_scripts"] += len(list(target_scripts_math.rglob("*.py")))

        # Copy scripts/tldr/ for TLDR hook integration
        # This enables symbol indexing for smart-search-router
        opc_scripts_tldr = opc_source.parent / "opc" / "scripts" / "tldr"
        target_scripts_tldr = target_dir / "scripts" / "tldr"
        if opc_scripts_tldr.exists():
            if target_scripts_tldr.exists():
                shutil.rmtree(target_scripts_tldr)
            shutil.copytree(opc_scripts_tldr, target_scripts_tldr)
            result["installed_scripts"] += len(list(target_scripts_tldr.rglob("*.py")))

        # Copy individual root scripts used by skills/hooks
        # These are referenced by skills like /qlty-check, /ast-grep-find, /mcp-chaining
        root_scripts = [
            "ast_grep_find.py",          # /ast-grep-find skill
            "braintrust_analyze.py",     # session-end-cleanup hook
            "qlty_check.py",             # /qlty-check skill
            "research_implement_pipeline.py",  # /mcp-chaining skill
            "test_research_pipeline.py", # /mcp-chaining skill
            "multi_tool_pipeline.py",    # /skill-developer example
            "recall_temporal_facts.py",  # /system_overview skill
        ]
        opc_scripts_root = opc_source.parent / "opc" / "scripts"
        target_scripts_root = target_dir / "scripts"
        target_scripts_root.mkdir(parents=True, exist_ok=True)
        for script_name in root_scripts:
            src = opc_scripts_root / script_name
            if src.exists():
                shutil.copy2(src, target_scripts_root / script_name)
                result["installed_scripts"] += 1

        # Merge user items if requested
        if merge_user_items and existing and conflicts:
            # Merge non-conflicting hooks
            if existing.claude_dir:
                for hook_name in conflicts.mergeable_hooks:
                    src = existing.claude_dir / "hooks" / hook_name
                    if src.exists():
                        shutil.copy2(src, target_hooks / hook_name)
                        result["merged_items"].append(f"hook:{hook_name}")

                # Merge non-conflicting skills
                for skill_name in conflicts.mergeable_skills:
                    src = existing.claude_dir / "skills" / skill_name
                    if src.exists():
                        shutil.copytree(src, target_skills / skill_name)
                        result["merged_items"].append(f"skill:{skill_name}")

                # Merge non-conflicting rules
                for rule_name in conflicts.mergeable_rules:
                    src = existing.claude_dir / "rules" / rule_name
                    if src.exists():
                        shutil.copy2(src, target_rules / rule_name)
                        result["merged_items"].append(f"rule:{rule_name}")

                # Merge non-conflicting MCPs into settings.json
                if conflicts.mergeable_mcps and existing.mcps:
                    settings = json.loads(target_settings_path.read_text())
                    if "mcpServers" not in settings:
                        settings["mcpServers"] = {}
                    for mcp_name in conflicts.mergeable_mcps:
                        if mcp_name in existing.mcps:
                            settings["mcpServers"][mcp_name] = existing.mcps[mcp_name]
                            result["merged_items"].append(f"mcp:{mcp_name}")
                    target_settings_path.write_text(json.dumps(settings, indent=2))

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


def get_platform_info() -> dict[str, str]:
    """Get current platform information.

    Returns:
        dict with keys: system, release, machine
    """
    return {
        "system": platform.system(),  # Windows, Darwin, Linux
        "release": platform.release(),
        "machine": platform.machine(),
    }


# Protected fields that should never be modified
PROTECTED_FIELDS = frozenset({"env", "attribution"})


def merge_settings(
    user_settings: dict[str, Any],
    repo_settings: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    """Merge user and repository settings intelligently.

    PROTECTED FIELDS (never touched):
    - `env` - all API keys and tokens
    - `attribution` - commit/PR fields
    - Any field starting with "custom_" prefix

    NEW FIELD ADDITION:
    - If field exists in repo but not user, add it
    - If field exists in both, merge intelligently:
      - For hooks: deep merge (add new hooks, keep existing)
      - For mcpServers: merge servers, preserve env/* in each
      - For other objects: user values win

    Args:
        user_settings: User's current settings.json
        repo_settings: Settings from repository's .claude/settings.json

    Returns:
        tuple: (merged_settings, fields_added, fields_preserved, warnings)
    """
    merged: dict[str, Any] = {}
    fields_added: list[str] = []
    fields_preserved: list[str] = []
    warnings: list[str] = []

    # Collect all unique keys from both settings
    all_keys = set(user_settings.keys()) | set(repo_settings.keys())

    for key in all_keys:
        user_val = user_settings.get(key)
        repo_val = repo_settings.get(key)

        # Check if protected (env, attribution, or custom_*)
        is_protected = key in PROTECTED_FIELDS or key.startswith("custom_")
        if is_protected:
            if user_val is not None:
                merged[key] = user_val
                fields_preserved.append(key)
            elif repo_val is not None:
                merged[key] = repo_val
                warnings.append(f"Protected field '{key}' was in repo but not in user settings - using repo value")
                fields_added.append(key)
            continue

        # Both have the field
        if user_val is not None and repo_val is not None:
            merged[key] = _merge_values(user_val, repo_val, key, fields_preserved, fields_added, warnings)
            if key not in fields_added:
                fields_preserved.append(key)

        # Only user has it
        elif user_val is not None:
            merged[key] = user_val
            fields_preserved.append(key)

        # Only repo has it
        elif repo_val is not None:
            merged[key] = repo_val
            fields_added.append(key)

    return merged, fields_added, fields_preserved, warnings


def _merge_values(
    user_val: Any,
    repo_val: Any,
    key: str,
    fields_preserved: list[str],
    fields_added: list[str],
    warnings: list[str],
) -> Any:
    """Merge two values based on their types.

    Args:
        user_val: User's value
        repo_val: Repository's value
        key: Field name for context
        fields_preserved: List to append preserved field names
        fields_added: List to append added field names
        warnings: List to append warnings

    Returns:
        Merged value
    """
    # Both are dicts - special handling for hooks and mcpServers
    if isinstance(user_val, dict) and isinstance(repo_val, dict):
        if key == "hooks":
            return _merge_hooks(user_val, repo_val, fields_preserved, fields_added, warnings)
        elif key == "mcpServers":
            return _merge_mcps(user_val, repo_val, fields_preserved, fields_added, warnings)
        else:
            # For other objects: user values win
            return user_val

    # Both are lists - concatenate
    elif isinstance(user_val, list) and isinstance(repo_val, list):
        return user_val + repo_val

    # User value takes precedence for primitives
    elif user_val is not None:
        return user_val
    else:
        return repo_val


def _merge_hooks(
    user_hooks: dict[str, Any],
    repo_hooks: dict[str, Any],
    fields_preserved: list[str],
    fields_added: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    """Deep merge hooks - add new hook types, keep existing hook arrays.

    Args:
        user_hooks: User's hooks configuration
        repo_hooks: Repository's hooks configuration
        fields_preserved: List to append preserved field names
        fields_added: List to append added field names
        warnings: List to append warnings

    Returns:
        Merged hooks configuration
    """
    merged: dict[str, Any] = {}
    all_hook_types = set(user_hooks.keys()) | set(repo_hooks.keys())

    for hook_type in all_hook_types:
        user_hook = user_hooks.get(hook_type)
        repo_hook = repo_hooks.get(hook_type)

        if user_hook is not None and repo_hook is not None:
            # Both have this hook type - merge arrays, keeping order: user first
            if isinstance(user_hook, list) and isinstance(repo_hook, list):
                # Merge by combining unique entries based on command
                merged_commands = _unique_hooks_by_command(user_hook + repo_hook)
                merged[hook_type] = merged_commands
                fields_preserved.append(f"hooks.{hook_type}")
            else:
                # Different types - user wins
                merged[hook_type] = user_hook
                fields_preserved.append(f"hooks.{hook_type}")

        elif user_hook is not None:
            # Only user has this hook type
            merged[hook_type] = user_hook
            fields_preserved.append(f"hooks.{hook_type}")

        elif repo_hook is not None:
            # Only repo has this hook type
            merged[hook_type] = repo_hook
            fields_added.append(f"hooks.{hook_type}")

    return merged


def _merge_mcps(
    user_mcps: dict[str, Any],
    repo_mcps: dict[str, Any],
    fields_preserved: list[str],
    fields_added: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    """Merge mcpServers - merge server configs, preserve env/* in each.

    Args:
        user_mcps: User's MCP servers configuration
        repo_mcps: Repository's MCP servers configuration
        fields_preserved: List to append preserved field names
        fields_added: List to append added field names
        warnings: List to append warnings

    Returns:
        Merged MCP servers configuration
    """
    merged: dict[str, Any] = {}
    all_servers = set(user_mcps.keys()) | set(repo_mcps.keys())

    for server_name in all_servers:
        user_mcp = user_mcps.get(server_name)
        repo_mcp = repo_mcps.get(server_name)

        if user_mcp is not None and repo_mcp is not None:
            # Both have this server - merge intelligently
            if isinstance(user_mcp, dict) and isinstance(repo_mcp, dict):
                merged_server: dict[str, Any] = {}

                # All keys from both configs
                all_keys = set(user_mcp.keys()) | set(repo_mcp.keys())

                for config_key in all_keys:
                    user_val = user_mcp.get(config_key)
                    repo_val = repo_mcp.get(config_key)

                    if config_key == "env":
                        # Preserve both env configs - they may have different vars
                        if isinstance(user_val, dict) and isinstance(repo_val, dict):
                            merged_env = dict(repo_val)  # Start with repo base
                            merged_env.update(user_val)  # User values override
                            merged_server["env"] = merged_env
                        elif user_val is not None:
                            merged_server["env"] = user_val
                        else:
                            merged_server["env"] = repo_val
                    elif user_val is not None:
                        # User values win for other keys
                        merged_server[config_key] = user_val
                    else:
                        merged_server[config_key] = repo_val

                merged[server_name] = merged_server
                fields_preserved.append(f"mcpServers.{server_name}")
            else:
                # Different types - user wins
                merged[server_name] = user_mcp
                fields_preserved.append(f"mcpServers.{server_name}")

        elif user_mcp is not None:
            # Only user has this server
            merged[server_name] = user_mcp
            fields_preserved.append(f"mcpServers.{server_name}")

        elif repo_mcp is not None:
            # Only repo has this server
            merged[server_name] = repo_mcp
            fields_added.append(f"mcpServers.{server_name}")

    return merged


def _unique_hooks_by_command(hooks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate hooks based on command, preserving order.

    Args:
        hooks: List of hook configurations

    Returns:
        List with duplicate commands removed (first occurrence kept)
    """
    seen_commands: dict[str, int] = {}
    result: list[dict[str, Any]] = []

    for hook in hooks:
        if isinstance(hook, dict):
            command = hook.get("command", "")
            if command and command not in seen_commands:
                seen_commands[command] = len(result)
                result.append(hook)
        else:
            # Non-dict entries (unlikely but safe)
            result.append(hook)

    return result
