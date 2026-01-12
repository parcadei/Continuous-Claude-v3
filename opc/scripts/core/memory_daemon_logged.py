#!/usr/bin/env python3
"""
Memory Daemon with Structured Logging

Example integration showing:
- PID acquisition logging
- Poll cycle metrics
- Extraction spawn tracking
- Stuck detection events
- Queue state monitoring

Run with:
    uv run python scripts/core/memory_daemon_logged.py start
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Import structured logging
from scripts.core.logging_config import (
    get_logger,
    setup_logging,
    get_correlation_logger,
    generate_correlation_id,
    script_main,
    log_function_call,
)

# Load .env files
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)

opc_env = Path(__file__).parent.parent.parent / ".env"
if opc_env.exists():
    load_dotenv(opc_env, override=True)

# Configuration
POLL_INTERVAL = 60
STALE_THRESHOLD = 300
MAX_CONCURRENT_EXTRACTIONS = 2
PID_FILE = Path.home() / ".claude" / "memory-daemon.pid"

# Global state
active_extractions: dict[int, str] = {}
pending_queue: list[tuple[str, str]] = []


# =============================================================================
# Logger Setup
# =============================================================================

logger = get_logger("memory_daemon", "memory_daemon")


# =============================================================================
# Logging Wrappers
# =============================================================================

def log_pid_acquisition(daemon_pid: int) -> None:
    """Log PID file acquisition and validation."""
    logger.info(
        f"Acquired PID file for daemon",
        trace_id=generate_correlation_id(),
        daemon_pid=daemon_pid,
        pid_file=str(PID_FILE),
        operation="pid_acquisition",
    )


def log_poll_cycle_start() -> dict[str, Any]:
    """Log start of poll cycle with metrics."""
    cycle_id = generate_correlation_id()
    logger.info(
        "Poll cycle started",
        trace_id=cycle_id,
        operation="poll_cycle",
        cycle_start=datetime.now(timezone.utc).isoformat(),
    )
    return {"cycle_id": cycle_id, "start_time": time.time()}


def log_poll_cycle_end(cycle_data: dict[str, Any], stale_count: int) -> None:
    """Log end of poll cycle with duration and results."""
    duration_ms = (time.time() - cycle_data["start_time"]) * 1000
    logger.info(
        "Poll cycle completed",
        trace_id=cycle_data["cycle_id"],
        operation="poll_cycle",
        duration_ms=round(duration_ms, 2),
        stale_sessions_found=stale_count,
        active_extractions=len(active_extractions),
        queued_sessions=len(pending_queue),
    )


def log_extraction_spawn(
    session_id: str,
    project_dir: str,
    extraction_pid: int,
    correlation_id: str,
) -> None:
    """Log extraction process spawning."""
    logger.info(
        "Extraction process spawned",
        trace_id=correlation_id,
        operation="extraction_spawn",
        session_id=session_id,
        project_dir=project_dir,
        extraction_pid=extraction_pid,
        concurrency_active=len(active_extractions),
        concurrency_limit=MAX_CONCURRENT_EXTRACTIONS,
    )


def log_extraction_complete(session_id: str, extraction_pid: int) -> None:
    """Log extraction completion."""
    logger.info(
        "Extraction process completed",
        trace_id=generate_correlation_id(),
        operation="extraction_complete",
        session_id=session_id,
        extraction_pid=extraction_pid,
        duration_estimate="<tracked>",
    )


def log_stale_session_found(session_id: str, project: str | None, cycle_id: str) -> None:
    """Log when a stale session is detected."""
    logger.info(
        "Stale session detected",
        trace_id=cycle_id,
        operation="stale_detection",
        session_id=session_id,
        project=project or "unknown",
    )


def log_queue_state_change(
    action: str,
    session_id: str,
    queue_before: int,
    queue_after: int,
) -> None:
    """Log queue state changes (enqueue/dequeue)."""
    logger.info(
        f"Queue state changed: {action}",
        trace_id=generate_correlation_id(),
        operation="queue_update",
        action=action,
        session_id=session_id,
        queue_before=queue_before,
        queue_after=queue_after,
    )


# =============================================================================
# Database Operations
# =============================================================================

def get_postgres_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("CONTINUOUS_CLAUDE_DB_URL")


def use_postgres() -> bool:
    url = get_postgres_url()
    if not url:
        return False
    try:
        import psycopg2
        return True
    except ImportError:
        return False


def get_stale_sessions() -> list:
    """Get stale sessions - wrapped with logging."""
    with logger.measure_time("get_stale_sessions"):
        if use_postgres():
            import psycopg2
            conn = psycopg2.connect(get_postgres_url())
            cur = conn.cursor()
            threshold = datetime.now() - timedelta(seconds=STALE_THRESHOLD)
            cur.execute("""
                SELECT id, project FROM sessions
                WHERE last_heartbeat < %s AND memory_extracted_at IS NULL
            """, (threshold,))
            rows = cur.fetchall()
            conn.close()
            return rows
        else:
            db_path = Path.home() / ".claude" / "sessions.db"
            if not db_path.exists():
                return []
            conn = sqlite3.connect(db_path)
            threshold = (datetime.now() - timedelta(seconds=STALE_THRESHOLD)).isoformat()
            cursor = conn.execute("""
                SELECT id, project FROM sessions
                WHERE last_heartbeat < ? AND memory_extracted_at IS NULL
            """, (threshold,))
            rows = cursor.fetchall()
            conn.close()
            return rows


def mark_extracted(session_id: str) -> None:
    """Mark session as extracted."""
    if use_postgres():
        import psycopg2
        conn = psycopg2.connect(get_postgres_url())
        cur = conn.cursor()
        cur.execute("UPDATE sessions SET memory_extracted_at = NOW() WHERE id = %s", (session_id,))
        conn.commit()
        conn.close()
    else:
        db_path = Path.home() / ".claude" / "sessions.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE sessions SET memory_extracted_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), session_id),
        )
        conn.commit()
        conn.close()


# =============================================================================
# Extraction Logic
# =============================================================================

def extract_memories(session_id: str, project_dir: str) -> None:
    """Run memory extraction for a session."""
    correlation_id = generate_correlation_id()

    logger.info(
        "Starting memory extraction",
        trace_id=correlation_id,
        session_id=session_id,
        project_dir=project_dir,
    )

    # Find JSONL file
    jsonl_dir = Path.home() / ".opc-dev" / "projects"
    if not jsonl_dir.exists():
        jsonl_dir = Path.home() / ".claude" / "projects"

    jsonl_path = None
    for f in sorted(jsonl_dir.glob("*/*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
        if session_id in f.name or f.stem == session_id:
            jsonl_path = f
            break

    if not jsonl_path:
        logger.warning(
            "No JSONL found for session",
            trace_id=correlation_id,
            session_id=session_id,
            operation="extraction_skip",
        )
        return

    # Get agent prompt
    agent_file = Path.home() / ".opc-dev" / ".claude" / "agents" / "memory-extractor.md"
    if not agent_file.exists():
        agent_file = Path.home() / ".claude" / "agents" / "memory-extractor.md"

    agent_prompt = ""
    if agent_file.exists():
        content = agent_file.read_text()
        if content.startswith("---"):
            parts = content.split("---", 2)
            agent_prompt = parts[2].strip() if len(parts) >= 3 else content
        else:
            agent_prompt = content

    # Spawn extraction process
    try:
        proc = subprocess.Popen(
            [
                "claude", "-p",
                "--model", "sonnet",
                "--dangerously-skip-permissions",
                "--max-turns", "15",
                "--append-system-prompt", agent_prompt,
                f"Extract learnings from session {session_id}. JSONL path: {jsonl_path}"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        active_extractions[proc.pid] = session_id
        log_extraction_spawn(session_id, project_dir, proc.pid, correlation_id)

    except Exception as e:
        logger.exception(
            "Failed to start extraction",
            trace_id=correlation_id,
            session_id=session_id,
            error=str(e),
        )


def reap_completed_extractions() -> int:
    """Check for completed extraction processes."""
    completed = []
    for pid, session_id in active_extractions.items():
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            completed.append(pid)
            log_extraction_complete(session_id, pid)
        except PermissionError:
            pass

    for pid in completed:
        del active_extractions[pid]

    return len(completed)


def process_pending_queue() -> int:
    """Spawn extractions from queue if under concurrency limit."""
    spawned = 0
    while pending_queue and len(active_extractions) < MAX_CONCURRENT_EXTRACTIONS:
        queue_before = len(pending_queue)
        session_id, project = pending_queue.pop(0)
        queue_after = len(pending_queue)
        log_queue_state_change("dequeue", session_id, queue_before, queue_after)

        extract_memories(session_id, project or "")
        spawned += 1

    return spawned


def queue_or_extract(session_id: str, project: str) -> None:
    """Queue extraction if at limit, otherwise extract immediately."""
    queue_before = len(pending_queue)

    if len(active_extractions) >= MAX_CONCURRENT_EXTRACTIONS:
        pending_queue.append((session_id, project))
        queue_after = len(pending_queue)
        log_queue_state_change("enqueue", session_id, queue_before, queue_after)
    else:
        extract_memories(session_id, project or "")


# =============================================================================
# Daemon Loop
# =============================================================================

def daemon_loop() -> None:
    """Main daemon loop with comprehensive logging."""
    db_type = "PostgreSQL" if use_postgres() else "SQLite"
    daemon_pid = os.getpid()

    logger.info(
        "Memory daemon started",
        trace_id=generate_correlation_id(),
        daemon_pid=daemon_pid,
        database_type=db_type,
        poll_interval_seconds=POLL_INTERVAL,
        max_concurrent_extractions=MAX_CONCURRENT_EXTRACTIONS,
    )
    log_pid_acquisition(daemon_pid)

    while True:
        try:
            # Log poll cycle start
            cycle_data = log_poll_cycle_start()

            # Reap completed processes and process pending queue
            completed = reap_completed_extractions()
            spawned = process_pending_queue()

            # Find new stale sessions
            stale = get_stale_sessions()

            if stale:
                logger.info(
                    "Found stale sessions to process",
                    trace_id=cycle_data["cycle_id"],
                    stale_count=len(stale),
                )

                for session_id, project in stale:
                    log_stale_session_found(session_id, project, cycle_data["cycle_id"])
                    queue_or_extract(session_id, project or "")
                    mark_extracted(session_id)

            # Log poll cycle end
            log_poll_cycle_end(cycle_data, len(stale))

        except Exception as e:
            logger.exception(
                "Error in daemon loop",
                trace_id=generate_correlation_id(),
                error=str(e),
            )

        time.sleep(POLL_INTERVAL)


# =============================================================================
# Daemon Management
# =============================================================================

def is_running() -> tuple[bool, int | None]:
    if not PID_FILE.exists():
        return False, None

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True, pid
    except (ValueError, ProcessLookupError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return False, None


def _run_as_daemon():
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    sys.stdin.close()
    sys.stdout.close()
    sys.stderr.close()

    try:
        daemon_loop()
    finally:
        PID_FILE.unlink(missing_ok=True)


def start_daemon():
    running, pid = is_running()
    if running:
        print(f"Memory daemon already running (PID {pid})")
        return 0

    logger.info("Starting memory daemon")

    if sys.platform == "win32":
        DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        try:
            with open(os.devnull, "r+b") as devnull:
                subprocess.Popen(
                    [sys.executable, __file__, "--daemon-subprocess"],
                    creationflags=DETACHED_PROCESS,
                    stdin=devnull,
                    stdout=devnull,
                    stderr=devnull,
                )
            print("Memory daemon started")
            return 0
        except Exception as e:
            print(f"Failed to start daemon: {e}")
            return 1
    else:
        if os.fork() > 0:
            print("Memory daemon started")
            return 0

        os.setsid()
        if os.fork() > 0:
            sys.exit(0)

        _run_as_daemon()


def stop_daemon():
    running, pid = is_running()
    if not running:
        print("Memory daemon not running")
        return 0

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped memory daemon (PID {pid})")
        PID_FILE.unlink(missing_ok=True)
        return 0
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return 0


def status_daemon():
    running, pid = is_running()
    db_type = "PostgreSQL" if use_postgres() else "SQLite"

    print(f"Memory Daemon Status")
    print(f"  Running: {'Yes' if running else 'No'}")
    if running:
        print(f"  PID: {pid}")
    print(f"  Database: {db_type}")
    print(f"  PID file: {PID_FILE}")

    return 0


# =============================================================================
# Main Entry
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Memory Daemon with Structured Logging")
    parser.add_argument("command", nargs="?", choices=["start", "stop", "status"])
    parser.add_argument("--daemon-subprocess", action="store_true")
    args = parser.parse_args()

    if args.daemon_subprocess:
        _run_as_daemon()
        return 0

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "start":
        return start_daemon()
    elif args.command == "stop":
        return stop_daemon()
    elif args.command == "status":
        return status_daemon()


if __name__ == "__main__":
    setup_logging(script_name="memory_daemon", log_level="INFO")
    sys.exit(main())
