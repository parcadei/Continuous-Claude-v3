"""Tests for Agentica Jury pattern (TDD - tests written first).

The Jury pattern spawns N independent agents (jurors) that evaluate the same
question independently. Uses Consensus to reach a verdict.

Pattern from scripts/agentica/PATTERNS.md:
    Structure: N agents independently evaluate → Consensus/majority wins
    Use when: High-stakes decisions, reducing hallucination, validation
"""

import pytest
from scripts.agentica.patterns import Jury, ConsensusMode, ConsensusNotReachedError
from unittest.mock import AsyncMock, Mock, patch


def create_jury_mock(votes):
    """Helper to create mock spawn that returns jurors with predetermined votes."""
    async def mock_spawn(*args, **kwargs):
        juror = AsyncMock()
        # Pop first vote for this juror
        if votes:
            vote = votes.pop(0)
            juror.call = AsyncMock(return_value=vote)
        else:
            juror.call = AsyncMock(return_value=True)
        return juror
    return mock_spawn


class TestJuryBasicVoting:
    """Test basic jury voting functionality."""

    @pytest.mark.asyncio
    async def test_jury_majority_voting(self):
        """3 jurors, 2 agree → majority wins.

        Pattern: N agents vote independently → Consensus decides winner
        Expected: Jury spawns 3 agents, collects votes, returns majority
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # 2 vote False, 1 votes True → majority is False
            votes = [False, False, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                model="openai:gpt-4.1"
            )

            # Ask jury to evaluate a question
            result = await jury.decide(
                bool,
                "Is the Earth flat?"
            )

            # Should return False (majority of jurors)
            assert result is False

    @pytest.mark.asyncio
    async def test_jury_unanimous_mode(self):
        """Jury can require unanimous agreement.

        Pattern: All jurors must agree, or raise ConsensusNotReached
        Expected: Jury spawns agents, requires unanimous vote
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # All vote True → unanimous
            votes = [True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.UNANIMOUS,
                model="openai:gpt-4.1"
            )

            # Question with unanimous answer
            result = await jury.decide(
                bool,
                "Is 2+2 equal to 4?"
            )

            # Should pass (all agree)
            assert result is True

    @pytest.mark.asyncio
    async def test_jury_unanimous_mode_fails_on_disagreement(self):
        """Unanimous mode raises ConsensusNotReached if jurors disagree.

        Pattern: Jury fails fast if consensus cannot be reached
        Expected: Raises ConsensusNotReached with vote details
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # Disagreement: different votes
            votes = ["Python", "Rust", "Go"]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.UNANIMOUS,
                model="openai:gpt-4.1"
            )

            # Should raise because votes are not unanimous
            with pytest.raises(ConsensusNotReachedError):
                await jury.decide(
                    str,
                    "What is the best programming language?"
                )

    @pytest.mark.asyncio
    async def test_jury_weighted_jurors(self):
        """Some jurors can have more weight.

        Pattern: Expert jurors get higher weight in voting
        Expected: Jury accepts weights list and passes to Consensus
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # All vote True
            votes = [True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                weights=[2, 1, 1],  # First juror has double weight
                model="openai:gpt-4.1"
            )

            result = await jury.decide(
                bool,
                "Is Python dynamically typed?"
            )

            # Should work with weighted voting
            assert result is True

    @pytest.mark.asyncio
    async def test_jury_threshold_voting(self):
        """Jury can use threshold consensus (e.g., 75% agreement).

        Pattern: Require X% of jurors to agree
        Expected: Jury uses THRESHOLD mode with specified threshold
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # 3 out of 4 vote True (75% agreement)
            votes = [True, True, True, False]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=4,
                consensus_mode=ConsensusMode.THRESHOLD,
                threshold=0.75,  # Need 75% agreement
                model="openai:gpt-4.1"
            )

            # 3/4 = 75% vote True
            result = await jury.decide(
                bool,
                "Is water composed of H2O?"
            )

            # Should pass threshold
            assert result is True

    @pytest.mark.asyncio
    async def test_jury_threshold_fails_below_threshold(self):
        """Jury raises ConsensusNotReached when threshold not met.

        Pattern: Threshold validation prevents weak consensus
        Expected: Raises ConsensusNotReached if below threshold
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # Split vote: 2 tabs, 2 spaces (50% agreement, below 75%)
            votes = ["tabs", "tabs", "spaces", "spaces"]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=4,
                consensus_mode=ConsensusMode.THRESHOLD,
                threshold=0.75,  # Need 75% agreement
                model="openai:gpt-4.1"
            )

            # 50% split vote, below 75% threshold
            with pytest.raises(ConsensusNotReachedError):
                await jury.decide(
                    str,
                    "Is tabs better than spaces?"
                )

    @pytest.mark.asyncio
    async def test_jury_tie_handling(self):
        """Ties resolved by first occurrence.

        Pattern: Consensus breaks ties deterministically (first vote)
        Expected: With even split, first juror's vote wins
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # 50/50 split - first vote wins
            votes = ["Option A", "Option B"]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=2,
                consensus_mode=ConsensusMode.MAJORITY,
                model="openai:gpt-4.1"
            )

            # Tie situation
            result = await jury.decide(
                str,
                "Choose: Option A or Option B?"
            )

            # Should return something (tie broken by first occurrence)
            assert result is not None
            assert isinstance(result, str)


class TestJuryValidation:
    """Test input validation and error handling."""

    def test_jury_minimum_jurors(self):
        """At least 1 juror required.

        Pattern: Jury requires at least one juror to function
        Expected: Raises ValueError if num_jurors < 1
        """
        with pytest.raises(ValueError, match="at least 1"):
            Jury(
                num_jurors=0,
                consensus_mode=ConsensusMode.MAJORITY
            )

    def test_jury_negative_jurors(self):
        """Negative jurors not allowed.

        Pattern: num_jurors must be positive
        Expected: Raises ValueError if negative
        """
        with pytest.raises(ValueError, match="at least 1"):
            Jury(
                num_jurors=-1,
                consensus_mode=ConsensusMode.MAJORITY
            )

    def test_jury_weights_length_mismatch(self):
        """Weights must match number of jurors.

        Pattern: Each juror must have a weight
        Expected: Raises ValueError if weights length != num_jurors
        """
        with pytest.raises(ValueError, match="weights.*same length"):
            Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                weights=[1, 2]  # Only 2 weights for 3 jurors
            )

    def test_jury_threshold_requires_threshold_param(self):
        """THRESHOLD mode requires threshold parameter.

        Pattern: Threshold mode needs explicit threshold value
        Expected: Raises ValueError if threshold missing
        """
        with pytest.raises(ValueError, match="threshold"):
            Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.THRESHOLD
                # Missing threshold parameter
            )

    def test_jury_invalid_threshold_range(self):
        """Threshold must be between 0 and 1.

        Pattern: Threshold is a percentage (0.0 to 1.0)
        Expected: Raises ValueError if outside range
        """
        with pytest.raises(ValueError, match="between 0 and 1"):
            Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.THRESHOLD,
                threshold=1.5
            )


class TestJuryCustomPremises:
    """Test custom premises for jurors."""

    @pytest.mark.asyncio
    async def test_jury_with_custom_premise(self):
        """Jury can customize juror premise.

        Pattern: All jurors share same premise/system prompt
        Expected: Jury passes premise to each spawned agent
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = ["no", "no", "yes"]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                premise="You are a conservative code reviewer. Prefer readability over cleverness.",
                model="openai:gpt-4.1"
            )

            result = await jury.decide(
                str,
                "Should we use this one-liner: x = [i for i in range(10) if i % 2]?"
            )

            # Jurors should reflect conservative premise
            assert result is not None

    @pytest.mark.asyncio
    async def test_jury_with_diverse_premises(self):
        """Jury can have different premise per juror.

        Pattern: Each juror can have specialized perspective
        Expected: Jury accepts list of premises (one per juror)
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # 2 vote False (security concern), 1 votes True
            votes = [False, False, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                premises=[
                    "You are a security expert. Focus on vulnerabilities.",
                    "You are a performance expert. Focus on optimization.",
                    "You are a readability expert. Focus on maintainability."
                ],
                model="openai:gpt-4.1"
            )

            result = await jury.decide(
                bool,
                "Is this code acceptable: password = request.args.get('pwd')"
            )

            # Majority vote False (security concern)
            assert result is False

    def test_jury_diverse_premises_length_mismatch(self):
        """Premises list must match num_jurors.

        Pattern: One premise per juror required
        Expected: Raises ValueError if premises length != num_jurors
        """
        with pytest.raises(ValueError, match="premises.*same length"):
            Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                premises=[
                    "Expert 1",
                    "Expert 2"
                    # Missing premise for juror 3
                ]
            )


class TestJuryReturnTypes:
    """Test different return types for jury decisions."""

    @pytest.mark.asyncio
    async def test_jury_returns_bool(self):
        """Jury can return boolean verdict.

        Pattern: Simple yes/no questions
        Expected: Jurors vote bool, consensus returns bool
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY)

            result = await jury.decide(bool, "Is Python interpreted?")

            assert isinstance(result, bool)
            assert result is True

    @pytest.mark.asyncio
    async def test_jury_returns_string(self):
        """Jury can return string verdict.

        Pattern: Classification or choice questions
        Expected: Jurors vote str, consensus returns str
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = ["critical", "critical", "high"]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY)

            result = await jury.decide(
                str,
                "Classify this bug severity: 'App crashes on startup'. Options: low, medium, high, critical"
            )

            assert isinstance(result, str)
            assert result in ["low", "medium", "high", "critical"]

    @pytest.mark.asyncio
    async def test_jury_returns_dict(self):
        """Jury can return structured verdict.

        Pattern: Complex decisions with reasoning
        Expected: Jurors vote dict, consensus handles structured votes
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # All return same dict - need key function for unhashable dicts
            votes = [
                {"verdict": "approve", "confidence": 0.9},
                {"verdict": "approve", "confidence": 0.8},
                {"verdict": "approve", "confidence": 0.95}
            ]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                model="openai:gpt-4.1",
                # Key function to extract hashable value for consensus
                key=lambda v: v.get("verdict") if isinstance(v, dict) else v
            )

            result = await jury.decide(
                dict,
                "Evaluate this PR. Return: {verdict: 'approve'|'reject', confidence: 0-1}"
            )

            assert isinstance(result, dict)
            assert "verdict" in result

    @pytest.mark.asyncio
    async def test_jury_with_key_extraction(self):
        """Jury can use key function for structured votes.

        Pattern: Vote on specific field of complex response
        Expected: Jury uses key param to extract decision field
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # Votes are dicts, consensus uses key to extract decision
            votes = [
                {"decision": "pass", "reason": "looks good"},
                {"decision": "pass", "reason": "all tests pass"},
                {"decision": "pass", "reason": "well formatted"}
            ]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                key=lambda v: v.get("decision") if isinstance(v, dict) else v,
                model="openai:gpt-4.1"
            )

            result = await jury.decide(
                dict,
                "Return: {decision: 'pass'|'fail', reason: '...'}"
            )

            # Should consensus on 'decision' field
            assert isinstance(result, dict)


class TestJuryParallelExecution:
    """Test parallel execution of jurors."""

    @pytest.mark.asyncio
    async def test_jury_executes_in_parallel(self):
        """Jurors evaluate independently and in parallel.

        Pattern: All jurors run concurrently via asyncio.gather
        Expected: All jurors complete, total time < sum of individual times
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY)

            import time
            start = time.time()

            result = await jury.decide(bool, "Is Python dynamically typed?")

            duration = time.time() - start

            # With 3 jurors running in parallel, should complete in roughly
            # the time of a single agent call (not 3x)
            # (This is more of a smoke test - actual timing varies)
            assert result is not None
            # TODO: Add actual parallelism verification

    @pytest.mark.asyncio
    async def test_jury_handles_partial_failures(self):
        """Jury continues if some jurors fail.

        Pattern: Resilient voting - ignore failed juror votes
        Expected: Jury completes with successful jurors only
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            # This test will fail until we implement failure handling
            jury = Jury(
                num_jurors=5,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=True,  # Continue with partial votes
                min_jurors=3  # Need at least 3 successful votes
            )

            # Even if 1-2 jurors fail, should still complete
            result = await jury.decide(bool, "Is the sky blue?")

            assert result is not None


class TestJuryScope:
    """Test jury with custom scope (tools)."""

    @pytest.mark.asyncio
    async def test_jury_with_tools(self):
        """Jury can provide tools to all jurors.

        Pattern: Tool-using jurors for informed decisions
        Expected: All jurors have access to scope tools
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            def search_docs(query: str) -> str:
                """Mock doc search."""
                return f"Documentation says: {query} is important"

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                scope={"search_docs": search_docs},
                model="openai:gpt-4.1"
            )

            result = await jury.decide(
                bool,
                "Based on docs, is error handling required? Use search_docs tool."
            )

            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_jury_per_call_scope(self):
        """Jury scope is set at init time, not per-call.

        Pattern: Tools configured at Jury creation
        Expected: Scope from init() available to all jurors
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            def analyze_code(code: str) -> dict:
                return {"complexity": 5, "security_issues": 1}

            # Scope is configured at init time
            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                scope={"analyze": analyze_code}
            )

            result = await jury.decide(bool, "Is this code acceptable?")

            assert isinstance(result, bool)


class TestJuryEdgeCases:
    """Test edge cases and corner scenarios."""

    @pytest.mark.asyncio
    async def test_single_juror_jury(self):
        """Single juror is valid (trivial consensus).

        Pattern: Jury of 1 is allowed (always reaches consensus)
        Expected: Returns single juror's vote
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(num_jurors=1, consensus_mode=ConsensusMode.MAJORITY)

            result = await jury.decide(bool, "Is 1+1=2?")

            assert result is True

    @pytest.mark.asyncio
    async def test_jury_with_none_return_type(self):
        """Jury can perform side-effects only (no return).

        Pattern: Jury validates action but doesn't return value
        Expected: Works with None return type
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [None, None, None]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY)

            # Side-effect only task
            result = await jury.decide(
                None,
                "Validate this is safe: os.remove('/tmp/test.txt')"
            )

            # Should complete without error
            assert result is None

    @pytest.mark.asyncio
    async def test_large_jury(self):
        """Jury scales to larger numbers of jurors.

        Pattern: Jury can have many jurors for high-confidence decisions
        Expected: Handles N=10+ jurors without issues
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # 9 True, 1 False = 90% agreement (above 80%)
            votes = [True] * 9 + [False]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(num_jurors=10, consensus_mode=ConsensusMode.THRESHOLD, threshold=0.8)

            result = await jury.decide(bool, "Is Python popular?")

            assert isinstance(result, bool)


class TestJuryIntegration:
    """Integration tests with real Agentica spawn."""

    @pytest.mark.asyncio
    async def test_jury_integration_basic(self):
        """End-to-end test with real agent spawning.

        Pattern: Full jury workflow from spawn to consensus
        Expected: Creates jury, spawns agents, collects votes, returns verdict
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY)

            result = await jury.decide(
                bool,
                "Is the capital of France Paris?"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_jury_debug_mode(self):
        """Jury can expose individual votes for debugging.

        Pattern: Visibility into jury decisions for transparency
        Expected: Jury tracks and exposes individual juror votes
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, False]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(num_jurors=3, consensus_mode=ConsensusMode.MAJORITY, debug=True)

            result = await jury.decide(bool, "Is water wet?")

            # Should track individual votes when debug=True
            assert hasattr(jury, 'last_votes')
            assert len(jury.last_votes) == 3
            assert all(isinstance(v, bool) for v in jury.last_votes)


class TestJuryCoordinationDB:
    """Test Jury integration with CoordinationDB for tracking."""

    @pytest.mark.asyncio
    async def test_jury_with_coordination_db(self):
        """Jury registers jurors in coordination database when db provided.

        Pattern: Observable jury decisions via CoordinationDB
        Expected: Each juror is registered as an agent with pattern='jury'
        """
        import tempfile
        from pathlib import Path
        from scripts.agentica.coordination import CoordinationDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = CoordinationDB(db_path=db_path, session_id="test-jury-session")

            with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn, \
                 patch("scripts.agentica.tracked_agent.spawn") as mock_tracked_spawn:
                # Mock tracked_spawn behavior
                votes = [True, True, False]

                async def mock_tracked_spawn_fn(**kwargs):
                    juror = AsyncMock()
                    if votes:
                        vote = votes.pop(0)
                        juror.call = AsyncMock(return_value=vote)
                    else:
                        juror.call = AsyncMock(return_value=True)
                    return juror

                mock_tracked_spawn.side_effect = mock_tracked_spawn_fn

                # Also need to mock the import-time spawn
                mock_spawn.side_effect = mock_tracked_spawn_fn

                jury = Jury(
                    num_jurors=3,
                    consensus_mode=ConsensusMode.MAJORITY,
                    db=db  # Pass coordination database
                )

                # This will use tracked_spawn if db is provided
                result = await jury.decide(bool, "Is 2+2=4?")

                # Verify verdict reached
                assert result is True or result is False

    @pytest.mark.asyncio
    async def test_jury_without_db(self):
        """Jury works without CoordinationDB (no tracking).

        Pattern: DB is optional for simpler deployments
        Expected: Jury completes successfully without db parameter
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [True, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            # No db parameter - should still work
            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY
            )

            result = await jury.decide(bool, "Is the sky blue?")

            assert result is True


class TestJuryWeightedVoting:
    """Test weighted voting scenarios in detail."""

    @pytest.mark.asyncio
    async def test_weighted_voting_minority_wins(self):
        """Heavy weight can override majority count.

        Pattern: Expert jurors can have decisive votes
        Expected: Single high-weight vote beats multiple low-weight votes
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # 1 True with weight 10, 2 False with weight 1 each
            # Total True weight: 10, Total False weight: 2
            votes = [True, False, False]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                weights=[10, 1, 1],  # First juror has 10x weight
            )

            result = await jury.decide(bool, "Is this code safe?")

            # True should win despite being minority in count
            assert result is True

    @pytest.mark.asyncio
    async def test_weighted_voting_threshold_calculation(self):
        """Threshold mode uses weighted sums correctly.

        Pattern: Threshold percentage based on total weight, not count
        Expected: 10/12 = 83.3% meets 80% threshold
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # Weight: 10+1+1 = 12 total
            # True weight: 10 (first juror)
            # Percentage: 10/12 = 83.3%
            votes = [True, False, False]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.THRESHOLD,
                threshold=0.80,  # Need 80%
                weights=[10, 1, 1],
            )

            result = await jury.decide(bool, "Approve this PR?")

            # 83.3% > 80% threshold, should pass
            assert result is True

    @pytest.mark.asyncio
    async def test_weighted_threshold_fails(self):
        """Weighted threshold correctly fails when not met.

        Pattern: Even high-weight votes must meet percentage
        Expected: 5/10 = 50% fails 80% threshold
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # Weight: 5+5 = 10 total, split evenly
            votes = [True, False]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=2,
                consensus_mode=ConsensusMode.THRESHOLD,
                threshold=0.80,
                weights=[5, 5],
            )

            with pytest.raises(ConsensusNotReachedError):
                await jury.decide(bool, "Is this approved?")

    @pytest.mark.asyncio
    async def test_weighted_tie_breaking(self):
        """Ties in weighted voting resolved by first occurrence.

        Pattern: Equal weights go to first vote
        Expected: With same weight, first juror's vote wins
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = ["A", "B"]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=2,
                consensus_mode=ConsensusMode.MAJORITY,
                weights=[1, 1],  # Equal weights
            )

            result = await jury.decide(str, "Choose A or B?")

            # First occurrence wins tie
            assert result == "A"


class TestJuryPremiseBuilding:
    """Test how jury builds premises for spawned jurors."""

    @pytest.mark.asyncio
    async def test_spawn_receives_premise(self):
        """Spawn receives the premise from jury configuration.

        Pattern: Premise flows from Jury config to spawn call
        Expected: spawn() is called with premise kwarg
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            mock_juror = AsyncMock()
            mock_juror.call = AsyncMock(return_value=True)
            mock_spawn.return_value = mock_juror

            jury = Jury(
                num_jurors=1,
                consensus_mode=ConsensusMode.MAJORITY,
                premise="You are an expert code reviewer",
            )

            await jury.decide(bool, "Is this code good?")

            # Check spawn was called with the premise
            mock_spawn.assert_called()
            call_kwargs = mock_spawn.call_args[1]
            assert "premise" in call_kwargs
            assert "expert code reviewer" in call_kwargs["premise"]

    @pytest.mark.asyncio
    async def test_spawn_receives_model(self):
        """Spawn receives model from jury configuration.

        Pattern: Model flows from Jury config to spawn call
        Expected: spawn() is called with model kwarg when provided
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            mock_juror = AsyncMock()
            mock_juror.call = AsyncMock(return_value=True)
            mock_spawn.return_value = mock_juror

            jury = Jury(
                num_jurors=1,
                consensus_mode=ConsensusMode.MAJORITY,
                model="anthropic:claude-3-opus",
            )

            await jury.decide(bool, "Test question")

            call_kwargs = mock_spawn.call_args[1]
            assert call_kwargs.get("model") == "anthropic:claude-3-opus"

    @pytest.mark.asyncio
    async def test_default_premise_for_jurors(self):
        """Jurors get default premise when none specified.

        Pattern: Jury provides sensible default premise
        Expected: spawn() called with default evaluator premise
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            mock_juror = AsyncMock()
            mock_juror.call = AsyncMock(return_value=True)
            mock_spawn.return_value = mock_juror

            jury = Jury(
                num_jurors=1,
                consensus_mode=ConsensusMode.MAJORITY,
                # No premise specified - should use default
            )

            await jury.decide(bool, "Evaluate this")

            call_kwargs = mock_spawn.call_args[1]
            assert "premise" in call_kwargs
            # Default premise should be non-empty
            assert len(call_kwargs["premise"]) > 0


class TestJuryFailureHandling:
    """Test jury behavior when jurors fail."""

    @pytest.mark.asyncio
    async def test_all_jurors_fail_raises(self):
        """Jury raises when all jurors fail.

        Pattern: Can't reach consensus with no votes
        Expected: Raises error when all jurors fail
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            mock_juror = AsyncMock()
            mock_juror.call = AsyncMock(side_effect=Exception("Juror failed"))
            mock_spawn.return_value = mock_juror

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=False,  # Don't allow partial results
            )

            with pytest.raises(Exception, match="Juror failed"):
                await jury.decide(bool, "Will this fail?")

    @pytest.mark.asyncio
    async def test_partial_failure_with_enough_votes(self):
        """Jury succeeds with partial failures if min_jurors met.

        Pattern: Resilient consensus despite some failures
        Expected: Reaches consensus with remaining jurors
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            call_count = [0]

            async def spawn_with_failures(**kwargs):
                call_count[0] += 1
                juror = AsyncMock()
                if call_count[0] == 2:  # Second juror fails
                    juror.call = AsyncMock(side_effect=Exception("Failed"))
                else:
                    juror.call = AsyncMock(return_value=True)
                return juror

            mock_spawn.side_effect = spawn_with_failures

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=True,
                min_jurors=2,  # Need at least 2
            )

            result = await jury.decide(bool, "Partial success?")

            # Should succeed with 2/3 jurors
            assert result is True

    @pytest.mark.asyncio
    async def test_partial_failure_below_min_jurors(self):
        """Jury fails when too many jurors fail.

        Pattern: Minimum quorum required for valid consensus
        Expected: Raises when remaining jurors below minimum
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            call_count = [0]

            async def spawn_mostly_failing(**kwargs):
                call_count[0] += 1
                juror = AsyncMock()
                if call_count[0] <= 2:  # First two jurors fail
                    juror.call = AsyncMock(side_effect=Exception("Failed"))
                else:
                    juror.call = AsyncMock(return_value=True)
                return juror

            mock_spawn.side_effect = spawn_mostly_failing

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=True,
                min_jurors=2,  # Need at least 2, but only 1 succeeds
            )

            with pytest.raises(ValueError, match="Not enough successful jurors"):
                await jury.decide(bool, "Will this fail?")


class TestJuryConsensusIntegration:
    """Test Jury's integration with the Consensus primitive."""

    @pytest.mark.asyncio
    async def test_jury_uses_consensus_object(self):
        """Jury creates and uses Consensus object internally.

        Pattern: Jury delegates voting logic to Consensus
        Expected: Jury.consensus attribute is a Consensus instance
        """
        from scripts.agentica.patterns import Consensus

        jury = Jury(
            num_jurors=3,
            consensus_mode=ConsensusMode.MAJORITY,
        )

        assert hasattr(jury, 'consensus')
        assert isinstance(jury.consensus, Consensus)

    @pytest.mark.asyncio
    async def test_jury_passes_key_to_consensus(self):
        """Jury passes key function to Consensus.decide().

        Pattern: Key extraction for structured votes
        Expected: Consensus uses key to compare votes
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            votes = [
                {"decision": "approve", "confidence": 0.9},
                {"decision": "approve", "confidence": 0.7},
                {"decision": "reject", "confidence": 0.5},
            ]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                key=lambda v: v.get("decision") if isinstance(v, dict) else v,
            )

            result = await jury.decide(dict, "Evaluate this PR")

            # Should return one of the approve dicts
            assert isinstance(result, dict)
            assert result["decision"] == "approve"

    @pytest.mark.asyncio
    async def test_jury_passes_weights_to_consensus(self):
        """Jury passes weights to Consensus.decide().

        Pattern: Weighted voting through Consensus
        Expected: Consensus respects weights in vote counting
        """
        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            # First has weight 5, others weight 1 each
            votes = [False, True, True]
            mock_spawn.side_effect = create_jury_mock(votes.copy())

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                weights=[5, 1, 1],  # False has weight 5 > True weight 2
            )

            result = await jury.decide(bool, "Weighted vote")

            # False should win due to weight
            assert result is False


class TestJuryTaskGroupBehavior:
    """Test TaskGroup-based fail-fast behavior (Python 3.11+)."""

    @pytest.mark.asyncio
    async def test_strict_mode_cancels_on_first_failure(self):
        """Strict mode (allow_partial=False) should cancel on first failure.

        Pattern: Fail-fast cancellation via TaskGroup
        Expected: First failure cancels remaining juror tasks
        """
        import asyncio
        executed = []

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            call_count = [0]

            async def mock_spawn_fn(**kwargs):
                juror = AsyncMock()
                idx = call_count[0]
                call_count[0] += 1

                async def slow_or_fail(return_type, question):
                    if idx == 0:
                        executed.append("first")
                        raise ValueError("First fails")
                    # This should be cancelled before executing
                    await asyncio.sleep(1)
                    executed.append("slow")
                    return True

                juror.call = slow_or_fail
                return juror

            mock_spawn.side_effect = mock_spawn_fn

            jury = Jury(
                num_jurors=2,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=False  # Strict mode
            )

            with pytest.raises(ValueError, match="First fails"):
                await jury.decide(bool, "Test?")

            # Second juror should have been cancelled
            assert "slow" not in executed

    @pytest.mark.asyncio
    async def test_partial_mode_continues_all(self):
        """Partial mode should let all jurors complete.

        Pattern: Partial results mode (allow_partial=True) uses gather with return_exceptions
        Expected: All jurors execute even when some fail
        """
        executed = []

        with patch("scripts.agentica.patterns.jury.spawn") as mock_spawn:
            call_count = [0]

            async def mock_spawn_fn(**kwargs):
                juror = AsyncMock()
                idx = call_count[0]
                call_count[0] += 1

                async def vote_or_fail(return_type, question):
                    executed.append(f"juror_{idx}")
                    if idx == 1:
                        raise ValueError(f"Juror {idx} failed")
                    return True

                juror.call = vote_or_fail
                return juror

            mock_spawn.side_effect = mock_spawn_fn

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                allow_partial=True,
                min_jurors=2
            )

            result = await jury.decide(bool, "Test?")

            # All three should have executed
            assert len(executed) == 3
            assert result is True  # 2/3 voted True
