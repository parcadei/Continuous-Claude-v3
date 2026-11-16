from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GetCodeStructureParams(BaseModel):
    """Parameters for get_code_structure"""
    max_results: Optional[int] = None
    """Maximum number of codemaps to return (default: 25)"""
    paths: Optional[List[str]] = None
    """Array of file or directory paths (when scope='paths')"""
    scope: Optional[Literal["paths", "selected"]] = None
    """Scope of operation: current selection or explicit paths"""

async def get_code_structure(params: GetCodeStructureParams) -> Dict[str, Any]:
    """
    Return code structure (codemaps) for files and directories.

Scopes:
- `scope="selected"` — structures for the **current selection** (also lists files without codemaps)
- `scope="paths"` (default) — pass `paths` (files and/or directories; directories are recursive)

Note: Use with `get_file_tree` and `search` to explore before selecting.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__get_code_structure", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
