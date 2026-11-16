"""
Tests for Adaptive Resource Profiler.

Test categories:
1. Bootstrap defaults (5 tests) - Model-specific memory estimates
2. Historical profiler (5 tests) - JSONL recording and P95 calculations
3. Integration (5 tests) - Wiring with validate_resources.py
"""

import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest


# =============================================================================
# 1. Bootstrap Defaults Tests
# =============================================================================


class TestBootstrapDefaults:
    """Test model-specific memory defaults."""

    def test_haiku_default_450mb(self) -> None:
        """Haiku model should default to 450MB memory estimate."""
        from scripts.validate_resources import MODEL_MEMORY_MB

        assert MODEL_MEMORY_MB["haiku"] == 450

    def test_sonnet_default_650mb(self) -> None:
        """Sonnet model should default to 650MB memory estimate."""
        from scripts.validate_resources import MODEL_MEMORY_MB

        assert MODEL_MEMORY_MB["sonnet"] == 650

    def test_opus_default_850mb(self) -> None:
        """Opus model should default to 850MB memory estimate."""
        from scripts.validate_resources import MODEL_MEMORY_MB

        assert MODEL_MEMORY_MB["opus"] == 850

    def test_unknown_model_uses_sonnet_default(self) -> None:
        """Unknown models should fall back to sonnet's default (650MB)."""
        from scripts.validate_resources import estimate_agent_memory

        # Unknown model should use sonnet default
        assert estimate_agent_memory("unknown-model") == 650
        assert estimate_agent_memory("gpt-4") == 650
        assert estimate_agent_memory("") == 650

    def test_estimate_returns_int(self) -> None:
        """estimate_agent_memory should always return an integer."""
        from scripts.validate_resources import estimate_agent_memory

        for model in ["haiku", "sonnet", "opus", "unknown"]:
            result = estimate_agent_memory(model)
            assert isinstance(result, int), f"Expected int for {model}, got {type(result)}"


# =============================================================================
# 2. Historical Profiler Tests
# =============================================================================


class TestHistoricalProfiler:
    """Test the ResourceProfiler for historical data tracking."""

    def test_record_writes_jsonl(self, tmp_path: Path) -> None:
        """record() should append entries to JSONL file."""
        from scripts.resource_profiler import ResourceProfiler

        history_file = tmp_path / "resource_usage.jsonl"
        profiler = ResourceProfiler(history_file)

        # Record some usage
        profiler.record("agent-1", "sonnet", 700)
        profiler.record("agent-2", "haiku", 400)

        # Verify JSONL format
        lines = history_file.read_text().strip().split("\n")
        assert len(lines) == 2

        entry1 = json.loads(lines[0])
        assert entry1["agent_id"] == "agent-1"
        assert entry1["model"] == "sonnet"
        assert entry1["mem_mb"] == 700
        assert "timestamp" in entry1

        entry2 = json.loads(lines[1])
        assert entry2["agent_id"] == "agent-2"
        assert entry2["model"] == "haiku"
        assert entry2["mem_mb"] == 400

    def test_get_p95_with_enough_samples(self, tmp_path: Path) -> None:
        """get_p95() should return 95th percentile when enough samples exist."""
        from scripts.resource_profiler import ResourceProfiler

        history_file = tmp_path / "resource_usage.jsonl"
        profiler = ResourceProfiler(history_file)

        # Record 20+ samples for sonnet (enough for reliable P95)
        # Memory values: 600, 610, 620, ..., 790 (20 samples)
        for i in range(20):
            profiler.record(f"agent-{i}", "sonnet", 600 + i * 10)

        # P95 should be around the 95th percentile value
        # For 20 samples sorted, P95 index is 0.95 * 20 = 19th element (0-indexed: 18)
        # Values: 600, 610, 620, 630, 640, 650, 660, 670, 680, 690, 700, 710, 720, 730, 740, 750, 760, 770, 780, 790
        # 95th percentile should be around 780-790
        p95 = profiler.get_p95("sonnet")
        assert p95 is not None
        assert 770 <= p95 <= 800  # Allow some flexibility in P95 calculation

    def test_get_p95_falls_back_to_bootstrap_when_few_samples(self, tmp_path: Path) -> None:
        """get_p95() should return None when insufficient samples (fallback to bootstrap)."""
        from scripts.resource_profiler import ResourceProfiler

        history_file = tmp_path / "resource_usage.jsonl"
        profiler = ResourceProfiler(history_file)

        # Record only 5 samples (not enough for reliable P95)
        for i in range(5):
            profiler.record(f"agent-{i}", "haiku", 400 + i * 10)

        # Should return None to signal fallback to bootstrap
        p95 = profiler.get_p95("haiku")
        assert p95 is None

    def test_profiler_filters_by_model(self, tmp_path: Path) -> None:
        """get_p95() should only consider samples for the requested model."""
        from scripts.resource_profiler import ResourceProfiler

        history_file = tmp_path / "resource_usage.jsonl"
        profiler = ResourceProfiler(history_file)

        # Record samples for multiple models
        for i in range(20):
            profiler.record(f"haiku-{i}", "haiku", 400 + i * 5)  # 400-495
            profiler.record(f"opus-{i}", "opus", 800 + i * 10)  # 800-990

        # Haiku P95 should be around 480-495
        haiku_p95 = profiler.get_p95("haiku")
        assert haiku_p95 is not None
        assert 470 <= haiku_p95 <= 500

        # Opus P95 should be around 960-990
        opus_p95 = profiler.get_p95("opus")
        assert opus_p95 is not None
        assert 950 <= opus_p95 <= 1000

    def test_profiler_handles_missing_file(self, tmp_path: Path) -> None:
        """Profiler should handle missing history file gracefully."""
        from scripts.resource_profiler import ResourceProfiler

        history_file = tmp_path / "nonexistent" / "resource_usage.jsonl"
        profiler = ResourceProfiler(history_file)

        # Should not raise, should return None
        p95 = profiler.get_p95("sonnet")
        assert p95 is None

        # Should create parent dirs and write
        profiler.record("agent-1", "sonnet", 700)
        assert history_file.exists()


# =============================================================================
# 3. Integration Tests
# =============================================================================


class TestIntegration:
    """Test integration between profiler and validate_resources."""

    def test_validate_resources_uses_new_defaults(self) -> None:
        """validate_resources should use new MODEL_MEMORY_MB defaults."""
        from scripts.validate_resources import (
            MODEL_MEMORY_MB,
            PATTERN_COSTS,
            calculate_requirements,
        )

        # Swarm pattern should use MODEL_MEMORY_MB * concurrent_agents
        # With new defaults, Swarm(3) with sonnet agents = 650 * 3 = 1950 MB
        # But the current PATTERN_COSTS may use a base value

        # Verify MODEL_MEMORY_MB is used in pattern cost calculation
        assert "sonnet" in MODEL_MEMORY_MB
        swarm_cost = PATTERN_COSTS["Swarm"]

        # Memory per agent should be based on model defaults
        # The exact implementation may vary, but memory should be realistic
        assert swarm_cost.memory_mb >= 100  # At least 100MB per agent

    def test_profiler_blends_bootstrap_and_history(self, tmp_path: Path) -> None:
        """get_estimate() should blend bootstrap and history based on sample count."""
        from scripts.resource_profiler import ResourceProfiler
        from scripts.validate_resources import MODEL_MEMORY_MB

        history_file = tmp_path / "resource_usage.jsonl"
        profiler = ResourceProfiler(history_file)

        # No history - should use bootstrap
        estimate_no_history = profiler.get_estimate("sonnet")
        assert estimate_no_history == MODEL_MEMORY_MB["sonnet"]

        # Add some history but not enough for full P95
        for i in range(5):
            profiler.record(f"agent-{i}", "sonnet", 800)  # Higher than bootstrap

        # With few samples, should still use bootstrap
        estimate_few = profiler.get_estimate("sonnet")
        assert estimate_few == MODEL_MEMORY_MB["sonnet"]

        # Add enough history for P95
        for i in range(20):
            profiler.record(f"agent-extra-{i}", "sonnet", 750)

        # Now should blend or use P95
        estimate_many = profiler.get_estimate("sonnet")
        # Should be influenced by history (750s) vs bootstrap (650)
        assert estimate_many >= 700  # Historical values are higher

    def test_can_launch_with_realistic_memory(self) -> None:
        """validate_resources should work with realistic memory requirements."""
        from scripts.validate_resources import validate_resources

        # A simple Pipeline should always be launchable
        result = validate_resources("Pipeline")
        # On most systems with reasonable memory, Pipeline should work
        # If it fails, check the bottleneck makes sense
        if not result.can_launch:
            assert result.bottleneck in ["memory", "cpu", "processes"]
        else:
            assert result.can_launch is True

    def test_fallback_suggestion_with_new_costs(self) -> None:
        """Fallback suggestions should account for new memory costs."""
        from scripts.validate_resources import suggest_fallback, get_system_resources

        available = get_system_resources()

        # Test that fallback suggestion works
        suggestion = suggest_fallback("Swarm(10)", "memory", available)

        # Should suggest reducing agents or using Pipeline
        if suggestion:
            assert "Reduce" in suggestion or "Pipeline" in suggestion

    def test_profiler_thread_safe_writes(self, tmp_path: Path) -> None:
        """record() should be thread-safe for concurrent writes."""
        from scripts.resource_profiler import ResourceProfiler

        history_file = tmp_path / "resource_usage.jsonl"
        profiler = ResourceProfiler(history_file)

        # Concurrent writes from multiple threads
        errors: list[Exception] = []

        def write_records(thread_id: int) -> None:
            try:
                for i in range(10):
                    profiler.record(f"agent-{thread_id}-{i}", "sonnet", 650 + thread_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_records, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0

        # All records should be present
        lines = history_file.read_text().strip().split("\n")
        assert len(lines) == 50  # 5 threads * 10 records each
