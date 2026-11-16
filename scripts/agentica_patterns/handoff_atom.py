"""
HandoffAtom: Universal symbolic handoff format for multi-agent patterns.

Combines:
- Decision Theory: Choice representation with alternatives and rationale
- Category Theory: Morphisms as state transitions with composition
- Erotetic Logic: Question resolution tracking (E(X,Q))

Token-efficient: ~50-100 tokens vs ~500-1000 for prose.
Prose available on-demand via summarize_handoff().

Based on plan: thoughts/shared/plans/2025-12-31-handoff-atom.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

# ============================================================================
# Outcome Enum
# ============================================================================


class Outcome(Enum):
    """Outcome of an agent's work."""

    SUCCESS = "success"  # Task completed successfully
    PARTIAL_PLUS = "partial_plus"  # Progress made, continuation needed
    PARTIAL_MINUS = "partial_minus"  # Limited progress, may need different approach
    FAILED = "failed"  # Could not complete, rollback may be needed
    BLOCKED = "blocked"  # Waiting on external dependency
    DEFERRED = "deferred"  # Intentionally postponed


# ============================================================================
# Decision Theory Types
# ============================================================================


@dataclass
class Choice:
    """
    A decision point with alternatives and rationale.

    Based on decision theory: choice is selection from alternatives
    with explicit reasoning.
    """

    # Required fields
    selected: str  # What was chosen

    # Optional fields with defaults
    alternatives: list[str] = field(default_factory=list)  # What could have been done
    rationale: str = ""  # Why this was selected
    confidence: float = 1.0  # 0.0-1.0, certainty in choice
    constraints: list[str] = field(default_factory=list)  # What ruled out other options

    def __post_init__(self):
        """Validate confidence range."""
        self.confidence = max(0.0, min(1.0, self.confidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected,
            "alternatives": self.alternatives,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Choice":
        return cls(
            selected=data["selected"],
            alternatives=data.get("alternatives", []),
            rationale=data.get("rationale", ""),
            confidence=data.get("confidence", 1.0),
            constraints=data.get("constraints", []),
        )


# ============================================================================
# Category Theory Types
# ============================================================================


@dataclass
class Morphism:
    """
    A state transition (handoff) as a category-theoretic morphism.

    Captures: source -> target via mechanism, with what was preserved/transformed.
    """

    # Required fields
    source: str  # From state/agent
    target: str  # To state/agent

    # Optional fields with defaults
    via: str = "spawn"  # Mechanism: spawn, queue, broadcast, pipeline, etc.
    timestamp: str = ""  # ISO timestamp
    preserves: list[str] = field(default_factory=list)  # Artifact keys preserved
    transforms: dict[str, str] = field(
        default_factory=dict
    )  # What changed: {"context": "expanded"}

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "via": self.via,
            "timestamp": self.timestamp,
            "preserves": self.preserves,
            "transforms": self.transforms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Morphism":
        return cls(
            source=data["source"],
            target=data["target"],
            via=data.get("via", "spawn"),
            timestamp=data.get("timestamp", ""),
            preserves=data.get("preserves", []),
            transforms=data.get("transforms", {}),
        )


# ============================================================================
# Erotetic Logic Types
# ============================================================================

QValue = Literal["HIGH", "MED", "LOW"]


@dataclass
class Question:
    """
    A question/proposition that may be resolved or unknown.

    Based on erotetic logic: E(X,Q) tracks unresolved propositions.
    """

    # Required fields
    name: str  # Question identifier (snake_case)

    # Optional fields with defaults
    value: Any = None  # Resolved value (None = UNKNOWN)
    q_value: QValue = "MED"  # Architectural impact priority
    why: str = ""  # Explanation for q_value
    resolved_at: str | None = None  # ISO timestamp when resolved

    @property
    def is_resolved(self) -> bool:
        """True if this question has been answered."""
        return self.value is not None and self.value != "UNKNOWN"

    def resolve(self, value: Any) -> None:
        """Mark this question as resolved with a value."""
        self.value = value
        self.resolved_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "q_value": self.q_value,
            "why": self.why,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Question":
        return cls(
            name=data["name"],
            value=data.get("value"),
            q_value=data.get("q_value", "MED"),
            why=data.get("why", ""),
            resolved_at=data.get("resolved_at"),
        )


# ============================================================================
# HandoffAtom - The Universal Symbolic Handoff
# ============================================================================


@dataclass
class HandoffAtom:
    """
    Universal symbolic handoff format for all 11 multi-agent patterns.

    Combines:
    - Identity: agent_id, pattern_id, task_id
    - Morphism: state transition with mechanism
    - Decisions: choices made with rationale
    - Erotetic: questions resolved and remaining
    - Artifacts: produced files/values
    - Outcome: result classification

    Token-efficient: ~50-100 tokens vs ~500-1000 for prose.
    Prose available on-demand via summarize_handoff().
    """

    # == Identity (required) ==
    agent_id: str  # Unique agent identifier
    task_id: str  # Task/session identifier

    # == Morphism (required) ==
    from_state: str  # State before handoff
    to_state: str  # State after handoff

    # == Pattern (optional, defaults) ==
    pattern_id: str = ""  # Pattern: swarm, pipeline, hierarchical, etc.
    via_pattern: str = "direct"  # How transition occurred

    # == Decisions (optional) ==
    decisions: list[Choice] = field(default_factory=list)

    # == Erotetic (optional) ==
    q_resolved: list[Question] = field(default_factory=list)
    q_remaining: list[Question] = field(default_factory=list)

    # == Artifacts (optional) ==
    artifacts: list[str] = field(default_factory=list)  # File paths or value keys

    # == Outcome (optional) ==
    outcome: Outcome = Outcome.PARTIAL_PLUS

    # == Metadata (optional) ==
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    # == Morphism Chain (private, built from transitions) ==
    _morphism_chain: list[Morphism] = field(default_factory=list)

    def __post_init__(self):
        """Validate and set defaults."""
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    # ========== Erotetic Properties ==========

    @property
    def e_is_empty(self) -> bool:
        """True if E(X,Q) = {} (all questions resolved)."""
        return len(self.q_remaining) == 0 and len(self.q_resolved) > 0

    @property
    def q_remaining_count(self) -> int:
        """Number of unresolved questions."""
        return len(self.q_remaining)

    @property
    def q_remaining_high(self) -> list[Question]:
        """HIGH priority unresolved questions."""
        return [q for q in self.q_remaining if q.q_value == "HIGH"]

    # ========== Morphism Methods ==========

    def record_morphism(
        self,
        source: str,
        target: str,
        via: str = "spawn",
        preserves: list[str] | None = None,
        transforms: dict[str, str] | None = None,
    ) -> None:
        """Record a state transition in the morphism chain."""
        self._morphism_chain.append(
            Morphism(
                source=source,
                target=target,
                via=via,
                preserves=preserves or [],
                transforms=transforms or {},
            )
        )

    def compose(self, other: "HandoffAtom") -> "HandoffAtom":
        """
        Category-theoretic composition: (other . self).

        Creates new HandoffAtom representing self followed by other.
        """
        return HandoffAtom(
            # Identity: use other's agent, combined task
            agent_id=other.agent_id,
            task_id=f"{self.task_id}+{other.task_id}",
            # Morphism: from self's start to other's end
            from_state=self.from_state,
            to_state=other.to_state,
            pattern_id=f"{self.pattern_id}->{other.pattern_id}",
            via_pattern=f"{self.via_pattern}->{other.via_pattern}",
            # Decisions: concatenate
            decisions=self.decisions + other.decisions,
            # Erotetic: use other's remaining, combine resolved
            q_resolved=self.q_resolved + other.q_resolved,
            q_remaining=other.q_remaining,
            # Artifacts: union
            artifacts=list(set(self.artifacts + other.artifacts)),
            # Outcome: use other's (most recent)
            outcome=other.outcome,
            # Metadata: merge (other wins on conflict)
            metadata={**self.metadata, **other.metadata},
            # Morphism chain: concatenate
            _morphism_chain=self._morphism_chain + other._morphism_chain,
        )

    # ========== Decision Methods ==========

    def record_decision(self, choice: Choice) -> None:
        """Record a decision/choice made by the agent."""
        self.decisions.append(choice)

    # ========== Serialization ==========

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            # Identity
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            # Morphism
            "from_state": self.from_state,
            "to_state": self.to_state,
            "pattern_id": self.pattern_id,
            "via_pattern": self.via_pattern,
            # Decisions
            "decisions": [d.to_dict() for d in self.decisions],
            # Erotetic
            "q_resolved": [q.to_dict() for q in self.q_resolved],
            "q_remaining": [q.to_dict() for q in self.q_remaining],
            # Artifacts
            "artifacts": self.artifacts,
            # Outcome
            "outcome": self.outcome.value,
            # Metadata
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            # Morphism chain
            "morphism_chain": [m.to_dict() for m in self._morphism_chain],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffAtom":
        """Deserialize from dictionary."""
        atom = cls(
            agent_id=data["agent_id"],
            task_id=data["task_id"],
            from_state=data["from_state"],
            to_state=data["to_state"],
            pattern_id=data.get("pattern_id", ""),
            via_pattern=data.get("via_pattern", "direct"),
            decisions=[Choice.from_dict(d) for d in data.get("decisions", [])],
            q_resolved=[Question.from_dict(q) for q in data.get("q_resolved", [])],
            q_remaining=[Question.from_dict(q) for q in data.get("q_remaining", [])],
            artifacts=data.get("artifacts", []),
            outcome=Outcome(data.get("outcome", "partial_plus")),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", ""),
        )
        atom._morphism_chain = [Morphism.from_dict(m) for m in data.get("morphism_chain", [])]
        return atom

    def to_json(self) -> str:
        """Compact JSON representation."""
        import json

        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "HandoffAtom":
        """Parse from JSON string."""
        import json

        return cls.from_dict(json.loads(json_str))


# ============================================================================
# Renderer - Prose on Demand
# ============================================================================


def _format_choice(choice: Choice) -> str:
    """Format a single choice for display."""
    if choice.rationale:
        return f"{choice.selected} ({choice.rationale})"
    return choice.selected


def _get_outcome_description(outcome: Outcome) -> str:
    """Get human-readable outcome description."""
    descriptions = {
        Outcome.SUCCESS: "completed successfully",
        Outcome.PARTIAL_PLUS: "made progress, continuation needed",
        Outcome.PARTIAL_MINUS: "limited progress, may need different approach",
        Outcome.FAILED: "failed",
        Outcome.BLOCKED: "blocked on external dependency",
        Outcome.DEFERRED: "deferred",
    }
    return descriptions.get(outcome, "unknown outcome")


def summarize_handoff(atom: HandoffAtom) -> str:
    """
    Generate prose summary from symbolic HandoffAtom.

    Produces 3-5 sentences capturing:
    - What happened (morphism: from -> to via pattern)
    - Key decisions made (with rationale)
    - Questions resolved and remaining
    - Outcome and artifacts

    Returns:
        Prose summary suitable for human reading or LLM context.
    """
    lines = []

    # 1. Morphism summary
    if atom.pattern_id:
        lines.append(
            f"Agent {atom.agent_id} completed {atom.pattern_id} pattern, "
            f"transitioning from '{atom.from_state}' to '{atom.to_state}' "
            f"via {atom.via_pattern}."
        )
    else:
        lines.append(
            f"Agent {atom.agent_id} transitioned from '{atom.from_state}' to '{atom.to_state}'."
        )

    # 2. Decisions summary (top 2)
    if atom.decisions:
        decision_strs = [_format_choice(d) for d in atom.decisions[:2]]
        lines.append(f"Key decisions: {'; '.join(decision_strs)}.")

    # 3. Erotetic summary
    if atom.q_resolved:
        resolved_names = [q.name for q in atom.q_resolved[:3]]
        lines.append(f"Resolved: {', '.join(resolved_names)}.")

    if atom.q_remaining:
        remaining_high = [q.name for q in atom.q_remaining_high]
        remaining_text = (
            f"HIGH priority remaining: {', '.join(remaining_high)}."
            if remaining_high
            else f"Remaining questions: {', '.join(q.name for q in atom.q_remaining[:3])}."
        )
        lines.append(remaining_text)

    # 4. Outcome and artifacts
    outcome_str = _get_outcome_description(atom.outcome)
    artifact_suffix = f" Produced {len(atom.artifacts)} artifact(s)." if atom.artifacts else ""
    lines.append(f"Outcome: {outcome_str}.{artifact_suffix}")

    return " ".join(lines)


# ============================================================================
# Factory Functions for Common Patterns
# ============================================================================


def create_swarm_atom(
    agent_id: str,
    task_id: str,
    perspectives_used: list[str],
    aggregated_result: str,
    outcome: Outcome = Outcome.SUCCESS,
) -> HandoffAtom:
    """Create HandoffAtom for Swarm pattern completion."""
    return HandoffAtom(
        agent_id=agent_id,
        task_id=task_id,
        from_state="query",
        to_state="aggregated_result",
        pattern_id="swarm",
        via_pattern="parallel_aggregate",
        decisions=[
            Choice(
                selected=f"Used {len(perspectives_used)} perspectives",
                alternatives=["single_agent", "sequential"],
                rationale="Parallel exploration for comprehensive coverage",
            )
        ],
        artifacts=[aggregated_result] if aggregated_result else [],
        outcome=outcome,
        metadata={"perspectives_count": len(perspectives_used)},
    )


def create_pipeline_atom(
    agent_id: str,
    task_id: str,
    stages_completed: list[str],
    current_stage: str,
    outcome: Outcome = Outcome.PARTIAL_PLUS,
) -> HandoffAtom:
    """Create HandoffAtom for Pipeline stage completion."""
    return HandoffAtom(
        agent_id=agent_id,
        task_id=task_id,
        from_state=stages_completed[-1] if stages_completed else "initial",
        to_state=current_stage,
        pattern_id="pipeline",
        via_pattern="sequential_handoff",
        decisions=[],
        artifacts=[],
        outcome=outcome,
        metadata={
            "stages_completed": stages_completed,
            "current_stage": current_stage,
        },
    )


def create_jury_atom(
    agent_id: str,
    task_id: str,
    votes: list[Any],
    verdict: Any,
    consensus_mode: str,
    outcome: Outcome = Outcome.SUCCESS,
) -> HandoffAtom:
    """Create HandoffAtom for Jury verdict."""
    return HandoffAtom(
        agent_id=agent_id,
        task_id=task_id,
        from_state="question",
        to_state="verdict",
        pattern_id="jury",
        via_pattern=f"consensus_{consensus_mode}",
        decisions=[
            Choice(
                selected=str(verdict),
                alternatives=[str(v) for v in set(votes)],
                rationale=f"Consensus via {consensus_mode}",
            )
        ],
        artifacts=[],
        outcome=outcome,
        metadata={"vote_count": len(votes), "consensus_mode": consensus_mode},
    )
