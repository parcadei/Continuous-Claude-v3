from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ReadFileParams(BaseModel):
    """Parameters for read_file"""
    limit: Optional[int] = None
    """Number of lines to read"""
    path: str
    """File path"""
    start_line: Optional[int] = None
    """Line to start from (1-based) or negative for tail behavior (-N reads last N lines)"""

async def read_file(params: ReadFileParams) -> Dict[str, Any]:
    """
    Read file contents, optionally specifying a starting line and number of lines.

Details:
- 1‑based lines; no params → entire file
- `start_line` > 0: start at that line (e.g., 10)
- `start_line` < 0: last N lines (like `tail -n`)
- `limit`: only with positive `start_line` (e.g., start_line=10, limit=20 → lines 10–29)

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__read_file", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
