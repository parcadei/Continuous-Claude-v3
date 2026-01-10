"""Simple embeddings client with Jina v3.

Fallback chain: Jina v3 → Local BGE → Mock

Usage:
    embedder = Embedder()
    embedding = await embedder.embed("text")
    embeddings = await embedder.embed_batch(["text1", "text2"])
"""

import os
import hashlib
from typing import Literal

import httpx


TaskType = Literal[
    "retrieval.query",
    "retrieval.passage",
    "text-matching",
]


class Embedder:
    """Minimal embedder with Jina v3 and fallbacks."""

    def __init__(
        self,
        provider: str = "auto",  # "jina", "local", "mock", "auto"
        dimension: int = 1024,
        task: TaskType = "retrieval.passage",
    ):
        self.dimension = dimension
        self.task = task
        self._provider = self._select_provider(provider)
        self._client = httpx.AsyncClient(timeout=30.0)

    def _select_provider(self, provider: str) -> str:
        if provider != "auto":
            return provider

        # Auto-select based on available API keys
        if os.environ.get("JINA_API_KEY"):
            return "jina"

        # Try local embeddings
        try:
            from sentence_transformers import SentenceTransformer
            return "local"
        except ImportError:
            pass

        return "mock"

    async def embed(self, text: str, task: TaskType | None = None) -> list[float]:
        """Embed single text."""
        if self._provider == "jina":
            return await self._embed_jina(text, task or self.task)
        elif self._provider == "local":
            return await self._embed_local(text)
        else:
            return self._embed_mock(text)

    async def embed_batch(self, texts: list[str], task: TaskType | None = None) -> list[list[float]]:
        """Embed multiple texts."""
        if self._provider == "jina":
            return await self._embed_jina_batch(texts, task or self.task)
        elif self._provider == "local":
            return [await self._embed_local(t) for t in texts]
        else:
            return [self._embed_mock(t) for t in texts]

    # =========================================================================
    # Jina v3
    # =========================================================================

    async def _embed_jina(self, text: str, task: TaskType) -> list[float]:
        """Embed with Jina v3 API."""
        api_key = os.environ.get("JINA_API_KEY")
        if not api_key:
            raise ValueError("JINA_API_KEY required")

        response = await self._client.post(
            "https://api.jina.ai/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": [text],
                "model": "jina-embeddings-v3",
                "dimensions": self.dimension,
                "task": task,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    async def _embed_jina_batch(self, texts: list[str], task: TaskType) -> list[list[float]]:
        """Batch embed with Jina v3 API."""
        api_key = os.environ.get("JINA_API_KEY")
        if not api_key:
            raise ValueError("JINA_API_KEY required")

        response = await self._client.post(
            "https://api.jina.ai/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": texts,
                "model": "jina-embeddings-v3",
                "dimensions": self.dimension,
                "task": task,
            },
        )
        response.raise_for_status()
        data = response.json()
        # Sort by index to preserve order
        sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in sorted_data]

    # =========================================================================
    # Local BGE
    # =========================================================================

    async def _embed_local(self, text: str) -> list[float]:
        """Embed with local sentence-transformers."""
        import asyncio
        from sentence_transformers import SentenceTransformer

        if not hasattr(self, "_local_model"):
            self._local_model = SentenceTransformer("BAAI/bge-large-en-v1.5")

        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, lambda: self._local_model.encode(text).tolist()
        )
        return embedding

    # =========================================================================
    # Mock (for testing)
    # =========================================================================

    def _embed_mock(self, text: str) -> list[float]:
        """Deterministic mock embedding from text hash."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        embedding = []
        for i in range(self.dimension):
            byte_idx = i % 32
            byte_val = int(text_hash[byte_idx * 2 : byte_idx * 2 + 2], 16)
            normalized = ((byte_val + i) % 256) / 255.0 * 2 - 1
            embedding.append(normalized)
        return embedding

    async def close(self):
        await self._client.aclose()


# Quick test
async def _test():
    embedder = Embedder()
    print(f"Provider: {embedder._provider}")

    embedding = await embedder.embed("Hello world")
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")

    await embedder.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
