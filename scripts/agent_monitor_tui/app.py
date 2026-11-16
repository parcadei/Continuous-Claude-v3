"""Agent Monitor TUI - Main Application.

Textual app with three tabs:
1. Home - System overview (CPU, RAM, agent count)
2. Agents - Pattern-specific visualizers
3. Blackboard - Read-only blackboard entries

Key bindings:
- 1/2/3: Switch tabs
- t: Cycle themes
- r: Force refresh
- q: Quit

Uses Worker pattern for async polling (NOT set_interval).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, TabbedContent, TabPane

from scripts.agent_monitor_tui.themes import (
    THEMES,
    THEME_NAMES,
    next_theme,
)
from scripts.agent_monitor_tui.poller import (
    DataPoller,
    HomeData,
    AgentsData,
    BlackboardData,
    SettingsData,
)
from scripts.agent_monitor_tui.widgets.home_panel import HomePanel
from scripts.agent_monitor_tui.widgets.agent_view import AgentPanel
from scripts.agent_monitor_tui.widgets.blackboard_view import BlackboardPanel
from scripts.agent_monitor_tui.widgets.settings_panel import SettingsPanel, ServerStatusCard
from scripts.agent_monitor_tui.widgets.help_screen import HelpScreen


class AgentMonitorApp(App):
    """Agent Monitor TUI Application.

    Args:
        auto_start_servers: If True, automatically start Claude Proxy and
            Agentica Server on launch. Defaults to True.
    """

    TITLE = "Agent Monitor"
    SUB_TITLE = "Agentica Pattern Visualizer"

    # Load CSS from file
    CSS_PATH = Path(__file__).parent / "monitor.tcss"

    # Keyboard bindings
    BINDINGS = [
        Binding("1", "switch_tab('home')", "Home", show=True),
        Binding("2", "switch_tab('agents')", "Agents", show=True),
        Binding("3", "switch_tab('blackboard')", "Blackboard", show=True),
        Binding("4", "switch_tab('settings')", "Settings", show=True),
        Binding("t", "toggle_theme", "Theme", show=True),
        Binding("r", "force_refresh", "Refresh", show=True),
        Binding("?", "show_help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    # Reactive state
    theme_name = reactive("dark")
    active_tab = reactive("home")
    is_polling = reactive(False)

    def __init__(self, auto_start_servers: bool = True) -> None:
        super().__init__()
        self.poller = DataPoller()
        self._poll_task: asyncio.Task | None = None
        self._auto_start_servers = auto_start_servers

    def compose(self) -> ComposeResult:
        """Compose the app UI."""
        yield Header()

        with TabbedContent(id="tabs"):
            with TabPane("Home", id="home"):
                yield HomePanel()
            with TabPane("Agents", id="agents"):
                yield AgentPanel()
            with TabPane("Blackboard", id="blackboard"):
                yield BlackboardPanel()
            with TabPane("Settings", id="settings"):
                yield SettingsPanel()

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize on mount.

        Uses Worker pattern instead of set_interval() per review fix.
        """
        # Register all custom themes
        for name, theme_obj in THEMES.items():
            self.register_theme(theme_obj)

        # Apply initial theme
        self.theme = "agent-dark"

        # Connect poller
        await self.poller.connect()

        # Auto-start servers if enabled
        if self._auto_start_servers:
            await self._auto_start_servers_on_launch()

        # Start polling loop using Worker pattern
        # This is the correct async pattern per the review
        self.run_worker(self._polling_loop())

    async def _auto_start_servers_on_launch(self) -> None:
        """Automatically start Claude Proxy and Agentica Server on launch.

        Checks if servers are already running before starting.
        Failures are logged but don't prevent app startup.
        """
        # Check and start Claude Proxy
        proxy_healthy, _ = await self.poller._check_server_health("http://localhost:8080")
        if not proxy_healthy:
            self.notify("Starting Claude Proxy...", timeout=1.5)
            success, error = await self.poller.start_server("claude_proxy")
            if success:
                self.notify("Claude Proxy started", timeout=1.5)
            else:
                self.notify(f"Claude Proxy failed: {error}", severity="warning", timeout=3.0)
        else:
            self.notify("Claude Proxy already running", timeout=1.0)

        # Check and start Agentica Server
        agentica_healthy, _ = await self.poller._check_server_health("http://localhost:2345")
        if not agentica_healthy:
            self.notify("Starting Agentica Server...", timeout=1.5)
            success, error = await self.poller.start_server("agentica_server")
            if success:
                self.notify("Agentica Server started", timeout=1.5)
            else:
                self.notify(f"Agentica Server failed: {error}", severity="warning", timeout=3.0)
        else:
            self.notify("Agentica Server already running", timeout=1.0)

    async def on_unmount(self) -> None:
        """Clean up on unmount."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        await self.poller.disconnect()

    async def _polling_loop(self) -> None:
        """Background polling loop using Worker pattern.

        This replaces set_interval() which doesn't work with async callbacks.
        """
        while True:
            try:
                await self._poll_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log(f"Poll error: {e}")
            await asyncio.sleep(1.0)

    async def _poll_data(self) -> None:
        """Poll data for active tab."""
        self.is_polling = True

        try:
            if self.active_tab == "home":
                data = await self.poller.poll_home()
                try:
                    panel = self.query_one(HomePanel)
                    panel.data = data
                except Exception:
                    pass

            elif self.active_tab == "agents":
                data = await self.poller.poll_agents()
                try:
                    panel = self.query_one(AgentPanel)
                    panel.data = data
                except Exception:
                    pass

            elif self.active_tab == "blackboard":
                data = await self.poller.poll_blackboard()
                try:
                    panel = self.query_one(BlackboardPanel)
                    panel.data = data
                except Exception:
                    pass

            elif self.active_tab == "settings":
                data = await self.poller.poll_settings(self.theme_name)
                try:
                    panel = self.query_one(SettingsPanel)
                    panel.data = data
                except Exception:
                    pass

        finally:
            self.is_polling = False

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab switch.

        Uses run_worker() for async call per review fix.
        Note: event.pane.id gives our TabPane id (e.g., "settings"),
              event.tab.id gives internal id (e.g., "--content-tab-settings")
        """
        self.active_tab = event.pane.id or "home"
        # Trigger immediate refresh on tab switch
        self.run_worker(self._poll_data())

    # ========================================
    # Theme Management
    # ========================================

    def action_toggle_theme(self) -> None:
        """Cycle to next theme."""
        new_theme = next_theme(self.theme_name)
        self.theme_name = new_theme
        self.theme = f"agent-{new_theme}"
        self.notify(f"Theme: {new_theme}", timeout=1.0)

    # ========================================
    # Tab Switching
    # ========================================

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch to specified tab."""
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = tab_id
        except Exception:
            pass

    # ========================================
    # Manual Refresh
    # ========================================

    def action_force_refresh(self) -> None:
        """Force immediate data refresh."""
        self.run_worker(self._poll_data())
        self.notify("Refreshing...", timeout=0.5)

    def action_show_help(self) -> None:
        """Show help information via modal screen.

        Dismisses on any keypress (not just Escape).
        """
        self.push_screen(HelpScreen())

    # ========================================
    # Agent Cleanup Handlers
    # ========================================

    def on_agent_panel_clean_stale_requested(
        self,
        event: AgentPanel.CleanStaleRequested,
    ) -> None:
        """Handle Clean Stale request from AgentPanel."""
        try:
            panel = self.query_one(AgentPanel)
            # Calculate stale count for notification before hiding
            from scripts.agent_monitor_tui.poller import is_stale_agent
            stale_count = sum(1 for a in panel.data.agents if is_stale_agent(a))
            # Use hide_stale_agents() to filter view and trigger refresh
            panel.hide_stale_agents()
            self.notify(f"Hidden {stale_count} stale agents", timeout=2.0)
        except Exception as e:
            self.notify(f"Error cleaning stale agents: {e}", severity="error")

    def on_agent_panel_mark_dead_requested(
        self,
        event: AgentPanel.MarkDeadRequested,
    ) -> None:
        """Handle Mark Dead request from AgentPanel.

        Updates stale 'running' agents to 'completed' in the database.
        """
        self.run_worker(self._mark_dead_agents())

    async def _mark_dead_agents(self) -> None:
        """Mark stale running agents as completed in the database."""
        try:
            count = await self.poller.mark_dead_agents(threshold_hours=24)
            if count > 0:
                self.notify(f"Marked {count} zombie agents as completed", timeout=2.0)
                # Refresh agents view
                await self._poll_data()
            else:
                self.notify("No zombie agents found", timeout=2.0)
        except Exception as e:
            self.notify(f"Error marking dead agents: {e}", severity="error", timeout=3.0)

    def on_agent_panel_kill_agent_requested(
        self,
        event: AgentPanel.KillAgentRequested,
    ) -> None:
        """Handle Kill Agent request from AgentPanel."""
        self.run_worker(self._kill_agent(event.agent_id, event.pid))

    async def _kill_agent(self, agent_id: str, pid: int) -> None:
        """Kill an agent process asynchronously."""
        result = await self.poller.kill_agent_async(pid)
        if result.success:
            self.notify(
                f"Sent SIGTERM to agent {agent_id[:8]} (PID {pid})",
                timeout=2.0,
            )
            # Refresh agents view
            await self._poll_data()
        else:
            self.notify(
                f"Failed to kill agent {agent_id[:8]}: {result.error}",
                severity="error",
                timeout=3.0,
            )

    # ========================================
    # Server Control Handlers
    # ========================================

    def on_server_status_card_server_action(
        self,
        event: ServerStatusCard.ServerAction,
    ) -> None:
        """Handle server control actions (start/stop/restart) with loading state."""
        self.run_worker(self._handle_server_action(event))

    async def _handle_server_action(
        self,
        event: ServerStatusCard.ServerAction,
    ) -> None:
        """Execute server action with loading state management."""
        # Find the card that sent the event
        card_id = "proxy-card" if event.server_name == "claude_proxy" else "agentica-card"
        try:
            card = self.query_one(f"#{card_id}", ServerStatusCard)
        except Exception:
            return

        # Set loading state
        card.loading_action = event.action.title()  # "Start" -> "Starting"
        card.is_loading = True

        try:
            if event.action == "start":
                success, error = await self.poller.start_server(event.server_name)
            elif event.action == "stop":
                success, error = await self.poller.stop_server(event.server_name)
            elif event.action == "restart":
                success, error = await self.poller.restart_server(event.server_name)
            else:
                success, error = False, f"Unknown action: {event.action}"

            if success:
                self.notify(f"{event.action.title()} completed", timeout=1.5)
            else:
                self.notify(f"{event.action.title()} failed: {error}", severity="error", timeout=3.0)
        finally:
            card.is_loading = False
            # Refresh to show new status
            await self._poll_data()


def run_app(auto_start_servers: bool = True) -> None:
    """Run the Agent Monitor TUI.

    Args:
        auto_start_servers: If True, automatically start Claude Proxy and
            Agentica Server on launch. Defaults to True.
    """
    app = AgentMonitorApp(auto_start_servers=auto_start_servers)
    app.run()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agent Monitor TUI")
    parser.add_argument(
        "--no-autostart",
        action="store_true",
        help="Don't auto-start Claude Proxy and Agentica Server",
    )
    args = parser.parse_args()
    run_app(auto_start_servers=not args.no_autostart)
