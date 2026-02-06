"""WebSocket connection manager for Session Dashboard."""

import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        """Initialize with empty connections and subscriptions."""
        self.active_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and store a WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept
            client_id: Unique identifier for the client
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket

    async def disconnect(self, client_id: str) -> None:
        """Remove a client connection and their subscriptions.

        Args:
            client_id: The client to disconnect
        """
        self.active_connections.pop(client_id, None)
        self.subscriptions.pop(client_id, None)

    async def subscribe(self, client_id: str, project_id: str) -> None:
        """Subscribe a client to a project.

        Args:
            client_id: The client subscribing
            project_id: The project to subscribe to
        """
        if client_id not in self.subscriptions:
            self.subscriptions[client_id] = set()
        self.subscriptions[client_id].add(project_id)

    async def unsubscribe(self, client_id: str, project_id: str) -> None:
        """Unsubscribe a client from a project.

        Args:
            client_id: The client unsubscribing
            project_id: The project to unsubscribe from
        """
        if client_id in self.subscriptions:
            self.subscriptions[client_id].discard(project_id)

    async def broadcast(self, message: dict, project_id: str | None = None) -> None:
        """Send a message to connected clients, handling disconnections gracefully.

        Args:
            message: Dictionary to serialize and send
            project_id: If specified, only send to clients subscribed to this project
        """
        json_message = json.dumps(message)
        disconnected = []

        if project_id is None:
            for client_id, websocket in self.active_connections.items():
                try:
                    await websocket.send_text(json_message)
                except Exception as e:
                    logger.warning(f"Failed to send to {client_id}: {e}")
                    disconnected.append(client_id)
        else:
            for client_id, websocket in self.active_connections.items():
                if project_id in self.subscriptions.get(client_id, set()):
                    try:
                        await websocket.send_text(json_message)
                    except Exception as e:
                        logger.warning(f"Failed to send to {client_id}: {e}")
                        disconnected.append(client_id)

        # Clean up dead connections
        for client_id in disconnected:
            await self.disconnect(client_id)

    async def send_personal(self, client_id: str, message: dict) -> None:
        """Send a message to a specific client.

        Args:
            client_id: The client to send to
            message: Dictionary to serialize and send
        """
        websocket = self.active_connections.get(client_id)
        if websocket:
            json_message = json.dumps(message)
            await websocket.send_text(json_message)
