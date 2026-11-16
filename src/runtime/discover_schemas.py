"""
Generate Pydantic models from actual API responses.

This module discovers Pydantic models by executing safe tools and inferring
types from their responses. Useful for servers that don't provide output schemas.

Typical workflow:
  1. Run: uv run mcp-generate-discovery
     (generates discovery_config.json from mcp_config.json using Claude LLM)
  2. Review and edit discovery_config.json as needed
  3. Run: uv run mcp-discover
     (executes safe tools and infers schemas)
  4. Review generated schemas in servers/{server}/discovered_types.py
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import aiofiles

from .exceptions import ToolExecutionError
from .mcp_client import McpClientManager
from .schema_inference import (
    infer_pydantic_model_from_response,
)

logger = logging.getLogger("mcp_execution.discover_schemas")


async def execute_safe_tool(
    manager: McpClientManager,
    server_name: str,
    tool_name: str,
    params: dict[str, Any],
) -> Any:
    """
    Execute a tool safely (read-only operations only).

    Args:
        manager: MCP client manager
        server_name: Name of server
        tool_name: Name of tool
        params: Tool parameters

    Returns:
        Response from tool

    Raises:
        ToolExecutionError: If tool fails or has side effects
    """
    tool_id = f"{server_name}__{tool_name}"

    logger.debug(f"Executing safe tool: {tool_id} with params: {params}")

    try:
        result = await manager.call_tool(tool_id, params)

        # Defensive unwrapping
        unwrapped = getattr(result, "value", result)

        return unwrapped
    except Exception as e:
        raise ToolExecutionError(f"Failed to execute safe tool {tool_id}: {e}") from e


async def discover_server_schemas(
    manager: McpClientManager,
    server_name: str,
    safe_tools_config: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """
    Discover Pydantic models for a single server's tools.

    Args:
        manager: MCP client manager
        server_name: Name of server
        safe_tools_config: Dict mapping tool name to sample params

    Returns:
        Dict mapping tool name to Pydantic model code
    """
    logger.info(f"Discovering schemas for server: {server_name}")

    discovered_models = {}

    for tool_name, sample_params in safe_tools_config.items():
        try:
            logger.debug(f"Discovering schema for {server_name}.{tool_name}")

            # Execute with sample parameters
            response = await execute_safe_tool(manager, server_name, tool_name, sample_params)

            # Generate Pydantic model from response
            model_code = infer_pydantic_model_from_response(tool_name, response)

            discovered_models[tool_name] = model_code

            logger.debug(f"✓ Discovered schema for {tool_name}")

        except Exception as e:
            logger.warning(f"Failed to discover schema for {tool_name}: {e}")
            # Continue with other tools
            continue

    return discovered_models


async def write_discovered_types(
    server_name: str,
    discovered_models: dict[str, str],
    output_dir: Path,
) -> None:
    """
    Write discovered Pydantic models to file.

    Creates: servers/{server}/discovered_types.py

    Args:
        server_name: Name of server
        discovered_models: Dict mapping tool name to model code
        output_dir: Output directory (servers/)
    """
    server_dir = output_dir / server_name
    server_dir.mkdir(parents=True, exist_ok=True)

    discovered_file = server_dir / "discovered_types.py"

    # Build file content
    lines = [
        '"""',
        f"Discovered Pydantic models for {server_name} server.",
        "",
        "WARNING: These models are inferred from actual API responses.",
        "They may be incomplete or incorrect. Use with caution.",
        "All fields are Optional for defensive coding.",
        '"""',
        "",
        "from pydantic import BaseModel",
        "from typing import Any, Dict, List, Optional",
        "",
    ]

    # Add all discovered models
    for tool_name, model_code in discovered_models.items():
        lines.append(model_code)
        lines.append("")

    content = "\n".join(lines)

    async with aiofiles.open(discovered_file, "w") as f:
        await f.write(content)

    logger.info(f"Wrote discovered types to: {discovered_file}")


async def discover_schemas(config_path: Path | None = None) -> None:
    """
    Main schema discovery orchestrator.

    1. Load discovery_config.json
    2. For each configured server:
       a. Connect to server
       b. Execute safe tools with sample params
       c. Infer Pydantic models from responses
       d. Write to servers/{server}/discovered_types.py
    3. Log results

    Args:
        config_path: Path to discovery_config.json
    """
    logger.info("Starting schema discovery...")

    # Load discovery config
    config_file = config_path or Path.cwd() / "discovery_config.json"

    if not config_file.exists():
        logger.warning(f"Discovery config not found: {config_file}. " "Skipping schema discovery.")
        return

    try:
        async with aiofiles.open(config_file) as f:
            content = await f.read()
        discovery_config = json.loads(content)
    except Exception as e:
        logger.error(f"Failed to load discovery config: {e}")
        return

    # Initialize MCP client manager
    manager = McpClientManager()
    try:
        await manager.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize MCP client: {e}")
        return

    # Output directory
    output_dir = Path(__file__).parent.parent.parent / "servers"
    output_dir.mkdir(exist_ok=True)

    # Discover schemas for each server
    servers_config = discovery_config.get("servers", {})

    # Log metadata if present (from mcp-generate-discovery)
    metadata = discovery_config.get("metadata", {})
    if metadata.get("generated"):
        logger.info(
            f"Using auto-generated config: "
            f"{metadata.get('generated_count', 0)} tools, "
            f"{metadata.get('skipped_count', 0)} skipped"
        )

    for server_name, server_config in servers_config.items():
        try:
            safe_tools_config = server_config.get("safeTools", {})

            if not safe_tools_config:
                logger.debug(f"No safe tools configured for {server_name}, skipping")
                continue

            # Discover schemas
            discovered_models = await discover_server_schemas(
                manager, server_name, safe_tools_config
            )

            if discovered_models:
                # Write discovered types
                await write_discovered_types(server_name, discovered_models, output_dir)
                logger.info(f"✓ Discovered {len(discovered_models)} " f"schemas for {server_name}")
            else:
                logger.warning(f"No schemas discovered for {server_name}")

        except Exception as e:
            logger.error(f"Failed to discover schemas for {server_name}: {e}")
            continue

    # Cleanup
    try:
        await manager.cleanup()
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

    logger.info("Schema discovery complete!")


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )
    asyncio.run(discover_schemas())


if __name__ == "__main__":
    main()
