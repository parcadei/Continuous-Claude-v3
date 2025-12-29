"""Unified scope combining Claude file ops, memory, and tasks.

Provides a single create_unified_scope() factory that merges:
- File operations from claude_scope: read_file, write_file, edit_file, bash, grep, glob
- Memory operations from memory_service: remember, recall, search_memory, store_fact
- Task operations from beads_task_graph: create_task, complete_task, get_ready_tasks, get_all_tasks

Usage:
    scope = create_unified_scope(session_id="abc123", db_path=Path("/tmp/test.db"))
    agent = await spawn(premise="...", scope=scope)

    # Agent can now use file, memory, AND task operations:
    # scope["read_file"]("path/to/file.py")
    # scope["remember"]("key", "value")
    # scope["create_task"]("Build the API")
"""

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any, Protocol

from scripts.agentica.beads_task_graph import BeadsTaskGraph
from scripts.agentica.claude_scope import (
    ClaudeResult,
    SharedContext,
    _call_claude_cli,
    _canonicalize_path,
)
from scripts.agentica.memory_service import MemoryService

# Re-export SharedContext and _call_claude_cli for unified access
__all__ = [
    "create_unified_scope",
    "SharedContext",
    "_call_claude_cli",
    "CacheManager",
    "LocalCacheManager",
    "_create_file_ops",
]


class CacheManager(Protocol):
    """Protocol for cache/log operations in file ops factory.

    This protocol defines the interface that both SharedContext and
    LocalCacheManager implement, enabling a single _create_file_ops()
    factory to work with either caching strategy.

    SharedContext (claude_scope.py) already implements this interface
    via structural typing - no changes needed there.
    """

    def get_cached(self, path: str) -> ClaudeResult | None:
        """Get cached result for path, or None if not cached."""
        ...

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        """Cache result for path."""
        ...

    def invalidate(self, path: str) -> None:
        """Invalidate cache entry for path (if exists)."""
        ...

    def log_operation(self, operation: dict[str, Any]) -> None:
        """Log an operation."""
        ...

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        """Get copy of all cached results."""
        ...

    def get_all_operations(self) -> list[dict[str, Any]]:
        """Get copy of all logged operations."""
        ...

    def clear_cache(self) -> None:
        """Clear all cached results."""
        ...


class LocalCacheManager:
    """Cache manager with local dict storage for single-agent use.

    Not thread-safe - intentionally designed for single-agent contexts
    where SharedContext's locking overhead is unnecessary.
    """

    def __init__(self, cache_reads: bool = True):
        """Initialize local cache manager.

        Args:
            cache_reads: Whether to cache read operations
        """
        self._cache_reads = cache_reads
        self._cache: dict[str, ClaudeResult] = {}
        self._operations: list[dict[str, Any]] = []

    def get_cached(self, path: str) -> ClaudeResult | None:
        """Get cached result for path."""
        if not self._cache_reads:
            return None
        return self._cache.get(path)

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        """Cache result for path."""
        if self._cache_reads:
            self._cache[path] = result

    def invalidate(self, path: str) -> None:
        """Invalidate cache entry for path."""
        self._cache.pop(path, None)

    def log_operation(self, operation: dict[str, Any]) -> None:
        """Log an operation."""
        self._operations.append(operation)

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        """Get copy of all cached results."""
        return dict(self._cache)

    def get_all_operations(self) -> list[dict[str, Any]]:
        """Get copy of all logged operations."""
        return list(self._operations)

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()


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


def _create_file_ops(
    cache_manager: CacheManager,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with pluggable cache manager.

    This is the unified implementation that handles all caching strategies.
    The cache_manager parameter determines whether caching uses shared
    context (inter-agent, thread-safe) or local dict (single agent).

    Args:
        cache_manager: CacheManager implementation (SharedContext or LocalCacheManager)
        project_dir: Optional project directory for path validation

    Returns:
        Dict of file operation functions
    """

    def read_file(path: str) -> dict[str, Any]:
        """Read a file using Claude CLI."""
        try:
            path = _canonicalize_path(path, project_dir)
        except ValueError as e:
            return {
                "success": False,
                "path": path,
                "content": None,
                "error": str(e),
            }

        cached = cache_manager.get_cached(path)
        if cached:
            return {
                "success": cached.success,
                "path": cached.path,
                "content": cached.content,
                "cached": True,
            }

        prompt = f"""Read the file at: {path}

Return the file content. If the file doesn't exist, explain the error."""

        try:
            response = _call_claude_cli(prompt, ["Read"])

            result = ClaudeResult(
                success=True,
                operation="read",
                path=path,
                content=response,
                raw_response=response,
            )

            cache_manager.set_cached(path, result)
            cache_manager.log_operation({
                "operation": "read",
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "path": path,
                "content": response,
                "cached": False,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "read",
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "path": path,
                "content": None,
                "error": str(e),
            }

    def write_file(path: str, content: str) -> dict[str, Any]:
        """Write content to a file using Claude CLI."""
        try:
            path = _canonicalize_path(path, project_dir)
        except ValueError as e:
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }

        prompt = f"""Write the following content to the file at: {path}

Content to write:
```
{content}
```

Confirm when the file has been written."""

        try:
            response = _call_claude_cli(prompt, ["Write"])

            cache_manager.invalidate(path)
            cache_manager.log_operation({
                "operation": "write",
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "path": path,
                "response": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "write",
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }

    def edit_file(path: str, old_text: str, new_text: str) -> dict[str, Any]:
        """Edit a file by replacing text using Claude CLI."""
        try:
            path = _canonicalize_path(path, project_dir)
        except ValueError as e:
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }

        prompt = f"""Edit the file at: {path}

Find this text:
```
{old_text}
```

Replace it with:
```
{new_text}
```

Confirm when the edit is complete."""

        try:
            response = _call_claude_cli(prompt, ["Read", "Edit"])

            cache_manager.invalidate(path)
            cache_manager.log_operation({
                "operation": "edit",
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "path": path,
                "response": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "edit",
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "path": path,
                "error": str(e),
            }

    def bash(command: str, args: list[str] | None = None) -> dict[str, Any]:
        """Run a bash command using Claude CLI.

        Args:
            command: Command to execute
            args: Optional list of arguments to append (will be shlex.quoted)

        Returns:
            Dict with keys: success, command, output, error

        Security:
            Arguments passed via `args` are escaped using shlex.quote() to
            prevent command injection. Always prefer passing untrusted input
            via `args` rather than interpolating into `command`.
        """
        import shlex

        # Build full command with quoted args
        if args:
            quoted_args = " ".join(shlex.quote(arg) for arg in args)
            full_command = f"{command} {quoted_args}"
        else:
            full_command = command

        prompt = f"""Run this bash command:

```bash
{full_command}
```

Return the output."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            cache_manager.log_operation({
                "operation": "bash",
                "command": full_command,
                "success": True,
            })

            return {
                "success": True,
                "command": full_command,
                "output": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "bash",
                "command": full_command,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "command": full_command,
                "output": None,
                "error": str(e),
            }

    def grep(pattern: str, path: str = ".") -> dict[str, Any]:
        """Search for pattern in files using Claude CLI."""
        prompt = f"""Search for the pattern "{pattern}" in {path}

Use grep or similar to find all occurrences.
Return the matching lines with file paths and line numbers."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            cache_manager.log_operation({
                "operation": "grep",
                "pattern": pattern,
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "pattern": pattern,
                "path": path,
                "matches": response,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "grep",
                "pattern": pattern,
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "pattern": pattern,
                "path": path,
                "matches": None,
                "error": str(e),
            }

    def glob_search(pattern: str) -> dict[str, Any]:
        """Find files matching glob pattern using Claude CLI."""
        prompt = f"""Find all files matching the pattern: {pattern}

List all matching file paths."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            files = [
                line.strip()
                for line in response.split("\n")
                if line.strip() and not line.startswith("#")
            ]

            cache_manager.log_operation({
                "operation": "glob",
                "pattern": pattern,
                "success": True,
                "count": len(files),
            })

            return {
                "success": True,
                "pattern": pattern,
                "files": files,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "glob",
                "pattern": pattern,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "pattern": pattern,
                "files": [],
                "error": str(e),
            }

    def debug_get_cache() -> dict[str, ClaudeResult]:
        """Get the file cache (for debugging/inspection)."""
        return cache_manager.get_all_cached()

    def debug_get_operation_log() -> list[dict[str, Any]]:
        """Get the operation log (for debugging/inspection)."""
        return cache_manager.get_all_operations()

    def debug_clear_cache() -> None:
        """Clear the file cache."""
        cache_manager.clear_cache()

    return {
        "read_file": read_file,
        "write_file": write_file,
        "edit_file": edit_file,
        "bash": bash,
        "grep": grep,
        "glob": glob_search,
        "debug_get_cache": debug_get_cache,
        "debug_get_operation_log": debug_get_operation_log,
        "debug_clear_cache": debug_clear_cache,
    }


def _create_file_ops_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with shared context for multi-agent use.

    This is a thin wrapper around _create_file_ops that uses SharedContext
    as the cache manager. SharedContext provides thread-safe caching
    across multiple agents.

    Note: The cache_reads parameter is handled by SharedContext's methods,
    which always cache (SharedContext doesn't have a cache_reads flag).
    If cache_reads=False is needed with SharedContext, a wrapper class
    could be added, but current usage always has cache_reads=True.

    Args:
        shared: SharedContext for thread-safe multi-agent caching
        cache_reads: Whether to cache read operations (default: True)
        project_dir: Optional project directory for path validation

    Returns:
        Dict of file operation functions using shared context
    """
    # SharedContext implements CacheManager protocol via structural typing
    return _create_file_ops(shared, project_dir)


def _create_file_ops_default(
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with local cache for single-agent use.

    This is a thin wrapper around _create_file_ops that uses LocalCacheManager.
    LocalCacheManager is not thread-safe but has lower overhead for
    single-agent contexts.

    Args:
        cache_reads: Whether to cache read operations (default: True)
        project_dir: Optional project directory for path validation

    Returns:
        Dict of file operation functions with local caching
    """
    return _create_file_ops(LocalCacheManager(cache_reads), project_dir)


def create_unified_scope(
    session_id: str,
    db_path: Path | None = None,
    enable_memory: bool = True,
    enable_tasks: bool = True,
    shared_context: SharedContext | None = None,
    extra_scope: dict[str, Any] | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create unified scope with file, memory, and task operations.

    Args:
        session_id: Session identifier for memory/task isolation
        db_path: Optional custom database path for memory and tasks
        enable_memory: Whether to include memory functions (default: True)
        enable_tasks: Whether to include task functions (default: True)
        shared_context: Optional SharedContext for multi-agent file cache sharing
        extra_scope: Additional scope items to merge (cannot override built-ins)
        project_dir: Optional project directory for path validation

    Returns:
        Scope dict with callable functions for file, memory, and task operations
    """
    scope: dict[str, Any] = {}

    # 1. Add file operations (use local _call_claude_cli for testability)
    if shared_context is not None:
        file_ops = _create_file_ops_with_shared(shared_context, project_dir=project_dir)
    else:
        file_ops = _create_file_ops_default(project_dir=project_dir)

    # Add file operations
    scope["read_file"] = file_ops["read_file"]
    scope["write_file"] = file_ops["write_file"]
    scope["edit_file"] = file_ops["edit_file"]
    scope["bash"] = file_ops["bash"]
    scope["grep"] = file_ops["grep"]
    scope["glob"] = file_ops["glob"]

    # Add debug utilities from file ops
    scope["debug_get_cache"] = file_ops["debug_get_cache"]
    scope["debug_get_operation_log"] = file_ops["debug_get_operation_log"]
    scope["debug_clear_cache"] = file_ops["debug_clear_cache"]

    # 2. Add memory operations if enabled
    if enable_memory:
        memory = MemoryService(session_id=session_id, db_path=db_path)
        # Initialize schema synchronously
        _run_async(memory.connect())

        def remember(key: str, value: str) -> None:
            """Store a key-value pair in core memory."""
            _run_async(memory.set_core(key, value))

        def recall(query: str) -> str:
            """Recall information from all memory sources."""
            return _run_async(memory.recall(query))

        def search_memory(query: str, limit: int = 10) -> list[dict[str, Any]]:
            """Search archival memory with FTS5."""
            return _run_async(memory.search(query, limit=limit))

        def store_fact(content: str) -> str:
            """Store a fact in archival memory, returns memory ID."""
            return _run_async(memory.store(content))

        scope["remember"] = remember
        scope["recall"] = recall
        scope["search_memory"] = search_memory
        scope["store_fact"] = store_fact
        scope["_memory_service"] = memory  # For advanced access

    # 3. Add task operations if enabled
    if enable_tasks:
        tasks = BeadsTaskGraph(session_id=session_id, db_path=db_path)

        def create_task(
            description: str,
            blocks: list[str] | None = None,
            **kwargs: Any,
        ) -> str:
            """Create a task with optional blockers."""
            return tasks.add_task(description, blocks=blocks, **kwargs)

        def complete_task(task_id: str) -> None:
            """Mark a task as completed."""
            tasks.complete_task(task_id)

        def get_ready_tasks() -> list[str]:
            """Get task IDs that are ready to execute (no pending blockers)."""
            return tasks.get_ready_tasks()

        def get_all_tasks() -> list[dict[str, Any]]:
            """Get all tasks with their status."""
            return tasks.get_all_tasks()

        scope["create_task"] = create_task
        scope["complete_task"] = complete_task
        scope["get_ready_tasks"] = get_ready_tasks
        scope["get_all_tasks"] = get_all_tasks
        scope["_task_graph"] = tasks  # For advanced access

    # 4. Merge extra_scope (but do NOT override built-ins)
    if extra_scope:
        for key, value in extra_scope.items():
            if key not in scope:
                scope[key] = value
            # Silently ignore attempts to override built-in functions

    return scope
