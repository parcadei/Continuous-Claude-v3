"""Agent scope with memory and task functions.

Provides create_agent_scope() that returns a scope dict with:
- Memory functions: remember(), recall(), search_memory(), store_fact()
- Task functions: create_task(), complete_task(), get_ready_tasks(), get_all_tasks()
- Session isolation via session_id

Optional vector-enhanced memory operations (when enable_vector_memory=True):
- recall_vector(): Embed query, search via vector similarity, optionally rerank
- remember_with_embedding(): Store fact with embedding for vector search

Usage:
    scope = create_agent_scope(session_id="abc123")
    agent = await spawn(premise="...", scope=scope)

    # Agent can now use:
    # scope["remember"](key, value)
    # scope["recall"](query)
    # scope["create_task"](description)

    # With vector-enhanced memory:
    scope = create_agent_scope(
        session_id="abc123",
        enable_vector_memory=True,
        embedding_provider="mock",
    )
    # scope["recall_vector"]("query", top_k=5)
"""

from pathlib import Path
from typing import Any, Optional

from scripts.agentica_patterns.memory_service import MemoryService
from scripts.agentica_patterns.beads_task_graph import BeadsTaskGraph
from scripts.agentica_patterns.unified_scope import _run_async


def create_agent_scope(
    session_id: str = "default",
    db_path: Optional[Path] = None,
    include_memory: bool = True,
    include_tasks: bool = True,
    extra_scope: Optional[dict[str, Any]] = None,
    enable_vector_memory: bool = False,
    embedding_provider: str | None = None,
    enable_reranking: bool = False,
    reranker_provider: str = "local",
) -> dict[str, Any]:
    """Create an agent scope with memory and task functions.

    Args:
        session_id: Session identifier for isolation
        db_path: Optional custom database path
        include_memory: Whether to include memory functions
        include_tasks: Whether to include task functions
        extra_scope: Additional scope items to include
        enable_vector_memory: Whether to include vector-enhanced memory functions
        embedding_provider: Embedding provider ("openai", "voyage", "local", "mock")
        enable_reranking: Whether to enable cross-encoder reranking
        reranker_provider: Reranker provider ("local" or "cohere")

    Returns:
        Scope dict with callable functions
    """
    scope: dict[str, Any] = {}

    if include_memory:
        memory = MemoryService(session_id=session_id, db_path=db_path)
        # Initialize schema
        _run_async(memory.connect())

        def remember(key: str, value: str) -> None:
            """Store a fact in memory."""
            _run_async(memory.set_core(key, value))

        def recall(query: str) -> str:
            """Recall information from memory."""
            return _run_async(memory.recall(query))

        def search_memory(query: str, limit: int = 10) -> list[dict[str, Any]]:
            """Search archival memory."""
            return _run_async(memory.search(query, limit=limit))

        def store_fact(content: str) -> str:
            """Store a fact in archival memory."""
            return _run_async(memory.store(content))

        scope["remember"] = remember
        scope["recall"] = recall
        scope["search_memory"] = search_memory
        scope["store_fact"] = store_fact
        scope["_memory_service"] = memory  # For advanced access

    # Add vector-enhanced memory operations if enabled
    if enable_vector_memory and include_memory:
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        provider = embedding_provider or "mock"
        embedder = EmbeddingService(provider=provider)

        reranker = None
        if enable_reranking:
            from scripts.agentica_patterns.reranker import get_reranker

            reranker = get_reranker(reranker_provider)

        def recall_vector(
            query: str,
            top_k: int = 5,
            use_reranking: bool | None = None,
        ) -> list[dict[str, Any]]:
            """Recall facts using vector similarity search.

            Args:
                query: Natural language query to search for
                top_k: Number of results to return (default: 5)
                use_reranking: Override default reranking

            Returns:
                List of dicts with keys: content, score, metadata
            """

            async def _recall_vector_async() -> list[dict[str, Any]]:
                query_embedding = await embedder.embed(query)

                if hasattr(memory, "search_vector"):
                    raw_results = await memory.search_vector(
                        query_embedding, limit=top_k * 3 if reranker else top_k
                    )
                else:
                    raw_results = await memory.search(query, limit=top_k * 3)
                    for r in raw_results:
                        if "similarity" not in r:
                            r["similarity"] = r.get("score", 0.5)

                should_rerank = (
                    use_reranking if use_reranking is not None else enable_reranking
                )
                if should_rerank and reranker and raw_results:
                    documents = [r["content"] for r in raw_results]
                    reranked = await reranker.rerank(query, documents, top_k=top_k)

                    results = []
                    for ranked in reranked:
                        original = raw_results[ranked.original_rank]
                        results.append({
                            "content": ranked.content,
                            "score": ranked.score,
                            "similarity": original.get("similarity", 0.0),
                            "metadata": original.get("metadata", {}),
                            "id": original.get("id"),
                        })
                    return results
                else:
                    return [
                        {
                            "content": r["content"],
                            "score": r.get("similarity", r.get("score", 0.0)),
                            "similarity": r.get("similarity", 0.0),
                            "metadata": r.get("metadata", {}),
                            "id": r.get("id"),
                        }
                        for r in raw_results[:top_k]
                    ]

            return _run_async(_recall_vector_async())

        def remember_with_embedding(
            content: str,
            metadata: dict[str, Any] | None = None,
        ) -> str:
            """Store a fact with embedding for vector search."""

            async def _remember_async() -> str:
                embedding = await embedder.embed(content)
                return await memory.store(content, metadata=metadata, embedding=embedding)

            return _run_async(_remember_async())

        scope["recall_vector"] = recall_vector
        scope["remember_with_embedding"] = remember_with_embedding
        scope["_embedding_service"] = embedder
        if reranker:
            scope["_reranker"] = reranker

    if include_tasks:
        tasks = BeadsTaskGraph(session_id=session_id, db_path=db_path)

        def create_task(
            description: str, blocks: Optional[list[str]] = None, **kwargs: Any
        ) -> str:
            """Create a task."""
            return tasks.add_task(description, blocks=blocks, **kwargs)

        def complete_task(task_id: str) -> None:
            """Mark a task as completed."""
            tasks.complete_task(task_id)

        def get_ready_tasks() -> list[str]:
            """Get tasks that are ready to execute."""
            return tasks.get_ready_tasks()

        def get_all_tasks() -> list[dict[str, Any]]:
            """Get all tasks."""
            return tasks.get_all_tasks()

        scope["create_task"] = create_task
        scope["complete_task"] = complete_task
        scope["get_ready_tasks"] = get_ready_tasks
        scope["get_all_tasks"] = get_all_tasks
        scope["_task_graph"] = tasks  # For advanced access

    # Include any extra scope items
    if extra_scope:
        scope.update(extra_scope)

    return scope
