"""
Enhanced Stream Monitor Metrics for Continuous-Claude-v3

Provides comprehensive Prometheus metrics for stream monitoring including:
- Real-time event processing metrics
- Redis stream health metrics
- Enhanced stuck detection with dynamic thresholds
- Alert-ready metrics for P1/P2/P3 priorities

Usage:
    from scripts.core.stream_monitor_metrics import (
        StreamMonitorEnhanced, StreamMetricsCollector,
        stream_metrics, create_enhanced_monitor
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from collections import deque
from collections.abc import Callable

from prometheus_client import Counter, Gauge, Histogram, Summary, Info, REGISTRY
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Redis TTL for hot events (24 hours)
REDIS_EVENT_TTL = 24 * 60 * 60

# Stuck detection thresholds (dynamic)
STUCK_CONFIG = {
    "min_consecutive_tool": 5,
    "min_consecutive_thinking": 5,
    "min_consecutive_turns": 3,  # Minimum turns before stuck detection activates
    "adaptive_factor": 0.1,  # Factor for dynamic threshold adjustment
    "max_threshold_multiplier": 2.0,  # Max multiplier for adaptive thresholds
    "recovery_grace_period_ms": 5000,  # Grace period before marking stuck
    "false_positive_window": 10,  # Events to check for false positives
    "false_positive_tool_change_rate": 0.3,  # If >30% tool changes, likely false positive
}

# Alert thresholds
ALERT_THRESHOLDS = {
    "stuck_agents_p1": 1,  # P1: Any stuck agent
    "stream_backlog_p2": 1000,  # P2: Stream backlog > 1000
    "ttl_violations_p3": 5,  # P3: >5 TTL violations per hour
    "consumer_lag_p2_ms": 5000,  # P2: Consumer lag > 5 seconds
    "processing_latency_p2_ms": 1000,  # P2: Processing latency > 1 second
}


# =============================================================================
# Enums
# =============================================================================


class EventType(Enum):
    """Stream event types."""
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    TEXT = "text"
    ERROR = "error"
    RESULT = "result"
    UNKNOWN = "unknown"


class StuckReason(Enum):
    """Reasons for stuck detection."""
    CONSECUTIVE_TOOL = "consecutive_tool"
    CONSECUTIVE_THINKING = "consecutive_thinking"
    NO_PROGRESS = "no_progress"
    TIMEOUT = "timeout"
    MEMORY_PRESSURE = "memory_pressure"
    REDIS_UNAVAILABLE = "redis_unavailable"


class AlertPriority(Enum):
    """Alert priority levels."""
    P1_CRITICAL = 1
    P2_HIGH = 2
    P3_MEDIUM = 3
    P4_LOW = 4


# =============================================================================
# Prometheus Metrics - Real-time Processing Metrics
# =============================================================================

# -----------------------------------------------------------------------------
# Event Processing Metrics
# -----------------------------------------------------------------------------

stream_events_total = Counter(
    "stream_events_total",
    "Total number of stream events processed",
    ["agent_id", "event_type", "priority"],
    registry=REGISTRY,
)

stream_events_per_second = Gauge(
    "stream_events_per_second",
    "Current events processed per second",
    ["agent_id"],
    registry=REGISTRY,
)

stream_event_processing_latency = Histogram(
    "stream_event_processing_latency_seconds",
    "End-to-end event processing latency",
    ["agent_id", "event_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)

stream_event_parse_latency = Histogram(
    "stream_event_parse_latency_seconds",
    "Time to parse event from stream",
    ["agent_id", "event_type"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01),
    registry=REGISTRY,
)

stream_event_callback_latency = Histogram(
    "stream_event_callback_latency_seconds",
    "Time spent in event callbacks",
    ["agent_id", "callback_type"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1),
    registry=REGISTRY,
)

# -----------------------------------------------------------------------------
# Turn Tracking Metrics
# -----------------------------------------------------------------------------

stream_turn_count = Gauge(
    "stream_turn_count",
    "Current turn count for monitored agent",
    ["agent_id"],
    registry=REGISTRY,
)

stream_turn_total = Counter(
    "stream_turn_total",
    "Total number of turns completed",
    ["agent_id"],
    registry=REGISTRY,
)

stream_turn_latency = Histogram(
    "stream_turn_latency_seconds",
    "Time between turn starts and completions",
    ["agent_id"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)

stream_turn_tracking_accuracy = Gauge(
    "stream_turn_tracking_accuracy",
    "Turn tracking accuracy score (0-1, calculated from tool_result ratio)",
    ["agent_id"],
    registry=REGISTRY,
)

# -----------------------------------------------------------------------------
# Stuck Detection Metrics
# -----------------------------------------------------------------------------

stream_stuck_detections = Counter(
    "stream_stuck_detections_total",
    "Total number of stuck agent detections",
    ["agent_id", "reason", "priority"],
    registry=REGISTRY,
)

stream_stuck_recoveries = Counter(
    "stream_stuck_recoveries_total",
    "Total number of stuck agent recoveries",
    ["agent_id", "reason"],
    registry=REGISTRY,
)

stream_stuck_false_positives = Counter(
    "stream_stuck_false_positives_total",
    "Detected stuck states that were false positives",
    ["agent_id", "reason"],
    registry=REGISTRY,
)

stream_stuck_false_negatives = Counter(
    "stream_stuck_false_negatives_total",
    "Actual stuck states not detected",
    ["agent_id", "reason"],
    registry=REGISTRY,
)

stream_stuck_detection_latency = Histogram(
    "stream_stuck_detection_latency_seconds",
    "Time from actual stuck condition to detection",
    ["agent_id", "reason"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)

stream_stuck_threshold = Gauge(
    "stream_stuck_threshold",
    "Current dynamic stuck detection threshold",
    ["agent_id", "threshold_type"],  # tool, thinking, turns
    registry=REGISTRY,
)

stream_active_stuck_agents = Gauge(
    "stream_active_stuck_agents",
    "Number of currently stuck agents",
    registry=REGISTRY,
)

# -----------------------------------------------------------------------------
# Redis Stream Metrics
# -----------------------------------------------------------------------------

stream_redis_publishes = Counter(
    "stream_redis_publishes_total",
    "Total events published to Redis",
    ["agent_id", "status"],  # success, failed, timeout
    registry=REGISTRY,
)

stream_redis_publish_latency = Histogram(
    "stream_redis_publish_latency_seconds",
    "Latency of Redis publish operations",
    ["agent_id"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=REGISTRY,
)

stream_redis_backlog = Gauge(
    "stream_redis_backlog",
    "Number of events in Redis stream backlog",
    ["stream_key"],
    registry=REGISTRY,
)

stream_redis_backlog_growth_rate = Gauge(
    "stream_redis_backlog_growth_rate",
    "Rate of backlog growth (events per second)",
    ["stream_key"],
    registry=REGISTRY,
)

stream_redis_consumer_lag = Gauge(
    "stream_redis_consumer_lag_seconds",
    "Consumer group lag in seconds",
    ["consumer_group", "stream_key"],
    registry=REGISTRY,
)

stream_redis_ttl_violations = Counter(
    "stream_redis_ttl_violations_total",
    "Total number of TTL violations (events exceeding 24h)",
    ["agent_id", "key_prefix"],
    registry=REGISTRY,
)

stream_redis_memory_bytes = Gauge(
    "stream_redis_memory_bytes",
    "Memory used by stream keys",
    ["key_prefix"],
    registry=REGISTRY,
)

stream_redis_connection_state = Gauge(
    "stream_redis_connection_state",
    "Redis connection state (0=disconnected, 1=connected, 2=degraded)",
    registry=REGISTRY,
)

stream_redis_operations_total = Counter(
    "stream_redis_operations_total",
    "Total Redis stream operations",
    ["operation", "status"],
    registry=REGISTRY,
)

# -----------------------------------------------------------------------------
# Monitor Lifecycle Metrics
# -----------------------------------------------------------------------------

stream_active_monitors = Gauge(
    "stream_active_monitors",
    "Number of currently active stream monitors",
    registry=REGISTRY,
)

stream_monitor_total = Counter(
    "stream_monitor_total",
    "Total number of stream monitors created",
    registry=REGISTRY,
)

stream_monitor_duration = Histogram(
    "stream_monitor_duration_seconds",
    "Duration of completed monitor sessions",
    ["agent_id", "exit_reason"],
    buckets=(10, 30, 60, 300, 600, 1800, 3600, 7200),
    registry=REGISTRY,
)

stream_session_events = Histogram(
    "stream_session_events",
    "Number of events per monitor session",
    ["agent_id"],
    buckets=(10, 50, 100, 500, 1000, 5000),
    registry=REGISTRY,
)

# -----------------------------------------------------------------------------
# Alert Metrics
# -----------------------------------------------------------------------------

stream_alerts_total = Counter(
    "stream_alerts_total",
    "Total alerts fired",
    ["priority", "alert_type", "agent_id"],
    registry=REGISTRY,
)

stream_alerts_firing = Gauge(
    "stream_alerts_firing",
    "Number of currently firing alerts",
    ["priority", "alert_type"],
    registry=REGISTRY,
)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class StreamEvent:
    """Parsed event from Claude stream-json output."""
    event_type: str
    timestamp: str
    data: dict[str, Any]
    turn_number: int = 0
    correlation_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data,
            "turn_number": self.turn_number,
            "correlation_id": self.correlation_id,
        }


@dataclass
class MonitorState:
    """Internal state for a monitored agent."""
    agent_id: str
    events: list[StreamEvent] = field(default_factory=list)
    turn_count: int = 0
    consecutive_tool_calls: list[str] = field(default_factory=list)
    consecutive_thinking: int = 0
    is_stuck: bool = False
    stuck_reason: str | None = None
    stuck_at: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    exit_code: int | None = None
    last_event_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Adaptive threshold state
    tool_threshold: int = STUCK_CONFIG["min_consecutive_tool"]
    thinking_threshold: int = STUCK_CONFIG["min_consecutive_thinking"]
    turn_threshold: int = STUCK_CONFIG["min_consecutive_turns"]

    # False positive tracking
    recent_tools: deque = field(default_factory=lambda: deque(maxlen=STUCK_CONFIG["false_positive_window"]))
    tool_change_rate: float = 0.0

    # Latency tracking
    event_latencies: deque = field(default_factory=lambda: deque(maxlen=100))
    turn_timestamps: list[str] = field(default_factory=list)


@dataclass
class Alert:
    """Alert definition."""
    priority: AlertPriority
    alert_type: str
    agent_id: str | None
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    labels: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Adaptive Threshold Manager
# =============================================================================


class AdaptiveThresholdManager:
    """Manages dynamic thresholds for stuck detection based on load."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.base_thresholds = {
            "tool": STUCK_CONFIG["min_consecutive_tool"],
            "thinking": STUCK_CONFIG["min_consecutive_thinking"],
            "turns": STUCK_CONFIG["min_consecutive_turns"],
        }
        self.current_thresholds = dict(self.base_thresholds)
        self.load_history = deque(maxlen=100)  # Recent load measurements
        self.false_positive_count = 0
        self.true_positive_count = 0
        self._lock = threading.Lock()

    def update_load(self, events_per_second: float, avg_latency: float) -> None:
        """Update load metrics and adjust thresholds."""
        with self._lock:
            self.load_history.append({
                "eps": events_per_second,
                "latency": avg_latency,
                "timestamp": time.time(),
            })

            # Calculate adaptive threshold based on load
            if len(self.load_history) >= 10:
                recent_eps = sum(h["eps"] for h in list(self.load_history)[-10:]) / 10
                recent_latency = sum(h["latency"] for h in list(self.load_history)[-10:]) / 10

                # Increase threshold under high load to reduce false positives
                eps_factor = 1.0 + (recent_eps * STUCK_CONFIG["adaptive_factor"])
                latency_factor = 1.0 + (recent_latency * STUCK_CONFIG.get("latency_adaptive_factor", 0.1))

                self.current_thresholds["tool"] = min(
                    int(self.base_thresholds["tool"] * eps_factor * latency_factor),
                    int(self.base_thresholds["tool"] * STUCK_CONFIG["max_threshold_multiplier"]),
                )
                self.current_thresholds["thinking"] = min(
                    int(self.base_thresholds["thinking"] * eps_factor),
                    int(self.base_thresholds["thinking"] * STUCK_CONFIG["max_threshold_multiplier"]),
                )

                # Update Prometheus metrics
                stream_stuck_threshold.labels(
                    agent_id=self.agent_id, threshold_type="tool"
                ).set(self.current_thresholds["tool"])
                stream_stuck_threshold.labels(
                    agent_id=self.agent_id, threshold_type="thinking"
                ).set(self.current_thresholds["thinking"])

    def report_false_positive(self) -> None:
        """Report a false positive detection."""
        with self._lock:
            self.false_positive_count += 1
            # Slightly increase thresholds to reduce future false positives
            for key in self.current_thresholds:
                self.current_thresholds[key] = min(
                    self.current_thresholds[key] + 1,
                    int(self.base_thresholds[key] * STUCK_CONFIG["max_threshold_multiplier"]),
                )

    def report_true_positive(self) -> None:
        """Report a true positive detection."""
        with self._lock:
            self.true_positive_count += 1

    def get_thresholds(self) -> dict[str, int]:
        """Get current thresholds."""
        with self._lock:
            return dict(self.current_thresholds)

    def get_false_positive_rate(self) -> float:
        """Calculate false positive rate."""
        with self._lock:
            total = self.false_positive_count + self.true_positive_count
            if total == 0:
                return 0.0
            return self.false_positive_count / total


# =============================================================================
# Alert Manager
# =============================================================================


class AlertManager:
    """Manages alerting for stream monitoring."""

    def __init__(self):
        self.alerts: list[Alert] = []
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[Alert], None]] = []

    def register_callback(self, callback: Callable[[Alert], None]) -> None:
        """Register a callback for alert notifications."""
        self._callbacks.append(callback)

    def fire_alert(self, alert: Alert) -> None:
        """Fire an alert and notify callbacks."""
        with self._lock:
            self.alerts.append(alert)
            stream_alerts_total.labels(
                priority=f"P{alert.priority.value}",
                alert_type=alert.alert_type,
                agent_id=alert.agent_id or "global",
            ).inc()
            stream_alerts_firing.labels(
                priority=f"P{alert.priority.value}",
                alert_type=alert.alert_type,
            ).inc()

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.warning(f"Alert callback failed: {e}")

    def check_stuck_agent(self, agent_id: str, is_stuck: bool, reason: str) -> None:
        """Check and fire stuck agent alert."""
        if is_stuck:
            self.fire_alert(Alert(
                priority=AlertPriority.P1_CRITICAL,
                alert_type="stuck_agent",
                agent_id=agent_id,
                message=f"Agent {agent_id} stuck: {reason}",
            ))

    def check_stream_backlog(self, backlog: int, stream_key: str) -> None:
        """Check and fire stream backlog alert."""
        if backlog > ALERT_THRESHOLDS["stream_backlog_p2"]:
            self.fire_alert(Alert(
                priority=AlertPriority.P2_HIGH,
                alert_type="stream_backlog",
                agent_id=None,
                message=f"Stream backlog growing: {stream_key} has {backlog} events",
                labels={"stream_key": stream_key, "backlog": str(backlog)},
            ))

    def check_ttl_violation(self, agent_id: str, key_prefix: str, violations: int) -> None:
        """Check and fire TTL violation alert."""
        if violations > ALERT_THRESHOLDS["ttl_violations_p3"]:
            self.fire_alert(Alert(
                priority=AlertPriority.P3_MEDIUM,
                alert_type="ttl_violation",
                agent_id=agent_id,
                message=f"TTL violations for {key_prefix}: {violations} in last period",
            ))

    def check_consumer_lag(self, lag_ms: float, consumer_group: str) -> None:
        """Check and fire consumer lag alert."""
        if lag_ms > ALERT_THRESHOLDS["consumer_lag_p2_ms"]:
            self.fire_alert(Alert(
                priority=AlertPriority.P2_HIGH,
                alert_type="consumer_lag",
                agent_id=None,
                message=f"Consumer lag high: {consumer_group} lag is {lag_ms}ms",
                labels={"consumer_group": consumer_group, "lag_ms": str(lag_ms)},
            ))

    def check_processing_latency(self, latency_ms: float, agent_id: str) -> None:
        """Check and fire processing latency alert."""
        if latency_ms > ALERT_THRESHOLDS["processing_latency_p2_ms"]:
            self.fire_alert(Alert(
                priority=AlertPriority.P2_HIGH,
                alert_type="processing_latency",
                agent_id=agent_id,
                message=f"Processing latency high for {agent_id}: {latency_ms}ms",
            ))

    def get_active_alerts(self, priority: AlertPriority | None = None) -> list[Alert]:
        """Get active alerts, optionally filtered by priority."""
        with self._lock:
            if priority:
                return [a for a in self.alerts if a.priority == priority]
            return list(self.alerts)

    def clear_resolved(self, agent_id: str) -> None:
        """Clear resolved alerts for an agent."""
        with self._lock:
            self.alerts = [a for a in self.alerts if a.agent_id != agent_id]
            stream_active_stuck_agents.set(len([
                a for a in self.alerts
                if a.alert_type == "stuck_agent"
            ]))


# Global alert manager
alert_manager = AlertManager()


# =============================================================================
# Enhanced Stream Monitor
# =============================================================================


class StreamMonitorEnhanced:
    """Enhanced StreamMonitor with comprehensive metrics and adaptive thresholds."""

    def __init__(
        self,
        agent_id: str,
        redis_client: Any | None = None,
        on_event: Callable[[StreamEvent], None] | None = None,
        on_stuck: Callable[[str], None] | None = None,
        on_alert: Callable[[Alert], None] | None = None,
        enable_adaptive_thresholds: bool = True,
    ):
        self.agent_id = agent_id
        self.redis_client = redis_client
        self.on_event = on_event
        self.on_stuck = on_stuck
        self.enable_adaptive_thresholds = enable_adaptive_thresholds

        self._state = MonitorState(agent_id=agent_id)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Correlation ID for tracing
        self._correlation_id = f"monitor-{agent_id}-{int(time.time())}"

        # Adaptive threshold manager
        self._threshold_manager = AdaptiveThresholdManager(agent_id)

        # Rate tracking
        self._event_times: deque = deque(maxlen=1000)
        self._events_per_second: float = 0.0

        # Latency tracking
        self._latency_samples: list[float] = []

        # Register alert callback if provided
        if on_alert:
            alert_manager.register_callback(on_alert)

        # Update active monitors
        stream_active_monitors.inc()
        stream_monitor_total.inc()

    def _update_rate(self, event_time: float) -> None:
        """Update events per second rate."""
        now = time.time()
        self._event_times.append(now)

        # Count events in last second
        cutoff = now - 1.0
        count = sum(1 for t in self._event_times if t > cutoff)
        self._events_per_second = count

        stream_events_per_second.labels(agent_id=self.agent_id).set(count)

    def _detect_false_positive(self, event: StreamEvent) -> bool:
        """Check if current stuck-like pattern is likely a false positive."""
        if event.event_type == "tool_use":
            self._state.recent_tools.append(event.data.get("tool", "unknown"))

            # Calculate tool change rate
            if len(self._state.recent_tools) >= 5:
                changes = sum(
                    1 for i in range(1, len(self._state.recent_tools))
                    if self._state.recent_tools[i] != self._state.recent_tools[i-1]
                )
                self._state.tool_change_rate = changes / (len(self._state.recent_tools) - 1)

                # High tool change rate suggests not actually stuck
                if self._state.tool_change_rate > STUCK_CONFIG["false_positive_tool_change_rate"]:
                    return True

        return False

    def _check_stuck_with_adaptive_threshold(self, event: StreamEvent) -> tuple[bool, str | None]:
        """Check if agent is stuck using adaptive thresholds."""
        thresholds = self._threshold_manager.get_thresholds()

        # Check consecutive tools
        if event.event_type == "tool_use":
            tool_name = event.data.get("tool", event.data.get("name", "unknown"))
            self._state.consecutive_tool_calls.append(tool_name)

            if len(self._state.consecutive_tool_calls) >= thresholds["tool"]:
                recent = self._state.consecutive_tool_calls[-thresholds["tool"]:]
                if len(set(recent)) == 1:
                    # Check for false positive
                    if self._detect_false_positive(event):
                        self._threshold_manager.report_false_positive()
                        return False, None

                    return True, f"Same tool '{tool_name}' called {thresholds['tool']}+ times"

            self._state.consecutive_thinking = 0

        # Check consecutive thinking
        elif event.event_type == "thinking":
            self._state.consecutive_thinking += 1

            if self._state.consecutive_thinking >= thresholds["thinking"]:
                return True, f"Agent stuck in thinking ({thresholds['thinking']}+ consecutive)"

        # Check for no progress (no events for extended period)
        elif event.event_type in ("tool_result", "text"):
            self._state.consecutive_tool_calls = []
            self._state.consecutive_thinking = 0

        return False, None

    def _handle_stuck_detection(self, is_stuck: bool, reason: str | None) -> None:
        """Handle stuck detection with proper state management."""
        with self._lock:
            if is_stuck and not self._state.is_stuck:
                self._state.is_stuck = True
                self._state.stuck_reason = reason
                self._state.stuck_at = datetime.now(UTC).isoformat()

                # Record metrics
                stream_stuck_detections.labels(
                    agent_id=self.agent_id,
                    reason=reason or "unknown",
                    priority="P1",
                ).inc()
                stream_active_stuck_agents.inc()

                # Fire alert
                alert_manager.check_stuck_agent(self.agent_id, True, reason)

                # Call callback
                if self.on_stuck:
                    try:
                        self.on_stuck(reason)
                    except Exception as e:
                        logger.warning(f"Stuck callback error: {e}")

            elif not is_stuck and self._state.is_stuck:
                # Recovery
                self._state.is_stuck = False
                if self._state.stuck_at:
                    stuck_duration = (
                        datetime.now(UTC) - datetime.fromisoformat(self._state.stuck_at)
                    ).total_seconds()

                    stream_stuck_recoveries.labels(
                        agent_id=self.agent_id,
                        reason=self._state.stuck_reason or "unknown",
                    ).inc()

                    alert_manager.clear_resolved(self.agent_id)

                self._state.stuck_reason = None
                self._state.stuck_at = None

    def _process_event(self, event: StreamEvent, parse_time: float, callback_time: float) -> None:
        """Process a parsed event with comprehensive metrics."""
        event_start = time.time()

        with self._lock:
            # Add to event list
            self._state.events.append(event)
            self._state.last_event_at = datetime.now(UTC).isoformat()

            # Update turn count
            if event.event_type == "tool_result":
                prev_turn = self._state.turn_count
                self._state.turn_count += 1
                stream_turn_count.labels(agent_id=self.agent_id).set(self._state.turn_count)
                stream_turn_total.labels(agent_id=self.agent_id).inc()

                # Track turn latency
                if self._state.turn_timestamps:
                    turn_duration = (
                        datetime.now(UTC) - datetime.fromisoformat(self._state.turn_timestamps[-1])
                    ).total_seconds()
                    stream_turn_latency.labels(agent_id=self.agent_id).observe(turn_duration)

                self._state.turn_timestamps.append(datetime.now(UTC).isoformat())

            # Check for stuck with adaptive thresholds
            is_stuck, reason = self._check_stuck_with_adaptive_threshold(event)
            self._handle_stuck_detection(is_stuck, reason)

        # Record metrics
        stream_events_total.labels(
            agent_id=self.agent_id,
            event_type=event.event_type,
            priority="normal",
        ).inc()

        # Record latencies
        total_latency = time.time() - event_start + parse_time + callback_time
        stream_event_processing_latency.labels(
            agent_id=self.agent_id,
            event_type=event.event_type,
        ).observe(total_latency)

        # Update rate
        self._update_rate(event_start)

        # Track session stats
        self._latency_samples.append(total_latency)

        # Push to Redis if available with latency tracking
        if self.redis_client:
            redis_start = time.time()
            try:
                key = f"agent:{self.agent_id}:events"
                self.redis_client.lpush(key, json.dumps(event.to_dict()))
                self.redis_client.expire(key, REDIS_EVENT_TTL)

                redis_latency = time.time() - redis_start
                stream_redis_publishes.labels(
                    agent_id=self.agent_id,
                    status="success",
                ).inc()
                stream_redis_publish_latency.labels(
                    agent_id=self.agent_id,
                ).observe(redis_latency)

            except Exception as e:
                stream_redis_publishes.labels(
                    agent_id=self.agent_id,
                    status="failed",
                ).inc()
                logger.warning(f"Redis publish failed: {e}")

        # Call event callback
        if self.on_event:
            try:
                self.on_event(event)
            except Exception as e:
                logger.warning(f"Event callback error: {e}")

    def _parse_event(self, line: str) -> tuple[StreamEvent | None, float]:
        """Parse a stream-json line and return with parse time."""
        parse_start = time.time()

        try:
            data = json.loads(line)
            event_type = "unknown"

            if "thinking" in data or data.get("type") == "thinking":
                event_type = "thinking"
            elif "tool_use" in data or data.get("type") == "tool_use":
                event_type = "tool_use"
            elif "tool_result" in data or data.get("type") == "tool_result":
                event_type = "tool_result"
            elif "text" in data or data.get("type") == "text":
                event_type = "text"
            elif "error" in data or data.get("type") == "error":
                event_type = "error"
            elif data.get("type") == "result":
                event_type = "result"

            event = StreamEvent(
                event_type=event_type,
                timestamp=datetime.now(UTC).isoformat(),
                data=data,
                turn_number=self._state.turn_count,
                correlation_id=self._correlation_id,
            )

            parse_time = time.time() - parse_start
            stream_event_parse_latency.labels(
                agent_id=self.agent_id,
                event_type=event_type,
            ).observe(parse_time)

            return event, parse_time

        except json.JSONDecodeError:
            return None, 0.0

    # Public methods (same interface as original StreamMonitor)
    @property
    def is_stuck(self) -> bool:
        with self._lock:
            return self._state.is_stuck

    @property
    def stuck_reason(self) -> str | None:
        with self._lock:
            return self._state.stuck_reason

    @property
    def turn_count(self) -> int:
        with self._lock:
            return self._state.turn_count

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self._state.events)

    def get_events(self, limit: int | None = None) -> list[dict]:
        with self._lock:
            events = [e.to_dict() for e in self._state.events]
            if limit:
                return events[-limit:]
            return events

    def get_summary(self) -> dict:
        with self._lock:
            avg_latency = sum(self._latency_samples) / len(self._latency_samples) if self._latency_samples else 0.0
            return {
                "agent_id": self.agent_id,
                "event_count": len(self._state.events),
                "turn_count": self._state.turn_count,
                "is_stuck": self._state.is_stuck,
                "stuck_reason": self._state.stuck_reason,
                "events_per_second": self._events_per_second,
                "avg_latency_ms": avg_latency * 1000,
                "started_at": self._state.started_at,
                "completed_at": self._state.completed_at,
                "exit_code": self._state.exit_code,
                "adaptive_thresholds": self._threshold_manager.get_thresholds(),
                "false_positive_rate": self._threshold_manager.get_false_positive_rate(),
            }

    def start(self, process: subprocess.Popen) -> None:
        """Start monitoring with metrics."""
        if self._thread is not None:
            raise RuntimeError("Monitor already started")

        logger.info(f"Starting enhanced stream monitor for {self.agent_id}")

        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(process,),
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop monitoring and record final metrics."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

        with self._lock:
            total_events = len(self._state.events)
            total_turns = self._state.turn_count
            exit_code = self._state.exit_code
            stuck_detected = self._state.is_stuck

            if self._state.started_at:
                try:
                    start_dt = datetime.fromisoformat(self._state.started_at)
                    duration = (datetime.now(UTC) - start_dt).total_seconds()
                except Exception:
                    duration = 0.0
            else:
                duration = 0.0

        # Record session metrics
        stream_monitor_duration.labels(
            agent_id=self.agent_id,
            exit_reason=str(exit_code) if exit_code else "running",
        ).observe(duration)
        stream_session_events.labels(agent_id=self.agent_id).observe(total_events)

        stream_active_monitors.dec()
        stream_turn_count.labels(agent_id=self.agent_id).set(0)

        logger.info(
            f"Stopped enhanced stream monitor for {self.agent_id}: "
            f"{total_events} events, {total_turns} turns, stuck={stuck_detected}"
        )

    def _monitor_loop(self, process: subprocess.Popen) -> None:
        """Background thread loop for monitoring process output."""
        try:
            for line in iter(process.stdout.readline, b""):
                if self._stop_event.is_set():
                    break

                if not line:
                    continue

                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")

                line = line.strip()
                if not line:
                    continue

                callback_start = time.time()

                try:
                    event, parse_time = self._parse_event(line)
                    if event:
                        self._process_event(event, parse_time, time.time() - callback_start)

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.warning(f"Error processing event: {e}")

            # Process completed
            process.wait()
            with self._lock:
                self._state.exit_code = process.returncode
                self._state.completed_at = datetime.now(UTC).isoformat()

        except Exception as e:
            logger.error(f"Monitor loop error: {e}")


# =============================================================================
# Redis Stream Metrics Collector
# =============================================================================


class StreamMetricsCollector:
    """Collects Redis stream metrics for monitoring."""

    def __init__(self, redis_client, stream_prefix: str = "agent:"):
        self.redis = redis_client
        self.stream_prefix = stream_prefix
        self._last_backlog: dict[str, int] = {}
        self._last_check = time.time()

    def get_stream_info(self, stream_key: str) -> dict:
        """Get information about a Redis stream."""
        try:
            info = self.redis.xinfo_stream(stream_key)
            return {
                "length": info.get("length", 0),
                "last_id": info.get("last-id"),
                "first_id": info.get("first-id"),
                "max_deleted_entry_id": info.get("max-deleted-entry-id"),
                "entries_added": info.get("entries-added", 0),
            }
        except Exception as e:
            logger.warning(f"Failed to get stream info for {stream_key}: {e}")
            return {"length": 0, "error": str(e)}

    def get_consumer_group_info(self, stream_key: str, group_name: str) -> dict:
        """Get consumer group information."""
        try:
            info = self.redis.xinfo_groups(stream_key)
            for group in info:
                if group.get("name") == group_name:
                    return {
                        "name": group.get("name"),
                        "consumers": group.get("consumers", 0),
                        "pending": group.get("pending", 0),
                        "last_delivered_id": group.get("last-delivered-id"),
                    }
            return {}
        except Exception as e:
            logger.warning(f"Failed to get consumer group info: {e}")
            return {}

    def get_all_stream_keys(self) -> list[str]:
        """Get all stream keys matching the prefix."""
        try:
            keys = self.redis.keys(f"{self.stream_prefix}*:events")
            return [k.decode() if isinstance(k, bytes) else k for k in keys]
        except Exception as e:
            logger.warning(f"Failed to get stream keys: {e}")
            return []

    def collect_metrics(self) -> dict:
        """Collect all stream metrics."""
        streams = self.get_all_stream_keys()
        total_backlog = 0

        for stream_key in streams:
            info = self.get_stream_info(stream_key)
            length = info.get("length", 0)
            total_backlog += length

            # Update backlog gauge
            stream_redis_backlog.labels(stream_key=stream_key).set(length)

            # Calculate growth rate
            if stream_key in self._last_backlog:
                time_diff = time.time() - self._last_check
                if time_diff > 0:
                    growth_rate = (length - self._last_backlog[stream_key]) / time_diff
                    stream_redis_backlog_growth_rate.labels(stream_key=stream_key).set(growth_rate)

            self._last_backlog[stream_key] = length

            # Check for backlog alert
            alert_manager.check_stream_backlog(length, stream_key)

        self._last_check = time.time()

        # Update connection state
        try:
            self.redis.ping()
            stream_redis_connection_state.set(1)
        except Exception:
            stream_redis_connection_state.set(0)

        return {
            "streams": len(streams),
            "total_backlog": total_backlog,
            "streams": streams,
        }

    def collect_ttl_metrics(self) -> dict:
        """Check TTL compliance for stream keys."""
        violations = 0
        memory_bytes = 0

        try:
            # Check key TTLs
            keys = self.redis.keys(f"{self.stream_prefix}*:events")
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                ttl = self.redis.ttl(key_str)
                if ttl > 0 and ttl < REDIS_EVENT_TTL - 3600:  # Within 1 hour of expiry
                    violations += 1
                    stream_redis_ttl_violations.labels(
                        agent_id=key_str.split(":")[1] if ":" in key_str else "unknown",
                        key_prefix=self.stream_prefix.rstrip(":"),
                    ).inc()

        except Exception as e:
            logger.warning(f"Failed to collect TTL metrics: {e}")

        return {"violations": violations, "memory_bytes": memory_bytes}


# =============================================================================
# Factory Functions
# =============================================================================


def create_enhanced_monitor(
    agent_id: str,
    redis_client: Any | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    on_stuck: Callable[[str], None] | None = None,
    on_alert: Callable[[Alert], None] | None = None,
    enable_adaptive_thresholds: bool = True,
) -> StreamMonitorEnhanced:
    """Create an enhanced stream monitor with metrics."""
    return StreamMonitorEnhanced(
        agent_id=agent_id,
        redis_client=redis_client,
        on_event=on_event,
        on_stuck=on_stuck,
        on_alert=on_alert,
        enable_adaptive_thresholds=enable_adaptive_thresholds,
    )


def get_metrics_summary() -> dict:
    """Get summary of stream monitoring metrics."""
    return {
        "active_monitors": stream_active_monitors._value.get() if hasattr(stream_active_monitors, '_value') else 0,
        "active_stuck_agents": stream_active_stuck_agents._value.get() if hasattr(stream_active_stuck_agents, '_value') else 0,
        "firing_alerts": {
            "P1": sum(1 for a in alert_manager.alerts if a.priority == AlertPriority.P1_CRITICAL),
            "P2": sum(1 for a in alert_manager.alerts if a.priority == AlertPriority.P2_HIGH),
            "P3": sum(1 for a in alert_manager.alerts if a.priority == AlertPriority.P3_MEDIUM),
        },
    }
