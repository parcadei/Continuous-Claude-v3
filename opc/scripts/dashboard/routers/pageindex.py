"""PageIndex pillar drill-down router for document index data."""

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Query

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.db.postgres_pool import get_pool

router = APIRouter(prefix="/api/pillars/pageindex", tags=["pageindex"])

DOC_TYPE_TO_LANGUAGE = {
    "ROADMAP": "markdown",
    "ARCHITECTURE": "markdown",
    "README": "markdown",
    "DOCUMENTATION": "markdown",
    "CONFIGURATION": "yaml",
    "SKILL": "markdown",
    "HOOK": "typescript",
    "RULE": "markdown",
    "SCRIPT": "python",
    "SOURCE_CODE": "typescript",
    "TEST": "typescript",
    "GUIDE": "markdown",
    "OTHER": "text",
}


@router.get("/documents")
async def list_documents(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Records per page"),
    search: Optional[str] = Query(None, description="Filter by doc_path"),
) -> dict[str, Any]:
    """List indexed documents with pagination and optional search."""
    offset = (page - 1) * page_size

    pool = await get_pool()
    async with pool.acquire() as conn:
        where_clauses = []
        params = []
        param_idx = 1

        if search:
            where_clauses.append(f"doc_path ILIKE ${param_idx}")
            params.append(f"%{search}%")
            param_idx += 1

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM pageindex_trees {where_sql}", *params
        )

        params.append(page_size)
        params.append(offset)
        rows = await conn.fetch(
            f"""
            SELECT id, doc_path, doc_type, doc_hash, updated_at
            FROM pageindex_trees
            {where_sql}
            ORDER BY updated_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
        )

    documents = []
    for row in rows:
        doc_type = row["doc_type"] or ""
        documents.append(
            {
                "id": str(row["id"]),
                "file_path": row["doc_path"],
                "status": "indexed",
                "indexed_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "language": DOC_TYPE_TO_LANGUAGE.get(doc_type, "text"),
                "error": None,
            }
        )

    return {
        "documents": documents,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get summary statistics for indexed documents."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM pageindex_trees")
        type_rows = await conn.fetch(
            "SELECT doc_type, COUNT(*) as cnt FROM pageindex_trees GROUP BY doc_type ORDER BY cnt DESC"
        )

    return {
        "total": total or 0,
        "by_type": {row["doc_type"]: row["cnt"] for row in type_rows},
    }
