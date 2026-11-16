#!/usr/bin/env python3
"""
Shared SQLite connection factory with proper concurrency configuration.

This module provides a centralized way to create SQLite connections with:
- busy_timeout = 5000ms to prevent indefinite blocking
- WAL mode for better concurrent access
- Retry logic for SQLITE_LOCKED errors (same-connection table locks)

Issue: STARVATION_FINDINGS.md Finding 3 - SQLite Database Lock Without Busy Timeout
Gap 7: Negative/Zero Value Handling for Timeouts
Gap 8: SQLITE_LOCKED vs SQLITE_BUSY Handling
"""

import sqlite3
import time
from pathlib import Path
from typing import Any, Optional, Tuple, Union

# Default timeout in milliseconds (5 seconds)
DEFAULT_BUSY_TIMEOUT = 5000

# Default retry configuration for SQLITE_LOCKED
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_BASE = 0.1  # seconds


def get_connection(
    db_path: Union[str, Path],
    timeout_ms: int = DEFAULT_BUSY_TIMEOUT,
    enable_wal: bool = True,
    row_factory: bool = False,
) -> sqlite3.Connection:
    """Get SQLite connection with proper concurrency configuration.

    This factory ensures all connections are configured with:
    - busy_timeout: Prevents indefinite blocking when database is locked
    - WAL mode: Allows concurrent readers and writers

    Args:
        db_path: Path to the SQLite database file
        timeout_ms: Busy timeout in milliseconds (default: 5000).
                    Must be positive. Negative/zero values are converted to default.
        enable_wal: Whether to enable WAL journal mode (default: True)
        row_factory: Whether to set row_factory to sqlite3.Row (default: False)

    Returns:
        Configured sqlite3.Connection

    Example:
        from scripts.db_connection import get_connection

        conn = get_connection("/path/to/db.sqlite")
        try:
            cursor = conn.execute("SELECT * FROM table")
            # ... use cursor
        finally:
            conn.close()
    """
    # Gap 7: Validate timeout - reject negative/zero values
    if timeout_ms <= 0:
        timeout_ms = DEFAULT_BUSY_TIMEOUT

    conn = sqlite3.connect(str(db_path))

    # Set busy_timeout to prevent indefinite blocking
    conn.execute(f"PRAGMA busy_timeout = {timeout_ms}")

    # Enable WAL mode for better concurrent access
    if enable_wal:
        conn.execute("PRAGMA journal_mode = WAL")

    # Optionally set row factory
    if row_factory:
        conn.row_factory = sqlite3.Row

    return conn


def execute_with_retry(
    conn: sqlite3.Connection,
    sql: str,
    params: Optional[Tuple[Any, ...]] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> sqlite3.Cursor:
    """Execute SQL with retry logic for SQLITE_LOCKED errors.

    Gap 8: busy_timeout only handles SQLITE_BUSY (cross-connection contention).
    SQLITE_LOCKED occurs on same-connection table locks (e.g., modifying during iteration)
    and is NOT handled by busy_timeout. This function provides retry logic for SQLITE_LOCKED.

    Args:
        conn: SQLite connection
        sql: SQL statement to execute
        params: Optional tuple of parameters for the SQL statement
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        sqlite3.Cursor with the result

    Raises:
        sqlite3.OperationalError: If all retries fail or for non-LOCKED errors

    Example:
        from scripts.db_connection import get_connection, execute_with_retry

        conn = get_connection("/path/to/db.sqlite")
        try:
            cursor = execute_with_retry(conn, "DELETE FROM test WHERE id = ?", (1,))
        finally:
            conn.close()

    Note:
        For better patterns to avoid SQLITE_LOCKED entirely, consider:
        1. Use fetchall() before modifying: rows = cursor.fetchall()
        2. Use separate connections for reads vs writes
        3. Complete cursor iteration before starting modifications
    """
    last_exception: Optional[sqlite3.OperationalError] = None

    for attempt in range(max_retries):
        try:
            if params:
                return conn.execute(sql, params)
            return conn.execute(sql)
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            # Gap 8: Handle SQLITE_LOCKED ("database table is locked")
            # This is different from SQLITE_BUSY ("database is locked")
            if "database table is locked" in error_msg or "table is locked" in error_msg:
                if attempt < max_retries - 1:
                    # Exponential backoff: 0.1s, 0.2s, 0.3s, ...
                    time.sleep(DEFAULT_RETRY_DELAY_BASE * (attempt + 1))
                    last_exception = e
                    continue
            # For SQLITE_BUSY or other errors, don't retry - let busy_timeout handle BUSY
            raise

    # All retries exhausted
    if last_exception:
        raise last_exception
    raise sqlite3.OperationalError("execute_with_retry: unexpected state")


def fetchall_before_modify(
    conn: sqlite3.Connection,
    select_sql: str,
    select_params: Optional[Tuple[Any, ...]] = None,
) -> list:
    """Fetch all rows before modifying to avoid SQLITE_LOCKED.

    Gap 8: Pattern recommendation - use fetchall() before modifying rows.
    This function encapsulates the safe pattern for iterating over results
    when you plan to modify the table.

    Args:
        conn: SQLite connection
        select_sql: SELECT statement to fetch rows
        select_params: Optional tuple of parameters for the SELECT

    Returns:
        List of all rows from the query

    Example:
        from scripts.db_connection import get_connection, fetchall_before_modify

        conn = get_connection("/path/to/db.sqlite")
        rows = fetchall_before_modify(conn, "SELECT id FROM test WHERE status = ?", ("pending",))
        for row in rows:
            conn.execute("DELETE FROM test WHERE id = ?", (row[0],))
        conn.commit()
    """
    if select_params:
        cursor = conn.execute(select_sql, select_params)
    else:
        cursor = conn.execute(select_sql)
    return cursor.fetchall()
