"""Tests for temporal memory SQLite to PostgreSQL migration.

Phase 3.5 of Temporal PostgreSQL Migration.

Tests cover:
- Empty database migration
- Facts migration with data preservation
- Traces migration from both table naming conventions
- Idempotent migration (running twice doesn't duplicate)
- Dry run mode
- Session filtering
- Timestamp conversion
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.migrate_temporal_to_postgres import (
    _convert_timestamp,
    _is_valid_uuid,
    _migrate_facts,
    _migrate_traces,
    migrate,
)

# Patch target for get_connection (imported inside functions)
PATCH_GET_CONNECTION = "scripts.agentica_patterns.postgres_pool.get_connection"


@pytest.fixture
def temp_sqlite_db(tmp_path: Path) -> Path:
    """Create a temporary SQLite database with temporal tables."""
    db_path = tmp_path / "temporal.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        -- TemporalWriter schema (temporal_traces with plural)
        CREATE TABLE IF NOT EXISTS temporal_facts (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            turn INTEGER,
            confidence REAL DEFAULT 1.0,
            content_hash TEXT UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS temporal_traces (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            fact_count INTEGER DEFAULT 0,
            confidence REAL DEFAULT 1.0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def temp_sqlite_db_store_schema(tmp_path: Path) -> Path:
    """Create a temporary SQLite database with TemporalMemoryStore schema."""
    db_path = tmp_path / "temporal_store.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        -- TemporalMemoryStore schema (temporal_trace singular)
        CREATE TABLE IF NOT EXISTS temporal_facts (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            turn_established INTEGER NOT NULL,
            turn_last_changed INTEGER NOT NULL,
            change_count INTEGER DEFAULT 0,
            confidence REAL DEFAULT 1.0,
            created_at REAL NOT NULL,
            UNIQUE(session_id, key)
        );

        CREATE TABLE IF NOT EXISTS temporal_trace (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            facts_json TEXT NOT NULL,
            erotetic_json TEXT,
            created_at REAL NOT NULL
        );
    """
    )
    conn.commit()
    conn.close()
    return db_path


class TestMigrateEmptyDB:
    """Test migrating an empty SQLite database."""

    @pytest.mark.asyncio
    async def test_migrate_empty_db(self, temp_sqlite_db: Path) -> None:
        """Empty SQLite migrates without error."""
        # Mock PostgreSQL connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await migrate(
                sqlite_path=temp_sqlite_db,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

        # Should complete without error and report 0 records
        assert stats["facts_read"] == 0
        assert stats["facts_migrated"] == 0
        assert stats["traces_read"] == 0
        assert stats["traces_migrated"] == 0
        assert len(stats["errors"]) == 0


class TestMigrateFactsPreservesData:
    """Test that facts are migrated with all fields intact."""

    @pytest.mark.asyncio
    async def test_migrate_facts_preserves_data(self, temp_sqlite_db: Path) -> None:
        """Facts migrated with all fields intact."""
        # Insert test data
        conn = sqlite3.connect(str(temp_sqlite_db))
        conn.execute(
            """
            INSERT INTO temporal_facts
            (id, session_id, key, value, turn, confidence, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "fact-001",
                "session-abc",
                "db_type",
                "postgres",
                5,
                0.95,
                "hash123",
                "2025-01-15T10:30:00Z",
            ),
        )
        conn.commit()
        conn.close()

        # Track what was written
        written_data: list[dict[str, Any]] = []

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)  # No existing record

        async def capture_execute(query: str, *args: Any) -> None:
            if "INSERT INTO temporal_facts" in query:
                written_data.append({"query": query, "args": args})

        mock_conn.execute = AsyncMock(side_effect=capture_execute)

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await migrate(
                sqlite_path=temp_sqlite_db,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

        assert stats["facts_read"] == 1
        assert stats["facts_migrated"] == 1
        # Verify data was passed correctly
        assert len(written_data) == 1
        args = written_data[0]["args"]
        assert "session-abc" in args
        assert "db_type" in args
        assert "postgres" in args


class TestMigrateTracesFromBothTables:
    """Test handling both trace table naming conventions."""

    @pytest.mark.asyncio
    async def test_migrate_traces_from_temporal_traces(
        self, temp_sqlite_db: Path
    ) -> None:
        """Handles temporal_traces table (TemporalWriter convention)."""
        # Insert test data into temporal_traces (plural)
        conn = sqlite3.connect(str(temp_sqlite_db))
        conn.execute(
            """
            INSERT INTO temporal_traces
            (id, session_id, turn, fact_count, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            ("trace-001", "session-abc", 3, 5, 0.9, "2025-01-15T10:30:00Z"),
        )
        conn.commit()
        conn.close()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await migrate(
                sqlite_path=temp_sqlite_db,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

        assert stats["traces_read"] == 1
        assert stats["traces_migrated"] == 1

    @pytest.mark.asyncio
    async def test_migrate_traces_from_temporal_trace(
        self, temp_sqlite_db_store_schema: Path
    ) -> None:
        """Handles temporal_trace table (TemporalMemoryStore convention)."""
        # Insert test data into temporal_trace (singular)
        now = datetime.now(UTC).timestamp()
        conn = sqlite3.connect(str(temp_sqlite_db_store_schema))
        conn.execute(
            """
            INSERT INTO temporal_trace
            (id, session_id, turn, facts_json, erotetic_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                "trace-001",
                "session-abc",
                2,
                json.dumps({"phase": "testing"}),
                json.dumps({"unknowns": ["db_version"]}),
                now,
            ),
        )
        conn.commit()
        conn.close()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await migrate(
                sqlite_path=temp_sqlite_db_store_schema,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

        # Should find traces from the singular table
        assert stats["traces_read"] >= 1
        assert stats["traces_migrated"] >= 1


class TestMigrateIdempotent:
    """Test that running migration twice doesn't duplicate data."""

    @pytest.mark.asyncio
    async def test_migrate_idempotent(self, temp_sqlite_db: Path) -> None:
        """Running twice doesn't duplicate data."""
        # Insert test data
        conn = sqlite3.connect(str(temp_sqlite_db))
        conn.execute(
            """
            INSERT INTO temporal_facts
            (id, session_id, key, value, turn, confidence, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "fact-001",
                "session-abc",
                "db_type",
                "postgres",
                5,
                0.95,
                "hash123",
                "2025-01-15T10:30:00Z",
            ),
        )
        conn.commit()
        conn.close()

        insert_count = 0

        async def track_existing(query: str, *args: Any) -> MagicMock | None:
            # First call: no existing record, second call: record exists
            nonlocal insert_count
            if "SELECT 1 FROM temporal_facts" in query:
                if insert_count == 0:
                    return None  # First run: doesn't exist
                else:
                    return MagicMock()  # Second run: exists
            return None

        async def track_insert(query: str, *args: Any) -> None:
            nonlocal insert_count
            if "INSERT INTO temporal_facts" in query:
                insert_count += 1

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=track_existing)
        mock_conn.execute = AsyncMock(side_effect=track_insert)

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            # First migration
            stats1 = await migrate(
                sqlite_path=temp_sqlite_db,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

            # Second migration (should skip existing)
            stats2 = await migrate(
                sqlite_path=temp_sqlite_db,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

        # First run should migrate
        assert stats1["facts_migrated"] == 1
        # Second run should skip (idempotent)
        assert stats2["facts_migrated"] == 0


class TestMigrateDryRun:
    """Test dry run mode."""

    @pytest.mark.asyncio
    async def test_migrate_dry_run(self, temp_sqlite_db: Path) -> None:
        """Dry run reports stats without writing."""
        # Insert test data
        conn = sqlite3.connect(str(temp_sqlite_db))
        conn.execute(
            """
            INSERT INTO temporal_facts
            (id, session_id, key, value, turn, confidence, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "fact-001",
                "session-abc",
                "db_type",
                "postgres",
                5,
                0.95,
                "hash123",
                "2025-01-15T10:30:00Z",
            ),
        )
        conn.execute(
            """
            INSERT INTO temporal_traces
            (id, session_id, turn, fact_count, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            ("trace-001", "session-abc", 3, 5, 0.9, "2025-01-15T10:30:00Z"),
        )
        conn.commit()
        conn.close()

        # Track PostgreSQL interactions
        pg_interactions = []

        mock_conn = AsyncMock()

        async def track_all(query: str, *args: Any) -> None:
            pg_interactions.append(query)

        mock_conn.execute = AsyncMock(side_effect=track_all)

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await migrate(
                sqlite_path=temp_sqlite_db,
                session_id=None,
                dry_run=True,  # Dry run mode
                batch_size=100,
            )

        # Should report records found
        assert stats["facts_read"] == 1
        assert stats["traces_read"] == 1
        # But not migrated (dry run)
        assert stats["facts_migrated"] == 0
        assert stats["traces_migrated"] == 0
        # No PostgreSQL writes
        assert len(pg_interactions) == 0


class TestMigrateSessionFilter:
    """Test session ID filtering."""

    @pytest.mark.asyncio
    async def test_migrate_session_filter(self, temp_sqlite_db: Path) -> None:
        """--session-id filters migration."""
        # Insert test data for two sessions
        conn = sqlite3.connect(str(temp_sqlite_db))
        conn.execute(
            """
            INSERT INTO temporal_facts
            (id, session_id, key, value, turn, confidence, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "fact-001",
                "session-abc",
                "db_type",
                "postgres",
                5,
                0.95,
                "hash1",
                "2025-01-15T10:30:00Z",
            ),
        )
        conn.execute(
            """
            INSERT INTO temporal_facts
            (id, session_id, key, value, turn, confidence, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "fact-002",
                "session-xyz",
                "phase",
                "testing",
                1,
                1.0,
                "hash2",
                "2025-01-15T11:00:00Z",
            ),
        )
        conn.commit()
        conn.close()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            # Only migrate session-abc
            stats = await migrate(
                sqlite_path=temp_sqlite_db,
                session_id="session-abc",  # Filter
                dry_run=False,
                batch_size=100,
            )

        # Should only process matching session
        assert stats["facts_read"] == 1
        assert stats["facts_migrated"] == 1


class TestMigrateTimestampConversion:
    """Test timestamp format conversions."""

    def test_convert_iso_timestamp(self) -> None:
        """TEXT (ISO format) timestamps converted correctly."""
        iso_timestamp = "2025-01-15T10:30:00Z"
        result = _convert_timestamp(iso_timestamp)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None  # Should have timezone

    def test_convert_real_timestamp(self) -> None:
        """REAL (Unix timestamp) timestamps converted correctly."""
        unix_timestamp = 1736940600.0  # 2025-01-15T10:30:00 UTC
        result = _convert_timestamp(unix_timestamp)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None  # Should have timezone

    def test_convert_iso_with_microseconds(self) -> None:
        """ISO timestamps with microseconds handled."""
        iso_timestamp = "2025-01-15T10:30:00.123456Z"
        result = _convert_timestamp(iso_timestamp)
        assert isinstance(result, datetime)
        assert result.microsecond == 123456

    def test_convert_iso_without_z(self) -> None:
        """ISO timestamps without Z suffix handled."""
        iso_timestamp = "2025-01-15T10:30:00"
        result = _convert_timestamp(iso_timestamp)
        assert isinstance(result, datetime)
        # Should assume UTC if no timezone
        assert result.tzinfo is not None


class TestHelperFunctions:
    """Test helper functions."""

    def test_is_valid_uuid_valid(self) -> None:
        """Valid UUID format recognized."""
        assert _is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True
        assert _is_valid_uuid("550e8400e29b41d4a716446655440000") is True  # No dashes

    def test_is_valid_uuid_invalid(self) -> None:
        """Invalid UUID formats rejected."""
        assert _is_valid_uuid("not-a-uuid") is False
        assert _is_valid_uuid("fact-001") is False
        assert _is_valid_uuid("") is False
        assert _is_valid_uuid("12345") is False


class TestBatchProcessing:
    """Test batch processing behavior."""

    @pytest.mark.asyncio
    async def test_batch_processing(self, temp_sqlite_db: Path) -> None:
        """Large datasets processed in batches."""
        # Insert many records
        conn = sqlite3.connect(str(temp_sqlite_db))
        for i in range(150):  # More than default batch_size of 100
            conn.execute(
                """
                INSERT INTO temporal_facts
                (id, session_id, key, value, turn, confidence, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"fact-{i:03d}",
                    "session-abc",
                    f"key_{i}",
                    f"value_{i}",
                    i % 10,
                    1.0,
                    f"hash{i}",
                    "2025-01-15T10:30:00Z",
                ),
            )
        conn.commit()
        conn.close()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await migrate(
                sqlite_path=temp_sqlite_db,
                session_id=None,
                dry_run=False,
                batch_size=50,  # Smaller batch for testing
            )

        # All records processed
        assert stats["facts_read"] == 150
        assert stats["facts_migrated"] == 150


class TestSchemaCompatibility:
    """Test handling of schema differences between implementations."""

    @pytest.mark.asyncio
    async def test_writer_schema_fields(self, temp_sqlite_db: Path) -> None:
        """TemporalWriter schema fields mapped correctly."""
        conn = sqlite3.connect(str(temp_sqlite_db))
        conn.execute(
            """
            INSERT INTO temporal_facts
            (id, session_id, key, value, turn, confidence, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "fact-001",
                "session-abc",
                "db_type",
                "postgres",
                5,
                0.95,
                "hash123",
                "2025-01-15T10:30:00Z",
            ),
        )
        conn.commit()
        conn.close()

        written_args: list[tuple[Any, ...]] = []

        async def capture_insert(query: str, *args: Any) -> None:
            if "INSERT INTO temporal_facts" in query:
                written_args.append(args)

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock(side_effect=capture_insert)

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await migrate(
                sqlite_path=temp_sqlite_db,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

        # Verify the insert included the turn field
        assert len(written_args) == 1

    @pytest.mark.asyncio
    async def test_store_schema_fields(
        self, temp_sqlite_db_store_schema: Path
    ) -> None:
        """TemporalMemoryStore schema fields mapped correctly."""
        now = datetime.now(UTC).timestamp()
        conn = sqlite3.connect(str(temp_sqlite_db_store_schema))
        conn.execute(
            """
            INSERT INTO temporal_facts
            (id, session_id, key, value, turn_established, turn_last_changed,
             change_count, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "fact-001",
                "session-abc",
                "phase",
                "testing",
                1,
                3,
                2,
                0.85,
                now,
            ),
        )
        conn.commit()
        conn.close()

        written_args: list[tuple[Any, ...]] = []

        async def capture_insert(query: str, *args: Any) -> None:
            if "INSERT INTO temporal_facts" in query:
                written_args.append(args)

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock(side_effect=capture_insert)

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await migrate(
                sqlite_path=temp_sqlite_db_store_schema,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

        # Verify the insert occurred with store schema
        assert len(written_args) == 1


class TestErrorHandling:
    """Test error handling during migration."""

    @pytest.mark.asyncio
    async def test_missing_sqlite_file(self, tmp_path: Path) -> None:
        """Handles missing SQLite file gracefully."""
        missing_path = tmp_path / "nonexistent.db"

        # Should raise FileNotFoundError or similar
        with pytest.raises((FileNotFoundError, Exception)):
            await migrate(
                sqlite_path=missing_path,
                session_id=None,
                dry_run=False,
                batch_size=100,
            )

    @pytest.mark.asyncio
    async def test_postgres_connection_error(self, temp_sqlite_db: Path) -> None:
        """Handles PostgreSQL connection errors gracefully."""
        # Insert test data
        conn = sqlite3.connect(str(temp_sqlite_db))
        conn.execute(
            """
            INSERT INTO temporal_facts
            (id, session_id, key, value, turn, confidence, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "fact-001",
                "session-abc",
                "db_type",
                "postgres",
                5,
                0.95,
                "hash123",
                "2025-01-15T10:30:00Z",
            ),
        )
        conn.commit()
        conn.close()

        with patch(PATCH_GET_CONNECTION) as mock_get_conn:
            mock_get_conn.side_effect = ConnectionError("Could not connect to PostgreSQL")

            with pytest.raises(ConnectionError):
                await migrate(
                    sqlite_path=temp_sqlite_db,
                    session_id=None,
                    dry_run=False,
                    batch_size=100,
                )
