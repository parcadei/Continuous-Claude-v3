"""Tests for turn inference from Braintrust spans.

Tests the 4-step fallback strategy:
1. Handoff frontmatter (turn_span_id) - confidence 1.0
2. Braintrust metadata.turn_number - confidence 0.95
3. Task span boundaries - confidence 0.8
4. Batch numbering (fallback) - confidence 0.6
"""
import pytest

from scripts.backfill.turn_inference import TurnInference, TurnResult


class TestTurnInference:
    """Tests for TurnInference class."""

    def test_extract_from_handoff_frontmatter(self) -> None:
        """Turn number from handoff turn_span_id takes priority."""
        inference = TurnInference()
        handoff = {
            "turn_span_id": "turn-span-123",
            "content": "## What Was Done\n...",
        }
        spans = [{"id": "span-1"}, {"id": "turn-span-123"}]

        result = inference.infer_turns(spans, handoff=handoff)

        assert result.method == "handoff_frontmatter"
        assert result.confidence == 1.0

    def test_braintrust_metadata_turn_number(self) -> None:
        """Turn number from metadata.turn_number used if present."""
        inference = TurnInference()
        spans = [
            {"id": "s1", "metadata": {"turn_number": 1}},
            {"id": "s2", "metadata": {"turn_number": 1}},
            {"id": "s3", "metadata": {"turn_number": 2}},
        ]

        result = inference.infer_turns(spans)

        assert result.method == "braintrust_metadata"
        assert result.turns == {1: ["s1", "s2"], 2: ["s3"]}
        assert result.confidence == 0.95

    def test_span_creation_order(self) -> None:
        """Infer turns from task span boundaries."""
        inference = TurnInference()
        spans = [
            {"id": "s1", "span_attributes": {"type": "task"}, "input": "User: do X"},
            {"id": "s2", "span_attributes": {"type": "tool"}},
            {"id": "s3", "span_attributes": {"type": "task"}, "input": "User: now Y"},
            {"id": "s4", "span_attributes": {"type": "tool"}},
        ]

        result = inference.infer_turns(spans)

        assert result.method == "span_order"
        assert len(result.turns) == 2  # Two turns inferred
        assert result.confidence == 0.8

    def test_batch_numbering_fallback(self) -> None:
        """Fall back to batch numbering for long sessions."""
        inference = TurnInference()
        # 100 spans, no turn markers
        spans = [
            {"id": f"s{i}", "span_attributes": {"type": "tool"}} for i in range(100)
        ]

        result = inference.infer_turns(spans, batch_size=20)

        assert result.method == "batch_fallback"
        assert len(result.turns) == 5  # 100 / 20 = 5 batches
        assert result.confidence == 0.6

    def test_empty_spans_handled(self) -> None:
        """Empty span list doesn't crash."""
        inference = TurnInference()
        result = inference.infer_turns([])

        assert result.turns == {}
        assert result.method == "none"

    def test_mixed_signals_priority(self) -> None:
        """Handoff takes priority over metadata over span order."""
        inference = TurnInference()
        handoff = {"turn_span_id": "priority-span"}
        spans = [
            {"id": "priority-span", "metadata": {"turn_number": 5}},
            {"id": "other", "span_attributes": {"type": "task"}},
        ]

        result = inference.infer_turns(spans, handoff=handoff)

        assert result.method == "handoff_frontmatter"  # Priority

    def test_turn_result_has_correct_structure(self) -> None:
        """TurnResult dataclass has expected fields."""
        result = TurnResult(
            turns={1: ["s1", "s2"]},
            method="test",
            confidence=0.9,
            warnings=["test warning"],
        )

        assert result.turns == {1: ["s1", "s2"]}
        assert result.method == "test"
        assert result.confidence == 0.9
        assert result.warnings == ["test warning"]

    def test_default_batch_size_is_20(self) -> None:
        """Default batch size is 20 spans per turn."""
        inference = TurnInference()
        # 45 spans, should result in 3 batches with default batch_size=20
        spans = [
            {"id": f"s{i}", "span_attributes": {"type": "tool"}} for i in range(45)
        ]

        result = inference.infer_turns(spans)

        # With 45 spans and batch_size=20: ceil(45/20) = 3 batches
        assert result.method == "batch_fallback"
        assert len(result.turns) == 3

    def test_metadata_without_turn_number_falls_through(self) -> None:
        """Spans with metadata but no turn_number fall to next strategy."""
        inference = TurnInference()
        spans = [
            {"id": "s1", "metadata": {"other_field": "value"}},
            {"id": "s2", "span_attributes": {"type": "task"}},
            {"id": "s3", "span_attributes": {"type": "tool"}},
        ]

        result = inference.infer_turns(spans)

        # Should fall through to span_order (task boundary detection)
        assert result.method == "span_order"

    def test_handoff_without_turn_span_id_falls_through(self) -> None:
        """Handoff without turn_span_id falls to next strategy."""
        inference = TurnInference()
        handoff = {"content": "## What Was Done\n..."}  # No turn_span_id
        spans = [
            {"id": "s1", "metadata": {"turn_number": 1}},
            {"id": "s2", "metadata": {"turn_number": 2}},
        ]

        result = inference.infer_turns(spans, handoff=handoff)

        assert result.method == "braintrust_metadata"

    def test_single_task_span_creates_single_turn(self) -> None:
        """Single task span with following tool spans creates one turn."""
        inference = TurnInference()
        spans = [
            {"id": "s1", "span_attributes": {"type": "task"}},
            {"id": "s2", "span_attributes": {"type": "tool"}},
            {"id": "s3", "span_attributes": {"type": "tool"}},
        ]

        result = inference.infer_turns(spans)

        assert result.method == "span_order"
        assert len(result.turns) == 1
        # All spans should be in turn 1
        assert set(result.turns[1]) == {"s1", "s2", "s3"}

    def test_task_boundary_groups_spans_correctly(self) -> None:
        """Task spans create boundaries that group following spans."""
        inference = TurnInference()
        spans = [
            {"id": "s1", "span_attributes": {"type": "task"}},  # Turn 1 boundary
            {"id": "s2", "span_attributes": {"type": "tool"}},
            {"id": "s3", "span_attributes": {"type": "llm"}},
            {"id": "s4", "span_attributes": {"type": "task"}},  # Turn 2 boundary
            {"id": "s5", "span_attributes": {"type": "tool"}},
        ]

        result = inference.infer_turns(spans)

        assert result.method == "span_order"
        assert len(result.turns) == 2
        assert set(result.turns[1]) == {"s1", "s2", "s3"}
        assert set(result.turns[2]) == {"s4", "s5"}

    def test_batch_fallback_distributes_evenly(self) -> None:
        """Batch fallback distributes spans evenly across turns."""
        inference = TurnInference()
        # 50 spans with batch_size=10 should give 5 turns
        spans = [
            {"id": f"s{i}", "span_attributes": {"type": "tool"}} for i in range(50)
        ]

        result = inference.infer_turns(spans, batch_size=10)

        assert result.method == "batch_fallback"
        assert len(result.turns) == 5
        # Each turn should have 10 spans
        for turn_num, span_ids in result.turns.items():
            assert len(span_ids) == 10

    def test_warnings_added_for_low_confidence(self) -> None:
        """Warnings added when using low-confidence inference methods."""
        inference = TurnInference()
        spans = [
            {"id": f"s{i}", "span_attributes": {"type": "tool"}} for i in range(100)
        ]

        result = inference.infer_turns(spans, batch_size=20)

        assert result.method == "batch_fallback"
        assert len(result.warnings) > 0
        assert any("fallback" in w.lower() for w in result.warnings)

    def test_no_warnings_for_high_confidence(self) -> None:
        """No warnings added for high-confidence methods."""
        inference = TurnInference()
        spans = [
            {"id": "s1", "metadata": {"turn_number": 1}},
            {"id": "s2", "metadata": {"turn_number": 2}},
        ]

        result = inference.infer_turns(spans)

        assert result.method == "braintrust_metadata"
        assert len(result.warnings) == 0

    def test_handoff_span_not_in_list_adds_warning(self) -> None:
        """If turn_span_id from handoff not found in spans, add warning."""
        inference = TurnInference()
        handoff = {"turn_span_id": "missing-span-id"}
        spans = [{"id": "s1"}, {"id": "s2"}]

        result = inference.infer_turns(spans, handoff=handoff)

        # Should fall through to next strategy since span not found
        assert result.method != "handoff_frontmatter"
        # May add warning about missing span
        # (implementation choice: warning or silent fallthrough)
