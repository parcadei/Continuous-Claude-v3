"""Bidirectional E(X,Q) parity verification.

Compares E(X,Q) from prose vs schema to ensure converted schemas
preserve the semantic intent of original prose skill definitions.

USAGE:
    from scripts.skill_parity_checker import check_parity, ParityResult
    result = check_parity(prose_eqx, schema_eqx)

    if result.is_valid:
        print("Schema adequately covers prose requirements")
    else:
        print(f"Missing: {result.prose_only}")
        print(f"Coverage: {result.coverage_score:.1%}")

THEORY:
    Parity verification ensures that when converting prose skills to typed schemas,
    we don't lose semantic coverage. The coverage score measures what fraction of
    prose-identified parameters are captured in the schema.

    - coverage >= 0.8: Valid conversion (some flexibility allowed)
    - coverage < 0.8: Gaps need attention
    - prose_only: Parameters in prose but missing from schema (the gap)
    - schema_only: Extra parameters in schema (OK - superset is allowed)
"""
from dataclasses import dataclass, field
from typing import Any


# Coverage threshold for valid parity (can be tuned)
PARITY_THRESHOLD = 0.8


@dataclass
class ParityResult:
    """Result of bidirectional E(X,Q) parity check."""

    prose_only: list[str]       # Parameters in prose but not schema (the gap)
    schema_only: list[str]      # Parameters in schema but not prose (OK)
    coverage_score: float       # 0.0-1.0 (schema covers prose?)
    gaps: list[str]             # Semantic gaps (prose behaviors schema can't express)
    resolved_unknowns: list[str] = field(default_factory=list)  # Unknowns resolved by schema

    @property
    def is_valid(self) -> bool:
        """Check if parity meets threshold."""
        return self.coverage_score >= PARITY_THRESHOLD


def check_parity(
    prose_eqx: dict[str, Any],
    schema_eqx: dict[str, Any]
) -> ParityResult:
    """
    Check if schema E(X,Q) covers prose E(X,Q).

    Computes bidirectional coverage:
    - prose_only: What prose has that schema lacks (the gap)
    - schema_only: What schema adds beyond prose (allowed)
    - coverage_score: Fraction of prose params covered by schema

    Args:
        prose_eqx: E(X,Q) extraction from prose
        schema_eqx: E(X,Q) extraction from schema

    Returns:
        ParityResult with coverage analysis

    Example:
        >>> prose = {"parameters": {"x": {}, "y": {}}, ...}
        >>> schema = {"parameters": {"x": {}}, ...}
        >>> result = check_parity(prose, schema)
        >>> result.coverage_score
        0.5
    """
    prose_params = set(prose_eqx.get("parameters", {}).keys())
    schema_params = set(schema_eqx.get("parameters", {}).keys())

    # What's in prose but not schema (the gap)
    prose_only = prose_params - schema_params

    # What's in schema but not prose (allowed extras)
    schema_only = schema_params - prose_params

    # Coverage = (prose params covered by schema) / (all prose params)
    coverage = compute_coverage_score(prose_params, schema_params)

    # Track which prose unknowns are resolved by schema
    prose_unknowns = set(prose_eqx.get("unknowns", {}).keys())
    schema_unknowns = set(schema_eqx.get("unknowns", {}).keys())

    # Resolved = in prose unknowns but NOT in schema unknowns AND exists in schema
    resolved_unknowns = [
        u for u in prose_unknowns
        if u not in schema_unknowns and u in schema_params
    ]

    # Semantic gaps: prose behaviors that schema can't express
    # (For now, this is a placeholder for future LLM-based analysis)
    gaps: list[str] = []

    return ParityResult(
        prose_only=list(prose_only),
        schema_only=list(schema_only),
        coverage_score=coverage,
        gaps=gaps,
        resolved_unknowns=resolved_unknowns
    )


def compute_coverage_score(
    prose_params: set[str],
    schema_params: set[str]
) -> float:
    """
    Compute coverage score: fraction of prose params in schema.

    Args:
        prose_params: Set of parameter names from prose
        schema_params: Set of parameter names from schema

    Returns:
        Float in [0.0, 1.0]

    Note:
        Empty prose = 1.0 (vacuously true - nothing to cover)
    """
    if not prose_params:
        return 1.0

    covered = prose_params & schema_params
    return len(covered) / len(prose_params)
