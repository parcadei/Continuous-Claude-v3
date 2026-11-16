from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ListModelsParams(BaseModel):
    """Parameters for list_models"""
    pass

async def list_models(params: ListModelsParams) -> Dict[str, Any]:
    """
    List available model presets (id, name, description, supported modes).
Use before `chat_send` to pick an appropriate preset.
If no presets exist, shows the current chat model. Without `model`, `chat_send` picks the first compatible preset.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__list_models", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
