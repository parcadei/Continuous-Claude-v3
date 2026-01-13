#!/usr/bin/env python3
"""Session heartbeat using Redis for real-time crash detection."""

import asyncio
import json
from datetime import datetime
from typing import Optional, Dict
from .redis_client import get_redis

HEARTBEAT_TTL = 90  # 90 seconds (3x poll interval)


class SessionHeartbeat:
    """Redis-backed session heartbeat for crash detection."""

    def __init__(self):
        self._redis = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def _get_client(self):
        if self._redis is None:
            client = await get_redis()
            self._redis = client.client
        return self._redis

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}:heartbeat"

    async def beat(self, session_id: str, project: str = None, working_on: str = None) -> None:
        """Record heartbeat for session."""
        client = await self._get_client()
        data = {
            "session_id": session_id,
            "project": project,
            "working_on": working_on,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await client.setex(self._key(session_id), HEARTBEAT_TTL, json.dumps(data))

    async def is_alive(self, session_id: str) -> bool:
        """Check if session heartbeat is still active."""
        client = await self._get_client()
        return await client.exists(self._key(session_id)) > 0

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data from heartbeat."""
        client = await self._get_client()
        data = await client.get(self._key(session_id))
        if data:
            return json.loads(data)
        return None

    async def get_active_sessions(self) -> list:
        """Get all sessions with active heartbeats."""
        client = await self._get_client()
        # Use SCAN to find all heartbeat keys
        sessions = []
        async for key in client.scan_iter(match="session:*:heartbeat"):
            data = await client.get(key)
            if data:
                sessions.append(json.loads(data))
        return sessions

    async def remove(self, session_id: str) -> None:
        """Remove session heartbeat (on clean shutdown)."""
        client = await self._get_client()
        await client.delete(self._key(session_id))

    async def start_monitoring(self, check_interval: int = 30) -> None:
        """Start background monitoring for stale sessions."""
        self._running = True
        self._task = asyncio.create_task(self._monitor(check_interval))

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor(self, check_interval: int) -> None:
        """Monitor for stale sessions (no heartbeat)."""
        while self._running:
            sessions = await self.get_active_sessions()
            stale = [s for s in sessions if not await self.is_alive(s["session_id"])]
            if stale:
                # Log or handle stale sessions
                print(f"Found {len(stale)} stale sessions")
            await asyncio.sleep(check_interval)


# Singleton
heartbeat = SessionHeartbeat()
