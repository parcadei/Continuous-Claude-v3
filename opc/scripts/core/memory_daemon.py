#!/usr/bin/env python3
"""
Global Memory Extraction Daemon

A singleton daemon that monitors for stale Claude sessions and automatically
extracts learnings when sessions end (heartbeat goes stale).

USAGE:
    # Start daemon (if not already running)
    uv run python scripts/core/memory_daemon.py start

    # Check status
    uv run python scripts/core/memory_daemon.py status

    # Stop daemon
    uv run python scripts/core/memory_daemon.py stop

ARCHITECTURE:
    - Single global instance (PID file at ~/.claude/memory-daemon.pid)
    - Works with PostgreSQL or SQLite
    - Polls every 60 seconds for stale sessions (heartbeat > 5 min)
    - Runs headless `claude -p` for memory extraction
    - Marks sessions as extracted to prevent re-processing

The session_start hook ensures this daemon is running.
"""

import argparse
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load .env files for DATABASE_URL (cross-platform)
# 1. Global ~/.claude/.env (API keys, may have DB config)
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)

# 2. Local opc/.env (relative to script location)
# Script is at opc/scripts/core/memory_daemon.py, .env is at opc/.env
opc_env = Path(__file__).parent.parent.parent / ".env"
if opc_env.exists():
    load_dotenv(opc_env, override=True)  # Override with project-specific values

# Global config
POLL_INTERVAL = 60  # seconds
STALE_THRESHOLD = 300  # 5 minutes in seconds
MAX_CONCURRENT_EXTRACTIONS = 2  # Limit concurrent headless claude processes
PID_FILE = Path.home() / ".claude" / "memory-daemon.pid"
LOG_FILE = Path.home() / ".claude" / "memory-daemon.log"

# Worker queue state (module-level for daemon process)
active_extractions: dict[int, str] = {}  # pid -> session_id
pending_queue: list[tuple[str, str]] = []  # [(session_id, project), ...]


def _process_exists(pid: int) -> bool:
    """Check if a process exists, cross-platform."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def log(msg: str):
    """Write timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception:
        pass  # Don't crash on log failures


def get_postgres_url() -> str | None:
    """Get PostgreSQL URL from environment (canonical first)."""
    return os.environ.get("CONTINUOUS_CLAUDE_DB_URL") or os.environ.get("DATABASE_URL")


def use_postgres() -> bool:
    """Check if PostgreSQL is available."""
    url = get_postgres_url()
    if not url:
        return False
    try:
        import psycopg2  # noqa: F401
        return True
    except ImportError:
        return False


# Database operations - PostgreSQL
def pg_ensure_column():
    """Ensure memory_extracted_at column exists in PostgreSQL."""
    import psycopg2
    conn = psycopg2.connect(get_postgres_url())
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE sessions
        ADD COLUMN IF NOT EXISTS memory_extracted_at TIMESTAMP
    """)
    conn.commit()
    conn.close()


def pg_get_stale_sessions() -> list:
    """Get sessions with stale heartbeat that haven't been extracted."""
    import psycopg2
    conn = psycopg2.connect(get_postgres_url())
    cur = conn.cursor()
    threshold = datetime.now() - timedelta(seconds=STALE_THRESHOLD)
    cur.execute("""
        SELECT id, project FROM sessions
        WHERE last_heartbeat < %s
        AND memory_extracted_at IS NULL
    """, (threshold,))
    rows = cur.fetchall()
    conn.close()
    return rows


def pg_mark_extracted(session_id: str):
    """Mark session as extracted in PostgreSQL."""
    import psycopg2
    conn = psycopg2.connect(get_postgres_url())
    cur = conn.cursor()
    cur.execute("""
        UPDATE sessions SET memory_extracted_at = NOW() WHERE id = %s
    """, (session_id,))
    conn.commit()
    conn.close()


# Database operations - SQLite
def get_sqlite_path() -> Path:
    """Get SQLite database path."""
    # Use global path for cross-repo sessions
    return Path.home() / ".claude" / "sessions.db"


def sqlite_ensure_table():
    """Ensure sessions table exists in SQLite with required columns."""
    db_path = get_sqlite_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            project TEXT,
            working_on TEXT,
            started_at TIMESTAMP,
            last_heartbeat TIMESTAMP,
            memory_extracted_at TIMESTAMP
        )
    """)
    # Add column if table already exists without it
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN memory_extracted_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()


def sqlite_get_stale_sessions() -> list:
    """Get sessions with stale heartbeat that haven't been extracted."""
    db_path = get_sqlite_path()
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    threshold = (datetime.now() - timedelta(seconds=STALE_THRESHOLD)).isoformat()
    cursor = conn.execute("""
        SELECT id, project FROM sessions
        WHERE last_heartbeat < ?
        AND memory_extracted_at IS NULL
    """, (threshold,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def sqlite_mark_extracted(session_id: str):
    """Mark session as extracted in SQLite."""
    db_path = get_sqlite_path()
    conn = sqlite3.connect(db_path)
    conn.execute("""
        UPDATE sessions SET memory_extracted_at = ? WHERE id = ?
    """, (datetime.now().isoformat(), session_id))
    conn.commit()
    conn.close()


# Unified interface
def ensure_schema():
    """Ensure database schema is ready."""
    if use_postgres():
        pg_ensure_column()
    else:
        sqlite_ensure_table()


def get_stale_sessions() -> list:
    """Get stale sessions from database."""
    if use_postgres():
        return pg_get_stale_sessions()
    return sqlite_get_stale_sessions()


def mark_extracted(session_id: str):
    """Mark session as extracted."""
    if use_postgres():
        pg_mark_extracted(session_id)
    else:
        sqlite_mark_extracted(session_id)


def extract_memories(session_id: str, project_dir: str):
    """Run memory extraction for a session."""
    log(f"Extracting memories for session {session_id} in {project_dir}")

    # Find the most recent JSONL for this session
    jsonl_dir = Path.home() / ".opc-dev" / "projects"
    if not jsonl_dir.exists():
        jsonl_dir = Path.home() / ".claude" / "projects"

    # Look for session JSONL
    jsonl_path = None
    for f in sorted(jsonl_dir.glob("*/*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
        if session_id in f.name or f.stem == session_id:
            jsonl_path = f
            break

    if not jsonl_path:
        log(f"No JSONL found for session {session_id}, skipping")
        return

    # Run headless memory extraction
    try:
        # Read agent prompt from memory-extractor.md (strip YAML frontmatter)
        agent_file = Path.home() / ".opc-dev" / ".claude" / "agents" / "memory-extractor.md"
        if not agent_file.exists():
            agent_file = Path.home() / ".claude" / "agents" / "memory-extractor.md"

        agent_prompt = ""
        if agent_file.exists():
            content = agent_file.read_text()
            # Strip YAML frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                agent_prompt = parts[2].strip() if len(parts) >= 3 else content
            else:
                agent_prompt = content
        else:
            # Fallback minimal prompt
            agent_prompt = """Extract learnings from this Claude Code session.
Look for decisions, what worked, what failed, and patterns discovered.
Store each learning using store_learning.py with appropriate type and tags."""

        cmd = [
            "claude", "-p",
            "--model", "sonnet",
            "--dangerously-skip-permissions",
            "--max-turns", "15",
            "--append-system-prompt", agent_prompt,
            f"Extract learnings from session {session_id}. JSONL path: {jsonl_path}"
        ]
        if sys.platform == "win32":
            DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=DETACHED_PROCESS
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        active_extractions[proc.pid] = session_id
        log(f"Started extraction for {session_id} (pid={proc.pid}, active={len(active_extractions)})")
    except Exception as e:
        log(f"Failed to start extraction: {e}")


def reap_completed_extractions():
    """Check for completed extraction processes and remove from active set."""
    completed = []
    for pid, session_id in active_extractions.items():
        if not _process_exists(pid):
            completed.append(pid)
            log(f"Extraction completed for {session_id} (pid={pid})")

    for pid in completed:
        del active_extractions[pid]

    return len(completed)


def process_pending_queue():
    """Spawn extractions from queue if under concurrency limit."""
    spawned = 0
    while pending_queue and len(active_extractions) < MAX_CONCURRENT_EXTRACTIONS:
        session_id, project = pending_queue.pop(0)
        log(f"Dequeuing {session_id} (queue remaining: {len(pending_queue)})")
        extract_memories(session_id, project)
        spawned += 1
    return spawned


def queue_or_extract(session_id: str, project: str):
    """Queue extraction if at limit, otherwise extract immediately."""
    if len(active_extractions) >= MAX_CONCURRENT_EXTRACTIONS:
        pending_queue.append((session_id, project))
        log(f"Queued {session_id} (active={len(active_extractions)}, queue={len(pending_queue)})")
    else:
        extract_memories(session_id, project)


def daemon_loop():
    """Main daemon loop."""
    db_type = "PostgreSQL" if use_postgres() else "SQLite"
    log(f"Memory daemon started (using {db_type}, max_concurrent={MAX_CONCURRENT_EXTRACTIONS})")
    ensure_schema()

    while True:
        try:
            # Reap completed processes and process pending queue
            reap_completed_extractions()
            process_pending_queue()

            # Find new stale sessions
            stale = get_stale_sessions()
            if stale:
                log(f"Found {len(stale)} stale sessions")
                for session_id, project in stale:
                    queue_or_extract(session_id, project or "")
                    mark_extracted(session_id)
        except Exception as e:
            log(f"Error in daemon loop: {e}")

        time.sleep(POLL_INTERVAL)


def is_running() -> tuple[bool, int | None]:
    """Check if daemon is already running."""
    if not PID_FILE.exists():
        return False, None

    try:
        pid = int(PID_FILE.read_text().strip())
        if _process_exists(pid):
            return True, pid
        else:
            PID_FILE.unlink(missing_ok=True)
            return False, None
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return False, None


def _run_as_daemon():
    """Run the daemon loop (called by subprocess on Windows, directly after fork on Unix)."""
    # Write PID file
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    # Close standard file descriptors
    sys.stdin.close()
    sys.stdout.close()
    sys.stderr.close()

    # Run daemon
    try:
        daemon_loop()
    finally:
        PID_FILE.unlink(missing_ok=True)


def start_daemon():
    """Start the daemon if not already running.

    Cross-platform: Uses subprocess.DETACHED_PROCESS on Windows,
    double-fork on Unix (macOS/Linux).
    """
    running, pid = is_running()
    if running:
        print(f"Memory daemon already running (PID {pid})")
        return 0

    if sys.platform == "win32":
        # Windows: spawn as detached subprocess
        # Uses DETACHED_PROCESS flag to run independently of parent
        # Reference: MongoDB pymongo/daemon.py pattern
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
        # Unix (macOS/Linux): classic double-fork
        if os.fork() > 0:
            print("Memory daemon started")
            return 0

        # Detach from terminal
        os.setsid()

        # Fork again to prevent zombie
        if os.fork() > 0:
            sys.exit(0)

        _run_as_daemon()


def stop_daemon():
    """Stop the daemon."""
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
    """Show daemon status."""
    running, pid = is_running()
    db_type = "PostgreSQL" if use_postgres() else "SQLite"

    print(f"Memory Daemon Status")
    print(f"  Running: {'Yes' if running else 'No'}")
    if running:
        print(f"  PID: {pid}")
    print(f"  Database: {db_type}")
    print(f"  PID file: {PID_FILE}")
    print(f"  Log file: {LOG_FILE}")

    # Show recent log
    if LOG_FILE.exists():
        print(f"\nRecent log:")
        lines = LOG_FILE.read_text().strip().split("\n")[-5:]
        for line in lines:
            print(f"  {line}")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Global Memory Extraction Daemon")
    parser.add_argument("command", nargs="?", choices=["start", "stop", "status"], help="Command")
    parser.add_argument("--daemon-subprocess", action="store_true",
                        help="Internal: run as daemon subprocess (Windows)")
    args = parser.parse_args()

    # Windows subprocess entry point
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
    sys.exit(main() or 0)
