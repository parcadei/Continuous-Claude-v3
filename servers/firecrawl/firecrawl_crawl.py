from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class FirecrawlCrawlParams(BaseModel):
    """Parameters for firecrawl_crawl"""
    url: str
    prompt: Optional[str] = None
    excludePaths: Optional[List[str]] = None
    includePaths: Optional[List[str]] = None
    maxDiscoveryDepth: Optional[float] = None
    sitemap: Optional[Literal["skip", "include", "only"]] = None
    limit: Optional[float] = None
    allowExternalLinks: Optional[bool] = None
    allowSubdomains: Optional[bool] = None
    crawlEntireDomain: Optional[bool] = None
    delay: Optional[float] = None
    maxConcurrency: Optional[float] = None
    webhook: Optional[Dict[str, Any]] = None
    deduplicateSimilarURLs: Optional[bool] = None
    ignoreQueryParameters: Optional[bool] = None
    scrapeOptions: Optional[Dict[str, Any]] = None

async def firecrawl_crawl(params: FirecrawlCrawlParams) -> Dict[str, Any]:
    """
    
 Starts a crawl job on a website and extracts content from all pages.
 
 **Best for:** Extracting content from multiple related pages, when you need comprehensive coverage.
 **Not recommended for:** Extracting content from a single page (use scrape); when token limits are a concern (use map + batch_scrape); when you need fast results (crawling can be slow).
 **Warning:** Crawl responses can be very large and may exceed token limits. Limit the crawl depth and number of pages, or use map + batch_scrape for better control.
 **Common mistakes:** Setting limit or maxDiscoveryDepth too high (causes token overflow) or too low (causes missing pages); using crawl for a single page (use scrape instead). Using a /* wildcard is not recommended.
 **Prompt Example:** "Get all blog posts from the first two levels of example.com/blog."
 **Usage Example:**
 ```json
 {
   "name": "firecrawl_crawl",
   "arguments": {
     "url": "https://example.com/blog/*",
     "maxDiscoveryDepth": 5,
     "limit": 20,
     "allowExternalLinks": false,
     "deduplicateSimilarURLs": true,
     "sitemap": "include"
   }
 }
 ```
 **Returns:** Operation ID for status checking; use firecrawl_check_crawl_status to check progress.
 
 

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("firecrawl__firecrawl_crawl", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "firecrawl")

    return normalized
