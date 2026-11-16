"""
Field normalization utilities for handling inconsistent API casing.

Some MCP servers (e.g., Azure DevOps) return fields with lowercase prefixes
but expect PascalCase prefixes in certain contexts. This module provides
configurable normalization strategies.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# Type alias for normalization strategies
NormalizationStrategy = Literal["none", "ado-pascal-case"]


class NormalizationConfig(BaseModel):
    """Configuration for field normalization per server."""

    model_config = ConfigDict(extra="forbid")

    servers: dict[str, NormalizationStrategy]


# Default configuration
NORMALIZATION_CONFIG = NormalizationConfig(
    servers={
        "ado": "ado-pascal-case",
        "filesystem": "none",
        "github": "none",
    }
)


def normalize_field_names(obj: Any, server_name: str) -> Any:
    """
    Normalize field names based on server strategy.

    Recursively traverses dicts and lists.
    Returns new object (immutable).

    Args:
        obj: Object to normalize (dict, list, or primitive)
        server_name: Name of the server (determines strategy)

    Returns:
        Normalized object (new instance, original unchanged)

    Examples:
        >>> normalize_field_names({"system.title": "foo"}, "ado")
        {'System.Title': 'foo'}

        >>> normalize_field_names({"title": "foo"}, "github")
        {'title': 'foo'}
    """
    strategy = NORMALIZATION_CONFIG.servers.get(server_name, "none")

    if strategy == "none":
        return obj
    elif strategy == "ado-pascal-case":
        return normalize_ado_fields(obj)
    else:
        # Unknown strategy, return unchanged
        return obj


def normalize_ado_fields(obj: Any) -> Any:
    """
    ADO-specific field normalization.

    Rules:
    - system.* → System.*
    - microsoft.* → Microsoft.*
    - custom.* → Custom.*
    - wef_* → WEF_*

    Recursively processes nested structures.
    Returns new object (immutable).

    Args:
        obj: Object to normalize

    Returns:
        Normalized object (new instance)

    Examples:
        >>> normalize_ado_fields({"system.title": "foo"})
        {'System.title': 'foo'}

        >>> normalize_ado_fields({"fields": {"system.id": 123}})
        {'fields': {'System.id': 123}}
    """
    # Handle primitives
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # Handle lists
    if isinstance(obj, list):
        return [normalize_ado_fields(item) for item in obj]

    # Handle dicts
    if isinstance(obj, dict):
        normalized = {}
        for key, value in obj.items():
            new_key = key

            # Apply normalization rules
            if key.startswith("system."):
                new_key = "System." + key[7:]
            elif key.startswith("microsoft."):
                new_key = "Microsoft." + key[10:]
            elif key.startswith("custom."):
                new_key = "Custom." + key[7:]
            elif key.startswith("wef_"):
                new_key = "WEF_" + key[4:]

            # Recursively normalize value
            normalized[new_key] = normalize_ado_fields(value)

        return normalized

    # Unknown type, return as-is
    return obj


def update_normalization_config(server_name: str, strategy: NormalizationStrategy) -> None:
    """
    Update normalization strategy for a server.

    Args:
        server_name: Name of the server
        strategy: Normalization strategy to use

    Examples:
        >>> update_normalization_config("myserver", "ado-pascal-case")
        >>> update_normalization_config("myserver", "none")
    """
    NORMALIZATION_CONFIG.servers[server_name] = strategy


def get_normalization_strategy(server_name: str) -> NormalizationStrategy:
    """
    Get normalization strategy for a server.

    Args:
        server_name: Name of the server

    Returns:
        Normalization strategy (defaults to "none")
    """
    return NORMALIZATION_CONFIG.servers.get(server_name, "none")
