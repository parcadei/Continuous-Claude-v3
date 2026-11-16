"""Tests for Phase 3.1: PostgreSQL Temporal Schema.

These tests verify that the unified temporal schema is created in PostgreSQL.
Tests are written FIRST (TDD) and should FAIL until the schema is implemented.

Prerequisites:
- Docker must be running
- Run: ./docker/start-postgres.sh before tests
- Or: docker compose -f docker/docker-compose.yml up -d

Usage:
    uv run pytest tests/unit/test_temporal_pg_schema.py -v

Expected failures (schema not yet implemented):
- test_schema_creates_temporal_facts_table - table doesn't exist
- test_schema_creates_temporal_traces_table - table doesn't exist
- test_schema_idempotent - migration script doesn't exist
- test_schema_indexes_created - indexes don't exist
- test_pgvector_extension_enabled - may already pass (extension exists)
"""

import subprocess
import time

import pytest


def is_container_running(container_name: str = "agentica-postgres") -> bool:
    """Check if the PostgreSQL container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_container_healthy(container_name: str = "agentica-postgres") -> bool:
    """Check if the PostgreSQL container is healthy."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "healthy"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def ensure_postgres_running():
    """Ensure PostgreSQL container is running before tests.

    This fixture checks if the container is running and healthy.
    If not, it skips the test suite with a helpful message.
    """
    if not is_container_running():
        pytest.skip(
            "PostgreSQL container not running. "
            "Start with: ./docker/start-postgres.sh or "
            "docker compose -f docker/docker-compose.yml up -d"
        )

    # Wait for container to become healthy (max 30 seconds)
    for _ in range(30):
        if is_container_healthy():
            break
        time.sleep(1)
    else:
        pytest.skip("PostgreSQL container not healthy after 30 seconds")

    yield


@pytest.fixture(scope="module")
def connection_string() -> str:
    """PostgreSQL connection string for tests."""
    return "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"


class TestTemporalPGSchema:
    """Test PostgreSQL temporal schema creation (Phase 3.1)."""

    @pytest.mark.asyncio
    async def test_schema_creates_temporal_facts_table(
        self, ensure_postgres_running, connection_string
    ):
        """Verify temporal_facts table exists with all required columns.

        Expected columns from unified schema:
        - id: UUID PRIMARY KEY
        - session_id: TEXT NOT NULL
        - key: TEXT NOT NULL
        - value: TEXT NOT NULL
        - confidence: REAL DEFAULT 1.0
        - turn: INTEGER (TemporalWriter)
        - turn_established: INTEGER (TemporalMemoryStore)
        - turn_last_changed: INTEGER (TemporalMemoryStore)
        - change_count: INTEGER DEFAULT 0
        - content_hash: TEXT (for deduplication)
        - created_at: TIMESTAMPTZ NOT NULL
        - embedding: vector(1024) (pgvector)
        """
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Check table exists
            row = await conn.fetchrow(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'temporal_facts'
                """
            )
            assert row is not None, "temporal_facts table does not exist"

            # Check all required columns exist
            columns = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'temporal_facts'
                ORDER BY ordinal_position
                """
            )
            column_names = [col["column_name"] for col in columns]

            # Core columns (required)
            assert "id" in column_names, "id column missing"
            assert "session_id" in column_names, "session_id column missing"
            assert "key" in column_names, "key column missing"
            assert "value" in column_names, "value column missing"
            assert "confidence" in column_names, "confidence column missing"

            # Turn tracking (both implementations)
            assert "turn" in column_names, "turn column missing"
            assert "turn_established" in column_names, "turn_established column missing"
            assert "turn_last_changed" in column_names, "turn_last_changed column missing"

            # Change tracking
            assert "change_count" in column_names, "change_count column missing"

            # Deduplication
            assert "content_hash" in column_names, "content_hash column missing"

            # Timestamps
            assert "created_at" in column_names, "created_at column missing"

            # Vector embedding
            assert "embedding" in column_names, "embedding column missing"

            # Check specific data types
            column_types = {col["column_name"]: col["data_type"] for col in columns}
            assert column_types["id"] == "uuid", f"id should be uuid, got {column_types['id']}"
            assert column_types["session_id"] == "text", f"session_id should be text, got {column_types['session_id']}"

        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_schema_creates_temporal_traces_table(
        self, ensure_postgres_running, connection_string
    ):
        """Verify temporal_traces table exists with all required columns.

        Expected columns from unified schema:
        - id: UUID PRIMARY KEY
        - session_id: TEXT NOT NULL
        - turn: INTEGER NOT NULL
        - fact_count: INTEGER DEFAULT 0 (TemporalWriter)
        - confidence: REAL DEFAULT 1.0 (TemporalWriter)
        - facts_json: JSONB (TemporalMemoryStore)
        - erotetic_json: JSONB (TemporalMemoryStore)
        - created_at: TIMESTAMPTZ NOT NULL
        """
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Check table exists
            row = await conn.fetchrow(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'temporal_traces'
                """
            )
            assert row is not None, "temporal_traces table does not exist"

            # Check all required columns exist
            columns = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'temporal_traces'
                ORDER BY ordinal_position
                """
            )
            column_names = [col["column_name"] for col in columns]

            # Core columns
            assert "id" in column_names, "id column missing"
            assert "session_id" in column_names, "session_id column missing"
            assert "turn" in column_names, "turn column missing"

            # TemporalWriter fields
            assert "fact_count" in column_names, "fact_count column missing"
            assert "confidence" in column_names, "confidence column missing"

            # TemporalMemoryStore fields
            assert "facts_json" in column_names, "facts_json column missing"
            assert "erotetic_json" in column_names, "erotetic_json column missing"

            # Timestamps
            assert "created_at" in column_names, "created_at column missing"

            # Check specific data types
            column_types = {col["column_name"]: col["data_type"] for col in columns}
            assert column_types["id"] == "uuid", f"id should be uuid, got {column_types['id']}"
            assert column_types["facts_json"] == "jsonb", f"facts_json should be jsonb, got {column_types['facts_json']}"
            assert column_types["erotetic_json"] == "jsonb", f"erotetic_json should be jsonb, got {column_types['erotetic_json']}"

        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_schema_idempotent(self, ensure_postgres_running, connection_string):
        """Running schema migration twice should not error.

        This tests the idempotency of the schema migration script.
        The schema should use CREATE TABLE IF NOT EXISTS and similar patterns.
        """
        import asyncpg

        # Import the schema migration function (doesn't exist yet - will fail)
        try:
            from scripts.backfill.temporal_pg_schema import apply_schema
        except ImportError:
            pytest.fail(
                "scripts/backfill/temporal_pg_schema.py not found. "
                "Create this module with apply_schema() function."
            )

        conn = await asyncpg.connect(connection_string)
        try:
            # Apply schema twice - should not raise any errors
            await apply_schema(conn)
            await apply_schema(conn)  # Second call should be idempotent

            # Verify tables still exist after double application
            facts_row = await conn.fetchrow(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'temporal_facts'
                """
            )
            assert facts_row is not None, "temporal_facts table missing after idempotent apply"

            traces_row = await conn.fetchrow(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'temporal_traces'
                """
            )
            assert traces_row is not None, "temporal_traces table missing after idempotent apply"

        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_schema_indexes_created(self, ensure_postgres_running, connection_string):
        """Verify all performance indexes are created.

        Expected indexes from unified schema:
        - idx_temporal_facts_session
        - idx_temporal_facts_session_key
        - idx_temporal_facts_turn
        - idx_temporal_facts_turn_established
        - idx_temporal_facts_hash (partial index)
        - idx_temporal_traces_session
        - idx_temporal_traces_turn
        - idx_temporal_facts_value_fts (GIN for full-text search)
        """
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Get all indexes for temporal tables
            indexes = await conn.fetch(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename IN ('temporal_facts', 'temporal_traces')
                """
            )
            index_names = [idx["indexname"] for idx in indexes]

            # Check temporal_facts indexes
            assert "idx_temporal_facts_session" in index_names, \
                "idx_temporal_facts_session index missing"
            assert "idx_temporal_facts_session_key" in index_names, \
                "idx_temporal_facts_session_key index missing"
            assert "idx_temporal_facts_turn" in index_names, \
                "idx_temporal_facts_turn index missing"
            assert "idx_temporal_facts_turn_established" in index_names, \
                "idx_temporal_facts_turn_established index missing"
            assert "idx_temporal_facts_hash" in index_names, \
                "idx_temporal_facts_hash index missing"

            # Check temporal_traces indexes
            assert "idx_temporal_traces_session" in index_names, \
                "idx_temporal_traces_session index missing"
            assert "idx_temporal_traces_turn" in index_names, \
                "idx_temporal_traces_turn index missing"

            # Check full-text search index
            assert "idx_temporal_facts_value_fts" in index_names, \
                "idx_temporal_facts_value_fts GIN index missing"

        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_pgvector_extension_enabled(self, ensure_postgres_running, connection_string):
        """Verify pgvector extension is available for vector operations.

        This test may pass even before temporal schema is added,
        as pgvector is typically enabled in init.sql.
        """
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Check pgvector extension exists
            row = await conn.fetchrow(
                "SELECT * FROM pg_extension WHERE extname = 'vector'"
            )
            assert row is not None, "pgvector extension not found"
            assert row["extname"] == "vector"

            # Verify we can use vector operations
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _test_pgvector_check (
                    id SERIAL PRIMARY KEY,
                    embedding vector(4)
                )
                """
            )

            # Insert a test vector
            await conn.execute(
                "INSERT INTO _test_pgvector_check (embedding) VALUES ('[1,2,3,4]')"
            )

            # Query it back
            row = await conn.fetchrow(
                "SELECT embedding FROM _test_pgvector_check ORDER BY id DESC LIMIT 1"
            )
            assert row is not None
            assert row["embedding"] is not None

            # Cleanup test table
            await conn.execute("DROP TABLE _test_pgvector_check")

        finally:
            await conn.close()


class TestTemporalPGConstraints:
    """Test PostgreSQL constraints for temporal tables."""

    @pytest.mark.asyncio
    async def test_unique_constraint_content_hash(
        self, ensure_postgres_running, connection_string
    ):
        """Verify UNIQUE constraint on content_hash for deduplication.

        The temporal_facts table should have:
        CONSTRAINT uq_temporal_facts_hash UNIQUE (content_hash)
        """
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Check constraint exists
            constraints = await conn.fetch(
                """
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints
                WHERE table_name = 'temporal_facts'
                AND constraint_type = 'UNIQUE'
                """
            )
            constraint_names = [c["constraint_name"] for c in constraints]

            assert "uq_temporal_facts_hash" in constraint_names, \
                "uq_temporal_facts_hash unique constraint missing"

        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_no_session_key_unique_constraint(
        self, ensure_postgres_running, connection_string
    ):
        """Verify (session_id, key) does NOT have a unique constraint.

        Originally planned as UNIQUE constraint, but REMOVED in Phase 3.2 because:
        - TemporalWriter needs to store multiple facts with same (session_id, key)
        - Example: Multiple file reads with key="file_read" but different values
        - TemporalMemoryStore uses DELETE + INSERT pattern instead of UPSERT

        See: thoughts/shared/handoffs/temporal-postgres/plan.md Phase 3.2 notes
        """
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Check constraint does NOT exist (intentionally removed)
            constraints = await conn.fetch(
                """
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints
                WHERE table_name = 'temporal_facts'
                AND constraint_type = 'UNIQUE'
                """
            )
            constraint_names = [c["constraint_name"] for c in constraints]

            # This constraint was removed - verify it's NOT present
            assert "uq_temporal_facts_session_key" not in constraint_names, \
                "uq_temporal_facts_session_key should NOT exist (removed in Phase 3.2)"

        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_not_null_constraints(self, ensure_postgres_running, connection_string):
        """Verify NOT NULL constraints on required columns."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            columns = await conn.fetch(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'temporal_facts'
                """
            )
            column_nullable = {col["column_name"]: col["is_nullable"] for col in columns}

            # Required columns must be NOT NULL
            assert column_nullable.get("session_id") == "NO", "session_id should be NOT NULL"
            assert column_nullable.get("key") == "NO", "key should be NOT NULL"
            assert column_nullable.get("value") == "NO", "value should be NOT NULL"
            assert column_nullable.get("created_at") == "NO", "created_at should be NOT NULL"

        finally:
            await conn.close()
