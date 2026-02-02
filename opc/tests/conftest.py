"""Shared test fixtures for OPC test suite.

Provides:
- Mock embedding service with deterministic output
- Test database fixtures
- Common test data
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

opc_root = Path(__file__).parent.parent
sys.path.insert(0, str(opc_root))
sys.path.insert(0, str(opc_root / "scripts" / "core"))


class MockEmbeddingService:
    """Deterministic mock embedding service for reproducible tests.

    Uses content hash to generate consistent embeddings - same input always
    produces same output, making tests predictable.
    """

    def __init__(self, dimension: int = 1024, provider: str = "mock"):
        self.dimension = dimension
        self.provider = provider
        self._calls: list[str] = []

    def _deterministic_embedding(self, text: str) -> list[float]:
        """Generate deterministic embedding from text hash."""
        h = hashlib.sha256(text.encode()).digest()
        embedding = []
        for i in range(self.dimension):
            byte_idx = i % len(h)
            embedding.append(((h[byte_idx] + i) % 256) / 255.0)
        return embedding

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        self._calls.append(text)
        return self._deterministic_embedding(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [await self.embed(t) for t in texts]

    async def aclose(self) -> None:
        """Cleanup (no-op for mock)."""
        pass

    @property
    def calls(self) -> list[str]:
        """Return list of texts that were embedded."""
        return self._calls.copy()


@pytest.fixture
def mock_embedder():
    """Provide a mock embedding service."""
    return MockEmbeddingService()


@pytest.fixture
def mock_pool():
    """Provide a mock database connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    pool.acquire.return_value.__aexit__.return_value = None
    return pool, conn


def make_learning(
    content: str,
    learning_type: str = "WORKING_SOLUTION",
    session_id: str = "test-session",
    created_at: datetime | None = None,
    similarity: float = 0.5,
    embedding: list[float] | None = None,
    **metadata_extras,
) -> dict[str, Any]:
    """Create a mock learning record for tests."""
    if created_at is None:
        created_at = datetime.now()

    metadata = {
        "type": learning_type,
        "context": metadata_extras.get("context", "test context"),
        "tags": metadata_extras.get("tags", ["test"]),
        "confidence": metadata_extras.get("confidence", "high"),
    }
    metadata.update(metadata_extras)

    return {
        "id": hashlib.md5(content.encode()).hexdigest()[:8],
        "session_id": session_id,
        "content": content,
        "metadata": metadata,
        "created_at": created_at,
        "similarity": similarity,
        "embedding": embedding or MockEmbeddingService()._deterministic_embedding(content),
    }


@pytest.fixture
def sample_learnings() -> list[dict[str, Any]]:
    """Provide sample learning records for tests."""
    now = datetime.now()
    return [
        make_learning(
            "TypeScript hooks require npm install before they work",
            "ERROR_FIX",
            created_at=now - timedelta(hours=1),
            similarity=0.8,
            tags=["hooks", "typescript"],
        ),
        make_learning(
            "Always use session isolation for cross-terminal state",
            "ARCHITECTURAL_DECISION",
            created_at=now - timedelta(hours=2),
            similarity=0.7,
            tags=["architecture", "sessions"],
        ),
        make_learning(
            "The file-claims hook uses PostgreSQL for coordination",
            "CODEBASE_PATTERN",
            created_at=now - timedelta(days=1),
            similarity=0.6,
            tags=["hooks", "database"],
        ),
        make_learning(
            "Using ILIKE for text fallback when embeddings unavailable",
            "WORKING_SOLUTION",
            created_at=now - timedelta(days=2),
            similarity=0.5,
            tags=["search", "database"],
        ),
        make_learning(
            "Tried using setTimeout for debouncing - caused race conditions",
            "FAILED_APPROACH",
            created_at=now - timedelta(days=3),
            similarity=0.4,
            tags=["javascript", "async"],
        ),
    ]


@pytest.fixture
def env_postgres(monkeypatch):
    """Set environment for PostgreSQL backend."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    monkeypatch.delenv("AGENTICA_MEMORY_BACKEND", raising=False)


@pytest.fixture
def env_sqlite(monkeypatch):
    """Set environment for SQLite backend."""
    monkeypatch.setenv("AGENTICA_MEMORY_BACKEND", "sqlite")
    monkeypatch.delenv("DATABASE_URL", raising=False)


class MockRecord:
    """Mock asyncpg Record for testing."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def values(self) -> list[Any]:
        return list(self._data.values())

    def items(self) -> list[tuple[str, Any]]:
        return list(self._data.items())


def make_db_row(learning: dict[str, Any], **overrides) -> MockRecord:
    """Convert learning dict to mock database row."""
    data = {
        "id": learning["id"],
        "session_id": learning["session_id"],
        "content": learning["content"],
        "metadata": json.dumps(learning["metadata"]) if isinstance(learning["metadata"], dict) else learning["metadata"],
        "created_at": learning["created_at"],
        "similarity": learning.get("similarity", 0.5),
    }
    data.update(overrides)
    return MockRecord(data)
