"""Tests for pattern + coordination integration."""

import pytest
from unittest.mock import AsyncMock, patch


class TestSwarmCoordination:
    """Test Swarm pattern with coordination DB."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

    @pytest.mark.asyncio
    async def test_swarm_registers_all_agents(self, mock_db):
        """Swarm should register one agent per perspective."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value={"analysis": "done"})

        with patch("scripts.agentica.patterns.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                from scripts.agentica.patterns import Swarm

                swarm = Swarm(
                    perspectives=["Expert A", "Expert B", "Expert C"],
                    db=mock_db,
                )
                await swarm.execute("Analyze this")

                summary = mock_db.get_session_summary()
                assert summary["agents_by_pattern"].get("swarm", 0) == 3

    @pytest.mark.asyncio
    async def test_swarm_works_without_db(self):
        """Swarm should work without DB (backward compatibility)."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value={"analysis": "done"})

        with patch("scripts.agentica.patterns.spawn", return_value=mock_agent):
            from scripts.agentica.patterns import Swarm

            swarm = Swarm(
                perspectives=["Expert A", "Expert B"],
                db=None,
            )
            result = await swarm.execute("Analyze this")

            # Should get aggregated results
            assert result is not None


class TestHierarchicalCoordination:
    """Test Hierarchical pattern with coordination DB."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

    @pytest.mark.asyncio
    async def test_hierarchical_registers_coordinator_and_specialists(self, mock_db):
        """Hierarchical should register coordinator and specialists."""
        mock_agent = AsyncMock()
        # Coordinator returns empty list (no delegation needed)
        mock_agent.call = AsyncMock(return_value=[])

        with patch("scripts.agentica.patterns.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                from scripts.agentica.patterns import Hierarchical

                hierarchical = Hierarchical(
                    coordinator_premise="You coordinate",
                    specialist_premises={
                        "researcher": "You research",
                        "analyst": "You analyze",
                    },
                    db=mock_db,
                )
                await hierarchical.execute("Simple task")

                summary = mock_db.get_session_summary()
                # Should have at least coordinator registered
                assert summary["agents_by_pattern"].get("hierarchical", 0) >= 1

    @pytest.mark.asyncio
    async def test_hierarchical_works_without_db(self):
        """Hierarchical should work without DB (backward compatibility)."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value=[])

        with patch("scripts.agentica.patterns.spawn", return_value=mock_agent):
            from scripts.agentica.patterns import Hierarchical

            hierarchical = Hierarchical(
                coordinator_premise="You coordinate",
                specialist_premises={"researcher": "You research"},
                db=None,
            )
            result = await hierarchical.execute("Simple task")

            # Should complete without error
            assert result is not None


class TestJuryCoordination:
    """Test Jury pattern with coordination DB."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

    @pytest.mark.asyncio
    async def test_jury_registers_all_jurors(self, mock_db):
        """Jury should register one agent per juror."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value=True)

        with patch("scripts.agentica.patterns.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                from scripts.agentica.patterns import Jury, ConsensusMode

                jury = Jury(
                    num_jurors=5,
                    consensus_mode=ConsensusMode.MAJORITY,
                    db=mock_db,
                )
                await jury.decide(bool, "Is this correct?")

                summary = mock_db.get_session_summary()
                assert summary["agents_by_pattern"].get("jury", 0) == 5

    @pytest.mark.asyncio
    async def test_jury_works_without_db(self):
        """Jury should work without DB (backward compatibility)."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value=True)

        with patch("scripts.agentica.patterns.spawn", return_value=mock_agent):
            from scripts.agentica.patterns import Jury, ConsensusMode

            jury = Jury(
                num_jurors=3,
                consensus_mode=ConsensusMode.MAJORITY,
                db=None,
            )
            result = await jury.decide(bool, "Is this correct?")

            # Should get consensus result
            assert result is True


class TestGeneratorCriticCoordination:
    """Test GeneratorCritic pattern with coordination DB."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        from scripts.agentica.coordination import CoordinationDB
        return CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

    @pytest.mark.asyncio
    async def test_generator_critic_registers_both_agents(self, mock_db):
        """GeneratorCritic should register generator and critic."""
        from scripts.agentica.primitives import HandoffState

        mock_agent = AsyncMock()
        # First call (generator) returns state, second call (critic) approves
        mock_agent.call = AsyncMock(
            side_effect=[
                HandoffState(context="test", next_instruction="generated"),
                HandoffState(context="test", next_instruction="APPROVED"),
            ]
        )

        with patch("scripts.agentica.patterns.spawn", return_value=mock_agent):
            with patch("scripts.agentica.tracked_agent.spawn", return_value=mock_agent):
                from scripts.agentica.patterns import GeneratorCritic

                gc = GeneratorCritic(
                    generator_premise="You generate",
                    critic_premise="You critique",
                    db=mock_db,
                )
                await gc.run("Create something")

                summary = mock_db.get_session_summary()
                # Should have 2 agents (generator + critic)
                assert summary["agents_by_pattern"].get("generator_critic", 0) == 2

    @pytest.mark.asyncio
    async def test_generator_critic_works_without_db(self):
        """GeneratorCritic should work without DB (backward compatibility)."""
        from scripts.agentica.primitives import HandoffState

        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(
            side_effect=[
                HandoffState(context="test", next_instruction="generated"),
                HandoffState(context="test", next_instruction="APPROVED"),
            ]
        )

        with patch("scripts.agentica.patterns.spawn", return_value=mock_agent):
            from scripts.agentica.patterns import GeneratorCritic

            gc = GeneratorCritic(
                generator_premise="You generate",
                critic_premise="You critique",
                db=None,
            )
            result = await gc.run("Create something")

            # Should get final state
            assert result is not None
            assert "APPROVED" in result.next_instruction
