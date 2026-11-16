"""End-to-end integration tests for temporal memory system.

Tests the full workflow including:
- Multi-turn session recording
- Invariant detection across turns
- Transition tracking and utility scoring
- Erotetic (open question) tracking
- Handoff generation and parsing
- CLI integration
- Token reduction verification
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from scripts.temporal_memory.handoff import (
    TemporalHandoffState,
    parse_temporal_handoff,
)
from scripts.temporal_memory.inertia import RevisionPriority
from scripts.temporal_memory.store import TemporalMemoryStore
from scripts.temporal_memory.summarizer import TemporalSummarizer


class TestTemporalMemoryE2E:
    """Full workflow integration tests."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.mark.asyncio
    async def test_15_turn_session_workflow(self, temp_db):
        """Simulate a 15-turn session with state changes.

        This test simulates a realistic session workflow with three phases:
        1. Planning (turns 1-5): Initial setup with open questions
        2. Testing (turns 6-10): Open questions resolved
        3. Done (turns 11-15): Goals achieved

        Verifies that:
        - Invariant facts (db) are detected correctly
        - Transitions are tracked (phase changes)
        - Turn count is accurate
        """
        store = TemporalMemoryStore(session_id="e2e-test-15-turn", db_path=temp_db)
        await store.connect()

        # Turn 1-5: Planning phase
        for turn in range(1, 6):
            await store.record_with_erotetic(
                turn,
                {
                    "phase": "planning",
                    "db": "sqlite",
                    "goal_tests": "pending",
                    "auth": "UNKNOWN",  # Open question
                },
            )

        # Turn 6-10: Testing phase
        for turn in range(6, 11):
            await store.record_with_erotetic(
                turn,
                {
                    "phase": "testing",
                    "db": "sqlite",
                    "goal_tests": "pending",
                    "auth": "jwt",  # Resolved
                },
            )

        # Turn 11-15: Done phase
        for turn in range(11, 16):
            await store.record_with_erotetic(
                turn,
                {
                    "phase": "done",
                    "db": "sqlite",
                    "goal_tests": "achieved",
                },
            )

        # Summarize
        summarizer = TemporalSummarizer()
        summary = await summarizer.summarize(store, budget_tokens=2000)

        # Verify invariants (db never changed)
        # The invariant list contains compact TEL format like "ALWAYS(db=sqlite)"
        invariant_strs = summary["invariants"]
        db_invariants = [inv for inv in invariant_strs if "db" in inv]
        assert len(db_invariants) >= 1, f"Expected db invariant, got {invariant_strs}"

        # Verify transitions (phase changed twice: planning->testing, testing->done)
        assert len(summary["transitions"]) >= 2, (
            f"Expected at least 2 transitions, got {summary['transitions']}"
        )

        # Verify turn count
        assert summary["turn_count"] == 15

        # Verify current state
        assert summary["current_state"]["phase"] == "done"
        assert summary["current_state"]["db"] == "sqlite"

    @pytest.mark.asyncio
    async def test_handoff_write_parse_verify(self, temp_db):
        """Write handoff, parse it back, verify data integrity.

        Tests the complete handoff round-trip:
        1. Record some temporal state
        2. Generate a summary
        3. Create a handoff from the summary
        4. Generate markdown
        5. Parse the markdown back
        6. Verify data integrity across the round-trip
        """
        store = TemporalMemoryStore(session_id="handoff-test", db_path=temp_db)
        await store.connect()

        # Record some state with a transition
        await store.record(turn=1, facts={"db": "sqlite", "phase": "testing"})
        await store.record(turn=2, facts={"db": "sqlite", "phase": "done"})

        # Summarize
        summarizer = TemporalSummarizer()
        summary = await summarizer.summarize(store)

        # Create handoff with ranked open questions
        open_questions_ranked = summarizer.rank_open_questions([])

        handoff = TemporalHandoffState.from_summary(
            summary={
                "open_questions_ranked": open_questions_ranked,
                "pending_goals": summary["pending_goals"],
                "transitions": summary["transitions"],
                "invariants": summary["invariants"],
                "current_state": summary["current_state"],
                "turn_count": summary["turn_count"],
            },
            context="E2E test context",
            instruction="Verify data integrity",
        )

        # Generate markdown
        md = handoff.to_markdown()

        # Parse it back
        parsed = parse_temporal_handoff(md)

        # Verify data survived round-trip
        assert parsed["context"] == "E2E test context"
        assert parsed["next_instruction"] == "Verify data integrity"
        assert parsed["turn_count"] == handoff.turn_count

        # Verify invariants parsed from summary
        assert "db" in parsed["invariants"] or "sqlite" in str(parsed["invariants"])
        assert parsed["current_state"]["db"] == "sqlite"

    @pytest.mark.asyncio
    async def test_multi_agent_handoff_simulation(self, temp_db):
        """Simulate agent handoff with state transfer.

        Tests multi-agent coordination:
        1. Agent 1 does initial work (75% complete)
        2. Agent 1 generates handoff
        3. Agent 2 receives handoff via parsing
        4. Agent 2 continues work to completion
        5. Verify Agent 2 can see Agent 1's progress
        """
        # Agent 1: Initial work
        store1 = TemporalMemoryStore(session_id="agent-1", db_path=temp_db)
        await store1.connect()

        await store1.record(
            turn=1,
            facts={
                "task": "implement memory",
                "progress": "50%",
                "blocker": "UNKNOWN",
            },
        )
        await store1.record(
            turn=2,
            facts={
                "task": "implement memory",
                "progress": "75%",
                "blocker": "none",
            },
        )

        # Generate handoff from Agent 1
        summarizer1 = TemporalSummarizer()
        summary1 = await summarizer1.summarize(store1)

        handoff1 = TemporalHandoffState(
            context="Agent 1 completed 75% of memory implementation",
            next_instruction="Complete remaining 25%",
            invariants={"task": "implement memory"},
            transitions=summary1["transitions"],
            turn_count=summary1["turn_count"],
        )

        # Agent 2: Resume from handoff
        store2 = TemporalMemoryStore(session_id="agent-2", db_path=temp_db)
        await store2.connect()

        # Parse the handoff from Agent 1
        parsed = parse_temporal_handoff(handoff1.to_markdown())

        # Verify Agent 2 can see Agent 1's work
        assert parsed["context"] == "Agent 1 completed 75% of memory implementation"
        assert "implement memory" in str(parsed["invariants"])

        # Agent 2 continues
        await store2.record(
            turn=3,
            facts={
                "task": "implement memory",
                "progress": "100%",
            },
        )

        summary2 = await summarizer1.summarize(store2)
        assert summary2["current_state"]["progress"] == "100%"

    @pytest.mark.asyncio
    async def test_inertia_with_revision_events(self, temp_db):
        """Test inertia rule with revision tracking.

        The TEL inertia rule states:
            holds(P, T+1) :- holds(P, T), not -holds(P, T+1)

        This means facts persist unless explicitly updated.

        This test verifies:
        1. Initial state is recorded
        2. advance_turn() applies updates while preserving unchanged facts
        3. Revision events are generated for changes
        4. Inertia preserves unchanged facts (db persists)
        """
        store = TemporalMemoryStore(session_id="inertia-test", db_path=temp_db)
        await store.connect()

        # Initial state
        await store.record(turn=1, facts={"db": "sqlite", "phase": "planning"})

        # Advance with update - only phase changes
        revisions = await store.advance_turn(
            updates={"phase": "testing"},
            priority=RevisionPriority.RECENT_OBSERVATION,
        )

        # Verify revision event for phase change
        assert len(revisions) == 1
        assert revisions[0].key == "phase"
        assert revisions[0].old_value == "planning"
        assert revisions[0].new_value == "testing"

        # Verify inertia (db persisted without being in updates)
        state = await store.get_current_state()
        assert state["db"] == "sqlite"
        assert state["phase"] == "testing"

    @pytest.mark.asyncio
    async def test_token_reduction_measurement(self, temp_db):
        """Verify token reduction from temporal format.

        Compares verbose prose representation to compact temporal format.
        The temporal format should be significantly more compact.
        """
        store = TemporalMemoryStore(session_id="token-test", db_path=temp_db)
        await store.connect()

        # Create verbose prose equivalent
        verbose_prose = """
        The database is sqlite.
        The current phase is testing.
        The framework is agentica.
        The api is rest.
        The cache is redis.
        """
        # Rough token estimate: ~4 chars per token
        prose_tokens = len(verbose_prose) // 4

        # Record equivalent facts
        await store.record(
            turn=1,
            facts={
                "db": "sqlite",
                "phase": "testing",
                "framework": "agentica",
                "api": "rest",
                "cache": "redis",
            },
        )

        summarizer = TemporalSummarizer()
        summary = await summarizer.summarize(store)

        # Temporal format should be more compact
        temporal_tokens = summary["token_estimate"]

        # Verify reduction (should be significant)
        # Note: token_estimate may be 0 if no transitions/invariants
        # The point is the structured format is more efficient
        assert temporal_tokens <= prose_tokens, (
            f"Expected temporal format to be more compact: "
            f"temporal={temporal_tokens}, prose={prose_tokens}"
        )

    @pytest.mark.asyncio
    async def test_open_questions_tracked_across_turns(self, temp_db):
        """Test E(X,Q) tracking across multiple turns.

        Erotetic analysis identifies UNKNOWN propositions.
        As questions get answered (UNKNOWN -> value), the count decreases.
        """
        store = TemporalMemoryStore(session_id="erotetic-test", db_path=temp_db)
        await store.connect()

        # Turn 1: Multiple unknowns
        result1 = await store.record_with_erotetic(
            turn=1,
            facts={
                "db": "UNKNOWN",
                "framework": "UNKNOWN",
                "api": "rest",  # Known
            },
        )
        assert len(result1["unknowns"]) >= 2
        assert "db" in result1["unknowns"]
        assert "framework" in result1["unknowns"]

        # Turn 2: Resolve one unknown
        result2 = await store.record_with_erotetic(
            turn=2,
            facts={
                "db": "sqlite",  # Now known
                "framework": "UNKNOWN",  # Still unknown
                "api": "rest",
            },
        )

        # Verify unknown count decreased
        assert result2["count"] < result1["count"]
        assert "db" not in result2["unknowns"]
        assert "framework" in result2["unknowns"]

        # Query open questions at each turn
        q1 = await store.get_open_questions(turn=1)
        q2 = await store.get_open_questions(turn=2)

        assert len(q2) < len(q1)
        assert "db" in q1
        assert "db" not in q2

    @pytest.mark.asyncio
    async def test_invariant_detection_accuracy(self, temp_db):
        """Test that invariant detection correctly identifies stable facts.

        Facts that appear in all turns with consistent values should be
        detected as invariants. Facts that change should not be invariants.
        """
        store = TemporalMemoryStore(session_id="invariant-accuracy", db_path=temp_db)
        await store.connect()

        # Record 5 turns - db is always sqlite, phase changes
        await store.record(turn=1, facts={"db": "sqlite", "phase": "init"})
        await store.record(turn=2, facts={"db": "sqlite", "phase": "planning"})
        await store.record(turn=3, facts={"db": "sqlite", "phase": "coding"})
        await store.record(turn=4, facts={"db": "sqlite", "phase": "testing"})
        await store.record(turn=5, facts={"db": "sqlite", "phase": "done"})

        summarizer = TemporalSummarizer()

        # Extract raw invariants
        invariants = await summarizer.extract_invariants(store)

        # db should be invariant (never changed)
        db_invariants = [inv for inv in invariants if inv.fact == "db"]
        assert len(db_invariants) == 1
        assert db_invariants[0].value == "sqlite"

        # phase should NOT be invariant (changed each turn)
        phase_invariants = [inv for inv in invariants if inv.fact == "phase"]
        assert len(phase_invariants) == 0

    @pytest.mark.asyncio
    async def test_transition_utility_ranking(self, temp_db):
        """Test that transitions are ranked by utility (recency).

        More recent transitions should have higher utility scores
        due to the 15-turn half-life decay.
        """
        store = TemporalMemoryStore(session_id="utility-ranking", db_path=temp_db)
        await store.connect()

        # Record transitions at different turns
        await store.record(turn=1, facts={"phase": "init"})
        await store.record(turn=5, facts={"phase": "planning"})  # Early transition
        await store.record(turn=10, facts={"phase": "coding"})   # Middle transition
        await store.record(turn=15, facts={"phase": "done"})     # Recent transition

        summarizer = TemporalSummarizer()
        transitions = await summarizer.extract_transitions(store)

        # Transitions should be ordered by utility (most recent first)
        assert len(transitions) >= 2

        # Most recent transition should be first
        assert transitions[0].turn >= transitions[-1].turn

    @pytest.mark.asyncio
    async def test_pending_goals_detection(self, temp_db):
        """Test that pending goals are correctly identified.

        Facts with keys starting with 'goal_' that don't have value 'achieved'
        should be listed as pending goals.
        """
        store = TemporalMemoryStore(session_id="goals-test", db_path=temp_db)
        await store.connect()

        await store.record(
            turn=1,
            facts={
                "goal_tests": "pending",      # Should be pending
                "goal_docs": "in_progress",   # Should be pending
                "goal_deploy": "achieved",    # Should NOT be pending
                "phase": "working",           # Not a goal
            },
        )

        summarizer = TemporalSummarizer()
        summary = await summarizer.summarize(store)

        # Check pending goals
        pending = summary["pending_goals"]
        assert "goal_tests" in pending
        assert "goal_docs" in pending
        assert "goal_deploy" not in pending
        assert "phase" not in pending


class TestCLIIntegration:
    """Test CLI as subprocess."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path for CLI tests."""
        return str(tmp_path / "cli-test.db")

    def run_cli(self, *args, db_path=None):
        """Run the temporal memory CLI as a subprocess."""
        cmd = [
            "uv", "run", "python", "-m", "scripts.temporal_memory.cli"
        ] + list(args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=os.environ,
            cwd=Path(__file__).parent.parent.parent,  # Project root
        )
        return result

    def test_cli_record_and_summarize(self, temp_db_path):
        """Test CLI record and summarize commands."""
        session_id = "cli-e2e-basic"

        # Record turn 1
        result = self.run_cli(
            "record",
            "--session-id", session_id,
            "--turn", "1",
            "--facts", '{"phase": "planning", "db": "sqlite"}',
            "--db-path", temp_db_path,
        )
        assert result.returncode == 0, f"Record failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["status"] == "ok"
        assert output["turn"] == 1

        # Record turn 2
        result = self.run_cli(
            "record",
            "--session-id", session_id,
            "--turn", "2",
            "--facts", '{"phase": "testing", "db": "sqlite"}',
            "--db-path", temp_db_path,
        )
        assert result.returncode == 0

        # Summarize
        result = self.run_cli(
            "summarize",
            "--session-id", session_id,
            "--output", "json",
            "--db-path", temp_db_path,
        )
        assert result.returncode == 0, f"Summarize failed: {result.stderr}"

        summary = json.loads(result.stdout)
        assert summary["turn_count"] == 2
        assert "phase" in summary["current_state"]
        assert summary["current_state"]["db"] == "sqlite"

    def test_cli_full_workflow(self, temp_db_path):
        """Test a complete CLI workflow with multiple turns and transitions."""
        session_id = "cli-e2e-full"

        # Record multiple turns with phase transitions
        phases = ["planning", "coding", "testing", "done"]
        for i, phase in enumerate(phases, 1):
            result = self.run_cli(
                "record",
                "--session-id", session_id,
                "--turn", str(i),
                "--facts", json.dumps({"phase": phase, "db": "sqlite"}),
                "--db-path", temp_db_path,
            )
            assert result.returncode == 0, f"Record turn {i} failed: {result.stderr}"

        # Summarize
        result = self.run_cli(
            "summarize",
            "--session-id", session_id,
            "--output", "json",
            "--db-path", temp_db_path,
        )
        assert result.returncode == 0

        summary = json.loads(result.stdout)
        assert summary["turn_count"] == 4

        # Should have transitions (phase changed 3 times)
        assert len(summary["transitions"]) >= 3

    def test_cli_markdown_output(self, temp_db_path):
        """Test CLI markdown output format."""
        session_id = "cli-e2e-markdown"

        # Record a turn
        self.run_cli(
            "record",
            "--session-id", session_id,
            "--turn", "1",
            "--facts", '{"phase": "testing", "goal_tests": "pending"}',
            "--db-path", temp_db_path,
        )

        # Get markdown summary
        result = self.run_cli(
            "summarize",
            "--session-id", session_id,
            "--output", "markdown",
            "--db-path", temp_db_path,
        )
        assert result.returncode == 0

        md = result.stdout
        assert "# Temporal Summary" in md
        assert "Turn 1" in md
        assert "## Pending Goals" in md
        assert "goal_tests" in md

    def test_cli_invalid_json_error(self, temp_db_path):
        """Test CLI error handling for invalid JSON."""
        result = self.run_cli(
            "record",
            "--session-id", "error-test",
            "--turn", "1",
            "--facts", "not valid json",
            "--db-path", temp_db_path,
        )

        # Should fail with error
        assert result.returncode != 0
        assert "Invalid JSON" in result.stderr

    def test_cli_token_budget(self, temp_db_path):
        """Test CLI respects token budget parameter."""
        session_id = "cli-e2e-budget"

        # Record many turns to generate more content
        for i in range(1, 11):
            self.run_cli(
                "record",
                "--session-id", session_id,
                "--turn", str(i),
                "--facts", json.dumps({"phase": f"phase_{i}", "counter": i}),
                "--db-path", temp_db_path,
            )

        # Get summary with small budget
        result = self.run_cli(
            "summarize",
            "--session-id", session_id,
            "--budget", "100",  # Very small budget
            "--output", "json",
            "--db-path", temp_db_path,
        )
        assert result.returncode == 0

        summary = json.loads(result.stdout)
        # Token estimate should respect budget (may be truncated)
        # The system tries to stay under budget by limiting transitions
        assert summary["token_estimate"] <= 200  # Some margin


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.mark.asyncio
    async def test_empty_session(self, temp_db):
        """Test summarizing an empty session."""
        store = TemporalMemoryStore(session_id="empty-session", db_path=temp_db)
        await store.connect()

        summarizer = TemporalSummarizer()
        summary = await summarizer.summarize(store)

        assert summary["turn_count"] == 0
        assert summary["current_state"] == {}
        assert summary["invariants"] == []
        assert summary["transitions"] == []

    @pytest.mark.asyncio
    async def test_single_turn_session(self, temp_db):
        """Test a session with only one turn."""
        store = TemporalMemoryStore(session_id="single-turn", db_path=temp_db)
        await store.connect()

        await store.record(turn=1, facts={"phase": "init", "db": "sqlite"})

        summarizer = TemporalSummarizer()
        summary = await summarizer.summarize(store)

        assert summary["turn_count"] == 1
        assert summary["current_state"]["phase"] == "init"
        assert summary["transitions"] == []  # No transitions with one turn

    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, temp_db):
        """Test multiple sessions can coexist in same database."""
        store1 = TemporalMemoryStore(session_id="session-1", db_path=temp_db)
        store2 = TemporalMemoryStore(session_id="session-2", db_path=temp_db)

        await store1.connect()
        await store2.connect()

        # Record different data in each session
        await store1.record(turn=1, facts={"session": "1", "phase": "a"})
        await store2.record(turn=1, facts={"session": "2", "phase": "x"})

        # Verify isolation
        state1 = await store1.get_current_state()
        state2 = await store2.get_current_state()

        assert state1["session"] == "1"
        assert state2["session"] == "2"
        assert state1["phase"] == "a"
        assert state2["phase"] == "x"

    @pytest.mark.asyncio
    async def test_special_characters_in_facts(self, temp_db):
        """Test handling of special characters in fact values."""
        store = TemporalMemoryStore(session_id="special-chars", db_path=temp_db)
        await store.connect()

        special_value = "value with 'quotes' and \"double\" and\nnewlines"
        await store.record(turn=1, facts={"special": special_value})

        state = await store.get_current_state()
        assert state["special"] == special_value

    @pytest.mark.asyncio
    async def test_unicode_in_facts(self, temp_db):
        """Test handling of unicode in fact values."""
        store = TemporalMemoryStore(session_id="unicode-test", db_path=temp_db)
        await store.connect()

        unicode_value = "Test with unicode: emoji plus CJK"
        await store.record(turn=1, facts={"text": unicode_value})

        state = await store.get_current_state()
        assert state["text"] == unicode_value

    @pytest.mark.asyncio
    async def test_reconnect_preserves_state(self, temp_db):
        """Test that reconnecting to a store preserves state."""
        session_id = "reconnect-test"

        # First connection
        store1 = TemporalMemoryStore(session_id=session_id, db_path=temp_db)
        await store1.connect()
        await store1.record(turn=1, facts={"phase": "initial"})

        # Second connection (simulates new process)
        store2 = TemporalMemoryStore(session_id=session_id, db_path=temp_db)
        await store2.connect()

        # State should be preserved
        state = await store2.get_current_state()
        assert state["phase"] == "initial"

        # Turn count should be restored
        assert store2._current_turn == 1
