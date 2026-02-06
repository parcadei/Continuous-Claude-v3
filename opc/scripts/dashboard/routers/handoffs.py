"""Handoffs drill-down router for listing and retrieving handoffs."""

import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.db.postgres_pool import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pillars/handoffs", tags=["handoffs"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
HANDOFF_PATTERN = "HANDOFF-*.md"
VALID_OUTCOMES = ("SUCCEEDED", "PARTIAL_PLUS", "PARTIAL_MINUS", "FAILED", "UNKNOWN")


def _scan_handoff_files() -> list[dict[str, Any]]:
    """Scan for HANDOFF-*.md files in .claude directory.

    Returns:
        List of handoff dicts with file metadata.
    """
    claude_dir = PROJECT_ROOT / ".claude"
    handoffs = []

    if not claude_dir.exists():
        return handoffs

    for file_path in claude_dir.glob(HANDOFF_PATTERN):
        try:
            stat = file_path.stat()
            name = file_path.stem.replace("HANDOFF-", "")
            handoffs.append({
                "id": f"file:{file_path.name}",
                "title": name,
                "status": "UNKNOWN",
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "source": "file",
                "file_path": str(file_path),
            })
        except Exception as e:
            logger.debug(f"Error reading handoff file {file_path}: {e}")

    return handoffs


async def _get_db_handoffs(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
) -> tuple[list[dict[str, Any]], int]:
    """Query handoffs from database.

    Args:
        skip: Number of records to skip.
        limit: Maximum records to return.
        status_filter: Filter by outcome status.

    Returns:
        Tuple of (handoffs list, total count).
    """
    handoffs = []
    total = 0

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            base_query = "SELECT id, session_name, goal, outcome, created_at, file_path FROM handoffs"
            count_query = "SELECT COUNT(*) FROM handoffs"

            if status_filter and status_filter in VALID_OUTCOMES:
                base_query += f" WHERE outcome = $1"
                count_query += f" WHERE outcome = $1"
                params = [status_filter]
            else:
                params = []

            base_query += " ORDER BY created_at DESC"
            base_query += f" OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}"
            params.extend([skip, limit])

            if status_filter and status_filter in VALID_OUTCOMES:
                total = await conn.fetchval(count_query, status_filter)
                rows = await conn.fetch(base_query, *params)
            else:
                total = await conn.fetchval(count_query)
                rows = await conn.fetch(base_query, skip, limit)

            for row in rows:
                handoffs.append({
                    "id": str(row["id"]),
                    "title": row["goal"] or row["session_name"],
                    "status": row["outcome"] or "UNKNOWN",
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "source": "db",
                    "file_path": row["file_path"],
                })
    except Exception as e:
        logger.debug(f"Error querying handoffs from DB: {e}")

    return handoffs, total


@router.get("")
async def list_handoffs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    status_filter: Optional[str] = Query(None, description="Filter by outcome status"),
) -> dict[str, Any]:
    """List handoffs with pagination and optional filtering.

    Combines results from:
    - PostgreSQL handoffs table
    - HANDOFF-*.md files in .claude/ directory

    Args:
        skip: Pagination offset.
        limit: Maximum results per page.
        status_filter: Filter by outcome (SUCCEEDED, PARTIAL_PLUS, etc.)

    Returns:
        Dict with handoffs list and total count.
    """
    db_handoffs, db_total = await _get_db_handoffs(skip, limit, status_filter)
    file_handoffs = _scan_handoff_files()

    if status_filter:
        file_handoffs = [h for h in file_handoffs if h["status"] == status_filter]

    all_handoffs = db_handoffs + file_handoffs
    all_handoffs.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    paginated = all_handoffs[skip : skip + limit]

    return {
        "handoffs": paginated,
        "total": db_total + len(file_handoffs),
    }


@router.get("/{handoff_id}")
async def get_handoff(handoff_id: str) -> dict[str, Any]:
    """Get a single handoff by ID.

    Args:
        handoff_id: UUID for DB handoffs or "file:filename" for file handoffs.

    Returns:
        Handoff details.

    Raises:
        HTTPException: 404 if handoff not found.
    """
    if handoff_id.startswith("file:"):
        filename = handoff_id[5:]

        # Validate filename pattern (HANDOFF-*.md only)
        if not re.match(r'^HANDOFF-[A-Za-z0-9_-]+\.md$', filename):
            raise HTTPException(status_code=400, detail="Invalid filename format")

        claude_dir = PROJECT_ROOT / ".claude"
        file_path = (claude_dir / filename).resolve()

        # Verify path is within allowed directory
        if not str(file_path).startswith(str(claude_dir.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Handoff file not found")

        try:
            stat = file_path.stat()
            content = file_path.read_text(encoding="utf-8")
            name = file_path.stem.replace("HANDOFF-", "")

            return {
                "id": handoff_id,
                "title": name,
                "status": "UNKNOWN",
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "source": "file",
                "file_path": str(file_path),
                "content": content,
            }
        except Exception as e:
            logger.error(f"Error reading handoff file {file_path}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error reading handoff file")

    try:
        uuid_id = UUID(handoff_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid handoff ID format")

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, session_name, file_path, format, session_id, agent_id,
                       root_span_id, jsonl_path, goal, what_worked, what_failed,
                       key_decisions, outcome, outcome_notes, content, created_at
                FROM handoffs
                WHERE id = $1
                """,
                uuid_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail=f"Handoff not found: {handoff_id}")

            return {
                "id": str(row["id"]),
                "title": row["goal"] or row["session_name"],
                "session_name": row["session_name"],
                "status": row["outcome"] or "UNKNOWN",
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "source": "db",
                "file_path": row["file_path"],
                "format": row["format"],
                "session_id": row["session_id"],
                "agent_id": row["agent_id"],
                "root_span_id": row["root_span_id"],
                "jsonl_path": row["jsonl_path"],
                "goal": row["goal"],
                "what_worked": row["what_worked"],
                "what_failed": row["what_failed"],
                "key_decisions": row["key_decisions"],
                "outcome_notes": row["outcome_notes"],
                "content": row["content"],
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching handoff {handoff_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
