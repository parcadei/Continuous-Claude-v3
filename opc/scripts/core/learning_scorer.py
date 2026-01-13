#!/usr/bin/env python3
"""Confidence scoring for learning quality gate and MMR retrieval.

This module provides quality scoring for learnings to:
1. Gate storage based on confidence thresholds
2. Infer learning types from content
3. Filter out low-quality/benchmark data
4. Support MMR (Maximal Marginal Relevance) retrieval

Usage:
    from scripts.core.learning_scorer import scorer, LearningScore

    score = scorer.score(content, metadata)
    if scorer.should_store(score):
        # Store with type from score.suggested_type
        pass
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re


class ConfidenceLevel(Enum):
    """Confidence thresholds for learning quality gates."""
    HIGH = 0.8
    MEDIUM = 0.5
    LOW = 0.3


class LearningType(Enum):
    """Learning type taxonomy matching store_learning.py."""
    ARCHITECTURAL_DECISION = "ARCHITECTURAL_DECISION"
    WORKING_SOLUTION = "WORKING_SOLUTION"
    CODEBASE_PATTERN = "CODEBASE_PATTERN"
    FAILED_APPROACH = "FAILED_APPROACH"
    ERROR_FIX = "ERROR_FIX"
    USER_PREFERENCE = "USER_PREFERENCE"
    OPEN_THREAD = "OPEN_THREAD"


@dataclass
class LearningScore:
    """Scored learning with confidence and quality metrics."""
    id: str
    content: str
    confidence: float
    is_high_quality: bool
    quality_signals: list[str]
    suggested_type: Optional[LearningType]


class LearningScorer:
    """Score and filter learnings based on quality signals.

    Scoring algorithm:
    - Start at 0.5 (MEDIUM confidence)
    - Add points for high-quality patterns
    - Subtract points for low-quality patterns
    - Clamp to [0.0, 1.0]
    - HIGH quality: confidence >= 0.8
    """

    # Patterns indicating high-quality learning
    # These capture actionable insights, decisions, and discoveries
    HIGH_QUALITY_PATTERNS = [
        r"(?i)(worked|solved|fixed|implemented|created|built)",  # Successful actions
        r"(?i)(pattern|architecture|design|decision|chose|selected)",  # Design insights
        r"(?i)(learned|discovered|found that|realized|noticed)",  # Discovery language
        r"(?i)(avoid|don't|never|warning|caution|important)",  # Negative patterns (lessons learned)
        r"(?i)(best practice|recommended|instead use|prefer)",  # Recommendations
    ]

    # Patterns indicating low-quality (skip candidates)
    LOW_QUALITY_PATTERNS = [
        r"(?i)(test|benchmark|placeholder|temp|demo|sample)",  # Synthetic data
        r"(?i)^(yes|no|ok|maybe|true|false)$",  # Non-substantive content
        r"^\s*[\{\}\[\]\(\)]\s*$",  # Empty-ish structural content
        r"(?i)(^|\s)todo\b",  # TODOs (not learnings yet)
    ]

    # Minimum length for meaningful content
    MIN_CONTENT_LENGTH = 50

    # Length thresholds
    IDEAL_LENGTH_MIN = 100
    IDEAL_LENGTH_MAX = 5000

    def score(self, content: str, metadata: dict = None) -> LearningScore:
        """Score a learning based on quality signals.

        Args:
            content: The learning content to score
            metadata: Optional metadata dict (unused but available for extension)

        Returns:
            LearningScore with confidence, signals, and suggested type
        """
        quality_signals = []
        confidence = 0.5  # Start at medium

        # Check length
        content_len = len(content.strip())
        if content_len < self.MIN_CONTENT_LENGTH:
            confidence = 0.2
            quality_signals.append("content_too_short")
        elif content_len >= self.IDEAL_LENGTH_MIN and content_len <= self.IDEAL_LENGTH_MAX:
            confidence += 0.1
            quality_signals.append("good_length")
        elif content_len > self.IDEAL_LENGTH_MAX:
            confidence -= 0.1
            quality_signals.append("content_too_long")

        # Check for high-quality patterns
        for pattern in self.HIGH_QUALITY_PATTERNS:
            if re.search(pattern, content):
                confidence += 0.15
                # Extract the matched phrase for the signal
                match = re.search(pattern, content)
                signal_name = f"high_quality:{match.group(0)[:30]}"
                quality_signals.append(signal_name)

        # Check for low-quality patterns
        for pattern in self.LOW_QUALITY_PATTERNS:
            if re.search(pattern, content):
                confidence -= 0.3
                match = re.search(pattern, content)
                signal_name = f"low_quality:{match.group(0)[:30]}"
                quality_signals.append(signal_name)

        # Clamp confidence to [0.0, 1.0]
        confidence = max(0.0, min(1.0, confidence))

        # Determine quality level
        is_high_quality = confidence >= ConfidenceLevel.HIGH.value

        # Suggest learning type
        suggested_type = self._infer_type(content)

        return LearningScore(
            id="",  # Will be filled by caller (memory_id)
            content=content,
            confidence=confidence,
            is_high_quality=is_high_quality,
            quality_signals=quality_signals,
            suggested_type=suggested_type,
        )

    def _infer_type(self, content: str) -> Optional[LearningType]:
        """Infer learning type from content patterns.

        Args:
            content: Learning content to analyze

        Returns:
            Suggested LearningType or None
        """
        content_lower = content.lower()

        # Order matters - more specific patterns first
        if any(w in content_lower for w in ["avoid", "don't", "never", "caution", "warning"]):
            return LearningType.FAILED_APPROACH
        elif any(w in content_lower for w in ["error", "exception", "traceback", "failed"]):
            return LearningType.ERROR_FIX
        elif any(w in content_lower for w in ["decision", "chose", "selected", "architecture", "design"]):
            return LearningType.ARCHITECTURAL_DECISION
        elif any(w in content_lower for w in ["pattern", "found in", "discovered", "how to"]):
            return LearningType.CODEBASE_PATTERN
        elif any(w in content_lower for w in ["solved", "fixed", "worked", "implemented", "created"]):
            return LearningType.WORKING_SOLUTION
        elif any(w in content_lower for w in ["prefer", "like", "want", "should"]):
            return LearningType.USER_PREFERENCE
        elif any(w in content_lower for w in ["todo", "open thread", "unfinished", "continue"]):
            return LearningType.OPEN_THREAD

        return None

    def should_store(self, score: LearningScore) -> bool:
        """Determine if learning should be stored based on confidence gate.

        Args:
            score: Scored learning

        Returns:
            True if should store, False to skip
        """
        if score.confidence >= ConfidenceLevel.HIGH.value:
            return True  # Store immediately (high quality)
        elif score.confidence >= ConfidenceLevel.MEDIUM.value:
            return True  # Store with review flag (medium quality)
        elif score.confidence >= ConfidenceLevel.LOW.value:
            return False  # Skip unless explicitly requested
        return False  # Discard (below threshold)

    def get_storage_decision(self, score: LearningScore) -> dict:
        """Get detailed storage decision for UI/logging.

        Args:
            score: Scored learning

        Returns:
            Dict with decision, reason, and flags
        """
        if score.confidence >= ConfidenceLevel.HIGH.value:
            return {
                "action": "store",
                "priority": "high",
                "reason": f"High confidence ({score.confidence:.2f})",
                "needs_review": False,
            }
        elif score.confidence >= ConfidenceLevel.MEDIUM.value:
            return {
                "action": "store",
                "priority": "medium",
                "reason": f"Medium confidence ({score.confidence:.2f}) - flag for review",
                "needs_review": True,
            }
        elif score.confidence >= ConfidenceLevel.LOW.value:
            return {
                "action": "skip",
                "priority": "low",
                "reason": f"Below threshold ({score.confidence:.2f})",
                "needs_review": False,
            }
        else:
            return {
                "action": "discard",
                "priority": "discard",
                "reason": f"Very low confidence ({score.confidence:.2f})",
                "needs_review": False,
            }


def mmr_rerank(learnings: list[tuple[str, list[float]]], lambda_param: float = 0.5, top_k: int = 10) -> list[int]:
    """Maximal Marginal Relevance reranking for diverse results.

    Args:
        learnings: List of (id, embedding) tuples
        lambda_param: Balance between relevance and diversity (0.5 = equal)
        top_k: Number of results to return

    Returns:
        List of indices to select (in original order)
    """
    if not learnings:
        return []

    if len(learnings) <= top_k:
        return list(range(len(learnings)))

    # Simple implementation for demonstration
    # In production, use proper MMR formula with precomputed similarities
    selected = []
    remaining = list(range(len(learnings)))

    for _ in range(min(top_k, len(learnings))):
        if not remaining:
            break

        # First iteration: select highest relevance (first item)
        if not selected:
            idx = remaining.pop(0)
            selected.append(idx)
            continue

        # Calculate MMR scores for remaining items
        mmr_scores = []
        for idx in remaining:
            relevance = 1.0 - idx / len(learnings)  # Simplified relevance
            diversity = min(
                abs(idx - s) for s in selected
            ) / len(learnings)  # Max distance to selected

            mmr_score = lambda_param * relevance + (1 - lambda_param) * diversity
            mmr_scores.append((idx, mmr_score))

        # Select item with highest MMR score
        mmr_scores.sort(key=lambda x: x[1], reverse=True)
        idx = mmr_scores[0][0]
        remaining.remove(idx)
        selected.append(idx)

    return selected


# Singleton instance
scorer = LearningScorer()


# Convenience function for CLI usage
def score_content(content: str, verbose: bool = False) -> dict:
    """Score content and return decision.

    Args:
        content: Learning content to score
        verbose: Include detailed signals

    Returns:
        Dict with score, decision, and signals
    """
    score = scorer.score(content)
    decision = scorer.get_storage_decision(score)

    result = {
        "confidence": score.confidence,
        "is_high_quality": score.is_high_quality,
        "decision": decision["action"],
        "reason": decision["reason"],
        "suggested_type": score.suggested_type.value if score.suggested_type else None,
    }

    if verbose:
        result["quality_signals"] = score.quality_signals

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Score learning content quality")
    parser.add_argument("content", help="Content to score")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed signals")

    args = parser.parse_args()

    result = score_content(args.content, verbose=args.verbose)

    print(f"Confidence: {result['confidence']:.2f}")
    print(f"High Quality: {result['is_high_quality']}")
    print(f"Decision: {result['decision']}")
    print(f"Reason: {result['reason']}")
    print(f"Suggested Type: {result['suggested_type']}")

    if args.verbose:
        print(f"Quality Signals: {result.get('quality_signals', [])}")
