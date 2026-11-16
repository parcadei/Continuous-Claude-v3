"""Tests for Settings tab polling functionality.

TDD tests for Phases 1-6 of the Settings Tab implementation.
"""

from __future__ import annotations

import pytest
from datetime import datetime


class TestPhase1ServerStatus:
    """Phase 1: ServerStatus dataclass."""

    def test_server_status_import(self):
        """Test that ServerStatus can be imported from poller."""
        from scripts.agent_monitor_tui.poller import ServerStatus
        assert ServerStatus is not None

    def test_server_status_instantiation(self):
        """Test that ServerStatus can be instantiated with required fields."""
        from scripts.agent_monitor_tui.poller import ServerStatus

        status = ServerStatus(name="test", url="http://localhost:8080")

        assert status.name == "test"
        assert status.url == "http://localhost:8080"

    def test_server_status_default_values(self):
        """Test that ServerStatus has correct default values."""
        from scripts.agent_monitor_tui.poller import ServerStatus

        status = ServerStatus(name="test", url="http://localhost:8080")

        assert status.healthy is False
        assert status.last_check is None
        assert status.error is None

    def test_server_status_with_all_fields(self):
        """Test that ServerStatus accepts all fields."""
        from scripts.agent_monitor_tui.poller import ServerStatus

        now = datetime.now()
        status = ServerStatus(
            name="Claude Proxy",
            url="http://localhost:8080",
            healthy=True,
            last_check=now,
            error=None,
        )

        assert status.name == "Claude Proxy"
        assert status.url == "http://localhost:8080"
        assert status.healthy is True
        assert status.last_check == now
        assert status.error is None

    def test_server_status_with_error(self):
        """Test that ServerStatus can store error messages."""
        from scripts.agent_monitor_tui.poller import ServerStatus

        status = ServerStatus(
            name="test",
            url="http://localhost:8080",
            healthy=False,
            error="Connection refused",
        )

        assert status.healthy is False
        assert status.error == "Connection refused"


class TestPhase2SettingsData:
    """Phase 2: SettingsData dataclass."""

    def test_settings_data_import(self):
        """Test that SettingsData can be imported from poller."""
        from scripts.agent_monitor_tui.poller import SettingsData
        assert SettingsData is not None

    def test_settings_data_instantiation(self):
        """Test that SettingsData can be instantiated with defaults."""
        from scripts.agent_monitor_tui.poller import SettingsData

        data = SettingsData()

        assert data is not None

    def test_settings_data_default_servers(self):
        """Test that SettingsData has default ServerStatus objects."""
        from scripts.agent_monitor_tui.poller import SettingsData

        data = SettingsData()

        assert data.claude_proxy.name == "Claude Proxy"
        assert data.claude_proxy.url == "http://localhost:8080"
        assert data.agentica_server.name == "Agentica Server"
        assert data.agentica_server.url == "http://localhost:8765"

    def test_settings_data_default_values(self):
        """Test that SettingsData has correct default values."""
        from scripts.agent_monitor_tui.poller import SettingsData

        data = SettingsData()

        assert data.current_theme == "dark"
        assert data.poll_interval == 1.0
        assert data.db_path == ""

    def test_settings_data_servers_not_healthy_by_default(self):
        """Test that servers are not healthy by default."""
        from scripts.agent_monitor_tui.poller import SettingsData

        data = SettingsData()

        assert data.claude_proxy.healthy is False
        assert data.agentica_server.healthy is False


class TestPhase3HttpxImport:
    """Phase 3: httpx import in poller."""

    def test_httpx_is_available(self):
        """Test that httpx module is available in poller."""
        # Import poller and verify httpx is accessible
        import scripts.agent_monitor_tui.poller as poller_module
        import httpx

        # The poller module should have httpx in its namespace after import
        assert hasattr(poller_module, 'httpx') or 'httpx' in dir(poller_module), \
            "httpx not imported in poller module"

    def test_httpx_async_client_available(self):
        """Test that httpx.AsyncClient is available for health checks."""
        import httpx
        assert hasattr(httpx, 'AsyncClient')


class TestPhase4CheckServerHealth:
    """Phase 4: _check_server_health method in DataPoller."""

    def test_method_exists(self):
        """Test that _check_server_health method exists on DataPoller."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        assert hasattr(poller, '_check_server_health')

    @pytest.mark.asyncio
    async def test_returns_tuple(self):
        """Test that _check_server_health returns a tuple."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        result = await poller._check_server_health("http://localhost:9999")

        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_refused(self):
        """Test that connection refused returns (False, error_message)."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        healthy, error = await poller._check_server_health("http://localhost:9999")

        assert healthy is False
        assert error is not None
        assert "refused" in error.lower() or "connect" in error.lower()

    @pytest.mark.asyncio
    async def test_timeout_parameter(self):
        """Test that timeout parameter is accepted."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        # Should not raise - just testing the parameter is accepted
        result = await poller._check_server_health("http://localhost:9999", timeout=0.5)
        assert isinstance(result, tuple)


class TestPhase5PollSettings:
    """Phase 5: poll_settings method in DataPoller."""

    def test_method_exists(self):
        """Test that poll_settings method exists on DataPoller."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        assert hasattr(poller, 'poll_settings')

    @pytest.mark.asyncio
    async def test_returns_settings_data(self):
        """Test that poll_settings returns SettingsData."""
        from scripts.agent_monitor_tui.poller import DataPoller, SettingsData

        poller = DataPoller()
        await poller.connect()
        result = await poller.poll_settings()

        assert isinstance(result, SettingsData)

    @pytest.mark.asyncio
    async def test_accepts_theme_parameter(self):
        """Test that poll_settings accepts current_theme parameter."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        await poller.connect()
        result = await poller.poll_settings(current_theme="nord")

        assert result.current_theme == "nord"

    @pytest.mark.asyncio
    async def test_server_statuses_populated(self):
        """Test that server statuses are populated with health check results."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        await poller.connect()
        result = await poller.poll_settings()

        # Both servers should be checked
        assert result.claude_proxy.name == "Claude Proxy"
        assert result.claude_proxy.url == "http://localhost:8080"
        assert result.claude_proxy.last_check is not None

        assert result.agentica_server.name == "Agentica Server"
        assert result.agentica_server.url == "http://localhost:8765"
        assert result.agentica_server.last_check is not None

    @pytest.mark.asyncio
    async def test_server_health_is_boolean(self):
        """Test that server health status is a boolean value."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        await poller.connect()
        result = await poller.poll_settings()

        # Health status should be boolean (servers may or may not be running)
        assert isinstance(result.claude_proxy.healthy, bool)
        assert isinstance(result.agentica_server.healthy, bool)

    @pytest.mark.asyncio
    async def test_poll_interval_default(self):
        """Test that poll_interval has default value."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        await poller.connect()
        result = await poller.poll_settings()

        assert result.poll_interval == 1.0


class TestPhase6Exports:
    """Phase 6: Verify exports work from poller module."""

    def test_server_status_exported(self):
        """Test that ServerStatus is importable from poller."""
        from scripts.agent_monitor_tui.poller import ServerStatus
        assert ServerStatus is not None

    def test_settings_data_exported(self):
        """Test that SettingsData is importable from poller."""
        from scripts.agent_monitor_tui.poller import SettingsData
        assert SettingsData is not None

    def test_both_classes_importable_together(self):
        """Test that both classes can be imported together."""
        from scripts.agent_monitor_tui.poller import ServerStatus, SettingsData

        # Verify they are the correct types
        assert hasattr(ServerStatus, '__dataclass_fields__')
        assert hasattr(SettingsData, '__dataclass_fields__')

    def test_settings_data_uses_server_status(self):
        """Test that SettingsData uses ServerStatus as field type."""
        from scripts.agent_monitor_tui.poller import ServerStatus, SettingsData

        data = SettingsData()
        assert isinstance(data.claude_proxy, ServerStatus)
        assert isinstance(data.agentica_server, ServerStatus)

    def test_data_poller_exported(self):
        """Test that DataPoller is still exportable after changes."""
        from scripts.agent_monitor_tui.poller import DataPoller
        assert DataPoller is not None

    def test_existing_exports_still_work(self):
        """Test that existing exports (HomeData, AgentsData, BlackboardData) still work."""
        from scripts.agent_monitor_tui.poller import (
            HomeData,
            AgentsData,
            BlackboardData,
            ServerStatus,
            SettingsData,
            DataPoller,
        )

        assert HomeData is not None
        assert AgentsData is not None
        assert BlackboardData is not None
        assert ServerStatus is not None
        assert SettingsData is not None
        assert DataPoller is not None
