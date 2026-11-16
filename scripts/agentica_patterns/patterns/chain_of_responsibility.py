"""
Agentica Chain of Responsibility Pattern - Route Request to First Handler.

Pass request through chain until one handles it. Each handler has a can_handle
predicate. The first handler (by priority) where can_handle returns True
processes the request.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

# Import spawn from agentica if available, otherwise use a stub for testing
try:
    from agentica import spawn
except ImportError:
    # Stub for testing - tests will mock this
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - use mocking in tests")

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


@dataclass
class Handler:
    """
    Handler for Chain of Responsibility pattern.

    Attributes:
        premise: The agent premise for this handler
        can_handle: Callable that returns True if this handler can handle the query
        priority: Lower number = higher priority (default 0)
    """
    premise: str
    can_handle: Callable[[str], bool]
    priority: int = 0


class ChainOfResponsibility:
    """
    Chain of Responsibility pattern: Pass request through chain until one handles it.

    Each handler has a can_handle predicate. The first handler (by priority) where
    can_handle returns True processes the request. Good for routing to specialized agents.

    Example:
        chain = ChainOfResponsibility(handlers=[
            Handler(premise="You handle Python questions.", can_handle=lambda q: "python" in q.lower()),
            Handler(premise="You handle JavaScript questions.", can_handle=lambda q: "javascript" in q.lower()),
            Handler(premise="You handle general programming questions.", can_handle=lambda q: True),  # fallback
        ])
        result = await chain.process("How do I use async in Python?")
    """

    def __init__(
        self,
        handlers: list[Handler],
        model: str | None = None,
        scope: dict[str, Any] | None = None,
        return_type: type = str,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize Chain of Responsibility.

        Args:
            handlers: List of Handler objects (will be sorted by priority)
            model: Model to use for handler agents
            scope: Tools available to handler agents
            return_type: Expected return type from handler
            db: Optional coordination database for tracking agents
        """
        # Sort handlers by priority (lower = higher priority)
        self.handlers = sorted(handlers, key=lambda h: h.priority)
        self.model = model
        self.scope = scope or {}
        self.return_type = return_type
        self.db = db

    async def process(self, query: str) -> Any:
        """
        Process a query through the chain of handlers.

        Args:
            query: The query/request to process

        Returns:
            Result from the handler that processed the request

        Raises:
            ValueError: If no handler can handle the query
        """
        # Generate unique chain ID for this execution
        cor_id = f"cor-{uuid4()}"

        # Find first handler that can handle the query
        for handler in self.handlers:
            if handler.can_handle(query):
                # Set environment variables for hook detection
                env_vars = {
                    "PATTERN_TYPE": "chain_of_responsibility",
                    "PATTERN_ID": cor_id,
                    "COR_ID": cor_id,
                    "AGENT_ROLE": "handler",
                    "HANDLER_PRIORITY": str(handler.priority),
                    "CHAIN_LENGTH": str(len(self.handlers))
                }

                # Spawn agent for this handler
                spawn_kwargs = {
                    "premise": handler.premise,
                    "env": env_vars
                }
                if self.model:
                    spawn_kwargs["model"] = self.model
                if self.scope:
                    spawn_kwargs["scope"] = self.scope

                if self.db:
                    from scripts.agentica_patterns.tracked_agent import tracked_spawn
                    agent = await tracked_spawn(
                        db=self.db, pattern="chain_of_responsibility", **spawn_kwargs
                    )
                else:
                    agent = await spawn(**spawn_kwargs)

                # Process the query
                return await agent.call(self.return_type, query)

        # No handler could handle the query
        raise ValueError(f"No handler could process the query: {query}")
