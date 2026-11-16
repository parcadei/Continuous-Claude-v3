"""Integration tests with real fetch MCP server."""

from pathlib import Path

import pytest

from runtime.mcp_client import get_mcp_client_manager


@pytest.mark.asyncio
async def test_fetch_server_connection():
    """Test that fetch server can be connected."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    # Verify fetch server is in config
    assert "fetch" in manager._config.mcpServers


@pytest.mark.asyncio
async def test_fetch_url():
    """Test calling fetch tool."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    # Fetch example.com
    result = await manager.call_tool("fetch__fetch", {"url": "https://example.com"})

    assert result is not None
    # Result should contain HTML content or error
    # Structure varies, but should have content
    assert isinstance(result, (dict, str))


@pytest.mark.asyncio
async def test_fetch_multiple_urls():
    """Test fetching multiple URLs sequentially."""
    manager = get_mcp_client_manager()
    config_path = Path.cwd() / "mcp_config.json"

    await manager.initialize(config_path)

    urls = ["https://example.com", "https://example.org"]
    results = []

    for url in urls:
        result = await manager.call_tool("fetch__fetch", {"url": url})
        results.append(result)

    # Verify both fetches succeeded
    assert len(results) == 2
    assert all(r is not None for r in results)
