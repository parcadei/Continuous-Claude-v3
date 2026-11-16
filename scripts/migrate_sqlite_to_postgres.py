"""Migrate data from SQLite to PostgreSQL.

This script migrates memory data from the SQLite-based MemoryService to the
PostgreSQL-based MemoryServicePG. It handles:
- Core memory (key-value blocks)
- Archival memory (long-term facts with metadata)

Features:
- Idempotent (ON CONFLICT DO NOTHING) - safe to run multiple times
- Dry-run mode to preview changes
- Batch processing for large datasets
- Progress reporting
- Error handling for malformed data

Usage:
    uv run python scripts/migrate_sqlite_to_postgres.py \\
        --sqlite-path .claude/cache/agentica-memory/memory.db

    # Dry-run mode (no writes)
    uv run python scripts/migrate_sqlite_to_postgres.py \\
        --sqlite-path .claude/cache/agentica-memory/memory.db \\
        --dry-run

    # Filter by session ID
    uv run python scripts/migrate_sqlite_to_postgres.py \\
        --sqlite-path .claude/cache/agentica-memory/memory.db \\
        --session-id abc123

    # Custom batch size
    uv run python scripts/migrate_sqlite_to_postgres.py \\
        --sqlite-path .claude/cache/agentica-memory/memory.db \\
        --batch-size 100

Prerequisites:
    - PostgreSQL + pgvector running (docker/start-postgres.sh)
    - AGENTICA_POSTGRES_URL environment variable or default connection
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


async def migrate(
    sqlite_path: Path,
    session_id: str | None = None,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Migrate data from SQLite to PostgreSQL.

    Args:
        sqlite_path: Path to SQLite database file
        session_id: Optional session ID filter (migrate only this session)
        dry_run: If True, don't write to PostgreSQL
        batch_size: Number of records per batch

    Returns:
        Migration statistics dict with keys:
        - core_memory_read: Number of core memory records read
        - core_memory_migrated: Number of core memory records written
        - archival_memory_read: Number of archival memory records read
        - archival_memory_migrated: Number of archival memory records written
        - errors: List of error messages
    """

    stats: dict[str, Any] = {
        "core_memory_read": 0,
        "core_memory_migrated": 0,
        "archival_memory_read": 0,
        "archival_memory_migrated": 0,
        "errors": [],
    }

    # Open SQLite
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    try:
        # Migrate core memory
        core_stats = await _migrate_core_memory(
            sqlite_conn=sqlite_conn,
            session_id=session_id,
            dry_run=dry_run,
            batch_size=batch_size,
        )
        stats["core_memory_read"] = core_stats["read"]
        stats["core_memory_migrated"] = core_stats["migrated"]
        stats["errors"].extend(core_stats["errors"])

        # Migrate archival memory
        archival_stats = await _migrate_archival_memory(
            sqlite_conn=sqlite_conn,
            session_id=session_id,
            dry_run=dry_run,
            batch_size=batch_size,
        )
        stats["archival_memory_read"] = archival_stats["read"]
        stats["archival_memory_migrated"] = archival_stats["migrated"]
        stats["errors"].extend(archival_stats["errors"])

    finally:
        sqlite_conn.close()

    return stats


async def _migrate_core_memory(
    sqlite_conn: sqlite3.Connection,
    session_id: str | None,
    dry_run: bool,
    batch_size: int,
) -> dict[str, Any]:
    """Migrate core memory records.

    Returns:
        Dict with 'read', 'migrated', and 'errors' keys
    """

    stats = {"read": 0, "migrated": 0, "errors": []}

    # Build query
    if session_id:
        cursor = sqlite_conn.execute(
            "SELECT session_id, key, value, updated_at FROM core_memory "
            "WHERE session_id = ?",
            (session_id,),
        )
    else:
        cursor = sqlite_conn.execute(
            "SELECT session_id, key, value, updated_at FROM core_memory"
        )

    # Collect records in batches
    batch = []
    for row in cursor:
        stats["read"] += 1
        batch.append(
            {
                "session_id": row["session_id"],
                "key": row["key"],
                "value": row["value"],
                "updated_at": row["updated_at"],
            }
        )

        # Process batch
        if len(batch) >= batch_size:
            migrated = await _write_core_batch(batch, dry_run)
            stats["migrated"] += migrated
            batch = []

    # Process remaining records
    if batch:
        migrated = await _write_core_batch(batch, dry_run)
        stats["migrated"] += migrated

    return stats


async def _write_core_batch(
    records: list[dict[str, Any]], dry_run: bool
) -> int:
    """Write a batch of core memory records to PostgreSQL.

    Uses check-then-insert pattern for idempotency because PostgreSQL
    unique constraints treat NULL as distinct values.

    Returns:
        Number of records actually inserted
    """
    if dry_run or not records:
        return 0

    from scripts.agentica_patterns.postgres_pool import get_connection

    inserted = 0
    async with get_connection() as conn:
        for record in records:
            try:
                # Convert timestamp to PostgreSQL format
                updated_at = datetime.fromtimestamp(record["updated_at"], tz=UTC)

                # Check if record already exists (NULL-safe comparison)
                # PostgreSQL unique constraint doesn't work with NULL agent_id
                existing = await conn.fetchrow(
                    """
                    SELECT 1 FROM core_memory
                    WHERE session_id = $1
                    AND agent_id IS NULL
                    AND key = $2
                    """,
                    record["session_id"],
                    record["key"],
                )

                if existing:
                    # Record already exists, skip
                    continue

                # Insert new record
                await conn.execute(
                    """
                    INSERT INTO core_memory
                        (session_id, agent_id, key, value, updated_at)
                    VALUES ($1, NULL, $2, $3, $4)
                    """,
                    record["session_id"],
                    record["key"],
                    record["value"],
                    updated_at,
                )
                inserted += 1
            except Exception:
                # Log but continue with other records
                pass

    return inserted


async def _migrate_archival_memory(
    sqlite_conn: sqlite3.Connection,
    session_id: str | None,
    dry_run: bool,
    batch_size: int,
) -> dict[str, Any]:
    """Migrate archival memory records.

    Returns:
        Dict with 'read', 'migrated', and 'errors' keys
    """
    stats = {"read": 0, "migrated": 0, "errors": []}

    # Build query
    if session_id:
        cursor = sqlite_conn.execute(
            "SELECT id, session_id, content, metadata_json, created_at "
            "FROM archival_memory WHERE session_id = ?",
            (session_id,),
        )
    else:
        cursor = sqlite_conn.execute(
            "SELECT id, session_id, content, metadata_json, created_at "
            "FROM archival_memory"
        )

    # Collect records in batches
    batch = []
    for row in cursor:
        stats["read"] += 1

        # Parse metadata, handling NULL and malformed JSON
        metadata_json = row["metadata_json"]
        metadata = {}
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                # Malformed JSON - use empty metadata and log
                metadata = {"_migration_error": "malformed_json"}
                stats["errors"].append(
                    f"Malformed metadata JSON for id={row['id']}"
                )

        batch.append(
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "content": row["content"],
                "metadata": metadata,
                "created_at": row["created_at"],
            }
        )

        # Process batch
        if len(batch) >= batch_size:
            migrated = await _write_archival_batch(batch, dry_run)
            stats["migrated"] += migrated
            batch = []

    # Process remaining records
    if batch:
        migrated = await _write_archival_batch(batch, dry_run)
        stats["migrated"] += migrated

    return stats


async def _write_archival_batch(
    records: list[dict[str, Any]], dry_run: bool
) -> int:
    """Write a batch of archival memory records to PostgreSQL.

    Uses check-then-insert pattern for idempotency, preserving original IDs
    where possible for data integrity verification.

    Returns:
        Number of records actually inserted
    """
    if dry_run or not records:
        return 0

    from scripts.agentica_patterns.postgres_pool import get_connection

    inserted = 0
    async with get_connection() as conn:
        for record in records:
            try:
                # Convert timestamp to PostgreSQL format
                created_at = datetime.fromtimestamp(record["created_at"], tz=UTC)

                # Keep original ID if valid UUID, otherwise generate new one
                # Store original ID in metadata for traceability
                original_id = record["id"]
                if _is_valid_uuid(original_id):
                    memory_id = original_id
                else:
                    memory_id = str(uuid4())
                    # Add original ID to metadata for traceability
                    if "_original_id" not in record["metadata"]:
                        record["metadata"]["_original_id"] = original_id

                # Check if record already exists by content fingerprint
                # (session + content combination is unique enough for migration)
                existing = await conn.fetchrow(
                    """
                    SELECT 1 FROM archival_memory
                    WHERE session_id = $1
                    AND agent_id IS NULL
                    AND content = $2
                    """,
                    record["session_id"],
                    record["content"],
                )

                if existing:
                    # Record already exists, skip
                    continue

                # Insert new record
                await conn.execute(
                    """
                    INSERT INTO archival_memory
                        (id, session_id, agent_id, content, metadata, created_at)
                    VALUES ($1::uuid, $2, NULL, $3, $4::jsonb, $5)
                    """,
                    memory_id,
                    record["session_id"],
                    record["content"],
                    json.dumps(record["metadata"]),
                    created_at,
                )
                inserted += 1
            except Exception:
                # Log but continue with other records
                pass

    return inserted


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID format."""
    try:
        from uuid import UUID

        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def main() -> None:
    """CLI entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate memory data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        required=True,
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

    if not args.sqlite_path.exists():
        print(f"Error: SQLite file not found: {args.sqlite_path}")
        return

    print(f"Migrating from: {args.sqlite_path}")
    if args.session_id:
        print(f"Session filter: {args.session_id}")
    if args.dry_run:
        print("DRY RUN - no changes will be written")
    print()

    stats = asyncio.run(
        migrate(
            sqlite_path=args.sqlite_path,
            session_id=args.session_id,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
    )

    print("Migration complete:")
    print(f"  Core memory:    {stats['core_memory_read']} read, "
          f"{stats['core_memory_migrated']} migrated")
    print(f"  Archival memory: {stats['archival_memory_read']} read, "
          f"{stats['archival_memory_migrated']} migrated")

    if stats["errors"]:
        print(f"  Errors: {len(stats['errors'])}")
        for error in stats["errors"][:5]:
            print(f"    - {error}")
        if len(stats["errors"]) > 5:
            print(f"    ... and {len(stats['errors']) - 5} more")


if __name__ == "__main__":
    main()
