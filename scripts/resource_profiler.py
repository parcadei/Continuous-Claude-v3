#!/usr/bin/env python3
"""
USAGE:
    # Record agent memory usage
    uv run python scripts/resource_profiler.py record --agent-id agent-123 --model sonnet --mem-mb 720

    # Get P95 memory for a model
    uv run python scripts/resource_profiler.py p95 --model sonnet

    # Get blended estimate for a model
    uv run python scripts/resource_profiler.py estimate --model sonnet

    # Show all recorded data
    uv run python scripts/resource_profiler.py show

Historical resource profiler for adaptive memory estimation.
Records actual agent memory usage and provides P95-based estimates.
"""

import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Handle imports for both module and script execution
try:
    from scripts.validate_resources import MODEL_MEMORY_MB, DEFAULT_MODEL
except ModuleNotFoundError:
    # When run as standalone script
    import sys
    from pathlib import Path as PathImport
    sys.path.insert(0, str(PathImport(__file__).parent.parent))
    from scripts.validate_resources import MODEL_MEMORY_MB, DEFAULT_MODEL

# Default history file location
HISTORY_FILE = Path(".claude/cache/resource_usage.jsonl")

# Minimum samples required for reliable P95 calculation
MIN_SAMPLES_FOR_P95 = 10


class ResourceProfiler:
    """
    Historical resource profiler for adaptive memory estimation.

    Records actual agent memory usage to a JSONL file and provides
    P95-based estimates that blend with bootstrap defaults.
    """

    def __init__(self, history_file: Optional[Path] = None) -> None:
        """
        Initialize the profiler.

        Args:
            history_file: Path to JSONL history file (default: .claude/cache/resource_usage.jsonl)
        """
        self.history_file = history_file or HISTORY_FILE
        self._lock = threading.Lock()

    def record(self, agent_id: str, model: str, mem_mb: int) -> None:
        """
        Record a memory usage sample.

        Args:
            agent_id: Unique identifier for the agent
            model: Model name (e.g., "haiku", "sonnet", "opus")
            mem_mb: Actual memory usage in MB
        """
        entry = {
            "agent_id": agent_id,
            "model": model,
            "mem_mb": mem_mb,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            # Ensure parent directories exist
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            # Append to JSONL file
            with open(self.history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def _load_samples(self, model: str) -> list[int]:
        """
        Load all memory samples for a specific model.

        Args:
            model: Model name to filter by

        Returns:
            List of memory values in MB
        """
        if not self.history_file.exists():
            return []

        samples: list[int] = []
        try:
            with open(self.history_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("model") == model:
                            samples.append(entry["mem_mb"])
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []

        return samples

    def get_p95(self, model: str) -> Optional[int]:
        """
        Get the 95th percentile memory usage for a model.

        Args:
            model: Model name (e.g., "haiku", "sonnet", "opus")

        Returns:
            P95 memory in MB, or None if insufficient samples
        """
        samples = self._load_samples(model)

        if len(samples) < MIN_SAMPLES_FOR_P95:
            return None

        # Sort and calculate P95
        sorted_samples = sorted(samples)
        p95_index = int(len(sorted_samples) * 0.95)
        # Clamp to valid index
        p95_index = min(p95_index, len(sorted_samples) - 1)

        return sorted_samples[p95_index]

    def get_estimate(self, model: str) -> int:
        """
        Get a blended memory estimate combining bootstrap and history.

        Uses bootstrap defaults when insufficient history exists,
        P95 from history when enough samples are available.

        Args:
            model: Model name (e.g., "haiku", "sonnet", "opus")

        Returns:
            Estimated memory in MB
        """
        # Get bootstrap default
        bootstrap = MODEL_MEMORY_MB.get(model, MODEL_MEMORY_MB[DEFAULT_MODEL])

        # Try to get P95 from history
        p95 = self.get_p95(model)

        if p95 is None:
            # Not enough history, use bootstrap
            return bootstrap

        # Use the higher of bootstrap or P95 (conservative estimate)
        return max(bootstrap, p95)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Historical resource profiler for adaptive memory estimation"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # record command
    record_parser = subparsers.add_parser("record", help="Record memory usage")
    record_parser.add_argument("--agent-id", required=True, help="Agent identifier")
    record_parser.add_argument("--model", required=True, help="Model name")
    record_parser.add_argument("--mem-mb", type=int, required=True, help="Memory in MB")

    # p95 command
    p95_parser = subparsers.add_parser("p95", help="Get P95 memory for a model")
    p95_parser.add_argument("--model", required=True, help="Model name")

    # estimate command
    estimate_parser = subparsers.add_parser("estimate", help="Get blended estimate")
    estimate_parser.add_argument("--model", required=True, help="Model name")

    # show command
    subparsers.add_parser("show", help="Show all recorded data")

    args = parser.parse_args()
    profiler = ResourceProfiler()

    if args.command == "record":
        profiler.record(args.agent_id, args.model, args.mem_mb)
        print(f"Recorded: {args.agent_id} ({args.model}): {args.mem_mb} MB")

    elif args.command == "p95":
        p95 = profiler.get_p95(args.model)
        if p95 is not None:
            print(f"P95 for {args.model}: {p95} MB")
        else:
            print(f"Insufficient samples for {args.model} (need {MIN_SAMPLES_FOR_P95}+)")

    elif args.command == "estimate":
        estimate = profiler.get_estimate(args.model)
        print(f"Estimate for {args.model}: {estimate} MB")

    elif args.command == "show":
        if not profiler.history_file.exists():
            print("No history file found")
            return

        print(f"History file: {profiler.history_file}")
        print("-" * 50)
        with open(profiler.history_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    print(
                        f"{entry['timestamp']}: {entry['agent_id']} "
                        f"({entry['model']}): {entry['mem_mb']} MB"
                    )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
