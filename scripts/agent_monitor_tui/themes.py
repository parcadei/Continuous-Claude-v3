"""Color themes for Agent Monitor TUI.

Four themes with industrial/utilitarian terminal aesthetic:
- dark: High contrast dark theme (default)
- light: Clean light theme for bright environments
- catppuccin: Warm, cozy pastel palette
- nord: Cool, arctic color scheme
"""

from textual.theme import Theme


# Industrial Dark - Default theme
DARK_THEME = Theme(
    name="agent-dark",
    primary="#00ff88",      # Matrix green for active elements
    secondary="#888888",    # Muted gray for secondary
    accent="#ff6b35",       # Warning orange for alerts
    background="#0a0a0a",   # Near-black background
    surface="#1a1a1a",      # Slightly lighter panels
    error="#ff3366",        # Red for errors
    success="#00ff88",      # Green for success
    warning="#ffaa00",      # Amber for warnings
    dark=True,
)


# Industrial Light - Clean light theme
LIGHT_THEME = Theme(
    name="agent-light",
    primary="#006644",      # Deep green
    secondary="#666666",    # Medium gray
    accent="#cc4400",       # Deep orange
    background="#f5f5f5",   # Off-white
    surface="#ffffff",      # Pure white panels
    error="#cc0033",        # Dark red
    success="#006644",      # Dark green
    warning="#cc6600",      # Dark amber
    dark=False,
)


# Catppuccin Mocha - Warm pastel palette
CATPPUCCIN_THEME = Theme(
    name="agent-catppuccin",
    primary="#a6e3a1",      # Green (matching catppuccin)
    secondary="#9399b2",    # Overlay2
    accent="#f9e2af",       # Yellow
    background="#1e1e2e",   # Base
    surface="#313244",      # Surface0
    error="#f38ba8",        # Red
    success="#a6e3a1",      # Green
    warning="#fab387",      # Peach
    dark=True,
)


# Nord - Arctic color scheme
NORD_THEME = Theme(
    name="agent-nord",
    primary="#88c0d0",      # Nord8 - frost blue
    secondary="#4c566a",    # Nord3 - gray
    accent="#ebcb8b",       # Nord13 - yellow
    background="#2e3440",   # Nord0 - polar night
    surface="#3b4252",      # Nord1 - darker
    error="#bf616a",        # Nord11 - red
    success="#a3be8c",      # Nord14 - green
    warning="#d08770",      # Nord12 - orange
    dark=True,
)


# Theme registry
THEMES: dict[str, Theme] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
    "catppuccin": CATPPUCCIN_THEME,
    "nord": NORD_THEME,
}

THEME_NAMES: list[str] = list(THEMES.keys())


def get_theme(name: str) -> Theme:
    """Get theme by name with fallback to dark."""
    return THEMES.get(name, DARK_THEME)


def next_theme(current: str) -> str:
    """Get next theme name in rotation."""
    try:
        idx = THEME_NAMES.index(current)
        return THEME_NAMES[(idx + 1) % len(THEME_NAMES)]
    except ValueError:
        return THEME_NAMES[0]
