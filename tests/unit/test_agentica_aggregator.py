"""
Failing tests for Aggregator primitive - TDD approach.

These tests will fail until the Aggregator implementation is created.
"""

import pytest
from scripts.agentica_patterns.primitives import Aggregator, AggregateMode


class TestAggregator:
    """Test suite for the Aggregator primitive."""

    def test_merge_dicts(self):
        """Merge mode combines dictionaries without conflicts."""
        aggregator = Aggregator(mode=AggregateMode.MERGE)

        results = [
            {"a": 1, "x": 10},
            {"b": 2, "y": 20}
        ]

        merged = aggregator.aggregate(results)

        assert merged == {"a": 1, "b": 2, "x": 10, "y": 20}

    def test_merge_dicts_conflict_last_wins(self):
        """When merging dicts with key conflicts, last value wins."""
        aggregator = Aggregator(mode=AggregateMode.MERGE)

        results = [
            {"a": 1, "b": "first"},
            {"a": 2, "c": 3},
            {"a": 99}
        ]

        merged = aggregator.aggregate(results)

        assert merged["a"] == 99
        assert merged["b"] == "first"
        assert merged["c"] == 3

    def test_merge_lists(self):
        """Merge mode concatenates lists."""
        aggregator = Aggregator(mode=AggregateMode.MERGE)

        results = [
            [1, 2],
            [3, 4],
            [5]
        ]

        merged = aggregator.aggregate(results)

        assert merged == [1, 2, 3, 4, 5]

    def test_concat_strings(self):
        """Concat mode joins strings with default separator (space)."""
        aggregator = Aggregator(mode=AggregateMode.CONCAT)

        results = ["hello", "world", "from", "agents"]

        concatenated = aggregator.aggregate(results)

        assert concatenated == "hello world from agents"

    def test_concat_with_separator(self):
        """Concat mode uses custom separator when provided."""
        aggregator = Aggregator(mode=AggregateMode.CONCAT, separator="|")

        results = ["a", "b", "c"]

        concatenated = aggregator.aggregate(results)

        assert concatenated == "a|b|c"

    def test_concat_with_newline_separator(self):
        """Concat mode can use newline as separator."""
        aggregator = Aggregator(mode=AggregateMode.CONCAT, separator="\n")

        results = ["Line 1", "Line 2", "Line 3"]

        concatenated = aggregator.aggregate(results)

        assert concatenated == "Line 1\nLine 2\nLine 3"

    def test_best_picks_highest_score(self):
        """Best mode selects result with highest score."""
        aggregator = Aggregator(mode=AggregateMode.BEST)

        results = [
            {"result": "Agent A output", "score": 0.7},
            {"result": "Agent B output", "score": 0.95},
            {"result": "Agent C output", "score": 0.6}
        ]

        best = aggregator.aggregate(results)

        assert best == "Agent B output"

    def test_best_requires_score_field(self):
        """Best mode raises error if results lack score field."""
        aggregator = Aggregator(mode=AggregateMode.BEST)

        results = [
            {"result": "No score here"},
            {"result": "Also no score"}
        ]

        with pytest.raises(ValueError, match="score"):
            aggregator.aggregate(results)

    def test_deduplicate_lists(self):
        """Merge mode with dedupe removes duplicates from lists."""
        aggregator = Aggregator(mode=AggregateMode.MERGE, deduplicate=True)

        results = [
            ["a", "b", "c"],
            ["b", "c", "d"],
            ["a", "e"]
        ]

        merged = aggregator.aggregate(results)

        # Order preserved, duplicates removed
        assert set(merged) == {"a", "b", "c", "d", "e"}
        assert len(merged) == 5

    def test_deduplicate_strings(self):
        """Concat mode with dedupe removes duplicate words."""
        aggregator = Aggregator(mode=AggregateMode.CONCAT, deduplicate=True)

        results = ["hello world", "world peace", "hello"]

        concatenated = aggregator.aggregate(results)

        # Each word appears only once
        words = concatenated.split()
        assert set(words) == {"hello", "world", "peace"}
        assert len(words) == 3

    def test_empty_results_raises(self):
        """Aggregating empty results raises ValueError."""
        aggregator = Aggregator(mode=AggregateMode.MERGE)

        with pytest.raises(ValueError, match="empty"):
            aggregator.aggregate([])

    def test_single_result_returns_as_is(self):
        """Aggregating single result returns it unchanged."""
        aggregator = Aggregator(mode=AggregateMode.MERGE)

        result = aggregator.aggregate([{"key": "value"}])

        assert result == {"key": "value"}

    def test_merge_mixed_types_raises(self):
        """Merge mode raises error for incompatible types."""
        aggregator = Aggregator(mode=AggregateMode.MERGE)

        results = [
            {"a": 1},
            [1, 2, 3],  # Can't merge dict with list
            "string"
        ]

        with pytest.raises(TypeError, match="incompatible"):
            aggregator.aggregate(results)

    def test_concat_non_strings_converts(self):
        """Concat mode converts non-strings to strings."""
        aggregator = Aggregator(mode=AggregateMode.CONCAT)

        results = [42, "hello", 3.14, True]

        concatenated = aggregator.aggregate(results)

        assert concatenated == "42 hello 3.14 True"

    def test_best_with_tie_picks_first(self):
        """Best mode picks first result when scores are tied."""
        aggregator = Aggregator(mode=AggregateMode.BEST)

        results = [
            {"result": "First", "score": 0.9},
            {"result": "Second", "score": 0.9},
            {"result": "Third", "score": 0.9}
        ]

        best = aggregator.aggregate(results)

        assert best == "First"

    def test_merge_nested_dicts(self):
        """Merge mode handles nested dictionaries."""
        aggregator = Aggregator(mode=AggregateMode.MERGE)

        results = [
            {"outer": {"a": 1}},
            {"outer": {"b": 2}, "other": 3}
        ]

        merged = aggregator.aggregate(results)

        # Last value wins for 'outer' key
        assert merged == {"outer": {"b": 2}, "other": 3}

    def test_aggregate_with_none_values(self):
        """Aggregator handles None values appropriately."""
        aggregator = Aggregator(mode=AggregateMode.MERGE)

        results = [
            {"a": 1},
            None,  # Should be skipped
            {"b": 2}
        ]

        merged = aggregator.aggregate(results)

        assert merged == {"a": 1, "b": 2}
