"""
Tests for dynamic resource allocation.

TDD approach: Write tests first, then implement.

Tests cover:
- Phase 1: Schema & Types (WindowConfig, WindowedStats, DynamicAllocation)
- Phase 2: ResourceProfiler Enhancements (get_p95_windowed, get_estimate_adaptive)
- Phase 3: Dynamic Allocation Logic (DynamicAllocator)
- Phase 5: Circuit Breaker Integration (ResourceCircuitBreaker)
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


# ============================================================================
# Phase 1: Schema & Types Tests
# ============================================================================


class TestWindowConfig:
    """Tests for WindowConfig dataclass."""

    def test_window_config_defaults(self):
        """WindowConfig has sensible defaults (1 hour window, 10 min samples)."""
        from scripts.agentica_patterns.dynamic_resources import WindowConfig

        config = WindowConfig()
        assert config.window_size == timedelta(hours=1)
        assert config.min_samples == 10

    def test_window_config_custom_values(self):
        """WindowConfig accepts custom values."""
        from scripts.agentica_patterns.dynamic_resources import WindowConfig

        config = WindowConfig(window_size=timedelta(minutes=30), min_samples=5)
        assert config.window_size == timedelta(minutes=30)
        assert config.min_samples == 5


class TestWindowedStats:
    """Tests for WindowedStats dataclass."""

    def test_windowed_stats_dataclass(self):
        """WindowedStats holds all required fields."""
        from scripts.agentica_patterns.dynamic_resources import WindowedStats

        now = datetime.now(timezone.utc)
        stats = WindowedStats(
            p95=720,
            sample_count=15,
            window_start=now - timedelta(hours=1),
            window_end=now,
        )
        assert stats.p95 == 720
        assert stats.sample_count == 15
        assert stats.window_start < stats.window_end

    def test_windowed_stats_optional_p95(self):
        """WindowedStats p95 can be None when insufficient samples."""
        from scripts.agentica_patterns.dynamic_resources import WindowedStats

        now = datetime.now(timezone.utc)
        stats = WindowedStats(
            p95=None,
            sample_count=5,
            window_start=now - timedelta(hours=1),
            window_end=now,
        )
        assert stats.p95 is None
        assert stats.sample_count == 5


class TestDynamicAllocation:
    """Tests for DynamicAllocation dataclass."""

    def test_dynamic_allocation_sources(self):
        """DynamicAllocation tracks data source."""
        from scripts.agentica_patterns.dynamic_resources import DynamicAllocation

        allocation = DynamicAllocation(
            max_agents=8,
            estimated_memory_per_agent=650,
            available_memory_mb=8192,
            safety_margin_mb=2048,
            source="p95_windowed",
        )
        assert allocation.max_agents == 8
        assert allocation.source == "p95_windowed"

    def test_dynamic_allocation_all_sources(self):
        """DynamicAllocation supports all valid source values."""
        from scripts.agentica_patterns.dynamic_resources import DynamicAllocation

        for source in ["bootstrap", "p95_windowed", "p95_lifetime"]:
            allocation = DynamicAllocation(
                max_agents=4,
                estimated_memory_per_agent=500,
                available_memory_mb=4096,
                safety_margin_mb=2048,
                source=source,
            )
            assert allocation.source == source


# ============================================================================
# Phase 2: ResourceProfiler Enhancements Tests
# ============================================================================


class TestResourceProfilerWindowed:
    """Tests for windowed P95 methods on ResourceProfiler."""

    @pytest.fixture
    def temp_history_file(self, tmp_path):
        """Create a temporary history file for testing.

        Uses pytest's tmp_path fixture which handles cleanup automatically.
        """
        temp_file = tmp_path / "history.jsonl"
        temp_file.touch()
        yield temp_file
        # Cleanup is automatic via tmp_path

    @pytest.fixture
    def profiler(self, temp_history_file):
        """Create a profiler with temporary history file."""
        from scripts.resource_profiler import ResourceProfiler

        return ResourceProfiler(history_file=temp_history_file)

    def test_get_p95_windowed_empty_history(self, profiler):
        """Returns None when no history exists."""
        from scripts.agentica_patterns.dynamic_resources import get_p95_windowed

        result = get_p95_windowed(profiler, "sonnet")
        assert result is None

    def test_get_p95_windowed_old_samples_excluded(self, profiler, temp_history_file):
        """Samples outside window are excluded from P95."""
        from scripts.agentica_patterns.dynamic_resources import get_p95_windowed

        # Write samples that are 2 hours old
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        for i in range(15):
            entry = {
                "agent_id": f"agent-{i}",
                "model": "sonnet",
                "mem_mb": 500 + i * 10,
                "timestamp": old_time.isoformat(),
            }
            with open(temp_history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        # With 1 hour window, old samples should be excluded
        result = get_p95_windowed(profiler, "sonnet", window=timedelta(hours=1))
        assert result is None  # No samples in window

    def test_get_p95_windowed_recent_samples_included(
        self, profiler, temp_history_file
    ):
        """Samples within window are included in P95."""
        from scripts.agentica_patterns.dynamic_resources import get_p95_windowed

        # Write recent samples
        now = datetime.now(timezone.utc)
        for i in range(15):
            entry = {
                "agent_id": f"agent-{i}",
                "model": "sonnet",
                "mem_mb": 500 + i * 10,  # 500, 510, ..., 640
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
            }
            with open(temp_history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        # With 1 hour window, recent samples should be included
        result = get_p95_windowed(profiler, "sonnet", window=timedelta(hours=1))
        assert result is not None
        # P95 of 500-640 range should be around 630
        assert 620 <= result <= 650

    def test_get_estimate_adaptive_prefers_windowed(self, profiler, temp_history_file):
        """Uses windowed P95 when available."""
        from scripts.agentica_patterns.dynamic_resources import get_estimate_adaptive

        # Write sufficient recent samples
        now = datetime.now(timezone.utc)
        for i in range(15):
            entry = {
                "agent_id": f"agent-{i}",
                "model": "sonnet",
                "mem_mb": 700 + i * 10,  # Higher than bootstrap
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
            }
            with open(temp_history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        estimate, source = get_estimate_adaptive(profiler, "sonnet")
        assert source == "p95_windowed"
        assert estimate >= 700  # Should use higher P95

    def test_get_estimate_adaptive_falls_back_to_lifetime(
        self, profiler, temp_history_file
    ):
        """Falls back to lifetime P95 when windowed insufficient."""
        from scripts.agentica_patterns.dynamic_resources import get_estimate_adaptive

        # Write old samples (outside 1 hour window but sufficient for lifetime P95)
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        for i in range(15):
            entry = {
                "agent_id": f"agent-{i}",
                "model": "sonnet",
                "mem_mb": 700 + i * 10,
                "timestamp": old_time.isoformat(),
            }
            with open(temp_history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        estimate, source = get_estimate_adaptive(profiler, "sonnet")
        assert source == "p95_lifetime"

    def test_get_estimate_adaptive_falls_back_to_bootstrap(self, profiler):
        """Falls back to bootstrap when no P95 available."""
        from scripts.agentica_patterns.dynamic_resources import get_estimate_adaptive

        estimate, source = get_estimate_adaptive(profiler, "sonnet")
        assert source == "bootstrap"
        assert estimate == 650  # Bootstrap default for sonnet


# ============================================================================
# Phase 3: Dynamic Allocation Logic Tests
# ============================================================================


class TestDynamicAllocator:
    """Tests for DynamicAllocator class."""

    @pytest.fixture
    def temp_history_file(self, tmp_path):
        """Create a temporary history file for testing.

        Uses pytest's tmp_path fixture which handles cleanup automatically.
        """
        temp_file = tmp_path / "history.jsonl"
        temp_file.touch()
        yield temp_file
        # Cleanup is automatic via tmp_path

    @pytest.fixture
    def profiler(self, temp_history_file):
        """Create a profiler with temporary history file."""
        from scripts.resource_profiler import ResourceProfiler

        return ResourceProfiler(history_file=temp_history_file)

    def test_calculate_max_agents_uses_profiler(self, profiler):
        """Uses profiler's adaptive estimate for per-agent memory."""
        from scripts.agentica_patterns.dynamic_resources import DynamicAllocator

        allocator = DynamicAllocator(
            profiler=profiler,
            safety_margin_mb=2048,
        )

        # Mock get_system_resources to return consistent value
        with patch(
            "scripts.agentica_patterns.dynamic_resources.get_system_resources"
        ) as mock_resources:
            mock_resources.return_value = Mock(available_memory_mb=8192)

            allocation = allocator.calculate_max_agents(model="sonnet")
            # (8192 - 2048) / 650 (bootstrap) = 9.45 -> 9 agents
            assert allocation.max_agents == 9
            assert allocation.estimated_memory_per_agent == 650  # Bootstrap default

    def test_calculate_max_agents_respects_safety_margin(self, profiler):
        """Safety margin is subtracted from available memory."""
        from scripts.agentica_patterns.dynamic_resources import DynamicAllocator

        allocator = DynamicAllocator(
            profiler=profiler,
            safety_margin_mb=4096,  # Larger safety margin
        )

        with patch(
            "scripts.agentica_patterns.dynamic_resources.get_system_resources"
        ) as mock_resources:
            mock_resources.return_value = Mock(available_memory_mb=8192)

            allocation = allocator.calculate_max_agents(model="sonnet")
            # (8192 - 4096) / 650 = 6.3 -> 6 agents
            assert allocation.max_agents == 6
            assert allocation.safety_margin_mb == 4096

    def test_calculate_max_agents_clamps_to_bounds(self, profiler):
        """Result is clamped to [min_agents, max_agents]."""
        from scripts.agentica_patterns.dynamic_resources import DynamicAllocator

        allocator = DynamicAllocator(
            profiler=profiler,
            safety_margin_mb=2048,
            min_agents=2,
            max_agents=5,
        )

        with patch(
            "scripts.agentica_patterns.dynamic_resources.get_system_resources"
        ) as mock_resources:
            # High memory - would calculate > 5 without clamping
            mock_resources.return_value = Mock(available_memory_mb=16384)
            allocation = allocator.calculate_max_agents()
            assert allocation.max_agents == 5  # Clamped to max

            # Low memory - would calculate < 2 without clamping
            mock_resources.return_value = Mock(available_memory_mb=2500)
            allocation = allocator.calculate_max_agents()
            assert allocation.max_agents == 2  # Clamped to min

    def test_should_spawn_under_limit(self, profiler):
        """Returns True when under max_agents."""
        from scripts.agentica_patterns.dynamic_resources import DynamicAllocator

        allocator = DynamicAllocator(profiler=profiler)

        with patch(
            "scripts.agentica_patterns.dynamic_resources.get_system_resources"
        ) as mock_resources:
            mock_resources.return_value = Mock(available_memory_mb=8192)

            can_spawn, reason = allocator.should_spawn(active_agents=2, model="sonnet")
            assert can_spawn is True
            assert "allowed" in reason.lower() or reason == ""

    def test_should_spawn_at_limit(self, profiler):
        """Returns False when at max_agents."""
        from scripts.agentica_patterns.dynamic_resources import DynamicAllocator

        allocator = DynamicAllocator(profiler=profiler, max_agents=4)

        with patch(
            "scripts.agentica_patterns.dynamic_resources.get_system_resources"
        ) as mock_resources:
            mock_resources.return_value = Mock(available_memory_mb=8192)

            can_spawn, reason = allocator.should_spawn(active_agents=4)
            assert can_spawn is False
            assert "limit" in reason.lower() or "max" in reason.lower()

    def test_get_current_utilization(self, profiler):
        """Returns correct percentage."""
        from scripts.agentica_patterns.dynamic_resources import DynamicAllocator

        allocator = DynamicAllocator(profiler=profiler, max_agents=10)

        with patch(
            "scripts.agentica_patterns.dynamic_resources.get_system_resources"
        ) as mock_resources:
            # With 8192MB, 2048 safety, 650 per agent: max = (8192-2048)/650 = 9.45 -> 9
            # But max_agents=10 is clamped, so effective max is 9
            mock_resources.return_value = Mock(available_memory_mb=8192)

            # 5 active out of effective max 9 = 0.556
            utilization = allocator.get_current_utilization(active_agents=5)
            assert 0.5 <= utilization <= 0.6  # ~55%


# ============================================================================
# Phase 5: Circuit Breaker Integration Tests
# ============================================================================


class TestResourceCircuitBreaker:
    """Tests for ResourceCircuitBreaker class."""

    @pytest.fixture
    def mock_allocator(self):
        """Create a mock allocator for testing."""
        mock = Mock()
        mock.get_current_utilization.return_value = 0.5
        mock.calculate_max_agents.return_value = Mock(max_agents=8)
        return mock

    def test_circuit_closed_initially(self, mock_allocator):
        """Circuit starts in CLOSED state."""
        from scripts.agentica_patterns.dynamic_resources import (
            CircuitState,
            ResourceCircuitBreaker,
        )

        breaker = ResourceCircuitBreaker(allocator=mock_allocator)
        assert breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_at_threshold(self, mock_allocator):
        """Circuit opens when utilization >= threshold."""
        from scripts.agentica_patterns.dynamic_resources import (
            CircuitState,
            ResourceCircuitBreaker,
        )

        # Set utilization above threshold
        mock_allocator.get_current_utilization.return_value = 0.95

        breaker = ResourceCircuitBreaker(
            allocator=mock_allocator,
            utilization_threshold=0.9,
        )

        # Check triggers state update
        await breaker.can_spawn()
        assert breaker.get_state() == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_blocks_spawn_when_open(self, mock_allocator):
        """can_spawn returns False when circuit is OPEN."""
        from scripts.agentica_patterns.dynamic_resources import (
            CircuitState,
            ResourceCircuitBreaker,
        )

        mock_allocator.get_current_utilization.return_value = 0.95

        breaker = ResourceCircuitBreaker(
            allocator=mock_allocator,
            utilization_threshold=0.9,
        )

        allowed, reason = await breaker.can_spawn()
        assert allowed is False
        assert "circuit" in reason.lower() or "resource" in reason.lower()

    @pytest.mark.asyncio
    async def test_circuit_half_opens_after_agent_complete(self, mock_allocator):
        """Circuit enters HALF_OPEN when agent completes while OPEN."""
        from scripts.agentica_patterns.dynamic_resources import (
            CircuitState,
            ResourceCircuitBreaker,
        )

        # Start with high utilization
        mock_allocator.get_current_utilization.return_value = 0.95

        breaker = ResourceCircuitBreaker(
            allocator=mock_allocator,
            utilization_threshold=0.9,
        )

        # Open the circuit
        await breaker.can_spawn()
        assert breaker.get_state() == CircuitState.OPEN

        # Agent completes
        await breaker.on_agent_complete()
        assert breaker.get_state() == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_closes_below_recovery_threshold(self, mock_allocator):
        """Circuit closes when utilization drops below recovery_threshold."""
        from scripts.agentica_patterns.dynamic_resources import (
            CircuitState,
            ResourceCircuitBreaker,
        )

        # Start with high utilization
        mock_allocator.get_current_utilization.return_value = 0.95

        breaker = ResourceCircuitBreaker(
            allocator=mock_allocator,
            utilization_threshold=0.9,
            recovery_threshold=0.7,
        )

        # Open the circuit
        await breaker.can_spawn()
        assert breaker.get_state() == CircuitState.OPEN

        # Utilization drops
        mock_allocator.get_current_utilization.return_value = 0.6

        # Agent completes - should transition to HALF_OPEN then CLOSED
        await breaker.on_agent_complete()

        # Another check should see low utilization and close
        allowed, _ = await breaker.can_spawn()
        assert breaker.get_state() == CircuitState.CLOSED
        assert allowed is True


# ============================================================================
# Integration Tests: ResourcePool with Dynamic Allocator
# ============================================================================


class TestResourcePoolDynamicIntegration:
    """Tests for ResourcePool integration with DynamicAllocator."""

    @pytest.fixture
    def mock_allocator(self):
        """Create a mock allocator."""
        mock = Mock()
        mock.calculate_max_agents.return_value = Mock(max_agents=4)
        mock.get_current_utilization.return_value = 0.25
        return mock

    @pytest.mark.asyncio
    async def test_pool_uses_dynamic_allocator(self, mock_allocator):
        """ResourcePool respects dynamic_allocator when provided."""
        from scripts.agentica_patterns.dynamic_resources import (
            create_dynamic_resource_pool,
        )

        pool = create_dynamic_resource_pool(
            dynamic_allocator=mock_allocator,
            max_concurrent_agents=10,  # Static max
        )

        # Should use dynamic max (4) not static max (10)
        effective_max = await pool._get_effective_max()
        assert effective_max == 4

    @pytest.mark.asyncio
    async def test_pool_resize_increases_capacity(self):
        """resize() allows more concurrent acquisitions."""
        from scripts.agentica_patterns.resource_pool import ResourcePool

        pool = ResourcePool(max_concurrent_agents=2)

        # Acquire both slots
        h1 = await pool.acquire(timeout=1.0)
        h2 = await pool.acquire(timeout=1.0)

        # Should not be able to acquire more
        with pytest.raises(Exception):  # ResourceExhaustedError
            await pool.acquire(timeout=0.1)

        # Release and verify we can still only get 2
        await pool.release(h1)
        await pool.release(h2)

        # TODO: resize is not yet implemented, will be added with dynamic allocator
        # await pool.resize(4)
        # Now should be able to acquire 4

    @pytest.mark.asyncio
    async def test_pool_with_resource_breaker(self, mock_allocator):
        """Pool raises ResourceExhaustedError when breaker rejects."""
        from scripts.agentica_patterns.dynamic_resources import (
            ResourceCircuitBreaker,
            create_dynamic_resource_pool,
        )

        # High utilization
        mock_allocator.get_current_utilization.return_value = 0.95

        breaker = ResourceCircuitBreaker(
            allocator=mock_allocator,
            utilization_threshold=0.9,
        )

        pool = create_dynamic_resource_pool(
            dynamic_allocator=mock_allocator,
            resource_breaker=breaker,
        )

        # Should raise because circuit is open
        from scripts.agentica_patterns.resource_pool import ResourceExhaustedError

        with pytest.raises(ResourceExhaustedError):
            await pool.acquire(timeout=1.0)
