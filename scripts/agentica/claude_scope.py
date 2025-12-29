"""Claude CLI scope functions for Agentica agents.

Provides scope functions that:
1. Call Claude CLI subprocess for file operations
2. Return structured dicts for agent to reference
3. Cache results for scope persistence

Usage:
    scope = create_claude_scope()
    agent = await spawn(premise="...", scope=scope)

    # Agent can now use:
    # content = read_file("path/to/file.py")
    # result = write_file("path/to/file.py", "content")
    # output = bash("ls -la")
"""

import asyncio
import concurrent.futures
import os
import subprocess
import sys
import threading
import warnings
from dataclasses import dataclass, field
from typing import Any

from scripts.agentica.coordination import BroadcastType, CoordinationDB


def _run_async(coro):
    """Run an async coroutine synchronously.

    Handles both cases:
    - When called from sync context: creates new event loop
    - Works with nested event loops in test environments
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        # No running loop - create one and run
        return asyncio.run(coro)
    else:
        # There's a running loop - use thread pool to avoid nested loop issues
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()


def _canonicalize_path(path: str, project_dir: str | None = None) -> str:
    """Canonicalize path and validate it's within allowed scope.

    Args:
        path: User-provided path (may contain ../ or symlinks)
        project_dir: If set, paths must resolve within this directory

    Returns:
        Canonicalized absolute path

    Raises:
        ValueError: If path escapes project_dir bounds
    """
    # Expand ~ and resolve symlinks/..
    resolved = os.path.realpath(os.path.expanduser(path))

    if project_dir:
        allowed = os.path.realpath(os.path.expanduser(project_dir))

        # On macOS (case-insensitive), normalize case for comparison
        if sys.platform == 'darwin':
            resolved_check = resolved.lower()
            allowed_check = allowed.lower()
        else:
            resolved_check = resolved
            allowed_check = allowed

        # Ensure resolved path starts with allowed directory
        if not resolved_check.startswith(allowed_check + os.sep) and resolved_check != allowed_check:
            raise ValueError(
                f"Path '{path}' resolves to '{resolved}' which escapes "
                f"project directory '{allowed}'"
            )

    return resolved


@dataclass
class ClaudeResult:
    """Structured result from Claude CLI operation."""
    success: bool
    operation: str
    path: str | None = None
    content: str | None = None
    output: str | None = None
    error: str | None = None
    raw_response: str | None = None


def _call_claude_cli(
    prompt: str,
    allowed_tools: list[str],
    timeout: int = 300
) -> str:
    """Call Claude CLI and return response.

    Args:
        prompt: The prompt to send
        allowed_tools: List of tools to allow (Read, Write, Edit, Bash)
        timeout: Timeout in seconds

    Returns:
        Claude CLI response text

    Raises:
        RuntimeError: If Claude CLI fails
    """
    cmd = [
        "claude", "-p", prompt,
        "--allowedTools", ",".join(allowed_tools),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

    return result.stdout.strip()


@dataclass
class SharedContext:
    """Shared context for multi-agent coordination.

    Provides:
    - Shared file cache across agents
    - Operation log for coordination
    - Conflict detection for writes

    Thread-safe using threading.Lock for cross-thread protection.
    """
    file_cache: dict[str, ClaudeResult] = field(default_factory=dict)
    operation_log: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get_cached(self, path: str) -> ClaudeResult | None:
        """Get cached file content (thread-safe)."""
        with self._lock:
            return self.file_cache.get(path)

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        """Set cached file content (thread-safe)."""
        with self._lock:
            self.file_cache[path] = result

    def invalidate(self, path: str) -> None:
        """Invalidate cache for a path (thread-safe)."""
        with self._lock:
            if path in self.file_cache:
                del self.file_cache[path]

    def log_operation(self, operation: dict[str, Any]) -> None:
        """Log an operation (thread-safe)."""
        with self._lock:
            self.operation_log.append(operation)

    def get_writes_for_path(self, path: str) -> list[dict[str, Any]]:
        """Get all write operations for a path (conflict detection)."""
        with self._lock:
            return [
                op for op in self.operation_log
                if op.get("path") == path and op.get("operation") in ("write", "edit")
            ]

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        """Get copy of all cached files (thread-safe).

        Returns a shallow copy of the file cache for safe external iteration.
        Used by debug utilities to avoid direct access to internal state.
        """
        with self._lock:
            return self.file_cache.copy()

    def get_all_operations(self) -> list[dict[str, Any]]:
        """Get copy of all operations (thread-safe).

        Returns a shallow copy of the operation log for safe external iteration.
        Used by debug utilities to avoid direct access to internal state.
        """
        with self._lock:
            return self.operation_log.copy()

    def clear_cache(self) -> None:
        """Clear all cached files (thread-safe).

        Used by debug utilities to reset cache state safely.
        """
        with self._lock:
            self.file_cache.clear()


def broadcast_finding(
    finding: str,
    metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Broadcast a finding to other agents in the swarm."""
    swarm_id = os.environ.get("SWARM_ID")
    if not swarm_id:
        return {"success": False, "error": "Not in a swarm (SWARM_ID not set)"}

    agent_id = os.environ.get("AGENT_ID", "unknown")

    db = CoordinationDB()
    broadcast = db.create_broadcast(
        swarm_id=swarm_id,
        sender_agent=agent_id,
        broadcast_type=BroadcastType.FINDING,
        payload={"finding": finding, "metadata": metadata or {}}
    )

    return {"success": True, "broadcast_id": broadcast.id, "message": f"Broadcast sent to swarm {swarm_id}"}


def broadcast_blocker(
    blocker: str,
    severity: str = "medium"
) -> dict[str, Any]:
    """Broadcast a blocker that needs help from other agents."""
    swarm_id = os.environ.get("SWARM_ID")
    if not swarm_id:
        return {"success": False, "error": "Not in a swarm (SWARM_ID not set)"}

    agent_id = os.environ.get("AGENT_ID", "unknown")

    db = CoordinationDB()
    broadcast = db.create_broadcast(
        swarm_id=swarm_id,
        sender_agent=agent_id,
        broadcast_type=BroadcastType.BLOCKER,
        payload={"blocker": blocker, "severity": severity}
    )

    return {"success": True, "broadcast_id": broadcast.id}


def broadcast_done(
    summary: str,
    artifacts: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Broadcast that this agent has completed its work."""
    swarm_id = os.environ.get("SWARM_ID")
    if not swarm_id:
        return {"success": False, "error": "Not in a swarm"}

    agent_id = os.environ.get("AGENT_ID", "unknown")

    db = CoordinationDB()
    broadcast = db.create_broadcast(
        swarm_id=swarm_id,
        sender_agent=agent_id,
        broadcast_type=BroadcastType.DONE,
        payload={"summary": summary, "artifacts": artifacts or {}}
    )

    return {"success": True, "broadcast_id": broadcast.id}


def create_claude_scope(
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create scope with Claude CLI functions.

    Args:
        cache_reads: Whether to cache file reads (default: True)
        project_dir: Optional project directory for relative paths

    Returns:
        Scope dict with callable functions
    """
    # Lazy import to avoid circular dependency
    from scripts.agentica.unified_scope import _create_file_ops, LocalCacheManager

    if project_dir is None:
        warnings.warn(
            "project_dir=None is deprecated and will be required in a future version. "
            "Set project_dir to enable path validation and prevent traversal attacks.",
            DeprecationWarning,
            stacklevel=2
        )

    # Delegate to unified_scope._create_file_ops()
    cache_manager = LocalCacheManager(cache_reads)
    file_ops = _create_file_ops(cache_manager, project_dir)

    # Add broadcast functions for swarm coordination
    return {
        **file_ops,
        "broadcast_finding": broadcast_finding,
        "broadcast_blocker": broadcast_blocker,
        "broadcast_done": broadcast_done,
    }


def create_claude_scope_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create scope with shared context for multi-agent coordination.

    Args:
        shared: SharedContext instance to share across agents
        cache_reads: Whether to cache file reads
        project_dir: Optional project directory for path validation

    Returns:
        Scope dict with callable functions using shared context

    Note:
        Functions are synchronous for backward compatibility.
        SharedContext methods are thread-safe using threading.Lock.
    """
    # Lazy import to avoid circular dependency
    from scripts.agentica.unified_scope import _create_file_ops

    if project_dir is None:
        warnings.warn(
            "project_dir=None is deprecated and will be required in a future version. "
            "Set project_dir to enable path validation and prevent traversal attacks.",
            DeprecationWarning,
            stacklevel=2
        )

    # SharedContext implements CacheManager protocol via structural typing
    # Note: cache_reads is ignored here since SharedContext always caches
    # This matches original behavior (cache_reads only affected LocalCacheManager)
    file_ops = _create_file_ops(shared, project_dir)

    # Add shared context reference
    return {
        **file_ops,
        "shared": shared,
    }
