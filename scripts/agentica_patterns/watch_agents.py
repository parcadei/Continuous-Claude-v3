#!/usr/bin/env python3
"""Watch running Agentica agents in real-time with subprocess monitoring.

USAGE:
    uv run python scripts/agentica/watch_agents.py --watch
    uv run python scripts/agentica/watch_agents.py --watch --logs
    uv run python scripts/agentica/watch_agents.py --monitor --watch-dir ./scripts
    uv run python scripts/agentica/watch_agents.py --completed
    uv run python scripts/agentica/watch_agents.py --summary
    uv run python scripts/agentica/watch_agents.py --pattern swarm

SUBPROCESS MONITORING:
    The --monitor flag enables tracking of:
    - Claude CLI processes (`claude -p` subprocesses)
    - File changes in watched directories
    - Process tree relationships

LOG TAILING:
    The --logs flag enables streaming agent messages from ./logs/agent-*.log:
    - Shows recent agent input/output in a table
    - Direction indicators: > (input to agent), < (output from agent)
    - Use --logs-dir to specify custom log directory

PATTERN-AWARE VISUALIZATION:
    Automatically selects visualizer based on agent pattern:
    - ParallelVisualizer: Multi-bar progress (swarm, jury, map_reduce)
    - SequentialVisualizer: Stage markers (pipeline, generator_critic)
    - HierarchicalVisualizer: Tree with badges (hierarchical, dependency_swarm)
    - Default: Table view for unknown patterns
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Add project root to path for standalone execution
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

RICH_AVAILABLE = False
try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, TaskID, TextColumn
    from rich.table import Table
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    pass

if TYPE_CHECKING:
    from rich.table import Table

import json
import re
from scripts.agentica_patterns.coordination import CoordinationDB, AgentRecord, OrphanCandidate  # noqa: E402


# =============================================================================
# Log Tailing
# =============================================================================


@dataclass
class LogMessage:
    """Represents a parsed log message."""
    agent_id: str
    role: str  # "user" or "agent"
    content: str
    timestamp: float


class LogTailer:
    """Tail agent log files for real-time message streaming."""

    def __init__(self, logs_dir: str = "./logs"):
        self.logs_dir = Path(logs_dir)
        self._file_positions: dict[str, int] = {}
        self._messages: list[LogMessage] = []
        self._max_messages = 20

    def get_new_messages(self) -> list[LogMessage]:
        """Get new messages from all agent log files."""
        new_messages: list[LogMessage] = []

        if not self.logs_dir.exists():
            return new_messages

        for log_file in self.logs_dir.glob("agent-*.log"):
            agent_id = log_file.stem.replace("agent-", "")
            file_key = str(log_file)

            try:
                current_size = log_file.stat().st_size
                last_pos = self._file_positions.get(file_key, 0)

                if current_size > last_pos:
                    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        new_content = f.read()
                        self._file_positions[file_key] = f.tell()

                        # Parse messages from new content
                        parsed = self._parse_messages(agent_id, new_content)
                        new_messages.extend(parsed)
            except (OSError, IOError):
                pass

        # Add to buffer and trim
        self._messages.extend(new_messages)
        self._messages = self._messages[-self._max_messages:]

        return new_messages

    def get_recent_messages(self, limit: int = 10) -> list[LogMessage]:
        """Get the most recent messages."""
        return self._messages[-limit:]

    def _parse_messages(self, agent_id: str, content: str) -> list[LogMessage]:
        """Parse log content into LogMessage objects."""
        messages = []
        # Match <message role="...">...</message> patterns
        pattern = r'<message role="([^"]+)">\s*(.*?)\s*</message>'
        matches = re.findall(pattern, content, re.DOTALL)

        for role, msg_content in matches:
            # Clean up role (remove suffixes like <instructions>)
            clean_role = role.split("<")[0].strip()
            # Truncate content for display
            truncated = msg_content.strip()[:100]
            if len(msg_content.strip()) > 100:
                truncated += "..."

            messages.append(LogMessage(
                agent_id=agent_id,
                role=clean_role,
                content=truncated,
                timestamp=time.time(),
            ))

        return messages


# =============================================================================
# Pattern-Aware Visualizers
# =============================================================================


PARALLEL_PATTERNS = {"swarm", "jury", "map_reduce", "mapreduce"}
SEQUENTIAL_PATTERNS = {"pipeline", "generator_critic", "generatorcritic"}
HIERARCHICAL_PATTERNS = {"hierarchical", "dependency_swarm", "dependencyswarm"}


def get_visualizer_type(agents: list) -> str:
    """Determine which visualizer to use based on agent patterns."""
    if not agents:
        return "table"

    patterns = {(a.pattern or "").lower() for a in agents}

    if patterns & PARALLEL_PATTERNS:
        return "parallel"
    elif patterns & SEQUENTIAL_PATTERNS:
        return "sequential"
    elif patterns & HIERARCHICAL_PATTERNS:
        return "hierarchical"
    return "table"


class ParallelVisualizer:
    """Multi-bar progress for Swarm, Jury, MapReduce patterns."""

    def __init__(self):
        self.progress = Progress(
            TextColumn("[bold]{task.fields[agent_id]}"),
            BarColumn(bar_width=30),
            TextColumn("[cyan]{task.fields[pattern]}"),
            TextColumn("[dim]{task.fields[elapsed]}"),
        )
        self._tasks: dict[str, TaskID] = {}

    def render(self, agents: list) -> Panel:
        """Render parallel progress bars."""
        # Update tasks
        current_ids = {a.id for a in agents}

        # Remove completed agents
        for agent_id in list(self._tasks.keys()):
            if agent_id not in current_ids:
                self.progress.remove_task(self._tasks[agent_id])
                del self._tasks[agent_id]

        # Add/update agents
        for agent in agents:
            elapsed = format_elapsed(agent.spawned_at)
            if agent.id not in self._tasks:
                task_id = self.progress.add_task(
                    agent.id,
                    total=100,
                    completed=50,  # Indeterminate
                    agent_id=agent.id[:8],
                    pattern=agent.pattern or "-",
                    elapsed=elapsed,
                )
                self._tasks[agent.id] = task_id
            else:
                self.progress.update(
                    self._tasks[agent.id],
                    agent_id=agent.id[:8],
                    pattern=agent.pattern or "-",
                    elapsed=elapsed,
                )

        return Panel(self.progress, title="[bold green]Parallel Agents", border_style="green")


class SequentialVisualizer:
    """Single progress with stage marker for Pipeline, GeneratorCritic patterns."""

    def __init__(self):
        self._stages: list[str] = []

    def render(self, agents: list) -> Panel:
        """Render sequential stage progress."""
        if not agents:
            return Panel("[dim]No agents running", title="Sequential Pipeline")

        # Build stage list
        stage_lines = []
        for i, agent in enumerate(agents):
            premise = (agent.premise or "Stage")[:30]
            elapsed = format_elapsed(agent.spawned_at)
            status = agent.status

            if status == "running":
                marker = "[bold yellow]>>>[/]"
                style = "bold yellow"
            elif status == "completed":
                marker = "[green]+++[/]"
                style = "green"
            else:
                marker = "[dim]---[/]"
                style = "dim"

            stage_lines.append(f"{marker} [{style}]{premise}[/] [dim]({elapsed})[/]")

        content = "\n".join(stage_lines) if stage_lines else "[dim]No stages[/]"
        return Panel(content, title="[bold blue]Sequential Pipeline", border_style="blue")


class HierarchicalVisualizer:
    """Tree with status badges for Hierarchical, DependencySwarm patterns."""

    def render(self, agents: list) -> Panel:
        """Render hierarchical tree structure."""
        tree = Tree("[bold]Agent Hierarchy")

        # Group by parent
        by_parent: dict[str | None, list] = {}
        for agent in agents:
            parent = agent.parent_agent_id
            if parent not in by_parent:
                by_parent[parent] = []
            by_parent[parent].append(agent)

        def add_children(parent_tree, parent_id: str | None):
            children = by_parent.get(parent_id, [])
            for agent in children:
                elapsed = format_elapsed(agent.spawned_at)
                status = agent.status

                if status == "running":
                    badge = "[bold yellow]RUN[/]"
                elif status == "completed":
                    badge = "[green]OK[/]"
                else:
                    badge = "[red]ERR[/]"

                premise = (agent.premise or "Agent")[:25]
                label = f"{badge} {agent.id[:6]} {premise} [dim]({elapsed})[/]"
                child_tree = parent_tree.add(label)
                add_children(child_tree, agent.id)

        # Add root level agents
        add_children(tree, None)

        # Also add any agents whose parents aren't in the current list
        known_ids = {a.id for a in agents}
        for agent in agents:
            if agent.parent_agent_id and agent.parent_agent_id not in known_ids:
                # This is an orphan (parent not running) - add at root
                if agent.id not in [c.label for c in tree.children]:
                    elapsed = format_elapsed(agent.spawned_at)
                    badge = "[bold yellow]RUN[/]" if agent.status == "running" else "[green]OK[/]"
                    premise = (agent.premise or "Agent")[:25]
                    label = f"{badge} {agent.id[:6]} {premise} [dim]({elapsed})[/]"
                    tree.add(label)

        return Panel(tree, title="[bold magenta]Hierarchical", border_style="magenta")


# =============================================================================
# Subprocess Monitoring Functions
# =============================================================================


def is_unix_orphan(pid: int) -> bool:
    """Check if a process is a Unix orphan (ppid == 1).

    A Unix orphan is a process whose parent has died and has been
    adopted by init/launchd (PID 1). This is used for orphan detection
    in the three-tier orphan classification system.

    Args:
        pid: The process ID to check.

    Returns:
        True if the process exists and its parent is init/launchd (PID 1).
        False if process doesn't exist, has a living parent, or on any error.
    """
    if pid <= 0:
        return False

    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "ppid="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                ppid = int(output)
                return ppid == 1
        return False  # Process doesn't exist or ps failed
    except (subprocess.TimeoutExpired, ValueError):
        return False


def find_claude_processes() -> list[dict[str, Any]]:
    """Find running claude CLI processes.

    Returns:
        List of dicts with pid, command, parent_pid, and elapsed time.
    """
    processes = []
    try:
        # Use ps to find claude processes (works on macOS and Linux)
        result = subprocess.run(
            ["ps", "-eo", "pid,ppid,etime,command"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    pid, ppid, elapsed, command = parts
                    # Filter for claude-related processes
                    if "claude" in command.lower() and "-p" in command:
                        processes.append({
                            "pid": int(pid),
                            "parent_pid": int(ppid),
                            "elapsed": elapsed,
                            "command": command[:80],  # Truncate long commands
                        })
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return processes


def get_process_tree(parent_pid: int) -> list[dict[str, Any]]:
    """Get all child processes of a given PID (recursive).

    Args:
        parent_pid: The parent process ID to find children for.

    Returns:
        List of child process dicts with pid, command, and depth.
    """
    children = []
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(parent_pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for pid_str in result.stdout.strip().split("\n"):
                if pid_str:
                    pid = int(pid_str)
                    # Get command for this process
                    cmd_result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "command="],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    command = cmd_result.stdout.strip() if cmd_result.returncode == 0 else ""
                    children.append({
                        "pid": pid,
                        "parent_pid": parent_pid,
                        "command": command[:60],
                    })
                    # Recurse to find grandchildren
                    children.extend(get_process_tree(pid))
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return children


@dataclass
class FileChange:
    """Represents a file system change."""

    path: str
    type: str  # "created", "modified", "deleted"
    timestamp: float
    size: int = 0


class DirectoryWatcher:
    """Watch a directory for file changes."""

    def __init__(self, directory: str):
        self.directory = Path(directory)
        self._snapshot: dict[str, float] = {}
        self._take_snapshot()

    def _take_snapshot(self) -> None:
        """Take a snapshot of current file mtimes."""
        self._snapshot = {}
        if self.directory.exists():
            for f in self.directory.rglob("*"):
                if f.is_file():
                    try:
                        self._snapshot[str(f)] = f.stat().st_mtime
                    except OSError:
                        pass

    def get_changes(self) -> list[dict[str, Any]]:
        """Get changes since last check.

        Returns:
            List of change dicts with type, path, and timestamp.
        """
        changes = []
        current: dict[str, float] = {}

        if self.directory.exists():
            for f in self.directory.rglob("*"):
                if f.is_file():
                    try:
                        mtime = f.stat().st_mtime
                        current[str(f)] = mtime

                        if str(f) not in self._snapshot:
                            changes.append({
                                "type": "created",
                                "path": str(f),
                                "timestamp": mtime,
                            })
                        elif mtime > self._snapshot[str(f)]:
                            changes.append({
                                "type": "modified",
                                "path": str(f),
                                "timestamp": mtime,
                            })
                    except OSError:
                        pass

        # Check for deleted files
        for path in self._snapshot:
            if path not in current:
                changes.append({
                    "type": "deleted",
                    "path": path,
                    "timestamp": time.time(),
                })

        self._snapshot = current
        return changes


def watch_directory_changes(directory: str) -> DirectoryWatcher:
    """Create a directory watcher.

    Args:
        directory: Path to directory to watch.

    Returns:
        DirectoryWatcher instance.
    """
    return DirectoryWatcher(directory)


class SubprocessMonitor:
    """Unified subprocess and file system monitor.

    Tracks:
    - Running claude CLI processes
    - File changes in watched directories
    - Process trees
    """

    def __init__(self, watch_dirs: list[str] | None = None):
        """Initialize monitor.

        Args:
            watch_dirs: List of directories to watch for file changes.
        """
        self.watch_dirs = watch_dirs or []
        self._watchers = [DirectoryWatcher(d) for d in self.watch_dirs]
        self._snapshot_time: float | None = None
        self._snapshot_files: dict[str, float] = {}

    def take_snapshot(self) -> None:
        """Take a snapshot of current state for later comparison."""
        self._snapshot_time = time.time()
        self._snapshot_files = {}
        for watcher in self._watchers:
            self._snapshot_files.update(watcher._snapshot.copy())

    def get_diff_since_snapshot(self) -> dict[str, Any]:
        """Get changes since last snapshot.

        Returns:
            Dict with new_files, modified_files, deleted_files.
        """
        if self._snapshot_time is None:
            return {"new_files": [], "modified_files": [], "deleted_files": []}

        current_files: dict[str, float] = {}
        for watcher in self._watchers:
            watcher._take_snapshot()
            current_files.update(watcher._snapshot)

        new_files = [p for p in current_files if p not in self._snapshot_files]
        modified_files = [
            p for p in current_files
            if p in self._snapshot_files and current_files[p] > self._snapshot_files[p]
        ]
        deleted_files = [p for p in self._snapshot_files if p not in current_files]

        return {
            "new_files": new_files,
            "modified_files": modified_files,
            "deleted_files": deleted_files,
        }

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive status of all monitoring.

        Returns:
            Dict with claude_processes, file_changes, and timestamp.
        """
        # Gather file changes from all watchers
        all_changes = []
        for watcher in self._watchers:
            all_changes.extend(watcher.get_changes())

        return {
            "claude_processes": find_claude_processes(),
            "file_changes": all_changes,
            "timestamp": datetime.now(UTC).isoformat(),
            "watched_dirs": self.watch_dirs,
        }


def format_elapsed(start: datetime) -> str:
    """Format elapsed time as human-readable string."""
    now = datetime.now(UTC).replace(tzinfo=None)
    elapsed = now - start
    total_seconds = int(elapsed.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        return f"{total_seconds // 60}m {total_seconds % 60}s"
    else:
        return f"{total_seconds // 3600}h {(total_seconds % 3600) // 60}m"


def create_running_table(agents) -> Table:
    """Create table of running agents."""
    table = Table(title="Running Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Pattern", style="green")
    table.add_column("Premise", style="white")
    table.add_column("Elapsed", style="magenta")

    for agent in agents:
        premise = agent.premise or ""
        premise_display = premise[:40] + "..." if len(premise) > 40 else premise
        table.add_row(
            agent.id,
            agent.pattern or "-",
            premise_display,
            format_elapsed(agent.spawned_at),
        )

    return table


def create_running_table_all_sessions(agents) -> Table:
    """Create table of running agents with Session column for all-sessions view."""
    table = Table(title="Running Agents (All Sessions)")
    table.add_column("Session", style="yellow")
    table.add_column("ID", style="cyan")
    table.add_column("Pattern", style="green")
    table.add_column("Premise", style="white")
    table.add_column("Elapsed", style="magenta")

    for agent in agents:
        premise = agent.premise or ""
        premise_display = premise[:40] + "..." if len(premise) > 40 else premise
        # Truncate session ID to 8 chars for display
        session_display = agent.session_id[:8] if len(agent.session_id) > 8 else agent.session_id
        table.add_row(
            session_display,
            agent.id,
            agent.pattern or "-",
            premise_display,
            format_elapsed(agent.spawned_at),
        )

    return table


def create_subprocess_table(processes: list[dict[str, Any]]) -> Table:
    """Create table of running Claude subprocesses."""
    table = Table(title="Claude Subprocesses")
    table.add_column("PID", style="cyan")
    table.add_column("Parent", style="yellow")
    table.add_column("Elapsed", style="magenta")
    table.add_column("Command", style="white")

    for proc in processes:
        table.add_row(
            str(proc.get("pid", "-")),
            str(proc.get("parent_pid", "-")),
            proc.get("elapsed", "-"),
            proc.get("command", "-")[:60],
        )

    return table


def create_file_changes_table(changes: list[dict[str, Any]]) -> Table:
    """Create table of file changes."""
    table = Table(title="File Changes")
    table.add_column("Type", style="green")
    table.add_column("Path", style="white")
    table.add_column("Time", style="dim")

    style_map = {"created": "green", "modified": "yellow", "deleted": "red"}
    for change in changes[-10:]:  # Last 10 changes
        change_type = change.get("type", "unknown")
        style = style_map.get(change_type, "white")
        ts = change.get("timestamp", 0)
        time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else "-"
        table.add_row(
            f"[{style}]{change_type}[/]",
            Path(change.get("path", "")).name,
            time_str,
        )

    return table


def create_orphan_table(orphans: list[OrphanCandidate]) -> Table:
    """Create table of orphan candidates."""
    table = Table(title="Orphan Candidates")
    table.add_column("Tier", style="red")
    table.add_column("Agent ID", style="cyan")
    table.add_column("Age", style="magenta")
    table.add_column("Reason", style="white")

    for orphan in orphans:
        age = format_elapsed(orphan.spawned_at)
        table.add_row(
            str(orphan.tier),
            orphan.agent_id,
            age,
            orphan.reason,
        )

    return table


def create_message_table(messages: list[LogMessage]) -> Table:
    """Create table of recent agent messages."""
    table = Table(title="Agent Messages")
    table.add_column("Agent", style="cyan", width=6)
    table.add_column("Dir", style="yellow", width=3)
    table.add_column("Message", style="white", no_wrap=False)

    for msg in messages[-10:]:  # Last 10 messages
        # Direction indicator
        if msg.role == "agent":
            direction = "[green]\u25c4[/]"  # Left arrow (agent output)
        else:
            direction = "[blue]\u25ba[/]"   # Right arrow (user input)

        # Truncate message for table
        content = msg.content.replace("\n", " ").replace("\t", " ")
        if len(content) > 60:
            content = content[:57] + "..."

        table.add_row(
            msg.agent_id[:6],
            direction,
            content,
        )

    return table


def main():
    parser = argparse.ArgumentParser(description="Watch running Agentica agents")
    parser.add_argument("--watch", "-w", action="store_true", help="Watch in real-time")
    parser.add_argument("--completed", "-c", action="store_true", help="Show completed tasks")
    parser.add_argument("--summary", "-s", action="store_true", help="Show session summary")
    parser.add_argument("--pattern", "-p", type=str, help="Filter by pattern")
    parser.add_argument("--session", type=str, help="Session ID")
    parser.add_argument("--all-sessions", "-a", action="store_true", help="Show agents from all sessions")
    parser.add_argument("--monitor", "-m", action="store_true", help="Enable subprocess monitoring")
    parser.add_argument("--watch-dir", type=str, action="append", help="Directory to watch for file changes")
    parser.add_argument("--logs", "-l", action="store_true", help="Enable log tailing for agent messages")
    parser.add_argument("--logs-dir", type=str, default="./logs", help="Directory containing agent log files")
    parser.add_argument("--orphans", "-o", action="store_true", help="Show orphan candidates")
    parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    db = CoordinationDB(session_id=args.session)

    # Setup subprocess monitor if requested
    monitor = None
    if args.monitor or args.watch_dir:
        watch_dirs = args.watch_dir or []
        monitor = SubprocessMonitor(watch_dirs=watch_dirs)

    # Setup log tailer if requested
    log_tailer = None
    if args.logs:
        log_tailer = LogTailer(logs_dir=args.logs_dir)

    # Setup pattern-aware visualizers
    parallel_viz = ParallelVisualizer() if RICH_AVAILABLE else None
    sequential_viz = SequentialVisualizer() if RICH_AVAILABLE else None
    hierarchical_viz = HierarchicalVisualizer() if RICH_AVAILABLE else None

    # Handle --orphans flag
    if args.orphans:
        orphans = db.find_orphans()
        if args.json:
            # JSON output format
            orphan_dicts = [
                {
                    "tier": o.tier,
                    "agent_id": o.agent_id,
                    "reason": o.reason,
                    "age": format_elapsed(o.spawned_at),
                    "spawned_at": o.spawned_at.isoformat(),
                    "ppid": o.ppid,
                    "parent_agent_id": o.parent_agent_id,
                }
                for o in orphans
            ]
            print(json.dumps(orphan_dicts, indent=2))
        elif RICH_AVAILABLE:
            console = Console()
            if not orphans:
                console.print("[dim]No orphan candidates found[/]")
            else:
                console.print(create_orphan_table(orphans))
        else:
            if not orphans:
                print("No orphan candidates found")
            else:
                for o in orphans:
                    age = format_elapsed(o.spawned_at)
                    print(f"Tier {o.tier}: {o.agent_id} - {o.reason} ({age})")
        return

    if RICH_AVAILABLE:
        console = Console()
        if args.summary:
            summary = db.get_session_summary()
            console.print(f"[bold]Session:[/] {summary['session_id']}")
            console.print(f"[bold]By Status:[/] {summary['agents_by_status']}")
            console.print(f"[bold]By Pattern:[/] {summary['agents_by_pattern']}")
            console.print(f"[bold]Tasks:[/] {summary['total_tasks']}")

            # Show subprocess info if monitoring
            if monitor:
                status = monitor.get_status()
                console.print(f"\n[bold]Claude Processes:[/] {len(status['claude_processes'])}")
                for proc in status['claude_processes']:
                    console.print(f"  PID {proc['pid']}: {proc['command'][:50]}")
        elif args.watch:
            with Live(console=console, refresh_per_second=2) as live:
                try:
                    file_changes: list[dict[str, Any]] = []
                    while True:
                        # Use all-sessions query if flag is set
                        if args.all_sessions:
                            agents = db.get_all_running_agents(pattern=args.pattern)
                        else:
                            agents = db.get_running_agents(pattern=args.pattern)

                        # Collect log messages if tailing enabled
                        if log_tailer:
                            log_tailer.get_new_messages()

                        # Build combined display
                        tables: list[Any] = []

                        # Choose visualizer based on pattern
                        viz_type = get_visualizer_type(agents)

                        if not agents:
                            tables.append("[dim]No running agents[/]")
                        elif viz_type == "parallel" and parallel_viz:
                            tables.append(parallel_viz.render(agents))
                        elif viz_type == "sequential" and sequential_viz:
                            tables.append(sequential_viz.render(agents))
                        elif viz_type == "hierarchical" and hierarchical_viz:
                            tables.append(hierarchical_viz.render(agents))
                        elif args.all_sessions:
                            # Use all-sessions table for cross-session view
                            tables.append(create_running_table_all_sessions(agents))
                        else:
                            # Default table view
                            tables.append(create_running_table(agents))

                        # Add message table if log tailing enabled
                        if log_tailer:
                            messages = log_tailer.get_recent_messages(10)
                            if messages:
                                tables.append(create_message_table(messages))

                        if monitor:
                            status = monitor.get_status()
                            file_changes.extend(status.get("file_changes", []))

                            if status["claude_processes"]:
                                proc_table = create_subprocess_table(
                                    status["claude_processes"]
                                )
                                tables.append(proc_table)

                            if file_changes:
                                tables.append(create_file_changes_table(file_changes))

                        live.update(Group(*tables))

                        time.sleep(0.5)
                except KeyboardInterrupt:
                    pass
        else:
            # Use all-sessions query if flag is set
            if args.all_sessions:
                agents = db.get_all_running_agents(pattern=args.pattern)
                console.print(create_running_table_all_sessions(agents))
            else:
                agents = db.get_running_agents(pattern=args.pattern)
                console.print(create_running_table(agents))

            # Show subprocess info if monitoring
            if monitor:
                status = monitor.get_status()
                if status["claude_processes"]:
                    console.print(create_subprocess_table(status["claude_processes"]))
    else:
        print("Install 'rich' for better output: uv pip install rich")
        # Use all-sessions query if flag is set
        if args.all_sessions:
            agents = db.get_all_running_agents(pattern=args.pattern)
            for agent in agents:
                session_display = agent.session_id[:8] if len(agent.session_id) > 8 else agent.session_id
                print(f"{session_display} | {agent.id} | {agent.pattern} | {format_elapsed(agent.spawned_at)}")
        else:
            for agent in db.get_running_agents(pattern=args.pattern):
                print(f"{agent.id} | {agent.pattern} | {format_elapsed(agent.spawned_at)}")

        if monitor:
            status = monitor.get_status()
            for proc in status["claude_processes"]:
                print(f"PROC {proc['pid']} | {proc['elapsed']} | {proc['command'][:50]}")


if __name__ == "__main__":
    main()
