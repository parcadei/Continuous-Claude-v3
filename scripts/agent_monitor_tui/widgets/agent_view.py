"""Agent View - Pattern-specific agent visualizers.

Shows running agents with pattern-aware visualization:
- Swarm: Horizontal nodes with broadcast indicators
- Hierarchical: Tree structure with parent-child relationships
- Pipeline: Sequential flow with stage indicators
- Jury: Voting grid with consensus status
- Generic: Simple table for unknown patterns

Cleanup functionality:
- Clean Stale: Remove agents older than 24 hours from display
- Kill: Send SIGTERM to running agent process
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Callable

from rich.table import Table
from rich.text import Text

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Label, Static

from scripts.agentica_patterns.coordination import AgentRecord, OrphanCandidate
from scripts.agent_monitor_tui.poller import AgentsData, is_stale_agent


# Box-drawing characters for industrial aesthetic
BOX = {
    "h": "-",     # horizontal
    "v": "|",     # vertical
    "tl": "+",    # top-left
    "tr": "+",    # top-right
    "bl": "+",    # bottom-left
    "br": "+",    # bottom-right
    "t": "+",     # tee down
    "b": "+",     # tee up
    "l": "+",     # tee right
    "r": "+",     # tee left
    "x": "+",     # cross
}


def format_duration(spawned_at: datetime) -> str:
    """Format duration since spawn time."""
    now = datetime.now(UTC).replace(tzinfo=None)
    delta = now - spawned_at.replace(tzinfo=None)

    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def get_status_indicator(status: str) -> str:
    """Get status indicator character."""
    indicators = {
        "running": "[green]*[/]",   # Pulsing asterisk
        "completed": "[dim]+[/]",   # Plus sign
        "failed": "[red]X[/]",      # Red X
    }
    return indicators.get(status, "[dim]?[/]")


def get_pattern_icon(pattern: str | None) -> str:
    """Get pattern icon for visual identification."""
    icons = {
        "main": "[bold white]●[/]",       # Main session
        "task": "[white]○[/]",            # Simple task spawn
        "swarm": "[cyan]@[/]",
        "hierarchical": "[yellow]^[/]",
        "pipeline": "[blue]>[/]",
        "jury": "[magenta]#[/]",
        "generator_critic": "[green]~[/]",
        "map_reduce": "[red]%[/]",
        "blackboard": "[yellow]□[/]",
        "circuit_breaker": "[red]![/]",
        "chain_of_responsibility": "[blue]→[/]",
        "adversarial": "[red]⚔[/]",
        "event_driven": "[cyan]⚡[/]",
    }
    return icons.get(pattern or "", "[dim]?[/]")


def get_source_badge(source: str | None) -> str:
    """Get source badge for agent origin identification.

    Returns a colored badge indicating where the agent was spawned from:
    - cli: Claude Code CLI (Task tool) - shown in blue
    - agentica: Agentica server - shown in magenta
    - None/unknown: No badge shown
    """
    if source == "cli":
        return "[blue][CLI][/]"
    elif source == "agentica":
        return "[magenta][AGT][/]"
    else:
        return ""


class AgentCard(Static):
    """A compact card for a single agent.

    Includes a Kill button for running agents with a valid PID.
    """

    class KillRequested(Message):
        """Message emitted when Kill button is pressed."""

        def __init__(self, agent_id: str, pid: int) -> None:
            self.agent_id = agent_id
            self.pid = pid
            super().__init__()

    DEFAULT_CSS = """
    AgentCard {
        width: 1fr;
        height: auto;
        border: solid $surface;
        padding: 0 1;
        margin: 0 1 1 0;
    }
    AgentCard.running {
        border: solid $primary;
    }
    AgentCard.orphan {
        border: solid $error;
    }
    AgentCard .agent-header {
        text-style: bold;
    }
    AgentCard .agent-detail {
        color: $text-muted;
    }
    AgentCard .agent-actions {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    AgentCard .kill-btn {
        min-width: 8;
        height: 3;
        text-align: center;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        agent: AgentRecord,
        is_orphan: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.agent = agent
        self.is_orphan = is_orphan

        # Add CSS class based on status
        if is_orphan:
            self.add_class("orphan")
        elif agent.status == "running":
            self.add_class("running")

    def compose(self) -> ComposeResult:
        # Header: icon + id + status + source badge
        icon = get_pattern_icon(self.agent.pattern)
        status = get_status_indicator(self.agent.status)
        source_badge = get_source_badge(self.agent.source)
        header = f"{icon} {self.agent.id[:8]} {status}"
        if source_badge:
            header += f" {source_badge}"
        if self.is_orphan:
            header += " [red][ORPHAN][/]"

        yield Label(header, classes="agent-header")

        # Details
        duration = format_duration(self.agent.spawned_at)
        pattern = self.agent.pattern or "unknown"
        detail = f"  {pattern} | {duration}"
        yield Label(detail, classes="agent-detail")

        # Kill button for running agents with valid PID
        if self.agent.status == "running" and self.agent.pid:
            with Horizontal(classes="agent-actions"):
                yield Button(
                    "Kill",
                    id=f"kill-{self.agent.id}",
                    variant="error",
                    classes="kill-btn",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Kill button press."""
        if event.button.id and event.button.id.startswith("kill-"):
            if self.agent.pid:
                self.post_message(
                    AgentCard.KillRequested(self.agent.id, self.agent.pid)
                )


class SwarmVisualizer(Static):
    """Visualize swarm pattern as horizontal nodes with responsive grid."""

    DEFAULT_CSS = """
    SwarmVisualizer {
        width: 100%;
        height: auto;
        padding: 1;
        align: center middle;
    }
    SwarmVisualizer .swarm-grid {
        grid-size: 5;
        grid-gutter: 1;
        width: 100%;
        height: auto;
        align: center middle;
    }
    """

    def __init__(self, agents: list[AgentRecord]) -> None:
        super().__init__()
        self.agents = agents

    def compose(self) -> ComposeResult:
        # Group by session
        by_session: dict[str, list[AgentRecord]] = {}
        for agent in self.agents:
            by_session.setdefault(agent.session_id, []).append(agent)

        for session_id, session_agents in by_session.items():
            yield Label(f"[bold]Swarm {session_id[:8]}[/]")

            # Use Grid for responsive wrapping - no artificial limit
            with Grid(classes="swarm-grid"):
                for agent in session_agents:
                    yield AgentCard(agent)


class HierarchicalVisualizer(Static):
    """Visualize hierarchical pattern as tree."""

    DEFAULT_CSS = """
    HierarchicalVisualizer {
        width: 100%;
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, agents: list[AgentRecord]) -> None:
        super().__init__()
        self.agents = agents

    def compose(self) -> ComposeResult:
        # Build tree structure
        roots: list[AgentRecord] = []
        children: dict[str, list[AgentRecord]] = {}

        for agent in self.agents:
            if agent.parent_agent_id:
                children.setdefault(agent.parent_agent_id, []).append(agent)
            else:
                roots.append(agent)

        def render_tree(agent: AgentRecord, prefix: str = "") -> ComposeResult:
            """Recursively render tree nodes."""
            icon = get_pattern_icon(agent.pattern)
            status = get_status_indicator(agent.status)
            source_badge = get_source_badge(agent.source)
            duration = format_duration(agent.spawned_at)
            line = f"{prefix}{icon} {agent.id[:8]} {status}"
            if source_badge:
                line += f" {source_badge}"
            line += f" ({duration})"
            yield Label(line)

            agent_children = children.get(agent.id, [])
            for i, child in enumerate(agent_children):
                is_last = i == len(agent_children) - 1
                child_prefix = prefix + ("    " if is_last else "|   ")
                branch = "+" if is_last else "+"
                yield Label(f"{prefix}{branch}---")
                yield from render_tree(child, child_prefix)

        for root in roots:
            yield from render_tree(root)


class PipelineVisualizer(Static):
    """Visualize pipeline pattern as sequential stages."""

    DEFAULT_CSS = """
    PipelineVisualizer {
        width: 100%;
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, agents: list[AgentRecord]) -> None:
        super().__init__()
        self.agents = sorted(agents, key=lambda a: a.spawned_at)

    def compose(self) -> ComposeResult:
        yield Label("[bold]Pipeline Flow[/]")

        # Show agents as pipeline stages
        lines = []
        for i, agent in enumerate(self.agents):
            icon = get_pattern_icon(agent.pattern)
            status = get_status_indicator(agent.status)
            source_badge = get_source_badge(agent.source)
            duration = format_duration(agent.spawned_at)

            badge_str = f" {source_badge}" if source_badge else ""
            if i == 0:
                lines.append(f"  {icon} [{agent.id[:8]}] {status}{badge_str}")
            else:
                lines.append(f"  |")
                lines.append(f"  v")
                lines.append(f"  {icon} [{agent.id[:8]}] {status}{badge_str}")

        for line in lines:
            yield Label(line)


class JuryVisualizer(Static):
    """Visualize jury pattern as voting grid."""

    DEFAULT_CSS = """
    JuryVisualizer {
        width: 100%;
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, agents: list[AgentRecord]) -> None:
        super().__init__()
        self.agents = agents

    def compose(self) -> ComposeResult:
        yield Label("[bold]Jury Panel[/]")

        # Create voting grid
        lines = ["+-------" * len(self.agents) + "+"]

        # Agent IDs
        id_line = "|"
        for agent in self.agents:
            id_line += f" {agent.id[:6]} |"
        lines.append(id_line)

        # Status row
        status_line = "|"
        for agent in self.agents:
            status = get_status_indicator(agent.status)
            status_line += f"  {status}   |"
        lines.append(status_line)

        lines.append("+-------" * len(self.agents) + "+")

        for line in lines:
            yield Label(line)


class GenericVisualizer(Static):
    """Generic visualizer with responsive grid for unknown patterns."""

    DEFAULT_CSS = """
    GenericVisualizer {
        width: 100%;
        height: auto;
        padding: 1;
        align: center middle;
    }
    GenericVisualizer #agent-grid {
        grid-size: 5;
        grid-gutter: 1;
        width: 100%;
        height: auto;
        align: center middle;
    }
    """

    def __init__(
        self,
        agents: list[AgentRecord],
        orphans: list[OrphanCandidate],
    ) -> None:
        super().__init__()
        self.agents = agents
        self.orphan_ids = {o.agent_id for o in orphans}

    def compose(self) -> ComposeResult:
        # Use Grid for responsive wrapping - no artificial limit
        with Grid(id="agent-grid"):
            for agent in self.agents:
                is_orphan = agent.id in self.orphan_ids
                yield AgentCard(agent, is_orphan=is_orphan)


class AgentPanel(Static):
    """Agent panel with pattern-aware visualization.

    Features:
    - Pattern-specific visualizers (swarm, hierarchical, pipeline, jury)
    - Clean Stale button to remove old agents from display
    - Mark Dead button to update stale running agents to completed in DB
    - Kill button on each running agent to send SIGTERM
    """

    class CleanStaleRequested(Message):
        """Message emitted when Clean Stale button is pressed."""
        pass

    class MarkDeadRequested(Message):
        """Message emitted when Mark Dead button is pressed."""
        pass

    class KillAgentRequested(Message):
        """Message emitted when Kill button is pressed on an agent."""

        def __init__(self, agent_id: str, pid: int) -> None:
            self.agent_id = agent_id
            self.pid = pid
            super().__init__()

    DEFAULT_CSS = """
    AgentPanel {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    AgentPanel .header-row {
        height: auto;
        margin-bottom: 1;
    }
    AgentPanel .section-title {
        text-style: bold;
        color: $primary;
        padding: 0 1;
    }
    AgentPanel .clean-stale-btn {
        min-width: 14;
        height: 3;
        margin-left: 2;
    }
    AgentPanel .mark-dead-btn {
        min-width: 12;
        height: 3;
        margin-left: 1;
    }
    AgentPanel .summary-row {
        height: auto;
        margin: 1 0;
    }
    AgentPanel .visualizer-container {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    AgentPanel .empty-state {
        color: $text-muted;
        text-align: center;
        padding: 2;
    }
    """

    data: AgentsData = reactive(AgentsData)  # No always_update - use fingerprint
    _show_stale: bool = True  # Whether to show stale agents (>24 hours old)
    _last_fingerprint: str = ""  # Track last rendered data to prevent flicker

    def __init__(self) -> None:
        super().__init__()
        self._initialized = False

    def hide_stale_agents(self) -> None:
        """Hide stale agents from the view and trigger refresh."""
        self._show_stale = False
        # Reset fingerprint to force re-render, then trigger watch_data
        self._last_fingerprint = ""
        self.watch_data(self.data)

    def compose(self) -> ComposeResult:
        # Header row with title and cleanup buttons
        with Horizontal(classes="header-row"):
            yield Label("AGENTS", classes="section-title")
            yield Button(
                "Clean Stale",
                id="clean-stale",
                variant="warning",
                classes="clean-stale-btn",
            )
            yield Button(
                "Mark Dead",
                id="mark-dead",
                variant="error",
                classes="mark-dead-btn",
            )

        # Summary row
        with Horizontal(classes="summary-row"):
            yield Label("Patterns: --", id="patterns-summary")
            yield Label("  |  ", id="sep1")
            yield Label("Status: --", id="status-summary")

        # Visualizer container
        yield Vertical(id="visualizer-container", classes="visualizer-container")

    def on_mount(self) -> None:
        """Initialize after mount."""
        self._initialized = True

    def watch_data(self, data: AgentsData) -> None:
        """Update display when data changes."""
        if not self._initialized:
            return

        try:
            # Filter agents based on _show_stale flag
            if self._show_stale:
                visible_agents = data.agents
            else:
                visible_agents = [a for a in data.agents if not is_stale_agent(a)]

            # Create filtered data for fingerprinting
            display_data = AgentsData(
                agents=visible_agents,
                orphans=data.orphans,
                by_pattern=data.by_pattern,
                by_status=data.by_status,
            )

            # Use stable fingerprint method for change detection
            fingerprint = f"{display_data.fingerprint()}:{self._show_stale}"

            if fingerprint == self._last_fingerprint:
                return  # No changes, skip re-render to prevent flicker

            self._last_fingerprint = fingerprint

            # Update summary
            patterns = ", ".join(
                f"{k}:{v}" for k, v in display_data.by_pattern.items()
            ) or "none"
            self.query_one("#patterns-summary", Label).update(f"Patterns: {patterns}")

            status = ", ".join(
                f"{k}:{v}" for k, v in display_data.by_status.items()
            ) or "none"
            self.query_one("#status-summary", Label).update(f"Status: {status}")

            # Update visualizer
            container = self.query_one("#visualizer-container", Vertical)
            container.remove_children()

            if not display_data.agents:
                container.mount(
                    Label("No active agents", classes="empty-state")
                )
                return

            # Determine dominant pattern for visualization
            if display_data.by_pattern:
                dominant = max(display_data.by_pattern.items(), key=lambda x: x[1])[0]
            else:
                dominant = "generic"

            # Create appropriate visualizer
            visualizer = self._get_visualizer(dominant, display_data)
            container.mount(visualizer)

        except Exception:
            pass

    def _get_visualizer(
        self,
        pattern: str,
        data: AgentsData,
    ) -> Static:
        """Get appropriate visualizer for pattern."""
        pattern_agents = [
            a for a in data.agents
            if a.pattern == pattern or pattern == "generic"
        ]

        if pattern == "swarm":
            return SwarmVisualizer(pattern_agents)
        elif pattern == "hierarchical":
            return HierarchicalVisualizer(pattern_agents)
        elif pattern == "pipeline":
            return PipelineVisualizer(pattern_agents)
        elif pattern == "jury":
            return JuryVisualizer(pattern_agents)
        else:
            return GenericVisualizer(data.agents, data.orphans)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "clean-stale":
            self.post_message(AgentPanel.CleanStaleRequested())
        elif event.button.id == "mark-dead":
            self.post_message(AgentPanel.MarkDeadRequested())

    def on_agent_card_kill_requested(self, event: AgentCard.KillRequested) -> None:
        """Handle Kill request from AgentCard."""
        self.post_message(
            AgentPanel.KillAgentRequested(event.agent_id, event.pid)
        )
