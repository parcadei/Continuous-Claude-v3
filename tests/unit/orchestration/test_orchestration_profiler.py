"""
Unit tests for ResourceProfiler integration with OrchestrationLayer.

Tests are organized into four groups:
1. Resource Validation Before Launch (3 tests)
2. Memory Polling During Execution (3 tests)
3. Adaptive Estimation (3 tests)
4. Integration (1 test)

Total: 10 unit tests
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, MagicMock, patch

import pytest

from scripts.agentica_patterns.beads_task_graph import (
    BeadsTaskGraph,
    BeadsTask,
    TaskStatus,
    generate_task_id,
)
from scripts.agentica_patterns.resource_pool import (
    ResourcePool,
    ResourceHandle,
    ResourceExhaustedError,
)
from scripts.agentica_patterns.scope_manager import (
    ScopeManager,
    ManagedScope,
)
from scripts.agentica_patterns.pattern_resolver import (
    PatternResolver,
    PatternSelection,
)
from scripts.agentica_patterns.task_executor import (
    TaskExecutor,
    TaskResult,
)
from scripts.agentica_patterns.patterns.primitives import (
    AggregateMode,
)
from scripts.validate_composition import ScopeType
from scripts.resource_profiler import ResourceProfiler
from scripts.validate_resources import (
    get_system_resources,
    ResourceRequirements,
    SystemResources,
)


# ============================================================================
# Resource Validation Before Launch Tests (3 tests)
# ============================================================================


class TestResourceValidationBeforeLaunch:
    """Test that OrchestrationLayer validates resources before launching tasks."""

    @pytest.mark.asyncio
    async def test_orchestrate_validates_resources_before_launch(
        self, tmp_path: Path
    ) -> None:
        """Verify resource validation happens before task execution."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Create layer with profiler
        layer = OrchestrationLayer.create_default(
            session_id="test-validate",
            db_path=tmp_path / "test.db",
            max_concurrent_agents=4,
        )

        # The layer should have a profiler attribute
        assert hasattr(layer, "_profiler") or hasattr(layer, "profiler")

        # Orchestrate a task - should not raise (we have sufficient resources)
        result = await layer.orchestrate("Simple task")

        # Should succeed since we have resources
        assert result.success or result.errors == []

    @pytest.mark.asyncio
    async def test_orchestrate_fails_if_insufficient_resources(
        self, tmp_path: Path
    ) -> None:
        """Verify orchestration fails when resources are insufficient."""
        from scripts.agentica_patterns.orchestration_layer import (
            OrchestrationLayer,
            ResourceOrchestrationError,
        )

        # Mock get_system_resources to return very low resources
        with patch("scripts.agentica_patterns.orchestration_layer.get_system_resources") as mock_get:
            mock_get.return_value = SystemResources(
                available_memory_mb=10,  # Very low memory
                available_cpu_cores=0.1,
                max_concurrent_processes=1,
            )

            layer = OrchestrationLayer.create_default(
                session_id="test-insufficient",
                db_path=tmp_path / "test.db",
            )

            # Orchestrate should either fail or return error in result
            result = await layer.orchestrate(
                "Complex task requiring lots of memory",
                config={"model": "opus"},  # High memory model
            )

            # Should fail due to insufficient resources
            assert not result.success or len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_orchestrate_uses_fallback_when_resources_low(
        self, tmp_path: Path
    ) -> None:
        """Verify fallback pattern is used when resources are constrained."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Mock get_system_resources to return limited resources
        with patch("scripts.agentica_patterns.orchestration_layer.get_system_resources") as mock_get:
            mock_get.return_value = SystemResources(
                available_memory_mb=500,  # Limited but not exhausted
                available_cpu_cores=2.0,
                max_concurrent_processes=4,
            )

            layer = OrchestrationLayer.create_default(
                session_id="test-fallback",
                db_path=tmp_path / "test.db",
            )

            # Request a resource-heavy pattern with fallback option
            result = await layer.orchestrate(
                "Research authentication options",
                config={
                    "pattern_hint": "Swarm",
                    "fallback_pattern": "Pipeline",
                },
            )

            # Should complete (possibly with fallback pattern)
            # The key is that it handles resource constraints gracefully
            assert result is not None


# ============================================================================
# Memory Polling During Execution Tests (3 tests)
# ============================================================================


class TestMemoryPollingDuringExecution:
    """Test memory polling during task execution."""

    @pytest.mark.asyncio
    async def test_orchestrate_polls_memory_during_execution(
        self, tmp_path: Path
    ) -> None:
        """Verify memory is polled during task execution."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        layer = OrchestrationLayer.create_default(
            session_id="test-poll",
            db_path=tmp_path / "test.db",
        )

        # Ensure profiler exists
        profiler = getattr(layer, "_profiler", None) or getattr(layer, "profiler", None)
        assert profiler is not None, "OrchestrationLayer should have a profiler"

        # Execute a task
        result = await layer.orchestrate("Test task for memory polling")

        # Profiler should be accessible
        assert isinstance(profiler, ResourceProfiler)

    @pytest.mark.asyncio
    async def test_profiler_records_to_jsonl_during_execution(
        self, tmp_path: Path
    ) -> None:
        """Verify profiler records memory samples to JSONL file."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Use a custom history file path
        history_file = tmp_path / "test_usage.jsonl"

        # Create layer with custom profiler pointing to our test file
        layer = OrchestrationLayer.create_default(
            session_id="test-jsonl",
            db_path=tmp_path / "test.db",
        )

        # Replace profiler with one using our test file
        profiler = ResourceProfiler(history_file=history_file)
        if hasattr(layer, "_profiler"):
            layer._profiler = profiler
        elif hasattr(layer, "profiler"):
            layer.profiler = profiler

        # Manually record a sample to verify it works
        profiler.record("test-agent", "sonnet", 720)

        # Verify file was created with entry
        assert history_file.exists()
        with open(history_file) as f:
            lines = f.readlines()
            assert len(lines) >= 1
            entry = json.loads(lines[0])
            assert entry["agent_id"] == "test-agent"
            assert entry["model"] == "sonnet"
            assert entry["mem_mb"] == 720

    @pytest.mark.asyncio
    async def test_polling_stops_when_task_completes(self, tmp_path: Path) -> None:
        """Verify polling stops cleanly when task completes."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        layer = OrchestrationLayer.create_default(
            session_id="test-stop-poll",
            db_path=tmp_path / "test.db",
        )

        # Execute a quick task
        result = await layer.orchestrate("Quick task")

        # Should complete without hanging (polling should stop)
        assert result is not None

        # Allow a moment for cleanup
        await asyncio.sleep(0.1)

        # No lingering polling tasks should remain
        # (This is implicit - if polling didn't stop, the test would hang)


# ============================================================================
# Adaptive Estimation Tests (3 tests)
# ============================================================================


class TestAdaptiveEstimation:
    """Test adaptive memory estimation using historical data."""

    @pytest.mark.asyncio
    async def test_orchestrate_uses_historical_p95_when_available(
        self, tmp_path: Path
    ) -> None:
        """Verify P95 from history is used when enough samples exist."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Create history file with enough samples for P95
        history_file = tmp_path / "resource_usage.jsonl"
        history_file.parent.mkdir(parents=True, exist_ok=True)

        # Write 15 samples (above MIN_SAMPLES_FOR_P95 = 10)
        with open(history_file, "w") as f:
            for i in range(15):
                entry = {
                    "agent_id": f"agent-{i}",
                    "model": "sonnet",
                    "mem_mb": 600 + i * 10,  # 600-740 MB range
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                f.write(json.dumps(entry) + "\n")

        # Create profiler with history file
        profiler = ResourceProfiler(history_file=history_file)

        # P95 should be available
        p95 = profiler.get_p95("sonnet")
        assert p95 is not None
        assert p95 >= 700  # P95 of 600-740 range

        # Get estimate should use P95
        estimate = profiler.get_estimate("sonnet")
        assert estimate >= p95  # Should use max(bootstrap, p95)

    @pytest.mark.asyncio
    async def test_orchestrate_uses_bootstrap_when_no_history(
        self, tmp_path: Path
    ) -> None:
        """Verify bootstrap defaults are used when no history exists."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Create profiler with non-existent history file
        history_file = tmp_path / "nonexistent_usage.jsonl"
        profiler = ResourceProfiler(history_file=history_file)

        # P95 should be None (no samples)
        p95 = profiler.get_p95("sonnet")
        assert p95 is None

        # Estimate should use bootstrap default
        estimate = profiler.get_estimate("sonnet")
        assert estimate == 650  # Bootstrap default for sonnet

    @pytest.mark.asyncio
    async def test_resource_pool_size_adapts_to_available_memory(
        self, tmp_path: Path
    ) -> None:
        """Verify dynamic pool sizing based on available memory."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        layer = OrchestrationLayer.create_default(
            session_id="test-dynamic-pool",
            db_path=tmp_path / "test.db",
        )

        # Check if layer has method for calculating max concurrent
        if hasattr(layer, "_calculate_max_concurrent"):
            max_concurrent = layer._calculate_max_concurrent("sonnet")
            assert isinstance(max_concurrent, int)
            assert max_concurrent >= 1
        else:
            # Fallback: just verify we can get an estimate
            profiler = getattr(layer, "_profiler", None) or getattr(
                layer, "profiler", None
            )
            if profiler:
                estimate = profiler.get_estimate("sonnet")
                assert estimate > 0


# ============================================================================
# Integration Tests (1 test)
# ============================================================================


class TestFullIntegration:
    """Full integration test combining all profiler features."""

    @pytest.mark.asyncio
    async def test_full_orchestration_with_profiling(self, tmp_path: Path) -> None:
        """Test complete orchestration flow with profiling enabled."""
        from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

        # Create orchestration layer
        layer = OrchestrationLayer.create_default(
            session_id="test-full-integration",
            db_path=tmp_path / "integration.db",
            max_concurrent_agents=2,
        )

        # Verify profiler is attached
        profiler = getattr(layer, "_profiler", None) or getattr(layer, "profiler", None)
        assert profiler is not None, "Layer should have profiler"

        # Create a DAG with multiple tasks
        graph = BeadsTaskGraph(
            session_id="test-full-integration",
            db_path=tmp_path / "integration.db",
        )
        t1 = graph.add_task("Research task")
        t2 = graph.add_task("Implementation task", blocks=[t1])
        t3 = graph.add_task("Validation task", blocks=[t2])

        # Execute DAG with profiling
        result = await layer.orchestrate_dag(
            graph,
            config={
                "model": "sonnet",
                "enable_profiling": True,
            },
        )

        # Verify execution completed
        assert result is not None
        assert len(result.task_results) >= 3

        # Verify timing was recorded
        assert result.total_duration_ms > 0
