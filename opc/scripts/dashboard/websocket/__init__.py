"""WebSocket handlers for real-time dashboard updates."""

from dashboard.websocket.manager import ConnectionManager
from dashboard.websocket.events import (
    HealthUpdateEvent,
    ActivityEvent,
    NotificationEvent,
    WebSocketEvent,
)

__all__ = [
    "ConnectionManager",
    "HealthUpdateEvent",
    "ActivityEvent",
    "NotificationEvent",
    "WebSocketEvent",
]
