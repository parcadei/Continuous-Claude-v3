"""Migrate temporal memory from SQLite to PostgreSQL.

Phase 3.5 of Temporal PostgreSQL Migration.

Migrates data from the SQLite-based temporal memory stores (both TemporalWriter
and TemporalMemoryStore implementations) to PostgreSQL. Handles:
- temporal_facts table migration with field mapping
- temporal_traces table (TemporalWriter schema)
- temporal_trace table (TemporalMemoryStore schema)
- Timestamp format conversions (TEXT ISO and REAL Unix to TIMESTAMPTZ)
- Content hash deduplication for idempotent migration
- Session filtering for selective migration

Features:
- Idempotent (ON CONFLICT DO NOTHING) - safe to run multiple times
- Dry-run mode to preview changes
- Batch processing for large datasets
- Progress reporting
- Error handling for malformed data

Usage:
    # Dry run to check stats
    uv run python scripts/migrate_temporal_to_postgres.py \\
        .claude/cache/temporal-memory/temporal.db --dry-run

    # Actual migration
    uv run python scripts/migrate_temporal_to_postgres.py \\
        .claude/cache/temporal-memory/temporal.db

    # Filter by session ID
    uv run python scripts/migrate_temporal_to_postgres.py \\
        .claude/cache/temporal-memory/temporal.db \\
        --session-id abc123

    # Custom batch size
    uv run python scripts/migrate_temporal_to_postgres.py \\
        .claude/cache/temporal-memory/temporal.db \\
        --batch-size 50

Prerequisites:
    - PostgreSQL + pgvector running (docker/start-postgres.sh)
    - AGENTICA_POSTGRES_URL environment variable or default connection
    - Temporal tables created in PostgreSQL (Phase 3.1)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID format.

    Args:
        value: String to check

    Returns:
        True if valid UUID format, False otherwise
    """
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def _convert_timestamp(timestamp: str | float | int) -> datetime:
    """Convert various timestamp formats to datetime with timezone.

    Handles:
    - TEXT ISO format (e.g., "2025-01-15T10:30:00Z")
    - TEXT ISO without Z suffix (e.g., "2025-01-15T10:30:00")
    - TEXT ISO with microseconds (e.g., "2025-01-15T10:30:00.123456Z")
    - REAL Unix timestamp (e.g., 1736940600.0)

    Args:
        timestamp: Timestamp in any supported format

    Returns:
        datetime object with UTC timezone
    """
    if isinstance(timestamp, (int, float)):
        # Unix timestamp (REAL in SQLite)
        return datetime.fromtimestamp(timestamp, tz=UTC)

    # TEXT ISO format
    timestamp_str = str(timestamp)

    # Remove trailing Z if present
    if timestamp_str.endswith("Z"):
        timestamp_str = timestamp_str[:-1]

    # Try parsing with microseconds first, then without
    for fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"]:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue

    # Fallback: try Python's fromisoformat
    try:
        dt = datetime.fromisoformat(timestamp_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        # Last resort: return current time with warning
        return datetime.now(UTC)


async def migrate(
    sqlite_path: Path,
    session_id: str | None = None,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Migrate temporal data from SQLite to PostgreSQL.

    Args:
        sqlite_path: Path to SQLite database file
        session_id: Optional session ID filter (migrate only this session)
        dry_run: If True, don't write to PostgreSQL
        batch_size: Number of records per batch

    Returns:
        Migration statistics dict with keys:
        - facts_read: Number of fact records read from SQLite
        - facts_migrated: Number of fact records written to PostgreSQL
        - facts_skipped: Number of facts skipped (duplicates)
        - traces_read: Number of trace records read from SQLite
        - traces_migrated: Number of trace records written to PostgreSQL
        - errors: List of error messages
    """
    stats: dict[str, Any] = {
        "facts_read": 0,
        "facts_migrated": 0,
        "facts_skipped": 0,
        "traces_read": 0,
        "traces_migrated": 0,
        "errors": [],
    }

    # Verify SQLite file exists
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")

    # Open SQLite connection
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    try:
        # Detect schema type by checking which tables exist
        cursor = sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row["name"] for row in cursor.fetchall()}

        # Migrate facts (both schemas use temporal_facts)
        if "temporal_facts" in tables:
            facts_stats = await _migrate_facts(
                sqlite_conn=sqlite_conn,
                session_id=session_id,
                dry_run=dry_run,
                batch_size=batch_size,
            )
            stats["facts_read"] = facts_stats["read"]
            stats["facts_migrated"] = facts_stats["migrated"]
            stats["facts_skipped"] = facts_stats["skipped"]
            stats["errors"].extend(facts_stats["errors"])

        # Migrate traces from temporal_traces (TemporalWriter schema)
        if "temporal_traces" in tables:
            traces_stats = await _migrate_traces(
                sqlite_conn=sqlite_conn,
                table_name="temporal_traces",
                session_id=session_id,
                dry_run=dry_run,
                batch_size=batch_size,
            )
            stats["traces_read"] += traces_stats["read"]
            stats["traces_migrated"] += traces_stats["migrated"]
            stats["errors"].extend(traces_stats["errors"])

        # Migrate traces from temporal_trace (TemporalMemoryStore schema)
        if "temporal_trace" in tables:
            trace_stats = await _migrate_traces(
                sqlite_conn=sqlite_conn,
                table_name="temporal_trace",
                session_id=session_id,
                dry_run=dry_run,
                batch_size=batch_size,
            )
            stats["traces_read"] += trace_stats["read"]
            stats["traces_migrated"] += trace_stats["migrated"]
            stats["errors"].extend(trace_stats["errors"])

    finally:
        sqlite_conn.close()

    return stats


async def _migrate_facts(
    sqlite_conn: sqlite3.Connection,
    session_id: str | None,
    dry_run: bool,
    batch_size: int,
) -> dict[str, Any]:
    """Migrate temporal_facts table with schema detection.

    Handles both TemporalWriter and TemporalMemoryStore schemas:
    - TemporalWriter: id, session_id, key, value, turn, confidence, content_hash, created_at
    - TemporalMemoryStore: id, session_id, key, value, turn_established, turn_last_changed,
                          change_count, confidence, created_at

    Args:
        sqlite_conn: SQLite connection
        session_id: Optional session filter
        dry_run: If True, don't write
        batch_size: Records per batch

    Returns:
        Dict with 'read', 'migrated', 'skipped', and 'errors' keys
    """
    stats = {"read": 0, "migrated": 0, "skipped": 0, "errors": []}

    # Get column info to detect schema
    cursor = sqlite_conn.execute("PRAGMA table_info(temporal_facts)")
    columns = {row["name"] for row in cursor.fetchall()}

    # Determine which schema we're dealing with
    is_writer_schema = "turn" in columns and "turn_established" not in columns
    is_store_schema = "turn_established" in columns

    # Build query based on schema
    if is_writer_schema:
        base_query = """
            SELECT id, session_id, key, value, turn, confidence, content_hash, created_at
            FROM temporal_facts
        """
    elif is_store_schema:
        base_query = """
            SELECT id, session_id, key, value, turn_established, turn_last_changed,
                   change_count, confidence, created_at
            FROM temporal_facts
        """
    else:
        # Fallback: select common columns
        base_query = """
            SELECT id, session_id, key, value, confidence, created_at
            FROM temporal_facts
        """

    if session_id:
        base_query += " WHERE session_id = ?"
        cursor = sqlite_conn.execute(base_query, (session_id,))
    else:
        cursor = sqlite_conn.execute(base_query)

    # Process in batches
    batch: list[dict[str, Any]] = []
    for row in cursor:
        stats["read"] += 1
        record = dict(row)
        batch.append(record)

        if len(batch) >= batch_size:
            result = await _write_facts_batch(batch, dry_run, is_writer_schema, is_store_schema)
            stats["migrated"] += result["migrated"]
            stats["skipped"] += result["skipped"]
            stats["errors"].extend(result["errors"])
            batch = []

    # Process remaining records
    if batch:
        result = await _write_facts_batch(batch, dry_run, is_writer_schema, is_store_schema)
        stats["migrated"] += result["migrated"]
        stats["skipped"] += result["skipped"]
        stats["errors"].extend(result["errors"])

    return stats


async def _write_facts_batch(
    records: list[dict[str, Any]],
    dry_run: bool,
    is_writer_schema: bool,
    is_store_schema: bool,
) -> dict[str, Any]:
    """Write a batch of temporal_facts to PostgreSQL.

    Uses idempotent insert with content_hash deduplication (ON CONFLICT DO NOTHING).

    Args:
        records: List of fact records
        dry_run: If True, don't write
        is_writer_schema: True if TemporalWriter schema
        is_store_schema: True if TemporalMemoryStore schema

    Returns:
        Dict with 'migrated', 'skipped', and 'errors' keys
    """
    stats = {"migrated": 0, "skipped": 0, "errors": []}

    if dry_run or not records:
        return stats

    from scripts.agentica_patterns.postgres_pool import get_connection

    async with get_connection() as conn:
        for record in records:
            try:
                # Convert timestamp
                created_at = _convert_timestamp(record["created_at"])

                # Get or generate UUID
                original_id = record["id"]
                if _is_valid_uuid(original_id):
                    fact_id = original_id
                else:
                    fact_id = str(uuid4())

                # Map fields based on schema
                if is_writer_schema:
                    turn = record.get("turn")
                    turn_established = None
                    turn_last_changed = None
                    change_count = None
                    content_hash = record.get("content_hash")
                elif is_store_schema:
                    turn = None
                    turn_established = record.get("turn_established")
                    turn_last_changed = record.get("turn_last_changed")
                    change_count = record.get("change_count", 0)
                    content_hash = None
                else:
                    turn = record.get("turn")
                    turn_established = record.get("turn_established")
                    turn_last_changed = record.get("turn_last_changed")
                    change_count = record.get("change_count")
                    content_hash = record.get("content_hash")

                # Check if record already exists (idempotent)
                if content_hash:
                    existing = await conn.fetchrow(
                        "SELECT 1 FROM temporal_facts WHERE content_hash = $1",
                        content_hash,
                    )
                else:
                    existing = await conn.fetchrow(
                        "SELECT 1 FROM temporal_facts WHERE session_id = $1 AND key = $2",
                        record["session_id"],
                        record["key"],
                    )

                if existing:
                    stats["skipped"] += 1
                    continue

                # Insert into PostgreSQL
                await conn.execute(
                    """
                    INSERT INTO temporal_facts
                        (id, session_id, key, value, turn, turn_established, turn_last_changed,
                         change_count, confidence, content_hash, created_at)
                    VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT DO NOTHING
                    """,
                    fact_id,
                    record["session_id"],
                    record["key"],
                    record["value"],
                    turn,
                    turn_established,
                    turn_last_changed,
                    change_count,
                    record.get("confidence", 1.0),
                    content_hash,
                    created_at,
                )
                stats["migrated"] += 1

            except Exception as e:
                stats["errors"].append(f"Failed to migrate fact {record.get('id')}: {e}")

    return stats


async def _migrate_traces(
    sqlite_conn: sqlite3.Connection,
    table_name: str,
    session_id: str | None,
    dry_run: bool,
    batch_size: int,
) -> dict[str, Any]:
    """Migrate trace table (handles both naming conventions).

    Handles both schemas:
    - temporal_traces (TemporalWriter): id, session_id, turn, fact_count, confidence, created_at
    - temporal_trace (TemporalMemoryStore): id, session_id, turn, facts_json, erotetic_json, created_at

    Args:
        sqlite_conn: SQLite connection
        table_name: Either "temporal_traces" or "temporal_trace"
        session_id: Optional session filter
        dry_run: If True, don't write
        batch_size: Records per batch

    Returns:
        Dict with 'read', 'migrated', and 'errors' keys
    """
    stats = {"read": 0, "migrated": 0, "errors": []}

    # Get column info
    cursor = sqlite_conn.execute(f"PRAGMA table_info({table_name})")
    columns = {row["name"] for row in cursor.fetchall()}

    # Build query
    if "facts_json" in columns:
        # TemporalMemoryStore schema
        base_query = f"""
            SELECT id, session_id, turn, facts_json, erotetic_json, created_at
            FROM {table_name}
        """
    else:
        # TemporalWriter schema
        base_query = f"""
            SELECT id, session_id, turn, fact_count, confidence, created_at
            FROM {table_name}
        """

    if session_id:
        base_query += " WHERE session_id = ?"
        cursor = sqlite_conn.execute(base_query, (session_id,))
    else:
        cursor = sqlite_conn.execute(base_query)

    # Process in batches
    batch: list[dict[str, Any]] = []
    for row in cursor:
        stats["read"] += 1
        record = dict(row)
        batch.append(record)

        if len(batch) >= batch_size:
            result = await _write_traces_batch(batch, dry_run, "facts_json" in columns)
            stats["migrated"] += result["migrated"]
            stats["errors"].extend(result["errors"])
            batch = []

    # Process remaining records
    if batch:
        result = await _write_traces_batch(batch, dry_run, "facts_json" in columns)
        stats["migrated"] += result["migrated"]
        stats["errors"].extend(result["errors"])

    return stats


async def _write_traces_batch(
    records: list[dict[str, Any]],
    dry_run: bool,
    is_store_schema: bool,
) -> dict[str, Any]:
    """Write a batch of traces to PostgreSQL.

    Args:
        records: List of trace records
        dry_run: If True, don't write
        is_store_schema: True if TemporalMemoryStore schema (has facts_json)

    Returns:
        Dict with 'migrated' and 'errors' keys
    """
    stats = {"migrated": 0, "errors": []}

    if dry_run or not records:
        return stats

    from scripts.agentica_patterns.postgres_pool import get_connection

    async with get_connection() as conn:
        for record in records:
            try:
                # Convert timestamp
                created_at = _convert_timestamp(record["created_at"])

                # Get or generate UUID
                original_id = record["id"]
                if _is_valid_uuid(original_id):
                    trace_id = original_id
                else:
                    trace_id = str(uuid4())

                # Check if record already exists
                existing = await conn.fetchrow(
                    """
                    SELECT 1 FROM temporal_traces
                    WHERE session_id = $1 AND turn = $2
                    """,
                    record["session_id"],
                    record["turn"],
                )

                if existing:
                    stats["migrated"] += 0  # Already exists
                    continue

                # Map fields based on schema
                if is_store_schema:
                    facts_json = record.get("facts_json")
                    erotetic_json = record.get("erotetic_json")
                    fact_count = None
                    confidence = 1.0

                    # Parse JSON if present to get fact_count
                    if facts_json:
                        try:
                            facts = json.loads(facts_json)
                            fact_count = len(facts) if isinstance(facts, dict) else 0
                        except json.JSONDecodeError:
                            fact_count = 0
                else:
                    facts_json = None
                    erotetic_json = None
                    fact_count = record.get("fact_count", 0)
                    confidence = record.get("confidence", 1.0)

                # Insert into PostgreSQL (unified temporal_traces table)
                await conn.execute(
                    """
                    INSERT INTO temporal_traces
                        (id, session_id, turn, fact_count, confidence, facts_json, erotetic_json, created_at)
                    VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)
                    ON CONFLICT DO NOTHING
                    """,
                    trace_id,
                    record["session_id"],
                    record["turn"],
                    fact_count,
                    confidence,
                    facts_json,
                    erotetic_json,
                    created_at,
                )
                stats["migrated"] += 1

            except Exception as e:
                stats["errors"].append(f"Failed to migrate trace {record.get('id')}: {e}")

    return stats


def main() -> None:
    """CLI entry point for temporal migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate temporal memory from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "sqlite_path",
        type=Path,
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Optional: migrate only this session",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to PostgreSQL",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records per batch (default: 100)",
    )

    args = parser.parse_args()

    # Validate path
    if not args.sqlite_path.exists():
        print(f"Error: SQLite file not found: {args.sqlite_path}")
        return

    print(f"Migrating from: {args.sqlite_path}")
    if args.session_id:
        print(f"Session filter: {args.session_id}")
    if args.dry_run:
        print("DRY RUN - no changes will be written")
    print()

    # Run migration
    stats = asyncio.run(
        migrate(
            sqlite_path=args.sqlite_path,
            session_id=args.session_id,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
    )

    # Print results
    print("Migration complete:")
    print(f"  Facts:  {stats['facts_read']} read, {stats['facts_migrated']} migrated, "
          f"{stats['facts_skipped']} skipped")
    print(f"  Traces: {stats['traces_read']} read, {stats['traces_migrated']} migrated")

    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats["errors"][:10]:
            print(f"  - {error}")
        if len(stats["errors"]) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")


if __name__ == "__main__":
    main()
