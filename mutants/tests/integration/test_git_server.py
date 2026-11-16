"""Integration tests with real git MCP server."""

from pathlib import Path

import pytest

from runtime.exceptions import ToolNotFoundError
from runtime.mcp_client import ConnectionState, get_mcp_client_manager


@pytest.mark.asyncio
async def test_git_server_connection():
    """Test that git server can be connected."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    # Verify git server is in config
    assert "git" in manager._config.mcpServers


@pytest.mark.asyncio
async def test_git_status_tool():
    """Test calling git_status tool."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    # Call git_status on current repo
    result = await manager.call_tool("git__git_status", {"repo_path": "."})

    assert result is not None
    # Result should contain git status info
    # (structure varies, but should be dict or string)
    assert isinstance(result, (dict, str, list))


@pytest.mark.asyncio
async def test_git_log_tool():
    """Test calling git_log tool."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    # Call git_log with limit
    result = await manager.call_tool("git__git_log", {"repo_path": ".", "max_count": 5})

    assert result is not None


@pytest.mark.asyncio
async def test_tool_not_found():
    """Test that calling non-existent tool raises error."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    with pytest.raises(ToolNotFoundError):
        await manager.call_tool("git__nonexistent_tool", {})


@pytest.mark.asyncio
async def test_server_not_found():
    """Test that calling tool on non-existent server raises error."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    with pytest.raises(ToolNotFoundError):
        await manager.call_tool("nonexistent__tool", {})


@pytest.mark.asyncio
async def test_lazy_connection():
    """Test that server connects lazily on first tool call."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    # After initialize, no connections should exist
    assert len(manager._clients) == 0

    # Call tool
    await manager.call_tool("git__git_status", {"repo_path": "."})

    # Now git server should be connected
    assert "git" in manager._clients


@pytest.mark.asyncio
async def test_cleanup():
    """Test that cleanup closes all connections."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)
    await manager.call_tool("git__git_status", {"repo_path": "."})

    # Verify connection exists
    assert len(manager._clients) > 0

    # Cleanup
    await manager.cleanup()

    # Verify connections closed
    assert len(manager._clients) == 0
    assert manager._state == ConnectionState.UNINITIALIZED
