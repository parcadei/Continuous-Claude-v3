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
        List of goal dicts with 'id', 'text', 'completed', and 'section' keys.
    """
    # Calculate project root: opc/scripts/dashboard/routers/ -> up 5 levels
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    roadmap_path = project_root / "ROADMAP.md"

    if not roadmap_path.exists():
        raise FileNotFoundError(f"ROADMAP.md not found at {roadmap_path}")

    content = roadmap_path.read_text(encoding="utf-8")
    goals = []
    current_section = "General"

    for line in content.splitlines():
        # Track section headers (## or ###)
        header_match = re.match(r"^#{2,3}\s+(.+)$", line)
        if header_match:
            current_section = header_match.group(1).strip()
            continue

        # Match checkbox items
        checkbox_match = re.match(r"^- \[([ x])\]\s+(.+)$", line, re.IGNORECASE)
        if checkbox_match:
            checkbox = checkbox_match.group(1).strip().lower()
            text = checkbox_match.group(2).strip()
            completed = checkbox == "x"
            goals.append({
                "id": f"goal-{len(goals)}",
                "text": text,
                "completed": completed,
                "section": current_section,
            })

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

        total = len(goals)
        return {
            "goals": goals,
            "completed": completed_count,
            "total": total,
            "completion_rate": round((completed_count / total * 100), 1) if total > 0 else 0,
        }
    except FileNotFoundError as e:
        logger.error(f"ROADMAP.md not found: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Roadmap file not found")
    except Exception as e:
        logger.error(f"Error parsing ROADMAP.md: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error parsing roadmap file")
