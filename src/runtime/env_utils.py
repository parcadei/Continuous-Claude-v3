"""Environment variable utilities for MCP config loading.

This module provides:
- .env file loading via python-dotenv
- ${VAR} and ${VAR:-default} expansion in config values
"""

import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Pattern for ${VAR} or ${VAR:-default}
ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def expand_env_vars(value: str) -> str:
    """Expand environment variables in a string.

    Supports:
    - ${VAR} - expands to env var value or empty string
    - ${VAR:-default} - expands to env var value or default

    Args:
        value: String potentially containing ${VAR} patterns

    Returns:
        String with all env vars expanded
    """

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)  # May be None
        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        return default if default is not None else ""

    return ENV_VAR_PATTERN.sub(replacer, value)


def expand_env_vars_in_config(config: Any) -> Any:
    """Recursively expand environment variables in a config structure.

    Args:
        config: Dict, list, string, or other value

    Returns:
        Same structure with all string values having env vars expanded
    """
    if isinstance(config, dict):
        return {key: expand_env_vars_in_config(value) for key, value in config.items()}
    elif isinstance(config, list):
        return [expand_env_vars_in_config(item) for item in config]
    elif isinstance(config, str):
        return expand_env_vars(config)
    else:
        return config


def load_project_env(start_path: Path | None = None) -> bool:
    """Load .env file from project root, with global fallback.

    Searches for .env in:
    1. Current directory or specified path
    2. ~/.claude/.env (global fallback)

    Does not override existing environment variables.

    Args:
        start_path: Directory to search for .env (default: cwd)

    Returns:
        True if .env was loaded, False otherwise
    """
    search_path = start_path or Path.cwd()
    env_file = search_path / ".env"
    global_env = Path.home() / ".claude" / ".env"

    loaded = False

    # Load global .env first (lower priority)
    if global_env.exists():
        load_dotenv(global_env, override=False)
        loaded = True

    # Load local .env (higher priority, but doesn't override existing)
    if env_file.exists():
        load_dotenv(env_file, override=False)
        loaded = True

    return loaded
