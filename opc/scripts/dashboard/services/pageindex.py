"""PageIndex pillar health service.

Provides health checks and statistics for the pageindex_trees table.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.db.postgres_pool import get_pool
from dashboard.models import PillarHealth, PillarStatus
from dashboard.services.base import BasePillarService

logger = logging.getLogger(__name__)


class PageIndexPillarService(BasePillarService):
    """Service for checking pageindex pillar health."""

    def __init__(self):
        """Initialize the pageindex pillar service."""
        super().__init__("pageindex")

    async def check_health(self) -> PillarHealth:
        """Check health of the pageindex pillar.

        Queries pageindex_trees table for count of indexed documents.

        Returns:
            PillarHealth with ONLINE status if successful, OFFLINE with error otherwise.
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM pageindex_trees")

            return PillarHealth(
                name="pageindex",
                status=PillarStatus.ONLINE,
                count=count or 0,
            )
        except Exception as e:
            logger.warning(f"PageIndex health check failed: {e}")
            return PillarHealth(
                name="pageindex",
                status=PillarStatus.OFFLINE,
                count=0,
                error=str(e),
            )

    async def get_details(self) -> dict[str, Any]:
        """Get detailed statistics for the pageindex pillar.

        Returns:
            Dict with:
            - documents: List of indexed documents with path, type, and updated_at
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT doc_path, doc_type, updated_at
                    FROM pageindex_trees
                    ORDER BY updated_at DESC
                    LIMIT 50
                    """
                )

            return {
                "documents": [
                    {
                        "doc_path": row["doc_path"],
                        "doc_type": row["doc_type"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ]
            }
        except Exception as e:
            logger.warning(f"PageIndex get_details failed: {e}")
            return {"documents": [], "error": str(e)}
