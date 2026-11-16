"""JSON parsing utilities for the Native REPL Research Coordinator.

This module provides functions to extract JSON from LLM responses,
handling markdown code blocks and partial JSON extraction.

Functions:
    extract_json_from_markdown: Extract JSON from markdown code block
    parse_json_list: Parse JSON list from response
    parse_json_dict: Parse JSON dict from response
"""

import json
from typing import Any

# Constant for JSON code block marker
JSON_BLOCK_MARKER = "```json"


def extract_json_from_markdown(response: str) -> str | None:
    """Extract JSON from markdown code block.

    Args:
        response: The response string potentially containing markdown

    Returns:
        Extracted JSON string or None if not found
    """
    if JSON_BLOCK_MARKER not in response:
        return None
    start = response.find(JSON_BLOCK_MARKER) + len(JSON_BLOCK_MARKER)
    end = response.find("```", start)
    if end > start:
        return response[start:end].strip()
    return None


def _try_parse_json(text: str) -> Any:
    """Try to parse JSON, return None on failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_json_list(response: str) -> list[dict[str, Any]]:
    """Parse JSON list from agent response.

    Attempts multiple extraction strategies:
    1. Direct parse of the entire response
    2. Extract from markdown code block
    3. Find and parse array brackets

    Args:
        response: The response string from an agent

    Returns:
        Parsed list of dicts, or empty list on failure
    """
    # Try direct parse
    parsed = _try_parse_json(response)
    if isinstance(parsed, list):
        return parsed

    # Try markdown extraction
    extracted = extract_json_from_markdown(response)
    if extracted:
        parsed = _try_parse_json(extracted)
        if isinstance(parsed, list):
            return parsed

    # Try finding array brackets
    if "[" in response:
        start = response.find("[")
        end = response.rfind("]") + 1
        if end > start:
            parsed = _try_parse_json(response[start:end])
            if isinstance(parsed, list):
                return parsed

    return []


def parse_json_dict(response: str) -> dict[str, Any]:
    """Parse JSON dict from agent response.

    Attempts multiple extraction strategies:
    1. Direct parse of the entire response
    2. Extract from markdown code block
    3. Find and parse object brackets

    Args:
        response: The response string from an agent

    Returns:
        Parsed dict, or empty dict on failure
    """
    # Try direct parse
    parsed = _try_parse_json(response)
    if isinstance(parsed, dict):
        return parsed

    # Try markdown extraction
    extracted = extract_json_from_markdown(response)
    if extracted:
        parsed = _try_parse_json(extracted)
        if isinstance(parsed, dict):
            return parsed

    # Try finding object brackets
    if "{" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        if end > start:
            parsed = _try_parse_json(response[start:end])
            if isinstance(parsed, dict):
                return parsed

    return {}
