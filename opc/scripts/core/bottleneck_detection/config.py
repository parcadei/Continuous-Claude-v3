"""
Bottleneck Detection Configuration

Defines thresholds, baseline percentages, and detection parameters.
"""

from dataclasses import dataclass, field
from typing import Callable
from enum import Enum


class Severity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ThresholdConfig:
    """Configuration for a detection threshold."""
    name: str
    warning_pct: float  # Percentage above baseline to trigger warning
    critical_pct: float  # Percentage above baseline to trigger critical
    duration_seconds: int  # How long threshold must be exceeded
    evaluation_interval: int = 60  # How often to evaluate


@dataclass
class TrendConfig:
    """Configuration for trend detection."""
    min_data_points: int = 10  # Minimum points for trend calculation
    slope_threshold: float = 0.1  # Slope magnitude to detect trend
    window_hours: int = 24  # Time window for trend analysis


@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection."""
    z_score_threshold: float = 2.5  # Standard deviations for anomaly
    mad_threshold: float = 3.0  # Median absolute deviations
    min_data_points: int = 30  # Minimum points for statistical analysis


@dataclass
class CorrelationConfig:
    """Configuration for correlation analysis."""
    correlation_threshold: float = 0.8  # Correlation coefficient threshold
    min_data_points: int = 20  # Minimum points for correlation
    window_minutes: int = 5  # Time window for correlation


@dataclass
class BottleneckDetectionConfig:
    """Main configuration for bottleneck detection."""
    # Database thresholds
    db_query_latency_warning: float = 2.0  # seconds
    db_query_latency_critical: float = 5.0  # seconds
    db_pool_warning_pct: float = 0.70  # 70% pool utilization
    db_pool_critical_pct: float = 0.90  # 90% pool utilization
    db_connection_warning: float = 0.70  # 70% of max connections
    db_connection_critical: float = 0.90  # 90% of max connections

    # Memory thresholds
    memory_warning_pct: float = 0.80  # 80% memory used
    memory_critical_pct: float = 0.95  # 95% memory used
    memory_growth_rate_warning: float = 0.05  # 5% growth per hour
    embedding_memory_warning_mb: float = 2048.0  # 2GB

    # CPU thresholds
    cpu_warning_pct: float = 0.80  # 80% CPU usage
    cpu_critical_pct: float = 0.95  # 95% CPU usage
    cpu_sustained_duration: int = 300  # 5 minutes sustained
    embedding_cpu_warning_pct: float = 0.70  # 70% during embedding

    # Network thresholds
    mcp_latency_warning_ms: float = 500.0  # 500ms
    mcp_latency_critical_ms: float = 2000.0  # 2s
    redis_latency_warning_ms: float = 10.0  # 10ms
    redis_latency_critical_ms: float = 50.0  # 50ms
    embedding_api_latency_warning_s: float = 5.0  # 5s
    embedding_api_latency_critical_s: float = 15.0  # 15s

    # Baseline configuration
    baseline_update_weekly: bool = True
    baseline_update_on_deploy: bool = True
    baseline_min_data_points: int = 100  # Minimum samples for baseline

    # Trend detection
    trend_config: TrendConfig = field(default_factory=TrendConfig)

    # Anomaly detection
    anomaly_config: AnomalyConfig = field(default_factory=AnomalyConfig)

    # Correlation detection
    correlation_config: CorrelationConfig = field(default_factory=CorrelationConfig)

    # Detection intervals
    detection_interval_seconds: int = 60
    alert_cooldown_seconds: int = 300  # 5 minutes between same alert


# Default configuration instance
DEFAULT_CONFIG = BottleneckDetectionConfig()


# Metric-specific threshold configurations
DATABASE_THRESHOLDS = {
    "pg_stat_statements_p95_ms": ThresholdConfig(
        name="db_query_latency_p95",
        warning_pct=50.0,  # 50% above baseline
        critical_pct=100.0,  # 100% above baseline
        duration_seconds=300,
    ),
    "pg_pool_connections_active": ThresholdConfig(
        name="db_pool_utilization",
        warning_pct=70.0,
        critical_pct=90.0,
        duration_seconds=180,
    ),
    "pg_stat_activity_count": ThresholdConfig(
        name="db_connections",
        warning_pct=70.0,
        critical_pct=90.0,
        duration_seconds=300,
    ),
    "pg_stat_database_deadlocks": ThresholdConfig(
        name="db_deadlocks",
        warning_pct=0.0,  # Any increase
        critical_pct=0.0,
        duration_seconds=60,
    ),
}

MEMORY_THRESHOLDS = {
    "memory_available_bytes": ThresholdConfig(
        name="memory_usage",
        warning_pct=20.0,  # 20% available remaining
        critical_pct=5.0,  # 5% available remaining
        duration_seconds=180,
    ),
    "process_memory_bytes": ThresholdConfig(
        name="process_memory",
        warning_pct=50.0,
        critical_pct=80.0,
        duration_seconds=300,
    ),
    "embedding_cache_size": ThresholdConfig(
        name="embedding_cache",
        warning_pct=75.0,
        critical_pct=90.0,
        duration_seconds=600,
    ),
}

CPU_THRESHOLDS = {
    "cpu_idle_seconds_total": ThresholdConfig(
        name="cpu_usage",
        warning_pct=20.0,  # 20% idle remaining = 80% usage
        critical_pct=5.0,  # 5% idle remaining = 95% usage
        duration_seconds=300,
    ),
    "embedding_generation_duration_seconds": ThresholdConfig(
        name="embedding_latency",
        warning_pct=50.0,
        critical_pct=100.0,
        duration_seconds=600,
    ),
}

NETWORK_THRESHOLDS = {
    "mcp_tool_latency_seconds": ThresholdConfig(
        name="mcp_latency",
        warning_pct=50.0,
        critical_pct=100.0,
        duration_seconds=180,
    ),
    "redis_operation_latency_seconds": ThresholdConfig(
        name="redis_latency",
        warning_pct=50.0,
        critical_pct=100.0,
        duration_seconds=120,
    ),
}


# Runbook URLs for different bottleneck types
RUNBOOKS = {
    "db_query_slow": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#query-latency",
    "db_pool_saturated": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#connection-pool",
    "db_deadlock": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#deadlock",
    "memory_leak": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#memory-leak",
    "memory_critical": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#memory-critical",
    "cpu_high": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#cpu-usage",
    "embedding_slow": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#embedding-latency",
    "mcp_slow": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#mcp-latency",
    "redis_slow": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#redis-latency",
    "anomaly_detected": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#anomaly",
    "trend_degradation": "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md#trend-degradation",
}


def get_threshold_config(metric_name: str) -> ThresholdConfig | None:
    """Get threshold configuration for a metric."""
    all_thresholds = {**DATABASE_THRESHOLDS, **MEMORY_THRESHOLDS, **CPU_THRESHOLDS, **NETWORK_THRESHOLDS}
    return all_thresholds.get(metric_name)


def get_runbook_url(bottleneck_type: str) -> str:
    """Get runbook URL for a bottleneck type."""
    return RUNBOOKS.get(bottleneck_type, "https://github.com/grantray/Continuous-Claude-v3/docs/runbooks.md")
