from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class CodeGrepParams(BaseModel):
    """Parameters for code_grep"""
    repository: str
    """owner/repo"""
    pattern: str
    """Regex pattern"""
    path: Optional[str] = None
    """Path prefix"""
    context_lines: Optional[Dict[str, Any]] = None
    """Context lines"""
    A: Optional[Dict[str, Any]] = None
    """Lines after"""
    B: Optional[Dict[str, Any]] = None
    """Lines before"""
    case_sensitive: Optional[bool] = None
    """Case sensitive"""
    whole_word: Optional[bool] = None
    """Whole words"""
    fixed_string: Optional[bool] = None
    """Literal string"""
    max_matches_per_file: Optional[int] = None
    """Per-file limit"""
    max_total_matches: Optional[int] = None
    """Total limit"""
    output_mode: Optional[Literal["content", "files_with_matches", "count"]] = None
    """Output mode"""
    highlight: Optional[bool] = None
    """Highlight matches"""
    exhaustive: Optional[bool] = None
    """Full scan (True) or BM25 (False)"""

async def code_grep(params: CodeGrepParams) -> Dict[str, Any]:
    """
    Regex search in repo code.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__code_grep", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
