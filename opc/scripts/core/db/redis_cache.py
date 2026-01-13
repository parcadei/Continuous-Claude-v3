#!/usr/bin/env python3
"""Redis hot cache for embeddings and query results."""

import hashlib
import json
from typing import Optional, Any
from .redis_client import get_redis

EMBEDDING_TTL = 24 * 60 * 60  # 24 hours
QUERY_TTL = 5 * 60  # 5 minutes


class RedisCache:
    """Hot cache with TTL support."""

    def __init__(self):
        self._redis = None

    async def _get_client(self):
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis.client

    def _hash_key(self, key: str) -> str:
        return f"emb:{hashlib.sha256(key.encode()).hexdigest()[:32]}"

    async def get_embedding(self, query: str) -> Optional[list]:
        """Get cached embedding."""
        client = await self._get_client()
        key = self._hash_key(query)
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_embedding(self, query: str, embedding: list) -> None:
        """Cache embedding with 24h TTL."""
        client = await self._get_client()
        key = self._hash_key(query)
        await client.setex(key, EMBEDDING_TTL, json.dumps(embedding))

    async def get_query_results(self, query: str) -> Optional[list]:
        """Get cached query results."""
        client = await self._get_client()
        key = f"recall:{hashlib.sha256(query.encode()).hexdigest()[:32]}"
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_query_results(self, query: str, results: list) -> None:
        """Cache query results with 5min TTL."""
        client = await self._get_client()
        key = f"recall:{hashlib.sha256(query.encode()).hexdigest()[:32]}"
        await client.setex(key, QUERY_TTL, json.dumps(results))


# Singleton
cache = RedisCache()
