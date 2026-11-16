"""Memory backend Protocol definition.

Defines the contract that all memory service backends must implement.
Uses Protocol for structural typing (duck typing with type checking).

Both SQLite and PostgreSQL implementations satisfy this protocol.
"""

from typing import Any, Protocol


class MemoryBackend(Protocol):
    """Protocol for memory service backends.

    Defines the async interface that all backends must implement.
    Uses structural typing - no need to inherit from this class.

    Backends implementing this protocol:
    - SQLite (scripts.agentica.memory_service)
    - PostgreSQL (scripts.agentica.memory_service_pg)
    """

    # Core Memory Operations
    async def set_core(self, key: str, value: str) -> None:
        """Set a core memory block.

        Args:
            key: Memory block identifier
            value: Memory block content

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def get_core(self, key: str) -> str | None:
        """Get a core memory block.

        Args:
            key: Memory block identifier

        Returns:
            Memory block content if exists, None otherwise

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def list_core_keys(self) -> list[str]:
        """List all core memory block keys.

        Returns:
            List of core memory keys

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def delete_core(self, key: str) -> None:
        """Delete a core memory block.

        Args:
            key: Memory block identifier

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def get_all_core(self) -> dict[str, str]:
        """Get all core memory blocks.

        Returns:
            Dictionary mapping keys to values

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    # Archival Memory Operations
    async def store(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> str:
        """Store content in archival memory.

        Args:
            content: Content to store
            metadata: Optional metadata dictionary
            embedding: Optional embedding vector

        Returns:
            Memory ID (UUID)

        Raises:
            ConnectionError: If database unavailable
            ValueError: If content is empty
        """
        ...

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search archival memory (full-text search).

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching memories with metadata

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def delete_archival(self, memory_id: str) -> None:
        """Delete an archival memory entry.

        Args:
            memory_id: Memory ID to delete

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    # Recall Operations
    async def recall(
        self,
        query: str,
        include_core: bool = True,
        limit: int = 5,
    ) -> str:
        """Recall relevant memories for a query.

        Combines archival search with optional core memory inclusion.

        Args:
            query: Query string
            include_core: Whether to include core memory in results
            limit: Max archival memories to retrieve

        Returns:
            Formatted context string

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def to_context(self, max_archival: int = 10) -> str:
        """Convert memory state to context string.

        Args:
            max_archival: Maximum archival memories to include

        Returns:
            Formatted context string with core and archival memory

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    # Lifecycle Management
    async def connect(self) -> None:
        """Initialize backend connection.

        Should be idempotent - safe to call multiple times.

        Raises:
            ConnectionError: If connection fails
        """
        ...

    async def close(self) -> None:
        """Close backend connection and cleanup resources.

        Should be idempotent - safe to call multiple times.
        """
        ...
