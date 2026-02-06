"""Roadmap drill-down router for goal-level details."""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.services.roadmap import RoadmapPillarService

router = APIRouter(prefix="/api/pillars/roadmap", tags=["roadmap"])

roadmap_service = RoadmapPillarService()


def _parse_goals_from_roadmap() -> list[dict[str, Any]]:
    """Parse ROADMAP.md and extract all goals with completion status.

    Returns:
        List of goal dicts with 'text' and 'completed' keys.
    """
    # Calculate project root: opc/scripts/dashboard/routers/ -> up 5 levels
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    roadmap_path = project_root / "ROADMAP.md"

    if not roadmap_path.exists():
        raise FileNotFoundError(f"ROADMAP.md not found at {roadmap_path}")

    content = roadmap_path.read_text(encoding="utf-8")
    goals = []

    # Match both completed and planned items
    # Pattern: - [x] or - [ ] followed by text
    for match in re.finditer(r"^- \[([ x])\]\s+(.+)$", content, re.MULTILINE | re.IGNORECASE):
        checkbox = match.group(1).strip().lower()
        text = match.group(2).strip()
        completed = checkbox == "x"
        goals.append({"text": text, "completed": completed})

    return goals


@router.get("/goals")
async def get_roadmap_goals() -> dict[str, Any]:
    """Get all roadmap goals with completion status.

    Returns:
        Dict with:
        - goals: List of {text, completed}
        - summary: {completed, planned}

    Raises:
        HTTPException: 500 if ROADMAP.md cannot be read.
    """
    try:
        goals = _parse_goals_from_roadmap()
        completed_count = sum(1 for g in goals if g["completed"])
        planned_count = sum(1 for g in goals if not g["completed"])

        return {
            "goals": goals,
            "summary": {
                "completed": completed_count,
                "planned": planned_count,
            },
        }
    except FileNotFoundError as e:
        logger.error(f"ROADMAP.md not found: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Roadmap file not found")
    except Exception as e:
        logger.error(f"Error parsing ROADMAP.md: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error parsing roadmap file")
