"""
Temporal Handoff - Agent-to-agent state transfer.

Implements Phases 5.1-5.3 of the temporal memory system:
- 5.1: TemporalHandoffState dataclass with to_markdown()
- 5.2: parse_temporal_handoff() parser
- 5.3: load_temporal_handoff() file loader

Usage:
    from scripts.temporal_memory.handoff import (
        TemporalHandoffState,
        parse_temporal_handoff,
        load_temporal_handoff,
    )

    # Create from summarizer output
    handoff = TemporalHandoffState.from_summary(
        summary=summary_dict,
        context="Current work context",
        instruction="Next step to take"
    )

    # Generate markdown for file storage
    md = handoff.to_markdown()

    # Parse existing handoff
    parsed = parse_temporal_handoff(md_content)

    # Load from file system
    loaded = load_temporal_handoff("session-name")
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import re


@dataclass
class TemporalHandoffState:
    """Extended handoff state with temporal information.

    This dataclass captures the full state needed for agent-to-agent
    handoff, including temporal context from the memory system.

    Attributes:
        context: Human-readable description of current work context
        next_instruction: Specific instruction for the next agent
        invariants: Facts that have remained constant (key -> value)
        current_state: Snapshot of current facts (key -> value)
        eventualities: Pending goals (unchecked items)
        open_questions: Ranked questions as (name, priority, reason) tuples
        transitions: Recent state transitions as formatted strings
        turn_count: Current turn number in the session

    Example:
        >>> handoff = TemporalHandoffState(
        ...     context="Working on Phase 5",
        ...     next_instruction="Complete the parser tests",
        ...     invariants={"db": "sqlite"},
        ...     current_state={"phase": "testing"},
        ...     eventualities=["goal_tests"],
        ...     open_questions=[("auth", "HIGH", "Blocking")],
        ...     transitions=["T=1: a -> b"],
        ...     turn_count=5
        ... )
        >>> md = handoff.to_markdown()
    """

    context: str = ""
    next_instruction: str = ""
    invariants: dict[str, Any] = field(default_factory=dict)
    current_state: dict[str, Any] = field(default_factory=dict)
    eventualities: list[str] = field(default_factory=list)
    open_questions: list[tuple[str, str, str]] = field(default_factory=list)
    transitions: list[str] = field(default_factory=list)
    turn_count: int = 0

    def to_markdown(self) -> str:
        """Generate markdown handoff document.

        Produces a structured markdown document with all temporal
        information formatted for human readability and machine parsing.

        Returns:
            Markdown string with all handoff sections.

        Example:
            >>> handoff = TemporalHandoffState(turn_count=5)
            >>> md = handoff.to_markdown()
            >>> "# Temporal Handoff (Turn 5)" in md
            True
        """
        lines = [
            f"# Temporal Handoff (Turn {self.turn_count})",
            "",
            "## Open Questions (E(X,Q) - PRIORITY)",
            "| Question | Q-Value | Why Ask First |",
            "|----------|---------|---------------|",
        ]

        for q, qv, why in self.open_questions:
            lines.append(f"| {q} | {qv} | {why} |")

        lines.extend(
            [
                "",
                "## Invariants (Always)",
                "| Property | Value |",
                "|----------|-------|",
            ]
        )

        for k, v in self.invariants.items():
            lines.append(f"| {k} | {v} |")

        lines.extend(
            [
                "",
                "## Current State (Snapshot)",
                "| Property | Value |",
                "|----------|-------|",
            ]
        )

        for k, v in self.current_state.items():
            lines.append(f"| {k} | {v} |")

        lines.extend(
            [
                "",
                "## Pending Goals",
            ]
        )
        for g in self.eventualities:
            lines.append(f"- [ ] {g}")

        lines.extend(
            [
                "",
                "## Recent Transitions",
            ]
        )
        for t in self.transitions:
            lines.append(f"- {t}")

        lines.extend(
            [
                "",
                "## Context",
                self.context,
                "",
                "## Next Instruction",
                self.next_instruction,
            ]
        )

        return "\n".join(lines)

    @classmethod
    def from_summary(
        cls, summary: dict, context: str, instruction: str
    ) -> "TemporalHandoffState":
        """Create from TemporalSummary output.

        Converts the dictionary output from TemporalSummarizer.summarize()
        into a TemporalHandoffState ready for markdown generation.

        Args:
            summary: Dictionary with keys like open_questions_ranked,
                pending_goals, transitions, invariants, current_state, turn_count
            context: Human-readable context description
            instruction: Next instruction for receiving agent

        Returns:
            TemporalHandoffState populated from summary.

        Example:
            >>> summary = {"turn_count": 5, "current_state": {"db": "sqlite"}}
            >>> handoff = TemporalHandoffState.from_summary(
            ...     summary, "Working on tests", "Run pytest"
            ... )
        """
        return cls(
            context=context,
            next_instruction=instruction,
            invariants=_parse_invariants(summary.get("invariants", [])),
            current_state=summary.get("current_state", {}),
            eventualities=summary.get("pending_goals", []),
            open_questions=summary.get("open_questions_ranked", []),
            transitions=summary.get("transitions", []),
            turn_count=summary.get("turn_count", 0),
        )


def _parse_invariants(invariants: Any) -> dict[str, Any]:
    """Parse invariant strings (TEL compact form) into key/value pairs."""
    if isinstance(invariants, dict):
        return dict(invariants)
    parsed: dict[str, Any] = {}
    for inv in invariants or []:
        if not isinstance(inv, str):
            continue
        match = re.match(r"^G\\(([^=]+)=(.+)\\)$", inv.strip())
        if match:
            key, value = match.groups()
            parsed[key.strip()] = value.strip()
    return parsed


def parse_temporal_handoff(content: str) -> dict[str, Any]:
    """Parse a temporal handoff markdown file.

    Extracts structured data from the markdown format produced by
    TemporalHandoffState.to_markdown().

    Args:
        content: Markdown content of handoff file

    Returns:
        Dictionary with keys:
        - open_questions: list of (name, priority, reason) tuples
        - invariants: dict of key -> value
        - pending_goals: list of unchecked goal names
        - current_state: dict of key -> value
        - transitions: list of transition strings
        - context: context string
        - next_instruction: instruction string
        - turn_count: integer turn number

    Example:
        >>> content = "# Temporal Handoff (Turn 5)\\n..."
        >>> parsed = parse_temporal_handoff(content)
        >>> parsed["turn_count"]
        5
    """
    result: dict[str, Any] = {
        "open_questions": [],
        "invariants": {},
        "current_state": {},
        "pending_goals": [],
        "transitions": [],
        "context": "",
        "next_instruction": "",
        "turn_count": 0,
    }

    # Parse turn count from header
    turn_match = re.search(r"# Temporal Handoff \(Turn (\d+)\)", content)
    if turn_match:
        result["turn_count"] = int(turn_match.group(1))

    # Parse Open Questions table
    # Pattern matches: | question | priority | reason |
    oq_pattern = r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
    in_oq_section = False
    for line in content.split("\n"):
        if "## Open Questions" in line:
            in_oq_section = True
            continue
        if in_oq_section and line.startswith("##"):
            in_oq_section = False
        if in_oq_section and "|" in line:
            match = re.match(oq_pattern, line)
            if match:
                q, qv, why = match.groups()
                q = q.strip()
                qv = qv.strip()
                why = why.strip()
                # Skip header and separator rows
                if q not in ("Question", "") and not q.startswith("-"):
                    result["open_questions"].append((q, qv, why))

    # Parse Invariants table
    inv_section = re.search(
        r"## Invariants.*?\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if inv_section:
        for line in inv_section.group(1).split("\n"):
            if "|" in line and "Property" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2 and not parts[0].startswith("-"):
                    result["invariants"][parts[0]] = parts[1]

    # Parse Current State table
    state_section = re.search(
        r"## Current State.*?\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if state_section:
        for line in state_section.group(1).split("\n"):
            if "|" in line and "Property" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2 and not parts[0].startswith("-"):
                    result["current_state"][parts[0]] = parts[1]

    # Parse Pending Goals (unchecked only)
    for match in re.finditer(r"- \[ \] (.+)", content):
        result["pending_goals"].append(match.group(1).strip())

    # Parse Transitions
    trans_section = re.search(
        r"## Recent Transitions\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if trans_section:
        for line in trans_section.group(1).split("\n"):
            if line.strip().startswith("- "):
                result["transitions"].append(line.strip()[2:])

    # Parse Context
    ctx_match = re.search(r"## Context\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if ctx_match:
        result["context"] = ctx_match.group(1).strip()

    # Parse Instruction
    inst_match = re.search(
        r"## Next Instruction\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if inst_match:
        result["next_instruction"] = inst_match.group(1).strip()

    return result


def load_temporal_handoff(
    session_name: str, base_dir: Optional[Path] = None
) -> Optional[TemporalHandoffState]:
    """Load most recent temporal handoff for a session.

    Searches the handoff directory for the session and loads the most
    recent file that contains a temporal handoff marker.

    Args:
        session_name: Name of the session (directory name)
        base_dir: Base directory to search from (defaults to cwd)

    Returns:
        TemporalHandoffState if found, None otherwise.

    Example:
        >>> handoff = load_temporal_handoff("my-session")
        >>> if handoff:
        ...     print(f"Turn {handoff.turn_count}: {handoff.context}")
    """
    if base_dir is None:
        base_dir = Path.cwd()

    handoff_dir = base_dir / "thoughts" / "shared" / "handoffs" / session_name
    if not handoff_dir.exists():
        return None

    # Find most recent temporal handoff (sorted by name descending)
    handoffs = sorted(handoff_dir.glob("*.md"), reverse=True)
    for hf in handoffs:
        content = hf.read_text()
        if "# Temporal Handoff" in content:
            parsed = parse_temporal_handoff(content)
            return TemporalHandoffState(
                context=parsed["context"],
                next_instruction=parsed["next_instruction"],
                invariants=parsed["invariants"],
                current_state=parsed["current_state"],
                eventualities=parsed["pending_goals"],
                open_questions=parsed["open_questions"],
                transitions=parsed["transitions"],
                turn_count=parsed["turn_count"],
            )
    return None
