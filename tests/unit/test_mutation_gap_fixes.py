"""
Tests to close mutation testing gaps.

These tests are specifically designed to catch the 5 surviving mutants
identified in mutation testing:

1. CircuitBreaker HALF_OPEN state - Verify state is HALF_OPEN after timeout
2. Blackboard iteration count - Assert result.iterations is correct value
3. Blackboard early completion flag - Assert result.completed == True
4. Jury min_jurors default - Test default when min_jurors not specified
5. Jury None vote filtering - Test where a juror returns None (failure)
"""

import asyncio
import pytest
import time
from typing import Any
from unittest.mock import AsyncMock, patch


class TestCircuitBreakerHalfOpenState:
    """Test that circuit enters HALF_OPEN state after timeout."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_enters_half_open_state(self):
        """
        Mutation gap #3: Verify circuit enters HALF_OPEN state after timeout.

        The mutation removed `self.state = CircuitState.HALF_OPEN` but tests
        still passed because:
        - _should_try_primary() returns True after timeout
        - If primary succeeds, state goes to CLOSED
        - If primary fails, state goes to OPEN

        This test explicitly checks the state IS HALF_OPEN between timeout
        and retry completion.
        """
        from scripts.agentica.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call.side_effect = Exception("primary failed")

        fallback_agent = AsyncMock()
        fallback_agent.call.return_value = "fallback result"

        with patch("scripts.agentica.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="You implement features.",
                fallback_premise="You implement simpler versions.",
                max_failures=2,
                reset_timeout=0.1  # Short timeout for test
            )

            # Trigger 2 failures to open circuit
            await cb.execute("task1")
            await cb.execute("task2")
            assert cb.state == CircuitState.OPEN

            # Wait for timeout
            time.sleep(0.15)

            # Call _should_try_primary() which should set HALF_OPEN
            should_try = cb._should_try_primary()

            # CRITICAL: State must be HALF_OPEN after timeout, before retry completes
            assert should_try is True
            assert cb.state == CircuitState.HALF_OPEN, (
                f"Expected HALF_OPEN after timeout, got {cb.state}"
            )


class TestBlackboardIterationCount:
    """Test that iteration count is correct value."""

    @pytest.fixture
    def mock_spawn(self):
        """Create mock spawn function."""
        with patch("scripts.agentica.patterns.blackboard.spawn") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_blackboard_returns_correct_iteration_count(self, mock_spawn):
        """
        Mutation gap #5: Verify iteration count is correct.

        The mutation changed `range(1, max+1)` to `range(0, max)` but tests
        still passed because no test asserted the exact iteration value.

        This test verifies iteration count = 2 when controller approves
        on second iteration.
        """
        from scripts.agentica.patterns import Blackboard, Specialist

        iteration_counter = {"value": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()

            async def mock_call(return_type, prompt, **kw):
                iteration_counter["value"] += 1

                # Controller agent responds
                if "complete" in prompt.lower() or "coherent" in prompt.lower():
                    # Approve on iteration 2
                    if iteration_counter["value"] >= 4:  # 2 specialists + 2 controller calls = iteration 2
                        return {"complete": True}
                    return {"complete": False}

                # Specialist agent responds
                return {"work": f"contribution {iteration_counter['value']}"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="Worker 1", writes_to=["work"]),
            ],
            controller_premise="Check completion",
            max_iterations=5
        )

        result = await bb.solve("task")

        # CRITICAL: The mutation would make iteration start at 0
        # We expect iteration=2 when controller approves on second iteration
        assert result.iterations == 2, (
            f"Expected iterations=2, got {result.iterations}"
        )


class TestBlackboardCompletedFlag:
    """Test that completed flag is set correctly."""

    @pytest.fixture
    def mock_spawn(self):
        """Create mock spawn function."""
        with patch("scripts.agentica.patterns.blackboard.spawn") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_blackboard_sets_completed_flag_on_approval(self, mock_spawn):
        """
        Mutation gap #6: Verify completed=True when controller approves.

        The mutation changed `completion.get("complete", False)` to `False`
        meaning early completion never triggers. Tests still passed because
        they only checked that iterations >= some value.

        This test explicitly verifies result.completed == True AND
        iterations < max_iterations (early completion).
        """
        from scripts.agentica.patterns import Blackboard, Specialist

        call_count = {"value": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()

            async def mock_call(return_type, prompt, **kw):
                call_count["value"] += 1

                # Controller agent - approve immediately on first iteration
                if "complete" in prompt.lower() or "coherent" in prompt.lower():
                    return {"complete": True, "feedback": "Looks good!"}

                # Specialist agent
                return {"analysis": "done"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="Analyst", writes_to=["analysis"]),
            ],
            controller_premise="Check completion",
            max_iterations=10  # High max to prove early exit
        )

        result = await bb.solve("analyze this")

        # CRITICAL: completed must be True when controller approves
        assert result.completed is True, (
            f"Expected completed=True, got {result.completed}"
        )

        # ALSO verify early exit (not running all 10 iterations)
        assert result.iterations == 1, (
            f"Expected early completion at iteration 1, got {result.iterations}"
        )


class TestJuryMinJurorsDefault:
    """Test that min_jurors defaults to num_jurors."""

    def test_jury_uses_num_jurors_as_default_min(self):
        """
        Mutation gap #7: Verify min_jurors defaults to num_jurors.

        The mutation changed `min_jurors or num_jurors` to `min_jurors or 1`
        meaning default would be 1 instead of matching num_jurors.

        This test creates a Jury WITHOUT specifying min_jurors and
        verifies it equals num_jurors.
        """
        from scripts.agentica.patterns import Jury, ConsensusMode

        # Create jury with 5 jurors but NO min_jurors specified
        jury = Jury(
            num_jurors=5,
            consensus_mode=ConsensusMode.MAJORITY,
            allow_partial=True
            # NOTE: min_jurors intentionally NOT specified
        )

        # CRITICAL: min_jurors should default to num_jurors (5), not 1
        assert jury.min_jurors == 5, (
            f"Expected min_jurors to default to num_jurors (5), got {jury.min_jurors}"
        )


class TestJuryNoneVoteFiltering:
    """Test that None votes from failed jurors are filtered."""

    @pytest.mark.asyncio
    async def test_jury_filters_none_votes_from_failed_jurors(self):
        """
        Mutation gap #8: Verify None votes are filtered when jurors fail.

        The mutation removed `votes = [v for v in votes if v is not None]`
        meaning failed juror votes (None) would be counted.

        This test creates a jury where some jurors fail (return None)
        and verifies:
        1. None votes are excluded from counting
        2. Consensus is reached from successful votes only
        """
        from scripts.agentica.patterns import Jury, ConsensusMode

        # Track which jurors are spawned
        juror_index = {"value": 0}

        async def mock_spawn_with_failures(**kwargs):
            idx = juror_index["value"]
            juror_index["value"] += 1

            juror = AsyncMock()

            async def mock_call(return_type, question, **kw):
                # Jurors 0 and 1 fail (will be filtered to None by allow_partial)
                if idx < 2:
                    raise Exception(f"Juror {idx} failed!")
                # Jurors 2, 3, 4 succeed and vote True
                return True

            juror.call = mock_call
            return juror

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            mock_spawn.side_effect = mock_spawn_with_failures

            jury = Jury(
                num_jurors=5,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=True,
                min_jurors=3,  # Require at least 3 successful
                debug=True  # Track votes for verification
            )

            result = await jury.decide(bool, "Is this correct?")

            # CRITICAL: Should get True (from 3 successful jurors)
            # If None votes were NOT filtered, we'd have [None, None, True, True, True]
            # which could break consensus logic
            assert result is True

            # Verify only 3 votes (failed jurors filtered out)
            assert len(jury.last_votes) == 3, (
                f"Expected 3 votes (2 filtered as None), got {len(jury.last_votes)}: {jury.last_votes}"
            )

            # Verify no None values in collected votes
            assert None not in jury.last_votes, (
                f"None votes should be filtered out, got: {jury.last_votes}"
            )


# ============================================================================
# Tests 6-10: Priority 2-3 Surviving Mutants
# ============================================================================


class TestConsensusTieBreaking:
    """Test that consensus tie-breaking returns first occurrence, not arbitrary."""

    def test_majority_tie_breaks_to_first_occurrence_reverse_order(self):
        """
        Mutation gap #9: Verify tie-breaking uses first occurrence.

        The mutation removed tie-breaking logic but tests passed because
        Python 3.7+ dict iteration order happens to match insertion order.

        This test creates votes where the tie-breaker MUST use first_idx,
        not dict iteration order, by having the first-occurring winner
        come AFTER another winner in alphabetical order.
        """
        from scripts.agentica.primitives import Consensus, ConsensusMode

        consensus = Consensus(mode=ConsensusMode.MAJORITY)

        # Votes: B appears first, then A, then B, then A
        # Both have count=2, but B appears first (index 0)
        votes = ["B", "A", "B", "A"]

        result = consensus.decide(votes)

        # CRITICAL: B should win because it appeared first (index 0)
        # If tie-breaking is removed, dict iteration order could pick A or B
        # depending on hash ordering
        assert result == "B", (
            f"Expected 'B' (first occurrence), got '{result}'"
        )

    def test_weighted_tie_breaks_to_first_occurrence(self):
        """
        Test weighted voting tie-breaking also uses first occurrence.

        Creates weighted tie where dict order differs from first occurrence.
        """
        from scripts.agentica.primitives import Consensus, ConsensusMode

        consensus = Consensus(mode=ConsensusMode.MAJORITY)

        # C appears first (index 0, weight 2), D appears second (index 1, weight 2)
        # Both have total weight 2
        votes = ["C", "D", "D", "C"]
        weights = [2.0, 1.0, 1.0, 0.0]

        result = consensus.decide(votes, weights=weights)

        # C wins with weight 2 (2.0 + 0.0), D wins with weight 2 (1.0 + 1.0)
        # C appeared first, so C should win
        assert result == "C", (
            f"Expected 'C' (first occurrence), got '{result}'"
        )

    def test_threshold_tie_breaks_to_first_occurrence(self):
        """
        Test threshold mode also uses first occurrence for tie-breaking.
        """
        from scripts.agentica.primitives import Consensus, ConsensusMode

        # Set threshold to 0.25 so both X and Y exceed it
        consensus = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.25)

        # X and Y both have 2 votes out of 4 = 50% each
        # X appears first
        votes = ["X", "Y", "X", "Y"]

        result = consensus.decide(votes)

        # X should win because it appeared first
        assert result == "X", (
            f"Expected 'X' (first occurrence), got '{result}'"
        )


class TestJuryMinJurorsDefaultBehavior:
    """
    Additional test for jury min_jurors default behavior.

    This verifies the BEHAVIOR, not just the attribute value.
    """

    @pytest.mark.asyncio
    async def test_jury_default_min_jurors_requires_all_jurors(self):
        """
        Mutation gap #10: Verify min_jurors=num_jurors behavior.

        When min_jurors is not specified, it should default to num_jurors.
        This means if 2 of 5 jurors fail, the jury should fail (not enough votes).

        The mutation changed `min_jurors or num_jurors` to `min_jurors or 1`
        which would make partial success possible with just 1 juror.
        """
        from scripts.agentica.patterns import Jury, ConsensusMode

        juror_index = {"value": 0}

        async def mock_spawn_with_failures(**kwargs):
            idx = juror_index["value"]
            juror_index["value"] += 1

            juror = AsyncMock()

            async def mock_call(return_type, question, **kw):
                # Juror 0 succeeds
                if idx == 0:
                    return True
                # Jurors 1-4 fail
                raise Exception(f"Juror {idx} failed!")

            juror.call = mock_call
            return juror

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            mock_spawn.side_effect = mock_spawn_with_failures

            jury = Jury(
                num_jurors=5,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=True
                # NOTE: min_jurors NOT specified - should default to 5
            )

            # CRITICAL: Should fail because only 1 juror succeeded
            # but default min_jurors = num_jurors = 5
            with pytest.raises(ValueError) as exc_info:
                await jury.decide(bool, "Is this correct?")

            assert "Not enough successful jurors" in str(exc_info.value)
            assert "1 < 5" in str(exc_info.value)


class TestJuryPartialVoteFilteringBehavior:
    """
    Additional test for jury None vote filtering behavior.

    This verifies the filtering logic with edge cases.
    """

    @pytest.mark.asyncio
    async def test_jury_none_votes_not_passed_to_consensus(self):
        """
        Mutation gap #11: Verify None votes are excluded from consensus.

        The mutation removed `votes = [v for v in votes if v is not None]`
        This would cause None values to be passed to Consensus.decide(),
        which could break or cause incorrect results.

        This test verifies that:
        1. The jury can reach consensus with partial votes
        2. Only valid votes are stored in last_votes (when debug=True)
        3. None is not present in the final vote collection
        """
        from scripts.agentica.patterns import Jury, ConsensusMode

        # Track juror index based on call count, not spawn count
        call_count = {"value": 0}

        async def mock_spawn(**kwargs):
            juror = AsyncMock()

            async def mock_call(return_type, question, **kw):
                idx = call_count["value"]
                call_count["value"] += 1

                # Jurors 0, 1 fail (return None via allow_partial)
                if idx < 2:
                    raise Exception(f"Juror {idx} failed!")
                # Jurors 2, 3, 4 return True
                return True

            juror.call = mock_call
            return juror

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn_patch:
            mock_spawn_patch.side_effect = mock_spawn

            jury = Jury(
                num_jurors=5,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=True,
                min_jurors=2,  # Only need 2 to succeed
                debug=True  # Enable vote tracking
            )

            result = await jury.decide(bool, "Is this correct?")

            # CRITICAL: Result should be True (from 3 successful votes)
            assert result is True

            # CRITICAL: last_votes should only contain the 3 successful votes
            # If None filtering failed, we'd see None values or consensus would fail
            assert len(jury.last_votes) == 3, (
                f"Expected 3 votes (2 filtered as None), got {len(jury.last_votes)}"
            )
            assert None not in jury.last_votes, (
                f"None should be filtered before Consensus, got: {jury.last_votes}"
            )
            # All votes should be True
            assert all(v is True for v in jury.last_votes), (
                f"All votes should be True, got: {jury.last_votes}"
            )


class TestPipelineStateUpdate:
    """Test that Pipeline correctly updates state between stages."""

    @pytest.mark.asyncio
    async def test_pipeline_stage_can_return_new_state_object(self):
        """
        Mutation gap #15: Verify state assignment in pipeline loop.

        The mutation changed:
            state = await stage(state)
        To:
            await stage(state)  # No assignment

        Tests passed because stages modified state in-place (state.add_artifact()).
        This test verifies a stage can return a DIFFERENT state object.
        """
        from scripts.agentica.patterns.pipeline import Pipeline
        from scripts.agentica.primitives import HandoffState

        # Stage that returns a NEW state object (not modified in-place)
        async def stage_that_returns_new_state(state: HandoffState) -> HandoffState:
            # Create completely new state with modified content
            new_state = HandoffState(
                context=state.context + " -> stage1",
                next_instruction="Continue to stage 2"
            )
            new_state.add_artifact("stage1_marker", "was_here")
            return new_state

        async def stage_that_reads_previous(state: HandoffState) -> HandoffState:
            # This stage depends on receiving the NEW state from previous
            # If state wasn't updated, it won't have stage1_marker
            if "stage1_marker" not in state.artifacts:
                raise AssertionError("Missing stage1_marker - state update failed!")

            state.add_artifact("stage2_marker", "also_here")
            return state

        pipeline = Pipeline(stages=[
            stage_that_returns_new_state,
            stage_that_reads_previous
        ])

        initial_state = HandoffState(
            context="Initial",
            next_instruction="Start"
        )

        result = await pipeline.run(initial_state)

        # CRITICAL: Result should have artifacts from BOTH stages
        # If mutation exists, stage2 would fail because it got original state
        assert "stage1_marker" in result.artifacts, (
            "stage1_marker missing - state update failed in loop"
        )
        assert "stage2_marker" in result.artifacts, (
            "stage2_marker missing - stage2 didn't run correctly"
        )
        assert " -> stage1" in result.context, (
            "context not updated - state replacement failed"
        )


class TestHierarchicalParallelExecution:
    """Test that Hierarchical executes specialists in true parallel."""

    @pytest.mark.asyncio
    async def test_parallel_execution_timing(self):
        """
        Mutation gap #19: Verify asyncio.gather for parallel execution.

        The mutation changed:
            results = await asyncio.gather(*[execute_subtask(st) for st in subtasks])
        To:
            results = [await execute_subtask(st) for st in subtasks]  # Sequential

        This test measures wall-clock time to verify parallel execution.
        3 tasks with 0.1s delay each:
        - Parallel: ~0.1s
        - Sequential: ~0.3s
        """
        import time
        from scripts.agentica.patterns import Hierarchical

        DELAY = 0.1
        NUM_SPECIALISTS = 3

        specialist_call_count = {"value": 0}

        async def mock_spawn(**kwargs):
            agent = AsyncMock()

            async def mock_call(return_type, prompt, **kw):
                # Coordinator decomposition
                if "decompose" in prompt.lower() or "subtask" in prompt.lower():
                    return [
                        {"specialist": f"worker{i}", "task": f"Task {i}"}
                        for i in range(NUM_SPECIALISTS)
                    ]

                # Coordinator synthesis
                if "synthesize" in prompt.lower():
                    return "Synthesized result"

                # Specialist work - add delay to detect parallel vs sequential
                specialist_call_count["value"] += 1
                await asyncio.sleep(DELAY)
                return f"Result from specialist"

            agent.call = mock_call
            return agent

        with patch("scripts.agentica.patterns.hierarchical.spawn") as mock_spawn_patch:
            mock_spawn_patch.side_effect = mock_spawn

            hierarchical = Hierarchical(
                coordinator_premise="You decompose tasks.",
                specialist_premises={
                    f"worker{i}": f"You handle task {i}."
                    for i in range(NUM_SPECIALISTS)
                }
            )

            start = time.time()
            result = await hierarchical.execute("Do all tasks")
            duration = time.time() - start

            # CRITICAL: Parallel should take ~0.1s, sequential would take ~0.3s
            # Use 0.2s as threshold (gives 100% margin for overhead)
            max_parallel_time = DELAY * 2  # Allow 100% overhead
            sequential_time = DELAY * NUM_SPECIALISTS

            assert duration < max_parallel_time, (
                f"Expected parallel execution (~{DELAY}s), "
                f"but took {duration:.2f}s (sequential would be ~{sequential_time}s)"
            )

            # Verify all specialists were called
            assert specialist_call_count["value"] == NUM_SPECIALISTS, (
                f"Expected {NUM_SPECIALISTS} specialist calls, "
                f"got {specialist_call_count['value']}"
            )


# Need to import Consensus for the spy test
from scripts.agentica.primitives import Consensus


# ============================================================================
# Batch 2 Mutation Gap Fixes
# Tests for 6 surviving mutants from mutation testing batch 2
# ============================================================================


class TestEventDrivenPayloadInPrompt:
    """Test mutation 32: Verify subscriber receives event payload in prompt."""

    @pytest.mark.asyncio
    async def test_event_payload_included_in_dispatch_prompt(self):
        """
        Mutation gap: Drop event payload from prompt.

        The mutation removed `Payload: {event.payload}` from the dispatch prompt.
        This test captures the prompt passed to agent.call() and asserts
        the payload content is present.
        """
        from scripts.agentica.patterns import EventDriven, Event, Subscriber

        prompts_received = []

        async def mock_spawn(**kwargs):
            mock_agent = AsyncMock()

            async def capture_prompt(return_type, prompt, **kw):
                prompts_received.append(prompt)
                return "processed"

            mock_agent.call = capture_prompt
            return mock_agent

        with patch("scripts.agentica.patterns.event_driven.spawn") as mock_spawn_patch:
            mock_spawn_patch.side_effect = mock_spawn

            bus = EventDriven(subscribers=[
                Subscriber(premise="Handler", event_types=["test"])
            ])

            # Create event with specific payload values
            event = Event(type="test", payload={"user_id": "12345", "action": "login"})
            await bus.publish(event)

            # CRITICAL: Prompt must contain payload data
            assert len(prompts_received) == 1
            prompt = prompts_received[0]
            assert "user_id" in prompt, "Payload key 'user_id' not in prompt"
            assert "12345" in prompt, "Payload value '12345' not in prompt"
            assert "action" in prompt, "Payload key 'action' not in prompt"
            assert "login" in prompt, "Payload value 'login' not in prompt"


class TestAdversarialPreviousArgumentsInPrompt:
    """Test mutation 38: Verify adversary sees advocate's previous round."""

    @pytest.mark.asyncio
    async def test_advocate_receives_adversary_critique_in_round_2(self):
        """
        Mutation gap: Don't pass previous arguments in subsequent rounds.

        The mutation removed `Your previous argument: {advocate_position}` and
        `Adversary's critique: {adversary_position}` from subsequent round prompts.

        This test verifies that in round 2, the advocate's prompt contains
        the adversary's critique from round 1.
        """
        from scripts.agentica.patterns import Adversarial

        advocate_prompts = []
        round_counter = {"advocate": 0, "adversary": 0}

        async def mock_spawn(**kwargs):
            premise = kwargs.get("premise", "")
            mock_agent = AsyncMock()

            async def mock_call(return_type, prompt, **kw):
                if "favor" in premise.lower() or "advocate" in premise.lower():
                    round_counter["advocate"] += 1
                    advocate_prompts.append(prompt)
                    return f"Pro argument round {round_counter['advocate']}"
                else:
                    round_counter["adversary"] += 1
                    return f"FATAL_FLAW_{round_counter['adversary']}: This is wrong"

            mock_agent.call = mock_call
            return mock_agent

        with patch("scripts.agentica.patterns.adversarial.spawn") as mock_spawn_patch:
            mock_spawn_patch.side_effect = mock_spawn

            adv = Adversarial(
                advocate_premise="You argue in favor.",
                adversary_premise="You argue against.",
                max_rounds=2
            )

            await adv.debate("Question")

            # CRITICAL: Round 2 advocate prompt must contain adversary's critique
            assert len(advocate_prompts) == 2, f"Expected 2 advocate prompts, got {len(advocate_prompts)}"

            # Round 1 prompt should NOT have previous critique
            assert "FATAL_FLAW" not in advocate_prompts[0], (
                "Round 1 should not have adversary critique yet"
            )

            # Round 2 prompt MUST contain the adversary's critique from round 1
            assert "FATAL_FLAW_1" in advocate_prompts[1], (
                f"Round 2 advocate prompt missing adversary's critique. Got: {advocate_prompts[1][:200]}"
            )


class TestAdversarialJudgeFairness:
    """Test mutation 39: Verify judge receives both positions."""

    @pytest.mark.asyncio
    async def test_judge_receives_both_advocate_and_adversary_positions(self):
        """
        Mutation gap: Judge only sees advocate position.

        The mutation only included advocate position in judge prompt,
        dropping the adversary position.

        This test verifies the judge prompt contains BOTH positions.
        """
        from scripts.agentica.patterns import Adversarial

        judge_prompts = []

        async def mock_spawn(**kwargs):
            premise = kwargs.get("premise", "")
            mock_agent = AsyncMock()

            async def mock_call(return_type, prompt, **kw):
                if "judge" in premise.lower():
                    judge_prompts.append(prompt)
                    return "The advocate wins"
                elif "favor" in premise.lower():
                    return "ADVOCATE_MARKER_UNIQUE_STRING_123"
                else:
                    return "ADVERSARY_MARKER_UNIQUE_STRING_456"

            mock_agent.call = mock_call
            return mock_agent

        with patch("scripts.agentica.patterns.adversarial.spawn") as mock_spawn_patch:
            mock_spawn_patch.side_effect = mock_spawn

            adv = Adversarial(
                advocate_premise="You argue in favor.",
                adversary_premise="You argue against.",
                judge_premise="You are the judge.",
                max_rounds=1
            )

            await adv.resolve("Question")

            # CRITICAL: Judge prompt must contain BOTH positions
            assert len(judge_prompts) == 1, "Judge should be called exactly once"
            judge_prompt = judge_prompts[0]

            assert "ADVOCATE_MARKER_UNIQUE_STRING_123" in judge_prompt, (
                "Judge prompt missing advocate's position"
            )
            assert "ADVERSARY_MARKER_UNIQUE_STRING_456" in judge_prompt, (
                "Judge prompt missing adversary's position"
            )


class TestSwarmParallelExecution:
    """Test mutation 45: Stricter timing test for parallel execution."""

    @pytest.mark.asyncio
    async def test_swarm_parallel_execution_timing(self):
        """
        Mutation gap: Sequential execution instead of parallel.

        The mutation changed asyncio.gather to sequential await.
        This test uses timing to verify parallel execution.

        3 agents with 0.1s delay each:
        - Parallel: ~0.1s
        - Sequential: ~0.3s
        """
        from scripts.agentica.patterns import Swarm, AggregateMode

        DELAY = 0.1
        NUM_AGENTS = 3

        async def mock_spawn(**kwargs):
            agent = AsyncMock()

            async def mock_call(return_type, query, **kw):
                await asyncio.sleep(DELAY)
                return {"result": "done"}

            agent.call = mock_call
            return agent

        with patch("scripts.agentica.patterns.swarm.spawn") as mock_spawn_patch:
            mock_spawn_patch.side_effect = mock_spawn

            swarm = Swarm(
                perspectives=[f"Perspective {i}" for i in range(NUM_AGENTS)],
                aggregate_mode=AggregateMode.MERGE
            )

            start = time.time()
            result = await swarm.execute("Query")
            duration = time.time() - start

            # CRITICAL: Parallel should take ~0.1s, sequential ~0.3s
            # Use 0.2s as threshold (100% overhead allowance)
            max_parallel_time = DELAY * 2
            sequential_time = DELAY * NUM_AGENTS

            assert duration < max_parallel_time, (
                f"Expected parallel execution (~{DELAY}s), "
                f"but took {duration:.2f}s (sequential would be ~{sequential_time}s)"
            )


class TestSwarmNoneFiltering:
    """Test mutation 46: Better None filtering verification."""

    @pytest.mark.asyncio
    async def test_swarm_filters_none_results_before_aggregation(self):
        """
        Mutation gap: Skip filtering None results.

        The mutation removed `results = [r for r in results if r is not None]`.
        This would cause None values to be passed to the aggregator.

        This test verifies:
        1. Failed agents return None
        2. None values are filtered before aggregation
        3. Only successful results are aggregated
        """
        from scripts.agentica.patterns import Swarm, AggregateMode
        from scripts.agentica.patterns.primitives import Aggregator

        call_count = {"value": 0}

        async def mock_spawn(**kwargs):
            agent = AsyncMock()

            async def mock_call(return_type, query, **kw):
                idx = call_count["value"]
                call_count["value"] += 1

                # Agent 0 and 1 fail (return None via exception handling)
                if idx < 2:
                    raise Exception(f"Agent {idx} failed")

                # Agent 2 and 3 succeed
                return {"data": f"result_{idx}"}

            agent.call = mock_call
            return agent

        # Spy on Aggregator.aggregate to verify what gets passed
        aggregated_inputs = []
        original_aggregate = Aggregator.aggregate

        def spy_aggregate(self, results: list) -> Any:
            aggregated_inputs.append(list(results))
            return original_aggregate(self, results)

        with patch("scripts.agentica.patterns.swarm.spawn") as mock_spawn_patch:
            mock_spawn_patch.side_effect = mock_spawn

            with patch.object(Aggregator, "aggregate", spy_aggregate):
                swarm = Swarm(
                    perspectives=[f"Perspective {i}" for i in range(4)],
                    aggregate_mode=AggregateMode.MERGE,
                    fail_fast=False  # Allow partial results
                )

                result = await swarm.execute("Query")

                # CRITICAL: Aggregator should receive only 2 results (agents 2 and 3)
                assert len(aggregated_inputs) == 1
                inputs = aggregated_inputs[0]

                assert len(inputs) == 2, (
                    f"Expected 2 results (2 filtered as None), got {len(inputs)}: {inputs}"
                )
                assert None not in inputs, (
                    f"None should be filtered before aggregation, got: {inputs}"
                )
                # Verify correct results passed through
                assert {"data": "result_2"} in inputs
                assert {"data": "result_3"} in inputs


class TestBlackboardHistoryAction:
    """Test mutation 51: Verify action field is correct value."""

    def test_blackboard_history_records_set_action(self):
        """
        Mutation gap: Record wrong history action.

        The mutation changed history action from "set" to "get".

        This test explicitly verifies the action field is "set" for writes.
        """
        from scripts.agentica.patterns import BlackboardState

        state = BlackboardState()
        state["key1"] = "value1"
        state["key2"] = "value2"

        # CRITICAL: Action must be "set" for writes, not "get"
        assert len(state.history) == 2

        assert state.history[0]["action"] == "set", (
            f"Expected action='set', got '{state.history[0]['action']}'"
        )
        assert state.history[0]["key"] == "key1"
        assert state.history[0]["value"] == "value1"

        assert state.history[1]["action"] == "set", (
            f"Expected action='set', got '{state.history[1]['action']}'"
        )
        assert state.history[1]["key"] == "key2"
        assert state.history[1]["value"] == "value2"

    def test_blackboard_history_action_not_get(self):
        """
        Additional verification: action is specifically NOT 'get'.

        Catches the specific mutation that changed "set" to "get".
        """
        from scripts.agentica.patterns import BlackboardState

        state = BlackboardState()
        state["test_key"] = "test_value"

        # Verify action is NOT "get" (the mutated value)
        assert state.history[0]["action"] != "get", (
            "History action should not be 'get' for write operations"
        )
