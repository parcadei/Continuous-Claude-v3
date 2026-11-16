"""Extract E(X,Q) from prose skill definitions.

Uses LLM analysis to identify implicit parameters and their resolution status
from natural language skill definitions (SKILL.md prose sections).

USAGE:
    from scripts.skill_prose_extractor import extract_eqx_from_prose
    result = await extract_eqx_from_prose(skill_prose)

    # Result:
    {
        "parameters": {
            "auth_method": {"type": "enum", "values": ["JWT", "OAuth"], "required": True}
        },
        "unknowns": {"log_format": "UNKNOWN"},
        "z3_checkable": ["auth_method"]
    }

THEORY:
    This module extracts E(X,Q) - the set of parameters that need resolution -
    from prose descriptions. Unlike schema-based extraction which is deterministic,
    prose extraction requires LLM understanding of implicit requirements.

    - Z3-checkable: enum, bool, bounded int (finite domain)
    - LLM-only: string, unbounded int, complex types (infinite domain)
"""
import json
import re
from typing import TypedDict, Any


# Sentinel for unknown values (matches z3_erotetic.py)
UNKNOWN = "UNKNOWN"


class ProseExtractionResult(TypedDict):
    """Result of E(X,Q) extraction from prose."""
    parameters: dict[str, dict[str, Any]]  # param_name -> {type, values?, default?, ...}
    unknowns: dict[str, str]               # param_name -> "UNKNOWN" for unresolved
    z3_checkable: list[str]                # params with finite domains (enum, bool, bounded int)


async def extract_eqx_from_prose(prose: str) -> ProseExtractionResult:
    """
    Extract implicit parameters and their E(X,Q) status from prose.

    Uses LLM analysis to identify:
    - Implicit parameters mentioned in prose
    - Which parameters are unresolved (UNKNOWN)
    - Which parameters have finite domains (Z3-checkable)

    Args:
        prose: Skill prose content (markdown)

    Returns:
        ProseExtractionResult with parameters, unknowns, z3_checkable

    Example:
        >>> result = await extract_eqx_from_prose("Use JWT or OAuth for auth")
        >>> result["parameters"]["auth_method"]["type"]
        'enum'
    """
    if not prose.strip():
        return ProseExtractionResult(
            parameters={},
            unknowns={},
            z3_checkable=[]
        )

    # Call LLM for extraction
    raw_result = await _call_extraction_llm(prose)

    # Normalize and validate
    return _normalize_result(raw_result)


async def _call_extraction_llm(prose: str) -> dict[str, Any]:
    """
    Call LLM to extract parameters from prose.

    This is the integration point for LLM calls. In production, this uses
    Agentica/Claude. In tests, this is mocked.

    Args:
        prose: Skill prose content

    Returns:
        Raw LLM response dict
    """
    try:
        from agentica import spawn
    except ImportError:
        # Fallback for when Agentica isn't installed
        raise RuntimeError(
            "Agentica not installed. Run: uv sync --extra agentica\n"
            "For testing, mock _call_extraction_llm instead."
        )

    import os

    # Configure model
    model = os.getenv("AGENTICA_MODEL", "anthropic:claude-sonnet-4")

    extraction_prompt = f"""Analyze this skill prose and extract implicit parameters.

PROSE:
{prose}

TASK:
Identify all implicit parameters, their types, and whether they're resolved.

RETURN FORMAT (JSON only, no explanation):
{{
    "parameters": {{
        "param_name": {{
            "type": "enum|bool|int|string|duration",
            "values": ["val1", "val2"],  // for enums only
            "required": true|false,
            "default": null,  // if no default specified
            "min": null,      // for bounded int
            "max": null       // for bounded int
        }}
    }},
    "unknowns": {{
        "param_name": "UNKNOWN"  // for params without defaults
    }},
    "z3_checkable": ["param1"]  // enums, bools, bounded ints only
}}

RULES:
1. "X or Y" patterns suggest enum type with values [X, Y]
2. "true/false" or "enable/disable" suggest bool type
3. Range patterns like "30-300 seconds" suggest bounded int
4. Required params without defaults are UNKNOWN
5. Only finite-domain params (enum, bool, bounded int) are z3_checkable
6. String and unbounded int are NOT z3_checkable

Common implicit parameters to look for:
- auth_method, session_duration, error_format, log_format
- database_type, timeout, rate_limit, output_format
- verbose, debug_mode, dry_run, force

Return ONLY the JSON object, no markdown or explanation."""

    agent = await spawn(
        premise="You extract structured parameters from prose skill definitions.",
        model=model,
    )

    result = await agent.call(str, extraction_prompt)
    return _parse_llm_response(result)


def _parse_llm_response(response: str) -> dict[str, Any]:
    """
    Parse LLM response, extracting JSON from markdown if needed.

    Args:
        response: Raw LLM response (may contain markdown)

    Returns:
        Parsed dict with parameters, unknowns, z3_checkable

    Raises:
        ValueError: If response cannot be parsed as JSON
    """
    text = response.strip()

    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                raise ValueError(f"Could not parse JSON from response: {text[:100]}")
        else:
            raise ValueError(f"No JSON found in response: {text[:100]}")

    # Ensure required fields exist
    if "parameters" not in result:
        result["parameters"] = {}
    if "unknowns" not in result:
        result["unknowns"] = {}
    if "z3_checkable" not in result:
        result["z3_checkable"] = []

    return result


def _normalize_result(raw: dict[str, Any]) -> ProseExtractionResult:
    """
    Normalize and validate extraction result.

    Ensures:
    - All required fields present
    - Correct types
    - z3_checkable only contains finite-domain params
    - unknowns only contains params from parameters dict

    Args:
        raw: Raw extraction result

    Returns:
        Normalized ProseExtractionResult
    """
    parameters = raw.get("parameters", {})
    unknowns = raw.get("unknowns", {})
    z3_checkable = raw.get("z3_checkable", [])

    # Ensure parameters is dict
    if not isinstance(parameters, dict):
        parameters = {}

    # Ensure unknowns is dict
    if not isinstance(unknowns, dict):
        unknowns = {}

    # Ensure z3_checkable is list
    if not isinstance(z3_checkable, list):
        z3_checkable = []

    # Validate z3_checkable: only params with finite domains
    finite_domain_types = {"enum", "bool"}
    validated_z3 = []
    for param_name in z3_checkable:
        if param_name in parameters:
            param_spec = parameters[param_name]
            param_type = param_spec.get("type", "string")

            # enum and bool are always finite
            if param_type in finite_domain_types:
                validated_z3.append(param_name)
            # int with min/max is finite
            elif param_type == "int":
                if param_spec.get("min") is not None and param_spec.get("max") is not None:
                    validated_z3.append(param_name)

    # Validate unknowns: only params that exist in parameters
    validated_unknowns = {
        k: v for k, v in unknowns.items()
        if k in parameters and v == UNKNOWN
    }

    return ProseExtractionResult(
        parameters=parameters,
        unknowns=validated_unknowns,
        z3_checkable=validated_z3
    )
