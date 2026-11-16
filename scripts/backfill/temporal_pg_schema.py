"""PostgreSQL schema migration for temporal memory tables.

This module provides idempotent schema application for the unified
temporal memory schema that supports both TemporalWriter (backfill)
and TemporalMemoryStore (session-scoped) implementations.

Usage:
    # As a module (apply to existing connection):
    from scripts.backfill.temporal_pg_schema import apply_schema

    async with get_connection() as conn:
        await apply_schema(conn)

    # As a standalone script:
    python -m scripts.backfill.temporal_pg_schema

Key design decisions:
- Uses IF NOT EXISTS / IF EXISTS for idempotency
- Matches the schema defined in docker/init.sql
- Supports migration of existing databases
"""

import asyncio
import logging
import sys
from pathlib import Path

import asyncpg

# Add project root to path for imports
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)


# DDL for temporal tables (matches docker/init.sql)
TEMPORAL_FACTS_DDL = """
CREATE TABLE IF NOT EXISTS temporal_facts (
    -- Primary key: UUID for PG compatibility
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core fields (both implementations)
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,

    -- Turn tracking (TemporalWriter uses 'turn', Store uses established/changed)
    turn INTEGER,
    turn_established INTEGER,
    turn_last_changed INTEGER,

    -- Change tracking (TemporalMemoryStore only)
    change_count INTEGER DEFAULT 0,

    -- Deduplication (TemporalWriter)
    content_hash TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Vector embedding (1024 native Voyage dimension)
    embedding vector(1024),

    -- Constraints
    CONSTRAINT uq_temporal_facts_hash UNIQUE (content_hash),
    CONSTRAINT uq_temporal_facts_session_key UNIQUE (session_id, key)
        DEFERRABLE INITIALLY DEFERRED
)
"""

TEMPORAL_TRACES_DDL = """
CREATE TABLE IF NOT EXISTS temporal_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    turn INTEGER NOT NULL,

    -- TemporalWriter fields
    fact_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,

    -- TemporalMemoryStore fields
    facts_json JSONB,
    erotetic_json JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

# Index DDL (all use IF NOT EXISTS for idempotency)
TEMPORAL_INDEXES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_temporal_facts_session ON temporal_facts(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_temporal_facts_session_key ON temporal_facts(session_id, key)",
    "CREATE INDEX IF NOT EXISTS idx_temporal_facts_turn ON temporal_facts(session_id, turn)",
    "CREATE INDEX IF NOT EXISTS idx_temporal_facts_turn_established ON temporal_facts(session_id, turn_established)",
    "CREATE INDEX IF NOT EXISTS idx_temporal_facts_hash ON temporal_facts(content_hash) WHERE content_hash IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_temporal_traces_session ON temporal_traces(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_temporal_traces_turn ON temporal_traces(session_id, turn)",
    "CREATE INDEX IF NOT EXISTS idx_temporal_facts_value_fts ON temporal_facts USING gin(to_tsvector('english', value))",
]


async def apply_schema(conn: asyncpg.Connection) -> None:
    """Apply temporal schema to PostgreSQL connection (idempotent).

    Creates the temporal_facts and temporal_traces tables with all
    indexes if they don't already exist. Safe to call multiple times.

    Args:
        conn: An asyncpg Connection object (not from a pool acquire context).

    Raises:
        asyncpg.PostgresError: If DDL execution fails.
    """
    # Ensure pgvector extension is available
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create tables
    await conn.execute(TEMPORAL_FACTS_DDL)
    await conn.execute(TEMPORAL_TRACES_DDL)

    # Create indexes
    for index_ddl in TEMPORAL_INDEXES_DDL:
        await conn.execute(index_ddl)

    logger.info("Temporal schema applied successfully")


async def verify_schema(conn: asyncpg.Connection) -> dict:
    """Verify that temporal schema was applied correctly.

    Returns:
        Dict with verification results:
        - tables: list of temporal tables found
        - indexes: list of temporal indexes found
        - is_valid: bool indicating if schema is complete
    """
    # Check tables
    tables = await conn.fetch(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('temporal_facts', 'temporal_traces')
        """
    )
    table_names = [t["table_name"] for t in tables]

    # Check indexes
    indexes = await conn.fetch(
        """
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename IN ('temporal_facts', 'temporal_traces')
        """
    )
    index_names = [i["indexname"] for i in indexes]

    # Validate completeness
    expected_tables = {"temporal_facts", "temporal_traces"}
    expected_indexes = {
        "idx_temporal_facts_session",
        "idx_temporal_facts_session_key",
        "idx_temporal_facts_turn",
        "idx_temporal_facts_turn_established",
        "idx_temporal_facts_hash",
        "idx_temporal_traces_session",
        "idx_temporal_traces_turn",
        "idx_temporal_facts_value_fts",
    }

    tables_ok = expected_tables.issubset(set(table_names))
    indexes_ok = expected_indexes.issubset(set(index_names))

    return {
        "tables": table_names,
        "indexes": index_names,
        "is_valid": tables_ok and indexes_ok,
    }


async def main() -> int:
    """Apply temporal schema to PostgreSQL database.

    Uses connection settings from environment variables:
    - AGENTICA_POSTGRES_URL: PostgreSQL connection string

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    import os

    # Get connection string
    connection_string = os.environ.get(
        "AGENTICA_POSTGRES_URL",
        "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
    )

    try:
        conn = await asyncpg.connect(connection_string)
        try:
            print(f"Connected to PostgreSQL: {connection_string.split('@')[-1]}")

            # Apply schema
            await apply_schema(conn)
            print("Schema applied successfully.")

            # Verify
            result = await verify_schema(conn)
            print(f"Tables created: {result['tables']}")
            print(f"Indexes created: {len(result['indexes'])} indexes")

            if result["is_valid"]:
                print("Schema verification: PASSED")
                return 0
            else:
                print("Schema verification: FAILED - missing components")
                return 1

        finally:
            await conn.close()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
