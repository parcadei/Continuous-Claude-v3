#!/usr/bin/env python3
"""
Structured Logging System for Continuous-Claude-v3

Provides JSON-structured logging with correlation IDs, log levels by severity,
Loki/Promtail integration, and per-script logging patterns.

Usage:
    from scripts.core.logging_config import get_logger, setup_logging

    logger = get_logger("memory_daemon")
    logger.info("message", trace_id="...")

Environment Variables:
    LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
    LOG_DIR: Log file directory (default: ~/.claude/logs)
    LOG_TO_CONSOLE: true/false (default: true)
    LOG_TO_FILE: true/false (default: true)
    LOG_TO_LOKI: true/false (default: false)
    LOKI_URL: Loki server URL (default: http://localhost:3100/loki/api/v1/push)
    LOG_RETENTION_DAYS: Days to keep logs (default: 7)
    LOG_MAX_SIZE_MB: Max size per log file (default: 10)
"""

from __future__ import annotations

import asyncio
import functools
import gzip
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from logging.handlers import RotatingFileHandler
import threading

# Try optional Loki imports
try:
    import httpx
    LOKI_AVAILABLE = True
except ImportError:
    LOKI_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

# Default configuration
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "log_dir": str(Path.home() / ".claude" / "logs"),
    "log_to_console": True,
    "log_to_file": True,
    "log_to_loki": False,
    "loki_url": "http://localhost:3100/loki/api/v1/push",
    "loki_timeout": 5.0,
    "log_retention_days": 7,
    "log_max_size_mb": 10,
    "log_backup_count": 3,
    "pretty_json": False,  # Set True for development debugging
}

# Log level mapping
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Global state
_config: dict[str, Any] = {}
_loggers: dict[str, "StructuredLogger"] = {}
_loki_client: httpx.Client | None = None
_loki_lock = threading.Lock()
_correlation_id_context: threading.local = threading.local()


# =============================================================================
# Correlation ID Management
# =============================================================================

def get_correlation_id() -> str:
    """Get current correlation ID from context or generate new one."""
    try:
        return getattr(_correlation_id_context, "correlation_id", None)
    except Exception:
        return None


def set_correlation_id(correlation_id: str | None) -> None:
    """Set correlation ID in thread-local context."""
    try:
        _correlation_id_context.correlation_id = correlation_id
    except Exception:
        pass


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())[:8]


class CorrelationIdFilter(logging.Filter):
    """Filter that adds correlation_id to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.correlation_id = get_correlation_id() or ""
        except Exception:
            record.correlation_id = ""
        return True


# =============================================================================
# JSON Formatter
# =============================================================================

class StructuredJSONFormatter(logging.Formatter):
    """Formatter that outputs JSON with required fields for machine parsing."""

    def __init__(
        self,
        script_name: str = "",
        include_fields: list[str] | None = None,
        pretty: bool = False,
    ):
        super().__init__()
        self.script_name = script_name
        self.include_fields = include_fields or []
        self.pretty = pretty

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Build base record
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "script": self.script_name or record.name,
            "function": record.funcName,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add correlation ID if present
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_data["trace_id"] = correlation_id

        # Add line number for debugging
        if record.lineno > 0:
            log_data["line"] = record.lineno

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "msg", "args",
                "correlation_id",
            ):
                try:
                    # Convert complex types to JSON-serializable
                    log_data[key] = self._serialize_value(value)
                except Exception:
                    log_data[key] = str(value)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.format_exception(record.exc_info)

        # Add stack info if present
        if record.stack_info:
            log_data["stack_trace"] = record.stack_info

        # Apply include_fields filter
        if self.include_fields:
            log_data = {k: v for k, v in log_data.items() if k in self.include_fields}

        # Serialize to JSON
        if self.pretty:
            return json.dumps(log_data, indent=2, default=str)
        return json.dumps(log_data, default=str)

    def _serialize_value(self, value: Any) -> Any:
        """Serialize complex values to JSON-compatible types."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Exception):
            return str(value)
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        if hasattr(value, "__dict__"):
            return self._serialize_value(value.__dict__)
        try:
            return str(value)
        except Exception:
            return f"<non-serializable: {type(value).__name__}>"

    def format_exception(self, exc_info) -> dict[str, Any] | None:
        """Format exception info."""
        if not exc_info:
            return None
        exc_type, exc_value, exc_tb = exc_info
        return {
            "type": exc_type.__name__ if exc_type else "Unknown",
            "message": str(exc_value) if exc_value else "Unknown",
            "traceback": self.format_traceback(exc_tb),
        }

    def format_traceback(self, tb) -> list[dict[str, Any]]:
        """Format traceback as structured data."""
        frames = []
        while tb:
            frame = tb.tb_frame
            frames.append({
                "filename": frame.f_code.co_filename,
                "function": frame.f_code.co_name,
                "lineno": tb.tb_lineno,
            })
            tb = tb.tb_next
        return frames


# =============================================================================
# Loki Handler
# =============================================================================

class LokiHandler(logging.Handler):
    """Handler that sends logs to Loki for Grafana visualization."""

    def __init__(
        self,
        loki_url: str | None = None,
        labels: dict[str, str] | None = None,
        timeout: float = 5.0,
    ):
        super().__init__()
        self.loki_url = loki_url or DEFAULT_CONFIG["loki_url"]
        self.labels = labels or {}
        self.timeout = timeout
        self._buffer: list[dict] = []
        self._buffer_lock = threading.Lock()
        self._batch_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def emit(self, record: logging.LogRecord) -> None:
        """Buffer and ship log to Loki."""
        try:
            log_entry = self._format_entry(record)
            with self._buffer_lock:
                self._buffer.append(log_entry)
                # Start batch thread if not running
                if not self._batch_thread or not self._batch_thread.is_alive():
                    self._batch_thread = threading.Thread(
                        target=self._ship_batch,
                        daemon=True,
                    )
                    self._batch_thread.start()
        except Exception:
            pass  # Don't let logging failures crash the app

    def _format_entry(self, record: logging.LogRecord) -> dict:
        """Format log record as Loki stream entry."""
        return {
            "timestamp": int(record.created * 1_000_000_000),  # Nanoseconds
            "line": self.format(record),
        }

    def _ship_batch(self) -> None:
        """Ship buffered logs to Loki."""
        while not self._stop_event.is_set():
            try:
                self._stop_event.wait(timeout=1.0)  # Check every second
                with self._buffer_lock:
                    if not self._buffer:
                        continue
                    entries = self._buffer.copy()
                    self._buffer.clear()

                # Build Loki stream
                stream = {
                    "stream": {
                        "level": "info",  # Will be per-entry
                        "script": "continuous-claude",
                        **self.labels,
                    },
                    "values": [
                        [str(entry["timestamp"]), entry["line"]]
                        for entry in entries
                    ],
                }

                # Ship to Loki
                if LOKI_AVAILABLE:
                    try:
                        response = httpx.post(
                            self.loku_url,
                            json={"streams": [stream]},
                            timeout=self.timeout,
                        )
                        response.raise_for_status()
                    except Exception:
                        pass  # Silently fail - Loki is optional
            except Exception:
                pass

    def flush(self) -> None:
        """Flush remaining logs."""
        with self._buffer_lock:
            entries = self._buffer.copy()
            self._buffer.clear()
        # Ship remaining
        if entries and LOKI_AVAILABLE:
            try:
                stream = {
                    "stream": {"script": "continuous-claude", **self.labels},
                    "values": [
                        [str(entry["timestamp"]), entry["line"]]
                        for entry in entries
                    ],
                }
                httpx.post(
                    self.loki_url,
                    json={"streams": [stream]},
                    timeout=self.timeout,
                )
            except Exception:
                pass

    def close(self) -> None:
        """Close handler and flush buffer."""
        self._stop_event.set()
        self.flush()
        super().close()


# =============================================================================
# Structured Logger Class
# =============================================================================

class StructuredLogger:
    """Structured logger with correlation ID support."""

    def __init__(
        self,
        name: str,
        script_name: str = "",
        log_level: int = logging.INFO,
        log_dir: str = "",
    ):
        self.name = name
        self.script_name = script_name or name
        self._logger = logging.getLogger(name)
        self._logger.setLevel(log_level)
        self._logger.handlers = []  # Clear existing handlers

        # Get config
        global _config
        config = _config.copy()

        log_dir = log_dir or config.get("log_dir", DEFAULT_CONFIG["log_dir"])

        # Add correlation ID filter
        correlation_filter = CorrelationIdFilter()
        self._logger.addFilter(correlation_filter)

        # Console handler
        if config.get("log_to_console", DEFAULT_CONFIG["log_to_console"]):
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(
                StructuredJSONFormatter(
                    script_name=self.script_name,
                    pretty=config.get("pretty_json", DEFAULT_CONFIG["pretty_json"]),
                )
            )
            self._logger.addHandler(console_handler)

        # File handler with rotation
        if config.get("log_to_file", DEFAULT_CONFIG["log_to_file"]):
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_path / f"{name}.log",
                maxBytes=config.get("log_max_size_mb", DEFAULT_CONFIG["log_max_size_mb"]) * 1024 * 1024,
                backupCount=config.get("log_backup_count", DEFAULT_CONFIG["log_backup_count"]),
                encoding="utf-8",
            )
            file_handler.setFormatter(
                StructuredJSONFormatter(script_name=self.script_name)
            )
            self._logger.addHandler(file_handler)

        # Loki handler (optional)
        if config.get("log_to_loki", DEFAULT_CONFIG["log_to_loki"]) and LOKI_AVAILABLE:
            loki_handler = LokiHandler(
                loki_url=config.get("loki_url", DEFAULT_CONFIG["loki_url"]),
                labels={"script": self.script_name},
                timeout=config.get("loki_timeout", DEFAULT_CONFIG["loki_timeout"]),
            )
            self._logger.addHandler(loki_handler)

    def _log(
        self,
        level: int,
        message: str,
        trace_id: str | None = None,
        **kwargs,
    ):
        """Internal log method with correlation ID support."""
        # Set correlation ID if provided
        if trace_id:
            old_cid = get_correlation_id()
            set_correlation_id(trace_id)

        try:
            # Prepare extra kwargs for JSON formatter
            extra = {}
            for key, value in kwargs.items():
                if key not in ("exc_info", "stack_info", "stacklevel"):
                    extra[key] = value

            self._logger.log(
                level,
                message,
                exc_info=kwargs.get("exc_info"),
                stack_info=kwargs.get("stack_info"),
                extra=extra if extra else {},
            )
        finally:
            if trace_id:
                set_correlation_id(old_cid)

    def debug(
        self,
        message: str,
        trace_id: str | None = None,
        **kwargs,
    ):
        """DEBUG: Detailed flow tracing, variable states, control flow."""
        self._log(logging.DEBUG, message, trace_id, **kwargs)

    def info(
        self,
        message: str,
        trace_id: str | None = None,
        **kwargs,
    ):
        """INFO: Key operations, state changes, milestones."""
        self._log(logging.INFO, message, trace_id, **kwargs)

    def warning(
        self,
        message: str,
        trace_id: str | None = None,
        **kwargs,
    ):
        """WARNING: Degraded performance, retries, expected exceptions."""
        self._log(logging.WARNING, message, trace_id, **kwargs)

    def error(
        self,
        message: str,
        trace_id: str | None = None,
        exc_info: bool | None = None,
        **kwargs,
    ):
        """ERROR: Failures that don't crash the system."""
        self._log(logging.ERROR, message, trace_id, exc_info=exc_info, **kwargs)

    def critical(
        self,
        message: str,
        trace_id: str | None = None,
        exc_info: bool | None = None,
        **kwargs,
    ):
        """CRITICAL: System-level failures, unrecoverable errors."""
        self._log(logging.CRITICAL, message, trace_id, exc_info=exc_info, **kwargs)

    def exception(
        self,
        message: str,
        trace_id: str | None = None,
        **kwargs,
    ):
        """Log exception with full traceback."""
        self._log(logging.ERROR, message, trace_id, exc_info=True, **kwargs)

    def measure_time(
        self,
        operation: str,
        trace_id: str | None = None,
    ):
        """Context manager to measure operation time.

        Usage:
            with logger.measure_time("database_query"):
                await db.query()
        """
        return _MeasureTime(self, operation, trace_id)


class _MeasureTime:
    """Context manager for measuring operation duration."""

    def __init__(
        self,
        logger: StructuredLogger,
        operation: str,
        trace_id: str | None = None,
    ):
        self.logger = logger
        self.operation = operation
        self.trace_id = trace_id
        self.start_time: float | None = None
        self.duration_ms: float | None = None

    def __enter__(self):
        self.start_time = datetime.now(timezone.utc).timestamp()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (datetime.now(timezone.utc).timestamp() - self.start_time) * 1000
        if exc_type:
            self.logger.error(
                f"{self.operation} failed",
                trace_id=self.trace_id,
                duration_ms=self.duration_ms,
                operation=self.operation,
                error=str(exc_val),
                exc_info=True,
            )
        else:
            self.logger.debug(
                f"{self.operation} completed",
                trace_id=self.trace_id,
                duration_ms=round(self.duration_ms, 2),
                operation=self.operation,
            )
        return False


# =============================================================================
# Public API
# =============================================================================

def setup_logging(
    log_level: str | None = None,
    log_dir: str | None = None,
    log_to_console: bool | None = None,
    log_to_file: bool | None = None,
    log_to_loki: bool | None = None,
    loki_url: str | None = None,
    pretty_json: bool = False,
    script_name: str = "",
) -> dict[str, Any]:
    """Initialize the logging system.

    Args:
        log_level: DEBUG, INFO, WARNING, ERROR, CRITICAL
        log_dir: Directory for log files
        log_to_console: Enable console output
        log_to_file: Enable file logging
        log_to_loki: Enable Loki integration
        loki_url: Loki server URL
        pretty_json: Pretty-print JSON (for debugging)
        script_name: Default script name for logs

    Returns:
        Configuration dict
    """
    global _config

    # Build config from env vars and overrides
    _config = {
        "log_level": log_level or os.environ.get("LOG_LEVEL", DEFAULT_CONFIG["log_level"]),
        "log_dir": log_dir or os.environ.get("LOG_DIR", DEFAULT_CONFIG["log_dir"]),
        "log_to_console": log_to_console if log_to_console is not None else
            os.environ.get("LOG_TO_CONSOLE", str(DEFAULT_CONFIG["log_to_console"])).lower() == "true",
        "log_to_file": log_to_file if log_to_file is not None else
            os.environ.get("LOG_TO_FILE", str(DEFAULT_CONFIG["log_to_file"])).lower() == "true",
        "log_to_loki": log_to_loki if log_to_loki is not None else
            os.environ.get("LOG_TO_LOKI", str(DEFAULT_CONFIG["log_to_loki"])).lower() == "true",
        "loki_url": loki_url or os.environ.get("LOKI_URL", DEFAULT_CONFIG["loki_url"]),
        "loki_timeout": float(os.environ.get("LOKI_TIMEOUT", DEFAULT_CONFIG["loki_timeout"])),
        "log_retention_days": int(os.environ.get("LOG_RETENTION_DAYS", DEFAULT_CONFIG["log_retention_days"])),
        "log_max_size_mb": int(os.environ.get("LOG_MAX_SIZE_MB", DEFAULT_CONFIG["log_max_size_mb"])),
        "log_backup_count": int(os.environ.get("LOG_BACKUP_COUNT", DEFAULT_CONFIG["log_backup_count"])),
        "pretty_json": pretty_json,
    }

    # Set root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVELS.get(_config["log_level"], logging.INFO))

    return _config


def get_logger(
    name: str,
    script_name: str = "",
    log_level: str | None = None,
) -> StructuredLogger:
    """Get or create a structured logger.

    Args:
        name: Logger name (usually module name)
        script_name: Script/script name for log context
        log_level: Override log level

    Returns:
        StructuredLogger instance
    """
    global _loggers

    if name in _loggers:
        return _loggers[name]

    # Ensure logging is configured
    if not _config:
        setup_logging()

    # Determine log level
    level = logging.INFO
    if log_level:
        level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
    else:
        level = LOG_LEVELS.get(_config.get("log_level", "INFO"), logging.INFO)

    logger = StructuredLogger(
        name=name,
        script_name=script_name,
        log_level=level,
        log_dir=_config.get("log_dir"),
    )
    _loggers[name] = logger
    return logger


def get_correlation_logger(
    script_name: str,
    correlation_id: str | None = None,
) -> StructuredLogger:
    """Get logger with correlation context manager.

    Usage:
        with get_correlation_logger("memory_daemon", trace_id) as logger:
            logger.info("Processing started")
            # All logs in this block have the trace_id
    """
    logger = get_logger(script_name, script_name)
    return _CorrelationContext(logger, correlation_id)


class _CorrelationContext:
    """Context manager for correlation ID scope."""

    def __init__(
        self,
        logger: StructuredLogger,
        correlation_id: str | None = None,
    ):
        self.logger = logger
        self.correlation_id = correlation_id or generate_correlation_id()
        self._old_cid: str | None = None

    def __enter__(self):
        self._old_cid = get_correlation_id()
        set_correlation_id(self.correlation_id)
        self.logger.info("Correlation context started", trace_id=self.correlation_id)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.exception(
                "Correlation context ended with error",
                trace_id=self.correlation_id,
            )
        else:
            self.logger.info(
                "Correlation context ended",
                trace_id=self.correlation_id,
            )
        set_correlation_id(self._old_cid)
        return False


def log_function_call(
    logger: StructuredLogger,
    trace_id: str | None = None,
    log_args: bool = False,
    log_result: bool = False,
):
    """Decorator to log function calls with timing.

    Usage:
        @log_function_call(logger, log_args=True)
        async def my_function(param1, param2):
            ...
            return result
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with logger.measure_time(func.__name__, trace_id):
                if log_args:
                    logger.debug(
                        f"Calling {func.__name__}",
                        trace_id=trace_id,
                        args=str(args)[:500],
                        kwargs=str(kwargs)[:500],
                    )
                result = await func(*args, **kwargs)
                if log_result:
                    logger.debug(
                        f"{func.__name__} returned",
                        trace_id=trace_id,
                        result=str(result)[:500],
                    )
                return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with logger.measure_time(func.__name__, trace_id):
                if log_args:
                    logger.debug(
                        f"Calling {func.__name__}",
                        trace_id=trace_id,
                        args=str(args)[:500],
                        kwargs=str(kwargs)[:500],
                    )
                result = func(*args, **kwargs)
                if log_result:
                    logger.debug(
                        f"{func.__name__} returned",
                        trace_id=trace_id,
                        result=str(result)[:500],
                    )
                return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# =============================================================================
# Log Rotation Utility
# =============================================================================

def rotate_logs(log_dir: str, retention_days: int = 7) -> dict[str, int]:
    """Rotate and clean up old log files.

    Args:
        log_dir: Directory containing log files
        retention_days: Days to keep log files

    Returns:
        Dict with 'rotated' and 'deleted' counts
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return {"rotated": 0, "deleted": 0}

    cutoff_date = datetime.now(timezone.utc).timestamp() - (retention_days * 24 * 60 * 60)
    rotated = 0
    deleted = 0

    for log_file in log_path.glob("*.log*"):
        try:
            # Check modification time
            mtime = log_file.stat().st_mtime
            if mtime < cutoff_date:
                # Compress old logs
                if log_file.suffix == ".gz":
                    log_file.unlink()
                    deleted += 1
                else:
                    compressed = log_file.with_suffix(log_file.suffix + ".gz")
                    with open(log_file, "rb") as f_in:
                        with gzip.open(compressed, "wb") as f_out:
                            f_out.write(f_in.read())
                    log_file.unlink()
                    rotated += 1
        except Exception:
            pass

    return {"rotated": rotated, "deleted": deleted}


def tail_logs(log_dir: str, script_name: str, n_lines: int = 50) -> list[str]:
    """Get last n lines from a script's log file.

    Args:
        log_dir: Log directory
        script_name: Script name to get logs for
        n_lines: Number of lines to return

    Returns:
        List of log lines
    """
    log_file = Path(log_dir) / f"{script_name}.log"
    if not log_file.exists():
        return []

    lines = []
    with open(log_file, "r") as f:
        for line in f:
            lines.append(line.strip())
            if len(lines) > n_lines:
                lines = lines[-n_lines:]

    return lines


# =============================================================================
# Error Context Capture
# =============================================================================

def capture_error_context(
    logger: StructuredLogger,
    trace_id: str | None = None,
    additional_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture comprehensive error context for debugging.

    Returns a dict containing:
    - System info (Python version, platform)
    - Memory usage
    - Recent logs
    - Exception details

    Args:
        logger: Logger to use
        trace_id: Optional trace ID
        additional_context: Additional context to include

    Returns:
        Dict with error context
    """
    import gc
    import psutil
    import os

    context = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id or get_correlation_id() or generate_correlation_id(),
        "system": {
            "python_version": sys.version,
            "platform": sys.platform,
            "executable": sys.executable,
        },
        "memory": {
            "rss_mb": psutil.Process().memory_info().rss / (1024 * 1024),
            "gc_counts": gc.get_count(),
        },
    }

    if additional_context:
        context["additional"] = additional_context

    # Capture last 20 log lines
    if _config.get("log_dir"):
        context["recent_logs"] = tail_logs(_config["log_dir"], logger.script_name, 20)

    logger.error(
        "Error context captured",
        trace_id=context["trace_id"],
        **context,
    )

    return context


# =============================================================================
# Script Integration Helpers
# =============================================================================

def script_main(
    script_name: str,
    log_level: str = "INFO",
    include_caller_info: bool = True,
):
    """Decorator for script main functions.

    Usage:
        @script_main("memory_daemon")
        async def main():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(script_name, script_name, log_level)
            logger.info(f"Script {script_name} started")

            correlation_id = generate_correlation_id()
            set_correlation_id(correlation_id)

            try:
                result = await func(*args, **kwargs)
                logger.info(f"Script {script_name} completed", trace_id=correlation_id)
                return result
            except Exception as e:
                logger.exception(f"Script {script_name} failed", trace_id=correlation_id)
                capture_error_context(logger, correlation_id)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(script_name, script_name, log_level)
            logger.info(f"Script {script_name} started")

            correlation_id = generate_correlation_id()
            set_correlation_id(correlation_id)

            try:
                result = func(*args, **kwargs)
                logger.info(f"Script {script_name} completed", trace_id=correlation_id)
                return result
            except Exception as e:
                logger.exception(f"Script {script_name} failed", trace_id=correlation_id)
                capture_error_context(logger, correlation_id)
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
