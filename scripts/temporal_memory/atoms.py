"""Temporal atoms and operators for TEL-based memory."""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# Patterns for parsing compact format
# holds(fact=value, T=turn) - captures fact, value (up to comma before T=), and turn
HOLDS_PATTERN = re.compile(r"holds\(([^=]+)=(.+),\s*T=(\d+)\)")
# G(fact=value) - captures fact and value
ALWAYS_PATTERN = re.compile(r"G\(([^=]+)=(.+)\)")
# F(fact) - captures just the fact name
EVENTUALLY_PATTERN = re.compile(r"F\(([^)]+)\)")
# U(fact) - captures just the fact name
UNTIL_PATTERN = re.compile(r"U\(([^)]+)\)")
# X(fact) - captures just the fact name
NEXT_PATTERN = re.compile(r"X\(([^)]+)\)")


class TemporalOperator(Enum):
    """TEL temporal operators.

    Operators:
        ALWAYS (G): Globally - fact holds at all future times (invariant)
        EVENTUALLY (F): Future - fact will hold at some future time
        UNTIL (U): Until - fact holds until another fact becomes true
        NEXT (X): Next - fact holds at the next turn
        HOLDS: Fact holds at a specific turn T
    """
    ALWAYS = "G"      # Globally (invariant)
    EVENTUALLY = "F"  # Future (eventuality)
    UNTIL = "U"       # Until (transition)
    NEXT = "X"        # Next turn
    HOLDS = "holds"   # Fact holds at turn T


@dataclass(frozen=True)
class TemporalAtom:
    """A fact with temporal qualification.

    Represents a single temporal assertion in TEL format.
    Immutable (frozen) to allow use as dict keys and set members.

    Attributes:
        operator: The temporal operator qualifying this fact
        fact: The fact name/key
        value: The fact's value (can be any type)
        turn: The turn number this applies to
        metadata: Additional metadata (excluded from hash/equality)

    Example:
        >>> atom = TemporalAtom(TemporalOperator.HOLDS, "phase", "testing", 5)
        >>> atom.to_compact()
        'holds(phase=testing, T=5)'
    """
    operator: TemporalOperator
    fact: str
    value: Any
    turn: int
    metadata: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    def to_compact(self) -> str:
        """Convert to compact string representation.

        Returns a human-readable TEL-like notation:
        - holds(fact=value, T=turn) for HOLDS
        - G(fact=value) for ALWAYS
        - F(fact) for EVENTUALLY
        - U(fact) for UNTIL
        - X(fact) for NEXT

        Returns:
            Compact string representation of this temporal atom
        """
        if self.operator == TemporalOperator.HOLDS:
            return f"holds({self.fact}={self.value}, T={self.turn})"
        elif self.operator == TemporalOperator.ALWAYS:
            return f"G({self.fact}={self.value})"
        elif self.operator == TemporalOperator.EVENTUALLY:
            return f"F({self.fact})"
        else:
            # UNTIL and NEXT
            return f"{self.operator.value}({self.fact})"

    @classmethod
    def from_compact(cls, s: str) -> "TemporalAtom":
        """Parse compact string representation back to TemporalAtom.

        Parses the TEL-like notation produced by to_compact():
        - holds(fact=value, T=turn) -> HOLDS operator
        - G(fact=value) -> ALWAYS operator
        - F(fact) -> EVENTUALLY operator
        - U(fact) -> UNTIL operator
        - X(fact) -> NEXT operator

        Args:
            s: Compact string representation to parse

        Returns:
            TemporalAtom parsed from the string

        Raises:
            ValueError: If the string cannot be parsed

        Example:
            >>> atom = TemporalAtom.from_compact("holds(phase=testing, T=3)")
            >>> atom.operator == TemporalOperator.HOLDS
            True
            >>> atom.fact == "phase"
            True
        """
        s = s.strip()

        if match := HOLDS_PATTERN.match(s):
            return cls(
                operator=TemporalOperator.HOLDS,
                fact=match.group(1).strip(),
                value=match.group(2).strip(),
                turn=int(match.group(3)),
            )
        elif match := ALWAYS_PATTERN.match(s):
            return cls(
                operator=TemporalOperator.ALWAYS,
                fact=match.group(1).strip(),
                value=match.group(2).strip(),
                turn=0,
            )
        elif match := EVENTUALLY_PATTERN.match(s):
            return cls(
                operator=TemporalOperator.EVENTUALLY,
                fact=match.group(1).strip(),
                value=None,
                turn=0,
            )
        elif match := UNTIL_PATTERN.match(s):
            return cls(
                operator=TemporalOperator.UNTIL,
                fact=match.group(1).strip(),
                value=None,
                turn=0,
            )
        elif match := NEXT_PATTERN.match(s):
            return cls(
                operator=TemporalOperator.NEXT,
                fact=match.group(1).strip(),
                value=None,
                turn=0,
            )

        raise ValueError(f"Cannot parse: {s}")


@dataclass
class TemporalFact:
    """Tracked fact with temporal metadata.

    Represents a fact that evolves over time, tracking when it was
    first seen, when it last changed, and how stable it is.

    Attributes:
        key: The fact's unique identifier
        current_value: The current value of the fact
        first_seen: Turn when this fact was first observed
        last_changed: Turn when this fact last changed value
        change_count: Number of times the value has changed
        confidence: Confidence score (0.0-1.0), decreases with changes

    Example:
        >>> fact = TemporalFact("db_type", "sqlite", first_seen=1, last_changed=1)
        >>> fact.current_value = "postgres"
        >>> fact.last_changed = 5
        >>> fact.change_count = 1
    """
    key: str
    current_value: Any
    first_seen: int
    last_changed: int
    change_count: int = 0
    confidence: float = 1.0
