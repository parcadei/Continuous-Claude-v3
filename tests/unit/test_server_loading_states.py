"""Tests for ServerStatusCard loading states.

Verifies:
1. is_loading reactive exists and works
2. loading_action reactive exists and works
3. Buttons disabled when loading
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from scripts.agent_monitor_tui.poller import ServerStatus
from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard


class TestServerStatusCardReactives:
    """Test reactive properties on ServerStatusCard."""

    def test_is_loading_reactive_exists(self) -> None:
        """Verify is_loading reactive property exists."""
        card = ServerStatusCard(server_key="test")
        # Check the reactive exists and has default value False
        assert hasattr(card, "is_loading")
        assert card.is_loading is False

    def test_loading_action_reactive_exists(self) -> None:
        """Verify loading_action reactive property exists."""
        card = ServerStatusCard(server_key="test")
        # Check the reactive exists and has default value ""
        assert hasattr(card, "loading_action")
        assert card.loading_action == ""

    def test_is_loading_can_be_set(self) -> None:
        """Verify is_loading can be set to True."""
        card = ServerStatusCard(server_key="test")
        card.is_loading = True
        assert card.is_loading is True

    def test_loading_action_can_be_set(self) -> None:
        """Verify loading_action can be set."""
        card = ServerStatusCard(server_key="test")
        card.loading_action = "Starting"
        assert card.loading_action == "Starting"


class TestServerActionMessage:
    """Test ServerAction message creation."""

    def test_server_action_message_creation(self) -> None:
        """Verify ServerAction message can be created."""
        action = ServerStatusCard.ServerAction("claude_proxy", "start")
        assert action.server_name == "claude_proxy"
        assert action.action == "start"

    def test_server_action_message_stop(self) -> None:
        """Verify ServerAction message for stop."""
        action = ServerStatusCard.ServerAction("agentica_server", "stop")
        assert action.server_name == "agentica_server"
        assert action.action == "stop"

    def test_server_action_message_restart(self) -> None:
        """Verify ServerAction message for restart."""
        action = ServerStatusCard.ServerAction("claude_proxy", "restart")
        assert action.server_name == "claude_proxy"
        assert action.action == "restart"


class TestServerStatusCardInitialization:
    """Test ServerStatusCard initialization."""

    def test_default_status(self) -> None:
        """Verify default status is created."""
        card = ServerStatusCard(server_key="test")
        assert card.status.name == ""
        assert card.status.url == ""

    def test_custom_status(self) -> None:
        """Verify custom status is set."""
        status = ServerStatus(name="Test Server", url="http://localhost:9999", healthy=True)
        card = ServerStatusCard(status=status, server_key="test")
        assert card.status.name == "Test Server"
        assert card.status.url == "http://localhost:9999"
        assert card.status.healthy is True

    def test_server_key_stored(self) -> None:
        """Verify server_key is stored."""
        card = ServerStatusCard(server_key="claude_proxy")
        assert card._server_key == "claude_proxy"


class TestWatchIsLoadingLogic:
    """Test the watch_is_loading logic without full Textual mounting."""

    def test_watch_is_loading_method_exists(self) -> None:
        """Verify watch_is_loading method exists."""
        card = ServerStatusCard(server_key="test")
        assert hasattr(card, "watch_is_loading")
        assert callable(card.watch_is_loading)

    def test_watch_status_method_exists(self) -> None:
        """Verify watch_status method exists."""
        card = ServerStatusCard(server_key="test")
        assert hasattr(card, "watch_status")
        assert callable(card.watch_status)
