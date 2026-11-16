"""
Proposition Extractor - Extract structured propositions from natural language.

Uses Claude to convert task descriptions into key-value pairs representing facts.

Usage:
    from scripts.extract_propositions import extract_propositions, UNKNOWN

    result = await extract_propositions(
        context="Build an API with JWT auth",
        domains=["auth", "backend"]  # Optional domain filter
    )

    # Returns:
    # {
    #     "propositions": {"has_api": True, "auth_method": "JWT"},
    #     "source": "extracted",  # or "cached"
    #     "confidence": 0.85
    # }
"""

from typing import Any

# Constant for unknown/ambiguous values
UNKNOWN = "UNKNOWN"

def get_cached(cache_key: str) -> dict[str, Any] | None:  # noqa: ARG001
    """
    Retrieve cached extraction result.

    This function is designed to be mocked in tests.
    Default implementation returns None (no caching).

    Args:
        cache_key: The cache key (typically context hash)

    Returns:
        Cached result dict or None if not cached
    """
    # Default: no caching. Override via mocking for cache tests.
    # cache_key parameter kept for API compatibility with mocks
    _ = cache_key  # Silence unused parameter warning
    return None


def set_cached(cache_key: str, value: dict[str, Any]) -> None:  # noqa: ARG001
    """
    Store extraction result in cache.

    This function is designed to be mocked in tests.
    Default implementation is a no-op.

    Args:
        cache_key: The cache key
        value: The result to cache
    """
    # Default: no-op. Override via mocking for cache tests.
    # Parameters kept for API compatibility with mocks
    _ = (cache_key, value)  # Silence unused parameter warnings


def call_claude(prompt: str, context: str) -> dict[str, Any]:
    """
    Call Claude API to extract propositions from context.

    This function is designed to be mocked in tests.
    In production, this would make an actual API call to Claude.

    Args:
        prompt: The extraction prompt
        context: The context/task description to analyze

    Returns:
        Dict with 'propositions' and 'confidence' keys
    """
    # In production, this would call Claude API
    # For now, return a default response
    # This will be mocked in tests
    raise NotImplementedError(
        "call_claude must be mocked in tests or implemented for production"
    )


def _build_prompt(context: str, domains: list[str] | None = None) -> str:
    """
    Build the extraction prompt for Claude.

    Args:
        context: The context to extract propositions from
        domains: Optional list of domains to focus on

    Returns:
        The formatted prompt string
    """
    domain_instruction = ""
    if domains:
        domain_list = ", ".join(domains)
        domain_instruction = f"""
Focus ONLY on propositions related to these domains: {domain_list}
Do not extract propositions from other domains."""

    return f"""Extract structured propositions from the following task description.

Return a JSON object with:
- "propositions": a dict of key-value pairs representing facts about the task
- "confidence": a float between 0.0 and 1.0 indicating how confident you are

Proposition values can be:
- boolean (True/False) for yes/no facts
- string for specific values (e.g., "JWT", "PostgreSQL")
- list for multiple values (e.g., ["JWT", "OAuth2"])
- "{UNKNOWN}" when information is ambiguous or not specified
{domain_instruction}

Task description:
{context}

Return ONLY valid JSON, no explanation."""


def _generate_cache_key(context: str, domains: list[str] | None) -> str:
    """Generate a cache key from context and domains."""
    domain_str = ",".join(sorted(domains)) if domains else ""
    return f"{hash(context)}:{domain_str}"


async def extract_propositions(
    context: str,
    domains: list[str] | None = None
) -> dict[str, Any]:
    """
    Extract structured propositions from natural language context.

    Args:
        context: The task description or context to analyze
        domains: Optional list of domains to filter propositions
                 (e.g., ["auth", "backend"])

    Returns:
        Dict with keys:
            - propositions: dict of extracted key-value pairs
            - source: "extracted" or "cached"
            - confidence: float between 0.0 and 1.0

    Raises:
        RuntimeError: If Claude API call fails (propagated from call_claude)
    """
    # Handle empty/whitespace context - return empty result without calling Claude
    if not context or not context.strip():
        return {
            "propositions": {},
            "source": "extracted",
            "confidence": 0.0,
        }

    # Check cache first
    cache_key = _generate_cache_key(context, domains)
    cached_result = get_cached(cache_key)
    if cached_result is not None:
        return {
            "propositions": cached_result["propositions"],
            "source": "cached",
            "confidence": cached_result["confidence"],
        }

    # Build prompt and call Claude
    prompt = _build_prompt(context, domains)
    claude_response = call_claude(prompt, context)

    # Validate response structure
    if not isinstance(claude_response, dict):
        return {
            "propositions": {},
            "source": "error",
            "confidence": 0.0,
            "error": f"Expected dict response, got {type(claude_response).__name__}",
        }

    if "propositions" not in claude_response:
        return {
            "propositions": {},
            "source": "error",
            "confidence": 0.0,
            "error": "Response missing 'propositions' key",
        }

    if not isinstance(claude_response.get("propositions"), dict):
        prop_type = type(claude_response.get("propositions")).__name__
        return {
            "propositions": {},
            "source": "error",
            "confidence": 0.0,
            "error": f"Expected 'propositions' to be dict, got {prop_type}",
        }

    # Clamp confidence to valid range
    raw_confidence = claude_response.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(raw_confidence)))
    except (TypeError, ValueError):
        confidence = 0.0

    # Build result
    result = {
        "propositions": claude_response["propositions"],
        "source": "extracted",
        "confidence": confidence,
    }

    # Cache the result (cache the propositions and confidence, not source)
    set_cached(cache_key, {
        "propositions": result["propositions"],
        "confidence": result["confidence"],
    })

    return result
