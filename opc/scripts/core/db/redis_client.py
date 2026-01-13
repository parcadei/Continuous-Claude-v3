"""Redis client module for connection pooling and caching.

Provides async Redis client with:
- Singleton pattern for connection pooling
- Embedding-specific caching with hash-based keys
- TTL configuration for cached items

Usage:
    from scripts.core.db.redis_client import get_redis, close_redis, RedisCache, cache

    # Basic client
    client = await get_redis()
    await client.ping()

    # Embedding cache
    cached = await cache.get_embedding("my text query")
    if cached:
        return cached
"""

import hashlib
import json
import logging
import os
from typing import Any, AsyncGenerator

import redis.asyncio as redis

# Global client instance
_client: redis.Redis | None = None
_client_lock: Any | None = None

# Cache configuration
DEFAULT_CACHE_TTL = 86400  # 24 hours in seconds
EMBEDDING_CACHE_TTL = 604800  # 7 days for embeddings (long-lived)
SESSION_CACHE_TTL = 300  # 5 minutes for session data

# Cache key prefixes
EMBEDDING_PREFIX = "embedding:"
SESSION_PREFIX = "session:"


def _get_redis_url() -> str:
    """Get Redis connection URL from environment.

    Checks env vars in order:
    1. REDIS_URL - standard name
    2. OPC_REDIS_URL - project-specific
    3. AGENTICA_REDIS_URL - framework name
    4. CONTINUOUS_CLAUDE_REDIS_URL - full project name
    5. Development default
    """
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


class RedisCache:
    """Redis cache wrapper with embedding-specific methods.

    Uses SHA-256 hash of text as key to avoid storing large strings.
    Stores embeddings as JSON-serialized float arrays.
    Supports configurable TTL for cache expiration.
    """

    def __init__(
        self,
        client: redis.Redis | None = None,
        default_ttl: int = DEFAULT_CACHE_TTL,
    ):
        """Initialize cache with optional client.

        Args:
            client: Redis client instance (created if None)
            default_ttl: Default TTL in seconds for cached items
        """
        self._client = client
        self._use_global = client is None
        self._default_ttl = default_ttl

    async def _get_client(self) -> redis.Redis:
        """Get Redis client, creating if needed."""
        if self._client is None:
            self._client = await get_redis()
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

    async def set_embedding(
        self,
        text: str,
        embedding: list[float],
        ttl: int | None = None,
    ) -> None:
        """Store embedding in cache.

        Args:
            text: Original text that was embedded
            embedding: Embedding vector to cache
            ttl: TTL in seconds (default: EMBEDDING_CACHE_TTL)
        """
        try:
            client = await self._get_client()
            key = self._hash_key(text)
            expire_time = ttl if ttl is not None else EMBEDDING_CACHE_TTL
            await client.setex(
                f"{EMBEDDING_PREFIX}{key}",
                expire_time,
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

    async def set_session_data(
        self,
        session_id: str,
        key: str,
        data: Any,
        ttl: int | None = None,
    ) -> None:
        """Store session-specific data with TTL.

        Args:
            session_id: Session identifier
            key: Data key
            data: Data to store (will be JSON serialized)
            ttl: TTL in seconds (default: SESSION_CACHE_TTL)
        """
        try:
            client = await self._get_client()
            full_key = f"{SESSION_PREFIX}{session_id}:{key}"
            expire_time = ttl if ttl is not None else self._default_ttl
            await client.setex(full_key, expire_time, json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to store session data in cache: {e}")

    async def get_session_data(self, session_id: str, key: str) -> Any | None:
        """Retrieve session-specific data.

        Args:
            session_id: Session identifier
            key: Data key

        Returns:
            Data if cached, None otherwise
        """
        try:
            client = await self._get_client()
            full_key = f"{SESSION_PREFIX}{session_id}:{key}"
            result = await client.get(full_key)
            if result:
                return json.loads(result)
            return None
        except Exception as e:
            logger.error(f"Failed to get session data from cache: {e}")
            return None

    async def clear_all(self) -> int:
        """Clear all cached embeddings.

        Returns:
            Number of keys deleted
        """
        try:
            client = await self._get_client()
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


# Re-export for backwards compatibility
def get_client() -> redis.Redis:
    """Alias for get_redis() for backwards compatibility."""
    return get_redis()


async def close_client() -> None:
    """Alias for close_redis() for backwards compatibility."""
    return await close_redis()


logger = logging.getLogger(__name__)
