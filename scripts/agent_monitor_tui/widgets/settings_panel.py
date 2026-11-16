"""Settings Panel - Server controls and configuration.

Shows:
- Claude Proxy health status and controls
- Agentica Server health status and controls
- Current theme display
- Configuration info
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Label, Static

from scripts.agent_monitor_tui.poller import ServerStatus, SettingsData


class ServerStatusCard(Static):
    """Card showing server status with health indicator and control buttons."""

    # Message for server control actions
    class ServerAction(Message):
        """Message sent when a server control button is pressed."""

        def __init__(self, server_name: str, action: str) -> None:
            self.server_name = server_name  # "claude_proxy" or "agentica_server"
            self.action = action  # "start", "stop", or "restart"
            super().__init__()

    # Reactive for loading state
    is_loading = reactive(False)
    loading_action = reactive("")

    DEFAULT_CSS = """
    ServerStatusCard {
        width: 1fr;
        height: auto;
        border: solid $surface;
        padding: 1;
        margin: 0 1 1 0;
        background: $surface;
    }
    ServerStatusCard .server-header {
        text-style: bold;
    }
    ServerStatusCard .server-url {
        color: $text-muted;
    }
    ServerStatusCard .status-row {
        height: auto;
        margin-top: 1;
    }
    ServerStatusCard .health-indicator {
        width: 3;
    }
    ServerStatusCard .health-indicator.healthy {
        color: green;
    }
    ServerStatusCard .health-indicator.unhealthy {
        color: red;
    }
    ServerStatusCard .error-text {
        color: $error;
        text-style: italic;
    }
    ServerStatusCard .button-row {
        height: auto;
        margin-top: 1;
    }
    ServerStatusCard Button {
        min-width: 10;
        margin-right: 1;
    }
    ServerStatusCard .loading-text {
        color: $warning;
        margin-left: 1;
    }
    """

    status = reactive(ServerStatus(name="", url=""), always_update=True)

    def __init__(
        self,
        status: ServerStatus | None = None,
        id: str | None = None,
        server_key: str = "",
    ) -> None:
        super().__init__(id=id)
        self._server_key = server_key  # "claude_proxy" or "agentica_server"
        if status:
            self.status = status

    def compose(self) -> ComposeResult:
        yield Label(self.status.name, classes="server-header", id="name")
        yield Label(self.status.url, classes="server-url", id="url")
        with Horizontal(classes="status-row"):
            # Health indicator (green/red dot)
            indicator_class = "healthy" if self.status.healthy else "unhealthy"
            dot = "[green]O[/]" if self.status.healthy else "[red]O[/]"
            yield Static(dot, classes=f"health-indicator {indicator_class}", id="indicator")
            status_text = "Running" if self.status.healthy else "Stopped"
            yield Label(status_text, id="status-text")
            # Loading indicator (shows "Starting...", "Stopping...", etc.)
            yield Label("", id="loading-text", classes="loading-text")
        # Error message if any
        if self.status.error:
            yield Label(self.status.error, classes="error-text", id="error")
        # Control buttons
        with Horizontal(classes="button-row"):
            yield Button("Start", id="start-btn", variant="success")
            yield Button("Stop", id="stop-btn", variant="error")
            yield Button("Restart", id="restart-btn", variant="warning")

    def watch_status(self, status: ServerStatus) -> None:
        """Update display when status changes."""
        try:
            self.query_one("#name", Label).update(status.name)
            self.query_one("#url", Label).update(status.url)

            # Update indicator
            dot = "[green]O[/]" if status.healthy else "[red]O[/]"
            indicator = self.query_one("#indicator", Static)
            indicator.update(dot)
            indicator.remove_class("healthy", "unhealthy")
            indicator.add_class("healthy" if status.healthy else "unhealthy")

            # Update status text
            status_text = "Running" if status.healthy else "Stopped"
            self.query_one("#status-text", Label).update(status_text)

            # Update error
            try:
                error_label = self.query_one("#error", Label)
                if status.error:
                    error_label.update(status.error)
                    error_label.display = True
                else:
                    error_label.display = False
            except Exception:
                pass  # Error label may not exist yet
        except Exception:
            pass

    def watch_is_loading(self, loading: bool) -> None:
        """Update UI when loading state changes."""
        try:
            loading_label = self.query_one("#loading-text", Label)
            if loading:
                loading_label.update(f"[yellow]{self.loading_action}...[/]")
            else:
                loading_label.update("")
            # Disable/enable buttons during loading
            for btn in self.query("Button"):
                btn.disabled = loading
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses and emit ServerAction message."""
        button_id = event.button.id
        if button_id == "start-btn":
            action = "start"
        elif button_id == "stop-btn":
            action = "stop"
        elif button_id == "restart-btn":
            action = "restart"
        else:
            return

        # Post the message to parent
        self.post_message(self.ServerAction(self._server_key, action))


class SettingsPanel(Static):
    """Settings panel showing server status and configuration."""

    DEFAULT_CSS = """
    SettingsPanel {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    SettingsPanel .section-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        padding: 0 1;
    }
    SettingsPanel .servers-row {
        height: auto;
        margin: 1 0;
    }
    SettingsPanel .config-section {
        margin-top: 2;
        padding: 1;
        border: solid $surface;
    }
    SettingsPanel .config-item {
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    data = reactive(SettingsData, always_update=True)

    def __init__(self) -> None:
        super().__init__()
        self._initialized = False

    def compose(self) -> ComposeResult:
        # Header
        yield Static(
            "[bold green]"
            "+========================================+\n"
            "|          SETTINGS & SERVERS           |\n"
            "+========================================+[/]",
            id="header",
        )

        yield Label("SERVER STATUS", classes="section-title")

        with Horizontal(classes="servers-row"):
            yield ServerStatusCard(id="proxy-card", server_key="claude_proxy")
            yield ServerStatusCard(id="agentica-card", server_key="agentica_server")

        yield Label("CONFIGURATION", classes="section-title")

        with Vertical(classes="config-section"):
            yield Label("Theme: dark", classes="config-item", id="theme-display")
            yield Label("Poll Interval: 1.0s", classes="config-item", id="poll-display")
            yield Label("Database: ", classes="config-item", id="db-display")

    def on_mount(self) -> None:
        """Initialize after mount."""
        self._initialized = True

    def watch_data(self, data: SettingsData) -> None:
        """Update display when data changes."""
        if not self._initialized:
            return

        try:
            # Update server cards
            proxy_card = self.query_one("#proxy-card", ServerStatusCard)
            proxy_card.status = data.claude_proxy

            agentica_card = self.query_one("#agentica-card", ServerStatusCard)
            agentica_card.status = data.agentica_server

            # Update config display
            self.query_one("#theme-display", Label).update(f"Theme: {data.current_theme}")
            self.query_one("#poll-display", Label).update(f"Poll Interval: {data.poll_interval}s")
            self.query_one("#db-display", Label).update(f"Database: {data.db_path or 'N/A'}")
        except Exception:
            pass
