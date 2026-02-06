"""Data models for dashboard health monitoring."""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel


class PillarStatus(str, Enum):
    """Health status of a pillar."""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class PillarHealth(BaseModel):
    """Health information for a single pillar."""
    name: str
    status: PillarStatus
    count: int = 0
    last_activity: Optional[datetime] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Complete health status response."""
    pillars: Dict[str, PillarHealth]
