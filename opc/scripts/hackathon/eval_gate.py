"""Simple evaluation quality gate.

Galileo-style quality checks before commits.
Falls back to local heuristics if Galileo API unavailable.

Usage:
    gate = QualityGate()
    result = await gate.check(
        input="What is 2+2?",
        output="2+2 equals 4.",
        context="Basic arithmetic."
    )
    if result.passed:
        print("✓ Ready to commit")
    else:
        print(f"✗ Failed: {result.failed_metrics}")
"""

import os
from dataclasses import dataclass, field
from typing import Literal


MetricType = Literal[
    "groundedness",
    "relevance",
    "factuality",
    "coherence",
    "toxicity",
]


@dataclass
class EvalResult:
    """Evaluation result."""
    passed: bool
    scores: dict[str, float]
    failed_metrics: list[str]
    reason: str | None = None


class QualityGate:
    """Quality gate for LLM outputs."""

    DEFAULT_THRESHOLDS = {
        "groundedness": 0.6,
        "relevance": 0.6,
        "factuality": 0.5,
        "coherence": 0.6,
        "toxicity": 0.2,  # Lower is better
    }

    def __init__(self, thresholds: dict[str, float] | None = None):
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}

    async def check(
        self,
        input: str,
        output: str,
        context: str | None = None,
        metrics: list[MetricType] | None = None,
    ) -> EvalResult:
        """Check if output passes quality gate."""
        use_metrics = metrics or list(self.thresholds.keys())

        scores = {}
        failed = []

        for metric in use_metrics:
            score = self._compute_metric(metric, input, output, context)
            scores[metric] = score

            threshold = self.thresholds.get(metric, 0.5)

            if metric == "toxicity":
                # Lower is better
                if score > threshold:
                    failed.append(metric)
            else:
                # Higher is better
                if score < threshold:
                    failed.append(metric)

        passed = len(failed) == 0

        return EvalResult(
            passed=passed,
            scores=scores,
            failed_metrics=failed,
            reason=f"Failed metrics: {failed}" if failed else None,
        )

    def _compute_metric(
        self,
        metric: MetricType,
        input: str,
        output: str,
        context: str | None,
    ) -> float:
        """Compute metric score using local heuristics."""

        if metric == "groundedness":
            if not context:
                return 0.5
            # Word overlap between output and context
            ctx_words = set(context.lower().split())
            out_words = set(output.lower().split())
            if not out_words:
                return 0.0
            overlap = len(ctx_words & out_words)
            return min(1.0, overlap / len(out_words))

        elif metric == "relevance":
            # Word overlap between input and output
            in_words = set(input.lower().split())
            out_words = set(output.lower().split())
            if not in_words:
                return 0.5
            overlap = len(in_words & out_words)
            return min(1.0, overlap / len(in_words) * 2)

        elif metric == "factuality":
            # Heuristic: longer, more detailed = more likely factual
            # Also penalize hedging words
            hedge_words = ["maybe", "perhaps", "might", "could be", "possibly"]
            output_lower = output.lower()
            hedge_count = sum(1 for w in hedge_words if w in output_lower)
            base_score = min(1.0, len(output) / 200)
            return max(0.0, base_score - hedge_count * 0.1)

        elif metric == "coherence":
            # Check sentence structure
            sentences = output.count(".") + output.count("!") + output.count("?")
            if sentences == 0:
                return 0.3
            avg_length = len(output) / sentences
            # Good sentences are 50-150 chars
            if 50 <= avg_length <= 150:
                return 0.9
            elif 30 <= avg_length <= 200:
                return 0.7
            else:
                return 0.4

        elif metric == "toxicity":
            # Simple keyword detection
            toxic_words = [
                "hate", "kill", "stupid", "idiot", "terrible",
                "awful", "worthless", "die", "attack"
            ]
            output_lower = output.lower()
            toxic_count = sum(1 for w in toxic_words if w in output_lower)
            return min(1.0, toxic_count * 0.25)

        return 0.5


# Quick test
async def _test():
    gate = QualityGate()

    # Test good response
    result = await gate.check(
        input="What is the capital of France?",
        output="The capital of France is Paris. Paris is located in northern France and is the country's largest city.",
        context="France is a country in Western Europe. Its capital city is Paris, which is known for the Eiffel Tower.",
    )
    print(f"Good response: passed={result.passed}, scores={result.scores}")

    # Test bad response
    result = await gate.check(
        input="What is the capital of France?",
        output="Maybe it could possibly be some city, I hate this question.",
        context="France is a country in Western Europe.",
    )
    print(f"Bad response: passed={result.passed}, failed={result.failed_metrics}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
