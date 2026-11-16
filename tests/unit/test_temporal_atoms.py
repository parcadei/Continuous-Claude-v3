"""Tests for temporal atoms and operators."""
import pytest
from scripts.temporal_memory.atoms import (
    TemporalOperator,
    TemporalAtom,
    TemporalFact,
)


class TestTemporalOperator:
    def test_always_operator(self):
        assert TemporalOperator.ALWAYS.value == "G"

    def test_eventually_operator(self):
        assert TemporalOperator.EVENTUALLY.value == "F"

    def test_until_operator(self):
        assert TemporalOperator.UNTIL.value == "U"

    def test_next_operator(self):
        assert TemporalOperator.NEXT.value == "X"

    def test_holds_operator(self):
        assert TemporalOperator.HOLDS.value == "holds"


class TestTemporalAtom:
    def test_create_holds_atom(self):
        atom = TemporalAtom(
            operator=TemporalOperator.HOLDS,
            fact="session_goal",
            value="implement memory",
            turn=5,
        )
        assert atom.operator == TemporalOperator.HOLDS
        assert atom.fact == "session_goal"
        assert atom.value == "implement memory"
        assert atom.turn == 5

    def test_to_compact_holds(self):
        atom = TemporalAtom(
            operator=TemporalOperator.HOLDS,
            fact="phase",
            value="testing",
            turn=3,
        )
        assert atom.to_compact() == "holds(phase=testing, T=3)"

    def test_to_compact_always(self):
        atom = TemporalAtom(
            operator=TemporalOperator.ALWAYS,
            fact="db_type",
            value="sqlite",
            turn=0,
        )
        assert atom.to_compact() == "G(db_type=sqlite)"

    def test_to_compact_eventually(self):
        atom = TemporalAtom(
            operator=TemporalOperator.EVENTUALLY,
            fact="tests_pass",
            value=None,
            turn=0,
        )
        assert atom.to_compact() == "F(tests_pass)"

    def test_to_compact_until(self):
        atom = TemporalAtom(
            operator=TemporalOperator.UNTIL,
            fact="waiting",
            value="done",
            turn=0,
        )
        assert atom.to_compact() == "U(waiting)"

    def test_to_compact_next(self):
        atom = TemporalAtom(
            operator=TemporalOperator.NEXT,
            fact="phase",
            value="testing",
            turn=5,
        )
        assert atom.to_compact() == "X(phase)"

    def test_equality(self):
        atom1 = TemporalAtom(TemporalOperator.HOLDS, "fact", "value", 1)
        atom2 = TemporalAtom(TemporalOperator.HOLDS, "fact", "value", 1)
        assert atom1 == atom2

    def test_inequality_different_operator(self):
        atom1 = TemporalAtom(TemporalOperator.HOLDS, "fact", "value", 1)
        atom2 = TemporalAtom(TemporalOperator.ALWAYS, "fact", "value", 1)
        assert atom1 != atom2

    def test_inequality_different_fact(self):
        atom1 = TemporalAtom(TemporalOperator.HOLDS, "fact1", "value", 1)
        atom2 = TemporalAtom(TemporalOperator.HOLDS, "fact2", "value", 1)
        assert atom1 != atom2

    def test_hashing(self):
        atom1 = TemporalAtom(TemporalOperator.HOLDS, "fact", "value", 1)
        atom2 = TemporalAtom(TemporalOperator.HOLDS, "fact", "value", 1)
        assert hash(atom1) == hash(atom2)
        assert {atom1, atom2} == {atom1}  # Set deduplication

    def test_hashable_in_dict(self):
        atom = TemporalAtom(TemporalOperator.HOLDS, "fact", "value", 1)
        d = {atom: "test"}
        assert d[atom] == "test"

    def test_metadata_default(self):
        atom = TemporalAtom(TemporalOperator.HOLDS, "fact", "val", 0)
        assert atom.metadata == {}

    def test_metadata_custom(self):
        atom = TemporalAtom(
            TemporalOperator.HOLDS,
            "fact",
            "val",
            0,
            metadata={"confidence": 0.9},
        )
        assert atom.metadata["confidence"] == 0.9

    def test_metadata_does_not_affect_equality(self):
        atom1 = TemporalAtom(
            TemporalOperator.HOLDS, "fact", "value", 1, metadata={"a": 1}
        )
        atom2 = TemporalAtom(
            TemporalOperator.HOLDS, "fact", "value", 1, metadata={"b": 2}
        )
        assert atom1 == atom2

    def test_metadata_does_not_affect_hash(self):
        atom1 = TemporalAtom(
            TemporalOperator.HOLDS, "fact", "value", 1, metadata={"a": 1}
        )
        atom2 = TemporalAtom(
            TemporalOperator.HOLDS, "fact", "value", 1, metadata={"b": 2}
        )
        assert hash(atom1) == hash(atom2)

    def test_immutability(self):
        atom = TemporalAtom(TemporalOperator.HOLDS, "fact", "value", 1)
        with pytest.raises(AttributeError):
            atom.fact = "new_fact"


class TestTemporalFact:
    def test_create_fact(self):
        fact = TemporalFact(
            key="db_type",
            current_value="sqlite",
            first_seen=1,
            last_changed=1,
        )
        assert fact.key == "db_type"
        assert fact.current_value == "sqlite"
        assert fact.change_count == 0
        assert fact.confidence == 1.0

    def test_fact_with_changes(self):
        fact = TemporalFact(
            key="goal",
            current_value="done",
            first_seen=1,
            last_changed=10,
            change_count=3,
            confidence=0.7,
        )
        assert fact.change_count == 3
        assert fact.confidence == 0.7

    def test_fact_first_seen_last_changed(self):
        fact = TemporalFact(
            key="phase",
            current_value="testing",
            first_seen=2,
            last_changed=8,
        )
        assert fact.first_seen == 2
        assert fact.last_changed == 8

    def test_fact_is_mutable(self):
        fact = TemporalFact(
            key="counter",
            current_value=0,
            first_seen=1,
            last_changed=1,
        )
        fact.current_value = 1
        fact.last_changed = 2
        fact.change_count = 1
        assert fact.current_value == 1
        assert fact.last_changed == 2
        assert fact.change_count == 1


class TestTemporalAtomParser:
    """Test from_compact() classmethod."""

    def test_parse_holds(self):
        compact = "holds(phase=testing, T=3)"
        atom = TemporalAtom.from_compact(compact)
        assert atom.operator == TemporalOperator.HOLDS
        assert atom.fact == "phase"
        assert atom.value == "testing"
        assert atom.turn == 3

    def test_parse_always(self):
        compact = "G(db_type=sqlite)"
        atom = TemporalAtom.from_compact(compact)
        assert atom.operator == TemporalOperator.ALWAYS
        assert atom.fact == "db_type"
        assert atom.value == "sqlite"
        assert atom.turn == 0

    def test_parse_eventually(self):
        compact = "F(tests_pass)"
        atom = TemporalAtom.from_compact(compact)
        assert atom.operator == TemporalOperator.EVENTUALLY
        assert atom.fact == "tests_pass"
        assert atom.value is None
        assert atom.turn == 0

    def test_parse_until(self):
        compact = "U(waiting_for_response)"
        atom = TemporalAtom.from_compact(compact)
        assert atom.operator == TemporalOperator.UNTIL
        assert atom.fact == "waiting_for_response"

    def test_parse_next(self):
        compact = "X(check_tests)"
        atom = TemporalAtom.from_compact(compact)
        assert atom.operator == TemporalOperator.NEXT
        assert atom.fact == "check_tests"

    def test_round_trip_holds(self):
        original = TemporalAtom(TemporalOperator.HOLDS, "phase", "testing", 3)
        parsed = TemporalAtom.from_compact(original.to_compact())
        assert parsed == original

    def test_round_trip_always(self):
        original = TemporalAtom(TemporalOperator.ALWAYS, "db_type", "sqlite", 0)
        parsed = TemporalAtom.from_compact(original.to_compact())
        assert parsed == original

    def test_round_trip_eventually(self):
        original = TemporalAtom(TemporalOperator.EVENTUALLY, "tests_pass", None, 0)
        parsed = TemporalAtom.from_compact(original.to_compact())
        assert parsed == original

    def test_parse_malformed_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            TemporalAtom.from_compact("not_valid_format")

    def test_parse_empty_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            TemporalAtom.from_compact("")

    def test_parse_with_spaces_in_value(self):
        compact = "holds(goal=implement memory system, T=5)"
        atom = TemporalAtom.from_compact(compact)
        assert atom.value == "implement memory system"

    def test_parse_with_special_chars(self):
        compact = "G(path=/Users/test/file.py)"
        atom = TemporalAtom.from_compact(compact)
        assert atom.value == "/Users/test/file.py"
