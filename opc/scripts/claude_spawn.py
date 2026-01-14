"""Headless Claude CLI spawning with depth control and routing.

Spawns Claude agents via `claude -p` command with:
- Depth limit enforcement (max 3 levels)
- Environment variable propagation
- Deterministic agent routing
- CoordinationDB registration
"""

import json
import logging
import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

import psutil

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Concurrent Agent Limits (Gap 1 Implementation)
# =============================================================================

# Soft limit: Log warning when reached, but allow spawning
SOFT_AGENT_LIMIT = 50

# Hard limit: Reject spawn attempts when reached
HARD_AGENT_LIMIT = 100


class AgentLimitExceededError(Exception):
    """Raised when agent spawn would exceed hard limit."""

    def __init__(self, current: int, limit: int):
        self.current = current
        self.limit = limit
        super().__init__(f"Agent limit exceeded: {current} agents running, limit is {limit}")


class _AgentCounter:
    """Thread-safe counter for tracking concurrent agent count.

    Uses threading.Lock for synchronization since spawn_agent() is synchronous.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._count = 0
        self._pids: set[int] = set()
        self._pid_to_agent: dict[int, str] = {}  # pid → agent_id for completion tracking

    @property
    def count(self) -> int:
        """Get current agent count."""
        with self._lock:
            return self._count

    @property
    def pids(self) -> set[int]:
        """Get set of tracked PIDs (copy for thread safety)."""
        with self._lock:
            return self._pids.copy()

    def increment(self, pid: int, agent_id: str | None = None) -> int:
        """Increment counter and track PID.

        Args:
            pid: Process ID to track.
            agent_id: Optional agent ID for completion tracking.

        Returns:
            New count after increment.
        """
        with self._lock:
            self._count += 1
            self._pids.add(pid)
            if agent_id:
                self._pid_to_agent[pid] = agent_id
            return self._count

    def decrement(self, pid: int) -> tuple[int, str | None]:
        """Decrement counter and remove PID.

        Args:
            pid: Process ID to remove.

        Returns:
            Tuple of (new count, agent_id if tracked).
        """
        with self._lock:
            agent_id = self._pid_to_agent.pop(pid, None)
            if pid in self._pids:
                self._pids.discard(pid)
                self._count = max(0, self._count - 1)
            return self._count, agent_id


class _ProcessMonitor:
    """Background thread that monitors spawned processes.

    Decrements the agent counter when processes exit.
    Uses os.kill(pid, 0) to check process liveness.
    """

    def __init__(self, counter: _AgentCounter, check_interval: float = 1.0):
        """Initialize process monitor.

        Args:
            counter: The agent counter to update.
            check_interval: Seconds between liveness checks.
        """
        self._counter = counter
        self._check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background monitor thread."""
        if self._thread is not None and self._thread.is_alive():
            return  # Already running

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="agent-process-monitor",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background monitor thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._check_interval + 0.5)

    def _monitor_loop(self) -> None:
        """Main monitor loop - check process liveness periodically."""
        while not self._stop_event.wait(self._check_interval):
            self._check_processes()

    def _check_processes(self) -> None:
        """Check if tracked processes are still alive and update DB on exit."""
        pids_to_check = self._counter.pids  # Get copy

        for pid in pids_to_check:
            try:
                os.kill(pid, 0)  # Check if process exists
            except OSError:
                # Process no longer exists - decrement and get agent_id
                _, agent_id = self._counter.decrement(pid)
                logger.debug(f"Process {pid} exited, decremented agent count")

                # Update database with completion status
                if agent_id:
                    self._handle_agent_completion(agent_id)

    def _handle_agent_completion(self, agent_id: str) -> None:
        """Read output file and update database with completion status."""
        import asyncio

        output_file = f"/tmp/claude-agents/{agent_id}.json"
        status = "completed"
        result_summary = None

        try:
            if os.path.exists(output_file):
                with open(output_file) as f:
                    data = json.load(f)
                    subtype = data.get("subtype", "unknown")
                    if subtype in ("success",):
                        status = "completed"
                    elif subtype in ("error", "error_tool", "error_api"):
                        status = "failed"
                    result_summary = data.get("result", "")[:500]  # Truncate
        except Exception as e:
            logger.warning(f"Failed to read output for {agent_id}: {e}")
            status = "failed"

        # Update database (fire-and-forget)
        try:
            asyncio.run(self._update_agent_status(agent_id, status, result_summary))
        except Exception as e:
            logger.warning(f"Failed to update DB for {agent_id}: {e}")

    async def _update_agent_status(
        self, agent_id: str, status: str, result_summary: str | None
    ) -> None:
        """Update agent status in PostgreSQL."""
        try:
            import asyncpg

            conn = await asyncpg.connect(
                os.environ.get("DATABASE_URL", "postgresql://claude:claude_dev@localhost:5432/continuous_claude")
            )
            await conn.execute(
                """
                UPDATE agents
                SET status = $1, completed_at = NOW(), result_summary = $2
                WHERE agent_id = $3
                """,
                status,
                result_summary,
                agent_id,
            )
            await conn.close()
            logger.debug(f"Updated agent {agent_id} status to {status}")
        except Exception as e:
            logger.warning(f"DB update failed for {agent_id}: {e}")


# Global counter and monitor instances
_agent_counter = _AgentCounter()
_process_monitor = _ProcessMonitor(_agent_counter)

# Start monitor when module is loaded
_process_monitor.start()


def get_agent_count() -> int:
    """Get current count of tracked agents.

    Returns:
        Number of agents currently tracked.
    """
    return _agent_counter.count


def increment_agent_count(pid: int) -> int:
    """Increment the agent counter.

    Args:
        pid: Process ID to track.

    Returns:
        New count after increment.
    """
    return _agent_counter.increment(pid)


def decrement_agent_count(pid: int) -> int:
    """Decrement the agent counter.

    Args:
        pid: Process ID to remove.

    Returns:
        New count after decrement.
    """
    return _agent_counter.decrement(pid)


class DepthLimitExceeded(Exception):
    """Raised when spawn depth exceeds maximum allowed."""

    pass


@dataclass
class SpawnedAgent:
    """Record of a spawned Claude agent."""

    pid: int
    agent_id: str
    output_file: str
    depth_level: int
    pattern: str | None = None
    premise: str | None = None


@dataclass
class AgentProfile:
    """Agent configuration from .claude/agents/*.json"""

    name: str
    description: str
    prompt: str
    tools: list[str]
    model: str
    permissions: str  # "skip" or "queue"
    blocked_patterns: list[str]
    inherit_blocks: bool


def load_agent_profile(agent_name: str) -> AgentProfile | None:
    """Load agent profile from .claude/agents/{name}.json.

    Args:
        agent_name: Name of the agent (e.g., "kraken", "spark")

    Returns:
        AgentProfile if found, None otherwise
    """
    # Check multiple possible locations (project dir, CWD, home)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    search_paths = [
        Path(project_dir) / ".claude/agents" / f"{agent_name}.json" if project_dir else None,
        Path(".claude/agents") / f"{agent_name}.json",
        Path.home() / ".claude/agents" / f"{agent_name}.json",
        # Also check parent .opc-dev location
        Path.home() / ".opc-dev/.claude/agents" / f"{agent_name}.json",
    ]
    search_paths = [p for p in search_paths if p is not None]

    for profile_path in search_paths:
        if profile_path.exists():
            try:
                data = json.loads(profile_path.read_text())
                return AgentProfile(
                    name=data.get("name", agent_name),
                    description=data.get("description", ""),
                    prompt=data.get("prompt", ""),
                    tools=data.get("tools", []),
                    model=data.get("model", "sonnet"),
                    permissions=data.get("permissions", "skip"),
                    blocked_patterns=data.get("blocked_patterns", []),
                    inherit_blocks=data.get("inherit_blocks", True),
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load agent profile {profile_path}: {e}")
                return None

    return None


# Max depth before hard rejection
MAX_DEPTH = 3

# Agent routing table: keyword patterns -> agent name
AGENT_ROUTING = {
    # Orchestrate (check first - high priority)
    r"\b(coordinate|orchestrate|multi-agent)\b": "maestro",
    # Implement
    r"\b(implement|build|create)\b.*\b(feature|system|module)\b": "kraken",
    r"\b(fix|tweak|update|small)\b": "spark",
    # Document
    r"\b(document|handoff|summarize|ledger)\b": "scribe",
    # Debug
    r"\b(security|vulnerability|CVE|audit)\b": "aegis",
    r"\b(performance|memory|slow|race|profile)\b": "profiler",
    r"\b(debug|investigate|error|bug|crash)\b": "sleuth",
    # Validate
    r"\b(e2e|end-to-end|acceptance)\b": "atlas",
    r"\b(test|validate|verify|unit|integration)\b": "arbiter",
    # Research
    r"\b(research|best practices|NIA|learn)\b": "oracle",
    r"\b(analyze repo|external repo|github)\b": "pathfinder",
    r"\b(find|locate|where|codebase)\b": "scout",
    # Plan (check refactor first, then general plan)
    r"\b(refactor|migration|cleanup)\b": "phoenix",
    r"\b(plan|design)\b.*\b(feature|dashboard|new|api|endpoint)\b": "architect",
    # Review
    r"\b(review)\b.*\b(refactor|migration)\b": "warden",
    r"\b(review)\b": "sentinel",
    # Session/History
    r"\b(session|precedent|history|context)\b": "chronicler",
    # Deploy
    r"\b(deploy|release|version|changelog)\b": "herald",
}


def check_spawn_allowed() -> bool:
    """Check if spawning is allowed based on depth and resources.

    Returns:
        True if spawn is allowed, False otherwise.
    """
    depth = int(os.environ.get("DEPTH_LEVEL", "0"))

    # Hard depth limit
    if depth >= MAX_DEPTH:
        return False

    return True


def resources_available() -> bool:
    """Check if system resources are available for spawning.

    Returns:
        True if resources are available (CPU < 80%, memory < 85%).
    """
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem_percent = psutil.virtual_memory().percent

        return cpu_percent < 80 and mem_percent < 85
    except Exception:
        # If we can't check, assume available
        return True


def route_to_agent(prompt: str) -> str:
    """Route a prompt to the appropriate agent using keyword matching.

    Args:
        prompt: The task prompt to route.

    Returns:
        Agent name (kraken, spark, scribe, etc.)
    """
    prompt_lower = prompt.lower()

    # Try each pattern in order
    for pattern, agent in AGENT_ROUTING.items():
        if re.search(pattern, prompt_lower, re.IGNORECASE):
            return agent

    # Default fallback
    return "spark"


# =============================================================================
# Helper Functions for spawn_agent/spawn_lead (Reduces Cognitive Complexity)
# =============================================================================


def _check_depth_limit(depth_level: int) -> None:
    """Check if depth level exceeds maximum allowed.

    Args:
        depth_level: Current depth level.

    Raises:
        DepthLimitExceeded: If depth_level >= MAX_DEPTH.
    """
    if depth_level >= MAX_DEPTH:
        raise DepthLimitExceeded(f"Max nesting depth ({MAX_DEPTH}) reached")


def _check_agent_limits() -> None:
    """Check concurrent agent limits and log/raise as appropriate.

    Raises:
        AgentLimitExceededError: If at or above hard limit.

    Logs warning if at or above soft limit but below hard limit.
    """
    current_count = _agent_counter.count

    if current_count >= HARD_AGENT_LIMIT:
        raise AgentLimitExceededError(current=current_count, limit=HARD_AGENT_LIMIT)

    if current_count >= SOFT_AGENT_LIMIT:
        logger.warning(
            f"Soft agent limit reached: {current_count} agents running "
            f"(soft limit: {SOFT_AGENT_LIMIT}, hard limit: {HARD_AGENT_LIMIT})"
        )


def _should_skip_permissions(profile: "AgentProfile | None") -> bool:
    """Determine if permissions should be skipped.

    Args:
        profile: Agent profile or None.

    Returns:
        True if permissions should be skipped (default), False if 'queue'.
    """
    if profile and profile.permissions == "queue":
        return False
    return True


def _get_effective_tools(
    profile: "AgentProfile | None",
    allowed_tools: list[str] | None,
) -> list[str] | None:
    """Get effective tools list from profile or parameter.

    Args:
        profile: Agent profile or None.
        allowed_tools: Tools from function parameter.

    Returns:
        List of tools to use, or None.
    """
    if profile and profile.tools:
        return profile.tools
    return allowed_tools


def _build_spawn_command(
    prompt: str,
    agent_id: str,
    perspective: str | None,
    skip_permissions: bool,
    tools: list[str] | None,
    system_prompt_path: Path | None,
    profile_prompt: str | None = None,
    model: str | None = None,
) -> list[str]:
    """Build the command list for spawning a Claude agent.

    Args:
        prompt: Task prompt.
        agent_id: Unique agent identifier.
        perspective: Optional perspective prefix.
        skip_permissions: Whether to skip permission prompts.
        tools: List of allowed tools.
        system_prompt_path: Path to system prompt file.
        profile_prompt: Agent-specific persona/instructions from profile.
        model: Model to use (opus, sonnet, haiku).

    Returns:
        Command list for subprocess.Popen.
    """
    # Build full prompt: profile persona + task
    if profile_prompt and perspective:
        full_prompt = f"{profile_prompt}\n\nTask: {prompt}"
    elif perspective:
        full_prompt = f"{perspective}: {prompt}"
    else:
        full_prompt = prompt

    cmd = [
        "claude",
        "-p",
        full_prompt,
        "--session-id",
        agent_id,
        "--max-turns",
        "100",
        "--output-format",
        "json",  # Use json (not stream-json which requires --verbose)
    ]

    # Add model if specified
    if model:
        cmd.extend(["--model", model])

    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")

    if tools:
        cmd.extend(["--allowedTools", ",".join(tools)])

    if system_prompt_path and system_prompt_path.exists():
        cmd.extend(["--append-system-prompt", str(system_prompt_path)])

    return cmd


def _build_spawn_environment(
    depth_level: int,
    agent_id: str,
    pattern: str | None,
) -> dict[str, str]:
    """Build environment variables for spawned agent.

    Args:
        depth_level: Current depth level.
        agent_id: Unique agent identifier.
        pattern: Coordination pattern.

    Returns:
        Environment dict for subprocess.
    """
    env = os.environ.copy()
    env.update(
        {
            "DEPTH_LEVEL": str(depth_level + 1),
            "PARENT_AGENT_ID": os.environ.get("AGENT_ID", "orchestrator"),
            "AGENT_ID": agent_id,
            "SESSION_ID": os.environ.get("SESSION_ID", "default"),
        }
    )

    if pattern:
        env["PATTERN_TYPE"] = pattern

    return env


def _load_worker_profiles(workers: list[str]) -> dict | None:
    """Load worker agent profiles into JSON dict.

    Args:
        workers: List of worker agent names.

    Returns:
        Dict of worker profiles or None if empty.
    """
    agents_json = {}
    for name in workers:
        profile = load_agent_profile(name)
        if profile:
            agents_json[name] = {
                "description": profile.description,
                "prompt": profile.prompt,
                "tools": profile.tools if profile.tools else [],
                "model": profile.model,
            }
        else:
            logger.warning(f"Worker profile not found: {name}")

    return agents_json if agents_json else None


def _build_lead_command(
    task: str,
    agent_id: str,
    model: str,
    agents_json: dict | None,
    system_prompt_path: Path | None,
    context: str | None,
) -> list[str]:
    """Build the command list for spawning a Lead agent.

    Args:
        task: Task prompt.
        agent_id: Unique agent identifier.
        model: Model to use.
        agents_json: Worker agent definitions.
        system_prompt_path: Path to system prompt file.
        context: Additional context to append.

    Returns:
        Command list for subprocess.Popen.
    """
    cmd = [
        "claude",
        "-p",
        task,
        "--session-id",
        agent_id,
        "--dangerously-skip-permissions",
        "--max-turns",
        "100",
        "--output-format",
        "json",  # Use json (not stream-json which requires --verbose)
        "--model",
        model,
    ]

    if agents_json:
        cmd.extend(["--agents", json.dumps(agents_json)])

    if system_prompt_path and system_prompt_path.exists():
        cmd.extend(["--append-system-prompt", str(system_prompt_path)])

    if context:
        cmd.extend(["--append-system-prompt", context])

    return cmd


def spawn_agent(
    prompt: str,
    perspective: str = "",
    depth_level: int | None = None,
    allowed_tools: list[str] | None = None,
    pattern: str | None = None,
    agent_id: str | None = None,
) -> SpawnedAgent:
    """Spawn a headless Claude agent via `claude -p`.

    Args:
        prompt: The task prompt for the agent.
        perspective: Optional perspective prefix (e.g., "Security expert").
        depth_level: Override depth level (defaults to env var + 1).
        allowed_tools: List of tools to allow (e.g., ["Read", "Grep"]).
        pattern: Coordination pattern (swarm, hierarchical, etc.).
        agent_id: Override agent ID (defaults to UUID).

    Returns:
        SpawnedAgent with process info and tracking data.

    Raises:
        DepthLimitExceeded: If spawn would exceed max depth.
        AgentLimitExceededError: If spawn would exceed hard agent limit.
    """
    # Resolve depth level from environment if not provided
    if depth_level is None:
        depth_level = int(os.environ.get("DEPTH_LEVEL", "0"))

    # Validate limits using helper functions
    _check_depth_limit(depth_level)
    _check_agent_limits()

    # Generate agent ID if not provided
    if agent_id is None:
        agent_id = str(uuid.uuid4())

    # Create output directory and file
    output_dir = "/tmp/claude-agents"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{agent_id}.json")

    # Load agent profile and determine effective configuration
    profile = load_agent_profile(perspective) if perspective else None
    skip_permissions = _should_skip_permissions(profile)
    effective_tools = _get_effective_tools(profile, allowed_tools)

    # Log queue permissions
    if profile and not skip_permissions:
        logger.info(f"Agent {perspective} uses 'queue' permissions - will pause for approval")

    # Build command using helper - inject profile.prompt and profile.model
    system_prompt_path = Path(__file__).parent / "agent_system_prompt.md"
    cmd = _build_spawn_command(
        prompt=prompt,
        agent_id=agent_id,
        perspective=perspective or None,
        skip_permissions=skip_permissions,
        tools=effective_tools,
        system_prompt_path=system_prompt_path if system_prompt_path.exists() else None,
        profile_prompt=profile.prompt if profile else None,
        model=profile.model if profile else None,
    )

    # Build environment using helper
    env = _build_spawn_environment(depth_level, agent_id, pattern)

    # Spawn process
    # NOTE: Don't use `with` - file must stay open while agent runs
    # The OS will close the file handle when the subprocess exits
    output_fh = open(output_file, "w")
    proc = subprocess.Popen(
        cmd,
        stdout=output_fh,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    # Don't close output_fh - agent process owns it now

    # Track and register (pass agent_id for completion tracking)
    _agent_counter.increment(pid=proc.pid, agent_id=agent_id)
    swarm_id = os.environ.get("SWARM_ID", env["SESSION_ID"])
    register_agent_in_db(
        agent_id=agent_id,
        session_id=env["SESSION_ID"],
        pid=proc.pid,
        parent=env["PARENT_AGENT_ID"],
        pattern=pattern,
        premise=perspective or None,
        depth_level=depth_level + 1,
        swarm_id=swarm_id,
    )

    return SpawnedAgent(
        pid=proc.pid,
        agent_id=agent_id,
        output_file=output_file,
        depth_level=depth_level + 1,
        pattern=pattern,
        premise=perspective,
    )


def register_agent_in_db(
    agent_id: str,
    session_id: str,
    pid: int,
    parent: str,
    pattern: str | None = None,
    premise: str | None = None,
    depth_level: int = 1,
    swarm_id: str | None = None,
) -> None:
    """Register agent in CoordinationDB (sync wrapper).

    In production, this would call CoordinationDBPg.register_agent().
    For now, we write to a local tracking file as fallback.

    Args:
        agent_id: Unique agent identifier.
        session_id: Session this agent belongs to.
        pid: Process ID.
        parent: Parent agent ID.
        pattern: Coordination pattern.
        premise: Agent premise/perspective.
        depth_level: Nesting depth.
        swarm_id: Optional swarm grouping ID (defaults to session_id).
    """
    import json
    from datetime import UTC, datetime

    # Use session_id as default swarm_id
    effective_swarm_id = swarm_id if swarm_id is not None else session_id

    # Try PostgreSQL first
    try:
        import asyncio

        from scripts.agentica_patterns.coordination_pg import CoordinationDBPg

        async def _register():
            async with CoordinationDBPg() as db:
                await db.register_agent(
                    agent_id=agent_id,
                    session_id=session_id,
                    pid=pid,
                    parent_agent_id=parent if parent != "orchestrator" else None,
                    pattern=pattern,
                    premise=premise,
                    depth_level=depth_level,
                    swarm_id=effective_swarm_id,
                )

        asyncio.run(_register())
        return
    except Exception:
        pass  # Fall back to file-based tracking

    # Fallback: write to tracking file
    tracking_file = "/tmp/claude-agents/registry.jsonl"
    os.makedirs(os.path.dirname(tracking_file), exist_ok=True)

    record = {
        "agent_id": agent_id,
        "session_id": session_id,
        "pid": pid,
        "parent_agent_id": parent,
        "pattern": pattern,
        "premise": premise,
        "depth_level": depth_level,
        "swarm_id": effective_swarm_id,
        "spawned_at": datetime.now(UTC).isoformat(),
        "status": "running",
    }

    with open(tracking_file, "a") as f:
        f.write(json.dumps(record) + "\n")


# Lead agents that can spawn other agents
LEAD_AGENTS = {"kraken", "architect", "phoenix", "herald", "maestro"}

# Worker agents (leaf nodes, no spawning)
WORKER_AGENTS = {
    "spark",
    "scribe",
    "sleuth",
    "aegis",
    "profiler",
    "arbiter",
    "atlas",
    "oracle",
    "scout",
    "pathfinder",
    "sentinel",
    "warden",
    "chronicler",
}


def is_lead_agent(agent_name: str) -> bool:
    """Check if an agent is a Lead (can spawn others).

    Args:
        agent_name: Name of the agent.

    Returns:
        True if the agent is a Lead.
    """
    return agent_name.lower() in LEAD_AGENTS


def is_worker_agent(agent_name: str) -> bool:
    """Check if an agent is a Worker (leaf node).

    Args:
        agent_name: Name of the agent.

    Returns:
        True if the agent is a Worker.
    """
    return agent_name.lower() in WORKER_AGENTS


def spawn_lead(
    task: str,
    workers: list[str] | None = None,
    context: str = "",
    model: str = "sonnet",
    pattern: str | None = None,
) -> SpawnedAgent:
    """Spawn a Lead agent with worker definitions.

    This function spawns a Lead agent (like kraken, architect) that can
    coordinate worker agents. Worker profiles are loaded and passed via
    the --agents flag so the Lead knows what workers are available.

    Args:
        task: The task prompt for the Lead agent.
        workers: List of worker agent names to make available (e.g., ["spark", "arbiter"]).
        context: Additional system context to append.
        model: Model to use (opus/sonnet/haiku). Default sonnet.
        pattern: Optional pattern type for routing/tracking.

    Returns:
        SpawnedAgent with process info and tracking IDs.

    Example:
        >>> agent = spawn_lead(
        ...     task="Implement user authentication",
        ...     workers=["spark", "arbiter", "scribe"],
        ...     model="opus"
        ... )
        >>> print(f"Lead spawned: {agent.agent_id}")
    """
    # Validate limits using helper functions
    depth_level = int(os.environ.get("DEPTH_LEVEL", "0"))
    _check_depth_limit(depth_level)
    _check_agent_limits()

    # Generate identifiers and paths
    agent_id = str(uuid.uuid4())
    output_dir = "/tmp/claude-agents"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{agent_id}.json")

    # Load worker profiles into agents_json
    agents_json = _load_worker_profiles(workers) if workers else None

    # Build command using helper
    system_prompt_path = Path(__file__).parent / "agent_system_prompt.md"
    cmd = _build_lead_command(
        task=task,
        agent_id=agent_id,
        model=model,
        agents_json=agents_json,
        system_prompt_path=system_prompt_path if system_prompt_path.exists() else None,
        context=context or None,
    )

    # Build environment using helper
    env = _build_spawn_environment(depth_level, agent_id, pattern)

    # Spawn process
    # NOTE: Don't use `with` - file must stay open while agent runs
    # The OS will close the file handle when the subprocess exits
    output_fh = open(output_file, "w")
    proc = subprocess.Popen(
        cmd,
        stdout=output_fh,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    # Don't close output_fh - agent process owns it now

    # Track and register (pass agent_id for completion tracking)
    _agent_counter.increment(pid=proc.pid, agent_id=agent_id)
    swarm_id = os.environ.get("SWARM_ID", env["SESSION_ID"])
    register_agent_in_db(
        agent_id=agent_id,
        session_id=env["SESSION_ID"],
        pid=proc.pid,
        parent=env["PARENT_AGENT_ID"],
        pattern=pattern,
        premise="lead",
        depth_level=depth_level + 1,
        swarm_id=swarm_id,
    )

    return SpawnedAgent(
        pid=proc.pid,
        agent_id=agent_id,
        output_file=output_file,
        depth_level=depth_level + 1,
        pattern=pattern,
        premise="lead",
    )
