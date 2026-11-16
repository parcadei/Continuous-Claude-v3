"""Tests for Settings Panel widgets.

TDD tests for Phases 7-9 of Settings Tab implementation:
- Phase 7: ServerStatusCard widget
- Phase 8: SettingsPanel container widget
- Phase 9: Export from widgets package
"""

import pytest
from datetime import datetime


class TestServerStatusCard:
    """Tests for ServerStatusCard widget (Phase 7)."""

    def test_import_server_status_card(self):
        """ServerStatusCard should be importable from settings_panel module."""
        from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard
        assert ServerStatusCard is not None

    def test_server_status_card_has_reactive_status(self):
        """ServerStatusCard should have a reactive 'status' property."""
        from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard
        from scripts.agent_monitor_tui.poller import ServerStatus

        # Check that 'status' is defined as a reactive property
        assert hasattr(ServerStatusCard, 'status')

    def test_server_status_card_accepts_status_in_init(self):
        """ServerStatusCard should accept a ServerStatus in __init__."""
        from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard
        from scripts.agent_monitor_tui.poller import ServerStatus

        status = ServerStatus(
            name="Test Server",
            url="http://localhost:9999",
            healthy=True,
            last_check=datetime.now(),
        )
        # Should not raise
        card = ServerStatusCard(status=status, id="test-card")
        assert card is not None

    def test_server_status_card_has_watch_status_method(self):
        """ServerStatusCard should have watch_status method for reactive updates."""
        from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard

        assert hasattr(ServerStatusCard, 'watch_status')
        assert callable(getattr(ServerStatusCard, 'watch_status'))

    def test_server_status_card_inherits_from_static(self):
        """ServerStatusCard should inherit from textual.widgets.Static."""
        from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard
        from textual.widgets import Static

        assert issubclass(ServerStatusCard, Static)


class TestSettingsPanel:
    """Tests for SettingsPanel widget (Phase 8)."""

    def test_import_settings_panel(self):
        """SettingsPanel should be importable from settings_panel module."""
        from scripts.agent_monitor_tui.widgets.settings_panel import SettingsPanel
        assert SettingsPanel is not None

    def test_settings_panel_has_reactive_data(self):
        """SettingsPanel should have a reactive 'data' property."""
        from scripts.agent_monitor_tui.widgets.settings_panel import SettingsPanel

        assert hasattr(SettingsPanel, 'data')

    def test_settings_panel_has_watch_data_method(self):
        """SettingsPanel should have watch_data method for reactive updates."""
        from scripts.agent_monitor_tui.widgets.settings_panel import SettingsPanel

        assert hasattr(SettingsPanel, 'watch_data')
        assert callable(getattr(SettingsPanel, 'watch_data'))

    def test_settings_panel_inherits_from_static(self):
        """SettingsPanel should inherit from textual.widgets.Static."""
        from scripts.agent_monitor_tui.widgets.settings_panel import SettingsPanel
        from textual.widgets import Static

        assert issubclass(SettingsPanel, Static)

    def test_settings_panel_instantiates(self):
        """SettingsPanel should instantiate without arguments."""
        from scripts.agent_monitor_tui.widgets.settings_panel import SettingsPanel

        # Should not raise
        panel = SettingsPanel()
        assert panel is not None


class TestWidgetExports:
    """Tests for widget package exports (Phase 9)."""

    def test_settings_panel_exported_from_widgets_package(self):
        """SettingsPanel should be importable from widgets package."""
        from scripts.agent_monitor_tui.widgets import SettingsPanel
        assert SettingsPanel is not None

    def test_settings_panel_in_all(self):
        """SettingsPanel should be in widgets.__all__."""
        from scripts.agent_monitor_tui import widgets

        assert hasattr(widgets, '__all__')
        assert 'SettingsPanel' in widgets.__all__

    def test_server_status_card_exported(self):
        """ServerStatusCard should also be importable from settings_panel."""
        from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard
        assert ServerStatusCard is not None


class TestIntegration:
    """Integration tests for settings widgets with poller data."""

    def test_server_status_card_with_healthy_status(self):
        """ServerStatusCard should handle healthy server status."""
        from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard
        from scripts.agent_monitor_tui.poller import ServerStatus

        status = ServerStatus(
            name="Claude Proxy",
            url="http://localhost:8080",
            healthy=True,
            last_check=datetime.now(),
            error=None,
        )
        card = ServerStatusCard(status=status)
        assert card.status.healthy is True
        assert card.status.name == "Claude Proxy"

    def test_server_status_card_with_unhealthy_status(self):
        """ServerStatusCard should handle unhealthy server status with error."""
        from scripts.agent_monitor_tui.widgets.settings_panel import ServerStatusCard
        from scripts.agent_monitor_tui.poller import ServerStatus

        status = ServerStatus(
            name="Agentica Server",
            url="http://localhost:8765",
            healthy=False,
            last_check=datetime.now(),
            error="Connection refused",
        )
        card = ServerStatusCard(status=status)
        assert card.status.healthy is False
        assert card.status.error == "Connection refused"

    def test_settings_panel_uses_settings_data(self):
        """SettingsPanel data property should work with SettingsData type."""
        from scripts.agent_monitor_tui.widgets.settings_panel import SettingsPanel
        from scripts.agent_monitor_tui.poller import SettingsData

        panel = SettingsPanel()
        # The data property should accept SettingsData type
        # (reactive properties are defined at class level)
        assert SettingsPanel.data is not None
