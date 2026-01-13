#!/usr/bin/env python3
"""Redis pub/sub for inter-agent messaging."""

import asyncio
import json
from typing import Callable, Dict, Set
from .redis_client import get_redis


class RedisPubSub:
    """Publish/subscribe for agent coordination."""

    def __init__(self):
        self._redis = None
        self._pubsub = None
        self._subscriptions: Dict[str, Set[Callable]] = {}
        self._listener_task: Optional[asyncio.Task] = None

    async def _get_client(self):
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis.client

    async def publish(self, channel: str, message: dict) -> int:
        """Publish message to channel."""
        client = await self._get_client()
        return await client.publish(channel, json.dumps(message))

    async def subscribe(self, channel: str, callback: Callable) -> None:
        """Subscribe to channel with callback."""
        if self._pubsub is None:
            self._pubsub = (await self._get_client()).pubsub()
            self._listener_task = asyncio.create_task(self._listen())

        await self._pubsub.subscribe(channel)
        if channel not in self._subscriptions:
            self._subscriptions[channel] = set()
        self._subscriptions[channel].add(callback)

    async def _listen(self) -> None:
        """Listen for messages."""
        async for message in self._pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"]
                data = json.loads(message["data"])
                if channel in self._subscriptions:
                    for cb in self._subscriptions[channel]:
                        asyncio.create_task(cb(data))

    async def close(self) -> None:
        """Close pub/sub."""
        if self._listener_task:
            self._listener_task.cancel()
        if self._pubsub:
            await self._pubsub.close()


# Channels
AGENT_INBOX = "agent:{id}:inbox"
SWARM_EVENTS = "swarm:{id}:events"
SESSION_HEARTBEAT = "session:{id}:heartbeat"

pubsub = RedisPubSub()
