from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class QltySmellsParams(BaseModel):
    """Parameters for qlty_smells"""
    paths: Optional[List[str]] = None
    """Files to analyze"""
    all: Optional[bool] = None
    """Analyze all files"""
    json_output: Optional[bool] = None
    """Return JSON instead of text"""
    cwd: Optional[str] = None
    """Working directory"""

async def qlty_smells(params: QltySmellsParams) -> Dict[str, Any]:
    """
    Find code smells (duplication, complexity hotspots).

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("qlty__qlty_smells", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "qlty")

    return normalized
