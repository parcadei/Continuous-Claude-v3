"""Agent registry - maps agent types to creation functions."""

from typing import Callable, Coroutine, Any

# Registry of agent types and their factory functions
AGENT_TYPES: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {}

# Active agent instances (lazy loaded)
_active_agents: dict[str, Any] = {}


def register_agent(agent_type: str):
    """Decorator to register an agent factory function."""
    def decorator(fn: Callable[[], Coroutine[Any, Any, Any]]):
        AGENT_TYPES[agent_type] = fn
        return fn
    return decorator


async def get_or_create_agent(agent_type: str):
    """Get existing agent or create new one with hydrated state.

    Note: Our agents are wrapped in StatefulAgent which provides
    a .state dict. Agentica agents don't have built-in state.
    """
    if agent_type not in AGENT_TYPES:
        raise ValueError(f"Unknown agent type: {agent_type}")

    if agent_type not in _active_agents:
        # Create new agent (returns StatefulAgent wrapper)
        factory = AGENT_TYPES[agent_type]
        agent = await factory()

        # Hydrate from persisted state
        from .persistence import load_state
        state = load_state(agent_type)
        if state:
            # Merge persisted state into agent
            if hasattr(agent, 'state'):
                if agent.state is None:
                    agent.state = {}
                for key, value in state.items():
                    agent.state[key] = value

        _active_agents[agent_type] = agent

    return _active_agents[agent_type]


async def persist_agent_state(agent_type: str) -> None:
    """Persist current agent state to disk."""
    if agent_type not in _active_agents:
        return

    agent = _active_agents[agent_type]
    if hasattr(agent, 'state') and agent.state:
        from .persistence import save_state, should_flush, flush_state

        save_state(agent_type, agent.state)

        # Check if flush needed
        if should_flush(agent_type):
            flush_state(agent_type)


# Import agent definitions to register them
from . import research_agent  # noqa: F401
