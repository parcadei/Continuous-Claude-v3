"""Redis cache module for embedding caching.

Provides a simple async Redis client with embedding-specific methods.
Uses hash-based keys to avoid storing large text in Redis.

Usage:
    from scripts.core.db.redis_cache import cache

    # Check cache first
    cached = await cache.get_embedding("my text query")
    if cached:
        return cached

    # Store after generating
    await cache.set_embedding("my text query", embedding)
"""

import hashlib
import json
import logging
import os
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Global Redis client instance
_client: redis.Redis | None = None
_client_lock: Any | None = None

# Cache key prefix for embeddings
EMBEDDING_PREFIX = "embedding:"


def _get_redis_url() -> str:
    """Get Redis connection URL from environment.

    Checks env vars in order:
    1. REDIS_URL - standard name
    2. OPC_REDIS_URL - project-specific
    3. AGENTICA_REDIS_URL - framework name
    4. Development default
    """
    return (
        os.environ.get("REDIS_URL")
        or os.environ.get("OPC_REDIS_URL")
        or os.environ.get("AGENTICA_REDIS_URL")
        or "redis://localhost:6379/0"
    )


async def get_client() -> redis.Redis:
    """Get or create the global Redis client.

    Thread-safe via asyncio.Lock. Creates client with:
    - decode_responses=True for string keys
    - socket_connect_timeout for resilience
    - max_connections for pooling

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


async def close_client() -> None:
    """Close the Redis client gracefully."""
    global _client

    if _client is not None:
        await _client.close()
        _client = None


class RedisCache:
    """Redis cache wrapper with embedding-specific methods.

    Uses SHA-256 hash of text as key to avoid storing large strings.
    Stores embeddings as JSON-serialized float arrays.
    """

    def __init__(self, client: redis.Redis | None = None):
        """Initialize cache with optional client.

        Args:
            client: Redis client instance (created if None)
        """
        self._client = client
        self._use_global = client is None

    async def _get_client(self) -> redis.Redis:
        """Get Redis client, creating if needed."""
        if self._client is None:
            self._client = await get_client()
        return self._client

    def _hash_key(self, text: str) -> str:
        """Generate cache key from text content.

        Args:
            text: Text to hash

        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(text.encode()).hexdigest()

    async def get_embedding(self, text: str) -> list[float] | None:
        """Retrieve cached embedding for text.

        Args:
            text: Original text that was embedded

        Returns:
            Embedding vector if cached, None otherwise
        """
        try:
            client = await self._get_client()
            key = self._hash_key(text)
            result = await client.get(f"{EMBEDDING_PREFIX}{key}")

            if result:
                return json.loads(result)
            return None
        except Exception as e:
            logger.error(f"Failed to get embedding from cache: {e}")
            return None

    async def set_embedding(self, text: str, embedding: list[float]) -> None:
        """Store embedding in cache.

        Args:
            text: Original text that was embedded
            embedding: Embedding vector to cache
        """
        try:
            client = await self._get_client()
            key = self._hash_key(text)
            # Store with no expiration (embedding cache is permanent)
            await client.set(
                f"{EMBEDDING_PREFIX}{key}",
                json.dumps(embedding),
            )
        except Exception as e:
            logger.error(f"Failed to store embedding in cache: {e}")

    async def delete_embedding(self, text: str) -> bool:
        """Remove embedding from cache.

        Args:
            text: Original text that was embedded

        Returns:
            True if key was deleted, False otherwise
        """
        try:
            client = await self._get_client()
            key = self._hash_key(text)
            result = await client.delete(f"{EMBEDDING_PREFIX}{key}")
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete embedding from cache: {e}")
            return False

    async def clear_all(self) -> int:
        """Clear all cached embeddings.

        Returns:
            Number of keys deleted
        """
        try:
            client = await self._get_client()
            # Find all embedding keys
            keys = []
            async for key in client.scan_iter(f"{EMBEDDING_PREFIX}*"):
                keys.append(key)

            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Failed to clear embedding cache: {e}")
            return 0

    async def health_check(self) -> tuple[bool, str | None]:
        """Check if Redis connection is healthy.

        Returns:
            Tuple of (is_healthy, error_message)
        """
        try:
            client = await self._get_client()
            await client.ping()
            return (True, None)
        except Exception as e:
            return (False, str(e))


# Global cache instance for convenience
cache = RedisCache()
