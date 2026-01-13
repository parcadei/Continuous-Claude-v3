#!/usr/bin/env python3
"""Redis connection pool manager."""

import asyncio
import redis.asyncio as redis
from typing import Optional
from contextlib import asynccontextmanager


class RedisClient:
    """Singleton Redis client with connection pooling."""

    _instance: Optional['RedisClient'] = None
    _pool: Optional[redis.ConnectionPool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self, url: str = "redis://localhost:6379") -> None:
        """Create connection pool."""
        self._pool = redis.ConnectionPool.from_url(url)
        self._client = redis.Redis(connection_pool=self._pool)

    async def close(self) -> None:
        """Close connection pool."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()

    @property
    def client(self) -> redis.Redis:
        return self._client


async def get_redis() -> RedisClient:
    """Get or create Redis client singleton."""
    client = RedisClient()
    if client._client is None:
        await client.connect()
    return client
