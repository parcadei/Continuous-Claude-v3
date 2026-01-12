"""
Performance Baseline Management

Manages performance baselines for bottleneck detection.
Supports synthetic traffic collection, production sampling, and baseline updates.
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class BaselineType(Enum):
    """Types of baseline data collection."""
    SYNTHETIC = "synthetic"  # Controlled benchmark traffic
    PRODUCTION = "production"  # Production sampling
    DEPLOY = "deploy"  # Post-deploy collection
    WEEKLY = "weekly"  # Weekly recomputation


@dataclass
class MetricBaseline:
    """Baseline statistics for a single metric."""
    metric_name: str
    mean: float
    std_dev: float
    p50: float  # Median
    p90: float
    p95: float
    p99: float
    min_val: float
    max_val: float
    sample_count: int
    collected_at: datetime
    baseline_type: BaselineType

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_name": self.metric_name,
            "mean": self.mean,
            "std_dev": self.std_dev,
            "p50": self.p50,
            "p90": self.p90,
            "p95": self.p95,
            "p99": self.p99,
            "min_val": self.min_val,
            "max_val": self.max_val,
            "sample_count": self.sample_count,
            "collected_at": self.collected_at.isoformat(),
            "baseline_type": self.baseline_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetricBaseline":
        """Create from dictionary."""
        return cls(
            metric_name=data["metric_name"],
            mean=data["mean"],
            std_dev=data["std_dev"],
            p50=data["p50"],
            p90=data["p90"],
            p95=data["p95"],
            p99=data["p99"],
            min_val=data["min_val"],
            max_val=data["max_val"],
            sample_count=data["sample_count"],
            collected_at=datetime.fromisoformat(data["collected_at"]),
            baseline_type=BaselineType(data["baseline_type"]),
        )


@dataclass
class Baseline:
    """Complete baseline for a component."""
    component: str  # e.g., "database", "memory", "cpu", "network"
    metrics: dict[str, MetricBaseline] = field(default_factory=dict)
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_metric(self, metric: MetricBaseline):
        """Add a metric baseline."""
        self.metrics[metric.metric_name] = metric
        self.updated_at = datetime.utcnow()

    def get_metric(self, name: str) -> MetricBaseline | None:
        """Get a metric baseline by name."""
        return self.metrics.get(name)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "component": self.component,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Baseline":
        """Create from dictionary."""
        baseline = cls(
            component=data["component"],
            version=data.get("version", "1.0"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        for name, metric_data in data.get("metrics", {}).items():
            baseline.add_metric(MetricBaseline.from_dict(metric_data))
        return baseline


class BaselineManager:
    """Manages performance baselines for the system."""

    def __init__(self, storage_path: str | None = None):
        """Initialize baseline manager.
        
        Args:
            storage_path: Path to store baseline files. Defaults to project root.
        """
        if storage_path is None:
            storage_path = os.environ.get(
                "BASELINE_STORAGE_PATH",
                str(Path(__file__).parent.parent.parent.parent / "baselines")
            )
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache of baselines
        self._baselines: dict[str, Baseline] = {}

    def _get_baseline_path(self, component: str) -> Path:
        """Get path for baseline file."""
        return self.storage_path / f"{component}_baseline.json"

    def save_baseline(self, baseline: Baseline) -> None:
        """Save a baseline to storage."""
        path = self._get_baseline_path(baseline.component)
        with open(path, "w") as f:
            json.dump(baseline.to_dict(), f, indent=2)
        self._baselines[baseline.component] = baseline

    def load_baseline(self, component: str) -> Baseline | None:
        """Load a baseline from storage."""
        path = self._get_baseline_path(component)
        if not path.exists():
            return None
        
        if component in self._baselines:
            return self._baselines[component]
        
        with open(path) as f:
            baseline = Baseline.from_dict(json.load(f))
            self._baselines[component] = baseline
            return baseline

    def delete_baseline(self, component: str) -> bool:
        """Delete a baseline from storage."""
        path = self._get_baseline_path(component)
        if path.exists():
            path.unlink()
            self._baselines.pop(component, None)
            return True
        return False

    def compute_baseline_from_samples(
        self,
        component: str,
        metric_name: str,
        samples: list[float],
        baseline_type: BaselineType = BaselineType.PRODUCTION,
    ) -> MetricBaseline:
        """Compute baseline statistics from samples.
        
        Args:
            component: Component name (e.g., "database")
            metric_name: Metric name (e.g., "pg_query_latency_ms")
            samples: List of sample values
            baseline_type: Type of baseline collection
            
        Returns:
            MetricBaseline with computed statistics
        """
        if len(samples) < 2:
            raise ValueError(f"Need at least 2 samples, got {len(samples)}")
        
        arr = np.array(samples)
        
        baseline = MetricBaseline(
            metric_name=metric_name,
            mean=float(np.mean(arr)),
            std_dev=float(np.std(arr)),
            p50=float(np.percentile(arr, 50)),
            p90=float(np.percentile(arr, 90)),
            p95=float(np.percentile(arr, 95)),
            p99=float(np.percentile(arr, 99)),
            min_val=float(np.min(arr)),
            max_val=float(np.max(arr)),
            sample_count=len(samples),
            collected_at=datetime.utcnow(),
            baseline_type=baseline_type,
        )
        
        # Create or update component baseline
        baseline_obj = self.load_baseline(component)
        if baseline_obj is None:
            baseline_obj = Baseline(component=component)
        
        baseline_obj.add_metric(baseline)
        self.save_baseline(baseline_obj)
        
        return baseline

    def get_baseline_percentile(
        self,
        component: str,
        metric_name: str,
        percentile: float,
    ) -> float | None:
        """Get a specific percentile from a baseline.
        
        Args:
            component: Component name
            metric_name: Metric name
            percentile: Percentile (0-100)
            
        Returns:
            Value at percentile or None if not found
        """
        baseline = self.load_baseline(component)
        if baseline is None:
            return None
        
        metric = baseline.get_metric(metric_name)
        if metric is None:
            return None
        
        percentiles = {
            50: metric.p50,
            90: metric.p90,
            95: metric.p95,
            99: metric.p99,
        }
        return percentiles.get(percentile)

    def is_baseline_stale(self, component: str, max_age_days: int = 7) -> bool:
        """Check if a baseline is stale.
        
        Args:
            component: Component name
            max_age_days: Maximum age in days
            
        Returns:
            True if baseline is older than max_age_days
        """
        baseline = self.load_baseline(component)
        if baseline is None:
            return True
        
        age = datetime.utcnow() - baseline.updated_at
        return age > timedelta(days=max_age_days)

    def compare_to_baseline(
        self,
        component: str,
        metric_name: str,
        current_value: float,
    ) -> dict[str, Any]:
        """Compare a current value to the baseline.
        
        Args:
            component: Component name
            metric_name: Metric name
            current_value: Current measurement
            
        Returns:
            Dictionary with comparison results
        """
        baseline = self.load_baseline(component)
        if baseline is None:
            return {
                "has_baseline": False,
                "current_value": current_value,
                "deviation": None,
                "percent_above_baseline": None,
                "status": "unknown",
            }
        
        metric = baseline.get_metric(metric_name)
        if metric is None:
            return {
                "has_baseline": False,
                "current_value": current_value,
                "deviation": None,
                "percent_above_baseline": None,
                "status": "unknown",
            }
        
        deviation = current_value - metric.p95
        pct_above = (deviation / metric.p95) * 100 if metric.p95 > 0 else 0
        
        # Determine status
        if pct_above >= 100:
            status = "critical"
        elif pct_above >= 50:
            status = "warning"
        else:
            status = "normal"
        
        return {
            "has_baseline": True,
            "current_value": current_value,
            "baseline_p95": metric.p95,
            "deviation": deviation,
            "percent_above_baseline": pct_above,
            "status": status,
            "baseline_std_dev": metric.std_dev,
            "baseline_mean": metric.mean,
            "sample_count": metric.sample_count,
        }

    def list_components(self) -> list[str]:
        """List all components with baselines."""
        components = []
        for path in self.storage_path.glob("*_baseline.json"):
            components.append(path.stem.replace("_baseline", ""))
        return components

    def get_baseline_summary(self, component: str) -> dict[str, Any] | None:
        """Get a summary of a baseline."""
        baseline = self.load_baseline(component)
        if baseline is None:
            return None
        
        return {
            "component": baseline.component,
            "metric_count": len(baseline.metrics),
            "created_at": baseline.created_at.isoformat(),
            "updated_at": baseline.updated_at.isoformat(),
            "is_stale": self.is_baseline_stale(component),
            "metrics": [
                {
                    "name": name,
                    "mean": m.mean,
                    "p95": m.p95,
                    "std_dev": m.std_dev,
                    "sample_count": m.sample_count,
                }
                for name, m in baseline.metrics.items()
            ],
        }


# Baseline collection helpers
class SyntheticTrafficGenerator:
    """Generates synthetic traffic for baseline collection."""

    def __init__(self, base_url: str = "http://localhost:8001"):
        """Initialize generator.
        
        Args:
            base_url: Base URL for the service
        """
        self.base_url = base_url

    async def generate_queries(self, count: int = 100) -> list[float]:
        """Generate synthetic queries and measure latencies.
        
        Args:
            count: Number of queries to generate
            
        Returns:
            List of latencies in seconds
        """
        import aiohttp
        latencies = []
        async with aiohttp.ClientSession() as session:
            for i in range(count):
                start = time.perf_counter()
                try:
                    async with session.get(
                        f"{self.base_url}/health",
                        timeout=aiohttp.ClientTimeout(total=30)
                    ):
                        pass
                except Exception:
                    pass  # Record failure separately if needed
                latency = time.perf_counter() - start
                latencies.append(latency)
        return latencies

    async def generate_recall_queries(self, count: int = 50) -> list[float]:
        """Generate synthetic recall queries.
        
        Args:
            count: Number of queries to generate
            
        Returns:
            List of latencies in seconds
        """
        import aiohttp
        latencies = []
        queries = [
            "test query",
            "performance patterns",
            "memory management",
        ]
        async with aiohttp.ClientSession() as session:
            for i in range(count):
                query = queries[i % len(queries)]
                start = time.perf_counter()
                try:
                    async with session.post(
                        f"{self.base_url}/recall",
                        json={"query": query, "k": 5},
                        timeout=aiohttp.ClientTimeout(total=60)
                    ):
                        pass
                except Exception:
                    pass
                latency = time.perf_counter() - start
                latencies.append(latency)
        return latencies


class ProductionSampler:
    """Samples production metrics for baseline collection."""

    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        """Initialize sampler.
        
        Args:
            prometheus_url: Prometheus server URL
        """
        self.prometheus_url = prometheus_url

    async def sample_metric(
        self,
        query: str,
        duration_minutes: int = 5,
    ) -> list[float]:
        """Sample a metric from Prometheus over a duration.
        
        Args:
            query: Prometheus query
            duration_minutes: Duration to sample over
            
        Returns:
            List of sample values
        """
        import aiohttp
        end = datetime.utcnow()
        start = end - timedelta(minutes=duration_minutes)
        
        query_params = {
            "query": f"rate({query}[1m])",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": "15s",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params=query_params,
            ) as response:
                data = await response.json()
        
        if data.get("status") != "success":
            return []
        
        values = []
        for result in data.get("data", {}).get("result", []):
            for value in result.get("values", []):
                if len(value) == 2:
                    values.append(float(value[1]))
        return values

    async def sample_latency_percentiles(self, metric: str) -> dict[str, float]:
        """Sample latency percentiles from Prometheus.
        
        Args:
            metric: Metric name for latency
            
        Returns:
            Dictionary with p50, p90, p95, p99 values
        """
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Sample for the last 5 minutes
            queries = {
                "p50": f"histogram_quantile(0.50, rate({metric}_bucket[5m]))",
                "p90": f"histogram_quantile(0.90, rate({metric}_bucket[5m]))",
                "p95": f"histogram_quantile(0.95, rate({metric}_bucket[5m]))",
                "p99": f"histogram_quantile(0.99, rate({metric}_bucket[5m]))",
            }
            
            results = {}
            for name, query in queries.items():
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        results[name] = float(result[0].get("value", [0, 0])[1])
        
        return results
