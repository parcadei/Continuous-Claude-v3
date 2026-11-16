"""TrackedAgent wrapper for observability.

Wraps an agentica agent to automatically track:
- Agent registration at spawn time
- Task completion with duration and output
- Agent completion/failure status

Auto-wires memory functions (remember, recall, search_memory, store_fact)
into agent scope by default via create_unified_scope().
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TypeVar
from uuid import uuid4

try:
    from agentica import spawn
except ImportError:
    async def spawn(**kwargs):
        raise NotImplementedError("agentica not installed")

from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.unified_scope import create_unified_scope

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class TrackedAgent:
    """Wrapper around agentica agent with tracking."""

    _agent: Any
    _agent_id: str
    _db: CoordinationDB | None
    _pattern: Optional[str] = None
    _closed: bool = field(default=False, init=False)

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def call(self, return_type: type[T], prompt: str, **kwargs) -> T:
        """Call the underlying agent with tracking."""
        start_time = time.perf_counter()

        try:
            result = await self._agent.call(return_type, prompt, **kwargs)

            if self._db:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                artifacts = {}
                if hasattr(result, "artifacts"):
                    artifacts = result.artifacts

                self._db.record_task(
                    agent_id=self._agent_id,
                    input_text=prompt,
                    output=result,
                    duration_ms=duration_ms,
                    pattern=self._pattern,
                    artifacts=artifacts,
                )

            return result

        except Exception as e:
            if self._db:
                self._db.complete_agent(
                    agent_id=self._agent_id,
                    status="failed",
                    error_message=str(e),
                )
            raise

    async def close(self) -> None:
        """Close the agent and mark as completed."""
        if self._closed:
            return

        self._closed = True

        if self._db:
            self._db.complete_agent(agent_id=self._agent_id, status="completed")

        if hasattr(self._agent, "close"):
            await self._agent.close()

    def __getattr__(self, name: str) -> Any:
        """Proxy other attributes to underlying agent."""
        return getattr(self._agent, name)


async def tracked_spawn(
    db: CoordinationDB | None,
    premise: str,
    model: Optional[str] = None,
    scope: Optional[dict[str, Any]] = None,
    mcp: str | None = None,
    pattern: Optional[str] = None,
    parent_agent_id: Optional[str] = None,
    inject_memory: bool = True,
    memory_db_path: Path | None = None,
    **kwargs,
) -> TrackedAgent:
    """Spawn an agent with automatic tracking and memory auto-wiring.

    Drop-in replacement for agentica.spawn() with:
    - Coordination tracking via CoordinationDB
    - Automatic memory function injection (remember, recall, search_memory, store_fact)

    Args:
        db: Optional CoordinationDB for tracking
        premise: Agent premise/instructions
        model: Optional model name
        scope: Optional scope dict (merged with memory scope)
        mcp: Optional MCP configuration
        pattern: Optional pattern name for tracking
        parent_agent_id: Optional parent agent ID
        inject_memory: Whether to auto-inject memory functions (default: True)
        memory_db_path: Optional Path for memory database
        **kwargs: Additional kwargs passed to agentica.spawn()

    Returns:
        TrackedAgent wrapper
    """
    agent_id = uuid4().hex[:8]

    # Auto-wire memory if enabled
    if inject_memory:
        try:
            # Use CLAUDE_SESSION_ID for session isolation, fall back to agent-based ID
            session_id = os.environ.get("CLAUDE_SESSION_ID", f"agent-{agent_id}")

            memory_scope = create_unified_scope(
                session_id=session_id,
                db_path=memory_db_path,
                enable_memory=True,
                enable_tasks=False,  # Tasks handled by coordination DB
            )

            # Protected memory keys that cannot be overridden by user scope
            protected_keys = frozenset({
                "remember", "recall", "search_memory", "store_fact", "_memory_service"
            })

            if scope:
                # Merge: start with memory scope, add user non-protected keys
                merged_scope = dict(memory_scope)
                for key, value in scope.items():
                    if key not in protected_keys:
                        merged_scope[key] = value
                    else:
                        logger.warning(
                            f"User scope attempted to override protected key '{key}' - ignoring"
                        )
                scope = merged_scope
            else:
                scope = memory_scope

        except Exception as e:
            # Don't fail spawn if memory init fails - graceful degradation
            logger.warning(f"Memory auto-wiring failed: {e}")
            if scope is None:
                scope = {}

    if db:
        db.register_agent(
            agent_id=agent_id,
            premise=premise,
            model=model,
            scope_keys=list(scope.keys()) if scope else [],
            pattern=pattern,
            parent_agent_id=parent_agent_id,
        )

    spawn_kwargs = {"premise": premise}
    if model:
        spawn_kwargs["model"] = model
    if scope:
        spawn_kwargs["scope"] = scope
    if mcp:
        spawn_kwargs["mcp"] = mcp
    spawn_kwargs.update(kwargs)

    agent = await spawn(**spawn_kwargs)

    return TrackedAgent(
        _agent=agent,
        _agent_id=agent_id,
        _db=db,
        _pattern=pattern,
    )
