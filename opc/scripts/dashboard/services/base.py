"""Base service interface for dashboard pillars."""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from abc import ABC, abstractmethod
from dashboard.models import PillarHealth


class BasePillarService(ABC):
    """Abstract base class for pillar health monitoring services."""

    def __init__(self, name: str):
        """Initialize service with pillar name.

        Args:
            name: Name of the pillar (e.g., "Memory", "Hooks")
        """
        self._name = name

    @property
    def name(self) -> str:
        """Return the pillar name."""
        return self._name

    @abstractmethod
    async def check_health(self) -> PillarHealth:
        """Check the health status of this pillar.

        Returns:
            PillarHealth instance with status, message, and metrics
        """
        pass

    @abstractmethod
    async def get_details(self) -> dict:
        """Get detailed information about this pillar.

        Returns:
            Dictionary with pillar-specific details
        """
        pass
