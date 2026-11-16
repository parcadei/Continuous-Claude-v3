# Rigg TUI Design Specification

**Version:** 1.0
**Date:** 2026-01-01
**Status:** Draft

---

## Overview

Rigg uses a custom ANSI direct rendering engine inspired by pi-tui. This approach provides full control over terminal output, eliminates framework overhead, and enables differential updates for flicker-free rendering.

---

## Rendering Engine

### Custom ANSI Direct Rendering

Unlike framework-based TUIs (Textual, Rich), rigg writes ANSI escape codes directly to stdout. This enables:

- **Minimal dependencies** - No external TUI framework required
- **Full control** - Precise positioning and styling
- **Differential updates** - Only changed lines are redrawn
- **Low latency** - No abstraction layer overhead

```python
# core/render.py
import sys
from dataclasses import dataclass

@dataclass
class Cell:
    char: str
    fg: str | None = None
    bg: str | None = None
    bold: bool = False

class Screen:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.buffer: list[list[Cell]] = []
        self.prev_buffer: list[list[Cell]] = []
        self._init_buffers()

    def _init_buffers(self):
        """Initialize double buffer for differential updates."""
        empty_row = lambda: [Cell(' ') for _ in range(self.width)]
        self.buffer = [empty_row() for _ in range(self.height)]
        self.prev_buffer = [empty_row() for _ in range(self.height)]

    def render(self):
        """Render only changed lines (differential update)."""
        output = []
        for y in range(self.height):
            if self.buffer[y] != self.prev_buffer[y]:
                output.append(f"\033[{y+1};1H")  # Move cursor
                output.append(self._render_row(y))

        if output:
            sys.stdout.write(''.join(output))
            sys.stdout.flush()

        # Swap buffers
        self.prev_buffer = [row[:] for row in self.buffer]

    def _render_row(self, y: int) -> str:
        """Render a single row with ANSI styling."""
        parts = []
        for cell in self.buffer[y]:
            style = self._cell_style(cell)
            parts.append(f"{style}{cell.char}\033[0m")
        return ''.join(parts)

    def _cell_style(self, cell: Cell) -> str:
        codes = []
        if cell.bold:
            codes.append('1')
        if cell.fg:
            codes.append(cell.fg)
        if cell.bg:
            codes.append(cell.bg)
        return f"\033[{';'.join(codes)}m" if codes else ''
```

### Terminal Capability Detection

Auto-detect terminal capabilities with environment variable override:

```python
# core/terminal.py
import os
import sys

class Terminal:
    def __init__(self):
        self.width, self.height = self._get_size()
        self.capabilities = self._detect_capabilities()

    def _detect_capabilities(self) -> dict:
        """Detect terminal capabilities, with RIGG_TERMINAL override."""
        override = os.environ.get('RIGG_TERMINAL')

        if override:
            return self._parse_override(override)

        term = os.environ.get('TERM', '')
        colorterm = os.environ.get('COLORTERM', '')

        return {
            'truecolor': colorterm in ('truecolor', '24bit') or 'truecolor' in term,
            '256color': '256color' in term or self._check_256(),
            'unicode': self._check_unicode(),
            'mouse': self._check_mouse_support(),
        }

    def _parse_override(self, spec: str) -> dict:
        """Parse RIGG_TERMINAL env var.

        Examples:
            RIGG_TERMINAL=truecolor,mouse
            RIGG_TERMINAL=256color
            RIGG_TERMINAL=basic
        """
        features = spec.lower().split(',')
        return {
            'truecolor': 'truecolor' in features,
            '256color': '256color' in features or 'truecolor' in features,
            'unicode': 'unicode' in features or 'basic' not in features,
            'mouse': 'mouse' in features,
        }

    def _check_unicode(self) -> bool:
        """Check if terminal supports unicode."""
        try:
            sys.stdout.write('\u2502')  # Box drawing
            return True
        except UnicodeEncodeError:
            return False

    def _check_mouse_support(self) -> bool:
        """Check for mouse support (DECSET 1000)."""
        term = os.environ.get('TERM', '')
        return 'xterm' in term or 'screen' in term or 'tmux' in term
```

---

## Adaptive Layouts / Modes

Rigg automatically detects the appropriate mode based on activity patterns, with manual override available.

### Mode Definitions

| Mode | Trigger | Layout | Description |
|------|---------|--------|-------------|
| **Research** | Explore/chat | Full chat, minimal chrome | Maximum space for conversation |
| **Work/Build** | Tool patterns | Stats panel + Chat | Token/context stats visible |
| **Session Tree** | Explicit | Geometric visualization | Session history with zoom/pan |
| **Editor** | Explicit | Built-in editor | Vim/emacs/nano configurable |

### Mode Detection

```python
# modes/detector.py
from enum import Enum, auto
from dataclasses import dataclass
from collections import deque

class Mode(Enum):
    RESEARCH = auto()
    WORK = auto()
    SESSION_TREE = auto()
    EDITOR = auto()

@dataclass
class ActivityWindow:
    tools_used: int = 0
    files_written: int = 0
    code_blocks: int = 0
    questions_asked: int = 0

class ModeDetector:
    def __init__(self, window_size: int = 10):
        self.history = deque(maxlen=window_size)
        self.current_mode = Mode.RESEARCH
        self.manual_override: Mode | None = None

    def record_activity(self, activity: ActivityWindow):
        """Record activity and potentially switch modes."""
        self.history.append(activity)

        if self.manual_override:
            return self.manual_override

        return self._detect_mode()

    def _detect_mode(self) -> Mode:
        """Detect mode based on recent activity."""
        if not self.history:
            return Mode.RESEARCH

        # Aggregate recent activity
        total_tools = sum(a.tools_used for a in self.history)
        total_writes = sum(a.files_written for a in self.history)
        total_questions = sum(a.questions_asked for a in self.history)

        # Work mode: heavy tool usage
        if total_tools > 5 or total_writes > 2:
            return Mode.WORK

        # Research mode: mostly conversation
        if total_questions > total_tools:
            return Mode.RESEARCH

        return self.current_mode

    def set_manual_mode(self, mode: Mode | None):
        """Set or clear manual mode override."""
        self.manual_override = mode
```

### Layout Definitions

```
# RESEARCH MODE - Full Chat
┌────────────────────────────────────────────────────────────────┐
│  rigg v1.0                                        Ctrl+? Help  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  User: How does the authentication flow work?                  │
│                                                                │
│  Claude: The authentication flow uses OAuth 2.0 with...        │
│  [truncated for display]                                       │
│                                                                │
│                                                                │
│                                                                │
│                                                                │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ > _                                                            │
└────────────────────────────────────────────────────────────────┘

# WORK MODE - Stats Panel + Chat
┌──────────────────┬─────────────────────────────────────────────┐
│  STATS           │  rigg v1.0                      Ctrl+? Help │
├──────────────────┼─────────────────────────────────────────────┤
│                  │                                             │
│  Tokens          │  User: Implement the login feature          │
│  ████████░░ 78%  │                                             │
│  156k / 200k     │  Claude: I'll create the login component... │
│                  │                                             │
│  Context         │  [Read src/auth.py] ✓                       │
│  ██████░░░░ 62%  │  [Write src/login.tsx] ✓                    │
│  124k / 200k     │  [Bash npm test] ✓                          │
│                  │                                             │
│  Session         │                                             │
│  03:24:15        │                                             │
│                  │                                             │
│  Tools: 12       │                                             │
│  Files: 4        │                                             │
│                  ├─────────────────────────────────────────────┤
│                  │ > _                                         │
└──────────────────┴─────────────────────────────────────────────┘

# SESSION TREE MODE - Geometric Visualization
┌────────────────────────────────────────────────────────────────┐
│  SESSION TREE                          [Z]oom [P]an [Enter] Go │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│         ●─────────●─────────●                                  │
│         │         │         │                                  │
│         │         │         └─────●                            │
│         │         │               │                            │
│         │         └─────●─────────●───────●                    │
│         │               │                 │                    │
│         └─────●         └─────●           └───●                │
│               │               │               │                │
│               ●               ●               ●                │
│                                                                │
│  Selected: 2026-01-01 14:32 "Implement auth flow"              │
│  Tokens: 45.2k | Duration: 12m | [F]ork [D]elete [R]ename     │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ > Search sessions: _                                           │
└────────────────────────────────────────────────────────────────┘
```

### Mode Switching

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` | Research mode |
| `Ctrl+2` | Work mode |
| `Ctrl+3` | Session tree |
| `Ctrl+4` | Editor mode |
| `Ctrl+0` | Auto-detect (clear override) |
| `Ctrl+Shift+P` | Command palette |

---

## Built-in Panes

Rigg supports multiple panes without requiring tmux, with dynamic resource management.

### Pane Architecture

```python
# panes/manager.py
from dataclasses import dataclass
from typing import Callable

@dataclass
class PaneBudget:
    max_memory_mb: int = 512
    max_tokens: int = 50000
    warn_threshold: float = 0.8  # Warn at 80%

@dataclass
class Pane:
    id: str
    name: str
    repo_path: str
    budget: PaneBudget
    current_memory_mb: int = 0
    current_tokens: int = 0

class PaneManager:
    MAX_PANES = 5
    TOTAL_MEMORY_MB = 2048
    TOTAL_TOKENS = 200000

    def __init__(self):
        self.panes: dict[str, Pane] = {}
        self.active_pane_id: str | None = None
        self.on_warning: Callable[[Pane, str], None] | None = None

    def create_pane(self, repo_path: str, name: str | None = None) -> Pane | None:
        """Create a new pane with allocated budget."""
        if len(self.panes) >= self.MAX_PANES:
            self._warn("Maximum panes reached (5). Close a pane first.")
            return None

        # Calculate fair share budget
        num_panes = len(self.panes) + 1
        budget = PaneBudget(
            max_memory_mb=self.TOTAL_MEMORY_MB // num_panes,
            max_tokens=self.TOTAL_TOKENS // num_panes,
        )

        pane_id = self._generate_id()
        pane = Pane(
            id=pane_id,
            name=name or self._extract_repo_name(repo_path),
            repo_path=repo_path,
            budget=budget,
        )
        self.panes[pane_id] = pane

        # Rebalance existing panes
        self._rebalance_budgets()

        return pane

    def _rebalance_budgets(self):
        """Redistribute budgets when panes are added/removed."""
        num_panes = len(self.panes)
        if num_panes == 0:
            return

        per_pane_memory = self.TOTAL_MEMORY_MB // num_panes
        per_pane_tokens = self.TOTAL_TOKENS // num_panes

        for pane in self.panes.values():
            pane.budget.max_memory_mb = per_pane_memory
            pane.budget.max_tokens = per_pane_tokens

            # Check if rebalance puts pane over budget
            if pane.current_tokens > per_pane_tokens * pane.budget.warn_threshold:
                self._warn_pane(pane, "Approaching token limit after rebalance")

    def update_usage(self, pane_id: str, tokens: int, memory_mb: int):
        """Update pane resource usage and check limits."""
        pane = self.panes.get(pane_id)
        if not pane:
            return

        pane.current_tokens = tokens
        pane.current_memory_mb = memory_mb

        # Check thresholds
        token_ratio = tokens / pane.budget.max_tokens
        memory_ratio = memory_mb / pane.budget.max_memory_mb

        if token_ratio > pane.budget.warn_threshold:
            self._warn_pane(pane, f"Token usage at {token_ratio:.0%}")
        if memory_ratio > pane.budget.warn_threshold:
            self._warn_pane(pane, f"Memory usage at {memory_ratio:.0%}")

    def _warn_pane(self, pane: Pane, message: str):
        if self.on_warning:
            self.on_warning(pane, message)

    def _extract_repo_name(self, path: str) -> str:
        """Extract repo name from path (not owner/repo, just repo)."""
        return path.rstrip('/').split('/')[-1]
```

### Resource Warning Display

```
┌────────────────────────────────────────────────────────────────┐
│  ⚠ claude-continuity-kit: Token usage at 85%                  │
│    Consider: /clear or close pane                              │
└────────────────────────────────────────────────────────────────┘
```

---

## Multi-Repo Navigation

### Tab-Based Switching

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` | Switch to repo 1 |
| `Ctrl+2` | Switch to repo 2 |
| `Ctrl+3` | Switch to repo 3 |
| `Ctrl+N` | New repo pane |
| `Ctrl+W` | Close current pane |

### @ References

Reference files from other repos in chat:

```
User: Compare @claude-continuity-kit/src/auth.py with @other-project/auth.py

Claude: Looking at both files...
```

```python
# input/at_references.py
import re
from dataclasses import dataclass

@dataclass
class AtReference:
    repo_name: str
    path: str
    original: str

def parse_at_references(text: str, known_repos: list[str]) -> list[AtReference]:
    """Parse @repo/path references from input text."""
    refs = []
    pattern = r'@([a-zA-Z0-9_-]+)/([^\s]+)'

    for match in re.finditer(pattern, text):
        repo = match.group(1)
        path = match.group(2)

        if repo in known_repos:
            refs.append(AtReference(
                repo_name=repo,
                path=path,
                original=match.group(0),
            ))

    return refs
```

### Display Convention

Show repo name only (not owner/repo):

```
┌──────────────────────────────────────────────────────────────┐
│  [1] continuity-kit  [2] other-project  [3] experiments      │
├──────────────────────────────────────────────────────────────┤
```

---

## Message Navigation

### Keyboard Navigation

Navigate through messages without scroll flicker:

| Shortcut | Action |
|----------|--------|
| `Ctrl+Up` | Previous message |
| `Ctrl+Down` | Next message |
| `Ctrl+Home` | First message |
| `Ctrl+End` | Last message |
| `Ctrl+F` | Search messages |

### Per-Message Actions

```
┌────────────────────────────────────────────────────────────────┐
│  Claude: Here's the implementation for the auth module...      │
│                                                                │
│  ```python                                                     │
│  def authenticate(user, password):                             │
│      # ... implementation ...                                  │
│  ```                                                           │
│                                                                │
│  [F]ork | [V]iew Raw | [C]opy | [B]ranch from here            │
└────────────────────────────────────────────────────────────────┘
```

```python
# messages/actions.py
from enum import Enum, auto

class MessageAction(Enum):
    FORK = auto()       # Start new session from this message
    VIEW = auto()       # View raw markdown
    COPY = auto()       # Copy to clipboard
    BRANCH = auto()     # Branch session from this point

def handle_message_action(action: MessageAction, message_id: str):
    """Handle per-message action."""
    match action:
        case MessageAction.FORK:
            # Create new session with this message as context
            pass
        case MessageAction.VIEW:
            # Show raw markdown in overlay
            pass
        case MessageAction.COPY:
            # Copy message content to clipboard
            pass
        case MessageAction.BRANCH:
            # Branch session history from this point
            pass
```

---

## Tool Display

### Collapsed by Default

Tools are shown inline, collapsed:

```
[Read src/auth.py] ✓
[Bash npm test] ✓ (2.3s)
[Write src/login.tsx] ✓
[Grep "TODO" in src/] ✓ (15 matches)
```

### Expandable for Full Output

Click or press Enter to expand:

```
[Read src/auth.py] ✓
┌──────────────────────────────────────────────────────────────┐
│ def authenticate(user: str, password: str) -> bool:         │
│     """Authenticate a user."""                               │
│     if not user or not password:                             │
│         return False                                         │
│     ...                                                      │
│ [+42 more lines - press Enter to expand]                     │
└──────────────────────────────────────────────────────────────┘
```

### Truncation Rules

- **Output limit:** 20 lines by default, expand for full
- **Width limit:** Terminal width - 4 chars for borders
- **Long lines:** Truncated with `...` indicator
- **Expand key:** Enter shows full output in scrollable overlay

### Debug Mode

Show timing and stderr (also truncated):

```
[Bash npm test] ✓
┌──────────────────────────────────────────────────────────────┐
│ Time: 2.34s                                                  │
│ Exit: 0                                                      │
│ ──────────────────────────────────────────────────────────── │
│ stdout:                                                      │
│ PASS src/auth.test.ts                                        │
│ PASS src/login.test.ts                                       │
│ ──────────────────────────────────────────────────────────── │
│ stderr:                                                      │
│ npm warn deprecated uuid@3.4.0                               │
└──────────────────────────────────────────────────────────────┘
```

Toggle debug mode: `Ctrl+D`

---

## Input Box

### Rich Editor Features

```python
# input/editor.py
from dataclasses import dataclass

@dataclass
class InputState:
    text: str = ""
    cursor_pos: int = 0
    selection_start: int | None = None
    selection_end: int | None = None
    history_index: int = -1
    preview_mode: bool = False

class InputEditor:
    def __init__(self):
        self.state = InputState()
        self.history: list[str] = []
        self.attachments: list[Attachment] = []

    def handle_key(self, key: str):
        """Handle keyboard input."""
        match key:
            case 'Ctrl+Enter':
                self.submit()
            case 'Ctrl+P':
                self.toggle_preview()
            case 'Ctrl+V':
                self.paste_with_detection()
            case 'Up':
                if self.state.cursor_pos == 0:
                    self.history_back()
                else:
                    self.cursor_up()
            # ... more key handlers

    def toggle_preview(self):
        """Toggle markdown preview mode."""
        self.state.preview_mode = not self.state.preview_mode

    def paste_with_detection(self):
        """Paste with auto-detection of images/files."""
        content = get_clipboard()
        if is_image(content):
            self.add_attachment(ImageAttachment(content))
        elif is_file_path(content):
            self.add_attachment(FileAttachment(content))
        else:
            self.insert_text(content)
```

### Markdown Preview

Toggle with `Ctrl+P`:

```
┌────────────────────────────────────────────────────────────────┐
│ # Preview                                    [Ctrl+P to edit]  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Here's my **bold** request:                                    │
│                                                                │
│ 1. First item                                                  │
│ 2. Second item                                                 │
│                                                                │
│ `code snippet`                                                 │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Multimedia Attachments

Drag-drop or paste support:

| Type | Display |
|------|---------|
| Image | `[Image: screenshot.png 1.2MB]` |
| File | `[File: data.csv 45KB]` |
| URL | `[URL: https://example.com]` |

```
> Analyze this chart [Image: chart.png 234KB] and compare with @repo/data.csv
```

### @ Autocomplete

Type `@` to trigger repo autocomplete:

```
> Compare @cont|
            ┌──────────────────────┐
            │ continuity-kit       │
            │ continuity-archive   │
            └──────────────────────┘
```

---

## Session Tree

### Geometric Style Visualization

Git-graph inspired with interactive navigation:

```
         ●─────────●─────────●
         │         │         │
         │         │         └─────●
         │         │               │
         │         └─────●─────────●───────●
         │               │                 │
         └─────●         └─────●           └───●
               │               │               │
               ●               ●               ●

Legend: ● = Session  ─── = Continuation  │ = Branch
```

### Interactive Controls

| Key | Action |
|-----|--------|
| Arrow keys | Navigate nodes |
| `+` / `-` | Zoom in/out |
| `Shift+Arrows` | Pan view |
| `Enter` | Enter selected session |
| `F` | Fork from selected |
| `D` | Delete selected |
| `R` | Rename selected |
| `M` | Merge sessions |
| `C` | Compare two sessions |
| `/` | Search sessions |

### Session Node Info

```python
# sessions/tree.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class SessionNode:
    id: str
    timestamp: datetime
    summary: str
    tokens_used: int
    duration_seconds: int
    parent_id: str | None
    children: list[str]
    tags: list[str]

class SessionTree:
    def __init__(self):
        self.nodes: dict[str, SessionNode] = {}
        self.root_ids: list[str] = []
        self.viewport = Viewport(x=0, y=0, zoom=1.0)

    def render(self, screen: Screen):
        """Render tree with current viewport."""
        visible_nodes = self._get_visible_nodes()

        for node in visible_nodes:
            x, y = self._node_position(node)
            screen_x, screen_y = self._apply_viewport(x, y)

            if self._in_bounds(screen_x, screen_y):
                self._draw_node(screen, node, screen_x, screen_y)
                self._draw_connections(screen, node)

    def zoom(self, delta: float):
        """Zoom in/out."""
        self.viewport.zoom = max(0.25, min(4.0, self.viewport.zoom + delta))

    def pan(self, dx: int, dy: int):
        """Pan the view."""
        self.viewport.x += dx
        self.viewport.y += dy
```

### Session Actions

```
Selected: 2026-01-01 14:32 "Implement auth flow"
Tokens: 45.2k | Duration: 12m | Branch: main

Actions: [F]ork  [D]elete  [R]ename  [M]erge  [C]ompare
```

---

## Theming

### Auto-Detection

```python
# themes/detector.py
import os

def detect_background() -> str:
    """Detect terminal background color.

    Methods:
    1. Query terminal with OSC 11 escape sequence
    2. Check COLORFGBG environment variable
    3. Fall back to dark
    """
    # Try OSC 11 query
    bg = query_terminal_background()
    if bg:
        return 'light' if is_light_color(bg) else 'dark'

    # Check COLORFGBG (format: "fg;bg" e.g., "15;0")
    colorfgbg = os.environ.get('COLORFGBG', '')
    if colorfgbg:
        parts = colorfgbg.split(';')
        if len(parts) >= 2:
            bg_idx = int(parts[-1])
            return 'light' if bg_idx in (7, 15) else 'dark'

    return 'dark'  # Default
```

### Theme Presets

```python
# themes/presets.py
from dataclasses import dataclass

@dataclass
class Theme:
    name: str
    background: str
    foreground: str
    accent: str
    success: str
    warning: str
    error: str
    muted: str
    border: str

THEMES = {
    'dark': Theme(
        name='dark',
        background='#1a1a1a',
        foreground='#e0e0e0',
        accent='#61afef',
        success='#98c379',
        warning='#e5c07b',
        error='#e06c75',
        muted='#5c6370',
        border='#3e4451',
    ),
    'light': Theme(
        name='light',
        background='#fafafa',
        foreground='#383a42',
        accent='#4078f2',
        success='#50a14f',
        warning='#c18401',
        error='#e45649',
        muted='#a0a1a7',
        border='#d3d3d3',
    ),
    'dracula': Theme(
        name='dracula',
        background='#282a36',
        foreground='#f8f8f2',
        accent='#bd93f9',
        success='#50fa7b',
        warning='#ffb86c',
        error='#ff5555',
        muted='#6272a4',
        border='#44475a',
    ),
    'solarized-dark': Theme(
        name='solarized-dark',
        background='#002b36',
        foreground='#839496',
        accent='#268bd2',
        success='#859900',
        warning='#b58900',
        error='#dc322f',
        muted='#586e75',
        border='#073642',
    ),
}
```

### Custom Themes

```yaml
# ~/.config/rigg/theme.yaml
name: custom
colors:
  background: "#1e1e2e"
  foreground: "#cdd6f4"
  accent: "#89b4fa"
  success: "#a6e3a1"
  warning: "#f9e2af"
  error: "#f38ba8"
  muted: "#6c7086"
  border: "#313244"
```

```python
# themes/loader.py
import yaml
from pathlib import Path

def load_custom_theme() -> Theme | None:
    """Load custom theme from config."""
    config_path = Path.home() / '.config' / 'rigg' / 'theme.yaml'

    if not config_path.exists():
        return None

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return Theme(
        name=data['name'],
        **data['colors'],
    )
```

### Theme Switching

| Shortcut | Action |
|----------|--------|
| `Ctrl+T` | Cycle themes |
| `Ctrl+Shift+T` | Open theme picker |

---

## Input Modes

### Keyboard and Mouse Equality

Both input methods are fully supported:

```python
# input/handler.py
from abc import ABC, abstractmethod

class InputHandler(ABC):
    @abstractmethod
    def handle(self, event) -> bool:
        """Handle input event, return True if consumed."""
        pass

class KeyboardHandler(InputHandler):
    def handle(self, event):
        if event.type != 'key':
            return False
        # Handle keyboard navigation
        return True

class MouseHandler(InputHandler):
    def handle(self, event):
        if event.type not in ('click', 'scroll', 'drag'):
            return False
        # Handle mouse events
        return True

class InputRouter:
    def __init__(self):
        self.handlers = [KeyboardHandler(), MouseHandler()]

    def route(self, event):
        for handler in self.handlers:
            if handler.handle(event):
                break
```

### Mouse Support

| Action | Result |
|--------|--------|
| Click message | Select message |
| Click tool | Expand/collapse |
| Scroll | Scroll messages |
| Click tab | Switch repo |
| Click node (tree) | Select session |
| Drag (tree) | Pan view |
| Scroll wheel (tree) | Zoom |

---

## Editor Mode

### Built-in Editor

Configurable keybindings (vim/emacs/nano):

```yaml
# ~/.config/rigg/editor.yaml
mode: vim  # or: emacs, nano
tab_size: 4
show_line_numbers: true
wrap_lines: false
auto_indent: true
```

```python
# editor/keymaps.py
KEYMAPS = {
    'vim': {
        'normal': {
            'h': 'cursor_left',
            'j': 'cursor_down',
            'k': 'cursor_up',
            'l': 'cursor_right',
            'i': 'enter_insert',
            'a': 'enter_insert_after',
            'dd': 'delete_line',
            'yy': 'yank_line',
            'p': 'paste',
            ':w': 'save',
            ':q': 'quit',
            ':wq': 'save_and_quit',
        },
        'insert': {
            'Escape': 'enter_normal',
        },
    },
    'emacs': {
        'Ctrl+f': 'cursor_right',
        'Ctrl+b': 'cursor_left',
        'Ctrl+n': 'cursor_down',
        'Ctrl+p': 'cursor_up',
        'Ctrl+x Ctrl+s': 'save',
        'Ctrl+x Ctrl+c': 'quit',
    },
    'nano': {
        'Ctrl+o': 'save',
        'Ctrl+x': 'quit',
        'Ctrl+k': 'cut_line',
        'Ctrl+u': 'paste',
    },
}
```

---

## Command Palette

Triggered with `Ctrl+Shift+P`:

```
┌────────────────────────────────────────────────────────────────┐
│ > _                                                            │
├────────────────────────────────────────────────────────────────┤
│ > Switch to Research Mode                           Ctrl+1     │
│   Switch to Work Mode                               Ctrl+2     │
│   Open Session Tree                                 Ctrl+3     │
│   Open Editor                                       Ctrl+4     │
│   Toggle Theme                                      Ctrl+T     │
│   New Repo Pane                                     Ctrl+N     │
│   Close Pane                                        Ctrl+W     │
│   Clear Context                                     /clear     │
│   Search Sessions                                   Ctrl+F     │
│   Toggle Debug Mode                                 Ctrl+D     │
└────────────────────────────────────────────────────────────────┘
```

Fuzzy search filters commands as you type.

---

## Summary

| Feature | Implementation |
|---------|----------------|
| Rendering | Custom ANSI direct, differential updates |
| Terminal | Auto-detect + `RIGG_TERMINAL` override |
| Modes | Auto-detect + manual (Ctrl+1/2/3/4) |
| Panes | Built-in, max 5, dynamic resource budgets |
| Multi-repo | Tabs + @ references |
| Navigation | Ctrl+arrows, flicker-free |
| Tools | Collapsed default, expandable, debug mode |
| Input | Rich editor, markdown preview, attachments |
| Session Tree | Geometric, zoom/pan, full CRUD |
| Theming | Auto-detect background, presets + custom |
| Input modes | Keyboard = mouse equality |
| Editor | Vim/emacs/nano configurable |

---

## Files to Create

| File | Purpose |
|------|---------|
| `rigg/core/render.py` | Screen buffer, differential updates |
| `rigg/core/terminal.py` | Terminal detection, capabilities |
| `rigg/modes/detector.py` | Activity-based mode detection |
| `rigg/modes/layouts.py` | Layout definitions per mode |
| `rigg/panes/manager.py` | Pane lifecycle, resource budgets |
| `rigg/input/editor.py` | Rich input box |
| `rigg/input/at_references.py` | @ reference parsing |
| `rigg/messages/navigator.py` | Message navigation |
| `rigg/messages/actions.py` | Per-message actions |
| `rigg/tools/display.py` | Tool rendering, collapse/expand |
| `rigg/sessions/tree.py` | Session tree visualization |
| `rigg/themes/detector.py` | Background detection |
| `rigg/themes/presets.py` | Built-in themes |
| `rigg/themes/loader.py` | Custom theme loading |
| `rigg/editor/keymaps.py` | Vim/emacs/nano keybindings |
| `rigg/palette/commands.py` | Command palette |
