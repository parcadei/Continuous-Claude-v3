#!/usr/bin/env python3
"""Continuous knowledge tree update daemon.

Watches project directory for changes and automatically updates
the knowledge tree. Debounces rapid changes to avoid excessive updates.

Usage:
    uv run python scripts/core/core/tree_daemon.py --project /path/to/project
    uv run python scripts/core/core/tree_daemon.py --project . --debounce 1000

The daemon runs in the background and updates .claude/knowledge-tree.json
whenever significant changes are detected.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    FileSystemEventHandler = object

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".cache", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "target", ".idea", ".vscode"
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".lock", ".log", ".tmp"
}

TRIGGER_FILES = {
    "README.md", "readme.md", "package.json", "pyproject.toml",
    "ROADMAP.md", "roadmap.md", "CLAUDE.md", "docker-compose.yml",
    "Dockerfile", ".env.example", "tsconfig.json", "Cargo.toml", "go.mod"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("tree-daemon")


def should_ignore_path(path: Path) -> bool:
    parts = path.parts
    for part in parts:
        if part in IGNORE_DIRS:
            return True
    if path.suffix.lower() in IGNORE_EXTENSIONS:
        return True
    return False


def is_significant_change(path: Path) -> bool:
    name = path.name
    if name in TRIGGER_FILES:
        return True
    if path.is_dir():
        return True
    if name.endswith(".md"):
        return True
    return False


class TreeDaemon:
    def __init__(self, project_path: Path, debounce_ms: int = 500):
        self.project_path = project_path.resolve()
        self.tree_path = self.project_path / ".claude" / "knowledge-tree.json"
        self.pid_path = self.project_path / ".claude" / "tree-daemon.pid"
        self.log_path = self.project_path / ".claude" / "tree-daemon.log"
        self.debounce_ms = debounce_ms
        self.pending_update = False
        self.last_update_time = 0.0
        self.lock = threading.Lock()
        self.running = True
        self._setup_logging()

    def _setup_logging(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(self.log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(fh)

    def _write_pid(self):
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid(self):
        if self.pid_path.exists():
            self.pid_path.unlink()

    def schedule_update(self):
        with self.lock:
            self.pending_update = True
            self.last_update_time = time.time()

    def _update_tree(self):
        try:
            from knowledge_tree import generate_tree, save_tree
        except ImportError:
            try:
                from .knowledge_tree import generate_tree, save_tree
            except ImportError:
                log.error("Cannot import knowledge_tree module")
                return False

        try:
            log.info("Regenerating knowledge tree...")
            tree = generate_tree(self.project_path)
            save_tree(tree, self.tree_path)
            log.info(f"Tree updated: {len(tree.get('structure', {}).get('directories', {}))} directories")
            return True
        except Exception as e:
            log.error(f"Failed to update tree: {e}")
            return False

    def _debounce_loop(self):
        while self.running:
            time.sleep(0.1)

            with self.lock:
                if not self.pending_update:
                    continue
                elapsed = (time.time() - self.last_update_time) * 1000
                if elapsed < self.debounce_ms:
                    continue
                self.pending_update = False

            self._update_tree()

    def run(self):
        if not HAS_WATCHDOG:
            log.error("watchdog not installed. Run: pip install watchdog")
            sys.exit(1)

        self._write_pid()
        log.info(f"Tree daemon started for: {self.project_path}")
        log.info(f"PID: {os.getpid()}, Debounce: {self.debounce_ms}ms")

        if not self.tree_path.exists():
            log.info("Initial tree generation...")
            self._update_tree()

        handler = TreeEventHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self.project_path), recursive=True)
        observer.start()

        debounce_thread = threading.Thread(target=self._debounce_loop, daemon=True)
        debounce_thread.start()

        def signal_handler(signum, frame):
            log.info("Shutdown signal received")
            self.running = False
            observer.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False

        observer.stop()
        observer.join()
        self._remove_pid()
        log.info("Tree daemon stopped")


class TreeEventHandler(FileSystemEventHandler):
    def __init__(self, daemon: TreeDaemon):
        self.daemon = daemon

    def _handle_event(self, event: FileSystemEvent):
        if event.is_directory:
            return

        path = Path(event.src_path)

        if should_ignore_path(path):
            return

        if is_significant_change(path):
            log.debug(f"Significant change: {event.event_type} {path.name}")
            self.daemon.schedule_update()

    def on_created(self, event):
        self._handle_event(event)

    def on_deleted(self, event):
        self._handle_event(event)

    def on_modified(self, event):
        self._handle_event(event)

    def on_moved(self, event):
        self._handle_event(event)


def check_existing_daemon(project_path: Path) -> int | None:
    pid_path = project_path / ".claude" / "tree-daemon.pid"
    if not pid_path.exists():
        return None

    try:
        pid = int(pid_path.read_text().strip())
    except (ValueError, FileNotFoundError):
        return None

    if sys.platform == "win32":
        try:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return pid
        except Exception:
            pass
    else:
        try:
            os.kill(pid, 0)
            return pid
        except OSError:
            pass

    pid_path.unlink()
    return None


def stop_daemon(project_path: Path) -> bool:
    pid = check_existing_daemon(project_path)
    if not pid:
        return False

    try:
        if sys.platform == "win32":
            PROCESS_TERMINATE = 0x0001
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                ctypes.windll.kernel32.TerminateProcess(handle, 0)
                ctypes.windll.kernel32.CloseHandle(handle)
        else:
            os.kill(pid, signal.SIGTERM)

        pid_path = project_path / ".claude" / "tree-daemon.pid"
        time.sleep(0.5)
        if pid_path.exists():
            pid_path.unlink()

        return True
    except Exception as e:
        log.error(f"Failed to stop daemon: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Knowledge tree update daemon")
    parser.add_argument("--project", "-p", required=True, help="Project root directory")
    parser.add_argument("--debounce", "-d", type=int, default=500, help="Debounce delay in ms (default: 500)")
    parser.add_argument("--stop", action="store_true", help="Stop running daemon")
    parser.add_argument("--status", action="store_true", help="Check daemon status")
    parser.add_argument("--background", "-b", action="store_true", help="Run in background (detached)")
    args = parser.parse_args()

    project_path = Path(args.project).resolve()
    if not project_path.is_dir():
        print(f"Error: {project_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    if args.status:
        pid = check_existing_daemon(project_path)
        if pid:
            print(f"Daemon running (PID: {pid})")
            log_path = project_path / ".claude" / "tree-daemon.log"
            if log_path.exists():
                print(f"Log: {log_path}")
        else:
            print("No daemon running")
        sys.exit(0)

    if args.stop:
        if stop_daemon(project_path):
            print("Daemon stopped")
        else:
            print("No daemon running")
        sys.exit(0)

    existing_pid = check_existing_daemon(project_path)
    if existing_pid:
        print(f"Daemon already running (PID: {existing_pid})")
        print("Use --stop to stop it first")
        sys.exit(1)

    if args.background:
        if sys.platform == "win32":
            import subprocess
            cmd = [sys.executable, __file__, "--project", str(project_path), "--debounce", str(args.debounce)]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            pid = os.fork()
            if pid > 0:
                print(f"Daemon started in background (PID: {pid})")
                sys.exit(0)
            os.setsid()
            sys.stdout = open(os.devnull, "w")
            sys.stderr = open(os.devnull, "w")

    daemon = TreeDaemon(project_path, args.debounce)
    daemon.run()


if __name__ == "__main__":
    main()
