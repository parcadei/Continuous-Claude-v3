"""Unit tests for discover_schemas module with mocks."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from runtime.discover_schemas import (
    discover_server_schemas,
    write_discovered_types,
)


@pytest.mark.asyncio
async def test_discover_server_schemas_with_dict_response():
    """Test discovering schemas from dict responses."""
    # Mock manager
    manager = AsyncMock()
    manager.call_tool = AsyncMock(return_value={"status": "success", "count": 42})

    # Configure safe tools
    safe_tools_config = {"test_tool": {"param1": "value1"}}

    # Discover schemas
    discovered = await discover_server_schemas(manager, "test_server", safe_tools_config)

    # Verify
    assert "test_tool" in discovered
    assert "class TestToolResult(BaseModel):" in discovered["test_tool"]
    assert "status: Optional[str] = None" in discovered["test_tool"]
    assert "count: Optional[int] = None" in discovered["test_tool"]


@pytest.mark.asyncio
async def test_discover_server_schemas_with_string_response():
    """Test discovering schemas from string responses."""
    # Mock manager
    manager = AsyncMock()
    manager.call_tool = AsyncMock(return_value="Simple string response")

    # Configure safe tools
    safe_tools_config = {"get_status": {}}

    # Discover schemas
    discovered = await discover_server_schemas(manager, "test_server", safe_tools_config)

    # Verify
    assert "get_status" in discovered
    assert "class GetStatusResult(BaseModel):" in discovered["get_status"]
    assert "value: str = None" in discovered["get_status"]


@pytest.mark.asyncio
async def test_discover_server_schemas_with_error():
    """Test that errors don't stop discovery."""
    # Mock manager - first call fails, second succeeds
    manager = AsyncMock()
    manager.call_tool = AsyncMock(side_effect=[Exception("Tool failed"), {"data": "success"}])

    # Configure safe tools
    safe_tools_config = {"failing_tool": {}, "working_tool": {}}

    # Discover schemas
    discovered = await discover_server_schemas(manager, "test_server", safe_tools_config)

    # Verify that working_tool was discovered despite failing_tool error
    assert "failing_tool" not in discovered
    assert "working_tool" in discovered


@pytest.mark.asyncio
async def test_write_discovered_types():
    """Test writing discovered types to file."""
    discovered_models = {
        "tool_one": "class ToolOneResult(BaseModel):\n    value: str = None",
        "tool_two": "class ToolTwoResult(BaseModel):\n    count: int = None",
    }

    # Create temporary directory
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Write discovered types
        await write_discovered_types("test_server", discovered_models, output_dir)

        # Verify file was created
        discovered_file = output_dir / "test_server" / "discovered_types.py"
        assert discovered_file.exists()

        # Verify content
        content = discovered_file.read_text()
        assert "from pydantic import BaseModel" in content
        assert "from typing import Any, Dict, List, Optional" in content
        assert "class ToolOneResult(BaseModel):" in content
        assert "class ToolTwoResult(BaseModel):" in content
        assert "WARNING: These models are inferred from actual API responses" in content
