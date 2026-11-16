"""Entry point for Agent Monitor TUI.

Run with:
    uv run python -m scripts.agent_monitor_tui

Or:
    uv run python scripts/agent_monitor_tui/__main__.py

Options:
    --no-autostart    Don't auto-start Claude Proxy and Agentica Server
"""

import argparse
from scripts.agent_monitor_tui.app import run_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Monitor TUI")
    parser.add_argument(
        "--no-autostart",
        action="store_true",
        help="Don't auto-start Claude Proxy and Agentica Server",
    )
    args = parser.parse_args()
    run_app(auto_start_servers=not args.no_autostart)
