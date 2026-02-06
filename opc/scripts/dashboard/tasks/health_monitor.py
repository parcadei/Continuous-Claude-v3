"""Background health monitor for real-time pillar status updates."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.models import PillarHealth, PillarStatus
from dashboard.services.memory import MemoryPillarService
from dashboard.services.knowledge import KnowledgePillarService
from dashboard.services.pageindex import PageIndexPillarService
from dashboard.services.handoffs import HandoffsPillarService
from dashboard.services.roadmap import RoadmapPillarService
from dashboard.websocket.events import HealthUpdateEvent

if TYPE_CHECKING:
    from dashboard.websocket.manager import ConnectionManager

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Background monitor that checks pillar health and broadcasts changes."""

    def __init__(self, connection_manager: ConnectionManager, interval: int = 10):
        """Initialize the health monitor.

        Args:
            connection_manager: WebSocket manager for broadcasting updates
            interval: Seconds between health checks (default: 10)
        """
        self._connection_manager = connection_manager
        self._interval = interval
        self._previous_states: dict[str, PillarHealth] = {}
        self._task: asyncio.Task | None = None
        self._services = {
            "memory": MemoryPillarService(),
            "knowledge": KnowledgePillarService(),
            "pageindex": PageIndexPillarService(),
            "handoffs": HandoffsPillarService(),
            "roadmap": RoadmapPillarService(),
        }

    async def check_all_pillars(self) -> dict[str, PillarHealth]:
        """Check health of all 5 pillar services in parallel.

        Returns:
            Dictionary mapping pillar name to PillarHealth result
        """
        # Execute all health checks in parallel
        results = await asyncio.gather(
            self._services["memory"].check_health(),
            self._services["knowledge"].check_health(),
            self._services["pageindex"].check_health(),
            self._services["handoffs"].check_health(),
            self._services["roadmap"].check_health(),
            return_exceptions=True
        )

        pillar_names = ["memory", "knowledge", "pageindex", "handoffs", "roadmap"]
        health_results = {}

        for name, result in zip(pillar_names, results):
            if isinstance(result, Exception):
                logger.warning(f"Health check failed for {name}: {result}")
                health_results[name] = PillarHealth(
                    name=name,
                    status=PillarStatus.OFFLINE,
                    count=0,
                    error=str(result)
                )
            else:
                health_results[name] = result

        return health_results

    async def detect_changes(
        self, current_states: dict[str, PillarHealth]
    ) -> dict[str, PillarHealth]:
        """Compare current states with previous and return changed pillars.

        Args:
            current_states: Current health states for all pillars

        Returns:
            Dictionary of pillars that have changed (status or count)
        """
        changed = {}
        for name, current in current_states.items():
            previous = self._previous_states.get(name)
            if previous is None:
                changed[name] = current
            elif previous.status != current.status or previous.count != current.count:
                changed[name] = current
        return changed

    async def _run_loop(self) -> None:
        """Internal loop that checks health and broadcasts changes."""
        try:
            while True:
                current_states = await self.check_all_pillars()
                changed = await self.detect_changes(current_states)

                for name, health in changed.items():
                    event = HealthUpdateEvent(
                        pillar=name,
                        status=health.status.value,
                        count=health.count,
                    )
                    await self._connection_manager.broadcast(event.model_dump())

                self._previous_states = current_states
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            logger.info("Health monitor stopped")
            raise

    async def start(self) -> None:
        """Start the background health monitoring loop."""
        if self._task is not None:
            logger.warning("Health monitor already running")
            return
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Health monitor started with {self._interval}s interval")

    async def stop(self) -> None:
        """Stop the background health monitoring task."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Health monitor stopped")
