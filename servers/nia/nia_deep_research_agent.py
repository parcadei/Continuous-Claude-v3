from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class NiaDeepResearchAgentParams(BaseModel):
    """Parameters for nia_deep_research_agent"""
    query: str
    """Research question"""
    output_format: Optional[Dict[str, Any]] = None
    """Format hint (e.g. 'comparison table')"""

async def nia_deep_research_agent(params: NiaDeepResearchAgentParams) -> Dict[str, Any]:
    """
    AI-powered deep research on any topic.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__nia_deep_research_agent", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
