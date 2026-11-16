"""Blackboard View - Read-only blackboard entries.

Shows recent blackboard entries with filtering by:
- Message type (finding, question, blocker, etc.)
- Scope level (agent, shared, temporal)
- Priority (critical, high, normal, low)
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Label, Static

from scripts.agentica_patterns.blackboard import (
    SharedContextEntry,
    MessageType,
    ScopeLevel,
    EntryPriority,
)
from scripts.agent_monitor_tui.poller import BlackboardData


def get_type_icon(msg_type: MessageType) -> str:
    """Get icon for message type."""
    icons = {
        MessageType.FINDING: "[green]F[/]",
        MessageType.QUESTION: "[yellow]?[/]",
        MessageType.BLOCKER: "[red]![/]",
        MessageType.CONTEXT: "[blue]C[/]",
        MessageType.DECISION: "[magenta]D[/]",
        MessageType.ARTIFACT: "[cyan]A[/]",
        MessageType.DONE: "[dim]+[/]",
    }
    return icons.get(msg_type, "[dim]-[/]")


def get_priority_indicator(priority: EntryPriority) -> str:
    """Get priority indicator."""
    indicators = {
        EntryPriority.CRITICAL: "[red bold]***[/]",
        EntryPriority.HIGH: "[yellow]** [/]",
        EntryPriority.NORMAL: "[dim]*  [/]",
        EntryPriority.LOW: "[dim]   [/]",
    }
    return indicators.get(priority, "[dim]   [/]")


def get_scope_badge(scope: ScopeLevel) -> str:
    """Get scope badge."""
    badges = {
        ScopeLevel.AGENT: "[cyan]@agent[/]",
        ScopeLevel.SHARED: "[green]@shared[/]",
        ScopeLevel.TEMPORAL: "[yellow]@temp[/]",
    }
    return badges.get(scope, "[dim]@?[/]")


class BlackboardEntry(Static):
    """A single blackboard entry card."""

    DEFAULT_CSS = """
    BlackboardEntry {
        width: 100%;
        height: auto;
        border: solid $surface;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    BlackboardEntry.critical {
        border: solid $error;
    }
    BlackboardEntry.high {
        border: solid $warning;
    }
    BlackboardEntry .entry-header {
        text-style: bold;
    }
    BlackboardEntry .entry-content {
        color: $text;
        padding-left: 2;
    }
    BlackboardEntry .entry-meta {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self, entry: SharedContextEntry, id: str | None = None) -> None:
        super().__init__(id=id)
        self.entry = entry

        # Add CSS class based on priority
        if entry.priority == EntryPriority.CRITICAL:
            self.add_class("critical")
        elif entry.priority == EntryPriority.HIGH:
            self.add_class("high")

    def compose(self) -> ComposeResult:
        entry = self.entry

        # Header: priority + type icon + from_agent
        priority = get_priority_indicator(entry.priority)
        type_icon = get_type_icon(entry.type)
        scope = get_scope_badge(entry.scope)

        header = f"{priority} {type_icon} [{entry.from_agent[:8]}] {scope}"
        yield Label(header, classes="entry-header")

        # Content (truncated)
        content = entry.content[:100]
        if len(entry.content) > 100:
            content += "..."
        yield Label(f"  {content}", classes="entry-content")

        # Metadata
        timestamp = entry.timestamp[:19]  # Trim microseconds
        meta_parts = [timestamp]
        if entry.to_agent:
            meta_parts.append(f"-> {entry.to_agent[:8]}")
        if entry.pattern_id:
            meta_parts.append(f"pattern:{entry.pattern_id[:8]}")

        yield Label("  " + " | ".join(meta_parts), classes="entry-meta")


class BlackboardPanel(Static):
    """Blackboard panel showing recent entries."""

    DEFAULT_CSS = """
    BlackboardPanel {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    BlackboardPanel .section-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        padding: 0 1;
    }
    BlackboardPanel .summary-text {
        color: $text-muted;
        margin: 1 0;
        padding: 0 1;
    }
    BlackboardPanel .entries-container {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    BlackboardPanel .empty-state {
        color: $text-muted;
        text-align: center;
        padding: 2;
    }
    BlackboardPanel .legend {
        color: $text-muted;
        padding: 0 1;
        margin-top: 1;
    }
    """

    data: BlackboardData = reactive(BlackboardData)  # No always_update - use fingerprint
    _last_fingerprint: str = ""  # Track last rendered data to prevent flicker
    _mounted_entry_ids: set[str] = set()  # Track mounted entries for diff updates

    def __init__(self) -> None:
        super().__init__()
        self._initialized = False
        self._mounted_entry_ids = set()

    def compose(self) -> ComposeResult:
        yield Label("BLACKBOARD", classes="section-title")

        # Legend
        yield Label(
            "Types: [green]F[/]=Finding [yellow]?[/]=Question [red]![/]=Blocker "
            "[blue]C[/]=Context [magenta]D[/]=Decision [cyan]A[/]=Artifact",
            classes="legend",
        )

        # Summary
        yield Label("Entries: 0", classes="summary-text", id="summary")

        # Entries container
        yield ScrollableContainer(id="entries-container", classes="entries-container")

    def on_mount(self) -> None:
        """Initialize after mount."""
        self._initialized = True

    def watch_data(self, data: BlackboardData) -> None:
        """Update display when data changes."""
        if not self._initialized:
            return

        try:
            # Use stable fingerprint for change detection
            fingerprint = data.fingerprint()
            if fingerprint == self._last_fingerprint:
                return  # No changes, skip re-render to prevent flicker
            self._last_fingerprint = fingerprint

            # Update summary
            count = len(data.entries)
            summary = self.query_one("#summary", Label)
            summary.update(f"Entries: {count}")

            # Update entries container
            container = self.query_one("#entries-container", ScrollableContainer)

            # Sort by priority then timestamp (most recent first)
            sorted_entries = sorted(
                data.entries,
                key=lambda e: (
                    0 if e.priority == EntryPriority.CRITICAL else
                    1 if e.priority == EntryPriority.HIGH else
                    2 if e.priority == EntryPriority.NORMAL else 3,
                    e.timestamp,
                ),
                reverse=True,
            )[:20]  # Limit to 20 for performance

            # Compute which entries to add/remove (diff update)
            new_entry_ids = {e.id for e in sorted_entries}

            # Only do full remount if entries changed
            if new_entry_ids != self._mounted_entry_ids:
                container.remove_children()

                if not sorted_entries:
                    container.mount(
                        Label("No blackboard entries", classes="empty-state")
                    )
                else:
                    for i, entry in enumerate(sorted_entries):
                        container.mount(BlackboardEntry(entry, id=f"entry-{i}"))

                self._mounted_entry_ids = new_entry_ids

        except Exception:
            pass
