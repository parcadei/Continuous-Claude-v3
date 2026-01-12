"""
Comprehensive Metrics System for Continuous-Claude-v3

Provides Prometheus-compatible metrics with decorators for easy instrumentation.
Supports per-script metrics, system metrics, and custom collectors.

Usage:
    from scripts.core.metrics import (
        metrics, track_latency, track_counter, track_gauge,
        MemoryDaemonMetrics, RecallMetrics, StoreMetrics,
        StreamMonitorMetrics, MCPMetrics, SystemMetrics
    )

    # Decorator usage
    @track_latency("my_function", labels={"component": "test"})
    async def my_function():
        ...

    # Direct metric updates
    metrics.memory_daemon_cycles.inc()
    metrics.postgres_pool_size.set(10)
"""

from __future__ import annotations

import asyncio
import gc
import os
import resource
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable

from prometheus_client import Counter, Gauge, Histogram, Info, REGISTRY, CollectorRegistry
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, multiprocess, exposition

# =============================================================================
# Metric Definitions
# =============================================================================

# Registry for metrics (allows testing with isolated registries)
_metrics_registry = REGISTRY

# -----------------------------------------------------------------------------
# Per-Script Metrics: Memory Daemon
# -----------------------------------------------------------------------------

memory_daemon_cycles = Counter(
    "memory_daemon_cycles_total",
    "Total number of daemon poll cycles completed",
    registry=_metrics_registry,
)

memory_daemon_extractions = Counter(
    "memory_daemon_extractions_total",
    "Total number of memory extractions started",
    ["session_id", "project"],
    registry=_metrics_registry,
)

memory_daemon_extraction_duration = Histogram(
    "memory_daemon_extraction_duration_seconds",
    "Time spent on each extraction attempt",
    ["status"],  # success, failed, skipped
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=_metrics_registry,
)

memory_daemon_queue_depth = Gauge(
    "memory_daemon_queue_depth",
    "Current number of pending extractions in queue",
    registry=_metrics_registry,
)

memory_daemon_active_extractions = Gauge(
    "memory_daemon_active_extractions",
    "Number of currently running extractions",
    registry=_metrics_registry,
)

memory_daemon_restarts = Counter(
    "memory_daemon_restarts_total",
    "Total number of daemon restarts",
    ["reason"],  # crash, manual, upgrade
    registry=_metrics_registry,
)

memory_daemon_stale_sessions = Histogram(
    "memory_daemon_stale_sessions_found",
    "Number of stale sessions found per cycle",
    buckets=(0, 1, 2, 5, 10, 20, 50),
    registry=_metrics_registry,
)

# -----------------------------------------------------------------------------
# Per-Script Metrics: Recall Learnings
# -----------------------------------------------------------------------------

recall_queries_total = Counter(
    "recall_queries_total",
    "Total number of recall queries",
    ["backend", "search_type"],  # sqlite/postgres, text/vector/hybrid
    registry=_metrics_registry,
)

recall_query_latency = Histogram(
    "recall_query_latency_seconds",
    "Latency of recall queries by search type",
    ["backend", "search_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=_metrics_registry,
)

recall_cache_hits = Counter(
    "recall_cache_hits_total",
    "Total cache hits",
    ["cache_type"],  # embedding, results
    registry=_metrics_registry,
)

recall_cache_misses = Counter(
    "recall_cache_misses_total",
    "Total cache misses",
    ["cache_type"],  # embedding, results
    registry=_metrics_registry,
)

recall_backend_switches = Counter(
    "recall_backend_switches_total",
    "Number of times backend switched during query",
    ["from_backend", "to_backend"],
    registry=_metrics_registry,
)

recall_results_returned = Histogram(
    "recall_results_returned",
    "Number of results returned per query",
    ["backend", "search_type"],
    buckets=(0, 1, 3, 5, 10, 20, 50),
    registry=_metrics_registry,
)

recall_embedding_latency = Histogram(
    "recall_embedding_latency_seconds",
    "Time to generate query embeddings",
    ["provider"],  # local, voyage
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=_metrics_registry,
)

# -----------------------------------------------------------------------------
# Per-Script Metrics: Store Learning
# -----------------------------------------------------------------------------

store_operations_total = Counter(
    "store_operations_total",
    "Total store operations",
    ["backend", "status"],  # postgres/sqlite, success/skipped/error
    registry=_metrics_registry,
)

store_latency = Histogram(
    "store_latency_seconds",
    "Latency of store operations by phase",
    ["backend", "phase"],  # embedding, dedup, insert
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=_metrics_registry,
)

store_deduplication_skipped = Counter(
    "store_deduplication_skipped_total",
    "Number of learnings skipped due to deduplication",
    ["backend", "reason"],  # similarity_threshold, exact_match
    registry=_metrics_registry,
)

store_embedding_time = Histogram(
    "store_embedding_time_seconds",
    "Time to generate embeddings for stored learnings",
    ["provider"],  # local, voyage
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=_metrics_registry,
)

store_content_length = Histogram(
    "store_content_length_bytes",
    "Content length of stored learnings",
    ["backend"],
    buckets=(100, 500, 1000, 2000, 5000, 10000, 50000),
    registry=_metrics_registry,
)

store_learning_types = Counter(
    "store_learning_types_total",
    "Count of learnings by type",
    ["type"],  # FAILED_APPROACH, WORKING_SOLUTION, etc.
    registry=_metrics_registry,
)

store_confidence_levels = Counter(
    "store_confidence_levels_total",
    "Count of learnings by confidence level",
    ["level"],  # high, medium, low
    registry=_metrics_registry,
)

# -----------------------------------------------------------------------------
# Per-Script Metrics: Stream Monitor
# -----------------------------------------------------------------------------

stream_events_processed = Counter(
    "stream_events_processed_total",
    "Total number of stream events processed",
    ["agent_id", "event_type"],  # thinking, tool_use, tool_result, text, error
    registry=_metrics_registry,
)

stream_stuck_detections = Counter(
    "stream_stuck_detections_total",
    "Total number of stuck agent detections",
    ["agent_id", "reason"],  # consecutive_tool, consecutive_thinking
    registry=_metrics_registry,
)

stream_lag_seconds = Histogram(
    "stream_lag_seconds",
    "Lag between event occurrence and processing",
    ["agent_id"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=_metrics_registry,
)

stream_turn_count = Gauge(
    "stream_turn_count",
    "Current turn count for monitored agent",
    ["agent_id"],
    registry=_metrics_registry,
)

stream_event_queue_depth = Gauge(
    "stream_event_queue_depth",
    "Number of events queued for processing",
    ["agent_id"],
    registry=_metrics_registry,
)

stream_redis_publishes = Counter(
    "stream_redis_publishes_total",
    "Total events published to Redis",
    ["agent_id", "status"],  # success, failed
    registry=_metrics_registry,
)

stream_active_monitors = Gauge(
    "stream_active_monitors",
    "Number of currently active stream monitors",
    registry=_metrics_registry,
)

# -----------------------------------------------------------------------------
# Per-Script Metrics: MCP Client
# -----------------------------------------------------------------------------

mcp_connection_state = Gauge(
    "mcp_connection_state",
    "Connection state per server (0=disconnected, 1=connected)",
    ["server_name", "transport"],  # stdio, sse, http
    registry=_metrics_registry,
)

mcp_tool_calls = Counter(
    "mcp_tool_calls_total",
    "Total MCP tool calls",
    ["server_name", "tool_name", "status"],  # success, error, retry
    registry=_metrics_registry,
)

mcp_tool_latency = Histogram(
    "mcp_tool_latency_seconds",
    "Latency of MCP tool calls",
    ["server_name", "tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=_metrics_registry,
)

mcp_connection_latency = Histogram(
    "mcp_connection_latency_seconds",
    "Time to establish MCP connections",
    ["server_name", "transport"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=_metrics_registry,
)

mcp_cache_hits = Counter(
    "mcp_cache_hits_total",
    "Total cache hits for tool listings",
    ["server_name"],
    registry=_metrics_registry,
)

mcp_cache_misses = Counter(
    "mcp_cache_misses_total",
    "Total cache misses for tool listings",
    ["server_name"],
    registry=_metrics_registry,
)

mcp_retries = Counter(
    "mcp_retries_total",
    "Total retry attempts",
    ["server_name", "tool_name"],
    registry=_metrics_registry,
)

mcp_active_connections = Gauge(
    "mcp_active_connections",
    "Number of active MCP connections",
    registry=_metrics_registry,
)

mcp_servers_connected = Gauge(
    "mcp_servers_connected",
    "Number of MCP servers currently connected",
    registry=_metrics_registry,
)

mcp_tools_available = Gauge(
    "mcp_tools_available",
    "Number of tools available per server",
    ["server_name"],
    registry=_metrics_registry,
)

# -----------------------------------------------------------------------------
# System Metrics: PostgreSQL
# -----------------------------------------------------------------------------

postgres_pool_size = Gauge(
    "postgres_pool_size",
    "Current size of PostgreSQL connection pool",
    ["state"],  # total, idle, busy
    registry=_metrics_registry,
)

postgres_pool_waiters = Gauge(
    "postgres_pool_waiters",
    "Number of threads waiting for connection",
    registry=_metrics_registry,
)

postgres_pool_acquire_time = Histogram(
    "postgres_pool_acquire_time_seconds",
    "Time to acquire connection from pool",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=_metrics_registry,
)

postgres_queries_total = Counter(
    "postgres_queries_total",
    "Total PostgreSQL queries",
    ["query_type"],  # select, insert, update, delete
    registry=_metrics_registry,
)

postgres_query_latency = Histogram(
    "postgres_query_latency_seconds",
    "Latency of PostgreSQL queries",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=_metrics_registry,
)

postgres_connection_errors = Counter(
    "postgres_connection_errors_total",
    "Total PostgreSQL connection errors",
    ["error_type"],  # connection_refused, timeout, auth
    registry=_metrics_registry,
)

postgres_active_transactions = Gauge(
    "postgres_active_transactions",
    "Number of active transactions",
    registry=_metrics_registry,
)

# -----------------------------------------------------------------------------
# System Metrics: Redis
# -----------------------------------------------------------------------------

redis_memory_bytes = Gauge(
    "redis_memory_bytes",
    "Redis memory usage in bytes",
    registry=_metrics_registry,
)

redis_memory_peak_bytes = Gauge(
    "redis_memory_peak_bytes",
    "Redis peak memory usage in bytes",
    registry=_metrics_registry,
)

redis_operations_total = Counter(
    "redis_operations_total",
    "Total Redis operations",
    ["operation"],  # get, set, lpush, expire, etc.
    registry=_metrics_registry,
)

redis_operation_latency = Histogram(
    "redis_operation_latency_seconds",
    "Latency of Redis operations",
    ["operation"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
    registry=_metrics_registry,
)

redis_connected_clients = Gauge(
    "redis_connected_clients",
    "Number of connected Redis clients",
    registry=_metrics_registry,
)

redis_key_count = Gauge(
    "redis_key_count",
    "Number of keys in Redis database",
    registry=_metrics_registry,
)

redis_expired_keys = Counter(
    "redis_expired_keys_total",
    "Total number of expired keys",
    registry=_metrics_registry,
)

redis_evicted_keys = Counter(
    "redis_evicted_keys_total",
    "Total number of evicted keys",
    registry=_metrics_registry,
)

# -----------------------------------------------------------------------------
# System Metrics: Process
# -----------------------------------------------------------------------------

process_memory_bytes = Gauge(
    "process_memory_bytes",
    "Process memory usage in bytes",
    ["type"],  # rss, vms, shared
    registry=_metrics_registry,
)

process_cpu_percent = Gauge(
    "process_cpu_percent",
    "Process CPU usage percentage",
    registry=_metrics_registry,
)

process_open_fds = Gauge(
    "process_open_fds",
    "Number of open file descriptors",
    registry=_metrics_registry,
)

process_fd_limit = Gauge(
    "process_fd_limit",
    "File descriptor limit",
    registry=_metrics_registry,
)

process_thread_count = Gauge(
    "process_thread_count",
    "Number of process threads",
    registry=_metrics_registry,
)

process_gc_collects = Counter(
    "process_gc_collects_total",
    "Total garbage collection runs",
    ["generation"],  # 0, 1, 2
    registry=_metrics_registry,
)

process_gc_time = Counter(
    "process_gc_time_seconds",
    "Total time spent in garbage collection",
    ["generation"],
    registry=_metrics_registry,
)

process_start_time_seconds = Gauge(
    "process_start_time_seconds",
    "Process start time in Unix timestamp",
    registry=_metrics_registry,
)

process_uptime_seconds = Gauge(
    "process_uptime_seconds",
    "Process uptime in seconds",
    registry=_metrics_registry,
)

# =============================================================================
# Decorators for Easy Instrumentation
# =============================================================================

def track_latency(
    metric_name: str,
    labels: dict[str, str] | None = None,
    histogram: Histogram | None = None,
) -> Callable:
    """Decorator to track function latency.

    Args:
        metric_name: Name of the histogram metric to use
        labels: Static labels to apply to all observations
        histogram: Optional pre-configured Histogram (auto-created if not provided)

    Usage:
        @track_latency("my_function", labels={"component": "test"})
        async def my_function():
            ...

        @track_latency("database_query")
        def query_db():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                # Get the histogram from module-level metric
                metric = globals().get(metric_name)
                if metric and isinstance(metric, Histogram):
                    obs_labels = labels or {}
                    metric.labels(**obs_labels).observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                metric = globals().get(metric_name)
                if metric and isinstance(metric, Histogram):
                    obs_labels = labels or {}
                    metric.labels(**obs_labels).observe(duration)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_counter(
    metric_name: str,
    labels: dict[str, str] | None = None,
) -> Callable:
    """Decorator to increment a counter on function entry/exit.

    Args:
        metric_name: Name of the counter metric to use
        labels: Static labels to apply to all increments

    Usage:
        @track_counter("api_requests", labels={"endpoint": "/home"})
        def handle_request():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            metric = globals().get(metric_name)
            if metric and isinstance(metric, Counter):
                obs_labels = labels or {}
                metric.labels(**obs_labels).inc()
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            metric = globals().get(metric_name)
            if metric and isinstance(metric, Counter):
                obs_labels = labels or {}
                metric.labels(**obs_labels).inc()
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_gauge(
    metric_name: str,
    operation: str = "set",  # set, inc, dec
    labels: dict[str, str] | None = None,
) -> Callable:
    """Decorator to update a gauge on function entry.

    Args:
        metric_name: Name of the gauge metric to use
        operation: Operation to perform (set, inc, dec)
        labels: Static labels to apply

    Usage:
        @track_gauge("active_requests", operation="inc", labels={"service": "api"})
        def handle_request():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            metric = globals().get(metric_name)
            if metric and isinstance(metric, Gauge):
                obs_labels = labels or {}
                if operation == "inc":
                    metric.labels(**obs_labels).inc()
                elif operation == "dec":
                    metric.labels(**obs_labels).dec()
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            metric = globals().get(metric_name)
            if metric and isinstance(metric, Gauge):
                obs_labels = labels or {}
                if operation == "inc":
                    metric.labels(**obs_labels).inc()
                elif operation == "dec":
                    metric.labels(**obs_labels).dec()
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def timed_operation(
    metric_name: str,
    labels: dict[str, str] | None = None,
    histogram: Histogram | None = None,
):
    """Context manager to track operation duration.

    Usage:
        with timed_operation("database_query", labels={"query": "select_users"}):
            await db.execute("SELECT ...")
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        if histogram is None:
            histogram = globals().get(metric_name)
        if histogram and isinstance(histogram, Histogram):
            obs_labels = labels or {}
            histogram.labels(**obs_labels).observe(duration)


# =============================================================================
# Context Managers for Script-Specific Metrics
# =============================================================================

class MemoryDaemonMetrics:
    """Metrics context for memory_daemon.py"""

    @contextmanager
    def extraction(self, session_id: str, project: str):
        """Track a single extraction operation."""
        memory_daemon_extractions.labels(session_id=session_id, project=project or "unknown").inc()
        start = time.perf_counter()
        status = "unknown"
        try:
            yield
            status = "success"
        except Exception:
            status = "failed"
            raise
        finally:
            duration = time.perf_counter() - start
            memory_daemon_extraction_duration.labels(status=status).observe(duration)

    def record_cycle(self, stale_count: int):
        """Record a daemon cycle completion."""
        memory_daemon_cycles.inc()
        memory_daemon_stale_sessions.observe(stale_count)

    def update_queue_state(self, queue_depth: int, active: int):
        """Update queue and active extraction counts."""
        memory_daemon_queue_depth.set(queue_depth)
        memory_daemon_active_extractions.set(active)


class RecallMetrics:
    """Metrics context for recall_learnings.py"""

    @contextmanager
    def query(self, backend: str, search_type: str):
        """Track a recall query."""
        start = time.perf_counter()
        recall_queries_total.labels(backend=backend, search_type=search_type).inc()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            recall_query_latency.labels(backend=backend, search_type=search_type).observe(duration)

    def record_embedding_time(self, provider: str, duration: float):
        """Record embedding generation time."""
        recall_embedding_latency.labels(provider=provider).observe(duration)

    def record_cache_hit(self, cache_type: str):
        """Record a cache hit."""
        recall_cache_hits.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str):
        """Record a cache miss."""
        recall_cache_misses.labels(cache_type=cache_type).inc()


class StoreMetrics:
    """Metrics context for store_learning.py"""

    @contextmanager
    def store(self, backend: str):
        """Track a store operation."""
        start = time.perf_counter()
        status = "unknown"
        try:
            yield
            status = "success"
        except Exception as e:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start
            store_operations_total.labels(backend=backend, status=status).inc()
            store_latency.labels(backend=backend, phase="total").observe(duration)

    def record_embedding_time(self, provider: str, duration: float):
        """Record embedding generation time."""
        store_embedding_time.labels(provider=provider).observe(duration)

    def record_deduplication(self, backend: str, skipped: bool, reason: str | None = None):
        """Record deduplication outcome."""
        if skipped:
            store_deduplication_skipped.labels(backend=backend, reason=reason or "similarity").inc()

    def record_learning_type(self, learning_type: str):
        """Record the type of learning stored."""
        store_learning_types.labels(type=learning_type).inc()

    def record_confidence(self, level: str):
        """Record confidence level."""
        store_confidence_levels.labels(level=level).inc()


class StreamMonitorMetrics:
    """Metrics context for stream_monitor.py"""

    def record_event(self, agent_id: str, event_type: str):
        """Record a processed event."""
        stream_events_processed.labels(agent_id=agent_id, event_type=event_type).inc()

    def record_stuck_detection(self, agent_id: str, reason: str):
        """Record a stuck detection."""
        stream_stuck_detections.labels(agent_id=agent_id, reason=reason).inc()

    def update_turn_count(self, agent_id: str, count: int):
        """Update turn count gauge."""
        stream_turn_count.labels(agent_id=agent_id).set(count)

    def update_queue_depth(self, agent_id: str, depth: int):
        """Update queue depth gauge."""
        stream_event_queue_depth.labels(agent_id=agent_id).set(depth)

    def record_redis_publish(self, agent_id: str, success: bool):
        """Record Redis publish attempt."""
        status = "success" if success else "failed"
        stream_redis_publishes.labels(agent_id=agent_id, status=status).inc()


class MCPMetrics:
    """Metrics context for MCP client operations"""

    def record_connection(self, server_name: str, transport: str, duration: float, success: bool):
        """Record a connection attempt."""
        if success:
            mcp_connection_state.labels(server_name=server_name, transport=transport).set(1)
            mcp_connection_latency.labels(server_name=server_name, transport=transport).observe(duration)

    def record_disconnection(self, server_name: str, transport: str):
        """Record a disconnection."""
        mcp_connection_state.labels(server_name=server_name, transport=transport).set(0)

    def record_tool_call(
        self,
        server_name: str,
        tool_name: str,
        duration: float,
        success: bool,
        retries: int = 0,
    ):
        """Record a tool call."""
        status = "success" if success else "error"
        mcp_tool_calls.labels(server_name=server_name, tool_name=tool_name, status=status).inc()
        mcp_tool_latency.labels(server_name=server_name, tool_name=tool_name).observe(duration)
        if retries > 0:
            mcp_retries.labels(server_name=server_name, tool_name=tool_name).inc(retries)

    def record_cache_hit(self, server_name: str):
        """Record a tool cache hit."""
        mcp_cache_hits.labels(server_name=server_name).inc()

    def record_cache_miss(self, server_name: str):
        """Record a tool cache miss."""
        mcp_cache_misses.labels(server_name=server_name).inc()

    def update_connection_count(self, connected_count: int):
        """Update connected server count."""
        mcp_servers_connected.set(connected_count)


# -----------------------------------------------------------------------------
# Webhook & External API Metrics
# -----------------------------------------------------------------------------

alert_webhook_delivery_total = Counter(
    "alert_webhook_delivery_total",
    "Total alert webhook delivery attempts",
    ["webhook_url", "status"],  # success, failed
    registry=_metrics_registry,
)

alert_webhook_response_time = Histogram(
    "alert_webhook_response_time_seconds",
    "Alert webhook response time",
    ["webhook_url"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=_metrics_registry,
)

external_api_requests = Counter(
    "external_api_requests_total",
    "Total external API requests",
    ["api_name", "endpoint", "status"],
    registry=_metrics_registry,
)

external_api_response_time = Histogram(
    "external_api_response_time_seconds",
    "External API response time",
    ["api_name", "endpoint"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=_metrics_registry,
)


class WebhookMetrics:
    """Metrics for webhook and external API monitoring"""

    def __init__(self):
        self._start_time = time.time()

    def record_webhook_delivery(self, webhook_url: str, success: bool, duration: float):
        """Record a webhook delivery attempt."""
        status = "success" if success else "failed"
        alert_webhook_delivery_total.labels(webhook_url=webhook_url, status=status).inc()
        alert_webhook_response_time.labels(webhook_url=webhook_url).observe(duration)

    def record_external_api_request(
        self, api_name: str, endpoint: str, success: bool, status_code: int, duration: float
    ):
        """Record an external API request."""
        status = f"{status_code}" if success else f"{status_code}_error"
        external_api_requests.labels(api_name=api_name, endpoint=endpoint, status=status).inc()
        external_api_response_time.labels(api_name=api_name, endpoint=endpoint).observe(duration)


class SystemMetrics:
    """System-level metrics collector"""

    def __init__(self):
        self._pid = os.getpid()
        self._start_time = time.time()

    def collect(self):
        """Collect all system metrics."""
        self._collect_process_metrics()
        self._collect_memory_metrics()
        self._collect_fd_metrics()

    def _collect_process_metrics(self):
        """Collect process-level metrics."""
        try:
            import psutil
            proc = psutil.Process(self._pid)

            # Memory
            mem_info = proc.memory_info()
            process_memory_bytes.labels(type="rss").set(mem_info.rss)
            process_memory_bytes.labels(type="vms").set(mem_info.vms)
            process_memory_bytes.labels(type="shared").set(mem_info.shared)

            # CPU
            cpu_percent = proc.cpu_percent()
            process_cpu_percent.set(cpu_percent)

            # Threads
            process_thread_count.set(proc.num_threads())

        except ImportError:
            # Fallback without psutil
            self._collect_process_metrics_fallback()

    def _collect_process_metrics_fallback(self):
        """Fallback process metrics without psutil."""
        # RSS via resource module
        usage = resource.getrusage(resource.RUSAGE_SELF)
        process_memory_bytes.labels(type="rss").set(usage.ru_maxrss * 1024)  # KB to bytes

        # File descriptors
        try:
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            process_fd_limit.set(hard)
            process_open_fds.set(soft)  # Approximate
        except Exception:
            pass

    def _collect_memory_metrics(self):
        """Collect Python memory/GC metrics."""
        gc.collect()
        process_gc_collects.labels(generation="0").inc()

    def _collect_fd_metrics(self):
        """Collect file descriptor metrics."""
        try:
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            process_fd_limit.set(hard)
            process_open_fds.set(soft)  # This is limit, not actual usage
        except Exception:
            pass

    def update_uptime(self):
        """Update process uptime."""
        process_uptime_seconds.set(time.time() - self._start_time)


# =============================================================================
# Metrics Endpoint Helpers
# =============================================================================

def generate_metrics() -> bytes:
    """Generate Prometheus metrics output.

    Returns:
        bytes: Metrics in Prometheus exposition format
    """
    return generate_latest(_metrics_registry)


def get_content_type() -> str:
    """Get the content type for metrics response."""
    return CONTENT_TYPE_LATEST


def prometheus_metrics():
    """WSGI app for /metrics endpoint.

    Usage with FastAPI:
        app = FastAPI()
        @app.get("/metrics")
        async def metrics():
            return Response(
                content=generate_metrics(),
                media_type=get_content_type()
            )
    """
    from starlette.responses import Response
    from starlette.requests import Request
    from starlette.routing import Route
    from starlette.applications import Starlette

    async def metrics_handler(request: Request) -> Response:
        return Response(
            content=generate_metrics(),
            media_type=get_content_type(),
        )

    return Starlette(routes=[Route("/metrics", metrics_handler)])


# =============================================================================
# Custom Collectors
# =============================================================================

class PostgresPoolCollector:
    """Custom collector for PostgreSQL pool metrics.

    Usage:
        collector = PostgresPoolCollector(get_pool)
        REGISTRY.register(collector)
    """

    def __init__(self, pool_getter: Callable):
        """Initialize collector with pool getter function.

        Args:
            pool_getter: Callable that returns the asyncpg Pool
        """
        self.pool_getter = pool_getter

    async def collect(self):
        """Collect pool metrics."""
        pool = await self.pool_getter()
        if pool is None:
            return

        # Pool size metrics
        yield GaugeMetricFamily(
            "postgres_pool_size_total",
            "Total pool size",
            value=pool.get_size(),
        )
        yield GaugeMetricFamily(
            "postgres_pool_size_idle",
            "Number of idle connections",
            value=pool.get_idle_size(),
        )
        yield GaugeMetricFamily(
            "postgres_pool_size_busy",
            "Number of busy connections",
            value=pool.get_size() - pool.get_idle_size(),
        )

    def describe(self):
        """Describe metrics for registration."""
        return []


class RedisStatsCollector:
    """Custom collector for Redis statistics.

    Usage:
        collector = RedisStatsCollector(redis_client)
        REGISTRY.register(collector)
    """

    def __init__(self, redis_client):
        """Initialize collector with Redis client.

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client

    def collect(self):
        """Collect Redis metrics."""
        try:
            info = self.redis.info()

            # Memory
            yield GaugeMetricFamily(
                "redis_memory_bytes",
                "Redis memory usage",
                value=info.get("used_memory", 0),
            )
            yield GaugeMetricFamily(
                "redis_memory_peak_bytes",
                "Redis peak memory usage",
                value=info.get("used_memory_peak", 0),
            )

            # Clients
            yield GaugeMetricFamily(
                "redis_connected_clients",
                "Number of connected clients",
                value=info.get("connected_clients", 0),
            )

            # Keys
            yield GaugeMetricFamily(
                "redis_key_count",
                "Number of keys",
                value=info.get("db0", {}).get("keys", 0) if isinstance(info.get("db0"), dict) else 0,
            )

            # Stats
            yield CounterMetricFamily(
                "redis_operations_total",
                "Total operations",
                value=info.get("total_commands_processed", 0),
            )

        except Exception:
            pass

    def describe(self):
        """Describe metrics for registration."""
        return []


# =============================================================================
# Utility Functions
# =============================================================================

def reset_metrics():
    """Reset all metrics (useful for testing)."""
    # Unregister all collectors except the default ones
    collectors_to_remove = []
    for collector in _metrics_registry._names_to_collectors.values():
        if hasattr(collector, '_is_child') and not collector._is_child:
            collectors_to_remove.append(collector)

    for collector in collectors_to_remove:
        try:
            _metrics_registry.unregister(collector)
        except Exception:
            pass


def get_metric_value(metric_name: str, labels: dict[str, str] | None = None) -> float | None:
    """Get current value of a metric.

    Args:
        metric_name: Name of the metric
        labels: Labels to filter by

    Returns:
        Current metric value or None if not found
    """
    metric = _metrics_registry._names_to_collectors.get(metric_name)
    if metric is None:
        return None

    if labels:
        try:
            sample = metric.labels(**labels)
            return sample._value.get()
        except Exception:
            return None
    return None


def metrics_summary() -> dict[str, Any]:
    """Get summary of all metrics for debugging/monitoring.

    Returns:
        Dict with metric counts by type
    """
    counters = sum(1 for m in _metrics_registry._names_to_collectors.values() if isinstance(m, Counter))
    gauges = sum(1 for m in _metrics_registry._names_to_collectors.values() if isinstance(m, Gauge))
    histograms = sum(1 for m in _metrics_registry._names_to_collectors.values() if isinstance(m, Histogram))
    infos = sum(1 for m in _metrics_registry._names_to_collectors.values() if isinstance(m, Info))

    return {
        "counters": counters,
        "gauges": gauges,
        "histograms": histograms,
        "infos": infos,
        "total": counters + gauges + histograms + infos,
    }


# =============================================================================
# Module-level instances for convenience
# =============================================================================

memory_daemon = MemoryDaemonMetrics()
recall = RecallMetrics()
store = StoreMetrics()
stream_monitor = StreamMonitorMetrics()
mcp = MCPMetrics()
webhook = WebhookMetrics()
system = SystemMetrics()
