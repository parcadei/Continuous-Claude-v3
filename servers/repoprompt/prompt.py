from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class PromptParams(BaseModel):
    """Parameters for prompt"""
    op: Optional[Literal["get", "set", "append", "clear"]] = None
    """Operation"""
    text: Optional[str] = None
    """Text for set/append"""

async def prompt(params: PromptParams) -> Dict[str, Any]:
    """
    Get or modify the shared prompt (instructions/notes). Ops: get | set | append | clear

Related: workspace_context (snapshot), manage_selection (files), chat_send (use prompt), apply_edits.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__prompt", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
