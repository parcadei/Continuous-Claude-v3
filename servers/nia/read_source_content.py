from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ReadSourceContentParams(BaseModel):
    """Parameters for read_source_content"""
    source_type: Literal["repository", "documentation"]
    """Source type"""
    source_identifier: str
    """Repo: owner/repo:path. Docs: URL/ID"""
    metadata: Optional[Dict[str, Any]] = None
    """Search result metadata"""

async def read_source_content(params: ReadSourceContentParams) -> Dict[str, Any]:
    """
    Read full content of source file/document.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__read_source_content", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
