"""TDD Tests for Phase 52: Add PATTERN_TYPE to EventDriven pattern.

These tests verify that the EventDriven pattern properly sets environment variables
when spawning agents, enabling pattern-aware hooks to detect and route correctly.

Required environment variables when spawning:
- PATTERN_TYPE=event_driven
- PATTERN_ID=<bus_id>
- EVENT_BUS_ID=<bus_id>
- AGENT_ROLE=publisher|subscriber
- SUBSCRIBER_EVENT_TYPES=<json_array> (for subscribers only)

Module path: scripts/agentica/patterns/event_driven.py

See plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 52)
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scripts.agentica_patterns.patterns.event_driven import EventDriven, Event, Subscriber


class TestEventDrivenPatternTypeEnvVars:
    """Tests that EventDriven sets PATTERN_TYPE and related env vars when spawning."""

    @pytest.mark.asyncio
    async def test_sets_pattern_type_env_var(self):
        """EventDriven should set PATTERN_TYPE=event_driven before spawning."""
        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Handle user events", event_types=["user.created"]),
            ]
        )

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="handled")
            mock_spawn.return_value = mock_agent

            event = Event(type="user.created", payload={"user_id": "123"})
            await bus.publish(event)

            # Spawn should have been called
            assert mock_spawn.call_count == 1

    @pytest.mark.asyncio
    async def test_sets_event_bus_id_env_var(self):
        """EventDriven should set EVENT_BUS_ID when spawning subscribers."""
        captured_env = {}

        async def capture_env_spawn(**kwargs):
            captured_env['EVENT_BUS_ID'] = os.environ.get('EVENT_BUS_ID')
            captured_env['PATTERN_TYPE'] = os.environ.get('PATTERN_TYPE')
            captured_env['PATTERN_ID'] = os.environ.get('PATTERN_ID')
            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            return mock

        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Handle events", event_types=["test.event"]),
            ]
        )

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn', side_effect=capture_env_spawn):
            event = Event(type="test.event", payload={})
            await bus.publish(event)

        # Verify env vars were set
        assert captured_env.get('PATTERN_TYPE') == 'event_driven', (
            f"PATTERN_TYPE should be 'event_driven', got: {captured_env.get('PATTERN_TYPE')}"
        )
        assert captured_env.get('EVENT_BUS_ID') is not None, (
            "EVENT_BUS_ID should be set"
        )
        assert captured_env.get('PATTERN_ID') is not None, (
            "PATTERN_ID should be set"
        )

    @pytest.mark.asyncio
    async def test_pattern_id_equals_bus_id(self):
        """PATTERN_ID should equal EVENT_BUS_ID for consistency."""
        captured_env = {}

        async def capture_env_spawn(**kwargs):
            captured_env['EVENT_BUS_ID'] = os.environ.get('EVENT_BUS_ID')
            captured_env['PATTERN_ID'] = os.environ.get('PATTERN_ID')
            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            return mock

        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Test subscriber", event_types=["*"]),
            ]
        )

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn', side_effect=capture_env_spawn):
            event = Event(type="test.event", payload={})
            await bus.publish(event)

        assert captured_env.get('PATTERN_ID') == captured_env.get('EVENT_BUS_ID'), (
            f"PATTERN_ID ({captured_env.get('PATTERN_ID')}) should equal "
            f"EVENT_BUS_ID ({captured_env.get('EVENT_BUS_ID')})"
        )


class TestEventDrivenAgentRoleEnvVar:
    """Tests for AGENT_ROLE environment variable."""

    @pytest.mark.asyncio
    async def test_subscriber_has_subscriber_role(self):
        """Subscriber agents should have AGENT_ROLE=subscriber."""
        captured_env = {}

        async def capture_env_spawn(**kwargs):
            captured_env['AGENT_ROLE'] = os.environ.get('AGENT_ROLE')
            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            return mock

        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Handle events", event_types=["test.event"]),
            ]
        )

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn', side_effect=capture_env_spawn):
            event = Event(type="test.event", payload={})
            await bus.publish(event)

        assert captured_env.get('AGENT_ROLE') == 'subscriber', (
            f"AGENT_ROLE should be 'subscriber', got: {captured_env.get('AGENT_ROLE')}"
        )

    @pytest.mark.asyncio
    async def test_subscriber_event_types_set(self):
        """SUBSCRIBER_EVENT_TYPES should be set for subscriber agents."""
        captured_env = {}

        async def capture_env_spawn(**kwargs):
            captured_env['SUBSCRIBER_EVENT_TYPES'] = os.environ.get('SUBSCRIBER_EVENT_TYPES')
            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            return mock

        bus = EventDriven(
            subscribers=[
                Subscriber(
                    premise="Handle specific events",
                    event_types=["user.created", "user.updated"]
                ),
            ]
        )

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn', side_effect=capture_env_spawn):
            event = Event(type="user.created", payload={})
            await bus.publish(event)

        event_types_json = captured_env.get('SUBSCRIBER_EVENT_TYPES')
        assert event_types_json is not None, "SUBSCRIBER_EVENT_TYPES should be set"

        # Should be valid JSON array
        import json
        event_types = json.loads(event_types_json)
        assert isinstance(event_types, list)
        assert "user.created" in event_types
        assert "user.updated" in event_types


class TestEventDrivenEnvVarPropagation:
    """Tests that pattern env vars are properly propagated."""

    @pytest.mark.asyncio
    async def test_env_vars_available_during_spawn(self):
        """Environment variables should be set before spawn is called."""
        captured_env = {}

        async def capture_env_spawn(**kwargs):
            # Capture env vars at spawn time
            captured_env['PATTERN_TYPE'] = os.environ.get('PATTERN_TYPE')
            captured_env['EVENT_BUS_ID'] = os.environ.get('EVENT_BUS_ID')
            captured_env['AGENT_ROLE'] = os.environ.get('AGENT_ROLE')
            captured_env['PATTERN_ID'] = os.environ.get('PATTERN_ID')
            captured_env['SUBSCRIBER_EVENT_TYPES'] = os.environ.get('SUBSCRIBER_EVENT_TYPES')

            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            return mock

        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Test", event_types=["test.event"]),
            ]
        )

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn', side_effect=capture_env_spawn):
            event = Event(type="test.event", payload={})
            await bus.publish(event)

        # Verify all required env vars were set
        assert captured_env.get('PATTERN_TYPE') == 'event_driven'
        assert captured_env.get('EVENT_BUS_ID') is not None
        assert captured_env.get('PATTERN_ID') is not None
        assert captured_env.get('AGENT_ROLE') == 'subscriber'
        assert captured_env.get('SUBSCRIBER_EVENT_TYPES') is not None

    @pytest.mark.asyncio
    async def test_multiple_subscribers_get_correct_env(self):
        """Each subscriber should get the correct event types in env."""
        captured_envs = []

        async def capture_env_spawn(**kwargs):
            captured_envs.append({
                'SUBSCRIBER_EVENT_TYPES': os.environ.get('SUBSCRIBER_EVENT_TYPES'),
                'premise': kwargs.get('premise')
            })
            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            return mock

        bus = EventDriven(
            subscribers=[
                Subscriber(premise="User handler", event_types=["user.created"]),
                Subscriber(premise="Order handler", event_types=["order.placed"]),
                Subscriber(premise="Wildcard handler", event_types=["*"]),
            ]
        )

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn', side_effect=capture_env_spawn):
            event = Event(type="user.created", payload={})
            await bus.publish(event)

        # Only matching subscribers should be spawned (user.created matches User and Wildcard)
        assert len(captured_envs) == 2  # User handler + Wildcard handler

    @pytest.mark.asyncio
    async def test_env_vars_cleaned_up_after_publish(self):
        """Environment variables should be cleaned up after execution."""
        original_pattern = os.environ.get('PATTERN_TYPE')
        original_bus = os.environ.get('EVENT_BUS_ID')

        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Test", event_types=["test.event"]),
            ]
        )

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="handled")
            mock_spawn.return_value = mock_agent

            event = Event(type="test.event", payload={})
            await bus.publish(event)

        # After publish, env should be restored to original state
        assert os.environ.get('PATTERN_TYPE') == original_pattern
        assert os.environ.get('EVENT_BUS_ID') == original_bus


class TestEventDrivenBusIdUniqueness:
    """Tests that each event bus execution gets a unique ID."""

    @pytest.mark.asyncio
    async def test_different_publishes_use_same_bus_id(self):
        """Same bus instance should use consistent bus ID across publishes."""
        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Test", event_types=["*"]),
            ]
        )

        captured_ids = []

        async def capture_id_spawn(**kwargs):
            captured_ids.append(os.environ.get('EVENT_BUS_ID'))
            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            return mock

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn', side_effect=capture_id_spawn):
            await bus.publish(Event(type="event1", payload={}))
            await bus.publish(Event(type="event2", payload={}))

        # Same bus instance should use same bus_id
        assert len(captured_ids) == 2
        assert captured_ids[0] == captured_ids[1], (
            "Same bus instance should have consistent bus_id"
        )

    @pytest.mark.asyncio
    async def test_different_buses_get_different_ids(self):
        """Different bus instances should have different IDs."""
        bus1 = EventDriven(
            subscribers=[Subscriber(premise="Test", event_types=["*"])],
        )
        bus2 = EventDriven(
            subscribers=[Subscriber(premise="Test", event_types=["*"])],
        )

        captured_ids = []

        async def capture_id_spawn(**kwargs):
            captured_ids.append(os.environ.get('EVENT_BUS_ID'))
            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            return mock

        with patch('scripts.agentica_patterns.patterns.event_driven.spawn', side_effect=capture_id_spawn):
            await bus1.publish(Event(type="test", payload={}))
            await bus2.publish(Event(type="test", payload={}))

        # Different bus instances should have different IDs
        assert len(captured_ids) == 2
        assert captured_ids[0] != captured_ids[1], (
            "Different bus instances should have different bus_ids"
        )


class TestEventDrivenTrackedAgentEnvVars:
    """Tests that tracked_spawn also receives pattern env vars."""

    @pytest.mark.asyncio
    async def test_tracked_spawn_sees_pattern_env(self):
        """When using tracked_spawn with db, pattern env vars should be set."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        mock_db = MagicMock(spec=CoordinationDB)
        mock_db.register_agent = MagicMock()

        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Test", event_types=["test.event"]),
            ],
            db=mock_db,
        )

        captured_env = {}

        async def capture_env_tracked(**kwargs):
            captured_env['PATTERN_TYPE'] = os.environ.get('PATTERN_TYPE')
            captured_env['EVENT_BUS_ID'] = os.environ.get('EVENT_BUS_ID')
            captured_env['AGENT_ROLE'] = os.environ.get('AGENT_ROLE')
            mock = AsyncMock()
            mock.call = AsyncMock(return_value="handled")
            # Return a TrackedAgent-like mock
            mock._agent_id = "test-subscriber-id"
            mock._db = mock_db
            return mock

        with patch('scripts.agentica_patterns.tracked_agent.tracked_spawn', side_effect=capture_env_tracked):
            event = Event(type="test.event", payload={})
            await bus.publish(event)

        # tracked_spawn should also see the pattern env vars
        assert captured_env.get('PATTERN_TYPE') == 'event_driven'
        assert captured_env.get('AGENT_ROLE') == 'subscriber'


class TestEventDrivenImportability:
    """Test that EventDriven can be imported and basic functionality works."""

    def test_event_driven_importable(self):
        """EventDriven class should be importable from patterns module."""
        from scripts.agentica_patterns.patterns.event_driven import EventDriven
        assert EventDriven is not None

    def test_event_driven_initialization(self):
        """EventDriven should initialize without errors."""
        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Test", event_types=["test.event"]),
            ]
        )
        assert bus is not None
        assert len(bus.subscribers) == 1

    def test_subscriber_initialization(self):
        """Subscriber should initialize correctly."""
        sub = Subscriber(
            premise="Handle user events",
            event_types=["user.created", "user.updated"]
        )
        assert sub.premise == "Handle user events"
        assert sub.event_types == ["user.created", "user.updated"]

    def test_event_initialization(self):
        """Event should initialize correctly."""
        event = Event(
            type="user.created",
            payload={"user_id": "123", "email": "test@example.com"}
        )
        assert event.type == "user.created"
        assert event.payload["user_id"] == "123"
        assert event.timestamp is not None
