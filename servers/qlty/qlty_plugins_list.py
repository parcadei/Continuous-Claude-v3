from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class QltyPluginsListParams(BaseModel):
    """Parameters for qlty_plugins_list"""
    cwd: Optional[str] = None
    """Working directory"""

async def qlty_plugins_list(params: QltyPluginsListParams) -> Dict[str, Any]:
    """
    List available qlty plugins.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("qlty__qlty_plugins_list", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "qlty")

    return normalized
