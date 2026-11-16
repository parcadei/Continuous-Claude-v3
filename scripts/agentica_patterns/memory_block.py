"""Block dataclass for structured core memory (Letta-compatible).

Provides memory blocks with labels, values, and character limits, similar
to Letta's Block schema for in-context memory management.

Usage:
    # Create a block with default limit (5000 chars)
    persona = Block(label="persona", value="I am a helpful assistant")

    # Update the block value
    persona.update("I am an expert Python developer")

    # Append to the block
    persona.append("\nI specialize in async programming.")

    # Check remaining capacity
    print(f"Remaining: {persona.remaining} chars")

    # Serialize for storage
    data = persona.to_dict()
    restored = Block.from_dict(data)

    # Use BlockManager for multiple blocks
    manager = BlockManager()
    manager.add_block(Block(label="persona", value="..."))
    manager.add_block(Block(label="human", value="..."))
    prompt_section = manager.to_core_memory_string()
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Block:
    """A labeled memory block with character limit.

    Blocks provide structured core memory storage with:
    - label: Unique identifier (e.g., "persona", "human", "system")
    - value: The content (string, enforced character limit)
    - limit: Maximum characters (default 5000, matching Letta's default)
    - metadata: Optional dict for additional block attributes

    The character limit is enforced on:
    - Initialization (__post_init__)
    - Updates (update method)
    - Appends (append method)

    Example:
        persona = Block(label="persona", value="You are a helpful assistant")
        persona.update("You are an expert Python developer")
        persona.append("\nYou specialize in async code.")

    Letta Compatibility:
        This implementation mirrors Letta's Block schema to enable
        cross-compatibility when migrating between frameworks.
    """

    label: str
    value: str = ""
    limit: int = 5000  # Letta's CORE_MEMORY_BLOCK_CHAR_LIMIT default
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Enforce character limit on initialization."""
        if len(self.value) > self.limit:
            raise ValueError(
                f"Block '{self.label}' value exceeds limit: "
                f"{len(self.value)} > {self.limit}"
            )

    def update(self, new_value: str) -> None:
        """Update block value, enforcing limit.

        Args:
            new_value: New content for the block

        Raises:
            ValueError: If new_value exceeds limit
        """
        if len(new_value) > self.limit:
            raise ValueError(
                f"Block '{self.label}' update exceeds limit: "
                f"{len(new_value)} > {self.limit}"
            )
        self.value = new_value

    def append(self, text: str) -> None:
        """Append text to block value.

        Args:
            text: Text to append

        Raises:
            ValueError: If result exceeds limit
        """
        new_value = self.value + text
        if len(new_value) > self.limit:
            raise ValueError(
                f"Block '{self.label}' append would exceed limit: "
                f"{len(new_value)} > {self.limit}"
            )
        self.value = new_value

    @property
    def remaining(self) -> int:
        """Characters remaining before limit."""
        return self.limit - len(self.value)

    def __len__(self) -> int:
        """Return current value length."""
        return len(self.value)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dict with label, value, limit, and metadata
        """
        return {
            "label": self.label,
            "value": self.value,
            "limit": self.limit,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Block":
        """Create Block from dictionary.

        Args:
            data: Dict with at least "label" key

        Returns:
            Block instance with values from dict or defaults
        """
        return cls(
            label=data["label"],
            value=data.get("value", ""),
            limit=data.get("limit", 5000),
            metadata=data.get("metadata", {}),
        )


@dataclass
class BlockManager:
    """Manages multiple memory blocks.

    Provides a container for organizing labeled blocks with methods
    for adding, retrieving, and updating blocks. Also supports
    rendering blocks as a formatted string for prompt injection.

    Example:
        manager = BlockManager()
        manager.add_block(Block(label="persona", value="I am helpful"))
        manager.add_block(Block(label="human", value="User is Alice"))

        # Update a block
        manager.update_block("persona", "I am an expert developer")

        # Render for prompt
        core_memory_text = manager.to_core_memory_string()
    """

    blocks: dict[str, Block] = field(default_factory=dict)

    def add_block(self, block: Block) -> None:
        """Add a block to the manager.

        If a block with the same label exists, it will be replaced.

        Args:
            block: Block instance to add
        """
        self.blocks[block.label] = block

    def get_block(self, label: str) -> Block | None:
        """Get block by label.

        Args:
            label: Block label to retrieve

        Returns:
            Block instance or None if not found
        """
        return self.blocks.get(label)

    def update_block(self, label: str, value: str) -> None:
        """Update block value by label.

        Args:
            label: Block label to update
            value: New value for the block

        Raises:
            KeyError: If label not found
            ValueError: If value exceeds block's limit
        """
        if label not in self.blocks:
            raise KeyError(f"Block not found: {label}")
        self.blocks[label].update(value)

    def list_labels(self) -> list[str]:
        """Return list of all block labels.

        Returns:
            List of label strings
        """
        return list(self.blocks.keys())

    def to_core_memory_string(self) -> str:
        """Format all blocks as core memory string for prompt injection.

        Returns a string with XML-style tags suitable for including
        in system prompts, following Letta's memory block format.

        Returns:
            Formatted string with all blocks
        """
        lines = []
        for label, block in self.blocks.items():
            lines.append(f"<{label}>")
            lines.append(block.value)
            lines.append(f"</{label}>")
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Serialize all blocks to dict.

        Returns:
            Dict mapping label to block.to_dict()
        """
        return {label: block.to_dict() for label, block in self.blocks.items()}

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, Any]]) -> "BlockManager":
        """Create BlockManager from serialized dict.

        Args:
            data: Dict mapping label to block dict

        Returns:
            BlockManager with restored blocks
        """
        manager = cls()
        for label, block_data in data.items():
            # Ensure label is consistent
            block_data["label"] = label
            manager.add_block(Block.from_dict(block_data))
        return manager
