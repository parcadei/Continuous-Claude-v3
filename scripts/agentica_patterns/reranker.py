"""Cross-encoder re-ranker for semantic search.

Provides two-stage retrieval pattern:
1. Fast vector search retrieves broad candidate set (top_k=50-100)
2. Expensive reranking with cross-encoder returns precise results (top_n=5-20)

Supports:
- Local cross-encoder models via sentence-transformers
- Cohere rerank API for cloud-based ranking

Usage:
    # Local reranker
    reranker = get_reranker("local")
    results = await reranker.rerank(query, documents, top_k=10)

    # Cohere API reranker
    reranker = get_reranker("cohere", api_key="...")
    results = await reranker.rerank(query, documents, top_k=10)
"""

import asyncio
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class RankedDocument:
    """A document with its reranking score.

    Attributes:
        content: Document text
        score: Relevance score (higher = more relevant)
        original_rank: Original position in input list
        metadata: Optional metadata dict
    """

    content: str
    score: float
    original_rank: int
    metadata: dict[str, Any] | None = None


class Reranker(ABC):
    """Abstract reranker protocol.

    Implementations must provide async rerank() method that scores
    documents by relevance to a query.
    """

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[RankedDocument]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of document texts to rank
            top_k: Optional limit on number of results (default: return all)

        Returns:
            List of RankedDocument sorted by score (descending)
        """
        ...


class CrossEncoderReranker(Reranker):
    """Local cross-encoder reranker using sentence-transformers.

    Uses a pre-trained cross-encoder model to score query-document pairs.
    Runs inference in a thread pool to avoid blocking async event loop.

    Default model: cross-encoder/ms-marco-MiniLM-L-12-v2
    - Speed: ~250ms for 100 docs on CPU (M2)
    - Quality: NDCG@10 = 0.407
    - Size: ~500MB in memory

    Attributes:
        model: CrossEncoder model instance
        executor: ThreadPoolExecutor for CPU-bound inference
    """

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        max_workers: int = 4,
    ):
        """Initialize cross-encoder reranker.

        Args:
            model_name: HuggingFace model ID
            max_workers: Thread pool size for inference

        Raises:
            ImportError: If sentence-transformers not installed
        """
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise ImportError(
                "sentence-transformers required for CrossEncoderReranker. "
                "Install with: pip install sentence-transformers"
            ) from e

        self.model = CrossEncoder(model_name)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def _predict_sync(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        """Synchronous inference method (runs in thread pool).

        Args:
            query: Search query
            documents: List of document texts

        Returns:
            List of relevance scores
        """
        pairs = [[query, doc] for doc in documents]
        scores = self.model.predict(pairs)
        return scores.tolist()

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[RankedDocument]:
        """Rerank documents using cross-encoder model.

        Args:
            query: Search query
            documents: List of document texts to rank
            top_k: Optional limit on number of results

        Returns:
            List of RankedDocument sorted by score (descending)

        Raises:
            ValueError: If top_k is negative
        """
        # Validate top_k
        if top_k is not None and top_k < 0:
            raise ValueError(f"top_k must be non-negative, got {top_k}")

        # Handle empty documents or top_k=0
        if not documents or top_k == 0:
            return []

        # Filter out whitespace-only documents
        filtered_docs = []
        original_indices = []
        for idx, doc in enumerate(documents):
            if doc.strip():  # Only include non-whitespace documents
                filtered_docs.append(doc)
                original_indices.append(idx)

        # If all documents were whitespace, return empty
        if not filtered_docs:
            return []

        # Run inference in thread pool
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            self.executor,
            self._predict_sync,
            query,
            filtered_docs,
        )

        # Sort by score descending with original rank
        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )

        # Apply top_k limit
        if top_k is not None:
            ranked = ranked[:top_k]

        # Map to RankedDocument with original indices
        return [
            RankedDocument(
                content=filtered_docs[idx],
                score=float(score),
                original_rank=original_indices[idx],
            )
            for idx, score in ranked
        ]


class CohereReranker(Reranker):
    """Cohere API reranker.

    Uses Cohere's rerank API for high-quality document ranking.
    Requires COHERE_API_KEY environment variable.

    Default model: rerank-english-v3.0
    - Handles up to 4096 tokens per document
    - Returns scores 0-1 (higher = more relevant)
    - Billed per search unit (1 query against up to 100 docs)

    Attributes:
        api_key: Cohere API key
        model: Model ID to use
        api_url: Cohere rerank endpoint
        timeout: HTTP request timeout in seconds
    """

    API_URL = "https://api.cohere.ai/v1/rerank"
    DEFAULT_MODEL = "rerank-english-v3.0"
    DEFAULT_TIMEOUT = 30.0  # 30 second timeout

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """Initialize Cohere reranker.

        Args:
            api_key: Cohere API key (defaults to COHERE_API_KEY env var)
            model: Model ID to use
            timeout: Request timeout in seconds (default: 30.0)

        Raises:
            ValueError: If api_key not provided and COHERE_API_KEY not set
        """
        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Cohere API key required. Set COHERE_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self.model = model
        self.api_url = self.API_URL
        self.timeout = timeout

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[RankedDocument]:
        """Rerank documents using Cohere API.

        Args:
            query: Search query
            documents: List of document texts to rank
            top_k: Optional limit on number of results

        Returns:
            List of RankedDocument sorted by score (descending)

        Raises:
            ValueError: If top_k is negative
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If API returns error status code
            httpx.RequestError: If connection fails
        """
        # Validate top_k
        if top_k is not None and top_k < 0:
            raise ValueError(f"top_k must be non-negative, got {top_k}")

        # Handle empty documents or top_k=0
        if not documents or top_k == 0:
            return []

        # Filter out whitespace-only documents
        filtered_docs = []
        original_indices = []
        for idx, doc in enumerate(documents):
            if doc.strip():  # Only include non-whitespace documents
                filtered_docs.append(doc)
                original_indices.append(idx)

        # If all documents were whitespace, return empty
        if not filtered_docs:
            return []

        # Build request payload
        payload = {
            "model": self.model,
            "query": query,
            "documents": filtered_docs,
        }

        # Add top_n if specified
        if top_k is not None:
            payload["top_n"] = top_k

        # Call Cohere API with timeout
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        # Parse response
        results = data.get("results", [])

        # Map to RankedDocument with original indices
        return [
            RankedDocument(
                content=filtered_docs[result["index"]],
                score=result["relevance_score"],
                original_rank=original_indices[result["index"]],
            )
            for result in results
        ]


def get_reranker(provider: str = "local", **kwargs) -> Reranker:
    """Factory function for creating rerankers.

    Args:
        provider: "local" or "cohere"
        **kwargs: Provider-specific arguments
            For "local":
                - model_name: HuggingFace model ID
                - max_workers: Thread pool size
            For "cohere":
                - api_key: Cohere API key
                - model: Cohere model ID

    Returns:
        Reranker instance

    Raises:
        ValueError: Unknown provider

    Examples:
        # Local reranker
        reranker = get_reranker("local")

        # Cohere reranker
        reranker = get_reranker("cohere", api_key="sk-...")

        # Custom local model
        reranker = get_reranker(
            "local",
            model_name="BAAI/bge-reranker-large"
        )
    """
    if provider == "local":
        return CrossEncoderReranker(**kwargs)
    elif provider == "cohere":
        return CohereReranker(**kwargs)
    else:
        raise ValueError(
            f"Unknown reranker provider: {provider}. "
            f"Valid options: 'local', 'cohere'"
        )
