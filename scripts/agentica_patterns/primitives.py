"""
Agentica Primitives - Consensus, Aggregation, and Handoff State.

These primitives enable multi-agent coordination patterns:
- Consensus: Voting mechanisms (majority, unanimous, threshold)
- Aggregator: Combining results from multiple agents
- HandoffState: Structured state transfer between agents
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ============================================================================
# Consensus Primitives
# ============================================================================


class ConsensusMode(Enum):
    """Voting modes for agent consensus."""
    MAJORITY = "majority"
    UNANIMOUS = "unanimous"
    THRESHOLD = "threshold"


class ConsensusNotReachedError(Exception):
    """Raised when consensus cannot be reached under the specified mode."""
    pass


# Alias for backwards compatibility
ConsensusNotReached = ConsensusNotReachedError


class Consensus:
    """
    Consensus voting mechanism for multi-agent decisions.

    Supports:
    - MAJORITY: Most common vote wins (ties go to first occurrence)
    - UNANIMOUS: All votes must agree
    - THRESHOLD: Percentage of votes must agree (configurable)

    Can handle weighted votes and custom key extraction for structured votes.
    """

    def __init__(self, mode: ConsensusMode, threshold: float | None = None):
        """
        Initialize consensus mechanism.

        Args:
            mode: Voting mode (MAJORITY, UNANIMOUS, THRESHOLD)
            threshold: Required agreement percentage (0.0-1.0) for THRESHOLD mode

        Raises:
            ValueError: If THRESHOLD mode without threshold or invalid threshold range
        """
        self.mode = mode
        self.threshold = threshold

        # Validation
        if mode == ConsensusMode.THRESHOLD:
            if threshold is None:
                raise ValueError("threshold parameter required for THRESHOLD mode")
            if not (0 <= threshold <= 1):
                raise ValueError("threshold must be between 0 and 1")

    def _validate_inputs(
        self,
        votes: list[Any],
        weights: list[float] | None
    ) -> list[float]:
        """Validate inputs and return normalized weights."""
        if votes is None:
            raise ValueError("votes cannot be None")
        if len(votes) == 0:
            raise ValueError("votes cannot be empty")

        if weights is None:
            return [1.0] * len(votes)

        if len(weights) != len(votes):
            raise ValueError("weights must be same length as votes")
        if any(w < 0 for w in weights):
            raise ValueError("weights cannot be negative")
        return weights

    def _count_votes(
        self,
        vote_keys: list[Any],
        weights: list[float]
    ) -> tuple[dict[Any, float], dict[Any, int]]:
        """Count weighted votes and track first occurrences."""
        try:
            vote_counts: dict[Any, float] = {}
            vote_first_idx: dict[Any, int] = {}

            for idx, (vote_key, weight) in enumerate(zip(vote_keys, weights, strict=True)):
                if vote_key not in vote_counts:
                    vote_counts[vote_key] = 0
                    vote_first_idx[vote_key] = idx
                vote_counts[vote_key] += weight
            return vote_counts, vote_first_idx
        except TypeError as e:
            raise TypeError(f"Unhashable vote type without key function: {e}") from e

    def decide(
        self,
        votes: list[Any],
        weights: list[float] | None = None,
        key: Callable[[Any], Any] | None = None
    ) -> Any:
        """
        Decide consensus from votes.

        Args:
            votes: List of votes from agents
            weights: Optional weights for each vote (must match votes length)
            key: Optional function to extract comparable value from vote

        Returns:
            The winning vote (original vote object, not extracted key)

        Raises:
            ValueError: Invalid inputs (empty votes, mismatched weights, negative weights)
            TypeError: Unhashable vote types without key function
            ConsensusNotReached: Consensus cannot be achieved under mode
        """
        weights = self._validate_inputs(votes, weights)
        vote_keys = [key(v) for v in votes] if key else votes
        vote_counts, vote_first_idx = self._count_votes(vote_keys, weights)
        total_weight = sum(weights)

        mode_handlers = {
            ConsensusMode.MAJORITY: lambda: self._decide_majority(
                votes, vote_keys, vote_counts, vote_first_idx
            ),
            ConsensusMode.UNANIMOUS: lambda: self._decide_unanimous(votes, vote_counts),
            ConsensusMode.THRESHOLD: lambda: self._decide_threshold(
                votes, vote_keys, vote_counts, vote_first_idx, total_weight
            ),
        }

        handler = mode_handlers.get(self.mode)
        if handler is None:
            raise ValueError(f"Unknown consensus mode: {self.mode}")
        return handler()

    def _decide_majority(
        self,
        votes: list[Any],
        vote_keys: list[Any],
        vote_counts: dict[Any, float],
        vote_first_idx: dict[Any, int]
    ) -> Any:
        """Majority: highest count wins, ties go to first occurrence."""
        # Find max count
        max_count = max(vote_counts.values())

        # Find all votes with max count
        winners = [k for k, count in vote_counts.items() if count == max_count]

        # If tie, pick first occurrence
        if len(winners) > 1:
            winner_key = min(winners, key=lambda k: vote_first_idx[k])
        else:
            winner_key = winners[0]

        # Return original vote object
        winner_idx = vote_keys.index(winner_key)
        return votes[winner_idx]

    def _decide_unanimous(
        self,
        votes: list[Any],
        vote_counts: dict[Any, float]
    ) -> Any:
        """Unanimous: all votes must be the same."""
        if len(vote_counts) > 1:
            # Not unanimous - show what the votes were
            vote_summary = ", ".join(str(k) for k in vote_counts.keys())
            raise ConsensusNotReached(
                f"Unanimous consensus not reached. Votes: {vote_summary}"
            )

        # All same, return first vote
        return votes[0]

    def _decide_threshold(
        self,
        votes: list[Any],
        vote_keys: list[Any],
        vote_counts: dict[Any, float],
        vote_first_idx: dict[Any, int],
        total_weight: float
    ) -> Any:
        """Threshold: winner must have >= threshold percentage."""
        # Find vote with highest count
        max_count = max(vote_counts.values())
        percentage = max_count / total_weight if total_weight > 0 else 0

        if percentage < self.threshold:
            raise ConsensusNotReached(
                f"Threshold not met: {percentage:.1%} < {self.threshold:.1%}"
            )

        # Find all votes with max count
        winners = [k for k, count in vote_counts.items() if count == max_count]

        # If tie, pick first occurrence
        if len(winners) > 1:
            winner_key = min(winners, key=lambda k: vote_first_idx[k])
        else:
            winner_key = winners[0]

        # Return original vote object
        winner_idx = vote_keys.index(winner_key)
        return votes[winner_idx]


# ============================================================================
# Aggregation Primitives
# ============================================================================


class AggregateMode(Enum):
    """Modes for aggregating results from multiple agents."""
    MERGE = "merge"      # Combine dicts/lists
    CONCAT = "concat"    # Join strings
    BEST = "best"        # Pick highest score


class Aggregator:
    """
    Aggregate results from multiple agents.

    Modes:
    - MERGE: Combine dicts (last wins on conflicts) or concatenate lists
    - CONCAT: Join strings with separator
    - BEST: Select result with highest score field

    Supports deduplication for MERGE and CONCAT modes.
    """

    def __init__(
        self,
        mode: AggregateMode,
        separator: str = " ",
        deduplicate: bool = False
    ):
        """
        Initialize aggregator.

        Args:
            mode: Aggregation mode
            separator: String separator for CONCAT mode
            deduplicate: Remove duplicates in MERGE/CONCAT modes
        """
        self.mode = mode
        self.separator = separator
        self.deduplicate = deduplicate

    def aggregate(self, results: list[Any]) -> Any:
        """
        Aggregate multiple results into one.

        Args:
            results: List of results from agents

        Returns:
            Aggregated result (type depends on mode)

        Raises:
            ValueError: Empty results or missing required fields
            TypeError: Incompatible types for merging
        """
        # Validation
        if not results:
            raise ValueError("results cannot be empty")

        # Filter out None values
        results = [r for r in results if r is not None]

        if not results:
            raise ValueError("results cannot be empty after filtering None values")

        # Single result - return as-is
        if len(results) == 1:
            return results[0]

        # Apply aggregation mode
        if self.mode == AggregateMode.MERGE:
            return self._aggregate_merge(results)
        elif self.mode == AggregateMode.CONCAT:
            return self._aggregate_concat(results)
        elif self.mode == AggregateMode.BEST:
            return self._aggregate_best(results)

        raise ValueError(f"Unknown aggregate mode: {self.mode}")

    def _aggregate_merge(self, results: list[Any]) -> Any:
        """Merge dicts or concatenate lists."""
        # Check if all are dicts
        if all(isinstance(r, dict) for r in results):
            merged = {}
            for r in results:
                merged.update(r)
            return merged

        # Check if all are lists
        if all(isinstance(r, list) for r in results):
            merged_list = []
            for r in results:
                merged_list.extend(r)

            if self.deduplicate:
                # Remove duplicates while preserving order
                seen = set()
                deduped = []
                for item in merged_list:
                    if item not in seen:
                        seen.add(item)
                        deduped.append(item)
                return deduped

            return merged_list

        # Mixed or unsupported types
        raise TypeError(
            f"Cannot merge incompatible types: {[type(r).__name__ for r in results]}"
        )

    def _aggregate_concat(self, results: list[Any]) -> str:
        """Concatenate results as strings."""
        # Convert all to strings
        str_results = [str(r) for r in results]

        if self.deduplicate:
            # Split on separator, deduplicate words
            all_words = []
            for s in str_results:
                all_words.extend(s.split())

            seen = set()
            deduped_words = []
            for word in all_words:
                if word not in seen:
                    seen.add(word)
                    deduped_words.append(word)

            return " ".join(deduped_words)

        return self.separator.join(str_results)

    def _aggregate_best(self, results: list[Any]) -> Any:
        """Select result with highest score."""
        # All results must be dicts with 'score' field
        if not all(isinstance(r, dict) for r in results):
            raise ValueError("BEST mode requires all results to be dicts")

        if not all("score" in r for r in results):
            raise ValueError("BEST mode requires all results to have 'score' field")

        # Find highest score (ties go to first)
        best_result = max(results, key=lambda r: r["score"])

        # Return the 'result' field if it exists, otherwise the whole dict
        return best_result.get("result", best_result)


# ============================================================================
# Handoff State Primitives
# ============================================================================


@dataclass
class HandoffState:
    """
    Structured state for agent-to-agent handoffs.

    Tracks:
    - context: Current situation/task context
    - next_instruction: What the next agent should do
    - artifacts: Data/files produced so far
    - metadata: Arbitrary metadata (priority, tags, etc.)
    - handoff_chain: History of agent handoffs
    """

    context: str
    next_instruction: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    _handoff_chain: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self):
        """Validate required fields."""
        if self.next_instruction is None:
            raise ValueError("next_instruction cannot be None")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "context": self.context,
            "next_instruction": self.next_instruction,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "handoff_chain": self._handoff_chain
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffState":
        """Deserialize from dictionary."""
        state = cls(
            context=data["context"],
            next_instruction=data["next_instruction"],
            artifacts=data.get("artifacts", {}),
            metadata=data.get("metadata", {})
        )
        state._handoff_chain = data.get("handoff_chain", [])
        return state

    def add_artifact(self, key: str, value: Any) -> None:
        """Add an artifact to the state."""
        self.artifacts[key] = value

    def merge(self, other: "HandoffState") -> "HandoffState":
        """
        Merge another state into this one.

        Later state (other) wins on conflicts for context and next_instruction.
        Artifacts and metadata are merged (later wins on key conflicts).
        Handoff chains are concatenated.

        Args:
            other: Another HandoffState to merge

        Returns:
            New merged HandoffState
        """
        merged_artifacts = {**self.artifacts, **other.artifacts}
        merged_metadata = {**self.metadata, **other.metadata}
        merged_chain = self._handoff_chain + other._handoff_chain

        merged_state = HandoffState(
            context=other.context,  # Later wins
            next_instruction=other.next_instruction,  # Later wins
            artifacts=merged_artifacts,
            metadata=merged_metadata
        )
        merged_state._handoff_chain = merged_chain

        return merged_state

    def record_handoff(self, from_agent: str, to_agent: str) -> None:
        """Record a handoff in the chain."""
        self._handoff_chain.append({
            "from": from_agent,
            "to": to_agent
        })

    def get_handoff_chain(self) -> list[dict[str, str]]:
        """Get the handoff chain history."""
        return self._handoff_chain.copy()

    def update_instruction(self, instruction: str) -> None:
        """Update the next instruction."""
        self.next_instruction = instruction

    def clear_artifacts(self) -> None:
        """Clear all artifacts while preserving other state."""
        self.artifacts = {}


# ============================================================================
# Premise Builder
# ============================================================================


def build_premise(
    role: str,
    task: str,
    do: list[str],
    dont: list[str],
    examples: list[str] | None = None,
) -> str:
    """
    Build a structured agent premise from components.

    Based on research findings (thoughts/shared/work/build-premise-pipeline/01-research-findings.md):
    - Instructions account for ~80% of task success
    - Structured sections (DO/DON'T) outperform prose (85% vs 60% compliance)
    - 2-3 examples improve compliance from 60% to 95%
    - Optimal counts: 3-5 DO items, 3-5 DON'T items

    Args:
        role: Functional role identity (e.g., "Research Agent")
        task: Specific task description
        do: List of 3-5 action items (use empty list to omit section)
        dont: List of 3-5 anti-patterns (use empty list to omit section)
        examples: Optional 2-3 concrete examples

    Returns:
        Formatted premise string for spawn()

    Raises:
        ValueError: If role or task is empty/whitespace-only

    Example:
        >>> premise = build_premise(
        ...     role="Code Review Agent",
        ...     task="Review Python files for security issues",
        ...     do=["Check for SQL injection", "Flag hardcoded secrets"],
        ...     dont=["Suggest style changes", "Rewrite entire functions"],
        ... )
        >>> agent = await spawn(premise=premise)

        Output format:
        ROLE: Code Review Agent

        TASK: Review Python files for security issues

        DO:
        - Check for SQL injection
        - Flag hardcoded secrets

        DON'T:
        - Suggest style changes
        - Rewrite entire functions
    """
    # Validate required fields
    if not role or not role.strip():
        raise ValueError("role cannot be empty")
    if not task or not task.strip():
        raise ValueError("task cannot be empty")

    # Sanitize list items: filter None, empty strings, whitespace-only
    # and replace newlines with spaces
    def sanitize_items(items: list[str]) -> list[str]:
        return [
            item.replace('\n', ' ')
            for item in items
            if item is not None and item.strip()
        ]

    do = sanitize_items(do)
    dont = sanitize_items(dont)
    if examples:
        examples = sanitize_items(examples)

    sections = [f"ROLE: {role}", f"TASK: {task}"]

    if do:
        do_items = "\n".join(f"- {item}" for item in do)
        sections.append(f"DO:\n{do_items}")

    if dont:
        dont_items = "\n".join(f"- {item}" for item in dont)
        sections.append(f"DON'T:\n{dont_items}")

    if examples:
        example_items = "\n".join(f"- {ex}" for ex in examples)
        sections.append(f"EXAMPLES:\n{example_items}")

    return "\n\n".join(sections)
