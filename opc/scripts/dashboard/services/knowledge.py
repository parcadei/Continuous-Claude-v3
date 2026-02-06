"""Knowledge tree pillar health service.

Provides health checks for the .claude/knowledge-tree.json file.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.models import PillarHealth, PillarStatus
from dashboard.services.base import BasePillarService

logger = logging.getLogger(__name__)

# Calculate project root: opc/scripts/dashboard/services/ -> up 5 levels to continuous-claude/
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
KNOWLEDGE_TREE_PATH = ".claude/knowledge-tree.json"
STALE_THRESHOLD_HOURS = 24


class KnowledgePillarService(BasePillarService):
    """Service for checking knowledge tree pillar health."""

    def __init__(self, project_root: Path | None = None):
        """Initialize with optional project root override.

        Args:
            project_root: Project root directory. Defaults to continuous-claude.
        """
        super().__init__("knowledge")
        self._project_root = project_root or DEFAULT_PROJECT_ROOT

    @property
    def name(self) -> str:
        """Return the pillar name."""
        return self._name

    def _get_tree_path(self) -> Path:
        """Get the path to the knowledge tree file."""
        return self._project_root / KNOWLEDGE_TREE_PATH

    async def check_health(self) -> PillarHealth:
        """Check health of the knowledge tree pillar.

        Returns:
            - ONLINE: File exists and modified <24h ago
            - DEGRADED: File exists but >24h old
            - OFFLINE: File missing or invalid
        """
        tree_path = self._get_tree_path()

        if not tree_path.exists():
            logger.warning(f"Knowledge tree not found at {tree_path}")
            return PillarHealth(
                name="knowledge",
                status=PillarStatus.OFFLINE,
                count=0,
                error="Knowledge tree file not found",
            )

        try:
            tree_data = json.loads(tree_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Knowledge tree parse error: {e}")
            return PillarHealth(
                name="knowledge",
                status=PillarStatus.OFFLINE,
                count=0,
                error=str(e),
            )

        mtime = datetime.fromtimestamp(tree_path.stat().st_mtime, tz=timezone.utc)
        age = datetime.now(tz=timezone.utc) - mtime
        is_stale = age > timedelta(hours=STALE_THRESHOLD_HOURS)

        count = len(tree_data) if isinstance(tree_data, dict) else 0

        status = PillarStatus.DEGRADED if is_stale else PillarStatus.ONLINE

        return PillarHealth(
            name="knowledge",
            status=status,
            count=count,
            last_activity=mtime,
        )

    async def get_details(self) -> dict[str, Any]:
        """Get the parsed knowledge tree structure.

        Returns:
            Dict with the full tree contents, or empty dict on error.
        """
        tree_path = self._get_tree_path()

        if not tree_path.exists():
            return {}

        try:
            return json.loads(tree_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Knowledge tree read error: {e}")
            return {}
