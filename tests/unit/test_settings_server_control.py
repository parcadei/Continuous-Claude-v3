"""Tests for server control functionality in Settings tab.

TDD tests for:
- start_server(name) - Start server with subprocess.Popen
- stop_server(name) - Kill server by PID
- restart_server(name) - Stop then start
- kill_orphans(port) - Kill any process using the port
"""

from __future__ import annotations

import subprocess
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestServerControlMethods:
    """Test that server control methods exist on DataPoller."""

    def test_start_server_method_exists(self):
        """Test that start_server method exists on DataPoller."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        assert hasattr(poller, 'start_server')
        assert callable(poller.start_server)

    def test_stop_server_method_exists(self):
        """Test that stop_server method exists on DataPoller."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        assert hasattr(poller, 'stop_server')
        assert callable(poller.stop_server)

    def test_restart_server_method_exists(self):
        """Test that restart_server method exists on DataPoller."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        assert hasattr(poller, 'restart_server')
        assert callable(poller.restart_server)

    def test_kill_orphans_method_exists(self):
        """Test that kill_orphans method exists on DataPoller."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        assert hasattr(poller, 'kill_orphans')
        assert callable(poller.kill_orphans)

    def test_server_pids_attribute_exists(self):
        """Test that _server_pids class/instance attribute exists."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        assert hasattr(poller, '_server_pids')
        assert isinstance(poller._server_pids, dict)


class TestServerConfigs:
    """Test server configuration constants."""

    def test_server_configs_exists(self):
        """Test that SERVER_CONFIGS constant exists."""
        from scripts.agent_monitor_tui.poller import SERVER_CONFIGS

        assert SERVER_CONFIGS is not None
        assert isinstance(SERVER_CONFIGS, dict)

    def test_server_configs_has_proxy(self):
        """Test that SERVER_CONFIGS contains claude_proxy config."""
        from scripts.agent_monitor_tui.poller import SERVER_CONFIGS

        assert "claude_proxy" in SERVER_CONFIGS
        config = SERVER_CONFIGS["claude_proxy"]
        assert "command" in config
        assert "port" in config
        assert config["port"] == 8080

    def test_server_configs_has_agentica(self):
        """Test that SERVER_CONFIGS contains agentica_server config."""
        from scripts.agent_monitor_tui.poller import SERVER_CONFIGS

        assert "agentica_server" in SERVER_CONFIGS
        config = SERVER_CONFIGS["agentica_server"]
        assert "command" in config
        assert "port" in config
        assert config["port"] == 8765


class TestStartServer:
    """Tests for start_server method."""

    @pytest.mark.asyncio
    async def test_start_server_returns_success(self):
        """Test that start_server returns success tuple."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch.object(poller, 'kill_orphans', new_callable=AsyncMock) as mock_kill:
            mock_kill.return_value = (True, None)
            with patch('subprocess.Popen') as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_process.poll.return_value = None  # Still running
                mock_popen.return_value = mock_process

                success, error = await poller.start_server("claude_proxy")

                assert success is True
                assert error is None

    @pytest.mark.asyncio
    async def test_start_server_stores_pid(self):
        """Test that start_server stores PID in _server_pids."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch.object(poller, 'kill_orphans', new_callable=AsyncMock) as mock_kill:
            mock_kill.return_value = (True, None)
            with patch('subprocess.Popen') as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process

                await poller.start_server("claude_proxy")

                assert "claude_proxy" in poller._server_pids
                assert poller._server_pids["claude_proxy"] == 12345

    @pytest.mark.asyncio
    async def test_start_server_calls_kill_orphans_first(self):
        """Test that start_server kills orphans before starting."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch.object(poller, 'kill_orphans', new_callable=AsyncMock) as mock_kill:
            mock_kill.return_value = (True, None)
            with patch('subprocess.Popen') as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process

                await poller.start_server("claude_proxy")

                # kill_orphans should be called with port 8080
                mock_kill.assert_called_once_with(8080)

    @pytest.mark.asyncio
    async def test_start_server_invalid_name_returns_error(self):
        """Test that start_server returns error for invalid server name."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        success, error = await poller.start_server("invalid_server")

        assert success is False
        assert error is not None
        assert "unknown server" in error.lower()

    @pytest.mark.asyncio
    async def test_start_server_spawns_correct_command(self):
        """Test that start_server spawns the correct command."""
        from scripts.agent_monitor_tui.poller import DataPoller, SERVER_CONFIGS

        poller = DataPoller()

        with patch.object(poller, 'kill_orphans', new_callable=AsyncMock) as mock_kill:
            mock_kill.return_value = (True, None)
            with patch('subprocess.Popen') as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process

                await poller.start_server("claude_proxy")

                # Check that Popen was called with correct command
                expected_cmd = SERVER_CONFIGS["claude_proxy"]["command"]
                mock_popen.assert_called_once()
                call_args = mock_popen.call_args
                assert call_args[0][0] == expected_cmd


class TestStopServer:
    """Tests for stop_server method."""

    @pytest.mark.asyncio
    async def test_stop_server_returns_success_when_pid_exists(self):
        """Test that stop_server returns success when PID exists."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        poller._server_pids["claude_proxy"] = 12345

        with patch('os.kill') as mock_kill:
            success, error = await poller.stop_server("claude_proxy")

            assert success is True
            assert error is None
            mock_kill.assert_called()

    @pytest.mark.asyncio
    async def test_stop_server_removes_pid_from_tracking(self):
        """Test that stop_server removes PID from _server_pids."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        poller._server_pids["claude_proxy"] = 12345

        with patch('os.kill'):
            await poller.stop_server("claude_proxy")

            assert "claude_proxy" not in poller._server_pids

    @pytest.mark.asyncio
    async def test_stop_server_calls_sigterm(self):
        """Test that stop_server sends SIGTERM signal."""
        from scripts.agent_monitor_tui.poller import DataPoller
        import signal

        poller = DataPoller()
        poller._server_pids["claude_proxy"] = 12345

        with patch('os.kill') as mock_kill:
            await poller.stop_server("claude_proxy")

            # Should call os.kill with SIGTERM
            mock_kill.assert_called_with(12345, signal.SIGTERM)

    @pytest.mark.asyncio
    async def test_stop_server_returns_error_when_no_pid(self):
        """Test that stop_server returns error when no PID tracked."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        success, error = await poller.stop_server("claude_proxy")

        assert success is False
        assert error is not None
        assert "not running" in error.lower() or "no pid" in error.lower()

    @pytest.mark.asyncio
    async def test_stop_server_handles_os_error(self):
        """Test that stop_server handles OSError gracefully."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        poller._server_pids["claude_proxy"] = 12345

        with patch('os.kill') as mock_kill:
            mock_kill.side_effect = OSError("No such process")

            success, error = await poller.stop_server("claude_proxy")

            # Should still succeed (process already dead)
            assert success is True
            # PID should be removed
            assert "claude_proxy" not in poller._server_pids


class TestRestartServer:
    """Tests for restart_server method."""

    @pytest.mark.asyncio
    async def test_restart_server_calls_stop_then_start(self):
        """Test that restart_server calls stop_server then start_server."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch.object(poller, 'stop_server', new_callable=AsyncMock) as mock_stop:
            mock_stop.return_value = (True, None)
            with patch.object(poller, 'start_server', new_callable=AsyncMock) as mock_start:
                mock_start.return_value = (True, None)

                success, error = await poller.restart_server("claude_proxy")

                mock_stop.assert_called_once_with("claude_proxy")
                mock_start.assert_called_once_with("claude_proxy")
                assert success is True
                assert error is None

    @pytest.mark.asyncio
    async def test_restart_server_still_starts_if_stop_fails(self):
        """Test that restart continues to start even if stop fails (server wasn't running)."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch.object(poller, 'stop_server', new_callable=AsyncMock) as mock_stop:
            mock_stop.return_value = (False, "Server not running")
            with patch.object(poller, 'start_server', new_callable=AsyncMock) as mock_start:
                mock_start.return_value = (True, None)

                success, error = await poller.restart_server("claude_proxy")

                # Should still call start_server
                mock_start.assert_called_once_with("claude_proxy")
                assert success is True

    @pytest.mark.asyncio
    async def test_restart_server_returns_start_error_if_start_fails(self):
        """Test that restart returns start error if start fails."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch.object(poller, 'stop_server', new_callable=AsyncMock) as mock_stop:
            mock_stop.return_value = (True, None)
            with patch.object(poller, 'start_server', new_callable=AsyncMock) as mock_start:
                mock_start.return_value = (False, "Failed to start")

                success, error = await poller.restart_server("claude_proxy")

                assert success is False
                assert error == "Failed to start"


class TestKillOrphans:
    """Tests for kill_orphans method."""

    @pytest.mark.asyncio
    async def test_kill_orphans_returns_tuple(self):
        """Test that kill_orphans returns (success, error) tuple."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch('subprocess.run') as mock_run:
            # No processes found
            mock_run.return_value = MagicMock(stdout="", returncode=0)

            result = await poller.kill_orphans(8080)

            assert isinstance(result, tuple)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_kill_orphans_uses_lsof(self):
        """Test that kill_orphans uses lsof to find processes."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)

            await poller.kill_orphans(8080)

            # Should call lsof with the port
            call_args = mock_run.call_args_list[0]
            cmd = call_args[0][0]
            assert "lsof" in cmd
            assert "8080" in cmd or ":8080" in " ".join(cmd)

    @pytest.mark.asyncio
    async def test_kill_orphans_kills_found_processes(self):
        """Test that kill_orphans kills processes found on port."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch('subprocess.run') as mock_run:
            # First call: lsof returns a process
            lsof_output = """COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
python  12345 user   3u  IPv4  12345      0t0  TCP *:8080 (LISTEN)"""
            mock_run.side_effect = [
                MagicMock(stdout=lsof_output, returncode=0),  # lsof
                MagicMock(returncode=0),  # kill
            ]

            with patch('os.kill') as mock_kill:
                success, error = await poller.kill_orphans(8080)

                # Should attempt to kill PID 12345
                assert success is True

    @pytest.mark.asyncio
    async def test_kill_orphans_returns_success_when_no_processes(self):
        """Test that kill_orphans returns success when no processes found."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()

        with patch('subprocess.run') as mock_run:
            # lsof returns empty (no processes)
            mock_run.return_value = MagicMock(stdout="", returncode=1)

            success, error = await poller.kill_orphans(8080)

            assert success is True
            assert error is None


class TestServerStatusWithProcess:
    """Test that ServerStatus includes process info."""

    def test_server_status_has_pid_field(self):
        """Test that ServerStatus has optional pid field."""
        from scripts.agent_monitor_tui.poller import ServerStatus

        status = ServerStatus(name="test", url="http://localhost:8080", pid=12345)
        assert status.pid == 12345

    def test_server_status_pid_default_none(self):
        """Test that ServerStatus pid defaults to None."""
        from scripts.agent_monitor_tui.poller import ServerStatus

        status = ServerStatus(name="test", url="http://localhost:8080")
        assert status.pid is None


class TestPollSettingsIncludesPids:
    """Test that poll_settings includes tracked PIDs."""

    @pytest.mark.asyncio
    async def test_poll_settings_includes_tracked_pid(self):
        """Test that poll_settings includes PID in ServerStatus."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        await poller.connect()

        # Simulate a tracked server
        poller._server_pids["claude_proxy"] = 12345

        result = await poller.poll_settings()

        # The proxy status should include the PID
        assert result.claude_proxy.pid == 12345

    @pytest.mark.asyncio
    async def test_poll_settings_pid_none_when_not_tracked(self):
        """Test that poll_settings returns None pid when not tracked."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        await poller.connect()

        result = await poller.poll_settings()

        # No tracked PIDs, so should be None
        assert result.claude_proxy.pid is None
        assert result.agentica_server.pid is None


class TestCleanShutdown:
    """Test clean shutdown of tracked processes."""

    @pytest.mark.asyncio
    async def test_disconnect_stops_all_servers(self):
        """Test that disconnect() stops all tracked servers."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        poller._server_pids["claude_proxy"] = 12345
        poller._server_pids["agentica_server"] = 67890

        with patch('os.kill') as mock_kill:
            await poller.disconnect()

            # Should have killed both processes
            assert mock_kill.call_count >= 2

    @pytest.mark.asyncio
    async def test_disconnect_clears_pid_tracking(self):
        """Test that disconnect() clears _server_pids."""
        from scripts.agent_monitor_tui.poller import DataPoller

        poller = DataPoller()
        await poller.connect()
        poller._server_pids["claude_proxy"] = 12345

        with patch('os.kill'):
            await poller.disconnect()

            assert len(poller._server_pids) == 0
