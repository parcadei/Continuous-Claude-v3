"""
TEL Inertia Rules - Non-monotonic persistence.

Inertia rule:
    holds(P, T+1) :- holds(P, T), not -holds(P, T+1)

Translation: A fact persists from turn T to T+1 unless explicitly negated.
"""
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Literal, Optional

QuestionState = Literal["open", "answered", "revised"]


class RevisionPriority(IntEnum):
    """Priority levels for belief revision.

    Higher values take precedence in conflict resolution.
    The hierarchy is:
      INVARIANT_DECAY < HISTORICAL < INVARIANT < RECENT_OBSERVATION < EXPLICIT_NEGATION
    """

    INVARIANT_DECAY = 1
    HISTORICAL = 2
    INVARIANT = 3
    RECENT_OBSERVATION = 4
    EXPLICIT_NEGATION = 5


@dataclass
class RevisionEvent:
    """Record of a belief revision for debugging and traceability."""

    key: str
    old_value: Any
    new_value: Any
    priority: RevisionPriority
    turn: int
    reason: str


def resolve_conflict(
    key: str,
    old_value: Any,
    old_priority: RevisionPriority,
    old_confidence: float,
    new_value: Any,
    new_priority: RevisionPriority,
    turn: int,
) -> tuple[Any, Optional[RevisionEvent]]:
    """
    Resolve conflicting beliefs using priority hierarchy.

    Priority: EXPLICIT_NEGATION > RECENT_OBSERVATION > INVARIANT > HISTORICAL
    Same priority: recent observation wins.

    Args:
        key: The fact key being contested
        old_value: Current value of the fact
        old_priority: Priority of the current value
        old_confidence: Confidence in the current value
        new_value: Proposed new value
        new_priority: Priority of the proposed value
        turn: Current turn number

    Returns:
        (winning_value, RevisionEvent if change occurred else None)
    """
    if new_priority > old_priority:
        return (
            new_value,
            RevisionEvent(
                key=key,
                old_value=old_value,
                new_value=new_value,
                priority=new_priority,
                turn=turn,
                reason=f"Priority: {new_priority.name} > {old_priority.name}",
            ),
        )
    elif new_priority == old_priority:
        return (
            new_value,
            RevisionEvent(
                key=key,
                old_value=old_value,
                new_value=new_value,
                priority=new_priority,
                turn=turn,
                reason="Same priority - recent wins",
            ),
        )
    else:
        return (old_value, None)


@dataclass
class QuestionLifecycle:
    """
    Question state machine for E(X,Q) tracking.

    States: open -> answered -> revised

    Each revision reduces confidence by 0.2, with a floor at 0.1.
    """

    question: str
    state: QuestionState
    answer: Optional[Any] = None
    answered_at: Optional[int] = None
    confidence: float = 1.0

    def answer_question(self, value: Any, turn: int) -> "QuestionLifecycle":
        """Transition: open -> answered."""
        return QuestionLifecycle(
            question=self.question,
            state="answered",
            answer=value,
            answered_at=turn,
            confidence=1.0,
        )

    def revise(self, new_value: Any, turn: int) -> "QuestionLifecycle":
        """Transition: answered -> revised with confidence decay."""
        new_confidence = max(self.confidence - 0.2, 0.1)
        return QuestionLifecycle(
            question=self.question,
            state="revised",
            answer=new_value,
            answered_at=turn,
            confidence=new_confidence,
        )


def apply_inertia(
    facts_at_t: dict[str, Any],
    updates_at_t_plus_1: dict[str, Any]
) -> dict[str, Any]:
    """
    Apply inertia rule to compute facts at T+1.

    The inertia rule states that facts persist from turn T to T+1
    unless explicitly updated (negated or changed).

    Args:
        facts_at_t: Facts known at turn T
        updates_at_t_plus_1: Explicit updates at turn T+1

    Returns:
        Complete fact set at T+1 (persisted + updates)
    """
    # Start with persisted facts (copy to avoid mutation)
    result = dict(facts_at_t)
    # Apply updates (explicit negation or new values)
    result.update(updates_at_t_plus_1)
    return result


def detect_contradictions(
    facts_at_t: dict[str, Any],
    new_fact: str,
    new_value: Any
) -> Optional[tuple[str, Any, Any]]:
    """
    Detect if a new fact contradicts an existing one.

    A contradiction occurs when:
    - The fact already exists with a different value
    - The existing value is not UNKNOWN (UNKNOWN can be overwritten)

    Args:
        facts_at_t: Current facts
        new_fact: Key of the new fact
        new_value: Value of the new fact

    Returns:
        None if no contradiction, else (key, old_value, new_value) tuple
    """
    if new_fact in facts_at_t:
        old_value = facts_at_t[new_fact]
        # UNKNOWN is a placeholder, not a real value
        if old_value != new_value and old_value != "UNKNOWN":
            return (new_fact, old_value, new_value)
    return None
