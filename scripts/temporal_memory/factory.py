"""Temporal memory backend factory.

Phase 3.4 of PostgreSQL migration - Factory Integration.

Provides factory functions for backend instantiation with:
- Explicit backend selection
- Environment-based configuration
- Lazy imports to avoid unnecessary dependencies

Both SQLite and PostgreSQL backends satisfy the same Protocol interface.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Union

if TYPE_CHECKING:
    from scripts.backfill.temporal_writer import TemporalWriter
    from scripts.backfill.temporal_writer_pg import TemporalWriterPG
    from scripts.temporal_memory.store import TemporalMemoryStore
    from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

TemporalBackendType = Literal["sqlite", "postgres"]


async def create_temporal_writer(
    backend: TemporalBackendType = "sqlite",
    db_path: Path | None = None,
) -> Union["TemporalWriter", "TemporalWriterPG"]:
    """Create temporal writer with specified backend.

    Args:
        backend: "sqlite" or "postgres"
        db_path: Path to SQLite database (only for sqlite backend)

    Returns:
        TemporalWriter implementation (satisfies TemporalWriterProtocol)

    Raises:
        ValueError: If backend type is unknown
        ImportError: If required backend dependencies not installed

    Examples:
        # SQLite (development)
        writer = await create_temporal_writer("sqlite", db_path=Path("temporal.db"))

        # PostgreSQL (production)
        writer = await create_temporal_writer("postgres")
    """
    if backend == "sqlite":
        try:
            from scripts.backfill.temporal_writer import TemporalWriter
        except ImportError as e:
            raise ImportError(
                "SQLite backend requires: uv pip install aiosqlite\n"
                f"Original error: {e}"
            ) from e

        writer = TemporalWriter(db_path=db_path)
        await writer.connect()
        return writer

    elif backend == "postgres":
        try:
            from scripts.backfill.temporal_writer_pg import TemporalWriterPG
        except ImportError as e:
            raise ImportError(
                "Postgres backend requires: uv pip install asyncpg\n"
                f"Original error: {e}"
            ) from e

        writer = TemporalWriterPG()
        await writer.connect()
        return writer

    else:
        raise ValueError(
            f"Unknown backend: {backend}. Must be 'sqlite' or 'postgres'"
        )


async def create_temporal_store(
    backend: TemporalBackendType = "sqlite",
    session_id: str = "default",
    db_path: Path | None = None,
) -> Union["TemporalMemoryStore", "TemporalMemoryStorePG"]:
    """Create temporal store with specified backend.

    Args:
        backend: "sqlite" or "postgres"
        session_id: Session identifier for isolation
        db_path: Path to SQLite database (only for sqlite backend)

    Returns:
        TemporalMemoryStore implementation (satisfies TemporalStoreProtocol)

    Raises:
        ValueError: If backend type is unknown
        ImportError: If required backend dependencies not installed

    Examples:
        # SQLite (development)
        store = await create_temporal_store(
            "sqlite",
            session_id="test-123",
            db_path=Path("temporal.db")
        )

        # PostgreSQL (production)
        store = await create_temporal_store(
            "postgres",
            session_id="prod-abc"
        )
    """
    if backend == "sqlite":
        try:
            from scripts.temporal_memory.store import TemporalMemoryStore
        except ImportError as e:
            raise ImportError(
                "SQLite backend requires: uv pip install aiosqlite\n"
                f"Original error: {e}"
            ) from e

        store = TemporalMemoryStore(session_id=session_id, db_path=db_path)
        await store.connect()
        return store

    elif backend == "postgres":
        try:
            from scripts.temporal_memory.store_pg import TemporalMemoryStorePG
        except ImportError as e:
            raise ImportError(
                "Postgres backend requires: uv pip install asyncpg\n"
                f"Original error: {e}"
            ) from e

        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()
        return store

    else:
        raise ValueError(
            f"Unknown backend: {backend}. Must be 'sqlite' or 'postgres'"
        )


def get_temporal_backend() -> TemporalBackendType:
    """Get backend from TEMPORAL_BACKEND env var.

    Reads from TEMPORAL_BACKEND environment variable.

    Defaults:
        TEMPORAL_BACKEND=sqlite (default, development)
        TEMPORAL_BACKEND=postgres (production)

    Returns:
        Backend type ("sqlite" or "postgres")

    Examples:
        # Default (development)
        backend = get_temporal_backend()  # Returns "sqlite"

        # Set in environment
        os.environ["TEMPORAL_BACKEND"] = "postgres"
        backend = get_temporal_backend()  # Returns "postgres"
    """
    backend = os.environ.get("TEMPORAL_BACKEND", "sqlite")

    # Normalize and validate
    backend = backend.lower().strip()
    if backend not in ("sqlite", "postgres"):
        # Fall back to sqlite for invalid values, logging would be nice here
        return "sqlite"

    return backend  # type: ignore


async def create_default_temporal_writer(
    db_path: Path | None = None,
) -> Union["TemporalWriter", "TemporalWriterPG"]:
    """Create temporal writer using environment config.

    Automatically selects backend based on TEMPORAL_BACKEND env var.

    Args:
        db_path: Path to SQLite database (only for sqlite backend)

    Returns:
        TemporalWriter implementation

    Raises:
        ImportError: If required backend dependencies not installed

    Example:
        # Set in environment or .env
        TEMPORAL_BACKEND=postgres

        # In code
        writer = await create_default_temporal_writer()
    """
    backend = get_temporal_backend()
    return await create_temporal_writer(backend, db_path)


async def create_default_temporal_store(
    session_id: str = "default",
    db_path: Path | None = None,
) -> Union["TemporalMemoryStore", "TemporalMemoryStorePG"]:
    """Create temporal store using environment config.

    Automatically selects backend based on TEMPORAL_BACKEND env var.

    Args:
        session_id: Session identifier for isolation
        db_path: Path to SQLite database (only for sqlite backend)

    Returns:
        TemporalMemoryStore implementation

    Raises:
        ImportError: If required backend dependencies not installed

    Example:
        # Set in environment or .env
        TEMPORAL_BACKEND=postgres

        # In code
        store = await create_default_temporal_store(session_id="my-session")
    """
    backend = get_temporal_backend()
    return await create_temporal_store(backend, session_id, db_path)
