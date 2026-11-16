from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class DocLsParams(BaseModel):
    """Parameters for doc_ls"""
    source_identifier: str
    """UUID/name/URL"""
    path: Optional[str] = None
    """Virtual path"""

async def doc_ls(params: DocLsParams) -> Dict[str, Any]:
    """
    List docs directory contents.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__doc_ls", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
