#!/usr/bin/env python3
"""
Erotetic Verifier - E(X,Q) Formal Verification System

Verifies whether all ambiguities in a task context have been resolved
through the Q-heuristic (question-based clarification) process.

USAGE:
    # As CLI
    uv run python -m scripts.agentica.erotetic_verifier \
        --context "Build an API" \
        --resolved '{"auth_method": "JWT", "session_duration": "24h"}'

    # As Python module
    from scripts.agentica_patterns.erotetic_verifier import verify_resolution
    result = await verify_resolution(
        context="Build an API",
        resolved={"auth_method": "JWT"}
    )

RETURNS:
    {
        "isEmpty": bool,           # True if E(X,Q) = empty set (fully resolved)
        "remainingCount": int,     # Number of unresolved ambiguities
        "remainingTopics": list,   # Topic names still needing resolution
        "confidence": float        # 0.0-1.0 confidence in the assessment
    }

REQUIREMENTS:
    - Python 3.12+ (Agentica requirement)
    - uv sync --extra agentica
    - Claude proxy running at localhost:8080 (optional, falls back to env models)

THEORY:
    E(X,Q) represents the "erotetic distance" - the set of remaining ambiguities
    after applying question-heuristic Q to context X. When E(X,Q) = ∅, the
    context is fully resolved and implementation can proceed without further
    clarification.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import TypedDict

# --- Type Definitions ---

class VerificationResult(TypedDict):
    """Result of erotetic verification."""
    isEmpty: bool              # True if E(X,Q) = empty set
    remainingCount: int        # Number of unresolved ambiguities
    remainingTopics: list[str] # Topic names needing resolution
    confidence: float          # 0.0-1.0 confidence


# --- Main Verification Function ---

async def verify_resolution(
    context: str,
    resolved: dict[str, str],
) -> VerificationResult:
    """
    Verify if all ambiguities in context are resolved.

    Uses Claude to analyze the context and determine if the resolved
    answers cover all necessary clarifications.

    Args:
        context: Task description that may contain ambiguities
        resolved: Dict of question keys to resolved answers

    Returns:
        VerificationResult with isEmpty, remainingCount, remainingTopics, confidence

    Example:
        >>> result = await verify_resolution(
        ...     context="Build an auth system",
        ...     resolved={"auth_method": "JWT"}
        ... )
        >>> result["isEmpty"]
        False  # May still need session_duration, error_format, etc.
    """
    try:
        # Call the LLM verifier
        result = await call_verifier_llm(context, resolved)

        # Validate and normalize the result
        return _validate_result(result)

    except Exception:
        # Fallback on error: assume not resolved (conservative)
        return VerificationResult(
            isEmpty=False,
            remainingCount=1,
            remainingTopics=["unknown_ambiguity"],
            confidence=0.3  # Low confidence on error
        )


async def call_verifier_llm(context: str, resolved: dict[str, str]) -> dict:
    """
    Call LLM to verify resolution.

    Uses Agentica SDK with Claude proxy (if available) or direct model access.

    Args:
        context: Task description
        resolved: Resolved answers

    Returns:
        Raw LLM response (dict)
    """
    try:
        from agentica import spawn
    except ImportError:
        raise RuntimeError(
            "Agentica not installed. Run: uv sync --extra agentica\n"
            "Note: Agentica requires Python 3.12+"
        )

    # Check if Claude proxy is available
    proxy_available = await _check_claude_proxy()

    # Configure model based on proxy availability
    if proxy_available:
        model = "openai:gpt-4o"  # Proxy translates to Claude
        base_url = "http://localhost:8080/v1"
    else:
        # Fall back to OpenRouter or direct model
        model = os.getenv("AGENTICA_MODEL", "anthropic:claude-sonnet-4")

    # Build the analysis prompt with actual values
    resolved_json = json.dumps(resolved, indent=2)
    analysis_prompt = f"""Analyze this task context and resolved answers to determine remaining ambiguities.

Task context:
{context}

Resolved answers:
{resolved_json}

Determine:
1. Are ALL ambiguities in the context resolved? (isEmpty: True/False)
2. How many ambiguities remain? (remainingCount: int)
3. What specific topics need clarification? (remainingTopics: list[str])
4. How confident are you in this assessment? (confidence: 0.0-1.0)

Return ONLY a JSON object with this exact structure:
{{
    "isEmpty": true or false,
    "remainingCount": 0,
    "remainingTopics": [],
    "confidence": 0.95
}}

Guidelines:
- isEmpty is True ONLY if NO clarifications are needed
- remainingCount = len(remainingTopics)
- Topic names should be snake_case identifiers
- Confidence 0.9+ for clear cases, 0.5-0.8 for ambiguous, <0.5 for unclear
- Common ambiguities: auth_method, session_duration, error_format,
  rate_limiting, validation_rules, security_requirements, etc.

Think about:
- What decisions would a developer need to make?
- What could be implemented in multiple valid ways?
- What requirements are implicit or underspecified?"""

    # Create agent with spawn pattern (idiomatic Agentica usage)
    agent = await spawn(
        premise="""You are a verification agent that analyzes task contexts
to identify remaining ambiguities. You return structured JSON responses
indicating whether all clarifications have been provided.""",
        model=model,
    )

    # Call the agent
    result = await agent.call(str, analysis_prompt)

    # Parse if string response
    if isinstance(result, str):
        # Try to extract JSON from markdown code blocks
        result = _extract_json_from_response(result)

    return result


# --- Helper Functions ---

async def _check_claude_proxy() -> bool:
    """Check if Claude proxy server is running."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8080/health",
                timeout=2.0
            )
            return response.status_code == 200
    except Exception:
        return False


def _extract_json_from_response(text: str) -> dict:
    """Extract JSON from LLM response that may contain markdown."""
    # Remove markdown code blocks
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        import re
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise


def _validate_result(result: dict) -> VerificationResult:
    """
    Validate and normalize LLM result.

    Ensures:
    - All required fields present
    - Correct types
    - Logical consistency (isEmpty=True => count=0, etc.)
    """
    # Extract fields with defaults
    is_empty = bool(result.get("isEmpty", False))
    remaining_count = int(result.get("remainingCount", 0))
    remaining_topics = result.get("remainingTopics", [])
    confidence = float(result.get("confidence", 0.5))

    # Ensure topics is a list of strings
    if not isinstance(remaining_topics, list):
        remaining_topics = []
    remaining_topics = [str(t).strip() for t in remaining_topics]

    # Enforce consistency invariants
    if is_empty:
        remaining_count = 0
        remaining_topics = []
    elif remaining_count == 0:
        is_empty = True
        remaining_topics = []
    elif len(remaining_topics) != remaining_count:
        # Adjust count to match topics
        remaining_count = len(remaining_topics)
        if remaining_count == 0:
            is_empty = True

    # Clamp confidence to [0.0, 1.0]
    confidence = max(0.0, min(1.0, confidence))

    return VerificationResult(
        isEmpty=is_empty,
        remainingCount=remaining_count,
        remainingTopics=remaining_topics,
        confidence=confidence
    )


# --- CLI Interface ---

async def main_async(args: argparse.Namespace) -> None:
    """Async main function for CLI."""
    # Parse resolved dict from JSON string
    try:
        resolved = json.loads(args.resolved)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in --resolved: {e}", file=sys.stderr)
        sys.exit(1)

    # Run verification
    result = await verify_resolution(
        context=args.context,
        resolved=resolved
    )

    # Output as JSON
    print(json.dumps(result, indent=2))


def main() -> None:
    """CLI entry point."""
    # Suppress Agentica logging to stderr to avoid polluting stdout
    # This ensures only JSON output goes to stdout for programmatic use
    logging.getLogger("agentica").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(
        description="Erotetic Verifier - Verify task ambiguity resolution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify simple context
  python -m scripts.agentica.erotetic_verifier \\
      --context "Build an API" \\
      --resolved '{}'

  # Verify with resolved answers
  python -m scripts.agentica.erotetic_verifier \\
      --context "Build an auth system" \\
      --resolved '{"auth_method": "JWT", "session_duration": "24h"}'

Returns:
  JSON object with isEmpty, remainingCount, remainingTopics, confidence
        """
    )

    parser.add_argument(
        "--context",
        type=str,
        required=True,
        help="Task description/context to verify"
    )

    parser.add_argument(
        "--resolved",
        type=str,
        required=True,
        help="JSON dict of resolved answers (e.g., '{\"key\": \"value\"}')"
    )

    args = parser.parse_args()

    # Run async main
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
