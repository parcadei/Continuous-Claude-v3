"""Memory pillar health service.

Provides health checks and statistics for the archival_memory table.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.db.postgres_pool import get_pool
from dashboard.models import PillarHealth, PillarStatus
from dashboard.services.base import BasePillarService

logger = logging.getLogger(__name__)


class MemoryPillarService(BasePillarService):
    """Service for checking memory pillar health."""

    def __init__(self):
        """Initialize the memory pillar service."""
        super().__init__("memory")

    async def check_health(self) -> PillarHealth:
        """Check health of the memory pillar.

        Queries archival_memory table for:
        - Total count of learnings
        - Most recent learning timestamp

        Returns:
            PillarHealth with ONLINE status if successful, OFFLINE with error otherwise.
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM archival_memory")
                last_activity = await conn.fetchval(
                    "SELECT MAX(created_at) FROM archival_memory"
                )

            return PillarHealth(
                name="memory",
                status=PillarStatus.ONLINE,
                count=count or 0,
                last_activity=last_activity,
            )
        except Exception as e:
            logger.warning(f"Memory health check failed: {e}")
            return PillarHealth(
                name="memory",
                status=PillarStatus.OFFLINE,
                count=0,
                error=str(e),
            )

    async def get_details(self) -> dict[str, Any]:
        """Get detailed statistics for the memory pillar.

        Returns:
            Dict with:
            - by_type: Count of learnings by type (from metadata->type)
            - by_scope: Count by scope
            - recent_entries: Last 5 entries
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                type_rows = await conn.fetch(
                    """
                    SELECT metadata->>'type' as learning_type, COUNT(*) as count
                    FROM archival_memory
                    WHERE metadata->>'type' IS NOT NULL
                    GROUP BY metadata->>'type'
                    ORDER BY count DESC
                    """
                )
                scope_rows = await conn.fetch(
                    """
                    SELECT scope, COUNT(*) as count
                    FROM archival_memory
                    GROUP BY scope
                    ORDER BY count DESC
                    """
                )
                recent_rows = await conn.fetch(
                    """
                    SELECT id, content, created_at
                    FROM archival_memory
                    ORDER BY created_at DESC
                    LIMIT 5
                    """
                )

            by_type = {row["learning_type"]: row["count"] for row in type_rows if row["learning_type"]}
            by_scope = {row["scope"] or "unknown": row["count"] for row in scope_rows}
            recent_entries = [
                {
                    "id": str(row["id"]),
                    "content": row["content"][:100] if row["content"] else "",
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in recent_rows
            ]

            return {
                "by_type": by_type,
                "by_scope": by_scope,
                "recent_entries": recent_entries,
            }
        except Exception as e:
            logger.warning(f"Memory details fetch failed: {e}")
            return {}
