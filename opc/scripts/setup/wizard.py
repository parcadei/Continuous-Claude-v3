#!/usr/bin/env python3
"""Setup Wizard for OPC v3.

Interactive setup wizard for configuring the Claude Continuity Kit.
Handles prerequisite checking, database configuration, API keys,
and environment file generation.

USAGE:
    python -m scripts.setup.wizard

Or run as a standalone script:
    python scripts/setup/wizard.py
"""

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
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

    # Step 7: Claude Code Integration
    console.print("\n[bold]Step 7/12: Claude Code Integration[/bold]")
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

    # Step 8: Math Features (Optional)
    console.print("\n[bold]Step 8/12: Math Features (Optional)[/bold]")
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

    # Step 9: TLDR Code Analysis Tool
    console.print("\n[bold]Step 9/12: TLDR Code Analysis Tool[/bold]")
    console.print("  TLDR provides token-efficient code analysis for LLMs:")
    console.print("    - 95% token savings vs reading raw files")
    console.print("    - 155x faster queries with daemon mode")
    console.print("    - Semantic search, call graphs, program slicing")
    console.print("    - Works with Python, TypeScript, Go, Rust")
    console.print("")
    console.print("  [dim]Note: First semantic search downloads ~1.3GB embedding model.[/dim]")

    if Confirm.ask("\nInstall TLDR code analysis tool?", default=True):
        console.print("  Installing TLDR...")
        import subprocess

        try:
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

    # Step 10: Diagnostics Tools (Shift-Left Feedback)
    console.print("\n[bold]Step 10/12: Diagnostics Tools (Shift-Left Feedback)[/bold]")
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

    # Step 11: Loogle (Lean 4 type search for /prove skill)
    console.print("\n[bold]Step 11/12: Loogle (Lean 4 Type Search)[/bold]")
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
            console.print("  [dim]Usage: loogle-search \"Nontrivial _ ↔ _\"[/dim]")
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


async def main():
    """Entry point for the setup wizard."""
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
