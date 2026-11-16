"""Data polling for Agent Monitor TUI.

Uses Textual Worker pattern for async polling (NOT set_interval).
Wraps sync CoordinationDB calls via lambda in run_in_executor.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

import httpx
import psutil

from scripts.agentica_patterns.coordination import (
    AgentRecord,
    CoordinationDB,
    OrphanCandidate,
)
from scripts.agentica_patterns.blackboard import BlackboardCache, SharedContextEntry


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float = 0.0
    memory_used_mb: int = 0
    memory_total_mb: int = 16384


@dataclass
class HomeData:
    """Data for Home panel."""
    agent_count: int = 0
    running_agents: int = 0
    session_count: int = 0
    metrics: SystemMetrics = field(default_factory=SystemMetrics)
    session_started: datetime | None = None

    def fingerprint(self) -> str:
        """Generate stable fingerprint for change detection."""
        # Round CPU to avoid constant changes from minor fluctuations
        cpu_bucket = int(self.metrics.cpu_percent // 5) * 5  # 5% buckets
        mem_bucket = self.metrics.memory_used_mb // 100 * 100  # 100MB buckets
        return f"{self.agent_count}:{self.running_agents}:{self.session_count}:{cpu_bucket}:{mem_bucket}"


@dataclass
class AgentsData:
    """Data for Agents panel."""
    agents: list[AgentRecord] = field(default_factory=list)
    orphans: list[OrphanCandidate] = field(default_factory=list)
    by_pattern: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Generate stable fingerprint for change detection."""
        # Time bucket (10s intervals) ensures duration updates without constant flicker
        now = datetime.now(UTC).replace(tzinfo=None)
        agent_fp = ",".join(
            f"{a.id}:{a.status}:{int((now - a.spawned_at.replace(tzinfo=None)).total_seconds() // 10)}"
            for a in sorted(self.agents, key=lambda x: x.id)
        )
        pattern_fp = ",".join(f"{k}:{v}" for k, v in sorted(self.by_pattern.items()))
        status_fp = ",".join(f"{k}:{v}" for k, v in sorted(self.by_status.items()))
        orphan_fp = ",".join(sorted(o.agent_id for o in self.orphans))
        return f"{len(self.agents)}:{agent_fp}:{pattern_fp}:{status_fp}:{orphan_fp}"


@dataclass
class BlackboardData:
    """Data for Blackboard panel."""
    entries: list[SharedContextEntry] = field(default_factory=list)
    summary: str = ""

    def fingerprint(self) -> str:
        """Generate stable fingerprint for change detection."""
        # Entry fingerprint: id + priority + type + truncated content
        entry_fp = ",".join(
            f"{e.id}:{e.priority.value}:{e.type.value}:{e.content[:20]}"
            for e in sorted(self.entries, key=lambda x: x.id)
        )
        return f"{len(self.entries)}:{entry_fp}:{self.summary}"


@dataclass
class ServerStatus:
    """Status of a server (proxy or Agentica)."""
    name: str
    url: str
    healthy: bool = False
    last_check: datetime | None = None
    error: str | None = None
    pid: int | None = None  # Tracked process ID if started by us


# Server configuration for process management
SERVER_CONFIGS: dict[str, dict[str, Any]] = {
    "claude_proxy": {
        "command": ["uv", "run", "python", "scripts/agentica_patterns/claude_proxy.py", "--port", "8080"],
        "port": 8080,
        "name": "Claude Proxy",
        "url": "http://localhost:8080",
    },
    "agentica_server": {
        # Must run from agentica-server directory with INFERENCE_ENDPOINT_URL set
        # See: .claude/skills/agentica-server/SKILL.md
        "command": ["uv", "run", "agentica-server", "--port", "2345"],
        "port": 2345,
        "name": "Agentica Server",
        "url": "http://localhost:2345",
        "cwd": "workspace/agentica-research/agentica-server",
        "env": {"INFERENCE_ENDPOINT_URL": "http://localhost:8080/v1/chat/completions"},
    },
}


@dataclass
class SettingsData:
    """Data for Settings panel."""
    claude_proxy: ServerStatus = field(default_factory=lambda: ServerStatus(
        name="Claude Proxy",
        url="http://localhost:8080",
    ))
    agentica_server: ServerStatus = field(default_factory=lambda: ServerStatus(
        name="Agentica Server",
        url="http://localhost:2345",
    ))
    current_theme: str = "dark"
    poll_interval: float = 1.0
    db_path: str = ""


@dataclass
class KillResult:
    """Result of attempting to kill an agent process."""
    success: bool
    pid: int | None
    error: str | None = None


# ============================================================
# Agent Cleanup Functions
# ============================================================


def is_stale_agent(agent: AgentRecord, threshold_hours: int = 24) -> bool:
    """Check if an agent is stale (older than threshold).

    Args:
        agent: The agent record to check
        threshold_hours: Hours after which agent is considered stale (default: 24)

    Returns:
        True if agent is stale, False otherwise
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    spawned = agent.spawned_at.replace(tzinfo=None)
    age = now - spawned
    return age >= timedelta(hours=threshold_hours)


def filter_stale_agents(
    agents: list[AgentRecord],
    threshold_hours: int = 24,
) -> list[AgentRecord]:
    """Filter out stale agents from a list.

    Args:
        agents: List of agent records to filter
        threshold_hours: Hours after which agent is considered stale

    Returns:
        List of non-stale agents
    """
    return [a for a in agents if not is_stale_agent(a, threshold_hours)]


def kill_agent(pid: int | None) -> KillResult:
    """Kill an agent process by PID.

    Sends SIGTERM to the specified PID. Handles common error cases:
    - Invalid PID (None, 0, negative)
    - Process not found (OSError)
    - Permission denied (PermissionError)

    Args:
        pid: Process ID to kill

    Returns:
        KillResult with success status and any error message
    """
    # Validate PID
    if pid is None or pid <= 0:
        return KillResult(
            success=False,
            pid=pid,
            error="Invalid PID: must be a positive integer",
        )

    try:
        os.kill(pid, signal.SIGTERM)
        return KillResult(success=True, pid=pid, error=None)
    except OSError as e:
        return KillResult(success=False, pid=pid, error=str(e))
    except PermissionError as e:
        return KillResult(success=False, pid=pid, error=str(e))


class DataPoller:
    """Async data poller for Agent Monitor.

    Key design decisions (from review):
    1. Uses lambda wrapper for ThreadPoolExecutor: `lambda: db.method()`
    2. BlackboardCache is sync but fast - wrap in executor for safety
    3. MemoryService removed (Option B - simple summary)
    4. All methods have try/except with sensible defaults
    """

    def __init__(self):
        """Initialize poller with lazy connections."""
        self._db: CoordinationDB | None = None
        self._blackboard: BlackboardCache | None = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._connected = False
        self._server_pids: dict[str, int] = {}  # Track PIDs of servers we started

    async def connect(self) -> None:
        """Connect to data sources."""
        if self._connected:
            return

        # CoordinationDB is sync, connects on __init__
        self._db = CoordinationDB()

        # BlackboardCache needs project_id
        project_id = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        project_id = Path(project_id).name  # Just the directory name
        self._blackboard = BlackboardCache(project_id)

        self._connected = True

    async def disconnect(self) -> None:
        """Clean up resources and stop all tracked servers."""
        # Stop all servers we started
        for name in list(self._server_pids.keys()):
            await self.stop_server(name)
        self._server_pids.clear()

        self._executor.shutdown(wait=False)
        self._connected = False

    async def _run_sync(self, func: Any) -> Any:
        """Run sync function in thread pool.

        Uses lambda wrapper pattern per review:
        `await loop.run_in_executor(None, lambda: db.get_running_agents())`
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func)

    async def _check_server_health(self, url: str, timeout: float = 2.0) -> tuple[bool, str | None]:
        """Check if a server is healthy by hitting its /health endpoint.

        Returns:
            Tuple of (is_healthy, error_message_or_none)
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{url}/health", timeout=timeout)
                return resp.status_code == 200, None
        except httpx.TimeoutException:
            return False, "Connection timed out"
        except httpx.ConnectError:
            return False, "Connection refused"
        except Exception as e:
            return False, str(e)

    async def poll_home(self) -> HomeData:
        """Poll data for Home panel."""
        if not self._connected or not self._db:
            return HomeData()

        try:
            # Get system metrics (always available)
            metrics = SystemMetrics(
                cpu_percent=psutil.cpu_percent(interval=0.1),
                memory_used_mb=int(psutil.virtual_memory().used / 1024 / 1024),
                memory_total_mb=int(psutil.virtual_memory().total / 1024 / 1024),
            )
        except Exception:
            metrics = SystemMetrics()

        try:
            # Use lambda wrapper for sync DB calls
            summary = await self._run_sync(lambda: self._db.get_session_summary())
            all_summary = await self._run_sync(lambda: self._db.get_all_sessions_summary())
            # Get current session's visible agents count
            running_agents = await self._run_sync(lambda: self._db.get_all_running_agents())
            visible_agent_count = len(running_agents) if running_agents else 0

            return HomeData(
                agent_count=visible_agent_count,  # Show visible agents, not all-time count
                running_agents=summary.get("agents_by_status", {}).get("running", 0),
                session_count=all_summary.get("total_sessions", 0),
                metrics=metrics,
                session_started=None,  # Could extract from DB if needed
            )
        except Exception:
            return HomeData(metrics=metrics)

    async def poll_agents(self) -> AgentsData:
        """Poll data for Agents panel."""
        if not self._connected or not self._db:
            return AgentsData()

        try:
            # get_all_running_agents EXISTS in coordination.py (line 401)
            agents = await self._run_sync(lambda: self._db.get_all_running_agents())
            orphans = await self._run_sync(lambda: self._db.find_orphans())
            summary = await self._run_sync(lambda: self._db.get_session_summary())

            return AgentsData(
                agents=agents or [],
                orphans=orphans or [],
                by_pattern=summary.get("agents_by_pattern", {}),
                by_status=summary.get("agents_by_status", {}),
            )
        except Exception:
            return AgentsData()

    async def poll_blackboard(self) -> BlackboardData:
        """Poll data for Blackboard panel."""
        if not self._connected or not self._blackboard:
            return BlackboardData()

        try:
            # BlackboardCache.poll() is sync but fast (file read)
            # Wrap in executor for safety
            entries = await self._run_sync(lambda: self._blackboard.poll())
            summary = await self._run_sync(lambda: self._blackboard.get_summary())

            return BlackboardData(
                entries=entries or [],
                summary=summary or "",
            )
        except Exception:
            return BlackboardData()

    async def poll_settings(self, current_theme: str = "dark") -> SettingsData:
        """Poll data for Settings panel - check server health."""
        now = datetime.now()

        # Check Claude Proxy health
        proxy_healthy, proxy_error = await self._check_server_health("http://localhost:8080")
        proxy_status = ServerStatus(
            name="Claude Proxy",
            url="http://localhost:8080",
            healthy=proxy_healthy,
            last_check=now,
            error=proxy_error,
            pid=self._server_pids.get("claude_proxy"),
        )

        # Check Agentica Server health
        agentica_healthy, agentica_error = await self._check_server_health("http://localhost:2345")
        agentica_status = ServerStatus(
            name="Agentica Server",
            url="http://localhost:2345",
            healthy=agentica_healthy,
            last_check=now,
            error=agentica_error,
            pid=self._server_pids.get("agentica_server"),
        )

        # Get DB path if connected
        db_path = ""
        if self._db:
            try:
                db_path = str(self._db._db_path) if hasattr(self._db, '_db_path') else ""
            except Exception:
                pass

        return SettingsData(
            claude_proxy=proxy_status,
            agentica_server=agentica_status,
            current_theme=current_theme,
            poll_interval=1.0,
            db_path=db_path,
        )

    # ========================================
    # Agent Cleanup Methods
    # ========================================

    def clean_stale_agents(self, data: AgentsData) -> AgentsData:
        """Remove stale agents from display data.

        Filters out agents older than 24 hours while preserving
        other data fields (orphans, by_pattern, by_status).

        Args:
            data: Current agents data

        Returns:
            New AgentsData with stale agents removed
        """
        fresh_agents = filter_stale_agents(data.agents)
        return AgentsData(
            agents=fresh_agents,
            orphans=data.orphans,
            by_pattern=data.by_pattern,
            by_status=data.by_status,
        )

    async def kill_agent_async(self, pid: int) -> KillResult:
        """Kill an agent process asynchronously.

        Wraps the sync kill_agent function for async context.

        Args:
            pid: Process ID to kill

        Returns:
            KillResult with success status and any error message
        """
        return await self._run_sync(lambda: kill_agent(pid))

    # ========================================
    # Server Control Methods
    # ========================================

    async def kill_orphans(self, port: int) -> tuple[bool, str | None]:
        """Kill any processes using the specified port.

        Uses lsof to find processes listening on the port and kills them.

        Args:
            port: Port number to check

        Returns:
            Tuple of (success, error_message_or_none)
        """
        try:
            # Use lsof to find processes on the port
            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Parse lsof output to find PIDs
            # Format: COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME
            pids_to_kill = set()
            for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1])
                            pids_to_kill.add(pid)
                        except ValueError:
                            continue

            # Kill each process found
            for pid in pids_to_kill:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass  # Process might have already exited

            return True, None
        except subprocess.TimeoutExpired:
            return False, "Timeout finding processes on port"
        except Exception as e:
            return False, str(e)

    async def start_server(self, name: str) -> tuple[bool, str | None]:
        """Start a server by name.

        Kills any orphan processes on the port first, then spawns the server.

        Args:
            name: Server name ("claude_proxy" or "agentica_server")

        Returns:
            Tuple of (success, error_message_or_none)
        """
        if name not in SERVER_CONFIGS:
            return False, f"Unknown server: {name}"

        config = SERVER_CONFIGS[name]

        # Kill any orphan processes on the port first
        await self.kill_orphans(config["port"])

        try:
            # Prepare environment (inherit current + add config-specific vars)
            env = os.environ.copy()
            if "env" in config:
                env.update(config["env"])

            # Determine working directory (relative to project root)
            cwd = None
            if "cwd" in config:
                project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
                cwd = os.path.join(project_dir, config["cwd"])

            # Start the server process
            process = subprocess.Popen(
                config["command"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,  # Detach from parent
                env=env,
                cwd=cwd,
            )

            # Check if process started successfully
            if process.poll() is None:  # Still running
                self._server_pids[name] = process.pid
                return True, None
            else:
                return False, f"Process exited immediately with code {process.poll()}"

        except FileNotFoundError as e:
            return False, f"Command not found: {e}"
        except Exception as e:
            return False, str(e)

    async def stop_server(self, name: str) -> tuple[bool, str | None]:
        """Stop a server by name.

        Sends SIGTERM to the tracked PID for the server.

        Args:
            name: Server name ("claude_proxy" or "agentica_server")

        Returns:
            Tuple of (success, error_message_or_none)
        """
        if name not in self._server_pids:
            return False, f"Server not running (no PID tracked for {name})"

        pid = self._server_pids[name]

        try:
            os.kill(pid, signal.SIGTERM)
            del self._server_pids[name]
            return True, None
        except OSError:
            # Process already dead - still remove from tracking
            del self._server_pids[name]
            return True, None
        except Exception as e:
            del self._server_pids[name]
            return False, str(e)

    async def restart_server(self, name: str) -> tuple[bool, str | None]:
        """Restart a server by name.

        Stops the server (if running) and starts it again.

        Args:
            name: Server name ("claude_proxy" or "agentica_server")

        Returns:
            Tuple of (success, error_message_or_none)
        """
        # Stop first (ignore errors - might not be running)
        await self.stop_server(name)

        # Then start
        return await self.start_server(name)

    async def mark_dead_agents(self, threshold_hours: int = 24) -> int:
        """Mark stale 'running' agents as 'completed' in the database.

        This cleans up zombie agents that are still marked as running
        but are from old sessions (e.g., 5+ days old).

        Args:
            threshold_hours: Hours after which running agents are considered dead

        Returns:
            Number of agents marked as completed
        """
        if not self._db:
            return 0

        try:
            # Use direct SQL to update stale running agents
            def do_update() -> int:
                import sqlite3
                conn = sqlite3.connect(self._db._db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE agents SET status='completed'
                    WHERE status='running'
                    AND datetime(spawned_at) < datetime('now', ?)
                    """,
                    (f'-{threshold_hours} hours',),
                )
                count = cursor.rowcount
                conn.commit()
                conn.close()
                return count

            return await self._run_sync(do_update)
        except Exception:
            return 0
