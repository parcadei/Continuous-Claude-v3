"""Home Panel - System overview dashboard.

Shows:
- CPU usage gauge
- Memory usage gauge
- Agent count and status
- Session information
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Label, ProgressBar, Static

from scripts.agent_monitor_tui.poller import HomeData


class MetricCard(Static):
    """A card displaying a single metric with label and value."""

    DEFAULT_CSS = """
    MetricCard {
        width: 1fr;
        height: auto;
        border: solid $primary;
        padding: 1;
        margin: 0 1;
    }
    MetricCard .metric-label {
        text-style: bold;
        color: $text-muted;
    }
    MetricCard .metric-value {
        text-style: bold;
        color: $primary;
    }
    """

    def __init__(
        self,
        label: str,
        value: str = "0",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._label = label
        self._value = value

    def compose(self) -> ComposeResult:
        yield Label(self._label, classes="metric-label")
        yield Label(self._value, classes="metric-value", id="value")

    def update_value(self, value: str) -> None:
        """Update the displayed value."""
        self._value = value
        try:
            self.query_one("#value", Label).update(value)
        except Exception:
            pass


class ResourceGauge(Static):
    """A gauge showing resource usage with label and progress bar."""

    DEFAULT_CSS = """
    ResourceGauge {
        width: 1fr;
        height: auto;
        padding: 1;
    }
    ResourceGauge .gauge-label {
        margin-bottom: 1;
    }
    ResourceGauge ProgressBar {
        width: 100%;
    }
    """

    percent = reactive(0.0)

    def __init__(
        self,
        label: str,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._label = label

    def compose(self) -> ComposeResult:
        yield Label(f"{self._label}: 0%", classes="gauge-label", id="label")
        yield ProgressBar(total=100, show_eta=False, show_percentage=False)

    def watch_percent(self, value: float) -> None:
        """Update gauge when percent changes."""
        try:
            label = self.query_one("#label", Label)
            label.update(f"{self._label}: {value:.1f}%")
            bar = self.query_one(ProgressBar)
            bar.update(progress=value)
        except Exception:
            pass


class HomePanel(Static):
    """Home panel showing system overview."""

    DEFAULT_CSS = """
    HomePanel {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    HomePanel .section-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        padding: 0 1;
    }
    HomePanel .metrics-row {
        height: auto;
        margin: 1 0;
    }
    HomePanel .gauges-row {
        height: auto;
        margin: 1 0;
    }
    """

    data: HomeData = reactive(HomeData)  # No always_update - use fingerprint
    _last_fingerprint: str = ""  # Track last rendered data to prevent flicker

    def __init__(self) -> None:
        super().__init__()
        self._initialized = False

    def compose(self) -> ComposeResult:
        # ASCII art header - industrial aesthetic
        yield Static(
            "[bold green]"
            "+========================================+\n"
            "|     AGENT MONITOR - CONTROL CENTER    |\n"
            "+========================================+[/]",
            id="header",
        )

        yield Label("SYSTEM RESOURCES", classes="section-title")

        with Horizontal(classes="gauges-row"):
            yield ResourceGauge("CPU", id="cpu-gauge")
            yield ResourceGauge("RAM", id="ram-gauge")

        yield Label("AGENT STATUS", classes="section-title")

        with Horizontal(classes="metrics-row"):
            yield MetricCard("Total Agents", "0", id="total-agents")
            yield MetricCard("Running", "0", id="running-agents")
            yield MetricCard("Sessions", "0", id="sessions")

    def on_mount(self) -> None:
        """Initialize after mount."""
        self._initialized = True

    def watch_data(self, data: HomeData) -> None:
        """Update display when data changes."""
        if not self._initialized:
            return

        try:
            # Use stable fingerprint for change detection
            fingerprint = data.fingerprint()
            if fingerprint == self._last_fingerprint:
                return  # No changes, skip re-render to prevent flicker
            self._last_fingerprint = fingerprint

            # Update gauges
            cpu = self.query_one("#cpu-gauge", ResourceGauge)
            cpu.percent = data.metrics.cpu_percent

            ram = self.query_one("#ram-gauge", ResourceGauge)
            if data.metrics.memory_total_mb > 0:
                ram.percent = (
                    data.metrics.memory_used_mb / data.metrics.memory_total_mb * 100
                )

            # Update metrics
            self.query_one("#total-agents", MetricCard).update_value(
                str(data.agent_count)
            )
            self.query_one("#running-agents", MetricCard).update_value(
                str(data.running_agents)
            )
            self.query_one("#sessions", MetricCard).update_value(
                str(data.session_count)
            )
        except Exception:
            pass
