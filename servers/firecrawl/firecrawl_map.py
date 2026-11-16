from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class FirecrawlMapParams(BaseModel):
    """Parameters for firecrawl_map"""
    url: str
    search: Optional[str] = None
    sitemap: Optional[Literal["include", "skip", "only"]] = None
    includeSubdomains: Optional[bool] = None
    limit: Optional[float] = None
    ignoreQueryParameters: Optional[bool] = None

async def firecrawl_map(params: FirecrawlMapParams) -> Dict[str, Any]:
    """
    
Map a website to discover all indexed URLs on the site.

**Best for:** Discovering URLs on a website before deciding what to scrape; finding specific sections of a website.
**Not recommended for:** When you already know which specific URL you need (use scrape or batch_scrape); when you need the content of the pages (use scrape after mapping).
**Common mistakes:** Using crawl to discover URLs instead of map.
**Prompt Example:** "List all URLs on example.com."
**Usage Example:**
```json
{
  "name": "firecrawl_map",
  "arguments": {
    "url": "https://example.com"
  }
}
```
**Returns:** Array of URLs found on the site.


    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("firecrawl__firecrawl_map", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "firecrawl")

    return normalized
