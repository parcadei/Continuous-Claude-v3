"""Tests for temporal memory factory module.

Phase 3.4 of PostgreSQL migration - Factory Integration tests.

Tests:
- Factory creates SQLite writer
- Factory creates PostgreSQL writer
- Factory creates SQLite store
- Factory creates PostgreSQL store
- Environment variable defaults to sqlite
- Environment variable TEMPORAL_BACKEND=postgres selects PG
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from scripts.temporal_memory.protocol import (
        TemporalStoreProtocol,
        TemporalWriterProtocol,
    )


class TestGetTemporalBackend:
    """Tests for get_temporal_backend function."""

    def test_defaults_to_sqlite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without TEMPORAL_BACKEND env var, defaults to sqlite."""
        monkeypatch.delenv("TEMPORAL_BACKEND", raising=False)

        from scripts.temporal_memory.factory import get_temporal_backend

        backend = get_temporal_backend()
        assert backend == "sqlite"

    def test_sqlite_explicit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TEMPORAL_BACKEND=sqlite returns sqlite."""
        monkeypatch.setenv("TEMPORAL_BACKEND", "sqlite")

        from scripts.temporal_memory.factory import get_temporal_backend

        backend = get_temporal_backend()
        assert backend == "sqlite"

    def test_postgres_selection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TEMPORAL_BACKEND=postgres returns postgres."""
        monkeypatch.setenv("TEMPORAL_BACKEND", "postgres")

        from scripts.temporal_memory.factory import get_temporal_backend

        backend = get_temporal_backend()
        assert backend == "postgres"


class TestCreateTemporalWriter:
    """Tests for create_temporal_writer factory function."""

    @pytest.mark.asyncio
    async def test_create_sqlite_writer(self, tmp_path: Path) -> None:
        """Factory creates SQLite writer."""
        from scripts.temporal_memory.factory import create_temporal_writer

        db_path = tmp_path / "temporal.db"
        writer = await create_temporal_writer(backend="sqlite", db_path=db_path)

        try:
            # Verify it's the SQLite implementation
            from scripts.backfill.temporal_writer import TemporalWriter

            assert isinstance(writer, TemporalWriter)
            assert writer.db_path == db_path
        finally:
            await writer.close()

    @pytest.mark.asyncio
    async def test_create_postgres_writer(self) -> None:
        """Factory creates PostgreSQL writer."""
        # Mock the postgres pool to avoid needing a real database
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(
            "scripts.backfill.temporal_writer_pg.get_connection"
        ) as mock_get_conn, patch(
            "scripts.backfill.temporal_writer_pg.get_transaction"
        ) as mock_get_trans:
            # Setup mock context managers
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_get_trans.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            from scripts.temporal_memory.factory import create_temporal_writer

            writer = await create_temporal_writer(backend="postgres")

            try:
                # Verify it's the PostgreSQL implementation
                from scripts.backfill.temporal_writer_pg import TemporalWriterPG

                assert isinstance(writer, TemporalWriterPG)
            finally:
                await writer.close()

    @pytest.mark.asyncio
    async def test_sqlite_writer_satisfies_protocol(self, tmp_path: Path) -> None:
        """SQLite writer satisfies TemporalWriterProtocol."""
        from scripts.temporal_memory.factory import create_temporal_writer
        from scripts.temporal_memory.protocol import TemporalWriterProtocol

        db_path = tmp_path / "temporal.db"
        writer = await create_temporal_writer(backend="sqlite", db_path=db_path)

        try:
            # Verify the protocol methods exist
            assert hasattr(writer, "connect")
            assert hasattr(writer, "close")
            assert hasattr(writer, "write_facts")
            assert hasattr(writer, "write_traces")
            assert hasattr(writer, "get_facts")
            assert hasattr(writer, "get_traces")

            # All methods should be callable
            assert callable(getattr(writer, "connect"))
            assert callable(getattr(writer, "close"))
            assert callable(getattr(writer, "write_facts"))
            assert callable(getattr(writer, "write_traces"))
            assert callable(getattr(writer, "get_facts"))
            assert callable(getattr(writer, "get_traces"))
        finally:
            await writer.close()


class TestCreateTemporalStore:
    """Tests for create_temporal_store factory function."""

    @pytest.mark.asyncio
    async def test_create_sqlite_store(self, tmp_path: Path) -> None:
        """Factory creates SQLite store."""
        from scripts.temporal_memory.factory import create_temporal_store

        db_path = tmp_path / "temporal.db"
        store = await create_temporal_store(
            backend="sqlite",
            session_id="test-session",
            db_path=db_path,
        )

        # Verify it's the SQLite implementation
        from scripts.temporal_memory.store import TemporalMemoryStore

        assert isinstance(store, TemporalMemoryStore)
        assert store.session_id == "test-session"

    @pytest.mark.asyncio
    async def test_create_postgres_store(self) -> None:
        """Factory creates PostgreSQL store."""
        # Mock the postgres pool to avoid needing a real database
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(
            "scripts.temporal_memory.store_pg.get_connection"
        ) as mock_get_conn, patch(
            "scripts.temporal_memory.store_pg.get_transaction"
        ) as mock_get_trans:
            # Setup mock context managers
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_get_trans.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            from scripts.temporal_memory.factory import create_temporal_store

            store = await create_temporal_store(
                backend="postgres",
                session_id="test-session-pg",
            )

            # Verify it's the PostgreSQL implementation
            from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

            assert isinstance(store, TemporalMemoryStorePG)
            assert store.session_id == "test-session-pg"

    @pytest.mark.asyncio
    async def test_sqlite_store_satisfies_protocol(self, tmp_path: Path) -> None:
        """SQLite store satisfies TemporalStoreProtocol."""
        from scripts.temporal_memory.factory import create_temporal_store
        from scripts.temporal_memory.protocol import TemporalStoreProtocol

        db_path = tmp_path / "temporal.db"
        store = await create_temporal_store(
            backend="sqlite",
            session_id="test-session",
            db_path=db_path,
        )

        # Verify the protocol methods exist
        assert hasattr(store, "connect")
        assert hasattr(store, "record")
        assert hasattr(store, "get_trace")
        assert hasattr(store, "get_current_state")
        assert hasattr(store, "get_invariants")
        assert hasattr(store, "advance_turn")

        # All methods should be callable
        assert callable(getattr(store, "connect"))
        assert callable(getattr(store, "record"))
        assert callable(getattr(store, "get_trace"))
        assert callable(getattr(store, "get_current_state"))
        assert callable(getattr(store, "get_invariants"))
        assert callable(getattr(store, "advance_turn"))


class TestFactoryEnvVarIntegration:
    """Tests for factory behavior with environment variables."""

    @pytest.mark.asyncio
    async def test_env_var_defaults_to_sqlite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without TEMPORAL_BACKEND env var, factory creates SQLite backends."""
        monkeypatch.delenv("TEMPORAL_BACKEND", raising=False)

        from scripts.temporal_memory.factory import (
            create_temporal_writer,
            get_temporal_backend,
        )

        # get_temporal_backend should return sqlite
        backend = get_temporal_backend()
        assert backend == "sqlite"

        # Using that backend should create SQLite writer
        db_path = tmp_path / "temporal.db"
        writer = await create_temporal_writer(backend=backend, db_path=db_path)

        try:
            from scripts.backfill.temporal_writer import TemporalWriter

            assert isinstance(writer, TemporalWriter)
        finally:
            await writer.close()

    @pytest.mark.asyncio
    async def test_env_var_postgres_selection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TEMPORAL_BACKEND=postgres selects PG backend via factory."""
        monkeypatch.setenv("TEMPORAL_BACKEND", "postgres")

        # Mock the postgres pool
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(
            "scripts.backfill.temporal_writer_pg.get_connection"
        ) as mock_get_conn, patch(
            "scripts.backfill.temporal_writer_pg.get_transaction"
        ) as mock_get_trans:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_get_trans.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_trans.return_value.__aexit__ = AsyncMock(return_value=None)

            from scripts.temporal_memory.factory import (
                create_temporal_writer,
                get_temporal_backend,
            )

            # get_temporal_backend should return postgres
            backend = get_temporal_backend()
            assert backend == "postgres"

            # Using that backend should create PG writer
            writer = await create_temporal_writer(backend=backend)

            try:
                from scripts.backfill.temporal_writer_pg import TemporalWriterPG

                assert isinstance(writer, TemporalWriterPG)
            finally:
                await writer.close()


class TestFactoryEdgeCases:
    """Edge case tests for the factory module."""

    @pytest.mark.asyncio
    async def test_invalid_backend_type_writer(self) -> None:
        """Factory raises ValueError for invalid backend type."""
        from scripts.temporal_memory.factory import create_temporal_writer

        with pytest.raises(ValueError, match="Unknown backend"):
            await create_temporal_writer(backend="mysql")  # type: ignore

    @pytest.mark.asyncio
    async def test_invalid_backend_type_store(self) -> None:
        """Factory raises ValueError for invalid backend type."""
        from scripts.temporal_memory.factory import create_temporal_store

        with pytest.raises(ValueError, match="Unknown backend"):
            await create_temporal_store(backend="mongodb", session_id="test")  # type: ignore

    @pytest.mark.asyncio
    async def test_sqlite_writer_default_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """SQLite writer uses default path when db_path is None."""
        # TemporalWriter uses a relative path by default:
        # .claude/cache/temporal-memory/temporal.db
        # This is different from TemporalMemoryStore which checks CLAUDE_PROJECT_DIR
        from scripts.temporal_memory.factory import create_temporal_writer

        writer = await create_temporal_writer(backend="sqlite")

        try:
            from scripts.backfill.temporal_writer import TemporalWriter

            assert isinstance(writer, TemporalWriter)
            # Default path is relative: .claude/cache/temporal-memory/temporal.db
            assert writer.db_path.name == "temporal.db"
            assert "temporal-memory" in str(writer.db_path)
        finally:
            await writer.close()

    @pytest.mark.asyncio
    async def test_sqlite_store_default_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """SQLite store uses default path when db_path is None."""
        # Set project dir to tmp_path to avoid writing to real project
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

        from scripts.temporal_memory.factory import create_temporal_store

        store = await create_temporal_store(
            backend="sqlite",
            session_id="test-session",
        )

        from scripts.temporal_memory.store import TemporalMemoryStore

        assert isinstance(store, TemporalMemoryStore)
        # Default path should be under CLAUDE_PROJECT_DIR
        assert tmp_path in store._db_path.parents or store._db_path.parent == tmp_path
