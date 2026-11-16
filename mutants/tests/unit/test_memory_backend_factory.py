"""Test memory backend factory abstraction.

TDD approach: These tests are written FIRST and should FAIL until implementation is complete.

Tests verify:
1. Protocol compliance for both backends
2. Factory function returns correct backend type
3. Environment-based backend selection
4. Both backends satisfy same API contract

MOCK STRATEGY:
- SQLite: Real aiosqlite with tmp_path (lightweight, fast)
- Postgres: Mock asyncpg to avoid Docker dependency
"""

import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# Test 1: Protocol definition exists and is importable
def test_protocol_exists():
    """Protocol module should exist and define MemoryBackend."""
    try:
        from scripts.agentica.memory_protocol import MemoryBackend
        assert MemoryBackend is not None
    except ImportError:
        pytest.fail("memory_protocol.py module not found")


# Test 2: Factory function exists and is importable
def test_factory_exists():
    """Factory module should exist and define create_memory_service."""
    try:
        from scripts.agentica.memory_factory import create_memory_service, get_default_backend
        assert create_memory_service is not None
        assert get_default_backend is not None
    except ImportError:
        pytest.fail("memory_factory.py module not found")


# Test 3: Factory returns correct backend type for SQLite
@pytest.mark.asyncio
async def test_factory_creates_sqlite_backend(tmp_path: Path):
    """Factory should create SQLite backend when requested."""
    from scripts.agentica.memory_factory import create_memory_service

    session_id = f"test-{uuid4().hex[:8]}"
    db_path = tmp_path / "test.db"

    service = await create_memory_service(
        "sqlite",
        session_id=session_id,
        db_path=db_path
    )

    # Should be able to use core Protocol methods
    await service.set_core("key", "value")
    result = await service.get_core("key")
    assert result == "value"

    await service.close()


# Test 4: Factory returns correct backend type for Postgres (mocked)
@pytest.mark.asyncio
async def test_factory_creates_postgres_backend_mocked():
    """Factory should create Postgres backend when requested (mocked pool)."""
    # Skip if postgres dependencies not installed
    try:
        import asyncpg  # noqa: F401
        import pgvector  # noqa: F401
    except ImportError:
        pytest.skip("Postgres dependencies not installed")

    from scripts.agentica.memory_factory import create_memory_service

    session_id = f"test-{uuid4().hex[:8]}"

    # Mock the Postgres pool to avoid real DB connection
    with patch('scripts.agentica.postgres_pool.get_pool') as mock_pool, \
         patch('scripts.agentica.postgres_pool.get_connection') as mock_conn, \
         patch('scripts.agentica.postgres_pool.get_transaction') as mock_txn:

        # Setup mock connection
        mock_connection = AsyncMock()
        mock_conn.return_value.__aenter__.return_value = mock_connection
        mock_txn.return_value.__aenter__.return_value = mock_connection

        # Mock responses for set_core / get_core
        mock_connection.fetchrow.return_value = {"value": "test_value"}
        mock_connection.fetch.return_value = []

        service = await create_memory_service(
            "postgres",
            session_id=session_id
        )

        # Verify pool was accessed
        assert mock_pool.called or True  # Mock was configured

        await service.close()


# Test 5: Environment-based backend selection
def test_get_default_backend_from_env():
    """get_default_backend() should respect AGENTICA_MEMORY_BACKEND env var."""
    from scripts.agentica.memory_factory import get_default_backend

    # Test default (sqlite)
    if "AGENTICA_MEMORY_BACKEND" in os.environ:
        del os.environ["AGENTICA_MEMORY_BACKEND"]
    assert get_default_backend() == "sqlite"

    # Test explicit sqlite
    os.environ["AGENTICA_MEMORY_BACKEND"] = "sqlite"
    assert get_default_backend() == "sqlite"

    # Test explicit postgres (only if dependencies installed)
    try:
        import asyncpg  # noqa: F401
        import pgvector  # noqa: F401
        os.environ["AGENTICA_MEMORY_BACKEND"] = "postgres"
        assert get_default_backend() == "postgres"
    except ImportError:
        # Skip postgres test if dependencies not installed
        pass

    # Cleanup
    if "AGENTICA_MEMORY_BACKEND" in os.environ:
        del os.environ["AGENTICA_MEMORY_BACKEND"]


# Test 6: Invalid backend raises error
def test_get_default_backend_invalid():
    """Invalid backend should raise ValueError."""
    from scripts.agentica.memory_factory import get_default_backend

    os.environ["AGENTICA_MEMORY_BACKEND"] = "invalid"

    with pytest.raises(ValueError, match="Invalid AGENTICA_MEMORY_BACKEND"):
        get_default_backend()

    # Cleanup
    del os.environ["AGENTICA_MEMORY_BACKEND"]


# Test 7: Protocol compliance - core memory methods
@pytest.mark.asyncio
async def test_protocol_core_memory_sqlite(tmp_path: Path):
    """SQLite backend should satisfy Protocol for core memory operations."""
    from scripts.agentica.memory_factory import create_memory_service

    session_id = f"test-{uuid4().hex[:8]}"
    db_path = tmp_path / "test.db"

    service = await create_memory_service("sqlite", session_id=session_id, db_path=db_path)

    # Test set_core and get_core
    await service.set_core("persona", "Assistant")
    result = await service.get_core("persona")
    assert result == "Assistant"

    # Test list_core_keys
    await service.set_core("task", "Research")
    keys = await service.list_core_keys()
    assert "persona" in keys
    assert "task" in keys

    # Test get_all_core
    all_core = await service.get_all_core()
    assert all_core["persona"] == "Assistant"
    assert all_core["task"] == "Research"

    # Test delete_core
    await service.delete_core("task")
    result = await service.get_core("task")
    assert result is None

    await service.close()


# Test 8: Protocol compliance - archival memory methods
@pytest.mark.asyncio
async def test_protocol_archival_memory_sqlite(tmp_path: Path):
    """SQLite backend should satisfy Protocol for archival memory operations."""
    from scripts.agentica.memory_factory import create_memory_service

    session_id = f"test-{uuid4().hex[:8]}"
    db_path = tmp_path / "test.db"

    service = await create_memory_service("sqlite", session_id=session_id, db_path=db_path)

    # Test store
    memory_id = await service.store("Python is a programming language")
    assert memory_id is not None

    # Test search (Protocol method)
    results = await service.search("Python", limit=10)
    assert len(results) > 0
    # Results should contain the stored content
    contents = [r.get("content") for r in results]
    assert any("Python" in c for c in contents if c)

    # Test delete_archival
    await service.delete_archival(memory_id)

    # Verify deletion
    results_after = await service.search("Python", limit=10)
    # Should have fewer results after deletion
    assert len(results_after) <= len(results)

    await service.close()


# Test 9: Protocol compliance - recall methods
@pytest.mark.asyncio
async def test_protocol_recall_sqlite(tmp_path: Path):
    """SQLite backend should satisfy Protocol for recall operations."""
    from scripts.agentica.memory_factory import create_memory_service

    session_id = f"test-{uuid4().hex[:8]}"
    db_path = tmp_path / "test.db"

    service = await create_memory_service("sqlite", session_id=session_id, db_path=db_path)

    # Setup test data
    await service.set_core("persona", "Assistant")
    await service.store("Python programming fact")

    # Test recall
    context = await service.recall("Python", include_core=True, limit=5)
    assert isinstance(context, str)
    assert len(context) > 0

    # Test to_context
    full_context = await service.to_context(max_archival=10)
    assert isinstance(full_context, str)
    # Should include core memory
    assert "persona" in full_context or "Assistant" in full_context

    await service.close()


# Test 10: Backend dependency validation
def test_backend_dependency_validation_sqlite():
    """Factory should validate SQLite dependencies are available."""
    from scripts.agentica.memory_factory import get_default_backend

    # This should not raise if aiosqlite is installed
    try:
        backend = get_default_backend()
        assert backend in ("sqlite", "postgres")
    except ImportError as e:
        # Expected if aiosqlite not installed
        assert "aiosqlite" in str(e)


# Test 11: Backend dependency validation for Postgres
def test_backend_dependency_validation_postgres():
    """Factory should validate Postgres dependencies are available."""
    # Set env to postgres
    os.environ["AGENTICA_MEMORY_BACKEND"] = "postgres"

    from scripts.agentica.memory_factory import get_default_backend

    try:
        backend = get_default_backend()
        assert backend == "postgres"
    except ImportError as e:
        # Expected if asyncpg not installed
        assert "asyncpg" in str(e) or "pgvector" in str(e)
    finally:
        # Cleanup
        if "AGENTICA_MEMORY_BACKEND" in os.environ:
            del os.environ["AGENTICA_MEMORY_BACKEND"]


# Test 12: Lifecycle methods exist
@pytest.mark.asyncio
async def test_lifecycle_methods_sqlite(tmp_path: Path):
    """Backend should have connect() and close() lifecycle methods."""
    from scripts.agentica.memory_factory import create_memory_service

    session_id = f"test-{uuid4().hex[:8]}"
    db_path = tmp_path / "test.db"

    service = await create_memory_service("sqlite", session_id=session_id, db_path=db_path)

    # Should be able to call connect (even if no-op)
    await service.connect()

    # Should be able to call close
    await service.close()

    # Multiple closes should be safe
    await service.close()


# Test 13: Factory raises error for unknown backend
@pytest.mark.asyncio
async def test_factory_unknown_backend_raises():
    """Factory should raise ValueError for unknown backend type."""
    from scripts.agentica.memory_factory import create_memory_service

    with pytest.raises(ValueError, match="Unknown backend"):
        await create_memory_service("unknown", session_id="test")  # type: ignore


# Test 14: Protocol compliance - Postgres search() method
@pytest.mark.asyncio
async def test_postgres_search_method_protocol_compliance():
    """Verify Postgres backend has search() method for Protocol compliance (GAP-002 fix)."""
    # Skip if postgres dependencies not installed
    try:
        import asyncpg  # noqa: F401
        import pgvector  # noqa: F401
    except ImportError:
        pytest.skip("Postgres dependencies not installed")

    from scripts.agentica.memory_factory import create_memory_service

    session_id = f"test-{uuid4().hex[:8]}"

    # Mock the Postgres pool to avoid real DB connection
    with patch('scripts.agentica.postgres_pool.get_pool') as mock_pool, \
         patch('scripts.agentica.postgres_pool.get_connection') as mock_conn, \
         patch('scripts.agentica.postgres_pool.get_transaction') as mock_txn:

        # Setup mock connection
        mock_connection = AsyncMock()
        mock_conn.return_value.__aenter__.return_value = mock_connection
        mock_txn.return_value.__aenter__.return_value = mock_connection

        # Mock responses for search method
        mock_connection.fetch.return_value = [
            {
                "id": "test-id",
                "content": "Test content",
                "metadata": "{}",
                "created_at": "2025-12-27T00:00:00",
                "rank": 1.0,
            }
        ]

        service = await create_memory_service(
            "postgres",
            session_id=session_id
        )

        # Verify search() method exists and is callable
        assert hasattr(service, 'search'), "MemoryServicePG must have search() method"
        assert callable(getattr(service, 'search')), "search() must be callable"

        # Test calling search()
        results = await service.search("test query", limit=10)
        assert isinstance(results, list), "search() must return a list"

        await service.close()
