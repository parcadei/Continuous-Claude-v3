"""Tests for EventDriven pattern."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.agentica.patterns import Event, Subscriber, EventDriven


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_has_type_and_payload(self):
        """Event stores type and payload."""
        event = Event(type="user.created", payload={"user_id": "123"})
        assert event.type == "user.created"
        assert event.payload == {"user_id": "123"}

    def test_event_has_timestamp(self):
        """Event has a timestamp."""
        before = datetime.now()
        event = Event(type="test", payload={})
        after = datetime.now()
        assert before <= event.timestamp <= after

    def test_event_accepts_custom_timestamp(self):
        """Event can have custom timestamp."""
        custom_time = datetime(2025, 1, 1, 12, 0, 0)
        event = Event(type="test", payload={}, timestamp=custom_time)
        assert event.timestamp == custom_time


class TestSubscriber:
    """Tests for Subscriber dataclass."""

    def test_subscriber_has_premise_and_event_types(self):
        """Subscriber stores premise and event types."""
        sub = Subscriber(
            premise="You handle user events.",
            event_types=["user.created", "user.deleted"]
        )
        assert sub.premise == "You handle user events."
        assert sub.event_types == ["user.created", "user.deleted"]


class TestEventDriven:
    """Tests for EventDriven pattern."""

    @pytest.fixture
    def mock_spawn(self):
        """Mock the spawn function."""
        with patch("scripts.agentica.patterns.event_driven.spawn") as mock:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="processed")
            mock.return_value = mock_agent
            yield mock

    @pytest.mark.asyncio
    async def test_subscriber_receives_matching_event(self, mock_spawn):
        """Subscriber is called when event type matches."""
        bus = EventDriven(subscribers=[
            Subscriber(
                premise="You handle user created events.",
                event_types=["user.created"]
            )
        ])

        event = Event(type="user.created", payload={"user_id": "123"})
        results = await bus.publish(event)

        # Verify subscriber was spawned and called
        assert mock_spawn.called
        mock_agent = mock_spawn.return_value
        assert mock_agent.call.called
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_wildcard_subscriber_receives_all_events(self, mock_spawn):
        """Subscriber with '*' event_type receives all events."""
        bus = EventDriven(subscribers=[
            Subscriber(
                premise="You log all events.",
                event_types=["*"]
            )
        ])

        # Publish different event types
        event1 = Event(type="user.created", payload={})
        event2 = Event(type="order.placed", payload={})
        event3 = Event(type="something.else", payload={})

        results1 = await bus.publish(event1)
        results2 = await bus.publish(event2)
        results3 = await bus.publish(event3)

        # Wildcard should receive all events
        assert len(results1) == 1
        assert len(results2) == 1
        assert len(results3) == 1

    @pytest.mark.asyncio
    async def test_non_matching_subscriber_not_called(self, mock_spawn):
        """Subscriber is not called when event type doesn't match."""
        bus = EventDriven(subscribers=[
            Subscriber(
                premise="You handle order events.",
                event_types=["order.placed"]
            )
        ])

        event = Event(type="user.created", payload={"user_id": "123"})
        results = await bus.publish(event)

        # No subscribers should match
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_concurrent_dispatch_to_multiple_subscribers(self, mock_spawn):
        """Multiple matching subscribers are dispatched concurrently."""
        call_times = []

        async def track_call(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.01)  # Small delay to test concurrency
            return "processed"

        mock_agent = AsyncMock()
        mock_agent.call = track_call
        mock_spawn.return_value = mock_agent

        bus = EventDriven(subscribers=[
            Subscriber(premise="Handler 1", event_types=["user.created"]),
            Subscriber(premise="Handler 2", event_types=["user.created"]),
            Subscriber(premise="Handler 3", event_types=["user.created"]),
        ])

        event = Event(type="user.created", payload={})
        results = await bus.publish(event)

        # All 3 subscribers should be called
        assert len(results) == 3

        # They should have started nearly simultaneously (concurrent dispatch)
        if len(call_times) >= 2:
            # Check that calls started close together (within 0.005s)
            time_diff = max(call_times) - min(call_times)
            assert time_diff < 0.02  # Should be concurrent

    @pytest.mark.asyncio
    async def test_multiple_event_types_per_subscriber(self, mock_spawn):
        """Subscriber with multiple event types matches any of them."""
        bus = EventDriven(subscribers=[
            Subscriber(
                premise="You handle user lifecycle events.",
                event_types=["user.created", "user.deleted", "user.updated"]
            )
        ])

        event1 = Event(type="user.created", payload={})
        event2 = Event(type="user.deleted", payload={})
        event3 = Event(type="order.placed", payload={})

        results1 = await bus.publish(event1)
        results2 = await bus.publish(event2)
        results3 = await bus.publish(event3)

        assert len(results1) == 1  # Matches
        assert len(results2) == 1  # Matches
        assert len(results3) == 0  # Doesn't match

    @pytest.mark.asyncio
    async def test_coordination_db_integration(self):
        """EventDriven uses tracked_spawn when db is provided."""
        mock_db = MagicMock()

        with patch("scripts.agentica.tracked_agent.tracked_spawn") as mock_tracked:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="processed")
            mock_tracked.return_value = mock_agent

            bus = EventDriven(
                subscribers=[
                    Subscriber(premise="Handler", event_types=["test"])
                ],
                db=mock_db
            )

            event = Event(type="test", payload={})
            await bus.publish(event)

            # Verify tracked_spawn was called with db and pattern
            mock_tracked.assert_called()
            call_kwargs = mock_tracked.call_args[1]
            assert call_kwargs["db"] == mock_db
            assert call_kwargs["pattern"] == "event_driven"

    @pytest.mark.asyncio
    async def test_publish_returns_results_from_all_subscribers(self, mock_spawn):
        """Publish returns list of results from all matching subscribers."""
        mock_spawn.return_value.call = AsyncMock(
            side_effect=["result1", "result2"]
        )

        bus = EventDriven(subscribers=[
            Subscriber(premise="Handler 1", event_types=["test"]),
            Subscriber(premise="Handler 2", event_types=["test"]),
        ])

        event = Event(type="test", payload={})
        results = await bus.publish(event)

        assert results == ["result1", "result2"]
