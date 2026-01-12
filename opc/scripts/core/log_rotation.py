#!/usr/bin/env python3
"""
Log Rotation Utility

Rotates and cleans up log files for Continuous-Claude-v3.

Usage:
    # Manual rotation
    uv run python scripts/core/log_rotation.py rotate

    # Show status
    uv run python scripts/core/log_rotation.py status

    # Run as daemon
    uv run python scripts/core/log_rotation.py daemon
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.core.logging_config import (
    setup_logging,
    get_logger,
    generate_correlation_id,
)


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_LOG_DIR = str(Path.home() / ".claude" / "logs")
DEFAULT_RETENTION_DAYS = 7


# =============================================================================
# Logger Setup
# =============================================================================

logger = get_logger("log_rotation", "log_rotation")


# =============================================================================
# Log Rotation Functions
# =============================================================================

def get_log_files(log_dir: str) -> list[Path]:
    """Get all log files in directory."""
    log_path = Path(log_dir)
    if not log_path.exists():
        return []
    return list(log_path.glob("*.log"))


def get_compressed_files(log_dir: str) -> list[Path]:
    """Get all compressed log files."""
    log_path = Path(log_dir)
    if not log_path.exists():
        return []
    return list(log_path.glob("*.log.gz"))


def rotate_logs(
    log_dir: str,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Rotate and clean up old log files.

    Args:
        log_dir: Directory containing log files
        retention_days: Days to keep uncompressed logs
        dry_run: If True, only show what would be done

    Returns:
        Dict with rotation results
    """
    correlation_id = generate_correlation_id()
    log_path = Path(log_dir)

    logger.info(
        "Log rotation started",
        trace_id=correlation_id,
        operation="rotate_logs",
        log_dir=log_dir,
        retention_days=retention_days,
        dry_run=dry_run,
    )

    if not log_path.exists():
        logger.warning(
            "Log directory not found",
            trace_id=correlation_id,
            log_dir=log_dir,
        )
        return {"rotated": 0, "deleted": 0, "errors": ["log directory not found"]}

    cutoff_timestamp = datetime.now(timezone.utc).timestamp() - (retention_days * 24 * 60 * 60)

    rotated = 0
    deleted = 0
    errors = []

    # Rotate: compress old logs
    for log_file in log_path.glob("*.log"):
        try:
            mtime = log_file.stat().st_mtime
            if mtime < cutoff_timestamp:
                if dry_run:
                    logger.info(
                        f"Would compress: {log_file.name}",
                        trace_id=correlation_id,
                    )
                else:
                    compressed = log_file.with_suffix(log_file.suffix + ".gz")
                    try:
                        with open(log_file, "rb") as f_in:
                            with gzip.open(compressed, "wb") as f_out:
                                f_out.write(f_in.read())
                        log_file.unlink()
                        rotated += 1
                        logger.debug(
                            f"Compressed: {log_file.name}",
                            trace_id=correlation_id,
                        )
                    except Exception as e:
                        errors.append(f"Failed to compress {log_file.name}: {e}")
        except Exception as e:
            errors.append(f"Error processing {log_file.name}: {e}")

    # Delete: remove very old compressed logs (2x retention)
    old_cutoff = cutoff_timestamp - (retention_days * 24 * 60 * 60)
    for gz_file in log_path.glob("*.log.gz"):
        try:
            mtime = gz_file.stat().st_mtime
            if mtime < old_cutoff:
                if dry_run:
                    logger.info(
                        f"Would delete: {gz_file.name}",
                        trace_id=correlation_id,
                    )
                else:
                    gz_file.unlink()
                    deleted += 1
                    logger.debug(
                        f"Deleted: {gz_file.name}",
                        trace_id=correlation_id,
                    )
        except Exception as e:
            errors.append(f"Error deleting {gz_file.name}: {e}")

    # Clean up empty files
    for log_file in log_path.glob("*.log"):
        try:
            if log_file.stat().st_size == 0:
                if dry_run:
                    logger.info(
                        f"Would delete empty: {log_file.name}",
                        trace_id=correlation_id,
                    )
                else:
                    log_file.unlink()
                    deleted += 1
        except Exception:
            pass

    logger.info(
        "Log rotation completed",
        trace_id=correlation_id,
        operation="rotate_logs_complete",
        rotated=rotated,
        deleted=deleted,
        errors=len(errors),
    )

    return {"rotated": rotated, "deleted": deleted, "errors": errors}


def get_log_status(log_dir: str) -> dict[str, Any]:
    """Get status of log files.

    Args:
        log_dir: Directory containing log files

    Returns:
        Dict with log status
    """
    log_path = Path(log_dir)

    if not log_path.exists():
        return {
            "exists": False,
            "log_dir": log_dir,
            "total_size_bytes": 0,
            "file_count": 0,
            "files": [],
        }

    files = []
    total_size = 0

    for log_file in sorted(log_path.glob("*.log*")):
        try:
            size = log_file.stat().st_size
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc)
            files.append({
                "name": log_file.name,
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "modified": mtime.isoformat(),
                "is_compressed": log_file.suffix == ".gz",
            })
            total_size += size
        except Exception as e:
            logger.warning(
                f"Error getting stats for {log_file.name}: {e}",
                trace_id=generate_correlation_id(),
            )

    return {
        "exists": True,
        "log_dir": log_dir,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "file_count": len(files),
        "files": files,
    }


def tail_log(
    log_dir: str,
    script_name: str,
    n_lines: int = 50,
    follow: bool = False,
) -> None:
    """Tail a log file with structured output.

    Args:
        log_dir: Log directory
        script_name: Script name to get logs for
        n_lines: Number of lines to show
        follow: If True, follow the file
    """
    log_file = Path(log_dir) / f"{script_name}.log"
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return

    correlation_id = generate_correlation_id()
    logger.info(
        "Tailing log",
        trace_id=correlation_id,
        operation="tail_log",
        log_file=str(log_file),
        n_lines=n_lines,
        follow=follow,
    )

    if follow:
        try:
            with open(log_file, "r") as f:
                # Show last n_lines first
                lines = f.readlines()
                for line in lines[-n_lines:]:
                    print(line.rstrip())

                # Follow
                while True:
                    line = f.readline()
                    if line:
                        print(line.rstrip())
                    else:
                        time.sleep(0.1)
        except KeyboardInterrupt:
            pass
    else:
        with open(log_file, "r") as f:
            lines = f.readlines()
            for line in lines[-n_lines:]:
                print(line.rstrip())


def search_logs(
    log_dir: str,
    pattern: str,
    script_name: str | None = None,
    level: str | None = None,
    n_results: int = 100,
) -> list[dict[str, Any]]:
    """Search logs for pattern.

    Args:
        log_dir: Log directory
        pattern: Search pattern (regex)
        script_name: Optional script name filter
        level: Optional log level filter
        n_results: Max results to return

    Returns:
        List of matching log entries
    """
    import re

    log_path = Path(log_dir)
    if not log_path.exists():
        return []

    correlation_id = generate_correlation_id()
    logger.info(
        "Searching logs",
        trace_id=correlation_id,
        operation="search_logs",
        pattern=pattern,
        script_name=script_name,
        level=level,
    )

    results = []
    compiled_pattern = re.compile(pattern)

    for log_file in sorted(log_path.glob("*.log")):
        if script_name and script_name not in log_file.name:
            continue

        try:
            with open(log_file, "r") as f:
                for line in f:
                    if compiled_pattern.search(line):
                        try:
                            entry = json.loads(line)
                            if level and entry.get("level") != level:
                                continue
                            results.append(entry)
                            if len(results) >= n_results:
                                return results
                        except json.JSONDecodeError:
                            # Non-JSON line (shouldn't happen with structured logging)
                            if pattern in line:
                                results.append({"raw": line.strip()})
                                if len(results) >= n_results:
                                    return results
        except Exception as e:
            logger.warning(
                f"Error reading {log_file.name}: {e}",
                trace_id=correlation_id,
            )

    return results


# =============================================================================
# Daemon Mode
# =============================================================================

def run_daemon(
    log_dir: str,
    interval_seconds: int = 3600,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> None:
    """Run log rotation as a daemon.

    Args:
        log_dir: Log directory
        interval_seconds: Rotation interval
        retention_days: Days to keep logs
    """
    correlation_id = generate_correlation_id()
    logger.info(
        "Log rotation daemon started",
        trace_id=correlation_id,
        operation="daemon_start",
        log_dir=log_dir,
        interval_seconds=interval_seconds,
        retention_days=retention_days,
    )

    while True:
        try:
            result = rotate_logs(log_dir, retention_days)
            logger.debug(
                "Rotation cycle complete",
                trace_id=generate_correlation_id(),
                **result,
            )
        except Exception as e:
            logger.exception(
                "Error in rotation cycle",
                trace_id=generate_correlation_id(),
                error=str(e),
            )

        time.sleep(interval_seconds)


# =============================================================================
# Main Entry
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Log Rotation Utility")
    parser.add_argument(
        "command",
        choices=["rotate", "status", "tail", "search", "daemon"],
    )
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--script", help="Script name for tail/search")
    parser.add_argument("--lines", type=int, default=50, help="Lines for tail")
    parser.add_argument("--follow", action="store_true", help="Follow log file")
    parser.add_argument("--pattern", help="Pattern for search")
    parser.add_argument("--level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--interval", type=int, default=3600, help="Daemon interval")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    setup_logging(script_name="log_rotation", log_level="INFO")

    if args.command == "rotate":
        result = rotate_logs(
            args.log_dir,
            args.retention_days,
            dry_run=args.dry_run,
        )
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Rotated: {result['rotated']}")
            print(f"Deleted: {result['deleted']}")
            if result['errors']:
                print(f"Errors: {len(result['errors'])}")

    elif args.command == "status":
        status = get_log_status(args.log_dir)
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(f"Log Directory: {status['log_dir']}")
            print(f"Exists: {status['exists']}")
            print(f"Total Size: {status['total_size_mb']} MB")
            print(f"Files: {status['file_count']}")
            for f in status.get("files", [])[:10]:
                print(f"  {f['name']}: {f['size_mb']} MB")

    elif args.command == "tail":
        if not args.script:
            parser.error("--script required for tail")
        tail_log(
            args.log_dir,
            args.script,
            n_lines=args.lines,
            follow=args.follow,
        )

    elif args.command == "search":
        if not args.pattern:
            parser.error("--pattern required for search")
        results = search_logs(
            args.log_dir,
            args.pattern,
            script_name=args.script,
            level=args.level,
        )
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Found {len(results)} results:")
            for r in results[:20]:
                if "raw" in r:
                    print(f"  {r['raw']}")
                else:
                    print(f"  [{r.get('timestamp', '?')}] {r.get('level', '?')}: {r.get('message', '?')}")

    elif args.command == "daemon":
        run_daemon(
            args.log_dir,
            interval_seconds=args.interval,
            retention_days=args.retention_days,
        )


if __name__ == "__main__":
    main()
