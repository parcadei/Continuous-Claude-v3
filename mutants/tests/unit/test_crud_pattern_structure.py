"""Level 3: Pattern Structure Tests - Pattern orchestration logic with mocked spawn.

Tests pattern coordination flow WITHOUT real LLM calls.
Mock `spawn` and `Agent.call` to control deterministic responses.

Reference: tests/unit/test_agentica_swarm.py for mock patterns.
"""

import pytest
from unittest.mock import AsyncMock, patch
from scripts.agentica.patterns import Swarm, Hierarchical, GeneratorCritic, AggregateMode
from scripts.agentica.primitives import HandoffState

# Pattern modules where spawn is imported
SWARM_SPAWN = 'scripts.agentica.patterns.swarm.spawn'
HIERARCHICAL_SPAWN = 'scripts.agentica.patterns.hierarchical.spawn'
GENERATOR_CRITIC_SPAWN = 'scripts.agentica.patterns.generator_critic.spawn'


# ============================================================================
# Swarm Pattern Tests
# ============================================================================


class TestSwarmSpawnsCorrectNumberOfAgents:
    """Test that swarm spawns correct number of agents."""

    @pytest.mark.asyncio
    async def test_swarm_spawns_correct_number_of_agents(self):
        """Swarm should spawn exactly N agents for N perspectives."""
        perspectives = [
            "Security expert perspective",
            "Performance expert perspective",
            "UX expert perspective",
        ]
        swarm = Swarm(perspectives=perspectives)

        with patch(SWARM_SPAWN) as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"result": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Analyze feature")

            # Verify spawn called exactly 3 times
            assert mock_spawn.call_count == 3

    @pytest.mark.asyncio
    async def test_swarm_spawns_five_agents_for_five_perspectives(self):
        """Swarm with 5 perspectives spawns 5 agents."""
        perspectives = [f"Expert {i}" for i in range(5)]
        swarm = Swarm(perspectives=perspectives)

        with patch(SWARM_SPAWN) as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"result": "x"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Query")

            assert mock_spawn.call_count == 5


class TestSwarmPassesPerspectivesToAgents:
    """Test that each agent receives unique perspective."""

    @pytest.mark.asyncio
    async def test_swarm_passes_perspectives_to_agents(self):
        """Each spawn call should receive a unique perspective as premise."""
        perspectives = [
            "You focus on security risks.",
            "You focus on scalability.",
            "You focus on usability."
        ]
        swarm = Swarm(perspectives=perspectives)

        with patch(SWARM_SPAWN) as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"insight": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Analyze feature")

            # Extract premises from spawn calls
            calls = mock_spawn.call_args_list
            premises_passed = [call.kwargs.get('premise') for call in calls]

            # Verify all perspectives were passed
            for perspective in perspectives:
                assert perspective in premises_passed

    @pytest.mark.asyncio
    async def test_swarm_perspectives_are_distinct(self):
        """Each agent gets a different premise."""
        perspectives = ["A", "B", "C"]
        swarm = Swarm(perspectives=perspectives)

        with patch(SWARM_SPAWN) as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Query")

            premises = [call.kwargs.get('premise') for call in mock_spawn.call_args_list]
            # Should have 3 distinct premises
            assert len(set(premises)) == 3


class TestSwarmAggregatesResults:
    """Test that swarm aggregates results from all agents."""

    @pytest.mark.asyncio
    async def test_swarm_aggregates_results(self):
        """MERGE mode combines all agent results into single dict."""
        swarm = Swarm(
            perspectives=["A", "B", "C"],
            aggregate_mode=AggregateMode.MERGE
        )

        with patch(SWARM_SPAWN) as mock_spawn:
            # Create separate agents returning different keys
            agents = []
            for result in [{"key1": "val1"}, {"key2": "val2"}, {"key3": "val3"}]:
                agent = AsyncMock()
                agent.call = AsyncMock(return_value=result)
                agents.append(agent)

            mock_spawn.side_effect = agents

            result = await swarm.execute("Query")

            # MERGE should combine all dicts
            assert result == {"key1": "val1", "key2": "val2", "key3": "val3"}

    @pytest.mark.asyncio
    async def test_swarm_aggregates_with_concat_mode(self):
        """CONCAT mode joins string results."""
        swarm = Swarm(
            perspectives=["A", "B"],
            aggregate_mode=AggregateMode.CONCAT,
            aggregation_separator=" | "
        )

        with patch(SWARM_SPAWN) as mock_spawn:
            agent1 = AsyncMock()
            agent1.call = AsyncMock(return_value="First insight")
            agent2 = AsyncMock()
            agent2.call = AsyncMock(return_value="Second insight")

            mock_spawn.side_effect = [agent1, agent2]

            result = await swarm.execute("Query")

            assert "First insight" in result
            assert "Second insight" in result


class TestSwarmHandlesAgentFailure:
    """Test swarm error handling."""

    @pytest.mark.asyncio
    async def test_swarm_handles_agent_failure(self):
        """Non-fail-fast mode continues with partial results."""
        swarm = Swarm(
            perspectives=["A", "B", "C"],
            fail_fast=False
        )

        with patch(SWARM_SPAWN) as mock_spawn:
            agent1 = AsyncMock()
            agent1.call = AsyncMock(return_value={"result": "A"})

            agent2 = AsyncMock()
            agent2.call = AsyncMock(side_effect=Exception("Agent B failed"))

            agent3 = AsyncMock()
            agent3.call = AsyncMock(return_value={"result": "C"})

            mock_spawn.side_effect = [agent1, agent2, agent3]

            result = await swarm.execute("Query")

            # Should have results from agents that succeeded
            assert result is not None
            # Merged dict should contain A and C results
            assert "result" in result

    @pytest.mark.asyncio
    async def test_swarm_fail_fast_propagates_error(self):
        """Fail-fast mode raises on first failure."""
        swarm = Swarm(
            perspectives=["A", "B", "C"],
            fail_fast=True
        )

        with patch(SWARM_SPAWN) as mock_spawn:
            agent1 = AsyncMock()
            agent1.call = AsyncMock(return_value={"result": "A"})

            agent2 = AsyncMock()
            agent2.call = AsyncMock(side_effect=ValueError("Agent B failed"))

            agent3 = AsyncMock()
            agent3.call = AsyncMock(return_value={"result": "C"})

            mock_spawn.side_effect = [agent1, agent2, agent3]

            with pytest.raises(ValueError, match="Agent B failed"):
                await swarm.execute("Query")


# ============================================================================
# Hierarchical Pattern Tests
# ============================================================================


class TestHierarchicalCoordinatorDecomposes:
    """Test coordinator task decomposition."""

    @pytest.mark.asyncio
    async def test_hierarchical_coordinator_decomposes(self):
        """Coordinator decomposes task into subtasks."""
        hierarchical = Hierarchical(
            coordinator_premise="You decompose tasks.",
            specialist_premises={
                "researcher": "You research.",
                "analyst": "You analyze."
            }
        )

        with patch(HIERARCHICAL_SPAWN) as mock_spawn:
            mock_coordinator = AsyncMock()
            # Coordinator returns decomposition
            mock_coordinator.call = AsyncMock(return_value=[
                {"specialist": "researcher", "task": "Research topic X"},
                {"specialist": "analyst", "task": "Analyze findings"}
            ])
            mock_spawn.return_value = mock_coordinator

            subtasks = await hierarchical._decompose_task("Research and analyze X")

            # Should return list of subtasks
            assert isinstance(subtasks, list)
            assert len(subtasks) == 2
            assert subtasks[0]["specialist"] == "researcher"
            assert subtasks[1]["specialist"] == "analyst"

    @pytest.mark.asyncio
    async def test_hierarchical_decompose_prompt_contains_specialists(self):
        """Decomposition prompt includes specialist names."""
        hierarchical = Hierarchical(
            coordinator_premise="You coordinate.",
            specialist_premises={
                "security_expert": "Security analysis.",
                "perf_expert": "Performance analysis."
            }
        )

        with patch(HIERARCHICAL_SPAWN) as mock_spawn:
            mock_coordinator = AsyncMock()
            mock_coordinator.call = AsyncMock(return_value=[])
            mock_spawn.return_value = mock_coordinator

            await hierarchical._decompose_task("Analyze system")

            # Check the prompt passed to coordinator.call
            call_args = mock_coordinator.call.call_args
            prompt = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get('prompt', '')

            # Prompt should mention available specialists
            assert "security_expert" in prompt or "perf_expert" in prompt


class TestHierarchicalRoutesToSpecialists:
    """Test routing to specialist agents."""

    @pytest.mark.asyncio
    async def test_hierarchical_routes_to_specialists(self):
        """Subtasks are routed to correct specialists."""
        hierarchical = Hierarchical(
            coordinator_premise="You coordinate.",
            specialist_premises={
                "researcher": "You research topics.",
                "writer": "You write summaries."
            }
        )

        with patch(HIERARCHICAL_SPAWN) as mock_spawn:
            mock_researcher = AsyncMock()
            mock_researcher.call = AsyncMock(return_value="Research findings")

            mock_writer = AsyncMock()
            mock_writer.call = AsyncMock(return_value="Written summary")

            # Track which agents are spawned
            spawned_premises = []

            async def spawn_side_effect(premise, **kwargs):
                spawned_premises.append(premise)
                if "research" in premise.lower():
                    return mock_researcher
                elif "write" in premise.lower():
                    return mock_writer
                return AsyncMock()

            mock_spawn.side_effect = spawn_side_effect

            subtasks = [
                {"specialist": "researcher", "task": "Find info"},
                {"specialist": "writer", "task": "Write summary"}
            ]

            results = await hierarchical._execute_subtasks(subtasks)

            # Both specialists should have been spawned
            assert len(results) == 2
            assert "Research findings" in results
            assert "Written summary" in results


class TestHierarchicalSynthesizesResults:
    """Test coordinator synthesis of specialist results."""

    @pytest.mark.asyncio
    async def test_hierarchical_synthesizes_results(self):
        """Coordinator synthesizes aggregated results into final answer."""
        hierarchical = Hierarchical(
            coordinator_premise="You synthesize results.",
            specialist_premises={"worker": "You work."}
        )

        with patch(HIERARCHICAL_SPAWN) as mock_spawn:
            mock_coordinator = AsyncMock()
            # Synthesis call
            mock_coordinator.call = AsyncMock(return_value="Final synthesized answer")
            mock_spawn.return_value = mock_coordinator

            result = await hierarchical._synthesize(
                task="Complete analysis",
                aggregated_results="Result A. Result B."
            )

            assert result == "Final synthesized answer"
            # Synthesis prompt should include aggregated results
            call_args = mock_coordinator.call.call_args
            prompt = call_args.args[1] if len(call_args.args) > 1 else ""
            assert "Result A" in prompt or "Result B" in prompt


class TestHierarchicalHandlesEmptyDecomposition:
    """Test handling of empty decomposition (simple task)."""

    @pytest.mark.asyncio
    async def test_hierarchical_handles_empty_decomposition(self):
        """If coordinator returns empty list, task answered directly."""
        hierarchical = Hierarchical(
            coordinator_premise="You coordinate.",
            specialist_premises={"worker": "You work."}
        )

        with patch(HIERARCHICAL_SPAWN) as mock_spawn:
            mock_coordinator = AsyncMock()
            # First call: decompose returns empty (simple task)
            # Second call: direct answer
            mock_coordinator.call = AsyncMock(side_effect=[
                [],  # Empty decomposition
                "Direct answer"  # Direct response
            ])
            mock_spawn.return_value = mock_coordinator

            result = await hierarchical.execute("What is 2+2?")

            # Should get direct answer without specialists
            assert result == "Direct answer"
            # Coordinator called twice: decompose + direct answer
            assert mock_coordinator.call.call_count == 2


# ============================================================================
# GeneratorCritic Pattern Tests
# ============================================================================


class TestGeneratorCriticLoopsUntilApproved:
    """Test generator/critic iteration loop."""

    @pytest.mark.asyncio
    async def test_generator_critic_loops_until_approved(self):
        """Loop continues until critic approves."""
        gc = GeneratorCritic(
            generator_premise="You generate code.",
            critic_premise="You review code.",
            max_rounds=5
        )

        with patch(GENERATOR_CRITIC_SPAWN) as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="Generated",
                next_instruction="PENDING",
                artifacts={"code": "def foo(): pass"}
            ))

            # Critic rejects first, approves second
            critic_outputs = [
                HandoffState(
                    context="Review 1",
                    next_instruction="NEEDS_REVISION",
                    artifacts={"feedback": "Add docstring"}
                ),
                HandoffState(
                    context="Review 2",
                    next_instruction="APPROVED",
                    artifacts={"feedback": "Looks good!"}
                )
            ]
            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Create function")

            # Should be approved after 2 rounds
            assert "APPROVED" in result.next_instruction
            assert mock_generator.call.call_count == 2
            assert mock_critic.call.call_count == 2


class TestGeneratorCriticPassesFeedback:
    """Test feedback passing between generator and critic."""

    @pytest.mark.asyncio
    async def test_generator_critic_passes_feedback(self):
        """Generator receives critic's feedback in subsequent rounds."""
        gc = GeneratorCritic(
            generator_premise="You generate.",
            critic_premise="You critique."
        )

        prompts_received = []

        async def generator_side_effect(return_type, prompt, **kwargs):
            prompts_received.append(prompt)
            return HandoffState(
                context="Generated",
                next_instruction="",
                artifacts={"code": "result"}
            )

        with patch(GENERATOR_CRITIC_SPAWN) as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(side_effect=generator_side_effect)

            critic_outputs = [
                HandoffState(
                    context="",
                    next_instruction="NEEDS_REVISION",
                    artifacts={"feedback": "Add error handling"}
                ),
                HandoffState(
                    context="",
                    next_instruction="APPROVED",
                    artifacts={"feedback": "Good!"}
                )
            ]
            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=critic_outputs)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            await gc.run("Create function")

            # Second generator prompt should mention the feedback
            assert len(prompts_received) >= 2
            second_prompt = prompts_received[1]
            assert "Add error handling" in second_prompt


class TestGeneratorCriticRespectsMaxRounds:
    """Test max_rounds enforcement."""

    @pytest.mark.asyncio
    async def test_generator_critic_respects_max_rounds(self):
        """Loop stops after max_rounds even if not approved."""
        gc = GeneratorCritic(
            generator_premise="You generate.",
            critic_premise="You critique.",
            max_rounds=2
        )

        with patch(GENERATOR_CRITIC_SPAWN) as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="",
                artifacts={"code": "attempt"}
            ))

            # Critic always rejects
            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="NEEDS_REVISION",
                artifacts={"feedback": "Not good enough"}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Create function")

            # Should stop after 2 rounds (max_rounds)
            assert "NEEDS_REVISION" in result.next_instruction
            assert mock_generator.call.call_count == 2
            assert mock_critic.call.call_count == 2


class TestGeneratorCriticReturnsFinalState:
    """Test that final state includes all artifacts."""

    @pytest.mark.asyncio
    async def test_generator_critic_returns_final_state(self):
        """Final state contains accumulated artifacts."""
        gc = GeneratorCritic(
            generator_premise="You generate.",
            critic_premise="You critique."
        )

        with patch(GENERATOR_CRITIC_SPAWN) as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="Generated code",
                next_instruction="PENDING",
                artifacts={"code": "def foo(): return 42", "language": "python"}
            ))

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="Review complete",
                next_instruction="APPROVED",
                artifacts={"code": "def foo(): return 42", "approved": True, "feedback": "Perfect!"}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Create function")

            # Final state should be from critic with all artifacts
            assert result.next_instruction == "APPROVED"
            assert result.artifacts.get("approved") is True
            assert "feedback" in result.artifacts


# ============================================================================
# Edge Cases and Integration
# ============================================================================


class TestPatternModelPropagation:
    """Test that model settings propagate correctly."""

    @pytest.mark.asyncio
    async def test_swarm_propagates_model(self):
        """Swarm passes model to all spawned agents."""
        swarm = Swarm(
            perspectives=["A", "B"],
            model="anthropic:claude-opus-4"
        )

        with patch(SWARM_SPAWN) as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Query")

            # All spawn calls should have the model
            for call in mock_spawn.call_args_list:
                assert call.kwargs.get('model') == "anthropic:claude-opus-4"

    @pytest.mark.asyncio
    async def test_hierarchical_propagates_models(self):
        """Hierarchical passes different models to coordinator and specialists."""
        hierarchical = Hierarchical(
            coordinator_premise="Coordinate.",
            specialist_premises={"worker": "Work."},
            coordinator_model="anthropic:claude-opus-4",
            specialist_model="openai:gpt-4"
        )

        assert hierarchical.coordinator_model == "anthropic:claude-opus-4"
        assert hierarchical.specialist_model == "openai:gpt-4"


class TestPatternScopePropagation:
    """Test that scope (tools) propagate correctly."""

    @pytest.mark.asyncio
    async def test_swarm_propagates_scope(self):
        """Swarm passes scope to all spawned agents."""
        def my_tool(x: str) -> str:
            return f"processed: {x}"

        swarm = Swarm(
            perspectives=["A", "B"],
            scope={"my_tool": my_tool}
        )

        with patch(SWARM_SPAWN) as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Query")

            # All spawn calls should have the scope
            for call in mock_spawn.call_args_list:
                assert "scope" in call.kwargs
                assert "my_tool" in call.kwargs["scope"]
