"""
ResourcePool - Semaphore-based pool for controlling concurrent agent execution.

Provides managed resource slots with timeout-based acquisition and
automatic release via context manager protocol.

Usage:
    pool = ResourcePool(max_concurrent_agents=4, acquire_timeout=30.0)

    # Context manager (recommended)
    async with await pool.acquire() as handle:
        # Do work while holding resource slot
        pass
    # Automatically released

    # Manual acquire/release
    handle = await pool.acquire(timeout=5.0)
    try:
        # Do work
    finally:
        await pool.release(handle)

    # Health monitoring
    healthy = await pool.check_health()
    metrics = pool.get_metrics()
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4


# ============================================================================
# Exceptions
# ============================================================================


class ResourceExhaustedError(Exception):
    """Raised when acquire times out waiting for resource slot.

    Attributes:
        timeout: The timeout that was exceeded
        active_handles: Number of handles held at time of timeout
    """

    def __init__(self, timeout: float, active_handles: int):
        self.timeout = timeout
        self.active_handles = active_handles
        super().__init__(
            f"Resource pool exhausted: timeout {timeout}s with {active_handles} active handles"
        )


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ResourceMetrics:
    """Metrics for pool monitoring and health checks.

    Attributes:
        max_concurrent: Maximum concurrent acquisitions allowed
        active: Currently held handles
        total_acquisitions: Lifetime acquisition count
        total_releases: Lifetime release count
        denied_due_to_timeout: Acquisitions that timed out
    """

    max_concurrent: int
    active: int
    total_acquisitions: int
    total_releases: int
    denied_due_to_timeout: int


@dataclass
class ResourceHandle:
    """Handle to an acquired resource slot.

    Supports async context manager protocol for automatic release.

    Attributes:
        resource_id: Unique identifier for this acquisition
        acquired_at: Timestamp when resource was acquired
        pool: Back-reference to owning pool for release
    """

    resource_id: str
    acquired_at: datetime
    pool: "ResourcePool"

    async def __aenter__(self) -> "ResourceHandle":
        """Enter context - handle already acquired."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context - release handle back to pool."""
        await self.pool.release(self)


# ============================================================================
# ResourcePool
# ============================================================================


class ResourcePool:
    """Semaphore-based pool for controlling concurrent agent execution.

    Thread-safe for concurrent acquire/release operations.
    Uses asyncio.Semaphore for concurrency control.

    Attributes:
        max_concurrent_agents: Maximum concurrent handles allowed
        acquire_timeout: Default timeout for acquire operations
    """

    def __init__(
        self,
        max_concurrent_agents: int = 4,
        acquire_timeout: float = 30.0,
    ):
        """Initialize pool with concurrency limit.

        Args:
            max_concurrent_agents: Maximum concurrent handles (default 4)
            acquire_timeout: Default timeout for acquire() in seconds (default 30)
        """
        self._max_concurrent = max_concurrent_agents
        self._default_timeout = acquire_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent_agents)
        self._active_handles: dict[str, ResourceHandle] = {}
        self._lock = asyncio.Lock()  # Protects _active_handles and metrics

        # Metrics counters
        self._total_acquisitions = 0
        self._total_releases = 0
        self._denied_due_to_timeout = 0

    async def acquire(self, timeout: float | None = None) -> ResourceHandle:
        """Acquire a resource slot with optional timeout.

        Blocks until a slot is available or timeout is exceeded.
        Returns a ResourceHandle that can be used as an async context manager.

        Args:
            timeout: Override default timeout in seconds (None uses default)

        Returns:
            ResourceHandle that must be released via release() or context manager

        Raises:
            ResourceExhaustedError: If timeout exceeded while waiting
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout

        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            async with self._lock:
                self._denied_due_to_timeout += 1
            raise ResourceExhaustedError(
                timeout=effective_timeout,
                active_handles=len(self._active_handles),
            )

        # Create handle with unique ID
        handle = ResourceHandle(
            resource_id=str(uuid4()),
            acquired_at=datetime.now(),
            pool=self,
        )

        # Track handle and update metrics
        async with self._lock:
            self._active_handles[handle.resource_id] = handle
            self._total_acquisitions += 1

        return handle

    async def release(self, handle: ResourceHandle) -> None:
        """Release a resource handle back to the pool.

        Idempotent - releasing an already-released handle is a no-op.
        Safe to call even if the handle was acquired from a different pool
        (will be a no-op in that case).

        Args:
            handle: The ResourceHandle to release
        """
        async with self._lock:
            if handle.resource_id not in self._active_handles:
                # Already released or from different pool (idempotent)
                return

            del self._active_handles[handle.resource_id]
            self._total_releases += 1

        # Release semaphore after updating state
        self._semaphore.release()

    async def check_health(self) -> bool:
        """Check if pool is healthy (not saturated).

        Returns True if pool has at least one available slot.
        This is useful for health checks and load balancing decisions.

        Returns:
            True if pool has available capacity, False if saturated
        """
        async with self._lock:
            return len(self._active_handles) < self._max_concurrent

    def get_metrics(self) -> ResourceMetrics:
        """Get current pool metrics.

        Returns a snapshot of current metrics state.
        This is a synchronous method for compatibility with monitoring systems.

        Returns:
            ResourceMetrics with current values
        """
        return ResourceMetrics(
            max_concurrent=self._max_concurrent,
            active=len(self._active_handles),
            total_acquisitions=self._total_acquisitions,
            total_releases=self._total_releases,
            denied_due_to_timeout=self._denied_due_to_timeout,
        )

    async def force_release_all(self) -> int:
        """Force release all active handles.

        Used for cleanup on failure or shutdown.
        Returns the number of handles that were released.

        Returns:
            Number of handles that were force-released
        """
        released_count = 0
        async with self._lock:
            for handle_id in list(self._active_handles.keys()):
                del self._active_handles[handle_id]
                self._semaphore.release()
                self._total_releases += 1
                released_count += 1
        return released_count
