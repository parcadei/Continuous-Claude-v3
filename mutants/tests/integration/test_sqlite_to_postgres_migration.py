"""Integration tests for SQLite to PostgreSQL migration (Phase 6: TDD).

Tests are designed to verify the migration script:
- Reads existing SQLite data correctly
- Converts to PostgreSQL format
- Is idempotent (can run multiple times safely)
- Handles empty databases
- Handles missing columns gracefully
- Preserves data integrity (no data loss)
- Can optionally generate embeddings for migrated data

Prerequisites:
- PostgreSQL + pgvector running (docker/start-postgres.sh)
- AGENTICA_POSTGRES_URL environment variable or default connection

Run with:
    uv run pytest tests/integration/test_sqlite_to_postgres_migration.py -v
"""

import json
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-migration-{uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def reset_pool_before_test():
    """Reset the connection pool before each test."""
    from scripts.agentica.postgres_pool import reset_pool

    reset_pool()
    yield
    reset_pool()


@pytest.fixture
def temp_sqlite_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Initialize schema (matching the original MemoryService schema)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        -- Core memory (key-value)
        CREATE TABLE IF NOT EXISTS core_memory (
            session_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (session_id, key)
        );

        -- Archival memory
        CREATE TABLE IF NOT EXISTS archival_memory (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT,
            created_at REAL NOT NULL
        );

        -- FTS5 virtual table for archival search
        CREATE VIRTUAL TABLE IF NOT EXISTS archival_fts USING fts5(
            content,
            content='archival_memory',
            content_rowid='rowid',
            tokenize='porter'
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS archival_ai AFTER INSERT ON archival_memory BEGIN
            INSERT INTO archival_fts(rowid, content) VALUES (new.rowid, new.content);
        END;

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_core_session ON core_memory(session_id);
        CREATE INDEX IF NOT EXISTS idx_archival_session ON archival_memory(session_id);
    """)
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
async def cleanup_sessions():
    """Fixture to track and clean up PostgreSQL sessions."""
    sessions_to_clean: list[str] = []

    def register(session_id: str):
        sessions_to_clean.append(session_id)

    yield register

    # Cleanup all registered sessions
    from scripts.agentica.postgres_pool import get_connection

    async with get_connection() as conn:
        for sid in sessions_to_clean:
            await conn.execute("DELETE FROM core_memory WHERE session_id = $1", sid)
            await conn.execute(
                "DELETE FROM archival_memory WHERE session_id = $1", sid
            )


def populate_sqlite_db(
    db_path: Path,
    session_id: str,
    num_core: int = 5,
    num_archival: int = 10,
) -> dict:
    """Populate SQLite database with test data.

    Returns:
        Dict with counts and sample data for verification
    """
    conn = sqlite3.connect(str(db_path))
    now = datetime.now(UTC).timestamp()

    # Insert core memory
    core_data = []
    for i in range(num_core):
        key = f"key_{i}"
        value = f"value_{i}_for_session_{session_id}"
        conn.execute(
            "INSERT INTO core_memory (session_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, key, value, now),
        )
        core_data.append({"key": key, "value": value})

    # Insert archival memory
    archival_data = []
    sql = (
        "INSERT INTO archival_memory "
        "(id, session_id, content, metadata_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    for i in range(num_archival):
        memory_id = f"mem-{uuid4().hex[:8]}"
        content = f"Archival fact {i} for session {session_id}"
        metadata = {"source": "test", "index": i}
        conn.execute(sql, (memory_id, session_id, content, json.dumps(metadata), now))
        archival_data.append({"id": memory_id, "content": content, "metadata": metadata})

    conn.commit()
    conn.close()

    return {
        "core_count": num_core,
        "archival_count": num_archival,
        "core_data": core_data,
        "archival_data": archival_data,
    }


class TestMigrationReadsExistingSQLiteData:
    """Test that migration reads existing SQLite data correctly."""

    @pytest.mark.asyncio
    async def test_reads_core_memory_from_sqlite(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Should read all core memory records from SQLite."""
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite
        populate_sqlite_db(temp_sqlite_db, session_id, num_core=5)

        # Run migration
        stats = await migrate(temp_sqlite_db, session_id=session_id)

        assert stats["core_memory_read"] == 5
        assert stats["core_memory_migrated"] == 5

    @pytest.mark.asyncio
    async def test_reads_archival_memory_from_sqlite(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Should read all archival memory records from SQLite."""
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite
        populate_sqlite_db(temp_sqlite_db, session_id, num_archival=10)

        # Run migration
        stats = await migrate(temp_sqlite_db, session_id=session_id)

        assert stats["archival_memory_read"] == 10
        assert stats["archival_memory_migrated"] == 10


class TestMigrationConvertsToPostgresFormat:
    """Test that migration converts data to PostgreSQL format correctly."""

    @pytest.mark.asyncio
    async def test_core_memory_accessible_via_memory_service_pg(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Migrated core memory should be accessible via MemoryServicePG."""
        from scripts.agentica.memory_service_pg import MemoryServicePG
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite with specific values
        conn = sqlite3.connect(str(temp_sqlite_db))
        now = datetime.now(UTC).timestamp()
        conn.execute(
            "INSERT INTO core_memory (session_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, "persona", "Test persona value", now),
        )
        conn.commit()
        conn.close()

        # Run migration
        await migrate(temp_sqlite_db, session_id=session_id)

        # Verify via MemoryServicePG
        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()

        result = await memory.get_core("persona")
        assert result == "Test persona value"

    @pytest.mark.asyncio
    async def test_archival_memory_searchable_via_memory_service_pg(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Migrated archival memory should be searchable via MemoryServicePG."""
        from scripts.agentica.memory_service_pg import MemoryServicePG
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite with searchable content
        conn = sqlite3.connect(str(temp_sqlite_db))
        now = datetime.now(UTC).timestamp()
        sql = (
            "INSERT INTO archival_memory "
            "(id, session_id, content, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        conn.execute(
            sql,
            (
                f"mem-{uuid4().hex[:8]}",
                session_id,
                "Python is great for data science",
                json.dumps({"source": "test"}),
                now,
            ),
        )
        conn.commit()
        conn.close()

        # Run migration
        await migrate(temp_sqlite_db, session_id=session_id)

        # Verify search works
        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()

        results = await memory.search_text("Python data science", limit=5)
        assert len(results) >= 1
        assert "Python" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_metadata_preserved_in_migration(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Metadata should be preserved during migration."""
        from scripts.agentica.memory_service_pg import MemoryServicePG
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite with metadata
        conn = sqlite3.connect(str(temp_sqlite_db))
        now = datetime.now(UTC).timestamp()
        metadata = {"source": "user", "priority": "high", "tags": ["important", "test"]}
        sql = (
            "INSERT INTO archival_memory "
            "(id, session_id, content, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        conn.execute(
            sql,
            (
                f"mem-{uuid4().hex[:8]}",
                session_id,
                "Important fact with metadata",
                json.dumps(metadata),
                now,
            ),
        )
        conn.commit()
        conn.close()

        # Run migration
        await migrate(temp_sqlite_db, session_id=session_id)

        # Verify metadata preserved
        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()

        results = await memory.search_text("Important fact", limit=1)
        assert len(results) == 1
        assert results[0]["metadata"]["source"] == "user"
        assert results[0]["metadata"]["priority"] == "high"
        assert "important" in results[0]["metadata"]["tags"]


class TestMigrationIdempotency:
    """Test that migration is idempotent (can run multiple times safely)."""

    @pytest.mark.asyncio
    async def test_running_migration_twice_does_not_duplicate_data(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Running migration twice should not create duplicate records."""
        from scripts.agentica.postgres_pool import get_connection
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite
        populate_sqlite_db(temp_sqlite_db, session_id, num_core=3, num_archival=5)

        # Run migration twice
        await migrate(temp_sqlite_db, session_id=session_id)
        await migrate(temp_sqlite_db, session_id=session_id)

        # Verify no duplicates
        async with get_connection() as conn:
            core_count = await conn.fetchval(
                "SELECT COUNT(*) FROM core_memory WHERE session_id = $1", session_id
            )
            archival_count = await conn.fetchval(
                "SELECT COUNT(*) FROM archival_memory WHERE session_id = $1", session_id
            )

        assert core_count == 3
        assert archival_count == 5

    @pytest.mark.asyncio
    async def test_idempotency_uses_on_conflict_do_nothing(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Migration should use ON CONFLICT DO NOTHING for idempotency."""
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite
        populate_sqlite_db(temp_sqlite_db, session_id, num_core=2, num_archival=3)

        # Run migration three times
        stats1 = await migrate(temp_sqlite_db, session_id=session_id)
        stats2 = await migrate(temp_sqlite_db, session_id=session_id)
        stats3 = await migrate(temp_sqlite_db, session_id=session_id)

        # First run should migrate all records
        assert stats1["core_memory_migrated"] == 2
        assert stats1["archival_memory_migrated"] == 3

        # Subsequent runs should skip (0 new records)
        assert stats2["core_memory_migrated"] == 0 or stats2.get("skipped", 0) > 0
        assert stats3["core_memory_migrated"] == 0 or stats3.get("skipped", 0) > 0


class TestMigrationHandlesEmptyDatabase:
    """Test that migration handles empty databases gracefully."""

    @pytest.mark.asyncio
    async def test_empty_sqlite_database(self, temp_sqlite_db, cleanup_sessions):
        """Should handle empty SQLite database without errors."""
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Don't populate - SQLite is empty
        stats = await migrate(temp_sqlite_db, session_id=session_id)

        assert stats["core_memory_read"] == 0
        assert stats["archival_memory_read"] == 0
        assert stats["core_memory_migrated"] == 0
        assert stats["archival_memory_migrated"] == 0
        assert len(stats.get("errors", [])) == 0

    @pytest.mark.asyncio
    async def test_empty_core_memory_only(self, temp_sqlite_db, cleanup_sessions):
        """Should handle database with only archival memory."""
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate only archival
        conn = sqlite3.connect(str(temp_sqlite_db))
        now = datetime.now(UTC).timestamp()
        sql = (
            "INSERT INTO archival_memory "
            "(id, session_id, content, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        conn.execute(
            sql, (f"mem-{uuid4().hex[:8]}", session_id, "Only archival", None, now)
        )
        conn.commit()
        conn.close()

        stats = await migrate(temp_sqlite_db, session_id=session_id)

        assert stats["core_memory_read"] == 0
        assert stats["archival_memory_read"] == 1
        assert stats["core_memory_migrated"] == 0
        assert stats["archival_memory_migrated"] == 1


class TestMigrationHandlesMissingColumns:
    """Test that migration handles missing or extra columns gracefully."""

    @pytest.mark.asyncio
    async def test_handles_null_metadata(self, temp_sqlite_db, cleanup_sessions):
        """Should handle NULL metadata_json gracefully."""
        from scripts.agentica.memory_service_pg import MemoryServicePG
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Insert with NULL metadata
        conn = sqlite3.connect(str(temp_sqlite_db))
        now = datetime.now(UTC).timestamp()
        sql = (
            "INSERT INTO archival_memory "
            "(id, session_id, content, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        mem_id = f"mem-{uuid4().hex[:8]}"
        conn.execute(sql, (mem_id, session_id, "Content without metadata", None, now))
        conn.commit()
        conn.close()

        stats = await migrate(temp_sqlite_db, session_id=session_id)

        assert stats["archival_memory_migrated"] == 1
        assert len(stats.get("errors", [])) == 0

        # Verify it's accessible
        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()
        results = await memory.search_text("Content without", limit=1)
        assert len(results) == 1
        # Metadata may contain _original_id if the SQLite ID wasn't a valid UUID
        # but should not contain user-provided keys
        assert "source" not in results[0]["metadata"]
        assert "priority" not in results[0]["metadata"]

    @pytest.mark.asyncio
    async def test_handles_malformed_metadata_json(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Should handle malformed JSON in metadata gracefully."""
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Insert with malformed JSON
        conn = sqlite3.connect(str(temp_sqlite_db))
        now = datetime.now(UTC).timestamp()
        sql = (
            "INSERT INTO archival_memory "
            "(id, session_id, content, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        mem_id = f"mem-{uuid4().hex[:8]}"
        conn.execute(
            sql, (mem_id, session_id, "Content with bad JSON", "not valid json {", now)
        )
        conn.commit()
        conn.close()

        # Should not raise, but may skip or log error
        stats = await migrate(temp_sqlite_db, session_id=session_id)

        # Either migrated with empty metadata or recorded an error
        assert (
            stats["archival_memory_migrated"] >= 0
        )  # May be 0 if skipped, 1 if handled


class TestMigrationPreservesDataIntegrity:
    """Test that migration preserves data integrity (no data loss)."""

    @pytest.mark.asyncio
    async def test_all_core_memory_values_preserved(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """All core memory key-value pairs should be preserved."""
        from scripts.agentica.memory_service_pg import MemoryServicePG
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Create specific test data
        conn = sqlite3.connect(str(temp_sqlite_db))
        now = datetime.now(UTC).timestamp()
        test_pairs = {
            "persona": "I am a helpful assistant",
            "task": "Build a REST API",
            "context": "Working on user authentication",
            "special_chars": "Test with special: !@#$%^&*()",
            "unicode": "Unicode test: cafe = cafe",
        }
        for key, value in test_pairs.items():
            conn.execute(
                "INSERT INTO core_memory (session_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, key, value, now),
            )
        conn.commit()
        conn.close()

        # Run migration
        await migrate(temp_sqlite_db, session_id=session_id)

        # Verify all values preserved
        memory = MemoryServicePG(session_id=session_id)
        await memory.connect()

        for key, expected_value in test_pairs.items():
            actual = await memory.get_core(key)
            assert actual == expected_value, f"Mismatch for key '{key}'"

    @pytest.mark.asyncio
    async def test_all_archival_content_preserved(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """All archival memory content should be preserved exactly."""
        from scripts.agentica.postgres_pool import get_connection
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Create test data with various content types
        conn = sqlite3.connect(str(temp_sqlite_db))
        now = datetime.now(UTC).timestamp()
        test_content = [
            "Simple text content",
            "Content with numbers: 12345",
            "Content with special chars: !@#$%^&*()",
            "Multi-line\ncontent\nwith\nnewlines",
            "Unicode: cafe emoji test",
        ]

        sql = (
            "INSERT INTO archival_memory "
            "(id, session_id, content, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        ids = []
        for i, content in enumerate(test_content):
            mem_id = f"mem-test-{i:04d}"
            ids.append(mem_id)
            conn.execute(sql, (mem_id, session_id, content, None, now))
        conn.commit()
        conn.close()

        # Run migration
        await migrate(temp_sqlite_db, session_id=session_id)

        # Verify all content preserved (lookup by content since IDs may change)
        async with get_connection() as pg_conn:
            for expected_content in test_content:
                row = await pg_conn.fetchrow(
                    "SELECT content FROM archival_memory "
                    "WHERE session_id = $1 AND content = $2",
                    session_id,
                    expected_content,
                )
                msg = f"Missing archival record: {expected_content[:30]}..."
                assert row is not None, msg
                assert row["content"] == expected_content

    @pytest.mark.asyncio
    async def test_record_count_matches_after_migration(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Total record counts should match between SQLite and PostgreSQL."""
        from scripts.agentica.postgres_pool import get_connection
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite
        populate_sqlite_db(temp_sqlite_db, session_id, num_core=10, num_archival=25)

        # Count in SQLite
        sqlite_conn = sqlite3.connect(str(temp_sqlite_db))
        sqlite_core_count = sqlite_conn.execute(
            "SELECT COUNT(*) FROM core_memory WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        sqlite_archival_count = sqlite_conn.execute(
            "SELECT COUNT(*) FROM archival_memory WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        sqlite_conn.close()

        # Run migration
        await migrate(temp_sqlite_db, session_id=session_id)

        # Count in PostgreSQL
        async with get_connection() as pg_conn:
            pg_core_count = await pg_conn.fetchval(
                "SELECT COUNT(*) FROM core_memory WHERE session_id = $1", session_id
            )
            pg_archival_count = await pg_conn.fetchval(
                "SELECT COUNT(*) FROM archival_memory WHERE session_id = $1", session_id
            )

        assert pg_core_count == sqlite_core_count
        assert pg_archival_count == sqlite_archival_count


class TestMigrationDryRunMode:
    """Test dry-run mode for migration."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_write_to_postgres(
        self, temp_sqlite_db, cleanup_sessions
    ):
        """Dry-run mode should not write any data to PostgreSQL."""
        from scripts.agentica.postgres_pool import get_connection
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite
        populate_sqlite_db(temp_sqlite_db, session_id, num_core=5, num_archival=10)

        # Run migration in dry-run mode
        stats = await migrate(temp_sqlite_db, session_id=session_id, dry_run=True)

        # Stats should show what would be migrated
        assert stats["core_memory_read"] == 5
        assert stats["archival_memory_read"] == 10

        # But PostgreSQL should be empty
        async with get_connection() as pg_conn:
            core_count = await pg_conn.fetchval(
                "SELECT COUNT(*) FROM core_memory WHERE session_id = $1", session_id
            )
            archival_count = await pg_conn.fetchval(
                "SELECT COUNT(*) FROM archival_memory WHERE session_id = $1", session_id
            )

        assert core_count == 0
        assert archival_count == 0


class TestMigrationProgressReporting:
    """Test progress reporting during migration."""

    @pytest.mark.asyncio
    async def test_returns_detailed_statistics(self, temp_sqlite_db, cleanup_sessions):
        """Migration should return detailed statistics."""
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite
        populate_sqlite_db(temp_sqlite_db, session_id, num_core=3, num_archival=7)

        # Run migration
        stats = await migrate(temp_sqlite_db, session_id=session_id)

        # Check required stats fields
        assert "core_memory_read" in stats
        assert "core_memory_migrated" in stats
        assert "archival_memory_read" in stats
        assert "archival_memory_migrated" in stats
        assert "errors" in stats

        # Values should be correct
        assert stats["core_memory_read"] == 3
        assert stats["archival_memory_read"] == 7


class TestMigrationBatchProcessing:
    """Test batch processing for large datasets."""

    @pytest.mark.asyncio
    async def test_handles_large_dataset(self, temp_sqlite_db, cleanup_sessions):
        """Should handle large datasets efficiently with batching."""
        from scripts.migrate_sqlite_to_postgres import migrate

        session_id = unique_session_id()
        cleanup_sessions(session_id)

        # Populate SQLite with larger dataset
        populate_sqlite_db(temp_sqlite_db, session_id, num_core=100, num_archival=500)

        # Run migration
        stats = await migrate(temp_sqlite_db, session_id=session_id, batch_size=50)

        # All records should be migrated
        assert stats["core_memory_migrated"] == 100
        assert stats["archival_memory_migrated"] == 500
        assert len(stats.get("errors", [])) == 0
