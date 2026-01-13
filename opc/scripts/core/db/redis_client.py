"""Redis client module for connection pooling.

Provides async Redis client with singleton pattern.
Uses redis.asyncio for async operations.

Usage:
    from scripts.core.db.redis_client import get_redis
    client = await get_redis()
    await client.ping()
"""

import os
from typing import AsyncGenerator

import redis.asyncio as redis

# TTL constants for Redis keys
# These values balance freshness with memory efficiency

DEFAULT_TTL: int = 3600  # General cache entries: 1 hour
SESSION_TTL: int = 300   # Session data: 5 minutes
HEARTBEAT_TTL: int = 90  # Heartbeat signals: 90 seconds (should be > poll interval)
MESSAGE_TTL: int = 60    # Message queue entries: 1 minute
LOCK_TTL: int = 30       # Distributed locks: 30 seconds (should be < operation time)

# Global client instance
_client: redis.Redis | None = None
_client_lock: any = None


def _get_redis_url() -> str:
    """Get Redis connection URL from environment."""
    return (
        os.environ.get("REDIS_URL")
        or os.environ.get("OPC_REDIS_URL")
        or os.environ.get("AGENTICA_REDIS_URL")
        or os.environ.get("CONTINUOUS_CLAUDE_REDIS_URL")
        or "redis://localhost:6379/0"
    )


async def get_redis() -> redis.Redis:
    """Get or create the global Redis client.

    Thread-safe singleton pattern for connection pooling.

    Returns:
        Redis client instance
    """
    global _client, _client_lock

    if _client_lock is None:
        import asyncio
        _client_lock = asyncio.Lock()

    async with _client_lock:
        if _client is None:
            _client = redis.Redis.from_url(
                _get_redis_url(),
                decode_responses=True,
                socket_connect_timeout=5.0,
                max_connections=10,
            )
        return _client


async def close_redis() -> None:
    """Close the Redis client gracefully."""
    global _client

    if _client is not None:
        await _client.close()
        _client = None
