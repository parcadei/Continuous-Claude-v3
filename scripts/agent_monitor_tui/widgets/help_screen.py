"""Help Screen Modal for Agent Monitor TUI.

A modal screen that displays help content and dismisses on any keypress.
"""

from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Static


HELP_TEXT = """[bold cyan]Agent Monitor TUI Help[/]

[bold]Navigation:[/]
  1-4    Switch tabs (Home/Agents/Blackboard/Settings)
  t      Cycle themes (dark/light/catppuccin/nord)
  r      Force refresh data
  q      Quit

[bold]Tabs:[/]
  [cyan]Home[/]       System resources + agent count
  [cyan]Agents[/]     Running agents with pattern info
  [cyan]Blackboard[/] Shared agent context entries
  [cyan]Settings[/]   Server health status

[bold]Agent Status Icons:[/]
  [green]o[/] Running    [red]o[/] Stopped    [yellow]?[/] Unknown

Press any key to close."""


class HelpScreen(ModalScreen):
    """Modal screen that shows help and dismisses on any keypress."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Center {
        width: 100%;
        height: 100%;
    }

    HelpScreen #help-content {
        width: auto;
        height: auto;
        padding: 2 4;
        border: thick $primary;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the help screen UI."""
        with Center():
            with Middle():
                yield Static(HELP_TEXT, id="help-content")

    def on_key(self, event: Key) -> None:
        """Dismiss on any keypress."""
        self.app.pop_screen()
