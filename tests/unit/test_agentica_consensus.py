"""Tests for Agentica Consensus primitive (TDD - tests written first)."""

import pytest
from scripts.agentica_patterns.primitives import Consensus, ConsensusMode, ConsensusNotReached


class TestConsensusMajority:
    """Test majority voting mode."""

    def test_majority_simple(self):
        """3 votes: A, A, B → A wins"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "A", "B"]

        result = consensus.decide(votes)

        assert result == "A"

    def test_majority_tie_breaks_to_first(self):
        """A, B, A, B → A wins (first in order)"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B", "A", "B"]

        result = consensus.decide(votes)

        assert result == "A"

    def test_majority_with_three_options(self):
        """A, B, C, A, A → A wins with 3/5 votes"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B", "C", "A", "A"]

        result = consensus.decide(votes)

        assert result == "A"

    def test_majority_single_vote(self):
        """Single vote → that vote wins"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A"]

        result = consensus.decide(votes)

        assert result == "A"


class TestConsensusWeighted:
    """Test weighted voting."""

    def test_weighted_voting(self):
        """A(weight=2), B(weight=1) → A wins"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B"]
        weights = [2, 1]

        result = consensus.decide(votes, weights=weights)

        assert result == "A"

    def test_weighted_voting_complex(self):
        """A(3), B(2), A(1), C(1) → A wins with total weight 4"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B", "A", "C"]
        weights = [3, 2, 1, 1]

        result = consensus.decide(votes, weights=weights)

        assert result == "A"

    def test_weighted_voting_tie_breaks_to_first(self):
        """A(2), B(2) → A wins (first in order)"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B"]
        weights = [2, 2]

        result = consensus.decide(votes, weights=weights)

        assert result == "A"

    def test_weighted_voting_wrong_length_raises(self):
        """Mismatched votes and weights → raises ValueError"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B", "C"]
        weights = [1, 2]  # Wrong length

        with pytest.raises(ValueError, match="weights.*same length"):
            consensus.decide(votes, weights=weights)


class TestConsensusUnanimous:
    """Test unanimous voting mode."""

    def test_unanimous_passes(self):
        """All same → passes"""
        consensus = Consensus(mode=ConsensusMode.UNANIMOUS)
        votes = ["A", "A", "A"]

        result = consensus.decide(votes)

        assert result == "A"

    def test_unanimous_fails(self):
        """Not all same → raises ConsensusNotReached"""
        consensus = Consensus(mode=ConsensusMode.UNANIMOUS)
        votes = ["A", "A", "B"]

        with pytest.raises(ConsensusNotReached):
            consensus.decide(votes)

    def test_unanimous_single_vote(self):
        """Single vote → passes (trivially unanimous)"""
        consensus = Consensus(mode=ConsensusMode.UNANIMOUS)
        votes = ["A"]

        result = consensus.decide(votes)

        assert result == "A"

    def test_unanimous_error_message_includes_votes(self):
        """ConsensusNotReached should include vote details"""
        consensus = Consensus(mode=ConsensusMode.UNANIMOUS)
        votes = ["approve", "approve", "reject"]

        with pytest.raises(ConsensusNotReached) as exc_info:
            consensus.decide(votes)

        # Error message should mention the votes
        assert "approve" in str(exc_info.value)
        assert "reject" in str(exc_info.value)


class TestConsensusThreshold:
    """Test threshold voting mode."""

    def test_threshold_75_passes(self):
        """3/4 agree → passes at 75% threshold"""
        consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.75)
        votes = ["A", "A", "A", "B"]

        result = consensus.decide(votes)

        assert result == "A"

    def test_threshold_75_fails(self):
        """2/4 agree → fails at 75% threshold"""
        consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.75)
        votes = ["A", "A", "B", "B"]

        with pytest.raises(ConsensusNotReached):
            consensus.decide(votes)

    def test_threshold_50_is_majority(self):
        """50% threshold behaves like majority"""
        consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.50)
        votes = ["A", "A", "B"]

        result = consensus.decide(votes)

        assert result == "A"

    def test_threshold_100_is_unanimous(self):
        """100% threshold behaves like unanimous"""
        consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=1.0)
        votes = ["A", "A", "A"]

        result = consensus.decide(votes)

        assert result == "A"

    def test_threshold_100_fails_on_disagreement(self):
        """100% threshold fails if not unanimous"""
        consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=1.0)
        votes = ["A", "A", "B"]

        with pytest.raises(ConsensusNotReached):
            consensus.decide(votes)

    def test_threshold_with_weights(self):
        """Threshold should work with weighted votes"""
        consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.6)
        votes = ["A", "A", "B"]
        weights = [2, 1, 1]  # A has 3/4 = 75% weight

        result = consensus.decide(votes, weights=weights)

        assert result == "A"

    def test_threshold_weighted_fails(self):
        """Threshold fails when weighted percentage too low"""
        consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.8)
        votes = ["A", "A", "B"]
        weights = [2, 1, 1]  # A has 3/4 = 75% weight < 80%

        with pytest.raises(ConsensusNotReached):
            consensus.decide(votes, weights=weights)

    def test_threshold_requires_threshold_param(self):
        """Creating threshold mode without threshold param → raises ValueError"""
        with pytest.raises(ValueError, match="threshold"):
            Consensus(mode=ConsensusMode.THRESHOLD)

    def test_threshold_invalid_range_raises(self):
        """Threshold outside [0, 1] → raises ValueError"""
        with pytest.raises(ValueError, match="between 0 and 1"):
            Consensus(mode=ConsensusMode.THRESHOLD, threshold=1.5)

        with pytest.raises(ValueError, match="between 0 and 1"):
            Consensus(mode=ConsensusMode.THRESHOLD, threshold=-0.1)


class TestConsensusValidation:
    """Test input validation."""

    def test_empty_votes_raises(self):
        """No votes → raises ValueError"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = []

        with pytest.raises(ValueError, match="empty"):
            consensus.decide(votes)

    def test_none_votes_raises(self):
        """None as votes → raises ValueError"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)

        with pytest.raises(ValueError):
            consensus.decide(None)

    def test_negative_weight_raises(self):
        """Negative weight → raises ValueError"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B"]
        weights = [1, -1]

        with pytest.raises(ValueError, match="negative"):
            consensus.decide(votes, weights=weights)

    def test_zero_weight_allowed(self):
        """Zero weight is allowed (vote doesn't count)"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B", "B"]
        weights = [0, 1, 1]  # A has weight 0, so B wins

        result = consensus.decide(votes, weights=weights)

        assert result == "B"


class TestConsensusStructuredVotes:
    """Test with structured vote data (dicts)."""

    def test_dict_votes_majority(self):
        """Votes as dicts → decides based on equality"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = [
            {"decision": "approve", "confidence": 0.9},
            {"decision": "approve", "confidence": 0.8},
            {"decision": "reject", "confidence": 0.7},
        ]

        # Should not work with dicts directly (they're unhashable)
        # Should raise TypeError or require custom key function
        with pytest.raises(TypeError):
            consensus.decide(votes)

    def test_dict_votes_with_key_function(self):
        """Votes as dicts with key function → extracts decision field"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = [
            {"decision": "approve", "confidence": 0.9},
            {"decision": "approve", "confidence": 0.8},
            {"decision": "reject", "confidence": 0.7},
        ]

        result = consensus.decide(votes, key=lambda v: v["decision"])

        assert result == {"decision": "approve", "confidence": 0.9}


class TestConsensusEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_all_different_votes_majority_picks_first(self):
        """All unique votes → first vote wins in majority mode"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["A", "B", "C", "D"]

        result = consensus.decide(votes)

        # With all tied at 1 vote each, should pick first
        assert result == "A"

    def test_case_sensitive_voting(self):
        """Votes are case-sensitive by default"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["Yes", "yes", "YES"]

        # All different due to case
        result = consensus.decide(votes)

        # Should pick first (they're all tied at 1)
        assert result == "Yes"

    def test_whitespace_matters(self):
        """Whitespace in votes matters"""
        consensus = Consensus(mode=ConsensusMode.MAJORITY)
        votes = ["approve", "approve ", " approve"]

        # All different due to whitespace
        result = consensus.decide(votes)

        assert result == "approve"
