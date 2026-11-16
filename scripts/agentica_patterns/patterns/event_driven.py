"""
Event-Driven Pattern for Agentica.

Agents react to events published on a bus with loose coupling.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

# Import spawn from agentica if available, otherwise use a stub for testing
try:
    from agentica import spawn
except ImportError:
    # Stub for testing - tests will mock this
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - use mocking in tests")

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


@dataclass
class Event:
    """
    An event to be published on the event bus.

    Attributes:
        type: Event type string (e.g., "user.created", "order.placed")
        payload: Event data as a dictionary
        timestamp: When the event was created (defaults to now)
    """
    type: str
    payload: dict[str, Any]
    timestamp: Any = field(default_factory=datetime.now)


@dataclass
class Subscriber:
    """
    A subscriber that reacts to specific event types.

    Attributes:
        premise: The agent premise for this subscriber
        event_types: List of event types to subscribe to. Use "*" for wildcard (all events)
    """
    premise: str
    event_types: list[str]


class EventDriven:
    """
    Event-Driven pattern: Agents react to events published on a bus.

    Events are published to a bus, and subscriber agents are notified based
    on their subscribed event types. Good for loose coupling between agents.

    Features:
    - Subscribers specify which event types they handle
    - Wildcard "*" subscribes to all events
    - Concurrent dispatch to all matching subscribers
    - CoordinationDB integration for tracking

    Example:
        bus = EventDriven(subscribers=[
            Subscriber(premise="You handle user created events.", event_types=["user.created"]),
            Subscriber(premise="You handle order placed events.", event_types=["order.placed"]),
            Subscriber(premise="You log all events.", event_types=["*"]),  # wildcard
        ])
        await bus.publish(Event(type="user.created", payload={"user_id": "123"}))
    """

    def __init__(
        self,
        subscribers: list[Subscriber],
        model: str | None = None,
        scope: dict[str, Any] | None = None,
        return_type: type = str,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize Event-Driven pattern.

        Args:
            subscribers: List of Subscriber definitions
            model: Model to use for subscriber agents
            scope: Tools available to subscriber agents
            return_type: Expected return type from subscriber handlers
            db: Optional coordination database for tracking agents
        """
        self.subscribers = subscribers
        self.model = model
        self.scope = scope or {}
        self.return_type = return_type
        self.db = db
        # Generate unique bus ID for this instance
        self.bus_id = str(uuid4())

    def _matches_event(self, subscriber: Subscriber, event: Event) -> bool:
        """Check if subscriber should receive this event."""
        for event_type in subscriber.event_types:
            if event_type == "*":
                return True
            if event_type == event.type:
                return True
        return False

    async def _spawn_subscriber_agent(self, subscriber: Subscriber) -> Any:
        """Spawn an agent for a subscriber with pattern environment variables."""
        # Set pattern environment variables for hook detection
        original_env = {}
        env_vars = {
            'PATTERN_TYPE': 'event_driven',
            'PATTERN_ID': self.bus_id,
            'EVENT_BUS_ID': self.bus_id,
            'AGENT_ROLE': 'subscriber',
            'SUBSCRIBER_EVENT_TYPES': json.dumps(subscriber.event_types)
        }

        # Save original values and set new ones
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            spawn_kwargs = {"premise": subscriber.premise}
            if self.model:
                spawn_kwargs["model"] = self.model
            if self.scope:
                spawn_kwargs["scope"] = self.scope

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                return await tracked_spawn(
                    db=self.db, pattern="event_driven", **spawn_kwargs
                )
            else:
                return await spawn(**spawn_kwargs)
        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    async def _dispatch_to_subscriber(
        self, subscriber: Subscriber, event: Event
    ) -> Any:
        """Dispatch event to a single subscriber."""
        agent = await self._spawn_subscriber_agent(subscriber)

        prompt = f"""
        Event received:
        Type: {event.type}
        Payload: {event.payload}
        Timestamp: {event.timestamp}

        Handle this event according to your role.
        """

        return await agent.call(self.return_type, prompt)

    async def publish(self, event: Event) -> list[Any]:
        """
        Publish an event to all matching subscribers.

        Args:
            event: The event to publish

        Returns:
            List of results from all matching subscriber handlers
        """
        # Find all matching subscribers
        matching = [s for s in self.subscribers if self._matches_event(s, event)]

        if not matching:
            return []

        # Dispatch concurrently to all matching subscribers
        results = await asyncio.gather(
            *[self._dispatch_to_subscriber(sub, event) for sub in matching]
        )

        return list(results)
