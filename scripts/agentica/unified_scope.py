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
from pathlib import Path
from typing import Any, Optional

from scripts.agentica.beads_task_graph import BeadsTaskGraph
from scripts.agentica.claude_scope import (
    ClaudeResult,
    SharedContext,
    _call_claude_cli,
)
from scripts.agentica.memory_service import MemoryService

# Re-export SharedContext and _call_claude_cli for unified access
__all__ = ["create_unified_scope", "SharedContext", "_call_claude_cli"]


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
        # There's a running loop - use nest_asyncio pattern or create task
        # For simplicity, create a new loop in a thread-safe way
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()


def _create_file_ops_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
) -> dict[str, Any]:
    """Create file operations that use shared context and this module's _call_claude_cli.

    This ensures tests can patch scripts.agentica.unified_scope._call_claude_cli.
    """

    def read_file(path: str) -> dict[str, Any]:
        """Read a file using Claude CLI with shared cache."""
        # Check shared cache first
        if cache_reads:
            cached = shared.get_cached(path)
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

            if cache_reads:
                shared.set_cached(path, result)

            shared.log_operation({
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
            shared.log_operation({
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
        prompt = f"""Write the following content to the file at: {path}

Content to write:
```
{content}
```

Confirm when the file has been written."""

        try:
            response = _call_claude_cli(prompt, ["Write"])

            # Invalidate shared cache for this file
            shared.invalidate(path)

            shared.log_operation({
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
            shared.log_operation({
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

            # Invalidate shared cache for this file
            shared.invalidate(path)

            shared.log_operation({
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
            shared.log_operation({
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

    def bash(command: str) -> dict[str, Any]:
        """Run a bash command using Claude CLI."""
        prompt = f"""Run this bash command:

```bash
{command}
```

Return the output."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            shared.log_operation({
                "operation": "bash",
                "command": command,
                "success": True,
            })

            return {
                "success": True,
                "command": command,
                "output": response,
            }

        except Exception as e:
            shared.log_operation({
                "operation": "bash",
                "command": command,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "command": command,
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

            shared.log_operation({
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
            shared.log_operation({
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

            # Parse file list from response
            files = [
                line.strip()
                for line in response.split("\n")
                if line.strip() and not line.startswith("#")
            ]

            shared.log_operation({
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
            shared.log_operation({
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

    # Debug utilities access the shared context
    def debug_get_cache() -> dict[str, ClaudeResult]:
        """Get the file cache (for debugging/inspection)."""
        return shared.file_cache.copy()

    def debug_get_operation_log() -> list[dict[str, Any]]:
        """Get the operation log (for debugging/inspection)."""
        return shared.operation_log.copy()

    def debug_clear_cache() -> None:
        """Clear the file cache."""
        shared.file_cache.clear()

    return {
        "read_file": read_file,
        "write_file": write_file,
        "edit_file": edit_file,
        "bash": bash,
        "grep": grep,
        "glob": glob_search,
        # Debug utilities
        "debug_get_cache": debug_get_cache,
        "debug_get_operation_log": debug_get_operation_log,
        "debug_clear_cache": debug_clear_cache,
    }


def _create_file_ops_default(cache_reads: bool = True) -> dict[str, Any]:
    """Create file operations with local cache (no shared context)."""
    file_cache: dict[str, ClaudeResult] = {}
    operation_log: list[dict[str, Any]] = []

    def read_file(path: str) -> dict[str, Any]:
        """Read a file using Claude CLI."""
        # Check cache first
        if cache_reads and path in file_cache:
            cached = file_cache[path]
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

            if cache_reads:
                file_cache[path] = result

            operation_log.append({
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
            operation_log.append({
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
        prompt = f"""Write the following content to the file at: {path}

Content to write:
```
{content}
```

Confirm when the file has been written."""

        try:
            response = _call_claude_cli(prompt, ["Write"])

            # Invalidate cache for this file
            if path in file_cache:
                del file_cache[path]

            operation_log.append({
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
            operation_log.append({
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

            # Invalidate cache for this file
            if path in file_cache:
                del file_cache[path]

            operation_log.append({
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
            operation_log.append({
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

    def bash(command: str) -> dict[str, Any]:
        """Run a bash command using Claude CLI."""
        prompt = f"""Run this bash command:

```bash
{command}
```

Return the output."""

        try:
            response = _call_claude_cli(prompt, ["Bash"])

            operation_log.append({
                "operation": "bash",
                "command": command,
                "success": True,
            })

            return {
                "success": True,
                "command": command,
                "output": response,
            }

        except Exception as e:
            operation_log.append({
                "operation": "bash",
                "command": command,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "command": command,
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

            operation_log.append({
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
            operation_log.append({
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

            # Parse file list from response
            files = [
                line.strip()
                for line in response.split("\n")
                if line.strip() and not line.startswith("#")
            ]

            operation_log.append({
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
            operation_log.append({
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

    # Debug utilities access local cache/log
    def debug_get_cache() -> dict[str, ClaudeResult]:
        """Get the file cache (for debugging/inspection)."""
        return file_cache.copy()

    def debug_get_operation_log() -> list[dict[str, Any]]:
        """Get the operation log (for debugging/inspection)."""
        return operation_log.copy()

    def debug_clear_cache() -> None:
        """Clear the file cache."""
        file_cache.clear()

    return {
        "read_file": read_file,
        "write_file": write_file,
        "edit_file": edit_file,
        "bash": bash,
        "grep": grep,
        "glob": glob_search,
        # Debug utilities
        "debug_get_cache": debug_get_cache,
        "debug_get_operation_log": debug_get_operation_log,
        "debug_clear_cache": debug_clear_cache,
    }


def create_unified_scope(
    session_id: str,
    db_path: Path | None = None,
    enable_memory: bool = True,
    enable_tasks: bool = True,
    shared_context: Optional[SharedContext] = None,
    extra_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create unified scope with file, memory, and task operations.

    Args:
        session_id: Session identifier for memory/task isolation
        db_path: Optional custom database path for memory and tasks
        enable_memory: Whether to include memory functions (default: True)
        enable_tasks: Whether to include task functions (default: True)
        shared_context: Optional SharedContext for multi-agent file cache sharing
        extra_scope: Additional scope items to merge (cannot override built-ins)

    Returns:
        Scope dict with callable functions for file, memory, and task operations
    """
    scope: dict[str, Any] = {}

    # 1. Add file operations (use local _call_claude_cli for testability)
    if shared_context is not None:
        file_ops = _create_file_ops_with_shared(shared_context)
    else:
        file_ops = _create_file_ops_default()

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
