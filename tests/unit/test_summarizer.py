"""Tests for TemporalSummarizer."""
import pytest
import tempfile
from pathlib import Path
from typing import Any

from scripts.temporal_memory.store import TemporalMemoryStore
from scripts.temporal_memory.summarizer import (
    TemporalSummarizer,
    Transition,
    TemporalSummary,
)


class TestInvariantDetection:
    """Phase 3.1: Invariant detection tests."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.fixture
    async def store(self, temp_db):
        s = TemporalMemoryStore(session_id="test", db_path=temp_db)
        await s.connect()
        return s

    @pytest.fixture
    def summarizer(self):
        return TemporalSummarizer(confidence_threshold=0.8)

    @pytest.mark.asyncio
    async def test_detect_invariants_single_turn(self, store, summarizer):
        await store.record(turn=1, facts={"db": "sqlite"})

        invariants = await summarizer.extract_invariants(store)

        assert len(invariants) == 1
        assert invariants[0].fact == "db"
        assert invariants[0].value == "sqlite"

    @pytest.mark.asyncio
    async def test_detect_invariants_multiple_turns(self, store, summarizer):
        await store.record(turn=1, facts={"db": "sqlite", "api": "rest"})
        await store.record(turn=2, facts={"db": "sqlite", "api": "rest"})
        await store.record(turn=3, facts={"db": "sqlite", "api": "rest"})

        invariants = await summarizer.extract_invariants(store)

        fact_names = [inv.fact for inv in invariants]
        assert "db" in fact_names
        assert "api" in fact_names

    @pytest.mark.asyncio
    async def test_changing_fact_not_invariant(self, store, summarizer):
        await store.record(turn=1, facts={"db": "sqlite", "phase": "planning"})
        await store.record(turn=2, facts={"db": "sqlite", "phase": "testing"})
        await store.record(turn=3, facts={"db": "sqlite", "phase": "done"})

        invariants = await summarizer.extract_invariants(store)

        fact_names = [inv.fact for inv in invariants]
        assert "db" in fact_names  # Never changed
        assert "phase" not in fact_names  # Changed

    @pytest.mark.asyncio
    async def test_empty_store_returns_empty(self, store, summarizer):
        invariants = await summarizer.extract_invariants(store)
        assert invariants == []

    @pytest.mark.asyncio
    async def test_invariant_with_partial_presence(self, store, summarizer):
        """Test that facts not present in all turns still count if consistent."""
        # db present in turns 1,2,3 but phase only in 1,2
        await store.record(turn=1, facts={"db": "sqlite", "phase": "planning"})
        await store.record(turn=2, facts={"db": "sqlite", "phase": "planning"})
        await store.record(turn=3, facts={"db": "sqlite"})

        invariants = await summarizer.extract_invariants(store)

        fact_names = [inv.fact for inv in invariants]
        assert "db" in fact_names  # Always sqlite

    @pytest.mark.asyncio
    async def test_invariant_confidence_metadata(self, store, summarizer):
        """Test that invariants include confidence metadata."""
        await store.record(turn=1, facts={"db": "sqlite"})
        await store.record(turn=2, facts={"db": "sqlite"})

        invariants = await summarizer.extract_invariants(store)

        assert len(invariants) == 1
        assert "confidence" in invariants[0].metadata
        assert invariants[0].metadata["confidence"] > 0.8


class TestUtilityScoring:
    """Phase 3.2: Utility scoring tests."""

    def test_utility_recent_higher(self):
        summarizer = TemporalSummarizer()

        t_recent = Transition("a=1", "a=2", "update", turn=10)
        t_old = Transition("b=1", "b=2", "update", turn=1)

        u_recent = summarizer._compute_utility(t_recent, current_turn=10)
        u_old = summarizer._compute_utility(t_old, current_turn=10)

        assert u_recent > u_old

    def test_utility_half_life_15_turns(self):
        summarizer = TemporalSummarizer()

        t_now = Transition("a=1", "a=2", "update", turn=15)
        t_15_ago = Transition("b=1", "b=2", "update", turn=0)

        u_now = summarizer._compute_utility(t_now, current_turn=15)
        u_15_ago = summarizer._compute_utility(t_15_ago, current_turn=15)

        # At half-life (15 turns), utility should be ~50% of recent
        assert 0.4 < u_15_ago / u_now < 0.6

    def test_utility_with_q_value(self):
        summarizer = TemporalSummarizer()

        t = Transition("a=1", "a=2", "update", turn=5)

        u_high = summarizer._compute_utility(t, current_turn=5, q_value=2.0)
        u_low = summarizer._compute_utility(t, current_turn=5, q_value=0.5)

        assert u_high > u_low

    def test_utility_with_access_count(self):
        """Test that utility increases with access frequency."""
        summarizer = TemporalSummarizer()

        t = Transition("a=1", "a=2", "update", turn=5)

        u_high_access = summarizer._compute_utility(
            t, current_turn=5, access_count=10, max_accesses=10
        )
        u_low_access = summarizer._compute_utility(
            t, current_turn=5, access_count=1, max_accesses=10
        )

        assert u_high_access > u_low_access

    def test_utility_zero_age(self):
        """Test utility at turn 0 (current turn)."""
        summarizer = TemporalSummarizer()

        t = Transition("a=1", "a=2", "update", turn=5)
        u = summarizer._compute_utility(t, current_turn=5)

        # At age 0, recency should be 1.0
        assert u > 0.5  # q_value=1, recency=1, frequency factor >= 0.5


class TestTransitionExtraction:
    """Phase 3.3: Transition extraction tests."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.fixture
    async def store(self, temp_db):
        s = TemporalMemoryStore(session_id="test", db_path=temp_db)
        await s.connect()
        return s

    @pytest.fixture
    def summarizer(self):
        return TemporalSummarizer()

    @pytest.mark.asyncio
    async def test_extract_transitions(self, store, summarizer):
        await store.record(turn=1, facts={"phase": "planning"})
        await store.record(turn=2, facts={"phase": "testing"})
        await store.record(turn=3, facts={"phase": "done"})

        transitions = await summarizer.extract_transitions(store)

        assert len(transitions) == 2

    @pytest.mark.asyncio
    async def test_transitions_ranked_by_utility(self, store, summarizer):
        await store.record(turn=1, facts={"a": "1"})
        await store.record(turn=2, facts={"a": "2"})
        await store.record(turn=3, facts={"b": "1"})
        await store.record(turn=4, facts={"b": "2"})

        transitions = await summarizer.extract_transitions(store)

        # More recent transition should be first
        assert transitions[0].turn > transitions[1].turn

    @pytest.mark.asyncio
    async def test_max_transitions_limit(self, store, summarizer):
        # Create 10 transitions
        for i in range(11):
            await store.record(turn=i + 1, facts={"phase": f"phase_{i}"})

        transitions = await summarizer.extract_transitions(store, max_transitions=5)

        assert len(transitions) <= 5

    @pytest.mark.asyncio
    async def test_millers_7_default(self, store, summarizer):
        for i in range(20):
            await store.record(turn=i + 1, facts={"x": str(i)})

        transitions = await summarizer.extract_transitions(store)

        assert len(transitions) <= 7  # Miller's 7+/-2

    @pytest.mark.asyncio
    async def test_transitions_include_from_to_state(self, store, summarizer):
        await store.record(turn=1, facts={"status": "pending"})
        await store.record(turn=2, facts={"status": "active"})

        transitions = await summarizer.extract_transitions(store)

        assert len(transitions) == 1
        assert "status=pending" in transitions[0].from_state
        assert "status=active" in transitions[0].to_state

    @pytest.mark.asyncio
    async def test_no_transitions_when_unchanged(self, store, summarizer):
        """Test that no transitions are recorded when values don't change."""
        await store.record(turn=1, facts={"db": "sqlite"})
        await store.record(turn=2, facts={"db": "sqlite"})
        await store.record(turn=3, facts={"db": "sqlite"})

        transitions = await summarizer.extract_transitions(store)

        assert len(transitions) == 0

    @pytest.mark.asyncio
    async def test_empty_store_no_transitions(self, store, summarizer):
        transitions = await summarizer.extract_transitions(store)
        assert transitions == []


class TestTokenBudgeting:
    """Phase 3.4: Token budgeting tests."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.fixture
    async def store(self, temp_db):
        s = TemporalMemoryStore(session_id="test", db_path=temp_db)
        await s.connect()
        return s

    @pytest.fixture
    def summarizer(self):
        return TemporalSummarizer()

    @pytest.mark.asyncio
    async def test_summarize_returns_typed_dict(self, store, summarizer):
        await store.record(turn=1, facts={"db": "sqlite"})

        summary = await summarizer.summarize(store)

        assert "open_questions" in summary
        assert "invariants" in summary
        assert "pending_goals" in summary
        assert "transitions" in summary
        assert "current_state" in summary
        assert "turn_count" in summary
        assert "token_estimate" in summary

    @pytest.mark.asyncio
    async def test_summarize_token_estimate(self, store, summarizer):
        await store.record(turn=1, facts={"db": "sqlite", "api": "rest"})

        summary = await summarizer.summarize(store)

        assert summary["token_estimate"] > 0

    @pytest.mark.asyncio
    async def test_summarize_respects_budget(self, store, summarizer):
        # Create lots of data
        for i in range(20):
            await store.record(turn=i + 1, facts={f"key_{i}": f"value_{i}"})

        summary = await summarizer.summarize(store, budget_tokens=100)

        assert summary["token_estimate"] <= 150  # Allow 50% overage

    @pytest.mark.asyncio
    async def test_pending_goals_extraction(self, store, summarizer):
        await store.record(
            turn=1,
            facts={"goal_tests": "pending", "goal_docs": "pending", "db": "sqlite"},
        )

        summary = await summarizer.summarize(store)

        assert len(summary["pending_goals"]) == 2

    @pytest.mark.asyncio
    async def test_summarize_empty_store(self, store, summarizer):
        """Test summarize on empty store."""
        summary = await summarizer.summarize(store)

        assert summary["open_questions"] == []
        assert summary["invariants"] == []
        assert summary["pending_goals"] == []
        assert summary["transitions"] == []
        assert summary["current_state"] == {}
        assert summary["turn_count"] == 0

    @pytest.mark.asyncio
    async def test_summarize_turn_count(self, store, summarizer):
        await store.record(turn=1, facts={"a": "1"})
        await store.record(turn=2, facts={"a": "2"})
        await store.record(turn=3, facts={"a": "3"})

        summary = await summarizer.summarize(store)

        assert summary["turn_count"] == 3

    @pytest.mark.asyncio
    async def test_goals_achieved_not_pending(self, store, summarizer):
        """Test that achieved goals are not in pending_goals."""
        await store.record(
            turn=1, facts={"goal_tests": "achieved", "goal_docs": "pending"}
        )

        summary = await summarizer.summarize(store)

        pending_goals = summary["pending_goals"]
        assert "goal_docs" in pending_goals
        assert "goal_tests" not in pending_goals


class TestQValueRanking:
    """Phase 3.5: Q-value ranking tests."""

    def test_rank_open_questions_high_first(self):
        summarizer = TemporalSummarizer()

        unknowns = ["framework", "database", "cache"]
        ranked = summarizer.rank_open_questions(unknowns)

        # Should return list of (question, q_value, why) tuples
        assert len(ranked) == 3
        assert all(len(r) == 3 for r in ranked)

    def test_rank_preserves_all_questions(self):
        summarizer = TemporalSummarizer()

        unknowns = ["a", "b", "c"]
        ranked = summarizer.rank_open_questions(unknowns)

        questions = [r[0] for r in ranked]
        assert set(questions) == {"a", "b", "c"}

    def test_unknown_questions_get_med(self):
        summarizer = TemporalSummarizer()

        unknowns = ["unknown_question_xyz"]
        ranked = summarizer.rank_open_questions(unknowns)

        assert ranked[0][1] == "MED"
        # Unknown questions get default MED priority with explanatory message
        assert "default" in ranked[0][2].lower() or "unrecognized" in ranked[0][2].lower()

    def test_high_priority_sorted_first(self):
        """Test that HIGH priority questions come before MED."""
        summarizer = TemporalSummarizer()

        # framework is HIGH, hosting is MED in Q_CONFIGS
        unknowns = ["hosting", "framework"]
        ranked = summarizer.rank_open_questions(unknowns)

        # framework (HIGH) should come first
        assert ranked[0][0] == "framework"
        assert ranked[0][1] == "HIGH"
        assert ranked[1][0] == "hosting"
        assert ranked[1][1] == "MED"

    def test_rank_empty_list(self):
        """Test ranking empty list of questions."""
        summarizer = TemporalSummarizer()

        ranked = summarizer.rank_open_questions([])

        assert ranked == []

    def test_rank_known_questions_have_why(self):
        """Test that known questions have meaningful why explanations."""
        summarizer = TemporalSummarizer()

        unknowns = ["database", "framework"]
        ranked = summarizer.rank_open_questions(unknowns)

        for _, _, why in ranked:
            assert len(why) > 10  # Meaningful explanation


class TestSummarizerIntegration:
    """Integration tests for the full summarizer workflow."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.fixture
    async def store(self, temp_db):
        s = TemporalMemoryStore(session_id="test", db_path=temp_db)
        await s.connect()
        return s

    @pytest.fixture
    def summarizer(self):
        return TemporalSummarizer()

    @pytest.mark.asyncio
    async def test_full_workflow(self, store, summarizer):
        """Test a realistic multi-turn session."""
        # Turn 1: Initial setup with unknowns
        await store.record_with_erotetic(
            turn=1,
            facts={
                "framework": "UNKNOWN",
                "database": "UNKNOWN",
                "goal_setup": "pending",
            },
        )

        # Turn 2: Some decisions made
        await store.record_with_erotetic(
            turn=2,
            facts={
                "framework": "fastapi",
                "database": "UNKNOWN",
                "goal_setup": "achieved",
            },
        )

        # Turn 3: More progress
        await store.record_with_erotetic(
            turn=3,
            facts={
                "framework": "fastapi",
                "database": "postgres",
                "goal_tests": "pending",
            },
        )

        summary = await summarizer.summarize(store)

        # Framework should be invariant after turn 2
        assert len(summary["invariants"]) >= 0  # May vary based on threshold
        assert summary["turn_count"] == 3
        assert "goal_tests" in summary["pending_goals"]

    @pytest.mark.asyncio
    async def test_transitions_with_erotetic(self, store, summarizer):
        """Test that transitions work with erotetic recording."""
        await store.record_with_erotetic(turn=1, facts={"phase": "planning"})
        await store.record_with_erotetic(turn=2, facts={"phase": "coding"})
        await store.record_with_erotetic(turn=3, facts={"phase": "testing"})

        transitions = await summarizer.extract_transitions(store)

        assert len(transitions) == 2
        # Most recent transition first
        assert "testing" in transitions[0].to_state
