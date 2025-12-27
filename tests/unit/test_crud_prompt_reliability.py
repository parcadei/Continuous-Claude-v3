"""Level 4: Prompt Reliability Tests - Verify prompts contain expected elements.

Tests that prompts produce predictable, parseable outputs.
Verifies prompt engineering without making real LLM calls.

Reference: .claude/skills/agentica-prompts/SKILL.md for expected formats.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from scripts.agentica.patterns import Hierarchical, GeneratorCritic, Swarm
from scripts.agentica.primitives import HandoffState
from scripts.agentica.agent_handoff import AgentHandoff

# Pattern modules where spawn is imported
SWARM_SPAWN = 'scripts.agentica.patterns.swarm.spawn'
HIERARCHICAL_SPAWN = 'scripts.agentica.patterns.hierarchical.spawn'
GENERATOR_CRITIC_SPAWN = 'scripts.agentica.patterns.generator_critic.spawn'


# ============================================================================
# Coordinator Prompt Tests
# ============================================================================


class TestCoordinatorPromptContainsSpecialistNames:
    """Test that coordinator prompts include specialist names."""

    @pytest.mark.asyncio
    async def test_coordinator_prompt_contains_specialist_names(self):
        """Coordinator's decomposition prompt lists available specialists."""
        hierarchical = Hierarchical(
            coordinator_premise="You coordinate.",
            specialist_premises={
                "security_auditor": "Security analysis.",
                "performance_analyst": "Performance analysis.",
                "ux_reviewer": "UX review."
            }
        )

        captured_prompt = None

        async def capture_call(return_type, prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return []  # Empty decomposition

        with patch(HIERARCHICAL_SPAWN) as mock_spawn:
            mock_coordinator = AsyncMock()
            mock_coordinator.call = AsyncMock(side_effect=capture_call)
            mock_spawn.return_value = mock_coordinator

            await hierarchical._decompose_task("Analyze the system")

            # Prompt should contain all specialist names
            assert captured_prompt is not None
            assert "security_auditor" in captured_prompt
            assert "performance_analyst" in captured_prompt
            assert "ux_reviewer" in captured_prompt

    @pytest.mark.asyncio
    async def test_coordinator_prompt_format_for_specialist_routing(self):
        """Coordinator prompt should ask for {specialist, task} format."""
        hierarchical = Hierarchical(
            coordinator_premise="You coordinate.",
            specialist_premises={
                "researcher": "Research.",
                "writer": "Write."
            }
        )

        captured_prompt = None

        async def capture_call(return_type, prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return []

        with patch(HIERARCHICAL_SPAWN) as mock_spawn:
            mock_coordinator = AsyncMock()
            mock_coordinator.call = AsyncMock(side_effect=capture_call)
            mock_spawn.return_value = mock_coordinator

            await hierarchical._decompose_task("Do something")

            # Prompt should mention expected output format
            assert captured_prompt is not None
            assert "specialist" in captured_prompt.lower()
            assert "task" in captured_prompt.lower()


# ============================================================================
# Critic Output Format Tests
# ============================================================================


class TestCriticOutputFormatValidated:
    """Test critic output format expectations."""

    @pytest.mark.asyncio
    async def test_critic_output_format_validated(self):
        """Critic returns HandoffState with expected fields."""
        gc = GeneratorCritic(
            generator_premise="You generate.",
            critic_premise="""You review code.
Return HandoffState with:
- next_instruction: "APPROVED" or "NEEDS_REVISION"
- artifacts containing: approved (bool), feedback (str)
"""
        )

        with patch(GENERATOR_CRITIC_SPAWN) as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="Generated",
                next_instruction="PENDING",
                artifacts={"code": "def foo(): pass"}
            ))

            # Properly formatted critic response
            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="Review complete",
                next_instruction="APPROVED",
                artifacts={"approved": True, "feedback": "Code is correct"}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Create function")

            # Verify structured output
            assert "approved" in result.artifacts
            assert isinstance(result.artifacts["approved"], bool)
            assert "feedback" in result.artifacts
            assert isinstance(result.artifacts["feedback"], str)

    @pytest.mark.asyncio
    async def test_critic_feedback_accessible_in_artifacts(self):
        """Feedback stored in artifacts for next iteration."""
        gc = GeneratorCritic(
            generator_premise="You generate.",
            critic_premise="You review."
        )

        with patch(GENERATOR_CRITIC_SPAWN) as mock_spawn:
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
                artifacts={"feedback": "Add type hints", "approved": True}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            result = await gc.run("Create function")

            # Feedback should be in final artifacts
            assert result.artifacts.get("feedback") == "Add type hints"


# ============================================================================
# Handoff Directory Chain Tests
# ============================================================================


class TestHandoffDirectoryChainWorks:
    """Test directory-based handoff mechanism."""

    def test_handoff_creates_output_directory(self, tmp_path):
        """get_output_dir creates phase directory."""
        handoff = AgentHandoff(session_id="test-session", base_dir=tmp_path)

        output_dir = handoff.get_output_dir("research")

        assert output_dir.exists()
        assert output_dir.is_dir()
        assert (output_dir / "artifacts").exists()

    def test_handoff_chain_from_returns_upstream_path(self, tmp_path):
        """chain_from returns correct upstream directory."""
        handoff = AgentHandoff(session_id="test-session", base_dir=tmp_path)

        # Create upstream phase output
        research_dir = handoff.get_output_dir("research")
        handoff.write_summary("research", "Research findings here")

        # Downstream reads from upstream
        upstream_path = handoff.chain_from("research")

        assert upstream_path == tmp_path / "test-session" / "research"
        assert (upstream_path / "summary.md").exists()

    def test_handoff_write_read_summary_roundtrip(self, tmp_path):
        """Write and read summary works correctly."""
        handoff = AgentHandoff(session_id="test-session", base_dir=tmp_path)

        # Write summary
        handoff.write_summary("research", "Key finding: X is true")

        # Read summary
        content = handoff.read_summary("research")

        assert content is not None
        assert "Key finding: X is true" in content

    def test_handoff_artifacts_directory_created(self, tmp_path):
        """Artifacts directory created with phase."""
        handoff = AgentHandoff(session_id="test-session", base_dir=tmp_path)

        output_dir = handoff.get_output_dir("implement")

        artifacts_dir = output_dir / "artifacts"
        assert artifacts_dir.exists()
        assert artifacts_dir.is_dir()

    def test_handoff_downstream_reads_upstream(self, tmp_path):
        """Downstream phase can read upstream summary."""
        handoff = AgentHandoff(session_id="test-session", base_dir=tmp_path)

        # Phase 1: Research writes
        handoff.write_summary("research", "Found patterns A, B, C")

        # Phase 2: Plan reads research
        research_summary = handoff.read_summary("research")

        assert research_summary is not None
        assert "patterns A, B, C" in research_summary

        # Plan writes its own summary
        handoff.write_summary("plan", f"Based on research: {research_summary[:50]}")

        # Phase 3: Implement reads plan
        plan_summary = handoff.read_summary("plan")
        assert plan_summary is not None
        assert "Based on research" in plan_summary


# ============================================================================
# Swarm Perspective in Agent Premise Tests
# ============================================================================


class TestSwarmPerspectiveInAgentPremise:
    """Test that swarm perspectives appear in agent premises."""

    @pytest.mark.asyncio
    async def test_swarm_perspective_in_agent_premise(self):
        """Each swarm agent's premise contains its unique perspective."""
        perspectives = [
            "Focus on security risks and vulnerabilities.",
            "Focus on performance bottlenecks.",
            "Focus on user experience issues."
        ]

        swarm = Swarm(perspectives=perspectives)

        captured_premises = []

        with patch(SWARM_SPAWN) as mock_spawn:
            async def capture_spawn(premise, **kwargs):
                captured_premises.append(premise)
                mock_agent = AsyncMock()
                mock_agent.call = AsyncMock(return_value={"result": "x"})
                return mock_agent

            mock_spawn.side_effect = capture_spawn

            await swarm.execute("Analyze system")

            # Each perspective should be in a premise
            for perspective in perspectives:
                assert perspective in captured_premises


# ============================================================================
# System Prompt Memory Context Tests
# ============================================================================


class TestSystemPromptContainsMemoryContext:
    """Test that system prompts include memory context."""

    def test_build_system_prompt_includes_memory_context(self, tmp_path):
        """System prompt includes memory documentation."""
        handoff = AgentHandoff(session_id="test-session", base_dir=tmp_path)

        memory_context = handoff.get_memory_context()
        system_prompt = handoff.build_system_prompt(
            agent_role="Researcher",
            phase="research",
            task="Find relevant information",
            memory_context=memory_context
        )

        # Should include memory system docs
        assert "remember(key, value)" in system_prompt
        assert "recall(query)" in system_prompt
        assert "store_fact" in system_prompt
        assert "search_memory" in system_prompt
        assert "test-session" in system_prompt  # Session ID

    def test_system_prompt_contains_directory_handoff(self, tmp_path):
        """System prompt includes directory handoff instructions."""
        handoff = AgentHandoff(session_id="test-session", base_dir=tmp_path)

        system_prompt = handoff.build_system_prompt(
            agent_role="Planner",
            phase="plan",
            task="Create implementation plan",
            upstream="research",
            downstream="implement"
        )

        # Should mention directory handoff
        assert "summary.md" in system_prompt
        assert "artifacts" in system_prompt
        assert "research" in system_prompt  # Upstream
        assert "implement" in system_prompt  # Downstream

    def test_system_prompt_includes_agent_identity(self, tmp_path):
        """System prompt includes agent role and phase."""
        handoff = AgentHandoff(session_id="my-session", base_dir=tmp_path)

        system_prompt = handoff.build_system_prompt(
            agent_role="Security Auditor",
            phase="audit",
            task="Review for vulnerabilities"
        )

        assert "Security Auditor" in system_prompt
        assert "audit" in system_prompt
        assert "my-session" in system_prompt

    def test_system_prompt_includes_critical_rules(self, tmp_path):
        """System prompt includes critical agent rules."""
        handoff = AgentHandoff(session_id="test", base_dir=tmp_path)

        system_prompt = handoff.build_system_prompt(
            agent_role="Agent",
            phase="work",
            task="Do work"
        )

        # Should have critical rules about RETRIEVE vs WRITE
        assert "RETRIEVE" in system_prompt
        assert "WRITE" in system_prompt


# ============================================================================
# Pattern Prompt Structure Tests
# ============================================================================


class TestPatternPromptStructure:
    """Test pattern-specific prompt structures."""

    @pytest.mark.asyncio
    async def test_generator_receives_task_in_prompt(self):
        """Generator prompt includes the original task."""
        gc = GeneratorCritic(
            generator_premise="You generate solutions.",
            critic_premise="You review solutions."
        )

        captured_prompts = []

        async def capture_generator_call(return_type, prompt, **kwargs):
            captured_prompts.append(prompt)
            return HandoffState(context="", next_instruction="", artifacts={})

        with patch(GENERATOR_CRITIC_SPAWN) as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(side_effect=capture_generator_call)

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(return_value=HandoffState(
                context="",
                next_instruction="APPROVED",
                artifacts={}
            ))

            mock_spawn.side_effect = [mock_generator, mock_critic]

            await gc.run("Implement OAuth login flow")

            # Generator prompt should contain the task
            assert len(captured_prompts) >= 1
            assert "OAuth" in captured_prompts[0] or "login" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_critic_receives_solution_in_prompt(self):
        """Critic prompt includes generator's solution."""
        gc = GeneratorCritic(
            generator_premise="You generate.",
            critic_premise="You critique."
        )

        captured_critic_prompts = []

        async def capture_critic_call(return_type, prompt, **kwargs):
            captured_critic_prompts.append(prompt)
            return HandoffState(context="", next_instruction="APPROVED", artifacts={})

        with patch(GENERATOR_CRITIC_SPAWN) as mock_spawn:
            mock_generator = AsyncMock()
            mock_generator.call = AsyncMock(return_value=HandoffState(
                context="Generated solution",
                next_instruction="PENDING",
                artifacts={"code": "def authenticate(): pass"}
            ))

            mock_critic = AsyncMock()
            mock_critic.call = AsyncMock(side_effect=capture_critic_call)

            mock_spawn.side_effect = [mock_generator, mock_critic]

            await gc.run("Create auth function")

            # Critic prompt should mention the solution
            assert len(captured_critic_prompts) >= 1
            critic_prompt = captured_critic_prompts[0]
            assert "code" in critic_prompt.lower() or "authenticate" in critic_prompt


# ============================================================================
# Handoff Artifact Tests
# ============================================================================


class TestHandoffArtifacts:
    """Test artifact handling in handoffs."""

    def test_write_and_read_artifact(self, tmp_path):
        """Artifacts can be written and read back."""
        handoff = AgentHandoff(session_id="test", base_dir=tmp_path)

        # Write artifact
        handoff.write_artifact("research", "findings.json", '{"key": "value"}')

        # Read artifact
        content = handoff.read_artifact("research", "findings.json")

        assert content == '{"key": "value"}'

    def test_list_artifacts(self, tmp_path):
        """Can list all artifacts in a phase."""
        handoff = AgentHandoff(session_id="test", base_dir=tmp_path)

        # Write multiple artifacts
        handoff.write_artifact("research", "data.json", "{}")
        handoff.write_artifact("research", "notes.md", "# Notes")
        handoff.write_artifact("research", "findings.txt", "Finding 1")

        # List artifacts
        artifacts = handoff.list_artifacts("research")

        assert len(artifacts) == 3
        assert "data.json" in artifacts
        assert "notes.md" in artifacts
        assert "findings.txt" in artifacts

    def test_read_nonexistent_artifact_returns_none(self, tmp_path):
        """Reading nonexistent artifact returns None."""
        handoff = AgentHandoff(session_id="test", base_dir=tmp_path)
        handoff.get_output_dir("research")  # Create phase dir

        result = handoff.read_artifact("research", "nonexistent.txt")

        assert result is None
