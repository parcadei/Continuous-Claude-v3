"""Embedding generation service.

Phase 5: Embedding Pipeline Integration

Provides embedding generation for archival memory with:
- Multiple provider support (OpenAI, mock for testing)
- Content-based caching to avoid duplicate API calls
- Batch processing for efficiency
- Rate limiting and retry logic
- Configurable dimensions

Usage:
    # OpenAI provider (requires OPENAI_API_KEY)
    embedder = EmbeddingService(provider="openai")
    embedding = await embedder.embed("Some text to embed")

    # Mock provider (for testing, no API calls)
    embedder = EmbeddingService(provider="mock")
    embedding = await embedder.embed("Some text to embed")

    # Batch embedding
    embeddings = await embedder.embed_batch(["Text 1", "Text 2", "Text 3"])

    # With caching enabled (default)
    embedder = EmbeddingService(provider="openai", cache_enabled=True)
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from abc import ABC, abstractmethod

import httpx


class EmbeddingError(Exception):
    """Error raised when embedding generation fails."""

    pass


class EmbeddingProvider(ABC):
    """Abstract embedding provider protocol.

    All embedding providers must implement:
    - embed(text) -> list[float]: Generate embedding for text
    - dimension: int: Embedding dimension
    """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimension."""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-3-small provider.

    Uses the OpenAI embeddings API for generating embeddings.
    Requires OPENAI_API_KEY environment variable.

    Dimension: 1536 (text-embedding-3-small)
    """

    DIMENSION = 1536
    MODEL = "text-embedding-3-small"
    API_URL = "https://api.openai.com/v1/embeddings"
    DEFAULT_MAX_BATCH_SIZE = 100
    DEFAULT_MAX_RETRIES = 3
    RETRY_DELAY = 0.5  # seconds

    def __init__(
        self,
        api_key: str | None = None,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize OpenAI embedding provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            max_batch_size: Maximum texts per API call (default 100)
            max_retries: Maximum retry attempts for transient errors
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")

        self.max_batch_size = max_batch_size
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        """Close the persistent HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> OpenAIEmbeddingProvider:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args) -> None:
        """Exit async context manager and close client."""
        await self.aclose()

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (1536 dimensions)

        Raises:
            EmbeddingError: If API call fails after retries
        """
        embeddings = await self._call_api([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Automatically splits into chunks to respect API limits.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Split into chunks
        for i in range(0, len(texts), self.max_batch_size):
            chunk = texts[i : i + self.max_batch_size]
            chunk_embeddings = await self._call_api(chunk)
            all_embeddings.extend(chunk_embeddings)

        return all_embeddings

    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings API with retry logic.

        Args:
            texts: List of texts to embed (must fit in one batch)

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingError: If API call fails after retries
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    self.API_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.MODEL,
                        "input": texts if len(texts) > 1 else texts[0],
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Sort by index to preserve order
                sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in sorted_data]

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))

        raise EmbeddingError(f"API call failed after {self.max_retries} attempts: {last_error}")

    @property
    def dimension(self) -> int:
        """OpenAI text-embedding-3-small dimension."""
        return self.DIMENSION


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embedding provider.

    Supports multiple Voyage models optimized for different use cases:
    - voyage-3: General purpose (1024 dim)
    - voyage-code-3: Code understanding (1024 dim)
    - voyage-3-lite: Lightweight (512 dim)

    Requires VOYAGE_API_KEY environment variable.
    """

    MODELS = {
        "voyage-3": 1024,
        "voyage-3-large": 1024,  # Higher quality, same dims
        "voyage-code-3": 1024,
        "voyage-3-lite": 512,
    }
    API_URL = "https://api.voyageai.com/v1/embeddings"
    DEFAULT_MAX_BATCH_SIZE = 128  # Voyage supports up to 128
    DEFAULT_MAX_RETRIES = 3
    RETRY_DELAY = 0.5

    def __init__(
        self,
        model: str = "voyage-3",
        api_key: str | None = None,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize Voyage embedding provider.

        Args:
            model: Voyage model name (voyage-3, voyage-code-3, voyage-3-lite)
            api_key: Voyage API key (defaults to VOYAGE_API_KEY env var)
            max_batch_size: Maximum texts per API call (default 128)
            max_retries: Maximum retry attempts for transient errors
        """
        if model not in self.MODELS:
            raise ValueError(
                f"Unknown Voyage model: {model}. Available: {list(self.MODELS.keys())}"
            )

        self.model = model
        self._dimension = self.MODELS[model]
        self.api_key = api_key or os.environ.get("VOYAGE_API_KEY")

        if not self.api_key:
            raise ValueError("VOYAGE_API_KEY environment variable required")

        self.max_batch_size = max_batch_size
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        """Close the persistent HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> VoyageEmbeddingProvider:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args) -> None:
        """Exit async context manager and close client."""
        await self.aclose()

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self._call_api([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.max_batch_size):
            chunk = texts[i : i + self.max_batch_size]
            chunk_embeddings = await self._call_api(chunk)
            all_embeddings.extend(chunk_embeddings)

        return all_embeddings

    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call Voyage embeddings API with retry logic."""
        last_error: Exception | None = None
        last_response_text: str | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": texts,
                        "input_type": "document",
                    },
                )

                # Store response text before raising for status
                last_response_text = response.text
                response.raise_for_status()
                data = response.json()

                # Sort by index to preserve order
                sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in sorted_data]

            except httpx.HTTPStatusError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
            except Exception as e:
                last_error = e
                f"{type(e).__name__}: {str(e)}"
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))

        # Detailed error message
        error_msg = f"Voyage API call failed after {self.max_retries} attempts.\n"
        error_msg += f"Last error: {type(last_error).__name__}: {str(last_error)}\n"
        if last_response_text:
            error_msg += f"Response body: {last_response_text[:500]}"
        raise EmbeddingError(error_msg)

    @property
    def dimension(self) -> int:
        """Return model dimension."""
        return self._dimension


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding provider using sentence-transformers.

    Runs embeddings locally - no API calls, no cost, works offline.

    Supported models:
    - Qwen/Qwen3-Embedding-0.6B: SOTA MTEB 70.58, 1024 dim (RECOMMENDED)
    - BAAI/bge-large-en-v1.5: High quality, 1024 dim
    - BAAI/bge-base-en-v1.5: Good balance, 768 dim
    - all-MiniLM-L6-v2: Fast but outdated, 384 dim
    - all-mpnet-base-v2: Medium quality, 768 dim

    Default is Qwen3-Embedding-0.6B for highest quality on M4 Max.

    Requires: pip install sentence-transformers torch
    RAM: ~3-4GB for bge-large, works on 8GB+ machines
    """

    MODELS = {
        "Qwen/Qwen3-Embedding-0.6B": 1024,  # SOTA MTEB 70.58 - RECOMMENDED
        "BAAI/bge-large-en-v1.5": 1024,  # Proven quality
        "BAAI/bge-base-en-v1.5": 768,
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
    }

    def __init__(
        self,
        model: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str | None = None,
    ):
        """Initialize local embedding provider.

        Args:
            model: Model name from sentence-transformers
            device: Device to use ('cpu', 'cuda', 'mps', or None for auto)
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers required for local embeddings. "
                "Install with: pip install sentence-transformers torch"
            )

        self.model_name = model
        self._model = SentenceTransformer(model, device=device)
        self._dimension = self._model.get_sentence_embedding_dimension()

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        import asyncio

        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, lambda: self._model.encode(text, convert_to_numpy=True).tolist()
        )
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        import asyncio

        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: self._model.encode(texts, convert_to_numpy=True).tolist()
        )
        return embeddings

    @property
    def dimension(self) -> int:
        """Return model dimension."""
        return self._dimension


class RerankerProvider:
    """Cross-encoder reranker for reordering search results.

    Rerankers take query-document pairs and output relevance scores.
    Used after vector search to improve result quality.

    Supported models:
    - Qwen/Qwen3-Reranker-0.6B: Best match with Qwen3 embeddings (RECOMMENDED)
    - BAAI/bge-reranker-base: Good cross-encoder reranker
    - BAAI/bge-reranker-large: Higher quality, more memory
    - Thenlper/gte-reranker-base: GTE-based reranker

    Usage:
        reranker = RerankerProvider()
        scores = await reranker.rerank("query", ["doc1", "doc2", "doc3"])
        # scores = [0.92, 0.45, 0.31] - higher = more relevant
    """

    MODELS = {
        "Qwen/Qwen3-Reranker-0.6B": 1024,  # RECOMMENDED - matches Qwen3 embeddings
        "BAAI/bge-reranker-base": 768,
        "BAAI/bge-reranker-large": 1024,
        "Thenlper/gte-reranker-base": 768,
    }

    def __init__(
        self,
        model: str = "Qwen/Qwen3-Reranker-0.6B",
        device: str | None = None,
        batch_size: int = 32,
    ):
        """Initialize reranker provider.

        Args:
            model: Model name from sentence-transformers
            device: Device to use ('cpu', 'cuda', 'mps', or None for auto)
            batch_size: Maximum documents per batch
        """
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError(
                "sentence-transformers required for reranking. "
                "Install with: pip install sentence-transformers torch"
            )

        self.model_name = model
        self._model = CrossEncoder(
            model,
            device=device,
            trust_remote_code=True,
        )
        self.batch_size = batch_size

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Score query-document pairs for relevance.

        Args:
            query: Search query
            documents: List of documents to rerank

        Returns:
            List of relevance scores (0.0-1.0), same order as input documents
        """
        import asyncio

        # Create query-document pairs
        pairs = [[query, doc] for doc in documents]

        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None, lambda: self._model.predict(pairs, batch_size=self.batch_size)
        )

        # Normalize scores to 0-1 range if needed
        import numpy as np

        if isinstance(scores, np.ndarray):
            # Cross-encoders often output raw logits - normalize with sigmoid
            scores = 1 / (1 + np.exp(-scores))  # sigmoid

        return scores.tolist()

    async def rerank_with_scores(
        self, query: str, documents: list[str], top_k: int | None = None
    ) -> list[tuple[str, float]]:
        """Rerank documents and return sorted results.

        Args:
            query: Search query
            documents: List of documents to rerank
            top_k: Return only top k results (default: all)

        Returns:
            List of (document, score) tuples sorted by score descending
        """
        scores = await self.rerank(query, documents)

        # Sort by score descending
        sorted_results = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

        if top_k:
            sorted_results = sorted_results[:top_k]

        return sorted_results

    @property
    def dimension(self) -> int:
        """Return model dimension (for compatibility)."""
        return self.MODELS.get(self.model_name, 1024)



# Global reference for lazy import in EmbeddingService
SentenceTransformer = None


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing.

    Generates deterministic embeddings based on text hash.
    No API calls required.

    Features:
    - Same text always returns same embedding
    - Different texts return different embeddings
    - Configurable dimension
    """

    DEFAULT_DIMENSION = 1536

    def __init__(self, dimension: int = DEFAULT_DIMENSION):
        """Initialize mock provider.

        Args:
            dimension: Embedding dimension (default 1536 to match OpenAI)
        """
        self._dimension = dimension

    async def embed(self, text: str) -> list[float]:
        """Generate deterministic embedding from text hash.

        Args:
            text: Text to embed

        Returns:
            Deterministic embedding vector based on text hash
        """
        # Create deterministic embedding from hash
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Generate embedding values from hash
        embedding = []
        for i in range(self._dimension):
            # Use different parts of hash for each dimension
            byte_idx = i % 32
            byte_val = int(text_hash[byte_idx * 2 : byte_idx * 2 + 2], 16)
            # Normalize to [-1, 1] range with some variation
            normalized = ((byte_val + i) % 256) / 255.0 * 2 - 1
            embedding.append(normalized)

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        return [await self.embed(text) for text in texts]

    @property
    def dimension(self) -> int:
        """Return configured dimension."""
        return self._dimension


class EmbeddingService:
    """Embedding service with caching and provider abstraction.

    Main entry point for generating embeddings. Supports:
    - Multiple providers (OpenAI, mock)
    - Content-based caching
    - Batch processing
    - Configurable retry logic

    Implements EmbeddingProvider protocol for use with MemoryServicePG.

    Usage:
        # OpenAI (production)
        service = EmbeddingService(provider="openai")

        # Mock (testing)
        service = EmbeddingService(provider="mock")

        # With caching
        service = EmbeddingService(provider="openai", cache_enabled=True)

        # Generate embedding
        embedding = await service.embed("Some text")
    """

    def __init__(
        self,
        provider: str = "local",
        cache_enabled: bool = True,
        dimension: int | None = None,
        max_batch_size: int = 100,
        max_retries: int = 3,
        model: str | None = None,
        **kwargs,
    ):
        """Initialize embedding service.

        Args:
            provider: Provider name ("openai", "mock", "voyage", or model name like "voyage-3")
            cache_enabled: Enable content-based caching (default True)
            dimension: Override dimension (only for mock provider)
            max_batch_size: Maximum texts per batch API call
            max_retries: Maximum retry attempts for transient errors
            model: Model name for provider (e.g., "voyage-3", "voyage-code-3")
            **kwargs: Additional provider-specific arguments
        """
        self.cache_enabled = cache_enabled
        self._cache: dict[str, list[float]] = {}
        self._cache_lock = asyncio.Lock()
        self.max_batch_size = max_batch_size
        self.max_retries = max_retries

        # Initialize provider
        if provider == "openai":
            self._provider = OpenAIEmbeddingProvider(
                max_batch_size=max_batch_size,
                max_retries=max_retries,
            )
        elif provider == "mock":
            dim = dimension if dimension is not None else MockEmbeddingProvider.DEFAULT_DIMENSION
            self._provider = MockEmbeddingProvider(dimension=dim)
        elif provider == "voyage":
            voyage_model = model if model is not None else "voyage-3"
            self._provider = VoyageEmbeddingProvider(
                model=voyage_model,
                max_batch_size=max_batch_size,
                max_retries=max_retries,
            )
        elif provider.startswith("voyage-"):
            # Allow provider="voyage-3" shorthand
            self._provider = VoyageEmbeddingProvider(
                model=provider,
                max_batch_size=max_batch_size,
                max_retries=max_retries,
            )
        elif provider == "local":
            local_model = model if model is not None else "Qwen/Qwen3-Embedding-0.6B"
            device = kwargs.get("device", None)
            self._provider = LocalEmbeddingProvider(model=local_model, device=device)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text with optional caching.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if self.cache_enabled:
            cache_key = self._cache_key(text)
            async with self._cache_lock:
                if cache_key in self._cache:
                    return self._cache[cache_key]

        embedding = await self._provider.embed(text)

        if self.cache_enabled:
            async with self._cache_lock:
                self._cache[self._cache_key(text)] = embedding

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Uses caching for already-seen texts and batches remaining.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (same order as input)
        """
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []

        # Check cache first
        async with self._cache_lock:
            for i, text in enumerate(texts):
                if self.cache_enabled:
                    cache_key = self._cache_key(text)
                    if cache_key in self._cache:
                        results[i] = self._cache[cache_key]
                        continue
                texts_to_embed.append((i, text))

        # Embed remaining texts (outside lock - allows concurrent API calls)
        if texts_to_embed:
            indices, remaining_texts = zip(*texts_to_embed)
            new_embeddings = await self._provider.embed_batch(list(remaining_texts))

            async with self._cache_lock:
                for idx, text, embedding in zip(indices, remaining_texts, new_embeddings):
                    results[idx] = embedding
                    if self.cache_enabled:
                        self._cache[self._cache_key(text)] = embedding

        # All results should be filled now
        return [r for r in results if r is not None]

    @property
    def dimension(self) -> int:
        """Get embedding dimension from provider."""
        return self._provider.dimension

    def _cache_key(self, text: str) -> str:
        """Generate cache key from text content hash.

        Args:
            text: Text to hash

        Returns:
            SHA-256 hash of text
        """
        return hashlib.sha256(text.encode()).hexdigest()

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    def cache_size(self) -> int:
        """Get number of cached embeddings."""
        return len(self._cache)

    async def aclose(self) -> None:
        """Close the underlying provider's client."""
        if hasattr(self._provider, "aclose"):
            await self._provider.aclose()

    async def __aenter__(self) -> EmbeddingService:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args) -> None:
        """Exit async context manager and close provider."""
        await self.aclose()
