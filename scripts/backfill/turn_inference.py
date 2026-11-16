"""Turn inference from Braintrust spans.

Implements 4-step fallback strategy:
1. Extract from handoff/ledger (turn_span_id) - confidence 1.0
2. Braintrust metadata.turn_number - confidence 0.95
3. Span creation order (task span boundaries) - confidence 0.8
4. Batch numbering fallback - confidence 0.6

Each step is tried in order. If a step succeeds (finds valid turn info),
that result is returned. Otherwise, the next step is tried.
"""
from dataclasses import dataclass, field
from math import ceil
from typing import Any


# Confidence levels for each inference method
CONFIDENCE_HANDOFF = 1.0
CONFIDENCE_METADATA = 0.95
CONFIDENCE_SPAN_ORDER = 0.8
CONFIDENCE_BATCH_FALLBACK = 0.6


@dataclass
class TurnResult:
    """Result of turn inference.

    Attributes:
        turns: Mapping of turn number to list of span IDs in that turn
        method: Which inference method was used (handoff_frontmatter,
                braintrust_metadata, span_order, batch_fallback, none)
        confidence: Confidence level of the inference (0.0 to 1.0)
        warnings: List of warnings encountered during inference
    """

    turns: dict[int, list[str]]
    method: str
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)


class TurnInference:
    """Infer turn numbers from span data.

    Uses a 4-step fallback strategy to determine which spans belong
    to which turn (user-assistant exchange) in a session.
    """

    def infer_turns(
        self,
        spans: list[dict[str, Any]],
        handoff: dict[str, Any] | None = None,
        batch_size: int = 20,
    ) -> TurnResult:
        """Apply 4-step fallback to determine turn numbers.

        Priority order:
        1. Handoff frontmatter (turn_span_id) - highest confidence
        2. Braintrust metadata.turn_number - high confidence
        3. Task span boundaries - medium confidence
        4. Batch numbering (fallback) - low confidence

        Args:
            spans: List of span dictionaries from Braintrust
            handoff: Optional handoff dictionary with turn_span_id
            batch_size: Number of spans per batch for fallback method

        Returns:
            TurnResult with turn assignments and method used
        """
        # Handle empty spans
        if not spans:
            return TurnResult(turns={}, method="none", confidence=0.0)

        # Step 1: Try handoff frontmatter extraction
        if handoff:
            result = self._try_handoff_extraction(spans, handoff)
            if result is not None:
                return result

        # Step 2: Try metadata.turn_number extraction
        result = self._try_metadata_extraction(spans)
        if result is not None:
            return result

        # Step 3: Try task span boundary detection
        result = self._try_task_boundary_detection(spans)
        if result is not None:
            return result

        # Step 4: Fall back to batch numbering
        return self._apply_batch_fallback(spans, batch_size)

    def _try_handoff_extraction(
        self, spans: list[dict[str, Any]], handoff: dict[str, Any]
    ) -> TurnResult | None:
        """Step 1: Extract from handoff turn_span_id.

        If the handoff contains a turn_span_id, use it to identify the
        turn boundary. This is the highest confidence method.

        Args:
            spans: List of span dictionaries
            handoff: Handoff dictionary with potential turn_span_id

        Returns:
            TurnResult if turn_span_id found and valid, None otherwise
        """
        turn_span_id = handoff.get("turn_span_id")
        if not turn_span_id:
            return None

        # Check if the span exists in our list
        span_ids = {span.get("id") for span in spans}
        if turn_span_id not in span_ids:
            # Span not found, fall through to next method
            # (could add warning here, but silent fallthrough is also valid)
            return None

        # Found the turn_span_id - assign all spans to turn 1
        # (since we only have one known turn boundary)
        all_span_ids: list[str] = [
            str(span.get("id")) for span in spans if span.get("id")
        ]

        return TurnResult(
            turns={1: all_span_ids},
            method="handoff_frontmatter",
            confidence=CONFIDENCE_HANDOFF,
            warnings=[],
        )

    def _try_metadata_extraction(
        self, spans: list[dict[str, Any]]
    ) -> TurnResult | None:
        """Step 2: Use metadata.turn_number if present.

        If spans have turn_number in their metadata, use those values
        to group spans into turns.

        Args:
            spans: List of span dictionaries

        Returns:
            TurnResult if turn_number found in metadata, None otherwise
        """
        turns: dict[int, list[str]] = {}
        has_turn_numbers = False

        for span in spans:
            metadata = span.get("metadata", {}) or {}
            turn_number = metadata.get("turn_number")

            if turn_number is not None:
                has_turn_numbers = True
                span_id = span.get("id")
                if span_id:
                    if turn_number not in turns:
                        turns[turn_number] = []
                    turns[turn_number].append(span_id)

        if not has_turn_numbers:
            return None

        return TurnResult(
            turns=turns,
            method="braintrust_metadata",
            confidence=CONFIDENCE_METADATA,
            warnings=[],
        )

    def _try_task_boundary_detection(
        self, spans: list[dict[str, Any]]
    ) -> TurnResult | None:
        """Step 3: Detect turn boundaries from task spans.

        Task spans typically mark the beginning of a new turn
        (user message -> assistant response cycle). We use these
        as boundaries to group spans.

        Args:
            spans: List of span dictionaries

        Returns:
            TurnResult if task spans found, None otherwise
        """
        turns: dict[int, list[str]] = {}
        current_turn = 0
        has_task_spans = False

        for span in spans:
            span_attrs = span.get("span_attributes", {}) or {}
            span_type = span_attrs.get("type", "")
            span_id = span.get("id")

            if span_type == "task":
                # Task span marks the start of a new turn
                has_task_spans = True
                current_turn += 1
                if current_turn not in turns:
                    turns[current_turn] = []
                if span_id:
                    turns[current_turn].append(span_id)
            elif current_turn > 0 and span_id:
                # Add non-task spans to current turn
                turns[current_turn].append(span_id)

        if not has_task_spans:
            return None

        return TurnResult(
            turns=turns,
            method="span_order",
            confidence=CONFIDENCE_SPAN_ORDER,
            warnings=[],
        )

    def _apply_batch_fallback(
        self, spans: list[dict[str, Any]], batch_size: int
    ) -> TurnResult:
        """Step 4: Fallback to batch numbering.

        When no other method works, divide spans into fixed-size
        batches. This is the lowest confidence method.

        Args:
            spans: List of span dictionaries
            batch_size: Number of spans per batch

        Returns:
            TurnResult with batch-based turn assignments
        """
        turns: dict[int, list[str]] = {}
        num_batches = ceil(len(spans) / batch_size)

        for i, span in enumerate(spans):
            span_id = span.get("id")
            if span_id:
                turn_number = (i // batch_size) + 1
                if turn_number not in turns:
                    turns[turn_number] = []
                turns[turn_number].append(span_id)

        return TurnResult(
            turns=turns,
            method="batch_fallback",
            confidence=CONFIDENCE_BATCH_FALLBACK,
            warnings=[
                "Using batch fallback for turn inference - "
                "turn boundaries are estimated, not detected"
            ],
        )
