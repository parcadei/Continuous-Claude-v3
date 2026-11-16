from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class QltyCheckParams(BaseModel):
    """Parameters for qlty_check"""
    paths: Optional[List[str]] = None
    """Files or directories to check (empty = changed files)"""
    all: Optional[bool] = None
    """Check all files, not just changed"""
    fix: Optional[bool] = None
    """Auto-fix issues where possible"""
    level: Optional[Literal["note", "low", "medium", "high"]] = None
    """Minimum issue level to report"""
    json_output: Optional[bool] = None
    """Return JSON instead of text"""
    cwd: Optional[str] = None
    """Working directory (must have .qlty/qlty.toml)"""

async def qlty_check(params: QltyCheckParams) -> Dict[str, Any]:
    """
    Run linters on files. Returns issues found. Use --fix to auto-fix.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("qlty__qlty_check", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "qlty")

    return normalized
