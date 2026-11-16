from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class NiaBugReportParams(BaseModel):
    """Parameters for nia_bug_report"""
    description: str
    """Description (10-5000 chars)"""
    bug_type: Optional[Literal["bug", "feature-request", "improvement", "other"]] = None
    """Report type"""
    additional_context: Optional[Dict[str, Any]] = None
    """Extra context"""

async def nia_bug_report(params: NiaBugReportParams) -> Dict[str, Any]:
    """
    Submit bug/feature request.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__nia_bug_report", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
