"""CRUD Tests for Batch 1 Patterns: Pipeline, Jury, DependencySwarm, CircuitBreaker.

Level 3: Pattern Structure Tests - Mocked spawn, deterministic responses
Level 4: Prompt Reliability Tests - Verify prompts contain expected elements
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch


# ============================================================================
# Pipeline Pattern Tests
# ============================================================================


class TestPipelineSequentialExecution:
    """Test sequential execution of pipeline stages."""

    @pytest.mark.asyncio
    async def test_stages_execute_in_order(self):
        """Verify stages A->B->C execute sequentially."""
        from scripts.agentica.patterns import Pipeline
        from scripts.agentica.patterns.primitives import HandoffState

        execution_order = []

        async def stage_a(state: HandoffState) -> HandoffState:
            execution_order.append("A")
            state.add_artifact("stage_a_output", "result_a")
            return state

        async def stage_b(state: HandoffState) -> HandoffState:
            execution_order.append("B")
            state.add_artifact("stage_b_output", "result_b")
            return state

        async def stage_c(state: HandoffState) -> HandoffState:
            execution_order.append("C")
            state.add_artifact("stage_c_output", "result_c")
            return state

        pipeline = Pipeline(stages=[stage_a, stage_b, stage_c])
        initial_state = HandoffState(context="Test", next_instruction="Start")

        final_state = await pipeline.run(initial_state)

        assert execution_order == ["A", "B", "C"]
        assert "stage_a_output" in final_state.artifacts
        assert "stage_b_output" in final_state.artifacts
        assert "stage_c_output" in final_state.artifacts

    @pytest.mark.asyncio
    async def test_single_stage_works(self):
        """Verify single-stage degenerate case works."""
        from scripts.agentica.patterns import Pipeline
        from scripts.agentica.patterns.primitives import HandoffState

        async def only_stage(state: HandoffState) -> HandoffState:
            state.add_artifact("result", "done")
            return state

        pipeline = Pipeline(stages=[only_stage])
        initial_state = HandoffState(context="Single stage", next_instruction="Go")

        result = await pipeline.run(initial_state)

        assert result.artifacts["result"] == "done"


class TestPipelineErrorHandling:
    """Test error handling in pipeline execution."""

    @pytest.mark.asyncio
    async def test_stage_failure_stops_pipeline(self):
        """Verify failing stage stops execution and propagates error."""
        from scripts.agentica.patterns import Pipeline
        from scripts.agentica.patterns.primitives import HandoffState

        stage_3_executed = False

        async def stage_1(state: HandoffState) -> HandoffState:
            state.add_artifact("stage_1", "ok")
            return state

        async def failing_stage(state: HandoffState) -> HandoffState:
            raise ValueError("Stage 2 failed")

        async def stage_3(state: HandoffState) -> HandoffState:
            nonlocal stage_3_executed
            stage_3_executed = True
            state.add_artifact("stage_3", "should not see")
            return state

        pipeline = Pipeline(stages=[stage_1, failing_stage, stage_3])
        initial_state = HandoffState(context="Failure test", next_instruction="Start")

        with pytest.raises(ValueError, match="Stage 2 failed"):
            await pipeline.run(initial_state)

        assert stage_3_executed is False


class TestPipelineValidation:
    """Test pipeline input validation."""

    def test_empty_stages_raises(self):
        """Verify empty stages list raises ValueError."""
        from scripts.agentica.patterns import Pipeline

        with pytest.raises(ValueError, match="at least one stage"):
            Pipeline(stages=[])


class TestPipelinePromptReliability:
    """Test state passing between stages (prompt reliability)."""

    @pytest.mark.asyncio
    async def test_state_passed_between_stages(self):
        """Verify HandoffState flows correctly between stages."""
        from scripts.agentica.patterns import Pipeline
        from scripts.agentica.patterns.primitives import HandoffState

        received_artifacts = {}

        async def stage_a(state: HandoffState) -> HandoffState:
            state.add_artifact("data_from_a", {"key": "value"})
            state.update_instruction("Go to B")
            return state

        async def stage_b(state: HandoffState) -> HandoffState:
            # Capture what stage B received
            received_artifacts["data_from_a"] = state.artifacts.get("data_from_a")
            received_artifacts["instruction"] = state.next_instruction
            state.add_artifact("data_from_b", "processed")
            return state

        pipeline = Pipeline(stages=[stage_a, stage_b])
        initial_state = HandoffState(context="Context test", next_instruction="Start")

        await pipeline.run(initial_state)

        assert received_artifacts["data_from_a"] == {"key": "value"}
        assert received_artifacts["instruction"] == "Go to B"


# ============================================================================
# Jury/Voting Pattern Tests
# ============================================================================


def create_jury_mock(votes):
    """Helper to create mock spawn that returns jurors with predetermined votes."""
    votes_copy = list(votes)

    async def mock_spawn(*args, **kwargs):
        juror = AsyncMock()
        if votes_copy:
            vote = votes_copy.pop(0)
            juror.call = AsyncMock(return_value=vote)
        else:
            juror.call = AsyncMock(return_value=True)
        return juror
    return mock_spawn


class TestJuryVotingMechanics:
    """Test jury voting mechanics."""

    @pytest.mark.asyncio
    async def test_majority_voting(self):
        """3 jurors, 2 agree -> majority wins."""
        from scripts.agentica.patterns import Jury, ConsensusMode

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [False, False, True]
            mock_spawn.side_effect = create_jury_mock(votes)

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                model="test-model"
            )

            result = await jury.decide(bool, "Is the Earth flat?")

            assert result is False
            assert mock_spawn.call_count == 3

    @pytest.mark.asyncio
    async def test_unanimous_fails_on_disagreement(self):
        """UNANIMOUS mode raises ConsensusNotReachedError on split vote."""
        from scripts.agentica.patterns import Jury, ConsensusMode, ConsensusNotReachedError

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = ["Python", "Rust", "Go"]
            mock_spawn.side_effect = create_jury_mock(votes)

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.UNANIMOUS,
                model="test-model"
            )

            with pytest.raises(ConsensusNotReachedError):
                await jury.decide(str, "What is the best programming language?")


class TestJuryValidation:
    """Test jury input validation."""

    def test_threshold_requires_threshold_param(self):
        """THRESHOLD mode without threshold param raises ValueError."""
        from scripts.agentica.patterns import Jury, ConsensusMode

        with pytest.raises(ValueError, match="threshold"):
            Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.THRESHOLD
            )

    def test_threshold_outside_range_raises(self):
        """Threshold outside 0-1 range raises ValueError."""
        from scripts.agentica.patterns import Jury, ConsensusMode

        with pytest.raises(ValueError, match="between 0 and 1"):
            Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.THRESHOLD,
                threshold=1.5
            )

    def test_weights_length_mismatch(self):
        """Weights list length mismatch raises ValueError."""
        from scripts.agentica.patterns import Jury, ConsensusMode

        with pytest.raises(ValueError, match="weights.*same length"):
            Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                weights=[1, 2]  # Only 2 weights for 3 jurors
            )


class TestJuryPromptReliability:
    """Test prompt reliability for jury pattern."""

    @pytest.mark.asyncio
    async def test_jurors_receive_unique_premises(self):
        """Each juror receives unique premise when using premises=[]."""
        from scripts.agentica.patterns import Jury, ConsensusMode

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            premises_received = []

            async def track_premises(**kwargs):
                premises_received.append(kwargs.get("premise"))
                juror = AsyncMock()
                juror.call = AsyncMock(return_value=True)
                return juror

            mock_spawn.side_effect = track_premises

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                premises=[
                    "You are a security expert.",
                    "You are a performance expert.",
                    "You are a readability expert."
                ],
                model="test-model"
            )

            await jury.decide(bool, "Is this code acceptable?")

            assert len(premises_received) == 3
            assert "security expert" in premises_received[0]
            assert "performance expert" in premises_received[1]
            assert "readability expert" in premises_received[2]


# ============================================================================
# DependencySwarm Pattern Tests
# ============================================================================


class TestDependencySwarmExecution:
    """Test dependency swarm execution."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_independent_tasks_parallel(self, db):
        """Independent tasks execute in parallel."""
        from scripts.agentica.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        swarm.add_task("A", "Task A")
        swarm.add_task("B", "Task B")
        swarm.add_task("C", "Task C")

        with patch("scripts.agentica.dependency_swarm.tracked_spawn") as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            results = await swarm.execute()

            assert len(results) == 3
            assert mock_spawn.call_count == 3

    @pytest.mark.asyncio
    async def test_dependencies_respected(self, db):
        """A->B->C respects execution order."""
        from scripts.agentica.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        a_id = swarm.add_task("A", "Task A")
        b_id = swarm.add_task("B", "Task B", depends_on=[a_id])
        c_id = swarm.add_task("C", "Task C", depends_on=[b_id])

        with patch("scripts.agentica.dependency_swarm.tracked_spawn") as mock_spawn:
            execution_order = []

            async def track_execution(db, premise, **kwargs):
                agent = AsyncMock()
                async def call_with_tracking(*args, **inner_kwargs):
                    # Extract task name from premise
                    if "\n\n" in premise:
                        original_premise = premise.split("\n\n")[-1]
                    else:
                        original_premise = premise
                    execution_order.append(original_premise)
                    return f"result-{original_premise}"
                agent.call = call_with_tracking
                agent.close = AsyncMock()
                return agent

            mock_spawn.side_effect = track_execution

            await swarm.execute()

            a_idx = execution_order.index("Task A")
            b_idx = execution_order.index("Task B")
            c_idx = execution_order.index("Task C")

            assert a_idx < b_idx < c_idx


class TestDependencySwarmValidation:
    """Test dependency swarm validation."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_cycle_detection(self, db):
        """Cycle detection raises ValueError before any agents spawn."""
        from scripts.agentica.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        a_id = swarm.add_task("A", "Task A")
        b_id = swarm.add_task("B", "Task B", depends_on=[a_id])
        # Create cycle: A depends on B
        swarm.graph.nodes[a_id].depends_on = [b_id]

        with patch("scripts.agentica.dependency_swarm.tracked_spawn") as mock_spawn:
            with pytest.raises(ValueError, match="[Cc]ycle"):
                await swarm.execute()

            mock_spawn.assert_not_called()


class TestDependencySwarmLifecycle:
    """Test agent lifecycle management."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_agents_closed_after_execution(self, db):
        """Agents are closed after successful execution."""
        from scripts.agentica.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        swarm.add_task("A", "Task A")

        with patch("scripts.agentica.dependency_swarm.tracked_spawn") as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            await swarm.execute()

            mock_agent.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_agents_closed_on_failure(self, db):
        """Agents are closed even after task failure."""
        from scripts.agentica.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db, fail_fast=False)
        swarm.add_task("A", "Task A")

        with patch("scripts.agentica.dependency_swarm.tracked_spawn") as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(side_effect=ValueError("Task failed"))
            mock_agent.close = AsyncMock()
            mock_spawn.return_value = mock_agent

            await swarm.execute()

            mock_agent.close.assert_called_once()


class TestDependencySwarmPromptReliability:
    """Test prompt reliability for dependency swarm."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary coordination database."""
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.mark.asyncio
    async def test_dependency_context_injected(self, db):
        """Dependent task receives upstream results in premise."""
        from scripts.agentica.dependency_swarm import DependencySwarm

        swarm = DependencySwarm(db=db)
        a_id = swarm.add_task("A", "Task A")
        swarm.add_task("B", "Task B", depends_on=[a_id])

        with patch("scripts.agentica.dependency_swarm.tracked_spawn") as mock_spawn:
            premises_received = []

            async def track_execution(db, premise, **kwargs):
                premises_received.append(premise)
                agent = AsyncMock()
                agent.call = AsyncMock(return_value="result-A")
                agent.close = AsyncMock()
                return agent

            mock_spawn.side_effect = track_execution

            await swarm.execute()

            assert len(premises_received) == 2
            # Second premise (Task B) should mention Task A's result
            b_premise = premises_received[1]
            assert "Task A" in b_premise or "result-A" in b_premise


# ============================================================================
# CircuitBreaker Pattern Tests
# ============================================================================


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_stays_closed_on_success(self):
        """Circuit stays CLOSED when primary succeeds."""
        from scripts.agentica.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call = AsyncMock(return_value="success")

        fallback_agent = AsyncMock()

        with patch("scripts.agentica.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="Primary agent",
                fallback_premise="Fallback agent",
                max_failures=3,
                reset_timeout=60
            )

            result = await cb.execute("Do something")

            assert result == "success"
            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == 0
            primary_agent.call.assert_called_once()
            fallback_agent.call.assert_not_called()

    @pytest.mark.asyncio
    async def test_opens_after_max_failures(self):
        """Circuit transitions to OPEN after max consecutive failures."""
        from scripts.agentica.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call = AsyncMock(side_effect=Exception("primary failed"))

        fallback_agent = AsyncMock()
        fallback_agent.call = AsyncMock(return_value="fallback result")

        with patch("scripts.agentica.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="Primary agent",
                fallback_premise="Fallback agent",
                max_failures=3,
                reset_timeout=60
            )

            # Trigger 3 failures
            for i in range(3):
                await cb.execute("Do something")

            assert cb.state == CircuitState.OPEN
            assert cb.failure_count == 3


class TestCircuitBreakerFallback:
    """Test fallback agent usage."""

    @pytest.mark.asyncio
    async def test_fallback_used_when_open(self):
        """Fallback agent is used when circuit is OPEN."""
        from scripts.agentica.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call = AsyncMock(side_effect=Exception("primary failed"))

        fallback_agent = AsyncMock()
        fallback_agent.call = AsyncMock(return_value="fallback result")

        with patch("scripts.agentica.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="Primary agent",
                fallback_premise="Fallback agent",
                max_failures=2,
                reset_timeout=60
            )

            # Trigger failures to open circuit
            for _ in range(2):
                await cb.execute("Do something")

            assert cb.state == CircuitState.OPEN

            # Reset mock call count
            primary_agent.call.reset_mock()

            # Execute again - should use fallback
            result = await cb.execute("Another task")

            assert result == "fallback result"
            fallback_agent.call.assert_called()


class TestCircuitBreakerReset:
    """Test circuit breaker reset after timeout."""

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        """HALF_OPEN success transitions circuit back to CLOSED."""
        from scripts.agentica.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        # First 2 calls fail, third succeeds (after timeout)
        primary_agent.call = AsyncMock(side_effect=[
            Exception("fail 1"),
            Exception("fail 2"),
            "success after reset"
        ])

        fallback_agent = AsyncMock()
        fallback_agent.call = AsyncMock(return_value="fallback result")

        with patch("scripts.agentica.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="Primary agent",
                fallback_premise="Fallback agent",
                max_failures=2,
                reset_timeout=0.1  # Short timeout for testing
            )

            # Trigger failures to open circuit
            for _ in range(2):
                await cb.execute("Do something")

            assert cb.state == CircuitState.OPEN

            # Wait for timeout
            await asyncio.sleep(0.15)

            # Next call should try primary in HALF_OPEN state
            result = await cb.execute("Do something")

            assert result == "success after reset"
            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        """HALF_OPEN failure transitions circuit back to OPEN."""
        from scripts.agentica.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call = AsyncMock(side_effect=Exception("always fails"))

        fallback_agent = AsyncMock()
        fallback_agent.call = AsyncMock(return_value="fallback result")

        with patch("scripts.agentica.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="Primary agent",
                fallback_premise="Fallback agent",
                max_failures=2,
                reset_timeout=0.1
            )

            # Trigger failures to open circuit
            for _ in range(2):
                await cb.execute("Do something")

            assert cb.state == CircuitState.OPEN

            # Wait for timeout
            await asyncio.sleep(0.15)

            # Next call tries primary in HALF_OPEN, it fails
            result = await cb.execute("Do something")

            # Should use fallback and reopen circuit
            assert result == "fallback result"
            assert cb.state == CircuitState.OPEN
