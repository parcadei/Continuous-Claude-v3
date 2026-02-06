"""Memory pillar drill-down router for learning data."""

import json
import os
import sys
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.db.postgres_pool import get_pool

router = APIRouter(prefix="/api/pillars/memory", tags=["memory"])


@router.get("/learnings")
async def list_learnings(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    search: Optional[str] = Query(None, description="Search text in content"),
    type_filter: Optional[str] = Query(None, description="Filter by learning type"),
) -> dict[str, Any]:
    """List learnings with pagination and optional filtering.

    Args:
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return (1-100).
        search: Optional search query to filter by content.
        type_filter: Optional filter by learning type (from metadata).

    Returns:
        Dict with items, total count, skip, and limit.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        where_clauses = []
        params = []
        param_idx = 1

        if search:
            where_clauses.append(f"to_tsvector('english', content) @@ plainto_tsquery('english', ${param_idx})")
            params.append(search)
            param_idx += 1

        if type_filter:
            where_clauses.append(f"metadata::jsonb->>'type' = ${param_idx}")
            params.append(type_filter)
            param_idx += 1

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) FROM archival_memory {where_sql}"
        total = await conn.fetchval(count_query, *params)

        params.append(limit)
        params.append(skip)
        items_query = f"""
            SELECT id, content, session_id, agent_id, project_id, scope, metadata, created_at
            FROM archival_memory
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        rows = await conn.fetch(items_query, *params)

    items = []
    for row in rows:
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        item = {
            "id": str(row["id"]),
            "content": row["content"],
            "session_id": row["session_id"],
            "agent_id": row["agent_id"],
            "project_id": row["project_id"],
            "scope": row["scope"],
            "type": metadata.get("type"),
            "context": metadata.get("context"),
            "tags": metadata.get("tags"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        items.append(item)

    return {
        "items": items,
        "total": total or 0,
        "skip": skip,
        "limit": limit,
    }


@router.get("/learnings/{learning_id}")
async def get_learning(learning_id: str) -> dict[str, Any]:
    """Get a single learning by ID.

    Args:
        learning_id: UUID of the learning to retrieve.

    Returns:
        Dict with learning data.

    Raises:
        HTTPException: 400 if invalid UUID, 404 if not found.
    """
    try:
        uuid_val = UUID(learning_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, content, session_id, agent_id, project_id, scope, metadata, created_at
            FROM archival_memory
            WHERE id = $1
            """,
            uuid_val,
        )

    if not row:
        raise HTTPException(status_code=404, detail=f"Learning {learning_id} not found")

    metadata = json.loads(row["metadata"]) if row["metadata"] else {}
    return {
        "id": str(row["id"]),
        "content": row["content"],
        "session_id": row["session_id"],
        "agent_id": row["agent_id"],
        "project_id": row["project_id"],
        "scope": row["scope"],
        "type": metadata.get("type"),
        "context": metadata.get("context"),
        "tags": metadata.get("tags"),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
