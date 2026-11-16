#!/usr/bin/env python3
"""
USAGE:
    uv run python scripts/validate_composition.py "Pipeline ;[handoff] Jury"
    uv run python scripts/validate_composition.py --explain "Swarm |[shared] Blackboard"
    uv run python scripts/validate_composition.py --suggest Pipeline Jury
    uv run python scripts/validate_composition.py --list-patterns
    uv run python scripts/validate_composition.py --json "Pipeline ;[handoff] Jury"
    uv run python scripts/validate_composition.py --check-resources "Swarm(10) |[iso] Jury"

Validates pattern compositions against the formal algebra in docs/pattern-algebra.md.

The composition syntax follows the pattern algebra:
    Pattern1 <operator>[<scope>] Pattern2

Operators:
    ;   Sequential composition (A then B)
    |   Parallel composition (A and B concurrently)
    +   Choice (A or B)

Scopes:
    iso      Isolated - no shared state
    shared   Shared context enabled
    fed      Federated - cross-agent queries (read-only)
    handoff  Sequential state transfer at boundaries
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ScopeType(Enum):
    """Scope types from pattern-algebra.md Section 2.1."""
    ISOLATED = "iso"
    SHARED = "shared"
    FEDERATED = "fed"
    HANDOFF = "handoff"


class Operator(Enum):
    """Composition operators from pattern-algebra.md Section 1."""
    SEQUENTIAL = ";"      # A ; B
    PARALLEL = "|"        # A | B
    CHOICE = "+"          # A + B
    NESTING = "()"        # A(B)


class Termination(Enum):
    """Termination guarantees."""
    GUARANTEED = "guaranteed"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


# Pattern definitions with their scope requirements
# Derived from pattern-algebra.md Section 4 "Pattern Composition Table"
PATTERNS: dict[str, dict] = {
    "Pipeline": {
        "scopes": [ScopeType.HANDOFF],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.SEQUENTIAL,
        "description": "Sequential stages with handoff between each",
    },
    "Swarm": {
        "scopes": [ScopeType.ISOLATED, ScopeType.SHARED],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.PARALLEL,
        "description": "Parallel independent agents with join barrier",
    },
    "Jury": {
        "scopes": [ScopeType.ISOLATED],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.PARALLEL,
        "description": "Independent voting with aggregation (requires isolation)",
    },
    "Hierarchical": {
        "scopes": [ScopeType.SHARED, ScopeType.FEDERATED],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.PARALLEL,
        "description": "Coordinator with nested parallel workers",
    },
    "Blackboard": {
        "scopes": [ScopeType.SHARED],
        "termination": Termination.CONDITIONAL,
        "primary_op": Operator.PARALLEL,
        "description": "Shared state parallel (requires convergence criterion)",
    },
    "MapReduce": {
        "scopes": [ScopeType.ISOLATED, ScopeType.HANDOFF],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.PARALLEL,
        "description": "Parallel map then sequential reduce",
    },
    "GeneratorCritic": {
        "scopes": [ScopeType.HANDOFF],
        "termination": Termination.CONDITIONAL,
        "primary_op": Operator.SEQUENTIAL,
        "description": "Sequential loop with acceptance condition",
    },
    "CircuitBreaker": {
        "scopes": [ScopeType.ISOLATED, ScopeType.HANDOFF],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.CHOICE,
        "description": "Primary with fallback on failure/timeout",
    },
    "ChainOfResponsibility": {
        "scopes": [ScopeType.HANDOFF],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.CHOICE,
        "description": "Sequential fallback cascade",
    },
    "EventDriven": {
        "scopes": [ScopeType.SHARED, ScopeType.FEDERATED],
        "termination": Termination.CONDITIONAL,
        "primary_op": Operator.SEQUENTIAL,
        "description": "Reactive loop (requires external stop signal)",
    },
    "Consensus": {
        "scopes": [ScopeType.SHARED],
        "termination": Termination.CONDITIONAL,
        "primary_op": Operator.PARALLEL,
        "description": "Agreement protocol (requires convergence)",
    },
    "Aggregator": {
        "scopes": [ScopeType.HANDOFF],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.SEQUENTIAL,
        "description": "Collect and combine results",
    },
    "Adversarial": {
        "scopes": [ScopeType.ISOLATED, ScopeType.HANDOFF],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.PARALLEL,
        "description": "Parallel debate with judge verdict",
    },
    "Broadcast": {
        "scopes": [ScopeType.SHARED],
        "termination": Termination.GUARANTEED,
        "primary_op": Operator.PARALLEL,
        "description": "One-to-many with acknowledgments",
    },
}

# Agent counts per pattern (same formula as status.sh: 500MB per agent)
PATTERN_AGENT_COUNTS: dict[str, int] = {
    "Pipeline": 1,
    "Swarm": 5,  # Default, can be overridden with Swarm(N)
    "Jury": 3,
    "Hierarchical": 4,
    "Blackboard": 3,
    "MapReduce": 4,
    "GeneratorCritic": 2,
    "CircuitBreaker": 1,
    "ChainOfResponsibility": 2,
    "EventDriven": 2,
    "Consensus": 3,
    "Aggregator": 1,
    "Adversarial": 3,
    "Broadcast": 2,
}


@dataclass
class ResourceCheckResult:
    """Result of resource validation."""
    can_launch: bool
    agents_needed: int
    agents_available: int
    reason: str = ""
    suggestion: str = ""
    resources: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "can_launch": self.can_launch,
            "agents_needed": self.agents_needed,
            "agents_available": self.agents_available,
            "reason": self.reason,
            "suggestion": self.suggestion,
            "resources": self.resources,
        }


@dataclass
class ValidationResult:
    """Result of composition validation."""
    valid: bool
    composition: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scope_trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "valid": self.valid,
            "composition": self.composition,
            "errors": self.errors,
            "warnings": self.warnings,
            "scope_trace": self.scope_trace,
        }


def extract_base_pattern(pattern_str: str) -> str:
    """Extract base pattern name from a pattern with optional count.

    Examples:
        'Swarm(10)' -> 'Swarm'
        'Pipeline' -> 'Pipeline'
    """
    match = re.match(r"(\w+)(?:\(\d+\))?", pattern_str)
    if match:
        return match.group(1)
    return pattern_str


def get_pattern_info(pattern_name: str) -> Optional[dict]:
    """Get pattern info, case-insensitive lookup."""
    # Extract base name if count is provided
    base_name = extract_base_pattern(pattern_name)

    # Try exact match first
    if base_name in PATTERNS:
        return PATTERNS[base_name]
    # Try case-insensitive match
    pattern_lower = base_name.lower()
    for name, info in PATTERNS.items():
        if name.lower() == pattern_lower:
            return info
    return None


def normalize_pattern_name(pattern_name: str) -> Optional[str]:
    """Normalize pattern name to canonical form."""
    # Extract base name if count is provided
    base_name = extract_base_pattern(pattern_name)

    if base_name in PATTERNS:
        return base_name
    pattern_lower = base_name.lower()
    for name in PATTERNS:
        if name.lower() == pattern_lower:
            return name
    return None


def scope_compatible(
    pattern_a: str, pattern_b: str, scope: ScopeType
) -> tuple[bool, str]:
    """
    Check if two patterns can compose under given scope.

    From pattern-algebra.md Section 6.1 ScopeCompatible.
    """
    info_a = get_pattern_info(pattern_a)
    info_b = get_pattern_info(pattern_b)

    if info_a is None:
        return False, f"Unknown pattern: {pattern_a}"
    if info_b is None:
        return False, f"Unknown pattern: {pattern_b}"

    a_scopes = info_a.get("scopes", [])
    b_scopes = info_b.get("scopes", [])

    if scope not in a_scopes:
        valid_scopes = ", ".join(s.value for s in a_scopes)
        return False, f"{pattern_a} doesn't support [{scope.value}] scope (valid: [{valid_scopes}])"
    if scope not in b_scopes:
        valid_scopes = ", ".join(s.value for s in b_scopes)
        return False, f"{pattern_b} doesn't support [{scope.value}] scope (valid: [{valid_scopes}])"

    return True, "compatible"


def no_deadlock(
    pattern_a: str, pattern_b: str, operator: Operator, scope: ScopeType
) -> tuple[bool, str]:
    """
    Check for potential deadlock conditions.

    From pattern-algebra.md Section 6.2 NoDeadlock.
    """
    # Blackboard with parallel isolated patterns can deadlock
    # (Blackboard requires shared scope for its central board)
    if operator == Operator.PARALLEL:
        if pattern_a == "Blackboard" or pattern_b == "Blackboard":
            if scope == ScopeType.ISOLATED:
                return False, "Blackboard requires [shared] scope, can't run parallel with [iso] scope"

    # Sequential composition requires first pattern to terminate
    # (handled in termination check)

    # Parallel sync requires matching alphabets
    # This is a simplified check - full check would require alphabet analysis
    if operator == Operator.PARALLEL and scope == ScopeType.SHARED:
        # Both patterns must support shared scope (already checked in scope_compatible)
        pass

    return True, "no deadlock risk detected"


def termination_guarantee(
    pattern_a: str, pattern_b: str, operator: Operator
) -> tuple[bool, str, Optional[str]]:
    """
    Check if composition guarantees termination.

    From pattern-algebra.md Section 6.3 TerminationGuarantee.

    Returns: (is_ok, message, optional_warning)
    """
    info_a = get_pattern_info(pattern_a)
    info_b = get_pattern_info(pattern_b)

    if info_a is None or info_b is None:
        return True, "termination unknown (pattern not found)", None

    a_term = info_a.get("termination", Termination.UNKNOWN)
    b_term = info_b.get("termination", Termination.UNKNOWN)

    warning = None

    # Sequential: both must terminate
    if operator == Operator.SEQUENTIAL:
        if a_term == Termination.CONDITIONAL:
            warning = f"Termination conditional: {pattern_a} may not terminate (needs acceptance/convergence condition)"
        elif b_term == Termination.CONDITIONAL:
            warning = f"Termination conditional: {pattern_b} may not terminate (needs acceptance/convergence condition)"

    # Parallel: for sync parallel, both must terminate
    elif operator == Operator.PARALLEL:
        if a_term == Termination.CONDITIONAL or b_term == Termination.CONDITIONAL:
            cond_pattern = pattern_a if a_term == Termination.CONDITIONAL else pattern_b
            warning = f"Termination conditional: parallel composition with {cond_pattern} may not terminate"

    # Choice: at least one branch must be available
    elif operator == Operator.CHOICE:
        # Choice is typically safe for termination
        if a_term == Termination.CONDITIONAL and b_term == Termination.CONDITIONAL:
            warning = "Termination conditional: both choice branches may not terminate"

    return True, "termination checked", warning


def resource_safe(
    pattern_a: str, pattern_b: str, operator: Operator, scope: ScopeType
) -> tuple[bool, str]:
    """
    Check for resource conflicts.

    From pattern-algebra.md Section 6.4 ResourceSafe.
    """
    # Parallel patterns with shared scope need to be careful about writes
    if operator == Operator.PARALLEL and scope == ScopeType.SHARED:
        # Both patterns modifying shared state is a potential conflict
        # This is a simplified heuristic
        write_patterns = {"Blackboard", "EventDriven"}
        if pattern_a in write_patterns and pattern_b in write_patterns:
            return False, f"Resource conflict: both {pattern_a} and {pattern_b} may write to shared state"

    return True, "resource safe"


def can_compose(
    pattern_a: str,
    pattern_b: str,
    scope: ScopeType,
    operator: Operator
) -> ValidationResult:
    """
    Validate if two patterns can compose.

    From pattern-algebra.md Section 6:
    CanCompose(A, B, scope) <=>
        ScopeCompatible(A, B, scope)
        & NoDeadlock(A, B)
        & TerminationGuarantee(A . B)
        & ResourceSafe(A, B)
    """
    errors: list[str] = []
    warnings: list[str] = []
    scope_trace: list[str] = []

    # Normalize pattern names
    norm_a = normalize_pattern_name(pattern_a)
    norm_b = normalize_pattern_name(pattern_b)

    if norm_a is None:
        errors.append(f"Unknown pattern: {pattern_a}")
    if norm_b is None:
        errors.append(f"Unknown pattern: {pattern_b}")

    if errors:
        composition = f"{pattern_a} {operator.value}[{scope.value}] {pattern_b}"
        return ValidationResult(
            valid=False,
            composition=composition,
            errors=errors,
            warnings=warnings,
            scope_trace=scope_trace,
        )

    # Use normalized names
    pattern_a = norm_a  # type: ignore
    pattern_b = norm_b  # type: ignore

    # Check scope compatibility
    compat, msg = scope_compatible(pattern_a, pattern_b, scope)
    scope_trace.append(f"ScopeCompatible({pattern_a}, {pattern_b}, {scope.value}): {compat}")
    if not compat:
        errors.append(msg)

    # Check deadlock
    safe, msg = no_deadlock(pattern_a, pattern_b, operator, scope)
    scope_trace.append(f"NoDeadlock({pattern_a}, {pattern_b}, {operator.value}): {safe}")
    if not safe:
        errors.append(msg)

    # Check termination
    terminates, msg, warning = termination_guarantee(pattern_a, pattern_b, operator)
    scope_trace.append(f"TerminationGuarantee({pattern_a} {operator.value} {pattern_b}): {terminates}")
    if warning:
        warnings.append(warning)

    # Check resource safety
    res_safe, msg = resource_safe(pattern_a, pattern_b, operator, scope)
    scope_trace.append(f"ResourceSafe({pattern_a}, {pattern_b}, {scope.value}): {res_safe}")
    if not res_safe:
        errors.append(msg)

    composition = f"{pattern_a} {operator.value}[{scope.value}] {pattern_b}"
    return ValidationResult(
        valid=len(errors) == 0,
        composition=composition,
        errors=errors,
        warnings=warnings,
        scope_trace=scope_trace,
    )


def parse_composition(expr: str) -> list[tuple[str, Operator, ScopeType, str]]:
    """
    Parse composition expression like 'Pipeline ;[handoff] Jury'.

    Also supports patterns with counts: 'Swarm(10) |[iso] Jury'

    Returns list of (pattern_a, operator, scope, pattern_b) tuples.
    """
    # Pattern: Word(optional count) Operator[scope] Word(optional count)
    # Supports optional whitespace
    # Examples: "Pipeline ;[handoff] Jury", "Swarm(10) |[iso] Jury"
    pattern = r'(\w+(?:\(\d+\))?)\s*([;|+])\s*\[(\w+)\]\s*(\w+(?:\(\d+\))?)'
    matches = re.findall(pattern, expr)

    results: list[tuple[str, Operator, ScopeType, str]] = []
    for match in matches:
        a, op_str, scope_str, b = match

        # Parse operator
        operator_map = {
            ";": Operator.SEQUENTIAL,
            "|": Operator.PARALLEL,
            "+": Operator.CHOICE,
        }
        operator = operator_map.get(op_str)
        if operator is None:
            continue

        # Parse scope
        try:
            scope_type = ScopeType(scope_str)
        except ValueError:
            continue

        results.append((a, operator, scope_type, b))

    return results


# ─────────────────────────────────────────────────────────────────
# RESOURCE VALIDATION
# ─────────────────────────────────────────────────────────────────


def get_resources_from_statusline() -> dict:
    """Read resources from /tmp/claude-resources-*.json written by status.sh."""
    # Find most recent resource file
    pattern = "/tmp/claude-resources-*.json"
    files = glob.glob(pattern)
    if not files:
        # Fallback defaults
        return {
            "freeMemMB": 4096,
            "activeAgents": 0,
            "maxAgents": 8,
            "contextPct": 50,
        }

    # Get most recent
    latest = max(files, key=os.path.getmtime)
    try:
        with open(latest) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Fallback on error
        return {
            "freeMemMB": 4096,
            "activeAgents": 0,
            "maxAgents": 8,
            "contextPct": 50,
        }


def parse_pattern_with_count(pattern_str: str) -> tuple[str, int]:
    """
    Parse pattern name with optional count, e.g., 'Swarm(10)' -> ('Swarm', 10).

    Returns (pattern_name, count) where count is the default if not specified.
    """
    # Match Pattern(N) syntax
    match = re.match(r"(\w+)\((\d+)\)", pattern_str)
    if match:
        name = match.group(1)
        count = int(match.group(2))
        return name, count

    # No count specified, use default
    norm_name = normalize_pattern_name(pattern_str)
    if norm_name:
        return norm_name, PATTERN_AGENT_COUNTS.get(norm_name, 1)
    return pattern_str, 1


def count_agents_in_composition(composition: str) -> int:
    """
    Count total agents needed for a composition expression.

    Handles:
    - Simple patterns: 'Pipeline' -> 1
    - Patterns with counts: 'Swarm(10)' -> 10
    - Compositions: 'Swarm(5) |[iso] Jury' -> 5 + 3 = 8
    """
    total = 0
    seen_patterns: set[str] = set()

    # Find all patterns (with optional count) in the expression
    # Matches: Pattern, Pattern(N), or just words that are pattern names
    pattern_regex = r"(\w+)(?:\((\d+)\))?"

    for match in re.finditer(pattern_regex, composition):
        name = match.group(1)
        explicit_count = match.group(2)

        # Normalize pattern name
        norm_name = normalize_pattern_name(name)
        if norm_name is None:
            continue  # Skip non-pattern words like scope names

        # Avoid double-counting in chained compositions
        pattern_key = f"{norm_name}_{match.start()}"
        if pattern_key in seen_patterns:
            continue
        seen_patterns.add(pattern_key)

        # Use explicit count or default
        if explicit_count:
            total += int(explicit_count)
        else:
            total += PATTERN_AGENT_COUNTS.get(norm_name, 1)

    return total


def suggest_cheaper_composition(composition: str, max_agents: int) -> str:
    """
    Suggest a cheaper alternative if resources are insufficient.

    Strategies:
    1. Reduce Swarm/Jury/MapReduce counts
    2. Substitute Pipeline for Swarm (extreme fallback)
    """
    # Parse all patterns with their counts
    patterns: list[tuple[str, int, int, int]] = []  # (name, count, start, end)

    for match in re.finditer(r"(\w+)(?:\((\d+)\))?", composition):
        name = match.group(1)
        norm_name = normalize_pattern_name(name)
        if norm_name is None:
            continue

        explicit_count = match.group(2)
        if explicit_count:
            count = int(explicit_count)
        else:
            count = PATTERN_AGENT_COUNTS.get(norm_name, 1)

        patterns.append((norm_name, count, match.start(), match.end()))

    if not patterns:
        return composition

    # Calculate current total
    current_total = sum(p[1] for p in patterns)

    if current_total <= max_agents:
        return composition  # Already fits

    # Strategy 1: Proportionally reduce counts
    reduction_factor = max_agents / current_total
    new_composition = composition

    # Process patterns in reverse order to preserve string positions
    for norm_name, orig_count, start, end in reversed(patterns):
        new_count = max(1, int(orig_count * reduction_factor))

        # Only modify if the pattern has explicit count or is a high-agent pattern
        if orig_count > 2:
            # Find the pattern in the original string
            pattern_text = composition[start:end]
            if f"({orig_count})" in pattern_text:
                new_text = f"{norm_name}({new_count})"
            else:
                new_text = f"{norm_name}({new_count})"

            new_composition = (
                new_composition[:start] + new_text + new_composition[end:]
            )

    # Verify the new composition fits
    new_total = count_agents_in_composition(new_composition)
    if new_total > max_agents:
        # Strategy 2: More aggressive reduction
        # Just return a minimal composition
        base_patterns = []
        for norm_name, _, _, _ in patterns:
            if norm_name not in [p[0] for p in base_patterns[:2]]:
                base_patterns.append((norm_name, 1, 0, 0))
            if len(base_patterns) >= 2:
                break

        if len(base_patterns) >= 2:
            return f"{base_patterns[0][0]}(1) ;[handoff] {base_patterns[1][0]}(1)"

    return new_composition


def check_resources(composition: str) -> ResourceCheckResult:
    """
    Check if composition can run with current resources.

    Reads resource state from status.sh output and validates
    against agent requirements.
    """
    resources = get_resources_from_statusline()

    agents_needed = count_agents_in_composition(composition)
    agents_available = resources["maxAgents"] - resources["activeAgents"]

    if agents_needed > agents_available:
        suggestion = suggest_cheaper_composition(composition, agents_available)
        suggestion_agents = count_agents_in_composition(suggestion)

        return ResourceCheckResult(
            can_launch=False,
            agents_needed=agents_needed,
            agents_available=agents_available,
            reason=f"Need {agents_needed} agents, only {agents_available} available",
            suggestion=suggestion if suggestion_agents <= agents_available else "",
            resources=resources,
        )

    return ResourceCheckResult(
        can_launch=True,
        agents_needed=agents_needed,
        agents_available=agents_available,
        reason="Sufficient resources available",
        resources=resources,
    )


def suggest_compositions(pattern_a: str, pattern_b: str) -> list[str]:
    """Suggest valid compositions between two patterns."""
    suggestions: list[str] = []

    # Normalize names first
    norm_a = normalize_pattern_name(pattern_a)
    norm_b = normalize_pattern_name(pattern_b)

    if norm_a is None or norm_b is None:
        return suggestions

    for op in Operator:
        if op == Operator.NESTING:
            continue  # Skip nesting for now (requires different syntax)
        for scope in ScopeType:
            result = can_compose(norm_a, norm_b, scope, op)
            if result.valid:
                suggestions.append(result.composition)

    return suggestions


def list_patterns() -> None:
    """Print all available patterns with their properties."""
    print("Available Patterns:")
    print("-" * 80)
    for name, info in sorted(PATTERNS.items()):
        scopes = ", ".join(s.value for s in info["scopes"])
        term = info["termination"].value
        op = info["primary_op"].value
        desc = info.get("description", "")
        print(f"\n  {name}")
        print(f"    Scopes: [{scopes}]")
        print(f"    Termination: {term}")
        print(f"    Primary Op: {op}")
        print(f"    {desc}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate pattern compositions against the formal algebra",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Validate a composition:
    %(prog)s "Pipeline ;[handoff] Jury"

  Show detailed validation trace:
    %(prog)s --explain "Swarm |[shared] Blackboard"

  Suggest valid compositions:
    %(prog)s --suggest Pipeline Jury

  Check resources (structure + availability):
    %(prog)s --check-resources "Swarm(10) |[iso] Jury"

  List all patterns:
    %(prog)s --list-patterns
        """,
    )
    parser.add_argument(
        "expression",
        nargs="?",
        help="Composition to validate, e.g., 'Pipeline ;[handoff] Jury'",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show detailed validation trace",
    )
    parser.add_argument(
        "--suggest",
        nargs=2,
        metavar=("PATTERN_A", "PATTERN_B"),
        help="Suggest valid compositions between two patterns",
    )
    parser.add_argument(
        "--list-patterns",
        action="store_true",
        help="List all patterns and their scope requirements",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )
    parser.add_argument(
        "--check-resources",
        action="store_true",
        help="Validate structure AND check resource availability",
    )

    args = parser.parse_args()

    # Handle --list-patterns
    if args.list_patterns:
        if args.json:
            output = {
                "patterns": {
                    name: {
                        "scopes": [s.value for s in info["scopes"]],
                        "termination": info["termination"].value,
                        "primary_op": info["primary_op"].value,
                        "description": info.get("description", ""),
                    }
                    for name, info in PATTERNS.items()
                }
            }
            print(json.dumps(output, indent=2))
        else:
            list_patterns()
        return

    # Handle --suggest
    if args.suggest:
        pattern_a, pattern_b = args.suggest
        suggestions = suggest_compositions(pattern_a, pattern_b)

        if args.json:
            output = {
                "pattern_a": pattern_a,
                "pattern_b": pattern_b,
                "valid_compositions": suggestions,
            }
            print(json.dumps(output, indent=2))
        else:
            if suggestions:
                print(f"Valid compositions for {pattern_a} -> {pattern_b}:")
                for s in suggestions:
                    print(f"  + {s}")
            else:
                # Check if patterns exist
                norm_a = normalize_pattern_name(pattern_a)
                norm_b = normalize_pattern_name(pattern_b)
                if norm_a is None:
                    print(f"Unknown pattern: {pattern_a}")
                    print("Use --list-patterns to see available patterns")
                elif norm_b is None:
                    print(f"Unknown pattern: {pattern_b}")
                    print("Use --list-patterns to see available patterns")
                else:
                    print(f"No valid compositions found for {pattern_a} -> {pattern_b}")
        return

    # Require expression for validation
    if not args.expression:
        parser.print_help()
        sys.exit(1)

    # Parse and validate composition
    compositions = parse_composition(args.expression)
    if not compositions:
        if args.json:
            output = {
                "error": f"Could not parse: {args.expression}",
                "expected_format": "Pattern ;[scope] Pattern",
                "example": "Pipeline ;[handoff] Jury",
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"Could not parse: {args.expression}")
            print("Expected format: Pattern <op>[scope] Pattern")
            print("  Operators: ; (sequential), | (parallel), + (choice)")
            print("  Scopes: iso, shared, fed, handoff")
            print("  Example: Pipeline ;[handoff] Jury")
        sys.exit(1)

    all_valid = True
    results_list: list[dict] = []

    for a, op, scope, b in compositions:
        result = can_compose(a, b, scope, op)
        results_list.append(result.to_dict())

        if not result.valid:
            all_valid = False

        if args.json:
            continue  # Collect all results, print at end

        # Print result
        if result.valid:
            print(f"+ VALID: {result.composition}")
        else:
            print(f"x INVALID: {result.composition}")

        # Show trace if --explain or if invalid
        if args.explain or not result.valid:
            print("\nValidation trace:")
            for trace in result.scope_trace:
                print(f"  {trace}")

        if result.errors:
            print("\nErrors:")
            for e in result.errors:
                print(f"  x {e}")

        if result.warnings:
            print("\nWarnings:")
            for w in result.warnings:
                print(f"  ! {w}")

        print()  # Blank line between compositions

    # Resource check if requested
    resource_result: Optional[ResourceCheckResult] = None
    if args.check_resources:
        resource_result = check_resources(args.expression)

        if not args.json:
            # Print structural result header
            if all_valid:
                print("+ STRUCTURAL: Valid composition")
            else:
                print("x STRUCTURAL: Invalid composition")

            # Print resource result
            if resource_result.can_launch:
                print(f"+ RESOURCES: OK ({resource_result.agents_needed} agents needed, "
                      f"{resource_result.agents_available} available)")
            else:
                ram_gb = resource_result.resources.get("freeMemMB", 0) // 1024
                print(f"x RESOURCES: {resource_result.reason} "
                      f"(RAM: {ram_gb}GB free)")

                if resource_result.suggestion:
                    suggestion_agents = count_agents_in_composition(
                        resource_result.suggestion
                    )
                    print(f"\n  Suggested fallback: {resource_result.suggestion}")
                    print(f"  -> Needs {suggestion_agents} agents, "
                          f"fits within available capacity")

            print()

    # JSON output
    if args.json:
        output: dict = {
            "expression": args.expression,
            "all_valid": all_valid,
            "compositions": results_list,
        }
        if resource_result:
            output["resources"] = resource_result.to_dict()
            output["overall_valid"] = all_valid and resource_result.can_launch
        print(json.dumps(output, indent=2))

    # Exit code considers both structural and resource validation
    if args.check_resources and resource_result:
        sys.exit(0 if (all_valid and resource_result.can_launch) else 1)
    else:
        sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
