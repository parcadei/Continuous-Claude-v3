"""
Inference-First Pattern Selection for Agentica Multi-Agent Orchestration.

This module implements natural language task analysis to infer the best
coordination pattern WITHOUT asking leading questions. CDM-style probes
are only used when genuinely ambiguous.

Design Principles:
1. Parse FIRST, ask ONLY if ambiguous
2. No pattern names shown to users - show work breakdown instead
3. CDM probes are concrete: "What would tell you this is fixed?" not "Is correctness important?"
4. Confidence scoring based on signal strength
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import re


# ============================================================================
# Vocabulary Sets for Classification
# ============================================================================

EXPLORATION_VERBS = frozenset({
    "understand", "explain", "research", "investigate", "explore", "learn",
    "discover", "how does", "what is", "where", "find", "analyze", "study",
    "examine", "look into", "dig into", "figure out", "comprehend", "clarify"
})

CONSTRUCTION_VERBS = frozenset({
    "build", "create", "implement", "develop", "add", "write", "make", "fix",
    "update", "refactor", "construct", "setup", "configure", "install",
    "deploy", "modify", "change", "extend", "enhance", "upgrade"
})

VALIDATION_VERBS = frozenset({
    "validate", "verify", "check", "review", "confirm", "ensure", "test",
    "audit", "inspect", "examine", "assess", "evaluate", "approve", "certify",
    "quality", "qa", "security review", "code review"
})

COMPARISON_VERBS = frozenset({
    "compare", "versus", "tradeoffs", "pros and cons", "which is better",
    "evaluate options", "weigh", "contrast", "difference between",
    "advantages", "disadvantages", "should i use", "pick between", "choose"
})

TRANSFORMATION_VERBS = frozenset({
    "migrate", "convert", "transform", "process", "parse", "extract",
    "translate", "import", "export", "format", "reformat", "normalize",
    "clean", "sanitize", "batch", "bulk"
})

# Structural signals for workflow type
SEQUENTIAL_SIGNALS = frozenset({
    "then", "after", "first", "next", "finally", "before", "once",
    "step by step", "in order", "followed by", "subsequently", "lastly",
    "start with", "begin by", "end with"
})

PARALLEL_SIGNALS = frozenset({
    "and", "also", "each", "all of", "independently", "simultaneously",
    "multiple", "various", "several", "at the same time", "together",
    "concurrently", "in parallel"
})

# Risk/stakes indicators
HIGH_STAKES_TERMS = frozenset({
    "production", "security", "critical", "important", "must be correct",
    "sensitive", "breaking change", "customer", "financial", "medical",
    "legal", "compliance", "audit", "pci", "hipaa", "gdpr", "soc2",
    "cannot fail", "zero downtime", "mission critical"
})


# ============================================================================
# Pattern Types
# ============================================================================

class Pattern(str, Enum):
    """Multi-agent coordination patterns."""
    SWARM = "swarm"
    HIERARCHICAL = "hierarchical"
    PIPELINE = "pipeline"
    GENERATOR_CRITIC = "generator_critic"
    ADVERSARIAL = "adversarial"
    MAP_REDUCE = "map_reduce"
    JURY = "jury"
    BLACKBOARD = "blackboard"
    CIRCUIT_BREAKER = "circuit_breaker"
    CHAIN_OF_RESPONSIBILITY = "chain_of_responsibility"
    EVENT_DRIVEN = "event_driven"


# Pattern descriptions for work breakdown (user-facing)
PATTERN_DESCRIPTIONS = {
    Pattern.SWARM: "Parallel exploration from multiple angles",
    Pattern.HIERARCHICAL: "Coordinated task decomposition with specialists",
    Pattern.PIPELINE: "Sequential processing through defined stages",
    Pattern.GENERATOR_CRITIC: "Iterative refinement with feedback",
    Pattern.ADVERSARIAL: "Debate and stress-testing from opposing views",
    Pattern.MAP_REDUCE: "Parallel processing with aggregation",
    Pattern.JURY: "Independent evaluation with consensus voting",
    Pattern.BLACKBOARD: "Collaborative problem-solving on shared state",
    Pattern.CIRCUIT_BREAKER: "Primary path with fallback",
    Pattern.CHAIN_OF_RESPONSIBILITY: "Capability-based routing",
    Pattern.EVENT_DRIVEN: "Reactive agents responding to events",
}


# ============================================================================
# Ambiguity Types
# ============================================================================

class AmbiguityType(str, Enum):
    """Types of ambiguity that require clarification."""
    SCOPE = "scope"  # How much work is involved?
    DEPENDENCIES = "dependencies"  # What must happen in order?
    RISK = "risk"  # How critical is correctness?
    PARALLELISM = "parallelism"  # Can work happen independently?
    ITERATION = "iteration"  # Will this need refinement?


# CDM-style concrete probes for each ambiguity type
CDM_PROBES = {
    AmbiguityType.SCOPE: [
        "Walk me through what you'd check first.",
        "What files or areas would this touch?",
        "Can you give me a specific example of what needs to change?",
    ],
    AmbiguityType.DEPENDENCIES: [
        "What has to be done before X can start?",
        "Is there anything that would block the next step?",
        "Can any of these happen at the same time?",
    ],
    AmbiguityType.RISK: [
        "What would make this completely fail?",
        "What's the worst case if we get this wrong?",
        "Are there any irreversible actions here?",
    ],
    AmbiguityType.PARALLELISM: [
        "Can these be done independently, or does one depend on the other?",
        "Would getting more perspectives help here?",
        "Is there a clear sequence, or can we explore multiple angles?",
    ],
    AmbiguityType.ITERATION: [
        "Is there a 'good enough' or does this need to be perfect?",
        "Will you want to review and refine this?",
        "How will you know when this is done?",
    ],
}


# ============================================================================
# Pattern Inference Result
# ============================================================================

@dataclass
class PatternInference:
    """Result of pattern inference from user prompt."""

    pattern: Pattern
    confidence: float  # 0.0 to 1.0
    signals: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_probe: Optional[str] = None
    ambiguity_type: Optional[AmbiguityType] = None

    # Secondary patterns that might also apply
    alternatives: list[Pattern] = field(default_factory=list)

    def get_work_breakdown(self) -> str:
        """
        Generate user-facing work breakdown without pattern names.

        Returns description of how work will be organized.
        """
        return PATTERN_DESCRIPTIONS.get(self.pattern, "Orchestrated task execution")

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON output."""
        return {
            "pattern": self.pattern.value,
            "confidence": self.confidence,
            "signals": self.signals,
            "needs_clarification": self.needs_clarification,
            "clarification_probe": self.clarification_probe,
            "ambiguity_type": self.ambiguity_type.value if self.ambiguity_type else None,
            "alternatives": [p.value for p in self.alternatives],
            "work_breakdown": self.get_work_breakdown(),
        }


# ============================================================================
# Signal Detection
# ============================================================================

def _normalize_prompt(prompt: str) -> str:
    """Normalize prompt for matching (lowercase, extra spaces removed)."""
    return " ".join(prompt.lower().split())


def _count_matches(text: str, vocabulary: frozenset) -> tuple[int, list[str]]:
    """
    Count vocabulary matches and return matched terms.

    Returns:
        Tuple of (count, list of matched terms)
    """
    matched = []
    for term in vocabulary:
        # Handle multi-word terms
        if " " in term:
            if term in text:
                matched.append(term)
        else:
            # Word boundary matching for single words
            pattern = rf'\b{re.escape(term)}\b'
            if re.search(pattern, text):
                matched.append(term)
    return len(matched), matched


def _has_sequential_structure(text: str) -> tuple[bool, list[str]]:
    """Detect sequential workflow signals."""
    count, matched = _count_matches(text, SEQUENTIAL_SIGNALS)
    return count >= 2, matched  # Require at least 2 sequential signals


def _has_parallel_structure(text: str) -> tuple[bool, list[str]]:
    """Detect parallel workflow signals."""
    count, matched = _count_matches(text, PARALLEL_SIGNALS)
    return count >= 1, matched


def _is_high_stakes(text: str) -> tuple[bool, list[str]]:
    """Detect high-stakes indicators."""
    count, matched = _count_matches(text, HIGH_STAKES_TERMS)
    return count >= 1, matched


# ============================================================================
# Pattern Selection Logic
# ============================================================================

def _score_pattern(
    text: str,
    pattern: Pattern,
) -> tuple[float, list[str]]:
    """
    Score how well a pattern matches the given text.

    Returns:
        Tuple of (score 0-1, list of signals that matched)
    """
    signals = []
    score = 0.0

    if pattern == Pattern.SWARM:
        # Exploration + parallel OR research-focused
        exp_count, exp_matched = _count_matches(text, EXPLORATION_VERBS)
        par_has, par_matched = _has_parallel_structure(text)

        if exp_count >= 1:
            score += 0.4 * min(exp_count / 2, 1.0)
            signals.extend(exp_matched[:2])
        if par_has:
            score += 0.3
            signals.extend(par_matched[:1])
        # Boost for research keywords
        if any(kw in text for kw in ["research", "investigate", "explore", "understand"]):
            score += 0.2

    elif pattern == Pattern.HIERARCHICAL:
        # Construction + complex scope
        con_count, con_matched = _count_matches(text, CONSTRUCTION_VERBS)

        if con_count >= 1:
            score += 0.4 * min(con_count / 2, 1.0)
            signals.extend(con_matched[:2])
        # Boost for implementation keywords
        if any(kw in text for kw in ["build", "implement", "create", "develop"]):
            score += 0.3
        # Boost for multi-component hints
        if any(kw in text for kw in ["api", "endpoint", "feature", "component", "module"]):
            score += 0.2

    elif pattern == Pattern.PIPELINE:
        # Sequential structure is primary signal
        seq_has, seq_matched = _has_sequential_structure(text)
        trans_count, trans_matched = _count_matches(text, TRANSFORMATION_VERBS)

        if seq_has:
            score += 0.5
            signals.extend(seq_matched[:2])
        if trans_count >= 1:
            score += 0.3 * min(trans_count / 2, 1.0)
            signals.extend(trans_matched[:2])

    elif pattern == Pattern.GENERATOR_CRITIC:
        # Validation + iteration hints
        val_count, val_matched = _count_matches(text, VALIDATION_VERBS)

        if val_count >= 1:
            score += 0.3 * min(val_count / 2, 1.0)
            signals.extend(val_matched[:2])
        # Boost for review/refine keywords
        if any(kw in text for kw in ["review", "refine", "improve", "iterate", "feedback"]):
            score += 0.4
        # PR review is strong signal
        if any(kw in text for kw in ["pr ", "pull request", "code review"]):
            score += 0.3

    elif pattern == Pattern.ADVERSARIAL:
        # Comparison verbs + debate hints
        cmp_count, cmp_matched = _count_matches(text, COMPARISON_VERBS)

        if cmp_count >= 1:
            score += 0.5 * min(cmp_count / 2, 1.0)
            signals.extend(cmp_matched[:2])
        # Boost for debate/comparison keywords
        if any(kw in text for kw in ["vs", "versus", "compare", "tradeoff", "debate"]):
            score += 0.3

    elif pattern == Pattern.MAP_REDUCE:
        # Parallel + transformation/processing
        par_has, par_matched = _has_parallel_structure(text)
        trans_count, trans_matched = _count_matches(text, TRANSFORMATION_VERBS)

        if par_has:
            score += 0.3
            signals.extend(par_matched[:1])
        if trans_count >= 1:
            score += 0.3 * min(trans_count / 2, 1.0)
            signals.extend(trans_matched[:2])
        # Boost for batch/bulk processing
        if any(kw in text for kw in ["all", "each", "every", "batch", "bulk", "process"]):
            score += 0.3

    elif pattern == Pattern.JURY:
        # High stakes + validation
        high_has, high_matched = _is_high_stakes(text)
        val_count, val_matched = _count_matches(text, VALIDATION_VERBS)

        if high_has:
            score += 0.5
            signals.extend(high_matched[:2])
        if val_count >= 1:
            score += 0.3 * min(val_count / 2, 1.0)
            signals.extend(val_matched[:1])
        # Boost for consensus keywords
        if any(kw in text for kw in ["consensus", "agreement", "vote", "decision"]):
            score += 0.2

    elif pattern == Pattern.BLACKBOARD:
        # Collaborative + multiple contributors
        if any(kw in text for kw in ["collaborate", "together", "shared", "contribute"]):
            score += 0.4
        par_has, par_matched = _has_parallel_structure(text)
        if par_has:
            score += 0.3
            signals.extend(par_matched[:1])

    elif pattern == Pattern.CIRCUIT_BREAKER:
        # Fallback + reliability hints
        if any(kw in text for kw in ["fallback", "backup", "if fails", "graceful"]):
            score += 0.5
        high_has, high_matched = _is_high_stakes(text)
        if high_has:
            score += 0.3
            signals.extend(high_matched[:1])

    elif pattern == Pattern.CHAIN_OF_RESPONSIBILITY:
        # Routing + capability matching
        if any(kw in text for kw in ["route", "dispatch", "forward", "delegate"]):
            score += 0.5
        if any(kw in text for kw in ["specialized", "expert", "capability"]):
            score += 0.3

    elif pattern == Pattern.EVENT_DRIVEN:
        # Event/trigger keywords
        if any(kw in text for kw in ["event", "trigger", "when", "react", "subscribe"]):
            score += 0.5
        if any(kw in text for kw in ["async", "webhook", "notification", "listener"]):
            score += 0.3

    return min(score, 1.0), signals


# ============================================================================
# Main Inference Function
# ============================================================================

def infer_pattern(user_prompt: str) -> PatternInference:
    """
    Infer the best pattern from natural language.

    Analyzes the user's prompt to determine which multi-agent coordination
    pattern best fits the task. Uses vocabulary matching and signal detection
    rather than asking leading questions.

    Args:
        user_prompt: The user's task description

    Returns:
        PatternInference with:
        - pattern: Best matching pattern
        - confidence: How confident (0-1)
        - signals: Detected signals from the prompt
        - needs_clarification: Whether to ask a CDM probe
        - clarification_probe: The probe to ask if needed
    """
    text = _normalize_prompt(user_prompt)

    # Score all patterns
    pattern_scores: list[tuple[Pattern, float, list[str]]] = []
    for pattern in Pattern:
        score, signals = _score_pattern(text, pattern)
        if score > 0:
            pattern_scores.append((pattern, score, signals))

    # Sort by score descending
    pattern_scores.sort(key=lambda x: x[1], reverse=True)

    # Handle empty results (no signals detected)
    if not pattern_scores:
        # Default to hierarchical for general tasks
        return PatternInference(
            pattern=Pattern.HIERARCHICAL,
            confidence=0.3,
            signals=["general task"],
            needs_clarification=True,
            clarification_probe=get_clarification_probe(AmbiguityType.SCOPE),
            ambiguity_type=AmbiguityType.SCOPE,
        )

    best_pattern, best_score, best_signals = pattern_scores[0]

    # Collect alternatives (patterns with significant scores)
    alternatives = [
        p for p, s, _ in pattern_scores[1:4]  # Top 3 alternatives
        if s >= 0.3  # Only if score is meaningful
    ]

    # Determine if clarification is needed
    needs_clarification = False
    clarification_probe = None
    ambiguity_type = None

    if best_score < 0.5:
        # Low confidence - need clarification
        needs_clarification = True

        # Determine what type of ambiguity
        if len(alternatives) >= 2 and pattern_scores[1][1] >= best_score * 0.8:
            # Multiple patterns are close - need to clarify scope/dependencies
            ambiguity_type = AmbiguityType.SCOPE
        elif _is_high_stakes(text)[0]:
            # High stakes but unclear pattern
            ambiguity_type = AmbiguityType.RISK
        else:
            # General ambiguity
            ambiguity_type = AmbiguityType.DEPENDENCIES

        clarification_probe = get_clarification_probe(ambiguity_type)

    elif len(alternatives) >= 1 and pattern_scores[1][1] >= best_score * 0.9:
        # Very close alternatives - might want to clarify
        needs_clarification = True
        ambiguity_type = AmbiguityType.PARALLELISM
        clarification_probe = get_clarification_probe(ambiguity_type)

    return PatternInference(
        pattern=best_pattern,
        confidence=best_score,
        signals=best_signals,
        needs_clarification=needs_clarification,
        clarification_probe=clarification_probe,
        ambiguity_type=ambiguity_type,
        alternatives=alternatives,
    )


def get_clarification_probe(ambiguity_type: AmbiguityType) -> str:
    """
    Return CDM-style concrete probe for ambiguous cases.

    These probes are designed to elicit specific, actionable information
    rather than abstract preferences.

    Args:
        ambiguity_type: Type of ambiguity to clarify

    Returns:
        A concrete question to ask the user
    """
    probes = CDM_PROBES.get(ambiguity_type, [])
    if probes:
        return probes[0]  # Return first (primary) probe
    return "Can you give me a specific example of what you want to achieve?"


def generate_work_breakdown(inference: PatternInference) -> str:
    """
    Generate a user-friendly work breakdown based on pattern inference.

    Does NOT expose pattern names - instead describes how work will be
    organized in user-friendly terms.

    Args:
        inference: The pattern inference result

    Returns:
        Human-readable work breakdown description
    """
    base_description = inference.get_work_breakdown()

    # Add detail based on pattern
    if inference.pattern == Pattern.SWARM:
        return f"{base_description}: Multiple agents will explore different aspects simultaneously, then synthesize findings."
    elif inference.pattern == Pattern.HIERARCHICAL:
        return f"{base_description}: Work will be broken into subtasks and assigned to specialist agents."
    elif inference.pattern == Pattern.PIPELINE:
        return f"{base_description}: Each stage will process and hand off to the next in sequence."
    elif inference.pattern == Pattern.GENERATOR_CRITIC:
        return f"{base_description}: One agent generates, another reviews, cycling until approved."
    elif inference.pattern == Pattern.ADVERSARIAL:
        return f"{base_description}: Opposing viewpoints will debate to find the strongest approach."
    elif inference.pattern == Pattern.MAP_REDUCE:
        return f"{base_description}: Work will be distributed, processed in parallel, then combined."
    elif inference.pattern == Pattern.JURY:
        return f"{base_description}: Multiple independent evaluations will vote for consensus."
    else:
        return base_description


# ============================================================================
# CLI Interface (for hook integration)
# ============================================================================

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python pattern_inference.py '<user_prompt>'", file=sys.stderr)
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    result = infer_pattern(prompt)

    # Output JSON for hook consumption
    output = result.to_dict()
    output["work_breakdown_detailed"] = generate_work_breakdown(result)

    print(json.dumps(output, indent=2))
