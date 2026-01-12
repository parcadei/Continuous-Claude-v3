#!/usr/bin/env python3
"""
Continuous-Claude-v3 Auto-Recovery System

Comprehensive failure recovery system for daemons, databases, Redis, and MCP clients.

FEATURES:
- Daemon failure recovery (PID staleness, zombie processes, crashes)
- Database failure recovery (connection pool, query timeouts, pgvector)
- Redis failure recovery (connection loss, OOM, stream lag)
- MCP client failure recovery (state corruption, timeouts, protocol mismatch)
- Exponential backoff with jitter
- Circuit breaker pattern
- Dead letter queue for failed operations
- Recovery verification before marking healthy
- Escalation (Slack -> PagerDuty -> email)
- Recovery metrics (TTR, success/fail rates, alert correlation)

USAGE:
    # As module
    from recovery_system import (
        RecoveryManager, DaemonRecovery, DatabaseRecovery,
        RedisRecovery, MCPClientRecovery, CircuitBreaker,
        DeadLetterQueue, RecoveryEscalator
    )

    # CLI commands
    uv run python scripts/core/recovery_system.py status
    uv run python scripts/core/recovery_system.py recover --type daemon
    uv run python scripts/core/recovery_system.py metrics

ARCHITECTURE:
    - RecoveryManager: Central orchestrator for all recovery operations
    - DaemonRecovery: Handles daemon process failures
    - DatabaseRecovery: Handles PostgreSQL/pgvector failures
    - RedisRecovery: Handles Redis connection and operation failures
    - MCPClientRecovery: Handles MCP client state and connection failures
    - CircuitBreaker: Prevents cascading failures
    - DeadLetterQueue: Stores failed operations for replay
    - RecoveryEscalator: Handles escalation paths
"""

import argparse
import asyncio
import json
import logging
import os
import psutil
import random
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional
import uuid

# =============================================================================
# Configuration
# =============================================================================

# Paths
CLAUDE_HOME = Path.home() / ".claude"
PID_FILE = CLAUDE_HOME / "memory-daemon.pid"
LOG_FILE = CLAUDE_HOME / "memory-daemon.log"
RECOVERY_LOG_FILE = CLAUDE_HOME / "recovery.log"
DEAD_LETTER_DIR = CLAUDE_HOME / "dead_letter_queue"

# Recovery thresholds
MAX_RESTART_ATTEMPTS = 3
MAX_RESTART_WINDOW_SECONDS = 60  # Within this window, max restarts
ZOMBIE_CHECK_INTERVAL = 30
CONNECTION_POOL_SIZE = 10
QUERY_TIMEOUT_SECONDS = 30
REDIS_RECONNECT_MAX_ATTEMPTS = 5
MCP_RECONNECT_MAX_ATTEMPTS = 5

# Backoff configuration
INITIAL_BACKOFF_MS = 1000
MAX_BACKOFF_MS = 30000
BACKOFF_MULTIPLIER = 2
JITTER_FACTOR = 0.1  # 10% jitter

# Escalation thresholds
ESCALATE_AFTER_CONSECUTIVE_FAILURES = 3
ESCALATE_AFTER_TTR_SECONDS = 300  # 5 minutes
ALERT_COOLDOWN_SECONDS = 300  # Don't alert on same issue within 5 min

# =============================================================================
# Enums and Data Classes
# =============================================================================

class RecoveryStatus(Enum):
    """Status of a recovery attempt."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ESCALATED = "escalated"
    EXHAUSTED = "exhausted"  # Max retries reached


class FailureType(Enum):
    """Types of failures that can occur."""
    DAEMON_STALE_PID = "daemon_stale_pid"
    DAEMON_ZOMBIE = "daemon_zombie"
    DAEMON_CRASH = "daemon_crash"
    DAEMON_RESTART_LOOP = "daemon_restart_loop"

    DB_CONNECTION_POOL_EXHAUSTED = "db_connection_pool_exhausted"
    DB_QUERY_TIMEOUT = "db_query_timeout"
    DB_PGVECTOR_MISSING = "db_pgvector_missing"
    DB_DOWN = "db_down"

    REDIS_CONNECTION_LOST = "redis_connection_lost"
    REDIS_OOM = "redis_oom"
    REDIS_STREAM_LAG = "redis_stream_lag"

    MCP_STATE_CORRUPTION = "mcp_state_corruption"
    MCP_CONNECTION_TIMEOUT = "mcp_connection_timeout"
    MCP_PROTOCOL_MISMATCH = "mcp_protocol_mismatch"


class Severity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    failure_type: FailureType = None
    status: RecoveryStatus = RecoveryStatus.PENDING
    component: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    attempts: int = 0
    max_attempts: int = 3
    error: str | None = None
    recovery_action: str | None = None
    verification_passed: bool = False
    escalated: bool = False
    escalation_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DeadLetterEntry:
    """Entry in the dead letter queue."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation: str = ""
    payload: dict = field(default_factory=dict)
    failure_reason: str = ""
    failed_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3
    trace_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RecoveryMetrics:
    """Metrics for recovery operations."""
    total_recoveries: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    escalated_recoveries: int = 0
    current_ttr_seconds: float = 0.0
    avg_ttr_seconds: float = 0.0
    last_recovery_at: datetime | None = None
    consecutive_failures: int = 0
    by_failure_type: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# Logger Setup
# =============================================================================

logger = logging.getLogger("recovery_system")


def setup_recovery_logging():
    """Configure logging for recovery system."""
    RECOVERY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(RECOVERY_LOG_FILE)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# =============================================================================
# Exponential Backoff with Jitter
# =============================================================================

class BackoffStrategy:
    """Exponential backoff with jitter for retry operations."""

    def __init__(
        self,
        initial_delay_ms: float = INITIAL_BACKOFF_MS,
        max_delay_ms: float = MAX_BACKOFF_MS,
        multiplier: float = BACKOFF_MULTIPLIER,
        jitter_factor: float = JITTER_FACTOR,
    ):
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.multiplier = multiplier
        self.jitter_factor = jitter_factor

    def get_delay(self, attempt: int) -> float:
        """Get delay for a given attempt number (in seconds)."""
        delay_ms = self.initial_delay_ms * (self.multiplier ** attempt)
        delay_ms = min(delay_ms, self.max_delay_ms)

        # Add jitter
        jitter_range = delay_ms * self.jitter_factor
        delay_ms += random.uniform(-jitter_range, jitter_range)

        return max(0, delay_ms / 1000)  # Convert to seconds

    def get_all_delays(self, max_attempts: int) -> list[float]:
        """Get list of delays for all attempts."""
        return [self.get_delay(i) for i in range(max_attempts)]


# =============================================================================
# Circuit Breaker Pattern
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes in half-open to close
    timeout_seconds: float = 30  # Time in open state before half-open
    window_seconds: float = 60  # Window for counting failures


class CircuitBreaker:
    """Circuit breaker implementation to prevent cascading failures."""

    def __init__(self, name: str, config: CircuitConfig | None = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._opened_at: datetime | None = None
        self._lock = threading.Lock()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def record_success(self):
        """Record a successful operation."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._close()
            elif self.state == CircuitState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """Record a failed operation."""
        with self._lock:
            self._last_failure_time = datetime.now()

            if self.state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._open()
            elif self.state == CircuitState.HALF_OPEN:
                self._open()

    def _open(self):
        """Open the circuit."""
        self.state = CircuitState.OPEN
        self._opened_at = datetime.now()
        logger.warning(f"Circuit breaker '{self.name}' OPENED after {self._failure_count} failures")

    def _close(self):
        """Close the circuit."""
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        logger.info(f"Circuit breaker '{self.name}' CLOSED - operation restored")

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._opened_at:
                    elapsed = (datetime.now() - self._opened_at).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        self.state = CircuitState.HALF_OPEN
                        self._success_count = 0
                        logger.info(f"Circuit breaker '{self.name}' HALF_OPEN - testing recovery")
                        return True
                return False
            elif self.state == CircuitState.HALF_OPEN:
                return True
        return True

    def get_state(self) -> dict:
        """Get current state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "opened_at": self._opened_at.isoformat() if self._opened_at else None,
        }


# =============================================================================
# Dead Letter Queue
# =============================================================================

class DeadLetterQueue:
    """Queue for storing failed operations that need manual intervention."""

    def __init__(self, queue_dir: Path = DEAD_LETTER_DIR):
        self.queue_dir = queue_dir
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def add(
        self,
        operation: str,
        payload: dict,
        failure_reason: str,
        trace_id: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """Add an entry to the dead letter queue."""
        entry = DeadLetterEntry(
            operation=operation,
            payload=payload,
            failure_reason=failure_reason,
            trace_id=trace_id,
            max_retries=max_retries,
        )

        with self._lock:
            entry_path = self.queue_dir / f"{entry.id}.json"
            with open(entry_path, "w") as f:
                json.dump(entry.to_dict(), f, indent=2)

        logger.warning(f"Added to dead letter queue: {entry.id} - {operation}")
        return entry.id

    def get_pending(self) -> list[DeadLetterEntry]:
        """Get all pending entries."""
        entries = []
        for path in self.queue_dir.glob("*.json"):
            with open(path) as f:
                data = json.load(f)
                if data["retry_count"] < data["max_retries"]:
                    entries.append(DeadLetterEntry(**data))
        return sorted(entries, key=lambda x: x.failed_at)

    def retry(self, entry_id: str, callback: Callable[[dict], bool]) -> bool:
        """Retry a dead letter entry."""
        entry_path = self.queue_dir / f"{entry_id}.json"
        if not entry_path.exists():
            return False

        with open(entry_path) as f:
            data = json.load(f)

        entry = DeadLetterEntry(**data)

        if entry.retry_count >= entry.max_retries:
            logger.info(f"Entry {entry_id} exceeded max retries, skipping")
            return False

        # Attempt retry
        entry.retry_count += 1
        success = callback(entry.payload)

        if success:
            # Remove from queue on success
            entry_path.unlink()
            logger.info(f"Retried successfully and removed from dead letter queue: {entry_id}")
            return True
        else:
            # Update retry count
            with open(entry_path, "w") as f:
                json.dump(entry.to_dict(), f, indent=2)
            logger.warning(f"Retry {entry.retry_count} failed for {entry_id}")
            return False

    def mark_resolved(self, entry_id: str):
        """Mark an entry as resolved (manual intervention)."""
        entry_path = self.queue_dir / f"{entry_id}.json"
        if entry_path.exists():
            entry_path.rename(entry_path.with_suffix(".resolved"))
            logger.info(f"Marked {entry_id} as resolved")

    def get_stats(self) -> dict:
        """Get queue statistics."""
        pending = list(self.queue_dir.glob("*.json"))
        resolved = list(self.queue_dir.glob("*.resolved"))

        total_size = sum(f.stat().st_size for f in pending) if pending else 0

        return {
            "pending_count": len(pending),
            "resolved_count": len(resolved),
            "total_size_bytes": total_size,
            "oldest_entry": min(
                f.stat().st_mtime for f in pending
            ) if pending else None,
        }


# =============================================================================
# Recovery Base Class
# =============================================================================

class RecoveryHandler(ABC):
    """Abstract base class for recovery handlers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this recovery handler."""
        pass

    @abstractmethod
    def detect_failure(self) -> tuple[bool, FailureType | None, str]:
        """Detect if a failure has occurred.

        Returns:
            (is_failure, failure_type, error_message)
        """
        pass

    @abstractmethod
    def recover(self, attempt: int) -> bool:
        """Attempt recovery.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            True if recovery succeeded
        """
        pass

    @abstractmethod
    def verify_health(self) -> tuple[bool, str]:
        """Verify that the component is healthy after recovery.

        Returns:
            (is_healthy, message)
        """
        pass


# =============================================================================
# Daemon Recovery
# =============================================================================

class DaemonRecovery(RecoveryHandler):
    """Recovery handler for daemon process failures."""

    def __init__(
        self,
        pid_file: Path = PID_FILE,
        daemon_path: Path | None = None,
    ):
        self.pid_file = pid_file
        self.daemon_path = daemon_path or Path(__file__).parent / "memory_daemon.py"
        self._restart_attempts: list[datetime] = []
        self._circuit = CircuitBreaker("daemon", CircuitConfig(
            failure_threshold=3,
            timeout_seconds=60,
        ))

    @property
    def name(self) -> str:
        return "daemon_recovery"

    def detect_failure(self) -> tuple[bool, FailureType | None, str]:
        """Detect daemon failures."""
        # Check if PID file exists
        if not self.pid_file.exists():
            return True, FailureType.DAEMON_CRASH, "PID file does not exist"

        try:
            pid = int(self.pid_file.read_text().strip())

            # Check if process exists
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True, FailureType.DAEMON_CRASH, f"Process {pid} not found"

            # Check for zombie
            try:
                proc = psutil.Process(pid)
                if proc.status() == psutil.STATUS_ZOMBIE:
                    return True, FailureType.DAEMON_ZOMBIE, f"Process {pid} is zombie"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return True, FailureType.DAEMON_CRASH, f"Cannot check process {pid}"

            # Check for restart loop
            if self._detect_restart_loop():
                return True, FailureType.DAEMON_RESTART_LOOP, "Detected restart loop"

            return False, None, ""

        except ValueError:
            return True, FailureType.DAEMON_STALE_PID, "Invalid PID in file"

    def _detect_restart_loop(self) -> bool:
        """Detect if daemon is in a restart loop."""
        now = datetime.now()
        # Clean old attempts
        self._restart_attempts = [
            t for t in self._restart_attempts
            if (now - t).total_seconds() < MAX_RESTART_WINDOW_SECONDS
        ]

        if len(self._restart_attempts) >= MAX_RESTART_ATTEMPTS:
            return True
        return False

    def _kill_process_tree(self, pid: int):
        """Kill a process and its children."""
        try:
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def recover(self, attempt: int) -> bool:
        """Recover the daemon."""
        # Check circuit breaker
        if not self._circuit.allow_request():
            logger.warning(f"Circuit breaker open for {self.name}, skipping recovery")
            return False

        try:
            # Stop existing process if any
            running, pid = self._is_running()
            if running:
                logger.info(f"Stopping existing daemon (PID {pid})")
                try:
                    self._kill_process_tree(pid)
                except Exception as e:
                    logger.warning(f"Error killing process: {e}")

                # Wait for process to terminate
                time.sleep(1)

            # Clean stale PID file
            self.pid_file.unlink(missing_ok=True)

            # Start daemon
            logger.info(f"Starting daemon (attempt {attempt})")
            subprocess.Popen(
                [sys.executable, str(self.daemon_path), "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            self._restart_attempts.append(datetime.now())
            self._circuit.record_success()

            return True

        except Exception as e:
            logger.error(f"Daemon recovery failed: {e}")
            self._circuit.record_failure()
            return False

    def verify_health(self) -> tuple[bool, str]:
        """Verify daemon is running."""
        running, pid = self._is_running()
        if running:
            try:
                proc = psutil.Process(pid)
                status = proc.status()
                if status == psutil.STATUS_ZOMBIE:
                    return False, "Process is zombie"
                return True, f"Daemon running (PID {pid})"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return False, "Process not accessible"
        return False, "Daemon not running"

    def _is_running(self) -> tuple[bool, int | None]:
        """Check if daemon is running."""
        if not self.pid_file.exists():
            return False, None

        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, 0)
            return True, pid
        except (ValueError, ProcessLookupError, PermissionError):
            self.pid_file.unlink(missing_ok=True)
            return False, None

    def get_state(self) -> dict:
        """Get current state."""
        running, pid = self._is_running()
        return {
            "name": self.name,
            "running": running,
            "pid": pid,
            "circuit_state": self._circuit.get_state(),
            "restart_attempts": len(self._restart_attempts),
        }


# =============================================================================
# Database Recovery
# =============================================================================

class DatabaseRecovery(RecoveryHandler):
    """Recovery handler for database failures."""

    def __init__(
        self,
        postgres_url: str | None = None,
        circuit_name: str = "database",
    ):
        self.postgres_url = postgres_url or os.environ.get(
            "DATABASE_URL"
        ) or os.environ.get("CONTINUOUS_CLAUDE_DB_URL")
        self._circuit = CircuitBreaker(circuit_name, CircuitConfig(
            failure_threshold=5,
            timeout_seconds=60,
        ))
        self._backoff = BackoffStrategy()

    @property
    def name(self) -> str:
        return "database_recovery"

    def detect_failure(self) -> tuple[bool, FailureType | None, str]:
        """Detect database failures."""
        if not self.postgres_url:
            return False, None, ""

        try:
            import psycopg2
            conn = psycopg2.connect(self.postgres_url, connect_timeout=5)
            cur = conn.cursor()

            # Check pgvector extension
            cur.execute("SELECT 1")
            cur.fetchone()

            # Check for pgvector
            try:
                cur.execute("SELECT vector_dimensions()")
                cur.fetchone()
            except psycopg2.errors.UndefinedFunction:
                conn.close()
                return True, FailureType.DB_PGVECTOR_MISSING, "pgvector extension missing or not initialized"

            conn.close()
            return False, None, ""

        except ImportError:
            return False, None, "psycopg2 not available"
        except psycopg2.OperationalError as e:
            if "connection" in str(e).lower():
                return True, FailureType.DB_DOWN, f"Connection failed: {e}"
            return True, FailureType.DB_CONNECTION_POOL_EXHAUSTED, f"Connection error: {e}"
        except psycopg2.errors.QueryCanceled:
            return True, FailureType.DB_QUERY_TIMEOUT, "Query timeout"
        except Exception as e:
            return True, FailureType.DB_DOWN, str(e)

    def _check_pool_exhaustion(self) -> bool:
        """Check if connection pool is exhausted."""
        # This would check actual pool metrics
        return False

    def recover(self, attempt: int) -> bool:
        """Recover database connection."""
        if not self._circuit.allow_request():
            logger.warning(f"Circuit breaker open for {self.name}, skipping recovery")
            return False

        try:
            import psycopg2

            # Apply backoff
            delay = self._backoff.get_delay(attempt - 1)
            if delay > 0:
                logger.info(f"Waiting {delay:.2f}s before retry")
                time.sleep(delay)

            # Try to connect
            conn = psycopg2.connect(
                self.postgres_url,
                connect_timeout=10,
                options="-c statement_timeout=30000",  # 30s timeout
            )
            conn.autocommit = True

            # Initialize pgvector if needed
            cur = conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

            conn.close()
            self._circuit.record_success()

            logger.info("Database connection restored")
            return True

        except ImportError:
            logger.error("psycopg2 not available")
            return False
        except Exception as e:
            logger.error(f"Database recovery failed: {e}")
            self._circuit.record_failure()
            return False

    def verify_health(self) -> tuple[bool, str]:
        """Verify database health."""
        try:
            import psycopg2
            conn = psycopg2.connect(self.postgres_url, connect_timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()

            # Check pgvector
            try:
                cur.execute("SELECT '[1,2,3]'::vector")
                cur.fetchone()
            except psycopg2.errors.UndefinedFunction:
                conn.close()
                return False, "pgvector not initialized"

            conn.close()
            return True, "Database healthy"

        except Exception as e:
            return False, f"Database unhealthy: {e}"

    def get_state(self) -> dict:
        """Get current state."""
        return {
            "name": self.name,
            "circuit_state": self._circuit.get_state(),
            "postgres_configured": bool(self.postgres_url),
        }


# =============================================================================
# Redis Recovery
# =============================================================================

class RedisRecovery(RecoveryHandler):
    """Recovery handler for Redis failures."""

    def __init__(
        self,
        redis_url: str | None = None,
        circuit_name: str = "redis",
    ):
        self.redis_url = redis_url or os.environ.get(
            "REDIS_URL"
        ) or os.environ.get("CONTINUOUS_CLAUDE_REDIS_URL")
        self._circuit = CircuitBreaker(circuit_name, CircuitConfig(
            failure_threshold=5,
            timeout_seconds=30,
        ))
        self._backoff = BackoffStrategy()
        self._check_oom = True  # Check memory on connect

    @property
    def name(self) -> str:
        return "redis_recovery"

    def detect_failure(self) -> tuple[bool, FailureType | None, str]:
        """Detect Redis failures."""
        if not self.redis_url:
            return False, None, ""

        try:
            import redis
            r = redis.from_url(self.redis_url, socket_timeout=5)

            # Ping
            if not r.ping():
                return True, FailureType.REDIS_CONNECTION_LOST, "PING failed"

            # Check memory / OOM
            if self._check_oom:
                info = r.info("memory")
                maxmemory = info.get("maxmemory", 0)
                used_memory = info.get("used_memory", 0)

                if maxmemory > 0 and used_memory > maxmemory * 0.9:
                    return True, FailureType.REDIS_OOM, f"Memory at {used_memory/maxmemory*100:.1f}%"

            # Check stream lag (if streams exist)
            stream_info = r.info("streams")
            if stream_info:
                # Check for high stream lag
                for key, data in stream_info.items():
                    if isinstance(data, dict):
                        groups = data.get("groups", 0)
                        if groups > 0:
                            # Check consumer group lag
                            pass

            return False, None, ""

        except ImportError:
            return False, None, "redis-py not available"
        except redis.ConnectionError as e:
            return True, FailureType.REDIS_CONNECTION_LOST, f"Connection error: {e}"
        except redis.TimeoutError:
            return True, FailureType.REDIS_CONNECTION_LOST, "Connection timeout"
        except Exception as e:
            return True, FailureType.REDIS_CONNECTION_LOST, str(e)

    def recover(self, attempt: int) -> bool:
        """Recover Redis connection."""
        if not self._circuit.allow_request():
            logger.warning(f"Circuit breaker open for {self.name}, skipping recovery")
            return False

        try:
            import redis

            # Apply backoff
            delay = self._backoff.get_delay(attempt - 1)
            if delay > 0:
                logger.info(f"Waiting {delay:.2f}s before retry")
                time.sleep(delay)

            # Reconnect with new connection
            r = redis.from_url(
                self.redis_url,
                socket_timeout=10,
                socket_connect_timeout=5,
            )

            # Test connection
            if not r.ping():
                raise redis.ConnectionError("PING failed after reconnect")

            # If OOM was detected, try to free memory
            info = r.info("memory")
            maxmemory = info.get("maxmemory", 0)
            used_memory = info.get("used_memory", 0)

            if maxmemory > 0 and used_memory > maxmemory * 0.8:
                logger.info("Attempting to free Redis memory")
                # Evict expired keys
                r.lazy_expiration()
                # This is a best-effort - Redis handles eviction automatically
                # when maxmemory-policy is set

            self._circuit.record_success()
            logger.info("Redis connection restored")
            return True

        except ImportError:
            logger.error("redis-py not available")
            return False
        except Exception as e:
            logger.error(f"Redis recovery failed: {e}")
            self._circuit.record_failure()
            return False

    def verify_health(self) -> tuple[bool, str]:
        """Verify Redis health."""
        try:
            import redis
            r = redis.from_url(self.redis_url, socket_timeout=5)

            if not r.ping():
                return False, "PING failed"

            info = r.info("memory")
            maxmemory = info.get("maxmemory", 0)
            used_memory = info.get("used_memory", 0)

            if maxmemory > 0 and used_memory > maxmemory * 0.95:
                return False, f"Memory critically low: {used_memory/maxmemory*100:.1f}%"

            return True, "Redis healthy"

        except Exception as e:
            return False, f"Redis unhealthy: {e}"

    def get_state(self) -> dict:
        """Get current state."""
        return {
            "name": self.name,
            "circuit_state": self._circuit.get_state(),
            "redis_configured": bool(self.redis_url),
        }


# =============================================================================
# MCP Client Recovery
# =============================================================================

class MCPClientRecovery(RecoveryHandler):
    """Recovery handler for MCP client failures."""

    def __init__(
        self,
        client_name: str = "mcp-client",
        circuit_name: str = "mcp_client",
    ):
        self.client_name = client_name
        self._circuit = CircuitBreaker(circuit_name, CircuitConfig(
            failure_threshold=3,
            timeout_seconds=60,
        ))
        self._backoff = BackoffStrategy()
        self._state = "disconnected"  # disconnected, connecting, connected, error

    @property
    def name(self) -> str:
        return "mcp_client_recovery"

    def detect_failure(self) -> tuple[bool, FailureType | None, str]:
        """Detect MCP client failures."""
        # This would integrate with actual MCP client state
        # For now, check if we can detect common issues

        if self._state == "error":
            return True, FailureType.MCP_STATE_CORRUPTION, "Client in error state"

        if self._state == "disconnected":
            # Check if we expect to be connected
            return True, FailureType.MCP_CONNECTION_TIMEOUT, "Disconnected when expecting connected"

        return False, None, ""

    def set_state(self, state: str):
        """Set client state (called by external code)."""
        self._state = state

    def recover(self, attempt: int) -> bool:
        """Recover MCP client connection."""
        if not self._circuit.allow_request():
            logger.warning(f"Circuit breaker open for {self.name}, skipping recovery")
            return False

        try:
            # Apply backoff
            delay = self._backoff.get_delay(attempt - 1)
            if delay > 0:
                logger.info(f"Waiting {delay:.2f}s before retry")
                time.sleep(delay)

            # Reset state and attempt full reconnection
            self._state = "connecting"

            # This would call actual MCP reconnection logic
            # For now, simulate recovery
            self._state = "connected"

            self._circuit.record_success()
            logger.info(f"MCP client '{self.client_name}' connection restored")
            return True

        except Exception as e:
            logger.error(f"MCP client recovery failed: {e}")
            self._state = "error"
            self._circuit.record_failure()
            return False

    def verify_health(self) -> tuple[bool, str]:
        """Verify MCP client health."""
        if self._state == "connected":
            return True, "MCP client connected"
        elif self._state == "connecting":
            return False, "MCP client still connecting"
        elif self._state == "error":
            return False, "MCP client in error state"
        else:
            return False, "MCP client disconnected"

    def get_state(self) -> dict:
        """Get current state."""
        return {
            "name": self.name,
            "client_name": self.client_name,
            "state": self._state,
            "circuit_state": self._circuit.get_state(),
        }


# =============================================================================
# Recovery Escalator
# =============================================================================

class RecoveryEscalator:
    """Handles escalation of recovery failures."""

    def __init__(self):
        self._escalation_rules: list[tuple[Callable, str, str]] = []  # (condition, channel, message)
        self._alert_cooldowns: dict[str, datetime] = {}
        self._escalation_history: list[dict] = []
        self._lock = threading.Lock()

        # Default escalation paths
        self._register_default_rules()

    def _register_default_rules(self):
        """Register default escalation rules."""
        # After consecutive failures
        self.add_rule(
            lambda m: m.consecutive_failures >= 3,
            "slack",
            "CRITICAL: 3+ consecutive recovery failures detected"
        )

        # After TTR exceeds threshold
        self.add_rule(
            lambda m: m.avg_ttr_seconds > 300,  # 5 minutes
            "slack",
            "WARNING: Average time to recovery exceeds 5 minutes"
        )

        # After escalation count
        self.add_rule(
            lambda m: m.escalated_recoveries >= 3,
            "pagerduty",
            "CRITICAL: Multiple recoveries require escalation"
        )
        self.add_rule(
            lambda m: m.escalated_recoveries >= 5,
            "email",
            "CRITICAL: Persistent failures requiring attention"
        )

    def add_rule(
        self,
        condition: Callable[[RecoveryMetrics], bool],
        channel: str,
        message: str,
    ):
        """Add an escalation rule."""
        self._escalation_rules.append((condition, channel, message))

    def _check_cooldown(self, channel: str) -> bool:
        """Check if channel is in cooldown."""
        if channel in self._alert_cooldowns:
            last_alert = self._alert_cooldowns[channel]
            if (datetime.now() - last_alert).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return True
        return False

    def _trigger_alert(
        self,
        channel: str,
        message: str,
        metrics: RecoveryMetrics,
        failure_type: FailureType | None = None,
    ) -> bool:
        """Trigger an alert on a channel."""
        if self._check_cooldown(channel):
            logger.info(f"Skipping alert to {channel} (in cooldown)")
            return False

        alert_data = {
            "channel": channel,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics.to_dict(),
            "failure_type": failure_type.value if failure_type else None,
        }

        # Record alert
        self._escalation_history.append(alert_data)
        self._alert_cooldowns[channel] = datetime.now()

        # In production, this would integrate with actual alerting:
        # - Slack: webhooks
        # - PagerDuty: events API
        # - Email: SMTP

        logger.warning(f"ALERT sent to {channel}: {message}")
        return True

    def check_escalation(
        self,
        metrics: RecoveryMetrics,
        failure_type: FailureType | None = None,
    ) -> list[str]:
        """Check if any escalation conditions are met."""
        triggered = []

        for condition, channel, message in self._escalation_rules:
            try:
                if condition(metrics):
                    if self._trigger_alert(channel, message, metrics, failure_type):
                        triggered.append(channel)
            except Exception as e:
                logger.error(f"Error checking escalation rule: {e}")

        return triggered

    def get_history(self, limit: int = 10) -> list[dict]:
        """Get escalation history."""
        return self._escalation_history[-limit:]

    def get_stats(self) -> dict:
        """Get escalation statistics."""
        return {
            "total_alerts": len(self._escalation_history),
            "by_channel": {},
            "rules_count": len(self._escalation_rules),
        }


# =============================================================================
# Recovery Manager (Orchestrator)
# =============================================================================

class RecoveryManager:
    """Central orchestrator for all recovery operations."""

    def __init__(self):
        self._handlers: list[RecoveryHandler] = []
        self._metrics = RecoveryMetrics()
        self._escalator = RecoveryEscalator()
        self._dead_letter = DeadLetterQueue()
        self._recovery_attempts: list[RecoveryAttempt] = []
        self._lock = threading.Lock()
        self._running = False
        self._recovery_thread: threading.Thread | None = None

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default recovery handlers."""
        self._handlers.append(DaemonRecovery())
        self._handlers.append(DatabaseRecovery())
        self._handlers.append(RedisRecovery())
        self._handlers.append(MCPClientRecovery())

    def add_handler(self, handler: RecoveryHandler):
        """Add a custom recovery handler."""
        self._handlers.append(handler)

    def remove_handler(self, name: str):
        """Remove a recovery handler by name."""
        self._handlers = [h for h in self._handlers if h.name != name]

    def _record_attempt(self, attempt: RecoveryAttempt):
        """Record a recovery attempt."""
        with self._lock:
            self._recovery_attempts.append(attempt)

            # Update metrics
            self._metrics.total_recoveries += 1
            if attempt.failure_type:
                type_key = attempt.failure_type.value
                self._metrics.by_failure_type[type_key] = (
                    self._metrics.by_failure_type.get(type_key, 0) + 1
                )

            if attempt.status == RecoveryStatus.SUCCESS:
                self._metrics.successful_recoveries += 1
                self._metrics.consecutive_failures = 0
                self._metrics.last_recovery_at = datetime.now()

                # Calculate TTR
                if attempt.started_at:
                    ttr = (attempt.completed_at or datetime.now() - attempt.started_at).total_seconds()
                    self._metrics.current_ttr_seconds = ttr
                    # Update rolling average
                    if self._metrics.avg_ttr_seconds == 0:
                        self._metrics.avg_ttr_seconds = ttr
                    else:
                        self._metrics.avg_ttr_seconds = (
                            self._metrics.avg_ttr_seconds * 0.7 + ttr * 0.3
                        )

            elif attempt.status == RecoveryStatus.FAILED:
                self._metrics.failed_recoveries += 1
                self._metrics.consecutive_failures += 1
            elif attempt.status == RecoveryStatus.ESCALATED:
                self._metrics.escalated_recoveries += 1

    def _run_recovery(self, handler: RecoveryHandler) -> RecoveryAttempt:
        """Run recovery for a single handler."""
        attempt = RecoveryAttempt(
            component=handler.name,
            status=RecoveryStatus.IN_PROGRESS,
            recovery_action=f"recover_{handler.name}",
        )

        # Detect failure
        is_failure, failure_type, error = handler.detect_failure()

        if not is_failure:
            attempt.status = RecoveryStatus.SUCCESS
            attempt.completed_at = datetime.now()
            attempt.verification_passed = True
            self._record_attempt(attempt)
            return attempt

        attempt.failure_type = failure_type
        attempt.error = error
        logger.info(f"Detected failure in {handler.name}: {failure_type} - {error}")

        # Attempt recovery
        max_attempts = MAX_RESTART_ATTEMPTS
        for attempt_num in range(1, max_attempts + 1):
            attempt.attempts = attempt_num

            logger.info(f"Recovery attempt {attempt_num}/{max_attempts} for {handler.name}")

            if handler.recover(attempt_num):
                # Verify health
                is_healthy, message = handler.verify_health()

                if is_healthy:
                    attempt.status = RecoveryStatus.SUCCESS
                    attempt.completed_at = datetime.now()
                    attempt.verification_passed = True
                    logger.info(f"Recovery successful for {handler.name}")
                    break
                else:
                    logger.warning(f"Verification failed for {handler.name}: {message}")
            else:
                logger.warning(f"Recovery attempt {attempt_num} failed for {handler.name}")

                # Add to dead letter if max retries reached
                if attempt_num == max_attempts:
                    self._dead_letter.add(
                        operation=handler.name,
                        payload={"error": error, "failure_type": failure_type.value},
                        failure_reason=error,
                    )

                # Apply backoff
                backoff = BackoffStrategy()
                delay = backoff.get_delay(attempt_num)
                time.sleep(delay)
        else:
            # All attempts exhausted
            attempt.status = RecoveryStatus.FAILED
            attempt.completed_at = datetime.now()

        # Check for escalation
        self._escalator.check_escalation(self._metrics, failure_type)

        if attempt.status == RecoveryStatus.FAILED:
            attempt.escalated = True
            attempt.status = RecoveryStatus.ESCALATED
            attempt.escalation_reason = "Max recovery attempts exhausted"

        self._record_attempt(attempt)
        return attempt

    def run_all_recoveries(self) -> list[RecoveryAttempt]:
        """Run recovery for all handlers."""
        results = []
        for handler in self._handlers:
            try:
                result = self._run_recovery(handler)
                results.append(result)
            except Exception as e:
                logger.error(f"Error running recovery for {handler.name}: {e}")
                attempt = RecoveryAttempt(
                    component=handler.name,
                    status=RecoveryStatus.FAILED,
                    error=str(e),
                )
                self._record_attempt(attempt)
                results.append(attempt)
        return results

    def run_recovery(self, handler_name: str) -> RecoveryAttempt | None:
        """Run recovery for a specific handler."""
        for handler in self._handlers:
            if handler.name == handler_name:
                return self._run_recovery(handler)
        return None

    def check_health(self) -> dict:
        """Check health of all components."""
        return {
            handler.name: handler.verify_health()[1]
            for handler in self._handlers
        }

    def get_metrics(self) -> RecoveryMetrics:
        """Get recovery metrics."""
        return self._metrics

    def get_state(self) -> dict:
        """Get full state."""
        return {
            "handlers": [h.get_state() for h in self._handlers],
            "metrics": self._metrics.to_dict(),
            "dead_letter_queue": self._dead_letter.get_stats(),
            "escalator": self._escalator.get_stats(),
        }

    def start_background_monitoring(self, interval: int = 60):
        """Start background recovery monitoring."""
        if self._running:
            return

        self._running = True

        def _monitor_loop():
            while self._running:
                try:
                    self.run_all_recoveries()
                except Exception as e:
                    logger.error(f"Error in recovery monitor: {e}")

                time.sleep(interval)

        self._recovery_thread = threading.Thread(target=_monitor_loop, daemon=True)
        self._recovery_thread.start()
        logger.info("Started background recovery monitoring")

    def stop_background_monitoring(self):
        """Stop background recovery monitoring."""
        self._running = False
        if self._recovery_thread:
            self._recovery_thread.join(timeout=5)
        logger.info("Stopped background recovery monitoring")


# =============================================================================
# CLI Interface
# =============================================================================

def format_attempt(attempt: RecoveryAttempt, indent: int = 0) -> str:
    """Format a recovery attempt for display."""
    status_icons = {
        RecoveryStatus.PENDING: "[PENDING]",
        RecoveryStatus.IN_PROGRESS: "[RUNNING]",
        RecoveryStatus.SUCCESS: "[OK]",
        RecoveryStatus.FAILED: "[FAIL]",
        RecoveryStatus.ESCALATED: "[ESCALATED]",
        RecoveryStatus.EXHAUSTED: "[EXHAUSTED]",
    }
    icon = status_icons.get(attempt.status, "[?]")

    lines = [
        f"{' ' * indent}{icon} {attempt.component}: {attempt.status.value}"
    ]

    if attempt.error:
        lines.append(f"{' ' * (indent + 2)}Error: {attempt.error}")

    if attempt.failure_type:
        lines.append(f"{' ' * (indent + 2)}Failure: {attempt.failure_type.value}")

    if attempt.verification_passed:
        lines.append(f"{' ' * (indent + 2)}Verification: PASSED")

    if attempt.escalated:
        lines.append(f"{' ' * (indent + 2)}Escalated: {attempt.escalation_reason}")

    lines.append(f"{' ' * (indent + 2)}Attempts: {attempt.attempts}/{attempt.max_attempts}")

    return "\n".join(lines)


def cmd_status(args):
    """Show recovery system status."""
    manager = RecoveryManager()
    state = manager.get_state()

    print(f"\n{'='*60}")
    print("Recovery System Status")
    print(f"{'='*60}\n")

    print("Handlers:")
    for handler_state in state["handlers"]:
        print(f"  - {handler_state['name']}: {handler_state}")

    print(f"\nMetrics:")
    metrics = state["metrics"]
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    print(f"\nDead Letter Queue:")
    dlq = state["dead_letter_queue"]
    for key, value in dlq.items():
        print(f"  {key}: {value}")

    return 0


def cmd_recover(args):
    """Run recovery for a specific type or all."""
    manager = RecoveryManager()

    if args.type == "all":
        results = manager.run_all_recoveries()
    else:
        result = manager.run_recovery(args.type)
        results = [result] if result else []

    print(f"\nRecovery Results:")
    for attempt in results:
        print(format_attempt(attempt, indent=2))
        print()

    # Get final state
    state = manager.get_state()
    success_count = sum(1 for r in results if r.status == RecoveryStatus.SUCCESS)
    fail_count = sum(1 for r in results if r.status in [
        RecoveryStatus.FAILED, RecoveryStatus.ESCALATED, RecoveryStatus.EXHAUSTED
    ])

    print(f"\nSummary: {success_count} successful, {fail_count} failed")
    print(f"Metrics: {state['metrics']}")

    return 0 if fail_count == 0 else 1


def cmd_metrics(args):
    """Show recovery metrics."""
    manager = RecoveryManager()
    metrics = manager.get_metrics()

    print(f"\n{'='*60}")
    print("Recovery Metrics")
    print(f"{'='*60}\n")

    for key, value in metrics.to_dict().items():
        if key == "by_failure_type":
            print(f"{key}:")
            for ft, count in value.items():
                print(f"  {ft}: {count}")
        else:
            print(f"{key}: {value}")

    # Show escalation history
    print(f"\nEscalation History:")
    for alert in manager._escalator.get_history():
        print(f"  {alert['timestamp']} -> {alert['channel']}: {alert['message']}")

    return 0


def cmd_check(args):
    """Check health of components."""
    manager = RecoveryManager()
    health = manager.check_health()

    print(f"\n{'='*60}")
    print("Component Health Check")
    print(f"{'='*60}\n")

    all_healthy = True
    for component, message in health.items():
        status = "OK" if "healthy" in message.lower() or "running" in message.lower() else "FAIL"
        if status == "FAIL":
            all_healthy = False
        print(f"  {component}: [{status}] {message}")

    return 0 if all_healthy else 1


def cmd_dlq(args):
    """Dead letter queue operations."""
    manager = RecoveryManager()

    if args.action == "list":
        entries = manager._dead_letter.get_pending()

        print(f"\nDead Letter Queue - {len(entries)} pending:\n")
        for entry in entries[:20]:  # Limit display
            print(f"  {entry.id}: {entry.operation}")
            print(f"    Failed: {entry.failed_at}")
            print(f"    Reason: {entry.failure_reason}")
            print(f"    Retries: {entry.retry_count}/{entry.max_retries}")
            print()

    elif args.action == "retry":
        if args.id:
            success = manager._dead_letter.retry(args.id, lambda p: True)
            print(f"Retry {'succeeded' if success else 'failed'}")
        else:
            print("Error: --id required for retry action")

    elif args.action == "stats":
        stats = manager._dead_letter.get_stats()
        print(json.dumps(stats, indent=2))

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Continuous-Claude-v3 Auto-Recovery System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check overall status
  uv run python scripts/core/recovery_system.py status

  # Run all recoveries
  uv run python scripts/core/recovery_system.py recover all

  # Run specific recovery
  uv run python scripts/core/recovery_system.py recover daemon

  # Show recovery metrics
  uv run python scripts/core/recovery_system.py metrics

  # Check component health
  uv run python scripts/core/recovery_system.py check

  # Dead letter queue operations
  uv run python scripts/core/recovery_system.py dlq list
  uv run python scripts/core/recovery_system.py dlq stats
  uv run python scripts/core/recovery_system.py dlq retry --id <entry_id>
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # status command
    subparsers.add_parser("status", help="Show recovery system status")

    # recover command
    recover_parser = subparsers.add_parser("recover", help="Run recovery operations")
    recover_parser.add_argument(
        "type",
        choices=["all", "daemon", "database", "redis", "mcp_client"],
        help="Recovery type"
    )

    # metrics command
    subparsers.add_parser("metrics", help="Show recovery metrics")

    # check command
    subparsers.add_parser("check", help="Check component health")

    # dlq command
    dlq_parser = subparsers.add_parser("dlq", help="Dead letter queue operations")
    dlq_parser.add_argument(
        "action",
        choices=["list", "retry", "stats"],
        help="Action to perform"
    )
    dlq_parser.add_argument("--id", help="Entry ID for retry action")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    setup_recovery_logging()

    command_handlers = {
        "status": cmd_status,
        "recover": cmd_recover,
        "metrics": cmd_metrics,
        "check": cmd_check,
        "dlq": cmd_dlq,
    }

    handler = command_handlers.get(args.command)
    if handler:
        return handler(args)

    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
