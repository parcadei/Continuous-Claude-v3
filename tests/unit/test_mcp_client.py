"""Comprehensive unit tests for MCP Client Manager with state machine architecture.

This test suite verifies:
- State machine transitions and validation
- Lazy initialization (config loaded, servers NOT connected)
- Lazy connection (servers connect on first tool call)
- Tool caching (list_tools cached, not called repeatedly)
- Defensive unwrapping (handles response.value and text responses)
- Singleton pattern verification
- Cleanup and error handling
- Edge cases and error scenarios
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from runtime.exceptions import (
    ConfigurationError,
    ServerConnectionError,
    ToolExecutionError,
    ToolNotFoundError,
)
from runtime.mcp_client import (
    ConnectionState,
    McpClientManager,
    call_mcp_tool,
    get_mcp_client_manager,
)


@pytest.fixture
def sample_config_dict() -> dict[str, Any]:
    """Sample configuration dictionary for testing."""
    return {
        "mcpServers": {
            "test-server": {
                "command": "node",
                "args": ["server.js"],
                "env": {"TEST_VAR": "test_value"},
            },
            "disabled-server": {
                "command": "python",
                "args": ["server.py"],
                "disabled": True,
            },
        }
    }


@pytest.fixture
def temp_config_file(tmp_path: Path, sample_config_dict: dict[str, Any]) -> Path:
    """Create a temporary config file for testing."""
    config_file = tmp_path / "mcp_config.json"
    config_file.write_text(json.dumps(sample_config_dict))
    return config_file


@pytest.fixture
def manager() -> McpClientManager:
    """Create a fresh manager instance for each test."""
    return McpClientManager()


@pytest.fixture
def mock_tool() -> Mock:
    """Create a mock tool object."""
    tool = Mock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    return tool


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock ClientSession."""
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock()
    session.call_tool = AsyncMock()
    return session


@pytest.fixture
def mock_stdio_context() -> AsyncMock:
    """Create a mock stdio context manager that yields read/write streams."""
    stdio_ctx = AsyncMock()
    stdio_ctx.__aenter__ = AsyncMock(return_value=(Mock(), Mock()))
    stdio_ctx.__aexit__ = AsyncMock(return_value=None)
    return stdio_ctx


class TestStateTransitions:
    """Test state machine transitions and validation."""

    def test_initial_state_is_uninitialized(self, manager: McpClientManager) -> None:
        """Manager should start in UNINITIALIZED state."""
        assert manager._state == ConnectionState.UNINITIALIZED

    async def test_initialize_transitions_to_initialized(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Initialize should transition from UNINITIALIZED to INITIALIZED."""
        assert manager._state == ConnectionState.UNINITIALIZED
        await manager.initialize(temp_config_file)
        assert manager._state == ConnectionState.INITIALIZED

    async def test_cannot_initialize_twice(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Should not allow initializing an already initialized manager."""
        await manager.initialize(temp_config_file)
        with pytest.raises(ConfigurationError, match="requires state 'uninitialized'"):
            await manager.initialize(temp_config_file)

    async def test_cannot_call_tool_before_initialize(self, manager: McpClientManager) -> None:
        """Should raise error when calling tool before initialization."""
        with pytest.raises(ConfigurationError, match="requires at least state 'initialized'"):
            await manager.call_tool("server__tool", {})

    async def test_cleanup_resets_to_uninitialized(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Cleanup should reset state to UNINITIALIZED."""
        await manager.initialize(temp_config_file)
        assert manager._state == ConnectionState.INITIALIZED
        await manager.cleanup()
        assert manager._state == ConnectionState.UNINITIALIZED

    async def test_can_reinitialize_after_cleanup(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Should be able to initialize again after cleanup."""
        await manager.initialize(temp_config_file)
        await manager.cleanup()
        await manager.initialize(temp_config_file)
        assert manager._state == ConnectionState.INITIALIZED


class TestLazyInitialization:
    """Test lazy initialization behavior - config loaded but no connections."""

    async def test_initialize_loads_config(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Initialize should load config from file."""
        await manager.initialize(temp_config_file)
        assert manager._config is not None
        assert len(manager._config.mcpServers) == 2
        assert "test-server" in manager._config.mcpServers

    async def test_initialize_does_not_connect(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Initialize should NOT establish any server connections."""
        await manager.initialize(temp_config_file)
        assert len(manager._clients) == 0
        assert len(manager._tool_cache) == 0

    async def test_initialize_missing_config_file(self, manager: McpClientManager) -> None:
        """Should raise error if config file doesn't exist."""
        with pytest.raises(ConfigurationError, match="Config file not found"):
            await manager.initialize(Path("/nonexistent/config.json"))

    async def test_initialize_invalid_json(self, manager: McpClientManager, tmp_path: Path) -> None:
        """Should raise error if config file contains invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ invalid json }")
        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            await manager.initialize(invalid_file)

    async def test_initialize_uses_default_path(
        self, manager: McpClientManager, tmp_path: Path, sample_config_dict: dict[str, Any]
    ) -> None:
        """Initialize should use mcp_config.json in cwd if no path provided."""
        config_file = tmp_path / "mcp_config.json"
        config_file.write_text(json.dumps(sample_config_dict))

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            await manager.initialize()
            assert manager._config is not None


class TestLazyConnection:
    """Test lazy connection behavior - servers connect on first tool call."""

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_call_tool_connects_on_demand(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """First tool call should establish server connection."""
        # Setup mocks
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]
        mock_session.call_tool.return_value.value = "result"

        # Initialize but don't connect
        await manager.initialize(temp_config_file)
        assert len(manager._clients) == 0

        # Call tool - should trigger connection
        await manager.call_tool("test-server__test_tool", {})

        # Verify connection was established
        assert "test-server" in manager._clients
        assert manager._state == ConnectionState.CONNECTED
        mock_stdio.assert_called_once()

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_second_call_reuses_connection(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Second tool call should reuse existing connection."""
        # Setup mocks
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]
        mock_session.call_tool.return_value.value = "result"

        await manager.initialize(temp_config_file)

        # First call
        await manager.call_tool("test-server__test_tool", {})
        first_call_count = mock_stdio.call_count

        # Second call
        await manager.call_tool("test-server__test_tool", {})
        second_call_count = mock_stdio.call_count

        # Should not create new connection
        assert second_call_count == first_call_count

    async def test_call_tool_invalid_identifier(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Should raise error for invalid tool identifier format."""
        await manager.initialize(temp_config_file)
        with pytest.raises(ToolNotFoundError, match="Invalid tool identifier"):
            await manager.call_tool("invalid_identifier", {})

    async def test_call_tool_unknown_server(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Should raise error if server not in configuration."""
        await manager.initialize(temp_config_file)
        with pytest.raises(ToolNotFoundError, match="Server 'unknown' not found"):
            await manager.call_tool("unknown__tool", {})

    async def test_call_tool_disabled_server(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Should raise error if server is disabled."""
        await manager.initialize(temp_config_file)
        with pytest.raises(ToolNotFoundError, match="disabled in configuration"):
            await manager.call_tool("disabled-server__tool", {})


class TestToolCaching:
    """Test tool caching behavior - avoid repeated list_tools calls."""

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_tools_cached_after_first_query(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Tools should be cached after first list_tools call."""
        # Setup mocks
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]
        mock_session.call_tool.return_value.value = "result"

        await manager.initialize(temp_config_file)

        # First tool call - should query list_tools
        await manager.call_tool("test-server__test_tool", {})
        first_list_count = mock_session.list_tools.call_count

        # Second tool call - should use cache
        await manager.call_tool("test-server__test_tool", {})
        second_list_count = mock_session.list_tools.call_count

        # list_tools should only be called once
        assert first_list_count == 1
        assert second_list_count == 1

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_cache_persists_across_calls(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Tool cache should persist across multiple tool calls."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]
        mock_session.call_tool.return_value.value = "result"

        await manager.initialize(temp_config_file)
        await manager.call_tool("test-server__test_tool", {})

        # Cache should be populated
        assert "test-server" in manager._tool_cache
        assert len(manager._tool_cache["test-server"]) == 1

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_list_all_tools_uses_cache(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """list_all_tools should use cache if available."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]

        await manager.initialize(temp_config_file)

        # First call - populates cache
        await manager.list_all_tools()
        first_count = mock_session.list_tools.call_count

        # Second call - should use cache
        await manager.list_all_tools()
        second_count = mock_session.list_tools.call_count

        # Should not call list_tools again
        assert first_count == 1
        assert second_count == 1


class TestDefensiveUnwrapping:
    """Test defensive unwrapping of responses - handle various response formats."""

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_unwrap_response_value(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Should unwrap response.value if present."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]

        # Mock response with .value attribute
        response = Mock()
        response.value = "test_value"
        mock_session.call_tool.return_value = response

        await manager.initialize(temp_config_file)
        result = await manager.call_tool("test-server__test_tool", {})

        assert result == "test_value"

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_unwrap_response_content(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Should unwrap response.content if no .value."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]

        # Mock response with .content attribute
        response = Mock(spec=["content"])
        response.content = "test_content"
        mock_session.call_tool.return_value = response

        await manager.initialize(temp_config_file)
        result = await manager.call_tool("test-server__test_tool", {})

        assert result == "test_content"

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_unwrap_text_response(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Should unwrap text from list response format."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]

        # Mock response as list with text attribute
        text_item = Mock()
        text_item.text = "plain text result"
        response = Mock()
        response.value = [text_item]
        mock_session.call_tool.return_value = response

        await manager.initialize(temp_config_file)
        result = await manager.call_tool("test-server__test_tool", {})

        assert result == "plain text result"

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_unwrap_json_text_response(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Should parse JSON from text response."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]

        # Mock response with JSON text
        text_item = Mock()
        text_item.text = '{"key": "value", "number": 42}'
        response = Mock()
        response.value = [text_item]
        mock_session.call_tool.return_value = response

        await manager.initialize(temp_config_file)
        result = await manager.call_tool("test-server__test_tool", {})

        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["number"] == 42

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_fallback_to_response(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Should fall back to raw response if no known attributes."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]

        # Mock response with no .value or .content
        response = {"raw": "data"}
        mock_session.call_tool.return_value = response

        await manager.initialize(temp_config_file)
        result = await manager.call_tool("test-server__test_tool", {})

        assert result == {"raw": "data"}


class TestSingletonPattern:
    """Test singleton behavior using lru_cache."""

    def test_get_manager_returns_same_instance(self) -> None:
        """Multiple calls should return the same instance."""
        manager1 = get_mcp_client_manager()
        manager2 = get_mcp_client_manager()
        assert manager1 is manager2

    def test_singleton_state_persists(self) -> None:
        """State should persist across get_mcp_client_manager calls."""
        # Clear the cache to start fresh
        get_mcp_client_manager.cache_clear()

        manager1 = get_mcp_client_manager()
        manager1._state = ConnectionState.INITIALIZED

        manager2 = get_mcp_client_manager()
        assert manager2._state == ConnectionState.INITIALIZED


class TestCleanup:
    """Test cleanup and resource management."""

    async def test_cleanup_clears_clients(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Cleanup should clear all client connections."""
        await manager.initialize(temp_config_file)
        manager._clients["test"] = Mock()  # Simulate connection

        await manager.cleanup()
        assert len(manager._clients) == 0

    async def test_cleanup_clears_cache(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Cleanup should clear tool cache."""
        await manager.initialize(temp_config_file)
        manager._tool_cache["test"] = [Mock()]

        await manager.cleanup()
        assert len(manager._tool_cache) == 0

    async def test_cleanup_resets_config(
        self, manager: McpClientManager, temp_config_file: Path
    ) -> None:
        """Cleanup should reset configuration."""
        await manager.initialize(temp_config_file)
        assert manager._config is not None

        await manager.cleanup()
        assert manager._config is None


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_tool_not_found_on_server(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Should raise ToolNotFoundError if tool doesn't exist on server."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        # Return empty tool list
        mock_session.list_tools.return_value.tools = []

        await manager.initialize(temp_config_file)

        with pytest.raises(ToolNotFoundError, match="not found on server"):
            await manager.call_tool("test-server__nonexistent_tool", {})

    @patch("runtime.mcp_client.stdio_client")
    async def test_connection_failure(
        self,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
    ) -> None:
        """Should raise ServerConnectionError if connection fails."""
        # Mock stdio_client to raise an error
        mock_stdio.side_effect = Exception("Connection failed")

        await manager.initialize(temp_config_file)

        with pytest.raises(ServerConnectionError, match="Could not connect"):
            await manager.call_tool("test-server__test_tool", {})

    @patch("runtime.mcp_client.stdio_client")
    @patch("runtime.mcp_client.ClientSession")
    async def test_tool_execution_error(
        self,
        mock_session_class: Mock,
        mock_stdio: Mock,
        manager: McpClientManager,
        temp_config_file: Path,
        mock_session: AsyncMock,
        mock_tool: Mock,
        mock_stdio_context: AsyncMock,
    ) -> None:
        """Should raise ToolExecutionError if tool execution fails."""
        mock_stdio.return_value = mock_stdio_context
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.list_tools.return_value.tools = [mock_tool]
        # Mock tool execution failure
        mock_session.call_tool.side_effect = Exception("Tool failed")

        await manager.initialize(temp_config_file)

        with pytest.raises(ToolExecutionError, match="Failed to execute tool"):
            await manager.call_tool("test-server__test_tool", {})

    async def test_list_all_tools_with_no_enabled_servers(
        self, manager: McpClientManager, tmp_path: Path
    ) -> None:
        """Should return empty list if no servers are enabled."""
        config_dict = {
            "mcpServers": {
                "disabled-server": {
                    "command": "python",
                    "args": ["server.py"],
                    "disabled": True,
                }
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_dict))

        await manager.initialize(config_file)
        tools = await manager.list_all_tools()

        assert tools == []


class TestConvenienceFunction:
    """Test the call_mcp_tool convenience function."""

    @patch("runtime.mcp_client.get_mcp_client_manager")
    async def test_call_mcp_tool_uses_singleton(
        self, mock_get_manager: Mock, temp_config_file: Path
    ) -> None:
        """call_mcp_tool should use the singleton manager."""
        mock_manager = AsyncMock()
        mock_manager.call_tool = AsyncMock(return_value="result")
        mock_get_manager.return_value = mock_manager

        result = await call_mcp_tool("server__tool", {"param": "value"})

        mock_get_manager.assert_called_once()
        mock_manager.call_tool.assert_called_once_with("server__tool", {"param": "value"}, max_retries=1)
        assert result == "result"
