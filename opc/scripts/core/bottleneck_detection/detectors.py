"""
Bottleneck Detection Algorithms

Implements specific detection algorithms for different bottleneck types:
- Database: slow queries, connection pool, indexes, locks
- Memory: leaks, cache growth, embedding memory
- CPU: sustained high usage, embedding generation
- Network: MCP latency, Redis RTT, API latency
"""

from __future__ import annotations
import abc
import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import numpy as np


class BottleneckType(Enum):
    """Types of bottlenecks that can be detected."""
    # Database bottlenecks
    DB_QUERY_SLOW = "db_query_slow"
    DB_POOL_SATURATED = "db_pool_saturated"
    DB_INDEX_MISSING = "db_index_missing"
    DB_LOCK_CONTENTION = "db_lock_contention"
    DB_DEADLOCK = "db_deadlock"

    # Memory bottlenecks
    MEMORY_LEAK = "memory_leak"
    MEMORY_CRITICAL = "memory_critical"
    EMBEDDING_MEMORY_HIGH = "embedding_memory_high"
    CACHE_GROWTH = "cache_growth"

    # CPU bottlenecks
    CPU_HIGH = "cpu_high"
    CPU_SUSTAINED = "cpu_sustained"
    EMBEDDING_CPU_HIGH = "embedding_cpu_high"
    VECTOR_SEARCH_CPU = "vector_search_cpu"

    # Network bottlenecks
    MCP_LATENCY_HIGH = "mcp_latency_high"
    REDIS_LATENCY_HIGH = "redis_latency_high"
    EMBEDDING_API_LATENCY = "embedding_api_latency"
    DB_QUERY_TIME = "db_query_time"


@dataclass
class DetectionResult:
    """Result of a bottleneck detection."""
    bottleneck_type: BottleneckType
    severity: str  # "warning", "critical"
    metric_name: str
    current_value: float
    threshold_value: float
    percent_above_threshold: float
    detected_at: datetime
    duration_seconds: int | None = None
    description: str = ""
    affected_component: str = ""
    recommendations: list[str] = field(default_factory=list)
    runbook_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bottleneck_type": self.bottleneck_type.value,
            "severity": self.severity,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "percent_above_threshold": self.percent_above_threshold,
            "detected_at": self.detected_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "description": self.description,
            "affected_component": self.affected_component,
            "recommendations": self.recommendations,
            "runbook_url": self.runbook_url,
        }


class BaseDetector(abc.ABC):
    """Base class for bottleneck detectors."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize detector with configuration."""
        self.config = config or {}
        self._history: list[dict[str, Any]] = []

    @abc.abstractmethod
    async def detect(self) -> list[DetectionResult]:
        """Run detection and return results."""
        pass

    def _add_to_history(self, data: dict[str, Any]) -> None:
        """Add data point to history."""
        self._history.append({
            **data,
            "timestamp": datetime.utcnow(),
        })
        # Keep only last 1000 points
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

    def _get_history(
        self,
        duration: timedelta | None = None,
    ) -> list[dict[str, Any]]:
        """Get history filtered by duration."""
        if duration is None:
            return self._history.copy()
        
        cutoff = datetime.utcnow() - duration
        return [h for h in self._history if h["timestamp"] >= cutoff]


class DatabaseBottleneckDetector(BaseDetector):
    """Detects database-related bottlenecks."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.prometheus_url = config.get("prometheus_url", "http://localhost:9090")

    async def detect(self) -> list[DetectionResult]:
        """Run database bottleneck detection."""
        results = []
        
        # Parallel detection of different bottleneck types
        tasks = [
            self._detect_slow_queries(),
            self._detect_pool_saturation(),
            self._detect_lock_contention(),
            self._detect_deadlocks(),
        ]
        
        for result in await asyncio.gather(*tasks):
            results.extend(result)
        
        return results

    async def _detect_slow_queries(self) -> list[DetectionResult]:
        """Detect slow database queries."""
        import aiohttp
        
        query = "pg_stat_statements_p95_ms"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])
                        
                        warning_threshold = self.config.get("db_query_latency_warning", 2.0)
                        critical_threshold = self.config.get("db_query_latency_critical", 5.0)
                        
                        if value >= critical_threshold:
                            severity = "critical"
                            threshold = critical_threshold
                        elif value >= warning_threshold:
                            severity = "warning"
                            threshold = warning_threshold
                        else:
                            return results
                        
                        pct_above = ((value - threshold) / threshold) * 100
                        
                        results.append(DetectionResult(
                            bottleneck_type=BottleneckType.DB_QUERY_SLOW,
                            severity=severity,
                            metric_name=query,
                            current_value=value,
                            threshold_value=threshold,
                            percent_above_threshold=pct_above,
                            detected_at=datetime.utcnow(),
                            description=f"Query latency p95 at {value:.2f}s",
                            affected_component="postgresql",
                            recommendations=[
                                "Review slow query log for specific queries",
                                "Check for missing indexes",
                                "Consider query optimization or rewriting",
                                "Review execution plans for affected queries",
                            ],
                            runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#query-latency",
                        ))
                        
                        self._add_to_history({
                            "metric": query,
                            "value": value,
                            "severity": severity,
                        })
        except Exception:
            pass
        
        return results

    async def _detect_pool_saturation(self) -> list[DetectionResult]:
        """Detect connection pool saturation."""
        import aiohttp
        
        query = "pg:pool:utilization:ratio"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])
                        
                        warning_pct = self.config.get("db_pool_warning_pct", 0.70)
                        critical_pct = self.config.get("db_pool_critical_pct", 0.90)
                        
                        if value >= critical_pct:
                            severity = "critical"
                            threshold = critical_pct
                        elif value >= warning_pct:
                            severity = "warning"
                            threshold = warning_pct
                        else:
                            return results
                        
                        pct_above = ((value - threshold) / threshold) * 100
                        
                        results.append(DetectionResult(
                            bottleneck_type=BottleneckType.DB_POOL_SATURATED,
                            severity=severity,
                            metric_name="connection_pool_utilization",
                            current_value=value,
                            threshold_value=threshold,
                            percent_above_threshold=pct_above,
                            detected_at=datetime.utcnow(),
                            description=f"Connection pool at {value*100:.1f}% utilization",
                            affected_component="postgresql",
                            recommendations=[
                                "Increase pool size if appropriate",
                                "Review connection leak potential",
                                "Consider longer connection timeouts",
                                "Implement connection retry logic",
                            ],
                            runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#connection-pool",
                        ))
        except Exception:
            pass
        
        return results

    async def _detect_lock_contention(self) -> list[DetectionResult]:
        """Detect database lock contention."""
        import aiohttp
        
        # Check for waiting queries (indicates lock contention)
        query = 'pg_stat_activity_wait_event{state="active"}'
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    # Any waiting queries is concerning
                    if result and len(result) > 0:
                        results.append(DetectionResult(
                            bottleneck_type=BottleneckType.DB_LOCK_CONTENTION,
                            severity="warning",
                            metric_name="lock_waiters",
                            current_value=len(result),
                            threshold_value=0,
                            percent_above_threshold=100,
                            detected_at=datetime.utcnow(),
                            description=f"{len(result)} queries waiting on locks",
                            affected_component="postgresql",
                            recommendations=[
                                "Identify long-running transactions",
                                "Review transaction isolation levels",
                                "Optimize query ordering to reduce conflicts",
                            ],
                            runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#lock-contention",
                        ))
        except Exception:
            pass
        
        return results

    async def _detect_deadlocks(self) -> list[DetectionResult]:
        """Detect database deadlocks."""
        import aiohttp
        
        # Check for deadlocks in last 5 minutes
        query = 'increase(pg_stat_database_deadlocks[5m])'
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        deadlocks = float(result[0].get("value", [0, 0])[1])
                        
                        if deadlocks > 0:
                            results.append(DetectionResult(
                                bottleneck_type=BottleneckType.DB_DEADLOCK,
                                severity="critical",
                                metric_name="deadlocks_5m",
                                current_value=deadlocks,
                                threshold_value=0,
                                percent_above_threshold=100,
                                detected_at=datetime.utcnow(),
                                description=f"{int(deadlocks)} deadlocks detected in last 5 minutes",
                                affected_component="postgresql",
                                recommendations=[
                                    "Review transaction ordering across queries",
                                    "Identify circular dependencies",
                                    "Consider row-level locking hints",
                                    "Reduce transaction size",
                                ],
                                runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#deadlock",
                            ))
        except Exception:
            pass
        
        return results


class MemoryBottleneckDetector(BaseDetector):
    """Detects memory-related bottlenecks."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.prometheus_url = config.get("prometheus_url", "http://localhost:9090")

    async def detect(self) -> list[DetectionResult]:
        """Run memory bottleneck detection."""
        results = []
        
        tasks = [
            self._detect_high_memory_usage(),
            self._detect_memory_leak(),
            self._detect_embedding_memory(),
            self._detect_cache_growth(),
        ]
        
        for result in await asyncio.gather(*tasks):
            results.extend(result)
        
        return results

    async def _detect_high_memory_usage(self) -> list[DetectionResult]:
        """Detect high memory usage."""
        import aiohttp
        
        query = "system:memory:usage:ratio"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])
                        
                        warning_pct = self.config.get("memory_warning_pct", 0.80)
                        critical_pct = self.config.get("memory_critical_pct", 0.95)
                        
                        if value >= critical_pct:
                            severity = "critical"
                            threshold = critical_pct
                        elif value >= warning_pct:
                            severity = "warning"
                            threshold = warning_pct
                        else:
                            return results
                        
                        pct_above = ((value - threshold) / threshold) * 100
                        
                        results.append(DetectionResult(
                            bottleneck_type=BottleneckType.MEMORY_CRITICAL,
                            severity=severity,
                            metric_name="memory_usage_ratio",
                            current_value=value,
                            threshold_value=threshold,
                            percent_above_threshold=pct_above,
                            detected_at=datetime.utcnow(),
                            description=f"Memory at {value*100:.1f}% usage",
                            affected_component="system",
                            recommendations=[
                                "Check for memory leaks in application",
                                "Review garbage collection frequency",
                                "Consider increasing system memory",
                                "Identify large object allocations",
                            ],
                            runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#memory-critical",
                        ))
        except Exception:
            pass
        
        return results

    async def _detect_memory_leak(self) -> list[DetectionResult]:
        """Detect potential memory leak via trend analysis."""
        # Use history to detect upward trend
        history = self._get_history(timedelta(hours=1))
        
        if len(history) < 10:
            return []
        
        values = [h["value"] for h in history if "value" in h]
        if len(values) < 10:
            return []
        
        # Simple linear regression for trend
        n = len(values)
        x = list(range(n))
        x_mean = n / 2
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return []
        
        slope = numerator / denominator
        
        # If slope indicates consistent growth
        growth_threshold = self.config.get("memory_growth_rate_warning", 0.05)
        
        if slope > growth_threshold:
            return [DetectionResult(
                bottleneck_type=BottleneckType.MEMORY_LEAK,
                severity="warning",
                metric_name="memory_trend",
                current_value=slope,
                threshold_value=growth_threshold,
                percent_above_threshold=((slope - growth_threshold) / growth_threshold) * 100,
                detected_at=datetime.utcnow(),
                description=f"Memory growing at rate {slope:.4f} per sample",
                affected_component="application",
                recommendations=[
                    "Profile memory allocations",
                    "Check for unbounded caches",
                    "Review object retention patterns",
                    "Enable detailed GC logging",
                ],
                runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#memory-leak",
            )]
        
        return []

    async def _detect_embedding_memory(self) -> list[DetectionResult]:
        """Detect high embedding model memory usage."""
        import aiohttp
        
        query = 'process_memory_bytes{type="rss"}'
        results = []
        
        # Convert MB to bytes for threshold
        warning_mb = self.config.get("embedding_memory_warning_mb", 2048)
        warning_bytes = warning_mb * 1024 * 1024
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])
                        
                        if value >= warning_bytes:
                            pct_above = ((value - warning_bytes) / warning_bytes) * 100
                            
                            results.append(DetectionResult(
                                bottleneck_type=BottleneckType.EMBEDDING_MEMORY_HIGH,
                                severity="warning",
                                metric_name="embedding_memory_bytes",
                                current_value=value,
                                threshold_value=warning_bytes,
                                percent_above_threshold=pct_above,
                                detected_at=datetime.utcnow(),
                                description=f"Process memory at {value / (1024**3):.2f} GB",
                                affected_component="embedding_service",
                                recommendations=[
                                    "Implement embedding cache size limits",
                                    "Consider model quantization",
                                    "Add memory cleanup after batch processing",
                                    "Review embedding batch sizes",
                                ],
                                runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#embedding-memory",
                            ))
        except Exception:
            pass
        
        return results

    async def _detect_cache_growth(self) -> list[DetectionResult]:
        """Detect excessive cache growth."""
        import aiohttp
        
        query = "embedding_cache_size"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])
                        
                        # Get cache hit rate
                        hit_query = "rate(cache_hits_total[1h]) / rate(cache_requests_total[1h])"
                        async with session.get(
                            f"{self.prometheus_url}/api/v1/query",
                            params={"query": hit_query},
                        ) as response:
                            hit_data = await response.json()
                        
                        hit_rate = 0.5  # Default
                        if hit_data.get("status") == "success":
                            hit_result = hit_data.get("data", {}).get("result")
                            if hit_result:
                                hit_rate = float(hit_result[0].get("value", [0, 0.5])[1])
                        
                        # Low hit rate with high cache size indicates inefficiency
                        if hit_rate < 0.5:
                            results.append(DetectionResult(
                                bottleneck_type=BottleneckType.CACHE_GROWTH,
                                severity="warning",
                                metric_name="cache_size",
                                current_value=value,
                                threshold_value=100000,  # Arbitrary threshold
                                percent_above_threshold=0,
                                detected_at=datetime.utcnow(),
                                description=f"Cache size {value:.0f} with {hit_rate*100:.1f}% hit rate",
                                affected_component="embedding_cache",
                                recommendations=[
                                    "Review cache eviction policy",
                                    "Consider LRU with TTL",
                                    "Implement cache size limits",
                                    "Analyze cache key patterns",
                                ],
                                runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#cache-growth",
                            ))
        except Exception:
            pass
        
        return results


class CPUBottleneckDetector(BaseDetector):
    """Detects CPU-related bottlenecks."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.prometheus_url = config.get("prometheus_url", "http://localhost:9090")

    async def detect(self) -> list[DetectionResult]:
        """Run CPU bottleneck detection."""
        results = []
        
        tasks = [
            self._detect_high_cpu(),
            self._detect_sustained_cpu(),
            self._detect_embedding_cpu(),
        ]
        
        for result in await asyncio.gather(*tasks):
            results.extend(result)
        
        return results

    async def _detect_high_cpu(self) -> list[DetectionResult]:
        """Detect high CPU usage."""
        import aiohttp
        
        query = "system:cpu:usage:ratio"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])
                        
                        warning_pct = self.config.get("cpu_warning_pct", 0.80)
                        critical_pct = self.config.get("cpu_critical_pct", 0.95)
                        
                        if value >= critical_pct:
                            severity = "critical"
                            threshold = critical_pct
                        elif value >= warning_pct:
                            severity = "warning"
                            threshold = warning_pct
                        else:
                            return results
                        
                        pct_above = ((value - threshold) / threshold) * 100
                        
                        results.append(DetectionResult(
                            bottleneck_type=BottleneckType.CPU_HIGH,
                            severity=severity,
                            metric_name="cpu_usage_ratio",
                            current_value=value,
                            threshold_value=threshold,
                            percent_above_threshold=pct_above,
                            detected_at=datetime.utcnow(),
                            description=f"CPU at {value*100:.1f}% usage",
                            affected_component="system",
                            recommendations=[
                                "Profile CPU hotspots",
                                "Review async task scheduling",
                                "Consider horizontal scaling",
                                "Optimize hot paths",
                            ],
                            runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#cpu-usage",
                        ))
        except Exception:
            pass
        
        return results

    async def _detect_sustained_cpu(self) -> list[DetectionResult]:
        """Detect sustained high CPU usage over time."""
        import aiohttp
        
        # Check rate of CPU usage over last 5 minutes
        query = 'rate(system:cpu:usage:ratio[5m])'
        results = []
        
        sustained_duration = self.config.get("cpu_sustained_duration", 300)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        rate = float(result[0].get("value", [0, 0])[1])
                        
                        if rate > 0.8:  # Sustained above 80%
                            results.append(DetectionResult(
                                bottleneck_type=BottleneckType.CPU_SUSTAINED,
                                severity="warning",
                                metric_name="cpu_sustained_rate",
                                current_value=rate,
                                threshold_value=0.8,
                                percent_above_threshold=((rate - 0.8) / 0.8) * 100,
                                detected_at=datetime.utcnow(),
                                duration_seconds=sustained_duration,
                                description=f"CPU sustained at {rate*100:.1f}% for {sustained_duration}s",
                                affected_component="system",
                                recommendations=[
                                    "Check for runaway processes",
                                    "Review background task scheduling",
                                    "Consider CPU-bound operation optimization",
                                    "Implement CPU throttling if needed",
                                ],
                                runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#cpu-sustained",
                            ))
        except Exception:
            pass
        
        return results

    async def _detect_embedding_cpu(self) -> list[DetectionResult]:
        """Detect high CPU during embedding generation."""
        import aiohttp
        
        query = "embedding:latency:percentiles_seconds{p95}"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        latency_p95 = float(result[0].get("value", [0, 0])[1])
                        
                        # Compare to baseline
                        baseline = self.config.get("embedding_latency_baseline", 5.0)
                        
                        if latency_p95 > baseline * 1.5:
                            pct_above = ((latency_p95 - baseline) / baseline) * 100
                            
                            results.append(DetectionResult(
                                bottleneck_type=BottleneckType.EMBEDDING_CPU_HIGH,
                                severity="warning",
                                metric_name="embedding_latency_p95",
                                current_value=latency_p95,
                                threshold_value=baseline,
                                percent_above_threshold=pct_above,
                                detected_at=datetime.utcnow(),
                                description=f"Embedding p95 latency at {latency_p95:.2f}s",
                                affected_component="embedding_service",
                                recommendations=[
                                    "Check embedding model load",
                                    "Consider batching optimization",
                                    "Review GPU utilization if applicable",
                                    "Implement embedding request queuing",
                                ],
                                runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#embedding-cpu",
                            ))
        except Exception:
            pass
        
        return results


class NetworkBottleneckDetector(BaseDetector):
    """Detects network-related bottlenecks."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.prometheus_url = config.get("prometheus_url", "http://localhost:9090")

    async def detect(self) -> list[DetectionResult]:
        """Run network bottleneck detection."""
        results = []
        
        tasks = [
            self._detect_mcp_latency(),
            self._detect_redis_latency(),
            self._detect_embedding_api_latency(),
        ]
        
        for result in await asyncio.gather(*tasks):
            results.extend(result)
        
        return results

    async def _detect_mcp_latency(self) -> list[DetectionResult]:
        """Detect high MCP client latency."""
        import aiohttp
        
        query = "histogram_quantile(0.95, rate(mcp_tool_latency_seconds_bucket[5m]))"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])  # in seconds
                        
                        warning_ms = self.config.get("mcp_latency_warning_ms", 500)
                        critical_ms = self.config.get("mcp_latency_critical_ms", 2000)
                        
                        value_ms = value * 1000
                        
                        if value_ms >= critical_ms:
                            severity = "critical"
                            threshold_ms = critical_ms
                        elif value_ms >= warning_ms:
                            severity = "warning"
                            threshold_ms = warning_ms
                        else:
                            return results
                        
                        pct_above = ((value_ms - threshold_ms) / threshold_ms) * 100
                        
                        results.append(DetectionResult(
                            bottleneck_type=BottleneckType.MCP_LATENCY_HIGH,
                            severity=severity,
                            metric_name="mcp_latency_p95",
                            current_value=value_ms,
                            threshold_value=threshold_ms,
                            percent_above_threshold=pct_above,
                            detected_at=datetime.utcnow(),
                            description=f"MCP p95 latency at {value_ms:.1f}ms",
                            affected_component="mcp_client",
                            recommendations=[
                                "Check MCP server health",
                                "Review network latency to server",
                                "Consider connection pooling for MCP",
                                "Implement request timeout optimization",
                            ],
                            runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#mcp-latency",
                        ))
        except Exception:
            pass
        
        return results

    async def _detect_redis_latency(self) -> list[DetectionResult]:
        """Detect high Redis operation latency."""
        import aiohttp
        
        query = "histogram_quantile(0.95, rate(redis_operation_latency_seconds_bucket[5m]))"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])
                        
                        warning_ms = self.config.get("redis_latency_warning_ms", 10)
                        critical_ms = self.config.get("redis_latency_critical_ms", 50)
                        
                        value_ms = value * 1000
                        
                        if value_ms >= critical_ms:
                            severity = "critical"
                            threshold_ms = critical_ms
                        elif value_ms >= warning_ms:
                            severity = "warning"
                            threshold_ms = warning_ms
                        else:
                            return results
                        
                        pct_above = ((value_ms - threshold_ms) / threshold_ms) * 100
                        
                        results.append(DetectionResult(
                            bottleneck_type=BottleneckType.REDIS_LATENCY_HIGH,
                            severity=severity,
                            metric_name="redis_latency_p95",
                            current_value=value_ms,
                            threshold_value=threshold_ms,
                            percent_above_threshold=pct_above,
                            detected_at=datetime.utcnow(),
                            description=f"Redis p95 latency at {value_ms:.1f}ms",
                            affected_component="redis",
                            recommendations=[
                                "Check Redis server load",
                                "Review Redis slow log",
                                "Consider Redis cluster for scaling",
                                "Implement operation pipelining",
                            ],
                            runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#redis-latency",
                        ))
        except Exception:
            pass
        
        return results

    async def _detect_embedding_api_latency(self) -> list[DetectionResult]:
        """Detect high embedding API latency."""
        import aiohttp
        
        query = "histogram_quantile(0.95, rate(embedding_generation_duration_seconds_bucket[5m]))"
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": query},
                ) as response:
                    data = await response.json()
                
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result")
                    if result:
                        value = float(result[0].get("value", [0, 0])[1])
                        
                        warning_s = self.config.get("embedding_api_latency_warning_s", 5.0)
                        critical_s = self.config.get("embedding_api_latency_critical_s", 15.0)
                        
                        if value >= critical_s:
                            severity = "critical"
                            threshold = critical_s
                        elif value >= warning_s:
                            severity = "warning"
                            threshold = warning_s
                        else:
                            return results
                        
                        pct_above = ((value - threshold) / threshold) * 100
                        
                        results.append(DetectionResult(
                            bottleneck_type=BottleneckType.EMBEDDING_API_LATENCY,
                            severity=severity,
                            metric_name="embedding_api_latency_p95",
                            current_value=value,
                            threshold_value=threshold,
                            percent_above_threshold=pct_above,
                            detected_at=datetime.utcnow(),
                            description=f"Embedding API p95 latency at {value:.2f}s",
                            affected_component="embedding_api",
                            recommendations=[
                                "Check embedding provider status",
                                "Review API rate limits",
                                "Consider local embedding model",
                                "Implement request batching",
                            ],
                            runbook_url="https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#embedding-api-latency",
                        ))
        except Exception:
            pass
        
        return results
