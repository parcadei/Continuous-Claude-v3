"""Test Block dataclass for structured core memory.

Tests for the Block dataclass that provides Letta-style memory blocks
with labels, values, and character limits.
"""

import pytest
from scripts.agentica_patterns.memory_block import Block, BlockManager


class TestBlockCreation:
    """Test Block creation and basic properties."""

    def test_block_creation_basic(self):
        """Block should be created with label, value, limit."""
        block = Block(label="persona", value="I am a helpful assistant")
        assert block.label == "persona"
        assert block.value == "I am a helpful assistant"
        assert block.limit == 5000  # default

    def test_block_creation_with_custom_limit(self):
        """Block should accept custom character limit."""
        block = Block(label="test", value="hello", limit=100)
        assert block.limit == 100

    def test_block_creation_empty_value(self):
        """Block should allow empty value."""
        block = Block(label="empty")
        assert block.value == ""
        assert block.label == "empty"

    def test_block_creation_with_metadata(self):
        """Block should accept metadata dict."""
        block = Block(label="test", value="content", metadata={"key": "val"})
        assert block.metadata == {"key": "val"}

    def test_block_creation_default_metadata(self):
        """Block should have empty dict as default metadata."""
        block = Block(label="test")
        assert block.metadata == {}


class TestBlockCharacterLimit:
    """Test Block character limit enforcement."""

    def test_block_character_limit_raises_on_init(self):
        """Block should raise ValueError if value exceeds limit on init."""
        with pytest.raises(ValueError) as excinfo:
            Block(label="test", value="x" * 6000, limit=5000)
        assert "exceeds limit" in str(excinfo.value)
        assert "6000 > 5000" in str(excinfo.value)

    def test_block_character_limit_exact(self):
        """Block should allow value exactly at limit."""
        value = "x" * 5000
        block = Block(label="test", value=value, limit=5000)
        assert len(block.value) == 5000

    def test_block_remaining_property(self):
        """Block.remaining should return characters until limit."""
        block = Block(label="test", value="hello", limit=100)
        assert block.remaining == 95  # 100 - 5

    def test_block_remaining_empty(self):
        """Block.remaining should equal limit when value is empty."""
        block = Block(label="test", value="", limit=100)
        assert block.remaining == 100


class TestBlockUpdate:
    """Test Block.update() method."""

    def test_block_update_replaces_value(self):
        """Block.update() should replace value."""
        block = Block(label="test", value="old")
        block.update("new")
        assert block.value == "new"

    def test_block_update_enforces_limit(self):
        """Block.update() should raise if new value exceeds limit."""
        block = Block(label="test", value="short", limit=100)
        with pytest.raises(ValueError) as excinfo:
            block.update("x" * 150)
        assert "exceeds limit" in str(excinfo.value)

    def test_block_update_empty_string(self):
        """Block.update() should allow empty string."""
        block = Block(label="test", value="something")
        block.update("")
        assert block.value == ""


class TestBlockAppend:
    """Test Block.append() method."""

    def test_block_append_adds_to_value(self):
        """Block.append() should add to value."""
        block = Block(label="test", value="hello")
        block.append(" world")
        assert block.value == "hello world"

    def test_block_append_respects_limit(self):
        """Block.append() should raise if result exceeds limit."""
        block = Block(label="test", value="x" * 95, limit=100)
        with pytest.raises(ValueError) as excinfo:
            block.append("y" * 10)  # Would be 105 chars
        assert "would exceed limit" in str(excinfo.value)

    def test_block_append_exact_limit(self):
        """Block.append() should allow appending up to exact limit."""
        block = Block(label="test", value="x" * 95, limit=100)
        block.append("y" * 5)  # Exactly 100
        assert len(block.value) == 100

    def test_block_append_empty_string(self):
        """Block.append() should handle empty string."""
        block = Block(label="test", value="hello")
        block.append("")
        assert block.value == "hello"


class TestBlockSerialization:
    """Test Block serialization to/from dict."""

    def test_block_to_dict(self):
        """Block should serialize to dict."""
        block = Block(label="test", value="content", limit=1000, metadata={"k": "v"})
        d = block.to_dict()
        assert d == {
            "label": "test",
            "value": "content",
            "limit": 1000,
            "metadata": {"k": "v"},
        }

    def test_block_from_dict(self):
        """Block should deserialize from dict."""
        d = {"label": "test", "value": "content", "limit": 1000}
        block = Block.from_dict(d)
        assert block.label == "test"
        assert block.value == "content"
        assert block.limit == 1000

    def test_block_from_dict_defaults(self):
        """Block.from_dict() should use defaults for missing fields."""
        d = {"label": "minimal"}
        block = Block.from_dict(d)
        assert block.label == "minimal"
        assert block.value == ""
        assert block.limit == 5000
        assert block.metadata == {}

    def test_block_roundtrip(self):
        """Block should roundtrip through to_dict/from_dict."""
        original = Block(label="test", value="content", limit=2000, metadata={"x": 1})
        restored = Block.from_dict(original.to_dict())
        assert restored.label == original.label
        assert restored.value == original.value
        assert restored.limit == original.limit
        assert restored.metadata == original.metadata


class TestBlockManager:
    """Test BlockManager for managing multiple blocks."""

    def test_manager_add_block(self):
        """BlockManager.add_block() should add blocks."""
        manager = BlockManager()
        manager.add_block(Block(label="persona", value="assistant"))
        assert "persona" in manager.blocks

    def test_manager_get_block(self):
        """BlockManager.get_block() should return block by label."""
        manager = BlockManager()
        block = Block(label="persona", value="assistant")
        manager.add_block(block)

        retrieved = manager.get_block("persona")
        assert retrieved is not None
        assert retrieved.value == "assistant"

    def test_manager_get_block_not_found(self):
        """BlockManager.get_block() should return None if not found."""
        manager = BlockManager()
        assert manager.get_block("nonexistent") is None

    def test_manager_update_block(self):
        """BlockManager.update_block() should update block value."""
        manager = BlockManager()
        manager.add_block(Block(label="persona", value="old"))
        manager.update_block("persona", "new")
        assert manager.get_block("persona").value == "new"

    def test_manager_update_block_not_found(self):
        """BlockManager.update_block() should raise KeyError if not found."""
        manager = BlockManager()
        with pytest.raises(KeyError):
            manager.update_block("nonexistent", "value")

    def test_manager_update_block_enforces_limit(self):
        """BlockManager.update_block() should enforce character limit."""
        manager = BlockManager()
        manager.add_block(Block(label="test", value="short", limit=100))
        with pytest.raises(ValueError):
            manager.update_block("test", "x" * 150)

    def test_manager_to_core_memory_string(self):
        """BlockManager.to_core_memory_string() should format blocks for prompt."""
        manager = BlockManager()
        manager.add_block(Block(label="persona", value="I am helpful"))
        manager.add_block(Block(label="human", value="Alice"))

        result = manager.to_core_memory_string()

        assert "<persona>" in result
        assert "</persona>" in result
        assert "I am helpful" in result
        assert "<human>" in result
        assert "</human>" in result
        assert "Alice" in result

    def test_manager_multiple_blocks(self):
        """BlockManager should handle multiple blocks."""
        manager = BlockManager()
        manager.add_block(Block(label="a", value="A"))
        manager.add_block(Block(label="b", value="B"))
        manager.add_block(Block(label="c", value="C"))

        assert len(manager.blocks) == 3
        assert manager.get_block("a").value == "A"
        assert manager.get_block("b").value == "B"
        assert manager.get_block("c").value == "C"

    def test_manager_replace_block(self):
        """Adding block with same label should replace existing."""
        manager = BlockManager()
        manager.add_block(Block(label="test", value="first"))
        manager.add_block(Block(label="test", value="second"))

        assert manager.get_block("test").value == "second"
        assert len(manager.blocks) == 1


class TestBlockLettaCompatibility:
    """Test compatibility with Letta's Block design patterns."""

    def test_persona_human_blocks(self):
        """Should support Letta's standard persona/human block pattern."""
        manager = BlockManager()
        manager.add_block(Block(label="persona", value="You are a helpful AI assistant."))
        manager.add_block(Block(label="human", value="The human's name is Alice."))

        persona = manager.get_block("persona")
        human = manager.get_block("human")

        assert persona.label == "persona"
        assert human.label == "human"

    def test_default_limit_matches_letta(self):
        """Default limit should match Letta's CORE_MEMORY_BLOCK_CHAR_LIMIT."""
        # Letta uses 5000 as default
        block = Block(label="test", value="content")
        assert block.limit == 5000

    def test_block_with_description_metadata(self):
        """Block should support description via metadata (Letta pattern)."""
        block = Block(
            label="persona",
            value="I am helpful",
            metadata={"description": "The assistant's persona and character traits"}
        )
        assert block.metadata["description"] == "The assistant's persona and character traits"


class TestBlockIntegrationWithRemember:
    """Test Block integration with remember() pattern.

    These tests verify that Block can work alongside the existing
    remember/recall pattern in unified_scope.
    """

    def test_block_value_matches_remember_pattern(self):
        """Block.update() should behave like remember()."""
        # Simulate what unified_scope.remember() would do
        block = Block(label="persona", value="initial")
        block.update("updated value")  # Like remember("persona", "updated value")
        assert block.value == "updated value"

    def test_block_manager_tracks_remember_calls(self):
        """BlockManager should track blocks from remember() calls."""
        manager = BlockManager()

        # Simulate remember("key1", "val1") with Block tracking
        manager.add_block(Block(label="key1", value="val1"))

        # Simulate remember("key2", "val2")
        manager.add_block(Block(label="key2", value="val2"))

        # Simulate remember("key1", "updated") - should update
        manager.update_block("key1", "updated")

        assert manager.get_block("key1").value == "updated"
        assert manager.get_block("key2").value == "val2"

    def test_block_remaining_useful_for_context_budget(self):
        """remaining property helps manage context window budget."""
        # If context budget is tight, check remaining before append
        block = Block(label="context", value="initial", limit=100)
        new_content = " more content"

        if block.remaining >= len(new_content):
            block.append(new_content)

        assert "more content" in block.value
