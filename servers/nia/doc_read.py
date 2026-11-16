from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class DocReadParams(BaseModel):
    """Parameters for doc_read"""
    source_identifier: str
    """UUID/name/URL"""
    path: str
    """Virtual path"""
    line_start: Optional[Dict[str, Any]] = None
    """Start line"""
    line_end: Optional[Dict[str, Any]] = None
    """End line"""
    max_length: Optional[Dict[str, Any]] = None
    """Max chars"""

async def doc_read(params: DocReadParams) -> Dict[str, Any]:
    """
    Read docs page by virtual path.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__doc_read", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
