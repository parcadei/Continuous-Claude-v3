"""
Ledger Workflow State - Erotetic format for workflow tracking.

This module provides:
1. Workflow State template generation (erotetic format)
2. New codebase detection function
3. Workflow state parsing utilities

USAGE:
    from scripts.ledger_workflow import (
        is_known_codebase,
        get_workflow_state_template,
        parse_workflow_state,
        check_workflow_readiness,
    )

    # Check if project has existing handoffs
    if not is_known_codebase("/path/to/project"):
        print("New codebase - run onboarding")

    # Generate workflow state template
    template = get_workflow_state_template(
        pattern="hierarchical",
        phase=2,
        total_phases=5,
        goal="implement auth system",
        unknowns=["rate_limit: UNKNOWN", "error_format: UNKNOWN"],
    )

    # Parse existing workflow state from markdown
    state = parse_workflow_state(ledger_content)
    if state:
        readiness = check_workflow_readiness(state)
        if readiness["isEmpty"]:
            print("All resolved - ready to continue")
        else:
            print(f"Unknowns remaining: {readiness['unknowns']}")

Theory:
    Workflow state follows the erotetic pattern from z3_erotetic.py.
    E(X,Q) = {} means all propositions are resolved and implementation
    can proceed. Unknowns must be resolved before continuing.

    The format tracks:
    - pattern: which orchestration pattern is being used
    - phase: current phase in multi-phase work
    - retries: for circuit-breaker style error recovery
    - Resolved: known facts (goal, resource_allocation, etc.)
    - Unknowns: things that must be determined before proceeding
    - Last Failure: context for retry decisions
"""

import os
import re
from typing import Any


def is_known_codebase(project_dir: str) -> bool:
    """
    Check if this is a known codebase by looking for existing handoffs.

    A "known" codebase has at least one .md file in the handoffs directory,
    indicating previous work sessions have been recorded.

    Args:
        project_dir: Path to the project root directory

    Returns:
        True if handoffs exist (known codebase), False otherwise (new codebase)
    """
    handoffs_dir = os.path.join(project_dir, "thoughts", "shared", "handoffs")

    if not os.path.exists(handoffs_dir):
        return False

    # Walk the handoffs directory looking for any .md files
    for root, _dirs, files in os.walk(handoffs_dir):
        if any(f.endswith(".md") for f in files):
            return True

    return False


def get_workflow_state_template(
    pattern: str = "[workflow pattern name]",
    phase: int | str = "[current phase number]",
    total_phases: int | str = "[total phases]",
    retries: int = 0,
    max_retries: int = 3,
    goal: str = "[user's stated goal]",
    resource_allocation: str = "[conservative|balanced|aggressive]",
    unknowns: list[str] | None = None,
    last_failure: str = "[error context if any]",
) -> str:
    """
    Generate a Workflow State section template for the ledger.

    The template follows erotetic format with Resolved/Unknowns sections.

    Args:
        pattern: The workflow pattern being used (e.g., "hierarchical", "swarm")
        phase: Current phase number
        total_phases: Total number of phases
        retries: Current retry count
        max_retries: Maximum retries allowed
        goal: The user's stated goal
        resource_allocation: Resource allocation strategy
        unknowns: List of unknown items (erotetic)
        last_failure: Context from last failure (for retries)

    Returns:
        Formatted markdown template string
    """
    # Format unknowns section
    if unknowns:
        unknowns_lines = "\n".join(f"- {u}" for u in unknowns)
    else:
        unknowns_lines = "- [any unresolved questions marked UNKNOWN]"

    template = f"""### Workflow State
pattern: {pattern}
phase: {phase}
total_phases: {total_phases}
retries: {retries}
max_retries: {max_retries}

#### Resolved
- goal: "{goal}"
- resource_allocation: {resource_allocation}

#### Unknowns
{unknowns_lines}

#### Last Failure
{last_failure}
"""
    return template


def parse_workflow_state(markdown: str) -> dict[str, Any] | None:
    """
    Parse workflow state from markdown content.

    Extracts pattern, phase info, retries, resolved items, unknowns,
    and last failure context from a ### Workflow State section.

    Args:
        markdown: Markdown content containing workflow state

    Returns:
        Dict with parsed state, or None if no workflow state section found
    """
    # Check for workflow state section
    if "### Workflow State" not in markdown:
        return None

    # Extract the workflow state section (everything after "### Workflow State")
    state_match = re.search(
        r"### Workflow State\s*\n(.*)",
        markdown,
        re.DOTALL,
    )
    if not state_match:
        return None

    section = state_match.group(1)

    result: dict[str, Any] = {
        "pattern": None,
        "phase": None,
        "total_phases": None,
        "retries": None,
        "max_retries": None,
        "resolved": {},
        "unknowns": [],
        "last_failure": "",
    }

    # Parse simple key: value fields
    pattern_match = re.search(r"^pattern:\s*(.+)$", section, re.MULTILINE)
    if pattern_match:
        result["pattern"] = pattern_match.group(1).strip()

    phase_match = re.search(r"^phase:\s*(\d+)$", section, re.MULTILINE)
    if phase_match:
        result["phase"] = int(phase_match.group(1))

    total_phases_match = re.search(r"^total_phases:\s*(\d+)$", section, re.MULTILINE)
    if total_phases_match:
        result["total_phases"] = int(total_phases_match.group(1))

    retries_match = re.search(r"^retries:\s*(\d+)$", section, re.MULTILINE)
    if retries_match:
        result["retries"] = int(retries_match.group(1))

    max_retries_match = re.search(r"^max_retries:\s*(\d+)$", section, re.MULTILINE)
    if max_retries_match:
        result["max_retries"] = int(max_retries_match.group(1))

    # Parse Resolved section - look for #### Resolved and capture until next #### or end
    resolved_match = re.search(
        r"#### Resolved\s*\n(.*?)(?=####|\Z)",
        section,
        re.DOTALL,
    )
    if resolved_match:
        resolved_content = resolved_match.group(1)
        # Extract goal
        goal_match = re.search(r'-\s*goal:\s*"([^"]+)"', resolved_content)
        if goal_match:
            result["resolved"]["goal"] = goal_match.group(1)
        # Extract resource_allocation
        ra_match = re.search(r"-\s*resource_allocation:\s*(.+)$", resolved_content, re.MULTILINE)
        if ra_match:
            result["resolved"]["resource_allocation"] = ra_match.group(1).strip()

    # Parse Unknowns section
    unknowns_match = re.search(
        r"#### Unknowns\s*\n(.*?)(?=####|\Z)",
        section,
        re.DOTALL,
    )
    if unknowns_match:
        unknowns_content = unknowns_match.group(1).strip()
        # Check for "(none)" or empty
        if unknowns_content.lower() in ["(none)", ""]:
            result["unknowns"] = []
        else:
            # Extract unknown items (handle both "- key: UNKNOWN" and "- key: value" formats)
            unknown_items = re.findall(r"-\s*(\w+):\s*UNKNOWN", unknowns_content)
            result["unknowns"] = unknown_items

    # Parse Last Failure section
    failure_match = re.search(
        r"#### Last Failure\s*\n(.*?)(?=####|\n###|\n##|\Z)",
        section,
        re.DOTALL,
    )
    if failure_match:
        result["last_failure"] = failure_match.group(1).strip()

    return result


def check_workflow_readiness(state: dict[str, Any]) -> dict[str, Any]:
    """
    Check if workflow is ready to proceed (all unknowns resolved).

    This follows the erotetic pattern: E(X,Q) = {} means ready.

    Args:
        state: Parsed workflow state dict

    Returns:
        {
            "isEmpty": bool,      # True if no unknowns
            "unknowns": list,     # List of unknown names
            "count": int          # Number of unknowns
        }
    """
    unknowns = state.get("unknowns", [])
    count = len(unknowns)

    return {
        "isEmpty": count == 0,
        "unknowns": unknowns,
        "count": count,
    }
