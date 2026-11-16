from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class QltyFmtParams(BaseModel):
    """Parameters for qlty_fmt"""
    paths: Optional[List[str]] = None
    """Files to format (empty = changed files)"""
    all: Optional[bool] = None
    """Format all files"""
    cwd: Optional[str] = None
    """Working directory"""

async def qlty_fmt(params: QltyFmtParams) -> Dict[str, Any]:
    """
    Auto-format files using configured formatters.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("qlty__qlty_fmt", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "qlty")

    return normalized
