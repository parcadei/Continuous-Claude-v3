"""Tests for Settings tab integration into AgentMonitorApp (Phases 10-14).

TDD approach: Write tests first, then implement to make them pass.
"""

import inspect

import pytest


class TestPhase11SettingsImports:
    """Phase 11: Add imports for SettingsPanel and SettingsData."""

    def test_settings_data_importable_via_app(self):
        """SettingsData should be importable from app module."""
        # This works because the import statement in app.py makes it available
        from scripts.agent_monitor_tui.app import SettingsData

        # Verify it's the right class
        from scripts.agent_monitor_tui.poller import SettingsData as PollerSettingsData
        assert SettingsData is PollerSettingsData

    def test_settings_panel_importable_via_app(self):
        """SettingsPanel should be importable from app module."""
        from scripts.agent_monitor_tui.app import SettingsPanel

        # Verify it's the right class
        from scripts.agent_monitor_tui.widgets.settings_panel import SettingsPanel as WidgetSettingsPanel
        assert SettingsPanel is WidgetSettingsPanel

    def test_app_module_has_settings_imports_in_source(self):
        """The app.py source should contain the Settings imports."""
        import scripts.agent_monitor_tui.app as app_module

        source = inspect.getsource(app_module)
        assert "SettingsData" in source, "SettingsData not found in app.py imports"
        assert "SettingsPanel" in source, "SettingsPanel not found in app.py imports"


class TestPhase12SettingsTabPane:
    """Phase 12: Add Settings TabPane to compose() method."""

    def test_compose_source_has_settings_tabpane(self):
        """compose() method should include Settings TabPane."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        source = inspect.getsource(AgentMonitorApp.compose)

        # Check for Settings tab in compose
        assert 'TabPane("Settings"' in source or "TabPane('Settings'" in source, \
            "Settings TabPane not found in compose() method"
        assert 'id="settings"' in source or "id='settings'" in source, \
            "Settings TabPane should have id='settings'"

    def test_compose_source_yields_settings_panel(self):
        """compose() should yield SettingsPanel widget."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        source = inspect.getsource(AgentMonitorApp.compose)
        assert "SettingsPanel" in source, "SettingsPanel not found in compose() method"

    def test_settings_tab_comes_after_blackboard(self):
        """Settings tab should come after Blackboard in compose()."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        source = inspect.getsource(AgentMonitorApp.compose)

        # Find positions
        blackboard_pos = source.find("Blackboard")
        settings_pos = source.find("Settings")

        assert blackboard_pos > -1, "Blackboard not found in compose()"
        assert settings_pos > -1, "Settings not found in compose()"
        assert settings_pos > blackboard_pos, "Settings should come after Blackboard in compose()"


class TestPhase13SettingsPolling:
    """Phase 13: Add settings case to _poll_data() method."""

    def test_poll_data_has_settings_case(self):
        """_poll_data() should have a case for settings tab."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        source = inspect.getsource(AgentMonitorApp._poll_data)

        # Check for settings case
        assert "settings" in source, "_poll_data() should handle 'settings' tab"
        assert "poll_settings" in source, "_poll_data() should call poll_settings"

    def test_poll_data_passes_theme_to_poll_settings(self):
        """_poll_data() should pass theme_name to poll_settings."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        source = inspect.getsource(AgentMonitorApp._poll_data)

        assert "theme_name" in source, "_poll_data() should pass theme_name to poll_settings"

    def test_poll_data_updates_settings_panel(self):
        """_poll_data() should update SettingsPanel with data."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        source = inspect.getsource(AgentMonitorApp._poll_data)

        assert "SettingsPanel" in source, "_poll_data() should query for SettingsPanel"


class TestPhase14SettingsCss:
    """Phase 14: Add CSS styles to monitor.tcss."""

    def test_css_has_settings_panel_styles(self):
        """monitor.tcss should have SettingsPanel styles."""
        css_path = "/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agent_monitor_tui/monitor.tcss"
        with open(css_path) as f:
            css_content = f.read()

        assert "SettingsPanel" in css_content, "SettingsPanel CSS rules not found"

    def test_css_has_server_status_card_styles(self):
        """monitor.tcss should have ServerStatusCard styles."""
        css_path = "/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agent_monitor_tui/monitor.tcss"
        with open(css_path) as f:
            css_content = f.read()

        assert "ServerStatusCard" in css_content, "ServerStatusCard CSS rules not found"

    def test_css_has_settings_section_comment(self):
        """monitor.tcss should have Settings section comment."""
        css_path = "/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agent_monitor_tui/monitor.tcss"
        with open(css_path) as f:
            css_content = f.read()

        assert "Settings Panel" in css_content, "Settings Panel section comment not found"


class TestPhase10SettingsBinding:
    """Phase 10: Add key `4` binding for Settings tab."""

    def test_binding_4_exists_in_bindings_list(self):
        """Key '4' should be in BINDINGS list."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        binding_keys = [b.key for b in AgentMonitorApp.BINDINGS]
        assert "4" in binding_keys, "Missing binding for key '4'"

    def test_binding_4_switches_to_settings_tab(self):
        """Binding for '4' should switch to settings tab."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        # Find the binding with key "4"
        binding = None
        for b in AgentMonitorApp.BINDINGS:
            if b.key == "4":
                binding = b
                break

        assert binding is not None, "Binding for key '4' not found"
        assert "settings" in binding.action, f"Expected action to contain 'settings', got {binding.action}"
        assert "switch_tab" in binding.action, f"Expected action to be switch_tab, got {binding.action}"

    def test_binding_4_has_show_true(self):
        """Binding for '4' should be visible in footer."""
        from scripts.agent_monitor_tui.app import AgentMonitorApp

        binding = None
        for b in AgentMonitorApp.BINDINGS:
            if b.key == "4":
                binding = b
                break

        assert binding is not None
        assert binding.show is True, "Binding for '4' should have show=True"
