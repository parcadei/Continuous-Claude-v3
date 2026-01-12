#!/usr/bin/env python3
"""
Stream Monitor with Structured Logging

Example integration showing:
- Event processing logging
- Stuck detection with correlation IDs
- Turn tracking
- Redis push metrics
- State transition tracking

Usage:
    from scripts.core.stream_monitor_logged import StreamMonitor, create_monitor

    monitor = create_monitor("agent-123")
    monitor.start(process)
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from scripts.core.logging_config import (
    get_logger,
    setup_logging,
    generate_correlation_id,
    StructuredLogger,
)


# =============================================================================
# Logger Setup
# =============================================================================

logger = get_logger("stream_monitor", "stream_monitor")


# =============================================================================
# Logging Wrappers
# =============================================================================

def log_event_received(
    event_type: str,
    correlation_id: str,
    turn_number: int = 0,
) -> None:
    """Log when an event is received."""
    logger.debug(
        "Event received",
        trace_id=correlation_id,
        operation="event_received",
        event_type=event_type,
        turn_number=turn_number,
    )


def log_event_processed(
    event_type: str,
    correlation_id: str,
    processing_time_ms: float,
) -> None:
    """Log when an event is processed."""
    logger.debug(
        "Event processed",
        trace_id=correlation_id,
        operation="event_processed",
        event_type=event_type,
        duration_ms=round(processing_time_ms, 2),
    )


def log_state_transition(
    from_state: str,
    to_state: str,
    correlation_id: str,
    reason: str | None = None,
) -> None:
    """Log state transitions."""
    logger.info(
        f"State transition: {from_state} -> {to_state}",
        trace_id=correlation_id,
        operation="state_transition",
        from_state=from_state,
        to_state=to_state,
        reason=reason,
    )


def log_stuck_detected(
    agent_id: str,
    reason: str,
    correlation_id: str,
    consecutive_tool: str | None = None,
    consecutive_count: int = 0,
) -> None:
    """Log when agent is detected as stuck."""
    logger.warning(
        "Agent stuck detected",
        trace_id=correlation_id,
        operation="stuck_detection",
        agent_id=agent_id,
        reason=reason,
        consecutive_tool=consecutive_tool,
        consecutive_count=consecutive_count,
    )


def log_stuck_recovered(
    agent_id: str,
    correlation_id: str,
    stuck_duration_ms: float,
) -> None:
    """Log when agent recovers from stuck state."""
    logger.info(
        "Agent recovered from stuck state",
        trace_id=correlation_id,
        operation="stuck_recovery",
        agent_id=agent_id,
        stuck_duration_ms=round(stuck_duration_ms, 2),
    )


def log_redis_push(
    key: str,
    success: bool,
    correlation_id: str,
    duration_ms: float | None = None,
    error: str | None = None,
) -> None:
    """Log Redis push operations."""
    if success:
        logger.debug(
            "Redis push successful",
            trace_id=correlation_id,
            operation="redis_push",
            key=key,
            duration_ms=round(duration_ms, 2) if duration_ms else None,
        )
    else:
        logger.warning(
            "Redis push failed",
            trace_id=correlation_id,
            operation="redis_push",
            key=key,
            error=error,
        )


def log_turn_completed(
    agent_id: str,
    turn_number: int,
    correlation_id: str,
    duration_ms: float | None = None,
) -> None:
    """Log turn completion."""
    logger.debug(
        "Turn completed",
        trace_id=correlation_id,
        operation="turn_completed",
        agent_id=agent_id,
        turn_number=turn_number,
        duration_ms=round(duration_ms, 2) if duration_ms else None,
    )


def log_monitor_started(
    agent_id: str,
    correlation_id: str,
    has_redis: bool,
) -> None:
    """Log monitor start."""
    logger.info(
        "Stream monitor started",
        trace_id=correlation_id,
        operation="monitor_start",
        agent_id=agent_id,
        redis_enabled=has_redis,
    )


def log_monitor_stopped(
    agent_id: str,
    correlation_id: str,
    total_events: int,
    total_turns: int,
    exit_code: int | None,
    stuck_detected: bool,
    duration_ms: float,
) -> None:
    """Log monitor stop."""
    logger.info(
        "Stream monitor stopped",
        trace_id=correlation_id,
        operation="monitor_stop",
        agent_id=agent_id,
        total_events=total_events,
        total_turns=total_turns,
        exit_code=exit_code,
        stuck_detected=stuck_detected,
        duration_ms=round(duration_ms, 2),
    )


# =============================================================================
# Configuration
# =============================================================================

REDIS_EVENT_TTL = 24 * 60 * 60
CONSECUTIVE_TOOL_THRESHOLD = 5
CONSECUTIVE_THINKING_THRESHOLD = 5


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

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data,
            "turn_number": self.turn_number,
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
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    exit_code: int | None = None
    stuck_at: str | None = None


# =============================================================================
# Monitor Class with Logging
# =============================================================================

class StreamMonitor:
    """Monitor Claude agent stream-json output with structured logging."""

    def __init__(
        self,
        agent_id: str,
        redis_client: Any | None = None,
        on_event: Callable[[StreamEvent], None] | None = None,
        on_stuck: Callable[[str], None] | None = None,
    ):
        self.agent_id = agent_id
        self.redis_client = redis_client
        self.on_event = on_event
        self.on_stuck = on_stuck

        self._state = MonitorState(agent_id=agent_id)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Correlation ID for this monitoring session
        self._correlation_id = generate_correlation_id()

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

    def start(self, process: subprocess.Popen) -> None:
        """Start monitoring with logging."""
        if self._thread is not None:
            raise RuntimeError("Monitor already started")

        log_monitor_started(
            self.agent_id,
            self._correlation_id,
            has_redis=self.redis_client is not None,
        )

        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(process,),
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop monitoring with logging."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

        # Log final state
        with self._lock:
            total_events = len(self._state.events)
            total_turns = self._state.turn_count
            exit_code = self._state.exit_code
            stuck_detected = self._state.is_stuck

        if self._state.started_at:
            try:
                start_dt = datetime.fromisoformat(self._state.started_at)
                duration_ms = (datetime.now(UTC) - start_dt).total_seconds() * 1000
            except Exception:
                duration_ms = None
        else:
            duration_ms = None

        log_monitor_stopped(
            self.agent_id,
            self._correlation_id,
            total_events,
            total_turns,
            exit_code,
            stuck_detected,
            duration_ms or 0,
        )

    def _monitor_loop(self, process: subprocess.Popen) -> None:
        """Background thread loop with comprehensive logging."""
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

                start_time = datetime.now(timezone.utc).timestamp()

                try:
                    event = self._parse_event(line)
                    if event:
                        log_event_received(
                            event.event_type,
                            self._correlation_id,
                            event.turn_number,
                        )

                        self._process_event(event)

                        processing_time = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
                        log_event_processed(
                            event.event_type,
                            self._correlation_id,
                            processing_time,
                        )

                except json.JSONDecodeError as e:
                    logger.debug(
                        "Non-JSON line skipped",
                        trace_id=self._correlation_id,
                        operation="parse_error",
                        line_preview=line[:100],
                        error=str(e),
                    )
                except Exception as e:
                    logger.warning(
                        "Error processing event",
                        trace_id=self._correlation_id,
                        operation="event_processing_error",
                        error=str(e),
                    )

            # Process completed
            process.wait()
            with self._lock:
                self._state.exit_code = process.returncode
                self._state.completed_at = datetime.now(UTC).isoformat()

            log_state_transition(
                "running",
                "completed",
                self._correlation_id,
                reason=f"exit_code={process.returncode}",
            )

        except Exception as e:
            logger.exception(
                "Monitor loop error",
                trace_id=self._correlation_id,
                operation="monitor_loop_error",
                error=str(e),
            )

    def _parse_event(self, line: str) -> StreamEvent | None:
        """Parse a stream-json line."""
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

        return StreamEvent(
            event_type=event_type,
            timestamp=datetime.now(UTC).isoformat(),
            data=data,
            turn_number=self._state.turn_count,
        )

    def _process_event(self, event: StreamEvent) -> None:
        """Process a parsed event with logging."""
        with self._lock:
            # Add to event list
            self._state.events.append(event)

            # Update turn count
            if event.event_type == "tool_result":
                prev_turn = self._state.turn_count
                self._state.turn_count += 1
                log_turn_completed(
                    self.agent_id,
                    prev_turn,
                    self._correlation_id,
                )

            # Track consecutive tools for stuck detection
            if event.event_type == "tool_use":
                tool_name = event.data.get("tool", event.data.get("name", "unknown"))
                self._state.consecutive_tool_calls.append(tool_name)
                self._state.consecutive_thinking = 0

                # Check for stuck (same tool 5+ times)
                if len(self._state.consecutive_tool_calls) >= CONSECUTIVE_TOOL_THRESHOLD:
                    recent = self._state.consecutive_tool_calls[-CONSECUTIVE_TOOL_THRESHOLD:]
                    if len(set(recent)) == 1 and not self._state.is_stuck:
                        self._state.is_stuck = True
                        self._state.stuck_reason = (
                            f"Same tool '{recent[0]}' called {CONSECUTIVE_TOOL_THRESHOLD}+ times"
                        )
                        self._state.stuck_at = datetime.now(UTC).isoformat()

                        log_stuck_detected(
                            self.agent_id,
                            self._state.stuck_reason,
                            self._correlation_id,
                            consecutive_tool=recent[0],
                            consecutive_count=CONSECUTIVE_TOOL_THRESHOLD,
                        )

                        if self.on_stuck:
                            try:
                                self.on_stuck(self._state.stuck_reason)
                            except Exception as e:
                                logger.warning(
                                    "Stuck callback error",
                                    trace_id=self._correlation_id,
                                    error=str(e),
                                )

            elif event.event_type == "thinking":
                self._state.consecutive_thinking += 1

                if self._state.consecutive_thinking >= CONSECUTIVE_THINKING_THRESHOLD and not self._state.is_stuck:
                    self._state.is_stuck = True
                    self._state.stuck_reason = (
                        f"Agent stuck in thinking ({CONSECUTIVE_THINKING_THRESHOLD}+ consecutive)"
                    )
                    self._state.stuck_at = datetime.now(UTC).isoformat()

                    log_stuck_detected(
                        self.agent_id,
                        self._state.stuck_reason,
                        self._correlation_id,
                        consecutive_count=self._state.consecutive_thinking,
                    )

                    if self.on_stuck:
                        try:
                            self.on_stuck(self._state.stuck_reason)
                        except Exception as e:
                            logger.warning(
                                "Stuck callback error",
                                trace_id=self._correlation_id,
                                error=str(e),
                            )

            else:
                # Reset counters on other events
                if self._state.is_stuck and event.event_type in ("tool_result", "text"):
                    # Agent might be recovering
                    logger.debug(
                        "Agent may be recovering from stuck state",
                        trace_id=self._correlation_id,
                        operation="potential_recovery",
                    )

                self._state.consecutive_tool_calls = []
                self._state.consecutive_thinking = 0

        # Push to Redis if available
        if self.redis_client:
            start_time = datetime.now(timezone.utc).timestamp()
            try:
                key = f"agent:{self.agent_id}:events"
                self.redis_client.lpush(key, json.dumps(event.to_dict()))
                self.redis_client.expire(key, REDIS_EVENT_TTL)

                push_time = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
                log_redis_push(key, True, self._correlation_id, duration_ms=push_time)

            except Exception as e:
                log_redis_push(key, False, self._correlation_id, error=str(e))

        # Call event callback
        if self.on_event:
            try:
                self.on_event(event)
            except Exception as e:
                logger.warning(
                    "Event callback error",
                    trace_id=self._correlation_id,
                    error=str(e),
                )

    def get_summary(self) -> dict:
        """Get summary with logging context."""
        with self._lock:
            summary = {
                "agent_id": self.agent_id,
                "event_count": len(self._state.events),
                "turn_count": self._state.turn_count,
                "is_stuck": self._state.is_stuck,
                "stuck_reason": self._state.stuck_reason,
                "started_at": self._state.started_at,
                "completed_at": self._state.completed_at,
                "exit_code": self._state.exit_code,
            }

        logger.debug(
            "Monitor summary requested",
            trace_id=self._correlation_id,
            operation="get_summary",
            **summary,
        )

        return summary


# =============================================================================
# Factory Function
# =============================================================================

def create_monitor(
    agent_id: str,
    redis_client: Any | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    on_stuck: Callable[[str], None] | None = None,
) -> StreamMonitor:
    """Create a new StreamMonitor with logging.

    Args:
        agent_id: Unique identifier for the agent
        redis_client: Optional Redis client for event caching
        on_event: Optional callback for each event
        on_stuck: Optional callback when stuck is detected

    Returns:
        Configured StreamMonitor instance
    """
    return StreamMonitor(
        agent_id=agent_id,
        redis_client=redis_client,
        on_event=on_event,
        on_stuck=on_stuck,
    )


# =============================================================================
# Async Version
# =============================================================================

async def monitor_agent_async(
    agent_id: str,
    output_file: str,
    redis_client: Any | None = None,
) -> MonitorState:
    """Async version that monitors an agent's output file."""
    correlation_id = generate_correlation_id()

    logger.info(
        "Async monitor started",
        trace_id=correlation_id,
        operation="async_monitor_start",
        agent_id=agent_id,
        output_file=output_file,
    )

    state = MonitorState(agent_id=agent_id)

    path = Path(output_file)
    while not path.exists():
        await asyncio.sleep(0.1)

    with open(output_file) as f:
        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(0.1)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)

                event_type = "unknown"
                if "thinking" in data or data.get("type") == "thinking":
                    event_type = "thinking"
                elif "tool_use" in data or data.get("type") == "tool_use":
                    event_type = "tool_use"
                elif "tool_result" in data or data.get("type") == "tool_result":
                    event_type = "tool_result"

                event = StreamEvent(
                    event_type=event_type,
                    timestamp=datetime.now(UTC).isoformat(),
                    data=data,
                    turn_number=state.turn_count,
                )

                log_event_received(event_type, correlation_id, state.turn_count)
                state.events.append(event)

                if event_type == "tool_result":
                    log_turn_completed(agent_id, state.turn_count, correlation_id)
                    state.turn_count += 1

            except json.JSONDecodeError:
                pass

            if data.get("type") == "result":
                break

    state.completed_at = datetime.now(UTC).isoformat()

    logger.info(
        "Async monitor completed",
        trace_id=correlation_id,
        operation="async_monitor_complete",
        agent_id=agent_id,
        total_events=len(state.events),
        total_turns=state.turn_count,
    )

    return state
