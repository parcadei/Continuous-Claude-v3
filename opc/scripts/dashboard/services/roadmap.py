"""Roadmap pillar health service."""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.services.base import BasePillarService
from dashboard.models import PillarHealth, PillarStatus

# Calculate project root: opc/scripts/dashboard/services/ -> up 5 levels to continuous-claude/
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


class RoadmapPillarService(BasePillarService):
    """Service for checking roadmap pillar health."""

    def __init__(self, project_root: Path | None = None):
        super().__init__("roadmap")
        self._project_root = project_root or DEFAULT_PROJECT_ROOT

    def _parse_roadmap(self) -> tuple[int, int]:
        """Parse ROADMAP.md and count completed/planned items.

        Returns:
            Tuple of (completed_count, planned_count)
        """
        roadmap_path = self._project_root / "ROADMAP.md"
        if not roadmap_path.exists():
            raise FileNotFoundError(f"ROADMAP.md not found at {roadmap_path}")

        content = roadmap_path.read_text(encoding="utf-8")
        completed = len(re.findall(r"^- \[x\]", content, re.MULTILINE | re.IGNORECASE))
        planned = len(re.findall(r"^- \[ \]", content, re.MULTILINE))
        return completed, planned

    async def check_health(self) -> PillarHealth:
        """Check health of the roadmap pillar.

        Returns:
            PillarHealth with ONLINE if ROADMAP.md exists, OFFLINE otherwise.
            count = number of completed items
        """
        try:
            completed, _ = self._parse_roadmap()
            return PillarHealth(
                name=self.name,
                status=PillarStatus.ONLINE,
                count=completed,
            )
        except FileNotFoundError as e:
            return PillarHealth(
                name=self.name,
                status=PillarStatus.OFFLINE,
                count=0,
                error=str(e),
            )
        except Exception as e:
            return PillarHealth(
                name=self.name,
                status=PillarStatus.OFFLINE,
                count=0,
                error=f"Error parsing ROADMAP.md: {e}",
            )

    async def get_details(self) -> dict:
        """Get detailed breakdown of roadmap items.

        Returns:
            Dict with completed and planned counts.
        """
        try:
            completed, planned = self._parse_roadmap()
            return {
                "completed": completed,
                "planned": planned,
                "total": completed + planned,
            }
        except FileNotFoundError as e:
            return {
                "completed": 0,
                "planned": 0,
                "total": 0,
                "error": str(e),
            }
        except Exception as e:
            return {
                "completed": 0,
                "planned": 0,
                "total": 0,
                "error": f"Error parsing ROADMAP.md: {e}",
            }
