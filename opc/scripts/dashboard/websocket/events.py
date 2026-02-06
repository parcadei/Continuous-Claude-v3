"""WebSocket event models for Session Dashboard."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class HealthUpdateEvent(BaseModel):
    """Health status update for a pillar."""

    type: Literal["health_update"] = "health_update"
    pillar: str = Field(..., description="Name of the pillar (hooks/memory/agents/workflows)")
    status: str = Field(..., description="Status: online/offline/degraded")
    count: int = Field(..., description="Count of active/enabled items")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json()


class ActivityEvent(BaseModel):
    """Activity event for real-time updates."""

    type: Literal["activity"] = "activity"
    pillar: str = Field(..., description="Pillar where activity occurred")
    action: str = Field(..., description="Action performed (e.g., 'hook_fired', 'agent_spawned')")
    details: dict = Field(default_factory=dict, description="Additional context")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json()


class NotificationEvent(BaseModel):
    """General notification event."""

    type: Literal["notification"] = "notification"
    level: str = Field(..., description="Notification level: info/warning/error")
    message: str = Field(..., description="Notification message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json()


# Union type for all events (useful for type discrimination)
WebSocketEvent = HealthUpdateEvent | ActivityEvent | NotificationEvent
