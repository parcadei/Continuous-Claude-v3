"""Tests for greeting package."""

from dataclasses import fields

import pytest


class TestGreetingModel:
    """Tests for Greeting dataclass."""

    def test_greeting_is_dataclass(self):
        """Greeting should be a dataclass."""
        from workspace.greeting.models import Greeting

        # Dataclasses have __dataclass_fields__
        assert hasattr(Greeting, "__dataclass_fields__")

    def test_greeting_has_name_field(self):
        """Greeting should have a name field of type str."""
        from workspace.greeting.models import Greeting

        field_names = [f.name for f in fields(Greeting)]
        assert "name" in field_names

    def test_greeting_has_message_field(self):
        """Greeting should have a message field of type str."""
        from workspace.greeting.models import Greeting

        field_names = [f.name for f in fields(Greeting)]
        assert "message" in field_names

    def test_greeting_can_be_instantiated(self):
        """Greeting should be instantiable with name and message."""
        from workspace.greeting.models import Greeting

        g = Greeting(name="Alice", message="Hello")
        assert g.name == "Alice"
        assert g.message == "Hello"


class TestGreetFunction:
    """Tests for greet() function."""

    def test_greet_returns_greeting(self):
        """greet() should return a Greeting instance."""
        from workspace.greeting.core import greet
        from workspace.greeting.models import Greeting

        result = greet("Bob")
        assert isinstance(result, Greeting)

    def test_greet_sets_name(self):
        """greet() should set the name field from the argument."""
        from workspace.greeting.core import greet

        result = greet("Charlie")
        assert result.name == "Charlie"

    def test_greet_sets_message(self):
        """greet() should set a greeting message."""
        from workspace.greeting.core import greet

        result = greet("Diana")
        assert "Diana" in result.message
        assert "Hello" in result.message
