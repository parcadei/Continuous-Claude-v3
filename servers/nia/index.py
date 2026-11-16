from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class IndexParams(BaseModel):
    """Parameters for index"""
    url: str
    """GitHub URL, docs URL, or arXiv ID"""
    resource_type: Optional[Dict[str, Any]] = None
    """Auto-detected if omitted"""
    branch: Optional[Dict[str, Any]] = None
    """Repo branch"""
    url_patterns: Optional[Dict[str, Any]] = None
    """Docs: include patterns"""
    exclude_patterns: Optional[Dict[str, Any]] = None
    """Docs: exclude patterns"""
    max_age: Optional[Dict[str, Any]] = None
    """Cache max age (sec)"""
    only_main_content: Optional[bool] = None
    """Skip nav/footer"""
    wait_for: Optional[Dict[str, Any]] = None
    """Dynamic load wait (ms)"""
    include_screenshot: Optional[Dict[str, Any]] = None
    """Screenshot pages"""
    check_llms_txt: Optional[bool] = None
    """Check llms.txt"""
    llms_txt_strategy: Optional[Literal["prefer", "only", "ignore"]] = None
    """llms.txt handling"""

async def index(params: IndexParams) -> Dict[str, Any]:
    """
    Index repo/docs/paper. Auto-detects type from URL. Use manage_resource(action='status') to monitor.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__index", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
