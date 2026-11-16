from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class QltyInitParams(BaseModel):
    """Parameters for qlty_init"""
    yes: Optional[bool] = None
    """Auto-accept defaults"""
    cwd: Optional[str] = None
    """Repository to initialize"""

async def qlty_init(params: QltyInitParams) -> Dict[str, Any]:
    """
    Initialize qlty in a repository. Creates .qlty/qlty.toml.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("qlty__qlty_init", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "qlty")

    return normalized
