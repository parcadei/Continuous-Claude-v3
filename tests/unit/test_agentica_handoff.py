"""
TDD Tests for HandoffState Primitive

Tests written BEFORE implementation to drive design.
Expected to FAIL until primitives.py implements HandoffState.
"""

import pytest
from scripts.agentica_patterns.primitives import HandoffState


class TestHandoffState:
    """Test structured state transfer between agents."""

    def test_create_basic(self):
        """Create HandoffState with context and instruction."""
        state = HandoffState(
            context="User wants to analyze sales data",
            next_instruction="Fetch Q4 sales from database"
        )

        assert state.context == "User wants to analyze sales data"
        assert state.next_instruction == "Fetch Q4 sales from database"
        assert state.artifacts == {}
        assert state.metadata == {}

    def test_to_dict(self):
        """Serialize HandoffState to dict."""
        state = HandoffState(
            context="Research task",
            next_instruction="Search for papers"
        )

        result = state.to_dict()

        assert isinstance(result, dict)
        assert result["context"] == "Research task"
        assert result["next_instruction"] == "Search for papers"
        assert "artifacts" in result
        assert "metadata" in result

    def test_from_dict(self):
        """Deserialize HandoffState from dict."""
        data = {
            "context": "Analysis task",
            "next_instruction": "Generate report",
            "artifacts": {"data": [1, 2, 3]},
            "metadata": {"priority": "high"}
        }

        state = HandoffState.from_dict(data)

        assert state.context == "Analysis task"
        assert state.next_instruction == "Generate report"
        assert state.artifacts["data"] == [1, 2, 3]
        assert state.metadata["priority"] == "high"

    def test_roundtrip(self):
        """to_dict then from_dict preserves all data."""
        original = HandoffState(
            context="Complex context with details",
            next_instruction="Do something specific",
            artifacts={"file": "data.csv", "count": 42},
            metadata={"source": "agent_a", "timestamp": "2025-12-26"}
        )

        # Roundtrip
        data = original.to_dict()
        restored = HandoffState.from_dict(data)

        assert restored.context == original.context
        assert restored.next_instruction == original.next_instruction
        assert restored.artifacts == original.artifacts
        assert restored.metadata == original.metadata

    def test_add_artifact(self):
        """Add artifact to state after creation."""
        state = HandoffState(
            context="Processing",
            next_instruction="Continue"
        )

        state.add_artifact("result", {"status": "success", "value": 100})

        assert "result" in state.artifacts
        assert state.artifacts["result"]["status"] == "success"
        assert state.artifacts["result"]["value"] == 100

    def test_merge_states(self):
        """Merge two states, later state overwrites conflicts."""
        state1 = HandoffState(
            context="Context A",
            next_instruction="Instruction A",
            artifacts={"shared": "value1", "unique1": "data1"},
            metadata={"key1": "val1"}
        )

        state2 = HandoffState(
            context="Context B",
            next_instruction="Instruction B",
            artifacts={"shared": "value2", "unique2": "data2"},
            metadata={"key2": "val2"}
        )

        merged = state1.merge(state2)

        # Later state (state2) wins on conflicts
        assert merged.context == "Context B"
        assert merged.next_instruction == "Instruction B"

        # Artifacts merged, state2 overwrites shared key
        assert merged.artifacts["shared"] == "value2"
        assert merged.artifacts["unique1"] == "data1"
        assert merged.artifacts["unique2"] == "data2"

        # Metadata merged
        assert merged.metadata["key1"] == "val1"
        assert merged.metadata["key2"] == "val2"

    def test_handoff_chain(self):
        """Track handoff chain: A → B → C."""
        state = HandoffState(
            context="Initial task",
            next_instruction="Start processing"
        )

        # A hands off to B
        state.record_handoff(from_agent="agent_a", to_agent="agent_b")

        # B hands off to C
        state.record_handoff(from_agent="agent_b", to_agent="agent_c")

        chain = state.get_handoff_chain()

        assert len(chain) == 2
        assert chain[0] == {"from": "agent_a", "to": "agent_b"}
        assert chain[1] == {"from": "agent_b", "to": "agent_c"}

    def test_with_metadata(self):
        """Arbitrary metadata preserved through lifecycle."""
        metadata = {
            "priority": "high",
            "deadline": "2025-12-31",
            "tags": ["urgent", "customer-facing"],
            "retry_count": 0
        }

        state = HandoffState(
            context="Task with metadata",
            next_instruction="Execute",
            metadata=metadata
        )

        assert state.metadata["priority"] == "high"
        assert state.metadata["deadline"] == "2025-12-31"
        assert "urgent" in state.metadata["tags"]
        assert state.metadata["retry_count"] == 0

        # Metadata survives roundtrip
        restored = HandoffState.from_dict(state.to_dict())
        assert restored.metadata == metadata

    def test_empty_context_allowed(self):
        """Can create HandoffState with empty context."""
        state = HandoffState(
            context="",
            next_instruction="Start fresh"
        )

        assert state.context == ""
        assert state.next_instruction == "Start fresh"

    def test_none_instruction_fails(self):
        """Cannot create HandoffState without next_instruction."""
        with pytest.raises((ValueError, TypeError)):
            HandoffState(
                context="Has context",
                next_instruction=None
            )

    def test_update_instruction(self):
        """Can update next_instruction after creation."""
        state = HandoffState(
            context="Processing",
            next_instruction="Step 1"
        )

        state.update_instruction("Step 2 - continue processing")

        assert state.next_instruction == "Step 2 - continue processing"

    def test_clear_artifacts(self):
        """Can clear all artifacts while preserving state."""
        state = HandoffState(
            context="Task",
            next_instruction="Continue",
            artifacts={"temp1": "data", "temp2": "more"}
        )

        state.clear_artifacts()

        assert state.artifacts == {}
        assert state.context == "Task"
        assert state.next_instruction == "Continue"
