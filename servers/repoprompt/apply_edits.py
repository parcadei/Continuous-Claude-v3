from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ApplyEditsParams(BaseModel):
    """Parameters for apply_edits"""
    all: Optional[bool] = None
    """Replace all occurrences (default: false)"""
    edits: Optional[List[Dict[str, Any]]] = None
    """Multiple edits"""
    on_missing: Optional[Literal["error", "create"]] = None
    """Behavior when the file is missing (only for `rewrite`)"""
    path: str
    """File path"""
    replace: Optional[str] = None
    """Replacement text"""
    rewrite: Optional[str] = None
    """Replace the entire file content with this string"""
    search: Optional[str] = None
    """Text to find"""
    verbose: Optional[bool] = None
    """Include diff preview"""

async def apply_edits(params: ApplyEditsParams) -> Dict[str, Any]:
    """
    Apply direct file edits (rewrite or search/replace).

Examples:

Single replacement:
`{"path": "file.swift", "search": "oldCode", "replace": "newCode", "all": true}`

Multiple edits:
`{"path": "file.swift", "edits": [{"search": "old1", "replace": "new1"}, {"search": "old2", "replace": "new2"}]}`

Rewrite entire file:
`{"path": "file.swift", "rewrite": "complete file content...", "on_missing": "create"}`

Note: When creating new files (e.g., using `on_missing="create"`), and multiple roots are loaded, you must provide an absolute path within a loaded root; relative paths are rejected to avoid ambiguity. Missing intermediate folders are automatically created.

Options: `verbose` (show diff), `on_missing` (for rewrite: "error" | "create")

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__apply_edits", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
