#!/usr/bin/env python3
"""
USAGE:
    uv run python scripts/validate_resources.py "Swarm(5) |[iso] Jury(3)"
    uv run python scripts/validate_resources.py --available  # show current resources
    uv run python scripts/validate_resources.py --cost Pipeline Swarm  # show cost of patterns

Checks if a composition can run given current system resources.
Works with validate_composition.py for full validation pipeline.
"""

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import psutil


# Model-specific memory defaults (MB) based on empirical measurements
# These are bootstrap defaults used when no historical data exists
MODEL_MEMORY_MB: dict[str, int] = {
    "haiku": 450,   # Lighter model, lower memory footprint
    "sonnet": 650,  # Mid-range model, moderate memory
    "opus": 850,    # Largest model, highest memory requirements
}

# Default model for unknown models
DEFAULT_MODEL = "sonnet"


def estimate_agent_memory(model: str) -> int:
    """
    Estimate memory requirements for an agent using a specific model.

    Args:
        model: Model name (e.g., "haiku", "sonnet", "opus")

    Returns:
        Estimated memory in MB (always an integer)
    """
    return MODEL_MEMORY_MB.get(model, MODEL_MEMORY_MB[DEFAULT_MODEL])


@dataclass
class ResourceRequirements:
    """Resource requirements for a pattern instance."""

    memory_mb: int  # Memory per agent
    cpu_cores: float  # CPU cores (can be fractional)
    concurrent_agents: int  # How many agents run simultaneously
    estimated_duration_s: int  # Rough duration estimate


@dataclass
class SystemResources:
    """Current available system resources."""

    available_memory_mb: int
    available_cpu_cores: float
    max_concurrent_processes: int


@dataclass
class ResourceValidationResult:
    """Result of resource validation."""

    can_launch: bool
    composition: str
    required: ResourceRequirements
    available: SystemResources
    bottleneck: Optional[str]  # "memory", "cpu", "processes", or None
    fallback_suggestion: Optional[str]  # Cheaper alternative if can't launch


# Resource costs per pattern (empirically tuned)
PATTERN_COSTS: dict[str, ResourceRequirements] = {
    "Pipeline": ResourceRequirements(
        memory_mb=100, cpu_cores=0.5, concurrent_agents=1, estimated_duration_s=30
    ),
    "Swarm": ResourceRequirements(
        memory_mb=150, cpu_cores=0.5, concurrent_agents=5, estimated_duration_s=60
    ),  # per-agent, default 5
    "Jury": ResourceRequirements(
        memory_mb=200, cpu_cores=0.5, concurrent_agents=3, estimated_duration_s=45
    ),  # 3 jurors
    "Hierarchical": ResourceRequirements(
        memory_mb=250, cpu_cores=1.0, concurrent_agents=4, estimated_duration_s=120
    ),
    "Blackboard": ResourceRequirements(
        memory_mb=300, cpu_cores=0.5, concurrent_agents=3, estimated_duration_s=90
    ),
    "MapReduce": ResourceRequirements(
        memory_mb=150, cpu_cores=0.5, concurrent_agents=4, estimated_duration_s=60
    ),
    "GeneratorCritic": ResourceRequirements(
        memory_mb=200, cpu_cores=1.0, concurrent_agents=2, estimated_duration_s=90
    ),
    "CircuitBreaker": ResourceRequirements(
        memory_mb=100, cpu_cores=0.25, concurrent_agents=1, estimated_duration_s=30
    ),
    "Aggregator": ResourceRequirements(
        memory_mb=100, cpu_cores=0.25, concurrent_agents=1, estimated_duration_s=15
    ),
    "ChainOfResponsibility": ResourceRequirements(
        memory_mb=100, cpu_cores=0.5, concurrent_agents=1, estimated_duration_s=45
    ),
    "EventDriven": ResourceRequirements(
        memory_mb=150, cpu_cores=0.5, concurrent_agents=2, estimated_duration_s=60
    ),
    "Consensus": ResourceRequirements(
        memory_mb=200, cpu_cores=0.5, concurrent_agents=3, estimated_duration_s=60
    ),
    "Broadcast": ResourceRequirements(
        memory_mb=100, cpu_cores=0.25, concurrent_agents=1, estimated_duration_s=15
    ),
    "Adversarial": ResourceRequirements(
        memory_mb=250, cpu_cores=1.0, concurrent_agents=2, estimated_duration_s=90
    ),
}

# Fallback suggestions: pattern -> cheaper alternative
FALLBACK_MAP: dict[str, str] = {
    "Swarm": "Pipeline",  # Many agents -> single agent
    "Jury": "Pipeline",  # 3 jurors -> 1 agent
    "Hierarchical": "Pipeline",  # Complex hierarchy -> linear
    "Blackboard": "Pipeline",  # Shared state -> sequential
    "MapReduce": "Pipeline",  # Parallel map -> sequential
    "GeneratorCritic": "Pipeline",  # 2 agents -> 1 agent
    "Consensus": "Jury",  # Many voters -> 3 jurors
    "Adversarial": "GeneratorCritic",  # Red/blue team -> single critic
}


def get_system_resources() -> SystemResources:
    """Get current available system resources."""
    mem = psutil.virtual_memory()
    cpu_count = psutil.cpu_count() or 4  # Default to 4 if detection fails

    # Reserve 20% for system
    available_memory = int(mem.available * 0.8 / (1024 * 1024))  # MB
    available_cpu = cpu_count * 0.8  # Reserve 20%

    return SystemResources(
        available_memory_mb=available_memory,
        available_cpu_cores=available_cpu,
        max_concurrent_processes=min(cpu_count * 2, 16),  # Reasonable limit
    )


def parse_pattern_with_count(pattern_str: str) -> tuple[str, Optional[int]]:
    """Parse 'Swarm(5)' -> ('Swarm', 5) or 'Swarm' -> ('Swarm', None)"""
    match = re.match(r"(\w+)(?:\((\d+)\))?", pattern_str)
    if match:
        name = match.group(1)
        count = int(match.group(2)) if match.group(2) else None
        return name, count
    return pattern_str, None


def calculate_requirements(composition: str) -> ResourceRequirements:
    """Calculate total resource requirements for a composition."""
    # Parse composition into patterns
    # Find all pattern names (with optional counts)
    patterns = re.findall(r"(\w+)(?:\((\d+)\))?", composition)

    total_memory = 0
    total_cpu = 0.0
    max_concurrent = 0
    total_duration = 0

    for pattern_name, count in patterns:
        if pattern_name in PATTERN_COSTS:
            cost = PATTERN_COSTS[pattern_name]
            multiplier = int(count) if count else cost.concurrent_agents

            total_memory += cost.memory_mb * multiplier
            total_cpu += cost.cpu_cores * multiplier
            max_concurrent = max(max_concurrent, multiplier)
            total_duration += cost.estimated_duration_s

    # Default if no patterns found
    if total_memory == 0:
        total_memory = 100
        total_cpu = 0.5
        max_concurrent = 1
        total_duration = 30

    return ResourceRequirements(
        memory_mb=total_memory,
        cpu_cores=total_cpu,
        concurrent_agents=max_concurrent,
        estimated_duration_s=total_duration,
    )


def suggest_fallback(
    composition: str, bottleneck: str, available: SystemResources
) -> Optional[str]:
    """Suggest a cheaper alternative composition."""
    # Find patterns in the composition
    patterns = re.findall(r"(\w+)(?:\((\d+)\))?", composition)

    suggestions: list[str] = []

    for pattern_name, count in patterns:
        if pattern_name not in PATTERN_COSTS:
            continue

        cost = PATTERN_COSTS[pattern_name]
        current_count = int(count) if count else cost.concurrent_agents

        if bottleneck == "memory":
            # Try reducing agent count first
            if current_count > 2:
                reduced_count = max(2, current_count // 2)
                suggestions.append(
                    f"Reduce {pattern_name} agents: {pattern_name}({reduced_count})"
                )

            # Suggest pattern replacement
            if pattern_name in FALLBACK_MAP:
                fallback = FALLBACK_MAP[pattern_name]
                suggestions.append(f"Replace {pattern_name} with {fallback}")

        elif bottleneck == "cpu":
            # Reduce parallelism
            if current_count > 1:
                suggestions.append(f"Reduce {pattern_name} to sequential: {pattern_name}(1)")

        elif bottleneck == "processes":
            # Reduce concurrent agents
            if current_count > available.max_concurrent_processes:
                suggestions.append(
                    f"Reduce {pattern_name} agents to {available.max_concurrent_processes}"
                )

    if suggestions:
        return "; ".join(suggestions[:2])  # Return top 2 suggestions
    return None


def validate_resources(composition: str) -> ResourceValidationResult:
    """Check if composition can run with current resources."""
    available = get_system_resources()
    required = calculate_requirements(composition)

    bottleneck: Optional[str] = None

    if required.memory_mb > available.available_memory_mb:
        bottleneck = "memory"
    elif required.cpu_cores > available.available_cpu_cores:
        bottleneck = "cpu"
    elif required.concurrent_agents > available.max_concurrent_processes:
        bottleneck = "processes"

    fallback: Optional[str] = None
    if bottleneck:
        fallback = suggest_fallback(composition, bottleneck, available)

    return ResourceValidationResult(
        can_launch=bottleneck is None,
        composition=composition,
        required=required,
        available=available,
        bottleneck=bottleneck,
        fallback_suggestion=fallback,
    )


def format_memory(mb: int) -> str:
    """Format memory in human-readable form."""
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb} MB"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate resource availability for compositions"
    )
    parser.add_argument("composition", nargs="?", help="Composition to validate")
    parser.add_argument(
        "--available", action="store_true", help="Show available resources"
    )
    parser.add_argument("--cost", nargs="+", help="Show cost of patterns")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--list-patterns", action="store_true", help="List all known patterns"
    )

    args = parser.parse_args()

    if args.list_patterns:
        print("Known patterns and their resource costs:")
        print("-" * 60)
        for name, cost in sorted(PATTERN_COSTS.items()):
            print(
                f"  {name:20} {cost.memory_mb:4} MB, {cost.cpu_cores:.2f} CPU, "
                f"{cost.concurrent_agents} agents, ~{cost.estimated_duration_s}s"
            )
        return

    if args.available:
        res = get_system_resources()
        if args.json:
            print(
                json.dumps(
                    {
                        "available_memory_mb": res.available_memory_mb,
                        "available_cpu_cores": res.available_cpu_cores,
                        "max_concurrent_processes": res.max_concurrent_processes,
                    },
                    indent=2,
                )
            )
        else:
            print("Available Resources:")
            print(f"  Memory: {format_memory(res.available_memory_mb)}")
            print(f"  CPU Cores: {res.available_cpu_cores:.1f}")
            print(f"  Max Concurrent: {res.max_concurrent_processes}")
        return

    if args.cost:
        results = []
        for pattern in args.cost:
            if pattern in PATTERN_COSTS:
                cost = PATTERN_COSTS[pattern]
                if args.json:
                    results.append(
                        {
                            "pattern": pattern,
                            "memory_mb": cost.memory_mb,
                            "cpu_cores": cost.cpu_cores,
                            "concurrent_agents": cost.concurrent_agents,
                            "estimated_duration_s": cost.estimated_duration_s,
                        }
                    )
                else:
                    print(f"{pattern}:")
                    print(f"  Memory: {cost.memory_mb} MB per agent")
                    print(f"  CPU: {cost.cpu_cores} cores")
                    print(f"  Default agents: {cost.concurrent_agents}")
                    print(f"  Est. duration: {cost.estimated_duration_s}s")
            else:
                if not args.json:
                    print(f"{pattern}: Unknown pattern")
        if args.json and results:
            print(json.dumps(results, indent=2))
        return

    if not args.composition:
        parser.print_help()
        return

    result = validate_resources(args.composition)

    if args.json:
        print(
            json.dumps(
                {
                    "can_launch": result.can_launch,
                    "composition": result.composition,
                    "bottleneck": result.bottleneck,
                    "fallback_suggestion": result.fallback_suggestion,
                    "required": {
                        "memory_mb": result.required.memory_mb,
                        "cpu_cores": result.required.cpu_cores,
                        "concurrent_agents": result.required.concurrent_agents,
                        "estimated_duration_s": result.required.estimated_duration_s,
                    },
                    "available": {
                        "memory_mb": result.available.available_memory_mb,
                        "cpu_cores": result.available.available_cpu_cores,
                        "max_concurrent_processes": result.available.max_concurrent_processes,
                    },
                },
                indent=2,
            )
        )
        return

    if result.can_launch:
        print(f"[OK] CAN LAUNCH: {result.composition}")
        print(
            f"  Required: {format_memory(result.required.memory_mb)}, "
            f"{result.required.cpu_cores:.1f} CPU, "
            f"{result.required.concurrent_agents} concurrent agents"
        )
        print(
            f"  Available: {format_memory(result.available.available_memory_mb)}, "
            f"{result.available.available_cpu_cores:.1f} CPU"
        )
        print(f"  Estimated duration: ~{result.required.estimated_duration_s}s")
    else:
        print(f"[FAIL] CANNOT LAUNCH: {result.composition}")
        print(f"  Bottleneck: {result.bottleneck}")
        print(
            f"  Required: {format_memory(result.required.memory_mb)}, "
            f"{result.required.cpu_cores:.1f} CPU, "
            f"{result.required.concurrent_agents} concurrent agents"
        )
        print(
            f"  Available: {format_memory(result.available.available_memory_mb)}, "
            f"{result.available.available_cpu_cores:.1f} CPU"
        )
        if result.fallback_suggestion:
            print(f"\n  Suggested fallback: {result.fallback_suggestion}")


if __name__ == "__main__":
    main()
