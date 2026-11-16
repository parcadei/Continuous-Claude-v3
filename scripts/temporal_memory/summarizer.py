"""
Temporal Summarizer - Token-efficient memory summarization.

Implements Phases 3.1-3.5 of the temporal memory system:
- 3.1: Invariant detection
- 3.2: Utility scoring with 15-turn half-life
- 3.3: Transition extraction ranked by utility
- 3.4: Token budgeting
- 3.5: Q-value ranking for open questions

Usage:
    from scripts.temporal_memory.summarizer import TemporalSummarizer

    summarizer = TemporalSummarizer()
    summary = await summarizer.summarize(store, budget_tokens=500)
"""
from collections import Counter
from dataclasses import dataclass
from typing import Any, TypedDict

from .atoms import TemporalAtom, TemporalOperator
from .store import TemporalMemoryStore


@dataclass
class Transition:
    """State transition record.

    Represents a change in fact value between turns.

    Attributes:
        from_state: Previous state (e.g., "phase=planning")
        to_state: New state (e.g., "phase=testing")
        trigger: What caused the transition (e.g., "observation")
        turn: Turn number when transition occurred
        utility: Computed utility score for ranking
    """

    from_state: str
    to_state: str
    trigger: str
    turn: int
    utility: float = 0.0


class TemporalSummary(TypedDict):
    """Structured temporal summary output.

    All fields are required for a complete summary.

    Attributes:
        open_questions: List of unresolved questions (unknowns)
        invariants: List of facts that never changed (compact TEL format)
        pending_goals: List of goal_* facts not yet achieved
        transitions: List of significant state changes (formatted strings)
        current_state: Dict of all current fact values
        turn_count: Current turn number
        token_estimate: Estimated token count for summary
    """

    open_questions: list[str]
    invariants: list[str]
    pending_goals: list[str]
    transitions: list[str]
    current_state: dict[str, Any]
    turn_count: int
    token_estimate: int


class TemporalSummarizer:
    """Summarize temporal memory with token budgeting.

    This class extracts key information from a TemporalMemoryStore
    and produces token-efficient summaries suitable for inclusion
    in Claude's context window.

    Attributes:
        confidence_threshold: Minimum confidence for invariant detection (default 0.8)

    Example:
        >>> summarizer = TemporalSummarizer(confidence_threshold=0.8)
        >>> invariants = await summarizer.extract_invariants(store)
        >>> summary = await summarizer.summarize(store, budget_tokens=500)
    """

    def __init__(self, confidence_threshold: float = 0.8):
        """Initialize the summarizer.

        Args:
            confidence_threshold: Minimum confidence (0-1) for a fact to be
                considered an invariant. Higher values require more consistent
                presence across turns.
        """
        self.confidence_threshold = confidence_threshold

    async def extract_invariants(
        self, store: TemporalMemoryStore
    ) -> list[TemporalAtom]:
        """Extract facts that never changed (true invariants).

        Analyzes the temporal trace to find facts that:
        1. Are present in at least `confidence_threshold` fraction of turns
        2. Have consistent values (>90% of the time)

        Args:
            store: The temporal memory store to analyze

        Returns:
            List of TemporalAtom objects with ALWAYS operator,
            each representing an invariant fact.

        Example:
            >>> await store.record(turn=1, facts={"db": "sqlite", "phase": "init"})
            >>> await store.record(turn=2, facts={"db": "sqlite", "phase": "done"})
            >>> invariants = await summarizer.extract_invariants(store)
            >>> # db is invariant (never changed), phase is not
        """
        trace = await store.get_trace()
        if not trace:
            return []

        # Collect all keys and their values across turns
        all_keys: set[str] = set()
        key_values: dict[str, list[Any]] = {}

        for turn_data in trace:
            facts = turn_data.get("facts", {})
            for key, value in facts.items():
                all_keys.add(key)
                key_values.setdefault(key, []).append(value)

        invariants = []
        num_turns = len(trace)

        for key in all_keys:
            values = key_values.get(key, [])
            if not values:
                continue

            # Calculate presence ratio (how often the fact appears)
            presence_ratio = len(values) / num_turns

            # Calculate consistency ratio (how often the same value appears)
            value_counts = Counter(values)
            most_common_value, count = value_counts.most_common(1)[0]
            consistency_ratio = count / len(values)

            # Fact is invariant if present enough and consistent
            if presence_ratio >= self.confidence_threshold and consistency_ratio >= 0.9:
                confidence = presence_ratio * consistency_ratio
                invariants.append(
                    TemporalAtom(
                        operator=TemporalOperator.ALWAYS,
                        fact=key,
                        value=most_common_value,
                        turn=0,
                        metadata={"confidence": confidence},
                    )
                )

        return invariants

    def _compute_utility(
        self,
        transition: Transition,
        current_turn: int,
        q_value: float = 1.0,
        access_count: int = 1,
        max_accesses: int = 10,
    ) -> float:
        """Compute utility score for a transition.

        U(event) = importance * recency * access_frequency

        Uses a 15-turn half-life for recency decay, meaning events
        15 turns ago have half the recency weight of current events.

        Args:
            transition: The transition to score
            current_turn: Current turn number for recency calculation
            q_value: Importance multiplier (default 1.0)
            access_count: How often this fact has been accessed
            max_accesses: Maximum access count for normalization

        Returns:
            Utility score (higher = more important to include)

        Example:
            >>> t = Transition("a=1", "a=2", "update", turn=5)
            >>> u = summarizer._compute_utility(t, current_turn=10)
            >>> # Returns ~0.7 (decayed by ~5/15 of half-life)
        """
        # Calculate age in turns
        age = current_turn - transition.turn

        # Recency with 15-turn half-life
        # At age=0: recency=1.0
        # At age=15: recency=0.5
        # At age=30: recency=0.25
        recency = 0.5 ** (age / 15)

        # Importance from q-value
        importance = q_value

        # Frequency factor: scale from 0.5 to 1.0 based on access ratio
        frequency = access_count / max(max_accesses, 1)
        frequency_factor = 0.5 + 0.5 * frequency

        return importance * recency * frequency_factor

    async def extract_transitions(
        self, store: TemporalMemoryStore, max_transitions: int = 7
    ) -> list[Transition]:
        """Extract significant state transitions, ranked by utility.

        Analyzes the temporal trace to find value changes and ranks
        them by utility (importance * recency * frequency).

        The default limit of 7 follows Miller's Law (7 +/- 2 items
        for working memory).

        Args:
            store: The temporal memory store to analyze
            max_transitions: Maximum transitions to return (default 7)

        Returns:
            List of Transition objects, sorted by utility descending.

        Example:
            >>> await store.record(turn=1, facts={"phase": "planning"})
            >>> await store.record(turn=2, facts={"phase": "coding"})
            >>> transitions = await summarizer.extract_transitions(store)
            >>> # Returns [Transition(from="phase=planning", to="phase=coding", ...)]
        """
        trace = await store.get_trace()
        if len(trace) < 2:
            return []

        current_turn = store._current_turn
        transitions = []

        # Compare consecutive turns to find changes
        for i in range(1, len(trace)):
            prev = trace[i - 1].get("facts", {})
            curr = trace[i].get("facts", {})

            for key in curr:
                if key in prev and str(prev[key]) != str(curr[key]):
                    t = Transition(
                        from_state=f"{key}={prev[key]}",
                        to_state=f"{key}={curr[key]}",
                        trigger="observation",
                        turn=trace[i]["turn"],
                    )
                    t.utility = self._compute_utility(t, current_turn)
                    transitions.append(t)

        # Sort by utility descending (most important first)
        transitions.sort(key=lambda t: t.utility, reverse=True)

        return transitions[:max_transitions]

    async def summarize(
        self, store: TemporalMemoryStore, budget_tokens: int = 2000
    ) -> TemporalSummary:
        """Generate token-budgeted temporal summary.

        Produces a structured summary containing:
        - Open questions (unknowns from erotetic analysis)
        - Invariants (facts that never changed)
        - Pending goals (goal_* facts not yet achieved)
        - Transitions (significant state changes)
        - Current state (all current fact values)

        The summary respects the token budget by truncating transitions
        if necessary.

        Args:
            store: The temporal memory store to summarize
            budget_tokens: Maximum estimated tokens for summary (default 2000)

        Returns:
            TemporalSummary with all fields populated.

        Example:
            >>> summary = await summarizer.summarize(store, budget_tokens=500)
            >>> print(f"Turn {summary['turn_count']}: {summary['token_estimate']} tokens")
        """
        # 1. Open questions (from erotetic analysis)
        open_questions = await store.get_open_questions()

        # 2. Invariants (facts that never changed)
        invariants_raw = await self.extract_invariants(store)
        invariants = [inv.to_compact() for inv in invariants_raw]

        # 3. Pending goals (goal_* facts not achieved)
        pending = await self._extract_pending_goals(store)

        # 4. Transitions (utility-ranked)
        transitions_raw = await self.extract_transitions(store)
        transitions = [
            f"T={t.turn}: {t.from_state} -> {t.to_state}" for t in transitions_raw
        ]

        # 5. Current state
        current = await store.get_current_state()

        # Estimate tokens (rough: 1 token ~= 4 chars)
        current_chars = sum(
            len(str(k)) + len(str(v)) for k, v in current.items()
        )
        total_chars = (
            sum(len(q) for q in open_questions)
            + sum(len(i) for i in invariants)
            + sum(len(p) for p in pending)
            + sum(len(t) for t in transitions)
            + current_chars
        )
        token_estimate = max(total_chars // 4, 1) if total_chars > 0 else 0

        # Truncate transitions if over budget
        if token_estimate > budget_tokens and len(transitions) > 1:
            # Calculate how much we need to cut
            ratio = budget_tokens / token_estimate
            max_transitions = max(1, int(len(transitions) * ratio))
            transitions = transitions[:max_transitions]

            # Recalculate token estimate
            total_chars = (
                sum(len(q) for q in open_questions)
                + sum(len(i) for i in invariants)
                + sum(len(p) for p in pending)
                + sum(len(t) for t in transitions)
                + current_chars
            )
            token_estimate = max(total_chars // 4, 1) if total_chars > 0 else 0

        return TemporalSummary(
            open_questions=open_questions,
            invariants=invariants,
            pending_goals=pending,
            transitions=transitions,
            current_state=current,
            turn_count=store._current_turn,
            token_estimate=token_estimate,
        )

    async def _extract_pending_goals(self, store: TemporalMemoryStore) -> list[str]:
        """Extract facts marked as goals not yet achieved.

        Goals are identified by the naming convention: keys starting
        with "goal_" that have a value other than "achieved".

        Args:
            store: The temporal memory store to analyze

        Returns:
            List of pending goal names (e.g., ["goal_tests", "goal_docs"])
        """
        current = await store.get_current_state()
        return [
            k for k, v in current.items() if k.startswith("goal_") and v != "achieved"
        ]

    def rank_open_questions(
        self, unknowns: list[str]
    ) -> list[tuple[str, str, str]]:
        """Rank open questions by Q-value (HIGH first).

        Uses the erotetic Q-value ranking system to prioritize
        questions by architectural impact. Questions not in the
        Q_CONFIGS registry get MED priority.

        Args:
            unknowns: List of unknown proposition names

        Returns:
            List of (question, q_value, why) tuples sorted by priority.
            q_value is "HIGH", "MED", or "LOW".
            why explains the importance.

        Example:
            >>> ranked = summarizer.rank_open_questions(["framework", "cache"])
            >>> ranked[0]
            ('framework', 'HIGH', 'Framework choice partitions entire solution architecture')
        """
        if not unknowns:
            return []

        # Try to import Q-value ranking
        try:
            from scripts.erotetic_q_ranking import get_q_config

            use_q_config = True
        except ImportError:
            use_q_config = False

        ranked = []
        for q in unknowns:
            if use_q_config:
                try:
                    config = get_q_config(q)
                    ranked.append((q, config.q_value, config.why))
                except Exception:
                    ranked.append((q, "MED", "Not in Q_CONFIGS"))
            else:
                ranked.append((q, "MED", "Not in Q_CONFIGS"))

        # Sort by priority: HIGH > MED > LOW
        priority_order = {"HIGH": 0, "MED": 1, "LOW": 2}
        ranked.sort(key=lambda x: priority_order.get(x[1], 1))

        return ranked
