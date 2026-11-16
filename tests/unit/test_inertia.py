"""Tests for TEL inertia rules."""
import pytest
from scripts.temporal_memory.inertia import (
    apply_inertia,
    detect_contradictions,
    RevisionPriority,
    RevisionEvent,
    resolve_conflict,
    QuestionLifecycle,
)


class TestApplyInertia:
    """Test inertia rule: holds(P, T+1) :- holds(P, T), not -holds(P, T+1)"""

    def test_persists_unchanged_facts(self):
        facts_t = {"db": "sqlite", "api": "rest"}
        updates = {}

        result = apply_inertia(facts_t, updates)

        assert result == {"db": "sqlite", "api": "rest"}

    def test_applies_updates(self):
        facts_t = {"phase": "planning"}
        updates = {"phase": "testing"}

        result = apply_inertia(facts_t, updates)

        assert result["phase"] == "testing"

    def test_adds_new_facts(self):
        facts_t = {"db": "sqlite"}
        updates = {"cache": "redis"}

        result = apply_inertia(facts_t, updates)

        assert result == {"db": "sqlite", "cache": "redis"}

    def test_mixed_persist_and_update(self):
        facts_t = {"db": "sqlite", "phase": "planning", "auth": "jwt"}
        updates = {"phase": "testing"}

        result = apply_inertia(facts_t, updates)

        assert result["db"] == "sqlite"      # Persisted
        assert result["phase"] == "testing"  # Updated
        assert result["auth"] == "jwt"       # Persisted

    def test_empty_facts(self):
        facts_t = {}
        updates = {"new": "value"}

        result = apply_inertia(facts_t, updates)

        assert result == {"new": "value"}

    def test_empty_updates(self):
        facts_t = {"existing": "value"}
        updates = {}

        result = apply_inertia(facts_t, updates)

        assert result == {"existing": "value"}

    def test_does_not_mutate_inputs(self):
        facts_t = {"a": "1"}
        updates = {"b": "2"}

        apply_inertia(facts_t, updates)

        assert facts_t == {"a": "1"}
        assert updates == {"b": "2"}


class TestDetectContradictions:
    """Test contradiction detection."""

    def test_no_contradiction_new_fact(self):
        facts_t = {"a": "1"}

        result = detect_contradictions(facts_t, "b", "2")

        assert result is None

    def test_no_contradiction_same_value(self):
        facts_t = {"phase": "testing"}

        result = detect_contradictions(facts_t, "phase", "testing")

        assert result is None

    def test_detects_contradiction(self):
        facts_t = {"phase": "planning"}

        result = detect_contradictions(facts_t, "phase", "testing")

        assert result is not None
        assert result == ("phase", "planning", "testing")

    def test_unknown_value_not_contradiction(self):
        facts_t = {"db": "UNKNOWN"}

        result = detect_contradictions(facts_t, "db", "postgres")

        assert result is None  # UNKNOWN can be overwritten

    def test_multiple_contradictions_first_only(self):
        facts_t = {"a": "old_a", "b": "old_b"}

        result = detect_contradictions(facts_t, "a", "new_a")

        assert result == ("a", "old_a", "new_a")


class TestRevisionPriority:
    """Test priority-based belief revision."""

    def test_priority_ordering(self):
        assert RevisionPriority.EXPLICIT_NEGATION > RevisionPriority.RECENT_OBSERVATION
        assert RevisionPriority.RECENT_OBSERVATION > RevisionPriority.INVARIANT
        assert RevisionPriority.INVARIANT > RevisionPriority.HISTORICAL
        assert RevisionPriority.HISTORICAL > RevisionPriority.INVARIANT_DECAY

    def test_higher_priority_wins(self):
        winner, event = resolve_conflict(
            key="phase",
            old_value="planning",
            old_priority=RevisionPriority.HISTORICAL,
            old_confidence=0.9,
            new_value="testing",
            new_priority=RevisionPriority.RECENT_OBSERVATION,
            turn=5,
        )
        assert winner == "testing"
        assert event is not None
        assert event.key == "phase"

    def test_lower_priority_loses(self):
        winner, event = resolve_conflict(
            key="db",
            old_value="postgres",
            old_priority=RevisionPriority.INVARIANT,
            old_confidence=1.0,
            new_value="mysql",
            new_priority=RevisionPriority.HISTORICAL,
            turn=3,
        )
        assert winner == "postgres"  # Old wins
        assert event is None  # No revision

    def test_same_priority_recent_wins(self):
        winner, event = resolve_conflict(
            key="cache",
            old_value="redis",
            old_priority=RevisionPriority.RECENT_OBSERVATION,
            old_confidence=0.8,
            new_value="memcached",
            new_priority=RevisionPriority.RECENT_OBSERVATION,
            turn=10,
        )
        assert winner == "memcached"  # Recent wins
        assert event is not None
        assert "Same priority" in event.reason

    def test_explicit_negation_always_wins(self):
        winner, event = resolve_conflict(
            key="feature",
            old_value="enabled",
            old_priority=RevisionPriority.INVARIANT,
            old_confidence=1.0,
            new_value="disabled",
            new_priority=RevisionPriority.EXPLICIT_NEGATION,
            turn=1,
        )
        assert winner == "disabled"
        assert event is not None


class TestRevisionEvent:
    """Test revision event logging."""

    def test_event_fields(self):
        event = RevisionEvent(
            key="phase",
            old_value="planning",
            new_value="testing",
            priority=RevisionPriority.RECENT_OBSERVATION,
            turn=5,
            reason="Priority upgrade",
        )
        assert event.key == "phase"
        assert event.old_value == "planning"
        assert event.new_value == "testing"
        assert event.turn == 5


class TestQuestionLifecycle:
    """Test E(X,Q) question state machine."""

    def test_initial_state_open(self):
        q = QuestionLifecycle(question="What framework?", state="open")
        assert q.state == "open"
        assert q.answer is None
        assert q.confidence == 1.0

    def test_answer_question(self):
        q = QuestionLifecycle(question="What DB?", state="open")
        answered = q.answer_question(value="postgres", turn=3)

        assert answered.state == "answered"
        assert answered.answer == "postgres"
        assert answered.answered_at == 3
        assert answered.confidence == 1.0

    def test_revise_answer(self):
        q = QuestionLifecycle(
            question="What DB?",
            state="answered",
            answer="sqlite",
            answered_at=2,
            confidence=1.0,
        )
        revised = q.revise(new_value="postgres", turn=5)

        assert revised.state == "revised"
        assert revised.answer == "postgres"
        assert revised.answered_at == 5
        assert revised.confidence == 0.8  # Decay: 1.0 - 0.2

    def test_multiple_revisions_decay(self):
        q = QuestionLifecycle(question="Q", state="open")
        q1 = q.answer_question("v1", turn=1)
        q2 = q1.revise("v2", turn=2)
        q3 = q2.revise("v3", turn=3)

        assert q1.confidence == 1.0
        assert q2.confidence == pytest.approx(0.8)  # 1.0 - 0.2
        assert q3.confidence == pytest.approx(0.6)  # 0.8 - 0.2

    def test_confidence_floor(self):
        q = QuestionLifecycle(
            question="Q",
            state="revised",
            answer="v",
            confidence=0.15,
        )
        revised = q.revise("v2", turn=10)

        assert revised.confidence == 0.1  # Floor at 0.1
