"""
Dynamic Resource Allocation for Multi-Agent Workflows.

Provides time-windowed P95 memory estimates, adaptive max_agents calculation,
and circuit breaker integration for resource exhaustion scenarios.

Usage:
    # Get adaptive estimate
    from scripts.agentica_patterns.dynamic_resources import (
        get_estimate_adaptive, DynamicAllocator
    )
    from scripts.resource_profiler import ResourceProfiler

    profiler = ResourceProfiler()
    estimate, source = get_estimate_adaptive(profiler, "sonnet")

    # Dynamic allocation
    allocator = DynamicAllocator(profiler)
    allocation = allocator.calculate_max_agents(model="sonnet")
    print(f"Max agents: {allocation.max_agents} (source: {allocation.source})")

    # Circuit breaker
    breaker = ResourceCircuitBreaker(allocator)
    can_spawn, reason = await breaker.can_spawn()
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from scripts.agentica_patterns.resource_pool import ResourceHandle, ResourceMetrics

# Handle imports for both module and script execution
try:
    from scripts.validate_resources import (
        MODEL_MEMORY_MB,
        DEFAULT_MODEL,
        get_system_resources,
    )
    from scripts.resource_profiler import ResourceProfiler, MIN_SAMPLES_FOR_P95
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from scripts.validate_resources import (
        MODEL_MEMORY_MB,
        DEFAULT_MODEL,
        get_system_resources,
    )
    from scripts.resource_profiler import ResourceProfiler, MIN_SAMPLES_FOR_P95


# ============================================================================
# Phase 1: Schema & Types
# ============================================================================


@dataclass
class WindowConfig:
    """Configuration for time-windowed statistics.

    Attributes:
        window_size: Time window for P95 calculation (default 1 hour)
        min_samples: Minimum samples required for reliable P95 (default 10)
    """

    window_size: timedelta = timedelta(hours=1)
    min_samples: int = 10


@dataclass
class WindowedStats:
    """Statistics within a time window.

    Attributes:
        p95: 95th percentile memory in MB, or None if insufficient samples
        sample_count: Number of samples in the window
        window_start: Start of the time window
        window_end: End of the time window
    """

    p95: Optional[int]
    sample_count: int
    window_start: datetime
    window_end: datetime


@dataclass
class DynamicAllocation:
    """Result of dynamic allocation calculation.

    Attributes:
        max_agents: Maximum concurrent agents allowed
        estimated_memory_per_agent: Estimated memory per agent in MB
        available_memory_mb: Available system memory in MB
        safety_margin_mb: Safety margin subtracted from available memory
        source: Data source used ("bootstrap", "p95_windowed", "p95_lifetime")
    """

    max_agents: int
    estimated_memory_per_agent: int
    available_memory_mb: int
    safety_margin_mb: int
    source: str  # "bootstrap" | "p95_windowed" | "p95_lifetime"


# ============================================================================
# Phase 2: ResourceProfiler Enhancements (standalone functions)
# ============================================================================


def _load_samples_windowed(
    profiler: ResourceProfiler,
    model: str,
    window: timedelta,
) -> list[tuple[datetime, int]]:
    """Load samples with timestamps within window.

    Args:
        profiler: ResourceProfiler instance
        model: Model name to filter by
        window: Time window to consider

    Returns:
        List of (timestamp, memory_mb) tuples within window
    """
    if not profiler.history_file.exists():
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - window
    samples: list[tuple[datetime, int]] = []

    try:
        with open(profiler.history_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("model") != model:
                        continue

                    # Parse timestamp
                    ts_str = entry.get("timestamp")
                    if not ts_str:
                        continue

                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts >= cutoff:
                        samples.append((ts, entry["mem_mb"]))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    except OSError:
        return []

    return samples


def get_p95_windowed(
    profiler: ResourceProfiler,
    model: str,
    window: timedelta = timedelta(hours=1),
    min_samples: int = MIN_SAMPLES_FOR_P95,
) -> Optional[int]:
    """Get P95 within a time window.

    Args:
        profiler: ResourceProfiler instance
        model: Model name
        window: Time window to consider (default 1 hour)
        min_samples: Minimum samples required (default 10)

    Returns:
        P95 within window, or None if insufficient samples
    """
    samples = _load_samples_windowed(profiler, model, window)

    if len(samples) < min_samples:
        return None

    # Extract memory values and calculate P95
    mem_values = sorted([mem for _, mem in samples])
    p95_index = int(len(mem_values) * 0.95)
    p95_index = min(p95_index, len(mem_values) - 1)

    return mem_values[p95_index]


def get_windowed_stats(
    profiler: ResourceProfiler,
    model: str,
    window: timedelta = timedelta(hours=1),
    min_samples: int = MIN_SAMPLES_FOR_P95,
) -> WindowedStats:
    """Get full windowed statistics.

    Args:
        profiler: ResourceProfiler instance
        model: Model name
        window: Time window to consider
        min_samples: Minimum samples for P95

    Returns:
        WindowedStats with P95 and metadata
    """
    now = datetime.now(timezone.utc)
    samples = _load_samples_windowed(profiler, model, window)

    p95 = None
    if len(samples) >= min_samples:
        mem_values = sorted([mem for _, mem in samples])
        p95_index = int(len(mem_values) * 0.95)
        p95_index = min(p95_index, len(mem_values) - 1)
        p95 = mem_values[p95_index]

    return WindowedStats(
        p95=p95,
        sample_count=len(samples),
        window_start=now - window,
        window_end=now,
    )


def get_estimate_adaptive(
    profiler: ResourceProfiler,
    model: str,
    window: timedelta = timedelta(hours=1),
) -> tuple[int, str]:
    """Get adaptive estimate with source tracking.

    Priority:
    1. Windowed P95 (most recent data)
    2. Lifetime P95 (more history)
    3. Bootstrap default (no history)

    Returns:
        (estimate_mb, source) where source is one of:
        - "bootstrap": Using default MODEL_MEMORY_MB
        - "p95_windowed": Using windowed P95
        - "p95_lifetime": Using lifetime P95 (fallback)
    """
    # Get bootstrap default
    bootstrap = MODEL_MEMORY_MB.get(model, MODEL_MEMORY_MB[DEFAULT_MODEL])

    # Try windowed P95 first (most recent data)
    p95_windowed = get_p95_windowed(profiler, model, window)
    if p95_windowed is not None:
        # Use max of bootstrap and windowed P95 (conservative)
        return max(bootstrap, p95_windowed), "p95_windowed"

    # Try lifetime P95 (fallback)
    p95_lifetime = profiler.get_p95(model)
    if p95_lifetime is not None:
        return max(bootstrap, p95_lifetime), "p95_lifetime"

    # Fall back to bootstrap default
    return bootstrap, "bootstrap"


# ============================================================================
# Phase 3: Dynamic Allocation Logic
# ============================================================================


class DynamicAllocator:
    """Dynamic resource allocation based on real-time memory and history.

    Calculates maximum concurrent agents based on:
    - Available system memory
    - Per-agent memory estimates (windowed P95 > lifetime P95 > bootstrap)
    - Safety margin
    - Configurable bounds
    """

    def __init__(
        self,
        profiler: ResourceProfiler,
        safety_margin_mb: int = 2048,
        min_agents: int = 1,
        max_agents: int = 20,
        window: timedelta = timedelta(hours=1),
    ):
        """Initialize allocator with profiler and configuration.

        Args:
            profiler: ResourceProfiler instance for memory estimates
            safety_margin_mb: Memory to reserve for system (default 2GB)
            min_agents: Minimum agents to allow (default 1)
            max_agents: Maximum agents to allow (default 20)
            window: Time window for P95 calculation (default 1 hour)
        """
        self._profiler = profiler
        self._safety_margin_mb = safety_margin_mb
        self._min_agents = min_agents
        self._max_agents = max_agents
        self._window = window

    def calculate_max_agents(self, model: str = "sonnet") -> DynamicAllocation:
        """Calculate maximum concurrent agents for current conditions.

        Formula: (available_memory - safety_margin) / per_agent_estimate

        Uses adaptive estimate from profiler (windowed P95 > lifetime P95 > bootstrap).

        Args:
            model: Model name for memory estimation (default "sonnet")

        Returns:
            DynamicAllocation with max_agents and metadata
        """
        # Get current system resources
        resources = get_system_resources()
        available_memory = resources.available_memory_mb

        # Get adaptive memory estimate per agent
        estimate, source = get_estimate_adaptive(self._profiler, model, self._window)

        # Calculate max agents
        usable_memory = available_memory - self._safety_margin_mb
        if usable_memory <= 0:
            calculated_max = self._min_agents
        else:
            calculated_max = usable_memory // estimate

        # Clamp to bounds
        clamped_max = max(self._min_agents, min(self._max_agents, calculated_max))

        return DynamicAllocation(
            max_agents=clamped_max,
            estimated_memory_per_agent=estimate,
            available_memory_mb=available_memory,
            safety_margin_mb=self._safety_margin_mb,
            source=source,
        )

    def should_spawn(
        self, active_agents: int, model: str = "sonnet"
    ) -> tuple[bool, str]:
        """Check if another agent can be spawned.

        Args:
            active_agents: Current number of active agents
            model: Model name for memory estimation

        Returns:
            (can_spawn, reason) where reason explains decision
        """
        allocation = self.calculate_max_agents(model)

        if active_agents >= allocation.max_agents:
            return (
                False,
                f"At limit: {active_agents}/{allocation.max_agents} agents (max from {allocation.source})",
            )

        return (
            True,
            f"Allowed: {active_agents}/{allocation.max_agents} agents",
        )

    def get_current_utilization(self, active_agents: int) -> float:
        """Get current resource utilization as percentage (0.0-1.0).

        Args:
            active_agents: Current number of active agents

        Returns:
            Utilization as float from 0.0 to 1.0
        """
        allocation = self.calculate_max_agents()
        if allocation.max_agents <= 0:
            return 1.0
        return active_agents / allocation.max_agents


# ============================================================================
# Phase 5: Circuit Breaker Integration
# ============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, spawning allowed
    OPEN = "open"  # Resource exhaustion, spawning blocked
    HALF_OPEN = "half_open"  # Testing if resources recovered


class ResourceCircuitBreaker:
    """Circuit breaker that opens on resource exhaustion.

    Complements failure-based CircuitBreaker by tracking resource state.
    Opens circuit when utilization exceeds threshold, preventing new spawns.

    States:
    - CLOSED: Normal operation, spawning allowed
    - OPEN: Resource exhaustion, spawning blocked
    - HALF_OPEN: Testing if resources recovered

    The breaker tracks active agents internally via `on_agent_start()` and
    `on_agent_complete()` callbacks. Alternatively, callers can pass
    `active_agents` to `can_spawn()` for external tracking.
    """

    def __init__(
        self,
        allocator: DynamicAllocator,
        utilization_threshold: float = 0.9,  # Open at 90% utilization
        recovery_threshold: float = 0.7,  # Close at 70% utilization
        check_interval: float = 5.0,  # Seconds between checks (for future polling)
    ):
        """Initialize resource circuit breaker.

        Args:
            allocator: DynamicAllocator for resource calculations
            utilization_threshold: Open circuit when utilization >= this
            recovery_threshold: Close circuit when utilization < this
            check_interval: Seconds between utilization checks (reserved for future use)
        """
        self._allocator = allocator
        self._utilization_threshold = utilization_threshold
        self._recovery_threshold = recovery_threshold
        self._check_interval = check_interval
        self._state = CircuitState.CLOSED
        self._lock = asyncio.Lock()
        self._active_agents = 0  # Track active agents internally

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    async def can_spawn(
        self, model: str = "sonnet", active_agents: int | None = None
    ) -> tuple[bool, str]:
        """Check if spawning is allowed.

        Updates circuit state based on current utilization.

        Args:
            model: Model name for memory estimation
            active_agents: Override active agent count (uses internal tracking if None)

        Returns:
            (allowed, reason) explaining decision
        """
        async with self._lock:
            # Use provided active_agents or internal tracking
            current_active = (
                active_agents if active_agents is not None else self._active_agents
            )
            utilization = self._allocator.get_current_utilization(
                active_agents=current_active
            )

            if self._state == CircuitState.CLOSED:
                if utilization >= self._utilization_threshold:
                    self._state = CircuitState.OPEN
                    return (
                        False,
                        f"Circuit OPEN: utilization {utilization:.0%} >= {self._utilization_threshold:.0%}",
                    )
                return (True, f"Circuit CLOSED: utilization {utilization:.0%}")

            elif self._state == CircuitState.OPEN:
                return (
                    False,
                    f"Circuit OPEN: waiting for recovery (utilization {utilization:.0%})",
                )

            elif self._state == CircuitState.HALF_OPEN:
                if utilization < self._recovery_threshold:
                    self._state = CircuitState.CLOSED
                    return (
                        True,
                        f"Circuit CLOSED: recovered (utilization {utilization:.0%})",
                    )
                else:
                    self._state = CircuitState.OPEN
                    return (
                        False,
                        f"Circuit OPEN: still high utilization {utilization:.0%}",
                    )

            # Should not reach here
            return (False, "Unknown circuit state")

    async def on_agent_start(self) -> None:
        """Called when an agent starts - increments active count."""
        async with self._lock:
            self._active_agents += 1

    async def on_agent_complete(self) -> None:
        """Called when an agent completes - may transition state.

        Decrements active count and transitions OPEN -> HALF_OPEN to test recovery.
        """
        async with self._lock:
            self._active_agents = max(0, self._active_agents - 1)
            if self._state == CircuitState.OPEN:
                self._state = CircuitState.HALF_OPEN

    def get_active_agents(self) -> int:
        """Get current active agent count.

        Returns the internally tracked active agent count.
        """
        return self._active_agents

    def set_active_agents(self, count: int) -> None:
        """Set active agent count for external synchronization.

        Use this to sync with an external source (e.g., ResourcePool).

        Args:
            count: Number of active agents
        """
        self._active_agents = max(0, count)


# ============================================================================
# Phase 3 (continued): ResourcePool Integration
# ============================================================================


def create_dynamic_resource_pool(
    dynamic_allocator: Optional[DynamicAllocator] = None,
    resource_breaker: Optional[ResourceCircuitBreaker] = None,
    max_concurrent_agents: int = 4,
    acquire_timeout: float = 30.0,
) -> "DynamicResourcePool":
    """Create a ResourcePool with optional dynamic allocation.

    Args:
        dynamic_allocator: Optional DynamicAllocator for dynamic sizing
        resource_breaker: Optional ResourceCircuitBreaker for resource protection
        max_concurrent_agents: Static max when dynamic_allocator is None
        acquire_timeout: Timeout for acquire operations

    Returns:
        DynamicResourcePool with integrated dynamic allocation
    """
    return DynamicResourcePool(
        dynamic_allocator=dynamic_allocator,
        resource_breaker=resource_breaker,
        max_concurrent_agents=max_concurrent_agents,
        acquire_timeout=acquire_timeout,
    )


class DynamicResourcePool:
    """ResourcePool extension with dynamic allocation support.

    Wraps the base ResourcePool with dynamic sizing based on
    real-time memory conditions.
    """

    def __init__(
        self,
        dynamic_allocator: Optional[DynamicAllocator] = None,
        resource_breaker: Optional[ResourceCircuitBreaker] = None,
        max_concurrent_agents: int = 4,
        acquire_timeout: float = 30.0,
    ):
        """Initialize dynamic resource pool.

        Args:
            dynamic_allocator: Optional allocator for dynamic sizing
            resource_breaker: Optional circuit breaker for resource protection
            max_concurrent_agents: Static max (used when no allocator)
            acquire_timeout: Default timeout for acquire()
        """
        # Import here to avoid circular imports
        from scripts.agentica_patterns.resource_pool import (
            ResourcePool,
            ResourceHandle,
            ResourceExhaustedError,
        )

        self._base_pool = ResourcePool(
            max_concurrent_agents=max_concurrent_agents,
            acquire_timeout=acquire_timeout,
        )
        self._dynamic_allocator = dynamic_allocator
        self._resource_breaker = resource_breaker
        self._static_max = max_concurrent_agents

    async def _get_effective_max(self) -> int:
        """Get effective max agents (dynamic or static)."""
        if self._dynamic_allocator:
            allocation = self._dynamic_allocator.calculate_max_agents()
            return allocation.max_agents
        return self._static_max

    async def acquire(self, timeout: float | None = None) -> "ResourceHandle":
        """Acquire a resource slot with dynamic limits.

        Checks resource circuit breaker first, then delegates to base pool.

        Args:
            timeout: Override default timeout

        Returns:
            ResourceHandle

        Raises:
            ResourceExhaustedError: If timeout exceeded or circuit open
        """
        from scripts.agentica_patterns.resource_pool import (
            ResourceExhaustedError,
            ResourceHandle,
        )

        # Check resource circuit breaker first
        if self._resource_breaker:
            # Sync breaker's active count with pool's actual count
            self._resource_breaker.set_active_agents(
                len(self._base_pool._active_handles)
            )
            allowed, reason = await self._resource_breaker.can_spawn()
            if not allowed:
                raise ResourceExhaustedError(
                    timeout=0,  # Immediate rejection
                    active_handles=len(self._base_pool._active_handles),
                )

        handle = await self._base_pool.acquire(timeout=timeout)

        # Track new agent in breaker
        if self._resource_breaker:
            await self._resource_breaker.on_agent_start()

        return handle

    async def release(self, handle: "ResourceHandle") -> None:
        """Release a resource handle."""
        await self._base_pool.release(handle)
        if self._resource_breaker:
            await self._resource_breaker.on_agent_complete()

    def get_metrics(self) -> "ResourceMetrics":
        """Get pool metrics."""
        from scripts.agentica_patterns.resource_pool import ResourceMetrics

        return self._base_pool.get_metrics()

    async def check_health(self) -> bool:
        """Check if pool is healthy."""
        return await self._base_pool.check_health()
