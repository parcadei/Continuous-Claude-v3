"""
TDD Tests for GeneratorCritic Pattern

Tests written BEFORE implementation to drive design.
Expected to FAIL until patterns.py implements GeneratorCritic.

Pattern: Generator proposes → Critic evaluates → Generator refines → loop
- Generator agent creates initial solution
- Critic agent provides feedback
- Generator refines based on feedback
- Iterates until critic approves or max_rounds reached
- Uses HandoffState for passing state between agents
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from scripts.agentica_patterns.patterns import GeneratorCritic
from scripts.agentica_patterns.primitives import HandoffState


class TestGeneratorCriticBasicFlow:
    """Test basic generator/critic interaction."""

    @pytest.mark.asyncio
    async def test_generator_critic_basic_flow(self):
        """Generator proposes, critic approves → done in 1 round."""
        # Create a GeneratorCritic instance
        gc = GeneratorCritic(
            generator_premise="You generate Python code for the task.",
            critic_premise="You review Python code. Approve if it's correct."
        )

        # Mock spawn to return mock agents
        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            # Generator produces solution
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="Task: Create hello world function",
                next_instruction="PENDING_REVIEW",
                artifacts={"code": "def hello(): return 'Hello, World!'"}
            ))

            # Critic approves immediately - note: result comes from critic
            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="Code review complete",
                next_instruction="APPROVED",
                artifacts={"code": "def hello(): return 'Hello, World!'", "feedback": "Looks good!"}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            # Run the pattern
            result = await gc.run("Create a hello world function")

            # Assertions - result is from critic's final state
            assert result.next_instruction == "APPROVED"
            assert "feedback" in result.artifacts
            assert result.artifacts["feedback"] == "Looks good!"

            # Only 1 generation + 1 critique
            assert mock_generator.call.call_count == 1
            assert mock_critic.call.call_count == 1

    @pytest.mark.asyncio
    async def test_generator_critic_iteration(self):
        """Critic rejects, generator refines, critic approves."""
        gc = GeneratorCritic(
            generator_premise="You generate Python code.",
            critic_premise="You review Python code.",
            max_rounds=3
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            # Generator: first attempt
            generator_outputs = [
                HandoffState(
                    context="Task: Create hello world function",
                    next_instruction="PENDING_REVIEW",
                    artifacts={"code": "def hello(): print('Hello')"}
                ),
                # Second attempt after feedback
                HandoffState(
                    context="Task: Create hello world function",
                    next_instruction="PENDING_REVIEW",
                    artifacts={"code": "def hello(): return 'Hello, World!'"}
                )
            ]

            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(side_effect=generator_outputs)

            # Critic: reject first, approve second
            # Note: critic's final state is returned, include code in final approval
            critic_outputs = [
                HandoffState(
                    context="Code review",
                    next_instruction="NEEDS_REVISION",
                    artifacts={"feedback": "Should return, not print"}
                ),
                HandoffState(
                    context="Code review complete",
                    next_instruction="APPROVED",
                    artifacts={"code": "def hello(): return 'Hello, World!'", "feedback": "Perfect!"}
                )
            ]

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Create a hello world function")

            # Final result should be approved (from critic's final state)
            assert result.next_instruction == "APPROVED"
            assert result.artifacts["code"] == "def hello(): return 'Hello, World!'"

            # 2 generation attempts, 2 critiques
            assert mock_generator.call.call_count == 2
            assert mock_critic.call.call_count == 2


class TestGeneratorCriticMaxRounds:
    """Test max_rounds enforcement."""

    @pytest.mark.asyncio
    async def test_generator_critic_max_rounds(self):
        """Stops after max_rounds even if not approved."""
        gc = GeneratorCritic(
            generator_premise="You generate code.",
            critic_premise="You review code.",
            max_rounds=2  # Only 2 rounds allowed
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            # Generator always produces something
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="Task",
                next_instruction="PENDING_REVIEW",
                artifacts={"code": "def foo(): pass"}
            ))

            # Critic always rejects
            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="Review",
                next_instruction="NEEDS_REVISION",
                artifacts={"feedback": "Not good enough"}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Create something")

            # Should stop after 2 rounds (not approved)
            assert result.next_instruction == "NEEDS_REVISION"
            assert mock_generator.call.call_count == 2
            assert mock_critic.call.call_count == 2

    @pytest.mark.asyncio
    async def test_generator_critic_default_max_rounds(self):
        """Default max_rounds should be 3."""
        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic"
        )

        assert gc.max_rounds == 3


class TestGeneratorCriticFeedbackPassing:
    """Test that feedback is correctly passed between agents."""

    @pytest.mark.asyncio
    async def test_generator_critic_feedback_passed(self):
        """Generator receives critic's feedback in context."""
        gc = GeneratorCritic(
            generator_premise="You generate code.",
            critic_premise="You review code."
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            feedback_received = []

            async def generator_call(return_type, prompt, **kwargs):
                # Capture what feedback was passed
                if "feedback" in kwargs.get("state", HandoffState("", "")).artifacts:
                    feedback_received.append(kwargs["state"].artifacts["feedback"])

                return HandoffState(
                    context="Generated",
                    next_instruction="PENDING_REVIEW",
                    artifacts={"code": "def foo(): return 42"}
                )

            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(side_effect=generator_call)

            # Critic provides feedback, then approves
            critic_outputs = [
                HandoffState(
                    context="Review",
                    next_instruction="NEEDS_REVISION",
                    artifacts={"feedback": "Add docstring"}
                ),
                HandoffState(
                    context="Review",
                    next_instruction="APPROVED",
                    artifacts={"feedback": "Good!"}
                )
            ]

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            await gc.run("Create a function")

            # Generator should have received the feedback
            assert "Add docstring" in feedback_received


class TestGeneratorCriticCustomApproval:
    """Test custom approval checking."""

    @pytest.mark.asyncio
    async def test_generator_critic_custom_approval_check(self):
        """Can provide custom function to check approval."""

        def custom_is_approved(state: HandoffState) -> bool:
            """Custom approval: must have 'quality_score' >= 8"""
            return state.artifacts.get("quality_score", 0) >= 8

        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            is_approved=custom_is_approved
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="Generated",
                next_instruction="",
                artifacts={"code": "def foo(): pass"}
            ))

            # Critic: first score too low, second score passes
            critic_outputs = [
                HandoffState(
                    context="Review",
                    next_instruction="",
                    artifacts={"quality_score": 5}
                ),
                HandoffState(
                    context="Review",
                    next_instruction="",
                    artifacts={"quality_score": 9}
                )
            ]

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Create function")

            # Should have iterated until score >= 8
            assert result.artifacts["quality_score"] == 9
            assert mock_generator.call.call_count == 2
            assert mock_critic.call.call_count == 2

    @pytest.mark.asyncio
    async def test_generator_critic_default_approval_check(self):
        """Default approval check looks for 'APPROVED' in next_instruction."""
        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic"
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="PENDING",
                artifacts={}
            ))

            # First: not approved, Second: approved
            critic_outputs = [
                HandoffState(
                    context="",
                    next_instruction="NEEDS_WORK",
                    artifacts={}
                ),
                HandoffState(
                    context="",
                    next_instruction="APPROVED",
                    artifacts={}
                )
            ]

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Task")

            assert result.next_instruction == "APPROVED"


class TestGeneratorCriticEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_generator_critic_first_attempt_accepted(self):
        """If critic approves first attempt, only 1 round."""
        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic"
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="Perfect code",
                next_instruction="",
                artifacts={"code": "perfect"}
            ))

            # Critic approves immediately
            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="Reviewed",
                next_instruction="APPROVED",
                artifacts={}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Make perfect code")

            # Only 1 generation, 1 critique
            assert mock_generator.call.call_count == 1
            assert mock_critic.call.call_count == 1
            assert result.next_instruction == "APPROVED"

    @pytest.mark.asyncio
    async def test_generator_critic_with_model_selection(self):
        """Can specify different models for generator and critic."""
        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            generator_model="openai:gpt-5",
            critic_model="anthropic:claude-opus-4.5"
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="",
                artifacts={}
            ))

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="APPROVED",
                artifacts={}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            await gc.run("Task")

            # Verify spawn was called with correct models
            calls = mock_spawn.call_args_list
            assert calls[0][1]["model"] == "openai:gpt-5"  # Generator
            assert calls[1][1]["model"] == "anthropic:claude-opus-4.5"  # Critic

    @pytest.mark.asyncio
    async def test_generator_critic_state_accumulation(self):
        """State accumulates across iterations - final result from critic."""
        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic"
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            # Generator adds artifacts each time
            iteration_count = [0]

            async def generator_side_effect(return_type, prompt, **kwargs):
                iteration_count[0] += 1
                state = kwargs.get("state", HandoffState("", ""))

                # Add new artifact each iteration
                new_state = HandoffState(
                    context=f"Iteration {iteration_count[0]}",
                    next_instruction="",
                    artifacts={**state.artifacts, f"attempt_{iteration_count[0]}": True}
                )
                return new_state

            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(side_effect=generator_side_effect)

            # Critic rejects first, approves second - final result includes accumulated artifacts
            critic_outputs = [
                HandoffState(
                    context="",
                    next_instruction="NEEDS_REVISION",
                    artifacts={"feedback": "Try again", "attempt_1": True}
                ),
                HandoffState(
                    context="",
                    next_instruction="APPROVED",
                    artifacts={"attempt_1": True, "attempt_2": True}  # Critic preserves artifacts
                )
            ]

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Task")

            # Final result from critic should include artifacts
            assert result.next_instruction == "APPROVED"
            assert "attempt_1" in result.artifacts
            assert "attempt_2" in result.artifacts


class TestGeneratorCriticInitialization:
    """Test GeneratorCritic initialization and configuration."""

    def test_generator_critic_requires_premises(self):
        """Should require generator_premise and critic_premise."""
        with pytest.raises((ValueError, TypeError)):
            GeneratorCritic()

    def test_generator_critic_with_scope(self):
        """Can pass scope (tools) to generator and critic."""

        def search_tool(query: str) -> str:
            return f"Results for {query}"

        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            generator_scope={"search": search_tool},
            critic_scope={"validate": lambda x: True}
        )

        assert gc.generator_scope == {"search": search_tool}
        assert "validate" in gc.critic_scope

    def test_generator_critic_default_values(self):
        """Test default configuration values."""
        gc = GeneratorCritic(
            generator_premise="Gen",
            critic_premise="Crit"
        )

        assert gc.max_rounds == 3
        assert gc.generator_model is None  # Uses Agentica default
        assert gc.critic_model is None  # Uses Agentica default
        assert gc.is_approved is not None  # Has default approval check


class TestGeneratorCriticBroadcastIntegration:
    """Test Generator/Critic integration with claude_scope broadcasting."""

    @pytest.mark.asyncio
    async def test_generator_critic_with_broadcast_scope(self):
        """Generator/Critic can use broadcast functions from scope."""
        from scripts.agentica_patterns.claude_scope import broadcast_finding, broadcast_done

        gc = GeneratorCritic(
            generator_premise="You generate code and broadcast progress.",
            critic_premise="You review code.",
            generator_scope={
                "broadcast_finding": broadcast_finding,
                "broadcast_done": broadcast_done,
            }
        )

        # Verify scope is set up correctly
        assert "broadcast_finding" in gc.generator_scope
        assert "broadcast_done" in gc.generator_scope

    @pytest.mark.asyncio
    async def test_generator_broadcasts_finding_on_progress(self):
        """Generator broadcasts findings during refinement."""
        findings_broadcast = []

        def mock_broadcast(finding: str, metadata: dict = None):
            findings_broadcast.append({"finding": finding, "metadata": metadata or {}})
            return {"success": True, "broadcast_id": "test-123"}

        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            generator_scope={"broadcast_finding": mock_broadcast}
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            # Generator uses broadcast function during generation
            async def generator_call(return_type, prompt, **kwargs):
                # Simulate generator using the broadcast function from scope
                scope = gc.generator_scope
                if "broadcast_finding" in scope:
                    scope["broadcast_finding"]("Found potential solution")
                return HandoffState(
                    context="Generated",
                    next_instruction="APPROVED",
                    artifacts={"code": "def foo(): pass"}
                )

            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(side_effect=generator_call)

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="Review",
                next_instruction="APPROVED",
                artifacts={}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            await gc.run("Create function")

            # Verify broadcast was called
            assert len(findings_broadcast) == 1
            assert findings_broadcast[0]["finding"] == "Found potential solution"


class TestGeneratorCriticCoordinationDB:
    """Test Generator/Critic integration with CoordinationDB for tracking."""

    @pytest.mark.asyncio
    async def test_generator_critic_with_coordination_db(self):
        """Generator/Critic can use CoordinationDB for agent tracking."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        # Create mock DB
        mock_db = Mock(spec=CoordinationDB)

        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            db=mock_db
        )

        assert gc.db is mock_db

    @pytest.mark.asyncio
    async def test_generator_critic_tracked_spawn(self):
        """Uses tracked_spawn when db is provided."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        mock_db = Mock(spec=CoordinationDB)

        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            db=mock_db
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn, \
             patch('scripts.agentica_patterns.tracked_agent.tracked_spawn') as mock_tracked_spawn:

            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="APPROVED",
                artifacts={}
            ))

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="APPROVED",
                artifacts={}
            ))

            mock_tracked_spawn.side_effect = [mock_generator, mock_critic]

            await gc.run("Task")

            # Verify tracked_spawn was called with db and pattern
            assert mock_tracked_spawn.call_count == 2
            calls = mock_tracked_spawn.call_args_list
            assert calls[0][1]["db"] == mock_db
            assert calls[0][1]["pattern"] == "generator_critic"


class TestGeneratorCriticQualityThreshold:
    """Test quality threshold termination conditions."""

    @pytest.mark.asyncio
    async def test_quality_threshold_numeric(self):
        """Can terminate based on numeric quality threshold."""

        def quality_threshold_check(state: HandoffState) -> bool:
            """Approve if quality_score >= 0.8"""
            return state.artifacts.get("quality_score", 0) >= 0.8

        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            is_approved=quality_threshold_check,
            max_rounds=5
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="",
                artifacts={"code": "..."}
            ))

            # Critic gradually increases quality score
            critic_outputs = [
                HandoffState(
                    context="",
                    next_instruction="",
                    artifacts={"quality_score": 0.5}  # Below threshold
                ),
                HandoffState(
                    context="",
                    next_instruction="",
                    artifacts={"quality_score": 0.7}  # Still below
                ),
                HandoffState(
                    context="",
                    next_instruction="",
                    artifacts={"quality_score": 0.85}  # Above threshold!
                )
            ]

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Task")

            # Should have stopped after 3rd iteration (quality >= 0.8)
            assert mock_generator.call.call_count == 3
            assert mock_critic.call.call_count == 3
            assert result.artifacts["quality_score"] == 0.85

    @pytest.mark.asyncio
    async def test_multiple_termination_conditions(self):
        """Can combine multiple termination conditions."""

        def complex_approval(state: HandoffState) -> bool:
            """Approve if: score >= 0.8 AND no critical issues"""
            score = state.artifacts.get("quality_score", 0)
            has_critical = state.artifacts.get("has_critical_issues", True)
            return score >= 0.8 and not has_critical

        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            is_approved=complex_approval
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="",
                artifacts={}
            ))

            # First: high score but critical issues
            # Second: low score no issues
            # Third: high score no issues
            critic_outputs = [
                HandoffState(
                    context="",
                    next_instruction="",
                    artifacts={"quality_score": 0.9, "has_critical_issues": True}
                ),
                HandoffState(
                    context="",
                    next_instruction="",
                    artifacts={"quality_score": 0.6, "has_critical_issues": False}
                ),
                HandoffState(
                    context="",
                    next_instruction="",
                    artifacts={"quality_score": 0.85, "has_critical_issues": False}
                )
            ]

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Task")

            # Should have stopped after 3rd iteration
            assert mock_generator.call.call_count == 3
            assert result.artifacts["quality_score"] == 0.85
            assert result.artifacts["has_critical_issues"] is False


class TestGeneratorCriticRoundTracking:
    """Test round tracking and iteration metadata."""

    @pytest.mark.asyncio
    async def test_track_iteration_count(self):
        """Can track current iteration number."""
        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic",
            max_rounds=3
        )

        iterations_seen = []

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            async def generator_call(return_type, prompt, **kwargs):
                # Track what prompt was passed
                iterations_seen.append(prompt)
                return HandoffState(
                    context="",
                    next_instruction="",
                    artifacts={}
                )

            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(side_effect=generator_call)

            # Always reject to force max iterations
            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="NEEDS_REVISION",
                artifacts={"feedback": "Try again"}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            await gc.run("Task")

            # Should have 3 iterations
            assert mock_generator.call.call_count == 3

    @pytest.mark.asyncio
    async def test_round_metadata_in_state(self):
        """HandoffState can track round number in metadata."""
        gc = GeneratorCritic(
            generator_premise="Generator",
            critic_premise="Critic"
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            # Generator includes round in metadata
            round_counter = [0]

            async def generator_call(return_type, prompt, **kwargs):
                round_counter[0] += 1
                return HandoffState(
                    context="",
                    next_instruction="",
                    artifacts={},
                    metadata={"round": round_counter[0]}
                )

            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(side_effect=generator_call)

            # Critic preserves metadata and approves on round 2
            critic_outputs = [
                HandoffState(
                    context="",
                    next_instruction="NEEDS_REVISION",
                    artifacts={},
                    metadata={"round": 1}
                ),
                HandoffState(
                    context="",
                    next_instruction="APPROVED",
                    artifacts={},
                    metadata={"round": 2}
                )
            ]

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Task")

            # Final result should have round metadata
            assert result.metadata.get("round") == 2
