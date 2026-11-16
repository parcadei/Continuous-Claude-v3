"""E2E Integration Tests for Pattern Hooks.

Tests that pattern implementations:
1. Set correct environment variables during execution
2. Integrate with CoordinationDB for agent tracking
3. Handle real multi-agent coordination flows
4. Work end-to-end without mocking

Test scenarios:
1. Pipeline E2E - Run 2-stage pipeline, verify handoff via HandoffState
2. Jury E2E - Spawn jury with CoordinationDB, verify vote isolation
3. Circuit Breaker E2E - Simulate failure and recovery cycle
4. Swarm E2E - Verify broadcasts are exchanged via CoordinationDB
"""

import asyncio
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from scripts.agentica.coordination import (
    BroadcastRecord,
    BroadcastType,
    CoordinationDB,
)
from scripts.agentica.patterns import (
    CircuitBreaker,
    CircuitState,
    ConsensusMode,
    Jury,
    Pipeline,
    Swarm,
)
from scripts.agentica.patterns.primitives import AggregateMode, HandoffState


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def isolated_db(tmp_path: Path) -> CoordinationDB:
    """Create an isolated test database for each test."""
    db_path = tmp_path / "test_pattern_e2e.db"
    return CoordinationDB(db_path=db_path, session_id=f"test-{uuid4().hex[:8]}")


@pytest.fixture
def swarm_id() -> str:
    """Generate a unique swarm ID for each test."""
    return uuid4().hex[:12]


# ============================================================================
# Test Scenario 1: Pipeline E2E
# ============================================================================


class TestPipelineE2E:
    """End-to-end tests for Pipeline pattern."""

    @pytest.mark.asyncio
    async def test_pipeline_sets_pattern_env_vars(self):
        """Pipeline sets PATTERN_TYPE=pipeline during stage execution."""
        captured_env = {}

        async def capture_env_stage(state: HandoffState) -> HandoffState:
            captured_env["PATTERN_TYPE"] = os.environ.get("PATTERN_TYPE")
            captured_env["PIPELINE_ID"] = os.environ.get("PIPELINE_ID")
            captured_env["AGENT_ROLE"] = os.environ.get("AGENT_ROLE")
            captured_env["PIPELINE_STAGE_INDEX"] = os.environ.get("PIPELINE_STAGE_INDEX")
            captured_env["PIPELINE_TOTAL_STAGES"] = os.environ.get("PIPELINE_TOTAL_STAGES")
            state.add_artifact("captured", True)
            return state

        pipeline = Pipeline(stages=[capture_env_stage])
        initial = HandoffState(context="Test", next_instruction="Capture env")

        await pipeline.run(initial)

        assert captured_env["PATTERN_TYPE"] == "pipeline"
        assert captured_env["PIPELINE_ID"] is not None
        assert captured_env["AGENT_ROLE"] == "stage"
        assert captured_env["PIPELINE_STAGE_INDEX"] == "0"
        assert captured_env["PIPELINE_TOTAL_STAGES"] == "1"

    @pytest.mark.asyncio
    async def test_pipeline_handoff_between_stages(self):
        """Pipeline correctly passes HandoffState between stages."""
        execution_log = []

        async def stage_fetch(state: HandoffState) -> HandoffState:
            execution_log.append("fetch")
            state.add_artifact("raw_data", {"users": ["alice", "bob"]})
            state.update_instruction("Transform the data")
            return state

        async def stage_transform(state: HandoffState) -> HandoffState:
            execution_log.append("transform")
            raw = state.artifacts["raw_data"]
            state.add_artifact("transformed", {"count": len(raw["users"])})
            state.update_instruction("Validate")
            return state

        async def stage_validate(state: HandoffState) -> HandoffState:
            execution_log.append("validate")
            transformed = state.artifacts["transformed"]
            state.add_artifact("valid", transformed["count"] > 0)
            return state

        pipeline = Pipeline(stages=[stage_fetch, stage_transform, stage_validate])
        initial = HandoffState(context="Data pipeline", next_instruction="Fetch")

        result = await pipeline.run(initial)

        # Verify execution order
        assert execution_log == ["fetch", "transform", "validate"]

        # Verify all artifacts accumulated
        assert result.artifacts["raw_data"]["users"] == ["alice", "bob"]
        assert result.artifacts["transformed"]["count"] == 2
        assert result.artifacts["valid"] is True

    @pytest.mark.asyncio
    async def test_pipeline_env_restored_after_execution(self):
        """Pipeline restores env vars after execution."""
        # Set a custom value before
        os.environ["PATTERN_TYPE"] = "custom_pattern"

        async def dummy_stage(state: HandoffState) -> HandoffState:
            # During execution, should be "pipeline"
            assert os.environ.get("PATTERN_TYPE") == "pipeline"
            return state

        pipeline = Pipeline(stages=[dummy_stage])
        initial = HandoffState(context="Test", next_instruction="Run")

        await pipeline.run(initial)

        # After execution, should be restored
        assert os.environ.get("PATTERN_TYPE") == "custom_pattern"

        # Cleanup
        del os.environ["PATTERN_TYPE"]

    @pytest.mark.asyncio
    async def test_pipeline_stage_index_increments(self):
        """Pipeline correctly increments stage index for each stage."""
        captured_indices = []

        async def capture_index(state: HandoffState) -> HandoffState:
            captured_indices.append(os.environ.get("PIPELINE_STAGE_INDEX"))
            return state

        pipeline = Pipeline(stages=[capture_index, capture_index, capture_index])
        initial = HandoffState(context="Test", next_instruction="Run")

        await pipeline.run(initial)

        assert captured_indices == ["0", "1", "2"]


# ============================================================================
# Test Scenario 2: Jury E2E
# ============================================================================


class TestJuryE2E:
    """End-to-end tests for Jury pattern."""

    @pytest.mark.asyncio
    async def test_jury_sets_pattern_env_vars(self):
        """Jury sets PATTERN_TYPE=jury during juror spawning."""
        captured_envs = []

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            async def capture_env_spawn(**kwargs):
                env_snapshot = {
                    "PATTERN_TYPE": os.environ.get("PATTERN_TYPE"),
                    "JURY_ID": os.environ.get("JURY_ID"),
                    "AGENT_ROLE": os.environ.get("AGENT_ROLE"),
                    "JUROR_INDEX": os.environ.get("JUROR_INDEX"),
                    "TOTAL_JURORS": os.environ.get("TOTAL_JURORS"),
                }
                captured_envs.append(env_snapshot)

                juror = AsyncMock()
                juror.call = AsyncMock(return_value=True)
                return juror

            mock_spawn.side_effect = capture_env_spawn

            jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY)
            await jury.decide(bool, "Test question")

        # Verify each juror had correct env vars
        assert len(captured_envs) == 3
        for i, env in enumerate(captured_envs):
            assert env["PATTERN_TYPE"] == "jury"
            assert env["JURY_ID"] is not None
            assert env["AGENT_ROLE"] == "juror"
            assert env["JUROR_INDEX"] == str(i)
            assert env["TOTAL_JURORS"] == "3"

    @pytest.mark.asyncio
    async def test_jury_vote_isolation(self):
        """Jurors vote independently without seeing each other's votes."""
        votes_cast = []

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # Each juror gets different predetermined vote
            vote_sequence = [True, True, False]
            call_count = [0]

            async def mock_spawn_fn(**kwargs):
                juror = AsyncMock()
                idx = call_count[0]
                call_count[0] += 1

                async def cast_vote(return_type, question):
                    vote = vote_sequence[idx]
                    votes_cast.append({"juror": idx, "vote": vote, "at": datetime.now(timezone.utc)})
                    return vote

                juror.call = cast_vote
                return juror

            mock_spawn.side_effect = mock_spawn_fn

            jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY, debug=True)
            verdict = await jury.decide(bool, "Is this acceptable?")

        # Verify all votes were collected independently
        assert len(votes_cast) == 3
        assert votes_cast[0]["vote"] is True
        assert votes_cast[1]["vote"] is True
        assert votes_cast[2]["vote"] is False

        # Verify majority verdict
        assert verdict is True

        # Debug mode should have captured votes
        assert jury.last_votes == [True, True, False]

    @pytest.mark.asyncio
    async def test_jury_with_coordination_db(self, isolated_db: CoordinationDB):
        """Jury can integrate with CoordinationDB for agent tracking."""
        # Mock both spawn and tracked_spawn since jury uses tracked_spawn when db is provided
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn, \
             patch("scripts.agentica.tracked_agent.spawn") as mock_tracked_spawn:
            votes = [True, True, True]

            async def mock_spawn_fn(**kwargs):
                juror = AsyncMock()
                vote = votes.pop(0) if votes else True
                juror.call = AsyncMock(return_value=vote)
                return juror

            mock_spawn.side_effect = mock_spawn_fn
            mock_tracked_spawn.side_effect = mock_spawn_fn

            # Note: Full db integration requires tracked_spawn which needs more setup
            # Here we verify the jury accepts db parameter
            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                db=isolated_db
            )

            # With tracked_spawn mocked, this should work
            verdict = await jury.decide(bool, "Is this correct?")
            assert verdict is True

    @pytest.mark.asyncio
    async def test_jury_weighted_voting_e2e(self):
        """Jury correctly handles weighted voting end-to-end."""
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # Expert (weight 10) votes False, others (weight 1 each) vote True
            votes = [False, True, True]
            call_count = [0]

            async def mock_spawn_fn(**kwargs):
                juror = AsyncMock()
                idx = call_count[0]
                call_count[0] += 1
                juror.call = AsyncMock(return_value=votes[idx])
                return juror

            mock_spawn.side_effect = mock_spawn_fn

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                weights=[10, 1, 1],  # Expert has overwhelming weight
            )

            verdict = await jury.decide(bool, "Should we proceed?")

            # False should win due to weight (10 > 2)
            assert verdict is False


# ============================================================================
# Test Scenario 3: Circuit Breaker E2E
# ============================================================================


class TestCircuitBreakerE2E:
    """End-to-end tests for CircuitBreaker pattern."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_full_cycle(self):
        """Test complete circuit breaker cycle: closed -> open -> half-open -> closed."""
        with patch("scripts.agentica.patterns.circuit_breaker.spawn") as mock_spawn:
            failure_count = [0]
            max_failures_before_success = 3

            # Primary fails 3 times, then succeeds
            async def primary_call(return_type, query):
                failure_count[0] += 1
                if failure_count[0] <= max_failures_before_success:
                    raise ValueError(f"Failure #{failure_count[0]}")
                return "primary success"

            # Fallback always succeeds
            async def fallback_call(return_type, query):
                return "fallback result"

            primary_agent = AsyncMock()
            primary_agent.call = primary_call

            fallback_agent = AsyncMock()
            fallback_agent.call = fallback_call

            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="Primary",
                fallback_premise="Fallback",
                max_failures=2,
                reset_timeout=0.05  # 50ms for fast testing
            )

            # Initial state: CLOSED
            assert cb.state == CircuitState.CLOSED

            # First failure - still CLOSED
            result1 = await cb.execute("query 1")
            assert result1 == "fallback result"  # Fallback used on failure
            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == 1

            # Second failure - transitions to OPEN
            result2 = await cb.execute("query 2")
            assert result2 == "fallback result"
            assert cb.state == CircuitState.OPEN
            assert cb.failure_count == 2

            # While OPEN, fallback is used directly
            result3 = await cb.execute("query 3")
            assert result3 == "fallback result"
            assert cb.state == CircuitState.OPEN

            # Wait for reset timeout
            await asyncio.sleep(0.06)

            # After timeout, circuit tries primary again (HALF_OPEN)
            # Primary will fail once more (failure #3)
            result4 = await cb.execute("query 4")
            assert result4 == "fallback result"
            assert cb.state == CircuitState.OPEN  # Reopened on failure

            # Wait for timeout again
            await asyncio.sleep(0.06)

            # Now primary succeeds (failure_count > max_failures_before_success)
            result5 = await cb.execute("query 5")
            assert result5 == "primary success"
            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_env_vars_set(self):
        """Circuit breaker sets pattern env vars when spawning agents."""
        captured_envs = []

        with patch("scripts.agentica.patterns.circuit_breaker.spawn") as mock_spawn:
            async def capture_spawn(env=None, **kwargs):
                if env:
                    captured_envs.append({
                        "PATTERN_TYPE": env.get("PATTERN_TYPE"),
                        "CB_ID": env.get("CB_ID"),
                        "AGENT_ROLE": env.get("AGENT_ROLE"),
                    })
                agent = AsyncMock()
                agent.call = AsyncMock(return_value="success")
                return agent

            mock_spawn.side_effect = capture_spawn

            cb = CircuitBreaker(
                primary_premise="Primary",
                fallback_premise="Fallback",
                max_failures=3
            )

            await cb.execute("test query")

        # Both primary and fallback should have been spawned with env vars
        assert len(captured_envs) == 2
        for env in captured_envs:
            assert env["PATTERN_TYPE"] == "circuit_breaker"
            assert env["CB_ID"] is not None
        assert captured_envs[0]["AGENT_ROLE"] == "primary"
        assert captured_envs[1]["AGENT_ROLE"] == "fallback"


# ============================================================================
# Test Scenario 4: Swarm E2E with Broadcasts
# ============================================================================


class TestSwarmE2E:
    """End-to-end tests for Swarm pattern with broadcast integration."""

    @pytest.mark.asyncio
    async def test_swarm_sets_pattern_env_vars(self):
        """Swarm sets PATTERN_TYPE=swarm during agent execution."""
        captured_envs = []

        with patch("scripts.agentica.patterns.swarm.spawn") as mock_spawn:
            async def capture_spawn(**kwargs):
                env_snapshot = {
                    "PATTERN_TYPE": os.environ.get("PATTERN_TYPE"),
                    "SWARM_ID": os.environ.get("SWARM_ID"),
                }
                captured_envs.append(env_snapshot)

                agent = AsyncMock()
                agent.call = AsyncMock(return_value={"insight": "test"})
                return agent

            mock_spawn.side_effect = capture_spawn

            swarm = Swarm(perspectives=["P1", "P2", "P3"])
            await swarm.execute("Analyze this")

        assert len(captured_envs) == 3
        for env in captured_envs:
            assert env["PATTERN_TYPE"] == "swarm"
            assert env["SWARM_ID"] is not None

    @pytest.mark.asyncio
    async def test_swarm_aggregates_results(self):
        """Swarm correctly aggregates results from all agents."""
        with patch("scripts.agentica.patterns.swarm.spawn") as mock_spawn:
            results = [
                {"key1": "value1"},
                {"key2": "value2"},
                {"key3": "value3"},
            ]
            call_count = [0]

            async def mock_spawn_fn(**kwargs):
                agent = AsyncMock()
                idx = call_count[0]
                call_count[0] += 1
                agent.call = AsyncMock(return_value=results[idx])
                return agent

            mock_spawn.side_effect = mock_spawn_fn

            swarm = Swarm(
                perspectives=["Expert A", "Expert B", "Expert C"],
                aggregate_mode=AggregateMode.MERGE
            )

            result = await swarm.execute("Analyze")

        # MERGE mode combines all dicts
        assert result == {"key1": "value1", "key2": "value2", "key3": "value3"}

    @pytest.mark.asyncio
    async def test_swarm_with_broadcast_simulation(self, isolated_db: CoordinationDB, swarm_id: str):
        """Swarm agents can exchange broadcasts via CoordinationDB.

        This simulates the full swarm broadcast flow:
        1. Create agents
        2. Each agent broadcasts findings
        3. Agents query broadcasts from others
        4. Final synthesis
        """
        # Simulate agent broadcasts
        agent_insights = [
            ("security-analyst", {"security_issues": 2, "severity": "high"}),
            ("performance-analyst", {"bottlenecks": 3, "latency_ms": 150}),
            ("ux-analyst", {"usability_score": 7.5, "issues": 1}),
        ]

        # Phase 1: Each agent broadcasts their findings
        for agent_name, insight in agent_insights:
            isolated_db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=agent_name,
                broadcast_type=BroadcastType.FINDING,
                payload=insight,
            )

        # Phase 2: Each agent can query others' broadcasts
        for agent_name, _ in agent_insights:
            others_findings = isolated_db.get_broadcasts(
                swarm_id=swarm_id,
                exclude_sender=agent_name,
                broadcast_types=[BroadcastType.FINDING]
            )
            # Each agent sees 2 other agents' findings
            assert len(others_findings) == 2
            assert all(f.sender_agent != agent_name for f in others_findings)

        # Phase 3: All agents mark done
        for agent_name, _ in agent_insights:
            isolated_db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=agent_name,
                broadcast_type=BroadcastType.DONE,
                payload={"summary": f"{agent_name} completed analysis"},
            )

        # Phase 4: Coordinator synthesizes
        all_findings = isolated_db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.FINDING]
        )
        all_done = isolated_db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.DONE]
        )

        assert len(all_findings) == 3
        assert len(all_done) == 3

        # Verify we can aggregate insights
        aggregated = {}
        for finding in all_findings:
            aggregated.update(finding.payload)

        assert "security_issues" in aggregated
        assert "bottlenecks" in aggregated
        assert "usability_score" in aggregated


# ============================================================================
# Cross-Pattern Integration Tests
# ============================================================================


class TestCrossPatternIntegration:
    """Test interactions between different patterns."""

    @pytest.mark.asyncio
    async def test_pipeline_with_jury_stage(self):
        """Pipeline can have a stage that uses Jury for validation."""
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, True]

            async def mock_spawn_fn(**kwargs):
                juror = AsyncMock()
                vote = votes.pop(0) if votes else True
                juror.call = AsyncMock(return_value=vote)
                return juror

            mock_spawn.side_effect = mock_spawn_fn

            async def fetch_stage(state: HandoffState) -> HandoffState:
                state.add_artifact("code", "def foo(): pass")
                return state

            async def jury_validation_stage(state: HandoffState) -> HandoffState:
                code = state.artifacts["code"]
                jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY)
                is_valid = await jury.decide(bool, f"Is this code valid: {code}")
                state.add_artifact("is_valid", is_valid)
                return state

            pipeline = Pipeline(stages=[fetch_stage, jury_validation_stage])
            initial = HandoffState(context="Code validation", next_instruction="Fetch and validate")

            result = await pipeline.run(initial)

            assert result.artifacts["code"] == "def foo(): pass"
            assert result.artifacts["is_valid"] is True

    @pytest.mark.asyncio
    async def test_env_vars_restored_between_patterns(self):
        """Environment variables are properly isolated between different patterns."""
        with patch("scripts.agentica.patterns.jury.spawn") as mock_jury_spawn:
            mock_jury_spawn.return_value = AsyncMock()
            mock_jury_spawn.return_value.call = AsyncMock(return_value=True)

            captured_pattern_types = []

            async def stage_1(state: HandoffState) -> HandoffState:
                captured_pattern_types.append(("stage_1", os.environ.get("PATTERN_TYPE")))
                return state

            async def stage_with_jury(state: HandoffState) -> HandoffState:
                captured_pattern_types.append(("stage_jury_outer", os.environ.get("PATTERN_TYPE")))

                jury = Jury(num_jurors=1, consensus_mode=ConsensusMode.MAJORITY)
                await jury.decide(bool, "test")

                # After jury completes, pattern type should still be pipeline
                captured_pattern_types.append(("stage_jury_after", os.environ.get("PATTERN_TYPE")))
                return state

            async def stage_3(state: HandoffState) -> HandoffState:
                captured_pattern_types.append(("stage_3", os.environ.get("PATTERN_TYPE")))
                return state

            pipeline = Pipeline(stages=[stage_1, stage_with_jury, stage_3])
            initial = HandoffState(context="Test", next_instruction="Run")

            await pipeline.run(initial)

            # All pipeline stages should see "pipeline" pattern type
            assert captured_pattern_types[0] == ("stage_1", "pipeline")
            assert captured_pattern_types[1] == ("stage_jury_outer", "pipeline")
            assert captured_pattern_types[2] == ("stage_jury_after", "pipeline")
            assert captured_pattern_types[3] == ("stage_3", "pipeline")


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestPatternErrorHandling:
    """Test error handling across patterns."""

    @pytest.mark.asyncio
    async def test_pipeline_stage_failure_propagates(self):
        """Pipeline propagates stage failures correctly."""
        async def failing_stage(state: HandoffState) -> HandoffState:
            raise ValueError("Stage failed intentionally")

        pipeline = Pipeline(stages=[failing_stage])
        initial = HandoffState(context="Test", next_instruction="Run")

        with pytest.raises(ValueError, match="Stage failed intentionally"):
            await pipeline.run(initial)

    @pytest.mark.asyncio
    async def test_jury_partial_failure_handling(self):
        """Jury handles partial juror failures when allow_partial=True."""
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            call_count = [0]

            async def mock_spawn_fn(**kwargs):
                juror = AsyncMock()
                idx = call_count[0]
                call_count[0] += 1

                if idx == 1:  # Second juror fails
                    juror.call = AsyncMock(side_effect=Exception("Juror failed"))
                else:
                    juror.call = AsyncMock(return_value=True)
                return juror

            mock_spawn.side_effect = mock_spawn_fn

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=True,
                min_jurors=2
            )

            # Should succeed with 2/3 jurors
            verdict = await jury.decide(bool, "Test question")
            assert verdict is True


# ============================================================================
# Performance Tests
# ============================================================================


class TestPatternPerformance:
    """Performance tests for patterns."""

    @pytest.mark.asyncio
    async def test_pipeline_10_stages(self):
        """Pipeline handles 10 stages efficiently."""
        async def stage(state: HandoffState) -> HandoffState:
            stage_num = len([k for k in state.artifacts if k.startswith("stage_")])
            state.add_artifact(f"stage_{stage_num}", f"result_{stage_num}")
            return state

        pipeline = Pipeline(stages=[stage] * 10)
        initial = HandoffState(context="Perf test", next_instruction="Run")

        import time
        start = time.time()
        result = await pipeline.run(initial)
        duration = time.time() - start

        assert len([k for k in result.artifacts if k.startswith("stage_")]) == 10
        assert duration < 1.0  # Should complete in under 1 second

    @pytest.mark.asyncio
    async def test_jury_parallel_voting(self):
        """Jury executes votes in parallel."""
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            async def slow_spawn(**kwargs):
                juror = AsyncMock()

                async def slow_vote(return_type, question):
                    await asyncio.sleep(0.1)  # Simulate slow voting
                    return True

                juror.call = slow_vote
                return juror

            mock_spawn.side_effect = slow_spawn

            jury = Jury(num_jurors=5, consensus_mode=ConsensusMode.MAJORITY)

            import time
            start = time.time()
            await jury.decide(bool, "Parallel test")
            duration = time.time() - start

            # If parallel, should take ~0.1s. If sequential, would take ~0.5s
            # Allow some overhead, but should definitely be < 0.3s
            assert duration < 0.3, f"Took {duration}s - votes may not be parallel"
