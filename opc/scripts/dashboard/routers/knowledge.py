"""Knowledge tree drill-down router."""

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.services.knowledge import KnowledgePillarService

router = APIRouter(prefix="/api/pillars/knowledge", tags=["knowledge"])

knowledge_service = KnowledgePillarService()


@router.get("/tree")
async def get_knowledge_tree() -> dict[str, Any]:
    """Get the full knowledge tree structure.

    Returns:
        Dict with the parsed knowledge-tree.json contents, or empty dict if not found.
    """
    return await knowledge_service.get_details()
