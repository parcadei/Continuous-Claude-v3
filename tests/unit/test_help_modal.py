"""Tests for HelpScreen modal widget.

TDD tests for dismissable help modal:
1. HelpScreen should be importable
2. HelpScreen should inherit from ModalScreen
3. HelpScreen should display help content
4. HelpScreen should dismiss on any keypress
5. AgentMonitorApp.action_show_help should push HelpScreen
"""

import pytest
from unittest.mock import MagicMock, patch


class TestHelpScreenImport:
    """Tests for HelpScreen import and basic structure."""

    def test_import_help_screen(self):
        """HelpScreen should be importable from help_screen module."""
        from scripts.agent_monitor_tui.widgets.help_screen import HelpScreen
        assert HelpScreen is not None

    def test_help_screen_inherits_from_modal_screen(self):
        """HelpScreen should inherit from textual.screen.ModalScreen."""
        from scripts.agent_monitor_tui.widgets.help_screen import HelpScreen
        from textual.screen import ModalScreen

        assert issubclass(HelpScreen, ModalScreen)

    def test_help_screen_has_help_text_constant(self):
        """HelpScreen should have HELP_TEXT constant with help content."""
        from scripts.agent_monitor_tui.widgets.help_screen import HELP_TEXT

        assert isinstance(HELP_TEXT, str)
        assert "Navigation" in HELP_TEXT
        assert "Press any key to close" in HELP_TEXT


class TestHelpScreenBehavior:
    """Tests for HelpScreen behavior."""

    def test_help_screen_instantiates(self):
        """HelpScreen should instantiate without arguments."""
        from scripts.agent_monitor_tui.widgets.help_screen import HelpScreen

        screen = HelpScreen()
        assert screen is not None

    def test_help_screen_has_on_key_handler(self):
        """HelpScreen should have on_key method for dismissing on any keypress."""
        from scripts.agent_monitor_tui.widgets.help_screen import HelpScreen

        assert hasattr(HelpScreen, 'on_key')
        assert callable(getattr(HelpScreen, 'on_key'))

    def test_help_screen_on_key_calls_dismiss(self):
        """HelpScreen.on_key should call app.pop_screen to dismiss."""
        from scripts.agent_monitor_tui.widgets.help_screen import HelpScreen
        from textual.events import Key

        screen = HelpScreen()

        # Create a mock key event
        mock_event = MagicMock(spec=Key)
        mock_event.key = "a"

        # Patch the app property to return a mock
        mock_app = MagicMock()
        with patch.object(type(screen), 'app', new_callable=lambda: property(lambda self: mock_app)):
            # Call on_key
            screen.on_key(mock_event)

            # Should have called app.pop_screen()
            mock_app.pop_screen.assert_called_once()


class TestHelpScreenCompose:
    """Tests for HelpScreen compose method."""

    def test_help_screen_has_compose_method(self):
        """HelpScreen should have compose method."""
        from scripts.agent_monitor_tui.widgets.help_screen import HelpScreen

        assert hasattr(HelpScreen, 'compose')
        assert callable(getattr(HelpScreen, 'compose'))


class TestWidgetExports:
    """Tests for widget package exports."""

    def test_help_screen_exported_from_widgets_package(self):
        """HelpScreen should be importable from widgets package."""
        from scripts.agent_monitor_tui.widgets import HelpScreen
        assert HelpScreen is not None

    def test_help_screen_in_all(self):
        """HelpScreen should be in widgets.__all__."""
        from scripts.agent_monitor_tui import widgets

        assert hasattr(widgets, '__all__')
        assert 'HelpScreen' in widgets.__all__


class TestAppIntegration:
    """Tests for AgentMonitorApp integration with HelpScreen."""

    def test_app_action_show_help_pushes_screen(self):
        """action_show_help should push HelpScreen instead of using notify."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp
        from scripts.agent_monitor_tui.widgets.help_screen import HelpScreen

        app = AgentMonitorApp()
        app.push_screen = MagicMock()

        # Call action_show_help
        app.action_show_help()

        # Should have called push_screen with a HelpScreen instance
        app.push_screen.assert_called_once()
        call_args = app.push_screen.call_args
        assert isinstance(call_args[0][0], HelpScreen)

    def test_app_does_not_use_notify_for_help(self):
        """action_show_help should NOT use notify (the old implementation)."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        app = AgentMonitorApp()
        app.notify = MagicMock()
        app.push_screen = MagicMock()

        # Call action_show_help
        app.action_show_help()

        # notify should NOT have been called
        app.notify.assert_not_called()
