"""
Test Blackboard Pattern Environment Variables

Tests that scripts/agentica/patterns/blackboard.py sets correct environment variables.
"""
import os
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_blackboard_sets_pattern_type():
    """Blackboard pattern sets PATTERN_TYPE=blackboard."""
    from scripts.agentica_patterns.patterns.blackboard import Blackboard, Specialist

    # Mock spawn to capture environment variables
    captured_env = {}

    async def mock_spawn(**kwargs):
        # Capture environment if set
        if 'env' in kwargs:
            captured_env.update(kwargs['env'])

        # Return mock agent
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value={'complete': True})
        return mock_agent

    with patch('scripts.agentica_patterns.patterns.blackboard.spawn', side_effect=mock_spawn):
        bb = Blackboard(
            specialists=[
                Specialist(premise="Test specialist", writes_to=["test"])
            ],
            controller_premise="Test controller"
        )

        # Trigger agent spawn
        await bb.solve("test query")

    # Verify PATTERN_TYPE was set
    assert 'PATTERN_TYPE' in captured_env
    assert captured_env['PATTERN_TYPE'] == 'blackboard'


@pytest.mark.asyncio
async def test_blackboard_sets_specialist_env_vars():
    """Blackboard pattern sets specialist environment variables."""
    from scripts.agentica_patterns.patterns.blackboard import Blackboard, Specialist

    captured_envs = []

    async def mock_spawn(**kwargs):
        # Capture environment if set
        if 'env' in kwargs:
            captured_envs.append(dict(kwargs['env']))

        # Return mock agent
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value={'test': 'value'})
        return mock_agent

    with patch('scripts.agentica_patterns.patterns.blackboard.spawn', side_effect=mock_spawn):
        bb = Blackboard(
            specialists=[
                Specialist(
                    premise="Specialist 1",
                    writes_to=["requirements", "design"],
                    reads_from=["query"]
                )
            ],
            controller_premise="Controller"
        )

        # Trigger specialist spawn
        await bb.solve("test query")

    # Find specialist env (not controller)
    specialist_envs = [e for e in captured_envs if e.get('AGENT_ROLE') == 'specialist']
    assert len(specialist_envs) > 0

    specialist_env = specialist_envs[0]
    assert specialist_env['PATTERN_TYPE'] == 'blackboard'
    assert specialist_env['AGENT_ROLE'] == 'specialist'
    assert 'requirements' in specialist_env['BLACKBOARD_WRITES_TO']
    assert 'design' in specialist_env['BLACKBOARD_WRITES_TO']
    assert 'query' in specialist_env['BLACKBOARD_READS_FROM']


@pytest.mark.asyncio
async def test_blackboard_sets_controller_env_vars():
    """Blackboard pattern sets controller environment variables."""
    from scripts.agentica_patterns.patterns.blackboard import Blackboard, Specialist

    captured_envs = []

    async def mock_spawn(**kwargs):
        # Capture environment if set
        if 'env' in kwargs:
            captured_envs.append(dict(kwargs['env']))

        # Return mock agent
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value={'complete': True})
        return mock_agent

    with patch('scripts.agentica_patterns.patterns.blackboard.spawn', side_effect=mock_spawn):
        bb = Blackboard(
            specialists=[
                Specialist(premise="Test specialist", writes_to=["test"])
            ],
            controller_premise="Test controller"
        )

        # Trigger controller spawn
        await bb.solve("test query")

    # Find controller env
    controller_envs = [e for e in captured_envs if e.get('AGENT_ROLE') == 'controller']
    assert len(controller_envs) > 0

    controller_env = controller_envs[0]
    assert controller_env['PATTERN_TYPE'] == 'blackboard'
    assert controller_env['AGENT_ROLE'] == 'controller'


@pytest.mark.asyncio
async def test_blackboard_sets_blackboard_id():
    """Blackboard pattern sets unique BLACKBOARD_ID."""
    from scripts.agentica_patterns.patterns.blackboard import Blackboard, Specialist

    captured_envs = []

    async def mock_spawn(**kwargs):
        if 'env' in kwargs:
            captured_envs.append(dict(kwargs['env']))

        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value={'complete': True})
        return mock_agent

    with patch('scripts.agentica_patterns.patterns.blackboard.spawn', side_effect=mock_spawn):
        bb = Blackboard(
            specialists=[
                Specialist(premise="Test", writes_to=["test"])
            ],
            controller_premise="Controller"
        )

        await bb.solve("test query")

    # All agents should have same BLACKBOARD_ID
    blackboard_ids = [e.get('BLACKBOARD_ID') for e in captured_envs if 'BLACKBOARD_ID' in e]
    assert len(blackboard_ids) > 0
    assert len(set(blackboard_ids)) == 1  # All same ID

    # ID should be non-empty
    assert blackboard_ids[0]
    assert len(blackboard_ids[0]) > 0
