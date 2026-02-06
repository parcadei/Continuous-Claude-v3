"""Health check router for pillar status monitoring."""

import os
import sys
from typing import Any

from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.models import HealthResponse, PillarHealth
from dashboard.services.memory import MemoryPillarService
from dashboard.services.knowledge import KnowledgePillarService
from dashboard.services.pageindex import PageIndexPillarService
from dashboard.services.roadmap import RoadmapPillarService
from dashboard.services.handoffs import HandoffsPillarService

router = APIRouter(prefix="/api", tags=["health"])

memory_service = MemoryPillarService()
knowledge_service = KnowledgePillarService()
pageindex_service = PageIndexPillarService()
roadmap_service = RoadmapPillarService()
handoffs_service = HandoffsPillarService()


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Get health status of all pillars.

    Returns:
        HealthResponse with status of all 5 pillars.
    """
    memory_health = await memory_service.check_health()
    knowledge_health = await knowledge_service.check_health()
    pageindex_health = await pageindex_service.check_health()
    roadmap_health = await roadmap_service.check_health()
    handoffs_health = await handoffs_service.check_health()

    return HealthResponse(
        pillars={
            "memory": memory_health,
            "knowledge": knowledge_health,
            "pageindex": pageindex_health,
            "roadmap": roadmap_health,
            "handoffs": handoffs_health,
        }
    )


PILLAR_SERVICES = {
    "memory": memory_service,
    "knowledge": knowledge_service,
    "pageindex": pageindex_service,
    "roadmap": roadmap_service,
    "handoffs": handoffs_service,
}


@router.get("/health/{pillar}")
async def get_pillar_health(pillar: str) -> dict[str, Any]:
    """Get detailed health status for a specific pillar.

    Args:
        pillar: Name of the pillar (memory, knowledge, pageindex, roadmap, handoffs)

    Returns:
        Dict with pillar health and detailed statistics.

    Raises:
        HTTPException: 404 if pillar not found.
    """
    if pillar not in PILLAR_SERVICES:
        raise HTTPException(status_code=404, detail=f"Pillar '{pillar}' not found")

    service = PILLAR_SERVICES[pillar]
    health = await service.check_health()
    details = await service.get_details()
    return {
        "name": health.name,
        "status": health.status.value,
        "count": health.count,
        "last_activity": health.last_activity,
        "error": health.error,
        "details": details,
    }
