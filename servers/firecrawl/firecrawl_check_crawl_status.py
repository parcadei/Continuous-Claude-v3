from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class FirecrawlCheckCrawlStatusParams(BaseModel):
    """Parameters for firecrawl_check_crawl_status"""
    id: str

async def firecrawl_check_crawl_status(params: FirecrawlCheckCrawlStatusParams) -> Dict[str, Any]:
    """
    
Check the status of a crawl job.

**Usage Example:**
```json
{
  "name": "firecrawl_check_crawl_status",
  "arguments": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```
**Returns:** Status and progress of the crawl job, including results if available.


    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("firecrawl__firecrawl_check_crawl_status", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "firecrawl")

    return normalized
