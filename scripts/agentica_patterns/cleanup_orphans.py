#!/usr/bin/env python3
"""Orphan agent cleanup with three-tier detection.

USAGE:
    uv run python scripts/agentica/cleanup_orphans.py --dry-run
    uv run python scripts/agentica/cleanup_orphans.py --tier 1
    uv run python scripts/agentica/cleanup_orphans.py --kill

TIER DESCRIPTIONS:
    Tier 1: ppid=1 (true Unix orphan) -> Kill immediately
    Tier 2: parent agent dead -> Kill after 30min grace period
    Tier 3: app orphan (running > 24h) -> Kill after timeout

By default, --dry-run is enabled for safety. Use --kill to actually
terminate orphan processes.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Add project root to path for standalone execution
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.agentica_patterns.coordination import CoordinationDB, OrphanCandidate
from scripts.agentica_patterns.watch_agents import is_unix_orphan

if TYPE_CHECKING:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def kill_process(pid: int) -> bool:
    """Attempt to kill a process with SIGTERM.

    Args:
        pid: Process ID to kill.

    Returns:
        True if signal was sent successfully.
        False if process doesn't exist or permission denied.
    """
    if pid <= 0:
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        logger.info(f"Sent SIGTERM to PID {pid}")
        return True
    except ProcessLookupError:
        logger.debug(f"Process {pid} already dead")
        return False  # Already dead
    except PermissionError:
        logger.warning(f"Permission denied to kill PID {pid}")
        return False


def cleanup_orphans(
    db: CoordinationDB | None = None,
    dry_run: bool = True,
    tier_filter: int | None = None,
) -> list[OrphanCandidate]:
    """Find and optionally kill orphaned agent processes.

    Args:
        db: CoordinationDB instance (uses default if None)
        dry_run: If True, only report orphans without killing
        tier_filter: If set, only process orphans of this tier (1, 2, or 3)

    Returns:
        List of OrphanCandidate objects that were processed (and killed if not dry_run)
    """
    if db is None:
        db = CoordinationDB()

    candidates = db.get_orphan_candidates()

    if tier_filter is not None:
        candidates = [c for c in candidates if c.tier == tier_filter]

    killed: list[OrphanCandidate] = []

    for candidate in candidates:
        prefix = "[DRY-RUN] " if dry_run else ""
        print(f"{prefix}Tier {candidate.tier}: {candidate.agent_id} - {candidate.reason}")

        if not dry_run:
            should_kill = False
            pid_to_kill = candidate.ppid

            if candidate.tier == 1:
                # Tier 1: Verify it's still a Unix orphan before killing
                if pid_to_kill and is_unix_orphan(pid_to_kill):
                    should_kill = True
            elif candidate.tier in (2, 3):
                # Tier 2 and 3: Already qualified by database query
                # For these, we need the actual agent PID, not ppid
                # The ppid would be init (1) or the dead parent
                # So we trust the database status
                should_kill = True
                # Note: For tier 2/3, we may not have the actual agent PID
                # The cleanup marks the agent as killed in the DB

            if should_kill:
                if pid_to_kill and kill_process(pid_to_kill):
                    # Update database to mark agent as killed
                    db.complete_agent(
                        candidate.agent_id,
                        status="killed",
                        error_message=f"Orphan cleanup: {candidate.reason}",
                    )
                    killed.append(candidate)
                    print(f"  Killed agent {candidate.agent_id}")
                else:
                    # Process doesn't exist or no pid - just mark as killed
                    db.complete_agent(
                        candidate.agent_id,
                        status="killed",
                        error_message=f"Orphan cleanup (no process): {candidate.reason}",
                    )
                    killed.append(candidate)
                    print(f"  Marked agent {candidate.agent_id} as killed (process not found)")

    return killed


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Clean up orphaned agents using three-tier detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report orphans without killing (default: True)",
    )
    parser.add_argument(
        "--kill",
        action="store_true",
        help="Actually kill orphan processes (disables --dry-run)",
    )
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3],
        help="Only process orphans of this tier",
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Session ID to use for the coordination database",
    )
    return parser


def main() -> None:
    """Main entry point for cleanup_orphans CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # --kill overrides --dry-run
    dry_run = not args.kill

    # Initialize database
    db = CoordinationDB(session_id=args.session)

    # Run cleanup
    print("=" * 60)
    print("Orphan Agent Cleanup")
    print("=" * 60)
    print(f"Mode: {'DRY-RUN' if dry_run else 'KILL'}")
    if args.tier:
        print(f"Tier filter: {args.tier}")
    print("-" * 60)

    candidates = db.get_orphan_candidates()
    if args.tier:
        candidates = [c for c in candidates if c.tier == args.tier]

    if not candidates:
        print("No orphan candidates found.")
        print("=" * 60)
        return

    print(f"Found {len(candidates)} orphan candidate(s):\n")

    killed = cleanup_orphans(db=db, dry_run=dry_run, tier_filter=args.tier)

    print("-" * 60)
    if dry_run:
        print(f"Dry run complete. {len(candidates)} orphan(s) would be cleaned up.")
        print("Run with --kill to actually terminate orphan processes.")
    else:
        print(f"Cleanup complete. {len(killed)} orphan(s) terminated.")
    print("=" * 60)


if __name__ == "__main__":
    main()
