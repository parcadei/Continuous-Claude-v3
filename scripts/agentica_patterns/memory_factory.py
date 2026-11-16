"""Memory backend factory for creating SQLite or PostgreSQL backends.

Provides factory functions for backend instantiation with:
- Explicit backend selection
- Environment-based configuration
- Dependency validation
"""

import os
from typing import Any, Literal

from .memory_protocol import MemoryBackend

BackendType = Literal["sqlite", "postgres"]


async def create_memory_service(
    backend: BackendType = "sqlite",
    session_id: str = "default",
    agent_id: str | None = None,
    **kwargs: Any,
) -> MemoryBackend:
    """Create a memory service with the specified backend.

    Args:
        backend: "sqlite" or "postgres"
        session_id: Session identifier for isolation
        agent_id: Optional agent identifier within session
        **kwargs: Backend-specific options
            - db_path: For SQLite (Path)
            - connection_string: For Postgres (str, optional)

    Returns:
        MemoryBackend implementation (satisfies Protocol)

    Raises:
        ValueError: If backend type is unknown
        ImportError: If required backend dependencies not installed

    Examples:
        # SQLite (development)
        memory = await create_memory_service("sqlite", session_id="test-123")

        # PostgreSQL (production)
        memory = await create_memory_service(
            "postgres",
            session_id="prod-abc",
            agent_id="agent-1"
        )
    """
    if backend == "sqlite":
        try:
            from .memory_service import MemoryService
        except ImportError as e:
            raise ImportError(
                "SQLite backend requires: uv pip install aiosqlite\n"
                f"Original error: {e}"
            ) from e

        db_path = kwargs.get("db_path")
        service = MemoryService(session_id=session_id, db_path=db_path)
        await service.connect()
        return service

    elif backend == "postgres":
        try:
            from .memory_service_pg import MemoryServicePG
        except ImportError as e:
            raise ImportError(
                "Postgres backend requires: uv pip install asyncpg pgvector\n"
                f"Original error: {e}"
            ) from e

        service = MemoryServicePG(session_id=session_id, agent_id=agent_id)
        await service.connect()
        return service

    else:
        raise ValueError(f"Unknown backend: {backend}. Must be 'sqlite' or 'postgres'")


def get_default_backend() -> BackendType:
    """Get default backend from environment.

    Reads from AGENTICA_MEMORY_BACKEND environment variable.

    Defaults:
        AGENTICA_MEMORY_BACKEND=sqlite (default, development)
        AGENTICA_MEMORY_BACKEND=postgres (production)

    Returns:
        Backend type

    Raises:
        ValueError: If invalid backend specified
        ImportError: If backend dependencies not available
    """
    backend = os.environ.get("AGENTICA_MEMORY_BACKEND", "sqlite")

    if backend not in ("sqlite", "postgres"):
        raise ValueError(
            f"Invalid AGENTICA_MEMORY_BACKEND: {backend}. "
            "Must be 'sqlite' or 'postgres'"
        )

    # Validate backend dependencies
    if backend == "postgres":
        try:
            import asyncpg  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "postgres backend requires: uv pip install asyncpg pgvector"
            ) from e
    elif backend == "sqlite":
        try:
            import aiosqlite  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "sqlite backend requires: uv pip install aiosqlite"
            ) from e

    return backend  # type: ignore


async def create_default_memory_service(
    session_id: str = "default",
    agent_id: str | None = None,
) -> MemoryBackend:
    """Create memory service using environment config.

    Automatically selects backend based on AGENTICA_MEMORY_BACKEND env var.

    Args:
        session_id: Session identifier for isolation
        agent_id: Optional agent identifier within session

    Returns:
        MemoryBackend implementation

    Raises:
        ValueError: If invalid backend specified in environment
        ImportError: If required backend dependencies not installed

    Example:
        # Set in environment or .env
        AGENTICA_MEMORY_BACKEND=postgres

        # In code
        memory = await create_default_memory_service(session_id="my-session")
    """
    backend = get_default_backend()
    return await create_memory_service(backend, session_id, agent_id)
