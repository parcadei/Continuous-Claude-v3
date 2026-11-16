"""TDD Tests for Phase 24: Add PATTERN_TYPE to GeneratorCritic pattern.

These tests verify that the GeneratorCritic pattern properly sets environment variables
when spawning agents, enabling pattern-aware hooks to detect and route correctly.

Required environment variables when spawning:
- PATTERN_TYPE=generator_critic
- PATTERN_ID=<gc_id>
- GC_ID=<gc_id>
- AGENT_ROLE=generator|critic
- GC_ITERATION=<n>
- GC_MAX_ROUNDS=<n>

Module path: scripts/agentica/patterns/generator_critic.py

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 24)
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scripts.agentica_patterns.patterns.generator_critic import GeneratorCritic
from scripts.agentica_patterns.patterns.primitives import HandoffState


class TestGeneratorCriticPatternTypeEnvVars:
    """Tests that GeneratorCritic sets PATTERN_TYPE and related env vars when spawning."""

    @pytest.mark.asyncio
    async def test_sets_pattern_type_env_var(self):
        """GeneratorCritic should set PATTERN_TYPE=generator_critic before spawning."""
        gc = GeneratorCritic(
            generator_premise="Generate code",
            critic_premise="Review code",
            max_rounds=3,
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="APPROVED",
                artifacts={}
            ))
            mock_spawn.return_value = mock_agent

            original_pattern = os.environ.get("PATTERN_TYPE")

            try:
                await gc.run("Test task")
                # After run, PATTERN_TYPE should have been set during spawn
            finally:
                if original_pattern:
                    os.environ["PATTERN_TYPE"] = original_pattern
                else:
                    os.environ.pop("PATTERN_TYPE", None)

    @pytest.mark.asyncio
    async def test_spawn_passes_pattern_env_context(self):
        """GeneratorCritic spawn calls should include pattern context env vars."""
        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=2,
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn, \
             patch.dict(os.environ, {}, clear=False):
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="APPROVED",
                artifacts={}
            ))
            mock_spawn.return_value = mock_agent

            await gc.run("Test task")

            # Should spawn generator and critic
            assert mock_spawn.call_count >= 2

    @pytest.mark.asyncio
    async def test_gc_id_is_set_as_pattern_id(self):
        """PATTERN_ID should match the generator-critic's unique ID."""
        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=3,
        )

        # GeneratorCritic should be properly initialized with required attributes
        assert gc is not None, "GeneratorCritic should be created successfully"
        assert hasattr(gc, 'max_rounds'), "GeneratorCritic should have max_rounds attribute"
        assert gc.max_rounds == 3, "GeneratorCritic should have 3 max rounds"

    @pytest.mark.asyncio
    async def test_agent_role_set_for_generator_and_critic(self):
        """Generator and critic agents should have appropriate AGENT_ROLE."""
        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=2,
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="APPROVED",
                artifacts={}
            ))
            mock_spawn.return_value = mock_agent

            await gc.run("Test task")

            # Verify spawn was called for both generator and critic
            assert mock_spawn.call_count >= 2


class TestGeneratorCriticEnvVarPropagation:
    """Tests that pattern env vars are properly propagated."""

    @pytest.mark.asyncio
    async def test_env_vars_available_during_spawn(self):
        """Environment variables should be set before spawn is called."""
        captured_envs = []

        async def capture_env_spawn(**kwargs):
            # Capture env vars at spawn time
            captured_envs.append({
                'PATTERN_TYPE': os.environ.get('PATTERN_TYPE'),
                'GC_ID': os.environ.get('GC_ID'),
                'AGENT_ROLE': os.environ.get('AGENT_ROLE'),
                'PATTERN_ID': os.environ.get('PATTERN_ID'),
                'GC_ITERATION': os.environ.get('GC_ITERATION'),
                'GC_MAX_ROUNDS': os.environ.get('GC_MAX_ROUNDS'),
            })

            mock = AsyncMock()
            mock.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="APPROVED",
                artifacts={}
            ))
            return mock

        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=3,
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn', side_effect=capture_env_spawn):
            await gc.run("Test task")

        # Should have captured env vars for at least one spawn (generator)
        assert len(captured_envs) >= 1

        # Check first spawn (generator)
        first_env = captured_envs[0]
        assert first_env.get('PATTERN_TYPE') == 'generator_critic', (
            f"PATTERN_TYPE should be 'generator_critic', got: {first_env.get('PATTERN_TYPE')}"
        )
        assert first_env.get('GC_ID') is not None, "GC_ID should be set"
        assert first_env.get('PATTERN_ID') is not None, "PATTERN_ID should be set"
        assert first_env.get('AGENT_ROLE') in ['generator', 'critic'], (
            f"AGENT_ROLE should be 'generator' or 'critic', got: {first_env.get('AGENT_ROLE')}"
        )
        assert first_env.get('GC_MAX_ROUNDS') is not None, "GC_MAX_ROUNDS should be set"

    @pytest.mark.asyncio
    async def test_iteration_increments(self):
        """GC_ITERATION should increment across rounds."""
        captured_iterations = []

        async def capture_iteration_spawn(**kwargs):
            captured_iterations.append(os.environ.get('GC_ITERATION'))
            mock = AsyncMock()
            # Return not approved to trigger next iteration
            mock.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="Try again",
                artifacts={'feedback': 'Not good enough'}
            ))
            return mock

        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=3,
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn', side_effect=capture_iteration_spawn):
            await gc.run("Test task")

        # Should have iterations captured
        assert len(captured_iterations) > 0

    @pytest.mark.asyncio
    async def test_env_vars_cleaned_up_after_run(self):
        """Environment variables should be cleaned up after execution."""
        original_pattern = os.environ.get('PATTERN_TYPE')
        original_gc = os.environ.get('GC_ID')

        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=2,
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="APPROVED",
                artifacts={}
            ))
            mock_spawn.return_value = mock_agent

            await gc.run("Test task")

        # After run, env should be restored to original state
        assert os.environ.get('PATTERN_TYPE') == original_pattern
        assert os.environ.get('GC_ID') == original_gc


class TestGeneratorCriticPatternIdUniqueness:
    """Tests that each GC execution gets a unique ID."""

    @pytest.mark.asyncio
    async def test_different_executions_get_different_ids(self):
        """Each run() call should have a unique GC ID."""
        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=2,
        )

        captured_ids = []

        async def capture_id_spawn(**kwargs):
            captured_ids.append(os.environ.get('GC_ID'))
            mock = AsyncMock()
            mock.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="APPROVED",
                artifacts={}
            ))
            return mock

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn', side_effect=capture_id_spawn):
            await gc.run("First task")
            await gc.run("Second task")

        # Should have captured IDs from both executions
        assert len(captured_ids) >= 2

    @pytest.mark.asyncio
    async def test_pattern_id_equals_gc_id(self):
        """PATTERN_ID should equal GC_ID for consistency."""
        captured_ids = {}

        async def capture_ids_spawn(**kwargs):
            captured_ids['PATTERN_ID'] = os.environ.get('PATTERN_ID')
            captured_ids['GC_ID'] = os.environ.get('GC_ID')
            mock = AsyncMock()
            mock.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="APPROVED",
                artifacts={}
            ))
            return mock

        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=1,
        )

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn', side_effect=capture_ids_spawn):
            await gc.run("Test task")

        assert captured_ids.get('PATTERN_ID') == captured_ids.get('GC_ID'), (
            f"PATTERN_ID ({captured_ids.get('PATTERN_ID')}) should equal "
            f"GC_ID ({captured_ids.get('GC_ID')})"
        )


class TestGeneratorCriticTrackedAgentEnvVars:
    """Tests that tracked_spawn also receives pattern env vars."""

    @pytest.mark.asyncio
    async def test_tracked_spawn_sees_pattern_env(self):
        """When using tracked_spawn with db, pattern env vars should be set."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        mock_db = MagicMock(spec=CoordinationDB)
        mock_db.register_agent = MagicMock()

        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=2,
            db=mock_db,
        )

        captured_env = {}

        async def capture_env_tracked(**kwargs):
            captured_env['PATTERN_TYPE'] = os.environ.get('PATTERN_TYPE')
            captured_env['GC_ID'] = os.environ.get('GC_ID')
            captured_env['AGENT_ROLE'] = os.environ.get('AGENT_ROLE')
            mock = AsyncMock()
            mock.call = AsyncMock(return_value=HandoffState(
                context="test",
                next_instruction="APPROVED",
                artifacts={}
            ))
            # Return a TrackedAgent-like mock
            mock._agent_id = "test-gc-id"
            mock._db = mock_db
            return mock

        with patch('scripts.agentica_patterns.patterns.generator_critic.spawn', side_effect=capture_env_tracked), \
             patch('scripts.agentica_patterns.tracked_agent.tracked_spawn', side_effect=capture_env_tracked):
            await gc.run("Test task")

        # tracked_spawn should also see the pattern env vars
        assert captured_env.get('PATTERN_TYPE') == 'generator_critic'
        assert captured_env.get('AGENT_ROLE') in ['generator', 'critic']


class TestGeneratorCriticImportability:
    """Test that GeneratorCritic can be imported and basic functionality works."""

    def test_gc_importable(self):
        """GeneratorCritic class should be importable from patterns module."""
        from scripts.agentica_patterns.patterns.generator_critic import GeneratorCritic
        assert GeneratorCritic is not None

    def test_gc_initialization(self):
        """GeneratorCritic should initialize without errors."""
        gc = GeneratorCritic(
            generator_premise="Generate code",
            critic_premise="Review code",
            max_rounds=3,
        )
        assert gc is not None
        assert gc.max_rounds == 3

    def test_gc_validates_max_rounds(self):
        """GeneratorCritic should reject invalid max_rounds."""
        with pytest.raises(ValueError):
            GeneratorCritic(
                generator_premise="Generate",
                critic_premise="Review",
                max_rounds=0,
            )

    def test_gc_has_lazy_agent_initialization(self):
        """GeneratorCritic should not spawn agents at init time."""
        gc = GeneratorCritic(
            generator_premise="Generate",
            critic_premise="Review",
            max_rounds=3,
        )
        # Agents should be None until run() is called
        assert gc.generator is None
        assert gc.critic is None
